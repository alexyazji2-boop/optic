"""Everything the auth layer reads from the environment, in one place.

Each provider reports whether it is configured and, when it is not, *what is
missing*. That is the same contract the assistant already uses (`ai.available()`
returns a reason, not a bare False) and it exists for the same reason: a feature
that is dark because a variable is unset should say so, not look broken.

Nothing here has a default that would be a security decision. There is no
fallback signing key, no default client secret, and no development bypass that
could survive into production by accident.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from ..runtime import base_url, is_hosted

# --------------------------------------------------------------- sessions

COOKIE_NAME = "optic_session"
CSRF_COOKIE = "optic_csrf"

# 30 days, slid forward on use. Long because this is a research tool people come
# back to weekly, not a bank; the mitigation for a long-lived session is that it
# can be revoked from Settings and is destroyed by a password change.
SESSION_TTL = int(os.environ.get("SESSION_TTL_SECONDS", str(30 * 24 * 3600)))

# One-time links. Fifteen minutes for a reset is short enough that a link sitting
# in a mailbox is not a standing key; a day for verification because people read
# a signup email later.
RESET_TTL = int(os.environ.get("RESET_TTL_SECONDS", "900"))
VERIFY_TTL = int(os.environ.get("VERIFY_TTL_SECONDS", str(24 * 3600)))
OAUTH_STATE_TTL = 600
WEBAUTHN_CHALLENGE_TTL = 300


def cookie_secure() -> bool:
    """Secure in production, not locally.

    Hard-coding True would make sign-in impossible on http://127.0.0.1 — the
    browser silently drops a Secure cookie on a plain-HTTP origin, so the login
    request succeeds and the next request is anonymous, which reads as a broken
    session rather than a cookie policy. Hard-coding False would send session
    tokens in the clear on the public site."""
    if os.environ.get("COOKIE_SECURE", "").strip().lower() in ("1", "true", "yes"):
        return True
    if os.environ.get("COOKIE_SECURE", "").strip().lower() in ("0", "false", "no"):
        return False
    return is_hosted()


def cookie_kwargs(max_age: int) -> Dict[str, Any]:
    """SameSite=Lax, not Strict.

    Strict would refuse to send the cookie on any top-level navigation that
    started somewhere else — including the return leg of an OAuth redirect and
    every link to the site from an email. Lax withholds it from cross-site
    POSTs, which is the CSRF case; the remaining exposure is a cross-site GET,
    and no endpoint here changes state on GET."""
    return {
        "max_age": max_age,
        "httponly": True,
        "secure": cookie_secure(),
        "samesite": "lax",
        "path": "/",
    }


# ------------------------------------------------------------------ webauthn


def rp_id() -> str:
    """The Relying Party id: the domain a passkey is bound to.

    It must be the site's registrable domain or a parent of it. Getting it wrong
    does not degrade gracefully — the browser rejects the ceremony outright with
    a SecurityError, and a passkey registered under the wrong id can never be
    used. Derived from APP_URL so it cannot drift from the origin."""
    explicit = (os.environ.get("WEBAUTHN_RP_ID") or "").strip()
    if explicit:
        return explicit
    host = urlparse(base_url()).hostname or "localhost"
    # An IP address is not a valid RP id. The spec requires a domain, and
    # browsers reject 127.0.0.1 with a SecurityError before any request is made
    # — so a local checkout served on 127.0.0.1 would have passkeys that fail
    # with no server-side trace. `localhost` is the one host browsers treat as a
    # secure context over plain HTTP, so that is the local answer; reach the dev
    # server at http://localhost:8000 rather than the loopback address to
    # register or use one.
    if host.replace(".", "").isdigit() or host == "::1":
        return "localhost"
    return host


def rp_name() -> str:
    return os.environ.get("WEBAUTHN_RP_NAME", "Optic Terminal")


def expected_origins() -> List[str]:
    """Origins a WebAuthn response may claim to come from.

    A list rather than one string because the same deployment is legitimately
    reachable at more than one origin — the Railway domain and the custom domain
    during a DNS move — and an assertion from the other one is not an attack.
    Everything not in this list is rejected."""
    origins = [base_url()]
    extra = (os.environ.get("WEBAUTHN_ORIGIN") or "").strip()
    for candidate in extra.split(","):
        candidate = candidate.strip().rstrip("/")
        if candidate and candidate not in origins:
            origins.append(candidate)
    if not is_hosted():
        for local in ("http://localhost:8000", "http://127.0.0.1:8000"):
            if local not in origins:
                origins.append(local)
    return origins


# ------------------------------------------------------------------- google

GOOGLE_CLIENT_ID = (os.environ.get("GOOGLE_CLIENT_ID") or "").strip()
GOOGLE_CLIENT_SECRET = (os.environ.get("GOOGLE_CLIENT_SECRET") or "").strip()
GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"

# --------------------------------------------------------------------- apple

APPLE_CLIENT_ID = (os.environ.get("APPLE_CLIENT_ID") or "").strip()
APPLE_TEAM_ID = (os.environ.get("APPLE_TEAM_ID") or "").strip()
APPLE_KEY_ID = (os.environ.get("APPLE_KEY_ID") or "").strip()
# The .p8 contents. Newlines survive a dashboard paste badly, so a literal "\n"
# is accepted and converted — that one detail is the most common reason Apple
# sign-in fails at the token exchange with an unhelpful "invalid_client".
APPLE_PRIVATE_KEY = (os.environ.get("APPLE_PRIVATE_KEY") or "").replace("\\n", "\n").strip()
APPLE_ISSUER = "https://appleid.apple.com"
APPLE_AUTH_URL = "https://appleid.apple.com/auth/authorize"
APPLE_TOKEN_URL = "https://appleid.apple.com/auth/token"
APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"


def redirect_uri(provider: str) -> str:
    return "{}/api/auth/{}/callback".format(base_url(), provider)


def google_status() -> Dict[str, Any]:
    missing = [name for name, value in (("GOOGLE_CLIENT_ID", GOOGLE_CLIENT_ID),
                                        ("GOOGLE_CLIENT_SECRET", GOOGLE_CLIENT_SECRET))
               if not value]
    if missing:
        return {"available": False,
                "reason": "Google sign-in needs {} in the environment.".format(
                    " and ".join(missing))}
    return {"available": True, "redirect_uri": redirect_uri("google")}


def apple_status() -> Dict[str, Any]:
    missing = [name for name, value in (("APPLE_CLIENT_ID", APPLE_CLIENT_ID),
                                        ("APPLE_TEAM_ID", APPLE_TEAM_ID),
                                        ("APPLE_KEY_ID", APPLE_KEY_ID),
                                        ("APPLE_PRIVATE_KEY", APPLE_PRIVATE_KEY))
               if not value]
    if missing:
        return {"available": False,
                "reason": "Sign in with Apple needs {} in the environment. It also "
                          "needs a paid Apple Developer membership, which is where "
                          "the Service ID and key come from.".format(", ".join(missing))}
    return {"available": True, "redirect_uri": redirect_uri("apple")}


def passkeys_status() -> Dict[str, Any]:
    """Passkeys need no third party and no credential, so they are available
    wherever the library imported. The check exists so the front end can treat
    all three providers the same way."""
    try:
        import webauthn  # noqa: F401
    except ImportError:
        return {"available": False,
                "reason": "Passkeys need the `webauthn` package. Run pip install -r "
                          "requirements.txt."}
    return {"available": True, "rp_id": rp_id()}


def providers() -> Dict[str, Any]:
    """What the login screen may offer. A button for an unconfigured provider is
    worse than a missing one: it looks like the site is broken."""
    return {
        "email": {"available": True},
        "google": google_status(),
        "apple": apple_status(),
        "passkey": passkeys_status(),
    }
