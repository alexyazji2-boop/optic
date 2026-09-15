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
    assert "const zoneRefs = (showFib ? (h.accumulation_zones || []) : [])" in fn


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
