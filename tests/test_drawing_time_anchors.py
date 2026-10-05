"""Drawings are anchored to a time and a price, and stay on their candles.

**The defect.** A drawing was stored as `{i, p}`: a bar index into whatever
slice of bars was on screen when it was placed. Every pan, zoom, range change
and resize re-slices the bars, and the stored index went on naming the same
screen position while the candles moved under it. Measured on SPY hourly: a
trend line anchored on the 2026-09-02 14:30 candle drew 243px away from it
after a 150-bar pan; and in the browser harness used to verify the fix, an
`{i, p}` copy of a drawing moved 162.3px after a 100-bar pan while the same
drawing stored as `{t, p}` moved 0.

So a drawing is `{t, p}` now, converted to an index against the bars on
screen at draw time by `wsTimeAxis`. These tests drive that conversion, the
migration of stored `{i, p}` sets, the per-symbol store and cancelling a drag,
executed under JavaScriptCore rather than read as text: an off-by-one in an
interpolation and the correct one read alike.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess

import pytest

JSC = ("/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/"
       "Helpers/jsc")


def _run(scenario: str, seed: dict | None = None) -> dict:
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    script = """
      load('tests/support/browser_stubs.js');
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      document.documentElement.style.removeProperty = function () {};
      // A storage that keeps what it is given, seeded before app.js reads it.
      var SAVED = %s;
      localStorage.getItem = function (k) { return k in SAVED ? SAVED[k] : null; };
      localStorage.setItem = function (k, v) { SAVED[k] = String(v); };
      localStorage.removeItem = function (k) { delete SAVED[k]; };
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}

      // Weekdays from a Monday, as the feed dates daily bars.
      function weekdays(fromIso, n) {
        var out = [], d = new Date(fromIso + 'T00:00:00Z');
        while (out.length < n) {
          var w = d.getUTCDay();
          if (w !== 0 && w !== 6) out.push(d.toISOString().slice(0, 10));
          d = new Date(d.getTime() + 86400000);
        }
        return out;
      }
      // The series the axis is read against: the whole history for the size
      // on screen, and the slice of it a pan or zoom has put on screen.
      var FULL = { dates: [] }, SHOWN = { dates: [] };
      wsBaseSeries = function () { return FULL; };
      wsSeries = function () { return SHOWN; };
      function show(full, from, to) {
        FULL = full;
        SHOWN = {};
        Object.keys(full).forEach(function (k) {
          SHOWN[k] = Array.isArray(full[k]) ? full[k].slice(from, to) : full[k];
        });
      }
      STATE.chartData = { ticker: 'TEST' };
      STATE.chartSymbol = 'TEST';
      chartRange = '6m'; chartInterval = 'daily';
      var R = {};
      %s
      print('RESULT:' + JSON.stringify(R));
    """ % (json.dumps({k: json.dumps(v) for k, v in (seed or {}).items()}), scenario)
    proc = subprocess.run([exe, "-e", script], capture_output=True, text=True,
                          timeout=120)
    blob = proc.stdout + proc.stderr
    assert "RESULT:" in blob, blob[-2000:]
    return json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])


# ------------------------------------------------------------ the axis


def test_every_bar_on_screen_is_found_at_its_own_index():
    """The round trip, on a slice that does not start at the first bar. The
    defect was exactly a slice offset ignored, so the slice here starts 10 bars
    in and every one of its 20 bars has to come back where it is drawn."""
    out = _run("""
      show({ dates: weekdays('2026-08-03', 40) }, 10, 30);
      var axis = wsTimeAxis(), worst = 0, back = 0;
      SHOWN.dates.forEach(function (d, k) {
        worst = Math.max(worst, Math.abs(axis.indexOf(wsParseTime(d)) - k));
        if (axis.timeOf(k) !== wsParseTime(d)) back += 1;
      });
      R.ok = axis.ok; R.worst = worst; R.back = back;
    """)
    assert out["ok"] is True
    assert out["worst"] == 0, "a bar's own date must name its own index"
    assert out["back"] == 0, "and its index must name its own date"


def test_a_time_between_two_bars_lands_between_them():
    out = _run("""
      show({ dates: weekdays('2026-08-03', 40) }, 10, 30);
      var axis = wsTimeAxis();
      var a = wsParseTime(SHOWN.dates[3]), b = wsParseTime(SHOWN.dates[4]);
      R.mid = axis.indexOf((a + b) / 2);
    """)
    assert out["mid"] == pytest.approx(3.5)


def test_a_bar_panned_off_screen_keeps_its_exact_index():
    """Five bars before the slice is index -5 exactly: the loaded history is
    still there to read it from, so it is not an estimate."""
    out = _run("""
      var full = { dates: weekdays('2026-08-03', 40) };
      show(full, 10, 30);
      var axis = wsTimeAxis();
      R.before = axis.indexOf(wsParseTime(full.dates[5]));
      R.after = axis.indexOf(wsParseTime(full.dates[35]));
    """)
    assert out["before"] == -5
    assert out["after"] == 25


def test_the_future_counts_trading_days_not_calendar_days():
    """A trend line projected into the empty space right of the last candle.
    The last bar here is a Friday, so the next Monday is one trading day on,
    not three calendar days."""
    out = _run("""
      var full = { dates: weekdays('2026-08-03', 40) };   // ends Fri 2026-09-25
      show(full, 10, 40);
      var axis = wsTimeAxis(), last = SHOWN.dates.length - 1;
      R.lastDay = full.dates[39];
      R.monday = axis.indexOf(Date.parse('2026-09-28T12:00:00Z')) - last;
      R.wednesday = axis.indexOf(Date.parse('2026-09-30T12:00:00Z')) - last;
      R.saturday = axis.indexOf(Date.parse('2026-09-26T12:00:00Z')) - last;
      // And back: an index past the end names the trading day it counts to.
      R.back = new Date(axis.timeOf(last + 3)).toISOString();
      R.roundTrip = axis.indexOf(axis.timeOf(last + 7.25)) - last;
    """)
    assert out["lastDay"] == "2026-09-25"
    assert out["monday"] == pytest.approx(1)
    assert out["wednesday"] == pytest.approx(3)
    assert out["saturday"] == pytest.approx(0.5), "a weekend is no time at all"
    assert out["back"] == "2026-09-30T12:00:00.000Z"
    assert out["roundTrip"] == pytest.approx(7.25)


def test_the_past_before_the_history_counts_the_same_way():
    out = _run("""
      var full = { dates: weekdays('2026-08-03', 40) };   // starts Mon 2026-08-03
      show(full, 10, 30);
      var axis = wsTimeAxis();
      R.friday = axis.indexOf(Date.parse('2026-07-31T12:00:00Z'));
      R.back = new Date(axis.timeOf(-12)).toISOString();
    """)
    # Ten bars of history before the slice, then one trading day further.
    assert out["friday"] == pytest.approx(-11)
    assert out["back"] == "2026-07-30T12:00:00.000Z"


def test_a_weekly_bar_is_five_trading_days():
    out = _run("""
      chartInterval = 'weekly';
      var mondays = weekdays('2026-06-01', 100).filter(function (d) {
        return new Date(d + 'T12:00:00Z').getUTCDay() === 1; });
      show({ dates: mondays }, 0, mondays.length);
      var axis = wsTimeAxis(), last = mondays.length - 1;
      var t = wsParseTime(mondays[last]);
      R.nextWeek = axis.indexOf(t + 7 * 86400000) - last;
    """)
    assert out["nextWeek"] == pytest.approx(1)


HOURLY = """
      chartRange = '60';
      // Seven hourly bars a session, 09:30 to 15:30 Eastern in summer time.
      function hourly(fromIso, days) {
        var out = [];
        weekdays(fromIso, days).forEach(function (d) {
          for (var h = 0; h < 7; h += 1) {
            out.push(new Date(Date.parse(d + 'T13:30:00Z') + h * 3600000).toISOString());
          }
        });
        return out;
      }
