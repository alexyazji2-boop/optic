"""Accumulation zones on the Charting tab.

They were on the Investing tab and nowhere else. That tab draws them as
labelled horizontal lines built by `fibLines` -- the multi-year structure:
the 40- and 200-week averages, and the retracements of the three-year range.
The Charting tab, whose whole job is charting, could not show them at all.

What is checked here is the wiring, for the reason test_ema_clouds.py gives:
there is no JS test runner, and every overlay failure in this codebase has
been a control that looks right and does nothing.

Verified in a browser at 1440x950 before this was written. On AMD: five zones
fetched, five reference lines built, the chart went from 31 lines to 35 and
from 29 text nodes to 33, and both weekly averages drew with their labels.
Clicking the checkbox three times gave 2 labels -> 0 -> 2 -> 0. Switching to
MSFT refetched (five zones at 454/430/427/401/400). The 1d pill drew none and
1y brought them back.
"""

from __future__ import annotations

import re

import pandas as pd

from app.analytics.longterm import _accumulation_zones

APP = open("static/app.js", encoding="utf-8").read()


def _block(marker, end="\n};"):
    start = APP.index(marker)
    return APP[start:APP.index(end, start)]


def _fn(name):
    start = APP.index("function %s(" % name)
    return APP[start:APP.index("\n}", start)]


# --------------------------------------------------------------- the wiring


def test_the_overlay_is_defined_with_a_label():
    """`overlayStyle` falls back to the id when there is no definition, so a
    missing entry does not throw -- it puts `accum` in the menu as its own
    label and offers a colour picker over a default that does not exist."""
    defs = _block("const OVERLAY_DEFS = [", "\n];")
    entry = [ln for ln in defs.splitlines() if "id: 'accum'" in ln]
    assert entry, "accum has no OVERLAY_DEFS entry"
    assert "label: 'Accumulation zones'" in entry[0]


def test_it_is_reachable_from_the_trends_menu():
    """An overlay defined but not listed in WS_MENUS cannot be switched on."""
    menus = _block("const WS_MENUS = [", "\n];")
    trends = [ln for ln in menus.splitlines() if "id: 'trends'" in ln]
    assert trends, "the Trends menu is gone"
    assert "'accum'" in trends[0]


def test_it_has_a_flag_and_a_setter():
    """wsOverlayOn reads WS_FLAGS and wsSetOverlay writes through WS_SETTERS.
    Missing either half renders unchecked forever or never redraws."""
    assert "accum:" in _block("const WS_FLAGS = {")
    assert "accum:" in _block("const WS_SETTERS = {")


def test_the_choice_is_remembered_like_every_other_level_family():
    assert "const SHOW_ACCUM_KEY = 'optic.chart.accum.v1';" in APP
    assert "showAccum = localStorage.getItem(SHOW_ACCUM_KEY) === 'on';" in APP
    assert "storeFlag(SHOW_ACCUM_KEY, on)" in APP


# ------------------------------------------------------- fetched on demand


def test_switching_it_on_fetches_the_payload():
    """The chart payload is `/api/ticker`; these come from `/api/longterm`,
    which the Charting tab does not otherwise call. Without this the checkbox
    ticks, the chart redraws with an empty STATE.accumZones, and nothing
    appears -- and nothing ever would, because the redraw is the only trigger
    and it has already happened."""
    setters = _block("const WS_SETTERS = {")
    accum = setters.split("accum: (on) => {", 1)[1]
    accum = accum[:accum.index("},")]
    assert "loadAccumZones(" in accum
    assert "if (on)" in accum, "fetching when switched off is a wasted request"


def test_the_loader_asks_the_right_endpoint_and_caches_per_symbol():
    fn = _fn("loadAccumZones")
    assert "/api/longterm/${encodeURIComponent(sym)}?indices=false" in fn
    # Per symbol, or switching the overlay off and on refetches, and switching
    # symbols draws the old company's levels over the new company's price.
    assert "STATE.accumZonesFor === sym" in fn
    assert "STATE.accumZonesFor = sym" in fn


def test_a_symbol_change_refetches_when_the_overlay_is_on():
    """Same rule as trendlines: the chart loader triggers it, so arriving on a
    new symbol with the overlay already on is not an empty overlay."""
    fn = _fn("loadChartWorkspace")
    assert "if (showAccum) loadAccumZones(sym);" in fn


def test_the_failure_shapes_are_both_tested_for():
    """Two of them reach accumLines and neither is falsy, which is the trap
    CLAUDE.md records: the server sends `{error: ...}` on a bad symbol, and
    the loader writes `{available: false, reason: ...}` when the request
    itself fails. `if (!holding)` catches neither and the map below throws."""
    fn = _fn("accumLines")
    guard = fn[:fn.index("const zones")]
    assert "holding.error" in guard
    assert "holding.available === false" in guard
    loader = _fn("loadAccumZones")
    assert "available: false" in loader, "the loader must produce the shape tested above"


