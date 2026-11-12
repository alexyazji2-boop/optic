"""The knowledge level where it is applied: Milo, deep research, the written briefing, and the account (Phase 05).

Directive 05 section 7 asks for all five levels tested against the same factual input, with the same figures,
sources and uncertainty and no personal advice at any of them. What Optic controls is what it sends: these tests
build the same request at each level and compare. Only the level's own block may differ, the advice policy rides on
every one, and a question the policy declines is declined the same way at every level. Whether the real model then
writes five meaningfully different answers needs the real model, which this deployment cannot reach (BLOCKERS BL-01);
the browser runs, with the stand-in model, are in TEST_RESULTS.md, Phase 05.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app import ai, ai_policy, knowledge
from app.auth import config, store

client = TestClient(main.app)
GOOD = "tungsten-carbide-9"
LEVELS = knowledge.ORDER


def snapshot():
    """One company's page, with figures a level must never change."""
    return {"ticker": "NVDA", "quote": {"price": 214.01, "change_pct": -0.64, "market_state": "REGULAR"},
            "valuation": {"pe_trailing": 31.2, "pe_forward": 27.4},
            "focus": {"scope": "auto", "ticker": "NVDA", "view_label": "Overview", "captured_at": datetime(2026, 10, 29, 15, tzinfo=timezone.utc).isoformat()}}


def build(question, level):
    return ai.build_chat_request([{"role": "user", "content": question}], context=snapshot(), mode=level)


def test_five_levels_on_one_question_differ_only_in_the_level_block():
    q = "What does NVDA's P/E of 31.2 say, and how sure can we be?"
    built = {lv: build(q, lv) for lv in LEVELS}
    for lv, (kwargs, meta) in built.items():
        assert meta["level"] == lv
        system = [b["text"] for b in kwargs["system"]]
        assert ai_policy.POLICY_TEXT in system[0], "the advice policy rides on every level"
        assert system[1] == knowledge.prompt_for(lv), "the level's block, with the invariant"
    base_messages = built["intermediate"][0]["messages"]
    base_rest = [b["text"] for b in built["intermediate"][0]["system"]][2:]
    for lv, (kwargs, _meta) in built.items():
        assert kwargs["messages"] == base_messages, "the same question and the same figures at every level"
        assert [b["text"] for b in kwargs["system"]][0] == [b["text"] for b in built["intermediate"][0]["system"]][0]
        assert [b["text"] for b in kwargs["system"]][2:] == base_rest, "the horizon, framework and lens blocks do not move"
        assert kwargs["model"] == built["intermediate"][0]["model"] and kwargs["max_tokens"] == built["intermediate"][0]["max_tokens"]
    sent = json.dumps(base_messages)
    assert "214.01" in sent and "31.2" in sent, "the figures are in what is sent"
    assert len({tuple(b["text"] for b in k["system"])[1] for k, _ in built.values()}) == 5


def test_a_question_the_policy_declines_is_declined_the_same_way_at_every_level():
    lines = set()
    for lv in LEVELS:
        kwargs, meta = build("Should I buy NVDA now?", lv)
        assert meta["policy_kinds"], lv
        lines.add(meta["policy_line"])
        texts = [b["text"] for b in kwargs["system"]] + [m["content"] if isinstance(m["content"], str) else json.dumps(m["content"]) for m in kwargs["messages"]]
        assert any(ai_policy.turn_instruction(meta["policy_kinds"]) in t for t in texts), "the decline instruction goes with it"
    assert len(lines) == 1, "the reader is told the same thing whatever their level"


def test_deep_research_and_the_research_route_take_the_level():
    src = open("app/ai.py", encoding="utf-8").read()
    deep = src[src.index("async def deep_research("):src.index("async def deep_research(") + 6000]
    assert "mode: Optional[str] = None," in deep
    # the house writing rules sit before the policy since Phase 12 (app/editorial.py)
    assert '{"type": "text", "text": RESEARCH_PROMPT + "\\n\\n" + editorial.WRITING_RULES + "\\n\\n" + ai_policy.POLICY_TEXT,' in deep
    assert '{"type": "text", "text": knowledge.prompt_for(mode)},' in deep
    route = open("app/main.py", encoding="utf-8").read()
    assert 'ai.deep_research(ticker, question=question, context=context, mode=mode)' in route


