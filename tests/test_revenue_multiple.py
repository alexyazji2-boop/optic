"""Revenue against the multiple the market paid for it.

The panel exists for the divergence case — revenue up while the multiple
compresses — so that is what these tests pin, along with the refusal to draw a
conclusion from one data point.
"""
from __future__ import annotations

import pytest

from app.analytics import valuation


def _fin(revenues, periods):
    return {"annual": {"revenue": revenues}, "annual_periods": periods,
            "quarterly": {"revenue": [10.0, 9.0]},
            "quarterly_periods": ["2026-06-30", "2026-03-31"]}


def _hist(pairs):
    return {"years": [{"period": p, "pe": pe} for p, pe in pairs]}


PERIODS = ["2026-06-30", "2025-06-30", "2024-06-30", "2023-06-30"]
REVENUES = [400.0, 300.0, 250.0, 200.0]


def test_years_are_ordered_oldest_first():
    """The chart reads left to right like every other series in the terminal."""
    out = valuation.revenue_and_multiple(_fin(REVENUES, PERIODS), _hist([]))
    assert [y["label"] for y in out["years"]] == ["2023", "2024", "2025", "2026"]
    assert out["years"][0]["revenue"] == 200.0


def test_pe_is_matched_to_its_own_fiscal_year():
    """Off-by-one here would attribute a multiple to the wrong year's revenue."""
    hist = _hist([("2023-06-30", 20.0), ("2026-06-30", 30.0)])
    out = valuation.revenue_and_multiple(_fin(REVENUES, PERIODS), hist)
    by_label = {y["label"]: y["pe"] for y in out["years"]}
    assert by_label["2023"] == 20.0
    assert by_label["2026"] == 30.0
    assert by_label["2024"] is None


def test_cagr_is_annualised_not_total():
    """400 from 200 over four points is three years of growth, not four."""
    out = valuation.revenue_and_multiple(_fin(REVENUES, PERIODS), _hist([]))
    expected = ((400.0 / 200.0) ** (1 / 3) - 1) * 100
    assert out["revenue_cagr_pct"] == pytest.approx(round(expected, 1), abs=0.05)


def test_single_year_refuses_to_compare():
    out = valuation.revenue_and_multiple(_fin([200.0], ["2026-06-30"]), _hist([]))
    assert out["available"] is False
    assert "two fiscal years" in out["reason"]


def test_missing_revenue_is_reported_not_guessed():
    out = valuation.revenue_and_multiple({"annual": {}, "annual_periods": []}, _hist([]))
    assert out["available"] is False


def test_method_states_the_window_limit():
    """Four points cannot establish a range; the note has to say so."""
    out = valuation.revenue_and_multiple(_fin(REVENUES, PERIODS), _hist([]))
    assert "4 fiscal years" in out["method"]
    assert "cannot establish a range" in out["method"]


def test_quarters_are_included_and_ordered():
    out = valuation.revenue_and_multiple(_fin(REVENUES, PERIODS), _hist([]))
    assert [q["revenue"] for q in out["quarters"]] == [9.0, 10.0]


def test_years_with_pe_is_counted_separately():
    """A year with revenue but no EPS still plots a bar; the count must reflect that."""
    hist = _hist([("2026-06-30", 30.0)])
    out = valuation.revenue_and_multiple(_fin(REVENUES, PERIODS), hist)
    assert out["years_covered"] == 4
    assert out["years_with_pe"] == 1
