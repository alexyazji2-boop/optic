"""The weekly stand-in labels a week the way the ten-year weekly bars do.

Reproduced before the fix: `aggregateWeekly` (the 1W chart until the ten-year
bars arrive) labelled each week by its last session and `weeklyFromBars` (the
ten-year bars, from Yahoo) by its Monday. Drawings are stored as times, so one
made on the stand-in sat at a Friday and, read against Monday-dated bars,
landed most of the way into the next week. Yahoo dates a week by its calendar
Monday even when that Monday is a holiday (checked on 2026-09-07 and
2026-01-19), which is what weekMonday returns.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def test_the_stand_in_weeks_are_their_mondays():
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = """
      load('tests/support/browser_stubs.js');
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
      // Labor Day week (Tue to Fri) and the week after it.
      var ps = {dates: ['2026-09-08', '2026-09-09', '2026-09-10', '2026-09-11', '2026-09-14', '2026-09-18'],
                open: [1, 2, 3, 4, 5, 6], high: [2, 3, 4, 5, 6, 9], low: [0, 1, 2, 3, 4, 5],
                close: [1.5, 2.5, 3.5, 4.5, 5.5, 8], volume: [1, 1, 1, 1, 1, 1]};
      var w = aggregateWeekly(ps);
      print('RESULT:' + JSON.stringify({dates: w.dates, close: w.close, high: w.high, mondays: w.mondays}));
    """
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    got = json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])
    assert got["dates"] == ["2026-09-07", "2026-09-14"]
    assert got["close"] == [4.5, 8] and got["high"] == [5, 9]
    assert got["mondays"] is True
