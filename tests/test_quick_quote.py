"""The price first, ahead of the full analysis.

Asked for as "make the first load faster, show the price first". A symbol's
first /api/ticker was 7.0s (SOFI), 10.4s (MARA) and 11.5s (PATH) on the live
site after its fetches were made parallel, and the Dossier's header strip said
nothing but the symbol for all of it. The strip needs one quote, which is the
first thing the build fetches and is cached for thirty seconds, so the page now
asks /api/quote/{ticker} alongside the full load and repaints the strip with
the price when that lands.

What must not happen: one symbol's price under another's name, or a quick
quote outliving the load it stood in for and opening a later visit with a
price hours old.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.providers import yf as Y

ROOT = Path(__file__).resolve().parent.parent
RAW = (ROOT / "static/app.js").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


# ------------------------------------------------------------ the route


def test_the_route_answers_the_providers_quote(monkeypatch):
    asked = []

    def quote(sym):
        asked.append(sym)
        return {"ticker": sym, "name": "Robinhood Markets", "price": 41.2, "change_pct": 2.5}

    monkeypatch.setattr(main.PROVIDER, "quote", quote)
    body = TestClient(main.app).get("/api/quote/hood").json()
    assert asked == ["HOOD"], "upper-cased, and asked once"
    assert body == {"ticker": "HOOD", "available": True,
                    "quote": {"ticker": "HOOD", "name": "Robinhood Markets",
                              "price": 41.2, "change_pct": 2.5}}


def test_a_failed_quote_is_unavailable_and_does_not_say_why_to_the_reader(monkeypatch):
    def quote(sym):
        raise RuntimeError("upstream said 429 at /v7/finance/quote?crumb=abc123")

    monkeypatch.setattr(main.PROVIDER, "quote", quote)
    res = TestClient(main.app).get("/api/quote/HOOD")
    assert res.status_code == 200, "best effort: the full load reports failures"
    assert res.json() == {"ticker": "HOOD", "available": False}
    assert "crumb" not in res.text


def test_a_quote_without_a_price_is_unavailable(monkeypatch):
    monkeypatch.setattr(main.PROVIDER, "quote",
                        lambda sym: {"ticker": sym, "name": "Nothing", "price": None})
    assert TestClient(main.app).get("/api/quote/ZZZZ").json() == {"ticker": "ZZZZ",
                                                                 "available": False}


class _Stop(Exception):
    pass


def test_the_build_starts_with_the_same_call(monkeypatch):
    # If the build fetched its quote some other way, asking for the price
    # first would be a second Yahoo call per load rather than a free one.
    started = {}

    class Legs:
        def __init__(self, parallel, timings=None):
            self.parallel = parallel

        def start(self, name, fn, *args, **kwargs):
            started[name] = (fn, args)

        def get(self, name):
            raise _Stop()

    monkeypatch.setattr(main, "_Legs", Legs)
    with pytest.raises(_Stop):
        main._swing_snapshot("hood", None, 4, True, parallel=True)
    assert started["quote"] == (main.PROVIDER.quote, ("HOOD",))


def test_asked_first_the_builds_quote_is_a_cache_hit(monkeypatch):
    reads = []

    class Ticker:
        def __init__(self, symbol):
            self.symbol = symbol

        @property
        def info(self):
            reads.append(self.symbol)
            return {"regularMarketPrice": 41.2, "longName": "Robinhood Markets"}

    monkeypatch.setattr(Y, "_CACHE", {})
    monkeypatch.setattr(Y.yf, "Ticker", Ticker)
    monkeypatch.setattr(main, "PROVIDER", Y.YFinanceProvider())
    body = TestClient(main.app).get("/api/quote/HOOD").json()
    assert body["quote"]["price"] == 41.2
    assert main.PROVIDER.quote("HOOD")["price"] == 41.2      # the build's leg
    assert reads == ["HOOD"], "fetched twice: %r" % reads


# ------------------------------------------------------------ the page


def _raw_fn(name):
    return re.search(r"^(?:async )?function " + name + r"\([^\n]*\) \{.*?^\}",
                     RAW, re.M | re.S).group()


def _js(prelude, names, scenario):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = ("function assert(v, m) { if (!v) throw new Error(m); }\n" + prelude + "\n"
           + "\n".join(_raw_fn(n) for n in names)
           + "\n(async function () {\n" + scenario + "\n})().then(function () { print('TEST_OK'); },"
           " function (e) { print('FAIL ' + e + '\\n' + e.stack); });")
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=30)
    assert "TEST_OK" in out.stdout, out.stdout + out.stderr


HEADER = r"""
var SECURITY_VIEWS = ['overview', 'news'];
// The strip asks which facets a symbol has; a fund's has no Financials
// (tests/test_chart_arrival_rail_funds.py). Every symbol here has them all.
function securityViewsFor(sym) { return SECURITY_VIEWS; }
var SUB_TITLES = {}, SUB_LABELS = { overview: 'Overview', news: 'News' };
function esc(s) { return String(s); }
function fmt(v, d) { return Number(v).toFixed(d); }
function queueMicrotask() {}
var STATE = { ticker: 'HOOD', swing: null, quickQuote: null };
function priceIn(html) { var m = /sec-px">([^<]*)</.exec(html); return m ? m[1] : null; }
// The header's own satellites, driven by tests/test_ux_system.py; stubbed so
// this harness measures which price the header picks and nothing else.
function secDataStateHTML() { return ''; }
function secActionsHTML() { return ''; }
"""


def test_the_header_takes_the_quick_price_while_the_full_one_is_on_its_way():
    _js(HEADER, ["securityHeader"], """
      assert(priceIn(securityHeader('news')) === null, 'nothing yet, nothing shown');
      STATE.quickQuote = { ticker: 'HOOD', quote: { name: 'Robinhood', price: 41.2, change_pct: 2.5 } };
      var html = securityHeader('news');
      assert(priceIn(html) === '41.20', 'the quick price: ' + html);
      assert(html.indexOf('+2.50%') >= 0 && html.indexOf('Robinhood') >= 0, 'with its change and name');
      STATE.swing = { ticker: 'HOOD', quote: { price: 41.35, change_pct: 2.9 } };
      assert(priceIn(securityHeader('news')) === '41.35', 'the full payload wins once it lands');
    """)


def test_a_full_payload_without_a_price_does_not_erase_the_quick_one():
    """Measured on NVDA after hours: the full load landed with `price: null`
    because one Yahoo leg came back empty. Preferring the full quote whole
    dropped the quick quote's price (and its name and change) for nothing,
    until the session payload's close arrived to stand in. The merge is field
    by field, so a blank field defers and a filled one wins."""
    _js(HEADER, ["securityHeader"], """
      STATE.quickQuote = { ticker: 'HOOD', quote: { name: 'Robinhood', price: 41.2, change_pct: 2.5 } };
      STATE.swing = { ticker: 'HOOD', quote: { price: null, change_pct: null, exchange: 'NMS' } };
      var html = securityHeader('news');
      assert(priceIn(html) === '41.20', 'the quick price survives a blank one: ' + html);
      assert(html.indexOf('+2.50%') >= 0, 'and so does its change');
      assert(html.indexOf('Robinhood') >= 0, 'and its name');
      assert(html.indexOf('NMS') >= 0, 'while the full payload still adds what it has');
    """)


def test_the_header_never_lends_one_symbols_price_to_another():
    _js(HEADER, ["securityHeader"], """
      // The previous name's payload is still held while this one loads.
      STATE.swing = { ticker: 'NKE', quote: { price: 71.1, change_pct: -1 } };
      assert(priceIn(securityHeader('news')) === null, "NKE's price under HOOD");
      STATE.quickQuote = { ticker: 'NKE', quote: { price: 71.1 } };
      assert(priceIn(securityHeader('news')) === null, "NKE's quick price under HOOD");
      STATE.quickQuote = { ticker: 'HOOD', quote: { price: 41.2 } };
      assert(priceIn(securityHeader('news')) === '41.20', 'its own');
      // Charting names its own symbol, and nothing here is its price.
      assert(priceIn(securityHeader('news', { symbol: 'TSLA' })) === null, 'no price for the charted name');
    """)


FACET = r"""
var host = { innerHTML: '', querySelector: function (sel) {
  return sel === 'header.sec-head' ? head : null; } };
var head = { outerHTML: '' };
var views = { overview: host, news: { innerHTML: '', querySelector: function () { return null; } } };
var STATE = { ticker: 'HOOD', view: 'overview', swing: null, quickQuote: null };
function esc(s) { return String(s); }
var headers = 0;
function securityHeader(view) {
  headers++;
  var q = STATE.quickQuote && STATE.quickQuote.ticker === STATE.ticker ? STATE.quickQuote.quote : null;
  return '<header class="sec-head">' + (q ? 'px ' + q.price : 'no price') + '</header>';
}
function emptyHTML() { return 'empty'; }
function errorHTML(m) { return 'error ' + m; }
function preserveUI(h, f) { f(); }
function renderOverviewView() { host.innerHTML = 'overview'; }
function renderNewsView() {} function renderFinancialsView() {}
var release, fail;
function loadSwing() { return new Promise(function (r, j) { release = r; fail = j; }); }
var fetched = [], answer;
function fetch(url) {
  fetched.push(url);
  return new Promise(function (r) { answer = function (body, ok) {
    r({ ok: ok !== false, json: function () { return Promise.resolve(body); } }); }; });
}
function tick() { return new Promise(function (r) { Promise.resolve().then(function () { Promise.resolve().then(r); }); }); }
async function settle() { for (var i = 0; i < 6; i++) await tick(); }
"""


def test_a_first_load_asks_for_the_price_and_paints_it_the_moment_it_lands():
    _js(FACET, ["loadSecurityFacet"], """
      var p = loadSecurityFacet('overview', false);
      assert(fetched.length === 1 && fetched[0] === '/api/quote/HOOD', 'asked: ' + fetched);
      assert(host.innerHTML.indexOf('Loading HOOD') >= 0, 'the loading panel is up');
      answer({ ticker: 'HOOD', available: true, quote: { price: 41.2 } });
      await settle();
      assert(head.outerHTML === '<header class="sec-head">px 41.2</header>', 'painted: ' + head.outerHTML);
      assert(host.innerHTML.indexOf('Loading HOOD') >= 0, 'and the rest is still loading below it');
      STATE.swing = { ticker: 'HOOD' };
      release({ ticker: 'HOOD' }); await p;
      assert(STATE.quickQuote === null, 'gone once the load it stood in for is done');
      assert(host.innerHTML === 'overview', 'the page drew');
    """)


def test_a_price_that_lands_after_the_full_answer_changes_nothing():
    _js(FACET, ["loadSecurityFacet"], """
      var p = loadSecurityFacet('overview', false);
      STATE.swing = { ticker: 'HOOD' };
      release({ ticker: 'HOOD' }); await p;
      answer({ ticker: 'HOOD', available: true, quote: { price: 41.2 } });
      await settle();
      assert(head.outerHTML === '', 'the drawn page was not touched');
      assert(STATE.quickQuote === null, 'and nothing was kept for a later visit');
    """)


def test_a_price_that_lands_after_another_callers_full_answer_is_not_painted():
    # A second facet joins the first one's request, and the payload can land
    # through that one while this facet is still waiting on it.
    _js(FACET, ["loadSecurityFacet"], """
      var p = loadSecurityFacet('overview', false);
      STATE.swing = { ticker: 'HOOD' };
      answer({ ticker: 'HOOD', available: true, quote: { price: 41.2 } });
      await settle();
      assert(head.outerHTML === '' && STATE.quickQuote === null, 'painted over the full answer');
      release({ ticker: 'HOOD' }); await p;
    """)


def test_a_price_for_a_symbol_the_reader_has_left_is_dropped():
    _js(FACET, ["loadSecurityFacet"], """
      var p = loadSecurityFacet('overview', false);
      STATE.ticker = 'NKE';
      answer({ ticker: 'HOOD', available: true, quote: { price: 41.2 } });
      await settle();
      assert(head.outerHTML === '' && STATE.quickQuote === null, 'HOOD painted under NKE');
      release(null); await p;
    """)


def test_a_price_that_lands_after_a_failed_load_is_not_kept_either():
    _js(FACET, ["loadSecurityFacet"], """
      var p = loadSecurityFacet('overview', false);
      fail(new Error('HTTP 503')); await p;
      assert(host.innerHTML.indexOf('error HTTP 503') >= 0, 'the failure is said');
      answer({ ticker: 'HOOD', available: true, quote: { price: 41.2 } });
      await settle();
      assert(STATE.quickQuote === null, 'kept, it would open the next visit with an old price');
    """)


def test_an_unavailable_or_failed_quote_leaves_the_header_alone():
    _js(FACET, ["loadSecurityFacet"], """
      var p = loadSecurityFacet('overview', false);
      answer({ ticker: 'HOOD', available: false });
      await settle();
      assert(head.outerHTML === '' && STATE.quickQuote === null, 'unavailable');
      release(null); await p;
      fetched = [];
      p = loadSecurityFacet('overview', false);
      answer(null, false);                       // a 502 from the edge
      await settle();
      assert(head.outerHTML === '' && STATE.quickQuote === null, 'not ok');
      release(null); await p;
    """)


def test_a_refresh_of_a_loaded_symbol_does_not_ask():
    _js(FACET, ["loadSecurityFacet"], """
      STATE.swing = { ticker: 'HOOD' };
      var p = loadSecurityFacet('overview', true);          // forced, already have it
      release({ ticker: 'HOOD' }); await p;
      p = loadSecurityFacet('overview', false, { silent: true });
      await p;
      assert(fetched.length === 0, 'the header already has the full price: ' + fetched);
    """)


def test_the_price_is_repainted_only_on_the_facet_that_asked():
    _js(FACET, ["loadSecurityFacet"], """
      var p = loadSecurityFacet('overview', false);
      STATE.view = 'news';                      // the reader switched facet
      answer({ ticker: 'HOOD', available: true, quote: { price: 41.2 } });
      await settle();
      assert(head.outerHTML === '', 'an off-screen header rewritten');
      assert(STATE.quickQuote && STATE.quickQuote.quote.price === 41.2,
             'but kept for the facet now on screen, whose own load is still waiting');
      release(null); await p;
    """)
