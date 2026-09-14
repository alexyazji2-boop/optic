"""What the terminal shows between 8pm and 4am.

Reported from a Sunday evening: the session bar said "this feed does not carry
the overnight tape" and the index cells showed Friday's 4pm close. The sentence
was true and the page was still wrong, because it answered "we cannot tell you"
when something perfectly good was available.

Measured at 21:18 ET on a Sunday, with the overnight session open:

    ^GSPC   last print  Fri 19:59
    ES=F    last print  Sun 21:08   ten minutes old
    NQ=F    last print  Sun 21:08
    RTY=F   last print  Sun 21:08

So the feed does carry an overnight tape. It does not carry one for single
stocks, which is a narrower and more useful claim, and the index futures are
live right through the window the cash indices are shut.
"""

import re

from app import session
from app.analytics import macro

APP_JS = open("static/app.js", encoding="utf-8").read()

FUTURES = {"ES=F", "NQ=F", "RTY=F"}


def test_the_index_futures_are_tracked():
    symbols = {i["symbol"] for i in macro.INSTRUMENTS}
    assert FUTURES <= symbols, FUTURES - symbols


def test_they_are_their_own_group_not_folded_into_equities():
    """A future is a different instrument, not a better quote for the index. It
    carries basis and its own expiry, so ES at 7,622 is not the S&P at 7,622,
    and a group that held both would let something pick either one for a figure
    labelled "S&P 500"."""
    by_symbol = {i["symbol"]: i for i in macro.INSTRUMENTS}
    for sym in FUTURES:
        assert by_symbol[sym]["group"] == "futures", by_symbol[sym]


def test_every_futures_label_says_futures():
    """The label travels with the number onto the strip. If it said "S&P 500"
    the page would be publishing a figure under a name that does not describe
    it, which is worse than the stale close it replaced."""
    for item in macro.INSTRUMENTS:
        if item["group"] == "futures":
            assert "futures" in item["label"].lower(), item["label"]


def test_the_strip_substitutes_rather_than_appends():
    """Five index cells in one strip would be the same reading twice. The
    overnight row replaces its daytime one."""
    block = APP_JS[APP_JS.index("const MARKET_STRIP = ["):]
    block = block[:block.index("];")]
    assert block.count("overnight:") == 3, "expected the three index rows"
    assert block.count("group: 'futures'") == 3
    assert "row.overnight ? row.overnight : row" in APP_JS


def test_the_swap_happens_only_overnight():
    """Globex runs Sunday 6pm to Friday 5pm, so during `closed` the futures are
    shut as well: swapping there would trade one stale print for another and
    lose the cash close, which is the better reference when nothing trades.
    Pre-market and after-hours stay on the cash indices because this feed does
    carry those sessions."""
    fn = APP_JS[APP_JS.index("function stripRows("):]
    fn = fn[:fn.index("\nfunction ")]
    assert "=== 'overnight'" in fn
    for phase in ("'closed'", "'pre'", "'after'"):
        assert phase not in fn, phase


def test_the_description_no_longer_claims_nothing_is_carried():
    """It said the feed does not carry the overnight session, full stop. That
    was the sentence a reader circled while three live futures quotes were
    available from the same provider."""
    text = session.DESCRIPTIONS["overnight"]
    assert "futures" in text.lower()
    assert "does not carry it" not in text


def test_the_description_still_says_what_is_not_live():
    """The half that must survive. A single stock still shows its 4pm close, and
    swapping the complaint for an advertisement would be the same failure in the
    other direction."""
    text = session.DESCRIPTIONS["overnight"].lower()
    assert "single stock" in text
    assert "4pm close" in text


def test_the_description_says_a_future_is_not_the_index():
    """Basis and expiry. Someone reading ES as "the S&P right now" is off by the
    carry, and this is the one sentence standing between them and that."""
    text = session.DESCRIPTIONS["overnight"].lower()
    assert "basis" in text
    # And says what to do about it. Naming the difference without saying how to
    # read it leaves a reader taking ES for the S&P, off by the carry, which is
    # the misreading this sentence exists to prevent.
    assert "rather than as a price" in text


def test_the_other_phases_are_untouched():
    """The change is scoped to one phase. Pre-market and after-hours were always
    carried and their copy was always right."""
    assert "Pre-market trading" in session.DESCRIPTIONS["pre"]
    assert "weekend" in session.DESCRIPTIONS["closed"]
