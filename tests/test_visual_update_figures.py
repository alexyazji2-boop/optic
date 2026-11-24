"""The visual update's figures (2026-11-11): red and green by the span a line draws, an arrow and a sign on every move,
the gauges, bars and donut, and the compact More list. The modules run in JavaScriptCore; the pages' wiring is read as
text (the project's pattern for client contracts, CLAUDE.md). The browser journeys in tests/e2e/test_visual_update.py
check the same figures drawn on Home and the Overview at each level."""
import re

from tests.test_frontend_v2_stage0 import V2
from tests.test_v2_p3 import _run

JS = V2 / "js"
WS = (JS / "pages/workspace.js").read_text()
OV = (JS / "pages/dossier.js").read_text()
HOME = (JS / "pages/home.js").read_text()
FRAME = (JS / "pages/dossier-frame.js").read_text()
CSS = (V2 / "css/components.css").read_text() + (V2 / "css/pages.css").read_text()


def run(tmp_path, body):
    return _run(tmp_path, f"""
      const C = await import('{(JS / "ui/chart.js").as_posix()}');
      const G = await import('{(JS / "ui/glance.js").as_posix()}');
      const SM = await import('{(JS / "ui/showmore.js").as_posix()}');
      const D = await import('{(JS / "core/dom.js").as_posix()}');
      const S = (x) => D.toString(x);
      {body}
    """)


# ------------------------------------------------------------ the span rule (operator decision 2)

def test_a_line_is_coloured_by_the_span_it_draws_never_by_today(tmp_path):
    got = run(tmp_path, """
      const pts = (v) => v.map((c, i) => ({ d: `2026-0${1 + Math.floor(i / 28)}-${String(1 + (i % 28)).padStart(2, '0')}`, c }));
      const up = C.lineChart(pts([10, 9, 11, 12]), { w: 400, tone: 'span', base: true }).html;
      const down = C.lineChart(pts([12, 13, 11, 10]), { w: 400, tone: 'span', base: true }).html;
      const flat = C.lineChart(pts([10, 12, 9, 10]), { w: 400, tone: 'span' }).html;
      const plain = C.lineChart(pts([10, 12]), { w: 400 }).html;
      print(JSON.stringify({ up: /class="chart tone-up"/.test(up), down: /class="chart tone-down"/.test(down), flat: /class="chart tone-flat"/.test(flat),
        base: /<line class="base"/.test(up), noBase: !/<line class="base"/.test(flat), plain: /class="chart" /.test(plain),
        tones: [C.spanTone([1, 2]), C.spanTone([2, 1]), C.spanTone([3, 1, 3]), C.spanTone([5])],
        sparks: [C.spark([1, 3, 2]), C.spark([3, 1, 2]), C.spark([2, 9, 2])].map((s) => (s.match(/class="spark (\\w+)"/) || [])[1]),
        named: C.spark([1, 2], 'AAPL, past 30 sessions, up 1.0%'), hidden: C.spark([1, 2]) }));
    """)
    assert got["up"] and got["down"] and got["flat"] and got["plain"]
    assert got["base"] and got["noBase"], "the start level dashed only when asked"
    assert got["tones"] == ["up", "down", "flat", "flat"]
    assert got["sparks"] == ["up", "down", "flat"], "a sparkline by its own span: first point to last"
    assert 'role="img" aria-label="AAPL, past 30 sessions, up 1.0%"' in got["named"] and 'aria-hidden="true"' in got["hidden"]


def test_the_charts_take_the_pair_and_gold_keeps_the_cone():
    assert ".chart.tone-up .line, .chart.tone-up .end { stroke: var(--c-up); }" in CSS
    assert ".chart.tone-down .line, .chart.tone-down .end { stroke: var(--c-down); }" in CSS
    assert ".spark.up path { stroke: var(--c-up); } .spark.down path { stroke: var(--c-down); }" in CSS
    assert ".chart .cone-edge { stroke: var(--c-cone-edge);" in CSS, "the options cone stays gold"
    # the pages draw their lines by span: Home's headline and the company's year
    assert "tone: 'span', base: true, label: `${name} daily closes, ${words}`" in WS
    assert "area: true, tone: 'span', base: true, label: `${sym} closing price`," in OV


# ------------------------------------------------------------ an arrow and a sign on every move

