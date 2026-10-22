"""Learning replays (roadmap stage 7, 2026-10-22).

A past chart revealed one completed session at a time from GET /api/replays/{id}: the server sends the bars up
to the cursor and not one more, the setup reading is the engine run on the history cut at that close, nothing
about the outcome is sent before the review, and the split adjustment of old prices is named. The reader's
decision is asked for before the replay passes the decision session and is kept in the browser.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import main
from app import replays as RP
from app import session as session_mod
from tests.test_frontend_v2_stage0 import V2, _run

ENTRY = {"id": "t-1", "symbol": "TTT", "preset": "donchian_20", "direction": "bull", "decision": "2024-06-14",
         "title": "TTT, June 2024", "question": "A breakout: would you take it?", "start_hint": "May 2024"}


class _Feed:
    def __init__(self, splits=None):
        self.splits = splits or {}

    def history(self, sym, period="max", interval="1d"):
        i = pd.bdate_range("2022-01-03", "2024-09-30")
        c = 100 + np.cumsum(np.random.default_rng(len(sym)).normal(0, 1, len(i)))
        df = pd.DataFrame({"Open": c, "High": c + 1, "Low": c - 1, "Close": c, "Volume": 1e6, "Stock Splits": 0.0}, index=i)
        for d, f in self.splits.items():
            df.loc[pd.Timestamp(d), "Stock Splits"] = f
        return df


@pytest.fixture
def lib(monkeypatch):
    monkeypatch.setattr(RP, "LIBRARY", [ENTRY])
    RP._CACHE.clear()
    seen = []

    def analyse(sym, daily, bench, presets, directions, overrides, timeframe, intraday, now=None, **kw):
        seen.append({"last": pd.Timestamp(daily.index[-1]).date().isoformat(), "bench_last": pd.Timestamp(bench.index[-1]).date().isoformat(), "now": now})
        return {"rows": [{"preset": presets[0], "direction": directions[0], "label": "Donchian 20-bar breakout", "status": "triggered",
                          "status_at": ENTRY["decision"], "trigger_level": 101.0, "invalidation": 95.0, "checks": [], "conditions": {}}]}
    monkeypatch.setattr(RP.setups_mod, "analyse", analyse)
    return seen


def test_nothing_after_the_cursor_is_sent(lib):
    feed = _Feed()
    dates = [d.date().isoformat() for d in feed.history("TTT").index]
    d0 = dates.index(ENTRY["decision"])
    for at, want in ((-20, dates[d0 - 20]), (0, dates[d0]), (7, dates[d0 + 7])):
        s = RP.step(feed, "t-1", at)
        last = pd.Timestamp(s["bars"][-1]["t"], unit="ms").date().isoformat()
        assert s["through"] == want and last == want, at
        assert lib[-1]["last"] == want and lib[-1]["bench_last"] <= want, "the reading saw only what existed then"
        assert lib[-1]["now"] == session_mod.regular_close(date.fromisoformat(want))
    assert RP.step(feed, "t-1", 999)["at"] == RP.REVIEW and RP.step(feed, "t-1", -999)["at"] == -RP.LEAD
    s = RP.step(feed, "t-1", -20)
    assert len(s["bars"]) == RP.WARMUP + 1 and s["first_replayed"] == RP.WARMUP, "a year of context before the replay"
    assert s["decision_date"] is None, "the decision date is not named before it comes"


def test_the_outcome_waits_for_the_review(lib):
    feed = _Feed()
    for at in (-20, 0, RP.REVIEW - 1):
        s = RP.step(feed, "t-1", at)
        assert not {"rule_outcome", "at_decision", "revision"} & set(s), at
    r = RP.step(feed, "t-1", RP.REVIEW)
    assert r["phase"] == "review" and r["rule_outcome"]["sessions"] == RP.REVIEW
    assert r["rule_outcome"]["through"] == r["through"], "the outcome covers the revealed sessions only"
    assert "No split since" in r["revision"]


def test_a_later_split_is_named_at_the_review_only(lib):
    feed = _Feed(splits={"2024-07-10": 10.0})
    assert "Stock Splits" in feed.history("TTT").columns
    assert "split" not in str(RP.step(feed, "t-1", 0)).lower().replace("split-adjusted", "").replace("stock splits", "")
    r = RP.step(feed, "t-1", RP.REVIEW)
    assert "10 new shares for each old one" in r["revision"]
    assert "adjusted for later stock splits" in r["revised"]


def test_the_library_asks_and_never_tells(lib):
    out = RP.library()
    assert out["replays"] == [{k: ENTRY[k] for k in ("id", "symbol", "title", "question", "start_hint")}]
    assert "option flow" in out["scope"] and out["lead"] == RP.LEAD


def test_the_shipped_library_is_small_dated_and_hides_outcomes():
    assert 3 <= len(RP.LIBRARY) <= 8, "a small library"
    for e in RP.LIBRARY:
        assert set(e) >= {"id", "symbol", "preset", "direction", "decision", "title", "question"}
        for word in ("worked", "failed", "stopped", "won", "lost", "rallied", "crashed"):
            assert word not in (e["title"] + e["question"]).lower(), (e["id"], word)


def test_the_endpoints(lib, monkeypatch):
    monkeypatch.setattr(main, "YF_PROVIDER", _Feed())
    c = TestClient(main.app)
    assert c.get("/api/replays").json()["replays"][0]["id"] == "t-1"
    assert c.get("/api/replays/t-1?at=-20").json()["phase"] == "before"
    assert c.get("/api/replays/nope").status_code == 404
    monkeypatch.setattr(RP, "LIBRARY", [dict(ENTRY, decision="2024-09-27")])
    RP._CACHE.clear()
    r = c.get("/api/replays/t-1?at=0")
    assert r.status_code == 503 and "Fewer than" in r.json()["detail"]


def test_the_readers_plan_is_scored_on_the_revealed_bars(tmp_path):
    js = (V2 / "js/pages/paper-replay.js").as_posix()
    got = _run(tmp_path, f"""
      const R = await import('{js}');
      const b = (h, l, c, d) => ({{ t: Date.UTC(2024, 5, d), o: c, h, l, c }});
      const bars = [b(101, 99, 100, 14), b(103, 99.5, 102, 17), b(106, 101, 105, 18), b(107, 94, 96, 19)];
      print(JSON.stringify({{
        target: R.planResult({{ choice: 'take', side: 'long', entry: 100, stop: 95, target: 105 }}, bars, 0),
        stop: R.planResult({{ choice: 'take', side: 'long', entry: 100, stop: 99.6 }}, bars, 0),
        both: R.planResult({{ choice: 'take', side: 'long', entry: 100, stop: 95, target: 106.5 }}, bars, 0),
        short: R.planResult({{ choice: 'take', side: 'short', entry: 100, stop: 108 }}, bars, 0),
        pass: R.planResult({{ choice: 'pass' }}, bars, 0) }}));
    """)
    assert got["target"]["r"] == 1 and "reached the target" in got["target"]["how"]
    assert got["stop"]["r"] == -1 and "stopped out" in got["stop"]["how"]
    assert got["both"]["ambiguous"] is True and got["both"]["r"] == -1, "one bar touching both is counted as the stop"
    assert got["short"]["r"] == pytest.approx(0.5) and got["short"]["how"] == "was still open at the end"
    assert got["pass"] is None


def test_the_desk_hosts_it_and_the_decision_is_never_skipped():
    paper = (V2 / "js/pages/paper.js").read_text()
    rp = (V2 / "js/pages/paper-replay.js").read_text()
    assert "RP.mount(mainEl.querySelector('#pt-replay')" in paper and "export const retry = RP.retry" in paper
    assert "if (R.at < 0 && to > 0 && !decided) to = 0;" in rp, "the decision is never skipped"
    assert "REPLAY_KEY = 'optic.v2.replay.v1'" in rp
    assert "createPriceChart(" in rp, "the Chart tab's chart, computing its studies from the bars it is given"
