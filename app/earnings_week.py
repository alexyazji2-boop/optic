"""The earnings week: who reports, when, and what the street expects.

The Earnings tab was inert without a ticker — it said "no ticker loaded" and
stopped. That is a waste of the one question a reader has before they have picked
a name: *who is reporting this week?* This answers it, and every ticker on it is
clickable straight into the full analysis.

**Grouped by day, not by session.** The reference terminals split each day into
"before open" and "after close". yfinance publishes an earnings DATE and no
session tag, so that column would be invented — and a name filed under the wrong
session is worse than one filed under neither. The panel says why the split is
absent rather than guessing at it.

**Consensus EPS here is real, unlike on the economic calendar.** That distinction
is worth being precise about: analyst estimates for a *company* come through the
provider, while consensus for a *macro release* is a surveyed, licensed product
this terminal has no access to. So an earnings row can show what the street
expects and a CPI row cannot.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from .weekly import WATCHLIST

ET = ZoneInfo("America/New_York")
log = logging.getLogger(__name__)

# Names whose report moves the index rather than just their own sector. Flagged
# so a week with forty reports still shows which three matter.
MAJORS = {
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AVGO", "JPM",
    "WMT", "UNH", "LLY", "XOM", "HD", "COST", "ORCL", "NFLX", "AMD", "CRM",
    "TSM", "V", "MA", "BAC",
}

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]


def _num(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if out != out else out


def week_bounds(offset: int = 0, now: Optional[datetime] = None):
    """Monday-to-Friday of the current week, or `offset` weeks either side."""
    when = (now or datetime.now(timezone.utc)).astimezone(ET)
    monday = (when - timedelta(days=when.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0)
    monday += timedelta(weeks=offset)
    return monday, monday + timedelta(days=5)


def _domain(website: Optional[str]) -> Optional[str]:
    """Bare registrable domain from a company website URL.

    Logo services key on the domain, and the filed website is inconsistent about
    scheme, `www.` and trailing paths — "https://www.nvidia.com/en-us/" has to
    become "nvidia.com" or the lookup misses.
    """
    if not website:
        return None
    host = str(website).strip().lower()
    for prefix in ("https://", "http://"):
        if host.startswith(prefix):
            host = host[len(prefix):]
    host = host.split("/")[0].split("?")[0].strip()
    if host.startswith("www."):
        host = host[4:]
    # A host with no dot is not a domain; better to show a monogram than to ask a
    # logo service for garbage.
    return host if host and "." in host else None


def build(provider, offset: int = 0, now: Optional[datetime] = None,
          watchlist: Optional[List[str]] = None) -> Dict[str, Any]:
    """Watchlist names reporting in one week, grouped by day."""
    start, end = week_bounds(offset, now)
    names = watchlist if watchlist is not None else WATCHLIST
    today = (now or datetime.now(timezone.utc)).astimezone(ET).date()

    by_day: Dict[str, List[Dict[str, Any]]] = {}
    checked = failed = 0
    for symbol in names:
        try:
            raw = provider.earnings_date(symbol)
        except Exception:
            failed += 1
            continue
        checked += 1
        if not raw:
            continue
        try:
            when = datetime.fromisoformat(str(raw)[:10]).replace(tzinfo=ET)
        except (ValueError, TypeError):
            continue
        if not (start <= when < end):
            continue

        row: Dict[str, Any] = {
            "ticker": symbol,
            "date": when.date().isoformat(),
            "major": symbol in MAJORS,
        }
        # Consensus only for the handful actually in the window — this is a second
        # provider call per name and the window is usually small.
        try:
            cal = provider.earnings_calendar(symbol) or {}
            row["eps_consensus"] = _num(cal.get("eps_avg"))
            row["eps_low"] = _num(cal.get("eps_low"))
            row["eps_high"] = _num(cal.get("eps_high"))
            row["revenue_consensus"] = _num(cal.get("revenue_avg"))
            row["confirmed"] = bool(cal.get("confirmed"))
        except Exception:
            pass
        try:
            prof = provider.profile(symbol) or {}
            row["name"] = prof.get("name")
            row["sector"] = prof.get("sector")
            # The bare domain, for the logo. profile() already carried `website`
            # on a day-long cache and this builder simply was not reading it, so
            # the logo costs no extra request.
            row["domain"] = _domain(prof.get("website"))
        except Exception:
            pass

        by_day.setdefault(when.strftime("%A"), []).append(row)

    days = []
    for name in DAY_ORDER:
        rows = sorted(by_day.get(name, []),
                      key=lambda r: (not r["major"], r["ticker"]))
        date = (start + timedelta(days=DAY_ORDER.index(name))).date()
        days.append({
            "day": name,
            "short": name[:3],
            "date": date.isoformat(),
            "day_number": date.day,
            "is_today": date == today,
            "is_past": date < today,
            "count": len(rows),
            "majors": sum(1 for r in rows if r["major"]),
            "rows": rows,
        })

    total = sum(d["count"] for d in days)
    return {
        "available": True,
        "week_of": start.date().isoformat(),
        "week_label": "{} – {}".format(
            start.strftime("%b %-d"), (start + timedelta(days=4)).strftime("%-d")),
        "offset": offset,
        "days": days,
        "total": total,
        "majors": sum(d["majors"] for d in days),
        "checked": checked,
        "failed": failed,
        "universe": len(names),
        "session_note": (
            "Grouped by day rather than by trading session. The provider publishes "
            "an earnings date and no before-open or after-close tag, so a session "
            "column here would be invented — and a name filed under the wrong "
            "session is worse than one filed under neither."
        ),
        "method": (
            "Scanned {} widely-followed names, not the whole market: a complete "
            "earnings calendar is a licensed product and free data gives one date "
            "per symbol at a time. Consensus EPS comes from the provider's analyst "
            "estimates — real for a company, unlike consensus for a macro release, "
            "which is surveyed and licensed and is why the economic calendar has no "
            "forecast column. Dates move: companies reschedule, and an unconfirmed "
            "date is the provider's best guess."
            .format(checked)
        ),
    }
