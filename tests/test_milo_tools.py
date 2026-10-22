"""Milo looks up Optic's data itself (app/milo_tools.py, the loop in ai.stream_chat), 2026-10-15.

The owner's acceptance case: from a fresh conversation with no page context, "What does the updated
call/put flow, walls and gamma look like on AMD?" got "the current page does not contain options data,
open AMD's Options tab". Root cause, measured: the server fetched AMD's whole analysis, but as one
261,550-character block it exceeded the context budget's 14,000-character section cap and was dropped
whole, so the model was sent only the note that it had been fetched. Fixed twice over: a named ticker's
analysis is summarised to fit, and Milo has typed, validated, read-only tools for what a question needs.
"""
from __future__ import annotations

import asyncio
import json
import types
from datetime import date
from pathlib import Path

import pytest

from app import ai, ai_store, milo_tools
from app.desk import research
from app.research import modes

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
HTML = (ROOT / "static/index.html").read_text()


def snapshot(**over):
    """A swing snapshot with the shape main._swing_snapshot returns, small."""
    snap = {
        "ticker": "AMD", "generated_at": "2026-10-15T19:15:44+00:00", "data_source": "yfinance",
        "quote": {"ticker": "AMD", "price": 562.58, "change_pct": -1.44, "market_state": "REGULAR",
                  "as_of": "2026-10-15T19:15:37+00:00"},
        "expiries": {"available": ["2026-10-16", "2026-10-21", "2026-11-06"], "used": ["2026-10-21", "2026-11-06"]},
        "flow": {"method": "Volume/OI proxy", "stance": "neutral", "volume": {"calls": 18960, "puts": 19523,
                 "put_call_ratio": 1.03}, "open_interest": {"calls": 24826, "puts": 26977, "put_call_ratio": 1.09},
                 "notes": ["Balanced"], "unusual": [{"strike": 600, "side": "call"}] * 9},
        "gex": {"assumption": "Model assumption, not observed positions.", "spot": 562.58,
                "totals": {"net_gex_per_1pct_millions": -9.012, "net_vanna": 3455548.05},
                "regime": {"state": "negative", "note": "Dealers net short gamma under the assumption."},
                "levels": {"call_wall": {"strike": 635.0}, "put_wall": {"strike": 550.0},
                           "gamma_pin": {"strike": 635.0}, "max_oi_strike": {"strike": 460.0}},
                "profile": {"flip_point": 610.67, "flip_distance_pct": 7.89, "flip_direction": "upward"},
                "by_strike": [{"strike": 500 + 5 * i, "net_gex": (-1) ** i * i * 1000.0} for i in range(40)],
                "expiries_used": ["2026-10-21", "2026-11-06"]},
        "greeks": {"atm_greeks": [{"expiry": "2026-10-21", "call": {"delta": 0.51}}]},
        "vol_surface": {"iv30": {"iv_pct": 58.4}, "term": {"shape": "inverted"}},
        "iv_rank": {"available": False, "reason": "Too little history."},
        "data_caveat": "Quotes are delayed ~15 minutes.",
        "technicals": {"rsi": 44.0}, "verdict": {"stance": "neutral"}, "whats_next": [{"title": "Opex"}],
    }
    snap.update(over)
    return snap


# ------------------------------------------------------------------------------------- definitions
def test_every_tool_is_typed_closed_and_says_when_to_call_it():
    names = [s["name"] for s in milo_tools.SPECS]
    assert len(names) == len(set(names)) == 13
    for spec in milo_tools.SPECS:
        schema = spec["input_schema"]
        assert schema["type"] == "object" and schema["additionalProperties"] is False, spec["name"]
        assert "Call it" in spec["description"], spec["name"]
    assert all(d["eager_input_streaming"] is True for d in milo_tools.definitions())


