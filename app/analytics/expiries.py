"""Option expiry dates that move markets: equity opex, triple witching, VIX.

Three separate schedules that people routinely conflate, which is the reason to
compute them rather than eyeball them:

  monthly opex     Third Friday of every month. Standard equity and index
                   options settle, and the dealer gamma tied to those strikes
                   stops existing.
  triple witching  The third Friday of March, June, September and December,
                   when index futures, index options and single-stock options
                   all expire together. Volume is several times a normal opex.
  VIX expiry       The Wednesday **30 days before the third Friday of the
                   following month**. This is the one people get wrong: it is
                   not the same week as equity opex, and VIX settles on a
                   Wednesday morning auction rather than a Friday close.

All three are deterministic rules, so this needs no data feed and cannot go
stale. What it cannot know is holidays: when the third Friday is a market
holiday, equity opex moves to the Thursday. That is rare, and the output says so
rather than silently being a day wrong.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

# Months where all three product families expire together.
WITCHING_MONTHS = (3, 6, 9, 12)

# VIX settles this many days before the following month's third Friday.
VIX_OFFSET_DAYS = 30


def third_friday(year: int, month: int) -> date:
    """The third Friday of a given month."""
    d = date(year, month, 1)
    # weekday(): Monday is 0, Friday is 4.
    first_friday = d + timedelta(days=(4 - d.weekday()) % 7)
    return first_friday + timedelta(days=14)


def vix_expiry(year: int, month: int) -> date:
    """VIX settlement for a contract month: 30 days before the NEXT month's third Friday.

    Returns a Wednesday for every valid month, which is the rule's own
    self-check — the third Friday of any month minus 30 days always lands on a
    Wednesday, and a result that does not is a bug in this function.
    """
    nxt_year, nxt_month = (year + 1, 1) if month == 12 else (year, month + 1)
    return third_friday(nxt_year, nxt_month) - timedelta(days=VIX_OFFSET_DAYS)


def _months_ahead(start: date, count: int):
    y, m = start.year, start.month
    for _ in range(count):
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def upcoming(now: Optional[datetime] = None, months: int = 4) -> List[Dict[str, Any]]:
    """Every expiry event in the next few months, soonest first."""
    today = (now or datetime.now(ET)).date()
    out: List[Dict[str, Any]] = []

    for year, month in _months_ahead(today, months + 1):
        friday = third_friday(year, month)
        if friday >= today:
            witching = month in WITCHING_MONTHS
            out.append({
                "date": friday.isoformat(),
                "kind": "witching" if witching else "opex",
                "title": ("Quadruple witching" if witching else "Monthly options expiry"),
                "short": "Witching" if witching else "Opex",
                "time_label": "4:00 PM ET",
                "impact": "high" if witching else "medium",
                "why": (
                    "Index futures, index options, single-stock options and "
                    "single-stock futures all expire together. Volume runs several "
                    "times a normal session and the dealer gamma pinned to those "
                    "strikes disappears at the close, which is why the following "
                    "Monday often trades differently from the Friday."
                    if witching else
                    "Standard equity and index options expire. The dealer hedging "
                    "tied to those strikes stops existing at the close, so levels "
                    "that have been acting like a magnet or a ceiling all month "
                    "simply stop doing so."
                ),
            })

        vix = vix_expiry(year, month)
        if vix >= today:
            out.append({
                "date": vix.isoformat(),
                "kind": "vix",
                "title": "VIX futures and options settlement",
                "short": "VIX expiry",
                "time_label": "9:30 AM ET (opening auction)",
                "impact": "medium",
                "why": (
                    "VIX settles against a special opening auction of SPX options, "
                    "not against a close, and it lands on a Wednesday rather than "
                    "with equity opex. A distinction routinely missed. Hedges "
                    "rolled around this date can move implied volatility without "
                    "the index itself doing much."
                ),
            })

    out.sort(key=lambda e: e["date"])
    for e in out:
        d = date.fromisoformat(e["date"])
        e["days_away"] = (d - today).days
        e["when_label"] = ("Today" if d == today else
                           "Tomorrow" if (d - today).days == 1 else
                           d.strftime("%a %b %-d"))
        e["confidence"] = "rule"
    return out


def context(now: Optional[datetime] = None) -> Dict[str, Any]:
    """How close the next opex is — the number a gamma reading is read against."""
    events = upcoming(now, months=2)
    opex = next((e for e in events if e["kind"] in ("opex", "witching")), None)
    vix = next((e for e in events if e["kind"] == "vix"), None)
    if not opex:
        return {"available": False}
    days = opex["days_away"]
    if days <= 2:
        note = ("Expiry week. Dealer gamma tied to this month's strikes is at its "
                "largest and about to vanish, so pinning near big strikes is most "
                "likely now and least likely next week.")
    elif days <= 7:
        note = ("Opex is inside a week. Charm. The delta that decays with time "
                "alone. Builds fastest here, which is where the drift into an "
                "expiry Friday comes from.")
    else:
        note = ("Opex is still {} days out, so expiry mechanics are not yet the "
                "dominant force in dealer hedging.".format(days))
    return {
        "available": True,
        "next_opex": opex,
        "next_vix_expiry": vix,
        "days_to_opex": days,
        "is_expiry_week": days <= 4,
        "note": note,
        "method": (
            "Computed from the calendar rule, not a feed: monthly expiry is the "
            "third Friday, quadruple witching is the third Friday of March, June, "
            "September and December, and VIX settles on the Wednesday 30 days "
            "before the following month's third Friday. When a third Friday falls "
            "on a market holiday the equity expiry moves to the Thursday, which "
            "this rule does not model."
        ),
    }
