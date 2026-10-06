"""A request that failed is not an answer, so it is never cached as one.

Reproduced before the fix: one refused price-history request returned an empty
frame that `_cached` kept for five minutes, so /api/ticker answered "No price
data found" for a name with plenty, and the ranking's retry pass got the cached
failure back instead of retrying. The same held for the batch download,
intraday bars, earnings dates and history, the statements (six hours) and the
splits (a day). A genuinely empty answer is still cached: a symbol with no data
is not asked again on every request.
"""

from __future__ import annotations

import pandas as pd
import pytest

import app.providers.yf as y
from app.main import YF_PROVIDER as P


class Refused:
    def __init__(self, *a, **k):
        pass

    def history(self, *a, **k):
        raise Exception("429 Too Many Requests")

    @property
    def calendar(self):
        raise Exception("429 Too Many Requests")

    @property
    def income_stmt(self):
        raise Exception("timed out")

    @property
    def splits(self):
        raise Exception("timed out")


class Empty(Refused):
    def history(self, *a, **k):
        return pd.DataFrame()


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    monkeypatch.setattr(y, "_CACHE", {})
    monkeypatch.setattr(y, "_wait_turn", lambda: None)
    monkeypatch.setattr(y, "note_throttle", lambda exc: None)


def test_a_refused_history_is_not_kept(monkeypatch):
    monkeypatch.setattr(y.yf, "Ticker", Refused)
    assert P.history("ZZZZ").empty
    assert not any(k.startswith("hist:ZZZZ") for k in y._CACHE)


def test_an_empty_history_is_kept(monkeypatch):
    monkeypatch.setattr(y.yf, "Ticker", Empty)
    assert P.history("ZZZZ").empty
    assert any(k.startswith("hist:ZZZZ") for k in y._CACHE)


def test_a_refused_batch_download_is_not_kept(monkeypatch):
    def boom(*a, **k):
        raise Exception("429 Too Many Requests")
    monkeypatch.setattr(y.yf, "download", boom)
    assert P.batch_history(["AAA", "BBB"]) == {}
    assert not any(k.startswith("batch:") for k in y._CACHE)


def test_a_statement_that_failed_to_load_is_not_kept(monkeypatch):
    monkeypatch.setattr(y.yf, "Ticker", Refused)
    out = P.financials("ZZZZ")
    assert out.get("income_annual") is None
    assert "fin:ZZZZ" not in y._CACHE


def test_earnings_dates_and_splits_that_failed_are_not_kept(monkeypatch):
    monkeypatch.setattr(y.yf, "Ticker", Refused)
    assert P.earnings_date("ZZZZ") is None and P.splits("ZZZZ") == []
    assert "earn:ZZZZ" not in y._CACHE and "splits:ZZZZ" not in y._CACHE
