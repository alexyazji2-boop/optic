"""The rebuilt frontend in static/v2 stays faithful to the current app.

Four promises are checked here:
- the navigation's names are the classic app's, word for word (the owner's
  rule that no section, page or phone-bar name changes without a yes);
- every page in the navigation is accounted for in the coverage tracker;
- the device-session module keeps exactly the classic list of personal keys,
  so the two frontends shelve the same things on an account switch;
- the pure helpers (number formatting, the 0 to 100 score, the router) give
  the same answers as the classic app.
"""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
V2 = ROOT / "static/v2"
NAV = (V2 / "js/nav.js").read_text()


def _classic_groups():
    block = APP[APP.index("const NAV_GROUPS = ["):]
    block = block[:block.index("];")]
    return re.findall(r"\{ id: '([a-z]+)', label: '([^']+)', views: ([^,}]+(?:\][^,}]*)?)", block)


def _sub_labels():
    block = APP[APP.index("const SUB_LABELS = {"):]
    block = block[:block.index("};")]
    return dict(re.findall(r"""(\w+): ['"]([^'"]+)['"]""", block))


def test_group_names_are_the_classic_ones():
    classic = {gid: label for gid, label, _ in _classic_groups()}
    v2 = dict(re.findall(r"\{ id: '([a-z]+)', label: '([^']+)'", NAV))
    assert v2 == classic


def test_page_names_are_the_classic_ones():
    labels = _sub_labels()
    pages = re.findall(r"\{ view: '([a-z]+)', label: '([^']+)'", NAV)
    assert pages, "nav.js lists no pages"
    for view, label in pages:
        if view in labels:
            assert label == labels[view], view
    # every classic page is in v2's navigation
    assert {v for v, _ in pages} >= set(labels) - {"overview"} | {"overview"}


def test_sections_and_phone_bar_are_the_classic_ones():
    assert re.search(r"portfolio: 'Tracking', follow: 'Tracking', brokerage: 'Tracking'", APP)
    for gid, section in re.findall(r"(\w+): '(Research|Tracking|Owner)'", NAV):
        assert re.search(r"%s: '%s'" % (gid, section), APP), gid
    classic = re.findall(r"label: '([^']+)', (?:nav|more)", APP[APP.index("const MOBILE_TABS = ["):][:600])
    block = NAV[NAV.index("export const MOBILE_TABS = ["):]
    v2 = re.findall(r"label: '([^']+)'", block[:block.index("];")])
    assert classic == ["Home", "Dossier", "Markets", "Discover", "More"]     # Classic is unchanged
    # The owner's order for v2's bar (2026-10-19): "Home · Markets · Watchlist · Dossier · More, with
    # Discover accessible through More and search". Same names; More lists every group the bar does not.
    assert v2 == ["Home", "Markets", "Watchlist", "Dossier", "More"]
    shell = (V2 / "js/ui/shell.js").read_text()
    assert "visibleGroups(flags).filter((g) => !shown.has(g.id))" in shell, "Discover must stay reachable in More"


def test_every_navigation_page_is_in_the_coverage_tracker():
    doc = (ROOT / "docs/frontend-v2/COVERAGE.md").read_text()
    rows = re.findall(r"^\| ([^|]+) \| ([^|]+) \| `[^`]+` \| (Rebuilt|Current app) \|$", doc, re.M)
    listed = {(g.strip(), p.strip()) for g, p, _ in rows}
    nav = NAV[NAV.index("export const GROUPS = ["):NAV.index("export const SETTINGS")]
    groups = dict(re.findall(r"\{ id: '([a-z]+)', label: '([^']+)'", nav))
    for gid, glabel in groups.items():
        start = nav.index("{ id: '%s'" % gid)
        end = nav.find("{ id: '", start + 5)
        for _view, plabel in re.findall(r"\{ view: '([a-z]+)', label: '([^']+)'", nav[start:end if end > 0 else None]):
            assert (glabel, plabel) in listed, (glabel, plabel)
    # and the tracker's v2 claims match nav.js
    rebuilt = {p.strip() for g, p, s in rows if s == "Rebuilt" and not g.startswith("(")}
    marked = set(re.findall(r"label: '([^']+)', slug: '[^']*', v2: true", NAV))
    assert rebuilt == marked


