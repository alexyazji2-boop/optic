"""Tests for who owns a drag on the price chart.

A left-drag has three candidates on this chart: pan, measure, and draw. The
split has gone every way. Measuring held the plain drag while panning lived
only on the navigator strip; then the drag panned and the measurement moved to
shift-drag, reported as "the drag feature to see percent change is not
working"; then the drag measured and shift panned, reported as "dragging left
and right on the chart with a left click does not move the chart".

Both are wanted, so time tells them apart: a plain drag pans, and a press held
still for 300ms, or a shifted one, measures. An armed tool draws. A chart with
nothing to pan measures on a plain drag. tests/test_chart_hold_to_measure.py
runs the chart's side of this; what is checked here is the wiring that decides
which handler gets the event. Each assertion stands for a failure that is
silent in the browser: a gesture that quietly does nothing, or two handlers
that both fire.
"""

import re

APP = open("static/app.js", encoding="utf-8").read()
CHARTS = open("static/charts.js", encoding="utf-8").read()


def _block(source, marker, end="\n}"):
    start = source.index(marker)
    return source[start:source.index(end, start)]


def test_every_chart_that_pans_says_so():
    """The pan no longer claims the pointer before the chart's mousedown, so a
    chart that pans has to know to wait out a hold rather than measure at once.
    Every registered chart passes panDrag, and nothing else does."""
    hosts = re.findall(r"^registerChartZoom\('([\w-]+)'", APP, re.M)
    assert sorted(hosts) == ["chart-price", "chart-weekly", "ws-chart"]
    assert APP.count("panDrag: true") == len(hosts)
    for host in ("chart-price", "chart-weekly"):
        opts = _block(APP, "mount('%s', (w) => lineChart({" % host, "\n    }")
        assert "panDrag: true," in opts, host
    ws = _block(APP, "function wsMountChart(", "\n}")
    assert "panDrag: true," in ws


def test_line_chart_defaults_to_measuring_on_a_plain_drag():
    """Every other caller — the sparklines, the breadth strip, the Swing chart —
    passes no opinion and must keep the behaviour it had."""
    assert "\n    panDrag = false,\n" in CHARTS


def test_a_press_measures_at_once_unless_the_pan_has_armed_the_chart():
    """The pan arms the chart's host on pointerdown, which comes before the
    mousedown, and only when it can move the chart. Shift, a chart that does
    not pan, and one with its whole history on screen measure from the press.
    Otherwise the press waits: held still it measures, moved it is the pan's."""
    handler = _block(CHARTS, "overlay.addEventListener('mousedown'", "\n  });")
    assert "const armed = root.closest ? root.closest('[data-pan-armed]') : null;" in handler
    assert "if (!panDrag || evt.shiftKey || !armed) { beginMeasure(at); return; }" in handler
    assert "}, HOLD_MS);" in handler
    # Every press, so no text is selected under a pan or a measurement.
    assert handler.index("evt.preventDefault();") < handler.index("if (!panDrag")
    assert "const HOLD_MS = 300;" in CHARTS and "const HOLD_SLOP = 4;" in CHARTS


def test_panning_yields_to_every_more_specific_gesture():
    """Shift means measure, an armed tool means draw, and a drag that
    started on a drawing means move that drawing. Panning takes a plain drag
    that moves before the hold is up, and each of these has to be checked
    before it claims the event.

    The three checks now live in three places, because the handler is shared by
    every chart that registers for it rather than hardcoded to the workspace:
    shift is universal and stays inline; the armed tool is workspace-specific
    and is reported by its adapter's `enabled`; and the drawing layer is a
    SIBLING of #ws-chart, so a hit on one of its strokes resolves no zoom target
    at all.
    """
    handler = _block(APP, "let wsPan = null;\n\ndocument.addEventListener('pointerdown'", "\n});")
    assert "if (evt.shiftKey) return;" in handler
    assert handler.index("if (evt.shiftKey) return;") < handler.index("chartZoomTarget(evt)")
    # No preventDefault: it would suppress the mousedown that times the hold.
    code = re.sub(r"/\*.*?\*/", " ", handler, flags=re.S)
    assert "preventDefault" not in code
    assert "target.host.dataset.panArmed = '1';" in handler
    assert "const target = chartZoomTarget(evt);" in handler
    assert "if (!target) return;" in handler
    # The workspace adapter still declines while a tool is armed.
    ws = _block(APP, "registerChartZoom('ws-chart', {", "});")
    assert "wsTool === 'cursor'" in ws
    # And resolution is by registered host id, so only a registered chart pans.
    resolver = _block(APP, "function chartHostFor(", "\n}")
    assert "evt.target.closest('#' + hostId)" in resolver
    # The drawing overlay resolves to its chart for the wheel only. A press on
    # a drawing must still find no target, or the pan would take the drag that
    # moves the drawing; tests/test_chart_wheel_routing.py drives both.
    assert "if (wheel && adapter.overlay && evt.target.closest(adapter.overlay))" in resolver


