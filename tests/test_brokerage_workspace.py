"""The Brokerage workspace's lead-owned pieces (2026-10-15): the personal
calendar, alerts, the Desk read for one portfolio, the measured briefing, the
workspace routes' access rules, position theses and Milo's portfolio tool.

The analytics modules built alongside (performance, exposure, scorecard,
options risk) have their own test files; here they are only reached
through the routes.
"""

from __future__ import annotations

import json
import types
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app import db
from app.brokerage import alerts, briefing, desk_section, events, service, store, workspace

from tests.test_brokerage import link, paid, reader, sandbox  # noqa: F401  (autouse fixture)

TODAY = date(2026, 10, 15)
H = [  # an overview's holdings, as portfolio.build returns them
    {"symbol": "NVDA", "kind": "equity", "weight_pct": 30.0, "value_usd": 3000.0, "quantity": 20,
     "accounts": ["Individual"], "sector": "Technology", "currency": "USD"},
    {"symbol": "JNJ", "kind": "equity", "weight_pct": 20.0, "value_usd": 2000.0, "quantity": 12,
     "accounts": ["Roth IRA"], "sector": "Healthcare", "currency": "USD"},
    {"symbol": "QQQ", "kind": "etf", "weight_pct": 50.0, "value_usd": 5000.0, "quantity": 10,
     "accounts": ["Roth IRA"], "currency": "USD"},
]


# ------------------------------------------------------------------- calendar


def test_the_calendar_marks_estimates_skips_funds_and_reads_expiries_exactly():
    cal = {"NVDA": {"dates": ["2026-10-20"], "confirmed": True, "timing": "after_close", "usual_timing": {"timing": "after_close", "count": 4}},
           "JNJ": {"dates": ["2026-10-27", "2026-10-31"], "confirmed": False}}
    div = {"JNJ": {"ex_date": "2026-10-21", "last_amount": 1.3}, "QQQ": {"ex_date": "2026-09-22", "last_amount": 0.6}}
    asked = []
    out = events.build(H, [{"underlying": "NVDA", "strike": 150, "option_type": "call", "expiry": "2026-10-16",
                            "contracts": 1, "account": "Individual"}], TODAY,
                       earnings_of=lambda s: asked.append(s) or cal.get(s), dividend_of=lambda s: div.get(s))
    kinds = [(e["kind"], e["symbol"]) for e in out["events"]]
    assert kinds == [("option_expiry", "NVDA"), ("earnings", "NVDA"), ("ex_dividend", "JNJ"), ("earnings", "JNJ")]
    assert "QQQ" not in asked                                  # a fund has no earnings date of its own
    nv = out["events"][1]
    # the feed's time on an upcoming report is a placeholder (2026-10-21), so the event carries none of its own;
    # the company's habit from its past reports travels separately
    assert nv["confirmed"] is True and nv["timing"] is None and nv["usual_timing"] == {"timing": "after_close", "count": 4} and nv["days_away"] == 5
    jnj = out["events"][3]
    assert jnj["confirmed"] is False and jnj["range_end"] == "2026-10-31" and jnj["timing"] is None
    assert "not confirmed" in jnj["note"]
    assert not [e for e in out["events"] if e["symbol"] == "QQQ"]   # its ex-date has passed
    assert out["summary"]["earnings_next_14d_pct"] == 50.0       # NVDA 30 + JNJ 20 (12 days)
    assert out["summary"]["earnings_confirmed_next_14d_pct"] == 30.0
    assert out["summary"]["options_expiring_7d"] == 1


def test_the_calendar_spends_its_lookups_on_the_largest_holdings_and_says_so():
    many = [{"symbol": "S{}".format(i), "kind": "equity", "weight_pct": float(i)} for i in range(30)]
    asked = []
    out = events.build(many, [], TODAY, earnings_of=lambda s: asked.append(s) or None, max_lookups=5)
    assert asked == ["S29", "S28", "S27", "S26", "S25"]
    assert any("5 largest holdings" in l for l in out["limitations"])


# --------------------------------------------------------------------- alerts


def test_alert_settings_take_only_the_listed_choices():
    with pytest.raises(ValueError):
        alerts.validate({"earnings": {"days": 9}})
    with pytest.raises(ValueError):
        alerts.validate({"nonsense": True})
    ok = alerts.validate({"earnings": {"days": 14}, "email": True})
    assert ok["earnings"]["days"] == 14 and ok["email"] is True


