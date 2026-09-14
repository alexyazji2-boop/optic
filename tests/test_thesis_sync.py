"""A thesis outliving the browser it was written in.

The thesis panel kept everything in localStorage, which was the only option
before there were accounts. Its own comment said so: "accounts exist now and
this has not moved yet, which is a gap rather than a decision." The symptom was
quiet and total. Clear the cache, or open the terminal on a phone, and a
reader's own written view on twenty names was gone, and the panel below the box
said "Kept in this browser" to somebody who was signed in.

**Its own table, not a saved_research row.** `RESEARCH_TYPES` already listed
"thesis", so that was the anticipated home, and it is the wrong one for two
behavioural reasons. POST /api/saved-research inserts a new row every call, so
five edits to one thesis would be five rows with nothing marking the current
one. And saved research is quota'd per plan, so a reader who had saved forty
Pulse answers could not write a thesis at all. One per symbol is a UNIQUE index.

**Adopt merges and never clobbers.** These are documents the reader wrote. Where
both sides have a thesis for a symbol the account's copy wins, because that is
the one that survived a cache clear, and a merge that silently overwrites is
indistinguishable from data loss.

These drive the real endpoints through TestClient rather than reading source.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app import db
from app.auth import config, store

client = TestClient(main.app)

GOOD = "tungsten-carbide-9"


@pytest.fixture(autouse=True)
def fresh(accounts):
    client.cookies.clear()
    return accounts


@pytest.fixture
def signed_in():
    client.post("/api/auth/register", json={
        "first_name": "Alex", "last_name": "Yazji", "email": "reader@example.com",
        "password": GOOD, "confirm_password": GOOD})
    return {"csrf": client.cookies.get(config.CSRF_COOKIE),
            "user": store.get_user_by_email("reader@example.com")}


def put(path, csrf, **body):
    return client.put(path, headers={"X-Optic-CSRF": csrf}, json=body)


def post(path, csrf, **body):
    return client.post(path, headers={"X-Optic-CSRF": csrf}, json=body)


def delete(path, csrf):
    return client.delete(path, headers={"X-Optic-CSRF": csrf})


SNAP = {"stance": "bullish", "price": 212.3, "rsi": 61.2, "gamma": "positive"}


# ----------------------------------------------------------- the round trip

def test_a_new_account_has_no_theses(signed_in):
    reply = client.get("/api/theses").json()
    assert reply["theses"] == {}
    assert reply["count"] == 0


def test_write_a_thesis_and_read_it_back(signed_in):
    reply = put("/api/theses/nvda", signed_in["csrf"],
                bull="Datacenter demand is still supply-constrained.",
                bear="Any hyperscaler capex cut hits this first.",
                catalysts="Earnings, GTC", invalidation="Loses the 200-day",
                snapshot=SNAP)
    assert reply.status_code == 200, reply.text
    saved = reply.json()["thesis"]
    assert saved["symbol"] == "NVDA", "the symbol is upper-cased"
    assert saved["bull"].startswith("Datacenter")
    assert saved["snapshot"] == SNAP

    back = client.get("/api/theses").json()
    assert list(back["theses"]) == ["NVDA"]
    assert back["theses"]["NVDA"]["invalidation"] == "Loses the 200-day"


def test_the_snapshot_survives_as_an_object_not_a_string(signed_in):
    """The client's `thesisChanges` indexes into the snapshot. Handing back the
    JSON string it is stored as would make a synced thesis a different shape
    from a local one, and the diff would silently find nothing."""
    put("/api/theses/NVDA", signed_in["csrf"], bull="x", snapshot=SNAP)
    got = client.get("/api/theses").json()["theses"]["NVDA"]["snapshot"]
    assert isinstance(got, dict)
    assert got["rsi"] == 61.2


def test_editing_a_thesis_replaces_it_rather_than_adding_a_row(signed_in):
    """The reason this is not a saved_research row. Five edits must be one
    thesis, not five with nothing saying which is current."""
    for n in range(5):
        put("/api/theses/NVDA", signed_in["csrf"], bull="take %d" % n,
            snapshot=SNAP)
    reply = client.get("/api/theses").json()
    assert reply["count"] == 1
    assert reply["theses"]["NVDA"]["bull"] == "take 4"
    rows = db.rows("SELECT * FROM theses WHERE symbol = 'NVDA'")
    assert len(rows) == 1


def test_an_edit_keeps_the_date_the_view_was_first_taken(signed_in):
    """`created_at` is when the reader first took a view on this name, which is
    the more interesting of the two dates and the one an UPDATE would quietly
    destroy.

    The stored date is backdated rather than read from a first write. Writing
    twice and comparing is what this test did first, and it passed against an
    UPDATE that set `created_at = ?, now`: both writes land inside the same
    second, so `db.utcnow()` returns the identical string and the assertion
    holds while the column is being overwritten. A date test that depends on
    two calls being a second apart is not a date test.
    """
    csrf = signed_in["csrf"]
    put("/api/theses/NVDA", csrf, bull="first", snapshot=SNAP)
    db.execute("UPDATE theses SET created_at = ? WHERE symbol = ?",
               ("2026-01-02T03:04:05Z", "NVDA"))

    put("/api/theses/NVDA", csrf, bull="second", snapshot=SNAP)
    after = client.get("/api/theses").json()["theses"]["NVDA"]
    assert after["created_at"] == "2026-01-02T03:04:05Z"
    assert after["bull"] == "second", "the edit itself still has to land"
    # And `saved_at` is the update, so the panel can say when it last changed.
    assert after["saved_at"] != "2026-01-02T03:04:05Z"


def test_two_symbols_are_two_theses(signed_in):
    put("/api/theses/NVDA", signed_in["csrf"], bull="a", snapshot=SNAP)
    put("/api/theses/AMD", signed_in["csrf"], bull="b", snapshot=SNAP)
    assert client.get("/api/theses").json()["count"] == 2


def test_an_empty_thesis_is_refused(signed_in):
    """Matches the client, which ignores a submit with every box empty. An
    empty thesis is a delete, and a delete has its own verb."""
    reply = put("/api/theses/NVDA", signed_in["csrf"], bull="", bear="   ")
    assert reply.status_code == 400
    assert client.get("/api/theses").json()["count"] == 0


def test_delete_removes_it(signed_in):
    put("/api/theses/NVDA", signed_in["csrf"], bull="a", snapshot=SNAP)
    assert delete("/api/theses/NVDA", signed_in["csrf"]).status_code == 200
    assert client.get("/api/theses").json()["count"] == 0


def test_deleting_something_that_is_not_there_is_a_404(signed_in):
    assert delete("/api/theses/NVDA", signed_in["csrf"]).status_code == 404


def test_a_bad_symbol_is_refused(signed_in):
    assert put("/api/theses/not a symbol!", signed_in["csrf"],
               bull="x").status_code in (400, 404)


# ------------------------------------------------------------- the isolation

def test_one_reader_cannot_see_or_touch_anothers_thesis(signed_in):
    """Every query is scoped by user_id. The thesis is the most personal thing
    in this database: it is the reader's own reasoning about their own money."""
    put("/api/theses/NVDA", signed_in["csrf"], bull="mine", snapshot=SNAP)
    client.cookies.clear()
    client.post("/api/auth/register", json={
        "first_name": "Other", "last_name": "Person",
        "email": "other@example.com", "password": GOOD, "confirm_password": GOOD})
    other = client.cookies.get(config.CSRF_COOKIE)

    assert client.get("/api/theses").json()["theses"] == {}
    assert delete("/api/theses/NVDA", other).status_code == 404
    # And writing their own NVDA thesis must not touch the first reader's.
    put("/api/theses/NVDA", other, bull="theirs", snapshot=SNAP)
    rows = db.rows("SELECT bull FROM theses WHERE symbol = 'NVDA' ORDER BY bull")
    assert [r["bull"] for r in rows] == ["mine", "theirs"]


