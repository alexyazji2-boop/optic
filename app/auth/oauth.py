"""Google and Apple sign-in.

**What is hand-written here and what is not.** The redirect dance is HTTP: build
a URL, receive a code, POST the code for a token. That part is written out
because it is three requests and a library for it would be a dependency for
plumbing. The cryptography is not: the ID token's signature is verified by PyJWT
against the provider's published JWKS, and Apple's client secret is signed by
PyJWT too. There is no place in this file where a signature is checked by
comparing strings.

**Four things every callback checks, and what breaks without each.**

* **state** — issued by us, stored server-side, deleted on use. Without it, an
  attacker can complete a flow they started and land their own provider account
  in your session (login CSRF).
* **PKCE** — a `code_verifier` we keep and never send to the browser. Without it,
  a code intercepted from the redirect can be redeemed by whoever holds it,
  since the code travels through the user agent.
* **nonce** — echoed inside the signed ID token. Without it, a token minted for
  a different login of the same app can be replayed into this one.
* **the signature, issuer and audience** — via JWKS. Without them, the ID token
  is just JSON somebody sent us.

**Why state lives in the database rather than a cookie.** Apple posts its
callback from `appleid.apple.com` with `response_mode=form_post`, and a
cross-site POST does not carry a SameSite=Lax cookie. A cookie-based state would
therefore be absent exactly when Apple is the provider, and the usual fix is to
weaken the cookie to SameSite=None. Storing state server-side keeps the cookie
strict and makes the check independent of what the browser chose to send.

Setting the session cookie *in the response to* that cross-site POST is fine:
SameSite governs which requests carry a cookie, not which responses may set one.
The response then redirects to a top-level GET on this origin, which Lax allows.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
import time
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode

import jwt
import requests
from jwt import PyJWKClient

from . import config

log = logging.getLogger("optic.oauth")

# JWKS is fetched over the network and the keys rotate slowly, so the client
# caches them. Module level: one cache per process rather than one per callback,
# which would mean a network round trip on every sign-in.
_JWKS: Dict[str, PyJWKClient] = {}

HTTP_TIMEOUT = 12


def _jwks(url: str) -> PyJWKClient:
    if url not in _JWKS:
        _JWKS[url] = PyJWKClient(url, cache_keys=True, lifespan=3600)
    return _JWKS[url]


def _pkce_pair() -> Tuple[str, str]:
    """(verifier, challenge). S256, which is the only method to use: `plain`
    sends the verifier through the browser and protects nothing."""
    verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


class OAuthError(Exception):
    """A failure with a message that is safe to show a person.

    Provider errors are not passed through verbatim. `invalid_client` means
    nothing to a reader and can disclose configuration; the caller gets a
    sentence about what to do and the detail goes to the log."""


# ------------------------------------------------------------------ authorize


def start(provider: str,
          state: str,
          nonce: str) -> Tuple[str, Optional[str]]:
    """(authorize_url, code_verifier)."""
    if provider == "google":
        status = config.google_status()
        if not status["available"]:
            raise OAuthError(status["reason"])
        verifier, challenge = _pkce_pair()
        query = {
            "client_id": config.GOOGLE_CLIENT_ID,
            "redirect_uri": config.redirect_uri("google"),
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            # Ask every time rather than silently reusing a stale grant. Without
            # it, a reader who removed the connection in Settings is signed
            # straight back in by one click with no chance to pick an account.
            "prompt": "select_account",
        }
        return config.GOOGLE_AUTH_URL + "?" + urlencode(query), verifier

    if provider == "apple":
        status = config.apple_status()
        if not status["available"]:
            raise OAuthError(status["reason"])
        verifier, challenge = _pkce_pair()
        query = {
            "client_id": config.APPLE_CLIENT_ID,
            "redirect_uri": config.redirect_uri("apple"),
            "response_type": "code",
            "scope": "name email",
            # Required by Apple whenever a scope is requested. It also means the
            # callback arrives as a POST, which is why state is not in a cookie.
            "response_mode": "form_post",
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        return config.APPLE_AUTH_URL + "?" + urlencode(query), verifier

    raise OAuthError("Unknown sign-in provider.")


# ------------------------------------------------------------- apple secret


def _apple_client_secret() -> str:
    """Apple has no static client secret. It wants a short-lived ES256 JWT signed
    with the .p8 key from the developer portal, where `iss` is the team, `sub` is
    the Service ID and `aud` is Apple. Six months is Apple's maximum lifetime;
    ten minutes is used because this is minted per exchange and a long-lived
    bearer assertion sitting in memory buys nothing."""
    now = int(time.time())
    payload = {
        "iss": config.APPLE_TEAM_ID,
        "iat": now,
        "exp": now + 600,
        "aud": config.APPLE_ISSUER,
        "sub": config.APPLE_CLIENT_ID,
    }
    try:
        return jwt.encode(payload, config.APPLE_PRIVATE_KEY, algorithm="ES256",
                          headers={"kid": config.APPLE_KEY_ID})
    except Exception as exc:                      # a malformed .p8 is the usual cause
        log.warning("apple client secret could not be signed: %s", exc)
        raise OAuthError(
            "The Apple private key in this deployment could not be read. Paste the "
            "whole .p8 file contents, including the BEGIN and END lines.")


# ------------------------------------------------------------ code exchange


def _exchange(provider: str, code: str, code_verifier: Optional[str]) -> Dict[str, Any]:
    if provider == "google":
        url = config.GOOGLE_TOKEN_URL
        data = {
            "code": code,
            "client_id": config.GOOGLE_CLIENT_ID,
            "client_secret": config.GOOGLE_CLIENT_SECRET,
            "redirect_uri": config.redirect_uri("google"),
            "grant_type": "authorization_code",
        }
    else:
        url = config.APPLE_TOKEN_URL
        data = {
            "code": code,
            "client_id": config.APPLE_CLIENT_ID,
            "client_secret": _apple_client_secret(),
            "redirect_uri": config.redirect_uri("apple"),
            "grant_type": "authorization_code",
        }
    if code_verifier:
        data["code_verifier"] = code_verifier

    try:
        response = requests.post(url, data=data, timeout=HTTP_TIMEOUT,
                                 headers={"Accept": "application/json"})
    except requests.RequestException as exc:
        log.warning("%s token exchange transport error: %s", provider, exc)
        raise OAuthError("Could not reach {} to finish signing in. Try again.".format(
            provider.title()))

    if response.status_code >= 400:
        # Logged, not returned: the body can name the client id and the exact
        # misconfiguration, which is useful in a log and not in a browser.
        log.warning("%s token exchange failed %s: %s", provider, response.status_code,
                    response.text[:400])
        raise OAuthError("{} refused to complete the sign-in. If this keeps happening "
                         "the connection needs reconfiguring.".format(provider.title()))
    try:
        return response.json()
    except ValueError:
        raise OAuthError("{} returned something unreadable.".format(provider.title()))


def _verify_id_token(provider: str, id_token: str, nonce: str) -> Dict[str, Any]:
    if provider == "google":
        jwks_url, audience, issuers = (config.GOOGLE_JWKS_URL, config.GOOGLE_CLIENT_ID,
                                       config.GOOGLE_ISSUERS)
    else:
        jwks_url, audience, issuers = (config.APPLE_JWKS_URL, config.APPLE_CLIENT_ID,
                                       (config.APPLE_ISSUER,))
    try:
        key = _jwks(jwks_url).get_signing_key_from_jwt(id_token)
        claims = jwt.decode(
            id_token,
            key.key,
            # The provider's advertised algorithms, listed explicitly. Passing
            # the token's own `alg` back in is the classic JWT hole: `none` and
            # HS256-signed-with-the-public-key both verify.
            algorithms=["RS256", "ES256"],
            audience=audience,
            options={"require": ["exp", "iat", "sub", "aud", "iss"],
                     "verify_exp": True, "verify_aud": True, "verify_iss": False},
        )
    except jwt.PyJWTError as exc:
        log.warning("%s id_token rejected: %s", provider, exc)
        raise OAuthError("The sign-in token from {} could not be verified.".format(
            provider.title()))
    except requests.RequestException as exc:
        log.warning("%s jwks fetch failed: %s", provider, exc)
        raise OAuthError("Could not fetch {}'s signing keys. Try again.".format(
            provider.title()))

    # Issuer is checked here rather than by PyJWT because Google publishes two
    # spellings of its own issuer and PyJWT accepts a single string.
    if claims.get("iss") not in issuers:
        raise OAuthError("The sign-in token from {} named an unexpected issuer.".format(
            provider.title()))

    # The nonce binds this token to the authorize request we issued. A token
    # without one, when we sent one, is a token from a different flow.
    if nonce and claims.get("nonce") != nonce:
        log.warning("%s nonce mismatch", provider)
        raise OAuthError("That sign-in attempt has expired. Start again.")
    return claims


def _truthy(value: Any) -> bool:
    """Apple sends `email_verified` as the string "true" in some responses and a
    boolean in others, and Google sends a boolean. `bool("false")` is True, so
    this cannot be left to Python."""
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes")


def complete(provider: str,
             code: str,
             nonce: str,
             code_verifier: Optional[str],
             apple_user_json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Exchange the code and return a normalised profile.

    `subject` is the only field that identifies the account. Everything else is
    display detail that the provider is free to change between sign-ins."""
    payload = _exchange(provider, code, code_verifier)
    id_token = payload.get("id_token")
    if not id_token:
        raise OAuthError("{} did not return an identity token.".format(provider.title()))
    claims = _verify_id_token(provider, id_token, nonce)

    subject = claims.get("sub")
    if not subject:
        raise OAuthError("{} did not identify the account.".format(provider.title()))

    email = (claims.get("email") or "").strip().lower() or None
    verified = _truthy(claims.get("email_verified"))

    if provider == "google":
        first = (claims.get("given_name") or "").strip()
        last = (claims.get("family_name") or "").strip()
        avatar = claims.get("picture") or None
        private_relay = False
    else:
        # Apple sends the name exactly once, in a form field on the first
        # authorization, and never again. If it is not captured now it is gone:
        # a second sign-in returns only the subject and the email. There is no
        # endpoint to ask later.
        name = (apple_user_json or {}).get("name") or {}
        first = str(name.get("firstName") or "").strip()
        last = str(name.get("lastName") or "").strip()
        avatar = None
        # Private relay: Apple mints a per-app forwarding address. It is a real
        # deliverable mailbox, so it counts as verified, but it is meaningless
        # as an identifier for matching an existing account, because the same
        # person has a different one at every app.
        private_relay = _truthy(claims.get("is_private_email"))

    return {
        "provider": provider,
        "subject": str(subject),
        "email": email,
        "email_verified": verified,
        "first_name": first,
        "last_name": last,
        "avatar_url": avatar,
        "private_relay": private_relay,
    }
