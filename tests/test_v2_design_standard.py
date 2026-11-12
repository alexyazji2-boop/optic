"""The design standard (2026-10-19, docs/frontend-v2/DESIGN-STANDARD.md): one small system for type, radii,
surfaces, controls, figures and the use of gold, applied in the shared shell and the components every page uses,
with the Chart page's compact header as the reference. And the review's fixes that came with it: the Read's bold
markers, unavailable short interest drawn as a conclusion, two clocks said apart, Discover's line, the account
button wrapping, the chart readout under its buttons, methods folded behind "How this works".

Checked at five sizes on twelve routes (sweep2.py, 60 of 60 clean, launch audit 0 faults) and by a probe that
counts the gold on each first screen outside the charts and the sidebar: Home 3, a dossier 2, Options 3, Chart 3.
"""
import re

from tests.test_frontend_v2_stage0 import V2
from tests.test_v2_p3 import _run

ROOT = V2.parent.parent
CSS = {p.name: p.read_text() for p in (V2 / "css").glob("*.css")}
RULES = "\n".join(v for k, v in CSS.items() if k != "tokens.css")
TOK = CSS["tokens.css"]
JS = V2 / "js"


def _rule(text, sel):
    i = text.index(sel + " {")
    return text[i:text.index("}", i)]


def test_the_type_scale():
    for t in ("--t-xs: 13px;", "--t-sm: 13px;", "--t-md: 14px;", "--t-base: 15px;", "--t-lg: 16px;", "--t-xl: 18px;", "--t-lead: 20px;", "--t-2xl: 24px;"):
        assert t in TOK, t
    sizes = set(re.findall(r"font-size:\s*(\d+(?:\.\d+)?)px", RULES)) | set(re.findall(r"font:\s*\d{3}\s+(\d+(?:\.\d+)?)px/", RULES))
    assert all(float(s) >= 22 for s in sizes), f"text sizes come from the scale; only headline figures are literal: {sorted(sizes)}"
    assert not re.search(r"font-size:\s*\d+\.\d+px", RULES), "no half-pixel sizes"
    assert set(re.findall(r"font-weight:\s*(\d+)", RULES)) <= {"400", "500", "600"}


def test_the_two_faces_are_the_ones_the_page_loads():
    # index.html loads fontsource's variable packages, which declare the families "Inter Variable" and
    # "Space Grotesk Variable". The tokens named "Inter" and "Space Grotesk", which matched nothing, so every
    # reader without the fonts installed got the system face: measured on live 2026-11-02, text sat at exactly
    # system-ui's width while both downloaded faces went unused. Classic's stacks already name them this way.
    html = (V2 / "index.html").read_text()
    assert "https://cdn.jsdelivr.net/npm/@fontsource-variable/inter/opsz.css" in html
    assert "https://cdn.jsdelivr.net/npm/@fontsource-variable/space-grotesk/index.css" in html
    assert '--f-sans: "Inter Variable", "Inter", system-ui' in TOK
    assert '--f-label: "Space Grotesk Variable", "Space Grotesk", "Inter Variable"' in TOK
    named = set(re.findall(r'font-family:\s*"([^"]+)"', RULES))
    assert not named, f"faces come from the tokens, not literal families: {sorted(named)}"


def test_radii_by_what_the_shape_holds():
    assert "--r-xs: 4px; --r-sm: 6px; --r-md: 8px; --r-lg: 12px; --r-xl: 16px;" in TOK
    assert "--r-ctl: var(--r-md); --r-ctl-in: var(--r-sm);" in TOK
    literal = set(re.findall(r"border-radius:\s*(\d+(?:\.\d+)?px)", RULES))
    assert literal <= {"2px"}, f"only 2px bars and marks are literal: {literal}"
    assert "border-radius: var(--r-lg)" in _rule(CSS["pages.css"], ".ws-panel"), "a panel is a container"


def test_readable_secondary_text():
    # lifted a step again on 2026-11-11 (the visual update); the ratios are computed in tests/test_visual_update_tokens.py
    assert TOK.count("--c-ink-2: #e5e1d9; --c-ink-3: #c5c0b6;") == 2, "lifted in both dark blocks"
    assert "--c-ink-3: #5c564b;" in TOK, "and deepened in the light theme"


