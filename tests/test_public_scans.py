"""Every scan works for whoever asks, and none of them needs a key.

Reported with a screenshot of Momentum leaders reading "The universe ranking
has not been built yet": "it should work whenever requested. all scans should
be the same, go through all scanning related buttons and make sure they work
without the need of an API key".

Three things were in the way.

* The ranking every scanner page reads was rewritten in place. Opening it
  with "w" empties it before the new one is written, so a page that read it in
  that window got nothing and said it had not been built, and a restart in the
  window left it that way. It is written beside the old one and renamed now.
* Only the tracker's scheduled scan built it, on market days in the session.
  A page that finds none, or one past stale, now starts a build and says how
  far it has got, and the page fills in when it lands.
* "Run a scan now", "Refresh marks" and "Scan for new catalysts" wanted the
  write token, so a reader pressing any of them was asked for a key. They are
  open now: one at a time, and for anyone but the owner no more often than
  half an hour, two minutes and an hour apart, since they cost three thousand
  downloads, a quote per position and a model reading the news. A reader's scan
  runs on the book's own universe; only the owner may hand it a list.
"""
from __future__ import annotations

import json
import os
import time

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.analytics import screen

client = TestClient(main.app)
PLATFORM_VARS = ("RAILWAY_ENVIRONMENT", "RAILWAY_GIT_COMMIT_SHA", "RENDER", "FLY_APP_NAME")


@pytest.fixture(autouse=True)
def hosted_with_a_token(monkeypatch):
    """The live site: hosted, a write token configured, no owner signed in."""
    for name in PLATFORM_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    token = main.WRITE_TOKEN
    main.WRITE_TOKEN = "correct-horse"
    main._PUBLIC_LAST.clear()
    yield
    main.WRITE_TOKEN = token
    main._PUBLIC_LAST.clear()


OWNER = {"X-Optic-Token": "correct-horse"}


@pytest.fixture
def scans(monkeypatch):
    """The tracker's scan and marks, without running either."""
    started = []

    def fake_scan(tickers, trigger):
        # Recorded as it is asked for, not when the task gets round to it.
        started.append({"tickers": tickers, "trigger": trigger})

        async def nothing():
            return {}
        return nothing()

    monkeypatch.setattr(main, "_do_scan", fake_scan)
    monkeypatch.setattr(main.paper, "progress", lambda: {"running": False})
    monkeypatch.setattr(main.paper, "mark_scan_queued", lambda trigger: None)
    monkeypatch.setattr(main.paper, "mark_open_positions", lambda provider, rf: {"marked": 0})
    return started


# ------------------------------------------------------ the portfolio scan


def test_a_reader_can_start_the_portfolio_scan(scans, monkeypatch):
    monkeypatch.setattr(main.paper, "seconds_since_last_scan", lambda: 3600.0)
    r = client.post("/api/tracker/scan", json={})
    assert r.status_code == 200, r.text
    assert r.json()["started"] is True


def test_a_reader_waits_half_an_hour_after_the_last_scan(scans, monkeypatch):
    monkeypatch.setattr(main.paper, "seconds_since_last_scan", lambda: 600.0)
    r = client.post("/api/tracker/scan", json={})
    assert r.status_code == 429
    assert r.json()["detail"] == "A scan ran 10 minutes ago. The next one can start in 20 minutes."


def test_the_owner_is_never_kept_waiting(scans, monkeypatch):
    monkeypatch.setattr(main.paper, "seconds_since_last_scan", lambda: 60.0)
    assert client.post("/api/tracker/scan", json={}, headers=OWNER).status_code == 200


def test_a_reader_cannot_choose_the_names_that_go_into_the_record(scans, monkeypatch):
    monkeypatch.setattr(main.paper, "seconds_since_last_scan", lambda: 3600.0)
    client.post("/api/tracker/scan", json={"tickers": ["ZZZZ"]})
    client.post("/api/tracker/scan", json={"tickers": ["ZZZZ"]}, headers=OWNER)
    tickers = [s["tickers"] for s in scans]
    assert None in tickers, "a reader's scan runs on the book's universe"
    assert ["ZZZZ"] in tickers, "the owner may still hand it a list"


