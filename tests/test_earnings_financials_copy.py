"""Earnings and Financials: each figure says what it is, once.

Measured on AAPL on 2026-10-07:
- The next report read "2026-11-02" in display type, beside a chip reading
  "Estimates unknown" over a known EPS consensus and revenue range, and a
  chip reading "Event fair".
- The week's calendar said "1 reporting from the watchlist" over PepsiCo on a
  watchlist of SPY, QQQ, NVDA and AMD: "the watchlist" was the 144 names the
  server scans.
- Financials printed "Revenue growth +16.4%" in Key stats and "Revenue growth
  (y/y) +6.4%" under the statements, both right and for different periods,
  and "Net cash position $-62.7B" above "$62.72B net debt position".
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


def _fn(head):
    at = APP.index(head)
    return APP[at:APP.index("\n}\n", at) + 3]


def test_a_report_date_is_written_as_a_reader_says_it():
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = _fn("function reportDate(iso) {") + """
      var y = new Date().getFullYear();
      print('RESULT:' + JSON.stringify([reportDate(y + '-11-02'), reportDate((y + 1) + '-01-29'),
        reportDate('not a date')]));
    """
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=30)
    got = json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])
    assert got[0].endswith("Nov 2") and "," in got[0], got
    assert got[1].endswith(str(__import__("datetime").date.today().year + 1)), "another year says so"
    assert got[2] == "not a date"


def test_the_next_report_card_says_what_its_chips_mean():
    assert "nr.date ? esc(reportDate(nr.date))" in APP
    assert "Estimates ${esc(rev.direction || 'unknown')}" not in APP
    assert "rev.direction && rev.direction !== 'unknown'" in APP
    assert "{ expensive: 'Move priced rich', cheap: 'Move priced cheap', fair: 'Move priced fairly' }" in APP


def test_the_week_names_its_scan_for_what_it_is_and_marks_your_own():
    fn = _fn("function renderEarningsWeek(w) {")
    assert "reporting\n          from the watchlist" not in fn and "Nothing from the watchlist" not in fn
    assert "widely followed names Optic checks" in fn
    assert "const mine = new Set(watchList()" in fn and 'class="ew-mine">watching' in fn


def test_two_figures_for_two_periods_have_two_names():
    rows = _fn("function keyStatRows(q, short) {") if "function keyStatRows(q, short) {" in APP \
        else APP[APP.index("profit_margin: ['Profit margin"):]
    assert "'Profit margin, 12 months'" in rows
    assert "'Revenue growth, last quarter'" in rows


def test_negative_net_cash_is_net_debt():
    assert "? ['Net debt', usdCompact(-(fn.balance_sheet || {}).net_cash)" in APP


def test_no_double_hyphen_stands_in_for_a_dash_in_these_readings():
    for gone in ("reaches net income`\n        + (num(m.gross_pct) !== null\n          ? ` -- ",
                 "netSh), 1)} -- under a tenth", "filters${share === null ? '' : ` -- "):
        assert gone not in APP, gone


def test_the_options_tab_is_called_what_the_strip_calls_it():
    """"Back to Swing", "shared with the Swing tab", "The Swing / Options and
    Macro tabs": the tab strip has said Options since the Dossier."""
    assert "swing: 'Options', earnings: 'Earnings'," in APP
    assert "The Swing / Options and Macro tabs" not in APP
    assert "Overlay settings are shared with the Swing tab" not in APP
    assert "Changes apply to the Charting tab and the Swing chart" not in APP
