"""A first load starts the company and earnings fetches with everything else.

They were the last two legs of a cold ticker build to finish. Fundamentals is
five fetches in a row and could not start until the quote had come back;
earnings momentum is three. Profiled on cold symbols (SNAP, LYFT, 2026-09-28)
the company leg ran from 0.39s to 2.05s and earnings to 1.76s while everything
else was done by 1.2s. Started up front, a cold ORCL build measured 1.14s.

The blocks themselves did not change. They find the prefetched answers in the
provider's cache, or wait on the fetch already in flight, so what matters is
that the prefetch asks for exactly what they ask for: one call more would be a
Yahoo request per first load that nothing reads.
"""
from __future__ import annotations

import threading
import time

import pandas as pd
import pytest
from fastapi import HTTPException

import app.main as main
from app.analytics import earnings as earnings_mod
from app.analytics import fundamentals as fundamentals_mod
from app.providers import yf as Y

PREFETCHED = ("short_interest", "insiders", "institutions", "financials",
              "earnings_history", "estimates")


class _Recorder:
    """A provider that answers with nothing and writes down what it was asked."""

    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def call(ticker, *args, **kwargs):
            self.calls.append((name, ticker))
            return {} if name != "earnings_history" else []
        return call


def test_the_prefetch_is_exactly_what_the_two_blocks_fetch(monkeypatch):
    rec = _Recorder()
    fundamentals_mod.analyse(rec, "ABC", {"avg_volume": 1.0})
    earnings_mod.momentum(rec, "ABC")
    blocks = set(rec.calls)

    # The prefetch is whatever a parallel build starts that a sequential one
    # does not, which catches a leg added under any name.
    started = {True: {}, False: {}}

    class Legs(main._Legs):
        def start(self, name, fn, *args, **kwargs):
            started[self.parallel][name] = (getattr(fn, "__name__", name), args[:1])
            super().start(name, lambda *a, **k: None)

    monkeypatch.setattr(main, "_Legs", Legs)
    for parallel in (True, False):
        with pytest.raises(HTTPException):          # every leg answers None: a 404
            main._swing_snapshot("ABC", None, 4, True, include_earnings=True, parallel=parallel)
    extra = {n: v for n, v in started[True].items() if n not in started[False]}
    prefetched = {(fn, args[0]) for fn, args in extra.values()}
    assert prefetched == blocks, (
        "prefetched but never read: %s; read but not prefetched: %s"
        % (sorted(prefetched - blocks), sorted(blocks - prefetched)))


@pytest.fixture
def slow_provider(monkeypatch):
    """Every leg answers after a pause; the prefetches write down when they began."""
    began = {}
    t0 = []

    def slow(name, value, pause=0.2):
        def fn(*a, **k):
            began.setdefault(name, time.perf_counter() - t0[0])
            began.setdefault((name, a[0] if a else None), time.perf_counter() - t0[0])
            time.sleep(pause)
            return value
        return fn

    P, YF = main.PROVIDER, main.YF_PROVIDER
    monkeypatch.setattr(P, "quote", slow("quote", {"price": 10.0}, 0.3))
    monkeypatch.setattr(P, "history", slow("history", pd.DataFrame(), 0.3))
    monkeypatch.setattr(P, "expirations", slow("expirations", []))
    monkeypatch.setattr(P, "options_chain", slow("chain", None))
    monkeypatch.setattr(main.news_mod, "analyse", slow("news", {}))
    monkeypatch.setattr(main.macro_mod, "analyse", slow("macro", {}))
    monkeypatch.setattr(main.filings_mod, "recent", slow("filings", []))
    monkeypatch.setattr(main, "_sector_confirm", slow("sector", {}))
    monkeypatch.setattr(YF, "earnings_date", slow("earnings_date", None))
    for name in PREFETCHED:
        monkeypatch.setattr(YF, name, slow(name, [] if name == "earnings_history" else {}))
    # The blocks themselves, out of the way: left real, a block still reading
    # its fetches one by one when a test ends makes its next call through the
    # following test's stubs and lands in that test's record.
    monkeypatch.setattr(main.earnings_mod, "momentum", lambda *a, **k: {})
    monkeypatch.setattr(main.fundamentals_mod, "analyse", lambda *a, **k: {})
    yield began, t0
    time.sleep(0.3)                             # let the last 0.2s legs finish


def test_they_start_with_the_build_not_after_the_quote(slow_provider):
    began, t0 = slow_provider
    t0.append(time.perf_counter())
    with pytest.raises(HTTPException):          # the empty history is a 404
        main._swing_snapshot("ABC", None, 4, True, include_earnings=True, parallel=True)
    deadline = time.time() + 5
    while time.time() < deadline and not set(PREFETCHED) <= set(began):
        time.sleep(0.02)
    late = {n: round(began.get(n, 99), 3) for n in PREFETCHED if began.get(n, 99) > 0.15}
    assert not late, "started after the quote had come back (0.3s): %s" % late


def test_two_readers_loading_at_once_do_not_queue_each_other(slow_provider):
    # Eighteen legs a first load, so a pool of sixteen made the second reader's
    # wait for the first reader's.
    began, t0 = slow_provider
    t0.append(time.perf_counter())

    def load(sym):
        with pytest.raises(HTTPException):
            main._swing_snapshot(sym, None, 4, True, include_earnings=True, parallel=True)

    threads = [threading.Thread(target=load, args=(s,)) for s in ("AAA", "BBB")]
    for t in threads:
        t.start()
    for t in threads:
        t.join(5)
    deadline = time.time() + 5
    want = {(n, s) for n in PREFETCHED for s in ("AAA", "BBB")}
    while time.time() < deadline and not want <= set(began):
        time.sleep(0.02)
    late = {k: round(began.get(k, 99), 3) for k in want if began.get(k, 99) > 0.15}
    assert not late, "queued behind the other reader's legs: %s" % late


def test_a_scan_starts_none_of_them(slow_provider):
    began, t0 = slow_provider
    t0.append(time.perf_counter())
    with pytest.raises(HTTPException):
        main._swing_snapshot("ABC", None, 4, True, include_earnings=True)
    time.sleep(0.3)
    assert not set(PREFETCHED) & set(began), sorted(set(PREFETCHED) & set(began))


# ------------------------------------------------------------ earnings history


class _Frame:
    def __init__(self, n):
        self.frame = pd.DataFrame(
            {"EPS Estimate": [1.0] * n, "Reported EPS": [1.1] * n, "Surprise(%)": [10.0] * n},
            index=pd.date_range("2019-01-01", periods=n, freq="QS"))


def test_each_caller_gets_its_own_number_of_quarters_whoever_asks_first(monkeypatch):
    # Both blocks now start together, so which one fills the cache is a race.
    # The slice used to be taken inside the cache, which made the loser's
    # answer the winner's length: 16 rows for fundamentals, or 20 for momentum.
    class Ticker:
        def __init__(self, symbol):
            pass

        @property
        def earnings_dates(self):
            return _Frame(30).frame

    monkeypatch.setattr(Y.yf, "Ticker", Ticker)
    provider = Y.YFinanceProvider()
    for first, second in ((8, 10), (10, 8)):
        monkeypatch.setattr(Y, "_CACHE", {})
        a = provider.earnings_history("ABC", limit=first)
        b = provider.earnings_history("ABC", limit=second)
        assert (len(a), len(b)) == (first * 2, second * 2), (first, len(a), second, len(b))
