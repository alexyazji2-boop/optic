"""The same terminal on a fraction of the model calls.

Asked as "what in the terminal is currently using up my $100 worth of credits",
then "create a model which allows optic to work the same but minimizes the API
usage credits". What was found on 2026-09-30:

- Optic's Read called the model on every rebuild of the brief, and the tracker
  loop rebuilds it every twenty minutes around the clock: about 72 calls a day,
  each carrying ~10,000 tokens of facts. Every archived Read from 2026-09-15 to
  the 30th ended in the mechanical note, so those answers were being paid for
  and thrown away, most likely cut off at the 1,600-token limit.
- The desk, the earnings briefs, the sector reads and the catalyst read were
  kept in module dicts, and Railway starts a new process on every deploy: 22
  commits shipped on the 30th, and each push paid for all of them again.
- Nothing recorded what any call cost, so the question had no answer but the
  code.

So the Read is written once per edition, the pieces are kept on disk, a failed
write is retried a bounded number of times, and every call is in a ledger the
owner can read. Nothing here touches the network: the client is a fake.
"""
from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import types
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app import ai, ai_store, brief

ROOT = Path(__file__).resolve().parent.parent
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _usage(inp=10000, out=900, read=0, write=0, searches=None):
    return types.SimpleNamespace(
        input_tokens=inp, output_tokens=out, cache_read_input_tokens=read,
        cache_creation_input_tokens=write,
        server_tool_use=(types.SimpleNamespace(web_search_requests=searches)
                         if searches is not None else None))


def _msg(text, stop="end_turn", usage=None, model="claude-opus-5-5"):
    return types.SimpleNamespace(content=[types.SimpleNamespace(type="text", text=text)],
                                 stop_reason=stop, usage=usage or _usage(), model=model)


READ = json.dumps({"headline": "Rates lead the tape",
                   "paragraphs": ["## What happened", "Yields fell.", "The S&P held."]})
DESK = json.dumps({"lead": ["Futures are flat."], "scenarios": [], "note": "", "overall": ""})


class _Claude:
    """Anthropic's client, faked: answers in order, then the default, and counts."""

    def __init__(self):
        self.asked, self.answers, self.default, self.delay = [], [], _msg(READ), 0.0
        outer = self

        class Anthropic:
            def __init__(self, **kwargs):
                self.messages = self

            def create(self, **kwargs):
                outer.asked.append(kwargs)
                if outer.delay:
                    time.sleep(outer.delay)
                answer = outer.answers.pop(0) if outer.answers else outer.default
                if isinstance(answer, Exception):
                    raise answer
                return answer
        self.module = types.SimpleNamespace(Anthropic=Anthropic)


@pytest.fixture
def claude(monkeypatch):
    fake = _Claude()
    monkeypatch.setitem(sys.modules, "anthropic", fake.module)
    monkeypatch.setattr(ai, "available", lambda: {"enabled": True})
    return fake


@pytest.fixture
def clock(monkeypatch):
    """The store's clock, which every lifetime and retry window is measured on."""
    now = [time.time()]
    monkeypatch.setattr(ai_store, "time", types.SimpleNamespace(time=lambda: now[0]))
    return now


def _edition(monkeypatch, edition):
    monkeypatch.setattr(brief, "read_edition", lambda now=None: edition)


def _read():
    return brief._morning_read({}, {}, {}, {}, index_regime={"score": 0})


# ------------------------------------------------------------------ editions


@pytest.mark.parametrize("when,edition", [
    ("2026-09-30 00:05", "2026-09-30:overnight"),     # a Wednesday
    ("2026-09-30 08:59", "2026-09-30:overnight"),
    ("2026-09-30 09:00", "2026-09-30:morning"),       # the anchor, before the open
    ("2026-09-30 16:14", "2026-09-30:morning"),
    ("2026-09-30 16:15", "2026-09-30:close"),         # the close, settled
    ("2026-09-30 23:59", "2026-09-30:close"),
    ("2026-10-03 08:00", "2026-10-03:overnight"),     # a Saturday
    ("2026-10-03 09:00", "2026-10-03:closed"),
    ("2026-11-26 12:00", "2026-11-26:closed"),        # Thanksgiving
    ("2026-11-27 13:14", "2026-11-27:morning"),       # the half day after it
    ("2026-11-27 13:15", "2026-11-27:close"),
])
def test_the_edition_in_force(when, edition):
    at = datetime.strptime(when, "%Y-%m-%d %H:%M").replace(tzinfo=brief.ET)
    assert brief.read_edition(at) == edition


