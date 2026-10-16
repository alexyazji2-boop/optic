"""Options risk for linked portfolios (app/brokerage/options_risk.py).

The reference numbers are published ones, not this module's own output read
back. The Greeks are Hull's running example in the chapter on the Greek
letters (J. C. Hull, Options, Futures, and Other Derivatives, ch. 19 in the 9th
and 10th editions, ch. 18 in the 8th): a European call on a non-dividend
stock, S = 49, K = 50, r = 5%, sigma = 20%, T = 20 weeks (0.3846 years), priced
at $2.40, with delta 0.522, gamma 0.066, theta -4.31 a year (-0.0118 per
calendar day) and vega 12.1 per 100% of volatility (0.121 per point). The
institution in that example has sold calls on 100,000 shares and Hull gives its
position delta as -0.522 x 100,000 = -52,200. The European prices are Hull's
Example 15.6 (S = 42, K = 40, r = 10%, sigma = 20%, T = 0.5): call 4.76, put
0.81.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from app.analytics import american, greeks as greeks_mod, vol_surface
from app.brokerage import options_risk as orisk

YEAR = 365.0 * 86400.0
HULL_T = 20.0 / 52.0


def _now_for(expiry: str, tau_years: float) -> datetime:
    """The instant `tau_years` before the 4:00pm ET close on `expiry`, so the
    module's clock gives exactly that time to expiry."""
    return (vol_surface.expiry_close(expiry) - timedelta(seconds=tau_years * YEAR)).astimezone(timezone.utc)


def _opt(underlying="XYZ", occ=None, option_type="call", strike=50.0, expiry="2027-03-05", contracts=1,
         multiplier=100, price=2.40, mini=False, currency="USD", **kw):
    occ = occ or "{:<6}{}{}{:08d}".format(underlying, expiry[2:4] + expiry[5:7] + expiry[8:10],
                                         "C" if option_type == "call" else "P", int(round(strike * 1000)))
    d = {"underlying": underlying, "occ": occ, "option_type": option_type, "strike": strike, "expiry": expiry,
         "contracts": contracts, "multiplier": multiplier, "multiplier_assumed": multiplier is None, "mini": mini,
         "price": price, "currency": currency, "account": "Brokerage"}
    d.update(kw)
    return d


def _spots(**prices):
    return lambda s: ({"price": prices[s], "as_of": None, "source": "test", "delayed_minutes": 15}
                      if s in prices else None)


NO_DIV = staticmethod(lambda s: {"yield": 0.0, "next_ex_date": None})


def _build(opts, spots, rate=0.05, now=None, shares=None, div=None):
    return orisk.build(opts, shares or {}, spots, {"rate": rate, "source": "test", "as_of": None},
                       div or (lambda s: {"yield": 0.0, "next_ex_date": None}), now)


# ------------------------------------------------------------ textbook Greeks

def test_greeks_match_hulls_published_example():
    now = _now_for("2027-03-05", HULL_T)
    out = _build([_opt(price=2.40)], _spots(XYZ=49.0), now=now)
    leg = out["positions"][0]
    assert leg["greeks_available"] is True
    # Hull prints the price to the cent; the vol that reproduces $2.40 is 20%.
    assert leg["iv"] == pytest.approx(0.20, abs=0.001)
    ps = leg["per_share"]
    assert ps["delta"] == pytest.approx(0.522, abs=0.001)
    assert ps["gamma"] == pytest.approx(0.066, abs=0.001)
    assert ps["theta"] == pytest.approx(-4.31 / 365.0, abs=0.0002)
    assert ps["theta"] == pytest.approx(-0.0118, abs=0.0002)
    assert ps["vega"] == pytest.approx(0.121, abs=0.001)
    # Scaled for one standard contract: x 100 shares.
    assert leg["delta_shares"] == pytest.approx(52.2, abs=0.1)
    assert leg["theta_per_day"] == pytest.approx(-1.18, abs=0.02)
    assert leg["vega_per_vol_point"] == pytest.approx(12.1, abs=0.1)
    assert leg["notional"] == pytest.approx(4900.0)


