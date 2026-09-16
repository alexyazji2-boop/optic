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


# Comments blanked to spaces rather than removed, so every offset and line
# number below still points at the real file. The previous version skipped a
# comment by testing whether its LINE started with `*` or `/*`, which misses
# every continuation line -- and a continuation line is exactly where the
# rationale for removing a colour ends up.
CSS_NC = re.sub(r"/\*.*?\*/", lambda m: re.sub(r"\S", " ", m.group()), CSS, flags=re.S)


def loose_colour_literals():
    """Colour literals outside the token blocks, excluding the honest cases.

    Two kinds are honest. `#000` in a mask gradient is an alpha channel: a mask
    reads only that, so the value is not a colour and a token would mislead.
    And a GREY rgb() -- r == g == b -- is a shadow or a scrim, not a hue; those
    have their own tokens (--shadow-ink, --scrim) and the literals that remain
    are geometry with black in them.

    Saturated rgb() is checked as well as hex, which it was not before. That
    gap is why `rgba(28, 114, 216, 0.38)` sat on `.btn.primary:hover` long
    after the brand went gold: this test's own docstring says it exists because
    literals stayed blue, and the one that stayed was not written in hex.
    """
    spans = token_block_spans()
    out = []

    def outside(pos):
        return not any(a <= pos < b for a, b in spans)

    def line_at(pos):
        start = CSS_NC.rfind("\n", 0, pos) + 1
        end = CSS_NC.find("\n", pos)
        return CSS_NC[start:end if end != -1 else len(CSS_NC)]

    for m in re.finditer(r"#[0-9a-fA-F]{3,8}\b", CSS_NC):
        if not outside(m.start()):
            continue
        line = line_at(m.start())
        if "mask" in line:
            continue
        out.append((CSS_NC.count("\n", 0, m.start()) + 1, m.group(), line.strip()[:60]))

    for m in re.finditer(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", CSS_NC):
        if not outside(m.start()):
            continue
        r, g, b = (int(x) for x in m.groups())
        if r == g == b:                 # grey: a shadow or a scrim, not a hue
            continue
        line = line_at(m.start())
        out.append((CSS_NC.count("\n", 0, m.start()) + 1, m.group() + ")",
                    line.strip()[:60]))
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


def test_the_chart_palette_fallbacks_match_their_tokens():
    """charts.js resolves its palette from the custom properties at boot, with
    literals as the fallback for a stylesheet that has not loaded. Seven of
    twenty-four had drifted as the theme moved.

    The worst was `pos: '#3987e5'`: the POSITIVE colour fell back to blue while
    --pos is green, so until syncChartTheme ran, every up-candle, up-volume bar
    and positive figure on a chart drew in the wrong hue. Also #ffffff against a
    warm --ink #f5f1ec, and a --surface two shades out.

    Compared against the dark defaults, which is the first :root block: the
    fallbacks stand in for that theme, and the light values live in
    :root[data-theme="light"] further down.
    """
    js = open("static/charts.js", encoding="utf-8").read()
    js_nc = re.sub(r"/\*.*?\*/", " ", js, flags=re.S)
    dark_start = CSS.index(":root {")
    dark = CSS[dark_start:CSS.index(':root[data-theme="light"]')]
    tokens = dict(re.findall(r"(--[a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{3,8})\s*;", dark))
    var_of = dict(re.findall(r"(\w+)\s*:\s*'(--[a-z0-9-]+)'", js_nc))
    literal_of = dict(re.findall(r"(\w+)\s*:\s*'(#[0-9a-fA-F]{3,8})'", js_nc))
    checked, bad = 0, []
    for slot, var in var_of.items():
        if slot not in literal_of or var not in tokens:
            continue
        checked += 1
        if literal_of[slot].lower() != tokens[var].lower():
            bad.append((slot, literal_of[slot], var, tokens[var]))
    assert checked >= 20, "only %d slots compared; the parse is wrong" % checked
    assert bad == [], bad


def test_the_primary_button_glow_follows_the_brand():
    """It was `rgba(28, 114, 216, 0.38)` -- #1c72d8, a blue from before the
    brand became gold -- so every primary button cast a blue glow against its
    own gold fill. Mixed from the token, so it cannot drift again."""
    assert "rgba(28, 114, 216" not in CSS_NC
    assert CSS.count("color-mix(in srgb, var(--btn-primary) 38%, transparent)") == 2


def test_one_scrim_and_one_shadow_ink():
    """The modal backdrops were rgba(0,0,0,0.5) twice and 0.6 once for the same
    job. Naming them is what stops the next one being a fourth value."""
    assert CSS.count("--scrim:") == 2, "both themes"
    assert CSS.count("--shadow-ink:") == 2
    assert "background: rgba(0, 0, 0, 0." not in CSS_NC


def test_the_dead_bg_hover_fallbacks_are_gone():
    """--bg-hover is declared in both themes now, so `var(--bg-hover, rgba(...))`
    can never reach its fallback. Two of the three fallbacks disagreed with each
    other anyway."""
    assert "var(--bg-hover, " not in CSS_NC
