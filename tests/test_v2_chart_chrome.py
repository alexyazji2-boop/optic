"""The classic Chart page's chrome in v2 (C12): the reader's chart colours, the collapsible legend, full screen
and the navigator (static/v2/js/pages/chart-chrome.js, drawn by ui/pricechart.js, wired in pages/chart.js).

The keys and formats are compared with static/app.js as text, so a choice made in either app holds in the
other. The colour store, the navigator's drag maths and the legend's rows run in JavaScriptCore. Each piece was
also driven in headless Chrome at 1440, 1024 and 390 px against the running server, signed in, with real
pointer, touch and key events (~/Optic/work/v2-overnight/chrome/chrome_check.py, 112 of 112).
"""
import re

from tests.test_frontend_v2_stage0 import V2
from tests.test_v2_p3 import _run

ROOT = V2.parent.parent
JS = V2 / "js"
CLASSIC = (ROOT / "static/app.js").read_text()
CC = (JS / "pages/chart-chrome.js").read_text()
CH = (JS / "pages/chart.js").read_text()
PC = (JS / "ui/pricechart.js").read_text()
CSS = (V2 / "css/pages.css").read_text()
CHROME_CSS = CSS[CSS.index("/* The chart's chrome, from the classic Charting tab (C12)"):CSS.index("html.ch-max .ch-side, html.ch-max .ch-wrail { max-height")]
CSS_STUB = "globalThis.CSS = { supports: (p, v) => p === 'color' && /^(#[0-9a-f]{3}([0-9a-f]{3})?|rgb\\([\\d, ]+\\))$/i.test(String(v).trim()) };"


def test_colours_and_the_legend_share_the_classic_keys_and_formats():
    assert "const CHART_COLORS_KEY = 'optic.chart.colors.v1';" in CLASSIC and "export const COLOURS_KEY = 'optic.chart.colors.v1';" in CC
    assert "const CHART_COLOR_SLOTS = ['up', 'down', 'line'];" in CLASSIC
    assert re.findall(r"\['(up|down|line)', '([^']+)'\]", CC) == re.findall(r"\{ slot: '(up|down|line)', label: '([^']+)' \}", CLASSIC), \
        "the same three slots, with the classic picker's names"
    assert "localStorage.removeItem(CHART_COLORS_KEY)" in CLASSIC and "localStorage.removeItem(COLOURS_KEY)" in CC, "Reset removes the key in both"
    assert "const WS_LEGEND_KEY = 'optic.chart.legend.v1';" in CLASSIC and "export const LEGEND_KEY = 'optic.chart.legend.v1';" in CC
    assert "localStorage.getItem(WS_LEGEND_KEY) === 'open'" in CLASSIC and "localStorage.getItem(LEGEND_KEY) === 'open'" in CC, "folded unless opened"
    assert "wsLegendOpen ? 'open' : 'closed'" in CLASSIC and "open ? 'open' : 'closed'" in CC
    # settings of this browser, not one person's things: neither app moves them when the account changes
    device = (JS / "core/device.js").read_text()
    for key in ("optic.chart.colors.v1", "optic.chart.legend.v1"):
        assert f"'{key}'" not in device
    assert "colours: C.readColours(), legend: C.legendOpen()" in CH and "C.saveLegend(open)" in CH


