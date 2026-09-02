"""Tests for the SEC filing extraction and the trailing P/E series.

Every test here corresponds to a bug that actually shipped into a chart during
development. The multiple history took four separate fixes before it agreed with a
known figure, and each one was invisible in the output — the series looked
plausible and was wrong by 30-50%. So these are regression tests in the literal
sense.
"""

import datetime as dt

import pandas as pd
import pytest

from app.analytics import pe_history, sec_facts


# --------------------------------------------------------------- extraction

def _point(start, end, val, filed):
    return {"start": start, "end": end, "val": val, "filed": filed, "form": "10-Q"}


def _gaap(tag, points, unit="USD"):
    return {tag: {"units": {unit: points}}}


def test_merge_keeps_the_restated_value_but_the_first_filing_date():
    """The single most consequential bug in this module.

    A restatement supersedes the value it restates, so the latest filing wins on
    the number. But it does NOT change when the quarter became public, and
    overwriting the date with the restatement's told the code Microsoft's June 2021
    quarter was not public until July 2023 — which broke the four-consecutive-
    quarters test for two years and put every multiple in that stretch on earnings
    up to two years stale.
    """
    gaap = _gaap("Revenues", [
        _point("2021-01-01", "2021-03-31", 100.0, "2021-04-27"),
        _point("2021-01-01", "2021-03-31", 105.0, "2022-04-26"),   # restatement
    ])
    merged = sec_facts._merge_periods(gaap, ("Revenues",), "USD", 80, 100)
    row = merged["2021-03-31"]
    assert row["value"] == 105.0, "the restated figure is the current truth"
    assert row["first_filed"] == "2021-04-27", "but it was public from the original filing"

    series = sec_facts._series(merged)
    assert series[0]["available_from"] == "2021-04-27"
    assert series[0]["restated_on"] == "2022-04-26"


def test_merge_spans_multiple_tags():
    """Six us-gaap revenue tags are in circulation and one issuer's history
    routinely spans three. Reading a single tag truncated NVIDIA's revenue at 2020
    and JPMorgan's at 2014, exactly where each switched."""
    gaap = {}
    gaap.update(_gaap("SalesRevenueNet", [
        _point("2015-01-01", "2015-03-31", 50.0, "2015-04-20")]))
    gaap.update(_gaap("Revenues", [
        _point("2018-01-01", "2018-03-31", 70.0, "2018-04-20")]))
    gaap.update(_gaap("RevenueFromContractWithCustomerExcludingAssessedTax", [
        _point("2022-01-01", "2022-03-31", 90.0, "2022-04-20")]))
    merged = sec_facts._merge_periods(gaap, sec_facts.REVENUE_TAGS, "USD", 80, 100)
    assert sorted(merged) == ["2015-03-31", "2018-03-31", "2022-03-31"]


def test_only_quarter_length_periods_are_taken_as_quarters():
    gaap = _gaap("Revenues", [
        _point("2021-01-01", "2021-03-31", 100.0, "2021-04-20"),   # ~89 days
        _point("2021-01-01", "2021-06-30", 210.0, "2021-07-20"),   # half year
        _point("2021-01-01", "2021-12-31", 400.0, "2022-01-20"),   # full year
    ])
    merged = sec_facts._merge_periods(gaap, ("Revenues",), "USD",
                                      sec_facts.Q_MIN_DAYS, sec_facts.Q_MAX_DAYS)
    assert list(merged) == ["2021-03-31"], "a half year is not a quarter"


def test_fourth_quarter_is_derived_from_the_annual_figure():
    """A fiscal Q4 is normally reported only inside the 10-K, so without this every
    year has a hole in it."""
    quarters = {
        "2021-03-31": {"value": 100.0, "filed": "2021-04-20", "first_filed": "2021-04-20",
                       "tag": "Revenues", "start": "2021-01-01", "span_days": 89},
        "2021-06-30": {"value": 110.0, "filed": "2021-07-20", "first_filed": "2021-07-20",
                       "tag": "Revenues", "start": "2021-04-01", "span_days": 90},
        "2021-09-30": {"value": 120.0, "filed": "2021-10-20", "first_filed": "2021-10-20",
                       "tag": "Revenues", "start": "2021-07-01", "span_days": 91},
    }
    years = {"2021-12-31": {"value": 460.0, "filed": "2023-02-01",
                            "first_filed": "2022-02-01", "tag": "Revenues",
                            "start": "2021-01-01", "span_days": 364}}
    added = sec_facts._fill_fourth_quarters(quarters, years)
    assert added == 1
    q4 = quarters["2021-12-31"]
    assert q4["value"] == pytest.approx(130.0), "annual minus the three quarters"
    assert q4["derived"] is True
    # The original 10-K date, not the later restatement of it. Inheriting the
    # restatement made every derived quarter look years newer than it was.
    assert q4["first_filed"] == "2022-02-01"


