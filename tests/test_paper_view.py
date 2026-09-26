"""The paper book's page: a ticket, a book, and a scoreboard with a twist.

Driven end to end in a browser against the live provider: a long 100 NVDA at
200 marked +$2,507 (+2.51R), the same size short in AAPL marked -9.11R, and
three NVDA calls opened at the chain mid and marked from it. A trade with no
stop and a trade with the stop on the wrong side were both refused before
anything was written.

The twist is the last panel. Every trade freezes the stance Optic held on that
symbol at the moment it was opened, and the record splits realised R by whether
the trade ran with that read or against it. Verified: "Traded with Optic's read
+0.51R, 1 trade".
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
CSS = (ROOT / "static/styles.css").read_text()
HTML = (ROOT / "static/index.html").read_text()


def function(name):
    return re.search(r"^(?:async )?function " + name + r"\([^\n]*\) \{.*?^\}",
                     APP, re.M | re.S).group()


# ------------------------------------------------- a view needs five places


def test_the_view_is_registered_everywhere_it_has_to_be():
    assert 'id="view-paper"' in HTML
    assert "paper: $('#view-paper')" in APP
    assert "views: ['tracker', 'paper', 'roth']" in APP, "not in the Positions group"
    assert "if (view === 'paper') return loadPaper(force);" in APP
    assert "{ view: 'paper', label: 'Paper trades'" in APP
    allowed = APP.split("const TICKERLESS_VIEWS = [", 1)[1].split("];", 1)[0]
    assert "'paper'" in allowed, "a book is not about one loaded symbol"


def test_it_carries_a_hypothetical_performance_disclaimer():
    """The terminal's own record already carries one. A book where the reader
    picks the fills needs it more, not less: there is no borrow, no assignment
    and no slippage in it."""
    d = APP.split("    paper: '<strong>", 1)[1].split("',\n", 1)[0]
    assert "Hypothetical performance" in d
    for missing in ("commission", "slippage", "borrow", "tax"):
        assert missing in d, missing
    assert "never placed with real money" in d


# ------------------------------------------------- it is not the other ledger


def test_the_book_never_touches_the_terminals_own_record():
    """Optic Portfolio's value is that nobody edited it. A hand-entered trade
    reaching that ledger would end that, and the numbers would still add up."""
    for fn in ("paperOpenTrade", "paperClose", "paperMark"):
        body = function(fn)
        assert "/api/tracker" not in body, fn
        assert "STATE.tracker" not in body, fn


def test_the_book_lives_in_the_browser_and_says_so():
    """No sign-in, so a server-side book would be one book shared by every
    visitor. The page states this rather than leaving it to be discovered when
    a trade turns up on another machine -- or worse, does not."""
    assert "const PAPER_KEY = 'optic.paper.v1';" in APP
    assert "localStorage.setItem(PAPER_KEY" in function("paperSave")
    head = " ".join(function("renderPaperView").split())
    assert "this browser and nowhere else" in head
    assert "Optic Portfolio" in head, "and what it is not"


def test_a_browser_that_refuses_storage_does_not_break_the_page():
    """Private mode throws on setItem, and an exception in a submit handler
    stops the handler: the trade would be lost AND the page would stop
    responding."""
    assert "catch (e)" in function("paperSave")
    # And a hand-edited or half-written key is no book, not a crash on render.
    block = APP.split("localStorage.getItem(PAPER_KEY)", 1)[1][:260]
    assert "Array.isArray(raw.open)" in block


# ------------------------------------------------- what it refuses to open


def test_a_trade_without_a_stop_is_refused():
    """Everything on this page is reported in multiples of what a trade risked.
    A trade with no stop has no denominator, and admitting one would put a
    blank in the only column that compares trades of different sizes."""
    fn = function("paperOpenTrade")
    assert "if (!(stop > 0))" in fn
    assert "A stop is required" in " ".join(fn.split())


def test_a_stop_on_the_wrong_side_is_refused():
    """A long stopped above entry is stopped out immediately: the book would
    record a loss the reader never meant to take. It is a typo, and the moment
    to catch a typo is before it becomes a row in a record."""
    fn = function("paperOpenTrade")
    assert "t.direction === 'long' && stop >= entry" in fn
    assert "t.direction === 'short' && stop <= entry" in fn


def test_nothing_is_written_until_every_check_has_passed():
    """A refusal that had already pushed the position would leave a trade in
    the book AND an error message saying it was not opened."""
    fn = function("paperOpenTrade")
    assert fn.index("paperBook.open.unshift(") > fn.rindex("return '"), \
        "a refusal after the write is a write"


def test_the_book_has_a_ceiling_that_matches_the_servers():
    """The marking endpoint caps at fifty. A book allowed past that would show
    its first fifty marked and the rest blank forever."""
    assert "const PAPER_MAX = 50;" in APP
    assert "paperBook.open.length >= PAPER_MAX" in function("paperOpenTrade")
    server = (ROOT / "app/papertrade.py").read_text()
    assert "MAX_POSITIONS = 50" in server


# ------------------------------------------------- the twist


def test_every_trade_freezes_the_read_optic_held_at_the_time():
    """Reading it at close time would be scoring the terminal with the benefit
    of having watched the trade."""
    fn = function("paperOpenTrade")
    assert "const read = paperRead();" in fn
    # The value that is stored, not just the presence of the words. An earlier
    # version asserted `"stance: read.stance" in fn`, which survived changing
    # the guard to `null ?` -- the branch was still in the source and never ran,
    # so every trade recorded no read at all and the scoreboard quietly had
    # nothing to split on.
    stored = re.search(r"read: (\w+) \? \{ stance: read\.stance", fn)
    assert stored and stored.group(1) == "read", fn[fn.index("read:"):][:80]
    # And the close path copies the trade forward rather than re-reading.
    close = function("paperClose")
    assert "paperRead()" not in close


def test_a_neutral_read_is_neither_agreement_nor_disagreement():
    """"Optic was neutral and you were long" is not a disagreement. Counting it
    as one would make the scoreboard say the reader fought the terminal on
    trades where it held no view."""
    fn = function("paperAgreement")
    assert "return null;" in fn.split("read.stance === 'bearish'", 1)[1]
    stats = function("paperStatsHTML")
    assert "paperAgreement(t.read, t.direction) === want" in stats
    assert "neither column" in " ".join(stats.split())


def test_the_scoreboard_is_realised_only():
    """An open position's P&L is a quote, not a result. Folding it in would let
    a book look like it wins by never closing anything that is down -- the
    exact habit a practice account exists to expose."""
    fn = function("paperStatsHTML")
    assert "paperBook.closed" in fn
    assert "paperBook.open" not in fn
    assert "realised" in fn.lower()


def test_the_scoreboard_admits_a_small_sample_proves_nothing():
    # Whitespace collapsed: the sentence wraps in the source, and asserting
    # the exact string found it split across two lines.
    flat = " ".join(function("paperStatsHTML").split())
    assert "is not a finding about anything" in flat


# ------------------------------------------------- R, not a percentage


def test_results_are_reported_in_multiples_of_what_was_risked():
    """A book with no deposits has no equity, so a percentage return here would
    be a percentage of a number the reader invented. R is true whatever the
    account."""
    fn = function("paperR")
    assert "paperRisk(pos)" in fn
    risk = function("paperRisk")
    assert "Math.abs(pos.entry_price - pos.stop)" in risk
    assert "pos.instrument === 'option' ? 100 : 1" in risk, "a contract is 100 shares"


def test_the_cost_and_the_risk_are_shown_before_the_trade_exists():
    """A reader who finds out afterwards that a two-dollar stop on five
    contracts was a thousand dollars of risk has learned it the expensive way,
    which is the way this page exists to avoid."""
    fn = function("paperPreviewHTML")
    assert "Costs" in fn and "Risks" in fn
    assert "Reward:risk" in fn
    assert "wrongSide" in fn, "and the typo is named before it is taken"


# ------------------------------------------------- honest marks


def test_the_mark_says_where_it_came_from():
    """mark_option answers from the live chain when there is one and from a
    model when there is not. Which one it was changes what the P&L beside it is
    worth, and no other simulator tells you."""
    assert "m.mark_source" in function("paperOpenRow")
    server = (ROOT / "app/papertrade.py").read_text()
    assert '"Last trade"' in server
    assert "paper.mark_option" in server


def test_a_position_that_could_not_be_marked_cannot_be_closed():
    """Closing at a mark that does not exist would write a P&L of nothing into
    the record."""
    row = function("paperOpenRow")
    assert "disabled" in row.split("data-paper-close", 1)[1][:200]
    fn = function("paperClose")
    assert "if (m.mark_price === undefined || m.mark_price === null) return;" in fn


def test_a_wide_spread_is_called_out_at_the_moment_of_entry():
    """The mid is what the book marks at, so the spread is the first thing that
    makes a paper fill a fiction. Said at entry rather than in a footnote."""
    fn = function("paperTicketHTML")
    assert "picked.spread_pct > 10" in fn
    assert "a real fill would be worse" in " ".join(fn.split())


# ------------------------------------------------- controls and handlers


def test_every_control_on_this_page_has_a_handler():
    """A dead control does not error; it takes the click and nothing happens,
    which reads as a slow app."""
    rendered = set(re.findall(r"data-paper-([a-z]+)=", APP))
    handled = set(re.findall(r"closest\('\[data-paper-([a-z]+)\]'\)", APP))
    assert not rendered - handled, sorted(rendered - handled)


def test_clearing_the_book_asks_first():
    """There is no server copy to restore from and no undo: this browser is the
    only place the book exists."""
    i = APP.index("closest('[data-paper-reset]')")
    assert "window.confirm(" in APP[i:i + 400]


def test_the_read_can_be_fetched_from_this_page():
    """STATE.swing is filled only by the Dossier facets, so with nothing loaded
    a reader here got "Optic has no read on NVDA loaded" and no way to get one
    without leaving the page."""
    fn = function("paperLoadRead")
    assert "loadSwing(false, { silent: true })" in fn
    assert "data-paper-load" in function("paperReadHTML")


def test_the_chain_is_only_fetched_for_the_option_half():
    """/api/chain is a real cost and a shares ticket never reads it."""
    i = APP.index("closest('[data-paper-inst]')")
    block = APP[i:i + 600]
    assert "paperTicket.instrument === 'option'" in block


def test_it_introduces_no_new_colours():
    block = CSS[CSS.index("/* ------------------------------------------------------------ paper trades"):]
    assert not re.search(r"#[0-9a-fA-F]{3,8}", block), "a hex value on this page"


# ------------------------------------------------- failures that recover
#
# Reported from a screenshot: the expiry control read "Load a symbol first"
# with NVDA typed into the field beside it, and the book said "Could not price
# the book just now (Failed to fetch)" with no way to ask again. The server had
# gone down. Both states were permanent for the rest of the session.


def test_a_failed_chain_can_be_asked_for_again():
    """`paperChainFor` was set before the fetch and left set whatever happened,
    so the guard short-circuited every later attempt: one failure and that
    symbol's chain was never requested again.

    Driven for real -- server killed mid-flight, state went to `failed` with a
    Try again beside it, server restarted, retry recovered 1,570 chain rows."""
    fn = function("paperLoadChain")
    assert "paperChainFor = '';" in fn, "a failed load must not pin the symbol"
    # And the guard only short-circuits states that are actually in hand.
    assert "paperChainState === 'loading'" in fn
    assert "paperChainState === 'ready'" in fn


def test_the_chain_request_ignores_a_stale_answer():
    """Typing a second symbol while the first is in flight: the slower reply
    must not overwrite the newer one's chain."""
    fn = function("paperLoadChain")
    assert fn.count("if (paperChainFor !== want) return;") == 2


def test_the_expiry_control_says_which_of_the_four_things_is_true():
    """"Load a symbol first" is one of four states and the only one that reads
    as an instruction. Shown for all four, it was wrong in three -- including
    the one a reader meets with the symbol already typed in."""
    fn = function("paperChainPrompt")
    assert "Type a symbol above" in fn
    assert "Could not read" in fn
    assert "has no listed options" in fn
    assert "'s chain" in fn, "and one for while it is being read"
    # The control renders it rather than the old constant.
    ticket = function("paperTicketHTML")
    assert "paperChainPrompt(t)" in ticket
    assert "Load a symbol first" not in ticket


def test_a_book_that_failed_to_price_offers_to_try_again():
    """Marking runs on arriving at the page and after opening a trade, so a
    reader whose book failed to price had to leave the page and come back --
    with nothing on screen telling them that was the move."""
    fn = function("paperMark")
    assert "paperMarkFailed = true;" in fn
    assert "paperMarkFailed = false;" in fn, "and cleared when it is tried again"
    assert "data-paper-remark" in function("paperTicketHTML")
    i = APP.index("closest('[data-paper-remark]')")
    assert "paperMark();" in APP[i:i + 300]
