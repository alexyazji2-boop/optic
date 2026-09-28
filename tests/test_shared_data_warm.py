"""The rest of a first load's waiting: back-to-back loads, shared data, deploys.

Read off the live site's Server-Timing on 2026-09-28, after cold first loads
had come down to 1.5s to 3.5s:

  back to back   a cold load is twelve to fourteen requests and the limiter's
                 burst was twelve, so MRVL opened a second after LRCX was held
                 at the gate for up to 3.8s.
  shared data    the macro basket and the sector funds are one download each,
                 cached five minutes, and the reader whose load found them
                 expired paid for the refetch: 3.0s to 3.2s of loads otherwise
                 around 1.5s, and the FRED calendar 3.2s of another.
  after deploys  a cold VRSK took 9.4s two minutes after one, about 8s of it in
                 legs that made no request, queued behind the warm-up's
                 downloads at the lock that keeps yf.download calls apart.
"""
from __future__ import annotations

import asyncio
import inspect
import os
import threading
import time

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.providers import yf as Y


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.setattr(Y, "_CACHE", {})
    monkeypatch.setattr(Y, "_BUCKET", {"tokens": Y.YF_BURST, "rate": 20.0, "last": time.time()})
    monkeypatch.setattr(Y, "_THROTTLE", {"until": 0.0, "hits": 0, "last_seen": None})


# ------------------------------------------------------------ the burst


@pytest.mark.skipif("YF_BURST" in os.environ, reason="the burst is set in the environment")
def test_the_burst_covers_two_cold_loads():
    assert Y.YF_BURST == 24
    assert Y.YF_RATE == 2.0, "the sustained rate is not what changed"


# ------------------------------------------------------------ the download lock


def _handoff(first, second):
    """Who gets the lock next when `first` queued before `second`."""
    order, hold = [], threading.Event()

    def holder():
        with Y._NET_LOCK:
            hold.wait(2)

    def waiter(who):
        if who == "job":
            with Y.background():
                with Y._NET_LOCK:
                    order.append(who)
        else:
            with Y._NET_LOCK:
                order.append(who)

    threads = [threading.Thread(target=holder)]
    threads[0].start()
    time.sleep(0.05)
    for who in (first, second):
        threads.append(threading.Thread(target=waiter, args=(who,)))
        threads[-1].start()
        time.sleep(0.05)
    hold.set()
    for t in threads:
        t.join(5)
    return order


def test_a_reader_goes_before_a_job_that_queued_first():
    for _ in range(3):
        assert _handoff("job", "reader") == ["reader", "job"]


def test_readers_still_queue_among_themselves_and_jobs_still_get_in():
    assert sorted(_handoff("reader", "reader")) == ["reader", "reader"]
    assert _handoff("job", "job") == ["job", "job"]


def test_a_job_is_not_held_out_for_good(monkeypatch):
    monkeypatch.setattr(Y, "MAX_YIELD_WAIT", 0.2)
    monkeypatch.setattr(Y._NET_LOCK, "_readers_waiting", 1)   # a reader forever waiting
    got = {}

    def job():
        t0 = time.time()
        with Y.background():
            with Y._NET_LOCK:
                got["took"] = time.time() - t0

    t = threading.Thread(target=job, daemon=True)
    t.start()
    t.join(3)
    assert not t.is_alive(), "the job never got the lock"
    assert 0.15 <= got["took"] < 1.0, got


def test_the_wait_is_reported_as_a_lock_wait():
    hold = threading.Event()

    def holder():
        with Y._NET_LOCK:
            hold.wait(2)

    t = threading.Thread(target=holder)
    t.start()
    time.sleep(0.05)
    threading.Timer(0.2, hold.set).start()
    Y.meter_reset()
    with Y._NET_LOCK:
        pass
    t.join(5)
    assert Y.meter_read()[1] >= 0.15


# ------------------------------------------------------------ refreshing early


