"""What a Milo question costs, by workload and model, and what Milo costs a month (Phase 13, directive 15 Part 7).

A model of the bill, not a measurement of it. There is no usage ledger to read locally and no working key
(BLOCKERS BL-01), so every figure comes from three inputs, each labelled where it is used:

- **What Optic sends**, measured from the code today: the cached system block and the tool definitions exactly as
  `build_chat_request` and the toolbox produce them. Characters become tokens at the cost audit's assumed 4 a token
  for prose and 3.5 for JSON (COST_AUDIT section 4.3). That ratio is an ASSUMPTION and the largest single
  uncertainty here: the token-counting endpoint, which is free, settles it once a key works.
- **The shape of each workload's answer** (model calls, tool results, output), from the cost audit's typical and
  light questions (section 4.4), labelled ASSUMPTION. Which shape a workload takes follows the tools its benchmark
  cases need.
- **List prices** from `prices.json`, read from each provider's own page. A model without a listed price is not
  costed; nothing is guessed.

The check on the arithmetic: with the audit's 16,300-token prefix, Sonnet 5.5's typical question comes out at the
audit's $0.14 warm, $0.18 cold and $0.10 with the CONTEXT turn cached (C1), and its monthly chat lines match
(tests/test_milo_cost_model.py).

    .venv/bin/python -m tests.milo_eval.cost_model --out docs/ai/eval-results/cost-model
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from tests.milo_eval import compare as CMP

CHARS_PER_TOKEN = {"prose": 4.0, "json": 3.5}          # ASSUMPTION (COST_AUDIT 4.3); not counted, BL-01
TOOL_SYSTEM_TOKENS = 286                                 # Anthropic's tool-use system prompt, Sonnet 5.5, auto (pricing page)

# Per question, whatever the workload (COST_AUDIT 4.4): the level, horizon, framework and lens blocks after the
# breakpoint, the question, the assistant content (thinking and tool calls) carried into each later round and billed
# as input, and the output of a round that only calls tools.
COMMON = {"blocks": 500, "question": 50, "carried": 800, "out_tool": 800}

# The shape of an answer. `rounds` is the chance each model call happens (the first always); `results` the tokens of
# tool results each tool round adds; `out_answer` the output of the answering round, thinking included. ASSUMPTION:
# "typical" and "light" are the audit's; the others change one thing each, said beside it.
SHAPES: Dict[str, Dict[str, Any]] = {
    "light": {"rounds": [1.0], "context": 2_300, "history": 0, "results": [], "out_answer": 1_000, "tools": 16,
              "why": "a definition or a help question: no tool, a small page context (the audit's light question)"},
    "typical": {"rounds": [1.0, 1.0, 0.5], "context": 15_700, "history": 1_000, "results": [3_400, 1_700],
                "out_answer": 2_000, "tools": 16, "why": "a Dossier question with one or two tool rounds (the audit's typical)"},
    "thread": {"rounds": [1.0, 1.0, 0.5], "context": 15_700, "history": 4_000, "results": [3_400, 1_700],
               "out_answer": 2_000, "tools": 16, "why": "typical, with three earlier turns in the history"},
    "portfolio": {"rounds": [1.0, 1.0, 0.5], "context": 19_700, "history": 1_000, "results": [3_400, 1_700],
                  "out_answer": 2_000, "tools": 17, "why": "typical, plus the linked-portfolio block and the portfolio tool"},
    "research": {"rounds": [1.0, 1.0, 1.0, 0.5], "context": 15_700, "history": 1_000, "results": [3_400, 3_400, 1_700],
                 "out_answer": 2_500, "tools": 16, "why": "typical, with a third tool round and a longer answer"},
}
SHAPE_OF = {"W1": "light", "W9": "light", "W2": "typical", "W3": "typical", "W4": "typical", "W5": "typical",
            "W10": "typical", "S1": "typical", "S2": "typical", "W8": "thread", "W6": "portfolio", "W7": "research"}

# The share of chat questions in each workload. ASSUMPTION: there is no traffic to count (the ledger records the
# kind of request, chat or research, not what was asked). It is a product guess, set before any model was priced, and
# section 4 of MILO_COST_ANALYSIS.md shows how the totals move when the light share doubles or halves.
MIX = {"W1": 0.12, "W2": 0.20, "W3": 0.10, "W4": 0.10, "W5": 0.12, "W6": 0.06, "W7": 0.06, "W8": 0.12, "W9": 0.04,
       "W10": 0.02, "S1": 0.05, "S2": 0.01}

# Monthly volume, the cost audit's assumptions A3 to A5: 10% of monthly actives ask on a given day, 2 questions
# each, 30.4 days, chat 85% of what is asked; the server-wide ceiling of 300 questions a day (MILO_QUESTIONS_PER_DAY).
VOLUME = {"ask_share": 0.10, "per_asker": 2, "days": 30.4, "chat_share": 0.85, "ceiling": 300,
          "active_hours": 14, "cache_life_minutes": 5, "prefix_variants": 1.5}
# Answers paid for twice: a stream cut and asked again, a refusal re-run under the fallback model, a server error after
# partial output. ASSUMPTION, not measured: the ledger skips a round the reader cancels (COST_AUDIT C2).
REPEATED = 0.02
MAU = (100, 1_000, 10_000)
# Prices are those in force on this date: the earliest a change of model could reach readers after the evaluation,
# the owner's approval and the privacy review it needs. Two Gemini prices double before it (prices.json `changes`).
PLAN_DATE = "2027-01-01"


def prefix_tokens(tools: int = 16, system_chars: Optional[int] = None, tool_chars: Optional[int] = None) -> int:
    """The cached prefix (tool definitions, then the system block) in tokens, from the code's own sizes."""
    if system_chars is None or tool_chars is None:
        sizes = measured_sizes()
        system_chars = sizes["system_chars"] if system_chars is None else system_chars
        tool_chars = sizes["tool_chars"][str(tools)] if tool_chars is None else tool_chars
    return round(system_chars / CHARS_PER_TOKEN["prose"] + tool_chars / CHARS_PER_TOKEN["json"]) + TOOL_SYSTEM_TOKENS


