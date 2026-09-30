"""Stages in the candles and the line, as the reference chart draws them.

Stages have been drawn three ways. First as the TrendSpider reference does,
every candle in the colour of its week's stage, which NKE's hourly chart in
stage 4 had reported as "why are all candles [red], even in uptrends like
these?". Then as a four-pixel band along the foot of the price, which was
asked about as "does stages no longer work on the chart?", and then as a
faint tint behind each run with the band under it.

Now as the reference again, asked for directly: "keep the candles as is with
the color change as per the reference screenshot attached, and so the same
feature with the lines". The candles and the line take their week's stage
colour, the tint and the band are gone, each run is still named along the
foot, and hovering a bar still names its stage. Stages off gives every bar
its own direction back, which is the answer to the NKE question now.

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
      // A candle's body is the one rect filled and stroked in one colour, and
      // it comes after its wick, a line in the same colour.
      var bodies = NODES.filter(function (n) {
        return n.tag === 'rect' && n.attrs.fill && n.attrs.fill === n.attrs.stroke
          && n.attrs['stroke-width'] === '1';
      }).map(function (r) { return r.attrs.fill; });
      var lines = NODES.filter(function (n) {
        return n.tag === 'polyline' && n.attrs.fill === 'none' && n.attrs.stroke;
      }).map(function (p) { return { stroke: p.attrs.stroke, points: p.attrs.points.split(' ').length }; });
      var names = group('stage-names');
      var f = svg.chartFrame || {};
      var hover = %s;
      if (hover !== null && SCRUBS.length) SCRUBS[0]({ clientX: hover, clientY: 50, pointerType: 'mouse' });
      print(JSON.stringify({ bodies: bodies, lines: lines,
                             zones: !!group('stage-zones'), band: !!group('stage-band'),
                             names: names ? names.children.map(function (t) {
                               return { x: t.attrs.x, y: t.attrs.y, fill: t.attrs.fill, text: t.textContent };
                             }) : [],
                             tip: TIPS.length ? TIPS[TIPS.length - 1] : null,
                             top: f.margin ? f.margin.t : 0, priceH: f.priceH || 0,
                             foot: (f.margin ? f.margin.t : 0) + (f.priceH || 0) }));
    """ % (json.dumps(opts), json.dumps(hover)))
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=30)
    last = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else ""
    assert last.startswith("{"), out.stdout + out.stderr
    return json.loads(last)


BASE = {"width": 600, "height": 300, "labels": ["a", "b", "c", "d", "e"],
        "candleUp": UP, "candleDown": DOWN}
HIDDEN_CLOSE = [{"name": "Close", "values": OHLC["close"], "color": "#123456", "hidden": True}]


# ------------------------------------------------------------ the candles


def test_with_stages_every_candle_is_in_its_weeks_stage_colour():
    got = _draw({**BASE, "candles": OHLC, "series": HIDDEN_CLOSE,
                 "candleTints": ["S4", "S4", "S4", "S2", "S2"],
                 "stageBand": ["S4", "S4", "S4", "S2", "S2"]})
    # The reference's rule: the week's stage, whichever way the bar went. Bar
    # two closed up and bar three down, and both are stage 4's colour.
    assert got["bodies"] == ["S4", "S4", "S4", "S2", "S2"]


def test_without_stages_every_candle_says_which_way_it_went():
    got = _draw({**BASE, "candles": OHLC, "series": HIDDEN_CLOSE})
    # up, up, down, up, down: the closes against their opens.
    assert got["bodies"] == [UP, UP, DOWN, UP, DOWN]


def test_a_bar_before_the_first_stage_keeps_the_colour_it_is_given():
    """stageTints gives such a bar the muted colour, so that green on this
    chart means one thing. A null entry, which no caller sends, would fall back
    to the direction colour rather than draw nothing."""
    got = _draw({**BASE, "candles": OHLC, "series": HIDDEN_CLOSE,
                 "candleTints": ["MUTED", "MUTED", "S2", "S2", None]})
    assert got["bodies"] == ["MUTED", "MUTED", "S2", "S2", DOWN]


# ------------------------------------------------------------ the line


def test_with_stages_the_line_is_drawn_a_run_per_stage():
    got = _draw({**BASE, "series": [{"name": "Close", "values": OHLC["close"],
                                     "color": "#123456", "tints": ["S4", "S4", "S2", "S2", "S2"]}],
                 "stageBand": ["S4", "S4", "S2", "S2", "S2"]})
    # Two runs, joined: the segment into bar three takes bar three's stage.
    assert [l["stroke"] for l in got["lines"]] == ["S4", "S2"]
    assert [l["points"] for l in got["lines"]] == [2, 4]


