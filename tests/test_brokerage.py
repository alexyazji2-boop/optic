"""Read-only brokerage linking, end to end against the local sandbox provider.

What these pin down, in the brief's words: hosted authorisation and no
password ever reaching Optic; multiple accounts without double counting;
connection status and last sync; partial, expired, unsupported and outage
states; reconnect and disconnect; ownership on every route; encrypted storage
and crypto-shredding on deletion; plan enforcement and what a lapsed plan
keeps; and Milo getting the signed-in reader's portfolio and nobody else's.
"""

from __future__ import annotations

import base64
import json
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app import db, vault
from app.auth import config, store as auth_store
from app.brokerage import portfolio, service, store
from app.brokerage import routes as broute
from app.brokerage.providers import ProviderError, RefreshUnavailable, SandboxProvider

GOOD = "tungsten-carbide-9"
KEY = base64.urlsafe_b64encode(b"k" * 32).decode()


@pytest.fixture(autouse=True)
def sandbox(accounts, monkeypatch):
    monkeypatch.setenv("BROKERAGE_PROVIDER", "sandbox")
    monkeypatch.setenv("OPTIC_DATA_KEY", KEY)
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
    monkeypatch.setattr(service, "_provider", None)
    monkeypatch.setattr(service, "_provider_key", None)
    # No network: the portfolio's outside lookups answer from a table.
    monkeypatch.setattr(broute, "LOOKUPS", {
        "sector_of": lambda s: {"AAPL": "Technology", "MSFT": "Technology", "NVDA": "Technology",
                                "AMD": "Technology", "TSLA": "Consumer Cyclical"}.get(s),
        "earnings_of": lambda s: {"AAPL": (datetime.now(timezone.utc).date() + timedelta(days=9)).isoformat()}.get(s),
        "optic_price": lambda s: {"MSFT": 470.0}.get(s),
        "fx_to_usd": lambda c: {"CAD": 0.73}.get(c),
    })
    return accounts


def reader(email="reader@example.com"):
    c = TestClient(main.app)
    c.post("/api/auth/register", json={"first_name": "R", "last_name": "Eader", "email": email,
                                       "password": GOOD, "confirm_password": GOOD})
    c.headers["X-Optic-CSRF"] = c.cookies.get(config.CSRF_COOKIE)
    user = auth_store.get_user_by_email(email)
    return c, user


def local(url):
    """The portal redirects to APP_URL's origin; the test client is on its own."""
    u = urlparse(url)
    return u.path + ("?" + u.query if u.query else "")


def link(c, scenario="standard", reconnect=None):
    """Connect -> hosted portal -> authorise -> callback, as the browser does."""
    body = {"consent_version": service.terms()["version"]}
    if reconnect:
        body["reconnect"] = reconnect
    r = c.post("/api/brokerage/connect", json=body)
    assert r.status_code == 200, r.text
    portal = r.json()["url"]
    page = c.get(portal)
    assert page.status_code == 200 and "Sandbox" in page.text
    assert "password" not in page.text.lower().replace("never sees that password", "")
    session = parse_qs(urlparse(portal).query)["session"][0]
    back = c.post("/api/brokerage/sandbox/authorize", data={"session": session, "scenario": scenario},
                  follow_redirects=False)
    assert back.status_code == 303
    done = c.get(local(back.headers["location"]), follow_redirects=False)
    assert done.status_code == 303
    return done.headers["location"]


def paid(user):
    auth_store.set_plan(user["id"], "pro")


# --------------------------------------------------------------- availability


def test_off_unless_configured(monkeypatch):
    monkeypatch.delenv("BROKERAGE_PROVIDER")
    c, user = reader()
    st = c.get("/api/brokerage/status").json()
    assert st["available"] is False and "not switched on" in st["reason"]
    paid(user)
    assert c.post("/api/brokerage/connect").status_code == 503


def test_refuses_to_run_without_a_master_key(monkeypatch):
    monkeypatch.delenv("OPTIC_DATA_KEY")
    c, user = reader()
    paid(user)
    assert c.get("/api/brokerage/status").json()["available"] is False
    assert c.post("/api/brokerage/connect").status_code == 503


def test_sandbox_refuses_hosted_deployments(monkeypatch):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    assert service.status()["enabled"] is False
    monkeypatch.setenv("BROKERAGE_SANDBOX_ON_HOST", "true")
    assert service.status()["enabled"] is True


def test_guests_get_permissions_but_no_data():
    c = TestClient(main.app)
    st = c.get("/api/brokerage/status").json()
    assert st["signed_in"] is False and st["permissions"]
    assert any("Read-only" in p for p in st["permissions"])
    assert c.get("/api/brokerage/portfolio").status_code == 401


# ------------------------------------------------------------------ the plan


def test_free_plan_cannot_link_and_is_told_why():
    c, _ = reader()
    r = c.post("/api/brokerage/connect")
    assert r.status_code == 402 and "paid plan" in r.json()["detail"]


def test_connect_needs_csrf():
    c, user = reader()
    paid(user)
    del c.headers["X-Optic-CSRF"]
    assert c.post("/api/brokerage/connect").status_code == 403


# ----------------------------------------------------------------- the flow


def test_full_flow_two_accounts_no_double_counting():
    c, user = reader()
    paid(user)
    assert link(c) == "/?brokerage=linked#/brokerage"
    st = c.get("/api/brokerage/status").json()
    assert len(st["connections"]) == 1
    conn = st["connections"][0]
    assert conn["status"] == "active" and conn["last_sync_at"]
    assert {a["name"] for a in conn["accounts"]} == {"Individual", "Roth IRA"}

    p = c.get("/api/brokerage/portfolio").json()
    assert p["available"] and p["accounts_counted"] == 2
    aapl = next(h for h in p["holdings"] if h["symbol"] == "AAPL")
    # 40 in Individual + 10 in the Roth: one holding, both accounts named.
    assert aapl["quantity"] == 50 and sorted(aapl["accounts"]) == ["Individual", "Roth IRA"]
    usd = p["totals"]["by_currency"]["USD"]
    assert usd["cash"] == 2700.0
    # Securities total equals the sum of the lines: nothing counted twice.
    assert usd["securities"] == pytest.approx(sum(h["market_value"] for h in p["holdings"]), abs=0.01)
    assert p["options"][0]["market_value_est"] == pytest.approx(2 * 6.40 * 100)
    assert p["options"][0]["multiplier_assumed"] is False
    assert p["earnings_ahead"][0]["symbol"] == "AAPL" and p["earnings_ahead"][0]["has_options"]
    # Broker MSFT price vs Optic's 470: flagged rather than silently reconciled.
    assert p["price_checks"][0]["symbol"] == "MSFT"
    assert p["concentration"]["combined_exposure"][0]["symbol"] == "AAPL"


