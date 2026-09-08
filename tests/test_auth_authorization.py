"""Who may read what, and what happens when they try anyway.

Two accounts, and every owned resource asked for across the boundary. The
answers are all 404 rather than 403: telling a caller "that exists but is not
yours" is telling them it exists.

Also here: the SQL-injection attempts, the CSRF check, and the guarantee that
guests keep the whole research surface. That last one is a real regression risk
— adding accounts to an app is exactly when somebody wraps the wrong router in
a login check.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.auth import config, store

client = TestClient(main.app)
other = TestClient(main.app)

GOOD = "tungsten-carbide-9"


@pytest.fixture(autouse=True)
def fresh(accounts):
    client.cookies.clear()
    other.cookies.clear()
    return accounts


def register(http, email):
    http.post("/api/auth/register", json={
        "first_name": "A", "last_name": "B", "email": email,
        "password": GOOD, "confirm_password": GOOD})
    return http.cookies.get(config.CSRF_COOKIE)


@pytest.fixture
def two_accounts():
    mine = register(client, "mine@example.com")
    theirs = register(other, "theirs@example.com")
    return {"mine": mine, "theirs": theirs}


# ------------------------------------------------------- protected vs open


PROTECTED = [
    ("get", "/api/auth/sessions"),
    ("get", "/api/auth/identities"),
    ("get", "/api/auth/passkeys"),
    ("get", "/api/auth/preferences"),
    ("get", "/api/auth/subscription"),
    ("get", "/api/watchlists"),
    ("get", "/api/saved-research"),
    ("patch", "/api/auth/profile"),
    ("patch", "/api/auth/preferences"),
    ("post", "/api/auth/change-password"),
    ("post", "/api/auth/resend-verification"),
    ("post", "/api/auth/logout-all"),
    ("post", "/api/auth/delete-account"),
    ("post", "/api/watchlists"),
    ("post", "/api/watchlists/adopt"),
    ("post", "/api/saved-research"),
    ("post", "/api/auth/passkeys/register/options"),
]


@pytest.mark.parametrize("method,path", PROTECTED)
def test_protected_routes_refuse_a_guest(method, path):
    # httpx.get takes no json= argument, so the body only goes on the verbs
    # that have one. Passing it anyway raises TypeError and the test passes for
    # the wrong reason, which is how this was caught.
    if method == "get":
        reply = client.get(path)
    else:
        reply = getattr(client, method)(path, json={})
    assert reply.status_code == 401, path
    assert "Sign in" in reply.json()["detail"]


OPEN = ["/api/health", "/api/session", "/api/legal", "/api/auth/providers",
        "/api/auth/me", "/api/ai-allowance", "/api/watches/catalogue"]


@pytest.mark.parametrize("path", OPEN)
def test_the_research_surface_stays_open_to_guests(path):
    """Adding accounts must not put a wall in front of the terminal."""
    assert client.get(path).status_code == 200, path


def test_guest_me_is_a_plain_negative_not_an_error():
    body = client.get("/api/auth/me").json()
    assert body["authenticated"] is False
    assert body["user"] is None
    # Enough to render the login screen correctly on the first paint.
    assert "providers" in body and "password_policy" in body


# ------------------------------------------------------------- cross-account


def test_one_account_cannot_read_or_change_anothers_watchlist(two_accounts):
    made = client.post("/api/watchlists", headers={"X-Optic-CSRF": two_accounts["mine"]},
                       json={"name": "AI", "symbols": ["NVDA", "AMD"]})
    list_id = made.json()["watchlist"]["id"]

    theirs = two_accounts["theirs"]
    assert other.get("/api/watchlists").json()["watchlists"] == []
    assert other.patch("/api/watchlists/{}".format(list_id),
                       headers={"X-Optic-CSRF": theirs},
                       json={"name": "Mine now"}).status_code == 404
    assert other.delete("/api/watchlists/{}".format(list_id),
                        headers={"X-Optic-CSRF": theirs}).status_code == 404
    assert other.post("/api/watchlists/{}/items".format(list_id),
                      headers={"X-Optic-CSRF": theirs},
                      json={"symbol": "TSLA"}).status_code == 404
    assert other.delete("/api/watchlists/{}/items/NVDA".format(list_id),
                        headers={"X-Optic-CSRF": theirs}).status_code == 404
    # Untouched.
    assert client.get("/api/watchlists").json()["watchlists"][0]["symbols"] == ["NVDA", "AMD"]


def test_one_account_cannot_read_or_delete_anothers_research(two_accounts):
    saved = client.post("/api/saved-research", headers={"X-Optic-CSRF": two_accounts["mine"]},
                        json={"title": "NVDA read", "symbol": "NVDA",
                              "content": "private thinking"})
    research_id = saved.json()["research"]["id"]

    assert other.get("/api/saved-research").json()["research"] == []
    assert other.get("/api/saved-research/{}".format(research_id)).status_code == 404
    assert other.delete("/api/saved-research/{}".format(research_id),
                        headers={"X-Optic-CSRF": two_accounts["theirs"]}
                        ).status_code == 404
    body = client.get("/api/saved-research/{}".format(research_id)).json()
    assert body["research"]["content"] == "private thinking"


def test_one_account_cannot_revoke_anothers_session(two_accounts):
    mine = client.get("/api/auth/sessions").json()["sessions"][0]["id"]
    assert other.delete("/api/auth/sessions/{}".format(mine),
                        headers={"X-Optic-CSRF": two_accounts["theirs"]}
                        ).status_code == 404
    assert client.get("/api/auth/me").json()["authenticated"] is True


def test_a_user_id_in_the_body_is_ignored(two_accounts):
    """The session decides whose data this is. If a body field could override it,
    every owned resource would be one typo away from public."""
    mine = store.get_user_by_email("mine@example.com")
    theirs = store.get_user_by_email("theirs@example.com")
    saved = other.post("/api/saved-research", headers={"X-Optic-CSRF": two_accounts["theirs"]},
                       json={"title": "T", "content": "theirs",
                             "user_id": mine["id"]})
    assert saved.status_code == 200
    row = main.accounts_db.row("SELECT user_id FROM saved_research WHERE id = ?",
                               (saved.json()["research"]["id"],))
    assert row["user_id"] == theirs["id"]
    assert client.get("/api/saved-research").json()["research"] == []


# ---------------------------------------------------------------- injection


INJECTIONS = [
    "' OR '1'='1",
    "admin'--",
    "'; DROP TABLE users; --",
    "\" OR 1=1 --",
    "x' UNION SELECT id,email,'','',NULL,1,1,'','','' FROM users --",
    "'||(SELECT password_hash FROM user_passwords)||'",
]


@pytest.mark.parametrize("payload", INJECTIONS)
def test_injection_in_the_login_email_does_nothing(payload):
    register(client, "real@example.com")
    client.cookies.clear()
    reply = client.post("/api/auth/login", json={"email": payload, "password": payload})
    assert reply.status_code in (400, 401)
    # The table is still there and still has exactly the one account.
    assert len(main.accounts_db.rows("SELECT 1 FROM users")) == 1
    assert client.get("/api/auth/me").json()["authenticated"] is False


@pytest.mark.parametrize("payload", INJECTIONS)
def test_injection_in_a_watchlist_name_is_stored_as_text(payload, two_accounts):
    reply = client.post("/api/watchlists", headers={"X-Optic-CSRF": two_accounts["mine"]},
                        json={"name": payload})
    assert reply.status_code == 200
    assert reply.json()["watchlist"]["name"] == payload[:60]
    assert len(main.accounts_db.rows("SELECT 1 FROM users")) == 2


def test_injection_in_a_symbol_is_refused_by_the_validator(two_accounts):
    made = client.post("/api/watchlists", headers={"X-Optic-CSRF": two_accounts["mine"]},
                       json={"name": "L"})
    list_id = made.json()["watchlist"]["id"]
    reply = client.post("/api/watchlists/{}/items".format(list_id),
                        headers={"X-Optic-CSRF": two_accounts["mine"]},
                        json={"symbol": "'; DROP TABLE watchlist_items; --"})
    assert reply.status_code == 400
    assert main.accounts_db.rows("SELECT 1 FROM watchlist_items") == []
    # The table survived, which is the point.
    assert client.get("/api/watchlists").status_code == 200


# An f-string prefix, and not the letter f at the end of a word. `"brief"`
# matched the naive version, which is a good reminder that a grep-shaped test
# needs the same scrutiny as the code.
F_STRING = re.compile(r'(?<![A-Za-z0-9_])f(?:"""|\'\'\'|"|\')')


