"""The session strip's clock keeps time.

Reported with a screenshot of the strip reading "Thu 5:05 pm EDT · Overnight
in 2 hours and 54 minutes" beside a menu bar at 5:19: "time should always be
updating". The line printed the server's `now_et`, which is the moment of the
last fetch, and the fetch was repeated each minute only while a symbol was
loaded. On Home with none, the strip kept the time the page opened at.

It reads the browser's clock, redrawn every second, the marker on the day
with it; the server is asked every minute with or without a symbol, and again
once the next session's start has passed.

Checked in a browser on Home with no symbol: the line read the clock's 6:07,
a clock moved 14 minutes on read 6:21 and "1 hour and 38 minutes" with the
marker moved, and past 8 pm one /api/session went out, and only one.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"

# 5:05 pm ET on Thursday 1 October 2026, after hours, with overnight at 8 pm.
SESSION = {
    "phase": "after", "label": "After hours", "now_et": "2026-10-01T17:05:00-04:00",
    "now_et_label": "5:05 PM", "weekday": "Thu", "day_pct": 71.18,
    "next": {"phase": "overnight", "label": "Overnight",
             "starts_at": "2026-10-01T20:00:00-04:00", "minutes_away": 174},
    "segments": [],
}
AT_505 = "Date.parse('2026-10-01T17:05:00-04:00')"
AT_519 = "Date.parse('2026-10-01T17:19:30-04:00')"


def _run(script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    out = subprocess.run([exe, "-e", """
      load('tests/support/browser_stubs.js');
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      document.documentElement.style.removeProperty = function () {};
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
      SETTINGS.timezone = 'America/New_York';
      var line = { textContent: '' }, mark = { style: { left: '' } };
      document.getElementById = function (id) { return id === 'ses-clock' ? line : null; };
      document.querySelector = function (q) { return q === '#sessionbar .ses-now' ? mark : null; };
      var asked = [];
      loadSession = function (force) { asked.push('ticker'); };
      loadCalendarSession = function (force) { asked.push('calendar'); };
    """ + script], capture_output=True, text=True, timeout=120, cwd=str(ROOT))
    assert "RESULT:" in out.stdout, (out.stdout + out.stderr)[-2000:]
    return json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])


def test_the_line_is_the_time_now_and_not_the_time_of_the_fetch():
    out = _run("""
      var sess = %s;
      var then = sessionClockLine(sess, %s), now = sessionClockLine(sess, %s);
      SETTINGS.timezone = 'Europe/London';
      var away = sessionClockLine(sess, %s);
      print('RESULT:' + JSON.stringify({ then: then, now: now, away: away }));
    """ % (json.dumps(SESSION), AT_505, AT_519, AT_519))
    assert out["then"] == "Thu 5:05 pm EDT · Overnight in 2 hours and 55 minutes"
    assert out["now"] == "Thu 5:19 pm EDT · Overnight in 2 hours and 40 minutes", (
        "whole minutes left, rounded down, as the server counts them")
    assert out["away"].startswith("Thu 10:19 pm "), out["away"]
    assert "· Thu 5:19 pm ET · Overnight in 2 hours and 40 minutes" in out["away"], (
        "and the market's own clock beside it, at the same moment")


def test_every_second_the_line_and_the_marker_follow_the_clock():
    out = _run("""
      STATE.session = { session: %s };
      STATE.ticker = null;
      var t = %s;
      Date.now = function () { return t; };
      tickSessionBar();
      var first = [line.textContent, mark.style.left];
      t = %s;
      tickSessionBar();
      print('RESULT:' + JSON.stringify({ first: first, then: [line.textContent, mark.style.left], asked: asked }));
    """ % (json.dumps(SESSION), AT_505, AT_519))
    assert out["first"] == ["Thu 5:05 pm EDT · Overnight in 2 hours and 55 minutes", "71.18%"]
    assert out["then"] == ["Thu 5:19 pm EDT · Overnight in 2 hours and 40 minutes", "72.19%"]
    assert out["asked"] == [], "nothing to ask the server while the session holds"


def test_past_the_next_start_the_server_is_asked_and_not_on_every_tick():
    out = _run("""
      STATE.session = { session: %s };
      var t = Date.parse('2026-10-01T20:00:01-04:00');
      Date.now = function () { return t; };
      STATE.ticker = null;
      tickSessionBar(); var once = asked.slice();
      t += 5000; tickSessionBar(); var held = asked.slice();
      t += 11000; STATE.ticker = 'NVDA'; tickSessionBar();
      print('RESULT:' + JSON.stringify({ once: once, held: held, again: asked, line: line.textContent }));
    """ % json.dumps(SESSION))
    assert out["once"] == ["calendar"], "no symbol loaded: the calendar session"
    assert out["held"] == ["calendar"], "not again within fifteen seconds"
    assert out["again"] == ["calendar", "ticker"], "and with a symbol, the symbol's session"
    assert out["line"].endswith("Overnight starting now"), out["line"]


def test_the_minute_refresh_runs_without_a_symbol_and_the_tick_is_wired():
    assert "setInterval(refreshSession, 60000);" in APP
    assert "setInterval(tickSessionBar, 1000);" in APP
    assert "setInterval(() => { if (STATE.ticker) loadSession(true); }, 60000);" not in APP
    load = APP[APP.index("async function loadCalendarSession(force) {"):]
    load = load[:load.index("\n}\n")]
    assert "if (STATE.session && !force) return;" in load
    assert "if (!STATE.session || !STATE.session.ticker) STATE.session = { session: data };" in load, (
        "a symbol's session, which carries its prices, is not replaced by the calendar's")
    render = APP[APP.index("function renderSessionBar() {"):]
    render = render[:render.index("\n}\n")]
    assert '<span class="ses-sub" id="ses-clock">${esc(sessionClockLine(sess, now))}</span>' in render
    assert "left:${sessionDayPct(now)}%" in render
    assert not re.search(r"sess\.now_et\b", render), "the time of the fetch is not printed"
