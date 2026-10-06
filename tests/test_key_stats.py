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
    assert ".filter((id) => all[id] && all[id][1] !== null);" in ks
    assert "if (!ids.length) return '';" in ks


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


def _jsc(script, before=""):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = """
      load('tests/support/browser_stubs.js');
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      document.documentElement.style.removeProperty = function () {};
    """ + before + """
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


# ------------------------------------------------------------ what each one means
#
# Asked for over the Investing tab's panel: "include definitions for each of
# these terms". Each label explains itself by the reader's knowledge mode, the
# way the glossary's terms do.

import re

ALL_IDS = ["market_cap", "pe_trailing", "pe_forward", "eps_trailing", "eps_forward",
           "dividend_yield", "open", "day_high", "day_low", "volume", "avg_volume",
           "high_52", "low_52", "beta", "short_float", "days_to_cover", "profit_margin",
           "revenue_growth"]


def _defs():
    return _jsc("R = KEY_STAT_DEFS;")


def test_every_figure_has_a_definition():
    defs = _defs()
    rows = _fn("function keyStatRows(q, short) {")
    ids = re.findall(r"^    (\w+): \[", rows, re.M)
    assert sorted(ids) == sorted(ALL_IDS), ids
    for view, listed in _jsc("R = KEY_STATS_FOR;").items():
        for fid in listed:
            assert defs.get(fid), (view, fid)


def test_each_definition_says_what_it_is_and_why_it_matters():
    """The glossary's own rules (tests/test_glossary_fundamentals.py): two
    sentences at least, no em dash, and no telling the reader what to do."""
    banned = ("you should", "you want", "look for a", "buy when", "sell when",
              "a good sign that you")
    for fid, body in _defs().items():
        assert body.count(".") >= 2 and len(body) >= 110, (fid, body)
        assert "\u2014" not in body, fid
        for phrase in banned:
            assert phrase not in body.lower(), (fid, phrase)


def test_the_definitions_say_what_the_feed_measures():
    """Checked against Yahoo's own data on 2026-10-06 (AAPL, VST, PLTR, KO)."""
    d = _defs()
    assert "intraday highs rather than closing prices" in d["high_52"]
    assert "intraday lows rather than closing prices" in d["low_52"]
    assert "five years of monthly returns against the S&P 500" in d["beta"]
    assert "last three months" in d["avg_volume"]
    assert "same quarter a year earlier" in d["revenue_growth"]
    assert "last twelve months" in d["profit_margin"]
    assert "current rate" in d["dividend_yield"]
    assert "regular session" in d["day_high"] and "regular session" in d["day_low"]


def test_the_glossary_wording_is_reused_where_it_exists():
    d = _defs()
    gl = _jsc("R = {cap: GLOSSARY['market cap'], si: GLOSSARY['short interest'], dtc: GLOSSARY['days to cover']};")
    assert d["market_cap"] == gl["cap"] and d["days_to_cover"] == gl["dtc"]
    assert d["short_float"].startswith(gl["si"])


def test_each_label_explains_itself_by_the_readers_mode():
    out = _jsc("""
      marketSessionET = function () { return 'regular'; };
      var policy = 'on_demand';
      explainPolicy = function () { return policy; };
      R.demand = keyStatsHTML(Q, {view: 'long', short: SH});
      policy = 'inline';
      R.inline = keyStatsHTML(Q, {view: 'long', short: SH});
      policy = 'off';
      R.off = keyStatsHTML(Q, {view: 'long', short: SH});
      R.beta = KEY_STAT_DEFS.beta;
    """)
    demand, inline, off = out["demand"], out["inline"], out["off"]
    # The Investing tab's seven, each marked.
    assert demand.count('<dfn class="gloss-term" tabindex="0"') == 7, demand
    assert 'data-def="How far the stock has tended to move' in demand
    assert '>Beta</dfn>' in demand and '>Market cap</dfn>' in demand
    # Simple: a control that opens the definition in place.
    assert inline.count("data-gloss-open") == 7 and 'aria-expanded="false"' in inline
    # Professional: the figures, unmarked.
    assert "gloss-term" not in off and "<dt>Beta</dt>" in off
    # The definition text survives the attribute round trip (S&P's ampersand).
    assert "S&amp;P 500" in demand and "&amp;amp;" not in demand


