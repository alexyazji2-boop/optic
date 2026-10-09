"""Charts sweep in when a sub-page is opened, not only on its first fetch.

Asked for as "show the chart animation when the subtab clicking the futures on
the home page loads and similar sub tabs". The futures chart opened from Home
(the instrument page) never asked for the draw-on, and a section page reopened
from memory re-rendered with whatever flag the last view left, which after a
silent refresh is off.
"""
from pathlib import Path

APP = (Path(__file__).resolve().parent.parent / "static/app.js").read_text()


def _fn(name):
    at = APP.index("function %s(" % name)
    return APP[at:APP.index("\n}\n", at) + 3]


def test_the_sweep_is_set_around_a_render_and_put_back():
    fn = _fn("sweepCharts")
    assert "const was = chartAnimationOn();" in fn
    assert "setChartAnimation(true);" in fn
    assert "finally { setChartAnimation(was); }" in fn


def test_the_futures_chart_sweeps_on_open_and_on_a_new_timeframe():
    load = _fn("loadInstrument")
    assert load.count("sweepCharts(() => drawInstrumentChart(") == 2, "cached open and fresh load"
    assert "drawInstrumentChart(STATE.instrumentData);\n    return;" not in load


def test_a_section_page_reopened_from_memory_sweeps():
    for render in ("renderBrief(STATE.brief)", "renderMarket(STATE.market)", "renderLong(STATE.long)",
                   "renderRoth(STATE.roth)", "renderTracker(STATE.tracker)",
                   "renderIndices(STATE.indices)", "renderEarnings(STATE.earnings)"):
        assert "sweepCharts(() => %s)" % render in APP, render


def test_a_silent_refresh_still_does_not_sweep():
    """The fresh-fetch paths keep their own rule: animate unless silent."""
    for loader in ("loadMarket", "loadLong", "loadIndices"):
        assert "setChartAnimation(!silent || hasPendingDraws());" in _fn(loader), loader
