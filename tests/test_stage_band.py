"""Stages behind the price, and candles in their own direction.

Reported with NKE's hourly chart in stage 4: "why are all candles [red], even
in uptrends like these?". Stages coloured every candle by its week's stage, as
the TrendSpider reference draws them, so a rally inside a declining stage was a
row of red, and the one thing a candle is for was gone. The stage moved to a
band along the foot of the price area and each candle kept its own up or down
colour.

That band was four pixels under a 470px chart, and the next question was "does
stages no longer work on the chart?". So each run of a stage is now also a
faint tint behind the whole price area, the band names the stage where the run
is wide enough, and hovering a bar names its stage in the readout.

The renderer itself is run here, under JavaScriptCore with a recording DOM, and
what it drew is read back.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
UP, DOWN = "#00aa00", "#aa0000"
OHLC = {"open": [10, 10.2, 11, 10.6, 12.1], "high": [10.5, 11.2, 11.1, 12.2, 12.3],
        "low": [9.8, 10.1, 10.3, 10.5, 11.4], "close": [10.3, 11, 10.5, 12, 11.5]}


def _draw(opts, hover=None):
    """Draw `opts` and read back what was drawn. `hover` is a clientX to move
    the pointer to afterwards; the readout it produced comes back as `tip`."""
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = ((ROOT / "tests/support/recording_dom.js").read_text()
           + (ROOT / "static/charts.js").read_text() + """
      // The pointer, without a browser: keep the chart's move handler, and
      // the readout it would have shown.
      var SCRUBS = [], TIPS = [];
      bindScrub = function (el, onMove) { SCRUBS.push(onMove); };
      showTip = function (html) { TIPS.push(html); };
      var opts = %s;
      var svg = lineChart(opts);
      var group = function (cls) {
        var g = NODES.filter(function (n) { return n.tag === 'g' && n.attrs['class'] === cls; });
        return g.length ? g[0] : null;
      };
      var attrsOf = function (g) { return g ? g.children.map(function (r) { return r.attrs; }) : []; };
      var band = NODES.filter(function (n) { return n.tag === 'g' && n.attrs['class'] === 'stage-band'; });
      var rects = band.length ? band[0].children.map(function (r) { return r.attrs; }) : [];
      var candles = NODES.filter(function (n) {
        return n.tag === 'rect' && (n.attrs.fill === '%s' || n.attrs.fill === '%s') && n.attrs.stroke === n.attrs.fill;
      }).map(function (r) { return r.attrs.fill; });
      var names = group('stage-names');
      var kids = svg.children || [];
      var f = svg.chartFrame || {};
      var hover = %s;
      if (hover !== null && SCRUBS.length) SCRUBS[0]({ clientX: hover, clientY: 50, pointerType: 'mouse' });
      print(JSON.stringify({ groups: band.length, rects: rects, candles: candles,
                             zones: attrsOf(group('stage-zones')),
                             names: names ? names.children.map(function (t) {
                               return { x: t.attrs.x, y: t.attrs.y, fill: t.attrs.fill, text: t.textContent };
                             }) : [],
                             zonesAt: kids.indexOf(group('stage-zones')),
                             gridAt: kids.findIndex(function (k) {
                               return (k.children || []).some(function (c) { return c.tag === 'line'; });
                             }),
                             tip: TIPS.length ? TIPS[TIPS.length - 1] : null,
                             top: f.margin ? f.margin.t : 0, priceH: f.priceH || 0,
                             foot: (f.margin ? f.margin.t : 0) + (f.priceH || 0) }));
    """ % (json.dumps(opts), UP, DOWN, json.dumps(hover)))
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


# ---------------------------------------------------------------- the tint


NAMES = {"S1": "Stage 1 \u00b7 Basing", "S2": "Stage 2 \u00b7 Advancing",
         "S3": "Stage 3 \u00b7 Topping", "S4": "Stage 4 \u00b7 Declining"}


def _staged(stages, **extra):
    """A line chart of len(stages) bars, each in the stage given."""
    n = len(stages)
    return {"width": 600, "height": 300, "labels": ["d%d" % i for i in range(n)],
            "series": [{"name": "Close", "values": [10 + (i % 3) * 0.5 for i in range(n)],
                        "color": "#123456"}],
            "stageBand": stages, "stageNames": [NAMES[s] for s in stages], **extra}


def test_each_run_is_tinted_behind_the_whole_price_area():
    got = _draw({**BASE, "candles": OHLC, "stageBand": ["S4", "S4", "S4", "S2", "S2"],
                 "series": [{"name": "Close", "values": OHLC["close"], "color": "#123456",
                             "hidden": True}]})
    zones = got["zones"]
    assert [z["fill"] for z in zones] == ["S4", "S2"]
    for z in zones:
        # A tint: well under the full colour a candle is drawn in.
        assert 0 < float(z["fill-opacity"]) <= 0.2
        assert float(z["y"]) == pytest.approx(got["top"])
        assert float(z["height"]) == pytest.approx(got["priceH"])
    # The same runs as the band, edge for edge.
    assert [(z["x"], z["width"]) for z in zones] == [(r["x"], r["width"]) for r in got["rects"]]
    # Behind the grid, and so behind everything drawn after it.
    assert 0 <= got["zonesAt"] < got["gridAt"]
    # And the candles still say which way each bar went.
    assert got["candles"] == [UP, UP, DOWN, UP, DOWN]


def test_a_run_is_named_on_the_band_as_fully_as_it_has_room_for():
    # 20 bars across 534px: about 27px a bar.
    got = _draw(_staged(["S4"] * 12 + ["S2"] * 2 + ["S3"] + ["S1"] * 5))
    widths = [float(z["width"]) for z in got["zones"]]
    assert widths[0] > 200 and 55 < widths[1] < 110 and widths[2] < 50 and widths[3] > 110
    # Wide: the whole name. Two bars: the number alone. One bar: nothing,
    # though its colour is still there. Five: the whole name again.
    assert [t["text"] for t in got["names"]] == [
        "Stage 4 \u00b7 Declining", "Stage 2", "Stage 1 \u00b7 Basing"]
    fills = {t["text"]: t["fill"] for t in got["names"]}
    assert fills["Stage 2"] == "S2" and fills["Stage 1 \u00b7 Basing"] == "S1"
    # On the band: above it, inside the price area.
    band_top = got["foot"] - float(got["rects"][0]["height"])
    for t in got["names"]:
        assert got["top"] < float(t["y"]) < band_top


def test_a_name_stands_aside_for_a_session_caption():
    """Session dividers caption the foot of the plot as well. A stage run that
    starts on a month line would print its name over the month's."""
    days = []
    d = date(2026, 1, 5)
    while len(days) < 60:
        if d.weekday() < 5:
            days.append(d.isoformat())
        d += timedelta(days=1)
    feb = next(i for i, iso in enumerate(days) if iso >= "2026-02-01")
    stages = ["S4"] * feb + ["S2"] * (len(days) - feb)
    opts = {**_staged(stages), "labels": days}
    plain = _draw(opts)
    assert [t["text"] for t in plain["names"]] == [
        "Stage 4 \u00b7 Declining", "Stage 2 \u00b7 Advancing"]
    got = _draw({**opts, "sessions": True})
    assert [t["text"] for t in got["names"]] == ["Stage 4 \u00b7 Declining"]
    # The tint and the band do not stand aside: only the name does.
    assert [z["fill"] for z in got["zones"]] == ["S4", "S2"]


