"""A segment table that does not add up is not shown as shares of a whole.

Seen on NVDA's Financials tab on 26 October 2026: operating income by segment
listed Compute & Networking 130.1B, Graphics 9.2B and a positive 139.3B
"Corporate, not in a segment", parts adding to 278.6B against 130.4B reported,
each with a percentage of that sum. The filing explains it. NVIDIA tags the
reconciliation table's first line, "total segment operating income", with
CorporateNonSegmentMember, and files the items that take it down to the
reported figure under their own concepts. The fixture is an excerpt of that
10-K's XBRL instance with the values as filed."""

from __future__ import annotations

from pathlib import Path

import pytest

from app import feeds, segment_store
from app.analytics import segments
from tests.test_v2_dataviz import fv

FIX = Path(__file__).parent / "fixtures" / "nvda_10k_fy2026_segments_excerpt.xml"
FIX_Q = Path(__file__).parent / "fixtures" / "nvda_10q_2026-07-26_segments_excerpt.xml"
YEAR, QUARTER = "2026-01-25", "2026-07-26"


@pytest.fixture
def nvda(tmp_path, monkeypatch):
    monkeypatch.setattr(segment_store, "DB_PATH", str(tmp_path / "segments.db"))
    monkeypatch.setattr(feeds, "CACHE_PATH", str(tmp_path / "feed_cache.json"))
    monkeypatch.setattr(feeds, "_MEM", {})
    monkeypatch.setattr(feeds, "_DISK", {})
    monkeypatch.setattr(segments, "_SHARED_CLEARED", False)
    monkeypatch.setattr(feeds, "fetch_text",
                        lambda url, *a, **k: (FIX_Q if "20260726" in url else FIX).read_text())
    monkeypatch.setattr(segments, "filings", lambda ticker, force=False: {
        "available": True, "cik": "0001045810", "ticker": "NVDA",
        "rows": [{"accession": "0001045810-26-000075", "form": "10-Q", "period": QUARTER, "filed": "2026-08-26",
                  "instance_url": "https://example.test/nvda-20260726_htm.xml"},
                 {"accession": "0001045810-26-000021", "form": "10-K", "period": YEAR, "filed": "2026-02-25",
                  "instance_url": "https://example.test/nvda-20260125_htm.xml"}]})
    return segments.build("NVDA")


def _table(out, metric):
    return next(t for t in out["tables"] if t["axis"] == "segment" and t["metric"] == metric)


def _year(t):
    ends = t["annual"]["ends"]
    return {r["member"]: r["values"][ends.index(YEAR)] for r in t["annual"]["rows"]}



def test_the_parse_sees_the_corporate_line_as_filed(monkeypatch):
    monkeypatch.setattr(feeds, "fetch_text", lambda *a, **k: FIX.read_text())
    facts = segments.parse_instance("https://example.test/x_htm.xml")["facts"]
    op = {f["member"]: f["value"] for f in facts if f["metric"] == "operating_income" and f["kind"] == "year"}
    assert op["Compute and Networking"] == 130141e6 and op["Graphics"] == 9156e6
    assert op["Corporate, not in a segment"] == 139297e6 == op["Compute and Networking"] + op["Graphics"]


def test_the_subtotal_is_left_out_and_the_table_says_why(nvda):
    t = _table(nvda, "operating_income")
    year = _year(t)
    assert set(year) == {"Compute and Networking", "Graphics"}, "no 139.3B corporate row"
    assert sum(year.values()) == 139297e6
    gone = {(x["kind"], x["end"]): x["value"] for x in t["subtotals_removed"]}
    assert gone == {("year", YEAR): 139297e6, ("quarter", QUARTER): 66595e6}, "the 10-Q tags it the same way"
    q = {r["member"]: r["values"][nvda["quarters"].index(QUARTER)] for r in t["rows"]}
    assert q == {"Compute and Networking": 62696e6, "Graphics": 3899e6}
    assert "segments' own total" in t["notes"][0] and "Corporate, not in a segment" in t["notes"][0]