def _overview(weights):
    return {"holdings": [{"symbol": s, "weight_pct": w} for s, w in weights.items()],
            "allocation": {"by_sector": [{"label": "Technology", "share_pct": 61.0}]}}


def test_alerts_fire_on_thresholds_and_compare_with_a_baseline_snapshot():
    prefs = alerts.validate({})
    ev = {"events": [{"kind": "earnings", "symbol": "NVDA", "date": "2026-10-20", "days_away": 5,
                      "confirmed": False, "weight_pct": 30.0},
                     {"kind": "earnings", "symbol": "JNJ", "date": "2026-10-30", "days_away": 15, "weight_pct": 20}]}
    base = {"taken_at": "2026-09-14T20:00:00Z",
            "positions": {"a": {"symbol": "NVDA", "kind": "equity", "value": 2000.0},
                          "b": {"symbol": "JNJ", "kind": "equity", "value": 8000.0}}}
    got = alerts.evaluate(_overview({"NVDA": 30.0, "JNJ": 70.0}), ev, [base], [], {}, lambda s: None, prefs, TODAY)
    kinds = sorted(a["kind"] for a in got)
    assert kinds == ["concentration", "concentration", "concentration", "drift", "drift", "earnings"]
    earn = next(a for a in got if a["kind"] == "earnings")
    assert "estimated" in earn["title"] and "NVDA" in earn["title"]
    drift = {a["title"] for a in got if a["kind"] == "drift"}
    assert drift == {"NVDA weight up 10.0 points", "JNJ weight down 10.0 points"}
    # A baseline under a week old is no baseline.
    young = dict(base, taken_at="2026-10-12T20:00:00Z")
    got = alerts.evaluate(_overview({"NVDA": 30.0}), {}, [young], [], {}, None, prefs, TODAY)
    assert not [a for a in got if a["kind"] == "drift"]


def test_a_fund_is_not_a_single_holding_concentration():
    prefs = alerts.validate({})
    ov = {"holdings": [{"symbol": "VOO", "kind": "etf", "weight_pct": 60.0},
                       {"symbol": "NVDA", "kind": "equity", "weight_pct": 40.0}], "allocation": {}}
    got = alerts.evaluate(ov, {}, [], [], {}, None, prefs, TODAY)
    assert [a["title"] for a in got if a["kind"] == "concentration"] == ["NVDA is 40.0% of your portfolio"]


def test_alerts_are_sealed_deduplicated_and_marked_seen():
    c, user = reader()
    paid(user)
    link(c)
    uid = user["id"]
    cands = [{"kind": "earnings", "dedupe_key": alerts._key("earnings", "NVDA", "2026-10-20"),
              "title": "NVDA reports in 5 days", "body": "30% of your portfolio.", "symbol": "NVDA"}]
    assert alerts.record(uid, cands) == 1
    assert alerts.record(uid, cands) == 0                       # same situation, not raised again
    raw = db.row("SELECT * FROM portfolio_alerts WHERE user_id = ?", (uid,))
    assert b"NVDA" not in raw["payload"] and "NVDA" not in raw["dedupe_key"]
    listed = alerts.listing(uid)
    assert listed["unseen"] == 1 and listed["alerts"][0]["title"] == "NVDA reports in 5 days"
    alerts.mark_seen(uid)
    assert alerts.listing(uid)["unseen"] == 0
    # Deleting brokerage data deletes them.
    service.delete_all(user)
    assert not db.row("SELECT 1 FROM portfolio_alerts WHERE user_id = ?", (uid,))


def test_alert_email_is_opt_in_and_carries_only_a_count():
    c, user = reader()
    paid(user)
    link(c)
    uid = user["id"]
    alerts.record(uid, [{"kind": "earnings", "dedupe_key": "k1", "title": "NVDA reports today", "body": "x"}])
    sent = []
    assert alerts.email_pending(user, lambda *a: sent.append(a) or True, "/x") is False and not sent
    alerts.save_settings(uid, {"email": True})
    assert alerts.email_pending(user, lambda *a: sent.append(a) or True, "/x") is True
    to, subject, body, _ = sent[0]
    assert "1 new portfolio alert" in subject and "NVDA" not in subject + body
    assert alerts.email_pending(user, lambda *a: sent.append(a) or True, "/x") is False   # emailed once


# ----------------------------------------------------------------------- desk


