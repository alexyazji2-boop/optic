"""Regular trading hours or extended hours, on the charts under a day.

Asked for as: "have a button to show whether the not the user wants to include
after hours price movement as well on the charts. have a dropdown, one for
"regular trading hours" and one for "extended hours"".

Every intraday chart was the regular session only, deliberately: pre- and
post-market prints trade on thin books. They are the reader's choice now, and
the regular session stays the default. The choice is a menu beside the bar
size. The server asks the feed for the extended session, and marks every bar
outside the regular one, so the chart can shade it. It marks nothing for a
symbol with no pre- or post-market, such as a future or a coin, where the
choice changes nothing. Daily and weekly bars are the regular session's, as
the feed builds them, so there the menu is disabled and says so.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.providers import yf as yf_mod

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _extended_day(day="2026-09-29", has_prepost=True):
    """One session of 5m bars from 4:00 to 19:55, as the feed sends them with
    extended hours: 66 before the open, 78 in the session, 48 after it."""
    t0 = pd.Timestamp(day).tz_localize("America/New_York") + pd.Timedelta(hours=4)
    idx = pd.DatetimeIndex([t0 + pd.Timedelta(minutes=5 * k) for k in range(192)])
    close = pd.Series([100 + (k % 30) * 0.1 for k in range(192)], index=idx)
    frame = pd.DataFrame({"Open": close - 0.05, "High": close + 0.2, "Low": close - 0.2,
                          "Close": close, "Volume": 500.0}, index=idx)
    frame.attrs.update({"has_prepost": has_prepost, "regular_minutes": (570, 960)})
    return frame


class _Feed:
    def __init__(self, frame):
        self.frame, self.sessions = frame, []

    def intraday_history(self, symbol, period="5d", interval="1m", prepost=False):
        self.sessions.append(prepost)
        return self.frame

    def history(self, symbol, period="2y", interval="1d"):
        return pd.DataFrame()


def _client(monkeypatch, feed):
    monkeypatch.setattr(main, "YF_PROVIDER", feed)
    monkeypatch.setattr(main, "PROVIDER", feed)
    return TestClient(main.app)


# ------------------------------------------------------------------ the server


def test_the_spec_carries_the_session():
    assert main.intraday_spec("5", "", "extended")["prepost"] is True
    assert main.intraday_spec("5", "1mo", "EXTENDED")["prepost"] is True
    for session in ("", "regular", "anything else"):
        assert main.intraday_spec("5", "", session)["prepost"] is False, session
    assert main.intraday_spec("7", "", "extended") is None


def test_the_feed_is_asked_for_it_for_the_bars_the_studies_and_the_trend_lines(monkeypatch):
    feed = _Feed(_extended_day())
    client = _client(monkeypatch, feed)
    ext = {"session": "extended"}
    client.get("/api/intraday/PLTR", params={"range": "5", **ext})
    client.get("/api/indicators/PLTR", params={"ids": "adx", "intraday": "5", **ext})
    client.get("/api/trendlines/PLTR", params={"intraday": "5", **ext})
    assert feed.sessions == [True, True, True]
    client.get("/api/intraday/PLTR", params={"range": "5"})
    client.get("/api/indicators/PLTR", params={"ids": "adx", "intraday": "5"})
    client.get("/api/trendlines/PLTR", params={"intraday": "5"})
    assert feed.sessions[3:] == [False, False, False]


def test_each_bar_outside_the_regular_session_is_marked(monkeypatch):
    body = _client(monkeypatch, _Feed(_extended_day())).get(
        "/api/intraday/PLTR", params={"range": "5", "session": "extended"}).json()
    assert body["session"] == "extended"
    flags, times = body["extended"], body["times"]
    assert len(flags) == len(times) == 192
    # 4:00 to 9:25 before, 16:00 to 19:55 after, 9:30 to 15:55 in between.
    assert flags[:66] == [True] * 66 and flags[66:144] == [False] * 78 and flags[144:] == [True] * 48
    assert times[66].endswith("09:30:00-04:00") and times[144].endswith("16:00:00-04:00")
    assert "shaded apart from the regular session" in body["session_note"]


def test_nothing_is_marked_where_there_is_no_pre_or_post_market(monkeypatch):
    """A future or a coin: the feed says it has no pre- or post-market, and
    every bar it sends is the session's."""
    body = _client(monkeypatch, _Feed(_extended_day(has_prepost=False))).get(
        "/api/intraday/ES=F", params={"range": "5", "session": "extended"}).json()
    assert body["session"] == "extended" and body["extended"] == []
    assert "no pre- or post-market session" in body["session_note"]


