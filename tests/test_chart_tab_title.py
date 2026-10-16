"""The browser tab names the chart's symbol and price while the Charting tab is open.

Asked for with a picture of a tab reading "GOOGL: 344.15 (+1.75...": "have the
tab change to something like this when the charting tab is open". On the
Charting tab the title is the symbol, its price and the day's change; on every
other page it is the app's name.

Checked in a browser: Overview read "Optic Terminal", the Charting tab read
"GOOGL: 344.21 (+1.76%)", Macro read "Optic Terminal" again, and back on the
chart it was "GOOGL: 344.21 (+1.76%)".
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _piece(head):
    at = APP.index(head)
    end = APP.index("\n}\n", at) + 3
    return APP[at:end]


def _run(script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    prelude = """
      var document = { title: 'Optic Terminal' };
      var STATE = { view: 'home', chartSymbol: '', chartData: null };
      function fmt(v, d) { return Number(v).toFixed(d); }
      function fmtPct(v, d) { return (v >= 0 ? '+' : '') + Number(v).toFixed(d) + '%'; }
      const APP_TITLE = 'Optic Terminal';
      const SUB_LABELS = { swing: 'Options', market: 'Macro', overview: 'Overview' };
      const VIEW_NAMES = { settings: 'Settings' };
      const SECURITY_VIEWS = ['overview', 'chart', 'swing'];
      // What chartTabPrice reads: the bars on screen and the live tick.
      var chartRange = '6m', chartInterval = 'daily', chartSession = 'regular';
      var wsIntraday = null;
      const chartLive = { data: null, price: null };
      function isIntradayRange(k) { return /^[0-9]+$/.test(k || chartRange); }
    """ + _piece("function chartTabPrice(d) {") + _piece("function chartTabTitle() {") \
        + _piece("function pageTabTitle() {") + _piece("function syncTabTitle() {")
    out = subprocess.run([exe, "-e", prelude + script], capture_output=True, text=True,
                         timeout=60, cwd=str(ROOT))
    assert "RESULT:" in out.stdout, (out.stdout + out.stderr)[-2000:]
    return json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])


def test_the_chart_tab_reads_symbol_price_and_change():
    out = _run("""
      STATE.chartSymbol = 'GOOGL';
      STATE.chartData = { ticker: 'GOOGL', quote: { price: 344.2058, change_pct: 1.7637832 } };
      STATE.view = 'chart'; syncTabTitle(); var up = document.title;
      STATE.chartData.quote.change_pct = -0.42; syncTabTitle(); var down = document.title;
      delete STATE.chartData.quote.change_pct; syncTabTitle(); var bare = document.title;
      print('RESULT:' + JSON.stringify({ up: up, down: down, bare: bare }));
    """)
    assert out == {"up": "GOOGL: 344.21 (+1.76%)", "down": "GOOGL: 344.21 (-0.42%)",
                   "bare": "GOOGL: 344.21"}


def test_every_other_page_names_itself_and_leaving_puts_it_back():
    """Each page has its own title since pages have their own addresses
    (WCAG 2.4.2); it read "Optic Terminal" everywhere but the chart until
    2026-10-16. Home stays the bare name, a Dossier page leads with its symbol,
    and a view with no name falls back to the app's."""
    out = _run("""
      STATE.chartSymbol = 'GOOGL'; STATE.ticker = 'GOOGL';
      STATE.chartData = { ticker: 'GOOGL', quote: { price: 344.2, change_pct: 1.7 } };
      var titles = [];
      ['chart', 'market', 'swing', 'chart', 'settings', 'nowhere', 'home'].forEach(function (v) {
        STATE.view = v; syncTabTitle(); titles.push(document.title); });
      print('RESULT:' + JSON.stringify(titles));
    """)
    assert out == ["GOOGL: 344.20 (+1.70%)", "Macro · Optic Terminal", "GOOGL Options · Optic Terminal",
                   "GOOGL: 344.20 (+1.70%)", "Settings · Optic Terminal", "Optic Terminal", "Optic Terminal"]
