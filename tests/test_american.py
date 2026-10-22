"""O2 (Options audit): equity and ETF options priced as American.

The Barone-Adesi-Whaley approximation is held to a Cox-Ross-Rubinstein tree,
then each place it is used is checked: the IV solve, the position engine's
values before expiry, and the research table's early-exercise column."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app.analytics import american as am
from app.analytics import contracts, position
from app.analytics import vol_surface as vs

ROOT = Path(__file__).resolve().parents[1]
R = 0.045


@pytest.mark.parametrize("is_call,q", [(False, 0.0), (False, 0.02), (True, 0.03)])
def test_baw_matches_a_fine_tree_to_six_months(is_call, q):
    worst = 0.0
    for S in (70, 85, 100, 115, 130):
        for days in (1, 7, 30, 90, 180):
            for v in (0.15, 0.3, 0.6):
                T = days / 365
                a = float(am.baw(S, 100, T, v, R, q, is_call))
                b = am.crr(S, 100, T, v, R, q, is_call, steps=1500)
                worst = max(worst, abs(a - b) / max(0.005 * b, 0.10))
    assert worst <= 1.0


def test_american_is_european_where_early_exercise_is_worthless():
    # A call with no dividend, a put at a zero rate: never exercised early.
    S, K, T, v = np.array([90.0, 100, 110]), 100.0, 0.25, 0.3
    assert np.allclose(am.baw(S, K, T, v, R, 0.0, True), vs._bs(S, K, T, v, R, 0.0, True))
    assert np.allclose(am.baw(S, K, T, v, 0.0, 0.02, False), vs._bs(S, K, T, v, 0.0, 0.02, False))


def test_american_is_never_below_european_or_intrinsic():
    S = np.linspace(40, 160, 61)
    for is_call, q in ((True, 0.04), (False, 0.0)):
        a = am.baw(S, 100.0, 0.5, 0.25, R, q, is_call)
        e = vs._bs(S, 100.0, 0.5, 0.25, R, q, is_call)
        intr = np.maximum(S - 100 if is_call else 100 - S, 0)
        assert np.all(a >= e - 1e-12) and np.all(a >= intr - 1e-12)
        assert np.all(np.isfinite(a))
    # A deep in-the-money put at 4.5% is worth exercising now: the value is intrinsic.
    assert float(am.baw(50.0, 100.0, 0.5, 0.25, R, 0.0, False)) == pytest.approx(50.0, abs=1e-9)


def test_extreme_trial_vols_stay_finite():
    v = np.array([1e-3, 1e-2, 5.0])
    assert np.all(np.isfinite(am.baw(100.0, np.array([80.0, 100, 130]), 3 / 365, v, R, 0.01, False)))
    assert np.all(np.isfinite(am.baw(100.0, np.array([80.0, 100, 130]), 3 / 365, v, R, 0.03, True)))


def test_iv_solved_on_the_american_price_recovers_the_true_vol():
    # Put prices from a fine tree at 30% vol. The European solve reads the
    # exercise premium as extra vol, worst where the time value is thinnest.
    K = np.array([100.0, 105.0, 110.0, 115.0, 120.0, 125.0])
    T = 60 / 365
    px = np.array([am.crr(100.0, k, T, 0.30, R, 0.0, False, steps=1500) for k in K])
    args = (100.0, K, np.full(len(K), T), R, 0.0, np.zeros(len(K), bool))
    euro = vs.solve_iv(px, *args)
    amer = vs.solve_iv(px, *args, american=True)
    assert np.all(np.abs(amer[:4] - 0.30) < 0.008)
    assert abs(amer[4] - 0.30) < 0.02, "6 cents of time value: tiny vega magnifies the approximation"
    assert np.all(np.abs(euro[2:5] - 0.30) > 3 * np.abs(amer[2:5] - 0.30))
    # At 125 the tree says exercise now: the price is all intrinsic, so there
    # is no volatility in it to solve for. The European solve invents one.
    assert np.isnan(amer[5]) and euro[5] > 0.40


def test_index_options_stay_european():
    assert vs.is_american("AAPL") and vs.is_american("SPY") and vs.is_american("qqq")
    assert not vs.is_american("^SPX") and not vs.is_american("SPX") and not vs.is_american("XSP")


def _put_leg(strike, iv, mid):
    return {"type": "put", "side": "long", "qty": 1, "strike": strike, "expiry": "2026-12-18",
            "tau": 60 / 365, "iv": iv, "mid": mid, "bid": mid - 0.05, "ask": mid + 0.05}


def test_position_values_before_expiry_include_the_exercise_right():
    mid = am.crr(100.0, 120.0, 60 / 365, 0.30, R, 0.0, False, steps=1500)
    leg = _put_leg(120.0, 0.30, mid)
    eu = position.analyse([leg], 100.0, R, 0.0)
    us = position.analyse([leg], 100.0, R, 0.0, american=True)
    i = int(np.argmin(np.abs(np.array(us["curves"]["price"]) - 100.0)))
    # At today's price the American value is the mid (P/L about zero); the
    # European value sits below it by the missed premium.
    assert abs(us["curves"]["today"][i]) < 0.10 * 100
    assert eu["curves"]["today"][i] < us["curves"]["today"][i] - 5
    assert any("Barone-Adesi-Whaley" in a for a in us["assumptions"])
    assert any("cash-settled" in a for a in eu["assumptions"])
    # Payoff at expiry does not depend on the exercise style.
    assert us["curves"]["at_expiry"] == eu["curves"]["at_expiry"]


def test_table_reports_the_early_exercise_premium():
    import pandas as pd
    T = 60 / 365
    rows = []
    for k in (90.0, 100.0, 120.0):
        rows.append({"contract": "P{}".format(int(k)), "expiry": "2026-12-18", "dte": 60, "tau": T,
                     "strike": k, "is_call": False, "bid": 1.0, "ask": 1.1, "quote_mid": 1.05, "last": 1.05,
                     "quote_state": "two_sided", "spread_abs": 0.1, "spread_pct": 9.5, "volume": 100.0,
                     "open_interest": 1000.0, "iv": 0.30, "delta": -0.5, "gamma": 0.01, "theta": -0.01,
                     "vega": 0.1, "iv_source": "otm_mid", "last_trade_age_h": 0.1})
    frame = pd.DataFrame(rows)
    got = contracts.table(frame, 100.0, R, 0.0, side="put", american=True)["rows"]
    eep = {r["strike"]: r["early_exercise_premium_contract"] for r in got}
    assert eep[90.0] < eep[100.0] < eep[120.0], "deeper in the money, more exercise value"
    want = (am.baw(100.0, 120.0, T, 0.3, R, 0.0, False) - vs._bs(100.0, 120.0, T, 0.3, R, 0.0, False)) * 100
    assert eep[120.0] == pytest.approx(float(want), abs=0.01)
    assert all(r["exercise"] == "american" for r in got)
    eu = contracts.table(frame, 100.0, R, 0.0, side="put")["rows"]
    assert all(r["exercise"] == "european" and r["early_exercise_premium_contract"] is None for r in eu)


def test_every_pricing_call_site_passes_the_exercise_style():
    src = (ROOT / "app" / "main.py").read_text()
    # Five on the Options tab's reads, the daily edition's index surface, and the contract picker (2026-10-22).
    assert src.count("american=vol_surface_mod.is_american(") == 7
    js = (ROOT / "static" / "app.js").read_text()
    assert "Early exercise</th>" in js and "early_exercise_premium_contract" in js
