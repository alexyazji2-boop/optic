"""Every SQL statement that touches brokerage data.

Same two rules as `app/auth/store.py`: bound parameters only, and `user_id` is
an argument that goes into every WHERE clause. A connection or account id from
the browser never decides on its own what is read; `connection(user_id, id)`
returns None for another reader's row, which is the same answer as a row that
does not exist.

Holdings live only inside sealed payloads (see `app/vault.py`). The associated
data for an account payload is `acct:<user_id>:<account_id>`, so a blob moved to
another row does not open.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .. import db, vault
from ..auth import tokens

# ------------------------------------------------------------------ the link
#
# One provider-side user per Optic user. Its id is random, not the Optic user
# id, so the aggregator never learns Optic's identifiers and a purge record that
# outlives the account cannot be tied back to it.


def link(user_id: str) -> Optional[Dict[str, Any]]:
    return db.row("SELECT * FROM brokerage_users WHERE user_id = ?", (user_id,))


def create_link(user_id: str, provider: str, provider_user_id: str, secret: str) -> Dict[str, Any]:
    wrapped = vault.new_wrapped_dek(user_id)
    dek = vault.unwrap_dek(user_id, wrapped)
    sealed = vault.seal(dek, secret, "secret:" + user_id)
    db.execute("INSERT INTO brokerage_users (user_id, provider, provider_user_id, secret, dek, created_at) "
               "VALUES (?,?,?,?,?,?)",
               (user_id, provider, provider_user_id, sealed, wrapped, db.utcnow()))
    found = link(user_id)
    assert found is not None
    return found


def dek(user_id: str, row: Optional[Dict[str, Any]] = None) -> Optional[bytes]:
    row = row or link(user_id)
    if not row:
        return None
    return vault.unwrap_dek(user_id, row["dek"])


def secret(user_id: str, row: Dict[str, Any]) -> str:
    key = vault.unwrap_dek(user_id, row["dek"])
    return vault.open_(key, row["secret"], "secret:" + user_id) if row.get("secret") else ""


# ------------------------------------------------------------- connections


def connections(user_id: str) -> List[Dict[str, Any]]:
    return db.rows("SELECT * FROM brokerage_connections WHERE user_id = ? ORDER BY created_at",
                   (user_id,))


def connection(user_id: str, connection_id: str) -> Optional[Dict[str, Any]]:
    return db.row("SELECT * FROM brokerage_connections WHERE id = ? AND user_id = ?",
                  (connection_id, user_id))


def connection_by_provider_id(user_id: str, provider: str, provider_connection_id: str):
    return db.row("SELECT * FROM brokerage_connections WHERE user_id = ? AND provider = ? "
                  "AND provider_connection_id = ?", (user_id, provider, provider_connection_id))


def upsert_connection(user_id: str, provider: str, provider_connection_id: str,
                      institution: str, status: str, reason: Optional[str] = None) -> Dict[str, Any]:
    now = db.utcnow()
    db.execute(
        "INSERT INTO brokerage_connections (id, user_id, provider, provider_connection_id, institution, "
        "status, status_reason, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(user_id, provider, provider_connection_id) DO UPDATE SET "
        "institution = excluded.institution, status = excluded.status, "
        "status_reason = excluded.status_reason, updated_at = excluded.updated_at",
        (db.new_id(), user_id, provider, provider_connection_id, institution, status, reason, now, now))
    found = connection_by_provider_id(user_id, provider, provider_connection_id)
    assert found is not None
    return found


def set_connection(user_id: str, connection_id: str, **fields: Any) -> None:
    allowed = {"status", "status_reason", "last_sync_at", "last_attempt_at", "institution"}
    sets = {k: v for k, v in fields.items() if k in allowed}
    if not sets:
        return
    cols = ", ".join("{} = ?".format(k) for k in sets)
    db.execute("UPDATE brokerage_connections SET {}, updated_at = ? WHERE id = ? AND user_id = ?".format(cols),
               tuple(sets.values()) + (db.utcnow(), connection_id, user_id))


def delete_connection(user_id: str, connection_id: str) -> None:
    # Accounts cascade. The snapshot history is rebuilt from what remains on
    # the next sync rather than edited, so it is cleared with the last
    # connection (see purge_local).
    db.execute("DELETE FROM brokerage_connections WHERE id = ? AND user_id = ?", (connection_id, user_id))


# ----------------------------------------------------------------- accounts


def accounts(user_id: str, connection_id: Optional[str] = None) -> List[Dict[str, Any]]:
    if connection_id:
        return db.rows("SELECT * FROM brokerage_accounts WHERE user_id = ? AND connection_id = ? "
                       "ORDER BY created_at", (user_id, connection_id))
    return db.rows("SELECT * FROM brokerage_accounts WHERE user_id = ? ORDER BY created_at", (user_id,))


def account(user_id: str, account_id: str) -> Optional[Dict[str, Any]]:
    return db.row("SELECT * FROM brokerage_accounts WHERE id = ? AND user_id = ?", (account_id, user_id))


def upsert_account(user_id: str, connection_id: str, provider: str, provider_account_id: str,
                   name: str, number_mask: str, institution: str, account_type: Optional[str],
                   currency: Optional[str]) -> Dict[str, Any]:
    """Keyed on (user, provider, provider account id). If the same account is
    reached through a second connection, the row moves to that connection
    instead of being duplicated: one account, counted once."""
    now = db.utcnow()
    db.execute(
        "INSERT INTO brokerage_accounts (id, user_id, connection_id, provider, provider_account_id, name, "
        "number_mask, institution, account_type, currency, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(user_id, provider, provider_account_id) DO UPDATE SET "
        "connection_id = excluded.connection_id, name = excluded.name, number_mask = excluded.number_mask, "
        "institution = excluded.institution, account_type = excluded.account_type, "
        "currency = excluded.currency, updated_at = excluded.updated_at",
        (db.new_id(), user_id, connection_id, provider, provider_account_id, name, number_mask,
         institution, account_type, currency, now, now))
    found = db.row("SELECT * FROM brokerage_accounts WHERE user_id = ? AND provider = ? AND "
                   "provider_account_id = ?", (user_id, provider, provider_account_id))
    assert found is not None
    return found


def set_account_selected(user_id: str, account_id: str, selected: bool) -> bool:
    return db.execute("UPDATE brokerage_accounts SET selected = ?, updated_at = ? WHERE id = ? AND user_id = ?",
                      (1 if selected else 0, db.utcnow(), account_id, user_id)) > 0


def save_payload(user_id: str, account_id: str, payload: Dict[str, Any], state: str,
                 note: Optional[str], broker_as_of: Optional[str]) -> None:
    key = dek(user_id)
    if key is None:
        raise vault.VaultUnavailable("no data key for this user")
    sealed = vault.seal(key, json.dumps(payload, default=str), "acct:{}:{}".format(user_id, account_id))
    now = db.utcnow()
    db.execute("UPDATE brokerage_accounts SET payload = ?, sync_state = ?, sync_note = ?, last_sync_at = ?, "
               "broker_as_of = ?, updated_at = ? WHERE id = ? AND user_id = ?",
               (sealed, state, note, now, broker_as_of, now, account_id, user_id))


def set_account_state(user_id: str, account_id: str, state: str, note: Optional[str]) -> None:
    db.execute("UPDATE brokerage_accounts SET sync_state = ?, sync_note = ?, updated_at = ? "
               "WHERE id = ? AND user_id = ?", (state, note, db.utcnow(), account_id, user_id))


def payload(user_id: str, row: Dict[str, Any], key: Optional[bytes] = None) -> Optional[Dict[str, Any]]:
    if not row.get("payload"):
        return None
    key = key or dek(user_id)
    if key is None:
        return None
    return json.loads(vault.open_(key, row["payload"], "acct:{}:{}".format(user_id, row["id"])))


# ---------------------------------------------------------------- snapshots

SNAPSHOTS_KEPT = 30


def add_snapshot(user_id: str, summary: Dict[str, Any]) -> None:
    key = dek(user_id)
    if key is None:
        return
    sid = db.new_id()
    sealed = vault.seal(key, json.dumps(summary, default=str), "snap:{}:{}".format(user_id, sid))
    db.execute_many([
        ("INSERT INTO brokerage_snapshots (id, user_id, taken_at, payload) VALUES (?,?,?,?)",
         (sid, user_id, summary.get("taken_at") or db.utcnow(), sealed)),
        ("DELETE FROM brokerage_snapshots WHERE user_id = ? AND id NOT IN (SELECT id FROM "
         "brokerage_snapshots WHERE user_id = ? ORDER BY taken_at DESC LIMIT ?)",
         (user_id, user_id, SNAPSHOTS_KEPT)),
    ])


def recent_snapshots(user_id: str, limit: int = 2) -> List[Dict[str, Any]]:
    key = dek(user_id)
    if key is None:
        return []
    out = []
    for r in db.rows("SELECT * FROM brokerage_snapshots WHERE user_id = ? ORDER BY taken_at DESC, rowid DESC "
                     "LIMIT ?", (user_id, limit)):
        try:
            out.append(json.loads(vault.open_(key, r["payload"], "snap:{}:{}".format(user_id, r["id"]))))
        except Exception:                                       # noqa: BLE001
            continue
    return out


# ------------------------------------------------------------ link states
#
# The hosted portal sends the browser back to /api/brokerage/callback. The
# state token proves the callback finishes a link this signed-in reader
# started, within ten minutes, once.

LINK_STATE_TTL = 600


def new_link_state(user_id: str, reconnect_id: Optional[str], known_ids: List[str]) -> str:
    """`known_ids` is every connection the provider already had for this
    reader when the link started. The callback imports only something new
    since then (or the connection being repaired), so a portal link handed to
    someone else cannot later be swept in by an unrelated callback."""
    token = tokens.new_token()
    db.execute("INSERT INTO brokerage_link_states (token_hash, user_id, reconnect_id, known_ids, expires_at) "
               "VALUES (?,?,?,?,?)", (tokens.token_hash(token), user_id, reconnect_id,
                                      json.dumps(sorted(known_ids)), db.in_seconds(LINK_STATE_TTL)))
    return token


def take_link_state(token: str) -> Optional[Dict[str, Any]]:
    if not token:
        return None
    hashed = tokens.token_hash(token)
    found = db.row("SELECT * FROM brokerage_link_states WHERE token_hash = ?", (hashed,))
    # Single use: whichever request deletes the row is the one that finishes.
    taken = db.execute("DELETE FROM brokerage_link_states WHERE token_hash = ?", (hashed,))
    if not found or not taken or found["expires_at"] < db.utcnow():
        return None
    return found


# ------------------------------------------------------------------- purges


def purge_local(user_id: str) -> Optional[Dict[str, Any]]:
    """Delete everything Optic holds about this reader's brokerage link and
    return the provider-side ids still to be deleted there.

    Dropping `brokerage_users` drops the wrapped data key, which is what makes
    any copy of the sealed payloads in a backup unreadable."""
    row = link(user_id)
    db.execute_many([
        ("DELETE FROM brokerage_snapshots WHERE user_id = ?", (user_id,)),
        ("DELETE FROM brokerage_connections WHERE user_id = ?", (user_id,)),
        ("DELETE FROM brokerage_link_states WHERE user_id = ?", (user_id,)),
        ("DELETE FROM brokerage_users WHERE user_id = ?", (user_id,)),
    ])
    return row


def queue_purge(provider: str, provider_user_id: str, provider_connection_id: Optional[str],
                error: str) -> None:
    db.execute("INSERT INTO brokerage_purges (id, provider, provider_user_id, provider_connection_id, "
               "attempts, last_error, created_at) VALUES (?,?,?,?,1,?,?)",
               (db.new_id(), provider, provider_user_id, provider_connection_id, error[:300], db.utcnow()))


PURGE_MAX_ATTEMPTS = 12


def pending_purges(limit: int = 20) -> List[Dict[str, Any]]:
    """Fewest attempts first, so one deletion that keeps failing cannot starve
    the rest; after PURGE_MAX_ATTEMPTS a row stops being retried and is left
    for the operator (logged by the caller)."""
    return db.rows("SELECT * FROM brokerage_purges WHERE attempts < ? ORDER BY attempts, created_at LIMIT ?",
                   (PURGE_MAX_ATTEMPTS, limit))


def purge_done(purge_id: str) -> None:
    db.execute("DELETE FROM brokerage_purges WHERE id = ?", (purge_id,))


def purge_failed(purge_id: str, error: str) -> None:
    db.execute("UPDATE brokerage_purges SET attempts = attempts + 1, last_error = ? WHERE id = ?",
               (error[:300], purge_id))


# ----------------------------------------------------------------- consent


def has_consent(user_id: str, version: str) -> bool:
    return bool(db.row("SELECT 1 FROM brokerage_consents WHERE user_id = ? AND terms_version = ?",
                       (user_id, version)))


def record_consent(user_id: str, version: str, ip_hash: Optional[str]) -> None:
    if has_consent(user_id, version):
        return
    db.execute("INSERT INTO brokerage_consents (id, user_id, terms_version, accepted_at, ip_hash) "
               "VALUES (?,?,?,?,?)", (db.new_id(), user_id, version, db.utcnow(), ip_hash))


def consent_row(user_id: str, version: str) -> Optional[Dict[str, Any]]:
    return db.row("SELECT terms_version, accepted_at FROM brokerage_consents WHERE user_id = ? AND "
                  "terms_version = ?", (user_id, version))


# ----------------------------------------------------------------- webhooks


def first_delivery(provider: str, event_id: str, event_type: str) -> bool:
    """True the first time an event id is seen, False on every redelivery.

    The INSERT is the check: two deliveries racing each other cannot both
    succeed against the primary key, which a read-then-write could."""
    import sqlite3
    try:
        db.execute("INSERT INTO webhook_events (id, provider, event_type, received_at) VALUES (?,?,?,?)",
                   ("{}:{}".format(provider, event_id), provider, event_type, db.utcnow()))
        return True
    except sqlite3.IntegrityError:
        return False


def forget_delivery(provider: str, event_id: str) -> None:
    """A handler that failed un-records the event so the provider's retry is
    processed rather than acknowledged as a duplicate."""
    db.execute("DELETE FROM webhook_events WHERE id = ?", ("{}:{}".format(provider, event_id),))
