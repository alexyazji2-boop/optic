"""Cortex-style assistant: grounded chat + live deep research.

Two entry points, both Claude-backed:

  stream_chat()     - answers questions about the ticker currently loaded in
                      the terminal, with the whole computed analysis injected
                      as context so answers cite your numbers rather than
                      generic market commentary.
  deep_research()   - runs Claude's server-side web search to produce a dated
                      research brief on the ticker or on a macro question.

Both degrade gracefully: with no credentials configured the endpoints return a
clear message instead of failing, and the rest of the terminal is unaffected.
"""

from __future__ import annotations

import json
import os
from datetime import date
from typing import Any, AsyncGenerator, Dict, List, Optional

MODEL = "claude-opus-5"

# Server-side refusal fallback: on a policy decline the API re-runs the request
# on Anthropic's recommended fallback model inside the same call, so a false
# positive on a finance/security-adjacent question doesn't dead-end the chat.
FALLBACK_BETA = "server-side-fallback-2026-07-01"

SYSTEM_PROMPT = """You are Pulse, the analysis assistant built into a personal options-and-markets \
terminal — similar in spirit to a research co-pilot sitting next to a trading screen. The name reflects \
what you do: read the market's vital signs (gamma, flow, momentum, sentiment) in real time, not anything \
medical. Only introduce yourself by name if asked; don't work it into unrelated answers. The user is a \
self-directed trader running their own analysis.

## What you have
Every message includes a CONTEXT block: the terminal's own computed output for whatever the user \
is currently looking at. That may include Black-Scholes greeks aggregated across the option chain, \
dealer gamma exposure (GEX) by strike with the gamma flip point and call/put walls, a volume-and-open-\
interest-based call-vs-put flow proxy, daily technicals (RSI, MACD, moving averages, Fibonacci \
retracements anchored to the current trend direction), a cross-asset macro regime read, sector \
relative-strength rankings and ratio pair trades, a long-term/index view, and scored news headlines.

## How to answer
Ground every claim in the CONTEXT numbers and name them. "Net GEX is negative at -$412m per 1% and \
spot is below the 6,180 flip, so moves accelerate rather than mean-revert" is useful. "The market \
looks volatile" is not.

Lead with the answer. One or two sentences on what the data says, then the supporting detail. Keep \
responses focused and brief — most questions need a short paragraph, not a report. Use prose; reach \
for a table only for genuinely enumerable facts.

Be explicit about the limits of the data rather than papering over them:
- Prices are delayed roughly 15 minutes and the greeks are computed locally from Black-Scholes with \
a zero risk-free rate, so they are approximations.
- The call-vs-put flow figures are a volume/open-interest *proxy*. Free data has no trade tape, so \
whether a contract was bought or sold is inferred, never observed. Say so when it matters to the \
conclusion.
- The GEX numbers assume dealers are short customer calls and long customer puts. It is the standard \
retail assumption and it is sometimes wrong.

If the CONTEXT does not contain what is needed to answer, say that plainly and say what would.

Answer the question asked, at the scope asked. If the user asks what the gamma profile implies, don't \
also deliver an unrequested full trade plan.

## Boundaries
You analyse; you do not place orders, and this terminal has no brokerage connection. You are not a \
licensed advisor — discuss structures, probabilities, risk, and what the data supports, but don't \
tell the user what they personally should do with their money, and don't project specific returns. \
When a question is really about position sizing or suitability, talk about the mechanics and the risk \
and note that the allocation decision is theirs."""

RESEARCH_PROMPT = """You are a market research analyst producing a briefing for a self-directed \
swing trader. Use web search to find current, dated information — you are being asked precisely \
because the terminal's own data is quantitative and doesn't cover narrative.

Produce, in this order:
1. **What's happening now** — the two or three developments actually driving the name or theme, each \
with a date and source.
2. **The bull case** and **the bear case** — the strongest honest version of each, not a strawman.
3. **Catalysts ahead** — dated where possible (earnings, product events, regulatory decisions, macro prints).
4. **What would change the picture** — the specific evidence that would invalidate the current read.

Rules: cite sources with dates. Distinguish reported fact from analyst opinion from speculation. If \
search turns up nothing recent, say so rather than filling space with background. Note when sources \
conflict. Keep it tight — a trader reads this in two minutes. Do not give personalised investment \
advice or price targets of your own invention."""


def _client():
    """Return an AsyncAnthropic client, or None if no credentials are available.

    The SDK resolves ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN, or an `ant auth
    login` profile on its own, so we construct it bare and let it decide.
    """
    try:
        from anthropic import AsyncAnthropic
    except ImportError:
        return None
    try:
        return AsyncAnthropic()
    except Exception:
        return None


