"""The Charting tab as a chart-first workspace.

Asked for with a Hyper Terminal screenshot as the visual reference: the price
chart taking most of the space, a compact volume pane, a compact symbol and
timeframe header with an OHLC and volume readout, no redundant labels or
competing panels, secondary settings in a compact menu, and an expanded view.

Measured at 1440x900 before: the plot was about 800x520 under two toolbar
rows, beside a 245px dock of four widgets, with the symbol and bar size
stated three times (the legend's title, the status strip, the interval
button) and not once beside the price. After: 1072x586, one toolbar row, the
dock shut until a widget is asked for, and "SPY 1h · Candles" in the header.

Checked in the running UI at 1440x900, 1280x800, 1152x720 and 1100x760 (the
last two are 1440x900 at 125% and 1280x800 at about 115% browser zoom), 960x600
(150%) and 375x812: no toolbar button outside the toolbar, no two chart
labels overlapping, every drawing tool and every widget button on screen and
clickable, the header on one line down to 1100px.
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
CHARTS = (ROOT / "static/charts.js").read_text()
CSS = (ROOT / "static/styles.css").read_text()
NO_COMMENTS = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _fn(name, src=APP):
    start = src.index("function %s(" % name)
    nxt = src.find("\nfunction ", start + 1)
    return src[start:nxt if nxt > 0 else len(src)]


def _run(prelude, script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    out = subprocess.run([exe, "-e", prelude + script], capture_output=True, text=True,
                         timeout=120, cwd=str(ROOT))
    blob = out.stdout + out.stderr
    assert "RESULT:" in blob, blob[-2000:]
    return json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])


APP_PRELUDE = """
  load('tests/support/browser_stubs.js');
  document.documentElement.style = document.documentElement.style || {};
  document.documentElement.style.setProperty = function () {};
  document.documentElement.style.removeProperty = function () {};
  try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
  var R = {};
"""


# ------------------------------------------------------- one price tag


def _tags(script):
    return _run((ROOT / "tests/support/recording_dom.js").read_text() + CHARTS + """
      var n = 60, labels = [], close = [], sma = [];
      for (var i = 0; i < n; i += 1) {
        labels.push(new Date(Date.UTC(2026, 6, 1) + i * 86400000).toISOString().slice(0, 10));
        close.push(700 + i);
        sma.push(690 + i * 0.9);
      }
      function tagsReading(text) {
        return NODES.filter(function (nd) { return nd.tag === 'text' && nd.textContent === text; }).length;
      }
      var R = {};
    """, script + "\nprint('RESULT:' + JSON.stringify(R));")


def test_the_price_is_tagged_once_in_line_mode():
    """In line mode the price series is drawn, so it took a tag of its own as
    well as the price tag: two pills reading 769.64, 17px apart, beside SPY's
    weekly close."""
    out = _tags("""
      NODES.length = 0;
      lineChart({ width: 900, height: 420, labels: labels, valueTags: true,
        series: [{ name: 'Close', values: close }, { name: 'SMA', values: sma }] });
      R.price = tagsReading('759.00');
      R.sma = tagsReading('743.10');
    """)
    assert out["price"] == 1, "the last close is one pill, not two"
    assert out["sma"] == 1, "and every other series keeps its own"


def test_candle_mode_was_already_tagged_once_and_still_is():
    out = _tags("""
      NODES.length = 0;
      lineChart({ width: 900, height: 420, labels: labels, valueTags: true,
        candles: { open: close, high: close, low: close, close: close },
        series: [{ name: 'Close', values: close, hidden: true }] });
      R.price = tagsReading('759.00');
    """)
    assert out["price"] == 1


# ------------------------------------------------------- the header


def test_the_header_names_the_bar_size_and_the_style():
    out = _run(APP_PRELUDE, """
      chartRange = '6m'; chartInterval = 'daily';
      chartMode = 'candle';
      R.candles = wsHeadFrame({ open: [1], high: [1], low: [1], close: [1] });
      R.noOhlc = wsHeadFrame({ close: [1] });
      chartMode = 'area';
      R.area = wsHeadFrame({ close: [1] });
      print('RESULT:' + JSON.stringify(R));
    """)
    assert out["candles"] == '1D<span class="ws-head-style"> · Candles</span>'
    # Candles need OHLC; without it the chart draws a line, and says so.
    assert out["noOhlc"] == '1D<span class="ws-head-style"> · Line</span>'
    assert out["area"] == '1D<span class="ws-head-style"> · Area</span>'


def test_a_redraw_puts_the_readout_back_on_the_newest_bar():
    """wsRedrawChart rebuilt the toolbar and the legend and never the header.
    Hourly to weekly through the bar-size menu left "O — H — L — C —" over a
    weekly chart whose last bar was 768.35 / 772.65 / 758.79 / 769.64: the
    readout still held the index the crosshair had last been on, and the weekly
    series has 26 bars to the hourly's 449."""
    redraw = _fn("wsRedrawChart")
    assert redraw.index("wsMountChart();") < redraw.index("wsSyncHead();")
    sync = _fn("wsSyncHead")
    assert "tf.innerHTML = wsHeadFrame(wsSeries(d));" in sync
    assert "wsHoverReadout(null);" in sync


