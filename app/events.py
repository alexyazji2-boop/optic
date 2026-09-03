"""Upcoming macro releases: what is due, when, and where the date came from.

Three sources, in descending order of how much they can be trusted, and the
difference is surfaced on every row rather than smoothed over:

**Published calendars.** The BLS publishes its release schedule as iCalendar at
a stable URL — 313 events, 63 of them in the future when this was written, each
with an exact release time. CPI, PPI, the Employment Situation, JOLTS, ECI and
the rest come from there verbatim. `confidence: "published"`.

**Scraped pages.** The Fed publishes FOMC meeting dates as HTML and nothing
else: there is no ICS and no JSON (both 404). So those dates are parsed out of
the calendar page, which works until the Fed changes its markup. Parsing failure
returns no events rather than guesses, and the section says the leg is down.
`confidence: "published"` when parsed, because the date itself is official.

**Recurring rules.** The CFTC has no machine-readable schedule at all. The
Commitments of Traders report has a genuine weekly rule — Friday at 15:30 ET,
covering positions as of the previous Tuesday — so those rows are *derived* from
the rule, not read from a calendar. They are marked `confidence: "recurring"`
and the UI labels them, because a bank holiday shifts the real release and this
module has no way to know that.

Nothing here forecasts a number. It says a release is scheduled, which is a fact
about a calendar, and never what the release will contain.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from zoneinfo import ZoneInfo

from . import feeds

log = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")

# How far ahead the section looks, and the most it will list.
HORIZON_DAYS = int(__import__("os").environ.get("BRIEF_EVENT_DAYS", "21"))
LIMIT = int(__import__("os").environ.get("BRIEF_EVENT_LIMIT", "18"))

BLS_ICS = "https://www.bls.gov/schedule/news_release/bls.ics"
# Where a *reader* should be sent. The .ics above is what we parse; linking a
# person to it downloads a calendar file instead of showing them the schedule,
# which is indistinguishable from a broken link.
BLS_SCHEDULE_URL = "https://www.bls.gov/schedule/news_release/"
FOMC_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
COT_URL = ("https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm")

# The releases most people actually watch, promoted above the rest of the BLS
# schedule. Matched case-insensitively against the calendar's own SUMMARY.
HEADLINE_RELEASES = {
    "consumer price index": ("CPI", 10),
    "producer price index": ("PPI", 9),
    "employment situation": ("Jobs", 10),
    "job openings and labor turnover": ("JOLTS", 7),
    "employment cost index": ("ECI", 6),
    "real earnings": ("Real earnings", 4),
    "productivity and costs": ("Productivity", 5),
    "u.s. import and export price indexes": ("Import/export prices", 5),
    "county employment and wages": ("", 2),
    "state employment and unemployment": ("", 2),
}


# Impact bands over the importance weights above. Three bands rather than a raw
# 1-10 number: a reader deciding whether to be flat into a print needs to know
# whether this is a CPI morning or a county-wages morning, and the difference
# between weight 5 and weight 6 is not a real distinction.
#
# The thresholds are where the market's own behaviour changes. High is the set of
# releases that reprice the front end of the curve on their own — CPI, jobs, PPI,
# an FOMC decision. Medium moves a sector or confirms a trend. Low is a data
# point that matters to economists and almost never to a chart.
IMPACT_HIGH, IMPACT_MEDIUM = 8, 5

IMPACT_BANDS = {
    "high": "Repriced the front of the curve on its own more than once.",
    "medium": "Moves sectors and confirms trends; rarely repriced the index alone.",
    "low": "Routine data. Worth knowing, seldom worth trading.",
}


def _impact(importance: int) -> str:
    if importance >= IMPACT_HIGH:
        return "high"
    if importance >= IMPACT_MEDIUM:
        return "medium"
    return "low"


# What each release actually measures and why a price reacts to it. Keyed by the
# same needles as HEADLINE_RELEASES so one match serves both.
#
# These are deliberately about mechanism, not direction. "A hot CPI is bearish"
# is a claim about what the market will do; "CPI is the number the Fed's mandate
# is written against" is a fact about why the market watches. The first would be
# a forecast dressed as a definition, and it is also often wrong — the reaction
# depends on positioning going in.
WHY_IT_MATTERS = {
    "consumer price index": (
        "The inflation print the Fed's 2% mandate is written against. Rate "
        "expectations for the next two meetings usually reset within seconds of "
        "the release, which is why it moves the whole index and not just "
        "rate-sensitive sectors. Core (stripping food and energy) is what gets "
        "traded; the headline number is noisier because of petrol."
    ),
    "producer price index": (
        "Prices at the factory gate, before anything reaches a shop shelf. Read "
        "as a leading indicator for CPI and as a direct read on margins: a "
        "producer absorbing higher input costs is a producer with a thinner "
        "margin next quarter."
    ),
    "employment situation": (
        "Payrolls and the unemployment rate. The other half of the Fed's dual "
        "mandate. Average hourly earnings inside the same release is the part "
        "that ties employment back to inflation, so a strong jobs number with "
        "soft wages reads very differently from a strong one with hot wages."
    ),
    "job openings and labor turnover": (
        "Vacancies and the quit rate. Quits are the honest signal. People leave "
        "jobs when they are confident of finding a better one, so the rate falls "
        "before payrolls do. Slower and less traded than the jobs report, but it "
        "turns earlier."
    ),
    "employment cost index": (
        "The Fed's preferred wage measure, because it holds the mix of jobs "
        "constant. Average hourly earnings can fall simply because low-paid "
        "hiring picked up; this one cannot. Quarterly, so each print carries "
        "three months of information."
    ),
    "real earnings": (
        "Wages after inflation. Whether pay packets actually bought more. "
        "Derived from CPI and the jobs report, both already released, so it very "
        "rarely moves a price. It matters for the consumer-demand story rather "
        "than for the tape."
    ),
    "productivity and costs": (
        "Output per hour, and unit labour costs. This is the release that decides "
        "whether wage growth is inflationary: pay rising alongside productivity "
        "can be absorbed, pay rising without it lands in prices or margins."
    ),
    "u.s. import and export price indexes": (
        "Traded-goods prices, which is where the dollar shows up in inflation. A "
        "strong dollar makes imports cheaper and quietly does some of the Fed's "
        "work; a weak one does the opposite. Mostly a second-order read on CPI."
    ),
    "county employment and wages": (
        "Local labour-market detail, published with a long lag. Useful for "
        "regional analysis and essentially never a market event."
    ),
    "state employment and unemployment": (
        "The state-level breakdown of a national number already published. "
        "Included for completeness; it does not move an index."
    ),
    "fomc": (
        "The rate decision itself, plus the statement and, at four of the eight "
        "meetings. The projections and a press conference. The decision is "
        "usually priced well in advance, so the move tends to come from the "
        "language and the dot plot rather than the number, and often from the "
        "press conference rather than the statement."
    ),
    "commitments of traders": (
        "Weekly positioning: how large speculators and commercial hedgers are "
        "actually placed across futures. It is a Tuesday snapshot published on "
        "Friday, so it is history, not a signal. Its use is spotting a crowded "
        "trade, where an extreme reading means the marginal buyer has already "
        "bought."
    ),
}


# The agencies title their own releases with acronyms — "PPI for final demand",
# "CPI for all items" — while the calendar's ICS spells them out. Matching only
# the long form meant a release headline never resolved to its explanation, and
# fell through to the generic fallback.
ACRONYMS = {
    "cpi": "consumer price index",
    "ppi": "producer price index",
    "jolts": "job openings and labor turnover",
    "eci": "employment cost index",
}


def _why(summary: str, agency_short: str = "") -> str:
    """Plain-English note on what a release measures and why price reacts."""
    low = (summary or "").lower()
    for needle, text in WHY_IT_MATTERS.items():
        if needle in low:
            return text
    # Acronyms, matched as whole words so "eci" cannot hit inside "specimen".
    words = set(re.findall(r"[a-z]+", low))
    for short, long_form in ACRONYMS.items():
        if short in words and long_form in WHY_IT_MATTERS:
            return WHY_IT_MATTERS[long_form]
    # FOMC and COT rows are titled by their own builders, so match those too.
    if "fomc" in low or "federal open market" in low:
        return WHY_IT_MATTERS["fomc"]
    if "commitments" in low or agency_short == "CFTC":
        return WHY_IT_MATTERS["commitments of traders"]
    # The BLS schedule carries a long tail of specialist releases — worker
    # displacement, occupational projections, benchmark revisions. Writing a
    # bespoke note for each would mean inventing significance they do not have,
    # so say what is true of all of them: they are scheduled, they are real, and
    # they are not why a price moved.
    if agency_short == "BLS":
        return ("A scheduled BLS statistical release outside the set that "
                "regularly moves markets. Listed so the calendar is complete "
                "rather than because a reaction is expected.")
    return ""


def _importance(summary: str) -> int:
    low = summary.lower()
    for needle, (_short, weight) in HEADLINE_RELEASES.items():
        if needle in low:
            return weight
    return 3


def _short_label(summary: str) -> str:
    low = summary.lower()
    for needle, (short, _w) in HEADLINE_RELEASES.items():
        if needle in low and short:
            return short
    return ""


def _bls_events(force: bool = False) -> Dict[str, Any]:
    result = feeds.load_ics("bls-schedule", BLS_ICS, force=force)
    rows: List[Dict[str, Any]] = []
    for ev in result.get("events", []):
        try:
            start = datetime.fromisoformat(ev["start"])
        except (ValueError, TypeError):
            continue
        # The calendar publishes wall-clock Eastern times without a zone.
        start = start.replace(tzinfo=ET)
        rows.append({
            "title": ev["summary"],
            "short": _short_label(ev["summary"]),
            "at": start.isoformat(),
            "all_day": bool(ev.get("all_day")),
            "agency": "Bureau of Labor Statistics",
            "agency_short": "BLS",
            "source_url": BLS_SCHEDULE_URL,
            "confidence": "published",
            "importance": _importance(ev["summary"]),
        })
    return {"events": rows, "error": result.get("error"),
            "stale": bool(result.get("stale"))}


_MONTHS = ("January February March April May June July August September "
           "October November December").split()


def _fomc_events(force: bool = False) -> Dict[str, Any]:
    """Parse FOMC meeting dates out of the Fed's calendar page.

    The page lists each meeting as a month and a day range. Two-day meetings are
    what matter — the statement lands on the second day at 14:00 ET — so a range
    is collapsed to its final day. Anything that doesn't parse is dropped.
    """
    result = feeds.load_html("fomc-calendar", FOMC_URL, force=force)
    text = result.get("text") or ""
    if not text:
        return {"events": [], "error": result.get("error") or "empty page",
                "stale": bool(result.get("stale"))}

    # Anchor on the page's own structure rather than on prose dates.
    #
    # The first version of this matched "Month DD, YYYY" anywhere in the stripped
    # text and produced 46 dates spanning 2021-2028 with exactly one in the
    # future — it was reading archive links, "(Released February 18, 2026)"
    # minutes notes, and the tentative out-year schedule, not the meeting table.
    #
    # Each meeting is really a pair of divs:
    #   <div class="fomc-meeting__month"><strong>January</strong></div>
    #   <div class="fomc-meeting__date">27-28</div>
    # under an "<h4>… 2026 FOMC Meetings" heading. So: track the year from the
    # headings, then read month/day pairs in document order.
    rows: List[Dict[str, Any]] = []
    seen = set()

    tokens = re.finditer(
        r"(?P<year>20\d\d)\s+FOMC\s+Meetings"
        r"|fomc-meeting__month[^>]*>\s*(?:<strong>)?\s*(?P<month>[A-Z][a-z]+)"
        r"|fomc-meeting__date[^>]*>\s*(?P<days>[\d\-–/\s*]+)",
        text)

    year: Optional[int] = None
    month: Optional[int] = None
    for token in tokens:
        if token.group("year"):
            year = int(token.group("year"))
            month = None
            continue
        if token.group("month"):
            name = token.group("month")
            month = _MONTHS.index(name) + 1 if name in _MONTHS else None
            continue

        days_raw = token.group("days") or ""
        if year is None or month is None:
            continue
        # "27-28", "17-18*", "28" — the statement lands on the final day. The
        # asterisk marks a meeting with projection materials; not a date.
        nums = re.findall(r"\d{1,2}", days_raw)
        if not nums:
            continue
        day = int(nums[-1])
        # A range that crosses a month end ("30-1") ends in the next month.
        month_used, year_used = month, year
        if len(nums) > 1 and int(nums[-1]) < int(nums[0]):
            month_used = 1 if month == 12 else month + 1
            if month == 12:
                year_used = year + 1
        try:
            # The statement comes at 2pm Eastern on the final day.
            when = datetime(year_used, month_used, day, 14, 0, tzinfo=ET)
        except ValueError:
            continue
        key = when.date().isoformat()
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "title": "FOMC statement and rate decision",
            "short": "FOMC",
            "at": when.isoformat(),
            "all_day": False,
            "agency": "Federal Reserve",
            "agency_short": "Fed",
            "source_url": FOMC_URL,
            "confidence": "published",
            "importance": 10,
            "note": "Two-day meetings are shown on the day the statement lands.",
        })
    return {"events": rows, "error": None if rows else "no dates parsed",
            "stale": bool(result.get("stale"))}


def _cot_events(now: datetime) -> Dict[str, Any]:
    """Derive upcoming COT postings from the weekly rule.

    Not fetched — computed. The CFTC publishes Commitments of Traders each Friday
    at 15:30 ET reflecting positions held the previous Tuesday, and exposes no
    machine-readable schedule to check that against. Marked `recurring` so the UI
    can say the date is a rule rather than a confirmation; a federal holiday
    shifts the real posting and nothing here would know.
    """
    rows: List[Dict[str, Any]] = []
    # Next Friday, including today if it's Friday before the posting time.
    ahead = (4 - now.weekday()) % 7
    first = (now + timedelta(days=ahead)).replace(hour=15, minute=30, second=0,
                                                 microsecond=0)
    if first < now:
        first += timedelta(days=7)
    for week in range(3):
        when = first + timedelta(days=7 * week)
        as_of = when - timedelta(days=3)          # the Tuesday it reflects
        rows.append({
            "title": "CFTC Commitments of Traders",
            "short": "COT",
            "at": when.isoformat(),
            "all_day": False,
            "agency": "Commodity Futures Trading Commission",
            "agency_short": "CFTC",
            "source_url": COT_URL,
            "confidence": "recurring",
            "importance": 6,
            "note": f"Weekly schedule. Positions as of {as_of:%b %-d}. "
                    "A federal holiday can shift the posting.",
        })
    return {"events": rows, "error": None, "stale": False}


# Per-series BLS release feeds, so an upcoming print can show what the last one
# actually said. The BLS writes the figure into its own headline — "CPI for all
# items increases 0.1% in July" — which means the previous reading is available
# as primary source text rather than as a number somebody transcribed.
#
# There is no forecast column here and there will not be one from this source.
# Consensus estimates are a surveyed, licensed product; every free copy of them
# is somebody else's paid feed republished, usually without a date. A column
# headed "forecast" that is silently a week stale is worse than no column, so the
# panel says the number is not available instead of guessing at it.
PREV_FEEDS = {
    "consumer price index": "https://www.bls.gov/feed/cpi.rss",
    "producer price index": "https://www.bls.gov/feed/ppi.rss",
    "employment situation": "https://www.bls.gov/feed/empsit.rss",
}

# A previous print older than this is not the previous print — the series either
# changed schedule or the feed stopped updating.
PREV_MAX_AGE_DAYS = 75


def _last_release(summary: str, force: bool = False) -> Optional[Dict[str, Any]]:
    """What the most recent print of this series said, in the agency's words."""
    low = (summary or "").lower()
    url = next((u for needle, u in PREV_FEEDS.items() if needle in low), None)
    if not url:
        return None

    try:
        leg = feeds.load_source(
            {"id": "prev:" + url, "name": "Bureau of Labor Statistics",
             "detail": "Previous release", "kind": "macro", "sector": "economy",
             "weight": 5, "url": url},
            force=force)
    except Exception:
        return None

    entries = [e for e in (leg.get("entries") or []) if e.get("title")]
    if not entries:
        return None

    newest = entries[0]
    published = newest.get("published")
    age = None
    if published:
        try:
            when = datetime.fromisoformat(published)
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - when).days
        except (ValueError, TypeError):
            age = None
    if age is not None and age > PREV_MAX_AGE_DAYS:
        return None

    return {
        "headline": newest["title"],
        "url": newest.get("url"),
        "published": published,
        "age_days": age,
    }


