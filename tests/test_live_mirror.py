"""A local copy without a working key shows the live site's AI-written panels.

Asked for after the local key turned out to have expired on 2026-09-10: the
Catalyst Library and the weekly update were errors on the local copy while the
live site had both. Everything here runs against fakes. conftest keeps the
mirror off and the network out; the tests below put back exactly the piece
each one is about.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import types
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app import ai, catalysts, live_mirror

ROOT = Path(__file__).resolve().parent.parent
# Taken before conftest's fixture swaps it out, which happens per test.
REAL_KEY_USABLE = ai.key_usable
PLATFORM = ("RAILWAY_ENVIRONMENT", "RAILWAY_GIT_COMMIT_SHA", "RENDER", "FLY_APP_NAME")
LIBRARY = {"available": True, "catalysts": [{"id": "x", "title": "Live catalyst"}],
           "matched": 1, "stored_total": 5, "facets": {}, "scan": {"last_ok_at": "T"}}
WEEKLY = {"available": True, "headline": "Live week", "paragraphs": ["p"]}


@pytest.fixture(autouse=True)
def local(monkeypatch):
    for name in PLATFORM:
        monkeypatch.delenv(name, raising=False)


class _Live:
    """The live site: records every URL asked for, answers from a table."""

    def __init__(self, answers):
        self.answers, self.urls, self.timeouts = answers, [], []

    def __call__(self, url, timeout=None):
        self.urls.append(url)
        self.timeouts.append(timeout)
        path = url[len(live_mirror.LIVE_URL):].split("?")[0]
        answer = self.answers.get(path)
        if isinstance(answer, Exception):
            raise answer
        return json.dumps(answer).encode()


def _mirroring(monkeypatch, answers, mode="auto", key_ok=False):
    live = _Live(answers)
    monkeypatch.setattr(live_mirror, "MODE", mode)
    monkeypatch.setattr(live_mirror, "_http_get", live)
    monkeypatch.setattr(ai, "key_usable", lambda: key_ok)
    return live


# ------------------------------------------------------------- the key check


class _Models:
    def __init__(self, outcome):
        self.outcome, self.calls = outcome, 0

    def list(self, **kwargs):
        self.calls += 1
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return types.SimpleNamespace(data=[])


class _StatusError(Exception):
    def __init__(self, status):
        super().__init__("status %d" % status)
        self.status_code = status


def _sdk(monkeypatch, outcome):
    models = _Models(outcome)
    seen = {}

    class Anthropic:
        def __init__(self, **kwargs):
            seen.update(kwargs)
            self.models = models

    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=Anthropic))
    monkeypatch.setattr(ai, "key_usable", REAL_KEY_USABLE)
    monkeypatch.setattr(ai, "available", lambda: {"enabled": True})
    return models, seen


def test_an_expired_key_is_found_out_before_anything_is_written(monkeypatch):
    models, _ = _sdk(monkeypatch, _StatusError(401))
    assert ai.key_usable() is False
    assert models.calls == 1


def test_a_working_key_is_asked_about_once_in_fifteen_minutes(monkeypatch):
    models, _ = _sdk(monkeypatch, None)
    assert ai.key_usable() is True and ai.key_usable() is True
    assert models.calls == 1


@pytest.mark.parametrize("status", [400, 403])
def test_an_unscoped_or_unpermitted_key_counts_as_unusable(monkeypatch, status):
    _sdk(monkeypatch, _StatusError(status))
    assert ai.key_usable() is False


def test_a_network_failure_is_not_a_refusal(monkeypatch):
    """Switching to another server's panels on a blip is the worse surprise."""
    _sdk(monkeypatch, ConnectionError("offline"))
    assert ai.key_usable() is True
    monkeypatch.setattr(ai, "_KEY_CHECK", {"usable": False, "at": 0.0})
    assert ai.key_usable() is False, "the last real answer stands"


