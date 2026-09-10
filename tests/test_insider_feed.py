"""Form 4 filings across the market, timestamped.

The terminal already showed insider transactions for one loaded ticker, from
yfinance, with a date and no time. This is the other question — who is buying
anything, right now — and it comes from the filings themselves: EDGAR's live
index gives an acceptance timestamp to the second, and the form carries the
issuer's ticker, the insider's name and role, the transaction date, the SEC's
code, the share count and the price.

**The test that matters most here is the one about grants.** Form 4 code A is
compensation, frequently at a stated price of $0.00. The first filing read while
building this was 51,606 shares at zero, which presented as an "insider buy"
reads as enormous conviction and is in fact a payslip. Measured on a live run:
8 of 46 filed transactions were open-market purchases. Showing all 46 as insider
buying would have been wrong about 38 of them.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app import insiders

ROOT = Path(__file__).resolve().parent.parent
APP_JS = (ROOT / "static" / "app.js").read_text()
STYLES = (ROOT / "static" / "styles.css").read_text()
MAIN_PY = (ROOT / "app" / "main.py").read_text()


# ------------------------------------------------------------ codes and truth

def test_only_an_open_market_purchase_counts_as_a_buy():
    buys = [k for k, v in insiders.CODES.items() if v["buy"]]
    assert buys == ["P"], buys


def test_a_grant_is_explicitly_not_a_purchase():
    grant = insiders.CODES["A"]
    assert grant["buy"] is False
    assert "not a purchase" in grant["note"].lower()


def test_every_code_is_explained():
    for code, meta in insiders.CODES.items():
        assert meta["label"], code
        assert "buy" in meta, code


def test_the_default_view_is_purchases_only():
    """8 of 46 on a live run. The default has to be the 8."""
    import inspect
    sig = inspect.signature(insiders.latest)
    assert sig.parameters["only_purchases"].default is True
    assert "insiderPurchasesOnly = true" in APP_JS


# --------------------------------------------------------------- the index

def test_the_index_is_restricted_by_owner_not_by_type():
    """Measured: `type=4` alone returns 424B2 prospectuses and 485BXT fund
    filings, 36 of 40 rows on the run that found it. `owner=only` is what
    restricts it to ownership forms."""
    assert "owner=only" in insiders.INDEX_URL
    assert "action=getcurrent" in insiders.INDEX_URL


def test_one_filing_is_listed_once():
    """EDGAR lists each filing once per party — the issuer as "(Filer)" and the
    insider as "(Reporting)", same accession. Without deduping, every
    transaction rendered twice: eight filings read produced sixteen index rows
    and every row on the panel appeared in a pair."""
    body = APP_JS  # the dedupe is server-side; assert it there
    src = (ROOT / "app" / "insiders.py").read_text()
    block = src.split("def index(", 1)[1].split("\ndef ", 1)[0]
    assert "if acc in seen:" in block
    assert "seen.add(acc)" in block


def test_amendments_are_kept_and_other_forms_are_not():
    src = (ROOT / "app" / "insiders.py").read_text()
    block = src.split("def index(", 1)[1].split("\ndef ", 1)[0]
    assert '("4", "4/A")' in block


def test_the_index_gets_a_longer_timeout_than_a_feed():
    """browse-edgar is a CGI script rather than a static file and took longer
    than the feed module's twelve-second default, which reported it as down."""
    assert insiders.INDEX_TIMEOUT > 12
    src = (ROOT / "app" / "insiders.py").read_text()
    assert "timeout=INDEX_TIMEOUT" in src


# ------------------------------------------------------------- the enrichment

def test_the_work_is_capped_per_call():
    """Forty filings at the polite gap is half a minute. A panel may not cost
    that, so a cold cache returns what it managed and says what it has not
    read."""
    assert insiders.ENRICH_BUDGET <= 20
    src = (ROOT / "app" / "insiders.py").read_text()
    block = src.split("def latest(", 1)[1]
    assert "fetched >= max(0, int(budget))" in block
    assert "unread += 1" in block


def test_the_unread_count_is_reported():
    src = (ROOT / "app" / "insiders.py").read_text()
    for key in ("filings_listed", "filings_read", "filings_unread", "filings_failed"):
        assert f'"{key}"' in src, key
    assert "filings_unread" in APP_JS, "the panel does not say what it has not read"


def test_a_parsed_filing_is_cached_and_a_failure_too():
    """A filing is immutable once accepted, so re-reading one is pure waste —
    and a malformed one must not be refetched on every poll for a week."""
    src = (ROOT / "app" / "insiders.py").read_text()
    assert "feeds.store_json(\"insider:parsed:\" + acc" in src
    block = src.split("def latest(", 1)[1]
    assert block.index("feeds.store_json") < block.index('if not parsed.get("available")')


def test_the_filing_is_read_in_one_request():
    """The XML's filename is unpredictable ("wk-form4_1789056227.xml"), so
    listing the folder first was a second request per filing for nothing."""
    body = (ROOT / "app" / "insiders.py").read_text()
    block = body.split("def parse_filing(", 1)[1].split("\ndef ", 1)[0]
    assert '.txt"' in block
    assert "index.json" not in block


