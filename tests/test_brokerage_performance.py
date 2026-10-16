"""Brokerage performance (app/brokerage/performance.py), checked against
reference figures worked out independently of the module: Excel's documented
XIRR example, returns computed by hand on paper, a benchmark total return
reinvested by hand, and an attribution whose remainder is explained trade by
trade. A test that only compared the module with itself would pass a wrong
formula as readily as a right one.
"""

from __future__ import annotations

import math
from dataclasses import asdict
from datetime import date

import pytest

from app.brokerage import performance as P
from app.brokerage.providers import SANDBOX_ACTIVITIES, SandboxProvider, _sandbox_activity


# ----------------------------------------------------------------- helpers


def acct(aid, name=None, ccy="USD", **kw):
    return dict({"id": aid, "name": name or aid, "currency": ccy, "transactions_first_date": None,
                 "activities_state": "ok", "history_state": "ok"}, **kw)


def act(kind, day, amount=None, ccy="USD", **kw):
    return dict({"id": "{}-{}-{}".format(kind, day, amount), "type": kind, "trade_date": day,
                 "settlement_date": day, "amount": amount, "currency": ccy}, **kw)


def hist(*points, ccy="USD"):
    return {"currency": ccy, "points": [list(p) for p in points]}


def run(accounts, activities, histories, today, period="all", snapshots=(), current=None, benchmark=None):
    return P.build(accounts, activities, histories, list(snapshots), current or {}, benchmark,
                   date.fromisoformat(today), period)


def own_irr(flows):
    """An XIRR written separately from the module's: plain bisection on the
    365-day NPV, used only to check the module's answer."""
    t0 = min(d for d, _ in flows)

    def npv(r):
        return sum(a / (1 + r) ** ((d - t0).days / 365.0) for d, a in flows)

    lo, hi = -0.99, 10.0
    for _ in range(300):
        mid = (lo + hi) / 2
        if (npv(mid) > 0) == (npv(lo) > 0):
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from strings(v)


# --------------------------------------------------------------- XIRR


def test_xirr_matches_excels_documented_example():
    # Microsoft's XIRR help page: these five flows return 0.373362535.
    flows = [(date(2008, 1, 1), -10000), (date(2008, 3, 1), 2750), (date(2008, 10, 30), 4250),
             (date(2009, 2, 15), 3250), (date(2009, 4, 1), 2750)]
    got = P.xirr(flows)
    assert got["converged"] is True
    assert abs(got["rate"] - 0.373362535) < 1e-6


def test_the_same_example_through_build_as_a_start_value_withdrawals_and_an_end_value():
    # The account is worth 10,000 on 2008-01-01, pays out three withdrawals and
    # is worth 2,750 on 2009-04-01: the investor's flows are Excel's.
    out = run([acct("a")], {"a": [act("WITHDRAWAL", "2008-03-01", -2750), act("WITHDRAWAL", "2008-10-30", -4250),
                                  act("WITHDRAWAL", "2009-02-15", -3250)]},
              {"a": hist(("2008-01-01", 10000), ("2009-04-01", 2750))}, "2009-04-01")
    mwr = out["returns"]["mwr"]
    assert mwr["converged"] is True and mwr["irr_annualized_pct"] == 37.34
    # Period figure: (1 + irr) ** (456 / 365) - 1, 456 days from 2008-01-01 (a leap year).
    assert mwr["period_pct"] == round(100 * (1.373362535 ** (456 / 365) - 1), 2)
    # The time-weighted return across that single 456-day gap is Modified
    # Dietz, by hand: numerator 2,750 - 10,000 + 10,250 = 3,000; the flows sit
    # 60, 303 and 411 days in, so the weights are 396/456, 153/456, 45/456 and
    # the denominator is 10,000 - (2,750*396 + 4,250*153 + 3,250*45)/456.
    denom = 10000 - (2750 * 396 + 4250 * 153 + 3250 * 45) / 456
    twr = out["returns"]["twr"]
    assert twr["pct"] == round(100 * 3000 / denom, 2) == 51.15
    assert twr["annualized"] is True and twr["covered_days"] == 456
    assert twr["annualized_pct"] == round(100 * ((1 + 3000 / denom) ** (365 / 456) - 1), 2)


