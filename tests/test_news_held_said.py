"""Headlines kept from earlier say so.

Reproduced from the code before the fix: when the feed came back empty, the
provider served the last list that had stories in it for up to six hours, and
nothing downstream could tell it from a fresh answer, so a morning's headlines
read as this minute's news. The list now carries when it was fetched, the news
payload passes that on, and the News tab and the chart's news widget say it.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

import app.providers.yf as y
from app import news as news_mod
from app.main import YF_PROVIDER as P

ROOT = Path(__file__).resolve().parent.parent
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
STORY = {"id": "1", "title": "Example Co beats estimates", "summary": "", "publisher": "Wire",
         "published": "2026-10-06T12:00:00Z", "link": "https://example.com/1"}


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    monkeypatch.setattr(y, "_CACHE", {})
    monkeypatch.setattr(y, "_NEWS_GOOD", {})
    monkeypatch.setattr(y, "_wait_turn", lambda: None)


def test_a_fresh_list_is_plain_and_a_held_one_carries_its_time(monkeypatch):
    answers = iter([[STORY], []])
    monkeypatch.setattr(type(P), "_gather_news", lambda self, t, limit: next(answers))
    fresh = P.news("EXM")
    assert fresh == [STORY] and not hasattr(fresh, "fetched_at")
    y._CACHE.clear()                                   # the fresh entry has expired
    held = P.news("EXM")
    assert held == [STORY] and abs(held.fetched_at - time.time()) < 5


def test_the_payload_says_when_its_headlines_were_fetched():
    class Stub:
        def news(self, t, limit=36):
            return y.HeldNews([STORY], time.time() - 3 * 3600)

        def earnings_date(self, t):
            return None

        def quote(self, t):
            return {"name": "Example Co"}

    out = news_mod.analyse(Stub(), "EXM")
    assert out["held"] and "came back empty" in out["held"]["note"]
    assert out["held"]["fetched_at"].endswith("+00:00")

    class Fresh(Stub):
        def news(self, t, limit=36):
            return [STORY]

    assert news_mod.analyse(Fresh(), "EXM")["held"] is None


def test_the_news_tab_says_it():
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = """
      load('tests/support/browser_stubs.js');
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
      var at = new Date(Date.now() - 3 * 3600 * 1000).toISOString();
      print('RESULT:' + JSON.stringify({
        held: newsHeldNote({held: {fetched_at: at, note: 'The headline feed came back empty just now, so these are the stories it returned earlier.'}}),
        fresh: newsHeldNote({held: null})}));
    """
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    got = json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])
    assert "came back empty" in got["held"] and "3h ago" in got["held"]
    assert got["fresh"] == ""
