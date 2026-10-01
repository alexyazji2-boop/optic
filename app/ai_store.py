"""What the model wrote, kept across restarts, and what each call cost.

Asked as "what in the terminal is currently using up my $100 worth of credits",
and then "create a model which allows optic to work the same but minimizes the
API usage credits". Two tables in one SQLite file under TRACKER_DATA_DIR, which
in production is the Railway volume at /app/data and outlives the container.

**`kept`: a written piece, by kind and key.** Optic's Read by edition, the
desk by its date, an earnings brief by ticker and report date, a sector read
by symbol, a catalyst read by release. The writers in `app/ai.py` kept these in
module dicts, and Railway starts a new process on every deploy, so each deploy
paid for every one of them again: 22 commits shipped on 2026-09-30 and 30 on
the 29th, and each push was a fresh desk, a fresh catalyst read and a fresh
earnings brief for the next reader of each name. A row also counts the
attempts at a piece that is not kept yet, so a write that keeps failing is
tried a bounded number of times rather than on every rebuild.

**`calls`: the ledger.** One row per model call, with the tokens the API
reported, so the owner can see which part of the terminal is spending the
account's credit (`/api/ai/usage`). The Console's total cannot say that. A
call whose answer was paid for and then thrown away, malformed or cut off at
its token limit, is marked unused, because that is spend that bought nothing.
For two weeks before this existed every archived Read was the mechanical note
while the model was asked for one every twenty minutes, and nothing anywhere
said what was coming back.

**What is stored is the piece as served**, its method note and disclaimer
included. Unlike the weekly update (`app/weekly_store.py`), which is kept for a
week and so has those put round it on the way out, every kind here lives for a
day at most, so an edit to either reaches the page with the next piece written.

**A store that cannot be read or written costs the saving, never the page.**
Every failure here is logged and answered as "nothing kept", which is how the
writers behaved before. OSError as well as sqlite3.Error, because opening the
database creates its directory first and an unmounted volume raises from
`os.makedirs`.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from contextlib import closing
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")

_DATA_DIR = os.environ.get(
    "TRACKER_DATA_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"),
)
DB_PATH = os.path.join(_DATA_DIR, "ai.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS kept (
  kind        TEXT NOT NULL,      -- read, desk, earnings, sector, catalyst_read
  key         TEXT NOT NULL,
  written_at  REAL,               -- epoch seconds; NULL until a piece is kept
  payload     TEXT,               -- JSON; NULL until a piece is kept
  attempts    INTEGER NOT NULL DEFAULT 0,
  tried_at    REAL,               -- epoch seconds of the latest attempt
  PRIMARY KEY (kind, key)
);
CREATE TABLE IF NOT EXISTS calls (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  at                  REAL NOT NULL,      -- epoch seconds
  feature             TEXT NOT NULL,      -- see FEATURES
  model               TEXT NOT NULL,
  input_tokens        INTEGER NOT NULL DEFAULT 0,
  output_tokens       INTEGER NOT NULL DEFAULT 0,
  cache_read_tokens   INTEGER NOT NULL DEFAULT 0,
  cache_write_tokens  INTEGER NOT NULL DEFAULT 0,
  web_searches        INTEGER NOT NULL DEFAULT 0,
  stop_reason         TEXT,
  used                INTEGER NOT NULL DEFAULT 1,   -- 0: no answer was used
  note                TEXT                          -- why, or the error
);
CREATE INDEX IF NOT EXISTS calls_at ON calls (at);
"""

# Every call site, in the order the usage page lists them, with the name a
# reader knows it by. A feature missing here still records, under its own id.
FEATURES: Dict[str, str] = {
    "read": "Optic's Read",
    "desk": "Optic Desk (home)",
    "earnings": "Earnings briefs",
    "sector": "Sector and index reads",
    "catalyst_read": "Catalyst mode read",
    "weekly": "Weekly update",
    "catalyst_scan": "Catalyst scan",
    "pulse": "Pulse chat",
    "research": "Deep research",
}

