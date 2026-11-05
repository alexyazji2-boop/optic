"""Handoff 5 of the owner's handover pack (2026-11-03): the Saved Research Library.

The audit found research had no home: a comparison, a Milo conversation or a research sheet could not be kept and
returned to. The acceptance tests:

1. Save from Dossier, Compare and Milo; all three appear in the library and reopen with correct ticker context.
2. Delete removes the item everywhere; a duplicate save does not duplicate.
3. A saved Milo conversation keeps its original sources and as-of dates on reopen.
4. The library is private per account (ownership tests).

Then the edge cases the handoff names: a ticker that later goes, a comparison missing one, the inline save failure
with Retry, the library's own loading ending in a retry state, pages and search, the size limits, the questions saved
before the library, no saving without a press, and the phone layout.

The pages' parts run in JavaScriptCore (each page's own save spec, the Milo conversation's save and restore, the Save
buttons' state); the server's in Python against a fresh accounts database per test.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app import library, universe
from app.auth import config, store
from tests.test_frontend_v2_stage0 import V2, _run

ROOT = Path(__file__).resolve().parents[1]
JS = V2 / "js"
GOOD = "tungsten-carbide-9"
client, other = TestClient(main.app), TestClient(main.app)


@pytest.fixture(autouse=True)
def fresh(accounts, monkeypatch):
    client.cookies.clear()
    other.cookies.clear()
    monkeypatch.setattr(library, "_LISTED", {})
    # the exchange directory and the quote source, stood in: AAPL, MSFT and NVDA listed; TCEHY outside the directory
    # but trading (over the counter); ZZGONE outside it with no price
    monkeypatch.setattr(universe, "known_symbol", lambda s: s in {"AAPL", "MSFT", "NVDA", "SPY"})
    monkeypatch.setattr(library, "QUOTE", lambda s: {} if s == "ZZGONE" else {"price": 74.1, "trade_time": None})
    return accounts


def register(http, email):
    http.post("/api/auth/register", json={"first_name": "A", "last_name": "B", "email": email,
                                          "password": GOOD, "confirm_password": GOOD})
    return {"X-Optic-CSRF": http.cookies.get(config.CSRF_COOKIE)}


@pytest.fixture
def two():
    return {"mine": register(client, "mine@example.com"), "theirs": register(other, "theirs@example.com")}


def save(http, headers, body):
    return http.post("/api/library", headers=headers, json=body)


# What each page would save, from its own code: the Dossier's header provider, the Compare page's provider after a
# comparison, and Milo's conversation spec from a conversation with one answer and its sources.
PAGE_SPECS = """
  // JavaScriptCore waits for every timer: a zero-delay one runs as a microtask, the API's time limits never
  globalThis.setTimeout = (fn, ms) => { if (!ms) Promise.resolve().then(fn); return 0; };
  globalThis.CSS = { escape: (s) => String(s) }; globalThis.clearTimeout = () => {};
  globalThis.CustomEvent = class { constructor(t, o) { this.type = t; this.detail = o && o.detail; } }; window.dispatchEvent = () => true;
  globalThis.AbortController = class { constructor() { this.signal = { aborted: false, reason: null, addEventListener() {} }; } abort(r) { this.signal.aborted = true; this.signal.reason = r; } };
  globalThis.history = { state: null, replaceState() {} };
  const COMPARE = { available: true, tickers: ['AAPL', 'MSFT'], rows: [{ ticker: 'AAPL', name: 'Apple Inc.' }, { ticker: 'MSFT', name: 'Microsoft Corporation' }, { ticker: 'SPY', name: 'SPDR S&P 500', is_benchmark: true }],
    take: { available: false }, horizons: [], performance: { series: [] } };
  globalThis.fetch = async (url) => ({ ok: true, status: 200, statusText: '', headers: { get: () => null }, text: async () => JSON.stringify(String(url).startsWith('/api/compare') ? COMPARE : {}) });
  localStorage.setItem('optic.timezone', 'America/New_York');
  const U = await import('@UI@'), L = await import('@CORE@'), F = await import('@FRAME@'), C = await import('@COMPARE@'), M = await import('@MILO@'), { toString } = await import('@DOM@');
  const D = { sym: 'AAPL', quote: { name: 'Apple Inc.', price: 352.79, change_pct: 6.29, trade_time: '2026-11-04T18:46:30Z', delayed_minutes: 15 },
    session: { prices: { phase: 'regular' }, session: { is_regular: true, last_close: { date: '2026-11-03' } } } };
  const header = toString(F.header('AAPL', D, 'chart', { bar: true }));
  const company = U._test.SPECS.get('company')();
  const main = { innerHTML: '', style: { setProperty() {} }, addEventListener() {}, querySelector: () => null, querySelectorAll: () => [] };
  await C.render(main, { params: { t: 'AAPL,MSFT' } });
  for (let i = 0; i < 20; i++) await Promise.resolve();
  const comparison = U._test.SPECS.get('comparison')();
  const facts = new Map([[1, { symbol: 'AAPL', policyLine: '', level: 'intermediate',
    citations: [{ title: 'Apple 10-K 2025', url: 'https://www.sec.gov/aapl-10k' }],
    retrieved: [{ label: 'AAPL quote', source: 'Yahoo Finance', as_of: '2026-10-28T18:46:30Z', retrieved_at: '2026-10-28T18:46:31Z' }],
    loaded: [{ label: 'MSFT quote', source: 'Yahoo Finance', as_of: '2026-10-28T18:45:02Z' }],
    context: { focus: { view_label: 'AAPL Dossier, Chart', ticker: 'AAPL', captured_at: '2026-10-28T18:46:29Z' } } }]]);
  const conversation = M.conversationSpec({ id: 'cmiloaapl1', messages: [{ role: 'user', content: 'Is AAPL cheap on earnings?' }, { role: 'assistant', content: 'At **30 times** trailing earnings [[src framework]] it is above its five-year median.' }], lastTicker: 'AAPL' }, facts, 'AAPL Dossier, Chart');
  const blank = M.conversationSpec({ id: 'c0', messages: [{ role: 'user', content: 'Hi' }] }, new Map());
  print(JSON.stringify({ header, company, comparison, conversation, blank }));
