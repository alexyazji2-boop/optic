"""The conviction headlines on the Options and Investing tabs read 0 to 100.

Asked for as "change the rating scale from 0-100, not -100 to 100", after the
Investing tab's "Of a possible +97" read as a puzzle. The server's signed
scores are unchanged; the page re-reads them: the worst possible is 0, the
best 100, and zero (no edge either way) 50.
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


def _fn(name):
    at = APP.index("function %s(" % name)
    return APP[at:APP.index("\n}\n", at) + 3]


def _run(script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    prelude = "function fmt(v, d) { return Number(v).toFixed(d); }\n" + "\n".join(
        _fn(n) for n in ("score100", "score100HTML", "longScore100"))
    out = subprocess.run([exe, "-e", prelude + script], capture_output=True, text=True, timeout=60)
    assert "RESULT:" in out.stdout, (out.stdout + out.stderr)[-2000:]
    return json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])


def test_each_side_is_scaled_to_its_own_limit_and_zero_is_fifty():
    h = {"conviction_scale": {"min_possible": -86, "max_possible": 97}}
    got = _run("print('RESULT:' + JSON.stringify(["
               "longScore100(H, 97), longScore100(H, 0), longScore100(H, -86), longScore100(H, 62),"
               "longScore100(H, 120), longScore100({}, 50),"
               "score100(100), score100(0), score100(-100), score100(24), score100(null)]));"
               .replace("H", json.dumps(h)))
    assert got[:3] == [100, 50, 0]
    assert round(got[3]) == 82, "+62 of a possible +97"
    assert got[4] == 100, "clamped, never above 100"
    assert got[5] == 75, "no scale in the payload falls back to +-100"
    assert got[6:10] == [100, 50, 0, 62]
    assert got[10] is None


def test_both_headlines_print_out_of_100_and_say_where_neutral_is():
    assert "subnote sm\">Of a possible" not in APP
    assert "subnote sm\">Out of ±100" not in APP
    assert "score100HTML(longScore100(h, h.conviction_score))" in APP
    assert "score100HTML(score100(v.composite_score))" in APP
    assert "50 is neutral, 100 is every factor at its best" in APP
    assert "50 is neutral, 0 fully bearish, 100 fully bullish" in APP
    assert "(${fmt(of100, 0)}/100)" in APP, "the Investing context strip agrees with the headline"
