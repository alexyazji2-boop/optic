"""The forward research archive (app/research_book.py).

Research rounds R1 and R2 of 2026-10-21 found no validated strategy, and the inputs that make
Optic's strongest claims (flow, gamma, news) have no history to test on. This archive is the
prospective test, so the things that would quietly ruin it are what these tests hold: rules that
drift from the registered ones, a scan that records the same signal twice, a shadow trade that
fills or exits differently from the replay, an earnings time read in the wrong zone, and any of
it reading like a recommendation.
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from app import research_book as RB


@pytest.fixture()
def archive(tmp_path, monkeypatch):
    monkeypatch.setenv("TRACKER_DATA_DIR", str(tmp_path))
    RB.init_db()
    return RB


def _frame(closes, opens=None, spread=0.5, start="2025-01-02"):
    idx = pd.bdate_range(start, periods=len(closes))
    c = np.array(closes, dtype=float)
    o = np.array(opens, dtype=float) if opens is not None else c - 0.1
    return pd.DataFrame({"Open": o, "High": np.maximum(o, c) + spread, "Low": np.minimum(o, c) - spread,
                         "Close": c, "Volume": np.full(len(c), 1e6)}, index=idx)


def _pullback_frame():
    """A steady uptrend, a five-session pullback of about 7 points to the 50-day, then a reclaim
    on bar 284 and a second up close on bar 285."""
    closes = [50 + 0.2 * i for i in range(280)] + [104.3, 102.8, 101.3, 99.8, 101.8, 102.8]
    opens = [c - 0.1 for c in closes[:280]] + [105.5, 104.0, 102.5, 101.0, 100.0, 101.6]
    return _frame(closes, opens)


# ---------------------------------------------------------------- frozen rules


def test_the_registered_constants():
    assert (RB.RVOL_MIN, RB.STOP_BUFFER_ATR, RB.STOP_FLOOR_ATR, RB.STOP_CAP_ATR) == (1.25, 0.25, 1.5, 4.0)
    assert (RB.MAX_GAP_ATR, RB.TARGET_R, RB.HOLD_DAYS, RB.COOLDOWN_SESSIONS) == (1.0, 2.0, 45, 5)
    assert (RB.REACTION_MIN, RB.REACTION_RVOL) == (0.03, 2.0)
    assert RB.COST_BPS == {"fund": 10.0, "stock": 15.0}
    assert RB.RULES_VERSION == "rb-2026-10-21"


def test_every_setup_says_what_it_watches_and_what_triggers_it():
    for key, s in RB.SETUPS.items():
        for field in ("name", "holding", "context", "location", "trigger"):
            assert s[field], (key, field)


def test_nothing_it_shows_reads_with_an_em_dash_or_a_promise():
    text = json.dumps(RB.SETUPS) + RB.RESEARCH_STATUS + " ".join(RB.LIMITS)
    assert "—" not in text
    for word in ("probability", "high probability", "guarantee", "recommend "):
        assert word not in text.lower(), word
    assert RB.RESEARCH_STATUS.startswith("No validated strategy")


# ---------------------------------------------------------------- setups


def test_a_pullback_triggers_on_its_first_bar_only():
    a = RB.arrays(_pullback_frame(), _frame([400 + 0.1 * i for i in range(286)]))
    assert RB.stage(a, "A", 284)[0] == "triggered"
    state, level = RB.stage(a, "A", 285)
    assert state == "armed", "the same condition a second day is the same signal"
    assert level == pytest.approx(min(a["l"][281:286]))


def test_no_trend_no_setup():
    falling = _frame([150 - 0.2 * i for i in range(286)])
    a = RB.arrays(falling, falling)
    assert RB.stage(a, "A", 284)[0] == "none"


def test_too_little_history_is_not_a_signal():
    a = RB.arrays(_pullback_frame().iloc[:250], _frame([400.0] * 250))
    assert RB.stage(a, "A", 249)[0] == "none"


# ---------------------------------------------------------------- shadow trades


def _trade(frame, t, level, kind="fund"):
    a = RB.arrays(frame, frame)
    return a, {"signal_date": a["dates"][t].isoformat(), "signal_close": a["c"][t], "atr": a["atr"][t],
               "stop_level": level, "status": "intended", "kind": kind}


def test_a_trigger_fills_at_the_next_open_with_the_floor_and_a_2r_target():
    f = _frame([100.0] * 300)
    a, tr = _trade(f, 290, 99.8)                       # a stop 0.45 ATR under: floored to 1.5 ATR
    out = RB.advance(tr, a)
    atr = tr["atr"]
    assert out["status"] in ("open", "closed")
    assert out["entry"] == pytest.approx(a["o"][291])
    assert out["entry"] - out["stop"] == pytest.approx(1.5 * atr)
    assert out["target"] - out["entry"] == pytest.approx(2 * (out["entry"] - out["stop"]))


def test_a_gap_above_one_atr_skips_the_trade():
    closes = [100.0] * 300
    opens = list(closes)
    opens[291] = 104.0
    a, tr = _trade(_frame(closes, opens), 290, 98.0)
    assert RB.advance(tr, a)["status"] == "skipped"


def test_stop_first_when_one_bar_holds_both_and_costs_are_charged():
    closes = [100.0] * 300
    f = _frame(closes)
    f.iloc[292, f.columns.get_loc("High")] = 130.0
    f.iloc[292, f.columns.get_loc("Low")] = 80.0
    a, tr = _trade(f, 290, 97.0, kind="stock")
    out = RB.advance(tr, a)
    assert out["status"] == "closed" and out["reason"] == "stop"
    assert out["r_gross"] == pytest.approx(-1.0, abs=1e-6)
    assert out["cost_r"] > 0 and out["r_net"] < out["r_gross"]


def test_the_time_stop_closes_at_45_days():
    a, tr = _trade(_frame([100.0] * 360, spread=0.2), 290, 99.4)
    out = RB.advance(tr, a)
    assert out["reason"] == "time"
    held = date.fromisoformat(out["exit_date"]) - date.fromisoformat(out["entry_date"])
    assert held.days >= 45


def test_advancing_twice_changes_nothing():
    a, tr = _trade(_frame([100.0] * 300), 290, 98.0)
    once = RB.advance(tr, a)
    twice = RB.advance(once, a)
    assert {k: v for k, v in twice.items() if k != "updated_at"} == {k: v for k, v in once.items() if k != "updated_at"}


# ---------------------------------------------------------------- earnings timing


def test_sec_acceptance_times_read_as_eastern_after_the_offset():
    """Measured 2026-10-21: Apple's 4:30pm ET release is stored as 00:30Z the next day."""
    blob = {"filings": {"recent": {
        "form": ["8-K", "8-K", "10-Q", "8-K"],
        "items": ["2.02,9.01", "2.02,9.01", "", "5.02"],
        "acceptanceDateTime": ["2026-07-31T00:30:28.000Z", "2026-01-30T02:30:33.000Z",
                               "2026-08-01T20:00:00.000Z", "2026-05-01T12:00:00.000Z"]}}}
    rels = RB.releases_from_submissions(blob)
    assert [(r["date"], r["timing"]) for r in rels] == [("2026-01-29", "after_close"), ("2026-07-30", "after_close")]
    assert rels[1]["release_et"].startswith("2026-07-30T16:30")
    jpm = RB.releases_from_submissions({"filings": {"recent": {
        "form": ["8-K"], "items": ["2.02"], "acceptanceDateTime": ["2026-10-13T14:30:00.000Z"]}}})
    assert jpm[0]["timing"] == "before_open" and jpm[0]["release_et"].startswith("2026-10-13T06:30")


