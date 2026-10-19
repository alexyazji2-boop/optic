"""The Investing tab's weekly structure chart in v2 (I6, 2026-10-19).

The closes-only line it was is now the Chart tab's interactive chart on the long-term model's weekly bars:
candles, a line or an area; the classic Technical levels menu (retracements, support and resistance as bands,
volume); drag to move along the years, wheel or pinch to zoom, arrows to read each week. The choices are the
classic app's own keys, so a style or a range picked in either app holds in the other, and the menu's three
switches are the flags the classic charts share.

Months are rolled up from the weeks the way the classic aggregateMonthly does it (checked against it in
JavaScriptCore). A week is named by its Monday and the one still trading says so, since the model dates its weeks
by their Friday. Checked in a browser on AAPL and COIN at 1440, 390 and 375 by 549.
"""
from tests.test_frontend_v2_stage0 import V2
from tests.test_v2_p3 import _run

ROOT = V2.parent.parent
JS = V2 / "js"
CLASSIC = (ROOT / "static/app.js").read_text()
INV = (JS / "pages/investing.js").read_text()
PC = (JS / "ui/pricechart.js").read_text()
CSS = (V2 / "css/pages.css").read_text()


def _classic(name):
    i = CLASSIC.index(f"function {name}(")
    return CLASSIC[i:CLASSIC.index("\n}\n", i) + 2]


def test_months_are_rolled_up_as_the_classic_app_does(tmp_path):
    got = _run(tmp_path, f"""
      {_classic("aggregateMonthly")}
      const I = await import('{(JS / "pages/investing.js").as_posix()}');
      // thirty weeks of made-up bars from a Friday, the model's dating
      const weeks = []; let p = 50; const t0 = Date.UTC(2025, 0, 3);
      for (let i = 0; i < 30; i++) {{ const t = t0 + i * 7 * 86400000, o = p, c = p + Math.sin(i) * 3 + 0.4; weeks.push({{ t, d: new Date(t).toISOString().slice(0, 10), o, h: Math.max(o, c) + 1 + (i % 3), l: Math.min(o, c) - 1 - (i % 2), c, v: 1e6 + i * 1e4 }}); p = c; }}
      const ser = {{ dates: weeks.map((b) => b.d), open: weeks.map((b) => b.o), high: weeks.map((b) => b.h), low: weeks.map((b) => b.l), close: weeks.map((b) => b.c), volume: weeks.map((b) => b.v) }};
      const c = aggregateMonthly(ser), v = I.monthlyBars(weeks);
      const same = (a, b) => a.length === b.length && a.every((x, i) => Math.abs(x - b[i]) < 1e-9);
      print(JSON.stringify({{
        n: [c.dates.length, v.length], dates: JSON.stringify(c.dates) === JSON.stringify(v.map((b) => b.d)),
        o: same(c.open, v.map((b) => b.o)), h: same(c.high, v.map((b) => b.h)), l: same(c.low, v.map((b) => b.l)),
        cl: same(c.close, v.map((b) => b.c)), vol: same(c.volume, v.map((b) => b.v)),
      }}));
    """)
    assert got["n"][0] == got["n"][1] == 7, "thirty weeks from January 3 are seven calendar months"
    assert all(got[k] for k in ("dates", "o", "h", "l", "cl", "vol")), got


