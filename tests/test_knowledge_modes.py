"""Knowledge levels: five positions, one preference, and the facts never move (Phase 05 rewrite of the ladder tests).

The earlier history, kept because its reasons still hold:

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


# ------------------------------------------------------------- the levels

def test_the_five_levels_exist_in_slider_order():
    """The owner's five (directive 05, 2026-10-29), New to Markets to Expert, one slider position each."""
    assert knowledge.ORDER == ["new", "beginner", "intermediate", "advanced", "expert"]
    assert set(knowledge.ORDER) == set(knowledge.MODES)
    assert [knowledge.MODES[k]["position"] for k in knowledge.ORDER] == [1, 2, 3, 4, 5]


def test_the_labels_are_the_owners_five():
    """The labels used to describe the explanation rather than the reader ("Simple", never "Beginner"). The owner's
    directive names the five levels, so its words are the labels now (DECISIONS D-026)."""
    assert [knowledge.MODES[k]["label"] for k in knowledge.ORDER] == [
        "New to Markets", "Beginner", "Intermediate", "Advanced", "Expert"]


def test_classics_panel_ladder_does_not_move():
    """Classic's layouts read these integers. The two levels that replace Simple share its rung, so nobody's Classic
    page moved when the five arrived; Intermediate sits where Financially Literate did."""
    assert [knowledge.MODES[k]["level"] for k in knowledge.ORDER] == [0, 0, 1, 2, 3]


def test_the_recommended_default_is_the_middle():
    """New to Markets as the default would talk down to most readers; Expert would explain nothing."""
    assert knowledge.DEFAULT_MODE == "intermediate"


def test_an_unknown_level_falls_back_and_the_old_ids_map():
    """The value arrives from localStorage, which the reader can edit, from a request body, which anybody can, and
    from pages loaded before Phase 05, which send the old ids."""
    for bad in ("enormous", "", None, "PRO", "novice"):
        assert knowledge.normalise(bad) == knowledge.DEFAULT_MODE, bad
        assert not knowledge.known(bad), bad
    assert knowledge.normalise("Expert") == "expert", "case only"
    for old, new in (("simple", "new"), ("literate", "intermediate"), ("professional", "expert"), ("adaptive", "intermediate"), ("advanced", "advanced")):
        assert knowledge.normalise(old) == new and knowledge.known(old), old


# ----------------------------------------------- what a level may never change

def test_every_level_carries_the_invariant():
    """One sentence, appended in one place, so no level can be written without it (directive 05, section 5)."""
    inv = knowledge.INVARIANT.lower()
    for phrase in ("every figure, calculation and date is the same at every level", "every source is named the same way",
                   "every caveat", "missing or unknown", "the advice policy in these instructions applies unchanged",
                   "never makes the facts softer", "never drops a caveat"):
        assert phrase in inv, phrase
    for key in knowledge.ORDER:
        block = knowledge.prompt_for(key)
        assert block.startswith(knowledge.MODES[key]["prompt"]) and block.endswith(knowledge.INVARIANT), key


def test_no_level_is_allowed_to_soften_the_facts():
    """New to Markets is the level most able to lose a caveat, because softening is what it sounds like it licenses."""
    new = knowledge.MODES["new"]["prompt"].lower()
    assert "never state a number you do not have" in new
    assert "delayed data and inferred flow" in new
    assert "not softer facts" in new


def test_the_densest_level_still_labels_an_inference():
    """Expert drops the definitions, which is the point, and could as easily drop the line between measured and
    inferred. That line is the one thing this register must keep: the instruction, not just the words."""
    pro = knowledge.MODES["expert"]["prompt"].lower()
    for word in ("proxy", "measured", "inferred"):
        assert word in pro, word
    assert "keep it labelled" in pro and "label it in a word" in pro


def test_the_levels_follow_the_directives_descriptions():
    """Directive 05 section 1, word for word where it names the register."""
    want = {"new": ("basic everyday english", "define every financial term"), "beginner": ("simple explanations", "introduce the essential terms"),
            "intermediate": ("balanced financial vocabulary",), "advanced": ("professional technical language", "deeper analytical reasoning"),
            "expert": ("concise, precise financial research language", "advanced metrics where they are relevant")}
    for key, phrases in want.items():
        text = knowledge.MODES[key]["prompt"].lower()
        for phrase in phrases:
            assert phrase in text, (key, phrase)


def test_the_catalogue_publishes_what_it_cannot_change_and_one_fact_five_ways():
    """The slider's promise and its previews come from one place. Every preview explains the same illustration, so the
    number in it is the same at every level: the level changes the words around the figure, never the figure."""
    cat = knowledge.catalogue()
    assert cat["changes"] and any("figures" in c for c in cat["never_changes"])
    assert cat["preview_fact"].startswith("A company whose shares trade at 30 times its earnings")
    assert [m["id"] for m in cat["modes"]] == knowledge.ORDER and cat["default"] == "intermediate"
    assert cat["legacy"] == knowledge.LEGACY
    for m in cat["modes"]:
        assert m["preview"] and "30" in m["preview"], m["id"]
    assert len({m["preview"] for m in cat["modes"]}) == 5, "five ways of saying it, not one"


def test_the_level_is_the_readers_own_and_never_read_from_the_question():
    """Adaptive, which read each question, is not one of the five positions (D-027)."""
    for mode in knowledge.ORDER:
        for q in ("what is a P/E ratio", "is the 31x forward multiple supported by the skew", "", None):
            assert knowledge.resolve_for_answer(mode, q) == mode
    assert knowledge.resolve_for_answer("adaptive", "what is a P/E ratio") == "intermediate"


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
    """The level decides what a view opens with, never what it may contain: a
    panel above it starts collapsed, and one the reader opened stays open."""
    fn = APP_JS.split("function makePanelsCollapsible(", 1)[1].split("\nfunction ", 1)[0]
    assert fn.index("knowledgeLevel()") < fn.index("hasOwnProperty.call(saved, id) ? !!saved[id]")
    hidden = APP_JS.split("function panelIsHidden(", 1)[1].split("\n}", 1)[0]
    assert "knowledgeLevel" not in hidden, "the level hides nothing"

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
    """Classic copies five integers because density is decided on the first paint, before any fetch has answered, and
    both apps copy the old ids' map. Two records of one fact drift, so they are compared here."""
    table = COMPONENT.split("var LEVELS = {", 1)[1].split("};", 1)[0]
    client = {k: int(v) for k, v in re.findall(r"(\w+):\s*(\d)", table)}
    server = {k: v["level"] for k, v in knowledge.MODES.items()}
    assert client == server, (client, server)
    legacy = COMPONENT.split("var LEGACY = {", 1)[1].split("};", 1)[0]
    assert dict(re.findall(r"(\w+): '(\w+)'", legacy)) == knowledge.LEGACY
    v2 = open("static/v2/js/core/prefs.js", encoding="utf-8").read()
    # v2 offers three since 2026-11-09 and maps every older id onto them; the server's five stay as wording tiers
    assert "export const LEVEL_IDS = ['beginner', 'intermediate', 'advanced'];" in v2
    assert "const LEGACY = { new: 'beginner', expert: 'advanced', simple: 'beginner', literate: 'intermediate', professional: 'advanced', adaptive: 'intermediate' };" in v2
    assert knowledge.THREE == ["beginner", "intermediate", "advanced"]
    assert "const DEFAULT_MODE = 'intermediate';" in v2 and "var DEFAULT_MODE = 'intermediate';" in COMPONENT


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
