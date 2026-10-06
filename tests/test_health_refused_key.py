"""A key Anthropic refuses is reported as not working, not as "Ask me anything".

Reproduced from the code before the fix: /api/health reported the assistant
`enabled` whenever a credential was present, revoked or not, and the page
greeted the reader with "Ask me anything" over a key whose first question would
fail. `ai.key_usable()` did check, but only scheduled jobs asked it. The status
now carries the last check's verdict, read from memory so a page load never
waits on Anthropic.
"""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

import app.main as main
from app import ai


def _present(monkeypatch):
    monkeypatch.setattr(ai, "available", lambda: {"enabled": True, "credential_source": "ANTHROPIC_API_KEY",
                                                  "hint": "", "model": "x"})


def test_a_refused_key_is_not_enabled(monkeypatch):
    _present(monkeypatch)
    monkeypatch.setitem(ai._KEY_CHECK, "usable", False)
    monkeypatch.setitem(ai._KEY_CHECK, "at", time.time())
    body = TestClient(main.app).get("/api/health").json()["assistant"]
    assert body["enabled"] is False and body["key_refused"] is True
    assert "refused the configured key" in body["hint"]


def test_an_accepted_or_unchecked_key_stays_enabled(monkeypatch):
    _present(monkeypatch)
    monkeypatch.setitem(ai._KEY_CHECK, "usable", True)
    monkeypatch.setitem(ai._KEY_CHECK, "at", time.time())
    assert TestClient(main.app).get("/api/health").json()["assistant"]["enabled"] is True


def test_the_status_read_never_waits_on_anthropic(monkeypatch):
    """Stale, it starts one check off the request and answers from memory."""
    _present(monkeypatch)
    monkeypatch.setitem(ai._KEY_CHECK, "usable", None)
    monkeypatch.setitem(ai._KEY_CHECK, "at", 0.0)
    started = []

    class NoThread:
        def __init__(self, target=None, name=None, daemon=None):
            started.append(name)

        def start(self):
            pass

    monkeypatch.setattr(ai.threading, "Thread", NoThread)
    ai._KEY_REFRESHING.clear()
    try:
        assert ai.key_refused() is False
        assert started == ["key-check"]
    finally:
        ai._KEY_REFRESHING.clear()
