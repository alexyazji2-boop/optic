"""Congressional trade disclosures, from the filings rather than a vendor.

Cost, since that was the question: nothing. The STOCK Act requires members to
disclose covered transactions within 45 days, and the Clerk of the House
publishes both the index and the filings with no key and no paid tier. What is
sold elsewhere is the parsing, not the data.

The shape, measured against the live 2026 archive: one annual ZIP holds an XML
index of 1,695 filings, 400 of them `FilingType P` -- the Periodic Transaction
Reports that carry trades. The index has no ticker and no amount; each trade is
in a per-filing PDF that carries a real text layer, so this is parsing and not
OCR.

Nothing here touches the network. The parser is exercised against the exact
text the Clerk's own filings produce, including the two data-quality quirks
found in the live archive:

  * doc 20035450 is filed under `First: "Scott Scott"`, so the stutter is in
    the government's record and appears identically on the PDF -- collapsing
    it is presentation, not correction.
  * one McGuire entry is filed under `First: "John J Mr"`, an honorific in the
    wrong column.

Both were checked against the source before being treated as quirks rather
than as bugs in this parser.
"""

from __future__ import annotations

import re

from app.analytics import congress


# The text pypdf actually returns for a House PTR, flattened the way the
# parser flattens it. Taken from doc 20034201 and 20033751.
FILING = (
    "P T R Clerk of the House of Representatives • Legislative Resource Center "
    "Name: Hon. Mark Alford Status: Member State/District: MO04 "
    "ID Owner Asset Transaction Type Date Notification Date Amount Cap. Gains > $200? "
    "Amazon.com, Inc. - Common Stock (AMZN) [ST] S (partial) 03/16/2026 03/16/2026 "
    "$1,001 - $15,000 F S "
    "Ferguson Enterprises Inc. Common Stock (FERG) [ST] P 12/12/2025 01/06/2026 "
    "$15,001 - $50,000 F "
    "US Treasury Note 3.5% DUE 1/31/30 (91282CGJ4) [GS] P 03/24/2026 04/08/2026 "
    "$15,001 - $50,000 F"
)


def _rows(text=FILING):
    return [m.groupdict() for m in congress._ROW.finditer(text)]


def test_it_reads_the_trades_out_of_a_filing():
    rows = _rows()
    tickers = [r["ticker"] for r in rows]
    assert "AMZN" in tickers and "FERG" in tickers


def test_a_bond_cusip_does_not_become_a_ticker():
    """The same table carries Treasuries, and a CUSIP sits in the parentheses
    a ticker sits in. `91282CGJ4` parsed as a symbol would be a security that
    does not exist, attributed to a real member."""
    assert "91282CGJ4" not in [r["ticker"] for r in _rows()]
    # And it is excluded by asset class as well as by shape.
    assert "GS" not in congress._EQUITY_KINDS


def test_a_purchase_and_a_sale_are_told_apart():
    rows = {r["ticker"]: r for r in _rows()}
    assert rows["FERG"]["tx"] == "P"
    assert rows["AMZN"]["tx"].startswith("S")


def test_the_amount_is_kept_as_the_band_it_was_filed_as():
    """A filer reports "$1,001 - $15,000", never a figure. Collapsing that to
    a midpoint would invent a number nobody disclosed, so both ends survive
    and the totals are a range."""
    rows = {r["ticker"]: r for r in _rows()}
    assert rows["AMZN"]["low"] == "1,001" and rows["AMZN"]["high"] == "15,000"
    # Asserted against code rather than prose. The module's own comment says
    # why it does not take a midpoint, so grepping the file for the word finds
    # the explanation and fails on it.
    src = open("app/analytics/congress.py", encoding="utf-8").read()
    code = re.sub(r"(?m)^\s*#.*$", "", src)
    assert "amount_low" in code and "amount_high" in code
    assert not re.search(r"amount_(?:low|high)[^\n]*/\s*2", code), \
        "a midpoint is a figure nobody filed"


def test_the_gap_between_trading_and_disclosing_is_reported():
    """Up to 45 days is legal, and the gap is the part a reader should see --
    a trade dated seven weeks before it was filed is not news in the way a
    same-day filing is."""
    assert congress._disclosure_lag("12/12/2025", "01/06/2026") == 25
    assert congress._disclosure_lag("03/16/2026", "03/16/2026") == 0
    assert congress._disclosure_lag("bad", "worse") is None


