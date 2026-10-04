"""Every figure Pulse quotes says which panel it came from.

Pulse tags a figure it takes from CONTEXT with `[[src KEY]]`, KEY being the
CONTEXT key that holds it, and the terminal shows a chip naming the panel which
opens it. Only keys the terminal sends become chips; anything else is dropped.

Checked in a browser with a simulated answer (no model call): "Net GEX is
-$412m per 1%" carried a Dealer gamma chip that opened Options, beside it Pulse
stayed open on a desktop and closed on a phone at 375px; a made-up tag showed
nothing; Copy gave "(Dealer gamma)" in place of the tag.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from app import ai

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
CSS = (ROOT / "static/styles.css").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _fn(head):
    at = APP.index(head)
    return APP[at:APP.index("\n}\n", at) + 3]


def _run(script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    prelude = ("function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')"
               ".replace(/>/g, '&gt;').replace(/\"/g, '&quot;'); }\n"
               + APP[APP.index("const PULSE_SOURCES = {"):APP.index("function pulseSourcesIn(")]
               + _fn("function pulseSourcesIn(html) {") + _fn("function pulseSourcesAsText(text) {"))
    out = subprocess.run([exe, "-e", prelude + script], capture_output=True, text=True, timeout=60)
    assert "RESULT:" in out.stdout, (out.stdout + out.stderr)[-1500:]
    return json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])


def test_a_known_tag_becomes_a_chip_and_an_unknown_one_vanishes():
    html, text = _run("""
      var t = 'GEX is -$412m [[src gex]], up 1% [[src quote]], odd [[src banana]].';
      print('RESULT:' + JSON.stringify([pulseSourcesIn(t), pulseSourcesAsText(t)]));
    """)
    chips = re.findall(r'data-src-view="([a-z]+)"[^>]*>([^<]+)</button>', html)
    assert chips == [("swing", "Dealer gamma"), ("overview", "Quote")]
    assert "banana" not in html and "[[src" not in html
    assert text == "GEX is -$412m (Dealer gamma), up 1% (Quote), odd."


def test_every_source_is_a_key_the_terminal_sends_and_a_view_it_has():
    keys = re.findall(r"^  ([a-z_]+): \['", APP[APP.index("const PULSE_SOURCES = {"):APP.index("const PULSE_SRC_RE")], re.M)
    payload = _fn("function chatContextPayload() {")
    for key in keys:
        assert ("ctx.%s = " % key) in payload, key
    views = set(re.findall(r"\['[^']+', '([a-z]+)'\]", APP[APP.index("const PULSE_SOURCES = {"):APP.index("const PULSE_SRC_RE")]))
    for view in views:
        assert ("'%s'" % view) in APP[APP.index("const NAV_GROUPS = ["):] or view in (
            "overview", "chart", "swing", "long", "earnings", "news"), view
    fmt = " ".join(ai.FORMAT_PROMPT.split())
    for key in keys:
        assert key in fmt, "Pulse is told about " + key


def test_pulse_is_told_when_to_tag_and_when_not_to():
    fmt = " ".join(ai.FORMAT_PROMPT.split())
    assert "`[[src KEY]]`, where KEY is the top-level CONTEXT key that holds the figure" in fmt
    assert "Tag a source once per paragraph" in fmt
    assert "Never tag a figure that is not in CONTEXT" in fmt
    assert "—" not in ai.FORMAT_PROMPT


def test_chips_render_open_their_panel_and_leave_copy_and_save_readable():
    assert "return pulseSourcesIn(html.replace(PULSE_CHART_RE," in APP, "every reply path renders them"
    assert "if (window.matchMedia('(max-width: 559px)').matches) $('#chat-close').click();\n    switchView(src.dataset.srcView);" in APP
    assert "pulseSourcesAsText(splitFollowUps(" in APP
    assert "${pulseSourcesAsText(t.content)}" in _fn("function pulseExport() {")
    assert ".replace(/\\s?\\[\\[[^\\]\\n]*\\]\\]/g, '')" in APP, "no brackets flash past while streaming"
    assert ".pulse-src {" in CSS
