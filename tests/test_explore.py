"""Explore: the page for when you do not know what you are looking for.

Assembled from four requests, all of them endpoints that already existed: the
scanner catalogue, its groups, the sector board, and the home payload's
cross-asset instruments. Nothing here is a new feed and every row either opens
a screen that runs or a symbol that loads.

**It does not run the seventeen screens.** Seventeen requests over a
three-thousand-symbol universe is not a discovery page. Each screen shows its
own description and opens on click, which is the Scan view's job; what this page
adds is the map.
"""

from __future__ import annotations

import re

APP_JS = open("static/app.js").read()
CSS = open("static/styles.css").read()
HTML = open("static/index.html").read()


def _fn(name: str) -> str:
    start = APP_JS.index("function %s(" % name)
    nxt = APP_JS.find("\nfunction ", start + 1)
    return APP_JS[start:nxt if nxt > 0 else len(APP_JS)]


# ------------------------------------------------------------ registration


def test_the_view_is_registered_everywhere_it_has_to_be():
    """Five places. Missing any one of them is a different broken symptom."""
    assert 'id="view-explore"' in HTML
    assert "explore: $('#view-explore')," in APP_JS
    assert "{ id: 'explore', label: 'Explore', views: ['explore'] }," in APP_JS
    assert "if (view === 'explore') return loadExplore(force);" in APP_JS
    assert "{ view: 'explore', label: 'Explore'," in APP_JS


def test_it_is_on_the_no_ticker_allow_list():
    """The guard is an allow-list by omission, so a new view is ticker-specific
    by default. Explore is the third to be caught by it: its loader ran, its
    requests never fired, and the page showed "No ticker loaded" on a view that
    has nothing to do with a symbol. Verified live with STATE.ticker null."""
    guard = APP_JS[APP_JS.index("if (!['market', 'indices', 'roth'"):]
    guard = guard[:guard.index("&& !STATE.ticker")]
    assert "'explore'" in guard


# ---------------------------------------------------------------- requests


def test_one_failed_leg_costs_its_own_section_not_the_page():
    fn = _fn("loadExplore")
    assert "Promise.allSettled" in fn
    assert "r.status === 'fulfilled'" in fn


def test_the_home_payload_is_reused_when_it_is_already_loaded():
    """Arriving from the command centre, this is already in STATE."""
    assert "STATE.home ? Promise.resolve(STATE.home) : getJSON('/api/home')" in _fn("loadExplore")


def test_the_grouping_is_fetched_not_inferred():
    """A first version rebuilt it from a `group` field on each scan. There is
    no such field: a scan is {id, name, looks_for, blind_spot}, so every screen
    landed in one group called "Other"."""
    assert "getJSON('/api/scanners/groups')" in _fn("loadExplore")
    fn = _fn("renderExplore")
    assert "(data.groups || {}).groups" in fn
    assert "s.group ||" not in fn


def test_a_missing_grouping_falls_back_to_one_list():
    """Rather than to no screens at all."""
    fn = _fn("renderExplore")
    assert "[{ id: 'all', label: 'Screens', scans: (scans.scans || []) }]" in fn


def test_it_does_not_run_the_screens():
    """Seventeen scans over a 3000-symbol universe on page load."""
    fn = _fn("loadExplore")
    assert "/api/scanners/" not in fn.replace("/api/scanners/groups", "")
    assert "runScan" not in fn


def test_a_section_that_did_not_arrive_is_named():
    """`allSettled` keeps the page, but the first cold load showed only the
    questions and said nothing about the three missing sections. A section that
    silently is not there reads as a product that does not have it."""
    fn = _fn("renderExplore")
    assert "Unavailable right now:" in fn
    for name in ("the screen catalogue", "the sector board",
                 "the cross-asset instruments"):
        assert name in fn, name


# ------------------------------------------------------------- the rows


def test_a_screen_opens_the_scan_view_on_that_screen():
    handler = APP_JS[APP_JS.index("closest('[data-explore-scan]')"):]
    handler = handler[:handler.index("data-explore-sector")]
    assert "switchView('scan')" in handler
    assert "runScan(exScan.dataset.exploreScan)" in handler


def test_a_sector_row_actually_opens_that_sector_s_read():
    """A first version only set `STATE.sectorFocus` and switched view. Nothing
    reads that field, so the click navigated and the focus did nothing: a state
    write standing in for behaviour."""
    handler = APP_JS[APP_JS.index("closest('[data-explore-sector]')"):]
    handler = handler[:handler.index("const wsMode")]
    assert "openSectorRead(symbol, 'sector-read-host')" in handler
    # The dead field is gone, not merely unused.
    assert "STATE.sectorFocus =" not in APP_JS


def test_cross_asset_cells_reuse_the_existing_instrument_handler():
    fn = _fn("renderExplore")
    assert "data-instrument=" in fn
    assert "closest('[data-instrument]')" in APP_JS


def test_the_cross_asset_grid_uses_the_shared_ranking():
    """Same function the command centre uses, so the two cannot disagree about
    which instrument moved most."""
    assert "rankedMoves(data.home)" in _fn("renderExplore")


# ------------------------------------------------------------- presentation


def test_the_descriptions_are_clamped_not_sliced():
    """`.slice(0, 110)` cut mid-word: "because a termi", "as ri", "of the".
    Verified live: two lines, and the full text still in the DOM."""
    assert "String(full.looks_for || '').slice" not in APP_JS
    block = CSS[CSS.index(".ex-scan-note {"):]
    block = block[:block.index("}")]
    assert "-webkit-line-clamp: 2" in block


def test_the_screens_note_says_whether_the_universe_is_ready():
    """`ready: false` is a normal cold-start state, not an error."""
    fn = _fn("renderExplore")
    assert "scans.ready" in fn
    assert "still building in the background" in fn


def test_every_class_it_renders_has_a_rule():
    used = set()
    for name in ("renderExplore", "exploreScanGroup"):
        for attr in re.findall(r'class="([^"]*)"', _fn(name)):
            for tok in attr.split():
                if tok.startswith("ex-"):
                    used.add(tok)
    assert {"ex-wrap", "ex-groups", "ex-group", "ex-scan", "ex-inst"} <= used, used
    for cls in used:
        assert ".%s" % cls in CSS, cls


def test_no_em_dashes_in_the_copy():
    for name in ("renderExplore", "exploreScanGroup"):
        body = re.sub(r"/\*.*?\*/", "", _fn(name), flags=re.S)
        for text in re.findall(r">([^<>{}]{16,})<", body):
            assert "—" not in text, (name, text)
