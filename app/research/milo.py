"""How Milo uses the research framework: one block per mode, and a compact
copy of the framework's output for CONTEXT.

The blocks change which evidence leads and in what order, never the figures.
Each is short on purpose: the base prompt already carries the reasoning
standards, and a long block per mode would bury them. Only the block for the
question's mode is sent.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

COMMON = (
    "## The research framework\n"
    "CONTEXT has `framework`: Optic's deterministic assessment for this question ({mode}). Its grades and labels "
    "come from stated rules (`framework.policy`); quote them, name the rule that capped a grade, and never "
    "regrade, round up or invent a grade it does not give. Insufficient Data means the evidence is missing, which "
    "is different from an unfavourable view: say which input is missing. Keep the judgments apart: business "
    "quality, valuation, the swing setup, earnings expectations and event risk are separate questions, and when "
    "two disagree, say in plain English why they can (different horizons, different things measured). Explain the "
    "mechanism behind a figure, not only the figure: why returns above the cost of capital matter, why cash "
    "falling short of profit is a question, why a beat can still fall. Tag figures from it as [[src framework]]."
)

DEPTH = {
    "quick": "This is a short question: answer it in a few sentences from the part of `framework` it asks about, "
             "not as a report.",
    "full": "Cover the mode's parts in that order, a sentence or two each, in about 450 words at most; the reader "
            "can ask for more on any part. Shortening never drops the main thing against the view or what would "
            "change it.",
}

MODES: Dict[str, str] = {
    "long_term": (
        "Long-term mode. Lead with the conviction label, then business quality and valuation as two grades, each "
        "with its strongest and weakest measure. Quality comes before any talk of buying. Then the chart as "
        "context, kept apart from the business: a broken trend is technical weakness, not by itself a failed "
        "thesis. Give the bull and bear case and the two ways this could lose money over three years "
        "(`loss_paths`, with their numbers). The moat measures are traces in the accounts; name the advantage "
        "itself only from a cited source, or say the data does not establish it. Accumulation zones only when "
        "`accumulation.offered` is true, as conditional levels to reassess at, never targets or allocations."
    ),
    "swing": (
        "Swing mode. Before any grade, give the strongest specific reasons to skip the trade from "
        "`swing.objections`, the most damaging first, and only those the data shows. Then the grade and why, and "
        "for a defined setup: the entry zone, the confirmation, the structural invalidation (and whether the stop "
        "was widened to the ATR floor), the targets and their basis, reward-to-risk with its formula and "
        "sensitivity range, the holding estimate, earnings exposure and the time-based reassessment. RSI is the "
        "stock against its own recent moves; relative strength is the stock against the market; never treat one "
        "as the other. Sizing arithmetic only as an illustration, with the gap caveat. Grades are framework rules, "
        "not probabilities. For No Setup, say what observable change would warrant another look (`reassess_when`)."
    ),
    "pre_earnings": (
        "Pre-earnings mode. Give the strongest view the evidence supports, starting \"My best-supported "
        "pre-earnings view is ... because ...\" (`earnings.pre.view`). Then the three predictions separately, "
        "results, guidance and the stock's reaction, each with its own confidence; a likely beat is not a bullish "
        "price call. Set out the expectations hurdle (consensus, revisions, the beat record, the run-up, the "
        "multiple) and keep company guidance apart from analyst consensus. Options: the priced move with its "
        "method and horizon, and say whether it isolates the release. News: official disclosure, reporting, "
        "analyst opinion and rumour are different weights, and one story repeated is one story. Then base, bull "
        "and bear cases, the figures that will decide the reaction, what would invalidate the view, and why a "
        "correct direction can still lose money in options. No probabilities (none is validated yet), no exact "
        "post-earnings prices, no whisper numbers. Where evidence is mixed, say so and explain the uncertainty."
    ),
    "post_earnings": (
        "Post-earnings mode. Audit the headline like for like: actual against the estimate on the same basis "
        "(adjusted against GAAP, any basis warning), guidance against prior guidance where a source has it. Then "
        "the reaction, saying whether it is after-hours, intraday or a completed session; separate what is "
        "verified from plausible explanations, and never say price or volume proves institutional buying or "
        "selling. Grade the report (`post.quality`) apart from the stock's move. Positives, weaknesses and real "
        "red flags; \"none found within the reviewed evidence\" when that is the answer. If `forecast_review` "
        "exists, quote what the saved forecast said and when, score results, guidance and reaction separately, and "
        "never rewrite the earlier reasoning. Finish with the next-quarter evidence and the near-term condition to "
        "watch."
    ),
    "combined": (
        "Combined mode. Each assessment on its own first, in a short paragraph (long term, swing, earnings), then "
        "where they agree or disagree and why (`combined.verdict`), then the one thing most worth watching."
    ),
    "unclear": (
        "The question asks whether to buy or sell without a timeframe, and the answer differs for a trade and an "
        "investment. Give a two-line read for each from the data you have, or ask one short question about the "
        "horizon; do not pick one silently."
    ),
}

SCREENSHOT_ONLY = (
    "## A screenshot is the evidence\n"
    "The reader sent an image and CONTEXT has no structured data for it. Read levels off the image as approximate "
    "zones (\"around 180\"), indicator values as estimates, and describe only the history the image shows. Say "
    "what the picture cannot show (volume you cannot read, the timeframe if unlabelled, anything off the edge) and "
    "that loading the symbol would give exact figures."
)

SCREENSHOT_WITH_DATA = (
    "The reader also sent an image. Prefer CONTEXT's figures to readings off the picture, and say so when the two "
    "disagree."
)


def prompt(routing: Optional[Dict[str, Any]], has_framework: bool, has_image: bool = False,
           has_structured: bool = False) -> str:
    parts: List[str] = []
    mode = (routing or {}).get("mode")
    if has_framework and mode in MODES and mode != "unclear":
        parts.append(COMMON.format(mode=mode.replace("_", " ")))
        parts.append(MODES[mode])
        d = DEPTH.get((routing or {}).get("depth") or "full")
        if d:
            parts.append(d)
    elif mode == "unclear":
        parts.append(MODES["unclear"])
    if has_image:
        parts.append(SCREENSHOT_WITH_DATA if has_structured else SCREENSHOT_ONLY)
    return "\n".join(parts)


# ---------------------------------------------------------------- compaction

def _pick(d: Optional[Dict[str, Any]], *keys: str) -> Dict[str, Any]:
    return {k: d.get(k) for k in keys if d and d.get(k) is not None}


def _components(cs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for c in cs or []:
        row = _pick(c, "id", "label", "status", "score", "grade")
        row["says"] = c.get("headline") if c.get("status") == "scored" else c.get("reason")
        figs = c.get("figures") or {}
        small = {k: v for k, v in figs.items() if isinstance(v, (int, float, str, bool)) and v is not None}
        if small:
            row["figures"] = small
        if c.get("id") in ("margins", "cash", "durability", "health") and c.get("evidence"):
            row["evidence"] = c["evidence"][-3:]
        src = (c.get("sources") or [])[:1]
        if src:
            row["source"] = _pick(src[0], "period", "form", "url")
        out.append(row)
    return out


def compact(out: Dict[str, Any], routing: Dict[str, Any]) -> Dict[str, Any]:
    c: Dict[str, Any] = {"routing": _pick(routing, "mode", "source", "depth", "why"),
                         "ticker": out.get("ticker"), "generated_at": out.get("generated_at"),
                         "method_version": out.get("method_version"),
                         "policy": out.get("policy"),
                         "freshness": _pick(out.get("freshness"), "state", "text", "phase")}
    lt = out.get("long_term")
    if lt:
        c["long_term"] = {
            "conviction": lt.get("conviction"),
            "business_type": lt.get("business_type_label") or lt.get("business_type"),
            "quality": dict(_pick(lt.get("quality"), "grade", "score", "status", "summary", "reason"),
                            components=_components((lt.get("quality") or {}).get("components")),
                            rule_of_40=(lt.get("quality") or {}).get("rule_of_40")),
            "valuation": dict(_pick(lt.get("valuation"), "label", "score", "status", "summary", "reason"),
                              components=_components((lt.get("valuation") or {}).get("components"))),
            "chart": lt.get("chart"), "accumulation": lt.get("accumulation"), "scenarios": lt.get("scenarios"),
            "loss_paths": lt.get("loss_paths"), "policy_note": lt.get("policy_note"),
        } if lt.get("available") else {"available": False, "conviction": lt.get("conviction")}
    sw = out.get("swing")
    if sw:
        rd = sw.get("readings") or {}
        plan = sw.get("plan") or {}
        c["swing"] = {
            "grade": sw.get("grade"), "why": sw.get("why"), "rules": sw.get("rules"),
            "most_damaging": (sw.get("most_damaging") or {}).get("text"),
            "objections": [{"severity": o["severity"], "text": o["text"]}
                           for o in sorted(sw.get("objections") or [], key=lambda o: -o["severity"])],
            "setup": _pick(sw.get("setup"), "kind", "side", "why"),
            "readings": _pick(rd, "as_of", "spot", "ema20", "ema50", "sma200", "rsi14", "macd_hist",
                              "macd_hist_rising", "atr14", "atr_pct", "relative_volume", "daily_trend",
                              "weekly_trend", "aligned", "relative_strength", "benchmark", "high_252"),
            "plan": dict(_pick(plan, "side", "kind", "entry", "entry_zone", "confirmation", "targets",
                               "target_basis", "obstacles", "reward_to_risk", "reward_to_risk_t2", "rr_formula",
                               "reassess"),
                         invalidation=_pick(plan.get("invalidation"), "price", "basis", "widened", "structure", "note"),
                         sensitivity=_pick(plan.get("sensitivity"), "low", "high", "representative"),
                         holding=_pick(plan.get("holding"), "days", "basis"),
                         earnings=_pick(plan.get("earnings"), "date", "confirmed", "in_window", "text"),
                         sizing_example=_pick(plan.get("sizing_example"), "label", "shares", "risk_per_share",
                                              "planned_loss", "gap_note")) if plan else None,
            "reassess_when": sw.get("reassess_when"), "framework_note": sw.get("framework_note"),
        }
    er = out.get("earnings")
    if er:
        e: Dict[str, Any] = {"which": er.get("which"), "next_report": er.get("next_report")}
        pre, post = er.get("pre"), er.get("post")
        if pre:
            if pre.get("available"):
                preds = pre.get("predictions") or {}
                e["pre"] = {
                    "release": pre.get("release"), "consensus": pre.get("consensus"),
                    "revisions": _pick(pre.get("revisions"), "direction", "drift_90d_pct", "analysts_up_30d",
                                       "analysts_down_30d"),
                    "surprise_history": pre.get("surprise_history"),
                    "trajectory": _pick(pre.get("trajectory"), "revenue_trend", "revenue_trend_text", "operating_margin",
                                        "revenue_yoy"),
                    "run_up": pre.get("run_up"),
                    "hurdle": {"state": (pre.get("hurdle") or {}).get("state"), "text": (pre.get("hurdle") or {}).get("text"),
                               "points": [p["text"] for p in (pre.get("hurdle") or {}).get("points") or []],
                               "consensus_growth": (pre.get("hurdle") or {}).get("consensus_growth")},
                    "options": _pick(pre.get("options"), "available", "reason", "expiry", "dte", "expiry_move_pct",
                                     "expiry_move_method", "event_isolated", "event_move_pct", "event_note", "range",
                                     "pricing_vs_history", "caveats"),
                    "news": [_pick(s, "title", "kind", "bears_on", "outlet_count", "published")
                             for s in ((pre.get("news") or {}).get("stories") or [])[:6]],
                    "predictions": {k: {"lean": v.get("lean"), "confidence": v.get("confidence"),
                                        "evidence": [x["text"] for x in v.get("evidence") or []],
                                        "gaps": v.get("gaps"), "basis_warning": v.get("basis_warning")}
                                    for k, v in preds.items()},
                    "view": pre.get("view"), "not_available": pre.get("not_available"),
                    "saved": pre.get("saved"),
                }
            else:
                e["pre"] = {"available": False, "reason": pre.get("reason")}
        if post:
            e["post"] = ({k: post.get(k) for k in ("release", "headline_audit", "reaction", "quality", "positives",
                                                   "weaknesses", "red_flags", "forecast_review", "next_quarter",
                                                   "separation_note")}
                         | {"trajectory": _pick(post.get("trajectory"), "revenue_trend", "revenue_trend_text",
                                                "operating_margin")}
                         if post.get("available") else {"available": False, "reason": post.get("reason")})
        if not er.get("pre") and not er.get("post"):
            e["available"] = er.get("available", False)
            e["reason"] = er.get("reason")
        c["earnings"] = e
    if out.get("combined"):
        c["combined"] = out["combined"]
    c["limitations"] = out.get("limitations")
    gaps = (out.get("data") or {}).get("gaps")
    if gaps:
        c["gaps"] = gaps
    return c
