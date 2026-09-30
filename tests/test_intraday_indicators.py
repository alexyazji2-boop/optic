"""Indicators on every chart size under a day.

Reported as: none of the indicators work for time frames under 1D. Every one
was switched off there, for one sound reason applied too widely: the only
series on hand were daily, and the charts line a study up with their bars by
counting back from the newest, so a daily line over five-minute candles puts
last spring on this morning. The fix computes each one on the intraday bars
themselves -- the averages, clouds and oscillators on the client, the way the
weekly chart already computes weekly ones, and the studies on the server from
the same frame /api/intraday draws -- and answers a study payload only for the
bars it was computed on.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import app.main as main

ROOT = Path(__file__).resolve().parent.parent


def _strip(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"^\s*//.*$", " ", text, flags=re.M)


APP = _strip((ROOT / "static/app.js").read_text())


def _fn(name: str) -> str:
    body = APP[APP.index("function " + name + "("):]
    return body[:body.index("\n}") + 2]


class _Feed:
    """Minute bars for any symbol, and a daily frame that must not be used."""

    def __init__(self, n=120):
        idx = pd.date_range("2026-09-25 09:30", periods=n, freq="5min", tz="America/New_York")
        close = pd.Series([100 + (i % 17) * 0.4 + i * 0.05 for i in range(n)], index=idx)
        self.frame = pd.DataFrame({"Open": close - 0.1, "High": close + 0.3,
                                   "Low": close - 0.3, "Close": close,
                                   "Volume": [1000.0 + i for i in range(n)]}, index=idx)
        self.intraday_calls, self.daily_calls = [], []

    def intraday_history(self, symbol, period="5d", interval="1m", prepost=False):
        self.intraday_calls.append((symbol, period, interval))
        return self.frame

    def history(self, symbol, period="2y", interval="1d"):
        self.daily_calls.append((symbol, period, interval))
        return pd.DataFrame()


def _get(monkeypatch, feed, **params):
    monkeypatch.setattr(main, "YF_PROVIDER", feed)
    monkeypatch.setattr(main, "PROVIDER", feed)
    return TestClient(main.app).get("/api/indicators/PLTR", params=params).json()


# ------------------------------------------------------------------ server


def test_studies_are_computed_on_the_intraday_bars(monkeypatch):
    feed = _Feed()
    body = _get(monkeypatch, feed, ids="bollinger,vwap,adx,rs", intraday="5")
    assert feed.daily_calls == [], "a daily frame was fetched for an intraday chart"
    assert ("PLTR", "5d", "5m") in feed.intraday_calls
    assert ("SPY", "5d", "5m") in feed.intraday_calls, "relative strength needs SPY on the same bars"
    for key in ("bollinger", "vwap", "adx", "rs"):
        v = body["indicators"][key]
        assert v["available"] is True, key
        assert all(len(line["values"]) == 120 for line in v["lines"]), key


def test_the_bars_are_stamped_with_times_not_dates(monkeypatch):
    """A pane's x-axis is minutes here; dates alone would label every bar of a
    session the same."""
    body = _get(monkeypatch, _Feed(), ids="adx", intraday="5")
    assert body["dates"][0] == "2026-09-25T09:30:00-04:00"
    assert body["intraday"] == "5" and body["interval"] == "5m"


def test_readings_written_in_sessions_are_dropped(monkeypatch):
    body = _get(monkeypatch, _Feed(), ids="rs,adx", intraday="5")
    assert all("reading" not in v for v in body["indicators"].values())


def test_vwap_ignores_a_date_anchor_on_minute_bars(monkeypatch):
    """A naive date compared against a timezone-aware minute index raises."""
    body = _get(monkeypatch, _Feed(), ids="vwap", intraday="5", anchor="2026-09-01")
    assert body["indicators"]["vwap"]["available"] is True


def test_an_unknown_intraday_key_says_so(monkeypatch):
    body = _get(monkeypatch, _Feed(), ids="adx", intraday="7")
    assert body["available"] is False and "Unknown intraday range" in body["reason"]


# ------------------------------------------------------------------ client


def test_the_intraday_series_carries_its_own_averages():
    fn = _fn("intradaySeries")
    for key, call in (("sma20", "smaSeries(close, 20)"), ("sma50", "smaSeries(close, 50)"),
                      ("sma200", "smaSeries(close, 200)"), ("ema9", "emaSeries(close, 9)"),
                      ("ema21", "emaSeries(close, 21)"), ("ema50", "emaSeries(close, 50)")):
        assert "%s: %s," % (key, call) in fn, key


def test_both_charts_draw_the_averages_on_intraday():
    ws = _fn("wsMountChart")
    assert "...(intraday ? [] : [\n          ['sma20'" not in ws
    assert "['sma20', maLabel('sma20', ps), ps.sma20]," in ws
    swing = _fn("swingPriceBlock")
    assert "...(ps.intraday ? [] : [\n          ['sma20'" not in swing
    assert "...(ps.intraday ? [] : indicatorOverlaySeries(" not in swing
    assert "...indicatorOverlaySeries((ps.dates || []).length, overlayPalette)," in swing


def test_an_average_under_a_day_is_named_in_bars():
    assert "if (ps && ps.intraday) return 'bar';" in _fn("barUnit")
    assert "const unit = barUnit(ps);" in _fn("maLabel")


def test_the_panes_recompute_on_intraday_bars():
    series = _fn("wsSeries")
    assert "const full = wsWithOscillators(intra, null, true);" in series
    assert "const unit = barUnit(ps);" in _fn("wsMountPanes")


def test_both_tabs_key_their_studies_to_the_bars():
    bars = _fn("studyBars")
    assert "if (isIntradayRange(chartRange)) return intradayBarsKey();" in bars
    assert "return chartInterval === 'weekly' ? 'weekly' : 'daily';" in bars
    query = _fn("studyQuery")
    assert "if (bars === 'weekly') return '&weekly=true&range=10y';" in query
    assert "return '&' + intradayQuery(bars);" in query
    ws = _fn("wsLoadIndicators")
    assert "&& wsIndicators.bars === bars && !wsIndicators.loading" in ws
    # And on the VWAP anchor, after the bars: see test_vwap_anchor.
    assert "+ studyQuery(bars)\n      + vwapAnchorQuery(ids, STATE.chartData));" in ws
    swing = _fn("loadIndicators")
    assert "const key = `${STATE.ticker}|${indicatorIds.join(',')}|${bars}${anchor}`;" in swing
    assert "+ studyQuery(bars) + anchor);" in swing
    assert "return data && data.bars === studyBars() ? data : null;" in _fn("swingStudies")
    for name in ("indicatorOverlaySeries", "indicatorOverlayLegend", "renderIndicatorPanes",
                 "drawIndicatorCharts"):
        assert "swingStudies()" in _fn(name), name
        assert "STATE.indicators" not in _fn(name), name


def test_a_size_change_asks_for_studies_on_the_new_bars():
    """Otherwise the old payload is held, refused by the bars check, and the
    studies simply vanish until the page reloads."""
    handler = APP[APP.index("const wsRange = evt.target.closest('[data-ws-range]');"):]
    assert "if (wsPriceIndicatorIds().length) wsLoadIndicators();" in handler[:handler.index("return;\n  }")]
    handler = APP[APP.index("const wsInt = evt.target.closest('[data-ws-interval]');"):]
    handler = handler[:handler.index("const wsTl =")]
    assert "if (wsPriceIndicatorIds().length) wsLoadIndicators();" in handler
    handler = APP[APP.index("const tf = evt.target.closest('[data-chart-range]');"):]
    assert "loadIndicators();" in handler[:handler.index("const ltTf =")]


def test_the_menus_offer_them_under_a_day():
    studies = _fn("wsStudiesMenu")
    assert "${intraday ? 'disabled' : ''}" not in studies
    assert "Computed on these bars." in studies
    assert "${ps.intraday && overlay ? 'disabled' : ''}" not in APP


def test_the_options_momentum_panels_use_the_bars_on_screen():
    assert "const rsiSource = ps.intraday ? rsiSeries(ps.close || [], 14)" in APP
    assert "const m = macdSeries(ps.intraday ? (ps.close || []) : weeklyAll.close);" in APP
    # The branch has to be taken on intraday, not merely contain the call: a
    # mutation that routed intraday back to the daily series left it in place.
    assert "const full = (ps.weekly || ps.intraday)" in APP
    assert "macdCrossSentence(cross, wk, macdDates, barUnit(ps), zoom)" in APP


def test_the_status_line_carries_no_intraday_exception_any_more():
    """It said daily overlays did not apply, then that daily levels and
    drawings did not. Both are on every bar size now, so the line is the same
    on every one."""
    assert "'Daily overlays and drawings do not apply to these bars'" not in APP
    assert "Daily levels and drawings are not" not in APP
    assert "'drawings hidden on intraday'" not in APP


def test_the_macd_axis_uses_the_calendar_ticks_every_other_chart_does():
    """It printed three raw labels, and on minute bars that wrote
    "2026-09-21T09:30:00-04:00" under the pane."""
    charts = _strip((ROOT / "static/charts.js").read_text())
    fn = charts[charts.index("function macdChart("):]
    fn = fn[:fn.index("\n}") + 2]
    assert "const ticks = timeTicks(labels, X, 46);" in fn


def test_an_average_with_no_line_says_why_instead_of_being_keyed():
    """A 200-bar SMA on a one-day chart of 78 five-minute bars has no value
    anywhere. The Options key listed it as if it were drawn."""
    fn = _fn("maShortOf")
    assert "arr.some((v) => Number.isFinite(v))" in fn
    assert "`needs ${length} bars`" in fn
    swing = _fn("swingPriceBlock")
    assert swing.count("maLabel(id, ps) + (maShortOf(id, ps) ? ` (${maShortOf(id, ps)})` : '')") == 2
    leg = _fn("wsLegend")
    assert "add('sma200', ps.sma200, maShortOf('sma200', ps) || maDetail('sma200'));" in leg
    assert "add('ema50', ps.ema50, maShortOf('ema50', ps) || null);" in leg
