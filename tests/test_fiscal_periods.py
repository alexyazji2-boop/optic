"""Fiscal-period labels (owner's Handoff 2, 2026-11-03; app/figures/periods.py, static/v2/js/core/periods.js, ui/period.js).

On 2026-11-03 Apple's Financials page said "Summary, FY25: the fiscal year to Sep 30, 2025" over a Segments block that
said "FY26" and no date. Both were guesses about Apple's calendar: the date was the provider's month-end stand-in for
Saturday, Sep 27, 2025, and every name was worked out from a date on the assumption that a company names its year
after the calendar year it ends in, which named Home Depot's fiscal 2025 "FY26". These tests hold the fix: the
company's fiscal years and quarters come from its own 10-Ks and 10-Qs, every statement and segment block carries a
period line beside its title (the period in words with its end date, a period-type badge, an accounting-basis badge,
the filing), a segment table is reconciled against the filings' own total, nothing is named that no filing names, and
a page that names a period from a date fails here.

The handoff's acceptance tests, in order: the AAPL Segments block (test_acceptance_1_*), no bare FY label in the
Dossier and Compare (test_acceptance_2_*), non-December year ends (test_acceptance_3_*).
"""
import json
import re
from pathlib import Path

import pytest

from app import segment_store
from app.analytics import earnings, fundamentals, segments
from app.figures import compute as res
from app.figures import periods as P
from app.research import quality
from app.valuation import inputs as vi
from tests.test_frontend_v2_stage0 import _run

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "static" / "v2" / "js"
REV = "RevenueFromContractWithCustomerExcludingAssessedTax"
B = 1e9


# ------------------------------------------------------------------------------------------------ the filings
def row(val, start, end, accn, form, fy, fp, filed):
    return {"val": val, "start": start, "end": end, "accn": accn, "form": form, "fy": fy, "fp": fp, "filed": filed}


def filings(rows, cik="0000320193", ifrs=False):
    facts = {"us-gaap": {REV: {"units": {"USD": rows}}}} if rows else {}
    if ifrs:
        facts["ifrs-full"] = {"Revenue": {"units": {"TWD": [row(1.0, "2025-01-01", "2025-12-31", "x", "20-F", 2025, "FY", "2026-04-01")]}}}
    return vi.Filings({"entityName": "Test", "facts": facts}, cik, "2026-11-03T12:00:00+00:00")


# Apple's calendar as filed: 52- or 53-week years ending on the last Saturday of September (FY2023 had 53, its first
# quarter 14). Each 10-K also carries the two years before it under its own fiscal-year focus, as the real ones do, so a
# year must take its name from its own 10-K, never a comparative.
AAPL_YEARS = [  # (fy, start, end, accn, filed, revenue)
    (2023, "2022-09-25", "2023-09-30", "0000320193-23-000106", "2023-11-03", 240 * B),
    (2024, "2023-10-01", "2024-09-28", "0000320193-24-000123", "2024-11-01", 250 * B),
    (2025, "2024-09-29", "2025-09-27", "0000320193-25-000079", "2025-10-31", 270 * B),
    (2026, "2025-09-28", "2026-09-26", "0000320193-26-000026", "2026-11-03", 300 * B),
]
AAPL_QUARTERS = [  # (fy, fp, start, end, accn, filed, revenue, nine months to date or None)
    (2023, "Q1", "2022-09-25", "2022-12-31", "0000320193-23-000006", "2023-02-03", 70 * B, None),
    (2025, "Q1", "2024-09-29", "2024-12-28", "0000320193-25-000008", "2025-01-31", 80 * B, None),
    (2025, "Q2", "2024-12-29", "2025-03-29", "0000320193-25-000057", "2025-05-02", 60 * B, None),
    (2025, "Q3", "2025-03-30", "2025-06-28", "0000320193-25-000073", "2025-08-01", 60 * B, 200 * B),
    (2026, "Q1", "2025-09-28", "2025-12-27", "0000320193-26-000006", "2026-01-30", 90 * B, None),
    (2026, "Q2", "2025-12-28", "2026-03-28", "0000320193-26-000013", "2026-05-01", 70 * B, None),
    (2026, "Q3", "2026-03-29", "2026-06-27", "0000320193-26-000020", "2026-07-31", 65 * B, 225 * B),
]


def aapl_rows():
    rows = []
    for i, (fy, start, end, accn, filed, rev) in enumerate(AAPL_YEARS):
        rows.append(row(rev, start, end, accn, "10-K", fy, "FY", filed))
        for (_f2, s2, e2, _a2, _d2, r2) in AAPL_YEARS[max(0, i - 2):i]:        # the comparatives, under this 10-K's name
            rows.append(row(r2, s2, e2, accn, "10-K", fy, "FY", filed))
    for (fy, fp, start, end, accn, filed, rev, ytd) in AAPL_QUARTERS:
        rows.append(row(rev, start, end, accn, "10-Q", fy, fp, filed))
        if ytd:
            year_start = next(y[1] for y in AAPL_YEARS if y[0] == fy)
            rows.append(row(ytd, year_start, end, accn, "10-Q", fy, fp, filed))
    # an amendment whose cover page names the wrong year, a proxy and an 8-K: none of them names or adds a period
    rows.append(row(270 * B, "2024-09-29", "2025-09-27", "0000320193-26-000099", "10-K/A", 2027, "FY", "2026-02-01"))
    rows.append(row(300 * B, "2025-09-28", "2026-09-26", "0000320193-26-000101", "DEF 14A", None, None, "2026-12-01"))
    rows.append(row(65 * B, "2026-03-29", "2026-06-27", "0000320193-26-000102", "8-K", None, None, "2026-08-01"))
    return rows


def aapl():
    return filings(aapl_rows())


