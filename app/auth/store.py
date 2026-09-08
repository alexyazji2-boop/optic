"""Every SQL statement that touches an account.

One module so that "what can be read and written about a user" is a list you can
read end to end. Two rules hold throughout:

**Parameters, never interpolation.** Every value reaches SQLite as a bound
parameter. There is no f-string containing a caller's input anywhere in this
file; the only formatting is of table names that are literals in this source.

**`user_id` is an argument, never a filter the caller can widen.** Each function
that reads or writes owned data takes the user id and puts it in the WHERE
clause. `research_get(user_id, research_id)` returns None for another user's row
rather than raising — the caller cannot tell "not yours" from "does not exist",
which is the same answer for the same reason as the login form's.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from .. import db
from . import tokens

# ------------------------------------------------------------------- helpers


def normalise_email(email: str) -> str:
    """Lowercased and trimmed. The address is stored in this form and the column
    is COLLATE NOCASE as well, because relying on callers to normalise is how
    two accounts end up with the same mailbox."""
    return (email or "").strip().lower()


def public_user(user: Dict[str, Any]) -> Dict[str, Any]:
    """The user as the browser is allowed to see them.

    An allow-list, not a deny-list: a column added to `users` later is absent
    from the API until someone names it here. The opposite arrangement is how a
    `password_hash` ends up in a JSON response after an unrelated migration."""
    return {
        "id": user["id"],
        "email": user["email"],
        "first_name": user.get("first_name") or "",
        "last_name": user.get("last_name") or "",
        "name": (" ".join(x for x in [user.get("first_name") or "",
                                      user.get("last_name") or ""] if x)).strip(),
        "avatar_url": user.get("avatar_url"),
        "email_verified": bool(user.get("email_verified")),
        "created_at": user.get("created_at"),
        "last_login_at": user.get("last_login_at"),
    }


# --------------------------------------------------------------------- users


def create_user(email: str,
                first_name: str = "",
                last_name: str = "",
                email_verified: bool = False,
                avatar_url: Optional[str] = None) -> Dict[str, Any]:
    """A user, their preference row and their free subscription row, in one
    transaction. Splitting them would allow an account with no preferences, and
    then every read of preferences needs a None branch forever."""
    now = db.utcnow()
    uid = db.new_id()
    db.execute_many([
        ("INSERT INTO users (id,email,first_name,last_name,avatar_url,email_verified,"
         "is_active,created_at,updated_at) VALUES (?,?,?,?,?,?,1,?,?)",
         (uid, normalise_email(email), first_name.strip(), last_name.strip(),
          avatar_url, 1 if email_verified else 0, now, now)),
        ("INSERT INTO user_preferences (user_id,updated_at) VALUES (?,?)", (uid, now)),
        ("INSERT INTO subscriptions (id,user_id,plan,status,created_at,updated_at) "
         "VALUES (?,?,'free','active',?,?)", (db.new_id(), uid, now, now)),
    ])
    created = get_user(uid)
    assert created is not None
    return created


def get_user(user_id: str) -> Optional[Dict[str, Any]]:
    return db.row("SELECT * FROM users WHERE id = ?", (user_id,))


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    return db.row("SELECT * FROM users WHERE email = ? COLLATE NOCASE",
                  (normalise_email(email),))


def update_profile(user_id: str,
                   first_name: Optional[str] = None,
                   last_name: Optional[str] = None,
                   avatar_url: Optional[str] = None) -> Optional[Dict[str, Any]]:
    sets: List[str] = []
    params: List[Any] = []
    if first_name is not None:
        sets.append("first_name = ?")
        params.append(first_name.strip()[:80])
    if last_name is not None:
        sets.append("last_name = ?")
        params.append(last_name.strip()[:80])
    if avatar_url is not None:
        sets.append("avatar_url = ?")
        params.append(avatar_url.strip()[:500] or None)
    if not sets:
        return get_user(user_id)
    sets.append("updated_at = ?")
    params.extend([db.utcnow(), user_id])
    db.execute("UPDATE users SET {} WHERE id = ?".format(", ".join(sets)), params)
    return get_user(user_id)


def mark_verified(user_id: str) -> None:
    db.execute("UPDATE users SET email_verified = 1, updated_at = ? WHERE id = ?",
               (db.utcnow(), user_id))


def touch_login(user_id: str) -> None:
    now = db.utcnow()
    db.execute("UPDATE users SET last_login_at = ?, updated_at = ? WHERE id = ?",
               (now, now, user_id))


def delete_user(user_id: str) -> None:
    """Everything the person owns goes with them, via ON DELETE CASCADE. That
    only works because `app/db.py` turns foreign keys on per connection."""
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))


# ---------------------------------------------------------------- identities


def add_identity(user_id: str,
                 provider: str,
                 provider_user_id: str,
                 provider_email: Optional[str] = None) -> Dict[str, Any]:
    now = db.utcnow()
    db.execute(
        "INSERT INTO auth_identities (id,user_id,provider,provider_user_id,"
        "provider_email,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
        (db.new_id(), user_id, provider, provider_user_id,
         normalise_email(provider_email) if provider_email else None, now, now))
    found = get_identity(provider, provider_user_id)
    assert found is not None
    return found


def get_identity(provider: str, provider_user_id: str) -> Optional[Dict[str, Any]]:
    return db.row("SELECT * FROM auth_identities WHERE provider = ? AND provider_user_id = ?",
                  (provider, provider_user_id))


def identities_for(user_id: str) -> List[Dict[str, Any]]:
    return db.rows("SELECT * FROM auth_identities WHERE user_id = ? ORDER BY created_at",
                   (user_id,))


def remove_identity(user_id: str, provider: str) -> int:
    return db.execute("DELETE FROM auth_identities WHERE user_id = ? AND provider = ?",
                      (user_id, provider))


def touch_identity(identity_id: str, provider_email: Optional[str]) -> None:
    """Apple and Google can both change the address they report. The identity is
    keyed on the provider's stable subject id, so the email is refreshed here as
    a display detail and never used to decide which account this is."""
    db.execute("UPDATE auth_identities SET provider_email = ?, updated_at = ? WHERE id = ?",
               (normalise_email(provider_email) if provider_email else None,
                db.utcnow(), identity_id))


# ----------------------------------------------------------------- passwords


def set_password(user_id: str, password_hash: str, algo: str) -> None:
    now = db.utcnow()
    db.execute(
        "INSERT INTO user_passwords (user_id,password_hash,algo,updated_at) VALUES (?,?,?,?) "
        "ON CONFLICT(user_id) DO UPDATE SET password_hash = excluded.password_hash, "
        "algo = excluded.algo, updated_at = excluded.updated_at",
        (user_id, password_hash, algo, now))


def get_password(user_id: str) -> Optional[Dict[str, Any]]:
    return db.row("SELECT * FROM user_passwords WHERE user_id = ?", (user_id,))


def clear_password(user_id: str) -> None:
    db.execute("DELETE FROM user_passwords WHERE user_id = ?", (user_id,))


# ------------------------------------------------------------------ sessions


def create_session(user_id: str,
                   ttl_seconds: int,
                   ip_address: Optional[str] = None,
                   user_agent: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
    """(token, session row). The token is returned once and never stored; only
    its hash goes to the database."""
    token = tokens.new_token()
    now = db.utcnow()
    sid = db.new_id()
    db.execute(
        "INSERT INTO sessions (id,user_id,session_token_hash,expires_at,created_at,"
        "last_used_at,ip_address,user_agent) VALUES (?,?,?,?,?,?,?,?)",
        (sid, user_id, tokens.token_hash(token), db.in_seconds(ttl_seconds), now, now,
         (ip_address or "")[:64] or None, (user_agent or "")[:300] or None))
    found = db.row("SELECT * FROM sessions WHERE id = ?", (sid,))
    assert found is not None
    return token, found


def session_by_token(token: str) -> Optional[Dict[str, Any]]:
    """The live session for this token, or None.

    Expiry is in the WHERE clause rather than checked afterwards. A caller who
    forgets the check is then unable to authenticate an expired session, instead
    of doing it silently."""
    return db.row(
        "SELECT * FROM sessions WHERE session_token_hash = ? AND expires_at > ?",
        (tokens.token_hash(token), db.utcnow()))


def touch_session(session_id: str, ttl_seconds: int) -> None:
    """Slide the expiry forward on use.

    **Why the token is not rotated per request.** Rotating on every request is
    the stronger-sounding option and it breaks the app: a page that fires three
    requests at once has two of them arrive with a token the first one has
    already replaced, and the reader is signed out by their own parallelism. The
    token is replaced where it actually matters instead — a new session at
    sign-in, and every other session destroyed on a password change."""
    now = db.utcnow()
    db.execute("UPDATE sessions SET last_used_at = ?, expires_at = ? WHERE id = ?",
               (now, db.in_seconds(ttl_seconds), session_id))


def sessions_for(user_id: str) -> List[Dict[str, Any]]:
    return db.rows(
        "SELECT id,created_at,last_used_at,expires_at,ip_address,user_agent "
        "FROM sessions WHERE user_id = ? AND expires_at > ? ORDER BY last_used_at DESC",
        (user_id, db.utcnow()))


def delete_session(session_id: str, user_id: Optional[str] = None) -> int:
    if user_id:
        return db.execute("DELETE FROM sessions WHERE id = ? AND user_id = ?",
                          (session_id, user_id))
    return db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))


def delete_sessions_for(user_id: str, except_session: Optional[str] = None) -> int:
    if except_session:
        return db.execute("DELETE FROM sessions WHERE user_id = ? AND id != ?",
                          (user_id, except_session))
    return db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))


# ------------------------------------------------------- reset / verification


def create_reset(user_id: str, ttl_seconds: int) -> str:
    """Invalidate any outstanding reset before issuing a new one, so asking
    twice does not leave two working links in two inboxes."""
    token = tokens.new_token()
    db.execute_many([
        ("DELETE FROM password_resets WHERE user_id = ? AND used_at IS NULL", (user_id,)),
        ("INSERT INTO password_resets (id,user_id,token_hash,expires_at,created_at) "
         "VALUES (?,?,?,?,?)",
         (db.new_id(), user_id, tokens.token_hash(token), db.in_seconds(ttl_seconds),
          db.utcnow())),
    ])
    return token


def peek_reset(token: str) -> Optional[Dict[str, Any]]:
    return db.row(
        "SELECT * FROM password_resets WHERE token_hash = ? AND used_at IS NULL "
        "AND expires_at > ?", (tokens.token_hash(token), db.utcnow()))


def consume_reset(token: str, new_hash: str, algo: str) -> Optional[str]:
    """Mark the token used and set the password in one transaction, returning the
    user id. Single-use is enforced by `used_at IS NULL` in the UPDATE's WHERE
    and by checking rowcount: two simultaneous submissions of the same link mean
    one UPDATE matches and the other matches nothing."""
    hashed = tokens.token_hash(token)
    now = db.utcnow()
    with db.cursor(write=True) as conn:
        found = conn.execute(
            "SELECT * FROM password_resets WHERE token_hash = ? AND used_at IS NULL "
            "AND expires_at > ?", (hashed, now)).fetchone()
        if not found:
            return None
        claimed = conn.execute(
            "UPDATE password_resets SET used_at = ? WHERE id = ? AND used_at IS NULL",
            (now, found["id"]))
        if not claimed.rowcount:
            return None
        user_id = found["user_id"]
        conn.execute(
            "INSERT INTO user_passwords (user_id,password_hash,algo,updated_at) "
            "VALUES (?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET "
            "password_hash = excluded.password_hash, algo = excluded.algo, "
            "updated_at = excluded.updated_at", (user_id, new_hash, algo, now))
        # A reset is also proof of mailbox control, so it verifies the address.
        conn.execute("UPDATE users SET email_verified = 1, updated_at = ? WHERE id = ?",
                     (now, user_id))
        # Anyone holding a session from before the reset loses it. A password
        # reset is what someone does when they think an account is compromised;
        # leaving the intruder's session alive defeats the point.
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        return user_id


def create_verification(user_id: str, ttl_seconds: int) -> str:
    token = tokens.new_token()
    db.execute_many([
        ("DELETE FROM email_verifications WHERE user_id = ? AND verified_at IS NULL",
         (user_id,)),
        ("INSERT INTO email_verifications (id,user_id,token_hash,expires_at,created_at) "
         "VALUES (?,?,?,?,?)",
         (db.new_id(), user_id, tokens.token_hash(token), db.in_seconds(ttl_seconds),
          db.utcnow())),
    ])
    return token


def consume_verification(token: str) -> Optional[str]:
    hashed = tokens.token_hash(token)
    now = db.utcnow()
    with db.cursor(write=True) as conn:
        found = conn.execute(
            "SELECT * FROM email_verifications WHERE token_hash = ? AND verified_at IS NULL "
            "AND expires_at > ?", (hashed, now)).fetchone()
        if not found:
            return None
        claimed = conn.execute(
            "UPDATE email_verifications SET verified_at = ? WHERE id = ? "
            "AND verified_at IS NULL", (now, found["id"]))
        if not claimed.rowcount:
            return None
        conn.execute("UPDATE users SET email_verified = 1, updated_at = ? WHERE id = ?",
                     (now, found["user_id"]))
        return found["user_id"]


# ------------------------------------------------------------------ passkeys


def add_passkey(user_id: str,
                credential_id: str,
                public_key: bytes,
                counter: int,
                device_type: Optional[str],
                backed_up: bool,
                transports: Optional[List[str]],
                name: str) -> Dict[str, Any]:
    now = db.utcnow()
    pid = db.new_id()
    db.execute(
        "INSERT INTO passkeys (id,user_id,credential_id,public_key,counter,device_type,"
        "backed_up,transports,name,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (pid, user_id, credential_id, public_key, counter, device_type,
         1 if backed_up else 0, json.dumps(transports or []), name[:60] or "Passkey", now))
    found = db.row("SELECT * FROM passkeys WHERE id = ?", (pid,))
    assert found is not None
    return found


def passkeys_for(user_id: str) -> List[Dict[str, Any]]:
    return db.rows("SELECT * FROM passkeys WHERE user_id = ? ORDER BY created_at", (user_id,))


def passkey_by_credential(credential_id: str) -> Optional[Dict[str, Any]]:
    return db.row("SELECT * FROM passkeys WHERE credential_id = ?", (credential_id,))


def update_passkey_use(passkey_id: str, counter: int, backed_up: Optional[bool] = None) -> None:
    if backed_up is None:
        db.execute("UPDATE passkeys SET counter = ?, last_used_at = ? WHERE id = ?",
                   (counter, db.utcnow(), passkey_id))
        return
    db.execute("UPDATE passkeys SET counter = ?, backed_up = ?, last_used_at = ? WHERE id = ?",
               (counter, 1 if backed_up else 0, db.utcnow(), passkey_id))


def rename_passkey(user_id: str, passkey_id: str, name: str) -> int:
    return db.execute("UPDATE passkeys SET name = ? WHERE id = ? AND user_id = ?",
                      ((name or "Passkey").strip()[:60] or "Passkey", passkey_id, user_id))


def delete_passkey(user_id: str, passkey_id: str) -> int:
    return db.execute("DELETE FROM passkeys WHERE id = ? AND user_id = ?",
                      (passkey_id, user_id))


def public_passkey(rowdict: Dict[str, Any]) -> Dict[str, Any]:
    try:
        transports = json.loads(rowdict.get("transports") or "[]")
    except (TypeError, ValueError):
        transports = []
    return {
        "id": rowdict["id"],
        "name": rowdict.get("name") or "Passkey",
        "device_type": rowdict.get("device_type"),
        "backed_up": bool(rowdict.get("backed_up")),
        "transports": transports,
        "created_at": rowdict.get("created_at"),
        "last_used_at": rowdict.get("last_used_at"),
    }


# ------------------------------------------------- challenges and oauth state


def store_challenge(challenge: str, kind: str,
                    user_id: Optional[str], ttl_seconds: int) -> None:
    db.execute_many([
        # Sweep on issue as well as on the timer, so a long-idle instance does
        # not accumulate rows between sweeps.
        ("DELETE FROM webauthn_challenges WHERE expires_at < ?", (db.utcnow(),)),
        ("INSERT INTO webauthn_challenges (id,challenge,kind,user_id,expires_at,created_at) "
         "VALUES (?,?,?,?,?,?)",
         (db.new_id(), challenge, kind, user_id, db.in_seconds(ttl_seconds), db.utcnow())),
    ])


def take_challenge(challenge: str, kind: str) -> Optional[Dict[str, Any]]:
    """Fetch and delete in one transaction. Deleting is what makes a captured
    assertion useless the second time it is presented."""
    now = db.utcnow()
    with db.cursor(write=True) as conn:
        found = conn.execute(
            "SELECT * FROM webauthn_challenges WHERE challenge = ? AND kind = ? "
            "AND expires_at > ?", (challenge, kind, now)).fetchone()
        if not found:
            return None
        gone = conn.execute("DELETE FROM webauthn_challenges WHERE id = ?", (found["id"],))
        if not gone.rowcount:
            return None
        return dict(found)


def store_state(state: str, provider: str, nonce: str,
                redirect_to: Optional[str], link_user_id: Optional[str],
                ttl_seconds: int, code_verifier: Optional[str] = None) -> None:
    db.execute_many([
        ("DELETE FROM oauth_states WHERE expires_at < ?", (db.utcnow(),)),
        ("INSERT INTO oauth_states (state,provider,nonce,redirect_to,link_user_id,"
         "code_verifier,expires_at,created_at) VALUES (?,?,?,?,?,?,?,?)",
         (state, provider, nonce, redirect_to, link_user_id, code_verifier,
          db.in_seconds(ttl_seconds), db.utcnow())),
    ])


def take_state(state: str, provider: str) -> Optional[Dict[str, Any]]:
    now = db.utcnow()
    with db.cursor(write=True) as conn:
        found = conn.execute(
            "SELECT * FROM oauth_states WHERE state = ? AND provider = ? AND expires_at > ?",
            (state, provider, now)).fetchone()
        if not found:
            return None
        gone = conn.execute("DELETE FROM oauth_states WHERE state = ?", (state,))
        if not gone.rowcount:
            return None
        return dict(found)


# ------------------------------------------------------ how many ways in there
#
# The number that stops someone locking themselves out. Counted from the
# database on every removal rather than tracked as a column, because a stale
# counter here means either a lockout or a bypass.


def auth_methods(user_id: str) -> Dict[str, Any]:
    identities = identities_for(user_id)
    passkeys = passkeys_for(user_id)
    has_password = get_password(user_id) is not None
    providers = sorted({i["provider"] for i in identities if i["provider"] != "email"})
    return {
        "password": has_password,
        "providers": providers,
        "passkeys": len(passkeys),
        # An email identity without a password is not a way in: nothing can be
        # presented at the login form. So it does not count here.
        "count": (1 if has_password else 0) + len(providers) + len(passkeys),
    }


# ------------------------------------------------------------- preferences


DEFAULT_PREFERENCES = {
    "time_zone": "auto",
    "default_market": "US",
    "default_landing": "home",
}

LANDING_VIEWS = ("home", "brief", "watchlist", "swing", "market", "chart", "scan")


def preferences(user_id: str) -> Dict[str, Any]:
    found = db.row("SELECT * FROM user_preferences WHERE user_id = ?", (user_id,))
    if not found:
        return dict(DEFAULT_PREFERENCES)
    return {k: found.get(k) or DEFAULT_PREFERENCES[k] for k in DEFAULT_PREFERENCES}


def set_preferences(user_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    fields = {k: v for k, v in patch.items() if k in DEFAULT_PREFERENCES}
    if "default_landing" in fields and fields["default_landing"] not in LANDING_VIEWS:
        # An unknown view would send the reader to a blank page on every visit,
        # so it is dropped rather than stored and discovered later.
        fields.pop("default_landing")
    # Checked *after* the validation above, not before: a patch whose only field
    # was rejected leaves nothing to set, and "SET , updated_at = ?" is a syntax
    # error rather than a no-op.
    if not fields:
        return preferences(user_id)
    sets = ", ".join("{} = ?".format(k) for k in fields)      # keys are literals above
    params = [str(v)[:64] for v in fields.values()] + [db.utcnow(), user_id]
    db.execute_many([
        # The row is created with the account; the upsert covers a user whose
        # account predates that guarantee.
        ("INSERT INTO user_preferences (user_id,updated_at) VALUES (?,?) "
         "ON CONFLICT(user_id) DO NOTHING", (user_id, db.utcnow())),
        ("UPDATE user_preferences SET {}, updated_at = ? WHERE user_id = ?".format(sets),
         params),
    ])
    return preferences(user_id)


# ----------------------------------------------------------- subscription
#
# No payment code. This reads the row created with the account so that the plan
# is already a fact the app can branch on — today it decides an assistant
# allowance, later it decides more.


PLANS = {
    "free": {"label": "Free", "ai_calls_per_day": 25, "watchlists": 3,
             "saved_research": 40},
    "pro": {"label": "Pro", "ai_calls_per_day": 400, "watchlists": 25,
            "saved_research": 1000},
    "enterprise": {"label": "Enterprise", "ai_calls_per_day": 4000, "watchlists": 200,
                   "saved_research": 10000},
}


def subscription(user_id: str) -> Dict[str, Any]:
    found = db.row(
        "SELECT * FROM subscriptions WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
        (user_id,))
    plan = (found or {}).get("plan") or "free"
    if plan not in PLANS:
        plan = "free"
    limits = PLANS[plan]
    return {
        "plan": plan,
        "label": limits["label"],
        "status": (found or {}).get("status") or "active",
        "provider": (found or {}).get("provider"),
        "current_period_end": (found or {}).get("current_period_end"),
        "limits": {k: v for k, v in limits.items() if k != "label"},
    }


def set_plan(user_id: str, plan: str, status: str = "active") -> Dict[str, Any]:
    """Present so a plan can be granted without hand-editing SQL. Nothing in the
    HTTP surface calls it; billing is not implemented."""
    if plan not in PLANS:
        raise ValueError("unknown plan: {}".format(plan))
    now = db.utcnow()
    existing = db.row("SELECT id FROM subscriptions WHERE user_id = ? LIMIT 1", (user_id,))
    if existing:
        db.execute("UPDATE subscriptions SET plan = ?, status = ?, updated_at = ? WHERE id = ?",
                   (plan, status, now, existing["id"]))
    else:
        db.execute("INSERT INTO subscriptions (id,user_id,plan,status,created_at,updated_at) "
                   "VALUES (?,?,?,?,?,?)", (db.new_id(), user_id, plan, status, now, now))
    return subscription(user_id)
