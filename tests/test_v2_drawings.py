"""The classic chart's drawing tools in v2 (C10, 2026-10-19), and the Chart tab laid out as the classic one.

The seven tools v2 lacked (channel, Fibonacci extension, pitchfork, arrow, measure, risk / reward, position size),
snapping to a candle's open, high, low or close, moving a drawing (its body or one handle) and redo. The
geometry (ui/drawings.js) is the classic wsRenderDrawings' arithmetic; the stored form is the classic one in
optic.chart.drawings.v2, so a drawing made in either app reads the same in the other.

And the layout from the owner's screenshot of the classic chart: Indicators, Layers (a second row), Chart read,
Reset; bar size, session or range, Fit, Reset zoom and the style at the right; a two-column drawing rail with
snap, undo, redo and delete at its foot; the symbol and bar size heading the plot with Explain and full screen at
its corner; the last price tagged on the axis; volume in its own band. Placed, moved and undone with pointer
events in a browser at 1440 and 390.
"""
import json
import re

from tests.test_frontend_v2_stage0 import V2
from tests.test_v2_p3 import _run

ROOT = V2.parent.parent
JS = V2 / "js"
CLASSIC = (ROOT / "static/app.js").read_text()
CH = (JS / "pages/chart.js").read_text()
PC = (JS / "ui/pricechart.js").read_text()
DW = (JS / "ui/drawings.js").read_text()
CSS = (V2 / "css/pages.css").read_text()


def test_the_tools_and_their_points_are_the_classic_ones():
    i = CLASSIC.index("const WS_TOOLS = [")
    classic_ids = re.findall(r"\{ id: '([a-z]+)', group:", CLASSIC[i:CLASSIC.index("\n];", i)])
    v2_ids = re.findall(r"\['([a-z]+)', '[^']+'\]", CH[CH.index("const TOOLS = ["):CH.index("const TOOL_ICON")])
    assert len(classic_ids) == 15
    assert sorted("select" if c == "cursor" else c for c in classic_ids) == sorted(v2_ids), "the classic fifteen, select for its cursor"
    i = CLASSIC.index("const TOOL_POINTS = {")
    classic_points = dict(re.findall(r"(\w+): (\d)", CLASSIC[i:CLASSIC.index("};", i)]))
    v2_points = dict(re.findall(r"(\w+): (\d)", DW[DW.index("export const TOOL_POINTS = {"):DW.index("};", DW.index("export const TOOL_POINTS = {"))]))
    assert v2_points == classic_points
    assert "export const FIB_EXT = [0, 0.618, 1, 1.272, 1.618, 2, 2.618];" in DW and "[0, 0.618, 1, 1.272, 1.618, 2, 2.618].forEach" in CLASSIC
    assert "export const SNAP_PX = 7;" in DW and "const DRAW_SNAP_PX = 7;" in CLASSIC


def test_the_geometry(tmp_path):
    got = _run(tmp_path, f"""
      const D = await import('{(JS / "ui/drawings.js").as_posix()}');
      const a = {{ i: 10, p: 100 }}, b = {{ i: 20, p: 110 }}, c = {{ i: 15, p: 90 }};
      const bars = [0, 1, 2, 3, 4].map((k) => ({{ t: k * 1000, o: 10, h: 12, l: 8, c: 11 }}));
      const Y = (v) => 400 - v * 10;
      print(JSON.stringify({{
        ch: D.channel(a, b, c, 30), ext: D.fibExt(a, b, c), pf: D.pitchfork(a, b, c, 30),
        rr: D.riskReward({{ p: 100 }}, {{ p: 95 }}, {{ p: 112 }}), pos: D.positionSize({{ p: 100 }}, {{ p: 96 }}, {{ p: 105 }}),
        m: D.measure({{ i: 3, p: 50 }}, {{ i: 9, p: 55 }}),
        snapNear: D.snap(bars[2], 11.4, Y), snapFar: D.snap(bars[2], 9.0, Y),
        moved: D.moved([{{ t: 1000, p: 10 }}, {{ t: 3000, p: 12 }}], 2, 0.5, (await import('{(JS / "ui/timeaxis.js").as_posix()}')).makeAxis(bars, true)),
        seg: D.segDist(5, 5, 0, 0, 10, 0),
      }}));
    """)
    l1, l2 = got["ch"]
    assert l1 == {"i1": 10, "p1": 100, "i2": 30, "p2": 120} and l2 == {"i1": 10, "p1": 85, "i2": 30, "p2": 105}, "parallel, the copy through the third point"
    assert [x["price"] for x in got["ext"]] == [90, 96.18, 100, 102.72, 106.18, 110, 116.18], "from c by multiples of a to b"
    pf = got["pf"]
    assert pf["handle"] == {"i1": 10, "p1": 100, "i2": 17.5, "p2": 100} and [t["p2"] for t in pf["tines"]] == [100, 110, 90], "flat handle, so flat tines"
    assert got["rr"] == {"risk": 5, "reward": 12, "r": 2.4}
    assert got["pos"] == {"perShare": 4, "budget": 500, "shares": 125}, "$100 a dollar from the entry, as the classic tool reads it"
    assert got["m"]["bars"] == 6 and abs(got["m"]["pct"] - 10) < 1e-9
    assert got["snapNear"] == {"price": 11, "field": "C"} and got["snapFar"] == {"price": 9.0, "field": None}, "within 7 px of a field, else where the pointer is"
    # two bars on; past the series' end a point keeps its place by the bars' spacing (2026-10-20: it was held at the end)
    assert got["moved"] == [{"t": 3000, "p": 10.5}, {"t": 5000, "p": 12.5}]
    assert got["seg"] == 5