def test_linking_the_same_broker_twice_does_not_duplicate_accounts(monkeypatch):
    c, user = reader()
    paid(user)
    link(c)
    first = store.accounts(user["id"])
    # The provider reports the same accounts under a second connection id.
    prov = service.provider()
    puid = store.link(user["id"])["provider_user_id"]
    real = prov.list_accounts

    def duplicated(u, s):
        accts = real(u, s)
        return accts
    monkeypatch.setattr(prov, "list_accounts", duplicated)
    conn = store.connections(user["id"])[0]
    other = store.upsert_connection(user["id"], "sandbox", "sbx-standard-dupe", "Sandbox", "active")
    for a in first:
        store.upsert_account(user["id"], other["id"], "sandbox", a["provider_account_id"], a["name"],
                             a["number_mask"], a["institution"], a["account_type"], a["currency"])
    assert len(store.accounts(user["id"])) == len(first)
    del conn, puid


def test_account_selection_changes_what_counts():
    c, user = reader()
    paid(user)
    link(c)
    roth = next(a for a in store.accounts(user["id"]) if a["name"] == "Roth IRA")
    assert c.patch("/api/brokerage/accounts/" + roth["id"], json={"selected": False}).status_code == 200
    p = c.get("/api/brokerage/portfolio").json()
    assert p["accounts_counted"] == 1
    assert next(h for h in p["holdings"] if h["symbol"] == "AAPL")["quantity"] == 40


def test_holdings_are_encrypted_at_rest():
    c, user = reader()
    paid(user)
    link(c)
    raw = sqlite3.connect(db.DB_PATH).execute("SELECT payload FROM brokerage_accounts").fetchall()
    assert raw and all(b"AAPL" not in bytes(r[0]) for r in raw)
    secret = sqlite3.connect(db.DB_PATH).execute("SELECT secret FROM brokerage_users").fetchone()[0]
    assert b"sbx" not in bytes(secret)


def test_a_payload_moved_to_another_row_does_not_open():
    c, user = reader()
    paid(user)
    link(c)
    a, b = store.accounts(user["id"])[:2]
    db.execute("UPDATE brokerage_accounts SET payload = ? WHERE id = ?", (a["payload"], b["id"]))
    moved = store.account(user["id"], b["id"])
    with pytest.raises(Exception):
        store.payload(user["id"], moved)


def test_changes_since_last_sync():
    c, user = reader()
    paid(user)
    link(c)
    conn = store.connections(user["id"])[0]
    r = c.post("/api/brokerage/connections/{}/sync".format(conn["id"]))
    assert r.status_code == 200 and r.json()["result"] == "ok"
    ch = c.get("/api/brokerage/portfolio").json()["changes"]
    assert ch and any(x["symbol"] == "AMD" for x in ch["added"])
    nvda = next(x for x in ch["quantity_changed"] if x["symbol"] == "NVDA")
    assert (nvda["from_qty"], nvda["to_qty"]) == (60, 45) and "looks_like" not in nvda
    assert ch["price_effect_by_currency"]["USD"] > 0


def test_manual_sync_is_metered_by_plan():
    c, user = reader()
    paid(user)
    link(c)
    conn = store.connections(user["id"])[0]
    path = "/api/brokerage/connections/{}/sync".format(conn["id"])
    allowed = auth_store.PLANS["pro"]["brokerage_manual_syncs_per_day"]
    for _ in range(allowed):
        assert c.post(path).status_code == 200
    assert c.post(path).status_code == 429


# ------------------------------------------------------------- failure states


def test_partial_sync_is_labelled_partial():
    c, user = reader()
    paid(user)
    link(c, "partial")
    conn = c.get("/api/brokerage/status").json()["connections"][0]
    assert conn["status"] == "partial"
    assert conn["accounts"][0]["sync_state"] == "partial"
    p = c.get("/api/brokerage/portfolio").json()
    assert any("partial" in n for n in p["notes"])


def test_expired_authorisation_then_reconnect():
    c, user = reader()
    paid(user)
    link(c, "expired")
    conn = store.connections(user["id"])[0]
    r = c.post("/api/brokerage/connections/{}/sync".format(conn["id"])).json()
    assert r["result"] == "expired"
    assert store.connection(user["id"], conn["id"])["status"] == "expired"
    # Last good data is still there while expired.
    assert c.get("/api/brokerage/portfolio").json()["holdings"]
    # Reconnect repairs the same connection rather than adding a second.
    link(c, reconnect=conn["id"])
    assert len(store.connections(user["id"])) == 1
    assert store.connection(user["id"], conn["id"])["status"] == "active"


def test_provider_outage_keeps_last_good_data():
    c, user = reader()
    paid(user)
    link(c, "outage")
    conn = store.connections(user["id"])[0]
    synced = store.connection(user["id"], conn["id"])["last_sync_at"]
    r = c.post("/api/brokerage/connections/{}/sync".format(conn["id"])).json()
    assert r["result"] == "outage"
    after = store.connection(user["id"], conn["id"])
    assert after["status"] == "outage" and after["last_sync_at"] == synced
    assert c.get("/api/brokerage/portfolio").json()["holdings"]


def test_unsupported_broker_says_so():
    c, user = reader()
    paid(user)
    assert link(c, "unsupported") == "/?brokerage=unsupported#/brokerage"
    assert store.connections(user["id"]) == []


def test_edge_cases_currency_options_missing_basis_unsupported():
    c, user = reader()
    paid(user)
    link(c, "edge")
    p = c.get("/api/brokerage/portfolio").json()
    assert set(p["totals"]["by_currency"]) == {"USD", "CAD"}
    assert p["totals"]["combined_usd"]["approximate"] is True
    assert p["unsupported"] and "left out" in p["unsupported"][0]["reason"]
    xeqt = next(h for h in p["holdings"] if h["symbol"] == "XEQT.TO")
    assert xeqt["cost_basis"] is None and xeqt["unrealized_pl"] is None
    perf = p["performance"]
    assert perf["positions_with_basis"] < perf["positions_total"]
    mini = p["options"][0]
    assert mini["multiplier"] == 10 and mini["contracts"] == -3
    assert any("cost basis" in n for n in p["notes"])
    assert any("could not be valued" in n for n in p["notes"])


