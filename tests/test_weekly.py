"""The weekly update's fact-gathering.

The model writes the piece; this module decides what it is allowed to know. So
these tests are about the boundary — that a week is bounded correctly, that an
empty earnings week reports emptiness rather than nothing, and that the
watchlist scan never presents itself as a complete market calendar.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from app import weekly

ET = ZoneInfo("America/New_York")


class _Provider:
    def __init__(self, dates=None, frames=None):
        self.dates = dates or {}
        self.frames = frames or {}

    def earnings_date(self, symbol):
        return self.dates.get(symbol)

    def batch_history(self, symbols, period="1y", interval="1d"):
        return {s: self.frames[s] for s in symbols if s in self.frames}


def _frame(n=300, price=100.0):
    vals = [price + i * 0.1 for i in range(n)]
    return pd.DataFrame({"Close": vals, "High": [v + 1 for v in vals],
                         "Low": [v - 1 for v in vals], "Open": vals,
                         "Volume": [1e6] * n})


# ------------------------------------------------------------- week bounds

def test_weekday_looks_at_the_week_it_is_in():
    wed = datetime(2026, 8, 12, 10, 0, tzinfo=ET)      # a Wednesday
    start, end = weekly._week_bounds(wed)
    assert start.strftime("%A") == "Monday"
    assert start.date() == datetime(2026, 8, 10).date()
    assert (end - start).days == 5


def test_weekend_looks_forward_to_the_coming_week():
    """A Sunday reader wants the week ahead, not the one that just ended."""
    sun = datetime(2026, 8, 16, 18, 0, tzinfo=ET)
    start, _ = weekly._week_bounds(sun)
    assert start.date() == datetime(2026, 8, 17).date()


def test_week_key_is_the_iso_week():
    assert weekly.week_key(datetime(2026, 8, 12, tzinfo=ET)) == "2026-W33"
    # Same week, different day, same key — the cache must not regenerate daily.
    assert weekly.week_key(datetime(2026, 8, 14, tzinfo=ET)) == "2026-W33"


def test_week_key_rolls_over():
    a = weekly.week_key(datetime(2026, 8, 14, tzinfo=ET))
    b = weekly.week_key(datetime(2026, 8, 18, tzinfo=ET))
    assert a != b


# ---------------------------------------------------------------- earnings

def test_earnings_are_grouped_by_weekday_in_order():
    p = _Provider({"AAPL": "2026-08-12", "MSFT": "2026-08-11", "NVDA": "2026-08-12"})
    got = weekly.earnings_this_week(p, datetime(2026, 8, 10, tzinfo=ET),
                                    watchlist=["AAPL", "MSFT", "NVDA"])
    assert [d["day"] for d in got["days"]] == ["Tuesday", "Wednesday"]
    assert got["days"][1]["symbols"] == ["AAPL", "NVDA"]      # sorted within a day
    assert got["total"] == 3


def test_dates_outside_the_week_are_excluded():
    p = _Provider({"AAPL": "2026-11-12", "MSFT": "2026-08-09"})
    got = weekly.earnings_this_week(p, datetime(2026, 8, 10, tzinfo=ET),
                                    watchlist=["AAPL", "MSFT"])
    assert got["total"] == 0


def test_an_empty_week_still_reports_what_it_checked():
    """'No earnings' and 'we did not look' must not look the same."""
    p = _Provider({"AAPL": "2026-11-12"})
    got = weekly.earnings_this_week(p, datetime(2026, 8, 10, tzinfo=ET),
                                    watchlist=["AAPL"])
    assert got["total"] == 0
    assert got["checked"] == 1
    assert "not the whole market" in got["note"]


def test_a_broken_symbol_does_not_abort_the_scan():
    class Flaky(_Provider):
        def earnings_date(self, symbol):
            if symbol == "BAD":
                raise RuntimeError("provider blew up")
            return self.dates.get(symbol)
    p = Flaky({"AAPL": "2026-08-12"})
    got = weekly.earnings_this_week(p, datetime(2026, 8, 10, tzinfo=ET),
                                    watchlist=["BAD", "AAPL"])
    assert got["total"] == 1
    assert got["failed"] == 1


def test_unparseable_date_is_skipped_not_guessed():
    p = _Provider({"AAPL": "not a date"})
    got = weekly.earnings_this_week(p, datetime(2026, 8, 10, tzinfo=ET),
                                    watchlist=["AAPL"])
    assert got["total"] == 0


def test_watchlist_is_deduplicated_and_uppercase():
    assert len(weekly.WATCHLIST) == len(set(weekly.WATCHLIST)), "duplicate tickers"
    assert all(s == s.upper() for s in weekly.WATCHLIST)


# ------------------------------------------------------------ index levels

def test_index_levels_reports_the_week_range():
    p = _Provider(frames={"SPY": _frame()})
    got = weekly.index_levels(p, "SPY")
    assert got["available"] is True
    assert got["prior_week_high"] > got["prior_week_low"]
    assert got["vs_sma200_pct"] is not None


def test_index_levels_needs_enough_history():
    p = _Provider(frames={"SPY": _frame(n=10)})
    assert weekly.index_levels(p, "SPY")["available"] is False


def test_index_levels_survives_a_dead_provider():
    class Broken:
        def batch_history(self, *a, **k):
            raise RuntimeError("down")
    assert weekly.index_levels(Broken(), "SPY")["available"] is False