def measured_sizes() -> Dict[str, Any]:
    """Characters of the chat system block and of the tool definitions as the toolbox offers them."""
    from app import ai, ai_policy, editorial, milo_tools
    system = ai.SYSTEM_PROMPT + ai.FORMAT_PROMPT + "\n\n" + editorial.WRITING_RULES + "\n\n" + ai_policy.POLICY_TEXT
    every = milo_tools.definitions()          # as a streamed request carries them
    without = [d for d in every if d["name"] != "get_my_portfolio"]
    return {"system_chars": len(system), "tool_chars": {"17": len(json.dumps(every)), "16": len(json.dumps(without))}}


def price_on(model: str, on: Optional[str] = PLAN_DATE) -> Optional[Dict[str, Any]]:
    """The model's listed prices as they stand on `on` (an ISO date; None for today's), or None when not listed."""
    price = CMP.price_of(model)
    if not price:
        return None
    price = dict(price)
    for change in sorted(price.pop("changes", []), key=lambda c: c["from"]):
        if on and change["from"] <= on:
            price.update({k: v for k, v in change.items() if k != "from"})
    return price


def _tier(price: Dict[str, Any], prompt: float) -> Optional[Dict[str, Any]]:
    """The price row that applies to a call of `prompt` tokens; None when its tier lists no price."""
    for tier in sorted(price.get("tiers", []), key=lambda t: -t["above"]):
        if prompt > tier["above"]:
            return {**price, **tier} if all(k in tier for k in ("input", "output")) else None
    return price


