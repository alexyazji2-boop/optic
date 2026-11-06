"""A deterministic workload router, for measuring whether routing could work (Phase 13, directive 15 Part 8).

Analysis only. Nothing in the app routes: the directive says not to build the architecture before its value is shown,
and this is how its first question is answered. Can a question's workload be told from its words, its page and its
thread, before any model runs, accurately enough to send it somewhere cheaper?

`route(case)` uses only what production has before the model starts: the question, the earlier turns, the page
context, and Optic's own existing classifiers (the advice policy's request reader, the definition test and the
own-portfolio test in `app/main.py`). `evaluate()` scores it against the benchmark's labels, which the benchmark's
authors assigned, so "accuracy" is agreement with them, not ground truth.
"""
from __future__ import annotations

import re
import time
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

_INJECT = re.compile(r"\b(ignore (?:all |your |the )?(?:previous |prior )?(?:instructions|rules)|system prompt|developer mode|"
                     r"no disclaimers|repeat (?:it|this|exactly)|api key|sk-ant)\b|!\[", re.I)
_NAV = re.compile(r"\b(?:how do i|where (?:do|can|are) (?:i|my)|can milo|how can i|where is|where are)\b", re.I)
_NAV_OBJ = re.compile(r"\b(?:watchlist|alert|knowledge level|level|settings|export|link|brokerage|saved|tab|page|pdf|trade for me|"
                      r"place a trade|optic score)\b", re.I)
_TECH = re.compile(r"\b(?:rsi|macd|moving average|200-day|50-day|support|resistance|trend|chart|bollinger|indicator|"
                   r"volatil\w*|levels?|crossover|overbought|oversold)\b", re.I)
_FUND = re.compile(r"\b(?:revenue|eps|earnings per share|margins?|profit\w*|cash flow|debt|filings?|10-k|10-q|sec|valuation|"
                   r"p/e|dcf|business|fundamentals?|return on capital|cheap|expensive)\b", re.I)
_MULTI = re.compile(r"\b(?:compare|decompose|framework|reverse dcf|walk me through|across the|how much of the price)\b", re.I)
_PAGE = re.compile(r"\b(?:this page|on (?:this|the) page|on screen|summari[sz]e|the overview|here|this chart|my screen|"
                   r"am i researching)\b", re.I)
_MISSING = re.compile(r"\b(?:order book|trade tape|level 2|dark pool prints)\b", re.I)
_MARKET = re.compile(r"\b(?:trading at|price of|how is .{0,30}doing|today|this week|over the last|last month|"
                     r"the market|happened|right now)\b|\$[A-Z]{1,5}\b|\b[A-Z]{2,5}\b", 0)
DOSSIER_VIEWS = {"overview", "chart", "swing", "long", "earnings", "news", "financials"}


def route(case: Dict[str, Any], named: Dict[str, Any] = None) -> str:
    """The workload id this question would be routed as. `named` is what the server finds in the question before the
    model runs (`main._named_and_unknown`: the symbols it names and ticker-like words no directory knows); without
    it "What is AAPL at?" reads as a definition, which production never does."""
    from app import ai_policy
    import app.main as m
    q = case["question"]
    named = named or {}
    ctx = case.get("context") or {}
    view = ((ctx.get("focus") or {}).get("view")) or ctx.get("view")
    if ai_policy.classify_request(q):
        return "S1"
    if _INJECT.search(q) or any(_INJECT.search(str(t.get("content", ""))) for t in case.get("history") or [] if isinstance(t, dict)):
        return "S2"
    if case.get("history"):
        return "W8"
    if m._asks_about_own_portfolio({"role": "user", "content": q}) or view in ("brokerage", "paper"):
        return "W6"
    if _NAV.search(q) and _NAV_OBJ.search(q):
        return "W9"
    if m._is_definition(q, {"question_named": named}):
        return "W1"
    if _MISSING.search(q):
        return "W10"
    if _MULTI.search(q):
        return "W7"
    if _PAGE.search(q) and view in DOSSIER_VIEWS:
        return "W5"
    if _TECH.search(q):
        return "W4"
    if _FUND.search(q):
        return "W3"
    return "W2"


