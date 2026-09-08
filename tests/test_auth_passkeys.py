"""Passkeys, end to end, against real WebAuthn verification.

`tests/webauthn_fixtures.py` builds the bytes a browser would return, including
a genuine P-256 signature, so py_webauthn does the checking here rather than a
stub. That matters because every interesting passkey bug lives in the parts a
mock would paper over: the RP id hash inside authData, the challenge binding,
the sign counter, and which account a credential belongs to.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.auth import config, passkeys as passkeys_mod, store
from webauthn_fixtures import SoftAuthenticator

client = TestClient(main.app)

GOOD = "tungsten-carbide-9"
ORIGIN = "http://localhost:8000"


@pytest.fixture(autouse=True)
def fresh(accounts):
    client.cookies.clear()
    return accounts


@pytest.fixture
def signed_in():
    client.post("/api/auth/register", json={
        "first_name": "Alex", "last_name": "Yazji", "email": "reader@example.com",
        "password": GOOD, "confirm_password": GOOD})
    return {"csrf": client.cookies.get(config.CSRF_COOKIE),
            "user": store.get_user_by_email("reader@example.com")}


def add_passkey(csrf, device=None, name=None):
    options = client.post("/api/auth/passkeys/register/options",
                          headers={"X-Optic-CSRF": csrf}).json()["options"]
    device = device or SoftAuthenticator(rp_id=config.rp_id())
    payload = {"credential": device.register(options["challenge"], ORIGIN)}
    if name:
        payload["name"] = name
    reply = client.post("/api/auth/passkeys/register/verify",
                        headers={"X-Optic-CSRF": csrf}, json=payload)
    return device, reply


def sign_in_with(device):
    options = client.post("/api/auth/passkeys/login/options").json()["options"]
    return client.post("/api/auth/passkeys/login/verify", json={
        "credential": device.authenticate(options["challenge"], ORIGIN)})


# ------------------------------------------------------------------ registration


def test_register_a_passkey_and_sign_in_with_it(signed_in):
    device, reply = add_passkey(signed_in["csrf"], name="MacBook Pro")
    assert reply.status_code == 200, reply.text
    saved = reply.json()["passkey"]
    assert saved["name"] == "MacBook Pro"
    assert saved["backed_up"] is True
    assert saved["transports"] == ["internal", "hybrid"]
    assert reply.json()["methods"]["passkeys"] == 1

    client.cookies.clear()
    signed = sign_in_with(device)
    assert signed.status_code == 200, signed.text
    assert signed.json()["user"]["email"] == "reader@example.com"
    assert client.get("/api/auth/me").json()["authenticated"] is True


def test_only_the_public_key_is_stored(signed_in):
    device, _ = add_passkey(signed_in["csrf"])
    row = store.passkey_by_credential(device.credential_id_b64)
    stored = bytes(row["public_key"])
    private = device.key.private_numbers().private_value.to_bytes(32, "big")
    assert private not in stored
    assert stored == device.cose_public_key()


def test_the_name_defaults_from_the_user_agent(signed_in):
    options = client.post("/api/auth/passkeys/register/options",
                          headers={"X-Optic-CSRF": signed_in["csrf"]}).json()["options"]
    device = SoftAuthenticator(rp_id=config.rp_id())
    reply = client.post(
        "/api/auth/passkeys/register/verify",
        headers={"X-Optic-CSRF": signed_in["csrf"],
                 "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                               "AppleWebKit/605.1.15 Safari/605.1.15"},
        json={"credential": device.register(options["challenge"], ORIGIN)})
    assert reply.json()["passkey"]["name"] == "Safari on Mac"


def test_registering_needs_a_session():
    assert client.post("/api/auth/passkeys/register/options").status_code == 401
    assert client.post("/api/auth/passkeys/register/verify",
                       json={"credential": {}}).status_code == 401


def test_the_same_authenticator_is_excluded_from_a_second_registration(signed_in):
    device, _ = add_passkey(signed_in["csrf"])
    options = client.post("/api/auth/passkeys/register/options",
                          headers={"X-Optic-CSRF": signed_in["csrf"]}).json()["options"]
    excluded = [c["id"] for c in options["excludeCredentials"]]
    assert device.credential_id_b64 in excluded


def test_two_different_devices_can_both_be_registered(signed_in):
    first, _ = add_passkey(signed_in["csrf"], name="Mac")
    second, reply = add_passkey(signed_in["csrf"],
                                SoftAuthenticator(rp_id=config.rp_id()), name="iPhone")
    assert reply.status_code == 200
    assert reply.json()["methods"]["passkeys"] == 2
    client.cookies.clear()
    assert sign_in_with(second).status_code == 200


# ------------------------------------------------- challenges and replay


def test_a_registration_challenge_works_once(signed_in):
    options = client.post("/api/auth/passkeys/register/options",
                          headers={"X-Optic-CSRF": signed_in["csrf"]}).json()["options"]
    device = SoftAuthenticator(rp_id=config.rp_id())
    body = {"credential": device.register(options["challenge"], ORIGIN)}
    assert client.post("/api/auth/passkeys/register/verify",
                       headers={"X-Optic-CSRF": signed_in["csrf"]},
                       json=body).status_code == 200
    replay = client.post("/api/auth/passkeys/register/verify",
                         headers={"X-Optic-CSRF": signed_in["csrf"]}, json=body)
    assert replay.status_code == 400
    assert "expired" in replay.json()["detail"]


def test_an_authentication_assertion_cannot_be_replayed(signed_in):
    device, _ = add_passkey(signed_in["csrf"])
    client.cookies.clear()
    options = client.post("/api/auth/passkeys/login/options").json()["options"]
    body = {"credential": device.authenticate(options["challenge"], ORIGIN)}
    assert client.post("/api/auth/passkeys/login/verify", json=body).status_code == 200
    client.cookies.clear()
    replay = client.post("/api/auth/passkeys/login/verify", json=body)
    assert replay.status_code == 401
    # The challenge row is deleted on use, so this fails on the lookup.
    assert "expired" in replay.json()["detail"]


def test_an_expired_challenge_is_refused(signed_in):
    device, _ = add_passkey(signed_in["csrf"])
    client.cookies.clear()
    options = client.post("/api/auth/passkeys/login/options").json()["options"]
    main.accounts_db.execute("UPDATE webauthn_challenges SET expires_at = ?",
                             (main.accounts_db.in_seconds(-10),))
    reply = client.post("/api/auth/passkeys/login/verify", json={
        "credential": device.authenticate(options["challenge"], ORIGIN)})
    assert reply.status_code == 401


def test_a_challenge_the_server_never_issued_is_refused(signed_in):
    device, _ = add_passkey(signed_in["csrf"])
    client.cookies.clear()
    reply = client.post("/api/auth/passkeys/login/verify", json={
        "credential": device.authenticate("aW52ZW50ZWQtY2hhbGxlbmdl", ORIGIN)})
    assert reply.status_code == 401


def test_login_options_never_list_credentials(signed_in):
    add_passkey(signed_in["csrf"])
    client.cookies.clear()
    options = client.post("/api/auth/passkeys/login/options").json()["options"]
    # A populated list here would answer "does this person have a passkey" for
    # any address handed to it.
    assert options.get("allowCredentials") == []


# ------------------------------------------------------- origin and rp id


def test_an_assertion_from_another_origin_is_refused(signed_in):
    device, _ = add_passkey(signed_in["csrf"])
    client.cookies.clear()
    options = client.post("/api/auth/passkeys/login/options").json()["options"]
    reply = client.post("/api/auth/passkeys/login/verify", json={
        "credential": device.authenticate(options["challenge"],
                                          "https://evil.example")})
    assert reply.status_code == 401


def test_a_credential_made_for_another_rp_id_is_refused(signed_in):
    """The RP id hash lives inside authData, so a passkey minted for another
    site cannot be presented here even with a valid signature."""
    options = client.post("/api/auth/passkeys/register/options",
                          headers={"X-Optic-CSRF": signed_in["csrf"]}).json()["options"]
    impostor = SoftAuthenticator(rp_id="evil.example")
    reply = client.post("/api/auth/passkeys/register/verify",
                        headers={"X-Optic-CSRF": signed_in["csrf"]},
                        json={"credential": impostor.register(options["challenge"],
                                                              ORIGIN)})
    assert reply.status_code == 400
    assert store.passkey_by_credential(impostor.credential_id_b64) is None


def test_a_tampered_signature_is_refused(signed_in):
    device, _ = add_passkey(signed_in["csrf"])
    client.cookies.clear()
    options = client.post("/api/auth/passkeys/login/options").json()["options"]
    credential = device.authenticate(options["challenge"], ORIGIN)
    signature = credential["response"]["signature"]
    credential["response"]["signature"] = ("A" if signature[0] != "A" else "B") + signature[1:]
    reply = client.post("/api/auth/passkeys/login/verify", json={"credential": credential})
    assert reply.status_code == 401


def test_an_unregistered_credential_and_a_bad_signature_read_the_same(signed_in):
    device, _ = add_passkey(signed_in["csrf"])
    stranger = SoftAuthenticator(rp_id=config.rp_id())
    client.cookies.clear()

    options = client.post("/api/auth/passkeys/login/options").json()["options"]
    unknown = client.post("/api/auth/passkeys/login/verify", json={
        "credential": stranger.authenticate(options["challenge"], ORIGIN)})

    options = client.post("/api/auth/passkeys/login/options").json()["options"]
    credential = device.authenticate(options["challenge"], ORIGIN)
    credential["response"]["signature"] = "AAAA" + credential["response"]["signature"][4:]
    bad = client.post("/api/auth/passkeys/login/verify", json={"credential": credential})

    assert unknown.status_code == bad.status_code == 401
    assert unknown.json()["detail"] == bad.json()["detail"]


# -------------------------------------------------------------- sign counter


def test_a_counting_authenticator_must_keep_counting(signed_in):
    """A counter that has been non-zero and then stops advancing is the clone
    signal, and it is the one case where refusing is correct."""
    device = SoftAuthenticator(rp_id=config.rp_id(), counter=5)
    _device, reply = add_passkey(signed_in["csrf"], device)
    assert reply.status_code == 200
    assert store.passkey_by_credential(device.credential_id_b64)["counter"] == 5

    client.cookies.clear()
    assert sign_in_with(device).status_code == 401       # replayed at 5

    options = client.post("/api/auth/passkeys/login/options").json()["options"]
    advanced = client.post("/api/auth/passkeys/login/verify", json={
        "credential": device.authenticate(options["challenge"], ORIGIN, bump=1)})
    assert advanced.status_code == 200
    assert store.passkey_by_credential(device.credential_id_b64)["counter"] == 6


def test_an_apple_style_zero_counter_still_works_every_time(signed_in):
    """Synced platform passkeys report zero forever. Refusing `new <= stored`
    outright would break every Apple passkey on its second use."""
    device = SoftAuthenticator(rp_id=config.rp_id(), counter=0)
    add_passkey(signed_in["csrf"], device)
    client.cookies.clear()
    for _ in range(3):
        assert sign_in_with(device).status_code == 200
        client.cookies.clear()
    assert store.passkey_by_credential(device.credential_id_b64)["counter"] == 0


# --------------------------------------------------------------- management


def test_rename_and_remove_are_scoped_to_the_owner(signed_in):
    device, reply = add_passkey(signed_in["csrf"], name="Mac")
    passkey_id = reply.json()["passkey"]["id"]
    csrf = signed_in["csrf"]

    renamed = client.patch("/api/auth/passkeys/{}".format(passkey_id),
                           headers={"X-Optic-CSRF": csrf}, json={"name": "MacBook Pro"})
    assert renamed.json()["passkeys"][0]["name"] == "MacBook Pro"

    # A second account cannot touch it.
    client.cookies.clear()
    client.post("/api/auth/register", json={
        "first_name": "Other", "email": "other@example.com",
        "password": GOOD, "confirm_password": GOOD})
    other_csrf = client.cookies.get(config.CSRF_COOKIE)
    assert client.patch("/api/auth/passkeys/{}".format(passkey_id),
                        headers={"X-Optic-CSRF": other_csrf},
                        json={"name": "Mine now"}).status_code == 404
    assert client.delete("/api/auth/passkeys/{}".format(passkey_id),
                         headers={"X-Optic-CSRF": other_csrf}).status_code == 404
    assert store.passkeys_for(signed_in["user"]["id"])[0]["name"] == "MacBook Pro"


def test_the_last_way_in_cannot_be_removed(signed_in):
    """Account recovery should not become a support ticket."""
    device, reply = add_passkey(signed_in["csrf"])
    passkey_id = reply.json()["passkey"]["id"]
    csrf = signed_in["csrf"]
    user_id = signed_in["user"]["id"]

    # Two ways in right now: password and passkey. Either may go.
    assert store.auth_methods(user_id)["count"] == 2
    assert client.delete("/api/auth/identities/email",
                         headers={"X-Optic-CSRF": csrf}).status_code == 200
    assert store.auth_methods(user_id)["count"] == 1

    refused = client.delete("/api/auth/passkeys/{}".format(passkey_id),
                            headers={"X-Optic-CSRF": csrf})
    assert refused.status_code == 400
    assert "only way into this account" in refused.json()["detail"]
    assert store.auth_methods(user_id)["count"] == 1
    # Still usable, which is the point of refusing.
    client.cookies.clear()
    assert sign_in_with(device).status_code == 200


def test_removing_a_passkey_when_another_way_in_exists(signed_in):
    device, reply = add_passkey(signed_in["csrf"])
    csrf = signed_in["csrf"]
    gone = client.delete("/api/auth/passkeys/{}".format(reply.json()["passkey"]["id"]),
                         headers={"X-Optic-CSRF": csrf})
    assert gone.status_code == 200
    assert gone.json()["methods"]["passkeys"] == 0
    client.cookies.clear()
    assert sign_in_with(device).status_code == 401


def test_the_last_provider_cannot_be_disconnected_either(signed_in):
    csrf = signed_in["csrf"]
    user_id = signed_in["user"]["id"]
    store.add_identity(user_id, "google", "sub-1", "reader@example.com")
    assert store.auth_methods(user_id)["count"] == 2

    # Drop the password, leaving Google as the only way in.
    assert client.delete("/api/auth/identities/email",
                         headers={"X-Optic-CSRF": csrf}).status_code == 200
    refused = client.delete("/api/auth/identities/google",
                            headers={"X-Optic-CSRF": csrf})
    assert refused.status_code == 400
    assert "only way into this account" in refused.json()["detail"]
    assert store.auth_methods(user_id)["providers"] == ["google"]


def test_disconnecting_a_password_clears_the_hash_as_well_as_the_identity(signed_in):
    csrf = signed_in["csrf"]
    user_id = signed_in["user"]["id"]
    store.add_identity(user_id, "google", "sub-1", "reader@example.com")
    client.delete("/api/auth/identities/email", headers={"X-Optic-CSRF": csrf})
    # An identity row without the hash gone would leave a working password on an
    # account that reports having none.
    assert store.get_password(user_id) is None
    client.cookies.clear()
    assert client.post("/api/auth/login", json={"email": "reader@example.com",
                                                "password": GOOD}).status_code == 401


def test_a_stale_passkey_row_cannot_authenticate_a_deleted_user(signed_in):
    device, _ = add_passkey(signed_in["csrf"])
    main.accounts_db.execute("DELETE FROM users WHERE id = ?", (signed_in["user"]["id"],))
    client.cookies.clear()
    # Cascade removed the credential with the account, so there is nothing to
    # present. That only holds because foreign keys are enabled per connection.
    assert store.passkey_by_credential(device.credential_id_b64) is None
    assert sign_in_with(device).status_code == 401
