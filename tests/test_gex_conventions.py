"""Dealer gamma: one convention, checked with positions whose answer is known.

The documentation said dealers were short calls and long puts while the code
counted calls as positive gamma exposure, puts as negative, and read positive as
stabilizing: three statements that cannot all be true. The arithmetic is the
common convention (dealers long the calls customers sold, short the puts they
bought), so that is the stated assumption now, and these tests hold the
signs, the units and the hedge direction to it with single contracts, where
the right answer can be worked out by hand.

Nothing tested gex.py before this file.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.analytics import gex
from app.analytics.greeks import greeks

ROOT = Path(__file__).resolve().parent.parent
S0 = 100.0


def contract(strike, is_call, oi=1.0, tau=30 / 365.0, iv=0.3, root="ABC", multiplier=None):
    row = {"contract": "%s261120%s%08d" % (root, "C" if is_call else "P", int(strike * 1000)),
           "strike": float(strike), "is_call": is_call, "open_interest": oi, "volume": 0.0,
           "tau": tau, "iv": iv, "mid": 1.0, "last": 1.0, "bid": 0.9, "ask": 1.1, "dte": 30,
           "expiry": "2026-11-20"}
    if multiplier is not None:
        row["multiplier"] = multiplier
    return row


def frame(*rows):
    return pd.DataFrame(list(rows))


def dealer_shares(row, spot):
    """The dealer's delta in shares under the stated positions: long a call,
    short a put, 100 shares a contract."""
    g = greeks(spot, np.array([row["strike"]]), np.array([row["tau"]]), np.array([row["iv"]]),
               is_call=np.array([row["is_call"]]))
    position = 1.0 if row["is_call"] else -1.0
    return position * float(g["delta"][0]) * row["open_interest"] * 100.0


def hedge_trade_for_a_1pct_rise(row, spot):
    """Dollars of stock the dealer's delta changes by across a 1% move, worked
    out by re-pricing the option rather than from gamma: a central difference,
    valued at today's spot."""
    return (dealer_shares(row, spot * 1.005) - dealer_shares(row, spot * 0.995)) * spot


# ================================================== signs, units, hedge direction

def test_a_call_the_dealer_is_long_is_positive_gamma_and_its_hedge_sells_a_rise():
    row = contract(S0, True)
    out = gex.compute_exposure(frame(row), S0)
    value = float(out["gex"].iloc[0])
    assert value > 0
    # GEX is the change in the dealer's dollar delta for a 1% rise.
    moved = hedge_trade_for_a_1pct_rise(row, S0)
    assert moved == pytest.approx(value, rel=0.01)
    # The dealer's delta went up with the price, so staying neutral means
    # selling stock into the rise: leaning against it.
    assert moved > 0


def test_a_put_the_dealer_is_short_is_negative_gamma_and_its_hedge_buys_a_rise():
    row = contract(S0, False)
    out = gex.compute_exposure(frame(row), S0)
    value = float(out["gex"].iloc[0])
    assert value < 0
    moved = hedge_trade_for_a_1pct_rise(row, S0)
    assert moved == pytest.approx(value, rel=0.01)
    # The dealer's delta fell as the price rose, so the hedge buys stock into
    # the rise: adding to it.
    assert moved < 0


def test_the_units_are_gamma_times_contracts_times_shares_times_spot_squared_over_100():
    row = contract(S0, True, oi=7.0)
    out = gex.compute_exposure(frame(row), S0)
    gamma = float(out["gamma"].iloc[0])
    assert float(out["gex"].iloc[0]) == pytest.approx(gamma * 7.0 * 100.0 * S0 * S0 * 0.01)


def test_dex_is_the_dealers_own_option_delta_never_negative():
    """A long call and a short put both carry positive delta, so dealer DEX is
    at least zero by construction: which is why it is no longer read as a
    directional signal."""
    call, put = contract(S0, True), contract(S0, False)
    out = gex.compute_exposure(frame(call, put), S0)
    assert (out["dex"] >= 0).all()
    assert float(out["dex"].iloc[0]) == pytest.approx(dealer_shares(call, S0) * S0)
    assert float(out["dex"].iloc[1]) == pytest.approx(dealer_shares(put, S0) * S0)


def test_the_score_no_longer_reads_dex():
    from app.analytics import swing
    base = {"regime": {"state": "positive", "flip_point": 95.0}, "levels": {}, "totals": {"net_dex": 0.0}}
    huge = {**base, "totals": {"net_dex": 9e12}}
    assert swing._gamma_score(base, S0) == swing._gamma_score(huge, S0)


def test_the_score_reads_the_sign_at_spot_not_which_side_of_the_flip():
    """Above an upward flip is positive gamma; above a downward one is negative.
    The regime is the sign at spot, so the score follows it."""
    from app.analytics import swing
    up = {"regime": {"state": "positive", "flip_point": 95.0}, "levels": {}}
    down = {"regime": {"state": "negative", "flip_point": 95.0}, "levels": {}}
    assert swing._gamma_score(up, S0) > swing._gamma_score(down, S0)


