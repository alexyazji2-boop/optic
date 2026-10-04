"""Remember me on the sign-in form.

Asked for as "include a remember me for next time on the log-in page". Ticked
(the default), a sign-in is what every sign-in was: thirty days in a cookie that
outlives the browser, slid forward on use. Unticked, the cookie has no lifetime
of its own, so the browser drops it on closing, and the server ends the session
a day after it was last used. Password, passkey, Google and Apple all honour it.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.auth import config, oauth

client = TestClient(main.app)
ROOT = Path(__file__).resolve().parent.parent
AUTH_JS = (ROOT / "static/auth.js").read_text()
GOOD = "tungsten-carbide-9"


@pytest.fixture(autouse=True)
def fresh(accounts):
    client.cookies.clear()
    client.post("/api/auth/register", json={
        "first_name": "Ada", "last_name": "Reader", "email": "reader@example.com",
        "password": GOOD, "confirm_password": GOOD})
    client.cookies.clear()
    return accounts


def _session_cookie(reply):
    found = [c for c in reply.headers.get_list("set-cookie")
             if c.startswith(config.COOKIE_NAME + "=")]
    assert found, reply.headers.get_list("set-cookie")
    return found[-1]


def _hours_left(accounts):
    row = accounts.rows("SELECT expires_at, remember FROM sessions ORDER BY rowid DESC")[0]
    left = datetime.strptime(row["expires_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc) - datetime.now(timezone.utc)
    return left.total_seconds() / 3600, row["remember"]


def _login(remember=None):
    body = {"email": "reader@example.com", "password": GOOD}
    if remember is not None:
        body["remember"] = remember
    reply = client.post("/api/auth/login", json=body)
    assert reply.status_code == 200, reply.text
    return reply


def test_remembered_is_thirty_days_in_a_lasting_cookie(accounts):
    cookie = _session_cookie(_login(True))
    assert "Max-Age=%d" % config.SESSION_TTL in cookie and "HttpOnly" in cookie
    hours, remember = _hours_left(accounts)
    assert remember == 1 and hours > 29 * 24


def test_not_remembered_is_a_browser_session_cookie_and_a_day_on_the_server(accounts):
    cookie = _session_cookie(_login(False))
    assert "Max-Age" not in cookie and "expires" not in cookie.lower()
    assert "HttpOnly" in cookie
    hours, remember = _hours_left(accounts)
    assert remember == 0 and 23 < hours <= 24


def test_staying_on_the_site_does_not_turn_a_short_session_into_a_long_one(accounts):
    _login(False)
    reply = client.get("/api/auth/me")
    assert reply.json()["authenticated"] is True
    assert "Max-Age" not in _session_cookie(reply)
    hours, _ = _hours_left(accounts)
    assert hours <= 24


def test_a_caller_that_does_not_say_keeps_the_long_session(accounts):
    _login()
    hours, remember = _hours_left(accounts)
    assert remember == 1 and hours > 29 * 24


def test_google_carries_the_choice_through_the_round_trip(accounts, monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_CLIENT_ID", "client-id.apps.googleusercontent.com")
    monkeypatch.setattr(config, "GOOGLE_CLIENT_SECRET", "client-secret")
    monkeypatch.setattr(oauth, "complete", lambda *a, **k: {
        "provider": "google", "subject": "sub-9", "email": "new@example.com",
        "email_verified": True, "private_relay": False, "first_name": "New",
        "last_name": "Reader", "avatar_url": None})
    client.get("/api/auth/google/start", params={"remember": 0}, follow_redirects=False)
    row = accounts.rows("SELECT state, remember FROM oauth_states")[0]
    assert row["remember"] == 0
    reply = client.get("/api/auth/google/callback",
                       params={"code": "c", "state": row["state"]}, follow_redirects=False)
    assert "Max-Age" not in _session_cookie(reply)
    hours, remember = _hours_left(accounts)
    assert remember == 0 and hours <= 24


def test_the_form_has_the_box_ticked_and_sends_it_every_way_in():
    assert '<input type="checkbox" name="remember" checked>' in AUTH_JS
    assert "+ rememberField()" in AUTH_JS
    assert "remember: rememberChoice() }," in AUTH_JS, "the password"
    assert "body: { credential: assertion, remember: rememberChoice() }," in AUTH_JS, "a passkey"
    assert "(rememberChoice() ? '' : '&remember=0')" in AUTH_JS, "Google and Apple"
    assert "localStorage" not in AUTH_JS[AUTH_JS.index("function rememberField()"):
                                         AUTH_JS.index("function paint()")]
