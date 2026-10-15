"""A take on a stock in the owner's reference shape, with its chart (2026-10-15).

The owner's reference: "Thoughts on HOOD in the near/long term?" answered with a chart (daily candles, a
long rising trend line, the near supports) and a short take (what drives the business, the near-term
supports, the long-term view with a sturdier peer, one line splitting the timeframes). What holds it:

* app/analytics/take_chart.py builds the levels and trend lines for the span the question asks for;
* main._with_take_levels puts them in CONTEXT (`chart_levels`, kept by the budget) with the chart tag;
* GET /api/take-chart draws the same numbers, so the chart and the text cannot disagree;
* the prompt's "A take on a stock" section, the chart rules, and the routing that gives a take both
  assessments.

Checked in a browser with HOOD on 2026-10-15: two years of candles, the rising trend line from the
November 2024 low, the falling one from the October 2025 high, resistance 112.15, supports 93.84 and
82.32, the level price sat on (101.86) left to the price tag.
"""
from __future__ import annotations

import asyncio
from datetime import date

import numpy as np
import pandas as pd
import pytest

from app import ai
from app.analytics import take_chart
from app.research import milo as research_milo
from app.research import modes


def _bars(n=600, seed=7):
    """A rising series with swings, so there are pivots, levels and trend lines to find."""
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    base = 40 + 0.08 * t + 6 * np.sin(t / 18.0)
    close = base + rng.normal(0, 0.8, n)
    open_ = close + rng.normal(0, 0.6, n)
    high = np.maximum(open_, close) + np.abs(rng.normal(0.6, 0.3, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0.6, 0.3, n))
    idx = pd.bdate_range(end="2026-10-15", periods=n)
    return pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close,
                         "Volume": rng.integers(1_000_000, 5_000_000, n)}, index=idx)


def test_the_span_follows_the_timeframe_asked():
    assert take_chart.span_for("long", "Thoughts on HOOD in the near/long term?") == "2y"
    assert take_chart.span_for("auto", "What do you think of HOOD short and long term?") == "2y"
    assert take_chart.span_for("long", "Is Apple worth owning for 10 years?") == "2y"
    assert take_chart.span_for("swing", "Any swing trade on AMD?") == "6m"
    assert take_chart.span_for("day", "Trade it at the open?") == "3m"
    assert take_chart.span_for("auto", "Thoughts on HOOD?") == "1y"


def test_levels_each_side_and_the_level_price_sits_on():
    out = take_chart.build(_bars(), "2y")
    assert out["available"] and out["span"] == "2y" and out["bars"] == 504
    close, near = out["close"], out["atr"] / 2
    assert all(lv["price"] < close - near for lv in out["supports"])
    assert all(lv["price"] > close + near for lv in out["resistances"])
    assert all(abs(lv["price"] - close) <= near + 0.01 for lv in out["at_price"])
    assert len(out["supports"]) <= 2 and len(out["resistances"]) <= 2
    sup = [lv["price"] for lv in out["supports"]]
    assert sup == sorted(sup, reverse=True), "nearest first"
    assert len(out["drawn"]) <= 2 and all(not ln["broken"] for ln in out["drawn"])
    assert "not forecasts" in out["method"]


def test_milo_gets_the_levels_without_the_bars_and_the_tag_that_draws_them():
    ctx = take_chart.for_context(take_chart.build(_bars(), "6m"), "HOOD")
    assert ctx["chart_tag"] == "[[chart HOOD 6m]]"
    assert "_window" not in ctx and "chart" not in ctx
    assert all("start_index" not in ln for ln in ctx["trend_lines"])
    assert len(ctx["trend_lines"]) <= 2 and "drawn" not in ctx, "only the lines the chart draws"
    assert take_chart.for_context(take_chart.build(_bars(30), "6m"), "HOOD")["available"] is False
    assert take_chart.build(None, "2y")["available"] is False


def test_the_chart_endpoint_draws_the_same_numbers(monkeypatch):
    from fastapi.testclient import TestClient
    import app.main as m
    df = _bars()
    monkeypatch.setattr(m.YF_PROVIDER, "history", lambda *a, **k: df)
    body = TestClient(m.app).get("/api/take-chart/hood?span=2y").json()
    same = take_chart.build(df, "2y")
    assert body["ticker"] == "HOOD" and body["available"]
    assert body["supports"] == same["supports"] and body["resistances"] == same["resistances"]
    assert len(body["chart"]["close"]) == 504 and body["chart"]["dates"][-1] == "2026-10-15"
    assert {"open", "high", "low", "close", "volume"} <= set(body["chart"])


def test_the_chat_context_carries_the_levels(monkeypatch):
    import app.main as m
    df = _bars()
    monkeypatch.setattr(m.YF_PROVIDER, "history", lambda *a, **k: df)
    hist = [{"role": "user", "content": "Thoughts on HOOD in the near/long term?"}]
    ctx = asyncio.run(m._with_take_levels(hist, {"ticker": "HOOD", "quote": {"ticker": "HOOD", "price": 100}}))
    assert ctx["chart_levels"]["chart_tag"] == "[[chart HOOD 2y]]" and ctx["chart_levels"]["available"]
    # Nothing in scope, nothing added.
    assert asyncio.run(m._with_take_levels(hist, {"focus": {"scope": "auto"}})) == {"focus": {"scope": "auto"}}


def test_the_budget_keeps_the_levels_ahead_of_the_bulk():
    order = ai._ORDER_BASE
    assert order.index("chart_levels") < order.index("pulse") < order.index("technicals")


def test_milo_is_told_the_take_shape():
    sp = " ".join(ai.SYSTEM_PROMPT.split())
    assert "## A take on a stock" in ai.SYSTEM_PROMPT
    for phrase in ("exactly as `chart_levels.chart_tag` gives it",
                   "What drives the business, and what that means for the stock",
                   "Specific to this company, never a generic line that would fit any stock",
                   "as plain prices from `chart_levels`",
                   "a business you would want to own for years, as your own read with the reason",
                   "When a well-known peer suits the long-term case better, name it with the business reason",
                   "One closing line, in your own words, that splits the timeframes",
                   "About 150 to 180 words and never more than 200, even when a framework block allows more",
                   "no more than six numbers in all",
                   "never write a grade's label, not even in quotation marks",
                   "No disclaimer line such as \"not advice\"",
                   "never an instruction about the reader's money"):
        assert phrase in sp, phrase
    fmt = " ".join(ai.FORMAT_PROMPT.split())
    assert "one of 1m, 3m, 6m, 1y, 2y or 5y" in fmt and "use its `chart_tag` exactly" in fmt
    assert "stop_check, chart_levels, retrieved and pairs" in fmt
    assert "—" not in ai.SYSTEM_PROMPT and "—" not in ai.FORMAT_PROMPT


def test_a_take_gets_both_assessments_unless_a_timeframe_decides():
    today = date(2026, 10, 15)
    for q in ("Thoughts on HOOD in the near/long term?", "Thoughts on HOOD?",
              "What do you think of HOOD short and long term?", "HOOD near term vs long term?"):
        assert modes.resolve(q, "HOOD", today=today)["mode"] == "combined", q
    assert modes.resolve("Thoughts on HOOD for a swing?", "HOOD", today=today)["mode"] == "swing"
    assert modes.resolve("thoughts on NVDA?", "NVDA", saved_horizon="swing", today=today)["mode"] == "swing"
    assert modes.resolve("Is HOOD worth owning long term?", "HOOD", today=today)["mode"] == "long_term"
    assert "take shape of the base prompt" in research_milo.MODES["combined"]