"""


def test_an_hourly_series_projects_by_its_own_bars_per_day():
    """A day ahead of the last bar is seven bars ahead: the regular session's
    count, the median the axis takes from the bars themselves."""
    out = _run(HOURLY + """
      var dates = hourly('2026-09-14', 9);                  // ends Thu 2026-09-24
      show({ dates: dates }, 20, dates.length);
      var axis = wsTimeAxis(), last = SHOWN.dates.length - 1;
      var t = wsParseTime(SHOWN.dates[last]);
      R.perDay = wsBarsPerDay(dates.map(wsParseTime));
      R.dayAhead = axis.indexOf(t + 86400000) - last;
    """)
    assert out["perDay"] == 7
    assert out["dayAhead"] == pytest.approx(7)


def test_a_point_past_fridays_close_is_mondays_bar_and_lands_on_it():
    """The space right of the last candle, across a weekend, and then the
    candles arriving under it: the live-update half of keeping a drawing where
    it was put.

    Three bars past Friday's 15:30 bar is Monday's 11:30 bar. With the day's
    elapsed part measured across all twenty-four hours the point was stored as
    05:47 UTC on Monday, and once Monday's bars were loaded it drew 0.88 of a
    bar past Friday's, on no candle at all."""
    out = _run(HOURLY + """
      var dates = hourly('2026-09-14', 10);                 // ends Fri 2026-09-25
      show({ dates: dates }, 20, dates.length);
      var axis = wsTimeAxis(), last = SHOWN.dates.length - 1;
      var t = axis.timeOf(last + 3);
      R.stored = new Date(t).toISOString();
      // Monday's session arrives; the slice keeps its start and grows.
      var later = dates.concat(hourly('2026-09-28', 1));
      show({ dates: later }, 20, later.length);
      var after = wsTimeAxis();
      R.landed = after.indexOf(t) - last;
      R.onBar = SHOWN.dates[last + 3];
    """)
    assert out["stored"] == "2026-09-28T15:30:00.000Z", "Monday 11:30 Eastern"
    assert out["landed"] == pytest.approx(3)
    assert out["onBar"] == "2026-09-28T15:30:00.000Z"


