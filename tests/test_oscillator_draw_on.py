"""RSI and MACD draw on with the price chart they sit under.

Asked for as "add an animation for the RSI and MACD when it loads up, similar
to the chart coming up as it loads in". Both panes already carried the same
draw-on the price chart has; three things kept it from being seen.

On the Charting tab, loadView decided the flag from the chart being replaced,
so switching symbols drew every chart finished. Measured on a switch from NVDA
to AMD: no animation at all on the price chart, RSI or MACD.

Builds are queued a frame apart, and below the fold until they are scrolled
to, and each read the flag when it ran rather than when it was asked for. The
MACD pane, two frames after the price chart, drew finished while the price
swept, and an Options-tab panel opened after any control press never swept.

And the stage reading lands a moment after the payload. Its redraw replaced
all three charts with finished copies part-way through their sweep.

Measured after, at 1440x1100: on a new symbol the price chart, RSI and MACD
start their sweeps within 15ms of each other; Line to Candles sweeps the price
alone; a range press sweeps nothing; opening a pane from the Panes menu sweeps
that pane alone; the Options tab's RSI and MACD sweep when opened, after a
control press as well.
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


def strip_comments(js):
    js = re.sub(r"/\*.*?\*/", " ", js, flags=re.S)
    return re.sub(r"(?<!:)//[^\n]*", " ", js)


CODE = strip_comments(APP)


def fn(name, src=CODE):
    start = src.index("function %s(" % name)
    return src[start:].split("\nfunction ", 1)[0]


def raw_fn(name, src):
    """A function's own source, to run it: one line, or up to its closing brace."""
    one = re.search(r"^function " + name + r"\([^\n]*\}$", src, re.M)
    if one:
        return one.group() + "\n"
    m = re.search(r"^(?:async )?function " + name + r"\(.*?^\}", src, re.M | re.S)
    return m.group() + "\n"


def _jsc(script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    out = subprocess.run([exe, "-e", script], capture_output=True, text=True, timeout=30)
    last = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else ""
    assert last.startswith("{"), out.stdout + out.stderr
    return json.loads(last)


STUBS = """
  var window = this;
  window.matchMedia = function () { return { matches: false }; };
"""


# ----------------------------------------------- the answer is kept at mount


def test_a_build_draws_on_as_its_mount_decided():
    """Asked for while the flag was on, built after it went off: it still
    draws on, and the flag is left as the build found it."""
    got = _jsc(STUBS + raw_fn("setChartAnimation", CHARTS) + raw_fn("chartAnimationOn", CHARTS)
               + "var animateNextChart = false;\n" + raw_fn("drawnAs", APP) + """
      setChartAnimation(true);
      var seen = [];
      var build = drawnAs(function () { seen.push(chartAnimationOn()); return 1; }, chartAnimationOn());
      setChartAnimation(false);
      build(300);
      var after = chartAnimationOn();
      setChartAnimation(true);
      var still = drawnAs(function () { seen.push(chartAnimationOn()); return 1; }, false);
      still(300);
      print(JSON.stringify({ seen: seen, after: after, restored: chartAnimationOn() }));
    """)
    assert got == {"seen": [True, False], "after": False, "restored": True}


def test_every_mounted_builder_carries_its_answer():
    body = fn("mount")
    assert "node = drawnAs(node, chartAnimationOn());" in body
    # Before anything queues or defers it.
    at = body.index("node = drawnAs(node, chartAnimationOn());")
    assert at < body.index("CHART_QUEUE.push") and at < body.index("CHART_BUILDERS.set")


# --------------------------------------------- a redraw waits for the sweep


def test_a_callback_waits_for_every_draw_in_progress():
    got = _jsc(STUBS + CHARTS[CHARTS.index("const runningDraws = new Set();"):
                               CHARTS.index("/** Kick off the animation.")] + """
      var log = [];
      afterDrawsSettle(function () { log.push('idle'); });
      var finish;
      trackDraw({ finished: new Promise(function (res) { finish = res; }) });
      var fail;
      trackDraw({ finished: new Promise(function (res, rej) { fail = rej; }) });
      afterDrawsSettle(function () { log.push('after'); });
      log.push('queued');
      finish();
      drainMicrotasks();
      log.push('one left');
      fail(new Error('cancelled'));
      drainMicrotasks();
      print(JSON.stringify({ log: log, left: runningDraws.size }));
    """)
    # At once with nothing running; after both otherwise, a cancelled one too.
    assert got == {"log": ["idle", "queued", "one left", "after"], "left": 0}


def test_both_kinds_of_draw_on_are_tracked():
    body = fn("animateChart", strip_comments(CHARTS))
    assert body.count("trackDraw(anim);") == 2


def test_the_stage_redraw_waits_for_the_sweep():
    assert "afterDrawsSettle(() => stagesRedraw(symbol));" in fn("stagesArrived")
    redraw = fn("stagesRedraw")
    # The Charting tab alone: the other charts draw no stages.
    assert "if (STATE.view !== 'chart') return;" in redraw
    for view in ("'swing'", "'instrument'"):
        assert view not in redraw


# ---------------------------------------------------- the Charting tab


def test_a_new_payload_draws_on_and_only_that_draw():
    body = fn("loadChartWorkspace")
    arrived = body[body.index("if (STATE.view !== 'chart') return;"):]
    on = arrived.index("setChartAnimation(true);")
    assert on < arrived.index("wsPaneArriving = '*';") < arrived.index("wsMountChart();")
    after = arrived[arrived.index("wsMountChart();"):]
    assert after.index("setChartAnimation(false);") < after.index("wsEnsureIntraday();")
    assert after.index("wsPaneArriving = null;") < after.index("wsEnsureIntraday();")


def test_the_stage_is_asked_for_beside_the_payload():
    body = fn("loadChartWorkspace")
    assert "if (wsOverlayDrawn('stages')) fetchStage(sym);" in body
    assert body.index("fetchStage(sym)") < body.index("await getJSON(")


def test_the_panes_draw_on_for_an_arrival_or_their_own_opening_only():
    """Not for Line and Candles, which redraw the price and leave both panes
    as they were."""
    body = fn("wsMountPanes")
    assert "setChartAnimation(arriving === '*' || arriving === id)" in body
    assert "was ||" not in body
    for pane in ("rsi", "macd"):
        at = body.index("drawOn('%s');" % pane)
        mount_at = body.index("mount('ws-pane-%s'" % pane)
        assert at < mount_at
        assert "setChartAnimation(was);" in body[mount_at:]
    assert "wsPaneArriving = null;" in body


def test_opening_a_pane_names_it_and_nothing_else_replays():
    at = CODE.index("const wsPaneOpt = evt.target.closest('[data-ws-pane-opt]');")
    branch = CODE[at:CODE.index("return;", at)]
    assert "setChartAnimation(false);" in branch
    assert ("wsPaneArriving = wsPaneOpen(wsPaneOpt.dataset.wsPaneOpt)"
            " ? wsPaneOpt.dataset.wsPaneOpt : null;") in branch
    assert branch.index("wsPaneArriving =") < branch.index("wsRepaintWithPanes();")
