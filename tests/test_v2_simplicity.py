"""The Phase 04 simplicity pass, held in place (post-demo overhaul, directive 04; SIMPLICITY_AUDIT.md).

Each test names the finding it keeps fixed: a time on every page that shows market figures (registry B X-10), the
Desk's own time (H-2), one word per model (X-6, X-7), colour only where a reader acts on it (BUG-077), controls that
answer every press (BUG-075), a long list that starts short, and no second, unrouted Home page (X-2). The pages were
also checked rendered, in headless Chrome, by ~/Optic/work/post-demo-ultra-2026-10-29/tools/density.py and
deadclicks.py (TEST_RESULTS.md, Phase 04).
"""
from pathlib import Path

from tests.test_frontend_v2_stage0 import V2, _run

ROOT = Path(__file__).resolve().parents[1]
JS = V2 / "js"
src = lambda p: (JS / p).read_text()   # noqa: E731


def test_a_time_is_said_the_same_way_everywhere(tmp_path):
    got = _run(tmp_path, f"""
      localStorage.setItem('optic.timezone', 'America/New_York');
      const s = await import('{(JS / "ui/states.js").as_posix()}');
      const dom = await import('{(JS / "core/dom.js").as_posix()}');
      const now = new Date(), iso = now.toISOString();
      print(JSON.stringify({{ day: s.whenText('2026-10-28'), none: s.whenText(''), bad: s.whenText('soon'),
        today: s.whenText(iso), old: s.whenText('2026-01-05T15:30:00Z'), line: dom.toString(s.asOfLine('2026-10-28', {{ what: 'Weekly closes' }})),
        empty: dom.toString(s.asOfLine(null)) }}));
    """)
    assert got["day"] == "through Oct 28" and got["none"] == "" and got["bad"] == ""
    assert got["today"].startswith("as of ") and "," not in got["today"] and got["today"].endswith(("EDT", "EST"))
    assert got["old"] == "as of Jan 5, 10:30 AM EST"
    assert got["line"] == '<p class="asof">Weekly closes through Oct 28.</p>' and got["empty"] == ""


def test_the_five_pages_that_had_no_time_now_say_one():
    assert "asOfLine(D.m.generated_at, { note: 'From delayed quotes and daily closes.' })" in src("pages/macro.js")
    ind = src("pages/indices.js")
    assert "asOfLine(through, { what: 'Weekly closes', note: open ? 'This week counts at the latest price.' : '' })" in ind
    assert "const open = newest > today," in ind, "the current week's bar carries its Friday's date, not a day that has passed"
    ex = src("pages/explore.js")
    assert "asOfLine((b.basis || {}).price_as_of, { what: 'Prices' })" in ex and "asOfLine((D.home || {}).generated_at, { what: 'Moves'" in ex
    assert "`Last price ${whenText(sn.quote_as_of || d.generated_at)}. `" in src("pages/instrument.js")
    assert "asOfLine(c.generated_at, { what: 'Compared'" in src("pages/compare.js")
    # the sector and index fund boards on Macro and Indices name their price time and kind
    assert "`Prices ${whenText(board.basis.price_as_of)}" in src("pages/market-shared.js")


def test_the_desk_footer_says_when_its_words_were_written():
    ws = src("pages/workspace.js")
    desk = ws[ws.index("  desk: {\n    title: 'Optic Desk'"):ws.index("milo: 'Walk me through today\\'s Desk.'")]
    assert "at: written ? md.written_at : (d || {}).generated_at, verb: written ? 'Written' : 'Compiled'" in desk
    assert "${asof(f.at, f.verb)}" in ws and "const asof = (iso, verb = 'Updated') =>" in ws
    assert "Written before the open and after the close; this is the latest edition." not in ws, "that was the edition's cadence"
    main = (ROOT / "app/main.py").read_text()
    assert main.count('desk["written_at"] = prose.get("written_at")') == 2, "the written voice carries its time too"


def test_one_model_one_name():
    mac, read, ind, ws = src("pages/macro.js"), src("pages/read.js"), src("pages/indices.js"), src("pages/workspace.js")
    assert "<p class=\"t-label\">Optic's market score</p>" in mac and "Optic's market score" in ws
    assert "['Index score', regime]" in read and "A different measure from Optic's market score on Home and Macro" in read
    assert ">Where each index stands</h2>" in ind
    for page in (mac, read, ind):
        assert "Macro regime" not in page and "'Market regime'" not in page and ">Index regime<" not in page
    # the expected move's three figures carry one set of labels on Home and on Macro
    for label in ("Move priced by options, one day", "Typical day lately"):
        assert label in ws and label in mac
    assert "Options price, as one day" not in mac and "Priced, as one day" not in ws


def test_colour_marks_direction_not_a_firms_opinion():
    css = (V2 / "css/pages.css").read_text()
    assert ".rt { font: 600 var(--t-sm)/1 var(--f-label); color: var(--c-ink); }" in css
    assert ".rt-buy" not in css and ".rt-sell" not in css
    an = src("pages/analysts.js")
    assert '<span class="t-muted" title="Raised">↑</span>' in an and '<span class="up">↑</span>' not in an
    ws = src("pages/workspace.js")
    # real red and green since the visual update (2026-11-11): 14% to 55%, still a fixed scale, not the day's largest
    assert "a = Math.round(14 + 41 * Math.min(1, Math.abs(v) / full));" in ws, "a fixed scale, at most 55%, not the day's largest"
    assert "const full = { chg_1d: 2, chg_5d: 4, chg_20d: 8 }[P.period] || 2;" in ws


