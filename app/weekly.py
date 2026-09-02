"""The weekly market update: what happened, what's next, and where SPY stands.

A different piece of writing from the morning note. The morning note is two
minutes before the open and is about today; this is the Sunday-evening read that
frames a week — what the data said, what is due, who reports, and the one level
on the index that decides whether the current move continues.

Assembled here, written by the model in ai.write_weekly_update(). The split
matters: everything in this module is a fact with a source — a release that was
published, a date on an agency calendar, an earnings date from the provider, a
level computed from bars. The model's job is to connect them, never to supply
them.

**Earnings are scanned across a watchlist, not the whole market.** A complete
earnings calendar is a licensed product; what free data gives is one date per
symbol, one call at a time. So this checks a few hundred widely-followed names
and says that is what it did. A reader who sees six names on Tuesday should know
that means six *of these*, not six in the market.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from . import events, feeds
from .analytics.sectors import SECTORS, THEMES

ET = ZoneInfo("America/New_York")
log = logging.getLogger(__name__)

# Widely-followed names, checked for an earnings date each week. Not an index —
# a watchlist, chosen for how much a report moves the tape or the conversation.
# Mega-caps, the semiconductor complex, the AI infrastructure names, the big
# banks, and the consumer bellwethers people actually watch.
WATCHLIST: List[str] = [
    # Mega-cap tech
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AVGO", "ORCL", "CRM",
    "ADBE", "NFLX", "AMD", "INTC", "QCOM", "TXN", "MU", "AMAT", "LRCX", "KLAC",
    "ARM", "SMCI", "DELL", "HPQ", "IBM", "CSCO", "ANET", "PANW", "CRWD", "SNOW",
    "MDB", "DDOG", "NOW", "INTU", "SHOP", "UBER", "ABNB", "COIN", "PLTR", "APP",
    "MRVL", "ON", "NXPI", "ASML", "TSM", "CRWV", "NBIS", "VRT", "MSTR",
    # Financials
    "JPM", "BAC", "WFC", "GS", "MS", "C", "SCHW", "BLK", "AXP", "V", "MA", "PYPL",
    "COF", "USB", "PNC", "BX", "KKR",
    # Health care
    "UNH", "JNJ", "LLY", "PFE", "MRK", "ABBV", "TMO", "ABT", "AMGN", "GILD",
    "BMY", "CVS", "ISRG", "VRTX", "REGN", "HIMS",
    # Consumer and industrial
    "WMT", "COST", "TGT", "HD", "LOW", "NKE", "SBUX", "MCD", "PG", "KO", "PEP",
    "DIS", "CMCSA", "T", "VZ", "BA", "CAT", "DE", "GE", "HON", "UPS", "FDX",
    "LMT", "RTX", "NOC", "F", "GM", "RIVN", "LULU", "CAVA", "CMG", "DKNG",
    # Energy and materials
    "XOM", "CVX", "COP", "SLB", "OXY", "PSX", "MPC", "FCX", "NEM", "LIN",
    # Widely-traded mid-caps that move on results
    "SOFI", "HOOD", "RBLX", "U", "AFRM", "TTD", "ROKU", "SE", "JD", "BABA",
    "NU", "GRAB", "ONON", "CELH", "ELF", "DUOL", "RKLB", "ASTS", "LUNR", "IONQ",
]

# How many sessions of macro releases count as "last week".
LOOKBACK_HOURS = 8 * 24
# How far ahead the "what matters" section looks.
FORWARD_DAYS = 8


def _num(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if out != out or out in (float("inf"), float("-inf")) else out


def week_key(now: Optional[datetime] = None) -> str:
    """ISO year-week, the natural cache key for a weekly piece."""
    when = (now or datetime.now(timezone.utc)).astimezone(ET)
    year, week, _ = when.isocalendar()
    return "{}-W{:02d}".format(year, week)


def _week_bounds(now: Optional[datetime] = None):
    """Monday 00:00 to Friday 23:59 of the week ahead, in ET."""
    when = (now or datetime.now(timezone.utc)).astimezone(ET)
    # Saturday and Sunday look forward to the coming week; a weekday looks at
    # the week it is in, because that is the week the reader is trading.
    start = when - timedelta(days=when.weekday())
    if when.weekday() >= 5:
        start = when + timedelta(days=7 - when.weekday())
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=5)


def earnings_this_week(provider, now: Optional[datetime] = None,
                       watchlist: Optional[List[str]] = None) -> Dict[str, Any]:
    """Which watchlist names report between Monday and Friday, grouped by day."""
    start, end = _week_bounds(now)
    names = watchlist if watchlist is not None else WATCHLIST

    by_day: Dict[str, List[str]] = {}
    checked, failed = 0, 0
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
        if start <= when < end:
            by_day.setdefault(when.strftime("%A"), []).append(symbol)

    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    days = [{"day": d, "symbols": sorted(by_day[d])} for d in order if d in by_day]
    return {
        "week_of": start.date().isoformat(),
        "days": days,
        "total": sum(len(d["symbols"]) for d in days),
        "checked": checked,
        "failed": failed,
        "universe": len(names),
        "note": (
            "Scanned {} widely-followed names, not the whole market — a complete "
            "earnings calendar is a licensed product, and free data gives one date "
            "per symbol at a time. Names outside this watchlist report too."
            .format(checked)
        ),
    }


def index_levels(provider, symbol: str = "SPY") -> Dict[str, Any]:
    """Where the index sits, and the levels a weekly read turns on."""
    try:
        frames = provider.batch_history([symbol], period="1y", interval="1d") or {}
    except Exception as exc:                     # noqa: BLE001
        return {"available": False, "reason": str(exc)[:120]}
    frame = frames.get(symbol)
    if frame is None or frame.empty or len(frame) < 60:
        return {"available": False, "reason": "Not enough history."}

    closes = frame["Close"].dropna()
    last = _num(closes.iloc[-1])
    if last is None:
        return {"available": False, "reason": "No usable close."}

    week = closes.tail(6)
    month = closes.tail(22)
    high52, low52 = _num(closes.tail(252).max()), _num(closes.tail(252).min())

    out: Dict[str, Any] = {
        "available": True,
        "symbol": symbol,
        "price": round(last, 2),
        "week_change_pct": round((last / _num(week.iloc[0]) - 1.0) * 100.0, 2)
        if len(week) > 1 and _num(week.iloc[0]) else None,
        "month_change_pct": round((last / _num(month.iloc[0]) - 1.0) * 100.0, 2)
        if len(month) > 1 and _num(month.iloc[0]) else None,
        "fifty_two_week_high": round(high52, 2) if high52 else None,
        "fifty_two_week_low": round(low52, 2) if low52 else None,
        "at_all_time_high_area": bool(high52 and last >= high52 * 0.995),
        # The prior session's range, the same definition the sector board uses.
        "prior_session_high": round(_num(frame["High"].iloc[-2]) or 0, 2),
        "prior_session_low": round(_num(frame["Low"].iloc[-2]) or 0, 2),
        # Last week's range is the level a weekly piece actually argues about.
        "prior_week_high": round(_num(frame["High"].tail(6).max()) or 0, 2),
        "prior_week_low": round(_num(frame["Low"].tail(6).min()) or 0, 2),
    }
    for window in (20, 50, 200):
        if len(closes) >= window:
            avg = _num(closes.rolling(window).mean().iloc[-1])
            if avg:
                out["sma{}".format(window)] = round(avg, 2)
                out["vs_sma{}_pct".format(window)] = round((last / avg - 1.0) * 100.0, 2)
    return out


def _sector_week(provider) -> Dict[str, Any]:
    """Which sectors and themes led and lagged over the week."""
    universe = SECTORS + THEMES
    try:
        frames = provider.batch_history(
            [e["symbol"] for e in universe], period="3mo", interval="1d") or {}
    except Exception:
        return {}
    rows = []
    for entry in universe:
        frame = frames.get(entry["symbol"])
        if frame is None or frame.empty or len(frame) < 7:
            continue
        closes = frame["Close"].dropna()
        first, last = _num(closes.iloc[-6]), _num(closes.iloc[-1])
        if first and last:
            rows.append({"symbol": entry["symbol"], "name": entry["name"],
                         "week_pct": round((last / first - 1.0) * 100.0, 2)})
    rows.sort(key=lambda r: -r["week_pct"])
    return {"leaders": rows[:5], "laggards": rows[-5:][::-1]} if rows else {}


def gather(provider, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Everything the weekly update is written from."""
    start, end = _week_bounds(now)

    # What actually printed over the past week, from the agencies themselves.
    try:
        # load_kind returns (entries, per-source status), not a dict.
        entries, _status = feeds.load_kind("macro")
        released = feeds.within_hours(entries, LOOKBACK_HOURS)
    except Exception as exc:
        log.warning("weekly: macro feed unavailable: %s", exc)
        released = []

    # What is scheduled next.
    try:
        calendar = events.upcoming()
        upcoming = [e for e in calendar.get("events", [])
                    if (e.get("days_away") or 99) <= FORWARD_DAYS]
    except Exception as exc:
        log.warning("weekly: calendar unavailable: %s", exc)
        upcoming = []

    return {
        "week_of": start.date().isoformat(),
        "week_key": week_key(now),
        "released_last_week": [
            {"title": e.get("title"), "source": e.get("source"),
             "published": e.get("published"), "summary": (e.get("summary") or "")[:400]}
            for e in released[:14]
        ],
        "scheduled_this_week": [
            {"title": e.get("title"), "short": e.get("short"), "when": e.get("when_label"),
             "time": e.get("time_label"), "impact": e.get("impact"),
             "why": e.get("why"), "previous": e.get("previous")}
            for e in upcoming
        ],
        "earnings": earnings_this_week(provider, now),
        "spy": index_levels(provider, "SPY"),
        "qqq": index_levels(provider, "QQQ"),
        "sectors": _sector_week(provider),
    }
