"""Zooming the charts from a Mac trackpad.

Reported as: the trackpad cannot zoom the charts. Four causes, all measured.

* The wheel handler zoomed 1.15 per EVENT. A mouse notch is one event; a
  two-finger scroll is dozens of a few pixels each, and so is a pinch, which
  Chrome, Edge and Firefox deliver as ctrl+wheel. One gentle stroke went
  straight to the limit. A sideways swipe has deltaY 0, which is not greater
  than 0, so it zoomed in.
* Safari delivers a pinch as gesture events, which nothing listened for, so
  the page zoomed instead of the chart.
* While a chart redraws it swaps its SVG, and one wheel event in three landed
  in that gap and went to the page: a jerky scroll, or for a pinch the browser
  zooming the whole page.
* Under a day nothing zoomed at all. The Charting tab's window counted the
  daily bars and the Options chart declined intraday outright.

Studies were also cut to the newest bars rather than the window, so a zoomed
chart drew one period's Bollinger band over another's candles.
"""
from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
RAW = (ROOT / "static/app.js").read_text()


def _strip(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"^\s*//.*$", " ", text, flags=re.M)


APP = _strip(RAW)


def _fn(name: str) -> str:
    body = APP[APP.index("function " + name + "("):]
    return body[:body.index("\n}") + 2]


def _raw_fn(name: str) -> str:
    return re.search(r"^(?:async )?function " + name + r"\([^\n]*\) \{.*?^\}",
                     RAW, re.M | re.S).group()


JSC = ("/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/"
       "Helpers/jsc")


def _run(scenario: str) -> str:
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    consts = "\n".join(re.search(r"^const %s = [^\n]*;" % name, RAW, re.M).group()
                       for name in ("ZOOM_PER_PX", "PINCH_PER_PX", "WS_MIN_BARS"))
    src = ("function assert(v, m) { if (!v) throw new Error(m); }\n"
           "var frames = []; function requestAnimationFrame(f) { frames.push(f); return frames.length; }\n"
           "function runFrames() { var f = frames; frames = []; f.forEach(function (g) { g(); }); }\n"
           "var chartWheel = null, chartWheelFrame = 0, chartGesture = null;\n"
           "var chartInteractive = false;\n"
           + consts + "\n"
           + "\n".join(_raw_fn(n) for n in ("wheelPixels", "queueChartFrame", "zoomedWindow",
                                             "zoomedWindowAt", "chartMayAct",
                                             "flushChartWheel", "chartBarsPerPixel", "alignToWindow",
                                             "interactiveRedraw"))
           + "\n" + scenario + "\nprint('TEST_OK');")
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=30)
    assert "TEST_OK" in out.stdout, out.stdout + out.stderr
    return out.stdout


# A chart of 500 bars showing 126, 800px of plot drawn at its own size.
FAKE = """
var win = {from: 374, to: 500, total: 500};
var applied = 0, redrawn = 0;
var frame = {plotW: 800, width: 880, bars: 126};
var svg = {chartFrame: frame, getBoundingClientRect: function () { return {width: 880}; }};
var host = {querySelector: function () { return svg; }};
var adapter = {
  enabled: function () { return true; },
  window: function () { return {from: win.from, to: win.to, total: win.total}; },
  apply: function (w) {
    var span = Math.max(WS_MIN_BARS, Math.min(win.total, w.to - w.from));
    var from = Math.max(0, Math.min(win.total - span, w.from));
    if (from === win.from && from + span === win.to) return false;
    win = {from: from, to: from + span, total: win.total}; applied++; return true;
  },
  redraw: function () { redrawn++; },
};
var target = {host: host, svg: svg, frame: frame, adapter: adapter};
function feed(zoomPx, panPx, pinch) {
  if (!chartWheel) chartWheel = {target: target, bar: 63, zoomLog: 0, panPx: 0};
  chartWheel.zoomLog += zoomPx * (pinch ? PINCH_PER_PX : ZOOM_PER_PX);
  chartWheel.panPx += panPx;
  queueChartFrame();
}
"""


