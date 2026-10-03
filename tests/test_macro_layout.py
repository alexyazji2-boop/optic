"""The Macro tab's first row: the regime beside breadth and equal-weight.

Two asks with screenshots. "clear this gap in the macro section": the regime
panel carries its twelve-term breakdown and is the tall one, and the breadth
panel beside it ended a third of the way down. And of the equal-weight panel,
five sections further down: "move this up in the macro tab and say why it is
important. no repetition". Its title, both tile captions and its note all said
"equal-weight vs cap-weight", and the note stated the three-month figure the
tile under it showed again.

It sits under breadth in the right column now, the row's columns end on one
line, and it says why it matters once, in words the reading above does not
use. Measured at 1440px: 1,145px of regime panel against 1,068px of right
column before the last panel takes up the difference, from a void of about
600px.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
CSS = (ROOT / "static/styles.css").read_text()


def _market():
    body = APP[APP.index("function renderMarket(d) {"):]
    return body[:body.index("\n}\n")]


def test_equal_weight_sits_under_breadth_beside_the_regime():
    html = _market()
    row = html[html.index('<div class="grid c2 gap macro-row">'):html.index('<div id="rotation-host"')]
    assert row.index("hg('Macro regime')") < row.index('<div class="macro-side">') \
        < row.index("hg('Market breadth')") < row.index("hg('Equal-weight vs cap-weight (RSP / SPY)')")
    assert html.count("Equal-weight vs cap-weight (RSP / SPY)") == 1, "moved, not copied"


def test_the_columns_end_on_one_line():
    assert ".grid.c2.macro-row { align-items: stretch; }" in CSS
    assert ".macro-side > .panel.is-open:last-child { flex: 1 0 auto; }" in CSS
    # Two tiles side by side in a half-width column, not stacked.
    side = _market()
    side = side[side.index('<div class="macro-side">'):side.index('<div id="rotation-host"')]
    assert side.count('<div class="grid c4">') == 2 and '<div class="grid c2">' not in side


def test_it_says_why_once_and_repeats_nothing():
    side = _market()
    panel = side[side.index("hg('Equal-weight vs cap-weight (RSP / SPY)')"):]
    panel = panel[:panel.index('<div id="chart-breadth">')]
    assert '<strong>Why it matters.</strong>' in panel
    assert "tile('3 months', fmtPct(evc.chg_3m_pct, 1), ''" in panel
    assert "tile('1 year', fmtPct(evc.chg_1y_pct, 1), ''" in panel
    assert "equal-weight vs cap-weight'" not in panel.lower().replace("(rsp / spy)", ""), \
        "a tile caption saying the title again"


def test_the_reading_leaves_the_figures_to_the_tiles():
    src = (ROOT / "app/analytics/sectors.py").read_text()
    body = src[src.index("    line = joined[\"rsp\"] / joined[\"spy\"]"):]
    notes = re.findall(r'note = \(?\s*"([^"]+)"', body[:body.index("return {")])
    joined = " ".join(re.findall(r'"([^"]+)"', body[:body.index("return {")]))
    assert "{:.1f}" not in joined and "%" not in joined.replace("{:.1f}%", "")
    assert "The average stock is falling behind the index" in joined
    assert notes, "the readings are still there"


def test_a_shut_panel_in_the_column_keeps_the_height_of_its_heading():
    """Reported with the regime panel tall and equal-weight vs cap-weight shut:
    "fix this UI issue in the macro tab as well". The last panel stretched to
    the row's height whether or not it was open, a heading over a column of
    empty box. Only an open one takes up the difference, and it is open unless
    the reader shut it."""
    assert ".macro-side > .panel.is-closed { flex: 0 0 auto; }" in CSS
    assert ".macro-side > .panel:last-child {" not in CSS
    defaults = APP[APP.index("  market: ['macro regime', 'market breadth',"):]
    defaults = defaults[:defaults.index("],")]
    assert "'equal-weight vs cap-weight'" in defaults
