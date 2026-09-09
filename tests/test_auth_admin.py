"""Who owns the deployment, and the two ways that could go wrong.

The gate is one `and`, and each half of it is a separate failure. Without the
membership test anyone with a verified address would own the deployment; without
the *verification* test anyone who can type would, because the signup form
accepts any address. The second is the one worth testing hardest: it is the
difference between a gate and a decoration, and it fails open silently.

Everything here also asserts the unset case, because that is what 1068 other
tests run under: `ADMIN_EMAILS` absent must leave the write token as the only
way in.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.auth import admin, config, store

client = TestClient(main.app)

GOOD = "tungsten-carbide-9"
OWNER = "owner@example.com"
STRANGER = "stranger@example.com"

# One of the four. Chosen over /api/tracker/scan because a scan does real work.
WRITE_PATH = "/api/alerts/clear"


@pytest.fixture(autouse=True)
def fresh(accounts, monkeypatch):
    client.cookies.clear()
    monkeypatch.delenv(admin.ENV_NAME, raising=False)
    # The token branch is what the admin branch falls through to, so it has to
    # be a known value rather than whatever the developer's shell happens to
    # carry. Set on `main` and not the environment: main reads it at import.
    monkeypatch.setattr(main, "WRITE_TOKEN", "test-write-token")
    return accounts


def register(email: str = OWNER) -> str:
    """Register and return the CSRF value. The account is left UNVERIFIED,
    which is the state a real signup lands in."""
    client.post("/api/auth/register", json={
        "first_name": "A", "last_name": "B", "email": email,
        "password": GOOD, "confirm_password": GOOD})
    return client.cookies.get(config.CSRF_COOKIE)


def verify(email: str) -> None:
    """Confirm the address the way consuming a mailed link does."""
    user = store.get_user_by_email(email)
    store.mark_verified(user["id"])


def post(csrf=None, token=None):
    headers = {}
    if csrf:
        headers["X-Optic-CSRF"] = csrf
    if token:
        headers["X-Optic-Token"] = token
    return client.post(WRITE_PATH, json={}, headers=headers)


# --------------------------------------------------------------- the predicate


def test_unset_env_names_nobody(monkeypatch):
    monkeypatch.delenv(admin.ENV_NAME, raising=False)
    assert admin.configured() is False
    assert admin.emails() == frozenset()
    assert admin.is_admin({"email": OWNER, "email_verified": 1}) is False


def test_a_verified_configured_address_is_the_owner(monkeypatch):
    monkeypatch.setenv(admin.ENV_NAME, OWNER)
    assert admin.is_admin({"email": OWNER, "email_verified": 1}) is True


def test_an_unverified_configured_address_is_not(monkeypatch):
    """The escalation-by-registration case. Anyone may type any address."""
    monkeypatch.setenv(admin.ENV_NAME, OWNER)
    assert admin.is_admin({"email": OWNER, "email_verified": 0}) is False


def test_a_verified_unlisted_address_is_not(monkeypatch):
    monkeypatch.setenv(admin.ENV_NAME, OWNER)
    assert admin.is_admin({"email": STRANGER, "email_verified": 1}) is False


def test_case_and_whitespace_do_not_decide_it(monkeypatch):
    """users.email is stored COLLATE NOCASE, so the comparison must agree."""
    monkeypatch.setenv(admin.ENV_NAME, "  Owner@Example.COM ")
    assert admin.is_admin({"email": "owner@example.com", "email_verified": 1}) is True
    assert admin.is_admin({"email": "OWNER@EXAMPLE.COM", "email_verified": 1}) is True


def test_several_addresses_and_empty_entries(monkeypatch):
    monkeypatch.setenv(admin.ENV_NAME, "a@x.com,,  ,b@x.com,")
    assert admin.emails() == {"a@x.com", "b@x.com"}
    assert admin.is_admin({"email": "b@x.com", "email_verified": 1}) is True


def test_no_user_and_no_email_are_not_the_owner(monkeypatch):
    monkeypatch.setenv(admin.ENV_NAME, OWNER)
    assert admin.is_admin(None) is False
    assert admin.is_admin({}) is False
    assert admin.is_admin({"email": "", "email_verified": 1}) is False
    # An empty ADMIN_EMAILS must not make an empty address match.
    monkeypatch.setenv(admin.ENV_NAME, "")
    assert admin.is_admin({"email": "", "email_verified": 1}) is False


def test_status_does_not_leak_the_addresses(monkeypatch):
    """This shape is handed to a signed-in reader; the owner's address is not."""
    monkeypatch.setenv(admin.ENV_NAME, OWNER)
    text = repr(admin.status({"email": OWNER, "email_verified": 1}))
    assert OWNER not in text
    assert admin.status()["count"] == 1


