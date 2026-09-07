"""Tests for who owns a drag on the price chart.

A left-drag can only mean one thing, and this chart has three candidates: pan,
measure, and draw. The split is deliberate and has already been reversed once —
measuring held the plain drag while panning lived only on the navigator strip
below the chart, which read as "the chart cannot be dragged" to anyone who
reached for the gesture every other charting tool has.

Nothing here can drive a mouse; what it checks is the wiring that decides which
handler gets the event. Each assertion stands for a failure that is silent in the
browser: a gesture that quietly does nothing, or two handlers that both fire.
"""

APP = open("static/app.js", encoding="utf-8").read()
CHARTS = open("static/charts.js", encoding="utf-8").read()


def _block(source, marker, end="\n}"):
    start = source.index(marker)
    return source[start:source.index(end, start)]


def test_only_the_pannable_chart_gives_up_its_plain_drag():
    """The Swing chart has no zoom and no pan, so a plain drag there still
    measures. Setting panDrag on both would leave that chart with a gesture that
    demands a modifier for no reason, and no gesture at all without one."""
    assert APP.count("panDrag: true") == 1


def test_line_chart_defaults_to_measuring_on_a_plain_drag():
    """Every other caller — the sparklines, the breadth strip, the Swing chart —
    passes no opinion and must keep the behaviour it had."""
    assert "\n    panDrag = false,\n" in CHARTS


def test_measure_defers_before_it_swallows_the_default():
    """Load-bearing ordering. The pan handler runs on pointerdown and calls
    preventDefault, which suppresses the compatibility mousedown entirely — so
    on a pannable chart this listener is usually never reached. It IS reached
    when the pan declines the gesture, which happens when the whole history is
    already on screen. Calling preventDefault before the guard would eat the
    event on behalf of a measurement that is not going to happen."""
    handler = _block(CHARTS, "overlay.addEventListener('mousedown'", "\n  });")
    guard = handler.index("if (panDrag && !evt.shiftKey) return;")
    default = handler.index("evt.preventDefault();")
    assert guard < default, "preventDefault runs before the guard"


def test_panning_yields_to_every_more_specific_gesture():
    """Shift means measure, an armed tool means draw, and a drag that started on
    a drawing means move that drawing. Panning is the fallback, so each of these
    has to be checked before it claims the event."""
    handler = _block(APP, "let wsPan = null;\n\ndocument.addEventListener('pointerdown'", "\n});")
    assert "evt.shiftKey || wsTool !== 'cursor'" in handler
    # A drawing lives in #ws-draw, a sibling of #ws-chart, so requiring the
    # target to be inside the chart is what leaves drawings to their own handler.
    assert "closest('#ws-chart')" in handler
    assert "if (!host) return;" in handler


def test_panning_declines_touch_so_the_page_can_still_scroll():
    """preventDefault on a touch pointerdown cancels the scroll the gesture
    would have become, which pins the page under a finger dragged down the
    chart."""
    handler = _block(APP, "let wsPan = null;\n\ndocument.addEventListener('pointerdown'", "\n});")
    assert "evt.pointerType !== 'mouse' && evt.pointerType !== 'pen'" in handler


def test_panning_does_nothing_when_there_is_nothing_to_pan():
    """At the widest range the window already covers the history. Claiming the
    drag there would show a grab cursor for a gesture that cannot move."""
    handler = _block(APP, "let wsPan = null;\n\ndocument.addEventListener('pointerdown'", "\n});")
    assert "if (win.to - win.from >= win.total) return;" in handler


def test_the_pan_moves_the_window_rather_than_resizing_it():
    """wsApplyWindow preserves the span. Writing from/to independently is what a
    navigator edge-handle does, and doing it here would zoom while panning."""
    assert "if (wsApplyWindow({ from: wsPan.from - bars, to: wsPan.to - bars })) wsRedrawChart();" in APP


def test_the_drag_moves_the_chart_not_a_scrollbar():
    """Dragging right shows earlier bars, because the thing under the cursor is
    the chart. Subtracting is the whole of that; the sign is the bug."""
    handler = _block(APP, "document.addEventListener('pointermove', (evt) => {\n  if (!wsPan) return;", "\n});")
    assert "(evt.clientX - wsPan.x) * wsPan.barsPerPx" in handler
    assert "wsPan.from - bars" in handler


def test_the_hint_names_the_gestures_that_exist():
    """The status strip is the only place the gestures are written down, and it
    described the arrangement this replaced."""
    assert "'Drag to pan, scroll to zoom, shift-drag to measure'" in APP
    assert "drag the chart to measure" not in APP


def test_measuring_keeps_a_second_way_in():
    """Giving up the plain drag is only affordable because the ruler in the tool
    rail measures too, and unlike the gesture it leaves a drawing behind."""
    rail = _block(APP, "const WS_TOOLS = [", "\n];")
    assert "id: 'ruler'" in rail


def test_the_pan_state_is_cleared_on_cancel_as_well_as_release():
    """pointercancel fires when the browser takes the gesture over. Without it
    the body keeps the grabbing cursor and the next mousemove pans with no
    button held."""
    assert "document.addEventListener('pointerup', wsEndPan);" in APP
    assert "document.addEventListener('pointercancel', wsEndPan);" in APP
