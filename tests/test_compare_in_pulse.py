"""Pulse reads the comparison the reader ran.

Reported with Pulse's answer to the Compare page's question: "This CONTEXT
isn't actually a side-by-side horizon comparison... it's the paper-trading
tracker", and "what? this response makes no sense, fix this". The context
Pulse is sent with every question had no comparison in it at all, so a
question about one went out with whatever else the browser had loaded.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _context(compare):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    script = """
      load('tests/support/browser_stubs.js');
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      document.documentElement.style.removeProperty = function () {};
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
      STATE.compare = %s;
      STATE.tracker = { summary: { open: 12 }, open: [], config: {}, caveats: [] };
      print('RESULT:' + JSON.stringify(chatContextPayload()));
    """ % json.dumps(compare)
    out = subprocess.run([exe, "-e", script], capture_output=True, text=True,
                         timeout=120, cwd=str(ROOT))
    assert "RESULT:" in out.stdout, (out.stdout + out.stderr)[-2000:]
    return json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])


COMPARE = {"available": True, "tickers": ["MU", "TSLA"],
           "horizons": [{"name": "Swing setup", "horizon": "1 to 8 weeks",
                         "basis": "14-session RSI"}],
           "rows": [{"ticker": "MU", "scores": {"swing": 61}},
                    {"ticker": "TSLA", "scores": {"swing": 48}}],
           "ranks": {"swing": ["MU", "TSLA"]}, "take": {"headline": "MU leads the swing"}}


def test_a_comparison_that_ran_is_in_what_pulse_reads():
    ctx = _context(COMPARE)
    assert ctx["compare"] == COMPARE
    assert "tracker" in ctx, "beside the rest, not instead of it"


def test_one_that_did_not_run_is_not():
    assert "compare" not in _context({"available": False, "reason": "Give at least two tickers."})
    assert "compare" not in _context(None)


def test_the_context_chip_names_it_once_it_is_there():
    app = (ROOT / "static/app.js").read_text()
    fn = app[app.index("function updateChatContext() {"):]
    fn = fn[:fn.index("\n}\n")]
    assert "if (STATE.compare && STATE.compare.available === true) bits.push('comparison');" in fn
    assert "comparison: 'the side-by-side comparison you ran'," in fn
    run = app[app.index("async function runCompare() {"):]
    run = run[:run.index("\n}\n")]
    assert run.rstrip().endswith("updateChatContext();")
