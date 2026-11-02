"""/api/health has to answer "what is actually running".

There was no way to tell a deploy that landed from one that never fired. The
obvious proxy — the ?v= asset stamp — cannot answer it: that value derives from
the mtimes of the files in static/, so a commit touching only Python or docs
leaves it identical, and an unchanged stamp looks the same as a dead webhook.
I watched a real deploy against that stamp for ten minutes, learned nothing,
and this endpoint is the fix.
"""

from fastapi.testclient import TestClient

import os

from app.main import app, deployed_commit

client = TestClient(app)

PLATFORM_VARS = ("RAILWAY_GIT_COMMIT_SHA", "SOURCE_VERSION", "FLY_MACHINE_VERSION")


def _clear(monkeypatch):
    for name in PLATFORM_VARS:
        monkeypatch.delenv(name, raising=False)


def test_reports_the_platform_commit(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "facfcda1234567890abcdef")
    assert deployed_commit() == "facfcda12345"


def test_falls_back_to_dev_when_unset(monkeypatch):
    """A local run should say so rather than invent a version."""
    _clear(monkeypatch)
    assert deployed_commit() == "dev"


def test_each_platform_var_is_recognised(monkeypatch):
    for name in PLATFORM_VARS:
        _clear(monkeypatch)
        monkeypatch.setenv(name, "abc123def456789")
        assert deployed_commit() == "abc123def456", name


def test_health_exposes_commit_and_uptime(monkeypatch):
    """To everyone, the operator included: the commit of a public repository says
    whether a published fix has reached production yet."""
    from app import main as main_mod
    monkeypatch.setattr(main_mod.auth_deps, "is_admin", lambda request: True)
    body = client.get("/api/health").json()
    assert body["commit"] == deployed_commit()
    assert body["uptime_seconds"] >= 0
    assert body["booted_at"].endswith("+00:00")


def test_a_visitor_gets_the_public_fields_only():
    body = client.get("/api/health").json()
    assert set(body) == {"status", "provider", "realtime_chain", "server_time", "assistant", "commit", "booted_at",
                         "uptime_seconds"}, body
    assert set(body["assistant"]) <= {"enabled", "hint"}, body["assistant"]


def test_publish_sh_reads_the_commit_without_signing_in():
    """BUG-181 (Phase 11): publish.sh curls /api/health with no session and reads `commit` with sed; Phase 10 had
    made it the operator's, so every publish waited ten minutes and reported a failed deploy."""
    import re
    raw = client.get("/api/health").text
    script = open(os.path.join(os.path.dirname(__file__), "..", "publish.sh")).read()
    assert 's/.*"commit":"\\([^"]*\\)".*/\\1/p' in script
    m = re.search(r'"commit":"([^"]*)"', raw)
    assert m and m.group(1) == deployed_commit()
