"""The Compare boxes suggest tickers as they are typed in, names included.

Reported by a user: "When someone is doing Side-by-Side comparison, searching
the ticker box should give them recommended tickers based on their search. And
I should be able to type Amazon and that ticker will show up as an option".
Checked in a browser at 1470x785: typing "Amazon" offered AMZN (Amazon.com,
Inc) and an Amazon ETF; picking AMZN filled the box, moved focus to the next
empty one and stayed on Compare; "apple", Down, Enter picked AAPL without
running the comparison, and a plain Enter then ran it.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = (ROOT / "static/app.js").read_text()
CSS = (ROOT / "static/styles.css").read_text()


def _fn(name):
    return re.search(r"^(?:async )?function %s\([^\n]*\) \{.*?^\}" % name, RAW, re.M | re.S).group()


def test_each_box_is_a_combobox_with_its_own_list():
    fn = _fn("renderCompare")
    assert '<div class="combo cmp-combo">' in fn
    assert 'id="cmp-input-${i}" data-cmp-input="${i}"' in fn
    assert 'role="combobox" aria-expanded="false"' in fn and 'aria-controls="cmp-results-${i}"' in fn
    assert '<ul class="combo-list" id="cmp-results-${i}" role="listbox" hidden></ul>' in fn
    assert 'placeholder="Ticker ${i + 1} or company"' in fn
    assert ".cmp-combo { flex: 0 1 auto; }" in CSS


def test_every_render_is_wired_and_a_pick_stays_on_the_tab():
    mount = _fn("mountCompare")
    assert "views.compare.innerHTML = renderCompare(c);" in mount
    assert "attachTypeahead(`cmp-input-${i}`, `cmp-results-${i}`, (pick) => {" in mount
    assert "next[i] = pick.symbol;" in mount and "if (empty) empty.focus();" in mount
    # Every other render goes through it, so no render loses its suggestions.
    assert RAW.count("views.compare.innerHTML = renderCompare(") == 1
    assert RAW.count("mountCompare(") >= 9


def test_the_shared_typeahead_takes_a_pick_handler_and_keeps_its_old_default():
    fn = _fn("attachTypeahead")
    assert "function attachTypeahead(inputId, listId, onChoose) {" in fn
    assert "if (onChoose) onChoose(pick);\n    else loadTicker(pick.symbol, SEARCH_LANDING);" in fn
    assert "attachTypeahead('home-input', 'home-results');" in RAW


def test_enter_on_a_suggestion_picks_it_rather_than_running_the_comparison():
    assert ("if (evt.key === 'Enter' && !evt.defaultPrevented && "
            "evt.target.closest('[data-cmp-input]')) {\n    runCompare();") in RAW