"""


def js(body: str, **extra) -> str:
    paths = {"UI": "ui/library.js", "CORE": "core/library.js", "FRAME": "pages/dossier-frame.js", "COMPARE": "pages/compare.js",
             "MILO": "ui/milo.js", "DOM": "core/dom.js", "SAVED": "pages/saved.js", "STORE": "core/store.js"}
    for k, v in paths.items():
        body = body.replace("@{}@".format(k), (JS / v).as_posix())
    for k, v in extra.items():
        body = body.replace("@{}@".format(k), v)
    return body


def page_specs(tmp_path):
    return _run(tmp_path, js(PAGE_SPECS))


# ------------------------------------------------------------------ acceptance 1: save from three places, reopen

def test_acceptance_1_save_from_dossier_compare_and_milo_and_reopen_with_their_tickers(tmp_path, two):
    specs = page_specs(tmp_path)
    # each page offers Save, and what it would keep is its own: the Dossier's tab and price, Compare's tickers, Milo's
    # conversation with its sources
    assert 'data-v2-save="company"' in specs["header"] and 'data-v2-save-key="company:AAPL"' in specs["header"]
    assert specs["company"]["kind"] == "company" and specs["company"]["tickers"] == ["AAPL"] and specs["company"]["ref"] == {"tab": "chart"}
    assert specs["company"]["summary"]["names"] == {"AAPL": "Apple Inc."} and specs["company"]["summary"]["price"]["price"] == 352.79
    assert specs["comparison"]["kind"] == "comparison" and specs["comparison"]["tickers"] == ["AAPL", "MSFT"]
    assert specs["comparison"]["summary"]["names"] == {"AAPL": "Apple Inc.", "MSFT": "Microsoft Corporation"}, "the benchmark row is not a compared name"
    conv = specs["conversation"]
    assert conv["kind"] == "conversation" and conv["tickers"] == ["AAPL"] and conv["ref"] == {"conversation": "cmiloaapl1"}
    assert specs["blank"]["blocked"].startswith("Ask Milo something first"), "a conversation without an answer is not saved"

    saved = {}
    for spec in (specs["company"], specs["comparison"], conv):
        r = save(client, two["mine"], spec)
        assert r.status_code == 200, r.text
        saved[spec["kind"]] = r.json()["item"]
    listed = client.get("/api/library").json()
    assert {i["kind"]: i["tickers"] for i in listed["items"]} == {"company": ["AAPL"], "comparison": ["AAPL", "MSFT"], "conversation": ["AAPL"]}
    assert listed["counts"]["company"] == listed["counts"]["comparison"] == listed["counts"]["conversation"] == 1
    assert all(re.match(r"^(AAPL|AAPL vs MSFT), [A-Z][a-z]{2} \d{1,2}, 20\d\d$", i["name"]) for i in listed["items"]), "default name: tickers and date"
    full = client.get("/api/library/{}".format(saved["conversation"]["id"])).json()["item"]

    # reopened: the company on its Dossier tab, the comparison in Compare, the conversation in Milo about AAPL
    got = _run(tmp_path, js("""
      localStorage.setItem('optic.timezone', 'America/New_York');
      const L = await import('@CORE@'), M = await import('@MILO@');
      const items = @ITEMS@, full = @FULL@;
      const r = M.restoreSaved(full, () => 'cnew');
      print(JSON.stringify({ routes: items.map((i) => [i.kind, L.routeOf(i)]), conv: r.conv, ticker: r.ticker, note: r.items[0].text, facts: [...r.facts.entries()] }));
    """, ITEMS=json.dumps(listed["items"]), FULL=json.dumps(full)))
    routes = dict(got["routes"])
    assert routes["company"] == "#/AAPL/chart" and routes["comparison"] == "#/compare?t=AAPL,MSFT"
    assert routes["conversation"] is None, "a conversation opens in Milo's panel, not at an address"
    assert got["ticker"] == "AAPL" and got["conv"]["lastTicker"] == "AAPL" and got["conv"]["id"] == "cmiloaapl1"
    assert got["conv"]["messages"][0]["content"] == "Is AAPL cheap on earnings?"
    facts = dict((int(k), v) for k, v in got["facts"])
    assert facts[1]["context"]["focus"]["ticker"] == "AAPL" and facts[1]["symbol"] == "AAPL", "Milo's context is the saved ticker"


def test_the_research_sheet_saves_and_reopens_on_todays_figures(tmp_path, two):
    src = (JS / "pages/sheet.js").read_text()
    assert "saveButton('sheet', keyOf('sheet', [sym]), { label: 'Save sheet' })" in src and "provide('sheet'," in src
    r = save(client, two["mine"], {"kind": "sheet", "tickers": ["NVDA"], "summary": {"names": {"NVDA": "NVIDIA"}}})
    assert r.status_code == 200 and r.json()["item"]["kind"] == "sheet"
    got = _run(tmp_path, js("const L = await import('@CORE@'); print(JSON.stringify(L.routeOf(@IT@)));", IT=json.dumps(r.json()["item"])))
    assert got == "#/NVDA/sheet"
    css = (V2 / "css/pages.css").read_text()
    assert ".sh-actions" in css[css.index("@media print"):css.index("@media print") + 400], "Save is not printed with the sheet"


# ------------------------------------------------------------------ acceptance 2: delete everywhere, no duplicates

def test_acceptance_2_delete_removes_the_item_everywhere(tmp_path, two):
    item = save(client, two["mine"], {"kind": "company", "tickers": ["AAPL"]}).json()["item"]
    assert client.get("/api/library?key=company:AAPL").json()["items"][0]["id"] == item["id"], "the Save buttons ask by key"
    assert client.delete("/api/library/{}".format(item["id"]), headers=two["mine"]).status_code == 200
    assert client.get("/api/library/{}".format(item["id"])).status_code == 404
    assert client.get("/api/library").json()["items"] == [] and client.get("/api/library?key=company:AAPL").json()["items"] == []
    assert client.get("/api/library").json()["counts"]["company"] == 0
    assert client.delete("/api/library/{}".format(item["id"]), headers=two["mine"]).status_code == 404
    # and every Save button for it on the page turns back to Save, told by the same delete (core/library.js remove)
    got = _run(tmp_path, js("""
      globalThis.setTimeout = (fn, ms) => { if (!ms) Promise.resolve().then(fn); return 0; };
      globalThis.CSS = { escape: (s) => String(s) }; globalThis.clearTimeout = () => {};
      globalThis.AbortController = class { constructor() { this.signal = { aborted: false, reason: null, addEventListener() {} }; } abort() {} };
      const heard = []; globalThis.CustomEvent = class { constructor(t, o) { this.type = t; this.detail = o && o.detail; } };
      const listeners = {}; window.addEventListener = (t, f) => { (listeners[t] = listeners[t] || []).push(f); };
      window.dispatchEvent = (e) => { heard.push([e.type, e.detail]); (listeners[e.type] || []).forEach((f) => f(e)); return true; };
      globalThis.fetch = async (url, o) => ({ ok: true, status: 200, statusText: '', headers: { get: () => null }, text: async () => JSON.stringify(o && o.method === 'DELETE' ? { ok: true } : { items: [@ITEM@] }) });
      const S = await import('@STORE@'); S.state.auth = 'user';
      const L = await import('@CORE@'), U = await import('@UI@');
      const label = { textContent: 'Saved' };
      const btn = { dataset: { v2SaveKey: 'company:AAPL', v2SaveLabel: 'Save' }, attrs: { 'aria-pressed': 'true' }, title: '', classList: { contains: () => false },
        setAttribute(k, v) { this.attrs[k] = v; }, querySelector: () => label };
      document.querySelectorAll = (sel) => (sel === '[data-v2-save-key="company:AAPL"]' ? [btn] : []);
      const before = await L.savedAs('company:AAPL');
      await L.remove(@ITEM@);
      print(JSON.stringify({ before: !!before, after: L.known('company:AAPL'), pressed: btn.attrs['aria-pressed'], label: label.textContent, heard }));
    """, ITEM=json.dumps(item)))
    assert got["before"] is True and got["after"] is None
    assert got["pressed"] == "false" and got["label"] == "Save"
    assert ["v2:library", {"key": "company:AAPL", "item": None}] in got["heard"]


def test_acceptance_2_a_duplicate_save_does_not_duplicate(two):
    first = save(client, two["mine"], {"kind": "comparison", "tickers": ["AAPL", "MSFT"], "name": "Big tech"}).json()["item"]
    again = save(client, two["mine"], {"kind": "comparison", "tickers": ["MSFT", "AAPL"]})
    assert again.status_code == 409, "the same comparison in another order is the same thing"
    dup = again.json()["detail"]["duplicate"]
    assert dup["id"] == first["id"] and dup["name"] == "Big tech" and "already saved" in again.json()["detail"]["message"]
    assert client.get("/api/library").json()["total"] == 1, "nothing was added by asking"
    upd = save(client, two["mine"], {"kind": "comparison", "tickers": ["MSFT", "AAPL"], "on_duplicate": "update",
                                     "summary": {"headline": "newer"}}).json()
    assert upd["updated"] is True and upd["item"]["id"] == first["id"] and upd["item"]["name"] == "Big tech", "updating keeps the name"
    assert upd["item"]["summary"] == {"headline": "newer"} and upd["item"]["updated_at"] >= first["updated_at"]
    assert client.get("/api/library").json()["total"] == 1
    copy = save(client, two["mine"], {"kind": "comparison", "tickers": ["AAPL", "MSFT"], "name": "Big tech (copy)", "on_duplicate": "copy"}).json()
    assert copy["item"]["id"] != first["id"] and copy["item"]["name"] == "Big tech (copy)"
    assert client.get("/api/library").json()["total"] == 2, "a copy only when the reader asks for one"


def test_the_save_control_asks_before_a_duplicate_and_never_shows_a_failed_save_as_saved(tmp_path):
    """The press: a 409 opens "Already saved" (update or a copy), and any other failure says so beside the button with
    Retry while the button stays "Save"."""
    got = _run(tmp_path, js("""
      globalThis.setTimeout = (fn, ms) => { if (!ms) Promise.resolve().then(fn); return 0; };
      globalThis.CSS = { escape: (s) => String(s) }; globalThis.clearTimeout = () => {};
      globalThis.AbortController = class { constructor() { this.signal = { aborted: false, reason: null, addEventListener() {} }; } abort() {} };
      globalThis.CustomEvent = class { constructor(t, o) { this.type = t; this.detail = o && o.detail; } }; window.dispatchEvent = () => true;
      globalThis.requestAnimationFrame = (f) => 0;
      let answer = { status: 503, body: { detail: 'The accounts database is busy.' } };
      globalThis.fetch = async () => ({ ok: answer.status < 400, status: answer.status, statusText: '', headers: { get: () => null }, text: async () => JSON.stringify(answer.body) });
      const S = await import('@STORE@'); S.state.auth = 'user';
      const U = await import('@UI@');
      U.provide('company', () => ({ kind: 'company', tickers: ['AAPL'], ref: { tab: '' } }));
      const err = { hidden: true, innerHTML: '', querySelectorAll: () => [] };
      const wrap = { querySelector: (s) => (s === '.lib-err' ? err : null) };
      const btn = { dataset: { v2Save: 'company', v2SaveKey: 'company:AAPL' }, disabled: false, attrs: { 'aria-pressed': 'false' }, setAttribute(k, v) { this.attrs[k] = v; }, closest: (s) => (s === '.lib-save' ? wrap : null) };
      await U._test.press(btn);
      print(JSON.stringify({ failed: { hidden: err.hidden, text: err.innerHTML, pressed: btn.attrs['aria-pressed'], busy: btn.attrs['aria-busy'], disabled: btn.disabled } }));
    """))
    f = got["failed"]
    assert f["hidden"] is False and f["text"].startswith("Not saved: The accounts database is busy. <button") and "data-v2-save-retry" in f["text"] and ">Retry<" in f["text"]
    assert f["pressed"] == "false", "a failed save is not shown as saved"
    assert f["busy"] == "false" and f["disabled"] is False, "the button is ready for Retry"
    src = (JS / "ui/library.js").read_text()
    assert "if (dup) duplicateSheet(dup, body, b);" in src and "Update the saved one" in src and "Save a copy" in src


# ------------------------------------------------------------------ acceptance 3: a conversation keeps its sources

def test_acceptance_3_a_saved_conversation_keeps_its_sources_and_their_dates(tmp_path, two):
    spec = page_specs(tmp_path)["conversation"]
    item = save(client, two["mine"], spec).json()["item"]
    assert "conversation" not in client.get("/api/library").json()["items"][0], "the list does not carry the copy: it loads on open"
    full = client.get("/api/library/{}".format(item["id"])).json()["item"]
    answer = full["conversation"]["messages"][1]
    assert answer["sources"]["retrieved"] == [{"label": "AAPL quote", "source": "Yahoo Finance", "as_of": "2026-10-28T18:46:30Z", "retrieved_at": "2026-10-28T18:46:31Z"}]
    assert answer["sources"]["citations"] == [{"title": "Apple 10-K 2025", "url": "https://www.sec.gov/aapl-10k"}]
    assert answer["sources"]["loaded"][0]["as_of"] == "2026-10-28T18:45:02Z" and answer["focus"]["captured_at"] == "2026-10-28T18:46:29Z"
    assert answer["content"].startswith("At **30 times** trailing earnings"), "the words as answered"
    # reopened in Milo: the note says when it was saved and that its figures are as of then, and each source keeps its day
    full["updated_at"] = full["created_at"] = "2026-10-28T19:15:00Z"
    got = _run(tmp_path, js("""
      localStorage.setItem('optic.timezone', 'America/New_York');
      const M = await import('@MILO@'), { toString } = await import('@DOM@');
      const r = M.restoreSaved(@FULL@);
      const again = M.conversationSpec(r.conv, r.facts, 'AAPL Dossier, Chart');
      print(JSON.stringify({ note: r.items[0].text, sources: toString(M.sourceLists(r.facts.get(1))), about: toString(M.aboutLine(r.facts.get(1), { view: 'saved' })), again }));
    """, FULL=json.dumps(full)))
    assert got["note"] == "Saved on Oct 28, 2026 at 3:15 pm EDT; figures as of then. Each answer keeps the sources it had and when they were read."
    assert "observed Oct 28, 2:46 pm" in got["sources"] and "retrieved Oct 28, 2:46 pm" in got["sources"], got["sources"]
    assert "quote observed Oct 28, 2:45 pm" in got["sources"] and "Apple 10-K 2025" in got["sources"]
    assert "Oct 28, 2:46 pm" in got["about"], "when it was asked, with its day"
    # saving it again saves the same sources: a reopened conversation carries them on
    assert got["again"]["conversation"]["messages"][1]["sources"] == {k: answer["sources"].get(k, []) for k in ("citations", "read", "retrieved", "loaded")}


# ------------------------------------------------------------------ acceptance 4: private per account

def test_acceptance_4_the_library_is_private_per_account(two):
    mine = save(client, two["mine"], {"kind": "company", "tickers": ["AAPL"], "summary": {"note": "private thinking"}}).json()["item"]
    conv = save(client, two["mine"], {"kind": "conversation", "tickers": ["AAPL"], "ref": {"conversation": "csecret"},
                                      "conversation": {"messages": [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}]}}).json()["item"]
    assert other.get("/api/library").json()["items"] == [] and other.get("/api/library").json()["total"] == 0
    for it in (mine, conv):
        assert other.get("/api/library/{}".format(it["id"])).status_code == 404, "not 403: an id reveals nothing"
        assert other.patch("/api/library/{}".format(it["id"]), headers=two["theirs"], json={"name": "mine now"}).status_code == 404
        assert other.delete("/api/library/{}".format(it["id"]), headers=two["theirs"]).status_code == 404
    assert other.get("/api/library?key=company:AAPL").json()["items"] == [] and other.get("/api/library?key=conversation:csecret").json()["items"] == []
    # the other account saving the same thing makes its own; "update" never reaches mine
    theirs = save(other, two["theirs"], {"kind": "company", "tickers": ["AAPL"], "on_duplicate": "update", "summary": {"note": "theirs"}}).json()
    assert theirs["updated"] is False and theirs["item"]["id"] != mine["id"]
    still = client.get("/api/library/{}".format(mine["id"])).json()["item"]
    assert still["summary"] == {"note": "private thinking"} and still["name"] == mine["name"]
    # a user id in the body is not an owner
    sneaky = save(other, two["theirs"], {"kind": "sheet", "tickers": ["NVDA"], "user_id": "someone", "owner": "x"}).json()["item"]
    assert client.get("/api/library/{}".format(sneaky["id"])).status_code == 404
    # guests have none of it, and every write needs the page's CSRF pair
    guest = TestClient(main.app)
    for method, path in (("get", "/api/library"), ("get", "/api/library/{}".format(mine["id"])), ("post", "/api/library"),
                         ("patch", "/api/library/{}".format(mine["id"])), ("delete", "/api/library/{}".format(mine["id"]))):
        assert getattr(guest, method)(path).status_code == 401, (method, path)
    assert client.post("/api/library", json={"kind": "company", "tickers": ["MSFT"]}).status_code == 403
    assert client.delete("/api/library/{}".format(mine["id"])).status_code == 403
    assert client.get("/api/library/{}".format(mine["id"])).status_code == 200


def test_every_statement_is_bound_to_the_owner():
    src = (ROOT / "app/library.py").read_text()
    assert not re.search(r'(?<![A-Za-z0-9_])f(?:"""|\'\'\'|"|\')', src), "SQL here uses bound parameters, never f-strings"
    assert ".format(payload" not in src and ".format(request" not in src
    flat = re.sub(r'"\s*\n\s*"', "", src)   # Python's adjacent literals, as one statement
    for stmt in re.findall(r'"((?:SELECT|UPDATE|DELETE|INSERT)[^"]*)"', flat):
        if stmt.startswith("INSERT"):
            assert "user_id" in stmt
        else:
            assert "user_id = ?" in stmt or "WHERE {}" in stmt, stmt
    assert 'where, args = ["user_id = ?"], [user["id"]]' in src, "the list's own filter starts with the owner"


