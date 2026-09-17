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
    for label in ("'Chart'", "'News'", "'Earnings'", "'Investing'", "'Compare'"):
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


def test_the_session_detail_collapses_at_every_width():
    """It was phone-only, on the reasoning that the desktop has the room.

    The desktop has the room and spent it badly. Measured on AAPL at 727x835
    with the strip fully expanded: the four phase keys, the timezone note and
    the business description put the price hero at y=801 in an 835px viewport,
    so the number the reader searched for was the last thing on the first
    screen. The live parts — which session, the clock, the 24-hour strip — are
    still unconditional; what is behind the button is a fixed timetable, a
    colour legend and a company profile, none of which change during a day.
    """
    assert 'class="ses-detail' in APP_JS
    # The disclosure is gone. It was introduced for a phone-height measurement
    # that was real, and its two rules were written for the 640px block and
    # ended up at the top of the file outside it — so `display: none` applied at
    # every width and the desktop hid the company details behind a click for no
    # reason. The name of this test was the only thing in the repository that
    # said so; the code comment beside it claimed the desktop "renders exactly
    # what it did before".
    assert "data-ses-detail" not in APP_JS, "the toggle button is gone"
    assert ".ses-detail-btn" not in CSS, "and so are its styles"
    assert ".ses-detail { display: none; }" not in CSS, \
        "the details render unconditionally now"
    assert ".ses-detail.is-open" not in CSS
    assert "is-open" not in _fn("renderSessionBar"), \
        "and nothing gates them on an open class"


def test_the_company_profile_sits_behind_the_session_disclosure():
    """Sector, headcount, head office and a business description are reference:
    they have the same shelf life as the trading timetable and none of it
    changes during a session. It was rendering above the price, and it was the
    third copy of the company's identity on that screen — px-head names the
    symbol, the company and the exchange directly below it."""
    fn = _fn("renderSessionBar")
    detail = fn[fn.index('<div class="ses-detail'):]
    assert "${companyBlock}" in detail, "the profile must render inside the disclosure"
    head = fn[:fn.index('<div class="ses-detail')]
    assert "${companyBlock}" not in head, "and must not also render above it"


def test_no_disclosure_state_is_kept_across_the_sixty_second_repaint():
    """There is nothing left to keep.

    `loadSession` is on a 60s interval and renderSessionBar replaces innerHTML
    wholesale, so while the panel was collapsible its open state had to live in
    a module flag or it shut under a reader mid-sentence. With the panel always
    rendered the flag is dead weight, and a flag nothing reads is the kind of
    thing that gets wired back up by mistake.
    """
    assert "sessionDetailOpen" not in APP_JS


def test_the_summary_fit_is_measured_at_render():
    """Now that the box always has a layout, it can simply be asked.

    This used to have to wait for the disclosure to open: inside `display: none`
    both scrollHeight and clientHeight are 0, so a render-time check read
    `0 <= 1`, concluded the text fitted and hid "More" on every symbol whose
    description is in fact clamped. The `clientHeight` guard stays as the cheap
    proof the box is laid out before it is believed.
    """
    fn = _fn("renderSessionBar")
    assert "if (!sEl || !mEl || !sEl.clientHeight) return;" in fn
    assert "checkSummaryFit();" in fn
    # Comments stripped first. The comment above the function records what was
    # removed and therefore names it, which is the trap CLAUDE.md describes and
    # which caught this assertion on its first run.
    code = re.sub(r"/\*.*?\*/", " ", fn, flags=re.S)
    code = re.sub(r"^\s*//.*$", " ", code, flags=re.M)
    assert "if (open) checkSummaryFit();" not in code, "no open state to wait on"
    assert "fitChecked" not in code, "and no latch, because it runs once per render"


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


def test_control_labels_start_with_a_capital():
    """Reported from the session bar, where the timezone line ended in a link
    reading "change".

    Scoped to buttons and links, which are labels. It deliberately does not
    sweep every lowercase string in the file: most are sentence fragments inside
    a span, where a capital would be the grammatical error rather than the fix,
    and the status chips are uppercased by CSS so their source case never
    reaches a reader. Table headers are the same, via `table.data th`.
    """
    pat = re.compile(r">\s*([a-z][A-Za-z0-9 '&/.\-]{0,38})\s*<\s*/\s*(button|a|summary|label)\s*>")
    found = [m.group(1) for m in pat.finditer(APP_JS) if "${" not in m.group(1)]
    assert found == [], "control labels must be capitalised: {}".format(found)


def test_statistical_notation_keeps_its_case():
    """`p` is a p-value and `n` is a sample size. Lowercase is the convention,
    so the capitalisation pass above must not reach them. They render uppercase
    anyway through `table.data th`, which is a separate question from what the
    source says."""
    assert "<th>p</th>" in APP_JS
    # Anchored with a leading newline. `.panel .grid table.data th {` contains
    # the bare substring and sits earlier in the file, so indexing on it without
    # the newline lands on a rule whose whole body is `white-space: normal`.
    rule = CSS[CSS.index("\ntable.data th {"):]
    assert "text-transform: uppercase" in rule[:rule.index("}")]
