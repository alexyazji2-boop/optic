"""Milo's answers on the evaluation suite, against the production model, under a spend cap (post-demo Phase 08,
2026-10-29; ported by hand from the milo-upgrade branch's tests/milo_eval/run_model.py at 55721f6).

    .venv/bin/python -m tests.milo_eval.run_model --max-dollars 5 [--only PREFIX] [--out DIR]

Each case goes through the same route and fixtures as `run.py`; then the real `ai.stream_chat` writes the
answer, with the fixture toolbox answering Milo's lookups. Recorded per answer: the text, latency (first text
and total), the usage the API reports and its cost, and every answer check (`answer_checks.py`).

It first asks Anthropic's Models API whether the key is accepted (free). The key is the app's own: ANTHROPIC_API_KEY
when it is set, else the one in the main checkout's .env (OPTIC_ENV_FILE, default ~/Optic/options-terminal/.env), read
into this process and never printed; any base URL in the environment (a stand-in's, or another program's) is removed
first. A refused key writes BLOCKED and spends nothing. It stops before the next answer once the cap is reached. It
never runs from pytest.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional
from unittest import mock

PRICE_IN, PRICE_OUT, PRICE_CACHED, PRICE_CACHE_WRITE = 2.0, 10.0, 0.2, 2.5     # per million tokens


def _app_key() -> None:
    """The app's key into this process, from the main checkout's .env, when the environment has none."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return
    path = os.path.expanduser(os.environ.get("OPTIC_ENV_FILE", "~/Optic/options-terminal/.env"))
    try:
        for line in open(path).read().splitlines():
            line = line.strip()
            if line.startswith("ANTHROPIC_API_KEY="):
                os.environ["ANTHROPIC_API_KEY"] = line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass


def key_status() -> Dict[str, Any]:
    """Whether the app's own key is accepted, by the free Models API. Never uses another program's credentials."""
    os.environ.pop("ANTHROPIC_BASE_URL", None)
    _app_key()
    try:
        from anthropic import Anthropic
        Anthropic(max_retries=0, timeout=15).models.list(limit=1)
        return {"usable": True}
    except Exception as exc:                                          # noqa: BLE001
        return {"usable": False, "reason": "{} {}".format(type(exc).__name__, getattr(exc, "status_code", "") or "").strip()}


def cost(usage: Dict[str, int]) -> float:
    return (usage.get("input_tokens", 0) * PRICE_IN + usage.get("output_tokens", 0) * PRICE_OUT
            + usage.get("cache_read_input_tokens", 0) * PRICE_CACHED) / 1e6


async def answer(case: Dict[str, Any], client: Any) -> Dict[str, Any]:
    """One case's answer from `client` (the real AsyncAnthropic, or a stand-in in tests)."""
    from app import ai
    from tests.milo_eval import harness
    got = harness.assemble(case)
    messages = list(case.get("history") or []) + [{"role": "user", "content": case["question"]}]
    text, first, usage, retrieved = [], None, {}, []
    t0 = time.perf_counter()
    with harness.world(case.get("user"), case.get("world")) as m, mock.patch.object(ai, "_client", lambda: client):
        box = m._milo_toolbox(__import__("types").SimpleNamespace(), got["context"])
        async for chunk in ai.stream_chat(messages, context=got["context"], use_web=bool(case.get("web")), toolbox=box,
                                          mode=case.get("mode") or "intermediate"):
            event = chunk.split("\n", 1)[0].replace("event: ", "")
            data = json.loads(chunk.split("data: ", 1)[1]) if "data: " in chunk else {}
            if event == "delta":
                first = first or time.perf_counter() - t0
                text.append(data.get("text", ""))
            elif event == "done":
                usage, retrieved = data.get("usage") or {}, data.get("retrieved") or []
            elif event == "error":
                text.append("[ERROR] " + str(data.get("message")))
        tool_results = [json.loads(c) for c, _ in box._memo.values()]
    return {"answer": "".join(text), "first_text_s": first, "total_s": time.perf_counter() - t0, "usage": usage,
            "cost": cost(usage), "retrieved": retrieved, "context": got["context"], "tool_results": tool_results}


def evaluate(case: Dict[str, Any], res: Dict[str, Any]) -> list:
    from tests.milo_eval import answer_checks as A
    headlines = [i for t in res["tool_results"] for i in (t.get("headlines") or t.get("items") or []) if isinstance(i, dict) and i.get("title")]
    ev = {"context": res["context"], "tool_results": res["tool_results"], "headlines": headlines,
          "subject": (res["context"].get("focus") or {}).get("ticker")}
    return [(cid,) + A.run(cid, res["answer"], ev) for cid in A.all_for(case)]


def main(argv=None, client: Optional[Any] = None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-dollars", type=float, required=True)
    ap.add_argument("--only")
    ap.add_argument("--out", default="milo-eval-answers")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if client is None:
        status = key_status()
        if not status["usable"]:
            (out / "BLOCKED.md").write_text("Not run: the app's Anthropic key was refused ({}). Nothing was spent.\n".format(status["reason"]))
            print("BLOCKED:", status["reason"])
            return 2
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic(max_retries=2)
    from tests.milo_eval.cases import CASES
    spent, rows = 0.0, []
    for case in CASES:
        if a.only and not case["id"].startswith(a.only):
            continue
        if spent >= a.max_dollars:
            rows.append({"id": case["id"], "skipped": "spend cap reached"})
            continue
        res = asyncio.run(answer(case, client))
        spent += res["cost"]
        rows.append({"id": case["id"], "category": case["category"], "answer": res["answer"], "first_text_s": res["first_text_s"],
                     "total_s": res["total_s"], "usage": res["usage"], "cost": res["cost"], "checks": evaluate(case, res)})
    (out / "answers.json").write_text(json.dumps({"spent": spent, "rows": rows}, indent=1, default=str))
    print("answers: {}  spent: ${:.2f}".format(sum(1 for r in rows if "answer" in r), spent))
    return 0


if __name__ == "__main__":
    sys.exit(main())
