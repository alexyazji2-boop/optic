"""Random secrets, and how they are stored.

Three kinds of secret live in the database: session tokens, password-reset
tokens and email-verification tokens. All three are stored as a SHA-256 hash and
never in the clear, so a leaked backup contains nothing that can be replayed.

**Why SHA-256 here and Argon2 for passwords.** Argon2 is slow on purpose because
a human-chosen password has maybe 30 bits of entropy and the only defence is
making each guess expensive. These tokens are 256 bits from the OS CSPRNG. There
is no dictionary to search, so there is nothing for slowness to buy — and a
slow hash on the session cookie would add its cost to *every authenticated
request*, not just to sign-in.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

# 32 bytes, URL-safe base64 => 43 characters. Fits a query string and a cookie
# without encoding, and is well past any brute-force reach.
TOKEN_BYTES = 32


def new_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def same(a: str, b: str) -> bool:
    """Constant-time comparison. Used where a token or a CSRF value is compared
    to something an attacker supplies and can time."""
    return hmac.compare_digest((a or "").encode("utf-8"), (b or "").encode("utf-8"))


def new_numeric_code(digits: int = 6) -> str:
    """A short code for cases where a link cannot be clicked (a different device
    to the one that asked). `secrets.randbelow` rather than `random`: the latter
    is a Mersenne Twister and its output is predictable from previous draws."""
    top = 10 ** digits
    return str(secrets.randbelow(top)).zfill(digits)