def test_a_stutter_in_the_clerks_own_record_is_not_shown_to_the_reader():
    """Doc 20035450 is filed under First="Scott Scott". Both the index and the
    PDF say it, so this is the government's typo -- but a reader who sees
    "Scott Scott Franklin" concludes the terminal is broken."""
    got = congress._member_name(
        {"prefix": "Hon.", "first": "Scott Scott", "last": "Franklin", "suffix": ""}, None)
    assert got == "Hon. Scott Franklin"


def test_a_genuine_repeat_in_a_name_survives():
    """Only consecutive repeats of the same word are a stutter."""
    got = congress._member_name(
        {"prefix": "Hon.", "first": "William", "last": "Williams", "suffix": ""}, None)
    assert got == "Hon. William Williams"


def test_an_honorific_in_the_wrong_column_is_dropped():
    got = congress._member_name(
        {"prefix": "Hon.", "first": "John J Mr", "last": "McGuire", "suffix": "III"}, None)
    assert got == "Hon. John J McGuire III"


def test_the_structured_index_is_preferred_over_the_pdf_header():
    """The PDF header is a rendered form; the index is fields. Same content,
    and one of them is already parsed."""
    got = congress._member_name(
        {"prefix": "Hon.", "first": "Pete", "last": "Sessions", "suffix": ""},
        "Hon. Somebody Else")
    assert got == "Hon. Pete Sessions"


def test_it_says_how_much_of_the_record_it_has_read():
    """400 filings is a backlog filled over successive refreshes, not a burst
    fired at a government file server. A partial answer is useful; a partial
    answer that claims to be complete is not."""
    out = congress.summary()
    for key in ("filings_parsed", "filings_known", "complete"):
        assert key in out


def test_the_fetch_is_bounded_and_spaced():
    src = open("app/analytics/congress.py", encoding="utf-8").read()
    assert "FETCH_BUDGET" in src and "if fetched >= budget:" in src
    assert "REQUEST_GAP" in src and "time.sleep(REQUEST_GAP)" in src
    # And it identifies itself to the server it is asking.
    assert "User-Agent" in src


def test_it_says_which_chamber_and_why():
    """The Senate is absent on purpose -- efdsearch gates its search behind an
    acceptance form rather than publishing an archive. Claiming to cover
    Congress while carrying half of it would be the misleading version."""
    out = congress.summary()
    assert out["chamber"] == "house"
    assert "Senate" in out["caveat"]
    assert "45 days" in out["caveat"] or "45" in out["caveat"]


def test_it_is_presented_as_a_record_not_a_signal():
    doc = congress.__doc__ or ""
    assert "Not a signal" in doc


# --------------------------------------------------------------- filtering
#
# Added with the Insiders page, which asks this module the questions a reader
# asks: this member, this side, this fortnight. All of it happens here rather
# than in the browser -- the archive is a thousand rows and the page shows
# sixty, so filtering there would mean shipping everything in order to narrow
# it, and the counts have to describe the narrowed set anyway.

import contextlib
import inspect


