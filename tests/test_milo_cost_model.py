"""Milo's cost model and the routing arithmetic (tests/milo_eval/cost_model.py, router.py; Phase 13, 2026-11-02).

The check on the model is the 2026-10-30 cost audit: given the audit's own prefix size, it must reproduce the audit's
per-question and monthly figures for Sonnet 5.5, so the Phase 13 tables rest on arithmetic that was already reviewed.
The rest pins how each provider's cache is billed, the announced price changes, the long-prompt tiers, and that a
model without a listed price is never costed.
"""
from __future__ import annotations

import pytest

from tests.milo_eval import cost_model as CM
from tests.milo_eval import router as R

# COST_AUDIT section 4.3: the system block and the tool definitions measured on 2026-10-30, a 16,300-token prefix
AUDIT_SIZES = {"system_chars": 51_609, "tool_chars": {"16": 10_895, "17": 12_288}}


def _sonnet():
    return CM.price_on("claude-sonnet-5-5")


def test_the_model_reproduces_the_cost_audits_question():
    prefix = CM.prefix_tokens(16, AUDIT_SIZES["system_chars"], AUDIT_SIZES["tool_chars"]["16"])
    assert prefix == pytest.approx(16_300, abs=5)
    typical, light = CM.SHAPES["typical"], CM.SHAPES["light"]
    assert CM.question_cost(typical, _sonnet(), prefix, 1.0)["dollars"] == pytest.approx(0.14, abs=0.005)
    assert CM.question_cost(typical, _sonnet(), prefix, 0.0)["dollars"] == pytest.approx(0.18, abs=0.005)
    assert CM.question_cost(typical, _sonnet(), prefix, 1.0, c1=True)["dollars"] == pytest.approx(0.10, abs=0.005)
    assert CM.question_cost(typical, _sonnet(), prefix, 0.0, c1=True)["dollars"] == pytest.approx(0.13, abs=0.006)
    assert CM.question_cost(light, _sonnet(), prefix, 0.0)["dollars"] == pytest.approx(0.06, abs=0.005)
    assert CM.question_cost(light, _sonnet(), prefix, 1.0)["dollars"] == pytest.approx(0.02, abs=0.005)


def test_the_model_reproduces_the_cost_audits_months(monkeypatch):
    monkeypatch.setattr(CM, "REPEATED", 0.0)               # the audit counted no repeats
    every_typical = {"W2": 1.0}
    got = {mau: CM.monthly("claude-sonnet-5-5", mau, mix=every_typical, sizes=AUDIT_SIZES)["dollars"] for mau in CM.MAU}
    assert got[100] == pytest.approx(89.76, rel=0.01)
    assert got[1_000] == pytest.approx(802, rel=0.01)
    assert got[10_000] == pytest.approx(1_159, rel=0.01)  # at the 300-a-day ceiling
    served = CM.monthly("claude-sonnet-5-5", 10_000, served_cap=None, mix=every_typical, sizes=AUDIT_SIZES)["dollars"]
    assert served == pytest.approx(7_109, rel=0.01)
    assert [round(CM.warm_share(q), 2) for q in (20, 200, 300)] == [0.08, 0.55, 0.70]


def test_the_prefix_is_measured_from_the_code():
    from app import ai, ai_policy, editorial, milo_tools
    sizes = CM.measured_sizes()
    assert sizes["system_chars"] == len(ai.SYSTEM_PROMPT + ai.FORMAT_PROMPT + "\n\n" + editorial.WRITING_RULES + "\n\n" + ai_policy.POLICY_TEXT)
    assert int(sizes["tool_chars"]["17"]) > int(sizes["tool_chars"]["16"]) > 0
    assert len(milo_tools.definitions()) == 17


def test_openais_cache_bills_like_anthropics_with_the_context_turn_cached():
    shape, prefix = CM.SHAPES["typical"], 16_835
    sol = dict(_sonnet(), cache="implicit-latest")         # the same list prices, the other cache rule
    for warm in (0.0, 1.0):
        assert CM.question_cost(shape, sol, prefix, warm)["dollars"] == pytest.approx(
            CM.question_cost(shape, _sonnet(), prefix, warm, c1=True)["dollars"])


