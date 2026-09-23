"""The phone, and the cascade trap that kept breaking it.

Four separate rules lost the same way in one session: a responsive override
written inside `@media (max-width: ...)`, and an unmediated rule for the same
selector and property sitting LATER in the file. A media query adds no
specificity, so at equal specificity the later rule wins and every
declaration in the block is silently discarded. Nothing errors. The symptom
is a phone layout that looks like nobody wrote one.

What it cost, measured on AAPL at 375x812:

  .ws-wrail        fifteen widget buttons as a 338x611 column under the
                   chart, because `.ws-wrail { flex-direction: column }` --
                   a restatement of the base rule, added as setup for an auto
                   margin -- undid the `max-width: 900px` block that turns the
                   rail into a row. That block had been dead on tablets too.
  .ws-menu         the toolbar dropdowns anchored to their own button with a
                   210px minimum, so Trends opened at x=172 and ran to 382.
  .ws-wrail-pulse  a row override discarded by the base rule below it.
  .rail nav...     the phone nav's `flex: 1 1 auto` discarded the same way.

`test_no_media_override_is_discarded_by_a_later_plain_rule` is the general
guard. It would have caught all four.
"""

from __future__ import annotations

import re

CSS = open("static/styles.css", encoding="utf-8").read()
# Comments blanked rather than deleted, so line numbers and source order
# survive for the ordering checks below.
CSS_CODE = re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), CSS, flags=re.S)


def _declarations():
    """(order, selector, property, media) for every declaration, in source
    order. `@supports` and `@keyframes` push a null context so they do not
    look like media queries and do not pop one on their closing brace."""
    out, order, stack, pos = [], 0, [], 0
    tok = re.compile(r"@(media|supports|keyframes|layer)([^{]*)\{|([^{}]+)\{([^{}]*)\}|\}")
    while pos < len(CSS_CODE):
        m = tok.search(CSS_CODE, pos)
        if not m:
            break
        pos = m.end()
        if m.group(1):
            stack.append(m.group(2).strip() if m.group(1) == "media" else None)
        elif m.group(3) is not None:
            media = next((x for x in reversed(stack) if x), None)
            sels = [x.strip() for x in m.group(3).split(",") if x.strip()]
            for prop in re.findall(r"([a-z-]+)\s*:", m.group(4)):
                for sel in sels:
                    order += 1
                    out.append((order, sel, prop, media))
        elif stack:
            stack.pop()
    return out


# Pairs that were already losing before this pass and were not introduced by
# it. Frozen rather than fixed: each needs its own measurement to say what the
# intended rendering is, and freezing the set is what stops a fifth appearing.
KNOWN = {
    (".hero", "font-size"),
    ("main", "padding"),
    ("body.chat-open main", "padding-right"),
}


def test_no_media_override_is_discarded_by_a_later_plain_rule():
    decls = _declarations()
    assert len(decls) > 5000, "the parser fell over; {} declarations".format(len(decls))
    by = {}
    for d in decls:
        by.setdefault((d[1], d[2]), []).append(d)
    dead = set()
    for key, lst in by.items():
        lst.sort()
        # The last unmediated declaration beats every media one before it. A
        # media declaration AFTER it is fine, which is how the two fixed here
        # are written.
        last_plain = max([x[0] for x in lst if x[3] is None], default=None)
        if last_plain is None:
            continue
        for order, sel, prop, media in lst:
            if media and "max-width" in media and order < last_plain:
                dead.add((sel, prop))
    assert dead == KNOWN, (
        "media overrides discarded by a later unmediated rule.\n"
        "  new: {}\n  fixed but still listed: {}".format(
            sorted(dead - KNOWN), sorted(KNOWN - dead)))


# ------------------------------------------------- the four, individually


def _phone_block(marker):
    i = CSS_CODE.index(marker)
    depth, j = 1, CSS_CODE.index("{", i) + 1
    while depth:
        o, c = CSS_CODE.find("{", j), CSS_CODE.find("}", j)
        if o != -1 and o < c:
            depth += 1
            j = o + 1
        else:
            depth -= 1
            j = c + 1
    return CSS_CODE[i:j]


