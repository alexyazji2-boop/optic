"""Technical Levels on the Investing chart, and what parity does not mean here.

The two price charts were inconsistent: Options carried an Indicators menu and
a Technical Levels menu, Investing carried neither. Measured from the rendered
DOM, the Options toolbar had Interval, range pills, Line/Candles, Indicators and
"Technical Levels 3"; the Investing toolbar had Interval, range pills and
Line/Candles and stopped there.

**What this adds.** The Technical Levels menu, with the three toggles this chart
can actually honour: retracements, support and resistance, and volume. They read
the same global flags the Options menu writes, so switching one on there
switches it on here. That is the consistency being asked for, rather than a
second set of settings that happens to look the same.

**Computed on the WEEKLY frame, not the daily one.** A support shelf found in
252 daily bars is a one-year structure and this chart draws twelve years, so the
same lookback over weekly bars is about five years, which is the horizon on
screen. Same `support_resistance_levels` the swing path calls, and the client
draws it with the same `srBands` the Options chart and the charting workspace
both use, so the three cannot render one level three ways.

**What parity deliberately excludes.** The Indicators menu is not here: giving
it to this chart means an `interval` parameter on /api/indicators, which
hardcodes `interval="1d"` and would hand back daily series that do not align
with weekly or monthly bars, and it means parameterising a subsystem that
currently reads the module globals `indicatorIds` and `STATE.indicators` from
inside `renderSwing`. That edits the Options chart, so it is its own change.

The intervals and ranges stay different on purpose. Options runs Daily/Weekly
over 1D to All; this runs Weekly/Monthly over 1Y to All. Matching them exactly
would put a 1D range and VWAP on a twelve-year chart, and VWAP is a session
measure.

Verified in a browser: the menu renders as "Technical Levels 1" with three
toggles, switching support and resistance on adds 4 bands, which is
SR_BAND_LIMIT and the same number Options draws, switching retracements on adds
3 dashed lines, the badge counts up to 3, and the Options tab still renders its
19 charts and still responds to the same toggle.
"""

import re

APP_JS = open("static/app.js", encoding="utf-8").read()
LONGTERM_PY = open("app/analytics/longterm.py", encoding="utf-8").read()
CSS = open("static/styles.css", encoding="utf-8").read()


def strip_comments(js):
    js = re.sub(r"/\*.*?\*/", " ", js, flags=re.S)
    return re.sub(r"(?<!:)//[^\n]*", " ", js)


CODE = strip_comments(APP_JS)


def body_of(name, src=None):
    s = src if src is not None else CODE
    start = s.index("function %s(" % name)
    return s[start:].split("\nfunction ", 1)[0]


# ------------------------------------------------------------- the server

def test_the_long_payload_carries_the_levels():
    """The Investing view fetches only /api/longterm, which returned
    close_defence, holding and generated_at and nothing a level could be drawn
    from."""
    assert '"levels": {' in LONGTERM_PY
    for key in ('"support_resistance"', '"atr14"', '"spot"'):
        assert key in LONGTERM_PY, key


def test_the_levels_are_computed_on_the_weekly_frame():
    """A shelf found in 252 daily bars is a one-year structure and this chart
    draws twelve years. The same lookback over weekly bars is about five."""
    at = LONGTERM_PY.index('"levels": {')
    block = LONGTERM_PY[at:at + 500]
    assert "support_resistance_levels(\n                weekly," in block
    assert "lookback=252" in block


def test_the_atr_rides_along_because_the_bands_are_sized_from_it():
    """`srBands` makes each band a zone the width of the instrument's own
    noise. Without the ATR every shelf would be a hairline, which claims a
    precision a shelf does not have."""
    at = LONGTERM_PY.index('"levels": {')
    assert "atr(weekly, 14)" in LONGTERM_PY[at:at + 500]
    assert "from .technicals import atr, rsi, sma, support_resistance_levels" in LONGTERM_PY


def test_the_server_reuses_the_swing_path_functions():
    """Not a second implementation. Two support-resistance finders would
    disagree about where a level is and nothing would report it."""
    assert "support_resistance_levels" in LONGTERM_PY
    tech = open("app/analytics/technicals.py", encoding="utf-8").read()
    assert tech.count("def support_resistance_levels(") == 1


# ------------------------------------------------------------- the client

def test_the_investing_toolbar_has_the_levels_menu():
    fn = body_of("renderLong")
    assert 'aria-label="Technical Levels"' in fn
    for opt in ('data-level-opt="fib"', 'data-level-opt="sr"', 'data-level-opt="vol"'):
        assert opt in fn, opt


def test_it_only_offers_toggles_this_chart_can_honour():
    """A toggle for something a chart cannot show is worse than its absence.
    This chart draws no EMA families, dealer clouds, volume-by-price or insider
    markers, so none of those appear in its menu."""
    fn = body_of("renderLong")
    menu = fn[fn.index('aria-label="Technical Levels"'):]
    menu = menu[:menu.index("</details>")]
    for absent in ('"ma"', '"ema"', '"vbp"', '"insiders"', '"cloud921"', '"zones"'):
        assert "data-level-opt=%s" % absent not in menu, absent


