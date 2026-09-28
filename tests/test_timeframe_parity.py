"""Every feature on the 1D chart, on every other bar size too.

Asked for as: all the features on the 1D time frame should be on the other time
frames as well. Under a day, support and resistance, supply and demand, trend
lines, accumulation zones, insider trades, earnings dates, stage colours and the
drawing tools were all off, each for the same sound-sounding reason: the only
copy was daily. On weekly bars the studies were daily ones lined up from the
newest bar, so a two-year weekly chart carried five months of a daily band.

Each now comes from the bars on screen: the server computes levels, zones and
trend lines on the intraday frame with the same functions it uses on daily
bars, and studies on weekly bars for a weekly chart.
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


def _minute_frame(n=240):
    idx = pd.date_range("2026-09-21 09:30", periods=n, freq="5min", tz="America/New_York")
    # A swing with shelves to find: up, back, up again.
    base = [100 + (i % 40) * 0.25 if (i // 40) % 2 == 0 else 110 - (i % 40) * 0.25
            for i in range(n)]
    close = pd.Series(base, index=idx)
    return pd.DataFrame({"Open": close - 0.05, "High": close + 0.4, "Low": close - 0.4,
                         "Close": close, "Volume": [1000.0 + (i % 7) * 50 for i in range(n)]},
                        index=idx)


class _Feed:
    def __init__(self, frame=None):
        self.frame = _minute_frame() if frame is None else frame
        self.intraday_calls, self.daily_calls = [], []

    def intraday_history(self, symbol, period="5d", interval="1m"):
        self.intraday_calls.append((symbol, period, interval))
        return self.frame

    def history(self, symbol, period="2y", interval="1d"):
        self.daily_calls.append((symbol, period, interval))
        idx = pd.date_range("2024-09-30", periods=104, freq="W-MON", tz="America/New_York")
        close = pd.Series([100 + i * 0.5 for i in range(104)], index=idx)
        return pd.DataFrame({"Open": close, "High": close + 1, "Low": close - 1,
                             "Close": close, "Volume": [1e6] * 104}, index=idx)


def _client(monkeypatch, feed):
    monkeypatch.setattr(main, "YF_PROVIDER", feed)
    monkeypatch.setattr(main, "PROVIDER", feed)
    return TestClient(main.app)


# ------------------------------------------------------------------ server


def test_the_intraday_payload_carries_levels_band_width_and_zones(monkeypatch):
    body = _client(monkeypatch, _Feed()).get("/api/intraday/PLTR", params={"range": "5"}).json()
    assert isinstance(body["support_resistance"], list) and body["support_resistance"]
    assert all("price" in lv for lv in body["support_resistance"])
    assert isinstance(body["atr14"], float) and body["atr14"] > 0
    assert isinstance(body["patterns"], dict) and "zones" in body["patterns"]


def test_a_failed_level_costs_the_levels_not_the_chart(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("no")
    monkeypatch.setattr(main.technicals, "support_resistance_levels", boom)
    body = _client(monkeypatch, _Feed()).get("/api/intraday/PLTR", params={"range": "5"}).json()
    assert body["available"] is True and body["bars"] == 240
    assert body["support_resistance"] == []


def test_trend_lines_can_be_fitted_to_intraday_bars(monkeypatch):
    feed = _Feed()
    body = _client(monkeypatch, feed).get("/api/trendlines/PLTR", params={"intraday": "5"}).json()
    assert ("PLTR", "5d", "5m") in feed.intraday_calls and feed.daily_calls == []
    assert body["intraday"] == "5"
    assert body["dates"][0] == "2026-09-21T09:30:00-04:00", "times, so each line anchors on its bar"


def test_an_unknown_intraday_key_for_trend_lines_says_so(monkeypatch):
    body = _client(monkeypatch, _Feed()).get("/api/trendlines/PLTR", params={"intraday": "7"}).json()
    assert body["available"] is False


def test_a_weekly_chart_gets_studies_computed_on_weekly_bars(monkeypatch):
    feed = _Feed()
    body = _client(monkeypatch, feed).get(
        "/api/indicators/PLTR", params={"ids": "bollinger", "weekly": "true"}).json()
    assert ("PLTR", "2y", "1wk") in feed.daily_calls
    assert body["interval"] == "1wk"
    assert len(body["dates"]) == 104


# ------------------------------------------------------------------ client


def test_the_intraday_series_carries_them():
    fn = _fn("intradaySeries")
    assert "sr: intra.support_resistance || []," in fn
    assert "atr: intra.atr14," in fn
    assert "patterns: intra.patterns || null," in fn


def test_the_charting_tab_draws_every_family_on_every_size():
    ws = _fn("wsMountChart")
    assert "bands: intraday ? [] :" not in ws
    assert "srBands(ps.sr || [], ps.atr, ps.spot)" in ws
    assert "zoneBands(intraday ? (ps.patterns || {}) : (d.patterns || {}))" in ws
    assert ("segments: !showTrends ? []\n        : trendSegments(trendlinesFor(d.ticker), ps.dates || [], "
            "{ mondays: !!ps.mondays })," in ws)
    assert "events: showInsiders\n" in ws
    assert "!intraday" not in ws


def test_the_options_tab_draws_every_family_on_every_size():
    swing = _fn("swingPriceBlock")
    assert "ps.intraday ? [] :" not in swing
    assert "!ps.intraday" not in swing
    assert "srBands(srLevels, ps.intraday ? ps.atr : (t.volatility || {}).atr14," in swing
    assert "zoneBands(ps.intraday ? (ps.patterns || {}) : d.patterns)" in swing
    assert "trendSegments(trendlinesFor(d.ticker), ps.dates || [], { mondays: !!ps.mondays })" in swing


def test_the_options_levels_come_from_the_bars_on_screen():
    render = _fn("renderSwing")
    assert "const srSource = srIntra || (weeklyAll || sliceSeries(" in render
    assert "const srUnit = srIntra ? ' bars' :" in render


def test_trend_lines_answer_only_for_their_own_symbol_and_bars():
    fn = _fn("trendlinesFor")
    assert "if (tl.symbol !== symbol || tl.bars !== trendBars()) return null;" in fn
    load = _fn("loadTrendlines")
    assert "const key = `${sym}|${bars}`;" in load
    assert "if (STATE.trendlinesFor !== key) return;" in load, "a late reply for another size"
    assert "`?${intradayQuery(bars)}`" in load


def test_the_options_tab_loads_its_own_trend_lines():
    """It drew whatever the Charting tab had last loaded, another symbol's
    lines included."""
    assert "if (showTrends) loadTrendlines(STATE.ticker);" in _fn("loadSwing")
    assert "trendSegments(STATE.trendlines," not in APP


def test_a_size_change_refetches_the_trend_lines():
    for anchor, stop in (("const wsRange = evt.target.closest('[data-ws-range]');", "return;\n  }"),
                         ("const tf = evt.target.closest('[data-chart-range]');", "const ltTf =")):
        block = APP[APP.index(anchor):]
        assert "if (showTrends) loadTrendlines(" in block[:block.index(stop)], anchor
    block = APP[APP.index("const wsInt = evt.target.closest('[data-ws-interval]');"):]
    assert "if (showTrends) loadTrendlines(STATE.chartSymbol);" in block[:block.index("const wsTl =")]


def test_earnings_dates_and_the_colour_seed_have_no_intraday_exclusion():
    assert "if (!dates.length) return [];" in _fn("earningsMarkers")
    assert "ps.intraday" not in _fn("earningsMarkers")
    assert "intraday)" not in _fn("chartBaseColors").replace("chartBaseColors(ps, candleMode, intraday", "")


def test_weekly_bars_have_their_own_studies():
    assert "return chartInterval === 'weekly' ? 'weekly' : 'daily';" in _fn("studyBars")
    handler = APP[APP.index("if (evt.target.id === 'chart-interval') {"):]
    assert "loadIndicators();" in handler[:handler.index("} else {")]


def test_stages_and_drawings_work_on_every_size():
    assert "if (!wsOverlayDrawn('stages') || !symbol) return null;" in _fn("stageTints")
    assert "`${sym}@${intradayBarsKey()}`" in _fn("wsDrawKey")


# ------------------------------------------------------------ weekly history


def test_the_weekly_endpoint_sends_ten_years_of_monday_labelled_bars(monkeypatch):
    feed = _Feed()
    body = _client(monkeypatch, feed).get("/api/weekly-bars/PLTR").json()
    assert ("PLTR", "10y", "1wk") in feed.daily_calls
    assert body["available"] is True and body["bars"] == 104
    assert body["dates"][0] == "2024-09-30", "the week's Monday"
    assert len(body["open"]) == len(body["close"]) == 104


def test_1w_uses_the_weekly_bars_once_they_are_here():
    """A 200-week average needs 200 weeks; the roll-up of two years of daily
    bars had 105, so SMA 200 could never draw on 1W."""
    fn = _fn("weeklySeriesFor")
    assert "if (sym && (!w || w.symbol !== sym)) loadWeeklyBars(sym);" in fn
    assert "return aggregateWeekly(((d && d.technicals) || {}).price_series || {});" in fn
    bars = _fn("weeklyFromBars")
    assert "sma200: smaSeries(close, 200)," in bars
    for name in ("wsFullSeries", "swingFullSeries"):
        assert "weeklySeriesFor(d)" in _fn(name), name
    assert "const weeklyAll = chartInterval === 'weekly' ? weeklySeriesFor(d) : null;" in _fn("renderSwing")


def test_a_late_weekly_answer_for_another_symbol_is_dropped():
    fn = _fn("loadWeeklyBars")
    assert "if (!weeklyBars || weeklyBars.symbol !== symbol) return;" in fn
    assert "wsWindow = null;" in fn, "a window into the stand-in is not a window into these bars"


def test_daily_trend_anchors_find_their_own_monday():
    fn = _fn("trendSegments")
    assert "const target = mondays ? (weekMonday(anchor) || anchor) : anchor;" in fn


def test_no_client_function_is_declared_twice():
    """Function declarations hoist, and the later of two with one name replaces
    the earlier without a word. The weekly-bars loader was first written as
    loadWeekly, which the Weekly update panel already had eleven thousand lines
    further down: the chart called the panel's loader, fetched the panel, and
    the 1W chart stayed on its 105-week stand-in with nothing in the console."""
    import collections
    names = []
    for path in ("static/app.js", "static/charts.js"):
        names += re.findall(r"^(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(",
                            (ROOT / path).read_text(), re.M)
    dup = [n for n, c in collections.Counter(names).items() if c > 1]
    assert not dup, dup


# ------------------------------------------------------------ intraday windows


def _client_windows():
    block = APP[APP.index("const INTRADAY_WINDOWS = {"):]
    block = block[:block.index("\n};")]
    out = {}
    for rung, body in re.findall(r"^\s*(\d+): \[(.*?)\],?$", block, re.M | re.S):
        out[rung] = re.findall(r"key: '([^']+)'", body)
    return out


def test_the_browser_and_the_server_offer_the_same_windows():
    """The server refuses a window a size does not offer, so a pill the server
    would refuse is a dead control."""
    server = {k: v["windows"] for k, v in main.INTRADAY_SPECS.items() if "windows" in v}
    assert _client_windows() == server


def test_each_size_opens_on_its_old_window():
    """So nothing changes for a reader who never presses a window pill."""
    for key, spec in main.INTRADAY_SPECS.items():
        if "windows" in spec:
            assert spec["period"] in spec["windows"], key
            assert "{ key: '%s'," % key in APP and "period: '%s' }" % spec["period"] in APP


def test_a_window_the_size_does_not_offer_is_refused(monkeypatch):
    client = _client(monkeypatch, _Feed())
    ok = client.get("/api/intraday/PLTR", params={"range": "5", "window": "1mo"}).json()
    assert ok["available"] is True and ok["window"] == "1mo"
    bad = client.get("/api/intraday/PLTR", params={"range": "5", "window": "2y"}).json()
    assert bad["available"] is False and "5m bars are offered over 1d, 5d, 1mo" in bad["reason"]
    assert main.intraday_spec("5", "")["period"] == "5d"
    assert main.intraday_spec("5", "1mo")["period"] == "1mo"
    assert main.intraday_spec("5", "2y") is None and main.intraday_spec("7", "") is None


def test_studies_and_trend_lines_are_computed_on_the_same_window(monkeypatch):
    feed = _Feed()
    client = _client(monkeypatch, feed)
    client.get("/api/indicators/PLTR", params={"ids": "adx", "intraday": "5", "window": "1mo"})
    client.get("/api/trendlines/PLTR", params={"intraday": "5", "window": "1mo"})
    assert feed.intraday_calls.count(("PLTR", "1mo", "5m")) == 2


def test_the_toolbar_offers_the_windows_and_they_have_a_handler():
    tb = _fn("wsToolbar")
    # The branch has to be taken, not merely exist: `${false ?` left the call
    # in place and the fixed pill on screen.
    cond = "${isIntradayRange(chartRange) && (INTRADAY_WINDOWS[chartRange] || []).length\n"
    call = "? rangePills(INTRADAY_WINDOWS[chartRange], intradayWindow(chartRange),\n      'data-ws-iwin', 'Window')"
    assert cond in tb and call in tb
    assert tb.index(cond) < tb.index(call) < tb.index(cond) + 400
    handler = APP[APP.index("const wsIwin = evt.target.closest('[data-ws-iwin]');"):]
    handler = handler[:handler.index("return;\n  }")]
    for part in ("setIntradayWindow(chartRange, wsIwin.dataset.wsIwin);", "wsWindow = null;",
                 "wsLoadIntraday();", "wsLoadIndicators();", "loadTrendlines(STATE.chartSymbol);"):
        assert part in handler, part


def test_everything_computed_on_the_bars_keys_on_the_window():
    """Drawings, studies and trend lines made on the default window keep the
    bare size as their key, so nothing made before windows existed moves."""
    key = _fn("intradayBarsKey")
    assert "return !spec || !spec.period || win === spec.period ? r : `${r}~${win}`;" in key
    load = _fn("wsLoadIntraday")
    assert "&& wsIntraday.window === win && !wsIntraday.loading" in load
    assert "+ (win ? '&window=' + encodeURIComponent(win) : ''));" in load, "the request has to ask for it"
    assert "intradayWindow(range) !== win) return;" in load, "a late reply for another window"
