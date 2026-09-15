"""RSI and MACD as panes under the chart, and four panels off the Options tab.

The Options tab carried 22 panels and 10,563px; every other facet had between 0
and 9. It was the workspace's dumping ground, and two of the things in it were
duplicates of panels that already had a home.

**What left.** Corporate actions & flow rendered identically on Financials and
was 2,092px of the Options tab, on a panel whose own copy calls it "four
datasets that did not have a home". Close defence rendered on both Options and
Investing. Sector confirmation is the Market tab's "Sector relative strength"
asked with less behind it. Fundamental momentum opened with "Not part of the
composite score", which is a panel explaining why it is not about the tab it is
on. Measured after: 19 panels.

**What moved.** RSI and MACD were two 447px panels on the tab about strikes and
positioning, while the charting workspace, which is where a reader goes to look
at a chart, offered moving averages and nothing else. They are panes under the
price plot now, sharing its x-axis, the way a charting package does it.

The one thing that matters about the panes is WHERE they are computed. They are
attached to the series before it is windowed, so the averages warm up outside
the view: the Options panel had the opposite bug and its comment records the
signal line starting nine bars into the plot.

Verified in a browser at 1280x1400:

    panes 157px each, x-aligned to the chart at 872px, order plot -> RSI ->
    MACD -> navigator, legends "RSI 14 43.9 ... bearish cross" and
    "MACD 12, 26, 9 1.55 ... bearish cross"
"""

import re

APP_JS = open("static/app.js", encoding="utf-8").read()
CHARTS_JS = open("static/charts.js", encoding="utf-8").read()
CSS_RAW = open("static/styles.css", encoding="utf-8").read()
# Comments out before matching, exactly as for the JS. The first version of
# `test_the_canvas_does_not_size_its_rows_by_child_position` asserted
# `"grid-template-rows" not in block` and failed on the comment explaining why
# it is gone. A contract that reads raw source cannot tell an explanation from
# an implementation.
CSS = re.sub(r"/\*.*?\*/", " ", CSS_RAW, flags=re.S)


def strip_comments(js):
    js = re.sub(r"/\*.*?\*/", " ", js, flags=re.S)
    return re.sub(r"(?<!:)//[^\n]*", " ", js)


CODE = strip_comments(APP_JS)


def body_of(name, src=None):
    s = src if src is not None else CODE
    start = s.index("function %s(" % name)
    return s[start:].split("\nfunction ", 1)[0]


# ------------------------------------------------------------ what came off

def test_corporate_actions_is_on_financials_only():
    """The same panel on two tabs, and 2,092px of the one it did not belong to."""
    assert "id=\"fin-extras-host\"" in APP_JS, "it must still render somewhere"
    assert "id=\"extras-host\"" not in APP_JS
    # And the loader no longer refreshes a host that does not exist.
    fn = body_of("loadExtras")
    assert "STATE.view === 'swing'" not in fn


def test_close_defence_is_on_options_only():
    calls = re.findall(r"renderCloseDefence\(d\.close_defence", CODE)
    assert len(calls) == 1, calls
    assert "horizonWord: 'today'" in CODE, "Options keeps it"
    assert "horizonWord: 'this week'" not in CODE


def test_sector_confirmation_is_gone_and_left_nothing_behind():
    """Removing a panel means removing its renderer, its Pulse topic and the
    constant only it used. A dead render function is not neutral: the topic
    test passes on a control nothing can reach, which is how an orphan hides."""
    for dead in ("renderSectorConfirm", "sectorconfirm", "SC_VERDICT_CLASS"):
        assert dead not in APP_JS, dead


def test_the_server_still_computes_what_another_module_reads():
    """`sector_confirm` is consumed by app/analytics/compare.py, so the panel
    going does not make the payload dead."""
    main = open("app/main.py", encoding="utf-8").read()
    assert 'payload["sector_confirm"]' in main
    compare = open("app/analytics/compare.py", encoding="utf-8").read()
    assert 'payload.get("sector_confirm")' in compare


