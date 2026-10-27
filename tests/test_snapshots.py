"""Dated copies of the ledger.

The paper ledger is one SQLite file on one volume, and it is the entire point of
the tracker — a record that resets is not a record. Nothing stood between it and
a bad write or a mistaken clear.

The copy is taken with sqlite3's backup API rather than by copying the file. The
database runs in WAL mode, so committed pages can still be sitting in the -wal
when the main file is read; a plain copy can capture a torn state that opens
cleanly and is quietly missing the newest writes. That is the worst kind of
backup to own, because it fails only when you finally need it.
"""

import os
import sqlite3

import pytest

from app import snapshots


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    """A real SQLite ledger in WAL mode, at a temporary path."""
    db = tmp_path / "tracker.db"
    conn = sqlite3.connect(str(db))
    conn.execute("pragma journal_mode=wal")
    conn.execute("create table positions (id integer primary key, ticker text)")
    conn.executemany("insert into positions (ticker) values (?)",
                     [("NVDA",), ("SPY",), ("AAPL",)])
    conn.commit()
    conn.close()
    monkeypatch.setattr(snapshots.paper, "DB_PATH", str(db))
    return db


def test_a_snapshot_is_a_readable_copy(ledger):
    path = snapshots.take()
    assert path and os.path.exists(path)
    got = sqlite3.connect(path).execute(
        "select ticker from positions order by ticker").fetchall()
    assert [r[0] for r in got] == ["AAPL", "NVDA", "SPY"]


def test_uncommitted_wal_pages_are_captured(ledger):
    """The reason for using the backup API rather than copying the file."""
    conn = sqlite3.connect(str(ledger))
    conn.execute("pragma journal_mode=wal")
    conn.execute("insert into positions (ticker) values ('TSLA')")
    conn.commit()          # committed, but likely still only in the -wal
    path = snapshots.take()
    conn.close()
    rows = sqlite3.connect(path).execute("select count(*) from positions").fetchone()
    assert rows[0] == 4, "the newest committed row is missing from the snapshot"


def test_retention_keeps_the_newest_and_drops_the_rest(ledger, monkeypatch):
    monkeypatch.setattr(snapshots, "KEEP", 3)
    made = []
    for i in range(6):
        # Distinct stamps without waiting a second per snapshot.
        monkeypatch.setattr(snapshots, "_NAME", snapshots._NAME)
        d = os.path.join(os.path.dirname(str(ledger)), "snapshots")
        os.makedirs(d, exist_ok=True)
        name = "tracker-202609%02dT120000Z.db" % (i + 1)
        sqlite3.connect(os.path.join(d, name)).close()
        made.append(name)
    snapshots._prune()
    left = [r["name"] for r in snapshots.existing()]
    assert len(left) == 3
    assert left == sorted(made, reverse=True)[:3]


def test_prune_only_touches_snapshot_files(ledger):
    """It runs in a directory it does not exclusively own, so the pattern match
    is what stops it deleting something else."""
    d = os.path.join(os.path.dirname(str(ledger)), "snapshots")
    os.makedirs(d, exist_ok=True)
    bystander = os.path.join(d, "notes.txt")
    open(bystander, "w").write("keep me")
    for i in range(9):
        sqlite3.connect(os.path.join(d, "tracker-202609%02dT120000Z.db" % (i + 1))).close()
    snapshots._prune()
    assert os.path.exists(bystander)


def test_the_schedule_is_testable_without_waiting(monkeypatch):
    monkeypatch.setattr(snapshots, "EVERY_HOURS", 24.0)
    assert snapshots.due(None, 1000.0) is True, "never taken means take one"
    assert snapshots.due(1000.0, 1000.0 + 3600) is False, "an hour later is not due"
    assert snapshots.due(1000.0, 1000.0 + 25 * 3600) is True


def test_zero_hours_disables_snapshots(monkeypatch):
    monkeypatch.setattr(snapshots, "EVERY_HOURS", 0.0)
    assert snapshots.due(None, 1000.0) is False


