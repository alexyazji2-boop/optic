"""Implied-volatility rank and percentile, measured rather than approximated.

The tab showed "IV rank (proxy)": today's at-the-money IV placed inside the
year's range of 20-day REALISED volatility, under the glossary definition of
a true IV rank. Implied vol usually sits above realised (the variance risk
premium: Carr & Wu 2009; Bollerslev, Tauchen & Zhou 2009), so that proxy reads
high most of the time; it is a different quantity, not an approximation.

Two honest sources replace it:

* **Cboe's volatility indices**, where one exists for the symbol: the VIX for
  the S&P 500 (SPY, SPX), VXN for the Nasdaq-100 (QQQ, NDX), RVX for the
  (RVX, the Russell 2000's, is not on Yahoo, so IWM uses Optic's own readings), VXD for the Dow (DIA), GVZ for gold (GLD), OVX for oil
  (USO). Each is a model-free 30-day implied volatility of that index, with a
  daily history on Yahoo, so rank and percentile over the past year are real
  today. It is the index's IV, not the ETF chain's own, and is labelled so.
* **Optic's own daily readings** for every other symbol: the 30-day
  constant-maturity at-the-money IV from the chain, stored once per symbol per
  ET trading day when a chain is read. A rank needs history, so it is shown
  only with the number of days it rests on, and called a full-year rank only
  at 252 of them. Until then there is no rank, and the panel says when there
  will be one.

Definitions (both over the same window):
  rank       = (today - lowest) / (highest - lowest) x 100
  percentile = share of days in the window with a lower reading x 100
"""

from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
FULL_WINDOW = 252
MIN_DAYS_TO_SHOW = 20
_LOCK = threading.Lock()

VOL_INDEX = {
    "SPY": ("^VIX", "Cboe Volatility Index (VIX), the S&P 500's 30-day implied volatility"),
    "SPX": ("^VIX", "Cboe Volatility Index (VIX), the S&P 500's 30-day implied volatility"),
    "^SPX": ("^VIX", "Cboe Volatility Index (VIX), the S&P 500's 30-day implied volatility"),
    "^GSPC": ("^VIX", "Cboe Volatility Index (VIX), the S&P 500's 30-day implied volatility"),
    "VOO": ("^VIX", "Cboe Volatility Index (VIX), the S&P 500's 30-day implied volatility"),
    "QQQ": ("^VXN", "Cboe Nasdaq-100 Volatility Index (VXN)"),
    "^NDX": ("^VXN", "Cboe Nasdaq-100 Volatility Index (VXN)"),
    "DIA": ("^VXD", "Cboe DJIA Volatility Index (VXD)"),
    "GLD": ("^GVZ", "Cboe Gold ETF Volatility Index (GVZ)"),
    "USO": ("^OVX", "Cboe Crude Oil ETF Volatility Index (OVX)"),
}


DB_PATH = os.path.join(os.environ.get("TRACKER_DATA_DIR", "data"), "iv_history.db")


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.execute("CREATE TABLE IF NOT EXISTS iv_daily (symbol TEXT NOT NULL, day TEXT NOT NULL, "
                "iv30 REAL NOT NULL, recorded_at TEXT NOT NULL, PRIMARY KEY (symbol, day))")
    return con


def record(symbol: str, iv30_pct: Optional[float], now: Optional[datetime] = None) -> bool:
    """Store today's reading once (the first good one of the ET day wins).

    Only between 9:30am and 8pm ET on a weekday: outside that the free chain is
    frozen or empty, and a reading from it would be yesterday's under today's
    date."""
    if iv30_pct is None or not (0.5 <= float(iv30_pct) <= 400.0):
        return False
    now = (now or datetime.now(timezone.utc)).astimezone(ET)
    minutes = now.hour * 60 + now.minute
    if now.weekday() >= 5 or not (9 * 60 + 30 <= minutes <= 20 * 60):
        return False
    with _LOCK:
        try:
            con = _connect()
            with con:
                con.execute("INSERT OR IGNORE INTO iv_daily VALUES (?,?,?,?)",
                            (symbol.upper(), now.date().isoformat(), float(iv30_pct),
                             now.isoformat()))
            con.close()
            return True
        except sqlite3.Error:
            return False


def stored(symbol: str, limit: int = FULL_WINDOW) -> List[float]:
    with _LOCK:
        try:
            con = _connect()
            rows = con.execute("SELECT iv30 FROM iv_daily WHERE symbol=? ORDER BY day DESC LIMIT ?",
                               (symbol.upper(), limit)).fetchall()
            con.close()
        except sqlite3.Error:
            return []
    return [r[0] for r in reversed(rows)]


def _rank(values: List[float], today: float) -> Dict[str, Any]:
    lo, hi = min(values), max(values)
    rank = (today - lo) / (hi - lo) * 100.0 if hi > lo else None
    pct = sum(1 for v in values if v < today) / len(values) * 100.0
    return {"rank": None if rank is None else round(max(0.0, min(100.0, rank)), 1),
            "percentile": round(pct, 1), "low": round(lo, 2), "high": round(hi, 2),
            "days": len(values)}


def rank_for(symbol: str, iv30_pct: Optional[float], provider: Any = None) -> Dict[str, Any]:
    """The best available rank and percentile, with what it is measured on."""
    sym = symbol.upper()
    idx = VOL_INDEX.get(sym)
    if idx and provider is not None:
        # Yahoo answers some periods for some indices and not others (^VIX
        # came back empty for "1y" on 2026-10-13 and not for "2y").
        hist = None
        for period in ("1y", "2y", "6mo"):
            try:
                hist = provider.history(idx[0], period=period, interval="1d")
            except Exception:                                     # noqa: BLE001
                hist = None
            if hist is not None and not hist.empty and "Close" in hist:
                break
        if hist is not None and not hist.empty and "Close" in hist:
            closes = [float(v) for v in hist["Close"].dropna().tail(FULL_WINDOW)]
            if len(closes) >= MIN_DAYS_TO_SHOW:
                out = _rank(closes, closes[-1])
                out.update({"available": True, "source": "vol_index", "index": idx[0],
                            "today": round(closes[-1], 2),
                            "label": idx[1],
                            "note": "The index's own 30-day implied volatility over the past year, "
                                    "not this ETF chain's: close, not identical."})
                return out
    history = stored(sym)
    if iv30_pct is not None and len(history) >= MIN_DAYS_TO_SHOW:
        out = _rank(history, float(iv30_pct))
        out.update({"available": True, "source": "optic_daily", "today": round(float(iv30_pct), 2),
                    "label": "Optic's own daily 30-day at-the-money IV readings",
                    "note": ("Over {} trading days of readings, not a full year yet.".format(len(history))
                             if len(history) < FULL_WINDOW else "Over the past year of daily readings.")})
        return out
    need = MIN_DAYS_TO_SHOW - len(history)
    return {"available": False, "source": "none", "days": len(history),
            "reason": ("No implied-volatility history yet. Optic stores one reading a trading day; "
                       "a rank appears after {} more, and a full-year rank after {}.".format(
                           max(need, 0), FULL_WINDOW - len(history)))}
