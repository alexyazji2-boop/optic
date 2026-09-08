"""Password hashing and the password policy.

**Argon2id, via argon2-cffi.** Nothing here implements a hash; the library does
the work and the parameters below are the only decision this module makes.

**Why the parameters are not the library defaults.** argon2-cffi defaults to
64 MiB of memory per hash. This service runs in a container that DEPLOY.md
records being OOM-killed during a scan at around 700 MB, and every concurrent
sign-in would want its own 64 MiB — so the default turns a burst of logins into
an out-of-memory restart. The settings used instead are OWASP's documented
minimum configuration for Argon2id (m=19456 KiB, t=2, p=1), which is a published
recommendation rather than a number picked to fit.

**Why the policy has no composition rules.** No "must contain a symbol", no
forced mixed case. NIST SP 800-63B advises against them: they push people toward
`Password1!`, which is in every cracking dictionary, and they make a long
passphrase harder to type than a short bad password. What is checked instead is
length, a list of the passwords that actually get tried first, and whether the
password is simply the person's own name or email — which is the failure mode a
symbol rule does not catch.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from argon2.low_level import Type

ALGO = "argon2id"

_HASHER = PasswordHasher(
    time_cost=2,
    memory_cost=19456,       # KiB. OWASP minimum configuration for Argon2id.
    parallelism=1,
    hash_len=32,
    salt_len=16,
    type=Type.ID,            # Argon2id: the hybrid, resistant to both attacks
)

MIN_LENGTH = 10

# An upper bound exists because the input is attacker-controlled and hashing is
# deliberately expensive: without it, a 10 MB "password" is a cheap way to make
# the server spend real CPU on one request. 128 is far above any real passphrase.
MAX_LENGTH = 128

# The short head of every credential-stuffing list. Not a substitute for a breach
# corpus — that is a 500 MB download and a lookup service — but it blocks the
# passwords that are tried first, which is where the actual risk is.
COMMON = {
    "password", "password1", "password123", "passw0rd", "123456", "1234567",
    "12345678", "123456789", "1234567890", "qwerty", "qwerty123", "qwertyuiop",
    "abc123", "111111", "123123", "000000", "iloveyou", "admin", "admin123",
    "welcome", "welcome1", "monkey", "dragon", "letmein", "login", "princess",
    "sunshine", "master", "football", "baseball", "trustno1", "starwars",
    "whatever", "zaq12wsx", "1q2w3e4r", "asdfghjkl", "changeme", "secret",
    "optic", "optic123", "opticterminal", "terminal", "stonks", "tothemoon",
    "robinhood", "tradingview", "bloomberg", "portfolio", "investing",
}


def hash_password(password: str) -> str:
    """The encoded Argon2 string, which carries its own parameters and salt.
    Storing that rather than a bare digest is what makes `needs_rehash` below
    possible: the cost can be raised later and old hashes still verify."""
    return _HASHER.hash(password)


def verify_password(stored: str, password: str) -> Tuple[bool, Optional[str]]:
    """(matched, replacement_hash).

    The second value is not None when the stored hash used weaker parameters
    than the current settings. The caller is the only place that has the plaintext
    to re-hash with, so upgrading has to happen at sign-in or never."""
    try:
        _HASHER.verify(stored, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False, None
    try:
        if _HASHER.check_needs_rehash(stored):
            return True, _HASHER.hash(password)
    except InvalidHashError:
        pass
    return True, None


def policy_problems(password: str,
                    email: str = "",
                    first_name: str = "",
                    last_name: str = "") -> List[str]:
    """Every reason this password is refused, phrased for a person to read.

    All of them at once rather than the first one: a form that reveals one rule
    per submission makes the reader guess how many are left."""
    problems: List[str] = []
    if len(password) < MIN_LENGTH:
        problems.append("Use at least {} characters.".format(MIN_LENGTH))
    if len(password) > MAX_LENGTH:
        problems.append("Keep it under {} characters.".format(MAX_LENGTH))

    folded = password.strip().lower()
    if folded in COMMON:
        problems.append("That password is one of the most commonly used ones. "
                        "Choose something else.")
    if password and password == password[0] * len(password):
        problems.append("Repeating one character is not a password.")
    if folded.isdigit() and len(folded) <= 12:
        problems.append("Digits alone are guessed quickly. Add words.")

    local = (email or "").split("@")[0].strip().lower()
    for part in (local, (first_name or "").strip().lower(), (last_name or "").strip().lower()):
        if len(part) >= 3 and part in folded:
            problems.append("Do not put your name or email address in your password.")
            break
    return problems


def describe_policy() -> List[str]:
    """What the signup form tells the reader before they type. Kept next to the
    rules so the two cannot drift apart."""
    return [
        "At least {} characters".format(MIN_LENGTH),
        "Not a commonly used password",
        "Not your name or email address",
    ]
