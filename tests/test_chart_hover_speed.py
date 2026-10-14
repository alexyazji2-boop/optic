"""The chart readout keeps up with the pointer (lag and jitter reported 2026-10-13).

A mouse reports far more moves than the screen draws. Each one rebuilt the
tooltip, measured it straight after writing it (a forced layout), and rebuilt
the workspace's whole series for the O/H/L/C row. These pin the three fixes.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
CHARTS = (ROOT / "static/charts.js").read_text()


def _fn(src, head):
    start = src.index(head)
    return src[start:src.index("\n}\n", start)]


def test_pointer_moves_are_drawn_once_a_frame():
    scrub = _fn(CHARTS, "function bindScrub(")
    move = scrub[scrub.index("'pointermove'"):scrub.index("'pointerdown'")]
    assert "requestAnimationFrame(flush)" in move
    assert "onMove(evt)" not in move.replace("{ onMove(evt); return; }", "")
    # A move waiting for its frame must not draw after the pointer has left.
    assert "cancelAnimationFrame(frame)" in scrub


def test_the_tooltip_is_measured_only_when_its_content_changes():
    tip = _fn(CHARTS, "function showTip(")
    assert "tip._optHtml !== html" in tip
    assert tip.count("getBoundingClientRect") == 1
    assert "_optOn = false" in _fn(CHARTS, "function hideTip(")


def test_a_pointer_within_one_bar_reuses_its_readout():
    assert re.search(r"if \(i === readI && readHtml\) \{ showTip\(readHtml, evt\); return readSaid; \}", CHARTS)


def test_the_header_readout_does_not_rebuild_the_series_per_move():
    head = _fn(APP, "function wsHoverReadout(")
    assert "const cached = wsHoverSeries && wsHoverSeries.data === d;" in head
    assert "cached ? wsHoverSeries.ps : wsSeries(d)" in head
    assert "wsHoverSeries = { data: d, ps, fit: wsOhlcFit(ps) };" in _fn(APP, "function wsMountChart(")
    # "No bar" always redraws: a live tick calls it to refresh the day change.
    assert "i !== null && i !== undefined && i === wsHoverLast" in head


# ------------------------------------------- the header holds still (2026-10-14)
# Hovering the top of the plot made the O/H/L flicker: the hovered row was
# wider than the resting one (a raw timestamp, a longer volume), the header
# wrapped, the plot moved under the cursor, and it looped.

CSS = (ROOT / "static/styles.css").read_text()


def test_the_header_readout_carries_no_timestamp():
    assert "ws-ohlc-date" not in APP and "ws-ohlc-date" not in CSS
    assert "at(ps.dates)" not in _fn(APP, "function wsHoverReadout(")


def test_every_readout_of_the_header_is_sized_to_the_series():
    assert "${wsOhlcRow(bar, wsOhlcFit(ps))}" in APP
    head = _fn(APP, "function wsHoverReadout(")
    assert head.count("wsOhlcRow(bar, fit)") == 2
    assert "wsHoverSeries = { data: d, ps, fit: wsOhlcFit(ps) };" in APP
    assert re.search(r"\.ws-ohlc b \{[^}]*display: inline-block;", CSS)
    assert re.search(r"#ws-chg \{[^}]*min-width: 7\.5ch;", CSS)


def test_the_widths_cover_every_bar(tmp_path):
    import json, os, shutil, subprocess
    import pytest
    jsc = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
    exe = jsc if os.path.exists(jsc) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    script = """
      load('tests/support/browser_stubs.js');
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      document.documentElement.style.removeProperty = function () {};
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
      var ps = { open: [9.5, 99.25, 1203.4], high: [9.9, 99.9, 1250.0], low: [9.1, 98.0, 1190.2],
                 close: [9.8, 99.5, 1240.75], volume: [980120, 4640000, 123450000] };
      var fit = wsOhlcFit(ps);
      var widths = [0, 1, 2].map(function (i) {
        return wsOhlcRow({ open: ps.open[i], high: ps.high[i], low: ps.low[i], close: ps.close[i],
                           volume: ps.volume[i] }, fit).match(/min-width:[0-9.]+ch/g);
      });
      print('RESULT:' + JSON.stringify({ fit: fit, widths: widths, bare: wsOhlcRow(wsLastBar(ps)) }));
    """
    out = subprocess.run([exe, "-e", script], capture_output=True, text=True, timeout=120, cwd=str(ROOT))
    blob = out.stdout + out.stderr
    assert "RESULT:" in blob, blob[-2000:]
    res = json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])
    # "1,250.00" is the widest price; "123.45M" the widest volume.
    assert res["fit"] == {"price": 8, "volume": 7.5}
    # Every bar asks for the same widths, so the row is one width throughout.
    assert res["widths"][0] == res["widths"][1] == res["widths"][2]
    assert len(res["widths"][0]) == 5
    # Without a fit the row is as before (other callers, older tests).
    assert "min-width" not in res["bare"]
