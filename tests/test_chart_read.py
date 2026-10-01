"""Chart read: what the chart says, in a few lines, on the Charting tab.

Asked for with another product's panel, "add this feature to the charting tab":
a trend, the facts it rests on, the nearest support and resistance, and where
RSI and MACD stand. Optic's version is computed from the technicals the chart
already loaded, so it opens at once and costs nothing, and it says it reads
completed daily sessions whatever the bars on screen. Checked in a browser on
SPY: Uptrend, five facts, both bands, "Neutral, 47" and "Momentum fading".
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


def _run(script):
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


def _payload(**over):
    t = {
        "moving_averages": {
            "sma20": {"value": 764.9, "distance_pct": -0.36, "position": "below", "slope_10d_pct": 0.07},
            "sma50": {"value": 763.0, "distance_pct": -0.12, "position": "below", "slope_10d_pct": 0.46},
            "sma200": {"value": 720.0, "distance_pct": 5.85, "position": "above", "slope_10d_pct": 0.58}},
        "structure": {"stacked_bullish": True, "stacked_bearish": False, "cross_event": None},
        "rsi": {"value": 47.4, "state": "neutral"},
        "macd": {"state": "bearish", "event": "histogram expanding down"},
        "support_resistance": [
            {"role": "support", "band_low": 756.85, "band_high": 760.81, "distance_pct": -0.43},
            {"role": "resistance", "band_low": 774.68, "band_high": 778.65, "distance_pct": 1.91},
            {"role": "support", "band_low": 747.58, "band_high": 751.55, "distance_pct": -1.65},
            {"role": "resistance", "band_low": 800.0, "band_high": 805.0, "distance_pct": 5.2}],
    }
    t.update(over)
    return {"technicals": t}


def test_the_read_from_the_charts_own_numbers():
    model = _run("print('RESULT:' + JSON.stringify(chartReadModel(%s)));" % json.dumps(_payload()))
    assert model["trend"] == "Uptrend"
    assert model["facts"] == [
        "Price is 5.9% above the 200-day average.",
        "Price is 0.1% below the 50-day average.",
        "Price is 0.4% below the 20-day average.",
        "The 20, 50 and 200-day averages are stacked in rising order.",
        "The 50-day average is rising, 0.46% over ten sessions."]
    assert model["support"]["band_low"] == 756.85, "the nearest, not the strongest"
    assert model["resistance"]["band_low"] == 774.68
    assert model["rsi"] == "Neutral, 47" and model["macd"] == "Momentum fading"


def test_a_downtrend_a_mixed_one_and_a_cross():
    down = _payload()
    ma = down["technicals"]["moving_averages"]
    ma["sma200"].update(position="below", distance_pct=-6.0)
    ma["sma50"].update(value=700.0, slope_10d_pct=-0.3)
    down["technicals"]["structure"] = {"stacked_bullish": False, "stacked_bearish": True,
                                      "cross_event": "death cross (50 crossed below 200) within 5 bars"}
    down["technicals"]["macd"] = {"state": "bearish", "event": "bearish crossover today"}
    model = _run("print('RESULT:' + JSON.stringify(chartReadModel(%s)));" % json.dumps(down))
    assert model["trend"] == "Downtrend"
    assert "The 50-day average is falling, 0.30% over ten sessions." in model["facts"]
    assert "The 50-day crossed below the 200-day in the last five sessions." in model["facts"]
    assert model["macd"] == "Crossed below its signal today"
    mixed = _payload()
    mixed["technicals"]["moving_averages"]["sma50"]["value"] = 700.0      # under the 200
    mixed["technicals"]["structure"]["stacked_bullish"] = False
    model = _run("print('RESULT:' + JSON.stringify(chartReadModel(%s)));" % json.dumps(mixed))
    assert model["trend"] == "Mixed trend"
    assert "The averages are not stacked in order, so the trend is not settled." in model["facts"]


def test_without_a_200_day_average_it_says_so_rather_than_guessing():
    out = _run("""
      STATE.chartSymbol = 'NEWCO';
      STATE.chartData = { technicals: { moving_averages: { sma50: { value: 10 } } } };
      print('RESULT:' + JSON.stringify({ model: chartReadModel(STATE.chartData), html: chartReadHTML() }));
    """)
    assert out["model"] is None
    assert "Not enough daily history for a 200-day average yet." in out["html"]


def test_the_panel_names_what_it_reads_and_offers_pulse_without_sending():
    html = _run("""
      STATE.chartSymbol = 'SPY'; STATE.chartData = %s;
      print('RESULT:' + JSON.stringify({ html: chartReadHTML() }));
    """ % json.dumps(_payload()))["html"]
    assert "Chart read · SPY · Daily" in html
    assert "756.85 – 760.81" in html and "774.68 – 778.65" in html
    assert "From completed daily sessions, whatever the bars on screen." in html
    assert 'data-explain-chart="SPY"' in html, "Explain chart, which drafts into Pulse's box"


def test_the_button_is_on_the_toolbar_outside_the_phone_drawer():
    fn = APP[APP.index("function wsToolbar() {"):]
    fn = fn[:fn.index('<div class="ws-tools">')]
    assert 'data-ws-menu="read"' in fn and ">Chart read</button>" in fn
    assert "${wsMenuOpen === 'read' ? `<div class=\"ws-menu-pop ws-read-pop\">${chartReadHTML()}</div>` : ''}" in fn
