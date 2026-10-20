"""The owner's v2 fixes of 2026-10-20 afternoon: the Dossier Overview's order and case titles, even answer cards,
the implied-move cone's outlook on hover, the classic draw-on for lines, Milo's width grip, the Options pricing
list without its method text, the two-sided quote box that did nothing, the Compare form's spacing, and the
classic RSI and MACD charts on Options.

The figures (crossings, the momentum window, the chart's fixed range, histogram and marks) run in
JavaScriptCore; the wiring is read as text. Each was also driven in headless Chrome against the demo server at
1440 and 390 px (~/Optic/work/v2-backlog/ui_batch_check.py) and looked at in the browser pane on MSFT.
"""
import re

from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"
CSS = {p.name: p.read_text() for p in (V2 / "css").glob("*.css")}
DOSSIER = (JS / "pages/dossier.js").read_text()
PANELS = (JS / "pages/options-panels.js").read_text()
OPTIONS = (JS / "pages/options.js").read_text()
CHART = (JS / "ui/chart.js").read_text()
MILO = (JS / "ui/milo.js").read_text()


def js(tmp_path, body):
    return _run(tmp_path, f"""
      const P = await import('{(JS / "pages/options-panels.js").as_posix()}');
      const C = await import('{(JS / "ui/chart.js").as_posix()}');
      {body}
    """)


# ---------- Dossier Overview ----------

def test_what_the_company_does_and_its_headlines_come_first():
    paint = DOSSIER[DOSSIER.index("function paint(main, sym)"):]
    assert paint.index("${about(sym)}") < paint.index('section class="section dchart"'), "above the chart"
    about = DOSSIER[DOSSIER.index("function about(sym)"):DOSSIER.index("function more(sym)")]
    # since the beginner pass the section is titled "What Apple does" and opens with its lead (test_v2_beginner)
    assert "What ${name} does" in about and "'Latest headlines'" in about
    more = DOSSIER[DOSSIER.index("function more(sym)"):DOSSIER.index("function paint(")]
    assert "Latest headlines" not in more and "What ${name} does" not in more, "not twice"


def test_bull_and_bear_case_titles_in_the_markets_colours():
    for src in (DOSSIER, PANELS):
        assert 'class="case-h up">Bull case<' in src and 'class="case-h down">Bear case<' in src
        assert ">For<" not in src and ">Against<" not in src


def test_every_answer_card_has_the_same_inset():
    css = CSS["pages.css"]
    assert ".answers .answer-in, .answers .answer:first-child .answer-in, .answers .answer:nth-child(3) .answer-in { padding: 20px 18px 18px; }" in css
    assert ".page-view > section.answers { padding: 0; overflow: hidden; }" in css


def test_the_cone_shows_its_outlook():
    assert "cone: im ? { lo: im.lo, hi: im.hi, pct: im.pct, expiry: im.expiry, from: (D.quote || {}).price } : null" in DOSSIER
    wire = CHART[CHART.index("const showCone = () =>"):CHART.index("if (opts.onEvent)")]
    assert "What the market charges for, not a forecast." in wire
    assert "if (cone && fx > X(pts.length - 1) + 4) { showCone(); return; }" in wire, "the pointer past the last close"
    assert "cone && shown && k === pts.length - 1) showCone()" in wire, "the right arrow from the last close"


# ---------- motion ----------

def test_the_draw_on_runs_once_as_the_chart_first_draws_never_on_scroll():
    src = (JS / "ui/drawon.js").read_text()
    assert "IntersectionObserver" not in src and "scroll" not in src.split("*/")[-1].split("export function")[1]
    assert "prefers-reduced-motion: reduce" in src and "return none" in src
    assert "DRAW_MS = 620, FADE_MS = 300, STAGGER_MS = 70" in src, "the classic timings"
    mount = CHART[CHART.index("const fresh = !el._drawn;"):CHART.index("const drawnOn = new WeakMap();")]
    assert "at === undefined || performance.now() - at < 900" in mount, "once per visit, and a double paint drawn too"
    pc = (JS / "ui/pricechart.js").read_text()
    assert "if (first) { first = false; if (S.animate !== false && !S.view && (S.style === 'line' || S.style === 'area'))" in pc
    assert "if (anim && anim.busy())" in pc, "a redraw waits for the line rather than cutting it off"