def test_fundamental_momentum_is_gone_but_its_data_is_not():
    """It still feeds the Earnings facet and the dock widget."""
    fn = body_of("renderSwing")
    assert "Fundamental momentum" not in fn
    assert "earnings_momentum" in APP_JS


# ------------------------------------------------------------- the panes

def test_the_panes_are_a_short_list_with_their_own_store():
    assert "const WS_PANES = [" in CODE
    assert "{ id: 'rsi'" in CODE and "{ id: 'macd'" in CODE
    assert "WS_PANES_KEY = 'optic.ws.panes'" in CODE


def test_an_unknown_pane_id_is_refused():
    """The list comes back from localStorage, which the reader can edit."""
    fn = body_of("wsTogglePane")
    assert "WS_PANES.some((p) => p.id === id)" in fn


def test_the_oscillators_are_attached_before_the_window_not_after():
    """The property the whole design turns on. An average computed from the
    visible closes warms up inside the view: the Options panel had exactly that
    and its signal line began nine bars in. Attaching to the full-length series
    means the window cuts an already-warm line."""
    fn = body_of("wsFullSeries")
    assert "wsWithOscillators(base, d, weekly)" in fn
    # Attached to the rolled-up series, and returned at full length: nothing in
    # here may slice.
    assert "slice(" not in fn


def test_the_windowing_path_carries_them_through():
    """`wsSeries` has two paths and only one of them used the prepared series.
    The other handed `sliceSeries` the raw payload, which threw the oscillator
    arrays away: the panes rendered their shells and drew nothing on every
    range except a manually zoomed one."""
    fn = body_of("wsSeries")
    assert "sliceSeries(raw, chartRange, chartInterval, full)" in fn


def test_slice_series_takes_a_prepared_series_without_aggregating_twice():
    """The caller cannot simply pass its series as `rawPs`, because weekly would
    then be rolled up here as well."""
    fn = body_of("sliceSeries")
    assert "prepared || (intervalKey === 'weekly' ? aggregateWeekly(rawPs) : rawPs)" in fn
    # Existing callers pass three arguments and must be unaffected: `prepared`
    # is undefined for them, so the aggregate-or-not branch runs as before.
    three_arg = re.findall(r"sliceSeries\(\s*[^;]*?\)", CODE)
    assert any("chartInterval)" in c and "full" not in c for c in three_arg), three_arg


def test_weekly_recomputes_rather_than_resampling():
    """A 14-week RSI is a slower measure than the 14-day one, not the same line
    at a different spacing. `aggregateWeekly` builds a fresh object, so the
    server's daily arrays are simply absent there and the recompute is forced
    rather than optional."""
    fn = body_of("wsWithOscillators")
    # Both branches, counted. Asserting the substring once passed against a
    # mutation that dropped `!weekly` from the RSI branch only: MACD still
    # carried it, so the string was still there and the test saw nothing.
    assert fn.count("!weekly &&") == 2, fn.count("!weekly &&")
    assert "rsiSeries(closes, 14)" in fn
    assert "macdSeries(closes)" in fn


def test_the_server_series_is_only_used_when_it_matches_the_bars():
    """Length is the check, not the interval alone. A server array of a
    different length than `close` would stretch the pane's x-axis past the
    chart's, which is the bug `sliceSeries`'s own comment describes."""
    fn = body_of("wsWithOscillators")
    # Counted for the same reason as the weekly check above.
    assert fn.count(".length === closes.length") == 2, (
        fn.count(".length === closes.length"))


def test_nothing_is_computed_when_no_pane_is_open():
    """A reader who never opens one pays nothing."""
    fn = body_of("wsWithOscillators")
    assert "if (!wsPanesOpen.length) return base;" in fn


