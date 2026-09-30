"""A drag pans a chart that pans, and a press held still measures.

Asked for one after the other, with the same button: "the drag feature to see
percent change is not working", and then "dragging left and right on the chart
with a left click does not move the chart". A plain drag pans now, and a press
held still for 300ms, or a shifted one, measures. A chart with nothing to pan,
its whole history on screen, measures on a plain drag.

The pan's side is in app.js, and tests/test_chart_gestures.py reads its wiring.
This runs the chart's side: charts.js under JavaScriptCore, on a recording DOM
that keeps its listeners, with a clock the test turns by hand.

It also pins the bug the measurement had all along. A move that stayed on the
bar the drag began on ended the drag, and a hand's first move almost always
does, so a real drag across the chart usually measured nothing.
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

HARNESS = """
  // Listeners kept, on elements and on the window, and a clock turned by hand.
  var baseMk = mk;
  mk = function (tag) {
    var n = baseMk(tag);
    n.on = {};
    n.addEventListener = function (type, f) { (this.on[type] = this.on[type] || []).push(f); };
    n.removeEventListener = function (type, f) {
      var l = this.on[type] || [], i = l.indexOf(f); if (i >= 0) l.splice(i, 1);
    };
    n.closest = function (sel) {
      var key = sel.slice(6, -1).replace(/-([a-z])/g, function (_, c) { return c.toUpperCase(); });
      for (var e = this; e; e = e.parentNode) if (e.dataset && e.dataset[key] !== undefined) return e;
      return null;
    };
    return n;
  };
  var WIN = {};
  window.addEventListener = function (type, f) { (WIN[type] = WIN[type] || []).push(f); };
  window.removeEventListener = function (type, f) {
    var l = WIN[type] || [], i = l.indexOf(f); if (i >= 0) l.splice(i, 1);
  };
  var TIMERS = [], NEXT = 1;
  setTimeout = function (f, ms) { TIMERS.push({ id: NEXT, f: f, ms: ms }); return NEXT++; };
  clearTimeout = function (id) { TIMERS = TIMERS.filter(function (t) { return t.id !== id; }); };
"""

SCENE = """
  var N = 40, values = [], labels = [];
  for (var i = 0; i < N; i++) { values.push(100 + i); labels.push('d' + i); }
  var GAP = %(gap)s;
  if (GAP !== null) values[GAP] = null;
  var svg = lineChart({ width: 600, height: 300, labels: labels, panDrag: %(pan)s,
                        series: [{ name: 'Close', values: values, color: '#123456' }] });
  var host = mk('div'); host.appendChild(svg);
  if (%(armed)s) host.dataset.panArmed = '1';
  var overlay = NODES.filter(function (x) {
    return x.tag === 'rect' && x.attrs.style === 'cursor:crosshair';
  })[0];
  var group = NODES.filter(function (x) {
    return x.tag === 'g' && x.children.map(function (c) { return c.tag; }).join()
      === 'rect,line,line,circle,circle,text';
  })[0];
  var label = group.children[5];
  // The clientX of a bar, from the frame the chart hangs on its node.
  var f = svg.chartFrame;
  function at(bar) { return (f.margin.l + bar / (N - 1) * f.plotW) * 900 / f.width; }
  function fire(list, evt) { (list || []).slice().forEach(function (h) { h(evt); }); }
  var LOG = [], prevented = null;
  function note(what) {
    LOG.push({ what: what, shown: group.attrs.opacity === '1' ? label.textContent : null,
               measuring: svg.dataset.measuring || null, timers: TIMERS.length,
               moves: (WIN.mousemove || []).length, ups: (WIN.mouseup || []).length });
  }
  function down(bar, shift) {
    TIMERS = [];
    fire(overlay.on.mousedown, { button: 0, clientX: at(bar), clientY: 100, shiftKey: !!shift,
                                 preventDefault: function () { prevented = true; } });
    note('down');
  }
  function nudge(bar, px) {
    fire(WIN.mousemove, { clientX: at(bar) + px, clientY: 100, buttons: 1 });
    note('nudge ' + px);
  }
  function move(bar) { fire(WIN.mousemove, { clientX: at(bar), clientY: 100, buttons: 1 }); note('move ' + bar); }
  function wait(ms) {
    var due = TIMERS.filter(function (t) { return t.ms <= ms; });
    TIMERS = TIMERS.filter(function (t) { return t.ms > ms; });
    due.forEach(function (t) { t.f(); });
    note('wait ' + ms);
  }
  function up() { fire(WIN.mouseup, {}); note('up'); }