def _expiry_events(now: datetime) -> Dict[str, Any]:
    """Options expiry dates, from the calendar rule rather than a feed.

    These belong on the same calendar as the macro releases because they move
    the tape in the same way a scheduled print does — a known date with known
    mechanics — even though no agency publishes them.
    """
    try:
        from .analytics import expiries as expiries_mod
        rows = expiries_mod.upcoming(now, months=3)
    except Exception as exc:                     # noqa: BLE001
        return {"events": [], "error": str(exc)[:120], "stale": False}

    out = []
    for row in rows:
        try:
            when = datetime.fromisoformat(row["date"] + "T16:00:00").replace(tzinfo=ET)
            if row["kind"] == "vix":
                when = when.replace(hour=9, minute=30)
        except (ValueError, TypeError):
            continue
        out.append({
            "title": row["title"],
            "short": row["short"],
            "at": when.isoformat(),
            "all_day": False,
            "agency": "Options exchanges",
            "agency_short": "OPEX" if row["kind"] != "vix" else "CBOE",
            "source_url": "https://www.cboe.com/us/options/market_statistics/",
            # Derived from a fixed rule, exactly like the CFTC weekly posting —
            # correct unless a market holiday moves it, which the rule cannot see.
            "confidence": "recurring",
            "importance": 9 if row["kind"] == "witching" else 6,
            "why_override": row["why"],
        })
    return {"events": out, "error": None, "stale": False}


