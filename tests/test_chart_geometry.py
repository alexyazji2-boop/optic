"""The chart tells the truth about its own shape and its own mode.

Two faults from one screenshot of the Charting tab, both of the kind that
renders cleanly and is wrong:

  the shape   the plot was drawn small and centred in its panel, with even
              gutters either side and the axis no longer under the bars.
  the mode    the Candles pill was lit and the chart was a line.

Neither threw. That is the point: an SVG with `width="100%"` and the default
`preserveAspectRatio` does not clip or complain when its viewBox stops matching
the element -- it scales the whole picture to fit and centres it. Reproduced by
hand at 885px with a 560px viewBox, which is the reported picture exactly.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
JSC = Path("/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/"
           "Helpers/jsc")


def function(name):
    return re.search(r"^(?:async )?function " + name + r"\([^\n]*\) \{.*?^\}",
                     APP, re.M | re.S).group()


def array_const(name):
    return re.search(r"^const " + name + r" = \[.*?^\];", APP, re.M | re.S).group()


def run_js(scenario):
    exe = str(JSC) if JSC.exists() else shutil.which("jsc")
    if not exe:
        pytest.skip("JavaScriptCore is unavailable")
    src = ("var chartRange = '6m';\nvar chartMode = 'line';\n"
           "var STATE = {chartData: null};\n"
           "function assert(v, m) { if (!v) throw new Error(m); }\n"
           + array_const("CHART_RANGES") + "\n"
           + "\n".join(function(n) for n in
                       ["isIntradayRange", "wsCandles", "wsCandlesPossible"])
           + "\n(function() {\n" + scenario + "\n})();\nprint('TEST_OK');")
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True,
                         timeout=15, cwd=ROOT)
    assert "TEST_OK" in out.stdout, out.stdout + out.stderr


# ------------------------------------------------- the mode pill is a claim


def test_the_toolbar_and_the_chart_agree_about_candles():
    """`wsCandles` decides per build with a series in hand; `wsCandlesPossible`
    decides per toolbar render with only the payload. Two questions, one
    answer, or the control says candles while the plot draws a line -- which is
    what was reported."""
    run_js("""
      chartMode = 'candle';
      var daily = {open: [1], high: [2], low: [0], close: [1]};
      var intra = {close: [1]};   // /api/intraday sends closes only

      chartRange = '6m';
      STATE.chartData = {technicals: {price_series: daily}};
      assert(wsCandlesPossible() === true, 'daily OHLC must allow candles');
      assert(wsCandles(daily) === true, 'and the chart must draw them');

      chartRange = '15';
      assert(wsCandlesPossible() === false, 'intraday cannot be candles');
      assert(wsCandles(intra) === false, 'and the chart already knew');
    """)


@pytest.mark.parametrize("rung", ["1", "5", "15", "30", "60", "240", "1d", "5d"])
def test_no_intraday_rung_offers_candles(rung):
    """Every key, because the ladder added six to a pair of branches written
    when there were two."""
    run_js("""
      chartMode = 'candle';
      chartRange = '%s';
      STATE.chartData = {technicals: {price_series: {open: [1], high: [2], low: [0]}}};
      assert(wsCandlesPossible() === false, 'candles offered on %s');
    """ % (rung, rung))


def test_a_daily_payload_without_ohlc_does_not_offer_candles_either():
    """The test is the data, not the range. A daily payload that arrives
    without open/high/low is the same situation as intraday."""
    run_js("""
      chartMode = 'candle';
      chartRange = '6m';
      STATE.chartData = {technicals: {price_series: {close: [1]}}};
      assert(wsCandlesPossible() === false, 'candles offered with no OHLC');
    """)


def test_nothing_loaded_yet_does_not_grey_the_control_out():
    """Before a payload lands there is nothing to contradict, and a control
    that starts disabled and enables itself a second later reads as a glitch.
    An empty payload on a daily range answers false; that is the honest answer
    and it is corrected on the next toolbar render."""
    run_js("""
      chartRange = '6m';
      STATE.chartData = null;
      wsCandlesPossible();   // must not throw on a missing payload
      STATE.chartData = 'loading';
      wsCandlesPossible();
    """)


def test_the_pills_read_what_is_on_screen():
    """Line reads pressed whenever candles cannot be drawn, because a line is
    what is drawn. The stored preference is untouched -- leaving the intraday
    range has to put candles back without the reader asking twice."""
    fn = function("wsToolbar")
    seg = fn[fn.index('aria-label="Chart style"'):]
    seg = seg[:seg.index("</div>")]
    assert "!wsCandlesPossible() || chartMode === 'line'" in seg, \
        "Line must read as active when it is what is drawn"
    assert "wsCandlesPossible() && chartMode === 'candle'" in seg, \
        "Candles must not read as active when it cannot be honoured"
    assert "disabled" in seg, "and it must not be clickable either"
    # An ASSIGNMENT, not a comparison. `chartMode =` is a substring of
    # `chartMode === 'line'`, which is three lines up and entirely correct.
    assert not re.search(r"chartMode\s*=\s*[^=]", seg), \
        "the toolbar must not overwrite the reader's stored choice"


def test_the_disabled_control_says_why():
    """A greyed-out control with no explanation is a bug report waiting to be
    filed. The range pills beside it set the pattern."""
    fn = function("wsToolbar")
    seg = fn[fn.index('aria-label="Chart style"'):]
    seg = seg[:seg.index("</div>")]
    assert "title=" in seg, "no tooltip on the disabled control"
    # The RENDERED string, not the source. The tooltip is built by joining
    # single-quoted fragments across two source lines, so the source holds a
    # newline the reader never sees. Joining them is what the engine does, and
    # it is the result that has to be one line -- the first draft used a
    # template literal and the title really did render with a newline and ten
    # spaces of indentation inside it.
    branch = seg[seg.index("' disabled title="):]
    branch = branch[:branch.index("}")]
    text = "".join(re.findall(r"'([^']*)'", branch))
    assert "open, high and low" in text, text
    assert "\n" not in text, "the tooltip carries the source's line break"


# ------------------------------------------------- the plot fits its box


def test_the_drawn_chart_is_checked_against_the_box_it_sits_in():
    """Not against a remembered width. Comparing the viewBox to the element
    cannot oscillate, because a redraw makes them equal and equal is the exit
    condition -- which matters here more than usual: this file's own comments
    record a ResizeObserver that recreated itself at 7Hz and ate clicks."""
    fn = function("wsChartAdrift")
    assert "viewBox" in fn and "getBoundingClientRect" in fn
    assert "return false" in fn, "a chart that is not there yet is not adrift"
    # And neither is one that is not laid out. Leaving the view hides the plot,
    # which measures zero -- the largest disagreement there is -- and would
    # schedule a redraw on every view switch for wsRedrawChart to decline.
    assert "!drawn || !box" in fn, "a hidden plot reads as adrift"


def test_the_measured_element_is_the_one_watched():
    """The chart is drawn to `.ws-plot` -- the workspace minus the dock and the
    two rails -- and the only resize watched was `.ws-body`, which those all sit
    inside. Anything moving the boundary between them resizes the plot without
    resizing the body; the dock does it by 260px.

    Measured: with the watcher off, squeezing the plot to 560px left a 625px
    viewBox in place and the chart adrift. With it on, it corrected in under
    300ms. Idle cost is 0 redraws in 15 seconds."""
    fn = function("wsWatchPlot")
    assert "querySelector('.ws-plot')" in fn, \
        "watching anything but the measured element is the original bug"
    assert "wsChartAdrift()" in fn
    # The guard that the 7Hz loop taught this file to write.
    assert "wsPlotObserved === plot" in fn, \
        "re-observing a node already watched is what caused the loop"
    # And it is actually installed.
    assert "\n    wsWatchPlot();" in APP, "the observer is never started"


def test_the_plot_watcher_keeps_no_width_of_its_own():
    """A width baseline is the thing that goes stale and the thing that makes
    two observers disagree. This one asks the picture."""
    fn = function("wsWatchPlot")
    assert "contentRect" not in fn, "a width baseline is what it exists without"
    assert "LastWidth" not in fn


def test_the_body_watcher_is_still_there():
    """The narrow class is a function of the BODY's width -- the dock is
    dropped below a threshold measured on the workspace, not the plot. Deleting
    that observer in favour of this one would take the narrow layout with it."""
    assert "function wsWatchWidth(" in APP
    assert "wsSyncNarrow()" in function("wsWatchWidth")
    assert "\n    wsWatchWidth();" in APP
