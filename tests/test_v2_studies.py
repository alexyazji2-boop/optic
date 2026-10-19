"""The classic chart studies in v2 (C11, 2026-10-19): EMA clouds, MA Trend, TSO, VWAP, Keltner, Donchian, the
regression channel, Weinstein stages, accumulation zones, auto trend lines, volume by price, supply and demand
zones and session dividers, on the v2 Chart page (ui/studies.js, pages/chart-studies.js, ui/pricechart.js).

The maths v2 does itself is checked against the classic app's own functions, lifted from static/app.js and run in
JavaScriptCore on the same bars, so the two apps draw the same thing. The rest comes from the endpoints the
classic app already reads. Checked in a browser on AAPL at 1440 on daily and hourly bars, every study on.
"""
import json
import re

from tests.test_frontend_v2_stage0 import V2
from tests.test_v2_p3 import _run

ROOT = V2.parent.parent
JS = V2 / "js"
CLASSIC = (ROOT / "static/app.js").read_text()
CH = (JS / "pages/chart.js").read_text()
CS = (JS / "pages/chart-studies.js").read_text()
PC = (JS / "ui/pricechart.js").read_text()


def _classic(name):
    i = CLASSIC.index(f"function {name}(")
    return CLASSIC[i:CLASSIC.index("\n}\n", i) + 2]


def _const(name):
    m = re.search(rf"^const {name} = [^\n]*;$", CLASSIC, re.M)
    assert m, name
    return m.group(0)


# made-up daily bars: a rise, a fall, a chop and a late rally, with volume
BARS_JS = """
  const bars = []; let p = 100, t0 = Date.UTC(2025, 0, 2);
  for (let i = 0; i < 420; i++) {
    const drift = i < 150 ? 0.35 : i < 250 ? -0.3 : i < 330 ? Math.sin(i / 6) * 0.6 : 0.8;
    const o = p, c = Math.max(5, p + drift + Math.sin(i * 1.7) * 1.3), h = Math.max(o, c) + 0.6 + (i % 5) * 0.2, l = Math.min(o, c) - 0.5 - (i % 3) * 0.25;
    bars.push({ t: t0 + i * 86400000, o, h, l, c, v: 1e6 + (i % 7) * 2e5 }); p = c;
  }
  const O = bars.map((b) => b.o), Hh = bars.map((b) => b.h), Ll = bars.map((b) => b.l), Cc = bars.map((b) => b.c), Vv = bars.map((b) => b.v);
"""


def test_the_maths_is_the_classic_apps(tmp_path):
    classic = "\n".join([_classic(n) for n in ("smaSeries", "rsiSeries", "adxSeries")]
                        + [_const("TSO_ADX"), _classic("tsoSeries"),
                           _const("MA_TREND_PERIODS"), _classic("maTrendSeries"), _const("VBP_BUCKETS"), _classic("volumeByPrice")])
    got = _run(tmp_path, f"""
      {classic}
      const S = await import('{(JS / "ui/studies.js").as_posix()}');
      {BARS_JS}
      const same = (a, b) => a.length === b.length && a.every((x, i) => (x === null && b[i] === null) || Math.abs(x - b[i]) < 1e-9);
      const vbC = volumeByPrice({{ close: Cc, volume: Vv }}), vbV = S.volumeByPrice(Cc, Vv);
      print(JSON.stringify({{
        tso: same(tsoSeries(Hh, Ll, Cc), S.tsoSeries(Hh, Ll, Cc)), tsoLast: S.tsoSeries(Hh, Ll, Cc).slice(-1)[0],
        mat: JSON.stringify(maTrendSeries(O, Cc)) === JSON.stringify(S.maTrendSeries(O, Cc)), matSeen: [...new Set(S.maTrendSeries(O, Cc))].sort(),
        vbp: vbC.length === vbV.length && vbC.every((b, i) => Math.abs(b.price - vbV[i].price) < 1e-9 && b.volume === vbV[i].volume && b.poc === vbV[i].poc),
        poc: vbV.filter((b) => b.poc).length,
      }}));
    """)
    assert got["tso"] and isinstance(got["tsoLast"], (int, float)), "TSO as the classic tsoSeries"
    assert got["mat"] and got["matSeen"] == [-1, 0, 1, None], "MA Trend as the classic maTrendSeries, all four readings met"
    assert got["vbp"] and got["poc"] >= 1, "volume by price as the classic volumeByPrice"


