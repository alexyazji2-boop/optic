"""The catalyst library keeps itself current, and every row traces to a story.

Reported as: the catalysts are not up to date. Measured on 2026-09-28, the live
library held nothing and the local one held three catalysts from 2026-08-14,
for three reasons, each tested here.

* It filled only when somebody pressed Scan, and on the hosted terminal that
  button needs the write token. A schedule now scans every CATALYST_SCAN_HOURS,
  read against a record of scans in the store so a deploy does not set one off.
* A scan read the thirty newest stories: 44 minutes of news, of which the model
  saw 25 (a list cap in the prompt builder), 18 from CNBC and MarketWatch, out
  of 494 stories from 33 sources in the week. It now takes the newest from every
  source in turn.
* The model was asked to copy each story's URL back, and none of the stored
  catalysts had one. Stories carry ids now, the model cites them, and the URL,
  source and date come from the story. An answer that cites nothing is dropped.

No test here reaches the network: the feeds, EDGAR and the model are all faked.
"""
from __future__ import annotations

import asyncio
import importlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import app.main as main
from app import ai, catalysts, feeds

ROOT = Path(__file__).resolve().parent.parent
NOW = datetime.now(timezone.utc)


def _iso(hours_ago):
    return (NOW - timedelta(hours=hours_ago)).replace(microsecond=0).isoformat()


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    """A private store, a known interval, and no attempt left stamped by
    another test."""
    monkeypatch.setattr(catalysts, "DB_PATH", str(tmp_path / "catalysts.db"))
    monkeypatch.setattr(catalysts, "_LAST_ATTEMPT", [0.0])
    monkeypatch.setattr(catalysts, "SCAN_EVERY_HOURS", 6.0)
    monkeypatch.setattr(catalysts, "AUTO", True)
    return tmp_path


DIRECTORY = {"XOM": "EXXON MOBIL CORP", "CVX": "CHEVRON CORP",
             "LMT": "LOCKHEED MARTIN CORP"}

STORIES = [
    {"id": "s1", "title": "OPEC+ agrees deeper output cuts", "summary": "One million barrels a day.",
     "source": "BBC News", "desk": "World", "published": _iso(3),
     "url": "https://bbc.example/opec", "access": "open"},
    {"id": "s2", "title": "Oil jumps on the OPEC+ cut", "summary": "Brent up 4%.",
     "source": "Financial Times", "desk": "Top stories", "published": _iso(1),
     "url": "https://ft.example/oil", "access": "paid"},
    {"id": "s3", "title": "Defence budget passes", "summary": "",
     "source": "CNBC", "desk": "Politics", "published": _iso(30),
     "url": "https://cnbc.example/defence", "access": "metered"},
]

OPEC = {"title": "OPEC+ Output Cut, September 2026", "summary": "OPEC+ cut output.",
        "category": "commodity", "horizon": "medium-term", "themes": ["Oil supply"],
        "sectors": ["Energy"], "story_ids": ["s1", "s2"],
        "companies": [{"ticker": "XOM", "directness": "direct", "strength": "moderate",
                       "why": "Producer."}]}


def _scan(monkeypatch, answer, stories=STORIES):
    """A real refresh over fixed stories, with the model's answer faked."""
    seen = {}

    def extract(for_model, library):
        seen["stories"], seen["library"] = for_model, library
        return json.loads(json.dumps(answer)) if answer is not None else None

    monkeypatch.setattr(catalysts, "candidate_stories",
                        lambda hours=168: [dict(s) for s in stories])
    monkeypatch.setattr(catalysts, "ticker_directory", lambda: DIRECTORY)
    monkeypatch.setattr(ai, "extract_catalysts", extract)
    monkeypatch.setattr(ai, "available", lambda: {"enabled": True})
    return catalysts.refresh(trigger="manual"), seen


def _table(name, order):
    with sqlite3.connect(catalysts.DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute("SELECT * FROM %s ORDER BY %s" % (name, order))]


def _rows():
    return _table("catalysts", "event_date DESC")


def _scans():
    return _table("catalyst_scans", "at")


