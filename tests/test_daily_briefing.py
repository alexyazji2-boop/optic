"""What changed since yesterday, held to the rules it was asked for with.

Saved, dated readings compared, never yesterday rebuilt from today's data: the
earlier close's technicals from the candles up to that close and no later, and
earnings dates and filings from a reading saved in an earlier session. The
period named, with weekends and holidays accounted for. "No meaningful change"
kept apart from stale or missing data, and from checks that could not run.
Every item saying what changed, why it may matter and where to look, in fixed
sentences that need no AI. A reader's own lists read by their own account.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import app.main as main
from app import briefing as B
from app import session as session_mod
from app.analytics import setups as S
from app.auth import config, store

from tests.test_swing_setups import frame, after

ROOT = Path(__file__).resolve().parent.parent
ET = session_mod.ET
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


@pytest.fixture(autouse=True)
def fresh_store(tmp_path, monkeypatch):
    monkeypatch.setattr(B, "DB_PATH", str(tmp_path / "observations.db"))
    main._BRIEFING_CACHE.clear()
    yield


def et(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=ET)


def bars(closes, volume=None, start="2025-01-02"):
    df = frame(closes, volume=volume, start=start)
    return S.daily_bars(df, after(df)), df


# ================================================================ the period

def test_a_tuesday_morning_compares_friday_with_monday():
    per = B.period(et(2026, 10, 6, 10, 30))
    assert (per["previous"], per["latest"]) == ("2026-10-02", "2026-10-05")
    assert per["label"] == "From the close of Fri Oct 2 to the close of Mon Oct 5"
    assert per["skipped"] == ["the weekend"] and per["in_progress"] is True
    assert "still trading" in " ".join(per["notes"])


def test_after_the_bell_the_day_just_closed_is_the_latest():
    per = B.period(et(2026, 10, 6, 16, 5))
    assert (per["previous"], per["latest"]) == ("2026-10-05", "2026-10-06")
    assert per["in_progress"] is False and per["skipped"] == []


def test_a_holiday_is_skipped_and_named():
    per = B.period(et(2026, 11, 27, 17, 0))                      # the half day after Thanksgiving
    assert (per["previous"], per["latest"]) == ("2026-11-25", "2026-11-27")
    assert per["skipped"] == ["Thu Nov 26 (Thanksgiving Day)"]


def test_a_weekend_morning_compares_the_last_two_sessions():
    per = B.period(et(2026, 10, 10, 9, 0))
    assert (per["previous"], per["latest"]) == ("2026-10-08", "2026-10-09")


# ================================================================ prices

def _quiet(n=300, step=0.1, base=100.0):
    rng = np.random.default_rng(3)
    return list(base + np.cumsum(rng.normal(step * 0.2, 0.6, n)))


def test_no_candles_is_missing_and_old_candles_are_stale():
    assert B.price_checks("X", None, "2026-10-05", "2026-10-02")["state"] == "missing"
    b, df = bars(_quiet(50))
    stale = B.price_checks("X", b, "2026-10-05", "2026-10-02")
    assert stale["state"] == "stale" and b.stamps[-1] in stale["note"]


def test_a_large_move_for_this_stock_is_an_item_with_its_reason():
    closes = _quiet(300)
    closes.append(closes[-1] * 1.06)
    vol = [1e6] * 300 + [3.2e6]
    b, _ = bars(closes, volume=vol)
    out = B.price_checks("X", b, b.stamps[-1], b.stamps[-2])
    move = [i for i in out["items"] if i["kind"] == "move"][0]
    assert move["headline"].startswith("X rose 6.0% to ")
    assert "times its typical daily move" in move["detail"] and "volume 3.2 times" in move["detail"]
    assert move["why"] and move["link"] == {"view": "chart"}


def test_a_routine_move_for_a_volatile_stock_is_not_one():
    rng = np.random.default_rng(5)
    closes = list(100 * np.cumprod(1 + rng.normal(0, 0.035, 300)))   # moves ~3.5% a day
    closes.append(closes[-1] * 1.025)
    b, _ = bars(closes)
    out = B.price_checks("X", b, b.stamps[-1], b.stamps[-2])
    assert not [i for i in out["items"] if i["kind"] == "move"]
    assert out["typical_pct"] > 2.5


def test_each_close_is_read_from_the_candles_up_to_it_only():
    """Candles after the session compared change nothing about it."""
    closes = _quiet(300) + [130.0, 80.0, 140.0]
    b, _ = bars(closes)
    upto = S.daily_bars(frame(closes[:301], start="2025-01-02"), after(frame(closes[:301], start="2025-01-02")))
    a = B.price_checks("X", b, b.stamps[300], b.stamps[299])
    c = B.price_checks("X", upto, upto.stamps[300], upto.stamps[299])
    assert a["state"] == c["state"] == "ok"
    assert [i["headline"] for i in a["items"]] == [i["headline"] for i in c["items"]]
    assert a["change_pct"] == c["change_pct"]


def test_a_close_through_the_50_day_is_a_change_of_state():
    closes = [100.0 + 0.05 * i for i in range(260)] + [95.0, 99.0, 112.0]
    b, _ = bars(closes)
    out = B.price_checks("X", b, b.stamps[-1], b.stamps[-2])
    heads = [i["headline"] for i in out["items"]]
    assert "X closed above its 50-day average" in heads


def _overbought_run():
    """Up three days in four: a 14-day RSI in the eighties."""
    closes = [100.0]
    for i in range(80):
        closes.append(closes[-1] + (0.9 if i % 4 != 3 else -0.5))
    return closes


def test_rsi_easing_just_under_70_is_not_news():
    """From 82 to 69.9 crosses the line by a tenth of a point: the same
    stretched reading, not a change of state."""
    closes = _overbought_run()
    b, _ = bars(closes + [closes[-1] - 1.825])
    r = S.rsi(b.c, 14)
    assert r[-2] >= 70 and 69 < r[-1] < 70
    out = B.price_checks("X", b, b.stamps[-1], b.stamps[-2])
    assert not [i for i in out["items"] if "RSI left" in i["headline"]]


def test_rsi_falling_well_out_of_the_zone_is():
    closes = _overbought_run()
    b, _ = bars(closes + [closes[-1] - 4.0])
    r = S.rsi(b.c, 14)
    assert r[-2] >= 70 and r[-1] <= 65
    out = B.price_checks("X", b, b.stamps[-1], b.stamps[-2])
    assert "X RSI left overbought territory" in [i["headline"] for i in out["items"]]


def test_a_new_52_week_closing_high_is_an_item():
    closes = _quiet(300)
    closes.append(max(closes) + 5)
    b, _ = bars(closes)
    out = B.price_checks("X", b, b.stamps[-1], b.stamps[-2])
    assert "X closed at a 52-week high" in [i["headline"] for i in out["items"]]


def test_a_short_history_names_what_it_could_not_check():
    b, _ = bars(_quiet(40))
    out = B.price_checks("X", b, b.stamps[-1], b.stamps[-2])
    joined = " ".join(out["not_checked"])
    assert "200-day" in joined and "52-week" in joined


# ================================================================ setups

def test_setups_on_one_close_are_one_item_and_older_ones_are_not_news():
    rows = [
        {"label": "Donchian 20-bar breakout", "direction": "bull", "status": "triggered",
         "trigger": {"stamp": "2026-10-05"}, "invalidation": 219.61},
        {"label": "Donchian 55-bar breakout", "direction": "bull", "status": "triggered",
         "trigger": {"stamp": "2026-10-05"}, "invalidation": 219.61},
        {"label": "Trend pullback", "direction": "bull", "status": "triggered",
         "trigger": {"stamp": "2026-09-28"}, "invalidation": 200.0},
        {"label": "AVWAP reclaim", "direction": "bear", "status": "invalidated", "status_at": "2026-10-05"},
    ]
    out = B.setup_checks("X", {"available": True, "rows": rows}, "2026-10-05")
    fired = [i for i in out["items"] if "triggered" in i["headline"]][0]
    assert fired["headline"] == "X 2 setups triggered on the close"
    assert "Trend pullback" not in fired["detail"]
    assert "Invalidated by a close below 219.61." in fired["detail"]
    assert fired["link"] == {"view": "swing", "panel": "Swing setups"}
    ended = [i for i in out["items"] if "invalidated" in i["headline"]][0]
    assert "AVWAP reclaim (bearish)" in ended["detail"]


# ================================================================ earnings and filings

def reading(session, observed_at, **data):
    return {"session": session, "observed_at": observed_at, "data": data}


def test_earnings_within_five_sessions_and_a_report_in_the_period():
    r = reading("2026-10-05", "2026-10-05T20:31:00+00:00", next_earnings="2026-10-09",
                last_reported={"date": "2026-10-05", "eps_reported": 1.23, "eps_estimate": 1.10})
    out = B.earnings_checks("X", r, "2026-10-05", "2026-10-02")
    heads = [i["headline"] for i in out["items"]]
    assert "X reports earnings on Fri Oct 9 (4 sessions away)" in heads
    assert "X reported earnings on Mon Oct 5" in heads
    rep = [i for i in out["items"] if "reported" in i["headline"]][0]
    assert rep["detail"] == "Reported EPS 1.23 against 1.10 expected (+11.8%)."
    far = reading("2026-10-05", "x", next_earnings="2026-10-30",
                  last_reported={"date": "2026-07-30", "eps_reported": 1.0})
    assert B.earnings_checks("X", far, "2026-10-05", "2026-10-02")["items"] == []


def test_filings_compare_two_saved_readings_and_one_is_not_enough():
    assert B.fundamental_checks("X", [])["ran"] is False
    one = B.fundamental_checks("X", [reading("2026-10-05", "2026-10-05T20:31:00+00:00")])
    assert one["ran"] is False and "First reading saved 2026-10-05" in one["note"]
    new = reading("2026-10-05", "2026-10-05T20:31:00+00:00",
                  revenue_ttm={"value": 44e9, "period_end": "2026-09-30"},
                  eps_ttm={"value": 2.5, "period_end": "2026-09-30"},
                  shares_outstanding=1.02e9, next_earnings="2026-10-29")
    old = reading("2026-10-02", "2026-10-02T20:31:00+00:00",
                  revenue_ttm={"value": 40e9, "period_end": "2026-06-30"},
                  eps_ttm={"value": 2.2, "period_end": "2026-06-30"},
                  shares_outstanding=1.0e9, next_earnings="2026-10-22")
    out = B.fundamental_checks("X", [new, old])
    heads = " | ".join(i["headline"] for i in out["items"])
    assert "filed a new quarter: trailing revenue $44.0B" in heads
    assert "trailing EPS is now 2.50" in heads
    assert "shares outstanding rose 2.0%" in heads
    assert "earnings date moved to 2026-10-29" in heads
    filed = [i for i in out["items"] if "filed" in i["headline"]][0]
    assert "+10.0% on the trailing figure on file before" in filed["detail"]


def test_a_saved_reading_is_never_rewritten_the_same_session():
    assert B.record("X", "2026-10-05", {"next_earnings": "2026-10-22"})
    assert not B.record("X", "2026-10-05", {"next_earnings": "2026-12-01"})
    B.record("X", "2026-10-02", {"next_earnings": "2026-10-20"})
    B.record("X", "2026-10-06", {"next_earnings": "2026-11-01"})
    reads = B.readings("X", "2026-10-05")
    assert [r["session"] for r in reads] == ["2026-10-05", "2026-10-02"]
    assert reads[0]["data"]["next_earnings"] == "2026-10-22"


def test_capture_reads_only_names_without_a_reading():
    class P:
        calls = []

        def earnings_date(self, s):
            self.calls.append(s)
            return "2026-10-22"

        def earnings_history(self, s, limit=8):
            return [{"date": "2026-07-29", "eps_reported": 1.0, "eps_estimate": 0.9}]

        def short_interest(self, s):
            return {"shares_outstanding": 1e9}

    from app.analytics import sec_facts
    orig = sec_facts.history
    sec_facts.history = lambda s, force=False: {"available": False, "reason": "none"}
    try:
        B.record("A", "2026-10-05", {})
        out = B.capture(P(), ["A", "B"], "2026-10-05")
    finally:
        sec_facts.history = orig
    assert out == {"session": "2026-10-05", "wanted": 1, "saved": 1, "remaining": 0}
    assert P.calls == ["B"]
    saved = B.readings("B", "2026-10-05")[0]["data"]
    assert saved["next_earnings"] == "2026-10-22" and saved["revenue_ttm"] is None
    assert saved["errors"]["filings"] == "none"


# ================================================================ the whole briefing

def test_unchanged_is_earned_and_stale_or_missing_is_said():
    calm, _ = bars(_quiet(300), start="2025-06-02")
    per = {"latest": calm.stamps[-1], "previous": calm.stamps[-2], "label": "x", "notes": []}
    B.record("CALM", per["latest"], {"next_earnings": None})
    B.record("CALM", per["previous"], {"next_earnings": None})
    old, _ = bars(_quiet(60), start="2025-01-02")
    out = B.build(["CALM", "OLD", "GONE"], ["GONE"], {"CALM": calm, "OLD": old}.get,
                  lambda s: {"available": True, "rows": []}, per)
    names = {n["symbol"]: n for n in out["names"]}
    assert names["CALM"]["state"] == "unchanged"
    summary = names["CALM"]["summary"]
    assert summary.startswith("No meaningful change: moved ")
    assert "no setup triggered or invalidated" in summary and "no new filing" in summary
    assert names["OLD"]["state"] == "stale" and names["GONE"]["state"] == "missing"
    assert names["GONE"]["holding"] is True
    assert out["counts"] == {"changed": 0, "unchanged": 1, "stale": 1, "missing": 1}
    assert "not by an AI model" in out["method"]


def test_a_name_never_read_says_its_earnings_were_not_checked():
    calm, _ = bars(_quiet(300), start="2025-06-02")
    per = {"latest": calm.stamps[-1], "previous": calm.stamps[-2], "label": "x", "notes": []}
    out = B.build(["NEW"], [], {"NEW": calm}.get, lambda s: {"available": True, "rows": []}, per)
    n = out["names"][0]
    assert n["state"] == "unchanged" and out["unread"] == ["NEW"]
    assert "earnings dates and filings (not read yet)" in n["not_checked"]
    assert "earnings" not in n["summary"] and "filing" not in n["summary"]


def test_holdings_come_first():
    a, _ = bars(_quiet(300) + [140.0], start="2025-06-02")
    per = {"latest": a.stamps[-1], "previous": a.stamps[-2], "label": "x", "notes": []}
    out = B.build(["A", "H"], ["H"], {"A": a, "H": a}.get, lambda s: {"available": True, "rows": []}, per)
    assert out["items"][0]["symbol"] == "H" and out["items"][0]["holding"] is True


# ================================================================ the endpoint

client = TestClient(main.app)
GOOD = "tungsten-carbide-9"


def _stub_feed(monkeypatch, symbols_seen):
    closes = _quiet(300)
    df = frame(closes, start="2025-06-02")

    def frames(symbols, bench, period="2y"):
        symbols_seen.append(sorted(symbols))
        return {s: df for s in list(symbols) + [bench]}

    monkeypatch.setattr(main, "_setup_frames", frames)
    monkeypatch.setattr(main.setups_mod, "analyse", lambda *a, **k: {"available": True, "rows": []})
    monkeypatch.setattr(main, "_briefing_read_soon", lambda symbols, session: None)
    last = df.index[-1].date()
    monkeypatch.setattr(B, "period", lambda now=None: {
        "latest": str(last), "previous": str(df.index[-2].date()), "label": "x", "notes": [],
        "skipped": [], "in_progress": False})


def test_a_guest_sends_their_names_and_nothing_personal_is_kept(monkeypatch, accounts):
    seen = []
    _stub_feed(monkeypatch, seen)
    reply = client.post("/api/briefing", json={"symbols": ["nvda", "AMD", "bad symbol!"], "holdings": ["SPY"]})
    assert reply.status_code == 200, reply.text
    body = reply.json()
    assert [n["symbol"] for n in body["names"]] == ["SPY", "NVDA", "AMD"]
    conn = sqlite3.connect(B.DB_PATH)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(requested)")]
    assert cols == ["symbol", "last_requested"], "a name and a time, nothing about who asked"


def test_a_signed_in_reader_gets_their_own_lists_and_not_anothers(monkeypatch, accounts):
    seen = []
    _stub_feed(monkeypatch, seen)
    client.cookies.clear()
    client.post("/api/auth/register", json={"first_name": "A", "last_name": "B", "email": "a@example.com",
                                            "password": GOOD, "confirm_password": GOOD})
    csrf = client.cookies.get(config.CSRF_COOKIE)
    client.post("/api/watchlists/adopt", headers={"X-Optic-CSRF": csrf}, json={"symbols": ["MSFT"]})
    client.cookies.clear()
    client.post("/api/auth/register", json={"first_name": "C", "last_name": "D", "email": "b@example.com",
                                            "password": GOOD, "confirm_password": GOOD})
    csrf = client.cookies.get(config.CSRF_COOKIE)
    client.post("/api/watchlists/adopt", headers={"X-Optic-CSRF": csrf}, json={"symbols": ["TSLA"]})
    body = client.post("/api/briefing", json={"symbols": []}).json()
    assert [n["symbol"] for n in body["names"]] == ["TSLA"]
    assert body["signed_in"] is True
    client.cookies.clear()


def test_nothing_to_compare_is_said(accounts):
    client.cookies.clear()
    body = client.post("/api/briefing", json={"symbols": []}).json()
    assert body["available"] is False and "watchlist" in body["reason"]


# ================================================================ the card

def _jsc(script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = """
      load('tests/support/browser_stubs.js');
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      document.documentElement.style.removeProperty = function () {};
      try { load('static/charts.js'); load('static/app.js'); } catch (e) { print('LOADFAIL:' + e); }
      var R = {};
    """ + script + "\nprint('RESULT:' + JSON.stringify(R));"
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=120, cwd=str(ROOT))
    blob = out.stdout + out.stderr
    assert "RESULT:" in blob, blob[-2000:]
    return json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])


def test_the_card_names_the_period_links_each_item_and_says_what_was_not_checked():
    out = _jsc("""
      DAILY_CHANGES.data = {available: true, summary: '1 of 3 names changed; 1 had no meaningful change; 1 has stale data.',
        period: {label: 'From the close of Fri Oct 2 to the close of Mon Oct 5', notes: ['No session in between: the weekend.']},
        items: [{symbol: 'NVDA', holding: true, kind: 'setup', headline: 'NVDA 2 setups triggered on the close',
                 detail: 'Donchian 20-bar breakout (bullish).', why: 'For review, not an order.',
                 link: {view: 'swing', panel: 'Swing setups'}}],
        names: [{symbol: 'NVDA', state: 'changed'},
                {symbol: 'AMD', state: 'unchanged', change_pct: -0.3, not_checked: ['filings and share count (only one reading so far)']},
                {symbol: 'OLD', state: 'stale', summary: 'The feed\\'s newest completed candle is 2026-10-01.'}],
        unread: [], method: 'Written from fixed rules, not by an AI model.'};
      R.html = dailyChangesHTML();
    """)
    html = out["html"]
    assert "From the close of Fri Oct 2 to the close of Mon Oct 5." in html
    assert "No session in between: the weekend." in html
    assert 'data-dc-open="NVDA" data-dc-view="swing" data-dc-panel="Swing setups"' in html
    assert "2 setups triggered on the close" in html and ">held<" in html
    assert "For review, not an order." in html
    assert "No meaningful change:</strong> AMD" in html
    assert "Not checked: filings and share count (only one reading so far) for AMD." in html
    assert "<strong>OLD</strong>: The feed" in html
    assert "not by an AI model" in html


def test_holdings_are_read_from_the_paper_book_and_the_roth_box():
    out = _jsc("""
      paperBook.open = [{ticker: 'aapl'}, {ticker: 'MSFT'}];
      STATE.rothInputs.holdings = 'VTI 4000\\nschd 1000, BND 50';
      R.held = dailyChangeHoldings();
    """)
    assert out["held"] == ["AAPL", "MSFT", "VTI", "SCHD", "BND"]


def test_the_removed_panel_stays_removed():
    app = (ROOT / "static/app.js").read_text(encoding="utf-8")
    for name in ("renderWhatChanged", "priorSnapshot", "writeSnapshot", "changesBetween", "whatchanged"):
        assert name not in app


# ------------------------------------------------- every name read, not the first 120

class _Reader:
    def earnings_date(self, s):
        return None

    def earnings_history(self, s, limit=8):
        return []

    def short_interest(self, s):
        return {}


def test_a_pass_says_how_many_are_left_and_the_next_one_reads_them(monkeypatch):
    """One pass used to stop at its limit and the session was marked done, so
    the names past it were never read."""
    from app.analytics import sec_facts
    monkeypatch.setattr(sec_facts, "history", lambda s, force=False: {"available": False, "reason": "x"})
    names = ["N%d" % i for i in range(5)]
    first = B.capture(_Reader(), names, "2026-10-05", limit=2)
    assert first == {"session": "2026-10-05", "wanted": 2, "saved": 2, "remaining": 3}
    second = B.capture(_Reader(), names, "2026-10-05", limit=2)
    third = B.capture(_Reader(), names, "2026-10-05", limit=2)
    assert second["remaining"] == 1 and third["remaining"] == 0
    assert all(B.has_reading(n, "2026-10-05") for n in names)


def test_kept_names_come_first_then_the_most_recently_asked():
    # Named so that alphabetical order is the opposite of recency.
    B.note_requested(["AAA"], datetime(2026, 10, 1, tzinfo=timezone.utc))
    B.note_requested(["ZZZ"], datetime(2026, 10, 5, tzinfo=timezone.utc))
    asked = B.recently_requested(datetime(2026, 10, 6, tzinfo=timezone.utc))
    assert asked == ["ZZZ", "AAA"]
    assert B.reading_order(["SPY", "ZZZ"], asked) == ["SPY", "ZZZ", "AAA"]


def test_the_loop_keeps_going_until_nobody_is_left():
    src = (ROOT / "app/main.py").read_text()
    block = src[src.index("due_read = signal_followup_due("):][:1600]
    assert 'if not out["remaining"] or passes[due_read] >= BRIEFING_MAX_PASSES:' in block
    assert "briefing_mod.reading_order(_all_watch_symbols()," in block
    assert "ORDER BY n DESC, symbol" in src
