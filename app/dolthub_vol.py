"""Daily implied and realised volatility for ~1,500 US optionable symbols, from
DoltHub's free `post-no-preference/options` database.

Why: Optic's IV rank rests on its own readings, one a trading day, so a
symbol needs a year of visits before it has a real rank. This database has
two years of daily history for every name it covers (from 2024-10-01, a
session behind), so the rank is real on the first look.

**What the columns are**, measured rather than assumed (2026-10-14, SPY, 516
sessions): `iv_current` follows the VIX with a correlation of 0.987 in level
and 0.96 in daily change, at about 0.83 of it, which is what a 30-day
at-the-money IV does beside an index that also prices the wings; `hv_current`
matches the 30-day close-to-close realised volatility exactly (correlation
1.000). Both are annualised decimals.

**Licence.** The database is CC BY-SA 4.0: free to use, including
commercially, with attribution, and anything adapted from it shared under the
same licence. Whether to show it to the public is the owner's decision, so it
is off unless `OPTIC_DOLTHUB` is set; `ATTRIBUTION` goes beside every figure
it supplies.

**How it is fetched.** DoltHub's SQL API answers one date for every symbol in
under a second, 1,000 rows a page, but a few months of one symbol can time out
(about 50 seconds). So the store is filled a day at a time, all symbols at
once, two pages a day: a two-year backfill is about a thousand small requests,
run once in the background, and each day after that is two.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

API = "https://www.dolthub.com/api/v1alpha1/post-no-preference/options/master"
FIRST_DAY = date(2024, 10, 1)
PAGE = 1000
ATTRIBUTION = ("Implied and realised volatility history: DoltHub post-no-preference/options, "
               "CC BY-SA 4.0")
SOURCE_URL = "https://www.dolthub.com/repositories/post-no-preference/options"
_LOCK = threading.Lock()
_log = logging.getLogger("uvicorn.error")


def enabled() -> bool:
    return os.environ.get("OPTIC_DOLTHUB", "false").strip().lower() in ("1", "true", "yes", "on")


def db_path() -> str:
    return os.path.join(os.environ.get("TRACKER_DATA_DIR", "data"), "dolthub_vol.db")


def _connect() -> sqlite3.Connection:
    path = db_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    con = sqlite3.connect(path, timeout=10)
    con.execute("CREATE TABLE IF NOT EXISTS vol (symbol TEXT NOT NULL, day TEXT NOT NULL, iv REAL, hv REAL, "
                "PRIMARY KEY (symbol, day))")
    # Days fetched, including empty ones (holidays), so a resumed backfill
    # does not ask for them again.
    con.execute("CREATE TABLE IF NOT EXISTS days (day TEXT PRIMARY KEY, rows INTEGER NOT NULL, fetched_at TEXT)")
    return con


def _get(sql: str, timeout: float = 30.0) -> Dict[str, Any]:
    url = API + "?q=" + urllib.parse.quote(sql)
    req = urllib.request.Request(url, headers={"User-Agent": "OpticTerminal/1.0 (+https://theopticterminal.com)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _num(v: Any) -> Optional[float]:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x and x > 0 else None


def fetch_day(day: date, getter=_get) -> List[Tuple[str, Optional[float], Optional[float]]]:
    """Every symbol's iv and hv for one date, paged by symbol."""
    out: List[Tuple[str, Optional[float], Optional[float]]] = []
    after = ""
    while True:
        sql = ("SELECT act_symbol, iv_current, hv_current FROM volatility_history WHERE date = '{}' "
               "AND act_symbol > '{}' ORDER BY act_symbol LIMIT {}".format(day.isoformat(), after.replace("'", ""), PAGE))
        d = getter(sql)
        status = d.get("query_execution_status")
        if status not in ("Success", "RowLimit"):
            raise RuntimeError("DoltHub: {} {}".format(status, (d.get("query_execution_message") or "")[:120]))
        rows = d.get("rows") or []
        out.extend((r["act_symbol"], _num(r.get("iv_current")), _num(r.get("hv_current"))) for r in rows)
        if len(rows) < PAGE:
            return out
        after = rows[-1]["act_symbol"]


