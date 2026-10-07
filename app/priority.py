"""Today's priority board: the four things worth knowing before anything else.

Everything here already exists somewhere in the terminal. The point of the board
is not new data, it is *triage* — the Read tab, the calendar, the scanners and
the sector board each answer their own question well, and none of them says which
of the four you should look at first this morning.

Four columns, each a different kind of "why does this matter today":

  events      Scheduled releases and expiries inside a short window, ranked by
              the calendar's own impact band. Facts about a calendar.
  earnings    Widely followed names reporting imminently. Also a calendar fact.
  sectors     Which sectors changed state overnight, and where money rotated.
              Computed from prices.
  movers      The names the scanners surfaced most strongly today.

**Nothing here is ranked by predicted importance.** A priority board that guessed
which event will matter most would be a forecast wearing an ordering. The rank
is the calendar's published impact band, then how soon it lands — both facts.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from datetime import timedelta

from . import events as events_mod
from . import session as session_mod
from . import weekly as weekly_mod
from .analytics import sector_board
from .earnings_week import MAJORS

log = logging.getLogger(__name__)

# How far ahead the board looks. A priority board covering a month is a calendar;
# this is meant to answer "today and the next few days".
HORIZON_DAYS = 5

# How many rows each column previews, and how many it holds in total.
PREVIEW = 3
MAX_PER_COLUMN = 20

IMPACT_RANK = {"high": 0, "medium": 1, "low": 2}


def _et_date(stamp: Any) -> Optional[str]:
    """The New York calendar date of an ISO timestamp, or None."""
    try:
        when = datetime.fromisoformat(str(stamp))
    except (TypeError, ValueError):
        return None
    if when.tzinfo is not None:
        when = when.astimezone(weekly_mod.ET)
    return when.date().isoformat()


def _events(now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Scheduled releases and expiries inside the horizon."""
    try:
        cal = events_mod.upcoming(now=now)
    except Exception as exc:
        log.warning("priority: calendar unavailable: %s", exc)
        return []
    rows = []
    for e in cal.get("events", []):
        days = e.get("days_away")
        if days is None or days > HORIZON_DAYS:
            continue
        rows.append({
            "kind": "event",
            "impact": e.get("impact") or "low",
            "title": e.get("title"),
            "short": e.get("short"),
            "when": e.get("when_label"),
            "time": e.get("time_label"),
            "days_away": days,
            "date": _et_date(e.get("at")),
            "why": e.get("why"),
            "agency": e.get("agency_short"),
        })
    # Impact band first, then soonest. Both published facts, no judgement.
    rows.sort(key=lambda r: (IMPACT_RANK.get(r["impact"], 3), r["days_away"]))
    return rows[:MAX_PER_COLUMN]


