"""Tests for the UI/UX refactor: responsiveness, dead style rules, contrast.

These assert on the stylesheet as a source document, which is the only place
the facts live — there is no JS test runner in this project. Each test stands
for something that was measured as broken in a real browser at a real viewport
size, so the numbers in the docstrings are observations rather than targets.
"""

import re

CSS = open("static/styles.css", encoding="utf-8").read()
APP = open("static/app.js", encoding="utf-8").read()
CHARTS = open("static/charts.js", encoding="utf-8").read()
HTML = open("static/index.html", encoding="utf-8").read()
CONSUMERS = APP + CHARTS + HTML

NO_COMMENTS = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)


def _blocks():
    return re.findall(r"([^{}]+)\{([^{}]*)\}", NO_COMMENTS)


# --------------------------------------------------------------- responsive

def test_there_is_a_breakpoint_for_phone_widths():
    """The smallest breakpoint in the file was 620px, so a 375px screen was
    served laptop rules: the top bar measured 211px tall and the status strip
    another 78, meaning 289px — 36% of an iPhone viewport — was chrome."""
    assert "@media (max-width: 559px)" in CSS


def phone_block_with(css, needle):
    """The `@media (max-width: 559px)` block that actually contains `needle`.

    There is more than one phone block in this stylesheet and there always
    will be: CLAUDE.md's rule is that a phone override belongs *after* the
    rule it overrides, so they are scattered by design rather than gathered
    in one place.

    Four tests below took `css.index("@media (max-width: 559px)")` -- the
    *first* block -- and read a selector out of it. They all broke at once the
    day a new phone block was added above theirs, and none of them is about
    the first block: each is about the block that styles its own selector.
    That is a fault in the lookup rather than in the CSS, and asserting the
    needle appears in exactly one block is also a check worth having.
    """
    parts = css.split("@media (max-width: 559px)")[1:]
    hits = [b[:b.index("\n}\n")] for b in parts if needle in b[:b.index("\n}\n")]]
    assert len(hits) == 1, "{!r} appears in {} phone blocks".format(needle, len(hits))
    return hits[0]


def test_the_phone_tab_strip_keeps_its_own_overflow_declaration():
    """This looks like a duplicate of the 1280px block and is not.

    `nav.tabs-group { overflow: visible }` fires unconditionally further down
    the file so the section dropdowns can escape the strip, and being later it
    wins. Removing this line as redundant pushed the two right-hand tabs 205px
    outside the document — 375px viewport against a 580px scrollWidth — and put
    the horizontal scrollbar back.
    """
    phone = phone_block_with(NO_COMMENTS, "nav.tabs,")
    strip = phone[phone.index("nav.tabs,"):]
    strip = strip[:strip.index("}")]
    assert "overflow-x: auto;" in strip
    assert "flex-wrap: nowrap;" in strip


def test_the_phone_dropdown_cannot_overhang_the_screen():
    """`left: 0` plus `min-width: 190px` on a nav item sitting at x=190 ran the
    menu to 380px on a 375px screen, which was the entire horizontal scroll.
    Fixed positioning pinned to both edges removes the arithmetic."""
    phone = phone_block_with(CSS, ".nav-menu {")
    menu = phone[phone.index(".nav-menu {"):]
    menu = menu[:menu.index("}")]
    assert "position: fixed;" in menu
    assert "left: var(--space-3);" in menu and "right: var(--space-3);" in menu


def test_the_phone_dropdown_opens_below_the_bar_not_across_it():
    """`top: auto` on a fixed box uses its static position, which put the menu
    over the tab strip and hid the section you were choosing from. A percentage
    is no good either — on a fixed box it resolves against the viewport — so the
    bar's measured height is the anchor."""
    phone = phone_block_with(CSS, ".nav-menu {")
    menu = phone[phone.index(".nav-menu {"):]
    menu = menu[:menu.index("}")]
    assert "var(--topbar-h" in menu
    # ...and something has to actually set it, with a fallback in the CSS for
    # browsers that never run the observer.
    assert "setProperty('--topbar-h'" in APP
    # Sliced to the function, not to a character count. At [:1200] this broke
    # when a comment was added inside it — a window measured in characters
    # fails on an edit that changes nothing it was testing. Same fault as the
    # [:1600] slice in tests/test_panel_chooser.py.
    fn = APP.split("function trackTopbarHeight() {", 1)[1].split("\nfunction ", 1)[0]
    assert "ResizeObserver" in fn


def test_a_menu_may_never_be_wider_than_the_window():
    """Belt and braces for every width, not just the phone one."""
    assert "max-width: calc(100vw - 2 * var(--space-4))" in CSS


def test_the_long_landing_placeholder_is_shortened_on_a_phone():
    """It needs 402px in the app's own face and a phone gives the field 343 at
    most, so it rendered as "Search a ticker or com" — cutting off the example,
    which is the only part that teaches anything."""
    assert "HOME_SEARCH_NARROW" in APP
    assert "matchMedia('(max-width: 559px)')" in APP
    # The accessible name must NOT be the thing that got shortened.
    block = APP[APP.index('<input id="home-input"'):][:400]
    assert 'aria-label="Ticker symbol or company name"' in block


