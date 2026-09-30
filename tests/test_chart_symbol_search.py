"""The chart's symbol opens the search, and carries the company's logo.

Asked for with a screenshot of the Charting tab, PLTR circled in its header:
"whenever you click on the ticker, go to the search bar, and add the company
logo next to the ticker on the chart as well". The symbol was bare text.

It is a button now, opening the same palette as the header box and Cmd+K, and
the logo is the typeahead's own (tickerMark), which keys on the ticker, so it
needs no website or profile the chart payload may not carry. The monogram sits
under the image, so a symbol no service has a logo for still gets a mark.

Checked in a browser: PLTR's logo beside the ticker, and a press opened the
palette with its input focused.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
CSS = (ROOT / "static/styles.css").read_text()


def _fn(name):
    return re.search(r"^function %s\([^\n]*\) \{.*?^\}" % name, APP, re.M | re.S).group()


def _head():
    ws = _fn("renderChartWorkspace")
    return ws[ws.index('<div class="ws-head">'):ws.index('<span class="ws-ohlc"')]


def test_the_symbol_is_a_button_that_opens_the_search():
    head = _head()
    assert '<button type="button" class="ws-sym-btn" data-open-palette=""' in head
    assert 'aria-label="${esc(STATE.chartSymbol)}. Search for another symbol"' in head
    # The generic opener every search entry point uses, with an empty seed so
    # the reader can type the next symbol straight away.
    click = APP[APP.index("const opener = evt.target.closest('[data-open-palette]');"):][:300]
    assert "openPalette(seed);" in click and "opener.dataset.openPalette || ''" in click


def test_the_logo_sits_before_the_symbol():
    head = _head()
    assert "tickerMark(STATE.chartSymbol, 26)}<strong>${esc(STATE.chartSymbol)}</strong></button>" in head
    mark = _fn("tickerMark")
    assert "TICKER_LOGO_SOURCES[0](sym)" in mark and "onerror=\"nextTickerLogo(this)\"" in mark
    assert 'aria-hidden="true"' in mark, "the button's label names the symbol once"


def test_the_button_reads_as_the_heading_and_says_it_can_be_pressed():
    rule = CSS[CSS.index(".ws-sym-btn {"):]
    rule = rule[:rule.index("}")]
    for decl in ("background: none;", "border: 0;", "cursor: pointer;", "transition:"):
        assert decl in rule, decl
    assert ".ws-sym-btn:hover strong, .ws-sym-btn:focus-visible strong" in CSS
    assert ".ws-sym-btn:focus-visible { outline: 2px solid var(--focus);" in CSS