TRADES = [
    {"ticker": "MSFT", "side": "buy", "member": "Hon. Kevin Hern", "district": "OK01",
     "traded_iso": "2026-09-10", "filed": "2026-09-20", "disclosure_lag_days": 10,
     "amount_low": 1001, "amount_high": 15000, "asset_kind": "ST",
     "transaction": "purchase", "traded": "09/10/2026", "notified": "09/20/2026",
     "doc_id": "1", "source_url": "u"},
    {"ticker": "MSFT", "side": "sell", "member": "Hon. April McClain Delaney", "district": "MD06",
     "traded_iso": "2026-09-12", "filed": "2026-09-14", "disclosure_lag_days": 2,
     "amount_low": 15001, "amount_high": 50000, "asset_kind": "ST",
     "transaction": "sale", "traded": "09/12/2026", "notified": "09/14/2026",
     "doc_id": "2", "source_url": "u"},
    {"ticker": "AAPL", "side": "sell", "member": "Hon. Kevin Hern", "district": "OK01",
     "traded_iso": "2026-08-01", "filed": "2026-09-30", "disclosure_lag_days": 60,
     "amount_low": 1001, "amount_high": 15000, "asset_kind": "ST",
     "transaction": "sale", "traded": "08/01/2026", "notified": "09/30/2026",
     "doc_id": "3", "source_url": "u"},
    {"ticker": "AAPL", "side": "other", "member": "Hon. Kevin Hern", "district": "OK01",
     "traded_iso": "2026-09-12", "filed": "2026-09-13", "disclosure_lag_days": 1,
     "amount_low": 1001, "amount_high": 15000, "asset_kind": "ST",
     "transaction": "exchange", "traded": "09/12/2026", "notified": "09/13/2026",
     "doc_id": "4", "source_url": "u"},
    # A second buy, by the OTHER member. Without it the archive held exactly one
    # purchase and so did Hern's slice, so a `buys` that counted the whole
    # archive instead of the filtered set returned the same 1 either way and
    # every test here passed. Found by mutating the count to ignore the filter.
    {"ticker": "NVDA", "side": "buy", "member": "Hon. April McClain Delaney", "district": "MD06",
     "traded_iso": "2026-09-11", "filed": "2026-09-15", "disclosure_lag_days": 4,
     "amount_low": 50001, "amount_high": 100000, "asset_kind": "ST",
     "transaction": "purchase", "traded": "09/11/2026", "notified": "09/15/2026",
     "doc_id": "5", "source_url": "u"},
]


@contextlib.contextmanager
def loaded(trades=None):
    """Put rows in the module's store and take them out again.

    Restores whatever was there, so this cannot leave a populated cache behind
    for the parsing tests above -- which assert against an empty one.
    """
    with congress._LOCK:
        before = dict(congress._MEM)
        congress._MEM.update(trades=list(TRADES if trades is None else trades),
                             parsed=5, known=5, at=congress.time.time(),
                             index_at="2026-09-25T00:00:00+00:00")
    try:
        yield
    finally:
        with congress._LOCK:
            congress._MEM.clear()
            congress._MEM.update(before)


def test_the_filters_cannot_be_passed_by_position():
    """This function had two positional parameters and gained five. Earlier in
    the same session a third positional flag added to `_swing_snapshot` bound
    itself to the argument after it and shipped a Dossier panel reading "not
    requested". Keyword-only makes that impossible rather than unlikely."""
    spec = inspect.getfullargspec(congress.summary)
    assert spec.args == ["ticker", "limit"]
    for name in ("member", "side", "since", "until", "activity_days", "top"):
        assert name in spec.kwonlyargs, name


def test_a_member_is_matched_by_substring_and_ignores_case():
    """The filed name carries an honorific and often a middle name and suffix
    -- "Hon. Richard Dean McCormick" -- so an exact match could only ever be
    produced by clicking a name, never by typing one."""
    with loaded():
        assert congress.summary(member="hern")["count"] == 3
        assert congress.summary(member="HERN")["count"] == 3
        assert congress.summary(member="Kevin Hern")["count"] == 3
        assert congress.summary(member="Delaney")["count"] == 2
        assert congress.summary(member="nobody")["count"] == 0


def test_the_date_range_is_inclusive_at_both_ends():
    """A reader who types the 12th on both sides means that day, not the empty
    interval between it and itself."""
    with loaded():
        assert congress.summary(since="2026-09-12", until="2026-09-12")["count"] == 2
        assert congress.summary(since="2026-09-10")["count"] == 4
        assert congress.summary(until="2026-08-01")["count"] == 1


def test_the_range_reads_the_trade_date_not_the_filing_date():
    """They are different dates and the gap runs to weeks. The AAPL sale below
    was traded on 1 August and filed on 30 September; a September filter must
    not return it, because the reader is asking what was traded then."""
    with loaded():
        out = congress.summary(since="2026-09-01")
        assert all(t["traded_iso"] >= "2026-09-01" for t in out["trades"])
        assert not any(t["doc_id"] == "3" for t in out["trades"]), \
            "a filing date was matched against a trade-date filter"


