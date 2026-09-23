"""The shell is a workspace frame, not a page.

The old shell was one full-width bar carrying the brand, the search box, eight
nav groups, the settings gear, the account slot and Pulse, over a centred
content column. Two things were wrong with it, both structural.

The navigation competed with the search box for horizontal room. Measured at
1411px -- the narrowest width where the strip may not wrap -- eight groups
ended at 1125 against a gear at 1160, and a ninth left 18px. Navigation that
cannot grow is navigation that cannot be labelled, and three separate rules
existed only to cope: a wrap band between 560 and 1410, a measured left/right
menu flip, and a horizontal scroller on phones.

And it cost vertical space on every page. Measured at 1280x900 on the charting
tab: 347px of chrome above a 309px chart.

A rail costs no height. Measured after: top bar 130px -> 66px, and the rail
collapses to 56px, which hands 156px back to the content.

Every fault below was found by reading a computed value in the browser after
the move, and each is the same kind: a rule written for a horizontal strip
that meant something else in a column.
"""

from __future__ import annotations

import re

CSS = open("static/styles.css", encoding="utf-8").read()
# Declarations only. A comment explaining why a declaration was removed quotes
# the declaration, and a bare substring check cannot tell those apart -- this
# is the third time that has caught a test in this repo.
CSS_CODE = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
HTML = open("static/index.html", encoding="utf-8").read()
APP = open("static/app.js", encoding="utf-8").read()


# ------------------------------------------------------------- the frame


def test_the_shell_is_a_grid_of_rail_and_content():
    assert '<div class="app">' in HTML
    assert '<nav class="rail" id="rail"' in HTML
    assert '<div class="app-main">' in HTML
    block = CSS.split("\n.app {", 1)[1]
    block = block[:block.index("}")]
    assert "grid-template-columns: auto minmax(0, 1fr)" in block


def test_the_navigation_moved_into_the_rail():
    """`paintNav` is untouched -- it writes into `nav.tabs-group` wherever that
    element lives, which is what made this a markup move rather than a
    rewrite."""
    # To the rail's own close, not the first </nav> in it -- the section list
    # is a <nav> too, and slicing at that one ends before the rail footer.
    rail = HTML.split('<nav class="rail"', 1)[1]
    rail = rail[:rail.index('<div class="app-main">')]
    assert 'class="tabs tabs-group"' in rail
    bar = HTML.split('<header class="topbar">', 1)[1].split("</header>", 1)[0]
    assert "tabs-group" not in bar, "the bar is a context strip now"
    # Settings lives in the rail footer. It moved to the top bar for one pass
    # on the reading that appearance and time zone are account business, and
    # that was asked to be undone: it is a destination like every other entry
    # in the rail, and the rail is where the destinations are. It carries a
    # rail-label so it collapses with them.
    assert 'id="settings-btn"' not in bar
    # To the rail-foot's own close. The buttons inside it contain no <div>, so
    # the first </div> after it is the footer's -- but slice on the toggle as
    # well, so a footer that gains a wrapper does not silently pass.
    foot = HTML.split('<div class="rail-foot">', 1)[1].split("</div>", 1)[0]
    assert 'id="settings-btn"' in foot
    assert 'id="rail-toggle"' in foot
    assert '<span class="rail-label">Settings</span>' in foot
    # And Settings comes first: Collapse is a control of the rail, so it sits
    # last, under the hairline.
    assert foot.index('id="settings-btn"') < foot.index('id="rail-toggle"')


def test_the_account_controls_are_pushed_to_the_far_end():
    """The nav strip used to sit between the search box and these and grow to
    fill the row, which is what held them against the right edge. Moving the
    nav to the rail took that spacer with it, and Sign in and Pulse ended up
    bunched against the Load button with most of the bar empty to their
    right."""
    assert ".topbar-right { margin-left: auto; }" in CSS_CODE
    bar = HTML.split('<header class="topbar">', 1)[1].split("</header>", 1)[0]
    # A class, not an id, because the push has to follow whichever control is
    # first: it was on the gear until the gear moved into the rail, and an id
    # selector went on pushing an element that had left the bar.
    # And it is on the FIRST of the group, or it pushes only itself: an auto
    # margin absorbs the free space where it is declared, so the same class on
    # Pulse would leave the account slot behind next to Load.
    assert '<div class="account-slot topbar-right" id="account-slot">' in bar
    assert bar.index('id="account-slot"') < bar.index('id="chat-toggle"')
    assert bar.count("topbar-right") == 1


