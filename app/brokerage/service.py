"""Linking, syncing, disconnecting and the plan rules around them.

**Off unless configured.** `BROKERAGE_PROVIDER` names the provider (`snaptrade`
or `sandbox`). Unset, every brokerage route answers "not available" and the
nav entry stays hidden, so this code can sit on production doing nothing until
the owner sets the keys. The sandbox refuses to run on a hosting platform unless
`BROKERAGE_SANDBOX_ON_HOST=true` (a staging service), because sandbox holdings
on the live site would read as somebody's real money. Both need
`OPTIC_DATA_KEY`: without a master key nothing is stored at all.

**Paid plans link; everyone can leave.** Linking and syncing need a plan with
`brokerage_connections` above zero. Disconnecting and deleting never check the
plan: a reader whose subscription ended still owns their data.

**When a plan ends** (`on_plan_change`, called from the billing webhook):
1. Syncing stops at once. What was stored stays visible, labelled as not
   updating since the plan ended.
2. After `LAPSE_CLOSE_DAYS` (7) the provider-side user is deleted, which ends
   the broker authorisation and the aggregator's per-user charge (SnapTrade
   bills inactive connections too). Resubscribing before then resumes as if
   nothing happened; after it, the reader reconnects.
3. After `LAPSE_PURGE_DAYS` (30) Optic deletes its own copy, including the
   data key, so backups become unreadable too.
"""

from __future__ import annotations

import dataclasses
import logging
import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from .. import db, runtime, vault
from ..auth import admin as auth_admin
from ..auth import store as auth_store
from . import portfolio, store
from .providers import (AuthExpired, NotFoundAtProvider, Provider, ProviderError, ProviderOutage,
                        SandboxProvider, UnsupportedBroker)

log = logging.getLogger("optic.brokerage")

LAPSE_CLOSE_DAYS = 7
LAPSE_PURGE_DAYS = 30
AUTO_SYNC_HOURS = 20          # the aggregator itself refreshes once a day on the Daily plan

_provider: Optional[Provider] = None
_provider_key: Optional[str] = None
_user_locks: Dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


class NotAvailable(RuntimeError):
    pass


class NotEntitled(RuntimeError):
    pass


class NeedsConsent(RuntimeError):
    pass


# ------------------------------------------------------------------- consent
#
# The reader ticks an unticked box agreeing to Optic's terms and privacy
# policy and the provider's end-user terms before the first link, and again
# whenever the version changes. The documents themselves are the owner's (and
# counsel's) to write; their URLs and version are configuration, and the
# SnapTrade provider will not switch on without them.


def terms() -> Dict[str, Optional[str]]:
    return {
        # Defaults name the drafts in ~/Optic/work/legal (not yet reviewed or
        # published). Set BROKERAGE_TERMS_VERSION to the final ids when the
        # reviewed documents go live, and every reader is asked again.
        "version": (os.environ.get("BROKERAGE_TERMS_VERSION")
                    or "terms-draft-2026-10-12+privacy-draft-2026-10-12").strip(),
        "terms_url": (os.environ.get("TERMS_URL") or "").strip() or None,
        "privacy_url": (os.environ.get("PRIVACY_URL") or "").strip() or None,
        "provider_terms_url": (os.environ.get("SNAPTRADE_TERMS_URL") or "").strip() or None,
    }


def consent_state(user_id: str) -> Dict[str, Any]:
    t = terms()
    row = store.consent_row(user_id, t["version"])
    return dict(t, accepted=bool(row), accepted_at=(row or {}).get("accepted_at"))


# ------------------------------------------------------------- configuration