def test_the_desk_read_matches_the_editions_own_evidence_to_holdings():
    with open("docs/desk/samples/2026-10-13-close.json") as fh:
        ed = json.load(fh)
    served = {"available": True, "edition": ed, "is_today": False}
    named = lambda text: ["JNJ"] if "Johnson" in text else []      # noqa: E731
    ed["evidence"].append({"id": "N900", "kind": "news", "label": "Johnson & Johnson raises guidance",
                           "source": "Wire", "published_at": "2026-10-13T12:00:00Z"})
    out = desk_section.build(served, H, named_in=named, today=date(2026, 10, 13))
    whys = {i["evidence_id"]: i["why"] for i in out["items"]}
    assert "You hold QQQ" in whys["I2"]                         # the index fund held directly
    assert "XLV is the Healthcare sector fund" in whys["S3"]    # JNJ is Healthcare
    assert "Names JNJ" in whys["N900"]
    assert all("JPM" not in (i["label"] or "") for i in out["items"])   # not held: not here
    assert [m["evidence_id"] for m in out["market_wide"]][:2] == ["E1", "E3"]
    assert out["edition"]["date"] == "2026-10-13" and out["link"] == "#/read"
    assert desk_section.build({"available": False, "reason": "No edition yet."}, H)["available"] is False


# ------------------------------------------------------------------- briefing


def test_todays_contributions_are_quantity_times_the_price_change():
    q = {"NVDA": {"price": 110.0, "prev_close": 100.0, "as_of": "2026-10-15T19:00:00Z"},
         "JNJ": {"price": 150.0, "prev_close": 160.0, "as_of": "2026-10-15T19:01:00Z"}}
    m = briefing.today_moves(H, q)
    rows = {r["symbol"]: r for r in m["rows"]}
    assert rows["NVDA"]["contribution"] == 200.0 and rows["JNJ"]["contribution"] == -120.0
    assert m["total"] == 80.0 and m["total_pct"] == round(100 * 80 / (20 * 100 + 12 * 160), 2)
    assert m["not_priced"] == ["QQQ"] and m["quotes_newest"] == "2026-10-15T19:01:00Z"


def test_headlines_are_candidates_by_timing_and_a_big_quiet_move_says_so():
    now = datetime(2026, 10, 15, 20, tzinfo=timezone.utc)
    rows = [{"symbol": "NVDA", "change_pct": 10.0, "contribution": 200.0},
            {"symbol": "JNJ", "change_pct": -6.25, "contribution": -120.0}]
    news = {"NVDA": [{"title": "Old", "published": "2026-10-10T10:00:00Z"},
                     {"title": "Chip rally", "published": "2026-10-15T14:00:00Z"}], "JNJ": []}
    got = briefing.headlines_for(rows, lambda s: news[s], now)
    assert got[0]["status"] == "possibly_related" and [h["title"] for h in got[0]["headlines"]] == ["Chip rally"]
    assert "timing only" in got[0]["note"]
    assert got[1]["status"] == "no_headline" and "no headline" in got[1]["note"]


# ------------------------------------------------------------------ the routes


@pytest.fixture
def market(monkeypatch):
    """The workspace's market lookups, answered from a table: no network."""
    monkeypatch.setattr(workspace, "MARKET", {
        "sector_of": lambda s: {"AAPL": "Technology", "MSFT": "Technology", "NVDA": "Technology"}.get(s),
        "earnings_calendar_of": lambda s: {"dates": [(date.today() + timedelta(days=4)).isoformat()],
                                           "confirmed": True} if s == "AAPL" else None,
        "dividend_of": lambda s: None,
        "quotes_of": lambda syms: {s: {"price": 100.0, "prev_close": 99.0, "as_of": "2026-10-15T19:00:00Z",
                                       "source": "test"} for s in syms},
        "news_of": lambda s: [],
        "desk_served": lambda: {"available": False, "reason": "No edition yet."},
        "named_in": lambda text: [],
        "catalysts_of": lambda s: [],
    })
    workspace._cache.clear()


def test_every_workspace_route_needs_a_reader_with_a_link(market):
    guest = TestClient(main.app)
    assert guest.get("/api/brokerage/workspace/overview").status_code == 401
    c, user = reader()
    assert c.get("/api/brokerage/workspace/overview").status_code == 409
    paid(user)
    link(c)
    r = c.get("/api/brokerage/workspace/overview")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["section"] == "overview" and body["totals"]["by_currency"]["USD"]["total"] > 0
    assert body["upcoming"][0]["symbol"] == "AAPL" and body["today"]["available"] is True
    assert body["freshness"]["market"]["quotes_newest"] == "2026-10-15T19:00:00Z"
    assert body["freshness"]["broker"]["newest_sync"]