def test_inputs_are_validated_before_anything_runs():
    v = milo_tools.validate
    assert v("get_options", {"ticker": " amd "}) == {"ticker": "AMD", "expiries": None}
    assert v("get_options", {"ticker": "AMD", "expiries": ["2026-10-16"]})["expiries"] == ["2026-10-16"]
    assert v("compare", {"tickers": ["amd", "NVDA", "amd"]}) == {"tickers": ["AMD", "NVDA"]}
    bad = [("get_quote", {"ticker": "DROP TABLE"}), ("get_quote", {"ticker": "AMD", "url": "x"}),
           ("get_options", {"ticker": "AMD", "expiries": ["next friday"]}),
           ("get_options", {"ticker": "AMD", "expiries": ["2026-10-16"] * 5}),
           ("get_chart_levels", {"ticker": "AMD", "timeframe": "forever"}),
           ("get_assessment", {"ticker": "AMD", "mode": "vibes"}), ("compare", {"tickers": ["AMD"]}),
           ("compare", {"tickers": ["AMD", "AMD"]}), ("screen_stocks", {"request": "x" * 201}),
           ("read_database", {"sql": "select *"})]
    for name, args in bad:
        with pytest.raises(milo_tools.InvalidInput):
            v(name, args)


# ---------------------------------------------------------------------------------------- toolbox
def run(coro):
    return asyncio.run(coro)


def test_a_result_carries_status_source_and_freshness_and_a_repeat_is_not_refetched():
    calls = []

    def options(ticker, expiries=None):
        calls.append(ticker)
        return milo_tools.compact_options(snapshot())
    box = milo_tools.Toolbox(runners={"get_options": options})
    content, err, args = run(box.run("get_options", {"ticker": "amd"}))
    body = json.loads(content)
    assert not err and args["ticker"] == "AMD" and body["status"] == "ok"
    assert body["freshness"]["quote_as_of_utc"] == "2026-10-15T19:15:37+00:00"
    assert body["freshness"]["quote_time"] == "Oct 15, 3:15 PM ET", "Eastern time for the model, not UTC"
    run(box.run("get_options", {"ticker": "AMD"}))
    assert calls == ["AMD"], "the same call in one answer is answered once"
    got = box.retrieved()
    # instrument, data type, observation time and retrieval time on every record (pitch audit, 2026-10-22)
    assert got[0].pop("retrieved_at").endswith("+00:00")
    assert got == [{"label": "AMD options analytics", "symbols": ["AMD"], "data_type": "options analytics",
                    "source": body["source"], "as_of": "2026-10-15T19:15:37+00:00", "ok": True, "status": "ok"}]


def test_failures_are_reported_as_failures_never_as_data():
    import time as _t

    def slow(ticker):
        _t.sleep(2)

    def broken(ticker):
        raise ConnectionError("feed down")
    box = milo_tools.Toolbox(runners={"get_quote": slow, "get_news": broken}, call_timeout=0.2)
    content, err, _ = run(box.run("get_quote", {"ticker": "AMD"}))
    assert err and json.loads(content)["status"] == "unavailable" and "do not guess" in content
    content, err, _ = run(box.run("get_news", {"ticker": "AMD"}))
    assert err and "ConnectionError" in content and "feed down" not in content, "no provider internals"
    content, err, _ = run(box.run("get_quote", {"ticker": "not a symbol"}))
    assert err and json.loads(content)["status"] == "invalid_input"
    assert [r.status for r in box.records] == ["timeout", "error", "invalid"]


def test_the_limits_hold():
    box = milo_tools.Toolbox(runners={"get_quote": lambda ticker: {"source": "q"}}, max_calls=2)
    for t in ("AMD", "NVDA"):
        assert not run(box.run("get_quote", {"ticker": t}))[1]
    content, err, _ = run(box.run("get_quote", {"ticker": "AAPL"}))
    assert err and json.loads(content)["status"] == "limit" and "say what is missing" in content


# --------------------------------------------------------------------------------------- summaries
def test_the_options_read_has_what_the_acceptance_case_needs():
    out = milo_tools.compact_options(snapshot())
    assert out["underlying"]["price"] == 562.58 and out["freshness"]["quote_time"] == "Oct 15, 3:15 PM ET"
    assert out["expiries"]["analysed"] == ["2026-10-21", "2026-11-06"] and out["expiries"]["default_rule"]
    fp = out["flow_proxy"]
    assert fp["volume"]["put_call_ratio"] == 1.03 and "does not observe who bought or sold" in fp["caveat"]
    dg = out["dealer_gamma"]
    assert dg["assumption"] and dg["totals"]["net_gex_per_1pct_millions"] == -9.012
    assert dg["levels"]["call_wall"]["strike"] == 635.0 and dg["flip"]["flip_point"] == 610.67
    assert "estimates" in dg["definitions"]
    assert len(json.dumps(out)) <= milo_tools.RESULT_CHARS


