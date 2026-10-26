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

from . import earnings_result as result_mod
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


# How far before a release its FRED observation may sit and still be the
# figure that release printed. A monthly series covers the month before (CPI,
# PPI) or two before (job openings, 67 days); a quarterly one, the quarter
# before. Older means FRED has not loaded the new print yet, and its newest
# figure is last period's: shown as the new result, it would be wrong.
FRED_FRESH_DAYS = {"monthly": 70, "quarterly": 150}
QUARTERLY_SERIES = {"GDPC1", "ECIALLCIV", "OPHNFB"}
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]


def _period_words(as_of: str, series: str) -> str:
    try:
        d = datetime.fromisoformat(str(as_of)[:10])
    except ValueError:
        return str(as_of)
    if series in QUARTERLY_SERIES:
        return "Q{} {}".format((d.month - 1) // 3 + 1, d.year)
    return "{} {}".format(MONTHS[d.month - 1], d.year)


def _signed(v: Any, unit: str) -> str:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return "n/a"
    if unit == "k":
        return "{:+,.0f}k".format(x)
    if unit == "m":
        return "{:.2f}m".format(x)
    return "{:+.1f}%".format(x)


def _event_result(e: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """What a release that is already out printed, from FRED's figure and the
    agency's own headline, when either is in hand and is this release's.

    Asked for on 2026-10-15 with a screenshot of the Today band: "PPI Out" sat
    over a paragraph explaining what the producer price index is. The figures
    were already fetched for each release (`readings`, `previous`) and dropped
    on the way to the page."""
    if not e.get("released"):
        return None
    try:
        at = datetime.fromisoformat(e["at"])
    except (KeyError, TypeError, ValueError):
        return None
    out: Dict[str, Any] = {}
    rd = e.get("readings") or {}
    if rd.get("available") and rd.get("actual") is not None and rd.get("as_of"):
        try:
            obs = datetime.fromisoformat(str(rd["as_of"])[:10]).date()
        except ValueError:
            obs = None
        kind = "quarterly" if rd.get("series") in QUARTERLY_SERIES else "monthly"
        if obs is not None and (at.date() - obs).days <= FRED_FRESH_DAYS[kind]:
            unit = rd.get("unit") or ""
            out.update({
                "short": _signed(rd["actual"], unit),
                "label": rd.get("series_label"), "actual": rd["actual"], "previous": rd.get("previous"),
                "unit": unit, "period": _period_words(rd["as_of"], rd.get("series") or ""),
                "source": "FRED ({})".format(rd.get("series")),
                "text": "{} {} for {}, after {} the month before.".format(
                    rd.get("series_label") or "The reading", _signed(rd["actual"], unit),
                    _period_words(rd["as_of"], rd.get("series") or ""), _signed(rd.get("previous"), unit))
                if kind == "monthly" else "{} {} for {}, after {} the quarter before.".format(
                    rd.get("series_label") or "The reading", _signed(rd["actual"], unit),
                    _period_words(rd["as_of"], rd.get("series") or ""), _signed(rd.get("previous"), unit)),
            })
        else:
            out["fred_pending"] = ("FRED still shows {} as its newest figure, so the new print has not reached "
                                   "it yet.".format(_period_words(rd["as_of"], rd.get("series") or "")))
    prev = e.get("previous") or {}
    if prev.get("headline") and prev.get("published"):
        try:
            pub = datetime.fromisoformat(prev["published"])
            if pub.tzinfo is None:
                pub = pub.replace(tzinfo=timezone.utc)
            same_day = pub.astimezone(at.tzinfo).date() == at.date() if at.tzinfo else False
        except (TypeError, ValueError):
            same_day = False
        if same_day:
            out["headline"] = prev["headline"]
            out["headline_url"] = prev.get("url")
            out["headline_source"] = e.get("agency_short") or "the agency"
    if not out.get("text") and not out.get("headline"):
        # Minutes, auctions and expiries print no figure Optic reads, so there
        # is nothing to be waiting for: "Out" says it all.
        if not _prints_figures(e.get("title") or ""):
            return None
        out["pending"] = True
        out["text"] = ("Released{}; the figures have not reached Optic's feeds yet.".format(
            " at " + e["time_label"] if e.get("time_label") else ""))
    if out.get("actual") is not None:
        out["forecast_note"] = rd.get("forecast_note") or (
            "Consensus forecasts are licensed data, so the result is shown against the previous "
            "print, not against expectations.")
    return out


def _prints_figures(title: str) -> bool:
    """Whether a release is one Optic has a FRED series for."""
    try:
        from . import fred
    except Exception:                                                      # noqa: BLE001
        return False
    low = title.lower()
    return any(k in low for k in fred.SERIES_MAP)


def _events(now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Scheduled releases and expiries inside the horizon."""
    try:
        cal = events_mod.upcoming(now=now, earlier_today=True)
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
            # Out already, and said so, rather than a time that has passed
            # reading as one still to come.
            "time": ("Out at " + e["time_label"]) if e.get("released") and e.get("time_label")
            else e.get("time_label"),
            "released": bool(e.get("released")),
            "days_away": days,
            "date": _et_date(e.get("at")),
            "why": e.get("why"),
            "agency": e.get("agency_short"),
            "result": _event_result(e),
        })
    # Impact band first, then soonest. Both published facts, no judgement.
    rows.sort(key=lambda r: (IMPACT_RANK.get(r["impact"], 3), r["days_away"]))
    return rows[:MAX_PER_COLUMN]


def _earnings_result(provider, symbol: str, day: Optional[str], now: Optional[datetime],
                     cal: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Reported EPS against the estimate for a report already out this week,
    from the same surprise table the Earnings tab reads, with the deeper read
    (revenue, growth, the record, the reaction) app/earnings_result.py adds."""
    today = (now or datetime.now(timezone.utc)).astimezone(session_mod.ET).date().isoformat()
    if not day or day > today:
        return None
    try:
        # ten, for the eight-report record and the same quarter a year before
        rows = provider.earnings_history(symbol, limit=10) or []
    except Exception:                                                      # noqa: BLE001
        return None
    row = next((r for r in rows if str(r.get("date")) == day), None)
    if not row or row.get("eps_reported") is None:
        # Today with no figures may simply be an after-close report still to
        # come, so it stays "reports"; an earlier day is out, and says so.
        if day == today:
            return None
        return {"pending": True, "text": "Reported; the figures have not reached Optic's feed yet."}
    est = row.get("eps_estimate")
    eps = row["eps_reported"]
    sur = row.get("surprise_pct")
    if sur is None and est:
        sur = (eps - est) / abs(est) * 100.0
    verdict = ("in line" if sur is not None and abs(sur) <= 1.0 else "beat" if (sur or 0) > 0 else "missed")
    out = {"short": {"beat": "Beat", "missed": "Missed", "in line": "In line"}[verdict],
           "eps": eps, "estimate": est, "surprise_pct": round(sur, 1) if sur is not None else None,
           "verdict": verdict, "source": "Yahoo Finance surprise table (adjusted EPS)",
           "text": "EPS {:.2f} against {} expected: {}{}.".format(
               eps, "{:.2f}".format(est) if est is not None else "no estimate",
               verdict, " by {:.1f}%".format(abs(sur)) if sur is not None and verdict != "in line" else "")}
    cal = cal or {}
    out["session"] = result_mod.released_session(row, cal, day)
    try:
        out["detail"] = result_mod.build(provider, symbol, day, row, rows, cal, out["session"], now)
    except Exception as exc:                                               # noqa: BLE001
        log.warning("priority: result detail for %s failed: %s", symbol, exc)
        out["detail"] = None
    combined = (out["detail"] or {}).get("combined")
    if combined:
        # The cell's word says both when both are known; "Beat" alone is EPS's.
        out["short"] = {"double beat": "Double beat", "double miss": "Double miss", "mixed": "Mixed"}[combined["kind"]]
    return out


def _session_words(side: Optional[str], done: bool) -> str:
    """After the day in a report's title: "FCX reports Tuesday before the open"."""
    if side == "before_open":
        return " before the open"
    if side == "after_close":
        return " after the close"
    return ", time not known" if done else ", time not set"


def _earnings(provider, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Widely followed names (weekly.WATCHLIST) reporting this week, soonest first."""
    try:
        block = weekly_mod.earnings_this_week(provider, now)
    except Exception as exc:
        log.warning("priority: earnings scan unavailable: %s", exc)
        return []
    today = (now or datetime.now(timezone.utc)).astimezone(session_mod.ET).date()
    rows = []
    for day in block.get("days", []):
        try:
            days_away = (datetime.fromisoformat(day.get("date") or "").date() - today).days
        except ValueError:
            days_away = None
        for symbol in day.get("symbols", []):
            try:
                cal = provider.earnings_calendar(symbol) or {}
            except Exception:                                              # noqa: BLE001
                cal = {}
            result = _earnings_result(provider, symbol, day.get("date"), now, cal)
            done = bool(result) and not result.get("pending")
            if done:
                side = result.get("session")
            elif result:
                # out, figures late: the quote's time for that day, as for a released report
                side = result_mod.released_session(None, cal, day.get("date") or "")
            else:
                side = result_mod.scheduled_session(cal, day.get("date") or "")
                # Yahoo's consensus for this report, kept before it lands: once
                # it is out Yahoo shows the next quarter's.
                try:
                    result_mod.record_consensus(symbol, day.get("date") or "", cal, side, now)
                except Exception as exc:                                   # noqa: BLE001
                    log.warning("priority: could not record %s's consensus: %s", symbol, exc)
            rows.append({
                "kind": "earnings",
                # High for a report that moves the index, medium for the rest.
                # Every report was "high", so on a day with two slots on Home's
                # week strip any name in the scan outranked a medium-impact
                # release, and a mid-cap's report took CPI's place.
                "impact": "high" if symbol in MAJORS else "medium",
                "ticker": symbol,
                # Past tense once the figures are in: "GS reports Tuesday" on a
                # Thursday read as a report still to come.
                "title": "{} {} {}{}".format(symbol, "reported" if done else "reports", day["day"],
                                             _session_words(side, done)),
                "when": day["day"],
                # Before the open or after the close, or None when no source
                # Optic trusts says (app/earnings_result.py). `time` is the
                # strip cell's short form, and absent rather than a guess.
                "session": side,
                "session_label": result_mod.LABEL.get(side) if side else None,
                "time": result_mod.SHORT.get(side) if side else None,
                "date": day.get("date"),
                # Negative for a report earlier this week, as the calendar's
                # rows count it, so a page can tell what is out from what is
                # still to come without its own clock.
                "days_away": days_away,
                "result": result,
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


# How Home's earnings rows are timed and read; shown in the board's method note.
EARNINGS_METHOD = (
    "Before the open or after the close comes from Yahoo's quote for a date Yahoo has confirmed, "
    "used only when the report's time falls outside the session and the call's time agrees; for a "
    "report that is out, from the time Yahoo's surprise table stamps on it. Where neither says, the "
    "report reads \"time not set\" rather than taking the company's habit as this quarter's time. "
    "A result is EPS against its estimate from Yahoo's surprise table (adjusted EPS). Revenue comes "
    "from Yahoo's quarterly statement or the SEC filing, which arrive a day to a few weeks after the "
    "press release, and its estimate is the Yahoo consensus Optic "
    "recorded before the report, because Yahoo replaces it with the next quarter's once a company "
    "reports. For both, within 1% either way is in line, and a double beat needs both above. Growth "
    "compares the same quarter a year earlier. The reaction is the session that "
    "traded the report: that day's for a report before the open, the next one's after the close."
)


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
        "earnings_method": EARNINGS_METHOD,
    }
