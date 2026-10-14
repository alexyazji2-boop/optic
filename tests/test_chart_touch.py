"""A finger on a chart: pan, pinch, hold to read, hold and a second finger to measure.

Reported 2026-10-14 from a phone: "zooming in and out on the phone version for
charting does not work, as well as dragging it left and right". Measured in
Mobile Safari on an iPhone 17 simulator (iOS 27), Charting tab, before the fix:
a one-finger drag left the window at bars 10 to 72 (the pan declined every
touch, and the finger scrubbed the readout), and fingers spread to three times
their distance zoomed one step, 78 bars to 62, then stopped, because the redraw
replaced the SVG under the fingers and every later event went to that detached
node. After it: the same pinch gives 26 bars, a 100px drag moves 14 bars, a
vertical swipe scrolls the page 269px and leaves the window alone, and the page
zoom (visualViewport.scale) stays 1 throughout.

Three layers, each run under JavaScriptCore:
- the pure maths (which way a finger went, the pinch's scale and window);
- app.js's touch handler, lifted out with the mouse pan and Safari's gesture
  handlers it shares the page with, on stub charts;
- charts.js's side, on the recording DOM: which touch moves the readout takes,
  and when two fingers measure, preventDefault or neither.
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
CHARTS = (ROOT / "static/charts.js").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _jsc():
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    return exe


def _fn(name):
    return re.search(r"^function %s\([^\n]*\) \{.*?^\}" % name, APP, re.M | re.S).group()


def _span(start, end):
    """From `start` through the end of `end`, as written in app.js."""
    a = APP.index(start)
    return APP[a:APP.index(end, a) + len(end)]


def _run(src):
    out = subprocess.run([_jsc(), "-e", src], capture_output=True, text=True, timeout=30)
    last = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else ""
    assert last.startswith("{"), out.stdout + out.stderr
    return json.loads(last)


# ------------------------------------------------------------------ the maths

MATHS = "\n".join(_fn(n) for n in ("touchLock", "pinchScale", "zoomedWindowAt", "pinchedWindow"))


def _maths(body):
    return _run("var WS_MIN_BARS = 12;\n" + MATHS + "\nvar R = {};\n" + body
                + "\nprint(JSON.stringify(R));")


def test_a_finger_is_sideways_or_upright_only_once_it_has_gone_the_slop():
    r = _maths("""
      R.still = touchLock(3, 2, 8);
      R.right = touchLock(8, 0, 8);
      R.left = touchLock(-12, 3, 8);
      R.up = touchLock(5, -9, 8);
      R.tie = touchLock(8, 8, 8);
    """)
    assert r["still"] is None
    assert r["right"] == "x" and r["left"] == "x"
    assert r["up"] == "y"
    # A diagonal is the page's: pan-y hands it to the browser's scroll.
    assert r["tie"] == "y"


def test_the_scale_is_the_ratio_of_the_two_fingers_distances():
    r = _maths("""
      R.spread = pinchScale({x: 0, y: 0}, {x: 100, y: 0}, {x: -50, y: 0}, {x: 150, y: 0});
      R.closer = pinchScale({x: 0, y: 0}, {x: 100, y: 0}, {x: 25, y: 0}, {x: 75, y: 0});
      R.upright = pinchScale({x: 0, y: 0}, {x: 0, y: 60}, {x: 0, y: -30}, {x: 0, y: 90});
      R.together = pinchScale({x: 5, y: 5}, {x: 5, y: 5}, {x: 0, y: 0}, {x: 9, y: 0});
    """)
    assert r["spread"] == 2 and r["closer"] == 0.5 and r["upright"] == 2
    assert r["together"] == 1, "two fingers on one point have no distance to scale"


def test_a_pinch_keeps_the_bar_under_its_midpoint_and_its_start_window_when_still():
    r = _maths("""
      var start = { from: 100, to: 200, total: 500 };
      var fx = 0.3, abs = start.from + fx * 99;
      R.still = pinchedWindow(start, abs, fx, 1);
      R.twice = pinchedWindow(start, abs, fx, 2);
      R.again = pinchedWindow(start, abs, fx, 2);
      R.closest = pinchedWindow(start, abs, fx, 100);
      R.widest = pinchedWindow(start, abs, fx, 0.001);
      // Both fingers moved right a tenth of the plot, apart by nothing.
      R.moved = pinchedWindow(start, abs, fx + 0.1, 1);
    """)
    assert r["still"] == {"from": 100, "to": 200}
    # From the start window every move, so scale is never applied twice.
    assert r["twice"] == r["again"] and r["twice"]["to"] - r["twice"]["from"] == 50
    bar = 100 + 0.3 * 99
    w = r["twice"]
    assert abs((w["from"] + 0.3 * 49) - bar) <= 0.5, "the bar under the midpoint stays under it"
    assert r["closest"]["to"] - r["closest"]["from"] == 12
    assert r["widest"]["to"] - r["widest"]["from"] == 500
    # The paper follows the fingers: right shows earlier bars, the span held.
    assert r["moved"] == {"from": 90, "to": 190}


# ----------------------------------------------------- app.js's touch handler

PAGE = """
var L = {};
var document = { addEventListener: function (t, f) { (L[t] = L[t] || []).push(f); },
                 body: { classList: { add: function () {}, remove: function () {} } } };