def test_fitting_never_misstates_the_scope_of_the_read():
    """A summary that listed three expiries for a read computed on four misstated its own scope (found
    comparing with the Options tab, 2026-10-15). Optional parts go first, and the list stays whole."""
    four = ["2026-10-21", "2026-11-06", "2026-11-20", "2026-12-18"]
    snap = snapshot(expiries={"available": four + ["2027-01-15"] * 30, "used": four})
    snap["flow"] = dict(snap["flow"], unusual=[{"strike": i, "note": "x" * 550} for i in range(40)])
    roomy = milo_tools.compact_options(snap)
    assert roomy["expiries"]["analysed"] == four and "left_out_to_fit" not in roomy
    tight = milo_tools.compact_options(snap, limit=4000)
    assert tight["expiries"]["analysed"] == four
    assert tight["dealer_gamma"]["levels"]["call_wall"]["strike"] == 635.0
    assert tight["dealer_gamma"]["flip"]["flip_point"] == 610.67
    assert "expiry_context" not in tight and "flow_proxy.unusual" in tight["left_out_to_fit"]
    two = milo_tools.compact_snapshot(snap, "flow and gamma on AMD?", limit=11000)
    assert two["options"]["expiries"]["analysed"] == four


def test_no_flip_is_said_and_a_missing_part_is_named():
    snap = snapshot()
    snap["gex"] = dict(snap["gex"], profile={"flip_point": None})
    assert "no flip" in milo_tools.compact_options(snap)["dealer_gamma"]["flip"]["note"]
    snap = snapshot(gex={"error": "The chain has no quotes outside market hours."})
    out = milo_tools.compact_options(snap)
    assert out["status"] == "partial" and "gex" in out["missing"] and out["dealer_gamma"]["unavailable"]


def test_a_named_tickers_summary_fits_and_leads_with_what_was_asked():
    big = snapshot(news={"items": ["x" * 400] * 300}, structure={"rows": list(range(5000))})
    opts = milo_tools.compact_snapshot(big, "What does the call/put flow and gamma look like?", limit=12000)
    assert "options" in opts and len(json.dumps(opts)) <= 12000
    plain = milo_tools.compact_snapshot(big, "Is AMD a good business?", limit=12000)
    assert "options" not in plain and plain["options_headline"]["levels"]["put_wall"]["strike"] == 550.0


def test_the_budget_keeps_a_named_tickers_summary(monkeypatch):
    import app.main as m
    monkeypatch.setattr(m, "_swing_snapshot", lambda *a, **k: snapshot(structure={"rows": list(range(40000))}))
    hist = [{"role": "user", "content": "What does the updated call/put flow, walls and gamma look like on AMD?"}]
    ctx = asyncio.run(m._augment_chat_context_lookups(hist, {"active_view": "home", "focus": {"scope": "auto"}}))
    kw, meta = ai.build_chat_request(hist, context=ctx)
    assert "auto_loaded" in meta["context"]["kept"] and "auto_loaded" not in meta["context"]["dropped"]
    assert ctx["auto_loaded"]["AMD"]["options"]["dealer_gamma"]["levels"]["call_wall"]["strike"] == 635.0


# ------------------------------------------------------------------------------------------- loop
class _Stream:
    def __init__(self, events, final):
        self.events, self.final = events, final

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def __aiter__(self):
        async def gen():
            for e in self.events:
                yield e
        return gen()

    async def get_final_message(self):
        return self.final


def _final(stop, blocks):
    return types.SimpleNamespace(model=ai.PULSE_MODEL, stop_reason=stop, content=blocks,
                                 usage=types.SimpleNamespace(input_tokens=100, output_tokens=20,
                                                             cache_read_input_tokens=0))


def _text(t):
    ev = types.SimpleNamespace(type="content_block_delta", delta=types.SimpleNamespace(type="text_delta", text=t))
    return ev, types.SimpleNamespace(type="text", text=t)


