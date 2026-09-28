"""Yahoo fetches run side by side, a cold start still makes one per key, and a
rate limit inside the quote pool cannot freeze the process.

_cached held one global lock around every network call, so the whole app
fetched from Yahoo one request at a time: the parallel ticker build's legs
started together and then queued, three of them finishing at the same instant.
With a lock per key instead, cold builds measured locally went from 5.3-7.1s to
about 2.6s (ADBE 2.53s, SHOP 2.62s, ABNB 2.67s).

The same lock hid a deadlock. batch_quote holds it across its worker pool, and
a worker that hit a rate limit called note_throttle, which wanted it too: the
worker waited on the owner and the owner on the worker, and every Yahoo call in
the process stopped. A test faking "Too Many Requests" there hung the suite.

And the limiter's own lock was held across its waits. Twenty fetches at once
with twelve tokens at 2/s: the twelve that had finished at 0.30s could not
record their success until the last of the eight waiting for a token woke, and
all of them returned at 4.03s.
"""
from __future__ import annotations

import threading
import time
import types

import pytest

from app.providers import yf as Y


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.setattr(Y, "_CACHE", {})
    monkeypatch.setattr(Y, "_BUCKET", {"tokens": 100.0, "rate": 100.0, "last": time.time()})
    monkeypatch.setattr(Y, "_THROTTLE", {"until": 0.0, "hits": 0, "last_seen": None})


def _in_thread(fn, deadline=5.0):
    """Run fn and fail rather than hang if it does not come back."""
    box = {}
    t = threading.Thread(target=lambda: box.update(value=fn()), daemon=True)
    t.start()
    t.join(deadline)
    assert not t.is_alive(), "did not return within %.0fs: deadlocked" % deadline
    return box.get("value")


def test_different_keys_fetch_side_by_side():
    def slow():
        time.sleep(0.3)
        return 1
    t0 = time.time()
    threads = [threading.Thread(target=Y._cached, args=("k%d" % i, 60, slow)) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(5)
    assert time.time() - t0 < 0.9, "six 0.3s fetches took %.2fs" % (time.time() - t0)


def test_one_key_is_still_fetched_once_on_a_cold_start():
    calls = []

    def slow():
        calls.append(1)
        time.sleep(0.2)
        return "v"
    threads = [threading.Thread(target=Y._cached, args=("same", 60, slow)) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(5)
    assert len(calls) == 1 and Y._CACHE["same"][1] == "v"


def test_every_fetch_still_takes_a_token():
    Y._BUCKET.update(tokens=3.0)
    for i in range(3):
        Y._cached("t%d" % i, 60, lambda: 1)
    assert Y._BUCKET["tokens"] < 1.0


def test_a_rate_limit_inside_the_quote_pool_does_not_freeze_the_process(monkeypatch):
    class Ticker:
        def __init__(self, symbol):
            self.symbol = symbol

        @property
        def fast_info(self):
            return {"lastPrice": 10.0, "regularMarketPreviousClose": 9.5}

        @property
        def info(self):
            raise RuntimeError("Too Many Requests. Rate limited. Try after a while.")

    monkeypatch.setattr(Y.yf, "Ticker", Ticker)
    provider = Y.YFinanceProvider()
    out = _in_thread(lambda: provider.batch_quote(["AAA", "BBB", "CCC"]))
    assert out["AAA"]["prev_close"] == 9.5, "the daily bars stood in"
    assert Y._THROTTLE["hits"] == 3, "and the refusal was recorded"


def test_downloads_still_take_the_lock_that_keeps_them_apart():
    import inspect
    src = inspect.getsource(Y.YFinanceProvider.batch_history)
    assert "with _NET_LOCK:\n                    raw = yf.download(" in src
    assert "with _key_lock(key):" in inspect.getsource(Y._cached)
    assert "with _NET_LOCK" not in inspect.getsource(Y._cached)


def test_a_finished_fetch_does_not_wait_behind_callers_waiting_for_a_token():
    # Twelve tokens at 20/s with twenty callers: the eight past the bucket are
    # booked at 0.05s apart. The twelve that had a token finish at 0.2s and
    # must come back then, not when the last booked caller wakes at 0.6s.
    Y._BUCKET.update(tokens=12.0, rate=20.0, last=time.time())
    t0 = time.time()
    back = {}

    def one(i):
        Y._cached("burst%d" % i, 60, lambda: time.sleep(0.2) or i)
        back[i] = time.time() - t0

    threads = [threading.Thread(target=one, args=(i,), daemon=True) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(5)
    times = sorted(back.values())
    assert len(times) == 20, "a fetch never came back"
    assert times[11] < 0.35, "the first twelve returned at %.2fs" % times[11]
    # And the rest were still held to the rate: eight turns 0.05s apart.
    assert times[-1] >= 0.2 + 7 * 0.05 * 0.8, "the queue ran early: %.2fs" % times[-1]


def test_booked_turns_stay_booked_through_a_rate_limit():
    # Below zero the bucket is the queue already waiting. A refusal empties
    # the allowance; zeroing the queue as well would let the next caller in
    # alongside the ones ahead of it.
    Y._BUCKET.update(tokens=-3.0)
    with Y._PACE_LOCK:
        Y._on_throttle()
    assert Y._BUCKET["tokens"] == -3.0
    Y._BUCKET.update(tokens=5.0)
    with Y._PACE_LOCK:
        Y._on_throttle()
    assert Y._BUCKET["tokens"] == 0.0