def test_presses_that_did_nothing_now_say_why():
    cmp = src("pages/compare.js")
    assert "const full = inputs.length >= MAX && inputs.every((x) => x.trim());" in cmp and "${recent.length && !full ?" in cmp
    assert "else { toast('Type a ticker to add, such as SPY.'); f.s.focus(); }" in src("pages/chart-widgets.js")
    ws = src("pages/workspace.js")
    assert "if (r.hit && r.hit.symbol === S.link) { const same = `The linked panels already show ${S.link}.`;" in ws


def test_a_week_of_analyst_actions_starts_with_forty(tmp_path):
    an = src("pages/analysts.js")
    assert "const FIRST = 40;" in an and "limit: showAll ? 0 : FIRST" in an and "data-v2-an-all>Show all ${rows.length}</button>" in an
    assert "D.err = null; showAll = false; paint();" in an, "a new query starts short again"
    got = _run(tmp_path, f"""
      const t = await import('{(JS / "ui/table.js").as_posix()}');
      const dom = await import('{(JS / "core/dom.js").as_posix()}');
      const rows = Array.from({{ length: 50 }}, (_, i) => ({{ n: i }}));
      const cols = [{{ key: 'n', label: 'N', num: true, cell: (r) => String(r.n) }}];
      const count = (h) => (dom.toString(h).match(/<tr >/g) || []).length;
      print(JSON.stringify({{ some: count(t.table(rows, cols, {{ limit: 40, sort: {{ key: 'n', dir: 'desc' }} }})), all: count(t.table(rows, cols, {{ limit: 0 }})),
        top: /<td class="n ">49</.test(dom.toString(t.table(rows, cols, {{ limit: 40, sort: {{ key: 'n', dir: 'desc' }} }}))) }}));
    """)
    assert got == {"some": 40, "all": 50, "top": True}, "40 body rows, sorted over all 50 first"


def test_read_says_why_reports_matter_once_and_the_overview_keeps_its_ids_in_the_fold():
    read = src("pages/read.js")
    assert "const reportWhy = (shown.find((e) => e.kind === 'report' && e.why) || {}).why || '';" in read
    ovr = src("pages/overview-research.js")
    head = ovr[:ovr.index("${how(html`<p>The Optic Score below")]
    assert "method_version" not in head.split("<p class=\"asof\">These four are graded separately")[-1]
    assert "<p class=\"t-muted\">Method ${out.method_version || 'not stated'}, policy ${g(out, 'policy', 'version'" in ovr


def test_liquidity_words_describe_the_whole_grade():
    from app.analytics import liquidity
    assert liquidity.LABELS == {"good": "Liquid", "fair": "Fair", "poor": "Thin", "not_tradable": "No usable quote"}
    assert "spread ${num(r.spread_pct, 1)}%</small>" in src("pages/options.js"), "the spread is named beside the word"


def test_there_is_one_home_page():
    home = src("pages/home.js")
    for gone in ("export async function render", "export function welcome", "export function starters", "export function modes",
                 "function loadHome", "function wireForms", "function scene(", "function strip(", "export const retry"):
        assert gone not in home, gone
    ws = src("pages/workspace.js")
    for gone in ("data-v2-home-ready", "t('[data-v2-mode]')", "matches('[data-ws-mode]')", "async function loadNew", "const NEW ="):
        assert gone not in ws, gone
    assert "Market conditions below sums it up too" not in ws, "the first-visit card no longer points at a panel Simple hides"
    # what Optic is, said once on the first visit (directive 04 section 4; the removed page's welcome said it)
    assert "<p class=\"ws-sub\">Prices, options, financials and filings for US stocks and funds, each figure with its source.</p>" in ws
    # one set of Follow buttons on a first screen: the empty Watchlist panel leaves them to the first-visit card
    assert "if (d.empty && showOnboard()) return html`<p class=\"ws-note\">Your open watchlist is empty. Follow a company from the card above" in ws


def test_supporting_tables_start_folded_in_simple_and_open_in_advanced(tmp_path):
    got = _run(tmp_path, f"""
      const s = await import('{(JS / "ui/states.js").as_posix()}');
      const dom = await import('{(JS / "core/dom.js").as_posix()}');
      localStorage.setItem('optic.mode.v1', 'simple');
      const simple = dom.toString(s.simpleFold('t1', 'All 12 funds, measured', 'TABLE'));
      localStorage.setItem('optic.mode.v1', 'pro');
      const adv = dom.toString(s.simpleFold('t2', 'All 12 funds, measured', 'TABLE'));
      print(JSON.stringify({{ simple, adv }}));
    """)
    assert got["simple"] == '<details class="more-inline sfold" data-v2-sfold="t1" ><summary>All 12 funds, measured</summary>TABLE</details>'
    assert '<details class="more-inline sfold" data-v2-sfold="t2" open>' in got["adv"]
    ex, ret = src("pages/explore.js"), src("pages/retirement.js")
    assert "${total ? simpleFold('explore-screens', `All ${total} screens, in ${groups.length}" in ex
    assert "simpleFold('roth-universe', `All ${(d.funds || []).length} funds, measured`" in ret and "simpleFold('roth-corr'," in ret
    st = src("ui/states.js")
    assert "closest('details[data-v2-sfold] > summary'); if (s) FOLDS.set(s.parentElement.dataset.v2Sfold, !s.parentElement.open);" in st