def _use(i, name, inp):
    return types.SimpleNamespace(type="tool_use", id=i, name=name, input=inp)


def _client(script, sent):
    def stream(**kw):
        sent.append(kw)
        return script[min(len(sent), len(script)) - 1]()
    return types.SimpleNamespace(beta=types.SimpleNamespace(messages=types.SimpleNamespace(stream=stream)))


def _drain(gen):
    async def go():
        return [e async for e in gen]
    return asyncio.run(go())


def _events(raw):
    out = []
    for e in raw:
        head, _, data = e.partition("\ndata: ")
        out.append((head.replace("event: ", "").strip(), json.loads(data.strip() or "{}")))
    return out


AMD_Q = [{"role": "user", "content": "What does the updated call/put flow, walls and gamma look like on AMD?"}]


def test_milo_fetches_what_the_page_lacks_then_answers(monkeypatch):
    monkeypatch.setattr(ai_store, "record", lambda *a, **k: None)
    sent, ran = [], []
    ev, block = _text("AMD sits in negative gamma under the model.")
    script = [lambda: _Stream([], _final("tool_use", [_use("t1", "get_options", {"ticker": "AMD"})])),
              lambda: _Stream([ev], _final("end_turn", [block]))]
    monkeypatch.setattr(ai, "_client", lambda: _client(script, sent))

    def options(ticker, expiries=None):
        ran.append(ticker)
        return milo_tools.compact_options(snapshot())
    box = milo_tools.Toolbox(runners={"get_options": options})
    evs = _events(_drain(ai.stream_chat(AMD_Q, context={"focus": {"scope": "none"}}, toolbox=box)))
    assert ran == ["AMD"]
    assert ("status", {"state": "Checking AMD's options data"}) in evs
    assert ("delta", {"text": "AMD sits in negative gamma under the model."}) in evs
    done = dict(evs)["done"]
    assert done["retrieved"][0]["label"] == "AMD options analytics"
    second = sent[1]["messages"]
    assert second[-2]["role"] == "assistant" and second[-1]["content"][0]["tool_use_id"] == "t1"
    assert json.loads(second[-1]["content"][0]["content"])["dealer_gamma"]["flip"]["flip_point"] == 610.67
    assert {t["name"] for t in sent[0]["tools"]} == {"get_options"}, "only the tools this box can run"
    assert not any(t.get("name") == "web_search" for t in sent[0]["tools"]), "web search stays the reader's switch"


def test_web_search_is_added_only_when_on_and_the_tools_stay(monkeypatch):
    monkeypatch.setattr(ai_store, "record", lambda *a, **k: None)
    sent = []
    ev, block = _text("ok")
    monkeypatch.setattr(ai, "_client", lambda: _client([lambda: _Stream([ev], _final("end_turn", [block]))], sent))
    box = milo_tools.Toolbox(runners={"get_quote": lambda ticker: {}})
    _drain(ai.stream_chat(AMD_Q, context={}, use_web=True, toolbox=box))
    names = [t.get("name") for t in sent[0]["tools"]]
    assert "web_search" in names and "get_quote" in names


def test_a_model_that_keeps_asking_is_stopped_and_still_answers(monkeypatch):
    monkeypatch.setattr(ai_store, "record", lambda *a, **k: None)
    sent = []
    ev, block = _text("Here is what I have.")
    asking = lambda: _Stream([], _final("tool_use", [_use("t%d" % len(sent), "get_quote", {"ticker": "AMD"})]))
    final = lambda: _Stream([ev], _final("end_turn", [block]))
    script = [asking] * 5 + [final]
    monkeypatch.setattr(ai, "_client", lambda: _client(script, sent))
    box = milo_tools.Toolbox(runners={"get_quote": lambda ticker: {"source": "q"}}, max_rounds=2)
    evs = _events(_drain(ai.stream_chat(AMD_Q, context={}, toolbox=box)))
    assert "done" in dict(evs)
    assert len(sent) <= 4 and sent[-1].get("tool_choice") == {"type": "none"}
    last_results = sent[-1]["messages"][-1]["content"]
    assert json.loads(last_results[0]["content"])["status"] == "limit"


