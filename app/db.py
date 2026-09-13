"""The accounts database: connection, schema and forward-only migrations.

**Why SQLite.** The ledger (`app/paper.py`) and the alert inbox (`app/alerts.py`)
are already SQLite on the Railway volume mounted at `/app/data`, and the service
runs one uvicorn worker on purpose (see the Dockerfile). One writer, one process,
a disk that survives deploys: that is the shape SQLite is good at. Adding a
Postgres service would mean running two database technologies for one feature.

**Why a separate file from the ledger.** `tracker.db` is the *system's* record —
one shared paper-trading history, identical for every visitor. `accounts.db` is
*people's* data. Different blast radius, different backup story, and a migration
that takes a write lock on one must not stall the other.

**Portability.** Every column type here is TEXT, INTEGER or BLOB; timestamps are
ISO-8601 UTC strings, which sort and compare correctly as text in any engine;
booleans are 0/1; ids are UUID4 strings rather than AUTOINCREMENT. The only
SQLite-specific syntax is `COLLATE NOCASE` on `users.email` and the PRAGMAs. That
is the deliberate cost of the swap to Postgres later: replace `_connect()`, drop
the PRAGMAs, and change one collation to `CITEXT` or a lower(email) index.

**Why `PRAGMA foreign_keys=ON` on every connection.** SQLite ships foreign-key
enforcement *off* for backwards compatibility, and it is a per-connection
setting, not a property of the file. Without it every `ON DELETE CASCADE` in the
schema below is decoration: deleting a user would leave their sessions behind,
and an orphaned session row still authenticates. That is the difference between
"delete my account" working and appearing to work.

**Migrations are forward-only and numbered.** `schema_migrations` records what
has been applied, so a fresh checkout, a staging box and production converge on
the same schema by running the same list. There is no down-migration: rolling a
schema backwards on live account data is not a thing you want to be one command
away from.
"""

from __future__ import annotations

import contextlib
import logging
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

log = logging.getLogger("optic.db")

# Same directory as the ledger, so one volume mount covers everything that must
# survive a deploy. TRACKER_DATA_DIR is set in the Dockerfile.
DATA_DIR = os.environ.get("TRACKER_DATA_DIR", "data")
DB_PATH = os.environ.get("ACCOUNTS_DB_PATH") or os.path.join(DATA_DIR, "accounts.db")

# Serialises writers in this process. SQLite handles concurrent readers under WAL
# by itself; what it does badly is two writers racing for the same lock, which
# surfaces as an intermittent "database is locked" under load rather than as a
# clean error at development time.
_LOCK = threading.RLock()