# ---------- Milo ----------

def test_milo_can_be_dragged_wider_as_in_the_classic_app():
    grip = MILO[MILO.index("function resizable(panel)"):]
    assert "W_KEY = 'optic.chat.width.v2'" in MILO and "W_MIN = 320" in MILO and "PAGE_MIN = 240" in MILO
    for want in ("role', 'separator'", "e.buttons === 0", "ArrowLeft", "ArrowRight", "dblclick", "removeItem(W_KEY)"):
        assert want in grip, want
    assert ".drawer-panel.milo-panel { width: min(var(--milo-w, 560px), 100vw); }" in CSS["components.css"]
    assert "@media (max-width: 860px) { .milo-grip { display: none; } }" in CSS["components.css"], "a phone's sheet has no grip"


# ---------- Options ----------

def test_the_pricing_list_is_findings_and_the_method_is_folded():
    pricing = PANELS[PANELS.index("export function pricing("):PANELS.index("/* ---------- dealer gamma")]
    items = pricing[pricing.index("const items = ["):pricing.index("].filter(Boolean);")]
    assert "ev.method" not in items and "Front against back" not in items and "Positive means" not in items
    assert "About ${num(ev.move_pct, 1)}% is priced for the report day itself." in items
    fold = pricing[pricing.index("${how("):]
    assert "clean(ev.method || '')" in fold and "vs.iv_method" in fold and "positive means downside puts cost more" in fold


def test_the_unquoted_box_shows_only_when_it_changes_the_list_and_says_by_how_much():
    res = OPTIONS[OPTIONS.index("function research()"):OPTIONS.index("function sumBar()")]
    assert "${R.unquoted || nUnq ? html`<label class=\"check\">" in res
    assert "Include ${nUnq} ${nUnq === 1 ? 'contract' : 'contracts'} without a two-sided quote" in res
    assert "'no two-sided quote' : `mid ${num(r.mid)}`" in res, "the added rows say so"
    load = OPTIONS[OPTIONS.index("async function loadResearch"):OPTIONS.index("/* ---------------- painting")]
    assert "if (R.revealUnq)" in load and "R.allStrikes = R.allByUnq = true" in load, "the far strikes it adds are shown"


def test_a_crossing_is_the_latest_sign_change_of_the_gap(tmp_path):
    got = js(tmp_path, """
      print(JSON.stringify({
        up: P.lastCross([1, 2, 3, 5], [2, 2.5, 2.8, 3]),
        down: P.lastCross([3, 3, 1, 0.5, 0.4], [2, 2, 2, 2, 2]),
        none: P.lastCross([3, 4, 5], [1, 1, 1]),
        gaps: P.lastCross([1, null, 3, 4], [2, 2, 2, 2]),
      }));
    """)
    assert got["up"] == {"index": 2, "bullish": True, "barsAgo": 1}
    assert got["down"] == {"index": 2, "bullish": False, "barsAgo": 2}
    assert got["none"] is None
    assert got["gaps"] is None, "a missing reading is skipped, never read as zero"


def test_momentum_takes_the_last_70_aligned_days_and_refuses_misaligned_series(tmp_path):
    got = js(tmp_path, """
      const n = 120, dates = Array.from({ length: n }, (_, i) => `2026-${String(1 + Math.floor(i / 28)).padStart(2, '0')}-${String(1 + i % 28).padStart(2, '0')}`);
      const rsi = Array.from({ length: n }, (_, i) => 50 + 10 * Math.sin(i / 6));
      const macd = Array.from({ length: n }, (_, i) => Math.sin(i / 9)), signal = macd.map((v) => v * 0.8);
      const t = { technicals: { price_series: { dates }, rsi: { series: rsi }, macd: { series: { macd, signal, hist: macd.map((v, i) => v - signal[i]) } } } };
      const m = P.momentumData(t);
      const bad = P.momentumData({ technicals: { price_series: { dates }, rsi: { series: rsi.slice(1) }, macd: { series: {} } } });
      // the RSI signal is a 9-day average of RSI, over the full series (not restarted at the window)
      const want = rsi.slice(n - 9).reduce((a, b) => a + b, 0) / 9;
      print(JSON.stringify({ n: m.n, d0: m.dates[0], dl: m.dates[69], rsiLen: m.rsi.v.length, sigLast: m.rsi.sig[69], want,
        sigFirst: m.rsi.sig[0], macdLen: m.macd.hist.length, bad,
        line: P.crossLine(null, [1, 2, 3], [0, 0, 0], ['a', 'b', 'c'], 'MACD') }));
    """)
    assert got["n"] == 70 and got["rsiLen"] == 70 and got["macdLen"] == 70
    assert got["dl"] == "2026-05-08" and got["d0"] != "2026-01-01", "the newest 70, not the oldest"
    assert abs(got["sigLast"] - got["want"]) < 1e-9 and got["sigFirst"] is not None
    assert got["bad"] is None, "series that do not line up with the dates are not drawn"
    assert got["line"].startswith("No crossover in the last 3 days: MACD has stayed above its signal line throughout")


