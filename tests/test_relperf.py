"""Relative Performance: a percentile rank against peers.

The distinction worth protecting is that RP is a RANK, not a ratio. A ratio
line against SPY answers "is this beating the index"; RP answers "how many of
its peers is it beating", and the two disagree exactly when it matters, such as
a stock up 3% in a month where the median name fell 4%.
"""

import numpy as np
import pandas as pd
import pytest

from app.analytics import relperf


class FakeProvider:
    """Deterministic closes: symbol i compounds at i basis points a day."""

    def __init__(self, symbols, days=300):
        idx = pd.bdate_range("2025-01-01", periods=days)
        self.frames = {}
        for i, s in enumerate(symbols):
            drift = 1.0 + (i / 10000.0)
            self.frames[s] = pd.DataFrame(
                {"Close": 100.0 * np.power(drift, np.arange(days))}, index=idx)

    def batch_history(self, symbols, period="1y", interval="1d"):
        return {s: self.frames[s] for s in symbols if s in self.frames}


@pytest.fixture(autouse=True)
def clear_cache():
    relperf._cache.clear()
    yield
    relperf._cache.clear()


def test_the_universe_is_sector_balanced_and_deduplicated():
    """Ranking against a cap-weighted index ranks against a handful of megacaps.
    The peer set exists to avoid that, so it must stay broad."""
    u = relperf.universe()
    assert len(u) == len(set(u)), "duplicates would weight some names twice"
    assert len(u) > 100


def test_a_symbol_is_not_its_own_peer():
    """Leaving it in shifts every rank and makes 100 unreachable."""
    syms = relperf.universe()[:40]
    out = relperf.analyse(FakeProvider(syms), syms[0])
    assert out["available"] is True
    assert out["universe_size"] == len(syms) - 1


def test_the_strongest_name_ranks_at_the_top():
    syms = relperf.universe()[:40]
    prov = FakeProvider(syms)
    best = relperf.analyse(prov, syms[-1])["windows"]["1m"]
    worst = relperf.analyse(prov, syms[0])["windows"]["1m"]
    assert best["rank"] > 95
    assert worst["rank"] < 5
    assert best["state"] == "leader"
    assert worst["state"] == "laggard"


def test_rank_is_a_percentile_not_a_return():
    """Every name rising still produces a spread of ranks: that is the point."""
    syms = relperf.universe()[:40]
    prov = FakeProvider(syms)
    # Sampled across the range, not off one end. syms[:8] are the eight weakest
    # by construction, so they all rank low and prove nothing.
    picks = [syms[0], syms[len(syms) // 2], syms[-1]]
    ranks = [relperf.analyse(prov, s)["windows"]["1m"]["rank"] for s in picks]
    assert ranks == sorted(ranks), "rank must follow relative strength"
    assert min(ranks) < 50 < max(ranks)


def test_crosses_need_a_real_transition():
    """A series hovering on the line must not report a cross every day, which is
    what makes threshold alerts unusable."""
    hover = pd.Series([79.9, 80.1, 79.9, 80.1, 79.9],
                      index=pd.bdate_range("2025-01-01", periods=5))
    # Two genuine upward crossings, not four.
    assert len(relperf._crosses(hover)) == 2

    flat = pd.Series([85.0] * 5, index=pd.bdate_range("2025-01-01", periods=5))
    assert relperf._crosses(flat) == []


def test_cross_direction_is_reported():
    s = pd.Series([50.0, 85.0, 50.0, 10.0],
                  index=pd.bdate_range("2025-01-01", periods=4))
    dirs = [c["direction"] for c in relperf._crosses(s)]
    assert dirs == ["up", "down"]


def test_state_thresholds():
    assert relperf._state(96) == "leader"
    assert relperf._state(4) == "laggard"
    assert relperf._state(85) == "outperforming"
    assert relperf._state(15) == "underperforming"
    assert relperf._state(50) == "in line"
    assert relperf._state(None) == "unknown"


def test_headline_names_the_divergence():
    """A short window ahead of a long one is a turn; the copy has to say which."""
    fast = {"available": True, "rank": 90.0, "window_days": 21}
    assert "Turning up" in relperf._headline("X", fast, {"rank": 60.0})
    assert "fading" in relperf._headline("X", {"available": True, "rank": 55.0,
                                               "window_days": 21}, {"rank": 85.0})


def test_scan_kinds_select_different_names():
    syms = relperf.universe()[:40]
    prov = FakeProvider(syms)
    lead = relperf.scan(prov, "leaders")
    lag = relperf.scan(prov, "laggards")
    assert lead["available"] and lag["available"]
    assert set(r["symbol"] for r in lead["rows"]).isdisjoint(
        r["symbol"] for r in lag["rows"])


def test_scan_states_its_own_limits():
    """A 143-name universe is a sample, and the panel has to say so."""
    out = relperf.scan(FakeProvider(relperf.universe()[:40]), "leaders")
    assert "not the whole market" in out["caveat"]


def test_missing_history_is_reported_not_guessed():
    out = relperf.analyse(FakeProvider([]), "NOSUCH")
    assert out["available"] is False
    assert "unavailable" in out["reason"].lower()


def test_no_em_dashes_in_the_copy():
    out = relperf.analyse(FakeProvider(relperf.universe()[:40]),
                          relperf.universe()[0])
    assert "—" not in out["method"]
    assert "—" not in out["headline"]
