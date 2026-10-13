"""Stripe billing: signed webhooks are the only thing that changes a plan.

Covers signature verification, duplicate and out-of-order events, the price
check, cancellation at period end and immediately, past-due grace, the
live-key refusal, and the brokerage pause that follows a lapsed plan.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app import billing, db
from app.auth import config, store as auth_store
from app.brokerage import service, store as bstore

GOOD = "tungsten-carbide-9"
WHSEC = "whsec_test_123"
PRICE = "price_optic_pro_test"


@pytest.fixture(autouse=True)
def env(accounts, monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_abc")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", WHSEC)
    monkeypatch.setenv("STRIPE_PRICE_ID", PRICE)
    monkeypatch.delenv("BILLING_LIVE_APPROVED", raising=False)
    return accounts


def reader(email="payer@example.com"):
    c = TestClient(main.app)
    c.post("/api/auth/register", json={"first_name": "P", "last_name": "Ayer", "email": email,
                                       "password": GOOD, "confirm_password": GOOD})
    c.headers["X-Optic-CSRF"] = c.cookies.get(config.CSRF_COOKIE)
    return c, auth_store.get_user_by_email(email)


def signed(payload: dict, secret=WHSEC, t=None):
    body = json.dumps(payload).encode()
    t = int(t or time.time())
    sig = hmac.new(secret.encode(), "{}.".format(t).encode() + body, hashlib.sha256).hexdigest()
    return body, {"Stripe-Signature": "t={},v1={}".format(t, sig), "Content-Type": "application/json"}


def sub_event(uid, status="active", etype="customer.subscription.updated", created=None, eid=None,
              price=PRICE, cancel_at_period_end=False):
    return {"id": eid or "evt_{}".format(time.time_ns()), "type": etype, "livemode": False,
            "created": created or int(time.time()),
            "data": {"object": {"object": "subscription", "id": "sub_1", "customer": "cus_1",
                                "status": status, "metadata": {"user_id": uid},
                                "cancel_at_period_end": cancel_at_period_end,
                                "items": {"data": [{"price": {"id": price},
                                                    "current_period_end": int(time.time()) + 86400 * 30}]}}}}


def deliver(event, **kw):
    body, headers = signed(event, **kw)
    return TestClient(main.app).post("/api/billing/webhook", content=body, headers=headers)


# --------------------------------------------------------------- signatures


def test_unsigned_or_wrongly_signed_events_are_rejected():
    _, user = reader()
    body = json.dumps(sub_event(user["id"])).encode()
    c = TestClient(main.app)
    assert c.post("/api/billing/webhook", content=body).status_code == 400
    assert deliver(sub_event(user["id"]), secret="whsec_wrong").status_code == 400
    assert auth_store.subscription(user["id"])["plan"] == "free"


def test_old_signatures_are_rejected():
    _, user = reader()
    assert deliver(sub_event(user["id"]), t=time.time() - 3600).status_code == 400


def test_signature_scheme_matches_stripe():
    body = b'{"a":1}'
    t = 1700000000
    sig = hmac.new(WHSEC.encode(), b"1700000000." + body, hashlib.sha256).hexdigest()
    assert billing.verify_signature(body, "t={},v1=bad,v1={}".format(t, sig), WHSEC, now=t + 10)
    assert not billing.verify_signature(body, "t={},v1={}".format(t, sig), WHSEC, now=t + 301)


# -------------------------------------------------------------- entitlements


def test_active_subscription_grants_pro_and_cancellation_removes_it():
    _, user = reader()
    assert deliver(sub_event(user["id"], "active")).json()["result"] == "pro"
    sub = auth_store.subscription(user["id"])
    assert sub["plan"] == "pro" and sub["current_period_end"]
    assert deliver(sub_event(user["id"], "canceled", etype="customer.subscription.deleted")).json()["result"] == "free"
    assert auth_store.subscription(user["id"])["plan"] == "free"


def test_cancel_at_period_end_keeps_pro_until_the_end():
    _, user = reader()
    deliver(sub_event(user["id"], "active", cancel_at_period_end=True))
    sub = auth_store.subscription(user["id"])
    assert sub["plan"] == "pro" and sub["cancel_at_period_end"] is True


def test_past_due_stays_entitled_unpaid_does_not():
    _, user = reader()
    deliver(sub_event(user["id"], "past_due"))
    assert auth_store.subscription(user["id"])["plan"] == "pro"
    deliver(sub_event(user["id"], "unpaid", created=int(time.time()) + 5))
    assert auth_store.subscription(user["id"])["plan"] == "free"


def test_duplicate_events_apply_once():
    _, user = reader()
    ev = sub_event(user["id"], "active", eid="evt_same")
    assert deliver(ev).json()["result"] == "pro"
    assert deliver(ev).json()["duplicate"] is True


def test_out_of_order_events_cannot_undo_newer_state():
    _, user = reader()
    now = int(time.time())
    deliver(sub_event(user["id"], "canceled", etype="customer.subscription.deleted", created=now))
    r = deliver(sub_event(user["id"], "active", created=now - 100))
    assert r.json()["result"] == "stale"
    assert auth_store.subscription(user["id"])["plan"] == "free"


def test_another_products_price_does_not_grant_pro():
    _, user = reader()
    deliver(sub_event(user["id"], "active", price="price_something_else"))
    assert auth_store.subscription(user["id"])["plan"] == "free"


def test_live_event_at_a_test_endpoint_is_ignored():
    _, user = reader()
    ev = sub_event(user["id"])
    ev["livemode"] = True
    assert deliver(ev).json()["ignored"] == "mode mismatch"
    assert auth_store.subscription(user["id"])["plan"] == "free"


def test_failed_handler_lets_the_retry_through(monkeypatch):
    _, user = reader()
    ev = sub_event(user["id"], eid="evt_retry")
    real = billing.apply_event
    monkeypatch.setattr(billing, "apply_event", lambda e: (_ for _ in ()).throw(RuntimeError("x")))
    assert deliver(ev).status_code == 500
    monkeypatch.setattr(billing, "apply_event", real)
    assert deliver(ev).json()["result"] == "pro"


def test_checkout_completed_links_customer_without_granting():
    _, user = reader()
    ev = {"id": "evt_co", "type": "checkout.session.completed", "livemode": False, "created": int(time.time()),
          "data": {"object": {"object": "checkout.session", "client_reference_id": user["id"],
                              "customer": "cus_9", "subscription": "sub_9", "metadata": {}}}}
    assert deliver(ev).json()["result"] == "linked"
    row = db.row("SELECT * FROM subscriptions WHERE user_id = ?", (user["id"],))
    assert row["provider_customer_id"] == "cus_9" and row["plan"] == "free"


# ------------------------------------------------------------------- routes


def test_live_keys_are_refused_without_explicit_approval(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_live_abc")
    assert billing.status()["available"] is False
    c, _ = reader()
    assert c.post("/api/billing/checkout").status_code == 503
    monkeypatch.setenv("BILLING_LIVE_APPROVED", "true")
    assert billing.status()["available"] is True


def test_checkout_creates_a_session_with_the_user_bound(monkeypatch):
    c, user = reader()
    sent = {}

    def fake(method, path, data=None, idempotency_key=None):
        sent.update(method=method, path=path, data=data, key=idempotency_key)
        return {"url": "https://checkout.stripe.com/c/pay/cs_test_1"}
    monkeypatch.setattr(billing, "_stripe", fake)
    r = c.post("/api/billing/checkout")
    assert r.status_code == 200 and r.json()["url"].startswith("https://checkout.stripe.com/")
    assert sent["path"] == "/checkout/sessions" and sent["data"]["client_reference_id"] == user["id"]
    assert sent["data"]["subscription_data[metadata][user_id]"] == user["id"]
    assert sent["key"].startswith("optic-checkout-")
    # The success URL does not grant anything by itself.
    assert auth_store.subscription(user["id"])["plan"] == "free"


def test_checkout_refused_when_already_pro(monkeypatch):
    c, user = reader()
    auth_store.set_plan(user["id"], "pro")
    assert c.post("/api/billing/checkout").status_code == 409


def test_checkout_needs_sign_in_and_csrf():
    assert TestClient(main.app).post("/api/billing/checkout").status_code == 401
    c, _ = reader()
    del c.headers["X-Optic-CSRF"]
    assert c.post("/api/billing/checkout").status_code == 403


def test_portal_only_for_own_customer(monkeypatch):
    c, user = reader()
    assert c.post("/api/billing/portal").status_code == 404
    deliver(sub_event(user["id"], "active"))
    monkeypatch.setattr(billing, "_stripe", lambda m, p, d=None, idempotency_key=None:
                        {"url": "https://billing.stripe.com/p/session/x"} if d["customer"] == "cus_1" else {})
    assert c.post("/api/billing/portal").json()["url"].startswith("https://billing.stripe.com/")


def test_deleting_the_account_cancels_the_subscription_first(monkeypatch):
    c, user = reader()
    deliver(sub_event(user["id"], "active"))
    calls = []
    monkeypatch.setattr(billing, "_stripe", lambda m, p, d=None, idempotency_key=None: calls.append((m, p)) or {})
    r = c.post("/api/auth/delete-account", json={"confirm_email": "payer@example.com", "password": GOOD})
    assert r.status_code == 200 and calls == [("DELETE", "/subscriptions/sub_1")]


def test_account_deletion_stops_if_stripe_will_not_cancel(monkeypatch):
    from fastapi import HTTPException
    c, user = reader()
    deliver(sub_event(user["id"], "active"))

    def refuse(*a, **k):
        raise HTTPException(status_code=502, detail="refused")
    monkeypatch.setattr(billing, "_stripe", refuse)
    r = c.post("/api/auth/delete-account", json={"confirm_email": "payer@example.com", "password": GOOD})
    assert r.status_code == 502
    assert auth_store.get_user(user["id"]) is not None


def test_status_reports_price_label_and_plan():
    c, _ = reader()
    st = c.get("/api/billing/status").json()
    assert st["available"] and st["mode"] == "test" and st["price_label"] == "$20 a month"
    assert st["subscription"]["plan"] == "free"


# -------------------------------------------- billing -> brokerage, end to end


def test_cancellation_pauses_brokerage_syncing(monkeypatch):
    monkeypatch.setenv("BROKERAGE_PROVIDER", "sandbox")
    monkeypatch.setenv("OPTIC_DATA_KEY", base64.urlsafe_b64encode(b"k" * 32).decode())
    monkeypatch.setattr(service, "_provider", None)
    _, user = reader()
    deliver(sub_event(user["id"], "active"))
    prov = service.provider()
    made = prov.register_user()
    bstore.create_link(user["id"], "sandbox", made["user_id"], made["secret"])
    bstore.upsert_connection(user["id"], "sandbox", "sbx-standard-1", "Sandbox", "active")
    deliver(sub_event(user["id"], "canceled", etype="customer.subscription.deleted",
                      created=int(time.time()) + 5))
    assert bstore.connections(user["id"])[0]["status"] == "paused"
    assert bstore.link(user["id"])["paused_at"]


# ------------------------------------------------------------ Milo allowance


def test_pro_has_a_monthly_milo_cap(monkeypatch):
    from app.auth import ratelimit
    c, user = reader()
    auth_store.set_plan(user["id"], "pro")
    monkeypatch.setitem(auth_store.PLANS["pro"], "ai_calls_per_month", 2)
    from fastapi import HTTPException
    from starlette.requests import Request
    req = Request({"type": "http", "headers": [(b"cookie", "; ".join(
        "{}={}".format(k, v) for k, v in c.cookies.items()).encode())], "client": ("1.2.3.4", 1)})
    main._spend_guard(req)
    req.state._state.clear() if hasattr(req.state, "_state") else None
    main._spend_guard(req)
    with pytest.raises(HTTPException) as hit:
        main._spend_guard(req)
    assert hit.value.status_code == 429 and "30 days" in hit.value.detail
    assert ratelimit.allowance("ai_day", ratelimit.key_bucket(user["id"]), 20, 86400)["used"] == 2
