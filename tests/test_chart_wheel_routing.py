"""The wheel zooms the chart over a drawing and with a tool armed; a press does not.

**What was wrong.** Drawings live in `#ws-draw`, a sibling of `#ws-chart`, and
the chart under the pointer was resolved with `closest('#ws-chart')`. So a
wheel turned over a drawing found no chart: measured in the browser, fourteen
notches over a selected trend line's handle left the chart at 195 bars, and
the page scrolled instead. And the workspace's adapter reported itself off
whenever a drawing tool was armed, which is right for a press (it places a
point) and wrong for the wheel (zooming in to find a trend line's second point
is not a drawing gesture).

**And the zoom wandered.** Each notch re-centred on the bar under the pointer
rounded to a whole bar, so the moment under a still pointer drifted: 0.52,
0.18 and 0.81 of a bar on the way from 195 bars to 21, about 43px at that
zoom. The point is held for the gesture now.

Driven under JavaScriptCore against the real registry and the real adapters,
because which handler gets an event is decided by four conditions together
and reading them as text cannot tell a working conjunction from a broken one.
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
RAW = (ROOT / "static/app.js").read_text()
JSC = ("/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/"
       "Helpers/jsc")


def _exe():
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    return exe


def _out(proc):
    blob = proc.stdout + proc.stderr
    assert "RESULT:" in blob, blob[-2000:]
    return json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])


# ------------------------------------------------------------- routing


ROUTING = """
  load('tests/support/browser_stubs.js');
  document.documentElement.style = document.documentElement.style || {};
  document.documentElement.style.setProperty = function () {};
  document.documentElement.style.removeProperty = function () {};
  try { load('static/charts.js'); load('static/app.js'); } catch (e) {}

  var chartHost = { id: 'ws-chart', querySelector: function () {
    return { chartFrame: { bars: 100, plotW: 800, width: 880, margin: { l: 8 } } }; } };
  // An element that answers closest() for the ids it sits inside.
  function el(inside) {
    return { closest: function (sel) {
      if (inside.indexOf(sel) < 0) return null;
      return sel === '#ws-chart' ? chartHost : { id: sel.slice(1) }; } };
  }
  document.getElementById = function (id) { return id === 'ws-chart' ? chartHost : null; };
  STATE.view = 'chart'; STATE.chartData = { ticker: 'SPY' };
  function who(inside, wheel) {
    var hit = chartZoomTarget({ target: el(inside) }, wheel ? { wheel: true } : undefined);
    return hit ? hit.host.id : null;
  }
  var R = {};
"""


def _routing(scenario):
    proc = subprocess.run([_exe(), "-e", ROUTING + scenario + "\nprint('RESULT:' + JSON.stringify(R));"],
                          capture_output=True, text=True, timeout=120, cwd=str(ROOT))
    return _out(proc)


def test_the_wheel_over_a_drawing_zooms_its_chart():
    out = _routing("""
      wsTool = 'cursor';
      R.wheel = who(['#ws-draw'], true);
      R.press = who(['#ws-draw'], false);
    """)
    assert out["wheel"] == "ws-chart", "the wheel over a drawing must reach the chart"
    # A press there grabs the drawing. If it resolved the chart, the pan would
    # take the drag that moves the drawing.
    assert out["press"] is None


def test_the_wheel_zooms_with_a_tool_armed_and_a_press_still_draws():
    out = _routing("""
      wsTool = 'trend';
      R.wheel = who(['#ws-chart'], true);
      R.wheelOverDrawing = who(['#ws-draw'], true);
      R.press = who(['#ws-chart'], false);
    """)
    assert out["wheel"] == "ws-chart"
    assert out["wheelOverDrawing"] == "ws-chart"
    assert out["press"] is None, "an armed tool's press places a point, it is no pan"


def test_nothing_else_on_the_page_is_taken_for_the_chart():
    out = _routing("""
      wsTool = 'cursor';
      R.elsewhere = who(['#somewhere-else'], true);
      STATE.view = 'home';
      R.otherView = who(['#ws-draw'], true);
    """)
    assert out == {"elsewhere": None, "otherView": None}


def test_only_the_workspace_lends_its_overlay_to_the_wheel():
    """The Options charts have no drawing layer, so nothing there changed."""
    adapters = re.findall(r"registerChartZoom\('([\w-]+)', \{(.*?)\n\}\);", RAW, re.S)
    overlays = {host: "overlay:" in body for host, body in adapters}
    assert overlays == {"ws-chart": True, "chart-price": False, "chart-weekly": False}, overlays


# ------------------------------------------------------------- the anchor


def _raw_fn(name):
    start = RAW.index("function %s(" % name)
    end = RAW.index("\n}\n", start) + 2
    return RAW[start:end]


ANCHOR = """
  var frames = []; function requestAnimationFrame(f) { frames.push(f); return frames.length; }
  var chartWheel = null, chartWheelFrame = 0, chartGesture = null, chartInteractive = false;
  %s
  %s
  var win, total = 1739;
  var adapter = {
    window: function () { return { from: win.from, to: win.to, total: total }; },
    apply: function (w) {
      var span = Math.max(WS_MIN_BARS, Math.min(total, w.to - w.from));
      var from = Math.max(0, Math.min(total - span, w.from));
      if (from === win.from && from + span === win.to) return false;
      win = { from: from, to: from + span }; return true;
    },
    redraw: function () {},
  };
  function frame() { return { plotW: 800, width: 880, bars: win.to - win.from, margin: { l: 8 } }; }
  var svg = { getBoundingClientRect: function () { return { width: 880 }; } };
  Object.defineProperty(svg, 'chartFrame', { get: frame });
  var target = { host: { querySelector: function () { return svg; } }, svg: svg, adapter: adapter };
  // The position under a still pointer, over the whole series, after a notch.
  function under(fx) { return win.from + fx * (win.to - win.from - 1); }
  function notches(fx, held) {
    win = { from: total - 195, to: total };
    chartWheel = null;
    var start = under(fx), worst = 0;
    for (var n = 0; n < 16; n += 1) {
      var span = win.to - win.from;
      if (!chartWheel) chartWheel = { target: target, bar: 0, zoomLog: 0, panPx: 0 };
      // What the wheel handler records for a pointer that has not moved.
      chartWheel.bar = Math.round(fx * (span - 1));
      if (held) {
        if (!Number.isFinite(chartWheel.abs)) {
          chartWheel.abs = under(fx); chartWheel.fx = fx; chartWheel.x = 100; chartWheel.win = adapter.window();
        }
      } else {
        chartWheel.abs = NaN;    // the old way: re-centred on the bar every notch
      }
      chartWheel.zoomLog += -100 * ZOOM_PER_PX;
      flushChartWheel();
      worst = Math.max(worst, Math.abs(under(fx) - start));
    }
    return { worst: worst, span: win.to - win.from };
  }