function fire(type, e) { (L[type] || []).forEach(function (f) { f(e); }); }
var RAF = [];
function requestAnimationFrame(f) { RAF.push(f); return RAF.length; }
function flush() { var q = RAF; RAF = []; q.forEach(function (f) { f(); }); }
var TIMERS = [];
function setTimeout(f, ms) { TIMERS.push({ f: f, ms: ms }); return TIMERS.length; }
function clearTimeout(id) { if (id && TIMERS[id - 1]) TIMERS[id - 1].dead = true; }
function wait(ms) {
  TIMERS.forEach(function (t) { if (!t.dead && !t.done && t.ms <= ms) { t.done = true; t.f(); } });
}
var WS_MIN_BARS = 12;
var chartGesture = null;
var WIN = { from: 100, to: 200, total: 500 };
var REDRAWS = 0, QUIET = 0, CAPTURED = [];
var frame = { clearReadout: function () { QUIET++; } };
var svg = { chartFrame: frame };
var HOST = { dataset: {}, setPointerCapture: function (id) { CAPTURED.push(id); },
             querySelector: function (sel) { return sel === 'svg.chart' ? svg : null; } };
var adapter = {
  window: function () { return { from: WIN.from, to: WIN.to, total: WIN.total }; },
  apply: function (w) {
    var span = Math.min(w.to - w.from, WIN.total);
    var from = Math.max(0, Math.min(w.from, WIN.total - span));
    if (from === WIN.from && from + span === WIN.to) return false;
    WIN = { from: from, to: from + span, total: WIN.total };
    return true;
  },
};
function interactiveRedraw(a) { REDRAWS++; }
function chartZoomTarget(evt) { return evt.onChart ? { host: HOST, svg: svg, frame: frame, adapter: adapter } : null; }
function chartZoomHost(evt) { return evt.onChart ? { host: HOST, adapter: adapter } : null; }
function chartBarsPerPixel() { return 0.5; }
function chartBarUnderCursor() { return 10; }
// 400px of plot from x = 0.
function chartPointerFraction(t, e, o) {
  var fx = e.clientX / 400;
  return o && o.clamp ? Math.max(0, Math.min(1, fx)) : fx;
}
var PREVENTED = 0;
function ev(id, x, y, more) {
  var e = { pointerType: 'touch', pointerId: id, isPrimary: id === 1, clientX: x, clientY: y,
            button: 0, onChart: true, shiftKey: false, timeStamp: 1,
            preventDefault: function () { PREVENTED++; },
            target: { scale: false, closest: function (sel) {
              return sel === '[data-price-scale]' && this.scale ? {} : null; } } };
  for (var k in more || {}) e[k] = more[k];
  return e;
}
function down(id, x, y, more) { fire('pointerdown', ev(id, x, y, more)); }
function move(id, x, y, more) { fire('pointermove', ev(id, x, y, more)); }
function up(id, x, y, more) { fire('pointerup', ev(id, x, y, more)); }
function state() {
  return { mode: HOST.dataset.chartTouch || null, win: [WIN.from, WIN.to], redraws: REDRAWS,
           quiet: QUIET, captured: CAPTURED.slice(), pan: !!wsPan, frames: RAF.length,
           gesture: !!chartGesture, prevented: PREVENTED };
}
var R = {};
"""


def _page(body):
    # In the order app.js registers them: Safari's gesture handlers, then the
    # touch handler, then the mouse's pan, whose release listeners come last.
    src = (PAGE + _fn("zoomedWindow") + "\n" + _fn("zoomedWindowAt") + "\n"
           + _span("document.addEventListener('gesturestart'",
                   "  chartGesture = null;\n}, { passive: false });") + "\n"
           + _span("const TOUCH_LOCK_PX = 8;", "document.addEventListener('pointercancel', chartTouchLift);")
           + "\n" + _span("let wsPan = null;", "  document.body.classList.remove('ws-panning');\n}")
           + "\ndocument.addEventListener('pointerup', wsEndPan);"
           + "\ndocument.addEventListener('pointercancel', wsEndPan);\n"
           + body + "\nprint(JSON.stringify(R));")
    return _run(src)


def test_a_sideways_finger_pans_through_the_mouse_pan_once_a_frame():
    r = _page("""
      down(1, 100, 100);
      R.down = state();
      move(1, 104, 101);
      R.slop = state();
      move(1, 130, 102);
      move(1, 140, 102);
      R.moving = state();
      flush();
      R.drawn = state();
      up(1, 140, 102);
      R.up = state();
    """)
    assert r["down"]["mode"] == "wait" and not r["down"]["pan"]
    assert r["slop"]["mode"] == "wait", "4px is a finger held still"
    assert r["moving"]["mode"] == "pan" and r["moving"]["pan"]
    # Two moves, one frame: drawn once, at the last.
    assert r["moving"]["frames"] == 1 and r["moving"]["redraws"] == 0
    # 40px at half a bar a pixel, from the press: 20 bars earlier.
    assert r["drawn"]["win"] == [80, 180] and r["drawn"]["redraws"] == 1
    # The readout went once the bars began to move, and the finger is held on
    # the host, which survives the redraw.
    assert r["moving"]["quiet"] == 1 and r["moving"]["captured"] == [1]
    assert r["up"]["mode"] is None and not r["up"]["pan"]


def test_an_upright_finger_is_the_pages_and_moves_nothing():
    r = _page("""
      down(1, 100, 100);
      move(1, 102, 130);
      move(1, 140, 160);
      flush();
      R.after = state();
      fire('pointercancel', ev(1, 140, 160));
      R.cancel = state();
    """)
    assert r["after"]["mode"] == "page" and not r["after"]["pan"]
    assert r["after"]["win"] == [100, 200] and r["after"]["redraws"] == 0
    assert r["cancel"]["mode"] is None


def test_a_held_finger_reads_and_never_pans():
    r = _page("""
      down(1, 100, 100);
      wait(300);
      R.held = state();
      move(1, 160, 100);
      move(1, 220, 140);
      flush();
      R.after = state();
    """)
    assert r["held"]["mode"] == "hold"
    assert r["after"]["mode"] == "hold" and r["after"]["win"] == [100, 200] and not r["after"]["pan"]


def test_a_move_before_the_hold_is_up_cancels_it():
    r = _page("""
      down(1, 100, 100);
      move(1, 120, 100);
      wait(300);
      R.after = state();
    """)
    assert r["after"]["mode"] == "pan"


def test_two_fingers_pinch_about_their_midpoint():
    r = _page("""
      down(1, 100, 100);
      down(2, 200, 100);
      R.two = state();
      move(2, 250, 100);
      move(2, 300, 100);
      R.moving = state();
      flush();
      R.drawn = state();
    """)
    assert r["two"]["mode"] == "pinch" and r["two"]["captured"] == [1, 2]
    assert r["moving"]["frames"] == 1, "one repaint a frame"
    # Distance 100 to 200 halves the 100 bars. The midpoint was 150px in, 0.375
    # of the plot, over bar 137.125; it is at 200px now, half way, and that
    # bar is under it: 137.125 - 0.5 * 49 rounds to 113.
    assert r["drawn"]["win"] == [113, 163] and r["drawn"]["redraws"] == 1


def test_each_frame_of_a_pinch_is_measured_from_the_window_it_began_on():
    """Scale is from the start of the pinch, so a pinch drawn over several
    frames must land where one drawn in a single frame does."""
    r = _page("""
      down(1, 100, 100);
      down(2, 200, 100);
      move(2, 250, 100);
      flush();
      R.half = state();
      move(2, 300, 100);
      flush();
      R.drawn = state();
    """)
    assert r["half"]["redraws"] == 1
    assert r["drawn"]["win"] == [113, 163] and r["drawn"]["redraws"] == 2


def test_lifting_one_finger_of_a_pinch_pans_with_the_other():
    r = _page("""
      down(1, 100, 100);
      down(2, 200, 100);
      move(2, 300, 100);
      flush();
      up(2, 300, 100);
      R.lifted = state();
      move(1, 100, 100);
      move(1, 140, 100);
      flush();
      R.after = state();
    """)
    assert r["lifted"]["mode"] == "pan" and not r["lifted"]["pan"]
    # From where the finger was when it took over: 40px is 20 bars earlier.
    assert r["after"]["win"] == [93, 143]


def test_hold_then_a_second_finger_measures_and_moves_nothing():
    r = _page("""
      down(1, 100, 100);
      wait(300);
      down(2, 260, 100);
      R.two = state();
      move(2, 300, 100);
      flush();
      R.after = state();
      up(2, 300, 100);
      R.one = state();
    """)
    assert r["two"]["mode"] == "measure"
    assert r["after"]["win"] == [100, 200] and r["after"]["redraws"] == 0
    assert r["one"]["mode"] == "hold", "the finger left reads again"


def test_with_every_bar_on_screen_a_finger_reads_and_two_still_zoom():
    r = _page("""
      WIN = { from: 0, to: 500, total: 500 };
      down(1, 100, 100);
      R.down = state();
      move(1, 160, 100);
      R.moved = state();
      down(2, 300, 100);
      move(2, 400, 100);
      flush();
      R.pinched = state();
    """)
    assert r["down"]["mode"] == "scrub" and r["moved"]["mode"] == "scrub" and not r["moved"]["pan"]
    assert r["pinched"]["mode"] == "pinch"
    assert r["pinched"]["win"][1] - r["pinched"]["win"][0] < 500


def test_a_pinch_may_begin_with_a_finger_on_the_price_scale():
    """The scale is 74px of a 365px chart on an iPhone 17. The first pinch-in
    tried there did nothing, because the handler declined that finger."""
    r = _page("""
      down(1, 330, 100, { target: { scale: true, closest: function (s) {
        return s === '[data-price-scale]' ? {} : null; } } });
      R.one = state();
      move(1, 330, 160);
      R.stretch = state();
      down(2, 250, 100);
      R.two = state();
    """)
    assert r["one"]["mode"] == "scale" and r["stretch"]["mode"] == "scale" and not r["stretch"]["pan"]
    assert r["two"]["mode"] == "pinch"


def test_safari_gesture_events_stand_aside_for_a_touch_pinch():
    r = _page("""
      down(1, 100, 100);
      down(2, 200, 100);
      fire('gesturestart', ev(0, 150, 100, { scale: 1 }));
      fire('gesturechange', ev(0, 150, 100, { scale: 3 }));
      flush();
      R.touch = state();
      fire('gestureend', ev(0, 150, 100, { scale: 3 }));
      up(1, 100, 100); up(2, 200, 100);
      // A trackpad's pinch, with no finger on the page, is still theirs.
      WIN = { from: 100, to: 200, total: 500 };
      fire('gesturestart', ev(0, 150, 100, { scale: 1 }));
      fire('gesturechange', ev(0, 150, 100, { scale: 2 }));
      R.trackpad = state();
    """)
    assert r["touch"]["win"] == [100, 200], "the pinch is applied once, by the pointer path"
    assert not r["touch"]["gesture"] and r["touch"]["prevented"] >= 2
    assert r["trackpad"]["gesture"] and r["trackpad"]["win"][1] - r["trackpad"]["win"][0] == 50


def test_a_mouse_never_starts_a_touch_gesture():
    r = _page("""
      fire('pointerdown', ev(1, 100, 100, { pointerType: 'mouse' }));
      R.after = state();
    """)
    assert r["after"]["mode"] is None
    assert r["after"]["pan"], "the mouse's own pan took it, as before"


def test_a_new_first_finger_clears_a_gesture_whose_release_was_lost():
    r = _page("""
      down(1, 100, 100);
      down(2, 200, 100);
      // Both releases lost; then a fresh touch.
      fire('pointerdown', ev(7, 50, 100, { isPrimary: true }));
      R.fresh = state();
    """)
    assert r["fresh"]["mode"] == "wait"


def test_the_touch_handler_is_registered_before_the_mouse_pan():
    """The move that decides a drag is sideways hands it to the pan, which then
    moves the chart in that same event."""
    assert APP.index("const TOUCH_LOCK_PX = 8;") < APP.index("let wsPan = null;")


# ------------------------------------------------------------- charts.js's side

CHART_HARNESS = """
  var baseMk = mk;
  mk = function (tag) {
    var n = baseMk(tag);
    n.on = {};
    n.addEventListener = function (type, f) { (this.on[type] = this.on[type] || []).push(f); };
    n.closest = function (sel) {
      var key = sel.slice(6, -1).replace(/-([a-z])/g, function (_, c) { return c.toUpperCase(); });
      for (var e = this; e; e = e.parentNode) if (e.dataset && e.dataset[key] !== undefined) return e;
      return null;
    };
    return n;
  };
  var RAF = [];
  requestAnimationFrame = function (f) { RAF.push(f); return RAF.length; };
  cancelAnimationFrame = function () {};