def available() -> Dict[str, Any]:
    """Report whether the assistant can actually make a call.

    The SDK client constructs fine with no credentials and only fails at request
    time, so checking construction alone would have the UI announce itself ready
    and then error on the first question.
    """
    from pathlib import Path

    source = None
    if os.environ.get("ANTHROPIC_API_KEY"):
        source = "ANTHROPIC_API_KEY"
    elif os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        source = "ANTHROPIC_AUTH_TOKEN"
    else:
        config_dir = os.environ.get("ANTHROPIC_CONFIG_DIR")
        base = Path(config_dir) if config_dir else Path.home() / ".config" / "anthropic"
        creds = base / "credentials"
        try:
            if creds.is_dir() and any(creds.glob("*.json")):
                source = "ant auth profile"
        except OSError:
            source = None

    client = _client()
    return {
        "enabled": bool(client is not None and source),
        "model": MODEL,
        "credential_source": source or "none",
        "hint": (
            "Set ANTHROPIC_API_KEY in your environment (or run `ant auth login`) to enable "
            "the assistant and deep research. Every other panel works without it."
        ),
    }


# --------------------------------------------------------------- context prep


def _prune(value: Any, depth: int = 0) -> Any:
    """Strip the chart-plotting arrays out of a snapshot.

    The model needs the numbers that carry meaning, not 120 points of price
    series per instrument — those are for the canvas and would dominate the
    context window for nothing.
    """
    drop_keys = {
        "series",
        "ratio_series",
        "price_series",
        "weekly_closes",
        "weekly_dates",
        "_exposure_frame",
    }
    if isinstance(value, dict):
        out = {}
        for key, inner in value.items():
            if key in drop_keys:
                continue
            if key == "profile" and isinstance(inner, dict):
                # Keep the flip point, drop the 61-point grid.
                out[key] = {
                    k: v for k, v in inner.items() if k not in ("spots", "net_gex")
                }
                continue
            out[key] = _prune(inner, depth + 1)
        return out
    if isinstance(value, list):
        limit = 25 if depth < 3 else 10
        return [_prune(v, depth + 1) for v in value[:limit]]
    return value


def build_context(snapshot: Dict[str, Any]) -> str:
    pruned = _prune(snapshot)
    body = json.dumps(pruned, indent=1, default=str)
    if len(body) > 90_000:
        body = body[:90_000] + "\n... [context truncated]"
    return "CONTEXT — terminal output as of {}:\n```json\n{}\n```".format(
        date.today().isoformat(), body
    )


def _sse(event: str, payload: Dict[str, Any]) -> str:
    return "event: {}\ndata: {}\n\n".format(event, json.dumps(payload))


# ---------------------------------------------------------------- chat stream


