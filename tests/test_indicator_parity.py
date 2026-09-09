"""Do the Charting tab and the Swing chart show the same indicators?

They did not, in four ways, and all four were visible on screen:

  * the five price-pane studies (Bollinger, Keltner, Donchian, the regression
    channel, anchored VWAP) drew on the Swing chart and were absent from the
    Charting tab entirely, on the tab whose whole job is charting;
  * the same SMA 20 was s2 on one tab and s1 on the other in candle mode, and a
    colour chosen in the indicator dialog was honoured on one and silently
    dropped on the other, which that code's own comment said should not happen;
  * the study palette was seeded from different sets on the two tabs, so the
    allocator handed the same study two different colours;
  * the labels disagreed, and one of them lied: the Swing tab hardcoded
    `200-day SMA` on a weekly chart while making its 20 and 50 unit aware.

Read as text, like the other client contracts here. The behaviour was verified
in a browser against live data; what these lock down is the wiring, which is
where every silent client failure in this codebase has been.
"""

from __future__ import annotations

import re

APP_JS = open("static/app.js").read()


def _fn(name: str) -> str:
    start = APP_JS.index("function %s(" % name)
    nxt = APP_JS.find("\nfunction ", start + 1)
    return APP_JS[start:nxt if nxt > 0 else len(APP_JS)]


# ------------------------------------------------------- the studies exist here


def test_the_charting_tab_draws_the_price_pane_studies():
    """The gap that prompted this. `indicatorOverlaySeries` was called by the
    Swing chart and by nothing else."""
    assert "wsIndicatorSeries((ps.dates || []).length, ps)" in APP_JS
    assert "function wsIndicatorSeries(" in APP_JS


def test_the_charting_tab_has_a_control_for_them():
    """A study that draws but cannot be switched on from this tab would be no
    better than one that cannot draw."""
    assert "function wsStudiesMenu(" in APP_JS
    assert 'data-ws-menu="studies"' in APP_JS
    assert "closest('[data-ws-study]')" in APP_JS
    assert "${wsStudiesMenu()}" in APP_JS       # actually rendered in the toolbar


def test_the_menu_says_where_the_other_five_live():
    """ADX, Stochastic, on-balance volume, money flow and relative strength are
    not on a price scale and this tab has no pane host under the plot. Naming
    where they are beats offering a checkbox that cannot work."""
    fn = _fn("wsStudiesMenu")
    assert "IND_PRICE_PANE.includes" in fn
    for name in ("ADX", "Stochastic", "on-balance volume", "money flow",
                 "relative strength"):
        assert name in fn, name
    assert "Analysis tab" in fn


def test_a_study_ticked_on_either_tab_reaches_the_other():
    """One selection, two caches. Ticking a box has to invalidate both or the
    checkbox appears to half-work."""
    assert APP_JS.count("IND_STATE_KEY, JSON.stringify(indicatorIds)") >= 3
    studies = APP_JS[APP_JS.index("closest('[data-ws-study]')"):]
    studies = studies[:studies.index("closest('[data-ind]')")]
    assert "wsLoadIndicators()" in studies
    assert "loadIndicators(true)" in studies
    # and the other direction
    analysis = APP_JS[APP_JS.index("closest('[data-ind]')"):]
    analysis = analysis[:analysis.index("return;") + 7]
    assert "wsLoadIndicators()" in analysis


# --------------------------------------------------------- the symbol boundary


def test_the_charting_tab_never_draws_the_other_tabs_symbol():
    """`STATE.indicators` is keyed on STATE.ticker; this tab holds
    STATE.chartSymbol. Using the former here would put one company's Bollinger
    bands over another company's candles and label them correctly, which
    CLAUDE.md names as the worst kind of failure."""
    for fn in ("wsIndicatorSeries", "wsStudyRows"):
        body = _fn(fn)
        assert "STATE.indicators" not in body, fn
        assert "payload.symbol !== STATE.chartSymbol" in body, fn
    loader = _fn("wsLoadIndicators")
    assert "STATE.chartSymbol" in loader
    assert "STATE.ticker" not in loader


def test_the_loader_drops_a_reply_that_arrived_late():
    """Same guard loadIndicators carries: ticking four boxes quickly starts four
    requests that do not return in order, and the slowest would win."""
    loader = _fn("wsLoadIndicators")
    assert "if (STATE.chartSymbol !== symbol" in loader
    assert "!== key) return;" in loader


def test_unticking_the_last_study_clears_the_cache():
    """Otherwise the final study's lines stay on the chart with its box empty."""
    loader = _fn("wsLoadIndicators")
    assert "if (!ids.length)" in loader
    assert "wsIndicators = null" in loader


# ------------------------------------------------------------ colour agreement


def test_one_resolver_answers_for_both_tabs():
    """The Swing tab used to substitute a hardcoded s1/s2/s4 in candle mode."""
    assert APP_JS.count("maColorsOnChart(") >= 4
    assert "{ fast: C.s1, mid: C.s2, slow: C.s4 }" not in APP_JS
    assert "const maColors = { fast: maOn.sma20, mid: maOn.sma50, slow: maOn.sma200 };" in APP_JS
    assert "const wsMaColors = maColorsOnChart(wsCandles(ps));" in APP_JS


def test_a_chosen_colour_is_never_moved():
    """The trade the old comment described and the old code did not implement."""
    fn = _fn("maColorsOnChart")
    assert "overlayColorChosen(id)" in fn
    # Chosen colours are settled in the first pass, before anything is placed.
    chosen_at = fn.index("overlayColorChosen(id)")
    displaced_at = fn.index("const displaced")
    assert chosen_at < displaced_at


