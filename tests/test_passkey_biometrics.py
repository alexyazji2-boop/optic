"""Calling a passkey what the device will actually ask you for.

The capability was already here. A passkey IS Face ID or Touch ID: WebAuthn with
a platform authenticator uses the device biometric, resident_key is REQUIRED so
sign-in needs no username, and conditional mediation offers the credential from
inside the email field with nothing pressed.

What was missing was saying so. The button read "Sign in with a passkey" — a
word most people have never met — sitting next to buttons that said Google and
Apple. Nobody has to learn what a passkey is to press "Sign in with Face ID".

The care here is in not claiming a sensor that cannot be seen. There is no API
that distinguishes Face ID from Touch ID, or a Windows Hello camera from its
fingerprint reader, so the platform family is named and both of that family's
sensors are named with it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
AUTH_JS = (ROOT / "static" / "auth.js").read_text()
APP_JS = (ROOT / "static" / "app.js").read_text()
PASSKEYS_PY = (ROOT / "app" / "auth" / "passkeys.py").read_text()


def _fn(name: str, src: str = None) -> str:
    text = src if src is not None else AUTH_JS
    return text.split(f"function {name}(", 1)[1].split("\n  function ", 1)[0]


# ----------------------------------------------- the capability already exists

def test_a_passkey_needs_no_username():
    """Resident, so the browser picks the account and the biometric is the whole
    interaction. Without this, "sign in with Face ID" would still need an email
    typed first."""
    assert "resident_key=ResidentKeyRequirement.REQUIRED" in PASSKEYS_PY


def test_the_person_is_verified_not_just_the_device():
    """PREFERRED rather than REQUIRED, and the file says why: REQUIRED refuses a
    hardware key with no PIN and offers no way forward from the browser dialog.
    A platform authenticator verifies regardless — that is what it is for."""
    assert "user_verification=UserVerificationRequirement.PREFERRED" in PASSKEYS_PY


def test_the_email_field_offers_the_passkey_by_itself():
    """`username webauthn` is what lets the browser put Face ID in the autofill
    dropdown with no button pressed."""
    assert '"username webauthn"' in AUTH_JS or "'username webauthn'" in AUTH_JS
    assert "isConditionalMediationAvailable" in AUTH_JS


# ------------------------------------------------------------- the detection

def test_availability_is_asked_not_assumed():
    """isUserVerifyingPlatformAuthenticatorAvailable answers exactly the claim
    the label makes: this device has a built-in authenticator that will verify
    the person."""
    assert "isUserVerifyingPlatformAuthenticatorAvailable" in AUTH_JS
    body = _fn("askPlatformAuthenticator")
    assert "platformAuth = !!ok" in body


def test_the_probe_is_cached_and_cannot_throw():
    """It runs on every paint of the modal, and a rejected promise must not take
    the sign-in form down with it."""
    body = _fn("askPlatformAuthenticator")
    assert "if (platformAuth !== null) return" in body
    assert ".catch(" in body


def test_a_browser_without_the_api_is_handled():
    body = _fn("askPlatformAuthenticator")
    assert "!window.PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable" in body
    assert "platformAuth = false" in body


def test_the_render_never_waits_on_it():
    """The answer arrives after the first paint. A modal that awaited it would
    flash empty, so the label starts neutral and is upgraded in place."""
    body = _fn("paint")
    assert "askPlatformAuthenticator().then(" in body
    assert "label.textContent = passkeyButtonLabel()" in body


def test_the_upgrade_swaps_the_label_not_the_row():
    """Repainting would take focus off the field being typed in and tear down
    the conditional-UI request armed two lines above."""
    body = _fn("paint")
    assert "[data-passkey-label]" in body
    assert body.index("armConditionalPasskey()") < body.index("askPlatformAuthenticator()")


# ------------------------------------------------------------- the wording

def test_no_specific_sensor_is_claimed_alone():
    """No API distinguishes Face ID from Touch ID. Naming one would be a guess
    printed as a fact."""
    body = _fn("biometricName")
    assert "'Face ID or Touch ID'" in body
    assert "'Face ID'" not in body
    assert "'Touch ID'" not in body


@pytest.mark.parametrize("pattern", ["iPhone", "Android", "Windows"])
def test_each_platform_family_is_recognised(pattern):
    assert pattern in _fn("biometricName")


def test_an_unknown_platform_stays_generic():
    """Three families are named; everything else gets wording that is true
    everywhere rather than a fourth guess."""
    body = _fn("biometricName")
    # The last return in the body, not the last line of the extracted text: the
    # extraction carries the following function's doc comment with it.
    returns = re.findall(r"return ('[^']+');", body)
    assert returns[-1] == "'your fingerprint or face'", returns


def test_a_device_with_no_biometric_keeps_the_passkey_wording():
    """A security key or a phone-by-QR still works. The label must not promise a
    fingerprint to a desktop that has no reader."""
    body = _fn("passkeyButtonLabel")
    assert "platformAuth ?" in body
    assert "'Sign in with a passkey'" in body


def test_the_button_still_teaches_the_word_passkey():
    """The concept has to stay learnable, and the security-key path
    discoverable, or the label has traded one confusion for another."""
    # All three fragments of the concatenated title. Checking two of them passed
    # with the third deleted, which is how a sentence loses its ending.
    assert "Uses the passkey saved on this device" in AUTH_JS
    assert "security key or your" in AUTH_JS
    assert "phone works too" in AUTH_JS


def test_the_promotion_banner_uses_the_same_name():
    """It hardcoded "Face ID, Touch ID or your device PIN" on every platform,
    including Android and Windows."""
    assert "Set up a passkey and use ' + esc(biometricName())" in AUTH_JS


def test_the_settings_page_names_every_route():
    """Settings is where someone chooses, so it lists all of them rather than
    the one this device happens to have."""
    block = APP_JS.split("Passkeys <span", 1)[1][:400]
    for word in ("Face ID", "Touch ID", "Windows Hello", "device PIN", "hardware key"):
        assert word in block, word


def test_the_helpers_are_exported():
    """So the Settings page and a test can read the same wording rather than
    each spelling it."""
    assert "biometricName: biometricName," in AUTH_JS
    assert "platformAuthenticator: askPlatformAuthenticator," in AUTH_JS
