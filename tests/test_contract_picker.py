"""Contract picker (roadmap stage 2, 2026-10-22): up to three contracts that fit a stated plan, or none.

Driven on fixture chains: no network. The fit score is a match-and-tradability score, never a chance of
profit; expiry payoff and model value before expiry stay apart; a mid is never treated as a fill.
"""
from __future__ import annotations

import math
from datetime import date

import pandas as pd
import pytest

from app.analytics import contract_picker as cp

TODAY = date(2026, 10, 22)
R = 0.04


def _row(k, dte, *, call=True, iv=0.30, spread=0.1, oi=2000, vol=300, contract=None, state="two_sided", spot=100.0):
    from app.analytics.greeks import bs_price, greeks
    import numpy as np
    tau = dte / 365.0
    mid = float(bs_price(spot, np.array([k]), np.array([tau]), np.array([iv]), R, 0.0, call)[0])
    g = greeks(spot, np.array([k]), np.array([tau]), np.array([iv]), R, 0.0, np.array([call]))
    exp = (pd.Timestamp(TODAY) + pd.Timedelta(days=dte)).date().isoformat()
    return {"contract": contract or "XYZ{}{}{:08d}".format(exp[2:].replace("-", ""), "C" if call else "P", int(k * 1000)),
            "expiry": exp, "dte": dte, "tau": tau, "strike": float(k), "is_call": call,
            "bid": round(mid - spread / 2, 2), "ask": round(mid + spread / 2, 2), "quote_mid": round(mid, 3), "last": mid,
            "quote_state": state, "spread_abs": spread, "spread_pct": spread / mid * 100 if mid else None,
            "volume": float(vol), "open_interest": float(oi), "iv": iv, "delta": float(g["delta"][0]),
            "gamma": float(g["gamma"][0]), "theta": float(g["theta"][0]), "vega": float(g["vega"][0]),
            "iv_source": "otm_mid", "last_trade_age_h": 0.1}


def _frames(dtes=(30, 45, 60), strikes=(85, 90, 95, 100, 105, 110, 115, 120), **kw):
    out = {}
    for d in dtes:
        rows = [_row(k, d, **kw) for k in strikes] + [_row(k, d, call=False, **kw) for k in strikes]
        f = pd.DataFrame(rows)
        out[f["expiry"].iloc[0]] = f
    return out


def _plan(**kw):
    p = {"thesis": "bull", "hold_days": 14, "max_premium": 800.0, "target": 110.0, "invalidation": None, "through_event": False}
    p.update(kw)
    return p


def test_up_to_three_contracts_that_fit_each_explained():
    out = cp.pick(_frames(), 100.0, R, 0.0, _plan(), TODAY, None, None, "XYZ")
    assert 1 <= len(out["picks"]) <= 3 and out["why_none"] is None
    for p in out["picks"]:
        assert p["type"] == "call" and p["ask"] * 100 <= 800 and cp.DELTA_LO <= abs(p["delta"]) <= cp.DELTA_HI
        assert p["dte"] >= 14 + cp.EXPIRY_BUFFER_DAYS
        assert p["why"]["fit"].startswith("Costs $") and p["why"]["tradeoff"]
        assert p["multiplier"] == 100
    assert "not a chance of profit" in out["fit_note"] and "not a price anybody has offered" in out["fill_note"].replace("price anybody", "price anybody")


def test_none_fits_is_said_with_the_reasons_and_nothing_is_forced():
    out = cp.pick(_frames(), 100.0, R, 0.0, _plan(max_premium=20.0), TODAY, None, None, "XYZ")
    assert out["picks"] == [] and "cost more than your limit at the ask" in out["why_none"]
    one = cp.pick(_frames(dtes=(30,), strikes=(100,)), 100.0, R, 0.0, _plan(), TODAY, None, None, "XYZ")
    assert len(one["picks"]) == 1, "one eligible contract is one pick, not three"


def test_a_report_inside_the_hold_needs_the_plan_to_say_so():
    earn = "2026-10-30"
    exits_before = cp.pick(_frames(), 100.0, R, 0.0, _plan(), TODAY, earn, None, "XYZ")
    assert exits_before["event_in_hold"] and exits_before["picks"] == []
    assert "held through the report on 2026-10-30" in exits_before["why_none"]
    assert exits_before["conflict"] == ("The 2026-10-30 earnings report falls inside your 14-day hold. Either say you "
                                        "mean to hold through it, or plan a hold of 7 days or fewer.")
    holds = cp.pick(_frames(), 100.0, R, 0.0, _plan(through_event=True), TODAY, earn, None, "XYZ")
    assert holds["picks"]
    sc = holds["picks"][0]["scenarios"]
    crush = next(s for s in sc["before_expiry"] if s["label"] == "Implied volatility falls")
    assert sc["vol_drop_pct"] == 30 and "report you plan to hold through" in crush["why"]
    assert any(e["kind"] == "earnings" for e in holds["picks"][0]["events"])


