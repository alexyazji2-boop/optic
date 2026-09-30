"""Report a problem has a close button in its corner.

Asked for by a user: "There should be an X button on the Report a problem box
so I can close it, the user shouldn't need to press cancel". Checked in a
browser at 1470x785: the x sits on the title row in the panel's top-right
corner, a click closes the panel, and focus goes back to the button that
opened it, as it does on Escape.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = (ROOT / "static/index.html").read_text()
CSS = (ROOT / "static/styles.css").read_text()
APP = (ROOT / "static/app.js").read_text()


def test_the_x_is_on_the_title_row_and_is_named():
    panel = INDEX[INDEX.index('id="rp-panel"'):INDEX.index('id="rp-open"')]
    head = panel[panel.index('<div class="rp-head">'):panel.index('</div>')]
    assert 'id="rp-title"' in head
    assert re.search(r'<button type="button" class="rp-close" id="rp-close"\s+'
                     r'aria-label="Close Report a problem">&times;</button>', head)
    assert 'id="rp-cancel">Cancel</button>' in panel, "Cancel stays beside Send"


def test_it_closes_the_panel_and_hands_focus_back():
    fn = re.search(r"^function installReportPanel\(\) \{.*?^\}", APP, re.M | re.S).group()
    assert ("if (close) close.addEventListener('click', () => { closeReportPanel(); "
            "btn.focus(); });") in fn


def test_it_looks_like_the_sign_in_dialogs_close_button():
    # Shared with the free explanations' close button since they arrived.
    rule = CSS[CSS.index("\n.rp-close,\n.explain-close {"):]
    rule = rule[:rule.index("}")]
    for decl in ("width: 28px;", "height: 28px;", "background: none;", "border: 0;",
                 "font: 400 20px/1 var(--sans);", "color: var(--ink-muted);"):
        assert decl in rule, decl
    assert ".rp-close:hover,\n.explain-close:hover { background: var(--surface-2); color: var(--ink); }" in CSS