def test_the_readout_volume_is_compact_with_the_count_on_hover():
    out = _run(APP_PRELUDE, """
      R.row = wsOhlcRow({ open: 769.35, high: 770.08, low: 769.17, close: 769.67, volume: 7160248 });
      print('RESULT:' + JSON.stringify(R));
    """)
    assert "V <b>7.16M</b>" in out["row"]
    assert 'title="7,160,248 shares"' in out["row"]


def test_the_header_folds_by_its_own_width():
    """The same header sits beside a dock, under Pulse and in full screen, so
    the window's width cannot say what fits in it."""
    head = NO_COMMENTS[NO_COMMENTS.index("\n.ws-head {"):]
    head = head[:head.index("}")]
    assert "container: ws-head / inline-size;" in head
    folds = re.findall(r"@container ws-head \(max-width: (\d+)px\) \{(.*?)\n\}", NO_COMMENTS, re.S)
    by = {int(w): body for w, body in folds}
    assert sorted(by) == [700, 860, 1000]
    assert ".chart-pulse-lab { display: none; }" in by[1000]
    assert ".stage-chip" in by[860] and ".ws-head-name" in by[860]
    assert ".ws-head-style { display: none; }" in by[700]


def test_the_legend_title_no_longer_repeats_the_header():
    legend = _fn("wsLegend")
    title = legend[legend.index('class="ws-leg-title"'):]
    title = title[:title.index("</button>")]
    assert "STATE.chartSymbol" not in title
    assert "chartIntervalLabel()" not in title
    assert "ws-leg-count" in title


# ------------------------------------------------------- competing panels


def test_the_dock_starts_shut_and_a_stored_arrangement_is_kept():
    assert "let wsDockOpen = [];" in APP
    after = APP[APP.index("let wsDockOpen = [];"):]
    after = after[:after.index("function wsSaveDock()")]
    assert "localStorage.getItem(WS_DOCK_KEY)" in after
    assert "if (Array.isArray(saved)) wsDockOpen = saved" in after


def test_layers_counts_what_it_holds_that_is_on():
    out = _run(APP_PRELUDE, """
      R.rest = wsTuckedOn();
      wsPanesOpen = ['rsi'];
      R.withPane = wsTuckedOn();
      R.bar = wsToolbar();
      print('RESULT:' + JSON.stringify(R));
    """)
    assert out["rest"] == 1, "volume is on by default, and it is in Layers"
    assert out["withPane"] == 2
    assert re.search(r'data-ws-tools[^>]*>Layers <span class="ws-count">2</span>', out["bar"])