def msft():
    """June 30 every year; the quarter to Sep 30, 2026 is the first of fiscal 2027."""
    r = []
    for fy, start, end, accn, filed in ((2025, "2024-07-01", "2025-06-30", "0000789019-25-000001", "2025-07-30"),
                                        (2026, "2025-07-01", "2026-06-30", "0000789019-26-000001", "2026-07-29")):
        r.append(row(300 * B, start, end, accn, "10-K", fy, "FY", filed))
    for fy, fp, start, end, accn, filed in ((2026, "Q1", "2025-07-01", "2025-09-30", "0000789019-25-000010", "2025-10-29"),
                                            (2026, "Q3", "2026-01-01", "2026-03-31", "0000789019-26-000005", "2026-04-29"),
                                            (2027, "Q1", "2026-07-01", "2026-09-30", "0000789019-26-000010", "2026-10-28")):
        r.append(row(80 * B, start, end, accn, "10-Q", fy, fp, filed))
    return filings(r, cik="0000789019")


def jpm():
    """The calendar year."""
    r = [row(270 * B, "2025-01-01", "2025-12-31", "0000019617-26-000001", "10-K", 2025, "FY", "2026-02-13"),
         row(260 * B, "2024-01-01", "2024-12-31", "0000019617-25-000001", "10-K", 2024, "FY", "2025-02-14"),
         row(70 * B, "2026-07-01", "2026-09-30", "0000019617-26-000010", "10-Q", 2026, "Q3", "2026-11-03")]
    return filings(r, cik="0000019617")


def hd():
    """The Sunday nearest the end of January, each year named for the year it starts in: the 10-K for the year to
    Feb 1, 2026 is fiscal 2025, and its fiscal 2024 had 53 weeks."""
    r = [row(160 * B, "2024-01-29", "2025-02-02", "0000354950-25-000085", "10-K", 2024, "FY", "2025-03-21"),
         row(165 * B, "2025-02-03", "2026-02-01", "0001628280-26-019436", "10-K", 2025, "FY", "2026-03-18"),
         row(40 * B, "2026-02-02", "2026-05-03", "0001628280-26-038247", "10-Q", 2026, "Q1", "2026-05-27")]
    return filings(r, cik="0000354950")


def cmp_change():
    """Compass Minerals: a December year to 2020, a 10-KT for the nine months to Sep 30, 2021, September years after;
    the FY2022 10-K's twelve-month comparative to Sep 30, 2021 is a recast, not a fiscal year."""
    r = [row(1.2 * B, "2020-01-01", "2020-12-31", "0001227654-21-000037", "10-K", 2020, "FY", "2021-02-26"),
         row(0.9 * B, "2021-01-01", "2021-09-30", "0001227654-21-000309", "10-KT", 2021, "FY", "2021-11-30"),
         row(1.2 * B, "2021-10-01", "2022-09-30", "0001227654-22-000340", "10-K", 2022, "FY", "2022-12-14"),
         row(1.1 * B, "2020-10-01", "2021-09-30", "0001227654-22-000340", "10-K", 2022, "FY", "2022-12-14")]
    return filings(r, cik="0001227654")


def vfc_change():
    """VF Corp: a year to Dec 30, 2017, the three months to Mar 31, 2018 on a 10-QT, then years to late March."""
    r = [row(12 * B, "2017-01-01", "2017-12-30", "0000103379-18-000010", "10-K", 2017, "FY", "2018-02-28"),
         row(2.5 * B, "2017-12-31", "2018-03-31", "0000103379-18-000020", "10-QT", 2018, "Q1", "2018-05-10"),
         row(13 * B, "2018-04-01", "2019-03-30", "0000103379-19-000010", "10-K", 2019, "FY", "2019-05-24")]
    return filings(r, cik="0000103379")


# ------------------------------------------------------------------------------------------------ the calendar
def test_a_year_is_named_and_dated_as_its_own_10k_files_it():
    cal = P.calendar(aapl())
    assert cal["available"] and cal["basis"] == "GAAP" and cal["kind"] == "52_53_week"
    assert cal["year_end"] == "the last Saturday of September"
    years = {y["end"]: y for y in cal["years"]}
    assert list(years) == ["2026-09-26", "2025-09-27", "2024-09-28", "2023-09-30"], "the 10-Ks' own last days, not month ends"
    # each named by its own 10-K: the FY2026 10-K reports FY2025 and FY2024 too, under its own fiscal-year focus
    assert [years[e]["fy"] for e in years] == [2026, 2025, 2024, 2023]
    assert years["2023-09-30"]["weeks"] == 53 and years["2025-09-27"]["weeks"] == 52
    assert years["2025-09-27"]["filing"]["form"] == "10-K" and years["2025-09-27"]["filing"]["filed"] == "2025-10-31"
    assert years["2025-09-27"]["filing"]["url"].endswith("/000032019325000079/")
    # the amendment names fiscal 2027 on its cover; the original's name holds, and the amendment is listed
    assert years["2025-09-27"]["amended"][0]["form"] == "10-K/A"
    assert all(q["filing"]["form"] in ("10-Q", "10-K") for q in cal["quarters"]), "no proxy or 8-K period"


def test_quarters_take_their_year_and_number_from_the_filings():
    cal = P.calendar(aapl())
    q = {x["end"]: x for x in cal["quarters"]}
    assert (q["2025-12-27"]["fy"], q["2025-12-27"]["fq"]) == (2026, 1), "Apple's first quarter of fiscal 2026 ended Dec 27"
    q4 = q["2026-09-26"]
    assert q4["derived"] and q4["fq"] == 4 and q4["start"] == "2026-06-28" and q4["filing"]["form"] == "10-K"
    assert q["2022-12-31"]["weeks"] == 14, "the 53-week year's extra week, in its first quarter"
    d = P.describe(cal, "2022-12-31", "quarter")
    assert d["short"] == "Q1 FY23" and d["note"] == "A 14-week quarter, one week longer than the quarters beside it."
    # an earnings report covers the latest quarter that ended at least five days before it
    rep = P.for_report(cal, "2026-10-30")
    assert rep["short"] == "Q4 FY26" and rep["label"] == "Quarter ended Sep 26, 2026"
    assert P.for_report(cal, "2026-01-29")["short"] == "Q1 FY26"


