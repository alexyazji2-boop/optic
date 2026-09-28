"""Anyone may read the weekly update; only the operator may force a rewrite.

Since the update started being kept (`app/weekly_store.py`),
`/api/weekly?force=true` is the one way to replace it. A forced write is a
fresh model call of up to 6,000 output tokens and about 56 seconds (measured
2026-09-28), and when it succeeds every reader gets a different piece. It was
open, so any visitor could spend the operator's money and change the week's
headline for everyone, which is the churn that keeping it was meant to stop.

So `force` goes through `_write_guard`, and a plain read does not. Everything
drives the route against a fake model and a per-test store, and checks the two
things a forced write costs: a model call, and the piece kept for every reader.

No platform variable is set except where a test says so. A hosted deployment
marks the session cookie Secure, the test client speaks plain http, and the
owner's cookie would be dropped: the owner tests would pass as guests. With a
token configured the guard never asks whether it is hosted anyway.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import types
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app import ai, weekly_store
from app.auth import admin, config, store

client = TestClient(main.app)

TOKEN = "test-write-token"
GOOD = "tungsten-carbide-9"
OWNER = "owner@example.com"
STRANGER = "stranger@example.com"
PLATFORM = ("RAILWAY_ENVIRONMENT", "RAILWAY_GIT_COMMIT_SHA", "RENDER", "FLY_APP_NAME")
# The two headlines production published for one week, either side of a deploy.
BEFORE = "Durable Goods Go Flat as Friday's Jobs Report Takes the Wheel"
AFTER = "Flat Factory Orders Hand the Week to Friday's Jobs Report"


class _Model:
    """Anthropic's client: records each call and answers with the next headline."""
    calls: list = []
    headlines: list = []

    def __init__(self, **kwargs):
        self.messages = self

    def create(self, **kwargs):
        _Model.calls.append(kwargs)
        text = json.dumps({"headline": _Model.headlines.pop(0),
                           "subhead": "The week hinges on payrolls.",
                           "paragraphs": ["## What happened", "Factory orders were flat."]})
        return types.SimpleNamespace(content=[types.SimpleNamespace(text=text)],
                                     stop_reason="end_turn")


@pytest.fixture(autouse=True)
def deployment(accounts, monkeypatch, tmp_path):
    """A token configured, nobody named the owner, and an empty store."""
    client.cookies.clear()
    for name in PLATFORM:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv(admin.ENV_NAME, raising=False)
    # On `main`, not the environment: main reads it at import, and whatever
    # the developer's .env carries must not decide these.
    monkeypatch.setattr(main, "WRITE_TOKEN", TOKEN)
    _Model.calls, _Model.headlines = [], [BEFORE, AFTER]
    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=_Model))
    monkeypatch.setattr(ai, "available", lambda: {"enabled": True})
    monkeypatch.setattr(weekly_store, "DB_PATH", str(tmp_path / "weekly.db"))
    monkeypatch.setattr(main.weekly_mod, "gather", lambda provider: {"spy": {}})
    return accounts


def _kept():
    """This week's update, written by a guest's plain load as on the live site."""
    got = client.get("/api/weekly")
    assert got.status_code == 200 and got.json()["headline"] == BEFORE
    assert len(_Model.calls) == 1


def _writes():
    with closing(sqlite3.connect(weekly_store.DB_PATH)) as conn:
        return conn.execute("SELECT writes FROM weekly_updates").fetchone()[0]


def _unchanged():
    """No model call past the week's first, and every reader still gets it."""
    assert len(_Model.calls) == 1, "a refused force reached the model"
    assert client.get("/api/weekly").json()["headline"] == BEFORE
    assert _writes() == 1, "a refused force replaced the kept piece"


def _sign_in(email, confirmed):
    """Register, which signs in, confirm the address if asked, and return the
    CSRF value this site's page would send."""
    client.post("/api/auth/register", json={
        "first_name": "A", "last_name": "B", "email": email,
        "password": GOOD, "confirm_password": GOOD})
    if confirmed:
        store.mark_verified(store.get_user_by_email(email)["id"])
    return client.cookies.get(config.CSRF_COOKIE)


def _force(**headers):
    return client.get("/api/weekly", params={"force": "true"}, headers=headers)


# ------------------------------------------------------------------- reading


