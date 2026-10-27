"""The pre-earnings brief: reading costs nothing, writing is metered, and once.

GET /api/earnings/{T}/brief wrote a brief on a cache miss for anyone who opened
an Earnings tab, with no account and no allowance (readiness audits of
2026-10-23 and 2026-10-26). The six-hour cache bounded one ticker's cost and
nothing bounded the number of tickers. Now the GET only reads what is kept, and
a POST writes, behind the assistant allowance, one write per report at a time,
under a daily ceiling. No test here reaches a model: the client is faked."""

from __future__ import annotations

import json
import threading
import time

import pytest
from fastapi.testclient import TestClient

import app.main as m
from app import ai
from tests.test_ai_credits import _msg, claude  # noqa: F401  (the stubbed client)

client = TestClient(m.app)
FACTS = {"next_report": {"date": "2026-11-17"}}
BRIEF = {"headline": "Into the report", "stance": "two-sided", "paragraphs": ["Consensus is 1.20."]}


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    monkeypatch.setattr(m, "_earnings_brief_facts", lambda sym: dict(FACTS))
    monkeypatch.setattr(ai, "_EARNINGS_CACHE", {})
    monkeypatch.setattr(ai, "_OPEN_WRITES", {})
    monkeypatch.setattr(m, "_ai_calls", {})


def _no_write(monkeypatch):
    calls = []
    monkeypatch.setattr(ai, "write_earnings_brief", lambda *a, **k: calls.append(a) or {"available": True})
    return calls


def test_opening_the_tab_never_writes(monkeypatch):
    calls = _no_write(monkeypatch)
    monkeypatch.setattr(ai, "available", lambda: {"enabled": True})
    body = client.get("/api/earnings/ZQNV/brief").json()
    assert calls == [] and body["available"] is False and body["written"] is False and body["can_write"] is True
    assert "one Milo message" in body["reason"]


def test_a_kept_brief_is_read_by_anyone_for_free(monkeypatch):
    calls = _no_write(monkeypatch)
    monkeypatch.setattr(ai, "kept_earnings_brief", lambda sym, facts: dict(BRIEF, available=True))
    got = client.get("/api/earnings/ZQNV/brief").json()
    assert got["headline"] == "Into the report" and got["ticker"] == "ZQNV" and calls == []
    posted = client.post("/api/earnings/ZQNV/brief").json()
    assert posted["headline"] == "Into the report" and calls == [], "a guest's POST reads the kept one"


def test_a_guest_cannot_write_and_nothing_is_spent(monkeypatch):
    calls = _no_write(monkeypatch)
    monkeypatch.setattr(m, "GUEST_AI_CALLS_PER_DAY", 0)
    reply = client.post("/api/earnings/ZQNV/brief")
    assert reply.status_code == 401 and "free account" in reply.json()["detail"]
    assert calls == []


def test_an_exhausted_allowance_spends_nothing(monkeypatch):
    calls = _no_write(monkeypatch)

    def spent(request):
        raise m.HTTPException(status_code=429, detail="That is 3 assistant messages today, which is what this plan includes.")
    monkeypatch.setattr(m, "_spend_guard", spent)
    reply = client.post("/api/earnings/ZQNV/brief")
    assert reply.status_code == 429 and "3 assistant messages today" in reply.json()["detail"]
    assert calls == []


def test_an_allowed_write_is_counted_and_served(monkeypatch, claude):  # noqa: F811
    guarded = []
    monkeypatch.setattr(m, "_spend_guard", lambda request: guarded.append(1))
    claude.default = _msg(json.dumps(BRIEF))
    got = client.post("/api/earnings/ZQNW/brief").json()
    assert got["available"] is True and got["headline"] == "Into the report" and guarded == [1]
    assert len(claude.asked) == 1
    again = client.get("/api/earnings/ZQNW/brief").json()
    assert again["headline"] == "Into the report" and len(claude.asked) == 1, "kept, and read for free"


