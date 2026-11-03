"""Form 4 filings read from EDGAR for the insider trades Yahoo's list leaves out, kept across restarts.

Yahoo's insider list stops at its 150 latest rows, so for a company that files many grants it covers far less
than the two years the chart draws, and the older purchases and sales never reach Optic at all (UNH, measured
2026-11-03: 150 rows from 2025-06-24, 146 of them awards, none of them the executives' May 2025 purchases).
`app/insider_fill.py` reads the missing stretch from the filings themselves, and this keeps what it read.

The same lesson as `app/segment_store.py`: the shared feed cache in `app/feeds.py` keeps sixty entries on disk and
loses its memory with every deploy, so a few hundred parsed filings kept there would be evicted by ordinary feed
traffic and read again. A Form 4 is immutable once EDGAR accepts it, so its parse is kept here by accession number
and never expires, under TRACKER_DATA_DIR (the Railway volume in production). Failures are kept too, so a filing
that does not parse is not fetched on every visit. Each company's list of Form 4 filings is kept beside them with
the time it was read, since that list does change, when the company files.

A store that cannot be read or written costs the older trades, never the page: every failure is logged and
answered as "nothing kept".
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import sqlite3
from contextlib import closing
from typing import Any, Dict, Iterable, List, Optional

log = logging.getLogger(__name__)

_DATA_DIR = os.environ.get(
    "TRACKER_DATA_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"),
)
DB_PATH = os.path.join(_DATA_DIR, "form4.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS form4_filings (
  accession  TEXT PRIMARY KEY,   -- EDGAR accession number, 0000731766-25-000101
  cik        TEXT NOT NULL,      -- the issuer whose list it came from, without leading zeros
  parsed_at  TEXT NOT NULL,      -- UTC ISO instant it was read
  payload    TEXT NOT NULL       -- JSON: the open-market trades it reports, or why it could not be read
);
CREATE TABLE IF NOT EXISTS form4_lists (
  ticker     TEXT PRIMARY KEY,   -- the symbol as Optic asks for it
  cik        TEXT NOT NULL,
  fetched_at TEXT NOT NULL,      -- UTC ISO instant the list was read
  payload    TEXT NOT NULL       -- JSON: {filings: [[accession, filing date], ...] newest first, reaches: date}
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


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def load_many(accessions: Iterable[str]) -> Dict[str, Dict[str, Any]]:
    """The kept parse for each of these accessions that has one, in one query."""
    wanted = [a for a in dict.fromkeys(accessions) if a]
    if not wanted:
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    try:
        with closing(_connect()) as conn:
            # SQLite caps the parameters in one statement, and a busy filer has hundreds of filings
            for i in range(0, len(wanted), 500):
                part = wanted[i:i + 500]
                rows = conn.execute("SELECT accession, payload FROM form4_filings WHERE accession IN (%s)"
                                    % ",".join("?" * len(part)), part).fetchall()
                for accession, payload in rows:
                    try:
                        parsed = json.loads(payload)
                    except ValueError:
                        continue
                    if isinstance(parsed, dict):
                        out[accession] = parsed
    except (sqlite3.Error, OSError) as exc:
        log.warning("form4_store: could not read (%s)", exc)
        return {}
    return out


def save(accession: str, cik: str, parsed: Dict[str, Any]) -> bool:
    """Keep one filing's parse. True when it was written."""
    if not accession or not isinstance(parsed, dict):
        return False
    try:
        with closing(_connect()) as conn:
            with conn:
                conn.execute("INSERT OR REPLACE INTO form4_filings (accession, cik, parsed_at, payload) "
                             "VALUES (?, ?, ?, ?)",
                             (accession, cik or "", _now(), json.dumps(parsed, separators=(",", ":"))))
        return True
    except (sqlite3.Error, OSError) as exc:
        log.warning("form4_store: could not write %s (%s)", accession, exc)
        return False


def load_list(ticker: str) -> Optional[Dict[str, Any]]:
    """{cik, fetched_at, filings: [[accession, filing date], ...], reaches} for a symbol, or None. `reaches` is the
    earliest date the list is known to be whole from (its oldest filing, or the company's first)."""
    sym = (ticker or "").upper().strip()
    if not sym:
        return None
    try:
        with closing(_connect()) as conn:
            row = conn.execute("SELECT cik, fetched_at, payload FROM form4_lists WHERE ticker = ?", (sym,)).fetchone()
    except (sqlite3.Error, OSError) as exc:
        log.warning("form4_store: could not read the list for %s (%s)", sym, exc)
        return None
    if not row:
        return None
    try:
        body = json.loads(row[2])
    except ValueError:
        return None
    if not isinstance(body, dict) or not isinstance(body.get("filings"), list):
        return None
    return {"cik": row[0], "fetched_at": row[1], "filings": body["filings"], "reaches": body.get("reaches")}


def save_list(ticker: str, cik: str, filings: List[List[str]], reaches: Optional[str]) -> bool:
    sym = (ticker or "").upper().strip()
    if not sym or not cik:
        return False
    try:
        with closing(_connect()) as conn:
            with conn:
                conn.execute("INSERT OR REPLACE INTO form4_lists (ticker, cik, fetched_at, payload) VALUES (?, ?, ?, ?)",
                             (sym, cik, _now(), json.dumps({"filings": filings, "reaches": reaches},
                                                           separators=(",", ":"))))
        return True
    except (sqlite3.Error, OSError) as exc:
        log.warning("form4_store: could not write the list for %s (%s)", sym, exc)
        return False