# ------------------------------------------------------------------ parsing

def test_a_zero_price_grant_reports_no_value_rather_than_zero():
    """$0 reads as a data fault. Absent reads as what it is."""
    body = (ROOT / "app" / "insiders.py").read_text()
    block = body.split("def parse_filing(", 1)[1].split("\ndef ", 1)[0]
    assert "if shares is not None and price else None" in block


def test_both_timestamps_survive_to_the_row():
    """EDGAR's acceptance time and the date the insider reported. Different
    facts: a purchase made on Monday and filed on Wednesday is news on
    Wednesday."""
    body = (ROOT / "app" / "insiders.py").read_text()
    block = body.split("def latest(", 1)[1]
    assert '"filed_at": entry.get("filed_at")' in block
    assert 'r.get("filed_at")' in block and 'r.get("date")' in block


def test_the_sort_is_by_filing_then_trade_date():
    """Filing time first: a purchase made on Monday and filed on Wednesday
    belongs at Wednesday's position, which is when anyone could know about it."""
    body = (ROOT / "app" / "insiders.py").read_text()
    assert '(r.get("filed_at") or "", r.get("date") or "")' in body
    assert "reverse=True" in body.split("rows.sort(", 1)[1][:200]


def test_the_roles_are_read_from_the_relationship_block():
    body = (ROOT / "app" / "insiders.py").read_text()
    block = body.split("def parse_filing(", 1)[1].split("\ndef ", 1)[0]
    for role in ("isDirector", "isOfficer", "isTenPercentOwner", "otherText"):
        assert role in block, role


def test_it_says_what_it_cannot_see():
    """Read by value, not by searching the source.

    CLAUDE.md: an implicitly-concatenated Python string is not in the file as
    one string, so a source search for "two business days" finds nothing while
    the sentence reads perfectly on the page. An earlier version of this test
    failed for exactly that reason, which is why METHOD and BLIND are constants.
    """
    assert "two business days" in insiders.BLIND, "the reporting lag is the main caveat"
    assert "10b5-1" in insiders.BLIND, "a scheduled sale is not a decision to sell now"
    assert "acceptance time" in insiders.METHOD


# ------------------------------------------------------------------- the UI

def test_the_endpoint_exists():
    assert '@app.get("/api/insiders/latest")' in MAIN_PY


def test_the_row_shows_a_date_and_a_time():
    """Asked for explicitly, and a filing at 09:31 and one at 15:58 are
    differently interesting on the same day."""
    body = APP_JS.split("function insiderWhen(", 1)[1].split("\nfunction ", 1)[0]
    assert "dayIn(iso, zone)" in body
    assert "timeIn(iso, zone)" in body
    assert "zoneAbbrev(zone)" in body


@pytest.mark.parametrize("attr,handler", [
    ("data-ins-only", "insiderPurchasesOnly"),
    ("data-ins-refresh", "loadInsiderFeed(true)"),
])
def test_every_control_has_a_handler(attr, handler):
    assert f"closest('[{attr}]')" in APP_JS, f"{attr} has no handler"
    block = APP_JS.split(f"closest('[{attr}]')", 1)[1][:500]
    assert handler in block


def test_the_feed_loads_with_the_read_view():
    block = APP_JS.split("function loadView(view, force) {", 1)[1].split("\nfunction ", 1)[0]
    assert "loadInsiderFeed(force)" in block


def test_it_does_not_ride_on_the_brief_payload():
    """The brief is one shared build per day; this is live. Binding them would
    have made the day's read wait on EDGAR."""
    assert "id=\"insider-host\"" in APP_JS
    body = APP_JS.split("async function loadInsiderFeed(", 1)[1].split("\nfunction ", 1)[0]
    assert "/api/insiders/latest" in body


def test_a_grant_takes_no_directional_colour():
    """Colour cannot carry a meaning the row contradicts — the VIX lesson. A
    grant is neither a buy nor a sell."""
    body = APP_JS.split("function insiderFeedRow(", 1)[1].split("\nfunction ", 1)[0]
    assert "r.is_purchase ? 'up'" in body
    assert "r.acquired ? '' : 'down'" in body


def test_the_per_ticker_panel_points_at_the_market_wide_one():
    assert "Every Form 4 as it is filed, across the market" in APP_JS


def test_the_wide_table_scrolls_sideways():
    """Eight columns including two dates overflowed the panel and the price
    column was cut off mid-figure."""
    body = APP_JS.split("function renderInsiderFeed(", 1)[1].split("\nasync function ", 1)[0]
    assert 'class="scroll-y table-scroll"' in body


@pytest.mark.parametrize("cls", [".ins-t", ".ins-clock", ".ins-role", ".ins-code"])
def test_the_feed_is_styled(cls):
    assert re.search(re.escape(cls) + r"[\s,{:.]", STYLES), f"{cls} has no rule"
