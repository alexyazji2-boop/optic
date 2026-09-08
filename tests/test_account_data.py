"""Watchlists, saved research, preferences and the plan that limits them.

Also, at the end, two structural checks: that the schema has the indexes and
cascades it claims, and that no route added here collides with one main.py
already owns. The second one exists because it already happened: `/api/research`
was taken by the streaming deep-research endpoint, and the collision left GET
working while POST silently ran a web search.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.main as main
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


def post(path, csrf, **body):
    return client.post(path, headers={"X-Optic-CSRF": csrf}, json=body)


# ------------------------------------------------------------------ watchlists


def test_a_new_account_has_no_lists_until_it_needs_one(signed_in):
    assert client.get("/api/watchlists").json()["watchlists"] == []


def test_create_a_list_with_symbols_and_read_it_back(signed_in):
    reply = post("/api/watchlists", signed_in["csrf"], name="AI Stocks",
                 symbols=["NVDA", "amd", "  smci "])
    assert reply.status_code == 200
    made = reply.json()["watchlist"]
    assert made["name"] == "AI Stocks"
    # Upper-cased and trimmed, in the order they were given.
    assert made["symbols"] == ["NVDA", "AMD", "SMCI"]


def test_symbol_order_is_stable_across_reads(signed_in):
    post("/api/watchlists", signed_in["csrf"], name="L", symbols=["SPY", "QQQ", "IWM"])
    first = client.get("/api/watchlists").json()["watchlists"][0]["symbols"]
    second = client.get("/api/watchlists").json()["watchlists"][0]["symbols"]
    assert first == second == ["SPY", "QQQ", "IWM"]


@pytest.mark.parametrize("symbol", ["NVDA", "^GSPC", "EURUSD=X", "BTC-USD", "BRK.B"])
def test_the_symbol_validator_accepts_every_instrument_the_terminal_loads(symbol, signed_in):
    made = post("/api/watchlists", signed_in["csrf"], name="Mixed")
    list_id = made.json()["watchlist"]["id"]
    reply = post("/api/watchlists/{}/items".format(list_id), signed_in["csrf"],
                 symbol=symbol)
    assert reply.status_code == 200, symbol
    assert symbol in reply.json()["watchlist"]["symbols"]


def test_the_same_symbol_twice_is_one_row(signed_in):
    made = post("/api/watchlists", signed_in["csrf"], name="L", symbols=["NVDA"])
    list_id = made.json()["watchlist"]["id"]
    reply = post("/api/watchlists/{}/items".format(list_id), signed_in["csrf"],
                 symbol="nvda")
    assert reply.json()["watchlist"]["symbols"] == ["NVDA"]


def test_remove_a_symbol_and_delete_a_list(signed_in):
    csrf = signed_in["csrf"]
    made = post("/api/watchlists", csrf, name="L", symbols=["NVDA", "AMD"])
    list_id = made.json()["watchlist"]["id"]
    reply = client.delete("/api/watchlists/{}/items/NVDA".format(list_id),
                          headers={"X-Optic-CSRF": csrf})
    assert reply.json()["watchlist"]["symbols"] == ["AMD"]
    gone = client.delete("/api/watchlists/{}".format(list_id),
                         headers={"X-Optic-CSRF": csrf})
    assert gone.json()["watchlists"] == []
    # The items went with the list, through ON DELETE CASCADE.
    assert main.accounts_db.rows("SELECT 1 FROM watchlist_items") == []


def test_duplicate_list_names_are_refused_case_insensitively(signed_in):
    csrf = signed_in["csrf"]
    post("/api/watchlists", csrf, name="AI Stocks")
    assert post("/api/watchlists", csrf, name="ai stocks").status_code == 409


def test_renaming_onto_another_list_name_is_refused(signed_in):
    csrf = signed_in["csrf"]
    post("/api/watchlists", csrf, name="One")
    second = post("/api/watchlists", csrf, name="Two").json()["watchlist"]["id"]
    reply = client.patch("/api/watchlists/{}".format(second),
                         headers={"X-Optic-CSRF": csrf}, json={"name": "one"})
    assert reply.status_code == 409
    # But renaming to its own name is fine, not a false conflict.
    same = client.patch("/api/watchlists/{}".format(second),
                        headers={"X-Optic-CSRF": csrf}, json={"name": "Two"})
    assert same.status_code == 200


def test_the_free_plan_limits_how_many_lists(signed_in):
    csrf = signed_in["csrf"]
    limit = store.PLANS["free"]["watchlists"]
    for i in range(limit):
        assert post("/api/watchlists", csrf, name="List {}".format(i)).status_code == 200
    refused = post("/api/watchlists", csrf, name="One too many")
    assert refused.status_code == 403
    assert str(limit) in refused.json()["detail"]

    # A plan change lifts it, with no schema change and no code change.
    store.set_plan(signed_in["user"]["id"], "pro")
    assert post("/api/watchlists", csrf, name="Now allowed").status_code == 200


def test_adopting_a_browser_watchlist_merges_rather_than_replaces(signed_in):
    csrf = signed_in["csrf"]
    first = post("/api/watchlists/adopt", csrf, symbols=["SPY", "QQQ", "NVDA", "AMD"])
    assert first.status_code == 200
    assert first.json()["added"] == 4
    assert first.json()["watchlist"]["name"] == "Main Watchlist"

    # Running it twice adds nothing and deletes nothing. Someone who signs in on
    # two devices should not lose a list to the second one.
    second = post("/api/watchlists/adopt", csrf, symbols=["SPY", "TSLA"])
    assert second.json()["added"] == 1
    assert set(second.json()["watchlist"]["symbols"]) == {"SPY", "QQQ", "NVDA", "AMD", "TSLA"}


def test_adopting_skips_junk_without_losing_the_rest(signed_in):
    reply = post("/api/watchlists/adopt", signed_in["csrf"],
                 symbols=["NVDA", "'; DROP TABLE users; --", "", "AMD"])
    assert reply.status_code == 200
    assert reply.json()["watchlist"]["symbols"] == ["NVDA", "AMD"]
    assert len(main.accounts_db.rows("SELECT 1 FROM users")) == 1


def test_adopting_nothing_is_refused_rather_than_creating_an_empty_list(signed_in):
    assert post("/api/watchlists/adopt", signed_in["csrf"], symbols=[]).status_code == 400
    assert client.get("/api/watchlists").json()["watchlists"] == []


# -------------------------------------------------------------- saved research


def test_save_read_and_delete_research(signed_in):
    csrf = signed_in["csrf"]
    saved = post("/api/saved-research", csrf, title="NVDA AI Infrastructure Outlook",
                 symbol="NVDA", content="The long version." * 40,
                 research_type="deep_research")
    assert saved.status_code == 200
    research_id = saved.json()["research"]["id"]

    listed = client.get("/api/saved-research").json()["research"]
    assert len(listed) == 1
    assert listed[0]["title"] == "NVDA AI Infrastructure Outlook"
    assert listed[0]["research_type"] == "deep_research"
    # The list carries a preview, not forty full reports.
    assert "content" not in listed[0]
    assert len(listed[0]["preview"]) == 280

    full = client.get("/api/saved-research/{}".format(research_id)).json()["research"]
    assert full["content"].startswith("The long version.")

    assert client.delete("/api/saved-research/{}".format(research_id),
                         headers={"X-Optic-CSRF": csrf}).status_code == 200
    assert client.get("/api/saved-research").json()["research"] == []


def test_research_can_be_filtered_by_symbol(signed_in):
    csrf = signed_in["csrf"]
    post("/api/saved-research", csrf, title="A", symbol="NVDA", content="a")
    post("/api/saved-research", csrf, title="B", symbol="AAPL", content="b")
    post("/api/saved-research", csrf, title="C", content="c")
    assert len(client.get("/api/saved-research").json()["research"]) == 3
    only = client.get("/api/saved-research", params={"symbol": "nvda"}).json()["research"]
    assert [r["title"] for r in only] == ["A"]


def test_empty_research_is_refused_and_a_title_is_derived(signed_in):
    csrf = signed_in["csrf"]
    assert post("/api/saved-research", csrf, content="   ").status_code == 400
    derived = post("/api/saved-research", csrf, symbol="NVDA", content="something")
    assert derived.json()["research"]["title"] == "NVDA research"
    plain = post("/api/saved-research", csrf, content="something else")
    assert plain.json()["research"]["title"] == "Research note"


def test_an_unknown_research_type_falls_back_rather_than_failing(signed_in):
    saved = post("/api/saved-research", signed_in["csrf"], content="x",
                 research_type="whatever-i-invented")
    assert saved.json()["research"]["research_type"] == "note"


def test_the_plan_limits_how_much_research_is_kept(signed_in, monkeypatch):
    monkeypatch.setitem(store.PLANS["free"], "saved_research", 2)
    csrf = signed_in["csrf"]
    for i in range(2):
        assert post("/api/saved-research", csrf, content="note {}".format(i)
                    ).status_code == 200
    refused = post("/api/saved-research", csrf, content="one too many")
    assert refused.status_code == 403
    assert "Delete one" in refused.json()["detail"]


# ---------------------------------------------------------------- preferences


def test_preferences_round_trip_and_reject_an_unknown_landing_view(signed_in):
    csrf = signed_in["csrf"]
    body = client.get("/api/auth/preferences").json()
    assert body["preferences"]["default_landing"] == "home"
    assert "watchlist" in body["landing_views"]

    updated = client.patch("/api/auth/preferences", headers={"X-Optic-CSRF": csrf},
                           json={"time_zone": "America/New_York",
                                 "default_landing": "watchlist"})
    assert updated.json()["preferences"]["time_zone"] == "America/New_York"
    assert updated.json()["preferences"]["default_landing"] == "watchlist"

    # An unknown view would land the reader on a blank page every visit.
    kept = client.patch("/api/auth/preferences", headers={"X-Optic-CSRF": csrf},
                        json={"default_landing": "does-not-exist"})
    assert kept.json()["preferences"]["default_landing"] == "watchlist"


def test_subscription_reports_free_and_says_billing_is_not_built(signed_in):
    body = client.get("/api/auth/subscription").json()
    assert body["subscription"]["plan"] == "free"
    assert body["subscription"]["limits"]["watchlists"] == store.PLANS["free"]["watchlists"]
    assert body["billing"]["available"] is False
    assert "not on sale" in body["billing"]["reason"]


# ----------------------------------------------------------------- structural


def test_the_schema_has_the_indexes_it_depends_on(accounts):
    names = {r["name"] for r in accounts.rows(
        "SELECT name FROM sqlite_master WHERE type = 'index'")}
    for expected in ("idx_users_email", "idx_sessions_user", "idx_sessions_expiry",
                     "idx_identity_user", "idx_identity_provider",
                     "idx_watchlists_user", "idx_items_list", "idx_research_user",
                     "idx_research_symbol", "idx_passkey_cred", "idx_attempts"):
        assert expected in names, expected


def test_foreign_keys_are_enforced_on_every_connection(accounts):
    """SQLite ships this off, per connection. Every ON DELETE CASCADE in the
    schema is decoration without it, and an orphaned session row still
    authenticates."""
    with accounts.cursor() as conn:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    with pytest.raises(Exception):
        accounts.execute(
            "INSERT INTO sessions (id,user_id,session_token_hash,expires_at,"
            "created_at,last_used_at) VALUES ('x','ghost','h',?,?,?)",
            (accounts.in_seconds(60), accounts.utcnow(), accounts.utcnow()))


def test_migrations_are_idempotent_and_recorded(accounts):
    assert accounts.migrate() == []                 # already applied by the fixture
    assert accounts.applied() == [m[0] for m in accounts.MIGRATIONS]
    rows = accounts.rows("SELECT version, name FROM schema_migrations ORDER BY version")
    assert rows[0]["name"] == "accounts"


def test_no_new_route_collides_with_one_main_already_owned():
    """The bug this test is named after: `/api/research` existed as the
    streaming deep-research endpoint, and adding a saved-research route on the
    same path left GET working and POST doing something else entirely.

    main.py's own routes are read out of its source rather than off the running
    app. On the app object the routers' paths and main's paths are the same
    strings, so a collision is invisible there: the two entries are identical
    and the set operation cannot tell which came from where.
    """
    import re

    from app import account as account_mod
    from app.auth import routes as auth_routes

    decorator = re.compile(r'@app\.(get|post|put|patch|delete)\(\s*"([^"]+)"')
    owned = {(method.upper(), path)
             for method, path in decorator.findall(open("app/main.py").read())}
    assert ("POST", "/api/research") in owned, "sanity: the deep-research route"

    added = set()
    for route in list(auth_routes.router.routes) + list(account_mod.router.routes):
        for method in getattr(route, "methods", set()) or set():
            added.add((method, route.path))
    assert added, "sanity: the routers contributed routes"

    clash = added & owned
    assert not clash, "route collision with app/main.py: {}".format(sorted(clash))
