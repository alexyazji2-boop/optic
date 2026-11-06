"""Invalid-symbol handling (owner's Handoff 3, 2026-11-03; app/symbol_check.py, static/v2/js/core/symbolcheck.js,
pages/notfound.js).

On 2026-11-03 the authenticated audit opened `#/markets` and got a "MARKETS" Dossier: tabs, an empty chart, a Watch
button, and Milo told the page was "MARKETS Dossier, Overview". Any address shaped like a ticker was a company. These
tests hold the fix: a symbol is checked against the universe the search box uses before anything about it is drawn;
one that names nothing gets the not-found page at its own address, with the closest listings and a search box holding
what was typed; it cannot reach a watchlist, Compare or Milo's context; a check that cannot be made says so and is
never a not-found; and every miss is logged, sanitised, for finding bad links.

The handoff's acceptance tests, in order: test_acceptance_1_* (ten invalid symbols), test_acceptance_2_* (valid symbols
and their spellings), test_acceptance_3_* (watchlist, Compare, Milo), test_acceptance_4_* (logged).
"""
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app import symbol_check as SC
from app import universe
from app.auth import config, store
from tests.test_frontend_v2_stage0 import _run

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "static" / "v2" / "js"
NOW = datetime(2026, 11, 4, 18, 0, tzinfo=timezone.utc)

# A small exchange directory, as app/universe.py search_index keeps it (share classes dotted, as filed)
ROWS = [{"symbol": s, "name": n, "etf": e} for s, n, e in (
    ("AAPL", "Apple Inc", False), ("MSFT", "Microsoft Corporation", False), ("NVDA", "NVIDIA Corporation", False),
    ("BRK.B", "Berkshire Hathaway Inc. New", False), ("SPY", "SPDR S&P 500 ETF Trust", True),
    ("GLD", "SPDR Gold Shares", True), ("GOLD", "Barrick Mining Corporation", False),
    ("HOOD", "Robinhood Markets, Inc. Class A", False), ("TW", "Tradeweb Markets Inc. Class A", False),
    ("APP", "Applovin Corporation Class A", False), ("AAP", "Advance Auto Parts Inc", False))]
IDX = {"rows": ROWS, "fetched_on": "2026-11-04", "count": len(ROWS)}
QUOTES = {
    # Tencent's ADR: over the counter, so not in the directory, but quoted and traded this week
    "TCEHY": {"price": 62.4, "name": "Tencent Holdings Limited", "quote_type": "EQUITY", "trade_time": "2026-11-04T15:59:00+00:00"},
    # a symbol whose quote is a year old: it no longer trades
    "OLDCO": {"price": 3.1, "name": "Old Company", "quote_type": "EQUITY", "trade_time": "2025-10-27T20:00:00+00:00"},
}


def quote(sym):
    return dict(QUOTES.get(sym) or {})


@pytest.fixture
def directory(monkeypatch):
    """The directory loaded (as on a running server) and the stub quote source."""
    monkeypatch.setattr(universe, "_rows_today", lambda: IDX)
    monkeypatch.setattr(universe, "_MEMO", {"index": IDX})
    monkeypatch.setattr(universe, "_INSTRUMENTS", [{"symbol": "^GSPC", "name": "S&P 500", "kind": "index"},
                                                    {"symbol": "ES=F", "name": "S&P 500 futures", "kind": "future"}])
    monkeypatch.setattr(universe, "_prominence", lambda: {"AAPL": 9e10, "MSFT": 8e10, "APP": 2e9, "AAP": 1e8})
    monkeypatch.setattr(SC, "QUOTE", quote)
    SC.forget()
    yield
    SC.forget()


# ------------------------------------------------------------------------------------------------ the check
BAD = ["MARKETS", "ZZZZQX", "APPL", "AAPLL", "MSTF", "", "%", "AAPL!", "<script>", "BRK$B", "../etc", "MAR\nKETS"]


