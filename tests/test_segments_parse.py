"""`parse_instance`, driven against XBRL rather than read as source.

The rest of `tests/test_segments.py` asserts on the module's text, which is the
right tool for the vocabulary and the wrong one here: whether a fact survives
the filter is a conjunction of four conditions, and a regex cannot tell a
correct one from an inverted one. The defect this file was written for proves
the point -- the source said `len(ours) != len(dims)`, which reads sensible and
threw away most of the table.

**What went wrong.** `ConsolidationItemsAxis` was treated as one more untracked
axis. Measured on Intel's June 2026 10-Q, of the facts carrying
`StatementBusinessSegmentsAxis`:

    20 revenue          + ConsolidationItemsAxis   -> dropped
    12 operating income + ConsolidationItemsAxis   -> dropped
     8 operating income alone                      -> kept
     4 revenue          + ProductOrServiceAxis     -> kept

So the revenue table rendered one row, Intel Foundry, against the six segments
Intel reports. The axis is not a breakdown: it says what *sort of line* a
figure is, and it co-occurs with segment reporting by design.

After the fix the whole table matches a paid terminal's own screenshot of the
same company to the cent -- Data Center and AI, Intel Foundry, All Other,
intersegment eliminations and corporate unallocated, across five quarters.
"""

from __future__ import annotations

import pytest

from app import feeds
from app.analytics import segments

USD = "usd"
URL = "https://example.test/fake-instance.xml"

# A quarter: 91 days, inside Q_MIN..Q_MAX.
START, END = "2026-03-29", "2026-06-27"


def _ctx(cid, dims):
    members = "".join(
        '<xbrldi:explicitMember dimension="{}">{}</xbrldi:explicitMember>'.format(k, v)
        for k, v in dims.items())
    return (
        '<xbrli:context id="{cid}">'
        '<xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">'
        '0000050863</xbrli:identifier>'
        '{seg}</xbrli:entity>'
        '<xbrli:period><xbrli:startDate>{s}</xbrli:startDate>'
        '<xbrli:endDate>{e}</xbrli:endDate></xbrli:period>'
        '</xbrli:context>'
    ).format(cid=cid, s=START, e=END,
             seg='<xbrli:segment>{}</xbrli:segment>'.format(members) if members else "")


SEG = "us-gaap:StatementBusinessSegmentsAxis"
CONS = "us-gaap:ConsolidationItemsAxis"
PROD = "us-gaap:ProductOrServiceAxis"
FAIR = "us-gaap:FairValueByFairValueHierarchyLevelAxis"

CONTEXTS = {
    # The shape Intel actually files: the segment figure is qualified as an
    # operating segment, and that qualifier was what disqualified it.
    "c-dcai":   {CONS: "us-gaap:OperatingSegmentsMember", SEG: "intc:DatacenterAndAIMember"},
    "c-foundry": {CONS: "us-gaap:OperatingSegmentsMember", SEG: "intc:IntelFoundryMember"},
    # Reconciling lines. No segment of their own, which is why they need to
    # become rows in their own right or the column does not add up.
    "c-elim":   {CONS: "us-gaap:IntersegmentEliminationMember"},
    "c-corp":   {CONS: "us-gaap:CorporateNonSegmentMember"},
    # A consolidation member this does not understand. Inventing a row for it
    # would put a number on the page that belongs to nothing.
    "c-odd":    {CONS: "us-gaap:SomeFutureMember"},
    # The qualifier with no breakdown at all: that is the consolidated total,
    # which the table must not repeat as a row.
    "c-alone":  {CONS: "us-gaap:OperatingSegmentsMember"},
    # Still skipped, and the reason the rule exists in the first place.
    "c-fair":   {FAIR: "us-gaap:FairValueInputsLevel1Member"},
    # Two tracked axes at once still contributes to both tables.
    "c-cross":  {SEG: "intc:IntelFoundryMember", PROD: "intc:AssemblyAndTestMember"},
}

FACTS = [
    ("us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax", "c-dcai", "6260000000"),
    ("us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax", "c-foundry", "5760000000"),
    ("us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax", "c-elim", "-5480000000"),
    ("us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax", "c-odd", "123000000"),
    ("us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax", "c-alone", "12540000000"),
    ("us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax", "c-fair", "999000000"),
    ("us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax", "c-cross", "290000000"),
    ("us-gaap:OperatingIncomeLoss", "c-foundry", "-2090000000"),
    ("us-gaap:OperatingIncomeLoss", "c-corp", "-1420000000"),
]