def test_simultaneous_requests_for_one_report_write_once(claude):  # noqa: F811
    claude.default = _msg(json.dumps(BRIEF))
    claude.delay = 0.3
    out = []
    threads = [threading.Thread(target=lambda: out.append(ai.write_earnings_brief("ZQNX", dict(FACTS))))
               for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(claude.asked) == 1
    assert len(out) == 5 and all(b["headline"] == "Into the report" for b in out)


def test_simultaneous_sector_reads_write_once(claude, monkeypatch):  # noqa: F811
    monkeypatch.setattr(ai, "_SECTOR_CACHE", {})
    claude.default = _msg(json.dumps({"headline": "h", "stance": "cautious", "paragraphs": ["p"]}))
    claude.delay = 0.3
    threads = [threading.Thread(target=lambda: ai.write_sector_read("ZQXL", {"row": {}})) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(claude.asked) == 1


def test_the_daily_ceiling_refuses_before_any_client_is_made(monkeypatch, claude):  # noqa: F811
    monkeypatch.setitem(ai.OPEN_WRITE_LIMITS, "earnings", 0)
    monkeypatch.setattr(m, "_spend_guard", lambda request: None)
    got = client.post("/api/earnings/ZQNY/brief").json()
    assert got["available"] is False and got["refused"] == "daily_ceiling" and claude.asked == []


def test_a_cross_site_post_with_a_session_is_refused(monkeypatch):
    calls = _no_write(monkeypatch)
    c = TestClient(m.app)
    c.cookies.set("optic_session", "x")
    reply = c.post("/api/earnings/ZQNV/brief")
    assert reply.status_code == 403 and calls == []


def test_a_junk_symbol_never_reaches_the_writer(monkeypatch):
    calls = _no_write(monkeypatch)
    assert client.get("/api/earnings/%3Cscript%3E/brief").status_code == 400
    assert client.post("/api/earnings/AAAAAAAAAAAAAAAAAA/brief").status_code == 400
    assert calls == []


def test_the_pages_read_free_and_write_on_a_press():
    from pathlib import Path
    root = Path(__file__).parent.parent
    v2 = (root / "static/v2/js/pages/earnings.js").read_text()
    assert "api.post(`/api/earnings/${encodeURIComponent(box.sym)}/brief`" in v2
    assert "b.error.kind === 'auth'" in v2 and "b.error.kind === 'limit'" in v2
    classic = (root / "static/app.js").read_text()
    assert "data-earn-brief-write" in classic and "method: 'POST'" in classic


# ---------------------------------------------- the review's findings, 2026-10-27


def test_a_full_ceiling_refuses_before_the_readers_allowance_is_touched(monkeypatch):
    guarded = []
    monkeypatch.setattr(m, "_spend_guard", lambda request: guarded.append(1))
    monkeypatch.setattr(ai, "available", lambda: {"enabled": True})
    monkeypatch.setitem(ai.OPEN_WRITE_LIMITS, "earnings", 0)
    got = client.post("/api/earnings/ZQRA/brief").json()
    assert got["refused"] == "daily_ceiling" and guarded == [], "no Milo message spent on a refusal"
    view = client.get("/api/earnings/ZQRA/brief").json()
    assert view["can_write"] is False and "switched off" in view["reason"], "the page offers no button to press"


def test_a_brief_being_written_is_waited_for_not_charged_twice(monkeypatch):
    guarded = []
    monkeypatch.setattr(m, "_spend_guard", lambda request: guarded.append(1))
    lock = ai._write_lock("earnings:" + ai.earnings_brief_key("ZQRB", FACTS))
    lock.acquire()

    def finish():
        time.sleep(0.3)
        ai._EARNINGS_CACHE[ai.earnings_brief_key("ZQRB", FACTS)] = {"at": time.time(), "brief": dict(BRIEF, available=True)}
        lock.release()
    threading.Thread(target=finish).start()
    got = client.post("/api/earnings/ZQRB/brief").json()
    assert got["headline"] == "Into the report" and guarded == []


def test_a_kept_brief_says_when_it_was_written(monkeypatch):
    from app import ai_store
    key = ai.earnings_brief_key("ZQRC", FACTS)
    ai_store.keep("earnings", key, dict(BRIEF, available=True))
    monkeypatch.setattr(ai, "_EARNINGS_CACHE", {})
    monkeypatch.setattr(ai_store, "kept", lambda kind, k, ttl=None: (dict(BRIEF, available=True), time.time() - 5 * 3600))
    got = client.get("/api/earnings/ZQRC/brief").json()
    from datetime import datetime, timezone
    age = datetime.now(timezone.utc) - datetime.fromisoformat(got["generated_at"])
    assert 4.9 * 3600 < age.total_seconds() < 5.1 * 3600, "not stamped with the time it was read"
