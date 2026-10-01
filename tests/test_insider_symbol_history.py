"""A company's insiders' buys and sells, all of them, when its symbol is asked for.

Reported with a screenshot of the Insiders page on HOOD: "no insider buys/sells
on HOOD? not true". Three things said so together:

- The feed showed open-market purchases alone by default, and HOOD's insiders
  sell (its chief executive files 10b5-1 sales most weeks) and convert shares,
  so the default view of HOOD was an empty table. Buys and sells is the
  default now: the two codes that are an insider choosing to trade. Grants,
  exercises, tax withholding and conversions stay out of it, a press away.
- Each request reads twelve filings, and HOOD lists ninety-nine. The rest
  were to "fill in as you come back". With a symbol asked for, the page now
  keeps reading in the background until every listed filing is read.
- The box right under the search said "No filings match". It was about House
  disclosures, and read as no filings at all. It names its record now.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app import insiders

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


# ------------------------------------------------------------------ the server


def _filing(acc, *codes):
    return {"available": True, "ticker": "HOOD", "issuer": "Robinhood Markets, Inc.",
            "insider": "Tenev Vladimir", "roles": ["CEO"],
            "transactions": [{"kind": "non-derivative", "code": c, "code_label": c,
                              "code_note": "", "is_purchase": c == "P", "acquired": c in "PAMC",
                              "shares": 100.0, "price": 125.0, "value": 12500.0,
                              "date": "2026-09-2%d" % i, "security": "Class A"}
                             for i, c in enumerate(codes)]}


@pytest.fixture
def hood(monkeypatch):
    """Three filings already read: a sale, a conversion with a sale, and a
    purchase with a grant and shares withheld for tax."""
    parsed = {"a1": _filing("a1", "S"), "a2": _filing("a2", "C", "S"),
              "a3": _filing("a3", "P", "A", "F")}
    monkeypatch.setattr(insiders, "index", lambda force=False, ticker=None: {
        "available": True, "ticker": "HOOD", "note": None,
        "rows": [{"accession": a, "filed_at": "2026-09-2%sT16:00:00-04:00" % a[1],
                  "form": "4", "index_url": "https://www.sec.gov/x/" + a} for a in parsed]})
    monkeypatch.setattr(insiders.feeds, "cached_json",
                        lambda key: parsed.get(key.split(":")[-1]))
    return parsed


def _codes(out):
    return sorted(r["code"] for r in out["rows"])


def test_buys_and_sells_are_the_two_codes_that_are_a_trade():
    assert insiders.SHOWS == {"trades": ("P", "S"), "buys": ("P",), "all": None}


def test_buys_and_sells_keeps_the_sales_and_never_a_grant(hood):
    out = insiders.latest(ticker="HOOD", show="trades")
    assert _codes(out) == ["P", "S", "S"]
    assert out["show"] == "trades" and out["only_purchases"] is False
    assert out["matched"] == 3


def test_buys_only_and_everything_filed_are_still_there(hood):
    assert _codes(insiders.latest(ticker="HOOD", show="buys")) == ["P"]
    assert _codes(insiders.latest(ticker="HOOD", show="all")) == ["A", "C", "F", "P", "S", "S"]


def test_a_caller_that_sends_the_old_flag_gets_what_it_asked_for(hood):
    assert _codes(insiders.latest(ticker="HOOD")) == ["P"]
    assert _codes(insiders.latest(ticker="HOOD", only_purchases=False)) == ["A", "C", "F", "P", "S", "S"]
    assert insiders.latest(ticker="HOOD", show="nonsense")["show"] == "buys"


def test_the_endpoint_passes_the_view_through(monkeypatch):
    seen = {}

    def fake(limit, purchases, force, budget, ticker, show):
        seen.update(limit=limit, purchases=purchases, ticker=ticker, show=show)
        return {"available": True, "rows": []}
    monkeypatch.setattr(main.insiders_mod, "latest", fake)
    client = TestClient(main.app)
    client.get("/api/insiders/latest", params={"limit": 60, "show": "trades", "ticker": "HOOD"})
    assert seen == {"limit": 60, "purchases": True, "ticker": "HOOD", "show": "trades"}
    client.get("/api/insiders/latest", params={"purchases": "false"})
    assert seen["show"] is None and seen["purchases"] is False


# ------------------------------------------------------------------ the page


def _app(scenario):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    script = """
      load('tests/support/browser_stubs.js');
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      document.documentElement.style.removeProperty = function () {};
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
      var TIMERS = [], CALLS = [], REPLIES = [];
      setTimeout = function (f) { TIMERS.push(f); return TIMERS.length; };
      clearTimeout = function () { TIMERS.length = 0; };
      getJSON = async function (url) { CALLS.push(url); return REPLIES.shift() || { available: false }; };
      function reply(unread) {
        return { available: true, ticker: insiderTicker || null, rows: [], matched: 0,
                 filings_read: 12, filings_unread: unread };
      }
      async function drain() {
        var n = 0;
        while (TIMERS.length && n < 40) { var f = TIMERS.shift(); await f(); n += 1; }
      }
      (async function () {
        try { %s } catch (e) { print('RESULT:' + JSON.stringify({ error: String(e) })); }
      })();
    """ % scenario
    out = subprocess.run([exe, "-e", script], capture_output=True, text=True,
                         timeout=120, cwd=str(ROOT))
    assert "RESULT:" in out.stdout, (out.stdout + out.stderr)[-2000:]
    got = json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])
    assert "error" not in got, got
    return got


def test_the_page_asks_for_buys_and_sells_by_default():
    got = _app("""
      STATE.view = 'insiders'; insiderTicker = ''; STATE.insiders = null;
      REPLIES = [reply(0)];
      await loadInsiderFeed(false);
      print('RESULT:' + JSON.stringify({ show: insiderShow, calls: CALLS }));
    """)
    assert got["show"] == "trades"
    assert got["calls"] == ["/api/insiders/latest?limit=60&show=trades"]


def test_a_symbols_history_is_read_to_the_end():
    got = _app("""
      STATE.view = 'insiders'; insiderTicker = 'HOOD'; STATE.insiders = null;
      REPLIES = [reply(75), reply(63), reply(51), reply(0)];
      await loadInsiderFeed(false);
      await drain();
      print('RESULT:' + JSON.stringify({ calls: CALLS, last: STATE.insiders.filings_unread,
        pending: TIMERS.length }));
    """)
    assert len(got["calls"]) == 4 and got["last"] == 0 and got["pending"] == 0
    assert all(c == "/api/insiders/latest?limit=200&show=trades&ticker=HOOD" for c in got["calls"]), \
        "a batch at a time, never a forced refetch of the index"


def test_the_reading_is_capped_and_the_market_wide_list_is_not_read_on():
    got = _app("""
      STATE.view = 'insiders'; insiderTicker = 'HOOD'; STATE.insiders = null;
      for (var i = 0; i < 20; i++) REPLIES.push(reply(50));
      await loadInsiderFeed(false);
      await drain();
      var capped = CALLS.length;
      CALLS = []; insiderTicker = ''; STATE.insiders = null; REPLIES = [reply(88)];
      await loadInsiderFeed(false);
      await drain();
      print('RESULT:' + JSON.stringify({ capped: capped, market: CALLS.length }));
    """)
    assert got["capped"] == 1 + 9
    assert got["market"] == 1


def test_it_stops_when_the_reader_moves_on():
    got = _app("""
      STATE.view = 'insiders'; insiderTicker = 'HOOD'; STATE.insiders = null;
      REPLIES = [reply(75), reply(63)];
      await loadInsiderFeed(false);
      STATE.view = 'home';
      await drain();
      var left = CALLS.length;
      // And a reply for a symbol no longer asked for is dropped.
      STATE.view = 'insiders'; CALLS = []; STATE.insiders = null;
      REPLIES = [reply(40)];
      var pending = loadInsiderFeed(false);
      insiderTicker = 'NVDA';
      await pending;
      print('RESULT:' + JSON.stringify({ left: left, stale: STATE.insiders, timers: TIMERS.length }));
    """)
    assert got["left"] == 2, "one more batch was already asked for, and nothing after it"
    assert got["stale"] is None and got["timers"] == 0


def test_the_three_views_are_offered_with_the_default_lit():
    got = _app("""
      STATE.insiders = { available: true, ticker: 'HOOD', rows: [], matched: 0,
                         filings_read: 24, filings_unread: 75 };
      var empty = renderInsiderFeed();
      var row = { filed_at: '2026-09-24T16:33:07-04:00', ticker: 'HOOD', insider: 'Tenev Vladimir',
                  roles: [], code: 'S', code_label: 'Open-market sale', shares: 100, price: 125,
                  value: 12500, date: '2026-09-23' };
      STATE.insiders = { available: true, ticker: 'HOOD', rows: [row, row], matched: 226,
                         filings_read: 99, filings_unread: 0 };
      print('RESULT:' + JSON.stringify({ html: empty, full: renderInsiderFeed() }));
    """)
    html = got["html"]
    for key, label in (("trades", "Buys and sells"), ("buys", "Buys only"), ("all", "Everything filed")):
        assert 'data-ins-show="%s"' % key in html and ">%s</button>" % label in html, key
    assert 'class="pill on"\n        data-ins-show="trades" aria-pressed="true"' in html
    assert "75 more of HOOD's\n      filings are being read now" in html
    assert "No open-market buys or sells for HOOD in the filings read so far." in html
    assert '"Everything filed"' in html
    # More than the table holds: it says so.
    assert "226 open-market buys or sells from 99 filings read. The newest 2 are below." in got["full"]


def test_the_empty_house_record_says_whose_it_is():
    got = _app("""
      congressQuery = { ...CONGRESS_BLANK, ticker: 'hood', days: congressQuery.days };
      STATE.insCongress = { available: true, count: 0, filings_parsed: 113, filings_known: 403 };
      var narrowed = congressResults();
      congressQuery = { ...CONGRESS_BLANK, days: congressQuery.days };
      print('RESULT:' + JSON.stringify({ narrowed: narrowed, plain: congressResults() }));
    """)
    assert "No House trades in HOOD" in got["narrowed"]
    assert "Nothing in the House disclosures read so far matches HOOD." in got["narrowed"]
    assert "under Insider filings below" in got["narrowed"]
    assert "No filings match" in got["plain"] and "No House trades" not in got["plain"]


def test_every_control_still_has_its_handler():
    block = APP.split("closest('[data-ins-show]')", 1)[1][:700]
    assert "insiderShow = want;" in block and "loadInsiderFeed(false);" in block
    assert "INSIDER_SHOWS.some((v) => v.key === want)" in block, "an unknown view is ignored"
