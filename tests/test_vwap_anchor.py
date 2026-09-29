"""Anchored VWAP starts at the range on screen, and an anchor can be given at all.

Reported with a screenshot of TSLA's 1W chart of one year, the line labelled
148.78 under a year spent between $300 and $500: "there is no way the anchored
VWAP is at $148 for TSLA". Two faults, both tested here.

* The chart never sent an anchor, so VWAP started at the first bar of whatever
  history the studies were computed over: ten years of weekly bars (from
  2016-09-26, which is where 148.78 comes from) under a one-year chart, two
  years of daily bars under a daily one. The chart now sends the first bar of
  its range, and choosing a range moves it.
* An anchor could not have worked anyway. The daily and weekly bars carry the
  exchange's timezone, and every anchored request came back "Invalid
  comparison between dtype=datetime64[ns, America/New_York] and Timestamp".

Measured on the local server after the fix: TSLA's weekly VWAP from 2025-10-06
is 408.22, and the daily one from 2025-09-29 is 410.40.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.analytics import indicators

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
NY = "America/New_York"


def _bars(index, prices, volume=1_000_000.0):
    prices = np.asarray(prices, dtype=float)
    return pd.DataFrame({"Open": prices, "High": prices + 1, "Low": prices - 1,
                         "Close": prices, "Volume": np.full(len(prices), volume)},
                        index=index)


def _years(freq="B", n=520):
    """Years of bars that start cheap and end dear, like TSLA's: a VWAP from
    the first of them sits far under the last year's prices."""
    idx = pd.date_range("2016-09-26", periods=n, freq=freq, tz=NY)
    return _bars(idx, np.linspace(15.0, 420.0, n))


# ------------------------------------------------------------------ server


def test_an_anchor_works_on_bars_that_carry_the_exchange_timezone():
    df = _years()
    anchor = str(df.index[-252].date())
    out = indicators.compute(df, ["vwap"], anchor=anchor)["indicators"]["vwap"]
    assert out["available"] is True, out.get("reason")
    values = out["lines"][0]["values"]
    assert values[-253] is None and values[-252] is not None
    assert out["anchor"] == anchor


def test_the_range_anchor_puts_vwap_among_the_prices_it_averages():
    df = _years()
    whole = indicators.compute(df, ["vwap"])["indicators"]["vwap"]["last"]
    year = indicators.compute(df, ["vwap"], anchor=str(df.index[-252].date()))
    last = year["indicators"]["vwap"]["last"]
    recent = df["Close"].iloc[-252:]
    assert whole < recent.min(), "from the first bar of the history it sits under them all"
    assert recent.min() < last < recent.max()


def test_a_weekly_anchor_on_its_monday_includes_that_week():
    idx = pd.date_range("2016-09-26", periods=520, freq="W-MON", tz=NY)
    df = _bars(idx, np.linspace(15.0, 420.0, 520))
    monday = str(idx[-52].date())
    out = indicators.compute(df, ["vwap"], anchor=monday)["indicators"]["vwap"]
    values = out["lines"][0]["values"]
    assert values[-52] is not None and values[-53] is None
    assert out["anchor"] == monday


def test_an_anchor_on_a_weekend_starts_on_the_next_session_and_says_so():
    idx = pd.date_range("2025-09-22", periods=30, freq="B", tz=NY)
    df = _bars(idx, np.linspace(400, 430, 30))
    out = indicators.compute(df, ["vwap"], anchor="2025-09-27")["indicators"]["vwap"]
    assert out["anchor"] == "2025-09-29"
    # The first bar in is 2025-09-29, so the average is that bar's own price
    # (to the cent the payload is rounded to).
    assert out["lines"][0]["values"][5] == pytest.approx(df["Close"].iloc[5], abs=0.01)


def test_with_no_anchor_it_starts_at_the_first_bar_as_before():
    df = _years(n=60)
    out = indicators.compute(df, ["vwap"])["indicators"]["vwap"]
    assert out["anchor"] == "2016-09-26"
    assert out["lines"][0]["values"][0] == pytest.approx(15.0)