def test_the_env_is_read_per_call_not_at_import(monkeypatch):
    """A module constant would have frozen this at whatever was set first."""
    monkeypatch.setenv(admin.ENV_NAME, "first@x.com")
    assert admin.emails() == {"first@x.com"}
    monkeypatch.setenv(admin.ENV_NAME, "second@x.com")
    assert admin.emails() == {"second@x.com"}


# ------------------------------------------------------------ the write guard


def test_owner_writes_without_the_token(monkeypatch):
    csrf = register()
    verify(OWNER)
    monkeypatch.setenv(admin.ENV_NAME, OWNER)
    assert post(csrf=csrf).status_code == 200


def test_unverified_owner_still_needs_the_token(monkeypatch):
    """The same account, one column different."""
    csrf = register()
    monkeypatch.setenv(admin.ENV_NAME, OWNER)
    assert post(csrf=csrf).status_code == 401
    assert post(csrf=csrf, token="test-write-token").status_code == 200


def test_a_stranger_signed_in_still_needs_the_token(monkeypatch):
    csrf = register(STRANGER)
    verify(STRANGER)
    monkeypatch.setenv(admin.ENV_NAME, OWNER)
    assert post(csrf=csrf).status_code == 401


def test_the_owner_branch_requires_csrf(monkeypatch):
    """A cookie authorises this branch, so the second lock has to be shut.

    Without it another origin could aim the owner's own browser at a write.
    SameSite=Lax already refuses to send the cookie on a cross-site POST; this
    asserts the check that does not depend on the browser getting that right."""
    register()
    verify(OWNER)
    monkeypatch.setenv(admin.ENV_NAME, OWNER)
    assert post().status_code == 403


def test_the_token_still_works_with_no_admin_configured(monkeypatch):
    """The regression that would break every existing deployment."""
    monkeypatch.delenv(admin.ENV_NAME, raising=False)
    assert post(token="test-write-token").status_code == 200
    assert post(token="wrong").status_code == 401


def test_a_guest_is_refused_whatever_is_configured(monkeypatch):
    monkeypatch.setenv(admin.ENV_NAME, OWNER)
    assert post().status_code == 401


def test_admin_check_failing_falls_back_to_the_token(monkeypatch):
    """An unmounted volume must not 500 a correctly-authenticated write.

    These four endpoints ran on a token alone long before the accounts database
    existed, and resolving a session now touches it."""
    import sqlite3

    monkeypatch.setenv(admin.ENV_NAME, OWNER)

    def explode(_request):
        raise sqlite3.OperationalError("unable to open database file")

    monkeypatch.setattr(main.auth_deps, "is_admin", explode)
    assert post(token="test-write-token").status_code == 200
    assert post(token="wrong").status_code == 401


# ------------------------------------------------------------------- exposure


def test_me_reports_admin_only_for_the_owner(monkeypatch):
    register()
    verify(OWNER)
    monkeypatch.setenv(admin.ENV_NAME, OWNER)
    assert client.get("/api/auth/me").json()["admin"] is True
    monkeypatch.delenv(admin.ENV_NAME)
    assert client.get("/api/auth/me").json()["admin"] is False


def test_me_reports_no_admin_key_to_a_guest(monkeypatch):
    """`admin` is a fact about the caller, and a guest is not one."""
    monkeypatch.setenv(admin.ENV_NAME, OWNER)
    body = client.get("/api/auth/me").json()
    assert body["authenticated"] is False
    assert "admin" not in body


def test_providers_never_mentions_the_owner(monkeypatch):
    """/api/auth/providers is unauthenticated, so it must not become a way to
    harvest the operator's address from a public site."""
    monkeypatch.setenv(admin.ENV_NAME, OWNER)
    text = client.get("/api/auth/providers").text
    assert OWNER not in text
    assert "admin" not in text.lower()


def test_public_user_has_no_admin_field(monkeypatch):
    """It is an allow-list of columns, and admin is not one."""
    monkeypatch.setenv(admin.ENV_NAME, OWNER)
    register()
    verify(OWNER)
    user = store.get_user_by_email(OWNER)
    assert "admin" not in store.public_user(user)


# ------------------------------------------------------------- ai allowance


def test_owner_is_not_metered_on_the_daily_allowance(monkeypatch):
    register()
    verify(OWNER)
    monkeypatch.setenv(admin.ENV_NAME, OWNER)
    body = client.get("/api/ai-allowance").json()["allowance"]
    assert body["scope"] == "admin"
    assert body["enforced"] is False


def test_a_signed_in_stranger_is_still_metered(monkeypatch):
    register(STRANGER)
    verify(STRANGER)
    monkeypatch.setenv(admin.ENV_NAME, OWNER)
    body = client.get("/api/ai-allowance").json()["allowance"]
    assert body["scope"] == "account"
    assert body["allowed"] == store.PLANS["free"]["ai_calls_per_day"]