def test_without_stages_the_line_is_one_colour():
    got = _draw({**BASE, "series": [{"name": "Close", "values": OHLC["close"], "color": "#123456"}]})
    assert [l["stroke"] for l in got["lines"]] == ["#123456"]


# ------------------------------------------------ nothing drawn behind them


def test_no_tint_and_no_band_behind_the_price_any_more():
    """The candles and the line carry the colour now. A tint of the same
    colour behind them only took contrast from the candles it sat under."""
    got = _draw({**BASE, "candles": OHLC, "series": HIDDEN_CLOSE,
                 "candleTints": ["S4"] * 5, "stageBand": ["S4"] * 5,
                 "stageNames": ["Stage 4 · Declining"] * 5})
    assert got["zones"] is False and got["band"] is False


# ---------------------------------------------------------------- the names


NAMES = {"S1": "Stage 1 · Basing", "S2": "Stage 2 · Advancing",
         "S3": "Stage 3 · Topping", "S4": "Stage 4 · Declining"}


def _staged(stages, **extra):
    """A line chart of len(stages) bars, each in the stage given."""
    n = len(stages)
    return {"width": 600, "height": 300, "labels": ["d%d" % i for i in range(n)],
            "series": [{"name": "Close", "values": [10 + (i % 3) * 0.5 for i in range(n)],
                        "color": "#123456", "tints": list(stages)}],
            "stageBand": stages, "stageNames": [NAMES[s] for s in stages], **extra}


def test_a_run_is_named_along_the_foot_as_fully_as_it_has_room_for():
    # 20 bars across 534px: about 27px a bar.
    got = _draw(_staged(["S4"] * 12 + ["S2"] * 2 + ["S3"] + ["S1"] * 5))
    # Wide: the whole name. Two bars: the number alone. One bar: nothing,
    # though its colour is still in its bar. Five: the whole name again.
    assert [t["text"] for t in got["names"]] == [
        "Stage 4 · Declining", "Stage 2", "Stage 1 · Basing"]
    fills = {t["text"]: t["fill"] for t in got["names"]}
    assert fills["Stage 2"] == "S2" and fills["Stage 1 · Basing"] == "S1"
    # Along the foot, inside the price area.
    for t in got["names"]:
        assert got["foot"] - 12 < float(t["y"]) < got["foot"]


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
        "Stage 4 · Declining", "Stage 2 · Advancing"]
    got = _draw({**opts, "sessions": True})
    assert [t["text"] for t in got["names"]] == ["Stage 4 · Declining"]
    # The line does not stand aside: only the name does.
    assert [l["stroke"] for l in got["lines"]] == ["S4", "S2"]


def test_without_names_nothing_is_written():
    opts = _staged(["S4", "S4", "S2", "S2", "S2"])
    del opts["stageNames"]
    got = _draw(opts)
    assert got["names"] == []
    assert [l["stroke"] for l in got["lines"]] == ["S4", "S2"]


def test_no_names_without_stages():
    opts = _staged(["S4"] * 5)
    del opts["stageBand"], opts["stageNames"]
    got = _draw(opts)
    assert got["names"] == []


# ---------------------------------------------------------------- the readout


def test_hovering_a_bar_names_its_stage():
    got = _draw(_staged(["S4", "S4", "S2", "S2", "S2"]), hover=0)
    assert "Stage</span><span>4 · Declining</span>" in got["tip"]
    assert 'style="color:S4"' in got["tip"]
    got = _draw(_staged(["S4", "S4", "S2", "S2", "S2"]), hover=100000)
    assert "Stage</span><span>2 · Advancing</span>" in got["tip"]


def test_the_readout_is_escaped():
    """A stage's name comes from the server, and the readout is HTML."""
    opts = _staged(["S2"] * 5)
    opts["stageNames"] = ["Stage 2 · <b>x</b>"] * 5
    got = _draw(opts, hover=0)
    assert "&lt;b&gt;x&lt;/b&gt;" in got["tip"] and "<b>x</b>" not in got["tip"]


def test_no_stage_row_in_the_readout_without_names():
    opts = _staged(["S2"] * 5)
    del opts["stageNames"]
    got = _draw(opts, hover=0)
    assert got["tip"] and "Stage" not in got["tip"]