def test_without_names_the_tint_and_band_still_draw():
    opts = _staged(["S4", "S4", "S2", "S2", "S2"])
    del opts["stageNames"]
    got = _draw(opts)
    assert [z["fill"] for z in got["zones"]] == ["S4", "S2"]
    assert [r["fill"] for r in got["rects"]] == ["S4", "S2"]
    assert got["names"] == []


def test_no_tint_without_stages():
    opts = _staged(["S4"] * 5)
    del opts["stageBand"], opts["stageNames"]
    got = _draw(opts)
    assert got["zones"] == [] and got["names"] == [] and got["zonesAt"] == -1


def test_hovering_a_bar_names_its_stage():
    got = _draw(_staged(["S4", "S4", "S2", "S2", "S2"]), hover=0)
    assert "Stage</span><span>4 \u00b7 Declining</span>" in got["tip"]
    assert 'style="color:S4"' in got["tip"]
    got = _draw(_staged(["S4", "S4", "S2", "S2", "S2"]), hover=100000)
    assert "Stage</span><span>2 \u00b7 Advancing</span>" in got["tip"]


def test_the_readout_is_escaped():
    """A stage's name comes from the server, and the readout is HTML."""
    opts = _staged(["S2"] * 5)
    opts["stageNames"] = ["Stage 2 \u00b7 <b>x</b>"] * 5
    got = _draw(opts, hover=0)
    assert "&lt;b&gt;x&lt;/b&gt;" in got["tip"] and "<b>x</b>" not in got["tip"]


def test_no_stage_row_in_the_readout_without_names():
    opts = _staged(["S2"] * 5)
    del opts["stageNames"]
    got = _draw(opts, hover=0)
    assert got["tip"] and "Stage" not in got["tip"]
