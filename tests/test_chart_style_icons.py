"""Candles, a line or an area, as three icons on every chart that offers it.

Asked for with a picture of a three-icon control, "have the line/candles
feature look like this across all graphs, with the addition of the third
selected tab". The Options chart, the Charting tab, an instrument page and the
Investing chart each had Line and Candles as words; each has the same three
icons now, and Area is the line with the ground under it filled. Line is a
plain line, where it carried a faint fill of its own, so the two read apart.
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
CHARTS = (ROOT / "static/charts.js").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _jsc(script, prelude=None):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    head = prelude or """
      load('tests/support/browser_stubs.js');
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      document.documentElement.style.removeProperty = function () {};
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
    """
    out = subprocess.run([exe, "-e", head + script], capture_output=True, text=True,
                         timeout=120, cwd=str(ROOT))
    assert "RESULT:" in out.stdout, (out.stdout + out.stderr)[-2000:]
    return json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])


def test_three_icons_in_order_with_the_choice_pressed():
    out = _jsc("""
      print('RESULT:' + JSON.stringify({ area: chartStyleSeg('data-ws-mode', 'area'),
        off: chartStyleSeg('data-ws-mode', 'candle', { candlesOff: 'No candles here.' }) }));
    """)
    area, off = out["area"], out["off"]
    labels = [s.split('"')[0] for s in area.split('aria-label="')[2:]]
    assert labels == ["Candles", "Line", "Area"], "candles, line, area, in that order"
    assert area.count("<svg") == 3 and ">Candles<" not in area, "icons, not words"
    assert 'data-ws-mode="area" aria-pressed="true"' in area
    assert area.count('aria-pressed="true"') == 1
    # Candles chosen where none can be drawn: the line drawn instead is what reads as chosen.
    assert 'data-ws-mode="candle" aria-pressed="false"' in off
    assert 'data-ws-mode="line" aria-pressed="true"' in off
    assert 'title="No candles here." disabled' in off


def test_every_chart_with_a_style_has_the_three():
    for attr, mode in (("data-chart-mode", "chartMode"), ("data-inst-mode", "instrumentMode"),
                       ("data-ws-mode", "chartMode"), ("data-lt-mode", "ltMode")):
        assert "chartStyleSeg('%s', %s" % (attr, mode) in APP, attr
    for gone in (">Candles</button>", ">Line</button>"):
        assert gone not in APP, gone


def test_area_fills_and_line_does_not():
    for mode, series in (("chartMode", "fill: !candleMode && chartMode === 'area', fillOpacity: AREA_FILL_OPACITY"),
                         ("instrumentMode", "fill: !candles && instrumentMode === 'area',"),
                         ("chartMode", "fill: !wsCandles(ps) && chartMode === 'area',"),
                         ("ltMode", "fill: !ltCandles && ltMode === 'area', fillOpacity: AREA_FILL_OPACITY")):
        assert series in APP, series
    assert "const AREA_FILL_OPACITY = 0.22;" in APP
    assert CHARTS.count("opacity: se.fillOpacity || 0.1") == 2, "both the plain and the tinted line"


def test_the_area_is_drawn_at_its_own_strength():
    got = _jsc("""
      var svg = lineChart({ width: 600, height: 240, labels: ['2026-09-01', '2026-09-02', '2026-09-03',
        '2026-09-04', '2026-09-07'], series: [{ name: 'Close', values: [10, 11, 10.5, 12, 12.4],
        fill: true, fillOpacity: 0.22 }] });
      var fills = NODES.filter(function (n) { return n.tag === 'path' && n.attrs.stroke === 'none'; });
      print('RESULT:' + JSON.stringify(fills.map(function (n) { return n.attrs.opacity; })));
    """, prelude=(ROOT / "tests/support/recording_dom.js").read_text() + CHARTS)
    assert got == ["0.22"]


def test_every_mode_accepts_area_and_keeps_it():
    assert "chartMode = chartStyleMode(localStorage.getItem(CHART_MODE_KEY));" in APP
    assert "if (CHART_STYLES.includes(m)) ltMode = m;" in APP
    assert "const want = chartStyleMode(modeBtn.dataset.chartMode);" in APP
    assert "instrumentMode = chartStyleMode(instModeBtn.dataset.instMode);" in APP
    assert "ltMode = chartStyleMode(ltBtn.dataset.ltMode);" in APP
    assert "chartMode = chartStyleMode(wsMode.dataset.wsMode);" in APP


def test_the_styles_are_declared_before_the_code_that_reads_them_at_load():
    """Both saved styles are read by top-level code inside a try. A `const`
    read before its line throws, and the catch would swallow the throw and
    the rest of the saved settings with it."""
    declared = APP.index("const CHART_STYLES = ['candle', 'line', 'area'];")
    assert declared < APP.index("if (CHART_STYLES.includes(m)) ltMode = m;")
    assert declared < APP.index("chartMode = chartStyleMode(localStorage.getItem(CHART_MODE_KEY));")
