"""Revenue and operating income broken out by segment, geography and product.

The consolidated numbers were already here: `sec_facts` reads SEC's
`companyfacts` API for thirteen years of quarterly revenue and EPS. This is the
question that API cannot answer.

**Why companyfacts is not enough, measured.** It publishes one value per (tag,
period, unit) with no dimensions at all, so a revenue figure tagged with a
business-segment axis is simply absent from it. Probed on Meta: `companyfacts`
returns five namespaces — dei, ecd, ffd, srt, us-gaap — and no custom namespace
whatsoever, so neither the segment breakdown nor any company-specific metric is
reachable through it.

**So this reads the filings.** Each 10-Q and 10-K has an XBRL instance document
carrying every fact with its full context, dimensions included. Probed on Meta's
June 2026 10-Q: 270 contexts, 254 of them dimensioned, including
StatementBusinessSegmentsAxis. The figures come out matching the paid terminals
to the cent — advertising revenue 59,363,000,000 for the quarter, US and Canada
23,863,000,000, Family of Apps operating income 23,394,000,000, Reality Labs
-4,619,000,000.

**What is not here, and why.** Company-authored operating metrics — daily active
people, ad impressions delivered, subscriber counts — are not in the XBRL. Meta's
custom namespace was enumerated across both its latest 10-Q and 10-K: 35 and 42
tags, every one an accounting extension for litigation, tax, leases or
non-marketable securities, and zero occurrences of DailyActive, MonthlyActive or
ActivePeople in either instance. Those numbers live in the quarterly press
release, as prose and HTML tables laid out differently by every issuer. Scraping
them per company is not a feature, it is a maintenance contract, so this reports
the breakdowns it can stand behind and says the KPIs are not in the filings.

**The cost.** An instance document is about a megabyte, and the last nine
filings cover roughly two years. That is nine requests, so parsing is capped per
call and cached per accession forever: a filing does not change after EDGAR
accepts it. A cold panel returns what it managed and says how many filings it
has not read, exactly as app/insiders.py does.
"""

from __future__ import annotations

import datetime as dt
import logging
import os
import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple

from .. import feeds
from . import sec_facts

log = logging.getLogger(__name__)

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SUBMISSIONS_TTL = 6 * 3600
FILING_TTL = 30 * 86400

# A ceiling, not a target, and usually not the binding one.
#
# EDGAR's `submissions` endpoint returns the company's most recent filings of
# every type in one block, and older ones live in paginated archives this does
# not fetch. Measured on Meta: that block holds nine 10-Qs and 10-Ks, which
# after deriving the fourth quarters is twelve quarters of history. Raising this
# costs nothing per call — parsing is capped at PARSE_BUDGET either way and
# every parse is cached forever — but it will not reach further back than the
# block does.
FILINGS_WANTED = int(os.environ.get("SEGMENT_FILINGS", "13"))
# How many unread instance documents one call will fetch. Each is ~1MB.
PARSE_BUDGET = int(os.environ.get("SEGMENT_PARSE_BUDGET", "3"))
INSTANCE_TIMEOUT = float(os.environ.get("SEGMENT_TIMEOUT", "60"))

XBRLI = "{http://www.xbrl.org/2003/instance}"
XBRLDI = "{http://xbrl.org/2006/xbrldi}"

# The axes worth breaking out, in the order a reader wants them, with the label
# the panel shows. All four are standard us-gaap or srt axes rather than
# company extensions, which is what makes this work for any filer rather than
# only for the one it was built against.
AXES: List[Dict[str, str]] = [
    {"axis": "StatementBusinessSegmentsAxis", "id": "segment",
     "label": "By business segment"},
    {"axis": "ProductOrServiceAxis", "id": "product",
     "label": "By product and service"},
    {"axis": "StatementGeographicalAxis", "id": "geography",
     "label": "By geography"},
]
AXIS_BY_ID = {a["id"]: a for a in AXES}

# The metrics, and the tags each can arrive under. Revenue reuses sec_facts'
# list for the reason that module documents: revenue has lived under at least
# six us-gaap tags and companies switch mid-history.
METRICS: List[Dict[str, Any]] = [
    {"id": "revenue", "label": "Revenue", "tags": sec_facts.REVENUE_TAGS},
    {"id": "operating_income", "label": "Operating income",
     "tags": ("OperatingIncomeLoss",)},
]
METRIC_BY_ID = {m["id"]: m for m in METRICS}

