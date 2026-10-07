"""Home as a daily brief: the reader's own names, each thing said once.

Measured on Home at 1440x900 on 2026-10-06, before: the quick picks were the
same eight examples for a reader who had opened INTC and PLTR the day before;
four setups triggering on the close carried the same two-sentence explanation
four times; and the server wrote an em dash into reader-facing copy in nine
places the client-side pass never saw ("XLK — Technology" on the Today band).
"""
from __future__ import annotations

import ast
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


def _run(script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    prelude = """
      function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
      function cap(s) { return s; }
      const DAILY_LINK_LABEL = { swing: 'Swing setups', chart: 'Chart' };
    """ + _fn("function dailyChangeRow(it, repeatWhy) {") + _fn("function dailyChangeRows(items) {")
    out = subprocess.run([exe, "-e", prelude + script], capture_output=True, text=True,
                         timeout=60, cwd=str(ROOT))
    assert "RESULT:" in out.stdout, (out.stdout + out.stderr)[-2000:]
    return json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])


def test_a_returning_reader_sees_their_own_names():
    fn = _fn("function renderHome() {")
    assert "const recent = recentSymbols();" in fn
    assert "const picks = recent.length ? recent : HOME_QUICK_PICKS;" in fn
    assert "recent.length ? 'Recent' : 'Or jump to'" in fn
    assert '<span class="label">${quickLabel}</span>' in fn
    # A stored symbol is markup on the way out, like any other string.
    assert 'data-pick="${esc(t)}">${esc(t)}</button>' in fn


def test_an_explanation_shared_by_several_changes_is_said_once():
    why = "A rule's trigger on a completed candle. It is for review, not an order."
    out = _run("""
      var items = [
        { symbol: 'AMD', headline: 'AMD A setup triggered', why: %(w)s, link: { view: 'swing' } },
        { symbol: 'QQQ', headline: 'QQQ 2 setups triggered', why: %(w)s, link: { view: 'swing' } },
        { symbol: 'AMD', headline: 'AMD Closed at a 52-week high', why: 'No overhead level.',
          link: { view: 'chart' } },
        { symbol: 'SPY', headline: 'SPY 3 setups triggered', why: %(w)s, link: { view: 'swing' } },
      ];
      var html = dailyChangeRows(items);
      print('RESULT:' + JSON.stringify({ html: html }));
    """ % {"w": json.dumps(why)})
    html = out["html"]
    assert html.count("for review, not an order") == 1
    assert html.count("No overhead level.") == 1
    assert html.count('class="dc-item') == 4, "every change is still listed"


def _reader_strings(path):
    """String constants in a module, less its docstrings."""
    tree = ast.parse(path.read_text())
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                docs.add(id(body[0].value))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs:
            yield node.lineno, node.value


def test_the_server_writes_no_em_dash_into_a_sentence():
    """The house rule is no em dashes in reader-facing copy, and the pass that
    enforced it read static/ only. A bare dash standing for a missing figure is
    a table's placeholder, not copy; a regex character class is not copy; and
    feeds.py's notes on rejected feeds are the operator's, never rendered."""
    found = []
    for path in sorted((ROOT / "app").rglob("*.py")):
        if path.name == "feeds.py":
            continue
        for line, text in _reader_strings(path):
            if "—" not in text or text.strip() == "—":
                continue
            if "[" in text and "\\s" in text:      # a pattern, not a sentence
                continue
            found.append(f"{path.relative_to(ROOT)}:{line}: {text.strip()[:70]}")
    assert not found, "\n".join(found)


def test_the_pe_bands_quote_cheap_with_quote_marks():
    """`\\\\u201c` in a plain string is a backslash and five letters, so the
    method note read `so \\u201ccheap\\u201d means cheap against itself`."""
    src = (ROOT / "app/analytics/pe_history.py").read_text()
    assert "\\\\u201c" not in src and "\\\\u201d" not in src


