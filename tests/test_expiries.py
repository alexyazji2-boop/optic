"""Expiry date rules.

These are deterministic, which means they can be tested exactly rather than
approximately — and they are worth testing exactly because the whole reason to
compute them is that people get the VIX rule wrong.
"""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.analytics import expiries as ex

ET = ZoneInfo("America/New_York")


@pytest.mark.parametrize("year", [2024, 2025, 2026, 2027])
def test_third_friday_is_always_a_friday_in_the_third_week(year):
    for month in range(1, 13):
        d = ex.third_friday(year, month)
        assert d.weekday() == 4, d
        assert 15 <= d.day <= 21, d


@pytest.mark.parametrize("year", [2024, 2025, 2026, 2027])
def test_vix_expiry_is_always_a_wednesday(year):
    """The rule's own invariant: third Friday minus 30 days is a Wednesday."""
    for month in range(1, 13):
        assert ex.vix_expiry(year, month).weekday() == 2


def test_vix_expiry_uses_the_following_month():
    """The distinction people get wrong: it is next month's third Friday."""
    assert ex.vix_expiry(2026, 8) == ex.third_friday(2026, 9) - __import__(
        "datetime").timedelta(days=30)


def test_vix_expiry_rolls_the_year_in_december():
    assert ex.vix_expiry(2026, 12) == ex.third_friday(2027, 1) - __import__(
        "datetime").timedelta(days=30)


def test_vix_and_equity_expiry_are_different_dates():
    """If these ever coincide in the output, the rule has collapsed."""
    for month in range(1, 13):
        assert ex.vix_expiry(2026, month) != ex.third_friday(2026, month)


def test_witching_months_only():
    for month in range(1, 13):
        witching = month in (3, 6, 9, 12)
        assert (month in ex.WITCHING_MONTHS) is witching


def test_upcoming_is_sorted_and_forward_looking():
    now = datetime(2026, 8, 14, 12, 0, tzinfo=ET)
    rows = ex.upcoming(now, months=3)
    assert rows
    dates = [r["date"] for r in rows]
    assert dates == sorted(dates)
    assert all(date.fromisoformat(d) >= now.date() for d in dates)
    assert {"opex", "vix"} <= {r["kind"] for r in rows}


def test_context_reports_days_to_the_next_expiry():
    now = datetime(2026, 8, 14, 12, 0, tzinfo=ET)   # opex is Aug 21
    c = ex.context(now)
    assert c["available"] is True
    assert c["days_to_opex"] == 7
    assert c["is_expiry_week"] is False
    assert c["next_vix_expiry"]["date"] == "2026-08-19"


def test_expiry_week_flags_inside_four_days():
    c = ex.context(datetime(2026, 8, 19, 12, 0, tzinfo=ET))
    assert c["is_expiry_week"] is True


def test_method_admits_the_holiday_gap():
    """The rule cannot see holidays; it must say so rather than be quietly wrong."""
    c = ex.context(datetime(2026, 8, 14, tzinfo=ET))
    assert "holiday" in c["method"]
