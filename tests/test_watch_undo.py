"""Removing a watchlist row can be undone (launch audit, 2026-10-16).

A row's x removed the name at once with no way back but retyping it; a stray
press on the row above lost the wrong name. The x now says what it removed and
offers Undo, through the toast's one action button. The header's Watch /
Watching toggle is its own undo and does not raise the note.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
AUTH = (ROOT / "static/auth.js").read_text()


def test_the_x_offers_undo_and_the_toggle_does_not():
    assert "watchRemove(rm.dataset.watchRemove, { undo: true })" in APP
    body = APP[APP.index("function watchRemove(symbol, opts = {}) {"):]
    body = body[:body.index("\n}\n")]
    assert "label: 'Undo', run: () => watchAdd(sym)" in body
    assert "if (on) watchRemove(sym); else watchAdd(sym);" in APP


def test_the_toast_takes_one_action():
    fn = AUTH[AUTH.index("function toast(message, kind, action) {"):]
    fn = fn[:fn.index("\n  }\n")]
    assert "act.className = 'auth-toast-act'" in fn and "action.run()" in fn
    assert "e.stopPropagation()" in fn
