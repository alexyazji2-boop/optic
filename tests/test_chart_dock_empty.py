"""The chart takes the dock's width when the dock holds nothing.

Reported from the Charting tab: a 260px column saying "No widgets open. Pick
one from the rail." That sentence is only readable from inside the space it is
taking, and the rail it points at is immediately beside it with every widget's
name on it. So the panel was describing a state the reader could already see
while charging a quarter of the chart for it.

Measured at a 1500px viewport with AAPL loaded: chart 1092px with widgets open,
1352px with none, and the SVG redrawn to 1352 rather than left at 1092.
"""

import re

RAW = open("static/app.js", encoding="utf-8").read()
CSS = open("static/styles.css", encoding="utf-8").read()


def strip_comments(js):
    """Drop `/* */` and `//` before asserting on the code.

    The first version of the next test checked that "No widgets open" was gone
    from the file and failed on the comment I had just written explaining why it
    went. The rationale for a removal names the thing removed, so a contract
    that reads the raw file can never tell the two apart."""
    js = re.sub(r"/\*.*?\*/", " ", js, flags=re.S)
    return re.sub(r"(?<!:)//[^\n]*", " ", js)


APP_JS = strip_comments(RAW)

# And the stylesheet, for the same reason: the comment explaining why
# `grid-template-rows` went names `grid-template-rows`, so a contract reading
# the raw file cannot tell the removal from its own rationale.
CSS_NC = re.sub(r"/\*.*?\*/", " ", CSS, flags=re.S)


def body_of(name):
    start = APP_JS.index("function %s(" % name)
    return APP_JS[start:].split("\nfunction ", 1)[0]


def test_an_empty_dock_renders_nothing():
    """Not a panel, not a wrapper, not a space. `.ws-dock:empty` can only fire
    on an element with no children and no text."""
    fn = body_of("wsDock")
    assert "if (!panels) return '';" in fn
    assert "No widgets open" not in APP_JS


def test_the_empty_dock_is_collapsed_in_css():
    assert ".ws-dock:empty { display: none; }" in CSS


def test_the_collapse_is_driven_by_the_content_not_a_class():
    """One thing decides this: whether wsDock() produced any panels. A class
    would be a second record of the same fact, and the two can disagree."""
    assert not re.search(r"\.ws-dock\.(is-)?empty", CSS)
    assert "classList.add('is-empty')" not in body_of("wsToggleWidget")


def test_opening_or_closing_the_last_widget_redraws_the_chart():
    """The chart is drawn to a measured pixel size rather than laid out by CSS,
    so a 260px change in its column leaves the old geometry in place until
    something else redraws: candles in the wrong position, or a gap."""
    fn = body_of("wsToggleWidget")
    assert "wsRedrawChart()" in fn


def test_the_redraw_only_fires_on_the_transition():
    """Every other toggle changes what is in the dock, not how wide it is, and
    redrawing the chart on each of those is work nobody asked for."""
    fn = body_of("wsToggleWidget")
    assert "const had = dock ? !!dock.innerHTML.trim() : false;" in fn
    assert re.search(r"if \(dock && had !== !!dock\.innerHTML\.trim\(\)\) wsRedrawChart\(\)", fn)


def test_the_chart_column_is_the_one_that_grows():
    """The grid is rail / chart / dock / widget rail. Only the chart is `1fr`,
    so a collapsed dock hands its width to the chart rather than to the rails."""
    # Anchored to a top-level rule with the leading newline. A bare
    # ".ws-body {" also matches inside a descendant selector, and one arrived:
    # `.view-workspace.active > .ws-body { flex: 1 1 auto; }` sits ~200 lines
    # earlier, so the slice started there and found no grid-template-columns at
    # all. Same fault as the tier-block and character-window slices fixed
    # earlier in this session.
    rule = CSS[CSS.index("\n.ws-body {"):]
    rule = rule[:rule.index("}")]
    cols = re.search(r"grid-template-columns: ([^;]+);", rule).group(1)
    assert cols.count("1fr") == 1, cols
    assert cols.strip().startswith("auto 1fr"), cols