def test_xirr_says_it_did_not_converge_rather_than_inventing_a_rate():
    assert P.xirr([(date(2026, 1, 1), 100), (date(2026, 2, 1), 50)]) == {
        "rate": None, "converged": False, "method": "needs money both in and out"}
    # +15% in two days is far above +1000% a year: outside the bracket, no rate.
    got = P.xirr([(date(2026, 1, 1), -1000), (date(2026, 1, 3), 1150)])
    assert got["rate"] is None and got["converged"] is False


# ------------------------------------------------------- time-weighted


def test_two_day_twr_with_a_mid_period_deposit_by_hand():
    # Day 1: 1,000 grows 10% to 1,100 and a 500 deposit lands at the end of the
    # day: 1,600. Day 2: +5%, 1,680. TWR = 1.10 * 1.05 - 1 = 15.5%. A single
    # Dietz over both days would say 180 / 1,250 = 14.4%, which is why the
    # days are chained.
    out = run([acct("a")], {"a": [act("CONTRIBUTION", "2026-03-03", 500)]},
              {"a": hist(("2026-03-02", 1000), ("2026-03-03", 1600), ("2026-03-04", 1680))}, "2026-03-04")
    twr = out["returns"]["twr"]
    assert twr["pct"] == 15.50
    assert twr["annualized"] is False and twr["annualized_pct"] is None
    assert [r["cum_twr_pct"] for r in out["series"]] == [0.0, 10.0, 15.5]
    assert [r["net_flow"] for r in out["series"]] == [0.0, 500.0, 0.0]
    assert out["period"]["measured_start"] == "2026-03-02" and out["period"]["measured_end"] == "2026-03-04"
    assert any("not annualised" in s for s in out["limitations"])
    # Two days is too short for a money-weighted rate inside the solver's bracket,
    # and the output says so rather than printing a number.
    assert out["returns"]["mwr"]["irr_annualized_pct"] is None
    assert any("noisy" in s for s in out["limitations"])


def test_modified_dietz_across_a_gap_by_hand():
    # 10,000 on 2026-03-01, a 2,000 deposit on 2026-03-11, 12,500 on 2026-03-31.
    # 30-day gap, the deposit has 20 of them left: weight 20/30.
    # (12,500 - 10,000 - 2,000) / (10,000 + 2,000 * 2/3) = 500 / 11,333.33 = 4.4118%.
    assert P.modified_dietz(10000, 12500, [(date(2026, 3, 11), 2000)], date(2026, 3, 1),
                            date(2026, 3, 31)) == pytest.approx(0.04411764705882353, abs=1e-12)
    out = run([acct("a")], {"a": [act("CONTRIBUTION", "2026-03-11", 2000)]},
              {"a": hist(("2026-03-01", 10000), ("2026-03-31", 12500))}, "2026-03-31")
    assert out["returns"]["twr"]["pct"] == 4.41
    assert out["sources"]["gaps"] == [{"from": "2026-03-01", "to": "2026-03-31", "days": 30}]
    assert any("Modified Dietz" in s for s in out["limitations"])


def test_a_deposit_before_a_fall_separates_twr_from_mwr():
    # 10,000 doubles to 20,000 by 2025-07-01, when 100,000 more goes in
    # (120,000). Then everything halves: 60,000 on 2026-01-01.
    # TWR: 2.0 * 0.5 - 1 = 0%. The investments ended where they started.
    # MWR: 110,000 went in and 60,000 is left, most of it lost after the big
    # deposit, so the reader's money did badly. Both are true, which is why
    # both are reported and only the TWR is set against a benchmark.
    out = run([acct("a")], {"a": [act("CONTRIBUTION", "2025-07-01", 100000)]},
              {"a": hist(("2025-01-01", 10000), ("2025-07-01", 120000), ("2026-01-01", 60000))}, "2026-01-01")
    r = out["returns"]
    assert r["twr"]["pct"] == 0.0 and r["twr"]["annualized"] is True and r["twr"]["annualized_pct"] == 0.0
    # Newton from 10% overshoots below -99% on these flows; the bisection
    # fallback is what solves them.
    assert P.xirr([(date(2025, 1, 1), -10000), (date(2025, 7, 1), -100000), (date(2026, 1, 1), 60000)])[
        "method"] == "bisection"
    expect = own_irr([(date(2025, 1, 1), -10000), (date(2025, 7, 1), -100000), (date(2026, 1, 1), 60000)])
    assert -0.75 < expect < -0.6
    assert r["mwr"]["converged"] is True
    assert r["mwr"]["irr_annualized_pct"] == round(100 * expect, 2)
    assert r["mwr"]["period_pct"] == round(100 * expect, 2)          # exactly 365 days


