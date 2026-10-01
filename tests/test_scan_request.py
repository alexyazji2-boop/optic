"""Find stocks: a request in words, read as the screener's filters.

Asked for with another terminal's scanner box: "add this in the discover ->
scan tab for users to look for stocks based on their requests", with "two
options like this", find the symbols now or hand it to the assistant, and the
example "Strong Stocks on the 200 SMA line right now". The screener finds; this
reads. Read here for nothing where it can be, by Pulse for the words it cannot
(behind Pulse's own allowance), and a reading Pulse made is kept so a request is
paid for once. Nothing here touches the network.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.main as main
from app import ai, ai_store
from app.analytics import scan_request as sr

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _f(reading):
    return {(f["field"], f["min"], f["max"]) for f in reading["filters"]}


# ------------------------------------------------------------- read here


def test_the_example_asked_about_is_read_in_full_and_for_nothing():
    r = sr.read("Strong Stocks on the 200 SMA line right now")
    assert _f(r) == {("pct_from_sma200", -3.0, 3.0)}
    assert r["states"] == ["golden"]
    assert r["understood"] == ["Within 3% of the 200-day average",
                               "In an uptrend: the 50-day above the 200-day"]
    assert r["leftover"] == []


@pytest.mark.parametrize("text,filters,states,leftover", [
    ("stocks under $20 with high volume near 52-week highs",
     {("range_position", 90.0, None), ("volume_expansion", 1.3, None), ("price", None, 20.0)}, [], []),
    ("pullbacks in strong uptrends", {("pct_from_sma20", None, 0.0)}, ["golden"], []),
    ("up 20% in the last 3 months above the 50 day", {("roc60", 20.0, None)}, ["above_sma50"], []),
    ("weak names below the 200-day moving average",
     {("pct_from_sma200", None, 0.0), ("roc60", None, 0.0)}, [], []),
    ("breakouts on strong volume",
     {("range_position", 95.0, None), ("volume_expansion", 1.3, None)}, [], []),
    ("golden cross under 50 dollars", {("price", None, 50.0)}, ["golden"], []),
    ("calm stocks above the 200 dma", {("atr_pct", None, 2.0)}, ["above_sma200"], []),
    ("down 15% this month", {("roc20", None, -15.0)}, [], []),
    # What the vocabulary cannot express is left over, never stood in for.
    ("oversold tech stocks with RSI below 30", set(), [], ["oversold", "tech", "rsi", "below", "30"]),
])
def test_common_requests_are_read_here(text, filters, states, leftover):
    r = sr.read(text)
    assert _f(r) == filters and r["states"] == states and r["leftover"] == leftover


def test_a_number_without_a_unit_is_not_taken_for_an_average():
    """"Under 200" could be a price as well as the 200-day; read as either it
    could be wrong, so it is left for the assistant."""
    r = sr.read("stocks under 200")
    assert r["filters"] == [] and r["states"] == [] and r["leftover"] == ["under", "200"]


def test_every_example_on_the_page_is_read_here():
    block = APP[APP.index("const SCAN_ASK_EXAMPLES = ["):]
    examples = re.findall(r"'([^']+)'", block[:block.index("];")])
    assert len(examples) >= 3
    for text in examples:
        r = sr.read(text)
        assert r["leftover"] == [] and (r["filters"] or r["states"]), text


def test_a_reading_is_said_in_the_screeners_own_words():
    assert sr.labels([{"field": "pct_from_sma200", "min": -3, "max": 3},
                      {"field": "price", "min": None, "max": 20},
                      {"field": "volume_expansion", "min": 1.3, "max": None},
                      {"field": "nonsense", "min": 1, "max": 2}], ["golden", "nope"]) == [
        "Distance from 200-day average from -3% to 3%", "Price at most $20",
        "Volume vs 3-month average at least 1.30x", "50-day average above the 200-day"]


def test_the_same_request_differently_typed_is_the_same_key():
    assert sr.cache_key("Oversold  TECH stocks ") == sr.cache_key("oversold tech stocks")


# ------------------------------------------------------------- the server


RANKING = {"ranked_at": time.time(), "universe_size": 2975, "passed": 3, "gates": {},
           "ranked": [
               {"symbol": "GOOGL", "price": 344.08, "sma20": 345.0, "sma50": 342.0, "sma200": 338.6,
                "roc20": -1.0, "roc60": 2.0, "range_position": 0.6, "atr_pct": 1.8,
                "volume_expansion": 1.0, "dollar_volume": 5e9, "score": 44.7},
               {"symbol": "NVDA", "price": 230.9, "sma20": 220.0, "sma50": 217.4, "sma200": 200.2,
                "roc20": 6.0, "roc60": 17.0, "range_position": 0.97, "atr_pct": 2.5,
                "volume_expansion": 1.4, "dollar_volume": 4e10, "score": 63.9},
               {"symbol": "XYZ", "price": 12.0, "sma20": 13.0, "sma50": 14.0, "sma200": 16.0,
                "roc20": -9.0, "roc60": -20.0, "range_position": 0.05, "atr_pct": 5.0,
                "volume_expansion": 0.9, "dollar_volume": 3e7, "score": -30.0}]}


@pytest.fixture
def server(monkeypatch):
    monkeypatch.setattr(main, "_cached_ranking", lambda: RANKING)
    monkeypatch.setattr(main, "_ensure_ranking", lambda ranking: None)
    calls = []

    def reader(text, vocabulary):
        calls.append(text)
        return {"available": True, "filters": [{"field": "pct_from_sma200", "min": -3, "max": 3}],
                "states": ["golden", "invented_state"], "sort": "invented_field",
                "direction": "desc", "unsupported": ["RSI", "sector"]}
    monkeypatch.setattr(main.ai, "read_scan_request", reader)
    monkeypatch.setattr(main.ai, "available", lambda: {"enabled": True})
    monkeypatch.setattr(main, "_spend_guard", lambda request: None)
    return TestClient(main.app), calls


def test_a_request_read_here_runs_with_no_call(server):
    client, calls = server
    out = client.post("/api/screener/ask", json={"text": "Strong stocks on the 200 SMA line right now"}).json()
    assert calls == [] and out["read_by"] == "terminal" and out["unread"] == []
    assert [r["symbol"] for r in out["result"]["rows"]] == ["GOOGL"]


def test_words_left_over_go_to_pulse_once_and_its_reading_is_kept(server):
    client, calls = server
    out = client.post("/api/screener/ask", json={"text": "oversold tech near the 200 line"}).json()
    assert calls == ["oversold tech near the 200 line"] and out["read_by"] == "pulse"
    # Validated against the screener's own vocabulary: nothing invented runs.
    assert out["spec"] == {"filters": [{"field": "pct_from_sma200", "min": -3.0, "max": 3.0}],
                           "states": ["golden"], "sort": "score", "direction": "desc"}
    assert out["unsupported"] == ["RSI", "sector"]
    assert out["understood"] == ["Distance from 200-day average from -3% to 3%",
                                 "50-day average above the 200-day"]
    again = client.post("/api/screener/ask", json={"text": "  Oversold TECH near the 200 line"}).json()
    assert calls == ["oversold tech near the 200 line"], "kept, not paid for twice"
    assert again["read_by"] == "pulse" and again["spec"] == out["spec"]


def test_without_an_allowance_it_says_so_and_reads_what_it_can(server, monkeypatch):
    client, calls = server

    def refuse(request):
        raise HTTPException(status_code=401, detail="Pulse needs a free account.")
    monkeypatch.setattr(main, "_spend_guard", refuse)
    out = client.post("/api/screener/ask", json={"text": "oversold names near 52-week lows"}).json()
    assert calls == [] and out["read_by"] == "terminal"
    assert out["note"] == "Pulse needs a free account." and out["unread"] == ["oversold"]
    assert [r["symbol"] for r in out["result"]["rows"]] == ["XYZ"], "what was read still runs"


def test_nothing_readable_runs_nothing(server, monkeypatch):
    client, _ = server
    monkeypatch.setattr(main.ai, "available", lambda: {"enabled": False})
    out = client.post("/api/screener/ask", json={"text": "companies with good management"}).json()
    assert out["result"] is None and out["understood"] == []
    assert client.post("/api/screener/ask", json={"text": "   "}).status_code == 400


def test_pulse_reads_on_its_own_model_and_is_on_the_ledger():
    src = (ROOT / "app/ai.py").read_text()
    fn = src[src.index("def read_scan_request("):src.index("async def stream_chat(")]
    assert '_ask(\n            client, "scan",' in fn and "model=PULSE_MODEL" in fn
    assert ai_store.FEATURES["scan"] == "Scan requests"


# ------------------------------------------------------------- the page


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


RESPONSE = {"text": "Strong stocks on the 200 SMA line", "read_by": "terminal",
            "understood": ["Within 3% of the 200-day average"], "unread": [], "unsupported": [],
            "note": None, "spec": {"filters": [], "states": ["golden"], "sort": "score",
                                   "direction": "desc"},
            "result": {"available": True, "matched": 1, "considered": 484, "limit": 50,
                       "ranking_age_hours": 2.0,
                       "columns": [{"id": "score", "label": "Trend score", "unit": "", "decimals": 1},
                                   {"id": "price", "label": "Price", "unit": "$", "decimals": 2}],
                       "rows": [{"symbol": "GOOGL", "score": 44.7, "price": 344.08}]}}


def test_the_box_has_both_answers_and_shows_how_it_read():
    out = _jsc("""
      STATE.scanAsk = { text: 'Strong stocks on the 200 SMA line', busy: false, response: %s };
      print('RESULT:' + JSON.stringify({ html: scanAskHTML(),
        prompt: scanAskPulsePrompt('Strong stocks on the 200 SMA line', STATE.scanAsk.response) }));
    """ % json.dumps(RESPONSE))
    html, prompt = out["html"], out["prompt"]
    assert ">Find symbols now</button>" in html and ">Ask Pulse</button>" in html
    assert "Read by the screener" in html and "Within 3% of the 200-day average" in html
    assert 'data-analyse="GOOGL"' in html and "1 of 484 ranked names match" in html
    assert ">Edit as filters</button>" in html
    # Pulse is given the matches in the question, since nothing else carries them.
    assert prompt.startswith("I'm looking for: Strong stocks on the 200 SMA line")
    assert "GOOGL: 44.7, $344.08" in prompt and "1 of 484 ranked names matched" in prompt


def test_ask_pulse_drafts_and_never_sends():
    handler = APP[APP.index("if (evt.target.closest('[data-sc-ask-pulse]')) {"):][:700]
    assert "draftPulse(scanAskPulsePrompt(text, response))" in handler
    assert "sendChat" not in handler


def test_the_box_is_on_the_scan_page_in_both_modes():
    fn = APP[APP.index("function renderScan(cat, res) {"):]
    fn = fn[:fn.index("\nasync function loadScan(")]
    assert fn.count("${renderResearchHub()}${scanAskHTML()}${modeBar}") == 2