def test_regular_hours_mark_nothing_and_say_so(monkeypatch):
    body = _client(monkeypatch, _Feed(_extended_day())).get(
        "/api/intraday/PLTR", params={"range": "5"}).json()
    assert body["session"] == "regular" and body["extended"] == []
    assert body["session_note"].startswith("Regular session bars only")


# ----------------------------------------------------------------- the feed


def _meta(start="09:30", end="16:00", has=True, zone="America/New_York"):
    def epoch(hhmm):
        return int(pd.Timestamp("2026-09-29 " + hhmm).tz_localize(zone).timestamp())
    return {"hasPrePostMarketData": has, "exchangeTimezoneName": zone,
            "currentTradingPeriod": {"regular": {"start": epoch(start), "end": epoch(end)}}}


def test_the_session_hours_come_from_the_feeds_own_metadata():
    assert yf_mod._session_hours(_meta()) == {"has_prepost": True, "regular_minutes": (570, 960)}
    # A half day closes at one.
    assert yf_mod._session_hours(_meta(end="13:00"))["regular_minutes"] == (570, 780)
    assert yf_mod._session_hours(_meta(has=False))["has_prepost"] is False
    # Nothing to go on: the US session, and nothing marked.
    assert yf_mod._session_hours({}) == {"has_prepost": False, "regular_minutes": (570, 960)}


def test_the_two_sessions_are_cached_apart(monkeypatch):
    asked = []

    class _Ticker:
        def __init__(self, sym):
            self.history_metadata = _meta()

        def history(self, period, interval, auto_adjust, prepost):
            asked.append(prepost)
            frame = _extended_day() if prepost else _extended_day().iloc[66:144].copy()
            frame.attrs = {}               # the feed's frame carries none of its own
            return frame

    monkeypatch.setattr(yf_mod.yf, "Ticker", _Ticker)
    provider = yf_mod.YFinanceProvider()
    regular = provider.intraday_history("ZZSESSION", period="5d", interval="5m")
    extended = provider.intraday_history("ZZSESSION", period="5d", interval="5m", prepost=True)
    assert asked == [False, True]
    assert len(regular) == 78 and len(extended) == 192
    assert extended.attrs["has_prepost"] is True and "has_prepost" not in regular.attrs


# ------------------------------------------------------------------ the client


def _app(scenario):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    script = """
      load('tests/support/browser_stubs.js');
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      document.documentElement.style.removeProperty = function () {};
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
      %s
    """ % scenario
    out = subprocess.run([exe, "-e", script], capture_output=True, text=True,
                         timeout=120, cwd=str(ROOT))
    assert "RESULT:" in out.stdout, (out.stdout + out.stderr)[-2000:]
    return json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])


def test_the_dropdown_offers_the_two_choices_asked_for():
    got = _app("""
      chartRange = '5'; chartSession = 'regular'; wsMenuOpen = 'session';
      var open = wsSessionMenu();
      chartSession = 'extended'; wsMenuOpen = null;
      var ext = wsSessionMenu();
      print('RESULT:' + JSON.stringify({ open: open, ext: ext }));
    """)
    assert 'data-ws-menu="session"' in got["open"] and ">Regular hours<" in got["open"]
    for key, label in (("regular", "Regular trading hours"), ("extended", "Extended hours")):
        assert 'data-ws-session="%s"' % key in got["open"] and ">%s</button>" % label in got["open"]
    assert 'class="pill on"\n      data-ws-session="regular" aria-pressed="true"' in got["open"]
    # The button names the session on screen, and lights when it is extended.
    assert ">Extended hours<" in got["ext"] and 'class="ws-menu-btn on"' in got["ext"]
    assert "disabled" not in got["ext"]


def test_daily_and_weekly_bars_say_they_are_the_regular_session():
    """Disabled rather than hidden, as Candles is where it cannot apply, and
    honest about what is on screen whatever was chosen for the sizes under a
    day."""
    got = _app("""
      chartRange = '6m'; chartSession = 'extended'; wsMenuOpen = 'session';
      print('RESULT:' + JSON.stringify({ html: wsSessionMenu(), kept: chartSession }));
    """)
    assert " disabled " in got["html"] and ">Regular hours<" in got["html"]
    assert "Daily and weekly bars are the regular session." in got["html"]
    assert "data-ws-session" not in got["html"], "no menu opens on a disabled button"
    assert got["kept"] == "extended"


