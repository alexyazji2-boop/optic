"""Two small fixes reported from the live site on 2026-10-08.

1. "entering the tab button should load the prompt": Tab in an empty Pulse box
   drafts the example its placeholder quotes.
2. A collapsible pane's header band stopped short of the pane's top edge with
   the gold notch under the title, and "Long-Term View  · AAPL" had a doubled
   space before the dot.
"""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
CSS = (ROOT / "static/styles.css").read_text()
HTML = (ROOT / "static/index.html").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _fn(name):
    at = APP.index("function %s(" % name)
    return APP[at:APP.index("\n}\n", at) + 3]


def test_the_placeholder_example_becomes_the_draft():
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    ph = re.search(r'id="chat-input" placeholder="([^"]*)"', HTML).group(1).replace("&quot;", '"')
    script = _fn("pulsePlaceholderAsk") + (
        "print('RESULT:' + JSON.stringify([pulsePlaceholderAsk({placeholder: %s}),"
        " pulsePlaceholderAsk({placeholder: 'Pulse is unavailable'}), pulsePlaceholderAsk(null)]));"
        % json.dumps(ph))
    out = subprocess.run([exe, "-e", script], capture_output=True, text=True, timeout=60)
    got = json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])
    assert got == ["What does the gamma profile imply for a swing long here?", "", ""]


def test_tab_drafts_only_into_an_empty_box_and_never_traps_focus():
    handler = APP[APP.index("$('#chat-input').addEventListener('keydown'"):]
    handler = handler[:handler.index("\n});\n")]
    assert "evt.key === 'Tab' && !evt.shiftKey" in handler
    assert "if (box.value.trim()) return;" in handler, "with text in the box Tab moves on"
    assert "if (!ask) return;" in handler, "no example, no capture"
    assert handler.index("if (!ask) return;") < handler.index("evt.preventDefault();\n    box.value = ask;")


def test_a_collapsible_panes_band_reaches_its_top_edge():
    rule = CSS[CSS.index(".panel > h2:first-child,\n.panel.is-open > h2.is-toggle:first-child {"):]
    rule = rule[:rule.index("}")]
    assert "padding-top: calc(var(--ws-pad) - 2px);" in rule
    assert "margin-top: calc(-1 * var(--ws-pad));" in rule


def test_the_title_and_its_symbol_sit_a_word_space_apart():
    rule = CSS[CSS.index(".panel > h2.is-toggle {"):]
    rule = rule[:rule.index("}")]
    assert "column-gap: 0.3em;" in rule and "  gap: var(--space-2);" not in rule
    assert ".panel > h2.is-toggle > .ask-pulse { margin-left: var(--space-1); }" in CSS