# ------------------------------------------------- the market strip and the band


def test_a_yield_moves_in_basis_points():
    """The 10-year read "-0.79%", a percent of the rate, for a move of about
    four hundredths of a point."""
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = """
      function fmtPct(v, d) { return (v >= 0 ? '+' : '') + Number(v).toFixed(d) + '%'; }
    """ + _fn("function moveLabel(inst) {") + """
      print('RESULT:' + JSON.stringify([
        moveLabel({ group: 'rates', last: 5.27, chg_1d: -0.79 }),
        moveLabel({ group: 'rates', last: 4.10, chg_1d: 1.24 }),
        moveLabel({ group: 'rates', last: 4.10, chg_1d: 0 }),
        moveLabel({ group: 'equity', last: 7878, chg_1d: 0.66 }),
        moveLabel({ group: 'rates', last: 4.1, chg_1d: null })]));
    """
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=30)
    got = json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])
    assert got == ["−4 bp", "+5 bp", "0 bp", "+0.66%", None]


def test_the_strip_says_when_it_was_read():
    fn = _fn("function marketStripHTML(data) {")
    assert 'class="ms-asof">As of' in fn and "data.generated_at" in fn
    assert "esc(moveLabel(inst))" in fn
    assert "esc(moveLabel(inst))" in _fn("function whatMattersNow(data) {")


def test_a_holiday_is_named_on_the_week_strip():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from app import priority
    days = priority._closed_days(datetime(2026, 11, 23, 10, tzinfo=ZoneInfo("America/New_York")))
    assert days == {"2026-11-26": "Thanksgiving Day"}
    fn = _fn("function catalystPlacement(p, nowIso) {")
    assert "closed_days" in fn
    assert "Market closed: ${esc(x.closed)}" in _fn("function catalystStripHTML(p, nowIso) {")


def test_a_report_is_high_impact_only_when_it_moves_the_index():
    src = (ROOT / "app/priority.py").read_text()
    assert '"impact": "high" if symbol in MAJORS else "medium",' in src
    assert "Watchlist names reporting" not in src


def test_the_strip_explains_its_two_cues():
    fn = _fn("function catalystStripHTML(p, nowIso) {")
    assert 'class="cs-key"' in fn and "High impact" in fn and "Company report" in fn


def test_the_today_band_goes_stale_and_says_when_it_is_from():
    fn = _fn("async function loadHomeToday() {")
    assert "HOME_TODAY_TTL_MS" in fn and "STATE.priorityDay !== etDay()" in fn
    assert "loadHomeToday();" in _fn("async function tickAutoRefresh() {") \
        if "async function tickAutoRefresh() {" in APP else "loadHomeToday();" in APP
    assert "as of ${esc(timeIn(p.generated_at, activeZone()))}" in _fn("function homeTodayHTML(p) {")


def test_the_pulse_inputs_fill_out_from_a_middle_line():
    """(score + 100) / 2 drew a score of 0 as a half-full bar, and -7 for
    Macro as "about half good"."""
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = _fn("function pulseBar(score, direction) {") + """
      function cells(html) {
        var parts = html.split('<i class="pl-mid"></i>');
        var on = function (s) { return (s.match(/pl-cell on/g) || []).length; };
        return [on(parts[0]), on(parts[1])];
      }
      print('RESULT:' + JSON.stringify([cells(pulseBar(0, 'flat')), cells(pulseBar(50, 'up')),
        cells(pulseBar(-75, 'down')), cells(pulseBar(100, 'up')), pulseBar(null).indexOf('is-none') >= 0]));
    """
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=30)
    got = json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])
    assert got == [[0, 0], [0, 3], [4, 0], [0, 5], True]
    hero = _fn("function renderOpticPulse(d) {")
    assert "pulseBar(f.unavailable ? null : f.score, f.direction)" in hero
    assert "from -100 to +100" in hero