def test_the_toggles_share_the_flags_rather_than_keeping_their_own():
    """Switching retracements on for Options switches them on here. A second
    set of state would look identical and drift on the first change."""
    fn = body_of("renderLong")
    assert "showFib ? 'checked' : ''" in fn
    assert "showSR ? 'checked' : ''" in fn
    assert "showVol ? 'checked' : ''" in fn


def test_the_retracements_answer_to_the_fib_flag():
    """They were drawn unconditionally. They are retracements of the three-year
    range, which is what Fibonacci means at this horizon, so they belong to the
    flag the Options chart already uses for its retracement grid."""
    fn = body_of("renderLong")
    assert "(showFib ? (h.accumulation_zones || []) : [])" in fn


def test_the_retracements_are_drawn_by_the_shared_fib_builder():
    """They were not, and the two charts had drifted apart about how this app
    draws a Fibonacci level.

    This view built its own refs: one flat colour, `pattern: '6 4'` so every
    line was dashed, a `38.2% · $273.20` label and no tooltip. fibLines — which
    the Options chart and the charting workspace both call — draws them solid,
    gives the golden pair the weight, dims the rest, labels them
    `38.2 (273.20)` and carries a detail table. The local version had reverted
    to exactly the dashed style fibLines' own comment records being told to
    stop using.
    """
    fn = body_of("renderLong")
    assert "const zoneRefs = fibLines(" in fn
    assert "pattern: '6 4'" not in fn, "dashed ratio lines are the old look"
    # Scoped to the refs expression. C.refSR legitimately appears in the legend
    # swatch below, which takes the golden colour on purpose.
    refs = fn[fn.index("const zoneRefs = fibLines("):]
    refs = refs[:refs.index(");") + 2]
    assert "color:" not in refs, "fibLines owns the colour, not the caller"


def test_the_retracement_legend_matches_what_is_drawn():
    """It was unconditional and described the old look: it named "Accumulation
    zones" with `dash: true` when the toggle was off and nothing was drawn, and
    kept claiming a dashed style after fibLines started drawing them solid. A
    legend naming a line the chart is not drawing sends the reader looking for
    it."""
    fn = body_of("renderLong")
    assert "...(showFib && zoneRefs.length" in fn
    assert "{ name: 'Retracements', color: C.refSR }" in fn
    assert "{ name: 'Accumulation zones', color: C.refSR, dash: true }" not in fn


def test_the_retracement_filter_reads_the_ratio_not_the_prose():
    """accumulation_zones holds the 40- and 200-week averages too, and those
    have real series lines of their own. The filter was `!/average/i` over the
    label — a regex on prose to answer "is this a retracement" when the server
    can just send the ratio."""
    fn = body_of("renderLong")
    assert "z.ratio !== null && z.ratio !== undefined" in fn
    assert "!/average/i.test" not in fn


def test_the_ratio_label_is_built_from_the_number():
    """fibLines derives its ratio text by stripping non-digits from the label,
    and "38.2% retracement of the 3-year range" yields "38.23" because of the 3
    in "3-year". The label handed in is the same "38.2%" form technicals.py
    sends, so both charts produce the identical string."""
    fn = body_of("renderLong")
    assert "`${fmt(z.ratio * 100, 1)}%`" in fn


# ------------------------------------------------- the averages on this chart


def test_the_weekly_averages_are_computed_before_the_window_is_applied():
    """Both lines started partway into the chart, and were reported as cut off.

    They were computed by the caller from the already-windowed closes, so each
    warmed up inside the view: on a 5Y weekly window (~260 bars) the 40-week
    average had no value for its first 39 bars and the 200-week none for its
    first 199 — so the green line began nine months in and the orange line did
    not appear until the last fifth of the plot. Measured after the fix on
    AAPL: 260 of 260 non-null for both, and all three polylines spanning
    x=8 to x=877.

    A 200-week average at a given week is a fact about the 200 weeks before it,
    and those weeks are in the payload — the server sends twelve years. They
    were just outside the window.
    """
    fn = body_of("ltSlice")
    assert "smaSeries(base.close || [], period)" in fn, \
        "the full series, not the sliced one"
    assert "ma[period] = full.some((v) => v !== null) ? cut(full) : null;" in fn, \
        "computed on the full series, then cut with everything else"
    caller = body_of("renderLong")
    assert "smaSeries(ltSer.close" not in caller, \
        "computing from the windowed closes is what cut both lines off"
    assert "const ltMa = (period) => (ltSer.ma || {})[period] || null;" in caller


def test_an_average_longer_than_the_history_is_dropped_not_drawn_empty():
    """200 months needs ~17 years and the payload holds twelve, so the monthly
    rollup has no 200-bar average. The legend follows the same test, so a line
    that is not drawn is not named."""
    fn = body_of("ltSlice")
    assert "full.some((v) => v !== null) ? cut(full) : null" in fn
    caller = body_of("renderLong")
    assert "...(ltMa200 ? [{ name: `200-${unit} average`" in caller


