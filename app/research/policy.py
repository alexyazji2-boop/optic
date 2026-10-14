"""Every threshold the framework grades with, as a named and configurable rule.

These are framework rules: choices about how strict the grading is. None of
them is an established probability or a measured edge, and the output says so
wherever one decides a grade. They are kept here, and not inline beside the
code that applies them, for three reasons:

* a reader (or Milo) can be told exactly which rule capped a grade, by name;
* the historical validation program can test each rule as a stated hypothesis;
* an operator can change one without editing analysis code. `OPTIC_RESEARCH_POLICY`
  takes a JSON object of {rule: value}; an unknown rule or a value of the wrong
  type is ignored and reported, never half-applied.

`status` says what kind of claim each rule is:
  framework       - a grading convention from the brief, not a measurement
  assumption      - a working value that still needs validation on our data
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple

POLICY_VERSION = "policy-2026-10-14"

RULES: Dict[str, Dict[str, Any]] = {
    # ------------------------------------------------------------ long term
    "quality_cap_grade": {
        "value": "B",
        "status": "framework",
        "text": "Business quality below this grade caps overall long-term conviction at Neutral.",
    },
    "quality_min_components": {
        "value": 4,
        "status": "framework",
        "text": "Fewer scored quality components than this is Insufficient Data, not a low grade.",
    },
    "leverage_max_net_debt_ebitda": {
        "value": 3.0,
        "status": "assumption",
        "text": "Net debt above this multiple of EBITDA counts against financial health "
                "(not applied to banks, insurers or REITs, whose debt is operating).",
    },
    "coverage_min_ebit_interest": {
        "value": 4.0,
        "status": "assumption",
        "text": "Operating income below this multiple of interest expense counts against financial health.",
    },
    "rule_of_40_min_growth": {
        "value": 0.15,
        "status": "framework",
        "text": "The Rule of 40 is applied only to companies growing revenue at least this fast, "
                "where trading margin for growth is the stated strategy.",
    },
    "cash_conversion_years": {
        "value": 3,
        "status": "framework",
        "text": "Operating cash flow is compared with net income over this many years before "
                "earnings are called low quality; one year's gap is a question, not a finding.",
    },
    # ---------------------------------------------------------------- swing
    "atr_stop_multiple": {
        "value": 1.5,
        "status": "assumption",
        "text": "A stop closer than this many daily ATRs to entry is flagged as inside ordinary "
                "noise. The stop is set at structural invalidation and widened to this distance "
                "when structure is closer; it is never tightened to improve reward-to-risk.",
    },
    "rr_s_min": {
        "value": 2.5,
        "status": "framework",
        "text": "Reward-to-risk needed for an S grade.",
    },
    "rr_avoid_below": {
        "value": 1.5,
        "status": "framework",
        "text": "Reward-to-risk below this is Avoid.",
    },
    "rr_cap_b_below": {
        "value": 2.0,
        "status": "framework",
        "text": "Reward-to-risk from the Avoid line up to this value caps the grade at B.",
    },
    "earnings_in_window_cap": {
        "value": "B",
        "status": "framework",
        "text": "An earnings release inside the holding window caps an ordinary swing grade at "
                "this, unless an event strategy is separately evaluated.",
    },
    "swing_holding_days_max": {
        "value": 20,
        "status": "framework",
        "text": "Longest holding window, in trading days, a swing plan is written for.",
    },
    "swing_min_bars": {
        "value": 220,
        "status": "framework",
        "text": "Daily bars needed to compute the 200-day average and grade a setup.",
    },
    "slippage_bps": {
        "value": 10,
        "status": "assumption",
        "text": "Slippage per side, in basis points, used in the reward-to-risk sensitivity.",
    },
    # ------------------------------------------------------------- earnings
    "inline_band_pct": {
        "value": 1.0,
        "status": "framework",
        "text": "A result within this percentage of consensus is in line, not a beat or a miss, "
                "so a marginal headline miss cannot override stronger underlying results.",
    },
    "pre_earnings_window_days": {
        "value": 21,
        "status": "framework",
        "text": "A confirmed or estimated release within this many calendar days makes "
                "pre-earnings analysis relevant by default.",
    },
    "post_earnings_window_days": {
        "value": 10,
        "status": "framework",
        "text": "A release within this many calendar days ago makes post-earnings analysis "
                "relevant by default.",
    },
    "quote_stale_minutes": {
        "value": 30,
        "status": "framework",
        "text": "A regular-session quote older than this is reported as stale.",
    },
}


def _coerce(name: str, value: Any) -> Tuple[bool, Any]:
    default = RULES[name]["value"]
    if isinstance(default, bool):
        return isinstance(value, bool), value
    if isinstance(default, (int, float)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return False, None
        return True, type(default)(value) if isinstance(default, int) and float(value).is_integer() else float(value)
    if isinstance(default, str):
        if not isinstance(value, str) or not value.strip():
            return False, None
        return True, value.strip()
    return False, None


def _from_env() -> Tuple[Dict[str, Any], List[str]]:
    raw = os.environ.get("OPTIC_RESEARCH_POLICY", "").strip()
    if not raw:
        return {}, []
    try:
        blob = json.loads(raw)
    except ValueError:
        return {}, ["OPTIC_RESEARCH_POLICY is not valid JSON; the default rules apply."]
    if not isinstance(blob, dict):
        return {}, ["OPTIC_RESEARCH_POLICY must be a JSON object; the default rules apply."]
    return blob, []


def current(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The rules in force: defaults, then the environment, then `overrides`.

    Returns {"version", "values": {rule: value}, "changed": [...], "ignored": [...]}.
    `changed` names every rule that differs from its default, so an output graded
    under a modified policy says so.
    """
    values = {k: v["value"] for k, v in RULES.items()}
    env, ignored = _from_env()
    changed: List[str] = []
    for source in (env, overrides or {}):
        for name, value in source.items():
            if name not in RULES:
                ignored.append("Unknown rule {!r} ignored.".format(name))
                continue
            ok, coerced = _coerce(name, value)
            if not ok:
                ignored.append("Rule {!r} needs a value like {!r}; ignored.".format(name, RULES[name]["value"]))
                continue
            values[name] = coerced
    for name, value in values.items():
        if value != RULES[name]["value"] and name not in changed:
            changed.append(name)
    version = POLICY_VERSION + ("+custom" if changed else "")
    return {"version": version, "values": values, "changed": changed, "ignored": ignored}


def describe(name: str, values: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """One rule as a reader-facing record: its name, value, status and text."""
    rule = RULES[name]
    value = (values or {}).get(name, rule["value"])
    return {"rule": name, "value": value, "status": rule["status"], "text": rule["text"]}


GRADE_ORDER = ["A", "B", "C", "D", "F"]


def grade_below(grade: Optional[str], floor: str) -> bool:
    """True when `grade` (A-F, plus/minus ignored) is strictly worse than `floor`."""
    if not grade:
        return False
    g, f = grade[0].upper(), floor[0].upper()
    if g not in GRADE_ORDER or f not in GRADE_ORDER:
        return False
    return GRADE_ORDER.index(g) > GRADE_ORDER.index(f)
