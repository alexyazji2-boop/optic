"""The price mark coloured by Weinstein stage, as the reference chart draws it.

Built after TrendSpider's weekly PLTR, where every candle is in the colour of
its stage: green advancing, amber topping, red declining, light green basing.
Checked against that chart in a browser rather than argued: PLTR on the
Charting tab, weekly candles over the whole payload, drew 69 Stage 2, 11 Stage
3, 18 Stage 4 and 7 Stage 1 bodies -- the same weeks, one for one, as the
server's history -- and 126 daily bars over six months matched their weeks
with no mismatches.

Drawn that way, then as a band and a tint behind the price after NKE's red
rally, and as the reference again once asked for directly: "keep the candles
as is with the color change as per the reference screenshot attached, and so
the same feature with the lines". Candles and the line both, now.

The property under all of it is that a bar's colour is its own week's stage
and nobody else's: not a later week's (hindsight, which stage.py rules out and
tests/test_stage.py proves), not another symbol's (the payload's own ticker),
and not a neighbouring week's (one Monday rule, shared with the server).
"""
from __future__ import annotations

import datetime as dt
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP_SRC = (ROOT / "static/app.js").read_text()
CHARTS_SRC = (ROOT / "static/charts.js").read_text()
CSS = (ROOT / "static/styles.css").read_text()


def _strip(text: str) -> str:
    """Code without its comments. Tests in this repo have passed on their own
    prose more than once: a comment naming the fix satisfies a substring
    search for the fix."""
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"^\s*//.*$", " ", text, flags=re.M)


APP = _strip(APP_SRC)
CHARTS = _strip(CHARTS_SRC)
CLEAN_CSS = _strip(CSS)


def _fn(src: str, name: str) -> str:
    body = src[src.index("function " + name + "("):]
    return body[:body.index("\n}") + 2]


def _chart_fn() -> str:
    return _fn(CHARTS, "lineChart")


# ------------------------------------------------------------ the colours


def test_four_tokens_three_of_them_the_terminals_own():
    root = CLEAN_CSS[:CLEAN_CSS.index(':root[data-theme="light"]')]
    for n in (1, 2, 3, 4):
        assert "--stage-%d:" % n in root, n
    assert "--stage-2: var(--pos);" in root
    assert "--stage-3: var(--warn);" in root
    assert "--stage-4: var(--neg);" in root


def test_the_light_theme_has_its_own_stage_1():
    """The dark theme's light green is 1.3:1 on white. Measured: anything
    lighter than --pos 70% into --surface fails the 3:1 a mark needs."""
    light = CLEAN_CSS[CLEAN_CSS.index(':root[data-theme="light"]'):]
    light = light[:light.index("}")]
    assert "--stage-1:" in light


def test_the_charts_read_the_tokens_so_a_theme_flip_repaints_them():
    c_vars = CHARTS[CHARTS.index("const C_VARS = {"):]
    c_vars = c_vars[:c_vars.index("};")]
    for n in (1, 2, 3, 4):
        assert "stage%d: '--stage-%d'" % (n, n) in c_vars, n


# ------------------------------------------------------------ the renderer


def test_a_candle_takes_its_tint_before_its_direction():
    fn = _chart_fn()
    assert "candleTints = null" in fn
    assert re.search(r"const colour = \(candleTints && candleTints\[i\]\)\s*\|\|\s*\(up \?", fn)


def test_a_tinted_line_is_drawn_in_runs_coloured_by_the_bar_they_lead_into():
    """So the line changes colour at the bar whose week changed stage, and not
    one bar early."""
    fn = _chart_fn()
    assert "if (Array.isArray(se.tints))" in fn
    loop = fn[fn.index("if (Array.isArray(se.tints))"):]
    loop = loop[:loop.index("} else {")]
    assert "const c = tint(k);" in loop
    assert "runs.push({ color: c, from: k - 1, to: k })" in loop
    assert "pts.slice(run.from, run.to + 1)" in loop, "runs must share their joining point"
    assert "fill: run.color" in loop, "the area under each run is in its own stage"


def test_the_untinted_line_is_drawn_exactly_as_before():
    fn = _chart_fn()
    plain = fn[fn.index("if (Array.isArray(se.tints))"):]
    plain = plain[plain.index("} else {"):]
    plain = plain[:plain.index("if (markerLast")]
    assert "stroke: se.color" in plain
    assert "'data-draw': animating && !se.dash ? seriesDelay(se) : null" in plain


def test_the_end_dot_value_tag_hover_dot_and_swatch_follow_the_bar():
    """A tinted line is a different colour at every stage. Anything still in
    the base colour names a line that is not on the chart."""
    fn = _chart_fn()
    assert "const endColor = (se.tints && se.tints[lastIdx]) || se.color;" in fn
    # The end dot, and the live marker's two ripples round it (filled and
    # ringed, so the blink is visible: see .live-halo in styles.css).
    assert fn.count("stroke: endColor") == 1 and fn.count("fill: endColor") == 2
    assert "fill: endColor, 'fill-opacity': 0.28, stroke: endColor" in fn
    assert "color: (se.tints && se.tints[li]) || se.color" in fn
    assert "const hue = (se.tints && se.tints[i]) || se.color;" in fn
    assert "dots[k].setAttribute('fill', hue);" in fn
    assert '<span style="color:${hue}">' in fn


