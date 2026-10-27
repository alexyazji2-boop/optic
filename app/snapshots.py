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

**accounts.db too, since 2026-10-23.** The readiness audit (P0, F-40) found the
file holding every account, plan, watchlist and the encrypted brokerage data
with no copy at all. `take_accounts` gives it the same same-volume protection.
That is the cheap half again: an off-host copy still needs somewhere to put it,
which is a decision and an account for the owner, not code. Its snapshots are
not listed by the open `/api/snapshots`, and a deleted account leaves them when
the last copy holding it is pruned, KEEP_ACCOUNTS days later.
"""

from __future__ import annotations

import logging
import os
import re
import sqlite3
from datetime import datetime, timezone
from typing import Dict, List, Optional

from . import db as accounts_db
from . import paper

# Keep a week. The ledger is measured in hundreds of KB, so retention is limited
# by usefulness rather than by space: a fault older than this would already have
# been noticed, or is in every copy anyway.
KEEP = int(os.environ.get("LEDGER_SNAPSHOT_KEEP", "7"))
EVERY_HOURS = float(os.environ.get("LEDGER_SNAPSHOT_HOURS", "24"))

# Accounts keep the same week. Each copy also holds rows a reader has since
# deleted, so the privacy policy states this figure; change both together.
KEEP_ACCOUNTS = int(os.environ.get("ACCOUNTS_SNAPSHOT_KEEP", "7"))

_NAME = re.compile(r"^tracker-(\d{8}T\d{6}Z)\.db$")
_ACCOUNTS_NAME = re.compile(r"^accounts-(\d{8}T\d{6}Z)\.db$")


def _dir() -> str:
    return os.path.join(os.path.dirname(paper.DB_PATH), "snapshots")


def _accounts_dir() -> str:
    return os.path.join(os.path.dirname(accounts_db.DB_PATH), "snapshots")


def existing() -> List[Dict[str, object]]:
    """Every ledger snapshot on disk, newest first."""
    return _listing(_dir(), _NAME)


def existing_accounts() -> List[Dict[str, object]]:
    """Every accounts snapshot on disk, newest first."""
    return _listing(_accounts_dir(), _ACCOUNTS_NAME)


def _listing(directory: str, pattern: "re.Pattern[str]") -> List[Dict[str, object]]:
    out: List[Dict[str, object]] = []
    try:
        names = os.listdir(directory)
    except OSError:
        return out
    for name in names:
        m = pattern.match(name)
        if not m:
            continue
        path = os.path.join(directory, name)
        try:
            size = os.path.getsize(path)
        except OSError:
            continue
        out.append({"name": name, "taken_at": m.group(1), "bytes": size})
    out.sort(key=lambda r: str(r["taken_at"]), reverse=True)
    return out


def take() -> Optional[str]:
    """Write one ledger snapshot and prune old ones. Returns the path, or None."""
    path = _copy(paper.DB_PATH, _dir(), "tracker")
    if path:
        _prune()
    return path


def take_accounts() -> Optional[str]:
    """Write one accounts snapshot and prune old ones. Returns the path, or None.

    The copy keeps no brokerage data keys. `app/vault.py` makes deleting a
    reader's wrapped key the deletion of their brokerage data, "a promise about
    backups too", and the consent text says so. A snapshot holding last week's
    keys would break that for KEEP_ACCOUNTS days. So the keys are blanked in the
    copy (the column is NOT NULL, hence an empty blob) and the file is vacuumed
    with secure_delete so the old bytes are not left in free pages. The cost is
    on restore: accounts, watchlists and plans come back, and a linked reader
    reconnects their broker. A copy that cannot be scrubbed is deleted, not kept."""
    path = _copy(accounts_db.DB_PATH, _accounts_dir(), "accounts")
    if not path:
        return None
    try:
        _blank_data_keys(path)
    except Exception:
        try:
            os.remove(path)
        except OSError:
            pass
        raise
    _prune_listing(existing_accounts(), _accounts_dir(), KEEP_ACCOUNTS)
    return path


def _blank_data_keys(path: str) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA secure_delete=ON")
        has = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='brokerage_users'").fetchone()
        if has:
            with conn:
                conn.execute("UPDATE brokerage_users SET dek = X''")
        conn.execute("VACUUM")
    finally:
        conn.close()


def _copy(source: str, directory: str, prefix: str) -> Optional[str]:
    if not os.path.exists(source):
        return None
    os.makedirs(directory, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = os.path.join(directory, "{}-{}.db".format(prefix, stamp))

    src = sqlite3.connect(source, timeout=15)
    try:
        dst = sqlite3.connect(path)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    return path


def _prune() -> None:
    """Delete all but the newest KEEP snapshots.

    Only files matching the snapshot name pattern are ever considered, so this
    cannot reach the live ledger or anything else that shares the directory.
    """
    _prune_listing(existing(), _dir(), KEEP)


def _prune_listing(rows: List[Dict[str, object]], directory: str, keep: int) -> None:
    for row in rows[keep:]:
        try:
            os.remove(os.path.join(directory, str(row["name"])))
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


# The tables a restored accounts copy is counted by. What a reader would miss.
_RESTORE_TABLES = ("users", "sessions", "passkeys", "watchlists", "saved_research", "subscriptions",
                   "brokerage_users", "brokerage_accounts", "alerts")


def verify_restore(snapshot: str, workdir: Optional[str] = None) -> Dict[str, object]:
    """Restore one accounts snapshot into an isolated directory and check it.

    A backup nobody has restored is a hope. This copies the snapshot (the
    original is only read), runs SQLite's integrity check on the copy, checks
    that the accounts migrations already applied in it are every one this code
    knows (so the running app would open it without migrating), counts what a
    reader would get back, and confirms the brokerage data keys are blank (a
    restore must not bring back a deleted reader's brokerage data). It never
    opens the live database. Run on the host with
    `python -m app.snapshots verify <path>`; the copy is removed afterwards
    unless `workdir` is given."""
    import shutil
    import tempfile
    own = workdir is None
    where = workdir or tempfile.mkdtemp(prefix="optic-restore-")
    target = os.path.join(where, "accounts.db")
    out: Dict[str, object] = {"snapshot": snapshot, "restored_to": target, "ok": False}
    try:
        os.makedirs(where, exist_ok=True)
        shutil.copyfile(snapshot, target)
        conn = sqlite3.connect(target)
        try:
            out["integrity"] = conn.execute("PRAGMA integrity_check").fetchone()[0]
            names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            have = sorted(r[0] for r in conn.execute("SELECT version FROM schema_migrations")) \
                if "schema_migrations" in names else []
            known = sorted(v for v, _name, _sql in accounts_db.MIGRATIONS)
            out["migrations_missing"] = [v for v in known if v not in have]
            out["tables"] = {t: conn.execute("SELECT COUNT(*) FROM {}".format(t)).fetchone()[0]
                             for t in _RESTORE_TABLES if t in names}
            out["data_keys_blank"] = ("brokerage_users" not in names or conn.execute(
                "SELECT COUNT(*) FROM brokerage_users WHERE length(dek) > 0").fetchone()[0] == 0)
        finally:
            conn.close()
        out["ok"] = (out["integrity"] == "ok" and not out["migrations_missing"] and bool(out["data_keys_blank"]))
    except (sqlite3.Error, OSError) as exc:
        out["error"] = "{}: {}".format(type(exc).__name__, exc)
    finally:
        if own:
            shutil.rmtree(where, ignore_errors=True)
            out["restored_to"] = None
    return out


if __name__ == "__main__":                      # python -m app.snapshots verify [path]
    import json
    import sys
    args = sys.argv[1:]
    if not args or args[0] != "verify":
        print("usage: python -m app.snapshots verify [accounts snapshot path]")
        sys.exit(2)
    rows = existing_accounts()
    path = args[1] if len(args) > 1 else (os.path.join(_accounts_dir(), str(rows[0]["name"])) if rows else None)
    if not path:
        print("No accounts snapshot on disk yet.")
        sys.exit(1)
    result = verify_restore(str(path))
    print(json.dumps(result, indent=1, default=str))
    sys.exit(0 if result["ok"] else 1)
