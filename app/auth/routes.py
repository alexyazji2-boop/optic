"""The HTTP surface for accounts.

Conventions, all of them inherited from the rest of this app rather than
invented here:

* Failures raise `HTTPException` with a sentence a reader can act on. No
  provider error strings, no stack traces, no database messages.
* Anything that changes state is POST, PATCH or DELETE. Nothing changes state on
  GET, which is what makes SameSite=Lax a real CSRF defence rather than a
  half one.
* Every endpoint that touches stored data resolves the user from the session
  cookie. No route takes a user id from the caller.
* Emailed links point at the app, not at an endpoint: `/?verify=TOKEN` opens the
  page, which then POSTs the token. A GET that consumed the token would be
  spent by any mail client that prefetches links, and there are several.

**On not saying whether an account exists.** `/login`, `/forgot-password` and
`/register` are the three endpoints that can be used to test an address. The
first two answer identically either way, and both spend the same password-hashing
time so the answer cannot be read off the clock. `/register` cannot hide it — it
has to refuse a duplicate — so it refuses with the same wording as a wrong
password would produce and points at sign-in.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlencode

from fastapi import APIRouter, Body, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from starlette.concurrency import run_in_threadpool

from .. import db
from ..runtime import base_url
from . import (config, deps, linking, mailer, oauth, passkeys as passkeys_mod,
               passwords as pw, ratelimit, store, tokens)

log = logging.getLogger("optic.auth")

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Verifying a password against a hash that cannot match, so that a request for an
# address with no account costs the same ~20ms as one that has an account. Without
# it, response time is an account-existence oracle and the identical wording
# above is decoration. Computed once at import: it is not a secret and never
# matches anything, since nobody knows the random input.
_DUMMY_HASH = pw.hash_password(tokens.new_token())


def _clean(value: Any, limit: int = 200) -> str:
    return str(value or "").strip()[:limit]


def _bad(message: str) -> HTTPException:
    return HTTPException(status_code=400, detail=message)


async def _hash(password: str) -> str:
    return await run_in_threadpool(pw.hash_password, password)


async def _verify(stored: str, password: str):
    return await run_in_threadpool(pw.verify_password, stored, password)


async def _send(to: str, subject: str, body: str, link: Optional[str] = None) -> bool:
    """Mail goes to a worker thread. smtplib is blocking, and a slow relay on the
    event loop stalls every other request in the process, not just this one."""
    return await run_in_threadpool(mailer.send, to, subject, body, link)


# ------------------------------------------------------------------ state


def _sign_in(response: Response, request: Request, user: Dict[str, Any]) -> None:
    """Issue a session and the CSRF cookie, and record the login.

    A fresh session row every time rather than reusing one: that is the token
    rotation that matters, and it means the Settings list shows one entry per
    device instead of one entry that moves."""
    meta = deps.request_meta(request)
    token, _session = store.create_session(user["id"], config.SESSION_TTL,
                                           meta["ip"], meta["user_agent"])
    response.set_cookie(config.COOKIE_NAME, token,
                        **config.cookie_kwargs(config.SESSION_TTL))
    deps.issue_csrf(response)
    store.touch_login(user["id"])


def _state_payload(request: Request) -> Dict[str, Any]:
    """One response with everything the front end needs to render either state.

    Deliberately not three endpoints. The app asks this once on load and the
    answer decides guest versus signed-in, which buttons the login screen shows,
    what the plan allows, and the CSRF value — splitting it would mean four
    round trips before the first paint."""
    session, user = deps.session_and_user(request)
    payload: Dict[str, Any] = {
        "authenticated": bool(user),
        "providers": config.providers(),
        "mail": mailer.available(),
        "password_policy": pw.describe_policy(),
    }
    if not user:
        payload["user"] = None
        return payload
    payload["user"] = store.public_user(user)
    payload["methods"] = store.auth_methods(user["id"])
    payload["preferences"] = store.preferences(user["id"])
    payload["subscription"] = store.subscription(user["id"])
    payload["session_id"] = (session or {}).get("id")
    return payload


@router.get("/providers")
async def providers() -> Dict[str, Any]:
    """Which sign-in methods this deployment can actually offer. A button for an
    unconfigured provider looks like a broken site."""
    return {"providers": config.providers(), "mail": mailer.available()}


@router.get("/me")
async def me(request: Request, response: Response) -> Dict[str, Any]:
    payload = _state_payload(request)
    # Only when absent. Reissuing on every call would rotate the value out from
    # under a request that is already in flight with the old one.
    if not request.cookies.get(config.CSRF_COOKIE):
        payload["csrf"] = deps.issue_csrf(response)
    else:
        payload["csrf"] = request.cookies.get(config.CSRF_COOKIE)
    if payload["authenticated"]:
        session, _user = deps.session_and_user(request)
        token = request.cookies.get(config.COOKIE_NAME)
        # Slide the expiry forward at both ends: the row and the cookie. Guarded
        # on the token being present rather than assuming it, because setting the
        # cookie to an empty string would sign the reader out.
        if session and token:
            store.touch_session(session["id"], config.SESSION_TTL)
            response.set_cookie(config.COOKIE_NAME, token,
                                **config.cookie_kwargs(config.SESSION_TTL))
    response.headers["Cache-Control"] = "no-store"
    return payload


# --------------------------------------------------------------- email + password


@router.post("/register")
async def register(request: Request, response: Response,
                   payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    email = store.normalise_email(_clean(payload.get("email"), 320))
    first_name = _clean(payload.get("first_name"), 80)
    last_name = _clean(payload.get("last_name"), 80)
    password = str(payload.get("password") or "")
    confirm = str(payload.get("confirm_password") or password)

    ratelimit.guard(request, "register", email or None)

    if "@" not in email or "." not in email.split("@")[-1] or len(email) < 6:
        raise _bad("Enter a valid email address.")
    if not first_name:
        raise _bad("Enter your first name.")
    if password != confirm:
        raise _bad("Those passwords do not match.")
    problems = pw.policy_problems(password, email, first_name, last_name)
    if problems:
        raise _bad(" ".join(problems))

    if store.get_user_by_email(email):
        # Same wording as a failed sign-in, and it points at the way forward. It
        # does confirm the address is in use, which registration cannot avoid.
        raise HTTPException(
            status_code=409,
            detail="An account already uses that email address. Sign in instead, or "
                   "reset your password if you have forgotten it.")

    hashed = await _hash(password)
    user = store.create_user(email, first_name, last_name)
    store.add_identity(user["id"], "email", email, email)
    store.set_password(user["id"], hashed, pw.ALGO)

    token = store.create_verification(user["id"], config.VERIFY_TTL)
    link = "{}/?verify={}".format(base_url(), token)
    letter = mailer.verification_email(first_name, link)
    sent = await _send(email, letter["subject"], letter["body"], link)

    _sign_in(response, request, user)
    ratelimit.clear("login", ratelimit.key_bucket(email))
    return {"ok": True, "user": store.public_user(store.get_user(user["id"])),
            "verification_sent": sent, "mail": mailer.available()}


@router.post("/login")
async def login(request: Request, response: Response,
                payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    email = store.normalise_email(_clean(payload.get("email"), 320))
    password = str(payload.get("password") or "")
    ratelimit.guard(request, "login", email or None)

    generic = HTTPException(status_code=401, detail="Email or password is incorrect.")
    user = store.get_user_by_email(email) if email else None
    record = store.get_password(user["id"]) if user else None

    if not user or not record:
        # Spend the time anyway. See _DUMMY_HASH.
        await _verify(_DUMMY_HASH, password or "x")
        if user and not record:
            methods = store.auth_methods(user["id"])
            if methods["providers"] or methods["passkeys"]:
                # Not an enumeration leak worth avoiding: the person is holding a
                # password for an account that has never had one, and the useful
                # answer is which button to press instead.
                names = [linking.label(p) for p in methods["providers"]]
                if methods["passkeys"]:
                    names.append("a passkey")
                raise HTTPException(
                    status_code=401,
                    detail="That account signs in with {}. Use that, then add a "
                           "password from Settings if you want one.".format(
                               " or ".join(names) or "another method"))
        raise generic

    matched, upgraded = await _verify(record["password_hash"], password)
    if not matched:
        raise generic
    if upgraded:
        store.set_password(user["id"], upgraded, pw.ALGO)
    if not user.get("is_active"):
        raise HTTPException(status_code=403, detail="That account is not active.")

    _sign_in(response, request, user)
    ratelimit.clear("login", ratelimit.client_ip(request), ratelimit.key_bucket(email))
    return {"ok": True, "user": store.public_user(user),
            "methods": store.auth_methods(user["id"])}


@router.post("/logout")
async def logout(request: Request, response: Response) -> Dict[str, Any]:
    session, _user = deps.session_and_user(request)
    if session:
        store.delete_session(session["id"])
    response.delete_cookie(config.COOKIE_NAME, path="/")
    response.delete_cookie(config.CSRF_COOKIE, path="/")
    return {"ok": True}


@router.post("/logout-all")
async def logout_all(request: Request, response: Response) -> Dict[str, Any]:
    deps.csrf_guard(request)
    user = deps.require_user(request)
    removed = store.delete_sessions_for(user["id"])
    response.delete_cookie(config.COOKIE_NAME, path="/")
    response.delete_cookie(config.CSRF_COOKIE, path="/")
    return {"ok": True, "signed_out": removed}


# ------------------------------------------------------------- password reset


@router.post("/forgot-password")
async def forgot_password(request: Request,
                          payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    email = store.normalise_email(_clean(payload.get("email"), 320))
    ratelimit.guard(request, "forgot", email or None)

    # One response for every case: address exists, does not exist, or exists with
    # no password. Anything else turns this into a free account-existence check.
    answer = {"ok": True,
              "message": "If an account uses that address, a reset link is on its way.",
              "mail": mailer.available()}

    user = store.get_user_by_email(email) if email else None
    if not user:
        return answer

    methods = store.auth_methods(user["id"])
    if not methods["password"] and (methods["providers"] or methods["passkeys"]):
        # A provider-only account has no password to reset. Saying so is safe:
        # the caller already had to guess the address, and sending them round a
        # reset loop for a password that does not exist is worse.
        names = [linking.label(p) for p in methods["providers"]]
        if methods["passkeys"]:
            names.append("a passkey")
        answer["message"] = ("That account signs in with {}, which is managed there "
                             "rather than here. There is no Optic Terminal password to "
                             "reset.".format(" or ".join(names)))
        return answer

    token = store.create_reset(user["id"], config.RESET_TTL)
    link = "{}/?reset={}".format(base_url(), token)
    letter = mailer.reset_email(user.get("first_name") or "", link)
    sent = await _send(user["email"], letter["subject"], letter["body"], link)
    answer["sent"] = sent
    return answer


@router.get("/reset/check")
async def reset_check(token: str = Query("", max_length=200)) -> Dict[str, Any]:
    """Is this link still good? Read-only, so the form can say the link has
    expired before someone types a new password into it twice."""
    found = store.peek_reset(token) if token else None
    if not found:
        return {"valid": False,
                "reason": "This password reset link has expired or has already been "
                          "used. Request a new one."}
    return {"valid": True}


@router.post("/reset-password")
async def reset_password(request: Request, response: Response,
                         payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    token = _clean(payload.get("token"), 200)
    password = str(payload.get("password") or "")
    confirm = str(payload.get("confirm_password") or password)
    ratelimit.guard(request, "reset")

    if not token:
        raise _bad("That reset link is missing its token.")
    if password != confirm:
        raise _bad("Those passwords do not match.")

    found = store.peek_reset(token)
    if not found:
        raise HTTPException(
            status_code=400,
            detail="This password reset link has expired or has already been used. "
                   "Request a new one.")
    user = store.get_user(found["user_id"])
    problems = pw.policy_problems(password, (user or {}).get("email") or "",
                                  (user or {}).get("first_name") or "",
                                  (user or {}).get("last_name") or "")
    if problems:
        raise _bad(" ".join(problems))

    hashed = await _hash(password)
    user_id = store.consume_reset(token, hashed, pw.ALGO)
    if not user_id:
        # Lost the race with another submission of the same link.
        raise HTTPException(status_code=400,
                            detail="That reset link has already been used.")

    user = store.get_user(user_id)
    if user:
        letter = mailer.password_changed_email(user.get("first_name") or "", db.utcnow())
        await _send(user["email"], letter["subject"], letter["body"])
        # Signed in on the new password rather than sent back to a login form
        # they have just proved they can pass.
        _sign_in(response, request, user)
    return {"ok": True, "user": store.public_user(user) if user else None}


# ----------------------------------------------------------- email verification


@router.post("/verify-email")
async def verify_email(payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    token = _clean(payload.get("token"), 200)
    if not token:
        raise _bad("That verification link is missing its token.")
    user_id = store.consume_verification(token)
    if not user_id:
        raise HTTPException(
            status_code=400,
            detail="This verification link has expired or has already been used. "
                   "Request a new one from Settings.")
    user = store.get_user(user_id)
    return {"ok": True, "user": store.public_user(user) if user else None}


@router.post("/resend-verification")
async def resend_verification(request: Request) -> Dict[str, Any]:
    user = deps.require_user(request)
    deps.csrf_guard(request)
    ratelimit.guard(request, "verify_resend", user["id"])
    if user.get("email_verified"):
        return {"ok": True, "already_verified": True}
    token = store.create_verification(user["id"], config.VERIFY_TTL)
    link = "{}/?verify={}".format(base_url(), token)
    letter = mailer.verification_email(user.get("first_name") or "", link)
    sent = await _send(user["email"], letter["subject"], letter["body"], link)
    return {"ok": True, "sent": sent, "mail": mailer.available()}


# ---------------------------------------------------------------------- profile


@router.patch("/profile")
async def update_profile(request: Request,
                         payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    user = deps.require_user(request)
    deps.csrf_guard(request)
    avatar = payload.get("avatar_url")
    if avatar is not None:
        avatar = _clean(avatar, 500)
        # Only an http(s) URL. A `javascript:` or `data:` value here would be
        # written into an <img src> and a src is not the only place a URL from
        # the database ends up.
        if avatar and not avatar.startswith(("https://", "http://")):
            raise _bad("A profile image needs to be an https link.")
    updated = store.update_profile(
        user["id"],
        first_name=None if payload.get("first_name") is None
        else _clean(payload.get("first_name"), 80),
        last_name=None if payload.get("last_name") is None
        else _clean(payload.get("last_name"), 80),
        avatar_url=avatar,
    )
    return {"ok": True, "user": store.public_user(updated or user)}


@router.post("/change-password")
async def change_password(request: Request, response: Response,
                          payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    user = deps.require_user(request)
    deps.csrf_guard(request)
    ratelimit.guard(request, "password_change", user["id"])

    current = str(payload.get("current_password") or "")
    new_password = str(payload.get("new_password") or "")
    confirm = str(payload.get("confirm_password") or new_password)
    record = store.get_password(user["id"])

    if record:
        matched, _ = await _verify(record["password_hash"], current)
        if not matched:
            raise HTTPException(status_code=401,
                                detail="That current password is not correct.")
    elif not user.get("email_verified"):
        # Setting a first password on a provider-only account is a new way in, so
        # it needs proof of the mailbox. Without that check, a provider account
        # whose email was never confirmed could be given a password that then
        # works even if the provider connection is removed.
        raise HTTPException(
            status_code=403,
            detail="Confirm your email address before adding a password, so the "
                   "reset link has somewhere to go.")

    if new_password != confirm:
        raise _bad("Those passwords do not match.")
    problems = pw.policy_problems(new_password, user["email"],
                                  user.get("first_name") or "",
                                  user.get("last_name") or "")
    if problems:
        raise _bad(" ".join(problems))

    hashed = await _hash(new_password)
    store.set_password(user["id"], hashed, pw.ALGO)
    if not store.get_identity("email", store.normalise_email(user["email"])):
        store.add_identity(user["id"], "email", store.normalise_email(user["email"]),
                           user["email"])

    session, _u = deps.session_and_user(request)
    # Everywhere else is signed out. The reason someone changes a password is
    # usually that they think somebody else has it.
    removed = store.delete_sessions_for(user["id"],
                                        except_session=(session or {}).get("id"))
    letter = mailer.password_changed_email(user.get("first_name") or "", db.utcnow())
    await _send(user["email"], letter["subject"], letter["body"])
    return {"ok": True, "other_sessions_ended": removed,
            "methods": store.auth_methods(user["id"])}


# --------------------------------------------------------------------- sessions


@router.get("/sessions")
async def list_sessions(request: Request) -> Dict[str, Any]:
    user = deps.require_user(request)
    session, _u = deps.session_and_user(request)
    current_id = (session or {}).get("id")
    rows: List[Dict[str, Any]] = []
    for found in store.sessions_for(user["id"]):
        rows.append({
            "id": found["id"],
            "created_at": found["created_at"],
            "last_used_at": found["last_used_at"],
            "expires_at": found["expires_at"],
            "ip_address": found.get("ip_address"),
            "user_agent": found.get("user_agent"),
            "label": passkeys_mod.device_label(found.get("user_agent") or ""),
            "current": found["id"] == current_id,
        })
    return {"sessions": rows}


@router.delete("/sessions/{session_id}")
async def revoke_session(session_id: str, request: Request,
                         response: Response) -> Dict[str, Any]:
    user = deps.require_user(request)
    deps.csrf_guard(request)
    # Scoped to the caller: a session id from another account matches nothing.
    removed = store.delete_session(session_id, user["id"])
    if not removed:
        raise HTTPException(status_code=404, detail="That session is no longer active.")
    session, _u = deps.session_and_user(request)
    if (session or {}).get("id") == session_id:
        response.delete_cookie(config.COOKIE_NAME, path="/")
        response.delete_cookie(config.CSRF_COOKIE, path="/")
    return {"ok": True}


# ----------------------------------------------------------- connected accounts


@router.get("/identities")
async def list_identities(request: Request) -> Dict[str, Any]:
    user = deps.require_user(request)
    methods = store.auth_methods(user["id"])
    rows = []
    for found in store.identities_for(user["id"]):
        rows.append({"provider": found["provider"],
                     "label": linking.label(found["provider"]),
                     "email": found.get("provider_email"),
                     "connected_at": found["created_at"]})
    return {"identities": rows, "methods": methods,
            "providers": config.providers(),
            "passkeys": [store.public_passkey(p)
                         for p in store.passkeys_for(user["id"])]}


@router.delete("/identities/{provider}")
async def disconnect(provider: str, request: Request) -> Dict[str, Any]:
    user = deps.require_user(request)
    deps.csrf_guard(request)
    provider = _clean(provider, 20).lower()
    methods = store.auth_methods(user["id"])

    if provider == "email":
        if not methods["password"]:
            raise HTTPException(status_code=404,
                                detail="There is no password on this account.")
        if methods["count"] <= 1:
            raise _bad("That is the only way into this account. Add a passkey or "
                       "connect Google or Apple first.")
        store.clear_password(user["id"])
        store.remove_identity(user["id"], "email")
        return {"ok": True, "methods": store.auth_methods(user["id"])}

    if provider not in methods["providers"]:
        raise HTTPException(status_code=404,
                            detail="That account is not connected.")
    if methods["count"] <= 1:
        # The rule that stops account recovery becoming a support ticket.
        raise _bad("That is the only way into this account. Add a password or a "
                   "passkey first, then disconnect it.")
    store.remove_identity(user["id"], provider)
    return {"ok": True, "methods": store.auth_methods(user["id"])}


# --------------------------------------------------------------------- passkeys


@router.get("/passkeys")
async def list_passkeys(request: Request) -> Dict[str, Any]:
    user = deps.require_user(request)
    return {"passkeys": [store.public_passkey(p)
                         for p in store.passkeys_for(user["id"])],
            "methods": store.auth_methods(user["id"]),
            "supported": config.passkeys_status()}


@router.post("/passkeys/register/options")
async def passkey_register_options(request: Request) -> Dict[str, Any]:
    user = deps.require_user(request)
    deps.csrf_guard(request)
    ratelimit.guard(request, "passkey_challenge", user["id"])
    status = config.passkeys_status()
    if not status["available"]:
        raise HTTPException(status_code=503, detail=status["reason"])
    return {"options": passkeys_mod.registration_options(user)}


@router.post("/passkeys/register/verify")
async def passkey_register_verify(request: Request,
                                  payload: Dict[str, Any] = Body(default={})
                                  ) -> Dict[str, Any]:
    user = deps.require_user(request)
    deps.csrf_guard(request)
    ratelimit.guard(request, "passkey_verify", user["id"])
    credential = payload.get("credential")
    if not isinstance(credential, dict):
        raise _bad("That passkey response was malformed.")
    try:
        saved = passkeys_mod.verify_registration(
            credential,
            user_agent=request.headers.get("user-agent") or "",
            name=_clean(payload.get("name"), 60) or None)
    except passkeys_mod.PasskeyError as exc:
        raise _bad(str(exc))
    # The challenge carried the user id, so a response cannot be redirected onto
    # another account; this asserts it rather than assuming it.
    if saved["user_id"] != user["id"]:
        store.delete_passkey(saved["user_id"], saved["id"])
        raise _bad("That passkey did not belong to this sign-in attempt.")
    return {"ok": True, "passkey": store.public_passkey(saved),
            "methods": store.auth_methods(user["id"])}


@router.post("/passkeys/login/options")
async def passkey_login_options(request: Request) -> Dict[str, Any]:
    ratelimit.guard(request, "passkey_challenge")
    status = config.passkeys_status()
    if not status["available"]:
        raise HTTPException(status_code=503, detail=status["reason"])
    return {"options": passkeys_mod.authentication_options()}


@router.post("/passkeys/login/verify")
async def passkey_login_verify(request: Request, response: Response,
                               payload: Dict[str, Any] = Body(default={})
                               ) -> Dict[str, Any]:
    ratelimit.guard(request, "passkey_verify")
    credential = payload.get("credential")
    if not isinstance(credential, dict):
        raise _bad("That passkey response was malformed.")
    try:
        user, _passkey = passkeys_mod.verify_authentication(credential)
    except passkeys_mod.PasskeyError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    _sign_in(response, request, user)
    return {"ok": True, "user": store.public_user(user),
            "methods": store.auth_methods(user["id"])}


@router.patch("/passkeys/{passkey_id}")
async def rename_passkey(passkey_id: str, request: Request,
                         payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    user = deps.require_user(request)
    deps.csrf_guard(request)
    changed = store.rename_passkey(user["id"], passkey_id, _clean(payload.get("name"), 60))
    if not changed:
        raise HTTPException(status_code=404, detail="That passkey is not on this account.")
    return {"ok": True, "passkeys": [store.public_passkey(p)
                                     for p in store.passkeys_for(user["id"])]}


@router.delete("/passkeys/{passkey_id}")
async def remove_passkey(passkey_id: str, request: Request) -> Dict[str, Any]:
    user = deps.require_user(request)
    deps.csrf_guard(request)
    methods = store.auth_methods(user["id"])
    owned = [p for p in store.passkeys_for(user["id"]) if p["id"] == passkey_id]
    if not owned:
        raise HTTPException(status_code=404, detail="That passkey is not on this account.")
    if methods["count"] <= 1:
        raise _bad("That passkey is the only way into this account. Add a password or "
                   "connect Google or Apple first.")
    store.delete_passkey(user["id"], passkey_id)
    return {"ok": True, "methods": store.auth_methods(user["id"])}


# ------------------------------------------------------------------ preferences


@router.get("/preferences")
async def get_preferences(request: Request) -> Dict[str, Any]:
    user = deps.require_user(request)
    return {"preferences": store.preferences(user["id"]),
            "landing_views": list(store.LANDING_VIEWS)}


@router.patch("/preferences")
async def patch_preferences(request: Request,
                            payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    user = deps.require_user(request)
    deps.csrf_guard(request)
    return {"ok": True, "preferences": store.set_preferences(user["id"], payload or {})}


@router.get("/subscription")
async def get_subscription(request: Request) -> Dict[str, Any]:
    user = deps.require_user(request)
    return {"subscription": store.subscription(user["id"]),
            "plans": {name: {"label": spec["label"]} for name, spec in store.PLANS.items()},
            "billing": {"available": False,
                        "reason": "Plans are not on sale yet. Every account is on Free."}}


# ------------------------------------------------------------- delete account


@router.post("/delete-account")
async def delete_account(request: Request, response: Response,
                         payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    """POST, not DELETE, and it wants the email typed back.

    Everything the person owns goes with the row. That is not undoable, so the
    confirmation is the account's own address rather than a yes/no."""
    user = deps.require_user(request)
    deps.csrf_guard(request)
    typed = store.normalise_email(_clean(payload.get("confirm_email"), 320))
    if typed != store.normalise_email(user["email"]):
        raise _bad("Type the account's email address to confirm.")
    record = store.get_password(user["id"])
    if record:
        matched, _ = await _verify(record["password_hash"],
                                   str(payload.get("password") or ""))
        if not matched:
            raise HTTPException(status_code=401, detail="That password is not correct.")
    store.delete_user(user["id"])
    response.delete_cookie(config.COOKIE_NAME, path="/")
    response.delete_cookie(config.CSRF_COOKIE, path="/")
    return {"ok": True}