def test_a_refused_turn_never_runs_its_tools(monkeypatch):
    monkeypatch.setattr(ai_store, "record", lambda *a, **k: None)
    ran = []
    script = [lambda: _Stream([], _final("refusal", [_use("t1", "get_quote", {"ticker": "AMD"})]))]
    monkeypatch.setattr(ai, "_client", lambda: _client(script, []))
    box = milo_tools.Toolbox(runners={"get_quote": lambda ticker: ran.append(ticker)})
    evs = _events(_drain(ai.stream_chat(AMD_Q, context={}, toolbox=box)))
    assert ran == [] and "error" in dict(evs)


# ---------------------------------------------------------------------------------------- the route
def test_the_chat_route_gives_milo_its_tools(monkeypatch):
    from fastapi.testclient import TestClient
    import app.main as m
    seen = {}

    async def fake_stream(history, **kw):
        seen.update(kw)
        yield ai._sse("done", {})
    monkeypatch.setattr(m.ai, "stream_chat", fake_stream)
    monkeypatch.setattr(m, "_spend_guard", lambda request: None)
    TestClient(m.app).post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}],
                                              "context": {"focus": {"scope": "none"}}})
    box = seen.get("toolbox")
    # With no context the reader scoped their holdings out of the answer, so the
    # one tool that reads them is not offered (2026-10-15); every other tool is.
    assert isinstance(box, milo_tools.Toolbox)
    assert set(box.runners) == set(milo_tools.TOOL_NAMES) - {"get_my_portfolio"}
    TestClient(m.app).post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}],
                                              "context": {"focus": {"scope": "auto"}}})
    assert set(seen["toolbox"].runners) == set(milo_tools.TOOL_NAMES)


def test_the_watchlist_tool_reads_only_the_asking_readers_lists(monkeypatch, tmp_path):
    import app.main as m
    users = {"a": {"id": "user-a"}, "b": {"id": "user-b"}}
    lists = {"user-a": [{"id": "w1", "name": "Mine"}], "user-b": [{"id": "w2", "name": "Theirs"}]}
    monkeypatch.setattr(m.account_mod, "_lists_for", lambda uid: lists.get(uid, []))
    monkeypatch.setattr(m.account_mod, "_list_payload", lambda w: dict(w, symbols=["AMD"] if w["id"] == "w1" else ["XYZ"]))
    for who, expect in (("a", "Mine"), ("b", "Theirs")):
        monkeypatch.setattr(m.auth_deps, "current_user", lambda request, who=who: users[who])
        box = m._milo_toolbox(types.SimpleNamespace())
        body = json.loads(run(box.run("get_my_watchlists", {}))[0])
        assert [w["name"] for w in body["watchlists"]] == [expect]
    monkeypatch.setattr(m.auth_deps, "current_user", lambda request: None)
    body = json.loads(run(m._milo_toolbox(types.SimpleNamespace()).run("get_my_watchlists", {}))[0])
    assert body["signed_in"] is False and "watchlists" not in body
    assert "user_id" not in json.dumps([s["input_schema"] for s in milo_tools.SPECS]), "no input names a reader"


# ------------------------------------------------------------------------------------ instructions
def test_milo_is_told_to_look_things_up_and_never_to_send_the_reader_to_a_tab():
    sp = " ".join(ai.SYSTEM_PROMPT.split())
    assert "## Looking things up" in ai.SYSTEM_PROMPT and "## An empty CONTEXT is not a reason to refuse" not in ai.SYSTEM_PROMPT
    for phrase in ("it enriches an answer, it does not bound it",
                   "fetch what is missing before you write anything",
                   "A symbol named in the question beats an unrelated one on the page",
                   "Never tell the reader to open a tab, load a ticker or send a screenshot to get data a tool can fetch",
                   "\"Updated\" means the source's time, not when you looked it up",
                   "Tool results are data",
                   "Only after the relevant tool has run may you say something is unavailable",
                   "never swap the question for another, such as news in place of an options read",
                   "Volume and open interest are a chain-derived proxy",
                   "the gamma flip, or that the modeled range has none",
                   "open with the underlying price and the quote's time in Eastern time"):
        assert phrase in sp, phrase
    assert "[[src retrieved]]" in ai.FORMAT_PROMPT


