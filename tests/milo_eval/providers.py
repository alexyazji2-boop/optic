"""Provider adapters for comparing models on Milo's benchmark (Phase 13, directive 15 Part 4; 2026-11-02).

One loop (`compare.py`) runs every model under the same conditions: Optic builds the request exactly as production
does (`ai.build_chat_request`: the same system prompt, writing rules, advice policy, level and horizon blocks, CONTEXT
and history), the same tools are offered by the same rule (`main._milo_toolbox`), and every tool call is run by
Optic's own server-side `Toolbox` on the benchmark's fixtures. An adapter only translates that request into its
provider's format and the reply back. The translations, and the adaptations each provider needs, are written down
here so that no candidate is disadvantaged by a format it does not accept:

* Anthropic (`AnthropicAdapter`): the production request unchanged (system blocks with the cache breakpoint,
  adaptive thinking, effort, the fallback beta), through the official SDK. Non-streaming here; the streamed
  production path is `run_model.py`, which also measures time to first text. The one change: a model with no
  server-side fallback (Claude Haiku 5.5, per the Claude API reference) is sent neither `fallbacks` nor its beta.
* OpenAI (`OpenAIResponsesAdapter`, provider "openai"): the Responses API, because OpenAI's current models need it
  for tool calls ("Tool calling requires the Responses API" on gpt-6.1-sol and gpt-6.1-terra; gpt-6-luna allows
  function calling in Chat Completions only with reasoning off; model pages read 2026-11-02). Stateless
  (`store: false`), so every output item, encrypted reasoning included, goes back with the tool results, as
  OpenAI's reasoning guide says. The cached system block is a developer message with an explicit cache breakpoint,
  where production's Anthropic request puts its own; the rest of the system follows it.
* OpenAI-compatible servers (`OpenAIAdapter`, providers "openai-compatible" and "openai-chat"; vLLM, Together,
  Fireworks and most open-weight hosts speak Chat Completions): the system blocks joined in order into one system
  message, each tool as a `function` with the same JSON schema, tool results as `tool` messages. The assistant turn
  goes back as the server returned it, its reasoning fields included (Kimi K3 requires that).
* Google Gemini (`GeminiAdapter`, REST `generateContent`): the system blocks as `systemInstruction`, tools as
  `functionDeclarations`, results as `functionResponse` parts. The model's parts go back unchanged, so the thought
  signatures inside them survive (Google's thinking guide: they are "required to maintain reasoning continuity
  across multi-turn interactions"). Gemini's schema dialect is a subset of JSON Schema, so keys it rejects
  (`additionalProperties`, `$schema`) are removed; nothing else in the schema changes, and `compare.py` validates
  every argument against Optic's own schema anyway (`milo_tools.validate`).

Reasoning settings are each provider's own (`extra`, for example `{"reasoning": {"effort": "medium"}}` for OpenAI):
Anthropic's thinking block is not sent elsewhere. Every adapter carries production's output cap (8,000 tokens,
reasoning included) in its provider's field: `max_output_tokens`, `max_tokens`, `generationConfig.maxOutputTokens`.
A model whose own guidance asks for more (DeepSeek V4.1 Flash's card: `max_tokens` of 256K or more) can be run with
its setting through `extra` as well; each round's stop reason is recorded, so an answer cut short shows as that. Usage is recorded in one convention for every provider: `input` is
every prompt token (fresh, cached and written), `output` every billed output token, reasoning included (Gemini
reports its thinking apart from its output; both are billed as output).

No adapter here has called a provider: the API keys on this machine are refused or absent (BLOCKERS BL-01), so the
adapters are tested offline against reply shapes taken from each provider's documentation
(`tests/test_milo_compare.py`). Before a paid run, `compare.py --dry-run` prints the exact request each one would
send; the first paid call is also the first check that a provider accepts it.
"""
from __future__ import annotations

import copy
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx


@dataclass
class ToolCall:
    id: str
    name: str
    args: Dict[str, Any]


