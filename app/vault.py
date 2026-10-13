"""Encryption at rest for the one kind of data Optic holds that is somebody's money.

Brokerage holdings, balances and the aggregator's per-user secret are the most
sensitive things this app has ever stored. Everything else in `accounts.db` is a
watchlist or a note. So they are sealed before they reach SQLite, and the shape
is envelope encryption:

* **One master key** (`OPTIC_DATA_KEY`, 32 random bytes, base64) lives in the
  environment, never on the volume. A copy of `accounts.db` taken from a backup,
  a snapshot or a stolen disk is ciphertext without it.
* **One data key per user**, random, stored wrapped by the master key in
  `brokerage_users.dek`. Every brokerage payload for that user is sealed with it.
* **Deleting the wrapped data key is the deletion.** That is crypto-shredding:
  a backup taken last week still holds the ciphertext, and nobody, including the
  operator, can open it once the key row is gone. "Disconnect and delete my data"
  can then be a promise about backups too, not only about the live table.

AES-256-GCM from `cryptography` (already installed for PyJWT and py_webauthn;
no new dependency). Every seal binds *associated data* naming the owner and the
row, so a ciphertext copied into another user's row, or from one account's row
to another's, fails authentication instead of decrypting as someone else's
portfolio. That is the property an `UPDATE ... SET payload = (SELECT ...)` slip
or a confused restore would otherwise break silently.

Key rotation: the ciphertext carries a one-byte version, and `OPTIC_DATA_KEY_OLD`
is tried for unwrapping when the current key fails, so a key can be rotated by
setting the new one, keeping the old one for a release, and rewrapping on read.
"""

from __future__ import annotations

import base64
import os
from typing import Optional

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

VERSION = b"\x01"


class VaultUnavailable(RuntimeError):
    """No usable master key. Brokerage linking refuses to run rather than
    storing anything in the clear."""


def _decode(raw: str) -> Optional[bytes]:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        key = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    except (ValueError, TypeError):
        return None
    return key if len(key) == 32 else None


def _master_keys() -> list:
    keys = [k for k in (_decode(os.environ.get("OPTIC_DATA_KEY", "")),
                        _decode(os.environ.get("OPTIC_DATA_KEY_OLD", ""))) if k]
    return keys


def available() -> bool:
    return bool(_decode(os.environ.get("OPTIC_DATA_KEY", "")))


def new_master_key() -> str:
    """For the launch checklist: `python -m app.vault` prints one."""
    return base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip("=")


def _seal(key: bytes, plaintext: bytes, aad: str) -> bytes:
    nonce = os.urandom(12)
    return VERSION + nonce + AESGCM(key).encrypt(nonce, plaintext, aad.encode())


def _open(key: bytes, blob: bytes, aad: str) -> bytes:
    if not blob or blob[:1] != VERSION or len(blob) < 1 + 12 + 16:
        raise InvalidTag()
    return AESGCM(key).decrypt(blob[1:13], blob[13:], aad.encode())


def new_wrapped_dek(user_id: str) -> bytes:
    keys = _master_keys()
    if not available():
        raise VaultUnavailable("OPTIC_DATA_KEY is not set")
    return _seal(keys[0], os.urandom(32), "dek:" + user_id)


def unwrap_dek(user_id: str, wrapped: bytes) -> bytes:
    keys = _master_keys()
    if not keys:
        raise VaultUnavailable("OPTIC_DATA_KEY is not set")
    for key in keys:
        try:
            return _open(key, wrapped, "dek:" + user_id)
        except InvalidTag:
            continue
    raise VaultUnavailable("the stored data key does not open with the configured master key")


def seal(dek: bytes, plaintext: str, aad: str) -> bytes:
    return _seal(dek, plaintext.encode("utf-8"), aad)


def open_(dek: bytes, blob: bytes, aad: str) -> str:
    return _open(dek, blob, aad).decode("utf-8")


if __name__ == "__main__":                      # python -m app.vault
    print(new_master_key())
