"""The live marker on a chart's newest point: findable, and no heavier.

Its third weight. Asked first to "make the chart blink more visible, pop out
more", with a screenshot of QQQ's hourly line where it could barely be found:
a 4px dot breathing by 14%, and one 1.5px outline of a halo reaching 2.6 times
the dot from 55% opacity. That made two filled ripples half a beat apart
reaching 4.2 times it from 90%, and a 5px dot swelling by a third with a glow.
Then, on 2026-10-05: "the blinking dot is too heavy. make it softer", with a
picture of it as a green blob over the price tag. One lightly filled ripple
now, to 2.8 times from 55% on a slower beat, and a dot that grows 12% with a
faint glow. Rendered through the recording DOM rather than read as text, so
the count of ripples is the count drawn.
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


def _drawn(live, ends_today=True):
    """A series of 40 daily bars ending today in New York, or yesterday. The
    pulse is drawn only on a series that runs to today: a page in market hours
    set the flag for every chart it drew, lagged daily data included."""
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = ((ROOT / "tests/support/recording_dom.js").read_text() + CHARTS + """
      var labels = [], close = [];
      var end = Date.parse(etTodayISO() + 'T12:00:00Z') - (%s ? 0 : 86400000);
      for (var i = 39; i >= 0; i -= 1) {
        labels.push(new Date(end - i * 86400000).toISOString().slice(0, 10));
        close.push(739 - i);
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
    """ % ("true" if ends_today else "false", "true" if live else "false"))
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=120)
    blob = out.stdout + out.stderr
    assert "RESULT:" in blob, blob[-2000:]
    return json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])


def test_a_live_chart_draws_one_lightly_filled_ripple_and_a_slightly_larger_dot():
    out = _drawn(True)
    assert [h["cls"] for h in out["halos"]] == ["live-halo"], "one ripple, not two"
    halo = out["halos"][0]
    assert halo["fill"] == "#0ca30c" and halo["stroke"] == "#0ca30c"
    # Filled, so it is a mark and not a thicker line end, but lightly.
    assert 0 < float(halo["opacity"]) <= 0.2
    assert out["dots"] == [{"r": "4.5", "color": "#0ca30c", "fill": "#0ca30c"}]


def test_a_closed_market_draws_no_blink():
    """A blinking dot on a closed market would claim movement that is not
    happening."""
    out = _drawn(False)
    assert out == {"halos": [], "dots": []}


def test_the_ripple_and_the_glow_are_soft():
    halo = NO_COMMENTS[NO_COMMENTS.index("@keyframes live-halo {"):]
    halo = halo[:halo.index("\n}")]
    # Frame by frame: a bare `scale(2.8) in halo` would match the 100% frame
    # alone and pass with the spread put back to 4.2.
    assert "0%   { transform: scale(1);   opacity: 0.55; }" in halo
    assert "75%  { transform: scale(2.8); opacity: 0; }" in halo
    assert "live-halo-late" not in NO_COMMENTS and "live-halo-late" not in CHARTS
    assert "animation: live-halo 2.4s" in NO_COMMENTS
    dot = NO_COMMENTS[NO_COMMENTS.index("\n.live-dot {"):]
    assert "filter: drop-shadow(0 0 2px currentColor);" in dot[:dot.index("}")]
    beat = NO_COMMENTS[NO_COMMENTS.index("@keyframes live-dot {"):]
    beat = beat[:beat.index("\n}")]
    assert "scale(1.12)" in beat and "drop-shadow(0 0 3px currentColor)" in beat


def test_less_motion_still_finds_it():
    """No animation for a reader who asked for less, and still a ring to see."""
    still = NO_COMMENTS[NO_COMMENTS.index("@media (prefers-reduced-motion: reduce) {\n  .live-halo"):]
    still = still[:still.index("\n}")]
    assert ".live-halo { animation: none; opacity: 0.3; transform: scale(1.8); }" in still
    assert ".live-dot { animation: none; }" in still


def test_a_series_that_ends_before_today_does_not_pulse_on_a_live_page():
    """FINRA's daily short volume and the gamma profile pulsed "live" in
    market hours beside the one price that was."""
    assert _drawn(True, ends_today=False) == {"halos": [], "dots": []}