def test_trend_lines_land_where_the_classic_app_puts_them(tmp_path):
    tl = {"available": True, "dates": [f"2026-0{m}-{d:02d}" for m in (7, 8) for d in range(1, 29)],
          "lines": [{"kind": "support", "start_index": 3, "end_index": 50, "start_price": 100.0, "price_now": 120.0, "touches": 4, "broken": False},
                    {"kind": "resistance", "start_index": 10, "end_index": 50, "start_price": 140.0, "price_now": 130.0, "touches": 3, "broken": True}]}
    got = _run(tmp_path, f"""
      const C = {{ pos: 'POS', neg: 'NEG' }};
      {_classic("weekMonday")}
      {_classic("trendSegments")}
      const S = await import('{(JS / "ui/studies.js").as_posix()}');
      const tl = {json.dumps(tl)};
      const keys = tl.dates.slice(5).concat(['2026-08-31', '2026-09-01']);   // the chart starts later and runs on
      const c = trendSegments(tl, keys), v = S.trendSegments(tl, keys);
      print(JSON.stringify({{ c: c.map((s) => [s.x1, s.y1, s.x2, s.y2, s.color]), v: v.map((s) => [s.i1, s.p1, s.i2, s.p2, s.up ? 'POS' : 'NEG']) }}));
    """)
    assert got["c"] == got["v"] and len(got["v"]) == 2, "each end read off the line, counted on past the server's last bar"


def test_a_week_takes_the_stage_its_friday_decided(tmp_path):
    got = _run(tmp_path, f"""
      const S = await import('{(JS / "ui/studies.js").as_posix()}');
      const day = (s) => ({{ t: Date.parse(s + 'T00:00:00Z') }});
      const history = [['2026-09-28', 2], ['2026-10-05', 3], ['2026-10-12', 4]];
      const daily = ['2026-10-05', '2026-10-09', '2026-10-12', '2026-10-16'].map(day);
      const weekly = ['2026-10-05', '2026-10-12'].map(day);
      const hourly = [{{ t: Date.parse('2026-10-13T10:30:00-04:00') }}];
      print(JSON.stringify({{ daily: S.stageOfBars(daily, history), weekly: S.stageOfBars(weekly, history, {{ weekly: true }}), hourly: S.stageOfBars(hourly, history, {{ intraday: true }}), monday: S.weekMonday('2026-10-18') }}));
    """)
    assert got["daily"] == [2, 2, 3, 3], "a daily bar takes the last completed week's stage, no hindsight"
    assert got["weekly"] == [3, 4], "a weekly bar keeps its own week's"
    assert got["hourly"] == [3] and got["monday"] == "2026-10-12"


def test_sessions_server_lines_and_the_vwap_anchor(tmp_path):
    got = _run(tmp_path, f"""
      const S = await import('{(JS / "ui/studies.js").as_posix()}');
      const hours = []; for (let d = 0; d < 6; d++) for (let h = 0; h < 7; h++) hours.push({{ t: Date.parse(`2026-10-${{String(12 + d).padStart(2, '0')}}T${{String(9 + h).padStart(2, '0')}}:30:00-04:00`) }});
      const dense = []; for (let d = 0; d < 6; d++) dense.push({{ t: Date.parse(`2026-10-${{String(12 + d).padStart(2, '0')}}T10:30:00-04:00`) }});
      const bars = [{{ t: Date.parse('2026-10-15T00:00:00Z') }}, {{ t: Date.parse('2026-10-16T00:00:00Z') }}, {{ t: Date.parse('2026-10-19T00:00:00Z') }}];
      const al = S.alignLines(['2026-10-16', '2026-10-19'], [{{ name: 'Keltner mid', values: [10, null] }}], bars);
      const CS = await import('{(JS / "pages/chart-studies.js").as_posix()}');
      const iv = {{ key: 'daily' }}, t = {{ patterns: {{ zones: [{{ side: 'supply', top: 12, bottom: 11, formed: '2026-10-16', broken: false, out_of_horizon: false }}, {{ side: 'demand', top: 5, bottom: 4, formed: '2026-09-01', out_of_horizon: true }}] }} }};
      CS.bind({{ sym: () => 'ZZZ', bars: () => bars, iv: () => iv, range: () => '6M', session: () => 'regular', weekly: () => false, firstShown: () => bars[1].t, t: () => t, repaint() {{}} }});
      CS.reset();
      const on = {{ zones: true, sessions: true, trends: false }};
      const d = CS.data(on);
      print(JSON.stringify({{ starts: S.sessionStarts(hours), dense: S.sessionStarts(dense), al: al[0].values, zones: d.studies.zones, notes: CS.notes(on) }}));
    """)
    assert got["starts"] == [7, 14, 21, 28, 35], "a line where each day starts"
    assert got["dense"] == [], "one a bar would be a fence: none"
    assert got["al"] == [None, 10, None], "server values land on the bars with the same time"
    assert got["zones"] == [{"t": 1792108800000, "top": 12, "bottom": 11, "side": "supply", "broken": False}], "zones out of reach are left out"
    assert got["notes"] == ["Session dividers are drawn on intraday bars."]
    assert "anchor = P.weekly() ? weekMonday(d) || d : d;" in CS and "if (on.vwap && !P.iv().intraday)" in CS, "VWAP from the first bar in view"


def test_only_the_classic_endpoints_and_only_while_on():
    urls = set(re.findall(r"`(/api/[a-z-]+)", CS))
    assert urls == {"/api/indicators", "/api/stage", "/api/trendlines", "/api/longterm"}, urls
    for k, url in (("stages", "/api/stage"), ("trends", "/api/trendlines"), ("accum", "/api/longterm")):
        assert f"if (on.{k}) get(" in CS and url in CS
    assert "ST.need(ticked())" in CH, "asked for when a study is turned on, and with each new set of bars"


