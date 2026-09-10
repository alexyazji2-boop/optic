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


# ------------------------------------------------ the button that did nothing

def test_the_autofill_request_is_released_before_an_explicit_one():
    """The bug behind "the Face ID sign in button is not working".

    A browser allows exactly one navigator.credentials.get() at a time, and
    paint() arms a conditional-mediation request on every render of the sign-in
    modal. Pressing the button started a second call while the first was still
    outstanding, so the browser rejected it — reproduced on the live site and on
    localhost as `OperationError: A request is already pending.` The abort
    existed but only ran in close(), so the collision was guaranteed for anyone
    who pressed the button instead of using the autofill dropdown.
    """
    assert "function stopConditionalPasskey()" in AUTH_JS
    block = AUTH_JS.split("closest('[data-passkey-signin]')", 1)[1].split("\n    }", 1)[0]
    assert "stopConditionalPasskey().then(" in block
    assert block.index("stopConditionalPasskey") < block.index("signInWithPasskey")


def test_the_slot_is_released_on_its_own_turn():
    """abort() is synchronous but the browser frees the slot on its own turn.
    Retrying in the same tick fails the same way."""
    body = _fn("stopConditionalPasskey")
    assert "setTimeout(done, 0)" in body
    assert "conditionalAbort = null" in body


def test_a_second_press_cannot_collide_with_the_first():
    """Another pending request, and the same OperationError."""
    assert "var passkeyBusy = false;" in AUTH_JS
    block = AUTH_JS.split("closest('[data-passkey-signin]')", 1)[1].split("\n    }", 1)[0]
    assert "if (passkeyBusy) return;" in block
    assert "passkeyBusy = true;" in block
    # And it must be cleared on both outcomes, or the button locks up for good.
    assert block.count("passkeyBusy = false;") >= 2


def test_the_autofill_shortcut_comes_back_after_a_failed_press():
    """Aborted and never re-armed, the dropdown is dead for the rest of the
    modal's life — and dismissing the dialog to type an email is the most likely
    thing to happen next."""
    block = AUTH_JS.split("closest('[data-passkey-signin]')", 1)[1].split("\n    }", 1)[0]
    assert "armConditionalPasskey();" in block


def test_the_collision_still_has_a_message():
    """Unreachable from the button now, but an extension or a second tab can
    hold the slot, and "A request is already pending" alone tells a reader
    nothing they can act on."""
    body = _fn("passkeyMessage")
    assert "OperationError" in body
    assert "already pending" in body
    assert "reload this" in body


def test_an_empty_ceremony_is_explained_rather_than_swallowed():
    """NotAllowedError covers dismissal, timeout, and "there is no passkey on
    this device". Silence is right for the first two and a dead control for the
    third, so the one recorded fact — has this browser ever made a passkey —
    decides whether to explain."""
    assert "function passkeyNothingHappened(" in AUTH_JS
    body = _fn("passkeyNothingHappened")
    assert "passkeyMadeHere()" in body
    assert "err.name === 'AbortError'" in body, "the autofill teardown must stay silent"
    assert "biometricName()" in body, "the guidance should name what to set up"


def test_creating_a_passkey_records_that_it_happened():
    assert "rememberPasskeyMade();" in AUTH_JS
    body = _fn("createPasskey")
    assert "rememberPasskeyMade()" in body


def test_the_guidance_is_not_dressed_as_a_failure():
    """It reuses the error slot, where the reader is already looking, in the
    quiet .auth-note styling the stylesheet already defines."""
    body = _fn("showNote")
    assert "classList.remove('auth-error')" in body
    assert "classList.add('auth-note')" in body
    # And the styling is restored, or the next genuine error reads as advice.
    for name in ("showError", "clearError"):
        restored = _fn(name)
        assert "classList.add('auth-error')" in restored, name


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