def test_no_sql_in_the_data_layer_is_built_with_an_f_string():
    """A grep, not a behaviour test. It catches the next f-string before it
    ships, which is the only moment this class of bug is cheap. The injection
    tests above prove the current statements are safe; this one is about the
    next edit."""
    for path in ("app/auth/store.py", "app/account.py", "app/db.py",
                 "app/auth/ratelimit.py"):
        source = open(path).read()
        for match in F_STRING.finditer(source):
            line = source[:match.start()].count("\n") + 1
            raise AssertionError("f-string in {}:{} — SQL here must use bound "
                                 "parameters".format(path, line))
        # `.format()` on a SQL string is allowed only for identifiers, and every
        # such call in these files formats a literal written in this source.
        # These two assertions say a caller-supplied name never reaches one.
        assert ".format(payload" not in source
        assert ".format(request" not in source
        assert "% (" not in source.replace("100% (", "")


# --------------------------------------------------------------------- csrf


def test_a_state_change_without_the_csrf_header_is_refused(two_accounts):
    reply = client.post("/api/watchlists", json={"name": "No header"})
    assert reply.status_code == 403
    assert "did not look like it came from this page" in reply.json()["detail"]


def test_a_wrong_csrf_value_is_refused(two_accounts):
    reply = client.post("/api/watchlists", headers={"X-Optic-CSRF": "not-the-value"},
                        json={"name": "Wrong header"})
    assert reply.status_code == 403


