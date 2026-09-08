"""Password reset and email verification: the one-time links.

Both are the same shape and both fail the same interesting ways, so they are
tested together: a token that works twice, a token that outlives its window, a
token that leaks whether an address has an account, and a reset that leaves the
intruder's session alive.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.auth import config, mailer, store

client = TestClient(main.app)

GOOD = "tungsten-carbide-9"
NEXT = "molybdenum-77-x"


@pytest.fixture(autouse=True)
def fresh(accounts):
    client.cookies.clear()
    return accounts


@pytest.fixture
def outbox(monkeypatch):
    """Capture what would have been sent, including the link.

    Patched on the module rather than faking SMTP: the routes call
    `mailer.send` through the module object, so this is the same seam the real
    backend switch uses."""
    sent = []

    def fake_send(to, subject, body, link=None):
        sent.append({"to": to, "subject": subject, "body": body, "link": link})
        return True

    monkeypatch.setattr(mailer, "send", fake_send)
    monkeypatch.setattr(mailer, "available",
                        lambda: {"available": True, "backend": "smtp", "host": "test"})
    return sent


def signup(email="reader@example.com"):
    return client.post("/api/auth/register", json={
        "first_name": "Alex", "last_name": "Yazji", "email": email,
        "password": GOOD, "confirm_password": GOOD})


def token_from(link):
    return link.split("=", 1)[1]


# ------------------------------------------------------------------ verification


def test_signup_sends_a_verification_link_and_the_token_verifies_once(outbox):
    signup()
    assert len(outbox) == 1
    assert "Verify your email" in outbox[0]["subject"]
    assert "/?verify=" in outbox[0]["link"]

    user = store.get_user_by_email("reader@example.com")
    assert user["email_verified"] == 0

    token = token_from(outbox[0]["link"])
    assert client.post("/api/auth/verify-email", json={"token": token}).status_code == 200
    assert store.get_user_by_email("reader@example.com")["email_verified"] == 1

    again = client.post("/api/auth/verify-email", json={"token": token})
    assert again.status_code == 400
    assert "already been used" in again.json()["detail"]


def test_expired_verification_token_is_refused(outbox):
    signup()
    token = token_from(outbox[0]["link"])
    main.accounts_db.execute("UPDATE email_verifications SET expires_at = ?",
                             (main.accounts_db.in_seconds(-10),))
    reply = client.post("/api/auth/verify-email", json={"token": token})
    assert reply.status_code == 400
    assert store.get_user_by_email("reader@example.com")["email_verified"] == 0


def test_verification_tokens_are_stored_hashed(outbox):
    signup()
    token = token_from(outbox[0]["link"])
    rows = main.accounts_db.rows("SELECT token_hash FROM email_verifications")
    assert len(rows) == 1
    assert token not in rows[0]["token_hash"]
    assert len(rows[0]["token_hash"]) == 64


def test_resend_replaces_the_outstanding_token(outbox):
    signup()
    first = token_from(outbox[0]["link"])
    csrf = client.cookies.get(config.CSRF_COOKIE)
    assert client.post("/api/auth/resend-verification",
                       headers={"X-Optic-CSRF": csrf}).status_code == 200
    second = token_from(outbox[-1]["link"])
    assert first != second
    # Two live links in two inboxes is one more than anyone needs.
    assert client.post("/api/auth/verify-email", json={"token": first}).status_code == 400
    assert client.post("/api/auth/verify-email", json={"token": second}).status_code == 200


def test_resend_needs_a_session():
    assert client.post("/api/auth/resend-verification").status_code == 401


# ---------------------------------------------------------------------- reset


def test_reset_link_sets_a_new_password_and_signs_every_device_out(outbox):
    signup()
    user = store.get_user_by_email("reader@example.com")
    store.create_session(user["id"], 3600)               # a second device
    client.cookies.clear()
    outbox.clear()

    asked = client.post("/api/auth/forgot-password",
                        json={"email": "reader@example.com"})
    assert asked.status_code == 200
    reset_link = [m for m in outbox if "reset" in m["subject"].lower()][0]["link"]
    token = token_from(reset_link)

    assert client.get("/api/auth/reset/check", params={"token": token}
                      ).json()["valid"] is True

    reply = client.post("/api/auth/reset-password",
                        json={"token": token, "password": NEXT, "confirm_password": NEXT})
    assert reply.status_code == 200
    # The sessions that existed before the reset are gone. Someone resetting a
    # password usually believes another person is holding it.
    assert len(main.accounts_db.rows("SELECT 1 FROM sessions")) == 1
    assert client.get("/api/auth/me").json()["authenticated"] is True

    client.cookies.clear()
    assert client.post("/api/auth/login", json={"email": "reader@example.com",
                                                "password": GOOD}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "reader@example.com",
                                                "password": NEXT}).status_code == 200


def test_reset_token_is_single_use(outbox):
    signup()
    client.cookies.clear()
    outbox.clear()
    client.post("/api/auth/forgot-password", json={"email": "reader@example.com"})
    token = token_from([m for m in outbox if "reset" in m["subject"].lower()][0]["link"])

    assert client.post("/api/auth/reset-password",
                       json={"token": token, "password": NEXT,
                             "confirm_password": NEXT}).status_code == 200
    again = client.post("/api/auth/reset-password",
                        json={"token": token, "password": "another-good-one-42",
                              "confirm_password": "another-good-one-42"})
    assert again.status_code == 400
    assert "expired or has already been used" in again.json()["detail"]


def test_expired_reset_token_says_so(outbox):
    signup()
    client.cookies.clear()
    outbox.clear()
    client.post("/api/auth/forgot-password", json={"email": "reader@example.com"})
    token = token_from([m for m in outbox if "reset" in m["subject"].lower()][0]["link"])
    main.accounts_db.execute("UPDATE password_resets SET expires_at = ?",
                             (main.accounts_db.in_seconds(-10),))
    assert client.get("/api/auth/reset/check", params={"token": token}
                      ).json()["valid"] is False
    reply = client.post("/api/auth/reset-password",
                        json={"token": token, "password": NEXT, "confirm_password": NEXT})
    assert reply.status_code == 400
    assert "expired" in reply.json()["detail"].lower()


def test_reset_verifies_the_address_because_it_proves_mailbox_control(outbox):
    signup()
    client.cookies.clear()
    outbox.clear()
    client.post("/api/auth/forgot-password", json={"email": "reader@example.com"})
    token = token_from([m for m in outbox if "reset" in m["subject"].lower()][0]["link"])
    client.post("/api/auth/reset-password",
                json={"token": token, "password": NEXT, "confirm_password": NEXT})
    assert store.get_user_by_email("reader@example.com")["email_verified"] == 1


def test_reset_enforces_the_password_policy(outbox):
    signup()
    client.cookies.clear()
    outbox.clear()
    client.post("/api/auth/forgot-password", json={"email": "reader@example.com"})
    token = token_from([m for m in outbox if "reset" in m["subject"].lower()][0]["link"])
    reply = client.post("/api/auth/reset-password",
                        json={"token": token, "password": "qwerty",
                              "confirm_password": "qwerty"})
    assert reply.status_code == 400
    # And the token survives a refusal, so a weak first try is not a wasted link.
    assert client.get("/api/auth/reset/check", params={"token": token}
                      ).json()["valid"] is True


def test_forgot_password_does_not_reveal_whether_the_address_exists(outbox):
    signup()
    client.cookies.clear()
    outbox.clear()
    known = client.post("/api/auth/forgot-password", json={"email": "reader@example.com"})
    unknown = client.post("/api/auth/forgot-password", json={"email": "ghost@example.com"})
    assert known.status_code == unknown.status_code == 200
    assert known.json()["message"] == unknown.json()["message"]
    # One email was actually sent, and only one.
    assert len([m for m in outbox if "reset" in m["subject"].lower()]) == 1


def test_forgot_password_on_a_provider_only_account_explains_rather_than_looping():
    user = store.create_user("g@example.com", "G", "Oogle", email_verified=True)
    store.add_identity(user["id"], "google", "sub-1", "g@example.com")
    reply = client.post("/api/auth/forgot-password", json={"email": "g@example.com"})
    assert reply.status_code == 200
    assert "Google" in reply.json()["message"]
    assert main.accounts_db.rows("SELECT 1 FROM password_resets") == []


def test_a_changed_password_is_notified_by_email(outbox):
    signup()
    csrf = client.cookies.get(config.CSRF_COOKIE)
    outbox.clear()
    client.post("/api/auth/change-password", headers={"X-Optic-CSRF": csrf},
                json={"current_password": GOOD, "new_password": NEXT})
    assert any("password was changed" in m["subject"] for m in outbox)


# --------------------------------------------------------------- no mail backend


def test_without_smtp_the_link_is_reported_as_unsent_rather_than_claimed(monkeypatch):
    monkeypatch.setattr(mailer, "SMTP_HOST", "")
    reply = signup()
    assert reply.status_code == 200
    body = reply.json()
    # The account exists and the reader is signed in; the claim about the email
    # is the honest one.
    assert body["verification_sent"] is False
    assert body["mail"]["available"] is False
    assert "server log" in body["mail"]["reason"]
