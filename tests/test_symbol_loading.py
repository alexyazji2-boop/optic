"""Loading a symbol: one that does not exist, one that is slow, which close.

Measured on 2026-10-06 against the local server:
- `#/ZZZZQ` showed "Could not load. No price data found for 'ZZZZQ'." with Try
  again, under a header still reading "Loading price" over seven section tabs
  and a Watch button, and ZZZZQ went into the recent symbols Home offers back.
- With Yahoo rate-limiting the machine, a first load ran 31s under a sentence
  promising "several seconds".
- MSFT's header read "MSFT MSFT 529.30" when the feed named it by its symbol.
- "At the close" on a Monday morning did not say it was Friday's.

Checked in a browser at 1440x900: `#/APPL` showed "No symbol called APPL" with
AAPL, AMAT, APP, AAOI and APLD offered, no tabs and no actions; pressing AAPL
opened Apple's Overview at `#/AAPL` with all seven sections.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app import session as S

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
ET = ZoneInfo("America/New_York")


def _fn(head):
    at = APP.index(head)
    return APP[at:APP.index("\n}\n", at) + 3]


def _run(prelude, names, script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = prelude + "\n".join(_fn(n) for n in names) + script
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    assert "RESULT:" in out.stdout, (out.stdout + out.stderr)[-2000:]
    return json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])


PRELUDE = """
  var STATE = { ticker: 'ZZZZQ', swing: null, session: null, loadFailed: null };
  const SYMBOL_MISSING = new Set();
  const RECENT_KEY = 'optic.recent.v1';
  var store = { 'optic.recent.v1': JSON.stringify(['ZZZZQ', 'MSFT']) };
  var localStorage = { getItem: function (k) { return store[k] || null; },
                       setItem: function (k, v) { store[k] = v; } };
  function esc(s) { return String(s); }
  function errorHTML(m) { return 'ERROR ' + m; }
