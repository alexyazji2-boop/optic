"""The Investing chart, drawn the way the Options chart is.

Asked for as "fix this investing chart to keep it consistent with that of the
options chart" and "200/40 SMA cuts off in the chart as well", on COIN.
Measured on 2026-10-07 against the local server:

- The averages were "40-week average" and "200-week average" in colours read
  straight off overlayStyle, beside the Options chart's "50-week SMA" from
  maColorsOnChart; the price line was "Weekly close" against "Close"; the
  retracement labels sat on the left edge, the Options chart's on the right.
- COIN listed in April 2021. Its 40-week average begins in January 2022 and
  its 200-week in February 2025, with nothing on the chart saying why the
  lines start in the middle of it.
- AAPL on 10Y: the payload's twelve years left two years of lead-in for an
  average that needs four, so the 200-week line began about two years in.

Checked in a browser at 1440x900: COIN 5Y keyed "40-week SMA (from Jan 2022)"
and "200-week SMA (from Feb 2025)" with the sentence under the plot, and the
61.8 (204.10) label on the right; AAPL 10Y drew both averages from the first
bar, 520 of 2392 weeks shown, with no note.
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


def _fn(head):
    at = APP.index(head)
    return APP[at:APP.index("\n}\n", at) + 3]


def _const(name):
    at = APP.index(f"const {name} = ")
    return APP[at:APP.index(";\n", at) + 2]


def _block():
    return _fn("function ltPriceBlock(h, lt, ltLevels) {")


def _run(script, prelude=""):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = (prelude + _const("LT_RANGES") + _const("LT_MA_PERIODS") + _const("LT_PAYLOAD_WEEKS")
           + "".join(_fn(h) for h in ("function ltMaLines(ser, unit, colors) {",
                                      "function ltMaNote(mas, ticker, full, unit) {",
                                      "function ltMonthYear(iso) {",
                                      "function ltNeedsAllBars(lt) {",
                                      "function levelsOffScaleText(refs, closes) {"))
           + script)
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    assert "RESULT:" in out.stdout, (out.stdout + out.stderr)[-2000:]
    return json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])


SERIES = """
  var nul = function (n) { var a = []; for (var i = 0; i < n; i++) a.push(null); return a; };
  var num = function (n) { var a = []; for (var i = 0; i < n; i++) a.push(100 + i); return a; };
  var dates = ['2024-01-01', '2024-02-05', '2024-03-04', '2024-04-01', '2024-05-06'];
"""


def test_each_average_says_where_it_begins_or_what_it_needs():
    out = _run(SERIES + """
      var ser = { dates: dates, ma: { 40: num(5), 200: nul(2).concat(num(3)) } };
      var full = ltMaLines(ser, 'week', { 40: 'blue', 200: 'pink' });
      var none = ltMaLines({ dates: dates, ma: { 40: num(5), 200: null } }, 'month',
                           { 40: 'blue', 200: 'pink' });
      print('RESULT:' + JSON.stringify({ full: full, none: none }));
    """)
    a40, a200 = out["full"]
    assert a40["name"] == "40-week SMA" and a40["short"] == "" and a40["color"] == "blue"
    assert a40["slot"] == "sma50", "the Options chart's middle average"
    assert a200["name"] == "200-week SMA" and a200["short"] == "from Mar 2024"
    assert a200["slot"] == "sma200" and a200["start"] == "2024-03-04"
    m200 = out["none"][1]
    assert m200["values"] is None and m200["short"] == "needs 200 months"


def test_the_note_names_the_history_and_why_the_line_starts_late():
    out = _run(SERIES + """
      var late = ltMaLines({ dates: dates, ma: { 40: nul(1).concat(num(4)), 200: nul(3).concat(num(2)) } },
                           'week', {});
      var whole = ltMaLines({ dates: dates, ma: { 40: num(5), 200: num(5) } }, 'week', {});
      var none = ltMaLines({ dates: dates, ma: { 40: num(5), 200: null } }, 'month', {});
      var full = { dates: ['2021-04-12'].concat(dates) };
      print('RESULT:' + JSON.stringify([ltMaNote(late, 'COIN', full, 'week'),
        ltMaNote(whole, 'AAPL', full, 'week'), ltMaNote(none, 'COIN', full, 'month')]));
    """)
    late, whole, none = out
    assert late.startswith("Optic's price history for COIN begins in Apr 2021.")
    assert "the 40-week starts in Feb 2024 and the 200-week starts in Apr 2024." in late
    assert whole == "", "nothing to explain when both lines run the width"
    assert none.endswith("so the 200-month has none yet.")


def test_the_window_asks_for_the_whole_history_when_its_averages_need_it():
    out = _run("""
      var ltRange, ltInterval;
      function weeks(n) { var a = []; for (var i = 0; i < n; i++) a.push('d'); return { series: { dates: a } }; }
      var rows = [];
      [['5y', 'weekly', 626], ['10y', 'weekly', 626], ['all', 'weekly', 287],
       ['10y', 'weekly', 287], ['5y', 'monthly', 626], ['1y', 'monthly', 287]].forEach(function (r) {
        ltRange = r[0]; ltInterval = r[1]; rows.push(ltNeedsAllBars(weeks(r[2])));
      });
      print('RESULT:' + JSON.stringify(rows));
    """)
    # 5Y weekly has 366 weeks of lead-in in twelve years; 10Y has 106 for a
    # 200-week average. A payload shorter than twelve years is the listing.
    assert out == [False, True, True, False, True, False]


def test_the_redraw_follows_the_same_rule_as_the_fetch():
    src = _fn("function ltSource(lt) {")
    assert "if (!ltNeedsAllBars(lt)) return base;" in src
    arrived = _fn("function allBarsArrived(symbol, size) {")
    assert "size === 'weekly' && ltNeedsAllBars(lt)" in arrived


def test_it_takes_the_options_charts_colours_names_and_label_side():
    block = _block()
    assert "const maOn = maColorsOnChart(ltCandles);" in block
    assert "ltMaLines(ltSer, unit, { 40: maOn.sma50, 200: maOn.sma200 })" in block
    assert "overlayStyle('sma50').color" not in block and "overlayStyle('sma200').color" not in block
    assert "[{ name: 'Close', color: priceLineColor(ltSer.close) }]" in block
    assert "{ name: 'Close',\n          values: ltSer.close" in block
    assert "Weekly'} close" not in block
    assert "name: `Up ${unit}`, color: chartColor('up')" in block, "the reader's candle colours"
    assert "candleUp: chartColor('up')" in block
    code = re.sub(r"/\*.*?\*/", "", block, flags=re.S)
    assert "refLabelSide" not in code, "labels on the right, as on the Options chart"


def test_both_charts_count_the_levels_they_cannot_draw_with_one_sentence():
    out = _run("""
      var refs = [{ value: 100 }, { value: 300 }, { value: 140 }];
      print('RESULT:' + JSON.stringify([levelsOffScaleText(refs, [120, 130, 150]),
        levelsOffScaleText([{ value: 140 }], [120, 150]), levelsOffScaleText(refs, [])]));
    """)
    two, none, empty = out
    assert two.startswith("2 levels sit too far outside the price range on screen to draw")
    assert none == "" and empty == ""
    assert "levelsOffScaleText(overlayRefs, ps.close)" in APP
    assert "levelsOffScaleText(zoneRefs, ltSer.close)" in _block()
    assert '<div id="chart-weekly-note"></div>' in APP
