"""The Brokerage workspace's data foundation (2026-10-15): transactions and
the provider's balance history fetched and sealed per account, snapshots kept
one a day for collected history, a disconnected account cut out of that
history, the same broker account recognised across a second connection, and a
money-market fund counted once.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app import db
from app.brokerage import portfolio, service, store
from app.brokerage.providers import Activity, FeatureUnavailable, SandboxProvider

from tests.test_brokerage import link, paid, reader, sandbox  # noqa: F401  (autouse fixture)


def _linked(scenario="standard"):
    c, user = reader()
    paid(user)
    link(c, scenario)
    return c, user


def test_a_sync_stores_transactions_and_balance_history_sealed():
    c, user = _linked()
    uid = user["id"]
    accts = {a["name"]: a for a in store.accounts(uid)}
    ind, roth = accts["Individual"], accts["Roth IRA"]
    acts = store.activities(uid, ind["id"])
    assert acts and acts[0]["type"] == "CONTRIBUTION" and acts[0]["trade_date"] == "2026-01-02"
    assert round(sum(a["amount"] or 0 for a in acts), 2) == 2400.00     # the cash the holdings report
    assert round(sum(a["amount"] or 0 for a in store.activities(uid, roth["id"])), 2) == 300.00
    hist = store.history(uid, ind["id"])
    assert hist["currency"] == "USD" and hist["points"][0][0] == "2026-01-02"
    row = store.account(uid, ind["id"])
    assert row["activities_state"] == "ok" and row["history_state"] == "ok"
    # Sealed: neither the amounts nor the symbols are in the database as text.
    raw = db.row("SELECT activities, history FROM brokerage_accounts WHERE id = ?", (ind["id"],))
    assert b"CONTRIBUTION" not in raw["activities"] and b"2026-01-02" not in raw["history"]


def test_history_is_fetched_once_a_day_not_on_every_sync(monkeypatch):
    c, user = _linked()
    uid = user["id"]
    calls = []
    prov = service.provider()
    real = prov.activities
    monkeypatch.setattr(prov, "activities", lambda *a, **k: calls.append(1) or real(*a, **k))
    conn = store.connections(uid)[0]
    service.sync_connection(user, conn)
    assert calls == []                                   # fetched at link time, under a day ago
    for a in store.accounts(uid):
        db.execute("UPDATE brokerage_accounts SET activities_synced_at = ? WHERE id = ?",
                   ((datetime.now(timezone.utc) - timedelta(hours=21)).isoformat(), a["id"]))
    service.sync_connection(user, conn)
    assert len(calls) == 2                               # once per account


def test_an_unavailable_balance_history_is_remembered_and_never_fails_the_sync():
    c, user = _linked("edge")
    uid = user["id"]
    result = service.sync_connection(user, store.connections(uid)[0])
    assert result["result"] in ("ok", "partial")
    for a in store.accounts(uid):
        assert a["history_state"] == "unavailable" and store.history(uid, a["id"]) is None
    # The CAD account's transactions still arrived.
    tfsa = next(a for a in store.accounts(uid) if a["name"] == "TFSA")
    assert store.activities(uid, tfsa["id"])[0]["currency"] == "CAD"


def test_a_failed_transactions_fetch_keeps_what_was_stored(monkeypatch):
    c, user = _linked()
    uid = user["id"]
    ind = next(a for a in store.accounts(uid) if a["name"] == "Individual")
    before = store.activities(uid, ind["id"])
    prov = service.provider()
    from app.brokerage.providers import ProviderError

    def broken(*a, **k):
        raise ProviderError("transactions did not arrive")
    monkeypatch.setattr(prov, "activities", broken)
    db.execute("UPDATE brokerage_accounts SET activities_synced_at = NULL WHERE user_id = ?", (uid,))
    service.sync_connection(user, store.connections(uid)[0])
    assert store.activities(uid, ind["id"]) == before
    assert store.account(uid, ind["id"])["activities_state"] == "error"


def test_merging_a_fresh_read_replaces_the_overlap_window():
    old = [{"id": "a", "trade_date": "2026-01-01"}, {"id": "b", "trade_date": "2026-03-01"},
           {"id": "c", "trade_date": "2026-03-05"}]
    # The broker reprocessed "c" under a new id; the window re-read returns it once.
    new = [{"id": "b", "trade_date": "2026-03-01"}, {"id": "c2", "trade_date": "2026-03-05"},
           {"id": "d", "trade_date": "2026-03-09"}]
    got = service.merge_activities(old, new, "2026-02-20")
    assert [a["id"] for a in got] == ["a", "b", "c2", "d"]
    assert [a["id"] for a in service.merge_activities([], new, None)] == ["b", "c2", "d"]


def test_snapshots_keep_one_a_day_beyond_the_last_thirty():
    c, user = _linked()
    uid = user["id"]
    db.execute("DELETE FROM brokerage_snapshots WHERE user_id = ?", (uid,))
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for day in range(40):
        for hour in (10, 15, 20):                        # three syncs a day
            t = (start + timedelta(days=day, hours=hour)).strftime("%Y-%m-%dT%H:%M:%SZ")
            store.add_snapshot(uid, {"taken_at": t, "positions": {}, "accounts": []})
    days = store.daily_snapshots(uid)
    assert len(days) == 40 and [d["taken_at"][11:13] for d in days].count("20") == 40
    kept = db.row("SELECT COUNT(*) AS n FROM brokerage_snapshots WHERE user_id = ?", (uid,))["n"]
    assert kept == 40 + 20                              # the newest 30 cover 10 days, 3 a day
    store.prune_snapshots(uid, now="2027-06-01T00:00:00Z")   # 400+ days on, only the newest 30 stay
    assert db.row("SELECT COUNT(*) AS n FROM brokerage_snapshots WHERE user_id = ?", (uid,))["n"] == 30


def test_snapshots_carry_every_account_and_a_disconnect_cuts_it_out():
    c, user = reader()
    paid(user)
    link(c, "standard")
    link(c, "edge")
    uid = user["id"]
    edge = next(x for x in store.connections(uid) if "edge" in x["provider_connection_id"])
    edge_ids = {a["id"] for a in store.accounts(uid, edge["id"])}
    snap = store.recent_snapshots(uid, 1)[0]
    assert edge_ids <= set(snap["by_account"])
    tesla = [k for k in snap["positions"] if "TSLA" in k]
    assert tesla                                         # the edge margin account's short is in it
    c.post("/api/brokerage/connections/{}/disconnect".format(edge["id"]))
    for s in store.daily_snapshots(uid) + store.recent_snapshots(uid, 30):
        assert not edge_ids & set(s.get("by_account") or {})
        assert not edge_ids & set(s.get("accounts") or [])
        assert not [k for k in s.get("positions") or {} if "TSLA" in k or "SHOP" in k]


def test_a_snapshot_from_before_per_account_detail_is_deleted_not_kept_on_disconnect():
    c, user = _linked()
    uid = user["id"]
    conn = store.connections(uid)[0]
    ids = [a["id"] for a in store.accounts(uid, conn["id"])]
    store.add_snapshot(uid, {"taken_at": "2026-01-01T00:00:00Z", "accounts": ids, "positions": {"x": {}}})
    assert portfolio.drop_accounts({"accounts": ids, "positions": {}}, ids) is None
    n = store.scrub_snapshots(uid, ids, portfolio.drop_accounts)
    assert n >= 1
    for s in store.recent_snapshots(uid, 30):
        assert not set(ids) & set(s.get("accounts") or [])


def test_drop_accounts_rebuilds_the_portfolio_figures_from_what_remains():
    snap = {"taken_at": "t", "accounts": ["a", "b"],
            "by_account": {
                "a": {"total": {"USD": 1000.0}, "positions": {"equity:AAPL:USD": {
                    "symbol": "AAPL", "kind": "equity", "currency": "USD", "qty": 2.0, "value": 400.0}}},
                "b": {"total": {"USD": 500.0}, "positions": {"equity:AAPL:USD": {
                    "symbol": "AAPL", "kind": "equity", "currency": "USD", "qty": 1.0, "value": 200.0}}},
                "c": {"total": {"USD": 99.0}, "positions": {}}}}
    out = portfolio.drop_accounts(snap, {"b"})
    assert out["accounts"] == ["a"] and set(out["by_account"]) == {"a", "c"}
    assert out["positions"]["equity:AAPL:USD"]["qty"] == 2.0 and out["by_currency"] == {"USD": 1000.0}
    assert out["combined_usd"] == 1000.0
    assert out["positions"]["equity:AAPL:USD"]["price"] == 200.0


def test_the_same_broker_account_through_a_second_connection_keeps_its_row():
    c, user = _linked()
    uid = user["id"]
    conn = store.connections(uid)[0]
    first = store.upsert_account(uid, conn["id"], "sandbox", "prov-1", "Individual", "..04", "Sandbox",
                                 "Individual", "USD", institution_account_id="INST-77")
    store.set_account_nickname(uid, first["id"], "Investing")
    again = store.upsert_account(uid, conn["id"], "sandbox", "prov-2", "Individual", "..04", "Sandbox",
                                 "Individual", "USD", institution_account_id="INST-77")
    assert again["id"] == first["id"] and again["provider_account_id"] == "prov-2"
    assert store.account(uid, first["id"])["name"] == "Investing"
    assert db.row("SELECT COUNT(*) AS n FROM brokerage_accounts WHERE institution_account_id = 'INST-77'")["n"] == 1


def test_a_money_market_fund_the_cash_balance_includes_is_counted_once():
    payload = {"positions": [
        {"symbol": "SPAXX", "kind": "fund", "quantity": 500.0, "price": 1.0, "avg_cost": 1.0,
         "currency": "USD", "cash_equivalent": True},
        {"symbol": "AAPL", "kind": "equity", "quantity": 1.0, "price": 200.0, "avg_cost": 150.0, "currency": "USD"}],
        "options": [], "cash": [{"currency": "USD", "amount": 500.0}], "problems": [], "total_value": 700.0}
    acct = {"id": "a", "name": "Brokerage", "currency": "USD", "selected": True, "payload": payload,
            "sync_state": "ok", "last_sync_at": "2026-10-15T00:00:00Z", "broker_as_of": None}
    built = portfolio.build([acct])
    assert built["totals"]["by_currency"]["USD"]["total"] == 700.0
    assert [h["symbol"] for h in built["holdings"]] == ["AAPL"]
    assert built["cash_equivalents"][0]["symbol"] == "SPAXX"
    assert any("counted once, inside cash" in n for n in built["notes"])
    # With the balances missing there is no cash figure to hold it: it counts as a holding.
    built = portfolio.build([dict(acct, payload=dict(payload, cash=[], problems=["balances"]))])
    assert {h["symbol"] for h in built["holdings"]} == {"AAPL", "SPAXX"}
    assert portfolio.account_detail(acct)["total"] == {"USD": 700.0}


def test_the_base_provider_offers_no_history_and_says_so():
    from app.brokerage.providers import Provider
    import pytest
    with pytest.raises(FeatureUnavailable):
        Provider().activities("u", "s", "a")
    with pytest.raises(FeatureUnavailable):
        Provider().balance_history("u", "s", "a")
    assert isinstance(SandboxProvider().activities.__self__, SandboxProvider)
    assert Activity(id="x", type="BUY", trade_date="2026-01-01").amount is None
