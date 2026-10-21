"""Classic parity, batch B2b, part 1 (2026-10-21): the price chart's interactions (ui/pricechart.js) under
docs/frontend-v2/CHART-GESTURES.md. The wheel maths, the direction lock, the measurement's words and the page-key
rule run in JavaScriptCore; the rest are source checks. The interactions were driven in headless Chrome at 1440,
430, 390 and 360 (~/Optic/work/classic-parity/b2b_check.py, touch emulated) and in Mobile Safari on the iOS
simulator. These tests are not interaction evidence. Ledger: docs/frontend-v2/CLASSIC-PARITY.md, B2b.
"""
import math

from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"
PC = (JS / "ui/pricechart.js").read_text()
PAGE = (JS / "pages/chart.js").read_text()
CSS = (V2 / "css/pages.css").read_text()
COMP = (V2 / "css/components.css").read_text()


def test_the_wheel_zooms_by_distance_and_keeps_the_bar_under_the_pointer(tmp_path):
    got = _run(tmp_path, f"""
      const P = await import('{(JS / "ui/pricechart.js").as_posix()}');
      const ev = (o) => Object.assign({{ deltaX: 0, deltaY: 0, deltaMode: 0, ctrlKey: false, shiftKey: false }}, o);
      print(JSON.stringify({{
        notch: Math.exp(-100 * P.ZOOM_PER_PX), pinch: Math.exp(-10 * P.PINCH_PER_PX), lines: P.wheelPx(3, 1), pages: P.wheelPx(1, 2), px: P.wheelPx(7, 0),
        mid: P.zoomedAt(150, 0.5, 51, 1000), left: P.zoomedAt(10, 0.9, 101, 1000), right: P.zoomedAt(995, 0.2, 101, 1000), floor: P.zoomedAt(500, 0.5, 3, 1000), all: P.zoomedAt(500, 0.5, 5000, 1000),
        outAll: P.wheelRoom(ev({{ deltaY: 40 }}), 1000, 1000), inMin: P.wheelRoom(ev({{ deltaY: -40 }}), 10, 1000), out: P.wheelRoom(ev({{ deltaY: 40 }}), 300, 1000),
        side: P.wheelRoom(ev({{ deltaX: 30, deltaY: 4 }}), 1000, 1000), pin: P.wheelRoom(ev({{ deltaY: 5, ctrlKey: true }}), 1000, 1000), none: P.wheelRoom(ev({{}}), 300, 1000),
        lock: [P.touchLock(3, 4), P.touchLock(12, 3), P.touchLock(3, 12), P.touchLock(9, 9), P.touchLock(-20, 5)] }}));
    """)
    assert abs(got["notch"] - 1 / 1.15) < 1e-9, "a 100 px notch is the 1.15 it always was"
    assert abs(got["pinch"] - math.exp(-0.1)) < 1e-9
    assert got["lines"] == 99 and got["pages"] == 800 and got["px"] == 7
    m = got["mid"]
    assert m["to"] - m["from"] + 1 == 51 and m["from"] + 0.5 * 50 == 150, "the bar under the pointer stays under it"
    assert got["left"]["from"] == 0 and got["right"]["to"] == 999, "kept inside the history"
    assert got["floor"]["to"] - got["floor"]["from"] + 1 == 10, "never under ten bars"
    assert got["all"] == {"from": 0, "to": 999}
    assert got["outAll"] is False and got["inMin"] is False, "nowhere to go: the page's scroll"
    assert got["out"] is True and got["side"] is True and got["pin"] is True and got["none"] is False
    assert got["lock"] == [None, "x", "y", "y", "x"], "a tie is the page's"


def test_a_measurement_reads_closes_and_bars(tmp_path):
    got = _run(tmp_path, f"""
      const P = await import('{(JS / "ui/pricechart.js").as_posix()}');
      const bars = [{{ t: 1, c: 100 }}, {{ t: 2, c: 90 }}, {{ t: 3, c: 115 }}];
      const f = (t) => `day ${{t}}`;
      print(JSON.stringify({{ up: P.measuredBars(bars, 2, 0, f), down: P.measuredBars(bars, 0, 1, f), flat: P.measuredBars(bars, 1, 1, f) }}));
    """)
    assert got["up"] == {"i": 0, "j": 2, "head": "+15.00 (+15.00%)", "span": "day 1 to day 3", "bars": 2, "tone": "up"}
    assert got["down"]["head"] == "−10.00 (−10.00%)" and got["down"]["tone"] == "dn"
    assert got["flat"]["bars"] == 0 and got["flat"]["tone"] == ""


