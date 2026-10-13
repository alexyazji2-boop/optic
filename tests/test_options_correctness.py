"""The options inputs and maths corrected in the Options audit (2026-10-13).

Reference cases are worked by hand or by put-call parity, so a regression in
any formula shows as a number that no longer matches arithmetic anyone can
redo, rather than as a snapshot that silently moved.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from app import iv_history, rates
from app.analytics import liquidity, position, vol_surface as vs
from app.analytics.position import _bs_vec

ET = ZoneInfo("America/New_York")


# --------------------------------------------------------------- the clock

def test_expiry_is_measured_to_4pm_et_not_the_servers_date():
    # 9pm ET Monday is 01:00 UTC Tuesday: a UTC calendar count said 3 days to
    # Friday; the ET 4pm clock says 3 days and 19 hours.
    now = datetime(2026, 10, 13, 1, 0, tzinfo=timezone.utc)
    tau = vs.expiry_tau("2026-10-16", now)
    assert abs(tau * 365 * 24 - (3 * 24 + 19)) < 0.01
    assert vs.expiry_dte("2026-10-16", now) == 4          # Mon -> Fri on the ET calendar


def test_expiry_day_has_the_hours_actually_left():
    morning = datetime(2026, 10, 16, 10, 0, tzinfo=ET)
    assert abs(vs.expiry_tau("2026-10-16", morning) * 365 * 24 - 6.0) < 1e-6
    after = datetime(2026, 10, 16, 17, 0, tzinfo=ET)
    assert vs.expiry_tau("2026-10-16", after) == vs.MIN_TAU


# --------------------------------------------------------------- the quote

def test_quote_states_and_a_mid_only_for_a_two_sided_quote():
    df = pd.DataFrame({"bid": [1.0, 0.0, 1.0, 1.2, 1.0, 0.0], "ask": [1.2, 1.0, 0.0, 1.0, 1.0, 0.0],
                       "last": [1.1, 0.9, 0.95, 1.1, 1.0, 0.5]})
    out = vs.apply_quotes(df)
    assert list(out["quote_state"]) == ["two_sided", "no_bid", "no_ask", "crossed", "locked", "no_quote"]
    assert out["quote_mid"].iloc[0] == pytest.approx(1.1)
    assert out["quote_mid"].iloc[1:].isna().all()
    assert out["spread_pct"].iloc[0] == pytest.approx(0.2 / 1.1 * 100)
    assert np.isnan(out["spread_pct"].iloc[1]), "no spread from a zero bid"
    assert list(out["mark_source"]) == ["mid", "last", "last", "last", "last", "last"]


# --------------------------------------------------------------- the surface

def _chain(spot=100.0, r=0.04, q=0.01, vol=0.25, tau=30 / 365, put_extra=0.0):
    rows = []
    for k in (80, 85, 90, 95, 100, 105, 110, 115, 120):
        for is_call in (True, False):
            v = vol + (put_extra if not is_call else 0.0) + (100 - k) * 0.002
            px = float(_bs_vec([spot], k, tau, v, r, q, is_call)[0])
            rows.append({"expiry": "2026-11-13", "strike": float(k), "is_call": is_call,
                         "bid": round(px * 0.98, 4), "ask": round(px * 1.02, 4), "last": px,
                         "volume": 100.0, "open_interest": 1000.0, "iv": 0.99, "iv_filled": False,
                         "tau": tau, "dte": 30})
    return pd.DataFrame(rows)


def test_iv_is_re_solved_from_the_mid_and_the_otm_side_sets_the_strike():
    df = vs.resolve_surface(vs.apply_quotes(_chain()), 100.0, 0.04, 0.01)
    atm = df[df["strike"] == 100.0]
    # The feed said 99%; the mids were priced at 25%.
    assert atm["iv"].iloc[0] == pytest.approx(0.25, abs=0.002)
    assert set(atm["iv_source"]) == {"otm_mid"}
    # Both contracts at a strike carry one IV.
    for _, g in df.groupby("strike"):
        assert g["iv"].nunique() == 1


def test_a_put_call_gap_from_the_rate_disappears_at_the_right_rate():
    """Prices made at r = 4%: solved at 4% the call and put agree; solved at 0%
    the calls read richer, which is the 'chase bid' the flow score scored."""
    df = vs.apply_quotes(_chain())
    right = vs.resolve_surface(df, 100.0, 0.04, 0.01)
    wrong = vs.resolve_surface(df, 100.0, 0.0, 0.01)
    gap = lambda d: float((d[(d.strike == 100) & d.is_call]["iv_mid"].iloc[0]
                           - d[(d.strike == 100) & ~d.is_call]["iv_mid"].iloc[0]) * 100)
    assert abs(gap(right)) < 0.1
    assert gap(wrong) > 1.0


def test_risk_reversal_reads_put_skew_as_positive():
    df = vs.resolve_surface(vs.apply_quotes(_chain()), 100.0, 0.04, 0.01)
    row = vs.expiry_rows(df, 100.0, 0.04, 0.01)[0]
    assert row["rr25_pts"] > 0, "lower strikes carry more IV in the fixture"
    assert row["atm_iv_pct"] == pytest.approx(25.0, abs=0.3)
    # Straddle ~ 0.8 x the one-standard-deviation move, the known identity.
    assert row["straddle_move_pct"] / row["one_sd_move_pct"] == pytest.approx(0.8, abs=0.05)


def test_constant_maturity_interpolates_total_variance():
    rows = [{"tau_years": 20 / 365, "atm_iv_pct": 20.0}, {"tau_years": 40 / 365, "atm_iv_pct": 30.0}]
    cm = vs.constant_maturity(rows, 30)
    expected = np.sqrt((0.2 ** 2 * 20 + (0.3 ** 2 * 40 - 0.2 ** 2 * 20) * 0.5) / 30) * 100
    assert cm["iv_pct"] == pytest.approx(expected, abs=0.01)
    assert not vs.constant_maturity(rows[:1], 30)["available"]


def test_term_structure_names_an_event_only_when_one_is_inside():
    rows = [{"expiry": "2026-10-16", "dte": 4, "tau_years": 4 / 365, "atm_iv_pct": 40.0},
            {"expiry": "2026-10-30", "dte": 18, "tau_years": 18 / 365, "atm_iv_pct": 24.0},
            {"expiry": "2026-11-13", "dte": 32, "tau_years": 32 / 365, "atm_iv_pct": 27.0},
            {"expiry": "2026-12-18", "dte": 67, "tau_years": 67 / 365, "atm_iv_pct": 25.0}]
    vs.mark_events(rows, "2026-11-02")
    term = vs.term_read(rows, "2026-11-02")
    assert term["front"] == "2026-10-30", "a 4-day weekly is not the front"
    assert "2026-11-13" in term["text"]
    move = vs.event_move(rows, "2026-11-02")
    want = np.sqrt(0.27 ** 2 * 32 / 365 - 0.24 ** 2 * 31 / 365) * 100
    assert move["move_pct"] == pytest.approx(want, abs=0.01)


def test_an_after_close_report_on_expiry_day_is_outside_that_expiry():
    rows = [{"expiry": "2026-10-30"}, {"expiry": "2026-11-06"}]
    vs.mark_events(rows, "2026-10-30", after_close=True)
    assert [r["contains_event"] for r in rows] == [False, True]


# --------------------------------------------------------------- the rate

def test_the_rate_comes_from_the_bill_yield_and_says_so(monkeypatch):
    monkeypatch.delenv("RISK_FREE_RATE", raising=False)
    rates.reset_cache()

    class P:
        def history(self, sym, period, interval):
            assert sym == "^IRX"
            return pd.DataFrame({"Close": [4.0, 4.05]}, index=pd.to_datetime(["2026-10-09", "2026-10-12"]))

    out = rates.risk_free(P())
    assert out["rate"] == pytest.approx(0.0405) and out["source"] == "irx"
    assert "13-week Treasury bill" in out["label"]
    rates.reset_cache()

    class Down:
        def history(self, *a, **k):
            raise RuntimeError("feed down")

    assert rates.risk_free(Down())["source"] == "unavailable"
    monkeypatch.setenv("RISK_FREE_RATE", "0.05")
    assert rates.risk_free(Down())["source"] == "setting"
    rates.reset_cache()


# --------------------------------------------------------------- liquidity

def test_liquidity_grades_and_says_why():
    good = liquidity.grade_row({"quote_state": "two_sided", "spread_pct": 3.0, "spread_abs": 0.1,
                                "quote_mid": 3.3, "open_interest": 5000, "volume": 300})
    assert good["grade"] == "good" and good["round_trip_cost"]["per_contract"] == 10.0
    wide = liquidity.grade_row({"quote_state": "two_sided", "spread_pct": 40.0, "spread_abs": 0.4,
                                "quote_mid": 1.0, "open_interest": 5000, "volume": 300})
    assert wide["grade"] == "not_tradable"
    thin = liquidity.grade_row({"quote_state": "two_sided", "spread_pct": 3.0, "spread_abs": 0.1,
                                "quote_mid": 3.3, "open_interest": 20, "volume": 0})
    assert thin["grade"] == "fair" and any("Open interest" in r for r in thin["reasons"])
    nobid = liquidity.grade_row({"quote_state": "no_bid", "open_interest": 5000})
    assert nobid["grade"] == "not_tradable" and "No bid" in nobid["reasons"][0]
    # A nickel-wide quote on a cheap contract is tight whatever its percentage.
    cheap = liquidity.grade_row({"quote_state": "two_sided", "spread_pct": 20.0, "spread_abs": 0.05,
                                 "quote_mid": 0.25, "open_interest": 5000, "volume": 100})
    assert cheap["grade"] == "good"


# --------------------------------------------------------------- positions

R, Q, T = 0.04, 0.0, 30 / 365


def _leg(kind, side, k, qty=1):
    px = float(_bs_vec([100.0], k, T, 0.25, R, Q, kind == "call")[0])
    return {"type": kind, "side": side, "strike": float(k), "mid": px, "bid": px - 0.05,
            "ask": px + 0.05, "iv": 0.25, "tau": T, "qty": qty, "expiry": "2026-11-12"}


def test_a_bull_call_spread_matches_hand_arithmetic():
    legs = [_leg("call", "long", 100), _leg("call", "short", 105)]
    a = position.analyse(legs, 100.0, R, Q)
    debit = (legs[0]["mid"] - legs[1]["mid"]) * 100
    assert a["entry"]["mid"] == pytest.approx(debit, abs=0.01)
    assert a["entry"]["natural"] == pytest.approx((legs[0]["ask"] - legs[1]["bid"]) * 100, abs=0.01)
    assert a["max_profit"] == pytest.approx(500 - debit, abs=0.05)
    assert a["max_loss"] == pytest.approx(-debit, abs=0.05)
    assert a["breakevens_at_expiry"][0] == pytest.approx(100 + debit / 100, abs=0.01)


def test_unbounded_sides_are_said_not_measured():
    assert position.analyse([_leg("call", "short", 105)], 100.0, R, Q)["max_loss_unbounded"]
    assert position.analyse([_leg("call", "long", 105)], 100.0, R, Q)["max_profit_unbounded"]
    put = position.analyse([_leg("put", "short", 95)], 100.0, R, Q)
    assert not put["max_loss_unbounded"]
    assert put["max_loss"] == pytest.approx(-(95 - _leg("put", "short", 95)["mid"]) * 100, abs=0.05)


def test_an_iron_condor_loses_at_most_the_width_minus_the_credit():
    legs = [_leg("put", "long", 90), _leg("put", "short", 95), _leg("call", "short", 105), _leg("call", "long", 110)]
    a = position.analyse(legs, 100.0, R, Q)
    credit = -a["entry"]["mid"]
    assert a["max_profit"] == pytest.approx(credit, abs=0.05)
    assert a["max_loss"] == pytest.approx(-(500 - credit), abs=0.05)
    assert len(a["breakevens_at_expiry"]) == 2


def test_aggregate_greeks_are_per_position_in_dollars():
    a = position.analyse([_leg("call", "long", 100, qty=2)], 100.0, R, Q)
    one = position.analyse([_leg("call", "long", 100)], 100.0, R, Q)
    assert a["greeks"]["delta_shares"] == pytest.approx(2 * one["greeks"]["delta_shares"], abs=0.2)
    assert 45 < one["greeks"]["delta_shares"] < 60      # an ATM call ~ half a share per share
    assert one["greeks"]["theta_per_day"] < 0 < one["greeks"]["vega_per_vol_pt"]


def test_scenarios_at_expiry_equal_the_payoff():
    legs = [_leg("call", "long", 100)]
    a = position.analyse(legs, 100.0, R, Q)
    last = [r for r in a["scenarios"]["rows"] if r["when"] == "at expiry" and r["iv_shift_pts"] == 0][0]
    plus10 = last["pnl"][a["scenarios"]["moves_pct"].index(10)]
    assert plus10 == pytest.approx((110 - 100 - legs[0]["mid"]) * 100, abs=0.05)


def test_max_loss_is_never_called_margin():
    a = position.analyse([_leg("put", "short", 95)], 100.0, R, Q)
    assert any("margin" in x for x in a["assumptions"])


# --------------------------------------------------------------- IV rank

def test_iv_rank_and_percentile_are_defined_and_need_history(monkeypatch, tmp_path):
    monkeypatch.setattr(iv_history, "DB_PATH", str(tmp_path / "iv.db"))
    assert not iv_history.rank_for("ZZZZ", 30.0)["available"]
    # Readings only count in the session window, once per ET day.
    assert not iv_history.record("ZZZZ", 30.0, datetime(2026, 10, 13, 3, 0, tzinfo=ET))
    for i, v in enumerate(range(20, 45)):
        day = pd.Timestamp("2026-08-03") + pd.tseries.offsets.BDay(i)
        assert iv_history.record("ZZZZ", float(v), datetime(day.year, day.month, day.day, 15, 0, tzinfo=ET))
    out = iv_history.rank_for("ZZZZ", 40.0)
    assert out["available"] and out["source"] == "optic_daily" and out["days"] == 25
    assert out["rank"] == pytest.approx((40 - 20) / (44 - 20) * 100, abs=0.1)
    assert out["percentile"] == pytest.approx(20 / 25 * 100, abs=0.1)
    assert "not a full year" in out["note"]


# --------------------------------------------------------------- the page

def test_the_tab_leads_with_pricing_and_offers_research_not_a_pick():
    from pathlib import Path
    app_js = Path(__file__).resolve().parent.parent.joinpath("static", "app.js").read_text()
    swing = app_js[app_js.index("function renderSwing(d) {"):]
    order = [swing.index(x) for x in ("renderPriceHead(d, extQ)", "renderOptionsPricing(d)", "optResearchShellHTML()")]
    assert order == sorted(order)
    shell = app_js[app_js.index("function optResearchShellHTML()"):]
    assert "Nothing here is ranked best" in shell[:1200]
    assert "['IV rank (proxy)'" not in app_js
    assert "No unusual activity" not in app_js
    assert "'Notable contracts'" not in app_js
    ctx = app_js[app_js.index("function chatContextPayload()"):]
    assert "ctx.options_research = optCtx" in ctx[:6000] and "ctx.vol_surface = s.vol_surface" in ctx[:6000]


def test_milo_is_told_how_to_read_the_options_research():
    from app import ai
    flat = " ".join(ai.SYSTEM_PROMPT.lower().split())
    for phrase in ("`p_itm_model`, n(d2), risk-neutral", "not limits on the price",
                   "maximum loss is not the broker's margin", "never call one contract the best",
                   "`sign_note`"):
        assert phrase in flat, phrase


# --------------------------------------------------- textbook reference values

def test_black_scholes_matches_hull_example_15_6():
    """Hull, Options, Futures and Other Derivatives, the S=42 K=40 r=10%
    sigma=20% T=0.5 example: call 4.76, put 0.81; call delta N(d1) = 0.7791."""
    from app.analytics.greeks import bs_price, greeks
    call = float(bs_price(42.0, np.array([40.0]), np.array([0.5]), np.array([0.2]), 0.10, 0.0, True)[0])
    put = float(bs_price(42.0, np.array([40.0]), np.array([0.5]), np.array([0.2]), 0.10, 0.0, False)[0])
    assert call == pytest.approx(4.76, abs=0.005) and put == pytest.approx(0.81, abs=0.005)
    g = greeks(42.0, np.array([40.0]), np.array([0.5]), np.array([0.2]), 0.10, 0.0, np.array([True]))
    assert float(g["delta"][0]) == pytest.approx(0.7791, abs=1e-3)
    # Theta per calendar day and vega per vol point, by finite differences.
    h = 1e-4
    up = float(bs_price(42.0, np.array([40.0]), np.array([0.5 - h]), np.array([0.2]), 0.10, 0.0, True)[0])
    assert float(g["theta"][0]) == pytest.approx((up - call) / h / 365.0, rel=1e-3)
    v_up = float(bs_price(42.0, np.array([40.0]), np.array([0.5]), np.array([0.21]), 0.10, 0.0, True)[0])
    assert float(g["vega"][0]) == pytest.approx(v_up - call, rel=0.02)


def test_greeks_agree_with_finite_differences_with_a_dividend():
    from app.analytics.greeks import bs_price, greeks
    S, K, T, v, r, q = 100.0, 95.0, 0.25, 0.3, 0.04, 0.02
    g = greeks(S, np.array([K]), np.array([T]), np.array([v]), r, q, np.array([False]))
    f = lambda s=S, t=T, vol=v: float(bs_price(s, np.array([K]), np.array([t]), np.array([vol]), r, q, False)[0])
    h = 0.01
    assert float(g["delta"][0]) == pytest.approx((f(S + h) - f(S - h)) / (2 * h), abs=1e-4)
    assert float(g["gamma"][0]) == pytest.approx((f(S + h) - 2 * f() + f(S - h)) / h ** 2, rel=1e-2)
    # Vanna per vol point: d(delta)/d(sigma) / 100.
    dv = 1e-4
    d_up = float(greeks(S, np.array([K]), np.array([T]), np.array([v + dv]), r, q, np.array([False]))["delta"][0])
    d_dn = float(greeks(S, np.array([K]), np.array([T]), np.array([v - dv]), r, q, np.array([False]))["delta"][0])
    assert float(g["vanna"][0]) == pytest.approx((d_up - d_dn) / (2 * dv) / 100.0, rel=1e-3)


def test_iv_solver_round_trips_and_refuses_impossible_prices():
    from app.analytics.vol_surface import solve_iv
    S, r, q = 100.0, 0.04, 0.01
    for vol in (0.05, 0.25, 1.2, 3.0):
        for k, call in ((80, True), (100, True), (120, False), (100, False)):
            px = float(_bs_vec([S], k, 0.2, vol, r, q, call)[0])
            iv = solve_iv(np.array([px]), S, np.array([float(k)]), np.array([0.2]), r, q, np.array([call]))[0]
            fwd_intr = max((S * np.exp(-q * 0.2) - k * np.exp(-r * 0.2)) * (1 if call else -1), 0.0)
            if px - fwd_intr > 0.005:
                assert iv == pytest.approx(vol, rel=2e-3), (vol, k, call)
            else:
                # Priced at intrinsic: the price says nothing about volatility.
                assert np.isnan(iv)
    # Below intrinsic, above the spot, or zero: no IV rather than a made-up one.
    bad = solve_iv(np.array([5.0, 150.0, 0.0]), S, np.array([80.0, 100.0, 100.0]), np.array([0.2] * 3), r, q,
                   np.array([True, True, True]))
    assert np.isnan(bad).all()


def test_an_expiring_contract_has_finite_greeks():
    from app.analytics.greeks import greeks
    g = greeks(100.0, np.array([100.0]), np.array([vs.MIN_TAU]), np.array([0.25]), 0.04, 0.0, np.array([True]))
    assert np.isfinite(g["gamma"][0]) and np.isfinite(g["theta"][0])


def test_a_chain_with_no_quotes_resolves_to_the_feed_iv_flagged():
    df = _chain()
    df["bid"] = 0.0
    df["ask"] = 0.0
    out = vs.resolve_surface(vs.apply_quotes(df), 100.0, 0.04, 0.01)
    assert set(out["iv_source"]) == {"feed"} and (out["iv"] == 0.99).all()
    assert vs.build(out, 100.0, 0.04, 0.01)["expiries"][0]["atm_iv_pct"] is None
