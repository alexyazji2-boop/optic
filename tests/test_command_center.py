"""The homepage as a market command centre.

It used to open with a 92px aperture, "Optic Terminal" at display size and a
three-line product pitch: about 340px of branding above the fold, on a page
whose own header already says OPTIC TERMINAL in the corner. The market state
was below all of it. Now the strip is the first element, the day's read and the
ranked cross-asset moves are the first section, and the brand is one 30px row.

**Everything here is built from `/api/home`, which already carried all of it.**
Nineteen macro instruments grouped by asset class, the index board, and the
written daily read. No new endpoint, no placeholder rows. The one thing the
brief behind this asked for that the data cannot support is a same-day movers
leaderboard over the whole universe, and the movers block says so in its own
copy rather than pretending.
"""

from __future__ import annotations

import re

APP_JS = open("static/app.js").read()
CSS = open("static/styles.css").read()


def _fn(name: str) -> str:
    start = APP_JS.index("function %s(" % name)
    nxt = APP_JS.find("\nfunction ", start + 1)
    return APP_JS[start:nxt if nxt > 0 else len(APP_JS)]


# ------------------------------------------------------------------ the strip


def test_the_strip_is_the_first_thing_on_the_page():
    """Above the brand and above the search, in its own host so it does not wait
    behind the watchlist and the movers scan."""
    home = _fn("renderHome")
    assert '<div id="cc-strip"></div>' in home
    assert home.index('id="cc-strip"') < home.index('class="home-brand"')
    assert home.index('id="cc-strip"') < home.index('class="home-search"')


def test_the_strip_reads_real_instruments_from_the_home_payload():
    """Not a hardcoded list of prices. Each entry names the group and label the
    payload uses, so a group that fails to build drops its own cells."""
    assert "const MARKET_STRIP = [" in APP_JS
    block = APP_JS[APP_JS.index("const MARKET_STRIP = ["):]
    block = block[:block.index("];")]
    for label in ("S&P 500", "Nasdaq 100", "Russell 2000", "VIX",
                  "US 10Y", "WTI Crude", "Gold", "Bitcoin"):
        assert label in block, label
    fn = _fn("stripInstrument")
    assert "macro || {}).groups" in fn
    assert "r.label === label" in fn


def test_a_missing_instrument_drops_its_own_cell():
    """A degraded feed should cost one cell, not the strip."""
    fn = _fn("marketStripHTML")
    assert "if (!inst || inst.last === null || inst.last === undefined) return '';" in fn
    assert ".filter(Boolean)" in fn
    assert "if (!cells) return '';" in fn


def test_the_strip_keeps_the_plain_language_reading():
    """`macroWord` was the fix for the red VIX plus. The tile it lived on is
    gone; the wording is not."""
    fn = _fn("marketStripHTML")
    assert "macroWord(inst.symbol, chg)" in fn
    assert "'^VIX'" in fn and "'^TNX'" in fn


def test_the_strip_scrolls_rather_than_wrapping():
    """Eight cells need ~1050px. A strip that becomes three rows is not a
    strip, and a hard-cut last cell reads as a layout bug."""
    block = CSS[CSS.index(".ms-strip {"):]
    block = block[:block.index("}")]
    assert "overflow-x: auto" in block
    assert "mask-image" in CSS[CSS.index(".ms-strip"):CSS.index(".ms-cell {")]


# --------------------------------------------------------- what matters now


def test_the_moves_are_ranked_against_each_instrument_s_own_range():
    """Raw percent ranks by which instrument is inherently jumpiest. Measured:
    it led with VVIX +6.4% and Nat Gas -3.9% while the Russell was down 1.3% in
    fourth, but VVIX moves 4.9% on an average day and the Russell 1.1%."""
    fn = _fn("rankedMoves")
    assert "inst.atr_pct" in fn
    assert "Math.abs(inst.chg_1d) / atr" in fn
    assert "rows.sort((a, b) => b.rel - a.rel)" in fn


def test_an_instrument_without_a_range_sorts_last_rather_than_dividing_by_zero():
    fn = _fn("rankedMoves")
    assert "const atr = Number(inst.atr_pct) || 0;" in fn
    assert "atr ? Math.abs(inst.chg_1d) / atr : 0" in fn


def test_the_multiple_is_shown_because_it_justifies_the_order():
    """Without it, VVIX +6.4% above Russell -1.3% looks like a list sorted by
    the bigger number, which is the ordering this deliberately is not."""
    fn = _fn("whatMattersNow")
    assert "cc-move-rel" in fn
    assert "normal" in fn
    assert ".cc-move-rel" in CSS


def test_the_headline_is_the_existing_written_read():
    """Not a new AI call on page load. `read.summary` is the daily brief the
    app already stands behind."""
    fn = _fn("whatMattersNow")
    assert "(data.read || {}).summary" in fn
    assert "read.headline" in fn


def test_the_section_says_what_it_does_not_rank():
    """Every panel states what it cannot tell you. Single stocks are not in
    this ranking and the reason is a real data limit."""
    fn = _fn("whatMattersNow")
    assert "Single stocks are not ranked here" in fn
    assert "same-day quote for the whole universe" in fn


# ------------------------------------------------------------------- movers


def test_the_movers_block_names_its_real_window():
    """The brief asked for "today's biggest movers". The scanners rank on 20-
    and 60-day rate of change over a background-built universe. Calling a
    one-month leaderboard "today's movers" would be wrong on every row."""
    fn = _fn("homeMovers")
    assert "roc20" in fn
    assert "not\n    today's move" in fn or "not" in fn and "today's move" in fn
    head = APP_JS[APP_JS.index("Moved most this month"):]
    assert head[:40].startswith("Moved most this month")


