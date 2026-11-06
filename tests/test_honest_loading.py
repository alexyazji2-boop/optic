"""Handoff 4 of the owner's handover pack (2026-11-03): honest loading and a single delay source.

The audit found Home panels left on "Loading" and quote delays that disagree: 15 minutes on the Dossier and in Milo, 20
on Brokerage. The acceptance tests:

1. Delay labels agree on charts, Dossier, brokerage quotes, and footers for the test set.
2. Killing a panel's data source produces a retry state within the timeout, not infinite loading.
3. Stale quotes carry a stale label; the market-closed state renders correctly.

Then the edge cases the handoff names: the delay record failing (the longest delay and a note, never "Live"), the
reader's timezone and changes to it, daylight saving by the zone's own rules, the extended sessions, no retry storms,
labels kept on phones, and a ratchet on hard-coded delay sentences.

The test set is the feed's own statements, measured on the local server at 1:46 PM ET on 2026-11-04: AAPL (Nasdaq,
15 minutes), BRK-B (NYSE, 20), SPY (NYSE Arca, none), ^VIX (Cboe, 15, its trade 15 minutes old), ES=F (CME, 10),
TCEHY (over the counter, 15) and a quote that states no delay.

JavaScriptCore waits for real timers and has no clearTimeout, setInterval or AbortController, so each script runs on a
virtual clock (CLOCK) against a stand-in fetch that counts every request.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app import delays as delays_mod
from tests.test_frontend_v2_stage0 import V2, _run

ROOT = Path(__file__).resolve().parents[1]
JS = V2 / "js"
MODS = {"DELAYS": "core/delays.js", "DOM": "core/dom.js", "PREFS": "core/prefs.js", "FRAME": "pages/dossier-frame.js",
        "BROKER": "pages/brokerage.js", "HOME": "pages/workspace.js", "STATUS": "core/status.js", "MT": "core/marketTime.js"}

CLOCK = """
  const T = { now: Date.parse('2026-11-04T18:46:32Z'), q: [], id: 0, calls: {} };
  Date.now = () => T.now;
  globalThis.setTimeout = (fn, ms = 0) => { const id = ++T.id; T.q.push({ id, at: T.now + Math.max(0, Number(ms) || 0), fn }); return id; };
  globalThis.clearTimeout = (id) => { T.q = T.q.filter((x) => x.id !== id); };
  globalThis.setInterval = (fn, ms) => { const id = ++T.id; const tick = () => { fn(); T.q.push({ id, at: T.now + ms, fn: tick }); }; T.q.push({ id, at: T.now + ms, fn: tick }); return id; };
  globalThis.clearInterval = globalThis.clearTimeout;
  const flush = async () => { for (let i = 0; i < 60; i++) await Promise.resolve(); };
  async function advance(ms) {
    const end = T.now + ms;
    for (;;) {
      await flush();
      T.q.sort((a, b) => a.at - b.at || a.id - b.id);
      const n = T.q[0];
      if (!n || n.at > end) break;
      T.q.shift(); T.now = n.at;
      try { n.fn(); } catch (e) { print('timer error ' + e); }
    }
    T.now = end; await flush();
  }
  globalThis.AbortController = class { constructor() { const ls = []; this._ls = ls; this.signal = { aborted: false, reason: null, addEventListener: (t, f) => ls.push(f) }; } abort(r) { if (this.signal.aborted) return; this.signal.aborted = true; this.signal.reason = r; this._ls.forEach((f) => f()); } };
  globalThis.CustomEvent = class { constructor(t, o) { this.type = t; this.detail = o && o.detail; } };
  window.dispatchEvent = () => true;
  // ROUTES[path](url) answers { status, body }, or 'hang' for a source that never answers
  const ROUTES = {};
  globalThis.fetch = (url, opts = {}) => new Promise((resolve, reject) => {
    const path = String(url).split('?')[0]; T.calls[path] = (T.calls[path] || 0) + 1;
    if (opts.signal) opts.signal.addEventListener('abort', () => reject(new Error('aborted')));
    const h = ROUTES[path], r = h ? h(url) : { status: 404, body: { detail: 'Not found' } };
    Promise.resolve(r).then((x) => { if (x === 'hang') return; resolve({ ok: x.status < 400, status: x.status, statusText: '', headers: { get: () => null }, text: async () => JSON.stringify(x.body) }); });
  });
  const RECORD = @RECORD@;
  ROUTES['/api/delays'] = () => ({ status: 200, body: RECORD });
  localStorage.setItem('optic.timezone', 'America/New_York');
  const at = (s) => new Date(T.now - s * 1000).toISOString();
  // the feed's statements for the test set, 2026-11-04 1:46 PM ET
  const SET = {
    AAPL: { price: 352.79, change_pct: 6.29, delayed_minutes: 15, trade_time: at(2), exchange: 'NasdaqGS', market_state: 'REGULAR' },
    'BRK-B': { price: 512.4, change_pct: 0.4, delayed_minutes: 20, trade_time: at(8), exchange: 'NYSE', market_state: 'REGULAR' },
    SPY: { price: 767.65, change_pct: 1.1, delayed_minutes: 0, trade_time: at(2), exchange: 'NYSEArca', market_state: 'REGULAR' },
    '^VIX': { price: 16.97, change_pct: -18.5, delayed_minutes: 15, trade_time: at(916), exchange: 'Cboe Indices', market_state: 'REGULAR' },
    'ES=F': { price: 7712.5, change_pct: 0.9, delayed_minutes: 10, trade_time: at(601), exchange: 'CME', market_state: 'REGULAR' },
    TCEHY: { price: 74.1, change_pct: 1.4, delayed_minutes: 15, trade_time: at(988), exchange: 'OTC Markets OTCPK', market_state: 'REGULAR' },
    ZZZQ: { price: 10.5, change_pct: 0.2, trade_time: at(30), exchange: 'NasdaqCM', market_state: 'REGULAR' },
  };
  const qlabel = (h) => { const m = /data-qlabel="[^"]*">([^<]*)</.exec(h); return m ? m[1] : null; };
  const qlist = (h) => { const m = /data-q(?:label|list)="[^"]*">([^<]*)</.exec(h); return m ? m[1] : null; };
  // a stand-in page for Home's panels: each element the loader asks for, made on demand
  function fakeRoot() {
    const els = {};
    const el = (k) => els[k] || (els[k] = { key: k, innerHTML: '', textContent: '', dataset: {}, hidden: false, scrollTop: 0, className: '',
      querySelector: () => null, querySelectorAll: () => [], focus() { this.focused = true; }, insertAdjacentHTML(w, h) { this.innerHTML += h; }, setAttribute() {}, classList: { add() {}, remove() {}, toggle() {} } });
    return { els, querySelector: (sel) => (/^#wsb-|^#wsf-|^#wsd-|^\\[data-ws-panel="[a-z]+"\\]$/.test(sel) ? el(sel) : null), querySelectorAll: () => [] };
  }
"""


def js(body: str) -> str:
    out = CLOCK.replace("@RECORD@", json.dumps(delays_mod.public())) + body
    for k, v in MODS.items():
        out = out.replace("@{}@".format(k), (JS / v).as_posix())
    return out


EXPECTED = {
    "AAPL": "Delayed 15 min · as of 1:46 PM EST",
    "BRK-B": "Delayed 20 min (NYSE) · as of 1:46 PM EST",
    "SPY": "Live · as of 1:46 PM EST",
    "^VIX": "Delayed 15 min · as of 1:31 PM EST",
    "ES=F": "Delayed 10 min (CME) · as of 1:36 PM EST",
    "TCEHY": "Delayed 15 min · as of 1:30 PM EST",
    "ZZZQ": "Delayed up to 20 min · as of 1:46 PM EST",
}


# ------------------------------------------------------------------ acceptance 1: one delay, everywhere

def test_acceptance_1_delay_labels_agree_on_chart_dossier_brokerage_and_footers(tmp_path):
    got = _run(tmp_path, js("""
      const D = await import('@DELAYS@'), { toString } = await import('@DOM@');
      await D.load();
      const F = await import('@FRAME@'), B = await import('@BROKER@'), W = await import('@HOME@');
      const root = fakeRoot(), S = W._test.mount(root);
      const out = {};
      for (const [sym, q] of Object.entries(SET)) {
        const page = { sym, quote: q, session: { prices: { phase: 'regular' }, session: { is_regular: true, phase: 'regular', last_close: { date: '2026-11-03' } } } };
        const chart = qlabel(toString(F.header(sym, page, 'chart', { bar: true })));
        const dossier = qlabel(toString(F.header(sym, page, 'overview', { bar: true })));
        const broker = qlabel(toString(B._test.holdings({ holdings: [{ symbol: sym, quantity: 2, price: q.price, market_value: q.price * 2, currency: 'USD', accounts: ['Main'] }],
          quotes: { [sym]: Object.assign({ session: 'regular', source: 'Yahoo Finance' }, q) } })));
        // Home's Quote panel, linked to the symbol: its footer's label, from the panel's own quote
        S.link = sym;
        ROUTES['/api/quote/' + encodeURIComponent(sym)] = () => ({ status: 200, body: { available: true, quote: Object.assign({ name: sym }, q) } });
        ROUTES['/api/take-chart/' + encodeURIComponent(sym)] = () => ({ status: 200, body: { available: false } });
        W._test.loadPanel('quote', { force: true }); await advance(0);
        const foot = qlist(root.els['#wsf-quote'].innerHTML);
        out[sym] = { chart, dossier, broker, foot };
      }
      // the page footer's status line and Milo's panel say the feed's longest, by exchange
      out.sentence = D.quotesSentence();
      // a footer over several of them: their range, and the oldest trade's time
      out.range = D.listLabel([SET.AAPL, SET['BRK-B'], SET.SPY], { phase: 'regular' }).text;
      out.brokerPill = toString(B._test.quotesTag({}, { AAPL: SET.AAPL, 'BRK-B': SET['BRK-B'] }));
      print(JSON.stringify(out));
    """))
    for sym, want in EXPECTED.items():
        row = got[sym]
        assert row == {"chart": want, "dossier": want, "broker": want, "foot": want}, (sym, row)
    # the general statement covers every label: the longest any exchange in the feed states, said by exchange
    assert got["sentence"] == delays_mod.quote_sentence()
    assert "up to {} minutes".format(delays_mod.LONGEST_MINUTES) in got["sentence"] and "by exchange" in got["sentence"]
    assert max(int(m) for m in re.findall(r"Delayed (?:up to )?(\d+) min", " ".join(EXPECTED.values()))) <= delays_mod.LONGEST_MINUTES
    assert got["range"] == "Delayed 0 to 20 min by exchange · as of 1:46 PM EST"
    # Brokerage's pill: the range of its holdings' delays, not the longest alone (20 beside the Dossier's 15)
    assert "Delayed 15 to 20 min by exchange · as of 1:46 PM EST" in got["brokerPill"]


def test_the_page_footer_states_the_record_and_settings_and_milo_use_the_same_words(tmp_path):
    got = _run(tmp_path, js("""
      const els = {};
      document.querySelector = (sel) => (sel === '#app-status' || sel === '#session-chip' ? (els[sel] || (els[sel] = { innerHTML: '', title: '', querySelectorAll: () => [] })) : null);
      ROUTES['/api/health'] = () => ({ status: 200, body: { status: 'ok', provider: 'yfinance', realtime_chain: false, assistant: { enabled: true } } });
      ROUTES['/api/session'] = () => ({ status: 200, body: { phase: 'regular', label: 'Regular session', is_regular: true } });
      ROUTES['/api/ai-allowance'] = () => ({ status: 200, body: { allowance: {} } });
      const St = await import('@STATUS@');
      St.watchStatus(); await advance(1000);
      print(JSON.stringify({ footer: els['#app-status'].innerHTML }));
    """))
    assert got["footer"].startswith("From Yahoo Finance. " + delays_mod.quote_sentence())
    for path in ("static/v2/js/pages/settings.js", "static/v2/js/ui/milo.js", "static/v2/js/core/status.js"):
        src = (ROOT / path).read_text()
        assert "delays.quotesSentence()" in src, path


def test_the_server_reads_the_same_record():
    from fastapi.testclient import TestClient
    from app import ai, legal, milo_tools
    from app.main import app
    r = TestClient(app).get("/api/delays")
    assert r.status_code == 200
    d = r.json()
    assert d["longest_minutes"] == delays_mod.LONGEST_MINUTES == 20 and d["usual_minutes"] == 15
    assert d["footer"] == delays_mod.quote_sentence()
    assert d["exchanges"]["NYSE"] == "NYSE" and d["sources"]["quotes"]["by_exchange"]["NYSE"] == 20
    assert set(d["sources"]) == {"quotes", "options", "brokerage", "fundamentals", "news"}, "each source the handoff names"
    # the client's fallback is the server's numbers (core/delays.js FALLBACK)
    fb = re.search(r"FALLBACK = Object\.freeze\(\{ longest_minutes: (\d+), usual_minutes: (\d+), stale_after_minutes: (\d+), chain_minutes: (\d+)",
                   (JS / "core/delays.js").read_text())
    assert fb and [int(x) for x in fb.groups()] == [d["longest_minutes"], d["usual_minutes"], d["stale_after_minutes"], d["chain_minutes"]]
    # the server's own sentences: the legal notice's label, Milo's prompt, context line and tool note
    up_to = delays_mod.quotes_up_to()
    assert legal.LABELS["delayed"] == delays_mod.quote_label() and up_to in legal.LABELS["delayed"]
    assert "delayed {} during the session, by exchange".format(up_to) in " ".join(ai.SYSTEM_PROMPT.split())
    assert up_to in milo_tools.DELAY_NOTE
    assert "quotes are delayed {} by exchange".format(up_to) in ai.context_header({})


def test_brokerage_sends_the_range_of_its_quotes_delays_not_the_longest_alone():
    from app.brokerage import workspace
    quotes = {"AAPL": {"price": 352.8, "as_of": "2026-11-04T18:46:30Z", "delayed_minutes": 15},
              "BRK-B": {"price": 512.4, "as_of": "2026-11-04T18:46:24Z", "delayed_minutes": 20},
              "ZZZQ": {"price": 10.5, "as_of": "2026-11-04T18:46:02Z", "delayed_minutes": None}}
    m = workspace._freshness({"as_of": {}}, quotes)["market"]
    assert m["delay_range"] == [15, 20] and m["delay_unstated"] == 1
    assert m["delayed_minutes"] == 20, "the longest stays for the classic reader of this field"
    src = (ROOT / "app/brokerage/workspace.py").read_text()
    for k in ('"trade_time"', '"exchange"', '"session"', '"market_state"'):
        assert k in src[src.index('"quotes": {s: {k: q.get(k)'):][:400], k


# ------------------------------------------------------------------ acceptance 2: loading always ends

def test_acceptance_2_a_killed_source_gives_a_retry_state_within_the_timeout(tmp_path):
    """The Indices panel's source never answers; the Movers panel's does. After ten seconds the Indices panel says it
    could not load and offers Retry; Movers was never held up by it."""
    got = _run(tmp_path, js("""
      const W = await import('@HOME@');
      const root = fakeRoot(); W._test.mount(root);
      ROUTES['/api/home'] = () => 'hang';
      ROUTES['/api/scanners/movers'] = () => ({ status: 200, body: { available: false, reason: 'The movers scan has not run yet today.' } });
      W._test.loadPanel('indices', { force: true }); W._test.loadPanel('movers', { force: true });
      await advance(1000);
      const early = { indices: root.els['#wsb-indices'].innerHTML, movers: root.els['#wsb-movers'].innerHTML };
      await advance(W.PANEL_WAIT - 1001);
      const before = root.els['#wsb-indices'].innerHTML;
      await advance(1);
      const after = root.els['#wsb-indices'].innerHTML;
      print(JSON.stringify({ early, before, after, wait: W.PANEL_WAIT }));
    """))
    assert got["wait"] == 10000
    assert "sk-wrap" in got["early"]["indices"], "the skeleton while it waits"
    assert "movers scan has not run yet today" in got["early"]["movers"], "the other panel drew at once"
    assert "sk-wrap" in got["before"] and "Couldn't load" not in got["before"]
    a = got["after"]
    assert "Couldn't load Markets at a glance." in a and "has not answered in 10 seconds" in a, a
    assert '<button type="button" class="btn btn-sm" data-ws-reload="indices">Retry</button>' in a, "a real button: the keyboard reaches it"
    assert 'role="alert"' in a and "sk-wrap" not in a


def test_a_late_answer_replaces_the_retry_state(tmp_path):
    got = _run(tmp_path, js("""
      const W = await import('@HOME@');
      const root = fakeRoot(); W._test.mount(root);
      ROUTES['/api/scanners/movers'] = () => new Promise((r) => setTimeout(() => r({ status: 200, body: { available: false, reason: 'Ranking not built yet.' } }), 12000));
      W._test.loadPanel('movers', { force: true });
      await advance(10500); const late = root.els['#wsb-movers'].innerHTML;
      await advance(2000); const landed = root.els['#wsb-movers'].innerHTML;
      print(JSON.stringify({ late, landed, calls: T.calls['/api/scanners/movers'] }));
    """))
    assert "Couldn't load Movers" in got["late"] or "Couldn't load" in got["late"]
    assert "Ranking not built yet." in got["landed"] and "Couldn't load" not in got["landed"]
    assert got["calls"] == 1, "waiting asked nothing more of the source"


def test_failures_retry_with_backoff_three_times_then_only_on_retry(tmp_path):
    """A source answering 500 is asked again 5, 15 and 45 seconds apart, then left alone: four requests in about a
    minute, then none until the reader presses Retry, which asks once."""
    got = _run(tmp_path, js("""
      const W = await import('@HOME@');
      const root = fakeRoot(); W._test.mount(root);
      ROUTES['/api/scanners/movers'] = () => ({ status: 500, body: { detail: 'Upstream failed' } });
      W._test.loadPanel('movers', { force: true });
      const seen = [];
      for (const t of [0, 4900, 100, 14900, 100, 44900, 100]) { await advance(t); seen.push(T.calls['/api/scanners/movers'] || 0); }
      const shown = root.els['#wsb-movers'].innerHTML;
      await advance(30 * 60000); const later = T.calls['/api/scanners/movers'];
      W._test.loadPanel('movers', { force: true }); await advance(0); const pressed = T.calls['/api/scanners/movers'];
      await advance(30 * 60000); const after = T.calls['/api/scanners/movers'];
      print(JSON.stringify({ seen, shown, later, pressed, after, backoff: W.BACKOFF }));
    """))
    assert got["backoff"] == [5000, 15000, 45000]
    assert got["seen"] == [1, 1, 2, 2, 3, 3, 4], "first ask, then 5 s, 15 s and 45 s later"
    assert "Couldn't load" in got["shown"] and "Optic has stopped asking by itself." in got["shown"] and "Retry</button>" in got["shown"]
    assert got["later"] == 4, "no fourth automatic retry, however long the page stays open"
    assert got["pressed"] == 5 and got["after"] == 5, "Retry asks once; it does not restart the automatic ones"


def test_a_retry_joins_a_request_still_in_flight(tmp_path):
    """No storm from a slow source: the reader's Retry while the first request is pending sends nothing new."""
    got = _run(tmp_path, js("""
      const W = await import('@HOME@');
      const root = fakeRoot(); W._test.mount(root);
      ROUTES['/api/brief'] = () => 'hang';
      W._test.loadPanel('news', { force: true }); await advance(11000);
      W._test.loadPanel('news', { force: true }); await advance(100);
      W._test.loadPanel('news', { force: true }); await advance(100);
      print(JSON.stringify({ calls: T.calls['/api/brief'] }));
    """))
    assert got["calls"] == 1


def test_a_building_board_is_polled_a_bounded_number_of_times(tmp_path):
    got = _run(tmp_path, js("""
      const W = await import('@HOME@');
      const root = fakeRoot(); W._test.mount(root);
      ROUTES['/api/scanners/movers'] = () => ({ status: 200, body: { available: false, building: { done: 3, total: 500 } } });
      W._test.loadPanel('movers', { force: true });
      await advance(60 * 60000);
      print(JSON.stringify({ calls: T.calls['/api/scanners/movers'], foot: root.els['#wsf-movers'].innerHTML, polls: W.BUILD_POLLS }));
    """))
    assert got["calls"] == 1 + got["polls"], "re-read while it builds, then no more"
    assert "Still building: Refresh to check" in got["foot"]


def test_the_home_refresh_skips_failed_panels_and_the_loader_has_no_endless_paths():
    src = (JS / "pages/workspace.js").read_text()
    assert "MARKET_PANELS.includes(x.id) && DATA[x.id] !== undefined" in src, "the 20 s refresh never re-asks a failed panel"
    assert "Still loading" not in src and "RETRIED" not in src, "the one quiet retry that kept a skeleton up is gone"
    assert "if (POLLS[id] <= BUILD_POLLS) setTimeout(" in src


# ------------------------------------------------------------------ acceptance 3: stale and closed

def test_acceptance_3_stale_quotes_carry_a_stale_label_and_a_closed_market_says_so(tmp_path):
    got = _run(tmp_path, js("""
      const D = await import('@DELAYS@'), { toString } = await import('@DOM@');
      await D.load();
      const F = await import('@FRAME@'), B = await import('@BROKER@');
      const old = Object.assign({}, SET.AAPL, { trade_time: at(50 * 60) });          // 50 minutes, past 15 + 30
      const edge = Object.assign({}, SET.AAPL, { trade_time: at(44 * 60) });         // 44 minutes: still delayed
      const regular = { prices: { phase: 'regular' }, session: { is_regular: true, phase: 'regular', last_close: { date: '2026-11-03' } } };
      const shut = { prices: { phase: 'closed' }, session: { is_regular: false, phase: 'closed', last_close: { date: '2026-11-03' } } };
      const holiday = { prices: { phase: 'holiday' }, session: { phase: 'holiday', last_close: { date: '2026-11-25' } } };
      const pre = { prices: { phase: 'pre' }, session: { phase: 'pre', last_close: { date: '2026-11-03' } } };
      const preExt = { prices: { phase: 'pre', extended: { kind: 'pre-market', price: 354.1, change_pct: 0.4, as_of: '2026-11-04T12:59:00Z' } }, session: { phase: 'pre', last_close: { date: '2026-11-03' } } };
      const head = (q, s) => toString(F.header('AAPL', { sym: 'AAPL', quote: q, session: s }, 'overview', { bar: true }));
      print(JSON.stringify({
        stale: qlabel(head(old, regular)), edge: qlabel(head(edge, regular)),
        staleBroker: qlabel(toString(B._test.holdings({ holdings: [{ symbol: 'AAPL', quantity: 1, price: 350, market_value: 350, currency: 'USD' }], quotes: { AAPL: Object.assign({ session: 'regular' }, old) } }))),
        staleList: D.listLabel([old, SET['BRK-B']], { phase: 'regular' }).text, allStale: D.listLabel([old], { phase: 'regular' }).text,
        liveStale: D.quoteLabel(Object.assign({}, SET.SPY, { trade_time: at(31 * 60) }), { phase: 'regular' }).text,
        closed: qlabel(head(SET.AAPL, shut)), holiday: qlabel(head(SET.AAPL, holiday)),
        pre: qlabel(head(SET.AAPL, pre)), preExt: head(SET.AAPL, preExt), closedList: D.listLabel([SET.AAPL, SET['BRK-B']], { phase: 'closed', lastClose: '2026-11-03' }).text,
        weekend: D.quoteLabel(Object.assign({}, SET.AAPL, { trade_time: '2026-10-30T20:00:00Z', market_state: 'CLOSED' }), {}).text,
        printBroker: D.quoteLabel({ price: 354.1, session: 'pre', trade_time: '2026-11-04T12:59:00Z' }, { phase: 'pre' }).text,
      }));
    """))
    assert got["stale"] == "Stale · as of 12:56 PM EST", "an old price is never shown as current"
    assert got["edge"] == "Delayed 15 min · as of 1:02 PM EST"
    assert got["staleBroker"] == got["stale"], "the same words on Brokerage"
    assert got["staleList"] == "Delayed 20 min (NYSE) · as of 1:46 PM EST · 1 stale" and got["allStale"] == "Stale · as of 12:56 PM EST"
    assert got["liveStale"] == "Stale · as of 1:15 PM EST", "a price stating no delay is stale past the tolerance too"
    assert got["closed"] == "Market closed · last close Tue Nov 3", "not a delay that implies intraday staleness"
    assert got["holiday"] == "Market closed · last close Wed Nov 25"
    assert got["closedList"] == "Market closed · last close Tue Nov 3"
    assert got["weekend"] == "Market closed · last close", "the quote's own state, when no session read answered"
    assert got["pre"] == "Pre-market · regular session only · last close Tue Nov 3", "the data holds no pre-market print"
    assert "Pre-market · last close Tue Nov 3" in got["preExt"] and "· as of 7:59 AM EST" in got["preExt"], "a print of the session, labelled"
    assert got["printBroker"] == "Pre-market print · as of 7:59 AM EST"


def test_labels_age_in_place_as_the_clock_moves(tmp_path):
    """A label drawn "Live" says "As of" once its trade is two minutes old, and a delayed one says Stale past the
    tolerance, without the page being redrawn (core/delays.js relabel, every 30 s)."""
    got = _run(tmp_path, js("""
      const D = await import('@DELAYS@'), { toString } = await import('@DOM@');
      await D.load();
      const parse = (h) => { const m = /data-qlabel="([^"]*)">([^<]*)</.exec(h); return { data: m[1].replace(/&quot;/g, '"').replace(/&amp;/g, '&'), text: m[2] }; };
      const make = (h) => { const p = parse(h); return { dataset: { qlabel: p.data }, textContent: p.text, className: 'qlabel is-live' }; };
      const live = make(toString(D.label(SET.SPY, { phase: 'regular' }))), slow = make(toString(D.label(SET.AAPL, { phase: 'regular' })));
      document.querySelectorAll = (sel) => (sel === '[data-qlabel]' ? [live, slow] : []);
      D.watch();
      const t0 = [live.textContent, slow.textContent];
      await advance(3 * 60000); const t3 = [live.textContent, slow.textContent, live.className];
      await advance(43 * 60000); const t46 = [live.textContent, slow.textContent, slow.className];
      print(JSON.stringify({ t0, t3, t46 }));
    """))
    assert got["t0"] == ["Live · as of 1:46 PM EST", "Delayed 15 min · as of 1:46 PM EST"]
    assert got["t3"][0] == "As of 1:46 PM EST" and got["t3"][2] == "qlabel is-asof", "two minutes on: not live"
    assert got["t46"][1] == "Stale · as of 1:46 PM EST" and got["t46"][2] == "qlabel is-stale"


# ------------------------------------------------------------------ the delay record failing

def test_without_the_record_every_label_takes_the_longest_delay_and_says_so_never_live(tmp_path):
    got = _run(tmp_path, js("""
      ROUTES['/api/delays'] = () => ({ status: 503, body: { detail: 'down' } });
      const D = await import('@DELAYS@');
      await D.load();
      const out = {};
      for (const [k, q] of Object.entries(SET)) out[k] = D.quoteLabel(q, { phase: 'regular' }).text;
      out.list = D.listLabel([SET.SPY, SET.AAPL], { phase: 'regular' }).text;
      out.general = D.generalLabel({ phase: 'regular' }).text;
      out.sentence = D.quotesSentence();
      const first = T.calls['/api/delays'];
      await D.load(); const again = T.calls['/api/delays'];
      await advance(61000); await D.load(); const later = T.calls['/api/delays'];
      out.calls = [first, again, later];
      out.after = D.quoteLabel(SET.SPY, { phase: 'regular' }).text;
      print(JSON.stringify(out));
    """))
    for k in ("AAPL", "BRK-B", "SPY", "ZZZQ"):
        assert got[k].startswith("Delayed up to 20 min · as of ") and got[k].endswith("· delay info unavailable"), (k, got[k])
    assert "Live" not in json.dumps(got), "never live without the record"
    assert got["list"] == "Delayed up to 20 min · as of 1:46 PM EST · delay info unavailable"
    assert got["general"] == "Delayed up to 20 min · delay info unavailable"
    assert got["sentence"].endswith("(delay info unavailable).")
    assert got["calls"] == [1, 1, 2], "asked again only after a minute, at the next page shown"


# ------------------------------------------------------------------ the reader's timezone

def test_labels_use_the_readers_timezone_and_follow_a_change(tmp_path):
    got = _run(tmp_path, js("""
      const D = await import('@DELAYS@'), P = await import('@PREFS@'), { toString } = await import('@DOM@');
      await D.load();
      const make = (h) => { const m = /data-qlabel="([^"]*)">([^<]*)</.exec(h); return { dataset: { qlabel: m[1].replace(/&quot;/g, '"') }, textContent: m[2], className: 'qlabel is-delayed' }; };
      const el = make(toString(D.label(SET.AAPL, { phase: 'regular' })));
      document.querySelectorAll = (sel) => (sel === '[data-qlabel]' ? [el] : []);
      D.watch();
      const ny = el.textContent;
      P.setTimezone('America/Los_Angeles'); const la = el.textContent;
      P.setTimezone('Asia/Tokyo'); const tokyo = el.textContent;
      P.setTimezone('Europe/London'); const london = el.textContent;
      // the clocks went back in New York on Sunday 2026-11-01: each side keeps its own abbreviation
      P.setTimezone('America/New_York');
      const before = D.quoteLabel({ delayed_minutes: 15, trade_time: '2026-10-30T17:00:00Z' }, { now: Date.parse('2026-10-30T17:01:00Z') }).text;
      const after = D.quoteLabel({ delayed_minutes: 15, trade_time: '2026-11-02T17:00:00Z' }, { now: Date.parse('2026-11-02T17:01:00Z') }).text;
      const dayOld = D.quoteLabel({ delayed_minutes: 15, trade_time: '2026-11-03T20:59:00Z' }, {}).text;
      print(JSON.stringify({ ny, la, tokyo, london, before, after, dayOld }));
    """))
    assert got["ny"] == "Delayed 15 min · as of 1:46 PM EST"
    assert got["la"] == "Delayed 15 min · as of 10:46 AM PST"
    assert got["tokyo"] == "Delayed 15 min · as of 3:46 AM GMT+9", "Tokyo's own clock and abbreviation"
    assert got["london"] == "Delayed 15 min · as of 6:46 PM GMT"
    assert got["before"] == "Delayed 15 min · as of 1:00 PM EDT" and got["after"] == "Delayed 15 min · as of 12:00 PM EST"
    assert got["dayOld"] == "Delayed 15 min · as of Nov 3, 3:59 PM EST", "no session given: no stale claim, the date said"
    src = (JS / "core/delays.js").read_text()
    assert "getTimezoneOffset" not in src and "* 3600000" not in src.split("export function clockText")[1].split("\n}\n")[0], "no manual offsets"


# ------------------------------------------------------------------ phones, and the ratchet

def test_delay_labels_stay_visible_on_phones():
    css = "\n".join((V2 / "css" / f).read_text() for f in ("components.css", "pages.css"))
    for sel in (".qlabel", ".qrow", ".dh-ext", ".ws-state", ".bk-fresh"):
        for m in re.finditer(r"[^{}]*\{[^}]*\}", css):
            rule = m.group(0)
            if sel in rule.split("{")[0] and re.search(r"display:\s*none|visibility:\s*hidden", rule):
                pytest.fail("{} is hidden by: {}".format(sel, rule.strip()[:160]))
    assert ".ws-foot { margin-top: auto; display: flex; flex-wrap: wrap;" in css, "a long label wraps rather than being clipped"
    assert ".ws-foot .ws-state { color: var(--c-ink-2); white-space: normal; min-width: 0; }" in css


# A sentence that puts a number of minutes on a quote's delay. Only app/delays.py and core/delays.js may: every other
# surface reads them (Handoff 4). Classic takes security fixes only and keeps its own words.
DELAY_NUMBER = re.compile(r"(?i)(?:delay(?:ed)?|behind|late)\b[^.;:\n`'\"]{0,24}?\b(?:about |up to |~)?(?:10|15|20)\s*(?:min\b|minutes?\b)"
                          r"|\b(?:10|15|20)[- ]?(?:min\b|minutes?\b)[^.;\n`'\"]{0,12}\b(?:delay(?:ed)?|behind)\b")


@pytest.mark.parametrize("folder, pattern", [("static/v2/js", "*.js"), ("app", "*.py")])
def test_no_surface_hard_codes_a_quote_delay(folder, pattern):
    found = []
    for f in sorted((ROOT / folder).rglob(pattern)):
        if f.name in ("delays.py", "delays.js"):
            continue
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            # a comment records what was measured or decided; only what a reader or Milo is shown is held here
            if re.match(r"\s*(#|//|\*|/\*)", line):
                continue
            if DELAY_NUMBER.search(line):
                found.append("{}:{}: {}".format(f.relative_to(ROOT), n, line.strip()[:140]))
    assert not found, found


def test_the_markets_strip_carries_each_rows_stated_delay_and_trade_time():
    """Home's Markets tiles were priced from a quote read that carries neither: their footer would have said the time
    Optic asked. Each row now carries the feed's own trade time and stated delay, read in one batch."""
    from app.analytics import series_stats

    class Feed:
        def session_quotes(self, syms):
            return {"^VIX": {"regular_market_time": "2026-11-04T18:31:16+00:00", "delayed_minutes": 15.0, "exchange": "Cboe Indices"},
                    "CL=F": {"regular_market_time": "2026-11-04T18:36:13+00:00", "delayed_minutes": 10.0, "exchange": "NY Mercantile"}}

    class Down:
        def session_quotes(self, syms):
            raise RuntimeError("feed down")

    got = series_stats.stated_times(Feed(), ["^VIX", "CL=F", "GC=F"])
    assert got == {"^VIX": {"trade_time": "2026-11-04T18:31:16+00:00", "delayed_minutes": 15.0, "exchange": "Cboe Indices"},
                   "CL=F": {"trade_time": "2026-11-04T18:36:13+00:00", "delayed_minutes": 10.0, "exchange": "NY Mercantile"}}
    assert series_stats.stated_times(Down(), ["^VIX"]) == {} and series_stats.stated_times(object(), ["^VIX"]) == {}
    assert "snap.update(stated.get(str(item[\"symbol\"]).upper()) or {})" in (ROOT / "app/analytics/macro.py").read_text()
    home = (JS / "pages/workspace.js").read_text()
    assert "quotes: STRIP.map(([g, l]) => inst(d, g, l)).filter((i) => i && isNum(i.last)).map((i) => ({ delayed_minutes: i.delayed_minutes, trade_time: i.trade_time, exchange: i.exchange }))" in home
    assert delays_mod.EXCHANGE_NAMES["NY Mercantile"] == "NYMEX"
