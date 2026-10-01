"""What the analysts did: each firm's rating and price-target actions.

Asked for with a screenshot of another terminal's feed of them: "if not yet
included, include analyst estimates as well". The date, the symbol, the firm,
its price target before and after, what it did, and the rating it holds. The
terminal had each name's consensus rating and mean target (`analyst_view`, the
Analysts widget), but not who moved them, or when.

Yahoo carries the actions one symbol at a time (`analyst_actions` in the
provider) and has no market-wide list, so the feed is put together here: a
background pass reads the actions of the names the scanner already ranks, the
most traded first, plus the curated large caps, and keeps the recent ones in
SQLite under TRACKER_DATA_DIR, so a restart does not begin it again. A name's
own page reads its actions directly, whatever it is.

**The rating is the firm's own word.** "Overweight", "Outperform" and "Buy" are
three firms saying the same thing, so each is also put in a class, buy, hold or
sell, for filtering; what is shown is what the firm wrote. A word that is in no
class is shown and left unclassed rather than guessed at.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
import time
from contextlib import closing
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

log = logging.getLogger(__name__)

_DATA_DIR = os.environ.get(
    "TRACKER_DATA_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"),
)
DB_PATH = os.path.join(_DATA_DIR, "analysts.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS actions (
  ticker      TEXT NOT NULL,
  at          TEXT NOT NULL,      -- UTC ISO instant of the action
  firm        TEXT NOT NULL,
  to_grade    TEXT,
  from_grade  TEXT,
  action      TEXT,               -- up, down, init, main, reit
  pt_action   TEXT,               -- Raises, Lowers, Maintains, Announces
  pt          REAL,
  prior_pt    REAL,
  PRIMARY KEY (ticker, at, firm)
);
CREATE INDEX IF NOT EXISTS actions_at ON actions (at);
CREATE TABLE IF NOT EXISTS read_at (
  ticker  TEXT PRIMARY KEY,
  at      REAL NOT NULL               -- epoch seconds this name was last read
);
"""

# How long a name's actions stand before the pass reads them again, how far
# back the feed keeps them, and how many names the pass covers. Analysts act on
# a working day's news, so six hours keeps the feed within a session of them;
# a name is one request.
REFRESH_HOURS = float(os.environ.get("ANALYSTS_REFRESH_HOURS", "6"))
KEEP_DAYS = 45
COVER = int(os.environ.get("ANALYSTS_COVER", "400"))

# Yahoo's action codes, as the page says them.
ACTIONS = {"up": "Upgrade", "down": "Downgrade", "init": "Initiated",
           "main": "Maintained", "reit": "Reiterated"}

# What the feed can be narrowed to. A rating change is the action; a target
# change is its own column, so raised and lowered are filters of their own.
FILTERS = {
    "upgrades": "Upgrades",
    "downgrades": "Downgrades",
    "initiated": "Initiations",
    "raised": "Target raised",
    "lowered": "Target lowered",
}
CLASSES = ("buy", "hold", "sell")

_LOCK = threading.Lock()


def grade_class(grade: Optional[str]) -> Optional[str]:
    """buy, hold or sell for a firm's rating word, or None for one in no class.

    Sell is tested first because its words contain the others' ("Market
    Underperform" contains "perform", "Underweight" contains "weight"), and buy
    before hold for the same reason ("Sector Outperform")."""
    g = (grade or "").strip().lower()
    if not g:
        return None
    if any(w in g for w in ("underperform", "underweight", "sell", "reduce", "negative")):
        return "sell"
    if any(w in g for w in ("outperform", "overweight", "buy", "positive", "accumulate",
                            "top pick", "add")):
        return "buy"
    if any(w in g for w in ("neutral", "hold", "equal", "perform", "in-line", "inline",
                            "weight", "mixed")):
        return "hold"
    return None