def test_the_rail_nav_is_a_column_and_not_a_row():
    """`order: 3` and `flex: 1 0 100%` were on `nav.tabs-group` to place it on
    the bar's third row and claim the full width. In a column they put the
    settings footer ABOVE the sections -- measured, foot at y=87 against nav at
    y=172 -- and forced a 100% basis."""
    block = CSS.split(".rail nav.tabs-group {", 1)[1]
    block = block[:block.index("}")]
    assert "flex-direction: column" in block
    assert ".rail nav.tabs-group { order: 0; flex: 0 1 auto; }" in CSS


def test_main_does_not_ask_to_be_centred_inside_the_frame():
    """`margin: 0 auto` was a no-op in block layout once the width cap went --
    auto margins resolve to zero when the width is auto. As a flex item it
    turns OFF stretch and sizes to max-content: measured 1129px inside a
    1068px column, 61px past the viewport, which was the whole of the
    horizontal page scroll."""
    block = re.search(r"\nmain \{[^}]*was tables, charts[^}]*\}", CSS, re.S)
    assert block, "the main sizing rule moved; check this test still finds it"
    assert "margin: 0;" in block.group(0)
    assert "margin: 0 auto;" not in block.group(0)
    # The Pulse reservation still sets its own margin afterwards.
    assert "body.chat-open main { padding-right: var(--space-5); margin-right: var(--chat-w); }" in CSS


def test_the_frames_children_may_shrink():
    """A flex item defaults to `min-width: auto` and refuses to shrink below
    its content, which is how a table drags the whole column past the edge."""
    assert ".app-main > * { min-width: 0; }" in CSS


def test_the_rail_icons_have_a_size():
    """An unsized inline SVG in a flex column took its default 105px square and
    pushed everything under it down a screen."""
    assert ".rail .icon-btn svg," in CSS
    block = CSS.split(".rail .icon-btn svg,", 1)[1]
    block = block[:block.index("}")]
    assert "width: 18px" in block


# ------------------------------------------------------------ collapsing


def test_the_rail_collapses_and_remembers():
    """212px to 56px, which hands 156px to the content. A rail that forgets is
    one you re-collapse every visit, and the width was the whole point."""
    assert "body.rail-tight .rail { width: 56px; }" in CSS
    assert "const RAIL_KEY = 'optic.rail.tight';" in APP
    fn = APP.split("function applyRail(tight) {", 1)[1].split("\n}", 1)[0]
    assert "classList.toggle('rail-tight', tight)" in fn
    assert "localStorage.setItem(RAIL_KEY" in fn
    assert "aria-pressed" in fn, "a toggle has to say which way it is set"


def test_a_collapsed_rail_still_opens_its_menus_on_screen():
    """The fly-out is positioned from the rail's edge, so it has to follow the
    rail's width rather than assume the expanded one."""
    assert "body.rail-tight .rail nav.tabs-group .nav-menu { left: 56px; }" in CSS


# --------------------------------------------------------------- phones


def test_a_phone_puts_the_rail_under_the_search_not_above_it():
    """The rail is first in the DOM because on every other width it is a column
    beside the content, so a phone has to reorder it."""
    phone = [b for b in CSS.split("@media (max-width: 559px)")[1:]
             if ".rail { order: 2; }" in b[:b.index("\n}")]]
    assert phone, "the phone ordering rule is gone"
    assert ".app-main { order: 1; }" in phone[0]


def test_the_phone_menu_anchor_follows_the_rail():
    """These menus hung off the top bar when the fixed-position rule was
    written. With the nav in a rail that sits under the bar on a phone,
    anchoring to --topbar-h alone puts the panel across the strip it opens
    from -- the exact fault that rule exists to prevent, one element along."""
    assert "var(--rail-h" in CSS
    assert "setProperty('--rail-h'" in APP
    fn = APP.split("function trackRailHeight() {", 1)[1].split("\n}\n", 1)[0]
    assert "matchMedia('(max-width: 559px)')" in fn, \
        "zero on a desktop, where the menus fly out sideways instead"


def test_the_rail_does_not_clip_its_own_fly_outs():
    """Reported as "there's no dropdown", and it was one word of CSS.

    `overflow-y: auto` on the rail computes `overflow-x` to `auto` as well --
    per spec, a `visible` on one axis becomes `auto` when the other is not
    visible. The section menus open sideways, so asking for a vertical
    scrollbar clipped them at the rail's own edge: measured, the Dossier menu
    ran 206 to 396 against a rail ending at 212.

    Visible is safe because the rail's content does not grow with data -- a
    brand row, the sections and two footer buttons, about 380px against a
    100dvh column."""
    block = CSS_CODE.split("\n.rail {", 1)[1]
    block = block[:block.index("}")]
    assert "overflow: visible" in block
    assert "overflow-y: auto" not in block, \
        "this clips the horizontal axis too, and the menus open sideways"