def test_a_guest_is_not_served_theses():
    """Signed out the panel is local, so the endpoint has nothing to answer
    with. This must be a 401 rather than an empty list: an empty list would
    read to the client as "your account has none", and the sync code would
    treat a signed-out reader as one whose theses had all been deleted."""
    assert client.get("/api/theses").status_code == 401


def test_a_write_without_the_csrf_header_is_refused(signed_in):
    """The session is a cookie, so the browser sends it whether or not the
    reader meant to. The header an attacker cannot set is the proof."""
    assert client.put("/api/theses/NVDA", json={"bull": "x"}).status_code == 403
    assert client.delete("/api/theses/NVDA").status_code == 403
    assert client.post("/api/theses/adopt",
                       json={"theses": {"NVDA": {"bull": "x"}}}).status_code == 403


# ---------------------------------------------------------------- the bounds

def test_a_field_is_capped_rather_than_the_write_refused(signed_in):
    put("/api/theses/NVDA", signed_in["csrf"], bull="x" * 50000, snapshot=SNAP)
    got = client.get("/api/theses").json()["theses"]["NVDA"]["bull"]
    assert 1000 < len(got) < 20000, len(got)


def test_an_oversized_snapshot_keeps_the_prose_and_drops_the_readings(signed_in):
    """Rejecting the write would lose what the reader typed to protect a field
    they never see."""
    put("/api/theses/NVDA", signed_in["csrf"], bull="real words",
        snapshot={"junk": "y" * 40000})
    got = client.get("/api/theses").json()["theses"]["NVDA"]
    assert got["bull"] == "real words"
    assert got["snapshot"] == {}