def test_the_topbar_search_wrapper_grows_rather_than_the_input_alone():
    """The input is wrapped in .combo so the autocomplete can position its list,
    and the wrapper is `flex: 0 1 auto`. Growing only the input left 96px of the
    row empty while the placeholder truncated inside it."""
    phone = phone_block_with(CSS, ".search .combo {")
    combo = phone[phone.index(".search .combo {"):]
    combo = combo[:combo.index("}")]
    assert "flex: 1 1 auto;" in combo
    # Without min-width:0 a flex item will not shrink below its content width.
    assert "min-width: 0;" in combo


# --------------------------------------------------------- dead style rules

DEAD_NAMES = [
    "brief-picker", "brief-title", "chat-chip", "fg-chip", "fg-dial", "fg-head",
    "ind-grid", "ind-group", "ind-name", "ind-opt", "ind-what", "ind-caveat",
    "sub-dynamic", "ws-leg-hint", "ws-widget-add", "glass", "scroll-shadow-x",
    "ws-head-sym", "scroll-x", "table-wrap",
]


def test_no_rule_targets_a_class_that_appears_in_no_markup():
    """Seventeen class names had styles and no markup, `.glass` among them — a
    liquid-glass utility defined three times over and applied to nothing.

    `.scroll-x` and `.table-wrap` are on this list because the refactor
    introduced them itself: a phone rule was written for wrappers this codebase
    does not have. The real one is `.table-scroll`.
    """
    still_styled = [n for n in DEAD_NAMES
                    if re.search(r"\." + re.escape(n) + r"\b", NO_COMMENTS)]
    assert still_styled == [], still_styled


def test_the_scrollable_table_rule_names_the_class_that_exists():
    assert ".table-scroll" in NO_COMMENTS
    assert 'class="table-scroll"' in CONSUMERS


def test_a_dead_class_inside_not_or_has_does_not_condemn_its_rule():
    """A class that only ever appears as an exclusion makes its condition
    vacuously true and leaves the subject of the selector completely live. A
    first pass at removing dead classes deleted such a rule on the strength of
    the name inside the `:not()`.

    The example used to be the two-up height cap,
    `.grid.c2 > .panel:not(.span2):not(:has(svg.chart)):not(:has(.chart-controls))`.
    That rule is gone now — not because a class in it was dead, but because the
    cap turned those panels into nested vertical scroll containers; see
    test_no_panel_is_capped_into_a_nested_scroll_container. So the principle is
    pinned to the rule that still has this shape: the grid that hides itself
    when every panel in it is one Simple mode takes.
    """
    assert ".grid:has(> .panel.is-advanced):not(:has(> *:not(.is-advanced)))" \
        in NO_COMMENTS


def test_the_screen_reader_helper_is_defined_once():
    """Two identical definitions, three thousand lines apart."""
    assert len(re.findall(r"^\.sr-only \{", NO_COMMENTS, re.M)) == 1


def test_the_screen_reader_helper_does_not_rely_on_deprecated_clip():
    """`clip` is deprecated and now ignored by some engines, which would leave a
    1px-square box with its text overflowing."""
    rule = NO_COMMENTS[NO_COMMENTS.index(".sr-only {"):]
    rule = rule[:rule.index("}")]
    assert "clip-path: inset(50%)" in rule
    assert "clip: rect(" in rule, "the fallback is still worth keeping"


def test_the_pan_cursor_is_declared_in_one_place():
    """A `body.ws-panning` rule was already in the file, left behind by the
    first version of drag-to-pan and dormant until something set that class
    again. It wins on !important, so a second declaration was two rules for one
    state with only one of them in effect."""
    body_level = re.findall(r"body\.ws-panning[^{]*\{[^}]*cursor: grabbing", NO_COMMENTS)
    assert len(body_level) == 1, body_level
    # The navigator strip has its own, which is a different element and a
    # different gesture — it is not the duplicate this is guarding against.
    assert ".ws-nav.dragging { cursor: grabbing; }" in NO_COMMENTS


# ------------------------------------------------------------- interaction

def test_every_hover_state_transitions():
    """Fifty-eight of eighty-three hover rules changed colour with no
    transition, so most of the app snapped while a handful of buttons eased.
    The eye reads that as unfinished rather than as fast.

    Four bases are expected to remain: two are hover rules on an element whose
    own base selector is already covered, and two belong to a menu that carries
    its own transition.
    """
    transitioned = set()
    for sel, body in _blocks():
        if not re.search(r"\btransition\s*:", body):
            continue
        if "none" in body.split("transition")[1][:40]:
            continue
        for part in sel.split(","):
            transitioned.add(part.strip())
    missing = set()
    for sel, _ in _blocks():
        if ":hover" not in sel:
            continue
        for part in sel.split(","):
            part = part.strip()
            if ":hover" not in part:
                continue
            base = part.split(":hover")[0].strip()
            # A functional pseudo-class in the base is not a different element.
            # `.ws-wrail-btn:not(:disabled):hover` reduces to `.ws-wrail-btn`,
            # which is where the transition is declared; without stripping it
            # the check reported a rule that was already covered. Written as a
            # loop because a selector can carry more than one.
            while True:
                stripped = re.sub(r":(?:not|is|where)\([^()]*\)$", "", base).strip()
                if stripped == base:
                    break
                base = stripped
            if base and base not in transitioned:
                missing.add(base)
    allowed = {".nav-item", ".panel.is-closed", "h2 .gloss-term", "h3 .gloss-term"}
    assert missing <= allowed, sorted(missing - allowed)