def test_empty_days_before_the_first_deposit_are_not_a_return():
    # The provider's history opens at zero; the 1,000 deposit lands on 03-04
    # (inside that day's value), then +10%. Measured from the first day with
    # money in it: 10%, not "unmeasurable".
    out = run([acct("a")], {"a": [act("CONTRIBUTION", "2026-03-04", 1000)]},
              {"a": hist(("2026-03-02", 0), ("2026-03-03", 0), ("2026-03-04", 1000), ("2026-03-05", 1100))},
              "2026-03-05")
    assert out["period"]["measured_start"] == "2026-03-04"
    assert out["returns"]["twr"]["pct"] == 10.0 and out["returns"]["twr"]["excluded"] == []


def test_returns_start_where_history_does_and_say_so():
    out = run([acct("a")], {"a": []}, {"a": hist(("2026-06-01", 100), ("2026-06-02", 101))}, "2026-06-02",
              period="1y")
    assert out["period"]["start"] == "2025-06-02" and out["period"]["measured_start"] == "2026-06-01"
    assert any("Values begin on 2026-06-01" in s for s in out["limitations"])


# ------------------------------------------------------ internal transfers


def two_accounts(out_kind="WITHDRAWAL", out_amt=-1000, out_day="2026-05-01", in_kind="CONTRIBUTION",
                 in_amt=1000, in_day="2026-05-03"):
    return {"a": [act(out_kind, out_day, out_amt)], "b": [act(in_kind, in_day, in_amt)]}


def test_an_outflow_and_an_inflow_between_accounts_in_view_are_one_internal_transfer():
    # Reported as WITHDRAWAL and CONTRIBUTION, two days apart.
    out = run([acct("a"), acct("b")], two_accounts(), {}, "2026-05-10")
    f = out["flows"]
    assert f["internal_transfers"]["matched"] == 1
    assert f["internal_transfers"]["pairs"][0]["from"] == "a" and f["internal_transfers"]["pairs"][0]["to"] == "b"
    assert f["deposits"] == 0.0 and f["withdrawals"] == 0.0 and f["net_external"] == 0.0
    # Within 0.1% (a wire fee) still matches.
    assert run([acct("a"), acct("b")], two_accounts(in_amt=999.50), {}, "2026-05-10")[
        "flows"]["internal_transfers"]["matched"] == 1


def test_one_account_in_view_matches_nothing():
    out = run([acct("a")], two_accounts(), {}, "2026-05-10")
    assert out["flows"]["internal_transfers"]["matched"] == 0
    assert out["flows"]["withdrawals"] == 1000.0


def test_different_amounts_or_too_far_apart_are_not_matched():
    differ = run([acct("a"), acct("b")], two_accounts(in_amt=990), {}, "2026-05-10")["flows"]
    assert differ["internal_transfers"]["matched"] == 0
    assert differ["deposits"] == 990.0 and differ["withdrawals"] == 1000.0
    late = run([acct("a"), acct("b")], two_accounts(in_day="2026-05-05"), {}, "2026-05-10")["flows"]
    assert late["internal_transfers"]["matched"] == 0


def test_money_out_and_back_into_the_same_account_is_not_an_internal_transfer():
    # A returned withdrawal: both legs in one account, with a second account in
    # view. Money did leave and come back, so both are external flows.
    acts = {"a": [act("WITHDRAWAL", "2026-05-01", -1000), act("CONTRIBUTION", "2026-05-02", 1000)], "b": []}
    f = run([acct("a"), acct("b")], acts, {}, "2026-05-10")["flows"]
    assert f["internal_transfers"]["matched"] == 0
    assert f["deposits"] == 1000.0 and f["withdrawals"] == 1000.0


