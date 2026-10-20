"""Alerts fire on a change, not on a state (backlog task 3, 2026-10-20).

Each test drives the scheduled runner or the account routes with fake snapshots, so it asserts what
fires and when, never the source. The rule: every check records the condition's state, met or not;
a watch fires when its state changes into the met one. A crossing arms on its first look (or from
the price the reader saw when making it); an event (a session's move, a report, a filing) carries
its own identity, so each new one fires once.
"""
import json
import uuid
from datetime import datetime, timezone

import pytest

from app import db, watch_runner
from app.analytics import watches as watches_mod
from tests.test_account_data import client, post, signed_in  # noqa: F401  (the fixture)


@pytest.fixture()
def account(accounts):
    uid = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    db.execute("INSERT INTO users (id, email, created_at, updated_at) VALUES (?,?,?,?)", (uid, "a@example.com", now, now))
    return uid


@pytest.fixture(autouse=True)
def _fresh_client(accounts):
    client.cookies.clear()


def add(user, symbol, kind, params, ref_price=None, active=1):
    wid = uuid.uuid4().hex
    db.execute("INSERT INTO watches (id, user_id, symbol, kind, params, active, created_at, ref_price) VALUES (?,?,?,?,?,?,?,?)",
               (wid, user, symbol, kind, json.dumps(params, sort_keys=True), active, datetime.now(timezone.utc).isoformat(), ref_price))
    return wid


def at(monkeypatch, *moments):
    it = iter(moments)
    monkeypatch.setattr(watch_runner, "_now", lambda: next(it))


def day(d, h=15):
    return datetime(2026, 10, d, h, 0, tzinfo=timezone.utc)   # October 2026: no exchange holidays on these days


def price(p, when="2026-10-06T15:45:00-04:00"):
    return lambda sym: {"quote": {"price": p, "change_pct": 0.5, "market_time": when}}


def test_a_price_alert_made_below_its_level_fires_at_the_first_check_above(account, monkeypatch):
    # made at 342.94 with the level at 350: the first check already sees 351, a crossing
    add(account, "AAPL", "price_above", {"level": 350}, ref_price=342.94)
    at(monkeypatch, day(6), day(6, 16), day(7))
    assert [watch_runner.run_once(price(p))["hits"] for p in (351.2, 352.0, 353.0)] == [1, 0, 0]
    hit = watch_runner.hits_for(account)[0]
    seen = hit["observed"]
    assert seen["price"] == 351.2 and seen["level"] == 350 and seen["ref_price"] == 342.94
    assert seen["from"] == "not above" and seen["to"] == "above" and seen["quote_time"].startswith("2026-10-06")
    assert hit["origin"] == "schedule" and hit["condition"] == "AAPL price rises above 350"


def test_a_level_already_crossed_when_made_waits_for_the_next_crossing(account, monkeypatch):
    add(account, "AAPL", "price_above", {"level": 300}, ref_price=342.94)
    at(monkeypatch, day(6), day(7), day(8), day(9))
    # still above, still above, dips under, back above: one hit, at the second crossing
    assert [watch_runner.run_once(price(p))["hits"] for p in (343, 344, 299, 305)] == [0, 0, 0, 1]


def test_without_a_reference_price_the_first_check_only_arms(account, monkeypatch):
    add(account, "AAPL", "price_below", {"level": 300})
    at(monkeypatch, day(6), day(7), day(8))
    assert [watch_runner.run_once(price(p))["hits"] for p in (290, 285, 280)] == [0, 0, 0]
    w = db.row("SELECT last_state, last_checked_at FROM watches")
    assert w["last_state"] == "below" and w["last_checked_at"]


def test_a_filtered_stance_fires_each_time_it_returns(account, monkeypatch):
    # signal_flip "to bearish" over bearish, neutral, bearish, neutral, bearish fired 1,0,0,0,0 before
    add(account, "AAA", "signal_flip", {"to": "bearish"})
    at(monkeypatch, *[day(d) for d in (5, 6, 7, 8, 9)])
    seq = ["bearish", "neutral", "bearish", "neutral", "bearish"]
    got = [watch_runner.run_once(lambda s, st=st: {"verdict": {"stance": st}})["hits"] for st in seq]
    assert got == [0, 0, 1, 0, 1]


def test_macd_fires_on_the_turn_not_every_day_it_holds(account, monkeypatch):
    add(account, "AAA", "macd_cross", {"to": "any"})
    at(monkeypatch, *[day(d) for d in (5, 6, 7, 8)])
    snap = lambda st: (lambda s: {"technicals": {"macd": {"state": st, "macd": 1.0, "signal": 0.5}}})
    assert [watch_runner.run_once(snap(st))["hits"] for st in ("bullish", "bullish", "bearish", "bearish")] == [0, 0, 1, 0]