def test_the_shared_transition_only_animates_paint():
    """Animating a layout property forces a full-document reflow every frame,
    which is why the rule above `main` says padding gets no transition. The
    shared rule must not quietly reintroduce that."""
    rule = NO_COMMENTS[NO_COMMENTS.index("  transition:\n    color var(--dur-ui)"):]
    rule = rule[:rule.index("}")]
    for layout in ("width", "height", "padding", "margin", "top", "left", "inset"):
        assert re.search(r"\b" + layout + r"\s+var\(--dur-ui\)", rule) is None, layout


def test_the_shared_transition_respects_reduced_motion():
    """A vestibular trigger does not care that the movement was only a fade."""
    tail = CSS[CSS.index("interaction, everywhere"):]
    assert "@media (prefers-reduced-motion: reduce)" in tail


# ---------------------------------------------------------------- contrast

def _lum(hex_colour):
    hex_colour = hex_colour.lstrip("#")
    parts = [int(hex_colour[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in parts]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _ratio(a, b):
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _token(name, theme=0):
    """theme 0 = the dark :root, 1 = the light override."""
    hits = re.findall(r"--%s:\s*(#[0-9a-fA-F]{6})" % name, NO_COMMENTS)
    return hits[theme]


def test_no_filled_control_puts_white_on_the_series_blue():
    """White on --s1 measures 3.64:1 and fails body text. --btn-primary exists
    for this: it is the one blue chosen for white text sitting ON it rather than
    for separation from the seven other series hues."""
    assert "background: var(--s1); color: #fff" not in NO_COMMENTS
    assert _ratio("#ffffff", _token("btn-primary")) >= 4.5


def test_the_green_series_slot_can_carry_text_in_both_themes():
    """#008300 reached the Read card's heading through --accent and measured
    3.83:1 on --surface, 3.54:1 on --surface-2 and 4.00:1 on --plane — under the
    threshold on every surface in the app, including the plane."""
    for theme, surfaces in ((0, ("surface", "surface-2", "plane")),
                            (1, ("surface", "surface-2"))):
        s6 = _token("s6", theme)
        for surface in surfaces:
            ratio = _ratio(s6, _token(surface, theme))
            assert ratio >= 4.5, (theme, surface, s6, round(ratio, 2))


def test_the_green_slot_stays_distinguishable_from_the_directional_green():
    """Brightening #008300 straight up lands it on top of --pos, and these are
    supposed to be eight separable categorical hues."""
    s6, pos = _token("s6"), _token("pos")
    a = [int(s6.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    b = [int(pos.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    assert sum(abs(x - y) for x, y in zip(a, b)) > 60, (s6, pos)


# ------------------------------------------------------------ tap targets

def test_undersized_controls_grow_their_hit_area_not_their_box():
    """WCAG 2.5.8 wants 24x24. The panel chevron measured 17x13 and the ask-Pulse
    pills 63x16. An inset ::after is invisible, costs no layout and belongs to
    the button, so it forwards the click; padding would have moved every panel
    heading for a reason that has nothing to do with how it looks."""
    rule = NO_COMMENTS[NO_COMMENTS.index(".panel-toggle::after,"):]
    rule = rule[:rule.index("}")]
    assert "position: absolute" in rule and "inset: -6px" in rule
    assert re.search(r"\.panel-toggle,\s*\n\.ask-pulse \{ position: relative; \}", NO_COMMENTS)


def test_the_chevron_keeps_its_own_before_pseudo_element():
    """The glyph is drawn with ::before, which is why the hit area uses ::after."""
    assert ".panel-toggle::before {" in NO_COMMENTS


# ------------------------------------------------------------ a11y outline

def test_the_loaded_chart_view_has_a_heading():
    """The empty state has <h2>Charting</h2> and it is replaced when a symbol
    loads, so the view a reader spends the most time in was the only one with
    nothing in its heading outline."""
    block = APP[APP.index("host.innerHTML = `\n  ${/*"):][:1600]
    assert 'class="sr-only">Charting ${esc(STATE.chartSymbol)}' in block


# ------------------------------------------------- de-cluttering the Options tab
#
# Measured on AAPL at 727x835 before any of this: the Options tab was 10,761px
# for a reader with no stored panel state, and the price hero sat at y=801 in an
# 835px viewport. Every number in these docstrings is an observation from that
# session, not a target.


def test_a_collapsed_momentum_panel_actually_collapses():
    """The bug this exists for.

    `.grid.momentum-row > .panel > .panel-body` carries four classes and
    outranked the three in `.panel.is-closed > .panel-body { display: none }`,
    so the equal-height flexing won and the collapse lost. Clicking either
    heading rotated the chevron and set aria-expanded="false" while the panel
    stayed 466px tall — measured on AAPL with both panels reporting is-closed
    and their bodies computing to display:flex over a 400px box. 930px of chart
    the reader had asked to put away, and a control that took the click and did
    nothing.

    Excluded rather than out-specified: the flexing is only meaningful between
    two panels that are both showing a chart.
    """
    assert ".grid.momentum-row > .panel:not(.is-closed) > .panel-body {" in NO_COMMENTS
    assert ".grid.momentum-row > .panel > .panel-body {" not in NO_COMMENTS, \
        "the unqualified form outranks the collapse rule"


def test_a_collapsed_momentum_panel_opts_out_of_the_stretch():
    """The row is `align-items: stretch` so the two charts share a baseline.
    With one panel closed that inflates a 66px header to its sibling's height,
    which looks like the collapse half-worked."""
    assert ".grid.momentum-row > .panel.is-closed { align-self: start; }" in NO_COMMENTS


def test_every_top_level_options_panel_can_be_collapsed():
    """makePanelsCollapsible only adopts a panel with a direct h2 — "nothing to
    click and nothing to label the collapsed state with". Volatility context
    was titled with an h3 and fell through it: 678px, the only panel on the tab
    with no toggle, because of a heading level."""
    block = APP[APP.index("Volatility context, moved out of the entry plan"):]
    block = block[:2000]
    assert "<h2>${hg('Volatility context')}" in block
    assert "<h3>${hg('Volatility context')}" not in block


def test_the_options_tab_opens_two_panels_not_five():
    """The five that used to open came to 5,476px, and the Pulse hero plus the
    four summary blocks above them — not collapsible, always rendered — come to
    another 1,790px. So the tab opened with the read stated five times before
    the reader reached anything new. Quote (404px) repeats px-head almost
    exactly; Optic's Perspective (1,017px) is the fifth restatement; close
    defence (449px) answers what the verdict above it already leads with."""
    block = APP[APP.index("const PANELS_OPEN_BY_DEFAULT = {"):]
    block = block[:block.index("};") + 2]
    swing = block[block.index("swing:"):block.index("earnings:")]
    assert "'swing verdict'" in swing, "the answer stays open"
    assert "'price, moving averages'" in swing, "the chart is what the tab is for"
    for dropped in ("'quote'", '"optic\'s perspective"', "'close defence'"):
        assert dropped not in swing, f"{dropped} is a duplicate of something above it"


def test_the_options_tab_has_one_price_header_not_two():
    """securityHeader's full form and renderPriceHead both name the symbol, the
    company, the exchange, the last price and the change. Stacked they measured
    108px + 280px of the same four facts — and the sec-head copy showed the
    price at var(--t-body), 13px, against px-head's display size, so the
    smaller duplicate was also the less legible one."""
    assert "securityHeader('swing', { compact: true })" in APP
    body = APP.split("function securityHeader(", 1)[1].split("\nfunction ", 1)[0]
    assert "opts.compact ? '' : `<div class=\"sec-id\">" in body, \
        "compact is what drops the identity line"


def test_the_disclaimer_footer_is_one_column_with_no_rule():
    """Reported as "why is there a breaker here? keep the text consistent",
    against a hairline sitting mid-sentence in the footer notice.

    It was two CSS columns with a `column-rule` between them, to fill a 1900px
    bar that a 110ch measure left two thirds empty. Measured at 1900px the
    columns came out **two lines deep**, which is the same fault the block
    already recorded talking itself out of a 46ch `column-width` -- "four
    columns of one and a half lines each... the sentence had been chopped into
    slivers" -- stopped at two slivers instead of four. The rule then made the
    split look deliberate rather than fixing it.

    The cap in the base rule now stands at every width, and the collapsed
    notice and the expanded disclaimer share it."""
    assert "column-rule" not in NO_COMMENTS, \
        "the hairline is the breaker that was reported"
    for selector in (".legal-line", ".legal-full"):
        assert "{} {{ column-count".format(selector) not in NO_COMMENTS, selector

    # One measure, both states, so the expanded version does not reflow to a
    # different width than the line that opened it.
    for selector in (".legal-line {", ".legal-full {"):
        block = NO_COMMENTS[NO_COMMENTS.index(selector):]
        block = block[:block.index("}")]
        assert "max-width: 110ch;" in block, selector
    # And nothing later takes the cap off again, which is what the 1180px
    # block did.
    assert "max-width: none;" not in NO_COMMENTS.split(".legal-line {", 1)[1][:1200]


def test_the_section_strips_drag_yields_to_every_control_on_it():
    """Reported as "these buttons do not work" against Expand all, Collapse
    all and Panels.

    The strip is drag-to-pan, and its `pointerdown` handler called
    `nav.setPointerCapture`. A captured pointer retargets the rest of the
    sequence — including the `click` — to the capture target, so the click
    arrived on `nav`, every `evt.target.closest('[data-bulk]')` below returned
    null, and all three buttons did nothing. The guard bailed out for
    `[data-sec-jump]` chips, which is why those kept working and the bulk
    buttons did not.

    Measured by clicking Expand all with a real mouse and logging the click
    target: `NAV.sec-index`, not the button. Panels open went 0 of 11 before
    and 11 of 11 after.

    **This test is weaker than the bug deserves and it is worth saying why.**
    CLAUDE.md's rule is that reading source text to prove a control-flow
    property is a bad test, and it applies here. But nothing in this suite can
    reproduce the defect: `el.click()` and a hand-dispatched MouseEvent
    sequence both exercise the handler and both *passed* while the button was
    dead, because neither can make a pointer id active, so `setPointerCapture`
    throws into its catch and no retargeting happens. Only a trusted pointer
    sequence shows it.

    So the substantive assertion is the second one, which is structural and a
    regex can check honestly: the guard covers `button`, and every control the
    strip renders is a `button`. An `<a>` or a `<div role="button">` added
    here later would slip the guard again."""
    fn = APP.split("function armSectionIndex(view, nav, panels) {", 1)[1]
    fn = fn.split("\nfunction ", 1)[0]
    down = fn.split("addEventListener('pointerdown'", 1)[1].split("});", 1)[0]
    assert "closest('button')" in down, \
        "the drag must not start on any control in the strip"
    assert "[data-sec-jump]" not in down, \
        "naming only the chips is the bug: the bulk buttons were not covered"

    # The guard says `button`, so everything rendered into the strip has to be
    # one. This is the half that would catch the next occurrence.
    build = APP.split("function buildSectionIndex(view) {", 1)[1]
    build = build.split("\nfunction ", 1)[0]
    for control in ("data-sec-jump", "data-bulk=\"open\"", "data-bulk=\"close\"",
                    "data-panels-open"):
        assert control in build, control
        before = build.split(control, 1)[0]
        tag = before.rsplit("<", 1)[1].split()[0]
        assert tag == "button", "{} is rendered as <{}>, which the drag guard " \
            "does not recognise as a control".format(control, tag)


def test_the_quote_panel_is_gone_and_took_nothing_with_it():
    """Reported as "this is a repetition".

    The Quote panel sat below a price header that already carried every row in
    it: the name, the exchange, the last price, the change and its percent,
    the day's range, the 52-week range, volume against average, and the market
    cap. Nine readings, all of them a second time in a second typeface.

    Three were only in the panel -- ATR (14), the expected two-week range and
    the sector -- plus the extended-hours caveat, which is the one line on the
    page saying the other figures are measured from the regular close rather
    than from the after-hours print. Removing the panel had to keep those or
    it would be deleting information rather than a duplicate, so this asserts
    both halves: the panel is gone, and each of the four is in the header."""
    swing = APP.split("function renderSwing(d) {", 1)[1].split("\nfunction ", 1)[0]
    assert "hg('Quote')" not in swing, "the duplicate panel is back"
    assert "hg('Quote')" not in APP, "and it has not reappeared elsewhere"

    head = APP.split("function renderPriceHead(d, extQ) {", 1)[1]
    head = head.split("\nfunction ", 1)[0]
    for carried, why in (
            ("vol.atr14", "how far this name moves on an ordinary day"),
            ("vol.expected_2w_move_pct", "the expected two-week range"),
            ("q.sector", "the sector"),
            ("px-ext-note", "the extended-hours caveat")):
        assert carried in head, "{} ({}) was dropped with the panel".format(carried, why)

    # ATR is a term the glossary defines, and the panel it came from marked it.
    assert "hg('ATR')" in head, "the abbreviation needs its gloss"


def test_the_extended_hours_caveat_spans_the_header_rather_than_a_column():
    """`.px-head` is a wrapping flex row, so a grid property on a child is
    ignored in silence -- the note would sit in the row squeezing the price
    instead of taking a line under it. This was written as `grid-column: 1 /
    -1` first and did exactly that."""
    block = NO_COMMENTS[NO_COMMENTS.index(".px-ext-note {"):]
    block = block[:block.index("}")]
    assert "flex:" in block and "100%" in block
    assert "grid-column" not in block

    head = NO_COMMENTS[NO_COMMENTS.index(".px-head {"):]
    head = head[:head.index("}")]
    assert "display: flex;" in head, \
        "if this becomes a grid, the rule above should change with it"


def test_the_status_strip_has_no_disclosure_left():
    """Reported twice. First on Home, where a More/Less button appeared with
    nothing to reveal because `statusOpen` was module state shared by every
    view; then "remove this button across the whole terminal".

    The clamp goes with the button and that is what keeps it honest. A clipped
    row with no control left is the one arrangement that can hide a reading for
    good. Measured at 1512px across Options, Earnings, Investing, Chart and
    Overview: every strip is one row and 29px with the clamp removed, which is
    the height it had with it -- so on a desktop nothing about the sizing
    changed.

    The cost lands on a narrow window and is stated rather than hidden: at
    633px the Options strip is seven parts over five rows, 152px. It wraps
    instead of clipping."""
    fn = APP.split("function setStatus(parts) {", 1)[1].split("\nfunction ", 1)[0]
    for gone in ("sl-more", "data-sl-more", "statusOpen", "is-open", "disclose"):
        assert gone not in fn, gone
    assert "addEventListener" not in fn, "nothing on this strip is clickable now"

    # And the rules are deleted rather than left dark.
    for gone in (".sl-more", ".statusline.is-open", ".sl-plain"):
        assert gone not in NO_COMMENTS, gone

    block = NO_COMMENTS[NO_COMMENTS.index(".sl-parts {"):]
    block = block[:block.index("}")]
    assert "max-height" not in block, "the clamp is what the button existed to lift"
    assert "overflow: hidden" not in block, "and clipping is what it would hide"
    assert "flex-wrap: wrap;" in block, "so it wraps rather than clipping"

    # No caller is still asking for a disclosure that does not exist.
    assert "disclose" not in APP.split("function updateStatus()", 1)[1][:4000]


def test_the_status_strip_does_not_list_the_expiries():
    """"Remove this, unnecessary."

    It printed all four dates -- "Expiries: 2026-09-28, 2026-10-09,
    2026-10-23, 2026-11-20" -- 58 characters, comfortably the longest thing on
    the strip. Every one of them is already a row of the at-the-money greeks
    table on the same tab, and each idea card names its own expiry.

    It cost the most, too. With the clamp gone the strip wraps on a narrow
    window, and this part was most of the wrapping: measured at 771px on
    Options, three rows and 121px before, two rows and 80px after. Desktop was
    one row either way."""
    # Comments stripped first. The first version of this failed on the comment
    # I had just written explaining the removal -- the rationale for taking
    # something out names the thing taken out, so a contract that reads the raw
    # file cannot tell the two apart. Same lesson as tests/test_chart_dock_empty.py.
    code = re.sub(r"/\*.*?\*/", " ", APP, flags=re.S)
    code = re.sub(r"(?<!:)//[^\n]*", " ", code)
    fn = code.split("function updateStatus()", 1)[1].split("\nfunction ", 1)[0]
    assert "Expiries:" not in fn
    assert "(d.expiries || {}).used" not in fn
    # The verdict beside it stays: it is the one swing-only reading on the
    # strip that is a summary rather than a list.
    assert "Verdict: ${esc(cap((d.verdict || {}).stance)" in fn


def test_the_header_logo_blinks_everywhere_except_home():
    """The home page's 64px mark blinks on a 6s clock; the header's did not, so
    leaving Home stopped the terminal's one piece of life.

    Same keyframes and the same clock rather than a second set: two marks
    blinking to two timings drift apart the first time either is retimed.

    Not on Home, because the big one is already blinking on that screen and two
    apertures closing half a second apart reads as a rendering fault."""
    assert 'body:not([data-view="home"]) .brand-mark-eye {' in NO_COMMENTS
    assert 'body:not([data-view="home"]) .brand-mark-line {' in NO_COMMENTS

    eye = NO_COMMENTS[NO_COMMENTS.index('body:not([data-view="home"]) .brand-mark-eye {'):]
    eye = eye[:eye.index("}")]
    assert "eye-blink 6s" in eye, "the same keyframes and clock as .home-logo-eye"
    assert "transform-box: fill-box;" in eye, \
        "without it the lid closes on the viewport's centre and the mark slides"

    line = NO_COMMENTS[NO_COMMENTS.index('body:not([data-view="home"]) .brand-mark-line {'):]
    line = line[:line.index("}")]
    assert "line-redraw 6s" in line and "stroke-dasharray: 100;" in line

    # The gate has to be published, or the selector never matches -- and it
    # has to be published in the markup too. `:not([data-view="home"])`
    # matches an element carrying no such attribute at all, so before
    # switchView had run once the header blinked against the home logo it is
    # meant to defer to. Measured on load: animationName was "eye-blink".
    assert "document.body.dataset.view = view;" in APP
    assert '<body data-view="home">' in HTML, \
        "an absent attribute is not the home page to :not(), it is every page"

    # The markup the selectors need.
    assert 'class="brand-mark-eye"' in HTML
    assert 'class="brand-mark-line"' in HTML and 'pathLength="100"' in HTML

    # Decorative, so it goes with the rest under reduced motion. The file has
    # several of these blocks; the one that matters is the one already
    # switching off the home mark, because these share its keyframes.
    blocks = [b for b in NO_COMMENTS.split("@media (prefers-reduced-motion: reduce) {")[1:]
              if ".home-logo-eye," in b[:b.index("}")]]
    assert len(blocks) == 1, "the home mark's guard moved or was duplicated"
    rm = blocks[0][:blocks[0].index("}")]
    assert ".brand-mark-eye," in rm and ".brand-mark-line," in rm


def test_the_chart_toolbar_has_a_phone_drawer_and_a_desktop_that_ignores_it():
    """Measured at 375x812 on the Charting tab: nineteen buttons wrapping to
    six rows, 227px of toolbar above a chart that got 443. More than a third
    of the screen was controls, which is the "mobile chart controls create
    unusable layouts" report.

    Inline now: the range pills, the interval, Line/Candles, Reset zoom. In
    the drawer: Fibs, Trends, Indicators, the study menus, Panes, Colours --
    the set you open, use once and close. Re-measured: 141px over three rows
    closed, 227px and twenty buttons open, and 54px on a desktop, unchanged.
    """
    fn = APP.split("function wsToolbar() {", 1)[1].split("\nfunction ", 1)[0]
    assert 'class="ws-tools"' in fn
    assert "data-ws-tools" in fn
    # Two wrappers, because the tool groups are not contiguous: Panes and
    # Colours sit after the pills, and reordering them would have changed the
    # desktop to fix the phone.
    assert fn.count('<div class="ws-tools">') == 2

    # State survives the rebuild. The toolbar is replaced wholesale on every
    # menu toggle, so a class on the element alone would be thrown away.
    assert "let wsToolsOpen = false;" in APP
    assert "wsToolsOpen ? ' tools-open' : ''" in fn

    # `display: contents` is what makes this free above the breakpoint: the
    # wrapper stops generating a box and its children go back to being flex
    # items of the toolbar.
    # Leading newline, or this matches the tail of
    # `.ws-toolbar.tools-open .ws-tools { display: contents; }` in the phone
    # block and passes while the desktop rule says something else entirely.
    # A mutation to `display: flex` survived the bare substring.
    assert "\n.ws-tools { display: contents; }" in NO_COMMENTS
    assert "\n.ws-tools-btn { display: none; }" in NO_COMMENTS
    phone = phone_block_with(NO_COMMENTS, ".ws-tools-btn")
    assert ".ws-tools { display: none; }" in phone
    assert ".ws-toolbar.tools-open .ws-tools { display: contents; }" in phone
    # A flexible spacer on a wrapping row is a row of its own, and it was one
    # of the six.
    assert ".ws-toolbar-gap { display: none; }" in phone


def test_no_panel_is_capped_into_a_nested_scroll_container():
    """Reported as "scrolling up and down is messed up", and it was.

    `.grid.c2 > .panel:not(.span2):not(:has(svg.chart)):not(:has(.chart-controls))`
    carried `max-height: 640px; overflow-y: auto` to make two-up columns end at
    the same place. `.panel` also carries `overflow-x: auto` for wide tables,
    and a box with one axis scrollable and the other `visible` computes the
    visible axis to `auto` — so the cap made those panels vertical scroll
    containers as well. Scrolling the page with the pointer over one scrolled
    the panel instead, stopped, then chained to the document.

    Measured on Investing at 720px and again at 1400px: "Long-term view"
    clientHeight 638 of scrollHeight 754, "Valuation vs its own history" 638 of
    850 — 116px and 212px behind an inner scrollbar on a page that already
    scrolls. Zero after removing it, at both widths.

    The phone escape hatch had never worked: `.grid.c2 > .panel:not(.span2)`
    inside `@media (max-width: 860px)` is four classes against the capping
    selector's six, and a media query adds no specificity.
    """
    for block in _blocks():
        selector, body = block[0].strip(), block[1]
        if ".panel" not in selector:
            continue
        if "max-height" in body and "overflow-y: auto" in body:
            raise AssertionError(
                "a panel with both a max-height and overflow-y:auto is a nested "
                "scroll container: %s" % selector)


def test_the_two_up_cap_is_gone_rather_than_narrowed():
    """Kept as a comment recording why, so it does not get reintroduced as a
    fix for uneven columns. `align-items: start` handles those, and every panel
    with a heading is collapsible — which is a better answer to "this panel is
    long" than a scroll box, and did not exist when the cap was written."""
    assert ":not(:has(svg.chart))" not in NO_COMMENTS, \
        "the capping selector is back"
    assert "max-height: 640px" not in NO_COMMENTS
    # The reasoning survives in the source.
    assert "swallowed the wheel" in CSS


# ------------------------------------------------- one rule per thing


def test_the_panel_is_declared_once():
    """It was declared five times at top level, and the duplication was not
    harmless. With equal specificity the last declaration won, which killed
    three things their authors meant to happen: the scroll shadows, the 640px
    phone padding, and any hope of predicting a panel's box by reading one
    rule. Two paddings and three border-radii were declared; one of each
    applied."""
    assert len(re.findall(r'^\.panel \{', NO_COMMENTS, re.M)) == 1


def test_the_panel_sets_background_color_not_the_shorthand():
    """`background: var(--surface)` is a SHORTHAND and resets every background-*
    longhand. A later .panel rule used it, so background-image, -repeat, -size,
    -position and -attachment all reverted to their defaults and the scroll
    shadows were dead. Measured on a live panel: `background-image: none`,
    `background-repeat: repeat`, `background-size: auto`."""
    rule = NO_COMMENTS[NO_COMMENTS.index("\n.panel {"):]
    rule = rule[:rule.index("}")]
    assert "background-color: var(--surface)" in rule
    assert "background:" not in rule, "the shorthand resets the gradients below it"
    assert "background-image:" in rule and "linear-gradient" in rule


def test_the_chrome_height_has_exactly_one_publisher():
    """--chrome-h is owned by wsSyncChromeHeight, and only it.

    An audit pass added a second publisher in trackTopbarHeight, on the strength
    of reading `var(--chrome-h, 132px)` in the stylesheet, finding no CSS
    declaration, and reading the property off documentElement while a different
    view was active. All three observations were true and the conclusion was
    false: wsSyncChromeHeight sets it, from the chart VIEW's own offset, and
    only while that view is active, which is the only place the CSS uses it.

    Measuring from `main` instead comes out 24px short, because main carries
    24px of padding above its first child -- that is recorded in
    wsSyncChromeHeight's own comment, from when it was measured that way. So a
    second publisher is not a redundancy, it is a wrong number racing a right
    one on every resize.
    """
    assert APP.count("setProperty('--chrome-h'") == 1
    owner = APP.split("function wsSyncChromeHeight() {", 1)[1].split("\n}", 1)[0]
    assert "setProperty('--chrome-h'" in owner
    assert "view.getBoundingClientRect().top" in owner, "the view's offset, not main's"
    assert "classList.contains('active')" in owner, "only while that view is up"


def test_every_css_variable_used_is_declared():
    """`--bg-hover` was reached for by three rules and never declared, so all
    three silently took their fallback and the hover wash did not follow the
    theme. `--chrome-h` was the same fault with a layout consequence.

    Variables set from JS are declared there, so they are exempt by name."""
    # Declarations found ANYWHERE, not anchored to the start of a line, and read
    # from the comment-stripped source. Both matter: `.p-regular { --ses-hue:
    # var(--s1); }` is a single-line rule, and `var(--bg)` appears only inside a
    # comment describing a bug. An earlier version of this check reported five
    # false positives for exactly those two reasons.
    declared = set(re.findall(r'(--[a-z0-9-]+)\s*:', NO_COMMENTS))
    # Variables JS sets, either inline in a template or via setProperty.
    from_js = (set(re.findall(r'(--[a-z0-9-]+)\s*:', APP))
               | set(re.findall(r"setProperty\('(--[a-z0-9-]+)'", APP)))
    used = set(re.findall(r'var\((--[a-z0-9-]+)', NO_COMMENTS))
    missing = sorted(used - declared - from_js)
    assert not missing, "used but never declared: %s" % missing


# ------------------------------------------------------- resizing Pulse


def test_the_chat_width_has_one_source():
    """There were three numbers for one panel: it was 382px wide, main reserved
    420px and the legal footer reserved 400px, so the page held a 38px strip of
    nothing open beside an already-narrow panel. Everything reads --chat-w."""
    assert "--chat-w: 382px;" in CSS
    block = NO_COMMENTS[NO_COMMENTS.index("aside#chat {"):]
    block = block[:block.index("}")]
    assert "width: var(--chat-w)" in block
    for hardcoded in ("margin-right: 420px", "padding-right: 400px"):
        assert hardcoded not in NO_COMMENTS, hardcoded


def test_the_cover_override_sits_after_the_rule_it_overrides():
    """`body.chat-open main` and `body.chat-full main` are both (0,1,2), so
    source order is the whole of it. Placed with the panel's own styles the
    override sat ~3,900 lines earlier and lost silently: at full cover main
    still reserved the panel's full width and rendered 46px wide."""
    split = NO_COMMENTS.index("body.chat-open main { padding-right: var(--space-5)")
    cover = NO_COMMENTS.index("body.chat-full main,")
    assert cover > split, "the override has to come after what it overrides"


def test_the_split_has_a_minimum_for_both_panes():
    """The trigger was a fraction of the window (0.92) and left a dead band: at
    1153px, dragging to 1057 gave the page an 85px sliver, too narrow to read
    and not covering either. Stated as the page's floor so it holds at any
    window size."""
    assert "const CHAT_MIN_PAGE = 240;" in APP
    assert "window.innerWidth - w < CHAT_MIN_PAGE" in APP
    assert "CHAT_FULL_AT" not in APP, "the fraction is gone, not shadowed"


def test_a_zero_width_main_is_never_reserved():
    """Every chart measures its host before building, so a zero-width main
    resolves them all to 0 and the window has to be resized to recover. That is
    what the cover mode exists to prevent."""
    assert "body.chat-full main," in NO_COMMENTS
    block = NO_COMMENTS[NO_COMMENTS.index("body.chat-full main,"):]
    block = block[:block.index("}")]
    assert "margin-right: 0" in block


def test_the_grip_is_reachable_without_a_mouse():
    """A 10px drag target is not an input method for everyone."""
    assert 'role="separator"' in HTML and 'id="chat-grip"' in HTML
    assert 'aria-orientation="vertical"' in HTML
    fn = APP.split("function installChatResize() {", 1)[1].split("\nfunction ", 1)[0]
    for key in ("ArrowLeft", "ArrowRight", "Home", "End"):
        assert key in fn, key
    # And the value is announced, not just changed.
    assert "aria-valuenow" in APP


def test_the_drag_survives_leaving_the_handle():
    """Ten pixels is narrow enough that a fast drag leaves it. Without pointer
    capture the panel stops following, which reads as a sticky handle."""
    fn = APP.split("function installChatResize() {", 1)[1].split("\nfunction ", 1)[0]
    assert "setPointerCapture" in fn and "releasePointerCapture" in fn


def test_a_shrinking_window_reclamps_without_forgetting_the_choice():
    """A stored width wider than the window puts the panel off-screen and makes
    the page unreachable. Re-clamped transiently, so a temporarily narrow window
    does not overwrite what the reader chose."""
    fn = APP.split("function installChatResize() {", 1)[1].split("\nfunction ", 1)[0]
    assert "addEventListener('resize'" in fn
    assert "{ transient: true }" in fn