def _document():
    body = ["<?xml version='1.0' encoding='utf-8'?>",
            '<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" '
            'xmlns:xbrldi="http://xbrl.org/2006/xbrldi" '
            'xmlns:us-gaap="http://fasb.org/us-gaap/2026" '
            'xmlns:intc="http://intel.com/20260627" '
            'xmlns:iso4217="http://www.xbrl.org/2003/iso4217">',
            '<xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>']
    for cid, dims in CONTEXTS.items():
        body.append(_ctx(cid, dims))
    for tag, cid, value in FACTS:
        body.append('<{t} contextRef="{c}" unitRef="{u}" decimals="-6">{v}</{t}>'
                    .format(t=tag, c=cid, u=USD, v=value))
    body.append("</xbrli:xbrl>")
    return "".join(body)


@pytest.fixture
def parsed(monkeypatch):
    monkeypatch.setattr(feeds, "fetch_text",
                        lambda *a, **k: _document())
    out = segments.parse_instance(URL)
    assert out.get("available") is True, out
    return out["facts"]


def _rows(facts, metric, axis="segment"):
    """Directly reported figures only, which is the precedence `build` uses.

    Intel Foundry appears twice on the segment axis: once as its own revenue
    (cross 1) and once as a cell of the segment-by-product cross-tab (cross 2).
    A plain dict comprehension let the 290M cell overwrite the 5.76B figure,
    which is the same mix-up the module records making on Meta -- Family of
    Apps came out as advertising alone. Direct wins; the cross-tab cell is only
    ever the answer for a member not reported on its own."""
    return {f["member"]: f["value"]
            for f in facts
            if f["metric"] == metric and f["axis"] == axis and f["cross"] == 1}


def _cells(facts, metric, axis):
    """The cross-tab cells, which the other half of the rule is about."""
    return {f["member"]: f["value"]
            for f in facts
            if f["metric"] == metric and f["axis"] == axis and f["cross"] > 1}


# --------------------------------------------------- the defect, both halves


def test_a_segment_qualified_as_an_operating_segment_is_kept(parsed):
    """The 20 revenue facts that were being thrown away."""
    rev = _rows(parsed, "revenue")
    assert rev["Datacenter And AI"] == 6_260_000_000
    assert rev["Intel Foundry"] == 5_760_000_000


def test_the_reconciling_lines_become_rows_of_their_own(parsed):
    """A reader adding the segment column needs these to reach the
    consolidated total, which is why the reference terminals print
    "Eliminations from revenue" as a row."""
    assert _rows(parsed, "revenue")["Intersegment Elimination"] == -5_480_000_000
    assert _rows(parsed, "operating_income")["Corporate Non Segment"] == -1_420_000_000


# ------------------------------------------------------ and what stays out


def test_an_unfamiliar_consolidation_member_is_not_invented_into_a_row(parsed):
    """Listed rather than "anything that is not OperatingSegments": an
    unfamiliar member is more likely a slice this does not understand than a
    reconciling item."""
    assert all("Some Future" not in m for m in _rows(parsed, "revenue"))
    assert 123_000_000 not in _rows(parsed, "revenue").values()


def test_the_consolidated_total_is_not_repeated_as_a_row(parsed):
    """`OperatingSegmentsMember` with no breakdown beside it is the total of
    the segments, not a segment. Admitting it would double the column."""
    assert 12_540_000_000 not in _rows(parsed, "revenue").values()


def test_a_fair_value_hierarchy_is_still_skipped(parsed):
    """The rule the original filter was written for, and it still holds. Most
    dimensioned contexts in a filing are nothing to do with segments."""
    assert 999_000_000 not in _rows(parsed, "revenue").values()


def test_a_fact_on_two_tracked_axes_still_feeds_both_tables(parsed):
    """Unchanged by the fix, and worth holding: requiring exactly one
    dimension is what once hid Meta's entire product breakdown."""
    assert _cells(parsed, "revenue", "product")["Assembly And Test"] == 290_000_000
    cross = [f for f in parsed if f["value"] == 290_000_000]
    assert {f["axis"] for f in cross} == {"segment", "product"}
    assert all(f["cross"] == 2 for f in cross), \
        "a cross-tab cell is summed into its row rather than replacing it"


def test_a_reconciling_row_is_not_treated_as_a_cross_tab(parsed):
    """It carries one axis' worth of meaning, so `cross` has to be 1 or the
    build step would add it to itself across filings."""
    elim = [f for f in parsed if f["member"] == "Intersegment Elimination"]
    assert elim and all(f["cross"] == 1 for f in elim)