def test_a_daily_point_in_the_future_lands_on_its_candle_when_it_arrives():
    out = _run("""
      var dates = weekdays('2026-08-03', 40);               // ends Fri 2026-09-25
      show({ dates: dates }, 10, 40);
      var axis = wsTimeAxis(), last = SHOWN.dates.length - 1;
      var t = axis.timeOf(last + 2);
      var later = weekdays('2026-08-03', 42);               // Mon and Tue arrive
      show({ dates: later }, 10, 42);
      R.landed = wsTimeAxis().indexOf(t) - last;
      R.stored = new Date(t).toISOString();
    """)
    assert out["stored"] == "2026-09-29T12:00:00.000Z"
    assert out["landed"] == pytest.approx(2)


def test_a_daily_date_is_read_as_midday_utc():
    """"2026-09-02" parsed as midnight UTC is the evening of 1 September in New
    York, so a drawing anchored on it would print the previous day's date."""
    out = _run("""
      R.t = new Date(wsParseTime('2026-09-02')).toISOString();
      R.label = wsAnchorDate(wsParseTime('2026-09-02'));
    """)
    assert out["t"] == "2026-09-02T12:00:00.000Z"
    assert out["label"] == "2026-09-02"


def test_no_bars_means_no_axis_rather_than_a_wrong_one():
    out = _run("""
      show({ dates: [] }, 0, 0);
      var axis = wsTimeAxis();
      R.ok = axis.ok; R.nan = isNaN(axis.indexOf(Date.now()));
    """)
    assert out == {"ok": False, "nan": True}


# ------------------------------------------------------------ the store


def test_drawings_are_kept_per_symbol_and_persisted():
    out = _run("""
      STATE.chartSymbol = 'AAA';
      wsSaveDrawings([{ id: 'a1', kind: 'hline', points: [{ t: 1, p: 10 }] }]);
      STATE.chartSymbol = 'BBB';
      R.bBefore = wsDrawings().length;
      wsSaveDrawings([{ id: 'b1', kind: 'hline', points: [{ t: 2, p: 20 }] }]);
      STATE.chartSymbol = 'AAA';
      R.a = wsDrawings().map(function (d) { return d.id; });
      R.stored = JSON.parse(SAVED[WS_DRAW_KEY_V2]);
    """)
    assert out["bBefore"] == 0, "one symbol's drawings must not appear on another"
    assert out["a"] == ["a1"]
    assert sorted(out["stored"]) == ["AAA", "BBB"]
    assert out["stored"]["BBB"][0]["points"] == [{"t": 2, "p": 20}]


def test_a_stored_set_is_read_back_at_load():
    out = _run("""
      STATE.chartSymbol = 'AAA';
      R.ids = wsDrawings().map(function (d) { return d.id; });
    """, seed={"optic.chart.drawings.v2": {"AAA": [{"id": "kept", "kind": "hline",
                                                     "points": [{"t": 5, "p": 1}]}]}})
    assert out["ids"] == ["kept"]


