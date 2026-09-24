"""Pulse has a face.

Two drawings rather than one, and the split is measured rather than
stylistic. Rendered at 16 and 20px the mascot's eyes stop resolving and the
whole thing turns to mush, while the circle and the waveform stay legible all
the way down. So the face is used where there is room for it -- the panel's
empty state, at 76px -- and a reduced mark everywhere else: the top bar
button, the panel header and the phone tab.

The waveform is the fixed part of both, because it is the name. It is also
the same idea the brand mark draws, a chart line through an eye, so the two
read as one family rather than two logos.
"""

from __future__ import annotations

import re

APP = open("static/app.js", encoding="utf-8").read()
CSS = open("static/styles.css", encoding="utf-8").read()
HTML = open("static/index.html", encoding="utf-8").read()


def _fn(name):
    start = APP.index("function %s(" % name)
    return APP[start:APP.index("\n}", start)]


def test_there_are_two_marks_and_both_are_drawn_here():
    assert "function pulseMarkHTML(" in APP
    assert "function pulseMascotHTML(" in APP


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


def test_the_face_goes_where_there_is_room_and_only_there():
    """A first draft added a second greeting to `#chat-log`, which rendered
    under the one `pulseStarters` has always drawn -- so the panel greeted a
    reader twice. There is one empty state and the face belongs to it."""
    starters = _fn("pulseStarters")
    assert "pulseMascotHTML('pulse-face-lg')" in starters
    assert APP.count("pulseMascotHTML(") == 2, "definition plus exactly one caller"
    assert "chat-empty" not in APP, "the duplicate greeting is gone"
    assert "renderChatEmpty" not in APP


def test_the_heartbeat_stays_sharp():
    """The friendliness comes from the eyes and the fill, not from rounding
    the trace. A draft that curved it read as a moustache at 110px: the angles
    are the only reason it reads as a heartbeat at all. The corners lift
    instead, which turns the mouth up without touching the spikes."""
    # The reduced mark only. The figure carries no trace any more -- it was a
    # mouth, then a belly line, and it was asked to go.
    fn = _fn("pulseMarkHTML")
    after = fn.split('class="pulse-trace"', 1)[1]
    d = re.search(r'd="([^"]+)"', after).group(1)
    assert re.fullmatch(r"[\sMmLlHhVvZz0-9.\-]+", d), \
        "the heartbeat has a curve command in it: {!r}".format(d)
    assert 'class="pulse-trace"' not in _fn("pulseMascotHTML"), \
        "the line through him is back"


def test_the_marks_carry_no_hex():
    """Tokens or currentColor. A mascot is exactly the kind of asset that
    arrives with three brand hexes baked into it."""
    for fn in (_fn("pulseMarkHTML"), _fn("pulseMascotHTML")):
        assert not re.search(r"#[0-9a-fA-F]{3,8}", fn), fn


def test_the_reduced_mark_is_one_colour_throughout():
    """It sits on the primary button, where the only pair that works is white
    on brand. A two-tone glyph on a brand fill reads as a rendering fault."""
    fn = _fn("pulseMarkHTML")
    assert fn.count("currentColor") >= 2
    assert "var(--brand)" not in fn


def test_the_face_uses_the_palette_for_its_warmth():
    """The soft body is the brand token at low opacity rather than a tint
    colour, because the palette has no tint slot and inventing a hex for one
    is what the design system exists to stop."""
    fn = _fn("pulseMascotHTML")
    # On the group that holds the body, the head, the arms and the feet, so
    # one declaration covers every part of him.
    assert re.search(r'fill="var\(--brand\)" fill-opacity="0\.\d+"', fn)
    assert 'fill="var(--surface)"' in fn, "the eye highlights"


def test_only_the_trace_moves_and_reduced_motion_stops_it():
    """A mark that scales in the corner of a button is motion nobody asked
    for, which is what the bullet it replaced used to do. The trace redraws
    itself with the brand mark's own idiom instead."""
    assert ".pulse-trace {" in CSS
    block = CSS.split(".pulse-trace {", 1)[1]
    block = block[:block.index("}")]
    assert "stroke-dasharray: 100" in block
    assert "animation: pulse-trace-draw" in block
    # Per mark, not file-wide: there are two, and a check that either one has
    # it passes with the other stripped.
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


