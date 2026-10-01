"""Every panel is on the page; the level only decides which start collapsed.

Asked for as "remove the 9 panels are hidden tab, show everything but keep it
collapsed". At the default level the Options tab took its nine specialist
panels off the page, GEX, VEX, the flow and the strike recommendation among
them, and put a note at the top: "9 panels hidden on this tab". The note is
gone, the nine are on the page, and the ones above the reader's level start
collapsed. What the reader opened or closed by hand holds, and what they took
off in the chooser stays off.

Checked in a browser on NVDA's Options tab at Financially Literate: no note,
none of the 19 panels hidden, the nine collapsed, the jump bar listing GEX.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"

NINE = ["Delta analysis", "Gamma analysis", "GEX. Dealer gamma exposure",
        "VEX. Dealer vanna exposure", "Call vs put flow", "Net premium by strike",
        "Buy calls / puts", "Options strategies", "Strike & entry recommendation"]


def _piece(name):
    """One top-level function or table out of app.js, as written there."""
    for head, tail in ((f"function {name}(", "\n}\n"), (f"const {name} = ", ";\n")):
        at = APP.find("\n" + head)
        if at >= 0:
            end = APP.index(tail, at + 1) + len(tail)
            return APP[at + 1:end]
    raise AssertionError(name + " is gone from app.js")


# The panel machinery and nothing else: the whole of app.js stops loading
# under the test stubs well before these, at the first missing element.
_PIECES = ["PANEL_HIDDEN_KEY", "hiddenPanels", "setPanelHidden", "clearHiddenPanels",
           "panelId", "panelIsHidden", "PANELS_DENSE", "PANELS_SIMPLE_HIDES",
           "PANELS_ADVANCED", "panelMinLevel", "knowledgeLevel", "uiMode"]


def _run(script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    prelude = """
      var store = {};
      var localStorage = {
        getItem: function (k) { return Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null; },
        setItem: function (k, v) { store[k] = String(v); } };
      var window = { OpticKnowledge: { level: function () { return 1; } } };   // Financially Literate
    """ + "\n".join(_piece(n) for n in _PIECES)
    out = subprocess.run([exe, "-e", prelude + script], capture_output=True, text=True,
                         timeout=120, cwd=str(ROOT))
    assert "RESULT:" in out.stdout, (out.stdout + out.stderr)[-2000:]
    return json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])


def test_at_the_default_level_the_nine_are_on_the_page_and_above_its_level():
    out = _run("""
      var nine = %s;
      print('RESULT:' + JSON.stringify({
        level: knowledgeLevel(), mode: uiMode(),
        hidden: nine.filter(function (t) { return panelIsHidden('swing', t); }),
        above: nine.filter(function (t) { return panelMinLevel('swing', t) > knowledgeLevel(); }).length }));
    """ % json.dumps(NINE))
    assert out["level"] == 1 and out["mode"] == "simple"
    assert out["hidden"] == [], "on the page"
    assert out["above"] == 9, "and above the level, so they start collapsed"


def test_what_the_reader_took_off_in_the_chooser_stays_off():
    out = _run("""
      setPanelHidden(panelId('swing', 'Call vs put flow'), true);
      var off = panelIsHidden('swing', 'Call vs put flow');
      var other = panelIsHidden('swing', 'Gamma analysis');
      clearHiddenPanels('swing');
      print('RESULT:' + JSON.stringify({ off: off, other: other, back: panelIsHidden('swing', 'Call vs put flow') }));
    """)
    assert out == {"off": True, "other": False, "back": False}


def test_no_note_and_the_copy_says_collapsed():
    body = APP[APP.index("function applyUiMode(view) {"):]
    body = body[:body.index("\n}\n")]
    assert "panel hidden" not in body and "createElement" not in body
    assert "ADVANCED_NOUN" not in APP and "function advancedNoun" not in APP
    chooser = APP[APP.index("function panelChooserHTML(view) {"):]
    chooser = chooser[:chooser.index("\n}\n")]
    assert ">Show all</button>" in chooser and "Reset to ${" not in chooser
    settings = APP[APP.index("<h2>${hg('How much to show')}</h2>"):]
    settings = settings[:settings.index("</div>\n  </div>")]
    assert "Simple starts those collapsed" in settings
    assert "Simple leaves those out" not in settings and "says\n          so where they were" not in settings