def _seed(**over):
    row = {"id": "iran0000blockade", "event_date": "2026-08-14",
           "title": "U.S. Naval Blockade of Iran, August 2026", "summary": "Old summary.",
           "category": "geopolitical", "horizon": "medium-term",
           "themes": ["Energy security"], "sectors": ["Energy"],
           "companies": [{"ticker": "LMT", "name": "LOCKHEED MARTIN CORP",
                          "directness": "indirect", "strength": "weak", "why": "Defence."}],
           "source_url": None, "source_name": None}
    row.update(over)
    assert catalysts.upsert([row]) == 1
    return row


# ------------------------------------------------------------ what a scan reads


class _Feeds:
    """feeds.load_kind over a table of (source_id, kind, weight, [(title, hours_ago)])."""

    def __init__(self, table):
        self.table = table

    def __call__(self, kind, force=False, sector=None):
        rows = []
        for sid, kind_, weight, items in self.table:
            if kind_ != kind:
                continue
            for title, hours_ago in items:
                rows.append({
                    "title": title, "summary": "",
                    "url": "https://%s.example/%s" % (sid, re.sub(r"\W+", "-", title)),
                    "source": sid.upper(), "source_detail": "", "source_id": sid,
                    "published": _iso(hours_ago) if hours_ago is not None else None,
                    "weight": weight, "access": "open"})
        rows.sort(key=lambda r: r.get("published") or "", reverse=True)
        return rows, []


def test_a_busy_desk_no_longer_takes_the_whole_scan(monkeypatch):
    """Forty market stories inside the hour pushed a two-day-old central-bank
    decision and the whole world desk out of a newest-first cut."""
    monkeypatch.setattr(feeds, "load_kind", _Feeds([
        ("cnbc", "wire", 9, [("market story %d" % i, i / 60) for i in range(40)]),
        ("bbc-world", "wire", 9, [("ceasefire agreed", 20), ("election called", 30)]),
        ("ecb", "macro", 7, [("ECB cuts rates", 50)]),
    ]))
    titles = [s["title"] for s in catalysts.candidate_stories(limit=12)]
    assert len(titles) == 12
    assert {"ceasefire agreed", "election called", "ECB cuts rates"} <= set(titles)
    assert sum(t.startswith("market story") for t in titles) == 9


def test_the_scan_is_newest_first_and_numbered(monkeypatch):
    monkeypatch.setattr(feeds, "load_kind", _Feeds([
        ("a", "wire", 5, [("a1", 5), ("a2", 1)]),
        ("b", "macro", 5, [("b1", 3)]),
    ]))
    got = catalysts.candidate_stories()
    assert [s["title"] for s in got] == ["a2", "b1", "a1"]
    assert [s["id"] for s in got] == ["s1", "s2", "s3"]


def test_undated_and_out_of_window_stories_are_left_out(monkeypatch):
    """within_hours keeps an undated story for the desks; a catalyst is filed
    under its story's date, so here it would be filed under the scan's own."""
    monkeypatch.setattr(feeds, "load_kind", _Feeds([
        ("a", "wire", 5, [("dated", 2), ("undated", None), ("last month", 24 * 30)]),
    ]))
    assert [s["title"] for s in catalysts.candidate_stories(hours=168)] == ["dated"]


def test_one_story_on_two_feeds_is_read_once(monkeypatch):
    monkeypatch.setattr(feeds, "load_kind", _Feeds([
        ("bbc-world", "wire", 9, [("Ceasefire agreed", 2)]),
        ("bbc-business", "wire", 7, [("Ceasefire agreed", 2)]),
    ]))
    assert len(catalysts.candidate_stories()) == 1


def test_the_model_is_shown_ids_and_never_a_url():
    shown = catalysts._for_model(STORIES)
    assert [s["id"] for s in shown] == ["s1", "s2", "s3"]
    assert all("url" not in s and "access" not in s for s in shown)
    assert shown[0]["source"] == "BBC News (World)"


# --------------------------------------------------------------- the model call


class _FakeClient:
    calls: list = []
    reply = '{"catalysts": []}'

    def __init__(self, **kwargs):
        self.messages = self

    def create(self, **kwargs):
        _FakeClient.calls.append(kwargs)
        return types.SimpleNamespace(
            content=[types.SimpleNamespace(text=_FakeClient.reply)], stop_reason="end_turn")