def test_the_widget_rail_becomes_a_row_below_900():
    """Fifteen buttons at 39px is a 611px column. As a row it is one 58px
    strip. Measured after: 338x58 on a phone, 510x58 on a tablet."""
    block = _phone_block("@media (max-width: 900px) {\n  .ws-body")
    rule = block.split(".ws-wrail {", 1)[1]
    rule = rule[:rule.index("}")]
    assert "flex-direction: row" in rule
    assert "overflow-x: auto" in rule


def test_nothing_restates_the_widget_rails_direction_afterwards():
    """A `.ws-wrail { display: flex; flex-direction: column; }` was added
    below as setup for the Pulse button's auto margin. The base rule nine
    hundred lines up already said it, and being unmediated and later it undid
    the row for every width under 900px."""
    after = CSS_CODE.split("@media (max-width: 900px) {\n  .ws-body", 1)[1]
    plain = re.findall(r"\n\.ws-wrail\s*\{([^}]*)\}", after)
    for body in plain:
        assert "flex-direction" not in body, \
            "an unmediated .ws-wrail below the row block: {!r}".format(body.strip())


def test_the_toolbar_menus_are_pinned_to_the_toolbar_on_a_phone():
    """210px minimum from `left: 0` of their own button ran Trends off a
    375px screen. Measured after: all five open at 32..343."""
    # The override has to come after the two rules it overrides.
    pop_base = CSS_CODE.index(".ws-menu-pop {\n  position: absolute;")
    static = CSS_CODE.index(".ws-menu { position: static; }")
    relative = CSS_CODE.index(".ws-menu { position: relative; }")
    assert static > pop_base and static > relative, \
        "the phone rule must follow both unmediated rules it overrides"
    tail = CSS_CODE[static:static + 400]
    assert "left: var(--space-3)" in tail and "right: var(--space-3)" in tail
    assert "min-width: 0" in tail


def test_the_chart_gets_the_room_on_a_phone():
    """The plot was 180px of a 649px canvas with two 179px oscillator panes
    under it -- the price chart was the third-largest thing in its own
    workspace. Measured after: plot 310, panes 110."""
    plot = re.search(r"@media \(max-width: 559px\)[^@]*?\.ws-plot \{ min-height: (\d+)px", CSS_CODE, re.S)
    assert plot and int(plot.group(1)) >= 280, "the plot floor is back to the old 180"
    pane = re.search(r"\.ws-pane \{ max-height: (\d+)px", CSS_CODE)
    assert pane and int(pane.group(1)) <= 140


def test_the_toolbar_pill_rows_scroll_rather_than_overflow():
    """The interval ladder is eight pills totalling 412px in a 338px toolbar,
    so `1W` sat at x=359 to 408 and could not be tapped at all."""
    assert ".ws-toolbar .pills,\n  .ws-toolbar .seg {" in CSS_CODE
    rule = CSS_CODE.split(".ws-toolbar .pills,\n  .ws-toolbar .seg {", 1)[1]
    rule = rule[:rule.index("}")]
    assert "overflow-x: auto" in rule
    assert ".ws-toolbar .pill { flex: none; }" in CSS_CODE, \
        "shrinkable pills squash instead of scrolling"


def test_the_nav_caret_is_inline_on_a_phone():
    """The base rule pins it to `top; right` of the nav item, which was right
    for a full-width top bar. In a row of buttons sized to their label a 7x4px
    triangle at the top-right corner reads as a speck floating above the
    strip: measured at y=141 against a button spanning 135 to 179."""
    block = _phone_block("@media (max-width: 559px) {\n  .app {")
    rule = block.split(".rail nav.tabs-group .nav-caret {", 1)[1]
    rule = rule[:rule.index("}")]
    assert "position: static" in rule
    # And it has to flip when open, which is the one thing the glyph is for.
    assert ".rail nav.tabs-group .nav-item.open .nav-caret { transform: rotate(180deg); }" in block