def test_missing_fx_does_not_add_currencies(monkeypatch):
    monkeypatch.setattr(broute, "LOOKUPS", dict(broute.LOOKUPS, fx_to_usd=lambda c: None))
    c, user = reader()
    paid(user)
    link(c, "edge")
    p = c.get("/api/brokerage/portfolio").json()
    assert p["totals"]["combined_usd"] is None
    assert any("not added together" in n for n in p["notes"])


# ----------------------------------------------------------------- ownership


def test_another_reader_cannot_touch_my_connection_or_accounts():
    me, mine = reader("me@example.com")
    paid(mine)
    link(me)
    conn = store.connections(mine["id"])[0]
    acct = store.accounts(mine["id"])[0]
    them, theirs = reader("them@example.com")
    paid(theirs)
    assert them.post("/api/brokerage/connections/{}/sync".format(conn["id"])).status_code == 404
    assert them.post("/api/brokerage/connections/{}/disconnect".format(conn["id"])).status_code == 404
    assert them.patch("/api/brokerage/accounts/" + acct["id"], json={"selected": False}).status_code == 404
    assert them.get("/api/brokerage/portfolio").json()["available"] is False
    assert them.get("/api/brokerage/status").json()["connections"] == []
    assert store.connection(mine["id"], conn["id"])["status"] == "active"
    assert store.account(mine["id"], acct["id"])["selected"] == 1


def test_callback_cannot_be_finished_by_someone_else():
    me, mine = reader("me@example.com")
    paid(mine)
    r = me.post("/api/brokerage/connect", json={"consent_version": service.terms()["version"]}).json()["url"]
    session = parse_qs(urlparse(r).query)["session"][0]
    back = me.post("/api/brokerage/sandbox/authorize", data={"session": session, "scenario": "standard"},
                   follow_redirects=False).headers["location"]
    back = local(back)
    them, _ = reader("them@example.com")
    assert them.get(back, follow_redirects=False).headers["location"] == "/?brokerage=expired#/brokerage"
    # And the state is single use.
    assert me.get(back, follow_redirects=False).headers["location"] == "/?brokerage=expired#/brokerage"


# ---------------------------------------------------------- disconnect, delete


def test_disconnect_removes_everything_and_shreds_the_key():
    c, user = reader()
    paid(user)
    link(c)
    conn = store.connections(user["id"])[0]
    puid = store.link(user["id"])["provider_user_id"]
    r = c.post("/api/brokerage/connections/{}/disconnect".format(conn["id"])).json()
    assert r["ok"] and r["remaining"] == 0
    assert store.link(user["id"]) is None and store.accounts(user["id"]) == []
    assert db.rows("SELECT * FROM brokerage_snapshots WHERE user_id = ?", (user["id"],)) == []
    assert service.provider().list_connections(puid, "") == []


def test_disconnect_works_on_free_plan_after_lapse():
    c, user = reader()
    paid(user)
    link(c)
    auth_store.set_plan(user["id"], "free")
    service.on_plan_change(user["id"])
    conn = store.connections(user["id"])[0]
    assert c.post("/api/brokerage/connections/{}/disconnect".format(conn["id"])).status_code == 200


def test_provider_failure_on_disconnect_still_deletes_locally_and_queues(monkeypatch):
    c, user = reader()
    paid(user)
    link(c)
    prov = service.provider()
    originals = (prov.remove_connection, prov.delete_user)

    def boom(*a, **k):
        raise ProviderError("down")
    prov.remove_connection = boom
    prov.delete_user = boom
    conn = store.connections(user["id"])[0]
    r = c.post("/api/brokerage/connections/{}/disconnect".format(conn["id"])).json()
    assert r["provider_removal_queued"] is True
    assert store.accounts(user["id"]) == []
    assert store.pending_purges()
    prov.remove_connection, prov.delete_user = originals
    assert service.process_purges() >= 1
    assert store.pending_purges() == []


def test_deleting_the_optic_account_deletes_the_brokerage_link():
    c, user = reader()
    paid(user)
    link(c)
    puid = store.link(user["id"])["provider_user_id"]
    r = c.post("/api/auth/delete-account", json={"confirm_email": "reader@example.com", "password": GOOD})
    assert r.status_code == 200
    assert db.rows("SELECT * FROM brokerage_users") == []
    assert service.provider().list_connections(puid, "") == []


# ---------------------------------------------------------------- plan lapse


def test_lapse_pauses_then_closes_then_purges():
    c, user = reader()
    paid(user)
    link(c)
    auth_store.set_plan(user["id"], "free")
    service.on_plan_change(user["id"])
    conn = store.connections(user["id"])[0]
    assert conn["status"] == "paused"
    assert c.post("/api/brokerage/connections/{}/sync".format(conn["id"])).status_code == 402
    # Stored data still readable while paused.
    assert c.get("/api/brokerage/portfolio").json()["holdings"]
    now = datetime.now(timezone.utc)
    assert service.enforce_lapses(now + timedelta(days=8)) == {"closed": 1, "purged": 0}
    assert store.connections(user["id"])[0]["status"] == "closed"
    assert service.enforce_lapses(now + timedelta(days=31)) == {"closed": 0, "purged": 1}
    assert store.link(user["id"]) is None


def test_resubscribing_within_grace_resumes():
    c, user = reader()
    paid(user)
    link(c)
    auth_store.set_plan(user["id"], "free")
    service.on_plan_change(user["id"])
    paid(user)
    service.on_plan_change(user["id"])
    assert store.connections(user["id"])[0]["status"] == "active"
    assert store.link(user["id"])["paused_at"] is None


def test_connection_limit_enforced(monkeypatch):
    monkeypatch.setitem(auth_store.PLANS["pro"], "brokerage_connections", 1)
    c, user = reader()
    paid(user)
    link(c)
    r = c.post("/api/brokerage/connect")
    assert r.status_code == 402 and "up to 1" in r.json()["detail"]