def question_cost(shape: Dict[str, Any], price: Dict[str, Any], prefix: int, warm: float, c1: bool = False) -> Optional[Dict[str, float]]:
    """Expected dollars for one question of `shape`, and its expected tokens.

    `warm` is the chance the first call finds the prefix in the cache. How the rest is billed follows the provider:
    "explicit" (Anthropic) writes the prefix at the write price and reads it later in the answer; only what carries a
    breakpoint is cached, so the CONTEXT turn is paid at the full input price on every round unless `c1` marks it too.
    "implicit-latest" (OpenAI's GPT-6 models) is "explicit" with the latest message always marked as well, at the
    provider's write price. "implicit" (Gemini, the open-weight hosts) has no write price and reads any prefix it has
    seen, so a later round reads everything the round before it sent. "none" pays the full input price for every token.
    """
    mode = price.get("cache", "none")
    if mode == "implicit-latest":
        mode, c1 = "explicit", True
    after = COMMON["blocks"] + shape["context"] + shape["history"] + COMMON["question"]
    rounds, results = shape["rounds"], shape["results"]
    dollars, tokens = 0.0, {"input": 0.0, "cached_input": 0.0, "cache_write": 0.0, "output": 0.0}
    sent = after                      # what follows the prefix in this round's request
    for r, p in enumerate(rounds):
        if r:
            sent += COMMON["carried"] + results[r - 1]
        nxt = rounds[r + 1] / p if r + 1 < len(rounds) else 0.0
        out = nxt * COMMON["out_tool"] + (1 - nxt) * shape["out_answer"]
        new = after if r == 0 else COMMON["carried"] + results[r - 1]
        if mode == "explicit":
            hit_prefix = warm if r == 0 else 1.0
            read = prefix * hit_prefix + ((sent - new) if c1 and r else 0)
            write = prefix * (1 - hit_prefix) + (new if c1 else 0)
            fresh = 0 if c1 else sent
        elif mode == "implicit":
            read = prefix * warm if r == 0 else prefix + sent - new
            write, fresh = 0.0, (prefix * (1 - warm) + sent) if r == 0 else new
        else:
            read, write, fresh = 0.0, 0.0, prefix + sent
        row = _tier(price, prefix + sent)
        if row is None:
            return None
        dollars += p * (fresh * row["input"] + read * row.get("cached_input", row["input"])
                        + write * row.get("cache_write", row["input"]) + out * row["output"]) / 1e6
        for k, v in (("input", fresh), ("cached_input", read), ("cache_write", write), ("output", out)):
            tokens[k] += p * v
    return {"dollars": dollars, "calls": sum(rounds), **{k: round(v) for k, v in tokens.items()}}


def warm_share(questions_a_day: float, life_minutes: Optional[float] = None) -> float:
    """The chance a question's first call finds the prefix cached: Poisson arrivals over the active hours, one cache
    life of memory, the prefix split between its variants (web search on or off, the portfolio tool or not). A
    provider that states no lifetime (Gemini's implicit cache, the open-weight hosts) is given Anthropic's 5 minutes."""
    windows = VOLUME["active_hours"] * 60 / (life_minutes or VOLUME["cache_life_minutes"])
    return 1 - math.exp(-questions_a_day / windows / VOLUME["prefix_variants"])


def workload_cost(workload: str, model: str, warm: float, c1: bool = False,
                  sizes: Optional[Dict[str, Any]] = None, on: Optional[str] = PLAN_DATE) -> Optional[float]:
    """Dollars for one question of `workload` answered by `model`, or None when the model has no listed price."""
    price = price_on(model, on)
    if not price:
        return None
    sizes = sizes or measured_sizes()
    shape = SHAPES[SHAPE_OF[workload]]
    got = question_cost(shape, price, prefix_tokens(shape["tools"], sizes["system_chars"], sizes["tool_chars"][str(shape["tools"])]), warm, c1)
    return None if got is None else got["dollars"]


def mixed_cost(model: str, warm: float, c1: bool = False, mix: Optional[Dict[str, float]] = None,
               sizes: Optional[Dict[str, Any]] = None, on: Optional[str] = PLAN_DATE) -> Optional[float]:
    """Dollars for the average chat question at this warm share, or None when the model has no listed price."""
    sizes = sizes or measured_sizes()
    total = 0.0
    for w, share in (mix or MIX).items():
        got = workload_cost(w, model, warm, c1, sizes, on)
        if got is None:
            return None
        total += share * got
    return total


def monthly(model: str, mau: int, served_cap: Optional[int] = VOLUME["ceiling"], c1: bool = False,
            mix: Optional[Dict[str, float]] = None, sizes: Optional[Dict[str, Any]] = None,
            on: Optional[str] = PLAN_DATE) -> Optional[Dict[str, float]]:
    """Milo chat's month at `mau` monthly actives. `served_cap` None serves every question asked."""
    price = price_on(model, on)
    if not price:
        return None
    asked = mau * VOLUME["ask_share"] * VOLUME["per_asker"]
    served = min(asked, served_cap) if served_cap else asked
    warm = warm_share(served, price.get("cache_life_minutes"))
    per = mixed_cost(model, warm, c1, mix, sizes, on)
    if per is None:
        return None
    chats = served * VOLUME["days"] * VOLUME["chat_share"]
    return {"asked_a_day": asked, "served_a_day": served, "warm_share": round(warm, 3), "chat_questions": round(chats),
            "per_question": round(per * (1 + REPEATED), 4), "dollars": round(chats * per * (1 + REPEATED), 2)}