"""


def _anchor(scenario):
    consts = "\n".join(re.search(r"^const %s = [^\n]*;" % name, RAW, re.M).group()
                       for name in ("ZOOM_PER_PX", "PINCH_PER_PX", "WS_MIN_BARS"))
    fns = "\n".join(_raw_fn(n) for n in ("zoomedWindow", "zoomedWindowAt", "chartMayAct",
                                          "flushChartWheel", "chartBarsPerPixel",
                                          "interactiveRedraw"))
    src = ANCHOR % (consts, fns) + "\nvar R = {};\n" + scenario + "\nprint('RESULT:' + JSON.stringify(R));"
    proc = subprocess.run([_exe(), "-e", src], capture_output=True, text=True, timeout=60)
    return _out(proc)


def test_a_still_pointer_keeps_its_moment_through_a_whole_zoom():
    """Sixteen notches in, at pointer positions across the plot. The window is
    whole bars, so a step can land half a bar either side; held, that is the
    most it ever is. The pre-fix rule, re-centring on the rounded bar each
    notch, is run through the same notches as the control: it must exceed
    half a bar somewhere, or this test could not tell the two apart."""
    out = _anchor("""
      R.held = []; R.old = [];
      [0.13, 0.37, 0.5, 0.61, 0.88].forEach(function (fx) {
        R.held.push(notches(fx, true)); R.old.push(notches(fx, false));
      });
    """)
    for run in out["held"]:
        assert run["worst"] <= 0.5 + 1e-9, out["held"]
        assert run["span"] < 40, "and it did zoom in"
    assert max(r["worst"] for r in out["old"]) > 0.5, out["old"]


def test_the_anchor_follows_a_pan_inside_the_same_gesture():
    """A diagonal trackpad stroke pans and zooms at once. The paper moves under
    the pointer, so the held point has to move with it, or the next zoom step
    would pull the chart back to where the pan started."""
    fn = _raw_fn("flushChartWheel")
    pan = fn[fn.index("if (w.panPx) {"):]
    assert "if (Number.isFinite(w.abs)) w.abs += bars;" in pan[:pan.index("\n  }\n")]


def test_the_anchor_is_retaken_when_something_else_moved_the_window():
    """A drag-pan or a range pill between two wheel gestures leaves a held point
    that is no longer under the pointer. The handler compares the window with
    the one its own last step left (`w.win`), and re-reads the point when they
    differ or the pointer has moved."""
    handler = RAW[RAW.index("document.addEventListener('wheel', (evt) => {"):]
    handler = handler[:handler.index("}, { passive: false });")]
    assert "const ours = chartWheel.win && chartWheel.win.from === cur.from && chartWheel.win.to === cur.to;" in handler
    assert "const still = Number.isFinite(chartWheel.x) && Math.abs(evt.clientX - chartWheel.x) <= 1;" in handler
    assert "if (fx !== null && !(ours && still && Number.isFinite(chartWheel.abs))) {" in handler
    assert "w.win = target.adapter.window();" in _raw_fn("flushChartWheel")