def evaluate(cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Agreement with the benchmark's workload labels, per workload, with the confusion and the time per decision."""
    from tests.milo_eval import harness
    confusion: Dict[str, Counter] = defaultdict(Counter)
    spent = 0.0
    for c in cases:
        with harness.world(c.get("user"), c.get("world")) as m:      # the fixture directory, so no network
            t0 = time.perf_counter()
            symbols, unknown = m._named_and_unknown(c["question"])
            confusion[c["workload"]][route(c, {"symbols": symbols, "unknown": unknown})] += 1
            spent += time.perf_counter() - t0
    per = spent / max(1, len(cases))
    rows = {}
    for w, got in sorted(confusion.items()):
        n = sum(got.values())
        rows[w] = {"cases": n, "routed_right": got[w], "share": round(got[w] / n, 3), "routed_as": dict(got)}
    right = sum(r["routed_right"] for r in rows.values())
    return {"cases": len(cases), "routed_right": right, "accuracy": round(right / max(1, len(cases)), 3),
            "seconds_per_decision": per, "by_workload": rows}


# The directive's example architecture (Part 8) as models, to price it, not to recommend it: definitions, navigation
# and routine market data to the small fast model, multi-source research to the larger one, everything else and every
# safeguard case to today's model. `deterministic` routes answer without a model (a help index Optic does not have).
EXAMPLE_ROUTES = {"W1": "claude-haiku-5-5", "W9": "claude-haiku-5-5", "W2": "claude-haiku-5-5", "W7": "claude-opus-5-5"}
DEFAULT_MODEL = "claude-sonnet-5-5"
HIGH_RISK = ("W2", "W6", "W10", "S1", "S2")


def routed_month(confusion: Dict[str, Dict[str, int]], routes: Dict[str, str], mau: int, served_cap: Optional[int] = 300,
                 c1: bool = False, deterministic: Tuple[str, ...] = (), mix: Optional[Dict[str, float]] = None,
                 sizes: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Milo chat's month when each question goes to the model of the route it is sent to.

    `confusion` is where the router sends each workload's questions (`evaluate()["by_workload"][w]["routed_as"]`); a
    perfect router is `{w: {w: 1} for w in mix}`. A question keeps the shape of its own workload (the work is the
    same) and pays the price of its route's model. Each model keeps its own cache, so the warm share is worked out
    from that model's own share of the questions: splitting traffic costs cache hits.
    """
    from tests.milo_eval import cost_model as CM
    mix = mix or CM.MIX
    sizes = sizes or CM.measured_sizes()
    asked = mau * CM.VOLUME["ask_share"] * CM.VOLUME["per_asker"]
    served = min(asked, served_cap) if served_cap else asked
    flows = []                                        # (own workload, route, share of chat questions)
    for w, share in mix.items():
        got = confusion.get(w) or {w: 1}
        n = sum(got.values())
        flows += [(w, r, share * k / n) for r, k in got.items()]
    model_of = lambda r: None if r in deterministic else routes.get(r, DEFAULT_MODEL)
    volume: Dict[str, float] = {}
    for w, r, s in flows:
        if model_of(r):
            volume[model_of(r)] = volume.get(model_of(r), 0.0) + s
    per_question, exposure, risky = 0.0, 0.0, 0.0
    for w, r, s in flows:
        model = model_of(r)
        if model:
            life = (CM.price_on(model) or {}).get("cache_life_minutes")
            cost = CM.workload_cost(w, model, CM.warm_share(served * volume[model], life), c1, sizes)
            if cost is None:
                return {"priced": False, "model": model}
            per_question += s * cost
        if model != model_of(w):                      # answered by a model its own workload's route would not use
            exposure += s
            if w in HIGH_RISK:
                risky += s
    chats = served * CM.VOLUME["days"] * CM.VOLUME["chat_share"]
    per_question *= 1 + CM.REPEATED
    return {"priced": True, "served_a_day": served, "per_question": round(per_question, 4),
            "dollars": round(chats * per_question, 2), "model_share": {m: round(v, 3) for m, v in sorted(volume.items())},
            "misrouted_share": round(exposure, 3), "misrouted_high_risk_share": round(risky, 3)}


def cheap_route_errors(cases: List[Dict[str, Any]], cheap=("W1", "W9")) -> List[Tuple[str, str, str]]:
    """The cases a cheap-model route would take that are not cheap workloads: what routing would get wrong first."""
    from tests.milo_eval import harness
    out = []
    for c in cases:
        with harness.world(c.get("user"), c.get("world")) as m:
            symbols, unknown = m._named_and_unknown(c["question"])
        if route(c, {"symbols": symbols, "unknown": unknown}) in cheap and c["workload"] not in cheap:
            out.append((c["id"], c["workload"], c["question"]))
    return out


# What MILO_ROUTING_RECOMMENDATION.md compares, all on the measured router unless named "perfect".
SCENARIOS = {
    "one model (Sonnet 5.5, as built)": ({}, False, ()),
    "one model, CONTEXT cached (C1)": ({}, True, ()),
    "definitions and help to Haiku 5.5": ({"W1": "claude-haiku-5-5", "W9": "claude-haiku-5-5"}, False, ()),
    "definitions to Haiku 5.5, help answered without a model": ({"W1": "claude-haiku-5-5"}, False, ("W9",)),
    "the directive's example": (EXAMPLE_ROUTES, False, ()),
    "the directive's example, perfect router": (EXAMPLE_ROUTES, False, ()),
    "the directive's example with C1": (EXAMPLE_ROUTES, True, ()),
    "definitions and help to Haiku 5.5, with C1": ({"W1": "claude-haiku-5-5", "W9": "claude-haiku-5-5"}, True, ()),
    "every question to Haiku 5.5 (the bound if one cheap model qualified)": ({w: "claude-haiku-5-5" for w in
                                                                              ("W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8",
                                                                               "W9", "W10", "S1", "S2")}, False, ()),
}


def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    import json
    from pathlib import Path
    from tests.milo_eval import cost_model as CM
    from tests.milo_eval.cases import CASES, BENCH_VERSION
    ap = argparse.ArgumentParser(description="Score the router and price the routing scenarios (no network, no model).")
    ap.add_argument("--out", default="docs/ai/eval-results/routing")
    a = ap.parse_args(argv)
    ev = evaluate(CASES)
    measured = {w: row["routed_as"] for w, row in ev["by_workload"].items()}
    perfect = {w: {w: 1} for w in CM.MIX}
    sizes = CM.measured_sizes()
    scenarios = {}
    for name, (routes, c1, det) in SCENARIOS.items():
        conf = perfect if "perfect" in name else measured
        scenarios[name] = {str(mau): {"at_ceiling": routed_month(conf, routes, mau, 300, c1, det, sizes=sizes),
                                      "demand_served": routed_month(conf, routes, mau, None, c1, det, sizes=sizes)}
                           for mau in CM.MAU}
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "routing.json").write_text(json.dumps({"benchmark": BENCH_VERSION, "evaluation": ev,
                                                  "cheap_route_errors": cheap_route_errors(CASES),
                                                  "scenarios": scenarios, "mix": CM.MIX}, indent=1, sort_keys=True) + "\n")
    print("router: {} of {} routed as labelled ({:.1%}), {:.3f} ms a decision".format(
        ev["routed_right"], ev["cases"], ev["accuracy"], 1000 * ev["seconds_per_decision"]))
    for name, row in scenarios.items():
        print("{:<72} 1,000 MAU ${:>8,.0f}   10,000 served ${:>9,.0f}".format(name, row["1000"]["at_ceiling"]["dollars"],
                                                                            row["10000"]["demand_served"]["dollars"]))
    print("wrote", out / "routing.json")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