class _Provider:
    def __init__(self):
        self.asked = []

    def history(self, symbol, period="2y", interval="1d"):
        self.asked.append((symbol, period, interval))
        freq = "W-MON" if interval == "1wk" else "B"
        return _years(freq=freq, n=520)


def test_the_route_passes_the_anchor_through_for_daily_and_weekly_bars(monkeypatch):
    feed = _Provider()
    monkeypatch.setattr(main, "PROVIDER", feed)
    monkeypatch.setattr(main, "YF_PROVIDER", feed)
    client = TestClient(main.app)
    daily = client.get("/api/indicators/TSLA", params={"ids": "vwap", "anchor": "2018-01-02"})
    got = daily.json()["indicators"]["vwap"]
    assert got["available"] is True and got["anchor"] == "2018-01-02"
    weekly = client.get("/api/indicators/TSLA", params={
        "ids": "vwap", "weekly": "true", "range": "10y", "anchor": "2025-10-06"}).json()
    assert weekly["indicators"]["vwap"]["anchor"] == "2025-10-06"
    assert feed.asked[-1] == ("TSLA", "10y", "1wk")


# ------------------------------------------------------------------ client


def _fn(name):
    src = re.sub(r"/\*.*?\*/", " ", APP, flags=re.S)
    start = src.index("function %s(" % name)
    return src[start:].split("\nfunction ", 1)[0]


def _anchor(range_, interval, dates, ids="['vwap']"):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    script = """
      load('tests/support/browser_stubs.js');
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      document.documentElement.style.removeProperty = function () {};
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
      chartRange = %s; chartInterval = %s;
      var dates = %s;
      var d = { ticker: '', technicals: { price_series: {
        dates: dates, open: dates.map(function () { return 1; }),
        high: dates.map(function () { return 1; }), low: dates.map(function () { return 1; }),
        close: dates.map(function () { return 1; }), volume: dates.map(function () { return 1; }) } } };
      print('RESULT:' + JSON.stringify({ anchor: vwapAnchorFor(d),
        query: vwapAnchorQuery(%s, d), none: vwapAnchorFor(null) }));
    """ % (json.dumps(range_), json.dumps(interval), json.dumps(dates), ids)
    proc = subprocess.run([exe, "-e", script], capture_output=True, text=True,
                          timeout=180, cwd=str(ROOT))
    blob = proc.stdout + proc.stderr
    assert "RESULT:" in blob, blob[-1500:]
    return json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])


DAYS = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2023-10-02", periods=760)]


def test_the_chart_anchors_at_the_first_bar_of_its_range():
    got = _anchor("1y", "daily", DAYS)
    first = DAYS[-252]
    assert got["anchor"] == first and got["query"] == "&anchor=" + first
    assert got["none"] == ""


def test_a_weekly_range_anchors_at_its_first_weeks_monday():
    got = _anchor("1y", "weekly", DAYS)
    assert pd.Timestamp(got["anchor"]).dayofweek == 0
    # A year of weeks back from the newest, give or take the partial week.
    assert 51 <= (pd.Timestamp(DAYS[-1]) - pd.Timestamp(got["anchor"])).days / 7 <= 53


def test_the_anchor_rides_only_on_a_request_that_carries_vwap():
    got = _anchor("1y", "daily", DAYS, ids="['bollinger', 'keltner']")
    assert got["query"] == "" and got["anchor"] == DAYS[-252]


def test_an_intraday_size_sends_no_anchor():
    """The server anchors minute bars at the window's first bar already."""
    assert _anchor("5", "daily", DAYS)["anchor"] == ""


def test_both_tabs_ask_for_their_range_anchor_and_key_their_payload_on_it():
    ws = _fn("wsLoadIndicators")
    assert "const key = ids.join(',') + vwapAnchorQuery(ids, STATE.chartData);" in ws
    assert "+ vwapAnchorQuery(ids, STATE.chartData));" in ws
    assert "now.join(',') + vwapAnchorQuery(now, STATE.chartData) !== key" in ws
    swing = _fn("loadIndicators")
    assert "const anchor = vwapAnchorQuery(indicatorIds, STATE.swing);" in swing
    assert "|${bars}${anchor}`;" in swing
    assert "studyQuery(bars) + anchor);" in swing