def test_acceptance_1_ten_invalid_symbols_are_refused(directory):
    """Gibberish, typos of AAPL, empty and special characters: twelve, every one refused, none a company."""
    got = {raw: SC.check(raw, now=NOW)["status"] for raw in BAD}
    assert all(st in SC.REFUSED for st in got.values()), got
    assert got["MARKETS"] == "unknown" and got["APPL"] == "unknown" and got[""] == "invalid" and got["%"] == "invalid"
    assert got["MAR\nKETS"] == "invalid", "a newline is not part of a symbol"
    # the closest listings: the typo's company first, and both a stock and a fund where both answer
    assert [s["symbol"] for s in SC.suggestions("APPL", "APPL")][:1] == ["AAPL"]
    assert [s["symbol"] for s in SC.suggestions("AAPLL", "AAPLL")][:1] == ["AAPL"]
    assert {s["symbol"] for s in SC.suggestions("MARKETS", "MARKETS")} >= {"HOOD", "TW"}, "companies named Markets"
    gold = SC.suggestions("SPDR GOLD", None)
    assert any(s["kind"] == "etf" for s in gold)
    assert SC.suggestions("%", None) == [], "nothing is close to a percent sign"
    assert [s["symbol"] for s in SC.suggestions("BRK$B", None)][:1] == ["BRK-B"]


def test_acceptance_2_valid_symbols_and_their_spellings_resolve(directory):
    for raw, want in (("aapl", "AAPL"), ("AAPL", "AAPL"), ("brk.b", "BRK-B"), ("BRK/B", "BRK-B"), ("brk b", "BRK-B"),
                      ("BRK-B", "BRK-B"), ("spy", "SPY")):
        r = SC.check(raw, now=NOW)
        assert (r["status"], r["symbol"]) == ("listed", want), raw
    assert SC.check("spy", now=NOW)["kind"] == "etf" and SC.check("aapl", now=NOW)["kind"] == "stock"
    assert SC.check("^GSPC", now=NOW)["status"] == "instrument"
    t = SC.check("tcehy", now=NOW)
    assert t["status"] == "traded" and t["name"] == "Tencent Holdings Limited", "over the counter, still a company"
    assert SC.listed_now("AAPL")["status"] == "listed", "a listed symbol needs no thread and no quote"


def test_a_symbol_that_no_longer_trades_says_its_last_trade_and_no_delisting(directory):
    r = SC.check("OLDCO", now=NOW)
    assert r["status"] == "not_trading" and r["last_trade"] == "2025-10-27"
    assert r["status"] in SC.REFUSED


def test_a_check_that_cannot_be_made_is_never_a_not_found(directory, monkeypatch):
    def down(sym):
        raise TimeoutError("quote source down")
    assert SC.check("ZZZZQX", quote_fn=down, now=NOW)["status"] == "unavailable"
    # the directory unreadable: only a recent trade is an answer, so an unknown is "could not check"
    monkeypatch.setattr(universe, "_rows_today", lambda: {"rows": [], "error": "down"})
    SC.forget()
    assert SC.check("ZZZZQX", now=NOW)["status"] == "unavailable"
    assert SC.check("TCEHY", now=NOW)["status"] == "traded"
    # a guard that reads only what is loaded never starts the download, and refuses nothing it cannot check
    monkeypatch.setattr(universe, "_MEMO", {})
    assert SC.check("MARKETS", loaded_only=True)["status"] == "unavailable"


def test_answers_are_kept_briefly_and_a_miss_never_for_good(directory, monkeypatch):
    calls = []
    monkeypatch.setattr(SC, "QUOTE", lambda s: calls.append(s) or {})
    SC.check("ZZZZQX", now=NOW)
    SC.check("ZZZZQX", now=NOW)
    assert calls == ["ZZZZQX"], "a repeated miss is not asked again at once"
    assert SC._TTL["unknown"] == 600 and SC._TTL["listed"] <= 6 * 3600, "a symbol can list tomorrow"
    assert "unavailable" not in SC._TTL, "could not check is never kept"
    # ten minutes on, it is asked again
    real = SC.time.time
    monkeypatch.setattr(SC.time, "time", lambda: real() + 601)
    SC.check("ZZZZQX", now=NOW)
    assert calls == ["ZZZZQX", "ZZZZQX"]


# ------------------------------------------------------------------------------------------------ the route
client = TestClient(main.app)


def test_the_route_answers_and_suggests(directory):
    r = client.get("/api/symbol-check", params={"q": "APPL", "from": "#/watchlist"}).json()
    assert r["status"] == "unknown" and r["suggestions"][0]["symbol"] == "AAPL"
    ok = client.get("/api/symbol-check", params={"q": "brk.b"}).json()
    assert (ok["status"], ok["symbol"]) == ("listed", "BRK-B") and "suggestions" not in ok


