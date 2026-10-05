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
          var text = inner.replace(/<[^>]*>/g, '').replace(/&#9662;/g, '').replace(/\\s+/g, ' ').trim();
          // An icon button is read by its label, as a screen reader reads it.
          var label = (m.match(/aria-label="([^"]*)"/) || [])[1];
          out.push(text || label || '');
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


def _labels(html):
    """Button names in order, as the fixture's own helper reads them."""
    out = []
    for m in re.finditer(r"<button[^>]*>([\s\S]*?)</button>", html):
        text = " ".join(re.sub(r"<[^>]*>", "", m.group(1)).replace("&#9662;", "").split())
        label = re.search(r'aria-label="([^"]*)"', m.group(0))
        out.append(text or (label.group(1) if label else ""))
    return out


def _bar_and_drawer(html):
    """What is on the bar, and what is in Layers. The drawer is everything
    from its wrapper up to the spacer, which follows it directly."""
    at = html.index('<div class="ws-tools">')
    gap = html.index('<div class="ws-toolbar-gap">')
    return _labels(html[:at] + html[gap:]), _labels(html[at:gap])


def test_the_bar_carries_fifteen_controls_and_layers_holds_seven(toolbar):
    """Asked for as a chart-first workspace with "secondary settings in a
    compact menu". At 1440x900 the bar was two rows of twenty controls over
    the chart. On it now: what changes the chart often and what says what the
    chart is. In Layers: the layers you set up once. Every option is still
    there, and the count on Layers says how many of them are on. It shipped
    as More and was renamed, asked for as "something more fitting on a
    charting tab".

    The eighteenth control of the old count, the trading-hours menu, stays on
    the bar beside the bar size, as asked for ("regular trading hours" and
    "extended hours"); Chart read stays beside Reset and outside the drawer
    (see tests/test_chart_read.py); Fit is new, fit-to-data beside Reset zoom."""
    bar, drawer = _bar_and_drawer(toolbar["shut"])
    assert bar == ["Indicators", "Layers 1", "Chart read", "Reset", "1D", "Regular hours",
                   "1M", "3M", "6M", "1Y", "All", "Fit", "Candles", "Line", "Area"], bar
    assert drawer == ["Levels", "Stages", "Volume 1", "Events", "Studies", "Panes",
                      "Colours"], drawer


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
    """In the drawer with the other layers, and Colours with them now: the
    drawer is one wrapper since it became the desktop's menu too."""
    shut = toolbar["shut"]
    drawer = shut[shut.index('<div class="ws-tools">'):shut.index('<div class="ws-toolbar-gap">')]
    assert 'data-ws-menu="panes"' in drawer and 'data-ws-menu="colors"' in drawer
    assert 'data-ws-menu="indicators"' not in drawer, "Indicators stays on the bar"


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


# --------------------------------------------------------- the size grid
#
# Asked for with a screenshot of the open menu: "remove the circular
# surrounding of the time frames and have it cover the whole box in grids".
# The sizes were the row's pills, capsule and all, and the capsule kept around
# a two-line grid drew a stadium inside the box.


def css_rule(selector):
    """The declarations of the first rule written for exactly `selector`."""
    body = CSS[CSS.index("\n" + selector + " {") + 1:]
    return re.sub(r"/\*.*?\*/", "", body[:body.index("}")], flags=re.S)


def test_the_sizes_fill_the_menu_as_a_grid_with_no_capsule_around_them():
    pop = css_rule(".ws-menu-pop.ws-interval-pop")
    for decl in ("min-width: 0;", "padding: 0;", "overflow: hidden;"):
        assert decl in pop, decl
    grid = css_rule(".ws-interval-pop .pills")
    for decl in ("display: grid;", "grid-template-columns: repeat(4, minmax(52px, 1fr));",
                 "gap: 0;", "padding: 0;", "background: none;", "border: 0;",
                 "border-radius: 0;"):
        assert decl in grid, decl
    cell = css_rule(".ws-interval-pop .pill")
    for decl in ("border-radius: 0;", "border-right: 1px solid var(--border);",
                 "border-bottom: 1px solid var(--border);"):
        assert decl in cell, decl
    # No line along the menu's own edges, however many sizes there are.
    assert ".ws-interval-pop .pill:nth-child(4n) { border-right: 0; }" in CSS
    assert (".ws-interval-pop .pill:nth-last-child(-n+4):nth-child(4n+1),\n"
            ".ws-interval-pop .pill:nth-last-child(-n+4):nth-child(4n+1) ~ .pill "
            "{ border-bottom: 0; }") in CSS
    # The size on screen is still filled, and beats the cell's own background.
    assert (".ws-interval-pop .pill.on { background: var(--btn-primary); "
            "color: var(--btn-primary-ink); }") in CSS


def test_the_grid_rule_outweighs_the_menu_rule_it_would_have_lost_to():
    """`.ws-menu-pop` sets padding and a 210px floor further down the file at
    one class's weight, which is how the old `min-width: 0` never applied."""
    assert CSS.index(".ws-menu-pop {") > CSS.index(".ws-menu-pop.ws-interval-pop {")
    assert "\n.ws-interval-pop {" not in CSS


def _place(pop, host, width):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = re.search(r"^function wsPlaceMenu\(\) \{.*?^\}", APP, re.M | re.S).group()
    script = """
      var rect = function (l, w) { return { left: l, right: l + w }; };
      var HOST = %s, POP = %s;
      var pop = { style: {}, offsetWidth: POP.w,
                  offsetParent: { getBoundingClientRect: function () { return rect(HOST.l, HOST.w); } },
                  getBoundingClientRect: function () { return rect(HOST.l + POP.at, POP.w); } };
      var views = { chart: { querySelector: function () { return pop; } } };
      var document = { documentElement: { clientWidth: %d } };
      %s
      wsPlaceMenu();
      print('RESULT:' + JSON.stringify(pop.style));
    """ % (json.dumps(host), json.dumps(pop), width, src)
    out = subprocess.run([exe, "-e", script], capture_output=True, text=True, timeout=30)
    assert "RESULT:" in out.stdout, out.stdout + out.stderr
    return json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])


