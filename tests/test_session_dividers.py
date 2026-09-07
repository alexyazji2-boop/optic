"""Period dividers on the charts.

Source-contract tests, the same pattern as tests/test_ui_refactor.py — there is
no JS runner here, and the granularity logic was verified against synthetic
label arrays in a real browser. What is asserted is the set of properties that
stop the feature becoming what it was: 42 dashed verticals across a 126-bar
chart, drawn in the same colour as the axis line.
"""

import re

CHARTS = open("static/charts.js", encoding="utf-8").read()
CSS = open("static/styles.css", encoding="utf-8").read()
NO_COMMENTS = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)


def _fn(name):
    start = CHARTS.index("function %s(" % name)
    return CHARTS[start:CHARTS.index("\n}", start)]


def test_the_granularity_is_read_from_the_bars_not_passed_in():
    """The old version always divided on the calendar day, which is right
    intraday and absurd on a daily chart where every bar is a new day."""
    fn = _fn("periodDividers")
    assert "gaps.sort" in fn, "the bar spacing has to be measured"
    for grain in ("'day'", "'month'", "'quarter'", "'year'"):
        assert grain in fn, grain


def test_every_granularity_branch_is_reachable():
    """Asserting the grain names exist is not enough: replacing a branch's
    condition with `false` leaves the string in the source and the branch dead.
    A mutation doing exactly that passed the first version of these tests.

    The thresholds are the reachability, so they are what is checked — and in
    ascending order, because two branches in the wrong order means the first
    swallows the second."""
    fn = _fn("periodDividers")
    cuts = [float(m) for m in re.findall(r"step < ([\d.]+)", fn)]
    assert cuts == sorted(cuts), cuts
    assert cuts == [0.9, 5, 45], cuts


def test_the_median_gap_is_used_not_the_mean():
    """Weekends and holidays leave holes. A mean over a daily series lands
    between one and three days and would pick the wrong granularity."""
    fn = _fn("periodDividers")
    assert "gaps[Math.floor(gaps.length / 2)]" in fn


def test_a_boundary_is_a_key_change_at_every_granularity():
    """One test for all four grains. A per-grain comparison is four chances to
    get an off-by-one wrong."""
    fn = _fn("periodDividers")
    # Every returned spec carries a key, and the grains are what matter rather
    # than the count: 'year' legitimately appears twice — once for weekly bars
    # spanning more than three years, once as the fallback for anything coarser.
    grains = re.findall(r"grain: '(\w+)'", fn)
    assert set(grains) == {"day", "month", "quarter", "year"}, grains
    assert len(re.findall(r"key: \(d\)", fn)) == len(grains)


def test_january_carries_the_year():
    """On a two-year daily chart every divider says a month name, and without
    this there is nothing marking where one year ends."""
    fn = _fn("periodDividers")
    assert "getUTCMonth() === 0" in fn


def test_the_marks_are_counted_before_anything_is_drawn():
    """The old loop decided per line and capped mid-way, so it painted a fence
    and then stopped. 126 daily bars produced 42 verticals."""
    block = CHARTS[CHARTS.index("if (sessions && n > 1) {"):]
    block = block[:block.index("/* Sloped segments.")]
    assert "const marks = [];" in block
    assert "marks.push(" in block
    # The guard must sit between collecting and drawing.
    guard = block.index("marks.length <=")
    assert guard < block.index("marks.forEach("), "the cap must precede the draw"


def test_it_stands_down_rather_than_capping():
    """If the chosen granularity still yields a line every few bars the feature
    is adding noise, not orientation."""
    block = CHARTS[CHARTS.index("if (sessions && n > 1) {"):]
    block = block[:block.index("/* Sloped segments.")]
    assert "Math.max(2, Math.floor(n / 4))" in block
    assert "drawn > n / 3" not in CHARTS, "the old capping guard must be gone"


def test_dividers_are_not_drawn_in_the_axis_colour():
    """C.baseline is the axis line. A time boundary painted in it is
    indistinguishable from chart furniture, which is what "make it distinct"
    was about."""
    block = CHARTS[CHARTS.index("if (sessions && n > 1) {"):]
    block = block[:block.index("/* Sloped segments.")]
    assert "stroke: C.refSession" in block
    assert "C.baseline" not in block


def test_the_divider_colour_is_a_theme_token_in_both_themes():
    """A hardcoded hex would not follow a theme switch, and the light theme
    needs a darker cyan than the dark one."""
    assert "refSession: '--ref-session'" in CHARTS
    hits = re.findall(r"--ref-session:\s*(#[0-9a-fA-F]{6})", NO_COMMENTS)
    assert len(hits) == 2, hits
    assert hits[0] != hits[1], "both themes cannot use the same cyan"


def test_each_divider_is_labelled():
    """A line with no label says a boundary exists but not which one. The label
    is the difference between a divider and a stray vertical."""
    block = CHARTS[CHARTS.index("if (sessions && n > 1) {"):]
    block = block[:block.index("/* Sloped segments.")]
    assert "mk.label" in block
    assert "s('text'" in block


def test_the_dash_pattern_is_its_own():
    """Three level families, three patterns: fine dots for ratios, medium dashes
    for structure, and this. Sharing one makes them one family visually."""
    assert "'stroke-dasharray': '2 6'" in CHARTS
    # The other two patterns must still exist and differ.
    assert "'6 4'" in CHARTS


def test_the_month_names_are_defined_once():
    assert CHARTS.count("const MONTHS = [") == 1