def test_acceptance_4_invalid_symbol_hits_are_logged_sanitised(directory, caplog):
    SC._MISSES.clear()
    # the "optic" tree has its own handler and does not propagate (app/main.py), so the capture is attached to it
    optic = logging.getLogger("optic")
    optic.addHandler(caplog.handler)
    caplog.set_level(logging.INFO, logger="optic.symbols")
    try:
        _ask_three()
    finally:
        optic.removeHandler(caplog.handler)
    lines = [r.getMessage() for r in caplog.records if r.name == "optic.symbols"]
    assert "invalid symbol 'MARKETS injected' (invalid) from #/watchlist" in lines, lines
    assert "invalid symbol 'ZZZZQX' (unknown) from https://news.example.com" in lines
    assert not any("AAPL" in x for x in lines), "a listed symbol is not a miss"
    assert not any("\n" in x or "\r" in x or "email" in x for x in lines), "no forged line, no query string"
    m = SC.misses()
    assert {x["text"] for x in m["misses"]} == {"MARKETS INJECTED", "ZZZZQX"}
    zz = next(x for x in m["misses"] if x["text"] == "ZZZZQX")
    assert zz["count"] == 1 and zz["from"] == {"https://news.example.com": 1}
    # the owner reads them; nobody else does
    assert client.get("/api/admin/symbol-misses").status_code == 403


def _ask_three():
    client.get("/api/symbol-check", params={"q": "MAR\r\nKETS injected", "from": "#/watchlist?email=x@y.com"})
    client.get("/api/symbol-check", params={"q": "ZZZZQX", "from": "https://news.example.com/story?id=7"})
    client.get("/api/symbol-check", params={"q": "AAPL", "from": "#/home"})


# ------------------------------------------------------------------------------------------------ the guards
GOOD = "tungsten-carbide-9"


@pytest.fixture
def signed_in(accounts):
    client.cookies.clear()
    client.post("/api/auth/register", json={"first_name": "Alex", "last_name": "Yazji", "email": "reader@example.com",
                                            "password": GOOD, "confirm_password": GOOD})
    yield {"csrf": client.cookies.get(config.CSRF_COOKIE), "user": store.get_user_by_email("reader@example.com")}
    client.cookies.clear()


def test_acceptance_3_a_bogus_symbol_cannot_be_saved_to_a_watchlist(directory, signed_in):
    h = {"X-Optic-CSRF": signed_in["csrf"]}
    made = client.post("/api/watchlists", headers=h, json={"name": "L", "symbols": ["AAPL"]}).json()
    wid = made["watchlist"]["id"] if "watchlist" in made else made["watchlists"][0]["id"]
    bad = client.post("/api/watchlists/{}/items".format(wid), headers=h, json={"symbol": "MARKETS"})
    assert bad.status_code == 400 and bad.json()["detail"] == "No company found for 'MARKETS', so it was not added."
    good = client.post("/api/watchlists/{}/items".format(wid), headers=h, json={"symbol": "nvda"})
    assert good.status_code == 200 and "NVDA" in good.json()["watchlist"]["symbols"]
    otc = client.post("/api/watchlists/{}/items".format(wid), headers=h, json={"symbol": "TCEHY"})
    assert otc.status_code == 200, "a company traded outside the directory still saves"


def test_acceptance_3_compare_leaves_out_a_symbol_that_names_nothing(directory, monkeypatch):
    asked = []
    monkeypatch.setattr(main, "_swing_snapshot", lambda sym, *a, **k: asked.append(sym) or {"error": "stub"})
    out = main._compare_payload(["AAPL", "MARKETS"])
    assert out["available"] is False and out["not_found"] == ["MARKETS"]
    assert out["reason"] == "No company found for 'MARKETS', so there are fewer than 2 to compare."
    assert asked == [], "nothing is fetched for a comparison that cannot be made"
    main._compare_payload(["AAPL", "MSFT", "ZZZZQX"])
    assert "ZZZZQX" not in asked and set(asked) == {"AAPL", "MSFT"}


def test_acceptance_3_milo_is_given_no_context_for_a_symbol_that_names_nothing(directory):
    ctx = {"ticker": "MARKETS", "focus": {"scope": "auto", "view": "overview", "ticker": "MARKETS"}, "quote": {"price": None}}
    out = main._without_unknown_page_symbol(ctx)
    assert "ticker" not in out and out["focus"]["ticker"] is None
    assert "MARKETS" in out["page_symbol_note"] and "no data is available" in out["page_symbol_note"]
    kept = main._without_unknown_page_symbol({"ticker": "AAPL", "focus": {"ticker": "AAPL"}})
    assert kept["ticker"] == "AAPL" and kept["focus"]["ticker"] == "AAPL"
    src = (ROOT / "app" / "main.py").read_text()
    assert "context = await _run(_without_unknown_page_symbol, _without_linked_keys(context))" in src


