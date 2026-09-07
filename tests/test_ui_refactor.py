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
    """`.grid.c2 > .panel:not(:has(.chart-controls))` caps the height of every
    non-chart panel in a two-up row. A first pass at removing dead classes
    deleted it on the strength of a name that only ever appeared as an
    exclusion — where a dead class makes the condition vacuously true and
    leaves the subject of the selector completely live."""
    # The full selector, not a prefix of it: a shorter form of this also appears
    # inside the 1080px block, so matching the prefix passed even with the rule
    # under test deleted.
    assert (".grid.c2 > .panel:not(.span2):not(:has(svg.chart))"
            ":not(:has(.chart-controls))") in NO_COMMENTS


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