def test_no_key_is_unusable_without_asking(monkeypatch):
    models, _ = _sdk(monkeypatch, None)
    monkeypatch.setattr(ai, "available", lambda: {"enabled": False})
    assert ai.key_usable() is False and models.calls == 0


def test_the_first_refusal_a_writer_meets_settles_it(monkeypatch):
    models, _ = _sdk(monkeypatch, None)
    ai._human_error(_StatusError(401))
    assert ai.key_usable() is False and models.calls == 0


def test_the_check_names_the_workspace_when_one_is_set(monkeypatch):
    _, seen = _sdk(monkeypatch, None)
    monkeypatch.setenv("ANTHROPIC_WORKSPACE_ID", "wrkspc_01abc")
    ai.key_usable()
    assert seen["default_headers"] == {"anthropic-workspace-id": "wrkspc_01abc"}
    assert seen["max_retries"] == 0


# ------------------------------------------------------------ when it mirrors


def test_auto_mirrors_exactly_when_the_key_cannot_be_used(monkeypatch):
    monkeypatch.setattr(live_mirror, "MODE", "auto")
    monkeypatch.setattr(ai, "key_usable", lambda: False)
    assert live_mirror.active() is True
    monkeypatch.setattr(ai, "key_usable", lambda: True)
    assert live_mirror.active() is False


def test_on_and_off_are_honoured(monkeypatch):
    monkeypatch.setattr(ai, "key_usable", lambda: True)
    monkeypatch.setattr(live_mirror, "MODE", "on")
    assert live_mirror.active() is True
    monkeypatch.setattr(ai, "key_usable", lambda: False)
    monkeypatch.setattr(live_mirror, "MODE", "off")
    assert live_mirror.active() is False


@pytest.mark.parametrize("mode", ["auto", "on"])
def test_a_hosted_deployment_never_reads_another_server(monkeypatch, mode):
    """Which is also what stops the live site reading from itself."""
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    monkeypatch.setattr(live_mirror, "MODE", mode)
    monkeypatch.setattr(ai, "key_usable", lambda: False)
    assert live_mirror.active() is False


# ------------------------------------------------------------------ fetching


def test_the_answer_is_marked_and_the_filters_go_with_it(monkeypatch):
    live = _mirroring(monkeypatch, {"/api/catalysts": LIBRARY})
    got = live_mirror.fetch("/api/catalysts", {"status": "all", "q": "oil & gas", "theme": ""})
    assert got["catalysts"][0]["title"] == "Live catalyst"
    assert got["mirror"]["from"] == live_mirror.LIVE_URL
    assert "cannot be used" in got["mirror"]["why"]
    assert live.urls == [live_mirror.LIVE_URL + "/api/catalysts?q=oil+%26+gas&status=all"]


def test_a_copy_is_reused_until_it_ages_and_fresh_skips_it(monkeypatch):
    live = _mirroring(monkeypatch, {"/api/catalysts": LIBRARY})
    live_mirror.fetch("/api/catalysts")
    live_mirror.fetch("/api/catalysts")
    assert len(live.urls) == 1
    live_mirror.fetch("/api/catalysts", fresh=True)
    assert len(live.urls) == 2


def test_a_live_site_that_is_down_costs_one_timeout_a_minute(monkeypatch):
    live = _mirroring(monkeypatch, {"/api/catalysts": OSError("timed out")})
    assert live_mirror.fetch("/api/catalysts") is None
    assert live_mirror.fetch("/api/catalysts") is None
    assert len(live.urls) == 1


def test_an_answer_that_is_not_an_object_is_no_answer(monkeypatch):
    _mirroring(monkeypatch, {"/api/weekly": ["not", "an", "object"]})
    assert live_mirror.fetch("/api/weekly") is None


# -------------------------------------------------------------------- routes


def test_the_library_route_answers_with_the_live_library(monkeypatch):
    live = _mirroring(monkeypatch, {"/api/catalysts": LIBRARY})

    def local_store(**kwargs):
        raise AssertionError("the local store was read")

    monkeypatch.setattr(main.catalysts_mod, "search", local_store)
    body = TestClient(main.app).get("/api/catalysts", params={"sector": "Energy"}).json()
    assert body["catalysts"][0]["title"] == "Live catalyst" and body["mirror"]
    assert "sector=Energy" in live.urls[0] and "status=relevant" in live.urls[0]


