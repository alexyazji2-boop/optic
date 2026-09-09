"""Does the client JavaScript parse, and is every function it calls defined?

**Why this exists.** There is no JS test runner in this project and the other
client tests read `static/*.js` as *text*, which cannot see a
`ReferenceError`. In one session two separate edits to the same region deleted
`maLabel` while twelve call sites still referenced it. Nothing failed: the file
parsed, every panel that did not touch that function rendered, 1123 Python tests
passed, and the defect only showed up as an empty chart legend in a browser.

**What it does.** Evaluates `charts.js` and `app.js` under JavaScriptCore, which
ships with macOS, against the smallest possible set of browser stubs. Evaluation
is *expected* to stop part-way with a TypeError when a stub returns null; that
is not the check. The check is that the file parsed at all (a syntax error
throws before any of it runs) and that the named functions exist, because
function declarations hoist to the top of the module regardless of where
evaluation stopped.

**Skipped rather than failed where `jsc` is absent**, so this does not turn a
Linux CI box red for a reason that has nothing to do with the change. On a Mac
it runs, which is where this code is written.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess

import pytest

JSC = ("/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/"
       "Helpers/jsc")

# Functions the app calls across file and panel boundaries. Not an exhaustive
# list of everything defined: these are the ones whose absence is silent,
# because they are referenced from a render path that only some views reach.
REQUIRED = [
    # chart colours and the price mark
    "chartColor", "chartColorDefault", "chartColorsCustom", "setChartColor",
    "resetChartColors", "isColor", "hexish", "colorContrast", "markWarnText",
    # indicator parity
    "maLabel", "maColorsOnChart", "overlayColorChosen", "chartBaseColors",
    "wsPriceIndicatorIds", "wsLoadIndicators", "wsStudyPalette", "wsStudyRows",
    "wsIndicatorSeries", "wsStudiesMenu",
    # the pieces those sit inside
    "overlayStyle", "setOverlayStyle", "allocateOverlayColors", "seriesDrawn",
    "wsToolbar", "wsLegend", "wsRedrawChart", "macroWord",
    # market command centre
    "marketStripHTML", "stripInstrument", "whatMattersNow", "marketQuestions",
    "homeMovers", "openPulseWithText",
]


def _jsc():
    return JSC if os.path.exists(JSC) else shutil.which("jsc")


def _run(script: str) -> str:
    exe = _jsc()
    proc = subprocess.run([exe, "-e", script], capture_output=True, text=True,
                          timeout=120)
    return proc.stdout + proc.stderr


@pytest.fixture(scope="module")
def evaluated():
    exe = _jsc()
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    # `print` the answers rather than exit codes, so a stub-induced TypeError
    # part-way through evaluation does not look like a failure.
    script = """
      load('tests/support/browser_stubs.js');
      var parseError = null;
      try { load('static/charts.js'); load('static/app.js'); }
      catch (e) { parseError = String(e); }
      print('PARSE_STOPPED_AT:' + (parseError || 'end of file'));
      var names = %s;
      var missing = [];
      for (var i = 0; i < names.length; i++) {
        if (typeof this[names[i]] !== 'function') missing.push(names[i]);
      }
      print('MISSING:' + missing.join(','));
    """ % repr(REQUIRED).replace("'", '"')
    return _run(script)


def test_the_client_javascript_parses(evaluated):
    """A syntax error throws before any of the file runs, so it would show up
    here as a SyntaxError rather than as the TypeError a stub produces."""
    assert "PARSE_STOPPED_AT:" in evaluated, evaluated[-800:]
    stop = evaluated.split("PARSE_STOPPED_AT:")[1].split("\n")[0]
    assert "SyntaxError" not in stop, stop


def test_every_cross_panel_function_is_defined(evaluated):
    """The defect this file was written for. `maLabel` was deleted twice by
    edits to a neighbouring block while its twelve call sites stayed."""
    assert "MISSING:" in evaluated, evaluated[-800:]
    missing = evaluated.split("MISSING:")[1].split("\n")[0].strip()
    assert not missing, "not defined: " + missing


def test_the_required_list_names_things_that_are_actually_called():
    """A list of names nobody calls would pass forever while proving nothing.

    Positive control on the control: every entry has to appear as a call
    somewhere in app.js, or it is a stale name and this file is asserting the
    existence of dead code."""
    src = open("static/app.js").read()
    for name in REQUIRED:
        calls = len(re.findall(r"\b%s\(" % re.escape(name), src))
        # One occurrence is the definition itself; a real caller makes two.
        assert calls >= 2, "%s is defined but never called (%d)" % (name, calls)
