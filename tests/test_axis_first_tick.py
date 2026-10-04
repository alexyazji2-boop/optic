"""The first label on a time axis names a month, not a year.

A live Pulse chart of AAPL over three months read "2026, Sep, Oct": the
leftmost label said the year and not which month the line starts in. A year
the axis crosses is still named where it turns.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CHARTS = (ROOT / "static/charts.js").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _fn(head):
    at = CHARTS.index(head)
    return CHARTS[at:CHARTS.index("\n}\n", at) + 3]


def _labels(unit, dates):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    months = CHARTS[CHARTS.index("const MONTH_SHORT"):CHARTS.index("/** A bar's label")]
    script = months + _fn("function tickLabel(d, unitId, prev) {") + """
      var ds = %s.map(function (s) { var p = s.split('-'); return new Date(+p[0], +p[1] - 1, +p[2]); });
      print('RESULT:' + JSON.stringify(ds.map(function (d, i) { return tickLabel(d, '%s', i ? ds[i - 1] : null); })));
    """ % (json.dumps(dates), unit)
    out = subprocess.run([exe, "-e", script], capture_output=True, text=True, timeout=60)
    assert "RESULT:" in out.stdout, (out.stdout + out.stderr)[-1500:]
    return json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])


def test_months_start_with_a_month_and_name_a_year_where_it_turns():
    assert _labels("month", ["2026-07-01", "2026-08-01", "2026-09-01", "2026-10-01"]) == ["Jul", "Aug", "Sep", "Oct"]
    assert _labels("month", ["2025-11-03", "2025-12-01", "2026-01-02", "2026-02-02"]) == ["Nov", "Dec", "2026", "Feb"]


def test_days_and_years_are_as_they_were():
    assert _labels("day", ["2026-09-08", "2026-09-15", "2026-09-22", "2026-10-01"]) == ["Sep", "15", "22", "Oct"]
    assert _labels("year", ["2022-01-03", "2023-01-03", "2024-01-02"]) == ["2022", "2023", "2024"]