def test_with_the_live_site_down_it_shows_its_own_store_and_says_so(monkeypatch):
    _mirroring(monkeypatch, {"/api/catalysts": OSError("down")})
    monkeypatch.setattr(main.catalysts_mod, "search", lambda **k: {"available": True})
    body = TestClient(main.app).get("/api/catalysts").json()
    assert body["mirror_failed"] == {"from": live_mirror.LIVE_URL}
    assert "mirror" not in body


def test_a_copy_with_a_working_key_keeps_its_own_library(monkeypatch):
    live = _mirroring(monkeypatch, {"/api/catalysts": LIBRARY}, key_ok=True)
    monkeypatch.setattr(main.catalysts_mod, "search", lambda **k: {"available": True, "own": 1})
    body = TestClient(main.app).get("/api/catalysts").json()
    assert body == {"available": True, "own": 1} and live.urls == []


def test_the_scan_button_does_not_scan_or_spend_while_mirroring(monkeypatch):
    _mirroring(monkeypatch, {})
    monkeypatch.setattr(main, "WRITE_TOKEN", "")

    def scan(**kwargs):
        raise AssertionError("a scan ran")

    monkeypatch.setattr(main.catalysts_mod, "refresh", scan)
    body = TestClient(main.app).post("/api/catalysts/refresh", json={}).json()
    assert body["available"] is False and "live library" in body["reason"]


def test_the_weekly_route_answers_with_the_live_update(monkeypatch):
    live = _mirroring(monkeypatch, {"/api/weekly": WEEKLY})

    def gather(provider):
        raise AssertionError("this copy tried to write its own")

    monkeypatch.setattr(main.weekly_mod, "gather", gather)
    body = TestClient(main.app).get("/api/weekly").json()
    assert body["headline"] == "Live week" and body["mirror"]["from"] == live_mirror.LIVE_URL
    assert live.urls == [live_mirror.LIVE_URL + "/api/weekly"]


def test_the_weekly_update_is_given_time_to_be_written(monkeypatch):
    """The first request of a week waits for the live site's model."""
    live = _mirroring(monkeypatch, {"/api/weekly": WEEKLY, "/api/catalysts": LIBRARY})
    live_mirror.fetch("/api/weekly")
    live_mirror.fetch("/api/catalysts")
    assert live.timeouts == [120.0, 15.0]


def test_unreachable_and_unable_to_write_says_both_and_does_not_try(monkeypatch):
    _mirroring(monkeypatch, {"/api/weekly": OSError("timed out")})

    def gather(provider):
        raise AssertionError("a write that could only be refused was attempted")

    monkeypatch.setattr(main.weekly_mod, "gather", gather)
    body = TestClient(main.app).get("/api/weekly").json()
    assert body["available"] is False
    assert body["mirror_failed"] == {"from": live_mirror.LIVE_URL}
    assert "could not be fetched" in body["reason"] and "cannot write one" in body["reason"]


def test_unreachable_with_a_working_key_writes_its_own(monkeypatch):
    """OPTIC_MIRROR_LIVE=on with a key: the live site is preferred, not required."""
    _mirroring(monkeypatch, {"/api/weekly": OSError("timed out")}, mode="on", key_ok=True)
    written = []
    monkeypatch.setattr(main.weekly_mod, "gather", lambda provider: written.append(1) or {})
    monkeypatch.setattr(ai, "write_weekly_update", lambda key, facts: {"available": False,
                                                                        "reason": "own"})
    monkeypatch.setattr(ai, "available", lambda: {"enabled": True})
    body = TestClient(main.app).get("/api/weekly").json()
    assert written == [1] and body["reason"] == "own"


