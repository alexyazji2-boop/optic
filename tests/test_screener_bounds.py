"""A bound the reader typed is the bound the screen runs with, or it says why not.

Found in a review of the screener, and reproduced before fixing:

* a bound was kept only on `change`, so the five-second poll that re-runs the
  screen while the ranking builds rebuilt the boxes and wiped what was typed,
  and Run sent no bound at all;
* text a number box cannot read reached the server as an empty bound, which it
  drops without a word, so "price at least 100" returned the whole market;
* a field the server does not know was dropped the same silent way;
* switching a row's field kept its old bounds ("price at least 100" became a
  screen for a 100% twenty-day move);
* a limit that was not a number was a 500.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.analytics import screener

ROOT = Path(__file__).resolve().parent.parent
APP_JS = (ROOT / "static" / "app.js").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _ranking(rows):
    return {"ranked": rows, "ranked_at": time.time() - 3600, "universe_size": 2951,
            "passed": len(rows), "gates": {}}


def _row(symbol, price):
    return {"symbol": symbol, "price": price, "dollar_volume": 5e7, "sma20": 1.0, "sma50": 1.0,
            "sma200": 1.0, "roc20": 1.0, "roc60": 1.0, "range_position": 0.5,
            "volume_expansion": 1.0, "atr_pct": 2.0, "score": 10.0}


def test_what_was_not_applied_is_reported_with_the_reason():
    rows = [_row("A", 50.0), _row("B", 150.0)]
    out = screener.run(_ranking(rows), filters=[{"field": "pe_ratio", "max": 15},
                                                 {"field": "price", "min": None, "max": None},
                                                 {"field": "price", "min": 100}])
    assert [r["symbol"] for r in out["rows"]] == ["B"]
    reasons = {(g.get("label") or g["field"]): g["reason"] for g in out["ignored"]}
    assert reasons["pe_ratio"] == "not a field this screen has"
    assert "no minimum or maximum" in reasons["Price"]


def test_a_limit_that_is_not_a_number_is_the_callers_mistake():
    reply = TestClient(main.app).post("/api/screener", json={"limit": "abc"})
    assert reply.status_code == 400 and "whole number" in reply.json()["detail"]


def _jsc(script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = """
      load('tests/support/browser_stubs.js');
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      document.documentElement.style.removeProperty = function () {};
      try { load('static/charts.js'); load('static/app.js'); } catch (e) { print('LOADFAIL:' + e); }
      var R = {};
      function box(attr, value, bad) {
        var ds = {}; ds[attr] = '0';
        return {dataset: ds, value: value, validity: {badInput: !!bad}, attrs: {},
                setAttribute: function (k, v) { this.attrs[k] = v; }, closest: function () { return null; }};
      }
    """ + script + "\nprint('RESULT:' + JSON.stringify(R));"
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=120, cwd=str(ROOT))
    blob = out.stdout + out.stderr
    assert "RESULT:" in blob, blob[-2000:]
    return json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])


def test_a_bound_is_kept_as_it_is_typed():
    out = _jsc("""
      STATE.screener = {filters: [{field: 'price', min: null, max: null}], states: [], sort: 'score', direction: 'desc', limit: 50};
      screenerBoundInput(box('scMin', '100'));
      R.min = STATE.screener.filters[0].min;
      screenerBoundInput(box('scMax', '250.5'));
      R.max = STATE.screener.filters[0].max;
    """)
    assert out == {"min": 100, "max": 250.5}


def test_an_unreadable_bound_stops_the_run_instead_of_vanishing():
    out = _jsc("""
      STATE.screener = {filters: [{field: 'price', min: null, max: null}], states: [], sort: 'score', direction: 'desc', limit: 50};
      var b = box('scMin', '', true);
      screenerBoundInput(b);
      R.row = STATE.screener.filters[0];
      R.invalid = b.attrs['aria-invalid'];
      var posted = false;
      postJSON = function () { posted = true; return new Promise(function () {}); };
      runScreener(false);
      R.posted = posted;
      R.reason = (STATE.screenerResult || {}).reason;
      R.html = screenerFilterRow(R.row, 0);
    """)
    assert out["row"]["min"] is None and out["row"]["bad"]["min"] is True
    assert out["invalid"] == "true" and out["posted"] is False
    assert "not a number" in out["reason"]
    assert "Not a number, so this bound is not applied." in out["html"]


def test_the_request_carries_bounds_and_not_the_page_markers():
    out = _jsc("""
      STATE.screener = {filters: [{field: 'price', min: 100, max: null, bad: {min: false}}], states: [], sort: 'score', direction: 'desc', limit: 50};
      var sent = null;
      postJSON = function (url, body) { sent = body; return new Promise(function () {}); };
      runScreener(false);
      R.sent = sent;
    """)
    assert out["sent"]["filters"] == [{"field": "price", "min": 100, "max": None}]


def test_a_new_field_starts_without_the_old_bounds():
    block = APP_JS.split("if (t.dataset.scField !== undefined) {", 1)[1][:700]
    assert "row.min = null; row.max = null;" in block


def test_a_background_rerun_leaves_the_boxes_alone():
    block = APP_JS.split("async function runScreener(quiet) {", 1)[1].split("\n}\n", 1)[0]
    assert "if (quiet) paintScreenerResult();" in block


def test_ignored_filters_are_shown_with_the_matches():
    assert "Not applied: " in APP_JS.split("function screenerResultHTML() {", 1)[1][:4000]


# ------------------------------------------------------------ the words box

def test_an_amount_with_a_size_is_not_a_share_price():
    """"market cap over $10B" became "priced over $10"."""
    from app.analytics import scan_request as sr
    out = sr.read("market cap over $10B")
    assert out["filters"] == [] and out["understood"] == []
    assert "$10b" in out["leftover"] and "cap" in out["leftover"]
    assert sr.read("cap above $500 million")["filters"] == []
    assert sr.read("price above $50")["filters"] == [{"field": "price", "min": 50.0, "max": None}]
    assert sr.read("under $20")["filters"] == [{"field": "price", "min": None, "max": 20.0}]


def test_a_ratio_it_cannot_read_is_listed_as_unread():
    """"P/E" split into "p" and "e", both too short to list, so the reply never
    said the ratio had been ignored."""
    from app.analytics import scan_request as sr
    assert "p/e" in sr.read("P/E below 15 above the 200-day")["leftover"]