def test_every_move_has_an_arrow_and_a_sign(tmp_path):
    got = run(tmp_path, """
      print(JSON.stringify({ up: S(G.move(1.27)), down: S(G.move(-0.5)), flat: S(G.move(0)), bp: S(G.move(0.3, '+1 bp')),
        words: [G.moveWords(2, '+2.00%'), G.moveWords(-1, '−1.00%'), G.moveWords(0, '0.00%')] }));
    """)
    assert got["up"] == '<span class="mv up"><span class="mv-a" aria-hidden="true">▲</span>+1.27%</span>'
    assert got["down"] == '<span class="mv down"><span class="mv-a" aria-hidden="true">▼</span>−0.50%</span>'
    assert got["flat"] == '<span class="mv flat">0.00%</span>', "no arrow and no sign where nothing moved"
    assert "▲" in got["bp"] and "+1 bp" in got["bp"]
    assert got["words"] == ["up +2.00%", "down −1.00%", "unchanged"]


def test_the_moves_on_home_and_the_overview_use_it():
    for snippet in ("${mv(i.chg_1d, moveText(i))}", "${mv(f.chg, f.chgText)}", "move(r.change_pct)".replace("move", "mv"), "${mv(v)}</button>"):
        assert snippet in WS, snippet
    assert 'aria-label="${r.label || r.name} (${r.symbol}), ${moveWords(v, signed(v))}"' in WS, "a heat-map tile says its move in words"
    assert "<span class=\"mv-a\" aria-hidden=\"true\">${ARROW[dir(q.change_pct)]}</span>" in FRAME, "the company's price carries its arrow"
    assert "${ARROW[d]}" in OV and "'For' : 'Against'" in OV, "the bull and bear lines"


# ------------------------------------------------------------ gauges, bars, the donut

def test_the_gauge_bars_and_donut_state_their_values_as_text(tmp_path):
    got = run(tmp_path, """
      print(JSON.stringify({
        g: S(G.gauge({ v: -2, lo: -100, hi: 100, ends: ['−100 cautious', '+100 risk-on'], label: 'Score −2' })),
        gNone: S(G.gauge({ v: null, lo: 0, hi: 100 })),
        d: S(G.divBars([{ label: 'VIX level', v: 10 }, { label: 'VIX 5-day change', v: -6 }], { label: 'Factors' })),
        p: S(G.pairBars([{ label: 'Today', v: 39.4, text: '39.4×', cls: 'gold' }, { label: 'Usual', v: 30.9, text: '30.9×', cls: 'mute' }])),
        dn: S(G.donut([{ label: 'iPhone', v: 53 }, { label: 'Services', v: 26 }, { label: 'Mac', v: 21 }], { center: '$479B', sub: 'FY26' })),
        dnOne: S(G.donut([{ label: 'All', v: 1 }])) }));
    """)
    g = got["g"]
    assert 'role="img" aria-label="Score −2"' in g and "left:49.0%" in g and "−100 cautious" in g and "+100 risk-on" in g
    assert got["gNone"] == "", "no reading, no gauge: the panel says so instead"
    d = got["d"]
    assert 'aria-label="Factors"' in d and "+10.0" in d and "−6.0" in d and 'class="db-fill pos" style="left:50%' in d and 'class="db-fill neg" style="right:50%' in d
    assert "39.4×" in got["p"] and "30.9×" in got["p"] and "pb-fill gold" in got["p"] and "pb-fill mute" in got["p"]
    dn = got["dn"]
    assert 'role="img" aria-label="iPhone 53%, Services 26%, Mac 21%"' in dn and "$479B" in dn and "<b>53%</b>" in dn
    assert got["dnOne"] == "", "a whole of one part is not a mix"


def test_nothing_in_the_figures_is_set_under_13px():
    comp, pages = (V2 / "css/components.css").read_text(), (V2 / "css/pages.css").read_text()
    rules = comp[comp.index("/* ---------- figures at a glance"):] + pages[pages.index("/* ---------- Home, the visual update"):]
    sizes = re.findall(r"font(?:-size)?:[^;]*?var\(--t-(\w+)\)", rules)
    assert sizes and set(sizes) <= {"xs", "sm", "md", "base", "lg", "xl", "2xl", "figure", "lead", "chart"}
    assert not re.search(r"font-size:\s*\d+px", rules)


# ------------------------------------------------------------ the compact More list

