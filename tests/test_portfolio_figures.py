"""The portfolio said it was down and up at the same time.

Reported from a screenshot. The first tile read "Equity $99,025" in red against
a $100,000 start; the fourth read "Total return +1.32%" in green. Both were
labelled as the state of the same book, side by side, disagreeing about its
sign. The three book cards repeated it: Conservative showed "$100.0K" beside
"-0.17%", its equity untouched because it has closed nothing while its three
open positions are down.

Neither number was wrong. `paper.equity_for` is realised-only on purpose and
says why -- marking open positions into equity would let position sizing drift
with unrealised swings -- so it is a sizing base, not a valuation. "Equity" in
every brokerage means cash plus the market value of what you hold, so the label
promised a valuation and delivered the sizing base.

The explanation existed, in a caveat four hundred pixels below the tile, which
is not where a reader is when two numbers disagree in front of them.

Measured from /api/tracker: start 100,000, realised -975, unrealised +2,296,
total +1,321, return +1.32%. Account value is 101,321 and agrees with the
return beside it; the sizing base is 99,025 and now appears in the risk row,
which is the row measured against it.
"""

from __future__ import annotations

import re

APP = open("static/app.js", encoding="utf-8").read()
PAPER = open("app/paper.py", encoding="utf-8").read()
CODE = re.sub(r"/\*.*?\*/", "", APP, flags=re.S)


def _fn(name, end="\n}"):
    return APP.split(name, 1)[1].split(end, 1)[0]


# ------------------------------------------------- the headline reconciles


def test_the_headline_is_what_the_book_is_worth():
    """Start plus everything made or lost, closed and open -- so it moves the
    same way as the return printed three tiles along."""
    assert "tile('Account value', money(s.start_equity + s.total_pnl)" in CODE
    # Anchored to THIS tile's own call, not to the file. Unanchored, the
    # mutation that colours the account value by realised P&L -- which is the
    # exact contradiction being fixed -- passed, because the string survived
    # elsewhere in the same view.
    # To the NEXT tile, not to the first `}` -- the call contains
    # `${money(...)}` and a brace slice stops inside it, before the colour
    # argument this test is about.
    call = CODE.split("tile('Account value'", 1)[1]
    call = call[:call.index("tile('Realised P&L'")]
    assert "signClass(s.total_pnl)" in call, \
        "coloured by the same figure it displays, or it contradicts itself again"
    assert "signClass(s.realised_pnl)" not in call


def test_the_sizing_base_is_labelled_as_one_and_sits_where_it_is_spent():
    """Not deleted -- it is the number every percentage in the risk row is
    measured against, and a reader checking "14.6% of a 15% budget" needs it."""
    assert "tile('Sizing base', money(s.equity)" in CODE
    risk = CODE.split("tile('Risk deployed'", 1)[1][:600]
    assert "Sizing base" in risk, "it belongs in the row it explains"


def test_no_tile_calls_the_sizing_base_equity():
    """The whole of the fault: one word promising a valuation."""
    tiles = re.findall(r"tile\('([^']+)'", CODE)
    assert "Equity" not in tiles or "money(s.equity)" not in CODE.split(
        "tile('Equity'", 1)[-1][:60], "the sizing base is labelled Equity again"


def test_the_backend_sizing_base_is_left_alone():
    """This is a labelling fix, not an accounting one. `equity_for` stays
    realised-only, and the reason is in its own docstring."""
    fn = PAPER.split("def equity_for(", 1)[1].split("\ndef ", 1)[0]
    assert "status='closed'" in fn
    assert "Realised only, deliberately" in fn


def test_a_single_closed_trade_is_not_plural():
    assert "(s.closed_count === 1) ? 'trade' : 'trades'" in CODE


# ------------------------------------------------------ the three books


def test_each_book_card_shows_what_that_book_is_worth():
    """Same fault, three times over. The cards read `b.equity`, which for a
    book that has closed nothing is exactly its starting capital -- so
    Conservative showed a flat $100.0K beside a negative return."""
    assert "function bookValue(b) {" in APP
    fn = _fn("function bookValue(b) {")
    assert "su.total_pnl" in fn and "start_equity" in fn
    sel = _fn("function renderBookSelector(d) {")
    assert "bookValue(b)" in sel
    assert "fmtCompact(b.equity)" not in sel, "a card is showing the sizing base again"


def test_a_book_with_no_trades_still_reports_a_value():
    """`bookValue` falls back rather than rendering undefined when the server
    sends a book with no summary at all."""
    fn = _fn("function bookValue(b) {")
    assert "if (start === null || start === undefined) return b && b.equity;" in fn


def test_the_figures_say_which_of_the_three_books_they_are():
    """The selector switches between three portfolios and every figure below
    sat under one fixed heading, so switching looked like the page failing to
    update rather than like a different book."""
    assert "const bookName = ((d.books || []).find((b) => b.id === (d.book || 'balanced')) || {}).label || '';" in APP
    assert 'class="bk-active"' in APP
    assert ".bk-active {" in open("static/styles.css", encoding="utf-8").read()


def test_the_name_comes_from_the_book_list_not_a_second_lookup():
    """So the heading and the highlighted card cannot disagree about what the
    book is called."""
    assert "(d.books || []).find((b) => b.id === (d.book || 'balanced'))" in APP


def test_switching_books_reloads_rather_than_re_rendering_stale_state():
    fn = _fn("  const bookBtn = evt.target.closest('[data-book]');", "\n  const noticeOk")
    assert "STATE.trackerBook = bookBtn.dataset.book;" in fn
    assert "STATE.tracker = null;" in fn, "or the next render shows the old book's rows"
    assert "loadTracker(true)" in fn