def test_owner_only_mode_hides_the_workspace_from_everyone_else(market, monkeypatch):
    c, user = reader("them@example.com")
    paid(user)
    link(c)
    monkeypatch.setenv("BROKERAGE_OWNER_ONLY", "true")
    monkeypatch.setenv("ADMIN_EMAILS", "owner@example.com")
    r = c.get("/api/brokerage/workspace/overview")
    assert r.status_code == 404 and r.json()["detail"] == service.NOT_SWITCHED_ON


def test_a_scope_reaches_only_the_readers_own_accounts(market):
    a, ua = reader("a@example.com")
    paid(ua)
    link(a)
    b, ub = reader("b@example.com")
    paid(ub)
    link(b, "edge")
    theirs = [x["id"] for x in store.accounts(ub["id"])]
    mine = [x["id"] for x in store.accounts(ua["id"])]
    # Another reader's ids are ignored, and the default scope answers instead.
    r = a.get("/api/brokerage/workspace/overview", params={"accounts": ",".join(theirs)}).json()
    assert set(r["scope"]["scope"]) == set(mine)
    one = next(x for x in store.accounts(ua["id"]) if x["name"] == "Roth IRA")
    r = a.get("/api/brokerage/workspace/overview", params={"accounts": one["id"]}).json()
    assert r["scope"]["scope"] == [one["id"]]
    assert {h["symbol"] for h in r["top_holdings"]} == {"VOO", "SCHD", "AAPL"}


def test_alert_routes_refresh_list_and_save_settings(market):
    c, user = reader()
    paid(user)
    link(c)
    r = c.post("/api/brokerage/workspace/alerts/refresh")
    assert r.status_code == 200, r.text
    titles = [a["title"] for a in r.json()["alerts"]]
    assert any(t.startswith("AAPL reports") for t in titles)
    assert c.put("/api/brokerage/workspace/alerts/settings", json={"earnings": {"days": 5}}).status_code == 400
    ok = c.put("/api/brokerage/workspace/alerts/settings", json={"earnings": {"days": 14}}).json()
    assert ok["settings"]["earnings"]["days"] == 14
    assert c.post("/api/brokerage/workspace/alerts/seen", json={}).json()["ok"] is True


def test_the_written_briefing_is_metered_and_cached_per_facts(market, monkeypatch):
    c, user = reader()
    paid(user)
    link(c)
    calls, guarded = [], []
    monkeypatch.setitem(main.brokerage_ws_routes.HOOKS, "spend_guard", lambda request: guarded.append(1))
    monkeypatch.setitem(main.brokerage_ws_routes.HOOKS, "write_brief",
                        lambda facts: calls.append(facts) or {"available": True, "headline": "A quiet day.",
                                                              "what_changed": "x", "drivers": "", "ahead": "",
                                                              "attention": ""})
    first = c.post("/api/brokerage/workspace/briefing/written", json={}).json()
    assert first["cached"] is False and first["written"]["headline"] == "A quiet day."
    again = c.post("/api/brokerage/workspace/briefing/written", json={}).json()
    assert again["cached"] is True and len(calls) == 1 and len(guarded) == 1
    assert set(calls[0]) == {"today", "since_sync", "drivers", "upcoming", "observations", "limitations"}
    raw = db.row("SELECT payload FROM portfolio_briefings WHERE user_id = ?", (user["id"],))
    assert b"quiet day" not in raw["payload"]                  # sealed
    got = c.get("/api/brokerage/workspace/briefing").json()
    assert got["written"]["headline"] == "A quiet day."


# -------------------------------------------------------------------- theses


def test_a_position_thesis_keeps_horizon_and_assumptions_through_a_dossier_save():
    c, user = reader()
    r = c.put("/api/theses/NVDA", json={"bull": "Data-centre demand", "invalidation": "Two quarters of falling "
              "data-centre revenue", "horizon": "3-5 years", "assumptions": "Hyperscaler capex keeps rising"})
    assert r.status_code == 200 and r.json()["thesis"]["horizon"] == "3-5 years"
    # The Dossier's form sends only its four fields.
    c.put("/api/theses/NVDA", json={"bull": "Data-centre demand, and software", "bear": "", "catalysts": "",
                                    "invalidation": "Two quarters of falling data-centre revenue"})
    t = c.get("/api/theses").json()["theses"]["NVDA"]
    assert t["horizon"] == "3-5 years" and t["assumptions"] == "Hyperscaler capex keeps rising"
    assert t["bull"] == "Data-centre demand, and software"


