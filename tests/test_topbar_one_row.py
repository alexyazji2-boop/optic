"""The top bar holds one line.

Seven nav groups, a brand, a search box and three controls on the right stopped
fitting, and the strip did what `flex-wrap: wrap` told it to: at 1440 six groups
sat on row one and "Optic's Positions" alone on row two, a 114px header where 68
does the job.

The fix took the width out of padding and gaps rather than out of the labels or
the type scale, so nothing is hidden behind a menu and nothing was renamed. What
that costs is the safety net: with the strip on `nowrap` there is no wrap left
to absorb an overflow, so if it ever outgrows the row again the tabs run
underneath Pulse instead of folding. The breakpoint below is the only thing
standing in the way, which is why it is asserted here against the width the row
was measured to need.

Measured in the browser at the time of the change: the inline row needs 1428px,
the breakpoint sits at 1430, and a 1440 viewport renders a 68px header with all
seven groups on one line and no document overflow.
"""

import re

CSS = open("static/styles.css", encoding="utf-8").read()

# The width the inline header measured, in the browser, after the last change to
# it. The breakpoint has to be at least this or there is a band of viewports
# where the strip is inline and does not fit.
#
# 1653 as it shipped, 1428 once the padding, gaps and search box came down,
# 1400 after the dropdown carets left the layout flow, 1227 once the wordmark
# went and left only the mark, and 1393 now that Watchlist is an eighth group
# on the strip. That group used to be `offStrip: true`, which was how a
# desktop ended up with no visible route to Watchlist or Alerts at all -- the
# only ones in the document were inside #mtabs, which is display:none there.
#
# The breakpoint stays at 1410. Below it the strip takes its own row and
# spreads across it, which is the arrangement that was asked for; dropping the
# breakpoint to follow the requirement down would quietly hand those viewports
# the inline row instead. An earlier version of this assertion caught exactly
# that, when the requirement fell and this number did not.
#
# **The slack is now 17px, and it was 183.** Measured in the browser: at 1411,
# the narrowest inline width, the last tab's right edge clears the settings
# gear by 18px. A ninth group, or a longer label on an existing one, does not
# fit -- it needs the breakpoint raised in the same commit. The stylesheet says
# the same thing beside the rule.
#
# Re-measure in a browser rather than adjusting it to whatever makes the test
# pass; the sum of the header's children plus its gaps and padding is the figure.
MEASURED_INLINE_WIDTH = 1393

# What the placeholder "Search or ask  ⌘K" measures in this font at this
# tracking, plus the input's own padding and border. Below it the field starts
# clipping its own text, which is the fault the 210px width was chosen to fix.
PLACEHOLDER_WIDTH = 189


def without_comments(css: str) -> str:
    """Comments blanked to spaces, so offsets still line up.

    Necessary rather than tidy: the rules below carry comments that quote the
    very declarations they replaced -- `flex-wrap: wrap` is named in the comment
    explaining why it is gone -- so a substring check against the raw file finds
    the history instead of the code.
    """
    return re.sub(r"/\*.*?\*/", lambda m: " " * len(m.group()), css, flags=re.S)


BODY = without_comments(CSS)


def rule(selector: str) -> str:
    """The declarations of the first rule with exactly this selector."""
    m = re.search(r"(?m)^" + re.escape(selector) + r"\s*\{(.*?)\}", BODY, re.S)
    assert m, "no rule for " + selector
    return m.group(1)


def test_the_strip_cannot_wrap():
    """`wrap` is what put a group on a line of its own."""
    assert re.search(r"flex-wrap:\s*nowrap", rule("nav.tabs-group"))
    assert not re.search(r"flex-wrap:\s*wrap", rule("nav.tabs-group"))


def test_the_strip_cannot_shrink():
    """The other half, and the half that is easy to lose.

    `nav.tabs` sets `min-width: 0` so the strip can scroll. A shrinkable box
    whose content may wrap will wrap before anything else on the row yields a
    pixel, so undoing both is what makes the row either fit or not.
    """
    body = rule("nav.tabs-group")
    assert re.search(r"flex:\s*none", body)
    assert re.search(r"min-width:\s*auto", body)


def test_the_strip_keeps_its_escape_hatch_for_menus():
    """`overflow: visible` is why the section dropdowns are not clipped.

    A scroll container clips on both axes, so an `overflow-x` here would cut a
    190px menu off inside a 43px strip.
    """
    assert re.search(r"overflow:\s*visible", rule("nav.tabs-group"))
    assert not re.search(r"overflow-x:\s*(auto|scroll)", rule("nav.tabs-group"))


def own_row_breakpoint() -> int:
    """The width below which the strip drops to a full-width row of its own."""
    for m in re.finditer(r"@media \(max-width:\s*(\d+)px\)\s*\{", BODY):
        depth, i = 1, m.end()
        while depth and i < len(BODY):
            if BODY[i] == "{":
                depth += 1
            elif BODY[i] == "}":
                depth -= 1
            i += 1
        if re.search(r"nav\.tabs\s*\{[^}]*flex:\s*1 0 100%", BODY[m.end():i]):
            return int(m.group(1))
    raise AssertionError("no media query moves nav.tabs to its own row")


def test_the_breakpoint_covers_the_width_the_row_needs():
    """The one assertion that matters.

    Below this width the strip takes its own row; above it the strip is inline
    and must fit. If the breakpoint drops under what the row measures, there is
    a band of viewports where neither is true and the tabs run under Pulse.
    """
    assert own_row_breakpoint() >= MEASURED_INLINE_WIDTH


def test_a_1440_laptop_gets_the_inline_row():
    """The case the change was made for, and the one a future trim could lose."""
    assert own_row_breakpoint() < 1440
    assert MEASURED_INLINE_WIDTH <= 1440


def test_search_field_still_fits_its_own_placeholder():
    """Width came out of this field; it must not come out of its legibility."""
    m = re.search(r"width:\s*(\d+)px", rule(".search input"))
    assert m, "no explicit width on the search input"
    assert int(m.group(1)) >= PLACEHOLDER_WIDTH


def test_tabs_carry_their_own_separation():
    """The gap went to zero, so the padding is the only thing keeping labels
    apart. Nothing to assert about taste here -- only that both did not go."""
    assert re.search(r"gap:\s*0\s*;", rule("nav.tabs"))
    assert re.search(r"padding:\s*var\(--space-2\)\s+var\(--space-\d\)",
                     rule("nav.tabs button"))


def test_navigation_keeps_the_type_size_reserved_for_it():
    """--t-lead is labelled "navigation" in the scale. Dropping the strip to
    --t-body would buy width and was measured as a way to do it; it is not the
    trade that was taken and should not be reintroduced silently."""
    assert re.search(r"font-size:\s*var\(--t-lead\)", rule("nav.tabs button"))


def test_the_brand_mark_is_the_enlarged_one():
    m = re.search(r"width:\s*(\d+)px", rule(".brand-mark"))
    assert m and int(m.group(1)) >= 28