# ------------------------------------------------------------------ the math


def test_a_mouse_notch_still_zooms_the_old_fifteen_percent():
    assert math.isclose(math.exp(100 * math.log(1.15) / 100), 1.15)
    assert "const ZOOM_PER_PX = Math.log(1.15) / 100;" in RAW
    assert "const PINCH_PER_PX = 0.01;" in RAW


def test_a_gentle_two_finger_scroll_zooms_a_little_not_to_the_limit():
    """Twenty events of four pixels: the old handler went 126 bars to 12."""
    _run(FAKE + """
      for (var i = 0; i < 20; i++) feed(-4, 0, false);
      runFrames();
      var span = win.to - win.from;
      assert(span > 100 && span < 126, 'span ' + span);
    """)


def test_many_events_in_one_frame_redraw_once():
    _run(FAKE + """
      for (var i = 0; i < 20; i++) feed(-4, 0, false);
      assert(frames.length === 1, 'frames queued: ' + frames.length);
      runFrames();
      assert(redrawn === 1, 'redraws: ' + redrawn);
    """)


def test_a_slow_stroke_accumulates_instead_of_rounding_to_nothing():
    """One pixel at a time rounds to no whole bar each time; kept, it moves,
    and by the distance travelled. 200 one-pixel steps are e^(-200k) of 126,
    95.3 bars. Dropping what is left after each whole-bar move roughly doubles
    the rate, because every move rounds up to a full bar."""
    _run(FAKE + """
      for (var i = 0; i < 200; i++) { feed(-1, 0, false); runFrames(); }
      var span = win.to - win.from;
      assert(Math.abs(span - 95.3) <= 3, 'slow stroke span ' + span);
    """)


def test_the_zoom_is_proportional_to_the_distance():
    """Twenty pixels is e^(-20k) of 126, 122.5 bars, not a whole notch's 110."""
    _run(FAKE + """
      for (var i = 0; i < 5; i++) feed(-4, 0, false);
      runFrames();
      var span = win.to - win.from;
      assert(span >= 121 && span <= 124, 'span ' + span);
    """)


def test_a_pinch_in_and_back_out_returns_to_the_start():
    _run(FAKE + """
      for (var i = 0; i < 30; i++) feed(-2, 0, true);
      runFrames();
      var inSpan = win.to - win.from;
      for (var j = 0; j < 30; j++) feed(2, 0, true);
      runFrames();
      assert(inSpan < 126, 'pinch did not zoom in');
      assert(Math.abs((win.to - win.from) - 126) <= 1, 'asymmetric: ' + (win.to - win.from));
    """)


def test_a_sideways_swipe_pans_and_does_not_zoom():
    _run(FAKE + """
      win = {from: 200, to: 326, total: 500};
      for (var i = 0; i < 10; i++) feed(0, -30, false);
      runFrames();
      assert(win.to - win.from === 126, 'swipe zoomed: ' + (win.to - win.from));
      assert(win.from < 200, 'swipe did not pan earlier: ' + win.from);
    """)


def test_a_zoom_keeps_the_bar_under_the_cursor():
    _run("""
      var cur = {from: 100, to: 200, total: 500};
      var next = zoomedWindow(cur, 50, 50);
      assert(next.from === 125 && next.to === 175, next.from + '-' + next.to);
    """)


def test_a_line_mode_notch_is_the_same_size_as_a_pixel_one():
    _run("""
      assert(wheelPixels(3, 1) === 99, 'firefox notch ' + wheelPixels(3, 1));
      assert(wheelPixels(100, 0) === 100, 'pixels');
    """)


# ------------------------------------------------------------------ routing