# ------------------------------------------------------------ the lookup


def test_nothing_is_tinted_when_off_or_hidden_and_intraday_is_by_week():
    """Intraday bars take their week's stage: the reading does not change
    inside a week, which is why a session's bars share one colour."""
    fn = _fn(APP, "stageTints")
    assert "if (!wsOverlayDrawn('stages') || !symbol) return null;" in fn


def test_an_unavailable_reading_is_not_a_falsy_test():
    assert "r.available !== true" in _fn(APP, "stageTints")


def test_a_bar_with_no_stage_is_muted_not_its_direction_colour():
    """Two colour languages on one chart would make green mean "up" on the left
    and "Stage 2" on the right."""
    fn = _fn(APP, "stageTints")
    assert "return n ? C['stage' + n] : C.muted;" in fn


def test_the_key_names_only_the_stages_on_screen():
    fn = _fn(APP, "stageTints")
    assert ".filter((n) => seen.has(n))" in fn
    assert "if (seen.has(0)) key.push" in fn


def test_a_bar_finds_its_week_by_the_shared_monday_rule():
    assert "byWeek.get(weekMonday(iso))" in _fn(APP, "stageTints")
    assert "const weekKey = weekMonday;" in _fn(APP, "aggregateWeekly")


def test_a_failed_fetch_redraws_nothing_so_a_blip_cannot_loop():
    fn = _fn(APP, "stageReading")
    assert "if (r) stagesArrived(symbol);" in fn
    assert "stageWaiting.has(symbol)" in fn, "one request in flight per symbol"
    fetch = _fn(APP, "fetchStage")
    assert re.search(r"if \(!r\) stageCache\.delete\(symbol\);\s*else stageSettled\.set", fetch)


def test_an_answer_redraws_only_a_chart_still_showing_that_symbol():
    # After any sweep in progress: see tests/test_oscillator_draw_on.py.
    assert "afterDrawsSettle(() => stagesRedraw(symbol));" in _fn(APP, "stagesArrived")
    fn = _fn(APP, "stagesRedraw")
    assert "d.ticker === symbol" in fn
    # The Charting tab's chart alone: no other chart draws stages.
    assert "if (STATE.view !== 'chart') return;" in fn
    assert "swingRedrawChart" not in fn and "drawInstrumentChart" not in fn
    # The colour wheel's OS picker belongs to its input; rebuilding the toolbar
    # under it shuts it.
    assert "wsRedrawChart({ keepToolbar: true })" in fn


# ------------------------------------------------------ the one chart that draws them


def test_the_chart_asks_for_its_own_payloads_symbol():
    """STATE.ticker and STATE.chartSymbol are independent, and the colours have
    to be the stages of the bars being drawn."""
    assert "const stages = wsStages(ps);" in _fn(APP, "wsMountChart")
    assert "stageTints((STATE.chartData || {}).ticker, ps.dates, !!ps.intraday)" in _fn(APP, "wsStages")


def test_with_stages_on_the_candles_and_the_line_take_the_stage_colour():
    """Asked for as "keep the candles as is with the color change as per the
    reference screenshot attached, and so the same feature with the lines". It
    had been a band and then a tint behind the price, after NKE's hourly
    candles in stage 4 drew a rally as a row of red ("why are all candles
    [red], even in uptrends like these?"). Stages off is the answer to that
    now: every bar its direction, and the line green or red by its own move."""
    assert "if (!wsCandles(ps)) return null;" not in _fn(APP, "wsStages")
    body = _fn(APP, "wsMountChart")
    assert "candleTints: stages ? stages.colors : null" in body
    assert "\n          tints: stages ? stages.colors : null" in body


def test_the_sub_charts_draw_no_stages():
    """Asked for as "remove the stages from the sub charts. it should be
    viewing only". The Options chart and the instrument pages coloured their
    price by stage too, each with its own switch, a key of what the stages
    mean, and on an instrument page a chip; all of it is gone from both, and
    they keep the range and Line or Candles. Stages are the Charting tab's."""
    for fn in ("swingPriceBlock", "drawInstrumentChart", "renderSwing", "renderInstrument"):
        body = _fn(APP, fn)
        for gone in ("stageTints(", "candleTints:", "stageBand:", "stageNames:", "stages.key",
                     "stagesToggleHTML", "stage-legend", "paintStageLegend", "stage-inst"):
            assert gone not in body, (fn, gone)
    for gone in ("function stagesToggleHTML(", "data-stages-toggle", "function paintStageLegend(",
                 "function stageLegendHTML("):
        assert gone not in APP, gone
    assert "chartStyleSeg('data-inst-mode', instrumentMode)" in _fn(APP, "renderInstrument")
    assert "chartStyleSeg('data-chart-mode', chartMode)" in _fn(APP, "renderSwing")