def test_colours_are_read_and_written_as_the_classic_app_keeps_them(tmp_path):
    got = _run(tmp_path, CSS_STUB + f"""
      const C = await import('{(JS / "pages/chart-chrome.js").as_posix()}');
      localStorage.setItem('optic.chart.colors.v1', JSON.stringify({{ up: '#199e70', down: 'nonsense', line: 42, wick: '#fff' }}));
      const read = C.readColours();
      const a = C.setColour('down', '#4a93ea');
      // the classic app changes the line meanwhile; the next write keeps it
      localStorage.setItem('optic.chart.colors.v1', JSON.stringify(Object.assign(JSON.parse(localStorage.getItem('optic.chart.colors.v1')), {{ line: '#d95926' }})));
      const b = C.setColour('up', '');
      const stored = JSON.parse(localStorage.getItem('optic.chart.colors.v1'));
      const reset = C.resetColours();
      print(JSON.stringify({{ read, a, b, stored, reset, after: localStorage.getItem('optic.chart.colors.v1'), warn: C.warnText(1.42) }}));
    """)
    assert got["read"] == {"up": "#199e70"}, "the three slots only, and only colours"
    assert got["a"] == {"up": "#199e70", "down": "#4a93ea"}
    assert got["b"] == {"down": "#4a93ea", "line": "#d95926"} == got["stored"], "a slot the other app set meanwhile is kept; '' is back to the theme"
    assert got["reset"] == {} and got["after"] is None
    assert got["warn"] == "Hard to see against the chart background at 1.4:1. A mark needs about 3:1 to read as a shape.", "the classic note"
    i = CLASSIC.index("function markWarnText(contrast)")
    assert "Hard to see against the chart background at" in CLASSIC[i:i + 300] and "A mark needs about 3:1 to read as a shape." in CLASSIC[i:i + 300]


def test_the_colours_reach_the_candles_volume_and_line_through_the_theme_fallbacks():
    for rule in (".pc .wick.u, .pc .body.u { stroke: var(--pc-up, var(--c-pos)); fill: var(--pc-up, var(--c-pos)); }",
                 ".pc .wick.d, .pc .body.d { stroke: var(--pc-down, var(--c-neg)); fill: var(--pc-down, var(--c-neg)); }",
                 ".pc .vol.u { fill: var(--pc-up, var(--c-pos)); } .pc .vol.d { fill: var(--pc-down, var(--c-neg)); }",
                 ".pc .pline { fill: none; stroke: var(--pc-line, var(--c-chart-ink)); stroke-width: 1.8; } .pc .area { fill: var(--pc-area, var(--c-area-top)); }"):
        assert rule in CSS, rule
    assert "[['--pc-up', c.up], ['--pc-down', c.down], ['--pc-line', c.line]]" in CC
    # the wheel colours live and the choice is kept on change; a click redraws the rows after it has finished
    assert "main.addEventListener('input'" in CH and "C.liveRow(p, chartBg())" in CH
    assert "if (el.matches('[data-v2-cc-pick]')) { pickColour(" in CH
    assert "setTimeout(() => { if (live) paintColours(focus); }, 0);" in CH
    # the other app (or another tab) changing them is followed
    assert "window.addEventListener('storage', onStorage)" in CH and "window.removeEventListener('storage', onStorage)" in CH


def test_the_navigator_moves_resizes_and_stays_inside_the_history(tmp_path):
    got = _run(tmp_path, f"""
      const p = await import('{(JS / "ui/pricechart.js").as_posix()}');
      const w = {{ from: 400, to: 499 }}, N = 500, nw = p.navWindow;
      print(JSON.stringify({{
        back: nw('move', w, -150, N), past: nw('move', w, -900, N), on: nw('move', w, 30, N),
        wider: nw('from', w, -100, N), narrow: nw('from', w, 200, N), toBack: nw('to', w, -60, N), toOn: nw('to', {{ from: 100, to: 199 }}, 900, N),
        short: nw('move', {{ from: 0, to: 6 }}, 3, 7), jumpStart: nw('move', w, -400 - 50, N),
      }}));
    """)
    assert got["back"] == {"from": 250, "to": 349}, "the whole window moves back, the same width"
    assert got["past"] == {"from": 0, "to": 99} and got["on"] == {"from": 400, "to": 499}, "never past either end"
    assert got["wider"] == {"from": 300, "to": 499}, "the left edge shows more bars, the right stays"
    assert got["narrow"] == {"from": 490, "to": 499}, "ten bars at least, as the zoom keeps"
    assert got["toBack"] == {"from": 400, "to": 439}
    assert got["toOn"] == {"from": 100, "to": 499}
    assert got["short"] == {"from": 0, "to": 6}, "a history under ten bars is shown whole"
    assert got["jumpStart"] == {"from": 0, "to": 99}
    # pointer: the window moves, an edge resizes, a press outside jumps there and can go on to drag
    assert "if (mode === 'jump') {" in PC and "mode = 'move'; }" in PC
    assert "nav.setPointerCapture(e.pointerId)" in PC and "grab = touch ? 16 : 8" in PC
    # keyboard: a slider, with its range said in words
    assert 'role="slider"' in PC and "aria-valuetext" in PC
    assert "ArrowLeft: -step, ArrowDown: -step, ArrowRight: step, ArrowUp: step, PageDown: -span, PageUp: span, Home: -from, End: N - 1 - to" in PC
    # drawn across the plot's own width, so it lines up with the bars, and built once for a width
    assert "const x0 = layout.l, x1 = W - layout.r" in PC and "navBase.W !== W" in PC