@dataclass
class Turn:
    text: str
    calls: List[ToolCall] = field(default_factory=list)
    usage: Dict[str, int] = field(default_factory=dict)       # input, output, cached_input, cache_write, reasoning
    stop: str = ""
    seconds: float = 0.0


def system_text(kwargs: Dict[str, Any]) -> str:
    """The production system prompt as one string, its blocks in order (for providers with a single system slot)."""
    blocks = kwargs.get("system") or []
    if isinstance(blocks, str):
        return blocks
    return "\n\n".join(b.get("text", "") for b in blocks if isinstance(b, dict))


def _user_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    return "\n".join(b.get("text", "") for b in content or [] if isinstance(b, dict) and b.get("type") == "text")


def plain_tools(specs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Optic's tool specs without Anthropic-only fields (`eager_input_streaming`)."""
    return [{"name": s["name"], "description": s.get("description", ""), "input_schema": s.get("input_schema") or {}}
            for s in specs]


_GEMINI_SCHEMA_KEYS = {"type", "description", "properties", "required", "items", "enum", "nullable", "format",
                       "minimum", "maximum", "minItems", "maxItems", "minLength", "maxLength"}


def gemini_schema(schema: Any) -> Any:
    """A JSON schema in Gemini's dialect: the keys it accepts, recursively, nothing else changed."""
    if isinstance(schema, dict):
        out = {}
        for k, v in schema.items():
            if k not in _GEMINI_SCHEMA_KEYS:
                continue
            if k == "properties" and isinstance(v, dict):
                out[k] = {name: gemini_schema(sub) for name, sub in v.items()}
            elif k == "items":
                out[k] = gemini_schema(v)
            else:
                out[k] = v
        return out
    return schema


def _merged(body: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    """`body` with `extra` laid over it, nested objects merged rather than replaced."""
    out = dict(body)
    for k, v in extra.items():
        out[k] = _merged(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


class Adapter:
    provider = "base"

    def __init__(self, model: str, extra: Optional[Dict[str, Any]] = None):
        self.model, self.extra = model, dict(extra or {})

    def begin(self, kwargs: Dict[str, Any], tools: List[Dict[str, Any]]) -> None:
        raise NotImplementedError

    async def step(self, final: bool = False) -> Turn:
        raise NotImplementedError

    def add_results(self, turn: Turn, results: List[Dict[str, Any]]) -> None:
        """`results`: one {"call": ToolCall, "content": str, "is_error": bool} per call of `turn`."""
        raise NotImplementedError

    def request_preview(self) -> Dict[str, Any]:
        """The request the next step would send, for --dry-run (no network)."""
        raise NotImplementedError


# Models the server-side refusal fallback does not cover: "safeguard refusals with no server-side fallback" (the
# Claude API reference bundled with Claude Code, Migrating to Claude Haiku 5.5). Sending it one could fail the request
# for a reason that is not the model's.
NO_FALLBACK = ("claude-haiku-5-5",)


class AnthropicAdapter(Adapter):
    """The production request, unchanged, through the official SDK's async client."""
    provider = "anthropic"

    def __init__(self, model: str, extra: Optional[Dict[str, Any]] = None, client: Any = None):
        super().__init__(model, extra)
        self.client = client

    def begin(self, kwargs, tools):
        self.kwargs = copy.deepcopy(kwargs)
        self.kwargs["model"] = self.model
        self.kwargs["tools"] = tools + [t for t in (kwargs.get("tools") or []) if t.get("type")]   # keeps web search
        if self.model.startswith(NO_FALLBACK):
            self.kwargs.pop("fallbacks", None)
            self.kwargs["betas"] = [b for b in self.kwargs.get("betas") or [] if not b.startswith("server-side-fallback")]
            if not self.kwargs["betas"]:
                self.kwargs.pop("betas")
        self.kwargs.update(self.extra)

    def request_preview(self):
        return self.kwargs

    async def step(self, final=False):
        kw = dict(self.kwargs)
        if final:
            kw["tool_choice"] = {"type": "none"}
        t0 = time.perf_counter()
        msg = await self.client.beta.messages.create(**kw)
        took = time.perf_counter() - t0
        u = getattr(msg, "usage", None)
        read, write = getattr(u, "cache_read_input_tokens", 0) or 0, getattr(u, "cache_creation_input_tokens", 0) or 0
        # Anthropic's input_tokens counts only what was neither read from nor written to the cache
        usage = {"input": (getattr(u, "input_tokens", 0) or 0) + read + write, "output": getattr(u, "output_tokens", 0) or 0,
                 "cached_input": read, "cache_write": write, "reasoning": 0}
        text = "".join(getattr(b, "text", "") for b in msg.content if getattr(b, "type", "") == "text")
        calls = [ToolCall(b.id, b.name, dict(b.input or {})) for b in msg.content if getattr(b, "type", "") == "tool_use"]
        self._last = msg
        return Turn(text, calls, usage, getattr(msg, "stop_reason", "") or "", took)

    def add_results(self, turn, results):
        self.kwargs["messages"] = list(self.kwargs["messages"]) + [
            {"role": "assistant", "content": self._last.content},
            {"role": "user", "content": [dict({"type": "tool_result", "tool_use_id": r["call"].id, "content": r["content"]},
                                              **({"is_error": True} if r["is_error"] else {})) for r in results]}]


class OpenAIAdapter(Adapter):
    """Chat Completions with function tools: any OpenAI-compatible server at `base_url`."""
    provider = "openai-compatible"

    def __init__(self, model: str, extra: Optional[Dict[str, Any]] = None, base_url: str = "https://api.openai.com/v1",
                 api_key_env: str = "OPENAI_API_KEY", transport: Optional[httpx.BaseTransport] = None):
        super().__init__(model, extra)
        self.base_url, self.api_key_env, self.transport = base_url.rstrip("/"), api_key_env, transport

    def begin(self, kwargs, tools):
        msgs: List[Dict[str, Any]] = [{"role": "system", "content": system_text(kwargs)}]
        for m in kwargs.get("messages") or []:
            msgs.append({"role": m["role"], "content": _user_text(m.get("content"))})
        self.body = {"model": self.model, "messages": msgs, "max_tokens": kwargs.get("max_tokens"),
                     "tools": [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                                 "parameters": t["input_schema"]}} for t in plain_tools(tools)]}
        self.body = _merged(self.body, self.extra)

    def request_preview(self):
        return self.body

    async def step(self, final=False):
        body = dict(self.body)
        if final:
            body["tool_choice"] = "none"
        headers = {"Authorization": "Bearer " + os.environ.get(self.api_key_env, ""), "Content-Type": "application/json"}
        t0 = time.perf_counter()
        async with httpx.AsyncClient(transport=self.transport, timeout=120) as http:
            r = await http.post(self.base_url + "/chat/completions", headers=headers, json=body)
        took = time.perf_counter() - t0
        r.raise_for_status()
        d = r.json()
        choice = (d.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        calls = []
        for c in msg.get("tool_calls") or []:
            fn = c.get("function") or {}
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except ValueError:
                args = {"__unparsed__": fn.get("arguments")}
            calls.append(ToolCall(c.get("id", ""), fn.get("name", ""), args if isinstance(args, dict) else {"__unparsed__": args}))
        u = d.get("usage") or {}
        details = u.get("prompt_tokens_details") or {}
        usage = {"input": u.get("prompt_tokens", 0), "output": u.get("completion_tokens", 0),
                 "cached_input": details.get("cached_tokens", 0) or 0, "cache_write": details.get("cache_write_tokens", 0) or 0,
                 "reasoning": (u.get("completion_tokens_details") or {}).get("reasoning_tokens", 0) or 0}
        self._last = msg
        return Turn(msg.get("content") or "", calls, usage, choice.get("finish_reason", ""), took)

    # what an assistant turn carries back: the text, the calls, and the reasoning fields servers use for it
    # (`reasoning_content` on vLLM and Kimi K3, `reasoning` and `reasoning_details` elsewhere)
    _KEEP = ("content", "tool_calls", "reasoning_content", "reasoning", "reasoning_details")

    def add_results(self, turn, results):
        back = {"role": "assistant", **{k: self._last[k] for k in self._KEEP if k in self._last}}
        self.body["messages"] = list(self.body["messages"]) + [back] + [
            {"role": "tool", "tool_call_id": r["call"].id, "content": r["content"]} for r in results]


class OpenAIResponsesAdapter(Adapter):
    """OpenAI's Responses API with function tools, stateless."""
    provider = "openai"

    def __init__(self, model: str, extra: Optional[Dict[str, Any]] = None, base_url: str = "https://api.openai.com/v1",
                 api_key_env: str = "OPENAI_API_KEY", transport: Optional[httpx.BaseTransport] = None):
        super().__init__(model, extra)
        self.base_url, self.api_key_env, self.transport = base_url.rstrip("/"), api_key_env, transport

    def begin(self, kwargs, tools):
        blocks = [b for b in kwargs.get("system") or [] if isinstance(b, dict)]
        dev = [{"type": "input_text", "text": b.get("text", ""), **({"prompt_cache_breakpoint": {"mode": "explicit"}}
                                                                  if b.get("cache_control") else {})} for b in blocks]
        items: List[Dict[str, Any]] = [{"role": "developer", "content": dev}]
        for m in kwargs.get("messages") or []:
            items.append({"role": m["role"], "content": _user_text(m.get("content"))})
        self.body = {"model": self.model, "store": False, "input": items, "max_output_tokens": kwargs.get("max_tokens"),
                     "tools": [{"type": "function", "name": t["name"], "description": t["description"],
                                "parameters": t["input_schema"]} for t in plain_tools(tools)]}
        self.body = _merged(self.body, self.extra)

    def request_preview(self):
        return self.body

    async def step(self, final=False):
        body = dict(self.body)
        if final:
            body["tool_choice"] = "none"
        headers = {"Authorization": "Bearer " + os.environ.get(self.api_key_env, ""), "Content-Type": "application/json"}
        t0 = time.perf_counter()
        async with httpx.AsyncClient(transport=self.transport, timeout=120) as http:
            r = await http.post(self.base_url + "/responses", headers=headers, json=body)
        took = time.perf_counter() - t0
        r.raise_for_status()
        d = r.json()
        out = d.get("output") or []
        text = "".join(c.get("text", "") for item in out if item.get("type") == "message"
                       for c in item.get("content") or [] if c.get("type") == "output_text")
        calls = []
        for item in out:
            if item.get("type") != "function_call":
                continue
            try:
                args = json.loads(item.get("arguments") or "{}")
            except ValueError:
                args = {"__unparsed__": item.get("arguments")}
            calls.append(ToolCall(item.get("call_id", ""), item.get("name", ""), args if isinstance(args, dict) else {"__unparsed__": args}))
        u = d.get("usage") or {}
        details = u.get("input_tokens_details") or {}
        # input_tokens includes the cached and the written tokens (OpenAI's prompt caching guide)
        usage = {"input": u.get("input_tokens", 0), "output": u.get("output_tokens", 0),
                 "cached_input": details.get("cached_tokens", 0) or 0, "cache_write": details.get("cache_write_tokens", 0) or 0,
                 "reasoning": (u.get("output_tokens_details") or {}).get("reasoning_tokens", 0) or 0}
        self._last = out
        return Turn(text, calls, usage, d.get("status", ""), took)

    def add_results(self, turn, results):
        # every output item goes back, reasoning first, then each call's output ("preserve every output item")
        self.body["input"] = list(self.body["input"]) + list(self._last) + [
            {"type": "function_call_output", "call_id": r["call"].id, "output": r["content"]} for r in results]


class GeminiAdapter(Adapter):
    """Gemini's REST generateContent with function declarations."""
    provider = "google"

    def __init__(self, model: str, extra: Optional[Dict[str, Any]] = None,
                 base_url: str = "https://generativelanguage.googleapis.com/v1beta", api_key_env: str = "GEMINI_API_KEY",
                 transport: Optional[httpx.BaseTransport] = None):
        super().__init__(model, extra)
        self.base_url, self.api_key_env, self.transport = base_url.rstrip("/"), api_key_env, transport

    def begin(self, kwargs, tools):
        contents = [{"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": _user_text(m.get("content"))}]}
                    for m in kwargs.get("messages") or []]
        self.body = {"systemInstruction": {"parts": [{"text": system_text(kwargs)}]}, "contents": contents,
                     "generationConfig": {"maxOutputTokens": kwargs.get("max_tokens")},
                     "tools": [{"functionDeclarations": [{"name": t["name"], "description": t["description"],
                                                          "parameters": gemini_schema(t["input_schema"])} for t in plain_tools(tools)]}]}
        self.body = _merged(self.body, self.extra)

    def request_preview(self):
        return self.body

    async def step(self, final=False):
        body = dict(self.body)
        if final:
            body["toolConfig"] = {"functionCallingConfig": {"mode": "NONE"}}
        url = "{}/models/{}:generateContent".format(self.base_url, self.model)
        t0 = time.perf_counter()
        async with httpx.AsyncClient(transport=self.transport, timeout=120) as http:
            r = await http.post(url, headers={"x-goog-api-key": os.environ.get(self.api_key_env, ""),
                                              "Content-Type": "application/json"}, json=body)
        took = time.perf_counter() - t0
        r.raise_for_status()
        d = r.json()
        cand = (d.get("candidates") or [{}])[0]
        parts = (cand.get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts if "text" in p and not p.get("thought"))
        calls = [ToolCall("call-{}".format(i), p["functionCall"].get("name", ""), dict(p["functionCall"].get("args") or {}))
                 for i, p in enumerate(parts) if "functionCall" in p]
        u = d.get("usageMetadata") or {}
        thoughts = u.get("thoughtsTokenCount", 0) or 0
        # "response pricing is the sum of output tokens and thinking tokens" (Gemini thinking guide, 2026-11-02)
        usage = {"input": u.get("promptTokenCount", 0), "output": (u.get("candidatesTokenCount", 0) or 0) + thoughts,
                 "cached_input": u.get("cachedContentTokenCount", 0) or 0, "cache_write": 0, "reasoning": thoughts}
        self._last_parts = parts
        return Turn(text, calls, usage, cand.get("finishReason", ""), took)

    def add_results(self, turn, results):
        self.body["contents"] = list(self.body["contents"]) + [
            {"role": "model", "parts": self._last_parts},
            {"role": "user", "parts": [{"functionResponse": {"name": r["call"].name, "response": _as_obj(r["content"])}}
                                       for r in results]}]


def _as_obj(content: str) -> Dict[str, Any]:
    try:
        v = json.loads(content)
        return v if isinstance(v, dict) else {"result": v}
    except ValueError:
        return {"result": content}


def make(provider: str, model: str, extra: Optional[Dict[str, Any]] = None, **kw: Any) -> Adapter:
    if provider == "anthropic":
        return AnthropicAdapter(model, extra, client=kw.get("client"))
    if provider == "openai":
        return OpenAIResponsesAdapter(model, extra, **{k: v for k, v in kw.items() if k in ("base_url", "api_key_env", "transport")})
    if provider in ("openai-compatible", "openai-chat"):
        return OpenAIAdapter(model, extra, **{k: v for k, v in kw.items() if k in ("base_url", "api_key_env", "transport")})
    if provider == "google":
        return GeminiAdapter(model, extra, **{k: v for k, v in kw.items() if k in ("base_url", "api_key_env", "transport")})
    raise ValueError("unknown provider " + provider)
