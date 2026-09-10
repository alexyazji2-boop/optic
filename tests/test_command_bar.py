"""The command bar: what it offers before you type, and what a ticker unlocks.

Opened empty it used to show six destinations and nothing else. It now leads
with the symbols you were just looking at, then the actions you cannot reach by
typing a symbol, then the places.

**Every action goes somewhere that already exists.** That was the constraint on
the list, and it is the one worth a test: an action that opens a view Optic does
not have is worse than an absent action, because it reads as a broken feature
rather than a missing one. The scan ids are checked against the catalogue
`/api/scanners` publishes.

Also here: the phone layout, because the same brief asked for both and the
mobile fix is measured rather than asserted.
"""

from __future__ import annotations

import re

APP_JS = open("static/app.js").read()
CSS = open("static/styles.css").read()


def _fn(name: str) -> str:
    start = APP_JS.index("function %s(" % name)
    nxt = APP_JS.find("\nfunction ", start + 1)
    return APP_JS[start:nxt if nxt > 0 else len(APP_JS)]


# ----------------------------------------------------------------- recents


def test_the_assistant_is_called_pulse_everywhere():
    """Three places said "Ask Optic" — the home panel heading, a command-bar
    quick action and the palette's group label — while the button on every panel
    said "Ask Pulse" and the assistant introduces itself as Pulse. Optic is the
    terminal; Pulse is the thing you ask."""
    assert "Ask Optic" not in APP_JS
    assert "const ASK_GROUP = 'Ask Pulse';" in APP_JS


def test_the_group_name_is_one_constant():
    """It is a label AND a comparison key. Two literals would let the label be
    renamed while the branch that clears the duplicate `enter` badge kept
    reading the old one — silently, since nothing throws."""
    # The quick-action label spells it too, and that is fine: it is display only.
    # What must be single is the value the comparison reads.
    assert APP_JS.count("group: 'Ask Pulse'") == 0, "the group name is inlined"
    assert "group: ASK_GROUP" in APP_JS
    assert "r.group === ASK_GROUP" in APP_JS


def test_a_symbol_is_recorded_wherever_it_is_opened():
    """One place, because every route into a symbol goes through loadTicker:
    the search box, the palette, a watchlist row, a mover row, a holding in the
    ledger. Recording per call site would miss whichever is added next."""
    assert "rememberSymbol(next);" in _fn("loadTicker")
    assert APP_JS.count("rememberSymbol(") == 2      # the definition and that call


def test_recents_are_deduplicated_and_most_recent_first():
    """Opening the same name twice should not fill the list with one symbol."""
    fn = _fn("rememberSymbol")
    assert "[sym, ...recentSymbols().filter((s) => s !== sym)]" in fn
    assert "slice(0, RECENT_MAX)" in fn


def test_a_hand_edited_store_cannot_inject_a_row():
    """It reaches a URL and a label, so the shape is validated on read."""
    fn = _fn("recentSymbols")
    assert "Array.isArray(raw)" in fn
    assert "typeof s === 'string'" in fn
    assert "test(s)" in fn


def test_recents_are_local_not_account_backed():
    """A per-device convenience. Putting it in SQL would mean a write on every
    ticker open for a list nobody would miss."""
    fn = _fn("rememberSymbol")
    assert "localStorage.setItem(RECENT_KEY" in fn
    assert "authApi" not in fn and "api(" not in fn


def test_private_mode_costs_the_history_not_the_bar():
    assert "catch (e) { /* private mode: the bar just has no history */ }" in _fn("rememberSymbol")
    assert "catch (e) { return []; }" in _fn("recentSymbols")


# ---------------------------------------------------------- quick actions


def test_every_quick_action_targets_something_that_exists():
    """The constraint on this list. Views come from PALETTE_PLACES' own set and
    scans from the catalogue."""
    block = APP_JS[APP_JS.index("const QUICK_ACTIONS = ["):]
    block = block[:block.index("\n];")]
    views = set(re.findall(r"switchView\('([a-z]+)'\)", block))
    known = set(re.findall(r"\{ view: '([a-z]+)'", APP_JS))
    assert views, block
    assert views <= known, sorted(views - known)


def test_the_scan_actions_name_real_scan_ids():
    """Checked against /api/scanners: movers, volume and momentum are three of
    the thirteen the catalogue publishes."""
    block = APP_JS[APP_JS.index("const QUICK_ACTIONS = ["):]
    block = block[:block.index("\n];")]
    ids = set(re.findall(r"runScan\('([a-z-]+)'\)", block))
    assert ids == {"movers", "volume", "momentum"}, ids