def test_the_legend_lists_what_is_on_with_values_and_takes_it_off(tmp_path):
    got = _run(tmp_path, f"""
      const p = await import('{(JS / "ui/pricechart.js").as_posix()}');
      const names = {{ ma: 'MA', ema: 'EMA', bb: 'Bollinger', events: 'Earnings', ins: 'Insider trades', volume: 'Volume' }};
      print(JSON.stringify([
        p.legendKeys(names, {{ ma: true, ema: false, events: true, ins: true }}, {{ volume: true, rsi: true }}),
        p.legendKeys(names, {{ ma: false }}, {{ volume: false }}), p.legendKeys(undefined, {{ ma: true }}, {{}}),
      ]));
    """)
    assert got == [["ma", "events", "ins", "volume"], [], []]
    # the names are the Indicators menu's, in its order, with the volume pane
    assert "const LEGEND_NAMES = Object.fromEntries([...OVERLAYS, ['volume', 'Volume']]);" in CH
    assert "names: LEGEND_NAMES, legendOpen: V.legend, navigator: true," in CH
    # folded, the count; open, a value at the crosshair's bar for each line, or why there is none
    assert "`${n ? `${n} overlay${n === 1 ? '' : 's'}` : 'No overlays'}${nd ? `, ${nd} drawing${nd === 1 ? '' : 's'}` : ''}`" in PC
    assert "const i = cross >= 0 ? cross : to;" in PC and "'not enough bars'" in PC
    assert "<b data-lv=\"${id}\"></b>" in PC and "if (el.textContent !== t) el.textContent = t;" in PC, "values written in place"
    # the insider trades key: a green arrow up for a purchase, a red one down for a sale
    assert "ARROW('buy', 'M6 0 12 7H7.5v7h-3V7H0Z')}purchase" in PC and "ARROW('sell', 'M6 14 0 7h4.5V0h3v7H12Z')}sale" in PC
    assert ".pc-la.buy { fill: var(--c-pos); } .pc-la.sell { fill: var(--c-neg); }" in CSS
    # the cross does what unticking it in Indicators does
    i = CH.index("function removeOverlay(k)")
    body = CH[i:CH.index("\n}\n", i)]
    assert "saveView(); paintTools(); if (chart) chart.set({ overlays: V.overlays, panes: V.panes });" in body
    assert 'aria-controls="${lid}"' in PC and "legT.setAttribute('aria-expanded', String(open));" in PC
    # the legend replaces the key line under the chart
    assert 'id="ch-key"' not in CH and "#ch-key" not in CH