# List prices in USD per million tokens, from Anthropic's pricing page as read
# on 2026-09-30: base input, 5-minute cache write, cache hit, output. The cache
# hit on Opus 5.5 is 0.05x its input price where every other model's is 0.1x.
# Matched on the id's start, so a dated id such as `claude-haiku-4-5-20251001`
# prices as its model. A model missing here is shown with no price rather than
# a guessed one.
PRICES: Dict[str, Tuple[float, float, float, float]] = {
    "claude-opus-5-5": (4.00, 5.00, 0.20, 20.00),
    "claude-opus-5": (5.00, 6.25, 0.50, 25.00),
    "claude-sonnet-5-5": (2.00, 2.50, 0.20, 10.00),
    "claude-sonnet-5": (2.00, 2.50, 0.20, 10.00),
    "claude-haiku-4-5": (1.00, 1.25, 0.10, 5.00),
    "claude-fable-5-1": (10.00, 12.50, 0.25, 50.00),
}
# Web search is billed per search on top of the tokens: $10 per 1,000.
WEB_SEARCH_USD = 0.01

# How long rows are kept. A kept piece older than two weeks is never served
# (every kind's lifetime is a day or less), and the ledger keeps a quarter.
KEEP_DAYS = 14
LEDGER_DAYS = 92
_PRUNE_EVERY = 3600.0
_PRUNED = [0.0]
_PRUNE_LOCK = threading.Lock()


