"""Passkeys, over py_webauthn.

Every cryptographic step is the library's: challenge comparison, client-data
hashing, the attestation object, the assertion signature, the RP-id hash and the
authenticator flags. This module supplies the policy around it — what to ask
for, what to store, and which failures are real.

**Discoverable credentials, deliberately.** `resident_key=required` means the
passkey carries the account inside it, so the login screen can offer "Sign in
with a passkey" with no email typed first. The alternative, a non-discoverable
credential, needs an `allow_credentials` list, which needs to know who you are,
which needs the email you were trying not to type.

**The sign counter, and why a naive check breaks Apple.** The counter exists to
catch a cloned authenticator: it should only ever increase. But a large share of
real authenticators — Apple's platform passkeys among them — always report zero,
because a synced credential has no single monotonic counter to report. So
rejecting `new <= stored` outright refuses every Apple passkey on its second
use. The rule here is: a counter that is zero on both sides carries no
information and is accepted; a counter that has previously been non-zero must
increase.

**What is stored.** The credential id and the COSE public key. Nothing secret:
the private key never leaves the device, and that is the property that makes a
passkey unphishable rather than just convenient.
"""

from __future__ import annotations

import json
import logging
import secrets
from typing import Any, Dict, List, Optional, Tuple

import webauthn
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.exceptions import (InvalidAuthenticationResponse,
                                         InvalidRegistrationResponse)
from webauthn.helpers.structs import (AuthenticatorSelectionCriteria,
                                      PublicKeyCredentialDescriptor,
                                      ResidentKeyRequirement,
                                      UserVerificationRequirement)

from . import config, store

log = logging.getLogger("optic.passkeys")


class PasskeyError(Exception):
    """A failure phrased for a person. The library's message goes to the log."""


def _challenge() -> bytes:
    return secrets.token_bytes(32)


def registration_options(user: Dict[str, Any]) -> Dict[str, Any]:
    """Options for creating a passkey, plus the challenge recorded server-side."""
    existing = store.passkeys_for(user["id"])
    options = webauthn.generate_registration_options(
        rp_id=config.rp_id(),
        rp_name=config.rp_name(),
        user_id=user["id"].encode("utf-8"),
        user_name=user["email"],
        user_display_name=(user.get("first_name") or user["email"]),
        challenge=_challenge(),
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            # PREFERRED, not REQUIRED. Required would refuse a hardware key with
            # no PIN set and offer no way forward from the browser dialog; the
            # verification flag is checked and recorded, not demanded.
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        # Stops the same authenticator being registered twice. Without it the
        # browser happily creates a second credential on the same device and the
        # Settings list grows a duplicate nobody can tell apart.
        exclude_credentials=[
            PublicKeyCredentialDescriptor(id=base64url_to_bytes(p["credential_id"]))
            for p in existing
        ],
    )
    challenge = bytes_to_base64url(options.challenge)
    store.store_challenge(challenge, "register", user["id"],
                          config.WEBAUTHN_CHALLENGE_TTL)
    return json.loads(webauthn.options_to_json(options))