def test_full_screen_takes_the_window_and_gives_it_back():
    for sel in ("html.ch-max .rail", "html.ch-max .topbar", "html.ch-max .tabbar", "html.ch-max #legal-footer", "html.ch-max .page-view > nav.tabs"):
        assert sel in CSS, sel
    # the browser's own full screen on top, on the root, a refusal being a normal answer
    assert "root.requestFullscreen || root.webkitRequestFullscreen" in CC and "if (p && p.catch) p.catch(() => {});" in CC
    assert "['fullscreenchange', 'webkitfullscreenchange'].forEach((n) => document.addEventListener(n, onFullChange));" in CH
    assert "if (!C.nativeFull() && C.isMax()) { C.setMax(false, false); paintMax(); }" in CH, "the browser's exit takes the class too"
    # Escape leaves it, unless it is cancelling a drawing, a note, a menu or a dialog first
    assert "document.addEventListener('keydown', onMaxKey, true);" in CH
    i = CH.index("function onMaxKey(e)")
    body = CH[i:CH.index("\n}\n", i)]
    assert "V.tool !== 'select' || D.textFor || D.confirmClear || document.querySelector('details.menu[open]')" in body
    # leaving the page leaves full screen
    i = CH.index("export function dispose()")
    assert "if (C.isMax()) C.setMax(false);" in CH[i:i + 400]
    # the plot takes the height in full screen, keeping the bars in view
    assert "if (C.isMax()) return Math.max(isPhone() ? 240 : 320, room - 14);" in CH and "chart.set({ height: h, navH: navH() })" in CH
    # one button, named, pressed while on; the four corners are full screen's, as in the classic chart, and Fit has its own mark
    assert 'aria-pressed="${isMax()}" aria-label="Full screen"' in CC
    icons = (JS / "ui/icons.js").read_text()
    expand = re.search(r"expand: '([^']+)'", icons).group(1)
    fit = re.search(r"fit: '([^']+)'", icons).group(1)
    assert expand == '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>' and fit != expand
    assert "enter: 'M2 6V2h4M10 2h4v4M14 10v4h-4M6 14H2v-4'" in CLASSIC, "the classic button is the four corners too"
    assert "${C.maxButton()}</div>" in CH


def test_the_chrome_follows_the_house_rules():
    assert "var(--r-pill)" not in CHROME_CSS and "999px" not in CHROME_CSS, "no pill shapes"
    for pressed in ('.cc-swatch[aria-pressed="true"]', '.ch-tool[data-v2-ch-max][aria-pressed="true"]'):
        rule = CSS[CSS.index(pressed):CSS.index("}", CSS.index(pressed))]
        assert "gold" not in rule, "the gold outline is the sidebar's alone"
    sizes = [float(x) for x in re.findall(r"font(?:-size)?:[^;]*?(\d+(?:\.\d+)?)px", CHROME_CSS)]
    assert sizes and min(sizes) >= 12, "nothing under 12px"
    phone = CHROME_CSS[CHROME_CSS.index("@media (max-width: 860px)"):]
    assert ".pc-lt, .pc-lx { min-height: 44px; } .pc-lx { width: 44px; height: 44px; }" in phone
    assert ".cc-swatch, .cc-wheel { width: 44px; height: 44px; }" in phone
    assert "navH = () => (isPhone() ? 44 : 40)" in CH, "the navigator is a 44px target on a phone"
    for src in (CC, CHROME_CSS):
        assert "—" not in src, "no em dashes"
    assert not re.search(r"[\U0001F300-\U0001FAFF☀-➿]", CC + PC[PC.index("/* ---------- legend"):]), "line icons, not emoji"
    # the page no longer sends colours and full screen to the current app
    assert "chart colours and full screen are in the current app" not in CH
    # the Instrument page's chart asks for neither, and gets neither
    inst = (JS / "pages/instrument.js").read_text()
    assert "names:" not in inst and "navigator:" not in inst
    assert "${S.names ? '<div class=\"pc-leg\"" in PC and "${S.navigator ? '<svg class=\"pc-nav\"" in PC