def _connect() -> sqlite3.Connection:
    directory = os.path.dirname(DB_PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn


def _prune(conn: sqlite3.Connection, now: float) -> None:
    """Drop what can no longer be served or reported, at most hourly."""
    with _PRUNE_LOCK:
        if now - _PRUNED[0] < _PRUNE_EVERY:
            return
        _PRUNED[0] = now
    conn.execute("DELETE FROM kept WHERE COALESCE(written_at, tried_at, 0) < ?",
                 (now - KEEP_DAYS * 86400,))
    conn.execute("DELETE FROM calls WHERE at < ?", (now - LEDGER_DAYS * 86400,))


# ------------------------------------------------------------------ pieces
#
# The process's own copy, used when the disk cannot be read or written: a kept
# piece and the attempts at one, as the writers' module dicts held them before
# this store existed. Bounded, since nothing else ever empties it.
_MEMORY: Dict[Tuple[str, str], Dict[str, Any]] = {}
_MEMORY_MAX = 512
_MEMORY_LOCK = threading.Lock()


def _entry(kind: str, key: str) -> Dict[str, Any]:
    """This process's copy of kind/key, made if missing. Call under _MEMORY_LOCK."""
    entry = _MEMORY.get((kind, key))
    if entry is None:
        if len(_MEMORY) >= _MEMORY_MAX:
            oldest = min(_MEMORY, key=lambda k: max(_MEMORY[k]["written_at"] or 0,
                                                     _MEMORY[k]["tried_at"] or 0))
            _MEMORY.pop(oldest, None)
        entry = _MEMORY[(kind, key)] = {"payload": None, "written_at": None,
                                        "attempts": 0, "tried_at": None}
    return entry


def kept(kind: str, key: str,
         max_age: Optional[float] = None) -> Optional[Tuple[Dict[str, Any], float]]:
    """The piece kept under kind/key and when it was written (epoch seconds), if
    there is one younger than `max_age` seconds."""
    try:
        with closing(_connect()) as conn:
            row = conn.execute(
                "SELECT written_at, payload FROM kept WHERE kind = ? AND key = ?",
                (kind, key)).fetchone()
        written, body = (row["written_at"], row["payload"]) if row else (None, None)
    except (sqlite3.Error, OSError) as exc:
        log.warning("ai store unreadable, using this process's copy: %s: %s",
                    type(exc).__name__, exc)
        with _MEMORY_LOCK:
            entry = dict(_MEMORY.get((kind, key)) or {})
        written, body = entry.get("written_at"), entry.get("payload")
    if body is None or written is None:
        return None
    if max_age is not None and time.time() - written >= max_age:
        return None
    try:
        payload = json.loads(body)
    except ValueError:
        log.warning("ai store: the %s piece for %s is not JSON", kind, key)
        return None
    return (payload, float(written)) if isinstance(payload, dict) else None


def keep(kind: str, key: str, payload: Dict[str, Any]) -> bool:
    """Keep a written piece, replacing any kept before. False when only this
    process has it."""
    now = time.time()
    try:
        body = json.dumps(payload, default=str)
    except (TypeError, ValueError) as exc:
        log.warning("ai store: the %s piece for %s cannot be kept: %s", kind, key, exc)
        return False
    with _MEMORY_LOCK:
        _entry(kind, key).update(payload=body, written_at=now)
    try:
        with closing(_connect()) as conn:
            with conn:
                conn.execute(
                    """INSERT INTO kept (kind, key, written_at, payload) VALUES (?, ?, ?, ?)
                       ON CONFLICT(kind, key) DO UPDATE SET
                         written_at = excluded.written_at, payload = excluded.payload""",
                    (kind, key, now, body))
                _prune(conn, now)
    except (sqlite3.Error, OSError) as exc:
        log.warning("ai store unwritable, %s kept in this process only: %s: %s",
                    kind, type(exc).__name__, exc)
        return False
    return True


def claim(kind: str, key: str, max_attempts: int, retry_seconds: float) -> bool:
    """Count an attempt at a piece not yet kept, if one is allowed now. True
    when the caller may make it.

    Allowed when nothing is kept under kind/key, fewer than `max_attempts` have
    been made, and the last was `retry_seconds` ago or more. Decided and counted
    in one statement, so of two requests arriving together, or two processes,
    exactly one is told to write; a check and a count made separately let both
    through. Counted before the call, so one that crashes still counts."""
    now = time.time()
    try:
        with closing(_connect()) as conn:
            with conn:
                conn.execute("INSERT OR IGNORE INTO kept (kind, key) VALUES (?, ?)",
                             (kind, key))
                cur = conn.execute(
                    """UPDATE kept SET attempts = attempts + 1, tried_at = ?
                       WHERE kind = ? AND key = ? AND payload IS NULL AND attempts < ?
                         AND (tried_at IS NULL OR tried_at <= ?)""",
                    (now, kind, key, max_attempts, now - retry_seconds))
                return cur.rowcount == 1
    except (sqlite3.Error, OSError) as exc:
        log.warning("ai store unwritable, counting attempts in this process: %s: %s",
                    type(exc).__name__, exc)
    with _MEMORY_LOCK:
        entry = _entry(kind, key)
        if (entry["payload"] is not None or entry["attempts"] >= max_attempts
                or (entry["tried_at"] is not None
                    and now - entry["tried_at"] < retry_seconds)):
            return False
        entry.update(attempts=entry["attempts"] + 1, tried_at=now)
        return True


# ------------------------------------------------------------------ the ledger


def _n(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def record(feature: str, model: str, usage: Any = None, stop_reason: Optional[str] = None,
           note: Optional[str] = None) -> Optional[int]:
    """Write one call to the ledger and return its row id, or None if it could not be.

    `usage` is the SDK's usage object (or a dict of the same fields). A call that
    raised before an answer came back is recorded with no usage and the stop
    reason "error", which is what it cost: the API does not bill a request it
    refused or failed."""
    def field(name: str) -> Any:
        if isinstance(usage, dict):
            return usage.get(name)
        return getattr(usage, name, None)

    server = field("server_tool_use")
    searches = (server.get("web_search_requests") if isinstance(server, dict)
                else getattr(server, "web_search_requests", None))
    row = (time.time(), feature, model or "unknown", _n(field("input_tokens")),
           _n(field("output_tokens")), _n(field("cache_read_input_tokens")),
           _n(field("cache_creation_input_tokens")), _n(searches),
           stop_reason, 0 if stop_reason == "error" else 1,
           (note or None) and str(note)[:300])
    try:
        with closing(_connect()) as conn:
            with conn:
                cur = conn.execute(
                    """INSERT INTO calls (at, feature, model, input_tokens, output_tokens,
                         cache_read_tokens, cache_write_tokens, web_searches, stop_reason,
                         used, note)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", row)
                return cur.lastrowid
    except (sqlite3.Error, OSError) as exc:
        log.warning("ai ledger unwritable, %s call not recorded: %s: %s",
                    feature, type(exc).__name__, exc)
        return None


def unused(call_id: Optional[int], note: str) -> None:
    """Mark a recorded call as paid for and thrown away, saying why."""
    if call_id is None:
        return
    try:
        with closing(_connect()) as conn:
            with conn:
                conn.execute("UPDATE calls SET used = 0, note = ? WHERE id = ?",
                             (str(note)[:300], call_id))
    except (sqlite3.Error, OSError) as exc:
        log.warning("ai ledger unwritable: %s: %s", type(exc).__name__, exc)


def price_of(model: str) -> Optional[Tuple[float, float, float, float]]:
    """The list prices for a model id, longest matching prefix first."""
    for name in sorted(PRICES, key=len, reverse=True):
        if (model or "").startswith(name):
            return PRICES[name]
    return None


def cost(model: str, input_tokens: int = 0, output_tokens: int = 0,
         cache_read: int = 0, cache_write: int = 0, web_searches: int = 0) -> Optional[float]:
    """What a call cost at list prices, in USD, or None for a model with no price."""
    price = price_of(model)
    if price is None:
        return None
    inp, write, hit, out = price
    return ((input_tokens * inp + cache_write * write + cache_read * hit
             + output_tokens * out) / 1_000_000.0 + web_searches * WEB_SEARCH_USD)


def _bucket() -> Dict[str, Any]:
    return {"calls": 0, "failed": 0, "unused": 0, "input_tokens": 0, "output_tokens": 0,
            "cache_read_tokens": 0, "cache_write_tokens": 0, "web_searches": 0,
            "cost_usd": 0.0, "unpriced": 0}


def _add(bucket: Dict[str, Any], row: sqlite3.Row) -> None:
    bucket["calls"] += 1
    # Failed: no answer came back, and nothing was billed. Unused: an answer
    # came back, was billed, and was thrown away.
    if row["stop_reason"] == "error":
        bucket["failed"] += 1
    elif not row["used"]:
        bucket["unused"] += 1
    for name in ("input_tokens", "output_tokens", "cache_read_tokens",
                 "cache_write_tokens", "web_searches"):
        bucket[name] += row[name]
    usd = cost(row["model"], row["input_tokens"], row["output_tokens"],
               row["cache_read_tokens"], row["cache_write_tokens"], row["web_searches"])
    if usd is None:
        bucket["unpriced"] += 1
    else:
        bucket["cost_usd"] += usd


def usage(now: Optional[float] = None, recent: int = 25) -> Dict[str, Any]:
    """Spend by feature today (Eastern), over seven days and over thirty.

    Estimated at list prices from the tokens each call reported. The Console's
    figure is the bill; this is where it went."""
    now = time.time() if now is None else now
    midnight = datetime.fromtimestamp(now, ET).replace(hour=0, minute=0, second=0,
                                                       microsecond=0).timestamp()
    windows = {"today": midnight, "week": now - 7 * 86400, "month": now - 30 * 86400}
    try:
        with closing(_connect()) as conn:
            rows = conn.execute(
                "SELECT * FROM calls WHERE at >= ? ORDER BY at DESC",
                (min(windows.values()),)).fetchall()
            first = conn.execute("SELECT MIN(at) FROM calls").fetchone()[0]
    except (sqlite3.Error, OSError) as exc:
        log.warning("ai ledger unreadable: %s: %s", type(exc).__name__, exc)
        return {"available": False,
                "reason": "The usage ledger could not be read on this server."}

    features: Dict[str, Dict[str, Any]] = {}
    totals = {name: _bucket() for name in windows}
    for row in rows:
        entry = features.setdefault(row["feature"], {
            "feature": row["feature"],
            "label": FEATURES.get(row["feature"], row["feature"]),
            **{name: _bucket() for name in windows}})
        for name, since in windows.items():
            if row["at"] >= since:
                _add(entry[name], row)
                _add(totals[name], row)

    order = list(FEATURES)
    listed = sorted(features.values(), key=lambda e: (
        order.index(e["feature"]) if e["feature"] in order else len(order), e["feature"]))

    def stamp(at: float) -> str:
        return datetime.fromtimestamp(at, timezone.utc).isoformat()

    latest: List[Dict[str, Any]] = []
    for row in rows[:recent]:
        latest.append({
            "at": stamp(row["at"]), "feature": row["feature"],
            "label": FEATURES.get(row["feature"], row["feature"]), "model": row["model"],
            "input_tokens": row["input_tokens"], "output_tokens": row["output_tokens"],
            "cache_read_tokens": row["cache_read_tokens"],
            "web_searches": row["web_searches"], "stop_reason": row["stop_reason"],
            "used": bool(row["used"]), "note": row["note"],
            "cost_usd": cost(row["model"], row["input_tokens"], row["output_tokens"],
                             row["cache_read_tokens"], row["cache_write_tokens"],
                             row["web_searches"]),
        })
    return {
        "available": True,
        "since": stamp(first) if first else None,
        "features": listed,
        "totals": totals,
        "recent": latest,
        "prices": {name: {"input": p[0], "cache_write": p[1], "cache_read": p[2],
                          "output": p[3]} for name, p in PRICES.items()},
        "method": ("Estimated at Anthropic's list prices from the tokens each call "
                   "reported, plus $10 per 1,000 web searches. Your Claude Console "
                   "has the billed figure. Unused means an answer was paid for and "
                   "thrown away, cut off at its length limit or not in the expected "
                   "format. Failed means no answer came back, which is not billed."),
    }
