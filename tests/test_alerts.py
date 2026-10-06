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
#
# Delivery was a refusal (`deliver()` returned False) while this ran on a laptop,
# and the panel said nothing would be emailed. Asked to "fix this issue", it is
# real now: through the mailer sign-in and problem reports use, one message per
# scan, stored before sent so a failed send stays pending.


@pytest.fixture
def mail(monkeypatch):
    """A mail server that accepts, and records, what it is given."""
    sent = []
    box = {"accept": True}
    monkeypatch.setattr(alerts.mailer, "available", lambda: {"available": True})

    def send(to, subject, body, link=None):
        sent.append({"to": to, "subject": subject, "body": body})
        return box["accept"]
    monkeypatch.setattr(alerts.mailer, "send", send)
    monkeypatch.setenv("ALERT_EMAIL_TO", "ops@example.test")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    box["sent"] = sent
    return box


def _local(monkeypatch):
    for var in ("RAILWAY_ENVIRONMENT", "RAILWAY_GIT_COMMIT_SHA", "RENDER", "FLY_APP_NAME",
                "ALERT_ALWAYS_ON"):
        monkeypatch.delenv(var, raising=False)


def test_delivery_is_off_without_a_mail_server_a_recipient_or_a_server_that_stays_up(monkeypatch):
    _local(monkeypatch)
    for var in ("ALERT_EMAIL_TO", "FEEDBACK_EMAIL_TO"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(alerts.mailer, "available", lambda: {"available": False})
    d = alerts.delivery_status()
    assert d["enabled"] is False
    assert len(d["blockers"]) == 3
    joined = " ".join(d["blockers"])
    # The settings the mailer actually reads, not ones nothing reads.
    assert "SMTP_HOST" in joined and "EMAIL_FROM" in joined and "ALERT_SMTP_URL" not in joined


def test_the_always_on_blocker_survives_having_a_mail_server(monkeypatch):
    """Someone who sets up mail on a local process should still be told it
    misses anything that happens while it is closed: a different problem from a
    missing password, and it does not go away by adding one."""
    _local(monkeypatch)
    monkeypatch.setattr(alerts.mailer, "available", lambda: {"available": True})
    monkeypatch.setenv("ALERT_EMAIL_TO", "ops@example.test")
    d = alerts.delivery_status()
    assert d["enabled"] is False and d["has_credential"] is True
    assert any("always-on" in b for b in d["blockers"])


def test_a_hosting_platform_is_always_on_without_being_told(mail):
    d = alerts.delivery_status()
    assert d["enabled"] is True and d["blockers"] == []


def test_the_recipient_falls_back_to_the_problem_report_address(mail, monkeypatch):
    monkeypatch.delenv("ALERT_EMAIL_TO", raising=False)
    monkeypatch.setenv("FEEDBACK_EMAIL_TO", "reports@example.test")
    alerts.raise_alert("closed", "NVDA closed at its target", ticker="NVDA", dedupe_key="c1")
    assert alerts.deliver_pending()["sent"] == 1
    assert mail["sent"][0]["to"] == "reports@example.test"


def _age(alert_title, hours):
    with alerts._conn() as conn:
        conn.execute("UPDATE alerts SET created_at = ? WHERE title = ?",
                     ((alerts.datetime.now(alerts.timezone.utc)
                       - alerts.timedelta(hours=hours)).isoformat(), alert_title))


def test_a_scan_is_one_email_of_what_fired_and_each_is_sent_once(mail):
    alerts.raise_alert("idea", "AMD new long shares", ticker="AMD", body="Composite 64.",
                       dedupe_key="i1")
    alerts.raise_alert("closed", "NVDA closed at its target", ticker="NVDA", dedupe_key="c1")
    alerts.raise_alert("pattern", "PLTR double bottom confirmed", ticker="PLTR", dedupe_key="p1")
    out = alerts.deliver_pending()
    assert out == {"sent": 3}
    assert len(mail["sent"]) == 1
    msg = mail["sent"][0]
    assert msg["to"] == "ops@example.test" and msg["subject"] == "Optic alerts: 3 new"
    body = msg["body"]
    assert body.index("New trade idea: AMD new long shares") < body.index("Position closed: NVDA")
    assert "    Composite 64." in body and "Pattern confirmed: PLTR double bottom confirmed" in body
    # Sent once.
    assert alerts.deliver_pending() == {"sent": 0} and len(mail["sent"]) == 1
    assert all(r["delivered"] for r in alerts.recent())


def test_one_alert_is_its_own_subject(mail):
    alerts.raise_alert("closed", "NVDA closed at its target", ticker="NVDA", dedupe_key="c1")
    alerts.deliver_pending()
    assert mail["sent"][0]["subject"] == "Optic alert: NVDA closed at its target"


def test_turning_delivery_on_does_not_mail_the_backlog(mail):
    alerts.raise_alert("idea", "Old idea", dedupe_key="old")
    _age("Old idea", 48)
    alerts.raise_alert("idea", "New idea", dedupe_key="new")
    assert alerts.deliver_pending() == {"sent": 1}
    assert "Old idea" not in mail["sent"][0]["body"]


def test_a_send_that_fails_leaves_them_pending_for_the_next_scan(mail):
    alerts.raise_alert("closed", "NVDA closed at its target", dedupe_key="c1")
    mail["accept"] = False
    out = alerts.deliver_pending()
    assert out["sent"] == 0 and out["pending"] == 1
    assert not any(r["delivered"] for r in alerts.recent())
    mail["accept"] = True
    assert alerts.deliver_pending() == {"sent": 1}


def test_the_last_attempt_and_the_backlog_are_recorded_as_they_happened(mail):
    """What the inbox says about delivery comes from what delivery did."""
    alerts.raise_alert("closed", "NVDA closed at its target", dedupe_key="c2")
    mail["accept"] = False
    alerts.deliver_pending()
    assert alerts.LAST_ATTEMPT["sent"] == 0 and alerts.LAST_ATTEMPT["pending"] == 1
    assert "did not accept" in alerts.LAST_ATTEMPT["reason"]
    assert alerts.undelivered_recent() == 1
    mail["accept"] = True
    alerts.deliver_pending()
    assert alerts.LAST_ATTEMPT["sent"] == 1 and alerts.LAST_ATTEMPT["reason"] is None
    assert alerts.undelivered_recent() == 0


def test_nothing_is_sent_while_delivery_is_off(monkeypatch):
    _local(monkeypatch)
    monkeypatch.setattr(alerts.mailer, "available", lambda: {"available": False})
    monkeypatch.setattr(alerts.mailer, "send", lambda *a, **k: pytest.fail("sent while off"))
    alerts.raise_alert("idea", "x", dedupe_key="x")
    out = alerts.deliver_pending()
    assert out["sent"] == 0 and "SMTP_HOST" in out["reason"]


def test_every_scan_emails_what_it_raised_off_the_scan_lock():
    src = open("app/main.py", encoding="utf-8").read()
    fn = src[src.index("def _raise_scan_alerts("):src.index("def _deliver_alerts(")]
    assert 'threading.Thread(target=_deliver_alerts, name="alert-mail", daemon=True).start()' in fn
    assert "alerts_mod.deliver_pending()" in src
