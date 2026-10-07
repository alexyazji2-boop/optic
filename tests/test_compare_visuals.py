"""Compare: how the names have moved against each other, and a lead's size.

Asked for as "Compare: small multiples" and "relative performance". The payload
held single figures only, so the question every comparison starts with (which
of these has done better, and by how much) had no picture. The snapshot each
name is compared from already carries two years of daily closes; the server
now sends the past year of them rebased to 100 on the first session all of the
names traded, one point a week and the last session, and the page draws one
line each.

Found doing it: the score bars said they used the take's threshold for a
decisive lead and used 8 points against its 5, so a six-point lead was called
decisive in the headline and not highlighted on its bar.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pandas as pd
import pytest

from app.analytics import compare

ROOT = Path(__file__).resolve().parent.parent
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _payload(start, n, step):
    dates = [d.strftime("%Y-%m-%d") for d in pd.bdate_range(start, periods=n)]
    close = [100 + i * step for i in range(n)]
    return {"technicals": {"price_series": {"dates": dates, "close": close}}, "quote": {"price": close[-1]}}


def test_the_names_are_rebased_to_100_on_the_first_day_all_of_them_traded():
    a = _payload("2025-01-01", 400, 0.5)
    b = _payload("2025-06-02", 300, -0.1)          # listed later: the shared start is its first day
    got = compare.build(lambda s: {"AAA": a, "BBB": b}[s], lambda s: {}, ["AAA", "BBB"])
    perf = got["performance"]
    shared = sorted(set(a["technicals"]["price_series"]["dates"]) & set(b["technicals"]["price_series"]["dates"]))
    assert perf["start"] == shared[-253] and perf["end"] == shared[-1] and perf["sessions"] == 252
    assert perf["dates"][0] == perf["start"] and perf["dates"][-1] == perf["end"]
    assert len(perf["dates"]) == 52, "one point a week and the last session"
    first = {x["ticker"]: x for x in perf["series"]}
    assert first["AAA"]["values"][0] == 100.0 and first["BBB"]["values"][0] == 100.0
    a_close = dict(zip(a["technicals"]["price_series"]["dates"], a["technicals"]["price_series"]["close"]))
    assert first["AAA"]["change_pct"] == round((a_close[perf["end"]] / a_close[perf["start"]] - 1) * 100, 1)


def test_too_little_shared_history_draws_nothing():
    a = _payload("2025-01-01", 400, 0.5)
    b = _payload("2026-08-03", 15, 0.2)
    got = compare.build(lambda s: {"AAA": a, "BBB": b}[s], lambda s: {}, ["AAA", "BBB"])
    assert got["available"] and got["performance"] is None


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
      var R = {}, BUILT = {}, CAPT = {};
      vizMount = function (id, build, none) { BUILT[id] = { build: build, none: none }; };
      lineChart = function (o) { (CAPT.lineChart = CAPT.lineChart || []).push(o); return { chart: 'line' }; };
      function build(id) { var b = BUILT[id]; return b ? b.build(600) : 'not mounted'; }
      var PERF = { start: '2025-10-06', end: '2026-10-05', sessions: 252, dates: ['2025-10-06', '2026-10-05'],
        series: [{ ticker: 'NVDA', values: [100, 164], change_pct: 64.2 }, { ticker: 'AMD', values: [100, 79], change_pct: -21.0 }] };
    """ + script + "\nprint('RESULT:' + JSON.stringify(R));"
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    blob = out.stdout + out.stderr
    assert "RESULT:" in blob, blob[-2000:]
    return json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])


def test_the_lines_are_titled_by_who_did_best_and_say_what_they_leave_out():
    out = _app("""
      var c = { available: true, performance: PERF };
      R.html = comparePerfHTML(c);
      mountCompareVisuals(c);
      build('viz-cmp-perf');
      var o = CAPT.lineChart[0];
      R.names = o.series.map(function (x) { return x.name; }); R.ref = o.refLines[0].value;
      R.colors = o.series.map(function (x) { return x.color; }); R.brand = C.brand; R.s7 = C.s7;
      R.none = comparePerfHTML({ available: true, performance: null });
    """)
    assert "NVDA rose 64% over the period; AMD fell 21%" in out["html"]
    assert "Price only: dividends are not included." in out["html"] and "on 2025-10-06" in out["html"]
    assert "NVDA +64.2%" in out["html"] and "AMD -21.0%" in out["html"], "the legend carries each figure"
    assert out["names"] == ["NVDA", "AMD"] and out["ref"] == 100
    assert out["colors"] == [out["brand"], out["s7"]]
    assert out["none"] == ""


def test_a_lead_of_five_points_is_decisive_on_the_bars_as_in_the_take():
    out = _app("""
      R.html = renderCompareBars({ rows: [{ ticker: 'AAA', scores: { swing: 66 } }, { ticker: 'BBB', scores: { swing: 60 } }],
        horizons: [{ id: 'swing', name: 'Swing setup', horizon: '1-8 weeks' }] });
    """)
    assert "cb-gap is-clear" in out["html"] and "6.0 points clear" in out["html"]


def test_peer_lines_are_tagged_in_their_own_colours():
    """The line chart tags its first series in the direction's colour, as the
    price the chart is about. Compare's names are peers: NVDA's gold line ended
    in a green tag beside a legend that said gold."""
    from tests.test_visual_primitives import _jsc as _prim
    out = _prim("""
      El.prototype.querySelectorAll = function (sel) { var self = this, out = []; walk(this, function (n) { if (n !== self && n.tag === sel) out.push(n); }); return out; };
      El.prototype.querySelector = function (sel) { return this.querySelectorAll(sel)[0] || null; };
      El.prototype.insertBefore = function (c) { this.children.unshift(c); return c; };
      El.prototype.removeChild = function (c) { this.children = this.children.filter(function (x) { return x !== c; }); return c; };
      function tags(dt) {
        var root = lineChart({ width: 500, height: 200, labels: ['a', 'b', 'c', 'd'], valueTags: true, directionTag: dt,
          series: [{ name: 'A', values: [100, 110, 120, 128], color: C.brand }, { name: 'B', values: [100, 90, 95, 116], color: C.s7 }] });
        return all(root, function (n) { return n.tag === 'rect' && n.attrs.rx && n.attrs.fill && n.attrs.fill !== 'transparent'; })
          .map(function (n) { return n.attrs.fill; });
      }
      R.peers = tags(false); R.price = tags(true); R.brand = C.brand; R.s7 = C.s7; R.pos = C.pos;
    """)
    assert out["peers"] == [out["brand"], out["s7"]]
    assert out["price"][0] == out["pos"], "a price chart keeps its directional tag"
    app = (ROOT / "static/app.js").read_text()
    assert "valueTags: true, directionTag: false," in app[app.index("function mountCompareVisuals"):]