def test_layers_closes_when_you_click_away_or_press_escape():
    """It floats over the chart now, so a drawer left open would sit over the
    candles. A click inside it is left alone: its own menus are in there."""
    click = APP[APP.index("if (wsToolsOpen && STATE.view === 'chart'"):]
    click = click[:click.index("\n  }\n")]
    assert "!evt.target.closest('.ws-tools, [data-ws-tools]')" in click
    assert "wsToolsOpen = false;" in click
    toggle = APP.index("if (evt.target.closest('[data-ws-tools]')) {")
    assert APP.index("if (wsToolsOpen && STATE.view === 'chart'") < toggle
    keys = _fn("wsDrawKeys")
    assert "if (evt.key === 'Escape' && (wsMenuOpen || wsToolsOpen)) {" in keys


# ------------------------------------------------------- fit and reset


def test_fit_has_a_control_and_the_control_has_a_handler():
    bar = _fn("wsToolbar")
    assert "data-ws-fit" in bar and "wsShowsAll() ? 'disabled' : ''" in bar
    assert "if (evt.target.closest('[data-ws-fit]')) { wsFitAll(); return; }" in APP
    # The name is new to the namespace (see CLAUDE.md on data-* collisions).
    assert len(re.findall(r"data-ws-fit\b", APP)) == 2


def test_fit_shows_every_bar_with_the_price_scale_fitted():
    out = _run(APP_PRELUDE, """
      var FULL = { dates: [] };
      for (var i = 0; i < 100; i += 1) FULL.dates.push('2026-01-' + (i < 9 ? '0' : '') + (i + 1));
      wsBaseSeries = function () { return FULL; };
      wsSeries = function () { return { dates: FULL.dates.slice(50) }; };
      STATE.chartData = { ticker: 'SPY' };
      var redraws = 0; wsRedrawChart = function () { redraws += 1; };
      wsWindow = null; wsYZoom = 2.5;
      R.before = wsShowsAll();
      wsFitAll();
      R.win = wsWindow; R.yZoom = wsYZoom; R.after = wsShowsAll();
      wsFitAll();
      R.redraws = redraws;
      print('RESULT:' + JSON.stringify(R));
    """)
    assert out["before"] is False
    assert out["win"] == {"from": 0, "to": 100}
    assert out["yZoom"] == 1
    assert out["after"] is True
    assert out["redraws"] == 1, "a second press with everything on screen redraws nothing"


def test_the_price_scale_says_what_its_gestures_are():
    grip = CHARTS[CHARTS.index("'data-price-scale': '1',"):]
    grip = grip[:grip.index("grip.addEventListener('pointerdown'")]
    assert "grip.appendChild(s('title', {}," in grip
    assert "Double-click to fit it to the bars on screen." in grip


# ------------------------------------------------------- the expanded view


def test_full_screen_spans_both_of_the_shells_tracks():
    """`.app` is rail then content. Full screen hides the rail, auto-placement
    put the content in the rail's `auto` track, and a 258px band of nothing ran
    down the right of a 1440px screen: the plot was 1023px wide, and is 1327."""
    assert "grid-template-columns: auto minmax(0, 1fr);" in CSS
    assert '\nbody.ws-max[data-view="chart"] .app-main { grid-column: 1 / -1; }' in NO_COMMENTS


def test_the_chart_view_gives_mains_top_padding_to_the_chart():
    assert '\nbody[data-view="chart"] main { padding-top: var(--space-2); }' in NO_COMMENTS
    # Full screen still takes all of it, and wins on specificity.
    assert 'body.ws-max[data-view="chart"] main { padding: 0; }' in NO_COMMENTS


# ------------------------------------------------------- the rails


def _media(query):
    """The body of every top-level @media block with exactly this query."""
    out = []
    for m in re.finditer(r"@media %s \{" % re.escape(query), NO_COMMENTS):
        depth, i = 1, m.end()
        while depth:
            depth += {"{": 1, "}": -1}.get(NO_COMMENTS[i], 0)
            i += 1
        out.append(NO_COMMENTS[m.end():i - 1])
    return "\n".join(out)


