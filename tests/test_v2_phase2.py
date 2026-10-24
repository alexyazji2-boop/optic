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
