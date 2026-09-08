"""A software authenticator, for testing the passkey paths for real.

Not a mock of `webauthn.verify_*`. This builds the actual bytes a browser would
hand back — a CBOR attestation object with `fmt: none`, and an assertion signed
by a real P-256 key — so the tests exercise py_webauthn's verification rather
than a stub of it. If the library rejects something, these tests fail.

Two things it deliberately gets right, because both are ways a hand-rolled
fixture passes while a real device fails:

* **The RP id hash.** authData begins with SHA-256 of the RP id, and the library
  compares it against the configured one. A fixture that puts the origin there
  instead verifies against nothing.
* **The backup flags.** BS (backed up) set without BE (backup eligible) is an
  invalid combination and py_webauthn refuses it, which is what a synced-passkey
  test has to model correctly to be worth anything.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, Optional

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from webauthn.helpers import bytes_to_base64url, encode_cbor

FLAG_UP = 0x01          # user present
FLAG_UV = 0x04          # user verified
FLAG_BE = 0x08          # backup eligible
FLAG_BS = 0x10          # backed up
FLAG_AT = 0x40          # attested credential data follows


class SoftAuthenticator:
    """One device holding one passkey."""

    def __init__(self, rp_id: str = "localhost", synced: bool = True,
                 counter: int = 0):
        self.rp_id = rp_id
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.credential_id = os.urandom(32)
        self.counter = counter
        self.synced = synced

    # ------------------------------------------------------------------ keys
    @property
    def credential_id_b64(self) -> str:
        return bytes_to_base64url(self.credential_id)

    def cose_public_key(self) -> bytes:
        """COSE_Key for an ES256 public key: kty=EC2(2), alg=-7, crv=P-256(1)."""
        numbers = self.key.public_key().public_numbers()
        return encode_cbor({
            1: 2,
            3: -7,
            -1: 1,
            -2: numbers.x.to_bytes(32, "big"),
            -3: numbers.y.to_bytes(32, "big"),
        })

    # ------------------------------------------------------------ authData
    def _flags(self, attested: bool) -> int:
        flags = FLAG_UP | FLAG_UV
        if self.synced:
            flags |= FLAG_BE | FLAG_BS
        if attested:
            flags |= FLAG_AT
        return flags

    def _auth_data(self, attested: bool) -> bytes:
        blob = hashlib.sha256(self.rp_id.encode("utf-8")).digest()
        blob += bytes([self._flags(attested)])
        blob += self.counter.to_bytes(4, "big")
        if attested:
            blob += b"\x00" * 16                      # AAGUID, zero for none-attestation
            blob += len(self.credential_id).to_bytes(2, "big")
            blob += self.credential_id
            blob += self.cose_public_key()
        return blob

    @staticmethod
    def _client_data(kind: str, challenge: str, origin: str) -> bytes:
        return json.dumps({
            "type": kind,
            "challenge": challenge,
            "origin": origin,
            "crossOrigin": False,
        }).encode("utf-8")

    # -------------------------------------------------------------- ceremonies
    def register(self, challenge: str, origin: str = "http://localhost:8000",
                 transports: Optional[list] = None) -> Dict[str, Any]:
        client_data = self._client_data("webauthn.create", challenge, origin)
        attestation = encode_cbor({
            "fmt": "none",
            "attStmt": {},
            "authData": self._auth_data(attested=True),
        })
        return {
            "id": self.credential_id_b64,
            "rawId": self.credential_id_b64,
            "type": "public-key",
            "response": {
                "clientDataJSON": bytes_to_base64url(client_data),
                "attestationObject": bytes_to_base64url(attestation),
                "transports": transports if transports is not None
                else ["internal", "hybrid"],
            },
            "clientExtensionResults": {},
        }

    def authenticate(self, challenge: str, origin: str = "http://localhost:8000",
                     bump: int = 0) -> Dict[str, Any]:
        self.counter += bump
        client_data = self._client_data("webauthn.get", challenge, origin)
        auth_data = self._auth_data(attested=False)
        signed = auth_data + hashlib.sha256(client_data).digest()
        signature = self.key.sign(signed, ec.ECDSA(hashes.SHA256()))
        return {
            "id": self.credential_id_b64,
            "rawId": self.credential_id_b64,
            "type": "public-key",
            "response": {
                "clientDataJSON": bytes_to_base64url(client_data),
                "authenticatorData": bytes_to_base64url(auth_data),
                "signature": bytes_to_base64url(signature),
                "userHandle": bytes_to_base64url(b"unused"),
            },
            "clientExtensionResults": {},
        }
