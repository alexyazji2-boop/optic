"""The Options tab leads with charts: payoffs, strikes, expiries, calls against puts.

Asked for as "replace flat options data wherever possible with understandable
visuals". The payoff diagrams are exact: each leg's value at expiry is its
intrinsic value less what was paid, or plus what was taken in, so the line is
straight between strikes. Checked here against the closed forms for every
structure the strategy builder makes, and in a browser against AAPL's ideas on
2026-10-06, where the drawn breakevens matched the server's (343.68 for the
long call, 338.30 for the bull call spread, 312.41 for the cash-secured put).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.test_visual_primitives import DOM

ROOT = Path(__file__).resolve().parent.parent
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _charts(script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = DOM + "\nload('static/charts.js');\nvar R = {};\n" + script + "\nprint('RESULT:' + JSON.stringify(R));"
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    blob = out.stdout + out.stderr
    assert "RESULT:" in blob, blob[-2000:]
    return json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])


def leg(action, typ, strike, mid):
    return {"action": action, "type": typ, "strike": strike, "mid": mid}


STRUCTURES = {
    "long call": [leg("BUY", "CALL", 100, 5)],
    "bull call spread": [leg("BUY", "CALL", 100, 5), leg("SELL", "CALL", 110, 2)],
    "cash-secured put": [leg("SELL", "PUT", 95, 3)],
    "straddle": [leg("BUY", "CALL", 100, 4), leg("BUY", "PUT", 100, 4)],
    "iron condor": [leg("BUY", "PUT", 85, 0.5), leg("SELL", "PUT", 90, 1.5),
                    leg("SELL", "CALL", 110, 1.5), leg("BUY", "CALL", 115, 0.5)],
}


def closed_form(legs, price):
    total = 0.0
    for l in legs:
        intrinsic = max(price - l["strike"], 0) if l["type"] == "CALL" else max(l["strike"] - price, 0)
        pl = intrinsic - l["mid"]
        total += -pl if l["action"] == "SELL" else pl
    return total


@pytest.mark.parametrize("name", sorted(STRUCTURES))
def test_the_payoff_is_the_closed_form_at_every_price(name):
    legs = STRUCTURES[name]
    prices = [60, 85, 90, 95, 97, 100, 103, 107, 110, 113, 115, 140]
    out = _charts("R.v = %s.map(function (p) { return payoffAt(%s, p); });" % (json.dumps(prices), json.dumps(legs)))
    for p, got in zip(prices, out["v"]):
        assert got == pytest.approx(closed_form(legs, p)), (name, p)


def test_breakevens_are_where_the_line_crosses_zero_and_are_vertices_of_the_shading():
    out = _charts("""
      var root = payoffChart({ width: 600, spot: 102, legs: %s });
      R.labels = texts(root);
      R.paths = all(root, function (n) { return n.tag === 'path'; }).map(function (n) { return n.attrs.d; });
      R.edge = R.labels.filter(function (t) { return /keeps|rises/.test(t); });
    """ % json.dumps(STRUCTURES["bull call spread"]))
    assert "breakeven 103.00" in out["labels"], out["labels"]
    assert "now 102.00" in out["labels"]
    assert out["edge"] == [], "a spread is flat at both ends"
    # Both areas pass through the breakeven, so neither spills across the line.
    for d in out["paths"]:
        assert d.count("L") >= 4


def test_an_unbounded_end_says_so():
    out = _charts("""
      R.call = texts(payoffChart({ width: 600, spot: 100, legs: %s })).filter(function (t) { return /keeps|rises/.test(t); });
      R.put = texts(payoffChart({ width: 600, spot: 100, legs: %s })).filter(function (t) { return /keeps|rises/.test(t); });
    """ % (json.dumps(STRUCTURES["long call"]), json.dumps(STRUCTURES["cash-secured put"])))
    assert out["call"] == ["keeps rising"] and out["put"] == ["keeps falling"]


def test_the_readout_walks_with_the_arrow_keys():
    out = _charts("""
      var root = payoffChart({ width: 600, spot: 100, legs: %s });
      var hit = all(root, function (n) { return n.attrs && n.attrs.tabindex === '0'; })[0];
      hit.listeners.focus[0]();
      R.first = TIPS[TIPS.length - 1];
      hit.listeners.keydown[0]({ key: 'ArrowRight', preventDefault: function () {} });
      R.second = TIPS[TIPS.length - 1];
      R.label = hit.attrs['aria-label'];
    """ % json.dumps(STRUCTURES["long call"]))
    assert "At 100.00 on expiry" in out["first"] and "-$500" in out["first"]
    assert "At 100.00" not in out["second"], "the arrow moved the price"
    assert "arrow keys" in out["label"]


def test_a_leg_without_a_price_draws_nothing():
    out = _charts("""
      R.v = payoffChart({ width: 600, spot: 100, legs: [{ action: 'BUY', type: 'CALL', strike: 100, mid: null }] });
    """)
    assert out["v"] is None


def test_strike_bars_split_puts_and_calls_and_mark_the_price():
    out = _charts("""
      var root = butterflyBars({ width: 500, markerRow: 1, markerLabel: 'price 102',
        rows: [{ label: '110', left: 10, right: 100 }, { label: '100', left: 50, right: 50 }, { label: '90', left: 100, right: 5 }] });
      var rects = all(root, function (n) { return n.tag === 'rect' && n.attrs.fill !== 'transparent'; });
      R.fills = rects.map(function (r) { return r.attrs.fill; });
      R.widths = rects.map(function (r) { return Number(r.attrs.width); });
      R.labels = texts(root);
      R.neg = C.neg; R.pos = C.pos;
      R.thin = butterflyBars({ rows: [{ label: 'x', left: 1, right: 1 }] });
    """)
    assert out["fills"][:2] == [out["neg"], out["pos"]]
    assert out["widths"][1] == pytest.approx(out["widths"][4], rel=0.001), "one scale for both sides"
    assert "price 102" in out["labels"] and "◀ Puts" in out["labels"] and "Calls ▶" in out["labels"]
    assert out["thin"] is None


def test_ranked_bars_highlight_the_named_row():
    out = _charts("""
      var root = rankBars({ width: 500, rows: [{ label: 'A', value: 10 }, { label: 'B', value: 80, highlight: true }] });
      R.ops = all(root, function (n) { return n.tag === 'rect' && n.attrs.fill !== 'transparent'; }).map(function (n) { return n.attrs.opacity; });
    """)
    assert out["ops"] == ["0.6", "1"]


# ------------------------------------------------------------ the tab's wiring

def _app(script, payload):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = """
      load('tests/support/browser_stubs.js');
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      document.documentElement.style.removeProperty = function () {};
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
      var D = %s, R = {}, BUILT = {}, CAPT = {};
      vizMount = function (id, build, none) { BUILT[id] = { build: build, none: none }; };
      ['columnChart', 'butterflyBars', 'rankBars', 'shareBars', 'payoffChart'].forEach(function (name) {
        this[name] = function (o) { (CAPT[name] = CAPT[name] || []).push(o); return { chart: name }; };
      });
      function build(id) { var b = BUILT[id]; return b ? b.build(500) : 'not mounted'; }
    """ % json.dumps(payload) + script + "\nprint('RESULT:' + JSON.stringify(R));"
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    blob = out.stdout + out.stderr
    assert "RESULT:" in blob, blob[-2000:]
    return json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])


PAYLOAD = {
    "quote": {"price": 333.6},
    "greeks": {"atm_greeks": [{"expiry": "2026-10-12", "dte": 6, "call": {"iv": 0.21, "strike": 332.5}, "put": {"iv": 0.22}},
                              {"expiry": "2026-12-18", "dte": 73, "call": {"iv": 0.25, "strike": 335}, "put": {"iv": 0.25}}],
               "gamma": {"by_expiry": [{"expiry": "2026-10-12", "dte": 6, "share_pct": 21.5, "gamma_oi": 1, "open_interest": 2},
                                       {"expiry": "2026-12-18", "dte": 73, "share_pct": 78.5, "gamma_oi": 3, "open_interest": 4}]}},
    "gex": {"by_strike": [{"strike": 330, "call_oi": 10, "put_oi": 50, "call_vol": 1, "put_vol": 2},
                          {"strike": 340, "call_oi": 90, "put_oi": 5, "call_vol": 3, "put_vol": 4}]},
    "flow": {"volume": {"calls": 64, "puts": 36}, "open_interest": {"calls": 56, "puts": 44},
             "premium": {"calls": 84, "puts": 16, "call_share_pct": 84}, "new_positions": {"call_premium": 7, "put_premium": 3}},
    "naked_ideas": [{"name": "Long call", "legs": [{"action": "BUY", "type": "CALL", "strike": 335, "mid": 8.68}]}],
    "strategy_ideas": [{"name": "Pair", "conceptual": True}],
}


def test_the_options_charts_are_handed_their_data():
    out = _app("""
      var idea = D.naked_ideas[0];
      R.id1 = payoffId(idea); R.id2 = payoffId(idea);
      mountOptionsVisuals(D);
      ['viz-opt-term', 'viz-opt-oi', 'viz-opt-expiry', 'viz-opt-split', R.id1].forEach(build);
      R.term = CAPT.columnChart[0].items.map(function (i) { return [i.label, Math.round(i.value * 10) / 10]; });
      R.oi = CAPT.butterflyBars[0];
      R.exp = CAPT.rankBars[0].rows.map(function (r) { return [r.label, r.highlight]; });
      R.split = CAPT.shareBars[0].rows.map(function (r) { return r.label; });
      R.payoff = CAPT.payoffChart[0];
      R.titles = [termStructureTitle(D.greeks), oiByStrikeTitle(D.gex), expiryGammaTitle(D.greeks), callPutTitle(D.flow)];
      R.mounted = Object.keys(BUILT);
    """, PAYLOAD)
    assert out["id1"] == out["id2"], "the same card keeps the same host across refreshes"
    assert out["term"] == [["6d", 21.5], ["73d", 25.0]]
    assert [r["label"] for r in out["oi"]["rows"]] == ["$340", "$330"] and out["oi"]["markerRow"] == 1
    assert out["oi"]["markerLabel"] == "price $333.60"
    assert out["exp"] == [["Oct 12 · 6d", False], ["Dec 18 · 73d", True]]
    # Time value, the premium paid above intrinsic value (app/analytics/flow.py).
    assert out["split"] == ["Volume", "Open interest", "Time value", "New positions"]
    assert out["payoff"]["spot"] == 333.6 and out["payoff"]["legs"][0]["strike"] == 335
    assert out["titles"] == ["Implied volatility rises from 22% at 6 days to 25% at 73",
                             "The most open interest sits at the 340 strike",
                             "79% of the chain's gamma is in the Dec 18 expiry",
                             "Calls took 84% of today's option premium"]
    assert not any(k.startswith("viz-payoff") and k != out["id1"] for k in out["mounted"]), "no payoff for a pair idea"


def test_each_idea_card_carries_its_payoff_host_and_keeps_its_figures():
    out = _app("""
      R.html = renderIdea({ name: 'Long call', structure: 'single', expiry: '2026-10-30', dte: 24, rationale: 'r',
        legs: [{ action: 'BUY', type: 'CALL', strike: 335, mid: 8.68, bid: 8.5, ask: 8.9, delta: 0.5, gamma: 0.01,
          theta_per_day: -0.2, iv: 0.25 }], net_delta: 0.5, cost_for_one: 868, net_debit: 8.68 });
    """, PAYLOAD)
    assert 'class="viz idea-payoff"' in out["html"] and 'id="viz-payoff-' in out["html"]
    assert "Cost for one" in out["html"], "the exact figures stay beside it"
