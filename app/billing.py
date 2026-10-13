"""Paid plans through Stripe: Checkout to subscribe, the Customer Portal to
manage or cancel, and a verified webhook that is the only thing allowed to
change a plan.

**The browser never grants a plan.** Returning from Checkout shows a "thanks,
confirming" state; the plan changes when Stripe's signed webhook says the
subscription is active, and not before. A success URL is a page anyone can
type.

**Test mode only until the owner says otherwise.** A live secret key
(`sk_live_` or `rk_live_`) is refused unless `BILLING_LIVE_APPROVED=true` is
also set, so live billing cannot start by pasting the wrong key.

**Webhooks:** signature checked against the raw body (`Stripe-Signature`,
`t=`/`v1=`, HMAC-SHA256 of `"{t}.{body}"` with the `whsec_` secret, five-minute
tolerance; Stripe's docs as read 2026-10-12). Each event id is processed once:
the insert into `webhook_events` is the lock, and a handler that fails removes
its row so Stripe's retry is processed rather than acknowledged. Events can
arrive out of order, so each subscription row remembers the `created` time of
the last event applied and ignores anything older.

**Only Optic's price counts.** A subscription grants Pro only if one of its
items is `STRIPE_PRICE_ID`. The same Stripe account selling something else
must not hand out Optic plans.

No SDK: four endpoints over `requests`, which is already a dependency.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time
from typing import Any, Dict, Optional, Tuple

import requests
from fastapi import APIRouter, HTTPException, Request

from . import db, runtime
from .auth import deps, store as auth_store
from .brokerage import service as brokerage
from .brokerage import store as bstore

log = logging.getLogger("optic.billing")
router = APIRouter(prefix="/api/billing", tags=["billing"])

API = "https://api.stripe.com/v1"
TOLERANCE = 300
PAID_PLAN = "pro"
TERMINAL = ("canceled", "incomplete_expired")


def _key() -> str:
    return (os.environ.get("STRIPE_SECRET_KEY") or "").strip()


def mode() -> Optional[str]:
    k = _key()
    if not k:
        return None
    return "live" if "_live_" in k else "test"


def status() -> Dict[str, Any]:
    missing = [n for n in ("STRIPE_SECRET_KEY", "STRIPE_PRICE_ID", "STRIPE_WEBHOOK_SECRET")
               if not (os.environ.get(n) or "").strip()]
    if missing:
        return {"available": False, "reason": runtime.for_reader(
            "Plans are not on sale yet. Every account is on Free.",
            "Billing is off: set {}.".format(", ".join(missing)))}
    if mode() == "live" and (os.environ.get("BILLING_LIVE_APPROVED") or "").lower() != "true":
        return {"available": False, "reason": runtime.for_reader(
            "Plans are not on sale yet. Every account is on Free.",
            "A live Stripe key is set but BILLING_LIVE_APPROVED is not true. Refusing live billing.")}
    return {"available": True, "mode": mode(),
            "price_label": os.environ.get("BILLING_PRICE_LABEL") or "$20 a month"}


def _stripe(method: str, path: str, data: Optional[Dict[str, Any]] = None,
            idempotency_key: Optional[str] = None) -> Dict[str, Any]:
    headers = {"Authorization": "Bearer " + _key()}
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    try:
        resp = requests.request(method, API + path, data=data, headers=headers, timeout=20)
    except requests.RequestException as exc:
        raise HTTPException(status_code=503, detail="The payment provider did not answer. Try again "
                                                    "in a minute.") from exc
    if resp.status_code >= 400:
        # The body can name the customer; log the status and Stripe's error
        # type only.
        try:
            kind = (resp.json().get("error") or {}).get("type")
        except ValueError:
            kind = None
        log.warning("stripe %s %s -> %s (%s)", method, path, resp.status_code, kind)
        raise HTTPException(status_code=502, detail="The payment provider refused the request.")
    return resp.json()


def _sub_row(user_id: str) -> Optional[Dict[str, Any]]:
    return db.row("SELECT * FROM subscriptions WHERE user_id = ? ORDER BY created_at DESC LIMIT 1", (user_id,))


# ------------------------------------------------------------------ routes


@router.get("/status")
async def billing_status(request: Request) -> Dict[str, Any]:
    user = deps.current_user(request)
    out = status()
    if user:
        out["subscription"] = auth_store.subscription(user["id"])
        out["can_manage"] = bool((_sub_row(user["id"]) or {}).get("provider_customer_id"))
    return out


@router.post("/checkout")
async def checkout(request: Request) -> Dict[str, Any]:
    # Signed in, not necessarily confirmed: Stripe collects and confirms the
    # billing email itself, and production mail is not configured yet, so
    # requiring a confirmed address would mean nobody could subscribe.
    user = deps.require_user(request)
    deps.csrf_guard(request)
    st = status()
    if not st["available"]:
        raise HTTPException(status_code=503, detail=st["reason"])
    sub = auth_store.subscription(user["id"])
    row = _sub_row(user["id"]) or {}
    open_sub = row.get("provider_subscription_id") and row.get("provider_status") not in TERMINAL
    if sub["plan"] == PAID_PLAN or open_sub:
        # Also refused while a subscription exists that has not ended, even
        # before its webhook made the plan Pro: two quick checkouts used to be
        # two subscriptions on one account (review M6).
        raise HTTPException(status_code=409, detail="You already have a Pro subscription. Use Manage billing "
                                                    "to change or cancel it.")
    base = runtime.base_url()
    data: Dict[str, Any] = {
        "mode": "subscription",
        "line_items[0][price]": os.environ["STRIPE_PRICE_ID"],
        "line_items[0][quantity]": "1",
        "client_reference_id": user["id"],
        "metadata[user_id]": user["id"],
        "subscription_data[metadata][user_id]": user["id"],
        "success_url": base + "/?billing=success#/settings",
        "cancel_url": base + "/?billing=cancel#/settings",
        "allow_promotion_codes": "true",
    }
    if row.get("provider_customer_id"):
        data["customer"] = row["provider_customer_id"]
    else:
        data["customer_email"] = user["email"]
    # A double click inside the same minute returns the same session rather
    # than two open checkouts.
    session = _stripe("POST", "/checkout/sessions", data,
                      idempotency_key="optic-checkout-{}-{}".format(user["id"], int(time.time() // 60)))
    return {"url": session.get("url")}


@router.post("/portal")
async def portal(request: Request) -> Dict[str, Any]:
    user = deps.require_user(request)
    deps.csrf_guard(request)
    st = status()
    if not st["available"]:
        raise HTTPException(status_code=503, detail=st["reason"])
    customer = (_sub_row(user["id"]) or {}).get("provider_customer_id")
    if not customer:
        raise HTTPException(status_code=404, detail="There is no billing account for this sign-in yet.")
    session = _stripe("POST", "/billing_portal/sessions",
                      {"customer": customer, "return_url": runtime.base_url() + "/#/settings"})
    return {"url": session.get("url")}


@router.post("/webhook")
async def webhook(request: Request) -> Dict[str, Any]:
    body = await request.body()
    secret = (os.environ.get("STRIPE_WEBHOOK_SECRET") or "").strip()
    if not secret:
        raise HTTPException(status_code=503, detail="Billing is not configured.")
    if not verify_signature(body, request.headers.get("stripe-signature") or "", secret):
        raise HTTPException(status_code=400, detail="Signature did not verify.")
    import json
    try:
        event = json.loads(body)
    except ValueError:
        raise HTTPException(status_code=400, detail="Not JSON.")
    if bool(event.get("livemode")) != (mode() == "live"):
        # A test event at a live endpoint, or the reverse: never apply it.
        return {"ok": True, "ignored": "mode mismatch"}
    eid, etype = str(event.get("id") or ""), str(event.get("type") or "")
    if not eid:
        raise HTTPException(status_code=400, detail="No event id.")
    if not bstore.first_delivery("stripe", eid, etype):
        return {"ok": True, "duplicate": True}
    try:
        result = apply_event(event)
    except Exception:
        bstore.forget_delivery("stripe", eid)
        log.exception("stripe webhook %s failed", etype)
        raise HTTPException(status_code=500, detail="Not processed; retry.")
    return {"ok": True, "result": result}


# ---------------------------------------------------------------- the logic


def verify_signature(body: bytes, header: str, secret: str, now: Optional[float] = None) -> bool:
    parts: Dict[str, list] = {}
    for item in header.split(","):
        k, _, v = item.strip().partition("=")
        parts.setdefault(k, []).append(v)
    try:
        stamp = int((parts.get("t") or [""])[0])
    except ValueError:
        return False
    if abs((now or time.time()) - stamp) > TOLERANCE:
        return False
    expected = hmac.new(secret.encode(), "{}.".format(stamp).encode() + body, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, sig) for sig in parts.get("v1") or [])


def _find_user(obj: Dict[str, Any]) -> Optional[str]:
    uid = (obj.get("metadata") or {}).get("user_id") or obj.get("client_reference_id")
    if uid and auth_store.get_user(uid):
        return uid
    for col, val in (("provider_subscription_id", obj.get("subscription") if obj.get("object") != "subscription"
                      else obj.get("id")), ("provider_customer_id", obj.get("customer"))):
        if val:
            found = db.row("SELECT user_id FROM subscriptions WHERE provider = 'stripe' AND {} = ?".format(col),
                           (val,))
            if found:
                return found["user_id"]
    return None


def _has_our_price(sub: Dict[str, Any]) -> bool:
    want = os.environ.get("STRIPE_PRICE_ID") or ""
    for item in ((sub.get("items") or {}).get("data") or []):
        if ((item.get("price") or {}).get("id")) == want:
            return True
    return False


def _period_end(sub: Dict[str, Any]) -> Optional[str]:
    end = sub.get("current_period_end")
    if end is None:
        items = (sub.get("items") or {}).get("data") or []
        end = items[0].get("current_period_end") if items else None
    if not end:
        return None
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(end)))


def _write(user_id: str, created: int, **fields: Any) -> bool:
    """Apply fields to the user's subscription row if this event is newer than
    the last one applied. Returns whether anything was written."""
    row = _sub_row(user_id)
    if row and row.get("last_event_at") and int(row["last_event_at"]) > created:
        return False
    fields["last_event_at"] = created
    fields["updated_at"] = db.utcnow()
    if not row:
        db.execute("INSERT INTO subscriptions (id, user_id, plan, status, created_at, updated_at) "
                   "VALUES (?,?,'free','active',?,?)", (db.new_id(), user_id, db.utcnow(), db.utcnow()))
        row = _sub_row(user_id)
    cols = ", ".join("{} = ?".format(k) for k in fields)
    db.execute("UPDATE subscriptions SET {} WHERE id = ?".format(cols), tuple(fields.values()) + (row["id"],))
    return True


def apply_event(event: Dict[str, Any]) -> str:
    etype = event.get("type") or ""
    obj = ((event.get("data") or {}).get("object") or {})
    created = int(event.get("created") or 0)
    if etype == "checkout.session.completed":
        uid = _find_user(obj)
        if not uid:
            return "no-user"
        # Links the Stripe customer and subscription to the account. The plan
        # itself comes from the subscription events, which carry its status.
        _write(uid, created - 1, provider="stripe", provider_customer_id=obj.get("customer"),
               provider_subscription_id=obj.get("subscription"))
        return "linked"
    if etype in ("customer.subscription.created", "customer.subscription.updated",
                 "customer.subscription.deleted", "customer.subscription.paused",
                 "customer.subscription.resumed"):
        uid = _find_user(obj)
        if not uid:
            return "no-user"
        stripe_status = "canceled" if etype == "customer.subscription.deleted" else str(obj.get("status") or "")
        row = _sub_row(uid) or {}
        stored = row.get("provider_subscription_id")
        if stored and stored != obj.get("id") and row.get("provider_status") in auth_store.ENTITLED_STATUSES:
            # A second subscription while the stored one is live. Applying it
            # would let cancelling either one end Pro while the other keeps
            # billing. Logged for a refund by hand.
            log.error("stripe: second subscription %s for a user who already has %s; not applied",
                      obj.get("id"), stored)
            return "second-subscription"
        ours = _has_our_price(obj)
        entitled = ours and stripe_status in auth_store.ENTITLED_STATUSES
        wrote = _write(uid, created,
                       plan=PAID_PLAN if entitled else "free",
                       status=stripe_status if stripe_status in auth_store.ENTITLED_STATUSES else "active",
                       provider="stripe", provider_status=stripe_status,
                       provider_customer_id=obj.get("customer"), provider_subscription_id=obj.get("id"),
                       cancel_at_period_end=1 if obj.get("cancel_at_period_end") else 0,
                       current_period_end=_period_end(obj))
        if wrote:
            brokerage.on_plan_change(uid)
        return ("pro" if entitled else "free") if wrote else "stale"
    if etype == "invoice.payment_failed":
        # The subscription's own update event moves it to past_due; nothing
        # to change here, and past_due stays entitled while Stripe retries.
        return "noted"
    return "ignored"


def cancel_for_deletion(user_id: str) -> None:
    """Cancel a live Stripe subscription immediately, before the account it
    belongs to is deleted. Raises a 502 if Stripe will not, so the deletion
    stops rather than leaving a subscription nobody can manage."""
    row = _sub_row(user_id) or {}
    if row.get("provider") != "stripe" or not row.get("provider_subscription_id"):
        return
    if row.get("provider_status") in ("canceled", "incomplete_expired"):
        return
    if not _key():
        raise HTTPException(status_code=503, detail="Your subscription could not be cancelled because "
                                                    "billing is unavailable. Nothing was deleted.")
    _stripe("DELETE", "/subscriptions/{}".format(row["provider_subscription_id"]))
