"""The research framework's rules: policy, trade arithmetic, the swing grade,
mode routing and quote freshness. Pure functions on synthetic inputs, no
network."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd
import pytest

from app.research import modes, policy, service, swing_setup, trade_math

VALUES = policy.current()["values"]


# ---------------------------------------------------------------- policy

def test_defaults_are_the_briefs_thresholds():
    v = policy.current()["values"]
    assert v["rr_s_min"] == 2.5 and v["rr_avoid_below"] == 1.5 and v["rr_cap_b_below"] == 2.0
    assert v["atr_stop_multiple"] == 1.5 and v["quality_cap_grade"] == "B"
    assert v["earnings_in_window_cap"] == "B"
    assert policy.RULES["atr_stop_multiple"]["status"] == "assumption"


def test_overrides_are_reported_and_bad_ones_ignored(monkeypatch):
    monkeypatch.setenv("OPTIC_RESEARCH_POLICY", json.dumps({"rr_s_min": 3, "nope": 1, "quality_cap_grade": 7}))
    cur = policy.current()
    assert cur["values"]["rr_s_min"] == 3.0
    assert cur["changed"] == ["rr_s_min"] and cur["version"].endswith("+custom")
    assert any("nope" in m for m in cur["ignored"]) and any("quality_cap_grade" in m for m in cur["ignored"])
    assert cur["values"]["quality_cap_grade"] == "B"


def test_invalid_env_json_falls_back(monkeypatch):
    monkeypatch.setenv("OPTIC_RESEARCH_POLICY", "{not json")
    cur = policy.current()
    assert cur["values"] == {k: r["value"] for k, r in policy.RULES.items()} and cur["ignored"]


def test_grade_below():
    assert policy.grade_below("C", "B") and not policy.grade_below("B", "B") and not policy.grade_below("A", "B")
    assert not policy.grade_below(None, "B")


# ---------------------------------------------------------------- trade math

def test_reward_to_risk_long_and_short():
    assert trade_math.reward_to_risk(100, 95, 112.5) == pytest.approx(2.5)
    assert trade_math.reward_to_risk(100, 105, 87.5, side="short") == pytest.approx(2.5)
    # A stop or target on the wrong side is not a plan, not a negative ratio.
    assert trade_math.reward_to_risk(100, 101, 110) is None
    assert trade_math.reward_to_risk(100, 95, 99) is None


def test_stop_is_widened_to_the_atr_floor_never_tightened():
    s = trade_math.place_stop(100.0, 99.0, 2.0, 1.5)        # structure 1 away, floor 3 away
    assert s["stop"] == pytest.approx(97.0) and s["widened"] and s["basis"] == "atr"
    s = trade_math.place_stop(100.0, 94.0, 2.0, 1.5)        # structure beyond the floor: kept
    assert s["stop"] == pytest.approx(94.0) and not s["widened"] and s["basis"] == "structure"
    s = trade_math.place_stop(100.0, 101.0, 2.0, 1.5, side="short")
    assert s["stop"] == pytest.approx(103.0) and s["widened"]


def test_sensitivity_covers_zone_and_costs():
    sens = trade_math.sensitivity(100, 95, 112.5, zone_low=99, zone_high=101, spread=0.2, slippage_bps=10)
    assert sens["representative"] == pytest.approx(2.5)
    assert sens["low"] < 2.5 < sens["high"]
    assert any("slippage" in c["case"] for c in sens["cases"])


def test_sizing_states_the_gap_risk():
    out = trade_math.sizing_example(10000, 1.0, 100, 95, gap_price=90)
    assert out["shares"] == 20 and out["planned_loss"] == pytest.approx(100)
    assert out["gap_loss"] == pytest.approx(200) and "not a guarantee" in out["gap_note"]


# ---------------------------------------------------------------- swing grade

def _criteria(**kw):
    c = {k: True for k in ("daily_weekly_aligned", "reward_to_risk_ok", "no_earnings_in_window",
                           "clear_invalidation", "outperforms_benchmark", "sufficient_data")}
    c.update(kw)
    return c


def _o(sev, kind="levels"):
    return {"text": "x", "severity": sev, "kind": kind}


def test_s_needs_every_criterion_and_no_serious_caveat():
    assert swing_setup.decide_grade(_criteria(), [], 3.0, False, VALUES)[0] == "S"
    assert swing_setup.decide_grade(_criteria(), [_o(1)], 3.0, False, VALUES)[0] == "S"
    assert swing_setup.decide_grade(_criteria(), [_o(2)], 3.0, False, VALUES)[0] == "A"
    assert swing_setup.decide_grade(_criteria(outperforms_benchmark=False), [_o(2, "relative")], 3.0, False,
                                    VALUES)[0] == "A"
    assert swing_setup.decide_grade(_criteria(), [_o(2), _o(2, "alignment")], 3.0, False, VALUES)[0] == "B"


def test_reward_to_risk_rules():
    g, rules = swing_setup.decide_grade(_criteria(reward_to_risk_ok=False), [], 1.4, False, VALUES)
    assert g == "Avoid" and rules[0]["rule"] == "rr_avoid_below"
    g, rules = swing_setup.decide_grade(_criteria(reward_to_risk_ok=False), [], 1.8, False, VALUES)
    assert g == "B"
    assert swing_setup.decide_grade(_criteria(), [], None, False, VALUES)[0] == "Avoid"


def test_earnings_in_window_caps_at_b_unless_an_event_strategy():
    g, rules = swing_setup.decide_grade(_criteria(no_earnings_in_window=False), [_o(3, "earnings")], 3.0, True,
                                        VALUES)
    assert g == "B" and rules[-1]["rule"] == "earnings_in_window_cap"
    g, _ = swing_setup.decide_grade(_criteria(no_earnings_in_window=False), [_o(3, "earnings")], 3.0, True,
                                    VALUES, event_strategy=True)
    assert g == "A"


def test_opposing_evidence_outweighs():
    g, rules = swing_setup.decide_grade(_criteria(), [_o(2), _o(2, "alignment"), _o(2, "benchmark")], 3.0, False,
                                        VALUES)
    assert g == "Avoid" and rules[0]["rule"] == "opposing_evidence"


def _bars(n=320, drift=0.001, seed=1, start=100.0):
    rng = np.random.default_rng(seed)
    r = rng.normal(drift, 0.012, n)
    close = start * np.exp(np.cumsum(r))
    idx = pd.bdate_range("2025-01-02", periods=n)
    high = close * (1 + np.abs(rng.normal(0, 0.006, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.006, n)))
    opn = np.r_[close[0], close[:-1]]
    vol = rng.integers(1_000_000, 2_000_000, n).astype(float)
    return pd.DataFrame({"Open": opn, "High": np.maximum(high, np.maximum(opn, close)),
                         "Low": np.minimum(low, np.minimum(opn, close)), "Close": close, "Volume": vol}, index=idx)


def test_too_few_bars_is_insufficient_data_not_a_bad_grade():
    out = swing_setup.assess(_bars(100), _bars(100, seed=2), VALUES)
    assert out["grade"] == "Insufficient Data" and "220" in out["why"]


def test_no_benchmark_is_insufficient():
    assert swing_setup.assess(_bars(), None, VALUES)["grade"] == "Insufficient Data"


def test_every_assessment_names_its_grade_and_framework_note():
    for seed in range(1, 9):
        out = swing_setup.assess(_bars(seed=seed), _bars(seed=99), VALUES,
                                 earnings={"date": "2025-12-01", "confirmed": False})
        assert out["grade"] in ("S", "A", "B", "Avoid", "No Setup")
        if out["grade"] == "No Setup":
            assert out["reassess_when"]
        else:
            plan = out["plan"]
            assert plan["rr_formula"] and plan["invalidation"]["price"] is not None
            # The stop is never closer than the ATR floor.
            atr = out["readings"]["atr14"]
            assert abs(plan["entry"] - plan["invalidation"]["price"]) >= 1.5 * atr - 0.02
            # Objections are listed before the grade is explained.
            assert isinstance(out["objections"], list)


def test_rsi_and_relative_strength_are_reported_separately():
    out = swing_setup.readings(_bars(), _bars(seed=99))
    assert "rsi14" in out and "SPY_1m" in out["relative_strength"] and "SPY_3m" in out["relative_strength"]
    assert "excess_pct" in out["relative_strength"]["SPY_1m"]
    assert "different thing from RSI" in swing_setup.__doc__


def test_holding_window_counts_earnings_inside_it():
    exp = swing_setup._earnings_exposure({"date": "2025-03-10", "confirmed": True}, "2025-03-03", 10)
    assert exp["in_window"] is True
    exp = swing_setup._earnings_exposure({"date": "2025-06-10", "confirmed": False}, "2025-03-03", 10)
    assert exp["in_window"] is False and "not confirmed" in exp["text"]
    exp = swing_setup._earnings_exposure({}, "2025-03-03", 10)
    assert exp["known"] is False and exp["in_window"] is None


# ---------------------------------------------------------------- modes

TODAY = date(2026, 10, 14)


@pytest.mark.parametrize("q,expected", [
    ("How did JPM's earnings go?", "post_earnings"),
    ("Why did JPM drop after earnings?", "post_earnings"),
    ("What should I expect into NVDA earnings next week?", "pre_earnings"),
    ("Is NVDA a good long-term investment?", "long_term"),
    ("Is there a swing setup on NVDA?", "swing"),
    ("Give me the full picture on NVDA, trade and invest", "combined"),
    ("Should I buy NVDA?", "unclear"),
])
def test_mode_from_the_question(q, expected):
    assert modes.resolve(q, "NVDA", today=TODAY)["mode"] == expected


def test_an_earnings_question_without_tense_reads_the_calendar():
    r = modes.resolve("How are earnings looking for JPM?", "JPM", last_report="2026-10-13",
                      next_report="2027-01-13", today=TODAY)
    assert r["mode"] == "post_earnings" and r["source"] == "timing"
    r = modes.resolve("How are earnings looking for AAPL?", "AAPL", last_report="2026-07-30",
                      next_report="2026-10-29", today=TODAY)
    assert r["mode"] == "pre_earnings" and r["source"] == "timing"


def test_short_questions_get_a_short_answer():
    assert modes.resolve("What's the stop on NVDA?", "NVDA", today=TODAY)["depth"] == "quick"
    assert modes.resolve("Where's the stop on the XOM setup?", "XOM", today=TODAY)["depth"] == "quick"
    assert modes.resolve("What's the EPS consensus for AAPL?", "AAPL", today=TODAY)["depth"] == "quick"
    assert modes.resolve("Give me a full analysis of NVDA", "NVDA", today=TODAY)["depth"] == "full"
    # A judgement is a full read, however short the question.
    for q in ("Is NVDA a good long-term investment at today's price?", "Is there a swing setup on XOM?",
              "How did JPM's earnings go?", "What should I expect from AAPL's earnings?"):
        assert modes.resolve(q, "NVDA", today=TODAY)["depth"] == "full", q


def test_what_should_i_expect_is_pre_earnings():
    assert modes.resolve("What should I expect from AAPL's earnings this month?", "AAPL",
                         today=TODAY)["mode"] == "pre_earnings"


def test_explicit_mode_and_saved_horizon():
    assert modes.resolve("thoughts?", "NVDA", explicit="swing", today=TODAY)["source"] == "chosen"
    assert modes.resolve("thoughts on NVDA?", "NVDA", saved_horizon="swing", today=TODAY)["mode"] == "swing"
    assert modes.resolve("what is a moat?", None, today=TODAY)["mode"] is None


# ---------------------------------------------------------------- freshness

def test_stale_quote_in_session_is_flagged():
    now = datetime(2026, 10, 14, 17, 30, tzinfo=timezone.utc)      # 13:30 ET, a Wednesday
    f = service.quote_freshness({"market_time": "12:20PM EDT"}, "2026-10-13", 30, now)
    assert f["phase"] == "regular" and f["state"] == "stale" and f["age_minutes"] == 70
    f = service.quote_freshness({"market_time": "1:15PM EDT"}, "2026-10-13", 30, now)
    assert f["state"] == "delayed"
    f = service.quote_freshness({}, "2026-10-14", 30, now)
    assert f["state"] == "delayed" and "exact age is unknown" in f["text"]
    f = service.quote_freshness({}, "2026-10-13", 30, now)
    assert f["state"] == "stale" and "stop at 2026-10-13" in f["text"]


def test_closed_session_is_labelled_not_called_stale():
    sat = datetime(2026, 10, 17, 16, 0, tzinfo=timezone.utc)
    f = service.quote_freshness({"market_time": "4:00PM EDT"}, "2026-10-16", 30, sat)
    assert f["state"] == "closed_session" and "last regular close" in f["text"]


def test_forming_bar_is_dropped_in_session_only():
    idx = pd.bdate_range("2026-10-08", "2026-10-14")
    df = pd.DataFrame({"Close": range(len(idx))}, index=idx)
    now = datetime(2026, 10, 14, 17, 30, tzinfo=timezone.utc)
    assert service.completed_bars(df, "regular", now).index[-1].date() == date(2026, 10, 13)
    assert service.completed_bars(df, "after", now).index[-1].date() == date(2026, 10, 14)


def test_a_fund_has_no_earnings_in_the_window_and_a_missing_date_stays_unknown():
    """Found by the historical validation replay (2026-10-14): with "no date"
    read as unknown, an ETF could never reach S."""
    exp = swing_setup._earnings_exposure({"not_applicable": True, "what": "an exchange-traded fund"}, "2025-03-03", 10)
    assert exp["known"] is True and exp["in_window"] is False and "exchange-traded fund" in exp["text"]
    assert service._earn_dates(None, {"quote_type": "ETF"})["not_applicable"] is True
    assert service._earn_dates({"not_applicable": True}, {"quote_type": "EQUITY"})["not_applicable"] is True
    # A company with no date in the feed is still unknown, so S stays out of reach.
    stock = service._earn_dates({"next_report": {}}, {"quote_type": "EQUITY"})
    assert "not_applicable" not in stock
    assert swing_setup._earnings_exposure(stock, "2025-03-03", 10)["in_window"] is None


@pytest.mark.parametrize("q,expected", [
    ("Why do the long-term and swing reads disagree on Alphabet?", "combined"),
    ("Is GOOGL a long-term hold or a swing trade?", "combined"),
    ("The signals don't agree on GOOGL, why?", "combined"),
    ("What's a dividend yield?", None),
    ("What does EBITDA mean?", None),
    ("What's a good entry on KO?", "swing"),
    ("What's a reasonable stop here?", "swing"),
])
def test_routing_misses_found_by_the_milo_eval(q, expected):
    assert modes.resolve(q, "GOOGL", today=TODAY)["mode"] == expected, q
