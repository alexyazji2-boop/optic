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
    for fn in (_fn("pulseMarkHTML"), _fn("pulseMascotHTML")):
        d = re.search(r'd="([^"]+)"', fn).group(1)
        assert not re.search(r"[qcsalt]", d, re.I) or re.fullmatch(r"[\sMmLlHhVvZz0-9.\-]+", d), \
            "the trace has a curve command in it: {!r}".format(d)


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
    assert 'fill="var(--brand)" fill-opacity="0.1"' in fn
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
    for name in ("pulseMarkHTML", "pulseMascotHTML"):
        assert 'pathLength="100"' in _fn(name), \
            "{}: without it the dash maths has to know the path's real length".format(name)
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
