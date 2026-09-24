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


def test_the_home_hero_is_always_on_the_page():
    """This was gated on `homeIsFirstRun()` and is not any more, on the
    reader's call.

    The audit premise was that the wordmark, the 592px search and the ticker
    pills are onboarding: they earn a screen where nothing is loaded, and after
    that the market is what the page is for. The premise was wrong about how
    the page is used. The top bar's 200px box is a different gesture from
    landing on Home and typing a name into the thing in front of you, and
    removing the second one took the page's primary action away from everybody
    who had ever loaded a ticker -- which, after one visit, is everybody.

    The same call was made once before for the phone, where these three were
    hidden as duplicates and came back; see
    tests/test_command_bar.py::test_the_phone_hides_only_what_is_still_a_duplicate.

    Kept from the audit: the lede moved into the tour, and the market sits
    directly under the hero rather than below three lines of product pitch."""
    home = _fn("renderHome")
    assert "homeIsFirstRun" not in APP, \
        "the gate is gone; the predicate should not survive it"
    for part in ('class="home-brand"', 'id="home-input"', 'class="home-quick"'):
        assert part in home, part
    # Unconditional: not wrapped in any ternary that could hide it again.
    for part in ('class="home-brand"', 'id="home-input"'):
        before = home[:home.index(part)]
        assert before.count("? `") == before.count("` : ''}"), \
            part + " sits inside an unclosed conditional"


def test_the_hero_still_comes_before_the_market():
    """Order is the part of the audit that survived. The hero is the page's
    action and the market is what it reports; the tour with the product pitch
    in it stays below both."""
    home = _fn("renderHome")
    assert home.index('class="home-brand"') < home.index('id="hm-market"')
    assert home.index('id="home-input"') < home.index('id="hm-market"')
    assert home.index('id="hm-market"') < home.index('id="home-tour"')


# ------------------------------------------------- one Dossier navigation


def test_dossier_opens_its_pages_from_the_rail():
    """This asserted `flat: true` and the flattening has been reversed, on the
    reader's call: "where is the dossier dropdown?"

    The audit finding was real -- these seven names are in the rail menu and in
    the section bar inside every one of those pages, the same seven words twice
    -- but the fix traded the wrong thing away. From the rail, the menu is the
    only way to open Earnings or Financials directly. Flattened, the rail opens
    whichever page you were last on and you move again inside it: two steps for
    what the menu did in one, on every navigation.

    The duplication costs width on a rail that has room. The flattening cost a
    click every time."""
    groups = APP.split("const NAV_GROUPS = [", 1)[1]
    groups = groups[:groups.index("\n];")]
    line = [ln for ln in groups.splitlines() if "id: 'security'" in ln]
    assert line, "the Dossier group is gone"
    assert "flat: true" not in line[0], \
        "flat renders it as a plain button with no menu"
    # And the mechanism the other groups rely on is untouched.
    fn = _fn("paintNav")
    assert "const single = pages.length < 2 || group.flat;" in fn


def test_a_group_with_one_page_still_renders_without_a_menu():
    """`flat` is gone from Dossier, not from paintNav: a caret on a group with
    a single destination is a menu that opens to one item."""
    fn = _fn("paintNav")
    assert "pages.length < 2" in fn, "a one-page group must not grow a caret"


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


def test_the_dossier_menu_lists_its_pages_and_they_are_clickable():
    """Restoring the menu is only half of it. The click handler is scoped to
    `nav.tabs [data-view]`, and the last time these pages moved into dropdowns
    that scope did not reach them -- the comment on that handler records it:
    the menu rendered, opened, and was inert.

    So this asserts the two halves meet: the menu buttons carry `data-view`,
    and the element they sit inside still matches the selector the handler
    uses. Driven in a browser to be sure -- hover Dossier, click Earnings,
    land on earnings in one click."""
    fn = _fn("paintNav")
    menu = fn[fn.index('<div class="nav-menu"'):]
    assert 'data-view="${p.view}"' in menu, "menu pages need the attribute the handler reads"
    # The handler's scope, and the element the rail actually renders.
    assert "evt.target.closest('nav.tabs [data-view]')" in APP
    # The element itself is in index.html, and it has to keep both classes:
    # `tabs-group` is what paintNav looks the container up by, and `tabs` is
    # what the click handler's selector matches through.
    html = open("static/index.html", encoding="utf-8").read()
    assert 'class="tabs tabs-group"' in html, \
        "the rail's nav must keep both classes or the handler stops seeing the menu"


def test_the_menu_marks_the_page_you_are_on():
    """Seven identical rows with no current-page marker is a list, not a
    navigation -- and it was the argument for dropping the label from the
    parent button, so it has to actually be there."""
    fn = _fn("paintNav")
    menu = fn[fn.index('<div class="nav-menu"'):]
    assert "p.view === view ? ' current' : ''" in menu