# ------------------------------------------------------------------ edge cases

def test_a_ticker_that_goes_keeps_the_item_readable_and_a_comparison_opens_without_it(tmp_path, two):
    co = save(client, two["mine"], {"kind": "company", "tickers": ["ZZGONE"], "summary": {"names": {"ZZGONE": "Gone Corp"},
                                                                                         "price": {"price": 12.5}}}).json()["item"]
    cmp_ = save(client, two["mine"], {"kind": "comparison", "tickers": ["AAPL", "MSFT", "ZZGONE"]}).json()["item"]
    otc = save(client, two["mine"], {"kind": "company", "tickers": ["TCEHY"]}).json()["item"]
    items = {i["id"]: i for i in client.get("/api/library").json()["items"]}
    assert items[co["id"]]["gone"] == ["ZZGONE"] and items[cmp_["id"]]["gone"] == ["ZZGONE"]
    assert items[otc["id"]]["gone"] == [], "outside the directory but trading: still there"
    got = _run(tmp_path, js("""
      localStorage.setItem('optic.timezone', 'America/New_York');
      const L = await import('@CORE@'), P = await import('@SAVED@'), { toString } = await import('@DOM@');
      const co = @CO@, cmp = @CMP@;
      print(JSON.stringify({ co: L.routeOf(co), cmp: L.routeOf(cmp), row: toString(P._test.item(co, 0)), crow: toString(P._test.item(cmp, 1)) }));
    """, CO=json.dumps(items[co["id"]]), CMP=json.dumps(items[cmp_["id"]])))
    assert got["co"] is None, "no Dossier to open"
    assert "ZZGONE is no longer available. Gone Corp, saved" in got["row"] and "at $12.50" in got["row"] and "disabled" in got["row"]
    assert got["cmp"] == "#/compare?t=AAPL,MSFT&gone=ZZGONE"
    assert "ZZGONE is no longer available. It opens with AAPL, MSFT." in got["crow"]
    src = (JS / "pages/compare.js").read_text()
    assert "were in this saved comparison and" in src.replace("${gone.length === 1 ? 'was' : 'were'}", "were") and "gone = String((route.params || {}).gone" in src
    # a source that fails is "cannot tell", never "gone"
    library._LISTED.clear()
    library.QUOTE = lambda s: (_ for _ in ()).throw(RuntimeError("feed down"))
    assert library.listed("ZZGONE") is None and library.listed("AAPL") is True