"""
NAMES = ["function symbolMissing(sym) {", "function noteTickerFailure(err, ticker) {",
         "function tickerErrorHTML(err, ticker) {", "function recentSymbols() {",
         "function forgetSymbol(symbol) {"]


def test_a_404_is_a_missing_symbol_and_leaves_the_recent_list():
    out = _run(PRELUDE, NAMES, """
      var e = new Error("No price data found for 'ZZZZQ'."); e.status = 404;
      noteTickerFailure(e, 'ZZZZQ');
      var html = tickerErrorHTML(e, 'ZZZZQ');
      print('RESULT:' + JSON.stringify({ missing: symbolMissing('zzzzq'), failed: STATE.loadFailed,
        recent: recentSymbols(), html: html }));
    """)
    assert out["missing"] is True and out["failed"] == "ZZZZQ"
    assert out["recent"] == ["MSFT"], "the name it could not find is not offered back"
    html = out["html"]
    assert "No symbol called ZZZZQ" in html and "data-open-palette" in html
    assert 'data-sym-suggest="ZZZZQ"' in html
    assert "ERROR" not in html and "Try again" not in html, "a retry cannot find a name that is not there"


def test_any_other_failure_stays_a_failure_with_its_retry():
    out = _run(PRELUDE, NAMES, """
      var e = new Error('the connection dropped after 4 attempts');
      noteTickerFailure(e, 'ZZZZQ');
      print('RESULT:' + JSON.stringify({ missing: symbolMissing('ZZZZQ'), failed: STATE.loadFailed,
        recent: recentSymbols(), html: tickerErrorHTML(e, 'ZZZZQ') }));
    """)
    assert out["missing"] is False and out["failed"] == "ZZZZQ"
    assert out["recent"] == ["ZZZZQ", "MSFT"]
    assert out["html"].startswith("ERROR the connection dropped")


def test_a_failed_refresh_over_a_loaded_dossier_changes_nothing():
    out = _run(PRELUDE, NAMES, """
      STATE.swing = { ticker: 'ZZZZQ' };
      var e = new Error('gone'); e.status = 404;
      noteTickerFailure(e, 'ZZZZQ');
      print('RESULT:' + JSON.stringify({ missing: symbolMissing('ZZZZQ'), failed: STATE.loadFailed }));
    """)
    assert out == {"missing": False, "failed": None}


def test_the_status_rides_on_the_error():
    fn = _fn("async function getJSON(url) {")
    assert "answered.status = res.status;" in fn and "refused.status = res.status;" in fn


def test_the_header_for_a_missing_symbol_has_no_sections_and_no_actions():
    fn = _fn("function securityHeader(view, opts = {}) {")
    missing = fn.split("if (symbolMissing(sym)) {", 1)[1].split("\n  }\n", 1)[0]
    assert "Not found" in missing
    assert "sec-tabs" not in missing and "secActionsHTML" not in missing
    assert "'Price unavailable'" in fn, "a failed load does not say Loading forever"
    assert "String(q.name).trim().toUpperCase() !== sym.toUpperCase()" in fn


def test_searching_it_again_asks_the_feed_again():
    fn = _fn("function loadTicker(raw, destination) {")
    assert "SYMBOL_MISSING.delete(next);" in fn
    assert "if (STATE.loadFailed === next) STATE.loadFailed = null;" in fn


def test_every_place_a_load_fails_renders_through_the_same_function():
    for head in ("async function loadSwing(force, opts = {}) {",
                 "async function loadSecurityFacet(view, force, opts = {}) {"):
        fn = _fn(head)
        assert "tickerErrorHTML(" in fn and "fillSymbolSuggestions(" in fn, head
        assert "errorHTML(err.message" not in fn and "errorHTML(outcome.error.message" not in fn, head
    assert "noteTickerFailure(err, ticker);" in _fn("async function loadSwing(force, opts = {}) {")


def test_the_suggestions_are_buttons_the_pick_handler_already_answers():
    fn = _fn("async function fillSymbolSuggestions(host) {")
    assert "/api/search?q=" in fn and 'data-pick="${esc(r.symbol)}"' in fn
    assert "r.symbol !== typed" in fn and "box.isConnected" in fn
    assert "const pick = evt.target.closest('[data-pick]');" in APP


def test_a_slow_first_load_says_it_is_slow():
    fn = _fn("async function loadSecurityFacet(view, force, opts = {}) {")
    assert "secs >= 15" in fn and "Taking longer than usual" in fn


# ------------------------------------------------------------- which close


@pytest.mark.parametrize("now, day, weekday", [
    ("2026-10-06T23:55", "2026-10-06", "Tuesday"),     # after hours: today's
    ("2026-10-10T12:00", "2026-10-09", "Friday"),      # Saturday: Friday's
    ("2026-10-12T07:00", "2026-10-09", "Friday"),      # Monday pre-market
    ("2026-09-07T10:00", "2026-09-04", "Friday"),      # Labor Day: the Friday before
    ("2026-10-06T10:00", "2026-10-05", "Monday"),      # mid-session: yesterday's
])
def test_the_session_names_the_close_a_price_belongs_to(now, day, weekday):
    lc = S.state(datetime.fromisoformat(now).replace(tzinfo=ET))["last_close"]
    assert lc["date"] == day and lc["weekday"] == weekday


def test_a_half_day_closes_at_one():
    lc = S.state(datetime(2026, 11, 27, 14, 0, tzinfo=ET))["last_close"]
    assert lc["at"].startswith("2026-11-27T13:00")


def test_the_header_says_which_close():
    out = _run("var STATE = { session: null };\n", ["function closeLabel() {"], """
      var rows = [];
      function at(now, lc) { STATE.session = { session: { now_et: now, last_close: lc } };
        rows.push(closeLabel()); }
      at('2026-10-06T23:55:00-04:00', { date: '2026-10-06', weekday: 'Tuesday', label: 'Oct 6' });
      at('2026-10-12T07:00:00-04:00', { date: '2026-10-09', weekday: 'Friday', label: 'Oct 9' });
      at('2026-10-20T07:00:00-04:00', { date: '2026-10-09', weekday: 'Friday', label: 'Oct 9' });
      STATE.session = null; rows.push(closeLabel());
      print('RESULT:' + JSON.stringify(rows));
    """)
    assert out == ["At today's close", "At Friday's close", "At the Oct 9 close", "At the close"]


def test_the_sections_are_one_tab_stop_and_the_arrows_move_along_them():
    """Seven separate Tab stops before Watch, and the arrow keys the tab role
    promises did nothing. Checked in a browser: from Overview, ArrowRight
    focused Chart, End focused News, ArrowRight wrapped to Overview, and the
    page stayed on Overview throughout."""
    fn = _fn("function securityHeader(view, opts = {}) {")
    assert 'tabindex="${on ? 0 : -1}"' in fn
    block = APP.split("/* The Dossier's sections are a tab list, and a tab list is one Tab stop.", 1)[1]
    block = block[:block.index("\n});")]
    assert "ArrowRight: at + 1, ArrowLeft: at - 1, Home: 0, End: tabs.length - 1" in block
    assert "next.focus();" in block
    assert "switchView" not in block and ".click()" not in block, "focus moves, it does not open"