def test_gold_is_for_selection_and_the_one_most_important_action():
    comp = CSS["components.css"]
    assert "background: var(--c-gold); border-color: var(--c-gold); color: var(--c-on-gold);" in _rule(comp, ".btn-primary")
    milo = _rule(comp, ".btn-milo")
    assert "gold" not in milo and "border-color: var(--c-line)" in milo, "Milo inside a page is quiet"
    assert "border-color: var(--c-gold-light)" in _rule(comp, ".topbar-milo"), "the top bar's Ask Milo is the one gold entry"
    assert "gold-wash" not in _rule(comp, ".topbar-milo:hover") and "background: var(--c-sunk)" in _rule(comp, ".topbar-milo:hover"), "no gold hover outside the sidebar (owner's rule): the outline stays as it is at rest"
    assert "gold" not in comp[comp.index('.btn[aria-pressed="true"]'):comp.index("}", comp.index('.btn[aria-pressed="true"]'))], "a pressed toggle is neutral"
    assert "gold" not in _rule(comp, ".textlink"), "links are ink"
    # one selection treatment per kind: a tab has the gold bar under it, a segmented choice the active fill
    pages = CSS["pages.css"]
    for sel in ('.ws-presets button[aria-selected="true"]', '.op-groups [role=tab][aria-selected="true"], .gtabs [role=tab][aria-selected="true"]'):
        r = _rule(pages, sel)
        assert "box-shadow: inset 0 -2px 0 var(--c-gold)" in r and "border-color: transparent" in r, sel
    assert "gold" not in comp[comp.index('.seg button[aria-pressed="true"]'):comp.index("}", comp.index('.seg button[aria-pressed="true"]'))]
    assert "border-bottom-color: var(--c-gold)" in comp, "the dossier tabs, the reference"


def test_figures_line_up_and_nothing_decorates():
    assert ".kv dd, table td, table th, .dh-price, .t-display, .ws-body, .pc-read, .num" in CSS["base.css"] and "font-variant-numeric: tabular-nums" in CSS["base.css"]
    assert len(re.findall(r"(?:linear|radial)-gradient\(", RULES)) == 2, "the rail's divider and the loading shimmer only"
    assert "radial-gradient" not in RULES, "no glow"
    shadows = set(re.findall(r"box-shadow:\s*([^;}]+)", RULES))
    assert not any(re.search(r"rgba\(0,\s*0,\s*0,\s*\.(?:14|24|35)\)", s) for s in shadows), "what floats uses --sh-pop or --sh-sheet"
    assert "--sh-pop:" in TOK and "--sh-sheet:" in TOK


def test_one_icon_family_in_the_shared_panels():
    ws = (JS / "pages/workspace.js").read_text()
    for glyph in ("⠿</button>", ">?</button>", "⋯</summary>"):
        assert glyph not in ws, glyph
    assert "${icon('help')}" in ws and "${icon('grip')}" in ws and "${icon('more')}" in ws
    assert 'class="ws-ibtn ws-ask"' in ws and "btn btn-milo btn-sm ws-ask" not in ws, "the panel's Milo is a quiet icon button"
    icons = (JS / "ui/icons.js").read_text()
    assert "  help: '" in icons and "  grip: '" in icons
    assert "}>${icon('milo')}${label}</button>`;" in (JS / "ui/milo.js").read_text(), "Milo's line icon before the words"


def test_the_compact_header_on_every_dossier_tab():
    frame = (JS / "pages/dossier-frame.js").read_text()
    assert "export function header(sym, D, view = 'overview', { compact = false, bar = true, stage = null, level = null } = {}) {" in frame
    # dhead-overview: the Overview's price at the display size (visual hierarchy review, 2026-11-10, change 1)
    assert "<header class=\"dhead bar${st ? ' is-wide' : ''}${view === 'chart' ? ' dhead-chart' : ''}${view === 'overview' ? ' dhead-overview' : ''}\">${raw(logoHTML(sym, { lazy: false }))}" in frame, "the company's logo on every tab (Classic, 2026-10-25)"
    assert "${stageLine(sym, st)}${actions(sym, label, true, level)}" in frame, "the stage on the Overview's header line, with Explain"
    assert ".account-btn { flex: none; white-space: nowrap;" in CSS["components.css"], "Sign in never wraps"
    pages = CSS["pages.css"]
    # Explain and full screen are on the toolbar row since 2026-11-10, so the readout needs no room kept for them
    assert ".ch-pacts" not in pages and ".ch-tacts { display: inline-flex;" in pages, "nothing is drawn over the readout"


def test_the_reads_bold_markers_become_bold(tmp_path):
    got = _run(tmp_path, f"""
      const F = await import('{(JS / "core/format.js").as_posix()}');
      print(JSON.stringify({{ a: F.bolded('The S&P rose **+0.4%** and **3 of 11** sectors led. A stray ** goes.'), b: F.bolded('<script>**x**') }}));
    """)
    assert got["a"] == "The S&amp;P rose <b>+0.4%</b> and <b>3 of 11</b> sectors led. A stray  goes."
    assert got["b"] == "&lt;script&gt;<b>x</b>", "escaped before anything is marked"
    read = (JS / "pages/read.js").read_text()
    assert read.count("raw(bolded(") == 4 and "html`<p>${clean(p)}</p>`" not in read