@pytest.fixture
def fake_model(monkeypatch):
    _FakeClient.calls = []
    _FakeClient.reply = '{"catalysts": []}'
    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=_FakeClient))
    monkeypatch.setattr(ai, "available", lambda: {"enabled": True})
    return _FakeClient


def test_every_story_reaches_the_model_not_the_first_25(fake_model):
    stories = [{"id": "s%d" % i, "title": "story %d" % i, "summary": "x" * 280,
                "source": "BBC News (World)", "published": _iso(i)} for i in range(1, 121)]
    ai.extract_catalysts(stories, [{"id": "abc", "title": "Stored", "event_date": "2026-09-01"}])
    body = fake_model.calls[0]["messages"][0]["content"]
    library, _, rest = body.partition("\n\nSTORIES:\n")
    assert library.startswith("LIBRARY:\n")
    assert json.loads(library[len("LIBRARY:\n"):])[0]["id"] == "abc"
    sent = json.loads(rest)                 # whole, so not cut mid-story
    assert len(sent) == 120 and sent[-1]["id"] == "s120"


def test_the_prompt_asks_for_story_ids_updates_and_the_whole_world(fake_model):
    ai.extract_catalysts(catalysts._for_model(STORIES), [])
    system = fake_model.calls[0]["system"][0]["text"]
    assert "story_ids" in system and "existing_id" in system
    assert "not only Washington" in system
    assert "echo back the story's url" not in system
    # A prompt that asks for no dashes should not be made of them.
    assert "—" not in system and "–" not in system


def test_the_answer_comes_back_as_the_models_list(fake_model):
    fake_model.reply = json.dumps({"catalysts": [OPEC]})
    assert ai.extract_catalysts(catalysts._for_model(STORIES), [])[0]["story_ids"] == ["s1", "s2"]


# ------------------------------------------------------------------ the scan


def test_a_catalyst_takes_its_link_source_and_date_from_its_stories(monkeypatch):
    """Not from the model, which here invents both."""
    out, _ = _scan(monkeypatch, [dict(OPEC, event_date="1999-01-01",
                                      source_url="https://invented.example")])
    row = _rows()[0]
    # The link is the newest story a reader can open, the FT one being
    # paywalled, and the date is that story's, so the two never disagree.
    assert row["source_url"] == "https://bbc.example/opec"
    assert row["source_name"] == "BBC News"
    assert row["event_date"] == _iso(3)[:10]
    assert (out["identified"], out["new"], out["written"]) == (1, 1, 1)


def test_the_date_is_the_linked_storys_not_the_newest_cited(monkeypatch):
    """Stories a day apart, so the two rules cannot agree by accident."""
    _scan(monkeypatch, [dict(OPEC, story_ids=["s2", "s3"])])
    row = _rows()[0]
    assert row["source_url"] == "https://cnbc.example/defence"
    assert row["event_date"] == _iso(30)[:10]


def test_a_paywalled_story_is_the_link_when_it_is_the_only_one(monkeypatch):
    _scan(monkeypatch, [dict(OPEC, story_ids=["s2"])])
    assert _rows()[0]["source_url"] == "https://ft.example/oil"


def test_an_answer_citing_no_story_the_scan_read_is_dropped(monkeypatch):
    out, _ = _scan(monkeypatch, [dict(OPEC, story_ids=["s99"]), dict(OPEC, story_ids=[])])
    assert _rows() == []
    assert out["unsourced"] == 2 and out["identified"] == 0
    assert _scans()[-1]["unsourced"] == 2


def test_a_copied_url_still_counts_when_it_is_exact(monkeypatch):
    _scan(monkeypatch, [dict(OPEC, story_ids=None, source_url="https://cnbc.example/defence")])
    assert _rows()[0]["source_url"] == "https://cnbc.example/defence"


