"""The instrument page names its instrument, and its tiles line up.

Asked for with a picture of DXY's page, which read "DXY" over "US dollar index"
in small type: "make it clearer that this subchart for the ticker DXY is for
the US dollar index". Then "center all of the text as well and keep them
horizontally aligned", over a row where Last and RSI had a third line and the
other three did not, so each tile, centred on its own content, put its caption
and its figure at a different height from its neighbours'.

The heading is "US Dollar Index (DXY)" over what the index measures, centred;
every tile has three lines, the third the level a change is measured from; and
the lines are rows of the row, so they stay level whatever wraps. The page's
"What is this?" chip asked Pulse about STATE.ticker, the Analysis tab's stock,
and now asks about the instrument.

Checked in a browser at 1440px: the five captions at 483, the figures at 505,
the third lines at 551, the heading's three lines centred on the panel's
middle; the chip drafted "Explain what US Dollar Index (DXY) actually is" with
NVDA loaded on Analysis.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.analytics import macro
from app.analytics.series_stats import snapshot

ROOT = Path(__file__).resolve().parent.parent
MAIN = (ROOT / "app/main.py").read_text()
CSS = (ROOT / "static/styles.css").read_text()
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


DXY = {
    "available": True, "symbol": "DX-Y.NYB", "label": "DXY", "name": "US Dollar Index",
    "note": "US dollar index", "group": "fx",
    "about": "The US dollar against a basket of six major currencies.",
    "snapshot": {"last": 102.022, "chg_1d": 0.56, "chg_20d": 2.473, "close_20d_ago": 99.56,
                 "vs_sma200": 2.788, "sma200": 99.2544, "rsi": 74.96,
                 "pct_from_52w_high": 0.0, "high_52w": 102.022},
}

# Each tile's spans, in order, as [class, text]; the heading's three lines.
_READ = """
  function read(html) {
    var tiles = html.split('<div class="tile">').slice(1).map(function (t) {
      return (t.match(/<span class="[^"]*">[^<]*(<[^/][^>]*>[^<]*<\\/[a-z]+>)?[^<]*<\\/span>/g) || []).map(function (sp) {
        return [sp.match(/class="([^"]*)"/)[1], sp.replace(/<[^>]+>/g, '').trim()];
      });
    });
    var head = html.slice(html.indexOf('<div class="inst-head">'), html.indexOf('<div class="inst-stats">'));
    return { tiles: tiles,
      kicker: (head.match(/<div class="weekly-kicker">([^<]*)</) || [])[1],
      title: (head.match(/<h2 class="weekly-title">([^<]*)</) || [])[1],
      sub: (head.match(/<p class="weekly-sub">([^<]*)</) || [])[1] };
  }
"""


def test_the_heading_names_the_index_and_says_what_it_measures():
    out = _run(_READ + """
      var d = %s;
      var named = read(renderInstrument(d));
      var plain = JSON.parse(JSON.stringify(d));
      delete plain.name; delete plain.about; plain.label = 'VIX'; plain.group = 'volatility';
      plain.note = 'S&P 30-day implied vol';
      var bare = read(renderInstrument(plain));
      print('RESULT:' + JSON.stringify({ named: named, bare: bare }));
    """ % json.dumps(DXY))
    assert out["named"]["title"] == "US Dollar Index (DXY)"
    assert out["named"]["sub"] == DXY["about"], "what it measures, not the name again"
    assert out["named"]["kicker"] == "FX", "an acronym, not 'Fx'"
    assert out["bare"]["title"] == "VIX" and out["bare"]["sub"] == "S&amp;P 30-day implied vol"
    assert out["bare"]["kicker"] == "Volatility"


def test_every_tile_has_three_lines_and_the_third_is_the_level():
    out = _run(_READ + """
      var d = %s;
      var full = read(renderInstrument(d)).tiles;
      d.snapshot.sma200 = null; d.snapshot.vs_sma200 = null;   // too short for a 200-day average
      var short = read(renderInstrument(d)).tiles;
      print('RESULT:' + JSON.stringify({ full: full, short: short }));
    """ % json.dumps(DXY))
    assert [len(t) for t in out["full"]] == [3, 3, 3, 3, 3]
    assert [t[2] for t in out["full"]] == [
        ["delta up", "+0.56% today"], ["note", "from 99.56"], ["note", "average 99.25"],
        ["note", "Overbought territory"], ["note", "high 102.02"]]
    assert out["short"][2] == [["label", "vs 200-day"], ["value flat", "—"], ["note", ""]], (
        "the line is kept, empty, so the row still has three in every tile")


def test_the_three_lines_are_rows_of_the_row_and_the_heading_is_centred():
    tile = CSS[CSS.index(".inst-stats .tile {"):]
    tile = tile[:tile.index("}")]
    assert "display: grid;" in tile and "grid-row: span 3;" in tile
    assert "grid-template-rows: subgrid;" in tile, "a line that wraps moves in every tile"
    assert ".inst-stats .tile .label { min-height: 0; align-self: end; }" in CSS
    assert ".inst-head { text-align: center; }" in CSS
    assert ".inst-head .weekly-sub { margin-inline: auto; }" in CSS


def test_what_is_this_asks_about_the_instrument_on_screen():
    out = _run("""
      var drafted = [];
      draftPulse = function (t) { drafted.push(t); };
      STATE.ticker = 'NVDA';
      STATE.instrument = { symbol: 'DX-Y.NYB', label: 'DXY' };
      STATE.instrumentData = null;                 // still loading
      openPulseWith('instrument');
      STATE.instrumentData = %s;
      openPulseWith('instrument');
      openPulseWith('gex');                        // every other topic is still the stock's
      print('RESULT:' + JSON.stringify(drafted.map(function (t) { return t.slice(0, 60); })));
    """ % json.dumps(DXY))
    assert out[0].startswith("Explain what DXY actually is")
    assert out[1].startswith("Explain what US Dollar Index (DXY) actually is")
    assert "NVDA" in out[2]
    assert not any("NVDA" in t for t in out[:2])


def test_the_catalogue_and_the_endpoint_carry_the_name():
    dxy = next(i for i in macro.INSTRUMENTS if i["symbol"] == "DX-Y.NYB")
    assert dxy["label"] == "DXY", "the tables and the strip keep the short label"
    assert dxy["name"] == "US Dollar Index"
    for word in ("euro", "yen", "pound", "Canadian dollar", "krona", "Swiss franc", "stronger dollar"):
        assert word in dxy["about"], word
    assert "—" not in dxy["about"]
    assert '"name": meta.get("name"),' in MAIN and '"about": meta.get("about"),' in MAIN


def test_the_levels_are_the_ones_the_changes_are_measured_from():
    idx = pd.bdate_range("2025-01-01", periods=300)
    close = pd.Series(100 + np.sin(np.arange(300) / 9) * 5 + np.arange(300) * 0.01, index=idx)
    snap = snapshot(pd.DataFrame({"Close": close}), "X")
    assert snap["close_20d_ago"] == pytest.approx(close.iloc[-21], abs=1e-3)
    assert snap["chg_20d"] == pytest.approx((close.iloc[-1] / snap["close_20d_ago"] - 1) * 100, abs=1e-2)
    assert snap["sma200"] == pytest.approx(close.tail(200).mean(), abs=1e-3)
    assert snap["high_52w"] == pytest.approx(close.tail(252).max(), abs=1e-3)
    short = snapshot(pd.DataFrame({"Close": close.tail(60)}), "X")
    assert short["sma200"] is None and short["vs_sma200"] is None
