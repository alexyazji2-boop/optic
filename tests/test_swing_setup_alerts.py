"""Swing setups from the scanner to the chart to the alert.

The engine has its own tests (tests/test_swing_setups.py). These cover what is
built on it: the endpoints the Options tab reads, the watch that turns a
trigger into an alert through the inbox the app already has, the runner that
stores it once, and the panel that shows it.

"Deduplicate alerts and use existing notification infrastructure": a trigger
stays fresh for three candles, and the watch runner's own dedupe is one hit
per watch per day, which would have stored the same trigger three times. A
setup watch names its trigger instead, and that is what is asserted here.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import db, main, watch_runner
from app.analytics import setups as S
from app.analytics import watches as watches_mod

from tests.test_swing_setups import _pullback_df, after, frame, walk

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text(encoding="utf-8")
CSS = (ROOT / "static/styles.css").read_text(encoding="utf-8")


def fresh_result():
    df = _pullback_df()
    return S.analyse("X", df, None, presets=["trend_pullback"], directions=["bull"],
                     overrides={"*": {"htf_filter": False}}, now=after(df))


# ================================================================= the watch

def test_the_watch_offers_exactly_the_presets_and_any():
    spec = watches_mod.CONDITIONS["swing_setup"]["param"]
    values = [c["value"] for c in spec["choices"]]
    assert values == ["any"] + [p["id"] for p in S.PRESETS]
    # account.py stores a choice lowercased and cut at 32 characters, and
    # refuses one that is not on the list: every id has to survive that.
    assert all(v == v.lower()[:32] for v in values)


def test_a_fresh_trigger_fires_once_named_by_its_own_key():
    result = fresh_result()
    hit = watches_mod.EVALUATORS["swing_setup"]({"setups": result}, {"preset": "any"})
    assert hit is not None
    assert hit["state"] == hit["dedupe"] == "setup:X:trend_pullback:bull:daily:" + result["as_of"]
    assert "None" not in hit["evidence"] and "21 EMA" in hit["evidence"]
    assert watches_mod.EVALUATORS["swing_setup"]({"setups": result}, {"preset": "donchian_20"}) is None


def test_a_stale_trigger_is_not_news():
    result = fresh_result()
    later = dict(result, recent_stamps=result["recent_stamps"] + ["a", "b", "c"], as_of="c")
    assert watches_mod.EVALUATORS["swing_setup"]({"setups": later}, {"preset": "any"}) is None


def test_no_setups_on_the_payload_is_silence_not_an_error():
    assert watches_mod.EVALUATORS["swing_setup"]({}, {"preset": "any"}) is None
    assert watches_mod.EVALUATORS["swing_setup"](
        {"setups": {"available": False, "rows": []}}, {"preset": "any"}) is None


@pytest.fixture()
def account(accounts):
    uid = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    db.execute("INSERT INTO users (id, email, created_at, updated_at) VALUES (?,?,?,?)",
               (uid, "s@example.com", now, now))
    return uid


def _watch(uid, symbol, preset="any"):
    wid = uuid.uuid4().hex
    db.execute("INSERT INTO watches (id, user_id, symbol, kind, params, note, active, created_at) "
               "VALUES (?,?,?,?,?,?,1,?)",
               (wid, uid, symbol, "swing_setup", json.dumps({"preset": preset}), None,
                datetime.now(timezone.utc).isoformat()))
    return wid


def test_the_runner_stores_a_trigger_once_however_many_days_it_stays_fresh(account):
    _watch(account, "X")
    result = fresh_result()
    snap = lambda symbol: {"setups": result}
    assert watch_runner.run_once(snap)["hits"] == 1
    assert watch_runner.run_once(snap)["hits"] == 0
    # A day later the same trigger is still fresh, and still the same hit.
    row = {"id": watch_runner.due_watches()[0]["id"], "user_id": account, "symbol": "X",
           "kind": "swing_setup", "note": None}
    hit = watches_mod.EVALUATORS["swing_setup"]({"setups": result}, {"preset": "any"})
    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    assert watch_runner.record_hit(row, {**hit, "label": "A swing setup triggers"}, tomorrow) is False
    assert len(watch_runner.hits_for(account)) == 1
    # A different trigger is a different hit.
    other = {**hit, "dedupe": hit["dedupe"] + "-next", "label": "A swing setup triggers"}
    assert watch_runner.record_hit(row, other, tomorrow) is True


def test_every_other_watch_still_dedupes_by_day():
    when = datetime(2026, 10, 5, 15, tzinfo=timezone.utc)
    assert watch_runner._dedupe_key("w", when) == "w:2026-10-05"
    assert watch_runner._dedupe_key("w", when, "setup:X") == "w:setup:X"


def test_the_snapshots_carry_the_setups_the_watch_reads():
    """Both the scheduled runner and the browser's check build what the
    evaluator reads. Missing from either, a setup watch would never fire there
    and nothing would say why."""
    src = (ROOT / "app/main.py").read_text(encoding="utf-8")
    snap = src[src.index("def _watch_snapshot("):src.index("def _attach_setups(")]
    assert "_attach_setups(payload, symbol)" in snap
    check = src[src.index('@app.post("/api/watches/check")'):]
    check = check[:check.index("\n@app.")]
    assert '"swing_setup"' in check and "_attach_setups(payload, ticker)" in check


# ============================================================== the endpoints

@pytest.fixture()
def feed(monkeypatch):
    """The batch download, faked: two symbols and the benchmark, no network."""
    frames = {"AAA": _pullback_df(), "BBB": walk(400, seed=31), "SPY": walk(400, seed=8, drift=0.05)}
    calls = []

    def batch(tickers, period="1y", interval="1d"):
        calls.append((tuple(tickers), period))
        return {t: frames[t] for t in tickers if t in frames}

    monkeypatch.setattr(main.YF_PROVIDER, "batch_history", batch)
    main._SETUP_CACHE.clear()
    return calls


def test_one_download_for_the_whole_scan(feed):
    res = TestClient(main.app).get("/api/setups?symbols=AAA,BBB&status=all")
    assert res.status_code == 200, res.text
    assert len(feed) == 1 and set(feed[0][0]) == {"AAA", "BBB", "SPY"}
    body = res.json()
    assert body["benchmark"] == "SPY" and body["failed"] == []
    assert len(body["rows"]) == 2 * 2 * len(S.PRESETS)


def test_scan_rows_are_compact_and_counted(feed):
    body = TestClient(main.app).get("/api/setups?symbols=AAA,BBB").json()
    assert body["status"] == "recent"
    assert all(r["status"] in ("armed", "triggered", "invalidated", "expired") for r in body["rows"])
    assert all("checks" not in r and "values" not in r for r in body["rows"])
    every = sum(sum(c.values()) for c in body["counts"].values())
    assert every == 2 * 2 * len(S.PRESETS), "the counts cover what the filter left out"


def test_the_scan_says_which_symbols_had_no_candles(feed):
    body = TestClient(main.app).get("/api/setups?symbols=AAA,ZZZ").json()
    assert body["failed"] == ["ZZZ"]


@pytest.mark.parametrize("query,needle", [
    ("symbols=", "at least one symbol"),
    ("symbols=AAA,BBB&timeframe=4h", "one symbol at a time"),
    ("symbols=AAA&timeframe=1h", "daily or 4h"),
    ("symbols=AAA&direction=up", "both, bull or bear"),
    ("symbols=AAA&status=open", "Unknown status"),
    ("symbols=AAA&params=nope", "JSON"),
])
def test_bad_requests_are_refused_in_words(feed, query, needle):
    res = TestClient(main.app).get("/api/setups?" + query)
    assert res.status_code == 400 and needle in res.json()["detail"]


def test_reader_parameters_reach_the_rules(feed):
    p = json.dumps({"donchian_20": {"channel": 5}, "*": {"htf_filter": False}})
    body = TestClient(main.app).get(
        "/api/setups?symbols=BBB&presets=donchian_20&direction=bull&status=all&params=" + p).json()
    assert [r["preset"] for r in body["rows"]] == ["donchian_20"]
    assert "5-bar" in body["rows"][0]["explanation"] or body["rows"][0]["status"] in ("watching", "armed")


def test_the_detail_is_the_scan_row_plus_its_chart_and_history(feed):
    client = TestClient(main.app)
    scan = client.get("/api/setups?symbols=AAA&presets=trend_pullback&direction=bull&status=all"
                      "&params=" + json.dumps({"*": {"htf_filter": False}})).json()
    detail = client.get("/api/setups/AAA/detail?preset=trend_pullback&direction=bull&params="
                        + json.dumps({"*": {"htf_filter": False}})).json()
    row = scan["rows"][0]
    assert detail["row"]["status"] == row["status"] == "triggered"
    assert detail["row"]["trigger"] == row["trigger"]
    assert detail["row"]["checks"], "the detail carries the rule checks the scan leaves out"
    chart = detail["chart"]
    assert len(chart["stamps"]) == len(chart["close"]) <= 120
    assert any(m["type"] == "triggered" for m in chart["marks"])
    assert detail["history"]["available"] is True
    assert "not options returns" in detail["history"]["caveat"]


def test_the_options_view_lists_without_ranking(monkeypatch):
    chain = pd.DataFrame([{
        "contract": "AAA261120C00100000", "strike": 100.0, "last": 2.0, "bid": 2.0, "ask": 2.1,
        "volume": 50.0, "open_interest": 500.0, "iv": 0.3, "iv_filled": False, "in_the_money": False,
        "is_call": True, "expiry": "2026-11-20", "dte": 46, "tau": 46 / 365.0, "mid": 2.05,
        "spread_pct": 4.9, "last_trade": pd.Timestamp("2026-10-05T19:59:00Z"),
        "fetched_at": "2026-10-05T20:10:00+00:00"}])
    monkeypatch.setattr(main.PROVIDER, "quote", lambda sym: {"price": 101.0})
    monkeypatch.setattr(main.PROVIDER, "options_chain", lambda sym, **kw: chain)
    monkeypatch.setattr(main.YF_PROVIDER, "earnings_date", lambda sym: None)
    res = TestClient(main.app).get("/api/setups/AAA/options?direction=bull&budget=500")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["passed"] == 1 and body["contracts"][0]["cost_for_one"] == 205
    assert body["filters"]["budget"] == 500
    assert "Not ranked" in body["order"]
    assert any("delayed" in n for n in body["notes"])


def test_the_catalogue_is_served():
    body = TestClient(main.app).get("/api/setups/catalogue").json()
    assert {p["id"] for p in body["presets"]} == set(S.PRESET_BY_ID)


# ================================================================== the panel

JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _run(script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = """
      load('tests/support/browser_stubs.js');
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
      var R = {};
      STATE.ticker = 'AAA';
      isTapeLiveET = function () { return false; };
      watchAllLists = function () { return [{id: 'w1', name: 'Main', symbols: ['AAA', 'BBB']}]; };
    """ + script + "\nprint('RESULT:' + JSON.stringify(R));"
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=120, cwd=str(ROOT))
    blob = out.stdout + out.stderr
    assert "RESULT:" in blob, blob[-2000:]
    return json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])


ROWS = """
  SETUPS.catalogue = {presets: [{id: 'donchian_20', label: 'Donchian 20-bar breakout', family: 'donchian',
    kind: 'continuation', experimental: false, rules: {bull: 'b', bear: 'r'}, params: [], context: []}],
    families: ['donchian'], states: []};
  SETUPS.data = {timeframe: 'daily', as_of: {AAA: '2026-10-05'}, forming: null, failed: [], counts: {AAA: {triggered: 1, watching: 3}},
    method: 'Completed candles only.', rows: [
    {symbol: 'AAA', preset: 'donchian_20', label: 'Donchian 20-bar breakout', family: 'donchian',
     kind: 'continuation', experimental: false, direction: 'bull', timeframe: 'daily',
     status: 'triggered', status_at: '2026-10-05', armed_at: '2026-10-02',
     trigger: {stamp: '2026-10-05', close: 238.9, level: 237.88}, trigger_level: 237.88,
     invalidation: 219.61, explanation: 'Daily candle Oct 5: Price closed above the 20-bar high.',
     provisional: null, key: 'setup:AAA:donchian_20:bull:daily:2026-10-05', conditions: {met: 3, of: 3}}]};