def test_the_rail_still_lists_every_widget_when_the_dock_is_empty():
    """The rail is what makes an empty dock legible instead of a dead end: it is
    rendered from WS_WIDGETS and not from what happens to be open."""
    fn = body_of("wsWidgetRail")
    assert "WS_WIDGETS" in fn
    assert "wsDockOpen.includes(w.id)" in fn


# ------------------------------------------------ the workspace's own layout


def test_the_workspace_is_a_flex_column_not_a_fixed_row_grid():
    """It was `grid-template-rows: auto 1fr`, written when the workspace had two
    children: the toolbar and the body. The Dossier section strip was added
    later, making three, so `1fr` landed on the TOOLBAR and the body fell into
    an implicit auto row that took its content height.

    Measured with a symbol loaded and Pulse open: rows resolved to
    48.39px / 10.19px / 595.42px, so the toolbar was 10px tall against 27px of
    content and its labels were sliced through the middle.

    A third row would not fix it: securityHeader returns '' with no symbol
    charted, so the child count is 2 or 3 depending on state and a row sized by
    POSITION cannot follow that. Flex attaches the flexing to the element, which
    is the correction `.ws-canvas` needed for the same reason.
    """
    rule = CSS_NC[CSS_NC.index(".view-workspace.active {"):]
    rule = rule[:rule.index("}")]
    assert "flex-direction: column" in rule
    assert "grid-template-rows" not in rule
    assert ".view-workspace.active > .ws-body { flex: 1 1 auto; min-height: 0; }" in CSS_NC


def test_the_dock_has_one_float_rule_and_it_excludes_pulse():
    """There were two near-identical float rules. The scoped one's own comment
    records that floating the dock with Pulse open "reintroduced exactly the
    fault being fixed", and an unscoped copy kept doing it: measured with Pulse
    at 620px on a 1142px window, the dock rendered at 300px on top of a 382px
    chart and overlapped the canvas by 300px.

    Three grid tracks, four visible children, so the dock auto-placed straight
    onto the canvas.
    """
    assert "body.chat-open .ws-body.dock-open .ws-dock" not in CSS_NC, \
        "floating the dock with Pulse open draws it over the chart"
    assert CSS_NC.count("body:not(.chat-open) .ws-body.narrow.dock-open .ws-dock") == 2, \
        "the float rule and its below-900px adjustment, both scoped"


def test_the_below_900_adjustment_comes_after_the_rule_it_adjusts():
    """Identical selectors, so source order is the only thing deciding. Placed
    above, its `right: 0` lost to the base rule's `right: 62px` and the overlay
    cleared a rail that was no longer on that edge."""
    base = CSS_NC.index("body:not(.chat-open) .ws-body.narrow.dock-open .ws-dock {")
    mq = CSS_NC.index("@media (max-width: 900px) {\n  body:not(.chat-open) .ws-body.narrow.dock-open .ws-dock {")
    assert mq > base


def test_a_widget_button_that_cannot_act_says_so():
    """With Pulse open the dock is hidden and does not float, so a press would
    flip the button's state and show nothing. That is the dead control this
    codebase keeps finding, and it is the fault the float rule was written to
    avoid: it avoided it by covering 78% of the chart instead.

    Disabled with the reason in the title is the third option neither took.
    Not hidden: the rail is how a reader learns these panels exist.
    """
    assert "function wsDockReachable() {" in RAW
    fn = body_of("wsWidgetRail")
    assert "const reachable = wsDockReachable();" in fn
    assert "reachable ? '' : 'disabled'" in fn
    assert "Close Pulse to open this panel" in fn
    # No em dashes in reader-facing copy.
    assert "—" not in fn.split("Close Pulse")[1][:120]


def test_the_rail_is_rebuilt_when_pulse_opens_or_closes():
    """Its disabled state depends on `body.chat-open`, so without a rebuild it
    reports whatever the page was doing when it last rendered. Only the rail:
    wsOnChatToggle deliberately leaves the chart alone, and says why."""
    fn = body_of("wsOnChatToggle")
    assert "querySelector('.ws-wrail')" in fn
    assert "wsWidgetRail()" in fn
    assert "wsRedrawChart" not in fn, "rebuilding the chart here blanks it; see the comment"
