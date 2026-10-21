"""Classic parity, batch B6b (2026-10-21): Swing setups in full on the Options tab, and chart patterns beside their
measured base rates. The pure rules run in JavaScriptCore: Classic's saved view and rule settings (optic.setups.view.v1,
optic.setups.params.v1, with partial and junk values), which symbols a scan covers, its request, the rules form keeping
only what differs from each default, and the base-rate reading. The interactions (filters, the watchlist scope, a row
opened to its chart, checks, back-test and contracts, the alert, the rules form, a group switch) were driven in headless
Chrome on the preview's own data (~/Optic/work/classic-parity/b6b_check.py). These tests are not interaction evidence.
Ledger: docs/frontend-v2/CLASSIC-PARITY.md, B6b.
"""
from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"
SETUPS = (JS / "pages/setups.js").read_text()
CLASSIC = (V2.parent / "app.js").read_text()
CAT = """{ families: ['trend', 'crossover'], presets: [
  { id: 'trend_pullback', label: 'Trend pullback', family: 'trend', context: [{ key: 'htf_filter', type: 'bool', default: true }, { key: 'htf_len', type: 'int', default: 30, min: 5, max: 60 }],
    params: [{ key: 'ema_len', type: 'int', default: 21, min: 5, max: 100 }, { key: 'buffer', type: 'float', default: 0.25, min: 0, max: 2 }] },
  { id: 'ema_cross', label: 'EMA cross', family: 'crossover', params: [{ key: 'fast', type: 'int', default: 9, min: 2, max: 50 }] },
  { id: 'golden_cross', label: 'Golden cross', family: 'crossover', params: [{ key: 'anchor', type: 'date', default: '' }] }] }"""


def test_classics_saved_view_and_rule_settings(tmp_path):
    got = _run(tmp_path, f"""
      const S = await import('{(JS / "pages/setups.js").as_posix()}');
      const seen = [];
      for (const [v, p] of [[JSON.stringify({{ direction: 'bull', status: 'all' }}), JSON.stringify({{ enabled: ['ema_cross'], params: {{ ema_cross: {{ fast: 5 }} }} }})], ['nonsense', '[1,2]'], [null, JSON.stringify({{ enabled: 'x', params: [] }})]]) {{
        if (v === null) localStorage.removeItem(S.VIEW_KEY); else localStorage.setItem(S.VIEW_KEY, v);
        localStorage.setItem(S.PARAMS_KEY, p);
        seen.push([S.readView(), S.readParams()]);
      }}
      S.saveParams({{ enabled: null, params: {{}} }}); const cleared = localStorage.getItem(S.PARAMS_KEY);
      S.saveView({{ scope: 'list:w1', direction: 'bear', timeframe: 'daily', family: 'trend', status: 'recent' }});
      print(JSON.stringify({{ seen, cleared, kept: JSON.parse(localStorage.getItem(S.VIEW_KEY)) }}));
    """)
    base = {"scope": "symbol", "direction": "both", "timeframe": "daily", "family": "", "status": "recent"}
    assert got["seen"][0] == [dict(base, direction="bull", status="all"), {"enabled": ["ema_cross"], "params": {"ema_cross": {"fast": 5}}}], "a partial view is filled from the defaults"
    assert got["seen"][1] == [base, {"enabled": None, "params": {}}] and got["seen"][2] == [base, {"enabled": None, "params": {}}], "junk reads as the defaults"
    assert got["cleared"] is None, "settings equal to the defaults are not kept at all, as Classic does"
    assert got["kept"] == {"scope": "list:w1", "direction": "bear", "timeframe": "daily", "family": "trend", "status": "recent"}
    assert "const SETUPS_VIEW_KEY = 'optic.setups.view.v1';" in CLASSIC and "const SETUPS_PARAMS_KEY = 'optic.setups.params.v1';" in CLASSIC


def test_what_a_scan_covers_and_asks_for(tmp_path):
    got = _run(tmp_path, f"""
      const S = await import('{(JS / "pages/setups.js").as_posix()}');
      const cat = {CAT}, lists = [{{ id: 'w1', name: 'Tech', symbols: ['aapl', 'MSFT', 'AAPL', ...Array.from({{ length: 50 }}, (_, i) => 'S' + i)] }}];
      const v = (o) => Object.assign({{ scope: 'symbol', direction: 'both', timeframe: 'daily', family: '', status: 'recent' }}, o);
      const prm = {{ enabled: ['trend_pullback', 'ema_cross'], params: {{ trend_pullback: {{ ema_len: 20 }} }} }};
      print(JSON.stringify({{
        one: S.symbolsFor(v({{}}), 'aapl', lists), list: S.symbolsFor(v({{ scope: 'list:w1' }}), 'AAPL', lists), gone: S.symbolsFor(v({{ scope: 'list:zz' }}), 'AAPL', lists),
        ids: S.presetIds(cat, v({{ family: 'crossover' }}), prm), all: S.presetIds(cat, v({{}}), {{ enabled: null, params: {{}} }}),
        url: S.scanUrl(v({{ timeframe: '4h', direction: 'bull' }}), ['AAPL'], cat, prm, true), many: S.scanUrl(v({{ timeframe: '4h' }}), ['AAPL', 'MSFT'], cat, {{ enabled: null, params: {{}} }}, false),
        none: S.scanUrl(v({{}}), [], cat, prm, false), key: S.rowKey({{ symbol: 'AAPL', preset: 'p', direction: 'bull', timeframe: 'daily' }}),
        when: [S.whenFor({{ status: 'triggered', trigger: {{ stamp: '2026-10-20' }} }}), S.whenFor({{ status: 'armed', armed_at: '2026-10-19' }}), S.whenFor({{ status: 'watching', status_at: '2026-10-20T15:30:00' }})],
        line: S.stateLine({{ AAPL: {{ armed: 2, inactive: 4 }}, MSFT: {{ armed: 1, triggered: 1 }} }}) }}));
    """)
    assert got["one"] == ["AAPL"] and len(got["list"]) == 40 and got["list"][:2] == ["AAPL", "MSFT"] and got["gone"] == [], "a watchlist's, deduplicated, 40 at most"
    assert got["ids"] == ["ema_cross"] and got["all"] == ["trend_pullback", "ema_cross", "golden_cross"]
    u = got["url"]
    assert u.startswith("/api/setups?symbols=AAPL&timeframe=4h&direction=bull&status=recent&presets=trend_pullback%2Cema_cross&params=") and u.endswith("&provisional=1")
    assert "timeframe=daily" in got["many"] and "presets=" in got["many"] and "params=" not in got["many"] and "provisional" not in got["many"], "4-hour is one symbol only"
    assert got["none"] is None and got["key"] == "AAPL|p|bull|daily"
    assert got["when"] == ["Oct 20 close", "armed Oct 19 close", "Oct 20 15:30 ET"]
    assert got["line"] == "1 triggered, 3 armed, 4 context not met"