def test_the_csrf_cookie_is_readable_but_the_session_cookie_is_not():
    reply = client.post("/api/auth/register", json={
        "first_name": "A", "email": "csrf@example.com",
        "password": GOOD, "confirm_password": GOOD})
    cookies = reply.headers.get_list("set-cookie")
    session = [c for c in cookies if c.startswith(config.COOKIE_NAME)][0]
    csrf = [c for c in cookies if c.startswith(config.CSRF_COOKIE)][0]
    assert "httponly" in session.lower()
    # Not HttpOnly on purpose: the front end has to echo it into a header, and
    # the value is not a credential on its own.
    assert "httponly" not in csrf.lower()


def test_logout_needs_no_csrf_header_because_it_only_removes_access():
    register(client, "out@example.com")
    assert client.post("/api/auth/logout").status_code == 200


# ------------------------------------------------------------- ai allowance


def test_a_guest_gets_a_smaller_assistant_allowance_than_an_account():
    guest = client.get("/api/ai-allowance").json()["allowance"]
    assert guest["scope"] == "guest"
    assert guest["allowed"] == main.GUEST_AI_CALLS_PER_DAY
    assert guest["signed_in_allowance"] > guest["allowed"]

    register(client, "spender@example.com")
    account = client.get("/api/ai-allowance").json()["allowance"]
    assert account["scope"] == "account"
    assert account["plan"] == "free"
    assert account["allowed"] == store.PLANS["free"]["ai_calls_per_day"]


def test_the_guest_allowance_is_spent_and_then_refuses(monkeypatch):
    monkeypatch.setattr(main, "GUEST_AI_CALLS_PER_DAY", 2)
    for _ in range(2):
        main._spend_guard(_FakeRequest())
    with pytest.raises(Exception) as caught:
        main._spend_guard(_FakeRequest())
    assert getattr(caught.value, "status_code", None) == 429
    assert "Create a free account" in caught.value.detail


class _FakeRequest:
    """Enough of a Request for the guard: headers, a client and request.state."""

    def __init__(self, ip="203.0.113.7"):
        self.headers = {"x-forwarded-for": ip}
        self.client = None
        self.cookies = {}

        class _State:
            pass

        self.state = _State()


def test_a_live_session_without_the_csrf_cookie_is_still_refused(two_accounts):
    """The two cookies are set together but can be separated: a reader who clears
    one, a browser that evicts it, an extension. An earlier version returned early
    whenever the CSRF cookie was absent, which meant a request with a live session
    and no CSRF cookie skipped the check entirely.

    **The POST comes first.** Calling /api/auth/me to prove the session is alive
    hands back a fresh CSRF cookie, because that endpoint reissues one when it is
    missing. Doing that before the POST put the cookie back and made both the
    fixed and the broken guard answer 403 for the same reason. This test passed
    its own mutation until the order changed.
    """
    # Deleted from the jar rather than cleared and re-set: httpx stores cookies
    # per domain, and a cookie set with no matching domain is simply not sent,
    # which would make this pass by being unauthenticated instead.
    client.cookies.delete(config.CSRF_COOKIE)
    assert client.cookies.get(config.CSRF_COOKIE) is None
    assert client.cookies.get(config.COOKIE_NAME) is not None

    refused = client.post("/api/watchlists", json={"name": "Forged"})
    assert refused.status_code == 403, refused.text
    assert "did not look like it came from this page" in refused.json()["detail"]

    # The session was live the whole time, so a 401 was never the reason.
    assert client.get("/api/auth/me").json()["authenticated"] is True
    assert client.get("/api/watchlists").json()["watchlists"] == []


def test_me_reissues_a_missing_csrf_cookie_so_the_gap_closes_itself():
    """The other half of the pair above: a reader who lost the cookie is not
    stuck, because the next state read gives them a new one."""
    register(client, "healme@example.com")
    client.cookies.delete(config.CSRF_COOKIE)
    body = client.get("/api/auth/me").json()
    assert body["csrf"]
    assert client.cookies.get(config.CSRF_COOKIE) == body["csrf"]
    assert client.post("/api/watchlists", headers={"X-Optic-CSRF": body["csrf"]},
                       json={"name": "Fine now"}).status_code == 200


def test_no_session_cookie_means_there_is_nothing_to_forge():
    """This is what lets the very first sign-in through, before any cookie
    exists."""
    client.cookies.clear()
    reply = client.post("/api/auth/register", json={
        "first_name": "A", "email": "first-ever@example.com",
        "password": GOOD, "confirm_password": GOOD})
    assert reply.status_code == 200