def test_the_list_pages_searches_and_counts(two):
    for i in range(35):
        save(client, two["mine"], {"kind": "company", "tickers": ["AAPL"], "name": "Apple {:02d}".format(i), "on_duplicate": "copy"})
    save(client, two["mine"], {"kind": "sheet", "tickers": ["NVDA"], "name": "Chips sheet"})
    first = client.get("/api/library").json()
    assert len(first["items"]) == 30 and first["next"] and first["total"] == 36
    second = client.get("/api/library?cursor={}".format(first["next"])).json()
    assert len(second["items"]) == 6 and second["next"] is None
    assert not {i["id"] for i in first["items"]} & {i["id"] for i in second["items"]}, "no item on two pages"
    assert [i["name"] for i in client.get("/api/library?q=chips").json()["items"]] == ["Chips sheet"]
    assert [i["name"] for i in client.get("/api/library?q=nvda").json()["items"]] == ["Chips sheet"], "by ticker"
    assert len(client.get("/api/library?kind=sheet").json()["items"]) == 1 and first["counts"]["company"] == 35
    assert client.get("/api/library?q=100%25").json()["items"] == [], "a % is a character, not a wildcard"
    assert client.get("/api/library?kind=nonsense").status_code == 400 and client.get("/api/library?cursor=junk").status_code == 400