def test_one_array_colours_the_candles_the_line_and_the_names():
    """The candles, the line, the names along the foot and the readout's Stage
    row are one array, so a bar cannot be one stage's colour and another's
    name."""
    assert APP.count("candleTints: stages ? stages.colors : null") == 1
    # Case matters: candleTints is the candles', `tints` the line's.
    assert APP.count("tints: stages ? stages.colors : null") == 1
    assert APP.count("stageBand: stages ? stages.colors : null") == 1
    assert APP.count("stageNames: stages ? stages.labels : null") == 1
    fn = _fn(APP, "stageTints")
    assert "labels.push(title(n));" in fn
    assert "return { colors, labels, key, marks };" in fn
    # The key and the names say the same thing about the same stage.
    assert ".map((n) => ({ name: title(n), color: C['stage' + n] }));" in fn


def test_the_charting_legend_names_the_stages_on_screen():
    """The Charting tab's legend carries the key, with its own hide and remove
    buttons, and the sub charts' keys name only the up and down colours or the
    line they draw."""
    swing = _fn(APP, "swingPriceBlock")
    assert "...(candleMode" in swing and "stages" not in swing
    inst = _fn(APP, "drawInstrumentChart")
    assert "...(candles ? [{ name: 'Up day', color: C.s3 }, { name: 'Down day', color: C.s8 }]" in inst
    leg = _fn(APP, "wsLegend")
    assert 'data-ws-leg="stages"' in leg
    assert 'data-ws-hide="stages"' in leg and 'data-ws-off="stages"' in leg


def test_the_charting_legend_says_why_nothing_is_coloured():
    leg = _fn(APP, "wsLegend")
    for why in ("'by week'", "'loading'", "'not enough history'", "'unavailable'"):
        assert why in leg, why
    assert "'weekly, not on intraday'" not in leg


# ------------------------------------------------------------ the switch


def test_it_is_off_until_someone_turns_it_on():
    """Asked for as "turn stages off by default", once Stages coloured the
    candles and the line themselves. A browser that never pressed it stored
    nothing, so it opens off as well; one that turned it on keeps it on."""
    assert "let showStages = false;" in APP
    assert "showStages = localStorage.getItem(SHOW_STAGES_KEY) === 'on';" in APP
    assert "showStages = localStorage.getItem(SHOW_STAGES_KEY) !== 'off';" not in APP


def test_it_is_wired_like_every_other_toggle():
    flags = APP[APP.index("const WS_FLAGS = {"):]
    assert "stages: () => showStages," in flags[:flags.index("};")]
    setters = APP[APP.index("const WS_SETTERS = {"):]
    assert "stages: (on) => { showStages = !!on; storeFlag(SHOW_STAGES_KEY, on); }," \
        in setters[:setters.index("};")]
    menus = APP[APP.index("const WS_MENUS = ["):]
    assert "{ id: 'stages', label: 'Stages', items: ['stages'] }," in menus[:menus.index("];")]


def test_the_style_dialog_offers_no_colour_for_it():
    defs = APP[APP.index("const OVERLAY_DEFS = ["):]
    entry = defs[defs.index("id: 'stages'"):]
    assert "fixed:" in entry[:entry.index("},")]
    row = _fn(APP, "wsManageRow")
    assert "${def.fixed ? `<p class=\"ws-mnote\">${esc(def.fixed)}</p>` : def.fill ?" in row


def test_the_colour_picker_says_when_stages_have_the_price():
    """While Stages are drawn the candle and line rows colour nothing on the
    chart, and a swatch that changed nothing would read as broken."""
    pop = _fn(APP, "wsColorPop")
    assert "const staged = wsOverlayDrawn('stages');" in pop
    assert "Stages is on, so the candles and the line are\n      drawn in the colour of their stage." in APP


# ------------------------------------------------------ the shared Monday


JSC = ("/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/"
       "Helpers/jsc")


def _jsc():
    return JSC if os.path.exists(JSC) else shutil.which("jsc")


def test_the_browser_and_the_server_agree_on_every_days_monday():
    """Executed, not read. Four hundred consecutive days through the client's
    weekMonday against the server's rule in app/analytics/stage.py, across a
    year end and a leap day. One day of disagreement is one bar coloured with
    the wrong week's stage."""
    exe = _jsc()
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    start = dt.date(2023, 12, 1)
    days = [start + dt.timedelta(days=i) for i in range(400)]
    script = """
      load('tests/support/browser_stubs.js');
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
      var days = %s;
      print('MONDAYS:' + days.map(weekMonday).join(','));
      print('JUNK:' + weekMonday('not a date'));
    """ % repr([d.isoformat() for d in days]).replace("'", '"')
    out = subprocess.run([exe, "-e", script], capture_output=True, text=True,
                         timeout=120).stdout
    got = out.split("MONDAYS:")[1].split("\n")[0].split(",")
    want = [(d - dt.timedelta(days=d.weekday())).isoformat() for d in days]
    assert got == want
    assert "JUNK:null" in out