def test_days_in_transit_are_neither_a_loss_nor_a_gain():
    # a: 2,000 -> sends 1,000 on 05-01 -> 1,000 -> grows 10% on 05-02 -> 1,100.
    # b: 1,000 -> receives the 1,000 on 05-03 -> 2,000.
    # In view: 3,000, 2,000, 2,100, 3,100. By hand the only return is a's 10% on
    # 1,000 of the 2,000 in view on 05-02: +5%. Counted as a loss and a gain it
    # would be 2/3 * 1.05 * 31/21 - 1 = +3.33%.
    acts = {"a": [act("TRANSFER", "2026-05-01", -1000)], "b": [act("TRANSFER", "2026-05-03", 1000)]}
    hists = {"a": hist(("2026-04-30", 2000), ("2026-05-01", 1000), ("2026-05-02", 1100), ("2026-05-03", 1100)),
             "b": hist(("2026-04-30", 1000), ("2026-05-01", 1000), ("2026-05-02", 1000), ("2026-05-03", 2000))}
    out = run([acct("a"), acct("b")], acts, hists, "2026-05-03")
    assert out["flows"]["internal_transfers"]["matched"] == 1
    assert out["returns"]["twr"]["pct"] == 5.0
    assert [r["net_flow"] for r in out["series"]] == [0.0, 0.0, 0.0, 0.0]     # not money in or out
    assert [r["value"] for r in out["series"]] == [3000.0, 2000.0, 2100.0, 3100.0]


# --------------------------------------------------------------- benchmark


SPY = {"symbol": "SPY",
       "closes": [["2026-03-02", 100.0], ["2026-03-03", 102.0], ["2026-03-04", 101.0], ["2026-03-05", 103.0]],
       "dividends": [["2026-03-04", 2.0]]}


def test_benchmark_total_return_with_one_dividend_by_hand():
    # One share at 100. On the ex-date the 2.00 dividend buys 2/101 of a share
    # at that day's 101 close. At 103: (1 + 2/101) * 103 = 105.0396, +5.0396%.
    idx = P.benchmark_index(SPY["closes"], SPY["dividends"])
    assert idx[-1][1] == pytest.approx((1 + 2 / 101) * 103 / 100, rel=1e-12)
    # A dividend going ex on a day with no close is reinvested at the next close.
    late = P.benchmark_index([["2026-03-06", 100.0], ["2026-03-09", 100.0]], [["2026-03-07", 1.0]])
    assert late[-1][1] == pytest.approx(1.01)


def test_benchmark_is_measured_over_the_portfolios_own_dates_and_carries_its_last_close():
    # Portfolio values on 03-02, 03-05 and Saturday 03-07: 1,000, 1,030, 1,050
    # (+5.00%). SPY has no close on the 7th, so it keeps the 5th's: +5.0396%.
    out = run([acct("a")], {"a": []}, {"a": hist(("2026-03-02", 1000), ("2026-03-05", 1030), ("2026-03-07", 1050))},
              "2026-03-07", benchmark=SPY)
    r = out["returns"]
    assert r["twr"]["pct"] == 5.0
    assert r["benchmark"]["symbol"] == "SPY" and r["benchmark"]["twr_pct"] == 5.04
    assert r["excess_pct"] == round(100 * (0.05 - ((1 + 2 / 101) * 103 / 100 - 1)), 2) == -0.04
    assert [row["cum_benchmark_pct"] for row in out["series"]] == [0.0, 5.04, 5.04]
    assert "simple difference of two time-weighted returns" in r["excess_method"]


def test_a_benchmark_that_starts_after_the_portfolio_is_not_compared():
    out = run([acct("a")], {"a": []}, {"a": hist(("2026-03-01", 1000), ("2026-03-05", 1030))}, "2026-03-05",
              benchmark=SPY)
    assert out["returns"]["benchmark"]["twr_pct"] is None and out["returns"]["excess_pct"] is None
    assert "after the first measured date" in out["returns"]["benchmark"]["reason"]


# ------------------------------------------------------------- attribution


def snap(day, positions, cash, aid="a", complete=True):
    total = cash + sum(p["value"] for p in positions.values())
    return {"taken_at": day + "T21:00:00Z",
            "by_account": {aid: {"total": {"USD": total}, "cash": {"USD": cash}, "positions": positions,
                                 "complete": complete}}}


def stock(qty, price):
    return {"symbol": "AAPL", "kind": "equity", "currency": "USD", "qty": qty, "price": price, "value": qty * price}