def test_a_scan_already_running_is_said_rather_than_doubled(scans, monkeypatch):
    monkeypatch.setattr(main.paper, "progress", lambda: {"running": True})
    assert client.post("/api/tracker/scan", json={}).status_code == 409


# ------------------------------------------------------------------ marks


def test_marks_are_open_two_minutes_apart(scans):
    assert client.post("/api/tracker/mark", json={}).status_code == 200
    again = client.post("/api/tracker/mark", json={})
    assert again.status_code == 429
    assert again.json()["detail"] == ("A refresh ran less than a minute ago. "
                                      "The next one can start in 2 minutes.")
    assert client.post("/api/tracker/mark", json={}, headers=OWNER).status_code == 200


# ------------------------------------------------------------ catalysts


def test_the_catalyst_scan_is_open_an_hour_apart(monkeypatch):
    asked = []
    monkeypatch.setattr(main.live_mirror, "active", lambda: False)
    monkeypatch.setattr(main.catalysts_mod, "refresh",
                        lambda hours, trigger: asked.append(hours) or {"available": True})
    monkeypatch.setattr(main.catalysts_mod, "seconds_since_last_scan", lambda: 7200.0)
    assert client.post("/api/catalysts/refresh?hours=720").status_code == 200
    assert asked == [168], "a reader scans the default window, not the most expensive one"
    monkeypatch.setattr(main.catalysts_mod, "seconds_since_last_scan", lambda: 1200.0)
    r = client.post("/api/catalysts/refresh")
    assert r.status_code == 429
    assert r.json()["detail"] == ("The last catalyst scan ran 20 minutes ago. "
                                  "The next one can start in 40 minutes.")
    assert client.post("/api/catalysts/refresh?hours=720", headers=OWNER).status_code == 200
    assert asked[-1] == 720


# ------------------------------------------------- the ranking, on request


@pytest.fixture
def no_ranking(monkeypatch):
    started = []
    monkeypatch.setattr(main, "_cached_ranking", lambda: None)
    monkeypatch.setattr(main.paper, "progress", lambda: {"running": False})
    monkeypatch.setattr(main.screen_mod, "building", lambda path="": False)

    def spawn():
        # Started, and part of the way through: it keeps running.
        started.append("ranking-build")
        main._RANKING_BUILD.update(done=1200, total=2977)

    monkeypatch.setattr(main, "_spawn_ranking_build", spawn)
    main._RANKING_BUILD.update(running=False, done=0, total=0, failed_at=None, error=None)
    yield started
    main._RANKING_BUILD.update(running=False, done=0, total=0, failed_at=None, error=None)


def test_a_scan_with_no_ranking_starts_one_and_says_how_far_it_has_got(no_ranking):
    out = client.get("/api/scanners/momentum").json()
    assert out["available"] is False
    assert out["building"] == {"done": 1200, "total": 2977}
    assert out["reason"].startswith("Building the universe ranking now. 1,200 of 2,977 symbols")
    assert "fill in by themselves" in out["reason"]
    # And a second page asking meanwhile does not start a second build.
    client.get("/api/scanners/breakout")
    client.post("/api/screener", json={})
    assert no_ranking == ["ranking-build"]


def test_every_scanner_page_asks_for_it(no_ranking):
    assert client.get("/api/scanners").json()["building"] == {"done": 1200, "total": 2977}
    screen_out = client.post("/api/screener", json={}).json()
    assert screen_out["building"] == {"done": 1200, "total": 2977}
    assert screen_out["reason"].startswith("Building the universe ranking now.")


