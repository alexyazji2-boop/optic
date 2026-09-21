"""Read is the longest page in the terminal and was the only one with no way
around it.

Measured in a browser at 1280x900: 13,361px, fourteen and a half screens, 21
headings, and no section index, no expand/collapse, no panel chooser. Every
other long view has all three. The cause was one omission -- `renderBrief` was
never added to the render-pass wrapper -- and the evidence that it was an
omission rather than a decision is that `PANELS_OPEN_BY_DEFAULT`,
`PANELS_ADVANCED`, `PANELS_DENSE` and `PANELS_SIMPLE_HIDES` all already carry a
`brief` key. Four pieces of configuration for a view the pass never reached.

Wiring it in surfaced two further things, both of which are also tested here:
the index has to survive sections that arrive on their own requests, and the
ids it generates have to survive being generated more than once.
"""

from __future__ import annotations

import re

APP = open("static/app.js", encoding="utf-8").read()


def _list(name):
    body = APP.split("const {} = [".format(name), 1)[1]
    return body[:body.index("\n];") if "\n];" in body else body.index("];")]


def _dict_entry(table, view):
    body = APP.split("const {} = {{".format(table), 1)[1]
    body = body[:body.index("\n};")]
    m = re.search(r"^\s*{}:\s*\[(.*?)\]".format(view), body, re.S | re.M)
    assert m, "{} has no {} entry".format(table, view)
    return re.findall(r"'([^']*)'|\"([^\"]*)\"", m.group(1))


def _keys(table):
    body = APP.split("const {} = {{".format(table), 1)[1]
    body = body[:body.index("\n};")]
    return set(re.findall(r"^\s{2}([a-z]+):", body, re.M))


CHROMED = re.findall(r"'([a-z]+)'", _list("CHROMED_VIEWS"))


# ------------------------------------------------- the omission itself


def test_read_is_wired_into_the_render_pass():
    assert "brief" in CHROMED
    assert "['brief', () => renderBrief]" in APP, "and actually wrapped"
    assert "case 'brief': renderBrief = wrapped; break;" in APP, \
        "the binding the rest of the file calls through has to be replaced too"


def test_a_view_configured_for_panels_is_a_view_that_gets_them():
    """The check that would have caught this.

    `PANELS_OPEN_BY_DEFAULT` is only ever read by `makePanelsCollapsible`, which
    only ever runs from the pass. A `brief` key there and no `brief` in the pass
    is configuration that cannot execute, and nothing said so for as long as it
    was true."""
    assert _keys("PANELS_OPEN_BY_DEFAULT") == set(CHROMED), (
        "configured but not chromed: {}; chromed but not configured: {}".format(
            sorted(_keys("PANELS_OPEN_BY_DEFAULT") - set(CHROMED)),
            sorted(set(CHROMED) - _keys("PANELS_OPEN_BY_DEFAULT"))))


def test_the_two_callers_of_the_pass_run_the_same_pass():
    """Extracted from the wrapper precisely so the late-panel path cannot drift
    from the render path. Inlining either one is the way that stops being
    true."""
    assert "function chromeView(view) {" in APP
    fn = APP.split("function chromeView(view) {", 1)[1].split("\n}\n", 1)[0]
    for step in ("makePanelsCollapsible(view)", "applyUiMode(view)",
                 "addBulkControl(view)", "buildSectionIndex(view)",
                 "syncSecurityHeader()", "legalBanner(view)"):
        assert step in fn, step
    # Ordering the original wrapper documented as load-bearing, preserved.
    assert fn.index("makePanelsCollapsible") < fn.index("applyUiMode(view)")
    assert fn.index("applyUiMode(view)") < fn.index("buildSectionIndex(view)")


# --------------------------------------- sections that arrive late


def test_the_index_is_rebuilt_when_a_section_arrives_late():
    """Seven of Read's twelve sections are separate requests that `loadBrief`
    fires without awaiting, so an index built once at render time would name
    five. `watchForLatePanels` already existed for the same shape of problem
    and re-ran only `applyUiMode`."""
    assert "function watchForLateChrome() {" in APP
    fn = APP.split("function watchForLateChrome() {", 1)[1].split("\n}\n", 1)[0]
    assert "CHROMED_VIEWS.forEach" in fn, "every chromed view, not a second list"
    assert "chromeView(view)" in fn
    assert "watchForLateChrome();" in APP, "and it is actually started"


def test_it_cannot_watch_itself_work():
    """The pass inserts a nav, a bulk bar, a mode note and a body wrapper per
    panel. It is idempotent, so a re-entry would settle rather than spin -- but
    this file has already had two observers that did spin, at ~3Hz and ~7Hz,
    and both took every click on the page with them."""
    fn = APP.split("function watchForLateChrome() {", 1)[1].split("\n}\n", 1)[0]
    assert "obs.disconnect();" in fn
    body = fn[fn.index("obs.disconnect();"):]
    assert body.index("chromeView(view);") < body.index("obs.observe("), \
        "reconnecting before the pass runs is the same as never disconnecting"
    # And the note it writes itself is excluded from the predicate as well.
    assert "[data-mode-note]" in fn


