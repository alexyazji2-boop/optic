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