def option(contracts, price):
    return {"symbol": "XYZ", "kind": "option", "currency": "USD", "qty": contracts, "price": price,
            "value": contracts * 100 * price, "multiplier": 100, "label": "XYZ 50 call 2026-12-18"}


def test_attribution_contributions_flows_and_remainder_add_up_to_the_change():
    # Day 1: 10 AAPL at 100, 2 XYZ calls at 5.00 (1,000), cash 500: 2,500.
    # Day 2: AAPL 110, calls 6.00, a 1,000 deposit: 3,800.
    # Day 3: 5 more AAPL bought at 110 during the day (550), AAPL closes 108,
    #        calls 5.50, a 20 dividend: 1,620 + 1,100 + 970 = 3,690.
    snaps = [snap("2026-10-12", {"equity:AAPL:USD": stock(10, 100), "option:XYZ": option(2, 5.0)}, 500),
             snap("2026-10-13", {"equity:AAPL:USD": stock(10, 110), "option:XYZ": option(2, 6.0)}, 1500),
             snap("2026-10-14", {"equity:AAPL:USD": stock(15, 108), "option:XYZ": option(2, 5.5)}, 970)]
    acts = {"a": [act("CONTRIBUTION", "2026-10-13", 1000),
                  act("BUY", "2026-10-14", -550, symbol="AAPL", units=5, price=110),
                  act("DIVIDEND", "2026-10-14", 20, symbol="AAPL")]}
    out = run([acct("a")], acts, {}, "2026-10-14", period="1m", snapshots=snaps)
    a = out["attribution"]
    assert a["available"] is True
    by = {p["key"]: p for p in a["positions"]}
    # By hand. AAPL: 10 * (110 - 100) + 10 * (108 - 110) = 80. Calls: the
    # value times the relative price change, 1,000 * 0.2 + 1,200 * (-1/12) = 100.
    assert by["equity:AAPL:USD"]["contribution"] == 80.0
    assert by["option:XYZ"]["contribution"] == 100.0
    assert a["sum_contributions"] == 180.0
    assert a["total_change"] == 1190.0 and a["flows"] == 1000.0
    # The remainder is the 5 shares bought at 110 marked at 108 (-10) plus the
    # dividend (+20): +10.
    assert a["remainder"] == 10.0
    assert a["sum_contributions"] + a["flows"] + a["remainder"] == a["total_change"]
    # Average capital is the mean of the starting values, (2,500 + 3,800) / 2.
    assert a["average_capital"] == 3150.0
    assert by["equity:AAPL:USD"]["contribution_pct"] == round(100 * 80 / 3150, 2)
    # The same three days give the time-weighted return its values too.
    assert out["sources"]["values"] == "collected"


def test_attribution_with_one_snapshot_says_why_it_is_unavailable():
    out = run([acct("a")], {"a": []}, {}, "2026-10-14", period="1m",
              snapshots=[snap("2026-10-14", {"equity:AAPL:USD": stock(10, 100)}, 0)])
    a = out["attribution"]
    assert a["available"] is False
    assert "1 daily snapshot" in a["reason"] and "at least two" in a["reason"]


# ------------------------------------------------------------- currencies


def test_mixed_currencies_are_measured_apart_and_never_combined():
    accounts = [acct("us", "Margin"), acct("ca", "TFSA", ccy="CAD")]
    acts = {"us": [], "ca": []}
    hists = {"us": hist(("2026-03-02", 1000), ("2026-03-03", 1100)),
             "ca": hist(("2026-03-02", 2000), ("2026-03-03", 1900), ccy="CAD")}
    out = run(accounts, acts, hists, "2026-03-03")
    assert out["currency"] is None
    assert out["returns"]["twr"]["pct"] is None and out["series"] == []
    assert "currency conversion" in out["returns"]["reason"]
    assert set(out["by_currency"]) == {"USD", "CAD"}
    assert out["by_currency"]["USD"]["returns"]["twr"]["pct"] == 10.0
    assert out["by_currency"]["CAD"]["returns"]["twr"]["pct"] == -5.0
    # Nowhere is 1,000 USD added to 2,000 CAD.
    assert all(row["value"] != 3000.0 for c in out["by_currency"].values() for row in c["series"])


# ------------------------------------------------------ not enough history