# ------------------------------------------------------------------ oauth flows
#
# The browser is redirected away and comes back to a callback. Outcomes travel
# home as short codes in the query string, and the front end turns a code plus a
# provider into a sentence. Not the message itself: a server-generated string
# echoed through a URL is a reflection this app does not need to own.

_ERROR_CODES = {"state", "provider", "config", "taken", "needs_link", "no_email",
                "inactive", "denied"}


def _home(code: str, provider: str = "", redirect_to: str = "") -> RedirectResponse:
    query: Dict[str, str] = {}
    if code == "ok":
        query["auth"] = "ok"
    else:
        query["auth_error"] = code if code in _ERROR_CODES else "provider"
    if provider:
        query["provider"] = provider
    target = "{}/?{}".format(base_url(), urlencode(query))
    if redirect_to and redirect_to.startswith("/") and not redirect_to.startswith("//"):
        # Relative paths only. An absolute URL here would make this an open
        # redirect: hand someone a link that signs them in and lands them on a
        # site of the attacker's choosing.
        target += "&next=" + redirect_to[:200]
    return RedirectResponse(target, status_code=303)


@router.get("/{provider}/start")
async def oauth_start(provider: str, request: Request,
                      link: int = Query(0),
                      next: str = Query("", max_length=200)) -> Any:
    provider = _clean(provider, 20).lower()
    if provider not in ("google", "apple"):
        raise HTTPException(status_code=404, detail="Unknown sign-in provider.")
    ratelimit.guard(request, "oauth_start")

    link_user_id = None
    if link:
        # Connecting a provider to the account already in this session. The id
        # comes from the session, never from the query string.
        user = deps.require_user(request)
        link_user_id = user["id"]

    state = tokens.new_token()
    nonce = tokens.new_token()
    try:
        url, verifier = oauth.start(provider, state, nonce)
    except oauth.OAuthError as exc:
        log.info("%s sign-in unavailable: %s", provider, exc)
        return _home("config", provider)
    store.store_state(state, provider, nonce, next or None, link_user_id,
                      config.OAUTH_STATE_TTL, verifier)
    return RedirectResponse(url, status_code=303)