def test_a_missing_ledger_is_not_an_error(tmp_path, monkeypatch):
    """A fresh volume has no ledger yet; the loop must not crash on the first pass."""
    monkeypatch.setattr(snapshots.paper, "DB_PATH", str(tmp_path / "absent.db"))
    assert snapshots.take() is None


# ------------------------------------------------------------ accounts.db
#
# Readiness audit 2026-10-23 (F-40): accounts.db, holding every account, plan and
# the sealed brokerage data, had no copy at all.


# Large enough to spill onto an overflow page, which is where an UPDATE leaves the
# old bytes behind in a free page unless secure_delete or VACUUM clears them. A
# real wrapped key is small and lives in-row; the test needs the harder case.
KEY = b"WRAPPED-DATA-KEY-BYTES" * 400


@pytest.fixture
def accounts(tmp_path, monkeypatch):
    """A small accounts.db in WAL mode with one linked reader, at a temporary path."""
    db = tmp_path / "accounts.db"
    conn = sqlite3.connect(str(db))
    conn.execute("pragma journal_mode=wal")
    conn.execute("create table users (id text primary key, email text)")
    conn.execute("create table brokerage_users (user_id text primary key, provider text not null, "
                 "provider_user_id text not null, secret blob, dek blob not null, created_at text not null)")
    conn.execute("insert into users values ('u1', 'reader@example.test')")
    conn.execute("insert into brokerage_users values ('u1', 'snaptrade', 'p1', ?, ?, '2026-10-23')",
                 (b"sealed-secret", KEY))
    conn.commit()
    conn.close()
    monkeypatch.setattr(snapshots.accounts_db, "DB_PATH", str(db))
    return db


def test_accounts_are_copied(accounts):
    path = snapshots.take_accounts()
    assert path and os.path.basename(path).startswith("accounts-")
    got = sqlite3.connect(path).execute("select email from users").fetchall()
    assert got == [("reader@example.test",)]
    assert [r["name"] for r in snapshots.existing_accounts()] == [os.path.basename(path)]


def test_an_accounts_copy_holds_no_brokerage_data_key(accounts):
    """Deleting the wrapped key is the deletion (app/vault.py), and the consent
    text promises backups cannot be read either. A copy with the key would break
    that for a week, so the key is blanked and its bytes are not left behind."""
    path = snapshots.take_accounts()
    row = sqlite3.connect(path).execute("select dek, secret from brokerage_users").fetchone()
    assert row[0] == b"", "the data key must not survive into the copy"
    assert row[1] == b"sealed-secret", "the ciphertext stays; without the key it is unreadable"
    assert b"WRAPPED-DATA-KEY-BYTES" not in open(path, "rb").read(), "old key bytes left in free pages"
    live = sqlite3.connect(str(accounts)).execute("select dek from brokerage_users").fetchone()
    assert live[0] == KEY, "only the copy is scrubbed, never the live file"


def test_accounts_and_ledger_snapshots_are_pruned_separately(accounts, ledger, monkeypatch):
    """They share a directory when both files share a volume; one's retention
    must not delete the other's copies."""
    monkeypatch.setattr(snapshots, "KEEP_ACCOUNTS", 2)
    d = os.path.join(os.path.dirname(str(accounts)), "snapshots")
    os.makedirs(d, exist_ok=True)
    for i in range(4):
        sqlite3.connect(os.path.join(d, "accounts-202609%02dT120000Z.db" % (i + 1))).close()
        sqlite3.connect(os.path.join(d, "tracker-202609%02dT120000Z.db" % (i + 1))).close()
    snapshots.take_accounts()
    assert len(snapshots.existing_accounts()) == 2
    assert len(snapshots.existing()) == 4


def test_accounts_snapshots_are_not_listed_by_the_open_endpoint(accounts):
    snapshots.take_accounts()
    assert all(not str(r["name"]).startswith("accounts-") for r in snapshots.existing())


def test_a_copy_that_cannot_be_scrubbed_is_not_kept(accounts, monkeypatch):
    def broken(path):
        raise sqlite3.OperationalError("disk I/O error")
    monkeypatch.setattr(snapshots, "_blank_data_keys", broken)
    with pytest.raises(sqlite3.OperationalError):
        snapshots.take_accounts()
    assert snapshots.existing_accounts() == []