def test_extended_bars_have_their_own_key_and_ask_for_their_session():
    """Drawings are a bar index and a price, and extended hours put other bars
    at those indices, so they keep their own drawings, studies and trend lines."""
    got = _app("""
      chartRange = '5';
      chartSession = 'regular'; var regular = intradayBarsKey();
      chartSession = 'extended'; var extended = intradayBarsKey();
      print('RESULT:' + JSON.stringify({ regular: regular, extended: extended,
        q: [intradayQuery(regular), intradayQuery(extended), intradayQuery('1d')] }));
    """)
    assert got["regular"] == "5~1mo" and got["extended"] == "5~1mo~ext"
    assert got["q"] == ["intraday=5&window=1mo", "intraday=5&window=1mo&session=extended",
                        "intraday=1d"]


def test_the_choice_is_kept_and_reloads_everything_computed_on_the_bars():
    at = APP.index("const wsSess = evt.target.closest('[data-ws-session]');")
    handler = APP[at:APP.index("const wsInt = evt.target.closest('[data-ws-interval]');", at)]
    assert "localStorage.setItem(CHART_SESSION_KEY, chartSession);" in handler
    assert "wsWindow = null;" in handler
    for call in ("wsLoadIntraday();", "wsLoadIndicators();", "loadTrendlines(STATE.chartSymbol);"):
        assert call in handler, call
    assert "localStorage.getItem(CHART_SESSION_KEY) === 'extended'" in APP
    load = APP[APP.index("async function wsLoadIntraday() {"):]
    assert "+ (session === 'extended' ? '&session=extended' : ''));" in load[:1600]


def test_the_chart_is_given_the_flags_only_when_there_are_any():
    assert "offHours: intraday && (ps.extended || []).some(Boolean) ? ps.extended : null," in APP
    series = APP[APP.index("function intradaySeries(intra) {"):]
    assert "extended: Array.isArray(intra.extended) ? intra.extended : []," in series[:1600]


# ------------------------------------------------------------------ the shading


def _shade(off_hours, bars=None):
    """Draw `bars` bars (as many as there are flags, by default) with the
    flags given, and read back the bands."""
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    n = bars or len(off_hours or [0, 0])
    src = ((ROOT / "tests/support/recording_dom.js").read_text()
           + (ROOT / "static/charts.js").read_text() + """
      var off = %s, n = %d, labels = [], values = [];
      for (var i = 0; i < n; i++) { labels.push('t' + i); values.push(100 + i); }
      var svg = lineChart({ width: 600, height: 300, labels: labels,
        series: [{ name: 'Close', values: values, color: '#123' }], offHours: off });
      var g = NODES.filter(function (n) { return n.tag === 'g' && n.attrs['class'] === 'off-hours'; });
      var f = svg.chartFrame;
      print(JSON.stringify({ groups: g.length, rects: g.length ? g[0].children.map(function (r) {
        return [Number(r.attrs.x), Number(r.attrs.x) + Number(r.attrs.width)]; }) : [],
        left: f.margin.l, plotW: f.plotW }));
    """ % (json.dumps(off_hours), n))
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=30)
    last = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else ""
    assert last.startswith("{"), out.stdout + out.stderr
    return json.loads(last)


def test_each_run_of_extended_bars_is_one_band_reaching_halfway_to_its_neighbours():
    got = _shade([True, True, False, False, False, True, True, True])
    left, width = got["left"], got["plotW"]
    half = width / 7 / 2
    x = lambda i: left + i * width / 7
    assert len(got["rects"]) == 2
    (a0, a1), (b0, b1) = got["rects"]
    # Clipped at the plot's edges, halfway between bars inside it.
    assert a0 == pytest.approx(left) and a1 == pytest.approx(x(1) + half)
    assert b0 == pytest.approx(x(5) - half) and b1 == pytest.approx(left + width)


def test_no_band_without_flags_or_with_the_wrong_number():
    assert _shade(None)["groups"] == 0
    # A flag a bar or none: a list from other bars would shade the wrong ones.
    assert _shade([True, False], bars=3)["groups"] == 0
    got = _shade([True, False, True])
    assert got["groups"] == 1 and len(got["rects"]) == 2
