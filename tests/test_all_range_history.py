"""All means every bar since the listing, on every chart that offers it.

Reported with a screenshot of NVDA on the Charting tab, 1D and All, starting
at October 2024: "NVDA did not IPO in 2024, this is not accurate to the ALL
button". All drew whatever the other ranges had loaded: the ticker payload's
two years of daily bars, ten years of weekly ones, and twelve on the Investing
chart. It now asks for the whole history when it is drawn, and the 1M to 1Y
ranges draw what they did.

Checked in a browser: NVDA's All on 1D began on 1999-01-22 with 6,966 bars,
1W on 1999-01-18 with 1,446, the Options tab said "daily bars, 6966 of 6966
shown" with its RSI over the same span, the Investing chart went from 627 weeks
starting 2014-10-03 to 1,446, and IBM's All drew 16,296 sessions back to 1962.
"""
from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.analytics import stage

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
CHARTS = (ROOT / "static/charts.js").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


class _Feed:
    """Dated bars from the listing on, and a record of what was asked for."""

    name = "stub"

    def __init__(self, n=700, freq="B", start="1999-01-22"):
        self.n, self.freq, self.start = n, freq, start
        self.calls = []

    def history(self, symbol, period="2y", interval="1d"):
        self.calls.append((symbol, period, interval))
        if not self.n:
            return pd.DataFrame()
        idx = pd.date_range(self.start, periods=self.n, freq=self.freq)
        close = pd.Series([0.0410156 + i * 0.01 for i in range(self.n)], index=idx)
        return pd.DataFrame({"Open": close, "High": close + 0.02, "Low": close * 0.99,
                             "Close": close, "Volume": [2.5e6] * self.n}, index=idx)


def _js(script, prelude=None):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    head = prelude if prelude is not None else """
      load('tests/support/browser_stubs.js');
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      document.documentElement.style.removeProperty = function () {};
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
    """
    out = subprocess.run([exe, "-e", head + script], capture_output=True, text=True,
                         timeout=120, cwd=str(ROOT))
    assert "RESULT:" in out.stdout, (out.stdout + out.stderr)[-2000:]
    return json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])


def _charts(script):
    return _js(script, prelude=(ROOT / "tests/support/recording_dom.js").read_text() + CHARTS)


# ------------------------------------------------------------------ server


def test_the_whole_daily_history_is_its_own_request(monkeypatch):
    feed = _Feed(n=700)
    monkeypatch.setattr(main, "YF_PROVIDER", feed)
    body = TestClient(main.app).get("/api/daily-bars/nvda").json()
    assert feed.calls == [("NVDA", "max", "1d")]
    assert body["available"] is True and body["ticker"] == "NVDA" and body["bars"] == 700
    assert len(body["dates"]) == len(body["open"]) == len(body["close"]) == 700
    assert body["dates"][0] == "1999-01-22", "from the first session"
    assert body["close"][0] == 0.041016, "six places, where four would round a four-cent close"


def test_no_daily_history_says_so(monkeypatch):
    monkeypatch.setattr(main, "YF_PROVIDER", _Feed(n=0))
    body = TestClient(main.app).get("/api/daily-bars/NOPE").json()
    assert body["available"] is False and body["reason"] == "No daily history for NOPE."


def test_the_weekly_bars_span_the_whole_history_only_when_asked(monkeypatch):
    feed = _Feed(n=300, freq="W-MON", start="1999-01-18")
    monkeypatch.setattr(main, "YF_PROVIDER", feed)
    client = TestClient(main.app)
    body = client.get("/api/weekly-bars/NVDA", params={"span": "max"}).json()
    assert feed.calls == [("NVDA", "max", "1wk")] and body["bars"] == 300
    client.get("/api/weekly-bars/NVDA", params={"span": "20y"})
    client.get("/api/weekly-bars/NVDA")
    assert feed.calls[1:] == [("NVDA", "10y", "1wk")] * 2, "ten years otherwise, as before"