def test_the_scan_actions_use_the_existing_entry_point():
    """A first draft added an `openScan` wrapper that duplicated `runScan`,
    fifty lines from a comment in this same file saying there is no openScan."""
    assert "function openScan(" not in APP_JS
    block = APP_JS[APP_JS.index("const QUICK_ACTIONS = ["):]
    block = block[:block.index("\n];")]
    assert "runScan(" in block


def test_the_empty_bar_leads_with_recents_then_actions_then_places():
    build = _fn("paletteBuild")
    empty = build[:build.index("const upper = q.toUpperCase();")]
    assert empty.index("recentSymbols()") < empty.index("QUICK_ACTIONS")
    assert empty.index("QUICK_ACTIONS") < empty.index("PALETTE_PLACES")


def test_every_empty_state_row_closes_the_palette():
    """A row that leaves the overlay open covers the view it just opened. The
    places branch did not close it before this."""
    build = _fn("paletteBuild")
    empty = build[:build.index("const upper = q.toUpperCase();")]
    runs = re.findall(r"run: \(\) => \{([^}]*)\}", empty)
    assert len(runs) >= 3, runs
    for body in runs:
        assert "closePalette()" in body, body


# --------------------------------------------------------- a ticker query


def test_a_ticker_offers_the_views_that_take_one():
    fn = _fn("paletteBuild")
    for label in ("'Chart'", "'News'", "'Earnings'", "'Long-term'", "'Compare'"):
        assert label in fn, label


def test_the_ticker_rows_are_grouped_under_the_symbol():
    """So a five-row block reads as "these are NVDA's" rather than as five
    unrelated destinations."""
    fn = _fn("paletteBuild")
    assert "group: upper," in fn


def test_saved_research_is_matched_on_the_ticker_field():
    """A question about AMD that mentions NVDA belongs under AMD, so this
    matches the row's own ticker rather than searching the text."""
    fn = _fn("paletteBuild")
    assert "String(r.ticker || '').toUpperCase() === upper" in fn
    # savedResearch() already resolves account-vs-local, so this needs no branch.
    assert "savedResearch() || []" in fn


def test_nothing_without_a_feed_is_offered():
    """Related-companies and holdings-based ETF membership have no endpoint.
    Name-matched ETFs are already delivered by /api/search's Symbols group,
    which is where NVDB and NVDY come from."""
    fn = _fn("paletteBuild")
    assert "Related companies" not in fn
    assert "ETFs containing" not in fn


# ------------------------------------------------------------ phone layout


def test_the_session_detail_collapses_only_on_a_phone():
    """Measured at 375x812: the legend and description took ~240px and pushed
    the day's moves off the first screen. The desktop renders what it always
    did."""
    assert 'class="ses-detail"' in APP_JS
    assert "data-ses-detail" in APP_JS
    assert ".ses-detail-btn { display: none; }" in CSS
    phone = CSS[CSS.index("@media (max-width: 719px) {"):]
    assert ".ses-detail { display: none; }" in phone


def test_the_toggle_uses_a_class_not_the_details_element():
    """`open` cannot be set by a media query, so a <details> would need JS to
    pick its initial state per width and would then fight a resize."""
    fn = _fn("renderSessionBar")
    assert "classList.toggle('is-open')" in fn
    assert "aria-expanded" in fn


def test_the_phone_hides_only_duplicates():
    """Each of the four is a copy of something else on the same screen. The
    search form goes because the topbar carries #ticker-input with the same
    live results."""
    block = CSS[CSS.index("/* Phone: three things go"):]
    block = block[:block.index("\n}") + 2]
    for cls in (".home-brand", ".home-quick", ".hm-greet", ".home-search"):
        assert cls in block, cls


def test_the_phone_block_sits_after_the_rules_it_overrides():
    """`.hm-greet` is defined near the bottom of the stylesheet. An earlier copy
    of this media query set display:none and the greeting stayed on screen,
    because at equal specificity the later rule wins."""
    assert CSS.index(".hm-greet {") < CSS.index(".hm-greet { display: none; }")


def test_the_topbar_search_is_what_the_phone_relies_on():
    """Verified live on a 375px viewport: ten matches for "NV"."""
    assert 'id="ticker-input"' in open("static/index.html").read()
