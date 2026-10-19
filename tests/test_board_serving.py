"""Home's slow boards are served while they rebuild (owner, 2026-10-18).

A cold first load of Home waited 90 s on /api/priority and /api/earnings-week:
each is a scan of about 150 companies, and a reader who arrived while it ran
waited for all of it. Now the last build is served at once with its age, a
fresh one runs in the jobs' lane, and the build is kept on disk so a deploy
starts from it. A build from another New York day is never served. With no
usable build, a `quick` request (v2) answers "building" after BOARD_WAIT
seconds; any other (Classic, which keeps its answer for half an hour) waits.
"""
import asyncio
import time

from app import main

ALWAYS = lambda at: True   # noqa: E731  these tests are not about the day a board was built


def test_a_fresh_board_is_served_without_a_rebuild(monkeypatch):
    calls = []
    cache = {"k": {"at": time.time(), "data": {"available": True, "n": 1}}}
    out = asyncio.run(main._served_while_rebuilt("t1", cache, "k", 600, lambda: calls.append(1) or {}, "building", usable=ALWAYS))
    assert out == {"available": True, "n": 1} and calls == []


def test_a_stale_board_is_served_at_once_and_rebuilt_behind_it(monkeypatch):
    cache = {"k": {"at": time.time() - 3600, "data": {"available": True, "n": 1}}}

    async def go():
        out = await main._served_while_rebuilt("t2", cache, "k", 600, lambda: {"available": True, "n": 2}, "building", usable=ALWAYS)
        await main._BOARD_BUSY["t2"]
        return out
    out = asyncio.run(go())
    assert out["n"] == 1 and out["served_stale"] is True and out["built_seconds_ago"] >= 3600
    assert cache["k"]["data"] == {"available": True, "n": 2}


def test_a_slow_first_build_answers_building_instead_of_holding_the_page(monkeypatch):
    monkeypatch.setattr(main, "BOARD_WAIT", 0.05)

    def slow():
        time.sleep(0.4)
        return {"available": True, "n": 3}
    cache = {}

    async def go():
        first = await main._served_while_rebuilt("t3", cache, "k", 600, slow, "Gathering report dates.", quick=True)
        await main._BOARD_BUSY["t3"]
        second = await main._served_while_rebuilt("t3", cache, "k", 600, slow, "Gathering report dates.", quick=True)
        return first, second
    first, second = asyncio.run(go())
    assert first == {"available": False, "building": True, "reason": "Gathering report dates."}
    assert second == {"available": True, "n": 3}


def test_a_board_survives_a_restart_from_disk(monkeypatch):
    async def go():
        await main._served_while_rebuilt("t4", {}, "k", 600, lambda: {"available": True, "n": 4}, "building")
        await main._BOARD_BUSY["t4"]
    asyncio.run(go())
    # a new process: nothing in memory, the file is still there
    calls = []
    out = asyncio.run(main._served_while_rebuilt("t4", {}, "k", 600, lambda: calls.append(1) or {}, "building", usable=ALWAYS))
    assert out == {"available": True, "n": 4} and calls == []


def test_a_failed_rebuild_keeps_the_last_board(monkeypatch):
    cache = {"k": {"at": time.time() - 3600, "data": {"available": True, "n": 5}}}

    def broken():
        raise RuntimeError("provider down")

    async def go():
        await main._served_while_rebuilt("t5", cache, "k", 600, broken, "building", usable=ALWAYS)
        await main._BOARD_BUSY["t5"]
        return await main._served_while_rebuilt("t5", cache, "k", 600, broken, "building", usable=ALWAYS)
    out = asyncio.run(go())
    assert out["n"] == 5 and out["served_stale"] is True


def test_the_earnings_week_is_keyed_by_the_week_it_covers():
    """A cached answer from last week is never served as this week's."""
    fn = open(main.__file__).read()
    fn = fn[fn.index("async def earnings_week_calendar("):]
    fn = fn[:fn.index("\n\n\n")]
    assert "week_bounds(offset)" in fn and "(offset, week)" in fn


def test_without_quick_a_first_build_is_waited_for_as_before(monkeypatch):
    """Classic keeps its board for half an hour, so it must not be handed "building"."""
    monkeypatch.setattr(main, "BOARD_WAIT", 0.05)

    def slow():
        time.sleep(0.3)
        return {"available": True, "n": 6}
    out = asyncio.run(main._served_while_rebuilt("t6", {}, "k", 600, slow, "building"))
    assert out == {"available": True, "n": 6}


def test_a_board_from_another_day_is_not_served(monkeypatch):
    """Its rows say today and past as of the day it was built."""
    yesterday = time.time() - 86400 * 1.5
    cache = {"k": {"at": yesterday, "data": {"available": True, "n": 7}}}
    out = asyncio.run(main._served_while_rebuilt("t7", cache, "k", 600, lambda: {"available": True, "n": 8}, "building"))
    assert out == {"available": True, "n": 8}
    assert main._same_market_day(time.time()) and not main._same_market_day(yesterday)
