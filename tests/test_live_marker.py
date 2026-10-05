"""The live marker on a chart's newest point is easy to find.

Asked for as "make the chart blink more visible, pop out more", with a
screenshot of QQQ's hourly line where it could barely be found: a 4px dot
breathing by 14%, and one 1.5px outline of a halo reaching 2.6 times the dot
from 55% opacity, in the line's own colour over a near-black plot. Now two
filled ripples half a beat apart reach 4.2 times it from 90%, and the dot is
larger, swells by a third and glows in its own colour. Rendered through the
recording DOM rather than read as text, so the count of ripples is the count
drawn.
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
CHARTS = (ROOT / "static/charts.js").read_text()
CSS = (ROOT / "static/styles.css").read_text()
NO_COMMENTS = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _drawn(live):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = ((ROOT / "tests/support/recording_dom.js").read_text() + CHARTS + """
      var labels = [], close = [];
      for (var i = 0; i < 40; i += 1) {
        labels.push(new Date(Date.UTC(2026, 8, 1) + i * 86400000).toISOString().slice(0, 10));
        close.push(700 + i);
      }
      setChartLive(%s);
      NODES.length = 0;
      lineChart({ width: 900, height: 420, labels: labels, markerLast: true,
        series: [{ name: 'Close', values: close, color: '#0ca30c' }] });
      var cls = function (n) { return n.attrs['class'] || ''; };
      var halos = NODES.filter(function (n) { return n.tag === 'circle' && /live-halo/.test(cls(n)); });
      var dots = NODES.filter(function (n) { return n.tag === 'circle' && /live-dot/.test(cls(n)); });
      print('RESULT:' + JSON.stringify({
        halos: halos.map(function (n) { return { cls: cls(n), r: n.attrs.r, fill: n.attrs.fill,
          opacity: n.attrs['fill-opacity'], stroke: n.attrs.stroke }; }),
        dots: dots.map(function (n) { return { r: n.attrs.r, color: n.attrs.color, fill: n.attrs.fill }; }) }));
    """ % ("true" if live else "false"))
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=120)
    blob = out.stdout + out.stderr
    assert "RESULT:" in blob, blob[-2000:]
    return json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])


def test_a_live_chart_draws_two_filled_ripples_and_a_larger_dot():
    out = _drawn(True)
    assert [h["cls"] for h in out["halos"]] == ["live-halo", "live-halo live-halo-late"]
    for halo in out["halos"]:
        assert halo["fill"] == "#0ca30c" and halo["stroke"] == "#0ca30c"
        assert float(halo["opacity"]) > 0, "filled, not an outline"
    assert out["dots"] == [{"r": "5", "color": "#0ca30c", "fill": "#0ca30c"}]


def test_a_closed_market_draws_no_blink():
    """A blinking dot on a closed market would claim movement that is not
    happening."""
    out = _drawn(False)
    assert out == {"halos": [], "dots": []}


def test_the_ripples_spread_wide_and_the_dot_glows():
    halo = NO_COMMENTS[NO_COMMENTS.index("@keyframes live-halo {"):]
    halo = halo[:halo.index("\n}")]
    # Frame by frame: a bare `scale(4.2) in halo` matched the 100% frame alone
    # and passed with the spread itself put back to 2.6.
    assert "0%   { transform: scale(1);   opacity: 0.9; }" in halo
    assert "80%  { transform: scale(4.2); opacity: 0; }" in halo
    assert "\n.live-halo-late { animation-delay: -0.8s; }" in NO_COMMENTS
    assert "animation: live-halo 1.6s" in NO_COMMENTS
    dot = NO_COMMENTS[NO_COMMENTS.index("\n.live-dot {"):]
    assert "filter: drop-shadow(0 0 4px currentColor);" in dot[:dot.index("}")]
    beat = NO_COMMENTS[NO_COMMENTS.index("@keyframes live-dot {"):]
    assert "scale(1.32)" in beat[:beat.index("\n}")]


def test_less_motion_still_finds_it():
    """No animation for a reader who asked for less, and still a ring to see."""
    still = NO_COMMENTS[NO_COMMENTS.index("@media (prefers-reduced-motion: reduce) {\n  .live-halo"):]
    still = still[:still.index("\n}")]
    assert ".live-halo { animation: none; opacity: 0.45; transform: scale(2); }" in still
    assert ".live-dot { animation: none; }" in still
