"""The Roth planner was a second product inside Optic Portfolio.

It rendered into `#roth-host`, a div in the middle of `renderTracker`. With a
section index on that view the shape of it is plain: fifteen sections, of which
seven -- model allocation, contribution projection, where to put this year's
contribution, the individual stock sleeve, what the Roth wrapper changes, the
fund universe and correlation -- are a retirement planner sitting inside a
simulated options record. No heading between them, and no name for it anywhere
in the navigation.

Its own disclaimer never rendered either. `LEGAL.areas.roth` says "Not
retirement or tax advice"; the render pass is what inserts those, and it was
keyed to `roth`, which was not a view. So a reader planning a Roth IRA read the
banner about hypothetical paper options trades instead.

Measured after the split: Optic Portfolio went from fifteen sections and
2,719px to eight and 2,018px, and the planner became a 7-section page with its
own index and its own notice.
"""

from __future__ import annotations

import re

APP = open("static/app.js", encoding="utf-8").read()
CSS = open("static/styles.css", encoding="utf-8").read()
HTML = open("static/index.html", encoding="utf-8").read()


# --------------------------------------------------------- it is a view


def test_the_planner_has_a_page_of_its_own():
    assert 'id="view-roth"' in HTML
    section = HTML.split('id="view-roth"', 1)[1].split("</section>", 1)[0]
    assert 'id="roth-host"' in section, "and the host it renders into lives there"


def test_every_view_in_the_map_is_a_section_in_the_document():
    """Both directions, and this is the check that would have caught it.

    `VIEW_NAMES.roth`, `PANELS_OPEN_BY_DEFAULT.roth`, the `loadView` allow-list
    and the render-pass wrapper all named `roth` while `views.roth` was
    undefined -- so `chromeView('roth')` returned on its first line, every
    time, and four pieces of configuration described a page that did not
    exist."""
    body = APP.split("const views = {", 1)[1]
    body = body[:body.index("\n};")]
    mapped = dict(re.findall(r"(\w+):\s*\$\('#(view-[\w-]+)'\)", body))
    in_html = set(re.findall(r'id="(view-[\w-]+)"', HTML))
    assert set(mapped.values()) == in_html, (
        "mapped with no section: {}; section with no mapping: {}".format(
            sorted(set(mapped.values()) - in_html),
            sorted(in_html - set(mapped.values()))))


def test_it_is_out_of_the_ledger():
    fn = APP.split("function renderTracker(", 1)[1].split("\nfunction ", 1)[0]
    assert 'id="roth-host"' not in fn, \
        "a retirement planner inside a simulated options record"


def test_the_ledger_no_longer_fetches_it():
    """Two calls, one on each path through `loadTracker`. Left behind they
    would fetch ten years of fund history every time anyone opened the
    positions page, for a panel that is no longer on it."""
    fn = APP.split("async function loadTracker(", 1)[1].split("\n}\n", 1)[0]
    assert "loadRoth" not in fn


def test_it_loads_when_you_go_to_it():
    assert "if (view === 'roth') return loadRoth(force);" in APP


# ------------------------------------------------------- and it has a name


def test_it_is_reachable_from_the_strip():
    """The Watchlist lesson: a view in the palette and nowhere else is a view
    you have to already know about."""
    body = APP.split("const NAV_GROUPS = [", 1)[1]
    body = body[:body.index("\n];")]
    line = [ln for ln in body.splitlines() if "'portfolio'" in ln]
    assert line and "'tracker'" in line[0] and "'roth'" in line[0]


def test_it_is_named_everywhere_a_view_is_named():
    for table in ("SUB_LABELS", "SUB_TITLES"):
        body = APP.split("const {} = {{".format(table), 1)[1]
        assert re.search(r"(?:^|[{,]\s*)roth:", body[:body.index("\n};")], re.M), table
    places = APP.split("const PALETTE_PLACES = [", 1)[1]
    assert "view: 'roth'" in places[:places.index("\n];")]


def test_its_own_notice_can_now_reach_the_page():
    """The sentence existed the whole time. `chromeView` inserts it, and
    `chromeView` needs a host."""
    legal = APP.split("areas: {", 1)[1]
    legal = legal[:legal.index("\n  },")]
    assert re.search(r"(?:^|[{,]\s*)roth:", legal, re.M), "the sentence"
    assert "not retirement or tax advice" in legal.lower()
    body = APP.split("const views = {", 1)[1]
    assert "roth: $('#view-roth')" in body[:body.index("\n};")], "the host"


# ------------------------------- what the extra caret cost, and the fix


def test_a_menus_side_is_measured_rather_than_deduced_from_its_position():
    """This was `nav.tabs-group > .nav-item:last-child`, written when the
    rightmost group was the first one to have a menu at all.

    Position in the list is not the question. The strip wraps at every width
    from 560 to 1410, so the last group can be the FIRST item on the second
    row. Measured at 900px the moment the Positions group gained a second view
    and a caret with it -- 14px, enough to tip the row -- Watchlist moved to
    x=18 and its right-anchored menu ran -79 to 111, ninety-eight pixels off
    the LEFT edge. Swept after the fix at 375, 560, 640, 771, 900, 1024, 1410,
    1411 and 1512: nothing leaves the window on either side."""
    assert ":last-child .nav-menu" not in CSS
    assert "nav.tabs-group > .nav-item.menu-right .nav-menu" in CSS
    rule = CSS.split("nav.tabs-group > .nav-item.menu-right .nav-menu", 1)[1]
    assert "right: 0" in rule[:rule.index("}")]

    fn = APP.split("function navMenuSides() {", 1)[1].split("\n}\n", 1)[0]
    assert "getBoundingClientRect()" in fn, "measured"
    assert "classList.toggle('menu-right'" in fn


def test_it_flips_only_when_the_other_side_actually_has_room():
    """A menu too wide for either side keeps `left: 0` and leans on the
    max-width beside it -- overflowing right is the recoverable one, because
    the page's own gutter is there and the left edge of a window is not."""
    fn = APP.split("function navMenuSides() {", 1)[1].split("\n}\n", 1)[0]
    assert "spillsRight && fitsLeftwards" in fn


def test_the_sides_are_remeasured_when_the_strip_reflows():
    """A resize reflows the strip without repainting it, so nothing else would
    notice the row the last group moved to."""
    assert "setTimeout(navMenuSides, 120)" in APP, "and debounced, like the chart's"
    assert "navMenuSides();\n}" in APP, "called at the end of paintNav"
