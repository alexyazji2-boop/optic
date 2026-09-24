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


# --------------------------------------------- one family, one corner


def _no_comments(css):
    """Comments cannot vouch for code. A note explaining that `.pill` used to
    carry --r-ctl contains the string `--r-ctl`, and a check that greps the
    raw file finds it and passes on the strength of its own apology."""
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _declared(css):
    """(selector, property, media-context) -> every value declared for it.

    Media context matters: a responsive override is a second value on purpose
    and must not be read as a conflict. @media adds no specificity, which is
    why a rule inside one can still lose to a plain rule later in the file --
    but that is a different bug, and tests/test_phone_workspace.py owns it."""
    out = {}
    stack = []
    for m in re.finditer(r"@media([^{]*)\{|([^{}@]+)\{([^{}]*)\}|\}", css):
        if m.group(1) is not None:
            stack.append(m.group(1).strip())
        elif m.group(2) is None:
            if stack:
                stack.pop()
        else:
            sel, body = m.group(2), m.group(3)
            hit = re.search(r"(?:^|;)\s*border-radius\s*:\s*([^;]+)", body)
            if not hit:
                continue
            for one in sel.split(","):
                one = re.sub(r"\s+", " ", one.strip())
                if one:
                    out.setdefault((one, tuple(stack)), []).append(hit.group(1).strip())
    return out


# Base-then-override layerings that exist on purpose, frozen so that a new one
# has to be looked at rather than absorbed. Each sets a shared value on a group
# and then a specific rule restates it for one member -- legitimate, and also
# exactly the shape that put --r-ctl on `.pill`, which is why the set is closed
# rather than the pattern being allowed.
#
# Left alone rather than flattened: the first value in each is live for the
# other selectors sharing that grouped rule, so deleting the declaration would
# move `.search input` to fix `.btn`.
KNOWN_LAYERED = {
    (".btn", "var(--r-md)", "var(--r-ctl)"),
    (".ws-menu-btn", "var(--r-md)", "var(--r-ctl)"),
    (".tile", "var(--r-md)", "var(--r-lg)"),
    (".hm-block", "var(--r-md)", "var(--r-lg)"),
}


def test_no_selector_is_given_two_different_radii_at_the_same_width():
    """`.pill` was given --r-pill in its own rule and then --r-ctl by a later
    sweep that listed it beside the buttons. The sweep's own comment says the
    curve belongs on "panels, buttons, pills" -- and 10px on a 29px control is
    a rounded rectangle, so the rule that meant to keep pills curved was the
    one uncurving them.

    Nothing in the file reads as wrong: both declarations are tokenised, both
    are defensible alone, and only the order decides. That is why this is a
    test and not a review comment."""
    bad = {}
    for (sel, media), vals in _declared(_no_comments(CSS)).items():
        if len(set(vals)) < 2:
            continue
        # A later multi-corner value is a shape, not a disagreement: a menu
        # panel square against the control above it and rounded below is one
        # element, drawn correctly.
        if len(_corners(vals[-1])) > 1:
            continue
        if (sel, vals[0], vals[-1]) in KNOWN_LAYERED:
            continue
        bad[(sel, media)] = vals
    assert not bad, "\n".join(
        "  {}{}: {}".format(sel, "  @media " + " ".join(media) if media else "",
                            " then ".join(vals))
        for (sel, media), vals in bad.items())


# A family is a set of components a reader is meant to read as the same thing.
# Membership is by what it is, not by what it is called: `.sec-chip` is a chip
# because it sits in a row of chips, and that is the whole argument for it
# having their corner.
FAMILIES = {
    "pill":   [".chip", ".pill", ".scan-pill", ".wd-chip", ".sec-chip"],
    "button": [".btn", ".icon-btn", ".ws-menu-btn"],
    "card":   [".panel", ".home-card", ".tile"],
}


def _resolved(cls, css):
    """The radius a class ends up with: last unconditional declaration wins.

    Only rules whose selector is exactly this class, which is the case for all
    of these and keeps the resolver honest -- a real cascade needs specificity
    and this does not pretend to be one."""
    vals = [v[-1] for (sel, media), v in _declared(css).items()
            if sel == cls and not media]
    assert vals, "no unconditional radius for {}".format(cls)
    return vals[-1]


def test_every_member_of_a_family_is_drawn_with_the_same_corner():
    """Measured in the browser before this: of five chips, `.chip`,
    `.scan-pill` and `.wd-chip` rendered at 999px while `.pill` rendered at
    10px and `.sec-chip` at 8px. Of three buttons, `.icon-btn` was two pixels
    squarer than the `.btn` in the same bar.

    Each on its own is a detail nobody would file. Together they are what
    "incohesive component system" means: things with one job and one name
    drawn three ways, so the eye reads them as three components."""
    stripped = _no_comments(CSS)
    for family, members in FAMILIES.items():
        got = {m: _resolved(m, stripped) for m in members}
        assert len(set(got.values())) == 1, \
            "the {} family is drawn {} ways: {}".format(
                family, len(set(got.values())),
                ", ".join("{} {}".format(k, v) for k, v in sorted(got.items())))


def test_each_family_sits_on_the_step_the_scale_named_for_it():
    """Coherence alone would be satisfied by drawing every pill at 4px. The
    scale already says which step each family belongs on, in the comment beside
    the token, so the families are pinned to those rather than to each other."""
    stripped = _no_comments(CSS)
    assert _resolved(".chip", stripped) == "var(--r-pill)"
    assert _resolved(".btn", stripped) == "var(--r-ctl)"
    assert _resolved(".panel", stripped) == "var(--r-lg)"
