"""Can Pulse explain the auto trend lines?

It could not, and it would have sounded like it could. chartStateWords puts
"Auto trend lines" into the overlay list it sends, so the model knew the words
were on screen — and nothing else. Not how many lines, not support or
resistance, not rising or falling, not what they are fitted to, not how many
candidates were rejected. Asked what they mean it would have explained trend
lines in general and been entirely credible about a chart it could not see.

That is the failure this codebase keeps naming: an answer that is plausible and
ungrounded is worse than "I cannot see that".
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP_JS = (ROOT / "static" / "app.js").read_text()


def _payload() -> str:
    return APP_JS.split("function chatContextPayload()", 1)[1].split("\nfunction ", 1)[0]


def test_the_trendlines_reach_the_model():
    assert "auto_trendlines" in _payload()


@pytest.mark.parametrize("field", ["kind", "direction", "touches", "touch_dates",
                                   "price_now", "slope_per_bar"])
def test_each_line_carries_what_a_reader_would_ask(field):
    body = _payload()
    assert f"{field}:" in body, f"a line is sent without its {field}"


@pytest.mark.parametrize("field", ["support", "resistance", "candidates_considered",
                                   "dropped_out_of_reach", "breaks"])
def test_the_filtering_is_sent_too(field):
    """"Two lines" and "two lines out of twenty candidates, five of them dropped
    as out of reach" are different claims about how much the set means."""
    assert f"{field}:" in _payload(), field


def test_the_method_is_stated_rather_than_left_to_be_guessed():
    body = _payload()
    assert "method:" in body
    method = body.split("method:", 1)[1][:400]
    assert "pivots" in method
    assert "not a forecast" in method.lower()


def test_the_whole_payload_is_not_sent():
    """/api/trendlines returns a 252-entry date array and per-line bar indexes,
    none of which a model can use, all of which would crowd out the analysis the
    question is usually about."""
    body = _payload()
    block = body.split("auto_trendlines", 1)[1][:1200]
    # The 252-entry date array, and the per-line bar indexes. `touch_dates` is
    # deliberately sent and an earlier version of this test caught it with a
    # `"dates:"` substring, which is the field it was meant to protect.
    assert "t.dates" not in body
    for noise in ("start_index", "end_index", "touch_indexes"):
        assert noise not in block, f"{noise} is a bar index and means nothing to a model"
    assert "...l" not in block, "the raw line object is being spread wholesale"
    assert ".slice(0, 6)" in body, "an unbounded line list could be dozens"


def test_it_is_only_sent_when_it_is_on_screen():
    """Sending lines the reader has toggled off would have Pulse explain
    something not drawn — the mirror of the bug it fixes."""
    body = _payload()
    block = body.split("auto_trendlines", 1)[0][-400:]
    assert "showTrends" in block
    assert "STATE.trendlinesFor === STATE.chartSymbol" in block, \
        "one symbol's trend lines could be described over another's chart"


def test_an_unavailable_computation_says_so():
    body = _payload()
    assert "t.available === false" in body
    assert "available: false" in body


def test_the_page_can_explain_them_too():
    """Pulse is not the only place a reader asks. The glossary is what the
    dotted underline on the chart's own toolbar label reaches."""
    block = APP_JS.split("const GLOSSARY = {", 1)[1].split("\n};", 1)[0]
    assert "'auto trend lines':" in block
    entry = block.split("'auto trend lines':", 1)[1].split("\n", 1)[0]
    assert "not a forecast" in entry.lower(), \
        "the definition must not imply price will turn there again"
