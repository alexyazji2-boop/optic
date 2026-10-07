"""The Earnings and Financials tabs lead with charts, and keep the figures.

Asked for as "lead with the visual and keep precise numerical detail
available through labels, hover states, expandable tables". Each panel's chart
is handed its data here and read back: what it was given, in what order, under
what title, and that the table it summarises is still on the page under
"Exact figures". The primitives themselves are tests/test_visual_primitives.py.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.test_earnings_definitions import D as EARN
from tests.test_financials_definitions import CO, X

ROOT = Path(__file__).resolve().parent.parent
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _jsc(script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = """
      load('tests/support/browser_stubs.js');
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      document.documentElement.style.removeProperty = function () {};
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
      var EARN = %s, CO = %s, X = %s, R = {}, BUILT = {}, CAPT = {};
      STATE.ticker = 'JPM'; STATE.swing = {};
      securityHeader = function () { return ''; };
      keyStatsHost = function () { return ''; };
      hideTip = function () {};
      views.earnings = { innerHTML: '' };
      explainPolicy = function () { return 'on_demand'; };
      vizMount = function (id, build, none) { BUILT[id] = { build: build, none: none }; };
      ['dumbbellChart', 'shareBars', 'columnChart', 'rangeChart', 'divergingBars', 'lineChart'].forEach(function (name) {
        this[name] = function (o) { (CAPT[name] = CAPT[name] || []).push(o); return { chart: name }; };
      });
      function build(id) { var b = BUILT[id]; return b ? b.build(600) : 'not mounted'; }
    """ % (json.dumps(EARN), json.dumps(CO), json.dumps(X)) + script + "\nprint('RESULT:' + JSON.stringify(R));"
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    blob = out.stdout + out.stderr
    assert "RESULT:" in blob, blob[-2000:]
    return json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])


# ------------------------------------------------------------ Earnings

def test_the_earnings_story_leads_with_estimate_against_actual():
    out = _jsc("""
      EARN.next_report.timing = 'after_close';
      EARN.surprise.beat_count = 3;            // the payload always carries it
      renderEarnings(EARN);
      R.html = views.earnings.innerHTML;
      build('viz-earn-surprise');
      R.items = CAPT.dumbbellChart[0].items;
    """)
    html, items = out["html"], out["items"]
    assert 'id="viz-earn-surprise"' in html and "Beat the estimate in 3 of the last 4 quarters" in html
    assert '<details class="exact"><summary>Exact figures</summary>' in html, "the table is kept, folded"
    reported, nxt = items[0], items[-1]
    assert reported["est"] == 4.5 and reported["act"] == 5.0 and reported["move"] == 2.5
    assert nxt["label"] == "Next" and nxt["upcoming"] is True and nxt["est"] == 4.8
    reports = dict(nxt["detail"])["Reports"]
    assert "2026-10-14" in reports and "after the close" in reports


def test_a_fresh_result_is_not_shown_as_still_to_come():
    out = _jsc("""
      EARN.latest_result = { available: true, just_reported: true, beat: true, surprise_pct: 9,
        eps_reported: 5, eps_estimate: 4.6, date: '2026-10-14', age_days: 0, next_day_move_pct: null };
      renderEarnings(EARN);
      build('viz-earn-surprise');
      R.labels = CAPT.dumbbellChart[0].items.map(function (i) { return i.label; });
    """)
    assert "Next" not in out["labels"]


def test_revisions_ratings_and_targets_each_draw_what_they_say():
    out = _jsc("""
      renderEarnings(EARN);
      R.html = views.earnings.innerHTML;
      build('viz-earn-revisions'); build('viz-earn-ratings'); build('viz-earn-targets');
      R.rev = CAPT.divergingBars[0].rows;
      R.rat = CAPT.shareBars[0];
      R.tgt = CAPT.rangeChart[0];
    """)
    assert out["rev"][0]["label"] == "Current quarter" and out["rev"][0]["value"] == 3.0
    row = out["rat"]["rows"][0]
    assert row["label"] == "Now" and row["values"] == {"buy": 12, "hold": 7, "sell": 1}
    assert "60% of 20 analysts rate it a buy" in out["html"]
    marks = {m["label"]: m["value"] for m in out["tgt"]["marks"]}
    assert marks["Mean"] == 320 and abs(marks["Price"] - 320 / 1.08) < 0.01
    assert out["tgt"]["low"] == 260 and out["tgt"]["high"] == 380
    assert "Mean target $320.00, 8% above the price" in out["html"]


def test_quarterly_growth_is_oldest_first_and_a_missing_margin_says_so():
    out = _jsc("""
      EARN.growth.quarterly = [
        { period: '2026-06-30', revenue: 3, net_income: 1 },
        { period: '2026-03-31', revenue: 2, net_income: 1 } ];
      renderEarnings(EARN);
      build('viz-earn-q-rev');
      R.labels = CAPT.columnChart[0].items.map(function (i) { return i.label; });
      R.none = BUILT['viz-earn-q-om'].none;
    """)
    assert out["labels"] == ["Mar '26", "Jun '26"]
    assert out["none"] == "Not reported in these statements."


# ------------------------------------------------------------ Financials

def test_the_track_record_statements_and_owners_are_drawn():
    out = _jsc("""
      CO.earnings_history.upcoming = [{ date: '2026-10-21', eps_estimate: 1.2, timing: 'before_open' }];
      R.html = renderCompany(CO);
      mountFinancialsVisuals(CO);
      build('viz-fin-track'); build('viz-fin-rev'); build('viz-fin-owners'); build('viz-fin-insiders');
      R.track = CAPT.dumbbellChart[0].items;
      R.rev = CAPT.columnChart[0].items;
      R.owners = CAPT.shareBars[0].rows[0].values;
      R.ins = CAPT.divergingBars[0].rows;
    """)
    html = out["html"]
    for host in ("viz-fin-track", "viz-fin-rev", "viz-fin-ni", "viz-fin-fcf", "viz-fin-eps", "viz-fin-owners",
                 "viz-fin-insiders"):
        assert f'id="{host}"' in html, host
    assert "Exact figures, by year" in html
    assert out["track"][-1]["label"] == "Next" and "before the open" in dict(out["track"][-1]["detail"])["Reports"]
    assert [i["label"] for i in out["rev"]] == ["2024", "2025"], "oldest first"
    assert out["rev"][-1]["value"] == 1e9
    assert out["owners"] == {"inst": 70.0, "ins": 5.0, "rest": 25.0}
    assert [r["label"] for r in out["ins"]] == ["Bought", "Sold"] and out["ins"][1]["value"] == -1500


def test_holder_figures_that_overlap_are_not_drawn_as_one_whole():
    out = _jsc("""
      CO.ownership.institutional_pct_held = 0.98; CO.ownership.insider_pct_held = 0.09;
      mountFinancialsVisuals(CO);
      R.built = build('viz-fin-owners');
      R.none = BUILT['viz-fin-owners'].none;
    """)
    assert out["built"] is None and "overlap" in out["none"]


def test_the_corporate_actions_charts():
    out = _jsc("""
      mountExtrasVisuals(X);
      build('viz-fin-divs'); build('viz-fin-excess');
      R.divs = CAPT.columnChart[0].items;
      R.excess = CAPT.divergingBars[0].rows.map(function (r) { return [r.label, r.value]; });
      R.titles = [dividendTitle(X.actions), excessTitle(X.relative)];
    """)
    assert [d["label"] for d in out["divs"]] == ["'24", "'25"] and out["divs"][-1]["value"] == 2.04
    assert out["excess"][0] == ["5 days", 1.0] and len(out["excess"]) == 5
    assert out["titles"] == ["$2.04 a share in 2025, raised 3 years in a row", "Ahead of SPY over 4 of 5 windows"]


@pytest.mark.parametrize("net,want", [(10, "bought more than they sold"), (-10, "sold more than they bought"),
                                      (0, "offset")])
def test_the_insider_title_follows_the_net(net, want):
    out = _jsc("R.t = insiderFlowTitle({ insider_6m: { net_shares: %d } });" % net)
    assert want in out["t"]