# ------------------------------------------------------------------------------------------------ the page
def page(tmp_path, cases):
    return _run(tmp_path, f"""
      const R = await import('{(JS / "core/router.js").as_posix()}');
      const SC = await import('{(JS / "core/symbolcheck.js").as_posix()}');
      const NF = await import('{(JS / "pages/notfound.js").as_posix()}');
      const d = await import('{(JS / "core/dom.js").as_posix()}');
      const cases = {json.dumps(cases)};
      const out = cases.map(([hash, check]) => {{
        const r = R.parse(hash), asked = SC.askedSymbol(r);
        const res = check || {{ status: 'unknown', query: asked }};
        const gated = asked != null && (r.view === 'notfound' || !SC.admissible(res));
        const html = gated ? d.toString(NF.view({{ view: 'notfound', attempted: asked, check: res }})) : '';
        return {{ hash, view: r.view, asked, gated, html, words: gated ? NF.words(res, asked) : null }};
      }});
      print(JSON.stringify(out));
    """)


def test_acceptance_1_every_invalid_address_draws_the_not_found_page_and_no_dossier(tmp_path):
    """The client half of the first test: each address, routed and gated as app.js gates it, is the not-found page,
    with its heading first, the search box holding what was typed, and nothing of a Dossier."""
    sug = [{"symbol": "AAPL", "name": "Apple Inc", "kind": "stock"}, {"symbol": "GLD", "name": "SPDR Gold Shares", "kind": "etf"}]
    cases = [["#/MARKETS", {"status": "unknown", "query": "MARKETS", "suggestions": sug}], ["#/ZZZZQX", None], ["#/APPL", None],
             ["#/AAPLL/financials", None], ["#/%20", {"status": "invalid", "query": " "}], ["#/%25", {"status": "invalid", "query": "%"}],
             ["#/AAPL!", None], ["#/%3Cscript%3E", {"status": "invalid", "query": "<script>"}], ["#/instrument/", {"status": "invalid", "query": ""}],
             ["#/XXXX/chart", None], ["#/OLDCO", {"status": "not_trading", "query": "OLDCO", "last_trade": "2025-10-27"}],
             ["#/QWERTY/options", {"status": "unavailable", "query": "QWERTY"}]]
    got = page(tmp_path, cases)
    for g in got:
        assert g["gated"], g["hash"]
        h = g["html"]
        assert h.startswith('<header class="page-head"><h1 class="t-h2" id="nf-h">'), g["hash"]
        for dossier in ('class="tabs"', "dstick", "chart-slot", "data-v2-milo", "Watch"):
            assert dossier not in h, (g["hash"], dossier)
        assert 'href="#/explore">Discover</a>' in h and 'href="#/read">Markets Read</a>' in h
    by = {g["hash"]: g for g in got}
    m = by["#/MARKETS"]
    assert m["words"]["h1"] == "No company found for 'MARKETS'"
    assert 'value="MARKETS"' in m["html"], "the search box holds what was typed"
    assert m["html"].index("Markets Read</b>") < m["html"].index(">AAPL<"), "the section a section's name names, first"
    assert ">ETF</span>" in m["html"] and ">Stock</span>" in m["html"], "a stock and a fund, each said to be one"
    assert by["#/%3Cscript%3E"]["words"]["h1"] == "No company found for '<script>'"
    assert "<script>" not in by["#/%3Cscript%3E"]["html"] and "&lt;script&gt;" in by["#/%3Cscript%3E"]["html"]
    assert by["#/instrument/"]["words"]["h1"] == "No company found"
    old = by["#/OLDCO"]["words"]["line"]
    assert "the last trade Optic can find for it was on Oct 27, 2025" in old and "may have been delisted" in old
    assert "was delisted on" not in old, "a delisting Optic has not verified is not stated"
    un = by["#/QWERTY/options"]
    assert un["words"]["h1"] == "Could not check this symbol right now" and "data-v2-nf-retry" in un["html"]
    assert "No company found" not in un["html"], "could not check is not a not-found"


