"""The scheduled jobs' fetches wait for a reader's.

One limiter paces every Yahoo request in the process, and the jobs spend the
same allowance a reader's first load needs: the watch runner can be twenty
minutes of requests every half hour, a tracker scan is three hundred, and the
homepage's earnings scan about a hundred and fifty, which the warm-up runs
straight after every deploy. On the live site two minutes after one (NTNX,
2026-09-28) a cold first load took 12.8s with its legs held at the gate for up
to 7.4s; three minutes later FTNT's were held for none.

A job now waits for a full bucket before each request. It still runs at the
full sustained rate when nobody is reading, and a reader always finds the
burst waiting.
"""
from __future__ import annotations

import asyncio
import threading
import time

import pytest

import app.main as main
from app.providers import yf as Y


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.setattr(Y, "_CACHE", {})
    monkeypatch.setattr(Y, "_BUCKET", {"tokens": Y.YF_BURST, "rate": 20.0, "last": time.time()})
    monkeypatch.setattr(Y, "_THROTTLE", {"until": 0.0, "hits": 0, "last_seen": None})
    monkeypatch.setattr(Y, "YF_RATE_FLOOR", 0.25)


def _timed(fn):
    t0 = time.time()
    fn()
    return time.time() - t0


def test_a_job_waits_for_a_full_bucket_and_a_reader_does_not():
    Y._BUCKET.update(tokens=Y.YF_BURST - 6, last=time.time())   # six short, 0.3s at 20/s
    assert _timed(lambda: Y._cached("r", 60, lambda: 1)) < 0.05, "a reader was held"
    Y._BUCKET.update(tokens=Y.YF_BURST - 6, last=time.time())
    with Y.background():
        took = _timed(lambda: Y._cached("j", 60, lambda: 1))
    assert 0.25 <= took < 1.0, "the job went at %.2fs" % took


def test_a_job_waiting_holds_nothing_a_reader_needs():
    # The same key: the job is still waiting for its turn when the reader asks.
    Y._BUCKET.update(tokens=0.0, last=time.time())             # 0.6s to full
    fetched = []

    def job():
        with Y.background():
            Y._cached("shared", 60, lambda: fetched.append("job") or "job's")

    t = threading.Thread(target=job)
    t.start()
    time.sleep(0.05)
    took = _timed(lambda: Y._cached("shared", 60, lambda: fetched.append("reader") or "reader's"))
    t.join(5)
    assert took < 0.1, "the reader queued behind the job: %.2fs" % took
    assert fetched == ["reader"], "fetched twice: %r" % fetched


def test_a_job_that_never_sees_a_full_bucket_goes_ahead_anyway(monkeypatch):
    monkeypatch.setattr(Y, "MAX_YIELD_WAIT", 0.2)
    monkeypatch.setattr(Y, "_BUCKET", {"tokens": -100.0, "rate": 20.0, "last": time.time()})
    with Y.background():
        took = _timed(lambda: Y._yield_to_readers())
    assert 0.15 <= took < 0.6, took


def test_a_job_keeps_the_full_rate_when_nobody_reads():
    # Ten requests at 20/s from a full bucket: one now, then one per refill.
    with Y.background():
        took = _timed(lambda: [Y._cached("n%d" % i, 60, lambda: 1) for i in range(10)])
    assert took < 9 / 20.0 * 1.6, "the job ran slower than the rate: %.2fs" % took


def test_the_lane_belongs_to_the_thread_and_is_put_back():
    seen = {}
    with Y.background():
        t = threading.Thread(target=lambda: seen.update(other=Y.in_background()))
        t.start()
        t.join(5)
        with Y.background():
            pass
        seen["inner"] = Y.in_background()
    seen["after"] = Y.in_background()
    assert seen == {"other": False, "inner": True, "after": False}


def test_an_ungated_fetch_does_not_yield():
    # The derived caches (the quote over the shared .info) never reach the
    # network themselves, so they have no turn to wait for.
    Y._BUCKET.update(tokens=0.0, last=time.time())
    with Y.background():
        assert _timed(lambda: Y._cached("derived", 60, lambda: 1, gate=False)) < 0.05


# ------------------------------------------------------------ who is a job


def test_a_readers_request_runs_in_the_readers_lane():
    async def request():
        return await main._run(Y.in_background)

    assert asyncio.run(request()) is False


class _Stop(BaseException):
    pass


def test_a_scan_runs_in_the_jobs_lane(monkeypatch):
    seen = []
    monkeypatch.setattr(main.paper, "run_scan", lambda *a, **k: seen.append(Y.in_background()) or {})
    monkeypatch.setattr(main, "_raise_scan_alerts", lambda result: None)
    asyncio.run(main._do_scan(None, "manual"))
    assert seen == [True]
    assert main._BACKGROUND_JOB.get() is False, "it leaked out of the scan's own task"


def test_the_tracker_loop_runs_in_the_jobs_lane(monkeypatch):
    async def instant(*a, **k):
        return None

    def sweep():
        raise _Stop(Y.in_background())

    monkeypatch.setattr(main.asyncio, "sleep", instant)
    monkeypatch.setattr(main.app.state, "last_account_sweep", None, raising=False)
    monkeypatch.setattr(main.accounts_db, "sweep", sweep)
    with pytest.raises(_Stop) as stop:
        asyncio.run(main._tracker_loop())
    assert stop.value.args == (True,)


def test_the_catalyst_loop_runs_in_the_jobs_lane(monkeypatch):
    def run_if_due():
        raise _Stop(Y.in_background())

    monkeypatch.setattr(main, "CATALYST_BOOT_DELAY", 0)
    monkeypatch.setattr(main.catalysts_mod, "run_if_due", run_if_due)
    with pytest.raises(_Stop) as stop:
        asyncio.run(main._catalyst_loop())
    assert stop.value.args == (True,)


def test_the_earnings_scans_run_in_the_jobs_lane_whoever_asks(monkeypatch):
    seen = []
    monkeypatch.setattr(main, "_PRIORITY_CACHE", {})
    monkeypatch.setattr(main, "_EW_CACHE", {})
    monkeypatch.setattr(main, "_cached_ranking", lambda: {})
    monkeypatch.setattr(main.priority_mod, "build",
                        lambda *a, **k: seen.append(("board", Y.in_background())) or {})
    monkeypatch.setattr(main.earnings_week_mod, "build",
                        lambda *a, **k: seen.append(("week", Y.in_background())) or {"days": []})
    asyncio.run(main.priority_board())
    asyncio.run(main.earnings_week_calendar(offset=0))
    assert seen == [("board", True), ("week", True)]