@pytest.mark.parametrize("params", [{}, {"force": "false"}], ids=["plain", "force-false"])
def test_a_guest_reads_the_week_as_before(params):
    """The week's first load included, because that load is what writes it: a
    gate on writing rather than on `force` would leave the site with no
    update at all."""
    first = client.get("/api/weekly", params=params)
    assert first.status_code == 200
    assert first.json()["available"] is True and first.json()["headline"] == BEFORE
    assert client.get("/api/weekly", params=params).json()["headline"] == BEFORE
    assert len(_Model.calls) == 1


# ------------------------------------------------------------------ refusing


@pytest.mark.parametrize("headers", [{}, {"X-Optic-Token": "guess"}], ids=["none", "wrong"])
def test_a_guest_cannot_force_a_rewrite(headers):
    _kept()
    refused = client.get("/api/weekly", params={"force": "true"}, headers=headers)
    assert refused.status_code == 401
    assert "write token" in refused.json()["detail"]
    _unchanged()


@pytest.mark.parametrize("email,confirmed", [(STRANGER, True), (OWNER, False)],
                         ids=["stranger", "unconfirmed-owner"])
def test_an_account_that_is_not_the_owner_cannot_force(monkeypatch, email, confirmed):
    """Being signed in is not being the owner, and neither is typing the
    owner's address into the signup form without confirming it."""
    monkeypatch.setenv(admin.ENV_NAME, OWNER)
    _kept()
    csrf = _sign_in(email, confirmed)
    assert _force(**{"X-Optic-CSRF": csrf}).status_code == 401
    _unchanged()


def test_a_link_cannot_make_the_owner_force_a_rewrite(monkeypatch):
    """SameSite=Lax sends the session cookie with a link followed from another
    site, because that is a top-level GET. On this route the CSRF header is the
    only thing between such a link and a rewrite on the owner's session. The
    owner typing the URL is refused the same way, and told the token works."""
    monkeypatch.setenv(admin.ENV_NAME, OWNER)
    _kept()
    _sign_in(OWNER, True)
    refused = _force()
    assert refused.status_code == 403
    assert "write token" in refused.json()["detail"]
    _unchanged()


def test_a_deployment_with_no_token_refuses_force(monkeypatch):
    """The forgotten-configuration case fails closed, as the writes do."""
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    monkeypatch.setattr(main, "WRITE_TOKEN", "")
    _kept()
    refused = _force()
    assert refused.status_code == 503
    assert "OPTIC_WRITE_TOKEN" in refused.json()["detail"]
    _unchanged()


@pytest.mark.parametrize("case,status", [("guest", 401), ("link", 403), ("no-token", 503)])
def test_a_refusal_is_about_the_rewrite_not_the_ledger(monkeypatch, case, status):
    """`_write_guard` words every refusal about changing the record, because
    every caller it turned away before this one was. Somebody who asked for a
    rewrite and is told the ledger is closed goes looking for a write they
    never made. Same status as the guard's, this route's sentence."""
    if case == "link":
        monkeypatch.setenv(admin.ENV_NAME, OWNER)
        _sign_in(OWNER, True)
    if case == "no-token":
        monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
        monkeypatch.setattr(main, "WRITE_TOKEN", "")
    refused = _force()
    assert refused.status_code == status
    detail = refused.json()["detail"]
    assert "force" in detail
    assert "ledger" not in detail and "record" not in detail
    assert "—" not in detail and "–" not in detail


# ------------------------------------------------------------------ allowing


def test_the_write_token_forces_a_rewrite_for_every_reader():
    _kept()
    forced = _force(**{"X-Optic-Token": TOKEN})
    assert forced.status_code == 200 and forced.json()["headline"] == AFTER
    assert client.get("/api/weekly").json()["headline"] == AFTER
    assert len(_Model.calls) == 2 and _writes() == 2


def test_the_confirmed_owner_forces_with_the_pages_csrf_header(monkeypatch):
    monkeypatch.setenv(admin.ENV_NAME, OWNER)
    _kept()
    csrf = _sign_in(OWNER, True)
    forced = _force(**{"X-Optic-CSRF": csrf})
    assert forced.status_code == 200 and forced.json()["headline"] == AFTER
    assert len(_Model.calls) == 2


def test_a_laptop_with_no_token_can_still_force(monkeypatch):
    """Local and unconfigured is the guard's standing allowance, and it is how
    a change to the prompt gets tried before it ships."""
    monkeypatch.setattr(main, "WRITE_TOKEN", "")
    assert not main.is_hosted()
    _kept()
    forced = _force()
    assert forced.status_code == 200 and forced.json()["headline"] == AFTER
