"""The Charting tab gives its space to the chart.

Asked for by pointing at another terminal's chart: one that fills the window.
Optic's plot was 340px of a 900px window, 38%, with 316px of chrome stacked
above a workspace sized `100dvh - var(--chrome-h)`.

Three findings, in the order they were measured at 1440x900.

`--chrome-h` went stale. It is this view's own offset from the top of the page,
republished by wsSyncChromeHeight -- which runs on mount, on a ws-body WIDTH
change and on a window resize. Collapsing the session fold is none of those: it
changes the chrome's HEIGHT. So closing it moved the view from 316 to 259 while
the variable stayed 316, and the 57px the chart should have gained became a gap
under the page instead.

The fold then defaults closed here. Everywhere else a desktop has room for the
timetable; this is the one view sized against the viewport rather than scrolled,
so every pixel above it comes off the plot.

And the session bar is off entirely, which is de-duplication before it is a
space grab. The chart's own header already states the phase -- "AAPL 336.72
338.91 334.30 335.92 V 24,696,400 -0.33% Overnight" -- so the bar above it said
OVERNIGHT a second time, with a phase strip and a timetable, over a chart that
draws its own dates and a status line already reading "Chart: AAPL 1D 6m".

Measured after: plot 512px, 57% of the window, with all 87 controls still on
the toolbar. The two-row toolbar was left alone on purpose -- forced to one row
it overflows by 310px and squashes a control to 2px, so it would buy 44px by
clipping features.
"""

from __future__ import annotations

import re

APP = open("static/app.js", encoding="utf-8").read()
CSS = open("static/styles.css", encoding="utf-8").read()


def _code(src):
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", " ", src)


def _fn(name):
    src = _code(APP)
    start = src.index("function %s(" % name)
    return src[start:src.index("\n}", start)]


def test_the_fold_republishes_the_chrome_height():
    """The bug that made the other two changes worth nothing on their own: the
    workspace is sized from a variable, and the fold changed the thing the
    variable measures without anything recomputing it."""
    fn = _fn("initSessionBar") if "function initSessionBar(" in _code(APP) else _code(APP)
    handler = fn[fn.index("detailBtn.addEventListener"):][:900]
    assert "wsSyncChromeHeight()" in handler, \
        "folding the session changes --chrome-h and nothing was republishing it"
    assert "STATE.view === 'chart'" in handler, "only the sized view needs it"


def test_the_fold_starts_closed_on_the_charting_view():
    fn = _fn("sessionDetailOpen")
    assert "STATE.view === 'chart'" in fn
    # After the stored answer, or a reader who opened it there loses it.
    assert fn.index("saved === '0'") < fn.index("STATE.view === 'chart'"), \
        "an explicit choice has to outrank the view"


def test_the_session_bar_is_hidden_only_on_charting():
    code = _code(CSS)
    rule = re.search(r'body\[data-view="chart"\]\s+\.sessionbar\s*\{([^}]*)\}', code)
    assert rule and "display: none" in rule.group(1)
    # Everywhere else it is the only thing saying what the market is doing.
    assert not re.search(r'(?<!\])\s\.sessionbar\s*\{[^}]*display:\s*none', code), \
        "the bar must not be hidden globally"


def test_the_workspace_is_still_sized_from_the_variable():
    """If this stops being viewport-sized the three fixes above stop mattering
    and nobody would notice, because the page would simply scroll."""
    code = _code(CSS)
    assert "height: calc(100dvh - var(--chrome-h" in code


def test_the_toolbar_still_wraps():
    """Left alone deliberately. Measured with `flex-wrap: nowrap` at 1440px:
    310px of horizontal overflow and a control squashed to 2px. One row would
    be bought by clipping controls, and the ask was to keep every feature."""
    code = _code(CSS)
    block = code.split(".ws-toolbar {", 1)[1]
    block = block[:block.index("}")]
    assert "flex-wrap: wrap" in block
