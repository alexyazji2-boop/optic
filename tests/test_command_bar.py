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


def test_the_phone_hides_only_what_is_still_a_duplicate():
    """Four things were hidden here as copies of something else on screen. One
    of those premises has since stopped being true.

    `.home-brand` went because the topbar said OPTIC TERMINAL. The topbar is
    now the mark alone, so a phone had no brand anywhere on it, and the pills
    and the search form came back with it on the reader's call. The greeting
    stays hidden: the session block directly above it says the phase and the
    local time, which is the same fact with more in it, and that has not
    changed.
    """
    block = CSS[CSS.index("/* Phone: three things go"):]
    block = block[:block.index("\n}") + 2]
    assert ".hm-greet" in block
    for restored in (".home-brand", ".home-quick", ".home-search"):
        assert restored + " { display: none; }" not in block, restored
    # And the premise that justified hiding the brand has to stay retired.
    assert ".brand-text { display: none; }" in CSS


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
    # It now renders lowercase too, and that is an improvement rather than a
    # regression. This used to assert `table.data th { text-transform:
    # uppercase }` and note that p and n were being shouted as P and N despite
    # the source being right. Sentence-case headers put the rendered form back
    # in agreement with the convention.
    #
    # Anchored with a leading newline: `.panel .grid table.data th {` contains
    # the bare substring and sits earlier in the file, so indexing without it
    # lands on a rule whose whole body is `white-space: normal`.
    rule = CSS[CSS.index("\ntable.data th {"):]
    body = rule[:rule.index("}")]
    assert "text-transform: uppercase" not in body
    assert "font-size: var(--t-small)" in body


def test_the_tab_strip_spaces_its_labels_evenly():
    """Two of the seven tabs carry a dropdown caret, and the caret used to be
    inline with `margin-left: var(--space-2)`. So a tab with a menu was 16px
    wider than one without and the rhythm alternated: measured at 1500, the ink
    gap ran 20px between Home and Dossier, 37px between Dossier and Compare,
    then 20px and 37px again. It read as uneven spacing rather than as a wider
    button, which is what it was.

    Absolute against the button, which `nav.tabs button { position: relative }`
    already sets up, and in the top-right corner the inline box ended up in
    anyway. Nothing moves visually and every gap becomes the two buttons'
    padding and nothing else.
    """
    rule = CSS[CSS.index("\n.nav-caret {"):]
    rule = rule[:rule.index("}")]
    assert "position: absolute" in rule
    assert "margin-left" not in rule, \
        "an inline caret is 16px of width on two tabs out of seven"
    # The positioned ancestor has to exist, or absolute resolves to the page.
    assert "nav.tabs button { position: relative; }" in CSS


def test_the_strip_padding_is_the_only_thing_between_labels():
    """Which is what makes the gaps equal: one padding value, no per-tab extras,
    and no flex gap doubling up on it."""
    rule = CSS[CSS.index("\nnav.tabs button {"):]
    rule = rule[:rule.index("}")]
    assert "padding: var(--space-2) var(--space-2);" in rule
    nav = CSS[CSS.index("\nnav.tabs {"):]
    nav = nav[:nav.index("}")]
    assert "gap: 0;" in nav


def test_the_own_row_rule_outranks_the_one_row_rule():
    """Specificity, not source order, and that is the whole point.

    `nav.tabs-group { flex: none; min-width: auto }` fires unconditionally to
    hold the strip on one row. Against the width query's `nav.tabs { flex: 1 0
    100% }` it is equal specificity and later in the file, so it won there too:
    `order: 3` still moved the strip to the end of the row, `flex: 1 0 100%`
    never applied, and it therefore never took a line of its own. Measured at
    1410 with the row needing 1400, everything fitted, nothing wrapped, and the
    tabs rendered to the right of Pulse.

    `nav.tabs.tabs-group` is two classes to one, so it wins wherever it applies
    regardless of position. Anything that re-broadens that selector brings the
    bug back.
    """
    block = CSS[CSS.index("@media (max-width: 1410px) {"):]
    block = block[:block.index("\n}")]
    assert "nav.tabs.tabs-group { flex: 1 0 100%; min-width: 0; }" in block
    assert "order: 3" in block, "and it still has to move to the end of the row"


def test_the_breakpoint_covers_what_the_inline_row_needs():
    """The two numbers have to stay in step: the strip has no wrap left to
    absorb an overflow, so below the breakpoint it must take its own row and
    above it the row must actually fit. Re-measure both together."""
    assert "@media (max-width: 1410px) {" in CSS
    # The measurement is recorded next to the rule so it can be checked.
    marker = CSS[CSS.index("@media (max-width: 1410px) {") - 700:
                 CSS.index("@media (max-width: 1410px) {")]
    assert "1400px" in marker, "the measured requirement has to be written down"