def test_the_personal_keys_are_the_classic_list():
    def keys(text, start):
        block = text[text.index(start):]
        return re.findall(r"'(optic\.[^']+)'", block[:block.index("];")])
    assert keys((V2 / "js/core/device.js").read_text(), "export const PERSONAL_KEYS = [") \
        == keys(APP, "const PERSONAL_KEYS = [")


def test_no_browser_dialogs_in_v2():
    """Lists are named and deleted inline; prompt() and confirm() are gone."""
    for path in V2.rglob("*.js"):
        text = path.read_text()
        assert not re.search(r"\b(window\.)?(prompt|confirm|alert)\(", text), path.name


JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _jsc():
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("jsc not available")
    return exe


def test_helpers_match_the_classic_app(tmp_path):
    script = tmp_path / "check.mjs"
    script.write_text(f"""
      globalThis.window = {{ addEventListener() {{}} }};
      globalThis.location = {{ hash: '' }};
      const f = await import('{(V2 / "js/core/format.js").as_posix()}');
      const r = await import('{(V2 / "js/core/router.js").as_posix()}');
      print(JSON.stringify({{
        signed: [f.signed(1.234), f.signed(-0.5), f.signed(0)],
        money: f.money(-1234.5), compact: f.compact(5012516765696),
        score: [f.score100(62, -78, 97), f.score100(-39, -78, 97), f.score100(28.2)],
        clean: f.clean('a \\u2014 b, 1\\u20132'),
        routes: ['', '#/', '#/AAPL', '#/aapl/options', '#/watchlist', '#/alerts?symbol=MSFT',
                 '#/brokerage/holdings', '#/instrument/%5EGSPC', '#/macro', '#/settings', '#/bad sym'].map((h) => r.parse(h)),
      }}));
    """)
    out = subprocess.run([_jsc(), "-m", str(script)], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    got = json.loads(out.stdout.strip().splitlines()[-1])
    assert got["signed"] == ["+1.23%", "−0.50%", "0.00%"]
    assert got["money"] == "−$1,234.50"
    assert got["compact"] == "5.01T"
    # 62 on the long-term scale is 82 of 100, as the Investing tab shows
    assert round(got["score"][0]) == 82 and round(got["score"][1]) == 25 and round(got["score"][2], 1) == 64.1
    assert got["clean"] == "a: b, 1 to 2"
    views = [(x["view"], x.get("symbol"), x.get("params", {}).get("symbol")) for x in got["routes"]]
    assert views == [("home", None, None), ("home", None, None), ("overview", "AAPL", None),
                     ("swing", "AAPL", None), ("watchlist", None, None), ("alerts", None, "MSFT"),
                     ("brokerage", None, None), ("instrument", "^GSPC", None), ("market", None, None),
                     ("settings", None, None), ("notfound", None, None)]


def test_chart_and_scenario_arithmetic(tmp_path):
    """The Chart page's indicators and the valuation scenarios compute what the
    classic app computes, on numbers small enough to check by hand."""
    script = tmp_path / "math.mjs"
    script.write_text(f"""
      globalThis.window = {{ addEventListener() {{}} }};
      globalThis.localStorage = {{ getItem() {{ return null; }}, setItem() {{}} }};
      const c = await import('{(V2 / "js/ui/pricechart.js").as_posix()}');
      const v = await import('{(V2 / "js/pages/valuation-scenarios.js").as_posix()}');
      const s = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
      const up = [44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28];
      const r = v.work({{ revenue: 100, shares: 10, price: 50 }}, {{ growth: 10, margin: 20, share_change: 0, pe: 15 }}, {{ years: 2, required_return: 10 }});
      print(JSON.stringify({{ sma: c.sma(s, 3).slice(-1)[0], ema: c.ema(s, 3).slice(-1)[0], rsi: c.rsi(up, 14).slice(-1)[0], r }}));
    """)
    out = subprocess.run([_jsc(), "-m", str(script)], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    got = json.loads(out.stdout.strip().splitlines()[-1])
    assert got["sma"] == 9
    assert abs(got["ema"] - 9) < 1e-9          # a straight line's EMA lags by (n-1)/2
    assert abs(got["rsi"] - 70.46) < 0.02      # by hand: gains 3.34 / 14, losses 1.40 / 14, RS 2.386
    r = got["r"]                               # 100 x 1.1^2 = 121; x 20% = 24.2; / 10 = 2.42; x 15 = 36.3
    assert abs(r["eps"] - 2.42) < 1e-9 and abs(r["price"] - 36.3) < 1e-9
    assert abs(r["today"] - 36.3 / 1.21) < 1e-9


def test_discover_ranking_and_scan_cells(tmp_path):
    """Explore ranks each move against its own typical day (ATR / 1.6) and keeps
    one of an index and its future; Scan formats cells as the classic page does."""
    script = tmp_path / "discover.mjs"
    script.write_text(f"""
      globalThis.window = {{ addEventListener() {{}} }};
      globalThis.matchMedia = () => ({{ matches: false }});
      globalThis.location = {{ hash: '' }};
      globalThis.localStorage = {{ getItem() {{ return null; }}, setItem() {{}} }};
      globalThis.document = {{ addEventListener() {{}}, querySelector() {{ return null; }} }};
      const e = await import('{(V2 / "js/pages/explore.js").as_posix()}');
      const s = await import('{(V2 / "js/pages/scan.js").as_posix()}');
      const home = {{ macro: {{ groups: {{
        indices: [{{ label: 'S&P 500', symbol: '^GSPC', chg_1d: 0.5, atr_pct: 1.6 }}, {{ label: 'S&P 500 futures', symbol: 'ES=F', chg_1d: 0.6, atr_pct: 1.6 }}],
        vol: [{{ label: 'VIX', symbol: '^VIX', chg_1d: 8, atr_pct: 8 }}, {{ label: 'Gold', symbol: 'GC=F', chg_1d: -1, atr_pct: null }}] }} }} }};
      print(JSON.stringify({{
        moves: e.rankedMoves(home).map((r) => [r.label, r.rel]),
        cells: [s.scanCell('pct_plain', 1.234), s.scanCell('mult', 2), s.scanCell('ratio', 0.42), s.scanCell('usd', 2.5e9), s.scanCell('text', null)],
        screen: [s.screenCell({{ unit: '$', decimals: 2 }}, 2.5e7), s.screenCell({{ unit: '$', decimals: 2 }}, 36.344),
                 s.screenCell({{ unit: '%', decimals: 0 }}, 97.2), s.screenCell({{ unit: 'x', decimals: 2 }}, 1.5)],
      }}));
    """)
    out = subprocess.run([_jsc(), "-m", str(script)], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    got = json.loads(out.stdout.strip().splitlines()[-1])
    # VIX 8% on an 8% range is 8 / (8 / 1.6) = 1.6 typical days; on a 1.6% range
    # the future's 0.6 beats the index's 0.5, so only the future is kept
    assert got["moves"] == [["VIX", 1.6], ["S&P 500 futures", 0.6], ["Gold", None]]
    assert got["cells"] == ["1.23%", "2.00×", "42%", "$2.5B", "n/a"]
    assert got["screen"] == ["$25.0M", "$36.34", "97%", "1.50×"]


def test_positions_compare_and_brokerage_arithmetic(tmp_path):
    """The rebuilt Compare, Optic Portfolio, Paper Desk, Retirement and
    Brokerage pages compute what the classic pages compute (static/app.js and
    static/brokerage.js), on numbers small enough to check by hand."""
    script = tmp_path / "positions.mjs"
    script.write_text(f"""
      globalThis.window = {{ addEventListener() {{}} }};
      globalThis.matchMedia = () => ({{ matches: false }});
      globalThis.location = {{ hash: '', search: '' }};
      globalThis.localStorage = {{ getItem() {{ return null; }}, setItem() {{}} }};
      globalThis.document = {{ addEventListener() {{}}, querySelector() {{ return null; }} }};
      const c = await import('{(V2 / "js/pages/compare.js").as_posix()}');
      const t = await import('{(V2 / "js/pages/tracker.js").as_posix()}');
      const p = await import('{(V2 / "js/pages/paper.js").as_posix()}');
      const r = await import('{(V2 / "js/pages/retirement.js").as_posix()}');
      const b = await import('{(V2 / "js/pages/brokerage.js").as_posix()}');
      const rows = [{{ ticker: 'A', rs: 10, pe: 30 }}, {{ ticker: 'B', rs: 9.9, pe: 20 }}, {{ ticker: 'C', rs: 0, pe: 25 }}];
      const g = t.travel({{ stop: 90, target: 110, entry_price: 100, mark_price: 105 }});
      const short = t.travel({{ stop: 110, target: 90, entry_price: 100, mark_price: 104 }});
      const pos = {{ instrument: 'option', entry_price: 2, stop: 1, qty: 3, direction: 'long' }};
      const open = [{{ id: 'a', ticker: 'AAA', instrument: 'shares', direction: 'long', qty: 10, entry_price: 100, stop: 90 }},
                    {{ id: 'b', ticker: 'BBB', instrument: 'option', direction: 'short', qty: 1, entry_price: 5, stop: 8, expiry: '2026-10-20' }}];
      const h = p.health(open, {{ a: {{ pnl: -80 }}, b: {{ pnl: 50 }} }}, '2026-10-18');
      print(JSON.stringify({{
        lead: [c.leader({{ key: 'rs', lead: 'high' }}, rows), c.leader({{ key: 'pe', lead: 'low' }}, rows), c.leader({{ key: 'rs' }}, rows)],
        tie: [c.rankRead([{{ ticker: 'A', score: 60 }}, {{ ticker: 'B', score: 56 }}]), c.rankRead([{{ ticker: 'A', score: 70 }}, {{ ticker: 'B', score: 52 }}])],
        cells: [c.cell('usd', 343.456), c.cell('pct_plain', 1.25), c.cell('pctile', 24.6)],
        gauge: [g.at, g.from, g.ahead, t.travelRead(g), t.travelRead(short)],
        held: [t.heldDays('2026-10-01T00:00:00Z', '2026-10-11T00:00:00Z'), t.heldDays('2026-10-11T00:00:00Z', '2026-10-01T00:00:00Z')],
        paper: [p.cost(pos), p.risk(pos), p.rOf(pos, 150), p.rText(-0.5), p.agrees({{ stance: 'bearish' }}, 'short'), p.agrees({{ stance: 'neutral' }}, 'long')],
        health: [h.total, h.long, h.short, Math.round(h.topShare * 1000) / 1000, h.review.map((x) => x.why)],
        roth: [r.clampInputs({{ years: '60', risk: 'wild', annual: '-5' }}), r.clampInputs({{ years: 'x', annual: 'y' }}).years],
        broker: [b.money(-1234.5), b.money(null), b.qty(1.234567), b.pct(-0.861, 2, true), b.pct(1.2, 1, true)],
      }}));
    """)
    out = subprocess.run([_jsc(), "-m", str(script)], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    got = json.loads(out.stdout.strip().splitlines()[-1])
    # A beats B by 0.1 on a spread of 10: inside 2% of the spread, so no leader
    assert got["lead"] == [None, "B", None]
    assert got["tie"] == ["A and B are level here (60 against 56). Too close to separate.", "A leads, 18 points clear of B."]
    assert got["cells"] == ["$343.46", "1.3%", "25th"]
    # stop 90, target 110: entry 100 is halfway, 105 is three quarters, half of the way to target
    assert got["gauge"][:3] == [0.75, 0.5, True]
    assert got["gauge"][3] == "50% of the way from entry to target"
    assert got["gauge"][4] == "40% of the way from entry to the stop"
    assert got["held"] == [10, 0]
    # an option is 100 shares: costs 2 x 3 x 100, risks 1 x 3 x 100; +150 is half of that
    assert got["paper"] == [600, 300, 0.5, "−0.50R", True, None]
    # exposure at cost: 1000 long, 500 short; AAA is two thirds; AAA is at -0.8R and BBB expires in 2 days
    assert got["health"][:4] == [1500, 1000, 500, 0.667]
    assert got["health"][4] == ["−0.80R, within a quarter of its stop", "expires in 2 days"]
    assert got["roth"][0] == {"years": 45, "risk": "balanced", "annual": 0, "holdings": "", "stock_candidates": ""}
    assert got["roth"][1] == 30
    assert got["broker"] == ["−$1,234.50", "Not supplied", "1.2346", "−0.86%", "+1.2%"]