def test_unavailable_short_interest_is_not_a_conclusion():
    from app.analytics.fundamentals import analyse_short_interest
    missing = analyse_short_interest({"shares_short": 1000, "short_ratio_days": 1.2}, None)
    assert missing["percent_of_float"] is None and missing["squeeze_potential"] == "not known"
    assert analyse_short_interest({"short_percent_float": 0.02}, None)["squeeze_potential"] == "low"
    fin = (JS / "pages/financials.js").read_text()
    assert "(si.percent_of_float || 0)" not in fin, "a missing share of float is not 0%"
    assert "'Share of float not reported'" in fin and "No squeeze reading without the share of float." in fin


def test_two_clocks_and_the_copy():
    read = (JS / "pages/read.js").read_text()
    assert "Prices and headlines updated ${ago(b.built_at)}" in read and "${generated(s, { at: s.written_at })}" in read and "the prices above are newer" in read
    ex = (JS / "pages/explore.js").read_text()
    assert "not a fourth thing to read" not in ex and "<h2 class=\"t-h2\" id=\"ex-r\">What is worth a look today</h2>" in ex, "the heading says it; no line restating it (editorial pass)"


def test_methods_fold_behind_how_this_works():
    states = (JS / "ui/states.js").read_text()
    assert "<details class=\"more-inline how\"><summary>How this works</summary>" in states
    op, pan = (JS / "pages/options.js").read_text(), (JS / "pages/options-panels.js").read_text()
    assert "${how((d.events || []).filter((e) => !/report/i.test(e.text || ''))" in op, "the report inside the expiry stays in view"
    assert "ITM (model) is N(d2)" in op[op.index("${how("):], "the formulas are inside the fold"
    assert "${how(html`<p>The strike chart shows the strikes with the most gamma only" in pan


def test_one_motion_system_with_tokens_and_a_still_reduced_motion_line():
    # the shared motion system (audit and motion session, 2026-10-22): tokens, one module, and a line that stands
    # still rather than vanishing under reduced motion
    from pathlib import Path
    v2 = Path(__file__).resolve().parent.parent / "static" / "v2"
    tokens = (v2 / "css/tokens.css").read_text()
    for t in ("--m-press:", "--m-content:", "--m-panel:", "--m-exit:", "--ease-out:", "--ease-drawer:"):
        assert t in tokens, t
    comp = (v2 / "css/components.css").read_text()
    assert ".page-line::before, .activity::before { animation: none !important; transform: none; width: 100%;" in comp
    motion = (v2 / "js/ui/motion.js").read_text()
    assert "if (!before || reduced()) return;" in motion, "no tab motion under reduced motion"
    assert "export const MILO_STATES" in (v2 / "js/ui/milo.js").read_text()


def test_density_and_times_follow_the_standard():
    """DESIGN-STANDARD.md, "Density and times" (post-demo Phase 04): two settings, a shared fold for supporting detail,
    one way to say a time, colour for direction only, and long lists that start short."""
    std = (ROOT / "docs/frontend-v2/DESIGN-STANDARD.md").read_text()
    assert "### Density and times (post-demo Phase 04, 2026-10-29)" in std
    states = (JS / "ui/states.js").read_text()
    for name in ("export const simpleFold = (id, summary, ...body) =>", "export function asOfLine(at, { what = 'Figures', note = '' } = {})", "export function whenText(at)"):
        assert name in states, name
    prefs = (JS / "core/prefs.js").read_text()
    assert "const DENSITY_KEY = 'optic.mode.v1';" in prefs and "export function density()" in prefs
    assert "limit" in (JS / "ui/table.js").read_text().split("export function table")[1].split("\n}")[0]
    css = (V2 / "css/pages.css").read_text()
    assert ".rt { font: 600 var(--t-sm)/1 var(--f-label); color: var(--c-ink); }" in css



def test_statement_and_segment_blocks_say_their_period_beside_their_title():
    """The periods rule (Handoff 2, DESIGN-STANDARD.md "Periods"): the blocks that print statements or segments draw
    `periodLine()`, and the written rule says what it holds. tests/test_fiscal_periods.py checks what they print."""
    std = (ROOT / "docs" / "frontend-v2" / "DESIGN-STANDARD.md").read_text()
    assert "### Periods (Handoff 2, 2026-11-03)" in std and "A fiscal-year name is never shown without its end date." in std
    for page in ("pages/financials.js", "pages/earnings.js"):
        src = (ROOT / "static" / "v2" / "js" / page).read_text()
        assert "periodLine(" in src and "from '../ui/period.js'" in src, page
