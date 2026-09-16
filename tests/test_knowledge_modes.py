"""Knowledge modes: one control, three axes.

Before this there were two controls for one question. `uiMode` was Pro / Simple
and hid panels; `PERSONAS` held six lenses, one of which ("Straight to it") was
not a lens at all but a register. A reader could hold Professional density and a
compressed voice at once and get a page arguing with itself.

A lens and a level are different questions. "Whose judgement do I want" is a
lens; "how much do I already know" is a level, and the level is the one that
should decide how everything is worded. So the registers moved to
app/knowledge.py and the lenses stayed in app/ai.py.

Half of this file guards the boundary the modes must not cross: presentation
changes, figures do not. "Explain it simply" is the rung most able to lose a
caveat, because softening is exactly what it sounds like it licenses.
"""

from __future__ import annotations

import json
import re

from app import ai, knowledge

APP_JS = open("static/app.js", encoding="utf-8").read()
COMPONENT = open("static/components/knowledge.js", encoding="utf-8").read()
INDEX = open("static/index.html", encoding="utf-8").read()
STYLES = open("static/styles.css", encoding="utf-8").read()


# ------------------------------------------------------------- the ladder

def test_the_five_rungs_exist_in_order():
    assert knowledge.ORDER == ["simple", "literate", "advanced",
                               "professional", "adaptive"]
    assert set(knowledge.ORDER) == set(knowledge.MODES)


def test_the_levels_are_monotonic_across_the_four_real_rungs():
    """Adaptive is not a rung, it is a choice not to pick one, so it sits at the
    end of the menu and shares Financially Literate's density."""
    rungs = [knowledge.MODES[k]["level"] for k in
             ("simple", "literate", "advanced", "professional")]
    assert rungs == [0, 1, 2, 3], rungs
    assert knowledge.MODES["adaptive"]["level"] == knowledge.LEVEL_LITERATE


def test_the_recommended_default_is_the_middle():
    """Simple as the default would talk down to most readers; Professional would
    hide nothing and explain nothing."""
    assert knowledge.DEFAULT_MODE == "literate"


def test_an_unknown_mode_falls_back_rather_than_raising():
    """The value arrives from localStorage, which the reader can edit, and from
    a request body, which anybody can. An unknown mode still has to render
    something."""
    for bad in ("enormous", "", None, "PRO", "beginner"):
        assert knowledge.normalise(bad) == knowledge.DEFAULT_MODE, bad
    assert knowledge.normalise("Professional") == "professional", "case only"


# ----------------------------------------------- what a mode may never change

def test_no_rung_is_allowed_to_soften_the_facts():
    """The load-bearing contract. A mode may hide a panel and simplify a
    sentence; it may not round a number or drop a caveat, or "I am new to this"
    becomes a way of getting a friendlier answer."""
    simple = knowledge.MODES["simple"]["prompt"].lower()
    assert "never state a number you do not have" in simple
    assert "delayed data and inferred flow" in simple
    assert "not that the facts are softer" in simple


def test_the_densest_rung_still_labels_an_inference():
    """Professional drops the definitions, which is the point, and could just as
    easily drop the line between measured and inferred. That line is the one
    thing this register must keep."""
    pro = knowledge.MODES["professional"]["prompt"].lower()
    for word in ("proxy", "measured", "inferred"):
        assert word in pro, word
    # And the *instruction*, not just the vocabulary. The first version of this
    # checked only the three words, and a mutation that deleted "keep it
    # labelled" passed: the rest of the sentence still mentioned all three
    # while no longer telling the model to do anything about them.
    assert "keep it labelled" in pro
    assert "label it in a word" in pro


def test_the_catalogue_publishes_what_it_cannot_change():
    """The menu's promise and the behaviour come from one place. A selector
    claiming to change density while the density table disagreed would be a
    split nothing reports."""
    cat = knowledge.catalogue()
    assert cat["changes"] and cat["never_changes"]
    assert any("figures" in c for c in cat["never_changes"])


