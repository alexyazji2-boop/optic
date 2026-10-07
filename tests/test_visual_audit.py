"""The terminal-wide visualization audit: what each chart now guarantees.

Asked for as "review every chart, graph, heatmap, visual score, sparkline,
timeline, and data visualization across Optic Terminal ... every visual must
earn its place", with every final visual keeping its exact values reachable
(tooltips, accessible labels, tables) and staying keyboard accessible. The
route-by-route fixes each have their own test file; this one holds the rules
that cut across routes.
"""
from __future__ import annotations

from tests.test_visual_primitives import _jsc as _prim

SHIMS = """
  El.prototype.querySelectorAll = function (sel) { var self = this, out = []; walk(this, function (n) { if (n !== self && n.tag === sel) out.push(n); }); return out; };
  El.prototype.querySelector = function (sel) { return this.querySelectorAll(sel)[0] || null; };
  El.prototype.insertBefore = function (c) { this.children.unshift(c); return c; };
  El.prototype.removeChild = function (c) { this.children = this.children.filter(function (x) { return x !== c; }); return c; };
"""


def test_a_chart_marker_is_reached_from_the_keyboard_not_only_by_a_pointer():
    """An earnings date marked on a price chart said what it was in a native
    <title>, which a pointer can show and a keyboard cannot reach."""
    out = _prim(SHIMS + """
      var root = lineChart({ width: 500, height: 200, labels: ['a', 'b', 'c', 'd'],
        series: [{ name: 'Close', values: [1, 2, 3, 4], color: C.pos }],
        vMarkers: [{ index: 1, label: 'E', detail: 'Earnings report 2026-07-28: beat by 4%' }, { index: 2, label: 'X' }] });
      var marks = all(root, function (n) { return n.attrs && n.attrs.tabindex === '0' && n.attrs.role === 'img'; });
      R.labels = marks.map(function (n) { return n.attrs['aria-label']; });
      R.focus = marks.length ? !!marks[0].listeners.focus && !!marks[0].listeners.blur : false;
      R.hover = marks.length ? !!marks[0].listeners.pointermove || !!marks[0].listeners.mousemove : true;
    """)
    assert out["labels"] == ["Earnings report 2026-07-28: beat by 4%"], "a marker with nothing to say is not a stop"
    assert out["focus"] is True
    assert out["hover"] is False, "no hover binding to fight the crosshair"


def test_a_line_chart_is_read_point_by_point_from_the_keyboard():
    """A chart's figures were reachable only by pointing at them. The plot is a
    slider over its bars now: one stop, the arrow keys move a bar, Shift ten,
    Home and End the ends, and the value is the slider's text."""
    out = _prim(SHIMS + """
      var root = lineChart({ width: 500, height: 200, labels: ['2026-10-01', '2026-10-02', '2026-10-05'],
        series: [{ name: 'Close', values: [101.5, 102.25, 99.75], color: C.pos }], yFormat: function (v) { return v.toFixed(2); } });
      var slider = all(root, function (n) { return n.attrs && n.attrs.role === 'slider'; })[0];
      R.label = slider.attrs['aria-label']; R.max = slider.attrs['aria-valuemax']; R.tab = slider.attrs.tabindex;
      slider.listeners.focus[0]();
      R.atFocus = slider.attrs['aria-valuetext'];
      var key = function (k, shift) { slider.listeners.keydown[0]({ key: k, shiftKey: !!shift, preventDefault: function () {} }); return slider.attrs['aria-valuetext']; };
      R.left = key('ArrowLeft'); R.home = key('Home'); R.end = key('End'); R.past = key('ArrowRight', true);
      R.now = slider.attrs['aria-valuenow'];
    """)
    assert out["label"] == "Close, point by point" and out["max"] == "3" and out["tab"] == "0"
    assert out["atFocus"].endswith(": Close 99.75"), "focus starts at the latest point"
    assert out["left"].endswith(": Close 102.25") and out["home"].endswith(": Close 101.50")
    assert out["end"] == out["past"] and out["now"] == "3", "a step past the end stays on it"


def test_a_chart_is_a_group_its_marks_can_be_announced_in_and_decoration_is_hidden():
    """Every chart root was role="img", and ARIA makes an image's children
    presentational: the focusable marks inside were reached and not read."""
    out = _prim("""
      R.root = divergingBars({ width: 400, rows: [{ label: 'A', value: 2 }, { label: 'B', value: -1 }] }).attrs.role;
      R.bar = inlineBar(3, 5).attrs['aria-hidden'];
      R.spark = sparkline([1, 2, 3]).attrs['aria-hidden'];
    """)
    assert out == {"root": "group", "bar": "true", "spark": "true"}


def test_the_rotation_and_bubble_charts_are_read_from_the_keyboard():
    """Both said their figures on mouseenter only: eleven sectors on the
    rotation chart and every name on a stock map's bubble chart were
    pointer-only, and their names went into the tooltip unescaped."""
    out = _prim("""
      var rot = rotationChart([{ symbol: 'XLK', name: 'Tech & <b>Co</b>', quadrant: 'leading', d_strength: 0.4, d_momentum: 0.2,
        path: [{ strength: 101, momentum: 100.5, date: '2026-09-25' }, { strength: 102, momentum: 101, date: '2026-10-02' }] }],
        { width: 500, height: 400 });
      var bub = bubbleChart([{ label: 'AAA', name: 'A & B', x: 1, y: 2, size: 5 }, { label: 'BBB', x: 2, y: 1, size: 3 }],
        { width: 500, height: 300, xLabel: 'P/E', yLabel: 'Growth', yUnit: '%' });
      var marks = function (root) { return all(root, function (n) { return n.attrs && n.attrs.tabindex === '0'; }); };
      R.rot = marks(rot).map(function (n) { return n.attrs['aria-label']; });
      R.bub = marks(bub).map(function (n) { return n.attrs['aria-label']; });
      marks(rot)[0].listeners.focus[0]();
      R.tip = TIPS[TIPS.length - 1];
    """)
    assert out["rot"] == ["XLK Tech & <b>Co</b>: leading, strength 102.00, momentum 101.00"]
    assert sorted(out["bub"]) == ["AAA: P/E 1.00, Growth 2.00%", "BBB: P/E 2.00, Growth 1.00%"]
    assert "&lt;b&gt;" in out["tip"] and "<b>Co</b>" not in out["tip"], "a name is text, not markup"
