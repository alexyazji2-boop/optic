"""A symbol typed into the header search is the symbol that opens.

Reported as "i type INTC into the search bar and it stays on NVDA". Focusing
the header box opens the command palette, which took focus on the next
animation frame. A frame held up by the chart behind it let the keys reach the
header box instead (it read "NVDAINTC", the palette's field ""), and Enter ran
the palette's first row, which with nothing typed is the most recent symbol:
NVDA. And had the keys reached the palette, Enter inside the wait for
/api/search ran the last query's rows all the same.

Checked in a browser: a click on the box, INTC typed at once and Enter opened
INTC, where it had stayed on NVDA.
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

# The page's own listeners, kept so a test can fire them in order; a field and
# a header box that remember focus; a symbol search that never answers.
_HARNESS = """
  load('tests/support/browser_stubs.js');
  document.documentElement.style = document.documentElement.style || {};
  document.documentElement.style.setProperty = function () {};
  document.documentElement.style.removeProperty = function () {};
  var HANDLERS = {};
  document.addEventListener = function (type, fn) { (HANDLERS[type] = HANDLERS[type] || []).push(fn); };
  try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
  function fire(type, evt) { (HANDLERS[type] || []).forEach(function (fn) { fn(evt); }); }
  var FOCUSED = null;
  var field = { id: 'cp-input', value: '', focus: function () { FOCUSED = field; }, setSelectionRange: function () {} };
  var box = { id: 'ticker-input', value: 'NVDA', focus: function () { FOCUSED = box; } };
  document.getElementById = function (id) { return id === 'cp-input' ? field : id === 'ticker-input' ? box : null; };
  mountPalette = function () {};
  paintPaletteList = function () {};
  recentSymbols = function () { return ['NVDA']; };
  var opened = [];
  loadTicker = function (sym, where) { opened.push(sym); };
  getJSON = function () { return new Promise(function () {}); };
  var enter = { key: 'Enter', preventDefault: function () {} };
"""


def _run(script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    out = subprocess.run([exe, "-e", _HARNESS + script], capture_output=True, text=True,
                         timeout=120, cwd=str(ROOT))
    assert "RESULT:" in out.stdout, (out.stdout + out.stderr)[-2000:]
    return json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])


def test_the_palette_has_focus_as_it_opens():
    out = _run("""
      fire('focusin', { target: box });
      print('RESULT:' + JSON.stringify({ open: paletteOpen, focused: FOCUSED === field }));
    """)
    assert out == {"open": True, "focused": True}, "not a frame later, when the keys have gone elsewhere"


def test_keys_that_reached_the_header_box_are_moved_into_the_palette():
    out = _run("""
      fire('focusin', { target: box });
      box.value = 'NVDAINTC';                 // what the box read in the report
      fire('input', { target: box });
      var moved = { field: field.value, box: box.value, query: paletteQuery, focused: FOCUSED === field };
      fire('keydown', enter);
      print('RESULT:' + JSON.stringify({ moved: moved, opened: opened }));
    """)
    assert out["moved"] == {"field": "INTC", "box": "NVDA", "query": "INTC", "focused": True}
    assert out["opened"] == ["INTC"], "not the most recent symbol"


def test_enter_before_the_symbol_search_answers_opens_what_was_typed():
    out = _run("""
      fire('focusin', { target: box });
      field.value = 'INTC';
      fire('input', { target: field });       // /api/search is still out
      fire('keydown', enter);
      print('RESULT:' + JSON.stringify({ opened: opened, rowsFor: paletteRowsFor }));
    """)
    assert out["opened"] == ["INTC"]
    assert out["rowsFor"] == "INTC"


def test_rows_built_for_another_query_are_rebuilt_before_enter_runs_one():
    out = _run("""
      fire('focusin', { target: box });
      paletteQuery = 'AMD';                   // typed, with its rows not yet asked for
      fire('keydown', enter);
      print('RESULT:' + JSON.stringify({ opened: opened }));
    """)
    assert out["opened"] == ["AMD"]


def test_an_empty_palette_still_opens_the_most_recent_symbol():
    """Enter with nothing typed is a request for the first row, as before."""
    out = _run("""
      fire('focusin', { target: box });
      fire('keydown', enter);
      // The empty query's rows come a microtask later; read after they have.
      Promise.resolve().then(function () { return Promise.resolve(); }).then(function () {
        print('RESULT:' + JSON.stringify({ opened: opened }));
      });
    """)
    assert out["opened"] == ["NVDA"]
    fn = APP[APP.index("function openPalette(seed) {"):]
    fn = fn[:fn.index("\n}\n")]
    assert fn.index("input.focus();") < fn.index("requestAnimationFrame("), "focus now, then again"