def test_the_panes_draw_from_the_series_the_chart_drew():
    """Passed in rather than re-derived. Two calls to `wsSeries` either side of
    a window change would not agree, and a pane a bar out of step with the
    candles above it is worse than no pane."""
    assert "wsMountPanes(ps);" in CODE
    fn = body_of("wsMountPanes")
    assert "wsSeries(" not in fn, "the pane re-derived its own series"
    assert "ps.dates" in fn


def test_the_rsi_pane_keeps_its_fixed_scale():
    """Bounded 0-100, so auto-scaling puts the overbought band on the top edge
    and the oversold band in dead space."""
    fn = body_of("wsMountPanes")
    assert "yDomain: [10, 90]" in fn
    assert "value: 70" in fn and "value: 30" in fn


def test_the_pane_charts_are_passed_only_options_they_read():
    """`lineChart` reads neither `compact` nor `unit`. Passing a chart options
    it ignores is how a caller comes to believe it configured something."""
    fn = body_of("wsMountPanes")
    # Scoped to the lineChart call. `unit` is asserted absent only there:
    # macdChart genuinely reads `opts.unit`, and a blanket check on the whole
    # function failed against the legitimate one.
    line_call = fn[fn.index("lineChart({"):fn.index("}));", fn.index("lineChart({"))]
    assert "compact:" not in line_call
    assert "unit" not in line_call
    # macdChart does read a height, because one was added for this caller.
    assert "height: 132" in fn
    assert "opts.height || 210" in CHARTS_JS


def test_the_pane_legend_is_written_not_mounted():
    """`mount` with a function means "chart builder": it calls it with a width
    and appendChild's the result, so one returning a string fails silently.
    That is what left the panes drawing correctly under an empty legend."""
    fn = body_of("wsPaneLegend")
    assert "innerHTML = html" in fn
    mount_fn = body_of("wsMountPanes")
    assert "mount('ws-pane-legend" not in mount_fn


def test_the_pane_toggle_and_its_close_button_use_different_events():
    """A checkbox fires change; a button fires click. Two shapes, two events,
    two names."""
    assert "data-ws-pane-opt" in APP_JS and "data-ws-pane-close" in APP_JS
    assert "closest('[data-ws-pane-opt]')" in CODE
    assert "closest('[data-ws-pane-close]')" in CODE


def test_toggling_a_pane_repaints_rather_than_redrawing_the_chart():
    """Adding a pane adds markup, and changes the series: the oscillators are
    attached only for panes that are open."""
    assert CODE.count("wsRepaintWithPanes()") >= 2
    fn = body_of("wsRepaintWithPanes")
    assert "renderChartWorkspace(STATE.chartData)" in fn
    assert "wsMountChart()" in fn


def test_the_pane_attribute_does_not_reuse_the_overlay_one():
    """`data-ws-opt` draws a line ON the price plot and is shared with the Swing
    chart. A pane is a plot of its own and belongs to this tab. A `data-*`
    collision does not error, it lets the wrong handler match first."""
    # The checkboxes are in the toolbar's Panes menu, not in the pane shells,
    # which is where the first version of this looked and why a mutation
    # swapping the attribute sailed past it.
    tb = body_of("wsToolbar")
    menu = tb[tb.index('data-ws-menu="panes"'):]
    menu = menu[:menu.index("ws-menu-note")]
    assert "data-ws-pane-opt" in menu
    assert "data-ws-opt" not in menu
    assert "data-ws-opt" not in body_of("wsPanesHTML")


# ------------------------------------------------------------- the layout

def test_the_canvas_does_not_size_its_rows_by_child_position():
    """It was a grid with `auto auto 1fr`, which means "the third child
    flexes". The legend renders empty on some configurations, so every child
    shifted up one slot and the RSI pane inherited the 1fr row with no free
    space in it: measured `51px 680px 1px 157px 46px` against six children, the
    pane collapsed to 1px while the identical MACD pane below it was fine."""
    block = CSS[CSS.index(".ws-canvas {"):CSS.index(".ws-head {")]
    assert "display: flex" in block
    assert "flex-direction: column" in block
    assert "grid-template-rows" not in block
    assert ".ws-plot { flex: 1 1 auto; }" in CSS
    assert ".ws-canvas > * { flex: 0 0 auto; }" in CSS