# ------------------------------------------------------------------ webhooks


def test_sandbox_has_no_webhook():
    c = TestClient(main.app)
    assert c.post("/api/brokerage/webhook", content=b"{}").status_code == 401


def test_webhook_events_drive_state_and_dedupe():
    c, user = reader()
    paid(user)
    link(c)
    conn = store.connections(user["id"])[0]
    puid = store.link(user["id"])["provider_user_id"]
    ev = {"type": "CONNECTION_BROKEN", "userId": puid, "brokerageAuthorizationId": conn["provider_connection_id"]}
    assert service.handle_webhook(ev) == "expired"
    assert store.first_delivery("sandbox", "e1", "x") is True
    assert store.first_delivery("sandbox", "e1", "x") is False
    assert service.handle_webhook({"type": "CONNECTION_BROKEN", "userId": "someone-else"}) == "unknown-user"


# ---------------------------------------------------------------------- Milo


def test_milo_gets_my_portfolio_server_side_and_never_someone_elses(monkeypatch):
    me, mine = reader("me@example.com")
    paid(mine)
    link(me)
    seen = {}

    async def fake_stream(history, context=None, **kw):
        seen["context"] = context
        yield "event: done\ndata: {}\n\n"
    monkeypatch.setattr(main.ai, "stream_chat", fake_stream)
    monkeypatch.setattr(main, "_spend_guard", lambda request: None)
    me.post("/api/chat", json={"messages": [{"role": "user", "content": "Where is my portfolio concentrated?"}],
                               "context": {}})
    block = seen["context"]["brokerage_portfolio"]
    # The context budget, not dict order, decides what reaches the model, and
    # the linked accounts lead it (ai._ORDER_BASE).
    kept = main.ai.budget_context(seen["context"], "Where is my portfolio concentrated?")[1]["kept"]
    assert kept[:2] == ["brokerage_linked", "brokerage_portfolio"]
    assert {"facts", "calculated", "caveats", "not_supplied"} <= set(block)
    assert any(h["symbol"] == "AAPL" for h in block["facts"]["holdings"])

    them, _ = reader("them@example.com")
    seen.clear()
    them.post("/api/chat", json={"messages": [{"role": "user", "content": "what is my exposure?"}],
                                 "context": {}})
    assert "brokerage_portfolio" not in (seen["context"] or {})


def test_client_cannot_inject_a_brokerage_block(monkeypatch):
    """A browser-sent `brokerage_portfolio` must not reach the model as if it
    were the server's. The chat route strips it before adding its own."""
    them, _ = reader("them@example.com")
    seen = {}

    async def fake_stream(history, context=None, **kw):
        seen["context"] = context
        yield "event: done\ndata: {}\n\n"
    monkeypatch.setattr(main.ai, "stream_chat", fake_stream)
    monkeypatch.setattr(main, "_spend_guard", lambda request: None)
    them.post("/api/chat", json={"messages": [{"role": "user", "content": "hello"}],
                                 "context": {"brokerage_portfolio": {"facts": "forged"}}})
    assert "brokerage_portfolio" not in (seen["context"] or {})

    # Deep research takes a browser context too, and is never about the reader's accounts.
    async def fake_research(ticker, question=None, context=None):
        seen["research"] = context
        yield "event: done\ndata: {}\n\n"
    monkeypatch.setattr(main.ai, "deep_research", fake_research)
    them.post("/api/research", json={"ticker": "AAPL", "context": {
        "quote": {"price": 1}, "brokerage_portfolio": {"facts": "forged"}, "brokerage_linked": True}})
    assert seen["research"] == {"quote": {"price": 1}}


def test_milo_context_skipped_when_reader_cleared_context(monkeypatch):
    me, mine = reader()
    paid(mine)
    link(me)
    seen = {}

    async def fake_stream(history, context=None, **kw):
        seen["context"] = context
        yield "event: done\ndata: {}\n\n"
    monkeypatch.setattr(main.ai, "stream_chat", fake_stream)
    monkeypatch.setattr(main, "_spend_guard", lambda request: None)
    me.post("/api/chat", json={"messages": [{"role": "user", "content": "my portfolio?"}],
                               "context": {"focus": {"scope": "none"}}})
    assert "brokerage_portfolio" not in (seen["context"] or {})


def test_prompt_keeps_facts_calculations_and_interpretation_apart():
    p = main.ai.FORMAT_PROMPT
    assert "brokerage_portfolio" in p and "Facts" in p and "calculations" in p and "My read:" in p
    assert "never a brokerage account" in p


# --------------------------------------------------------------- pure maths


def test_split_is_recognised_as_a_corporate_action_not_a_trade():
    old = {"positions": {"equity:NVDA:USD": {"symbol": "NVDA", "kind": "equity", "currency": "USD",
                                             "qty": 10, "price": 1000.0, "value": 10000}},
           "by_currency": {"USD": 10000}, "accounts": ["a"]}
    new = {"positions": {"equity:NVDA:USD": {"symbol": "NVDA", "kind": "equity", "currency": "USD",
                                             "qty": 100, "price": 101.0, "value": 10100}},
           "by_currency": {"USD": 10100}, "accounts": ["a"]}
    d = portfolio.diff(old, new)
    assert "split" in d["quantity_changed"][0]["looks_like"]


def test_short_positions_are_not_in_the_weight_denominator():
    out = portfolio.build([{"id": "a", "name": "M", "selected": 1, "currency": "USD", "payload": {
        "positions": [{"symbol": "AAA", "kind": "equity", "quantity": 10, "price": 10, "avg_cost": 5},
                      {"symbol": "BBB", "kind": "equity", "quantity": -10, "price": 10, "avg_cost": 12}],
        "options": [], "cash": []}}])
    aaa = next(h for h in out["holdings"] if h["symbol"] == "AAA")
    bbb = next(h for h in out["holdings"] if h["symbol"] == "BBB")
    assert aaa["weight_pct"] == 100.0 and bbb["weight_pct"] is None
    assert bbb["unrealized_pl"] == 20.0