def test_studies_over_the_whole_history_come_from_the_feed_its_bars_do(monkeypatch):
    """The brokerage feed is asked for a number of days, and reads `max` as a
    year: studies on it would have stopped a year back on a chart of decades."""
    yahoo, broker = _Feed(n=400), _Feed(n=400)
    monkeypatch.setattr(main, "YF_PROVIDER", yahoo)
    monkeypatch.setattr(main, "PROVIDER", broker)
    client = TestClient(main.app)
    client.get("/api/indicators/NVDA", params={"ids": "bollinger", "range": "max"})
    assert yahoo.calls == [("NVDA", "max", "1d")] and broker.calls == []
    client.get("/api/indicators/NVDA", params={"ids": "bollinger"})
    assert broker.calls == [("NVDA", "2y", "1d")], "every other range as it was"


def test_a_longer_history_changes_no_weeks_stage():
    """The stage reads every week since the listing now, so All is coloured
    all the way back. Each week is read from the 53 before it, so the weeks a
    ten-year read had keep their stage."""
    weeks = [date(2000, 1, 3) + timedelta(weeks=i) for i in range(900)]
    closes = [60 + 25 * math.sin(i / 23.0) + i * 0.08 for i in range(900)]
    whole = dict(stage.history(weeks, closes))
    recent = dict(stage.history(weeks[-520:], closes[-520:]))
    assert len(whole) == 900 - 52 and len(recent) == 520 - 52
    assert all(whole[w] == s for w, s in recent.items())
    assert {1, 2, 3, 4} <= set(recent.values()), "a series that passes through every stage"


# ------------------------------------------------------------------ client


_PAYLOAD = """
  var payload = { ticker: 'NVDA', technicals: { price_series: {
    dates: ['2026-09-29', '2026-09-30', '2026-10-01'], close: [229, 230, 231],
    open: [229, 230, 231], high: [229, 230, 231], low: [229, 230, 231], volume: [1, 1, 1] } } };
  var asked = [];
  getJSON = function (url) { asked.push(url); return new Promise(function () {}); };
  function sessions(n, from) {
    var out = { dates: [], open: [], high: [], low: [], close: [], volume: [] };
    for (var i = 0; i < n; i += 1) {
      out.dates.push(new Date(Date.UTC(1999, 0, 22) + i * 86400000 * (from || 1)).toISOString().slice(0, 10));
      var c = 1 + i * 0.1;
      out.open.push(c); out.high.push(c + 0.1); out.low.push(c - 0.05); out.close.push(c); out.volume.push(1000);
    }
    return out;
  }
"""


def test_all_draws_the_whole_history_once_it_is_here_and_no_other_range_does():
    out = _js(_PAYLOAD + """
      chartInterval = 'daily';
      chartRange = '1y';
      var ranged = allSeriesFor(payload, payload.technicals.price_series);
      chartRange = 'all';
      var waiting = allSeriesFor(payload, payload.technicals.price_series);
      allSeriesFor(payload, payload.technicals.price_series);
      allBars.daily = Object.assign({ symbol: 'NVDA', available: true }, sessions(300));
      var got = allSeriesFor(payload, payload.technicals.price_series);
      var full = wsFullSeries(payload);
      var swing = swingFullSeries(payload);
      // With the whole history in hand, 1Y still draws the payload's bars.
      chartRange = '1y';
      var heldOn1y = allSeriesFor(payload, payload.technicals.price_series);
      var full1y = wsFullSeries(payload).dates.length;
      chartRange = 'all';
      allBars.daily = Object.assign({ symbol: 'NVDA', available: true }, sessions(2));
      var shorter = allSeriesFor(payload, payload.technicals.price_series);
      print('RESULT:' + JSON.stringify({ ranged: ranged, waiting: waiting, asked: asked,
        bars: got.dates.length, first: got.dates[0], sma200: got.sma200.findIndex(function (v) { return v !== null; }),
        ema9: got.ema9.length, weekly: got.weekly, full: full.dates.length, swing: swing === got,
        heldOn1y: heldOn1y, full1y: full1y, shorter: shorter }));
    """)
    assert out["ranged"] is None, "1Y draws the payload's bars, as it did"
    assert out["heldOn1y"] is None and out["full1y"] == 3, "and goes on doing so once All has loaded"
    assert out["waiting"] is None and out["asked"] == ["/api/daily-bars/NVDA"], (
        "asked once, by All, with the payload standing in until it lands")
    assert out["bars"] == 300 and out["first"] == "1999-01-22"
    assert out["sma200"] == 199, "the 200-day average from 200 sessions after the listing"
    assert out["ema9"] == 300 and out["weekly"] is False
    assert out["full"] == 300 and out["swing"] is True, "both chart tabs"
    assert out["shorter"] is None, "never fewer bars than the stand-in"


