"""The company's fiscal calendar, from its own filings, and the period each statement and segment figure covers.

Handoff 2 of the owner's handover pack (2026-11-03): fiscal-period labels.

**What went wrong.** On 2026-11-03 Apple's Financials page said "Summary, FY25: the fiscal year to Sep 30, 2025", and
the Segments block under it said "FY26" with no date at all. Each label was a guess about the company's calendar:

- the date was Yahoo Finance's, which dates every period to the last day of its month. Apple's fiscal 2025 ended on
  Saturday, Sep 27, 2025;
- the name was worked out from that date, on the assumption that every company names a fiscal year after the
  calendar year it ends in (app/analytics/fundamentals.py fiscal_label). Home Depot does not: its 10-K for the year
  to Feb 1, 2026 calls it fiscal 2025, and Optic printed FY26;
- Segments read the 10-K Apple filed that morning, a year ahead of the statements above it, and nothing on the
  block said which year it covered.

**So the calendar comes from the filings, as the figures do (Handoff 1).** Every fact in SEC's company facts carries
the 10-K or 10-Q it was filed in, and SEC records with it the fiscal year and period the company assigned that filing
(its cover page's fiscal year focus). A filing's own period ends on the last date it reports. So each 10-K gives a
fiscal year exactly (start, end, the company's name for it, the filing), each 10-Q a quarter, and the fourth quarter
is the 10-K's year after the third. Measured on 2026-11-03: Apple's FY2026 ended Sep 26, 2026 (10-K filed that day),
Microsoft's Q1 FY2027 ended Sep 30, 2026, NVIDIA's FY2026 ended Jan 25, 2026, Home Depot's fiscal 2025 ended Feb 1,
2026, JPMorgan's 2025 ended Dec 31, 2025.

Nothing is named that a filing does not name. A period no filing reports (a provider's column older than the XBRL
filings, a company with no US-GAAP filings) is labelled by its end date alone, with no fiscal-year name, and a period
with no date says "Period labels unavailable".

**Edge cases, as filed.** A 52- or 53-week year is measured from its own start and end (Apple's FY2023 had 53
weeks, the extra one in its first quarter). A change of year end shows as a filing whose own period is not a year:
Compass Minerals' 10-KT covered the nine months from Jan 1 to Sep 30, 2021, between its last December year and its
first September one, and a later 10-K's twelve-month comparative to Sep 30, 2021 is a recast, not a fiscal year.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence

from ..valuation import inputs as vi

ANNUAL_FORMS = ("10-K", "10-K/A", "10-KT", "10-KT/A")
QUARTER_FORMS = ("10-Q", "10-Q/A", "10-QT", "10-QT/A")
# The duration lines that mark the periods a filing reports: every 10-K and 10-Q tags at least one of them.
MARKERS = ("revenue", "net_income", "operating_income", "cfo")
YEAR_DAYS = (340, 380)            # a fiscal year, inclusive of both ends' slack (app/valuation/inputs.py YEAR_DAYS)
QUARTER_DAYS = (80, 100)          # a quarter: 13 or 14 weeks, or a calendar quarter
# A provider's date against the filing's own: Yahoo dates Apple's year Sep 30 against the 10-K's Sep 27, and
# NVIDIA's Jan 31 against Jan 25. Quarters are three months apart, so ten days cannot reach the wrong one.
MATCH_DAYS = 10
UNAVAILABLE = "Period labels unavailable"
SOURCE = "SEC EDGAR: the period each 10-K and 10-Q reports, and the fiscal year the company assigned it"
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December")
_MON = tuple(m[:3] for m in MONTHS)
_DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
# What each kind of period is called on its badge, and what the badge means for a reader who does not know.
BADGES = {"annual": "Annual", "quarter": "Quarter", "ttm": "TTM", "balance": "Balance sheet",
          "transition": "Transition period"}
BADGE_MEANS = {"annual": "One fiscal year", "quarter": "One fiscal quarter",
               "ttm": "Trailing twelve months: the last four reported quarters",
               "balance": "Measured on one balance-sheet date", "transition": "The months between two fiscal year ends"}


def _date(s: Any) -> Optional[date]:
    try:
        return date.fromisoformat(str(s)[:10])
    except (TypeError, ValueError):
        return None


def _span(start: Any, end: Any) -> Optional[int]:
    """Days in a period, both ends counted: a 52-week year is 364, a 53-week year 371, a calendar year 365."""
    a, b = _date(start), _date(end)
    return None if a is None or b is None else (b - a).days + 1


def words(iso: Any) -> str:
    """"Sep 27, 2025", the client's fullDate()."""
    d = _date(iso)
    return "{} {}, {}".format(_MON[d.month - 1], d.day, d.year) if d else ""