def test_a_stale_ranking_still_answers_while_a_fresh_one_builds(no_ranking, monkeypatch):
    old = {"ranked_at": time.time() - 40 * 3600,
           "ranked": [{"symbol": "AAA", "price": 10.0, "score": 50.0, "roc20": 5.0,
                       "roc60": 9.0, "range_position": 0.9, "atr_pct": 2.0}]}
    monkeypatch.setattr(main, "_cached_ranking", lambda: old)
    out = client.get("/api/scanners/momentum").json()
    assert out["available"] is True, "yesterday's rows beat no rows"
    assert out["building"] == {"done": 1200, "total": 2977}
    assert no_ranking == ["ranking-build"]


def test_a_fresh_ranking_starts_nothing(no_ranking, monkeypatch):
    monkeypatch.setattr(main, "_cached_ranking", lambda: {"ranked_at": time.time(),
                                                          "ranked": [{"symbol": "AAA"}]})
    out = client.get("/api/scanners/momentum").json()
    assert "building" not in out
    assert no_ranking == []


def test_a_failed_build_waits_before_the_next_attempt(no_ranking):
    main._RANKING_BUILD.update(failed_at=time.time(), error="HTTP 429")
    out = client.get("/api/scanners/momentum").json()
    assert no_ranking == [], "a refusal answered at once is a refusal again"
    assert "could not be built just now" in out["reason"]
    main._RANKING_BUILD.update(failed_at=time.time() - main.RANKING_RETRY_S - 1)
    client.get("/api/scanners/momentum")
    assert no_ranking == ["ranking-build"]


def test_the_tracker_building_one_is_not_raced(no_ranking, monkeypatch):
    monkeypatch.setattr(main.paper, "progress",
                        lambda: {"running": True, "done": 800, "total": 2977})
    out = client.get("/api/scanners/momentum").json()
    assert no_ranking == []
    assert out["building"] == {"done": 800, "total": 2977}


# --------------------------------------------------------- the file itself


def test_the_ranking_file_is_replaced_whole_and_never_left_half_written(tmp_path, monkeypatch):
    path = str(tmp_path / "screen_ranking.json")
    screen._save_disk_cache("k", {"ranked_at": 1.0, "ranked": [{"symbol": "OLD"}]}, path)

    real_dump = json.dump

    def dies_half_way(obj, handle, *a, **kw):
        handle.write('{"key": "k", "ranking": {"ranked": [')
        raise OSError("disk full")

    monkeypatch.setattr(screen.json, "dump", dies_half_way)
    screen._save_disk_cache("k", {"ranked_at": 2.0, "ranked": [{"symbol": "NEW"}]}, path)
    monkeypatch.setattr(screen.json, "dump", real_dump)
    with open(path) as fh:
        kept = json.load(fh)
    assert kept["ranking"]["ranked"] == [{"symbol": "OLD"}], "the old ranking survives"
    assert os.listdir(str(tmp_path)) == ["screen_ranking.json"], "no temp file left behind"


def test_a_second_build_waits_for_the_first_and_uses_it(monkeypatch):
    """Two builds of three thousand symbols at once is the load that earns the
    feed's rate limit. The second waits, then takes what the first built."""
    import threading
    calls = []
    gate = threading.Event()

    def slow_rank(provider, symbols, *a, **kw):
        calls.append(1)
        gate.wait(2)
        return {"ranked_at": time.time(), "ranked": [], "universe_size": len(symbols)}

    monkeypatch.setattr(screen, "_rank", slow_rank)
    monkeypatch.setattr(screen, "_save_disk_cache", lambda *a, **kw: None)
    with screen._CACHE_LOCK:
        screen._CACHE.clear()
    # A file of its own, so no other build's lock is in play.
    name = "dedupe-test"
    kwargs = {"cache_name": name}
    t1 = threading.Thread(target=screen.run, args=(None, ["AAA", "BBB"]), kwargs=kwargs)
    t1.start()
    time.sleep(0.2)
    assert screen.building(screen.cache_path_for(name))
    t2 = threading.Thread(target=screen.run, args=(None, ["AAA", "BBB"]), kwargs=kwargs)
    t2.start()
    time.sleep(0.2)
    gate.set()
    t1.join(3)
    t2.join(3)
    assert calls == [1], "built once"
    assert not screen.building(screen.cache_path_for(name))