def test_no_label_categorises_the_reader():
    """The labels say what the reader gets, never what the product thinks of
    them: "Simple" describes the explanation where "Beginner" would describe the
    person. Nothing in the interface calls anybody a novice."""
    # The words that describe a *person*, not the words that describe what is
    # assumed. "Assumes the basics" is about the knowledge and is fine; "Basic
    # User" is about the reader and is not. The first draft of this banned
    # "basic" outright and failed on the honest sentence.
    banned = ("beginner", "basic user", "novice", "easy mode", "dumb",
              "for experts", "power user")
    for key, mode in knowledge.MODES.items():
        text = (mode["label"] + " " + mode["blurb"] + " " + mode["tagline"]).lower()
        for word in banned:
            assert word not in text, "%s says %r" % (key, word)
    # And the labels themselves are the five the brief specifies, none of which
    # names a kind of person.
    assert [knowledge.MODES[k]["label"] for k in knowledge.ORDER] == [
        "Simple", "Financially Literate", "Advanced", "Professional", "Adaptive"]


# ------------------------------------------------------------- adaptive only

def test_only_adaptive_reads_the_question():
    """A reader who picked Professional did not ask to be second-guessed by a
    keyword match."""
    for mode in ("simple", "literate", "advanced", "professional"):
        assert knowledge.resolve_for_answer(mode, "what is a P/E ratio") == mode


def test_adaptive_hears_a_request_to_be_taught():
    for q in ("What is a P/E ratio?", "explain gamma exposure",
              "why does the dollar matter", "in simple terms, what is IV"):
        assert knowledge.resolve_for_answer("adaptive", q) == "simple", q


def test_adaptive_hears_fluency_and_does_not_explain_it_back():
    """"Never explain a term the reader has just used correctly" is the rule
    this implements."""
    q = "is the 31x forward multiple supported by the revenue trajectory"
    assert knowledge.resolve_for_answer("adaptive", q) == "advanced"
    assert knowledge.resolve_for_answer("adaptive", "what's the term structure doing") \
        in ("simple", "advanced")


def test_adaptive_with_nothing_to_go_on_lands_on_the_default():
    """A reader who has asked nothing has given nothing to infer from."""
    for q in ("", None, "NVDA"):
        assert knowledge.resolve_for_answer("adaptive", q) == knowledge.DEFAULT_MODE


def test_adaptive_never_writes_the_readers_mode():
    """It changes the wording of one answer. The stored preference is the
    reader's and is not silently reassigned."""
    fn = knowledge.resolve_for_answer.__doc__ or ""
    assert "changes nothing about the reader's chosen mode" in \
        knowledge.resolve_for_answer.__code__.co_consts[0] or "adaptive" in fn.lower()


# -------------------------------------------------- the lens / level split

def test_the_register_left_the_lenses():
    """"Straight to it" was a register among five lenses."""
    assert "retail" not in ai.PERSONAS
    assert len(ai.PERSONAS) == 5


def test_no_lens_sets_a_register():
    for key, val in ai.PERSONAS.items():
        low = val["prompt"].lower()
        for register in ("shortest sentence", "no opening hook", "fewer words"):
            assert register not in low, "%s is setting a register" % key


def test_the_level_and_the_lens_are_separate_prompt_blocks():
    """Level before lens: the lens decides which figures lead and the level
    decides how they are worded, so the lens is the more specific instruction
    and reads last."""
    block = APP_JS  # the composition is server-side; read it there
    src = open("app/ai.py", encoding="utf-8").read()
    compose = src[src.index('"system": ['):]
    compose = compose[:compose.index("],")]
    assert compose.index("level_prompt") < compose.index("persona_prompt")


# ------------------------------------------------------------- the density

def test_density_has_four_rungs_not_two():
    for table in ("PANELS_SIMPLE_HIDES", "PANELS_ADVANCED", "PANELS_DENSE"):
        assert "const %s = {" % table in APP_JS, table
    fn = APP_JS.split("function panelMinLevel(", 1)[1].split("\n}", 1)[0]
    for level in ("return 3", "return 2", "return 1", "return 0"):
        assert level in fn, level


def test_the_readers_own_choice_still_beats_the_level():
    """The level decides what a view opens with, never what it may contain."""
    fn = APP_JS.split("function panelIsHidden(", 1)[1].split("\n}", 1)[0]
    assert fn.index("hasOwnProperty.call(chosen, id)") < fn.index("knowledgeLevel()")


def test_the_two_original_rungs_render_exactly_as_before():
    """Nobody's page moved when this shipped."""
    fn = APP_JS.split("function uiMode() {", 1)[1].split("\n}", 1)[0]
    assert "knowledgeLevel() >= 2 ? 'pro' : 'simple'" in fn


