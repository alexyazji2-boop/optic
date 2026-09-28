"""The weekly update, kept across restarts.

`app/ai.py` held the week's update in a module dict, and Railway starts a new
process on every deploy, so every deploy threw the update away and the next
reader waited for a fresh one: measured on 2026-09-28, a model call of up to
6,000 output tokens that took about 56 seconds. A rewrite is also a different
piece. After one deploy the first rewrite failed outright, and the retry came
back as "Flat Factory Orders Hand the Week to Friday's Jobs Report" where
readers had already seen "Durable Goods Go Flat as Friday's Jobs Report Takes
the Wheel", so the week's update changed under them within the week.

So it is written once per ISO week and kept here, under TRACKER_DATA_DIR, which
in production is the Railway volume at /app/data and outlives the container.
`/api/weekly?force=true` is the one way to replace it, and it takes the write
token or the signed-in owner (`_write_guard` in `app/main.py`). `writes` counts
how often the week has been written, so 1 after a deploy is the evidence this
is working.

**What is stored is what the model wrote, and nothing the code supplies.** The
headline, subhead and paragraphs are the piece; the method note and disclaimer
are put round them in `ai._weekly_update` on the way out, so an edit to either
reaches the page on the next deploy rather than the next week.

**A store that cannot be read or written costs the restart, never the page.**
Every failure here is logged and answered as "nothing stored", and the copy in
`ai`'s memory still serves the process, which is how the update behaved before
it was kept. OSError as well as sqlite3.Error, because opening the database
creates its directory first and an unmounted volume raises from `os.makedirs`.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from contextlib import closing
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

_DATA_DIR = os.environ.get(
    "TRACKER_DATA_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"),
)
DB_PATH = os.path.join(_DATA_DIR, "weekly.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS weekly_updates (
  week_key    TEXT PRIMARY KEY,   -- ISO week in Eastern time, e.g. 2026-W40
  written_at  TEXT NOT NULL,      -- UTC ISO instant the kept version was written
  model       TEXT NOT NULL,
  payload     TEXT NOT NULL,      -- JSON: headline, subhead, paragraphs
  writes      INTEGER NOT NULL DEFAULT 1
);
"""

# Columns added to the table after it first shipped, as in `app/catalysts.py`:
# CREATE TABLE IF NOT EXISTS never alters a table that is already there, so the
# production store would refuse every insert naming a column added to SCHEMA
# alone. A field of the piece itself goes in `payload` and needs no column.
_ADDED_COLUMNS: Dict[str, List[Tuple[str, str]]] = {}

# The fields of the model's answer that make up the piece.
WRITTEN = ("headline", "subhead", "paragraphs")


def _connect() -> sqlite3.Connection:
    directory = os.path.dirname(DB_PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    for table, columns in _ADDED_COLUMNS.items():
        have = {r[1] for r in conn.execute("PRAGMA table_info(%s)" % table)}
        for name, decl in columns:
            if name not in have:
                conn.execute("ALTER TABLE %s ADD COLUMN %s %s" % (table, name, decl))
    return conn


def load(week_key: str) -> Optional[Dict[str, Any]]:
    """What the model wrote for this week, with `model` and `written_at`, or None."""
    try:
        # closing() as well as the query: `with conn` only ends a transaction,
        # and leaves the connection open (see `app/db.py:cursor`).
        with closing(_connect()) as conn:
            row = conn.execute(
                "SELECT written_at, model, payload FROM weekly_updates WHERE week_key = ?",
                (week_key,)).fetchone()
    except (sqlite3.Error, OSError) as exc:
        log.warning("weekly store unreadable: %s: %s", type(exc).__name__, exc)
        return None
    if row is None:
        return None
    try:
        payload = json.loads(row["payload"])
    except ValueError:
        log.warning("weekly store: the payload for %s is not JSON", week_key)
        return None
    if not isinstance(payload, dict) or not payload.get("paragraphs"):
        return None
    written = {key: payload.get(key) for key in WRITTEN}
    written.update(model=row["model"], written_at=row["written_at"])
    return written


def save(week_key: str, written: Dict[str, Any]) -> bool:
    """Keep this week's piece, replacing any kept before. False when it could not be."""
    payload = json.dumps({key: written.get(key) for key in WRITTEN})
    try:
        with closing(_connect()) as conn:
            with conn:
                conn.execute(
                    """INSERT INTO weekly_updates (week_key, written_at, model, payload)
                       VALUES (?, ?, ?, ?)
                       ON CONFLICT(week_key) DO UPDATE SET
                         written_at = excluded.written_at,
                         model = excluded.model,
                         payload = excluded.payload,
                         writes = weekly_updates.writes + 1""",
                    (week_key, written["written_at"], written["model"], payload))
    except (sqlite3.Error, OSError) as exc:
        log.warning("weekly store unwritable, kept in memory only: %s: %s",
                    type(exc).__name__, exc)
        return False
    return True
