"""The Charting tab opens on hourly bars.

Asked for as "when the chart tab loads, load it into the 1h chart". Each time
the tab is opened, and not on the refresh tick that reloads it every twenty
seconds while it is open, so a size chosen on it holds until the reader leaves.
The range is shared with the Options chart, so the range the hour replaced is
put back when the tab is left still on it; a size or range pressed on the tab
is the reader's and stands.

Checked in a browser on NVDA: Overview on 6M, then Chart opened on 1h ("NVDA
1h · 3 months"); a reload of the view kept 1h; Options was back on 6M; Chart
again was 1h; 1D pressed on the tab stayed after leaving it.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


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
      var stored = [];
      localStorage.setItem = function (k, v) { stored.push([k, v]); };
    """ + script], capture_output=True, text=True, timeout=120, cwd=str(ROOT))
    assert "RESULT:" in out.stdout, (out.stdout + out.stderr)[-2000:]
    return json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])


def test_opening_the_tab_is_the_hour_and_leaving_it_puts_the_range_back():
    out = _run("""
      chartRange = '6m'; wsWindow = { from: 1, to: 9 }; wsYZoom = 3;
      var opened = wsOpenOnHour();
      var onTab = [chartRange, wsWindow, wsYZoom];
      wsLeaveHour();
      var left = chartRange;
      chartRange = '60';
      var already = wsOpenOnHour();
      print('RESULT:' + JSON.stringify({ opened: opened, onTab: onTab, left: left, already: already,
        stored: stored.filter(function (s) { return s[0] === CHART_RANGE_KEY; }) }));
    """)
    assert out["opened"] is True and out["onTab"] == ["60", None, 1], "the hour, from the start"
    assert out["left"] == "6m", "the Options chart's range, back"
    assert out["already"] is False, "already on the hour, nothing to put back"
    assert out["stored"] == [], "where the tab starts is not stored as a choice"


def test_a_size_pressed_on_the_tab_is_kept_after_it():
    out = _run("""
      chartRange = '6m';
      wsOpenOnHour();
      chartRange = '15';                     // a size pressed on the tab
      wsKeepSize();
      wsLeaveHour();
      var size = chartRange;
      chartRange = '6m';
      wsOpenOnHour();
      wsKeepSize();                          // the hour itself, pressed
      wsLeaveHour();
      print('RESULT:' + JSON.stringify({ size: size, hour: chartRange }));
    """)
    assert out == {"size": "15", "hour": "60"}


def test_the_switch_is_on_entering_and_leaving_not_on_a_reload():
    fn = APP[APP.index("function switchView(view, force) {"):]
    fn = fn[:fn.index("\n}\n")]
    assert "const was = STATE.view;" in fn
    assert "if (was === 'chart' && view !== 'chart') wsLeaveHour();" in fn
    assert "const reopened = view === 'chart' && was !== 'chart' && wsOpenOnHour();" in fn
    assert fn.index("wsOpenOnHour()") < fn.index("STATE.view = view;"), "before the view is set"
    assert fn.index("loadView(view, !!force);") < fn.index("if (reopened) {"), (
        "studies and trend lines asked again once the symbol is set")
    load = APP[APP.index("function loadView(view, force) {"):]
    load = load[:load.index("\n}\n")]
    assert "wsOpenOnHour" not in load, "the refresh tick reloads the view and must not reset it"
    assert "const WS_OPEN_SIZE = '60';" in APP
    assert [s for s in ("const wsInt = evt.target.closest('[data-ws-interval]');",
                        "const wsRange = evt.target.closest('[data-ws-range]');")
            if "wsKeepSize();" not in APP[APP.index(s):APP.index("return;\n  }", APP.index(s))]] == [], (
        "both the size menu and the range pills are the reader's choice")
