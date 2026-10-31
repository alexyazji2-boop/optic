"""The next report date on a company's analysis (`/api/ticker`), pinned. Found by the post-demo overhaul's final audit
(branch post-demo-ultra, BUG-200 and BUG-201) and taken to live main on its own.

- BUG-200: the earnings date leg is read by the volatility surface and again for next_earnings_date. The second read
  raised KeyError, so the next report date was missing whenever a company's option chain was complete (since
  2026-10-13).
- BUG-201: Yahoo keeps a report that has happened in its calendar until it posts the next one, so KO's report of
  2026-10-27 read as its next report on 2026-10-30, and as the event inside every expiry on the volatility surface.
  Earnings this week needs that same past date to show the week's results, so the date is filtered where the next
  report is read, not in the provider.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_a_leg_read_twice_answers_twice():
    from app import main
    for parallel in (False, True):
        legs = main._Legs(parallel)
        calls = []
        legs.start("earnings_date", lambda t: calls.append(t) or "2026-11-17", "NVDA")
        assert legs.get("earnings_date") == "2026-11-17" and legs.get("earnings_date") == "2026-11-17"
        assert calls == ["NVDA"]                                     # fetched once, read twice

        def refused(t):
            raise RuntimeError("refused")
        legs.start("calendar", refused, "NVDA")
        for _ in range(2):
            with pytest.raises(RuntimeError):
                legs.get("calendar")                                   # the same failure each time, never a KeyError


def test_both_reads_of_the_report_date_are_of_one_leg_and_skip_a_past_report():
    src = (ROOT / "app/main.py").read_text()
    assert 'legs.start("earnings_date", YF_PROVIDER.earnings_date, ticker)' in src
    assert src.count('legs.get("earnings_date")') == 2
    assert src.count('_upcoming(legs.get("earnings_date"))') == 2   # the surface's event and next_earnings_date


def test_a_report_that_has_passed_is_not_the_next_one(monkeypatch):
    from app import main
    monkeypatch.setattr(main.session_mod, "market_today", lambda now=None: dt.date(2026, 10, 30))
    assert main._upcoming("2026-10-27") is None                       # KO's, three days after it reported
    assert main._upcoming("2026-10-30") == "2026-10-30"               # a report today is still the next one
    assert main._upcoming("2027-02-10") == "2027-02-10"
    assert main._upcoming(None) is None and main._upcoming("") is None


def test_earnings_this_week_keeps_a_report_from_earlier_in_the_week(monkeypatch):
    """The provider's date stays as Yahoo gives it: filtered there, Tuesday's report would leave Earnings this week and
    the weekly digest on Wednesday, with its result."""
    import pandas as pd
    import app.providers.yf as y
    from app import earnings_week, weekly
    from app.main import YF_PROVIDER as P
    monkeypatch.setattr(y, "_CACHE", {})
    monkeypatch.setattr(y, "_wait_turn", lambda: None)
    monkeypatch.setattr(y.session_mod, "market_today", lambda now=None: dt.date(2026, 10, 30))

    class Stub:
        def __init__(self, sym, *a, **k):
            self.sym = sym

        @property
        def calendar(self):
            return {"Earnings Date": [pd.Timestamp("2026-10-27")]}
    monkeypatch.setattr(y.yf, "Ticker", Stub)

    class Provider:                                                    # the real date; nothing else asked of Yahoo
        def earnings_date(self, symbol):
            return P.earnings_date(symbol)

        def earnings_history(self, symbol, limit=10):
            return []

        def earnings_calendar(self, symbol):
            return {}

        def profile(self, symbol):
            return {}

    assert P.earnings_date("ZZKO") == "2026-10-27"
    now = dt.datetime(2026, 10, 30, 12, 0, tzinfo=earnings_week.ET)
    week = earnings_week.build(Provider(), now=now, watchlist=["ZZKO"])
    tuesday = next(d for d in week["days"] if d["day"] == "Tuesday")
    assert [r["ticker"] for r in tuesday["rows"]] == ["ZZKO"] and tuesday["is_past"]
    digest = weekly.earnings_this_week(Provider(), now=now, watchlist=["ZZKO"])
    assert [(d["day"], d["symbols"]) for d in digest["days"]] == [("Tuesday", ["ZZKO"])]
