"""The owner's three signals, server side (Pass 1, 2026-11-09; app/usage.py, migration 21).

What is recorded, what is never in a row, what the usage endpoint refuses (an unknown event, an oversized body, a
burst from one reader and a burst from one address), who may read the counts (no user, the wrong user, the wrong
role and the owner), and that rows are deleted at 400 days and with the account. The Milo question is recorded by
the chat route itself; the route-level tests of it are in tests/test_pass1_milo_route.py."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app import db, usage
from app.auth import admin, config, store

client = TestClient(main.app)
GOOD = "tungsten-carbide-9"
OWNER = "owner@example.com"
V1 = "v-" + "a" * 32
V2 = "v-" + "b" * 32


@pytest.fixture(autouse=True)
def fresh(accounts, monkeypatch):
    client.cookies.clear()
    usage.reset_limits()
    monkeypatch.delenv(admin.ENV_NAME, raising=False)
    monkeypatch.delenv("OPTIC_USAGE_CAPTURE", raising=False)
    yield accounts
    client.cookies.clear()
    usage.reset_limits()


def register(email):
    client.post("/api/auth/register", json={"first_name": "A", "last_name": "B", "email": email,
                                            "password": GOOD, "confirm_password": GOOD})
    return client.cookies.get(config.CSRF_COOKIE)


def rows():
    return db.rows("SELECT * FROM usage_event ORDER BY id")


def send(body, csrf=None, raw=None, ip=None):
    headers = {"Content-Type": "application/json"}
    if csrf:
        headers["X-Optic-CSRF"] = csrf
    if ip:
        headers["X-Forwarded-For"] = ip
    return client.post("/api/usage", content=raw if raw is not None else json.dumps(body), headers=headers)


# ------------------------------------------------------------------ recording

def test_a_visitor_opening_a_stock_from_home_is_one_row_with_nothing_personal():
    r = send({"event": "home_stock_open", "visitor": V1, "symbol": "aapl", "screen": "home", "level": "beginner",
              "question": "Why is Apple moving?", "email": "x@y.com"})
    assert r.status_code == 200 and r.json()["recorded"] is True
    (row,) = rows()
    assert (row["event"], row["actor_kind"], row["actor_ref"], row["user_id"], row["symbol"], row["source_screen"], row["level"]) == \
        ("home_stock_open", "visitor", V1, None, "AAPL", "home", "beginner")
    # the row has no column that could hold a question, an address or an email, whatever the body carried
    assert set(row) == {"id", "occurred_at", "actor_kind", "actor_ref", "user_id", "event", "symbol", "source_screen", "level"}
    assert "x@y.com" not in json.dumps(row) and "Apple moving" not in json.dumps(row) and "testclient" not in json.dumps(row)


def test_a_signed_in_reader_is_counted_by_account_not_by_the_visitor_id():
    csrf = register("reader@example.com")
    r = send({"event": "home_stock_open", "visitor": V1, "symbol": "MSFT"}, csrf=csrf)
    assert r.status_code == 200
    (row,) = rows()
    uid = store.get_user_by_email("reader@example.com")["id"]
    assert row["actor_kind"] == "signed_in" and row["actor_ref"] == uid and row["user_id"] == uid


def test_a_signed_in_write_without_the_csrf_header_is_refused():
    register("reader@example.com")
    assert send({"event": "visit", "visitor": V1}).status_code == 403
    assert rows() == []


def test_a_visit_is_kept_once_per_reader_per_day():
    for _ in range(3):
        assert send({"event": "visit", "visitor": V1}).status_code == 200
    send({"event": "visit", "visitor": V2})
    assert [r["actor_ref"] for r in rows()] == [V1, V2]
    # the next day counts again
    usage.record("visit", ("visitor", V1, None), now=datetime.now(timezone.utc) + timedelta(days=1))
    assert len(rows()) == 3


# ------------------------------------------------------------------ refusals

@pytest.mark.parametrize("event", ["milo_question", "page_view", "", None, "HOME_STOCK_OPEN"])
def test_unknown_events_and_the_server_only_event_are_refused(event):
    r = send({"event": event, "visitor": V1})
    assert r.status_code == 400
    assert rows() == []


def test_an_oversized_body_is_refused_before_it_is_read_as_an_event():
    r = send(None, raw=json.dumps({"event": "visit", "visitor": V1, "pad": "x" * 2000}))
    assert r.status_code == 413
    assert rows() == []


@pytest.mark.parametrize("raw", ["not json", "[1,2]", '"visit"'])
def test_a_body_that_is_not_an_event_object_is_refused(raw):
    assert send(None, raw=raw).status_code == 400


@pytest.mark.parametrize("visitor", [None, "", "v-123", "v-" + "g" * 32, "a" * 34, "<script>"])
def test_an_event_naming_no_reader_is_refused(visitor):
    assert send({"event": "visit", "visitor": visitor}).status_code == 400
    assert rows() == []


def test_a_burst_from_one_reader_is_slowed(monkeypatch):
    monkeypatch.setattr(usage, "ACTORS", usage._Window((5, 60.0)))
    codes = [send({"event": "home_stock_open", "visitor": V1, "symbol": "SPY"}).status_code for _ in range(7)]
    assert codes[:5] == [200] * 5 and codes[5:] == [429, 429]
    # another reader is not held back by the first
    assert send({"event": "home_stock_open", "visitor": V2, "symbol": "SPY"}).status_code == 200


def test_a_burst_from_one_address_is_slowed_even_when_the_visitor_id_rotates(monkeypatch):
    """Clearing browser storage makes a new visitor id; the per-address limit is the backstop. The address is held in
    memory for the limit only and never written to a row."""
    monkeypatch.setattr(usage, "ADDRESSES", usage._Window((4, 60.0)))
    codes = [send({"event": "home_stock_open", "visitor": "v-{:032x}".format(i), "symbol": "SPY"}, ip="203.0.113.7").status_code for i in range(6)]
    assert codes[:4] == [200] * 4 and codes[4:] == [429, 429]
    assert send({"event": "home_stock_open", "visitor": V2, "symbol": "SPY"}, ip="198.51.100.9").status_code == 200
    assert "203.0.113.7" not in json.dumps(rows())


def test_recording_off_records_nothing_and_health_says_so(monkeypatch):
    monkeypatch.setenv("OPTIC_USAGE_CAPTURE", "off")
    assert send({"event": "visit", "visitor": V1}).json()["recorded"] is False
    assert rows() == []
    assert client.get("/api/health").json()["usage_capture"] is False


# ------------------------------------------------------------------ the owner's read, three legs and the owner

def test_no_user_is_refused_the_counts(monkeypatch):
    monkeypatch.setenv(admin.ENV_NAME, OWNER)
    assert client.get("/api/admin/usage-signals").status_code == 401


def test_the_wrong_user_is_refused_the_counts(monkeypatch):
    monkeypatch.setenv(admin.ENV_NAME, OWNER)
    csrf = register("stranger@example.com")
    store.mark_verified(store.get_user_by_email("stranger@example.com")["id"])
    assert client.get("/api/admin/usage-signals", headers={"X-Optic-CSRF": csrf}).status_code == 403


def test_the_wrong_role_an_unverified_owner_address_is_refused_the_counts(monkeypatch):
    """Anyone may type the owner's address into the sign-up form; listed but unconfirmed is not the owner."""
    monkeypatch.setenv(admin.ENV_NAME, OWNER)
    csrf = register(OWNER)
    assert client.get("/api/admin/usage-signals", headers={"X-Optic-CSRF": csrf}).status_code == 403