def test_a_provider_date_is_matched_to_the_filing_that_reports_it():
    cal = P.calendar(aapl())
    d = P.describe(cal, "2025-09-30", "annual", provider="Yahoo Finance")
    assert d["label"] == "Fiscal year ended Sep 27, 2025" and d["short"] == "FY25" and d["badge"] == "Annual"
    assert d["provider_end"] == "2025-09-30" and d["dated_by"] == "filing" and d["filing"]["form"] == "10-K"
    assert P.describe(cal, "2023-09-30", "annual")["note"] == "A 53-week year, one week longer than the years beside it."
    q = P.describe(cal, "2026-06-30", "quarter", provider="Yahoo Finance")
    assert (q["short"], q["label"], q["badge"]) == ("Q3 FY26", "Quarter ended Jun 27, 2026", "Quarter")
    # a column no filing reports is dated only, and says whose date it is
    old = P.describe(cal, "2018-09-30", "annual", provider="Yahoo Finance")
    assert old["short"] is None and old["label"] == "Year to Sep 30, 2018, as Yahoo Finance dates it"
    assert P.in_words(d) == "the fiscal year ended Sep 27, 2025 (FY25)"


def test_acceptance_3_non_december_and_december_year_ends_label_correctly():
    """The handoff: AAPL (September), one June year end and one December, tested; Home Depot and NVIDIA's late
    January besides, where the old rule's guess and the company's own name part."""
    a, m, j, h = (P.calendar(f) for f in (aapl(), msft(), jpm(), hd()))
    assert P.describe(a, "2025-09-30", "annual")["short"] == "FY25"
    assert (m["kind"], m["year_end"]) == ("fixed", "June 30")
    assert P.describe(m, "2026-06-30", "annual")["label"] == "Fiscal year ended Jun 30, 2026"
    assert P.describe(m, "2026-06-30", "annual")["short"] == "FY26"
    assert P.describe(m, "2026-09-30", "quarter")["short"] == "Q1 FY27", "Microsoft's July to September is fiscal 2027's first"
    assert (j["kind"], j["year_end"]) == ("calendar", "December 31")
    assert P.describe(j, "2025-12-31", "annual")["short"] == "2025"
    assert P.describe(j, "2026-09-30", "quarter")["short"] == "Q3 2026"
    hy = P.describe(h, "2026-01-31", "annual", provider="Yahoo Finance")
    assert hy["short"] == "FY25" and hy["label"] == "Fiscal year ended Feb 1, 2026", "Home Depot's own name for it"
    assert fundamentals.fiscal_label("2026-01-31", "2026-01-31", annual=True) == "FY26", "the old guess, for the record"
    assert P.describe(h, "2026-05-03", "quarter")["short"] == "Q1 FY26"
    assert P.describe(h, "2025-01-31", "annual")["weeks"] == 53
    assert h["year_end"] == "the Sunday nearest the end of January"


def test_a_change_of_year_end_shows_both_ends_with_a_break_note():
    c = P.calendar(cmp_change())
    assert len(c["changes"]) == 1
    ch = c["changes"][0]
    assert (ch["from"], ch["to"]) == ("December 31", "September 30") and ch["transition"]["filing"]["form"] == "10-KT"
    assert ch["note"] == ("The fiscal year end moved from December 31 to September 30: the 9 months from Jan 1, 2021 to "
                          "Sep 30, 2021 were a transition period, filed on a 10-KT on Nov 30, 2021. Years before and "
                          "after it cover different months.")
    t = P.describe(c, "2021-09-30", "annual", provider="Yahoo Finance")
    assert t["type"] == "transition" and t["short"] is None and t["label"] == "Transition period ended Sep 30, 2021"
    assert t["note"] == "Not a full fiscal year: 9 months."
    assert P.describe(c, "2022-09-30", "annual")["short"] == "FY22"
    assert P.changes_between(c, ["2020-12-31", "2022-09-30"]) == c["changes"]
    v = P.calendar(vfc_change())
    assert v["changes"][0]["note"].startswith("The fiscal year end moved from late December to late March: the 3 months "
                                              "from Dec 31, 2017 to Mar 31, 2018 were a transition period, filed on a 10-QT")
    assert P.describe(v, "2018-03-31", "quarter")["label"] == "Transition period ended Mar 31, 2018"


def test_results_out_before_their_filing_are_named_by_their_place_in_the_calendar():
    """A company's results come out days or weeks before its 10-Q or 10-K (Apple's fiscal 2026 on Oct 30, its 10-K on
    Nov 3): the period is the next in the company's own calendar, named by its place in it, dated by how the year is
    set ("about" for a 52- or 53-week year) and said to be not yet filed. Nothing further ahead is named."""
    early = P.calendar(filings([r for r in aapl_rows() if r["accn"] not in ("0000320193-26-000026", "0000320193-26-000101")]))
    q = P.describe(early, "2026-09-30", "quarter", provider="Yahoo Finance")
    assert (q["short"], q["label"], q["projected"], q["filing"]) == ("Q4 FY26", "Quarter to about Sep 26, 2026, not yet filed", True, None)
    y = P.describe(early, "2026-09-30", "annual", provider="Yahoo Finance")
    assert (y["short"], y["label"]) == ("FY26", "Fiscal year to about Sep 26, 2026, not yet filed")
    assert P.for_report(early, "2026-10-30")["short"] == "Q4 FY26", "the report before its 10-K"
    assert P.describe(early, "2026-12-31", "quarter")["short"] is None, "two quarters ahead is not named"
    # Microsoft before its 10-Q for the quarter to Sep 30, 2026
    m = P.calendar(filings([row(300 * B, "2025-07-01", "2026-06-30", "0000789019-26-000001", "10-K", 2026, "FY", "2026-07-29"),
                            row(80 * B, "2026-01-01", "2026-03-31", "0000789019-26-000005", "10-Q", 2026, "Q3", "2026-04-29")],
                           cik="0000789019"))
    mq = P.describe(m, "2026-09-30", "quarter", provider="Yahoo Finance")
    assert (mq["short"], mq["label"]) == ("Q1 FY27", "Quarter ended Sep 30, 2026, not yet filed"), "a fixed year end is exact"