def test_insufficient_history_explains_what_is_missing_instead_of_returning_zero():
    accounts = [acct("m", "Margin", history_state="unavailable")]
    snaps = [snap("2026-10-14", {"equity:AAPL:USD": stock(10, 100)}, 0, aid="m")]
    out = run(accounts, {"m": [act("CONTRIBUTION", "2026-02-02", 10000)]}, {}, "2026-10-14", period="1y",
              snapshots=snaps, current={"m": {"value": 1000.0, "currency": "USD", "as_of": "2026-10-14T20:00:00Z"}})
    r = out["returns"]
    assert r["available"] is False and r["twr"]["pct"] is None and r["mwr"]["irr_annualized_pct"] is None
    assert "SnapTrade's balance-history add-on is off for Margin" in r["reason"]
    assert "on 1 day since 2026-10-14" in r["reason"]
    assert out["period"]["measured_start"] is None


def test_unknown_transactions_block_a_return_rather_than_counting_deposits_as_gains():
    accounts = [acct("a", "Individual", activities_state="unavailable")]
    out = run(accounts, {"a": []}, {"a": hist(("2026-03-02", 1000), ("2026-03-03", 2000))}, "2026-03-03")
    assert out["returns"]["twr"]["pct"] is None
    assert "does not supply transactions for Individual" in out["returns"]["reason"]


# --------------------------------------------------------------- sources


def test_provider_estimate_then_collected_then_current_are_labelled_and_gaps_not_filled():
    hists = {"a": hist(("2026-10-01", 1000), ("2026-10-02", 1010), ("2026-10-04", 1020))}
    snaps = [snap("2026-10-03", {}, 5000),          # inside the provider's window: not interleaved
             snap("2026-10-05", {}, 1030), snap("2026-10-06", {}, 1040)]
    out = run([acct("a")], {"a": []}, hists, "2026-10-07", period="1m", snapshots=snaps,
              current={"a": {"value": 1050.0, "currency": "USD", "as_of": "2026-10-07T15:00:00Z"}})
    assert [(r["date"], r["source"]) for r in out["series"]] == [
        ("2026-10-01", "provider_estimate"), ("2026-10-02", "provider_estimate"), ("2026-10-04", "provider_estimate"),
        ("2026-10-05", "collected"), ("2026-10-06", "collected"), ("2026-10-07", "current")]
    s = out["sources"]
    assert s["values"] == "mixed"
    assert s["switches"] == [{"date": "2026-10-05", "from": "provider_estimate", "to": "collected"}]
    assert {"from": "2026-10-02", "to": "2026-10-04", "days": 2} in s["gaps"]
    assert out["returns"]["twr"]["pct"] == 5.0                 # 1,000 to 1,050, no flows
    assert any("estimated by the provider" in x for x in out["limitations"])


def test_provider_history_is_used_only_where_every_account_has_it():
    hists = {"a": hist(("2026-10-05", 1000), ("2026-10-06", 1100))}
    snaps = [{"taken_at": "2026-10-05T21:00:00Z", "by_account": {
                 "a": {"total": {"USD": 900.0}, "positions": {}, "complete": True},
                 "b": {"total": {"USD": 100.0}, "positions": {}, "complete": True}}},
             {"taken_at": "2026-10-06T21:00:00Z", "by_account": {
                 "a": {"total": {"USD": 990.0}, "positions": {}, "complete": True},
                 "b": {"total": {"USD": 110.0}, "positions": {}, "complete": True}}}]
    out = run([acct("a"), acct("b", history_state="unavailable")], {"a": [], "b": []}, hists, "2026-10-06",
              snapshots=snaps)
    assert out["sources"]["values"] == "collected"
    assert [r["value"] for r in out["series"]] == [1000.0, 1100.0]


def test_an_incomplete_sync_is_left_out_rather_than_read_as_a_loss():
    snaps = [snap("2026-10-05", {}, 1000), snap("2026-10-06", {}, 400, complete=False), snap("2026-10-07", {}, 1010)]
    out = run([acct("a")], {"a": []}, {}, "2026-10-07", snapshots=snaps)
    assert [r["date"] for r in out["series"]] == ["2026-10-05", "2026-10-07"]
    assert out["returns"]["twr"]["pct"] == 1.0
    assert ("1 collected day in this period was left out (1 where the sync was incomplete or a holding had no "
            "price): a partial value would read as a loss and a recovery.") in out["limitations"]


