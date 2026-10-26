"""The earnings week: who reports, when, and what the street expects.

The Earnings tab was inert without a ticker — it said "no ticker loaded" and
stopped. That is a waste of the one question a reader has before they have picked
a name: *who is reporting this week?* This answers it, and every ticker on it is
clickable straight into the full analysis.

**Grouped by day, with the time where a source Optic trusts gives one.** The
reference terminals split each day into "before open" and "after close".
Yahoo's earnings calendar has a date only; its quote carries the report time,
which app/earnings_result.py takes on a confirmed date and outside market hours
only. Anything else reads "time not set", since a name filed under the wrong
session is worse than one filed under neither.

**A report already out shows its own quarter's estimates.** Once a company
reports, Yahoo moves its consensus to the next quarter while the calendar still
shows the report's date, so the panel showed VZ's Q4 consensus against the Q3
report it had just made (2026-10-26). A released row takes EPS from the
surprise table and revenue from Optic's record kept before the release.

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

from . import earnings_result as result_mod
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


def week_label(start, end) -> str:
    """"Sep 21 – 25" inside one month, "Sep 28 – Oct 2" across two.

    Reported by a user as: it "shows the date as "Sept 28 - 2", it should
    specify Oct". The end took only its day, so a week that crossed a month
    read as ending on the 2nd of the month it began in."""
    if end.month == start.month:
        return "{} – {}".format(start.strftime("%b %-d"), end.strftime("%-d"))
    return "{} – {}".format(start.strftime("%b %-d"), end.strftime("%b %-d"))


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


SESSION_NOTE = (
    "Grouped by day, with each report's time where Optic can trust it: before the "
    "open or after the close comes from the report time in Yahoo's quote, used "
    "only when the company has confirmed the date and the time falls outside "
    "market hours. Unscheduled reports carry a placeholder time inside the "
    "session, so those read \"time not set\" rather than a guess. Once a company "
    "has reported, Yahoo's estimates move to the next quarter, so a reported row "
    "shows the EPS estimate from Yahoo's surprise table for that report and the "
    "revenue estimate only if Optic recorded it before the release."
)

# A confirmed report this many minutes past its session's edge is out even if
# the surprise table has not caught up, and Yahoo's consensus may have moved.
OUT_AFTER = {"before_open": 9 * 60 + 30, "after_close": 16 * 60 + 30}


def _this_report(provider, symbol: str, day: str, cal: Dict[str, Any],
                 now: datetime) -> Dict[str, Any]:
    """Estimates and timing for one row. Still to come: Yahoo's live consensus,
    kept in Optic's record until the cutoff. Out: that report's own estimates
    (earnings_result.released_estimates), never the next quarter's."""
    today = now.date().isoformat()
    hist = None
    if day <= today:
        try:
            rows = provider.earnings_history(symbol, limit=10) or []
        except Exception:                                                  # noqa: BLE001
            rows = []
        hist = next((r for r in rows if str(r.get("date")) == day
                     and r.get("eps_reported") is not None), None)
    side = result_mod.scheduled_session(cal, day)
    released = day < today or hist is not None or (
        day == today and side in OUT_AFTER and now.hour * 60 + now.minute >= OUT_AFTER[side])
    if released:
        side = result_mod.released_session(hist, cal, day)
        est = result_mod.released_estimates(symbol, day, hist)
        out: Dict[str, Any] = {
            "reported": True,
            "eps_consensus": est["eps"],
            "eps_consensus_source": est["eps_source"],
            # the range is Yahoo's live one, so it belongs to the next quarter now
            "eps_low": None, "eps_high": None,
            "revenue_consensus": est["revenue"],
            "estimate_note": est["note"],
        }
        if hist is not None:
            out["eps_reported"] = _num(hist.get("eps_reported"))
            sur = _num(hist.get("surprise_pct"))
            out["surprise_pct"] = round(sur, 1) if sur is not None else None
            # the same 1% in-line rule as Home's result cell
            out["result_short"] = (None if sur is None else "In line" if abs(sur) <= result_mod.IN_LINE_PCT
                                   else "Beat" if sur > 0 else "Missed")
    else:
        out = {
            "reported": False,
            "eps_consensus": _num(cal.get("eps_avg")),
            "eps_consensus_source": "consensus" if cal.get("eps_avg") is not None else None,
            "eps_low": _num(cal.get("eps_low")),
            "eps_high": _num(cal.get("eps_high")),
            "revenue_consensus": _num(cal.get("revenue_avg")),
            "estimate_note": None,
        }
        try:
            result_mod.record_consensus(symbol, day, cal, side, now)
        except Exception as exc:                                           # noqa: BLE001
            log.warning("earnings week: could not record %s's consensus: %s", symbol, exc)
    out.update(session=side, session_label=result_mod.LABEL.get(side) if side else None,
               time=result_mod.SHORT.get(side) if side else None)
    return out


def build(provider, offset: int = 0, now: Optional[datetime] = None,
          watchlist: Optional[List[str]] = None) -> Dict[str, Any]:
    """Watchlist names reporting in one week, grouped by day."""
    start, end = week_bounds(offset, now)
    names = watchlist if watchlist is not None else WATCHLIST
    when_now = (now or datetime.now(timezone.utc)).astimezone(ET)
    today = when_now.date()

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
            row["confirmed"] = bool(cal.get("confirmed"))
        except Exception:
            cal = {}
        row.update(_this_report(provider, symbol, row["date"], cal, when_now))
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
        "week_label": week_label(start, start + timedelta(days=4)),
        "offset": offset,
        "days": days,
        "total": total,
        "majors": sum(d["majors"] for d in days),
        "checked": checked,
        "failed": failed,
        "universe": len(names),
        "session_note": SESSION_NOTE,
        "method": (
            "Scanned {} widely-followed names, not the whole market: a complete "
            "earnings calendar is a licensed product and free data gives one date "
            "per symbol at a time. Consensus EPS comes from the provider's analyst "
            "estimates. Real for a company, unlike consensus for a macro release, "
            "which is surveyed and licensed and is why the economic calendar has no "
            "forecast column. Dates move: companies reschedule, and an unconfirmed "
            "date is the provider's best guess."
            .format(checked)
        ),
    }