def test_the_periods_are_named_once():
    """40 and 200 in two places is how the legend comes to name a line the
    chart does not draw."""
    assert "const LT_MA_PERIODS = [40, 200];" in APP_JS


def test_support_and_resistance_uses_the_shared_band_builder():
    """Same `srBands` the Options chart and the charting workspace call."""
    fn = body_of("renderLong")
    assert "srBands(ltLevels.support_resistance || []" in fn
    assert "bands: showSR ?" in fn


def test_a_payload_without_levels_still_draws():
    """An older cached response has no `levels`, and the chart has to render
    without bands rather than throw."""
    fn = body_of("renderLong")
    assert "const ltLevels = h.levels || {};" in fn


def test_toggling_repaints_the_investing_view_as_well():
    """The handler repainted only Swing. Leaving it would have ticked the
    checkbox with nothing changing on the chart underneath, which reads as a
    broken feature rather than a missing one."""
    at = CODE.index("closest('[data-level-opt]')")
    branch = CODE[at:CODE.index("return;", at)]
    assert "if (STATE.swing) preserveUI(views.swing, () => renderSwing(STATE.swing));" in branch
    assert "if (STATE.long) preserveUI(views.long, () => renderLong(STATE.long));" in branch


def test_the_menu_badge_counts_what_is_on():
    fn = body_of("ltLevelCount")
    assert "[showFib, showSR, showVol].filter(Boolean).length" in fn


def test_every_swatch_class_in_the_new_menu_has_a_rule():
    """`lvl-key zone`, which the Options menu uses, has no rule in the
    stylesheet and renders as an unstyled box. The new menu uses `fib`, which
    matches its own toggle and is a real class."""
    fn = body_of("renderLong")
    menu = fn[fn.index('aria-label="Technical Levels"'):]
    menu = menu[:menu.index("</details>")]
    for cls in set(re.findall(r'class="lvl-key (\w+)"', menu)):
        assert ".lvl-key.%s" % cls in CSS, cls


# ------------------------------------------------- what parity does not mean

def test_the_horizons_stay_different():
    """Matching Options exactly would put a 1D range and daily bars over twelve
    years on this chart, and VWAP, which is a session measure."""
    assert "const LT_RANGES = [" in CODE
    lt = CODE[CODE.index("const LT_RANGES = ["):]
    lt = lt[:lt.index("\n];")]
    assert "'1d'" not in lt and "'5d'" not in lt
    assert "'10y'" in lt or "'5y'" in lt


def test_the_indicators_menu_is_not_claimed_here():
    """Its absence is deliberate and recorded: /api/indicators hardcodes
    interval="1d", so its series would not align with weekly or monthly bars."""
    fn = body_of("renderLong")
    assert "IND_FALLBACK_CATALOGUE" not in fn
    main = open("app/main.py", encoding="utf-8").read()
    assert 'interval="1d"' in main, (
        "if this endpoint gained an interval, the exclusion note is stale")


# ------------------------------------------------ what the server has to send


def test_the_retracement_zones_carry_their_ratio_and_the_golden_flag():
    """The chart draws these through the same fibLines() the Options chart uses,
    and it needs `is_golden` to decide the weight.

    Sent rather than parsed back out of the label: fibLines derives its ratio
    text by stripping non-digits, and "38.2% retracement of the 3-year range"
    yields "38.23" because of the 3 in "3-year".
    """
    import pandas as pd

    from app.analytics import longterm

    daily = pd.Series([100.0 + i * 0.1 for i in range(800)])
    zones = longterm._accumulation_zones(daily, {"sma_40w": 120.0, "sma_200w": 90.0})
    rets = [z for z in zones if z.get("ratio") is not None]
    assert len(rets) == 3, [z["label"] for z in zones]
    assert sorted(z["ratio"] for z in rets) == [0.382, 0.5, 0.618]
    golden = {z["ratio"]: z["is_golden"] for z in rets}
    assert golden == {0.382: False, 0.5: True, 0.618: True}


def test_the_average_zones_carry_no_ratio():
    """They are not retracements, and the chart filters on the ratio's presence
    to decide which zones become Fibonacci lines — the averages already have
    real series lines of their own."""
    import pandas as pd

    from app.analytics import longterm

    daily = pd.Series([100.0 + i * 0.1 for i in range(800)])
    zones = longterm._accumulation_zones(daily, {"sma_40w": 120.0, "sma_200w": 90.0})
    avgs = [z for z in zones if "average" in z["label"]]
    assert len(avgs) == 2
    for z in avgs:
        assert z.get("ratio") is None, z


def test_the_descriptive_label_is_left_alone():
    """The accumulation-zones table renders it, and defence.py reads it to name
    what a break would break."""
    import pandas as pd

    from app.analytics import longterm

    daily = pd.Series([100.0 + i * 0.1 for i in range(800)])
    zones = longterm._accumulation_zones(daily, {"sma_40w": 120.0, "sma_200w": 90.0})
    labels = [z["label"] for z in zones]
    assert "38.2% retracement of the 3-year range" in labels
