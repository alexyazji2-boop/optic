"""The house convention, kept, but no longer a wall.

"Every panel states what it cannot tell you" is in CLAUDE.md and none of it is
deleted here. What changed is how much of the page it occupies.

Measured with NVDA loaded at 1280x900: the Options facet carries 8,291
characters of caveat across 28 of them -- a quarter of everything on the page
-- and Investing is 37% prose. All of it was set in italic at 12.65px. Italic
is for emphasis; three hundred characters of it, twenty-eight times over, is
harder to read than the text it qualifies and reads as noise rather than as
care.

Upright now, and the long ones clamp to two lines with the rest one click
away. Measured after: 21 caveats on that facet, 8 clamped, 13 short enough to
be left alone entirely -- which is the point. A "more" on a sentence that
already fits is the same fault as a disclosure that expands nothing.
"""

from __future__ import annotations

import re

APP = open("static/app.js", encoding="utf-8").read()
CSS = open("static/styles.css", encoding="utf-8").read()
CSS_CODE = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)


def test_a_caveat_is_not_set_in_italic():
    block = CSS_CODE.split("\n.caveat {", 1)[1]
    block = block[:block.index("}")]
    assert "font-style: italic" not in block
    # Still quiet: small and muted is what makes it secondary, not the slant.
    assert "var(--t-caption)" in block and "var(--ink-muted)" in block


def test_only_a_caveat_that_overflows_is_clamped():
    """Marked by measurement rather than by length or by blanket rule."""
    fn = APP.split("function markClampedCaveats(host) {", 1)[1].split("\n}", 1)[0]
    assert "el.scrollHeight <= el.clientHeight + 1" in fn
    assert "el.classList.remove('is-clamped')" in fn


def test_an_element_with_no_layout_is_not_judged():
    """The trap the company-description fit check already carries a comment
    about, and which this walked into anyway: inside `display: none` both
    heights are 0, the test reads `0 <= 1`, and every caveat in a collapsed
    panel is declared to fit. Measured before the fix: 21 caveats, 0 clamped.

    Left unmarked as well as unclamped, so it is judged again when the panel
    holding it opens."""
    fn = APP.split("function markClampedCaveats(host) {", 1)[1].split("\n}", 1)[0]
    assert "if (!el.clientHeight) { el.classList.remove('is-clamped'); return; }" in fn
    guard = fn.index("if (!el.clientHeight)")
    marked = fn.index("el.dataset.caveatChecked = '1';")
    assert guard < marked, \
        "marking it checked before the layout guard makes the bail permanent"


def test_caveats_are_measured_again_when_their_panel_opens():
    """Both routes into an open panel: the heading toggle and Expand all."""
    assert "if (open) markClampedCaveats(panel);" in APP
    assert "if (open) markClampedCaveats(host);" in APP


def test_a_clamped_caveat_is_operable_by_keyboard():
    """A paragraph that reveals text on click has to be reachable and has to
    say that it expands. 150 of these render across the product."""
    fn = APP.split("function markClampedCaveats(host) {", 1)[1].split("\n}", 1)[0]
    for attr in ("role', 'button'", "tabindex', '0'", "aria-expanded', 'false'"):
        assert attr in fn, attr
    assert "if (evt.key !== 'Enter' && evt.key !== ' ') return;" in APP


def test_the_toggle_is_delegated():
    """These render into every panel on every repaint, so a bind-once loop
    would only reach the ones that existed at load -- the trap the nav menus
    and the glossary terms both hit in this file."""
    assert "document.addEventListener('click', (evt) => {\n  const cav = evt.target.closest" in APP


def test_the_expanded_state_is_announced_and_reversible():
    fn = APP.split("const cav = evt.target.closest && evt.target.closest('p.clamp-prose[role=\"button\"]');", 1)[1]
    fn = fn[:fn.index("});")]
    assert "classList.toggle('is-open')" in fn
    assert "classList.toggle('is-clamped', !open)" in fn
    assert "setAttribute('aria-expanded', String(open))" in fn


def test_the_affordance_says_which_way_it_goes():
    # Drawn over the end of the clamped line rather than appended to it: a
    # line-clamped box clips its own ::after, so " more" after the last word
    # was never on screen (found in the 2026-10-04 clutter pass).
    block = CSS_CODE.split(".clamp-prose.is-clamped::after {", 1)[1]
    block = block[:block.index("}")]
    assert "content: 'more'" in block and "position: absolute" in block
    assert ".clamp-prose.is-open::after { content: ' less'" in CSS


def test_panel_ledes_and_method_notes_clamp_like_caveats():
    """After the caveats, long panel ledes were the largest body of prose
    between a heading and its figures: 22 over 140 characters on three pages.
    They clamp by the same measurement, so a short one is left alone."""
    sel = APP.split("const CLAMP_PROSE = '", 1)[1].split("'", 1)[0]
    for part in ("p.caveat", ".panel > p.sub", "p.pl-method"):
        assert part in sel, part
    assert "host.querySelectorAll(CLAMP_PROSE)" in APP


def test_prose_rendered_while_hidden_is_judged_when_its_view_shows():
    """A facet prefetched in the background had every caveat unjudged,
    because a hidden view has no height to measure."""
    fn = APP.split("function switchView(view, force) {", 1)[1].split("\n}\n", 1)[0]
    assert "markClampedCaveats(views[view])" in fn