def test_every_class_hidden_by_attribute_has_a_display_pair():
    """An author `display` beats the UA stylesheet's `[hidden] { display: none }`
    whatever the specificity, so a class that sets one and is toggled by the
    attribute stays on screen.

    `.range-pick` was the live case: `swingPriceBlock` renders it
    `<label class="range-pick" hidden>` on an intraday range, because there is
    no interval to choose on a one-minute series, and it kept its 62px and went
    on offering the choice. Measured with the attribute set, it computed
    `inline-flex`. CLAUDE.md records the same fault against `.set-pw`.
    """
    code = re.sub(r"/\*.*?\*/", " ", CSS, flags=re.S)
    carried = set()
    for m in re.finditer(r'class="([^"$]*)"[^>]{0,120}?\shidden(?=[\s>])', APP_JS):
        carried.update(m.group(1).split())
    for m in re.finditer(r'class="([^"$]*)"[^>]{0,160}?\$\{[^}]*\?\s*\'\s*hidden', APP_JS):
        carried.update(m.group(1).split())

    def body_of(cls):
        """Rules where the class is the *subject*, not an ancestor of it.

        A first version took every rule whose selector mentioned the class, and
        flagged `.combo-list` because `.combo-list li { display: flex }` sets a
        display on the child. The parent declares no display at all, so
        `[hidden]` works on it: verified in a browser, the real element computes
        `display: none` and zero width. Only a display on the element that
        carries the attribute can defeat the UA rule.
        """
        out = []
        for m in re.finditer(r"(?:^|[{}])\s*([^{}]*?)\{", code, re.S):
            selectors = [x.strip() for x in m.group(1).split(",")]
            subject = False
            for sel in selectors:
                last = sel.split()[-1] if sel.split() else ""
                # Strip pseudo-classes and states; `.x:hover` still has .x as subject.
                last = re.split(r"[:\[]", last)[0]
                if last.split(">")[-1] == "." + cls or last == "." + cls:
                    subject = True
            if not subject:
                continue
            start = m.end() - 1
            depth, j = 0, start
            while j < len(code):
                if code[j] == "{":
                    depth += 1
                elif code[j] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            out.append(code[start:j])
        return " ".join(out)

    offenders = []
    for cls in sorted(c for c in carried if c and "$" not in c):
        if not re.search(r"display:\s*(flex|block|grid|inline-flex|inline-block|inline-grid)",
                         body_of(cls)):
            continue
        if re.search(r"\." + re.escape(cls) + r"\[hidden\]", code):
            continue
        offenders.append(cls)
    assert offenders == [], \
        "these set a display and are toggled by [hidden], with no pair: {}".format(offenders)


def test_the_restyle_carries_its_own_phone_rules():
    """A block at the foot of the stylesheet beats every responsive rule written
    above it at equal specificity, so it has to restate them.

    The Asset restyle set `.hm-block { padding: var(--space-6) var(--space-7) }`
    unscoped, which silently beat that class's own 559px rule at line 9437.
    Measured on a 390px screen: 74px of horizontal padding, 19% of the
    viewport, leaving 275px of content. The reference's spacing is a desktop
    brochure measurement and none of it survives a phone.
    """
    block = CSS[CSS.index("/* ---- Asset restyle: the phone"):]
    for rule in (".panel { padding: var(--space-3) var(--space-4); }",
                 ".hm-block { padding: var(--space-3) var(--space-4); }"):
        assert rule in block, rule
    # And it must be inside a width query, or it is the same bug pointed the
    # other way.
    assert "@media (max-width: 559px)" in block


def test_the_phone_header_does_not_strand_the_assistant_on_its_own_row():
    """It was six rows and 234px on an 844px screen, 28% of the phone spent on
    chrome before a single reading, with Pulse pushed onto a row of its own
    because the row above was one word too wide. Dropping TERMINAL from the
    wordmark buys that word back; the mark plus OPTIC still identifies it."""
    # The wordmark is now hidden at every width, not just here: it was about
    # 115px of the top row restating what the mark and the browser tab already
    # say. The phone rule that hid only its second word is gone with it.
    assert ".brand-text { display: none; }" in CSS
    assert ".brand-text span { display: none; }" not in CSS
    # The name still has to reach a screen reader.
    assert 'aria-label="Optic Terminal. Go to home"' in open("static/index.html").read()


def test_the_tabs_spread_across_the_row_they_own():
    """Given room, but not the whole row.

    Above the breakpoint the strip is inline beside the search and every pixel
    is contested, which is why its buttons carry no gap at all. On its own row
    seven tabs were huddled in the first two thirds of a 1163px one.

    `space-between` was the first answer and it overcorrected: 93px between
    every label, which stops reading as one strip of navigation and starts
    reading as seven separate things. A fixed gap measures 53px between labels
    and leaves the group spanning 743px of the row, left-aligned with the
    content beneath it rather than stretched to meet the far edge.
    """
    block = CSS[CSS.index("@media (max-width: 1410px) {"):]
    block = block[:block.index("\n}")]
    assert "justify-content: flex-start; gap: var(--space-5);" in block
    assert "justify-content: space-between" not in block, \
        "that spaced them to 93px, which reads as seven separate things"
    # And the inline case must stay tight, or the one-row fit goes.
    nav = CSS[CSS.index("\nnav.tabs {"):]
    assert "gap: 0;" in nav[:nav.index("}")]


def test_the_mark_carries_the_brand_alone():
    """Resolution is not a consideration: it is an inline SVG on a 32-unit
    viewBox, resampled by the renderer at whatever size and pixel ratio it
    lands on."""
    assert ".brand-mark { width: 34px; height: 34px;" in CSS
    assert 'viewBox="0 0 32 32"' in open("static/index.html").read()
