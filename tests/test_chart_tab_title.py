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
      // What chartTabPrice reads: the bars on screen and the live tick.
      var chartRange = '6m', chartInterval = 'daily', chartSession = 'regular';
      var wsIntraday = null;
      const chartLive = { data: null, price: null };
      function isIntradayRange(k) { return /^[0-9]+$/.test(k || chartRange); }
    """ + _piece("function chartTabPrice(d) {") + _piece("function chartTabTitle() {") \
        + _piece("function syncTabTitle() {")
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


def test_the_title_names_the_price_the_chart_shows():
    """Reported with a tab reading "INTC: 117.43" over a chart whose price label
    read 117.48: the title was the quote the tab loaded with, the label the
    newest bar's close, fetched separately and later. The day's change in the
    title is for that same price."""
    out = _run("""
      STATE.view = 'chart'; STATE.chartSymbol = 'INTC'; chartRange = '15';
      STATE.chartData = { ticker: 'INTC', quote: { price: 117.43, prev_close: 119.38, change_pct: -1.63 } };
      wsIntraday = { symbol: 'INTC', available: true, closes: [117.40, 117.48, null] };
      syncTabTitle(); var intraday = document.title;
      chartRange = '6m'; wsIntraday = null;
      STATE.chartData.technicals = { price_series: { close: [118.0, 117.45] } };
      syncTabTitle(); var daily = document.title;
      print('RESULT:' + JSON.stringify({ intraday: intraday, daily: daily }));
    """)
    assert out == {"intraday": "INTC: 117.48 (-1.59%)", "daily": "INTC: 117.45 (-1.62%)"}


def test_each_live_tick_moves_the_title_and_a_new_payload_resets_it():
    """The live tick's price is the title's until another payload loads: a chart
    reopened hours later, with the market shut and no tick coming, must not
    name the morning's price."""
    out = _run("""
      STATE.view = 'chart'; STATE.chartSymbol = 'INTC';
      var d = { ticker: 'INTC', quote: { price: 117.43, prev_close: 119.38 } };
      STATE.chartData = d;
      chartLive.data = d; chartLive.price = 117.52; syncTabTitle(); var ticked = document.title;
      chartLive.price = 117.61; syncTabTitle(); var again = document.title;
      STATE.chartData = { ticker: 'INTC', quote: { price: 116.9, prev_close: 119.38 } };
      syncTabTitle(); var reloaded = document.title;
      print('RESULT:' + JSON.stringify({ ticked: ticked, again: again, reloaded: reloaded }));
    """)
    assert out == {"ticked": "INTC: 117.52 (-1.56%)", "again": "INTC: 117.61 (-1.48%)",
                   "reloaded": "INTC: 116.90 (-2.08%)"}


def _bar_run(script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    prelude = """
      var STATE = { chartSymbol: 'INTC', chartData: null };
      var chartRange = '15', chartInterval = 'daily', chartSession = 'regular';
      var session = 'regular';
      function marketSessionET() { return session; }
      function isIntradayRange(k) { return /^[0-9]+$/.test(k || chartRange); }
      function etDate(v) { return new Date(v).toLocaleDateString('en-CA', { timeZone: 'America/New_York' }); }
      var wsIntraday = null;
    """ + _piece("function chartBarMinutes(interval) {") + _piece("function chartLiveBar(price, nowMs) {")
    out = subprocess.run([exe, "-e", prelude + script], capture_output=True, text=True,
                         timeout=60, cwd=str(ROOT))
    assert "RESULT:" in out.stdout, (out.stdout + out.stderr)[-2000:]
    return json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])


def test_the_price_goes_into_the_bar_that_is_still_forming():
    out = _bar_run("""
      var start = Date.parse('2026-10-05T13:00:00-04:00');
      function fresh() { return { symbol: 'INTC', available: true, interval: '15m',
        times: ['2026-10-05T12:45:00-04:00', '2026-10-05T13:00:00-04:00'],
        closes: [117.40, 117.48], highs: [117.5, 117.53], lows: [117.3, 117.31] }; }
      wsIntraday = fresh();
      var open = chartLiveBar(117.60, start + 5 * 60000);
      var bar = [wsIntraday.closes[1], wsIntraday.highs[1], wsIntraday.lows[1], wsIntraday.closes[0]];
      wsIntraday = fresh();
      var closed = chartLiveBar(117.60, start + 15 * 60000);
      var untouched = wsIntraday.closes[1];
      wsIntraday = fresh(); session = 'after';
      var afterHours = chartLiveBar(117.60, start + 5 * 60000);
      chartSession = 'extended';
      var extended = chartLiveBar(117.60, start + 5 * 60000);
      print('RESULT:' + JSON.stringify({ open: open, bar: bar, closed: closed, untouched: untouched,
        afterHours: afterHours, extended: extended }));
    """)
    assert out == {"open": "updated", "bar": [117.6, 117.6, 117.31, 117.4],
                   "closed": "closed", "untouched": 117.48,
                   "afterHours": "skipped", "extended": "updated"}


def test_a_daily_chart_takes_the_price_only_on_todays_bar():
    out = _bar_run("""
      chartRange = '6m';
      var now = Date.now();
      var today = etDate(now), yesterday = etDate(now - 3 * 864e5);
      STATE.chartData = { technicals: { price_series: { dates: [yesterday, today],
        close: [100, 101], high: [102, 101.5], low: [99, 100.2] } } };
      var live = chartLiveBar(99.9, now);
      var ps = STATE.chartData.technicals.price_series;
      var bar = [ps.close[1], ps.high[1], ps.low[1]];
      ps.dates[1] = yesterday;
      var stale = chartLiveBar(98, now);
      chartInterval = 'weekly';
      var weekly = chartLiveBar(98, now);
      print('RESULT:' + JSON.stringify({ live: live, bar: bar, stale: stale, weekly: weekly }));
    """)
    assert out == {"live": "updated", "bar": [99.9, 101.5, 99.9], "stale": "skipped",
                   "weekly": "skipped"}


def test_the_live_tick_runs_in_a_background_tab_and_never_redraws_under_the_hand():
    """A hidden tab is where the title is read, so the tick does not stop for
    one; the chart, though, is not redrawn mid-gesture or under the pointer."""
    tick = _piece("async function chartLiveTick() {")
    assert "document.hidden" not in tick, "the tick must keep the title moving in a hidden tab"
    assert "fetch('/api/quote/' + encodeURIComponent(sym))" in tick
    assert "setInterval(chartLiveTick, CHART_LIVE_MS);" in APP
    repaint = _piece("function chartLiveRepaint() {")
    assert repaint.index("syncTabTitle();") < repaint.index("chartUnderHand()"), \
        "the title updates even when the chart cannot redraw"
    hand = _piece("function chartUnderHand() {")
    for flag in ("wsPan", "wsDragging", "wsMenuOpen", ":hover"):
        assert flag in hand, flag
