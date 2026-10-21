"""Data visualizations on Financials and Earnings (owner's brief, 2026-10-20), with the beginner brief's Earnings
items (7) and term explanations (11).

Every takeaway is computed in core/finviz.js from the figures its chart draws, and the rules that keep a chart
honest run here in JavaScriptCore: percentage changes refused on a base at or below zero, percentage points for
margins, a cash-flow bridge only when the three figures reconcile, an aggregate segment line left out rather than
counted twice, surprises read one way every quarter with no percentage of a near-zero estimate, statements in the
currency the company files in. The chart components (ui/bars.js) are checked for a zero baseline, gaps left as
gaps, empty end periods trimmed and labels kept off each other. The server's new statement lines come from rows
the provider already read. Looked at in headless Chrome at 390 and 1440 on AAPL and TSM
(~/Optic/work/v2-backlog/tools/shot.py; screenshots in ~/Optic/work/dataviz).
"""
from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"
FIN = (JS / "pages/financials.js").read_text()
EARN = (JS / "pages/earnings.js").read_text()
CSS = (V2 / "css/components.css").read_text() + (V2 / "css/pages.css").read_text()
TOKENS = (V2 / "css/tokens.css").read_text()


def fv(tmp_path, body):
    return _run(tmp_path, f"""
      const F = await import('{(JS / "core/finviz.js").as_posix()}');
      const B = await import('{(JS / "ui/bars.js").as_posix()}');
      const T = await import('{(JS / "ui/term.js").as_posix()}');
      {body}
    """)


def test_changes_are_refused_where_they_would_mislead(tmp_path):
    got = fv(tmp_path, """
      print(JSON.stringify({ up: F.pctChange(110, 100), loss: F.pctChange(50, -20), zero: F.pctChange(5, 0), gap: F.pctChange(null, 4),
        pp: F.ppChange(32.0, 31.5), m: F.marginSeries([30, null], [100, 200]) }));
    """)
    assert abs(got["up"] - 10) < 1e-9 and got["loss"] is None and got["zero"] is None and got["gap"] is None
    assert abs(got["pp"] - 0.5) < 1e-9 and got["m"] == [30, None]


def test_takeaways_say_what_the_chart_shows(tmp_path):
    got = fv(tmp_path, """
      const L = ['FY25', 'FY24', 'FY23'];
      print(JSON.stringify({
        profit: F.profitLine([416161e6, 391035e6], [112010e6, 93736e6], L),
        quarter: F.profitLine([109417e6, 1, 1, 1, 94036e6], [29789e6, 1, 1, 1, 23434e6], ['Q3 FY26', 'a', 'b', 'c', 'Q3 FY25'], 4, 'the same quarter a year before'),
        margin: F.marginLine('Operating margin', [32.0, 31.5], L),
        flat: F.marginLine('Net margin', [26.9, 26.93], L),
        loss: F.profitLine([100e6, 90e6], [-5e6, 2e6], L),
        twd: F.growthLine('Revenue', [3809054e6, 2894307e6], ['2025', '2024'], 1, '', F.moneyIn('TWD')),
      }));
    """)
    assert got["profit"] == "Revenue rose 6.4% to $416.2B in FY25, from $391.0B in FY24. Net income rose 19.5% to $112.0B."
    assert "from $94.0B in Q3 FY25, the same quarter a year before" in got["quarter"]
    assert got["margin"] == "Operating margin was 32.0% in FY25, up 0.5 percentage points from 31.5% in FY24."
    assert got["flat"] == "Net margin was 26.9% in FY25, unchanged from FY24."
    assert "The company lost $5.0M in the period." in got["loss"] and "%" not in got["loss"].split("Net")[0].split("The company")[1] if "Net" in got["loss"] else True
    assert got["twd"].startswith("Revenue rose 31.6% to TWD 3.81T in 2025") and "$" not in got["twd"]


def test_a_cash_flow_bridge_only_when_the_figures_reconcile(tmp_path):
    got = fv(tmp_path, """
      print(JSON.stringify({ ok: F.bridges(111482e6, -12715e6, 98767e6), off: F.bridges(111482e6, -12715e6, 90000e6), gap: F.bridges(111482e6, null, 98767e6),
        line: F.cashFlowLine([111482e6, 118254e6], [-12715e6, -9447e6], [98767e6, 108807e6], ['FY25', 'FY24']),
        noBridge: F.cashFlowLine([111482e6], [-12715e6], [90000e6, 80000e6], ['FY25', 'FY24']) }));
    """)
    assert got["ok"] is True and got["off"] is False and got["gap"] is False
    assert got["line"] == "Free cash flow was $98.8B in FY25: $111.5B from operations less $12.7B of capital spending, down 9.2% from $108.8B in FY24."
    assert "which is not the statement's figure, so no bridge is drawn" in got["noBridge"]


