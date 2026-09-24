"""Where the keyboard is, and whether you can see it.

The app sets one global ring -- `:focus-visible { outline: 2px solid var(--focus) }`
-- and then eight rules turn it back off. Most of those are fine: a pointer
already knows where it is, and `.auth-field input` swaps the outline for a 3px
box-shadow ring, which is the same promise kept a different way.

Three were not fine, and they were only findable by asking what each control
does rather than what it looks like:

  * `.chat-grip` takes ArrowLeft/Right/Home/End and resizes the Pulse panel
    with them. It is a 10px strip at `opacity: 0`, and its own rule read
    `:focus-visible { outline: none }`. A keyboard reader tabbed onto something
    invisible and their arrow keys stopped scrolling the page.
  * `.gloss-term` drew focus exactly as it drew hover -- a colour change and
    nothing else -- so the two states were indistinguishable, and WCAG 1.4.1
    wants more than hue regardless.
  * `.range-pick select` and the Roth controls answered `:focus` with a 1px
    border tint. On a text input a caret covers for that. A <select> has no
    caret.

And one that no state could fix from the outside: `#cp-input` sets
`outline: none` on the base rule, and an id (1,0,0) outranks `:focus-visible`
(0,1,0), so the global ring never had a chance.

Measured in a browser rather than asserted from the file: `.focus()` does not
match :focus-visible until the page has seen a real key, which is why these are
source assertions and the browser run is recorded here instead.
"""

from __future__ import annotations

import re

CSS = open("static/styles.css", encoding="utf-8").read()


def _code():
    """Comments cannot vouch for code -- the note explaining why `.chat-grip`
    no longer says `outline: none` contains the string `outline: none`."""
    return re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)


def _rules(css):
    return re.findall(r"([^{}@]+)\{([^{}]*)\}", css)


def test_the_app_still_has_one_ring_everything_starts_from():
    """Every fix below restates this rule rather than inventing a second
    treatment, so it has to exist and has to be the thing being restated."""
    code = _code()
    hit = [b for s, b in _rules(code) if s.strip() == ":focus-visible"]
    assert hit, "the global :focus-visible rule is gone"
    assert "outline: 2px solid var(--focus)" in hit[0]


# Controls whose own rule used to remove the ring, and what each one needs
# back. Keyed by the selector that must carry a real outline.
MUST_RING = [
    ".chat-grip:focus-visible",
    ".gloss-term:focus-visible",
    "#cp-input:focus-visible",
    ".range-pick select:focus-visible",
    ".roth-controls select:focus-visible",
    ".roth-controls input:focus-visible",
    ".roth-controls textarea:focus-visible",
    ".home-search input:focus-visible",
]


def _declares_ring(selector, css):
    for sel, body in _rules(css):
        parts = [re.sub(r"\s+", " ", p.strip()) for p in sel.split(",")]
        if selector not in parts:
            continue
        m = re.search(r"(?:^|;)\s*outline\s*:\s*([^;]+)", body)
        if m and m.group(1).strip() not in ("none", "0"):
            return m.group(1).strip()
    return None


def test_every_control_that_lost_its_ring_has_it_back_for_the_keyboard():
    code = _code()
    missing = [s for s in MUST_RING if not _declares_ring(s, code)]
    assert not missing, "no keyboard ring for: " + ", ".join(missing)


def test_the_ring_is_the_apps_ring_and_not_a_second_invention():
    """Eight restatements are eight chances to drift two pixels apart, which is
    the same failure the radius families had."""
    code = _code()
    widths, colours = set(), set()
    for s in MUST_RING:
        decl = _declares_ring(s, code)
        parts = decl.split()
        widths.add(parts[0])
        colours.add(parts[-1])
    assert widths == {"2px"}, "rings drawn at {} widths: {}".format(len(widths), widths)
    assert colours == {"var(--focus)"}, "rings drawn in: {}".format(colours)


def test_hover_and_focus_are_told_apart():
    """`.gloss-term` shared one rule with `:hover`, so the two states were
    drawn identically and a keyboard reader could not tell a focused term from
    one the mouse happened to be over. The split is the fix; this asserts they
    have not been recombined."""
    code = _code()
    for sel, _ in _rules(code):
        parts = [re.sub(r"\s+", " ", p.strip()) for p in sel.split(",")]
        if ".gloss-term:hover" in parts:
            assert ".gloss-term:focus-visible" not in parts, \
                "hover and focus-visible share a rule again"


def test_a_focus_rule_is_not_left_behind_a_plain_focus_rule():
    """:focus and :focus-visible have the same specificity, so a `:focus` rule
    that says `outline: none` beats a `:focus-visible` rule that says otherwise
    whenever it comes later in the file. Source order is the entire mechanism
    and nothing in either rule hints at it."""
    code = _code()
    text = code
    for s in MUST_RING:
        if " " not in s and not s.startswith("#"):
            continue
        base = s.replace(":focus-visible", "")
        killer = re.search(
            r"(?<![\w.#-])" + re.escape(base) + r":focus\s*\{[^}]*outline:\s*(?:none|0)",
            text)
        if not killer:
            continue
        restore = text.index(s)
        assert killer.start() < restore, \
            "{}:focus removes the ring after {} restores it".format(base, s)