def _env_flag(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in ("1", "true", "yes", "on")


def status() -> Dict[str, Any]:
    """Whether brokerage linking can run here, and if not, the sentence why."""
    choice = (os.environ.get("BROKERAGE_PROVIDER") or "").strip().lower()
    if not choice:
        return {"enabled": False, "reason": "Brokerage linking is not switched on for this deployment."}
    if not vault.available():
        return {"enabled": False, "reason": runtime.for_reader(
            "Brokerage linking is not available right now.",
            "Set OPTIC_DATA_KEY (python -m app.vault prints one) before enabling brokerage linking.")}
    if choice == "sandbox" and runtime.is_hosted() and not _env_flag("BROKERAGE_SANDBOX_ON_HOST"):
        return {"enabled": False, "reason": "The brokerage sandbox does not run on a hosted deployment."}
    if choice == "snaptrade" and not (os.environ.get("SNAPTRADE_CLIENT_ID")
                                      and os.environ.get("SNAPTRADE_CONSUMER_KEY")):
        return {"enabled": False, "reason": runtime.for_reader(
            "Brokerage linking is not available right now.",
            "Set SNAPTRADE_CLIENT_ID and SNAPTRADE_CONSUMER_KEY.")}
    if choice == "snaptrade" and not all(terms()[k] for k in ("terms_url", "privacy_url", "provider_terms_url")):
        # Real holdings are not linked under terms nobody has published.
        return {"enabled": False, "reason": runtime.for_reader(
            "Brokerage linking is not available right now.",
            "Set TERMS_URL, PRIVACY_URL and SNAPTRADE_TERMS_URL (published, reviewed documents) "
            "before enabling SnapTrade.")}
    if choice not in ("sandbox", "snaptrade"):
        return {"enabled": False, "reason": "Unknown BROKERAGE_PROVIDER: {}".format(choice)}
    prov = provider()
    return {"enabled": True, "provider": prov.name, "label": prov.label, "mode": prov.mode}


def provider() -> Provider:
    global _provider, _provider_key
    choice = (os.environ.get("BROKERAGE_PROVIDER") or "").strip().lower()
    if _provider is not None and _provider_key == choice:
        return _provider
    if choice == "snaptrade":
        from .snaptrade import SnapTradeProvider
        _provider = SnapTradeProvider.from_env()
    elif choice == "sandbox":
        _provider = SandboxProvider()
    else:
        raise NotAvailable("Brokerage linking is not switched on for this deployment.")
    _provider_key = choice
    return _provider


def require_available() -> Provider:
    s = status()
    if not s["enabled"]:
        raise NotAvailable(s["reason"])
    return provider()


def _lock_for(user_id: str) -> threading.Lock:
    with _locks_guard:
        return _user_locks.setdefault(user_id, threading.Lock())


# --------------------------------------------------------------- entitlement


def entitlement(user: Dict[str, Any]) -> Dict[str, Any]:
    sub = auth_store.subscription(user["id"])
    limits = sub["limits"]
    if auth_admin.is_admin(user):
        limits = dict(limits, brokerage_connections=max(3, limits.get("brokerage_connections") or 0),
                      brokerage_accounts=max(10, limits.get("brokerage_accounts") or 0),
                      brokerage_manual_syncs_per_day=max(5, limits.get("brokerage_manual_syncs_per_day") or 0))
    max_conn = int(limits.get("brokerage_connections") or 0)
    return {
        "plan": sub["plan"], "plan_label": sub["label"], "status": sub["status"],
        "can_link": max_conn > 0,
        "max_connections": max_conn,
        "max_accounts": int(limits.get("brokerage_accounts") or 0),
        "manual_syncs_per_day": int(limits.get("brokerage_manual_syncs_per_day") or 0),
        "cancel_at_period_end": sub.get("cancel_at_period_end"),
        "current_period_end": sub.get("current_period_end"),
    }


# ------------------------------------------------------------------- linking


def _credentials(user_id: str) -> Optional[Dict[str, str]]:
    row = store.link(user_id)
    if not row:
        return None
    return {"provider_user_id": row["provider_user_id"], "secret": store.secret(user_id, row)}


def ensure_link(user_id: str, prov: Provider) -> Dict[str, str]:
    row = store.link(user_id)
    if row and row["provider"] == prov.name and not row.get("provider_removed_at"):
        return {"provider_user_id": row["provider_user_id"], "secret": store.secret(user_id, row)}
    if row:
        # A link closed at the provider (plan lapse) or made with another
        # provider: start over. Local rows go; an old provider user that was
        # not already deleted is queued for deletion.
        if not row.get("provider_removed_at"):
            store.queue_purge(row["provider"], row["provider_user_id"], None, "replaced by a new link")
        store.purge_local(user_id)
    made = prov.register_user()
    store.create_link(user_id, prov.name, made["user_id"], made["secret"])
    return {"provider_user_id": made["user_id"], "secret": made["secret"]}


def start_link(user: Dict[str, Any], redirect_base: str, reconnect_id: Optional[str] = None,
               consent_version: Optional[str] = None, ip_hash: Optional[str] = None) -> str:
    prov = require_available()
    ent = entitlement(user)
    if not ent["can_link"]:
        raise NotEntitled("Linking a brokerage is part of the paid plan.")
    version = terms()["version"]
    if not store.has_consent(user["id"], version):
        if consent_version != version:
            raise NeedsConsent("Agree to the terms first. Tick the box above Connect.")
        store.record_consent(user["id"], version, ip_hash)
    current = [c for c in store.connections(user["id"]) if c["status"] != "disconnected"]
    reconnect_provider_id = None
    if reconnect_id:
        conn = store.connection(user["id"], reconnect_id)
        if not conn:
            raise LookupError("No such connection.")
        reconnect_provider_id = conn["provider_connection_id"]
    elif len(current) >= ent["max_connections"]:
        raise NotEntitled("Your plan links up to {} brokerage connection{}. Disconnect one first."
                          .format(ent["max_connections"], "" if ent["max_connections"] == 1 else "s"))
    creds = ensure_link(user["id"], prov)
    known = [c.id for c in prov.list_connections(creds["provider_user_id"], creds["secret"])]
    state = store.new_link_state(user["id"], reconnect_id, known)
    redirect = "{}/api/brokerage/callback?state={}".format(redirect_base.rstrip("/"), state)
    return prov.portal_url(creds["provider_user_id"], creds["secret"], redirect,
                           reconnect=reconnect_provider_id)


def finish_link(user: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    """Import what this link created, then sync it. Called after the portal
    hands the browser back with a state token this reader started.

    Only one connection is imported per state: the one that did not exist
    when the link started, or the connection being repaired. Anything else
    the provider holds for this reader that Optic does not know about is
    removed at the provider, so a portal link someone else completed cannot
    be swept into this account later and is not billed (review M1). A
    connection that is not read-only is refused and removed (review H4)."""
    prov = require_available()
    creds = _credentials(user["id"])
    if not creds:
        raise LookupError("No brokerage link was started for this account.")
    ent = entitlement(user)
    import json as _json
    known_at_start = set(_json.loads(state.get("known_ids") or "[]"))
    repairing = store.connection(user["id"], state["reconnect_id"]) if state.get("reconnect_id") else None
    ours = {c["provider_connection_id"]: c for c in store.connections(user["id"])}
    found = prov.list_connections(creds["provider_user_id"], creds["secret"])
    new = [c for c in found if c.id not in known_at_start and c.id not in ours]
    target = None
    if repairing:
        target = next((c for c in found if c.id == repairing["provider_connection_id"]), None)
    elif len(new) == 1:
        target = new[0]
    synced, refused, over_limit = [], [], []
    for conn in found:
        if conn.id in ours and (target is None or conn.id != target.id):
            continue                                    # already Optic's; untouched here
        if target is not None and conn.id == target.id:
            continue
        # Not Optic's and not this link's: remove it at the provider.
        try:
            prov.remove_connection(creds["provider_user_id"], creds["secret"], conn.id)
        except NotFoundAtProvider:
            pass
        except ProviderError as exc:
            store.queue_purge(prov.name, creds["provider_user_id"], conn.id, _safe(exc))
    if target is not None:
        existing = ours.get(target.id)
        active = [c for c in store.connections(user["id"]) if c["status"] != "disconnected"]
        if target.read_only is not True:
            try:
                prov.remove_connection(creds["provider_user_id"], creds["secret"], target.id)
            except NotFoundAtProvider:
                pass
            except ProviderError as exc:
                store.queue_purge(prov.name, creds["provider_user_id"], target.id, _safe(exc))
            if existing:
                store.delete_connection(user["id"], existing["id"])
            refused.append(target.institution)
        elif existing is None and len(active) >= ent["max_connections"]:
            try:
                prov.remove_connection(creds["provider_user_id"], creds["secret"], target.id)
            except ProviderError as exc:
                store.queue_purge(prov.name, creds["provider_user_id"], target.id, _safe(exc))
            over_limit.append(target.institution)
        else:
            row = store.upsert_connection(user["id"], prov.name, target.id, target.institution,
                                          "expired" if target.disabled else "active", target.disabled_reason)
            if not target.disabled:
                synced.append(sync_connection(user, row, prov=prov, creds=creds))
    db.execute("UPDATE brokerage_users SET paused_at = NULL WHERE user_id = ?", (user["id"],))
    return {"synced": synced, "over_limit": over_limit, "refused": refused,
            "imported": target.institution if target is not None and not refused and not over_limit else None}


# ------------------------------------------------------------------- syncing


def _payload(h, acct) -> Dict[str, Any]:
    return {
        "positions": [dataclasses.asdict(p) for p in h.positions],
        "options": [dataclasses.asdict(o) for o in h.options],
        "cash": [dataclasses.asdict(c) for c in h.cash],
        "problems": list(h.problems),
        "total_value": acct.total_value,
        "currency": acct.currency,
        "fetched_at": db.utcnow(),
    }


def sync_connection(user: Dict[str, Any], conn: Dict[str, Any], prov: Optional[Provider] = None,
                    creds: Optional[Dict[str, str]] = None, refresh: bool = False,
                    only_account: Optional[str] = None) -> Dict[str, Any]:
    """Pull every account under one connection. Never raises for a provider
    problem: it records it on the connection and returns what happened."""
    uid = user["id"]
    prov = prov or require_available()
    lock = _lock_for(uid)
    if not lock.acquire(blocking=False):
        return {"connection_id": conn["id"], "result": "busy",
                "message": "A sync for this account is already running."}
    try:
        if not entitlement(user)["can_link"]:
            return {"connection_id": conn["id"], "result": "paused",
                    "message": "Syncing is paused because the paid plan has ended."}
        creds = creds or _credentials(uid)
        if not creds:
            return {"connection_id": conn["id"], "result": "error", "message": "Not linked."}
        store.set_connection(uid, conn["id"], last_attempt_at=db.utcnow())
        try:
            # The connection itself first. Without this, a connection removed
            # or broken at the provider came back as zero accounts, every
            # stored account was marked missing, and the sync said "ok".
            live = {c.id: c for c in prov.list_connections(creds["provider_user_id"], creds["secret"])}
            here = live.get(conn["provider_connection_id"])
            if here is None:
                store.set_connection(uid, conn["id"], status="error",
                                     status_reason="This connection no longer exists at the provider. "
                                                   "Reconnect it, or disconnect to remove it here.")
                return {"connection_id": conn["id"], "result": "error"}
            if here.disabled:
                raise AuthExpired(here.disabled_reason or "disabled")
            accts = [a for a in prov.list_accounts(creds["provider_user_id"], creds["secret"])
                     if a.connection_id == conn["provider_connection_id"]]
            if only_account:
                accts = [a for a in accts if a.id == only_account] or accts
        except AuthExpired:
            store.set_connection(uid, conn["id"], status="expired",
                                 status_reason="The broker needs you to sign in again.")
            return {"connection_id": conn["id"], "result": "expired"}
        except ProviderOutage:
            store.set_connection(uid, conn["id"], status="outage",
                                 status_reason="The provider did not respond. Showing the last good data.")
            return {"connection_id": conn["id"], "result": "outage"}
        except UnsupportedBroker as exc:
            store.set_connection(uid, conn["id"], status="unsupported", status_reason=str(exc)[:200])
            return {"connection_id": conn["id"], "result": "unsupported"}
        except ProviderError as exc:
            store.set_connection(uid, conn["id"], status="error", status_reason=_safe(exc))
            return {"connection_id": conn["id"], "result": "error"}

        max_accounts = entitlement(user)["max_accounts"]
        others = len([a for a in store.accounts(uid) if a["connection_id"] != conn["id"]])
        seen, states = set(), []
        for acct in accts:
            if others + len(seen) >= max_accounts:
                states.append("limit")
                continue
            row = store.upsert_account(uid, conn["id"], prov.name, acct.id, acct.name, acct.number_mask,
                                       acct.institution, acct.account_type, acct.currency)
            seen.add(row["id"])
            try:
                h = prov.holdings(creds["provider_user_id"], creds["secret"], acct.id)
            except AuthExpired:
                store.set_connection(uid, conn["id"], status="expired",
                                     status_reason="The broker needs you to sign in again.")
                return {"connection_id": conn["id"], "result": "expired"}
            except ProviderOutage:
                store.set_account_state(uid, row["id"], "stale", "The provider did not respond.")
                states.append("stale")
                continue
            except ProviderError as exc:
                store.set_account_state(uid, row["id"], "failed", _safe(exc))
                states.append("failed")
                continue
            state = "partial" if h.problems else ("pending" if not acct.initial_sync_done else "ok")
            note = ("Not returned: {}.".format(", ".join(h.problems)) if h.problems else
                    "The broker is still sending this account's first data." if state == "pending" else None)
            store.save_payload(uid, row["id"], _payload(h, acct), state, note, acct.broker_as_of)
            states.append(state)
        for gone in ([] if only_account else store.accounts(uid, conn["id"])):
            if gone["id"] not in seen:
                store.set_account_state(uid, gone["id"], "missing",
                                        "The broker no longer reports this account through the connection.")
        now = db.utcnow()
        if not accts:
            store.set_connection(uid, conn["id"], status="partial", last_sync_at=now,
                                 status_reason="The broker returned no investment accounts for this "
                                               "connection. If it has just been linked, the first data "
                                               "can take a few minutes.")
            return {"connection_id": conn["id"], "result": "partial", "accounts": 0}
        if states and all(s in ("stale",) for s in states):
            store.set_connection(uid, conn["id"], status="outage",
                                 status_reason="The provider did not respond. Showing the last good data.")
            result = "outage"
        elif any(s in ("partial", "failed", "stale", "limit") for s in states):
            store.set_connection(uid, conn["id"], status="partial", last_sync_at=now,
                                 status_reason="Some data did not arrive in the last sync."
                                 + (" Your plan's account limit was reached." if "limit" in states else ""))
            result = "partial"
        else:
            store.set_connection(uid, conn["id"], status="active", status_reason=None, last_sync_at=now)
            result = "ok"
        _snapshot(uid)
        return {"connection_id": conn["id"], "result": result, "accounts": len(seen)}
    finally:
        lock.release()


def request_refresh(user: Dict[str, Any], conn: Dict[str, Any]) -> Dict[str, Any]:
    """"Sync now". Where the provider refreshes asynchronously (SnapTrade's
    paid refresh), ask for it and let the ACCOUNT_HOLDINGS_UPDATED webhook do
    the pull: reading straight after the request returned yesterday's data
    under a "Synced" message (review M3). A provider with no refresh call
    (the sandbox) is read now."""
    prov = require_available()
    if not hasattr(prov, "refresh_connection"):
        return sync_connection(user, conn, prov=prov)
    creds = _credentials(user["id"])
    if not creds:
        return {"connection_id": conn["id"], "result": "error", "message": "Not linked."}
    prov.refresh_connection(creds["provider_user_id"], creds["secret"], conn["provider_connection_id"])
    store.set_connection(user["id"], conn["id"], last_attempt_at=db.utcnow())
    return {"connection_id": conn["id"], "result": "requested"}


BACKGROUND_PULLS_PER_DAY = 4    # SnapTrade's launch guide: at most 4 background pulls per user a day


def background_pull_allowed(user_id: str) -> bool:
    from ..auth import ratelimit as auth_ratelimit
    state = auth_ratelimit.allowance("brokerage_bg", auth_ratelimit.key_bucket(user_id),
                                     BACKGROUND_PULLS_PER_DAY, 86400)
    if state["left"] <= 0:
        return False
    auth_ratelimit.record("brokerage_bg", auth_ratelimit.key_bucket(user_id))
    return True


def _safe(exc: Exception) -> str:
    """An error message fit for the database and the screen: the exception's
    class and its first line, never a provider response body, which can echo
    request parameters including the user secret."""
    text = str(exc).splitlines()[0][:160] if str(exc) else ""
    return "{}{}".format(type(exc).__name__, ": " + text if text and "secret" not in text.lower() else "")


def _snapshot(user_id: str) -> None:
    try:
        built = portfolio.build(_accounts_with_payloads(user_id))
        store.add_snapshot(user_id, built["summary"])
    except Exception as exc:                                    # noqa: BLE001
        log.warning("brokerage snapshot skipped: %s", type(exc).__name__)


def _accounts_with_payloads(user_id: str) -> List[Dict[str, Any]]:
    key = store.dek(user_id)
    out = []
    for row in store.accounts(user_id):
        item = {k: v for k, v in row.items() if k != "payload"}
        try:
            item["payload"] = store.payload(user_id, row, key) if row["sync_state"] != "missing" else None
        except Exception:                                       # noqa: BLE001
            item["payload"] = None
            item["sync_note"] = "Stored data could not be opened."
        out.append(item)
    return out


# ------------------------------------------------------------ disconnecting


def disconnect(user: Dict[str, Any], connection_id: str) -> Dict[str, Any]:
    """Remove at the provider first, then locally. If the provider call fails
    the local copy is deleted anyway and the provider-side removal is queued:
    the reader asked for their data to go, and Optic's copy is the part Optic
    controls."""
    uid = user["id"]
    conn = store.connection(uid, connection_id)
    if not conn:
        raise LookupError("No such connection.")
    creds = _credentials(uid)
    queued = False
    if creds and conn["provider"] and status()["enabled"]:
        try:
            provider().remove_connection(creds["provider_user_id"], creds["secret"],
                                         conn["provider_connection_id"])
        except NotFoundAtProvider:
            pass
        except ProviderError as exc:
            store.queue_purge(conn["provider"], creds["provider_user_id"], conn["provider_connection_id"],
                              _safe(exc))
            queued = True
    elif creds:
        store.queue_purge(conn["provider"], creds["provider_user_id"], conn["provider_connection_id"],
                          "provider not configured at disconnect")
        queued = True
    store.delete_connection(uid, connection_id)
    remaining = store.connections(uid)
    if not remaining:
        delete_all(user)
    else:
        _snapshot(uid)
    return {"ok": True, "provider_removal_queued": queued, "remaining": len(remaining)}


def delete_all(user_or_id: Any) -> Dict[str, Any]:
    """Every connection, every stored holding, the snapshots, and the data key.
    Also used by account deletion, so it takes a bare id as well."""
    uid = user_or_id["id"] if isinstance(user_or_id, dict) else user_or_id
    row = store.purge_local(uid)
    queued = False
    if row and not row.get("provider_removed_at"):
        try:
            if status()["enabled"] and provider().name == row["provider"]:
                provider().delete_user(row["provider_user_id"])
            else:
                raise ProviderError("provider not configured at deletion")
        except ProviderError as exc:
            store.queue_purge(row["provider"], row["provider_user_id"], None, _safe(exc))
            queued = True
    return {"ok": True, "provider_removal_queued": queued}


def process_purges() -> int:
    if not status()["enabled"]:
        return 0
    prov = provider()
    done = 0
    for p in store.pending_purges():
        if p["provider"] != prov.name:
            continue
        try:
            if p["provider_connection_id"]:
                # Removing one connection needs the user secret, which went
                # with the local purge; deleting the provider user covers it
                # once no other connection of that user is still ours.
                still_ours = db.row("SELECT 1 FROM brokerage_users WHERE provider_user_id = ?",
                                    (p["provider_user_id"],))
                if still_ours:
                    uid = db.row("SELECT user_id FROM brokerage_users WHERE provider_user_id = ?",
                                 (p["provider_user_id"],))["user_id"]
                    creds = _credentials(uid)
                    prov.remove_connection(creds["provider_user_id"], creds["secret"],
                                           p["provider_connection_id"])
                else:
                    prov.delete_user(p["provider_user_id"])
            else:
                prov.delete_user(p["provider_user_id"])
            store.purge_done(p["id"])
            done += 1
        except NotFoundAtProvider:
            store.purge_done(p["id"])               # already gone there: that is the goal
            done += 1
        except ProviderError as exc:
            store.purge_failed(p["id"], _safe(exc))
            if p["attempts"] + 1 >= store.PURGE_MAX_ATTEMPTS:
                log.error("brokerage purge %s gave up after %s attempts; delete it at the provider by hand",
                          p["id"], p["attempts"] + 1)
    return done


# ---------------------------------------------------------------- plan lapse


def on_plan_change(user_id: str) -> None:
    """Called whenever billing changes a plan. Pauses or resumes."""
    user = auth_store.get_user(user_id)
    row = store.link(user_id)
    if not user or not row:
        return
    if entitlement(user)["can_link"]:
        if row.get("paused_at"):
            db.execute("UPDATE brokerage_users SET paused_at = NULL WHERE user_id = ?", (user_id,))
            for c in store.connections(user_id):
                if c["status"] == "paused":
                    store.set_connection(user_id, c["id"], status="active", status_reason=None)
    elif not row.get("paused_at"):
        db.execute("UPDATE brokerage_users SET paused_at = ? WHERE user_id = ?", (db.utcnow(), user_id))
        for c in store.connections(user_id):
            store.set_connection(user_id, c["id"], status="paused",
                                 status_reason="Syncing stopped when the paid plan ended.")


def enforce_lapses(now: Optional[datetime] = None) -> Dict[str, int]:
    now = now or datetime.now(timezone.utc)
    close_before = (now - timedelta(days=LAPSE_CLOSE_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    purge_before = (now - timedelta(days=LAPSE_PURGE_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    closed = purged = 0
    for row in db.rows("SELECT * FROM brokerage_users WHERE paused_at IS NOT NULL"):
        if row["paused_at"] < purge_before:
            delete_all(row["user_id"])
            purged += 1
        elif row["paused_at"] < close_before and not row.get("provider_removed_at"):
            try:
                if status()["enabled"] and provider().name == row["provider"]:
                    provider().delete_user(row["provider_user_id"])
                else:
                    raise ProviderError("provider not configured")
            except ProviderError as exc:
                store.queue_purge(row["provider"], row["provider_user_id"], None, _safe(exc))
            db.execute("UPDATE brokerage_users SET provider_removed_at = ? WHERE user_id = ?",
                       (db.utcnow(), row["user_id"]))
            for c in store.connections(row["user_id"]):
                store.set_connection(row["user_id"], c["id"], status="closed",
                                     status_reason="Closed at the provider when the paid plan ended. "
                                                   "Reconnect to resume.")
            closed += 1
    return {"closed": closed, "purged": purged}


def auto_sync_due(limit: int = 10) -> int:
    """Background pull for entitled readers whose data is older than a day."""
    if not status()["enabled"]:
        return 0
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=AUTO_SYNC_HOURS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    due = db.rows("SELECT c.* FROM brokerage_connections c JOIN brokerage_users u ON u.user_id = c.user_id "
                  "WHERE u.paused_at IS NULL AND c.status IN ('active', 'partial', 'outage') "
                  "AND (c.last_attempt_at IS NULL OR c.last_attempt_at < ?) ORDER BY c.last_attempt_at "
                  "LIMIT ?", (cutoff, limit))
    n = 0
    for conn in due:
        user = auth_store.get_user(conn["user_id"])
        if user and entitlement(user)["can_link"]:
            sync_connection(user, conn)
            n += 1
    return n


# ------------------------------------------------------------------ webhooks


def handle_webhook(event: Dict[str, Any]) -> str:
    """Provider events, already verified. Each one only nudges state Optic
    re-reads from the provider itself; nothing in a webhook body is trusted as
    holdings data."""
    kind = str(event.get("type") or event.get("eventType") or "")
    puid = str(event.get("userId") or event.get("user_id") or "")
    if not puid:
        return "ignored"
    row = db.row("SELECT * FROM brokerage_users WHERE provider_user_id = ?", (puid,))
    if not row:
        return "unknown-user"
    uid = row["user_id"]
    user = auth_store.get_user(uid)
    cid = str(event.get("brokerageAuthorizationId") or event.get("connection_id") or "")
    conn = store.connection_by_provider_id(uid, row["provider"], cid) if cid else None
    if kind in ("CONNECTION_BROKEN", "CONNECTION_FAILED") and conn:
        store.set_connection(uid, conn["id"], status="expired",
                             status_reason="The broker needs you to sign in again.")
        return "expired"
    if kind == "CONNECTION_FIXED" and conn:
        store.set_connection(uid, conn["id"], status="active", status_reason=None)
        return "fixed"
    if kind == "CONNECTION_DELETED" and conn:
        store.delete_connection(uid, conn["id"])
        return "deleted"
    if kind == "USER_DELETED":
        store.purge_local(uid)
        return "user-deleted"
    if kind in ("ACCOUNT_HOLDINGS_UPDATED", "NEW_ACCOUNT_AVAILABLE") and user and conn \
            and entitlement(user)["can_link"]:
        # Fires per account, daily and after every refresh. Pull only the
        # named account, and at most BACKGROUND_PULLS_PER_DAY a day per reader
        # (review M2); the daily job covers anything skipped.
        if not background_pull_allowed(uid):
            return "capped"
        sync_connection(user, conn, only_account=str(event.get("accountId") or "") or None)
        return "synced"
    return "ignored"


# ------------------------------------------------------------------- reading


def overview(user: Dict[str, Any], sector_of: Callable = lambda s: None,
             earnings_of: Callable = lambda s: None, optic_price: Callable = lambda s: None,
             fx_to_usd: Callable = lambda c: None) -> Dict[str, Any]:
    uid = user["id"]
    snaps = store.recent_snapshots(uid, 2)
    previous = snaps[1] if len(snaps) > 1 else None
    built = portfolio.build(_accounts_with_payloads(uid), sector_of=sector_of, earnings_of=earnings_of,
                            optic_price=optic_price, fx_to_usd=fx_to_usd, previous=previous)
    built.pop("summary", None)
    return built


def connections_payload(user: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    accts = store.accounts(user["id"])
    for c in store.connections(user["id"]):
        out.append({
            "id": c["id"], "institution": c["institution"], "status": c["status"],
            "status_reason": c["status_reason"], "last_sync_at": c["last_sync_at"],
            "last_attempt_at": c["last_attempt_at"], "created_at": c["created_at"],
            "accounts": [{"id": a["id"], "name": a["name"], "number_mask": a["number_mask"],
                          "account_type": a["account_type"], "currency": a["currency"],
                          "selected": bool(a["selected"]), "sync_state": a["sync_state"],
                          "sync_note": a["sync_note"], "last_sync_at": a["last_sync_at"],
                          "broker_as_of": a["broker_as_of"]}
                         for a in accts if a["connection_id"] == c["id"]],
        })
    return out


def milo_context(user: Dict[str, Any], **lookups: Callable) -> Optional[Dict[str, Any]]:
    """The signed-in reader's linked portfolio, compact, for Milo. Built on the
    server from the reader's own rows; nothing the browser sends can widen it.
    None when there is nothing linked."""
    if not store.link(user["id"]) or not store.accounts(user["id"]):
        return None
    full = overview(user, **lookups)
    conns = connections_payload(user)
    return {
        "source": "Read-only brokerage data relayed by the aggregator from the reader's broker, "
                  "for accounts the reader selected. Broker-reported, as of each account's last sync.",
        "connections": [{"institution": c["institution"], "status": c["status"],
                         "last_sync_at": c["last_sync_at"]} for c in conns],
        "facts": {
            "accounts": [{k: a.get(k) for k in ("name", "institution", "account_type", "currency",
                                                "sync_state", "broker_as_of", "last_sync_at", "broker_total")}
                         for a in full["accounts"] if a["selected"]],
            "holdings": [{k: h.get(k) for k in ("symbol", "description", "kind", "currency", "quantity",
                                                "price", "accounts")} for h in full["holdings"][:60]],
            "options": [{k: o.get(k) for k in ("underlying", "option_type", "strike", "expiry", "contracts",
                                               "price", "account")} for o in full["options"][:30]],
            "cash": full["cash"],
            "unsupported": full["unsupported"],
        },
        "calculated": {
            "totals": full["totals"],
            "weights": [{"symbol": h.get("symbol"), "weight_pct": h.get("weight_pct"),
                         "market_value": h.get("market_value"), "unrealized_pl": h.get("unrealized_pl"),
                         "sector": h.get("sector")} for h in full["holdings"][:60]],
            "allocation": full["allocation"],
            "concentration": full["concentration"],
            "performance": full["performance"],
            "earnings_ahead": full["earnings_ahead"],
            "changes_since_previous_sync": full["changes"],
            "price_checks": full["price_checks"],
        },
        "caveats": full["notes"],
        "not_supplied": "No transactions, realised gains, dividends, tax lots, greeks or live prices "
                        "come through this connection. broker_as_of is when the broker last reported; "
                        "last_sync_at is when Optic fetched it.",
    }