def test_inside_refreshing_early_a_late_entry_is_refetched_and_outside_it_is_served():
    fetched = []
    Y._CACHE["shared"] = (time.time() - 210, "old")        # 70% of a 300s life
    Y._CACHE["young"] = (time.time() - 60, "young")        # 20% of it
    assert Y._cached("shared", 300, lambda: fetched.append("a") or "new") == "old"
    with Y.refreshing_early():
        assert Y._cached("shared", 300, lambda: fetched.append("b") or "new") == "new"
        assert Y._cached("young", 300, lambda: fetched.append("c") or "new") == "young"
    assert fetched == ["b"]
    assert Y._cached("shared", 300, lambda: fetched.append("d") or "newer") == "new"


def test_refreshing_early_is_this_threads_and_is_put_back():
    seen = {}
    with Y.refreshing_early():
        t = threading.Thread(target=lambda: seen.update(other=getattr(Y._EARLY, "on", False)))
        t.start()
        t.join(5)
    seen["after"] = getattr(Y._EARLY, "on", False)
    assert seen == {"other": False, "after": False}


# ------------------------------------------------------------ keeping it warm


def test_a_pass_refreshes_every_shared_leg_early_and_survives_one_failing(monkeypatch):
    seen = []

    def rec(name, fail=False):
        def fn(*a, **k):
            seen.append((name, getattr(Y._EARLY, "on", False)))
            if fail:
                raise RuntimeError("feed down")
        return fn

    monkeypatch.setattr(main.macro_mod, "analyse", rec("macro", fail=True))
    monkeypatch.setattr(main.sector_board_mod, "build", rec("board"))
    monkeypatch.setattr(main.YF_PROVIDER, "history", rec("spy"))
    monkeypatch.setattr(main, "_macro_calendar_rows", rec("calendar"))
    main._warm_shared()
    assert seen == [("macro", True), ("board", True), ("spy", True), ("calendar", True)]


class _Stop(BaseException):
    pass


def _run_loop(monkeypatch, passes, read_at):
    runs = []
    sleeps = []

    async def sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) > passes:
            raise _Stop()

    monkeypatch.setattr(main.asyncio, "sleep", sleep)
    monkeypatch.setattr(main, "_warm_shared", lambda: runs.append(Y.in_background()))
    monkeypatch.setattr(main, "_KEEP_WARM", {"read_at": read_at})
    with pytest.raises(_Stop):
        asyncio.run(main._keep_warm_loop())
    return runs


def test_the_loop_warms_at_boot_and_then_only_while_someone_is_reading(monkeypatch):
    assert _run_loop(monkeypatch, 3, read_at=0.0) == [True], "idle: boot only"
    assert _run_loop(monkeypatch, 3, read_at=time.time()) == [True, True, True], (
        "while reading: every pass, in the jobs' lane")


def test_the_dossiers_routes_count_as_reading(monkeypatch):
    monkeypatch.setattr(main, "_KEEP_WARM", {"read_at": 0.0})
    monkeypatch.setattr(main.PROVIDER, "quote", lambda s: {"ticker": s, "price": 1.0})
    TestClient(main.app).get("/api/quote/ABC")
    assert time.time() - main._KEEP_WARM["read_at"] < 5
    main._KEEP_WARM["read_at"] = 0.0

    def build(*a, **k):
        k["timings"].begin()
        return {"ticker": "ABC"}

    monkeypatch.setattr(main, "_swing_snapshot", build)
    TestClient(main.app).get("/api/ticker/ABC")
    assert time.time() - main._KEEP_WARM["read_at"] < 5


def test_the_loop_is_started_and_stopped_with_the_others():
    start = inspect.getsource(main._start_tracker)
    stop = inspect.getsource(main._stop_tracker)
    assert "app.state.keepwarm_task = asyncio.create_task(_keep_warm_loop())" in start
    assert '"keepwarm_task"' in stop