# ---------------------------------------------------------- in-kind flows


def test_an_unvalued_in_kind_transfer_excludes_its_stretch_and_says_so():
    # The sandbox margin account's transfer in: units 1, no price, no amount.
    rows = [asdict(_sandbox_activity(r)) for r in SANDBOX_ACTIVITIES["margin"]]
    hists = {"m": hist(("2026-04-01", 10000), ("2026-04-02", 10500), ("2026-04-03", 10605))}
    out = run([acct("m", "Margin")], {"m": rows}, hists, "2026-04-03")
    twr = out["returns"]["twr"]
    assert twr["pct"] == 1.0                     # only 04-02 to 04-03 is measured: 10,605 / 10,500
    assert twr["excluded"] == [{"from": "2026-04-01", "to": "2026-04-02",
                                "reason": "a transfer on 2026-04-02 could not be valued"}]
    assert [r["measured"] for r in out["series"]] == [True, False, True]
    assert out["returns"]["mwr"]["available"] is False
    assert out["flows"]["unvalued"][0]["date"] == "2026-04-02"
    assert any("could not be valued" in s for s in out["limitations"])


def test_in_kind_transfers_are_valued_from_units_and_price_and_flagged():
    a = act("EXTERNAL_ASSET_TRANSFER_IN", "2026-04-02", None, symbol="AAPL", units=10, price=50.0)
    zero = act("EXTERNAL_ASSET_TRANSFER_IN", "2026-04-02", 0.0, symbol="MSFT", units=2, price=100.0)
    assert P.flow_value(a) == {"value": 500.0, "direction": 1, "in_kind": True, "valued_by": "units_x_price"}
    # A zero amount on shares moved is "not valued", not "worth nothing".
    assert P.flow_value(zero)["value"] == 200.0
    out = run([acct("a")], {"a": [a]}, {"a": hist(("2026-04-01", 1000), ("2026-04-02", 1500))}, "2026-04-02")
    assert out["returns"]["twr"]["pct"] == 0.0
    assert out["flows"]["in_kind"][0]["valued_by"] == "units_x_price"
    assert any("estimated from units and price" in s for s in out["limitations"])


def test_shares_transferred_out_are_money_out_whatever_the_sign_of_the_amount():
    # A broker can report the value of shares moved out as a positive amount.
    # The type says which way they went: out of 1,500 leaves 1,000, so the
    # 500 of shares is a withdrawal and the return is 0%, not -50%.
    out_kind = act("EXTERNAL_ASSET_TRANSFER_OUT", "2026-04-02", 500.0, symbol="AAPL", units=10, price=50.0)
    assert P.flow_value(out_kind)["value"] == -500.0
    out = run([acct("a")], {"a": [out_kind]}, {"a": hist(("2026-04-01", 1500), ("2026-04-02", 1000))}, "2026-04-02")
    assert out["returns"]["twr"]["pct"] == 0.0
    assert out["flows"]["withdrawals"] == 500.0


# ----------------------------------------------------------------- sandbox


def sandbox_rows():
    return {k: [asdict(_sandbox_activity(r)) for r in v] for k, v in SANDBOX_ACTIVITIES.items()}


def test_sandbox_transactions_give_the_deposits_withdrawal_and_internal_transfer():
    both = run([acct("ind", "Individual"), acct("roth", "Roth IRA")], sandbox_rows(), {}, "2026-10-15", period="1y")
    f = both["flows"]
    assert f["deposits"] == round(26663.50 + 14136.05, 2) == 40799.55
    assert f["withdrawals"] == 1500.0 and f["counts"]["withdrawals"] == 1
    assert f["internal_transfers"]["matched"] == 1 and f["internal_transfers"]["total"] == 1000.0
    pair = f["internal_transfers"]["pairs"][0]
    assert (pair["from"], pair["to"], pair["out_date"]) == ("Individual", "Roth IRA", "2026-05-01")
    # Dividends, by hand: 10.40 + 32.10 + 33.00 + 13.50 + 48.15 + 13.80 + 49.50.
    assert both["income"]["dividends"] == 200.45 and both["income"]["fees"] == 5.0
    # The Individual account alone: the transfer to the Roth is money out.
    ind = run([acct("ind", "Individual")], sandbox_rows(), {}, "2026-10-15", period="1y")["flows"]
    assert ind["deposits"] == 26663.50 and ind["withdrawals"] == 2500.0
    assert ind["internal_transfers"]["matched"] == 0


