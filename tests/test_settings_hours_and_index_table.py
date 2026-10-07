"""Two tables that were wider than a phone for no reason a reader would accept.

The Index regime table has eleven columns and scrolls sideways on anything
narrower than a desktop; the names scrolled away with the figures, and the
whole panel body scrolled, taking the summary sentence with it. Settings'
market hours repeated the Eastern column word for word as "Your zone" when the
reader is on market time, under a line saying nothing is converted.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
CSS = (ROOT / "static/styles.css").read_text()


def test_the_index_names_stay_while_the_figures_scroll():
    assert '<div class="table-scroll"><table class="data sticky-first" data-defs="indices">' in APP
    rule = CSS[CSS.index("table.sticky-first th:first-child,"):]
    rule = rule[:rule.index("}")]
    assert "position: sticky;" in rule and "left: 0;" in rule and "background: var(--surface);" in rule


def test_market_time_readers_get_one_time_column():
    body = APP.split("function renderSettings() {", 1)[1].split("\n}\n", 1)[0]
    assert "${onMarketTime ? '' : '<th>Your zone</th>'}" in body
    assert "${onMarketTime ? '' : `<td>${esc(timeIn(seg.start_at, zone))}" in body