"""


def test_a_row_shows_the_essentials_and_nothing_else():
    out = _run(ROWS + """
      var html = renderSetupsBody();
      R.symbol = html.indexOf('>AAA<') >= 0;
      R.status = html.indexOf('is-triggered') >= 0;
      R.levels = html.indexOf('237.88') >= 0 && html.indexOf('219.61') >= 0;
      R.when = html.indexOf('Oct 5 close') >= 0;
      R.why = html.indexOf('closed above the 20-bar high') >= 0;
      R.noChecks = html.indexOf('conditions met') < 0;
      R.filters = (html.match(/data-ss-filter="/g) || []).length;
      R.counts = html.indexOf('1 triggered') >= 0 && html.indexOf('3 watching') >= 0;
    """)
    assert out["symbol"] and out["status"] and out["levels"] and out["when"] and out["why"]
    assert out["noChecks"], "rule checks wait for the row to be opened"
    assert out["filters"] == 5, "symbol or watchlist, direction, timeframe, strategy, status"
    assert out["counts"]


def test_four_hour_timing_is_offered_for_one_symbol_only():
    out = _run(ROWS + """
      var one = renderSetupsFilters({scope: 'symbol', direction: 'both', timeframe: 'daily', family: '', status: 'recent'});
      var many = renderSetupsFilters({scope: 'list:w1', direction: 'both', timeframe: '4h', family: '', status: 'recent'});
      R.oneOk = /<option value="4h"(?![^>]*disabled)/.test(one);
      R.manyOff = /<option value="4h"[^>]*disabled/.test(many);
      R.url = setupsUrl({scope: 'list:w1', direction: 'both', timeframe: '4h', family: '', status: 'recent'});
    """)
    assert out["oneOk"] and out["manyOff"]
    assert "timeframe=daily" in out["url"] and "symbols=AAA%2CBBB" in out["url"]


def test_a_provisional_reading_is_marked_as_one():
    out = _run(ROWS + """
      SETUPS.data.rows[0].provisional = {event: 'triggered', text: 'Provisional: would trigger if the candle closed at 240.'};
      var html = renderSetupsBody();
      R.tag = html.indexOf('ss-prov') >= 0 && html.indexOf('provisional: triggered') >= 0;
    """)
    assert out["tag"]


def test_the_open_row_draws_the_setup_on_its_chart():
    out = _run(ROWS + """
      var key = setupRowKey(SETUPS.data.rows[0]);
      SETUPS.open[key] = true;
      SETUPS.details[key] = {at: '1', data: {
        rules: 'A completed close above the highest high of the preceding 20 bars.',
        row: Object.assign({}, SETUPS.data.rows[0], {checks: [
          {group: 'Context', rule: 'Weekly trend', passed: true, value: 'x', required: true},
          {group: 'Context', rule: 'SPY regime', passed: false, value: null, required: false}],
          conditions: {met: 1, of: 1, note: 'Not a probability of success.'}, values: {}, volume: {ratio: 1.4}}),
        chart: {stamps: ['a', 'b', 'c'], open: [1, 2, 3], high: [2, 3, 4], low: [0, 1, 2], close: [1.5, 2.5, 3.5],
          volume: [1, 1, 1], lines: {'20-bar channel': [2, 3, 3]},
          marks: [{index: 0, type: 'armed', stamp: 'a', price: 1.5, level: null},
                  {index: 2, type: 'triggered', stamp: 'c', price: 3.5, level: 3.0}],
          anchors: [], levels: [], trigger_level: 3.0, invalidation: 0.5},
        history: {available: false, reason: 'Daily only.'}}};
      var html = renderSetupsBody();
      R.checks = html.indexOf('1 of 1 conditions met') >= 0;
      R.offNotCounted = html.indexOf('filter off, not counted') >= 0;
      R.alert = html.indexOf('data-ss-alert=') >= 0;
      R.chartHost = html.indexOf('id="ss-chart-0"') >= 0;
      var spec = null;
      lineChart = function (o) { spec = o; return {}; };
      setupChartNode(SETUPS.details[key].data, 600);
      R.markers = spec.vMarkers.map(function (m) { return m.label; });
      R.levels = spec.refLines.map(function (l) { return l.label; });
      R.candles = !!spec.candles;
    """)
    assert out["checks"] and out["offNotCounted"] and out["alert"] and out["chartHost"]
    assert out["markers"] == ["Trigger"], "only the trigger, not every lapsed setup"
    assert any(l.startswith("Trigger") for l in out["levels"])
    assert any(l.startswith("Invalidation") for l in out["levels"])
    assert out["candles"]


def test_the_panel_is_on_the_options_tab_and_opens_by_default():
    swing = APP[APP.index("function renderSwing(d) {"):]
    swing = swing[:swing.index("\nfunction ")]
    assert "${renderSetupsShell()}" in swing
    assert "'swing setups'" in APP[APP.index("const PANELS_OPEN_BY_DEFAULT"):][:4000]
    loader = APP[APP.index("async function loadSwing("):]
    loader = loader[:loader.index("\n}\n")]
    assert "loadSetups();" in loader


def test_its_stores_are_listed_as_settings():
    """tests/test_device_session.py fails on an optic.* key nobody classified;
    these are preferences about the tool, kept with the chart's."""
    src = (ROOT / "tests/test_device_session.py").read_text(encoding="utf-8")
    assert '"optic.setups.view.v1"' in src and '"optic.setups.params.v1"' in src


def test_every_new_control_has_a_handler():
    for attr in ("data-ss-filter", "data-ss-open", "data-ss-rules", "data-ss-rules-reset",
                 "data-ss-alert", "data-ss-options-form", "data-ss-rules-form"):
        assert APP.count(attr) >= 2, attr
    for cls in (".ss-filters", ".ss-table", ".ss-state.is-triggered", ".ss-prov", ".ss-detail-row"):
        assert cls in CSS, cls