def test_the_rules_form_keeps_only_what_changed(tmp_path):
    got = _run(tmp_path, f"""
      const S = await import('{(JS / "pages/setups.js").as_posix()}');
      const cat = {CAT};
      const form = {{ '*::htf_filter': false, '*::htf_len': '30', 'trend_pullback::ema_len': '250', 'trend_pullback::buffer': 'abc', 'ema_cross::fast': '9', 'golden_cross::anchor': '' }};
      const value = (scope, spec) => form[scope + '::' + spec.key];
      const a = S.paramsFrom(cat, value, (id) => id !== 'golden_cross');
      const b = S.paramsFrom(cat, (scope, spec) => spec.default, () => true);
      print(JSON.stringify({{ a, b }}));
    """)
    assert got["a"] == {"enabled": ["trend_pullback", "ema_cross"], "params": {"*": {"htf_filter": False}, "trend_pullback": {"ema_len": 100}}}, "clamped to its range; a default or a bad number is not kept"
    assert got["b"] == {"enabled": None, "params": {}}, "every preset on, nothing changed: nothing kept"


def test_a_pattern_beside_what_followed_it(tmp_path):
    got = _run(tmp_path, f"""
      const P = await import('{(JS / "pages/options-panels.js").as_posix()}');
      const rates = {{ patterns: {{ 'Double top|confirmed': {{ sample: 85, h21: {{ hit_rate: 0.548, n: 85, edge_mean_pct: 0.38 }} }}, 'Doji|candle': {{ sample: 4000, h21: {{ hit_rate: 0.49, n: 4000, edge_mean_pct: -0.04 }} }},
        'Hammer|candle': {{ sample: 12 }}, 'Bad|candle': {{ sample: 300, h21: {{ hit_rate: 0.41, n: 300, edge_mean_pct: -1.2 }} }} }} }};
      print(JSON.stringify({{ a: P.baseRate(rates, 'Double top', 'confirmed'), b: P.baseRate(rates, 'Doji', 'candle'), c: P.baseRate(rates, 'Hammer', 'candle'), d: P.baseRate(rates, 'Bad', 'candle'), e: P.baseRate(null, 'X', 'candle'),
        m: [P.ratesMissing(null).slice(0, 30), P.ratesMissing({{ failed: true }}).slice(0, 30)] }}));
    """)
    assert got["a"] == {"text": "55% of 85", "edge": "+0.38% against its own drift", "tone": "up"}, "against 50%, not zero"
    assert got["b"]["tone"] == "flat" and got["d"]["tone"] == "down" and got["c"] == {"text": "too few to measure (12)", "tone": "none"} and got["e"]["text"] == "too few to measure"
    assert got["m"] == ["Base rates are on their way, s", "Base rates could not be loaded"]
    assert "const worked = h.hit_rate > 0.53;" in CLASSIC and "const failed = h.hit_rate < 0.47;" in CLASSIC, "Classic's cut-offs"


def test_the_tool_on_the_page():
    options = (JS / "pages/options.js").read_text()
    assert "['Swing setups', (t, s) => P.swingSetups(t, s), null, () => mountSetups(mainEl, D.sym," in options
    assert "api.get('/api/patterns/base-rates', { ttl: 3600000, timeout: 150000 })" in options and "disposeSetups();" in options
    assert "slot.replaceWith(SS.node)" in SETUPS, "one node for the visit, put back after the group's redraws"
    assert "saveParams(v); SS.details = {}; SS.open = {};" in SETUPS, "a row opened under old settings closes (Classic left it reading forever)"
    assert "await addAlert({ symbol: r.symbol, kind: 'swing_setup', params: { preset: r.preset } });" in SETUPS
    assert "/api/chat" not in SETUPS and "c-cat-4" not in (V2 / "css/pages.css").read_text().split("/* Swing setups on Options (Classic parity B6b) */")[1].split("/* chart patterns")[0], "no purple"
    assert "classic app" not in (JS / "pages/options-panels.js").read_text().split("export function swingSetups")[1].split("export function baseRate")[0]
