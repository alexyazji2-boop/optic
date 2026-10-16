"""HTTP routes for read-only brokerage linking.

Every route that reads or changes brokerage data takes the user from the
session (`deps.require_user`) and every state change also passes `csrf_guard`.
Ids in paths are looked up with the user id in the WHERE clause, so another
reader's connection or account answers 404, the same as one that does not
exist.

The webhook is the one unauthenticated route and is verified by signature
instead; the sandbox portal is the other, and it only exists while the
sandbox provider is configured.
"""

from __future__ import annotations

import asyncio
import hashlib
import html
import logging
from typing import Any, Callable, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Body, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool

from .. import runtime
from ..auth import admin as auth_admin
from ..auth import deps
from ..auth import store as auth_store
from ..auth import ratelimit as auth_ratelimit
from . import service, store
from .providers import ProviderError, SANDBOX_SCENARIOS, SandboxProvider, WebhookRejected

log = logging.getLogger("optic.brokerage")
router = APIRouter(prefix="/api/brokerage", tags=["brokerage"])

# Filled in by app.main, which owns the market-data provider. Importing main
# from here would be a cycle.
LOOKUPS: Dict[str, Callable] = {}

PERMISSIONS = [
    "Read-only: Optic can see account names, holdings, balances and cash. It cannot place trades, "
    "move money or change anything at your broker.",
    "You sign in to your broker on the broker's or SnapTrade's own page. Optic never sees or stores "
    "your brokerage password.",
    "You choose which accounts count towards your Optic portfolio, and can change that at any time.",
    "Holdings are stored encrypted. When you ask Milo about your portfolio, your holdings are sent with "
    "that question to Anthropic, the AI provider that runs Milo, to write the answer.",
    "Disconnect removes the connection at the provider and deletes Optic's copy of that connection's "
    "data straight away. Delete all brokerage data also deletes the encryption key, so backups "
    "cannot be read either.",
    "If your paid plan ends, syncing stops at once. After 7 days the connection is closed at the "
    "provider, and after 30 days Optic deletes its copy. You can disconnect or delete at any time, "
    "on any plan.",
]


def set_lookups(**fns: Callable) -> None:
    LOOKUPS.update(fns)


def _http(exc: Exception, user: Optional[Dict[str, Any]] = None) -> HTTPException:
    """The reader's answer for a failed step. Pass the reader so the owner
    also sees the provider's own reason (owner-only)."""
    if isinstance(exc, service.NotAvailable):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, service.NotEntitled):
        return HTTPException(status_code=402, detail=str(exc))
    if isinstance(exc, service.NeedsConsent):
        return HTTPException(status_code=428, detail=str(exc))
    if isinstance(exc, LookupError):
        return HTTPException(status_code=404, detail=str(exc).strip("'\"") or "Not found.")
    owner = bool(user) and auth_admin.is_admin(user)
    if isinstance(exc, ProviderError):
        # 424, not 502: Cloudflare swaps an origin 502 for its own "the origin
        # is misconfigured" page, which is what the owner saw on the first live
        # SnapTrade connect (2026-10-15) instead of this sentence. The
        # provider's reason names status codes and error codes, never a secret,
        # so it is logged, and shown to the owner, who has no other way to read it.
        log.warning("brokerage provider error: %s: %s", type(exc).__name__, exc)
        detail = "The brokerage provider did not complete that. Nothing was changed; try again shortly."
        if owner:
            detail += " (Owner only: {})".format(exc)
        return HTTPException(status_code=424, detail=detail)
    log.error("brokerage request failed: %s", type(exc).__name__, exc_info=exc)
    return HTTPException(status_code=500, detail="Something went wrong." + (
        " (Owner only: {})".format(type(exc).__name__) if owner else ""))


