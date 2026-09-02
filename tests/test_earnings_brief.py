"""Parsing and salvage for the written pre-earnings brief.

The interesting failure here was not a bad model response. It was a *good* one
that ran past the token limit: the object opened correctly and never closed, so
`rfind("}")` returned -1 and a fully paid-for brief was thrown away under the log
line "no JSON object" — which described the opposite of what had happened.

So these tests care about two things: that a truncated response is told apart
from a malformed one, and that salvage never emits a half-finished sentence.
"""

from __future__ import annotations

import json

import pytest

from app import ai


GOOD = json.dumps({
    "headline": "Beats every quarter, fades anyway",
    "stance": "two-sided",
    "paragraphs": ["## The setup", "Reports in 12 days.", "## The track record",
                   "Eight beats from eight."],
})


def test_parses_a_clean_response():
    got = ai._parse_brief_json(GOOD, False, "NVDA")
    assert got["stance"] == "two-sided"
    assert len(got["paragraphs"]) == 4


def test_parses_around_a_preamble_or_fence():
    """A stray fence must not lose the brief."""
    got = ai._parse_brief_json("```json\n" + GOOD + "\n```", False, "NVDA")
    assert got["headline"].startswith("Beats every quarter")


def test_multiline_paragraphs_survive_the_strict_parser():
    """Literal newlines inside strings are why strict=False is required.

    The morning note fell back to mechanical prose for exactly this reason on
    JSON that was otherwise perfectly well formed.
    """
    blob = '{"headline":"h","stance":"two-sided","paragraphs":["line one\nline two"]}'
    got = ai._parse_brief_json(blob, False, "NVDA")
    assert got is not None
    assert "line two" in got["paragraphs"][0]


# ------------------------------------------------------------- truncation

TRUNCATED = ('{"headline":"Beats every quarter","stance":"two-sided","paragraphs":['
             '"## The setup","Reports in 12 days.","Eight beats from eig')


def test_truncated_response_is_salvaged():
    """Complete paragraphs before the cut are kept; the fragment is not."""
    got = ai._parse_brief_json(TRUNCATED, True, "NVDA")
    assert got is not None
    assert got["paragraphs"] == ["## The setup", "Reports in 12 days."]
    assert not any("eig" in p and "eight" not in p.lower() for p in got["paragraphs"])


def test_truncated_response_keeps_the_headline_and_stance():
    got = ai._parse_brief_json(TRUNCATED, True, "NVDA")
    assert got["headline"] == "Beats every quarter"
    assert got["stance"] == "two-sided"


def test_unclosed_json_without_truncation_is_rejected():
    """No closing brace and no truncation means something else went wrong.

    Salvaging here would paper over a real malformation, so this fails closed
    rather than guessing.
    """
    assert ai._parse_brief_json(TRUNCATED, False, "NVDA") is None


def test_no_json_at_all_is_rejected():
    assert ai._parse_brief_json("I cannot help with that.", False, "NVDA") is None
    assert ai._parse_brief_json("", True, "NVDA") is None


def test_salvage_gives_up_rather_than_inventing():
    """A cut before any complete string yields nothing, not an empty brief."""
    assert ai._parse_brief_json('{"headline":"Beats ev', True, "NVDA") is None


def test_malformed_json_is_rejected_when_not_truncated():
    assert ai._parse_brief_json('{"headline": oops}', False, "NVDA") is None


# ------------------------------------------------------------------ shape

def test_prompt_forbids_inventing_business_narrative():
    """The one thing free data cannot support is what management said.

    Without this the model will happily narrate a product launch or a guidance
    figure, which is the most damaging possible failure for a pre-earnings read
    because it is fluent and completely unfounded.
    """
    p = ai.EARNINGS_PROMPT
    assert "Do NOT invent business narrative" in p
    assert "guidance" in p
    assert "Use ONLY figures in the DATA block" in p


def test_prompt_requires_a_stance_and_its_counter_argument():
    p = ai.EARNINGS_PROMPT
    assert "leaning bullish" in p and "leaning bearish" in p and "two-sided" in p
    assert "strongest argument against" in p


def test_prompt_forbids_advice():
    p = ai.EARNINGS_PROMPT
    for phrase in ("No price targets of your own", "position sizing", "buy or sell"):
        assert phrase in p


def test_token_budget_is_large_enough_for_five_sections():
    """2000 truncated the first live ticker tried. Guard the regression."""
    assert ai.EARNINGS_MAX_TOKENS >= 3000


@pytest.mark.parametrize("stance", ["leaning bullish", "leaning bearish", "two-sided"])
def test_ui_styles_every_stance_the_prompt_allows(stance):
    """Every stance the prompt permits must have a class the stylesheet knows.

    A stance the UI does not recognise renders unstyled, which reads as a bug to
    the user and is invisible in any backend test.
    """
    app_js = open("static/app.js").read()
    assert "'{}'".format(stance) in app_js