def test_without_filings_nothing_is_named_and_a_missing_date_says_so():
    none = P.calendar(None)
    assert none["available"] is False
    d = P.describe(none, "2026-03-31", "annual", provider="Yahoo Finance")
    assert d["short"] is None and d["label"] == "Year to Mar 31, 2026, as Yahoo Finance dates it"
    assert "could not read" in d["note"]
    assert P.describe(none, None, "annual") == {"type": "annual", "badge": "Annual", "available": False,
                                                "label": "Period labels unavailable", "short": None, "end": None,
                                                "why": "No end date for this period."}
    assert P.for_report(none, "2026-10-30") is None, "no quarter is guessed for a report"
    ifrs = P.calendar(filings([], ifrs=True))
    assert ifrs["available"] is False and ifrs["basis"] == "IFRS"


# ------------------------------------------------------------------------------------------------ the payloads
QUOTE = {"ticker": "AAPL", "price": 270.0, "forward_eps": 9.0, "quote_type": "EQUITY", "currency": "USD"}


def aapl_fin():
    """The provider's statements for the Apple fixture, dated as Yahoo dates them (month ends) and a year behind."""
    return {"available": True, "annual_periods": ["2025-09-30", "2024-09-30", "2023-09-30"],
            "quarterly_periods": ["2026-06-30", "2026-03-31", "2025-12-31"],
            "annual_fiscal": ["FY25", "FY24", "FY23"], "quarterly_fiscal": ["Q3 FY26", "Q2 FY26", "Q1 FY26"],
            "annual": {"revenue": [270 * B, 250 * B, 240 * B], "net_income": [70 * B, 62 * B, 60 * B],
                       "operating_income": [86 * B, 79 * B, 74 * B], "free_cash_flow": [90 * B, 88 * B, 85 * B],
                       "operating_cash_flow": [100 * B, 98 * B, 95 * B], "capital_expenditure": [-10 * B, -10 * B, -10 * B]},
            "quarterly": {"revenue": [65 * B, 70 * B, 90 * B], "net_income": [16 * B, 17 * B, 24 * B]},
            "growth": {"revenue_yoy_pct": 8.0, "net_income_yoy_pct": 12.9}, "margins": {"gross_pct": 46.0, "operating_pct": 31.9},
            "balance_sheet": {}, "balance_history": {}, "source": "The company's annual and quarterly statements as Yahoo Finance carries them."}


def ticker(fl=None, fin=None, sym="AAPL"):
    fin = fin if fin is not None else aapl_fin()
    block = res.resolve(sym, dict(QUOTE, ticker=sym), sec=(fl, fl.cik if fl else None, None if fl else "a fixture"),
                        financials=fin)
    return {"ticker": sym, "quote": dict(QUOTE, ticker=sym), "company": {"financials": fin}, "figures": block}


def test_the_statement_columns_carry_the_filings_names_and_dates():
    t = ticker(aapl())
    st = t["figures"]["periods"]["statements"]
    assert st["basis"] == "GAAP" and st["dated_by"] == "filings"
    assert [d["label"] for d in st["annual"]] == ["Fiscal year ended Sep 27, 2025", "Fiscal year ended Sep 28, 2024",
                                                  "Fiscal year ended Sep 30, 2023"]
    assert [d["short"] for d in st["annual"]] == ["FY25", "FY24", "FY23"]
    assert [d["short"] for d in st["quarterly"]] == ["Q3 FY26", "Q2 FY26", "Q1 FY26"]
    assert st["quarterly"][2]["label"] == "Quarter ended Dec 27, 2025", "not the provider's Dec 31"
    # a registry figure's year carries the company's name for it
    per = t["figures"]["figures"]["net_margin_fy"]["period"]
    assert per["end"] == "2026-09-26" and per["fiscal"] == "FY26" and per["badge"] == "Annual"
    assert t["figures"]["figures"]["net_margin_ttm"]["period"]["badge"] == "TTM"
    assert res.compact(t["figures"], ["net_margin_fy"])["AAPL net_margin_fy"].get("period") in (
        "Fiscal year ended Sep 26, 2026 (FY26)", None), "Milo's tools name the year as the filings do"
    cal = t["figures"]["periods"]["calendar"]
    assert cal["available"] and cal["year_end"] == "the last Saturday of September" and len(cal["years"]) == 4


def _parse(rows):
    return {"available": True, "facts": [{"metric": m, "axis": a, "member": mem, "start": s, "end": e, "kind": k,
                                          "value": v, "cross": 1} for (m, a, mem, s, e, k, v) in rows]}


SEG_FILINGS = [  # newest first, as EDGAR lists them
    {"accession": "0000320193-26-000026", "form": "10-K", "period": "2026-09-26", "filed": "2026-11-03"},
    {"accession": "0000320193-26-000020", "form": "10-Q", "period": "2026-06-27", "filed": "2026-07-31"},
    {"accession": "0000320193-26-000013", "form": "10-Q", "period": "2026-03-28", "filed": "2026-05-01"},
    {"accession": "0000320193-26-000006", "form": "10-Q", "period": "2025-12-27", "filed": "2026-01-30"},
]


def seg_parses():
    y26, y25 = ("2025-09-28", "2026-09-26"), ("2024-09-29", "2025-09-27")
    k = [("revenue", "segment", "Americas", *y26, "year", 200 * B), ("revenue", "segment", "Europe", *y26, "year", 100 * B),
         ("revenue", "segment", "Americas", *y25, "year", 180 * B), ("revenue", "segment", "Europe", *y25, "year", 90 * B),
         # products: "Products" is iPhone and Mac together, a subtotal the filing tags beside its parts
         ("revenue", "product", "iPhone", *y26, "year", 150 * B), ("revenue", "product", "Mac", *y26, "year", 50 * B),
         ("revenue", "product", "Services", *y26, "year", 100 * B), ("revenue", "product", "Products", *y26, "year", 200 * B),
         # geography is in the 10-K only
         ("revenue", "geography", "United States", *y26, "year", 120 * B),
         ("revenue", "geography", "Other countries", *y26, "year", 180 * B)]
    q = {"0000320193-26-000020": ("2026-03-29", "2026-06-27", 45, 20), "0000320193-26-000013": ("2025-12-28", "2026-03-28", 45, 25),
         "0000320193-26-000006": ("2025-09-28", "2025-12-27", 60, 30)}
    out = {"0000320193-26-000026": _parse(k)}
    for acc, (s, e, a, eu) in q.items():
        out[acc] = _parse([("revenue", "segment", "Americas", s, e, "quarter", a * B),
                           ("revenue", "segment", "Europe", s, e, "quarter", eu * B),
                           ("revenue", "product", "iPhone", s, e, "quarter", (a + eu) * 0.5 * B),
                           ("revenue", "product", "Services", s, e, "quarter", (a + eu) * 0.5 * B)])
    return out


