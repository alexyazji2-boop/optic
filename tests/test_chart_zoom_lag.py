"""A zoom or a pan draws in the frame it was asked for, over the chart on screen.

Reported as "zooming in/out of the chart is laggy". The wheel was already
gathered to one redraw a frame, and the redraw was the fault: `mount()` cleared
the chart and queued its build for a later frame, as it does for a first load,
and on a trackpad the next step arrived first and its token retired the build
before it ran. Measured in a browser on TSLA's daily chart: straight after a
zoom step the chart's host held nothing, where now it holds the new chart, and
a step costs about 7ms once warm. The toolbar, a few hundred nodes, was rebuilt
on every step as well, and a drag on the plot or on the navigator redrew on
every pointer move rather than once a frame.
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
    return re.search(r"^function %s\([^\n]*\) \{.*?^\}" % name, RAW, re.M | re.S).group()


def _block(start, end="\n});"):
    at = RAW.index(start)
    return RAW[at:RAW.index(end, at)]


HARNESS = """
function assert(v, m) { if (!v) throw new Error(m); }
var chartToken = 0, chartInteractive = false, CHART_QUEUE = [], chartObserver = null;
var CHART_BUILDERS = new Map(), PENDING_HOSTS = new Set();
var anim = false;
function chartAnimationOn() { return anim; }
function setChartAnimation(v) { anim = v; }
var queued = 0;
function runChartQueue() { queued++; }
function ensureChartSweeper() {}
function animateChart() {}
var window = { innerHeight: 900 };
function makeHost(built) {
  return { dataset: {}, style: {}, clientWidth: 800, children: built ? [{ old: true }] : [],
    get firstChild() { return this.children[0] || null; },
    set innerHTML(v) { this.children = []; }, get innerHTML() { return ''; },
    appendChild: function (el) { this.children.push(el); },
    getBoundingClientRect: function () { return { top: 0, bottom: 400 }; } };
}
var HOSTS = {};
var document = { getElementById: function (id) { return HOSTS[id]; } };
"""


def _run(scenario):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = (HARNESS + "\n".join(_raw_fn(n) for n in (
        "mount", "buildChartNow", "drawnAs", "settleHost", "interactiveRedraw"))
        + "\n" + scenario + "\nprint('TEST_OK');")
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=30)
    assert "TEST_OK" in out.stdout, out.stdout + out.stderr


def test_a_gesture_builds_the_chart_now_over_the_one_on_screen():
    _run("""
      HOSTS.c = makeHost(true);
      chartInteractive = true;
      mount('c', function (w) { return { built: w }; });
      chartInteractive = false;
      assert(HOSTS.c.children.length === 1 && HOSTS.c.children[0].built === 800, 'built in place');
      assert(CHART_QUEUE.length === 0 && queued === 0, 'not queued');
      assert(!('chartPending' in HOSTS.c.dataset), 'settled');
    """)


def test_anything_else_is_queued_as_before():
    _run("""
      HOSTS.c = makeHost(true);
      mount('c', function (w) { return { built: w }; });
      assert(HOSTS.c.children.length === 0, 'cleared for the queue');
      assert(CHART_QUEUE.length === 1 && queued === 1, 'queued');
    """)


def test_a_first_build_waits_for_the_queue_even_mid_gesture():
    """Nothing is on screen to draw over, and the queue is how a first load
    arrives progressively."""
    _run("""
      HOSTS.c = makeHost(false);
      chartInteractive = true;
      mount('c', function (w) { return { built: w }; });
      chartInteractive = false;
      assert(CHART_QUEUE.length === 1, 'queued');
    """)


def test_a_build_queued_before_the_gesture_is_retired_by_it():
    """runChartQueue builds a job only while the host still carries its
    token, and a build done in place clears the token."""
    _run("""
      HOSTS.c = makeHost(true);
      mount('c', function (w) { return { stale: true }; });
      var job = CHART_QUEUE[0];
      HOSTS.c.children = [{ old: true }];
      chartInteractive = true;
      mount('c', function (w) { return { built: w }; });
      chartInteractive = false;
      assert(HOSTS.c.dataset.chartPending !== job.token, 'the queued build no longer matches');
      assert(HOSTS.c.children[0].built === 800, 'the new chart is the one shown');
    """)


def test_the_flag_is_set_only_while_the_redraw_runs():
    _run("""
      var seen = null;
      interactiveRedraw({ redraw: function () { seen = chartInteractive; } });
      assert(seen === true && chartInteractive === false, 'set during, clear after');
      try { interactiveRedraw({ redraw: function () { throw new Error('x'); } }); } catch (e) {}
      assert(chartInteractive === false, 'clear after a throw too');
    """)


def test_every_gesture_draws_through_it():
    flush = _raw_fn("flushChartWheel")
    assert "interactiveRedraw(target.adapter);" in flush
    assert "target.adapter.redraw();" not in flush
    pinch = _block("document.addEventListener('gesturechange'")
    assert "interactiveRedraw(g.target.adapter);" in pinch


def test_a_drag_on_the_plot_redraws_once_a_frame_and_lands_its_last_move():
    pan = _block("document.addEventListener('pointermove', (evt) => {\n  if (!wsPan) return;")
    assert "const pan = wsPan;" in pan
    assert "if (!pan.frame) {" in pan and "requestAnimationFrame(" in pan
    assert "if (pan.adapter.apply(pan.next)) interactiveRedraw(pan.adapter);" in pan
    assert "wsPan.adapter.redraw()" not in pan


def test_a_drag_on_the_navigator_redraws_once_a_frame():
    nav = _block("document.addEventListener('pointermove', (evt) => {\n  if (!wsNavDrag) return;")
    assert "wsWindow = settled;" in nav
    assert "const drag = wsNavDrag;" in nav and "if (!drag.frame) {" in nav
    assert "interactiveRedraw({ redraw: () => wsRedrawChart() });" in nav
    assert nav.rstrip().endswith("}") and "\n  wsRedrawChart();" not in nav


def test_a_gesture_rebuilds_the_toolbar_only_when_reset_zoom_comes_or_goes():
    redraw = _raw_fn("wsRedrawChart")
    assert ("const same = chartInteractive && tb\n"
            "      && !!tb.querySelector('[data-ws-zoom-reset]') === !!wsWindow;") in redraw
    assert "if (tb && !same) tb.outerHTML = wsToolbar();" in redraw
    # And Reset zoom is the one thing on it a window changes.
    toolbar = _raw_fn("wsToolbar")
    assert toolbar.count("wsWindow") == 1 and "data-ws-zoom-reset" in toolbar