# EDGAR's index page for Mondelez's 8-K of 2024-04-30, the part that matters, as fetched for round R3.
MDLZ_INDEX = """<div class="formGrouping">
         <div class="infoHead">Filing Date</div>
         <div class="info">2024-04-30</div>
         <div class="infoHead">Accepted</div>
         <div class="info">2024-04-30 16:07:24</div>
         <div class="infoHead">Documents</div>"""


def _blob(cik, rows):
    """A submissions document: rows of (accession, filingDate, acceptanceDateTime, form, items)."""
    return {"cik": str(cik), "filings": {"recent": {
        "accessionNumber": [r[0] for r in rows], "filingDate": [r[1] for r in rows],
        "acceptanceDateTime": [r[2] for r in rows], "form": [r[3] for r in rows], "items": [r[4] for r in rows]}}}


def test_a_json_time_before_edgar_opens_is_read_as_true_utc():
    """Sealed Air 2021-11-02 is stored 11:02Z and was accepted at 07:02 ET. Read as UTC plus the offset
    it would be 03:02 ET, when EDGAR accepts nothing."""
    rels = RB.releases_from_submissions(_blob(1012100, [("0001012100-21-000045", "2021-11-02",
                                                         "2021-11-02T11:02:38.000Z", "8-K", "2.02,9.01")]))
    assert rels[0]["release_et"].startswith("2021-11-02T07:02:38") and rels[0]["timing"] == "before_open"
    assert rels[0]["clock"] == "json"