def test_a_week_is_nineteen_reads_where_it_was_five_hundred():
    """Three a trading day, two on each weekend day, against one per twenty
    minute rebuild, which is 504 in a week."""
    monday = datetime(2026, 9, 28, tzinfo=brief.ET)
    rebuilds = [monday + timedelta(minutes=20 * i) for i in range(7 * 72)]
    assert len(rebuilds) == 504
    assert len({brief.read_edition(at) for at in rebuilds}) == 19


# ------------------------------------------------------------------ the Read


def test_the_read_is_written_once_an_edition_not_once_a_rebuild(claude, monkeypatch):
    _edition(monkeypatch, "2026-09-30:morning")
    first = _read()
    for _ in range(5):
        again = _read()
    assert len(claude.asked) == 1
    assert again["written_by"] == ai.MODEL and again["paragraphs"] == first["paragraphs"]
    assert again["fallback_available"] is True and again["edition"] == "morning"
    assert again["written_at"]
    _edition(monkeypatch, "2026-09-30:close")
    _read()
    assert len(claude.asked) == 2, "a new edition is a new read"


def test_the_read_is_kept_on_disk_so_a_deploy_does_not_pay_for_it(claude, monkeypatch):
    """There is no copy in memory to lose: the store is the cache."""
    _edition(monkeypatch, "2026-09-30:overnight")
    _read()
    kept, _ = ai_store.kept("read", "2026-09-30:overnight")
    assert kept["headline"] == "Rates lead the tape"
    assert "fallback_available" not in kept, "the served copy is not what is kept"


def test_a_failed_read_is_tried_hourly_and_three_times_at_most(claude, monkeypatch, clock):
    _edition(monkeypatch, "2026-09-30:morning")
    claude.default = _msg("I can't help with that.")
    for minutes in range(0, 6 * 60, 20):              # six hours of rebuilds
        clock[0] += 0 if minutes == 0 else 20 * 60
        out = _read()
        assert "written_by" not in out, "the mechanical note stands in"
    assert len(claude.asked) == 3


