"""Milo and the research framework: the mode block, the compact CONTEXT copy,
the screenshot rule and the server-side hook. No model calls."""

from __future__ import annotations

import asyncio
import base64
import json

import pytest

from app import ai
from app import main as m
from app.research import milo, modes


def _texts(kwargs):
    return [b["text"] for b in kwargs["system"]]


def _routing(mode, depth="full"):
    return {"mode": mode, "source": "question", "depth": depth, "why": "test"}


def test_the_mode_block_rides_only_with_a_framework_assessment():
    hist = [{"role": "user", "content": "Is there a swing setup on NVDA?"}]
    kw, meta = ai.build_chat_request(hist, context={"ticker": "NVDA", "framework": {
        "routing": _routing("swing"), "swing": {"grade": "B"}}})
    blocks = "\n".join(_texts(kw))
    assert "## The research framework" in blocks and "Swing mode." in blocks
    assert "Before any grade, give the strongest specific reasons to skip" in blocks
    assert meta["framework_mode"] == "swing"
    kw, meta = ai.build_chat_request(hist, context={"ticker": "NVDA"})
    assert "## The research framework" not in "\n".join(_texts(kw)) and meta["framework_mode"] is None


@pytest.mark.parametrize("mode,phrase", [
    ("long_term", "Quality comes before any talk of buying"),
    ("pre_earnings", "My best-supported pre-earnings view is"),
    ("post_earnings", "never rewrite the earlier reasoning"),
    ("combined", "where they agree or disagree"),
])
def test_each_mode_has_its_own_block(mode, phrase):
    text = milo.prompt(_routing(mode), True)
    assert phrase in text
    # Only the block for this mode is sent.
    others = [m_ for m_ in milo.MODES if m_ not in (mode, "unclear")]
    for o in others:
        assert milo.MODES[o] not in text


def test_a_quick_question_is_told_to_stay_short():
    assert "not as a report" in milo.prompt(_routing("swing", "quick"), True)
    assert "not as a report" not in milo.prompt(_routing("swing", "full"), True)


def test_unclear_asks_or_reads_both():
    text = milo.prompt({"mode": "unclear"}, False)
    assert "two-line read for each" in text


def _png():
    return base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 64).decode()


def test_screenshot_only_inputs_are_read_as_approximate():
    hist = [{"role": "user", "content": "What do you make of this chart?"}]
    kw, _ = ai.build_chat_request(hist, context={}, attachments=[
        {"name": "c.png", "media_type": "image/png", "data": _png()}])
    blocks = "\n".join(_texts(kw))
    assert "## A screenshot is the evidence" in blocks and "approximate" in blocks
    kw, _ = ai.build_chat_request(hist, context={"quote": {"price": 1}}, attachments=[
        {"name": "c.png", "media_type": "image/png", "data": _png()}])
    blocks = "\n".join(_texts(kw))
    assert "## A screenshot is the evidence" not in blocks and "Prefer CONTEXT's figures" in blocks


def test_the_prompt_keeps_judgments_apart_and_drops_forced_slang():
    assert "Five judgments, kept apart" in ai.SYSTEM_PROMPT
    assert "No conclusion is bullish by default" in " ".join(ai.SYSTEM_PROMPT.split())
    assert "clownish" not in ai.SYSTEM_PROMPT
    for block in list(milo.MODES.values()) + [milo.COMMON, milo.SCREENSHOT_ONLY]:
        assert "—" not in block                         # house style: no em dashes


def test_framework_is_in_the_source_list_and_fits_the_budget():
    assert "framework" in " ".join(ai.FORMAT_PROMPT.split())
    assert ai._ORDER_BASE.index("framework") < ai._ORDER_BASE.index("quote")
    big = {"routing": _routing("long_term"), "long_term": {"x": "y" * 30000}}
    body, meta = ai.budget_context({"framework": big, "quote": {"price": 1}}, "is it a good investment", "long")
    assert "framework" in meta["kept"] and "framework" in meta["slimmed"]


def _fake_out():
    return {"ticker": "NVDA", "generated_at": "2026-10-14T17:00:00+00:00", "method_version": "research-1.0",
            "policy": {"version": "p"}, "freshness": {"state": "delayed", "text": "t", "phase": "regular"},
            "swing": {"grade": "B", "why": "w", "rules": [], "objections": [{"severity": 2, "text": "o", "kind": "rr"}],
                      "readings": {"rsi14": 52}, "plan": {"entry": 1, "invalidation": {"price": 0.9}}},
            "data": {"gaps": []}, "limitations": ["l"]}