def table(models: List[str], sizes: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Everything the cost analysis prints, for each model with a listed price."""
    sizes = sizes or measured_sizes()
    out: Dict[str, Any] = {"assumptions": {"chars_per_token": CHARS_PER_TOKEN, "common": COMMON,
                                           "shapes": SHAPES, "shape_of": SHAPE_OF, "mix": MIX, "volume": VOLUME,
                                           "repeated": REPEATED},
                           "sizes": sizes, "prefix_tokens": {t: prefix_tokens(t, sizes["system_chars"], sizes["tool_chars"][str(t)]) for t in (16, 17)},
                           "models": {}}
    for model in models:
        price = price_on(model)
        if not price:
            out["models"][model] = {"priced": False}
            continue
        per_w = {}
        for w in MIX:
            shape = SHAPES[SHAPE_OF[w]]
            pre = out["prefix_tokens"][shape["tools"]]
            per_w[w] = {"cold": question_cost(shape, price, pre, 0.0), "warm": question_cost(shape, price, pre, 1.0)}
            if price.get("cache") == "explicit":
                per_w[w]["warm_c1"] = question_cost(shape, price, pre, 1.0, c1=True)
        months = {}
        for mau in MAU:
            months[str(mau)] = {"at_ceiling": monthly(model, mau, sizes=sizes), "demand_served": monthly(model, mau, None, sizes=sizes)}
            if price.get("cache") == "explicit":
                months[str(mau)]["at_ceiling_c1"] = monthly(model, mau, c1=True, sizes=sizes)
                months[str(mau)]["demand_served_c1"] = monthly(model, mau, None, c1=True, sizes=sizes)
        row = {"priced": True, "price": price, "price_date": PLAN_DATE, "per_workload": per_w, "monthly": months}
        if price != price_on(model, None):
            row["today"] = {"price": price_on(model, None), "monthly": {str(mau): monthly(model, mau, sizes=sizes, on=None) for mau in MAU}}
        out["models"][model] = row
    return out


def evaluation_budget(models: List[str], trials: int = 3) -> Dict[str, Any]:
    """What running the benchmark would cost each model at today's prices, as a range: the harness's own rule of thumb
    on the fixtures' request sizes (`compare.estimate`, which `--dry-run` prints), and this model's production-sized
    shapes with the cache warm, since a run asks its questions one after another. For the owner's approval of a cap."""
    from tests.milo_eval import harness
    from tests.milo_eval.cases import CASES
    chars = {c["id"]: harness.assemble(c)["input_chars"] for c in CASES}
    sizes = measured_sizes()
    gate = [c for c in CASES if c["workload"] in ("W2", "W6", "W10", "S1", "S2")]
    rows = {}
    for model in models:
        p = CMP.price_of(model)
        if not p:
            continue
        low = sum((chars[c["id"]] / 3.6 * 2 * p["input"] + 1200 * p["output"]) / 1e6 for c in CASES) * trials
        high = sum(workload_cost(c["workload"], model, 1.0, False, sizes, None) for c in CASES) * trials
        g = sum(workload_cost(c["workload"], model, 1.0, False, sizes, None) for c in gate) * trials
        rows[model] = {"benchmark_fixture_sizes": round(low, 2), "benchmark_production_sizes": round(high, 2),
                       "gate_set_production_sizes": round(g, 2)}
    return {"cases": len(CASES), "gate_cases": len(gate), "trials": trials, "models": rows}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model", action="append", help="a model id (repeatable); default every model in prices.json")
    ap.add_argument("--out", default="docs/ai/eval-results/cost-model")
    ap.add_argument("--budget", action="store_true", help="also price a 3-trial benchmark run per model (5 s, no network)")
    a = ap.parse_args(argv)
    models = a.model or sorted(json.loads(CMP.PRICES.read_text())["models"])
    got = table(models)
    if a.budget:
        got["evaluation_budget"] = evaluation_budget(models)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "cost-model.json").write_text(json.dumps(got, indent=1, sort_keys=True) + "\n")
    for model, row in got["models"].items():
        if not row["priced"]:
            print("{:<28} not priced".format(model))
            continue
        m = row["monthly"]
        print("{:<28} typical warm ${:.3f}  month 100: ${:,.0f}  1,000: ${:,.0f}  10,000 at ceiling: ${:,.0f}  served: ${:,.0f}".format(
            model, row["per_workload"]["W2"]["warm"]["dollars"], m["100"]["at_ceiling"]["dollars"], m["1000"]["at_ceiling"]["dollars"],
            m["10000"]["at_ceiling"]["dollars"], m["10000"]["demand_served"]["dollars"]))
    print("wrote", out / "cost-model.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
