"""The weekly update is written once a week, not once a process.

`app/ai.py` kept it in a dict, and Railway starts a new process on every
deploy, so every deploy wrote the week's update again. Measured on 2026-09-28:
a write is up to 6,000 output tokens and about 56 seconds, and after one deploy
the first rewrite failed and the retry came back under a different headline,
so readers saw the week's update change within the week. Failures were not
kept either, so while one lasted every visitor paid for another attempt.

Everything here runs against a fake model and a per-test store. `_restart()`
empties what `ai` holds in memory, which is what a new process does not have,
and leaves the store, which is what the volume keeps.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import threading
import time
import types
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app import ai, weekly_store

WEEK = "2026-W40"
# The two headlines production published for one week, either side of a deploy.
BEFORE = "Durable Goods Go Flat as Friday's Jobs Report Takes the Wheel"
AFTER = "Flat Factory Orders Hand the Week to Friday's Jobs Report"
UNUSABLE = "no JSON object in this answer"


def _piece(headline):
    return json.dumps({"headline": headline, "subhead": "The week hinges on payrolls.",
                       "paragraphs": ["## What happened", "Factory orders were flat."]})


class _Model:
    """Anthropic's client, answering each call with the next of `replies`.

    `gate`, when set, holds every call until the test opens it: that is how a
    write is kept in flight while other readers arrive."""
    calls: list = []
    replies: list = []
    gate = None

    def __init__(self, **kwargs):
        self.messages = self

    def create(self, **kwargs):
        _Model.calls.append(kwargs)
        if _Model.gate is not None:
            _Model.gate.wait(10)
        reply = _Model.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return types.SimpleNamespace(content=[types.SimpleNamespace(text=reply)],
                                     stop_reason="end_turn")


class Overloaded(Exception):
    """Shaped like the SDK's: `status_code` is what `_human_error` reads."""
    status_code = 529


@pytest.fixture
def model(monkeypatch, tmp_path):
    _Model.calls, _Model.replies, _Model.gate = [], [], None
    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=_Model))
    monkeypatch.setattr(ai, "available", lambda: {"enabled": True})
    monkeypatch.setattr(weekly_store, "DB_PATH", str(tmp_path / "weekly.db"))
    return _Model


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main.weekly_mod, "gather", lambda provider: {"spy": {}})
    return TestClient(main.app)


def _restart():
    """What a deploy does: the process's memory goes and the volume stays."""
    ai._WEEKLY_CACHE.clear()
    ai._WEEKLY_FAILED.clear()


def _wait_for(condition, seconds=5.0):
    deadline = time.time() + seconds
    while not condition():
        assert time.time() < deadline, "timed out waiting"
        time.sleep(0.01)


def _stored(column):
    with closing(sqlite3.connect(weekly_store.DB_PATH)) as conn:
        return conn.execute("SELECT %s FROM weekly_updates" % column).fetchone()[0]


# ------------------------------------------------------------ across restarts


def test_a_restart_serves_the_update_already_written(model):
    """The regression: a deploy wrote the week again, and it read differently."""
    model.replies = [_piece(BEFORE), _piece(AFTER)]
    first = ai.write_weekly_update(WEEK, {})
    _restart()
    again = ai.write_weekly_update(WEEK, {})
    assert len(model.calls) == 1, "the restart paid for a second write"
    assert again["headline"] == first["headline"] == BEFORE
    assert again["paragraphs"] == first["paragraphs"]
    assert again["written_at"] == first["written_at"]


def test_the_route_serves_it_across_a_restart(model, client):
    model.replies = [_piece(BEFORE), _piece(AFTER)]
    first = client.get("/api/weekly").json()
    _restart()
    again = client.get("/api/weekly").json()
    assert again["available"] is True
    assert again["headline"] == first["headline"] == BEFORE
    assert len(model.calls) == 1


def test_a_key_that_goes_away_does_not_take_the_week_with_it(model, monkeypatch):
    """What is kept is served before anyone asks whether a new one could be written."""
    model.replies = [_piece(BEFORE)]
    ai.write_weekly_update(WEEK, {})
    _restart()
    monkeypatch.setattr(ai, "available", lambda: {"enabled": False})
    assert ai.write_weekly_update(WEEK, {})["headline"] == BEFORE


def test_a_new_week_is_written_fresh(model):
    model.replies = [_piece(BEFORE), _piece(AFTER)]
    ai.write_weekly_update("2026-W40", {})
    _restart()
    assert ai.write_weekly_update("2026-W41", {})["headline"] == AFTER
    assert len(model.calls) == 2


def test_only_what_the_model_wrote_is_stored(model):
    """The method note and disclaimer are put round it on the way out, so an
    edit to either reaches the page on the next deploy, not the next week."""
    model.replies = [_piece(BEFORE)]
    ai.write_weekly_update(WEEK, {})
    assert sorted(json.loads(_stored("payload"))) == ["headline", "paragraphs", "subhead"]


