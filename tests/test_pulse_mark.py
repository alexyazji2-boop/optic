"""Pulse has a mark. One drawing, three sizes.

It had a face for a while -- a snowman, through several passes: a body, then
the logo's eyes, then a redraw to stop the shapes overlapping. The verdict on
it was that it looked creepy, and a character at 104px keeps inviting that
judgement however it is drawn. So the mascot is gone and the empty state
carries the same circle-and-waveform glyph that is already in the button
above it and the phone tab below it.

That is also the cheaper thing to keep honest. One drawing has one set of
colours, one animation and one place to change it; a mascot needs a
personality maintained across every size it appears at.

The waveform is the fixed part, because it is the name. It is the same idea
the brand mark draws -- a chart line through an eye -- so the two read as one
family rather than two logos.
"""

from __future__ import annotations

import re

APP = open("static/app.js", encoding="utf-8").read()
CSS = open("static/styles.css", encoding="utf-8").read()
HTML = open("static/index.html", encoding="utf-8").read()


def _fn(name):
    start = APP.index("function %s(" % name)
    return APP[start:APP.index("\n}", start)]


def test_there_is_one_mark_and_the_mascot_is_gone():
    """Gone, not merely unused. Dead code that renders nothing is worse than
    absent code: the next reader has to work out whether it is live."""
    assert "function pulseMarkHTML(" in APP
    assert "pulseMascotHTML" not in APP
    for leftover in ("pulse-face", "pulse-eye", "pulse-collar", "pulse-smile"):
        assert leftover not in APP, leftover + " survived the removal"
        assert leftover not in CSS, leftover + " survived in the stylesheet"
    assert "pulse-blink" not in CSS, "the blink animated nothing"


def test_the_small_places_get_the_reduced_mark():
    """The button, the panel header and the phone tab are all under 24px."""
    mount = _fn("mountPulseMarks")
    assert "'pulse-mark-btn', 'pulse-mark-head'" in mount
    assert "pulseMarkHTML('pulse-glyph-sm')" in mount
    # Both hosts exist, or the mount writes into nothing.
    assert 'id="pulse-mark-btn"' in HTML and 'id="pulse-mark-head"' in HTML
    # And it is actually called at boot.
    assert "\n  mountPulseMarks();" in APP
    # The phone tab too, which used a four-pointed star standing in for a mark
    # that did not exist.
    assert "t.mark === 'pulse' ? pulseMarkHTML('pulse-glyph-sm') : t.icon" in APP
    assert "'&#10022;'" not in APP, "the stand-in star is gone"


def test_the_heartbeat_stays_sharp():
    """The friendliness comes from the eyes and the fill, not from rounding
    the trace. A draft that curved it read as a moustache at 110px: the angles
    are the only reason it reads as a heartbeat at all. The corners lift
    instead, which turns the mouth up without touching the spikes."""
    fn = _fn("pulseMarkHTML")
    after = fn.split('class="pulse-trace"', 1)[1]
    d = re.search(r'd="([^"]+)"', after).group(1)
    assert re.fullmatch(r"[\sMmLlHhVvZz0-9.\-]+", d), \
        "the heartbeat has a curve command in it: {!r}".format(d)


def test_the_marks_carry_no_hex():
    """Tokens or currentColor. A drawing is exactly the kind of asset that
    arrives with three brand hexes baked into it."""
    fn = _fn("pulseMarkHTML")
    assert not re.search(r"#[0-9a-fA-F]{3,8}", fn), fn


def test_clearing_a_conversation_redraws_the_empty_state():
    """Reported as "where is the pulse snowman" — and he was nowhere, because
    the panel had no empty state at all.

    `renderPulseEmpty` runs at boot and from `updateChatContext`. Starting a
    new conversation emptied `#chat-log` and called neither, so the panel went
    blank: no greeting, no starter cards, no mark, and no way in until a
    ticker changed and updateChatContext happened to run. Measured on
    production: `#chat-log` present and completely empty, and calling
    `renderPulseEmpty()` by hand drew it straight back.

    Found while chasing "where is the pulse snowman". The snowman has since
    been removed for looking creepy, and the bug it exposed outlived it --
    what goes in that space changed, the fact that something has to be drawn
    there did not.

    Cheap to call unconditionally — it returns early when the log holds real
    messages, which immediately after that line it cannot."""
    fn = APP[APP.index("function pulseNewConversation() {"):]
    fn = fn[:fn.index("\n}")]
    assert "log.innerHTML = ''" in fn
    assert "renderPulseEmpty()" in fn, \
        "an emptied log is the empty state and has to be drawn as one"
    assert fn.index("log.innerHTML = ''") < fn.index("renderPulseEmpty()"), \
        "drawing before clearing would be wiped by the clear"


