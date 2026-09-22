"""Shared fixtures.

**Nothing in the suite may touch `data/`.** That directory is the real ledger,
the real alert inbox and the real accounts database. The session fixture below
points all three at a temporary directory for the whole run.

Only the accounts path was redirected before this, and the rule was kept by
remembering: four test files redirect `alerts.DB_PATH` themselves and the rest
do not. The other two are redirected here so it is kept by construction
instead.

Neither of the two additions was chasing an observed write. Hashing `data/*.db`
either side of a full run showed `alerts.db` changing, and a first reading of
that blamed the suite — wrongly. Wrapping `sqlite3.connect` and printing a
stack for any open of the real path found zero during a full run, and hashing
across 120 seconds with no pytest running at all showed the same file changing
anyway. In this working directory that writer is the dev server, not pytest.

One loose end, recorded rather than guessed at: in a clean checkout with no
dev server running, a full run still ends with a `data/alerts.db` on disk,
while the same `sqlite3.connect` trace reports zero opens of it. No test
spawns a Python subprocess, so that is not the explanation either, and the
writer is unidentified. It predates this fixture -- a worktree at origin/main
produces the same file -- so the redirect below is prophylactic and is not
claimed to stop it.

`tracker.db` is the one that needed something done. The tests that reach the
ledger only read from it, and `init_db` is `CREATE TABLE IF NOT EXISTS`, so
nothing was ever written to a file that already had the schema — which is
exactly why a clean checkout broke:
`tests/test_books.py::test_capacity_is_per_book` runs at line 52 and queries
`positions`, and the first test to call `paper.init_db()` is at line 111. With
no `data/tracker.db` to inherit, the first run of the suite failed with
`sqlite3.OperationalError: no such table: positions` and every run after it
passed, because the first run had left the file behind.

So the fixture creates the schema as well as moving it. That is what
`app/main.py` does at startup — the tests import `paper` and call its
internals directly, so they were the only caller skipping the step production
always takes.

Every one of these modules reads `DB_PATH` inside its connect function rather
than caching a connection, so patching the module global is enough and no
import ordering has to be arranged.
"""

from __future__ import annotations

import pytest

from app import alerts as alert_inbox
from app import db as accounts_db
from app import paper


@pytest.fixture(scope="session", autouse=True)
def _real_data_out_of_the_way(tmp_path_factory):
    """Every database the suite can reach, pointed somewhere disposable.

    Session-scoped so each migration runs once rather than nine hundred times.
    `monkeypatch` is function-scoped and cannot be used here, hence the manual
    context.

    All three are in one fixture on purpose. Named separately they drifted:
    accounts was redirected and the other two were not, and nothing said so. A
    fourth database added to `app/` should fail obviously here rather than
    quietly start writing to `data/`.

    Each is migrated as well as moved, because a temporary directory starts
    empty and a test that reads before anything writes finds no schema at all.
    That is the whole of the clean-checkout failure described above."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(accounts_db, "DB_PATH",
                      str(tmp_path_factory.mktemp("accounts") / "accounts.db"))
        accounts_db.migrate()

        patch.setattr(paper, "DB_PATH",
                      str(tmp_path_factory.mktemp("tracker") / "tracker.db"))
        paper.init_db()

        # No init() for this one: every public function in app/alerts.py calls
        # it first, so the inbox creates its own schema on the way in and
        # cannot have the fault the ledger had. Moving it is still worth
        # doing -- four test files redirect it by hand and the rest do not.
        patch.setattr(alert_inbox, "DB_PATH",
                      str(tmp_path_factory.mktemp("alerts") / "alerts.db"))
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
