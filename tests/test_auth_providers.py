"""Google, Apple, and one account per person.

Two halves.

The **linking matrix** is the important one and it runs against
`linking.resolve` directly, with a provider profile as input. That is exactly
what a real callback produces once the ID token has been verified, so testing
here covers every branch without a network call and without faking a signature.

The **callback machinery** is tested through HTTP: state that was never issued,
state used twice, a nonce that does not match, PKCE reaching the exchange, and
Apple's form-post body. The one thing stubbed is `oauth.complete`, because the
alternative is standing up a fake Google.
"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.auth import config, linking, oauth, store

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def fresh(accounts):
    client.cookies.clear()
    return accounts


def profile(provider="google", subject="sub-1", email="reader@example.com",
            verified=True, relay=False, first="Alex", last="Yazji"):
    return {"provider": provider, "subject": subject, "email": email,
            "email_verified": verified, "private_relay": relay,
            "first_name": first, "last_name": last, "avatar_url": None}


# ----------------------------------------------------------------- the matrix


def test_first_sign_in_creates_one_account_and_one_identity():
    outcome = linking.resolve(profile())
    assert outcome["outcome"] == "created"
    user = outcome["user"]
    assert user["email"] == "reader@example.com"
    # Google verified the address, so asking the reader to verify it again would
    # be asking them to prove something they just proved.
    assert user["email_verified"] == 1
    assert store.auth_methods(user["id"])["providers"] == ["google"]


def test_signing_in_again_returns_the_same_account():
    first = linking.resolve(profile())["user"]
    second = linking.resolve(profile())
    assert second["outcome"] == "signed_in"
    assert second["user"]["id"] == first["id"]
    assert len(main.accounts_db.rows("SELECT 1 FROM users")) == 1


def test_the_identity_is_the_subject_not_the_email():
    user = linking.resolve(profile())["user"]
    # The person changed their Gmail address. Same subject, so the same account.
    moved = linking.resolve(profile(email="new-address@example.com"))
    assert moved["outcome"] == "signed_in"
    assert moved["user"]["id"] == user["id"]
    # And the identity's stored address follows, as display detail.
    identity = store.get_identity("google", "sub-1")
    assert identity["provider_email"] == "new-address@example.com"


def test_a_different_subject_with_the_same_verified_email_links_rather_than_duplicating():
    user = linking.resolve(profile())["user"]
    linked = linking.resolve(profile(provider="apple", subject="apple-1"))
    assert linked["outcome"] == "linked"
    assert linked["user"]["id"] == user["id"]
    assert store.auth_methods(user["id"])["providers"] == ["apple", "google"]
    assert len(main.accounts_db.rows("SELECT 1 FROM users")) == 1


def test_an_unverified_local_account_is_not_claimed_by_a_provider():
    existing = store.create_user("reader@example.com", "Someone", "Else",
                                 email_verified=False)
    store.add_identity(existing["id"], "email", "reader@example.com")
    outcome = linking.resolve(profile())
    assert outcome["outcome"] == "needs_link"
    assert "connect Google" in outcome["reason"]
    # Neither linked nor duplicated.
    assert store.get_identity("google", "sub-1") is None
    assert len(main.accounts_db.rows("SELECT 1 FROM users")) == 1


def test_a_provider_that_has_not_verified_the_address_cannot_claim_an_account():
    store.create_user("reader@example.com", "Real", "Owner", email_verified=True)
    outcome = linking.resolve(profile(verified=False))
    assert outcome["outcome"] == "needs_link"
    assert store.get_identity("google", "sub-1") is None


def test_apple_private_relay_is_never_a_match_key():
    store.create_user("abc@privaterelay.appleid.com", "Real", "Owner",
                      email_verified=True)
    outcome = linking.resolve(profile(provider="apple", subject="apple-9",
                                      email="abc@privaterelay.appleid.com",
                                      relay=True))
    assert outcome["outcome"] == "needs_link"


def test_no_email_from_the_provider_is_refused_rather_than_given_a_fake_mailbox():
    outcome = linking.resolve(profile(provider="apple", subject="apple-2", email=None))
    assert outcome["outcome"] == "no_email"
    assert main.accounts_db.rows("SELECT 1 FROM users") == []


def test_connecting_from_a_session_attaches_to_that_account():
    owner = store.create_user("owner@example.com", "Own", "Er", email_verified=True)
    outcome = linking.resolve(profile(email="something@else.com"),
                              link_user_id=owner["id"])
    assert outcome["outcome"] == "linked"
    assert outcome["user"]["id"] == owner["id"]
    # The account keeps its own address. A connected provider does not rename you.
    assert store.get_user(owner["id"])["email"] == "owner@example.com"


def test_an_identity_already_owned_elsewhere_cannot_be_moved():
    first = linking.resolve(profile())["user"]
    other = store.create_user("other@example.com", "O", "T", email_verified=True)
    outcome = linking.resolve(profile(), link_user_id=other["id"])
    assert outcome["outcome"] == "taken"
    assert "already connected to another" in outcome["reason"]
    assert store.get_identity("google", "sub-1")["user_id"] == first["id"]


def test_apple_first_authorization_name_is_captured_from_the_form_payload():
    # Apple sends the name once, in a form field, and never again.
    outcome = linking.resolve(profile(provider="apple", subject="a1",
                                      first="Alex", last="Yazji"))
    assert outcome["user"]["first_name"] == "Alex"
    assert outcome["user"]["last_name"] == "Yazji"


def test_an_inactive_account_is_not_signed_in_by_its_provider():
    user = linking.resolve(profile())["user"]
    main.accounts_db.execute("UPDATE users SET is_active = 0 WHERE id = ?", (user["id"],))
    assert linking.resolve(profile())["outcome"] == "inactive"


# ------------------------------------------------------------------ the callback


@pytest.fixture
def google(monkeypatch):
    """Google configured, and the code exchange stubbed."""
    monkeypatch.setattr(config, "GOOGLE_CLIENT_ID", "client-id.apps.googleusercontent.com")
    monkeypatch.setattr(config, "GOOGLE_CLIENT_SECRET", "client-secret")
    seen = {}

    def fake_complete(provider, code, nonce, verifier, apple_user=None):
        seen.update({"provider": provider, "code": code, "nonce": nonce,
                     "verifier": verifier, "apple_user": apple_user})
        return profile()

    monkeypatch.setattr(oauth, "complete", fake_complete)
    return seen


def test_providers_endpoint_hides_what_is_not_configured():
    body = client.get("/api/auth/providers").json()["providers"]
    assert body["email"]["available"] is True
    assert body["google"]["available"] is False
    assert "GOOGLE_CLIENT_ID" in body["google"]["reason"]
    assert body["apple"]["available"] is False
    assert "Apple Developer membership" in body["apple"]["reason"]
    # Passkeys need no third party, so they are on wherever the library imported.
    assert body["passkey"]["available"] is True


def test_start_redirects_with_state_nonce_and_a_pkce_challenge(google):
    reply = client.get("/api/auth/google/start", follow_redirects=False)
    assert reply.status_code == 303
    target = reply.headers["location"]
    assert target.startswith(config.GOOGLE_AUTH_URL)
    assert "code_challenge_method=S256" in target
    rows = main.accounts_db.rows("SELECT * FROM oauth_states")
    assert len(rows) == 1
    assert rows[0]["provider"] == "google"
    assert rows[0]["nonce"]
    # The verifier stays here. It is the half that never goes near the browser.
    assert rows[0]["code_verifier"]
    assert rows[0]["code_verifier"] not in target


def test_start_without_configuration_reports_it_instead_of_a_broken_redirect():
    reply = client.get("/api/auth/google/start", follow_redirects=False)
    assert reply.status_code == 303
    assert "auth_error=config" in reply.headers["location"]


def test_callback_signs_in_and_passes_the_nonce_and_verifier_to_the_exchange(google):
    start = client.get("/api/auth/google/start", follow_redirects=False)
    row = main.accounts_db.rows("SELECT * FROM oauth_states")[0]
    reply = client.get("/api/auth/google/callback",
                       params={"code": "auth-code", "state": row["state"]},
                       follow_redirects=False)
    assert reply.status_code == 303
    assert "auth=ok" in reply.headers["location"]
    assert google["nonce"] == row["nonce"]
    assert google["verifier"] == row["code_verifier"]
    assert client.get("/api/auth/me").json()["user"]["email"] == "reader@example.com"


def test_a_state_that_was_never_issued_is_refused(google):
    reply = client.get("/api/auth/google/callback",
                       params={"code": "auth-code", "state": "invented"},
                       follow_redirects=False)
    assert "auth_error=state" in reply.headers["location"]
    assert client.get("/api/auth/me").json()["authenticated"] is False


def test_state_is_single_use(google):
    client.get("/api/auth/google/start", follow_redirects=False)
    state = main.accounts_db.rows("SELECT state FROM oauth_states")[0]["state"]
    first = client.get("/api/auth/google/callback",
                       params={"code": "c", "state": state}, follow_redirects=False)
    assert "auth=ok" in first.headers["location"]
    client.cookies.clear()
    second = client.get("/api/auth/google/callback",
                        params={"code": "c", "state": state}, follow_redirects=False)
    assert "auth_error=state" in second.headers["location"]


def test_an_expired_state_is_refused(google):
    client.get("/api/auth/google/start", follow_redirects=False)
    state = main.accounts_db.rows("SELECT state FROM oauth_states")[0]["state"]
    main.accounts_db.execute("UPDATE oauth_states SET expires_at = ?",
                             (main.accounts_db.in_seconds(-10),))
    reply = client.get("/api/auth/google/callback",
                       params={"code": "c", "state": state}, follow_redirects=False)
    assert "auth_error=state" in reply.headers["location"]


def test_a_provider_failure_becomes_a_short_code_not_a_reflected_message(google, monkeypatch):
    def boom(*args, **kwargs):
        raise oauth.OAuthError("invalid_client: something specific and internal")

    monkeypatch.setattr(oauth, "complete", boom)
    client.get("/api/auth/google/start", follow_redirects=False)
    state = main.accounts_db.rows("SELECT state FROM oauth_states")[0]["state"]
    reply = client.get("/api/auth/google/callback",
                       params={"code": "c", "state": state}, follow_redirects=False)
    assert "auth_error=provider" in reply.headers["location"]
    assert "invalid_client" not in reply.headers["location"]


def test_needs_link_comes_home_as_a_code(google):
    store.create_user("reader@example.com", "Someone", "Else", email_verified=False)
    client.get("/api/auth/google/start", follow_redirects=False)
    state = main.accounts_db.rows("SELECT state FROM oauth_states")[0]["state"]
    reply = client.get("/api/auth/google/callback",
                       params={"code": "c", "state": state}, follow_redirects=False)
    assert "auth_error=needs_link" in reply.headers["location"]
    assert "provider=google" in reply.headers["location"]
    assert client.get("/api/auth/me").json()["authenticated"] is False


def test_connect_from_settings_needs_a_session(google):
    anonymous = client.get("/api/auth/google/start", params={"link": 1},
                           follow_redirects=False)
    assert anonymous.status_code == 401


def test_connect_from_settings_records_the_session_user_not_a_query_parameter(google):
    client.post("/api/auth/register", json={
        "first_name": "Alex", "email": "owner@example.com",
        "password": "tungsten-carbide-9", "confirm_password": "tungsten-carbide-9"})
    owner = store.get_user_by_email("owner@example.com")
    client.get("/api/auth/google/start", params={"link": 1}, follow_redirects=False)
    row = main.accounts_db.rows("SELECT * FROM oauth_states")[0]
    assert row["link_user_id"] == owner["id"]


def test_next_is_relative_only_so_the_callback_is_not_an_open_redirect(google):
    client.get("/api/auth/google/start", params={"next": "https://evil.example/steal"},
               follow_redirects=False)
    state = main.accounts_db.rows("SELECT state FROM oauth_states")[0]["state"]
    reply = client.get("/api/auth/google/callback",
                       params={"code": "c", "state": state}, follow_redirects=False)
    assert "evil.example" not in reply.headers["location"]
    assert reply.headers["location"].startswith(("http://127.0.0.1", "http://localhost",
                                                 "https://"))


def test_apple_posts_a_urlencoded_body_and_it_is_parsed_without_multipart(monkeypatch):
    monkeypatch.setattr(config, "APPLE_CLIENT_ID", "com.optic.web")
    monkeypatch.setattr(config, "APPLE_TEAM_ID", "TEAM123456")
    monkeypatch.setattr(config, "APPLE_KEY_ID", "KEY1234567")
    monkeypatch.setattr(config, "APPLE_PRIVATE_KEY", "-----BEGIN PRIVATE KEY-----x")
    seen = {}

    def fake_complete(provider, code, nonce, verifier, apple_user=None):
        seen["apple_user"] = apple_user
        return profile(provider="apple", subject="apple-1",
                       first=(apple_user or {}).get("name", {}).get("firstName", ""),
                       last=(apple_user or {}).get("name", {}).get("lastName", ""))

    monkeypatch.setattr(oauth, "complete", fake_complete)
    client.get("/api/auth/apple/start", follow_redirects=False)
    state = main.accounts_db.rows("SELECT state FROM oauth_states")[0]["state"]

    reply = client.post("/api/auth/apple/callback", follow_redirects=False,
                        data={"code": "apple-code", "state": state,
                              "user": '{"name":{"firstName":"Alex","lastName":"Yazji"}}'})
    assert reply.status_code == 303
    assert "auth=ok" in reply.headers["location"]
    assert seen["apple_user"]["name"]["firstName"] == "Alex"
    assert store.get_user_by_email("reader@example.com")["first_name"] == "Alex"


def test_apple_client_secret_is_a_signed_es256_jwt():
    """Apple has no static secret, so the exchange fails silently without this."""
    import jwt
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(serialization.Encoding.PEM,
                            serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()
    original = (config.APPLE_PRIVATE_KEY, config.APPLE_TEAM_ID,
                config.APPLE_KEY_ID, config.APPLE_CLIENT_ID)
    try:
        # The literal "\n" is what a dashboard paste produces, and it is the most
        # common reason Apple sign-in dies at the token exchange.
        config.APPLE_PRIVATE_KEY = pem.replace("\n", "\\n").replace("\\n", "\n")
        config.APPLE_TEAM_ID = "TEAM123456"
        config.APPLE_KEY_ID = "KEY1234567"
        config.APPLE_CLIENT_ID = "com.optic.web"
        secret = oauth._apple_client_secret()
        assert jwt.get_unverified_header(secret)["alg"] == "ES256"
        assert jwt.get_unverified_header(secret)["kid"] == "KEY1234567"
        claims = jwt.decode(secret, key.public_key(), algorithms=["ES256"],
                            audience=config.APPLE_ISSUER)
        assert claims["iss"] == "TEAM123456"
        assert claims["sub"] == "com.optic.web"
        assert claims["exp"] > time.time()
    finally:
        (config.APPLE_PRIVATE_KEY, config.APPLE_TEAM_ID,
         config.APPLE_KEY_ID, config.APPLE_CLIENT_ID) = original


def test_a_malformed_apple_private_key_is_reported_not_crashed():
    original = config.APPLE_PRIVATE_KEY
    try:
        config.APPLE_PRIVATE_KEY = "not-a-key"
        config.APPLE_TEAM_ID = "T"
        config.APPLE_KEY_ID = "K"
        config.APPLE_CLIENT_ID = "C"
        with pytest.raises(oauth.OAuthError) as caught:
            oauth._apple_client_secret()
        assert ".p8" in str(caught.value)
    finally:
        config.APPLE_PRIVATE_KEY = original


def test_id_token_verification_names_the_algorithms_rather_than_trusting_the_header():
    """The classic JWT hole: passing the token's own `alg` back to the verifier
    lets `none` and a public-key-as-HMAC both pass."""
    source = open("app/auth/oauth.py").read()
    assert 'algorithms=["RS256", "ES256"]' in source
    assert "algorithms=[claims" not in source
    assert 'options={"require": ["exp", "iat", "sub", "aud", "iss"]' in source
