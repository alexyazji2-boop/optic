"""Two facts about where this process is running.

Both were inline in `app/main.py`. They moved here because the auth layer needs
them too — for the Secure cookie flag, the WebAuthn RP id and the OAuth redirect
URI — and `app/main.py` imports the auth router, so the auth layer importing
`app/main.py` back would be a cycle.
"""

from __future__ import annotations

import os

# Railway, Render and Fly all announce themselves in the environment; a laptop
# does not. That is what decides fail-closed versus fail-open where a secret is
# unset, and whether a cookie may be sent over plain HTTP.
_PLATFORM_VARS = ("RAILWAY_ENVIRONMENT", "RAILWAY_GIT_COMMIT_SHA",
                  "RENDER", "FLY_APP_NAME")


def is_hosted() -> bool:
    """True when running on a hosting platform rather than a local machine."""
    return any(os.environ.get(v) for v in _PLATFORM_VARS)


def base_url() -> str:
    """The origin the browser reaches this app on, without a trailing slash.

    OAuth redirect URIs and the links inside verification emails have to be
    absolute, and they have to match what was registered with the provider
    exactly. Deriving this from the incoming request's Host header would be
    wrong twice over: a Host header is attacker-controlled, so a reset link
    built from it can be pointed at another site, and behind Railway's proxy the
    header is not always the public name anyway. So it is configuration.
    """
    explicit = (os.environ.get("APP_URL") or "").strip().rstrip("/")
    if explicit:
        return explicit
    if is_hosted():
        # Railway publishes the generated domain. A custom domain is not in the
        # environment, which is why APP_URL exists and is documented as required
        # once one is attached.
        railway = (os.environ.get("RAILWAY_PUBLIC_DOMAIN") or "").strip()
        if railway:
            return "https://" + railway.rstrip("/")
        return "https://theopticterminal.com"
    port = os.environ.get("PORT", "8000")
    return "http://127.0.0.1:{}".format(port)
