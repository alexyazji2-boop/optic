"""Revenue and operating income by segment, product and geography.

`sec_facts` already read SEC's companyfacts API for thirteen years of
consolidated quarterly revenue. This is the question that API cannot answer, and
the measurement is the reason the module exists: companyfacts publishes one value
per (tag, period, unit) with no dimensions at all, and probed on Meta it returns
five namespaces — dei, ecd, ffd, srt, us-gaap — with no custom namespace
whatsoever. A segment figure is simply absent from it.

So this reads each filing's XBRL instance document, where every fact carries its
full context. Validated against a paid terminal's own screenshot of the same
company: Family of Apps revenue and operating income, Reality Labs, advertising
against other revenue, and all four geographies match to the cent across twelve
quarters — including the four fourth quarters this module derives rather than
reads.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.analytics import segments

ROOT = Path(__file__).resolve().parent.parent
APP_JS = (ROOT / "static" / "app.js").read_text()
STYLES = (ROOT / "static" / "styles.css").read_text()
MAIN_PY = (ROOT / "app" / "main.py").read_text()
SRC = (ROOT / "app" / "analytics" / "segments.py").read_text()


# ------------------------------------------------------------- the vocabulary

def test_the_axes_are_standard_not_company_extensions():
    """What makes this work for any filer rather than only for the one it was
    built against. All three are us-gaap or srt axes."""
    for axis in segments.AXES:
        assert axis["axis"].endswith("Axis")
        assert not axis["axis"].startswith("meta")
    ids = [a["id"] for a in segments.AXES]
    assert ids == ["segment", "product", "geography"], ids


def test_revenue_reuses_the_tag_list_that_already_exists():
    """Revenue has lived under at least six us-gaap tags and companies switch
    mid-history — sec_facts documents that and owns the list."""
    revenue = segments.METRIC_BY_ID["revenue"]
    from app.analytics import sec_facts
    assert revenue["tags"] is sec_facts.REVENUE_TAGS


@pytest.mark.parametrize("raw,expected", [
    ("us-gaap:USCanadaMember", "US Canada"),
    ("meta:FamilyOfAppsMember", "Family Of Apps"),
    ("meta:RealityLabsMember", "Reality Labs"),
    ("us-gaap:AdvertisingMember", "Advertising"),
    ("us-gaap:EuropeMember", "Europe"),
])
def test_a_member_reads_as_words(raw, expected):
    """"USCanadaMember" needs two splits, not one: an acronym followed by a word
    has no lowercase at the boundary, so the first version left "USCanada"."""
    assert segments._member(raw) == expected


# ------------------------------------------------- which facts count as a row

def test_a_fact_carrying_an_untracked_axis_is_skipped():
    """254 of 270 contexts on Meta's 10-Q are dimensioned and most of them are
    fair-value hierarchies, award types and equity components."""
    block = SRC.split("def parse_instance(", 1)[1].split("\ndef ", 1)[0]
    assert "len(ours) != len(dims)" in block


def test_a_multi_axis_fact_contributes_to_each_of_its_tables():
    """The first version required exactly one dimension, and Meta tags
    advertising revenue with BOTH ProductOrServiceAxis and
    StatementBusinessSegmentsAxis — so the product breakdown, the largest line
    in the company, was silently missing from the panel entirely."""
    block = SRC.split("def parse_instance(", 1)[1].split("\ndef ", 1)[0]
    assert "for axis_id in ours:" in block
    assert '"cross": len(ours)' in block


def test_a_directly_reported_figure_beats_a_cross_tab_sum():
    """Both can feed one slot: Family of Apps revenue is tagged on its own AND
    as two product cells that sum to the same thing. Mixing them in one dict
    made the answer depend on which fact the parser reached first — measured,
    Family of Apps came out as 59.36B, which is advertising alone, where the
    company reported 60.37B. The other ordering gives 119.7B."""
    block = SRC.split("def build(", 1)[1]
    assert "direct[slot] if slot in direct else summed[slot]" in block
    assert "summed[slot] = round(summed.get(slot, 0.0)" in block


def test_cross_tab_cells_are_summed_within_one_filing_only():
    """Across filings the same quarter reappears as a restatement and would
    double."""
    block = SRC.split("def build(", 1)[1]
    assert block.index("direct: Dict") > block.index("for entry in rows:")


def test_a_restatement_is_resolved_to_the_newest_filing():
    block = SRC.split("def build(", 1)[1]
    assert "cells.setdefault(slot, value)" in block


def test_only_quarters_and_years_are_kept():
    """A filing reports the quarter and the year-to-date. A six-month or
    nine-month cumulative in a quarterly column would be nonsense."""
    block = SRC.split("def parse_instance(", 1)[1].split("\ndef ", 1)[0]
    assert "Q_MIN <= span <= Q_MAX" in block
    assert "Y_MIN <= span <= Y_MAX" in block
    assert segments.Q_MAX < segments.Y_MIN


# --------------------------------------------------------- the fourth quarter

def test_the_fourth_quarter_is_derived():
    """A 10-K reports the full year, so without this every fiscal year has a
    hole in its fourth column. Validated against a paid terminal: Family of Apps
    58.94B, Reality Labs 955M, and operating income 30.77B and -6.02B for Q4
    2025, all four derived rather than read, all four matching."""
    cells = {
        ("revenue|segment|A", "year", "2025-12-31"): 100.0,
        ("revenue|segment|A", "quarter", "2025-03-31"): 20.0,
        ("revenue|segment|A", "quarter", "2025-06-30"): 25.0,
        ("revenue|segment|A", "quarter", "2025-09-30"): 30.0,
    }
    out, derived = segments._fill_fourth_quarters(dict(cells))
    assert derived == 1
    assert out[("revenue|segment|A", "quarter", "2025-12-31")] == 25.0


def test_a_year_missing_a_quarter_is_left_alone():
    """Subtracting two quarters from a year gives a six-month figure in a
    quarterly column, which is worse than a gap."""
    cells = {
        ("revenue|segment|A", "year", "2025-12-31"): 100.0,
        ("revenue|segment|A", "quarter", "2025-03-31"): 20.0,
        ("revenue|segment|A", "quarter", "2025-06-30"): 25.0,
    }
    out, derived = segments._fill_fourth_quarters(dict(cells))
    assert derived == 0
    assert ("revenue|segment|A", "quarter", "2025-12-31") not in out


def test_a_reported_fourth_quarter_is_not_overwritten():
    cells = {
        ("revenue|segment|A", "year", "2025-12-31"): 100.0,
        ("revenue|segment|A", "quarter", "2025-03-31"): 20.0,
        ("revenue|segment|A", "quarter", "2025-06-30"): 25.0,
        ("revenue|segment|A", "quarter", "2025-09-30"): 30.0,
        ("revenue|segment|A", "quarter", "2025-12-31"): 99.0,
    }
    out, derived = segments._fill_fourth_quarters(dict(cells))
    assert derived == 0
    assert out[("revenue|segment|A", "quarter", "2025-12-31")] == 99.0


def test_quarters_from_another_series_are_not_borrowed():
    """Keyed on the series, so Reality Labs' quarters cannot be subtracted from
    Family of Apps' year."""
    cells = {
        ("revenue|segment|A", "year", "2025-12-31"): 100.0,
        ("revenue|segment|B", "quarter", "2025-03-31"): 20.0,
        ("revenue|segment|B", "quarter", "2025-06-30"): 25.0,
        ("revenue|segment|B", "quarter", "2025-09-30"): 30.0,
    }
    _out, derived = segments._fill_fourth_quarters(dict(cells))
    assert derived == 0