def test_a_development_updates_the_stored_catalyst_rather_than_adding_one(monkeypatch):
    _seed()
    out, seen = _scan(monkeypatch, [dict(
        OPEC, existing_id="iran0000blockade", story_ids=["s3"],
        title="U.S. Blockade of Iran Widens, September 2026", summary="New summary.")])
    assert seen["library"][0]["id"] == "iran0000blockade", "the model was shown the library"
    rows = _rows()
    assert len(rows) == 1
    assert rows[0]["title"] == "U.S. Blockade of Iran Widens, September 2026"
    assert rows[0]["event_date"] == _iso(30)[:10], "the date moves to the development"
    assert rows[0]["source_url"] == "https://cnbc.example/defence"
    assert out["new"] == 0 and out["written"] == 1


def test_an_existing_id_the_store_does_not_hold_is_a_new_row(monkeypatch):
    _seed()
    out, _ = _scan(monkeypatch, [dict(OPEC, existing_id="made-up")])
    assert len(_rows()) == 2 and out["new"] == 1


def test_the_same_story_read_again_is_not_filed_twice(monkeypatch):
    """Every story sits in several scans, a week's window scanned every six
    hours. The model is told what is stored and which story each came from;
    if it files one again from the same story regardless, the link finds it."""
    _scan(monkeypatch, [OPEC])
    out, seen = _scan(monkeypatch, [dict(OPEC, title="OPEC+ Deepens Cuts, September 2026")])
    assert seen["library"][0]["stories"] == ["s1"]
    assert len(_rows()) == 1 and out["new"] == 0


def test_an_older_story_never_moves_a_catalyst_back(monkeypatch):
    _seed(event_date=_iso(0)[:10], title="Current title")
    out, _ = _scan(monkeypatch, [dict(OPEC, existing_id="iran0000blockade",
                                      title="Stale title", story_ids=["s3"])])
    row = _rows()[0]
    assert (row["title"], row["event_date"]) == ("Current title", _iso(0)[:10])
    assert out["written"] == 0


def test_the_same_story_read_again_can_correct_its_own_date(monkeypatch):
    """The first live scan stored a catalyst under a newer date than its own
    linked story's. Rereading that story is a correction, not a move back."""
    _seed(event_date=_iso(0)[:10], source_url="https://cnbc.example/defence")
    _scan(monkeypatch, [dict(OPEC, existing_id="iran0000blockade", story_ids=["s3"])])
    assert _rows()[0]["event_date"] == _iso(30)[:10]


def test_an_update_that_brings_no_companies_keeps_the_stored_ones(monkeypatch):
    _seed()
    _scan(monkeypatch, [dict(OPEC, existing_id="iran0000blockade", companies=[],
                             story_ids=["s3"])])
    assert [c["ticker"] for c in json.loads(_rows()[0]["companies"])] == ["LMT"]


def test_two_answers_updating_one_catalyst_keep_the_first(monkeypatch):
    _seed()
    out, _ = _scan(monkeypatch, [
        dict(OPEC, existing_id="iran0000blockade", title="First", story_ids=["s3"]),
        dict(OPEC, existing_id="iran0000blockade", title="Second", story_ids=["s1"])])
    assert [r["title"] for r in _rows()] == ["First"]
    assert out["identified"] == 1


def test_no_dash_reaches_the_page(monkeypatch):
    _scan(monkeypatch, [dict(
        OPEC, title="OPEC+ Output Cut — September 2026",
        summary="The cut—the deepest since 2020—runs 2026–2027.",
        themes=["Oil – supply"],
        companies=[{"ticker": "XOM", "why": "Producer — upstream."}])])
    row = _rows()[0]
    printed = [row["title"], row["summary"], *json.loads(row["themes"]),
               *[c["why"] for c in json.loads(row["companies"])]]
    assert not any("—" in t or "–" in t for t in printed), printed
    assert row["title"] == "OPEC+ Output Cut, September 2026"
    assert row["summary"] == "The cut, the deepest since 2020, runs 2026-2027."


