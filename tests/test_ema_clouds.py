"""Tests for the EMA cloud overlays.

A cloud is the filled area between two exponential averages, tinted by which one
is on top. The renderer lives in charts.js and there is no JS test runner in this
project, so what is checked here is the wiring — which is where every previous
overlay failure in this codebase actually happened:

  * a toggle offered in a menu with no setter behind it (the six moving averages
    all wrote to two variables, so one checkbox moved three lines);
  * an overlay switched on and never passed to the chart (insider markers and
    volume-by-price were both offered on the Charting tab and neither reached
    lineChart, so the checkbox changed and nothing else did);
  * a field missing from the weekly aggregate, which builds a fresh object rather
    than spreading the daily one, so anything unnamed is silently absent.

Each of those is a silent failure: the control looks right and does nothing.
"""

import re

from app.analytics import technicals

APP = open("static/app.js", encoding="utf-8").read()
CHARTS = open("static/charts.js", encoding="utf-8").read()

CLOUDS = ("cloud921", "cloud2150")


def _block(source, marker, end="\n];"):
    start = source.index(marker)
    return source[start:source.index(end, start)]


def test_every_cloud_is_reachable_from_a_menu():
    """An overlay defined but not listed in WS_MENUS cannot be switched on at all."""
    menus = _block(APP, "const WS_MENUS = [")
    for cloud in CLOUDS:
        assert "'%s'" % cloud in menus, cloud


def test_every_cloud_has_a_flag_and_a_setter():
    """wsOverlayOn reads WS_FLAGS and wsSetOverlay writes through WS_SETTERS.
    A checkbox missing either half renders unchecked forever or never redraws."""
    flags = _block(APP, "const WS_FLAGS = {", "\n};")
    setters = _block(APP, "const WS_SETTERS = {", "\n};")
    for cloud in CLOUDS:
        assert "%s:" % cloud in flags, "%s has no flag" % cloud
        assert "%s:" % cloud in setters, "%s has no setter" % cloud


def test_both_charts_are_handed_the_clouds():
    """The Swing chart and the Charting workspace each call lineChart once. A
    toggle that reaches neither is the insider-marker bug again."""
    assert APP.count("clouds: emaClouds(ps),") == 2


def test_line_chart_accepts_the_option():
    """Destructured with a default, or every existing caller throws."""
    assert re.search(r"^\s*clouds = \[\],\s*$", CHARTS, re.M)


def test_clouds_are_suppressed_on_intraday():
    """The EMAs come from daily closes. Drawn on an intraday chart they would be
    describing a different timeframe from the one on screen, which is why the
    averages and the Fibonacci levels are excluded there too."""
    builder = _block(APP, "function emaClouds(ps)", "\n}")
    assert "if (!ps || ps.intraday) return [];" in builder


def test_weekly_aggregate_recomputes_the_emas():
    """aggregateWeekly builds a fresh object, so a field it does not name is
    absent from a weekly series. The EMAs were unnamed: switching to Weekly left
    the cloud with nothing to fill and the EMA lines with nothing to draw, while
    the legend still listed them."""
    agg = _block(APP, "function aggregateWeekly(ps)", "\n  return out;")
    for period in (9, 21, 50):
        assert "out.ema%d = emaSeries(out.close, %d);" % (period, period) in agg


def test_cloud_pairs_name_series_the_server_actually_sends():
    """The pairs are read off price_series by name. A rename server-side would
    empty the cloud with no error anywhere."""
    builder = _block(APP, "function emaClouds(ps)", "\n}")
    assert "add('cloud921', ps.ema9, ps.ema21);" in builder
    assert "add('cloud2150', ps.ema21, ps.ema50);" in builder
    payload = _block(technicals_source(), '"price_series": {', "\n        },")
    for field in ("ema9", "ema21", "ema50"):
        assert '"%s":' % field in payload, field


def technicals_source():
    return open(technicals.__file__, encoding="utf-8").read()


def test_a_filled_overlay_offers_no_line_width_or_colour():
    """Both are meaningless for a ribbon whose two colours carry the reading
    rather than an identity, and the style dialog's own comment is that a control
    the renderer ignores is worse than no control."""
    defs = _block(APP, "const OVERLAY_DEFS = [")
    for cloud in CLOUDS:
        entry = defs[defs.index("id: '%s'" % cloud):]
        assert "fill: true" in entry[:entry.index("}")], cloud
    row = _block(APP, "function wsManageRow(def)", "\n}")
    assert "${def.fill ? `" in row, "the dialog does not branch on fill"


def test_clear_all_levels_clears_the_clouds():
    """Otherwise 'Clear all' leaves two overlays on a chart it just promised to
    strip, and the count beside the menu disagrees with what is drawn."""
    handler = APP[APP.index("data-clear-levels]"):]
    handler = handler[:handler.index("return;")]
    assert "showCloudFast = false" in handler
    assert "showCloudSlow = false" in handler
    assert "SHOW_CLOUD_FAST_KEY, false" in handler
    assert "SHOW_CLOUD_SLOW_KEY, false" in handler


def test_the_overlay_count_includes_the_clouds():
    """levelCount drives the badge on the Technical Levels button."""
    counter = _block(APP, "function levelCount()", "\n}")
    assert "showCloudFast" in counter and "showCloudSlow" in counter