# A quarter by duration, and a year. Same bounds sec_facts uses and for the same
# reason: fiscal quarters end on weekdays, so the durations wobble around 91.
Q_MIN, Q_MAX = 80, 100
Y_MIN, Y_MAX = 340, 380

BLIND = ("Only what the filer tagged. A company that reports one segment has one "
         "row here, and a breakdown disclosed in prose rather than in XBRL is "
         "not reachable. Operating metrics — daily users, impressions, "
         "subscribers — are not in the filings at all: they are published in the "
         "quarterly press release, laid out differently by every issuer.")

METHOD = ("Read from the XBRL instance document of each 10-Q and 10-K, which "
          "carries every fact with its dimensions. SEC's companyfacts API is "
          "consolidated only, so a segment figure is absent from it entirely. "
          "Fourth quarters are derived as the annual figure minus the three "
          "reported quarters, because a 10-K reports the year rather than Q4.")


def _member(raw: str) -> str:
    """A dimension member as words. "USCanadaMember" -> "US Canada"."""
    name = (raw or "").split(":")[-1]
    name = re.sub(r"Member$", "", name)
    # Two splits, not one. The lookbehind on a lowercase letter alone leaves
    # "USCanadaMember" as "USCanada": an acronym followed by a word has no
    # lowercase at the boundary.
    name = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name)
    name = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", name)
    return name.strip() or raw


def _days(start: Optional[str], end: Optional[str]) -> Optional[int]:
    if not start or not end:
        return None
    try:
        return (dt.date.fromisoformat(end) - dt.date.fromisoformat(start)).days
    except ValueError:
        return None


def _num(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out else None


def filings(ticker: str, force: bool = False) -> Dict[str, Any]:
    """The recent 10-Q and 10-K filings for a ticker, newest first."""
    symbol = (ticker or "").strip().upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}", symbol or ""):
        return {"available": False, "reason": "That does not look like a symbol."}
    if not feeds.CONTACT_OK:
        return {"available": False, "needs_contact": True,
                "reason": ("This reads filings from SEC EDGAR, which requires a "
                           "contact address in every request and refuses the ones "
                           "without it. Set FEED_CONTACT to an email you are "
                           "willing to be contacted on.")}
    try:
        cik = sec_facts.cik_for(symbol)
    except sec_facts.LookupUnavailable as exc:
        return {"available": False,
                "reason": "EDGAR's ticker directory was unreadable ({}).".format(exc)}
    if not cik:
        return {"available": False,
                "reason": "EDGAR does not index a company under {}.".format(symbol)}

    try:
        blob = feeds.fetch_json(SUBMISSIONS_URL.format(cik=cik),
                                0 if force else SUBMISSIONS_TTL,
                                key="seg:subs:" + cik)
    except Exception as exc:                                  # noqa: BLE001
        return {"available": False,
                "reason": "EDGAR's filing list did not answer ({}).".format(
                    type(exc).__name__)}

    recent = ((blob or {}).get("filings") or {}).get("recent") or {}
    forms = recent.get("form") or []
    rows: List[Dict[str, Any]] = []
    for i, form in enumerate(forms):
        if form not in ("10-Q", "10-K"):
            continue
        acc = (recent.get("accessionNumber") or [None] * (i + 1))[i]
        primary = (recent.get("primaryDocument") or [""] * (i + 1))[i]
        if not acc or not primary:
            continue
        # The instance document is the primary document with .htm swapped for
        # _htm.xml. Derived rather than listed: the folder listing is a second
        # request per filing and this naming is EDGAR's own convention for
        # inline XBRL, which every 10-Q and 10-K has used since 2019.
        instance = re.sub(r"\.htm$", "_htm.xml", primary)
        if not instance.endswith("_htm.xml"):
            continue
        folder = "https://www.sec.gov/Archives/edgar/data/{}/{}".format(
            str(int(cik)), acc.replace("-", ""))
        rows.append({
            "accession": acc,
            "form": form,
            "period": (recent.get("reportDate") or [None] * (i + 1))[i],
            "filed": (recent.get("filingDate") or [None] * (i + 1))[i],
            "instance_url": "{}/{}".format(folder, instance),
        })
    return {"available": True, "cik": cik, "ticker": symbol, "rows": rows}