def test_page_keys_are_the_charts_only_when_nothing_else_handles_keys(tmp_path):
    got = _run(tmp_path, f"""
      const body = {{ tag: 'body' }}, html = {{ tag: 'html' }};
      globalThis.document = {{ body, documentElement: html }};
      const P = await import('{(JS / "ui/pricechart.js").as_posix()}');
      const el = (tag, opts = {{}}) => ({{ tag, isContentEditable: !!opts.edit, matches: (s) => s.split(',').map((x) => x.trim()).includes(tag), closest: (s) => (opts.inMenu ? {{}} : null) }});
      const scope = {{ contains: (a) => !a.outside }};
      const out = el('button'); out.outside = true;
      print(JSON.stringify({{ body: P.keyIsFree(body, scope), none: P.keyIsFree(null, scope), button: P.keyIsFree(el('button'), scope), link: P.keyIsFree(el('a[href]'), scope),
        input: P.keyIsFree(el('input'), scope), textarea: P.keyIsFree(el('textarea'), scope), edit: P.keyIsFree(el('button', {{ edit: true }}), scope),
        menu: P.keyIsFree(el('button', {{ inMenu: true }}), scope), outside: P.keyIsFree(out, scope), slider: P.keyIsFree(el('svg'), scope) }}));
    """)
    assert got == {"body": True, "none": True, "button": True, "link": True, "input": False, "textarea": False, "edit": False,
                   "menu": False, "outside": False, "slider": False}


def test_the_gesture_wiring_follows_the_precedence():
    # one wheel listener for the page, so a gesture has one owner; the old 1.15-per-event zoom is gone
    assert "svg.addEventListener('wheel'" not in PC and "zoom(e.deltaY > 0 ? 1.15 : 1 / 1.15" not in PC
    assert "document.addEventListener('wheel', onDocWheel, { capture: true, passive: false })" in PC
    assert "if (held && held.owner === 'page' && !e.ctrlKey) { held.at = now; return; }" in PC
    assert "else if (!c || (!held && !c.room(e))) { latch = { owner: 'page', at: now }; return; }" in PC
    # Safari's trackpad pinch, standing aside for a touch pinch
    assert "svg.addEventListener('gesturestart'" in PC and "if (tg || !layout) return;" in PC
    # a lost capture with the button held is not a release
    assert "if (pointers.has(e.pointerId) && e.pointerType === 'mouse' && e.buttons === 0) up(e);" in PC
    # the page holds still only once a gesture is the chart's; a vertical swipe before the lock still scrolls
    assert "const HELD = ['hold', 'pinch', 'measure', 'measure1', 'pan', 'scale', 'draw', 'place', 'cancelled'];" in PC
    assert "(tg.mode === 'scrub' && tg.locked)" in PC
    # nothing selectable while a finger is on a chart (iOS's long press), set and cleared by both charts
    assert "document.documentElement.classList.add('pc-touching')" in PC and "document.documentElement.classList.remove('pc-touching')" in PC
    assert "html.pc-touching, html.pc-touching * {" in COMP
    # the price scale's strip takes its own touch; zoom buttons only on touch screens, 44 px there
    assert ".pc-scale { position: absolute; z-index: 2; cursor: ns-resize; touch-action: none; }" in CSS
    assert ".pc-z { display: none; }" in CSS and "@media (hover: none), (pointer: coarse) { .pc-msb { opacity: 1; } .pc-z { display: grid; } .pc-cb { width: var(--tap); height: var(--tap); } }" in CSS
    assert '.pc-svg[data-drag="pan"] { cursor: grabbing; }' in CSS
    # Fit and Reset zoom put the price scale back; a rebuild keeps it
    assert "const fit = () => { from = 0; to = N - 1; yZoom = 1; redraw(); };" in PC
    assert "keep: () => ({ view: { from, to }, history: { undo, redo }, yZoom })," in PC


def test_the_chart_page_takes_page_keys_find_and_pane_removal():
    assert "pageKeys: mainEl," in PAGE, "undo, redo and Delete from the page, on the Chart tab"
    assert 'data-v2-ch-find placeholder="Find an indicator"' in PAGE and "export function findIndicators(q)" in PAGE
    assert "rsi: 'relative strength index momentum'" in PAGE, "found by what it is also called"
    assert "Nothing here is called ${q}." in PAGE
    assert "if (k !== 'volume' && k in V.panes) {" in PAGE, "a pane's own remove button takes it off"
    assert "x.checked = el.checked" in PAGE, "one box per overlay, wherever it is listed"