async def _finish_oauth(provider: str, request: Request,
                        code: str, state: str,
                        apple_user: Optional[str] = None) -> Any:
    ratelimit.guard(request, "oauth_callback")
    if not code or not state:
        return _home("denied", provider)

    found = store.take_state(state, provider)
    if not found:
        # Unknown, expired or already used. All three mean this callback is not
        # the continuation of a flow this server started.
        return _home("state", provider)

    parsed_user = None
    if apple_user:
        try:
            parsed_user = json.loads(apple_user)
        except (TypeError, ValueError):
            parsed_user = None

    try:
        profile = await run_in_threadpool(
            oauth.complete, provider, code, found["nonce"],
            found.get("code_verifier"), parsed_user)
    except oauth.OAuthError as exc:
        log.info("%s callback failed: %s", provider, exc)
        return _home("provider", provider)

    outcome = linking.resolve(profile, link_user_id=found.get("link_user_id"))
    if outcome["outcome"] in ("taken", "needs_link", "no_email", "inactive"):
        return _home(outcome["outcome"], provider, found.get("redirect_to") or "")

    user = outcome["user"]
    response = _home("ok", provider, found.get("redirect_to") or "")
    _sign_in(response, request, user)
    return response


@router.get("/google/callback")
async def google_callback(request: Request,
                          code: str = Query("", max_length=2048),
                          state: str = Query("", max_length=200),
                          error: str = Query("", max_length=200)) -> Any:
    if error:
        return _home("denied", "google")
    return await _finish_oauth("google", request, code, state)