def test_net_cash_reconciles_with_its_parts(tmp_path):
    got = fv(tmp_path, """
      print(JSON.stringify({ n: F.netCash(35934e6, 98657e6, -62723e6), bad: F.netCash(10e9, 5e9, 9e9), line: F.netCashLine([35934e6, 23646e6], [98657e6, 132480e6], ['FY25', 'FY22']) }));
    """)
    assert abs(got["n"]["net"] + 62723e6) < 1 and got["n"]["matches"] is True and got["bad"]["matches"] is False
    assert got["line"] == "Net debt of $62.7B at the end of FY25: $35.9B of cash and equivalents against $98.7B of debt. Debt fell from $132.5B at the end of FY22."


def test_a_total_line_among_its_parts_is_left_out_not_counted_twice(tmp_path):
    got = fv(tmp_path, """
      // Apple FY25 by product: "Product" is iPhone + Mac + iPad + Wearables
      const m = ['Mac', 'Product', 'Service', 'Wearables', 'iPad', 'iPhone'], v = [33708e6, 307003e6, 109158e6, 35686e6, 28023e6, 209586e6];
      const c = F.composition(m, v, 416161e6);
      const short = F.composition(['A', 'B'], [60, 30], 100);   // parts that fall short of the total are not scaled up
      const neg = F.composition(['Americas', 'Corporate'], [72.5, -42.6], 29.9);
      print(JSON.stringify({ dropped: c.dropped, labels: c.rows.map((r) => r.label), sum: c.sum, rec: c.reconciles, line: F.compositionLine(c, 'Revenue', 'FY25'),
        short: [short.reconciles, short.gap, F.compositionLine(short, 'Revenue', 'FY25')], neg: [neg.canShare, neg.reconciles] }));
    """)
    assert got["dropped"] == ["Product"] and got["labels"][0] == "iPhone" and got["rec"] is True and abs(got["sum"] - 416161e6) < 1e6
    assert got["line"] == "iPhone was the largest, $209.6B or 50% of revenue in FY25. The parts add to the $416.2B reported."
    assert got["short"][0] is False and got["short"][1] == 10 and "against $100 reported; the $10 difference is not assigned to a part" in got["short"][2]
    assert got["neg"] == [False, True], "a negative part: no shares of a whole"


def test_surprises_are_read_one_way_every_quarter(tmp_path):
    got = fv(tmp_path, """
      print(JSON.stringify({ beat: F.surprise(1.89, 2.02, 6.7), miss: F.surprise(2.0, 1.9), inline: F.surprise(1.50, 1.502), tiny: F.surprise(0.02, 0.05),
        none: F.surprise(null, 1.2), after: (await import('""" + (JS / "pages/earnings.js").as_posix() + """')).afterBeats([{ cls: 'beat', next_day_move_pct: -7.35 }, { cls: 'beat', next_day_move_pct: 3.24 }, { cls: 'miss', next_day_move_pct: -1 }]) }));
    """)
    assert got["beat"]["cls"] == "beat" and got["beat"]["pct"] == 6.7 and abs(got["beat"]["diff"] - 0.13) < 1e-9
    assert got["miss"]["cls"] == "miss" and abs(got["miss"]["pct"] + 5) < 1e-9
    assert got["inline"]["cls"] == "in line" and got["inline"]["pct"] == 0
    assert got["tiny"]["cls"] == "beat" and got["tiny"]["pct"] is None and got["tiny"]["small"] is True, "no percentage of a near-zero estimate"
    assert got["none"]["cls"] == "missing"
    assert got["after"]["n"] == 2 and got["after"]["fell"] == 1 and abs(got["after"]["avg"] + 2.055) < 1e-9