def test_the_owner_keeps_the_hourly_cap(monkeypatch):
    """The daily cap protects the operator's balance from visitors. The hourly
    one is also a runaway-loop guard, and a loop does not care whose key it is,
    so skipping the daily one must not skip that.

    Driven through `_spend_guard` rather than read out of the source. The first
    version of this test grepped main.py for a `return` in the admin branch and
    was defeated by the word "return" appearing in that branch's own comment,
    which is the kind of pass that proves nothing."""
    from fastapi import HTTPException

    register()
    verify(OWNER)
    monkeypatch.setenv(admin.ENV_NAME, OWNER)
    monkeypatch.setattr(main, "AI_CALLS_PER_HOUR", 2)
    monkeypatch.setattr(main, "_ai_calls", {})

    request = _request_with_cookies()
    main._spend_guard(request)
    main._spend_guard(request)
    with pytest.raises(HTTPException) as raised:
        main._spend_guard(request)
    assert raised.value.status_code == 429
    assert "in an hour" in raised.value.detail


def _request_with_cookies():
    """A Request carrying this client's session cookie.

    `_spend_guard` takes a Request, not a path, so the hourly cap cannot be
    reached through TestClient without also spending real assistant calls."""
    from starlette.requests import Request

    cookie = "; ".join("{}={}".format(k, v) for k, v in client.cookies.items())
    return Request({
        "type": "http",
        "method": "POST",
        "path": "/api/chat",
        "headers": [(b"cookie", cookie.encode()), (b"x-forwarded-for", b"203.0.113.7")],
        "query_string": b"",
        "client": ("203.0.113.7", 1234),
    })


# ------------------------------------------------------------------- client
#
# No JS runner here, so these read the source as text. See tests/test_ui_refactor.py
# for why: every silent client failure in this codebase has been a wiring failure.


def _auth_js() -> str:
    return open("static/auth.js").read()


def _app_js() -> str:
    return open("static/app.js").read()


def test_client_admin_comes_from_the_server_not_the_email():
    """A client that decided this itself would claim a privilege the API
    refuses, which shows the owner a working button that 401s."""
    src = _auth_js()
    assert "STATE.admin = !!(payload && payload.admin)" in src
    # No local inference: nothing in auth.js may compare an email to a list.
    assert "ADMIN_EMAILS" not in src
    assert "admin: false" in src            # declared in STATE, so it is never undefined


def test_post_json_sends_the_csrf_header():
    """The admin write branch is authorised by cookie, and the server pairs
    that with the double-submit check. Without this header every owner write
    would 403."""
    src = _app_js()
    guard = src[src.index("async function postJSON"):]
    guard = guard[:guard.index("\n}")]
    assert "X-Optic-CSRF" in guard
    assert "window.OpticAuth.csrf()" in guard
    assert "credentials: 'same-origin'" in guard


def test_the_csrf_cookie_name_lives_in_one_file():
    """app.js reads the value through OpticAuth rather than parsing the cookie
    itself: two copies of the name means the un-updated one fails as a missing
    header, silently."""
    assert "csrf: csrfCookie," in _auth_js()
    assert "optic_csrf" not in _app_js()


def test_an_admin_is_not_prompted_for_the_write_token():
    """Pasting a token they may not have set cannot fix a lapsed session."""
    src = _app_js()
    guard = src[src.index("async function postJSON"):]
    guard = guard[:guard.index("\n}")]
    prompt_at = guard.index("window.prompt")
    admin_at = guard.index("state().admin")
    assert admin_at < prompt_at, "the admin branch must come before the prompt"


def test_the_owner_marker_is_rendered_and_styled():
    """A dead class is a marker that never appears; a marker with no rule is an
    unstyled string in the menu."""
    assert 'class="acct-admin">Owner' in _auth_js()
    assert ".acct-admin {" in open("static/styles.css").read()


def test_assets_share_one_cache_bust_version():
    """Not a literal version number.

    The first version of this asserted `?v=398`, which meant the next asset
    change failed a test about accounts, and the obvious repair is to bump the
    number here, at which point the test asserts nothing. What actually matters
    is that the tags agree: app.js and auth.js are edited together, and a reader
    served 399 of one against 398 of the other gets a page where STATE.admin
    does not exist and the account menu never shows the marker."""
    html = open("static/index.html").read()
    versions = set(re.findall(r"\.(?:js|css)\?v=(\d+)", html))
    assert len(versions) == 1, versions
    for asset in ("app.js", "auth.js", "charts.js", "styles.css"):
        assert "%s?v=" % asset in html, asset