def parse_instance(url: str) -> Dict[str, Any]:
    """Dimensioned revenue and operating income out of one instance document."""
    body = feeds.fetch_text(url, FILING_TTL, key="seg:doc:" + url,
                            timeout=INSTANCE_TIMEOUT)
    try:
        root = ET.fromstring(body.encode("utf-8", "replace"))
    except ET.ParseError as exc:
        return {"available": False, "reason": "unparsable instance ({})".format(exc)}

    contexts: Dict[str, Dict[str, Any]] = {}
    for ctx in root.findall(XBRLI + "context"):
        period = ctx.find(XBRLI + "period")
        if period is None:
            continue
        dims = {}
        for m in ctx.iter(XBRLDI + "explicitMember"):
            axis = (m.get("dimension") or "").split(":")[-1]
            dims[axis] = (m.text or "").strip()
        contexts[ctx.get("id")] = {
            "start": period.findtext(XBRLI + "startDate"),
            "end": period.findtext(XBRLI + "endDate"),
            "dims": dims,
        }

    wanted_tags = {}
    for metric in METRICS:
        for tag in metric["tags"]:
            wanted_tags[tag] = metric["id"]
    wanted_axes = {a["axis"]: a["id"] for a in AXES}

    facts: List[Dict[str, Any]] = []
    for el in root:
        match = re.match(r"\{([^}]+)\}(.+)", el.tag)
        if not match:
            continue
        tag = match.group(2)
        metric = wanted_tags.get(tag)
        if not metric:
            continue
        ctx = contexts.get(el.get("contextRef") or "")
        if not ctx:
            continue
        dims = ctx["dims"]
        # Which of our axes this fact carries, and nothing outside them.
        #
        # The first version required exactly one dimension, which was wrong and
        # measurably so: Meta tags advertising revenue with BOTH
        # ProductOrServiceAxis and StatementBusinessSegmentsAxis, so the product
        # breakdown — advertising against other revenue, the largest line in the
        # company — was silently missing from the panel entirely.
        #
        # So a fact may carry several of our axes and contributes a row to each
        # of their tables, summed across the others. Summing the cells of a
        # cross-tab along one axis is that axis's marginal total, which is what
        # each table should show, and there is no double counting because a
        # consolidated figure carries no dimensions at all and never gets here.
        #
        # A fact carrying an axis we do not track is still skipped. Those are
        # the fair-value hierarchies, award types and equity components — 254 of
        # 270 contexts on Meta's 10-Q are dimensioned, and most of them are
        # nothing to do with segments.
        ours = [wanted_axes[a] for a in dims if a in wanted_axes]
        if not ours or len(ours) != len(dims):
            continue
        value = _num(el.text)
        if value is None:
            continue
        span = _days(ctx["start"], ctx["end"])
        if span is None:
            continue
        if Q_MIN <= span <= Q_MAX:
            kind = "quarter"
        elif Y_MIN <= span <= Y_MAX:
            kind = "year"
        else:
            continue                       # a half-year or nine-month cumulative
        for axis_id in ours:
            axis_name = next(a for a, i in wanted_axes.items() if i == axis_id)
            facts.append({
                "metric": metric, "axis": axis_id,
                "member": _member(dims[axis_name]),
                "start": ctx["start"], "end": ctx["end"],
                "kind": kind, "value": value,
                # How many of our axes this fact carried. A cell of a cross-tab
                # has to be added to its row rather than replacing it.
                "cross": len(ours),
            })
    return {"available": True, "facts": facts}


def _fill_fourth_quarters(cells: Dict[Tuple[str, str, str], float]
                          ) -> Tuple[Dict[Tuple[str, str, str], float], int]:
    """Derive Q4 as the year minus the three quarters that were reported.

    A 10-K reports the full year, so without this every fiscal year has a hole
    in its fourth column. Keyed on (metric|axis|member, kind, period end).
    """
    derived = 0
    years = [k for k in cells if k[1] == "year"]
    for key in years:
        series, _kind, end = key
        try:
            year_end = dt.date.fromisoformat(end)
        except ValueError:
            continue
        # The three quarters inside this fiscal year, by their end dates.
        inside = []
        for other in cells:
            if other[0] != series or other[1] != "quarter":
                continue
            try:
                q_end = dt.date.fromisoformat(other[2])
            except ValueError:
                continue
            if 0 < (year_end - q_end).days <= 300:
                inside.append(other)
        if len(inside) != 3:
            continue
        q4 = (series, "quarter", end)
        if q4 in cells:
            continue
        cells[q4] = round(cells[key] - sum(cells[o] for o in inside), 2)
        derived += 1
    return cells, derived


