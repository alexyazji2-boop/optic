"""Stretching and squeezing the price scale by dragging it, on the Charting tab.

Asked for as "be able to zoom in/out of this tab by dragging the price up or
down", with a picture of the price axis. Dragging the axis up stretches the
prices about the middle of their range, down squeezes them, and a double press
on it, Reset zoom, a range pill, a bar size or a session puts back the range
the bars ask for. Stretched past that range the price is cut at the plot's
edges, and the last-price tag sits at the edge the price left by.

Checked in a browser on NVDA's 6M chart: 120px up was 2.12 times (e to the
120/160), the range went from 186.43-240.97 to 200.82-226.58, the candles were
cut at the top and the 232.02 tag sat at the top edge; 110px down was half, a
double press and Reset zoom were 1 again, and so was the 3M pill.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
CHARTS = (ROOT / "static/charts.js").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _run(prelude, script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    out = subprocess.run([exe, "-e", prelude + script], capture_output=True, text=True,
                         timeout=120, cwd=str(ROOT))
    assert "RESULT:" in out.stdout, (out.stdout + out.stderr)[-2000:]
    return json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])


def _charts(script):
    return _run((ROOT / "tests/support/recording_dom.js").read_text() + CHARTS + """
      var n = 60, labels = [], close = [];
      for (var i = 0; i < n; i += 1) {
        labels.push(new Date(Date.UTC(2026, 6, 1) + i * 86400000).toISOString().slice(0, 10));
        close.push(100 + i * 0.5);
      }
      function chart(extra) {
        NODES.length = 0;
        var opts = { width: 900, height: 420, labels: labels, valueTags: true,
          series: [{ name: 'Close', values: close }] };
        for (var k in (extra || {})) opts[k] = extra[k];
        return lineChart(opts);
      }
    """, script)


def _app(script):
    return _run("""
      load('tests/support/browser_stubs.js');
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      document.documentElement.style.removeProperty = function () {};
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
    """, script)


def test_a_stretch_divides_the_range_about_its_middle():
    out = _charts("""
      var plain = chart().chartFrame;
      var twice = chart({ yZoom: 2 }).chartFrame;
      var half = chart({ yZoom: 0.5 }).chartFrame;
      var fixed = chart({ yZoom: 2, yDomain: [10, 90] }).chartFrame;
      print('RESULT:' + JSON.stringify({ plain: [plain.lo, plain.hi], twice: [twice.lo, twice.hi],
        half: [half.lo, half.hi], fixed: [fixed.lo, fixed.hi] }));
    """)
    lo, hi = out["plain"]
    mid, span = (lo + hi) / 2, hi - lo
    assert out["twice"] == pytest.approx([mid - span / 4, mid + span / 4])
    assert out["half"] == pytest.approx([mid - span, mid + span])
    assert out["fixed"] == [10, 90], "a chart with its own fixed scale, RSI's, is not stretched"


def test_stretched_the_price_area_is_clipped_and_squeezed_it_is_not():
    out = _charts("""
      chart({ yZoom: 2 });
      var clip = NODES.filter(function (x) { return x.tag === 'clipPath'; });
      var rect = clip.length ? clip[0].children[0].attrs : null;
      var using = NODES.filter(function (x) { return x.attrs['clip-path']; }).map(function (x) { return x.tag; });
      var line = NODES.filter(function (x) { return x.tag === 'polyline' && x.attrs['clip-path']; }).length;
      chart({ yZoom: 0.5 });
      var squeezed = NODES.filter(function (x) { return x.tag === 'clipPath'; }).length;
      chart();
      var plain = NODES.filter(function (x) { return x.attrs['clip-path']; }).length;
      print('RESULT:' + JSON.stringify({ clips: clip.length, id: clip.length && clip[0].attrs.id, rect: rect, using: using,
        line: line, squeezed: squeezed, plain: plain }));
    """)
    assert out["clips"] == 1 and out["id"].startswith("plot-clip-")
    assert out["line"] >= 1, "the price line is cut at the plot's edges"
    assert "g" in out["using"], "and the layers of the price area with it"
    assert out["squeezed"] == 0 and out["plain"] == 0


def test_a_tag_for_a_price_off_the_scale_sits_at_the_edge_it_left_by():
    out = _charts("""
      var f = chart({ yZoom: 6 }).chartFrame;
      var tags = NODES.filter(function (x) { return x.tag === 'rect' && x.attrs.rx === '3'; })
        .map(function (r) { return Number(r.attrs.y) + Number(r.attrs.height) / 2; });
      print('RESULT:' + JSON.stringify({ tags: tags, top: f.margin.t, priceH: f.priceH,
        lastY: f.yOf(close[n - 1]) }));
    """)
    assert out["lastY"] < out["top"], "the last price is above the stretched scale"
    assert out["tags"] and min(out["tags"]) >= out["top"], "its tag is not drawn above the plot"


def test_a_level_off_the_scale_loses_its_label():
    out = _charts("""
      chart({ yZoom: 6, refLines: [{ value: 101, label: 'Support 101', color: '#888888' },
                                   { value: close[30], label: 'Middle', color: '#888888' }] });
      var texts = NODES.filter(function (x) { return x.tag === 'text'; }).map(function (x) { return x.textContent; });
      print('RESULT:' + JSON.stringify(texts.filter(function (t) { return /Support|Middle/.test(t); })));
    """)
    assert out == ["Middle"]


def test_the_scale_is_a_handle_only_when_asked_for():
    out = _charts("""
      var asked = [];
      chart({ onYZoom: function (f) { asked.push(f); } });
      var grip = NODES.filter(function (x) { return x.attrs['data-price-scale']; });
      chart();
      var none = NODES.filter(function (x) { return x.attrs['data-price-scale']; }).length;
      print('RESULT:' + JSON.stringify({ grip: grip.length, style: grip.length && grip[0].attrs.style, none: none }));
    """)
    assert out["grip"] == 1 and "cursor:ns-resize" in out["style"] and "touch-action:none" in out["style"]
    assert out["none"] == 0
    grip = CHARTS[CHARTS.index("  if (onYZoom) {\n    const grip = s('rect', {"):]
    grip = grip[:grip.index("    root.appendChild(grip);")]
    assert "const move = (e) => onYZoom(from * Math.exp((startY - e.clientY) / Y_ZOOM_PX));" in grip, (
        "up stretches, down squeezes, from where the drag began")
    assert "window.addEventListener('pointermove', move);" in grip, "the window carries the drag"
    assert "onYZoom(1);" in grip, "a double press"
    assert CHARTS.index("  root.appendChild(overlay);") < CHARTS.index("    root.appendChild(grip);"), (
        "above the overlay, so a press there is not a pan or a measurement")


def test_the_charting_tab_keeps_the_stretch_and_clears_it_where_the_window_clears():
    out = _app("""
      var redraws = 0;
      // Run at once, as a frame would later; 0, as no frame is left pending.
      requestAnimationFrame = function (f) { f(); return 0; };
      wsRedrawChart = function () { redraws += 1; };
      wsSetYZoom(40); var top = wsYZoom;
      wsSetYZoom(0.01); var bottom = wsYZoom;
      wsSetYZoom(1.01); var snapped = wsYZoom;
      wsSetYZoom(2); var zoomed = wsZoomed();
      wsWindow = null; wsResetZoom(); var reset = wsYZoom;
      print('RESULT:' + JSON.stringify({ top: top, bottom: bottom, snapped: snapped, zoomed: zoomed, reset: reset,
        redraws: redraws, plain: wsZoomed() }));
    """)
    assert out["top"] == 12 and out["bottom"] == 0.25, "held between a quarter and twelve times"
    assert out["snapped"] == 1, "a hair from the bars' own range is that range"
    assert out["zoomed"] is True and out["reset"] == 1 and out["plain"] is False
    assert out["redraws"] >= 4
    for anchor in ("    wsWindow = null;   // a range pill overrides a manual zoom\n    wsYZoom = 1;",
                   "    wsWindow = null;   // a size change overrides a manual zoom\n    wsYZoom = 1;",
                   "      wsWindow = null;\n      wsYZoom = 1;"):
        assert anchor in APP, anchor
    mount = APP[APP.index("function wsMountChart() {"):]
    mount = mount[:mount.index("\n}\n")]
    assert "yZoom: wsYZoom," in mount and "onYZoom: wsSetYZoom," in mount
    assert "if (evt.target.closest && evt.target.closest('[data-price-scale]')) return;" in APP, (
        "the page's pan stands aside for the scale")
    assert "${wsZoomed() ? `<button type=\"button\" class=\"ws-menu-btn ws-zoom-reset\"" in APP
    assert "wsZoomed() ? `${shown} · zoomed`" in APP


def test_a_marker_stretched_off_the_scale_has_no_badge():
    """Just past the top edge, where a badge below the price would land back on
    the plot with no marker to belong to."""
    out = _charts("""
      var f = chart({ yZoom: 6 }).chartFrame;
      // Three pixels over the stretched scale, and well inside the range the
      // bars ask for, so the scale itself does not move.
      close[36] = f.hi + 3 * (f.hi - f.lo) / f.priceH;
      chart({ yZoom: 6, events: [{ index: 36, kind: 'sell', value: 1e8, label: 'Sell $100.0M' },
                                 { index: 30, kind: 'sell', value: 5e7, label: 'Sell $50.0M' }] });
      var texts = NODES.filter(function (x) { return x.tag === 'text'; }).map(function (x) { return x.textContent; });
      print('RESULT:' + JSON.stringify(texts.filter(function (t) { return /Sell/.test(t); })));
    """)
    assert out == ["Sell $50.0M"], "the trade over the stretched scale has no badge"
