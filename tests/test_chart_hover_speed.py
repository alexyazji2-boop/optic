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
    assert "wsHoverSeries.data === d ? wsHoverSeries.ps" in head
    assert "wsHoverSeries = { data: d, ps };" in _fn(APP, "function wsMountChart(")
    # "No bar" always redraws: a live tick calls it to refresh the day change.
    assert "i !== null && i !== undefined && i === wsHoverLast" in head
