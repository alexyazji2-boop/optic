"""Two tabs drawing on two symbols keep both drawings.

Reproduced from the code before the fix: each tab read the drawing store once
at load and wrote its whole copy back on every save, so a drawing another tab
had saved since was overwritten with the state at this tab's load. Draw on
AAPL in one tab and MSFT in another, reload, and the first was gone. A save now
re-reads the store and writes only its own symbol, and a `storage` listener
brings another tab's saves into this tab's copy.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def test_a_save_keeps_what_another_tab_saved_since():
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = """
      load('tests/support/browser_stubs.js');
      var MEM = {'optic.chart.drawings.v2': JSON.stringify({AAPL: [{id: 'a1'}]})};
      localStorage.getItem = function (k) { return Object.prototype.hasOwnProperty.call(MEM, k) ? MEM[k] : null; };
      localStorage.setItem = function (k, v) { MEM[k] = String(v); };
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      document.documentElement.style.removeProperty = function () {};
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
      // The other tab, after this one loaded: a drawing on MSFT.
      MEM['optic.chart.drawings.v2'] = JSON.stringify({AAPL: [{id: 'a1'}], MSFT: [{id: 'm1'}]});
      STATE.chartSymbol = 'AAPL';
      wsSaveDrawings([{id: 'a1'}, {id: 'a2'}]);
      var saved = JSON.parse(MEM['optic.chart.drawings.v2']);
      print('RESULT:' + JSON.stringify({saved: saved, mine: wsDrawings().map(function (d) { return d.id; })}));
    """
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    body = json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])
    assert body["saved"]["MSFT"] == [{"id": "m1"}], "the other tab's drawing survived"
    assert [d["id"] for d in body["saved"]["AAPL"]] == ["a1", "a2"]
    assert body["mine"] == ["a1", "a2"]


def test_another_tabs_save_reaches_this_tab():
    block = APP.split("window.addEventListener('storage', (evt) => {\n  if (evt.key !== WS_DRAW_KEY_V2) return;", 1)[1][:400]
    assert "wsDrawStore = wsStoredDrawings();" in block and "wsRenderDrawings()" in block


def test_the_migration_writes_through_the_same_save():
    block = APP.split("function wsMigrateLegacy(axis) {", 1)[1].split("\n}\n", 1)[0]
    assert "wsSaveDrawings([...wsDrawings(), ...moved]);" in block
    assert "JSON.stringify(wsDrawStore)" not in block
