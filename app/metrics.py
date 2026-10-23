"""The owner's Metrics page: sign-ups, active accounts, retention, Milo questions and plans.

Asked for on 2026-10-23 as "an owner-only metrics page from Optic's own database ... no
third-party analytics". Everything here is counted from tables Optic already keeps, plus
two small ones that migration 18 adds because the existing ones cannot answer the
question:

* **Which days an account used Optic** (`activity_days`). A session row keeps only its
  latest use and is deleted at sign-out, so a week in which someone was active is lost
  as soon as they come back. A row per account per UTC day is written on each page load
  (`/api/auth/me`) and each sign-in. Weekly actives are counted from it, and only for
  weeks it covers.
* **One row per question to Milo** (`milo_questions`). The usage ledger records model
  calls, and one chat question can take several (the tool loop), so calls are not
  questions. A row is written when a question passes the allowance, whoever asks.

Nothing records pages viewed, what was asked, or anything about a visitor beyond the
account id. The owner's own accounts (ADMIN_EMAILS) are left out of every count and
reported as left out, so the owner's testing does not read as customers.

Weeks start on Monday, in UTC, as the stored timestamps are.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from . import ai_store, db
from .auth import admin as auth_admin
from .auth import store as auth_store

log = logging.getLogger("optic.metrics")

WEEKS = 12
RETENTION_DAYS = 28
KINDS = {"chat": "Milo chat", "research": "Deep research", "scan": "Scan requests",
         "portfolio": "Portfolio briefings (Brokerage)"}


# ------------------------------------------------------------------ recording

def note_active(user_id: Optional[str], now: Optional[datetime] = None) -> None:
    """This account used Optic today. Never raises: a page load is not worth failing over it."""
    if not user_id:
        return
    day = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).date().isoformat()
    try:
        db.execute("INSERT OR IGNORE INTO activity_days (user_id, day) VALUES (?, ?)", (user_id, day))
    except Exception as exc:                                     # noqa: BLE001
        log.warning("activity day not recorded: %s", exc)


def note_question(user_id: Optional[str], kind: str) -> None:
    """One question to Milo passed the allowance. Guests are recorded without an id."""
    try:
        db.execute("INSERT INTO milo_questions (at, user_id, kind) VALUES (?, ?, ?)",
                   (db.utcnow(), user_id or None, kind))
    except Exception as exc:                                     # noqa: BLE001
        log.warning("Milo question not recorded: %s", exc)


# ------------------------------------------------------------------ reading

def _ts(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _tracking_since() -> Optional[date]:
    """The day migration 18 was applied: the first day activity and questions were recorded."""
    found = db.row("SELECT applied_at FROM schema_migrations WHERE version = 18")
    at = _ts((found or {}).get("applied_at"))
    return at.date() if at else None


def overview(now: Optional[datetime] = None) -> Dict[str, Any]:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    today = now.date()
    owners = auth_admin.emails()
    users = db.rows(
        "SELECT u.id, u.email, u.email_verified, u.is_active, u.created_at, u.last_login_at, "
        "(SELECT MAX(s.last_used_at) FROM sessions s WHERE s.user_id = u.id) AS session_used_at "
        "FROM users u")
    owner_ids = {u["id"] for u in users if (u["email"] or "").lower() in owners}
    people = [u for u in users if u["id"] not in owner_ids]
    ids = {u["id"] for u in people}

    days: Dict[str, List[date]] = {}
    for r in db.rows("SELECT user_id, day FROM activity_days"):
        if r["user_id"] in ids:
            days.setdefault(r["user_id"], []).append(date.fromisoformat(r["day"]))
    since = _tracking_since()

    def last_active(u: Dict[str, Any]) -> Optional[datetime]:
        known = [t for t in (_ts(u["last_login_at"]), _ts(u["session_used_at"])) if t]
        known += [datetime(d.year, d.month, d.day, tzinfo=timezone.utc) for d in days.get(u["id"], [])]
        return max(known) if known else None

    seen = {u["id"]: last_active(u) for u in people}
    created = {u["id"]: _ts(u["created_at"]) for u in people}

    # ---- weeks: sign-ups and weekly actives
    this_week = _monday(today)
    weeks = []
    for i in range(WEEKS - 1, -1, -1):
        start = this_week - timedelta(weeks=i)
        end = start + timedelta(days=6)
        joined = [u for u in people if created[u["id"]] and start <= created[u["id"]].date() <= end]
        covered = since is not None and end >= since
        active = (sum(1 for uid, ds in days.items() if any(start <= d <= end for d in ds))
                  if covered else None)
        weeks.append({"week_start": start.isoformat(), "partial": end >= today,
                      "signups": len(joined), "verified": sum(1 for u in joined if u["email_verified"]),
                      "active_accounts": active,
                      "active_from": since.isoformat() if covered and since > start else None})

    def active_within(n: int) -> int:
        cut = now - timedelta(days=n)
        return sum(1 for t in seen.values() if t and t >= cut)

    # ---- 4-week retention by sign-up week
    cohorts = []
    for w in weeks:
        start = date.fromisoformat(w["week_start"])
        members = [uid for uid, c in created.items() if c and start <= c.date() <= start + timedelta(days=6)]
        due = [uid for uid in members if created[uid] + timedelta(days=RETENTION_DAYS) <= now]
        kept = [uid for uid in due if seen[uid] and seen[uid] >= created[uid] + timedelta(days=RETENTION_DAYS)]
        cohorts.append({"week_start": w["week_start"], "signups": len(members), "measurable": len(due),
                        "retained": len(kept),
                        "retained_pct": round(len(kept) / len(due) * 100.0, 1) if due else None})

    # ---- Milo questions, by what was asked through
    rows = db.rows("SELECT at, user_id, kind FROM milo_questions")
    week_cut, month_cut = now - timedelta(days=7), now - timedelta(days=30)
    by_kind: Dict[str, Dict[str, Any]] = {}
    owner_questions, guests_7d, askers_7d = 0, 0, set()
    for r in rows:
        at = _ts(r["at"])
        if r["user_id"] in owner_ids:
            owner_questions += 1
            continue
        k = by_kind.setdefault(r["kind"], {"kind": r["kind"], "label": KINDS.get(r["kind"], r["kind"]),
                                           "last_7_days": 0, "last_30_days": 0, "all": 0})
        k["all"] += 1
        if at and at >= month_cut:
            k["last_30_days"] += 1
        if at and at >= week_cut:
            k["last_7_days"] += 1
            if r["user_id"]:
                askers_7d.add(r["user_id"])
            else:
                guests_7d += 1
    questions = sorted(by_kind.values(), key=lambda k: list(KINDS).index(k["kind"]) if k["kind"] in KINDS else 99)

    # ---- plans, as the entitlement code reads them
    plans: Dict[str, Dict[str, Any]] = {}
    for u in people:
        sub = auth_store.subscription(u["id"])
        p = plans.setdefault(sub["plan"], {"plan": sub["plan"], "label": sub["label"], "accounts": 0})
        p["accounts"] += 1

    return {
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tracking_since": since.isoformat() if since else None,
        "owners_left_out": len(owner_ids),
        "accounts": {"total": len(people), "verified": sum(1 for u in people if u["email_verified"]),
                     "deactivated": sum(1 for u in people if not u["is_active"]),
                     "active_7_days": active_within(7), "active_30_days": active_within(30)},
        "weeks": weeks,
        "retention": {"days": RETENTION_DAYS, "cohorts": cohorts},
        "questions": {"by_kind": questions, "askers_7_days": len(askers_7d), "guest_questions_7_days": guests_7d,
                      "owner_questions_left_out": owner_questions},
        "model_calls": ai_store.calls_by_feature(now.timestamp()),
        "plans": sorted(plans.values(), key=lambda p: -p["accounts"]),
    }
