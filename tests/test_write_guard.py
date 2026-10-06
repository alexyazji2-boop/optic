"""Reads stay open; writes want a token.

Optic has no sign-in and that is deliberate — every research endpoint should
answer anyone who finds the URL. But "anyone may read this" and "anyone may
rewrite my track record" are separable claims, and on a public deploy they were
bundled: a stranger could open paper positions, re-mark them, or delete the
alert inbox. Not a compromise of the server, but it destroys the one thing a
track record is for.

The unset-token case is the interesting one. Both answers are wrong somewhere —
refusing breaks a local checkout that never had a token, allowing leaves a
forgotten deployment open — so the guard decides by whether a hosting platform
is present in the environment.
"""

import pytest

import app.main as main
from fastapi.testclient import TestClient

client = TestClient(main.app)

# The scans are not here any more. The portfolio scan, its marks and the
# catalyst scan are open to everyone, spaced out for anyone but the owner, and
# tests/test_public_scans.py holds them to that. What is left changes the
# record in ways a reader has no business doing.
WRITES = ("/api/alerts/clear", "/api/feedback/resolve-all")
PLATFORM_VARS = ("RAILWAY_ENVIRONMENT", "RAILWAY_GIT_COMMIT_SHA",
                 "RENDER", "FLY_APP_NAME")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in PLATFORM_VARS:
        monkeypatch.delenv(name, raising=False)
    token = main.WRITE_TOKEN
    yield
    main.WRITE_TOKEN = token


def test_hosted_without_a_token_refuses_writes(monkeypatch):
    """The forgotten-configuration case must fail closed, not open."""
    main.WRITE_TOKEN = ""
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    for path in WRITES:
        assert client.post(path, json={}).status_code == 503, path


def test_local_without_a_token_still_works():
    """A laptop checkout has no token and never needed one."""
    main.WRITE_TOKEN = ""
    assert not main.is_hosted()
    # 503 is the refusal; anything else means the guard let it through.
    assert client.post("/api/alerts/clear", json={}).status_code != 503


def test_a_wrong_token_is_rejected(monkeypatch):
    main.WRITE_TOKEN = "correct-horse"
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    for path in WRITES:
        r = client.post(path, json={}, headers={"X-Optic-Token": "guess"})
        assert r.status_code == 401, path
        assert "write token" in r.json()["detail"]


def test_a_missing_token_is_rejected_when_one_is_configured():
    main.WRITE_TOKEN = "correct-horse"
    assert client.post("/api/alerts/clear", json={}).status_code == 401


def test_the_right_token_is_accepted():
    main.WRITE_TOKEN = "correct-horse"
    r = client.post("/api/alerts/clear", json={},
                    headers={"X-Optic-Token": "correct-horse"})
    assert r.status_code == 200
    assert "removed" in r.json()


def test_reads_are_never_gated():
    """The whole point: gating writes must not gate the research."""
    main.WRITE_TOKEN = "correct-horse"
    for path in ("/api/health", "/api/alerts", "/api/econ", "/api/snapshots", "/"):
        assert client.get(path).status_code == 200, path


def test_marking_alerts_seen_stays_open():
    """Benign and called by the UI on its own; gating it would prompt a reader
    for a token merely for having looked at the inbox."""
    main.WRITE_TOKEN = "correct-horse"
    assert client.post("/api/alerts/seen", json={}).status_code == 200


def test_only_the_owner_changes_the_shared_read_state():
    """One inbox for the deployment: a visitor's empty-bodied call marked every
    alert read for everyone (found in review, 2026-10-06)."""
    from app import alerts as alerts_mod
    main.WRITE_TOKEN = "correct-horse"
    seen = []
    orig = alerts_mod.mark_seen
    alerts_mod.mark_seen = lambda ids=None: seen.append(ids) or 3
    try:
        visitor = client.post("/api/alerts/seen", json={}).json()
        owner = client.post("/api/alerts/seen", json={}, headers={"X-Optic-Token": "correct-horse"}).json()
    finally:
        alerts_mod.mark_seen = orig
    assert visitor == {"marked": 0, "shared": False,
                       "detail": "The inbox's read state is the owner's, so nothing was marked."}
    assert owner["marked"] == 3 and owner["shared"] is True and seen == [None]