def test_nothing_that_states_a_limitation_is_ever_gated():
    """Every panel says what it cannot tell you, and a rung that hid those
    would be hiding the caveats rather than the complexity."""
    for table in ("PANELS_SIMPLE_HIDES", "PANELS_DENSE"):
        block = APP_JS.split("const %s = {" % table, 1)[1].split("\n};", 1)[0]
        for banned in ("caveat", "method", "disclaimer", "what this cannot"):
            assert banned not in block.lower(), "%s gates %r" % (table, banned)


# --------------------------------------------------- client / server agreement

def test_the_clients_level_table_agrees_with_the_server():
    """The component copies five integers because density is decided on the
    first paint, before any fetch has answered. Two records of one fact drift,
    and the symptom would be panels at a density the selector does not claim."""
    table = COMPONENT.split("var LEVELS = {", 1)[1].split("};", 1)[0]
    client = {k: int(v) for k, v in re.findall(r"(\w+):\s*(\d)", table)}
    server = {k: v["level"] for k, v in knowledge.MODES.items()}
    assert client == server, (client, server)


def test_the_component_copies_only_the_levels():
    """Labels, blurbs and registers have exactly one copy, on the server."""
    # Comments are stripped: this file's own rationale names the rungs, and a
    # contract that reads the raw source cannot tell an explanation from a copy.
    code = re.sub(r"/\*.*?\*/", " ", COMPONENT, flags=re.S)
    code = re.sub(r"(?<!:)//[^\n]*", " ", code)
    for mode in knowledge.MODES.values():
        assert mode["label"] not in code, mode["label"]
        assert mode["blurb"][:30] not in code
        assert mode["prompt"][:40] not in code


# ------------------------------------------------------------- the selector

def test_the_selector_is_not_buried_in_settings():
    """The brief is explicit: reachable from Ask Optic. It renders into the
    Pulse header beside the lens."""
    fn = APP_JS.split("function renderPersonaPicker() {", 1)[1].split("\n}", 1)[0]
    assert "knowledgeSelectorHTML(" in fn
    # Mode first, then persona. The marker used to be `pulse-persona-lab`, the
    # class on a label that sat OUTSIDE the persona box; the label moved inside
    # so both controls wear the same `.oc-field`, and the class went with it.
    assert fn.index("knowledgeSelectorHTML(") < fn.index("pp-field")


def test_the_selector_is_one_chip_not_five_segments():
    """Just as explicit: it must never dominate the interface."""
    fn = COMPONENT.split("function selectorHTML(", 1)[1].split("\n  }", 1)[0]
    assert "km-btn" in fn
    assert "o.open ? menuHTML() : ''" in fn.replace("(", "").replace(")", "") \
        or "open ? menuHTML()" in fn


def test_the_menu_closes_on_an_outside_click_and_on_escape():
    """A menu that can only be closed by the control that opened it is a trap,
    which is what the section dropdowns taught."""
    assert "!evt.target.closest('[data-km-root]')" in APP_JS
    assert re.search(r"key === 'Escape' && kmOpen", APP_JS)


def test_the_attribute_does_not_collide_with_the_settings_toggle():
    """`data-set-mode` already belongs to the Pro / Simple control. A data-*
    collision does not error, it lets the wrong handler match first and swallow
    the click, which is how a dead control happens in this codebase."""
    assert "data-km-pick" in APP_JS and "data-km-toggle" in APP_JS
    assert "data-set-mode=\"simple\"" not in COMPONENT


def test_the_component_loads_before_app_js():
    """It exposes what app.js consumes, the same way charts.js does, so order
    is the contract."""
    assert INDEX.index("components/knowledge.js") < INDEX.index("app.js?v=")


# ------------------------------------------------------------- the request

def test_the_chat_request_carries_the_level_and_the_lens():
    assert re.search(r"mode: window\.OpticKnowledge \? window\.OpticKnowledge\.mode\(\)", APP_JS)
    assert "persona: pulsePersona," in APP_JS


def test_the_server_normalises_what_arrives():
    src = open("app/main.py", encoding="utf-8").read()
    assert 'knowledge_mod.normalise(payload.get("mode"))' in src