def test_every_count_describes_the_filtered_set():
    """A reader who has narrowed to one member and one month is asking what
    that slice holds. A total that ignored the filter would be answering a
    question nobody asked, while looking authoritative."""
    with loaded():
        out = congress.summary(member="hern")
        assert out["count"] == 3
        assert out["buys"] == 1 and out["sells"] == 1 and out["other"] == 1
        assert out["members"] == 1
        assert out["symbols"] == 2
        # And they really are different numbers from the unfiltered ones, or
        # this test cannot tell a filtered count from a total.
        whole = congress.summary()
        assert whole["count"] == 5 and whole["buys"] == 2 and whole["members"] == 2
        assert {r["ticker"] for r in out["top_tickers"]} == {"MSFT", "AAPL"}


def test_the_third_direction_is_reported_rather_than_folded_in():
    """Neither a buy nor a sell: exchanges and the like. Counting one as the
    other is the same mistake as calling an insider exercise a purchase, which
    this codebase has already made once and written up."""
    with loaded():
        out = congress.summary()
        assert out["other"] == 1
        assert out["buys"] == 2 and out["sells"] == 2 and out["count"] == 5
        assert out["buys"] + out["sells"] + out["other"] == out["count"]


def test_the_activity_series_keeps_its_quiet_days():
    """A bar chart that silently drops empty days compresses a fortnight of
    nothing into the same width as a busy week, and makes a cluster look like
    a trend."""
    with loaded():
        act = congress.summary(activity_days=5)["activity"]
        assert len(act) == 5
        assert [r["date"] for r in act] == sorted(r["date"] for r in act), "newest last"
        assert act[-1]["date"] == "2026-09-12", "the window ends at the latest trade"
        assert any(r["buys"] == 0 and r["sells"] == 0 and r["other"] == 0 for r in act)
        # Four of the five: the August AAPL sale is older than a five-day window.
        assert sum(r["buys"] + r["sells"] + r["other"] for r in act) == 4


def test_the_activity_series_is_keyed_on_the_trade_date():
    """Both dates are real and they answer different questions. This one lines
    up with a price chart, which is what the rest of the row is for."""
    with loaded():
        act = {r["date"]: r for r in congress.summary(activity_days=40)["activity"]}
        assert act["2026-09-12"]["sells"] == 1, "the 12th is a trade date"
        assert act.get("2026-09-14", {}).get("sells", 0) == 0, \
            "the 14th is that trade's FILING date and holds nothing"


def test_the_ranking_is_by_disclosure_count_not_by_money():
    """Amounts are bands, so ranking by money ranks by the width of a band
    somebody else chose: one $1M-$5M sale would outrank ten purchases that say
    far more about what a committee is doing."""
    with loaded():
        top = congress.summary()["top_tickers"]
        # Two at two apiece and one at one. Ties break on the symbol, so the
        # order is stable rather than dependent on insertion.
        assert [r["ticker"] for r in top] == ["AAPL", "MSFT", "NVDA"]
        assert all(top[i]["count"] >= top[i + 1]["count"] for i in range(len(top) - 1))
        row = next(r for r in top if r["ticker"] == "MSFT")
        assert row["buys"] == 1 and row["sells"] == 1
        assert row["members"] == 2, "two different filers traded it"


def test_the_ranking_survives_being_turned_into_json():
    """`members` is counted with a set and a set is not JSON. Returning one
    would 500 the endpoint rather than the function."""
    import json
    with loaded():
        json.dumps(congress.summary())


def test_the_lag_is_reported_as_a_median():
    """One filing 476 days late -- there is one in the live archive -- drags a
    mean and tells the reader nothing about the usual case.

    The median proper, not `lags[len // 2]`: on an even count that is the
    upper-middle, which for these four lags answers 10 where the median is 6.
    The first version of this returned that and this test caught it."""
    with loaded():
        out = congress.summary()
        lags = sorted(t["disclosure_lag_days"] for t in TRADES)
        assert lags == [1, 2, 4, 10, 60]
        assert out["lag_median"] == 4
        assert out["lag_max"] == 60


def test_an_unfiltered_call_is_unchanged():
    """The page that existed before this asks for a ticker and a limit and
    must get exactly what it got."""
    with loaded():
        a = congress.summary(ticker="MSFT", limit=1)
        assert a["count"] == 2 and len(a["trades"]) == 1
        assert a["trades"][0]["ticker"] == "MSFT"
