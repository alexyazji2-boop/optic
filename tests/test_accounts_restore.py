"""An accounts snapshot restores, in isolation, and keeps deletions deleted.

DEPLOY.md said accounts.db had no backup at all (checked 26 October 2026, at
production's ca490f8). The daily copy (app/snapshots.take_accounts, from the
readiness branch's F-40) is only worth what a restore gives back, so this
restores one: real sign-ups and a watchlist through the routes, a snapshot, the
copy opened in its own directory, never the live file."""

from __future__ import annotations

import os
import sqlite3

from fastapi.testclient import TestClient

import app.main as main
from app import db as accounts_db, snapshots
from app.auth import config

GOOD = "tungsten-carbide-9"


def _register(http, email):
    http.post("/api/auth/register", json={"first_name": "R", "last_name": "S", "email": email,
                                          "password": GOOD, "confirm_password": GOOD})
    return http.cookies.get(config.CSRF_COOKIE)


def test_a_snapshot_restores_accounts_and_watchlists_and_no_data_keys(tmp_path, monkeypatch):
    monkeypatch.setattr(snapshots, "_accounts_dir", lambda: str(tmp_path / "snapshots"))
    keep, gone = TestClient(main.app), TestClient(main.app)
    csrf = _register(keep, "restore-keep@example.com")
    keep.post("/api/watchlists", headers={"X-Optic-CSRF": csrf}, json={"name": "Restore", "symbols": ["NVDA"]})
    csrf2 = _register(gone, "restore-gone@example.com")
    assert gone.post("/api/auth/delete-account", headers={"X-Optic-CSRF": csrf2},
                     json={"confirm_email": "restore-gone@example.com", "password": GOOD}).status_code == 200
    with sqlite3.connect(accounts_db.DB_PATH) as live:
        uid = live.execute("SELECT id FROM users WHERE email = ?", ("restore-keep@example.com",)).fetchone()[0]
        live.execute("INSERT OR REPLACE INTO brokerage_users (user_id, provider, provider_user_id, dek, secret, created_at) "
                     "VALUES (?, 'snaptrade', 'p-restore', X'0102', X'0304', '2026-10-26')", (uid,))
    path = snapshots.take_accounts()
    assert path and os.path.dirname(path) == str(tmp_path / "snapshots")

    got = snapshots.verify_restore(path, workdir=str(tmp_path / "restored"))
    assert got["ok"] is True, got
    assert got["integrity"] == "ok" and got["migrations_missing"] == [] and got["data_keys_blank"] is True
    assert got["restored_to"] != accounts_db.DB_PATH

    copy = sqlite3.connect(got["restored_to"])
    emails = {r[0] for r in copy.execute("SELECT email FROM users")}
    assert "restore-keep@example.com" in emails and "restore-gone@example.com" not in emails, \
        "an account deleted before the snapshot is not in it"
    assert copy.execute("SELECT COUNT(*) FROM watchlists WHERE user_id = ? AND name = 'Restore'", (uid,)).fetchone()[0] == 1
    assert copy.execute("SELECT dek FROM brokerage_users WHERE user_id = ?", (uid,)).fetchone()[0] == b""
    with sqlite3.connect(accounts_db.DB_PATH) as live:
        assert live.execute("SELECT dek FROM brokerage_users WHERE user_id = ?", (uid,)).fetchone()[0] == b"\x01\x02", \
            "the live key is untouched"


def test_a_damaged_snapshot_fails_the_check(tmp_path):
    bad = tmp_path / "accounts-20261026T000000Z.db"
    bad.write_bytes(b"SQLite format 3\x00" + b"\x00" * 200)
    got = snapshots.verify_restore(str(bad))
    assert got["ok"] is False and got["restored_to"] is None