def test_the_handler_routes_pinch_swipe_and_scroll():
    fn = APP[APP.index("document.addEventListener('wheel', (evt) => {"):]
    fn = fn[:fn.index("}, { passive: false });")]
    assert "if (evt.ctrlKey) {" in fn and "chartWheel.zoomLog += dy * PINCH_PER_PX;" in fn
    assert "} else if (Math.abs(dx) > Math.abs(dy)) {" in fn and "chartWheel.panPx += dx;" in fn
    assert "} else if (evt.shiftKey) {" in fn
    assert "chartWheel.zoomLog += dy * ZOOM_PER_PX;" in fn
    assert "evt.deltaY > 0 ? 1.15 : 1 / 1.15" not in APP


def test_a_gesture_mid_redraw_stays_with_the_chart():
    fn = APP[APP.index("document.addEventListener('wheel', (evt) => {"):]
    fn = fn[:fn.index("}, { passive: false });")]
    # `wheel: true`: a gesture held over a drawing is still this chart's.
    assert "const held = chartZoomHost(evt, { wheel: true });" in fn
    assert "if (!held || !chartWheel || chartWheel.target.host !== held.host) return;" in fn
    # and the flush re-reads the frame, since the old SVG measures zero wide
    assert "const svg = w.target.host.querySelector('svg.chart');" in _fn("flushChartWheel")


def test_safari_pinch_is_handled_and_measured_from_the_start():
    for kind in ("gesturestart", "gesturechange", "gestureend"):
        block = APP[APP.index("document.addEventListener('%s'" % kind):]
        block = block[:block.index("}, { passive: false });")]
        assert "evt.preventDefault();" in block, kind
    change = APP[APP.index("document.addEventListener('gesturechange'"):]
    assert "Math.round(span / scale)" in change[:change.index("}, { passive: false });")]
    wheel = APP[APP.index("document.addEventListener('wheel', (evt) => {"):]
    assert "if (chartGesture) return;" in wheel[:wheel.index("}, { passive: false });")]


# ------------------------------------------------------------------ intraday


def test_the_charting_window_counts_the_bars_on_screen():
    assert "if (isIntradayRange(chartRange)) {" in _fn("wsBaseSeries")
    for name in ("wsWindowNow", "wsApplyWindow", "wsRenderNav"):
        assert "wsBaseSeries(" in _fn(name), name
    series = _fn("wsSeries")
    assert "const total = (full.dates || []).length;\n    const win = wsClampWindow(wsWindow, total);" in series
    assert "if (win) { wsFit = null; return wsSliceWindow(full, win); }" in series
    # Unzoomed, the size's own window of it: see tests/test_intraday_history.py.
    assert "const shown = wsReadable(from ? wsSliceWindow(full, { from, to: total }) : full);" in series


def test_the_options_window_counts_the_bars_on_screen_and_zooms_intraday():
    for name in ("swingWindowNow", "swingApplyWindow"):
        assert "swingBaseSeries(" in _fn(name), name
    block = APP[APP.index("registerChartZoom('chart-price', {"):]
    assert "!isIntradayRange(chartRange)" not in block[:block.index("});")]
    series = _fn("swingSeries")
    assert "return win ? wsSliceWindow(series, win) : series;" in series


def test_studies_follow_the_window_not_the_newest_bars():
    _run("""
      var vals = []; for (var i = 0; i < 10; i++) vals.push(i);
      var got = alignToWindow(vals, {from: 2, to: 5, total: 10});
      assert(got.join() === '2,3,4', got.join());
      var longer = [100, 101].concat(vals);            // payload two bars longer, same end
      assert(alignToWindow(longer, {from: 2, to: 5, total: 10}).join() === '2,3,4', 'offset');
    """)
    assert "values: win ? alignToWindow(line.values, win) : line.values," in _fn("wsIndicatorSeries")
    assert "values: win ? alignToWindow(line.values, win) : line.values," in _fn("indicatorOverlaySeries")


def test_the_status_line_follows_the_zoom_on_every_rung():
    assert "updateStatus();" in _fn("wsRedrawChart")
    # Zoomed in time or in price (tests/test_price_scale_drag.py).
    assert "wsZoomed() ? `${shown} · zoomed`" in APP
    assert ": wsFit ? `${shown} · newest ${wsFit.shown} of ${wsFit.total} candles, scroll for more`" in APP