def test_an_implicit_cache_charges_no_write():
    shape, prefix = CM.SHAPES["typical"], 16_835
    flat = {"input": 1.0, "cached_input": 0.1, "output": 5.0, "cache": "implicit"}
    got = CM.question_cost(shape, flat, prefix, 0.0)
    assert got["cache_write"] == 0 and got["cached_input"] > 0
    none = CM.question_cost(shape, dict(flat, cache="none"), prefix, 0.0)
    assert none["cached_input"] == 0 and none["dollars"] > got["dollars"]


def test_announced_price_changes_apply_from_their_date():
    assert CM.price_on("gemini-4-argon", None)["input"] == 2.0
    assert CM.price_on("gemini-4-argon", "2026-11-30")["input"] == 2.0
    assert CM.price_on("gemini-4-argon", "2026-12-01")["input"] == 4.0
    assert CM.price_on("gemini-3.8-flash", CM.PLAN_DATE)["output"] == 7.5
    assert "changes" not in CM.price_on("gemini-4-argon")


def test_a_prompt_past_a_tier_pays_the_tiers_prices():
    haiku = CM.price_on("claude-haiku-5-5")
    small = dict(CM.SHAPES["light"], context=2_000)
    big = dict(CM.SHAPES["light"], context=150_000)
    a = CM.question_cost(small, haiku, 16_835, 0.0)
    b = CM.question_cost(big, haiku, 16_835, 0.0)
    # the big prompt pays $0.50 a million on its fresh input, not $0.10
    assert b["dollars"] - a["dollars"] == pytest.approx((150_000 + 16_835 * 1.25 + 550) * 0.5e-6 + 1_000 * 2.5e-6
                                                        - (2_000 + 16_835 * 1.25 + 550) * 0.1e-6 - 1_000 * 0.5e-6, rel=0.02)


def test_a_model_without_a_listed_price_is_not_costed():
    assert CM.price_on("some-unlisted-model") is None
    assert CM.workload_cost("W2", "some-unlisted-model", 1.0) is None
    assert CM.monthly("some-unlisted-model", 1_000) is None


def test_the_mix_covers_every_workload_once():
    from tests.milo_eval.cases import WORKLOADS
    assert set(CM.MIX) == set(WORKLOADS) == set(CM.SHAPE_OF)
    assert sum(CM.MIX.values()) == pytest.approx(1.0)


def test_routing_keeps_each_questions_work_and_splits_the_cache():
    perfect = {w: {w: 1} for w in CM.MIX}
    one = R.routed_month(perfect, {}, 1_000)
    alone = CM.monthly(R.DEFAULT_MODEL, 1_000)
    assert one["dollars"] == pytest.approx(alone["dollars"], rel=1e-6), "no routes is the single model"
    routed = R.routed_month(perfect, R.EXAMPLE_ROUTES, 1_000)
    assert routed["misrouted_share"] == 0 and set(routed["model_share"]) == {"claude-haiku-5-5", "claude-opus-5-5", "claude-sonnet-5-5"}
    # a misrouted question still does its own workload's work, at its route's price
    wrong = R.routed_month({**perfect, "W10": {"W2": 1}}, R.EXAMPLE_ROUTES, 1_000)
    assert wrong["misrouted_high_risk_share"] == pytest.approx(CM.MIX["W10"])
    deterministic = R.routed_month(perfect, {}, 1_000, deterministic=("W9",))
    assert deterministic["dollars"] < alone["dollars"]


def test_the_router_scores_what_the_routing_report_says():
    from tests.milo_eval.cases import CASES
    got = R.evaluate(CASES)
    assert (got["routed_right"], got["cases"]) == (126, 181), "update docs/ai/MILO_ROUTING_RECOMMENDATION.md"
    assert got["seconds_per_decision"] < 0.01
    cheap = R.cheap_route_errors(CASES)
    assert {cid for cid, _, _ in cheap} == {"IND-03", "IND-06", "IND-09", "IND-13"}
    assert all(c["workload"] != "S1" or R.route(c) == "S1" for c in CASES), "every advice request is seen as one"