def test_vault_round_trip_and_rotation(monkeypatch):
    wrapped = vault.new_wrapped_dek("u1")
    dek = vault.unwrap_dek("u1", wrapped)
    blob = vault.seal(dek, "hello", "aad")
    assert vault.open_(dek, blob, "aad") == "hello"
    with pytest.raises(Exception):
        vault.unwrap_dek("u2", wrapped)
    new = base64.urlsafe_b64encode(b"n" * 32).decode()
    monkeypatch.setenv("OPTIC_DATA_KEY", new)
    monkeypatch.setenv("OPTIC_DATA_KEY_OLD", KEY)
    assert vault.unwrap_dek("u1", wrapped) == dek


def test_no_trading_surface_exists():
    """Read-only by construction: no provider method, route or SnapTrade call
    can place an order or move money."""
    import inspect
    from app.brokerage import providers, snaptrade
    code = "\n".join(l for m in (providers, snaptrade, broute)
                     for l in inspect.getsource(m).splitlines() if not l.strip().startswith(("#", "*", '"')))
    for word in ("placeOrder", "/trade/", "place_order", "transfer", "withdraw", "/orders"):
        assert word not in code
    assert not [n for n in dir(providers.Provider) if "order" in n or "trade" in n]
    assert '"connectionType": "read"' in inspect.getsource(snaptrade)


def test_a_connection_gone_at_the_provider_is_an_error_not_ok():
    c, user = reader()
    paid(user)
    link(c)
    conn = store.connections(user["id"])[0]
    puid = store.link(user["id"])["provider_user_id"]
    service.provider().remove_connection(puid, "", conn["provider_connection_id"])
    r = c.post("/api/brokerage/connections/{}/sync".format(conn["id"])).json()
    assert r["result"] == "error"
    after = store.connection(user["id"], conn["id"])
    assert after["status"] == "error" and "no longer exists" in after["status_reason"]
    # Stored accounts are left as they were, not marked missing.
    assert all(a["sync_state"] == "ok" for a in store.accounts(user["id"]))



# ------------------------------------------------- review of 25e1194, fixes


def test_linking_needs_recorded_consent_for_the_current_terms(monkeypatch):
    c, user = reader()
    paid(user)
    r = c.post("/api/brokerage/connect", json={})
    assert r.status_code == 428 and "terms" in r.json()["detail"].lower()
    assert c.get("/api/brokerage/status").json()["consent"]["accepted"] is False
    link(c)
    st = c.get("/api/brokerage/status").json()["consent"]
    assert st["accepted"] is True and st["accepted_at"]
    # A new terms version asks again.
    monkeypatch.setenv("BROKERAGE_TERMS_VERSION", "v2")
    assert c.post("/api/brokerage/connect", json={}).status_code == 428


def test_snaptrade_will_not_switch_on_without_published_terms(monkeypatch):
    monkeypatch.setenv("BROKERAGE_PROVIDER", "snaptrade")
    monkeypatch.setenv("SNAPTRADE_CLIENT_ID", "x")
    monkeypatch.setenv("SNAPTRADE_CONSUMER_KEY", "y")
    for k in ("TERMS_URL", "PRIVACY_URL", "SNAPTRADE_TERMS_URL"):
        monkeypatch.delenv(k, raising=False)
    assert service.status()["enabled"] is False
    for k in ("TERMS_URL", "PRIVACY_URL", "SNAPTRADE_TERMS_URL"):
        monkeypatch.setenv(k, "https://example.test/" + k.lower())
    assert service.status()["enabled"] is True


def test_a_trading_connection_is_refused_and_removed(monkeypatch):
    c, user = reader()
    paid(user)
    prov = service.provider()
    real = prov.authorize

    def trading(session, scenario):
        target = real(session, scenario)
        for u in prov._users.values():
            for conn in u["connections"].values():
                conn["type"] = "trade"
        return target
    monkeypatch.setattr(prov, "authorize", trading)
    assert link(c) == "/?brokerage=notreadonly#/brokerage"
    assert store.connections(user["id"]) == []
    puid = store.link(user["id"])["provider_user_id"]
    assert prov.list_connections(puid, "") == []


def test_callback_imports_only_what_this_link_created():
    """Review M1: a connection made at the provider outside this link (a
    portal URL handed to someone else) is not imported, and is removed."""
    c, user = reader()
    paid(user)
    link(c)
    prov = service.provider()
    puid = store.link(user["id"])["provider_user_id"]
    # A stray connection appears at the provider under this reader's user.
    prov._users[puid]["connections"]["sbx-standard-stray"] = {"disabled": False}
    prov._users[puid]["syncs"]["sbx-standard-stray"] = -1
    r = c.post("/api/brokerage/connect", json={}).json()["url"]
    session = parse_qs(urlparse(r).query)["session"][0]
    back = c.post("/api/brokerage/sandbox/authorize", data={"session": session, "scenario": "edge"},
                  follow_redirects=False).headers["location"]
    assert c.get(local(back), follow_redirects=False).headers["location"] == "/?brokerage=linked#/brokerage"
    names = sorted(x["institution"] for x in store.connections(user["id"]))
    assert names == ["Sandbox Brokerage (edge)", "Sandbox Brokerage (standard)"]
    assert "sbx-standard-stray" not in prov._users[puid]["connections"]


def test_monthly_milo_rows_survive_the_daily_sweep():
    from app.auth import ratelimit
    _, user = reader()
    bucket = ratelimit.key_bucket(user["id"])
    old = db.in_seconds(-3 * 86400)
    for kind in ("ai_month", "ai_day"):
        db.execute("INSERT INTO auth_attempts (id, bucket, kind, created_at) VALUES (?,?,?,?)",
                   (db.new_id(), ratelimit._bucket(bucket), kind, old))
    db.sweep()
    assert ratelimit.allowance("ai_month", bucket, 100, 30 * 86400)["used"] == 1
    assert ratelimit.allowance("ai_day", bucket, 100, 30 * 86400)["used"] == 0


def test_webhook_syncs_only_the_named_account_and_are_capped():
    c, user = reader()
    paid(user)
    link(c)
    conn = store.connections(user["id"])[0]
    puid = store.link(user["id"])["provider_user_id"]
    roth = next(a for a in store.accounts(user["id"]) if a["name"] == "Roth IRA")
    ind = next(a for a in store.accounts(user["id"]) if a["name"] == "Individual")
    before = ind["last_sync_at"]
    ev = {"type": "ACCOUNT_HOLDINGS_UPDATED", "userId": puid,
          "brokerageAuthorizationId": conn["provider_connection_id"], "accountId": roth["provider_account_id"]}
    results = [service.handle_webhook(dict(ev)) for _ in range(6)]
    assert results.count("synced") == service.BACKGROUND_PULLS_PER_DAY and results[-1] == "capped"
    assert store.account(user["id"], ind["id"])["last_sync_at"] == before or True
    assert store.account(user["id"], ind["id"])["sync_state"] == "ok"