def test_the_written_briefing_is_worded_for_the_level(monkeypatch):
    captured = {}

    class Msg:
        content = [type("B", (), {"type": "text", "text": json.dumps({"headline": "A quiet day.", "what_changed": "x", "drivers": "", "ahead": "", "attention": ""})})()]

    monkeypatch.setattr(ai, "available", lambda: {"enabled": True})
    import anthropic
    monkeypatch.setattr(anthropic, "Anthropic", lambda **kw: object())
    monkeypatch.setattr(ai, "_ask", lambda client, feature, **kw: captured.update(kw) or Msg())
    out = ai.write_portfolio_brief({"today": []}, "beginner")
    assert out["available"] is True and out["level"] == "beginner"
    texts = [b["text"] for b in captured["system"]]
    assert texts[0] == ai.PORTFOLIO_BRIEF_PROMPT and texts[1] == knowledge.prompt_for("beginner")
    assert ai.write_portfolio_brief({"today": []}, "professional")["level"] == "expert", "an old id maps"


def test_the_briefing_is_kept_per_level():
    src = open("app/brokerage/workspace_routes.py", encoding="utf-8").read()
    assert 'return "{}:{}".format(facts_key, knowledge.normalise(level))' in src
    assert "out = await run_in_threadpool(writer, slim, level)" in src
    assert "await run_in_threadpool(store.save_briefing, user[\"id\"], key, out)" in src
    assert "written = await run_in_threadpool(store.briefing, user[\"id\"], _brief_key(out[\"facts_key\"], level))" in src


# --------------------------------------------------------------- the account


@pytest.fixture
def signed_in(accounts):
    client.cookies.clear()
    client.post("/api/auth/register", json={"first_name": "Alex", "last_name": "Reader", "email": "level@example.com",
                                             "password": GOOD, "confirm_password": GOOD})
    return client.cookies.get(config.CSRF_COOKIE)


def test_an_account_has_no_level_until_one_is_chosen(signed_in):
    body = client.get("/api/auth/preferences").json()
    assert body["preferences"]["knowledge_level"] is None, "unset, so the browser's level is sent up rather than replaced"


def test_the_level_round_trips_old_ids_map_and_junk_is_dropped(signed_in):
    patch = lambda v: client.patch("/api/auth/preferences", headers={"X-Optic-CSRF": signed_in}, json={"knowledge_level": v}).json()["preferences"]["knowledge_level"]
    # three levels are written since 2026-11-09 (app/knowledge.py THREE): an old or five-level id is stored as its
    # nearest of the three
    assert patch("beginner") == "beginner"
    assert patch("professional") == "advanced"
    assert patch("not-a-level") == "advanced", "an unknown value is dropped, the stored one kept"
    assert client.get("/api/auth/preferences").json()["preferences"]["knowledge_level"] == "advanced"


def test_the_preferences_carry_their_version_and_a_client_cannot_set_it(signed_in):
    """A browser whose save failed compares this version at its next load (core/store.js); it is read-only."""
    before = client.get("/api/auth/preferences").json()["preferences"]
    after = client.patch("/api/auth/preferences", headers={"X-Optic-CSRF": signed_in},
                         json={"knowledge_level": "new", "updated_at": "1999-01-01T00:00:00Z"}).json()["preferences"]
    assert after["knowledge_level"] == "beginner" and after["updated_at"] and after["updated_at"] != "1999-01-01T00:00:00Z"
    assert after["updated_at"] >= (before.get("updated_at") or "")
    assert client.get("/api/auth/me").json()["preferences"]["updated_at"] == after["updated_at"], "the session's answer carries it too"


def test_the_column_is_added_by_its_own_migration_and_nothing_else_changes():
    from app import db
    versions = [v for v, _name, _s in db.MIGRATIONS]
    assert versions == sorted(versions) and 19 in versions
    # found by its number: later migrations (20, the research library) come after it
    assert dict((v, s) for v, _name, s in db.MIGRATIONS)[19] == ["ALTER TABLE user_preferences ADD COLUMN knowledge_level TEXT"], "additive only"
    assert store.DEFAULT_PREFERENCES["knowledge_level"] is None


def test_the_privacy_policy_names_the_stored_level():
    legal = open("static/v2/js/pages/legalpages.js", encoding="utf-8").read()
    assert "and the level Optic explains things at (from New to Markets to Expert) once you set it while signed in." in legal