def test_the_mode_and_persona_controls_wear_one_box():
    """They sit side by side and have to read as one pair. They did not:
    measured at 47px tall on --surface-2 with --border next to 44px on
    --surface with --border-strong, and the label was INSIDE the first box and
    outside the second, so one looked like a designed control and the other like
    a bare form field dropped beside it.

    Shared rather than copied. Two lookalike rules drift the first time one is
    touched, which is the fault behind most of this session's other fixes.
    """
    assert ".oc-field {" in STYLES
    # The knowledge component's button wears it...
    assert 'class="km-btn oc-field"' in COMPONENT
    # ...and so does the persona field.
    assert 'class="pp-field oc-field"' in APP_JS
    # The box lives on .oc-field, so .km-btn must not redeclare it.
    rule = STYLES[STYLES.index("\n.km-btn {"):]
    rule = rule[:rule.index("}")]
    for prop in ("background", "border-radius", "padding"):
        assert prop not in rule, "%s belongs to .oc-field now" % prop


def test_the_persona_label_is_inside_its_box():
    """`.pulse-persona-lab` was a label sitting outside the box. It moved
    inside, which is what makes the two controls match, and the class went with
    it."""
    # The RULE, not the bare name: the comment recording the removal names the
    # thing removed, so a contract reading the raw file cannot tell them apart.
    # Third time this session.
    assert ".pulse-persona-lab {" not in STYLES
    assert 'class="pulse-persona-lab"' not in APP_JS
    fn = APP_JS.split("function renderPersonaPicker() {", 1)[1].split("\n}", 1)[0]
    # The label comes first inside the box, then the chosen value, which is the
    # order the mode chip uses. `id="pulse-persona"` was the marker until the
    # <select> was replaced by a button and a menu; see
    # test_the_persona_menu_is_the_same_menu.
    assert fn.index('class="pp-field oc-field"') < fn.index('class="pp-eyebrow"')
    assert fn.index('class="pp-eyebrow"') < fn.index('class="pp-now"')


def test_the_persona_menu_is_the_same_menu():
    """The boxes matched; the menus did not. One was a custom list with a label,
    a blurb and a footer stating what the setting changes; the other was
    whatever the operating system draws for a <select>: labels only, no blurbs,
    no promise, and no relation to the app's type or colour. Two controls side
    by side cannot look alike closed and unlike the moment either is opened.

    Aliased selectors, not a second copy of sixty lines.
    """
    assert "function personaMenuHTML() {" in APP_JS
    for sel in (".oc-menu", ".oc-opt", ".oc-opt-label", ".oc-opt-blurb",
                ".oc-foot", ".oc-foot-h"):
        assert sel + ",\n" in STYLES or sel + " {" in STYLES, sel
    fn = APP_JS.split("function personaMenuHTML() {", 1)[1].split("\n}", 1)[0]
    assert "oc-opt-label" in fn and "oc-opt-blurb" in fn
    assert "oc-foot" in fn, "the footer states what the choice changes"
    # And it closes the way every other menu here does.
    assert "data-pp-root" in APP_JS and "Escape" in APP_JS


def test_choosing_a_persona_actually_changes_the_persona():
    """It did not. `pulsePersona` was assigned in exactly two places, both at
    load -- once from localStorage, once from the server default -- and nothing
    read the <select>: no change listener touched it and
    `setItem(PULSE_PERSONA_KEY, ...)` appeared nowhere in the file. The key was
    read on every load and never written, and `persona: pulsePersona` went to
    /api/chat as the default every time.

    So picking "Devil's advocate" showed "Devil's advocate" in the box and Pulse
    answered as the neutral analyst. It looked alive because a native <select>
    updates its own displayed value whether or not anything is listening, which
    is the most convincing kind of dead control.
    """
    assert "function setPersona(id) {" in APP_JS
    fn = APP_JS.split("function setPersona(id) {", 1)[1].split("\n}", 1)[0]
    assert "pulsePersona = id;" in fn
    assert "setItem(PULSE_PERSONA_KEY, id)" in fn, "the choice has to survive a reload"
    assert "renderPersonaPicker()" in fn
    # The menu has to reach it.
    assert "setPersona(pick.dataset.ppPick)" in APP_JS


def test_the_persona_promise_comes_from_the_server():
    """The menu's footer and the behaviour need one source. The distinction was
    stated only in a comment in app/ai.py, where no reader of the app could see
    it."""
    ai = open("app/ai.py", encoding="utf-8").read()
    main = open("app/main.py", encoding="utf-8").read()
    assert "PERSONA_CHANGES" in ai and "PERSONA_NEVER_CHANGES" in ai
    assert '"changes": ai.PERSONA_CHANGES' in main
    assert '"never_changes": ai.PERSONA_NEVER_CHANGES' in main
    assert "PULSE_PERSONA_NOTE" in APP_JS