def test_two_builds_at_once_pay_for_one_read(claude, monkeypatch):
    _edition(monkeypatch, "2026-09-30:morning")
    claude.delay = 0.3
    out = []
    threads = [threading.Thread(target=lambda: out.append(_read())) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(claude.asked) == 1
    assert [r.get("written_by") for r in out] == [ai.MODEL, ai.MODEL], \
        "the second waited for the first rather than falling back"


def test_a_forced_rebuild_does_not_pay_for_the_read_again(claude, monkeypatch):
    """`/api/brief?force=true` has no guard and the page never sends it, so
    anyone could rebuild the brief, and every rebuild was a paid read."""
    _edition(monkeypatch, "2026-09-30:morning")
    for name in ("_overview", "_macro_section", "_desks"):
        monkeypatch.setattr(brief, name, lambda *a, **k: {"sources": [], "groups": {}})
    monkeypatch.setattr(brief.events, "upcoming", lambda: {"events": []})
    monkeypatch.setattr(brief.global_markets, "build", lambda p: {"available": False})
    monkeypatch.setattr(brief, "_save", lambda key, payload: None)
    monkeypatch.setattr(brief, "_MEM", {})
    for _ in range(3):
        brief.build(None)
    assert len(claude.asked) == 1


def test_an_answer_cut_off_at_its_limit_keeps_its_complete_paragraphs(claude):
    claude.default = _msg('{"headline": "Rates lead", "paragraphs": ["## What happened", '
                          '"First complete.", "Second compl', stop="max_tokens")
    out = ai.write_morning_read({})
    assert out["paragraphs"] == ["## What happened", "First complete."]


def test_both_morning_notes_have_room_to_finish(claude):
    """1,600 tokens was the limit on both, and both failed every day while the
    writers with 3,000 and 4,000 did not. Only what is written is billed."""
    assert ai.READ_MAX_TOKENS >= 4000 and ai.DESK_MAX_TOKENS >= 4000
    ai.write_morning_read({})
    claude.default = _msg(DESK)
    ai.write_morning_desk({"date": "2026-10-01"})
    assert [a["max_tokens"] for a in claude.asked] == [ai.READ_MAX_TOKENS, ai.DESK_MAX_TOKENS]


# ------------------------------------------------------------------ the desk


def _desk():
    return {"date": "2026-10-01",
            "tape": {"futures": [{"symbol": "ES=F", "chg_1d": 0.05}], "vix": {"last": 16.2}}}


def test_the_desk_is_written_once_and_a_deploy_does_not_pay_for_it(claude, monkeypatch):
    claude.default = _msg(DESK)
    monkeypatch.setattr(main, "_DESK_PROSE", {})
    first = main._desk_prose(_desk())
    assert first["lead"] == ["Futures are flat."]
    monkeypatch.setattr(main, "_DESK_PROSE", {})        # a new process
    again = main._desk_prose(_desk())
    assert len(claude.asked) == 1
    assert again["lead"] == first["lead"] and again["tape_marks"] == first["tape_marks"]
    assert again["written_at"] == first["written_at"], "what it was written against stands"


def test_a_desk_that_fails_is_tried_once_more_an_hour_later(claude, monkeypatch, clock):
    claude.default = _msg("no JSON here")
    monkeypatch.setattr(main, "_DESK_PROSE", {})
    assert main._desk_prose(_desk()) is None
    clock[0] += 30 * 60
    assert main._desk_prose(_desk()) is None
    monkeypatch.setattr(main, "_DESK_PROSE", {})        # a deploy does not retry it
    assert main._desk_prose(_desk()) is None
    assert len(claude.asked) == 1
    clock[0] += 31 * 60
    main._desk_prose(_desk())
    clock[0] += 3 * 3600
    main._desk_prose(_desk())
    assert len(claude.asked) == 2


def test_two_readers_on_a_new_day_pay_for_one_desk(claude, monkeypatch):
    claude.default, claude.delay = _msg(DESK), 0.3
    monkeypatch.setattr(main, "_DESK_PROSE", {})
    threads = [threading.Thread(target=main._desk_prose, args=(_desk(),)) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(claude.asked) == 1
    assert main._desk_prose(_desk())["lead"] == ["Futures are flat."]


def test_of_requests_arriving_together_exactly_one_may_write():
    """Held at a barrier until all eight are about to ask, which is the race a
    check followed by a separate count lost: each saw no attempt yet."""
    gate, answers = threading.Barrier(8, timeout=10), []

    def ask():
        gate.wait()
        answers.append(ai_store.claim("desk", "2026-10-01", 2, 3600.0))
    threads = [threading.Thread(target=ask) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(answers) == [False] * 7 + [True]


def test_a_claim_is_refused_once_the_piece_is_kept(clock):
    assert ai_store.claim("desk", "2026-10-01", 2, 3600.0)
    ai_store.keep("desk", "2026-10-01", {"lead": ["x"]})
    clock[0] += 7200
    assert not ai_store.claim("desk", "2026-10-01", 2, 3600.0)


# ------------------------------------------------------- the reads by symbol


@pytest.mark.parametrize("write,cache,ttl,answer", [
    (lambda: ai.write_earnings_brief("NFLX", {"next_report": {"date": "2026-10-20"}}),
     "_EARNINGS_CACHE", "EARNINGS_TTL",
     {"headline": "h", "stance": "two-sided", "paragraphs": ["p"]}),
    (lambda: ai.write_sector_read("XLE", {"row": {}}), "_SECTOR_CACHE", "SECTOR_TTL",
     {"headline": "h", "stance": "cautious", "paragraphs": ["p"]}),
    (lambda: ai.write_catalyst_read("https://www.bls.gov/cpi", {}), "_CATREAD_CACHE",
     "CATREAD_TTL", {"headline": "h", "paragraphs": ["p"]}),
], ids=["earnings", "sector", "catalyst"])
def test_a_read_outlives_a_deploy_for_its_lifetime_and_no_longer(claude, monkeypatch, clock,
                                                                 write, cache, ttl, answer):
    claude.default = _msg(json.dumps(answer))
    first = write()
    monkeypatch.setattr(ai, cache, {})                  # a new process
    assert write() == first
    assert len(claude.asked) == 1
    monkeypatch.setattr(ai, cache, {})
    clock[0] += getattr(ai, ttl) + 1
    write()
    assert len(claude.asked) == 2, "kept for as long as memory kept it, and no longer"


# ------------------------------------------------------------------ the ledger


def _feature(name):
    return next(f for f in ai_store.usage()["features"] if f["feature"] == name)


def test_every_call_is_recorded_with_what_it_used(claude):
    claude.default = _msg(READ, usage=_usage(inp=12000, out=1000))
    ai.write_morning_read({})
    today = _feature("read")["today"]
    assert today["calls"] == 1 and today["input_tokens"] == 12000
    # Opus 5.5 at $4 in and $20 out per million.
    assert today["cost_usd"] == pytest.approx(0.048 + 0.020)


def test_an_answer_thrown_away_is_marked_unused_and_says_why(claude):
    claude.default = _msg("I can't help with that.")
    assert ai.write_morning_read({}) is None
    call = ai_store.usage()["recent"][0]
    assert call["used"] is False and "no usable JSON" in call["note"]
    assert call["cost_usd"] > 0, "it was paid for"
    month = _feature("read")["month"]
    assert month["unused"] == 1 and month["failed"] == 0


def test_a_call_that_raised_is_recorded_as_failed_and_costs_nothing(claude):
    claude.answers = [RuntimeError("overloaded")]
    assert ai.write_morning_read({}) is None
    call = ai_store.usage()["recent"][0]
    assert call["stop_reason"] == "error" and call["cost_usd"] == 0
    assert "overloaded" in call["note"]
    month = _feature("read")["month"]
    assert month["failed"] == 1 and month["unused"] == 0


def test_a_streamed_call_counts_its_web_searches():
    final = types.SimpleNamespace(model="claude-sonnet-5", stop_reason="end_turn",
                                  usage=_usage(inp=25000, out=2000, read=3000, searches=3))
    ai._streamed("pulse", final, ai.PULSE_MODEL)
    # Sonnet 5 at $2 in, $10 out, $0.20 a cache hit, and $10 per 1,000 searches.
    assert _feature("pulse")["today"]["cost_usd"] == pytest.approx(
        0.050 + 0.020 + 0.0006 + 0.03)


def test_both_of_pulses_routes_record_what_they_used():
    src = (ROOT / "app/ai.py").read_text()
    chat = src[src.index("async def stream_chat("):src.index("async def deep_research(")]
    research = src[src.index("async def deep_research("):]
    assert '_streamed("pulse", final, PULSE_MODEL)' in chat
    assert '_streamed("research", final, PULSE_MODEL)' in research


def test_every_writer_asks_through_the_ledger():
    """Parsed, so the docstring that names the call is not counted as one."""
    src = (ROOT / "app/ai.py").read_text()
    tree = ast.parse(src)
    callers = [fn.name for fn in ast.walk(tree)
               if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))
               for node in ast.walk(fn)
               if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
               and node.func.attr == "create"
               and getattr(node.func.value, "attr", None) == "messages"]
    assert callers == ["_ask"], "only _ask calls the API directly: {}".format(callers)
    for feature in ("earnings", "sector", "weekly", "catalyst_scan", "catalyst_read",
                    "desk", "read"):
        assert '_ask(\n            client, "{}",'.format(feature) in src, feature


def test_the_price_list_prices_both_models_the_terminal_calls():
    assert ai_store.price_of(ai.MODEL) == (4.00, 5.00, 0.20, 20.00)
    assert ai_store.price_of(ai.PULSE_MODEL) == (2.00, 2.50, 0.20, 10.00)
    assert ai_store.price_of("claude-haiku-4-5-20251001") == (1.00, 1.25, 0.10, 5.00)
    assert ai_store.price_of("claude-opus-5-20260101") == (5.00, 6.25, 0.50, 25.00)
    assert ai_store.price_of("some-other-model") is None


def test_a_store_that_cannot_be_written_falls_back_to_the_process(claude, monkeypatch,
                                                                  clock):
    """An unmounted volume costs the saving across restarts, never the page, and
    never the bound: the process keeps the piece and counts the attempts itself,
    as the writers' module dicts did before the store existed."""
    monkeypatch.setattr(ai_store, "DB_PATH", "/dev/null/not-a-directory/ai.db")
    _edition(monkeypatch, "2026-09-30:morning")
    assert _read()["written_by"] == ai.MODEL
    assert _read()["written_by"] == ai.MODEL
    assert len(claude.asked) == 1
    assert ai_store.usage()["available"] is False
    claude.default = _msg("no JSON here")
    _edition(monkeypatch, "2026-09-30:close")
    for _ in range(18):                                 # six hours of rebuilds
        _read()
        clock[0] += 20 * 60
    assert len(claude.asked) == 1 + 3, "hourly, and three times an edition at most"


# ------------------------------------------------------------ the owner's page


def test_the_usage_is_the_owners_only(monkeypatch):
    client = TestClient(main.app)
    monkeypatch.setattr(main, "WRITE_TOKEN", "test-write-token")
    refused = client.get("/api/ai/usage")
    assert refused.status_code == 401
    assert "problem reports" not in refused.json()["detail"].lower()
    ok = client.get("/api/ai/usage", headers={"X-Optic-Token": "test-write-token"})
    assert ok.status_code == 200 and ok.json()["available"] is True


APP = (ROOT / "static/app.js").read_text()
HTML = (ROOT / "static/index.html").read_text()


def test_the_page_sits_beside_the_reports_for_the_owner_only():
    assert 'id="view-usage"' in HTML
    assert "usage: $('#view-usage')," in APP
    assert "{ id: 'reports', label: 'Reports', views: ['reports', 'usage', 'accounts'], owner: true }" in APP
    assert "if (view === 'usage') return loadUsage(force);" in APP
    assert "{ view: 'usage', label: 'Claude usage', owner: true," in APP
    assert "usage: 'Claude usage'," in APP
    assert "if (STATE.view === 'usage') loadUsage(true);" in APP
    ticketless = APP[APP.index("const TICKERLESS_VIEWS = ["):]
    assert "'usage'" in ticketless[:ticketless.index("]")]
    fn = APP[APP.index("async function loadUsage("):]
    fn = fn[:fn.index("\n}")]
    assert fn.index("if (!isOwner()) {") < fn.index("fetchUsage(")


def _jsc(script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    out = subprocess.run([exe, "-e", """
      load('tests/support/browser_stubs.js');
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      document.documentElement.style.removeProperty = function () {};
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
    """ + script], capture_output=True, text=True, timeout=120, cwd=str(ROOT))
    assert "RESULT:" in out.stdout, (out.stdout + out.stderr)[-2000:]
    return json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])