def test_a_short_call_has_negative_delta_like_hulls_institution():
    # Hull's institution sold calls on 100,000 shares: 1,000 contracts short.
    now = _now_for("2027-03-05", HULL_T)
    out = _build([_opt(contracts=-1000, price=2.40)], _spots(XYZ=49.0), now=now)
    leg = out["positions"][0]
    assert leg["side"] == "short"
    assert leg["delta_shares"] == pytest.approx(-52200.0, abs=100.0)
    assert leg["dollar_delta"] == pytest.approx(-52200.0 * 49.0, rel=0.002)
    # Short options earn time decay and lose when volatility rises.
    assert leg["theta_per_day"] > 0 and leg["vega_per_vol_point"] < 0
    assert leg["gamma_shares_per_dollar"] < 0
    assert "positive delta means the position gains when the underlying rises" in out["sign_convention"].lower()


def test_signs_of_the_four_basic_positions():
    now = _now_for("2027-03-05", HULL_T)
    put_price = float(greeks_mod.bs_price(49.0, np.array([50.0]), np.array([HULL_T]), np.array([0.2]),
                                          0.05, 0.0, False)[0])
    legs = [_opt(contracts=1, price=2.40, occ="XYZ   270305C00050000"),
            _opt(contracts=-1, price=2.40, occ="XYZ   270305C00050001"),
            _opt(option_type="put", contracts=1, price=put_price),
            _opt(option_type="put", contracts=-1, price=put_price, occ="XYZ   270305P00050001")]
    out = _build(legs, _spots(XYZ=49.0), now=now)
    by = {(p["option_type"], p["side"]): p["delta_shares"] for p in out["positions"]}
    assert by[("call", "long")] > 0 and by[("call", "short")] < 0
    assert by[("put", "long")] < 0 and by[("put", "short")] > 0


def test_iv_round_trips_on_the_american_price_for_an_equity_put():
    # An in-the-money American put while rates are positive: early exercise is
    # worth something, so the solve must be on the American price.
    expiry, tau, true_vol = "2027-01-15", 0.5, 0.35
    now = _now_for(expiry, tau)
    price = float(american.baw(100.0, 110.0, tau, true_vol, 0.04, 0.01, False))
    out = _build([_opt(underlying="ABC", option_type="put", strike=110.0, expiry=expiry, price=price)],
                 _spots(ABC=100.0), rate=0.04, now=now,
                 div=lambda s: {"yield": 0.01, "next_ex_date": None})
    leg = out["positions"][0]
    assert leg["exercise"] == "american" and leg["settlement"] == "physical"
    assert leg["iv"] == pytest.approx(true_vol, abs=0.002)


def test_iv_round_trips_on_hulls_european_prices_for_an_index_root():
    expiry = "2027-01-15"
    now = _now_for(expiry, 0.5)
    legs = [_opt(underlying="SPX", occ="SPXW  270115C00040000", strike=40.0, expiry=expiry, price=4.76),
            _opt(underlying="SPX", occ="SPXW  270115P00040000", option_type="put", strike=40.0, expiry=expiry,
                 price=0.81)]
    out = _build(legs, _spots(SPX=42.0), rate=0.10, now=now)
    for leg in out["positions"]:
        assert leg["exercise"] == "european" and leg["settlement"] == "cash"
        assert leg["iv"] == pytest.approx(0.20, abs=0.002)
    assert any(c["kind"] == "settlement" and c["settlement"] == "cash" for c in out["considerations"])


# ------------------------------------------------------------ multipliers

def test_a_mini_uses_ten_shares_a_contract():
    now = _now_for("2027-03-05", HULL_T)
    mini = _opt(underlying="SPY", occ="SPY7  270305C00050000", mini=True, multiplier=10, contracts=3, price=2.40)
    out = _build([mini], _spots(SPY=49.0), now=now)
    leg = out["positions"][0]
    assert leg["multiplier"] == 10 and leg["mini"] and not leg["adjusted"]
    assert leg["delta_shares"] == pytest.approx(leg["per_share"]["delta"] * 3 * 10, abs=0.01)
    assert leg["notional"] == pytest.approx(3 * 10 * 49.0)
    assert out["by_underlying"][0]["option_delta_shares"] == pytest.approx(0.5216 * 30, abs=0.02)