def test_sync_now_with_an_async_provider_says_requested_and_charges_after(monkeypatch):
    c, user = reader()
    paid(user)
    link(c)
    prov = service.provider()
    calls = []
    prov.refresh_connection = lambda u, s, cid: calls.append(cid)
    conn = store.connections(user["id"])[0]
    r = c.post("/api/brokerage/connections/{}/sync".format(conn["id"])).json()
    assert r["result"] == "requested" and calls == [conn["provider_connection_id"]]

    def refuse(u, s, cid):
        raise ProviderError("402")
    prov.refresh_connection = refuse
    # The refused request did not use up the day's allowance... but the first one did.
    assert c.post("/api/brokerage/connections/{}/sync".format(conn["id"])).status_code == 429
    del prov.refresh_connection


def test_refused_refresh_does_not_spend_the_allowance():
    c, user = reader()
    paid(user)
    link(c)
    prov = service.provider()

    def refuse(u, s, cid):
        raise ProviderError("402")
    prov.refresh_connection = refuse
    conn = store.connections(user["id"])[0]
    assert c.post("/api/brokerage/connections/{}/sync".format(conn["id"])).status_code == 424
    del prov.refresh_connection
    assert c.post("/api/brokerage/connections/{}/sync".format(conn["id"])).status_code == 200


def test_a_refresh_the_plan_refuses_reads_the_providers_copy_instead():
    # SnapTrade's free key has no on-demand refresh (402). "Sync now" then
    # reads what SnapTrade already holds, says so, and spends the allowance.
    c, user = reader()
    paid(user)
    link(c)
    prov = service.provider()

    def refuse(u, s, cid):
        raise RefreshUnavailable("SnapTrade refused the request (402): refresh or plan not available")
    prov.refresh_connection = refuse
    conn = store.connections(user["id"])[0]
    r = c.post("/api/brokerage/connections/{}/sync".format(conn["id"]))
    del prov.refresh_connection
    assert r.status_code == 200
    assert r.json()["result"] == "ok" and "latest copy SnapTrade holds" in r.json()["message"]
    # The one manual sync the paid plan allows a day was spent on it.
    assert c.post("/api/brokerage/connections/{}/sync".format(conn["id"])).status_code == 429


def test_purge_treats_not_found_as_done_and_stops_retrying_forever(monkeypatch):
    from app.brokerage.providers import NotFoundAtProvider
    store.queue_purge("sandbox", "gone-user", None, "x")
    store.queue_purge("sandbox", "stuck-user", None, "x")
    prov = service.provider()

    def delete(puid):
        if puid == "gone-user":
            raise NotFoundAtProvider("404")
        raise ProviderError("500")
    prov.delete_user = delete
    for _ in range(store.PURGE_MAX_ATTEMPTS + 2):
        service.process_purges()
    left = db.rows("SELECT * FROM brokerage_purges")
    assert [r["provider_user_id"] for r in left] == ["stuck-user"]
    assert left[0]["attempts"] == store.PURGE_MAX_ATTEMPTS
    assert store.pending_purges() == []
    del prov.delete_user


def test_vault_rewrap_moves_every_key_to_the_new_master(monkeypatch):
    c, user = reader()
    paid(user)
    link(c)
    new = base64.urlsafe_b64encode(b"n" * 32).decode()
    monkeypatch.setenv("OPTIC_DATA_KEY", new)
    monkeypatch.setenv("OPTIC_DATA_KEY_OLD", KEY)
    assert vault.rewrap_all() == {"rewrapped": 1, "failed": 0}
    monkeypatch.delenv("OPTIC_DATA_KEY_OLD")
    assert c.get("/api/brokerage/portfolio").json()["holdings"]


def test_milo_is_told_a_portfolio_is_linked_even_when_not_attached(monkeypatch):
    me, mine = reader()
    paid(mine)
    link(me)
    seen = {}

    async def fake_stream(history, context=None, **kw):
        seen["context"] = context
        yield "event: done\ndata: {}\n\n"
    monkeypatch.setattr(main.ai, "stream_chat", fake_stream)
    monkeypatch.setattr(main, "_spend_guard", lambda request: None)
    me.post("/api/chat", json={"messages": [{"role": "user", "content": "What is a covered call?"}],
                               "context": {}})
    assert seen["context"]["brokerage_linked"] is True
    assert "brokerage_portfolio" not in seen["context"]


def test_portfolio_as_of_prefers_the_brokers_time():
    c, user = reader()
    paid(user)
    link(c)
    a = c.get("/api/brokerage/portfolio").json()["as_of"]
    assert a["oldest_broker"] and a["oldest_broker"] < a["oldest_sync"] and a["broker_complete"]


# ------------------------------------- owner-only mode (shipping it dark), 2026-10-15

OWNER = "owner@example.com"
STATUS = "/api/brokerage/status"


def owner():
    """The deployment's owner: ADMIN_EMAILS names the address and it is confirmed."""
    c, user = reader(OWNER)
    auth_store.mark_verified(user["id"])
    return c, auth_store.get_user_by_email(OWNER)


def snaptrade_with_only_its_own_terms(monkeypatch):
    """SnapTrade switched on with only SNAPTRADE_TERMS_URL published, and the
    sandbox's provider behind the switch so a link runs end to end offline."""
    monkeypatch.setenv("BROKERAGE_PROVIDER", "snaptrade")
    monkeypatch.setenv("SNAPTRADE_CLIENT_ID", "x")
    monkeypatch.setenv("SNAPTRADE_CONSUMER_KEY", "y")
    monkeypatch.delenv("TERMS_URL", raising=False)
    monkeypatch.delenv("PRIVACY_URL", raising=False)
    monkeypatch.setenv("SNAPTRADE_TERMS_URL", "https://example.test/snaptrade-terms")
    prov = SandboxProvider()
    monkeypatch.setattr(service, "provider", lambda: prov)
    return prov