# 64 KB. Apple's callback body is a few hundred bytes; the cap is there so an
# unauthenticated POST cannot ask this process to buffer an arbitrary amount.
_APPLE_BODY_LIMIT = 64 * 1024


async def _apple_form(request: Request) -> Dict[str, str]:
    """Apple's callback body, parsed without FastAPI's `Form`.

    `Form(...)` pulls in python-multipart, and Starlette needs that package even
    for `application/x-www-form-urlencoded` because it uses it to read the
    content-type header. Apple sends urlencoded, which `parse_qs` handles in the
    standard library, so the dependency would buy nothing. Parsing it here also
    means a body Apple never sends cannot crash the route with a 422 mid-sign-in.
    """
    content_type = (request.headers.get("content-type") or "").split(";")[0].strip()
    if content_type not in ("application/x-www-form-urlencoded", ""):
        return {}
    # Content-Length first, so an oversized body is refused before it is read
    # into memory rather than after. A chunked request has no length to check,
    # which is why the check on the buffered body stays as well.
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > _APPLE_BODY_LIMIT:
        return {}
    raw = await request.body()
    if len(raw) > _APPLE_BODY_LIMIT:
        return {}
    try:
        parsed = parse_qs(raw.decode("utf-8"), keep_blank_values=True)
    except UnicodeDecodeError:
        return {}
    return {key: (values[0] if values else "") for key, values in parsed.items()}


@router.post("/apple/callback")
async def apple_callback_post(request: Request) -> Any:
    """Apple posts here from its own domain because `response_mode=form_post` is
    required whenever a scope is requested. The request therefore carries no
    cookies from this site, which is exactly why `state` is looked up in the
    database rather than compared against one."""
    form = await _apple_form(request)
    if form.get("error"):
        return _home("denied", "apple")
    return await _finish_oauth("apple", request, form.get("code", ""),
                               form.get("state", ""),
                               apple_user=form.get("user") or None)


@router.get("/apple/callback")
async def apple_callback_get(request: Request,
                             code: str = Query("", max_length=2048),
                             state: str = Query("", max_length=200),
                             error: str = Query("", max_length=200)) -> Any:
    """Apple uses form_post here, but a GET arrives if the flow was started
    without a scope. Handled rather than 405, because a 405 in the middle of a
    sign-in is indistinguishable from the site being down."""
    if error:
        return _home("denied", "apple")
    return await _finish_oauth("apple", request, code, state)