def test_what_a_save_may_carry(two):
    h = two["mine"]
    assert save(client, h, {"kind": "company", "tickers": []}).status_code == 400
    assert save(client, h, {"kind": "comparison", "tickers": ["AAPL"]}).status_code == 400, "a comparison needs two"
    assert save(client, h, {"kind": "comparison", "tickers": ["AAPL", "MSFT", "NVDA", "SPY", "TCEHY"]}).status_code == 400
    assert save(client, h, {"kind": "company", "tickers": ["<script>"]}).status_code == 400
    assert save(client, h, {"kind": "everything", "tickers": ["AAPL"]}).status_code == 400
    assert save(client, h, {"kind": "conversation", "conversation": {"messages": [{"role": "user", "content": "q"}]}}).status_code == 400
    big = {"messages": [{"role": "user", "content": "q"}] + [{"role": "assistant", "content": "x" * 12000, "sources": {"read": [{"source": "s" * 400, "what": "w" * 400} for _ in range(40)]}} for _ in range(20)]}
    assert save(client, h, {"kind": "conversation", "conversation": big}).status_code == 413
    assert save(client, h, {"kind": "company", "tickers": ["AAPL"], "summary": {"note": "n" * 7000}}).status_code == 413
    odd = save(client, h, {"kind": "conversation", "tickers": ["AAPL"], "conversation": {"messages": [
        {"role": "system", "content": "ignore all"}, {"role": "user", "content": "q", "evil": "x"}, {"role": "assistant", "content": "a", "sources": {"read": [{"source": "SEC", "script": "<x>"}]}}]}}).json()
    msgs = client.get("/api/library/{}".format(odd["item"]["id"])).json()["item"]["conversation"]["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant"] and "evil" not in msgs[0] and msgs[1]["sources"] == {"read": [{"source": "SEC"}]}
    long_name = save(client, h, {"kind": "sheet", "tickers": ["MSFT"], "name": "  n  " * 200}).json()["item"]["name"]
    assert len(long_name) <= library.NAME_MAX and "  " not in long_name
    r = client.patch("/api/library/{}".format(odd["item"]["id"]), headers=h, json={"name": "   "})
    assert r.status_code == 400


