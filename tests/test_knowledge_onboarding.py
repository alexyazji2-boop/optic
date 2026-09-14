"""Asking the question once.

The mode ladder shipped with a selector nobody is ever pointed at, so every new
reader silently landed on Financially Literate and the product's defining
feature was invisible unless you went looking in Ask Pulse.

The brief is explicit about the shape: one question, and nobody sits an exam.
It is equally explicit that the reader is never categorised, so the answers are
the taglines already published with each mode and there is no second copy of
them here to drift.

Verified in a browser from a cleared store:

    pick 'Advanced'  -> mode advanced, asked true, card gone, survives reload
    skip             -> mode literate, asked true, card gone, survives reload
"""

import re

APP_JS = open("static/app.js", encoding="utf-8").read()
COMPONENT = open("static/components/knowledge.js", encoding="utf-8").read()
CSS = open("static/styles.css", encoding="utf-8").read()


def strip_comments(js):
    js = re.sub(r"/\*.*?\*/", " ", js, flags=re.S)
    return re.sub(r"(?<!:)//[^\n]*", " ", js)


CODE = strip_comments(APP_JS)
COMP = strip_comments(COMPONENT)


def body_of(name, src=None):
    s = src if src is not None else CODE
    start = s.index("function %s(" % name)
    return s[start:].split("\nfunction ", 1)[0]


# ---------------------------------------------- chosen-nothing vs chose-default

def test_being_asked_is_its_own_state():
    """`read()` returns the default when the key is absent, which is right for
    every caller that needs a level and useless for the one question worth
    asking once. Without a second key a considered "Financially Literate" and
    never having seen the control are the same value, so the prompt would
    either never appear or appear forever."""
    assert "optic.knowledge.asked.v1" in COMP
    assert "optic.knowledge.asked.v1" != "optic.knowledge.v1"


def test_private_browsing_counts_as_already_asked():
    """The flag cannot be stored there, so the card would reappear on every
    navigation. A question that will not stay answered is worse than one never
    asked."""
    fn = body_of("asked", COMP)
    assert "catch (e) { return true; }" in fn


def test_choosing_records_both_the_answer_and_that_it_was_asked():
    fn = body_of("choose", COMP)
    assert "markAsked()" in fn
    assert "if (id) set(id)" in fn


def test_skip_is_an_answer_not_a_dismissal():
    """`choose(null)` keeps the default and still marks it asked. A prompt that
    returns until you engage with it teaches people to ignore the product's
    other questions too."""
    handler = CODE[CODE.index("closest('[data-kob-skip]')"):]
    handler = handler[:handler.index("\n});")]
    assert "choose(pick ? pick.dataset.kobPick : null)" in handler


# --------------------------------------------------------------- the card

def test_it_is_a_card_in_the_flow_not_a_modal_over_the_page():
    """Nothing gates this terminal: every research endpoint answers a guest
    exactly as it did before accounts existed, and that is a requirement rather
    than a current state of affairs. A wall in front of the market on a first
    load would be the one place that rule broke, for a preference."""
    rule = CSS[CSS.index(".kob {"):]
    rule = rule[:rule.index("}")]
    assert "position: fixed" not in rule and "position: absolute" not in rule
    assert "z-index" not in rule


def test_the_market_is_still_the_first_thing_on_the_page():
    """The strip is the reason anybody opens this on the second day."""
    home = CODE[CODE.index('<div id="cc-strip"></div>'):]
    assert home.index("knowledgeOnboardingHTML()") < home.index("home-brand")


def test_it_offers_every_mode_and_a_way_out():
    fn = body_of("knowledgeOnboardingHTML")
    assert "modes.map(" in fn
    assert "data-kob-skip" in fn


def test_the_answers_are_not_a_second_copy_of_the_taglines():
    """The card renders what the catalogue publishes. Hardcoding five taglines
    here would drift the day one of them is reworded."""
    fn = body_of("knowledgeOnboardingHTML")
    assert "m.tagline" in fn
    from app import knowledge
    for mode in knowledge.MODES.values():
        assert mode["tagline"] not in CODE, mode["tagline"]


def test_it_renders_nothing_before_the_catalogue_lands():
    """A card with five blank buttons is worse than one arriving a beat later."""
    fn = body_of("knowledgeOnboardingHTML")
    assert "if (!modes.length) return '';" in fn


def test_home_is_repainted_when_the_catalogue_arrives():
    """Home is painted before the fetch resolves, so the card had nothing to
    offer and returned empty. Without this it would never appear at all: the one
    visit it is for is the visit where the catalogue has not landed yet."""
    assert "if (STATE.view === 'home' && !window.OpticKnowledge.asked()) renderHome();" in CODE


def test_it_does_not_ask_again_once_answered():
    fn = body_of("knowledgeOnboardingHTML")
    assert "K.asked()" in fn
    assert re.search(r"if \(!K \|\| K\.asked\(\)\) return '';", fn)


# ------------------------------------------------------------- the wording

def test_the_question_is_about_optic_not_about_the_reader():
    """"How should Optic speak to you?" asks about the product. "How much do you
    know?" would ask the reader to rate themselves, which is the thing the brief
    rules out."""
    fn = body_of("knowledgeOnboardingHTML")
    assert "How should Optic speak to you?" in fn
    for banned in ("how much do you know", "experience level", "rate your",
                   "beginner", "test"):
        assert banned not in fn.lower(), banned


def test_it_says_what_the_choice_does_and_does_not_do():
    """The same promise the selector makes, because a reader deciding here has
    not seen the selector yet."""
    fn = body_of("knowledgeOnboardingHTML")
    low = fn.lower()
    assert "never the figures" in low
    assert "change it any time" in low


def test_it_names_the_assistant_the_way_the_app_does():
    """The app calls it Pulse. The brief this was built from says "Ask Optic"
    throughout, and a test caught the copy importing that wording: the reader
    renamed it and the product's own name wins over the spec's."""
    fn = body_of("knowledgeOnboardingHTML")
    assert "Ask Pulse" in fn
    assert "Ask Optic" not in fn


# -------------------------------------------------------------- responsive

def test_the_five_options_reflow_rather_than_sitting_in_a_fixed_grid():
    """Five at 150px do not fit a phone, and a fixed count gives three rows of
    oddly-sized buttons there."""
    rule = CSS[CSS.index(".kob-opts {"):]
    rule = rule[:rule.index("}")]
    assert "auto-fit" in rule and "minmax(" in rule


def test_the_options_are_focusable_and_transition():
    assert ".kob-opt:focus-visible" in CSS
    rule = CSS[CSS.index(".kob-opt {"):]
    rule = rule[:rule.index("}")]
    assert "transition" in rule