@pytest.fixture
def seg_build(monkeypatch):
    parses = seg_parses()
    monkeypatch.setattr(segment_store, "load_many", lambda accs: {a: parses[a] for a in accs if a in parses})
    monkeypatch.setattr(segment_store, "save", lambda *a, **k: None)
    monkeypatch.setattr(segments, "_SHARED_CLEARED", True)
    monkeypatch.setattr(segments.feeds, "cached_json", lambda key: None)
    monkeypatch.setattr(segments, "filings", lambda ticker, force=False: {
        "available": True, "cik": "0000320193", "ticker": "AAPL",
        "rows": [dict(r, instance_url="https://example.test/{}_htm.xml".format(r["accession"])) for r in SEG_FILINGS]})
    return lambda sec=None: segments.build("AAPL", sec=sec)


def test_segments_name_each_period_and_reconcile_to_the_filings_total(seg_build):
    fl = aapl()
    out = seg_build(lambda: (fl, fl.cik, None))
    y = out["periods"]["year"]["2026-09-26"]
    assert (y["short"], y["label"], y["badge"]) == ("FY26", "Fiscal year ended Sep 26, 2026", "Annual")
    assert y["read_from"]["form"] == "10-K" and y["read_from"]["filed"] == "2026-11-03"
    assert y["read_from"]["url"].endswith("/000032019326000026/")
    q4 = out["periods"]["quarter"]["2026-09-26"]
    assert q4["short"] == "Q4 FY26" and q4["derived"], "the 10-K's year less its three quarters"
    seg = next(t for t in out["tables"] if t["axis"] == "segment")
    ends = seg["annual"]["ends"]
    assert [r["value"] if r else None for r in seg["reported"]["year"]] == [270 * B, 300 * B]
    assert seg["reported"]["year"][ends.index("2026-09-26")]["form"] == "10-K"
    qtot = dict(zip(out["quarters"], seg["reported"]["quarter"]))
    assert qtot["2026-06-27"]["value"] == 65 * B and qtot["2026-09-26"]["value"] == 75 * B and qtot["2026-09-26"]["derived"]
    assert all(t["axis"] != "geography" for t in out["tables"]), "Classic and the sum of the parts read `tables` as quarterly"
    geo = next(t for t in out["annual_only_tables"] if t["axis"] == "geography")
    assert geo["annual_only"] is True and geo["rows"] == [] and geo["annual"]["ends"] == ["2026-09-26"], \
        "a breakdown filed only in the 10-K is kept, and said to be yearly"
    assert geo["reported"]["year"][0]["value"] == 300 * B
    assert out["basis"] == "GAAP" and "ASC 280" in out["basis_note"]


def test_without_the_company_facts_a_segment_period_is_dated_by_its_filing_and_not_reconciled(seg_build):
    out = seg_build(None)
    y = out["periods"]["year"]["2026-09-26"]
    assert y["short"] is None and y["label"] == "Fiscal year ended Sep 26, 2026" and y["filing"]["form"] == "10-K"
    assert all(t["reported"] is None and "not reconciled" in t["reported_why"] for t in out["tables"] + out["annual_only_tables"])


def test_a_report_is_named_for_the_quarter_the_filings_say():
    fl = aapl()

    class YF:
        def sec_filings(self, sym):
            return fl, fl.cik, None

    rows = [{"date": "2026-10-30", "eps_reported": 1.9}, {"date": "2026-07-31", "eps_reported": 1.5}]
    s, g = {"rows": [dict(r) for r in rows]}, {"quarterly": [{"period": "2026-06-30"}], "annual": [{"period": "2025-09-30"}]}
    earnings._name_quarters(YF(), "AAPL", s, g)
    assert [r["fiscal"] for r in s["rows"]] == ["Q4 FY26", "Q3 FY26"]
    assert s["rows"][0]["period"]["label"] == "Quarter ended Sep 26, 2026" and s["periods"]["available"]
    assert g["quarterly"][0]["fiscal"] == "Q3 FY26" and g["annual"][0]["period_info"]["label"] == "Fiscal year ended Sep 27, 2025"
    assert g["basis"] == "GAAP"
    # a provider with no filings: no names at all, and the reason
    s2, g2 = {"rows": [dict(r) for r in rows]}, {"quarterly": [{"period": "2026-06-30"}], "annual": []}
    earnings._name_quarters(object(), "AAPL", s2, g2)
    assert [r["fiscal"] for r in s2["rows"]] == [None, None] and s2["periods"]["available"] is False
    assert "SEC filings" in s2["periods"]["reason"] and g2["quarterly"][0]["fiscal"] is None


def test_the_research_frameworks_years_carry_their_names_and_dates():
    assert quality._fy({"fy_end": "2025-09-27", "fiscal": "FY25"}) == "FY25 (to Sep 27, 2025)"
    assert quality._fy({"fy_end": "2026-02-01"}) == "the year to Feb 1, 2026", "no name without a filing to give it"
    assert quality._cap("the year to Feb 1, 2026 revenue 1") == "The year to Feb 1, 2026 revenue 1"
    src = (ROOT / "app" / "research" / "quality.py").read_text()
    assert 'return "FY" + str(' not in src, "a calendar year is not a fiscal year's name"
    assert 'y["fiscal"] = periods_mod.describe(cal, y["fy_end"], "annual").get("short")' in (ROOT / "app/valuation/inputs.py").read_text()


