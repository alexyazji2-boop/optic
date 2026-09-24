"""One search box, one Dossier navigation, one session summary.

Three duplications found by auditing the running product at 1440x950, all of
the same kind: the same job offered twice on one screen, which costs space and
makes the reader choose between two identical affordances.

  the search    `#ticker-input` in the top bar at y=11, and `#home-input` on
                the page at y=696 -- the larger and lower of the two being the
                harder to reach.
  Dossier       the same seven page names in the rail's dropdown AND in the
                section bar inside every one of those pages.
  the session   150px of bar above every view, most of it a timetable, a
                colour legend and a company profile that do not change during
                a day.
"""

from __future__ import annotations

import re

APP = open("static/app.js", encoding="utf-8").read()
CSS = open("static/styles.css", encoding="utf-8").read()


def _fn(name):
    start = APP.index("function %s(" % name)
    return APP[start:APP.index("\n}", start)]


# ------------------------------------------------- one search box


def test_the_home_hero_is_onboarding_and_renders_only_for_a_new_reader():
    """The wordmark, the 592px search and the ticker pills are an onboarding
    surface. They earn their place on a screen where nothing has been loaded
    and the 200px box in the top bar is something the reader has no reason to
    have noticed. After that the market is what the page is for."""
    home = _fn("renderHome")
    assert "${homeIsFirstRun() ? `" in home
    # All three are inside the gate, and the market is not.
    gate = home.split("${homeIsFirstRun() ? `", 1)[1]
    gate = gate[:gate.index("` : ''}")]
    for part in ('class="home-brand"', 'id="home-input"', 'class="home-quick"'):
        assert part in gate, part
    assert 'id="hm-market"' not in gate, "the market is not onboarding"


def test_first_run_is_three_signals_and_any_one_ends_it():
    """A loaded ticker is the weakest of them and is still worth having: it
    covers the reader who arrives on a shared link, where nothing is stored
    yet but the page is plainly not being seen for the first time."""
    fn = _fn("homeIsFirstRun")
    assert "STATE.ticker" in fn
    assert "recentSymbols()" in fn
    assert "watchList()" in fn
    assert fn.count("return false") == 3
    assert fn.rstrip().endswith("return true;")
    # A storage failure must not wedge the page into onboarding forever.
    assert "catch" in fn


# ------------------------------------------------- one Dossier navigation


def test_dossier_opens_from_the_rail_without_repeating_its_pages():
    """The rail listed Overview, Chart, Options, Investing, Earnings,
    Financials and News, and so did the section bar inside every one of them.
    `flat` renders a group with several pages as a plain button: the rail
    opens the workspace at the page you were last on, the section bar moves
    you around inside it."""
    groups = APP.split("const NAV_GROUPS = [", 1)[1]
    groups = groups[:groups.index("\n];")]
    line = [ln for ln in groups.splitlines() if "id: 'security'" in ln]
    assert line and "flat: true" in line[0], line
    fn = _fn("paintNav")
    assert "const single = pages.length < 2 || group.flat;" in fn


def test_only_dossier_is_flattened():
    """Markets, Discover, Positions and Watchlist have no in-page section bar
    to defer to, so their menus are the only way to reach what is in them."""
    groups = APP.split("const NAV_GROUPS = [", 1)[1]
    groups = groups[:groups.index("\n];")]
    assert groups.count("flat: true") == 1


def test_the_section_bar_is_still_the_one_that_remains():
    """Flattening the rail entry only works if the other navigation exists."""
    assert "function securityHeader(" in APP
    assert "SECURITY_VIEWS" in _fn("securityHeader")


# ------------------------------------------------- one session summary


def test_the_session_bar_keeps_its_live_part_and_folds_the_rest():
    """Which session, the clock and the 24-hour strip are what the bar is
    for and stay unconditional. The timetable, the legend, the timezone note
    and the company profile fold."""
    render = _fn("renderSessionBar")
    assert render.index("ses-strip") < render.index('id="ses-detail-btn"')
    assert ".ses-detail.is-closed { display: none; }" in CSS
    # And the control that reveals them is visible at every width, which is
    # what makes folding safe -- see test_command_bar.py for the attempt that
    # hid both and had to be reverted.
    assert ".ses-detail-btn {\n  display: inline-flex;" in CSS