def test_a_missing_multiplier_is_assumed_and_said():
    now = _now_for("2027-03-05", HULL_T)
    out = _build([_opt(underlying="SPY", occ="SPY7  270305C00050000", mini=True, multiplier=None, price=2.40),
                  _opt(multiplier=None, price=2.40)], _spots(SPY=49.0, XYZ=49.0), now=now)
    legs = {p["underlying"]: p for p in out["positions"]}
    assert legs["SPY"]["multiplier"] == 10 and legs["SPY"]["multiplier_assumed"]
    assert legs["XYZ"]["multiplier"] == 100 and legs["XYZ"]["multiplier_assumed"]
    assert any("assumed" in n for n in legs["XYZ"]["notes"])
    assert any("assumed" in s for s in out["limitations"])


def test_an_adjusted_contract_is_excluded_from_every_total():
    now = _now_for("2027-03-05", HULL_T)
    standard = _opt(underlying="TSLA", contracts=1, price=2.40)
    adjusted = _opt(underlying="TSLA", occ="TSLA1 270305C00050000", contracts=5, price=2.40)
    odd = _opt(underlying="TSLA", occ="TSLA  270305C00055000", strike=55.0, contracts=2, multiplier=150, price=1.0)
    out = _build([standard, adjusted, odd], _spots(TSLA=49.0), now=now)
    legs = {p["occ"]: p for p in out["positions"]}
    assert legs[adjusted["occ"]]["adjusted"] and not legs[adjusted["occ"]]["in_aggregates"]
    assert legs[adjusted["occ"]]["delta_shares"] is None
    assert "TSLA1" in legs[adjusted["occ"]]["adjusted_reason"]
    assert legs[odd["occ"]]["adjusted"], "a 150-share multiplier is a non-standard deliverable"
    row = out["by_underlying"][0]
    assert row["legs"] == 1
    assert row["option_delta_shares"] == pytest.approx(legs[standard["occ"]]["delta_shares"])
    assert row["premium_value"] == pytest.approx(240.0)
    assert {e["occ"] for e in out["excluded"]} == {adjusted["occ"], odd["occ"]}
    assert out["coverage"]["adjusted"] == 2
    assert sum(b["legs"] for b in out["expiry_buckets"][0]["buckets"]) == 1


# ------------------------------------------------------------ scaled figures

def test_dollar_gamma_by_hand_and_against_a_repriced_one_percent_move():
    now = _now_for("2027-03-05", HULL_T)
    out = _build([_opt(contracts=2, price=2.40)], _spots(XYZ=49.0), now=now)
    leg = out["positions"][0]
    g = leg["per_share"]["gamma"]
    # The stated formula: 0.5 x gamma x (0.01 x spot)^2 x contracts x multiplier.
    assert leg["dollar_gamma_1pct"] == pytest.approx(0.5 * g * (0.01 * 49.0) ** 2 * 2 * 100, abs=0.01)
    # By hand from Hull's gamma of 0.066: 0.5 x 0.066 x 0.49^2 x 200 = 1.58.
    assert leg["dollar_gamma_1pct"] == pytest.approx(1.58, abs=0.02)
    # Independent: reprice at +1% and -1%. The delta terms cancel in the
    # average, leaving the curvature that dollar gamma estimates.
    def v(s):
        return float(greeks_mod.bs_price(s, np.array([50.0]), np.array([HULL_T]), np.array([leg["iv"]]),
                                         0.05, 0.0, True)[0])
    convexity = (v(49.0 * 1.01) + v(49.0 * 0.99) - 2 * v(49.0)) / 2.0 * 200
    assert leg["dollar_gamma_1pct"] == pytest.approx(convexity, rel=0.02)


def test_net_delta_adds_the_shares_held_directly():
    now = _now_for("2027-03-05", HULL_T)
    out = _build([_opt(contracts=-1, price=2.40)], _spots(XYZ=49.0), now=now, shares={"XYZ": 100})
    row = out["by_underlying"][0]
    opt = out["positions"][0]["delta_shares"]
    assert row["stock_shares"] == 100
    assert row["net_delta_shares"] == pytest.approx(100 + opt, abs=0.01)
    assert row["net_delta_shares"] == pytest.approx(100 - 52.16, abs=0.1)
    assert row["net_dollar_delta"] == pytest.approx((100 - 52.16) * 49.0, abs=5.0)
    assert out["totals_by_currency"]["USD"]["net_dollar_delta"] == pytest.approx(row["net_dollar_delta"])