def test_a_non_object_snapshot_does_not_raise(signed_in):
    for bad in ("a string", 42, ["a", "list"], None):
        reply = put("/api/theses/NVDA", signed_in["csrf"], bull="x", snapshot=bad)
        assert reply.status_code == 200, bad
        assert reply.json()["thesis"]["snapshot"] == {}


def test_unreadable_stored_json_loses_the_diff_not_the_thesis(signed_in):
    """The prose is what the reader wrote. A row whose snapshot cannot be
    parsed must still return the words."""
    put("/api/theses/NVDA", signed_in["csrf"], bull="the words", snapshot=SNAP)
    db.execute("UPDATE theses SET snapshot = ? WHERE symbol = ?",
               ("{not json", "NVDA"))
    got = client.get("/api/theses").json()["theses"]["NVDA"]
    assert got["bull"] == "the words"
    assert got["snapshot"] == {}


def test_the_cap_is_on_new_symbols_not_on_edits(signed_in):
    """A reader at the limit must still be able to rewrite what they have.
    Counting before an UPDATE would lock their own theses as read-only."""
    from app import account as account_mod
    csrf = signed_in["csrf"]
    now = db.utcnow()
    for n in range(account_mod.MAX_THESES):
        db.execute(
            "INSERT INTO theses (id,user_id,symbol,bull,bear,catalysts,"
            "invalidation,snapshot,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (db.new_id(), signed_in["user"]["id"], "SYM%d" % n, "x", "", "", "",
             "{}", now, now))
    assert put("/api/theses/SYM0", csrf, bull="rewritten").status_code == 200
    assert put("/api/theses/BRAND-NEW", csrf, bull="x").status_code == 403


# ---------------------------------------------------------------- the adopt

def test_adopt_takes_over_browser_held_theses(signed_in):
    reply = post("/api/theses/adopt", signed_in["csrf"], theses={
        "NVDA": {"bull": "a", "snapshot": SNAP, "saved_at": "2026-01-02T03:04:05Z"},
        "amd": {"bull": "b", "snapshot": SNAP},
    })
    assert reply.status_code == 200, reply.text
    assert reply.json()["adopted"] == ["AMD", "NVDA"]
    back = client.get("/api/theses").json()["theses"]
    assert set(back) == {"NVDA", "AMD"}
    assert back["NVDA"]["snapshot"] == SNAP


def test_adopt_keeps_the_local_date_the_view_was_taken(signed_in):
    """Adopting must not reset when the reader took the view. They wrote it in
    January; signing in in March does not make it a March thesis."""
    post("/api/theses/adopt", signed_in["csrf"], theses={
        "NVDA": {"bull": "a", "saved_at": "2026-01-02T03:04:05Z"}})
    assert client.get("/api/theses").json()["theses"]["NVDA"]["created_at"].startswith("2026-01-02")


def test_adopt_never_overwrites_what_the_account_already_has(signed_in):
    """The load-bearing one. The account copy survived a cache clear; the local
    copy is the one of unknown age. Silently replacing is data loss."""
    csrf = signed_in["csrf"]
    put("/api/theses/NVDA", csrf, bull="the account version", snapshot=SNAP)
    reply = post("/api/theses/adopt", csrf, theses={
        "NVDA": {"bull": "the browser version"},
        "AMD": {"bull": "new one"}})
    body = reply.json()
    assert body["skipped"] == ["NVDA"]
    assert body["adopted"] == ["AMD"]
    assert client.get("/api/theses").json()["theses"]["NVDA"]["bull"] == \
        "the account version"


def test_adopt_twice_adopts_nothing_the_second_time(signed_in):
    csrf = signed_in["csrf"]
    payload = {"NVDA": {"bull": "a"}, "AMD": {"bull": "b"}}
    assert len(post("/api/theses/adopt", csrf, theses=payload).json()["adopted"]) == 2
    second = post("/api/theses/adopt", csrf, theses=payload).json()
    assert second["adopted"] == []
    assert second["skipped"] == ["AMD", "NVDA"]
    assert client.get("/api/theses").json()["count"] == 2