def test_a_bar_is_named_for_the_time_it_covers(tmp_path):
    got = _run(tmp_path, f"""
      const I = await import('{(JS / "pages/investing.js").as_posix()}');
      const at = (iso) => Date.parse(iso), day = (d) => Date.parse(`${{d}}T00:00:00Z`);
      print(JSON.stringify({{
        // Monday Oct 19 2026, 7pm in New York: the week ending Friday Oct 23 is still trading
        friLabel: I.barName('weekly', day('2026-10-23'), at('2026-10-19T23:00:00Z')),
        monLabel: I.barName('weekly', day('2026-10-19'), at('2026-10-19T23:00:00Z')),
        done: I.barName('weekly', day('2026-10-16'), at('2026-10-19T23:00:00Z')),
        friBefore: I.barName('weekly', day('2026-10-23'), at('2026-10-23T19:30:00Z')),
        friAfter: I.barName('weekly', day('2026-10-23'), at('2026-10-23T20:30:00Z')),
        month: I.barName('monthly', day('2026-10-02'), at('2026-10-19T23:00:00Z')),
        past: I.barName('monthly', day('2026-09-04'), at('2026-10-19T23:00:00Z')),
      }}));
    """)
    assert got["friLabel"] == got["monLabel"] == "Week of Oct 19, 2026, so far", "the model's Friday and the full history's Monday name the same week"
    assert got["done"] == "Week of Oct 12, 2026"
    assert got["friBefore"].endswith("so far") and got["friAfter"] == "Week of Oct 19, 2026", "a week closes at 4pm on its Friday in New York"
    assert got["month"] == "Oct 2026, so far" and got["past"] == "Sep 2026"
    assert "when: (t) => barName(iv, t)" in INV
    assert "const w = S.when && S.when(t); if (w) return w;" in PC, "the readout, the keyboard reading and the summary use the page's name"


def test_the_note_says_why_an_average_starts_late(tmp_path):
    got = _run(tmp_path, f"""
      const I = await import('{(JS / "pages/investing.js").as_posix()}');
      const weeks = (n) => Array.from({{ length: n }}, (_, i) => ({{ t: Date.UTC(2021, 3, 16) + i * 7 * 86400000 }}));
      print(JSON.stringify({{
        young: I.maNote('COIN', weeks(287), 260, 'week'), old: I.maNote('AAPL', weeks(627), 260, 'week'),
        months: I.maNote('COIN', weeks(67), 60, 'month'),
      }}));
    """)
    assert got["young"] == ("Optic's price history for COIN begins in Apr 2021. An average has no value until it has as many weeks of closes "
                            "as its length, so the 40-week starts in Jan 2022 and the 200-week starts in Feb 2025."), got["young"]
    assert got["old"] == "", "nothing to say when both averages run across the whole view"
    assert got["months"].endswith("so the 40-month starts in Jan 2022 and the 200-month has none yet.")


def test_the_classic_keys_and_their_values():
    for k in ("LT_MODE_KEY = 'optic.lt.mode'", "LT_RANGE_KEY = 'optic.lt.range'", "LT_INTERVAL_KEY = 'optic.lt.interval'",
              "SHOW_FIB_KEY = 'optic.chart.fib.v2'", "SHOW_SR_KEY = 'optic.chart.sr.v2'", "SHOW_VOL_KEY = 'optic.chart.vol.v2'"):
        assert k in CLASSIC, k
    assert "const LT_STYLE_KEY = 'optic.lt.mode', LT_RANGE_KEY = 'optic.lt.range', LT_IV_KEY = 'optic.lt.interval';" in INV
    assert "const LVL_KEYS = { fib: 'optic.chart.fib.v2', sr: 'optic.chart.sr.v2', vol: 'optic.chart.vol.v2' };" in INV
    # the classic app keeps the range in lower case and the style as 'candle', and starts on a 5-year line
    assert "{ key: '5y', label: '5Y', weekly: 260, monthly: 60 }," in CLASSIC and "let ltMode = 'line';" in CLASSIC
    assert "setSetting(LT_RANGE_KEY, b.dataset.v2LtRange.toLowerCase())" in INV
    assert "setting(LT_RANGE_KEY, '5y')).toLowerCase()" in INV, "a range stored by v2 before, in capitals, still reads"
    assert "setSetting(LT_STYLE_KEY, { candles: 'candle', line: 'line', area: 'area' }[b.dataset.v2LtStyle])" in INV
    assert "({ candle: 'candles', line: 'line', area: 'area' })[setting(LT_STYLE_KEY, 'line')] || 'line'" in INV
    # on and off as the classic flags read: volume on unless turned off, the other two only when turned on
    assert "showVol = localStorage.getItem(SHOW_VOL_KEY) !== 'off';" in CLASSIC and "showFib = localStorage.getItem(SHOW_FIB_KEY) === 'on';" in CLASSIC
    assert "(k === 'vol' ? setting(LVL_KEYS.vol, 'on') !== 'off' : setting(LVL_KEYS[k], 'off') === 'on')" in INV
    assert "const MONTHS = { '1Y': 12, '3Y': 36, '5Y': 60, '10Y': 120, All: Infinity };" in INV, "the classic LT_RANGES' months"


