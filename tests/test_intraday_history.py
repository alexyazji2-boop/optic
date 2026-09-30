"""A drag has somewhere to go on every bar size.

Reported as "the drag feature only works on the 1D chart. apply it to all time
frames". The 1D chart loads two years of bars and opens on the range chosen,
so a drag reaches the year behind it. Each size under a day loaded exactly the
window it opened on, so every bar was already on screen, and the pan, which
declines when there is nothing to move, declined every time.

Each size loads its `history` now, the longest window the server offers it,
and opens on its own window as before. The server says where that window
starts (`view_from`) and computes the levels, zones, Fibonacci grid, change and
VWAP over it, so nothing on screen moves until the chart is dragged.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import app.main as main

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _sessions(days, per_day=78, spike_before=None):
    """`days` sessions of 5m bars from 9:30. The sessions before the last
    `spike_before` carry a high of 1000, to show what the view leaves out."""
    stamps, highs, closes = [], [], []
    for n, day in enumerate(pd.bdate_range("2026-08-03", periods=days)):
        t0 = pd.Timestamp(day.date()).tz_localize("America/New_York") + pd.Timedelta(hours=9, minutes=30)
        early = spike_before is not None and n < days - spike_before
        for k in range(per_day):
            stamps.append(t0 + pd.Timedelta(minutes=5 * k))
            close = 100 + (k % 40) * 0.25
            closes.append(close)
            highs.append(1000.0 if early and k == 10 else close + 0.4)
    idx = pd.DatetimeIndex(stamps)
    return pd.DataFrame({"Open": [c - 0.05 for c in closes], "High": highs,
                         "Low": [c - 0.4 for c in closes], "Close": closes,
                         "Volume": [1000.0 + (i % 7) * 50 for i in range(len(idx))]}, index=idx)


class _Feed:
    def __init__(self, frame):
        self.frame, self.calls = frame, []

    def intraday_history(self, symbol, period="5d", interval="1m", prepost=False):
        self.calls.append((period, interval))
        return self.frame

    def history(self, symbol, period="2y", interval="1d"):
        return pd.DataFrame()


def _client(monkeypatch, feed):
    monkeypatch.setattr(main, "YF_PROVIDER", feed)
    monkeypatch.setattr(main, "PROVIDER", feed)
    return TestClient(main.app)


# ------------------------------------------------------------------ the ladder


def _ladder():
    block = APP[APP.index("const CHART_INTERVALS = ["):]
    block = block[:block.index("\n];")]
    return [ln for ln in block.splitlines() if "intraday: true" in ln]


def test_each_size_loads_the_longest_window_the_server_offers_it():
    rungs = _ladder()
    assert len(rungs) == 6
    for ln in rungs:
        key = re.search(r"key: '([^']+)'", ln).group(1)
        spec = main.INTRADAY_SPECS[key]
        assert re.search(r"history: '([^']+)'", ln).group(1) == spec["windows"][-1], key
        # And it still opens where it always did.
        assert re.search(r"period: '([^']+)'", ln).group(1) == spec["period"], key


def test_the_window_asked_for_is_the_history():
    fn = APP[APP.index("function intradayWindow(rung) {"):]
    assert "return (spec && (spec.history || spec.period)) || '';" in fn[:200]


# ---------------------------------------------------------- where the view starts


def _stamps(frame):
    return list(frame.index)


def test_a_count_of_days_is_a_count_of_sessions():
    stamps = _stamps(_sessions(10))
    assert main.intraday_view_start(stamps, "5d") == 5 * 78
    assert main.intraday_view_start(stamps, "1d") == 9 * 78
    # Fewer sessions than the window: all of it.
    assert main.intraday_view_start(_stamps(_sessions(3)), "5d") == 0


def test_months_and_years_are_calendar():
    idx = pd.date_range("2026-06-01 09:30", "2026-09-30 15:30", freq="1h", tz="America/New_York")
    stamps = list(idx)
    at = main.intraday_view_start(stamps, "1mo")
    assert stamps[at] >= stamps[-1] - pd.DateOffset(months=1) > stamps[at - 1]
    at = main.intraday_view_start(stamps, "3mo")
    assert stamps[at] >= stamps[-1] - pd.DateOffset(months=3) > stamps[at - 1]
    assert main.intraday_view_start(stamps, "1y") == 0


def test_no_window_or_no_bars_is_the_start():
    stamps = _stamps(_sessions(2))
    assert main.intraday_view_start(stamps, "") == 0
    assert main.intraday_view_start(stamps, "bogus") == 0
    assert main.intraday_view_start([], "5d") == 0


# ------------------------------------------------------------------ the payload


def test_a_longer_history_comes_back_with_the_view_marked(monkeypatch):
    feed = _Feed(_sessions(10))
    body = _client(monkeypatch, feed).get(
        "/api/intraday/PLTR", params={"range": "5", "window": "1mo"}).json()
    assert body["available"] is True and body["window"] == "1mo"
    assert feed.calls == [("1mo", "5m")]
    assert body["bars"] == 780 and len(body["closes"]) == 780
    assert body["view_from"] == 390


def test_the_levels_the_grid_and_the_change_are_the_views(monkeypatch):
    """A spike to 1000 a week before the view: a grid over the whole history
    would hang off it, and the chart opens on bars around 100."""
    frame = _sessions(10, spike_before=5)
    body = _client(monkeypatch, _Feed(frame)).get(
        "/api/intraday/PLTR", params={"range": "5", "window": "1mo"}).json()
    levels = [lv["price"] for lv in (body["fibonacci"] or {}).get("levels", [])]
    assert levels and max(levels) < 200, levels
    assert all(lv["price"] < 200 for lv in body["support_resistance"])
    assert body["first"] == body["closes"][390]


def test_the_sizes_own_window_alone_is_all_view(monkeypatch):
    """No window asked for, as the Options tab's 1D and 5D pills ask: the
    whole answer is the view, as it always was."""
    body = _client(monkeypatch, _Feed(_sessions(5))).get(
        "/api/intraday/PLTR", params={"range": "5d"}).json()
    assert body["view_from"] == 0 and body["first"] == body["closes"][0]


def test_vwap_starts_at_the_views_first_bar(monkeypatch):
    ind = _client(monkeypatch, _Feed(_sessions(10))).get(
        "/api/indicators/PLTR", params={"ids": "vwap", "intraday": "5", "window": "1mo"}).json()
    values = ind["indicators"]["vwap"]["lines"][0]["values"]
    assert len(values) == 780
    assert all(v is None for v in values[:390]) and values[390] is not None
    assert ind["dates"][390].startswith(str(pd.bdate_range("2026-08-03", periods=10)[5].date()))


# ------------------------------------------------------------ the chart opens on it


def _run(scenario):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    frame = _sessions(10)
    bars = {"times": [s.isoformat() for s in frame.index],
            "opens": frame["Open"].round(4).tolist(), "highs": frame["High"].round(4).tolist(),
            "lows": frame["Low"].round(4).tolist(), "closes": frame["Close"].round(4).tolist(),
            "volumes": frame["Volume"].tolist(), "bars": len(frame)}
    script = """
      load('tests/support/browser_stubs.js');
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      document.documentElement.style.removeProperty = function () {};
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
      var BARS = %s;
      STATE.view = 'chart'; STATE.chartSymbol = 'PLTR';
      STATE.chartData = { ticker: 'PLTR', technicals: { price_series: {} } };
      chartRange = '5'; chartMode = 'line'; wsWindow = null; chartSession = 'regular';
      function payload(extra) {
        var out = { symbol: 'PLTR', range: '5', window: intradayWindow('5'), session: 'regular',
                    available: true };
        Object.keys(BARS).forEach(function (k) { out[k] = BARS[k]; });
        Object.keys(extra || {}).forEach(function (k) { out[k] = extra[k]; });
        return out;
      }
      %s
    """ % (json.dumps(bars), scenario)
    out = subprocess.run([exe, "-e", script], capture_output=True, text=True,
                         timeout=120, cwd=str(ROOT))
    assert "RESULT:" in out.stdout, (out.stdout + out.stderr)[-2000:]
    return json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])


def test_the_chart_opens_on_the_sizes_window_with_the_rest_to_pan_to():
    got = _run("""
      wsIntraday = payload({ view_from: 390 });
      var shown = wsSeries(STATE.chartData);
      print('RESULT:' + JSON.stringify({ shown: shown.dates.length, first: shown.dates[0],
        win: wsWindowNow(STATE.chartData), pan: CHART_ZOOM.get('ws-chart').window() }));
    """)
    assert got["shown"] == 390 and got["first"] == _sessions(10).index[390].isoformat()
    assert got["win"] == {"from": 390, "to": 780, "total": 780}
    # The pan's own test: there is something to move.
    assert got["pan"]["to"] - got["pan"]["from"] < got["pan"]["total"]


def test_a_payload_with_no_view_opens_on_all_of_it():
    """A server from before `view_from`: everything, as then."""
    got = _run("""
      wsIntraday = payload({});
      print('RESULT:' + JSON.stringify({ win: wsWindowNow(STATE.chartData) }));
    """)
    assert got["win"] == {"from": 0, "to": 780, "total": 780}


def test_bars_for_the_other_session_are_not_drawn_for_this_one():
    got = _run("""
      wsIntraday = payload({ view_from: 390, session: 'extended' });
      var shown = wsSeries(STATE.chartData);
      print('RESULT:' + JSON.stringify({ shown: shown.dates.length, note: shown.note || '' }));
    """)
    assert got["shown"] == 0 and got["note"]