def test_the_menu_names_groups_and_defaults():
    for k, name in (("cloud921", "EMA 9 / 21 cloud"), ("cloud2150", "EMA 21 / 50 cloud"), ("keltner", "Keltner channel"), ("donchian", "Donchian channel"),
                    ("sec", "Regression channel"), ("vwap", "Anchored VWAP"), ("zones", "Supply and demand"), ("accum", "Accumulation zones"),
                    ("trends", "Auto trend lines"), ("vbp", "Volume by price"), ("sessions", "Session dividers"), ("stages", "Weinstein stages"), ("matrend", "MA Trend Identifier")):
        assert f"['{k}', '{name}']" in CH, k
        assert f"{k}: false" in CH, f"{k} is off until the reader turns it on"
        assert f"  {k}: '" in CS, f"{k} says what it is in the menu"
    assert "['tso', 'Trend Strength Oscillator']" in CH and "tso: false," in CH
    assert "const OV_GROUP = { ma: 'Averages and bands', fib: 'Levels', msb: 'Structure and events', stages: 'Candle colours' };" in CH
    assert 'class="menu-body ch-imenu"' in CH, "the longer menu scrolls"
    assert "Studies such as stages, MA Trend and volume by price" not in CH, "the footnote no longer sends them to the current app"


def test_the_price_pane_is_clipped_and_tints_win():
    assert '<clipPath id="${CLIP}">' in PC and "o += '</g>';" in PC, "nothing on the price runs into the panes under it"
    assert "const tint = OV.matrend ?" in PC, "MA Trend colours the candles in place of the stages"
    css = (V2 / "css/pages.css").read_text()
    assert ".pc .wick.tint.st3, .pc .body.tint.st3 { stroke: var(--c-warn); fill: var(--c-warn); }" in css


# ------------------------------------------------------------ the indicator panes (C19, 2026-10-19)

def test_the_panes_come_from_the_classic_endpoint_on_these_bars(tmp_path):
    got = _run(tmp_path, f"""
      const CS = await import('{(JS / "pages/chart-studies.js").as_posix()}');
      const bars = ['2026-10-15', '2026-10-16', '2026-10-19'].map((d) => ({{ t: Date.parse(d + 'T00:00:00Z') }}));
      const ind = {{ dates: ['2026-10-16', '2026-10-19'], indicators: {{
        adx: {{ name: 'ADX and DI', available: true, reference: [{{ value: 25, label: '25' }}], lines: [{{ name: 'ADX', values: [20, 21] }}, {{ name: '+DI', values: [30, 31] }}, {{ name: '-DI', values: [10, null] }}] }},
        rs: {{ name: 'Relative strength line', available: false, reason: 'No benchmark history' }},
        keltner: {{ name: 'Keltner channel', available: true, lines: [] }},
      }} }};
      print(JSON.stringify({{ panes: CS.panesFrom(ind, bars), ids: CS.SERVER_PANES }}));
    """)
    p = got["panes"]
    assert sorted(p) == ["adx", "rs"], "panes only; the price studies go elsewhere"
    assert [ln["values"] for ln in p["adx"]["lines"]] == [[None, 20, 21], [None, 30, 31], [None, 10, None]], "bar for bar by time"
    assert p["adx"]["reference"] == [{"value": 25, "label": "25"}]
    assert p["rs"] == {"name": "Relative strength line", "reason": "No benchmark history"}, "a pane that cannot draw says why"
    assert got["ids"] == ["adx", "stochastic", "obv", "mfi", "rs"]


def test_the_panes_in_the_menu_and_on_the_chart():
    for k, name in (("adx", "ADX and DI"), ("stochastic", "Stochastic"), ("obv", "On-balance volume"), ("mfi", "Money flow index"), ("rs", "Relative strength line")):
        assert f"['{k}', '{name}']" in CH and f"{k}: false" in CH, k
        assert f"  {k}: '" in CS, f"{k} says what it is in the menu"
    assert "const ticked = () => Object.assign({}, V.overlays, V.panes);" in CH and "ST.need(ticked())" in CH, "fetched when a pane is ticked"
    assert "const ids = SERVER.concat(SERVER_PANES).filter((k) => on[k]);" in CS, "one request for the price studies and the panes"
    assert "const SERVER_PANES = ['adx', 'stochastic', 'obv', 'mfi', 'rs'];" in PC
    assert "Math.min(0.17, 0.5 / extra)" in PC, "with every pane on the price keeps half the height"
    assert "const BOUNDED = { stochastic: [0, 100], mfi: [0, 100], adx: [0, 50] };" in PC
    assert "indicator panes the current app adds" not in CH


def test_past_two_panes_the_chart_grows():
    assert "const paneRoom = () => Math.max(0, PANES.filter(([k]) => k !== 'volume' && V.panes[k]).length - 2) * (isPhone() ? 60 : 72);" in CH
    assert "function plotHeight(host) { return baseHeight(host) + paneRoom(); }" in CH, "five panes on a phone left the price 70 px and each pane 22 px"