def test_all_on_weekly_bars_asks_for_every_week():
    out = _js(_PAYLOAD + """
      chartRange = 'all'; chartInterval = 'weekly';
      allSeriesFor(payload, weeklySeriesFor(payload));
      allBars.weekly = Object.assign({ symbol: 'NVDA', available: true }, sessions(300, 7));
      var got = allSeriesFor(payload, weeklySeriesFor(payload));
      print('RESULT:' + JSON.stringify({ asked: asked, bars: got.dates.length, weekly: got.weekly,
        mondays: got.mondays, sma200: got.sma200.findIndex(function (v) { return v !== null; }) }));
    """)
    assert "/api/weekly-bars/NVDA?span=max" in out["asked"]
    assert out["bars"] == 300 and out["weekly"] is True and out["mondays"] is True
    assert out["sma200"] == 199


def test_the_panes_are_computed_over_the_whole_history():
    out = _js(_PAYLOAD + """
      chartRange = 'all'; chartInterval = 'daily'; wsPanesOpen = ['rsi', 'macd'];
      allBars.daily = Object.assign({ symbol: 'NVDA', available: true }, sessions(300));
      var full = wsFullSeries(payload);
      print('RESULT:' + JSON.stringify({ rsi: full.rsi.length, macd: full.macdHist.length,
        same: wsFullSeries(payload) === full }));
    """)
    assert out["rsi"] == 300 and out["macd"] == 300
    assert out["same"] is True, "kept between askings of the same bars"


def test_studies_on_all_are_asked_for_the_whole_history():
    out = _js("""
      var got = {};
      [['all', 'daily'], ['all', 'weekly'], ['1y', 'daily'], ['1y', 'weekly']].forEach(function (p) {
        chartRange = p[0]; chartInterval = p[1];
        got[p.join(' ')] = [studyBars(), studyQuery(studyBars())];
      });
      print('RESULT:' + JSON.stringify(got));
    """)
    assert out == {"all daily": ["daily-all", "&range=max"],
                   "all weekly": ["weekly-all", "&weekly=true&range=max"],
                   "1y daily": ["daily", ""],
                   "1y weekly": ["weekly", "&weekly=true&range=10y"]}


def test_the_bars_arriving_redraw_the_chart_waiting_for_them():
    out = _js(_PAYLOAD + """
      var calls = [];
      wsRedrawSettled = function () { calls.push('ws redraw'); };
      wsLoadIndicators = function () { calls.push('ws studies'); };
      swingRenderSettled = function () { calls.push('swing render'); };
      ltRedrawChart = function () { calls.push('lt redraw'); };
      STATE.view = 'chart'; STATE.chartData = payload; chartRange = 'all'; chartInterval = 'daily';
      indicatorIds = ['vwap']; wsWindow = { from: 1, to: 2 };
      allBarsArrived('NVDA', 'weekly');
      var other = calls.slice();
      allBarsArrived('NVDA', 'daily');
      var chart = { calls: calls.slice(), win: wsWindow };
      calls.length = 0;
      indicatorIds = [];
      allBarsArrived('NVDA', 'daily');
      var bare = calls.slice();
      calls.length = 0;
      STATE.view = 'long'; STATE.long = { holding: { ticker: 'NVDA' } }; ltRange = 'all';
      ltWindow = { from: 1, to: 2 };
      allBarsArrived('NVDA', 'weekly');
      print('RESULT:' + JSON.stringify({ other: other, chart: chart, bare: bare, long: calls, ltWindow: ltWindow }));
    """)
    assert out["other"] == [], "weekly bars do not redraw a daily chart"
    assert out["chart"] == {"calls": ["ws studies"], "win": None}, (
        "a window into the stand-in is dropped, and VWAP re-anchors at the listing; "
        "the studies' load is the redraw")
    assert out["bare"] == ["ws redraw"], "one redraw, not two"
    assert out["long"] == ["lt redraw"] and out["ltWindow"] is None