def test_acceptance_2_a_valid_symbol_opens_the_page_it_asked_for(tmp_path):
    got = page(tmp_path, [["#/aapl", {"status": "listed", "symbol": "AAPL"}], ["#/brk.b/options", {"status": "listed", "symbol": "BRK-B"}],
                          ["#/TCEHY", {"status": "traded", "symbol": "TCEHY"}], ["#/instrument/%5EGSPC", {"status": "instrument"}],
                          ["#/watchlist", None], ["#/compare?t=AAPL,MSFT", None]])
    assert [(g["view"], g["asked"], g["gated"]) for g in got] == [
        ("overview", "AAPL", False), ("swing", "BRK-B", False), ("overview", "TCEHY", False),
        ("instrument", "^GSPC", False), ("watchlist", None, False), ("compare", None, False)]


def test_the_app_checks_before_any_symbol_page_draws():
    app = (JS / "app.js").read_text()
    show = app.split("async function show(route) {", 1)[1].split("\nfunction accountBody", 1)[0]
    assert show.index("symbols.check(asked") < show.index("page.render(view, route, app)")
    assert "if (route.view === 'notfound' || !symbols.admissible(res))" in show and "load = PAGES.notfound;" in show
    assert "notfound: lazy(() => import('./pages/notfound.js'), 'notfound')" in app
    # the store refuses what the check refuses; Compare checks every name before it compares
    st = (JS / "core/store.js").read_text().split("export async function follow(", 1)[1].split("\n}\n", 1)[0]
    assert "const known = await symbols.check(sym);" in st and "symbols.refusal(known)" in st
    cmp_src = (JS / "pages/compare.js").read_text()
    assert "const checks = await Promise.all(t.map((s) => symbols.check(s, { from: '#/compare' })));" in cmp_src
    sc = (JS / "core/symbolcheck.js").read_text()
    assert "timeout = 8000" in sc and "status: 'unavailable'" in sc


def test_the_store_refuses_a_symbol_the_check_refuses(tmp_path):
    got = _run(tmp_path, f"""
      const answers = {{ MARKETS: {{ status: 'unknown', query: 'MARKETS' }}, OLDCO: {{ status: 'not_trading', query: 'OLDCO' }}, NVDA: {{ status: 'listed', symbol: 'NVDA' }} }};
      globalThis.fetch = async (url) => {{
        const q = decodeURIComponent((/q=([^&]*)/.exec(url) || [])[1] || '').toUpperCase();
        const body = JSON.stringify(answers[q] || {{ status: 'unknown', query: q }});
        return {{ ok: true, status: 200, statusText: 'OK', headers: {{ get: () => null }}, text: async () => body }};
      }};
      globalThis.AbortController = class {{ constructor() {{ this.signal = {{ addEventListener() {{}}, aborted: false }}; }} abort() {{}} }};
      // JavaScriptCore's shell has setTimeout and no clearTimeout
      if (typeof globalThis.clearTimeout !== 'function') globalThis.clearTimeout = () => {{}};
      globalThis.CustomEvent = class {{ constructor(t) {{ this.type = t; }} }};
      window.dispatchEvent = () => true;
      const s = await import('{(JS / "core/store.js").as_posix()}');
      localStorage.setItem('optic.session.holder.v1', 'guest');
      await s.loadLists();
      const said = {{}};
      for (const sym of ['MARKETS', 'OLDCO', 'NVDA']) {{ try {{ await s.follow(sym); said[sym] = 'added'; }} catch (e) {{ said[sym] = e.message; }} }}
      print(JSON.stringify({{ said, syms: (s.activeList() || {{}}).symbols || [] }}));
    """)
    assert got["said"]["MARKETS"] == "No company found for 'MARKETS', so it was not added."
    assert got["said"]["OLDCO"] == "OLDCO no longer trades, so it was not added."
    assert got["said"]["NVDA"] == "added" and got["syms"] == ["NVDA"]


def test_the_page_is_usable_on_a_phone():
    css = (ROOT / "static/v2/css/pages.css").read_text()
    assert "[data-v2-nf-form] input { font-size: var(--t-lg); }" in css, "16px: a phone does not zoom into the box"
    assert ".ds-row { display: flex; align-items: center; gap: 10px; min-height: var(--tap);" in css, "each row a tap target"
    assert "@media (max-width: 560px) { .ds-search { flex-wrap: wrap; } .ds-search .btn { width: 100%; } }" in css