# ------------------------------------------------------------------------------------------------ the pages
DATE = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d{1,2}, \d{4}"
FY = re.compile(r"\b(?:Q[1-4] )?FY ?\d{2,4}\b")


def bare_fy(html):
    """Every fiscal-year label in a page's text with no end date beside it: within 60 characters either side, inside
    the same piece of text (a table cell, a line, a list item). An "FY26" a reader cannot date is bare."""
    text = re.sub(r"<(?:/(?:p|li|td|th|dd|dt|h\d|div|figcaption|summary|section|tr)|br ?/?)>", "\n", html)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    out = []
    for piece in text.split("\n"):
        for m in FY.finditer(piece):
            near = piece[max(0, m.start() - 60):m.end() + 60]
            if not re.search(DATE, near):
                out.append(piece.strip()[:160])
    return out


def pages(tmp_path, cases):
    """Financials (fiscal years and quarters), the Overview's revenue line, Simple and research reads, Earnings and
    the research sheet, drawn by the pages' own code for each case."""
    return _run(tmp_path, f"""
      const FIN = await import('{(JS / "pages/financials.js").as_posix()}');
      const DS = await import('{(JS / "pages/dossier.js").as_posix()}');
      const ER = await import('{(JS / "pages/earnings.js").as_posix()}');
      const SH = await import('{(JS / "pages/sheet.js").as_posix()}');
      const OR = await import('{(JS / "pages/overview-research.js").as_posix()}');
      const S = await import('{(JS / "pages/overview-simple.js").as_posix()}');
      const d = await import('{(JS / "core/dom.js").as_posix()}');
      const cases = {json.dumps(cases)};
      const out = {{}};
      for (const [k, c] of Object.entries(cases)) {{
        const now = Date.parse('2026-11-03T20:00:00Z');
        const ctx = OR.context({{ sym: c.sym, t: c.t, lt: {{}}, stars: null, fund: false, advanced: false, phase: '', now }});
        const F = S.simpleFacts({{ sym: c.sym, kind: 'company', t: c.t, lt: {{}}, quote: c.t.quote, session: {{}}, earnings: {{}}, price: ctx.price, f: ctx.f, today: new Date(now) }});
        const simple = ['new', 'beginner', 'intermediate', 'advanced', 'expert'].map((L) => S.simpleAnalysis(F, L).map(([q, lines]) => lines.map((l) => S.plainText(l, F)).join(' ')).join('\\n')).join('\\n');
        const br = OR.businessRead(c.t) || {{}};
        out[k] = {{ year: d.toString(FIN.blocksFor({{ sym: c.sym, t: c.t, sg: c.sg }}, 'year')), quarter: d.toString(FIN.blocksFor({{ sym: c.sym, t: c.t, sg: c.sg }}, 'quarter')),
          revenue: DS.revenueLineFor(c.sg), simple, research: (br.evidence || []).map(([a, b]) => `${{a}}: ${{d.toString(b)}}`).join('\\n'),
          earnings: c.e ? d.toString(ER.blocksFor(c.e, c.sym)) : '', sheet: JSON.stringify(SH.sheetFacts({{ sym: c.sym, ticker: c.t, fairValue: {{}}, earnings: {{}} }}).financials) }};
      }}
      print(JSON.stringify(out));
    """)


def earnings_payload(fl):
    class YF:
        def sec_filings(self, sym):
            return (fl, fl.cik, None) if fl else (None, None, "no filings")

    s = {"available": True, "rows": [{"date": "2026-10-30", "eps_estimate": 1.8, "eps_reported": 1.9, "surprise_pct": 5.5, "next_day_move_pct": 1.2},
                                     {"date": "2026-07-31", "eps_estimate": 1.4, "eps_reported": 1.5, "surprise_pct": 7.1, "next_day_move_pct": -0.4}],
         "beat_count": 2, "in_line_count": 0, "rate_quarters": 2}
    g = {"quarterly": [{"period": "2026-06-30", "revenue": 65 * B, "revenue_yoy_pct": 8.3}, {"period": "2026-03-31", "revenue": 70 * B}],
         "annual": [], "forward": []}
    earnings._name_quarters(YF(), "AAPL", s, g)
    return {"surprise": s, "growth": g, "next_report": {}, "latest_result": {}}


@pytest.fixture
def drawn(tmp_path, seg_build):
    fl = aapl()
    sg = seg_build(lambda: (fl, fl.cik, None))
    m_fin = dict(aapl_fin(), annual_periods=["2026-06-30", "2025-06-30"], quarterly_periods=["2026-09-30", "2026-03-31"],
                 annual={"revenue": [300 * B, 280 * B], "net_income": [100 * B, 90 * B]}, quarterly={"revenue": [80 * B, 75 * B]})
    j_fin = dict(aapl_fin(), annual_periods=["2025-12-31", "2024-12-31"], quarterly_periods=["2026-09-30"],
                 annual={"revenue": [270 * B, 260 * B], "net_income": [55 * B, 50 * B]}, quarterly={"revenue": [70 * B]})
    h_fin = dict(aapl_fin(), annual_periods=["2026-01-31", "2025-01-31"], quarterly_periods=["2026-04-30"],
                 annual={"revenue": [165 * B, 160 * B], "net_income": [15 * B, 14 * B]}, quarterly={"revenue": [40 * B]})
    cases = {
        "AAPL": {"sym": "AAPL", "t": ticker(fl), "sg": sg, "e": earnings_payload(fl)},
        "MSFT": {"sym": "MSFT", "t": ticker(msft(), m_fin, "MSFT"), "sg": None, "e": None},
        "JPM": {"sym": "JPM", "t": ticker(jpm(), j_fin, "JPM"), "sg": None, "e": None},
        "HD": {"sym": "HD", "t": ticker(hd(), h_fin, "HD"), "sg": None, "e": None},
        "NOFILINGS": {"sym": "TSM", "t": ticker(None, j_fin, "TSM"), "sg": None, "e": earnings_payload(None)},
    }
    return pages(tmp_path, cases)


def _section(html, sid):
    i = html.index('id="{}"'.format(sid))
    j = html.find("<section", i + 1)
    return html[i:j if j > 0 else len(html)]