def test_a_workspace_thesis_save_keeps_the_dossiers_snapshot():
    # The Dossier's form saves a snapshot (the "what changed" baseline and the
    # thesis check's conditions); the workspace's form sends prose only, in
    # both apps, and used to wipe it.
    c, user = reader()
    snap = {"stance": "constructive", "price": 120.5, "check": {"conditions": ["close below 100"]}}
    c.put("/api/theses/NVDA", json={"bull": "Data-centre demand", "invalidation": "Close below 100", "snapshot": snap})
    c.put("/api/theses/NVDA", json={"bull": "Data-centre demand", "invalidation": "Close below 100",
                                    "horizon": "3-5 years"})
    t = c.get("/api/theses").json()["theses"]["NVDA"]
    assert t["snapshot"] == snap and t["horizon"] == "3-5 years"
    # a save that sends a snapshot still replaces it
    c.put("/api/theses/NVDA", json={"bull": "Data-centre demand", "snapshot": {"stance": "cautious"}})
    assert c.get("/api/theses").json()["theses"]["NVDA"]["snapshot"] == {"stance": "cautious"}


# ------------------------------------------------------------------- Milo


def test_milos_portfolio_tool_reads_only_the_asking_reader(market, monkeypatch):
    from app import milo_tools
    a, ua = reader("a@example.com")
    paid(ua)
    link(a)
    b, ub = reader("b@example.com")
    paid(ub)
    link(b, "edge")

    def run(coro):
        import asyncio
        return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)

    for who, expect, absent in ((ua, "VOO", "TSLA"), (ub, "TSLA", "VOO")):
        monkeypatch.setattr(main.auth_deps, "current_user", lambda request, who=who: who)
        box = main._milo_toolbox(types.SimpleNamespace(), {"focus": {"scope": "auto"}})
        body = run(box.run("get_my_portfolio", {"part": "summary"}))[0]
        assert expect in body and absent not in body
    # A scope naming the other reader's accounts reads nothing of theirs.
    theirs = [x["id"] for x in store.accounts(ub["id"])]
    monkeypatch.setattr(main.auth_deps, "current_user", lambda request: ua)
    box = main._milo_toolbox(types.SimpleNamespace(), {"focus": {"scope": "auto"}, "brokerage_scope": theirs})
    body = run(box.run("get_my_portfolio", {"part": "summary"}))[0]
    assert "VOO" in body and "TSLA" not in body
    # Not signed in: no portfolio, and said plainly.
    monkeypatch.setattr(main.auth_deps, "current_user", lambda request: None)
    body = json.loads(run(main._milo_toolbox(types.SimpleNamespace(), {}).run("get_my_portfolio",
                                                                             {"part": "summary"}))[0])
    assert body["signed_in"] is False and "data" not in body
    with pytest.raises(milo_tools.InvalidInput):
        milo_tools.validate("get_my_portfolio", {"part": "everything"})


# ------------------------------------------------ hard cases, through the routes

SECTIONS = ("overview", "holdings", "scorecard", "options", "performance", "events", "briefing")


@pytest.mark.parametrize("scenario", ["edge", "partial", "outage", "expired"])
def test_every_section_answers_for_awkward_accounts(market, scenario):
    """CAD and a mini option and crypto and an unvalued private placement
    (edge), a sync that lost its balances (partial), a provider that stops
    answering after the first sync (outage), an authorisation that expires
    (expired): every section still answers from what was stored, and says
    what is missing rather than showing a smaller portfolio as if whole."""
    c, user = reader()
    paid(user)
    link(c, scenario)
    if scenario in ("outage", "expired"):
        service.sync_connection(user, store.connections(user["id"])[0])   # the second sync fails
    for sec in SECTIONS:
        r = c.get("/api/brokerage/workspace/{}".format(sec))
        assert r.status_code == 200, (scenario, sec, r.text[:300])
    hold = c.get("/api/brokerage/workspace/holdings").json()
    over = c.get("/api/brokerage/workspace/overview").json()
    if scenario == "edge":
        assert [u for u in hold["unsupported"] if "Private placement" in (u.get("description") or "")]
        assert any("could not be valued" in n for n in hold["notes"])
        assert "CAD" in over["totals"]["by_currency"]
        perf = c.get("/api/brokerage/workspace/performance").json()
        assert any(s["balance_history"] == "unavailable" for s in perf["data_status"])
    if scenario == "partial":
        assert any("did not return" in n for n in hold["notes"])
        assert any(o["kind"] == "data" for o in over["observations"])
    if scenario in ("outage", "expired"):
        st = c.get("/api/brokerage/status").json()["connections"][0]["status"]
        assert st == ("outage" if scenario == "outage" else "expired")
        assert hold["holdings"], "the last good data is still shown"


