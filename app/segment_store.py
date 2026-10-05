"""Parsed filings for the segment tables, kept across restarts.

**What went wrong.** The Financials tab's segment tables are read out of each
10-Q and 10-K's XBRL instance document, three filings per request because each
is about a megabyte (see `app/analytics/segments.py`). The design was that a
reader who came back found the history longer. It never got longer for long:
the parsed filings were kept in `app/feeds.py`'s shared cache, which every feed
in the app writes to and which keeps sixty entries on disk, oldest out first,
and each parse stored the raw megabyte document beside it as a sixty-first. So
the parses were evicted by ordinary feed traffic within minutes, and lost
outright on every deploy, since the process memory that also held them goes
with the container. Measured on production on 2026-10-05, half an hour after a
deploy: the third request in a row for Intel reported 9 of 13 filings read, 3
of them fetched by that request, so the process had started from none; and
the day before, the panel sat at 3 of 13, the first batch, visit after visit.

A filing is immutable once EDGAR accepts it, so its parse is kept here by
accession number and never expires, under TRACKER_DATA_DIR, which in production
is the Railway volume and outlives the container. Failures are kept as well,
as the shared cache kept them, so a document that does not parse is not
fetched again on every visit.

**A store that cannot be read or written costs the history, never the panel.**
Every failure here is logged and answered as "nothing kept", which is how the
panel behaved before: it reads the filings again, a batch at a time. OSError as
well as sqlite3.Error, because opening the database creates its directory first
and an unmounted volume raises from `os.makedirs`.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import sqlite3
from contextlib import closing
from typing import Any, Dict, Iterable

log = logging.getLogger(__name__)

_DATA_DIR = os.environ.get(
    "TRACKER_DATA_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"),
)
DB_PATH = os.path.join(_DATA_DIR, "segments.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS segment_filings (
  accession  TEXT PRIMARY KEY,   -- EDGAR accession number, 0000050863-26-000123
  parsed_at  TEXT NOT NULL,      -- UTC ISO instant it was read
  payload    TEXT NOT NULL       -- JSON: what parse_instance answered, failures too
);
"""


def _connect() -> sqlite3.Connection:
    directory = os.path.dirname(DB_PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn


def load_many(accessions: Iterable[str]) -> Dict[str, Dict[str, Any]]:
    """The kept parse for each of these accessions that has one.

    One query for a ticker's whole list rather than one connection per filing:
    the panel asks for thirteen at a time."""
    wanted = [a for a in dict.fromkeys(accessions) if a]
    if not wanted:
        return {}
    try:
        with closing(_connect()) as conn:
            rows = conn.execute(
                "SELECT accession, payload FROM segment_filings WHERE accession IN (%s)"
                % ",".join("?" * len(wanted)), wanted).fetchall()
    except (sqlite3.Error, OSError) as exc:
        log.warning("segment_store: could not read (%s)", exc)
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for accession, payload in rows:
        try:
            parsed = json.loads(payload)
        except ValueError:
            continue
        if isinstance(parsed, dict):
            out[accession] = parsed
    return out


def save(accession: str, parsed: Dict[str, Any]) -> bool:
    """Keep one filing's parse. True when it was written."""
    if not accession or not isinstance(parsed, dict):
        return False
    try:
        with closing(_connect()) as conn:
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO segment_filings (accession, parsed_at, payload) "
                    "VALUES (?, ?, ?)",
                    (accession, dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                     json.dumps(parsed, separators=(",", ":"))))
        return True
    except (sqlite3.Error, OSError) as exc:
        log.warning("segment_store: could not write %s (%s)", accession, exc)
        return False
