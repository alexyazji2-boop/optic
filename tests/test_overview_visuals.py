"""The Overview: a year of the price with its reports, dividends and splits.

Asked for as "Dossier Overview: a price chart with earnings, dividend and split
markers". The Overview had no chart; it gave the price's place in its 52-week
range as a percentage. It draws the daily closes the ticker payload already
carries, marks each report (from the company's earnings history), ex-dividend
date and split (from the extras, drawn again when they land), lists every
marked date in a table because a marker's hover cannot be reached from a
keyboard, and leaves a date past the last bar off the chart, naming the next
report in the caption instead.

Found doing it: the caveat under the Overview read `fin.notes`, and the server
sends `note`, so "No statement data. Common for ETFs" never showed.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"

DATES = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2025-01-02", periods=300)]
CLOSE = [50 + i * 0.1 for i in range(300)]
D = {"technicals": {"price_series": {"dates": DATES, "close": CLOSE}},
     "company": {"earnings_history": {
         "quarters": [{"date": DATES[-30], "timing": "before_open", "eps_estimate": 0.9, "eps_reported": 0.97,
                       "surprise_pct": 7.8},
                      {"date": DATES[10], "timing": "after_close", "eps_estimate": 1, "eps_reported": 1.1,
                       "surprise_pct": 10}],
         "upcoming": [{"date": "2026-12-01", "timing": "after_close"}]}}}
X = {"ticker": "KO", "actions": {"dividends": [{"date": DATES[-60], "amount": 0.51}, {"date": "2019-01-01", "amount": 0.4}],
                                 "splits": [{"date": DATES[-5], "ratio": 2}]}}


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
      STATE.ticker = 'KO';
      var D = %s, X = %s, R = {}, BUILT = {}, CAPT = {}, HOSTS = {};
      STATE.extras = X;
      vizMount = function (id, build, none) { BUILT[id] = { build: build, none: none }; };
      lineChart = function (o) { (CAPT.line = CAPT.line || []).push(o); return { chart: 'line' }; };
      var realGet = document.getElementById;
      document.getElementById = function (id) { return HOSTS[id] || (HOSTS[id] = { innerHTML: '' }); };
      function build(id) { var b = BUILT[id]; return b ? b.build(600) : 'not mounted'; }
    """ % (json.dumps(D), json.dumps(X)) + script + "\nprint('RESULT:' + JSON.stringify(R));"
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    blob = out.stdout + out.stderr
    assert "RESULT:" in blob, blob[-2000:]
    return json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])


def test_a_year_of_closes_with_its_reports_dividends_and_splits_marked():
    out = _app("""
      R.html = overviewChartHTML(D);
      mountOverviewChart(D);
      build('viz-ov-price');
      var o = CAPT.line[0];
      R.n = o.labels.length; R.first = o.labels[0];
      R.marks = o.vMarkers.map(function (m) { return [m.label, m.index]; });
      R.color = o.series[0].color; R.pos = C.pos;
      R.events = HOSTS['ov-events'].innerHTML;
    """)
    assert out["n"] == 252 and out["first"] == DATES[-252]
    assert out["marks"] == [["D", 252 - 60], ["E", 252 - 30], ["S", 252 - 5]], "in date order; a report before the window is left off"
    assert out["color"] == out["pos"], "the price line follows its direction"
    html = out["html"]
    assert "KO is up" in html and "over the past year, at its highest close of it" in html
    assert "Next report 2026-12-01, after the close." in html, "a date past the last bar is named, not drawn"
    ev = out["events"]
    assert "The 3 marked dates" in ev and "Reported before the open EPS 0.97 against 0.90 expected (beat by 7.8%)" in ev
    assert "$0.51 a share" in ev and "2.00-for-1" in ev


def test_another_stocks_dividends_are_not_drawn_on_this_one():
    out = _app("""
      STATE.extras = { ticker: 'PEP', actions: X.actions };
      R.kinds = overviewEvents(D, D.technicals.price_series.dates.slice(-252)).map(function (e) { return e.label; });
    """)
    assert out["kinds"] == ["E"]


def test_too_little_history_draws_no_chart_and_a_fall_says_so():
    out = _app("""
      R.short = overviewChartHTML({ technicals: { price_series: { dates: D.technicals.price_series.dates.slice(0, 10),
        close: D.technicals.price_series.close.slice(0, 10) } } });
      R.down = overviewChartTitle('KO', [100, 120, 80]);
    """)
    assert out["short"] == ""
    assert out["down"] == "KO is down 20% over the 3 sessions shown, 33% below its highest close"


def test_the_overview_says_when_a_fund_has_no_statements():
    app = (ROOT / "static/app.js").read_text()
    body = app[app.index("function renderOverviewView() {"):]
    body = body[:body.index("\n}\n")]
    assert "fin.note || fin.notes" in body, "the server sends note; notes never showed"
    src = (ROOT / "app/analytics/fundamentals.py").read_text()
    assert '"note": "No statement data.' in src