def test_the_gap_to_the_reported_figure_is_the_filings_own_reconciling_items():
    import re
    body = FIX.read_text()

    def fact(tag, ctx_member):
        for m in re.finditer(r'<us-gaap:%s contextRef="([^"]+)"[^>]*>([-\d.]+)<' % tag, body):
            ctx = re.search(r'<xbrli:context id="%s">(.*?)</xbrli:context>' % re.escape(m.group(1)), body).group(1)
            if (ctx_member in ctx) if ctx_member else ("explicitMember" not in ctx):
                return float(m.group(2))
        raise AssertionError(tag)

    reported = fact("OperatingIncomeLoss", None)
    items = (fact("AllocatedShareBasedCompensationExpense", "CorporateNonSegmentMember")
             + fact("UnallocatedCorporateOperatingExpendituresAndOtherExpenses", "CorporateNonSegmentMember")
             + fact("AcquisitionRelatedAndOtherCosts", "CorporateNonSegmentMember"))
    assert reported == 130387e6
    assert round(139297e6 - items) == reported, "segments less the filed reconciling items is the reported total"


def test_revenue_by_segment_still_reconciles_and_keeps_every_segment(nvda):
    year = _year(_table(nvda, "revenue"))
    assert set(year) == {"Compute and Networking", "Graphics"} and sum(year.values()) == 215938e6
    assert _table(nvda, "revenue")["subtotals_removed"] == []


def test_a_genuine_reconciling_line_is_kept_negative_or_not():
    labels = {"o|segment|A": {"metric": "o", "axis": "segment", "member": "A"},
              "o|segment|B": {"metric": "o", "axis": "segment", "member": "B"},
              "o|segment|Intersegment Elimination": {"metric": "o", "axis": "segment",
                                                     "member": "Intersegment Elimination"},
              "o|segment|Corporate, not in a segment": {"metric": "o", "axis": "segment",
                                                        "member": "Corporate, not in a segment"}}
    # Intel-shaped, in dollars as filed: eliminations and corporate costs are real lines
    cells = {("o|segment|A", "quarter", "2026-06-27"): 5000e6, ("o|segment|B", "quarter", "2026-06-27"): -1000e6,
             ("o|segment|Intersegment Elimination", "quarter", "2026-06-27"): -300e6,
             ("o|segment|Corporate, not in a segment", "quarter", "2026-06-27"): -1200e6}
    assert segments._drop_segment_subtotals(cells, labels) == []
    assert len(cells) == 4


def test_the_page_gives_no_shares_unless_the_parts_add_up(tmp_path):
    got = fv(tmp_path, """
      const usd = F.moneyIn('USD');
      const fixed = F.composition(['Compute and Networking', 'Graphics'], [130141e6, 9156e6], 130387e6);
      const before = F.composition(['Compute and Networking', 'Graphics', 'Corporate, not in a segment'], [130141e6, 9156e6, 139297e6], 130387e6);
      const geo = F.composition(['United States', 'Taiwan', 'Other'], [100e9, 80e9, 35.9e9], 215.9e9);
      const none = F.composition(['A', 'B'], [60, 40], null);
      const apple = F.composition(['Mac', 'Product', 'Service', 'Wearables', 'iPad', 'iPhone'], [33708e6, 307003e6, 109158e6, 35686e6, 28023e6, 209586e6], 416161e6);
      print(JSON.stringify({ fixed: [fixed.canShare, fixed.reconciles, F.compositionLine(fixed, 'Operating income', 'FY2026', usd)],
        before: [before.canShare, before.reconciles], geo: [geo.canShare, F.compositionLine(geo, 'Revenue', 'FY2026', usd)], none: none.canShare, graphics: fixed.dropped, apple: apple.dropped }));
    """)
    assert got["fixed"][:2] == [False, False]
    assert "against $130.4B reported" in got["fixed"][2] and "no shares of the total are shown" in got["fixed"][2]
    assert "%" not in got["fixed"][2]
    assert got["before"] == [False, False], "even before the server fix, 278.6B is not a whole to take shares of"
    assert got["geo"][0] is True and "% of revenue" in got["geo"][1]
    assert got["none"] is False, "no reported total to check against: no shares"
    assert got["graphics"] == [], "Graphics is not a total of other lines"
    assert got["apple"] == ["Product"], "Apple's Product still is"


def test_the_financials_tab_prints_the_tables_notes():
    src = (Path(__file__).parent.parent / "static" / "v2" / "js" / "pages" / "financials.js").read_text()
    assert "(t.notes || [])" in src
