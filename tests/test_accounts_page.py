"""The owner's Accounts page: everyone who has signed up.

Asked for as "build the accounts page instead for my domain account only to
view", after reading the database over a Railway shell proved awkward. Only the
signed-in owner (ADMIN_EMAILS, verified) gets the list: not a guest, not another
reader, not an unverified account using the owner's address, and not the write
token. It carries names, emails, dates and how each person signs in, and never
an id, a hash or a token.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.auth import admin, config

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
HTML = (ROOT / "static/index.html").read_text()
GOOD = "tungsten-carbide-9"
OWNER = "owner@example.com"


def _signup(http, email, first="Ada"):
    reply = http.post("/api/auth/register", json={
        "first_name": first, "last_name": "Reader", "email": email,
        "password": GOOD, "confirm_password": GOOD})
    assert reply.status_code == 200, reply.text


def _verify(accounts, email):
    accounts.execute("UPDATE users SET email_verified = 1 WHERE email = ?", (email,))


def _get(http):
    return http.get("/api/admin/accounts",
                    headers={"X-Optic-CSRF": http.cookies.get(config.CSRF_COOKIE) or ""})


@pytest.fixture
def owner(accounts, monkeypatch):
    monkeypatch.setenv(admin.ENV_NAME, OWNER)
    http = TestClient(main.app)
    _signup(http, OWNER, "Owner")
    _verify(accounts, OWNER)
    reader = TestClient(main.app)
    _signup(reader, "reader@example.com")
    return http, reader


def test_the_owner_sees_everyone_and_nothing_that_works_as_a_key(owner, accounts):
    http, _reader = owner
    reply = _get(http)
    assert reply.status_code == 200, reply.text
    assert reply.headers["cache-control"] == "no-store"
    body = reply.json()
    assert body["total"] == 2 and body["last_7_days"] == 2 and body["verified"] == 1
    emails = [a["email"] for a in body["accounts"]]
    assert sorted(emails) == ["owner@example.com", "reader@example.com"]
    assert body["accounts"][0]["methods"] == ["Password"]
    raw = json.dumps(body)
    for leak in ("argon2", "password_hash", "token", '"id"', "user_id", "provider_user_id"):
        assert leak not in raw, leak
    hashes = [r["password_hash"] for r in accounts.rows("SELECT password_hash FROM user_passwords")]
    assert hashes and not any(h in raw for h in hashes)


def test_a_reader_a_guest_and_a_missing_csrf_header_are_refused(owner):
    http, reader = owner
    assert _get(reader).status_code == 403
    guest = TestClient(main.app)
    assert _get(guest).status_code == 401
    assert http.get("/api/admin/accounts").status_code == 403, "a cookie alone is not enough"


def test_the_owners_address_unverified_is_not_the_owner(accounts, monkeypatch):
    monkeypatch.setenv(admin.ENV_NAME, OWNER)
    squatter = TestClient(main.app)
    _signup(squatter, OWNER)
    assert _get(squatter).status_code == 403


def test_the_write_token_does_not_open_it(owner, monkeypatch):
    monkeypatch.setattr(main, "WRITE_TOKEN", "tok-123")
    guest = TestClient(main.app)
    assert guest.get("/api/admin/accounts", headers={"X-Optic-Token": "tok-123"}).status_code == 401


def test_no_owner_configured_means_nobody(accounts, monkeypatch):
    monkeypatch.delenv(admin.ENV_NAME, raising=False)
    http = TestClient(main.app)
    _signup(http, OWNER)
    _verify(accounts, OWNER)
    assert _get(http).status_code == 403


def test_the_page_sits_in_the_owners_group_and_asks_again_each_visit():
    assert "views: ['reports', 'usage', 'accounts'], owner: true }" in APP
    assert '<section class="view" id="view-accounts"' in HTML
    assert "if (view === 'accounts') return loadAccounts(true);" in APP
    load = APP[APP.index("async function loadAccounts(force) {"):]
    load = load[:load.index("\n}\n")]
    assert load.index("if (!isOwner())") < load.index("fetchAccounts()"), "nothing fetched for anyone else"
    assert "cache: 'no-store'" in APP[APP.index("async function fetchAccounts()"):]
    assert "{ view: 'accounts', label: 'Accounts', owner: true," in APP


def test_dates_carry_the_year():
    """A weekday alone would not say which week a months-old signup was in."""
    stamp = APP[APP.index("function accountStamp(iso, zone) {"):]
    assert "year: 'numeric'" in stamp[:stamp.index("\n}\n")]
    assert "accountStamp(a.created_at, zone)" in APP and "accountStamp(a.last_login_at, zone)" in APP


def test_the_table_scrolls_sideways_with_the_person_pinned():
    """Asked for as "make sure the table is scrollable", over a phone screenshot
    scrolled to Status with the names and emails out of sight. Checked at 375px:
    scrolled fully right, the person column sat at the left edge and a long
    email wrapped at its dots inside it."""
    CSS = (ROOT / "static/styles.css").read_text()
    assert '<div class="table-scroll ac-scroll" tabindex="0" role="region"' in APP, "keys scroll it too"
    assert ".ac-scroll { overflow-x: auto;" in CSS
    sticky = CSS[CSS.index(".accounts-table th:first-child,\n.accounts-table td.ac-who {"):]
    sticky = sticky[:sticky.index("}")]
    assert "position: sticky;" in sticky and "left: 0;" in sticky and "background: var(--surface);" in sticky
    assert "table.data.accounts-table td.ac-who { white-space: normal;" in CSS, (
        "beats table.data td's nowrap, or a long email runs over the next column")
    assert "${esc(a.email || '').replace(/@/g, '<wbr>@')" in APP, "escaped first, then the break points"


def _row(body, email):
    return next(a for a in body["accounts"] if a["email"] == email)


def test_last_active_is_the_last_visit_not_only_the_last_sign_in(owner, accounts):
    """Asked for after "is this consistently updating?" over a Last sign-in
    column that stood still: a remembered session lasts 30 days and slides on
    every visit without a new sign-in. Last active follows the visit."""
    http, _reader = owner
    body = _get(http).json()
    fresh = _row(body, "reader@example.com")
    assert fresh["last_active_at"] == fresh["last_login_at"], "a new account was last active at sign-up"

    later = "2099-01-01T00:00:00+00:00"
    accounts.execute(
        "UPDATE sessions SET last_used_at = ? WHERE user_id = "
        "(SELECT id FROM users WHERE email = ?)", (later, "reader@example.com"))
    seen = _row(_get(http).json(), "reader@example.com")
    assert seen["last_active_at"] == later
    assert seen["last_login_at"] == fresh["last_login_at"], "a visit is not a sign-in"


def test_signed_out_last_active_falls_back_to_the_last_sign_in(owner, accounts):
    """Signing out deletes the session, and its last use with it."""
    http, _reader = owner
    accounts.execute("DELETE FROM sessions WHERE user_id = "
                     "(SELECT id FROM users WHERE email = ?)", ("reader@example.com",))
    row = _row(_get(http).json(), "reader@example.com")
    assert row["last_active_at"] == row["last_login_at"]


def test_a_visit_moves_last_active(owner, accounts):
    """End to end: the app's own load (/api/auth/me) is what slides it."""
    http, reader = owner
    accounts.execute("UPDATE sessions SET last_used_at = '2000-01-01T00:00:00+00:00' WHERE user_id = "
                     "(SELECT id FROM users WHERE email = ?)", ("reader@example.com",))
    accounts.execute("UPDATE users SET last_login_at = '2000-01-01T00:00:00+00:00' WHERE email = ?",
                     ("reader@example.com",))
    assert reader.get("/api/auth/me").status_code == 200
    row = _row(_get(http).json(), "reader@example.com")
    assert row["last_active_at"] > "2000-01-01T00:00:00+00:00"
    assert row["last_login_at"] == "2000-01-01T00:00:00+00:00"


def test_the_table_shows_last_active_beside_last_sign_in():
    assert "<th>Joined</th><th>Last active</th><th>Last sign-in</th>" in APP
    row = APP[APP.index("function accountRowHTML(a, zone) {"):]
    row = row[:row.index("\n}\n")]
    assert "accountStamp(a.last_active_at, zone)" in row
    assert row.index("${esc(active)}") < row.index("${esc(seen)}")
    assert "Last active is the last time" in APP

