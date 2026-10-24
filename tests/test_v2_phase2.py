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
