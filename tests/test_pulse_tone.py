"""Pulse's voice, and the things warmth is not allowed to cost.

The register was rewritten to be friendlier after a reader compared it against a
chat assistant that ends a ranked shortlist with "still not trading advice, just
the tape, the levels, and the news". That closing line is the whole brief in one
sentence: the caveat is still there, it is one clause, and it sounds like a
person rather than a compliance footer.

The risk in a change like that is not that the prose gets worse. It is that a
tone pass quietly removes a constraint, because every constraint in a prompt is
also a sentence, and rewriting sentences is exactly what a tone pass does. So
half of this file is about the voice and half is a regression guard on the hard
limits that were already there.

These read the prompt constants rather than the file, which keeps them off the
explanatory comments around the strings. A prompt is data, not control flow: the
text *is* the artefact, so asserting on it is not the same mistake as grepping a
function for a `return`.
"""

from app import ai


def flat(text):
    """Collapse the wrapped literal into one line.

    Every prompt here is a hand-wrapped triple-quoted string, so a phrase the
    model reads as continuous is two lines to `in`. This caught a first pass of
    these tests: "cannot set a price alert" is really "cannot set a price\n
    alert".
    """
    return " ".join(text.lower().split())


SYSTEM = flat(ai.SYSTEM_PROMPT)
FORMAT = flat(ai.FORMAT_PROMPT)


def prompt_constants():
    """Every prompt the model is given, by name."""
    named = {n: getattr(ai, n) for n in dir(ai)
             if n.endswith("_PROMPT") and isinstance(getattr(ai, n), str)}
    named.update({"PERSONAS[%s]" % k: v["prompt"] for k, v in ai.PERSONAS.items()})
    return named


# --------------------------------------------------------------- the warmth

def test_pulse_is_told_to_address_the_reader():
    """The old register described good prose and never mentioned the reader, so
    the answers were well written *at* somebody. Second person is most of what
    separates "since your chart is $META daily" from a filed report."""
    assert "talk to the reader" in SYSTEM
    assert "second person" in SYSTEM


def test_pulse_answers_from_what_the_reader_has_on_screen():
    assert "in front of them" in SYSTEM
    assert "written for anybody" in SYSTEM, (
        "the contrast is what makes the rule actionable")


def test_pulse_owns_its_read_in_the_first_person():
    """A reader asking what the data says is also asking what you make of it. An
    answer with no first person in it reads as though nobody was home."""
    assert "first person" in SYSTEM
    assert "my ranking" in SYSTEM


def test_pulse_states_the_size_of_the_pool_it_checked():
    """"The least clownish setup of the names I checked" is warm and honest in
    the same clause. A bare superlative is neither: it hides how many things were
    looked at, which is the one thing that decides what it is worth."""
    assert "names i checked" in SYSTEM
    assert "superlative" in SYSTEM


def test_humour_is_allowed_and_bounded():
    """Dry humour was already permitted. What is new is where it stops."""
    assert "humour" in SYSTEM
    assert "at the reader's expense" in SYSTEM
    assert "gone against them" in SYSTEM, (
        "a joke lands differently when the reader is down on the position")


def test_plain_words_do_not_mean_dropped_vocabulary():
    """Friendly and condescending are easy to confuse. The reader knows what IV
    rank is; the fix is to explain the term, not to avoid saying it."""
    assert "keep the term and explain it" in SYSTEM
    assert "condescending" in SYSTEM


# ------------------------------------------- what warmth is not allowed to be

def test_warmth_is_not_paid_for_with_rigour():
    """The load-bearing sentence of the whole rewrite. Without it, "be friendly"
    reads as licence to round the numbers off."""
    assert "friendly and rigorous are not a trade-off" in SYSTEM
    assert "never gets spent" in SYSTEM


def test_flattery_is_not_warmth():
    assert "great question" in SYSTEM
    assert "not flattery" in SYSTEM


def test_no_emoji_or_hype():
    """Hype was already banned in the informal lens. It has to be banned in the
    base voice too, now that the base voice is a friendly one."""
    for phrase in ("no emoji", "exclamation marks", "no hype"):
        assert phrase in SYSTEM, phrase
    assert "enthusiasm about a position is not warmth" in SYSTEM


def test_the_friendly_voice_may_not_become_a_catchphrase():
    """The example that prompted this ends "my dude". Once, that is warm. On
    every reply it is a script, and a signature that appears regardless of what
    was asked stops carrying any warmth at all."""
    assert "not a catchphrase" in SYSTEM
    assert "nickname" in SYSTEM


def test_warmth_is_not_agreement():
    """The sharpest failure mode of a friendly assistant in a money app. Being
    liked and being useful come apart exactly when the reader is wrong."""
    assert "not agreement" in SYSTEM
    assert "disagrees with the context numbers" in SYSTEM
    assert "what they want to hear about their own money" in SYSTEM


def test_warmth_does_not_soften_the_conclusion():
    """"No edge here" is a legitimate answer and stays the answer. A warm hedge
    is worse than a blunt finding, because a hedge reads as permission."""
    assert "not a softer conclusion" in SYSTEM
    assert "no edge here" in SYSTEM
    assert "hedged maybe" in SYSTEM


