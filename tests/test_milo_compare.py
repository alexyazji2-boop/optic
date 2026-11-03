"""The model comparison harness (tests/milo_eval/compare.py, providers.py), offline (Phase 13, 2026-11-02).

No provider is called: each adapter runs against a recorded reply shape through httpx's mock transport (or a fake SDK
client), on the benchmark's fixtures, so what is tested is the translation in both directions, the one tool loop
every model shares, the recording of each field, and the refusals. A model asking for a tool the answer was not
offered is recorded as Severity 0 and the tool is not run.
"""
from __future__ import annotations

import asyncio
import json
import types

import httpx
import pytest

from tests.milo_eval import compare as CMP
from tests.milo_eval import providers as PV
from tests.milo_eval.cases import CASES

CASE = {c["id"]: c for c in CASES}


def _openai_transport(seen):
    replies = iter([
        {"choices": [{"finish_reason": "tool_calls", "message": {"role": "assistant", "content": None, "reasoning_content": "Need the quote.",
                                                                 "tool_calls": [{"id": "call_1", "type": "function", "function": {
                                                                     "name": "get_quote", "arguments": json.dumps({"ticker": "AAPL"})}}]}}],
         "usage": {"prompt_tokens": 30000, "completion_tokens": 40, "prompt_tokens_details": {"cached_tokens": 20000},
                   "completion_tokens_details": {"reasoning_tokens": 10}}},
        {"choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": "AAPL closed at $196.14 on Friday (delayed)."}}],
         "usage": {"prompt_tokens": 31000, "completion_tokens": 60}},
    ])

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=next(replies))
    return httpx.MockTransport(handler)


def test_the_chat_completions_adapter_runs_optics_request_and_tools():
    seen = []
    ad = PV.make("openai-compatible", "model-x", {"reasoning_effort": "medium"}, transport=_openai_transport(seen))
    row = asyncio.run(CMP.run_case(CASE["ACC-quote-AAPL"], ad))
    first, second = seen
    assert first["messages"][0]["role"] == "system" and first["messages"][0]["content"].startswith("You are Milo")
    assert "## Optic's advice policy" in first["messages"][0]["content"], "the same policy as production"
    assert first["reasoning_effort"] == "medium" and first["model"] == "model-x" and first["max_tokens"] == 8000
    names = [t["function"]["name"] for t in first["tools"]]
    assert "get_quote" in names and all(t["type"] == "function" for t in first["tools"])
    assert all("eager_input_streaming" not in t["function"] for t in first["tools"])
    tool_msg = second["messages"][-1]
    assert tool_msg["role"] == "tool" and tool_msg["tool_call_id"] == "call_1" and '"status": "ok"' in tool_msg["content"]
    assert second["messages"][-2]["reasoning_content"] == "Need the quote.", "the reasoning goes back unchanged (Kimi K3)"
    assert row["tool_calls"] == [{"name": "get_quote", "args": {"ticker": "AAPL"}, "status": "ok", "offered": True}]
    assert row["usage"] == {"input": 61000, "output": 100, "cached_input": 20000, "cache_write": 0, "reasoning": 10}
    assert row["answer"].startswith("AAPL closed at $196.14") and len(row["rounds"]) == 2
    checks = {c["check"]: c for c in row["checks"]}
    assert checks["grounded"]["passed"] and checks["advice_free"]["passed"] and checks["names_as_of"]["passed"]


def test_the_gemini_adapter_translates_the_schema_and_the_results():
    seen = []
    replies = iter([
        {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"functionCall": {"name": "get_quote", "args": {"ticker": "AAPL"}}}]}}],
         "usageMetadata": {"promptTokenCount": 25000, "candidatesTokenCount": 20, "thoughtsTokenCount": 15}},
        {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "thinking...", "thought": True},
                                                                       {"text": "AAPL is at $196.14, delayed."}]}}],
         "usageMetadata": {"promptTokenCount": 26000, "candidatesTokenCount": 30}},
    ])

    def handler(request):
        seen.append(json.loads(request.content))
        assert request.url.path.endswith("/models/gem-x:generateContent")
        return httpx.Response(200, json=next(replies))
    ad = PV.make("google", "gem-x", transport=httpx.MockTransport(handler))
    row = asyncio.run(CMP.run_case(CASE["ACC-quote-AAPL"], ad))
    decl = {d["name"]: d for d in seen[0]["tools"][0]["functionDeclarations"]}
    assert "additionalProperties" not in json.dumps(decl), "Gemini's schema dialect"
    assert decl["get_quote"]["parameters"]["properties"]["ticker"]["type"] == "string"
    assert seen[0]["systemInstruction"]["parts"][0]["text"].startswith("You are Milo")
    assert seen[0]["generationConfig"] == {"maxOutputTokens": 8000}, "production's output cap"
    resp = seen[1]["contents"][-1]["parts"][0]["functionResponse"]
    assert resp["name"] == "get_quote" and resp["response"]["status"] == "ok"
    assert row["answer"] == "AAPL is at $196.14, delayed.", "a thought part is not the answer"
    assert row["usage"]["reasoning"] == 15 and row["usage"]["output"] == 20 + 15 + 30, "thinking is billed as output"


