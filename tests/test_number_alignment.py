"""Figures centred, and sitting on one baseline.

Reported from a screenshot of the instrument stat row: `2,890.51` under `LAST`
ragged against `+1.10%` under `1 DAY`, in a row of six equal boxes. Two separate
faults were in that picture.

**Ragged horizontally.** The tiles were left-aligned, so six figures of six
different widths started at the same left edge and ended wherever they ended.
`font-variant-numeric: tabular-nums` is what makes centring safe here: the
digits are the same width, so a figure does not shift sideways as it ticks.

**Ragged vertically.** `FROM 52-WEEK HIGH` wraps to two lines and `RSI` does
not, and because the label sat directly above the value the values landed at two
different heights. Reserving the second line costs about 16px on the short
captions and buys one baseline across the row.

The fix also folded two `.tile` declarations 4,200 lines apart into one. The
second declared background, border and padding and therefore silently owned all
three, which is the last-declaration-wins trap this stylesheet has been caught
by more than once.
"""
from __future__ import annotations

import re

CSS = open("static/styles.css").read()


def _rule(selector: str) -> str:
    """The body of the first rule for `selector`, comments stripped."""
    start = CSS.index(selector + " {")
    body = CSS[start:CSS.index("}", start)]
    return re.sub(r"/\*.*?\*/", " ", body, flags=re.S)


# ------------------------------------------------------------------- tiles


def test_the_tile_is_declared_once():
    """Two declarations of one class is how the second silently won."""
    assert len(re.findall(r"^\.tile \{", CSS, flags=re.M)) == 1


def test_the_consolidated_tile_keeps_what_was_actually_rendering():
    """The later rule's values are the ones readers saw, so those are the ones
    that survive the merge: the flat surface and no border.

    The padding is no longer pinned here. --space-5 a side left an 88px content
    box in a 134px tile, and a price set at --t-d3 is 116px wide -- so the
    figure could not centre in its own tile, which is what a reader reported.
    tests/test_stat_tiles.py owns the padding now, together with the negative
    margin on `.tile .value` that has to match it; pinning half of that pair
    here would let the two drift apart."""
    body = _rule(".tile")
    assert "background: var(--surface-2)" in body
    assert "border: 0" in body
    assert "padding:" in body, "the tile still needs its own padding"


def test_tile_figures_are_centred():
    assert "text-align: center" in _rule(".tile")


def test_the_tile_value_stays_tabular():
    """What makes centring safe. Proportional digits change width as the number
    ticks, so a centred figure would jitter sideways."""
    assert "font-variant-numeric: tabular-nums" in _rule(".tile .value")


def test_the_tile_label_reserves_two_lines():
    """So a wrapping caption and a short one put their values at the same
    height. The reservation is computed from the line-height, so both have to be
    declared on the same rule."""
    body = _rule(".tile .label")
    assert "line-height: 1.4" in body
    # Caption, not micro: the label moved up a step when it stopped being
    # uppercase. The reservation is computed from whichever size is in use, so
    # the two have to name the same token.
    assert "min-height: calc(2 * 1.4 * var(--t-caption))" in body
    assert "font-size: var(--t-caption)" in body


def test_the_tile_centres_its_content_down_the_box():
    """The tile was the odd one out, and `test_the_market_strip_is_centred_too`
    below is the proof: `.ms-cell` is the same shape -- a caption over a figure
    in a row of equal cells -- and has been centred all along.

    The grid stretches every tile to the tallest in its row and the content was
    top-aligned inside that, so a tile with no delta and no note spent the extra
    height as a gap under its figure. Measured on the instrument row at 1440px:
    every tile 142px, label at 18 and value at 58 in all of them, and the space
    under the content 18px on the three-line tiles against 42px on the two-line
    ones. Reported as boxes that were not "properly adjusted within the box"."""
    assert "justify-content: center" in _rule(".tile")


def test_the_tile_note_no_longer_pins_itself_to_the_bottom():
    """It used to, and that was right while the content was top-aligned: it was
    how the notes lined up with each other. Against `justify-content: center` an
    auto margin wins outright, so the three-line tiles would splay open while
    the two-line ones sat centred -- the raggedness back, one row down, which is
    the exact thing the old rule existed to prevent.

    The notes still line up. Every tile carrying one now centres the same three
    lines, so they land at the same height by construction rather than by being
    pushed there."""
    assert "margin-top: auto" not in _rule(".tile .note")


# ------------------------------------------------------------ market strip


def test_the_market_strip_is_centred_too():
    """Same shape as a tile: a caption over a figure, in a row of equal cells."""
    body = _rule(".ms-cell")
    assert "justify-content: center" in body
    assert "text-align: center" in body


def test_the_strip_columns_stay_max_content():
    """The documented failure this must not reintroduce: an `auto` column
    absorbs free space, which pushed "S&P 500" hard left and "+0.86%" hard right
    in a 240px box and read as two unrelated numbers. Centring moves the pair as
    a unit; it must not let the columns grow."""
    assert "grid-template-columns: max-content max-content" in _rule(".ms-cell")


# ------------------------------------------------- what stays right-aligned


def test_key_value_rows_stay_right_aligned():
    """Deliberately not centred.

    A two-column list of readings is scanned down the value column, and
    right-aligned tabular figures put the ones, tens and hundreds under each
    other. Centring them would break that alignment to satisfy a rule about
    tiles, which is the wrong direction: the tiles were centred because each is
    one figure in its own box, not part of a column.
    """
    body = _rule(".kv dd")
    assert "text-align: right" in body
    assert "font-variant-numeric: tabular-nums" in body