def test_bars_stand_on_zero_leave_gaps_and_keep_labels_apart(tmp_path):
    got = fv(tmp_path, """
      const g = [{ x: '2021' }, { x: 'FY22' }, { x: 'FY23' }, { x: 'FY24' }];
      const h = B.groupedBars(g, [{ name: 'A', cls: 's1', values: [null, 100, null, 120] }, { name: 'B', cls: 's2', values: [null, 100, 90, 119] }], { w: 400, h: 200 }).html;
      const t = B.niceTicks(-12.7, 111.5, 4), e = B.groupedBars(g, [{ name: 'A', values: [null, null, null, null] }]).html;
      const flat = B.periodLines([{ x: 'a' }, { x: 'b' }], [{ name: 'S', cls: 's2', values: [5186e6, 5187e6] }], { w: 400, zero: false }).html;
      const ticks = [...flat.matchAll(/class="ax" x="[^"]+" y="[^"]+" text-anchor="end">([^<]+)</g)].map((m) => m[1]);
      // four equal bars in a narrow last period: their labels would sit on each other
      const crowd = B.groupedBars([{ x: 'Q1' }, { x: 'Q2' }], ['s1', 's2', 's3', 's0'].map((c) => ({ name: c, cls: c, values: [1, 1234567] })), { w: 280, h: 200, valueLabels: 'last' }).html;
      const boxes = [...crowd.matchAll(/class="vlab" x="([^"]+)" y="([^"]+)" text-anchor="middle">([^<]+)</g)].map((m) => ({ x: +m[1], y: +m[2], w: m[3].length * 6.6 }));
      const overlap = boxes.some((a, i) => boxes.some((b, j) => i < j && Math.abs(a.x - b.x) < (a.w + b.w) / 2 && Math.abs(a.y - b.y) < 13));
      print(JSON.stringify({ trimmed: !h.includes('>2021<'), gap: (h.match(/gap-mark/g) || []).length, zeroLine: h.includes('class="zero"'),
        ticks: t, empty: e, kept: boxes.length, overlap, flatTicks: ticks }));
    """)
    assert got["trimmed"], "a period with no figure at either end is not drawn"
    assert got["gap"] == 1, "the missing FY23 A is a gap, not a zero bar"
    assert got["zeroLine"] and got["ticks"][0] < 0 and 0 in got["ticks"], "magnitudes from a zero baseline"
    assert got["empty"] == "", "nothing to draw draws nothing"
    assert 1 <= got["kept"] < 4 and not got["overlap"], "labels that would overlap are left out (the tooltip and table keep them)"
    assert len(set(got["flatTicks"])) == len(got["flatTicks"]) > 1, "a count that barely moved gets a scale it can be read on"


def test_the_charts_print_no_numbers_the_readout_carries_them(tmp_path):
    # the owner (2026-10-20): "hide the numbers, i can see when hovering over it"
    got = fv(tmp_path, """
      const g = [{ x: '2024' }, { x: '2025' }];
      const gb = B.groupedBars(g, [{ name: 'Revenue', cls: 's1', values: [3e9, 4.5e9] }], { w: 400 });
      const pl = B.periodLines(g, [{ name: 'Margin', cls: 's2', values: [35.7, 46.8] }], { w: 400 });
      const br = B.bridgeBars([{ x: 'Operations', v: 1.6e9, kind: 'total' }, { x: 'Capital spending', v: -54e6 }, { x: 'Free cash flow', v: 1.55e9, kind: 'total' }], { w: 400 });
      const st = B.stackedBars(g, [{ name: 'A', cls: 's1', values: [2, 3] }, { name: 'B', cls: 's2', values: [1, 1] }], { w: 400, fmt: String });
      // a caller that asks for labels still gets them
      const asked = B.groupedBars(g, [{ name: 'Revenue', cls: 's1', values: [3e9, 4.5e9] }], { w: 400, valueLabels: 'all' }).html;
      const tips = (m, k) => { const out = []; const el = { querySelector: () => el, nextElementSibling: { style: {}, set innerHTML(v) { out.push(v); }, offsetWidth: 100 }, querySelectorAll: () => [], getBoundingClientRect: () => ({ width: 400, left: 0 }), matches: () => true,
        addEventListener: (t, f) => { if (t === 'keydown') el.key = f; if (t === 'focus') el.focus = f; } }; m.wire({ querySelector: () => el }); el.focus(); el.key({ key: k, preventDefault() {} }); return out; };
      print(JSON.stringify({ labels: [gb, pl, br, st].map((c) => (c.html.match(/class="vlab/g) || []).length), asked: (asked.match(/class="vlab/g) || []).length,
        bridgeTip: tips(br, 'ArrowLeft'), stackTip: tips(st, 'End') }));
    """)
    assert got["labels"] == [0, 0, 0, 0], "no figures printed on grouped bars, lines, the bridge or stacked bars"
    assert got["asked"] == 2
    assert got["bridgeTip"][0].startswith("<b>Free cash flow</b>"), "focus from the keyboard opens the readout on the newest period"
    assert got["bridgeTip"][1].startswith("<b>Capital spending</b> <span>−") and "54" in got["bridgeTip"][1], "a step keeps its sign in the readout"
    assert any("Total <b>4</b>" in t for t in got["stackTip"]), "the readout names the total a stacked bar no longer prints"
    for f in ("pages/earnings.js", "ui/finfigs.js"):
        assert "valueLabels: 'all'" not in (JS / f).read_text(), f


