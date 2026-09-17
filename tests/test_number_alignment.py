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
    that survive the merge: the flat surface, no border, the wider padding."""
    body = _rule(".tile")
    assert "background: var(--surface-2)" in body
    assert "border: 0" in body
    assert "padding: var(--space-4) var(--space-5)" in body


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
    assert "min-height: calc(2 * 1.4 * var(--t-micro))" in body


def test_the_tile_note_is_pushed_to_the_bottom():
    """Only some tiles carry one. A note floating under a short value while its
    neighbour's sits lower is the same raggedness one row down."""
    assert "margin-top: auto" in _rule(".tile .note")


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