def test_the_investing_chart_reads_every_week_on_all_only():
    out = _js(_PAYLOAD + """
      STATE.long = { holding: { ticker: 'NVDA' } };
      var lt = { series: sessions(3, 7) };
      ltRange = '10y';
      var ten = ltSource(lt) === lt.series;
      ltRange = 'all';
      var waiting = ltSource(lt) === lt.series;
      allBars.weekly = Object.assign({ symbol: 'NVDA', available: true }, sessions(300, 7));
      var all = ltSource(lt) === allBars.weekly;
      var full = ltFullSeries(lt);
      print('RESULT:' + JSON.stringify({ ten: ten, waiting: waiting, all: all, asked: asked,
        bars: full.dates.length, ma200: full.ma[200].findIndex(function (v) { return v !== null; }) }));
    """)
    assert out["ten"] is True and out["waiting"] is True
    assert out["asked"] == ["/api/weekly-bars/NVDA?span=max"]
    assert out["all"] is True and out["bars"] == 300 and out["ma200"] == 199


def test_the_options_oscillators_follow_all():
    assert "const allNow = allSeriesFor(d, weeklyAll || t.price_series || {});" in APP
    assert ": allNow ? rsiSeries(allNow.close || [], 14)" in APP
    assert "macdSeries(ps.intraday ? (ps.close || []) : (allNow || weeklyAll).close)" in APP
    # The levels do not move with the range.
    assert "const srSource = srIntra || (weeklyAll || sliceSeries(" in APP


def test_the_vwap_anchor_is_the_listing_on_all():
    out = _js(_PAYLOAD + """
      chartRange = 'all'; chartInterval = 'daily';
      var before = vwapAnchorFor(payload);
      allBars.daily = Object.assign({ symbol: 'NVDA', available: true }, sessions(300));
      print('RESULT:' + JSON.stringify({ before: before, after: vwapAnchorFor(payload) }));
    """)
    assert out == {"before": "2026-09-29", "after": "1999-01-22"}


def test_week_mondays_are_kept_and_still_right():
    out = _js("""
      var a = weekMonday('2026-10-01'), b = weekMonday('2026-10-01T09:30:00-04:00'),
        c = weekMonday('2026-10-01'), bad = weekMonday('not a date'), sun = weekMonday('2026-10-04');
      print('RESULT:' + JSON.stringify([a, b, c, bad, sun, weekMonday.memo.size]));
    """)
    assert out[:5] == ["2026-09-28", "2026-09-28", "2026-09-28", None, "2026-09-28"]
    assert out[5] == 3, "one entry a date"


# ------------------------------------------------------------------ drawing


def test_long_daily_spans_get_yearly_dividers():
    out = _charts("""
      function days(n) { var o = []; for (var i = 0; i < n; i += 1) o.push(new Date(Date.UTC(1999, 0, 22) + i * 86400000).toISOString().slice(0, 10)); return o; }
      var two = days(730), many = days(365 * 27);
      print('RESULT:' + JSON.stringify({ two: periodDividers(two, two.length).grain,
        many: periodDividers(many, many.length).grain, marks: dividerMarks(many, many.length).length }));
    """)
    assert out["two"] == "month", "two years as before"
    assert out["many"] == "year" and out["marks"] == 27, "a line at each new year, 2000 to 2026"


def test_the_price_range_is_read_without_spreading_every_value():
    """Chrome 152 threw between 100,000 and 125,000 spread arguments, and IBM's
    All with ten lines on pools 162,960 values."""
    assert "Math.min(...all)" not in CHARTS and "Math.max(...all)" not in CHARTS
    out = _charts("""
      var big = []; for (var i = 0; i < 200000; i += 1) big.push(i === 150000 ? 1e6 : (i % 1000) - 500);
      var n = 2000, labels = [], series = [];
      for (var j = 0; j < n; j += 1) labels.push(new Date(Date.UTC(1999, 0, 22) + j * 86400000).toISOString().slice(0, 10));
      for (var q = 0; q < 10; q += 1) { var v = []; for (var k = 0; k < n; k += 1) v.push(100 + q + k * 0.01); series.push({ name: 'line ' + q, values: v }); }
      var svg = lineChart({ width: 900, height: 300, labels: labels, series: series });
      print('RESULT:' + JSON.stringify({ extent: extentOf(big), drew: svg.tag }));
    """)
    assert out["extent"] == [-500, 1000000]
    assert out["drew"] == "svg"


