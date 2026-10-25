"""Explain this, throughout Optic (2026-10-12): a figure goes to Milo with
its actual value, ticker and page, asking what it measures, why use it, what
this value suggests and what it cannot establish. Drafted, never sent unseen.
Measured in Chromium at 402px: the Overview's two Optic Score tiles and the
stage chip each carry their reading ("64/100, Leaning bullish · low
conviction"; "Stage 2 (Advancing)")."""
from __future__ import annotations

from pathlib import Path

APP = (Path(__file__).resolve().parent.parent / "static/app.js").read_text()


def _fn(head):
    at = APP.index(head)
    return APP[at:APP.index("\n}\n", at) + 3]


def test_the_prompt_names_the_value_and_the_four_questions_and_drafts():
    fn = _fn("function miloExplainPrompt(item) {")
    assert "what it measures, why someone would use it, what this value suggests, " in fn
    assert "and what it cannot tell me." in fn
    handler = APP[APP.index("const btn = evt.target.closest && evt.target.closest('[data-milo-explain]');"):][:400]
    assert "draftPulse(miloExplainPrompt(item));" in handler and "sendChat" not in handler


def test_it_is_offered_where_a_reader_meets_a_reading():
    for where in ("miloExplainButton('RSI (14)'", "miloExplainButton('MACD (12, 26, 9)'",
                  "miloExplainButton('Trend Strength Oscillator (14, 14, 5)'",
                  "return miloExplainButton('MA Trend Identifier', words, 'Chart');",
                  "host.insertAdjacentHTML('afterend', miloExplainButton('Weinstein stage',",
                  "ask.className = 'ov-linkbtn gloss-milo';"):
        assert where in APP, where
    # The Optic Score's tiles traded Explain for an inline "How this is calculated" fold (owner, 2026-10-25)
    assert "miloExplainButton(`Optic Score" not in APP and "How this is calculated" in APP
