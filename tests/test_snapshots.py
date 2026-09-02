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
