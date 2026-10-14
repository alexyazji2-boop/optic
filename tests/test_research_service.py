"""The framework service end to end on a fake feed: every mode builds, gaps are
named, a failed read is not cached, and combined keeps the answers apart."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from app.research import forecasts, service
from tests.test_research_earnings import ea_fixture, sec_fixture
from tests.test_research_quality import strong_company


def _bars(n=320, seed=1):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.001, 0.012, n)))
    idx = pd.bdate_range(end="2026-10-13", periods=n)
    return pd.DataFrame({"Open": close, "High": close * 1.006, "Low": close * 0.994, "Close": close,
                         "Volume": np.full(n, 1e6)}, index=idx)


class Feed:
    def quote(self, sym):
        return {"price": 100.0, "name": sym, "market_time": "4:00PM EDT", "sector": "Technology"}

    def history(self, sym, period="2y", interval="1d"):
        return _bars(seed=2 if sym == "SPY" else 1)

    def financials(self, sym):
        return {"income_quarterly": None}

    def splits(self, sym):
        return []


def deps(**over):
    d = {
        "earnings": lambda p, yf, sym, rate: ea_fixture(),
        "earnings_dates": lambda yf, sym: {"next_report": ea_fixture()["next_report"]},
        "sec": lambda sym: sec_fixture(),
        "news": lambda yf, sym: {"articles": []},
        "longterm": lambda yf, sym: {"price": 100.0, "long_trend": {"above_200w_sma": True, "above_40w_sma": True},
                                     "valuation_history": {"percentile": 40}, "drawdown": {"max_drawdown_pct": -40}},
        "valuation": lambda yf, sym: {"classification": {"business_type": "operating", "models": {}}},
        "gathered": lambda yf, sym: dict(strong_company(), available=True),
        "comps": lambda yf, sym: None,
    }
    d.update(over)
    return d


NOW = datetime(2026, 10, 14, 21, 0, tzinfo=timezone.utc)      # after the close, before the 29 Oct release


@pytest.fixture(autouse=True)
def _store(tmp_path, monkeypatch):
    monkeypatch.setattr(forecasts, "DB_PATH", str(tmp_path / "f.db"))
    service._CACHE.clear()


@pytest.mark.parametrize("mode", ["long_term", "swing", "pre_earnings", "combined", "earnings"])
def test_every_mode_builds_offline(mode):
    out = service.build(Feed(), Feed(), "XYZ", mode, deps=deps(), now=NOW)
    assert out["available"] and out["mode"] == mode and out["data"]["gaps"] == []
    if mode in ("long_term", "combined"):
        assert out["long_term"]["quality"]["grade"] == "A"
    if mode in ("swing", "combined"):
        assert out["swing"]["grade"] in ("S", "A", "B", "Avoid", "No Setup")
    if mode in ("pre_earnings", "combined", "earnings"):
        assert out["earnings"]["which"] == "pre_earnings" and out["earnings"]["pre"]["available"]
        assert out["earnings"]["pre"]["saved"]["saved"] is True
    if mode == "combined":
        assert out["combined"]["verdict"] and "none is averaged" in out["combined"]["note"]


def test_a_failed_source_is_named_and_not_cached():
    def boom(*a, **k):
        raise RuntimeError("feed down")
    out = service.build(Feed(), Feed(), "XYZ", "combined", deps=deps(earnings=boom))
    assert any(g.startswith("earnings failed") for g in out["data"]["gaps"])
    assert "XYZ:combined" not in service._CACHE
    # The earnings read is missing, but the long-term and swing reads still stand.
    assert out["long_term"]["available"] and out["swing"]["grade"]


def test_swing_mode_does_not_fetch_the_chain():
    called = []
    out = service.build(Feed(), Feed(), "XYZ", "swing", now=NOW,
                        deps=deps(earnings=lambda *a: called.append(1) or ea_fixture()))
    assert not called and out["swing"]["grade"]


def test_missing_long_term_says_so_in_the_agreement():
    out = service.build(Feed(), Feed(), "XYZ", "combined", now=NOW,
                        deps=deps(gathered=lambda yf, sym: {"available": False, "reason": "no filings"}))
    assert out["long_term"]["available"] is False
    assert "could not be graded" in out["combined"]["verdict"]