def test_currencies_are_never_summed_together():
    now = _now_for("2027-03-05", HULL_T)
    out = _build([_opt(price=2.40), _opt(underlying="RY", currency="CAD", price=2.40)],
                 _spots(XYZ=49.0, RY=49.0), now=now)
    assert set(out["totals_by_currency"]) == {"USD", "CAD"}
    assert {b["currency"] for b in out["expiry_buckets"]} == {"USD", "CAD"}


# ------------------------------------------------------------ never invent a vol

def test_missing_zero_and_sub_intrinsic_prices_get_no_greeks_and_say_why():
    now = _now_for("2027-03-05", HULL_T)
    legs = [_opt(price=None, occ="XYZ   270305C00050000"),
            _opt(price=0.0, occ="XYZ   270305C00050001"),
            _opt(strike=40.0, price=5.0, occ="XYZ   270305C00040000")]       # intrinsic is 9.00
    out = _build(legs, _spots(XYZ=49.0), now=now)
    for p in out["positions"]:
        assert p["iv"] is None and p["greeks_available"] is False and p["delta_shares"] is None
        assert p["greeks_reason"]
    reasons = " ".join(p["greeks_reason"] for p in out["positions"])
    assert "no price" in reasons and "zero" in reasons and "below intrinsic" in reasons
    row = out["by_underlying"][0]
    # No leg priced: the option figures are absent, not zero.
    assert row["option_delta_shares"] is None and row["net_delta_shares"] is None
    assert row["complete"] is False


def test_a_missing_quote_is_never_shown_as_current():
    now = _now_for("2027-03-05", HULL_T)
    out = _build([_opt(price=2.40)], _spots(), now=now)
    leg = out["positions"][0]
    assert leg["spot"] is None and leg["notional"] is None and leg["itm"] is None
    assert "No current quote" in leg["greeks_reason"]
    assert out["freshness"]["underlyings"][0]["note"].startswith("No current quote")


def test_net_delta_is_withheld_when_one_leg_cannot_be_priced():
    now = _now_for("2027-03-05", HULL_T)
    out = _build([_opt(price=2.40), _opt(strike=40.0, price=None, occ="XYZ   270305C00040000", contracts=-3)],
                 _spots(XYZ=49.0), now=now, shares={"XYZ": 100})
    row = out["by_underlying"][0]
    assert row["net_delta_shares"] is None and row["net_dollar_delta"] is None
    assert row["partial"]["legs_left_out"] == 1
    assert row["partial"]["net_delta_shares"] == pytest.approx(100 + 52.16, abs=0.1)
    assert out["totals_by_currency"]["USD"]["net_dollar_delta"] is None


# ------------------------------------------------------------ expiry buckets

def test_bucket_edges():
    assert [orisk._bucket(d) for d in (0, 7, 8, 30, 31, 90, 91, 400)] == [
        "0-7 days", "0-7 days", "8-30 days", "8-30 days", "31-90 days", "31-90 days", "91+ days", "91+ days"]
    assert orisk._bucket(-1) is None


def test_expiry_buckets_by_premium_and_concentration():
    now = datetime(2026, 10, 15, 15, 0, tzinfo=timezone.utc)       # Thursday, 11:00 ET
    # Premiums by hand: 1 x 1.00 x 100 = 100; 2 x 1.00 x 100 = 200;
    # 5 x 2.00 x 100 = 1,000 (a short, counted by size); 3 x 1.00 x 100 = 300.
    legs = [_opt(underlying="AAA", strike=100.0, expiry="2026-10-18", contracts=1, price=1.0),     # 3 days
            _opt(underlying="AAA", strike=100.0, expiry="2026-11-04", contracts=2, price=1.0),     # 20 days
            _opt(underlying="AAA", strike=100.0, expiry="2026-12-14", contracts=-5, price=2.0),    # 60 days
            _opt(underlying="AAA", strike=100.0, expiry="2027-05-03", contracts=3, price=1.0)]     # 200 days
    out = _build(legs, _spots(), now=now)
    b = {x["label"]: x for x in out["expiry_buckets"][0]["buckets"]}
    assert [b[k]["premium_value"] for k in ("0-7 days", "8-30 days", "31-90 days", "91+ days")] == [
        100.0, 200.0, 1000.0, 300.0]
    assert b["31-90 days"]["premium_pct"] == pytest.approx(62.5)
    assert out["expiry_buckets"][0]["concentrated_in"] == "31-90 days"
    assert "62.5%" in out["expiry_buckets"][0]["flag"]