def test_only_a_genuine_collision_moves_a_default():
    """Three versions of this were wrong. The first added every resolved colour
    to the taken pile, so one choice recoloured two other averages. The second
    compared defaults only against the mark, leaving a chosen s7 and a default
    s7 drawn alike. The third let a displaced average squat on a colour a later
    average was keeping."""
    fn = _fn("maColorsOnChart")
    assert "const keepers" in fn
    assert "keepers.map((id) => lc(out[id]))" in fn, \
        "displaced averages must avoid the keepers' colours, not just the marks"


def test_the_mark_colours_are_read_not_hardcoded():
    """The candle pair is configurable now."""
    fn = _fn("maColorsOnChart")
    assert "chartColor('up')" in fn and "chartColor('down')" in fn
    assert "C.s3" not in fn and "C.s8" not in fn


def test_both_tabs_seed_the_study_allocator_identically():
    """allocateOverlayColors takes the first colour not already taken, so two
    tabs seeding it differently give the same study two different colours."""
    assert "function chartBaseColors(" in APP_JS
    assert "chartBaseColors(ps, wsCandles(ps), isIntradayRange(chartRange))" in APP_JS
    assert "chartBaseColors(ps, candleMode, ps.intraday)" in APP_JS


def test_the_seed_counts_what_is_drawn_not_the_family_flag():
    """`showEMA` is the family checkbox while the series list filters per
    average. With EMA 9 on and the family flag off, the allocator never learned
    s5 was taken and handed it to Bollinger."""
    fn = _fn("chartBaseColors")
    assert "MA_SERIES_IDS.filter(seriesDrawn)" in fn
    assert "showEMA" not in fn


def test_the_legend_names_the_colour_that_is_drawn():
    """`overlayStyle(id).color` is what is stored; the resolver is what is
    drawn. The legend showed the stored one, so a displaced EMA was keyed in a
    colour that was not on the chart."""
    fn = _fn("wsLegend")
    assert "const legMa = maColorsOnChart(wsCandles(ps));" in fn
    assert "colorOf = (id)" in fn
    assert 'style="color:${colorOf(id)}"' in fn


# -------------------------------------------------------------------- labelling


def _code_only(src: str) -> str:
    """app.js minus its comments.

    The first version of the assertion below matched `'20-week SMA'` inside a
    comment on the Long-term tab that describes this very convention, so it
    failed on prose rather than on code."""
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", "", src)


def test_an_average_is_labelled_in_the_units_on_screen():
    fn = _fn("maLabel")
    assert "ps.weekly" in fn
    assert "'week'" in fn and "'day'" in fn
    # And monthly, which no tab reaches today but which would reintroduce the
    # exact bug this function fixes the day a Monthly pill is added.
    assert "'month'" in fn
    # No hardcoded unit strings left in the code, on either tab.
    code = _code_only(APP_JS)
    assert "'200-day SMA'" not in code
    assert "'20-week SMA'" not in code
    assert "'50-week SMA'" not in code


def test_the_label_reads_the_overlay_s_own_length():
    """The manage dialog promises "The label will say 30 and the line will
    still be 20 until the recompute lands." A literal would break that."""
    fn = _fn("maLabel")
    assert "overlayStyle(id).params" in fn
    assert "params.length" in fn


def test_both_tabs_label_all_six_averages_the_same_way():
    """The Swing tab named its EMAs `EMA 9` and its SMAs `20-day SMA`."""
    for id_ in ("sma20", "sma50", "sma200", "ema9", "ema21", "ema50"):
        assert APP_JS.count("maLabel('%s', ps)" % id_) >= 2, id_
    assert "'EMA 9', emaColors" not in APP_JS


def test_the_charting_legend_does_not_print_the_length_twice():
    """`SMA 20 (20, 0, close)` read as two different numbers."""
    fn = _fn("wsLegend")
    assert "const maDetail = (id) => `${p(id).offset}, ${p(id).source}`;" in fn
    assert "${p('sma20').length}" not in fn


def test_the_swing_candle_keys_use_the_reader_s_colours():
    """The legend hardcoded s3/s8 and stopped being true the moment anyone used
    the Charting tab's colour picker."""
    assert "name: ps.weekly ? 'Up week' : 'Up day', color: chartColor('up')" in APP_JS
    assert "name: ps.weekly ? 'Down week' : 'Down day', color: chartColor('down')" in APP_JS


# ------------------------------------------------------------------- hygiene


def test_the_studies_are_excluded_on_intraday():
    """Same reason the averages are: computed from daily bars, so they would
    describe a different timeframe from the one on screen."""
    assert "intraday ? [] : wsIndicatorSeries(" in APP_JS
    assert "if (!isIntradayRange(chartRange)) {" in _fn("wsLegend")


def test_every_class_the_studies_menu_renders_has_a_rule():
    """Both of these shipped as markup with no rule for one revision: the note
    rendered at body size and was the tallest thing in the popover. A dead class
    does not error, it just looks unfinished."""
    css = open("static/styles.css").read()
    # Every class *token*, not whole attribute values: this renders as
    # `class="ws-menu-pop ws-studies"`, where the name is the second token, and
    # an anchored pattern found neither of them.
    used = {tok for attr in re.findall(r'class="([^"]*)"', APP_JS)
            for tok in attr.split() if tok.startswith("ws-studies")}
    assert {"ws-studies", "ws-studies-note"} <= used, used
    for cls in used:
        assert ".%s" % cls in css, cls


def test_no_em_dashes_in_the_studies_menu_copy():
    for text in re.findall(r">([^<>{}]{16,})<", _fn("wsStudiesMenu")):
        assert "—" not in text, text