def test_compare_is_its_own_section_again():
    """It was folded into Dossier to get the top strip from eight sections to
    six, back when the navigation was a horizontal row competing with the
    search box for width. The rail removed that constraint.

    The merge had a cost that showed up immediately: `NAV_LAST` returns you to
    the last page you used in a group, so once Compare had been opened it
    became what the Dossier button did -- a page about two to four securities
    answering to the section named for one."""
    groups = APP.split("const NAV_GROUPS = [", 1)[1]
    groups = groups[:groups.index("\n];")]
    assert "{ id: 'analyse', label: 'Compare', views: ['compare'] }" in groups
    line = [ln for ln in groups.splitlines() if "'security'" in ln]
    assert line and "'compare'" not in line[0], \
        "the Dossier group is the facets of one security"


# ------------------------------------------------------ collapsed, properly


def test_every_section_has_a_glyph():
    """Collapsed, a section is 56px of rail with no room for its name. Without
    these it was a column of blank buttons."""
    ids = re.findall(r"^\s{2}([a-z]+):\s*'", APP.split("const NAV_ICONS = {", 1)[1]
                     .split("\n};", 1)[0], re.M)
    groups = APP.split("const NAV_GROUPS = [", 1)[1]
    groups = groups[:groups.index("\n];")]
    for gid in re.findall(r"\{ id: '([a-z]+)'", groups):
        assert gid in ids, "the {} section has no icon".format(gid)


def test_the_label_is_hidden_rather_than_removed():
    """A collapsed rail has to read the same to a screen reader as an open
    one, so the name stays in the DOM and the button carries a title."""
    # BOTH render paths. A group with one view renders a plain button and a
    # group with several renders a button plus a menu; they are built by
    # separate template literals, so asserting the label exists "somewhere in
    # the file" passed a mutation that had emptied the single-view branch.
    # Sliced on structural markers, not on "}": the first brace inside either
    # branch closes ${group.id}, which is the slicing trap that let two
    # portfolio assertions survive earlier today.
    fn = APP.split("function paintNav(view) {", 1)[1].split("\nfunction ", 1)[0]
    cut, end = fn.index("aria-haspopup"), fn.index('class="nav-menu"')
    single = fn[fn.index("if (single) {"):cut]
    multi = fn[cut:end]
    for branch, name in ((single, "single-view group"), (multi, "group with a menu")):
        assert '<span class="nav-label">' in branch, name
        assert 'title="${esc(navGroupLabel(group))}"' in branch, name
        assert "navIcon(group.id)" in branch, name
    assert "body.rail-tight .rail nav.tabs-group .nav-label," in CSS


def test_collapsing_uses_display_not_a_font_size():
    """`font-size: 0` leaves the text in flow. With `overflow: visible` on the
    rail -- which the fly-out menus need -- it escaped the 56px column and
    painted over the page."""
    block = CSS_CODE.split("body.rail-tight .rail { width: 56px; }", 1)[1]
    block = block[:block.index("\n.nav-icon") if "\n.nav-icon" in block else 400]
    assert "font-size: 0" not in block
    assert "display: none" in block


def test_the_collapsed_rules_outrank_the_ones_they_override():
    """They did not. `body.rail-tight .rail .nav-top` and
    `.rail nav.tabs-group .nav-top` are both specificity (0,3,1), so source
    order decided it -- and the section styling comes later in the file, so
    the collapse rule never applied at all. Every collapsed selector carries
    the same `.rail nav.tabs-group` prefix now, which cannot tie."""
    for rule in ("body.rail-tight .rail nav.tabs-group .nav-label",
                 "body.rail-tight .rail nav.tabs-group .nav-caret",
                 "body.rail-tight .rail nav.tabs-group .nav-top"):
        assert rule in CSS, rule


def test_nothing_paints_outside_the_collapsed_column():
    """The rail keeps `overflow: visible` for its fly-outs, so the width has
    to hold on its own."""
    assert "body.rail-tight .rail nav.tabs-group .nav-top { overflow: hidden; }" in CSS


def test_the_glyph_does_not_move_when_the_label_goes():
    """A fixed icon box, so a section's mark sits on the same axis in both
    states and the label appears beside it rather than shifting it. Measured:
    one distinct icon x-position across all seven, open and collapsed."""
    block = CSS.split("\n.nav-icon {", 1)[1]
    block = block[:block.index("}")]
    assert "flex: none" in block and "width: 18px" in block


# ------------------------------------------------- the rail as a phone row