def test_the_anthropic_adapter_sends_productions_request_unchanged():
    from app import ai
    sent = []

    class Block(types.SimpleNamespace):
        pass

    class Msgs:
        async def create(self, **kw):
            sent.append(kw)
            if len(sent) == 1:
                return types.SimpleNamespace(stop_reason="tool_use", usage=types.SimpleNamespace(input_tokens=100, output_tokens=5),
                                             content=[Block(type="tool_use", id="tu1", name="get_quote", input={"ticker": "AAPL"})])
            return types.SimpleNamespace(stop_reason="end_turn", usage=types.SimpleNamespace(input_tokens=120, output_tokens=9),
                                         content=[Block(type="text", text="AAPL was $196.14 at Friday's close, delayed.")])
    client = types.SimpleNamespace(beta=types.SimpleNamespace(messages=Msgs()))
    ad = PV.make("anthropic", "claude-sonnet-5-5", client=client)
    row = asyncio.run(CMP.run_case(CASE["ACC-quote-AAPL"], ad))
    kw = sent[0]
    assert kw["system"][0]["cache_control"] == {"type": "ephemeral"} and kw["thinking"] == {"type": "adaptive"}
    assert kw["model"] == "claude-sonnet-5-5" and kw["betas"] == [ai.FALLBACK_BETA]
    assert sent[1]["messages"][-1]["content"][0]["type"] == "tool_result"
    # the figure is the fixture's quote, so the grounding check passes; what is left can only be style
    assert next(c for c in row["checks"] if c["check"] == "grounded")["passed"], row["checks"]
    assert row["worst_severity"] in (None, 2, 3), row["checks"]


def test_the_responses_adapter_is_stateless_and_sends_every_output_item_back():
    seen = []
    replies = iter([
        {"status": "completed", "output": [
            {"type": "reasoning", "id": "rs_1", "summary": [], "encrypted_content": "gAAA-opaque"},
            {"type": "function_call", "id": "fc_1", "call_id": "call_9", "name": "get_quote", "arguments": json.dumps({"ticker": "AAPL"})}],
         "usage": {"input_tokens": 30000, "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 29000},
                   "output_tokens": 50, "output_tokens_details": {"reasoning_tokens": 40}}},
        {"status": "completed", "output": [
            {"type": "message", "id": "msg_1", "role": "assistant",
             "content": [{"type": "output_text", "text": "AAPL closed at $196.14 on Friday (delayed)."}]}],
         "usage": {"input_tokens": 31000, "input_tokens_details": {"cached_tokens": 29000, "cache_write_tokens": 1500},
                   "output_tokens": 70, "output_tokens_details": {"reasoning_tokens": 20}}},
    ])

    def handler(request):
        seen.append(json.loads(request.content))
        assert request.url.path.endswith("/responses")
        return httpx.Response(200, json=next(replies))
    ad = PV.make("openai", "gpt-x", {"reasoning": {"effort": "medium"}}, transport=httpx.MockTransport(handler))
    row = asyncio.run(CMP.run_case(CASE["ACC-quote-AAPL"], ad))
    first, second = seen
    assert first["store"] is False and first["reasoning"] == {"effort": "medium"} and first["max_output_tokens"] == 8000
    dev = first["input"][0]
    assert dev["role"] == "developer" and dev["content"][0]["text"].startswith("You are Milo")
    assert dev["content"][0]["prompt_cache_breakpoint"] == {"mode": "explicit"}, "the block production caches"
    assert all("prompt_cache_breakpoint" not in b for b in dev["content"][1:])
    assert all(t["type"] == "function" and "parameters" in t and "eager_input_streaming" not in t for t in first["tools"])
    back = second["input"][-3:]
    assert back[0] == {"type": "reasoning", "id": "rs_1", "summary": [], "encrypted_content": "gAAA-opaque"}
    assert back[1]["type"] == "function_call" and back[2]["type"] == "function_call_output" and back[2]["call_id"] == "call_9"
    assert row["answer"].startswith("AAPL closed at $196.14")
    assert row["usage"] == {"input": 61000, "output": 120, "cached_input": 29000, "cache_write": 30500, "reasoning": 60}


def test_haiku_is_not_sent_a_fallback_it_does_not_have():
    from app import ai
    ad = PV.make("anthropic", "claude-haiku-5-5")
    kwargs, _ = ai.build_chat_request([{"role": "user", "content": "What is a P/E ratio?"}], context={})
    ad.begin(kwargs, [])
    assert "fallbacks" not in ad.kwargs and "betas" not in ad.kwargs
    son = PV.make("anthropic", "claude-sonnet-5-5")
    son.begin(kwargs, [])
    assert son.kwargs["fallbacks"] == "default" and son.kwargs["betas"] == [ai.FALLBACK_BETA], "production's request unchanged"