async def stream_chat(
    history: List[Dict[str, str]],
    context: Optional[Dict[str, Any]] = None,
    use_web: bool = False,
) -> AsyncGenerator[str, None]:
    client = _client()
    if client is None:
        yield _sse(
            "error",
            {
                "message": "Assistant is not configured. Set ANTHROPIC_API_KEY in your "
                "environment (or run `ant auth login`) and restart the server."
            },
        )
        return

    messages: List[Dict[str, Any]] = []
    for turn in history:
        role = "assistant" if turn.get("role") == "assistant" else "user"
        text = (turn.get("content") or "").strip()
        if text:
            messages.append({"role": role, "content": text})

    if not messages:
        yield _sse("error", {"message": "No message to send."})
        return

    if context:
        # Context rides on the final user turn so the cached system prefix stays
        # byte-identical between requests.
        last = messages[-1]
        messages[-1] = {
            "role": last["role"],
            "content": "{}\n\n{}".format(build_context(context), last["content"]),
        }

    tools: List[Dict[str, Any]] = []
    if use_web:
        tools.append({"type": "web_search_20260209", "name": "web_search", "max_uses": 5})

    kwargs: Dict[str, Any] = {
        "model": MODEL,
        "max_tokens": 8000,
        "system": [
            {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}
        ],
        "messages": messages,
        "thinking": {"type": "adaptive"},
        "output_config": {"effort": "medium"},
        "betas": [FALLBACK_BETA],
        "fallbacks": "default",
    }
    if tools:
        kwargs["tools"] = tools

    try:
        async with client.beta.messages.stream(**kwargs) as stream:
            async for event in stream:
                etype = getattr(event, "type", "")
                if etype == "content_block_start":
                    block = getattr(event, "content_block", None)
                    btype = getattr(block, "type", "")
                    if btype == "thinking":
                        yield _sse("status", {"state": "thinking"})
                    elif btype == "server_tool_use":
                        yield _sse("status", {"state": "searching the web"})
                elif etype == "content_block_delta":
                    delta = getattr(event, "delta", None)
                    if getattr(delta, "type", "") == "text_delta":
                        yield _sse("delta", {"text": delta.text})
            final = await stream.get_final_message()

        # A refusal is a successful HTTP response with empty or partial content,
        # so it has to be checked explicitly rather than caught.
        if getattr(final, "stop_reason", None) == "refusal":
            details = getattr(final, "stop_details", None)
            category = getattr(details, "category", None)
            yield _sse(
                "error",
                {
                    "message": "The request was declined by safety classifiers{}. "
                    "Try rephrasing toward the market-analysis question you're after.".format(
                        " (" + str(category) + ")" if category else ""
                    )
                },
            )
            return

        citations = []
        for block in getattr(final, "content", []) or []:
            if getattr(block, "type", "") == "web_search_tool_result":
                content = getattr(block, "content", None)
                if isinstance(content, list):
                    for result in content[:8]:
                        citations.append(
                            {
                                "title": getattr(result, "title", ""),
                                "url": getattr(result, "url", ""),
                            }
                        )

        usage = getattr(final, "usage", None)
        yield _sse(
            "done",
            {
                "model": getattr(final, "model", MODEL),
                "citations": citations,
                "usage": {
                    "input_tokens": getattr(usage, "input_tokens", None),
                    "output_tokens": getattr(usage, "output_tokens", None),
                    "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", None),
                }
                if usage
                else None,
            },
        )
    except Exception as exc:  # surfaced to the UI rather than swallowed
        yield _sse("error", {"message": "{}: {}".format(type(exc).__name__, exc)})


# -------------------------------------------------------------- deep research


async def deep_research(
    ticker: str,
    question: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> AsyncGenerator[str, None]:
    """Live web research on a ticker or macro question, streamed as it's written."""
    client = _client()
    if client is None:
        yield _sse(
            "error",
            {
                "message": "Deep research needs Claude API access. Set ANTHROPIC_API_KEY "
                "(or run `ant auth login`) and restart. The headline pass still works without it."
            },
        )
        return

    ask = question or (
        "Research {} for a swing trader looking out two to eight weeks. What is moving the "
        "stock right now, what is the bull and bear case, and what dated catalysts are ahead?".format(
            ticker.upper()
        )
    )
    if context:
        ask = "{}\n\n{}".format(build_context(context), ask)

    try:
        async with client.beta.messages.stream(
            model=MODEL,
            max_tokens=12000,
            system=[
                {"type": "text", "text": RESEARCH_PROMPT, "cache_control": {"type": "ephemeral"}}
            ],
            messages=[{"role": "user", "content": ask}],
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
            tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 10}],
            betas=[FALLBACK_BETA],
            fallbacks="default",
        ) as stream:
            async for event in stream:
                etype = getattr(event, "type", "")
                if etype == "content_block_start":
                    block = getattr(event, "content_block", None)
                    if getattr(block, "type", "") == "server_tool_use":
                        yield _sse("status", {"state": "searching"})
                    elif getattr(block, "type", "") == "thinking":
                        yield _sse("status", {"state": "reading and weighing sources"})
                elif etype == "content_block_delta":
                    delta = getattr(event, "delta", None)
                    if getattr(delta, "type", "") == "text_delta":
                        yield _sse("delta", {"text": delta.text})
            final = await stream.get_final_message()

        if getattr(final, "stop_reason", None) == "refusal":
            yield _sse("error", {"message": "The research request was declined by safety classifiers."})
            return

        sources = []
        for block in getattr(final, "content", []) or []:
            if getattr(block, "type", "") == "web_search_tool_result":
                content = getattr(block, "content", None)
                if isinstance(content, list):
                    for result in content:
                        sources.append(
                            {
                                "title": getattr(result, "title", ""),
                                "url": getattr(result, "url", ""),
                                "age": getattr(result, "page_age", None),
                            }
                        )

        seen = set()
        unique = []
        for src in sources:
            if src["url"] and src["url"] not in seen:
                seen.add(src["url"])
                unique.append(src)

        yield _sse("done", {"sources": unique[:20], "model": getattr(final, "model", MODEL)})
    except Exception as exc:
        yield _sse("error", {"message": "{}: {}".format(type(exc).__name__, exc)})
