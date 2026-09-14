"""The design system, asserted rather than described.

The brief this was built to asks for a real centralised token set. Most of one
existed: 47 colours, 10 type steps, 10 spacing steps, 5 radii, 76 uses of
tabular numerals. What it did not have was a guarantee, so the gaps were the
kind nothing reports.

Eighteen colour literals sat outside the token blocks. Four were prose in
comments and six were `#000` inside mask gradients, where the value is an alpha
channel and not a colour — both fine. The remaining eight were real:

  * three dead `var(--warn, #b45309)` fallbacks. --warn is defined in both
    themes so they never fired, and they were a second amber that would not
    have followed --warn if it changed.
  * five `color: #fff` over --btn-primary or --neg, so a theme could change the
    ink on the button and miss the badges.

And one motion value served both a hover and a menu opening, which is the
spec's two bands collapsed to a point.
"""

import re

CSS = open("static/styles.css", encoding="utf-8").read()


def token_block_spans():
    """Where the tokens are declared: `:root` and the light-theme override."""
    spans = []
    for m in re.finditer(r'(:root|\[data-theme="light"\])\s*\{', CSS):
        depth, i = 1, m.end()
        while depth and i < len(CSS):
            if CSS[i] == "{":
                depth += 1
            elif CSS[i] == "}":
                depth -= 1
            i += 1
        spans.append((m.start(), i))
    return spans


def loose_colour_literals():
    """Hex literals outside the token blocks, excluding the two honest cases.

    Comments are prose about colours, not colours. `#000` in a mask gradient is
    an alpha channel: a mask reads only that, so the value is not a colour and a
    token would be misleading rather than missing.
    """
    spans = token_block_spans()
    out = []
    for m in re.finditer(r"#[0-9a-fA-F]{3,8}\b", CSS):
        if any(a <= m.start() < b for a, b in spans):
            continue
        start = CSS.rfind("\n", 0, m.start()) + 1
        line = CSS[start:CSS.find("\n", m.start())]
        stripped = line.strip()
        if stripped.startswith("*") or stripped.startswith("/*"):
            continue
        if "mask" in line:
            continue
        if "documented dark surface" in line:      # prose, mid-comment
            continue
        out.append((CSS.count("\n", 0, m.start()) + 1, m.group(), stripped[:60]))
    return out


def test_no_colour_is_declared_outside_the_token_blocks():
    """The reason this matters is the accent change: one token moved the buttons
    and the mark together, and anything holding a literal would have stayed
    blue. Two did."""
    loose = loose_colour_literals()
    assert loose == [], loose


def test_the_dead_warn_fallbacks_are_gone():
    """`var(--warn, #b45309)` cannot fire: --warn is defined in both themes. A
    fallback that never runs is a second colour nobody maintains."""
    assert CSS.count("--warn:") == 2, "--warn must exist in both themes"
    assert "var(--warn, #" not in CSS


def test_text_on_a_saturated_fill_has_its_own_token():
    """--btn-primary-ink is the right name for the primary button's label and
    the wrong name for a count sitting on red."""
    assert "--ink-on-solid:" in CSS
    for bad in ("background: var(--neg);\n  color: #fff",
                "background: var(--btn-primary);\n  color: #fff"):
        assert bad not in CSS, bad


def test_the_one_colour_that_ignores_the_theme_says_so():
    """The plate behind a company logo is white in both themes on purpose,
    because most brand marks ship on white. As a bare #ffffff mid-rule it looked
    exactly like a token somebody forgot."""
    assert "--logo-plate:" in CSS
    assert "background: var(--logo-plate);" in CSS


def test_there_are_two_motion_bands():
    """One value served a hover and a menu opening alike. At 120ms something
    that opens reads as a jump rather than a movement."""
    assert "--dur-ui:" in CSS and "--dur-panel:" in CSS
    hover = int(re.search(r"--dur-ui:\s*(\d+)ms", CSS).group(1))
    panel = int(re.search(r"--dur-panel:\s*(\d+)ms", CSS).group(1))
    assert 100 <= hover <= 180, hover
    assert 180 <= panel <= 240, panel
    assert panel > hover


def test_the_scales_are_still_single_scales():
    """The point of a token set is that nobody picks a value. Ten spacing steps
    and ten type steps, not eleven of one because a rule wanted something in
    between."""
    assert len(re.findall(r"^\s+--space-\d:", CSS, re.M)) == 10
    assert len(re.findall(r"^\s+--t-[a-z0-9]+:", CSS, re.M)) == 10
    assert len(re.findall(r"^\s+--r-[a-z]+:", CSS, re.M)) == 5


def test_financial_figures_use_tabular_numerals():
    """A column of prices that shifts by a pixel per digit is a column that
    cannot be scanned."""
    assert CSS.count("tabular-nums") >= 70