def test_a_cold_universe_is_an_empty_state_not_an_error():
    """`available: false` is normal on a cold start: the scan covers ~3000
    symbols in the background. It shows the server's own reason."""
    fn = _fn("homeMovers")
    assert "data.reason" in fn
    assert "if (!rows.length)" in fn


def test_the_movers_scan_does_not_hold_the_page():
    """It is the slowest request on this page and the rest is useful without
    it."""
    assert "homeMovers();" in _fn("loadHomeMarket")
    assert "await homeMovers()" not in APP_JS


# ---------------------------------------------------------------- questions


def test_the_questions_name_real_numbers():
    """Generated from the day's biggest mover, the actual VIX level and the
    actual regime, so they cannot go stale into a canned list."""
    fn = _fn("marketQuestions")
    assert "rankedMoves(data)[0]" in fn
    assert "biggest.label" in fn and "biggest.chg_1d" in fn
    assert "vix.last" in fn
    assert "(data.macro || {}).regime" in fn


def test_the_questions_share_the_ranking_with_the_list():
    """Two sorts would drift and the question would name an instrument that is
    not the one at the top of the list. Same bug class as the two chart tabs
    seeding one palette differently."""
    # Three: the definition, plus one caller each. A count of two would have
    # been satisfied by deleting one of the callers.
    assert APP_JS.count("rankedMoves(data)") == 3
    assert "function rankedMoves(data)" in APP_JS
    assert "rankedMoves(data)" in _fn("whatMattersNow")
    assert "rankedMoves(data)[0]" in _fn("marketQuestions")
    assert "all.sort((a, b) => Math.abs(b.chg_1d)" not in APP_JS


def test_a_question_pre_types_rather_than_sending():
    """Five questions answered on load is five API calls nobody asked for, and
    the assistant costs money per call."""
    assert "data-ask-text" in APP_JS
    handler = APP_JS[APP_JS.index("closest('[data-ask-text]')"):]
    handler = handler[:handler.index("});")]
    assert "openPulseWithText" in handler


def test_the_market_level_ask_topic_exists():
    """The both-directions check in test_auth_client.py caught this one when it
    did not: `askPulse('whatmatters')` rendered a button with no prompt."""
    assert "askPulse('whatmatters')" in APP_JS
    assert "whatmatters: " in APP_JS


# -------------------------------------------------------------------- hero


def test_the_brand_is_one_row_not_a_hero():
    """The header already says OPTIC TERMINAL. A second wordmark at display
    size on every visit is the thing that pushed the market off the screen."""
    assert 'class="home-brand"' in APP_JS
    brand = CSS[CSS.index(".home-brand {"):]
    brand = brand[:brand.index("}")]
    assert "display: flex" in brand
    logo = CSS[CSS.index(".home-logo {"):]
    logo = logo[:logo.index("}")]
    # A bound rather than the exact number. The property is that the mark is a
    # row-height icon, and pinning a value made this test a second copy of the
    # declaration: growing 30 to 38 on a reader's request failed it while the
    # row was still one row. 48 is the ceiling because the row would then be
    # taller than the search field's 53px box it sits above, which is the point
    # at which the brand starts being the page again.
    px = int(re.search(r"width: (\d+)px", logo).group(1))
    assert px <= 48, "%dpx is a hero, not a row" % px
    title = CSS[CSS.index(".home-title {"):]
    title = title[:title.index("}")]
    assert "var(--t-lead)" in title


def test_the_phone_no_longer_keeps_a_hero_of_its_own():
    """A media query was still setting a 68px mark and a --t-d2 title, which is
    why the phone had a hero long after the desktop lost one."""
    assert ".home-logo { width: 68px; height: 68px; }" not in CSS
    assert ".home-title { font-size: var(--t-d2); }" not in CSS


def test_the_lede_survives_in_the_tour():
    """It is a good paragraph and the right thing to read once. Removed from
    above the fold, not deleted."""
    assert "A market research workbench" in APP_JS
    tour = APP_JS[APP_JS.index('<details class="home-tour"'):]
    tour = tour[:tour.index("</details>")]
    assert "A market research workbench" in tour


def test_the_superseded_four_tile_block_is_gone_not_orphaned():
    """It showed four of the strip's own instruments with the same numbers."""
    assert "homePulseStrip" not in APP_JS


# ------------------------------------------------------------------ wiring


def test_every_command_centre_class_has_a_rule():
    used = set()
    for name in ("marketStripHTML", "whatMattersNow", "marketQuestions", "homeMovers"):
        for attr in re.findall(r'class="([^"]*)"', _fn(name)):
            for tok in attr.split():
                if tok.startswith(("ms-", "cc-")):
                    used.add(tok)
    assert {"ms-strip", "ms-cell", "cc-move", "cc-q", "cc-method"} <= used, used
    for cls in used:
        assert ".%s" % cls in CSS, cls


def test_the_clickable_rows_use_handlers_that_already_exist():
    """A strip cell and a move row open the instrument workspace; a mover row
    opens the ticker. Both attributes are pre-existing and already handled."""
    assert "closest('[data-instrument]')" in APP_JS
    assert "closest('[data-watch-open]')" in APP_JS
    assert "data-instrument=" in _fn("marketStripHTML")
    assert "data-instrument=" in _fn("whatMattersNow")
    assert "data-watch-open=" in _fn("homeMovers")


def test_no_em_dashes_in_the_new_copy():
    for name in ("whatMattersNow", "marketQuestions", "homeMovers", "marketStripHTML"):
        fn = _fn(name)
        body = re.sub(r"/\*.*?\*/", "", fn, flags=re.S)
        for text in re.findall(r">([^<>{}]{16,})<", body):
            assert "—" not in text, (name, text)