def test_the_oscillator_chart_has_its_fixed_range_levels_histogram_and_mark(tmp_path):
    got = js(tmp_path, """
      const s = Array.from({ length: 40 }, (_, i) => ({ d: `2026-09-${String(1 + i % 28).padStart(2, '0')}`, c: 50 + i / 2 }));
      const r = C.lineChart(s, { w: 600, h: 200, domain: [10, 90], ticksAt: [30, 50, 70], refs: [{ v: 70, cls: 'band' }, { v: 30, cls: 'band' }],
        pins: [{ i: 30, v: s[30].c, dir: 'down', text: 'Bearish cross, 9 days ago' }] }).html;
      const h = C.lineChart(s.map((p, i) => ({ d: p.d, c: i - 20 })), { w: 600, h: 200, bars: s.map((_, i) => (i % 2 ? 2 : -3)), ticksAt: [-20, 0, 20], refs: [{ v: 0, cls: 'mid' }] }).html;
      const ax = (x) => [...x.matchAll(/class="ax"[^>]*>([^<]+)</g)].map((m) => m[1]);
      print(JSON.stringify({ refs: (r.match(/class="ref band"/g) || []).length, ticks: ax(r), pin: /class="pin down"/.test(r) && r.includes('Bearish cross, 9 days ago'),
        bars: (h.match(/class="hbar (up|down)"/g) || []).length, ups: (h.match(/class="hbar up"/g) || []).length, hticks: ax(h) }));
    """)
    assert got["refs"] == 2 and got["ticks"][:3] == ["30", "50", "70"]
    assert got["pin"] is True
    assert got["bars"] == 40 and got["ups"] == 20, "every bar drawn from zero, up and down told apart by class"
    assert got["hticks"][:3] == ["−20", "0", "20"] or got["hticks"][:3] == ["-20", "0", "20"], "round fixed ticks, no decimals"


def test_rsi_and_macd_sit_in_levels_and_momentum():
    assert "['Levels and momentum', (t, s) => P.levels(t, s), (t) => P.levelCharts(t)]," in OPTIONS
    lv = PANELS[PANELS.index("export function levels("):PANELS.index("/* ---------- how an option's value moves")]
    assert "${momentum(t)}" in lv
    assert "domain: [10, 90], ticksAt: [30, 50, 70]" in lv, "RSI on the classic fixed range"
    assert "Above 70 is overbought, below 30 oversold; 50 divides bullish from bearish momentum." in lv, "classic's words"
    assert '<p class="legend-line">' in lv and 'class="o2"' in lv, "a key, so the two lines are not told apart by colour alone"
    assert "grid-template-rows: subgrid" in CSS["pages.css"], "the two charts start level"


# ---------- Compare ----------

def test_the_compare_form_has_room():
    css = CSS["pages.css"]
    assert ".cmp-form { display: grid; gap: var(--s-5); justify-items: start; }" in css
    assert ".cmp-recent { display: grid; gap: var(--s-3); margin-top: var(--s-6);" in css
    cmp = (JS / "pages/compare.js").read_text()
    assert '<div class="cmp-recent" role="group" aria-labelledby="cmp-recent-h">' in cmp
    assert ">×</button>" not in cmp and "${icon('close')}" in cmp, "the line icon, not a text glyph"
    assert not re.search(r"\.cmp-inputs \{[^}]*margin-bottom", css)
