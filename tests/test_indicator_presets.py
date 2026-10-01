"""The five most asked-for studies, one press each, at the top of Indicators.

Asked for with another product's list, "have these indicators as well":
Volume, MA (20, 50, 200), EMA (9, 21), RSI (14) and MACD (12, 26, 9). Each was
on the Charting tab already, spread over the Volume, Indicators and Panes
menus, and the averages one line at a time. Checked in a browser: MA switched
all three averages on with the menu left open, and RSI took its pane away.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _jsc(script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    out = subprocess.run([exe, "-e", """
      load('tests/support/browser_stubs.js');
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      document.documentElement.style.removeProperty = function () {};
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
    """ + script], capture_output=True, text=True, timeout=120, cwd=str(ROOT))
    assert "RESULT:" in out.stdout, (out.stdout + out.stderr)[-2000:]
    return json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])


def test_the_five_are_the_ones_asked_for_and_name_what_they_switch():
    block = APP[APP.index("const WS_PRESETS = ["):]
    block = block[:block.index("\n];")]
    assert re.findall(r"label: '([^']+)'", block) == [
        "Volume", "MA (20, 50, 200)", "EMA (9, 21)", "RSI (14)", "MACD (12, 26, 9)"]
    assert "overlays: ['sma20', 'sma50', 'sma200']" in block
    assert "overlays: ['ema9', 'ema21']" in block
    assert "pane: 'rsi'" in block and "pane: 'macd'" in block


def test_they_head_the_indicators_menu_and_read_as_on_only_when_all_of_a_set_is():
    out = _jsc("""
      wsOverlayOn = function (id) { return id === 'vol' || id === 'sma20' || id === 'sma50'; };
      wsPanesOpen = ['macd'];
      wsMenuOpen = 'indicators';
      var html = wsToolbar();
      wsMenuOpen = 'volume';
      var other = wsToolbar();
      wsMenuOpen = null;
      print('RESULT:' + JSON.stringify({ html: html, other: other }));
    """)
    html = out["html"]
    pop = html[html.index('data-ws-menu="indicators"'):]
    assert pop.index('data-ws-preset="volume"') < pop.index('data-ws-opt="sma20"'), "first in the menu"
    got = dict(re.findall(r'data-ws-preset="(\w+)"( checked)?', html))
    assert got == {"volume": " checked", "ma": "", "ema": "", "rsi": "", "macd": " checked"}, (
        "MA reads as off with two of its three on")
    assert "data-ws-preset" not in out["other"], "only in Indicators"


def test_a_press_switches_the_whole_set_and_keeps_the_menu_true():
    at = APP.index("const wsPreset = evt.target.closest('[data-ws-preset]');")
    handler = APP[at:APP.index("return;\n  }", at)]
    assert "preset.overlays.forEach((id) => wsSetOverlay(id, on));" in handler
    assert "if (wsPaneOpen(preset.pane) !== on) wsTogglePane(preset.pane);" in handler
    assert "wsRepaintWithPanes();" in handler and "wsRedrawChart();" in handler
    assert "if (tb2) tb2.outerHTML = wsToolbar();" in handler, "the menu's own boxes follow"