def utcnow() -> str:
    """The one timestamp format the schema stores: ISO-8601, UTC, second
    resolution, always suffixed Z. Comparable with `<` as plain text."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def in_seconds(seconds: int) -> str:
    """A future timestamp in the same format, for expiry columns."""
    return (datetime.now(timezone.utc)
            + timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_id() -> str:
    """A primary key. UUID4 rather than a counter: ids appear in URLs and in API
    responses, and a sequential id tells anyone who sees one how many accounts
    exist and lets them guess the neighbours."""
    return str(uuid.uuid4())


def _connect() -> sqlite3.Connection:
    directory = os.path.dirname(DB_PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")      # see the module docstring
    conn.execute("PRAGMA busy_timeout=15000")
    return conn


@contextlib.contextmanager
def cursor(write: bool = False):
    """A connection that is always closed, and a transaction that is always
    resolved.

    `with sqlite3.connect(...)` is a *transaction* context manager, not a closing
    one — it commits or rolls back and leaves the connection open, so a
    per-request connection leaks a file handle until the garbage collector gets
    to it. Reads are wrapped too, because under WAL a read holds a snapshot and
    an unclosed reader pins WAL frames that can then never be checkpointed.
    """
    if write:
        with _LOCK:
            conn = _connect()
            with contextlib.closing(conn):
                with conn:                      # commit on success, roll back on raise
                    yield conn
    else:
        conn = _connect()
        with contextlib.closing(conn):
            yield conn


def rows(sql: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
    with cursor() as conn:
        return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]


def row(sql: str, params: Sequence[Any] = ()) -> Optional[Dict[str, Any]]:
    with cursor() as conn:
        found = conn.execute(sql, tuple(params)).fetchone()
        return dict(found) if found else None


def execute(sql: str, params: Sequence[Any] = ()) -> int:
    with cursor(write=True) as conn:
        cur = conn.execute(sql, tuple(params))
        return cur.rowcount


def execute_many(statements: Iterable[Tuple[str, Sequence[Any]]]) -> None:
    """Several statements, one transaction. Used where a half-applied change
    would be worse than no change — creating a user and their login identity, or
    consuming a reset token and rotating the password."""
    with cursor(write=True) as conn:
        for sql, params in statements:
            conn.execute(sql, tuple(params))


# --------------------------------------------------------------- the schema
#
# Each migration is a list of individual statements rather than one script.
# `executescript()` issues an implicit COMMIT before it runs, which would take
# the version bookkeeping outside the transaction that applies the change — so a
# crash mid-migration could leave tables created and the version unrecorded, and
# the next boot would then fail on "table already exists".

MIGRATION_1 = [
    # -------------------------------------------------------------- identity
    #
    # The Optic account. Deliberately *not* keyed on any provider's user id:
    # a Google `sub` or an Apple `sub` identifies a Google or Apple user, and
    # this row has to survive a reader dropping either one.
    """
    CREATE TABLE IF NOT EXISTS users (
        id             TEXT PRIMARY KEY,
        email          TEXT NOT NULL COLLATE NOCASE,
        first_name     TEXT NOT NULL DEFAULT '',
        last_name      TEXT NOT NULL DEFAULT '',
        avatar_url     TEXT,
        email_verified INTEGER NOT NULL DEFAULT 0,
        is_active      INTEGER NOT NULL DEFAULT 1,
        created_at     TEXT NOT NULL,
        updated_at     TEXT NOT NULL,
        last_login_at  TEXT
    )
    """,
    # UNIQUE and the lookup index in one. NOCASE because Alex@x.com and
    # alex@x.com are one mailbox everywhere that matters, and two rows would be
    # two accounts that can never be merged.
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email COLLATE NOCASE)",

    # How a person proves they are that user. One row per method.
    #
    # The UNIQUE(provider, provider_user_id) is the whole account-linking model:
    # it makes "this Google account already belongs to somebody" a constraint
    # violation rather than a race between two concurrent callbacks.
    """
    CREATE TABLE IF NOT EXISTS auth_identities (
        id               TEXT PRIMARY KEY,
        user_id          TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        provider         TEXT NOT NULL,
        provider_user_id TEXT NOT NULL,
        provider_email   TEXT,
        created_at       TEXT NOT NULL,
        updated_at       TEXT NOT NULL
    )
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_identity_provider "
    "ON auth_identities(provider, provider_user_id)",
    "CREATE INDEX IF NOT EXISTS idx_identity_user ON auth_identities(user_id)",
    # One password per user at most, in its own table rather than a nullable
    # column on users or on auth_identities. Two reasons: a SELECT * on users
    # then cannot leak a hash into a response by accident, and rotating a
    # password touches one row that holds nothing else.
    """
    CREATE TABLE IF NOT EXISTS user_passwords (
        user_id       TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
        password_hash TEXT NOT NULL,
        algo          TEXT NOT NULL,
        updated_at    TEXT NOT NULL
    )
    """,

    # --------------------------------------------------------------- sessions
    #
    # Only the hash is stored. A stolen database backup then contains no usable
    # session tokens, which is the same argument as not storing passwords.
    """
    CREATE TABLE IF NOT EXISTS sessions (
        id                 TEXT PRIMARY KEY,
        user_id            TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        session_token_hash TEXT NOT NULL,
        expires_at         TEXT NOT NULL,
        created_at         TEXT NOT NULL,
        last_used_at       TEXT NOT NULL,
        ip_address         TEXT,
        user_agent         TEXT
    )
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_sessions_hash ON sessions(session_token_hash)",
    "CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires_at)",

    # ---------------------------------------------------- one-time email links
    """
    CREATE TABLE IF NOT EXISTS password_resets (
        id         TEXT PRIMARY KEY,
        user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        token_hash TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        used_at    TEXT,
        created_at TEXT NOT NULL
    )
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_reset_hash ON password_resets(token_hash)",
    "CREATE INDEX IF NOT EXISTS idx_reset_user ON password_resets(user_id)",
    """
    CREATE TABLE IF NOT EXISTS email_verifications (
        id          TEXT PRIMARY KEY,
        user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        token_hash  TEXT NOT NULL,
        expires_at  TEXT NOT NULL,
        verified_at TEXT,
        created_at  TEXT NOT NULL
    )
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_verify_hash ON email_verifications(token_hash)",
    "CREATE INDEX IF NOT EXISTS idx_verify_user ON email_verifications(user_id)",

    # --------------------------------------------------------------- passkeys
    #
    # public_key is the COSE-encoded public key as the authenticator produced it,
    # stored as a BLOB and handed back to the WebAuthn library verbatim. Nothing
    # secret is here: the private key never leaves the device, which is the
    # entire point of the mechanism.
    """
    CREATE TABLE IF NOT EXISTS passkeys (
        id            TEXT PRIMARY KEY,
        user_id       TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        credential_id TEXT NOT NULL,
        public_key    BLOB NOT NULL,
        counter       INTEGER NOT NULL DEFAULT 0,
        device_type   TEXT,
        backed_up     INTEGER NOT NULL DEFAULT 0,
        transports    TEXT,
        name          TEXT NOT NULL DEFAULT 'Passkey',
        created_at    TEXT NOT NULL,
        last_used_at  TEXT
    )
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_passkey_cred ON passkeys(credential_id)",
    "CREATE INDEX IF NOT EXISTS idx_passkey_user ON passkeys(user_id)",
    # Challenges have to be server-issued and single-use or the whole ceremony is
    # replayable: an attacker who captured one signed assertion could present it
    # again. Rows are deleted on use, and expired ones swept on issue.
    """
    CREATE TABLE IF NOT EXISTS webauthn_challenges (
        id         TEXT PRIMARY KEY,
        challenge  TEXT NOT NULL,
        kind       TEXT NOT NULL,
        user_id    TEXT,
        expires_at TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_challenge ON webauthn_challenges(challenge)",

    # ------------------------------------------------------------ oauth state
    #
    # state and nonce live server-side rather than in a signed cookie, so a
    # callback can be validated without trusting anything the browser carried.
    # `link_user_id` is set when an already-signed-in reader is attaching a
    # provider, which is what stops a callback from silently creating a second
    # account for the same person.
    """
    CREATE TABLE IF NOT EXISTS oauth_states (
        state        TEXT PRIMARY KEY,
        provider     TEXT NOT NULL,
        nonce        TEXT NOT NULL,
        redirect_to  TEXT,
        link_user_id TEXT,
        expires_at   TEXT NOT NULL,
        created_at   TEXT NOT NULL
    )
    """,

    # ------------------------------------------------------- what a user owns
    """
    CREATE TABLE IF NOT EXISTS watchlists (
        id         TEXT PRIMARY KEY,
        user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        name       TEXT NOT NULL,
        position   INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_watchlists_user ON watchlists(user_id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_watchlists_name "
    "ON watchlists(user_id, name COLLATE NOCASE)",
    """
    CREATE TABLE IF NOT EXISTS watchlist_items (
        id           TEXT PRIMARY KEY,
        watchlist_id TEXT NOT NULL REFERENCES watchlists(id) ON DELETE CASCADE,
        symbol       TEXT NOT NULL,
        asset_type   TEXT NOT NULL DEFAULT 'equity',
        position     INTEGER NOT NULL DEFAULT 0,
        created_at   TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_items_list ON watchlist_items(watchlist_id)",
    # The same symbol twice in one list is a bug, not a preference.
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_items_symbol "
    "ON watchlist_items(watchlist_id, symbol)",
    """
    CREATE TABLE IF NOT EXISTS saved_research (
        id            TEXT PRIMARY KEY,
        user_id       TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        title         TEXT NOT NULL,
        symbol        TEXT,
        content       TEXT NOT NULL,
        research_type TEXT NOT NULL DEFAULT 'note',
        created_at    TEXT NOT NULL,
        updated_at    TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_research_user ON saved_research(user_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_research_symbol ON saved_research(symbol)",
    """
    CREATE TABLE IF NOT EXISTS user_preferences (
        user_id         TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
        time_zone       TEXT NOT NULL DEFAULT 'auto',
        default_market  TEXT NOT NULL DEFAULT 'US',
        default_landing TEXT NOT NULL DEFAULT 'home',
        updated_at      TEXT NOT NULL
    )
    """,
    # No payment code exists yet and none is implied by this table. It is here so
    # that the day a plan matters, "which plan is this user on" is a column and
    # not a schema change under live accounts.
    """
    CREATE TABLE IF NOT EXISTS subscriptions (
        id                       TEXT PRIMARY KEY,
        user_id                  TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        plan                     TEXT NOT NULL DEFAULT 'free',
        status                   TEXT NOT NULL DEFAULT 'active',
        provider                 TEXT,
        provider_customer_id     TEXT,
        provider_subscription_id TEXT,
        current_period_start     TEXT,
        current_period_end       TEXT,
        created_at               TEXT NOT NULL,
        updated_at               TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_subs_user ON subscriptions(user_id)",

    # -------------------------------------------------------- rate limiting
    #
    # In the database rather than in a dict, because this process is restarted
    # periodically and not always on purpose: DEPLOY.md records the service being
    # OOM-killed during scans. An in-memory attempt counter is reset by exactly
    # the event an attacker does not have to cause, and a login throttle that
    # forgets every few hours is not a throttle.
    """
    CREATE TABLE IF NOT EXISTS auth_attempts (
        id         TEXT PRIMARY KEY,
        bucket     TEXT NOT NULL,
        kind       TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_attempts ON auth_attempts(kind, bucket, created_at)",
]

# PKCE. OAuth 2.1 requires the code challenge for every client, including
# confidential ones like this server: the code is handed back through the
# browser, and PKCE is what binds the code to the session that asked for it
# rather than to whoever presents it. Added as a second migration rather than
# folded into the first so that a database created by the previous build
# upgrades in place, which is the whole reason the runner exists.
MIGRATION_2 = [
    "ALTER TABLE oauth_states ADD COLUMN code_verifier TEXT",
]

# User-defined watches. The evaluator in `app/analytics/watches.py` was written
# stateless because there was nobody to own a row; now there is, so a watch can
# outlive the browser it was created in. Guests keep theirs in localStorage, the
# same split as the watchlist and saved research.
#
# `last_met_at` and `last_evidence` are the reason this is a table rather than a
# list of conditions. Without them a watch that has tripped trips again on every
# check, so every page load reports the same news — which is how a notification
# feature becomes something people switch off.
MIGRATION_3 = [
    """
    CREATE TABLE IF NOT EXISTS watches (
        id            TEXT PRIMARY KEY,
        user_id       TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        symbol        TEXT NOT NULL,
        kind          TEXT NOT NULL,
        params        TEXT NOT NULL DEFAULT '{}',
        note          TEXT,
        active        INTEGER NOT NULL DEFAULT 1,
        created_at    TEXT NOT NULL,
        last_met_at   TEXT,
        last_evidence TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_watches_user ON watches(user_id, symbol)",
    # The same condition twice on the same symbol with the same parameters is a
    # duplicate, not a preference. Params are compared as their stored JSON,
    # which is why store.py serialises them with sorted keys.
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_watches_unique "
    "ON watches(user_id, symbol, kind, params)",
]

# Watches that fired, waiting for the reader.
#
# A watch used to be checked only while the page was open and on whatever symbol
# happened to be on screen, which meant the one thing anybody wants from an
# alert — being told about a move you were not watching — was the one thing it
# could not do. The runner evaluates stored watches server-side and writes the
# hits here, so they are waiting at the next sign-in.
#
# Still not a push. Nothing here can send to a device or a mailbox, and an alert
# that silently misses its move is worse than none, so what this promises is
# precisely "it will be here when you come back" and the copy says so.
#
# One hit per watch per UTC day, enforced by the unique index rather than by the
# caller remembering. Almost every condition reports a STATE rather than a
# transition: "RSI above 50" is true for as long as it is true, so a runner on a
# fifteen-minute loop would write the same news ninety-six times, and an inbox
# like that is one nobody opens twice.
MIGRATION_4 = [
    """
    CREATE TABLE IF NOT EXISTS watch_hits (
        id          TEXT PRIMARY KEY,
        user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        watch_id    TEXT NOT NULL REFERENCES watches(id) ON DELETE CASCADE,
        symbol      TEXT NOT NULL,
        kind        TEXT NOT NULL,
        title       TEXT NOT NULL,
        body        TEXT,
        created_at  TEXT NOT NULL,
        seen        INTEGER NOT NULL DEFAULT 0,
        dedupe_key  TEXT NOT NULL
    )
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_watch_hits_dedupe "
    "ON watch_hits(user_id, dedupe_key)",
    "CREATE INDEX IF NOT EXISTS idx_watch_hits_user "
    "ON watch_hits(user_id, created_at DESC)",
]

MIGRATIONS: List[Tuple[int, str, List[str]]] = [
    (1, "accounts", MIGRATION_1),
    (2, "oauth_pkce", MIGRATION_2),
    (3, "watches", MIGRATION_3),
    (4, "watch_hits", MIGRATION_4),
]


def applied() -> List[int]:
    with cursor(write=True) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)")
        return [r[0] for r in conn.execute(
            "SELECT version FROM schema_migrations ORDER BY version")]


def migrate() -> List[int]:
    """Apply every migration not yet recorded. Idempotent; safe on every boot.

    Returns the versions applied by this call, so a caller can log the
    difference rather than logging "migrated" on a no-op."""
    done = set(applied())
    ran: List[int] = []
    for version, name, statements in MIGRATIONS:
        if version in done:
            continue
        with cursor(write=True) as conn:
            for sql in statements:
                conn.execute(sql)
            conn.execute(
                "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?,?,?)",
                (version, name, utcnow()))
        ran.append(version)
        log.info("accounts db: applied migration %s (%s)", version, name)
    return ran


def sweep() -> Dict[str, int]:
    """Delete what has expired. Called from the tracker loop, which is the one
    thing in this app that already wakes up on a timer.

    Expired rows are not merely untidy: an expired session row that is never
    deleted is a row that only a correct expiry check stands between and a valid
    login, and there is no reason to keep depending on that check."""
    now = utcnow()
    counts: Dict[str, int] = {}
    with cursor(write=True) as conn:
        for table, column in (("sessions", "expires_at"),
                              ("password_resets", "expires_at"),
                              ("email_verifications", "expires_at"),
                              ("webauthn_challenges", "expires_at"),
                              ("oauth_states", "expires_at")):
            cur = conn.execute(
                "DELETE FROM {} WHERE {} < ?".format(table, column), (now,))
            counts[table] = cur.rowcount or 0
        # Attempts older than a day can no longer affect any window.
        cur = conn.execute("DELETE FROM auth_attempts WHERE created_at < ?",
                           (in_seconds(-86400),))
        counts["auth_attempts"] = cur.rowcount or 0
    return counts


if __name__ == "__main__":                      # python -m app.db migrate
    import sys
    logging.basicConfig(level=logging.INFO)
    command = sys.argv[1] if len(sys.argv) > 1 else "migrate"
    if command == "migrate":
        ran = migrate()
        print("up to date" if not ran else "applied: {}".format(ran))
        print("database: {}".format(DB_PATH))
    elif command == "sweep":
        print(sweep())
    elif command == "status":
        print("database: {}".format(DB_PATH))
        print("applied:  {}".format(applied()))
        print("known:    {}".format([m[0] for m in MIGRATIONS]))
    else:
        print("usage: python -m app.db [migrate|sweep|status]")
        raise SystemExit(2)
