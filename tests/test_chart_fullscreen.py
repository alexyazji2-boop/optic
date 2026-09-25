"""Full screen for the chart, and the legend that stopped being pinned to 44px.

Two mechanisms, deliberately. `body.ws-max` does the work and cannot be
refused; the Fullscreen API is asked for on top and is allowed to fail, because
it can be (an iframe without allow="fullscreen", a policy, an old engine). The
browser pane these were driven in refuses it, which made that the tested path
rather than the theoretical one: the class carried full screen on its own.

Measured entering full screen at a 1400x1000 window: plot 769x570 -> 1038x763.
Drawing verified inside it with real hit-testing -- the layer is transparent to
the pointer until a tool is armed, a trendline was created at bars 31->94,
dragged exactly 20 bars, undone with Cmd+Z and deleted.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
CSS = (ROOT / "static/styles.css").read_text()


def function(name):
    return re.search(r"^(?:async )?function " + name + r"\([^\n]*\) \{.*?^\}",
                     APP, re.M | re.S).group()


def rule(selector):
    """The declarations of the first rule whose selector list contains this."""
    i = CSS.index(selector)
    return CSS[i:CSS.index("}", i)]


# ------------------------------------------------- the two mechanisms


def test_the_class_does_the_work_and_the_api_is_a_bonus():
    """If the API were the mechanism, a refusal would be a button that does
    nothing -- and refusal is ordinary, not exceptional."""
    fn = function("wsSetMaximised")
    assert "classList.toggle(WS_MAX_CLASS" in fn, \
        "the class is what makes the chart full screen"
    # The class is set whether or not the request is granted: no await, no
    # then, nothing that makes the layout wait on a permission.
    assert "await" not in fn and ".then(" not in fn


def test_a_refused_fullscreen_request_is_not_an_error():
    """requestFullscreen rejects when it is not allowed, and an unhandled
    rejection in a click handler is a console error on a path that is working
    as designed."""
    fn = function("wsRequestNativeFullscreen")
    assert fn.count("catch(() => {})") == 2, \
        "both directions have to swallow the rejection"
    # Older engines throw synchronously instead of returning a promise.
    assert "try {" in fn and "} catch (e)" in fn


def test_fullscreen_is_asked_for_on_the_root_not_the_workspace():
    """Fullscreen renders the chosen element and its DESCENDANTS ONLY. Two
    things this chart needs are neither: `#tooltip`, which is the crosshair
    readout, and `#auth-toasts`, which is how "No chart to draw on yet"
    reaches anybody. Both are children of <body>.

    On `.ws-body` -- the obvious element to point at -- the chart would go full
    screen and lose its own readout."""
    fn = function("wsRequestNativeFullscreen")
    assert "document.documentElement" in fn
    assert ".ws-body" not in fn, "this is the trap, not the fix"
    # And the two orphans are really outside the workspace, which is the whole
    # reason. If either ever moves inside it this test should be revisited.
    html = (ROOT / "static/index.html").read_text()
    assert 'id="tooltip"' in html
    assert html.index('id="view-chart"') < html.index('id="tooltip"'), \
        "the tooltip is a sibling of the app, not a child of the workspace"


def test_both_spellings_of_the_api_are_handled():
    """Safari still ships the webkit-prefixed names."""
    for fn in (function("wsNativeFullscreen"), function("wsRequestNativeFullscreen")):
        assert "webkit" in fn, fn[:80]


# ------------------------------------------------- getting back out


def test_leaving_fullscreen_by_any_route_clears_the_class():
    """Escape, F11 and the browser's own exit all end native fullscreen without
    going through the toggle. The class would be left behind: a chart filling
    the window with no way back to the rail."""
    assert "'fullscreenchange', 'webkitfullscreenchange'" in APP
    block = APP.split("'fullscreenchange', 'webkitfullscreenchange'", 1)[1][:600]
    assert "classList.remove(WS_MAX_CLASS)" in block


def test_it_only_follows_fullscreen_downwards():
    """Going up happens when the reader presses F11 on some other page, and
    stealing that into a maximised chart is not what they asked for."""
    block = APP.split("'fullscreenchange', 'webkitfullscreenchange'", 1)[1][:600]
    assert "if (wsNativeFullscreen() || !wsIsMaximised()) return;" in block
    assert "classList.add(WS_MAX_CLASS)" not in block


def test_leaving_the_chart_leaves_full_screen():
    """A stranded class cannot break another page -- the CSS is scoped to the
    chart view -- but it would leave the browser in native fullscreen with the
    rail drawn inside it, and a Full screen button on a page that is not the
    chart."""
    fn = function("switchView")
    assert "if (view !== 'chart' && wsIsMaximised()) wsSetMaximised(false);" in fn


def test_escape_takes_the_drawing_before_it_takes_the_chart():
    """Pressing Escape to abandon a half-drawn trendline should not also throw
    the reader out of the chart they were drawing it on."""
    fn = function("wsDrawKeys")
    esc = fn[fn.index("evt.key === 'Escape'"):]
    assert "const busy = wsPending || wsSelected || wsTool !== 'cursor';" in esc
    # The drawing branch returns, so the full-screen branch is only reached
    # when there was nothing to cancel.
    assert esc.index("wsRenderDrawings(); wsSyncDrawChrome();\n      return;") \
        < esc.index("wsIsMaximised()")


def test_the_way_out_stays_on_screen():
    """In native fullscreen there is no browser chrome and no rail, so a
    toolbar that scrolled this button off the end would be a trap."""
    decls = rule('body.ws-max[data-view="chart"] [data-ws-max]')
    assert "position: sticky" in decls
    assert "margin-left: auto" in decls


# ------------------------------------------------- what full screen hides


def test_the_chrome_that_goes_is_app_chrome():
    """The rail, the top bar and the legal footer belong to the terminal, not
    to the chart. The Dossier section strip goes with them: those seven names
    navigate to other pages."""
    block = CSS[CSS.index('body.ws-max[data-view="chart"] .rail'):]
    block = block[:block.index("}") + 1]
    for part in (".rail", ".topbar", ".legal", ".sec-head"):
        assert part in block, part
    assert "display: none" in block


def test_the_rules_are_scoped_to_the_chart_as_well_as_the_class():
    """A class left behind by a reload or a half-finished transition must not
    be able to take the rail off some other page."""
    for line in CSS.splitlines():
        if "ws-max" in line and line.strip().startswith("body"):
            assert '[data-view="chart"]' in line, line


def test_full_screen_sets_no_height_of_its_own():
    """`.view-workspace.active` already sizes itself as the viewport minus
    --chrome-h, and wsSyncChromeHeight measures that chrome rather than
    assuming it -- so with the chrome gone the existing calc resolves to the
    whole viewport. A second answer here would drift from the first."""
    start = CSS.index('body.ws-max[data-view="chart"] .rail')
    block = CSS[start:].split("[data-ws-max]")[0]
    # Comments stripped first. The block explains in prose why it sets no
    # height, and the first version of this test matched its own explanation.
    block = re.sub(r"/\*.*?\*/", "", block, flags=re.S)
    assert "height:" not in block, \
        "the workspace already knows its own height"


def test_the_block_sits_after_the_rules_it_overrides():
    """`main`'s padding and the workspace's height are declared earlier at
    equal specificity, and equal specificity is decided by source order. Placed
    with the layout rules this left the padding in and the workspace short --
    the same trap the phone command-centre block at the foot of this file
    records."""
    assert CSS.index('body.ws-max[data-view="chart"] main') > CSS.index("\nmain {")
    assert CSS.index('body.ws-max[data-view="chart"] .rail') > CSS.index(".view-workspace.active {")


# ------------------------------------------------- the chart follows


def test_entering_full_screen_redraws_rather_than_waiting_to_be_noticed():
    """wsWatchPlot compares the viewBox's WIDTH and is deliberately width-only,
    because a height check can disagree with itself and redraw forever. Full
    screen is mostly a change of HEIGHT -- 570px to 763px, measured -- so it has
    to ask for the redraw itself."""
    fn = function("wsAfterMaximise")
    assert "wsSyncChromeHeight()" in fn, "the chrome height decides the workspace's"
    assert "wsRedrawChart()" in fn
    # Two frames: the class lands, the browser reflows, and only then is there
    # a real height to measure.
    assert fn.count("requestAnimationFrame") == 2
    assert "wsAfterMaximise()" in function("wsSetMaximised")


# ------------------------------------------------- the legend's 44px


def test_the_legend_follows_the_header_instead_of_a_fixed_offset():
    """`.ws-legend` floats over the plot and its offset was the literal 44px --
    the height of a header that fits on one line. The header is flex-wrap:
    wrap and carries the symbol, the OHLC readout, the session state and
    Explain chart, so between about 860 and 1000px of workspace it takes two
    rows and grows to 93px. The legend stayed at 44 and was drawn through the
    second row: measured as a 49px overlap at a 1180px window, with no full
    screen involved."""
    decls = rule(".ws-legend {")
    assert "top: var(--ws-head-h, 44px)" in decls, decls
    assert "top: 44px" not in decls, "the magic number is back"


def test_the_header_height_is_measured_and_published():
    """Published as a property rather than fixed with a second number, for the
    reason --topbar-h and --chrome-h are: the CSS keeps the layout and this
    supplies the measurement."""
    fn = function("wsWatchHead")
    assert "--ws-head-h" in fn
    assert "querySelector('.ws-head')" in fn
    assert "ResizeObserver" in fn
    # The guard this file learned to write the hard way.
    assert "wsHeadObserved === head" in fn
    # Not laid out yet is not a height of zero.
    assert "if (!h) return;" in fn
    assert "\n    wsWatchHead();" in APP, "the observer is never started"
