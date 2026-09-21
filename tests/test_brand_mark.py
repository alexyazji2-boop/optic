"""One mark at two sizes, not two marks that resemble each other.

Reported as the header logo looking low-resolution beside the home page's.
Rendered side by side at 240px the cause was plain, and it was not resolution:
the header carried an older, heavier cut of the same drawing. A 2 aperture
against 1.3, a 2.4 line against 1.9, a slightly flatter zigzag, and no dot at
the end of it. At that weight the line rounds its own corners into each other
and crowds the aperture it sits in, which at 34px reads as a smudge.

Weight is deliberately not compensated for the smaller size. A half-size mark
at identical stroke values does read a touch lighter and the usual answer is to
thicken it -- but the two were indistinguishable at 34px when compared
directly, and one set of numbers cannot drift from itself.

The header mark is in index.html; the home mark is built by renderHome in
app.js. This test is the only thing that can see both at once.
"""

from __future__ import annotations

import re

APP = open("static/app.js", encoding="utf-8").read()
CSS = open("static/styles.css", encoding="utf-8").read()
HTML = open("static/index.html", encoding="utf-8").read()

HEADER = HTML.split('class="brand-mark"', 1)[1].split("</svg>", 1)[0]
HOME = APP.split('class="home-logo"', 1)[1].split("</svg>", 1)[0]


def _paths(svg):
    return re.findall(r'd="([^"]+)"', svg)


def _widths(svg):
    return re.findall(r'stroke-width="([^"]+)"', svg)


def test_both_marks_draw_the_same_two_paths():
    assert _paths(HEADER) == _paths(HOME) != [], \
        "header {!r} vs home {!r}".format(_paths(HEADER), _paths(HOME))


def test_both_marks_use_the_same_stroke_weights():
    assert _widths(HEADER) == _widths(HOME) == ["1.3", "1.9"]


def test_both_marks_end_on_a_dot_at_the_end_of_the_line():
    """The line used to stop dead in the header. The dot is what makes it read
    as a chart's last print rather than as a stroke that ran out."""
    for svg, name in ((HEADER, "header"), (HOME, "home")):
        m = re.search(r'<circle[^>]*cx="([\d.]+)"[^>]*cy="([\d.]+)"[^>]*r="([\d.]+)"', svg)
        assert m, "{} has no dot".format(name)
        assert (m.group(1), m.group(2), m.group(3)) == ("23.9", "11.4", "1.5"), name
        # And it sits on the end of the line, not near it.
        assert _paths(svg)[1].endswith("23.9 11.4"), name


def test_the_aperture_is_the_quiet_one_in_both():
    for svg, name in ((HEADER, "header"), (HOME, "home")):
        assert 'opacity="0.7"' in svg, name
        assert svg.index('stroke="currentColor"') < svg.index("var(--brand)"), \
            "{}: the aperture is drawn first and takes the text colour".format(name)


# --------------------------------------------------------------- the blink


def test_the_header_dot_is_on_the_same_clock_as_its_line():
    """Three animations, one 6s cycle, one negative delay. The dot's only job
    is not hanging in space ahead of a half-drawn stroke, and it can only do
    that in phase. Left unanimated it stayed lit through the blink, so the
    closed lid had a gold speck floating over it."""
    rule = CSS.split('body:not([data-view="home"]) .brand-mark-dot {', 1)[1]
    rule = rule[:rule.index("}")]
    assert "dot-reveal 6s ease-in-out -4.25s infinite" in rule
    for other in (".brand-mark-eye", ".brand-mark-line", ".home-logo-dot"):
        block = CSS.split(other + " {", 1)[1] if other + " {" in CSS else ""
        assert "-4.25s" in CSS.split(other, 1)[1][:400], other


def test_the_header_mark_still_holds_still_on_home():
    """Two apertures closing half a second apart on one screen reads as a
    rendering fault. The home mark is already blinking further down the page."""
    for part in ("eye", "line", "dot"):
        assert 'body:not([data-view="home"]) .brand-mark-{}'.format(part) in CSS, part


def test_reduced_motion_switches_the_dot_off_too():
    # There are twenty reduced-motion blocks in this file; the one that owns
    # the logos is the one naming .home-logo-eye.
    blocks = [b for b in CSS.split("@media (prefers-reduced-motion: reduce) {")[1:]
              if ".home-logo-eye" in b[:b.index("\n}")]]
    assert len(blocks) == 1, "the logos are guarded in {} places".format(len(blocks))
    block = blocks[0][:blocks[0].index("\n}")]
    for cls in (".brand-mark-eye", ".brand-mark-line", ".brand-mark-dot",
                ".home-logo-dot"):
        assert cls in block, cls
    assert "animation: none;" in block


def test_the_header_mark_did_not_grow():
    """34px, unchanged. The brand is already the tallest thing in the top bar
    at 54px against 46px for everything else, so it is what sets the bar's
    height: a larger mark would be four more pixels of chrome on every page,
    and the complaint was the drawing rather than the size."""
    # Anchored on the whole declaration: `.brand-mark {` on its own also
    # matches `.brand:hover .brand-mark {`, which is the colour rule.
    assert "\n.brand-mark { width: 34px; height: 34px;" in CSS