def test_fourth_quarter_is_skipped_when_a_quarter_is_missing():
    """Deriving Q4 from two quarters folds the missing one into it and produces a
    spike that looks like a real result."""
    quarters = {
        "2021-03-31": {"value": 100.0, "filed": "2021-04-20", "first_filed": "2021-04-20",
                       "tag": "Revenues", "start": "2021-01-01", "span_days": 89},
        "2021-09-30": {"value": 120.0, "filed": "2021-10-20", "first_filed": "2021-10-20",
                       "tag": "Revenues", "start": "2021-07-01", "span_days": 91},
    }
    years = {"2021-12-31": {"value": 460.0, "filed": "2022-02-01",
                            "first_filed": "2022-02-01", "tag": "Revenues",
                            "start": "2021-01-01", "span_days": 364}}
    assert sec_facts._fill_fourth_quarters(quarters, years) == 0


def _quarters(n, start_year=2020, value=1.0, step=0.0):
    rows = []
    for i in range(n):
        year = start_year + i // 4
        month = [3, 6, 9, 12][i % 4]
        day = 31 if month in (3, 12) else 30
        end = "%04d-%02d-%02d" % (year, month, day)
        filed = (dt.date.fromisoformat(end) + dt.timedelta(days=27)).isoformat()
        rows.append({"period_end": end, "available_from": filed,
                     "value": value + step * i, "derived": False})
    return rows


def test_trailing_sums_four_consecutive_quarters():
    """The window test is on the span between the first and last period end, which
    for four consecutive quarters is three intervals — about 270 days, not 365.
    Asking for 300-420 threw away almost every valid window and left Microsoft
    with no trailing earnings at all."""
    rows = _quarters(8, value=1.0)
    ttm = sec_facts._trailing(rows)
    assert len(ttm) == 5
    assert ttm[0]["value"] == pytest.approx(4.0)


def test_trailing_refuses_to_span_a_gap():
    rows = _quarters(8)
    del rows[3]
    ttm = sec_facts._trailing(rows)
    ends = {r["period_end"] for r in ttm}
    assert "2021-06-30" not in ends, "summing across a hole is not a trailing year"


def test_trailing_availability_is_the_latest_of_its_quarters():
    rows = _quarters(4)
    ttm = sec_facts._trailing(rows)
    assert ttm[0]["available_from"] == max(r["available_from"] for r in rows)


# ------------------------------------------------------------------ as-of

def test_as_of_returns_the_freshest_public_period_not_the_last_restated():
    """A plain "latest filed wins" lookup returns whichever period was most
    recently RESTATED, and XBRL comparative columns mean that is usually a figure
    one to two years old."""
    rows = [
        {"period_end": "2024-03-31", "available_from": "2024-04-25", "value": 10.0},
        # A restatement of an old quarter, filed later than the newer quarter.
        {"period_end": "2022-03-31", "available_from": "2024-06-01", "value": 6.0},
    ]
    pairs = pe_history._as_of_lookup(rows)
    hit = pe_history._value_as_of(pairs, dt.date(2024, 7, 1))
    assert hit is not None
    _filed, value, period = hit
    assert period == "2024-03-31" and value == 10.0


def test_as_of_never_uses_a_figure_before_it_was_filed():
    rows = [{"period_end": "2024-03-31", "available_from": "2024-04-25", "value": 10.0}]
    pairs = pe_history._as_of_lookup(rows)
    assert pe_history._value_as_of(pairs, dt.date(2024, 4, 1)) is None
    assert pe_history._value_as_of(pairs, dt.date(2024, 4, 25)) is not None


# ------------------------------------------------------------------ splits