def test_snap_move_and_redo_in_the_chart():
    assert "const SNAP_KEY = 'optic.chart.snap.v1';" in CH and "d.snap = localStorage.getItem(SNAP_KEY) !== 'off'" in CH, "the classic key, on unless turned off"
    assert 'data-v2-ch-snap aria-pressed="${!!V.snap}" aria-label="Snap to candles"' in CH
    assert "const at = S.snap ? snap(bars[i], price, layout.ps.Y) : { price, field: null };" in PC
    assert "drag = { mode: 'handle', k: sel, h, before: S.drawings, moved: false };" in PC, "a handle moves one point"
    assert "moved(drag.pts, di, dp, AX)" in PC, "the body moves it all, through the time axis"
    assert "if ((drag.mode === 'handle' || drag.mode === 'body') && drag.moved) { undo.push(drag.before);" in PC, "a move is one change to undo"
    assert "function redoOne()" in PC and "data-v2-ch-redo" in CH and "k.toLowerCase() === 'y'" in PC
    for k in ("channel", "fibext", "pitchfork", "arrow", "ruler", "rr", "position"):
        assert f"dr.kind === '{k}'" in PC, k
        assert f"{k}: '" in CH[CH.index("const TOOL_HOW = {"):CH.index("const IND_KEYS")], f"{k} says what to click when it is picked"
    assert "drawn in full in the current app" not in PC, "every classic kind is drawn here now"


def test_the_classic_layout():
    tb = CH[CH.index("function toolbar() {"):CH.index("// The drawing tools: the classic rail")]
    # the wide toolbar's order (a phone puts Chart read, Reset and Fit in one menu, 2026-10-20)
    order = [tb.index(x) for x in ("menu('ind', 'Indicators'", "data-v2-ch-layers", 'data-v2-ch-read aria-pressed="${!!V.read}" aria-controls="ch-read" title=', "data-v2-ch-reset ${isClean() ? 'disabled' : ''} title=", 'class="spacer"', "data-v2-ch-iv", "data-v2-ch-sessionsel", 'data-v2-ch-fit title=', "data-v2-ch-home", "${isPhone() ? '' : html`<div class=\"seg seg-ic\" role=\"group\" aria-label=\"Style\">")]
    assert order == sorted(order), "Indicators, Layers, Chart read, Reset; then bar size, session, Fit, Reset zoom, style"
    assert "['ruler', 'Measure']" in CH and "Regular hours" in tb and "Extended hours" in tb
    assert "title=\"Back to price and volume. Your drawings are kept.\">Reset</button>" in tb
    assert 'id="ch-layers" role="group" aria-label="Layers"' in tb and "menu('panes', 'Panes'" in tb
    assert "onView: (v) => { D.zoomed = v.zoomed;" in CH and "home() { from = home0.from; to = home0.to; yZoom = 1; redraw(); }" in PC, "Reset zoom shows once zoomed (and puts a stretched price scale back)"
    assert "${miloButton('Explain'" in CH and "<div class=\"ch-pacts\"></div><div class=\"pc-host\"></div>" in CH, "Explain and full screen at the plot's corner"
    assert '<b class="pc-sym">' in PC, "the symbol and the bar size head the readout"
    assert "lastp-tag" in PC and "if (S.intraday && lb)" in PC, "the last price tagged, green or red with the day"
    assert "panes.push({ id: 'vol'," in PC and ">Volume</text>" in PC, "volume in its own band"
    assert ".ch-draw { display: grid; grid-template-columns: repeat(2, 36px);" in CSS, "two columns of tools"
    assert "syncToolbar();" in CH, "counts and Reset follow each tick without redrawing an open menu"


def test_the_stored_drawing_is_the_classic_one():
    assert "const DRAW_KEY = 'optic.chart.drawings.v2';" in CH
    assert "const dr = { id: 'd' + Date.now().toString(36) + Math.random().toString(36).slice(2, 5), kind: pending.kind, points: pending.points, color: 'accent', width: 1.6 };" in PC
    assert "pending.points.push({ t: at.t, p: at.p });" in PC, "points are a time and a price, as the classic app stores them"