def test_acceptance_1_the_aapl_segments_block_reads_its_fiscal_year_with_its_badges(drawn):
    """The handoff: AAPL's Segments block reads "Fiscal year ended Sep 30, 2025, or the correct current-year equivalent
    at test time", with the period-type and GAAP badges. The equivalent in this fixture, as on 2026-11-03, is fiscal
    2026, ended Sep 26, 2026, from the 10-K filed that day."""
    seg = _section(drawn["AAPL"]["year"], "fin-segments")
    line = seg.split('<div class="period-line">', 1)[1].split("</div>", 1)[0]
    assert "FY26, fiscal year ended Sep 26, 2026" in line
    assert '<span class="pbadge" title="One fiscal year' in line and ">Annual</span>" in line
    assert '>GAAP</span>' in line and "10-K filed Nov 3, 2026" in line and 'href="https://www.sec.gov/Archives/edgar/data/320193/000032019326000026/"' in line
    assert seg.index('class="period-line"') < seg.index('class="section-sub"'), "beside the title, not in a footnote"
    assert "A later period than the statements above" in seg, "the statements above are a year behind, and it says so"
    # every breakdown says what it adds up to against the 10-K's own total, or why it was not checked
    assert "The parts add to the $300.0B the 10-K reports." in seg
    assert "Products is a total of other lines here" in seg, "the subtotal is not counted twice"
    assert "Annual only" not in seg, "the fiscal-years view needs no such label"
    q = _section(drawn["AAPL"]["quarter"], "fin-segments")
    qline = q.split('<div class="period-line">', 1)[1].split("</div>", 1)[0]
    assert ">Quarter</span>" in qline and "Q4 FY26, quarter ended Sep 26, 2026" in qline and ">GAAP</span>" in qline
    assert "Q4 FY26 (to Sep 26, 2026) is not filed on its own: it is the 10-K&#39;s year less the three quarters filed before it." in q
    assert "Annual only: the company reports this breakdown in its 10-K, not each quarter." in q, "geography, by year"
    # the other blocks: the Summary and Statements, dated by the 10-K, not the provider's Sep 30
    summ = _section(drawn["AAPL"]["year"], "fin-summary")
    assert "FY25, fiscal year ended Sep 27, 2025" in summ and ">Annual</span>" in summ and ">GAAP</span>" in summ
    assert "Sep 30, 2025" not in summ and "Summary, FY" not in summ
    st = _section(drawn["AAPL"]["year"], "fin-statements")
    assert "Fiscal years ended Sep 30, 2023 to Sep 27, 2025 (FY23 to FY25)" in st and "FY23 (to Sep 30, 2023) had 53 weeks" in st
    assert "EBITDA" not in st or "Non-GAAP" in st
    assert 'Free cash flow<span class="pbadge"' in st, "a non-GAAP line says so where the rest is GAAP"
    sq = _section(drawn["AAPL"]["quarter"], "fin-statements")
    assert ">Quarter</span>" in sq and "Quarters ended Dec 27, 2025 to Jun 27, 2026 (Q1 FY26 to Q3 FY26)" in sq
    # TTM, the third period type, is the registry's twelve-month figures' badge (their definition panel)
    assert "ttm: 'TTM'" in (JS / "ui/figure.js").read_text()


def test_acceptance_2_no_bare_fy_label_without_an_end_date_in_the_dossier_and_compare(drawn):
    for sym, got in drawn.items():
        for where, html in got.items():
            assert bare_fy(html) == [], (sym, where, bare_fy(html))
    # the check is real: it finds the labels the pages printed before this fix
    assert bare_fy("<h2>Summary, FY25</h2><p>The fiscal year to Sep 30, 2025.</p>") == ["Summary, FY25"]
    assert bare_fy("<p>Americas was the largest, at $198.1B in FY26. The parts add to $478.8B.</p>")
    assert bare_fy("<th>FY25<small>to Sep 27, 2025</small></th>") == []
    # Compare names no fiscal period: its rows are prices, ratios and the registry's forward P/E
    cmp_src = (JS / "pages/compare.js").read_text()
    assert not FY.search(cmp_src) and "annual_fiscal" not in cmp_src and "quarterly_fiscal" not in cmp_src


def test_acceptance_3_the_pages_label_non_december_year_ends_correctly(drawn):
    m, j, h = drawn["MSFT"]["year"], drawn["JPM"]["year"], drawn["HD"]["year"]
    assert "FY26, fiscal year ended Jun 30, 2026" in m
    assert "Q1 FY27<small" in drawn["MSFT"]["quarter"], "Microsoft's quarter to Sep 30, 2026"
    assert "2025, fiscal year ended Dec 31, 2025" in j
    assert "FY25, fiscal year ended Feb 1, 2026" in h and "FY26" not in _section(h, "fin-summary"), "Home Depot's own name"
    a = drawn["AAPL"]
    assert "FY25 (to Sep 27, 2025)" in a["simple"] and "fiscal year ended Sep 27, 2025 (FY25)" in a["research"]
    assert a["revenue"] == "iPhone, 50%; Services, 33% of revenue in FY26 (to Sep 26, 2026), by product and service."
    assert json.loads(a["sheet"])["label"] == "FY25, fiscal year ended Sep 27, 2025"
    assert "Q4 FY26<small" in a["earnings"] and "to Sep 26, 2026" in a["earnings"]
    assert "Quarters ended Jun 27, 2026 to Sep 26, 2026 (Q3 FY26 to Q4 FY26)" in a["earnings"]
    assert ">Analysts&#39;" in a["earnings"] or ">Analysts' basis<" in a["earnings"], "reported EPS is not the GAAP figure"


