"""Throttles on the endpoints an attacker gets to call for free.

**Why this is in SQLite and not a dict.** The existing assistant guard in
`app/main.py` keeps its buckets in memory, and that is the right call there: it
is metering spend, and losing the counter on restart costs at most one hour of
one caller's allowance. Login throttling is different. DEPLOY.md records this
service being OOM-killed during scans, roughly every four hours — so an
in-memory attempt counter is cleared by an event the attacker does not even have
to cause. A throttle that forgets on a schedule is a delay, not a limit.

**Two buckets per attempt, not one.** Rate-limiting by IP alone is defeated by
anyone with a handful of addresses, and rate-limiting by account alone lets one
IP walk the whole user list at one guess per account. Login records against both
the address and the email, and either being over the limit refuses the attempt.

**What this does not do.** It does not lock accounts. A lockout on failed
attempts is a denial-of-service against a named user: anyone who knows an email
address can lock its owner out on demand. The window here expires on its own.
"""

from __future__ import annotations

import hashlib
from typing import Dict, Optional, Tuple

from fastapi import HTTPException, Request

from .. import db

# kind -> (attempts allowed, window in seconds)
#
# The numbers are chosen against what a legitimate person does. Ten logins in
# fifteen minutes covers a forgotten password and several retries; a hundredth
# attempt in that window is not a person typing.
LIMITS: Dict[str, Tuple[int, int]] = {
    "login": (10, 900),
    "register": (5, 3600),
    "forgot": (5, 3600),
    "reset": (10, 3600),
    "verify_resend": (5, 3600),
    "passkey_challenge": (30, 900),
    "passkey_verify": (20, 900),
    "oauth_start": (30, 900),
    "oauth_callback": (30, 900),
    "password_change": (10, 3600),
}

FRIENDLY = {
    "login": "sign-in attempts",
    "register": "account creations",
    "forgot": "password reset requests",
    "reset": "password reset attempts",
    "verify_resend": "verification emails",
    "passkey_challenge": "passkey attempts",
    "passkey_verify": "passkey attempts",
    "oauth_start": "sign-in attempts",
    "oauth_callback": "sign-in attempts",
    "password_change": "password changes",
}


def client_ip(request: Request) -> str:
    """The caller's address as best it can be known.

    Behind Railway's proxy the socket peer is the proxy, so the first hop of the
    forwarded chain is preferred. It is spoofable — which is why the email bucket
    exists alongside it — but bucketing every visitor together under one proxy
    address would throttle the whole site the moment one caller misbehaved."""
    forwarded = request.headers.get("x-forwarded-for", "")
    first = forwarded.split(",")[0].strip()
    if first:
        return first[:64]
    return (request.client.host if request.client else "unknown")[:64]


def key_bucket(value: str) -> str:
    """The bucket name for something that is not an address — an email, a user
    id. Prefixed so it can never collide with an IP-shaped bucket."""
    return "k:" + str(value).strip().lower()


def _bucket(raw: str) -> str:
    """Buckets are hashed before storage.

    The rate-limit table would otherwise be a log of who tried to sign in and
    from where, retained for a day, for no operational benefit — the counter only
    needs to know that two attempts came from the same place, not where."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def count(kind: str, raw_bucket: str) -> int:
    allowed, window = LIMITS.get(kind, (20, 900))
    found = db.row(
        "SELECT COUNT(*) AS n FROM auth_attempts WHERE kind = ? AND bucket = ? "
        "AND created_at > ?", (kind, _bucket(raw_bucket), db.in_seconds(-window)))
    return int((found or {}).get("n") or 0)


def record(kind: str, raw_bucket: str) -> None:
    db.execute(
        "INSERT INTO auth_attempts (id,bucket,kind,created_at) VALUES (?,?,?,?)",
        (db.new_id(), _bucket(raw_bucket), kind, db.utcnow()))


def over(kind: str, raw_bucket: str) -> bool:
    allowed, _window = LIMITS.get(kind, (20, 900))
    return count(kind, raw_bucket) >= allowed


def guard(request: Request, kind: str, *extra_buckets: Optional[str]) -> None:
    """Refuse the request if any of its buckets is over the limit.

    Recording happens here, on the attempt, rather than on failure. Counting only
    failures means a caller who alternates a wrong password with a right one
    never fills the bucket, and it makes an enumeration sweep free as long as the
    guesses are wrong in a way the endpoint treats as success."""
    buckets = [client_ip(request)]
    for candidate in extra_buckets:
        if candidate:
            buckets.append(key_bucket(candidate))

    allowed, window = LIMITS.get(kind, (20, 900))
    for bucket in buckets:
        if count(kind, bucket) >= allowed:
            minutes = max(1, window // 60)
            raise HTTPException(
                status_code=429,
                detail="Too many {}. Wait about {} minutes and try again.".format(
                    FRIENDLY.get(kind, "attempts"), minutes),
                headers={"Retry-After": str(window)},
            )
    for bucket in buckets:
        record(kind, bucket)


def clear(kind: str, *raw_buckets: Optional[str]) -> None:
    """Forget the attempts in these buckets. Called after a *successful*
    sign-in: someone who just proved who they are should not be one retry away
    from a lockout because of earlier typos."""
    for raw in raw_buckets:
        if not raw:
            continue
        db.execute("DELETE FROM auth_attempts WHERE kind = ? AND bucket = ?",
                   (kind, _bucket(str(raw))))


# ------------------------------------------------------- variable allowances
#
# The throttles above have a fixed ceiling per kind. An assistant allowance does
# not: it depends on whether the caller is signed in and on what plan, so the
# ceiling is an argument rather than a table lookup.


def allowance(kind: str, raw_bucket: str, allowed: int,
              window: int) -> Dict[str, int]:
    """How much of an allowance is spent, without spending any of it."""
    used = 0
    if allowed > 0:
        found = db.row(
            "SELECT COUNT(*) AS n FROM auth_attempts WHERE kind = ? AND bucket = ? "
            "AND created_at > ?", (kind, _bucket(raw_bucket), db.in_seconds(-window)))
        used = int((found or {}).get("n") or 0)
    return {"used": used, "allowed": allowed, "left": max(0, allowed - used)}


def spend(kind: str, raw_bucket: str, allowed: int, window: int,
          message: str) -> Dict[str, int]:
    """Take one unit or refuse. `allowed <= 0` disables the limit entirely, which
    is how the existing AI_CALLS_PER_HOUR=0 escape hatch keeps working."""
    if allowed <= 0:
        return {"used": 0, "allowed": 0, "left": 0}
    state = allowance(kind, raw_bucket, allowed, window)
    if state["left"] <= 0:
        raise HTTPException(status_code=429, detail=message,
                            headers={"Retry-After": str(window)})
    record(kind, raw_bucket)
    state["used"] += 1
    state["left"] -= 1
    return state
