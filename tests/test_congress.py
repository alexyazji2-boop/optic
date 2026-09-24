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