def test_a_menu_that_would_run_off_the_right_opens_leftward_from_its_button():
    """Measured at 1100px: the interval button at x=1003, its 210px menu
    ending at 1213, and two of the four columns off the window."""
    style = _place({"at": 0, "w": 210}, {"l": 1003, "w": 60}, 1100)
    # Its right edge on the button's: 1063 - 210 = 853, 150px left of it.
    assert style == {"left": "-150px", "right": "auto"}


def test_a_menu_that_fits_is_left_where_it_opened():
    assert _place({"at": 0, "w": 210}, {"l": 700, "w": 60}, 1440) == {}


def test_a_menu_is_never_pushed_off_the_left_edge_either():
    """A 300px menu under a button at x=100 in a 350px window: leftward would
    start at -140, so it is held 8px in from the edge instead."""
    style = _place({"at": 0, "w": 300}, {"l": 100, "w": 60}, 350)
    assert style == {"left": "-92px", "right": "auto"}


def test_every_redraw_that_can_leave_a_menu_open_places_it():
    toggle = CODE[CODE.index("const wsMenu = evt.target.closest('[data-ws-menu]');"):]
    toggle = toggle[:toggle.index("return;")]
    assert toggle.index("tb2.outerHTML = wsToolbar();") < toggle.index("wsPlaceMenu();")
    tools = CODE[CODE.index("if (evt.target.closest('[data-ws-tools]')) {"):]
    assert "wsPlaceMenu();" in tools[:tools.index("return;")]
    assert "if (tb && !same) tb.outerHTML = wsToolbar();\n    if (!same) wsPlaceMenu();" in CODE
    render = fn("renderChartWorkspace")
    assert render.index("${wsManagePanel()}`;") < render.index("wsPlaceMenu();")