def test_the_levels_menu_is_the_classic_three():
    i = CLASSIC.index('<div class="lvl-pop" role="group" aria-label="Levels on the chart">')
    tag = '<input type="checkbox" data-level-opt="'
    classic = [CLASSIC[j + len(tag):CLASSIC.index('"', j + len(tag))] for j in range(i, i + 4000) if CLASSIC.startswith(tag, j)]
    assert classic == ["fib", "sr", "vol"]
    assert "const lv = [['fib', 'Retracements'], ['sr', 'Support and resistance'], ['vol', 'Volume']]" in INV
    assert '<details class="menu lt-lvl"><summary class="btn btn-sm">Technical levels' in INV and '<span class="ch-count">' in INV, "with the count, as the classic menu has"
    # switched in place: the chart, the count and the key change and the open menu stays where it was
    w = INV[INV.index("main.addEventListener('change'"):INV.index("main.addEventListener('click'")]
    assert "WK.chart.set(weeklyLooks())" in w and "draw(lg, ltLegend())" in w and "paint()" not in w
    # retracements from the model's own ratios, the bands from the weekly frame's support and resistance
    assert ".filter((z) => isNum(z.price) && z.ratio !== null && z.ratio !== undefined)" in INV and "z.ratio * 100, 1)}%" in INV
    assert ".filter((x) => isNum(x.band_low) && isNum(x.band_high)).slice(0, 8).map((x) => ({ lo: x.band_low, hi: x.band_high, role: x.role" in INV
    assert "panes: { volume: lvlOn('vol'), rsi: false, macd: false }" in INV


def test_the_chart_is_the_interactive_one_and_survives_a_repaint():
    assert "import { createPriceChart } from '../ui/pricechart.js';" in INV
    assert "weeklyMaker" not in INV and "mountWeekly();" in INV, "no closes-only line any more"
    m = INV[INV.index("function mountWeekly() {"):INV.index("// Why an average starts partway across")]
    assert "if (WK.chart && WK.key === key && WK.host) { slot.replaceWith(WK.host); WK.chart.set(looks);" in m, "a pan or a zoom outlasts the other sections arriving"
    assert "[D.sym, iv, range," in m, "built again only for another symbol, interval, range or history"
    assert "series: [{ values: sma(closes, 40), cls: 'o1' }, { values: sma(closes, 200), cls: 'o2' }]" in m, "the averages over the whole history, so they are right at the left edge"
    assert "export function dispose() { live = false; if (WK.chart) WK.chart.destroy();" in INV
    assert "Drag to move along the years, wheel or pinch to zoom, arrows to read each ${unit}." in INV
    # the tiles hold one value each
    assert "['Weekly RSI', num(lt.weekly_rsi, 1)], ['40-week slope over 3 months', signed(lt.slope_40w_pct_3m)]], 4)" in INV


def test_the_chart_draws_bands_and_series_without_stacking_labels():
    assert "(S.bands || []).forEach((b) =>" in PC and '<rect class="band ${b.role === \'resistance\' ? \'res\' : \'sup\'}"' in PC
    assert "(S.series || []).forEach((sr) => { o += `<path class=\"ov ${sr.cls || ''}\"" in PC
    assert "Math.abs(q.y - y) < 15)) return false;" in PC and "b.label && room('l', top - 3)" in PC, "a weaker band's label goes where it would stack"
    assert "at.crowd && !room(at.end ? 'r' : 'l', Number(ty))" in PC and "end: true, crowd: true" in INV
    assert "text-anchor=\"${X(i) < 20 ? 'start' : 'middle'}\"" in PC, "the first date on the axis stays inside the plot"
    for k in (".pc .band.sup {", ".pc .band.res {", ".legend-line i.kbs", ".legend-line i.kbr", ".legend-line i.kfib"):
        assert k in CSS, k