# ------------------------------------------------------------- what it draws


def test_the_retracements_go_through_the_shared_builder():
    """`fibLines` is what the Investing chart calls. Two implementations of
    "how this app draws a level" is exactly how the Charting tab and the Swing
    chart came to disagree about Fibonacci -- see CLAUDE.md."""
    fn = _fn("accumLines")
    assert "fibLines(" in fn


def test_the_weekly_averages_do_not():
    """`fibLines` reads a ratio out of the label and there is none in
    "40-week average", so it would render `undefined (374.99)`. They are also
    averages rather than retracements: drawing them in the Fibonacci colour
    would say they were."""
    fn = _fn("accumLines")
    assert "isRetracement" in fn
    assert "filter((z) => !isRetracement(z))" in fn
    assert "z.ratio !== null && z.ratio !== undefined" in fn, \
        "a regex over the label is the fragile way to ask this; the server sends the ratio"


def test_spot_is_read_from_the_levels_block():
    """`levels.spot`, not `long_trend.spot`. Reading the wrong block gives
    undefined, and fibLines then drops the "From here" row from every tooltip
    without erroring -- a silently thinner tooltip."""
    fn = _fn("accumLines")
    assert "(holding.levels || {}).spot" in fn


def test_the_chart_is_actually_handed_them():
    """A toggle switched on and never passed to lineChart is the insider-marker
    bug: the checkbox changes and nothing else does."""
    fn = _fn("wsMountChart")
    assert "showAccum ? accumLines(STATE.accumZones) : []" in fn


def test_they_are_excluded_on_intraday():
    """Weekly bars over twelve years against a five-minute series. The same
    exclusion the averages and the daily zones already carry, and it comes free
    from the `intraday ? [] :` guard on the whole refLines array -- so this
    asserts the call sits inside that guard rather than after it."""
    fn = _fn("wsMountChart")
    refs = fn.split("refLines: intraday ? [] : [", 1)[1]
    refs = refs[:refs.index("\n      ],")]
    assert "accumLines(STATE.accumZones)" in refs


# ------------------------------------------------- the fields the client reads


def test_the_server_sends_the_fields_the_overlay_reads():
    """Both directions. The client reads `price`, `ratio`, `label`, `kind`,
    `is_golden` and `distance_pct`; a renamed field here draws nothing and
    throws nothing."""
    idx = pd.date_range("2014-01-01", periods=3000, freq="B")
    close = pd.Series(
        [100 + i * 0.05 + (i % 60) * 0.8 for i in range(len(idx))], index=idx)
    zones = _accumulation_zones(close, {"sma_40w": 150.0, "sma_200w": 120.0})
    assert zones, "no zones from three thousand bars"
    for z in zones:
        assert "price" in z and "label" in z and "kind" in z
        assert "distance_pct" in z
    averages = [z for z in zones if z.get("ratio") is None]
    retracements = [z for z in zones if z.get("ratio") is not None]
    assert len(averages) == 2, "the two weekly averages are what accumLines draws itself"
    assert retracements, "and the retracements are what it hands to fibLines"
    for z in retracements:
        assert isinstance(z["ratio"], float)
        assert "is_golden" in z


def test_the_two_zone_families_are_told_apart_by_the_ratio_not_the_words():
    """`accumLines` filters on `ratio`, so the two averages must be the only
    entries without one. If a retracement ever shipped without a ratio it would
    be drawn as an average, in the wrong colour, labelled with its prose."""
    idx = pd.date_range("2014-01-01", periods=3000, freq="B")
    close = pd.Series(
        [100 + i * 0.05 + (i % 60) * 0.8 for i in range(len(idx))], index=idx)
    zones = _accumulation_zones(close, {"sma_40w": 150.0, "sma_200w": 120.0})
    no_ratio = [z["label"] for z in zones if z.get("ratio") is None]
    assert no_ratio == ["40-week average", "200-week average"]


def test_the_two_zone_kinds_are_the_ones_the_overlay_reports():
    """`kind` goes into the tooltip's Role row verbatim."""
    idx = pd.date_range("2014-01-01", periods=3000, freq="B")
    close = pd.Series(
        [100 + i * 0.05 + (i % 60) * 0.8 for i in range(len(idx))], index=idx)
    for sma, expected in ((10.0, "support"), (10000.0, "reclaim level")):
        zones = _accumulation_zones(close, {"sma_40w": sma})
        assert zones[0]["kind"] == expected


def test_the_jsc_harness_declares_the_flag():
    """`loadChartWorkspace` is extracted and run under JavaScriptCore by
    test_client_loading.py with a hand-written stub preamble. An undeclared
    identifier there is a ReferenceError, not undefined, so adding a flag to
    that function without adding it to the stubs turns every scenario in that
    file red."""
    harness = open("tests/test_client_loading.py", encoding="utf-8").read()
    assert re.search(r"showAccum\s*=\s*false", harness)