def test_panning_declines_touch_so_the_page_can_still_scroll():
    """A finger dragged across a chart is scrolling the page. Panning it too
    would move two things under one finger."""
    handler = _block(APP, "let wsPan = null;\n\ndocument.addEventListener('pointerdown'", "\n});")
    assert "evt.pointerType !== 'mouse' && evt.pointerType !== 'pen'" in handler


def test_panning_does_nothing_when_there_is_nothing_to_pan():
    """At the widest range the window already covers the history. Claiming the
    drag there would show a grab cursor for a gesture that cannot move."""
    handler = _block(APP, "let wsPan = null;\n\ndocument.addEventListener('pointerdown'", "\n});")
    assert "if (win.to - win.from >= win.total) return;" in handler


def test_the_pan_moves_the_window_rather_than_resizing_it():
    """The adapter's `apply` preserves the span. Writing from/to independently is
    what a navigator edge-handle does, and doing it here would zoom while
    panning. Both ends move by the same `bars`, which is the whole guarantee."""
    handler = _block(APP, "document.addEventListener('pointermove', (evt) => {\n  if (!wsPan) return;", "\n});")
    assert "pan.next = { from: pan.from - bars, to: pan.to - bars };" in handler
    # Applied and drawn once a frame, in the frame: see test_chart_zoom_lag.
    assert "if (pan.adapter.apply(pan.next)) interactiveRedraw(pan.adapter);" in handler


def test_the_pan_remembers_which_chart_it_started_on():
    """The registry can resolve a different chart under the cursor mid-drag —
    two charts can be on screen at once on the Options tab. The adapter is
    captured at pointerdown so the gesture keeps moving the chart it grabbed."""
    down = _block(APP, "let wsPan = null;\n\ndocument.addEventListener('pointerdown'", "\n});")
    assert "adapter: target.adapter" in down


def test_the_drag_moves_the_chart_not_a_scrollbar():
    """Dragging right shows earlier bars, because the thing under the cursor is
    the chart. Subtracting is the whole of that; the sign is the bug."""
    handler = _block(APP, "document.addEventListener('pointermove', (evt) => {\n  if (!wsPan) return;", "\n});")
    assert "(evt.clientX - wsPan.x) * wsPan.barsPerPx" in handler
    assert "pan.from - bars" in handler


def test_the_pan_waits_out_a_hold_and_stands_aside_for_a_measurement():
    """The pan moves nothing until the pointer has gone further than a hold
    allows, the same few pixels the chart's timer allows, so a press held still
    never nudges the chart under the anchor it measures from. Once the chart
    reports a measurement, anywhere in the host, the rest of the drag is its."""
    handler = _block(APP, "document.addEventListener('pointermove', (evt) => {\n  if (!wsPan) return;", "\n});")
    measuring = handler.index("if (wsPan.host.querySelector('[data-measuring]')) return;")
    slop = handler.index("Math.abs(evt.clientX - wsPan.x) <= PAN_SLOP) return;")
    assert measuring < slop < handler.index("pan.next =")
    assert "const PAN_SLOP = 4;" in APP
    # The closed hand only once it pans, not for a press that may measure.
    assert "if (!wsPan.moved) document.body.classList.add('ws-panning');" in handler
    down = _block(APP, "let wsPan = null;\n\ndocument.addEventListener('pointerdown'", "\n});")
    assert "ws-panning" not in down


def test_a_pan_never_selects_text_and_leaves_nothing_armed():
    assert "document.addEventListener('selectstart', (evt) => { if (wsPan) evt.preventDefault(); });" in APP
    end = _block(APP, "function wsEndPan() {", "\n}")
    assert "delete wsPan.host.dataset.panArmed;" in end
    # A release the page never saw is cleared by the next press.
    down = _block(APP, "let wsPan = null;\n\ndocument.addEventListener('pointerdown'", "\n});")
    assert down.index("wsEndPan();") < down.index("if (evt.button !== 0) return;")


