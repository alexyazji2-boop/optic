"""`cached=1` on the Read's three model-written pieces serves only what is
already kept and never calls a model, so the rebuilt frontend can open the
Read without spending. Without the flag, behaviour is unchanged."""
import app.ai as ai
import app.brief as brief_mod
from app import main


def _no_model(*a, **k):  # pragma: no cover - failing is the point
    raise AssertionError("a model write was attempted")


def test_brief_cached_never_builds(monkeypatch, tmp_path):
    monkeypatch.setattr(brief_mod, "build", _no_model)
    monkeypatch.setattr(brief_mod, "_rebuild_behind", _no_model)
    monkeypatch.setattr(brief_mod, "_load", lambda day: None)
    monkeypatch.setattr(brief_mod, "_previous_read", lambda day: None)
    monkeypatch.setattr(brief_mod, "_MEM", {})
    out = brief_mod.state(None, None, False, cached_only=True)
    assert out["missing"] is True and "not been built" in out["reason"]


def test_brief_cached_serves_what_is_built(monkeypatch):
    monkeypatch.setattr(brief_mod, "build", _no_model)
    monkeypatch.setattr(brief_mod, "_rebuild_behind", _no_model)
    monkeypatch.setattr(brief_mod, "_MEM", {})
    monkeypatch.setattr(brief_mod, "_load", lambda day: {"day": day, "built_at": "2020-01-01T00:00:00+00:00", "summary": {"headline": "kept"}})
    out = brief_mod.state(None, None, False, cached_only=True)
    assert out["summary"]["headline"] == "kept" and out["stale"] is True and out["refreshing"] is False


def test_catalyst_mode_cached_never_writes(monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setattr(main.catalyst_live_mod, "build", lambda yf: {"available": True, "release": {"title": "CPI", "url": "u"}})
    monkeypatch.setattr(ai, "write_catalyst_read", _no_model)
    monkeypatch.setattr(ai, "kept_catalyst_read", lambda key: None)
    r = TestClient(main.app).get("/api/catalyst-mode?cached=true").json()
    assert r["read"] == {"available": False, "on_request": True}


def test_weekly_cached_never_writes(monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setattr(ai, "write_weekly_update", _no_model)
    monkeypatch.setattr(main.weekly_mod, "gather", _no_model)
    monkeypatch.setattr(main.weekly_store, "load", lambda key: None)
    monkeypatch.setattr(main.live_mirror, "active", lambda: False)
    r = TestClient(main.app).get("/api/weekly?cached=true").json()
    assert r["available"] is False and r["not_written"] is True
    monkeypatch.setattr(main.weekly_store, "load", lambda key: {"headline": "Kept week", "paragraphs": ["x"]})
    r = TestClient(main.app).get("/api/weekly?cached=true").json()
    assert r["available"] is True and r["headline"] == "Kept week"