"""

CHART_SCENE = """
  var SHOWN = 0;
  showTip = function () { SHOWN++; };
  hideTip = function () {};
  var N = 40, values = [], labels = [];
  for (var i = 0; i < N; i++) { values.push(100 + i); labels.push('d' + i); }
  var svg = lineChart({ width: 600, height: 300, labels: labels, panDrag: %(pan)s,
                        series: [{ name: 'Close', values: values, color: '#123456' }] });
  var host = mk('div'); host.appendChild(svg);
  var overlay = NODES.filter(function (x) {
    return x.tag === 'rect' && x.attrs.style === 'cursor:crosshair';
  })[0];
  var group = NODES.filter(function (x) {
    return x.tag === 'g' && x.children.map(function (c) { return c.tag; }).join()
      === 'rect,line,line,circle,circle,text';
  })[0];
  var label = group.children[5];
  var f = svg.chartFrame;
  function at(bar) { return (f.margin.l + bar / (N - 1) * f.plotW) * 900 / f.width; }
  function fire(type, evt) { (overlay.on[type] || []).slice().forEach(function (h) { h(evt); }); }
  function flush() { var q = RAF; RAF = []; q.forEach(function (g) { g(); }); }
  function touchmove(n) {
    var e = { touches: [{ clientX: at(5) }, { clientX: at(30) }].slice(0, n), prevented: false,
              preventDefault: function () { this.prevented = true; } };
    fire('touchmove', e);
    var shown = group.attrs.opacity === '1' ? label.textContent : '';
    return { prevented: e.prevented, measured: shown.indexOf('%%') >= 0 };
  }
  function pmove(type, bar) {
    var before = SHOWN;
    fire('pointermove', { pointerType: type, pointerId: 1, clientX: at(bar), clientY: 100,
                          pressure: 0.5, buttons: 1 });
    flush();
    return SHOWN > before;
  }
  var R = {};
