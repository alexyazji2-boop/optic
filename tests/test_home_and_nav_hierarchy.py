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


# ------------------------------------------------- the number comes first


def test_the_price_outranks_the_symbol_in_the_security_header():
    """Measured on AAPL at 1440x950 before this: symbol 27.6px/700, price
    14.95px/600, change 14.95px/400. The price was the same size as the
    exchange and the sector beside it, the change was the lightest thing in
    the row, and the loudest was the four letters the reader had just typed
    into the box above.

    The symbol is identity and they already know it. The price is what they
    opened the page for."""
    def size_of(cls):
        rule = CSS.split("\n.%s {" % cls, 1)[1]
        rule = rule[:rule.index("}")]
        return re.search(r"font-size: var\((--t-[a-z0-9]+)\)", rule).group(1), rule

    # The scale, largest first, as the ramp declares it.
    ramp = ["--t-micro", "--t-caption", "--t-small", "--t-body", "--t-base",
            "--t-lead", "--t-heading", "--t-title", "--t-d3", "--t-d2", "--t-d1"]
    px, px_rule = size_of("sec-px")
    sym, _ = size_of("sec-sym")
    chg, chg_rule = size_of("sec-chg")
    assert ramp.index(px) > ramp.index(sym), \
        "the price ({}) must outrank the symbol ({})".format(px, sym)
    assert ramp.index(chg) >= ramp.index("--t-base"), \
        "the change was body-sized and lighter than everything beside it"

    # Both are figures a reader scans down a column of.
    assert "tabular-nums" in px_rule and "tabular-nums" in chg_rule
    # And the change keeps a weight, or the direction is the quietest thing
    # in the row again.
    assert "font-weight: 600" in chg_rule


# ------------------------------------------------- states that offer a way out


def test_a_failed_panel_offers_a_retry_rather_than_just_a_sentence():
    """The origin-down branch has always explained itself, polled and offered
    a button. The other branch -- every per-endpoint failure, a throttled feed,
    a symbol the provider has no data for -- said "Could not load" and stopped,
    leaving a reader with a dead panel and one option: reload the whole page
    and lose the rest of the screen with it.

    Driven in a browser: the error renders with the button, the click refetches
    and the panel comes back with real content."""
    fn = _fn("errorHTML")
    generic = fn.split("if (!down) {", 1)[1].split("\n  }", 1)[0]
    assert "data-view-retry" in generic
    # And the control has a handler, which is the half that makes it real.
    assert "evt.target.closest('[data-view-retry]')" in APP
    handler = APP.split("evt.target.closest('[data-view-retry]')", 1)[1][:260]
    assert "switchView(STATE.view, true)" in handler, \
        "without force it repaints the cached failure it was clicked to clear"
