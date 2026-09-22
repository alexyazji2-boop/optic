"""The suite runs against disposable databases, and creates their schemas.

Two separate claims, and the second is the one that broke.

`tests/test_books.py::test_capacity_is_per_book` calls `paper._capacity`,
which runs `SELECT id FROM positions`. It sits at line 52 of that file; the
first test to call `paper.init_db()` is at line 111. For as long as a
`data/tracker.db` existed from an earlier run the query found a schema and
passed, so the fault was invisible in any working directory that had ever run
the suite.

Measured on a clean checkout -- `git worktree add --detach <tmp> origin/main`
then one `pytest -q`:

    2 failed, 2578 passed      sqlite3.OperationalError: no such table: positions
    (run the same command again in the same worktree)
    2580 passed

The first run had created `data/tracker.db` and the second inherited it. A
fresh CI box or a new contributor's first command hits the red one.

`app/main.py` calls `paper.init_db()` at startup, so production never reaches
a query without a schema. The tests import `paper` and call its internals
directly, which made them the only caller skipping that step. The session
fixture in conftest takes it instead, for every database at once.

These tests are executable rather than source contracts because the bug was
invisible in the source: every line involved was correct, and what was wrong
was the order two of them ran in and a file left over from last time.
"""

from __future__ import annotations

import os

from app import alerts as alert_inbox
from app import db as accounts_db
from app import paper

REPO_DATA = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))


def _under_real_data(path):
    return os.path.abspath(str(path)).startswith(REPO_DATA + os.sep)


def test_no_database_points_at_the_real_data_directory():
    """The rule the conftest docstring has always stated, asserted rather than
    remembered. Before this it was true of accounts and of nothing else."""
    for name, module in (("accounts", accounts_db), ("tracker", paper),
                         ("alerts", alert_inbox)):
        assert not _under_real_data(module.DB_PATH), \
            "{} database points into data/: {}".format(name, module.DB_PATH)


def test_the_ledger_can_be_queried_without_anyone_having_initialised_it():
    """The regression, exactly. This is `_capacity`'s first statement, run
    from a file that never calls `init_db` -- which is the position
    test_books.py was in at line 52.

    It passes trivially once a schema exists anywhere, so it is only
    meaningful on a clean checkout. That is the point: it is the assertion
    that was missing when a clean checkout was the one case nobody ran."""
    rows = paper._rows("SELECT id FROM positions WHERE status='open' LIMIT 1")
    assert isinstance(rows, list)


def test_capacity_works_from_a_cold_start():
    """The failing call itself, not a reconstruction of it."""
    cap = paper._capacity(100000.0, "conservative")
    assert cap["book"] == "conservative"


def test_the_alert_inbox_initialises_itself():
    """Why the fixture moves the inbox but does not migrate it.

    A first version called `alert_inbox.init()` there alongside the other two,
    and the mutation deleting that call failed nothing -- because `recent()`
    already opens with `init()`, as does every other public function in the
    module. The call was dead and the test asserting it could not fail, which
    is worse than no test.

    So the contract is the self-initialisation. This fails if it is ever
    removed, at which point the inbox would need the fixture to compensate the
    way the ledger does."""
    lines = open("app/alerts.py", encoding="utf-8").read().split("\n")
    i = next(n for n, ln in enumerate(lines) if ln.startswith("def recent("))
    # Past the signature, which may wrap, and past a docstring if one appears.
    while not lines[i].rstrip().endswith(":"):
        i += 1
    i += 1
    while not lines[i].strip() or lines[i].strip().startswith("#"):
        i += 1
    assert lines[i].strip() == "init()", (
        "recent() no longer creates its own schema; it opens with "
        "{!r}".format(lines[i].strip()))
    assert isinstance(alert_inbox.recent(limit=1), list)


def test_the_accounts_database_is_migrated():
    """This one was already true. It is here so the three are asserted in one
    place and a fourth database is obviously missing from the list."""
    assert accounts_db.row("SELECT COUNT(*) AS n FROM users")["n"] >= 0