def _is_calendar(end: date) -> bool:
    """A year that is the calendar year: ending in the last week of December or the first of January."""
    return (end.month == 12 and end.day >= 24) or (end.month == 1 and end.day <= 7)


def _amended(form: Any) -> bool:
    return str(form or "").endswith("/A")


# ------------------------------------------------------------------------------------------------ the filings
def _index(fl: "vi.Filings") -> Dict[str, Dict[str, Any]]:
    """Every 10-K and 10-Q in the company facts, by accession: its form, filing date, the fiscal year and period SEC
    recorded for it, and each period it reports, by end date."""
    out: Dict[str, Dict[str, Any]] = {}
    for concept in MARKERS:
        for tag in vi.TAGS.get(concept, ()):
            node = (fl.gaap or {}).get(tag) or {}
            for rows in (node.get("units") or {}).values():
                for r in rows:
                    accn, form, start, end = r.get("accn"), r.get("form"), r.get("start"), r.get("end")
                    if not accn or form not in ANNUAL_FORMS + QUARTER_FORMS or not start or not end:
                        continue
                    span = _span(start, end)
                    # a period that ends after the filing was made is not one it reports
                    if not span or span <= 0 or (r.get("filed") and str(end) > str(r["filed"])):
                        continue
                    f = out.setdefault(accn, {"accn": accn, "form": form, "filed": r.get("filed"),
                                              "fy": Counter(), "fp": Counter(), "periods": {}})
                    f["fy"][r.get("fy")] += 1
                    f["fp"][r.get("fp")] += 1
                    f["periods"].setdefault(end, set()).add(start)
    for f in out.values():
        f["end"] = max(f["periods"])
        f["fy"] = next((k for k, _ in f["fy"].most_common() if isinstance(k, int)), None)
        f["fp"] = next((k for k, _ in f["fp"].most_common() if k), None)
    return out


def _own_start(f: Dict[str, Any], lo: int, hi: int) -> Optional[str]:
    """The start of the filing's own period: the one of length lo..hi days ending on its last date, else (a transition
    period) the longest one ending there."""
    starts = sorted(f["periods"].get(f["end"], ()), key=lambda s: -(_span(s, f["end"]) or 0))
    fit = [s for s in starts if lo <= (_span(s, f["end"]) or 0) <= hi]
    return fit[0] if fit else (starts[0] if starts and lo == YEAR_DAYS[0] else None)