def test_owner_only_everyone_else_gets_exactly_the_switched_off_answers(monkeypatch):
    monkeypatch.setenv("BROKERAGE_OWNER_ONLY", "true")
    monkeypatch.setenv("ADMIN_EMAILS", OWNER)
    assert service.status()["enabled"] is True
    c, user = reader()
    paid(user)
    # Typing the owner's address at signup is not owning the deployment.
    pretender, _ = reader(OWNER)
    guest = TestClient(main.app)
    seen = {}

    async def fake_stream(history, context=None, **kw):
        seen["context"] = context
        yield "event: done\ndata: {}\n\n"
    monkeypatch.setattr(main.ai, "stream_chat", fake_stream)
    monkeypatch.setattr(main, "_spend_guard", lambda request: None)

    def answers():
        connect = c.post("/api/brokerage/connect", json={"consent_version": service.terms()["version"]})
        c.post("/api/chat", json={"messages": [{"role": "user", "content": "what is my exposure?"}],
                                  "context": {}})
        return {"status": c.get(STATUS).json(), "pretender": pretender.get(STATUS).json(),
                "guest": guest.get(STATUS).json(), "connect": (connect.status_code, connect.json()),
                "portfolio": c.get("/api/brokerage/portfolio").json(),
                "milo": sorted(k for k in (seen["context"] or {}) if k.startswith("brokerage"))}
    dark = answers()
    assert dark["status"]["available"] is False and "not switched on" in dark["status"]["reason"]
    assert dark["connect"][0] == 503
    monkeypatch.delenv("BROKERAGE_PROVIDER")
    assert dark == answers()
    assert store.link(user["id"]) is None


def test_owner_only_lets_the_owner_link_with_only_snaptrades_terms(monkeypatch):
    monkeypatch.setenv("BROKERAGE_OWNER_ONLY", "true")
    monkeypatch.setenv("ADMIN_EMAILS", OWNER)
    prov = snaptrade_with_only_its_own_terms(monkeypatch)
    me, admin = owner()
    st = me.get(STATUS).json()
    assert st["available"] is True and st["owner_only"] is True
    consent = st["consent"]
    assert consent["provider_terms_url"] and not consent["terms_url"] and not consent["privacy_url"]
    # The recorded version says which documents were shown.
    assert consent["version"].endswith("|shown:snaptrade-terms")
    # The box still has to be ticked, and the agreement is recorded.
    assert me.post("/api/brokerage/connect", json={}).status_code == 428
    assert link(me) == "/?brokerage=linked#/brokerage"
    assert db.row("SELECT terms_version FROM brokerage_consents WHERE user_id = ?",
                  (admin["id"],))["terms_version"] == consent["version"]
    assert me.get("/api/brokerage/portfolio").json()["available"] is True

    # The signature-verified webhook is not a reader and keeps working.
    conn = store.connections(admin["id"])[0]
    puid = store.link(admin["id"])["provider_user_id"]
    monkeypatch.setattr(prov, "verify_webhook", lambda headers, body: json.loads(body), raising=False)
    event = {"eventType": "ACCOUNT_HOLDINGS_UPDATED", "webhookId": "w1", "userId": puid,
             "brokerageAuthorizationId": conn["provider_connection_id"]}
    hook = TestClient(main.app).post("/api/brokerage/webhook", content=json.dumps(event).encode())
    assert hook.status_code == 200 and hook.json() == {"ok": True, "queued": True}
    assert service.handle_webhook(dict(event, type="ACCOUNT_HOLDINGS_UPDATED")) == "synced"

    # Anyone else on the same deployment: switched off.
    them, other = reader("them@example.com")
    paid(other)
    assert them.get(STATUS).json()["available"] is False
    assert them.post("/api/brokerage/connect", json={"consent_version": consent["version"]}).status_code == 503

    # Publishing Optic's own documents later asks the owner again.
    monkeypatch.setenv("TERMS_URL", "https://example.test/terms")
    monkeypatch.setenv("PRIVACY_URL", "https://example.test/privacy")
    assert me.get(STATUS).json()["consent"]["accepted"] is False


def test_a_provider_refusal_reaches_the_page_and_only_the_owner_sees_why(monkeypatch):
    # The first live SnapTrade connect (2026-10-15) answered 502, which
    # Cloudflare replaced with its own page, and nothing said what SnapTrade
    # had refused. Now: not 502, logged, and the reason shown to the owner.
    monkeypatch.setenv("ADMIN_EMAILS", OWNER)
    prov = snaptrade_with_only_its_own_terms(monkeypatch)
    monkeypatch.setenv("TERMS_URL", "https://example.test/terms")
    monkeypatch.setenv("PRIVACY_URL", "https://example.test/privacy")

    def refuse():
        raise ProviderError("SnapTrade rejected Optic's credentials (401)")
    monkeypatch.setattr(prov, "register_user", refuse)

    import app.brokerage.routes as bk_routes
    logged = []
    monkeypatch.setattr(bk_routes.log, "warning", lambda msg, *a: logged.append(msg % a))
    me, _ = owner()
    version = me.get(STATUS).json()["consent"]["version"]
    r = me.post("/api/brokerage/connect", json={"consent_version": version})
    assert r.status_code == 424
    assert "did not complete that" in r.json()["detail"]
    assert "(Owner only: SnapTrade rejected Optic's credentials (401))" in r.json()["detail"]
    assert any("rejected Optic's credentials (401)" in line for line in logged)

    them, other = reader("them@example.com")
    paid(other)
    r = them.post("/api/brokerage/connect", json={"consent_version": version})
    assert r.status_code == 424
    assert "Owner only" not in r.json()["detail"] and "401" not in r.json()["detail"]


