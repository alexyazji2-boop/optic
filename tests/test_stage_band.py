"""Stages as a band under the price, and candles in their own direction.

Reported with NKE's hourly chart in stage 4: "why are all candles [red], even
in uptrends like these?". Stages coloured every candle by its week's stage, as
the TrendSpider reference draws them, so a rally inside a declining stage was a
row of red, and the one thing a candle is for was gone. The stage is now a band
along the foot of the price area and each candle is its own up or down colour.

The renderer itself is run here, under JavaScriptCore with a recording DOM, and
what it drew is read back.
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
UP, DOWN = "#00aa00", "#aa0000"
OHLC = {"open": [10, 10.2, 11, 10.6, 12.1], "high": [10.5, 11.2, 11.1, 12.2, 12.3],
        "low": [9.8, 10.1, 10.3, 10.5, 11.4], "close": [10.3, 11, 10.5, 12, 11.5]}


def _draw(opts):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = ((ROOT / "tests/support/recording_dom.js").read_text()
           + (ROOT / "static/charts.js").read_text() + """
      var opts = %s;
      var svg = lineChart(opts);
      var band = NODES.filter(function (n) { return n.tag === 'g' && n.attrs['class'] === 'stage-band'; });
      var rects = band.length ? band[0].children.map(function (r) { return r.attrs; }) : [];
      var candles = NODES.filter(function (n) {
        return n.tag === 'rect' && (n.attrs.fill === '%s' || n.attrs.fill === '%s') && n.attrs.stroke === n.attrs.fill;
      }).map(function (r) { return r.attrs.fill; });
      var f = svg.chartFrame || {};
      print(JSON.stringify({ groups: band.length, rects: rects, candles: candles,
                             foot: (f.margin ? f.margin.t : 0) + (f.priceH || 0) }));
    """ % (json.dumps(opts), UP, DOWN))
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=30)
    last = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else ""
    assert last.startswith("{"), out.stdout + out.stderr
    return json.loads(last)


BASE = {"width": 600, "height": 300, "labels": ["a", "b", "c", "d", "e"],
        "candleUp": UP, "candleDown": DOWN}


def test_every_candle_keeps_its_own_direction_under_the_band():
    got = _draw({**BASE, "candles": OHLC, "stageBand": ["S4"] * 5,
                 "series": [{"name": "Close", "values": OHLC["close"], "color": "#123456",
                             "hidden": True}]})
    # up, up, down, up, down: the closes against their opens, not the stage.
    assert got["candles"] == [UP, UP, DOWN, UP, DOWN]


def test_the_band_is_one_run_per_stage_along_the_foot_of_the_price():
    got = _draw({**BASE, "candles": OHLC, "stageBand": ["S4", "S4", "S4", "S2", "S2"],
                 "series": [{"name": "Close", "values": OHLC["close"], "color": "#123456",
                             "hidden": True}]})
    assert got["groups"] == 1
    assert [r["fill"] for r in got["rects"]] == ["S4", "S2"]
    for r in got["rects"]:
        assert float(r["y"]) + float(r["height"]) == pytest.approx(got["foot"])
    # Contiguous: the second run starts where the first stops.
    a, b = got["rects"]
    assert float(a["x"]) + float(a["width"]) == pytest.approx(float(b["x"]), abs=0.01)


def test_the_band_draws_under_a_line_too():
    got = _draw({**BASE, "stageBand": ["S2"] * 5,
                 "series": [{"name": "Close", "values": OHLC["close"], "color": "#123456"}]})
    assert [r["fill"] for r in got["rects"]] == ["S2"]


def test_no_band_without_stages():
    got = _draw({**BASE, "candles": OHLC,
                 "series": [{"name": "Close", "values": OHLC["close"], "color": "#123456",
                             "hidden": True}]})
    assert got["groups"] == 0 and got["candles"] == [UP, UP, DOWN, UP, DOWN]
