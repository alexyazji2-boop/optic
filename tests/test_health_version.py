"""/api/health has to answer "what is actually running".

There was no way to tell a deploy that landed from one that never fired. The
obvious proxy — the ?v= asset stamp — cannot answer it: that value derives from
the mtimes of the files in static/, so a commit touching only Python or docs
leaves it identical, and an unchanged stamp looks the same as a dead webhook.
I watched a real deploy against that stamp for ten minutes, learned nothing,
and this endpoint is the fix.
"""

from fastapi.testclient import TestClient

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


def test_health_exposes_commit_and_uptime():
    body = client.get("/api/health").json()
    assert body["commit"] == deployed_commit()
    assert body["uptime_seconds"] >= 0
    assert body["booted_at"].endswith("+00:00")
