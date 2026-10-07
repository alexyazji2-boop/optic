"""The visual-first chart primitives, drawn into a recording DOM.

Asked for as "lead with the visual and keep precise numerical detail
available". These are the shared pieces in static/charts.js; each test reads
the marks a chart drew, the way a reader would: what is a ring, what is a dot,
what colour, whether it can be reached with the keyboard, and what it says.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"

DOM = r"""
function El(tag) { this.tag = tag; this.attrs = {}; this.children = []; this.listeners = {}; this.style = {}; this.textContent = ''; }
El.prototype.setAttribute = function (k, v) { this.attrs[k] = String(v); };
El.prototype.getAttribute = function (k) { return Object.prototype.hasOwnProperty.call(this.attrs, k) ? this.attrs[k] : null; };
El.prototype.appendChild = function (c) { this.children.push(c); return c; };
El.prototype.addEventListener = function (t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); };
El.prototype.getBoundingClientRect = function () { return { left: 0, top: 0, width: 10, height: 10 }; };
var TIPS = [];
var tooltip = new El('div'); tooltip.classList = { add: function () {}, remove: function () {} };
tooltip.getBoundingClientRect = function () { return { width: 100, height: 40 }; };
Object.defineProperty(tooltip, 'innerHTML', { set: function (v) { TIPS.push(v); }, get: function () { return ''; } });
var document = {
  createElementNS: function (ns, tag) { return new El(tag); },
  createElement: function (tag) { return new El(tag); },
  createTextNode: function (t) { var e = new El('#text'); e.textContent = t; return e; },
  getElementById: function (id) { return id === 'tooltip' ? tooltip : null; },
  documentElement: {}, addEventListener: function () {},
};
var window = { matchMedia: function () { return { matches: false, addEventListener: function () {} }; },
  innerWidth: 1400, innerHeight: 900, addEventListener: function () {} };
