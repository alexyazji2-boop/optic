"""Investing: the price against its yardsticks, on one axis.

Asked for as "Investing-tab valuation-range visuals". The fair value range was
a bar of its own with no figures a screen reader could reach, and the
analysts' targets were two numbers in a tile beside it, so the question both
answer (where the price sits against each) needed reading across two panels.
"Where the price sits" draws them as rows on one price axis, with the 52-week
range as the price's own yardstick and today's price as one line through all
of them. The old bar is gone, so the range is drawn once.

Found doing it: the Investing tab drew the P/E history it had in hand, so
moving from one stock to another showed the first one's multiples under the
second's name until the new request returned.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.test_visual_primitives import _jsc as _prim

ROOT = Path(__file__).resolve().parent.parent
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"

FV = {"fair_value": {"available": True, "low": 500.8, "mid": 604.92, "high": 653.38, "price": 529.3, "wide": False,
                     "multiples": {"mid": 31.3}},
      "analysts": {"available": True, "target_low": 440, "target_mean": 585.61, "target_high": 870, "analyst_count": 52}}


def _app(script, prelude=""):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = """
      load('tests/support/browser_stubs.js');
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      document.documentElement.style.removeProperty = function () {};
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
      explainPolicy = function () { return 'on_demand'; };
      STATE.ticker = 'MSFT';
      STATE.swing = { ticker: 'MSFT', quote: { price: 529.3, fifty_two_low: 349.2, fifty_two_high: 553.72 } };
      var FV = %s, R = {}, BUILT = {}, CAPT = {};
      vizMount = function (id, build, none) { BUILT[id] = { build: build, none: none }; };
      fieldChart = function (o) { (CAPT.f = CAPT.f || []).push(o); return { chart: 'field' }; };
      function build(id) { var b = BUILT[id]; return b ? b.build(600) : 'not mounted'; }
    """ % json.dumps(FV) + prelude + script + "\nprint('RESULT:' + JSON.stringify(R));"
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    blob = out.stdout + out.stderr
    assert "RESULT:" in blob, blob[-2000:]
    return json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])


def test_the_yardsticks_are_rows_on_one_axis_with_the_price_through_them():
    out = _app("""
      R.html = renderFairValue(FV);
      mountYardsticks(FV);
      build('viz-inv-field');
      var o = CAPT.f[0];
      R.rows = o.rows.map(function (r) { return [r.label, r.low, r.high, r.mid === undefined ? null : r.mid]; });
      R.price = o.price; R.colors = o.rows.map(function (r) { return r.color; }); R.c = [C.brand, C.s7, C.ink2];
    """)
    html = out["html"]
    assert "At $529.30, the price is inside both its fair value range and the analysts' targets" in html
    assert html.index("Where the price sits") < html.index("What analysts say")
    assert out["rows"] == [["Fair value", 500.8, 653.38, 604.92], ["Analyst targets", 440, 870, 585.61],
                           ["52-week range", 349.2, 553.72, None]]
    assert out["price"] == 529.3 and out["colors"] == out["c"]
    assert 'class="fv-bar"' not in html, "the range is drawn once"


def test_a_range_too_wide_to_call_is_left_off_and_one_yardstick_is_not_a_comparison():
    out = _app("""
      var wide = JSON.parse(JSON.stringify(FV)); wide.fair_value.wide = true;
      R.labels = yardstickRows(wide).map(function (r) { return r.label; });
      R.html = yardsticksHTML(wide);
      STATE.swing = null;
      R.alone = yardsticksHTML({ fair_value: FV.fair_value, analysts: { available: false } });
      R.title = yardsticksTitle([{ key: 'fv', low: 600, high: 700 }, { key: 'an', low: 400, high: 800 }], 550);
    """)
    assert out["labels"] == ["Analyst targets", "52-week range"]
    assert "The fair value range is too wide to draw against a price, and is left out." in out["html"]
    assert out["alone"] == ""
    assert out["title"] == "At $550.00, the price is below its fair value range and inside the analysts' targets"


def test_another_stocks_p_e_history_is_not_drawn_under_this_one():
    out = _app("""
      STATE.peHistory = { available: true, ticker: 'AAPL' }; STATE.peHistoryFor = 'AAPL';
      R.other = peHistoryForTicker();
      STATE.peHistoryFor = 'MSFT';
      R.own = !!peHistoryForTicker();
      var src = loadPeHistory.toString();
      R.drops = src.indexOf('if (STATE.peHistoryFor !== sym) return;') > 0 && src.indexOf('STATE.peHistory = null;') > 0;
      R.long = renderLong.toString().indexOf('renderPeHistory(peHistoryForTicker())') > 0;
    """)
    assert out["other"] is None and out["own"] is True
    assert out["drops"] and out["long"]


def test_the_field_chart_says_where_the_price_sits_in_each_row():
    out = _prim("""
      var root = fieldChart({ width: 600, price: 529, format: function (v) { return '$' + Math.round(v); }, rows: [
        { label: 'Fair value', low: 501, high: 653, mid: 605 }, { label: '52-week range', low: 349, high: 554 },
        { label: 'Broken', low: 5, high: 5 } ] });
      R.marks = all(root, function (n) { return n.attrs && n.attrs.tabindex === '0'; }).map(function (n) { return n.attrs['aria-label']; });
      R.labels = texts(root);
      R.none = fieldChart({ rows: [], price: 1 });
      var narrow = fieldChart({ width: 340, price: 529, rows: [{ label: 'Fair value', low: 501, high: 653 }] });
      R.narrowLabel = all(narrow, function (n) { return n.tag === 'text' && n.textContent === 'Fair value'; })[0].attrs['text-anchor'] || 'start';
    """)
    assert out["marks"] == ["Fair value: $501 to $653, middle $605; the price is inside it",
                            "52-week range: $349 to $554; the price is inside it"], "a row with no width is left out"
    assert "Price $529" in out["labels"] and "$501" in out["labels"] and "$653" in out["labels"]
    assert out["none"] is None
    assert out["narrowLabel"] == "start", "on a phone the row's name goes above its bar"