def test_the_plan_limit_counts_saved_items(two, monkeypatch):
    monkeypatch.setitem(store.PLANS["free"], "saved_research", 2)
    assert save(client, two["mine"], {"kind": "company", "tickers": ["AAPL"]}).status_code == 200
    assert save(client, two["mine"], {"kind": "company", "tickers": ["MSFT"]}).status_code == 200
    full = save(client, two["mine"], {"kind": "company", "tickers": ["NVDA"]})
    assert full.status_code == 403 and "keeps 2 saved items" in full.json()["detail"]
    assert save(client, two["mine"], {"kind": "company", "tickers": ["AAPL"], "on_duplicate": "update"}).status_code == 200, "an update is not a new item"


def test_questions_saved_before_are_in_the_library_and_classic_sees_only_questions(two):
    q = client.post("/api/saved-research", headers=two["mine"], json={"title": "Is NVDA stretched?", "symbol": "NVDA",
                                                                       "content": "Is NVDA stretched?", "research_type": "pulse"}).json()["research"]
    save(client, two["mine"], {"kind": "company", "tickers": ["AAPL"]})
    lib = client.get("/api/library").json()
    kinds = {i["kind"]: i for i in lib["items"]}
    assert kinds["question"]["id"] == q["id"] and kinds["question"]["question"] == "Is NVDA stretched?" and kinds["question"]["tickers"] == ["NVDA"]
    assert lib["counts"]["question"] == 1 and len(client.get("/api/library?kind=question").json()["items"]) == 1
    legacy = client.get("/api/saved-research").json()["research"]
    assert [r["id"] for r in legacy] == [q["id"]], "Classic's list (questions to ask again) has no library items in it"
    assert client.delete("/api/library/{}".format(q["id"]), headers=two["mine"]).status_code == 200, "deleted from the library, gone from Classic's too"
    assert client.get("/api/saved-research").json()["research"] == []


