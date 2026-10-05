"""Auto trend lines and Support & resistance draw on the Charting tab.

Reported with a screenshot of the Levels menu, both circled: "these two dont
work on charting, fix this". Measured on SPY's hourly chart, the one the tab
opens on, with both switched on:

* Support & resistance: /api/intraday sent eight levels and the chart was
  handed none. `wsSliceWindow` cut every array to the bars on screen, and the
  levels are a list of eight, not a value per bar, so bars 1284 to 1736 of it
  were nothing.
* Auto trend lines: both lines were anchored on 7 April at 651.06, three months
  before the window opens. Each was drawn from 651.06 at the window's left edge
  to 772.78 at its right, a slope that is not the line's, across a plot that
  runs 725 to 783: the lines fell off the chart. At the first bar on screen the
  lines are at 710.19 and 713.89, which is where they are drawn now.

Driven under JavaScriptCore against the real functions.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _run(script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = """
      load('tests/support/browser_stubs.js');
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      document.documentElement.style.removeProperty = function () {};
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
      // A hundred daily dates, as the server and the chart both write them.
      var D = [];
      for (var i = 0; i < 100; i += 1) D.push(new Date(Date.UTC(2026, 0, 1) + i * 86400000).toISOString().slice(0, 10));
      var R = {};
    """ + script + "\nprint('RESULT:' + JSON.stringify(R));"
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=120, cwd=str(ROOT))
    blob = out.stdout + out.stderr
    assert "RESULT:" in blob, blob[-2000:]
    return json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])


# ------------------------------------------------- support and resistance


def test_a_window_keeps_the_levels_and_cuts_the_bars():
    out = _run("""
      var close = D.map(function (d, i) { return 100 + i; });
      var levels = [1, 2, 3, 4, 5, 6, 7, 8].map(function (k) { return { price: 100 + k * 10 }; });
      var full = { dates: D, close: close, sr: levels, extended: [], patterns: { zones: [] }, spot: 199 };
      var cut = wsSliceWindow(full, { from: 70, to: 100 });
      R.dates = cut.dates.length; R.close = cut.close.length; R.first = cut.close[0];
      R.sr = cut.sr.length; R.extended = cut.extended.length; R.patterns = !!cut.patterns.zones;
    """)
    assert out["dates"] == 30 and out["close"] == 30 and out["first"] == 170
    assert out["sr"] == 8, "the levels are not a value per bar, and were cut to nothing"
    assert out["extended"] == 0 and out["patterns"] is True


# ------------------------------------------------------------- trend lines


LINE = """
  // Rising one a bar from 100 at server bar 10 to 189 at the last, bar 99.
  var tl = { available: true, dates: D, lines: [{ kind: 'support', start_index: 10, end_index: 99,
    start_price: 100, price_now: 189, touches: 4, broken: false }] };
"""


def test_a_line_anchored_before_the_window_starts_where_the_line_is():
    """The reported fault. The window opens at server bar 50, where the line is
    at 140; it was drawn from the anchor's 100 at that edge."""
    out = _run(LINE + """
      var seg = trendSegments(tl, D.slice(50), {})[0];
      R.seg = seg && { x1: seg.x1, y1: seg.y1, x2: seg.x2, y2: seg.y2 };
    """)
    assert out["seg"] == {"x1": 0, "y1": 140, "x2": 49, "y2": 189}


def test_a_line_anchored_on_screen_starts_on_its_anchor():
    """And a window that ends before the line does, panned into the past,
    ends where the line is on its last bar rather than at today's price."""
    out = _run(LINE + """
      var seg = trendSegments(tl, D.slice(5, 60), {})[0];
      R.seg = seg && { x1: seg.x1, y1: seg.y1, x2: seg.x2, y2: seg.y2 };
    """)
    assert out["seg"] == {"x1": 5, "y1": 100, "x2": 54, "y2": 149}


def test_bars_that_arrived_since_the_fit_carry_the_line_on():
    out = _run(LINE + """
      var later = D.concat(['2026-04-11', '2026-04-12', '2026-04-13']);
      var seg = trendSegments(tl, later.slice(50), {})[0];
      R.seg = seg && { x1: seg.x1, y1: seg.y1, x2: seg.x2, y2: seg.y2 };
    """)
    assert out["seg"] == {"x1": 0, "y1": 140, "x2": 52, "y2": 192}


def test_a_line_anchored_after_the_window_is_not_drawn():
    out = _run(LINE + """
      R.segs = trendSegments(tl, D.slice(0, 8), {}).length;
    """)
    assert out["segs"] == 0
