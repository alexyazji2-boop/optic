"""Reset, and an undo stack that can reverse it.

Reported from a screenshot of the charting tab carrying three averages, two
EMA clouds, a supply band, two Fibonacci levels, a 40-week average and an RSI
pane, with eight price tags stacked down the right edge: "include a clear
button to clean up the chart for times when it gets cluttered".

Undo and redo already existed on that tab, in the drawing rail, bound to the
platform shortcut. They covered `wsDrawings()` and nothing else -- which is
what they were written for and is not what gets cluttered. So Reset turns the
overlays off, and the stack was widened to hold everything Reset touches, so
the arrow a reader already has reverses it.

Verified in a browser at 1440x950 on AAPL. Cluttered to fourteen overlays and
two panes: Reset gave one overlay (volume) and no panes and disabled itself;
the rail's undo arrow gave all fourteen and both panes back; redo returned to
one. Two drawings on the chart survived the reset, and the original
drawing-only undo still round-trips 1 -> 0 -> 1.
"""

from __future__ import annotations

import re

APP = open("static/app.js", encoding="utf-8").read()


def _fn(name):
    start = APP.index("function %s(" % name)
    return APP[start:APP.index("\n}", start)]


def _code(text):
    """Comments stripped. A comment saying what a function must NOT touch
    names the thing it must not touch."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"^\s*//.*$", "", text, flags=re.M)


# ------------------------------------------------------------ the control


def test_the_button_exists_and_has_a_handler():
    """Both directions, as everywhere else in this file. A dead control does
    not error; it takes the click and nothing happens."""
    # Bounded. `data-ws-reset` is a prefix of `data-ws-resetX`, so a bare
    # substring check passes on a renamed attribute -- which is exactly how
    # this test first survived its own mutation.
    assert re.search(r"data-ws-reset(?![\w-])", APP), "the attribute is gone"
    assert 'class="ws-menu-btn ws-reset" data-ws-reset\n' in APP
    assert "evt.target.closest('[data-ws-reset]')" in APP
    assert "wsResetChart();" in APP


def test_the_button_is_not_inside_the_phone_drawer():
    """`.ws-tools` is `display: none` on a phone until Tools is pressed. A
    declutter is most wanted when the drawer is shut, and it was verified
    reachable at 375x812 with the drawer closed."""
    bar = APP.split("function wsToolbar() {", 1)[1]
    bar = bar[:bar.index("\n}")]
    before_group = bar[:bar.index('<div class="ws-tools">')]
    assert "data-ws-reset" in before_group


def test_the_button_says_so_when_it_would_do_nothing():
    """A control that would change nothing should not take the click."""
    assert "${wsChartIsClean() ? 'disabled' : ''}" in APP
    fn = _fn("wsChartIsClean")
    assert "wsPanesOpen.length" in fn
    assert "wsPriceIndicatorIds().length" in fn
    assert "seriesHidden" in fn
    assert "Object.keys(WS_FLAGS)" in fn


# -------------------------------------------------------- what it resets


def test_reset_targets_the_documented_default_not_a_written_out_list():
    """Price and volume and nothing else, which is the state the versioned
    storage keys were bumped to produce. Derived from WS_FLAGS so an overlay
    added later is cleared without anyone remembering a second place --
    otherwise Reset silently declines to clear the newest toggle, which is
    the dead-control bug wearing a different hat."""
    fn = _fn("wsResetChart")
    assert "Object.keys(WS_FLAGS).forEach" in fn
    assert "WS_RESET_KEEP.includes(id)" in fn
    assert "const WS_RESET_KEEP = ['vol'];" in APP, \
        "volume is a strip under the price, not a line across it"


def test_reset_clears_the_panes_and_the_studies_too():
    fn = _fn("wsResetChart")
    assert "wsPanesOpen = [];" in fn
    assert "indicatorIds = [];" in fn
    assert "wsIndicators = null;" in fn
    assert "seriesHidden = {};" in fn


def test_reset_does_not_touch_the_drawings():
    """They are the reader's own work rather than a display setting, they
    have their own Clear in the tool rail, and a declutter that silently
    deleted an hour of annotation would be the worst bug on this tab.
    Measured: two drawings before a reset, two after."""
    fn = _code(_fn("wsResetChart"))
    assert "wsSaveDrawings" not in fn
    assert "wsDrawings" not in fn


def test_reset_is_reversible():
    """It pushes its own snapshot before mutating, so the arrow in the rail
    and the platform shortcut both reverse it."""
    fn = _fn("wsResetChart")
    assert fn.index("wsPushUndo();") < fn.index("Object.keys(WS_FLAGS)")


# ------------------------------------------------- the widened undo stack


def test_the_snapshot_covers_everything_reset_touches():
    """The stack held `wsDrawings()` alone. Undoing a reset would have put
    the drawings back over a chart that still had nothing on it."""
    fn = _fn("wsChartState")
    for part in ("drawings:", "flags", "panes:", "studies:", "hidden:"):
        assert part in fn, part
    assert "Object.keys(WS_FLAGS).forEach" in fn, \
        "a written-out flag list is the thing this avoids"
    assert "JSON.stringify(wsChartState())" in _fn("wsPushUndo")


def test_restoring_a_flag_goes_through_the_setter():
    """The setters write the preference to localStorage and fetch the two
    payloads that have their own endpoints. Assigning `showTrends = true`
    would light the checkbox over a chart with nothing on it."""
    fn = _code(_fn("wsApplyChartState"))
    assert "wsSetOverlay(id, !!st.flags[id])" in fn
    assert "showTrends =" not in fn and "showFib =" not in fn


def test_undo_repaints_the_whole_chart_not_just_the_overlay_layer():
    """Restoring drawings needs the drawing layer; restoring flags, panes and
    studies changes the series the chart is built from."""
    fn = _fn("wsRestore")
    assert "wsRepaintWithPanes();" in fn
    assert "wsApplyChartState(" in fn
    # And both directions share it, or they drift.
    assert "function wsUndo() { wsRestore(wsUndoStack, wsRedoStack); }" in APP
    assert "function wsRedo() { wsRestore(wsRedoStack, wsUndoStack); }" in APP


def test_the_drawing_rail_still_carries_undo_and_redo():
    """They were already there and bound to the platform shortcut. This is
    the both-directions check for the controls the widened stack is reached
    through."""
    rail = _fn("wsToolRail")
    assert "data-ws-undo" in rail and "data-ws-redo" in rail
    assert "wsUndoStack.length ? '' : 'disabled'" in rail
    assert "wsRedoStack.length ? '' : 'disabled'" in rail
    assert "data-ws-clear-draw" in rail, "drawings keep their own clear"