# ======================================================= contract size

def test_a_stated_contract_size_scales_the_exposure():
    standard = gex.compute_exposure(frame(contract(S0, True)), S0)
    half = gex.compute_exposure(frame(contract(S0, True, multiplier=50.0)), S0)
    assert float(half["gex"].iloc[0]) == pytest.approx(float(standard["gex"].iloc[0]) / 2.0)


def test_an_adjusted_contract_of_unstated_size_is_left_out_and_counted():
    rows = [contract(S0, True), contract(S0 + 5, True), contract(S0, True, root="ABC1")]
    out = gex.analyse(frame(*rows), S0, ticker="ABC")
    assert out["excluded_contracts"] == 1
    assert "adjusted contract" in out["convention"]["multiplier"]


# ======================================================= the aggregate reads

def _chain():
    """Heavy puts below the price, heavy calls above it: the usual shape."""
    rows = []
    for k, oi in ((85, 4000), (90, 6000), (95, 3000)):
        rows.append(contract(k, False, oi=oi))
    for k, oi in ((105, 3000), (110, 6000), (115, 4000)):
        rows.append(contract(k, True, oi=oi))
    rows.append(contract(100, True, oi=500))
    rows.append(contract(100, False, oi=500))
    return frame(*rows)


def test_walls_sit_on_the_side_of_the_price_they_are_named_for():
    out = gex.analyse(_chain(), S0)
    cw, pw = out["levels"]["call_wall"], out["levels"]["put_wall"]
    assert cw["strike"] >= S0 and cw["gex"] > 0
    assert pw["strike"] <= S0 and pw["gex"] < 0


def test_the_pin_is_where_long_dealer_gamma_is_heaviest():
    out = gex.analyse(_chain(), S0)
    pin = out["levels"]["gamma_pin"]
    assert pin["gex"] > 0
    by = {r["strike"]: r["net_gex"] for r in out["by_strike"]}
    assert pin["strike"] == max((k for k in by if by[k] > 0), key=lambda k: by[k])


def test_the_flip_reports_which_way_it_crosses():
    out = gex.analyse(_chain(), S0)
    assert out["regime"]["flip_direction"] in ("upward", "downward")
    prof = out["profile"]
    i = int(np.argmin([abs(s - out["regime"]["flip_point"]) for s in prof["spots"]]))
    below, above = prof["net_gex"][max(0, i - 3)], prof["net_gex"][min(len(prof["spots"]) - 1, i + 3)]
    assert (out["regime"]["flip_direction"] == "upward") == (above > below)


def test_the_regime_is_the_sign_of_the_total_and_zero_is_neither():
    out = gex.analyse(_chain(), S0)
    total = out["totals"]["net_gex"]
    assert out["regime"]["state"] == ("positive" if total > 0 else "negative")
    flat = gex.analyse(frame(contract(S0, True, oi=0.0)), S0)
    assert flat["regime"]["state"] == "flat"


# ======================================================= what is said

def test_the_assumption_is_the_one_the_arithmetic_uses():
    out = gex.analyse(_chain(), S0)
    text = out["assumption"]
    assert "long the calls customers sold" in text and "short the puts customers bought" in text
    assert "Model assumption, not observed positions" in text
    conv = out["convention"]
    assert "leans against moves" in conv["positive"] and "adds to moves" in conv["negative"]
    assert conv["units"]["gex"] == "dollars of dealer delta per 1% move in spot"
    assert "who holds which side of a contract" in conv["cannot_establish"]


def test_the_contradiction_is_gone_from_every_explanation():
    for path in ("app/analytics/gex.py", "app/ai.py", "static/app.js", "app/analytics/pulse.py",
                 "app/analytics/swing.py"):
        src = (ROOT / path).read_text(encoding="utf-8")
        assert "short customer calls" not in src, path
        assert "dips get bought" not in src, path
    app = (ROOT / "static/app.js").read_text(encoding="utf-8")
    assert "${gloss('Put wall')} (support)" not in app
    assert "Above it dealers dampen moves, below it they amplify them." not in app
    assert "Positioning leans long" not in (ROOT / "app/analytics/greeks_panel.py").read_text()


JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def test_the_flip_sentence_follows_the_crossing():
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = """
      load('tests/support/browser_stubs.js');
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
      print('RESULT:' + JSON.stringify({
        up: gexFlipSentence({regime: {flip_direction: 'upward'}}),
        down: gexFlipSentence({regime: {flip_direction: 'downward'}}),
        none: gexFlipSentence({regime: {}})}));
    """
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=120, cwd=str(ROOT))
    body = json.loads((out.stdout + out.stderr).split("RESULT:", 1)[1].split("\n")[0])
    assert "above it hedging" in body["up"] and "dampens moves, below it adds" in body["up"]
    assert "below it hedging" in body["down"] and "above it adds" in body["down"]
    assert "same sign" in body["none"]