def _phone_block():
    """The `max-width: 559px` block that turns the rail into a row.

    Sliced to the closing brace of the media query, counting braces, because
    the block contains nested rules and stopping at the first `}` reads one
    declaration of it."""
    i = CSS_CODE.index("@media (max-width: 559px) {\n  .app {")
    depth, j = 1, CSS_CODE.index("{", i) + 1
    while depth:
        nxt_open = CSS_CODE.find("{", j)
        nxt_close = CSS_CODE.find("}", j)
        if nxt_open != -1 and nxt_open < nxt_close:
            depth += 1
            j = nxt_open + 1
        else:
            depth -= 1
            j = nxt_close + 1
    return CSS_CODE[i:j]


def test_on_a_phone_the_nav_scrolls_and_the_rail_does_not():
    """`.rail nav.tabs-group` carries `overflow: visible` so the fly-outs can
    open sideways out of the column, which is right at every other width.

    In a row it meant the seven group buttons ran from x=193 to x=969 out of a
    nav box measured at 112px, and the rail took the scroll instead. The
    footer is a flex sibling placed after that shrunken box, so it landed at
    x=314 -- on top of nav buttons three through seven -- and scrolled away
    with them. Measured after: rail scrollWidth 375 against clientWidth 375,
    nav scrollWidth 794 against 121, footer fixed at 323-361."""
    block = _phone_block()
    # One rule per selector in this block, so a split cannot pick the wrong
    # one. There were briefly two `.rail nav.tabs-group` rules here and this
    # assertion read the first, which is the one-line row rule and says
    # nothing about overflow.
    assert block.count(".rail nav.tabs-group {") == 1
    nav = block.split(".rail nav.tabs-group {", 1)[1]
    nav = nav[:nav.index("}")]
    assert "overflow-x: auto" in nav
    # Or the nav refuses to shrink below its content and nothing scrolls.
    assert "min-width: 0" in nav
    assert "flex: 1 1 auto" in nav
    # The multi-line form. `.rail { order: 2; }` is a separate one-liner in
    # this block on purpose -- it is about where the row sits, not how it
    # behaves -- so a bare `.rail {` split picks that one and reads nothing.
    assert block.count("\n  .rail {\n") == 1
    rail = block.split("\n  .rail {\n", 1)[1]
    assert "overflow-x: hidden" in rail[:rail.index("}")]
    assert "overflow-x: auto" not in rail[:rail.index("}")], \
        "the rail scrolling again is what put the footer over the nav buttons"


def test_the_footer_keeps_the_gear_on_screen_in_that_row():
    """Last in the row and not shrinkable. Measured at 375x812: the gear sits
    at 323-361 whatever the nav's scroll position, against a viewport of
    375."""
    block = _phone_block()
    foot = block.split(".rail-foot {", 1)[1]
    foot = foot[:foot.index("}")]
    assert "flex: none" in foot
    assert "flex-direction: row" in foot


def test_the_phone_rule_that_hides_collapse_can_actually_win():
    """`.rail-foot .icon-btn` is (0,2,0) and sets `display: flex`. A bare
    `.rail-toggle` is (0,1,0), so the rule meant to hide the toggle on phones
    lost the cascade and did nothing: computed display was `flex`.

    That mattered beyond a stray button. Tapping it set `body.rail-tight`,
    and `body.rail-tight .rail { width: 56px }` also outranks the `width:
    auto` the phone block gives the rail -- so the whole nav strip squeezed to
    56px with no way back, the toggle having squeezed itself out of reach."""
    block = _phone_block()
    assert ".rail-foot .rail-toggle { display: none; }" in block, \
        "a one-class selector here loses to .rail-foot .icon-btn"
    # And the rule it has to beat is still the reason why.
    setter = CSS_CODE.split(".rail-foot .icon-btn {", 1)[1]
    assert "display: flex" in setter[:setter.index("}")]


def test_the_wordmark_is_a_mark_only_in_that_row():
    """It took 161px of a 375px row and left the nav a 121px scroll box, which
    is about one group button visible at a time. Measured after: brand 14-56,
    nav 75-314."""
    block = _phone_block()
    assert ".rail > .brand .brand-text { display: none; }" in block


def test_collapse_is_separated_from_the_destination_above_it():
    """Settings navigates and Collapse does not, and at `--space-1` apart they
    read as one pair of related buttons. Misreading a pair costs a page.

    Drawn as a pseudo-element rather than `border-top` on the button, because
    a border there sits inside the hover background and squares off its top
    corner."""
    rule = CSS_CODE.split("\n.rail-toggle {", 1)[1]
    assert "position: relative" in rule[:rule.index("}")], \
        "the ::before below is absolutely positioned against this"
    before = CSS_CODE.split("\n.rail-toggle::before {", 1)[1]
    before = before[:before.index("}")]
    assert "border-top" in before
    assert "position: absolute" in before