# ------------------------------------------------------------------- the cost

def test_parsing_is_capped_and_cached():
    """An instance document is about a megabyte and the last nine filings are
    nine of them."""
    assert segments.PARSE_BUDGET <= 5
    block = SRC.split("def build(", 1)[1]
    assert "fetched >= max(0, int(budget))" in block
    assert "unread += 1" in block
    assert 'feeds.store_json(key, parsed)' in block
    assert 'feeds.cached_json(key)' in block


def test_the_panel_reports_what_it_has_not_read():
    for key in ("filings_listed", "filings_read", "filings_unread", "q4_derived"):
        assert f'"{key}"' in SRC, key
    assert "filings_unread" in APP_JS


def test_the_instance_url_is_derived_not_listed():
    """The folder listing is a second request per filing, and inline XBRL has
    named the instance after the primary document since 2019."""
    block = SRC.split("def filings(", 1)[1].split("\ndef ", 1)[0]
    assert '_htm.xml' in block
    assert "index.json" not in block


def test_the_filing_target_is_honest_about_its_ceiling():
    """EDGAR's submissions block holds the most recent filings of every type,
    and older ones are in paginated archives this does not fetch. Measured on
    Meta: nine 10-Qs and 10-Ks in that block, twelve quarters after deriving."""
    assert "paginated archives" in SRC