def test_options_risk_without_a_quote_says_so_rather_than_inventing_greeks(market):
    c, user = reader()
    paid(user)
    link(c)
    o = c.get("/api/brokerage/workspace/options").json()
    assert o["available"] is True
    for p in o["positions"]:
        assert p["greeks_available"] is False and p["greeks_reason"]
        assert p["delta_shares"] is None



def test_milo_gets_each_stocks_industry_and_the_rule_about_sector_names(monkeypatch):
    """Milo told the owner "no energy" in the answer that listed Bloom Energy,
    which Yahoo files under Industrials (2026-10-16). It now sees the industry
    beside the sector and is told how to say it."""
    from app import ai
    from app.brokerage import routes as broute
    c, user = reader()
    paid(user)
    link(c)
    lk = dict(broute.LOOKUPS, industry_of=lambda s: {"AAPL": "Consumer Electronics"}.get(s))
    block = service.milo_context(user, **lk)
    aapl = next(w for w in block["calculated"]["weights"] if w["symbol"] == "AAPL")
    assert aapl["industry"] == "Consumer Electronics" and aapl["sector"] == "Technology"
    assert "Energy means oil, gas and coal" in block["calculated"]["classification"]
    assert "Bloom Energy is filed under Industrials" in ai.FORMAT_PROMPT
    assert "check every holding's name and industry" in ai.FORMAT_PROMPT


def test_value_now_reprices_holdings_at_quotes_and_keeps_cash_options_and_bar_closes():
    """The owner asked for the portfolio to update in real time (2026-10-16): the tile showed the previous
    evening's broker total through a -2.5% session."""
    held = [{"symbol": "AAA", "kind": "equity", "quantity": 10, "value_usd": 1000.0, "currency": "USD"},
            {"symbol": "BBB", "kind": "etf", "quantity": 5, "value_usd": 500.0, "currency": "USD"},
            {"symbol": "CCC", "kind": "equity", "quantity": 2, "value_usd": 200.0, "currency": "USD"}]
    quotes = {"AAA": {"price": 95.0, "price_time": "2026-10-16T16:29:00Z"},
              "BBB": {"price": 102.0, "as_of": "2026-10-16T16:28:00Z"},
              "CCC": {"price": 90.0, "price_source": "daily_bar"}}
    totals = {"combined_usd": {"value": 1900.0}}      # 1,700 of holdings, plus cash and options
    v = workspace.value_now(held, quotes, totals)
    # AAA 1,000 -> 950, BBB 500 -> 510; CCC's bar close is not "now", so it stays at 200.
    assert v["available"] and v["value"] == 1860.0 and v["change_from_broker"] == -40.0
    assert v["kept_at_broker"] == ["CCC"] and v["priced"] == ["AAA", "BBB"]
    assert v["quotes_newest"] == "2026-10-16T16:29:00Z" and v["broker_value"] == 1900.0
    assert workspace.value_now(held, {}, totals)["available"] is False
    assert workspace.value_now(held, quotes, {"by_currency": {}})["available"] is False


def test_the_overview_shows_value_now_and_refreshes_while_the_market_is_open():
    import os
    src = open(os.path.join(os.path.dirname(__file__), "..", "static", "brokerage.js"), encoding="utf-8").read()
    assert "k: 'Value now'" in src and "The broker's own total is" in src
    assert "if (sec === 'overview') bkwScheduleRefresh();" in src
    body = src[src.index("function bkwScheduleRefresh() {"):src.index("async function bkwLoadBriefing() {")]
    assert "isTapeLiveET()" in body and "document.hidden" in body and "bkwWantKey('overview') !== want" in body
    assert "addEventListener('visibilitychange'" in body


def test_the_status_chip_says_the_brokerage_overview_refreshes():
    import os
    src = open(os.path.join(os.path.dirname(__file__), "..", "static", "app.js"), encoding="utf-8").read()
    assert "(STATE.view === 'brokerage' && typeof bkwSection === 'function' && bkwSection() === 'overview' && isTapeLiveET())" in src

