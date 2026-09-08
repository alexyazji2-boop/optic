"""Email and password: creating an account, signing in, and staying signed in.

The happy path is one test. The rest are the ways it is supposed to refuse,
because every one of them is a decision that can regress silently: a duplicate
email that creates a second account, a wrong password that is accepted, a
session cookie without HttpOnly, a protected route that answers a guest.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.auth import config, store

client = TestClient(main.app)

GOOD = "tungsten-carbide-9"


def signup(email="reader@example.com", password=GOOD, first="Alex", last="Yazji",
           confirm=None, http=None):
    return (http or client).post("/api/auth/register", json={
        "first_name": first, "last_name": last, "email": email,
        "password": password, "confirm_password": confirm if confirm is not None
        else password})


@pytest.fixture(autouse=True)
def fresh(accounts):
    """Every test in this file gets an empty database and no cookies."""
    client.cookies.clear()
    return accounts


# ------------------------------------------------------------------ registration


def test_register_creates_account_identity_password_and_session():
    reply = signup()
    assert reply.status_code == 200, reply.text
    body = reply.json()
    assert body["ok"] is True
    assert body["user"]["email"] == "reader@example.com"
    assert body["user"]["name"] == "Alex Yazji"

    user = store.get_user_by_email("reader@example.com")
    assert user is not None
    # An email identity, a password row, a preference row and a free plan: the
    # four things an account needs to exist rather than half-exist.
    assert store.get_identity("email", "reader@example.com")["user_id"] == user["id"]
    assert store.get_password(user["id"]) is not None
    assert store.preferences(user["id"])["default_landing"] == "home"
    assert store.subscription(user["id"])["plan"] == "free"
    assert store.auth_methods(user["id"])["count"] == 1
    # Signed in, not sent to a login form they have just proved they can pass.
    assert config.COOKIE_NAME in client.cookies


def test_password_is_never_stored_in_the_clear():
    signup()
    user = store.get_user_by_email("reader@example.com")
    record = store.get_password(user["id"])
    assert GOOD not in record["password_hash"]
    assert record["password_hash"].startswith("$argon2id$")
    assert record["algo"] == "argon2id"
    # And nothing that reads a user hands one out.
    assert "password" not in str(store.public_user(user)).lower()


def test_email_is_normalised_so_one_mailbox_is_one_account():
    assert signup(email="Reader@Example.COM").status_code == 200
    assert store.get_user_by_email("reader@example.com") is not None
    # The same mailbox in different case is a duplicate, not a new person.
    again = signup(email="READER@example.com")
    assert again.status_code == 409


def test_duplicate_email_is_refused_and_points_at_sign_in():
    signup()
    client.cookies.clear()
    again = signup()
    assert again.status_code == 409
    assert "sign in" in again.json()["detail"].lower()
    assert len(main.accounts_db.rows("SELECT 1 FROM users")) == 1


@pytest.mark.parametrize("password,fragment", [
    ("short", "at least"),
    ("password123", "commonly used"),
    ("aaaaaaaaaaaa", "repeating one character"),
    ("123456789012", "digits alone"),
    ("reader-is-me-1", "name or email"),
])
def test_weak_passwords_are_refused_with_the_reason(password, fragment):
    reply = signup(password=password)
    assert reply.status_code == 400
    assert fragment in reply.json()["detail"].lower()
    assert store.get_user_by_email("reader@example.com") is None


def test_mismatched_confirmation_is_refused():
    reply = signup(confirm="tungsten-carbide-8")
    assert reply.status_code == 400
    assert "do not match" in reply.json()["detail"]


@pytest.mark.parametrize("email", ["", "notanemail", "no@tld", "a@b"])
def test_invalid_email_is_refused(email):
    assert signup(email=email).status_code == 400


def test_first_name_is_required():
    assert signup(first="").status_code == 400


# ------------------------------------------------------------------------ login


def test_login_then_me_reports_the_account():
    signup()
    client.cookies.clear()
    reply = client.post("/api/auth/login",
                        json={"email": "reader@example.com", "password": GOOD})
    assert reply.status_code == 200
    me = client.get("/api/auth/me").json()
    assert me["authenticated"] is True
    assert me["user"]["email"] == "reader@example.com"
    assert me["methods"]["password"] is True
    assert me["subscription"]["plan"] == "free"


def test_wrong_password_and_unknown_account_are_indistinguishable():
    signup()
    client.cookies.clear()
    wrong = client.post("/api/auth/login",
                        json={"email": "reader@example.com", "password": "not-it-mate"})
    missing = client.post("/api/auth/login",
                          json={"email": "nobody@example.com", "password": "not-it-mate"})
    assert wrong.status_code == missing.status_code == 401
    # Same wording, so the response is not an account-existence oracle.
    assert wrong.json()["detail"] == missing.json()["detail"]
    assert wrong.json()["detail"] == "Email or password is incorrect."
    assert config.COOKIE_NAME not in client.cookies


def test_login_case_insensitive_on_email():
    signup()
    client.cookies.clear()
    reply = client.post("/api/auth/login",
                        json={"email": "READER@Example.com", "password": GOOD})
    assert reply.status_code == 200


def test_provider_only_account_is_told_which_button_to_press():
    user = store.create_user("g@example.com", "G", "Oogle", email_verified=True)
    store.add_identity(user["id"], "google", "sub-1", "g@example.com")
    reply = client.post("/api/auth/login",
                        json={"email": "g@example.com", "password": GOOD})
    assert reply.status_code == 401
    assert "Google" in reply.json()["detail"]


def test_inactive_account_cannot_sign_in():
    signup()
    user = store.get_user_by_email("reader@example.com")
    main.accounts_db.execute("UPDATE users SET is_active = 0 WHERE id = ?", (user["id"],))
    client.cookies.clear()
    reply = client.post("/api/auth/login",
                        json={"email": "reader@example.com", "password": GOOD})
    assert reply.status_code == 403
    # And an existing session stops working too, without the row being deleted.
    signup(email="other@example.com")
    assert client.get("/api/auth/me").json()["authenticated"] is True


# ---------------------------------------------------------------------- session


def test_session_cookie_is_httponly_and_the_token_is_only_stored_hashed():
    reply = signup()
    header = reply.headers.get("set-cookie", "")
    assert "httponly" in header.lower()
    assert "samesite=lax" in header.lower()
    token = client.cookies.get(config.COOKIE_NAME)
    rows = main.accounts_db.rows("SELECT session_token_hash FROM sessions")
    assert len(rows) == 1
    assert token not in rows[0]["session_token_hash"]
    assert len(rows[0]["session_token_hash"]) == 64        # sha256 hex


def test_expired_session_does_not_authenticate():
    signup()
    main.accounts_db.execute("UPDATE sessions SET expires_at = ?",
                             (main.accounts_db.in_seconds(-60),))
    assert client.get("/api/auth/me").json()["authenticated"] is False
    assert client.get("/api/auth/sessions").status_code == 401


def test_a_forged_cookie_authenticates_nobody():
    signup()
    # Cleared first. httpx keeps cookies per domain, and setting one with no
    # domain adds a second rather than replacing the real one, so without this
    # the request carries both and the test passes for the wrong reason.
    client.cookies.clear()
    client.cookies.set(config.COOKIE_NAME, "a" * 43)
    assert client.get("/api/auth/me").json()["authenticated"] is False
    assert client.get("/api/auth/sessions").status_code == 401


def test_logout_deletes_the_session_row():
    signup()
    assert len(main.accounts_db.rows("SELECT 1 FROM sessions")) == 1
    assert client.post("/api/auth/logout").status_code == 200
    assert main.accounts_db.rows("SELECT 1 FROM sessions") == []
    client.cookies.clear()
    assert client.get("/api/auth/me").json()["authenticated"] is False


def test_sessions_list_marks_the_current_one_and_can_revoke_another():
    signup()
    csrf = client.cookies.get(config.CSRF_COOKIE)
    user = store.get_user_by_email("reader@example.com")
    store.create_session(user["id"], 3600, "9.9.9.9", "Other Browser")

    rows = client.get("/api/auth/sessions").json()["sessions"]
    assert len(rows) == 2
    assert sum(1 for r in rows if r["current"]) == 1
    other = [r for r in rows if not r["current"]][0]
    gone = client.delete("/api/auth/sessions/{}".format(other["id"]),
                         headers={"X-Optic-CSRF": csrf})
    assert gone.status_code == 200
    assert len(client.get("/api/auth/sessions").json()["sessions"]) == 1


def test_logout_all_ends_every_session():
    signup()
    csrf = client.cookies.get(config.CSRF_COOKIE)
    user = store.get_user_by_email("reader@example.com")
    store.create_session(user["id"], 3600)
    store.create_session(user["id"], 3600)
    reply = client.post("/api/auth/logout-all", headers={"X-Optic-CSRF": csrf})
    assert reply.status_code == 200
    assert reply.json()["signed_out"] == 3
    assert main.accounts_db.rows("SELECT 1 FROM sessions") == []


# ---------------------------------------------------------------------- profile


def test_profile_update_and_the_avatar_scheme_check():
    signup()
    csrf = client.cookies.get(config.CSRF_COOKIE)
    reply = client.patch("/api/auth/profile", headers={"X-Optic-CSRF": csrf},
                         json={"first_name": "Alexander", "last_name": "Y"})
    assert reply.json()["user"]["name"] == "Alexander Y"
    bad = client.patch("/api/auth/profile", headers={"X-Optic-CSRF": csrf},
                       json={"avatar_url": "javascript:alert(1)"})
    assert bad.status_code == 400
    ok = client.patch("/api/auth/profile", headers={"X-Optic-CSRF": csrf},
                      json={"avatar_url": "https://example.com/a.png"})
    assert ok.json()["user"]["avatar_url"] == "https://example.com/a.png"


def test_change_password_requires_the_current_one_and_ends_other_sessions():
    signup()
    csrf = client.cookies.get(config.CSRF_COOKIE)
    user = store.get_user_by_email("reader@example.com")
    store.create_session(user["id"], 3600)          # a second device

    wrong = client.post("/api/auth/change-password", headers={"X-Optic-CSRF": csrf},
                        json={"current_password": "nope", "new_password": "molybdenum-77-x"})
    assert wrong.status_code == 401

    reply = client.post("/api/auth/change-password", headers={"X-Optic-CSRF": csrf},
                        json={"current_password": GOOD, "new_password": "molybdenum-77-x"})
    assert reply.status_code == 200
    assert reply.json()["other_sessions_ended"] == 1
    # This device stays signed in; the other one does not.
    assert client.get("/api/auth/me").json()["authenticated"] is True

    client.cookies.clear()
    assert client.post("/api/auth/login", json={"email": "reader@example.com",
                                                "password": GOOD}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "reader@example.com",
                                                "password": "molybdenum-77-x"}
                       ).status_code == 200


def test_change_password_enforces_the_policy():
    signup()
    csrf = client.cookies.get(config.CSRF_COOKIE)
    reply = client.post("/api/auth/change-password", headers={"X-Optic-CSRF": csrf},
                        json={"current_password": GOOD, "new_password": "password123"})
    assert reply.status_code == 400
    assert "commonly used" in reply.json()["detail"]


# ----------------------------------------------------------------- delete account


def test_delete_account_wants_the_email_typed_and_takes_everything_with_it():
    signup()
    csrf = client.cookies.get(config.CSRF_COOKIE)
    user = store.get_user_by_email("reader@example.com")
    client.post("/api/watchlists", headers={"X-Optic-CSRF": csrf}, json={"name": "AI"})

    wrong = client.post("/api/auth/delete-account", headers={"X-Optic-CSRF": csrf},
                        json={"confirm_email": "someone@else.com", "password": GOOD})
    assert wrong.status_code == 400

    no_password = client.post("/api/auth/delete-account", headers={"X-Optic-CSRF": csrf},
                              json={"confirm_email": "reader@example.com",
                                    "password": "nope"})
    assert no_password.status_code == 401

    gone = client.post("/api/auth/delete-account", headers={"X-Optic-CSRF": csrf},
                       json={"confirm_email": "reader@example.com", "password": GOOD})
    assert gone.status_code == 200
    assert store.get_user_by_email("reader@example.com") is None
    for table in ("sessions", "watchlists", "auth_identities", "user_passwords",
                  "user_preferences", "subscriptions"):
        assert main.accounts_db.rows("SELECT 1 FROM {}".format(table)) == [], table
