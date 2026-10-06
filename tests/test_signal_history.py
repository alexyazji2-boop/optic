"""Signal history: recorded once when it fires, never rewritten, kept per reader.

Asked for as transparent, persistent signal history: actual triggered signals
from the existing alert path, the original record immutable, later status and
outcome observations recorded separately and timestamped, repeated evaluations
of one event deduplicated, missing follow-up data left unknown, and nothing
backfilled from information that was not available at the time.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import db, main, signal_history, watch_runner
from app import session as session_mod
from app.analytics import setups as S
from app.analytics import watches as watches_mod

from tests.test_swing_setups import _pullback_df, after, frame


@pytest.fixture()
def two(accounts):
    ids = []
    for email in ("a@example.com", "b@example.com"):
        uid = uuid.uuid4().hex
        now = datetime.now(timezone.utc).isoformat()
        db.execute("INSERT INTO users (id, email, created_at, updated_at) VALUES (?,?,?,?)",
                   (uid, email, now, now))
        ids.append(uid)
    return ids


def fired():
    """A fresh trigger, as the swing_setup evaluator hands it on."""
    df = _pullback_df()
    res = S.analyse("X", df, None, presets=["trend_pullback"], directions=["bull"],
                    overrides={"*": {"htf_filter": False}}, now=after(df))
    hit = watches_mod.EVALUATORS["swing_setup"]({"setups": res}, {"preset": "any"})
    assert hit is not None
    return df, res, hit


# ===================================================== the record itself

def test_the_record_carries_what_the_trigger_was_and_what_it_read(two):
    _df, res, hit = fired()
    sid = watch_runner.record_signal(two[0], hit, "scheduled alert check")
    rows = signal_history.history(two[0])
    assert len(rows) == 1 and rows[0]["id"] == sid
    s = rows[0]
    assert s["symbol"] == "X" and s["strategy"] == "trend_pullback" and s["direction"] == "bull"
    assert s["timeframe"] == "daily" and s["trigger_at"] == res["as_of"]
    assert s["trigger_completed_at"].startswith(res["as_of"] + "T16:00"), \
        "when the trigger candle closed, the moment it could first be known"
    assert s["data_as_of"] == res["as_of"]
    assert s["trigger_price"] and s["invalidation"] and s["target"] is None
    assert s["conditions"]["checks"] and s["indicators"]
    assert s["rule_version"] == S.RULES_VERSION and "Yahoo" in s["source"]
    assert s["params"]["signal_ttl"] == 10 and s["assumptions"]
    assert s["status"] == "unresolved" and s["origin"] == "scheduled alert check"


def test_the_database_refuses_to_rewrite_a_signal(two):
    _df, _res, hit = fired()
    watch_runner.record_signal(two[0], hit, "scheduled alert check")
    with pytest.raises(sqlite3.DatabaseError, match="immutable"):
        db.execute("UPDATE signals SET trigger_price = 1.0 WHERE user_id = ?", (two[0],))
    sig = signal_history.history(two[0])[0]
    signal_history.add_event(sig, "status", "invalidated", "2026-01-01", 1.0, None, "x")
    with pytest.raises(sqlite3.DatabaseError, match="immutable"):
        db.execute("UPDATE signal_events SET price = 2.0 WHERE user_id = ?", (two[0],))


def test_the_same_trigger_seen_twice_is_one_record(two):
    _df, _res, hit = fired()
    assert watch_runner.record_signal(two[0], hit, "scheduled alert check")
    assert watch_runner.record_signal(two[0], hit, "alert check on the page") is None
    assert len(signal_history.history(two[0])) == 1


def test_each_reader_sees_only_their_own(two):
    _df, _res, hit = fired()
    watch_runner.record_signal(two[0], hit, "scheduled alert check")
    assert signal_history.history(two[1]) == []
    watch_runner.record_signal(two[1], hit, "scheduled alert check")
    assert len(signal_history.history(two[0])) == len(signal_history.history(two[1])) == 1
    a, b = signal_history.history(two[0])[0], signal_history.history(two[1])[0]
    assert a["id"] != b["id"]
    signal_history.add_event(a, "status", "expired", "2026-01-01")
    assert signal_history.history(two[1])[0]["events"] == []


def test_only_a_fired_alert_records_anything():
    """No setup, no record: the runner records only a met swing_setup watch."""
    assert watch_runner.record_signal("nobody", {"met": True}, "x") is None
    src = open("app/watch_runner.py", encoding="utf-8").read()
    loop = src[src.index("def run_once("):]
    assert 'result.get("met") and row["kind"] == "swing_setup"' in loop


# ===================================================== what followed

def _bars(closes, start="2025-02-21"):
    df = frame(closes, start=start)
    return S.daily_bars(df, after(df))


def _sig(trigger_at, price, stop, direction="bull"):
    return {"id": "s", "user_id": "u", "trigger_at": trigger_at, "trigger_price": price,
            "invalidation": stop, "direction": direction, "params": json.dumps({"signal_ttl": 10})}


def test_horizons_not_yet_printed_are_absent_not_zero():
    b = _bars([100.0, 101.0, 102.0])              # the trigger and two candles after it
    events = signal_history.followup_events(_sig(b.stamps[0], 100.0, 90.0), b, 10)
    labels = [e["label"] for e in events if e["kind"] == "observation"]
    assert labels == ["after 1 candle"], "5, 10 and 20 have not happened yet"
    assert events[0]["change_pct"] == pytest.approx(1.0)


def test_a_close_beyond_the_invalidation_resolves_it_once():
    b = _bars([100.0, 99.0, 89.0, 95.0, 80.0])
    events = signal_history.followup_events(_sig(b.stamps[0], 100.0, 90.0), b, 10)
    statuses = [e for e in events if e["kind"] == "status"]
    assert len(statuses) == 1 and statuses[0]["label"] == "invalidated"
    assert statuses[0]["data_as_of"] == b.stamps[2], "the first close beyond it"


def test_a_bearish_signal_invalidates_upward():
    b = _bars([100.0, 105.0, 111.0])
    events = signal_history.followup_events(_sig(b.stamps[0], 100.0, 110.0, "bear"), b, 10)
    assert [e["label"] for e in events if e["kind"] == "status"] == ["invalidated"]


def test_the_listing_window_expires_it_without_a_verdict():
    b = _bars([100.0 + i * 0.1 for i in range(15)])
    events = signal_history.followup_events(_sig(b.stamps[0], 100.0, 90.0), b, 10)
    status = [e for e in events if e["kind"] == "status"]
    assert status[0]["label"] == "expired" and status[0]["data_as_of"] == b.stamps[10]


def test_a_trigger_the_feed_no_longer_has_produces_nothing():
    b = _bars([100.0, 101.0])
    assert signal_history.followup_events(_sig("1999-01-04", 100.0, 90.0), b, 10) == []
    assert signal_history.followup_events(_sig(b.stamps[0], 100.0, 90.0), None, 10) == []


def test_follow_up_writes_each_event_once_across_passes(two):
    _df, _res, hit = fired()
    watch_runner.record_signal(two[0], hit, "scheduled alert check")
    sig = signal_history.history(two[0])[0]
    closes = [sig["trigger_price"] * (1 + 0.01 * i) for i in range(25)]
    later = _bars(closes, start=sig["trigger_at"])
    load = lambda syms: {"X": later}
    first = signal_history.followup_all(load, today=later.stamps[-1])
    second = signal_history.followup_all(load, today=later.stamps[-1])
    assert first["events_added"] == 1 + len(signal_history.HORIZONS)
    assert second["events_added"] == 0 and second["signals"] == 0
    row = signal_history.history(two[0])[0]
    assert row["status"] == "expired"
    obs = [e for e in row["events"] if e["kind"] == "observation"]
    assert [e["label"] for e in obs] == ["after 1 candle", "after 5 candles", "after 10 candles",
                                         "after 20 candles"]
    assert all(e["observed_at"] and e["data_as_of"] for e in row["events"])


def test_nothing_is_backfilled_from_history():
    """The module creates a signal only from a fired alert's row: there is no
    path that walks old candles and records what would have fired."""
    src = open("app/signal_history.py", encoding="utf-8").read()
    assert "def record(" in src and "lifecycle(" not in src and "analyse(" not in src
    assert S.fresh_triggers.__defaults__[-1] == S.FRESH_BARS == 3


# ===================================================== the endpoints

def test_history_needs_a_sign_in():
    assert TestClient(main.app).get("/api/signals").status_code == 401


def test_the_guest_follow_up_stores_nothing_and_reads_the_same_rule(monkeypatch):
    b = frame([100.0, 101.0, 89.0], start="2025-02-21")
    monkeypatch.setattr(main.YF_PROVIDER, "batch_history", lambda syms, period="6mo", interval="1d": {"X": b})
    res = TestClient(main.app).post("/api/signals/followup", json={"signals": [
        {"signal_key": "k1", "symbol": "X", "direction": "bull", "trigger_at": "2025-02-21",
         "trigger_price": 100.0, "invalidation": 90.0, "params": {"signal_ttl": 10}}]})
    assert res.status_code == 200, res.text
    events = res.json()["events"]["k1"]
    assert [e["label"] for e in events if e["kind"] == "status"] == ["invalidated"]
    assert "not an options return" in res.json()["basis"]


# ===================================================== listing and scheduling

def _rec(key, day, price=100.0, stop=90.0):
    return {"signal_key": key, "symbol": "X", "strategy": "trend_pullback",
            "strategy_label": "Trend pullback", "direction": "bull", "timeframe": "daily",
            "trigger_at": day, "data_as_of": day, "trigger_price": price, "invalidation": stop}


def test_the_status_filter_counts_toward_the_limit(two):
    """Filtered after the LIMIT, asking for invalidated signals came back empty
    whenever the newest rows were all still open."""
    days = ["2026-09-01", "2026-09-02", "2026-09-03"]
    for i, d in enumerate(days):
        signal_history.record(two[0], _rec("k%d" % i, d), "test")
    oldest = [s for s in signal_history.history(two[0]) if s["trigger_at"] == days[0]][0]
    signal_history.add_event(oldest, "status", "invalidated", "2026-09-04", 89.0)
    got = signal_history.history(two[0], status="invalidated", limit=2)
    assert [s["trigger_at"] for s in got] == [days[0]]
    still = signal_history.history(two[0], status="unresolved", limit=5)
    assert [s["trigger_at"] for s in still] == [days[2], days[1]]
    assert signal_history.history(two[1], status="invalidated") == []


def test_a_restated_feed_cannot_add_a_second_verdict(two):
    signal_history.record(two[0], _rec("k", "2026-09-01"), "test")
    calm = _bars([100.0 + 0.1 * i for i in range(14)], start="2026-09-01")
    signal_history.followup_all(lambda syms: {"X": calm}, today="2026-09-30")
    assert signal_history.history(two[0])[0]["status"] == "expired"
    # The same candles restated so that one closes beyond the invalidation.
    restated = _bars([100.0, 100.5, 85.0] + [100.0] * 25, start="2026-09-01")
    signal_history.followup_all(lambda syms: {"X": restated}, today="2026-10-20")
    row = signal_history.history(two[0])[0]
    assert [e["label"] for e in row["events"] if e["kind"] == "status"] == ["expired"]


def test_a_split_since_the_trigger_is_not_read_as_a_collapse():
    """Recorded at 400 with the stop at 360; the feed has since split 4-for-1,
    so it shows the trigger candle at 100."""
    b = _bars([100.0, 101.0, 102.0, 103.0, 104.0, 105.0])
    events = signal_history.followup_events(_sig(b.stamps[0], 400.0, 360.0), b, 10)
    assert not [e for e in events if e["kind"] == "status"]
    first = [e for e in events if e["label"] == "after 1 candle"][0]
    assert first["change_pct"] == pytest.approx(1.0)
    assert first["price"] == pytest.approx(404.0), "in the record's terms"
    assert "re-based" in first["detail"]
    restated = signal_history.followup_events(_sig(b.stamps[0], 100.2, 90.0), b, 10)
    assert "re-based" not in restated[0]["detail"], "a cent or two is a restatement, not a split"


def test_a_signal_past_the_follow_up_window_is_left_alone(two):
    signal_history.record(two[0], _rec("old", "2026-01-02"), "test")
    signal_history.record(two[0], _rec("new", "2026-09-01"), "test")
    assert [r["signal_key"] for r in signal_history.pending(today="2026-10-06")] == ["new"]


def test_follow_ups_wait_for_the_close_to_settle_and_run_once_a_session():
    ET = session_mod.ET
    due = main.signal_followup_due
    assert due(datetime(2026, 10, 9, 16, 10, tzinfo=ET), None) == "2026-10-08", \
        "a start reads up to the last settled session"
    assert due(datetime(2026, 10, 9, 16, 10, tzinfo=ET), "2026-10-08") is None, \
        "Friday's close is still settling"
    assert due(datetime(2026, 10, 9, 16, 31, tzinfo=ET), "2026-10-08") == "2026-10-09"
    assert due(datetime(2026, 10, 10, 12, 0, tzinfo=ET), "2026-10-09") is None
    assert due(datetime(2026, 10, 12, 10, 0, tzinfo=ET), "2026-10-09") is None
    assert due(datetime(2026, 11, 27, 13, 31, tzinfo=ET), "2026-11-25") == "2026-11-27", \
        "a half day settles from 1:30pm"


def test_the_follow_up_runs_above_the_market_hours_gate():
    """Below it, the evening pass that reads the settled candle never ran."""
    src = open("app/main.py", encoding="utf-8").read()
    loop = src[src.index("async def _tracker_loop"):]
    assert loop.index("signal_followup_due(") < loop.index("if not is_open and not just_closed:")


def _check_with(monkeypatch, res, lookup):
    monkeypatch.setattr(main, "_swing_snapshot", lambda *a, **k: {"quote": {"price": 1.0}})
    monkeypatch.setattr(main.YF_PROVIDER, "earnings_date", lambda t: None)
    monkeypatch.setattr(main, "_attach_setups", lambda payload, t: payload.update(setups=res))
    monkeypatch.setattr(main.auth_deps, "current_user", lookup)
    return TestClient(main.app).post("/api/watches/check", json={
        "ticker": "X", "watches": [{"id": "w1", "kind": "swing_setup", "params": {"preset": "any"}}]})


def test_a_page_check_records_for_the_signed_in_reader(two, monkeypatch):
    _df, res, _hit = fired()
    reply = _check_with(monkeypatch, res, lambda request: {"id": two[0]})
    assert reply.status_code == 200, reply.text
    assert reply.json()["met"][0]["signal_record"]["symbol"] == "X"
    rows = signal_history.history(two[0])
    assert len(rows) == 1 and rows[0]["origin"] == "alert check on the page"


def test_a_page_check_survives_an_accounts_outage(two, monkeypatch):
    _df, res, _hit = fired()

    def broken(request):
        raise sqlite3.OperationalError("database is locked")

    reply = _check_with(monkeypatch, res, broken)
    assert reply.status_code == 200, reply.text
    met = reply.json()["met"]
    assert met and met[0]["signal_record"]["strategy"] == "trend_pullback", \
        "the guest copy is still handed back"
    assert signal_history.history(two[0]) == []
