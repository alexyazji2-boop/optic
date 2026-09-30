"""A candle chart opens on the newest candles that still read as candles.

Reported with NKE on the hour over three months: "these candles are not even
visible". It was about 450 candles in 950 pixels of plot, two pixels each,
which draws a body 1.3 pixels wide, so every candle ran into the next and the
chart read as a jagged line with no candles in it. At five pixels a candle the
body is three wide with a gap. Nothing is dropped: the chart opens on the
newest part of what was loaded, and the wheel, the drag and the navigator reach
the rest. A line has no such limit, so this is candles only.
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
    consts = "\n".join(re.search(r"^const %s = [^\n]*;" % n, RAW, re.M).group()
                       for n in ("CANDLE_MIN_SLOT", "WS_MIN_BARS"))
    src = ("function assert(v, m) { if (!v) throw new Error(m); }\n"
           "var wsFit = null, chartMode = 'candle', hostWidth = 1040;\n"
           "var document = { getElementById: function () { return { clientWidth: hostWidth }; } };\n"
           + consts + "\n"
           + "\n".join(_raw_fn(n) for n in ("wsCandles", "wsSliceWindow", "wsReadableBars",
                                             "wsReadable"))
           + "\n" + scenario + "\nprint('TEST_OK');")
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=30)
    assert "TEST_OK" in out.stdout, out.stdout + out.stderr


SERIES = """
function series(n) {
  var s = { dates: [], open: [], high: [], low: [], close: [] };
  for (var i = 0; i < n; i++) { s.dates.push('d' + i); s.open.push(i); s.high.push(i + 1); s.low.push(i - 1); s.close.push(i + 0.5); }
  return s;
}
"""


def test_nke_on_the_hour_opens_on_the_newest_candles_that_fit():
    """446 candles, a 1040px chart: 950 of plot at five a candle is 190."""
    _js(SERIES + """
      var out = wsReadable(series(446));
      assert(out.dates.length === 190, 'shown ' + out.dates.length);
      assert(out.dates[189] === 'd445' && out.dates[0] === 'd256', 'the newest, in order');
      assert(out.open.length === 190 && out.close[189] === 445.5, 'every array cut alike');
      assert(wsFit && wsFit.shown === 190 && wsFit.total === 446, 'the status line is told');
    """)


def test_a_range_that_already_fits_is_left_whole():
    _js(SERIES + """
      var s = series(120);
      assert(wsReadable(s) === s, 'untouched');
      assert(wsFit === null, 'nothing to report');
    """)


def test_a_line_is_never_trimmed():
    _js(SERIES + """
      chartMode = 'line';
      var s = series(446);
      assert(wsReadable(s) === s && wsFit === null, 'line mode');
    """)


def test_the_count_follows_the_chart_width():
    _js(SERIES + """
      hostWidth = 1890;   // full screen on a wide display
      assert(wsReadableBars() === 360, 'wide ' + wsReadableBars());
      hostWidth = 300;    // a phone
      assert(wsReadableBars() === 48, 'narrow ' + wsReadableBars());
      hostWidth = 0;      // not laid out yet
      assert(wsReadableBars() === 174, 'fallback ' + wsReadableBars());
    """)


def test_both_paths_open_on_it_and_an_explicit_zoom_overrides_it():
    series = _fn("wsSeries")
    # Under a day, on the size's own window of the history loaded behind it.
    assert "const shown = wsReadable(from ? wsSliceWindow(full, { from, to: total }) : full);" in series
    assert "return wsReadable(sliceSeries(raw, chartRange, chartInterval, full));" in series
    assert series.count("wsFit = null;") == 2, "a zoom the reader chose is not trimmed"
    assert "const CANDLE_MIN_SLOT = 5;" in RAW