# Categories for the calendar's filter pills. Matched on the release title, and
# a release can only be in one — a filter where everything matches everything is
# not a filter.
CATEGORY_RULES = [
    ("inflation", ("consumer price", "producer price", "import and export price",
                   "pce", "inflation")),
    ("fed", ("fomc", "federal open market", "federal reserve", "beige book")),
    ("jobs", ("employment situation", "job openings", "employment cost",
              "unemployment", "jobless", "payroll", "labor force", "displacement",
              "employment projections", "employment statistics", "youth labor")),
    ("growth", ("gross domestic product", "gdp", "retail sales",
                "industrial production", "productivity", "durable goods")),
    ("housing", ("mortgage", "housing", "home sales", "building permits")),
    ("energy", ("petroleum", "natural gas", "crude", "energy")),
    ("positioning", ("commitments of traders", "options expiry", "witching",
                     "vix futures")),
]


def _category(title: str) -> str:
    low = (title or "").lower()
    for name, needles in CATEGORY_RULES:
        if any(n in low for n in needles):
            return name
    return "other"


def _readings(title: str, days_away: Optional[int]) -> Dict[str, Any]:
    """The last published figure for this release, from FRED.

    For a release that has ALREADY happened this is its actual. For one still
    scheduled it is the previous reading — the number the next print will be
    compared against. Those are different claims, so the field is named for which
    one it is rather than always calling it "actual" and letting the reader
    assume a future event has already reported.
    """
    try:
        from . import fred
        block = fred.for_release(title)
    except Exception as exc:                     # noqa: BLE001
        log.warning("calendar: FRED lookup failed for %r: %s", title, exc)
        return {"available": False}
    if not block.get("available"):
        return {"available": False}

    upcoming = days_away is not None and days_away > 0
    return {
        "available": True,
        "series": block["series"],
        "series_label": block["label"],
        "unit": block["unit"],
        "as_of": block["as_of"],
        # An upcoming release has not printed; its "actual" is next week's news.
        "actual": None if upcoming else block["actual"],
        "previous": block["actual"] if upcoming else block["previous"],
        "is_upcoming": upcoming,
        "forecast": None,
        "forecast_note": block["forecast_note"],
    }


