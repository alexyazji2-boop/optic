"""Three fixes to the Dossier asked for together.

1. "make sure to add the chart pop-up animation when it loads, it is not there
   anymore". The Charting tab opens on hourly bars, so the draw-on a new symbol
   is given went to the daily chart behind the loading state, and the bars the
   reader sees arrived without it. Fetched bars now sweep on as they land.

2. "have a bit more space for this section", circled round the drawing tools.
   The rail was --space-1 a side around 30px buttons, and a short window's
   scrollbar took its width from them.

3. "whenever the user inputs an ETF, hide the financials tab, as it is not
   applicable". A fund's strip leaves Financials out, and anything that still
   opens it for a fund lands on Overview.

Checked in a browser: SPY's strip read Overview, Chart, Options, Investing,
Earnings, News, and AAPL's had Financials; Financials for SPY opened Overview;
the hourly bars for a new symbol redrew with the animation on; the rail
measured 51px with 32px tools and no scrollbar.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
CSS = (ROOT / "static/styles.css").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _fn(head):
    at = APP.index(head)
    return APP[at:APP.index("\n}\n", at) + 3]


def _rule(selector):
    at = CSS.index(selector + " {")
    return CSS[at:CSS.index("}", at)]


# ------------------------------------------------------------- the draw-on

def test_fetched_hourly_bars_sweep_on_and_a_cached_repaint_does_not():
    load = _fn("async function wsLoadIntraday() {")
    cached = load.index("    wsRedrawChart();\n    return;\n  }")
    fetched = load.index("  wsFrameSweep = ++wsSweepSeq;\n  wsRedrawChart();")
    assert cached < fetched < load.index("await getJSON('/api/intraday/'")
    redraw = _fn("function wsRedrawChart(")
    assert "const sweep = !!wsFrameSweep && !chartInteractive && (ps.dates || []).length > 0;" in redraw, (
        "the loading redraw has no bars, so the sweep waits for the one that does")


# ------------------------------------------------------------- the rail

def test_the_drawing_rail_has_room_round_its_tools():
    rail = _rule(".ws-rail")
    assert "padding: var(--space-2) var(--space-2);" in rail and "min-width: 48px;" in rail
    assert "align-items: center;" in rail and "scrollbar-width: none;" in rail
    assert "overflow-y: auto;" in rail, "it still scrolls when the tools outrun the height"
    assert ".ws-rail::-webkit-scrollbar { display: none; }" in CSS
    tool = _rule(".ws-tool")
    assert "width: 32px;" in tool and "height: 32px;" in tool and "flex: none;" in tool


# ------------------------------------------------------------- funds

def _run(script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    prelude = """
      var STATE = { swing: null, quickQuote: null };
      const SECURITY_VIEWS = ['overview', 'chart', 'swing', 'long', 'earnings', 'financials', 'news'];
      const FUND_TYPES = ['ETF', 'MUTUALFUND'];
    """ + _fn("function symbolIsFund(sym) {") + _fn("function securityViewsFor(sym) {")
    out = subprocess.run([exe, "-e", prelude + script], capture_output=True, text=True,
                         timeout=60, cwd=str(ROOT))
    assert "RESULT:" in out.stdout, (out.stdout + out.stderr)[-1500:]
    return json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])


def test_a_funds_strip_has_no_financials_and_a_companys_does():
    out = _run("""
      var r = {};
      r.unknown = securityViewsFor('SPY');
      STATE.swing = { ticker: 'SPY', quote: { quote_type: 'ETF' } }; r.etf = securityViewsFor('SPY');
      STATE.swing = { ticker: 'VFIAX', quote: { quote_type: 'MUTUALFUND' } }; r.fund = securityViewsFor('VFIAX');
      STATE.swing = { ticker: 'AAPL', quote: { quote_type: 'EQUITY' } }; r.stock = securityViewsFor('AAPL');
      STATE.swing = { ticker: 'SPY', quote: { quote_type: 'ETF' } }; r.other = securityViewsFor('AAPL');
      STATE.swing = null; STATE.quickQuote = { ticker: 'QQQ', quote: { quote_type: 'etf' } };
      r.quick = securityViewsFor('QQQ');
      print('RESULT:' + JSON.stringify(r));
    """)
    every = ["overview", "chart", "swing", "long", "earnings", "financials", "news"]
    without = [v for v in every if v != "financials"]
    assert out["unknown"] == every, "until the quote says, the tab shows"
    assert out["etf"] == without and out["fund"] == without and out["quick"] == without
    assert out["stock"] == every
    assert out["other"] == every, "another symbol's quote says nothing about this one"


def test_the_strip_and_the_view_both_ask():
    head = _fn("function securityHeader(view, opts = {}) {")
    assert "const tabs = securityViewsFor(sym).map((v) => {" in head
    view = _fn("function renderFinancialsView(force) {")
    assert view.startswith("function renderFinancialsView(force) {\n"
                           "  if (symbolIsFund(STATE.ticker)) { switchView('overview'); return; }")