function walk(el, fn) { fn(el); (el.children || []).forEach(function (c) { walk(c, fn); }); }
function all(root, pred) { var out = []; walk(root, function (n) { if (pred(n)) out.push(n); }); return out; }
function texts(root) { return all(root, function (n) { return n.tag === 'text'; }).map(function (n) { return n.textContent; }); }
"""


def _jsc(script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = DOM + "\nload('static/charts.js');\nvar R = {};\n" + script + "\nprint('RESULT:' + JSON.stringify(R));"
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    blob = out.stdout + out.stderr
    assert "RESULT:" in blob, blob[-2000:]
    return json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])


# ------------------------------------------------------------ estimate against actual

def test_estimated_and_actual_are_told_apart_by_shape_and_the_gap_by_colour():
    out = _jsc("""
      var root = dumbbellChart({ width: 600, ariaLabel: 'EPS against the estimate', items: [
        { label: "Jan '26", est: 1.00, act: 1.10, move: 2.5, detail: [['Actual', '1.10']] },
        { label: "Apr '26", est: 1.20, act: 1.05, move: -3.0 },
        { label: "Jul '26", est: 1.30, act: 1.30, move: 0.4 },
        { label: 'Next', est: 1.40, upcoming: true },
      ] });
      var circles = all(root, function (n) { return n.tag === 'circle'; });
      R.rings = circles.filter(function (c) { return c.attrs.fill === C.surface; }).length;
      R.dots = circles.filter(function (c) { return c.attrs.fill !== C.surface; }).map(function (c) { return c.attrs.fill; });
      R.dashed = circles.filter(function (c) { return c.attrs['stroke-dasharray']; }).length;
      R.marks = all(root, function (n) { return n.attrs && n.attrs.tabindex === '0'; }).map(function (n) { return n.attrs['aria-label']; });
      R.aria = root.attrs['aria-label'];
      R.moves = all(root, function (n) { return n.tag === 'rect' && n.attrs.fill !== 'transparent'; }).map(function (n) { return n.attrs.fill; });
      R.labels = texts(root);
      R.pos = C.pos; R.neg = C.neg;
      R.thin = dumbbellChart({ items: [{ label: 'x', est: 1, act: 1 }] });
    """)
    assert out["rings"] == 4, "every estimate is a ring, the coming one too"
    assert out["dots"] == [out["pos"], out["neg"], out["pos"]], "beat, miss, in line counts as met"
    assert out["dashed"] == 1, "the coming report's ring is dashed: an estimate with no result yet"
    assert len(out["marks"]) == 4 and "estimate 1.00, actual 1.10" in out["marks"][0]
    assert "move after +2.5%" in out["marks"][0], out["marks"][0]
    assert out["aria"] == "EPS against the estimate"
    assert out["moves"] == [out["pos"], out["neg"], out["pos"]], "the reaction strip, signed"
    assert "Next" in out["labels"] and "Move after, in the session that reacted" in out["labels"]
    assert out["thin"] is None, "one quarter is not a comparison"


def test_a_mark_reached_with_the_keyboard_says_its_figures():
    out = _jsc("""
      var root = dumbbellChart({ width: 600, items: [
        { label: 'A', est: 1, act: 2, detail: [['Actual', '2.00'], ['Estimate', '1.00']] },
        { label: 'B', est: 1, act: 0.5 } ] });
      var mark = all(root, function (n) { return n.attrs && n.attrs.tabindex === '0'; })[0];
      mark.listeners.focus[0]();
      R.tip = TIPS[TIPS.length - 1];
      R.blur = !!mark.listeners.blur;
    """)
    assert "Actual" in out["tip"] and "2.00" in out["tip"] and out["blur"]


# ------------------------------------------------------------ shares of a whole

def test_shares_are_drawn_in_proportion_and_named_in_words():
    out = _jsc("""
      var root = shareBars({ width: 700, labelWidth: 64, rows: [{ label: 'Now', values: { buy: 12, hold: 7, sell: 1 } }],
        segments: [{ key: 'buy', name: 'Buy', color: C.pos }, { key: 'hold', name: 'Hold', color: C.ink2 },
                   { key: 'sell', name: 'Sell', color: C.neg }] });
      R.widths = all(root, function (n) { return n.tag === 'rect'; }).map(function (n) { return Number(n.attrs.width); });
      R.labels = texts(root);
      R.marks = all(root, function (n) { return n.attrs && n.attrs.tabindex === '0'; }).length;
      R.empty = shareBars({ rows: [{ label: 'x', values: {} }], segments: [{ key: 'a', name: 'A', color: 'red' }] });
    """)
    plot = 700 - 64 - 44
    want = [12 / 20 * plot - 2, 7 / 20 * plot - 2, 1 / 20 * plot - 2]
    assert [round(w, 1) for w in out["widths"]] == [round(w, 1) for w in want]
    assert "Buy 60%" in out["labels"] and "Hold 35%" in out["labels"]
    assert "Sell 5%" not in out["labels"], "a sliver too narrow for its words keeps them for the hover"
    assert out["marks"] == 3 and out["empty"] is None


# ------------------------------------------------------------ columns from zero

def test_columns_start_at_zero_and_losses_hang_below_it():
    out = _jsc("""
      var root = columnChart({ width: 300, height: 140, items: [
        { label: '2023', value: -50 }, { label: '2024', value: 100 }, { label: '2025', value: 150 } ] });
      var bars = all(root, function (n) { return n.tag === 'rect' && n.attrs.fill !== 'transparent'; });
      var base = all(root, function (n) { return n.tag === 'line'; })[0];
      R.base = Number(base.attrs.y1);
      R.bars = bars.map(function (b) { return { y: Number(b.attrs.y), h: Number(b.attrs.height), fill: b.attrs.fill, op: b.attrs.opacity }; });
      R.neg = C.neg; R.brand = C.brand;
      R.one = columnChart({ items: [{ label: 'x', value: 1 }] });
    """)
    loss, a, b = out["bars"]
    assert loss["fill"] == out["neg"] and abs(loss["y"] - out["base"]) < 0.01, "a loss starts at zero and hangs down"
    assert abs(a["y"] + a["h"] - out["base"]) < 0.01 and abs(b["y"] + b["h"] - out["base"]) < 0.01
    assert b["h"] / a["h"] == pytest.approx(1.5, rel=0.01), "heights in proportion, from zero"
    assert b["op"] == "1" and a["op"] != "1", "the latest period is the one in full colour"
    assert out["one"] is None


# ------------------------------------------------------------ a range with marks on it

def test_a_range_shows_its_ends_and_each_mark_in_words():
    out = _jsc("""
      var root = rangeChart({ width: 600, low: 260, high: 380, format: function (v) { return '$' + v; },
        marks: [{ value: 320, label: 'Mean', color: C.brand }, { value: 300, label: 'Price', color: C.ink, primary: true }] });
      R.labels = texts(root);
      R.anchors = {};
      all(root, function (n) { return n.tag === 'text' && /^(Mean|Price)/.test(n.textContent); })
        .forEach(function (n) { R.anchors[n.textContent] = n.attrs['text-anchor']; });
      R.marks = all(root, function (n) { return n.attrs && n.attrs.tabindex === '0'; }).length;
      R.bad = rangeChart({ low: 5, high: 5, marks: [] });
    """)
    for want in ("Low $260", "High $380", "Mean $320", "Price $300"):
        assert want in out["labels"], want
    assert out["marks"] == 3 and out["bad"] is None
    # Close marks stand side by side, the lower one ending at its tick.
    assert out["anchors"] == {"Price $300": "end", "Mean $320": "start"}, out["anchors"]


def test_a_long_row_label_has_room():
    out = _jsc("""
      var root = divergingBars({ width: 600, labelWidth: 140, rows: [{ label: 'Current fiscal year', value: 3 }] });
      var label = all(root, function (n) { return n.tag === 'text' && n.textContent === 'Current fiscal year'; })[0];
      R.x = Number(label.attrs.x);
    """)
    assert out["x"] == 132


# ------------------------------------------------------------ a loss under its year

def test_a_negative_columns_figure_clears_the_year_under_it():
    """COIN's four-year Financials printed "-$2.6B" over "2022": a negative
    column's figure sits under the column, and the floor gave it the same 22px
    the period labels use. Checked in a browser at 1440x900 on COIN: no text
    box in any of the four charts meets another."""
    out = _jsc("""
      function rows(items) {
        var root = columnChart({ width: 320, height: 140, format: function (v) { return v + 'B'; }, items: items });
        return all(root, function (n) { return n.tag === 'text'; })
          .map(function (n) { return [n.textContent || (n.children || []).map(function (c) { return c.textContent || ''; }).join(''), Number(n.attrs.y)]; });
      }
      R.loss = rows([{ label: '2022', value: -2.6 }, { label: '2023', value: 0.1 },
                     { label: '2024', value: 2.6 }, { label: '2025', value: 1.3 }]);
      R.gain = rows([{ label: '2022', value: 3.2 }, { label: '2023', value: 3.1 },
                     { label: '2024', value: 6.6 }, { label: '2025', value: 7.2 }]);
    """)
    def y_of(rows, s):
        return next(y for t, y in rows if s in t)
    loss = out["loss"]
    # Baselines 12px apart at the micro size: the figure's descender above the year's cap height.
    assert y_of(loss, "2022") - y_of(loss, "-2.6B") >= 12, loss
    gain = out["gain"]
    assert y_of(gain, "2022") == 134, "a chart with no loss keeps its floor"
