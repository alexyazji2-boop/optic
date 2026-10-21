"""Classic parity, batch B2a (2026-10-21): measuring on the shared line chart (ui/chart.js), under the precedence
written first in docs/frontend-v2/CHART-GESTURES.md. The wording of a measurement and the chart's markup run in
JavaScriptCore; the rest are source checks. The interactions (plain drag, Shift-drag, the Measure button, the
wheel, the keys, tap, swipe, hold and two fingers) were driven in headless Chrome at 1440, 430, 390 and 360
(~/Optic/work/classic-parity/b2a_check.py, touch emulated) and in Mobile Safari on the iOS simulator. These tests
are not interaction evidence. Ledger: docs/frontend-v2/CLASSIC-PARITY.md, B2a.
"""
from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"
CHART = (JS / "ui/chart.js").read_text()
CSS = (V2 / "css/components.css").read_text()


def test_a_measurement_reads_the_change_and_a_percent_only_for_levels(tmp_path):
    got = _run(tmp_path, f"""
      const C = await import('{(JS / "ui/chart.js").as_posix()}');
      const px = [{{ d: '2026-01-06', c: 262.36 }}, {{ d: '2026-03-02', c: 250 }}, {{ d: '2026-06-08', c: 301.54 }}];
      const dd = [{{ d: '2026-01-06', c: -4.2 }}, {{ d: '2026-03-02', c: -18.5 }}, {{ d: '2026-06-08', c: -2.1 }}];
      print(JSON.stringify({{
        up: C.measured(px, 0, 2, {{ mode: 'change', levels: true, dp: 2 }}),
        back: C.measured(px, 2, 0, {{ mode: 'change', levels: true, dp: 2 }}),
        down: C.measured(px, 0, 1, {{ mode: 'change', levels: true, dp: 2 }}),
        pts: C.measured(dd, 1, 2, {{ mode: 'points', levels: false, dp: 1, unit: ' pts' }}),
        neg: C.measured(dd, 1, 2, {{ mode: 'change', levels: false, dp: 1 }}) }}));
    """)
    assert got["up"]["head"] == "+39.18 (+14.93%)" and got["up"]["span"] == "Jan 6, 2026 to Jun 8, 2026"
    assert got["back"] == got["up"], "a drag to the left reads the same, earlier date first"
    assert got["down"]["head"] == "−12.36 (−4.71%)", "a fall is signed with a true minus"
    assert got["pts"]["head"] == "+16.4 pts", "a series in points or percent gets the change in points, never a percent of it"
    assert "%" not in got["neg"]["head"], "a series that crosses zero gets no percent change"


def test_the_chart_offers_measuring_with_a_button_and_a_spoken_result(tmp_path):
    got = _run(tmp_path, f"""
      const C = await import('{(JS / "ui/chart.js").as_posix()}');
      const s = Array.from({{ length: 60 }}, (_, i) => ({{ d: `2026-0${{1 + Math.floor(i / 28)}}-${{String(1 + (i % 28)).padStart(2, '0')}}`, c: 100 + i }}));
      print(JSON.stringify({{ on: C.lineChart(s, {{ w: 600, h: 200 }}).html, off: C.lineChart(s, {{ w: 600, h: 200, measure: false }}).html }}));
    """)
    on, off = got["on"], got["off"]
    assert 'class="chart-wrap can-measure"' in on and 'data-chart-measure aria-pressed="false"' in on
    assert 'aria-label="Measure between two dates"' in on and 'aria-live="polite" data-ms-say' in on
    assert "<svg" in on.split("data-chart-measure", 1)[1].split("</button>", 1)[0] and "[object Object]" not in on, "the ruler icon, drawn"
    assert "can-measure" not in off and "data-chart-measure" not in off, "measure: false leaves a chart as it was"


def test_the_gesture_precedence_holds_in_the_source():
    # a vertical swipe scrolls the page; only Measure on takes every touch
    assert ".chart-wrap.can-measure svg.chart { touch-action: pan-y; }" in CSS
    on = CSS.index(".chart-wrap.is-measuring svg.chart { touch-action: none;")
    assert on > CSS.index(".chart-wrap.can-measure svg.chart { touch-action: pan-y; }"), "same weight, later, so it wins"
    assert ".chart .ms { pointer-events: none; }" in CSS and ".chart .ev-rule { pointer-events: none; }" in CSS
    # a plain mouse drag never measures: Shift or the Measure button
    assert "if (e.button !== 0 || !(e.shiftKey || mOn))" in CHART
    # iOS Safari's long press is the system's: hold-to-measure is skipped there, before the timer starts
    hold = CHART.index("hold = setTimeout(")
    assert CHART.index("if (IOS_TOUCH) return;") < hold
    assert "typeof window.GestureEvent !== 'undefined' && (navigator.maxTouchPoints || 0) > 0" in CHART
    # the page's scroll taking a touch clears the reading it started
    assert "if (e.pointerType === 'touch' && !was) hide();" in CHART
    # keys: M, the arrows and Escape, never Tab, and never while a field has focus (the chart is the focused element)
    assert "e.key === 'Tab'" not in CHART
    doc = (V2.parent.parent / "docs/frontend-v2/CHART-GESTURES.md").read_text()
    assert "except in iOS and iPadOS Safari" in doc and "Taking Tab" in doc


def test_series_in_points_measure_in_points():
    pages = {
        "pages/investing.js": "measure: 'points', msUnit: ' pts'",
        "pages/financials.js": "measure: 'points', msUnit: ' pts'",
        "pages/brokerage.js": "measure: 'points', msUnit: ' pts'",
        "pages/options-panels.js": "measure: 'points', msUnit: ' pts', w, h: 200, label: 'RSI (14)'",
        "pages/macro.js": "measure: D.econ.unit === '%' ? 'points' : 'change', msUnit: D.econ.unit === '%' ? ' pts' : ''",
    }
    for page, needle in pages.items():
        src = (JS / page).read_text()
        assert needle in src, f"{page} measures its series in the right unit"
        assert "unit: ' pts'" not in src.replace("msUnit: ' pts'", ""), f"{page}: ' pts' is the measurement's unit, never the axis's"
    assert "unit: opts.msUnit == null ? opts.unit : opts.msUnit" in CHART


def test_the_readout_stays_on_screen_and_a_mouse_press_draws_no_ring():
    # every tip is placed by one helper that measures its real width and stacks it when the chart is narrower
    assert CHART.count("place(") >= 4 and "tip.classList.add('is-narrow')" in CHART
    assert "box.width - 220" not in CHART and "tw / 2)) + 'px'" in CHART, "no fixed tip width guessed any more"
    assert ".chart-tip.is-narrow { white-space: normal; width: max-content; max-width: 100%; }" in CSS
    assert ".chart:focus:not(:focus-visible) { outline: none; }" in CSS, "Chrome rings a clicked svg; the gold ring stays for keys"
    assert ".chart:focus-visible { outline: 2px solid var(--c-focus);" in CSS