def test_an_insider_alert_fires_for_a_new_filing_not_an_old_one(account, monkeypatch):
    add(account, "AAA", "insider_activity", {"side": "any"})
    at(monkeypatch, *[day(d) for d in (5, 6, 7, 8)])
    jan = {"date": "2026-01-15", "insider": "COOK TIMOTHY", "shares": 1000, "action": "sale"}
    oct_ = {"date": "2026-10-06", "insider": "PAREKH KEVAN", "shares": 500, "action": "sale"}
    snap = lambda rows: (lambda s: {"company": {"ownership": {"recent_transactions": rows}}})
    assert [watch_runner.run_once(snap(r))["hits"] for r in ([jan], [jan], [oct_, jan], [oct_, jan])] == [0, 0, 1, 0]


def test_a_short_interest_report_fires_once(account, monkeypatch):
    add(account, "AAA", "short_interest", {"pct": 15})
    at(monkeypatch, *[day(d) for d in (5, 6, 7)])
    rep = lambda when, chg: (lambda s: {"company": {"short_interest": {"change_vs_prior_pct": chg, "settlement_date": when}}})
    assert [watch_runner.run_once(rep(w, c))["hits"] for w, c in (("2026-09-30", 22.0), ("2026-09-30", 22.0), ("2026-10-15", 30.0))] == [1, 0, 1]


def test_earnings_near_fires_once_per_report_on_the_runners_clock(account, monkeypatch):
    add(account, "AAA", "earnings_near", {"days": 7})
    at(monkeypatch, day(27), day(28), day(29))
    snap = lambda s: {"next_earnings_date": "2026-11-02"}
    # 27 Oct is six days out: fires; the next two days are the same report
    assert [watch_runner.run_once(snap)["hits"] for _ in range(3)] == [1, 0, 0]


def test_a_day_move_fires_once_a_session(account, monkeypatch):
    add(account, "AAA", "move_pct", {"pct": 4})
    at(monkeypatch, day(6), day(6, 17), day(7))
    s1 = lambda s: {"quote": {"price": 10, "change_pct": 5.2, "market_time": "2026-10-06T14:00:00-04:00"}}
    s2 = lambda s: {"quote": {"price": 10, "change_pct": -4.5, "market_time": "2026-10-07T14:00:00-04:00"}}
    assert [watch_runner.run_once(s)["hits"] for s in (s1, s1, s2)] == [1, 0, 1]


def test_no_pass_on_an_exchange_holiday(account, monkeypatch):
    add(account, "AAA", "move_pct", {"pct": 4})
    at(monkeypatch, datetime(2026, 11, 26, 15, 0, tzinfo=timezone.utc))   # Thanksgiving
    out = watch_runner.run_once(lambda s: {"quote": {"price": 10, "change_pct": 5.0}})
    assert out["skipped"] == "holiday" and out["hits"] == 0


def test_a_paused_alert_is_not_checked_and_resuming_rearms_it(signed_in):  # noqa: F811
    csrf = signed_in["csrf"]
    made = post("/api/watches", csrf, symbol="AAPL", kind="price_above", params={"level": 350}, ref_price=342.0).json()["watch"]
    assert made["armed"] and made["ref_price"] == 342.0
    paused = client.patch("/api/watches/{}".format(made["id"]), headers={"X-Optic-CSRF": csrf}, json={"active": False}).json()["watch"]
    assert not paused["active"] and paused["paused_at"]
    assert all(r["id"] != made["id"] for r in watch_runner.due_watches())
    resumed = client.patch("/api/watches/{}".format(made["id"]), headers={"X-Optic-CSRF": csrf}, json={"active": True, "ref_price": 355.0}).json()["watch"]
    # it starts again from the price on screen: already above 350, so no hit until it crosses again
    assert resumed["active"] and resumed["paused_at"] is None and resumed["last_state"] is None and resumed["ref_price"] == 355.0


def test_editing_the_level_rearms_and_a_clash_is_refused(signed_in):  # noqa: F811
    csrf = signed_in["csrf"]
    a = post("/api/watches", csrf, symbol="AAPL", kind="price_above", params={"level": 350}).json()["watch"]
    post("/api/watches", csrf, symbol="AAPL", kind="price_above", params={"level": 360})
    db.execute("UPDATE watches SET last_state = 'above' WHERE id = ?", (a["id"],))
    edited = client.patch("/api/watches/{}".format(a["id"]), headers={"X-Optic-CSRF": csrf}, json={"params": {"level": 355}, "ref_price": 343.0}).json()["watch"]
    assert edited["params"] == {"level": 355.0} and edited["last_state"] is None and edited["ref_price"] == 343.0
    clash = client.patch("/api/watches/{}".format(a["id"]), headers={"X-Optic-CSRF": csrf}, json={"params": {"level": 360}})
    assert clash.status_code == 409