def test_the_series_colours_are_validated_and_kept_per_metric():
    assert "--c-s1: #5b7fbf; --c-s2: #c27a2c; --c-s3: #c75b88;" in TOKENS and "dataviz validator" in TOKENS
    assert "{ name: 'Revenue', cls: 's1'" in FIN and "{ name: 'Net income', cls: 's3'" in FIN and "{ name: 'Free cash flow', cls: 's3'" in FIN
    assert "{ name: 'Revenue', cls: 's1'" in EARN and "{ name: 'Net income', cls: 's3'" in EARN
    assert ".gbar.hollow { fill: none;" in CSS, "an estimate is hollow, never told apart by colour alone"


def test_financials_figures_and_their_data():
    st = FIN[FIN.index("function statements(sym) {"):FIN.index("function statementCharts()")]
    for h in ("Revenue and profit", "Margins", "Cash flow", "Cash and debt", "Per share"):
        assert f"<h3>{h}</h3>" in st, h
    assert '<details class="more-inline fv-data"><summary>View data</summary>' in st, "the table one step away"
    assert "The statements Optic reads carry no quarterly cash flow" in st and "Fiscal years, ${ccyWords()}" in st
    assert "usd = FV.moneyIn(ccy);" in FIN and "financial_currency" in FIN, "statements in the currency they are filed in"
    assert "FV.bridges(o, c, fc)" in FIN, "a waterfall only when the figures reconcile"
    seg = FIN[FIN.index("function segments() {"):FIN.index("function paint() {")]
    assert "FV.composition(" in seg and "is a total of other lines here, so it is left out rather than counted twice" in seg
    assert "if (!c.canShare) return;" in seg, "stacked composition only for parts at or above zero"


def test_the_server_reads_the_lines_behind_the_charts():
    from app.analytics.fundamentals import analyse_financials
    raw = {"income_annual": {"periods": ["2025-09-30", "2024-09-30"], "rows": {"Total Revenue": [416.0, 391.0], "Net Income": [112.0, 94.0], "Diluted Average Shares": [15.0, 15.4]}},
           "income_quarterly": {"periods": ["2026-06-30"], "rows": {"Total Revenue": [109.0], "Diluted Average Shares": [14.7]}},
           "balance_annual": {"periods": ["2025-09-30", "2024-09-30"], "rows": {"Cash And Cash Equivalents": [35.9, 29.9], "Total Debt": [98.7, 106.6]}},
           "cashflow_annual": {"periods": ["2025-09-30", "2024-09-30", "2023-09-30"], "rows": {"Operating Cash Flow": [111.5, 118.3, 110.5], "Capital Expenditure": [-12.7, -9.4, -11.0], "Free Cash Flow": [98.8, 108.8, 99.6]}}}
    f = analyse_financials(raw)
    a = f["annual"]
    assert a["operating_cash_flow"] == [111.5, 118.3] and a["capital_expenditure"] == [-12.7, -9.4], "on the income statement's years"
    assert a["diluted_shares"] == [15.0, 15.4] and f["quarterly"]["diluted_shares"] == [14.7]
    assert f["balance_history"] == {"cash": [35.9, 29.9], "total_debt": [98.7, 106.6]}


