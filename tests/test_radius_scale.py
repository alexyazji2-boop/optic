"""Corner radius is a scale, not a value you pick per element.

Measured before this: 75 hardcoded radii against five tokens, and the two
most-drawn surfaces in the product were both bypassing the scale. `.panel`
rendered at 14px while `--r-lg`, whose own comment reads "panels", was 16px and
used by nothing that is a panel. `.btn` rendered at 10px against a `--r-md` of
8px. Anything wanting "rounder than a button, less round than a card" -- the
command palette, the section index, the home skeleton -- had no token to reach
for and invented 10px, 11px, 12px or 14px.

Two of those inventions were not even self-consistent. `.btn.primary` carried
`11px 10px 10px 10px` and `.cp` carried `14px 12px 12px 12px`: one corner
rounder than the other three, on the button the eye lands on most and on the
modal that opens in the middle of the screen. Nobody would defend either as a
decision, and nobody could see either as a bug.

This file is what makes the scale a contract rather than a suggestion.
"""

from __future__ import annotations

import re

CSS = open("static/styles.css", encoding="utf-8").read()


def _corners(decl):
    """A radius declaration as a list of corner values.

    `var(--r-pill, 999px)` is one corner, not two. Collapsing each var() to a
    single opaque token first is the difference between reading a fallback as a
    second corner and reading it as what it is."""
    return re.sub(r"var\([^)]*\)", "VAR", decl).split()

# Values allowed to appear bare, and the only reason any value is.
SUB_TOKEN = {"1px", "2px", "3px"}


def _tokens():
    root = CSS.split(":root {", 1)[1]
    root = root[:root.index("\n}")]
    return dict(re.findall(r"--(r-[a-z]+):\s*([0-9]+px)", root))


def test_the_scale_names_every_step_the_app_draws():
    """Six steps, because six is what it draws: marks, small controls,
    buttons, chrome, cards, pills."""
    t = _tokens()
    assert t == {"r-xs": "4px", "r-sm": "8px", "r-ctl": "10px",
                 "r-chrome": "12px", "r-md": "8px", "r-lg": "14px",
                 "r-pill": "999px"}, t


def test_the_card_token_is_the_radius_cards_are_drawn_at():
    """The fault that started this. A token named for panels has to be the
    number panels use, or it is decoration."""
    panel = CSS.split("\n.panel {", 1)[1]
    panel = panel[:panel.index("}")]
    assert "border-radius: var(--r-lg);" in panel
    assert _tokens()["r-lg"] == "14px"


def test_nothing_holds_a_bare_radius_of_four_pixels_or_more():
    """4px and up is a step on the scale and has a name. Below that it is a
    proportion of a 3-8px bar's own height, where rounding to --r-xs would turn
    a 3px fill into a lozenge."""
    bare = []
    for decl in re.findall(r"border-radius:([^;]+);", CSS):
        # Outside any var(), so a documented fallback inside one is not a bare
        # value -- the token is still what is being asked for.
        outside = re.sub(r"var\([^)]*\)", " ", decl)
        for value in re.findall(r"\b([0-9.]+px)\b", outside):
            if value not in SUB_TOKEN:
                bare.append(decl.strip())
    assert not bare, "bare radii outside the scale: {}".format(sorted(set(bare)))


def test_no_corner_is_rounder_than_its_neighbours_by_accident():
    """The `11px 10px 10px 10px` shape. A multi-value radius is legitimate when
    some corners are square -- a bar rounded only at the top, a segment rounded
    only on one end -- and is a typo when all four are set and they disagree."""
    for decl in re.findall(r"border-radius:([^;]+);", CSS):
        parts = _corners(decl)
        if len(parts) < 2:
            continue
        if any(p in ("0", "0px") for p in parts):
            continue                      # a deliberate shape, not four corners
        assert len(set(parts)) == 1, \
            "all four corners set and unequal: border-radius: {};".format(decl.strip())


def test_every_token_on_the_scale_earns_its_place():
    """A step nothing uses is a step that will drift. --r-md is the one
    survivor of a merge and is still on 52 selectors, which is why it is not
    removed in the same breath as adding two."""
    for name in _tokens():
        uses = CSS.count("var(--{})".format(name))
        assert uses >= 3, "{} is used {} times".format(name, uses)