def test_the_migration_keeps_what_was_saved_before(tmp_path, monkeypatch):
    """A database at migration 19 with a question saved in it: migration 20 adds the library's columns, and the
    question is still there, listed as a question."""
    from app import db
    every = list(db.MIGRATIONS)
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "old.db"))
    monkeypatch.setattr(db, "MIGRATIONS", [m for m in every if m[0] < 20])
    db.migrate()
    db.execute("INSERT INTO users (id, email, created_at, updated_at) VALUES ('u1', 'x@example.com', '2026-10-01', '2026-10-01')")
    db.execute("INSERT INTO saved_research (id, user_id, title, symbol, content, research_type, created_at, updated_at) "
               "VALUES ('r1', 'u1', 'Is AAPL cheap?', 'AAPL', 'Is AAPL cheap?', 'pulse', '2026-10-02', '2026-10-02')")
    monkeypatch.setattr(db, "MIGRATIONS", every)
    assert db.migrate() == [20] and 20 in db.applied()
    cols = {r["name"] for r in db.rows("PRAGMA table_info(saved_research)")}
    assert {"tickers", "ref", "summary", "payload", "item_key"} <= cols
    row = db.row("SELECT * FROM saved_research WHERE id = 'r1'")
    assert row["content"] == "Is AAPL cheap?" and row["item_key"] is None
    assert library._out(dict(row, preview=row["content"]))["kind"] == "question"


def test_nothing_is_saved_without_a_press():
    """No auto-saving: the only write to the library is core/library.js save(), called only from the Save control's
    press (ui/library.js attempt)."""
    hits = []
    for f in sorted(JS.rglob("*.js")):
        text = f.read_text()
        if "'/api/library'" in text and "api.post" in text and f.name != "library.js":
            hits.append(str(f.relative_to(ROOT)))
        if re.search(r"\blib\.save\(|\bsave\(body, opts\)", text) and f.name not in ("library.js",):
            hits.append(str(f.relative_to(ROOT)))
    assert hits == []
    ui = (JS / "ui/library.js").read_text()
    assert ui.count("lib.save(") == 1 and "async function attempt(b, spec, opts)" in ui