def build(ticker: str, force: bool = False, budget: int = PARSE_BUDGET,
          wanted: int = FILINGS_WANTED) -> Dict[str, Any]:
    """Quarterly breakdowns for one ticker, as tables per axis."""
    listed = filings(ticker, force=force)
    if not listed.get("available"):
        return {**listed, "tables": [], "blind_spot": BLIND}

    rows = listed["rows"][:max(1, int(wanted))]
    cells: Dict[Tuple[str, str, str], float] = {}
    labels: Dict[str, Dict[str, str]] = {}
    read = 0
    unread = 0
    failed = 0
    fetched = 0

    for entry in rows:
        key = "seg:parsed:" + entry["accession"]
        parsed = feeds.cached_json(key)
        if parsed is None:
            if fetched >= max(0, int(budget)):
                unread += 1
                continue
            fetched += 1
            try:
                parsed = parse_instance(entry["instance_url"])
            except Exception as exc:                          # noqa: BLE001
                log.info("segments: %s failed (%s)", entry["accession"], exc)
                failed += 1
                continue
            feeds.store_json(key, parsed)
        if not parsed.get("available"):
            failed += 1
            continue
        read += 1
        # Two piles per filing, and a direct figure always wins.
        #
        # A slot can be fed from both directions: Meta tags Family of Apps
        # revenue on its own AND tags advertising revenue with the product and
        # segment axes together, so the segment row has a directly reported
        # value and two cross-tab cells that sum to the same thing. Mixing them
        # in one dict made the answer depend on which fact the parser happened
        # to reach first — measured, Family of Apps came out as 59.36B, which is
        # advertising alone, where the company reported 60.37B. The other
        # ordering would have given 119.7B.
        #
        # So: `direct` for facts carrying one of our axes, `summed` for cells of
        # a cross-tab, and direct is preferred whenever it exists. The sum is
        # only ever the answer for a member that is not reported on its own,
        # which is what makes the product table possible at all.
        direct: Dict[Tuple[str, str, str], float] = {}
        summed: Dict[Tuple[str, str, str], float] = {}
        for fact in parsed.get("facts", []):
            series = "{}|{}|{}".format(fact["metric"], fact["axis"], fact["member"])
            labels[series] = {"metric": fact["metric"], "axis": fact["axis"],
                              "member": fact["member"]}
            slot = (series, fact["kind"], fact["end"])
            if fact.get("cross", 1) > 1:
                summed[slot] = round(summed.get(slot, 0.0) + fact["value"], 2)
            else:
                direct.setdefault(slot, fact["value"])
        for slot in set(direct) | set(summed):
            value = direct[slot] if slot in direct else summed[slot]
            # A restated figure appears in several filings. The newest filing is
            # first in the list, so the first value seen is the latest one.
            cells.setdefault(slot, value)

    cells, derived = _fill_fourth_quarters(cells)

    quarters = sorted({k[2] for k in cells if k[1] == "quarter"})
    tables = []
    for axis in AXES:
        for metric in METRICS:
            series = [s for s, meta in labels.items()
                      if meta["axis"] == axis["id"] and meta["metric"] == metric["id"]]
            if not series:
                continue
            body = []
            for s in sorted(series, key=lambda x: labels[x]["member"]):
                values = [cells.get((s, "quarter", q)) for q in quarters]
                if all(v is None for v in values):
                    continue
                body.append({"member": labels[s]["member"], "values": values})
            if not body:
                continue
            tables.append({
                "axis": axis["id"], "axis_label": axis["label"],
                "metric": metric["id"], "metric_label": metric["label"],
                "rows": body,
            })

    return {
        "available": True,
        "ticker": listed["ticker"],
        "quarters": quarters,
        "tables": tables,
        "filings_listed": len(rows),
        "filings_read": read,
        "filings_unread": unread,
        "filings_failed": failed,
        "fetched_now": fetched,
        "q4_derived": derived,
        "method": METHOD,
        "blind_spot": BLIND,
        "kpis": None,
        "kpi_note": ("Operating metrics are not in the filings. Meta's custom "
                     "XBRL namespace was enumerated across its latest 10-Q and "
                     "10-K: 35 and 42 tags, every one an accounting extension, "
                     "and no occurrence of daily or monthly active users or ad "
                     "impressions in either. Those figures are published in the "
                     "quarterly press release rather than tagged, so no free "
                     "structured source for them exists."),
    }