def upcoming(force: bool = False, now: Optional[datetime] = None) -> Dict[str, Any]:
    """The calendar section: what's scheduled between now and the horizon."""
    now = now or datetime.now(ET)
    horizon = now + timedelta(days=HORIZON_DAYS)

    legs = {
        "bls": _bls_events(force=force),
        "fomc": _fomc_events(force=force),
        "cot": _cot_events(now),
        "expiry": _expiry_events(now),
    }

    events: List[Dict[str, Any]] = []
    for leg in legs.values():
        for row in leg["events"]:
            try:
                when = datetime.fromisoformat(row["at"])
            except (ValueError, TypeError):
                continue
            if now <= when <= horizon:
                events.append(row)

    # Chronological, with the bigger release first on a shared slot — CPI and
    # Real Earnings both print at 08:30 on the same morning.
    events.sort(key=lambda r: (r["at"], -r.get("importance", 0)))

    today = now.date()
    for row in events:
        when = datetime.fromisoformat(row["at"])
        days = (when.date() - today).days
        row["days_away"] = days
        row["when_label"] = ("Today" if days == 0 else
                             "Tomorrow" if days == 1 else
                             when.strftime("%a %b %-d"))
        row["time_label"] = "" if row.get("all_day") else when.strftime("%-I:%M %p ET")
        row["impact"] = _impact(int(row.get("importance") or 3))
        row["impact_note"] = IMPACT_BANDS[row["impact"]]
        row["why"] = row.pop("why_override", None) or _why(
            row.get("title") or "", row.get("agency_short") or "")
        row["category"] = _category(row.get("title") or "")
        # Only for the releases a reader would actually compare numbers on, so a
        # twenty-row calendar does not fire twenty FRED fetches.
        row["readings"] = (_readings(row.get("title") or "", row.get("days_away"))
                           if row["impact"] in ("high", "medium") else {"available": False})
        # Only for the releases a reader would actually compare against, so a
        # calendar of twenty rows does not fire twenty feed fetches.
        row["previous"] = (_last_release(row.get("title") or "", force=force)
                           if row.get("impact") == "high" else None)

    status = [{"id": key, "error": leg.get("error"), "stale": leg.get("stale"),
               "count": len(leg["events"])} for key, leg in legs.items()]

    return {
        "events": events[:LIMIT],
        "total": len(events),
        "horizon_days": HORIZON_DAYS,
        "sources": status,
        "degraded": [s["id"] for s in status if s.get("error")],
    }