def test_an_unwritable_store_costs_the_restart_not_the_page(model, monkeypatch, tmp_path):
    """An unmounted volume raises from os.makedirs: OSError, not sqlite3.Error."""
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("")
    monkeypatch.setattr(weekly_store, "DB_PATH", str(blocker / "weekly.db"))
    model.replies = [_piece(BEFORE)]
    assert ai.write_weekly_update(WEEK, {})["headline"] == BEFORE
    assert ai.write_weekly_update(WEEK, {})["headline"] == BEFORE
    assert len(model.calls) == 1


# ---------------------------------------------------------------------- force


def test_force_writes_it_again_and_the_new_one_is_kept(model, client):
    model.replies = [_piece(BEFORE), _piece(AFTER)]
    client.get("/api/weekly")
    forced = client.get("/api/weekly", params={"force": "true"}).json()
    assert forced["headline"] == AFTER and len(model.calls) == 2
    _restart()
    assert client.get("/api/weekly").json()["headline"] == AFTER
    assert len(model.calls) == 2
    assert _stored("writes") == 2


def test_a_forced_write_that_fails_leaves_readers_the_one_they_had(model):
    model.replies = [_piece(BEFORE), UNUSABLE]
    ai.write_weekly_update(WEEK, {})
    assert ai.write_weekly_update(WEEK, {}, force=True)["available"] is False
    assert ai.write_weekly_update(WEEK, {})["headline"] == BEFORE
    _restart()
    assert ai.write_weekly_update(WEEK, {})["headline"] == BEFORE
    assert len(model.calls) == 2


def test_force_is_not_held_back_by_a_failure(model):
    """The explicit rebuild is how the operator gets past a failure early."""
    model.replies = [UNUSABLE, _piece(AFTER)]
    ai.write_weekly_update(WEEK, {})
    assert ai.write_weekly_update(WEEK, {}, force=True)["headline"] == AFTER


# ------------------------------------------------------------------- failures


@pytest.mark.parametrize("failure", [UNUSABLE, Overloaded("overloaded_error")],
                         ids=["unusable", "refused"])
def test_a_failure_is_not_retried_on_every_load(model, failure):
    model.replies = [failure, _piece(AFTER)]
    assert ai.write_weekly_update(WEEK, {})["available"] is False
    assert ai.write_weekly_update(WEEK, {})["available"] is False
    assert len(model.calls) == 1, "a page load paid for another attempt"
    # Once the failure has stood its time, the next reader tries again.
    ai._WEEKLY_FAILED[WEEK]["at"] -= ai.WEEKLY_RETRY_SECONDS
    assert ai.write_weekly_update(WEEK, {})["headline"] == AFTER
    assert len(model.calls) == 2


def test_the_failure_says_when_the_next_attempt_is(model):
    model.replies = [UNUSABLE]
    reason = ai.write_weekly_update(WEEK, {})["reason"]
    assert reason == ("The weekly update could not be written on the latest attempt. "
                      "The next attempt is in about 10 minutes.")
    assert "—" not in reason and "–" not in reason
    ai._WEEKLY_FAILED[WEEK]["at"] -= 9.5 * 60
    assert ai.write_weekly_update(WEEK, {})["reason"].endswith(
        "The next attempt is in about 1 minute.")


# -------------------------------------------------------- one write at a time


def test_readers_who_arrive_during_a_write_share_it(model):
    """Each found nothing kept and started a write of its own, and whichever
    finished last replaced the rest."""
    model.gate = threading.Event()
    model.replies = [_piece(BEFORE), _piece(AFTER), _piece("Third"), _piece("Fourth")]
    got = []
    readers = [threading.Thread(target=lambda: got.append(ai.write_weekly_update(WEEK, {})))
               for _ in range(4)]
    readers[0].start()
    _wait_for(lambda: model.calls)
    for reader in readers[1:]:
        reader.start()
    time.sleep(0.2)                     # time for any of them to reach the model
    model.gate.set()
    for reader in readers:
        reader.join(10)
    assert len(model.calls) == 1
    assert [g["headline"] for g in got] == [BEFORE] * 4


def test_a_reader_is_not_held_longer_than_the_wait(model, monkeypatch):
    monkeypatch.setattr(ai, "WEEKLY_WAIT_SECONDS", 0.1)
    model.gate = threading.Event()
    model.replies = [_piece(BEFORE)]
    writer = threading.Thread(target=ai.write_weekly_update, args=(WEEK, {}))
    writer.start()
    _wait_for(lambda: model.calls)
    waited = ai.write_weekly_update(WEEK, {})
    model.gate.set()
    writer.join(10)
    assert waited["available"] is False and "still being written" in waited["reason"]
    # Not held as a failure: the next reader gets the piece.
    assert ai.write_weekly_update(WEEK, {})["headline"] == BEFORE
    assert len(model.calls) == 1