def _earnings(provider, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Widely followed names (weekly.WATCHLIST) reporting this week, soonest first."""
    try:
        block = weekly_mod.earnings_this_week(provider, now)
    except Exception as exc:
        log.warning("priority: earnings scan unavailable: %s", exc)
        return []
    rows = []
    for day in block.get("days", []):
        for symbol in day.get("symbols", []):
            rows.append({
                "kind": "earnings",
                # High for a report that moves the index, medium for the rest.
                # Every report was "high", so on a day with two slots on Home's
                # week strip any name in the scan outranked a medium-impact
                # release, and a mid-cap's report took CPI's place.
                "impact": "high" if symbol in MAJORS else "medium",
                "ticker": symbol,
                "title": "{} reports {}".format(symbol, day["day"]),
                "when": day["day"],
                "date": day.get("date"),
                "why": ("An earnings report resets the estimate the price is built "
                        "on, which is why the option market charges more into it."),
            })
    return rows[:MAX_PER_COLUMN]


def _sectors(provider) -> List[Dict[str, Any]]:
    """Sectors that changed overnight state, or where money is rotating."""
    try:
        board = sector_board.build(provider)
    except Exception as exc:
        log.warning("priority: sector board unavailable: %s", exc)
        return []
    rows = []
    for r in board.get("rows", []):
        if not r.get("available"):
            continue
        rot = (r.get("rotation") or {}).get("state")
        changed = bool(r.get("changed")) and r.get("trend") != "neutral"
        if not changed and rot not in ("in", "out"):
            continue
        # A state change is the more urgent of the two: it happened today.
        rows.append({
            "kind": "sector",
            "impact": "high" if changed else "medium",
            "ticker": r["symbol"],
            "title": "{} · {}".format(r["symbol"], r.get("name")),
            "trend": r.get("trend"),
            "rotation": rot,
            "why": (r.get("summary") or "") + (
                " " + (r.get("rotation") or {}).get("note", "") if rot in ("in", "out") else ""),
        })
    rows.sort(key=lambda r: IMPACT_RANK.get(r["impact"], 3))
    return rows[:MAX_PER_COLUMN]


def _movers(scanners_mod, ranking: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Names the scanners surfaced today, with how many lists they appear on.

    Appearing on several scans at once is the only ranking signal here that is
    not a calendar fact, and it is deliberately a count rather than a score: a
    name on four lists is on four lists, which is a statement about the filters
    rather than a claim about the stock.
    """
    if not ranking:
        return []
    hits: Dict[str, Dict[str, Any]] = {}
    for scan in scanners_mod.SCANS:
        try:
            res = scanners_mod.run(ranking, scan["id"], limit=10)
        except Exception:
            continue
        if not res.get("available"):
            continue
        for row in res.get("rows", []):
            sym = row.get("symbol")
            if not sym:
                continue
            entry = hits.setdefault(sym, {
                "kind": "mover", "ticker": sym, "scans": [],
                "roc20": row.get("roc20"), "score": row.get("score"),
            })
            entry["scans"].append(scan["name"])
    rows = list(hits.values())
    for r in rows:
        n = len(r["scans"])
        r["scan_count"] = n
        r["impact"] = "high" if n >= 3 else "medium" if n == 2 else "low"
        r["title"] = "{} on {} scan{}".format(r["ticker"], n, "" if n == 1 else "s")
        r["why"] = "Appears on: {}.".format(", ".join(r["scans"][:4]))
    rows.sort(key=lambda r: (-r["scan_count"], -abs(r.get("roc20") or 0)))
    return rows[:MAX_PER_COLUMN]


def _closed_days(now: Optional[datetime] = None) -> Dict[str, str]:
    """Weekdays inside the horizon the market does not trade, with the reason.

    Home's week strip leaves weekends out on its own and drew a holiday as an
    ordinary day reading "Nothing tracked"; the client knows weekends only and
    must not learn the exchange calendar (see marketSessionET), so the board
    names the days here."""
    when = (now or datetime.now(timezone.utc)).astimezone(session_mod.ET)
    out: Dict[str, str] = {}
    for k in range(HORIZON_DAYS + 1):
        day = (when + timedelta(days=k)).date()
        if day.weekday() >= 5:
            continue
        name = session_mod.market_holidays(day.year).get(day)
        if name:
            out[day.isoformat()] = name
    return out


def build(provider, scanners_mod, ranking: Dict[str, Any],
          now: Optional[datetime] = None) -> Dict[str, Any]:
    """The four columns, each with a preview and its full list."""
    columns = [
        {"id": "events", "name": "Market-moving events",
         "blurb": "Scheduled releases and expiries in the next {} days.".format(HORIZON_DAYS),
         "rows": _events(now)},
        {"id": "earnings", "name": "Earnings this week",
         "blurb": "Widely followed names reporting, soonest first.",
         "rows": _earnings(provider, now)},
        {"id": "sectors", "name": "Sector read-through",
         "blurb": "Sectors that changed state overnight, or where money is rotating.",
         "rows": _sectors(provider)},
        {"id": "movers", "name": "Scanner names",
         "blurb": "Names surfacing on more than one scan today.",
         "rows": _movers(scanners_mod, ranking)},
    ]
    for c in columns:
        c["total"] = len(c["rows"])
        c["preview"] = c["rows"][:PREVIEW]

    return {
        "available": any(c["total"] for c in columns),
        "columns": columns,
        "horizon_days": HORIZON_DAYS,
        "closed_days": _closed_days(now),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": (
            "Nothing on this board is new data. It is the calendar, the earnings "
            "scan, the sector board and the scanners, triaged into one view. The "
            "ordering is the calendar's own published impact band and then how soon "
            "an event lands, both facts. The scanner column ranks by how many lists "
            "a name appears on, which is a statement about the filters rather than "
            "a claim about the stock. Research context only."
        ),
    }
