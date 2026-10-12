"""Milo's greeting is on screen when the panel opens on a phone (2026-10-12).

"fix the phone chat greeting so it shows without scrolling and make the 'ask
milo' text a little smaller". Measured in headless Chrome at 390x844: the
notice was 179px of a 363px scroller and the footer 307px, so the greeting
(450-532px) sat under the footer (485px). After: the notice folds to two lines
on a phone (67px), the footer is 253px, and the greeting (338-420px) is clear
of it (539px).
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
CSS = re.sub(r"/\*.*?\*/", "", (ROOT / "static/styles.css").read_text(), flags=re.S)


def test_the_notice_folds_on_a_phone_and_only_there():
    assert '<p class="pulse-legal-text caveat">${LEGAL.areas.pulse}</p>' in APP
    fn = APP[APP.index("function foldPulseLegal() {"):]
    fn = fn[:fn.index("\n}\n")]
    assert "matchMedia(CHAT_PHONE_QUERY).matches" in fn
    assert "markClampedCaveats(document.getElementById('pulse-legal'))" in fn
    assert "const CHAT_PHONE_QUERY = '(max-width: 640px)';" in APP
    opener = APP[APP.index("$('#chat-toggle').addEventListener('click', () => {"):]
    assert "foldPulseLegal();" in opener[:opener.index("});")]


def test_the_phone_footer_is_one_row_of_actions_and_a_shorter_box():
    at = CSS.index("#chat .chat-foot textarea { height: 52px; min-height: 52px; }")
    media = CSS.rfind("@media", 0, at)
    assert CSS[media:CSS.index("{", media)].strip() == "@media (max-width: 640px)"
    block = CSS[media:CSS.index("\n}\n", at)]
    assert "#chat .chat-actions { flex-wrap: nowrap;" in block
    assert "#chat .chat-actions label { margin-left: auto; white-space: nowrap; }" in block


def test_the_ask_milo_label_is_a_step_smaller():
    rule = re.search(r"\n#chat-toggle \{([^}]*)\}", CSS).group(1)
    assert "font-size: var(--t-base);" in rule