def test_missing_fiscal_metadata_shows_period_labels_unavailable_and_no_guessed_name(drawn):
    n = drawn["NOFILINGS"]
    assert "FY" not in re.sub(r"<[^>]+>", " ", n["year"]) + n["simple"] + n["research"], "nothing named from a date"
    assert "Years ending Dec 31, 2024 to Dec 31, 2025, as the provider dates them" in n["year"]
    assert "Fiscal-year names come from the company&#39;s SEC filings" in n["year"] or "Fiscal-year names come from the company's SEC filings" in n["year"]
    assert ">Basis not stated</span>" in n["year"]
    # the Earnings tab cannot place a report in a quarter: it says so once and names none
    assert "Period labels unavailable" in n["earnings"] and "Not identified" in n["earnings"]
    assert "could not read for this company" in n["earnings"]


def test_a_tick_carries_its_end_date_and_its_whole_label(tmp_path):
    got = _run(tmp_path, f"""
      const PER = await import('{(JS / "core/periods.js").as_posix()}');
      const B = await import('{(JS / "ui/bars.js").as_posix()}');
      const d = {{ type: 'annual', available: true, end: '2025-09-27', short: 'FY25', label: 'Fiscal year ended Sep 27, 2025', dated_by: 'filing' }};
      const none = PER.bare('2025-12-31', 'annual');
      const ch = B.groupedBars([PER.tick(d)], [{{ name: 'Revenue', cls: 's1', values: [416e9] }}], {{ w: 400, labelWidth: 84 }});
      print(JSON.stringify({{ tick: PER.tick(d), bare: PER.tick(none), svg: ch.html, un: PER.tick(PER.bare(null)) }}));
    """)
    assert got["tick"] == {"x": "FY25", "sub": "Sep 27, 2025", "title": "FY25, fiscal year ended Sep 27, 2025"}
    assert got["bare"] == {"x": "Dec 31, 2025", "title": "Year to Dec 31, 2025"}, "no name, the date is the label"
    assert got["un"]["x"] == "Period labels unavailable"
    assert ">Sep 27, 2025</text>" in got["svg"] and "aria-label=\"Bars, FY25, fiscal year ended Sep 27, 2025 to" in got["svg"]


def test_a_period_not_yet_filed_says_so_on_the_page(tmp_path):
    got = _run(tmp_path, f"""
      const PER = await import('{(JS / "core/periods.js").as_posix()}');
      const d = {{ type: 'quarter', available: true, end: '2026-09-26', short: 'Q4 FY26', projected: true, dated_by: 'calendar',
        label: 'Quarter to about Sep 26, 2026, not yet filed', note: 'Results are out before the 10-Q or 10-K: the period is named by its place in the company calendar.' }};
      const f = {{ type: 'quarter', available: true, end: '2026-06-27', short: 'Q3 FY26', label: 'Quarter ended Jun 27, 2026', dated_by: 'filing' }};
      print(JSON.stringify({{ text: PER.inText(d), tick: PER.tick(d), range: PER.range([f, d]), notes: PER.notes([f, d]) }}));
    """)
    assert got["text"] == "Q4 FY26 (to about Sep 26, 2026, not yet filed)"
    assert got["tick"] == {"x": "Q4 FY26", "sub": "about Sep 26, 2026", "title": "Q4 FY26, quarter to about Sep 26, 2026, not yet filed"}
    assert got["range"] == "Quarters ended Jun 27, 2026 to about Sep 26, 2026 (Q3 FY26 to Q4 FY26)"
    assert got["notes"][0].startswith("Q4 FY26 (to about Sep 26, 2026) is not filed yet.")


def test_the_period_line_is_words_in_tags_and_wraps_on_a_phone():
    css = (ROOT / "static/v2/css/components.css").read_text()
    line = css.split(".period-line {", 1)[1].split("}", 1)[0]
    assert "flex-wrap: wrap" in line and "max-width: 100%" in line
    badge = css.split(".pbadge {", 1)[1].split("}", 1)[0]
    assert "border: 1px solid var(--c-line)" in badge and "border-radius: var(--r-xs)" in badge and "background" not in badge, \
        "a badge is a word in a squared tag; no colour carries its meaning"
    assert ".period-what { min-width: 0;" in css and "overflow-wrap: anywhere" in css.split(".period-what {", 1)[1].split("}", 1)[0]
    src = (JS / "ui/period.js").read_text()
    assert 'class="pbadge" title="${means}">${text}</span>' in src


# ------------------------------------------------------------------------------------------------ the check
GUESS = [
    re.compile(r"\b(annual_fiscal|quarterly_fiscal)\b"),                        # the provider's guessed names
    re.compile(r"fiscalLabel\("),                                               # the page's own namer, retired
    re.compile(r"[`'\"]FY[`'\"]?\s*\+|FY ?\$\{|Q\$\{[^}]*\} ?FY"),                # a name built from a date
]
ALLOWED = {
    # Milo's context drops the provider's names and sends the filings' instead
    "core/figures.js": ("annual_fiscal", "quarterly_fiscal"),
}


def offenders(sources):
    out = []
    for rel, src in sources.items():
        code = re.sub(r"//[^\n]*", "", src)                                     # comments say what was retired
        for rx in GUESS:
            for m in rx.finditer(code):
                if m.group(0).strip("(") in ALLOWED.get(rel, ()):
                    continue
                out.append("{}: {}".format(rel, m.group(0)))
    return out


def test_no_v2_page_names_a_period_from_a_date():
    """The build fails when a v2 page reads the provider's guessed fiscal names or builds one from a date: a period's
    name comes only from the filings (core/periods.js and the server's descriptions)."""
    sources = {str(p.relative_to(JS)): p.read_text() for p in JS.rglob("*.js")}
    assert offenders(sources) == []


def test_the_check_catches_a_guessed_name():
    planted = {"pages/x.js": "const yr = (f.annual_fiscal || [])[0];",
               "pages/y.js": "const n = `FY${String(end).slice(2, 4)}`;",
               "pages/z.js": "label: fiscalLabel(e, fy, true)",
               "core/figures.js": "delete out.annual_fiscal;"}
    got = offenders(planted)
    assert got == ["pages/x.js: annual_fiscal", "pages/y.js: FY${", "pages/z.js: fiscalLabel("], got
    assert offenders({"pages/dcf.js": "<th>FY ${String(y.fy_end).slice(0, 4)}</th>"}) == ["pages/dcf.js: FY ${"], "the DCF's old heading"
