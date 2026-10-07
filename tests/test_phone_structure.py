"""A phone has one of each thing.

Asked for as "It is tough to use on the phone as a first time user, make the
structure simple and understandable". Measured at 375x812 on AAPL: the top bar,
the sections strip, a status line and the market hours took 470px before the
company's name, and Home, the Dossier, Pulse and Settings were each in two
navigations at once; Home had two search boxes; and a stock's seven sections
scrolled sideways with three of them out of sight.

On a phone now: one navigation, the bottom bar (Home, Dossier, Markets,
Discover, More); one search box, beside Pulse in the top bar, and none on Home,
whose own search is its first thing; the market hours as one line; a section's
pages as chips; a stock's sections wrapping onto a second line. A desktop is as
it was.

Checked in a browser at 375x812: the company's name at 175px from 490, all seven
tabs in sight on two rows, Markets opening Read with Read, Macro and Indices as
chips, More listing Compare, Positions, Watchlist and Alerts, Settings and Sign
in, and the search box 227px wide; at 1440x900 the rail, the status line, the
Load button, the day's timeline and "Search or ask ⌘K" as before.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
CSS = (ROOT / "static/styles.css").read_text()


def _phone():
    at = CSS.index("/* ================================================================ the phone ===")
    block = CSS[at:]
    return block[block.index("@media (max-width: 559px) {"):]


def _fn(head):
    at = APP.index(head)
    return APP[at:APP.index("\n}\n", at) + 3]


def test_the_bottom_bar_is_four_places_and_more():
    tabs = APP[APP.index("const MOBILE_TABS = ["):]
    tabs = tabs[:tabs.index("\n];")]
    labels = re.findall(r"label: '([^']+)'", tabs)
    assert labels == ["Home", "Dossier", "Markets", "Discover", "More"]
    assert "{ group: 'market'" in tabs and "{ group: 'discover'" in tabs and "{ more: true" in tabs


def test_a_group_tab_lands_where_the_reader_was_and_more_lights_for_the_rest():
    click = APP[APP.index("  const view = tab.dataset.mtab;"):]
    click = click[:click.index("\n});")]
    assert "if (view === 'more') { openMoreSheet(); return; }" in click
    assert "switchView(g.views.includes(remembered) ? remembered : g.views[0]);" in click
    paint = _fn("function paintMobileTabs(view) {")
    assert "const own = { home: 'home', security: 'overview', market: 'g:market', discover: 'g:discover' };" in paint
    assert "const lit = own[group] || 'more';" in paint


def test_more_lists_every_other_page_with_what_it_is_for():
    sheet = _fn("function moreSheetHTML() {")
    assert "const named = ['home', 'security', 'market', 'discover'];" in sheet
    assert "navVisibleGroups().filter((g) => !named.includes(g.id))" in sheet
    assert "row('settings', 'Settings')" in sheet
    assert "document.querySelector('#account-slot .acct-signin')" in sheet and 'data-auth-open="signin"' in sheet
    assert "evt.target.closest('[data-more-view]')" in APP
    assert "if (evt.key === 'Escape') closeMoreSheet();" in APP


def test_a_sections_pages_are_chips_and_the_dossier_has_its_own():
    nav = _fn("function paintNav(view) {")
    assert "g && g.id !== 'security' && g.id !== 'home'" in nav
    assert "sub.hidden = pages.length < 2;" in nav
    phone = _phone()
    assert "header.topbar #subnav:not([hidden]) {\n    display: flex !important;" in phone
    # And on a desktop too, in the top bar: a section's pages were reachable
    # there only through a hover menu on the rail.
    assert "nav.tabs-sub, #subnav { display: none !important; }" not in CSS
    assert "nav.tabs-sub#subnav {" in CSS


def test_the_phone_draws_one_navigation_one_search_and_one_line_of_hours():
    phone = _phone()
    for rule in ("#rail.rail { display: none; }",
                 "#statusline.statusline { display: none; }",
                 'header.topbar #ticker-form button[type="submit"] { display: none; }',
                 'body[data-view="home"] header.topbar #ticker-form { display: none; }',
                 "header.topbar #ticker-form { order: -1; flex: 1 1 0; min-width: 0; }",
                 "header.topbar .account-slot:has(.acct-signin) { display: none; }",
                 ".sessionbar .ses-strip,\n  .sessionbar .ses-detail-btn,\n  .sessionbar .ses-detail { display: none; }",
                 ".sec-head .sec-tabs { flex-wrap: wrap; overflow: visible; row-gap: 0; }"):
        assert rule in phone, rule


def test_the_search_box_says_what_it_is_for_on_a_phone():
    assert "const PHONE_SEARCH_HINT = 'Ticker or company';" in APP
    sync = _fn("function syncSearchHint() {")
    assert "box.placeholder = phone ? PHONE_SEARCH_HINT : box.dataset.wideHint;" in sync


def test_the_update_notice_spans_the_screen_above_the_bar():
    phone = _phone()
    assert "left: var(--space-3); right: var(--space-3); transform: none;" in phone
    assert "bottom: calc(60px + env(safe-area-inset-bottom));" in phone


def test_a_selected_page_chip_has_no_blue_underline():
    """Asked for as "remove this blue line", circled under Problem Reports: the
    underline nav.tabs gives a selected tab, drawn under a chip already outlined
    in gold. Checked at phone width: Macro's ::after content read none."""
    assert 'header.topbar #subnav button[aria-selected="true"]::after { content: none; }' in _phone()
