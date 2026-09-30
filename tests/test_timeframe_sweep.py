"""A time frame press sweeps the chart on, whichever time frame it is.

Asked for as "show the chart animation regardless of what time frame you
change it to". A range, bar-size or window press redrew the chart finished, on
the grounds that it was the same shape at a different span. Now it sweeps, as
a new symbol does, on the Charting tab (RSI and MACD with it), the Options tab
and the Investing chart.

Three things make that hold rather than flicker, each tested here:

* Under a day and on 1W the bars arrive after the press, so the press marks
  the sweep and the first redraw with bars spends it.
* The studies' loading redraw follows every press in the same tick and
  replaces the mount before it builds, so the mark lasts two frames and that
  redraw sweeps too.
* Studies, trend lines, zones, earnings markers and weekly bars land a moment
  later, and a rebuild then cut the sweep off halfway, so they wait for it.

A zoom or a pan never sweeps: they redraw in place and have to stay instant.
Checked in a browser: a range press mounted the chart animated, the same pill
pressed again did not, and a 15m press swept when its 546 bars landed.
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


def _raw_fn(name):
    return re.search(r"^(?:async )?function %s\([^\n]*\) \{.*?^\}" % name, RAW, re.M | re.S).group()


def _handler(start):
    at = RAW.index(start)
    return RAW[at:RAW.index("\n    return;\n  }", at)]


# ---------------------------------------------------------- Charting tab


def test_each_press_marks_a_sweep_only_when_the_time_frame_changes():
    rng = _handler("const wsRange = evt.target.closest('[data-ws-range]');")
    assert rng.index("const before = wsFrameKey();") < rng.index("chartRange = wsRange.dataset.wsRange;")
    assert "if (wsFrameKey() !== before) wsFrameSweep = ++wsSweepSeq;" in rng
    assert rng.index("wsFrameSweep = ++wsSweepSeq") < rng.index("wsRedrawChart();")
    size = _handler("const wsInt = evt.target.closest('[data-ws-interval]');")
    # Both branches, after the size is written and before it is drawn.
    assert size.count("if (wsFrameKey() !== before) wsFrameSweep = ++wsSweepSeq;") == 2
    assert size.index("wsFrameSweep = ++wsSweepSeq;\n      wsLoadIntraday();") > 0
    assert size.index("wsFrameSweep = ++wsSweepSeq;\n      wsRedrawChart();") > 0


def test_the_time_frame_is_range_size_and_intraday_window():
    """Under a day the bars' own key, which carries the window and the session:
    extended hours are other bars, and a switch to them sweeps like a size."""
    key = _raw_fn("wsFrameKey")
    assert "`${chartRange}|${chartInterval}|${isIntradayRange(chartRange) ? intradayBarsKey(chartRange) : ''}`" in key


def test_the_first_redraw_with_bars_spends_it_and_a_gesture_never_does():
    fn = _raw_fn("wsRedrawChart")
    assert ("const sweep = !!wsFrameSweep && !chartInteractive && (ps.dates || []).length > 0;"
            in fn)
    assert "setChartAnimation(!!(opts && opts.animate) || sweep);" in fn
    # RSI and MACD with it, and both signals put back after the mount.
    assert fn.index("wsPaneArriving = '*';") < fn.index("wsMountChart();")
    after = fn[fn.index("wsMountChart();"):]
    assert "setChartAnimation(false);" in after and "wsPaneArriving = null;" in after
    # Spent two frames on, and only the mark it was: a press in between is its own.
    assert "const spent = wsFrameSweep;" in fn
    assert "if (wsFrameSweep === spent) wsFrameSweep = 0;" in fn


def test_data_that_lands_after_a_press_waits_for_the_sweep():
    assert _raw_fn("wsRedrawSettled").count("afterDrawsSettle(() => wsRedrawChart());") == 1
    studies = _raw_fn("wsLoadIndicators")
    assert "wsRedrawChart()" not in studies and studies.count("wsRedrawSettled();") == 4
    for name in ("loadTrendlines", "loadAccumZones", "repaintForEarningsMarkers"):
        body = _raw_fn(name)
        assert "if (STATE.view === 'chart') wsRedrawSettled();" in body, name
    weekly = _raw_fn("loadWeeklyBars")
    assert "wsWindow = null;\n    wsRedrawSettled();" in weekly
    assert "swingRenderSettled();" in weekly


# ------------------------------------------------------------ Options tab


def test_the_options_presses_sweep_when_the_time_frame_changes():
    rng = RAW[RAW.index("const tf = evt.target.closest('[data-chart-range]');"):]
    rng = rng[:rng.index("const ltTf")]
    assert "const changed = tf.dataset.chartRange !== chartRange;" in rng
    assert "swingFrameSweep = changed;\n      loadIntraday(chartRange);" in rng
    assert "if (STATE.swing) sweepSwing(changed);" in rng
    size = RAW[RAW.index("if (evt.target.id === 'chart-interval') {"):]
    size = size[:size.index("\n});")]
    assert "const changed = evt.target.value !== chartInterval;" in size
    assert "if (STATE.swing) sweepSwing(changed);" in size
    intraday = _raw_fn("loadIntraday")
    assert intraday.count("sweepSwingIntraday();") == 2, "the cached bars and the fetched ones"
    assert "STATE.intraday = { ticker, range, loading: true };\n  if (STATE.swing) renderSwing(STATE.swing);" in intraday
    assert "swingRenderSettled();" in _raw_fn("loadIndicators")


def test_the_investing_range_sweeps_when_it_changes():
    lt = RAW[RAW.index("const ltTf = evt.target.closest('[data-lt-range]');"):]
    lt = lt[:lt.index("\n    return;\n  }")]
    assert "const changed = ltTf.dataset.ltRange !== ltRange;" in lt
    assert "if (changed) setChartAnimation(true);\n        renderLong(STATE.long);" in lt


SWING = """
function assert(v, m) { if (!v) throw new Error(m); }
var anim = false;
function setChartAnimation(v) { anim = v; }
function chartAnimationOn() { return anim; }
var frames = [];
function requestAnimationFrame(f) { frames.push(f); return frames.length; }
function runFrames() { var f = frames; frames = []; f.forEach(function (g) { g(); }); }
function afterDrawsSettle(fn) { fn(); }
function preserveUI(host, fn) { setChartAnimation(false); fn(); }
var renders = [];
function renderSwing() { renders.push(chartAnimationOn()); }
var views = { swing: {} };
var STATE = { view: 'swing', swing: { ticker: 'TSLA' } };
"""


def _swing(scenario):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    lets = "\n".join(re.search(r"^let %s = [^\n]*;" % n, RAW, re.M).group()
                     for n in ("swingFrameSweep", "swingSweepPending", "swingSweepSeq"))
    src = (SWING + lets + "\n" + "\n".join(_raw_fn(n) for n in (
        "sweepSwing", "sweepSwingIntraday", "markSwingSweep", "swingRenderSettled"))
        + "\n" + scenario + "\nprint('TEST_OK');")
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=30)
    assert "TEST_OK" in out.stdout, out.stdout + out.stderr


def test_an_options_press_sweeps_and_so_does_what_lands_inside_two_frames():
    _swing("""
      sweepSwing(true);
      assert(renders[0] === true, 'the press sweeps');
      swingRenderSettled();
      assert(renders[1] === true, 'a study landing before the build sweeps too');
      runFrames(); runFrames();
      swingRenderSettled();
      assert(renders[2] === false, 'one landing after it does not');
    """)


def test_an_unchanged_options_press_does_not_sweep():
    _swing("""
      sweepSwing(false);
      swingRenderSettled();
      assert(renders[0] === false && renders[1] === false, 'no sweep, no window');
    """)


def test_intraday_bars_sweep_once_when_they_land():
    _swing("""
      swingFrameSweep = true;
      sweepSwingIntraday();
      assert(renders[0] === true && swingFrameSweep === false, 'spent on the bars');
      assert(anim === false, 'and the flag put back');
      swingRenderSettled();
      assert(renders[1] === true, 'a study landing inside the window sweeps as well');
      sweepSwingIntraday();
      assert(renders[2] === false, 'the press is spent: a re-render with no new press does not');
      runFrames(); runFrames();
      swingRenderSettled();
      assert(renders[3] === false, 'and after the window nothing does');
    """)


def test_a_later_press_is_not_cleared_by_the_one_before_it():
    _swing("""
      sweepSwing(true);
      runFrames();
      sweepSwing(true);
      runFrames();
      swingRenderSettled();
      assert(renders[renders.length - 1] === true, 'the second press still has its window');
    """)
