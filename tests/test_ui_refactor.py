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


def test_the_phone_tab_strip_keeps_its_own_overflow_declaration():
    """This looks like a duplicate of the 1280px block and is not.

    `nav.tabs-group { overflow: visible }` fires unconditionally further down
    the file so the section dropdowns can escape the strip, and being later it
    wins. Removing this line as redundant pushed the two right-hand tabs 205px
    outside the document — 375px viewport against a 580px scrollWidth — and put
    the horizontal scrollbar back.
    """
    phone = NO_COMMENTS[NO_COMMENTS.index("@media (max-width: 559px)"):]
    phone = phone[:phone.index("\n}\n")]
    strip = phone[phone.index("nav.tabs,"):]
    strip = strip[:strip.index("}")]
    assert "overflow-x: auto;" in strip
    assert "flex-wrap: nowrap;" in strip


def test_the_phone_dropdown_cannot_overhang_the_screen():
    """`left: 0` plus `min-width: 190px` on a nav item sitting at x=190 ran the
    menu to 380px on a 375px screen, which was the entire horizontal scroll.
    Fixed positioning pinned to both edges removes the arithmetic."""
    phone = CSS[CSS.index("@media (max-width: 559px)"):]
    menu = phone[phone.index(".nav-menu {"):]
    menu = menu[:menu.index("}")]
    assert "position: fixed;" in menu
    assert "left: var(--space-3);" in menu and "right: var(--space-3);" in menu


def test_the_phone_dropdown_opens_below_the_bar_not_across_it():
    """`top: auto` on a fixed box uses its static position, which put the menu
    over the tab strip and hid the section you were choosing from. A percentage
    is no good either — on a fixed box it resolves against the viewport — so the
    bar's measured height is the anchor."""
    phone = CSS[CSS.index("@media (max-width: 559px)"):]
    menu = phone[phone.index(".nav-menu {"):]
    menu = menu[:menu.index("}")]
    assert "var(--topbar-h" in menu
    # ...and something has to actually set it, with a fallback in the CSS for
    # browsers that never run the observer.
    assert "setProperty('--topbar-h'" in APP
    assert "ResizeObserver" in APP[APP.index("function trackTopbarHeight"):][:1200]


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
    phone = CSS[CSS.index("@media (max-width: 559px)"):]
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


def test_the_status_strip_is_clamped_to_one_row():
    """Seven items wrapping to five rows, 130px above the fold, measured on the
    Options tab at 727px. What was in them is the argument: the price, the
    change, the verdict and the market status were each already on that screen
    in a larger, better-labelled form, so the strip was the fifth copy of the
    price and the second copy of the verdict."""
    assert ".sl-parts {" in NO_COMMENTS
    parts = NO_COMMENTS[NO_COMMENTS.index(".sl-parts {"):]
    parts = parts[:parts.index("}")]
    assert "max-height: 1.6em;" in parts, "one line of the strip's own type"
    assert "overflow: hidden;" in parts
    assert ".statusline.is-open .sl-parts { max-height: none; overflow: visible; }" \
        in NO_COMMENTS


def test_the_status_strip_does_not_wrap_around_its_own_toggle():
    """The strip clips and .sl-parts wraps inside it. If the strip itself
    wrapped, More would drop onto a second line — restoring the height the
    clamp exists to remove."""
    block = NO_COMMENTS[NO_COMMENTS.index(".statusline {"):]
    block = block[:block.index("}")]
    assert "flex-wrap: nowrap;" in block


def test_the_status_toggle_only_appears_when_there_is_more_to_see():
    """A "more" that reveals nothing is the same fault as the session summary's
    render-time fit check. Overflow is measured on the inner row, because the
    strip is what clips and its own scrollHeight already equals its
    clientHeight."""
    fn = APP.split("function setStatus(parts) {", 1)[1].split("\nfunction ", 1)[0]
    assert "inner.scrollHeight > inner.clientHeight + 1 || statusOpen" in fn
    assert "hidden" in fn, "the button ships hidden and is revealed on measurement"


def test_the_status_open_state_survives_a_repaint():
    """updateStatus runs on every view change, every poll and every repaint, and
    setStatus replaces innerHTML. State in the DOM alone would re-collapse the
    strip under the reader."""
    assert "let statusOpen = false;" in APP
    fn = APP.split("function setStatus(parts) {", 1)[1].split("\nfunction ", 1)[0]
    assert "host.classList.toggle('is-open', statusOpen);" in fn


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