def test_the_panes_sit_between_the_plot_and_the_navigator():
    """Inside .ws-canvas so they share the chart's column and line up with it,
    and above the navigator because the navigator is about the window rather
    than about the bars."""
    body = CODE[CODE.index('<div class="ws-body">'):]
    body = body[:body.index('ws-dock')]
    assert body.index("ws-plot") < body.index("wsPanesHTML()") < body.index('id="ws-nav"')


def test_every_pane_class_has_a_rule():
    fn = body_of("wsPanesHTML")
    for cls in set(re.findall(r'class="(ws-pane[a-z-]*)"', fn)):
        assert ".%s" % cls in CSS, cls


# ------------------------------------------- the measure tool, and the animation

def test_the_measure_tool_spans_the_price_pane_rather_than_the_price_gap():
    """It drew a dashed diagonal between the two points and a rect bounded by
    both axes at 0.07 opacity. That measures the same numbers and shows them as
    a thin sloped ribbon: the span was hard to see, and the part that read as a
    shape was the price gap rather than the period.

    A range selection is a vertical boundary at each end, the interval between
    them filled, and a dot on the series at each end.
    """
    src = CODE[CODE.index("dr.kind === 'ruler'"):]
    src = src[:src.index("dr.kind === 'rr'")]
    assert "stroke-dasharray" not in src, "the diagonal is back"
    assert "frame.margin.t + frame.priceH" in src
    # Asserted as the loop that produces them, not as the presence of a circle.
    # Counting `el('circle'` passed against `[].forEach(...)`, which leaves the
    # text in place and creates nothing: the dots are drawn per point, so the
    # thing to pin is that they come from `pts`.
    assert "pts.forEach((pt) => {" in src
    dots = src[src.index("pts.forEach((pt) => {"):]
    assert "el('circle'" in dots[:200], dots[:200]
    assert "'fill-opacity': 0.12" in src


def test_the_measure_band_uses_the_frame_field_that_exists():
    """The frame carries {width, height, margin, plotW, priceH, lo, hi, bars,
    labels, xOf, yOf, indexAt, priceAt}. There is no plotH on it: the first
    version used one, so the band height and both boundary y2 attributes came
    out NaN and nothing between the edges drew at all.

    `priceH` rather than `height`, because height includes the volume strip.
    """
    src = CODE[CODE.index("dr.kind === 'ruler'"):]
    src = src[:src.index("dr.kind === 'rr'")]
    assert "frame.plotH" not in src
    assert "frame.priceH" in src


def test_the_measure_readout_is_direction_coloured_and_two_lines():
    src = CODE[CODE.index("dr.kind === 'ruler'"):]
    src = src[:src.index("dr.kind === 'rr'")]
    assert "var(--pos)" in src and "var(--neg)" in src
    # Dates above, the move below and larger.
    assert "'font-size': 10" in src and "'font-size': 14" in src


def test_the_charting_view_switches_the_draw_on_animation_on():
    """Every other loader calls setChartAnimation before it renders; this branch
    went straight to the workspace, so the flag was whatever the last thing to
    touch it left behind, and `preserveUI` sets it false on any control press.
    Measured: 0 elements carrying `data-draw` in the workspace against 4 charts
    animating on the Options tab from the same payload. After: 4 draw elements
    and 14 running animations."""
    at = CODE.index("if (view === 'chart')")
    branch = CODE[at:at + 400]
    assert "setChartAnimation(" in branch
    assert "hasPendingDraws()" in branch, (
        "a chart still waiting to be scrolled to must keep its wait")
    assert branch.index("setChartAnimation(") < branch.index("loadChartWorkspace(")