def test_only_one_scan_runs_at_a_time(monkeypatch):
    """In a thread with a deadline: a scan that waited for the lock instead of
    declining would hang the suite here rather than fail it."""
    got = {}
    assert catalysts._SCAN_LOCK.acquire(blocking=False)
    try:
        worker = threading.Thread(
            target=lambda: got.update(zip(("out", "seen"), _scan(monkeypatch, [OPEC]))),
            daemon=True)
        worker.start()
        worker.join(5)
        assert not worker.is_alive(), "the second scan waited for the first"
    finally:
        catalysts._SCAN_LOCK.release()
    assert got["out"]["available"] is False and "already running" in got["out"]["reason"]
    assert got["seen"] == {}, "the model was asked anyway"


def test_every_scan_is_recorded_and_a_failure_says_why(monkeypatch):
    _scan(monkeypatch, None)
    _scan(monkeypatch, [OPEC])
    fail, good = _scans()
    assert (fail["ok"], fail["kind"], fail["scanned"]) == (0, "manual", 3)
    assert fail["reason"] == "Catalyst extraction failed on this attempt."
    assert (good["ok"], good["identified"], good["written"]) == (1, 1, 1)


def test_the_library_reports_its_last_scan_and_its_schedule(monkeypatch):
    monkeypatch.setattr(ai, "available", lambda: {"enabled": True})
    assert catalysts.search()["scan"]["last_ok_at"] is None
    _scan(monkeypatch, [OPEC])
    scan = catalysts.search()["scan"]
    assert scan["last_ok"] is True and scan["last_reason"] is None
    assert scan["last_ok_at"] == scan["last_at"]
    assert scan["last_counts"] == {"scanned": 3, "identified": 1, "written": 1, "unsourced": 0}
    assert scan["every_hours"] == 6.0
    monkeypatch.setattr(catalysts, "AUTO", False)
    assert catalysts.search()["scan"]["every_hours"] is None


def test_a_store_from_before_the_record_is_dated_by_its_newest_catalyst():
    """The local store held three catalysts from a scan on 2026-08-14 and no
    record of any scan, and the page said none had run."""
    _seed()
    newest = _rows()[0]["created_at"]
    scan = catalysts.search()["scan"]
    assert scan["last_ok_at"] == newest and scan["last_counts"] is None


def test_a_row_stored_with_dashes_is_read_without_them():
    """Rows written before the scan cleaned its text are still on the page."""
    _seed(title="U.S. Naval Blockade of Iran \u2014 August 2026",
          summary="A blockade\u2014and a campaign.", themes=["Energy \u2013 security"],
          companies=[{"ticker": "LMT", "why": "Defence \u2014 prime."}])
    c = catalysts.search()["catalysts"][0]
    assert c["title"] == "U.S. Naval Blockade of Iran, August 2026"
    assert c["summary"] == "A blockade, and a campaign."
    assert c["themes"] == ["Energy, security"]
    assert c["companies"][0]["why"] == "Defence, prime."


def test_a_failed_scan_is_reported_beside_the_last_good_one(monkeypatch):
    _scan(monkeypatch, [OPEC])
    _scan(monkeypatch, None)
    scan = catalysts.search()["scan"]
    assert scan["last_ok"] is False
    assert scan["last_reason"] == "Catalyst extraction failed on this attempt."
    assert scan["last_ok_at"] < scan["last_at"]


# -------------------------------------------------------------- the schedule


def _record(hours_ago, ok):
    with sqlite3.connect(catalysts.DB_PATH) as conn:
        conn.executescript(catalysts.SCHEMA)
        conn.execute("INSERT INTO catalyst_scans (at, kind, ok) VALUES (?,?,?)",
                     ((NOW - timedelta(hours=hours_ago)).isoformat(), "scheduled", int(ok)))


def test_a_store_with_no_scans_is_due():
    assert catalysts.scan_due() is True


@pytest.mark.parametrize("hours_ago,due", [(1, False), (5.9, False), (6.1, True), (30, True)])
def test_a_good_scan_holds_for_the_interval(hours_ago, due):
    _record(hours_ago, True)
    assert catalysts.scan_due() is due


@pytest.mark.parametrize("failed_ago,due", [(0.5, False), (1.5, True)])
def test_a_failure_waits_an_hour_not_the_whole_interval(failed_ago, due):
    _record(10, True)
    _record(failed_ago, False)
    assert catalysts.scan_due() is due


