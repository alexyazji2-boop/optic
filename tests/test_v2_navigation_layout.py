"""v2 navigation and workspace (owner's overnight brief, 2026-10-19, priority 2).

Read from the page modules as text, this project's pattern for client contracts; each was also exercised
in a browser at 390 and 1440 px (~/Optic/work/v2-overnight). Names on the rail, the phone bar and the tabs
are the owner's and are checked word for word.
"""
import re

from tests.test_frontend_v2_stage0 import V2

JS = V2 / "js"
CSS = (V2 / "css/components.css").read_text() + (V2 / "css/pages.css").read_text()


def _src(rel):
    return (JS / rel).read_text()


def _fn(src, start):
    i = src.index(start)
    return src[i:src.index("\n}\n", i)]


# ------------------------------------------------------------ Home

def test_market_overview_is_in_the_owners_order():
    """Strip; regime, expected move and sectors; the ticker with Watchlist; the calendar and earnings;
    what matters today and news; the Desk; the portfolio last."""
    ws = _src("pages/workspace.js")
    line = re.search(r"market: \{ label: 'Market Overview', panels: (\[.*?\]) \}", ws).group(1)
    order = re.findall(r"\['(\w+)', \d+", line)
    assert order == ["indices", "regime", "expected", "sectors", "quote", "watch", "calendar", "earnings",
                     "priority", "news", "desk", "movers", "portfolio"]
    opts = re.findall(r"\['(\w+)', \d+", re.search(r"options: \{ label: 'Options Research', panels: (\[.*?\]) \}", ws).group(1))
    assert opts[:3] == ["quote", "watch", "contracts"], "Options Research leads with the contracts"
    lt = re.findall(r"\['(\w+)', \d+", re.search(r"longterm: \{ label: 'Long-Term Investing', panels: (\[.*?\]) \}", ws).group(1))
    assert {"biz", "value", "fin", "own"} <= set(lt[:6]), "Long-Term leads with the business and its valuation"


def test_layout_controls_show_only_while_customizing():
    ws = _src("pages/workspace.js")
    assert "let EDIT = false;" in ws
    assert "locked = !EDIT" in _fn(ws, "function panelShell")
    assert "is-editing" in ws and "data-ws-edit" in ws
    assert re.search(r"Reset", _fn(ws, "function bar(")), "Reset lives in the Customize menu"
    assert _fn(ws, "function bar(").count("data-ws-edit") == 1, "one Customize / Done toggle, not a second Done in the edit bar"


def test_first_visit_welcome_is_compact_and_dismissible():
    ws = _src("pages/workspace.js")
    assert "ONBOARD_KEY = 'optic.v2.onboard.v1'" in ws and "data-ws-onboard-done" in ws
    assert "ws-onboard" in ws


# ------------------------------------------------------------ navigation

def test_phone_bar_is_the_owners_order_and_more_lists_the_rest():
    nav = _src("nav.js")
    block = nav[nav.index("export const MOBILE_TABS = ["):]
    block = block[:block.index("];")]
    assert re.findall(r"label: '([^']+)'", block) == ["Home", "Markets", "Watchlist", "Dossier", "More"]
    assert "group: 'discover'" not in block
    assert "visibleGroups(flags).filter((g) => !shown.has(g.id))" in _src("ui/shell.js")


def test_every_tab_list_has_a_view_selector_for_a_phone():
    tabs = _src("pages/tabs.js")
    assert "tabSelect(g.label, g.pages, current, symbol)" in _fn(tabs, "export function groupTabs")
    assert "tabSelect(`${sym} Dossier`, pages, current, sym)" in _src("pages/dossier-frame.js")
    assert "select[data-v2-tabsel]" in _src("app.js")
    assert re.search(r"@media \(max-width: 640px\) \{\s*\.tabs:has\(\.tabsel\)", CSS)


def test_a_destination_is_headed_by_the_name_that_opened_it():
    """Markets opened on a page headed "Read" and Discover on one headed "Explore"."""
    for page, group, label in (("read", "market", "Read"), ("macro", "market", "Macro"), ("indices", "market", "Indices"),
                               ("explore", "discover", "Explore"), ("scan", "discover", "Scan"),
                               ("insiders", "discover", "Insiders"), ("analysts", "discover", "Analysts")):
        src = _src(f"pages/{page}.js")
        assert f"sectionHead('{group}'," in src, page
        assert f'<h1 class="t-display-m">{label}</h1>' not in src, page
    head = _fn(_src("pages/tabs.js"), "export function sectionHead")
    assert "g ? g.label" in head and "groupTabs(groupId, current, symbol)" in head


def test_ticker_actions_are_grouped_and_milo_names_the_ticker():
    frame = _src("pages/dossier-frame.js")
    acts = _fn(frame, "function actions(")
    # in a span since 2026-10-27, so the phone Chart header can show Milo's icon and keep the name for a screen reader
    assert '<span class="acts-milo-t">Ask about ${sym}</span>' in acts, "the contextual Milo differs from the top bar's Ask Milo"
    assert acts.count("btn-quiet") >= 2 and "acts-more" in acts
    assert "'Ask Milo', { ask: `What is the case" not in frame
    assert "details.menu[open]" in _src("app.js"), "an open menu closes on a click elsewhere"