# ------------------------------------------------------- what it says


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


def test_he_has_a_body_and_not_just_a_face():
    """The first version was a circle with two eyes and a heartbeat in it,
    which is a smiley. A mascot needs a silhouette you would recognise with
    the detail removed: a head, a rounder body under it, arms, buttons.

    This used to pin the feet and the exact arm paths, and those were the bug.
    Two foot ellipses at cy 34.4 sat inside a body ellipse spanning 18.4-34.8,
    and the fill is --brand at 0.14 -- so nothing occluded anything and the
    bottom of him was a tangle of crossing outlines. The feet are gone and the
    shapes no longer overlap, which is why this now asserts the silhouette
    rather than the coordinates that produced it."""
    fn = _fn("pulseMascotHTML")
    assert fn.count("<ellipse") >= 1, "a body rounder than the head"
    assert fn.count("<circle") >= 3, "head and two pupils"
    assert "stroke-linecap" in fn, "twig arms are strokes, not filled shapes"
    assert fn.count("pulse-collar") == 1, "one scarf, over the seam"
    # Three buttons, which is what stops the lower shape reading as a second
    # head. Counted inside their own group: the head is also `cx="16"`, so a
    # file-wide count of that returns four and means nothing.
    buttons = fn.split('<g fill="currentColor"', 1)[1]
    assert buttons[:buttons.index("</g>")].count("<circle") == 3


def test_nothing_in_the_silhouette_overlaps_anything_else():
    """The fill is semi-transparent, so overlap is not hidden -- it is drawn.
    Head and body are separate shapes with a gap the scarf covers, and the
    arms start outside the body rather than under it.

    Parsed rather than eyeballed: the head circle and the body ellipse must
    not intersect, and no arm may begin inside the body."""
    import re as _re
    fn = _fn("pulseMascotHTML")
    head = _re.search(r'<circle cx="16" cy="([\d.]+)" r="([\d.]+)"', fn)
    body = _re.search(r'<ellipse cx="16" cy="([\d.]+)" rx="([\d.]+)" ry="([\d.]+)"', fn)
    assert head and body, "head and body must both be there"
    head_bottom = float(head.group(1)) + float(head.group(2))
    body_top = float(body.group(1)) - float(body.group(3))
    assert head_bottom <= body_top, \
        "head reaches {} and the body starts at {}".format(head_bottom, body_top)
    # Every arm endpoint clear of the body's own bounding box.
    bx, by = 16.0, float(body.group(1))
    rx, ry = float(body.group(2)), float(body.group(3))
    arms = _re.findall(r'<path d="M([\d.]+) ([\d.]+)', fn)
    starts = [(float(x), float(y)) for x, y in arms]
    inside = [(x, y) for x, y in starts
              if ((x - bx) / rx) ** 2 + ((y - by) / ry) ** 2 < 0.92]
    assert not inside, "an arm starts inside the body: {}".format(inside)


def test_the_standing_figure_is_not_squashed():
    """A height and no width. Setting both to the same number on a 32x38
    viewBox squashes him."""
    block = CSS.split(".pulse-face-lg {", 1)[1]
    block = block[:block.index("}")]
    assert "height:" in block and "width: auto" in block