def test_an_unreadable_store_is_never_due(monkeypatch, tmp_path):
    """A directory is not a database: every read fails, so would every write."""
    monkeypatch.setattr(catalysts, "DB_PATH", str(tmp_path))
    assert catalysts.last_scan() is None
    assert catalysts.scan_due() is False


def test_the_schedule_needs_the_switch_and_the_assistant(monkeypatch):
    calls = []
    monkeypatch.setattr(catalysts, "refresh", lambda **k: calls.append(k) or {"available": True})
    monkeypatch.setattr(ai, "available", lambda: {"enabled": False})
    assert catalysts.run_if_due() is None
    monkeypatch.setattr(ai, "available", lambda: {"enabled": True})
    monkeypatch.setattr(catalysts, "AUTO", False)
    assert catalysts.run_if_due() is None
    assert calls == []
    monkeypatch.setattr(catalysts, "AUTO", True)
    assert catalysts.run_if_due() == {"available": True}
    assert calls == [{"trigger": "scheduled"}]


def test_a_process_tries_at_most_once_an_hour_whatever_the_store_says(monkeypatch):
    """A store that reads but cannot be written looks due on every pass."""
    calls = []
    monkeypatch.setattr(catalysts, "refresh", lambda **k: calls.append(k) or {})
    monkeypatch.setattr(catalysts, "scan_due", lambda now=None: True)
    monkeypatch.setattr(ai, "available", lambda: {"enabled": True})
    for _ in range(4):
        catalysts.run_if_due()
    assert len(calls) == 1


def test_the_interval_cannot_be_set_below_an_hour(monkeypatch):
    """The loop looks every fifteen minutes; zero would be a call on each look."""
    monkeypatch.setenv("CATALYST_SCAN_HOURS", "0")
    importlib.reload(catalysts)
    try:
        assert catalysts.SCAN_EVERY_HOURS == 1.0
    finally:
        monkeypatch.undo()
        importlib.reload(catalysts)


# ------------------------------------------------------------------ the loop


