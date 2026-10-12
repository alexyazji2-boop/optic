"""The MA Trend Identifier on the Charting tab (2026-10-12).

Asked for with TrendSpider's "Color Tells The Story": each candle green when
it opened and closed above all of the 10, 20, 50, 100 and 200 SMAs, red when
below them all, grey between.
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


def _fn(name):
    return re.search(r"^function " + name + r"\([^\n]*\) \{.*?^\}", APP, re.M | re.S).group()


def _run(src):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    consts = re.search(r"^const MA_TREND_PERIODS = [^\n]*;", APP, re.M).group()
    out = subprocess.run([exe, "-e", "\n".join([consts, _fn("smaSeries"), _fn("maTrendSeries"), src])],
                         capture_output=True, text=True, timeout=30)
    return json.loads(out.stdout)


def test_above_all_five_below_all_five_and_between():
    out = _run("""
      var c = [], o = [];
      for (var i = 0; i < 260; i++) { c.push(100); o.push(100); }
      c[220] = 110; o[220] = 105;      // opened and closed above every average
      c[230] = 90;  o[230] = 95;       // below every average
      c[240] = 101; o[240] = 99;       // opened below, closed above: mixed
      c[250] = 100; o[250] = 100;      // sitting on them: mixed
      print(JSON.stringify(maTrendSeries(o, c)));
    """)
    assert out[198] is None and out[199] == 0, "nothing before the 200-bar average exists"
    assert out[220] == 1 and out[230] == -1 and out[240] == 0 and out[250] == 0


def test_it_colours_the_candles_and_the_line_in_place_of_stages():
    body = _fn("wsMountChart")
    assert "const maTint = maTrendTints(ps);" in body
    assert "candleTints: maTint || (stages ? stages.colors : null)" in body
    assert "stageBand: stages ? stages.colors : null" in body, "the stage strip stays"
    tints = _fn("maTrendTints")
    assert "v === 1 ? C.pos : v === -1 ? C.neg : v === 0 ? C.muted : null" in tints
    assert "out.maTrend = maTrendSeries(base.open || [], closes);" in _fn("wsWithOscillators")
    assert "'cloud921', 'cloud2150', 'matrend']" in APP
    assert "const MA_TREND_PERIODS = [10, 20, 50, 100, 200];" in APP