def _connect() -> sqlite3.Connection:
    directory = os.path.dirname(DB_PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn


def shaped(ticker: str, row: Dict[str, Any]) -> Dict[str, Any]:
    """An action as the page reads it: the firm's words, and their classes."""
    action = (row.get("action") or "").lower()
    return {
        "ticker": ticker,
        "at": row.get("at"),
        "firm": row.get("firm") or "",
        "rating": row.get("to_grade") or "",
        "prior_rating": row.get("from_grade") or "",
        "rating_class": grade_class(row.get("to_grade")),
        "action": action,
        "action_label": ACTIONS.get(action, action.capitalize()),
        "target_action": row.get("pt_action") or "",
        "target": row.get("pt"),
        "prior_target": row.get("prior_pt"),
    }


def for_symbol(provider, ticker: str, limit: int = 20) -> Dict[str, Any]:
    """One name's latest actions, read directly rather than from the feed."""
    sym = (ticker or "").upper().strip()
    try:
        rows = provider.analyst_actions(sym) or []
    except Exception as exc:                                    # noqa: BLE001
        log.warning("analyst actions unavailable for %s: %s", sym, exc)
        return {"available": False, "ticker": sym,
                "reason": "The analyst actions could not be read just now."}
    return {"available": True, "ticker": sym,
            "rows": [shaped(sym, r) for r in rows[:max(1, limit)]]}


def coverage(ranked: Iterable[Dict[str, Any]], curated: Iterable[str]) -> List[str]:
    """The names the feed covers: the curated large caps, then the ranked names
    by dollar volume, to COVER in all."""
    seen: Dict[str, None] = {}
    for sym in curated:
        seen.setdefault(str(sym).upper(), None)
    for row in sorted(ranked or [], key=lambda r: -(r.get("dollar_volume") or 0)):
        sym = str(row.get("symbol") or "").upper()
        if sym:
            seen.setdefault(sym, None)
    return list(seen)[:COVER]


def due(symbols: List[str], now: Optional[float] = None) -> List[str]:
    """The names whose actions have not been read within REFRESH_HOURS."""
    now = time.time() if now is None else now
    try:
        with closing(_connect()) as conn:
            read = {r["ticker"]: r["at"] for r in conn.execute("SELECT ticker, at FROM read_at")}
    except (sqlite3.Error, OSError) as exc:
        log.warning("analyst store unreadable: %s", exc)
        return []
    return [s for s in symbols if now - read.get(s, 0.0) >= REFRESH_HOURS * 3600]


def refresh(provider, symbols: List[str], budget: int,
            now: Optional[float] = None) -> Dict[str, Any]:
    """Read the actions of up to `budget` names that are due, and keep the recent ones."""
    now = time.time() if now is None else now
    if not _LOCK.acquire(blocking=False):
        return {"read": 0, "kept": 0, "busy": True}
    try:
        cutoff = (datetime.fromtimestamp(now, timezone.utc)
                  - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%dT%H:%M:%S")
        read = kept = 0
        for sym in due(symbols, now)[:max(0, budget)]:
            try:
                rows = provider.analyst_actions(sym) or []
            except Exception as exc:                            # noqa: BLE001
                # Counted as read: a name Yahoo will not answer for is tried
                # again next cycle, not on every batch until it does.
                log.info("analyst actions for %s unavailable: %s", sym, exc)
                rows = []
            recent = [r for r in rows if (r.get("at") or "") >= cutoff and r.get("firm")]
            try:
                with closing(_connect()) as conn:
                    with conn:
                        conn.executemany(
                            """INSERT OR REPLACE INTO actions
                               (ticker, at, firm, to_grade, from_grade, action, pt_action,
                                pt, prior_pt) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            [(sym, r["at"], r["firm"], r.get("to_grade"), r.get("from_grade"),
                              r.get("action"), r.get("pt_action"), r.get("pt"), r.get("prior_pt"))
                             for r in recent])
                        conn.execute("INSERT OR REPLACE INTO read_at (ticker, at) VALUES (?, ?)",
                                     (sym, now))
                        conn.execute("DELETE FROM actions WHERE at < ?", (cutoff,))
            except (sqlite3.Error, OSError) as exc:
                log.warning("analyst store unwritable: %s", exc)
                break
            read += 1
            kept += len(recent)
        return {"read": read, "kept": kept, "busy": False}
    finally:
        _LOCK.release()


def feed(days: int = 7, show: Optional[str] = None, rating: Optional[str] = None,
         limit: int = 200, now: Optional[float] = None) -> Dict[str, Any]:
    """The covered names' actions over the last `days`, newest first."""
    now = time.time() if now is None else now
    since = (datetime.fromtimestamp(now, timezone.utc)
             - timedelta(days=max(1, days))).strftime("%Y-%m-%dT%H:%M:%S")
    where, args = ["at >= ?"], [since]
    if show == "upgrades":
        where.append("action = 'up'")
    elif show == "downgrades":
        where.append("action = 'down'")
    elif show == "initiated":
        where.append("action = 'init'")
    elif show == "raised":
        where.append("pt_action = 'Raises'")
    elif show == "lowered":
        where.append("pt_action = 'Lowers'")
    try:
        with closing(_connect()) as conn:
            rows = conn.execute(
                "SELECT * FROM actions WHERE " + " AND ".join(where) + " ORDER BY at DESC",
                args).fetchall()
            covered = conn.execute("SELECT COUNT(*), MAX(at) FROM read_at").fetchone()
    except (sqlite3.Error, OSError) as exc:
        log.warning("analyst store unreadable: %s", exc)
        return {"available": False, "reason": "The analyst feed could not be read just now."}
    out = [shaped(r["ticker"], dict(r)) for r in rows]
    if rating in CLASSES:
        out = [r for r in out if r["rating_class"] == rating]
    return {
        "available": True,
        "days": max(1, days),
        "show": show if show in FILTERS else None,
        "rating": rating if rating in CLASSES else None,
        "count": len(out),
        "rows": out[:max(1, limit)],
        "covered": int(covered[0] or 0),
        "read_at": (datetime.fromtimestamp(covered[1], timezone.utc).isoformat()
                    if covered[1] else None),
        "method": ("Each firm's rating and price-target actions as Yahoo Finance "
                   "lists them, read every {:g} hours for the curated large caps and "
                   "the most traded names the scanner ranks. The rating is the firm's "
                   "own word; buy, hold and sell group firms' words that mean the same. "
                   "A target is a forecast, and the record of them as a group is "
                   "poor.").format(REFRESH_HOURS),
    }
