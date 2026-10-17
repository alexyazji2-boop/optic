"""The home search row's empty right track, and the week that faded into the page.

Measured at 1440 in the light theme. The search sits in the middle 56% so it
stays centred, which leaves an equal track on each side. The brand fills the
left one. The right one was about 220px of page, and the only text near it was
"As of", right-aligned under the market strip, so it read as a caption for the
hole. The greeting and the market's date already existed as a full-width row
above the board. They move into that track.

The same pass: the day's cells used --surface-2, which in the light theme is
the page itself, so the next five days read as a watermark inside a card one
step off the page.
"""
from __future__ import annotations

import re

APP = open("static/app.js", encoding="utf-8").read()
CSS = open("static/styles.css", encoding="utf-8").read()


def _fn(name: str) -> str:
    start = APP.index("function %s(" % name)
    nxt = APP.find("\nfunction ", start + 1)
    return APP[start:nxt if nxt > 0 else len(APP)]


def test_the_aside_sits_on_the_search_row_and_uses_the_greetings_words():
    home = _fn("renderHome")
    assert 'class="home-now" id="home-now"' in home
    assert home.index('class="home-quick"') < home.index('id="home-now"')
    assert home.index('id="home-now"') < home.index('id="hm-today"')
    body = _fn("homeNowHTML")
    assert "homeHello()" in body and "homeDateLine(session)" in body
    assert "market closed" in body
    assert "paintHomeNow(session)" in _fn("loadHomeMarket")


def test_the_wide_grid_shows_the_aside_and_stands_the_row_down():
    """Below 1000px of Home there is no third track, so the aside stays
    hidden and the greeting inside the market block remains the one on screen."""
    assert re.search(r"\.home-now \{[^}]*display: none", CSS)
    block = CSS[CSS.index("@container homehead (min-width: 1000px)"):]
    block = block[:block.index("/* Hidden until")]
    now = re.search(r"#view-home > \.home > \.home-now \{([^}]*)\}", block)
    assert now, "the aside is not placed in the wide grid"
    rule = now.group(1)
    assert "grid-column: 3;" in rule and "grid-row: 2;" in rule
    assert "display: flex;" in rule
    assert "#view-home .hm-greet { display: none; }" in block


def test_the_day_cells_are_not_the_page_colour():
    """The original cells are --surface-2. The rule that wins is the later
    one, a wash of ink over the panel, and an empty day no longer fades its date."""
    first = CSS.index(".cs-day {")
    later = CSS.index(".cs-day {", first + 1)
    body = CSS[later:CSS.index("}", later)]
    assert "color-mix(in srgb, var(--ink) 8%, var(--ws-panel))" in body
    assert CSS.index(".cs-day.is-empty { opacity: 0.7") < CSS.index(
        ".cs-day.is-empty { opacity: 1")
    asof = CSS.rindex(".ms-asof {")
    assert "text-align: start" in CSS[asof:CSS.index("}", asof)]


def test_the_strip_is_a_row_of_plates_and_the_figure_is_the_card():
    """The box used to own the border, so eight readings were cells of one
    tray and the last cell had its right edge removed. Each quote is a plate
    now. The price sits on its own line at the figure size, and the change
    sits under it rather than beside it."""
    box = CSS[CSS.index(".ms-strip {"):]
    box = box[:box.index("}")]
    assert "overflow: hidden" in box
    assert "border: 0" in box and "background: transparent" in box
    cell = CSS[CSS.index(".ms-cell {"):]
    cell = cell[:cell.index("}")]
    assert "border-radius: var(--r-plate)" in cell
    assert "border: 1px solid var(--ws-line-strong)" in cell
    assert "box-shadow: var(--elev-1)" in cell
    assert ".ms-cell:last-child { border-right: 0" not in CSS
    price = CSS[CSS.index(".ms-last {"):]
    price = price[:price.index("}")]
    assert "grid-column: 1 / -1" in price
    assert "var(--t-d2)" in price
    change = CSS[CSS.index(".ms-chg {"):]
    change = change[:change.index("}")]
    assert "grid-column: 1 / -1" in change


def test_the_other_tabs_use_the_same_plate():
    """The home strip is the template. A figure in its own box on the
    Dossier, the index board, the overview's section row and Discover's
    cross-asset grid is the same card, or those tabs stay on the corner
    the home page just left."""
    for sel in (".tile", ".ov-card", ".idx-card", ".ex-inst"):
        body = CSS[CSS.index(sel + " {"):]
        body = body[:body.index("}")]
        assert "border-radius: var(--r-plate)" in body, sel
        assert "var(--plate-sheen)" in body, sel
    # The scroll covers on a tile inside a panel grid replace the wash.
    # The sheen has to be painted back under them, or the Dossier's stat
    # row is the one place the template is missing.
    grid = CSS[CSS.index(".panel .grid > .tile {"):]
    grid = grid[:grid.index("}")]
    assert "var(--plate-sheen)" in grid
    assert "var(--scroll-cover, var(--surface))" in grid


def test_the_remaining_readings_use_the_same_plate():
    """A figure in its own box was still a flat cell on the tabs the first
    plate pass did not reach. The ones that are a label and a number are
    centred. The ones that hold a paragraph keep their alignment and take
    the same edge, corner and wash."""
    centred = (
        ".ph-cell", ".wv-pulse-cell", ".bt-tile", ".bk-tile", ".op-tile",
        ".pt-stat", ".su-cell", ".ob-item", ".fg-hbox",
    )
    for sel in centred:
        body = CSS[CSS.index(sel + " {"):]
        body = body[:body.index("}")]
        assert "border-radius: var(--r-plate)" in body, sel
        assert "var(--plate-sheen)" in body, sel
        assert "text-align: center" in body, sel
    prose = (
        ".de-num", ".osc-tile", ".rf-tile", ".bkw-score", ".book-card",
        ".cmp-hz", ".ew-day", ".catmode-box", ".vs-case",
    )
    for sel in prose:
        body = CSS[CSS.index(sel + " {"):]
        body = body[:body.index("}")]
        assert "border-radius: var(--r-plate)" in body, sel
        assert "var(--plate-sheen)" in body, sel
    # Compare horizons and catalyst boxes are direct children of a panel
    # grid, so the scroll covers would replace the wash.
    grid = CSS[CSS.index(".panel .grid > .tile {"):]
    grid = grid[:grid.index("}")]
    assert ".panel .grid > .catmode-box" in CSS[CSS.index(".panel .grid > .catmode-box"):CSS.index(".panel .grid > .tile {")]
    assert ".panel .grid > .cmp-hz" in CSS[CSS.index(".panel .grid > .cmp-hz"):CSS.index(".panel .grid > .tile {")]
    assert "var(--plate-sheen)" in grid


def test_the_week_and_the_trend_cards_use_the_same_plate():
    """One corner for the things that are cards of a reading. The phone
    trend row stays square: a 16px corner on a full-width row was the
    375px height bug's cousin, a card pretending to be a list."""
    day = CSS[CSS.index(".cs-day {"):]
    day = day[:day.index("}")]
    assert "border-radius: var(--r-plate)" in day
    card = CSS[CSS.index(".tr-card {"):]
    card = card[:card.index("}")]
    assert "border-radius: var(--r-plate)" in card
    phone = CSS[CSS.index("@media (max-width: 559px) {\n  .tr-grid"):]
    phone = phone[:phone.index("\n}")]
    assert "border-radius: 0" in phone
