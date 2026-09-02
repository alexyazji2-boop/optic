"""The alert inbox.

Two things matter here and neither is the SQL. First, deduplication: a scan that
runs twice, or a restart mid-scan, must not produce the same alert twice — an
inbox that cries wolf gets ignored, which defeats the point. Second, the delivery
status has to be honest about *why* nothing is being sent, because "not
configured" hides the fact that one of the two blockers is not a credential at
all but the absence of a server that stays awake.
"""

import os
import tempfile

import pytest

from app import alerts


@pytest.fixture(autouse=True)
def _isolated_db(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setattr(alerts, "DB_PATH", os.path.join(tmp, "alerts.db"))
        alerts.init()
        yield


def test_an_alert_is_recorded_and_read_back():
    assert alerts.raise_alert("idea", "NVDA — new long shares", ticker="NVDA",
                              body="Composite 61.")
    rows = alerts.recent()
    assert len(rows) == 1
    assert rows[0]["ticker"] == "NVDA"
    assert rows[0]["kind_label"] == "New trade idea"
    assert rows[0]["seen"] == 0


def test_an_unknown_kind_is_refused():
    """Kinds carry an urgency that a delivery layer would filter on. An unknown
    one would arrive with no urgency at all."""
    assert alerts.raise_alert("whatever", "something happened") is False
    assert alerts.recent() == []


def test_the_same_event_twice_records_once():
    """The property the whole design turns on. A scan re-run, or a restart part
    way through one, must not refill the inbox."""
    for _ in range(3):
        alerts.raise_alert("idea", "NVDA — new long shares", ticker="NVDA",
                           dedupe_key="idea:NVDA:shares:balanced:2026-09-01")
    assert len(alerts.recent()) == 1


def test_different_events_on_the_same_ticker_both_record():
    """Dedupe must not be so eager that a real second event is swallowed."""
    alerts.raise_alert("idea", "NVDA long", ticker="NVDA", dedupe_key="a")
    alerts.raise_alert("closed", "NVDA closed", ticker="NVDA", dedupe_key="b")
    assert len(alerts.recent()) == 2


def test_a_scan_with_nothing_in_it_raises_nothing():
    assert alerts.from_scan({"considered": 300, "opened": 0, "closed": 0}) == 0
    assert alerts.recent() == []


def test_a_scan_raises_one_alert_per_opened_position():
    result = {
        "ran_at": "2026-09-01T14:00:00Z",
        "opened_positions": [
            {"ticker": "NVDA", "instrument": "shares", "direction": "long",
             "composite": 61, "entry_price": 180.0, "stop": 170.0, "target": 200.0,
             "book": "balanced", "entry_at": "2026-09-01T14:00:00Z"},
            {"ticker": "AMD", "instrument": "option", "direction": "long",
             "composite": 55, "entry_price": 4.2, "stop": 150.0, "target": 190.0,
             "book": "aggressive", "entry_at": "2026-09-01T14:00:00Z"},
        ],
    }
    assert alerts.from_scan(result) == 2
    rows = alerts.recent()
    assert {r["ticker"] for r in rows} == {"NVDA", "AMD"}
    # Re-running the same scan adds nothing.
    assert alerts.from_scan(result) == 0
    assert len(alerts.recent()) == 2


def test_a_closed_position_alert_says_why_it_closed():
    """"NVDA closed" without a reason is the least useful possible alert."""
    alerts.from_scan({
        "closed_positions": [{"id": 7, "ticker": "NVDA", "exit_reason": "Stop hit",
                              "exit_price": 170.0, "pnl": -420.0,
                              "exit_at": "2026-09-01T15:00:00Z"}],
    })
    row = alerts.recent()[0]
    assert "Stop hit" in row["title"]
    assert row["urgency"] == "high", "a closed position outranks a new idea"


def test_capacity_warns_once_per_day_not_once_per_scan():
    cap = {"position_slots_left": 0, "risk_budget_left": 500}
    for _ in range(4):
        alerts.from_capacity("balanced", cap, "2026-09-01")
    assert len(alerts.recent()) == 1
    # A new day is a new warning.
    alerts.from_capacity("balanced", cap, "2026-09-02")
    assert len(alerts.recent()) == 2


def test_capacity_says_nothing_when_there_is_room():
    alerts.from_capacity("balanced", {"position_slots_left": 4,
                                      "risk_budget_left": 900}, "2026-09-01")
    assert alerts.recent() == []


def test_marking_seen_and_the_unseen_count():
    alerts.raise_alert("idea", "one", dedupe_key="1")
    alerts.raise_alert("idea", "two", dedupe_key="2")
    assert alerts.unseen_count() == 2
    alerts.mark_seen()
    assert alerts.unseen_count() == 0
    assert len(alerts.recent()) == 2, "marking read must not delete anything"


def test_unseen_only_filter():
    alerts.raise_alert("idea", "one", dedupe_key="1")
    alerts.mark_seen()
    alerts.raise_alert("idea", "two", dedupe_key="2")
    assert len(alerts.recent(unseen_only=True)) == 1


def test_clear_removes_everything():
    alerts.raise_alert("idea", "one", dedupe_key="1")
    assert alerts.clear() == 1
    assert alerts.recent() == []


# ------------------------------------------------------------------ delivery

def test_delivery_is_off_without_credentials(monkeypatch):
    for var in ("ALERT_SMTP_URL", "ALERT_EMAIL_KEY", "ALERT_EMAIL_TO",
                "ALERT_ALWAYS_ON"):
        monkeypatch.delenv(var, raising=False)
    d = alerts.delivery_status()
    assert d["enabled"] is False
    assert len(d["blockers"]) == 3


def test_the_always_on_blocker_survives_having_a_credential(monkeypatch):
    """The important one. Someone who adds an SMTP password should still be told
    that alerts will miss anything happening while the laptop sleeps — that is a
    different problem from a missing key and it does not go away by adding one."""
    monkeypatch.setenv("ALERT_SMTP_URL", "smtp://user:pass@host:587")
    monkeypatch.setenv("ALERT_EMAIL_TO", "someone@example.com")
    monkeypatch.delenv("ALERT_ALWAYS_ON", raising=False)
    d = alerts.delivery_status()
    assert d["enabled"] is False
    assert d["has_credential"] is True
    assert any("always-on" in b for b in d["blockers"])


def test_delivery_refuses_rather_than_half_working():
    """A half-implemented SMTP call is the dangerous version: it looks fine in
    testing and drops messages exactly when the machine sleeps."""
    assert alerts.deliver({"title": "x"}) is False