# ------------------------------------------------------------ Options

def test_options_tools_sit_in_three_groups_near_the_top():
    op = _src("pages/options.js")
    ids = re.findall(r"\{ id: '(\w+)', label: '([^']+)'", op[op.index("const OPT_GROUPS"):])[:3]
    assert ids == [("contracts", "Contracts and pricing"), ("positioning", "Positioning and flow"), ("strategy", "Setups and strategy")]
    render = _fn(op, "export async function render")
    assert render.index("groupBar()") < render.index('id="op-research"') < render.index('id="op-builder"')
    # every panel the old tab row held is still on the page
    for name in ("What options are pricing", "Dealer gamma", "Flow", "Delta and gamma", "Ideas", "Strike and entry",
                 "Swing verdict", "Levels and momentum", "How value moves", "Swing setups", "Chart patterns and seasonality"):   # B6b split the last in two
        assert f"['{name}'," in op, name


def test_one_expiry_serves_the_table_and_the_builder_with_its_states():
    op = _src("pages/options.js")
    assert "data-v2-op-expiry" not in _fn(op, "function builder(")
    sel = _fn(op, "function expirySelect(")
    assert "Loading expiries" in sel and "Expiries unavailable" in sel and "disabled" in sel
    assert "${expirySelect()}" in _fn(op, "function research(")


def test_a_template_never_leaves_the_builder_spinning():
    """A template pressed before the chain loaded, or one that failed, left "Pricing the position" up."""
    tpl = _fn(_src("pages/options.js"), "async function template(")
    assert "if (!exp) { B.analyzing = false;" in tpl
    assert "B.analyzing = false; B.error = e.message;" in tpl


# ------------------------------------------------------------ Markets and Discover

def _grouped(src, groups_const, tabs_const="const TABS = ["):
    names = [a or b for a, b in re.findall(r"\[\s*(?:'([^']+)'|\"([^\"]+)\"),", src[src.index(tabs_const):src.index("];", src.index(tabs_const))])]
    block = src[src.index(groups_const):src.index("];", src.index(groups_const))]
    groups = re.findall(r"\['([^']+)', \[([^\]]*)\]\]", block)
    items = [a or b for inner in groups for a, b in re.findall(r"'([^']+)'|\"([^\"]+)\"", inner[1])]
    return names, [g for g, _ in groups], items


def test_macro_and_read_group_their_tabs_without_dropping_one():
    for page, const, n in (("macro", "const MGROUPS", 4), ("read", "const RGROUPS", 3)):
        src = _src(f"pages/{page}.js")
        names, heads, items = _grouped(src, const)
        assert "groupedTabs(" in src and "tabset(" not in src, page
        assert len(heads) == n, page
        assert sorted(items) == sorted(names) and len(items) == len(set(items)), page


def test_methodology_sits_behind_an_expansion():
    assert "How the score is built" in _src("pages/macro.js")
    read = _src("pages/read.js")
    assert "How the Read is made" in read
    assert "${readHero()}${desk()}" in read, "the day's summary comes before the Desk edition"


def test_insiders_views_have_counts_coverage_filters_and_both_dates():
    ins = _src("pages/insiders.js")
    assert "const VIEWS = [['house', 'House trades'], ['insiders', 'Insider filings'], ['contracts', 'Federal contracts']]" in ins
    assert "function count(v)" in ins and "function paint" in ins
    loadc = ins[ins.index("async function loadC"):ins.index("\n", ins.index("async function loadC"))]
    for p in ("'side'", "'member'", "'since'"):
        assert p in loadc, p
    assert "<th>Traded</th>${Q.ticker ? html`<th>Close that day</th>` : ''}<th>Filed</th>" in ins, "both dates, and the day's close when one symbol is shown"
    assert "is-partial" in ins and "Partial." in ins


# ------------------------------------------------------------ found by the four-width sweep

def test_no_row_of_choices_scrolls_sideways_out_of_sight():
    """The sweep at 768 and 390 found rows that scrolled sideways and clipped their last labels: Home's
    layout tabs, Options' templates, Scan's examples, Analysts' Show filter and Brokerage's sections."""
    ws = _src("pages/workspace.js")
    assert "data-ws-presetsel" in _fn(ws, "function bar(") and "matches('[data-ws-presetsel]')" in ws
    assert re.search(r"@media \(max-width: 640px\) \{\s*\.ws-layoutbar \.ws-presets \{ display: none; \}", CSS)
    assert ".tpl { flex-wrap: nowrap" not in CSS
    assert ".chips-scroll { flex-wrap: nowrap" not in CSS
    assert ".an-filters .seg { overflow-x: auto" not in CSS
    assert re.search(r"\.bk-tabs \{ display: grid; grid-template-columns: repeat\(3, minmax\(0, 1fr\)\)", CSS)


def test_home_contracts_say_why_a_chain_has_no_rows():
    """Overnight the panel drew an empty table under "ATM IV n/a%"; the Options page gave the reason."""
    body = _src("pages/workspace.js")
    i = body.index("  contracts: {")
    block = body[i:body.index("\n  },", i)]
    assert "d.unusable ? clean(d.unusable)" in block
    assert "isNum(sm.atm_iv_pct) && isNum(sm.straddle_move_pct)" in block
