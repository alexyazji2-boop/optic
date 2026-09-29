"""The drawing tools follow the pointer, and a drag draws.

Reported as "drawing tools are super laggy as well. go through each one of
them one by one and make sure that they properly work". Each of the fourteen
tools placed its points, drew and saved; what read as lag was what happened
between the clicks. Nothing followed the pointer: a trend line was a dot until
its second click, and a channel, pitchfork or risk box took three clicks with
nothing to aim by. Press, drag and release drew nothing at all, where most
charting tools draw the line the drag traced. Dragging a drawing rebuilt the
layer on every pointer event rather than once a frame, and every ruler looked
up the window's dates again on each of those rebuilds. A selected drawing's
handle was a 9px dot, and a press a few pixels off it panned the chart.

Now the shape being placed follows the pointer, drawn by the same painter as a
finished drawing, so a ruler reads out and a retracement lays out its levels
as the pointer moves; a drag places the next point where it is released; the
layer redraws once a frame; and a handle takes a press 11px from its centre.

Checked in a browser with real input, one tool at a time: trend, ray, level,
date line, channel, rectangle, both Fibonacci tools, pitchfork, arrow, text,
measure, risk / reward and position size each drew and saved with the points
it needs, with its shape following the pointer before the last click. Then a
press-drag-release trend line, moving a line, dragging a handle from 10px off
it, Delete, undo, redo, Clear, undoing Clear, and Escape on a half-placed line.
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
CSS = (ROOT / "static/styles.css").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def strip_comments(js):
    js = re.sub(r"/\*.*?\*/", " ", js, flags=re.S)
    return re.sub(r"(?<!:)//[^\n]*", " ", js)


CODE = strip_comments(APP)


def fn(name, src=CODE):
    start = src.index("function %s(" % name)
    return src[start:].split("\nfunction ", 1)[0]


def raw_fn(name):
    m = re.search(r"^function " + name + r"\(.*?^\}", APP, re.M | re.S)
    return m.group() + "\n"


def listener(event, first_line):
    """The source of one document listener, found by its first line."""
    at = APP.index("document.addEventListener('%s', (evt) => {\n  %s" % (event, first_line))
    end = APP.index("\n});", at) + len("\n});")
    return APP[at:end] + "\n"


# ------------------------------------------------------- once a frame


def test_the_layer_redraws_once_a_frame_however_many_moves_arrive():
    body = fn("wsScheduleDrawRender")
    assert "if (wsDrawFrame) return;" in body
    assert "requestAnimationFrame(" in body and "wsDrawFrame = 0;" in body


def test_dragging_a_drawing_draws_on_the_frame_not_the_event():
    drag = strip_comments(listener("pointermove", "if (!wsDragging) return;"))
    assert "wsScheduleDrawRender();" in drag
    assert "wsRenderDrawings()" not in drag


def test_the_pointer_is_only_noted_as_it_moves():
    hover = strip_comments(listener(
        "pointermove", "if (STATE.view !== 'chart' || wsTool === 'cursor' || wsDragging) return;"))
    assert "wsHoverAt = { clientX: evt.clientX, clientY: evt.clientY };" in hover
    assert "wsScheduleDrawRender();" in hover
    for heavy in ("wsRenderDrawings()", "wsSeries(", "wsPointAt("):
        assert heavy not in hover, heavy


def test_a_ruler_does_not_look_up_the_window_per_drawing():
    body = fn("wsRenderDrawings")
    assert body.count("wsSeries(STATE.chartData)") == 1
    assert "shownDates || (shownDates =" in body
    assert "const dates = seriesDates();" in body


# ------------------------------------------------ the shape follows


def test_one_painter_draws_the_saved_drawings_and_the_one_being_placed():
    body = fn("wsRenderDrawings")
    assert "const paint = (dr, preview) => {" in body
    assert "list.forEach((dr) => paint(dr, false));" in body
    assert "paint(ghost, true);" in body
    # A preview is not selectable and carries no grab targets.
    assert "const sel = !preview && dr.id === wsSelected;" in body
    assert "if (!preview) [...g.querySelectorAll('line')].forEach((ln) => {" in body


def test_the_ghost_is_what_is_placed_plus_the_pointer():
    got = _jsc("""
      var wsTool = 'cursor', wsPending = null, wsHoverAt = null;
      var TOOL_POINTS = { trend: 2, channel: 3, hline: 1 };
      function wsToolNeeds(t) { return TOOL_POINTS[t] || 0; }
      function wsSnappedPoint(at) { return at.off ? null : { i: at.clientX, p: at.clientY }; }
    """ + raw_fn("wsGhost") + """
      var out = {};
      out.cursor = wsGhost();
      wsTool = 'hline'; out.noPointer = wsGhost();
      wsHoverAt = { clientX: 5, clientY: 10 }; out.level = wsGhost().points;
      wsTool = 'channel'; wsPending = { kind: 'channel', points: [{ i: 1, p: 2 }] };
      out.second = wsGhost().points;
      wsPending.points.push({ i: 3, p: 4 }); out.third = wsGhost().points;
      wsHoverAt = { clientX: 5, clientY: 10, off: true }; out.offPlot = wsGhost().points;
      print(JSON.stringify(out));
    """)
    assert got["cursor"] is None and got["noPointer"] is None
    assert got["level"] == [{"i": 5, "p": 10}]
    assert got["second"] == [{"i": 1, "p": 2}, {"i": 5, "p": 10}]
    assert got["third"] == [{"i": 1, "p": 2}, {"i": 3, "p": 4}, {"i": 5, "p": 10}]
    assert got["offPlot"] == [{"i": 1, "p": 2}, {"i": 3, "p": 4}]


def test_the_shape_is_drawn_once_it_has_the_points_it_needs():
    body = fn("wsRenderDrawings")
    assert "if (ghost && ghost.points.length >= wsToolNeeds(ghost.kind)) {" in body


# ------------------------------------------------------ a drag draws


def _jsc(script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    out = subprocess.run([exe, "-e", script], capture_output=True, text=True, timeout=30)
    last = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else ""
    assert last.startswith("{"), out.stdout + out.stderr
    return json.loads(last)


def test_a_release_away_from_the_press_places_the_next_point():
    got = _jsc("""
      var handlers = {};
      var document = { addEventListener: function (t, f) { (handlers[t] = handlers[t] || []).push(f); } };
      var DRAW_DRAG_PX = 6, wsPending = null, wsDrawPress = null, placed = [];
      function wsSnappedPoint(evt) { return { i: evt.clientX, p: evt.clientY }; }
      function wsPlacePoint(pt) { placed.push(pt); wsPending.points.push(pt); }
    """ + listener("pointerup", "const press = wsDrawPress;") + """
      var up = handlers.pointerup[0], out = {};
      // Pressed at (100, 100) and released 40px along: the second point.
      wsPending = { points: [{ i: 100, p: 100 }] }; wsDrawPress = { x: 100, y: 100, count: 1 };
      up({ clientX: 140, clientY: 100 }); out.drag = placed.slice(); placed = [];
      // Released where it was pressed: a click, so nothing yet.
      wsPending = { points: [{ i: 100, p: 100 }] }; wsDrawPress = { x: 100, y: 100, count: 1 };
      up({ clientX: 103, clientY: 102 }); out.click = placed.slice();
      out.cleared = wsDrawPress;
      // The press finished the drawing: nothing to add to.
      wsPending = null; wsDrawPress = { x: 100, y: 100, count: 1 };
      up({ clientX: 160, clientY: 100 }); out.finished = placed.slice();
      // A second finger placed a point during the drag: the drag's release
      // is not the next point of a drawing that has moved on without it.
      wsPending = { points: [{ i: 100, p: 100 }, { i: 120, p: 90 }] };
      wsDrawPress = { x: 100, y: 100, count: 1 };
      up({ clientX: 160, clientY: 100 }); out.movedOn = placed.slice();
      print(JSON.stringify(out));
    """)
    assert got == {"drag": [{"i": 140, "p": 100}], "click": [], "cleared": None,
                   "finished": [], "movedOn": []}


def test_a_press_that_does_not_finish_the_drawing_is_remembered():
    body = fn("wsBeginDraw")
    assert "wsPlacePoint(pt);" in body
    assert ("wsDrawPress = wsPending\n    ? { x: evt.clientX, y: evt.clientY, count: "
            "wsPending.points.length } : null;") in body
    down = strip_comments(listener(
        "pointerdown", "if (STATE.view !== 'chart') return;\n  const layer = evt.target.closest"))
    assert "layer.setPointerCapture(evt.pointerId)" in down


def test_a_click_and_a_release_place_a_point_the_same_way():
    """One path for both, so a dragged point snaps and finishes a drawing
    exactly as a clicked one does."""
    assert "const pt = wsSnappedPoint(evt);" in fn("wsBeginDraw")
    up = strip_comments(listener("pointerup", "const press = wsDrawPress;"))
    assert "if (pt) wsPlacePoint(pt);" in up
    place = fn("wsPlacePoint")
    assert "wsSaveDrawings([...wsDrawings(), dr]);" in place
    assert "wsTool = 'cursor';" in place


# ---------------------------------------------------------- the handles


def test_a_handle_is_grabbed_well_outside_its_dot():
    body = fn("wsRenderDrawings")
    grab = body.index("r: DRAW_HANDLE_GRAB_R, fill: 'transparent',")
    dot = body.index("r: DRAW_HANDLE_R, fill: C.surface,")
    assert grab < dot, "the grab area goes under the dot"
    assert "class: 'ws-dr-handle ws-dr-grab', 'data-handle': i," in body
    assert re.search(r"const DRAW_HANDLE_GRAB_R = (\d+);", APP).group(1) == "11"


# -------------------------------------------------------------- styles


def test_the_shape_being_placed_never_takes_the_click():
    assert ".ws-draw-svg .ws-dr-pending,\n.ws-draw-svg .ws-dr-pending * { pointer-events: none; }" in CSS


def test_a_finger_draws_while_a_tool_is_armed():
    assert ".ws-canvas.arming .ws-draw { touch-action: none; }" in CSS
