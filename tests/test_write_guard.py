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

WRITES = ("/api/tracker/scan", "/api/tracker/mark", "/api/alerts/clear",
          "/api/catalysts/refresh")
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
