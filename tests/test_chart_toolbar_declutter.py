"""The Charting toolbar, with fewer buttons and full screen on its own.

Asked for with a screenshot of the toolbar in three rows, Full screen circled:
"make this button separate from the rest and try to minimize the amount of
clutter in terms of buttons". It carried twenty-seven controls: eight overlay
menus and toggles, eight interval pills, five range pills, Reset zoom,
Line/Candles, Panes, Colours and Full screen.

Now full screen is an icon in the corner of the chart's own header, the eight
interval pills are one menu that names the size on screen, Fibs and Trends
are one Levels menu, and Panes sits with the other things that go on the
chart. Seventeen controls at rest, in two rows at 1000px wide, where the
screenshot had three. Every option is still there: the menus hold them.

Checked in a browser at 1000x725: two toolbar rows; the interval menu opens
with the eight sizes, marks the one on screen, and closes on a pick (1W, 1D
and 1h each switched the chart and relabelled the button); Levels holds all
five level overlays and Fibonacci draws from it; Panes opens with RSI and
MACD; the full-screen icon sits clear of the header's text in its corner,
enters and leaves full screen, and Escape leaves it.
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
CSS = (ROOT / "static/styles.css").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def strip_comments(js):
    js = re.sub(r"/\*.*?\*/", " ", js, flags=re.S)
    return re.sub(r"(?<!:)//[^\n]*", " ", js)


CODE = strip_comments(APP)


def fn(name, src=CODE):
    start = src.index("function %s(" % name)
    return src[start:].split("\nfunction ", 1)[0]


@pytest.fixture(scope="module")
def toolbar():
    """The toolbar as it renders, shut and with the interval menu open."""
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    script = """
      load('tests/support/browser_stubs.js');
      // app.js sets custom properties at load; the shared stub has no setter.
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      document.documentElement.style.removeProperty = function () {};
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
      function buttons(html) {
        var out = [];
        html.replace(/<button[^>]*>([\\s\\S]*?)<\\/button>/g, function (m, inner) {
          out.push(inner.replace(/<[^>]*>/g, '').replace(/&#9662;/g, '').replace(/\\s+/g, ' ').trim());
          return m;
        });
        return out;
      }
      var shut = wsToolbar();
      wsMenuOpen = 'interval';
      var open = wsToolbar();
      wsMenuOpen = null;
      print('RESULT:' + JSON.stringify({ shut: shut, open: open,
        shutButtons: buttons(shut), openButtons: buttons(open) }));
    """
    proc = subprocess.run([exe, "-e", script], capture_output=True, text=True,
                          timeout=180, cwd=str(ROOT))
    blob = proc.stdout + proc.stderr
    assert "RESULT:" in blob, blob[-1500:]
    return json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])


# ----------------------------------------------------------- fewer buttons


def test_the_toolbar_carries_seventeen_controls_at_rest(toolbar):
    """Tools is the phone's drawer button and is not drawn above 560px."""
    got = toolbar["shutButtons"]
    assert got[0] == "Tools"
    assert got[1:] == ["Reset", "Levels", "Stages", "Indicators", "Volume 1", "Events",
                       "Studies", "Panes", "1D", "1M", "3M", "6M", "1Y", "All",
                       "Line", "Candles", "Colours"], got


def test_the_interval_is_one_menu_naming_the_size_on_screen(toolbar):
    shut = toolbar["shut"]
    assert 'data-ws-menu="interval"' in shut
    assert "data-ws-interval" not in shut, "the sizes are in the menu, not on the bar"
    opened = toolbar["openButtons"]
    sizes = ["1m", "5m", "15m", "30m", "1h", "4h", "1D", "1W"]
    at = opened.index("1m")
    assert opened[at:at + 8] == sizes
    # The one on screen is marked in the menu.
    assert re.search(r'class="pill on"\s+data-ws-interval="daily"', toolbar["open"])


def test_a_size_picked_from_the_menu_closes_it():
    at = CODE.index("const wsInt = evt.target.closest('[data-ws-interval]');")
    handler = CODE[at:CODE.index("return;\n  }", at)]
    assert "if (wsMenuOpen === 'interval') {" in handler
    assert "wsMenuOpen = null;" in handler
    assert handler.index("wsMenuOpen = null;") < handler.index("const key = wsInt.dataset.wsInterval;")


def test_the_menu_reuses_the_pills_so_they_are_handled_as_before():
    body = fn("wsIntervalMenu")
    assert "rangePills(CHART_INTERVALS, active, 'data-ws-interval', 'Interval')" in body
    assert "data-ws-menu=\"interval\"" in body
    assert "rangePills(CHART_INTERVALS" not in fn("wsToolbar")


def test_every_level_is_on_one_menu():
    menus = APP[APP.index("const WS_MENUS = ["):]
    menus = menus[:menus.index("\n];")]
    assert "{ id: 'levels', label: 'Levels', items: ['fib', 'trends', 'sr', 'zones', 'accum'] }," in menus
    assert "id: 'fibs'" not in menus and "id: 'trends'" not in menus


def test_panes_sit_with_the_other_things_that_go_on_the_chart(toolbar):
    shut = toolbar["shut"]
    assert shut.index('data-ws-menu="panes"') < shut.index('class="ws-toolbar-gap"')
    assert shut.index('data-ws-menu="colors"') > shut.index('class="ws-toolbar-gap"')


# ------------------------------------------------------- full screen apart


def test_full_screen_is_not_on_the_toolbar(toolbar):
    assert "data-ws-max" not in toolbar["shut"]
    assert "Full screen" not in toolbar["shut"]


def test_full_screen_is_in_the_chart_panel_beside_the_header():
    """Beside the header, not in it: inside, it fell to a line of its own at
    1000px and covered Explain chart on a phone, where the header clips."""
    workspace = fn("renderChartWorkspace")
    canvas = workspace[workspace.index('<div class="ws-canvas'):]
    assert canvas.index("${wsMaxButton()}") < canvas.index('<div class="ws-head">')
    head = canvas[canvas.index('<div class="ws-head">'):]
    head = head[:head.index("</div>")]
    assert "wsMaxButton" not in head


def test_the_icon_says_what_it_does_in_both_states():
    body = fn("wsMaxButton")
    assert "data-ws-max" in body
    assert "aria-label=\"${on ? 'Exit full screen' : 'Full screen'}\"" in body
    assert 'aria-pressed="${on}"' in body
    assert "WS_MAX_ICONS.leave : WS_MAX_ICONS.enter" in body


def test_the_icon_answers_the_press_at_once():
    """Repainted before the two frames the redraw waits for, not after them."""
    body = fn("wsAfterMaximise")
    assert body.index("btn.outerHTML = wsMaxButton();") < body.index("requestAnimationFrame(")


def test_the_icon_keeps_to_its_corner_and_the_header_ends_before_it():
    """At 1000px the header is three lines, and on a phone one clipped line.
    The header ends short of the corner with a margin: the narrow header clips
    at its padding edge, so padding left the text running under the icon."""
    head = CSS[CSS.index(".ws-head {"):]
    head = head[:head.index("}")]
    assert "margin-right: calc(28px + var(--space-3));" in head
    assert "padding-right" not in re.sub(r"/\*.*?\*/", "", head, flags=re.S)
    btn = CSS[CSS.index(".ws-full-btn {"):]
    btn = btn[:btn.index("}")]
    for decl in ("position: absolute;", "top: var(--space-1);", "right: var(--space-2);",
                 "width: 28px;", "height: 28px;"):
        assert decl in btn, decl
    # The panel is what it is positioned against.
    canvas = CSS[CSS.index(".ws-canvas {"):]
    assert "position: relative;" in canvas[:canvas.index("}")]


def test_explain_chart_becomes_the_pulse_mark_where_its_words_do_not_fit():
    """On a phone the header is one clipped line, and beside the full-screen
    icon the label was cut to "Ex". The mark stands in for it there, and the
    button keeps its name for a screen reader either way."""
    body = fn("chartPulse")
    assert 'aria-label="Explain chart"' in body
    assert "pulseMarkHTML('chart-pulse-ico')" in body
    assert '<span class="chart-pulse-lab">Explain chart</span>' in body
    assert ".chart-pulse-ico { display: none;" in CSS
    for rule in (".ws-body.narrow .ws-head .chart-pulse-lab { display: none; }",
                 ".ws-body.narrow .ws-head .chart-pulse-ico { display: block; }"):
        assert rule in CSS, rule