def test_no_flag_when_no_bucket_holds_more_than_half():
    now = datetime(2026, 10, 15, 15, 0, tzinfo=timezone.utc)
    legs = [_opt(underlying="AAA", strike=100.0, expiry="2026-10-18", contracts=1, price=1.0),
            _opt(underlying="AAA", strike=100.0, expiry="2026-11-04", contracts=1, price=1.0)]
    out = _build(legs, _spots(), now=now)
    assert out["expiry_buckets"][0]["concentrated_in"] is None and out["expiry_buckets"][0]["flag"] is None


def test_dollar_delta_buckets_add_to_one_hundred():
    now = datetime(2026, 10, 15, 15, 0, tzinfo=timezone.utc)
    legs = [_opt(underlying="AAA", strike=100.0, expiry="2026-10-23", contracts=1, price=2.5),
            _opt(underlying="AAA", strike=100.0, expiry="2027-01-15", contracts=-2, price=6.0)]
    out = _build(legs, _spots(AAA=100.0), now=now)
    rows = out["expiry_buckets"][0]["buckets"]
    dd = [abs(p["dollar_delta"]) for p in out["positions"]]
    assert sum(r["abs_dollar_delta"] for r in rows) == pytest.approx(sum(dd), abs=0.02)
    assert sum(r["abs_dollar_delta_pct"] or 0 for r in rows) == pytest.approx(100.0, abs=0.02)


# ------------------------------------------------------------ considerations

def test_assignment_dividend_zero_dte_and_worthless_considerations():
    now = datetime(2026, 10, 15, 15, 0, tzinfo=timezone.utc)       # 11:00 ET
    legs = [
        # Short call in the money, 1 day left: assignment risk.
        _opt(underlying="AAPL", strike=240.0, expiry="2026-10-16", contracts=-2, price=12.5),
        # Short in-the-money call over an ex-date with 0.10 of time value
        # against a 0.26 dividend: early assignment.
        _opt(underlying="AAPL", strike=200.0, expiry="2026-12-18", contracts=-1, price=52.10),
        # Long out-of-the-money call expiring today.
        _opt(underlying="AAPL", strike=260.0, expiry="2026-10-15", contracts=1, price=0.05),
    ]
    out = _build(legs, _spots(AAPL=252.0), rate=0.04, now=now,
                 div=lambda s: {"yield": 0.004, "next_ex_date": "2026-11-10", "amount": 0.26})
    kinds = {(c["kind"], c["occ"]) for c in out["considerations"]}
    assert ("assignment_risk", legs[0]["occ"]) in kinds
    assert ("early_assignment_dividend", legs[1]["occ"]) in kinds
    assert ("expires_today", legs[2]["occ"]) in kinds
    assert ("may_expire_worthless", legs[2]["occ"]) in kinds
    assert ("settlement", None) in kinds
    # Not raised for the 1-day call: the ex-date is after its expiry.
    assert ("early_assignment_dividend", legs[0]["occ"]) not in kinds
    assert out["considerations"][0]["severity"] == "high"


def test_a_cash_settled_short_is_not_described_as_assignable_early():
    now = datetime(2026, 10, 15, 15, 0, tzinfo=timezone.utc)
    leg = _opt(underlying="SPX", occ="SPXW  261019P06100000", option_type="put", strike=6100.0,
               expiry="2026-10-19", contracts=-1, price=110.0)
    out = _build([leg], _spots(SPX=6000.0), rate=0.04, now=now)
    risk = [c for c in out["considerations"] if c["kind"] == "assignment_risk"]
    assert risk and "settles in cash" in risk[0]["text"] and "not assigned early" in risk[0]["text"]


