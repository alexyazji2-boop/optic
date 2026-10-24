"""Phase 2 of the motion proposal (2026-10-24), held in place, one block per piece as it ships.

Measured in headless Chromium by ~/Optic/work/motion-pass-2026-10-24/p2check.mjs; the wiring is read as text here,
as the other v2 contract tests do.
"""
import re

from tests.test_frontend_v2_stage0 import V2

JS = V2 / "js"
APP = (JS / "app.js").read_text()
PALETTE = (JS / "ui/palette.js").read_text()
SHORTCUTS = (JS / "ui/shortcuts.js").read_text()
SETTINGS = (JS / "pages/settings.js").read_text()
PC = (JS / "ui/pricechart.js").read_text()
MILO = (JS / "ui/milo.js").read_text()
WL = (JS / "pages/watchlist.js").read_text()


# ------------------------------------------------------------ the shortcut sheet

def test_question_mark_opens_the_list_outside_a_field():
    assert "e.key === '?' && !typing && !e.metaKey && !e.ctrlKey && !drawer.isOpen() && !palette.isOpen()" in APP
    assert "openShortcuts(document.activeElement)" in APP
    assert "data-v2-shortcuts" in SETTINGS and "if ((b = t('[data-v2-shortcuts]'))) { openShortcuts(b); return; }" in APP
    assert "label: 'Keyboard shortcuts'" in PALETTE


def test_every_key_on_the_list_is_one_the_code_handles():
    # the list must not promise a key nobody listens for
    handled = {
        "'K'": "e.key.toLowerCase() === 'k'" in APP,
        "'/'": "e.key === '/'" in APP,
        "'?'": "e.key === '?'" in APP,
        "'>'": "q.startsWith('>')" in PALETTE,
        "'M'": "(k === 'm' || k === 'M')" in PC,
        "'Home', 'End'": "k === 'Home'" in PC and "k === 'End'" in PC,
        "'Delete'": "(k === 'Delete' || k === 'Backspace') && sel >= 0" in PC,
        "'+', '−'": "k === '+' || k === '='" in PC and "k === '-' || k === '_'" in PC,
        "'Shift', 'Enter'": "Shift+Enter" in MILO or "shiftKey" in MILO,
        "'↑', '↓'": "ArrowDown" in WL and "ArrowUp" in WL,
    }
    for keys, ok in handled.items():
        assert keys in SHORTCUTS, keys
        assert ok, f"{keys} is listed but not handled"


def test_the_prefix_searches_no_companies():
    block = PALETTE[PALETTE.index("if (q.startsWith('>')) {"):PALETTE.index("const upper = q.toUpperCase()")]
    assert "/api/search" not in block and "openMilo" not in block and "return rows;" in block
    assert "pages and actions" in PALETTE, "the palette's foot names the prefix"


# ------------------------------------------------------------ Home's link markers

WS = (JS / "pages/workspace.js").read_text()
PAGES_CSS = (V2 / "css/pages.css").read_text()


def test_a_linked_panel_says_what_it_follows_and_can_be_unlinked():
    chip = WS[WS.index("function linkChip(id)"):WS.index("function panelShell(")]
    assert "Follows ${S.link}" in chip and "Kept on ${own}" in chip and 'data-ws-pin="${id}"' in chip
    assert "${p.linked ? linkChip(x.id) :" in WS
    assert "data-ws-pin=\"${x.id}\"" in WS, "the panel's menu offers it too"


def test_a_kept_panel_loads_its_own_ticker_and_keeps_it():
    assert "const symOf = (id) => (PANELS[id] && PANELS[id].linked && ps(id).pin) || S.link;" in WS
    assert "const linkAt = symOf(id);" in WS and "const d = await p.load(linkAt, P);" in WS
    assert "PANELS[x.id].linked && !ps(x.id).pin).forEach" in WS, "a new link leaves kept panels alone"
    assert "...(PANELS[id] && PANELS[id].linked ? ['pin'] : [])" in WS, "the kept ticker is saved with the layout"


def test_the_marker_is_a_squared_control_not_a_pill():
    rule = PAGES_CSS[PAGES_CSS.index(".ws-linkchip {"):]
    rule = rule[:rule.index("}")]
    assert "var(--r-xs)" in rule and "--r-pill" not in rule


# ------------------------------------------------------------ the ticker More menu

COMPANY = (JS / "ui/company.js").read_text()
FRAME = (JS / "pages/dossier-frame.js").read_text()


def test_one_more_menu_for_a_ticker():
    menu = COMPANY[COMPANY.index("export function tickerMenu("):COMPANY.index("// Pieces about one company")]
    for item in ("Set an alert", "Compare", "Export research sheet", "Show on Home", "Copy ticker", "Copy price and time"):
        assert item in menu, item
    assert "${tickerMenu(sym)}" in FRAME and "tickerMenu(sym, { price: null })" in COMPANY


def test_copy_takes_the_figure_on_screen_with_its_time():
    fn = APP[APP.index("async function copyFrom(b)"):APP.index("function wireGlobal()")]
    assert "box.querySelector('.dh-px, .t-display')" in fn and ".dh-ext" in fn, "the price and the words that date it"
    assert "No price for ${sym} on screen yet." in fn, "nothing is copied when nothing is shown"
    assert "navigator.clipboard.writeText(text)" in fn and "menu.open = false" in fn


def test_the_header_menu_opens_from_its_button_on_a_wide_screen():
    assert "@media (min-width: 861px) { .acts-more > .menu-body.menu-end { left: auto; right: 0;" in PAGES_CSS
    assert ".acts-more .menu-phone { display: none; }" in PAGES_CSS


# ------------------------------------------------------------ SEC filing marks

CHART = (JS / "pages/chart.js").read_text()


def test_filing_marks_come_from_the_edgar_list_on_their_filing_dates():
    fn = CHART[CHART.index("function filings() {"):CHART.index("function filingNote()")]
    assert "(D.t || {}).filings" in fn and "Date.parse(f.filed)" in fn and "From SEC EDGAR." in fn
    assert "filings: filings()," in CHART
    assert "['filings', 'SEC filings']" in CHART and "['msb', 'events', 'ins', 'filings', 'sessions']" in CHART
    assert "overlays: { ma: true," in CHART and "filings: true" not in CHART.split("const d = {")[1].split("};")[0], "off by default"


def test_the_chart_says_only_the_latest_are_marked_and_why_a_fund_has_none():
    note = CHART[CHART.index("function filingNote()"):CHART.index("function events()")]
    assert "older ones are not marked" in note and "fl.available === false" in note
    assert "if (k === 'filings' && D.t && D.t.filings && D.t.filings.available === false)" in CHART
    assert "afterTicker(); paintTools(); }" in CHART, "the menus learn it once the ticker data is in"


def test_the_marks_are_drawn_named_and_counted():
    assert "if (S.overlays.filings && (S.filings || []).length) {" in PC
    assert '<g class="fim">' in PC and "<title>${esc(f.label)}</title>" in PC
    assert "x - lastX >= 34 && x - 14 > legW" in PC, "crowded labels and labels under the legend are left off"
    assert "SEC filing${fileMarks.length === 1 ? '' : 's'} marked." in PC
    assert 'class="pc-fil"' in PC, "the readout names a filing on the bar being read"