def test_a_tool_the_answer_was_not_offered_is_severity_zero_and_never_runs():
    seen = []
    replies = iter([
        {"choices": [{"finish_reason": "tool_calls", "message": {"role": "assistant", "content": None, "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "get_my_portfolio", "arguments": "{\"part\": \"summary\"}"}}]}}],
         "usage": {"prompt_tokens": 10, "completion_tokens": 1}},
        {"choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": "NVDA and AMD compared."}}],
         "usage": {"prompt_tokens": 10, "completion_tokens": 1}}])
    tr = httpx.MockTransport(lambda r: seen.append(json.loads(r.content)) or httpx.Response(200, json=next(replies)))
    row = asyncio.run(CMP.run_case(CASE["POR-04"], PV.make("openai-compatible", "m", transport=tr)))
    assert row["unauthorized_tool_calls"] == ["get_my_portfolio"] and row["worst_severity"] == 0
    assert row["tool_calls"][0]["status"] == "unsupported"
    assert "AAPL" not in seen[1]["messages"][-1]["content"], "reader A's holdings were never read"


def test_severity_follows_the_error_policy():
    assert CMP.severity("grounded", "W2") == 0 and CMP.severity("grounded", "W1") == 1
    assert CMP.severity("advice_free", "W1") == 0 and CMP.severity("level_length:new", "W1") == 2
    assert CMP.severity("well_formed", "W5") == 3


def test_the_split_is_stable_and_about_thirty_percent_held_out():
    held = [c["id"] for c in CASES if CMP.split_of(c["id"]) == "heldout"]
    assert held == [c["id"] for c in CASES if CMP.split_of(c["id"]) == "heldout"]
    assert 0.2 <= len(held) / len(CASES) <= 0.4


def test_the_runner_refuses_without_a_cap_or_a_key(tmp_path, monkeypatch):
    ad = PV.make("openai", "m", transport=httpx.MockTransport(lambda r: pytest.fail("no call without a cap")))
    assert CMP.main(["--provider", "openai", "--model", "m", "--out", str(tmp_path), "--only", "TKR-01"], adapter=ad) == 2
    monkeypatch.setattr(CMP, "key_ok", lambda provider, adapter: {"usable": False, "reason": "HTTP 401"})
    assert CMP.main(["--provider", "openai", "--model", "m", "--max-dollars", "1", "--out", str(tmp_path), "--only", "TKR-01"], adapter=ad) == 2
    assert "Nothing was spent" in (tmp_path / "BLOCKED.md").read_text()


def test_extra_settings_merge_into_the_request_rather_than_replace_it():
    from app import ai
    kwargs, _ = ai.build_chat_request([{"role": "user", "content": "What is a P/E ratio?"}], context={})
    ad = PV.make("google", "gem-x", {"generationConfig": {"thinkingConfig": {"thinkingLevel": "medium"}}})
    ad.begin(kwargs, [])
    assert ad.body["generationConfig"] == {"maxOutputTokens": 8000, "thinkingConfig": {"thinkingLevel": "medium"}}
    ds = PV.make("openai-compatible", "deepseek", {"max_tokens": 262144})
    ds.begin(kwargs, [])
    assert ds.body["max_tokens"] == 262144, "a model's own recommended cap, when the run asks for it"


def test_the_dry_run_writes_the_request_and_sends_nothing(tmp_path):
    ad = PV.make("google", "gem-x", transport=httpx.MockTransport(lambda r: pytest.fail("a dry run sends nothing")))
    assert CMP.main(["--provider", "google", "--model", "gem-x", "--dry-run", "--out", str(tmp_path), "--only", "TKR-01"], adapter=ad) == 0
    preview = json.loads((tmp_path / "request-preview.json").read_text())
    assert preview["systemInstruction"]["parts"][0]["text"].startswith("You are Milo") and preview["tools"]


def test_costs_come_from_the_price_table_and_unknown_models_are_not_guessed():
    assert CMP.cost_of({"input": 1_000_000, "cached_input": 0, "output": 0}, "claude-sonnet-5-5") == pytest.approx(2.0)
    assert CMP.cost_of({"input": 1_000_000, "cached_input": 1_000_000, "output": 1_000_000}, "claude-sonnet-5-5") == pytest.approx(10.1)
    assert CMP.cost_of({"input": 1, "output": 1}, "some-unlisted-model") is None
    # a cache write is charged once, at the write price, not again as fresh input
    assert CMP.cost_of({"input": 1_000_000, "cache_write": 1_000_000, "output": 0}, "claude-sonnet-5-5") == pytest.approx(2.5)