def test_adjusted_contracts_are_left_out_for_want_of_a_deliverable():
    f = _frames(dtes=(30,), strikes=(100,))
    exp = list(f)[0]
    f[exp]["contract"] = ["XYZ1" + c[3:] for c in f[exp]["contract"]]
    out = cp.pick(f, 100.0, R, 0.0, _plan(), TODAY, None, None, "XYZ")
    assert out["picks"] == [] and out["excluded"]["adjusted"] >= 1
    assert cp.is_adjusted("AAPL1261120C00350000", "AAPL") and not cp.is_adjusted("AAPL261120C00350000", "AAPL")
    assert not cp.is_adjusted("BRKB261120C00500000", "BRK-B")


def test_wide_spreads_and_missing_quotes_are_not_tradable_picks():
    wide = cp.pick(_frames(spread=3.0), 100.0, R, 0.0, _plan(max_premium=5000), TODAY, None, None, "XYZ")
    assert wide["picks"] == [] and wide["excluded"]["wide_spread"] > 0
    stale = cp.pick(_frames(state="no_bid"), 100.0, R, 0.0, _plan(max_premium=5000), TODAY, None, None, "XYZ")
    assert stale["picks"] == [] and stale["excluded"]["no_quote"] > 0


def test_expiry_payoff_and_model_value_before_expiry_are_kept_apart():
    out = cp.pick(_frames(), 100.0, R, 0.0, _plan(invalidation=95.0), TODAY, None, None, "XYZ")
    p = out["picks"][0]
    sc = p["scenarios"]
    labels = [s["label"] for s in sc["before_expiry"]]
    assert labels == ["Stock at your target", "Stock unchanged", "Stock moves against you", "Implied volatility falls"]
    flat = next(s for s in sc["before_expiry"] if s["label"] == "Stock unchanged")
    assert flat["pnl"] < 0, "time passing with the stock still costs a bought option"
    against = next(s for s in sc["before_expiry"] if s["label"] == "Stock moves against you")
    assert against["underlying"] == 95.0 and "invalidation" in against["why"]
    unchanged_exp = next(s for s in sc["at_expiry"] if s["label"] == "Unchanged")
    assert unchanged_exp["value"] == round(max(100.0 - p["strike"], 0) * 100)
    assert sc["paid"] == round(p["ask"] * 100), "valued against the ask, not the mid"
    assert "not prices anyone has offered" in out["model_note"]


def test_a_put_for_a_falling_view_and_a_target_it_cannot_reach_scores_no_sensitivity():
    out = cp.pick(_frames(), 100.0, R, 0.0, _plan(thesis="bear", target=97.0), TODAY, None, None, "XYZ")
    assert all(p["type"] == "put" for p in out["picks"])
    for p in out["picks"]:
        if p["breakeven_ask"] < 97.0:
            assert p["fit"]["parts"]["sensitivity"] == 0


def test_the_picks_differ_so_the_tradeoff_is_visible():
    out = cp.pick(_frames(), 100.0, R, 0.0, _plan(max_premium=2000), TODAY, None, None, "XYZ")
    ds = [abs(p["delta"]) for p in out["picks"]]
    assert len(out["picks"]) >= 2 and max(ds) - min(ds) >= 0.15


def test_an_unknown_report_date_is_said_not_assumed_absent():
    out = cp.pick(_frames(), 100.0, R, 0.0, _plan(), TODAY, None, None, "XYZ")
    assert "was not checked" in out["earnings_note"]
    known = cp.pick(_frames(), 100.0, R, 0.0, _plan(), TODAY, "2027-01-28", None, "XYZ")
    assert known["earnings_note"] is None


def test_a_not_found_answer_reads_as_the_servers_sentence(tmp_path):
    from tests.test_frontend_v2_stage0 import V2, _run
    got = _run(tmp_path, f"""
      const A = await import('{(V2 / "js/core/api.js").as_posix()}');
      print(JSON.stringify({{
        msg: A.explain(new A.ApiError('notfound', 404, "No listed options for 'AAPL'."), 'The contracts'),
        bare: A.explain(new A.ApiError('notfound', 404, 'Not Found'), 'The contracts'),
      }}));
    """)
    assert got["msg"].startswith("No listed options for 'AAPL'. If the data source is refusing requests")
    assert got["bare"] == "Nothing came back for the contracts." and "was not found" not in got["msg"] + got["bare"]
