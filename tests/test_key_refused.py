"""What the terminal says when Anthropic refuses its API key.

Reported as two error messages. The catalyst scan said "Catalyst extraction
failed on this attempt", and the weekly update said "The API key was rejected.
Check ANTHROPIC_API_KEY in .env, then restart the server so it is re-read."

Measured on 2026-09-28: the key in the local .env was well formed (one line, no
quotes, no stray whitespace), loaded, sent to api.anthropic.com from a clean
environment and refused as "API key is invalid". So the first message hid the
cause, and the second suggested a restart that could not help. On the public
site the second would also send a visitor to a file they cannot reach.
"""
from __future__ import annotations

import sys
import types

import pytest

from app import ai, catalysts

# Verbatim from the local server's refusal, as PRODUCTION_400 is in
# test_pulse_workspace.py, so the matcher meets what the API actually says.
REFUSED_401 = ("Error code: 401 - {'type': 'error', 'error': {'type': "
               "'authentication_error', 'message': 'API key is invalid.'}, "
               "'request_id': None}")
LOCAL_START = "Anthropic refused this server's API key as invalid"

PLATFORM = ("RAILWAY_ENVIRONMENT", "RAILWAY_GIT_COMMIT_SHA", "RENDER", "FLY_APP_NAME")


class AuthenticationError(Exception):
    """Shaped like the SDK's: the name and `status_code` are what is read."""
    status_code = 401


def _place(monkeypatch, hosted):
    for name in PLATFORM:
        monkeypatch.delenv(name, raising=False)
    if hosted:
        monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")


@pytest.fixture
def local(monkeypatch):
    _place(monkeypatch, False)


class _RefusingClient:
    def __init__(self, **kwargs):
        self.messages = self

    def create(self, **kwargs):
        raise AuthenticationError(REFUSED_401)


@pytest.fixture
def refusing(monkeypatch):
    monkeypatch.setitem(sys.modules, "anthropic",
                        types.SimpleNamespace(Anthropic=_RefusingClient))
    monkeypatch.setattr(ai, "available", lambda: {"enabled": True})


# ------------------------------------------------------------------ the copy


def test_locally_it_names_the_cause_and_what_will_fix_it(local):
    text = ai._human_error(AuthenticationError(REFUSED_401))
    assert text.startswith(LOCAL_START)
    assert "A restart alone will not fix it" in text
    assert "ANTHROPIC_API_KEY in .env" in text and "console.anthropic.com" in text


def test_on_the_public_site_it_does_not_send_a_visitor_to_a_file(monkeypatch):
    _place(monkeypatch, True)
    text = ai._human_error(AuthenticationError(REFUSED_401))
    assert ".env" not in text and "ANTHROPIC_API_KEY" not in text
    assert "asking again will not help" in text


@pytest.mark.parametrize("hosted", [False, True])
def test_the_old_sentence_is_gone_and_no_dash_came_with_the_new(monkeypatch, hosted):
    _place(monkeypatch, hosted)
    text = ai._human_error(AuthenticationError(REFUSED_401))
    assert "Check ANTHROPIC_API_KEY in .env" not in text
    assert "so it is re-read" not in text
    assert "—" not in text and "–" not in text


def test_the_status_alone_is_enough(local):
    """An SDK whose error text changes still carries the status."""
    assert ai._human_error(AuthenticationError("new wording")).startswith(LOCAL_START)


# ------------------------------------------------------------------ the paths


def test_the_catalyst_extractor_returns_the_reason_not_none(local, refusing):
    out = ai.extract_catalysts([{"id": "s1", "title": "t", "summary": "",
                                 "source": "x", "published": "2026-09-28"}], [])
    assert out == {"available": False,
                   "reason": ai._human_error(AuthenticationError(REFUSED_401))}


def test_the_scan_button_prints_it_and_the_record_keeps_it(local, refusing, tmp_path,
                                                           monkeypatch):
    """The whole path the button takes, with only the network faked."""
    monkeypatch.setattr(catalysts, "DB_PATH", str(tmp_path / "catalysts.db"))
    monkeypatch.setattr(catalysts, "candidate_stories", lambda hours=168: [{
        "id": "s1", "title": "t", "summary": "", "source": "x", "desk": "",
        "published": "2026-09-28T10:00:00+00:00", "url": "https://x.example/1",
        "access": "open"}])
    out = catalysts.refresh(trigger="manual")
    assert out["available"] is False and out["reason"].startswith(LOCAL_START)
    assert catalysts.search()["scan"]["last_reason"] == out["reason"]


def test_an_answer_the_library_cannot_read_says_so(local, monkeypatch, tmp_path):
    """The one failure left without a named cause still says what happened."""
    monkeypatch.setattr(catalysts, "DB_PATH", str(tmp_path / "catalysts.db"))
    monkeypatch.setattr(catalysts, "candidate_stories", lambda hours=168: [{
        "id": "s1", "title": "t", "summary": "", "source": "x", "desk": "",
        "published": "2026-09-28T10:00:00+00:00", "url": "https://x.example/1",
        "access": "open"}])
    monkeypatch.setattr(ai, "extract_catalysts", lambda stories, library: None)
    monkeypatch.setattr(ai, "available", lambda: {"enabled": True})
    assert catalysts.refresh(trigger="manual")["reason"] == catalysts._UNREADABLE
    assert "failed on this attempt" not in catalysts._UNREADABLE


def test_the_weekly_panel_receives_it(local, refusing, monkeypatch):
    import app.main as main
    from fastapi.testclient import TestClient
    monkeypatch.setattr(main.weekly_mod, "gather", lambda provider: {"spy": {}})
    monkeypatch.setattr(ai, "_WEEKLY_CACHE", {})
    body = TestClient(main.app).get("/api/weekly").json()
    assert body["available"] is False and body["reason"].startswith(LOCAL_START)