@pytest.mark.parametrize("kind,params", [
    ("price_above", {"level": 0}), ("price_below", {"level": -5}), ("move_pct", {"pct": 0}),
    ("rsi_above", {"level": 100}), ("rsi_below", {"level": 0}), ("unusual_options", {"min_ratio": 0}),
    ("earnings_near", {"days": 0}), ("short_interest", {"pct": 150}),
])
def test_values_that_cannot_mean_anything_are_refused(signed_in, kind, params):  # noqa: F811
    reply = post("/api/watches", signed_in["csrf"], symbol="AAPL", kind=kind, params=params)
    assert reply.status_code == 400, reply.text


def test_a_deleted_alert_keeps_its_history_and_can_come_back(signed_in, monkeypatch):  # noqa: F811
    csrf = signed_in["csrf"]
    made = post("/api/watches", csrf, symbol="AAPL", kind="price_above", params={"level": 350}, ref_price=340.0).json()["watch"]
    watch_runner.run_once(price(351.0))
    assert len(client.get("/api/watches/hits").json()["hits"]) == 1
    assert client.delete("/api/watches/{}".format(made["id"]), headers={"X-Optic-CSRF": csrf}).json()["ok"]
    assert client.get("/api/watches").json()["watches"] == []
    hits = client.get("/api/watches/hits").json()["hits"]
    assert len(hits) == 1 and hits[0]["condition"] == "AAPL price rises above 350.0"   # still readable
    back = client.post("/api/watches/{}/restore".format(made["id"]), headers={"X-Optic-CSRF": csrf}).json()["watch"]
    assert back["id"] == made["id"] and back["active"]
    # deleted again and made again: the same row returns, with its history
    client.delete("/api/watches/{}".format(made["id"]), headers={"X-Optic-CSRF": csrf})
    again = post("/api/watches", csrf, symbol="AAPL", kind="price_above", params={"level": 350}).json()["watch"]
    assert again["id"] == made["id"]
    assert len(client.get("/api/watches/hits?watch={}".format(made["id"])).json()["hits"]) == 1


def test_the_page_and_the_schedule_never_store_one_crossing_twice(signed_in, monkeypatch):  # noqa: F811
    csrf = signed_in["csrf"]
    made = post("/api/watches", csrf, symbol="AAPL", kind="price_above", params={"level": 350}, ref_price=340.0).json()["watch"]
    page = client.post("/api/watches/seen", headers={"X-Optic-CSRF": csrf}, json={"results": [
        {"id": made["id"], "met": True, "state": "above", "evidence": "last 351.00, above 350.00", "label": "Price rises above",
         "observed": {"price": 351.0, "level": 350.0}}]}).json()
    assert page["fired"] == 1
    assert watch_runner.run_once(price(351.5))["hits"] == 0      # the schedule sees no change
    assert len(client.get("/api/watches/hits").json()["hits"]) == 1


def test_the_catalogue_says_how_often_with_what_delay_and_where_it_shows():
    cat = watches_mod.catalogue()
    assert cat["schedule"]["every_minutes"] == 30 and cat["schedule"]["delay_minutes"] == 15
    assert "does not send email or push" in cat["method"] and "crosses the level" in cat["method"]
    assert watches_mod.CONDITIONS["breakout"]["label"] == "Breaks past every mapped level"   # what it checks


def test_a_deleted_alert_does_not_block_an_edit_onto_its_values(signed_in):  # noqa: F811
    csrf = signed_in["csrf"]
    old = post("/api/watches", csrf, symbol="AAPL", kind="price_above", params={"level": 380}, ref_price=340.0).json()["watch"]
    watch_runner.run_once(price(381.0))                       # it fires once, so it has a history
    client.delete("/api/watches/{}".format(old["id"]), headers={"X-Optic-CSRF": csrf})
    new = post("/api/watches", csrf, symbol="AAPL", kind="price_above", params={"level": 390}).json()["watch"]
    moved = client.patch("/api/watches/{}".format(new["id"]), headers={"X-Optic-CSRF": csrf}, json={"params": {"level": 380}})
    assert moved.status_code == 200 and moved.json()["watch"]["params"] == {"level": 380.0}
    # the deleted one's history now belongs to the alert that holds its values
    assert len(client.get("/api/watches/hits?watch={}".format(new["id"])).json()["hits"]) == 1