def test_with_no_owner_configured_nobody_reads_the_counts():
    csrf = register("reader@example.com")
    assert client.get("/api/admin/usage-signals", headers={"X-Optic-CSRF": csrf}).status_code == 403


def test_the_owner_reads_raw_counts_of_the_three_signals(monkeypatch):
    now = datetime.now(timezone.utc)
    a, b = ("visitor", V1, None), ("visitor", V2, None)
    usage.record("visit", a, now=now - timedelta(days=10))
    usage.record("visit", a, now=now - timedelta(days=5))       # came back within a week
    usage.record("visit", b, now=now - timedelta(days=9))       # did not
    usage.record("visit", b, now=now)
    usage.record("home_stock_open", a, symbol="AAPL", now=now)
    usage.record("home_stock_open", a, symbol="MSFT", now=now)
    usage.record("milo_question", a, source_screen="overview", now=now - timedelta(days=2))
    monkeypatch.setenv(admin.ENV_NAME, OWNER)
    csrf = register(OWNER)
    store.mark_verified(store.get_user_by_email(OWNER)["id"])
    r = client.get("/api/admin/usage-signals", headers={"X-Optic-CSRF": csrf})
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    d = r.json()
    assert d["windows"]["today"]["home_stock_open"] == {"events": 2, "readers": 1}
    assert d["windows"]["today"]["milo_question"]["events"] == 0
    assert d["windows"]["week"]["milo_question"] == {"events": 1, "readers": 1}
    assert d["windows"]["all"]["visit"]["days"] == 4 and d["windows"]["all"]["visit"]["readers"] == 2
    assert d["returned_within_week"] == {"readers": 1, "had_a_full_week": 2}
    # counts only: no reader id leaves the server
    assert V1 not in r.text and V2 not in r.text


def test_the_owner_page_shows_the_three_signals():
    src = (main.STATIC_DIR / "v2" / "js" / "pages" / "reports.js").read_text()
    for words in ("Opened a stock from Home", "Asked Milo a question", "Came back within a week", "/api/admin/usage-signals", "${signals()}"):
        assert words in src


# ------------------------------------------------------------------ retention

def test_rows_older_than_400_days_are_deleted_by_the_sweep():
    now = datetime.now(timezone.utc)
    usage.record("visit", ("visitor", V1, None), now=now - timedelta(days=401))
    usage.record("visit", ("visitor", V2, None), now=now - timedelta(days=399))
    counts = db.sweep()
    assert counts["usage_event"] == 1
    assert [r["actor_ref"] for r in rows()] == [V2]


def test_a_readers_rows_go_with_the_account_on_the_delete_account_path():
    csrf = register("leaving@example.com")
    send({"event": "home_stock_open", "visitor": V1, "symbol": "AAPL"}, csrf=csrf)
    send({"event": "visit", "visitor": V1}, csrf=csrf)
    usage.record("visit", ("visitor", V2, None))                 # someone else's, kept
    assert len(rows()) == 3
    r = client.post("/api/auth/delete-account", json={"confirm_email": "leaving@example.com", "password": GOOD},
                    headers={"X-Optic-CSRF": csrf})
    assert r.status_code == 200, r.text
    assert [r2["actor_ref"] for r2 in rows()] == [V2]


def test_the_migration_is_recorded():
    assert 21 in db.applied()
    assert db.MIGRATIONS[-1][:2] == (21, "usage_signals")