"""


def _chart(body, pan=True):
    src = ((ROOT / "tests/support/recording_dom.js").read_text() + CHART_HARNESS
           + CHARTS + CHART_SCENE % {"pan": json.dumps(pan)} + body
           + "\nprint(JSON.stringify(R));")
    return _run(src)


def test_two_fingers_on_a_chart_that_pans_pinch_rather_than_measure():
    r = _chart("""
      host.dataset.chartTouch = 'pinch';
      R.pinch = touchmove(2);
      // Redrawn out from under the fingers mid-pinch: still the pinch's.
      svg.isConnected = false; svg.parentNode = null;
      R.detached = touchmove(2);
      svg.isConnected = true; svg.parentNode = host;
      host.dataset.chartTouch = 'measure';
      R.measure = touchmove(2);
    """)
    assert r["pinch"] == {"prevented": True, "measured": False}
    assert r["measure"] == {"prevented": True, "measured": True}
    assert r["detached"] == {"prevented": True, "measured": False}


def test_one_finger_keeps_the_page_until_it_pans_or_holds():
    r = _chart("""
      host.dataset.chartTouch = 'wait'; R.wait = touchmove(1);
      host.dataset.chartTouch = 'page'; R.page = touchmove(1);
      host.dataset.chartTouch = 'scrub'; R.scrub = touchmove(1);
      host.dataset.chartTouch = 'pan'; R.pan = touchmove(1);
      host.dataset.chartTouch = 'hold'; R.hold = touchmove(1);
    """)
    for free in ("wait", "page", "scrub"):
        assert r[free]["prevented"] is False, free
    for held in ("pan", "hold"):
        assert r[held]["prevented"] is True, held


def test_every_other_chart_keeps_its_two_finger_measure():
    r = _chart("""
      R.two = touchmove(2);
      R.one = touchmove(1);
    """, pan=False)
    assert r["two"] == {"prevented": True, "measured": True}
    assert r["one"]["prevented"] is False


def test_a_finger_reads_the_bars_only_once_held_or_with_nothing_to_pan():
    r = _chart("""
      R.press = pmove('touch', 10);
      host.dataset.chartTouch = 'wait'; R.wait = pmove('touch', 12);
      host.dataset.chartTouch = 'pan'; R.pan = pmove('touch', 14);
      host.dataset.chartTouch = 'pinch'; R.pinch = pmove('touch', 16);
      host.dataset.chartTouch = 'hold'; R.hold = pmove('touch', 18);
      host.dataset.chartTouch = 'scrub'; R.scrub = pmove('touch', 20);
      // A mouse hovers as it always has, whatever a finger left on the host.
      host.dataset.chartTouch = 'pan'; R.mouse = pmove('mouse', 22);
      R.clear = typeof f.clearReadout;
    """)
    assert r["press"] is True, "no state yet: the press reads at once, so a tap shows its bar"
    assert r["wait"] is False and r["pan"] is False and r["pinch"] is False
    assert r["hold"] is True and r["scrub"] is True
    assert r["mouse"] is True
    assert r["clear"] == "function"


def test_a_press_still_reads_its_bar_at_once():
    """Hover-speed contract (tests/test_chart_hover_speed.py): the scrub's
    pointerdown reports straight away, and moves stay once a frame."""
    scrub = CHARTS[CHARTS.index("function bindScrub("):]
    scrub = scrub[:scrub.index("\n}\n")]
    down = scrub[scrub.index("el.addEventListener('pointerdown'"):]
    assert "onMove(evt);" in down[:down.index("});")]


def test_the_price_scale_stretch_is_one_fingers_gesture():
    grip = CHARTS[CHARTS.index("    grip.addEventListener('pointerdown', (evt) => {"):]
    grip = grip[:grip.index("\n    });")]
    assert "if (evt.pointerType === 'touch' && touchMode()) return;" in grip
    assert "const other = (e) => { if (e.pointerId !== evt.pointerId) end(); };" in grip
    assert "window.removeEventListener('pointerdown', other);" in grip


def test_a_held_finger_selects_no_text():
    """Measured on the simulator: a 1.3s hold on the plot selected the "14:00"
    axis label and drew Safari's selection handles over the chart."""
    css = (ROOT / "static/styles.css").read_text()
    rule = css[css.index("#ws-chart, #chart-price, #chart-weekly {"):]
    rule = rule[:rule.index("}")]
    assert "-webkit-user-select: none;" in rule and "-webkit-touch-callout: none;" in rule
    hosts = sorted(re.findall(r"^registerChartZoom\('([\w-]+)'", APP, re.M))
    assert hosts == ["chart-price", "chart-weekly", "ws-chart"], "a new zoomable chart joins the rule"


def test_the_hint_names_a_fingers_gestures_on_a_touch_screen():
    """The status strip said "scroll to zoom" and "hold then drag to measure"
    on a phone, where there is no wheel and a hold reads the bars."""
    hint = APP[APP.index("// A finger has no wheel, and its hold reads the bars (chartTouch)."):]
    hint = hint[:hint.index("]")]
    assert "window.matchMedia('(pointer: coarse)').matches" in hint
    assert "'Drag to pan, pinch to zoom, hold then drag to read'" in hint
    assert "'Drag to pan, hold then drag to measure, scroll to zoom'" in hint
