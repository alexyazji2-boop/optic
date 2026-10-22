"""The nightly setup shortlist (roadmap stage 5, 2026-10-22).

What qualifies is one versioned rule over the setups engine's rows on the last completed session; there is no
quota, so a quiet night is an empty list that says so. Each entry carries what supports and conflicts with it,
its catalysts and its data date. Every stored list gets its outcome recorded later, failures included, and the
record calls itself forward, never a backtest.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from app import main
from app import shortlist as SL
from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"
AS_OF = "2026-10-22"


def _row(sym, status="triggered", at=AS_OF, groups=("Trend", "Market", "Trigger"), failing=(), vol=1.5, met=3, **kw):
    return {"symbol": sym, "status": status, "status_at": at, "armed_at": at if status == "armed" else None,
            "conditions": {"met": met, "of": len(groups), "groups": [{"group": g, "passed": g not in failing} for g in groups]},
            "checks": [{"group": g, "rule": "{} rule".format(g), "passed": g not in failing} for g in groups],
            "volume": {"ratio": vol}, "direction": "bull", "label": "Breakout", "preset": "donchian_20", "family": "breakout",
            "trigger": "A close above the 20-bar high.", "trigger_level": 101.0, "invalidation": 95.0, "as_of": at, **kw}


def test_only_what_changed_on_the_last_session_qualifies():
    assert SL.qualifies(_row("A"), AS_OF).startswith("Every condition met")
    assert SL.qualifies(_row("A", at="2026-10-21"), AS_OF) is None, "a trigger from an earlier session is not news"
    assert SL.qualifies(_row("A", failing=("Market",)), AS_OF) is None
    assert SL.qualifies(_row("A", status="armed", failing=("Trigger",)), AS_OF).startswith("Every condition but the trigger")
    assert SL.qualifies(_row("A", status="armed", failing=("Trigger", "Trend")), AS_OF) is None
    assert SL.qualifies(_row("A", experimental=True), AS_OF) is None
    assert SL.qualifies(_row("A", provisional=True), AS_OF) is None, "an unfinished candle never qualifies"
    assert SL.qualifies(_row("A", status="watching"), AS_OF) is None


def test_one_per_name_triggered_first_and_the_overflow_is_named_not_hidden():
    rows = {"A": [_row("A", status="armed", failing=("Trigger",), vol=3.0), _row("A", vol=1.1)],
            "B": [_row("B", status="armed", failing=("Trigger",), vol=2.0)],
            "C": [_row("C", vol=2.5)], "D": [_row("D", at="2026-10-01")]}
    got = SL.select(rows, {k: AS_OF for k in rows})
    assert [r["symbol"] for r in got["items"]] == ["C", "A", "B"]
    assert got["items"][1]["status"] == "triggered", "A's triggered row beats its armed one"
    many = {"S{:02d}".format(i): [_row("S{:02d}".format(i), vol=i)] for i in range(SL.MAX_ITEMS + 3)}
    got = SL.select(many, {k: AS_OF for k in many})
    assert len(got["items"]) == SL.MAX_ITEMS and len(got["also_qualified"]) == 3
    assert got["items"][0]["symbol"] == "S{:02d}".format(SL.MAX_ITEMS + 2), "ties broken by participation"


def test_evidence_splits_the_engines_checks_and_the_wait_is_not_a_conflict():
    ev = SL.evidence(_row("A", status="armed", failing=("Trigger", "Market")))
    assert ev["supporting"] == ["Trend rule"]
    assert ev["conflicting"] == ["Not in place: market rule"], "the unmet trigger of an armed setup is the wait"
    assert SL.evidence({"checks": [{"group": "Market", "rule": "SPY below its 200-day SMA", "passed": False}]})["conflicting"] == ["Not in place: SPY below its 200-day SMA"]


def _bars(closes, start="2026-10-23"):
    return pd.DataFrame({"Close": closes}, index=pd.bdate_range(start, periods=len(closes)))


def test_outcomes_are_recorded_for_failures_too_and_only_once_enough_sessions_passed():
    long = {"key": "A:x:bull", "symbol": "A", "direction": "bull", "setup": "Breakout", "state": "armed",
            "close": 100.0, "trigger_level": 101.0, "invalidation": 95.0}
    assert SL.outcome(long, _bars([100] * 9), AS_OF) is None, "nine sessions are not ten"
    o = SL.outcome(long, _bars([99, 98, 94, 96, 97, 97, 98, 99, 99, 97]), AS_OF)
    assert o["triggered"] is False and o["invalidated_on"] == "2026-10-27" and o["move_pct"] == -3.0
    short = {**long, "direction": "bear", "state": "triggered", "trigger_level": 99.0, "invalidation": 104.0}
    o = SL.outcome(short, _bars([99, 98, 97, 96, 95, 95, 95, 95, 95, 90]), AS_OF)
    assert o["move_pct"] == 10.0 and o["invalidated_on"] is None, "a falling setup's move counts its own way"
    # bars on or before the evaluation close never count
    o = SL.outcome(long, pd.concat([_bars([200], start="2026-10-22"), _bars([100] * 10)]), AS_OF)
    assert o["best_pct"] == 0.0


class _Feed:
    def __init__(self, frames=None, ed=None):
        self.frames, self.ed = frames or {}, ed

    def batch_history(self, syms, period="2y", interval="1d"):
        return {s: self.frames[s] for s in syms if s in self.frames}

    def earnings_date(self, sym):
        return self.ed


def test_one_report_named_by_the_calendar_and_the_news_is_one_catalyst(monkeypatch):
    from app import news
    ev = {"kind": "earnings", "event_date": "2026-10-28", "headline": "A reports", "publisher": "Wire"}
    monkeypatch.setattr(news, "material_catalyst", lambda n: {"events": [ev]})
    monkeypatch.setattr(news, "pending_catalyst", lambda n: {"events": []})
    got = SL.catalysts(_Feed(ed="2026-10-28"), "A", news_for=lambda s: {}, as_of=AS_OF)
    assert len(got["items"]) == 1 and got["items"][0]["text"].startswith("Reports 2026-10-28 (6 days)")
    assert got["conflicting"] and "either way" in got["conflicting"][0]
    far = SL.catalysts(_Feed(ed="2026-12-30"), "A", as_of=AS_OF)
    assert far["items"] == [] and far["conflicting"] == [], "a report outside the horizon is not a catalyst here"


def _frame():
    i = pd.bdate_range("2024-10-23", AS_OF)
    c = 100 + np.cumsum(np.random.default_rng(1).normal(0, 1, len(i)))
    return pd.DataFrame({"Open": c, "High": c + 1, "Low": c - 1, "Close": c, "Volume": 1e6}, index=i)


def test_a_quiet_night_is_an_empty_list_that_says_so_and_a_dead_feed_says_that(monkeypatch):
    from app import paper
    from app.analytics import setups
    monkeypatch.setattr(paper, "CURATED_UNIVERSE", ["AAA", "BBB", "CCC"])
    monkeypatch.setattr(setups, "analyse", lambda sym, *a, **k: {"available": True, "as_of": AS_OF, "rows": [_row(sym, at="2026-10-01")]})
    sl = SL.build(_Feed({"AAA": _frame(), "BBB": _frame(), "SPY": _frame()}))
    assert sl["items"] == [] and "normal answer" in sl["empty_note"]
    assert sl["version"] == SL.SELECTION_VERSION and sl["universe_size"] == 3 and sl["evaluated"] == 2 and sl["failed"] == ["CCC"]
    dead = SL.build(_Feed({}))
    assert dead["available"] is False and "refusing" in dead["reason"]


def test_an_entry_carries_everything_the_brief_asks_for(monkeypatch):
    from app import paper
    from app.analytics import setups
    monkeypatch.setattr(paper, "CURATED_UNIVERSE", ["AAA"])
    monkeypatch.setattr(setups, "analyse", lambda sym, *a, **k: {"available": True, "as_of": AS_OF, "rows": [_row(sym)], "forming": True})
    sl = SL.build(_Feed({"AAA": _frame(), "SPY": _frame()}))
    it = sl["items"][0]
    for k in ("symbol", "direction", "setup", "horizon", "state", "state_at", "trigger", "trigger_level", "invalidation",
              "supporting", "conflicting", "catalysts", "data_as_of", "why_included", "close", "key"):
        assert k in it, k
    assert sl["forming_excluded"] is True and it["data_as_of"] == AS_OF


def test_lists_are_stored_by_date_and_the_record_is_forward(tmp_path, monkeypatch):
    monkeypatch.setenv("TRACKER_DATA_DIR", str(tmp_path))
    item = {"key": "A:x:bull", "symbol": "A", "direction": "bull", "setup": "Breakout", "state": "triggered",
            "close": 100.0, "trigger_level": 99.0, "invalidation": 95.0}
    SL.save({"as_of": "2026-10-01", "version": SL.SELECTION_VERSION, "built_at": "x", "items": [item]})
    SL.save({"as_of": AS_OF, "version": SL.SELECTION_VERSION, "built_at": "y", "items": [{**item, "key": "B:x:bull", "symbol": "B"}]})
    assert SL.latest()["as_of"] == AS_OF and [x["as_of"] for x in SL.history()] == [AS_OF, "2026-10-01"]
    frames = {"A": _bars([99, 98, 94, 96, 97, 97, 98, 99, 99, 97], start="2026-10-02"), "B": _bars([101])}
    assert SL.record_outcomes(_Feed(frames)) == 1, "B's ten sessions have not passed"
    assert SL.record_outcomes(_Feed(frames)) == 0, "recorded once"
    r = SL.record_summary()
    assert r["entries_listed"] == 2 and r["outcomes_recorded"] == 1 and r["pending"] == 1 and r["invalidated"] == 1 and r["positive"] == 0
    assert "forward record" in r["note"] and "not a backtest" in r["note"]


def test_the_endpoint_returns_the_stored_list_with_its_record(tmp_path, monkeypatch):
    monkeypatch.setenv("TRACKER_DATA_DIR", str(tmp_path))
    SL.save({"as_of": AS_OF, "version": SL.SELECTION_VERSION, "built_at": "y", "items": [], "empty_note": "Nothing."})
    monkeypatch.setattr(main, "_build_shortlist", lambda: (_ for _ in ()).throw(AssertionError("a stored list is not rebuilt")))
    body = TestClient(main.app).get("/api/shortlist").json()
    assert body["as_of"] == AS_OF and body["record"]["entries_listed"] == 0 and body["past"] == [{"as_of": AS_OF, "n": 0, "version": SL.SELECTION_VERSION}]


def test_the_scan_section_shows_the_empty_answer_and_each_entrys_evidence(tmp_path):
    item = {"symbol": "AAA", "direction": "bear", "setup": "Breakout", "state": "armed", "state_at": AS_OF, "trigger_level": 99,
            "invalidation": 104, "close": 100, "supporting": ["Trend rule"], "conflicting": ["Not in place: market rule"],
            "catalysts": [{"text": "Reports 2026-10-28 (6 days), inside the horizon."}], "data_as_of": "2026-10-21",
            "why_included": "Every condition but the trigger holds.", "conditions": {"met": 2, "of": 3}, "horizon": "Days to a few weeks."}
    base = {"as_of": AS_OF, "built_at": "2026-10-22T21:00:00+00:00", "version": SL.SELECTION_VERSION, "rules": SL.RULES,
            "universe_size": 86, "evaluated": 86, "failed": [], "also_qualified": []}
    got = _run(tmp_path, f"""
      const S = await import('{(JS / "pages/scan-shortlist.js").as_posix()}');
      const D = await import('{(JS / "core/dom.js").as_posix()}');
      const base = {json.dumps(base)};
      print(JSON.stringify({{
        empty: D.toString(S.shortlistBody({{ shortlist: {{ ...base, items: [], empty_note: 'Nothing qualified. That is a normal answer.' }} }})),
        full: D.toString(S.shortlistBody({{ shortlist: {{ ...base, items: [{json.dumps(item)}], also_qualified: ['ZZZ'] }} }})),
        none: D.toString(S.shortlistBody({{ shortlist: {{ available: false, reason: 'No prices came back.' }} }})),
      }}));
    """)
    assert "Nothing qualified on that close" in got["empty"] and "normal answer" in got["empty"]
    f = got["full"]
    for s in ("Falling setup", "Armed, waiting", "Trigger at 99.00", "A close above 104.00 invalidates it", "Not in place: market rule",
              "Reports Oct 28, 2026", "Older data: through the", "Also qualified, not shown: ZZZ", SL.SELECTION_VERSION, "not a probability"):
        assert s in f, s
    assert "No prices came back." in got["none"]