def test_one_unusable_key_does_not_fail_the_whole_import(signed_in):
    """The reader's other theses are not at fault."""
    reply = post("/api/theses/adopt", signed_in["csrf"], theses={
        "NVDA": {"bull": "good"},
        "not a symbol!": {"bull": "bad key"},
        "AMD": {"bull": "also good"}})
    assert reply.status_code == 200
    assert reply.json()["adopted"] == ["AMD", "NVDA"]


def test_adopt_skips_empty_and_malformed_entries(signed_in):
    reply = post("/api/theses/adopt", signed_in["csrf"], theses={
        "NVDA": {"bull": "", "bear": "  "},
        "AMD": "not even a dict",
        "INTC": {"bull": "real"}})
    assert reply.json()["adopted"] == ["INTC"]


def test_adopt_with_nothing_to_import_is_a_400(signed_in):
    assert post("/api/theses/adopt", signed_in["csrf"], theses={}).status_code == 400
    assert post("/api/theses/adopt", signed_in["csrf"]).status_code == 400


def test_adopt_respects_the_cap_and_says_what_it_could_not_take(signed_in):
    from app import account as account_mod
    csrf = signed_in["csrf"]
    now = db.utcnow()
    for n in range(account_mod.MAX_THESES - 1):
        db.execute(
            "INSERT INTO theses (id,user_id,symbol,bull,bear,catalysts,"
            "invalidation,snapshot,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (db.new_id(), signed_in["user"]["id"], "SYM%d" % n, "x", "", "", "",
             "{}", now, now))
    reply = post("/api/theses/adopt", csrf, theses={
        "AAA": {"bull": "a"}, "BBB": {"bull": "b"}, "CCC": {"bull": "c"}}).json()
    assert len(reply["adopted"]) == 1
    assert len(reply["no_room"]) == 2
    assert client.get("/api/theses").json()["count"] == account_mod.MAX_THESES


# -------------------------------------------------------------- the structure

def test_the_unique_index_is_what_makes_the_upsert_safe(signed_in):
    """Without it a race between two tabs writes two rows for one symbol, and
    the reader's thesis becomes whichever the ORDER BY happens to return."""
    idx = db.rows("SELECT name, sql FROM sqlite_master "
                  "WHERE type='index' AND tbl_name='theses'")
    unique = [i for i in idx if i["sql"] and "UNIQUE" in i["sql"].upper()]
    assert unique, [i["name"] for i in idx]
    assert "user_id" in unique[0]["sql"] and "symbol" in unique[0]["sql"]


def test_deleting_the_account_deletes_the_theses(signed_in):
    """ON DELETE CASCADE, and PRAGMA foreign_keys is per connection. Without it
    the cascade is decoration and a deleted account leaves its owner's private
    reasoning in the database."""
    put("/api/theses/NVDA", signed_in["csrf"], bull="a", snapshot=SNAP)
    db.execute("DELETE FROM users WHERE id = ?", (signed_in["user"]["id"],))
    assert db.rows("SELECT * FROM theses") == []


def test_the_migration_is_idempotent():
    assert db.migrate() == []
    assert 5 in db.applied()


# ------------------------------------------------------------------ the client
#
# Source-text contracts, the project's pattern for client wiring. Sound here
# only because the behaviour was driven in a browser first, with `signedIn` and
# `authApi` stubbed so the failure paths could be forced:
#
#   account copy wins over a differing local one      ACCOUNT, not LOCAL
#   adopt POSTs only what the account lacks           ["AMD"], NVDA skipped
#   save is optimistic then takes the server row      "typed now" -> "server copy"
#   created_at comes back from the server             2026-01-02
#   PUT rejected: words kept, syncFailed set, copy changes
#   ACCOUNT.theses null: falls back to local, says "Loading"

import re as _re

APP_JS = open("static/app.js", encoding="utf-8").read()


def _strip(js):
    js = _re.sub(r"/\*.*?\*/", " ", js, flags=_re.S)
    return _re.sub(r"(?<!:)//[^\n]*", " ", js)


JS = _strip(APP_JS)


def js_body(name):
    start = JS.index("function %s(" % name)
    return JS[start:].split("\nfunction ", 1)[0]


def test_the_account_copy_wins_when_there_is_one():
    """`ACCOUNT.theses === null` means not signed in, or signed in and the
    fetch has not landed. Falling back to this browser is what stops the panel
    saying "no thesis yet" to somebody who wrote one a second ago."""
    fn = js_body("thesisStore")
    assert "if (signedIn() && ACCOUNT.theses) return ACCOUNT.theses;" in fn
    assert "return thesisLocalStore();" in fn


