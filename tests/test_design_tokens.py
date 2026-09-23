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
    # Twelve, not the ten this asserted first, and for the reason the radius
    # note below already records: the count was guarding the wrong end. The
    # heading ramp stopped at --t-heading, so the two tiers above it -- page
    # titles and the home display line -- were written as literal `32px` and
    # `clamp(34px, 3.4vw, 48px)` instead. That made them the only type in the
    # product --ui-scale could not reach. Measured at 1440px across the three
    # settings: body 11 -> 12.65 -> 14.3 while both of those stood still.
    # Freezing the scale did not stop anyone picking a value; it removed the
    # value they should have been picking.
    assert len(re.findall(r"^\s+--t-[a-z0-9]+:", CSS, re.M)) == 12
    # Seven, not the five this asserted first.
    #
    # The count was guarding the wrong end. Five steps -- two of which were the
    # same 8px -- was fewer than the app draws, so the divergence went into the
    # rules instead: measured at 75 hardcoded radii, including `.panel` at 14px
    # against an --r-lg of 16px and `.btn` at 10px against an --r-md of 8px.
    # Freezing the scale small did not stop anyone picking a value; it removed
    # the value they should have been picking.
    #
    # What actually holds the line is tests/test_radius_scale.py, which fails
    # on any bare radius of 4px or more. With that in place the count here is
    # only a reminder that adding a step is a decision.
    assert len(re.findall(r"^\s+--r-[a-z]+:", CSS, re.M)) == 7


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


# ------------------------------------------------- the top of the type ramp
#
# The heading ramp stopped at --t-heading, so the two tiers above it were
# written as literals: page titles at `32px` and the home display line at
# `clamp(34px, 3.4vw, 48px)`. That made them the only type in the product
# --ui-scale could not reach, and --ui-scale is a user setting whose whole
# stated purpose is to change "the absolute size of everything and none of the
# relationships between any two things".
#
# Measured on the home page at 1440px across compact/default/large:
#
#   before   body 11 -> 12.65 -> 14.3   title 32 / 32 / 32    ratio 2.9 -> 2.24
#   after    body 11 -> 12.65 -> 14.3   title 28 / 32.2 / 36.4   ratio 2.55 flat
#
# and hero 48 / 48 / 48 became 42 / 48.3 / 54.6, ratio 3.82 flat. The default
# column is what the literals already rendered, so this changed how the sizes
# respond rather than what they are.

CSS_CODE = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)


def test_the_two_heading_tiers_exist_and_scale():
    for token, base in (("--t-title", "28px"), ("--t-hero", "42px")):
        decl = re.search(re.escape(token) + r":\s*([^;]+);", CSS_CODE)
        assert decl, token
        value = decl.group(1)
        assert "var(--ui-scale)" in value, \
            "{} is the fault it was added to fix if it does not scale".format(token)
        assert base in value


def test_a_page_title_uses_the_token():
    block = re.search(r"\nh2,([^{]*)\{([^}]*)\}", CSS_CODE)
    assert block, "the display-heading rule moved"
    assert "font-size: var(--t-title)" in block.group(2)


def test_every_term_of_the_hero_clamp_scales():
    """Scaling only the bounds leaves the middle term deciding at every width
    where the clamp is not already pinned -- and on a 1440px desktop it is
    pinned to the maximum, so the setting would have moved the hero by a
    pixel."""
    block = CSS_CODE.split("\nh1, .hero, .home-title {", 1)[1]
    block = block[:block.index("}")]
    clamp = re.search(r"clamp\(([^;]+)\)\s*;", block, re.S)
    assert clamp, "the hero is no longer a clamp; check this test"
    terms = clamp.group(1).split(",")
    assert len(terms) == 3
    for i, t in enumerate(terms):
        assert "var(--ui-scale)" in t or "var(--t-hero)" in t, \
            "clamp term {} does not scale: {!r}".format(i, t.strip())


def test_the_phone_overrides_are_tokens_too():
    """Same fault one breakpoint along: `26px` and `21px`, both frozen."""
    phone = CSS_CODE.split("@media (max-width: 559px) {", 1)[1]
    hero = [ln for ln in phone.splitlines() if ".home-title" in ln and "font-size" in ln]
    assert hero and "var(--ui-scale)" in hero[0], hero
    sel = [ln for ln in phone.splitlines() if ".panel > h2" in ln and ".hm-h" in ln]
    assert sel
    rule = phone.split(sel[0], 1)[1]
    assert "font-size: var(--t-heading)" in rule[:rule.index("}")]
    assert not re.search(r"\.pl-lede \{ font-size: \d+px", phone)


def test_no_heading_sized_literal_survives():
    """A general guard rather than four specific ones. Anything at 18px or
    more is heading-sized, and the ramp covers every tier of it now.

    The allowance is a glyph, not type: `#chat-history-btn` is a 44x44 icon
    button whose 22px is the size of the character drawn in it."""
    allowed = {"#chat-history-btn"}
    bad = []
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", CSS_CODE):
        m = re.search(r"font-size:\s*(\d+(?:\.\d+)?)px", body)
        if not m or float(m.group(1)) < 18:
            continue
        name = sel.strip().split("\n")[-1].strip()
        if name not in allowed:
            bad.append("{} at {}px".format(name, m.group(1)))
    assert not bad, "heading-sized literals outside the ramp: {}".format(bad)


def test_an_uppercase_heading_takes_the_weight_the_others_take():
    """Fifteen uppercase labels in this file are 600. `.ht-col-name` is an h3
    and was 500, which is the weight the two non-headings use: `.cal-impact`
    is a chip and `.bk-active` is a span subordinate to the h2 it sits in."""
    block = CSS_CODE.split(".ht-col-name {", 1)[1]
    block = block[:block.index("}")]
    assert "text-transform: uppercase" in block
    assert "font-weight: 600" in block