def test_every_drawing_tool_fits_at_desktop_heights():
    """Nineteen buttons need about 730px. At 1100x760 six were below the rail's
    bottom edge, snapping among them, with the scrollbar hidden."""
    assert ".ws-rail .ws-tool { width: 28px; height: 28px; }" in _media("(max-height: 950px)")
    two = _media("(max-height: 820px)")
    assert "grid-template-columns: repeat(2, 28px);" in two
    assert ".ws-rail-gap, .ws-rail-sep { grid-column: 1 / -1;" in two
    assert "align-content: space-between;" in two, "the rows spread down the rail"


def test_the_drawing_rail_has_no_hole_under_its_tools():
    """Asked to "fill this space out", with the rail circled in full screen.
    `.ws-rail-gap` was a flexible spacer that took all the spare height, so the
    tools sat at the top and the rest of the rail was one gap above Snap. The
    spare height is shared by the dividers between groups now, capped, and the
    rail spreads what is left. Measured after: from the top of the rail to its
    foot with no hole at 1100x760, 1440x900 and 1920x1080, normal and full
    screen; dividers 17px at 1440x900, 42px in full screen there."""
    assert "\n.ws-rail-gap { flex: 1 1 auto;" not in NO_COMMENTS, "the hole is back"
    assert "\n.ws-rail { justify-content: space-between; }" in NO_COMMENTS
    sep = NO_COMMENTS[NO_COMMENTS.index("\n.ws-rail-sep {"):]
    sep = sep[:sep.index("}")]
    for decl in ("flex: 1 1 var(--space-2);", "max-height: 44px;", "align-self: stretch;"):
        assert decl in sep, decl


def test_the_tools_are_grouped_with_a_divider_between_kinds():
    out = _run(APP_PRELUDE, """
      navigator.platform = navigator.platform || 'MacIntel';   // the undo shortcut's label
      var html = wsToolRail();
      // The order of tools and dividers as the rail draws them.
      R.seq = (html.match(/data-ws-tool="[a-z]+"|ws-rail-sep|data-ws-snap/g) || [])
        .map(function (m) { return m.replace(/data-ws-tool="|"/g, ''); });
      // Every group in one run, so a divider falls only where the kind changes.
      var seen = {}, runs = 0, prev = null;
      WS_TOOLS.forEach(function (t) { if (t.group !== prev) { runs += 1; seen[t.group] = (seen[t.group] || 0) + 1; prev = t.group; } });
      R.runs = runs; R.groups = Object.keys(seen).length;
      print('RESULT:' + JSON.stringify(R));
    """)
    assert out["runs"] == out["groups"] == 5
    assert out["seq"] == [
        "cursor", "ws-rail-sep",
        "trend", "ray", "hline", "vline", "channel", "ws-rail-sep",
        "rect", "fibdraw", "fibext", "pitchfork", "ws-rail-sep",
        "arrow", "text", "ws-rail-sep",
        "ruler", "rr", "position", "ws-rail-sep",
        "data-ws-snap",
    ], out["seq"]


def test_the_widget_buttons_share_the_rails_height_where_it_is_a_column():
    """Circled in the same request: fourteen buttons, then nothing down to
    Pulse. Above 900px only, where the rail is a column; below it the rail is a
    scrolling row and growing would mean wider."""
    col = _media("(min-width: 901px)")
    assert ".ws-wrail-btn { flex: 1 1 auto; max-height: 64px; justify-content: center; }" in col
    # Pulse keeps its place at the foot, which the cap leaves room for.
    pulse = NO_COMMENTS[NO_COMMENTS.index("\n.ws-wrail-pulse {"):]
    assert "margin-top: auto;" in pulse[:pulse.index("}")]


def test_the_widget_rail_keeps_the_report_pills_corner_free():
    """Measured at 1440x900: the rail's last button, Pulse, under the Report a
    problem pill, so a press on Pulse opened the report form."""
    desk = _media("(min-width: 560px)")
    assert 'body[data-view="chart"]:not(.ws-max) .ws-wrail { padding-bottom: 72px; }' in desk
    short = _media("(min-width: 560px) and (max-height: 760px)")
    assert ".ws-wrail-lab { display: none; }" in short
    # Without the label the button still has its name.
    rail = _fn("wsWidgetRail")
    assert rail.count("title=") >= 2