@router.get("/status")
async def brokerage_status(request: Request) -> Dict[str, Any]:
    user = deps.current_user(request)
    # Per reader: in owner-only mode everyone else gets the switched-off answer.
    st = service.status_for(user)
    out: Dict[str, Any] = {"available": st["enabled"], "reason": st.get("reason"),
                           "provider": st.get("label"), "mode": st.get("mode"),
                           "permissions": PERMISSIONS}
    if not user:
        out["signed_in"] = False
        return out
    out["signed_in"] = True
    if st["enabled"] and service.owner_only():
        # Only the owner ever sees this: the page says why Optic's own
        # documents may be missing from the agreement.
        out["owner_only"] = True
    out["entitlement"] = service.entitlement(user)
    out["consent"] = service.consent_state(user["id"])
    # What upgrading would give, so the page's offer is built from the same
    # numbers the server enforces rather than from copy that can drift.
    out["paid_limits"] = {k: v for k, v in auth_store.PLANS["pro"].items() if k != "label"}
    out["connections"] = await run_in_threadpool(service.connections_payload, user)
    row = store.link(user["id"])
    out["paused_at"] = (row or {}).get("paused_at")
    out["provider_closed_at"] = (row or {}).get("provider_removed_at")
    return out


@router.post("/connect")
async def connect(request: Request, payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    user = deps.require_user(request)
    deps.csrf_guard(request)
    auth_ratelimit.spend("brokerage_connect", auth_ratelimit.key_bucket(user["id"]), 10, 3600,
                         "That is a lot of connection attempts in an hour. Wait a while and try again.")
    ip_hash = auth_ratelimit.key_bucket(auth_ratelimit.client_ip(request))
    try:
        url = await run_in_threadpool(service.start_link, user, runtime.base_url(),
                                      (payload or {}).get("reconnect") or None,
                                      (payload or {}).get("consent_version") or None, ip_hash)
    except Exception as exc:                                    # noqa: BLE001
        raise _http(exc, user)
    return {"url": url}


@router.get("/callback")
async def callback(request: Request, state: str = "", status: str = "") -> RedirectResponse:
    """Where the hosted portal sends the browser back. The plan, the provider
    and the state token decide what happens; the portal's own query string
    (status, connection id) is only used to choose the message."""
    user = deps.current_user(request)
    taken = store.take_link_state(state)
    if not user or not taken or taken["user_id"] != user["id"]:
        return RedirectResponse("/?brokerage=expired#/brokerage", status_code=303)
    if status.upper() == "ABANDONED":
        return RedirectResponse("/?brokerage=abandoned#/brokerage", status_code=303)
    if status.upper() == "ERROR":
        reason = (request.query_params.get("reason") or request.query_params.get("error_code") or "").upper()
        code = "unsupported" if "UNSUPPORTED" in reason else "error"
        return RedirectResponse("/?brokerage={}#/brokerage".format(code), status_code=303)
    try:
        result = await run_in_threadpool(service.finish_link, user, taken)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("brokerage callback failed: %s", type(exc).__name__)
        return RedirectResponse("/?brokerage=error#/brokerage", status_code=303)
    code = ("notreadonly" if result["refused"] else "limit" if result["over_limit"]
            else "linked" if result["imported"] or result["synced"] else "nothing")
    return RedirectResponse("/?brokerage={}#/brokerage".format(code), status_code=303)


@router.post("/connections/{connection_id}/sync")
async def sync_now(connection_id: str, request: Request) -> Dict[str, Any]:
    user = deps.require_user(request)
    deps.csrf_guard(request)
    conn = store.connection(user["id"], connection_id)
    if not conn:
        raise HTTPException(status_code=404, detail="No such connection.")
    ent = service.entitlement(user)
    if not ent["can_link"]:
        raise HTTPException(status_code=402, detail="Syncing is part of the paid plan. Your stored data "
                                                    "is still here, and you can disconnect at any time.")
    if conn["status"] in ("expired", "closed"):
        raise HTTPException(status_code=409, detail="This connection needs to be reconnected first.")
    bucket = auth_ratelimit.key_bucket(user["id"])
    if auth_ratelimit.allowance("brokerage_sync", bucket, ent["manual_syncs_per_day"], 86400)["left"] <= 0:
        raise HTTPException(status_code=429, detail="Your plan includes {} manual sync{} a day. Accounts also "
                            "sync on their own once a day.".format(
                                ent["manual_syncs_per_day"], "" if ent["manual_syncs_per_day"] == 1 else "s"))
    try:
        result = await run_in_threadpool(service.request_refresh, user, conn)
    except Exception as exc:                                    # noqa: BLE001
        raise _http(exc, user)
    # Spent only once the provider accepted the request: a refused refresh
    # bought nothing and costs the reader nothing (review M3).
    auth_ratelimit.record("brokerage_sync", bucket)
    return result


@router.post("/connections/{connection_id}/disconnect")
async def disconnect(connection_id: str, request: Request) -> Dict[str, Any]:
    user = deps.require_user(request)
    deps.csrf_guard(request)
    try:
        return await run_in_threadpool(service.disconnect, user, connection_id)
    except Exception as exc:                                    # noqa: BLE001
        raise _http(exc, user)


@router.patch("/accounts/{account_id}")
async def select_account(account_id: str, request: Request,
                         payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    user = deps.require_user(request)
    deps.csrf_guard(request)
    if "selected" not in (payload or {}):
        raise HTTPException(status_code=400, detail="Say whether the account is selected.")
    if not store.set_account_selected(user["id"], account_id, bool(payload["selected"])):
        raise HTTPException(status_code=404, detail="No such account.")
    return {"ok": True}


@router.post("/delete-data")
async def delete_data(request: Request) -> Dict[str, Any]:
    user = deps.require_user(request)
    deps.csrf_guard(request)
    return await run_in_threadpool(service.delete_all, user)


@router.get("/portfolio")
async def portfolio(request: Request) -> Dict[str, Any]:
    user = deps.require_user(request)
    if not store.link(user["id"]):
        return {"available": False, "reason": "No brokerage is linked to this account."}
    if not service.open_to(user):
        # Owner-only mode: nobody else can have linked anything, and if a row
        # predates the switch it is not shown here (disconnect and delete
        # still work on it).
        return {"available": False, "reason": service.NOT_SWITCHED_ON}
    try:
        out = await run_in_threadpool(service.overview, user, **LOOKUPS)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("portfolio overview failed: %s", type(exc).__name__)
        return {"available": False, "reason": "Your stored portfolio could not be read just now."}
    out["available"] = True
    return out


@router.post("/webhook")
async def webhook(request: Request, background: BackgroundTasks) -> Dict[str, Any]:
    body = await request.body()
    st = service.status()
    if not st["enabled"]:
        raise HTTPException(status_code=503, detail="Not configured.")
    prov = service.provider()
    try:
        event = prov.verify_webhook({k.lower(): v for k, v in request.headers.items()}, body)
    except WebhookRejected:
        raise HTTPException(status_code=401, detail="Signature did not verify.")
    eid = str(event.get("webhookId") or event.get("eventId")
              or hashlib.sha256(body).hexdigest())
    kind = str(event.get("eventType") or event.get("type") or "")
    if not store.first_delivery(prov.name, eid, kind):
        return {"ok": True, "duplicate": True}
    event.setdefault("type", kind)
    # Acknowledged now, handled after the response: a sync is several provider
    # calls, and a slow one timing out the delivery made SnapTrade retry
    # (review M2). A failure un-records the id so the retry is processed.
    background.add_task(_handle_event, prov.name, eid, kind, event)
    return {"ok": True, "queued": True}


async def _handle_event(provider_name: str, eid: str, kind: str, event: Dict[str, Any]) -> None:
    try:
        await run_in_threadpool(service.handle_webhook, event)
    except Exception:                                           # noqa: BLE001
        store.forget_delivery(provider_name, eid)
        log.exception("brokerage webhook %s failed", kind)


# --------------------------------------------------------------- sandbox portal


def _sandbox() -> SandboxProvider:
    st = service.status()
    prov = service.provider() if st["enabled"] else None
    if not isinstance(prov, SandboxProvider):
        raise HTTPException(status_code=404, detail="Not found.")
    return prov


@router.get("/sandbox/portal", response_class=HTMLResponse)
async def sandbox_portal(session: str = "") -> HTMLResponse:
    prov = _sandbox()
    found = prov.portal_session(session)
    if not found:
        return HTMLResponse("<p>This sandbox link has expired. Go back to Optic and press Connect again.</p>",
                            status_code=410)
    options = "".join(
        '<label class="sc"><input type="radio" name="scenario" value="{v}"{c}> <b>{v}</b><span>{d}</span></label>'
        .format(v=html.escape(k), d=html.escape(v), c=" checked" if k == "standard" else "")
        for k, v in SANDBOX_SCENARIOS.items())
    repair = "<p class='note'>Reconnecting an existing sandbox connection.</p>" if found.get("reconnect") else ""
    page = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Sandbox brokerage</title>
<style>
:root{{--bg:#f6f6f4;--fg:#1c1c1a;--mut:#5f5f5a;--card:#fff;--line:#d8d8d2;--acc:#2456c9}}
@media (prefers-color-scheme:dark){{:root{{--bg:#141413;--fg:#ecece8;--mut:#a3a39c;--card:#1d1d1b;--line:#33332f;--acc:#7aa2ff}}}}
body{{margin:0;font:15px/1.5 -apple-system,system-ui,sans-serif;background:var(--bg);color:var(--fg)}}
main{{max-width:520px;margin:0 auto;padding:24px 16px}}
.banner{{border:1px dashed var(--acc);border-radius:8px;padding:10px 12px;margin-bottom:16px;font-weight:600}}
.sc{{display:grid;grid-template-columns:auto 1fr;gap:2px 10px;padding:10px 12px;border:1px solid var(--line);
border-radius:8px;margin:8px 0;background:var(--card);cursor:pointer}}
.sc span{{grid-column:2;color:var(--mut);font-size:13px}}
button{{font:inherit;padding:10px 16px;border-radius:8px;border:0;background:var(--acc);color:#fff;cursor:pointer;
min-height:44px}}
.note{{color:var(--mut);font-size:13px}}
</style></head><body><main>
<div class="banner">Sandbox. Not a real brokerage. No credentials are asked for and no real account is touched.</div>
<h1 style="font-size:20px;margin:0 0 4px">Authorise read-only access</h1>
<p class="note">In production this page is SnapTrade's hosted portal, where you choose your broker and sign in
there. Optic never sees that password.</p>{repair}
<form method="post" action="/api/brokerage/sandbox/authorize">
<input type="hidden" name="session" value="{session}">{options}
<p><button type="submit">Allow read-only access</button></p></form>
<form method="post" action="/api/brokerage/sandbox/abandon"><input type="hidden" name="session" value="{session}">
<button type="submit" style="background:transparent;color:var(--acc);padding-left:0">Cancel</button></form>
</main></body></html>""".format(session=html.escape(session), options=options, repair=repair)
    return HTMLResponse(page)


async def _form(request: Request) -> Dict[str, str]:
    """A urlencoded form, parsed by hand: Starlette's form parser needs
    python-multipart, which is not a dependency and is not worth adding for a
    two-field sandbox page."""
    from urllib.parse import parse_qs
    parsed = parse_qs((await request.body()).decode("utf-8", "replace"))
    return {k: v[0] for k, v in parsed.items() if v}


@router.post("/sandbox/authorize")
async def sandbox_authorize(request: Request) -> RedirectResponse:
    prov = _sandbox()
    form = await _form(request)
    try:
        target = prov.authorize(form.get("session", ""), form.get("scenario", "standard"))
    except ProviderError:
        return RedirectResponse("/?brokerage=expired#/brokerage", status_code=303)
    return RedirectResponse(target, status_code=303)


@router.post("/sandbox/abandon")
async def sandbox_abandon(request: Request) -> RedirectResponse:
    prov = _sandbox()
    form = await _form(request)
    found = prov.portal_session(form.get("session", ""))
    target = (found or {}).get("redirect") or "/#/brokerage"
    sep = "&" if "?" in target else "?"
    return RedirectResponse(target + sep + "status=ABANDONED", status_code=303)


# ------------------------------------------------------------- background job


async def background_loop(interval: int = 1800) -> None:
    """Every half hour: owed provider deletions, plan lapses, then daily
    syncs that are due. Each step is caught on its own so one failing does
    not stop the others."""
    await asyncio.sleep(60)
    while True:
        for step in (service.process_purges, service.enforce_lapses, service.auto_sync_due):
            try:
                await run_in_threadpool(step)
            except Exception as exc:                            # noqa: BLE001
                log.warning("brokerage background step %s failed: %s", step.__name__, type(exc).__name__)
        await asyncio.sleep(interval)