def test_the_reduced_mark_is_one_colour_throughout():
    """It sits on the primary button, where the only pair that works is white
    on brand. A two-tone glyph on a brand fill reads as a rendering fault."""
    fn = _fn("pulseMarkHTML")
    assert fn.count("currentColor") >= 2
    assert "var(--brand)" not in fn


def test_only_the_trace_moves_and_reduced_motion_stops_it():
    """A mark that scales in the corner of a button is motion nobody asked
    for, which is what the bullet it replaced used to do. The trace redraws
    itself with the brand mark's own idiom instead."""
    assert ".pulse-trace {" in CSS
    block = CSS.split(".pulse-trace {", 1)[1]
    block = block[:block.index("}")]
    assert "stroke-dasharray: 100" in block
    assert "animation: pulse-trace-draw" in block
    assert 'pathLength="100"' in _fn("pulseMarkHTML"), \
        "without it the dash maths has to know the path's real length"
    reduced = CSS.split("@media (prefers-reduced-motion: reduce) {", 1)
    assert any(".pulse-trace { animation: none" in chunk for chunk in reduced[1:])
    # The MARK no longer scales. The keyframe itself stays: `.ses-dot.p-regular`
    # and a refreshing indicator app.js sets inline both still name it, and
    # deleting it took their animation away silently -- a keyframe that does
    # not exist does not error, it just never runs.
    assert "animation: pulse-beat" not in CSS.split(".pulse-glyph")[0].split(".pulse-mark {")[-1][:400]
    assert "@keyframes pulse-beat" in CSS, "two other things still name it"
    assert ".ses-dot.p-regular { animation: pulse-beat" in CSS


def test_the_copy_does_not_mention_what_a_message_costs():
    """Asked for directly: the reader is told what they get and what it takes,
    not what it costs the person running it. The reasoning still lives in the
    comments, where it is for whoever changes the number next."""
    server = open("app/main.py", encoding="utf-8").read()
    import ast
    tree = ast.parse(server)
    strings = [n.value for n in ast.walk(tree)
               if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    # Docstrings and comments are exempt; only what a caller can be shown.
    said = [t for t in strings if "costs the operator" in t or "costs the" in t
            and "money" in t]
    assert not said, said
    # And the client's own sentence.
    reason = _fn("pulseBlockedReason")
    assert "costs" not in reason


def test_the_empty_state_carries_the_optic_aperture():
    """The waveform is drawn for 17px. At 76 it reads thin, and it is the
    Pulse glyph rather than the mark the product is named for -- so the panel's
    one large graphic is now the aperture the header and the home page carry.

    Rendered through `opticMarkHTML`, not pasted: there were already two
    hand-written copies of those three paths and a third would be the one that
    drifts. tests/test_brand_mark.py compares the generated drawing against
    index.html's static copy, which is the only pair that still can."""
    starters = APP[APP.index("function pulseStarters("):]
    starters = starters[:starters.index("\nfunction ")]
    assert "opticMarkHTML('pulse-logo')" in starters
    assert "pulseMarkHTML(" not in starters, "the waveform is the small mark"
    # One drawing: the aperture path appears once in the whole file.
    assert APP.count("M2.6 16C6.3 8.9") == 1, \
        "the aperture is hand-copied somewhere again"


def test_the_mark_in_the_panel_does_not_animate():
    """The header mark blinks everywhere except Home and the home logo irises
    open on arrival -- both are arrival. This one sits above four cards a
    reader is reading, and motion beside text being read is motion nobody
    asked for."""
    block = CSS.split("\n.pulse-logo {", 1)[1]
    block = block[:block.index("}")]
    assert "animation" not in block
    # And it inherits none, because the animated rules are keyed per prefix.
    assert ".pulse-logo-eye" not in CSS and ".pulse-logo-line" not in CSS