def test_split_factor_counts_only_splits_after_the_date():
    factors = pe_history._split_factors([
        {"date": "2021-07-20", "ratio": 4.0},
        {"date": "2024-06-10", "ratio": 10.0},
    ])
    assert pe_history._cumulative_after(factors, dt.date(2020, 1, 1)) == pytest.approx(40.0)
    assert pe_history._cumulative_after(factors, dt.date(2022, 1, 1)) == pytest.approx(10.0)
    assert pe_history._cumulative_after(factors, dt.date(2025, 1, 1)) == pytest.approx(1.0)


def test_split_factors_tolerate_junk():
    assert pe_history._split_factors([{"date": "nope", "ratio": 2.0},
                                      {"date": "2021-01-01", "ratio": 0.0},
                                      {}]) == []


# -------------------------------------------------------------- integration

class _Provider:
    """Minimal provider: a rising price and a two-for-one split in the middle."""

    def __init__(self, splits=None, trailing_pe=None):
        self._splits = splits or []
        self._pe = trailing_pe

    def history(self, ticker, period="10y", interval="1d"):
        idx = pd.date_range("2020-01-01", periods=1600, freq="B")
        return pd.DataFrame({"Close": [100.0] * len(idx)}, index=idx)

    def splits(self, ticker):
        return self._splits

    def quote(self, ticker):
        return {"trailing_pe": self._pe} if self._pe else {}


def _install_facts(monkeypatch, quarters):
    monkeypatch.setattr(sec_facts, "history", lambda t, force=False: {
        "available": True, "eps_quarters": quarters,
        "revenue_yoy": [], "revenue_ttm": [], "counts": {}, "span": {},
        "short_history": False, "notes": [], "source": "test",
    })


def test_build_produces_a_series_and_bands(monkeypatch):
    _install_facts(monkeypatch, _quarters(24, value=1.0))
    out = pe_history.build(_Provider(trailing_pe=25.0), "TEST")
    assert out["available"] is True
    assert out["weeks"] > 26
    assert out["pe_current"] == pytest.approx(100.0 / 4.0)
    assert set(out["pe_bands"]) == {"10", "25", "50", "75", "90"}


def test_build_reports_the_anchor_disagreement(monkeypatch):
    """The independent check on the whole chain. The provider computes its trailing
    P/E from a different source, so agreement at the latest point is corroboration
    rather than a tautology."""
    _install_facts(monkeypatch, _quarters(24, value=1.0))
    out = pe_history.build(_Provider(trailing_pe=25.0), "TEST")
    assert out["anchor"]["agrees"] is True
    out2 = pe_history.build(_Provider(trailing_pe=90.0), "TEST")
    assert out2["anchor"]["agrees"] is False, "a 3x gap must be flagged, not hidden"


def test_splits_are_applied_per_quarter_before_summing(monkeypatch):
    """Summing first and dividing the total by one factor means a trailing window
    spanning a split has added together quarters counted in different shares, and
    no single divisor can fix a sum like that."""
    quarters = _quarters(24, value=1.0)
    mid = quarters[12]["period_end"]
    _install_facts(monkeypatch, quarters)
    plain = pe_history.build(_Provider(), "TEST")
    split = pe_history.build(
        _Provider(splits=[{"date": mid, "ratio": 2.0}]), "TEST")
    # The latest quarters are filed after the split, so today is unaffected...
    assert split["pe_current"] == pytest.approx(plain["pe_current"])
    # ...while the earliest point, whose quarters were all filed before it, doubles.
    assert split["pe_series"][0]["pe"] == pytest.approx(
        plain["pe_series"][0]["pe"] * 2, rel=0.02)


def test_loss_making_years_are_omitted_not_plotted(monkeypatch):
    """A P/E on negative trailing earnings is not a small number, it is not a
    number — it swings through infinity as EPS crosses zero."""
    quarters = _quarters(24, value=-1.0)
    _install_facts(monkeypatch, quarters)
    out = pe_history.build(_Provider(), "TEST")
    assert out["available"] is False
    assert "overlapping" in out["reason"] or "week" in out["reason"]


def test_build_refuses_without_enough_quarters(monkeypatch):
    _install_facts(monkeypatch, _quarters(4))
    out = pe_history.build(_Provider(), "TEST")
    assert out["available"] is False
    assert "quarters" in out["reason"]


def test_quarter_label_is_by_calendar_quarter_ended():
    assert pe_history._quarter_label("2026-06-30") == "Q2'26"
    assert pe_history._quarter_label("2026-01-31") == "Q1'26"
    assert pe_history._quarter_label("nonsense") == "nonsense"
