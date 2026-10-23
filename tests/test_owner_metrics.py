"""The owner's Metrics page: sign-ups, active accounts, retention, Milo questions and plans.

Asked for on 2026-10-23: "an owner-only metrics page from Optic's own database ... No
third-party analytics." Counted from Optic's tables (app/metrics.py); the owner's own
accounts are left out of every count; counts only, no addresses.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app import metrics
from app.auth import admin, config
from app.auth import store as auth_store

ROOT = Path(__file__).resolve().parent.parent
GOOD = "tungsten-carbide-9"
OWNER = "owner@example.com"


def _signup(http, email, first="Ada"):
    reply = http.post("/api/auth/register", json={
        "first_name": first, "last_name": "Reader", "email": email,
        "password": GOOD, "confirm_password": GOOD})
    assert reply.status_code == 200, reply.text


def _get(http):
    return http.get("/api/admin/metrics", headers={"X-Optic-CSRF": http.cookies.get(config.CSRF_COOKIE) or ""})


def _iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture
def owner(accounts, monkeypatch):
    monkeypatch.setenv(admin.ENV_NAME, OWNER)
    http = TestClient(main.app)
    _signup(http, OWNER, "Owner")
    accounts.execute("UPDATE users SET email_verified = 1 WHERE email = ?", (OWNER,))
    reader = TestClient(main.app)
    _signup(reader, "reader@example.com")
    return http, reader


def test_only_the_signed_in_owner_with_the_csrf_header_reads_it(owner):
    http, reader = owner
    assert _get(reader).status_code == 403
    assert _get(TestClient(main.app)).status_code == 401
    assert http.get("/api/admin/metrics").status_code == 403, "a cookie alone is not enough"
    reply = _get(http)
    assert reply.status_code == 200 and reply.headers["cache-control"] == "no-store"
    raw = json.dumps(reply.json())
    assert "@example.com" not in raw and "user_id" not in raw, "counts only"


def test_counts_leave_the_owner_out_and_retention_needs_a_return_after_28_days(owner, accounts):
    http, _ = owner
    now = datetime.now(timezone.utc).replace(microsecond=0)
    for email in ("kept@example.com", "gone@example.com", "new@example.com"):
        _signup(TestClient(main.app), email)
    ids = {r["email"]: r["id"] for r in accounts.rows("SELECT id, email FROM users")}
    old = _iso(now - timedelta(days=40))
    for email in ("kept@example.com", "gone@example.com"):
        accounts.execute("UPDATE users SET created_at = ?, last_login_at = ? WHERE email = ?", (old, old, email))
        accounts.execute("DELETE FROM sessions WHERE user_id = ?", (ids[email],))
        accounts.execute("DELETE FROM activity_days WHERE user_id = ?", (ids[email],))   # signing up recorded today
    # kept came back 30 days after signing up; gone never did
    metrics.note_active(ids["kept@example.com"], now - timedelta(days=10))
    metrics.note_active(ids["new@example.com"], now)
    metrics.note_active(ids[OWNER], now)
    for kind, who in (("chat", "kept@example.com"), ("chat", "new@example.com"), ("research", "new@example.com"),
                      ("chat", OWNER), ("chat", None)):
        metrics.note_question(ids.get(who), kind)
    auth_store.set_plan(ids["kept@example.com"], "pro")

    body = metrics.overview(now)
    assert body["owners_left_out"] == 1
    assert body["accounts"]["total"] == 4, "reader, kept, gone and new; not the owner"
    assert body["accounts"]["active_7_days"] == 2, "reader and new used it this week; kept 10 days ago"
    cohort = next(c for c in body["retention"]["cohorts"] if c["measurable"])
    assert (cohort["signups"], cohort["measurable"], cohort["retained"], cohort["retained_pct"]) == (2, 2, 1, 50.0)
    young = body["retention"]["cohorts"][-1]
    assert young["signups"] >= 2 and young["measurable"] == 0 and young["retained_pct"] is None
    q = {k["kind"]: k for k in body["questions"]["by_kind"]}
    assert q["chat"]["last_7_days"] == 3 and q["research"]["last_7_days"] == 1, "the guest's counts, the owner's not"
    assert body["questions"]["owner_questions_left_out"] == 1
    assert body["questions"]["askers_7_days"] == 2 and body["questions"]["guest_questions_7_days"] == 1
    assert {p["plan"]: p["accounts"] for p in body["plans"]} == {"free": 3, "pro": 1}
    this_week = body["weeks"][-1]
    assert this_week["partial"] and this_week["active_accounts"] == 2, "reader (signed up today) and new; not the owner"
    before = [w for w in body["weeks"] if w["week_start"] < body["tracking_since"][:10] and not w["active_from"]]
    assert all(w["active_accounts"] is None for w in before), "no weekly actives for weeks before recording began"


def test_a_page_load_records_the_day_and_every_milo_entry_counts_its_question(owner, accounts):
    _, reader = owner
    assert reader.get("/api/auth/me").status_code == 200
    uid = accounts.row("SELECT id FROM users WHERE email = 'reader@example.com'")["id"]
    assert accounts.row("SELECT COUNT(*) AS n FROM activity_days WHERE user_id = ?", (uid,))["n"] == 1
    reader.get("/api/auth/me")
    assert accounts.row("SELECT COUNT(*) AS n FROM activity_days WHERE user_id = ?", (uid,))["n"] == 1, "once a day"
    src = (ROOT / "app/main.py").read_text()
    for kind in ("chat", "research", "scan", "portfolio"):
        assert '_count_question(request, "{}")'.format(kind) in src, kind


def test_recording_never_breaks_the_request(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("disk")
    monkeypatch.setattr(metrics.db, "execute", boom)
    metrics.note_active("someone")
    metrics.note_question(None, "chat")


def test_the_page_sits_with_the_owners_reports_in_v2():
    js = ROOT / "static/v2/js"
    nav, palette = (js / "nav.js").read_text(), (js / "ui/palette.js").read_text()
    reports, app_js = (js / "pages/reports.js").read_text(), (js / "app.js").read_text()
    group = nav[nav.index("{ id: 'reports'"):]
    assert "{ view: 'metrics', label: 'Metrics', slug: 'metrics', v2: true }" in group[:group.index("] }")]
    assert "{ view: 'metrics', label: 'Metrics', owner: true," in palette
    assert "metrics: P.reports" in app_js and "api.get('/api/admin/metrics'" in reports