def test_the_index_page_time_wins_over_the_json():
    """Mondelez 2024-04-30 is stored 20:07Z, which the JSON reading takes for 12:07 ET (mid-session,
    reacting the same day). Its index page says 16:07 ET: after the close, reacting the next day."""
    blob = _blob(1103982, [("0001103982-24-000052", "2024-04-30", "2024-04-30T20:07:24.000Z", "8-K", "2.02,9.01")])
    json_only = RB.releases_from_submissions(blob)
    assert (json_only[0]["timing"], json_only[0]["clock"]) == ("during_session", "json")
    asked = []
    rels = RB.releases_from_submissions(blob, lambda acc: asked.append(acc) or RB.accepted_from_index(MDLZ_INDEX),
                                        today=date(2024, 5, 10))
    assert asked == ["0001103982-24-000052"]
    assert rels[0]["release_et"].startswith("2024-04-30T16:07:24") and rels[0]["timing"] == "after_close"
    assert rels[0]["clock"] == "index page"
    days = [date(2024, 4, 29) + timedelta(days=i) for i in range(4)]
    assert RB.reaction_index(days, json_only[0]) == 1 and RB.reaction_index(days, rels[0]) == 2


def test_index_pages_are_read_only_for_releases_the_bars_can_reach():
    blob = _blob(1103982, [("0001103982-21-000001", "2021-02-02", "2021-02-02T21:05:00.000Z", "8-K", "2.02"),
                           ("0001103982-24-000052", "2024-04-30", "2024-04-30T20:07:24.000Z", "8-K", "2.02")])
    asked = []
    RB.releases_from_submissions(blob, lambda acc: asked.append(acc) or None, today=date(2024, 5, 10))
    assert asked == ["0001103982-24-000052"]          # the 2021 release is older than INDEX_PAGE_DAYS


def test_an_index_page_is_read_once_and_a_failed_one_is_asked_again(archive):
    calls = []

    def page(url):
        calls.append(url)
        return MDLZ_INDEX
    et = archive.accepted_time(1103982, "0001103982-24-000052", page)
    assert et.isoformat().startswith("2024-04-30T16:07:24") and et.utcoffset() == timedelta(hours=-4)
    assert calls == ["https://www.sec.gov/Archives/edgar/data/1103982/000110398224000052/0001103982-24-000052-index.htm"]
    assert archive.accepted_time(1103982, "0001103982-24-000052", page) == et and len(calls) == 1

    def down(url):
        raise OSError("403")
    assert archive.accepted_time(1103982, "0001103982-24-000099", down) is None
    assert archive._rows("SELECT * FROM rb_sec_accepted WHERE accession='0001103982-24-000099'") == []


def test_a_symbol_takes_releases_from_every_cik_it_filed_under(archive):
    """ExxonMobil Holdings (2115436) files from 2026-07; Exxon Mobil Corp (34088) filed before it. The
    July release filed under both counts once."""
    blobs = {2115436: _blob(2115436, [("0002115436-26-000002", "2026-07-31", "2026-07-31T10:30:00.000Z", "8-K", "2.02")]),
             34088: _blob(34088, [("0000034088-26-000020", "2026-05-01", "2026-05-01T10:30:00.000Z", "8-K", "2.02"),
                                  ("0000034088-26-000031", "2026-07-31", "2026-07-31T10:29:00.000Z", "8-K", "2.02"),
                                  ("0000034088-26-000012", "2026-01-30", "2026-01-30T11:30:00.000Z", "8-K", "2.02")])}
    fetched = []

    def fetch(url):
        cik = int(url.rsplit("CIK", 1)[1].split(".")[0])
        fetched.append(cik)
        return blobs[cik]
    rels = archive.sec_releases("XOM", lambda s: 2115436, fetch, None, today=date(2026, 8, 3))
    assert fetched == [2115436, 34088]
    assert [r["date"] for r in rels] == ["2026-01-30", "2026-05-01", "2026-07-31"]
    assert rels[-1]["accession"] == "0000034088-26-000031"     # the first one accepted, by a minute
    assert archive.sec_releases("XOM", lambda s: 2115436, fetch, None) == rels and len(fetched) == 2   # kept a day


