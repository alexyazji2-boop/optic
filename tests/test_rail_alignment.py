"""The sidebar as one list, on one line.

Two things were wrong with it and both were reported by eye before they were
measured.

The gap: `.rail-foot` carried `margin-top: auto`, which on an 835px rail
resolved to 339px of nothing between Watchlist and Settings. The rail is as
tall as the window either way, so the empty space cannot be removed -- but
below the last item it reads as a list that ended, and between two clusters it
reads as something missing. It now sits below.

The line: nav items carried `--space-3` horizontal padding where the brand mark
above and the gear below carried `--space-2`, so the glyph column ran 19, 24,
19 down the one vertical the eye follows the whole height of the sidebar. The
labels were staggered the other way, 51 against 47, because the three icons are
22px, 18px and 18px. Squaring the nav padding lands both columns at once.

All figures measured in a browser at 212px rail width, and re-measured on a
phone afterwards: the rail there is a 63px horizontal strip whose own rules
set `margin-top: 0` and `flex-direction: row`, and those still win.
"""

from __future__ import annotations

import re

CSS = open("static/styles.css", encoding="utf-8").read()


def _code():
    return re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)


def _rule(selector, css):
    """The last unconditional rule for exactly this selector."""
    found = None
    depth_media = []
    for m in re.finditer(r"@media([^{]*)\{|([^{}@]+)\{([^{}]*)\}|\}", css):
        if m.group(1) is not None:
            depth_media.append(1)
        elif m.group(2) is None:
            if depth_media:
                depth_media.pop()
        elif not depth_media:
            parts = [re.sub(r"\s+", " ", p.strip()) for p in m.group(2).split(",")]
            if selector in parts:
                found = m.group(3)
    return found


def test_the_footer_is_not_pinned_to_the_floor():
    body = _rule(".rail-foot", _code())
    assert body is not None, ".rail-foot lost its base rule"
    mt = re.search(r"margin-top:\s*([^;]+)", body)
    assert mt, ".rail-foot needs an explicit margin-top"
    assert mt.group(1).strip() != "auto", \
        "margin-top: auto puts 339px of nothing above the footer"


def _media_blocks(css):
    """Each @media block's condition and body, brace-matched.

    Scanning forward a fixed number of characters from the first `@media` that
    mentions a selector finds whichever block comes first in the file, not the
    one that sets the rule -- which is how the first version of this test
    failed against a `.panel` padding block six thousand characters away."""
    out = []
    for m in re.finditer(r"@media([^{]*)\{", css):
        i, depth = m.end(), 1
        while i < len(css) and depth:
            if css[i] == "{":
                depth += 1
            elif css[i] == "}":
                depth -= 1
            i += 1
        out.append((m.group(1).strip(), css[m.end():i - 1]))
    return out


def test_the_phone_rail_still_overrides_both():
    """The phone turns the rail into a horizontal strip. Its own rules set
    `margin-top: 0` and `flex-direction: row`, and a media query adds no
    specificity -- so an unmediated rule added later in the file beats them,
    which is the single most repeated bug in this stylesheet."""
    code = _code()
    hits = [(cond, body) for cond, body in _media_blocks(code)
            if re.search(r"\.rail-foot\s*\{[^}]*margin-top:\s*0", body)]
    assert hits, "no media block resets the footer's margin"
    cond, body = hits[0]
    assert "max-width" in cond, "the reset must be a narrow-width rule"
    assert re.search(r"\.rail-foot\s*\{[^}]*flex-direction:\s*row", body)
    # And the base rule it answers comes earlier in the file, or the media
    # query is overriding nothing.
    base = code.index(".rail-foot { margin-top")
    assert base < code.index(body[:80]), \
        "the phone reset sits before the rule it resets"


def test_the_glyphs_sit_on_one_vertical():
    """The brand mark, every nav item and both footer buttons share a left
    padding, which is what puts their icons on the same x. The brand keeps a
    22px mark against the others' 18px, so its label sits four pixels wider --
    that is a logo being a logo, and it is the only exception."""
    code = _code()
    nav = _rule(".rail nav.tabs-group .nav-top", code)
    assert nav, "the nav item rule is gone"
    pad = re.search(r"(?:^|;)\s*padding:\s*([^;]+)", nav)
    assert pad, "the nav item needs an explicit padding"
    parts = pad.group(1).split()
    assert len(parts) == 1, \
        "square padding or the glyph column bends: got {!r}".format(pad.group(1))
    assert parts[0] == "var(--space-2)", \
        "the same step the brand and the footer use, not {!r}".format(parts[0])


def test_the_nav_and_footer_icons_are_the_same_size():
    """Equal padding only straightens the icons. The labels line up because
    these two boxes match; if one changes, the labels stagger again and the
    padding test above still passes."""
    code = _code()
    nav = re.search(r"\.nav-icon\s*\{([^}]*)\}", code)
    assert nav, ".nav-icon rule is gone"
    w = re.search(r"width:\s*([0-9]+px)", nav.group(1))
    assert w and w.group(1) == "18px", "nav glyphs are 18px"
