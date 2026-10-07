"""An aged Read is served at once and rebuilt behind it.

Today's Read was rebuilt on the reader's request once its copy was twenty
minutes old. The background loop and the cache both run on twenty minutes, so
for much of every cycle the first reader to open Markets paid for the build:
2 to 30 seconds in the recorded builds, 14 and 39 measured from a browser,
behind one line of "Loading today's Read". The aged copy carries its own "Last
updated" and is served as what it is, with `refreshing` saying a newer one is
coming. A day with no Read yet still builds on the request.
"""
from __future__ import annotations

import os
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

from app import brief


@pytest.fixture
def store(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setattr(brief, "DB_PATH", os.path.join(tmp, "brief.db"))
        brief._MEM.clear()
        yield
        brief._MEM.clear()


@pytest.fixture
def builds(monkeypatch):
    """Stand in for the real build: count calls, hold each one until released."""
    calls, release = [], threading.Event()

    def build(provider, day=None):
        calls.append(threading.current_thread().name)
        release.wait(5)
        payload = {"day": day, "built_at": datetime.now(timezone.utc).isoformat(), "v": "new"}
        brief._save(day, payload)
        with brief._LOCK:
            brief._MEM[day] = {"at": time.time(), "payload": payload}
        return payload

    monkeypatch.setattr(brief, "build", build)
    return calls, release


def _aged(day, minutes):
    built = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
    brief._save(day, {"day": day, "built_at": built, "v": "old"})


def _wait_for(pred, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.01)
    return False


def test_an_aged_read_is_served_now_and_rebuilt_behind_it(store, builds):
    calls, release = builds
    today = brief.today_key()
    _aged(today, 45)
    started = time.time()
    out = brief.state(object())
    assert time.time() - started < 1.0, "the reader waited for the build"
    assert out["v"] == "old" and out["stale"] is True and out["refreshing"] is True
    assert _wait_for(lambda: len(calls) == 1), "no rebuild was started"
    assert calls == ["brief-rebuild"], "it ran on the reader's thread"
    release.set()
    assert _wait_for(lambda: brief.state(object()).get("v") == "new")
    assert "stale" not in brief.state(object())


def test_a_burst_of_readers_starts_one_build(store, builds):
    calls, release = builds
    _aged(brief.today_key(), 45)
    outs = [brief.state(object()) for _ in range(5)]
    assert all(o["refreshing"] is True for o in outs)
    assert _wait_for(lambda: len(calls) == 1)
    time.sleep(0.05)
    assert len(calls) == 1, "one build each"
    release.set()


def test_a_fresh_read_is_served_without_a_build(store, builds):
    calls, release = builds
    _aged(brief.today_key(), 5)
    out = brief.state(object())
    assert out["v"] == "old" and "stale" not in out and calls == []


def test_a_day_with_no_read_yet_still_builds_on_the_request(store, builds):
    calls, release = builds
    release.set()
    out = brief.state(object())
    assert out["v"] == "new" and calls == [threading.current_thread().name]


def test_force_still_rebuilds_in_the_foreground(store, builds):
    calls, release = builds
    release.set()
    _aged(brief.today_key(), 45)
    out = brief.state(object(), force=True)
    assert out["v"] == "new" and calls == [threading.current_thread().name]


def test_the_page_offers_the_newer_read_rather_than_repainting():
    app = open("static/app.js", encoding="utf-8").read()
    load = app.split("async function loadBrief(force, opts = {}) {", 1)[1].split("\n}\n", 1)[0]
    assert "if (data.refreshing === true && !day) watchForNewerBrief(data);" in load
    watch = app.split("function watchForNewerBrief(shown) {", 1)[1].split("\n}\n", 1)[0]
    assert "renderBrief" not in watch, "it repaints under the reader"
    assert "data-brief-newer" in watch
    assert "closest('[data-brief-newer]')" in app
