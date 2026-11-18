"""Pass 2, item 5 (2026-11-17): intraday lines on Home's ticker rows, a 1D range on Home's headline chart, and the
live dot's delayed, live or closed status, behind one intraday source a licensed feed slots into (app/sparklines.py).
"""
from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import main, sparklines as SL
from tests.test_frontend_v2_stage0 import V2

OPEN = {"is_regular": True, "label": "Regular session"}
SHUT = {"is_regular": False, "label": "After hours"}


class Fake(SL.IntradaySource):
    name, label, delayed_minutes = "fake", "Test feed, delayed", 15

    def __init__(self, bars=None, daily=None, boom=False):
        self.bars, self.daily, self.boom, self.asked = bars or {}, daily or {}, boom, []

    def bars_since_open(self, symbol):
        self.asked.append(symbol)
        if self.boom:
            raise RuntimeError("refused")
        return {"times": ["2026-11-17T14:30:00+00:00", "2026-11-17T14:35:00+00:00", "2026-11-17T14:40:00+00:00"][:len(self.bars.get(symbol, []))], "closes": self.bars.get(symbol, [])}

    def daily_closes(self, symbol, n=30):
        c = self.daily.get(symbol, [])
        return {"dates": ["2026-10-{:02d}".format(i + 1) for i in range(len(c))], "closes": c}


def test_in_session_a_row_is_todays_line_coloured_by_the_days_move_not_its_own_span():
    # starts above yesterday's close and drifts down, but ends above it: the day is up, so the line is green
    src = Fake(bars={"AAPL": [251.0, 250.0, 249.5]})
    out = SL.build(src, ["AAPL"], OPEN, {"AAPL": 248.0})
    r = out["rows"][0]
    assert r["kind"] == "intraday" and r["direction"] == "up" and r["change_pct"] == 0.6
    assert out["status"] == "delayed" and out["status_text"] == "Delayed 15 min" and out["refresh_seconds"] == 300


def test_closed_market_or_no_intraday_bars_fall_back_to_30_daily_closes_and_say_so():
    src = Fake(bars={"AAPL": [1.0, 2.0]}, daily={"AAPL": [10.0, 11.0, 12.0], "MSFT": [5.0, 4.0]})
    shut = SL.build(src, ["AAPL"], SHUT, {})
    assert shut["status"] == "closed" and shut["refresh_seconds"] is None and src.asked == [], "no intraday asked when closed"
    assert shut["rows"][0]["kind"] == "daily" and "market is closed" in shut["rows"][0]["note"]
    gone = SL.build(Fake(boom=True, daily={"MSFT": [5.0, 4.0]}), ["MSFT"], OPEN, {"MSFT": 4.5})
    assert gone["rows"][0]["kind"] == "daily" and gone["rows"][0]["direction"] == "down"
    assert SL.build(Fake(), ["ZZZQ"], OPEN, {})["rows"][0]["available"] is False


def test_a_licensed_source_slots_in_by_name_without_touching_the_rows(monkeypatch):
    class Licensed(Fake):
        name, label, realtime, licensed, delayed_minutes = "vendor", "Vendor, real-time", True, True, 0
    monkeypatch.setitem(SL.SOURCES, "vendor", lambda provider: Licensed(bars={"AAPL": [1.0, 2.0]}))
    monkeypatch.setenv("OPTIC_INTRADAY_SOURCE", "vendor")
    src = SL.source(provider=None)
    out = SL.build(src, ["AAPL"], OPEN, {"AAPL": 1.5})
    assert out["status"] == "live" and out["licensed"] is True and out["source_name"] == "vendor"
    monkeypatch.setenv("OPTIC_INTRADAY_SOURCE", "unknown")
    assert SL.source(provider=None).name == "free", "an unknown name falls back to the free feed"


def test_the_free_source_reads_five_minute_bars_through_the_provider():
    class P:
        def intraday_history(self, s, period, interval, prepost):
            assert (period, interval, prepost) == ("1d", "5m", False)
            return pd.DataFrame({"Close": [1.0, float("nan"), 2.0]}, index=pd.to_datetime(["2026-11-17 14:30", "2026-11-17 14:35", "2026-11-17 14:40"], utc=True))

        def history(self, s, period, interval):
            return pd.DataFrame()
    got = SL.FreeFeedSource(P()).bars_since_open("AAPL")
    assert got["closes"] == [1.0, 2.0] and len(got["times"]) == 3


def test_one_request_for_all_the_rows_capped_at_30_and_checked(monkeypatch):
    c = TestClient(main.app)
    assert c.get("/api/sparklines?symbols=").status_code == 422
    monkeypatch.setattr(SL, "source", lambda provider: Fake(daily={s: [1.0, 2.0] for s in ["S{}".format(i) for i in range(40)]}))
    monkeypatch.setattr(main.YF_PROVIDER, "quote", lambda s: {"previous_close": 1.0})
    r = c.get("/api/sparklines?symbols=" + ",".join("S{}".format(i) for i in range(40)) + ",<b>")
    assert r.status_code == 200 and len(r.json()["rows"]) == 30


def test_home_draws_todays_line_with_its_status_and_offers_1d_on_the_headline_chart():
    src = (V2 / "js" / "pages" / "workspace.js").read_text()
    assert "/api/sparklines?symbols=${list}" in src and "${today ? 'Today' : '30 sessions'}" in src
    assert "['1d', '1D', 'today']" in src and "live-dot is-${FEAT.c.status}" in src
    css = (V2 / "css" / "components.css").read_text()
    assert ".live-dot.is-delayed" in css and "prefers-reduced-motion: reduce) { .live-dot.is-live { animation: none; }" in css
