"""Throttles on the endpoints an attacker calls for free.

The interesting properties are not "does it stop at N". They are: does the limit
survive a restart, does changing address get you a fresh allowance for the same
account, and does a successful sign-in clear the typos that came before it.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.main as main
from app.auth import ratelimit as rl

client = TestClient(main.app)

GOOD = "tungsten-carbide-9"


@pytest.fixture(autouse=True)
def fresh(accounts):
    client.cookies.clear()
    return accounts


class Caller:
    """A request object with just what the limiter reads."""

    def __init__(self, ip="203.0.113.9"):
        self.headers = {"x-forwarded-for": ip}
        self.client = None


def test_the_login_limit_stops_at_its_ceiling():
    allowed, _window = rl.LIMITS["login"]
    caller = Caller()
    for _ in range(allowed):
        rl.guard(caller, "login", "victim@example.com")
    with pytest.raises(HTTPException) as caught:
        rl.guard(caller, "login", "victim@example.com")
    assert caught.value.status_code == 429
    assert "Retry-After" in caught.value.headers


def test_the_account_bucket_survives_a_change_of_address():
    """Rate-limiting by address alone is defeated by anyone with a few of them."""
    allowed, _ = rl.LIMITS["login"]
    for i in range(allowed):
        rl.guard(Caller("198.51.100.{}".format(i)), "login", "victim@example.com")
    with pytest.raises(HTTPException):
        rl.guard(Caller("198.51.100.250"), "login", "victim@example.com")
    # A different account from a fresh address is unaffected.
    rl.guard(Caller("198.51.100.251"), "login", "someone-else@example.com")


def test_the_address_bucket_survives_a_change_of_account():
    """And limiting by account alone lets one address walk the user list."""
    allowed, _ = rl.LIMITS["login"]
    caller = Caller("203.0.113.44")
    for i in range(allowed):
        rl.guard(caller, "login", "target{}@example.com".format(i))
    with pytest.raises(HTTPException):
        rl.guard(caller, "login", "another@example.com")


def test_the_counter_is_in_the_database_not_in_memory():
    """The service is OOM-killed periodically (see DEPLOY.md), so an in-memory
    counter is reset by an event the attacker does not have to cause."""
    rl.guard(Caller(), "login", "victim@example.com")
    rows = main.accounts_db.rows("SELECT kind, bucket FROM auth_attempts")
    assert len(rows) == 2                       # one for the address, one for the account
    assert all(r["kind"] == "login" for r in rows)


def test_buckets_are_stored_hashed_so_the_table_is_not_a_visitor_log():
    rl.guard(Caller("203.0.113.77"), "login", "victim@example.com")
    stored = [r["bucket"] for r in main.accounts_db.rows("SELECT bucket FROM auth_attempts")]
    assert "203.0.113.77" not in stored
    assert "victim@example.com" not in str(stored)
    assert all(len(b) == 32 for b in stored)


def test_attempts_outside_the_window_no_longer_count():
    allowed, window = rl.LIMITS["login"]
    caller = Caller()
    for _ in range(allowed):
        rl.guard(caller, "login", "victim@example.com")
    main.accounts_db.execute(
        "UPDATE auth_attempts SET created_at = ?",
        (main.accounts_db.in_seconds(-(window + 60)),))
    rl.guard(caller, "login", "victim@example.com")     # no raise


def test_a_successful_sign_in_clears_the_typos_before_it():
    client.post("/api/auth/register", json={
        "first_name": "A", "email": "reader@example.com",
        "password": GOOD, "confirm_password": GOOD})
    client.cookies.clear()
    allowed, _ = rl.LIMITS["login"]
    for _ in range(allowed - 1):
        client.post("/api/auth/login",
                    json={"email": "reader@example.com", "password": "wrong"})
    assert client.post("/api/auth/login",
                       json={"email": "reader@example.com",
                             "password": GOOD}).status_code == 200
    # Not one retry away from a lockout after proving who they are.
    client.cookies.clear()
    for _ in range(3):
        assert client.post("/api/auth/login",
                           json={"email": "reader@example.com",
                                 "password": "wrong"}).status_code == 401


def test_login_over_http_returns_429_with_a_readable_message():
    allowed, _ = rl.LIMITS["login"]
    for _ in range(allowed):
        client.post("/api/auth/login", json={"email": "x@example.com", "password": "p"})
    reply = client.post("/api/auth/login", json={"email": "x@example.com", "password": "p"})
    assert reply.status_code == 429
    assert "Wait about" in reply.json()["detail"]
    assert reply.headers["Retry-After"]


def test_registration_is_limited_too():
    allowed, _ = rl.LIMITS["register"]
    for i in range(allowed):
        client.cookies.clear()
        client.post("/api/auth/register", json={
            "first_name": "A", "email": "r{}@example.com".format(i),
            "password": GOOD, "confirm_password": GOOD})
    client.cookies.clear()
    reply = client.post("/api/auth/register", json={
        "first_name": "A", "email": "one-too-many@example.com",
        "password": GOOD, "confirm_password": GOOD})
    assert reply.status_code == 429


def test_forgot_password_is_limited_so_it_is_not_a_free_mail_cannon():
    allowed, _ = rl.LIMITS["forgot"]
    for _ in range(allowed):
        client.post("/api/auth/forgot-password", json={"email": "reader@example.com"})
    reply = client.post("/api/auth/forgot-password", json={"email": "reader@example.com"})
    assert reply.status_code == 429


def test_passkey_challenges_are_limited():
    allowed, _ = rl.LIMITS["passkey_challenge"]
    for _ in range(allowed):
        client.post("/api/auth/passkeys/login/options")
    assert client.post("/api/auth/passkeys/login/options").status_code == 429


def test_oauth_start_is_limited():
    allowed, _ = rl.LIMITS["oauth_start"]
    for _ in range(allowed):
        client.get("/api/auth/google/start", follow_redirects=False)
    assert client.get("/api/auth/google/start",
                      follow_redirects=False).status_code == 429


def test_attempts_are_recorded_on_the_attempt_not_on_failure():
    """Counting only failures means alternating a wrong password with a right
    one never fills the bucket."""
    source = open("app/auth/ratelimit.py").read()
    assert "Recording happens here, on the attempt" in source
    caller = Caller()
    rl.guard(caller, "login", "victim@example.com")
    assert rl.count("login", "203.0.113.9") == 1


def test_the_sweep_removes_attempts_older_than_a_day():
    rl.guard(Caller(), "login", "victim@example.com")
    main.accounts_db.execute("UPDATE auth_attempts SET created_at = ?",
                             (main.accounts_db.in_seconds(-90000),))
    removed = main.accounts_db.sweep()
    assert removed["auth_attempts"] == 2
    assert main.accounts_db.rows("SELECT 1 FROM auth_attempts") == []


def test_no_account_is_ever_locked():
    """A lockout on failed attempts is a denial of service against a named
    person: anyone who knows an address can lock its owner out on demand. The
    window expires on its own instead."""
    source = open("app/auth/ratelimit.py").read()
    assert "It does not lock accounts" in source
    assert "locked_until" not in source
    assert "is_locked" not in source