def test_local_storage_is_written_on_every_path():
    """A backing copy, not a second source of truth. No path through this
    feature may lose what somebody typed.

    The assertion is that the write precedes the `signedIn` guard, not merely
    that it precedes the network. Ordering against `authApi` alone was the
    first version, and it passed against a mutation that moved the write below
    `if (!signedIn()) return;`: still before the network, and signed-out saves
    stopped touching disk at all.
    """
    fn = js_body("thesisSave")
    write_at = fn.index("thesisLocalWrite(local)")
    guard_at = fn.index("if (!signedIn()) return;")
    net_at = fn.index("authApi(")
    assert write_at < guard_at, "the local write sits behind the signed-in guard"
    assert write_at < net_at, "the network call comes before the local write"


def test_the_save_does_not_await_the_network():
    """The submit handler re-renders on the next line. An await would leave the
    box showing the old thesis for a whole round trip, on the one interaction
    where the reader has just typed and pressed a button."""
    fn = js_body("thesisSave")
    assert "await" not in fn
    assert ".then(" in fn and ".catch(" in fn


def test_the_server_row_is_taken_back_after_a_save():
    """The server owns `created_at`, which is when the view was first taken and
    is not something this browser can know."""
    fn = js_body("thesisSave")
    assert "out.thesis" in fn
    assert "ACCOUNT.theses[sym] = out.thesis" in fn


def test_a_failed_sync_is_recorded_and_said_out_loud():
    """The one state that must not be silent: the words are on disk but not in
    the account, so saying nothing would claim a sync that did not happen."""
    fn = js_body("thesisSave")
    assert "syncFailed = true" in fn
    where = js_body("thesisWhere")
    assert "saved.syncFailed" in where
    assert "could not reach your account" in where


def test_the_failed_flag_is_per_symbol_not_global():
    """One symbol failing to sync says nothing about the others."""
    fn = js_body("thesisSave")
    assert "ACCOUNT.theses[sym].syncFailed" in fn


def test_every_state_of_where_it_is_kept_is_reachable():
    """This sentence has been wrong twice: it claimed there was no account to
    sync to after accounts shipped, then claimed nothing was synced after sync
    shipped. All four states are derived rather than written once."""
    fn = js_body("thesisWhere")
    assert "if (!signedIn())" in fn
    assert "Sign in and it follows you" in fn
    assert "Loading from your account" in fn
    assert "follows you between browsers" in fn
    # And the stale claims are gone.
    assert "Not synced to your account yet" not in APP_JS
    assert "no account to sync it to" not in APP_JS


def test_adopt_only_sends_what_the_account_lacks():
    """A reader with everything synced makes no request at all."""
    fn = js_body("adoptLocalTheses")
    assert "if (!mine[sym]) fresh[sym] = local[sym];" in fn
    assert "if (!Object.keys(fresh).length) return;" in fn


def test_adopt_does_not_wait_for_the_account_to_be_empty():
    """Unlike the watchlist adopt. A thesis is per symbol, so "the account has
    NVDA and this browser has AMD" is a normal state with an obvious right
    answer, where two whole watchlists merging is not."""
    fn = js_body("adoptLocalTheses")
    assert "length" in fn
    # The watchlist's gate is on the whole list being absent; this one is not.
    assert "ACCOUNT.listId" not in fn


def test_a_failed_adopt_keeps_the_local_copies():
    fn = js_body("adoptLocalTheses")
    catch_at = fn.index("catch (e)")
    assert "thesisLocalWrite" not in fn[catch_at:]
    assert "localStorage.removeItem" not in fn


def test_theses_are_fetched_with_the_rest_of_the_account():
    """One round of requests at sign-in, not a fifth one later."""
    assert "authApi('/api/theses')," in JS
    assert "ACCOUNT.theses = theses.theses || {};" in JS
    assert "await adoptLocalTheses();" in JS


def test_signing_out_clears_the_cached_theses():
    """Otherwise the next reader on a shared browser sees the last one's
    private reasoning."""
    assert "ACCOUNT.theses = null;" in JS


def test_the_symbol_is_encoded_in_the_path():
    """The terminal loads `BRK-B` and `^GSPC`, and a caret in a path segment is
    not something to find out about later."""
    for fn in (js_body("thesisSave"), js_body("thesisDelete")):
        assert "encodeURIComponent(sym)" in fn