def test_more_is_one_compact_list_of_rows_each_opening_its_panel(tmp_path):
    got = run(tmp_path, """
      print(JSON.stringify({ list: S(SM.moreList([{ id: 'regime', title: 'Market conditions', blurb: 'The score.' }], { heading: 'More on Home', screen: 'home' })),
        desk: S(SM.moreButton('desk:full', 'Optic Desk', { label: 'The whole desk' })), less: S(SM.lessButton('regime', 'Market conditions')) }));
    """)
    li = got["list"]
    assert 'data-v2-sm-stub="regime"' in li and '<span class="sm-t">Market conditions</span>' in li
    assert 'data-v2-show-more="regime" aria-expanded="false" aria-label="Open: Market conditions">Open</button>' in li
    assert "The score." not in li and "sm-sub" not in li, "a row, not a card: the blurb is the panel's own How"
    assert 'aria-label="The whole desk">The whole desk</button>' in got["desk"]
    assert 'data-v2-show-less="regime"' in got["less"]


# ------------------------------------------------------------ Home's composition by level (operator decisions 1 and 3)

def test_homes_level_matrix_is_the_prototypes():
    assert "beginner: [['indices', 12, 'm'], ['sectors', 8, 'm'], ['desk', 4, 'm']]," in WS
    assert "intermediate: [['indices', 12, 'm'], ['regime', 4, 'm'], ['sentiment', 4, 'm'], ['expected', 4, 'm'], ['sectors', 12, 'm'], ['watch', 6, 'm'], ['desk', 6, 'm']]," in WS
    assert "const LEVEL_TRIM = { beginner: ['desk'], intermediate: ['desk'] };" in WS
    # the first-visit card stays, smaller, with its Follow buttons (decision 3)
    ob = WS[WS.index("function onboard() {"):WS.index("// A row the next panel cannot join ends early")]
    assert "is-compact" in ob and "${STARTERS.map((sym) => followBtn(sym))}" in ob
    # no 1-day line on Home: no intraday read (decision 1); 3M, 6M and 1Y of the closes take-chart already serves
    assert "/api/intraday" not in WS
    assert "const FEAT_SPANS = [['3m', '3M', 'past 3 months'], ['6m', '6M', 'past 6 months'], ['1y', '1Y', 'past year']];" in WS
    assert "get(`/api/take-chart/${enc(sym)}?span=${span}`" in WS


def test_home_draws_what_it_already_fetches():
    tiles = WS[WS.index("  indices: {"):WS.index("  regime: {")]
    assert "const ser = (i.series || []).filter(isNum)" in tiles and "spark(ser, '', { w: 120, h: 30 })" in tiles
    assert "UNIT[" not in tiles, "the unit lines went"
    watch = WS[WS.index("  watch: {"):WS.index("  quote: {")]
    assert "const sp = (r.spark || []).filter(isNum)" in watch and "30 sessions" in watch
    assert "load: () => get('/api/sentiment', { ttl: 120000 })" in WS
    heat = WS[WS.index("  sectors: {"):WS.index("  calendar: {")]
    assert "<b>${r.symbol}</b>" not in heat, "the fund's code left the tile's face"
    assert "rows.sort((a, b) => b[P.period] - a[P.period])" in heat, "strongest move first"
    # the Desk below Advanced: two sentences of the edition's own, the rest one press away
    assert "s.slice(1, 2)" in HOME and "moreButton('desk:full', 'Optic Desk', { label: 'The whole desk' })" in WS


def test_the_overview_figures_read_what_the_page_already_holds():
    figs = OV[OV.index("/* ---------------- the figures (the visual update"):OV.index("/* ---------------- page ---------------- */")]
    for need in ("company || {}).financials", "OR.valuationRead(D.longterm)", "(D.fairValue || {}).stars", "(D.earnings || {}).surprise",
                 "next_day_move_pct", "ownership", "OR.earningsNext" if "OR.earningsNext" in figs else "F.report"):
        assert need in figs, need
    assert "api." not in figs and "fetch(" not in figs, "no new request"
    # each missing series has its own words where its figure would be
    for words in ("No yearly revenue came back for it.", "No reported quarters came back for it.", "No day-after moves came back for it.",
                  "No holder figures came back for it.", "The statements did not load."):
        assert words in figs, words
    # a fund, an index or a coin keeps the simple analysis in words
    assert "const companyLike = (sym) => !['fund', 'index', 'crypto'].includes(kindOf(sym, D));" in OV
    assert "['words', 'Simple analysis'," in OV
