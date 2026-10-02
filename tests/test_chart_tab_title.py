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
    """ + _piece("function chartTabTitle() {") + _piece("function syncTabTitle() {")
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


def test_every_other_page_is_the_app_name_and_leaving_puts_it_back():
    out = _run("""
      STATE.chartSymbol = 'GOOGL';
      STATE.chartData = { ticker: 'GOOGL', quote: { price: 344.2, change_pct: 1.7 } };
      var titles = [];
      ['chart', 'market', 'swing', 'chart', 'home'].forEach(function (v) {
        STATE.view = v; syncTabTitle(); titles.push(document.title); });
      print('RESULT:' + JSON.stringify(titles));
    """)
    assert out == ["GOOGL: 344.20 (+1.70%)", "Optic Terminal", "Optic Terminal",
                   "GOOGL: 344.20 (+1.70%)", "Optic Terminal"]


def test_while_loading_or_without_a_price_it_does_not_show_another_symbols_price():
    out = _run("""
      STATE.view = 'chart'; STATE.chartSymbol = 'AMD'; STATE.chartData = 'loading'; syncTabTitle();
      var loading = document.title;
      STATE.chartData = { ticker: 'GOOGL', quote: { price: 344.2, change_pct: 1.7 } }; syncTabTitle();
      var stale = document.title;
      STATE.chartData = { error: 'boom' }; syncTabTitle(); var failed = document.title;
      STATE.chartSymbol = ''; STATE.chartData = null; syncTabTitle(); var none = document.title;
      print('RESULT:' + JSON.stringify({ loading: loading, stale: stale, failed: failed, none: none }));
    """)
    assert out == {"loading": "AMD · Optic Terminal", "stale": "AMD · Optic Terminal",
                   "failed": "AMD · Optic Terminal", "none": "Optic Terminal"}


def test_the_title_follows_the_view_and_the_chart_payload():
    switch = _piece("function switchView(view, force) {")
    assert "  STATE.view = view;\n  syncTabTitle();" in switch
    load = APP[APP.index("async function loadChartWorkspace(symbol, force) {"):]
    load = load[:load.index("\n}\n")]
    assert "  STATE.chartData = 'loading';\n  syncTabTitle();" in load
    assert "  syncTabTitle();\n  if (STATE.view !== 'chart') return;" in load, (
        "the 20-second refresh brings a new price, and the title takes it")
    assert "STATE.chartData = null; syncTabTitle();" in APP
    assert len(re.findall(r"document\.title\s*=", APP)) == 1, "one place sets it"
