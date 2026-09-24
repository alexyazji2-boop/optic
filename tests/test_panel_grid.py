"""No panel sits alone in a two-column row.

Reported on Investing: a stack of collapsed title bars at half width with
nothing beside them, and under it a 743px panel in one column against 577px of
nothing. Measured at 1182px, the dead space on that tab was about 466,000
square pixels; Financials had 628,000 and Earnings 571,000.

Two causes, and the second is why the rule that already existed never fired.

A collapsed panel is a title bar. It was taking a grid column, so a closed
panel could never pair with anything and the span2 panels above and below it
could not either.

And `.grid.c2 > *:last-child:nth-child(odd)` -- the rule written for exactly
this, with its own measured comment -- counts *children*, not columns. Two
things break it. Panels switched off by Simple mode keep their `hidden`
attribute and their place in the child order, so `:last-child` was matching an
invisible panel. And a single `.span-all` or `.span2` anywhere in the grid puts
every later panel's parity one out, which no amount of counting fixes.

So the replacement does not count. An element spans the row when it starts one
-- it is first, or it follows something full-width -- and nothing can follow it
in that row, because the next thing is full-width or there is no next thing.

Measured after, at 1182px: every view that has panels reports zero dead space.
Investing, Options, Financials, Earnings, Markets, Indices, Read, Overview and
Positions.
"""

from __future__ import annotations

import re

CSS = open("static/styles.css", encoding="utf-8").read()


def _code():
    return re.sub(r"/\*.*?\*/", " ", CSS, flags=re.S)


def _rules():
    """Every (selector, body) pair in the stylesheet."""
    return [(m.group(1).strip(), m.group(2))
            for m in re.finditer(r"([^{}@]+)\{([^{}]*)\}", _code())]


def _rule(selector_fragment):
    """The first rule whose selector contains this fragment."""
    for sel, body in _rules():
        if selector_fragment in sel:
            return sel, body
    return None, None


def test_a_collapsed_panel_does_not_hold_a_column():
    """Every rule mentioning it, not the first one found. An earlier version of
    this walked the file looking for one and stopped on a rule about something
    else entirely -- so deleting the real rule left it green."""
    # The closed panel must be the SUBJECT of the rule, not a sibling in it.
    # `.panel.is-closed + *` contains the same substring and sets the same
    # property, so a substring check matched the wrong rule and stayed green
    # when the real one was deleted.
    subject = re.compile(r"\.panel\.is-closed\s*(?:,|$)")
    spanning = [
        (sel, body) for sel, body in _rules()
        if any(subject.search(part.strip()) for part in sel.split(","))
        and "grid-column: 1 / -1" in body
    ]
    assert spanning, "a closed panel is a title bar and should not take half a row"
    assert any(".grid.c2" in sel for sel, _ in spanning), \
        "the rule has to apply inside the two-column grids"


def test_the_lone_panel_rule_does_not_count_children():
    """Counting is what broke it: hidden panels keep their place in the child
    order, and one full-width sibling shifts every later parity."""
    code = _code()
    assert ":has(+ .span-all)" in code and ":has(+ .span2)" in code, \
        "the rule has to ask what follows, not what number it is"
    assert ".span-all + *" in code and ".span2 + *" in code, \
        "and what precedes it"


def test_it_still_ignores_panels_that_are_switched_off():
    """`hidden` is how Simple mode and the panel chooser remove a panel, and
    those panels keep their place in the child order."""
    # In the generalised rule specifically. The parity rule above it carries
    # the same fragment, so a file-wide check passes with this one gutted.
    sel, body = _rule(":has(+ .span-all)")
    assert sel, "the generalised rule is gone"
    assert "of :not([hidden])" in sel, \
        "a hidden panel must not count as the last one"


def test_the_original_parity_rule_is_kept_as_well():
    """Where nothing is hidden and nothing spans, the two agree. Keeping it
    means a browser without `:has` or `of S` still gets the old behaviour
    rather than none."""
    sel, body = _rule("*:last-child:nth-child(odd)")
    assert body and "grid-column: 1 / -1" in body