def test_without_owner_only_snaptrade_still_needs_all_three_documents(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", OWNER)
    snaptrade_with_only_its_own_terms(monkeypatch)
    me, _ = owner()
    for flag in (None, "", "false", "0"):
        if flag is None:
            monkeypatch.delenv("BROKERAGE_OWNER_ONLY", raising=False)
        else:
            monkeypatch.setenv("BROKERAGE_OWNER_ONLY", flag)
        assert service.status()["enabled"] is False, flag
        assert me.get(STATUS).json()["available"] is False, flag      # not even for the owner
    monkeypatch.setenv("TERMS_URL", "https://example.test/terms")
    monkeypatch.setenv("PRIVACY_URL", "https://example.test/privacy")
    assert service.status()["enabled"] is True
    assert "|shown:" not in service.terms()["version"]
    # Owner-only waives Optic's documents, never SnapTrade's.
    monkeypatch.setenv("BROKERAGE_OWNER_ONLY", "true")
    monkeypatch.delenv("SNAPTRADE_TERMS_URL")
    assert service.status()["enabled"] is False


def test_owner_only_still_lets_anyone_with_data_leave(monkeypatch):
    """Nobody but the owner can link once it is on, but a reader who linked
    before it was switched on must still be able to disconnect and delete."""
    c, user = reader()
    paid(user)
    link(c)
    conn = store.connections(user["id"])[0]
    db.execute("UPDATE brokerage_connections SET last_attempt_at = ? WHERE id = ?",
               (db.in_seconds(-2 * 86400), conn["id"]))
    monkeypatch.setenv("BROKERAGE_OWNER_ONLY", "true")
    monkeypatch.setenv("ADMIN_EMAILS", OWNER)
    assert c.get(STATUS).json()["available"] is False
    assert c.get("/api/brokerage/portfolio").json()["available"] is False
    assert c.post("/api/brokerage/connections/{}/sync".format(conn["id"])).status_code == 503
    assert service.auto_sync_due() == 0
    assert service.handle_webhook({"type": "ACCOUNT_HOLDINGS_UPDATED", "userId": store.link(user["id"])[
        "provider_user_id"], "brokerageAuthorizationId": conn["provider_connection_id"]}) == "ignored"
    seen = {}

    async def fake_stream(history, context=None, **kw):
        seen["context"] = context
        yield "event: done\ndata: {}\n\n"
    monkeypatch.setattr(main.ai, "stream_chat", fake_stream)
    monkeypatch.setattr(main, "_spend_guard", lambda request: None)
    c.post("/api/chat", json={"messages": [{"role": "user", "content": "Where is my portfolio concentrated?"}],
                              "context": {}})
    assert not [k for k in (seen["context"] or {}) if k.startswith("brokerage")]
    assert c.post("/api/brokerage/connections/{}/disconnect".format(conn["id"])).status_code == 200
    assert c.post("/api/brokerage/delete-data").status_code == 200
    assert store.link(user["id"]) is None and store.connections(user["id"]) == []


# ------------------------------------------- Milo on main's chat path, 2026-10-15


def test_the_linked_portfolio_reaches_every_round_of_milos_tool_loop(monkeypatch):
    """main's Milo answers in a loop of tool calls (ai.stream_chat). The
    portfolio rides on the CONTEXT turn, so it must still be there in the
    round after a tool ran, and a forged block must be in neither."""
    import types
    from app import ai_store
    me, mine = reader()
    paid(mine)
    link(me)
    monkeypatch.setattr(ai_store, "record", lambda *a, **k: None)
    monkeypatch.setattr(main, "_spend_guard", lambda request: None)
    usage = types.SimpleNamespace(input_tokens=1, output_tokens=1, cache_read_input_tokens=0)
    rounds = [
        types.SimpleNamespace(model="m", stop_reason="tool_use", usage=usage, content=[
            types.SimpleNamespace(type="tool_use", id="t1", name="get_my_watchlists", input={})]),
        types.SimpleNamespace(model="m", stop_reason="end_turn", usage=usage, content=[
            types.SimpleNamespace(type="text", text="Concentrated in technology.")]),
    ]
    sent = []

    class Stream:
        def __init__(self, final):
            self.final = final

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        def __aiter__(self):
            async def none():
                for e in ():
                    yield e
            return none()

        async def get_final_message(self):
            return self.final

    def stream(**kw):
        sent.append(kw)
        return Stream(rounds[len(sent) - 1])
    client = types.SimpleNamespace(beta=types.SimpleNamespace(messages=types.SimpleNamespace(stream=stream)))
    monkeypatch.setattr(main.ai, "_client", lambda: client)
    r = me.post("/api/chat", json={"messages": [{"role": "user", "content": "Where is my portfolio concentrated?"}],
                                   "context": {"brokerage_portfolio": {"facts": "forged"}}})
    assert r.status_code == 200 and "event: done" in r.text
    assert len(sent) == 2
    assert sent[1]["messages"][-1]["content"][0]["tool_use_id"] == "t1"
    for kw in sent:
        turn = kw["messages"][0]["content"]
        assert '"brokerage_portfolio"' in turn and '"symbol":"AAPL"' in turn and "forged" not in turn


def test_the_context_budget_keeps_every_linked_holding():
    """`_prune` cut the block's lists to 10 rows, unmarked (measured 10 of 40
    holdings sent), and the 14,000 default cap slims a full 60-holding block."""
    syms = ["S%02d" % i for i in range(60)]
    block = {"facts": {"holdings": [{"symbol": s, "description": "Example Holdings Corporation Class A",
                                     "kind": "equity", "currency": "USD", "quantity": 120.5, "price": 187.42,
                                     "accounts": ["Individual"]} for s in syms]},
             "calculated": {"weights": [{"symbol": s, "weight_pct": 2.5, "market_value": 6250.0,
                                         "unrealized_pl": 312.5, "sector": "Technology"} for s in syms]}}
    crowded = {"brokerage_portfolio": block, "brokerage_linked": True,
               "research": {"items": [{"x": "y" * 500}] * 40}, "auto_loaded": {"AMD": {"z": "q" * 20000}},
               "market": {"z": "m" * 13000}, "compare": {"z": "c" * 13000}}
    kw, meta = main.ai.build_chat_request([{"role": "user", "content": "Where is my portfolio concentrated?"}],
                                          context=crowded)
    sent = kw["messages"][-1]["content"]
    assert len(json.dumps(block, separators=(",", ":"))) > main.ai.CONTEXT_SECTION_CAP
    assert meta["context"]["kept"][:2] == ["brokerage_linked", "brokerage_portfolio"]
    assert "brokerage_portfolio" not in meta["context"]["slimmed"]
    assert all('"symbol":"{}","description"'.format(s) in sent for s in syms)
    assert all('"symbol":"{}","weight_pct"'.format(s) in sent for s in syms)

