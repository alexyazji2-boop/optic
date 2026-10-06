"""Signal history on the page: the account's, or a guest's kept in the browser.

The server side is tests/test_signal_history.py. These hold the page to the
same rules: a record kept exactly as it came and never twice, what followed
appended once each with one verdict per signal, and a horizon nothing was
observed for shown as unknown or not yet, never as a number. And the account
endpoint, driven through TestClient with two real sign-ins, serves each reader
only their own.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app import signal_history
from app.auth import config, store

ROOT = Path(__file__).resolve().parent.parent
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"

RECORD = {
    "signal_key": "X|trend_pullback|bull|2026-09-01", "symbol": "X", "strategy": "trend_pullback",
    "strategy_label": "Trend pullback", "direction": "bull", "timeframe": "daily",
    "trigger_at": "2026-09-01", "trigger_completed_at": "2026-09-01T16:00:00-04:00",
    "data_as_of": "2026-09-01", "trigger_price": 100.0, "trigger_level": 99.5,
    "invalidation": 95.0, "target": None,
    "conditions": {"checks": [{"group": "Trend", "rule": "Close above the 50-day", "passed": True,
                               "required": True, "value": "101.2 > 97.0"}], "met": 1, "of": 1},
    "indicators": {"RSI 14": 48.1}, "explanation": "Pulled back to the 20-day and closed back above it.",
    "source": "Yahoo Finance daily candles", "rule_version": "setups-2026-10-06.1",
    "params": {"signal_ttl": 10}, "assumptions": ["Rules read completed candles only."],
}


def _run(script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = """
      load('tests/support/browser_stubs.js');
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
      var MEM = {};
      localStorage.getItem = function (k) { return Object.prototype.hasOwnProperty.call(MEM, k) ? MEM[k] : null; };
      localStorage.setItem = function (k, v) { MEM[k] = String(v); };
      var R = {};
      var REC = %s;
    """ % json.dumps(RECORD) + script + "\nprint('RESULT:' + JSON.stringify(R));"
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=120, cwd=str(ROOT))
    blob = out.stdout + out.stderr
    assert "RESULT:" in blob, blob[-2000:]
    return json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])


# ================================================================ a guest's

def test_a_guest_record_is_kept_once_and_as_it_came():
    out = _run("""
      R.first = keepLocalSignal(REC);
      R.again = keepLocalSignal(Object.assign({}, REC, {trigger_price: 1}));
      var kept = JSON.parse(MEM['optic.signals.v1']).signals;
      R.n = kept.length; R.price = kept[0].trigger_price; R.origin = kept[0].origin;
      R.stamped = !!kept[0].recorded_at;
    """)
    assert out["first"] is True and out["again"] is False
    assert out["n"] == 1 and out["price"] == 100.0, "the second sighting does not rewrite the first"
    assert out["origin"] == "alert check on the page" and out["stamped"]


def test_what_followed_is_appended_once_with_one_verdict():
    out = _run("""
      keepLocalSignal(REC);
      var store = readLocalSignals(), key = REC.signal_key;
      addLocalSignalEvents(store, key, [
        {kind: 'status', label: 'expired', data_as_of: '2026-09-15', price: 101},
        {kind: 'observation', label: 'after 1 candle', data_as_of: '2026-09-02', price: 101, change_pct: 1.0}]);
      addLocalSignalEvents(store, key, [
        {kind: 'status', label: 'invalidated', data_as_of: '2026-09-03', price: 90},
        {kind: 'observation', label: 'after 1 candle', data_as_of: '2026-09-02', price: 77, change_pct: -23.0}]);
      writeLocalSignals(store);
      var row = localSignalRows()[0];
      R.status = row.status;
      R.statuses = row.events.filter(function (e) { return e.kind === 'status'; }).length;
      R.first = row.horizons[0];
      R.observedAt = row.events.every(function (e) { return !!e.observed_at; });
    """)
    assert out["status"] == "expired" and out["statuses"] == 1
    assert out["first"]["state"] == "observed" and out["first"]["change_pct"] == 1.0
    assert out["observedAt"]


def test_unobserved_horizons_are_words_not_numbers():
    out = _run("""
      keepLocalSignal(REC);
      var store = readLocalSignals();
      addLocalSignalEvents(store, REC.signal_key, [
        {kind: 'observation', label: 'after 1 candle', data_as_of: '2026-09-02', price: 101.5, change_pct: 1.5}]);
      writeLocalSignals(store);
      SIGNALS.followed = {}; SIGNALS.followed[REC.signal_key] = [
        {horizon: 1, state: 'observed'}, {horizon: 5, state: 'missing'},
        {horizon: 10, state: 'pending'}, {horizon: 20, state: 'pending'}];
      var rows = localSignalRows();
      R.states = rows[0].horizons.map(function (h) { return h.state; });
      SIGNALS.data = {signals: rows, basis: 'Not an options return.', where: 'browser'};
      SIGNALS.options = signalOptions(rows);
      var html = renderSignalHistory();
      R.html = html;
      SIGNALS.followed = null;
      R.before = localSignalRows()[0].horizons.map(function (h) { return h.state; });
    """)
    assert out["states"] == ["observed", "missing", "pending", "pending"]
    html = out["html"]
    assert "+1.5%" in html
    assert html.count(">+5</span> unknown") == 1 and html.count("not yet") == 2
    assert "0.0%" not in html and "+0" not in html.replace("+0.", "")
    assert out["before"] == ["observed", "unknown", "unknown", "unknown"], \
        "before any follow-up answers, what is not recorded is unknown"
    assert "Kept in this browser" in html and "Not an options return." in html


def test_the_record_shows_what_it_was_built_from():
    out = _run("""
      var row = Object.assign({}, REC, {events: [], status: 'unresolved', recorded_at: '2026-09-01T20:31:00Z',
        origin: 'scheduled alert check', horizons: [1, 5, 10, 20].map(function (h) { return {horizon: h, state: 'pending'}; })});
      R.html = signalHistoryDetail(row);
      R.line = signalHistoryRow(row);
    """)
    html = out["html"]
    assert "Sep 1, 2026, closed 4:00 PM EDT" in html, "the candle's own day, then its close"
    for want in ("Trigger candle", "Data read through",
                 "None: this rule sets no target", "setups-2026-10-06.1", "Yahoo Finance daily candles",
                 "by the scheduled alert check", "Close above the 50-day", "RSI", "48.1",
                 "Rules read completed candles only.", "Nothing observed yet"):
        assert want in html, want
    assert "Bullish" in out["line"] and "Open" in out["line"] and "Trend pullback" in out["line"]


def test_a_guest_filter_narrows_the_rows_and_says_when_none_match():
    out = _run("""
      keepLocalSignal(REC);
      keepLocalSignal(Object.assign({}, REC, {signal_key: 'Y|b', symbol: 'Y', direction: 'bear', trigger_at: '2026-09-02'}));
      var rows = localSignalRows();
      SIGNALS.data = {signals: rows, basis: '', where: 'browser'};
      SIGNALS.options = signalOptions(rows);
      SIGNALS.direction = 'bear';
      R.shown = signalRowsShown().map(function (s) { return s.symbol; });
      SIGNALS.direction = 'all'; SIGNALS.status = 'invalidated';
      R.none = renderSignalHistory();
      R.symbols = SIGNALS.options.symbols;
    """)
    assert out["shown"] == ["Y"]
    assert "None of your signals matches this filter." in out["none"] and "data-sig-reset" in out["none"]
    assert out["symbols"] == ["X", "Y"]


def test_the_account_filter_is_asked_of_the_server():
    out = _run("""
      SIGNALS.status = 'invalidated'; SIGNALS.direction = 'bear'; SIGNALS.symbol = 'NVDA';
      R.url = signalQuery();
      SIGNALS.status = 'all'; SIGNALS.direction = 'all'; SIGNALS.symbol = '';
      R.plain = signalQuery();
    """)
    assert out["url"] == "/api/signals?status=invalidated&direction=bear&symbol=NVDA"
    assert out["plain"] == "/api/signals"


def test_the_store_is_a_personal_key():
    app = (ROOT / "static/app.js").read_text(encoding="utf-8")
    keys = app[app.index("const PERSONAL_KEYS = ["):app.index("];", app.index("const PERSONAL_KEYS = ["))]
    assert "'optic.signals.v1'" in keys


# ================================================================ the account's

client = TestClient(main.app)
GOOD = "tungsten-carbide-9"


@pytest.fixture(autouse=True)
def fresh(accounts):
    client.cookies.clear()
    return accounts


def register(email):
    client.cookies.clear()
    client.post("/api/auth/register", json={
        "first_name": "Test", "last_name": "Reader", "email": email,
        "password": GOOD, "confirm_password": GOOD})
    assert client.cookies.get(config.CSRF_COOKIE)
    return store.get_user_by_email(email)


def test_each_reader_is_served_only_their_own_signals():
    a = register("a@example.com")
    b = register("b@example.com")
    signal_history.record(a["id"], dict(RECORD), "scheduled alert check")
    signal_history.record(b["id"], dict(RECORD, signal_key="other", symbol="Y"), "scheduled alert check")
    reply = client.get("/api/signals")                 # signed in as b
    assert reply.status_code == 200
    assert [s["symbol"] for s in reply.json()["signals"]] == ["Y"]
    assert "not an options return" in reply.json()["basis"]
    client.cookies.clear()
    assert client.get("/api/signals").status_code == 401


def test_the_status_filter_reaches_the_query():
    a = register("a@example.com")
    signal_history.record(a["id"], dict(RECORD), "scheduled alert check")
    sig = signal_history.history(a["id"])[0]
    signal_history.add_event(sig, "status", "invalidated", "2026-09-03", 94.0)
    assert len(client.get("/api/signals?status=invalidated").json()["signals"]) == 1
    assert client.get("/api/signals?status=unresolved").json()["signals"] == []