def store_day(day: date, rows: List[Tuple[str, Optional[float], Optional[float]]]) -> None:
    with _LOCK:
        con = _connect()
        with con:
            con.executemany("INSERT OR REPLACE INTO vol VALUES (?,?,?,?)",
                            [(s.upper(), day.isoformat(), iv, hv) for s, iv, hv in rows])
            con.execute("INSERT OR REPLACE INTO days VALUES (?,?,?)",
                        (day.isoformat(), len(rows), datetime.now(timezone.utc).isoformat()))
        con.close()


def fetched_days() -> Dict[str, int]:
    with _LOCK:
        try:
            con = _connect()
            rows = con.execute("SELECT day, rows FROM days").fetchall()
            con.close()
        except sqlite3.Error:
            return {}
    return {d: n for d, n in rows}


def sync(until: Optional[date] = None, getter=_get, pause: float = 0.2, max_days: Optional[int] = None) -> Dict[str, Any]:
    """Fetch every weekday from FIRST_DAY to `until` (yesterday by default)
    not fetched yet. The database lags a session, so a day in the last three
    that came back empty is asked again; older empty days are holidays."""
    until = until or (datetime.now(timezone.utc).date() - timedelta(days=1))
    have = fetched_days()
    recent = {(until - timedelta(days=k)).isoformat() for k in range(3)}
    todo = []
    d = FIRST_DAY
    while d <= until:
        key = d.isoformat()
        if d.weekday() < 5 and (key not in have or (key in recent and not have.get(key))):
            todo.append(d)
        d += timedelta(days=1)
    if max_days is not None:
        todo = todo[:max_days]
    done, rows = 0, 0
    for d in todo:
        try:
            got = fetch_day(d, getter)
        except Exception as exc:                                     # noqa: BLE001
            _log.warning("dolthub sync %s: %s", d, exc)
            break
        store_day(d, got)
        done += 1
        rows += len(got)
        if pause:
            time.sleep(pause)
    return {"days": done, "rows": rows, "pending": len(todo) - done}


def series(symbol: str, limit: int = 252) -> List[Dict[str, Any]]:
    """The newest `limit` days for a symbol, oldest first."""
    with _LOCK:
        try:
            con = _connect()
            rows = con.execute("SELECT day, iv, hv FROM vol WHERE symbol=? ORDER BY day DESC LIMIT ?",
                               (symbol.upper(), limit)).fetchall()
            con.close()
        except sqlite3.Error:
            return []
    return [{"day": d, "iv": iv, "hv": hv} for d, iv, hv in reversed(rows)]


def iv_hv(symbol: str, limit: int = 252) -> Dict[str, Any]:
    """Implied against realised volatility now and over the year: the gap the
    variance risk premium lives in. Percentages."""
    rows = [r for r in series(symbol, limit) if r["iv"] and r["hv"]]
    if len(rows) < 20:
        return {"available": False, "reason": "No volatility history for this symbol in the store."}
    gaps = [(r["iv"] - r["hv"]) * 100 for r in rows]
    last = rows[-1]
    gap = gaps[-1]
    # This stock's own record: how often implied beat the volatility that
    # followed. hv 21 sessions on is the realised vol of the 30 days after.
    after = [(rows[k]["iv"], rows[k + 21]["hv"]) for k in range(len(rows) - 21)]
    beat = round(sum(1 for iv, rv in after if iv > rv) / len(after) * 100, 1) if len(after) >= 60 else None
    return {
        "available": True, "as_of": last["day"], "days": len(rows),
        "iv30": round(last["iv"] * 100, 2), "hv30": round(last["hv"] * 100, 2), "gap": round(gap, 2),
        "ratio": round(last["iv"] / last["hv"], 2),
        "gap_percentile": round(sum(1 for g in gaps if g < gap) / len(gaps) * 100, 1),
        "iv_above_hv_pct": round(sum(1 for g in gaps if g > 0) / len(gaps) * 100, 1),
        "iv_above_next_rv_pct": beat, "next_rv_days": len(after),
        "history": [{"day": r["day"], "iv": round(r["iv"] * 100, 2), "hv": round(r["hv"] * 100, 2)}
                    for r in rows[:: max(1, len(rows) // 120)]],
        "source": ATTRIBUTION, "source_url": SOURCE_URL,
        "note": "IV is 30-day at-the-money implied volatility; HV is the past 30 days' realised volatility, "
                "so the two cover different 30 days: one expected, one already happened.",
    }