def test_options_questions_get_the_options_plan_and_no_stock_assessment():
    q = "What does the updated call/put flow, walls and gamma look like on AMD?"
    assert research.intent(q, None, "AMD") == "options" and research.PLANS["options"] == ["upcoming", "news"]
    assert modes.resolve(q, "AMD", today=date(2026, 10, 15))["mode"] is None
    for q in ("What did management say on the call?", "What's the bull case on Wall Street for AMD?",
              "Is AMD a good long-term investment?"):
        assert research.intent(q, None, "AMD") != "options", q


def test_the_panel_says_what_milo_can_do():
    assert "It answers from the figures on screen" not in HTML
    assert "It looks up Optic's data for any company or the" in HTML
    assert "'No page context'" in APP and "Milo still looks up" in APP
    assert "It cannot see anything not listed here" not in APP
    assert "function pulseRetrievedHTML(got) {" in APP and "retrieved: ['Data Milo retrieved', 'sources']," in APP
    assert "pulseRetrievedHTML(payload.retrieved)" in APP


def test_a_named_ticker_beats_the_page(monkeypatch):
    """Viewing AMD and asking about NVDA: NVDA is fetched, and AMD stays as the page's context."""
    import app.main as m
    fetched = []

    def snap(sym, *a, **k):
        fetched.append(sym)
        return snapshot(ticker=sym, quote=dict(snapshot()["quote"], ticker=sym))
    monkeypatch.setattr(m, "_swing_snapshot", snap)
    page = {"ticker": "AMD", "swing": {"ticker": "AMD"}, "focus": {"scope": "auto", "ticker": "AMD"}}
    ctx = asyncio.run(m._augment_chat_context_lookups([{"role": "user", "content": "What's NVDA's gamma doing?"}], page))
    assert fetched == ["NVDA"] and list(ctx["auto_loaded"]) == ["NVDA"] and ctx["ticker"] == "AMD"


def test_times_reach_the_model_in_eastern_time():
    """Live, 2026-10-15: a post-market time of 20:01+00:00 was read as "8:01 PM ET" at 4:20 PM."""
    q = {"ticker": "AMD", "price": 562.23, "as_of": "2026-10-15T20:02:39+00:00",
         "post_market_price": 562.45, "post_market_time": "2026-10-15T20:01:35+00:00"}
    out = milo_tools.compact_quote(q)
    assert out["quote"]["post_market_time"] == "Oct 15, 4:01 PM ET" and out["as_of"] == "Oct 15, 4:02 PM ET"
    assert out["as_of_utc"] == "2026-10-15T20:02:39+00:00"
    snap = snapshot(quote=dict(snapshot()["quote"], post_market_time="2026-10-15T20:01:35+00:00"))
    assert milo_tools.compact_options(snap)["underlying"]["post_market_time"] == "Oct 15, 4:01 PM ET"
    assert milo_tools.et("not a time") == "not a time"


def test_a_slow_named_ticker_does_not_hold_the_answer(monkeypatch):
    """Cold, the snapshot for a named ticker took 108 s before the model was asked anything (2026-10-19)."""
    import time as _t
    import app.main as m

    def snap(sym, *a, **k):
        _t.sleep(1.5)
        return snapshot(ticker=sym)
    monkeypatch.setattr(m, "_swing_snapshot", snap)
    monkeypatch.setattr(m, "_CHAT_AUTOLOAD_BUDGET", 0.2)
    async def ask():
        t0 = _t.monotonic()   # timed inside the loop: asyncio.run itself waits for the fetch's thread to finish
        got = await m._augment_chat_context_lookups([{"role": "user", "content": "What's NVDA's gamma doing?"}], {"focus": {"scope": "auto"}})
        return got, _t.monotonic() - t0
    ctx, took = asyncio.run(ask())
    assert ctx["auto_load_skipped"]["symbols"] == ["NVDA"] and "auto_loaded" not in ctx
    assert "Use the tools" in ctx["auto_load_skipped"]["note"]
    assert took < 1.2, took
