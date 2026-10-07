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
    # In a group, not necessarily its own: Explore and Scan share the Discover
    # group now. What matters is that some group can reach it -- a view no
    # group lists is reachable only from the command palette, which is the
    # fault test_nav_coherence was written for.
    groups = APP_JS.split("const NAV_GROUPS = [", 1)[1]
    assert "'explore'" in groups[:groups.index("\n];")]
    assert "if (view === 'explore') return loadExplore(force);" in APP_JS
    assert "{ view: 'explore', label: 'Explore'," in APP_JS


def test_it_is_on_the_no_ticker_allow_list():
    """The guard is an allow-list by omission, so a new view is ticker-specific
    by default. Explore is the third to be caught by it: its loader ran, its
    requests never fired, and the page showed "No ticker loaded" on a view that
    has nothing to do with a symbol. Verified live with STATE.ticker null."""
    # The list moved into TICKERLESS_VIEWS, because the Settings back-button
    # kept a second shorter copy of it and that copy had never heard of
    # Explore, Scan, Watchlist, Alerts or Compare -- so returning from Settings
    # to any of the five with no symbol loaded landed on Home instead.
    assert "if (!TICKERLESS_VIEWS.includes(view) && !STATE.ticker)" in APP_JS
    allowed = APP_JS[APP_JS.index("const TICKERLESS_VIEWS = ["):]
    allowed = allowed[:allowed.index("];")]
    assert "'explore'" in allowed
    # And there is exactly one such list.
    assert APP_JS.count("const TICKERLESS_VIEWS = [") == 1
    assert APP_JS.count("TICKERLESS_VIEWS.includes(") == 2, \
        "both the loader guard and the Settings back-button read it"


# ---------------------------------------------------------------- requests


def test_one_failed_leg_costs_its_own_section_not_the_page():
    fn = _fn("loadExplore")
    assert "Promise.allSettled" in fn
    assert "r.status === 'fulfilled'" in fn


def test_the_home_payload_is_reused_rather_than_refetched_blindly():
    """Arriving from the command centre, this is already in STATE.

    This asserted the literal `STATE.home ? Promise.resolve(STATE.home) :
    getJSON('/api/home')`, which is the same idea as the shared `homeData()`
    helper but a second implementation of it, and it was wrong in both
    directions: no in-flight guard, so opening Explore mid-boot fired a second
    /api/home; and no expiry, so Explore reused the payload for the life of the
    page and could draw an hours-old market reading.

    The property being protected is unchanged: do not refetch a payload you
    already hold. It is now held by one function, with a freshness window, and
    tests/test_home_fetch.py owns the details. What this keeps watching is that
    Explore goes through it and does not grow its own copy again. `loadExplore`
    is guarded by `exploreData && !force`, so the window costs at most one
    request per page load.
    """
    fn = _fn("loadExplore")
    assert "homeData()" in fn
    assert "getJSON('/api/home')" not in fn
    # A failed refresh must not empty a section that had content.
    assert "catch(() => STATE.home || null)" in fn


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


def test_the_scan_group_headings_read_the_name_not_the_id():
    """No group has ever carried a `label`, so `group.label || group.id` fell
    through to the id on all six and the page read MOVERS, MOMENTUM, VOLUME,
    STRUCTURE, RISK and RELPERF, uppercased by CSS, while the catalogue had been
    publishing "Market movers", "Momentum leaders", "Volume", "Trend structure",
    "High risk" and "Relative performance" the whole time. A reader reported the
    last one, which is the id you are least likely to guess the meaning of."""
    assert "group.name || group.label || group.id" in APP_JS
    assert "esc(group.label || group.id)" not in APP_JS


def test_every_published_group_actually_has_the_field_the_page_reads():
    """The other half of it. A heading that reads `name` is only right if every
    group carries one, and this is the check that would have caught the original
    the day `label` was written."""
    from app.analytics import relperf, scanners
    groups = scanners.groups() + [relperf.SCAN_GROUP]
    assert len(groups) >= 5
    for g in groups:
        assert g.get("name"), g.get("id")


def test_every_reading_draws_from_the_rows_the_server_actually_builds():
    """"A reading of the three sections below" gave two. Sector breadth filtered
    on `chg_1d`, which a sector-board row has never carried, so it was skipped
    on every load and nothing looked wrong: two readings is also a plausible
    page. Rows come from the real sector_board.build here, so a reading that
    names a field the server does not write fails rather than vanishing."""
    import json
    import os
    import shutil
    import subprocess

    import pandas as pd
    import pytest

    from app.analytics import sector_board

    jsc = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
    exe = jsc if os.path.exists(jsc) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")

    class Provider:
        def batch_history(self, symbols, period, interval):
            out = {}
            for i, sym in enumerate(symbols):
                # SPY rises 1 a day; half the sectors faster, half slower.
                step = 1.0 if sym == "SPY" else (1.5 if i % 2 else 0.5)
                closes = [100 + step * d for d in range(30)]
                out[sym] = pd.DataFrame({"Close": closes,
                                         "High": [c + 1 for c in closes],
                                         "Low": [c - 1 for c in closes]})
            return out

    board = sector_board.build(Provider())
    rows = [r for r in board["rows"] if r.get("available")]
    assert len(rows) == 11
    ahead = sum(1 for r in rows if r["rel_week_pct"] > 0)

    src = "\n".join([
        "function fmt(v, d) { return Number(v).toFixed(d); }",
        "function fmtPct(v, d) { return (v >= 0 ? '+' : '') + Number(v).toFixed(d) + '%'; }",
        _fn("exploreReadings"),
        "var rows = exploreReadings({ready: true, considered: 792, universe_size: 2975}, "
        "[], %s, %s);" % (json.dumps(rows), json.dumps(board["benchmark"])),
        "print(JSON.stringify(rows));",
    ])
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=30)
    readings = {r["label"]: r for r in json.loads(out.stdout.strip().splitlines()[-1])}
    assert "Sector breadth" in readings, out.stdout + out.stderr
    assert readings["Sector breadth"]["verdict"] == "%d of 11 ahead of SPY" % ahead
    # The share prints as a number in brackets, not after a typed double hyphen.
    assert "(27%)" in readings["What is screenable"]["detail"]
    assert "--" not in readings["What is screenable"]["detail"]


def test_a_quiet_tape_is_not_headlined_as_a_move():
    """Overnight the top of the ranking was HYG at 0.9x its normal day, under
    "Biggest move". Below one normal day the reading says nothing moved."""
    import json
    import os
    import shutil
    import subprocess

    import pytest

    jsc = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
    exe = jsc if os.path.exists(jsc) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")

    def run(rel):
        moves = [{"label": "HYG", "chg_1d": 0.4, "rel": rel}]
        src = "\n".join([
            "function fmt(v, d) { return Number(v).toFixed(d); }",
            "function fmtPct(v, d) { return (v >= 0 ? '+' : '') + Number(v).toFixed(d) + '%'; }",
            _fn("exploreReadings"),
            "print(JSON.stringify(exploreReadings(null, %s, [])));" % json.dumps(moves),
        ])
        out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=30)
        return json.loads(out.stdout.strip().splitlines()[-1])[0]

    quiet = run(0.9)
    assert quiet["label"] == "A quiet tape" and quiet["tone"] == "neutral"
    assert "0.9x" in quiet["detail"] and "HYG" in quiet["detail"]
    loud = run(2.4)
    assert loud["label"] == "Biggest move" and loud["verdict"] == "HYG +0.4%"