def test_his_eyes_are_the_optic_mark_and_they_blink():
    """Not an almond drawn to look like the logo: the brand mark's own path,
    scaled 0.19 and translated onto each socket. The four control points below
    are that path's, so a change to the mark is visible here as a failure
    rather than as two shapes quietly drifting apart."""
    brand = open("static/index.html", encoding="utf-8").read()
    assert "M2.6 16C6.3 8.9 10.9 5.4 16 5.4S25.7 8.9 29.4 16" in brand, \
        "the brand mark changed; the eyes are derived from it and must be redone"
    fn = _fn("pulseMascotHTML")
    assert fn.count('<g class="pulse-eye">') == 2
    # Lens and pupil in one group, or a blink shuts the eye and leaves the
    # pupil hanging in the air over it.
    for eye in fn.split('<g class="pulse-eye">')[1:]:
        socket = eye[:eye.index("</g>")]
        assert "<path" in socket and "<circle" in socket

    # Derived, and checked as derived rather than taken on trust.
    #
    # This used to assert the eye's literal control points, which made it a
    # copy of the drawing rather than a check on it -- rescaling the eyes
    # meant rewriting the assertion, and a mutation that replaced the path
    # with arbitrary numbers passed. Every point in each eye has to be the
    # brand mark's matching point under ONE uniform scale and translation.
    import re as _re
    src = [float(v) for v in _re.findall(r"-?\d+\.?\d*",
           "M2.6 16C6.3 8.9 10.9 5.4 16 5.4S25.7 8.9 29.4 16"
           "C25.7 23.1 21.1 26.6 16 26.6S6.3 23.1 2.6 16Z")]
    for eye in fn.split('<g class="pulse-eye">')[1:2]:
        d = _re.search(r'<path d="([^"]+)"', eye).group(1)
        got = [float(v) for v in _re.findall(r"-?\d+\.?\d*", d)]
        assert len(got) == len(src), "the eye is not the mark's own path"
        sx = (got[2] - got[0]) / (src[2] - src[0])
        for i in range(0, len(src), 2):
            exp_x = (src[i] - src[0]) * sx + got[0]
            exp_y = (src[i + 1] - src[1]) * sx + got[1]
            assert abs(got[i] - exp_x) < 0.05 and abs(got[i + 1] - exp_y) < 0.05, \
                "point {} is not the mark's under one uniform scale".format(i // 2)

    # Anchored to the start of a line: `.pulse-face-lg .pulse-eye {` contains
    # `.pulse-eye {`, so a bare split reads the colour rule above instead.
    block = CSS.split("\n.pulse-eye {", 1)[1]
    block = block[:block.index("}")]
    assert "transform-box: fill-box" in block, \
        "without it transform-origin is the SVG's corner and the eyes slide off his face"
    assert "transform-origin: center" in block
    assert "animation: pulse-blink" in block
    assert "@keyframes pulse-blink" in CSS
    reduced = CSS.split("@media (prefers-reduced-motion: reduce) {", 1)
    assert any(".pulse-eye { animation: none; }" in c for c in reduced[1:])


# ------------------------------------------- the empty state has to be drawn


def test_clearing_a_conversation_redraws_the_empty_state():
    """Reported as "where is the pulse snowman" — and he was nowhere, because
    the panel had no empty state at all.

    `renderPulseEmpty` runs at boot and from `updateChatContext`. Starting a
    new conversation emptied `#chat-log` and called neither, so the panel went
    blank: no greeting, no starter cards, no mascot, and no way in until a
    ticker changed and updateChatContext happened to run. Measured on
    production: `#chat-log` present and completely empty, and calling
    `renderPulseEmpty()` by hand put the mascot back with both eyes.

    Cheap to call unconditionally — it returns early when the log holds real
    messages, which immediately after that line it cannot."""
    fn = APP[APP.index("function pulseNewConversation() {"):]
    fn = fn[:fn.index("\n}")]
    assert "log.innerHTML = ''" in fn
    assert "renderPulseEmpty()" in fn, \
        "an emptied log is the empty state and has to be drawn as one"
    assert fn.index("log.innerHTML = ''") < fn.index("renderPulseEmpty()"), \
        "drawing before clearing would be wiped by the clear"


def test_the_mascot_lives_in_the_empty_state_and_only_there():
    """One greeting. An earlier draft mounted a second mascot into `#chat-log`
    and it rendered under this one, so the panel greeted a reader twice."""
    starters = APP[APP.index("function pulseStarters("):]
    starters = starters[:starters.index("\nfunction ")]
    assert "pulseMascotHTML(" in starters
    assert APP.count("pulseMascotHTML('pulse-face-lg')") == 1