def test_it_only_wakes_for_a_panel():
    """Attribute churn and text updates are most of what happens inside a view;
    a live price ticking would otherwise rebuild the index every second."""
    fn = APP.split("function watchForLateChrome() {", 1)[1].split("\n}\n", 1)[0]
    assert "if (!added) return;" in fn
    assert "requestAnimationFrame" in fn, "and a burst of them coalesces to one"


# ------------------------------------------------ ids that survive a rebuild


def test_a_sections_id_names_the_section_not_its_position():
    """`sec-${view}-${i}` is unique only if every panel is numbered in one pass.
    Once the index is rebuilt as late sections land, the ids already assigned
    are kept and newcomers are numbered by their position in the new list.

    Measured on Read before the fix: sec-brief-1 on both Overnight and Market
    regime, sec-brief-2 on both Today's priority and the Catalyst Library,
    sec-brief-3 on three panels at once. getElementById returns the first, so
    four of twelve chips scrolled to the wrong section."""
    fn = APP.split("function buildSectionIndex(view) {", 1)[1].split("\n}\n", 1)[0]
    # The assignment, not the mention -- the comment above it quotes the old
    # form and would satisfy a bare substring check on its own.
    assert "panel.id = `sec-${view}-${i}`" not in fn, "position is not identity"
    assert "panel.id = 'sec-' + panelId(view, full)" in fn, \
        "panelId is what collapse state already persists under"


def test_an_id_the_author_wrote_is_left_alone():
    """`cal-panel` and the desks' `read-desk-*` anchors are referenced by name
    from elsewhere -- `read-nav` links straight to them."""
    fn = APP.split("function buildSectionIndex(view) {", 1)[1].split("\n}\n", 1)[0]
    assert "const mine = !panel.id || panel.id.startsWith('sec-' + view + '-');" in fn
    assert "if (mine) panel.id =" in fn


# ------------------------------------------------------- the newsdesks


def test_the_newsdesks_opt_out_of_being_sections():
    """Eight cards in a grid, each with a heading, is one section wearing
    `.panel` eight times. They already have `read-nav` immediately above them,
    so indexing them again would spend eight of twenty chips on the one block
    that does not need them -- and a chevron on each of eight news cards
    collapses a newspaper."""
    assert '<section class="panel read-desk" data-fixed="1"' in APP
    fn = APP.split("function makePanelsCollapsible(view) {", 1)[1].split("\n}\n", 1)[0]
    assert "if (panel.dataset.fixed === '1') return;" in fn


def test_the_desks_keep_the_navigation_they_already_had():
    """Removing `read-nav` was the alternative to opting them out, and it is
    the wrong half to remove: an in-place list of eight is what makes the grid
    navigable once you reach it."""
    assert 'class="read-nav"' in APP
    assert '#read-desk-${esc(k.id)}' in APP and 'id="read-desk-${esc(k.id)}"' in APP


# --------------------------------------------- what opens, and what does not


def test_read_opens_almost_everything():
    """The other chromed views are analysis -- a verdict on top, evidence
    below, where closed means "you have the answer already". Read has no
    verdict. Twelve clicks to read the news is a worse page than the one that
    only scrolled."""
    keys = [a or b for a, b in _dict_entry("PANELS_OPEN_BY_DEFAULT", "brief")]
    assert len(keys) >= 9, "a newspaper does not open collapsed"
    for shut in ("catalyst library", "where this comes from", "market catalyst"):
        assert not any(shut in k for k in keys), \
            "{} is reference material, not news".format(shut)


def test_every_default_open_name_matches_a_heading_that_exists():
    """These matched nothing at all until the tab was wired in, and two of the
    four were wrong with it: the heading is "Weekly market update", not "weekly
    market analysis", and "optic's read" named the hero, whose h2 is nested and
    so was never collapsible in the first place."""
    headings = [h.lower() for h in re.findall(r"<h2[^>]*>([^<]{0,80})", APP)]
    for key in [a or b for a, b in _dict_entry("PANELS_OPEN_BY_DEFAULT", "brief")]:
        assert any(key in h for h in headings), \
            "{!r} matches no <h2> in the app".format(key)


def test_read_hides_nothing_by_mode():
    """Wiring the tab in runs `applyUiMode` on it for the first time. All three
    tables are empty for `brief`, so Simple mode hides nothing here and only a
    reader's own choice in the panel chooser can -- which is the behaviour this
    change is supposed to add, not a quiet removal of nine sections."""
    for table in ("PANELS_ADVANCED", "PANELS_DENSE", "PANELS_SIMPLE_HIDES"):
        assert not [a or b for a, b in _dict_entry(table, "brief")], \
            "{} now hides part of Read by mode".format(table)
