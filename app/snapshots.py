"""Dated copies of the ledger, so a corrupted or wiped record is recoverable.

The paper ledger is one SQLite file on one volume. That file is the entire point
of the tracker — a track record that resets is not a track record — and until
now nothing stood between it and a bad write, a half-finished migration or a
mistaken clear.

What this protects against: corruption, an accidental wipe, a scan that writes
something wrong. What it does NOT protect against: losing the volume itself,
since the copies live beside the original. Off-host backup is a different job
and needs somewhere to put them; this is the cheap half that needs nothing.

sqlite3.Connection.backup() rather than copying the file. The database runs in
WAL mode, so committed pages can still be sitting in the -wal when you read the
main file — a plain copy can capture a torn state that opens fine and is quietly
missing the most recent writes, which is the worst kind of backup to own.
"""

from __future__ import annotations

import logging
import os
import re
import sqlite3
from datetime import datetime, timezone
from typing import Dict, List, Optional

from . import paper

# Keep a week. The ledger is measured in hundreds of KB, so retention is limited
# by usefulness rather than by space: a fault older than this would already have
# been noticed, or is in every copy anyway.
KEEP = int(os.environ.get("LEDGER_SNAPSHOT_KEEP", "7"))
EVERY_HOURS = float(os.environ.get("LEDGER_SNAPSHOT_HOURS", "24"))

_NAME = re.compile(r"^tracker-(\d{8}T\d{6}Z)\.db$")


def _dir() -> str:
    return os.path.join(os.path.dirname(paper.DB_PATH), "snapshots")


def existing() -> List[Dict[str, object]]:
    """Every snapshot on disk, newest first."""
    out: List[Dict[str, object]] = []
    try:
        names = os.listdir(_dir())
    except OSError:
        return out
    for name in names:
        m = _NAME.match(name)
        if not m:
            continue
        path = os.path.join(_dir(), name)
        try:
            size = os.path.getsize(path)
        except OSError:
            continue
        out.append({"name": name, "taken_at": m.group(1), "bytes": size})
    out.sort(key=lambda r: str(r["taken_at"]), reverse=True)
    return out


def take() -> Optional[str]:
    """Write one snapshot and prune old ones. Returns the path, or None."""
    if not os.path.exists(paper.DB_PATH):
        return None
    os.makedirs(_dir(), exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = os.path.join(_dir(), "tracker-{}.db".format(stamp))

    src = sqlite3.connect(paper.DB_PATH, timeout=15)
    try:
        dst = sqlite3.connect(path)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()

    _prune()
    return path


def _prune() -> None:
    """Delete all but the newest KEEP snapshots.

    Only files matching the snapshot name pattern are ever considered, so this
    cannot reach the live ledger or anything else that shares the directory.
    """
    for row in existing()[KEEP:]:
        try:
            os.remove(os.path.join(_dir(), str(row["name"])))
        except OSError as exc:
            logging.getLogger("uvicorn.error").warning(
                "snapshot prune failed for %s: %s", row["name"], exc)


def due(last_taken: Optional[float], now: float) -> bool:
    """Whether a snapshot is owed. Time comes from the caller so the schedule is
    testable without waiting a day for it."""
    if EVERY_HOURS <= 0:
        return False
    if last_taken is None:
        return True
    return (now - last_taken) >= EVERY_HOURS * 3600
