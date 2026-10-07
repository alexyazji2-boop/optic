"""Scan, drawn where drawing helps: the ranked column, and whether the score works.

Asked for as "scanner result distributions, ranking, and explainable
comparisons". A scan's 25 rows stay a table, which is what many rows of
figures need, and three things are added:

* the column the list is ordered by is marked, with aria-sort, because it is
  not always the first and the order came from a lambda the page could not
  read; the server names it now;
* that column carries a bar per row only when the figures spread enough to tell
  rows apart. The top 25 momentum scores run 74 to 82 and drew the same bar 25
  times, which is decoration;
* "Does the score work?" draws each score bucket's mean excess return with its
  95% interval at each horizon, on one scale, grey where the interval crosses
  zero.

Found doing it: the relative-performance scans have no ranking age, and the
line under them read "ranking —h old".
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from app.analytics import relperf, scanners
from tests.test_visual_primitives import _jsc as _prim

ROOT = Path(__file__).resolve().parent.parent
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _app(script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = """
      load('tests/support/browser_stubs.js');
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      document.documentElement.style.removeProperty = function () {};
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
      explainPolicy = function () { return 'on_demand'; };
      scanAskHTML = function () { return ''; }; renderResearchHub = function () { return ''; };
      var R = {}, BUILT = {}, CAPT = {};
      vizMount = function (id, build, none) { BUILT[id] = { build: build, none: none }; };
      ['intervalChart'].forEach(function (name) {
        this[name] = function (o) { (CAPT[name] = CAPT[name] || []).push(o); return { chart: name }; };
      });
      function build(id) { var b = BUILT[id]; return b ? b.build(600) : 'not mounted'; }
      function res(rows, rk, cols) {
        return { available: true, looks_for: 'x', blind_spot: 'y', method: 'z', matched: rows.length,
          shown: rows.length, age_hours: rk && rk.key === 'rank' ? null : 7.7, ranked_by: rk,
          columns: cols || [{ key: 'score', label: 'Score', kind: 'score' }, { key: 'roc20', label: '1-month', kind: 'pct' }],
          rows: rows };
      }
    """ + script + "\nprint('RESULT:' + JSON.stringify(R));"
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    blob = out.stdout + out.stderr
    assert "RESULT:" in blob, blob[-2000:]
    return json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])


# ------------------------------------------------------------ the ranked column

def test_every_scan_names_the_column_it_is_ordered_by():
    for scan in scanners.SCANS:
        key, order = scanners.RANKED_BY[scan["id"]]
        assert key in scan["columns"], scan["id"]
        assert order in ("asc", "desc", "abs")
    ranking = {"ranked": [{"symbol": "A", "price": 10, "score": 30, "roc20": 5, "roc60": 9,
                           "range_position": 0.9, "volume_expansion": 1.2, "dollar_volume": 1e8, "atr_pct": 2}],
               "ranked_at": None}
    got = scanners.run(ranking, "downtrend")
    assert got["ranked_by"] == {"key": "roc60", "order": "asc"}, "not the first column, and lowest first"


def test_the_relative_performance_scans_name_theirs(monkeypatch):
    monkeypatch.setattr(relperf, "scan", lambda provider, kind, limit=20: {
        "available": True, "rows": [{"symbol": "A", "rank": 99, "prior": 90, "state": "leader"}], "universe_size": 143})
    assert relperf.run_scan(None, "rp-leaders")["ranked_by"] == {"key": "rank", "order": "desc"}
    assert relperf.run_scan(None, "rp-laggards")["ranked_by"] == {"key": "rank", "order": "asc"}


def test_the_ranked_column_is_marked_and_barred_only_when_rows_differ():
    out = _app("""
      var tight = []; for (var i = 0; i < 25; i++) tight.push({ symbol: 'T' + i, price: 10, score: 82 - i / 3, roc20: 20 });
      var wide = [{ symbol: 'A', price: 1, score: 9, roc20: 48 }, { symbol: 'B', price: 1, score: 8, roc20: -30 },
                  { symbol: 'C', price: 1, score: 7, roc20: 12 }, { symbol: 'D', price: 1, score: 6, roc20: 6 }];
      R.tight = renderScan({ scans: [] }, res(tight, { key: 'score', order: 'desc' }));
      R.wide = renderScan({ scans: [] }, res(wide, { key: 'roc20', order: 'abs' }));
    """)
    assert 'aria-sort="descending"' in out["tight"] and "Ranked highest first" in out["tight"]
    assert "data-scan-bar" not in out["tight"], "74 to 82 is the same bar 25 times"
    assert out["wide"].count("data-scan-bar=") == 4 and "Ranked by size, either way" in out["wide"]


def test_a_ranking_with_no_age_does_not_print_one():
    out = _app("""
      R.html = renderScan({ scans: [] }, res([{ symbol: 'A', rank: 99, prior: 90, state: 'leader' },
        { symbol: 'B', rank: 97, prior: 70, state: 'leader' }], { key: 'rank', order: 'desc' },
        [{ key: 'rank', label: 'RP rank', kind: 'num' }, { key: 'state', label: 'State', kind: 'text' }]));
    """)
    assert "h old" not in out["html"] and "—h" not in out["html"]


def test_bars_run_from_the_left_for_a_one_sided_figure_and_a_rank_is_out_of_100():
    out = _app("""
      var calls = [];
      inlineBar = function (v, max, w, h, opts) { calls.push([v, max, !!(opts && opts.oneSided)]); return { tag: 'svg' }; };
      function cell(v, kind) { return { dataset: { scanBar: String(v), kind: kind }, appendChild: function () {} }; }
      var set = [cell(30, 'num'), cell(60, 'num')];
      fillScanBars({ querySelectorAll: function () { return set; } });
      var signed = [cell(-20, 'pct'), cell(40, 'pct')];
      fillScanBars({ querySelectorAll: function () { return signed; } });
      R.calls = calls;
    """)
    assert out["calls"] == [[30, 100, True], [60, 100, True], [-20, 40, False], [40, 40, False]]


# ------------------------------------------------------------ does the score work

EVAL = {"available": True, "horizons": [
    {"horizon_sessions": 5, "buckets": [
        {"bucket": "strongly bearish", "n": 600, "mean_pct": -0.7, "ci95_pct": [-1.2, -0.1], "hit_rate_pct": 45},
        {"bucket": "neutral", "n": 150, "mean_pct": 1.5, "ci95_pct": [0.2, 2.8], "hit_rate_pct": 55},
        {"bucket": "strongly bullish", "n": 1100, "mean_pct": -0.1, "ci95_pct": [-0.5, 0.4], "hit_rate_pct": 50}]},
    {"horizon_sessions": 63, "buckets": [
        {"bucket": "strongly bearish", "n": 600, "mean_pct": -3.9, "ci95_pct": [-5.6, -2.0], "hit_rate_pct": 40},
        {"bucket": "strongly bullish", "n": 1100, "mean_pct": 1.3, "ci95_pct": [-0.3, 2.9], "hit_rate_pct": 52}]},
]}


def test_the_score_is_drawn_with_its_uncertainty_on_one_scale():
    out = _app("""
      var E = %s;
      R.title = evalTitle(E);
      mountEvaluation(E);
      build('viz-eval-5'); build('viz-eval-63');
      R.charts = CAPT.intervalChart.map(function (c) { return { domain: c.domain, rows: c.rows.map(function (r) { return [r.label, r.value, r.lo, r.hi]; }) }; });
    """ % json.dumps(EVAL))
    assert out["title"] == ("Strongly bearish scores trailed the rest at 2 of 2 horizons, clear of their interval; "
                            "strongly bullish ones beat it at no horizon")
    a, b = out["charts"]
    assert a["domain"] == b["domain"] == [-5.6, 2.9], "one scale, so the horizons read across"
    assert a["rows"][0] == ["Strongly bearish", -0.7, -1.2, -0.1]


def test_an_interval_that_crosses_zero_is_grey():
    out = _prim("""
      var root = intervalChart({ width: 400, rows: [
        { label: 'A', value: 1.5, lo: 0.2, hi: 2.8 }, { label: 'B', value: -0.1, lo: -0.5, hi: 0.4 },
        { label: 'C', value: -3.9, lo: -5.6, hi: -2.0 } ] });
      R.dots = all(root, function (n) { return n.tag === 'circle'; }).map(function (n) { return n.attrs.fill; });
      R.marks = all(root, function (n) { return n.attrs && n.attrs.tabindex === '0'; }).map(function (n) { return n.attrs['aria-label']; });
      R.pos = C.pos; R.neg = C.neg; R.muted = C.muted;
      R.none = intervalChart({ rows: [{ label: 'x', value: 1 }] });
    """)
    assert out["dots"] == [out["pos"], out["muted"], out["neg"]]
    assert "crosses zero" in out["marks"][1] and "crosses zero" not in out["marks"][0]
    assert out["none"] is None
