"""Pulse response lenses.

A persona changes which figures the answer leads with and how much doubt it
carries. It must never change the figures, and it must never drop a caveat —
otherwise picking a voice becomes a way of getting the answer you wanted, which
is the opposite of what this terminal is for. These tests are about that
boundary, and about the one persona written in an informal register, which is the
one where a caveat is most likely to be quietly lost.
"""

import pytest

from app import ai


def test_the_default_persona_exists_and_adds_nothing():
    assert ai.DEFAULT_PERSONA in ai.PERSONAS
    assert ai.PERSONAS[ai.DEFAULT_PERSONA]["prompt"] == "", (
        "the default lens should be the base prompt with no additions")


def test_every_persona_has_a_label_and_a_blurb():
    for key, val in ai.PERSONAS.items():
        assert val.get("label"), key
        assert val.get("blurb"), key
        assert len(val["blurb"]) > 20, "%s: blurb too thin to be a choice" % key


def test_no_persona_label_names_a_real_person():
    """The labels used to borrow first names — Warren, Graham, Simon, Karen —
    each pointing at an identifiable investor, while the prompt underneath said
    not to impersonate any real person. The label is what a reader sees first,
    so the menu made a claim the prompt then retracted. Labels now describe the
    lens instead."""
    banned = ("warren", "graham", "simon", "karen", "buffett", "munger",
              "dalio", "soros", "lynch", "wood")
    for key, val in ai.PERSONAS.items():
        low = val["label"].lower()
        for name in banned:
            assert name not in low, "%s label names %s" % (key, name)


def test_every_label_reads_as_a_description_not_a_persona():
    """"Statistician" tells you what comes back. "Simon, the data guy" needs you
    to already know who Simon is."""
    for key, val in ai.PERSONAS.items():
        assert "," not in val["label"], (
            "%s still uses the 'Name, the role' form" % key)


def test_no_persona_impersonates_a_real_person():
    """The prompts must still say explicitly that this is a style and not a
    person, or the model will start attributing views to someone who never held
    them — the labels no longer invite it, but the prompt is the backstop."""
    for key, val in ai.PERSONAS.items():
        if not val["prompt"]:
            continue
        low = val["prompt"].lower()
        assert "do not impersonate" in low or "identical substance" in low, (
            "%s does not forbid impersonation" % key)


def test_no_lens_is_a_register_in_disguise():
    """"Straight to it" used to be the sixth entry here and has moved to
    app/knowledge.py as the Simple end of the ladder.

    It was never a lens. Every other entry answers "whose judgement do I want"
    and changes which figures the answer leads with; that one answered "how much
    do I already know" and changed the register. Two controls for one question
    is how a reader picks Professional density and a compressed voice and gets
    an argument between them.

    So this asserts the separation holds: a lens may not instruct on length or
    on how much to explain, because those belong to the level."""
    for key, val in ai.PERSONAS.items():
        low = val["prompt"].lower()
        for register in ("shortest sentence", "no opening hook",
                         "fewer words", "compress"):
            assert register not in low, "%s is setting a register" % key

def test_no_persona_licenses_a_prediction():
    for key, val in ai.PERSONAS.items():
        low = val["prompt"].lower()
        for phrase in ("predict the", "will go up", "will go down",
                       "guarantee", "tell them to buy"):
            assert phrase not in low, "%s contains %r" % (key, phrase)


def test_the_quant_persona_asks_for_sample_sizes():
    """The persona exists to surface n, which is the terminal's own discipline."""
    p = ai.PERSONAS["quant"]["prompt"].lower()
    assert "sample size" in p
    assert "base rate" in p
    assert "multiple testing" in p or "number of things tested" in p
    assert "unproven" in p


def test_the_skeptic_is_not_merely_contrarian():
    p = ai.PERSONAS["skeptic"]["prompt"].lower()
    assert "same numbers" in p
    assert "if the setup is genuinely" in p, (
        "the adversarial lens must be able to concede")


# ----------------------------------------------------------- output format

def test_the_format_prompt_only_suggests_things_the_app_can_do():
    """The reference product offers "create an alert for META if it breaks back
    above recent highs" as a follow-up. A reader who accepts that offer here gets
    nothing: the alerts inbox is fed by the terminal's own scans, and Pulse has
    no way to add a rule to it. It read "no alerts" until the inbox shipped, at
    which point the flat denial became the wrong sentence rather than a stale
    one, because the panel is real and only the on-request half is missing."""
    # Collapsed, because the prompt is a wrapped literal: "cannot set a price\n
    # alert" is one phrase to the model and two lines to `in`.
    f = " ".join(ai.FORMAT_PROMPT.lower().split())
    assert "cannot set a price alert" in f
    assert "cannot send email" in f
    assert "cannot route an order" in f


def test_the_format_prompt_exempts_short_questions():
    """Structure applied to a one-line question is noise."""
    f = ai.FORMAT_PROMPT.lower()
    assert "short factual question" in f
    assert "ignore all of the above" in f


def test_the_format_prompt_asks_for_a_bottom_line_and_follow_ups():
    f = ai.FORMAT_PROMPT
    assert "Bottom line" in f
    assert "→ " in f, "follow-ups need a machine-detectable prefix"


def test_format_is_separate_from_persona():
    """If the format rules were inside each persona they would be restated five
    times and drift. This asserts the split holds."""
    for val in ai.PERSONAS.values():
        assert "Bottom line" not in val["prompt"]
        assert "→" not in val["prompt"]
