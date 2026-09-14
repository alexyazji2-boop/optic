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
    rule = CSS[CSS.index(".ws-body {"):]
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