def test_the_page_shows_spend_by_feature_and_the_latest_calls():
    bucket = {"calls": 3, "failed": 0, "unused": 1, "cost_usd": 0.204, "unpriced": 0}
    data = {"available": True, "since": "2026-10-01T04:00:00+00:00",
            "features": [{"feature": "read", "label": "Optic's Read", "today": bucket,
                          "week": bucket, "month": bucket}],
            "totals": {"today": bucket, "week": bucket, "month": bucket},
            "recent": [{"at": "2026-10-01T13:02:00+00:00", "feature": "read",
                        "label": "Optic's Read", "model": "claude-opus-5-5",
                        "input_tokens": 12000, "output_tokens": 1000, "used": False,
                        "stop_reason": "max_tokens", "note": "no usable JSON",
                        "cost_usd": 0.068}],
            "method": "Estimated at list prices."}
    html = _jsc("print('RESULT:' + JSON.stringify({ html: usageHTML(%s) }));"
                % json.dumps(data))["html"]
    assert "<td class=\"name\">Optic's Read</td>" in html.replace("&#39;", "'")
    assert "$0.20" in html and "<tfoot>" in html
    assert "Latest calls" in html and "Thrown away" in html and "12,000" in html
    assert "Estimated at list prices." in html
    empty = _jsc("print('RESULT:' + JSON.stringify({ html: usageHTML({ available: true, "
                 "features: [], totals: {}, recent: [] }) }));")["html"]
    assert "No calls recorded yet" in empty


def test_the_read_says_when_it_was_written():
    fn = APP[APP.index("<p class=\"caveat\">${summary.written_at ?"):]
    assert "This read was written ${" in fn[:200]
