"""A quote whose document did not answer still carries its day's change.

Seen on Home on 26 October 2026: SPY's quote panel read "765.37 n/a (n/a)"
with no fund name while the watchlist beside it said +0.71% for the same
close. The quote's `.info` read had failed, `quote()` fell back to the last
daily bar for the price and had no previous close to measure from. Coming back
later, with the document answering, showed +5.40 (+0.71%) and the name."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.providers import yf as Y

ROOT = Path(__file__).parent.parent


def _bars(closes):
    idx = pd.date_range("2026-10-21", periods=len(closes), freq="B", tz="America/New_York")
    return pd.DataFrame({"Close": closes, "Open": closes, "High": closes, "Low": closes,
                         "Volume": [1e6] * len(closes)}, index=idx)


@pytest.fixture
def provider(monkeypatch):
    p = Y.YFinanceProvider()
    monkeypatch.setattr(Y, "_CACHE", {})

    def no_info(ticker):
        raise RuntimeError("quoteSummary did not answer")
    monkeypatch.setattr(p, "_info", no_info)
    monkeypatch.setattr(p, "history", lambda ticker, period="5d", **k: _bars([758.10, 759.97, 765.37]))
    return p


def test_the_change_comes_from_the_bar_before_when_the_quote_fails(provider):
    q = provider.quote("SPY")
    assert q["price"] == 765.37 and q["prev_close"] == 759.97
    assert q["change"] == pytest.approx(5.40, abs=0.005)
    assert q["change_pct"] == pytest.approx(0.7106, abs=0.001), "the watchlist's +0.71%"
    assert q["partial"] is True


def test_a_future_keeps_no_change_rather_than_a_wrong_one(provider):
    q = provider.quote("ES=F")
    assert q["price"] == 765.37 and q["change"] is None and q["change_pct"] is None and q["partial"] is True


def test_a_full_quote_is_not_partial_and_yahoos_change_wins(monkeypatch):
    p = Y.YFinanceProvider()
    monkeypatch.setattr(Y, "_CACHE", {})
    monkeypatch.setattr(p, "_info", lambda t: {"regularMarketPrice": 765.37, "regularMarketPreviousClose": 759.97,
                                               "regularMarketChange": 5.40, "regularMarketChangePercent": 0.71,
                                               "longName": "SPDR S&P 500 ETF Trust"})
    q = p.quote("SPY")
    assert q["partial"] is False and q["change_pct"] == 0.71 and q["name"] == "SPDR S&P 500 ETF Trust"


def test_home_says_one_thing_when_the_change_is_missing():
    src = (ROOT / "static/v2/js/pages/workspace.js").read_text()
    body = src[src.index("title: 'Quote and chart'"):src.index("cnews: {")]
    assert "Day's change not reported yet" in body and "qq.partial" in body
    assert "${signed(qq.change, 2, '')} (${signed(qq.change_pct)})</span>` : " in body, "the pair only when there is one"
    assert "qq.name !== link" in body, "no 'SPY SPY' when the name is missing"
