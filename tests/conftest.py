"""Shared fixtures.

**Nothing in the suite may touch `data/`.** That directory is the real ledger,
the real alert inbox and, now, the real accounts database. The session fixture
below points the accounts path at a temporary directory for the whole run, which
it has to do because `/api/chat` reads the daily assistant allowance out of that
database — so `tests/test_spend_guard.py` was writing rows into `data/accounts.db`
until this existed.

`app/db.py` reads `DB_PATH` inside `_connect()` rather than caching a
connection, so patching the module global is enough and no import ordering has
to be arranged.
"""

from __future__ import annotations

import pytest

from app import db as accounts_db


@pytest.fixture(scope="session", autouse=True)
def _accounts_db_out_of_the_way(tmp_path_factory):
    """One migrated accounts database for the whole session.

    Session-scoped so the migration runs once rather than nine hundred times.
    `monkeypatch` is function-scoped and cannot be used here, hence the manual
    context."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(accounts_db, "DB_PATH",
                      str(tmp_path_factory.mktemp("accounts") / "accounts.db"))
        accounts_db.migrate()
        yield


@pytest.fixture
def accounts(tmp_path, monkeypatch):
    """A migrated, *empty* accounts database for one test.

    Per-test rather than leaning on the session one: these tests count rows and
    assert on totals, and a shared database makes every one of those assertions
    depend on what ran before it."""
    monkeypatch.setattr(accounts_db, "DB_PATH", str(tmp_path / "accounts.db"))
    accounts_db.migrate()
    return accounts_db