def test_a_kept_copy_from_the_old_clock_is_read_again(archive):
    with archive._LOCK, archive._connect() as conn:
        conn.execute("INSERT INTO rb_sec (symbol, fetched_at, releases) VALUES (?,?,?)",
                     ("MDLZ", archive._now(), json.dumps([{"release_et": "2024-04-30T12:07:24-04:00",
                                                          "date": "2024-04-30", "timing": "during_session"}])))
    blob = _blob(1103982, [("0001103982-24-000052", "2024-04-30", "2024-04-30T20:07:24.000Z", "8-K", "2.02,9.01")])
    rels = archive.sec_releases("MDLZ", lambda s: 1103982, lambda url: blob, lambda url: MDLZ_INDEX,
                                today=date(2024, 5, 10))
    assert (rels[0]["timing"], rels[0]["clock"]) == ("after_close", "index page")
    kept = json.loads(archive._rows("SELECT releases FROM rb_sec WHERE symbol='MDLZ'")[0]["releases"])
    assert kept["clock"] == RB.CLOCK_VERSION


def test_a_missing_extra_cik_loses_only_its_part(archive):
    blob = _blob(2115436, [("0002115436-26-000002", "2026-07-31", "2026-07-31T10:30:00.000Z", "8-K", "2.02")])

    def fetch(url):
        if "CIK0000034088" in url:
            raise OSError("timed out")
        return blob
    rels = archive.sec_releases("XOM", lambda s: 2115436, fetch, None, today=date(2026, 8, 3))
    assert [r["date"] for r in rels] == ["2026-07-31"]


def test_the_server_reads_index_pages_through_the_polite_fetch():
    fn = MAIN[MAIN.index("def _research_book_releases"):]
    fn = fn[:fn.index("\n\n\n")]
    assert "feeds_mod.fetch_text(" in fn and "store=False" in fn
    assert "sec_releases(symbol, cik, fetch, fetch_text)" in fn


def test_the_reaction_session_follows_the_release_timing():
    days = [date(2026, 10, 12) + timedelta(days=i) for i in range(5)]
    assert RB.reaction_index(days, {"date": "2026-10-13", "timing": "before_open"}) == 1
    assert RB.reaction_index(days, {"date": "2026-10-13", "timing": "after_close"}) == 2
    assert RB.reaction_index(days, {"date": "2026-10-13", "timing": "during_session"}) == 1


# ---------------------------------------------------------------- the daily run


def _universe_frames():
    base = _pullback_frame()
    frames = {"AAA": base, "SPY": _frame([400 + 0.1 * i for i in range(286)])}
    for s in RB.SECTOR_SPDRS:
        frames[s] = _frame([50 + 0.05 * i for i in range(286)])
    return frames, base.index[284].date()


def test_a_day_is_recorded_once_however_often_it_runs(archive):
    frames, day = _universe_frames()
    hist = lambda s: frames[s].loc[:pd.Timestamp(day)]   # noqa: E731
    first = archive.run_daily(hist, ["AAA"], ["AAA"], today=day)
    again = archive.run_daily(hist, ["AAA"], ["AAA"], today=day)
    assert first["triggered"] == 1 and first["recorded"] >= 1
    assert again["recorded"] == 0 and again["triggered"] == 0
    assert len(archive._rows("SELECT * FROM rb_trades")) == 1


def test_the_next_day_fills_the_shadow_trade_and_blocks_a_repeat(archive):
    frames, day = _universe_frames()
    archive.run_daily(lambda s: frames[s].loc[:pd.Timestamp(day)], ["AAA"], ["AAA"], today=day)
    nxt = frames["AAA"].index[285].date()
    archive.run_daily(lambda s: frames[s].loc[:pd.Timestamp(nxt)], ["AAA"], ["AAA"], today=nxt)
    trade = archive._rows("SELECT * FROM rb_trades")[0]
    assert trade["status"] in ("open", "closed") and trade["entry_date"] == nxt.isoformat()
    assert trade["last_close"] == pytest.approx(frames["AAA"]["Close"].iloc[285])


