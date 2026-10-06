"""Key stats on a stock's Overview.

The numbers a reader looks for first on any quote page: market cap, P/E both
ways, EPS both ways, dividend yield, the 52-week and day ranges, beta, volume.
All from the quote the page already loads; a figure the quote lacks is left
out rather than shown as a dash, so a fund's list is shorter than a company's.

Checked in a browser: AAPL listed thirteen, $4.87T and a 38.3 P/E among them;
SPY six, with no EPS or beta; both below Optic's read.
"""
from __future__ import annotations

from pathlib import Path

from app.providers import yf

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
CSS = (ROOT / "static/styles.css").read_text()


def _fn(head):
    at = APP.index(head)
    return APP[at:APP.index("\n}\n", at) + 3]


def test_the_quote_carries_eps_both_ways():
    src = Path(yf.__file__).read_text()
    assert '"trailing_eps": _f(info.get("trailingEps")),' in src
    assert '"forward_eps": _f(info.get("forwardEps")),' in src


def test_the_panel_lists_only_what_the_quote_has():
    rows = _fn("function keyStatRows(q, short) {")
    for label in ("Market cap", "P/E (trailing)", "P/E (forward)", "EPS (trailing)", "EPS (forward)",
                  "Dividend yield", "Open price", "52-week high", "52-week low", "Beta", "Volume",
                  "Average volume", "Short interest", "Days to cover"):
        assert f"['{label}'" in rows, label
    ks = _fn("function keyStatsHTML(q, opts = {}) {")
    assert ".map((id) => all[id]).filter((r) => r && r[1] !== null);" in ks
    assert "if (!rows.length) return '';" in ks


def test_it_sits_below_optics_read():
    assert ("    ${renderOpticPulse(d)}\n    ${keyStatsHTML(q, { view: 'overview', "
            "short: (d.company || {}).short_interest })}\n") in APP
    assert ".ks-grid {" in CSS


# ------------------------------------------------- the applicable figures, by tab
#
# Asked for with a broker's "Key statistics" panel: "add the applicable info to
# the tabs as well". Each tab shows the figures that serve it, not Overview's
# whole list. Short inventory and borrow rate are a broker's figures that no
# feed here carries, so the short side is exchange-reported short interest.

import json
import os
import shutil
import subprocess

import pytest

JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
QUOTE = {"price": 155.0, "market_cap": 54.11e9, "trailing_pe": 24.46, "forward_pe": 20.1,
         "trailing_eps": 6.33, "forward_eps": 7.7, "dividend_yield": 0.0063, "open": 151.44,
         "day_high": 161.61, "day_low": 146.0, "volume": 10.86e6, "avg_volume": 6.34e6,
         "fifty_two_high": 217.10, "fifty_two_low": 132.66, "beta": 1.3,
         "profit_margin": 0.12, "revenue_growth": 0.08}
SHORT = {"available": True, "percent_of_float": 0.034, "days_to_cover": 1.8,
         "settlement_date": "2026-09-15"}


def _jsc(script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = """
      load('tests/support/browser_stubs.js');
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      document.documentElement.style.removeProperty = function () {};
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
      var Q = %s, SH = %s, R = {};
    """ % (json.dumps(QUOTE), json.dumps(SHORT)) + script + "\nprint('RESULT:' + JSON.stringify(R));"
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    blob = out.stdout + out.stderr
    assert "RESULT:" in blob, blob[-1500:]
    return json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])


def test_each_tab_shows_the_figures_that_serve_it():
    out = _jsc("""
      marketSessionET = function () { return 'regular'; };
      ['overview', 'chart', 'swing', 'long', 'earnings', 'financials', 'news'].forEach(function (v) {
        R[v] = keyStatsHTML(Q, {view: v, short: SH});
      });
    """)
    chart, earnings, swing, long_ = out["chart"], out["earnings"], out["swing"], out["long"]
    for label in ("Open price", "High today", "Low today", "Volume", "Average volume",
                  "52-week high", "52-week low"):
        assert label in chart, label
    assert "P/E" not in chart and "Market cap" not in chart
    assert "P/E (trailing)" in earnings and "EPS (forward)" in earnings and "Volume" not in earnings
    assert "Short interest" in swing and "3.40% of float, as of Sep 15" in swing and "Days to cover" in swing
    assert "Dividend yield" in long_ and "0.63%" in long_ and "Open price" not in long_
    assert "$54.11B" in out["overview"] and "24.5" in out["overview"]
    for html in out.values():
        assert "Borrow" not in html and "inventory" not in html


def test_the_days_figures_say_whose_day_they_are():
    out = _jsc("""
      marketSessionET = function () { return 'closed'; };
      R.closed = keyStatsHTML(Q, {view: 'chart'});
      marketSessionET = function () { return 'after'; };
      R.after = keyStatsHTML(Q, {view: 'chart'});
    """)
    assert "High last session" in out["closed"] and "High today" not in out["closed"]
    assert "High today" in out["after"]


def test_a_figure_the_quote_lacks_is_left_out_on_every_tab():
    out = _jsc("""
      R.fund = keyStatsHTML({price: 400, volume: 5e7}, {view: 'earnings'});
      R.none = keyStatsHTML({price: null}, {view: 'chart'});
    """)
    assert out["fund"] == "" and out["none"] == ""


def test_the_chart_has_them_in_its_dock():
    out = _jsc("""
      marketSessionET = function () { return 'regular'; };
      R.ids = WS_WIDGETS.map(function (w) { return w.id; });
      STATE.chartData = {quote: Q, company: {short_interest: SH}};
      R.body = wsWidgetBody('stats');
      STATE.chartData = null;
      R.empty = wsWidgetBody('stats');
    """)
    assert "stats" in out["ids"]
    assert '<dl class="ks-grid">' in out["body"] and "Open price" in out["body"]
    assert "<section" not in out["body"], "the dock has its own title"
    assert "Load a symbol." in out["empty"]


def test_every_tab_renders_them():
    assert "keyStatsHTML(d.quote, { view: 'swing'" in APP
    assert "keyStatsHTML(facetQuote(STATE.ticker || ''), { view: 'news'" in APP
    assert "keyStatsHTML(facetQuote(STATE.ticker || ''), { view: 'financials'" in APP
    assert "securityHeader('long') + keyStatsHost('long')" in APP
    assert "securityHeader('earnings') + keyStatsHost('earnings')" in APP


def test_the_quote_carries_the_open():
    src = Path(yf.__file__).read_text()
    assert '"open": _f(info.get("regularMarketOpen") or info.get("open")),' in src
