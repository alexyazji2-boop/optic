"""The price line is green when the price is up over the bars shown, red when down.

Asked for as "whenever a chart is in an increasing matter, make the line green
and in a decreasing matter, make the line red", with the Charting tab's AAPL
one-minute day open, then chosen as one colour for the whole line (the way
Robinhood and Google Finance draw it) over a line that changes colour as it
goes. The line had been Optic's gold.

Stages take the line over while they are drawn, as they do the candles: asked
for later as "and so the same feature with the lines" (test_stage_band.py).
With Stages off the line is green or red by its own move, as here.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
RAW = (ROOT / "static/app.js").read_text()


def _strip(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"^\s*//.*$", " ", text, flags=re.M)


APP = _strip(RAW)


def _fn(name):
    body = APP[APP.index("function " + name + "("):]
    return body[:body.index("\n}") + 2]


def _raw_fn(name):
    return re.search(r"^function " + name + r"\([^\n]*\) \{.*?^\}", RAW, re.M | re.S).group()


JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _js(scenario):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = ("function assert(v, m) { if (!v) throw new Error(m); }\n"
           "var C = { pos: 'GREEN', neg: 'RED', ink2: 'GREY' };\n"
           "var chartColors = {};\n"
           + _raw_fn("priceLineColor") + "\n" + _raw_fn("lineMarks")
           + "\n" + scenario + "\nprint('TEST_OK');")
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=30)
    assert "TEST_OK" in out.stdout, out.stdout + out.stderr


def test_up_over_the_bars_shown_is_green_and_down_is_red():
    _js("""
      assert(priceLineColor([100, 98, 103]) === 'GREEN', 'up overall, with a dip');
      assert(priceLineColor([100, 104, 97]) === 'RED', 'down overall, with a rally');
      assert(priceLineColor([100, 90, 100]) === 'GREEN', 'unchanged is not a fall');
    """)


def test_it_is_measured_from_the_first_price_to_the_last_not_the_first_slot():
    """An intraday series can open and close on bars with no price yet."""
    _js("""
      assert(priceLineColor([null, 100, 101, 99, null]) === 'RED', 'nulls at both ends');
      assert(priceLineColor([NaN, 50, 51]) === 'GREEN', 'a NaN is not a price');
    """)


def test_no_direction_is_neutral():
    _js("""
      assert(priceLineColor([]) === 'GREY', 'empty');
      assert(priceLineColor([42]) === 'GREY', 'one price');
      assert(priceLineColor(undefined) === 'GREY', 'no series');
    """)


def test_a_colour_the_reader_picked_still_wins():
    _js("""
      chartColors.line = '#123456';
      assert(priceLineColor([1, 2]) === '#123456' && priceLineColor([2, 1]) === '#123456', 'chosen');
      assert(lineMarks().join() === '#123456', 'one colour to avoid');
      chartColors = {};
      assert(lineMarks().join() === 'GREEN,RED', 'both, since a pan can flip it');
    """)


# ------------------------------------------------------------ every price chart


def test_every_price_chart_draws_its_line_in_its_direction():
    swing = _fn("swingPriceBlock")
    assert "color: candleMode ? C.ink : priceLineColor(ps.close)," in swing
    assert "[{ name: 'Close', color: priceLineColor(ps.close) }]" in swing
    assert "color: wsCandles(ps) ? C.ink : priceLineColor(ps.close)," in _fn("wsMountChart")
    inst = _fn("drawInstrumentChart")
    assert "const lineColor = candles ? C.brand : priceLineColor(d.close);" in inst
    assert "values: d.close, color: lineColor," in inst
    assert "color: priceLineColor(ltSer.close) }" in APP
    assert "values: ltSer.close, color: priceLineColor(ltSer.close), hidden: ltCandles" in APP
    assert "host.appendChild(sparkline(vals, 96, 24, priceLineColor(vals)));" in APP
    assert "chartColor('line')" not in APP, "a price line still reads the single-slot default"


def test_the_averages_keep_clear_of_both_colours_the_line_can_take():
    assert ": lineMarks()), ...(marks || [])].map(lc));" in _fn("maColorsOnChart")
    assert "chartColor('down')] : lineMarks())," in _fn("chartBaseColors")


def test_the_picker_shows_the_pair_until_a_colour_is_picked():
    pop = _fn("wsColorPop")
    assert "const paired = row.slot === 'line' && !chosen;" in pop
    assert "linear-gradient(90deg, ${C.pos} 50%, ${C.neg} 50%)" in pop
    assert "const on = !!current && current.toLowerCase()" in pop, \
        "no preset may show as pressed for a default that is two colours"
    assert "Stages is on, so the candles and the line are" in RAW, "it says Stages have the line"


def test_the_legend_reads_the_stages_the_same_in_both_modes():
    """"Candles only" was right for a day: stages coloured the candles alone.
    They colour the line as well now, so the row reads the same in both."""
    leg = _fn("wsLegend")
    assert "'candles only'" not in leg
    assert ": !tinted ? 'unavailable' : intra ? 'by week' : '';" in leg