def test_a_trigger_keeps_the_snapshot_reads_with_their_time(archive):
    frames, day = _universe_frames()
    snap = {"generated_at": "2026-10-21T20:25:00+00:00",
            "verdict": {"composite_score": 41.5, "stance": "bullish", "components": {"gamma": 20.0, "flow": 10.0}},
            "gex": {"regime": {"state": "positive", "flip_point": 98.0, "flip_distance_pct": -3.5},
                    "totals": {"net_gex": 1.2e9, "net_vanna": -3e6},
                    "levels": {"call_wall": {"strike": 110.0}, "put_wall": {"strike": 95.0}}},
            "flow": {"flow_score": 25.0, "notes": ["60% of the time value traded was in calls (bought or sold: the feed has no side)"]},
            "entry_plan": {"iv_context": {"verdict": "fair"}, "recommended": {"strike": 100, "expiry": "2026-12-18", "entry_mid": 4.2, "delta": 0.5}},
            "next_earnings_date": "2026-11-05"}
    archive.run_daily(lambda s: frames[s].loc[:pd.Timestamp(day)], ["AAA"], ["AAA"], snapshot_fn=lambda s: snap, today=day)
    row = archive._rows("SELECT positioning FROM rb_signals WHERE state='triggered'")[0]
    pz = json.loads(row["positioning"])
    assert pz["taken_at"] == "2026-10-21T20:25:00+00:00"
    assert (pz["gamma_regime"], pz["flip"], pz["call_wall"], pz["put_wall"]) == ("positive", 98.0, 110.0, 95.0)
    assert pz["net_vanna_vex"] == -3e6 and pz["flow_score"] == 25.0 and pz["iv_verdict"] == "fair"
    assert "no trade side" in pz["caveat"] and "assume dealers" in pz["caveat"]


def test_reading_the_archive_calls_nothing(archive, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("state() must not fetch")
    monkeypatch.setattr(RB, "run_daily", boom)
    out = archive.state()
    assert out["research_status"].startswith("No validated strategy")
    assert out["record"]["judgeable"] is False and out["candidates"] == []


def test_off_unless_switched_on(monkeypatch):
    monkeypatch.delenv("OPTIC_RESEARCH_BOOK", raising=False)
    assert RB.enabled() is False
    monkeypatch.setenv("OPTIC_RESEARCH_BOOK", "true")
    assert RB.enabled() is True


def test_due_after_the_close_once_a_day(archive):
    from datetime import datetime, timezone
    assert archive.due(datetime(2026, 10, 21, 19, 0, tzinfo=timezone.utc)) is False      # 15:00 ET
    assert archive.due(datetime(2026, 10, 21, 20, 30, tzinfo=timezone.utc)) is True      # 16:30 ET
    assert archive.due(datetime(2026, 10, 24, 21, 0, tzinfo=timezone.utc)) is False      # Saturday


# ---------------------------------------------------------------- server and page


MAIN = open("app/main.py").read()
PAGE = open("static/v2/js/pages/tracker.js").read()


def test_the_server_runs_it_only_when_switched_on_and_reads_it_freely():
    start = MAIN[MAIN.index("async def _start_tracker"):]
    start = start[:start.index("\n\n\n")]
    assert "if research_book_mod.enabled():" in start
    route = MAIN[MAIN.index('@app.get("/api/research-book")'):]
    route = route[:route.index("\n\n\n")]
    assert "research_book_mod.state" in route and "run_daily" not in route


def test_the_page_shows_the_watch_beside_the_books_not_in_them():
    assert "${research(D.rb)}" in PAGE and "'/api/research-book'" in PAGE
    sec = PAGE[PAGE.index("function research("):PAGE.index("/* ---------------- page")]
    assert "Nothing here is sized, sent anywhere or added to a book" in sec
    assert 'class="pill"' not in sec and "—" not in sec
    assert "Research status." in sec and "Shadow trades" in sec
    for bad in ("probability", "confidence", "high-conviction"):
        assert bad not in sec.lower(), bad


def test_a_redraw_keeps_the_folds_the_reader_opened():
    """The page redraws when the risk read lands and every 4s while a scan runs; it used to
    close every open fold, the research cards' included."""
    paint = PAGE[PAGE.index("function paint()"):PAGE.index("async function load(")]
    assert "details[open] > summary" in paint and "x.parentElement.open = true" in paint