def authentication_options() -> Dict[str, Any]:
    """Options for signing in with a passkey.

    No `allow_credentials`: the whole point of a discoverable credential is that
    the browser picks the account. Sending a list would also be an account
    enumeration oracle — hand it an email and it tells you whether that person
    has a passkey."""
    options = webauthn.generate_authentication_options(
        rp_id=config.rp_id(),
        challenge=_challenge(),
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    challenge = bytes_to_base64url(options.challenge)
    store.store_challenge(challenge, "login", None, config.WEBAUTHN_CHALLENGE_TTL)
    return json.loads(webauthn.options_to_json(options))


def _client_challenge(credential: Dict[str, Any]) -> str:
    """The challenge the browser says it signed, read out of clientDataJSON.

    Needed because the response has to be matched to a stored challenge before
    verification can be asked to check it. The value is untrusted at this point;
    it is a lookup key, and the library then proves the signature covers it."""
    try:
        raw = credential["response"]["clientDataJSON"]
        data = json.loads(base64url_to_bytes(raw).decode("utf-8"))
        return str(data.get("challenge") or "")
    except (KeyError, TypeError, ValueError, UnicodeDecodeError):
        raise PasskeyError("That passkey response was malformed.")


def device_label(user_agent: str) -> str:
    """A default name, from the user agent.

    Not a device model: a browser cannot know it. "Chrome on Mac" is what can
    honestly be said, and the reader can rename it to "MacBook Pro" in Settings,
    which is the example in the design."""
    agent = (user_agent or "").lower()
    if "iphone" in agent:
        platform = "iPhone"
    elif "ipad" in agent:
        platform = "iPad"
    elif "android" in agent:
        platform = "Android"
    elif "mac os" in agent or "macintosh" in agent:
        platform = "Mac"
    elif "windows" in agent:
        platform = "Windows"
    elif "linux" in agent:
        platform = "Linux"
    else:
        return "Passkey"
    # Order matters: Edge and Chrome both say "Chrome", and Chrome says "Safari".
    if "edg/" in agent:
        browser = "Edge"
    elif "opr/" in agent or "opera" in agent:
        browser = "Opera"
    elif "chrome" in agent or "crios" in agent:
        browser = "Chrome"
    elif "firefox" in agent or "fxios" in agent:
        browser = "Firefox"
    elif "safari" in agent:
        browser = "Safari"
    else:
        return platform + " passkey"
    return "{} on {}".format(browser, platform)


def verify_registration(credential: Dict[str, Any],
                        user_agent: str = "",
                        name: Optional[str] = None) -> Dict[str, Any]:
    """Check a new passkey and store it. Returns the stored row.

    The challenge is taken (and deleted) before verification, so a response
    replayed a second time finds nothing to match and fails on the lookup rather
    than on the signature."""
    challenge = _client_challenge(credential)
    taken = store.take_challenge(challenge, "register")
    if not taken or not taken.get("user_id"):
        raise PasskeyError("That passkey attempt expired. Try adding it again.")
    user_id = taken["user_id"]

    try:
        verified = webauthn.verify_registration_response(
            credential=credential,
            expected_challenge=base64url_to_bytes(challenge),
            expected_rp_id=config.rp_id(),
            expected_origin=config.expected_origins(),
            require_user_verification=False,
        )
    except InvalidRegistrationResponse as exc:
        log.warning("passkey registration rejected: %s", exc)
        raise PasskeyError("That passkey could not be verified. It was not saved.")

    credential_id = bytes_to_base64url(verified.credential_id)
    if store.passkey_by_credential(credential_id):
        raise PasskeyError("That passkey is already registered.")

    transports: List[str] = []
    for value in (credential.get("response") or {}).get("transports") or []:
        transports.append(str(value))

    device_type = getattr(verified.credential_device_type, "value",
                          verified.credential_device_type)
    return store.add_passkey(
        user_id=user_id,
        credential_id=credential_id,
        public_key=verified.credential_public_key,
        counter=int(verified.sign_count or 0),
        device_type=str(device_type) if device_type else None,
        backed_up=bool(verified.credential_backed_up),
        transports=transports,
        name=(name or device_label(user_agent)),
    )


def verify_authentication(credential: Dict[str, Any]) -> Tuple[Dict[str, Any],
                                                               Dict[str, Any]]:
    """(user, passkey row) on a good assertion.

    Order of checks: challenge exists and is claimed, credential is known, then
    the signature. Each one is cheap and rules out a class of nonsense before the
    expensive step."""
    challenge = _client_challenge(credential)
    taken = store.take_challenge(challenge, "login")
    if not taken:
        raise PasskeyError("That sign-in attempt expired. Try again.")

    credential_id = str(credential.get("id") or credential.get("rawId") or "")
    stored = store.passkey_by_credential(credential_id) if credential_id else None
    if not stored:
        # Same message as an unknown credential *and* a wrong signature: which
        # of the two it was would tell a caller whether a given passkey is
        # registered here.
        raise PasskeyError("That passkey is not registered on this account.")

    try:
        verified = webauthn.verify_authentication_response(
            credential=credential,
            expected_challenge=base64url_to_bytes(challenge),
            expected_rp_id=config.rp_id(),
            expected_origin=config.expected_origins(),
            credential_public_key=bytes(stored["public_key"]),
            credential_current_sign_count=int(stored["counter"] or 0),
            require_user_verification=False,
        )
    except InvalidAuthenticationResponse as exc:
        log.warning("passkey assertion rejected: %s", exc)
        raise PasskeyError("That passkey is not registered on this account.")

    old_counter = int(stored["counter"] or 0)
    new_counter = int(verified.new_sign_count or 0)
    # See the module docstring: zero on both sides is the normal Apple case and
    # carries no information. A counter that was previously counting and has now
    # stopped or gone backwards is the clone signal.
    if old_counter > 0 and new_counter <= old_counter:
        log.warning("passkey sign counter did not advance: %s -> %s (credential %s)",
                    old_counter, new_counter, stored["id"])
        raise PasskeyError(
            "That passkey looks like it has been copied, so it was refused. Remove it "
            "in Settings and add a new one.")

    user = store.get_user(stored["user_id"])
    if not user or not user.get("is_active"):
        raise PasskeyError("That account is not active.")

    backed_up = getattr(verified, "credential_backed_up", None)
    store.update_passkey_use(stored["id"], new_counter,
                             None if backed_up is None else bool(backed_up))
    return user, stored