def test_the_library_loading_ends_in_a_retry_state(tmp_path):
    """The library's own load (pages/saved.js) ends like Home's panels: "Couldn't load your saved research." with
    Retry after 10 seconds, retried by itself 5, 15 and 45 seconds apart, then only on Retry."""
    got = _run(tmp_path, js("""
      const T = { now: Date.parse('2026-11-04T18:00:00Z'), q: [], id: 0, calls: 0 };
      Date.now = () => T.now;
      globalThis.setTimeout = (fn, ms = 0) => { const id = ++T.id; T.q.push({ id, at: T.now + (Number(ms) || 0), fn }); return id; };
      globalThis.clearTimeout = (id) => { T.q = T.q.filter((x) => x.id !== id); };
      const flush = async () => { for (let i = 0; i < 60; i++) await Promise.resolve(); };
      async function advance(ms) { const end = T.now + ms; for (;;) { await flush(); T.q.sort((a, b) => a.at - b.at || a.id - b.id); const n = T.q[0]; if (!n || n.at > end) break; T.q.shift(); T.now = n.at; n.fn(); } T.now = end; await flush(); }
      globalThis.AbortController = class { constructor() { const ls = []; this.signal = { aborted: false, reason: null, addEventListener: (t, f) => ls.push(f) }; this.ls = ls; } abort(r) { this.signal.aborted = true; this.signal.reason = r; this.ls.forEach((f) => f()); } };
      globalThis.CSS = { escape: (s) => String(s) }; globalThis.CustomEvent = class { constructor(t, o) { this.type = t; this.detail = o && o.detail; } };
      window.dispatchEvent = () => true; window.removeEventListener = () => {};
      let mode = 'hang';
      globalThis.fetch = (url, o = {}) => new Promise((res, rej) => { if (!String(url).startsWith('/api/library')) return res({ ok: true, status: 200, statusText: '', headers: { get: () => null }, text: async () => '{}' });
        T.calls++; if (o.signal) o.signal.addEventListener('abort', () => rej(new Error('aborted')));
        if (mode === 'fail') res({ ok: false, status: 500, statusText: '', headers: { get: () => null }, text: async () => JSON.stringify({ detail: 'Upstream failed' }) }); });
      const S = await import('@STORE@'); S.state.auth = 'user';
      const P = await import('@SAVED@');
      const bodyEl = { innerHTML: '', querySelectorAll: () => [], querySelector: () => null };
      const tools = { innerHTML: '' };
      const main = { innerHTML: '', addEventListener() {}, querySelector: (s) => (s === '#lib-body' ? bodyEl : s === '.lib-tools' ? tools : null), querySelectorAll: () => [] };
      await P.render(main, { params: {} });
      await advance(9000); const at9 = bodyEl.innerHTML;
      await advance(1500); const at10 = bodyEl.innerHTML;
      mode = 'fail'; T.calls = 0;
      await advance(25000);   // the request's own 20 s limit ends the hung one; it then fails at once each time
      await advance(5 * 60000);
      print(JSON.stringify({ at9, at10, calls: T.calls, end: bodyEl.innerHTML, wait: P.WAIT, backoff: P.BACKOFF }));
    """))
    assert got["wait"] == 10000 and got["backoff"] == [5000, 15000, 45000]
    assert "sk-wrap" in got["at9"]
    assert "Couldn't load your saved research." in got["at10"] and "has not answered in 10 seconds" in got["at10"] and "data-lib-retry" in got["at10"]
    assert got["calls"] == 3, "three automatic retries after the failure, then none"
    assert "Optic has stopped asking by itself." in got["end"] and "Retry</button>" in got["end"]


def test_the_library_page_and_save_controls_fit_a_phone():
    css = (V2 / "css/pages.css").read_text()
    block = css[css.index("/* Saved research, the library"):css.index(".sv-list, .sv-routes")]
    assert ".lib-item { flex-direction: column; }" in block and ".lib-acts .btn, .lib-kinds button { min-height: var(--tap); }" in block
    assert ".lib-search { flex-basis: 100%; max-width: none; }" in block
    comp = (V2 / "css/components.css").read_text()
    assert ".dhead .acts > .lib-save { flex: 1 1 0; min-width: 0; }" in comp, "Save sits in the phone header's one row, above the fold"
    assert '.btn[aria-pressed="true"] { background: var(--c-active);' in comp, "Saved is the active fill, never gold"
    page = (JS / "pages/saved.js").read_text()
    assert "Open a Dossier" in page and "href=\"#/dossier\"" in page, "the empty state explains and links to a Dossier"
    assert "not advice" in page


def test_the_save_buttons_sit_where_the_handoff_asks():
    frame = (JS / "pages/dossier-frame.js").read_text()
    assert "${watchButton(sym, { compact: sm })}${saveButton('company', keyOf('company', [sym]), { cls: s })}" in frame
    cmp_ = (JS / "pages/compare.js").read_text()
    assert "saveButton('comparison', keyOf('comparison', result.tickers), { cls: '', label: 'Save comparison' })" in cmp_
    milo = (JS / "ui/milo.js").read_text()
    assert "actions: html`${saveButton('conversation', keyOf('conversation', [], { conversation: S.conv.id }), { iconOnly: true, label: 'Save conversation' })}" in milo
    assert "provideSave('conversation', () => (S.busy ? { blocked:" in milo, "never mid-answer"
