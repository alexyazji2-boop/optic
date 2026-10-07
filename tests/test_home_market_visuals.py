"""Home and Markets: movement as lines, the week as days, sectors as a heatmap.

Asked for as an "at-a-glance market intelligence view": watchlist and market
movement in sparklines, upcoming catalysts as a calendar strip, sector
rotation as a heatmap, rates as a curve, and the expected move as a range. All
from data the pages already load; the watchlist feed gained its last 30 closes,
from the same pull its changes are read from.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pandas as pd
import pytest

from app.analytics import watchlist as watchlist_mod
from tests.test_visual_primitives import DOM

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "static/styles.css").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _app(script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = """
      load('tests/support/browser_stubs.js');
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      document.documentElement.style.removeProperty = function () {};
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
      var R = {}, BUILT = {}, CAPT = {};
      vizMount = function (id, build, none) { BUILT[id] = { build: build, none: none }; };
      ['rangeChart', 'curveChart'].forEach(function (name) {
        this[name] = function (o) { (CAPT[name] = CAPT[name] || []).push(o); return { chart: name }; };
      });
      function build(id) { var b = BUILT[id]; return b ? b.build(500) : 'not mounted'; }
    """ + script + "\nprint('RESULT:' + JSON.stringify(R));"
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    blob = out.stdout + out.stderr
    assert "RESULT:" in blob, blob[-2000:]
    return json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])


# ------------------------------------------------------------ sparklines

def test_the_watchlist_feed_carries_its_last_thirty_closes(monkeypatch):
    closes = pd.Series([100 + i * 0.123456 for i in range(80)],
                       index=pd.date_range("2026-06-01", periods=80, freq="B"))
    frame = pd.DataFrame({"Close": closes, "Volume": [1e6] * 80})
    monkeypatch.setattr(watchlist_mod, "_frames", lambda provider, wanted: {"AAA": frame, watchlist_mod.BENCH: frame})
    row = watchlist_mod.build(None, ["AAA"])["rows"][0]
    assert len(row["spark"]) == 30 and row["spark"][-1] == round(closes.iloc[-1], 2)
    assert row["spark"][0] == round(closes.iloc[-30], 2)


def test_a_row_and_a_strip_cell_carry_their_line():
    out = _app("""
      R.slot = sparkSlot([1, 2, 3]);
      R.down = sparkSlot([3, 2, 1], 'ms-spark');
      R.none = sparkSlot([5]);
      R.row = watchRow({ symbol: 'AAA', available: true, price: 10, change_pct: 1, spark: [1, 2, 3], signal: 'bullish' }, {});
      var forty = []; for (var i = 0; i < 40; i++) forty.push(7700 + i);
      R.cell = marketStripHTML({ macro: { groups: { equity: [
        { label: 'S&P 500', symbol: '^GSPC', last: 7800, chg_1d: 0.5, series: forty }] } } });
    """)
    assert 'data-spark="1,2,3" data-dir="up"' in out["slot"] and 'aria-hidden="true"' in out["slot"]
    assert 'class="ms-spark"' in out["down"] and 'data-dir="down"' in out["down"]
    assert out["none"] == "", "one close is not a line"
    assert '<span class="wl-trend"><span class="wl-spark"' in out["row"]
    cell = out["cell"]
    assert cell.count('class="ms-spark"') == 1, cell
    assert 'data-spark="7710,' in cell and ',7739"' in cell, "the strip draws the last 30 of the 90 closes it has"


def test_a_line_is_drawn_at_the_width_its_track_has():
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = DOM + """
      load('static/charts.js');
      var widths = [];
      sparkline = function (v, w, h) { widths.push([w, h]); return new El('svg'); };
      eval(%s);
      function slot(cls, parentWidth) {
        var s = new El('span'); s.dataset = { spark: '1,2,3', dir: 'up' };
        s.classList = { contains: function (c) { return c === cls; } };
        s.parentElement = { clientWidth: parentWidth };
        return s;
      }
      var slots = [slot('wl-spark', 60), slot('wl-spark', 300), slot('ms-spark', 300)];
      fillSparks({ querySelectorAll: function () { return slots; } });
      print('RESULT:' + JSON.stringify({ widths: widths, drawn: slots.map(function (s) { return s.dataset.drawn; }) }));
    """ % json.dumps(_fill_sparks_source())
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    blob = out.stdout + out.stderr
    r = json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])
    assert r["widths"] == [[58, 18], [160, 18], [64, 16]]
    assert r["drawn"] == ["1", "1", "1"]


def _fill_sparks_source():
    app = (ROOT / "static/app.js").read_text()
    start = app.index("function fillSparks(root) {")
    return app[start:app.index("\n}\n", start) + 2]


def test_a_narrow_row_gives_the_line_its_own_line():
    narrow = CSS[CSS.index("@container (max-width: 559px) {\n  .wv-cols { display: none; }"):]
    narrow = narrow[:narrow.index("\n}\n")]
    assert "'sym price chg go' 'sym changed changed go' 'sym trend signal go'" in narrow
    assert "'sym . price . chg . go' 'sym . changed . signal . go' 'sym . trend trend trend . go'" in CSS


# ------------------------------------------------------------ the week ahead

PRIORITY = {"horizon_days": 5, "columns": [
    {"id": "events", "rows": [{"title": "CFTC Commitments of Traders", "short": "COT", "days_away": 3,
                               "time": "3:30 PM ET", "impact": "medium"},
                              {"title": "Fed minutes", "date": "2026-10-07", "days_away": 2},
                              {"title": "Somewhere next month", "days_away": 40}]},
    {"id": "earnings", "rows": [{"title": "PEP reports Thursday", "when": "Thursday", "date": "2026-10-08",
                                 "impact": "high"},
                                {"title": "MSFT reports Monday", "when": "Monday", "date": "2026-10-05"},
                                {"title": "XYZ reports Friday", "when": "Friday"}]},
]}


def test_the_strip_places_only_what_the_feed_dates():
    out = _app("R.html = catalystStripHTML(%s, '2026-10-06T21:00:00-04:00');" % json.dumps(PRIORITY))
    html = out["html"]
    assert html.count('class="cs-day') == 4, "Tuesday to Sunday, the feed's five days ahead, weekend left out"
    assert ">Today<" in html and "Wed 7" in html and "Thu 8" in html and "Fri 9" in html
    assert "Sat 10" not in html and "Mon 12" not in html, "no day past what the feed looked at"
    assert "COT" in html and "3:30 PM ET" in html and "PEP reports Thursday" in html
    assert "Somewhere next month" not in html
    assert "XYZ reports Friday" not in html, "a weekday name alone is not a date"
    assert "MSFT reports Monday" not in html, "this week's Monday is past, not next week's"
    assert 'aria-label="3 scheduled catalysts by day"' in html
    assert "Nothing tracked" in html


def test_a_dated_row_is_placed_by_its_date_not_a_stale_count():
    # The feed was read yesterday: its days away are a day out, its dates are not.
    out = _app("R.html = catalystStripHTML(%s, '2026-10-07T09:00:00-04:00');" % json.dumps(PRIORITY))
    html = out["html"]
    wed = html[html.index(">Today<"):html.index("Thu 8")]
    assert "Fed minutes" in wed and "PEP reports Thursday" in html[html.index("Thu 8"):]


def test_a_busy_day_shows_two_and_opens_the_rest_below():
    busy = {"horizon_days": 5, "columns": [
        {"id": "events", "rows": [{"title": "Low one", "days_away": 0, "impact": "low"},
                                  {"title": "CPI", "days_away": 0, "impact": "high"},
                                  {"title": "Low two", "days_away": 0, "impact": "low"}]},
        {"id": "earnings", "rows": [{"title": "PEP reports Tuesday", "date": "2026-10-06", "impact": "high"}]}]}
    out = _app("R.html = catalystStripHTML(%s, '2026-10-06');" % json.dumps(busy))
    today = out["html"][out["html"].index(">Today<"):out["html"].index("Wed 7")]
    assert today.index("CPI") < today.index("PEP reports Tuesday"), "the larger first, in the feed's order"
    assert "Low one" not in today and "Low two" not in today
    assert 'data-ht-show="events"' in today and ">2 more<" in today
    assert 'aria-label="2 more on Today, listed below"' in today
    assert '<span class="sr-only"> (high impact)</span>' in today, "impact is said, not only coloured"
    app = (ROOT / "static/app.js").read_text()
    assert "evt.target.closest('[data-ht-show]')" in app and 'data-ht-col="${esc(c.id)}"' in app


def test_a_week_with_nothing_datable_shows_no_strip():
    out = _app("R.html = catalystStripHTML({ columns: [{ id: 'events', rows: [{ title: 'x' }] }] }, '2026-10-06');")
    assert out["html"] == ""


def test_the_feed_dates_its_earnings_days_and_events():
    from datetime import datetime

    from app import priority, weekly
    from tests.test_weekly import _Provider

    got = weekly.earnings_this_week(_Provider({"AAPL": "2026-08-12", "MSFT": "2026-08-11"}),
                                    datetime(2026, 8, 10, tzinfo=weekly.ET), watchlist=["AAPL", "MSFT"])
    assert [(d["day"], d["date"]) for d in got["days"]] == [("Tuesday", "2026-08-11"), ("Wednesday", "2026-08-12")]
    assert priority._et_date("2026-10-09T15:30:00-04:00") == "2026-10-09"
    assert priority._et_date("2026-10-10T02:00:00+00:00") == "2026-10-09", "New York's date, not UTC's"
    assert priority._et_date(None) is None and priority._et_date("soon") is None


def test_priority_rows_carry_the_date(monkeypatch):
    from app import priority

    monkeypatch.setattr(priority.events_mod, "upcoming", lambda now=None, **kw: {"events": [
        {"title": "CPI", "days_away": 2, "at": "2026-10-08T08:30:00-04:00", "impact": "high"}]})
    monkeypatch.setattr(priority.weekly_mod, "earnings_this_week", lambda provider, now=None: {"days": [
        {"day": "Thursday", "date": "2026-10-08", "symbols": ["PEP"]}]})
    assert priority._events()[0]["date"] == "2026-10-08"
    assert priority._earnings(None)[0]["date"] == "2026-10-08"


# ------------------------------------------------------------ Markets

SECTORS = {"benchmark": "SPY", "sectors": [
    {"name": "Energy", "symbol": "XLE", "rs": {"rs_1w": 1.6, "rs_1m": 2.0, "rs_3m": 9.0, "rs_6m": 4.0}},
    {"name": "Technology", "symbol": "XLK", "rs": {"rs_1w": 1.9, "rs_1m": 3.0, "rs_3m": 5.0, "rs_6m": 12.0}},
    {"name": "Utilities", "symbol": "XLU", "rs": {"rs_1w": -0.5, "rs_1m": -2.0, "rs_3m": -6.0, "rs_6m": -3.0}},
]}


def test_the_sector_heatmap_is_a_table_with_its_figures():
    out = _app("R.html = sectorHeatHTML(%s); R.pos = C.pos;" % json.dumps(SECTORS))
    html = out["html"]
    assert "Energy leads SPY over three months; Utilities trails it" in html
    assert '<table class="data heat">' in html and "<th>3 months</th>" in html
    assert ">+9.0%<" in html and ">-6.0%<" in html, "every cell carries its figure and sign"
    # Scaled within its column: the column's largest is the deepest.
    assert "0.620)" in html


def test_the_yield_curve_says_its_shape():
    up = _app("R.t = macroYieldCurve({ '^IRX': { last: 4.0 }, '^FVX': { last: 5.0 }, '^TNX': { last: 5.27 } });")
    inv = _app("R.t = macroYieldCurve({ '^IRX': { last: 5.5 }, '^FVX': { last: 5.0 }, '^TNX': { last: 4.5 } });")
    assert "The curve slopes up: the 10-year yields 1.27 points more than the 3-month" in up["t"]
    assert "The curve is inverted: the 3-month yields 1.00 points more than the 10-year" in inv["t"]


def test_the_expected_move_and_curve_are_drawn_from_the_payload():
    out = _app("""
      mountMarketVisuals({ expected_move: { spot: 7800, implied_pct: 1.0, realized_pct: 0.5 },
        instruments: { '^IRX': { last: 4, close_20d_ago: 3.8 }, '^FVX': { last: 5, close_20d_ago: 4.6 }, '^TNX': { last: 5.3, close_20d_ago: 4.8 } } });
      build('viz-mkt-move'); build('viz-mkt-curve');
      R.move = CAPT.rangeChart[0]; R.curve = CAPT.curveChart[0];
    """)
    m = out["move"]
    assert m["low"] == pytest.approx(7722) and m["high"] == pytest.approx(7878)
    assert [mk["value"] for mk in m["marks"]] == pytest.approx([7800, 7761, 7839])
    c = out["curve"]
    assert c["categories"] == ["3 month", "5 year", "10 year"]
    assert c["series"][0]["values"] == [4, 5, 5.3] and c["series"][1]["values"] == [3.8, 4.6, 4.8]


def test_the_curve_primitive():
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = DOM + """
      load('static/charts.js');
      var root = curveChart({ width: 400, categories: ['3 month', '5 year', '10 year'],
        series: [{ name: 'Now', values: [4, 5, 5.3] }, { name: 'Before', values: [3.8, 4.6, 4.8], dash: true }] });
      var R = { labels: texts(root), marks: all(root, function (n) { return n.attrs && n.attrs.tabindex === '0'; }).length,
                none: curveChart({ categories: ['x'], series: [{ values: [1] }] }) };
      print('RESULT:' + JSON.stringify(R));
    """
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    r = json.loads((out.stdout + out.stderr).split("RESULT:", 1)[1].split("\n")[0])
    assert "5.30%" in r["labels"] and "3 month" in r["labels"]
    assert r["marks"] == 6 and r["none"] is None
