"""Who is calling, and whether they may.

Three things live here, and every protected route uses them rather than reading
the cookie itself:

* `current_user(request)` — the signed-in user or None. Never raises.
* `require_user(request)` — the same, or a 401 with a message a person can act on.
* `csrf_guard(request)` — refuses a state-changing request that did not come
  from this app's own front end.

**The user id is never taken from the request body.** It comes from the session
row, which came from a hashed cookie value. A route that accepted `user_id` as a
parameter would be one typo away from letting anyone read anyone's watchlist, and
that class of bug does not show up in testing because the front end always sends
the right id.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from fastapi import HTTPException, Request, Response

from . import admin, config, store, tokens
from .ratelimit import client_ip


def _cached(request: Request) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """Whether this request has already been resolved, and to what.

    Several routes ask twice — once to decide authorisation and once to shape the
    response — and the session lookup is a database read. Cached on the request,
    so it cannot leak between requests the way a module-level cache would."""
    if hasattr(request.state, "optic_auth"):
        return True, request.state.optic_auth
    return False, None


def session_and_user(request: Request) -> Tuple[Optional[Dict[str, Any]],
                                                Optional[Dict[str, Any]]]:
    """(session, user), both None when not signed in."""
    cached, value = _cached(request)
    if cached:
        return ((value or {}).get("session"), (value or {}).get("user")) if value else (None, None)

    token = request.cookies.get(config.COOKIE_NAME) or ""
    resolved: Optional[Dict[str, Any]] = None
    if token:
        session = store.session_by_token(token)
        if session:
            user = store.get_user(session["user_id"])
            # A deactivated account keeps its rows but stops authenticating. The
            # session is left in place rather than deleted so that reactivating
            # does not also mean signing every device back in.
            if user and user.get("is_active"):
                resolved = {"session": session, "user": user}
    request.state.optic_auth = resolved
    if not resolved:
        return None, None
    return resolved["session"], resolved["user"]


def current_user(request: Request) -> Optional[Dict[str, Any]]:
    _session, user = session_and_user(request)
    return user


def require_user(request: Request) -> Dict[str, Any]:
    user = current_user(request)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Sign in to use this. Reading the terminal does not need an account.")
    return user


def require_verified(request: Request) -> Dict[str, Any]:
    """For anything that sends mail on a user's behalf or spends on their behalf.

    Deliberately not applied to reading or to saving research. Gating the product
    on a click in an inbox is how a new account bounces: the person is already
    signed in and has already seen the thing they wanted to keep."""
    user = require_user(request)
    if not user.get("email_verified"):
        raise HTTPException(
            status_code=403,
            detail="Confirm your email address first. Check your inbox, or request a "
                   "new link from Settings.")
    return user


def is_admin(request: Request) -> bool:
    """Does the caller own this deployment.

    A predicate, not a guard: the one caller that has an answer for "no" is
    `_write_guard`, which falls through to the write token rather than refusing.
    A `require_admin` that nothing called would be dead code, and the shape of
    the message on refusal belongs to whichever endpoint is refusing."""
    return admin.is_admin(current_user(request))


# ------------------------------------------------------------------ csrf
#
# Defence in depth over SameSite=Lax. Lax already blocks a cross-site POST from
# carrying the session cookie, and no endpoint changes state on GET; this is the
# second lock, in the double-submit form: a value the server set in a readable
# cookie has to be echoed in a header. An attacker on another origin can cause a
# request but cannot read that cookie to fill the header in.


def issue_csrf(response: Response) -> str:
    """Set the CSRF cookie. Not HttpOnly: the front end has to read it. That is
    not a weakness of the pattern — the value is not a credential on its own, it
    only proves the caller can read this site's cookies."""
    value = tokens.new_token()
    kwargs = config.cookie_kwargs(config.SESSION_TTL)
    kwargs["httponly"] = False
    response.set_cookie(config.CSRF_COOKIE, value, **kwargs)
    return value


def csrf_guard(request: Request) -> None:
    """Keyed on the *session* cookie, not on the CSRF cookie.

    The first version returned early whenever the CSRF cookie was absent, on the
    grounds that no cookie means no session to ride on. That is one case too
    generous: the two cookies are set together but can be separated — a reader
    who clears one, a browser that evicts it, an extension. A request arriving
    with a live session and no CSRF cookie would then have skipped the check
    entirely, which is exactly the state a forged request wants.

    So: no session cookie, nothing to forge, allow (this is what lets the very
    first sign-in through, before any cookie exists). A session cookie present
    means the header has to be there and has to match."""
    if not request.cookies.get(config.COOKIE_NAME):
        return
    cookie = request.cookies.get(config.CSRF_COOKIE) or ""
    header = request.headers.get("x-optic-csrf") or ""
    if not cookie or not tokens.same(cookie, header):
        raise HTTPException(
            status_code=403,
            detail="That request did not look like it came from this page. Reload and "
                   "try again.")


def request_meta(request: Request) -> Dict[str, str]:
    """What gets stored on a session row so the Settings page can say "Chrome on
    a Mac, seen an hour ago" instead of showing an opaque id."""
    return {
        "ip": client_ip(request),
        "user_agent": (request.headers.get("user-agent") or "")[:300],
    }