def test_an_old_index_set_is_moved_to_times_where_it_was_drawn():
    """The `{i, p}` sets are pinned to the dates they currently render at, which
    is the only position anyone has seen them in, then drained so they are
    never migrated twice."""
    out = _run("""
      STATE.chartSymbol = 'AAA';
      show({ dates: weekdays('2026-08-03', 40) }, 10, 30);
      var axis = wsTimeAxis();
      wsMigrateLegacy(axis);
      var dr = wsDrawings()[0];
      R.points = dr.points.map(function (p) { return [new Date(p.t).toISOString().slice(0, 10), p.p]; });
      R.want = [SHOWN.dates[2], SHOWN.dates[5]];
      R.left = JSON.parse(SAVED[WS_DRAW_KEY] || '{}');
      R.saved = JSON.parse(SAVED[WS_DRAW_KEY_V2]).AAA.length;
      wsMigrateLegacy(axis);
      R.afterTwice = wsDrawings().length;
    """, seed={"optic.chart.drawings.v1": {"AAA": [{"id": "old", "kind": "trend",
                                                     "points": [{"i": 2, "p": 100},
                                                                {"i": 5, "p": 101}]}]}})
    assert [p[0] for p in out["points"]] == out["want"]
    assert [p[1] for p in out["points"]] == [100, 101]
    assert "AAA" not in out["left"], "drained, so it is not migrated again"
    assert out["saved"] == 1 and out["afterTwice"] == 1


# ------------------------------------------------------------ cancelling


def test_escape_mid_drag_puts_the_drawing_back():
    """Escape was missing from the ladder, so a drawing kept following the
    pointer and the release committed it wherever it had got to."""
    out = _run("""
      STATE.view = 'chart';
      wsRenderDrawings = function () {}; wsSyncDrawChrome = function () {};
      wsSaveDrawings([{ id: 'x', kind: 'trend', points: [{ t: 1, p: 10 }, { t: 2, p: 11 }] }]);
      var dr = wsDrawings()[0];
      wsDragging = { id: 'x', part: 'all', from: { i: 0, p: 0 },
        original: JSON.parse(JSON.stringify(dr.points)) };
      dr.points = [{ t: 9, p: 90 }, { t: 10, p: 91 }];       // mid-drag
      wsDrawKeys({ key: 'Escape', target: { tagName: 'DIV' }, preventDefault: function () {} });
      R.points = wsDrawings()[0].points;
      R.dragging = wsDragging;
      R.stored = JSON.parse(SAVED[WS_DRAW_KEY_V2]).TEST[0].points;
    """)
    assert out["points"] == [{"t": 1, "p": 10}, {"t": 2, "p": 11}]
    assert out["dragging"] is None
    assert out["stored"] == [{"t": 1, "p": 10}, {"t": 2, "p": 11}]


def test_escape_shuts_an_open_menu_before_it_cancels_anything_on_the_chart():
    out = _run("""
      STATE.view = 'chart';
      wsRenderDrawings = function () {}; wsSyncDrawChrome = function () {};
      views.chart = { querySelector: function () { return null; } };
      wsMenuOpen = 'levels'; wsToolsOpen = true; wsSelected = 'x';
      wsDrawKeys({ key: 'Escape', target: { tagName: 'DIV' }, preventDefault: function () {} });
      R.first = [wsMenuOpen, wsToolsOpen, wsSelected];
      wsDrawKeys({ key: 'Escape', target: { tagName: 'DIV' }, preventDefault: function () {} });
      R.second = [wsMenuOpen, wsToolsOpen, wsSelected];
    """)
    assert out["first"] == [None, False, "x"], "the menu goes first, the selection stays"
    assert out["second"] == [None, False, None]


# ------------------------------------------------------------ snapping


def test_a_point_near_a_candle_snaps_to_its_high_and_says_so():
    out = _run("""
      show({ dates: weekdays('2026-08-03', 5), open: [10, 11, 12, 13, 14],
             high: [12, 13, 14, 15, 16], low: [9, 10, 11, 12, 13],
             close: [11, 12, 13, 14, 15] }, 0, 5);
      // 10px per dollar, so the 7px radius is 0.7 of a dollar.
      var frame = { bars: 5, yOf: function (v) { return 500 - v * 10; } };
      wsSetSnap(true);
      R.near = wsSnapIndexPrice(2.2, 14.4, frame);
      R.far = wsSnapIndexPrice(2.2, 15.5, frame);
      wsSetSnap(false);
      R.off = wsSnapIndexPrice(2.2, 14.4, frame);
      R.saved = SAVED[WS_SNAP_KEY];
    """)
    assert out["near"]["i"] == 2 and out["near"]["p"] == 14
    assert out["near"]["snap"]["field"] == "H"
    # Out of reach of every value: the bar is still whole, the price is free.
    assert out["far"]["i"] == 2 and out["far"]["p"] == 15.5 and out["far"]["snap"] is None
    # Off: exactly where the pointer was, and the choice is remembered.
    assert out["off"] == {"i": 2.2, "p": 14.4, "snap": None}
    assert out["saved"] == "off"
