"""The instrument page's tiles are the same on every range.

They were computed from the chart's own bars, so pressing a range pill changed
what they said about the instrument. Measured on DXY: on 1M the snapshot had 22
bars and gave up ("insufficient history"), so 20 days, vs 200-day, RSI and
From 52-week high were all blank; on 3M the 200-day average was blank, the RSI
read 73.65 against 74.96 on 1Y, and "From 52-week high" was the distance from
the high of three months.

The tiles come from a year of daily bars now, whatever the chart is on, which
is also what the macro panel computes them from. The chart keeps its range.

Checked against the local server on DX-Y.NYB: the snapshot on 1M, 3M, 6M, 2Y
and 5Y is the 1Y snapshot, 20 days +2.49%, vs 200-day +2.8%, RSI 75, from the
52-week high 0.0%, while the chart drew 22, 65, 127, 504 and 1,257 bars.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import app.main as main

BARS = {"1mo": 22, "3mo": 64, "6mo": 126, "1y": 252, "2y": 504, "5y": 1260}


def _series():
    idx = pd.bdate_range(end="2026-10-01", periods=1260)
    rng = np.random.default_rng(7)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.006, len(idx))))
    return pd.DataFrame({"Open": close, "High": close * 1.004, "Low": close * 0.996,
                         "Close": close, "Volume": np.zeros(len(idx))}, index=idx)


class _Provider:
    """One long series, cut to each period the way the feed cuts it."""

    def __init__(self, year_empty=False):
        self.full = _series()
        self.asked = []
        self.year_empty = year_empty

    def history(self, ticker, period="2y", interval="1d"):
        self.asked.append(period)
        if period == "1y" and self.year_empty:
            return pd.DataFrame()
        return self.full.tail(BARS[period]).copy()

    def batch_quote(self, tickers):
        return {}


@pytest.fixture
def client(monkeypatch):
    def make(**kw):
        provider = _Provider(**kw)
        monkeypatch.setattr(main, "YF_PROVIDER", provider)
        return TestClient(main.app), provider
    return make


def _get(c, rng):
    return c.get("/api/instrument", params={"symbol": "DX-Y.NYB", "range": rng}).json()


def test_every_range_has_the_one_year_tiles(client):
    c, provider = client()
    year = _get(c, "1y")
    assert provider.asked == ["1y"], "on a year, the chart's own bars and no second fetch"
    for rng in ("1mo", "3mo", "6mo", "2y", "5y"):
        provider.asked.clear()
        body = _get(c, rng)
        assert body["snapshot"] == year["snapshot"], rng
        assert provider.asked == [rng, "1y"], rng
        assert len(body["close"]) == BARS[rng], "the chart keeps its own range"
    s = year["snapshot"]
    assert "error" not in s
    for key in ("chg_20d", "vs_sma200", "rsi", "pct_from_52w_high", "sma200", "high_52w"):
        assert s[key] is not None, key


def test_a_short_range_no_longer_blanks_the_tiles(client):
    c, _ = client()
    s = _get(c, "1mo")["snapshot"]
    assert s.get("error") is None, "22 bars was 'insufficient history'"
    assert s["high_52w"] == pytest.approx(float(_series()["Close"].tail(252).max()), rel=1e-6), (
        "the high of a year, not of the month on screen")


def test_without_a_year_the_tiles_fall_back_to_the_chart_bars(client):
    c, provider = client(year_empty=True)
    body = _get(c, "3mo")
    assert body["available"] is True
    assert provider.asked == ["3mo", "1y"]
    assert body["snapshot"]["chg_20d"] is not None, "what the tiles read before, not an error"