def test_the_hint_names_the_gestures_that_exist():
    """The status strip is the only place the gestures are written down, and it
    described the arrangements this replaced."""
    assert "'Drag to pan, hold then drag to measure, scroll to zoom'" in APP
    assert "'Drag to measure, scroll to zoom, shift-drag to pan'" not in APP
    assert "'Drag to pan, scroll to zoom, shift-drag to measure'" not in APP


def test_the_plot_keeps_its_crosshair():
    """It points at a bar, which hovering, a held press and the drawing tools
    all need. The closed hand is for a pan under way."""
    css = open("static/styles.css", encoding="utf-8").read()
    assert ".ws-chart { cursor: grab; }" not in css
    assert "body.ws-panning, body.ws-panning * { cursor: grabbing !important; }" in css


def test_measuring_keeps_a_second_way_in():
    """The ruler in the tool rail measures too, and unlike the gesture it leaves
    a drawing behind."""
    rail = _block(APP, "const WS_TOOLS = [", "\n];")
    assert "id: 'ruler'" in rail


def test_the_pan_state_is_cleared_on_cancel_as_well_as_release():
    """pointercancel fires when the browser takes the gesture over. Without it
    the body keeps the grabbing cursor and the next mousemove pans with no
    button held."""
    assert "document.addEventListener('pointerup', wsEndPan);" in APP
    assert "document.addEventListener('pointercancel', wsEndPan);" in APP


def test_every_zoom_registration_runs_after_the_registry_exists():
    """The temporal dead zone, which cost a blank app.

    `CHART_ZOOM` is a top-level `const`, and `registerChartZoom(...)` calls run
    at parse time. Registering the Options chart from beside its own code —
    ~7,900 lines above the declaration — threw "Cannot access 'CHART_ZOOM'
    before initialization", which killed the rest of the script: every view
    rendered empty and the only symptom in the console was that one line.

    The adapters' own functions are function DECLARATIONS, so they hoist and can
    live next to the chart they describe. Only the registration call has to be
    down here.
    """
    decl = APP.index("const CHART_ZOOM = new Map();")
    calls = [m.start() for m in re.finditer(r"^registerChartZoom\(", APP, re.M)]
    assert calls, "no chart registers for pan and zoom"
    for at in calls:
        assert at > decl, (
            "registerChartZoom is called %d chars before CHART_ZOOM exists"
            % (decl - at))


def test_the_options_chart_registers_for_pan_and_zoom():
    """It could not pan or zoom at all; the wheel over it did nothing while the
    Charting tab had both."""
    block = _block(APP, "registerChartZoom('chart-price', {", "});")
    assert "STATE.view === 'swing'" in block
    assert "swingWindowNow(STATE.swing)" in block
    assert "swingRedrawChart()" in block
    # Intraday is no longer declined. It was, while swingWindow indexed the
    # daily series only, and that is why nothing zoomed a chart under a day.
    # The window counts the intraday bars now (swingBaseSeries), so the
    # adapter only waits for there to be bars.
    assert "!isIntradayRange(chartRange)" not in block
    assert "((swingBaseSeries(STATE.swing).dates) || []).length > 1" in block


def test_the_zoom_window_cannot_outlive_what_it_indexes():
    """A window is a pair of bar indices into one particular series. The range
    pills and the interval select are shared with the Charting tab and the
    ticker changes from four places, so the window is keyed instead of reset:
    a key mismatch reads as "not zoomed" and no reset site can be missed."""
    assert "function swingWindowKey() {" in APP
    for fn in ("swingSeries", "swingWindowNow"):
        body = _block(APP, "function %s(" % fn, "\n}")
        assert "swingWindow.key === swingWindowKey()" in body, fn


def test_the_options_zoom_repaints_the_chart_not_the_view():
    """renderSwing builds twenty panels and ~3,200 nodes. Doing that per wheel
    notch is what a zoom must not cost."""
    body = _block(APP, "function swingRedrawChart() {", "\n}")
    assert "swingPriceBlock(STATE.swing, ps, swingChartCtx)" in body
    assert "renderSwing" not in body


def test_the_bar_count_in_the_heading_has_one_source():
    """The heading states the window, so it changes on every zoom. Two copies of
    that sentence would disagree the first time one was edited."""
    assert "function swingBarCountText(ps) {" in APP
    assert APP.count("swingBarCountText(ps)") >= 2, "template and redraw both use it"
    body = _block(APP, "function swingRedrawChart() {", "\n}")
    assert "swingBarCountText(ps)" in body