def _drive_loop(monkeypatch, look, sleeps_before_stop):
    slept = []

    async def fake_sleep(seconds):
        slept.append(seconds)
        if len(slept) >= sleeps_before_stop:
            raise asyncio.CancelledError

    monkeypatch.setattr(main.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(main.catalysts_mod, "run_if_due", look)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(main._catalyst_loop())
    return slept


def test_the_loop_waits_out_the_boot_then_looks_every_fifteen_minutes(monkeypatch):
    looks = []
    slept = _drive_loop(monkeypatch, lambda: looks.append(1), 3)
    assert slept == [main.CATALYST_BOOT_DELAY, main.CATALYST_CHECK_MINUTES * 60,
                     main.CATALYST_CHECK_MINUTES * 60]
    assert len(looks) == 2


def test_a_pass_that_raises_does_not_end_the_loop(monkeypatch):
    looks = []

    def boom():
        looks.append(1)
        raise RuntimeError("disk gone")

    _drive_loop(monkeypatch, boom, 3)
    assert len(looks) == 2


MAIN = (ROOT / "app/main.py").read_text()


def test_the_loop_is_started_at_boot_held_and_cancelled_at_shutdown():
    start = MAIN[MAIN.index("async def _start_tracker()"):]
    start = start[:start.index('\n@app.on_event("shutdown")')]
    assert "app.state.catalyst_task = asyncio.create_task(_catalyst_loop())" in start
    # Above the tracker's switch: TRACKER_AUTO=false must not stop the library.
    assert start.index("catalyst_task") < start.index("if TRACKER_AUTO:")
    stop = MAIN[MAIN.index("async def _stop_tracker()"):]
    assert '"catalyst_task"' in stop[:stop.index("\n\n\n")]


def test_the_button_is_recorded_as_a_manual_scan(monkeypatch):
    from fastapi.testclient import TestClient
    for name in ("RAILWAY_ENVIRONMENT", "RAILWAY_GIT_COMMIT_SHA", "RENDER", "FLY_APP_NAME"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(main, "WRITE_TOKEN", "")
    seen = {}
    monkeypatch.setattr(main.catalysts_mod, "refresh",
                        lambda **k: seen.update(k) or {"available": True})
    r = TestClient(main.app).post("/api/catalysts/refresh", json={})
    assert r.status_code == 200
    assert seen == {"hours": 168, "trigger": "manual"}


# ------------------------------------------------------------------ the page

APP_RAW = (ROOT / "static/app.js").read_text()


def _strip(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"^\s*//.*$", " ", text, flags=re.M)


APP = _strip(APP_RAW)


def _fn(name):
    body = APP[APP.index("function " + name + "("):]
    return body[:body.index("\n}") + 2]


def _raw_fn(name):
    return re.search(r"^(?:async )?function " + name + r"\([^\n]*\) \{.*?^\}",
                     APP_RAW, re.M | re.S).group()


JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _js(scenario):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = ("function assert(v, m) { if (!v) throw new Error(m); }\n"
           "var STATE = { catalystScan: '' };\n"
           "function fmt(v, d) { return Number(v).toFixed(d); }\n"
           "function activeZone() { return 'UTC'; }\n"
           "function stampIn(iso) { return 'STAMP(' + iso + ')'; }\n"
           "function briefAgo(iso) { return 'AGO(' + iso + ')'; }\n"
           + "\n".join(_raw_fn(n) for n in ("esc", "catalystScanLine", "catalystScanProblem",
                                             "catalystEmptyText"))
           + "\n" + scenario + "\nprint('TEST_OK');")
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=30)
    assert "TEST_OK" in out.stdout, out.stdout + out.stderr


def test_the_page_says_when_the_library_last_scanned():
    _js("""
      var line = catalystScanLine({last_ok_at: 'T1', every_hours: 6});
      assert(line === ' · Last scanned STAMP(T1) (AGO(T1)). The library rescans the wires every 6 hours.', line);
      assert(catalystScanLine({last_ok_at: null, every_hours: 6})
             === ' · No scan has finished yet. The library rescans the wires every 6 hours.', 'none yet');
      assert(catalystScanLine({last_ok_at: null, every_hours: null}) === '', 'no schedule, no scan');
      assert(catalystScanLine({last_ok_at: 'T1', every_hours: 1}).indexOf('every 1 hour.') > 0, 'one hour');
      assert(catalystScanLine(undefined) === '', 'a payload from before the schedule');
    """)


def test_a_failed_scan_is_said_once():
    _js("""
      var scan = {last_ok: false, last_reason: 'Catalyst extraction failed on this attempt.', last_at: 'T2'};
      assert(catalystScanProblem(scan).indexOf('did not finish: Catalyst extraction failed') > 0, 'said');
      assert(catalystScanProblem({last_ok: true, last_reason: null}) === '', 'a success is quiet');
      STATE.catalystScan = 'Catalyst extraction failed on this attempt.';
      assert(catalystScanProblem(scan) === '', 'the button already printed it');
    """)


def test_an_empty_library_says_what_will_fill_it():
    _js("""
      assert(catalystEmptyText({stored_total: 4, scan: {}}) === 'Nothing matches these filters.', 'filtered');
      assert(catalystEmptyText({stored_total: 0, scan: {every_hours: 6}}).indexOf('first scheduled scan') > 0, 'scheduled');
      assert(catalystEmptyText({stored_total: 0, scan: {last_ok_at: 'T', every_hours: 6}}).indexOf('No scan so far') === 0, 'scanned, kept nothing');
      assert(catalystEmptyText({stored_total: 0}).indexOf('run a scan') > 0, 'no schedule');
    """)
    # It told a visitor to press a button the hosted terminal refuses them.
    assert "If it is empty, run a scan." not in APP


def test_the_panel_prints_the_line_the_problem_and_the_counts():
    fn = _fn("renderCatalysts")
    assert "catalystScanLine(d.scan)}</p>" in fn
    assert "${catalystScanProblem(d.scan)}" in fn
    assert "${esc(catalystEmptyText(d))}" in fn
    refresh = _fn("refreshCatalysts")
    assert "r.identified ? `, ${r.new || 0} new` : ''" in refresh
    assert "r.unsourced ? ` · ${r.unsourced} with no story behind" in refresh