@pytest.mark.framework_live
def test_the_chat_hook_adds_the_assessment(monkeypatch):
    calls = {}

    def fake_build(provider, yf, ticker, mode, **kw):
        calls.update(ticker=ticker, mode=mode, vol_event=kw.get("vol_event"))
        return _fake_out()

    monkeypatch.setattr(m.research_service, "build", fake_build)
    monkeypatch.setattr(m, "_rate", lambda: 0.04)
    hist = [{"role": "user", "content": "Is there a swing setup here?"}]
    ctx = {"ticker": "NVDA", "focus": {"ticker": "NVDA"}, "vol_surface": {"event": {"available": True, "move_pct": 4}}}
    out = asyncio.run(m._with_framework(hist, ctx))
    assert calls == {"ticker": "NVDA", "mode": "swing", "vol_event": {"available": True, "move_pct": 4}}
    fw = out["framework"]
    assert fw["routing"]["mode"] == "swing" and fw["swing"]["grade"] == "B"
    assert json.dumps(fw)                                   # serialisable for CONTEXT


@pytest.mark.framework_live
def test_the_chat_hook_never_blocks_the_answer(monkeypatch):
    def slow(*a, **k):
        raise TimeoutError("slow")

    monkeypatch.setattr(m.research_service, "build", slow)
    monkeypatch.setattr(m, "_rate", lambda: 0.04)
    out = asyncio.run(m._with_framework([{"role": "user", "content": "long-term view on NVDA?"}],
                                        {"ticker": "NVDA", "focus": {"ticker": "NVDA"}}))
    assert out["framework"]["available"] is False and "did not finish" in out["framework"]["reason"]


@pytest.mark.framework_live
def test_no_company_no_framework(monkeypatch):
    monkeypatch.setattr(m.research_service, "build", lambda *a, **k: pytest.fail("should not build"))
    out = asyncio.run(m._with_framework([{"role": "user", "content": "what is a moat?"}], {}))
    assert "framework" not in (out or {})


@pytest.mark.framework_live
def test_unclear_questions_are_routed_without_a_build(monkeypatch):
    monkeypatch.setattr(m.research_service, "build", lambda *a, **k: pytest.fail("should not build"))
    out = asyncio.run(m._with_framework([{"role": "user", "content": "should I buy it?"}],
                                        {"ticker": "NVDA", "focus": {"ticker": "NVDA"}}))
    assert out["framework"] == {"routing": out["framework"]["routing"]}
    assert out["framework"]["routing"]["mode"] == "unclear"


def test_framework_routes_are_open_and_validate(monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setattr(m.research_service, "build", lambda *a, **k: {"available": True, "ticker": a[2], "mode": a[3]})
    monkeypatch.setattr(m, "_rate", lambda: 0.04)
    c = TestClient(m.app)
    r = c.get("/api/framework/NVDA?mode=swing")
    assert r.status_code == 200 and r.json()["mode"] == "swing"
    assert c.get("/api/framework/NVDA?mode=bogus").status_code == 400
    pol = c.get("/api/framework-policy").json()
    assert {r_["rule"] for r_ in pol["rules"]} >= {"rr_s_min", "quality_cap_grade", "atr_stop_multiple"}
    q = c.get("/api/framework-quality").json()
    assert q["by_prediction"]["results"]["status"] == "collecting"
    assert c.get("/api/framework/NVDA/forecasts").json()["forecasts"] == []


@pytest.mark.framework_live
def test_the_chat_route_runs_research_and_framework_side_by_side(monkeypatch):
    import time
    from fastapi.testclient import TestClient

    async def slow_research(history, context, horizon=None):
        await asyncio.sleep(0.6)
        return dict(context or {}, research={"items": [1]})

    async def slow_framework(history, context, horizon=None, attachments=None):
        await asyncio.sleep(0.6)
        return dict(context or {}, framework={"routing": {"mode": "swing"}})

    seen = {}

    async def fake_stream(history, context=None, **kw):
        seen.update(context or {})
        yield "data: {}\n\n"

    monkeypatch.setattr(m, "_with_research", slow_research)
    monkeypatch.setattr(m, "_with_framework", slow_framework)
    monkeypatch.setattr(m.ai, "stream_chat", fake_stream)
    monkeypatch.setattr(m, "_spend_guard", lambda request: None)
    t0 = time.time()
    r = TestClient(m.app).post("/api/chat", json={"messages": [{"role": "user", "content": "setup?"}],
                                                  "context": {"ticker": "NVDA"}})
    assert r.status_code == 200
    assert time.time() - t0 < 1.1                     # not 1.2s in sequence
    assert seen["research"] == {"items": [1]} and seen["framework"]["routing"]["mode"] == "swing"


def test_the_swing_readings_never_pose_as_todays_price():
    out = _fake_out()
    out["swing"]["readings"] = {"spot": 228.52, "as_of": "2026-10-13", "rsi14": 52}
    c = milo.compact(out, _routing("swing"))
    rd = c["swing"]["readings"]
    assert "spot" not in rd and rd["last_completed_close"] == 228.52
    assert "today's price is in quote" in rd["basis"]
    assert "today's price and move are in `quote`" in milo.COMMON