# ------------------------------------------------------ the caveats, in voice

def test_the_caveats_are_delivered_in_the_voice_not_as_a_footer():
    """What the reader circled. The limits stay; the compliance paragraph goes."""
    assert "not a footer" in SYSTEM or "bolted to the end" in SYSTEM
    assert "say them once, in a clause" in SYSTEM


def test_the_caveat_rule_names_every_limit_it_is_shortening():
    """A rule that said "be brief about the caveats" without listing them would
    be an invitation to drop one. It names all four."""
    for limit in ("delayed prices", "inferred flow direction",
                  "dealer-positioning assumption",
                  "what this reader does with their money"):
        assert limit in SYSTEM, limit


def test_the_caveat_rule_gives_the_reason_it_is_safe():
    """It is only safe to shorten the in-prose caveat because the formal one is
    already on screen: `#pulse-legal` in index.html renders LEGAL.areas.pulse
    above the conversation. Stating the reason is what stops a later editor from
    reading this as "the disclaimer does not matter"."""
    assert "full formal disclaimer on screen" in SYSTEM
    assert "third telling" in SYSTEM


def test_the_formal_disclaimer_the_prompt_relies_on_is_actually_rendered():
    """The prompt's justification is a claim about the UI, so check the UI. If
    the Pulse notice were ever removed from the page, the reason for the short
    in-prose caveat would be gone with it and this test should fail loudly."""
    with open("static/index.html", encoding="utf-8") as fh:
        index = fh.read()
    with open("static/app.js", encoding="utf-8") as fh:
        app = fh.read()
    assert 'id="pulse-legal"' in index
    assert "LEGAL.areas.pulse" in app
    assert "Not financial advice." in app


# ------------------------------------------------- the limits that must remain

def test_the_tone_pass_did_not_drop_the_data_limits():
    """Delayed prices, the flow proxy and the dealer assumption are the three
    facts that make every number on screen an approximation. They were in the
    prompt before the rewrite and they have to be in it after."""
    assert "delayed roughly 15 minutes" in SYSTEM
    assert "proxy" in SYSTEM
    assert "short customer calls and long customer puts" in SYSTEM


def test_the_tone_pass_did_not_drop_the_line_between_analysis_and_instruction():
    """A warmer voice is closer to a friend giving advice, which is the one thing
    Pulse must not become. The distinction is the reason the app can exist
    without a licence, so it is asserted rather than assumed."""
    assert "direction versus instruction" in SYSTEM
    assert "not yours" in SYSTEM
    for banned in ("treat this as", "you want to be", "wait for"):
        assert banned in SYSTEM, banned


def test_the_tone_pass_did_not_license_a_forecast():
    assert "never imply certainty about the future" in SYSTEM
    assert "supports a lean, never a forecast" in SYSTEM


def test_the_tone_pass_did_not_drop_the_ban_on_invented_figures():
    """The most damaging thing a friendly voice could do is sound confident about
    a strike it does not have."""
    assert "never do is state a specific figure you do not have" in SYSTEM
    assert "fabrication" in SYSTEM


def test_the_tone_pass_did_not_soften_the_no_sizing_rule():
    assert "no position sizing" in SYSTEM
    assert "size accordingly" in SYSTEM, (
        "the named examples of instruction-shaped copy have to survive")


# ----------------------------------------------------------------- punctuation

def test_no_prompt_contains_an_em_dash():
    """FORMAT_PROMPT tells Pulse not to use em dashes and the house style bans
    them in user-facing copy, yet seven examples inside the prompts used one.
    A rule with a counter-example next to it teaches the counter-example: the
    model imitates the prose it is shown far more reliably than it obeys a
    sentence about punctuation. Comments are exempt, which is why this reads the
    constants and not the file."""
    for name, text in prompt_constants().items():
        assert "—" not in text, name


def test_the_em_dash_instruction_is_still_there():
    assert "do not use em dashes" in FORMAT


def test_the_jargon_rule_no_longer_recommends_a_dash():
    """It read "in parentheses or after a dash", two sections above the rule
    forbidding dashes."""
    assert "after a dash" not in SYSTEM
    assert "in the sentence right after" in SYSTEM


# ------------------------------------------------------------------- the lens

def test_the_compressed_lens_does_not_duplicate_the_base_voice():
    """It used to differentiate on being "informal", which the base voice now is,
    leaving a menu entry that selected nothing. It differentiates on length."""
    lens = flat(ai.PERSONAS["retail"]["prompt"])
    assert "what this lens changes is length" in lens
    assert "no opening hook" in lens


def test_the_compressed_lens_still_translates_its_terms():
    """Compression is the one lens that could reasonably drop the in-line
    glossing, and dropping it would make the shortest answers the least
    readable."""
    lens = flat(ai.PERSONAS["retail"]["prompt"])
    assert "still translate a term" in lens


def test_every_lens_label_is_still_a_description():
    """"Straight to it" replaced "Plain English". Same contract as before: the
    label says what comes back."""
    for key, val in ai.PERSONAS.items():
        assert val["label"], key
        assert "," not in val["label"], key