def test_force_is_never_passed_to_the_live_site(monkeypatch):
    """Otherwise any local reader could make the live site write, and pay, again."""
    live = _mirroring(monkeypatch, {"/api/weekly": WEEKLY})
    client = TestClient(main.app)
    client.get("/api/weekly")
    client.get("/api/weekly", params={"force": "true"})
    assert len(live.urls) == 2, "force skips this copy's cache"
    assert all("force" not in u for u in live.urls)


def test_the_local_schedule_stands_down_while_mirroring(monkeypatch):
    """Even with a key that works: the live library is the one on the page, so
    a local scan would pay to fill a store nobody is shown."""
    _mirroring(monkeypatch, {}, mode="on", key_ok=True)
    calls = []
    monkeypatch.setattr(catalysts, "refresh", lambda **k: calls.append(k))
    assert catalysts.scheduled() is False
    assert catalysts.run_if_due() is None and calls == []


def test_a_key_that_fails_the_check_stops_the_schedule_even_unmirrored(monkeypatch):
    """A copy set to OPTIC_MIRROR_LIVE=off with an expired key tried every
    hour and recorded a refusal each time."""
    monkeypatch.setattr(live_mirror, "MODE", "off")
    monkeypatch.setattr(ai, "key_usable", lambda: False)
    assert catalysts.scheduled() is False


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
           + "\n".join(_raw_fn(n) for n in ("esc", "httpUrl", "catalystMirrorNote",
                                             "weeklyMirrorNote"))
           + "\n" + scenario + "\nprint('TEST_OK');")
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=30)
    assert "TEST_OK" in out.stdout, out.stdout + out.stderr


def test_the_panels_say_where_their_content_came_from():
    _js("""
      var why = "This copy's Anthropic key cannot be used, so it shows the live site's version instead of writing its own.";
      var note = catalystMirrorNote({mirror: {from: 'https://theopticterminal.com', why: why}});
      assert(note.indexOf('Showing the live library from theopticterminal.com.') > 0, note);
      assert(note.indexOf('cannot be used') > 0, 'the reason');
      var down = catalystMirrorNote({mirror_failed: {from: 'https://theopticterminal.com'}});
      assert(down.indexOf("theopticterminal.com could not be reached") > 0, down);
      assert(catalystMirrorNote({catalysts: []}) === '', 'its own library needs no note');
      var w = weeklyMirrorNote({mirror: {from: 'https://theopticterminal.com', why: why}});
      assert(w.indexOf('From theopticterminal.com') > 0 && w.indexOf('once a week') > 0, w);
      assert(weeklyMirrorNote({available: true}) === '', 'its own update needs no note');
    """)


def test_only_a_web_address_becomes_a_source_link():
    _js("""
      assert(httpUrl('https://www.cnbc.com/x') === 'https://www.cnbc.com/x', 'https');
      assert(httpUrl('http://example.com') === 'http://example.com', 'http');
      assert(httpUrl('javascript:alert(1)') === '', 'a script');
      assert(httpUrl(' javascript:alert(1)') === '', 'a padded script');
      assert(httpUrl(null) === '', 'nothing');
    """)
    assert "${httpUrl(c.source_url) ? `<p class=\"caveat\"><a href=\"${esc(httpUrl(c.source_url))}\"" in APP


def test_the_button_refreshes_from_the_live_site_instead_of_scanning():
    fn = _fn("renderCatalysts")
    assert "${d && d.mirror\n    ? '<button type=\"button\" class=\"bulk-btn\" data-cat-reload>Refresh from the live site</button>'" in fn
    assert "${catalystMirrorNote(d)}" in fn
    click = APP[APP.index("const catReload = evt.target.closest('[data-cat-reload]');"):]
    assert "loadCatalysts(true, true);" in click[:click.index("return;")]
    assert "...(fresh ? { fresh: 'true' } : {})" in _fn("loadCatalysts")


def test_the_weekly_panel_carries_the_note_in_both_states():
    fn = _fn("renderWeekly")
    assert fn.count("${weeklyMirrorNote(w)}") == 2
