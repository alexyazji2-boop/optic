"""A link to #/scan?q=... never spends a reader's Milo message without a press (post-demo overhaul, Phase 02, BUG-036).

Milo's "Find stocks" card says it may use a question, so pressing it is the go-ahead: it leaves a one-time flag in
sessionStorage and the Scan page runs the request only when the flag matches, then removes it. Any other link with
?q= (a shared one, a bookmark) puts the words in the box and waits for "Find symbols now". Checked in the browser on
2026-10-29: a bare link filled the box and sent no /api/screener/ask; the card's flag ran it and was consumed.
"""
from __future__ import annotations

from pathlib import Path

JS = Path(__file__).resolve().parent.parent / "static" / "v2" / "js"


def test_only_the_card_press_runs_a_linked_scan_question():
    milo = (JS / "ui" / "milo.js").read_text()
    scan = (JS / "pages" / "scan.js").read_text()
    card = milo[milo.index("if (a.kind === 'screen')"):]
    card = card[:card.index("\n")]
    assert "sessionStorage.setItem('optic.scan.go.v1'" in card and card.index("setItem") < card.index("router.go")
    assert "const SCAN_GO = 'optic.scan.go.v1';" in scan
    gate = scan[scan.index("function pressedInMilo(q)"):]
    gate = gate[:gate.index("\n}\n")]
    assert "sessionStorage.removeItem(SCAN_GO)" in gate and "return go === q" in gate
    assert ("else if (q && pressedInMilo(q)) runAsk(q); else if (q) { S.askText = q; paint(); }" in scan)
    assert "else if (q) runAsk(q);" not in scan
