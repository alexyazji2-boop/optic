"""One market date across the terminal: New York's.

Measured on Monday 26 October 2026 after 10pm ET, with the server on UTC:
Brokerage called Tuesday's events "today" and Wednesday's "in 1 day", and
NVDA's 17 November report was 21 days away on the Earnings tab (the server's
`pd.Timestamp.today()`, already Tuesday in UTC) and 22 on the Overview
(news.py, which counted from New York). The header said Monday."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from app import session
from app.analytics import earnings
from app.brokerage import events as bk_events

ROOT = Path(__file__).parent.parent


class _Clock(datetime):
    at = datetime(2026, 10, 27, 2, 0, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz=None):
        return cls.at.astimezone(tz) if tz else cls.at.replace(tzinfo=None)


@pytest.fixture
def clock(monkeypatch):
    monkeypatch.setattr(session, "datetime", _Clock)

    def set_(iso):
        _Clock.at = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return set_


@pytest.mark.parametrize("utc, ny", [
    ("2026-10-27T02:00:00Z", "2026-10-26"),   # Monday 10pm EDT, Tuesday in UTC
    ("2026-10-27T03:59:00Z", "2026-10-26"),   # 11:59pm EDT
    ("2026-10-27T04:00:00Z", "2026-10-27"),   # midnight EDT
    ("2026-12-15T04:30:00Z", "2026-12-14"),   # 11:30pm EST: five hours behind in winter
    ("2026-12-15T05:00:00Z", "2026-12-15"),
    ("2026-03-08T04:30:00Z", "2026-03-07"),   # the night clocks go forward
    ("2026-03-08T07:30:00Z", "2026-03-08"),   # 3:30am EDT
    ("2026-11-01T03:30:00Z", "2026-10-31"),   # Saturday 11:30pm EDT, the night clocks go back
    ("2026-11-01T05:30:00Z", "2026-11-01"),   # 1:30am EDT
    ("2026-11-01T06:30:00Z", "2026-11-01"),   # 1:30am EST, the repeated hour
])
def test_the_market_date_is_new_yorks(utc, ny):
    assert session.market_today(datetime.fromisoformat(utc.replace("Z", "+00:00"))).isoformat() == ny


def test_a_naive_time_is_read_as_utc():
    assert session.market_today(datetime(2026, 10, 27, 2, 0)) == date(2026, 10, 26)


def test_the_earnings_tab_counts_from_new_york_after_utc_midnight(clock):
    clock("2026-10-27T02:30:00Z")
    nr = earnings._next_report([{"date": "2026-11-17", "eps_reported": None, "eps_estimate": 1.2}], {})
    assert nr["days_away"] == 22, "the Overview's count (news.py) and this one agree"


def test_a_report_today_in_new_york_is_still_upcoming_at_11pm(clock):
    clock("2026-10-27T03:30:00Z")
    nr = earnings._next_report([{"date": "2026-10-26", "eps_reported": None}], {})
    assert nr["date"] == "2026-10-26" and nr["days_away"] == 0


def test_brokerage_events_say_today_and_tomorrow_by_new_yorks_date(clock):
    clock("2026-10-27T02:30:00Z")
    holdings = [{"symbol": "AAPL", "kind": "equity", "quantity": 1, "weight_pct": 10.0},
                {"symbol": "MSFT", "kind": "equity", "quantity": 1, "weight_pct": 10.0}]
    cal = {"AAPL": {"dates": ["2026-10-27"], "confirmed": True}, "MSFT": {"dates": ["2026-10-28"], "confirmed": True}}
    out = bk_events.build(holdings, [], session.market_today(), earnings_of=lambda s: cal[s])
    away = {e["symbol"]: e["days_away"] for e in out["events"] if e["kind"] == "earnings"}
    assert away == {"AAPL": 1, "MSFT": 2}, "Tuesday is tomorrow and Wednesday is in 2 days on Monday night"


def test_a_weekend_counts_calendar_days_from_new_yorks_saturday(clock):
    clock("2026-11-01T01:00:00Z")            # Saturday 9pm EDT, Sunday in UTC
    assert session.market_today() == date(2026, 10, 31)
    nr = earnings._next_report([{"date": "2026-11-02", "eps_reported": None}], {})
    assert nr["days_away"] == 2


def test_no_market_date_is_taken_from_the_servers_own_clock():
    """The calls that produced the wrong dates, by file. A new one should use
    session.market_today(); a timestamp or a data window may stay on UTC."""
    offenders = []
    for rel in ("app/analytics/earnings.py", "app/brokerage/workspace.py", "app/brokerage/desk_section.py",
                "app/research/earnings_view.py", "app/research/modes.py", "app/analytics/morning_desk.py",
                "app/brokerage/portfolio.py", "app/paper.py", "app/providers/yf.py", "app/providers/common.py",
                "app/shortlist.py"):
        src = (ROOT / rel).read_text()
        for bad in ("date.today()", "pd.Timestamp.today()", "datetime.now(timezone.utc).date()"):
            if bad in src:
                offenders.append((rel, bad))
    assert offenders == []


def test_the_client_counts_from_new_york_too():
    mt = (ROOT / "static/v2/js/core/marketTime.js").read_text()
    assert "export const marketDate" in mt and "export function daysUntil" in mt
    ov = (ROOT / "static/v2/js/pages/overview-research.js").read_text()
    assert "daysUntil(up.date, today)" in ov and "today.getDate()" not in ov