# ------------------------------------------------------------ freshness

def test_trading_minutes_count_only_the_regular_session():
    et = vol_surface.ET
    fri = datetime(2026, 10, 9, 15, 30, tzinfo=et)
    mon = datetime(2026, 10, 12, 9, 45, tzinfo=et)
    assert orisk.trading_minutes_between(fri, mon) == pytest.approx(30 + 15)
    same = datetime(2026, 10, 14, 10, 0, tzinfo=et)
    assert orisk.trading_minutes_between(same, same + timedelta(minutes=50)) == pytest.approx(50)


def test_freshness_flags_an_option_price_more_than_an_hour_of_trading_old():
    now = datetime(2026, 10, 15, 15, 0, tzinfo=timezone.utc)       # 11:00 ET, market open
    spot = lambda s: {"price": 100.0, "as_of": "2026-10-15T14:45:00Z", "source": "yahoo", "delayed_minutes": 15}
    old = _opt(underlying="AAA", strike=100.0, expiry="2026-11-20", price=3.0,
               price_as_of="2026-10-14T19:30:00Z")                 # 3:30pm ET the day before: 105 minutes
    fresh = _opt(underlying="BBB", strike=100.0, expiry="2026-11-20", price=3.0,
                 price_as_of="2026-10-15T14:15:00Z")                # 30 minutes
    out = orisk.build([old, fresh], {}, spot, {"rate": 0.04}, lambda s: {"yield": 0.0}, now)
    rows = {r["underlying"]: r for r in out["freshness"]["underlyings"]}
    assert rows["AAA"]["trading_minutes_apart"] == 105 and rows["AAA"]["flagged"]
    assert rows["BBB"]["trading_minutes_apart"] == 30 and not rows["BBB"]["flagged"]
    assert rows["AAA"]["spot_delayed_minutes"] == 15 and rows["AAA"]["spot_source"] == "yahoo"
    assert out["freshness"]["market_open"] is True
    assert "broker" in out["freshness"]["statement"] and "spot" in out["freshness"]["statement"]


def test_an_unknown_price_time_is_said():
    now = datetime(2026, 10, 15, 15, 0, tzinfo=timezone.utc)
    out = _build([_opt(underlying="AAA", strike=100.0, expiry="2026-11-20", price=3.0)], _spots(AAA=100.0), now=now)
    assert "not known" in out["freshness"]["underlyings"][0]["note"]


# ------------------------------------------------------------ the envelope

def test_units_version_and_limitations_are_stated():
    now = _now_for("2027-03-05", HULL_T)
    out = _build([_opt(price=2.40)], _spots(XYZ=49.0), now=now)
    assert out["version"] == "options-risk-2026-10-15.1"
    for k in ("delta_shares", "dollar_delta", "gamma_shares_per_dollar", "dollar_gamma_1pct", "theta_per_day",
              "vega_per_vol_point", "notional", "iv"):
        assert k in out["units"]
    assert "0.5 x gamma x (0.01 x spot)^2" in out["units"]["dollar_gamma_1pct"]
    assert any("not paired" in s for s in out["limitations"])
    assert out["method"]


def test_no_options_is_said_plainly():
    out = orisk.build([], {}, lambda s: None, None, lambda s: None, datetime.now(timezone.utc))
    assert out["available"] is False and out["reason"]


def test_no_em_dashes_in_reader_facing_text():
    now = datetime(2026, 10, 15, 15, 0, tzinfo=timezone.utc)
    legs = [_opt(underlying="AAPL", strike=240.0, expiry="2026-10-16", contracts=-2, price=12.5),
            _opt(underlying="TSLA", occ="TSLA1 261218C00250000", strike=250.0, expiry="2026-12-18", price=10.0),
            _opt(underlying="SPX", occ="SPX   261120P05500000", option_type="put", strike=5500.0,
                 expiry="2026-11-20", contracts=-1, price=40.0)]
    out = _build(legs, _spots(AAPL=252.0, SPX=6000.0), now=now)
    assert "—" not in repr(out)