def _groups(filings: Iterable[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """Filings whose own periods end within ten days of each other report the same period (an original and its
    amendments), newest period first."""
    out: List[List[Dict[str, Any]]] = []
    for f in sorted(filings, key=lambda x: x["end"], reverse=True):
        if out and abs((_date(out[-1][0]["end"]) - _date(f["end"])).days) <= MATCH_DAYS:
            out[-1].append(f)
        else:
            out.append([f])
    return out


def _original(group: List[Dict[str, Any]]) -> Dict[str, Any]:
    """The filing that first reported a period: an amendment only when it is all there is."""
    return min(group, key=lambda f: (_amended(f["form"]), f.get("filed") or "", f["accn"]))


def _name_ok(fy: Any, end: date, lo: int, hi: int) -> Optional[int]:
    """The fiscal year a filing names, when it is a year the period can belong to: the year it ends in or the one
    before (Home Depot names its years by their start). A name outside that is a filer's cover-page error, and no
    name is better than a wrong one."""
    return fy if isinstance(fy, int) and end.year + lo <= fy <= end.year + hi else None


def _link(cik: Optional[str], f: Dict[str, Any]) -> Dict[str, Any]:
    return {"form": f["form"], "filed": f.get("filed"), "accession": f["accn"], "url": vi.filing_url(cik, f["accn"])}


def calendar(fl: Optional["vi.Filings"]) -> Dict[str, Any]:
    """The company's fiscal years and quarters as its 10-Ks and 10-Qs report them, newest first.

    {available, years: [{fy, start, end, days, weeks, transition, filing, amended}], quarters: [{fy, fq, start, end,
    days, weeks, derived, filing}], kind, year_end, changes, basis, source}."""
    if fl is None:
        return {"available": False, "reason": "No SEC filings were read for this company.", "years": [], "quarters": [],
                "changes": []}
    cik = getattr(fl, "cik", None)
    idx = _index(fl)
    years: List[Dict[str, Any]] = []
    for g in _groups(f for f in idx.values() if f["form"] in ANNUAL_FORMS):
        o = _original(g)
        start = _own_start(o, *YEAR_DAYS)
        days = _span(start, o["end"]) if start else None
        transition = bool(days) and not (YEAR_DAYS[0] <= days <= YEAR_DAYS[1])
        end = _date(o["end"])
        years.append({"fy": _name_ok(o["fy"], end, -1, 0), "start": start, "end": o["end"], "days": days,
                      "weeks": {364: 52, 371: 53}.get(days or 0), "transition": transition,
                      "filing": _link(cik, o),
                      "amended": [_link(cik, f) for f in sorted(g, key=lambda f: f.get("filed") or "")
                                  if f is not o and _amended(f["form"])]})
    quarters: List[Dict[str, Any]] = []
    for g in _groups(f for f in idx.values() if f["form"] in QUARTER_FORMS):
        o = _original(g)
        start = _own_start(o, *QUARTER_DAYS)
        days = _span(start, o["end"]) if start else None
        fp = str(o["fp"] or "")
        # a 10-QT reports the months between two year ends (VF Corp's, Dec 31, 2017 to Mar 31, 2018), not a quarter
        # of either year, whatever its cover page calls it
        tq = str(o["form"]).startswith("10-QT")
        quarters.append({"fy": None if tq else _name_ok(o["fy"], _date(o["end"]), -1, 1),
                         "fq": None if tq else int(fp[1]) if len(fp) == 2 and fp[0] == "Q" and fp[1] in "1234" else None,
                         "start": start, "end": o["end"], "days": days, "derived": False, "transition": tq,
                         "filing": _link(cik, o)})
    # The fourth quarter of each year is the 10-K's: it ends on the year's last day and starts after the third.
    for y in years:
        if y["transition"]:
            continue
        if any(abs((_date(q["end"]) - _date(y["end"])).days) <= MATCH_DAYS for q in quarters):
            continue
        prior = [q for q in quarters if not q["transition"] and 45 <= (_date(y["end"]) - _date(q["end"])).days <= 120]
        q3 = max(prior, key=lambda q: q["end"]) if prior else None
        start = (_date(q3["end"]) + timedelta(days=1)).isoformat() if q3 else None
        quarters.append({"fy": y["fy"], "fq": 4, "start": start, "end": y["end"], "days": _span(start, y["end"]) if start else None,
                         "derived": True, "transition": False, "filing": y["filing"]})
    quarters.sort(key=lambda q: q["end"], reverse=True)
    # A quarter takes the name of the fiscal year it falls in, as that year's 10-K gives it, where the 10-K is filed;
    # its own 10-Q's name otherwise (the quarters after the latest 10-K).
    for q in quarters:
        if q["transition"]:
            continue
        holder = next((y for y in reversed(years) if not y["transition"]
                       and 0 <= (_date(y["end"]) - _date(q["end"])).days <= 380), None)
        if holder and holder["fy"] is not None:
            q["fy"] = holder["fy"]
    kind = _kind(years)
    for q in quarters:
        q["weeks"] = ({91: 13, 98: 14}.get(q["days"] or 0) if kind == "52_53_week" else None)
    if not years and not quarters:
        return {"available": False, "reason": "The filings carry no US-GAAP fiscal year (a foreign issuer reporting "
                                              "under IFRS, for one).", "years": [], "quarters": [], "changes": [],
                "basis": "IFRS" if getattr(fl, "ifrs", False) else None}
    return {"available": True, "cik": cik, "years": years, "quarters": quarters, "kind": kind,
            "year_end": _year_end_words(years, kind), "changes": _changes(years, quarters, kind), "basis": "GAAP",
            "source": SOURCE, "retrieved": getattr(fl, "retrieved", None)}


def _kind(years: List[Dict[str, Any]]) -> Optional[str]:
    """How the company's year is set: "calendar", "fixed" (the same date each year, Microsoft's June 30) or
    "52_53_week" (a weekday near a month's end, so the date drifts and some years have 53 weeks)."""
    full = [y for y in years if not y["transition"] and y["days"]][:6]
    if not full:
        return None
    if any(y["weeks"] for y in full):
        return "52_53_week"
    if all(_is_calendar(_date(y["end"])) for y in full):
        return "calendar"
    return "fixed"


def _year_end_words(years: List[Dict[str, Any]], kind: Optional[str]) -> Optional[str]:
    """The year end in words: "December 31", "June 30", "the last Saturday of September", "the Saturday nearest the
    end of March"."""
    full = [y for y in years if not y["transition"]][:6]
    if not full:
        return None
    last = _date(full[0]["end"])
    if kind != "52_53_week":
        return "{} {}".format(MONTHS[last.month - 1], last.day)
    ends = [_date(y["end"]) for y in full]
    wd = {e.weekday() for e in ends}
    if len(wd) != 1:
        return "a date near the end of {}".format(MONTHS[last.month - 1])
    day = _DAYS[ends[0].weekday()]
    if len({e.month for e in ends}) == 1 and all((e + timedelta(days=7)).month != e.month for e in ends):
        return "the last {} of {}".format(day, MONTHS[last.month - 1])
    near = Counter((e - timedelta(days=10)).month for e in ends).most_common(1)[0][0]
    return "the {} nearest the end of {}".format(day, MONTHS[near - 1])


def _md(iso: str, loose: bool = False) -> str:
    """A year end as a date in the year, "September 30"; for a 52- or 53-week year, whose date drifts, "late March"."""
    d = _date(iso)
    if not d:
        return ""
    if loose and (d.day >= 22 or d.day <= 7):
        return "{} {}".format("late" if d.day >= 22 else "early", MONTHS[d.month - 1])
    return "{} {}".format(MONTHS[d.month - 1], d.day)


def _changes(years: List[Dict[str, Any]], quarters: Sequence[Dict[str, Any]] = (), kind: Optional[str] = None
             ) -> List[Dict[str, Any]]:
    """Each change of fiscal year end: the last year end before it, the first after, and the transition period between
    when one was filed (a 10-KT, or a 10-QT for a short one). A year end that moves by more than ten days counts with
    or without one."""
    out: List[Dict[str, Any]] = []
    loose = kind == "52_53_week"
    ys = list(reversed(years))                                   # oldest first
    for i, y in enumerate(ys):
        if y["transition"]:
            before = next((x for x in reversed(ys[:i]) if not x["transition"]), None)
            after = next((x for x in ys[i + 1:] if not x["transition"]), None)
            if not after and not before:
                continue
            out.append(_change(before, after or y, y, loose))
            continue
        prev = ys[i - 1] if i else None
        if prev is None or prev["transition"]:
            continue
        # the year end itself moved (more than ten days round the calendar); a year missing from the facts is a gap of
        # two years on the same date, and is not a change
        a, b = _date(prev["end"]), _date(y["end"])
        pos = abs(a.timetuple().tm_yday - b.timetuple().tm_yday)
        if min(pos, 365 - pos) > MATCH_DAYS:
            t = next((q for q in quarters if q.get("transition") and prev["end"] < q["end"] < y["end"]), None)
            out.append(_change(prev, y, t, loose))
    return list(reversed(out))


def _change(before: Optional[Dict[str, Any]], after: Dict[str, Any], t: Optional[Dict[str, Any]], loose: bool
            ) -> Dict[str, Any]:
    frm, to = (_md(before["end"], loose) if before else None), _md(after["end"], loose)
    lead = ("The fiscal year end moved from {} to {}".format(frm, to) if frm else "The fiscal year end moved to {}".format(to))
    out = {"before": before["end"] if before else None, "after": after["end"], "from": frm, "to": to, "transition": None}
    if t:
        months = round((t.get("days") or 0) / 30.44)
        f = t["filing"]
        out["transition"] = {"start": t.get("start"), "end": t["end"], "days": t.get("days"), "months": months,
                             "filing": f}
        span = ("the {} months from {} to {}".format(months, words(t["start"]), words(t["end"])) if t.get("start")
                else "the months to {}".format(words(t["end"])))
        out["note"] = ("{}: {} were a transition period, filed on a {}{}. Years before and after it cover different "
                       "months.".format(lead, span, f["form"], " on {}".format(words(f["filed"])) if f.get("filed") else ""))
    else:
        out["note"] = ("{} after the year ended {}: years before and after cover different months.".format(
            lead, words(before["end"])) if before else "{}.".format(lead))
    return out


def from_filing_list(rows: Sequence[Dict[str, Any]], cik: Optional[str] = None) -> Dict[str, Any]:
    """A calendar with dates and filings but no names, from EDGAR's list of a company's filings (the segments reader's
    own, app/analytics/segments.py filings): each 10-K's and 10-Q's period of report is its period's last day. Used
    when the company facts could not be read; a period it labels says its end date and filing, never a name."""
    years, quarters = [], []
    for r in rows or []:
        if not r.get("period") or r.get("form") not in ANNUAL_FORMS + QUARTER_FORMS:
            continue
        link = {"form": r["form"], "filed": r.get("filed"), "accession": r.get("accession"),
                "url": vi.filing_url(cik, r.get("accession")) if cik else None}
        rec = {"fy": None, "start": None, "end": r["period"], "days": None, "weeks": None, "filing": link}
        if r["form"] in ANNUAL_FORMS:
            years.append(dict(rec, transition=False, amended=[]))
        else:
            quarters.append(dict(rec, fq=None, derived=False))
    for y in years:
        quarters.append({"fy": None, "fq": None, "start": None, "end": y["end"], "days": None, "weeks": None,
                         "derived": True, "filing": y["filing"]})
    if not years and not quarters:
        return {"available": False, "reason": "No 10-K or 10-Q in the filing list.", "years": [], "quarters": [],
                "changes": []}
    return {"available": True, "named": False, "cik": cik, "years": sorted(years, key=lambda y: y["end"], reverse=True),
            "quarters": sorted(quarters, key=lambda q: q["end"], reverse=True), "kind": None, "year_end": None,
            "changes": [], "basis": None, "source": "SEC EDGAR: each filing's period of report"}


# ------------------------------------------------------------------------------------------------ one period
def _match(items: Sequence[Dict[str, Any]], end: date) -> Optional[Dict[str, Any]]:
    best = None
    for x in items:
        gap = abs((_date(x["end"]) - end).days)
        if gap <= MATCH_DAYS and (best is None or gap < best[0]):
            best = (gap, x)
    return best[1] if best else None


def short_name(rec: Dict[str, Any], kind: str) -> Optional[str]:
    """The company's own short name for a period: "FY25", "Q3 FY26"; "2025" and "Q3 2025" for a calendar year.
    None when no filing names it."""
    fy = rec.get("fy")
    if fy is None or rec.get("transition"):
        return None
    cal = _is_calendar(_date(rec["end"])) if kind == "annual" else False
    if kind == "quarter":
        holder_end = rec.get("year_end")
        cal = bool(holder_end) and _is_calendar(_date(holder_end))
    if kind == "annual":
        return str(fy) if cal else "FY{:02d}".format(fy % 100)
    if not rec.get("fq"):
        return None
    return "Q{} {}".format(rec["fq"], fy) if cal else "Q{} FY{:02d}".format(rec["fq"], fy % 100)


def describe(cal: Optional[Dict[str, Any]], end: Any, kind: str = "annual", *, provider: Optional[str] = None
             ) -> Dict[str, Any]:
    """One period as a reader needs it: its type and badge, its exact start and end, the company's name for it, a plain
    label ("Fiscal year ended Sep 27, 2025") and the filing that reported it.

    `end` is the date the figures' source gives the period (a provider dates Apple's year Sep 30); the label is the
    filing's own date when a filing reports the period. `provider` names that source for a period no filing reports,
    which is then labelled by its date alone ("Year to Mar 31, 2026, as Yahoo Finance dates it") with no name."""
    d = _date(end)
    badge = BADGES.get(kind, kind)
    if d is None:
        return {"type": kind, "badge": badge, "available": False, "label": UNAVAILABLE, "short": None, "end": None,
                "why": "No end date for this period."}
    cal = cal or {}
    pool = (cal.get("years") if kind == "annual" else cal.get("quarters")) or []
    hit = _match(pool, d)
    if hit:
        rec = dict(hit)
        if kind == "quarter":
            holder = next((y for y in reversed(cal.get("years") or []) if not y.get("transition")
                           and 0 <= (_date(y["end"]) - _date(hit["end"])).days <= 380), None)
            rec["year_end"] = holder["end"] if holder else (cal.get("years") or [{}])[0].get("end")
        transition = bool(rec.get("transition"))
        typ = "transition" if transition else kind
        lead = ("Transition period" if transition else "Fiscal year" if kind == "annual" else "Quarter")
        out = {"type": typ, "badge": BADGES.get(typ, typ), "available": True, "start": rec.get("start"),
               "end": rec["end"], "fy": rec.get("fy"), "fq": rec.get("fq") if kind == "quarter" else None,
               "short": short_name(rec, kind), "label": "{} ended {}".format(lead, words(rec["end"])),
               "weeks": rec.get("weeks"), "days": rec.get("days"), "filing": rec.get("filing"),
               "derived": bool(rec.get("derived")), "dated_by": "filing"}
        if out["weeks"] == 53 or out["weeks"] == 14:
            out["note"] = ("A 53-week year, one week longer than the years beside it." if kind == "annual"
                           else "A 14-week quarter, one week longer than the quarters beside it.")
        if transition:
            out["note"] = "Not a full fiscal year: {}.".format(_months(rec.get("days")))
        if str(rec["end"]) != str(end)[:10]:
            out["provider_end"] = str(end)[:10]
        return out
    nxt = _next(cal, d, kind)
    if nxt:
        return nxt
    out = {"type": kind, "badge": badge, "available": True, "start": None, "end": str(end)[:10], "fy": None, "fq": None,
           "short": None, "label": "{} to {}".format("Year" if kind == "annual" else "Quarter", words(end)),
           "weeks": None, "filing": None, "derived": False, "dated_by": "provider" if provider else "source"}
    if provider:
        out["label"] += ", as {} dates it".format(provider)
        out["note"] = ("No filing Optic has read reports this period, so it is named by its end date only."
                       if cal.get("available") else "Fiscal-year names come from the company's SEC filings, which "
                                                    "Optic could not read for this company.")
    return out


def _months(days: Optional[int]) -> str:
    return "{} months".format(round(days / 30.44)) if days else "a shorter period"


def _month_end(d: date) -> date:
    return (d.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)


def _add_months(d: date, n: int) -> date:
    """`d` moved n months on: the month's last day when `d` is one (June 30 to September 30), else the same day."""
    m = d.month - 1 + n
    first = date(d.year + m // 12, m % 12 + 1, 1)
    last = _month_end(first)
    return last if d == _month_end(d) else first.replace(day=min(d.day, last.day))


def _next(cal: Dict[str, Any], d: date, kind: str) -> Optional[Dict[str, Any]]:
    """The period after the latest the filings report, when `d` is its end: a company's results come out days or
    weeks before its 10-Q or 10-K, and the provider's statements and its earnings dates can be ahead of the filings.

    Its name is its place in the company's own calendar (the quarter after the third is the fourth, the year after
    fiscal 2026 is fiscal 2027), nothing worked out from a date. Its end is the calendar's own step: three months or a
    year on for a fixed year end; thirteen weeks or fifty-two for a 52- or 53-week year, said as "about", since a
    53-week year's extra week may fall in it. It says it is not yet filed."""
    if not (cal or {}).get("available") or cal.get("named") is False:
        return None
    pool = [p for p in (cal.get("years") if kind == "annual" else cal.get("quarters")) or [] if not p.get("transition")]
    if not pool:
        return None
    last = pool[0]
    if last.get("fy") is None or (kind == "quarter" and not last.get("fq")):
        return None
    le = _date(last["end"])
    weekly = cal.get("kind") == "52_53_week"
    end = le + timedelta(days=(91 if kind == "quarter" else 364)) if weekly else _add_months(le, 3 if kind == "quarter" else 12)
    if abs((d - end).days) > MATCH_DAYS:
        return None
    if kind == "quarter":
        fq, fy = last["fq"] % 4 + 1, last["fy"] + (1 if last["fq"] == 4 else 0)
    else:
        fq, fy = None, last["fy"] + 1
    rec = {"fy": fy, "fq": fq, "end": end.isoformat(),
           "year_end": (cal.get("years") or [{}])[0].get("end") if kind == "quarter" else end.isoformat()}
    when = "{}{}".format("about " if weekly else "", words(end))
    lead = "Fiscal year" if kind == "annual" else "Quarter"
    return {"type": kind, "badge": BADGES[kind], "available": True, "start": (le + timedelta(days=1)).isoformat(),
            "end": end.isoformat(), "fy": fy, "fq": fq, "short": short_name(rec, kind),
            "label": "{} {} {}, not yet filed".format(lead, "to" if weekly else "ended", when), "weeks": None,
            "filing": None, "derived": False, "projected": True, "dated_by": "calendar",
            "provider_end": d.isoformat() if d != end else None,
            "note": "Results are out before the {}: the period is named by its place in the company's calendar and "
                    "dated by how the company sets its year.".format("10-K" if kind == "annual" else "10-Q or 10-K")}


def for_report(cal: Optional[Dict[str, Any]], report_date: Any) -> Optional[Dict[str, Any]]:
    """The fiscal quarter an earnings report covers: the latest quarter in the filings that ended at least five days
    before the report and no more than 120 (a 10-K's year is reported later than a quarter), or the quarter after
    the latest filed one when the report is out before its 10-Q or 10-K (_next). None when the filings do not say,
    and then nothing is guessed."""
    r = _date(report_date)
    if r is None or not (cal or {}).get("available"):
        return None
    cands = [q for q in cal.get("quarters") or [] if 5 <= (r - _date(q["end"])).days <= 120]
    if cands:
        return describe(cal, max(cands, key=lambda q: q["end"])["end"], "quarter")
    q = [x for x in cal.get("quarters") or [] if not x.get("transition")]
    if not q:
        return None
    nxt = _next(cal, _date(q[0]["end"]) + timedelta(days=91), "quarter")
    return nxt if nxt and 5 <= (r - _date(nxt["end"])).days <= 120 else None


def for_statements(cal: Optional[Dict[str, Any]], fin: Optional[Dict[str, Any]], provider: str = "Yahoo Finance"
                   ) -> Dict[str, Any]:
    """The period of every column of the provider's statements (app/analytics/fundamentals.py analyse_financials),
    matched to the filings."""
    fin = fin if isinstance(fin, dict) else {}
    out = {"annual": [describe(cal, p, "annual", provider=provider) for p in fin.get("annual_periods") or []],
           "quarterly": [describe(cal, p, "quarter", provider=provider) for p in fin.get("quarterly_periods") or []],
           "basis": (cal or {}).get("basis"),
           "dated_by": "filings" if (cal or {}).get("available") else "provider"}
    return out


def public(cal: Optional[Dict[str, Any]], years: int = 6, quarters: int = 10) -> Dict[str, Any]:
    """The calendar as a page needs it: the recent years and quarters, how the year is set, and any change."""
    cal = cal or {}
    if not cal.get("available"):
        return {"available": False, "reason": cal.get("reason") or UNAVAILABLE, "basis": cal.get("basis")}
    keep = ("fy", "fq", "start", "end", "days", "weeks", "transition", "derived", "filing")
    return {"available": True, "kind": cal.get("kind"), "year_end": cal.get("year_end"), "basis": cal.get("basis"),
            "changes": cal.get("changes") or [], "source": cal.get("source"), "named": cal.get("named", True),
            "years": [{k: y.get(k) for k in keep if k in y} for y in (cal.get("years") or [])[:years]],
            "quarters": [{k: q.get(k) for k in keep if k in q} for q in (cal.get("quarters") or [])[:quarters]]}


def in_words(per: Optional[Dict[str, Any]]) -> str:
    """A period inside a sentence: "the fiscal year ended Sep 27, 2025 (FY25)", "the quarter ended Jun 27, 2026
    (Q3 FY26)", "the year to Mar 31, 2026"."""
    if not per or not per.get("available"):
        return "a period Optic could not date"
    lab = per["label"]
    lab = lab[0].lower() + lab[1:]
    return "the {}{}".format(lab, " ({})".format(per["short"]) if per.get("short") else "")


def changes_between(cal: Optional[Dict[str, Any]], ends: Iterable[Any]) -> List[Dict[str, Any]]:
    """The changes of year end that fall inside a run of periods: what a block showing them must say."""
    ds = sorted(d for d in (_date(e) for e in ends) if d)
    if not ds:
        return []
    lo, hi = ds[0], ds[-1]
    return [c for c in (cal or {}).get("changes") or []
            if (c.get("after") and lo <= _date(c["after"]) and (c.get("before") is None or _date(c["before"]) <= hi))
            or (c.get("transition") and lo <= _date(c["transition"]["end"]) <= hi)]


# ------------------------------------------------------------------------------------------------ reported totals
_CONCEPT = {"revenue": "revenue", "operating_income": "operating_income"}


def _quarter_fact(fl: "vi.Filings", concept: str, end: str) -> Optional[Dict[str, Any]]:
    unit = vi.UNITS.get(concept, "USD")
    for tag in vi.TAGS.get(concept, ()):
        rows = [r for r in fl._rows(tag, unit)                                              # noqa: SLF001
                if r.get("form") in ANNUAL_FORMS + QUARTER_FORMS and r.get("start")
                and QUARTER_DAYS[0] <= (_span(r["start"], r["end"]) or 0) <= QUARTER_DAYS[1]
                and abs((_date(r["end"]) - _date(end)).days) <= 3 and vi._num(r.get("val")) is not None]  # noqa: SLF001
        if rows:
            return fl._fact(concept, tag, rows, unit)                                       # noqa: SLF001
    return None


def reported_total(fl: Optional["vi.Filings"], cal: Optional[Dict[str, Any]], metric: str, end: str, kind: str
                   ) -> Optional[Dict[str, Any]]:
    """The consolidated figure a segment table should add up to, for the same period, from the same filings: the
    year's total from its 10-K, a quarter's from its 10-Q, and a fourth quarter as the year less the nine months to
    the third (a 10-K reports the year, not its fourth quarter). None when the filings do not carry it."""
    concept = _CONCEPT.get(metric)
    if fl is None or concept is None or _date(end) is None:
        return None
    try:
        if kind == "year":
            f = fl.flow(concept, end)
            return _total(f) if f else None
        f = _quarter_fact(fl, concept, end)
        if f:
            return _total(f)
        year = next((y for y in (cal or {}).get("years") or [] if abs((_date(y["end"]) - _date(end)).days) <= 3
                     and not y.get("transition") and y.get("start")), None)
        q3 = next((q for q in (cal or {}).get("quarters") or [] if 45 <= (_date(end) - _date(q["end"])).days <= 120),
                  None)
        if not year or not q3:
            return None
        fy = fl.flow(concept, year["end"])
        ytd = vi._ytd(fl, concept, year["start"], q3["end"], tag_only=(fy or {}).get("tag"))  # noqa: SLF001
        if not fy or not ytd:
            return None
        out = _total(fy)
        out.update(value=float(fy["value"]) - float(ytd["value"]), derived=True)
        return out
    except Exception:                                                                      # noqa: BLE001
        return None


def _total(f: Dict[str, Any]) -> Dict[str, Any]:
    return {"value": float(f["value"]), "form": f.get("form"), "filed": f.get("filed"), "url": f.get("url"),
            "tag": f.get("tag"), "derived": False}
