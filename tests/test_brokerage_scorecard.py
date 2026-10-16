"""The portfolio scorecard (app/brokerage/scorecard.py): five separate
assessments, each checked against figures worked out by hand here, never
against the module's own output.

What these pin down: the diversification arithmetic (1/HHI, the bands and the
weights the module documents), that missing fundamentals and funds go to
`not_assessed` instead of dragging a score down, Yahoo's debt-to-equity being
in percent, valuation and volatility staying unscored descriptions, a beta of
a series built as 1.5x the benchmark coming out near 1.5, and no overall score.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

import pytest

from app.brokerage import scorecard as s

TODAY = date(2026, 10, 15)


def _h(sym, kind, value, sector=None, total=10000.0):
    return {"symbol": sym, "kind": kind, "value_usd": value, "market_value": value, "quantity": value / 100,
            "price": 100.0, "weight_pct": 100.0 * value / total, "sector": sector, "currency": "USD"}


H = [_h("AAA", "equity", 5000.0, "Technology"), _h("BBB", "equity", 3000.0, "Healthcare"),
     _h("FFF", "etf", 2000.0)]
GOOD = {"return_on_equity": 0.25, "operating_margin": 0.30, "free_cash_flow": 30.0, "total_revenue": 100.0,
        "debt_to_equity": 0.2, "revenue_growth": 0.20, "forward_pe": 25.0, "quote_type": "EQUITY"}


def _by_id(out):
    return {a["id"]: a for a in out["assessments"]}


def test_there_are_five_separate_assessments_and_no_overall_score():
    out = s.build(H, None, lambda x: None, {}, [], [], None, TODAY)
    assert [a["id"] for a in out["assessments"]] == ["diversification", "financial_quality", "valuation",
                                                       "volatility", "event_exposure"]
    assert out["overall"] is None
    assert "not forecasts of return" in out["disclaimer"]
    for a in out["assessments"]:
        assert a["version"] == s.VERSION and "method" in a and "not_assessed" in a and "coverage_pct" in a


def test_diversification_is_the_documented_weighted_bands():
    # Weights 0.5, 0.3, 0.2: HHI 0.25 + 0.09 + 0.04 = 0.38, so 1/HHI = 2.63
    # effective holdings, below the lowest floor (4): grade 0. Largest position
    # 50% is over the 35% ceiling: 0. Largest sector: Technology 50% of value
    # (the fund is not a sector), between the 45 and 60 ceilings: grade 1.
    # Score = (0.4 x 0 + 0.3 x 0 + 0.3 x 1) / 4 x 100 = 7.5.
    a = _by_id(s.build(H, None, lambda x: None, {}, [], [], None, TODAY))["diversification"]
    assert a["score"] == pytest.approx(7.5, abs=0.5)
    assert a["level"] == "Highly concentrated"
    assert a["inputs"]["effective_holdings"] == pytest.approx(1 / 0.38, abs=0.01)
    # Ten equal holdings in ten sectors: 1/HHI = 10 (floor 7: grade 2), largest
    # 10% (ceiling 10: grade 3), largest sector 10% (ceiling 25: grade 4).
    # (0.4 x 2 + 0.3 x 3 + 0.3 x 4) / 4 x 100 = 72.5.
    even = [_h("S{}".format(i), "equity", 1000.0, "Sector{}".format(i)) for i in range(10)]
    a = _by_id(s.build(even, None, lambda x: None, {}, [], [], None, TODAY))["diversification"]
    assert a["score"] == pytest.approx(72.5, abs=0.5)


def test_missing_fundamentals_and_funds_are_not_assessed_never_scored_low():
    out = s.build(H, None, lambda x: GOOD if x == "AAA" else None, {}, [], [], None, TODAY)
    q = _by_id(out)["financial_quality"]
    skipped = {n["symbol"] for n in q["not_assessed"]}
    assert skipped == {"BBB", "FFF"}
    # AAA alone, every measure in its top band: 100. BBB's missing data does not pull it down.
    assert q["score"] == pytest.approx(100.0)
    # Covered: AAA's 5000 of 10000.
    assert q["coverage_pct"] == pytest.approx(50.0)
    fund = next(n for n in q["not_assessed"] if n["symbol"] == "FFF")
    assert "fund" in fund["reason"].lower()


def test_quality_needs_three_measures_before_it_grades():
    thin = {"return_on_equity": 0.3, "operating_margin": 0.3, "quote_type": "EQUITY"}   # two of five
    q = _by_id(s.build(H, None, lambda x: thin if x == "AAA" else None, {}, [], [], None, TODAY))["financial_quality"]
    assert "AAA" in {n["symbol"] for n in q["not_assessed"]}


def test_yahoo_debt_to_equity_is_percent_and_is_normalised():
    f = s.fundamentals_from_yahoo({"returnOnEquity": 0.3, "debtToEquity": 150.0, "operatingMargins": 0.2,
                                   "freeCashflow": 10, "totalRevenue": 100, "revenueGrowth": 0.1,
                                   "forwardPE": 20, "quoteType": "EQUITY"})
    assert f["debt_to_equity"] == pytest.approx(1.5)
    assert f["return_on_equity"] == 0.3 and f["quote_type"] == "EQUITY"


def test_valuation_compares_with_the_market_and_is_not_scored():
    # AAA alone assessed, forward P/E 25 against a market at 20: 25% richer,
    # outside the documented 15% "in line" band.
    v = _by_id(s.build(H, None, lambda x: GOOD if x == "AAA" else None, {}, [], [],
                       {"pe": 20.0, "ten_year": 0.04}, TODAY))["valuation"]
    assert v["score"] is None and "richer" in v["level"].lower()
    neg = dict(GOOD, forward_pe=-5.0, trailing_pe=None)
    v = _by_id(s.build(H, None, lambda x: neg if x == "AAA" else None, {}, [], [],
                       {"pe": 20.0, "ten_year": 0.04}, TODAY))["valuation"]
    assert "cheap" not in (v["level"] or "").lower()


def _series(returns, start=100.0):
    day = date(2025, 10, 1)
    out, p = [], start
    for r in returns:
        out.append([day.isoformat(), p])
        p *= 1 + r
        day += timedelta(days=1)
    return out


def test_volatility_beta_of_a_one_and_a_half_times_series_is_one_and_a_half():
    bench_r = [0.01 * math.sin(i / 3.0) for i in range(250)]
    stock_r = [1.5 * r for r in bench_r]
    closes = {"AAA": _series(stock_r), "BBB": _series(stock_r)}
    holdings = [_h("AAA", "equity", 5000.0, "Technology", 8000.0), _h("BBB", "equity", 3000.0, "Healthcare", 8000.0)]
    v = _by_id(s.build(holdings, None, lambda x: None, closes, _series(bench_r), [], None, TODAY))["volatility"]
    assert v["score"] is None
    assert v["inputs"]["beta"] == pytest.approx(1.5, abs=0.02)
    # Portfolio vol is 1.5x the benchmark's when every holding is 1.5x it.
    assert v["inputs"]["portfolio_vol_pct"] == pytest.approx(1.5 * v["inputs"]["benchmark_vol_pct"], rel=0.02)


def test_too_little_history_is_not_assessed():
    closes = {"AAA": _series([0.01] * 50)}
    v = _by_id(s.build(H, None, lambda x: None, closes, _series([0.01] * 50), [], None, TODAY))["volatility"]
    assert "AAA" in {n["symbol"] for n in v["not_assessed"]}


def test_event_exposure_splits_confirmed_from_estimated():
    events = [{"symbol": "AAA", "kind": "earnings", "date": "2026-10-20", "confirmed": True, "weight_pct": 50.0},
              {"symbol": "BBB", "kind": "earnings", "date": "2026-10-25", "confirmed": False, "weight_pct": 30.0},
              {"symbol": "AAA", "kind": "earnings", "date": "2026-12-20", "confirmed": True, "weight_pct": 50.0}]
    e = _by_id(s.build(H, None, lambda x: None, {}, [], events, None, TODAY))["event_exposure"]
    assert e["score"] is None
    assert e["inputs"]["confirmed_pct"] == pytest.approx(50.0)
    assert e["inputs"]["estimated_pct"] == pytest.approx(30.0)