def test_an_opened_definition_goes_under_the_whole_row():
    """Seen in the browser on Simple: opened after the label, the definition
    was squeezed into the label's half beside the figure, a column about a
    hundred pixels wide. It is now one more <dd> of the row, full width."""
    out = _jsc("""
      function el(tag, cls) {
        return { tagName: tag.toUpperCase(), className: cls || '', textContent: '', kids: [], attrs: {},
          classList: { contains: function (c) { return (this.owner.className || '').split(' ').indexOf(c) >= 0; } },
          getAttribute: function (k) { return Object.prototype.hasOwnProperty.call(this.attrs, k) ? this.attrs[k] : null; },
          setAttribute: function (k, v) { this.attrs[k] = String(v); },
          appendChild: function (c) { this.kids.push(c); c.parent = this; },
          insertAdjacentElement: function () { R.wrongPlace = true; },
          remove: function () { var i = this.parent.kids.indexOf(this); this.parent.kids.splice(i, 1); } };
      }
      var row = el('div', 'ks-row'), term = el('button', 'gloss-term is-inline');
      term.attrs['data-def'] = 'What beta is.'; term.attrs['aria-expanded'] = 'false';
      row.querySelector = function () {
        return this.kids.filter(function (k) { return k.className === 'gloss-inline'; })[0] || null;
      };
      term.closest = function (sel) { return sel === '[data-gloss-open]' ? term : sel === '[data-gloss-row]' ? row : null; };
      document.createElement = function (tag) { var e = el(tag); e.classList.owner = e; return e; };
      // The glossary's own click listener, as app.js registered it.
      var gloss = CLICKS.filter(function (fn) { return String(fn).indexOf('data-gloss-open') >= 0; });
      R.listeners = gloss.length;
      gloss[0]({ target: term });
      R.opened = row.kids.map(function (k) { return k.tagName + '.' + k.className + ':' + k.textContent; });
      R.expanded = term.attrs['aria-expanded'];
      gloss[0]({ target: term });
      R.closed = row.kids.length; R.after = term.attrs['aria-expanded'];
    """, before="""
      var CLICKS = [];
      document.addEventListener = function (type, fn) { if (type === 'click') CLICKS.push(fn); };
    """)
    assert out["listeners"] == 1, out
    assert out["opened"] == ["DD.gloss-inline:What beta is."], out
    assert out["expanded"] == "true" and not out.get("wrongPlace")
    assert out["closed"] == 0 and out["after"] == "false"


def test_the_row_wraps_only_while_a_definition_is_open():
    assert "data-gloss-row" in _fn("function keyStatsHTML(q, opts = {}) {")
    assert ".ks-row:has(> .gloss-inline) { flex-wrap: wrap; }" in CSS
    assert ".ks-row > .gloss-inline { flex-basis: 100%;" in CSS
    opened = CSS[CSS.index(".ks-row > .gloss-inline {"):]
    opened = opened[:opened.index("}")]
    assert "text-align: left;" in opened and "font-weight: 400;" in opened, "styled as a figure"
    phone = CSS[CSS.index(".ks-grid { grid-template-columns: 1fr 1fr;"):]
    phone = phone[:phone.index("\n}\n")]
    assert ".ks-row:has(> .gloss-inline) { grid-column: 1 / -1; flex-wrap: nowrap; }" in phone
    # Measured at 375px: wrapping the stacked row put the definition in a
    # second column, 34px past the row's edge.
    assert ".ks-row > .gloss-inline { flex-basis: auto; }" in phone
    base = CSS[CSS.index(".ks-row { display: flex;"):]
    assert "flex-wrap" not in base[:base.index("}")], "a long figure would drop below its label"