def test_sandbox_provider_history_gives_a_return_with_the_transfer_netted():
    prov = SandboxProvider()
    user = prov.register_user()
    session = prov.portal_url(user["user_id"], user["secret"], "http://localhost/cb").split("session=")[1]
    prov.authorize(session, "standard")
    hists = {}
    for a in prov.list_accounts(user["user_id"], user["secret"]):
        hists[a.id.rsplit(":", 1)[1]] = prov.balance_history(user["user_id"], user["secret"], a.id)
    out = run([acct("ind", "Individual"), acct("roth", "Roth IRA")], sandbox_rows(), hists, "2026-10-15",
              period="ytd")
    assert out["sources"]["values"] == "provider_estimate"
    assert out["returns"]["twr"]["pct"] is not None
    # The sandbox's estimate is the money put in so far times 1 + 0.12 * k / 365 + 0.02 * sin(k / 9), k days
    # after 2026-01-02. Day 0 is the two deposits; on 2026-10-14 (k = 285) the money in view is
    # 40,799.55 - 1,500 = 39,299.55, because the 1,000 left one account and arrived in the other.
    rows = {r["date"]: r for r in out["series"]}
    assert rows["2026-01-02"]["value"] == 40799.55
    k = 285
    assert rows["2026-10-14"]["value"] == pytest.approx(
        39299.55 * (1 + 0.12 * k / 365 + 0.02 * math.sin(k / 9)), abs=0.02)
    assert rows["2026-04-15"]["net_flow"] == -1500.0 and rows["2026-05-01"]["net_flow"] == 0.0


# ------------------------------------------------------------ house rules


def test_definitions_and_limitations_carry_no_em_dashes_and_state_their_terms():
    out = run([acct("a")], {"a": [act("CONTRIBUTION", "2026-03-03", 500)]},
              {"a": hist(("2026-03-02", 1000), ("2026-03-03", 1600), ("2026-03-04", 1680))}, "2026-03-04",
              benchmark=SPY)
    assert not [s for s in strings(out) if "\u2014" in s]   # the em dash, by code point
    assert out["version"] == "performance-2026-10-15.1"
    for key in ("time_weighted_return", "money_weighted_return", "modified_dietz", "internal_transfer",
                "in_kind_transfer", "benchmark_total_return", "excess_return", "value_sources"):
        assert out["definitions"][key]
    assert "not a return" in out["series_fields"]["value"]
    assert "not a return" in out["series_fields"]["cum_net_flow"].lower()


def test_periods():
    assert P.period_start("1m", date(2026, 3, 31)) == date(2026, 2, 28)
    assert P.period_start("3m", date(2026, 10, 15)) == date(2026, 7, 15)
    assert P.period_start("ytd", date(2026, 10, 15)) == date(2025, 12, 31)
    assert P.period_start("1y", date(2028, 2, 29)) == date(2027, 2, 28)
    with pytest.raises(ValueError):
        P.build([], {}, {}, [], {}, None, date(2026, 10, 15), "5y")


def test_classification_covers_every_snaptrade_type():
    expect = {"CONTRIBUTION": "external_flow", "WITHDRAWAL": "external_flow", "TRANSFER": "external_flow",
              "EXTERNAL_ASSET_TRANSFER_IN": "external_flow", "EXTERNAL_ASSET_TRANSFER_OUT": "external_flow",
              "DIVIDEND": "income", "SUBSTITUTE_DIVIDEND": "income", "INTEREST": "income", "REI": "income",
              "STOCK_DIVIDEND": "income", "FEE": "cost", "TAX": "cost", "BUY": "trade", "SELL": "trade",
              "OPTIONEXPIRATION": "trade", "OPTIONASSIGNMENT": "trade", "OPTIONEXERCISE": "trade",
              "SPLIT": "other", "ADJUSTMENT": "other", "SOMETHING_NEW": "unrecognised"}
    assert {k: P.classify(k) for k in expect} == expect