def test_earnings_leads_with_the_newcomers_questions():
    hero = EARN[EARN.index("function hero(sym) {"):EARN.index("// What Optic's earnings verdict")]
    # the date's status is Yahoo Finance's, said through core/reports.js; no session for a report not yet made (B1.9)
    assert "reports on ${longDate(nr.date)}</b>" in hero and "${RP.dateStatus(nr)}" in hero and "so it may move" in hero
    assert "${term('earnings report', 'earnings report')}" in hero and "${term('earnings per share', 'earnings per share')} (${term('eps', 'EPS')})" in hero
    assert "But the share price fell after ${ab.fell} of those ${ab.n} beats" in hero and "Beating estimates does not mean the price rises" in hero
    order = EARN[EARN.index("else body = html`${hero(sym)}"):]
    assert order.index("history(sym)") < order.index("pricing(sym)") and order.index("growth()") < order.index("pricing(sym)"), "options last"
    hist = EARN[EARN.index("function history(sym) {"):EARN.index("// What options price for the report day")]
    assert "After-hours and longer moves are not in this data." in hist and "${moves.length} reports." in hist, "the window and the sample"
    opt = EARN[EARN.index("function pricing(sym) {"):EARN.index("function revisions(sym) {")]
    assert "for the report day itself" in opt and "so it is not the report day's move and is not compared with one" in opt
    assert "One session each: the past moves and the priced move cover the same window." in opt
    assert "not a forecast or a guaranteed range" in opt
    mk = EARN[EARN.index("function makers() {"):EARN.index("function paint() {")]
    assert "hollow: true" in mk and "sub: 'Estimate'" in mk, "estimates drawn hollow and named"


def test_a_term_explains_itself_on_tap_and_keyboard(tmp_path):
    got = fv(tmp_path, """
      const D = await import('""" + (JS / "core/dom.js").as_posix() + """'), s = (x) => D.toString(x);
      print(JSON.stringify({ eps: T.define('eps'), cap: T.define('market cap'), bps: T.define('basis points'), none: T.define('flux capacitor'),
        btn: s(T.term('eps', 'EPS')), plain: s(T.term('flux capacitor', 'flux')) }));
    """)
    assert "profit for a period divided by its number of shares" in got["eps"]["def"] and got["eps"]["ex"].startswith("A company that earns $10 million")
    assert "share price times the number of shares" in got["cap"]["def"]
    assert got["bps"]["def"] and "25 basis points" in got["bps"]["ex"], "the classic glossary's words, with an illustration"
    assert got["none"] is None and "data-v2-term" not in got["plain"], "no definition: plain text, no dead control"
    assert 'type="button" class="term" data-v2-term=' in got["btn"] and 'aria-expanded="false"' in got["btn"]
    src = (JS / "ui/term.js").read_text()
    assert "e.key === 'Escape' && pop" in src and "from.focus(" in src and "<span>Illustration:</span>" in src
    assert ".term:focus-visible" in CSS and ".term-pop-x { justify-self: end; min-height: var(--tap);" in CSS


def test_milo_names_a_figure_and_optic_draws_it_from_its_own_data(tmp_path):
    got = _run(tmp_path, f"""
      const M = await import('{(JS / "core/milo-text.js").as_posix()}');
      const r = M.renderAnswer("Revenue grew.\\n\\n[[figure revenue AAPL]]\\n\\n[[figure eps AAPL]]\\n\\n[[figure segments AAPL]]\\n\\n[[figure stock AAPL]]", 'AAPL');
      print(JSON.stringify({{ html: r.html, copy: M.sourcesAsText("A [[figure revenue AAPL]] b") }}));
    """)
    h = got["html"]
    assert h.count('class="milo-fig"') == 2, "two figures an answer at most"
    assert 'data-v2-milo-fig="revenue" data-sym="AAPL"' in h and 'data-v2-milo-fig="eps"' in h and "[[figure stock" in h, "an unknown kind is not a figure"
    assert "<p><figure" not in h, "a tag alone in its paragraph becomes the figure itself"
    assert "[[figure" not in got["copy"], "Copy leaves the tag out"
    ff = (JS / "ui/finfigs.js").read_text()
    assert "drawn by Optic, not by Milo" in (JS / "ui/milo.js").read_text()
    assert "FV.profitLine(" in ff and "FV.composition(" in ff and "FV.surprise(" in ff, "the same takeaway rules as the pages"
    assert "return missing(" in ff and "No figure: ${f.missing}" in (JS / "ui/milo.js").read_text(), "no data: said, nothing drawn"
    assert "nothing a model wrote is plotted" in ff.lower()
    prompt = (V2.parent.parent / "app/ai.py").read_text()
    assert "`[[figure KIND SYMBOL]]`" in prompt and "it never uses\nnumbers from your text" in prompt


def test_options_draws_its_term_structure():
    pc = (JS / "pages/options-panels.js").read_text()
    assert "export function pricingCharts(t)" in pc and "sub: i === firstEvent ? 'Report' : ''" in pc and "zero: false" in pc
    assert "['What options are pricing', (t, s) => P.pricing(t, s), (t) => P.pricingCharts(t)]," in (JS / "pages/options.js").read_text()
