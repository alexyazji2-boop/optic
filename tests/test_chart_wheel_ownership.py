"""One wheel gesture, one owner (2026-10-12).

Reported: "when I scroll down on the chart, it is inconsistent between
zooming out the chart and scrolling down the tab". Measured with real wheel
events in headless Chrome at 1440x700 on the Charting tab with RSI and MACD:

* A trackpad stroke begun above the chart scrolled the page for two events,
  then the chart rose under the pointer and took the other 28 as zoom.
* The price plot zoomed; its price axis swallowed the event; the RSI and MACD
  panes and the plot's left margin scrolled the page.
* Zoomed fully out, a scroll down over the chart did nothing: no zoom and no
  page scroll.

Now a gesture belongs to whatever it began on until it pauses
(WHEEL_LATCH_MS), the panes and the axis margins zoom the chart they sit in,
and a gesture that begins on a chart with nowhere to go that way is the
page's. After the change, the same measurement: the stroke from above scrolled
the page to its end and never zoomed; plot, axis, margins and both panes
zoomed; a fresh scroll over the fully zoomed-out chart scrolled the page.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
RAW = (ROOT / "static/app.js").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _raw_fn(name: str) -> str:
    return re.search(r"^function " + name + r"\([^\n]*\) \{.*?^\}", RAW, re.M | re.S).group()


def _handler() -> str:
    at = RAW.index("document.addEventListener('wheel', (evt) => {")
    return RAW[at:RAW.index("}, { passive: false });", at)]


def _run(scenario: str) -> str:
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    consts = "\n".join(re.search(r"^const %s = [^\n]*;" % n, RAW, re.M).group()
                       for n in ("WS_MIN_BARS",))
    src = ("function assert(v, m) { if (!v) throw new Error(m); }\n" + consts + "\n"
           + _raw_fn("wheelPixels") + "\n" + _raw_fn("chartWheelHasRoom") + "\n"
           + _raw_fn("chartBarUnderCursor") + "\n" + _raw_fn("chartPointerFraction") + "\n"
           + scenario + "\nprint('OK');")
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=20)
    assert out.stdout.strip().endswith("OK"), out.stdout + out.stderr
    return out.stdout


def test_a_chart_with_nothing_to_show_hands_the_scroll_to_the_page():
    _run("""
      var at = function (from, to, total) { return { adapter: { window: function () { return { from: from, to: to, total: total }; } } }; };
      var wheel = function (dy, dx, extra) { var e = { deltaX: dx || 0, deltaY: dy, deltaMode: 0, ctrlKey: false, shiftKey: false };
        for (var k in (extra || {})) e[k] = extra[k]; return e; };
      assert(chartWheelHasRoom(at(0, 50, 200), wheel(100)), 'zoomed in, scrolling out: the chart');
      assert(!chartWheelHasRoom(at(0, 200, 200), wheel(100)), 'every bar shown, scrolling out: the page');
      assert(chartWheelHasRoom(at(0, 200, 200), wheel(-100)), 'every bar shown, scrolling in: the chart');
      assert(!chartWheelHasRoom(at(10, 10 + WS_MIN_BARS, 200), wheel(-100)), 'closest zoom, scrolling in: the page');
      assert(chartWheelHasRoom(at(0, 200, 200), wheel(5, 80)), 'a sideways swipe pans: the chart');
      assert(chartWheelHasRoom(at(0, 200, 200), wheel(100, 0, { ctrlKey: true })), 'a pinch is always the chart');
    """)


def test_the_margins_and_the_price_axis_anchor_at_the_nearest_edge():
    _run("""
      var frame = { width: 1000, margin: { l: 50 }, plotW: 880, bars: 100,
                    indexAt: function (px) { return Math.floor((px - 50) / 8.8); } };
      var svg = { getBoundingClientRect: function () { return { left: 0, width: 1000 }; } };
      var t = { svg: svg, frame: frame };
      assert(chartBarUnderCursor(t, { clientX: 960 }) === null, 'unclamped: off the plot');
      assert(chartBarUnderCursor(t, { clientX: 960 }, { clamp: true }) === 99, 'price axis: the last bar');
      assert(chartBarUnderCursor(t, { clientX: 10 }, { clamp: true }) === 0, 'left margin: the first bar');
      assert(chartPointerFraction(t, { clientX: 960 }, { clamp: true }) === 1, 'fraction clamps to the right edge');
      assert(chartPointerFraction(t, { clientX: 960 }) === null, 'unclamped fraction: off the plot');
    """)


def test_a_gesture_keeps_the_owner_it_began_with():
    fn = _handler()
    assert "const WHEEL_LATCH_MS = 200;" in RAW
    # A page scroll in progress stays the page's when the chart passes under it.
    assert "if (latched && latched.owner === 'page' && !evt.ctrlKey) {" in fn
    # A zoom in progress stays the chart's when the pointer drifts off it.
    assert "if (latched && chartWheel && chartWheel.target.host === latched.owner" in fn
    # A new gesture with nowhere to go on the chart is the page's.
    assert "} else if (!latched && !chartWheelHasRoom(target, evt)) {" in fn
    assert "wheelLatch = { owner: target.host, at: now };\n  evt.preventDefault();" in fn


def test_the_panes_and_axes_zoom_the_chart_they_belong_to():
    assert "if (wheel && adapter.panes && evt.target.closest(adapter.panes)) {" in _raw_fn("chartHostFor")
    reg = RAW[RAW.index("registerChartZoom('ws-chart', {"):]
    assert "panes: '.ws-pane'," in reg[:reg.index("});")]
    fn = _handler()
    assert "chartBarUnderCursor(target, evt, { clamp: true })" in fn
    assert "chartPointerFraction(target, evt, { clamp: true })" in fn
