"""A request that failed is not an answer, so it is never cached as one.

Reproduced before the fix: one refused price-history request returned an empty
frame that `_cached` kept for five minutes, so /api/ticker answered "No price
data found" for a name with plenty, and the ranking's retry pass got the cached
failure back instead of retrying. The same held for the batch download,
intraday bars, earnings dates and history, the statements (six hours) and the
splits (a day). An empty answer is not kept as data either (2026-10-21: Yahoo answered the live server's SPY,
IWM, DIA, S&P 500, oil and gold histories with nothing for hours); it is held back for a minute, so a symbol with no
data is not asked for on every request, and the last good history stands in meanwhile.
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


def test_an_empty_history_is_held_back_a_minute_not_kept(monkeypatch):
    calls = []

    class Counted(Empty):
        def history(self, *a, **k):
            calls.append(k)
            return pd.DataFrame()
    monkeypatch.setattr(y.yf, "Ticker", Counted)
    assert P.history("ZZZZ").empty
    assert "hist:ZZZZ:2y:1d" not in y._CACHE, "an empty answer is not the fact 'no price data'"
    assert [("period" in k, "start" in k) for k in calls] == [(True, False), (False, True)], "asked again by date, once"
    assert P.history("ZZZZ").empty and len(calls) == 2, "within the minute it is not asked for again"


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


def frame(n=3, start=100.0):
    idx = pd.date_range("2026-10-01", periods=n, freq="D")
    return pd.DataFrame({"Open": start, "High": start, "Low": start, "Close": [start + i for i in range(n)], "Volume": 1}, index=idx)


def test_a_name_that_had_history_keeps_it_while_yahoo_answers_nothing(monkeypatch):
    answers = [frame(), pd.DataFrame(), pd.DataFrame()]

    class Flaky(Empty):
        def history(self, *a, **k):
            return answers.pop(0)
    monkeypatch.setattr(y.yf, "Ticker", Flaky)
    good = P.history("SPY")
    assert len(good) == 3
    y._CACHE.pop(y._hist_key("SPY", "2y", "1d"))       # the five minutes are up
    again = P.history("SPY")
    assert len(again) == 3 and again["Close"].iloc[-1] == 102.0, "the last good history stands in"
    assert "hist:SPY:2y:1d" not in y._CACHE, "and the empty answer is not kept"


def test_a_partial_batch_asks_for_the_missing_names_and_is_not_kept(monkeypatch):

    def download(tickers, **k):
        parts = {"AAA": frame(start=10.0)}            # BBB left out of the download
        return pd.concat(parts, axis=1)
    asked = []

    class One(Empty):
        def __init__(self, sym, *a, **k):
            self.sym = sym

        def history(self, *a, **k):
            asked.append(self.sym)
            return frame(start=20.0)
    monkeypatch.setattr(y.yf, "download", download)
    monkeypatch.setattr(y.yf, "Ticker", One)
    out = P.batch_history(["AAA", "BBB"])
    assert sorted(out) == ["AAA", "BBB"] and asked == ["BBB"], "the name the download left out, on its own"
    assert out["BBB"]["Close"].iloc[0] == 20.0
    assert not any(k.startswith("batch:") for k in y._CACHE), "a partial download is not kept as the board"


def test_a_refused_batch_makes_no_more_requests_and_uses_what_each_name_had(monkeypatch):
    y._CACHE["good:" + y._hist_key("AAA", "1y", "1d")] = (__import__("time").time(), frame(start=5.0))

    def boom(*a, **k):
        raise Exception("429 Too Many Requests")

    class Never(Empty):
        def history(self, *a, **k):
            raise AssertionError("no request on top of a refusal")
    monkeypatch.setattr(y.yf, "download", boom)
    monkeypatch.setattr(y.yf, "Ticker", Never)
    out = P.batch_history(["AAA", "BBB"])
    assert list(out) == ["AAA"] and out["AAA"]["Close"].iloc[0] == 5.0

