"""A figure centred in its own tile, and a label that starts like a sentence.

Reported by eye on the S&P 500 instrument page: "7,688.11" sat visibly right of
centre in its tile while "53" and "-1.4%" beside it looked fine. That pattern --
only the long values wrong -- is what made it read as a rendering glitch rather
than a spacing one.

Measured at a 134px tile: the value is set at --t-d3 and "7,704.28" is 116px
wide, against an 88px content box left by --space-5 padding on each side.
`text-align: center` cannot centre a line wider than its box: the line box
anchors at the content edge and the whole overflow goes one way. The figure sat
14px right of the tile's centre and 4px past its right edge.

After: every value at offCenter 0 and nothing spilling, at 136px, 143px and
202px tiles.

Also here because the same screenshot showed it: the kicker above the title
rendered the instrument catalogue's own `group` field straight out, so the page
opened with the word "equity" in lower case.
"""

from __future__ import annotations

import re

APP = open("static/app.js", encoding="utf-8").read()
CSS = open("static/styles.css", encoding="utf-8").read()


def _css_code():
    return re.sub(r"/\*.*?\*/", " ", CSS, flags=re.S)


def _js_code():
    src = re.sub(r"/\*.*?\*/", " ", APP, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", " ", src)


def _rule(selector, css):
    m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    return m.group(1) if m else None


def test_the_figure_gets_the_whole_tile_to_centre_in():
    """The fix is not more padding or a smaller font: it is letting the one
    element that overflows use the width the tile already has."""
    body = _rule(".tile .value", _css_code())
    assert body, ".tile .value is gone"
    assert "margin-inline" in body, \
        "without reclaiming the side padding a long figure cannot centre"
    assert "var(--space-3)" in body, \
        "the reclaim has to match the tile's own padding step"


def test_the_tile_padding_matches_what_the_value_reclaims():
    """These two numbers are one number. If the tile's padding changes and the
    value's negative margin does not, the figure goes off-centre the other
    way -- and only on the long values again, which is the hardest version of
    this bug to notice."""
    tile = _rule(".tile", _css_code())
    assert tile
    pad = re.search(r"padding:\s*([^;]+)", tile).group(1).split()
    assert len(pad) == 2, "expected vertical and horizontal padding: {}".format(pad)
    horizontal = pad[1]
    value = _rule(".tile .value", _css_code())
    reclaim = re.search(r"margin-inline:\s*calc\(-1 \* (var\(--[a-z0-9-]+\))\)", value)
    assert reclaim, "the reclaim must be a negative multiple of a spacing token"
    assert reclaim.group(1) == horizontal, \
        "tile pads {} but the value reclaims {}".format(horizontal, reclaim.group(1))


def test_the_tile_still_centres_everything_else():
    tile = _rule(".tile", _css_code())
    assert "text-align: center" in tile


def test_the_instrument_kicker_is_not_printed_in_lower_case():
    """`group` comes out of the instrument catalogue as "equity", "rates",
    "fx". It is the first word on the page."""
    code = _js_code()
    kicker = re.search(r'<div class="weekly-kicker">\$\{esc\(([^)]*\))\)\}</div>', code)
    assert kicker, "the instrument kicker changed shape"
    assert kicker.group(1).startswith("cap("), \
        "the catalogue's own casing reaches the page: " + kicker.group(1)


def test_the_rsi_note_reads_as_a_sentence():
    """Three hand-written strings under the RSI figure, all lower case."""
    code = _js_code()
    block = code[code.index("stat('RSI'"):][:260]
    for word in ("Overbought", "Oversold", "Mid-range"):
        assert word in block, word + " should start capitalised"
    for word in ("'overbought", "'oversold", "'mid-range"):
        assert word not in block, word + " is still lower case"