def test_more_bars_than_pixels_draw_a_mark_a_pixel():
    """Volume, the MACD histogram and candles each drew one mark a bar, 16,296
    on IBM's All in about 1,200 pixels. Past three bars to a pixel they draw
    one a pixel column, from the bars in it."""
    out = _charts("""
      var n = 3000, labels = [], close = [], open = [], high = [], low = [], vol = [];
      for (var i = 0; i < n; i += 1) {
        labels.push(new Date(Date.UTC(1999, 0, 22) + i * 86400000).toISOString().slice(0, 10));
        var c = 100 + Math.sin(i / 40) * 20; close.push(c); open.push(c - 0.5);
        // A spike and a dip on the first two bars of the first column, which
        // are not its last: the column has to keep its highest high and lowest low.
        high.push(i === 0 ? 200 : c + 1); low.push(i === 1 ? 0 : c - 1); vol.push(1000 + (i % 13) * 100);
      }
      NODES.length = 0;
      lineChart({ width: 600, height: 300, labels: labels, volume: vol,
        series: [{ name: 'Close', values: close }] });
      var volRects = NODES.filter(function (x) { return x.tag === 'rect' && x.attrs.opacity === '0.42'; }).length;
      NODES.length = 0;
      lineChart({ width: 600, height: 300, labels: labels, candles: { open: open, high: high, low: low, close: close },
        series: [{ name: 'Close', values: close, hidden: true }] });
      // A wick is a vertical line in a candle body's colour; the gridlines are vertical too.
      var bodyFills = {};
      NODES.forEach(function (x) { if (x.tag === 'rect' && x.attrs.fill && x.attrs.fill === x.attrs.stroke) bodyFills[x.attrs.fill] = true; });
      var wicks = NODES.filter(function (x) { return x.tag === 'line' && bodyFills[x.attrs.stroke] && x.attrs.x1 === x.attrs.x2; });
      var ys = wicks.map(function (w) { return [Number(w.attrs.y1), Number(w.attrs.y2)]; });
      var top = Math.min.apply(null, ys.map(function (y) { return Math.min(y[0], y[1]); }));
      var bottom = Math.max.apply(null, ys.map(function (y) { return Math.max(y[0], y[1]); }));
      NODES.length = 0;
      var hist = close.map(function (c, i) { return i % 2 ? 1 : -1; });
      macdChart(close, close, hist, labels, 600, {});
      var histRects = NODES.filter(function (x) { return x.tag === 'rect' && x.attrs.opacity === '0.5'; }).length;
      NODES.length = 0;
      lineChart({ width: 600, height: 300, labels: labels.slice(0, 300), volume: vol.slice(0, 300),
        series: [{ name: 'Close', values: close.slice(0, 300) }] });
      var fewRects = NODES.filter(function (x) { return x.tag === 'rect' && x.attrs.opacity === '0.42'; }).length;
      print('RESULT:' + JSON.stringify({ volRects: volRects, wicks: wicks.length, top: top, bottom: bottom, histRects: histRects, fewRects: fewRects }));
    """)
    assert 0 < out["volRects"] <= 600 and 0 < out["wicks"] <= 600
    # 200 and 0 are at about y 30 and 260 here; the next high and low in, 121
    # and 79, at about 100 and 158.
    assert out["top"] < 40 and out["bottom"] > 240, "the column's highest high and lowest low"
    assert 0 < out["histRects"] <= 1200, "a bar above zero and one below, a column"
    assert out["fewRects"] == 300, "one a bar where they fit, as before"


def test_the_crosshair_relights_two_volume_bars_not_all_of_them():
    hover = CHARTS[CHARTS.index("const lightVol = (i) => {"):]
    hover = hover[:hover.index("};") + 2]
    assert "if (i === volLit) return;" in hover
    assert "volBars.forEach((b, k)" not in CHARTS
    assert CHARTS.count("lightVol(i);") == 1 and CHARTS.count("lightVol(-1);") == 1
