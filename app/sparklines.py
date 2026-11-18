"""Intraday lines for Home's ticker rows (Pass 2, 2026-11-17), behind one interface so a licensed feed slots in.

What a row draws: the five-minute closes since today's open, red or green by the day's direction (the last close
against the previous session's close, the same figure the row's "Today" shows), with a status saying whether the
line is delayed, live or from a closed market. Outside the session, or for a symbol the intraday source does not
cover, the row falls back to its last 30 daily closes and says so.

The source is chosen by `OPTIC_INTRADAY_SOURCE` from `SOURCES`. Today there is one, the free feed (Yahoo Finance
through app/providers/yf.py, delayed, not licensed for commercial display). A licensed vendor is one more class with
the same two methods and its own `delayed_minutes` and `realtime`, registered in `SOURCES`; nothing above it
changes. One request a refresh for all the rows, cached by the provider; refreshed every five minutes in session.
"""
from __future__ import annotations

import math
import os
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

MAX_SYMBOLS = 30
REFRESH_SECONDS = 300          # every five minutes while the session is open
DAILY_FALLBACK = 30


class IntradaySource:
    """What a source must answer. Bars are regular-session closes since today's open, oldest first."""
    name = "base"
    label = ""
    delayed_minutes = 0
    realtime = False
    licensed = False

    def bars_since_open(self, symbol: str) -> Dict[str, Any]:     # {"times": [...], "closes": [...]}
        raise NotImplementedError

    def daily_closes(self, symbol: str, n: int = DAILY_FALLBACK) -> Dict[str, Any]:   # {"dates": [...], "closes": [...]}
        raise NotImplementedError


def _clean(values: List[Any]) -> List[float]:
    out = []
    for v in values:
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if math.isfinite(f):
            out.append(round(f, 4))
    return out


class FreeFeedSource(IntradaySource):
    """Yahoo Finance's five-minute bars through the app's provider (and its cache). Delayed; personal use only."""
    name = "free"
    label = "Yahoo Finance, delayed"
    licensed = False

    def __init__(self, provider: Any, delayed_minutes: int = 15) -> None:
        self.provider = provider
        self.delayed_minutes = delayed_minutes

    def bars_since_open(self, symbol: str) -> Dict[str, Any]:
        df = self.provider.intraday_history(symbol, period="1d", interval="5m", prepost=False)
        if df is None or getattr(df, "empty", True):
            return {"times": [], "closes": []}
        return {"times": [t.isoformat() for t in df.index], "closes": _clean(list(df["Close"]))}

    def daily_closes(self, symbol: str, n: int = DAILY_FALLBACK) -> Dict[str, Any]:
        df = self.provider.history(symbol, period="3mo", interval="1d")
        if df is None or getattr(df, "empty", True):
            return {"dates": [], "closes": []}
        tail = df.tail(n)
        return {"dates": [str(t)[:10] for t in tail.index], "closes": _clean(list(tail["Close"]))}


SOURCES: Dict[str, Callable[[Any], IntradaySource]] = {"free": lambda provider: FreeFeedSource(provider)}


def source(provider: Any) -> IntradaySource:
    make = SOURCES.get((os.environ.get("OPTIC_INTRADAY_SOURCE") or "free").strip().lower()) or SOURCES["free"]
    return make(provider)


def _direction(last: Optional[float], prev: Optional[float]) -> str:
    if last is None or prev is None:
        return "flat"
    return "up" if last > prev else "down" if last < prev else "flat"


def row(src: IntradaySource, symbol: str, prev_close: Optional[float], in_session: bool) -> Dict[str, Any]:
    """One symbol's line: intraday in session when the source has it, else the last 30 daily closes."""
    try:
        bars = src.bars_since_open(symbol) if in_session else {"times": [], "closes": []}
    except Exception:                                         # noqa: BLE001 - a source refusing is the fallback's case
        bars = {"times": [], "closes": []}
    closes = bars.get("closes") or []
    if len(closes) >= 2:
        last = closes[-1]
        return {"symbol": symbol, "available": True, "kind": "intraday", "times": bars.get("times") or [], "closes": closes,
                "direction": _direction(last, prev_close), "previous_close": prev_close,
                "change_pct": round((last / prev_close - 1) * 100, 2) if prev_close else None}
    try:
        daily = src.daily_closes(symbol, DAILY_FALLBACK)
    except Exception:                                         # noqa: BLE001
        daily = {"dates": [], "closes": []}
    dc = daily.get("closes") or []
    if len(dc) >= 2:
        return {"symbol": symbol, "available": True, "kind": "daily", "dates": daily.get("dates") or [], "closes": dc,
                "direction": _direction(dc[-1], dc[0]),
                "note": "The last {} daily closes: {}".format(
                    len(dc), "the market is closed" if not in_session else "no intraday bars came back for it")}
    return {"symbol": symbol, "available": False, "reason": "No price line came back for it."}


def build(src: IntradaySource, symbols: List[str], session: Dict[str, Any],
          prev_closes: Optional[Dict[str, Optional[float]]] = None) -> Dict[str, Any]:
    """The rows for up to MAX_SYMBOLS symbols, with the one status line the page shows under them."""
    in_session = bool(session.get("is_regular"))
    status = ("live" if src.realtime else "delayed") if in_session else "closed"
    rows = [row(src, s, (prev_closes or {}).get(s), in_session) for s in symbols[:MAX_SYMBOLS]]
    words = {"live": "Live", "delayed": "Delayed {} min".format(src.delayed_minutes),
             "closed": "Market closed: {}".format(session.get("label") or "outside the regular session")}[status]
    return {"as_of": datetime.now(timezone.utc).isoformat(), "status": status, "status_text": words,
            "source": src.label, "source_name": src.name, "licensed": src.licensed,
            "delayed_minutes": src.delayed_minutes, "refresh_seconds": REFRESH_SECONDS if in_session else None,
            "rows": rows}