"""


def _run(steps, pan=True, armed=True, gap=None):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = ((ROOT / "tests/support/recording_dom.js").read_text() + HARNESS
           + (ROOT / "static/charts.js").read_text()
           + SCENE % {"pan": json.dumps(pan), "armed": json.dumps(armed), "gap": json.dumps(gap)}
           + steps + "\nprint(JSON.stringify({ log: LOG, prevented: prevented }));")
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=30)
    last = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else ""
    assert last.startswith("{"), out.stdout + out.stderr
    got = json.loads(last)
    return {e["what"]: e for e in got["log"]}, got["prevented"]


def _measured(entry):
    return bool(entry["shown"]) and "→" in entry["shown"] and "%" in entry["shown"]


# ------------------------------------------------ a chart that can pan


def test_a_quick_drag_is_the_pans_and_measures_nothing():
    log, prevented = _run("down(5); nudge(5, 3); nudge(5, 6); move(20); wait(300); move(25); up();")
    assert log["down"]["measuring"] is None and log["down"]["timers"] == 1
    # Three pixels is still a press held still.
    assert log["nudge 3"]["timers"] == 1
    # Six is a drag, and the hold is off: its timer and its listeners go.
    assert log["nudge 6"]["timers"] == 0 and log["nudge 6"]["moves"] == 0
    for step in ("move 20", "wait 300", "move 25", "up"):
        assert log[step]["shown"] is None and log[step]["measuring"] is None, step
    assert log["up"]["ups"] == 0
    assert prevented, "no text selection under the pan either"


def test_a_press_held_still_measures():
    log, _ = _run("down(5); nudge(5, 2); wait(300); nudge(5, 3); move(20); up();")
    assert log["nudge 2"]["shown"] is None, "nothing until the hold is up"
    # Held: the pan stands aside from here, and the anchor shows where the
    # measurement is taken from.
    assert log["wait 300"]["measuring"] == "1"
    assert log["wait 300"]["shown"] == "d5   drag to measure"
    assert log["nudge 3"]["shown"] == "d5   drag to measure"
    assert _measured(log["move 20"]) and log["move 20"]["shown"].startswith("d5 → d20")
    assert "+14.29%" in log["move 20"]["shown"], "105 to 120"
    # Released: gone, with nothing left listening.
    assert log["up"]["shown"] is None and log["up"]["measuring"] is None
    assert log["up"]["moves"] == 0 and log["up"]["ups"] == 0


def test_a_release_before_the_hold_measures_nothing():
    log, _ = _run("down(5); up(); wait(300); move(20);")
    assert log["up"]["timers"] == 0 and log["up"]["ups"] == 0
    for step in ("wait 300", "move 20"):
        assert log[step]["shown"] is None and log[step]["measuring"] is None, step


def test_shift_measures_from_the_press():
    log, _ = _run("down(5, true); move(20); up();")
    assert log["down"]["measuring"] == "1" and log["down"]["timers"] == 0
    assert _measured(log["move 20"])


# ------------------------------------------------ and the rest measure at once


def test_a_chart_with_nothing_to_pan_measures_on_a_plain_drag():
    """The pan arms the host only when it can move the chart."""
    log, _ = _run("down(5); move(20); up();", armed=False)
    assert log["down"]["measuring"] == "1" and log["down"]["timers"] == 0
    assert _measured(log["move 20"])


def test_a_chart_that_never_pans_measures_on_a_plain_drag():
    """Every lineChart that passes no panDrag, the default."""
    log, _ = _run("down(5); move(20); up();", pan=False)
    assert log["down"]["measuring"] == "1" and _measured(log["move 20"])


# ------------------------------------------------ the bug the drag always had


def test_a_first_move_on_the_starting_bar_keeps_the_measurement():
    """A bar here is twenty pixels wide, so a three-pixel move stays on it.
    That move cleared the anchor, and every move after it measured nothing."""
    log, _ = _run("down(5); nudge(5, 3); move(20); up();", pan=False)
    assert log["nudge 3"]["shown"] == "d5   drag to measure"
    assert log["nudge 3"]["measuring"] == "1"
    assert _measured(log["move 20"])


def test_crossing_a_gap_keeps_the_measurement():
    """A bar with no value hid the readout the same way, and ended the drag."""
    log, _ = _run("down(5); move(10); move(20); up();", pan=False, gap=10)
    assert log["move 10"]["shown"] is None and log["move 10"]["measuring"] == "1"
    assert _measured(log["move 20"])