# ---------------------------------------------------------------- the honesty

def test_the_missing_kpis_are_stated_rather_than_faked():
    """Meta's custom namespace was enumerated across both its latest 10-Q and
    10-K: 35 and 42 tags, every one an accounting extension, and zero
    occurrences of DailyActive, MonthlyActive or ActivePeople in either."""
    assert '"kpis": None' in SRC
    note = SRC.split('"kpi_note": (', 1)[1][:700]
    assert "not in the filings" in note
    assert "press release" in note
    assert "kpi_note" in APP_JS, "the panel does not say the KPIs are absent"


def test_it_says_what_it_cannot_see():
    assert "reports one segment" in segments.BLIND
    assert "prose" in segments.BLIND
    assert "companyfacts" in segments.METHOD
    assert "annual figure minus" in segments.METHOD


def test_a_missing_contact_address_is_named_as_configuration(monkeypatch):
    from app import feeds as feeds_mod
    monkeypatch.setattr(feeds_mod, "CONTACT_OK", False)
    out = segments.filings("META")
    assert out["available"] is False
    assert out.get("needs_contact") is True
    assert "FEED_CONTACT" in out["reason"]


def test_a_junk_symbol_never_reaches_a_url(monkeypatch):
    from app import feeds as feeds_mod

    def boom(*a, **k):                    # noqa: ANN002, ANN003
        raise AssertionError("junk reached the request")
    monkeypatch.setattr(feeds_mod, "fetch_json", boom)
    for junk in ("../etc", "a b", "'; DROP", "waytoolongsymbol"):
        out = segments.filings(junk)
        assert out["available"] is False, junk
        assert "symbol" in out["reason"], junk


# -------------------------------------------------------------------- the UI

def test_the_endpoint_exists():
    assert '@app.get("/api/segments/{ticker}")' in MAIN_PY


def test_it_does_not_ride_on_the_ticker_payload():
    """Nine megabytes of XBRL would make every ticker load wait on EDGAR."""
    body = APP_JS.split("async function loadSegments(", 1)[1].split("\n}\n", 1)[0]
    assert "/api/segments/" in body
    fin = APP_JS.split("function renderFinancialsView(", 1)[1].split("\nfunction ", 1)[0]
    assert "loadSegments(force)" in fin
    assert 'id="seg-host"' in fin


def test_a_slow_response_cannot_land_on_another_symbol():
    """Nine megabytes is not a fast request, and the reader may load something
    else while it runs."""
    body = APP_JS.split("async function loadSegments(", 1)[1].split("\n}\n", 1)[0]
    assert "if (STATE.segmentsFor !== STATE.ticker) return;" in body


def test_a_negative_segment_is_normal_not_an_error():
    """Reality Labs has lost money every quarter it has been reported. It gets
    the directional red and nothing louder."""
    assert re.search(r"\.seg-table td\.num\.neg", STYLES)
    body = APP_JS.split("function segmentCell(", 1)[1].split("\nfunction ", 1)[0]
    assert "v < 0 ? ' neg' : ''" in body


def test_a_missing_cell_is_a_dash_not_a_zero():
    body = APP_JS.split("function segmentCell(", 1)[1].split("\nfunction ", 1)[0]
    assert "v === null || v === undefined" in body


def test_the_quarter_label_carries_the_real_date():
    """The label is a calendar quarter derived from the period end, which is
    wrong for a filer whose fiscal year ends in January — so the date itself is
    in the title attribute."""
    body = APP_JS.split("function segmentQuarterLabel(", 1)[1].split("\nfunction ", 1)[0]
    assert 'title="${esc(iso)}"' in body
    assert "Not fiscal" in body


def test_the_wide_table_scrolls_sideways():
    """Twelve quarters plus a label column does not fit a panel."""
    body = APP_JS.split("function renderSegments(", 1)[1].split("\nasync function ", 1)[0]
    assert 'class="table-scroll"' in body
