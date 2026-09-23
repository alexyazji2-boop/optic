"""The shared visual layer: one declaration per decision.

Every claim here was found by reading a *computed* value in a browser rather
than by reading the rule, because each fault was a rule that looked right and
lost.

Panel headings rendered at 32px in the display face at weight 400.
`.panel > h2` was declared three times -- 17.25px/600, 20.7px/600, and once
inside a list of display-face headings -- all at specificity (0,1,2), so
source order decided and the display rule won. Two reasoned declarations were
dead. Against 13px table text that is a heading two and a half times the size
of the data it introduces, repeated twenty times down a view.

Eleven box-shadows hardcoded `rgba(0, 0, 0, ...)` at alphas from 0.25 to 0.7
in an app with a light theme, while `--shadow-ink` and `--scroll-shade` were
already themed and already used by two of the thirteen.

Fifty-two focus rings on two colours, four of them on the logo's gold.

`table.data td.name` opted a text column out of tabular figures against a
default that did not exist, so every price column in the product rendered in
proportional figures.

And the catalyst table ran 144px past a panel that could not scroll: measured
at 1280px, table right edge 1395, panel right edge 1251, panel scrollWidth
equal to its clientWidth. Clipped and unreachable, not merely off to one side.
"""

from __future__ import annotations

import re

CSS = open("static/styles.css", encoding="utf-8").read()


def _decls(selector):
    """Every declaration block for an exact selector."""
    return re.findall(re.escape(selector) + r"\s*\{([^}]*)\}", CSS)


# --------------------------------------------------------------- hierarchy


def test_the_panel_heading_has_one_declaration_that_sets_its_size():
    """Three set it before, and the one that won was the one nobody wrote for
    panels."""
    sized = [d for d in _decls(".panel > h2") if "font-size" in d]
    assert len(sized) == 1, "{} declarations set the panel heading size".format(len(sized))
    assert "var(--t-heading)" in sized[0]
    assert "font-weight: 600" in sized[0]


def test_a_panel_heading_is_not_display_type():
    """The display face and the title tier belong to the one thing a page is
    about. A panel heading repeats down the view.

    Matched on `--t-title` rather than on `32px`: that literal was the whole
    reason the tier could not follow --ui-scale, and a test anchored to it
    would have had to be rewritten to allow the fix it was guarding."""
    block = re.search(r"\nh2,([^{]*)\{([^}]*font-size:\s*var\(--t-title\)[^}]*)\}", CSS)
    assert block, "the display-heading rule moved; check this test still points at it"
    assert ".panel > h2" not in block.group(1), \
        "panel headings are back in the display-heading list"


# --------------------------------------------------------------- elevation


def test_no_shadow_hardcodes_black():
    """A literal black cast under a cream card reads as dirt rather than
    depth, and the tokens to avoid it already existed."""
    bare = re.findall(r"box-shadow:[^;]*rgba\(0,\s*0,\s*0", CSS)
    assert not bare, "{} shadows still hardcode black".format(len(bare))


def test_there_are_three_elevations_and_both_themes_define_the_cast():
    for step in ("--elev-1", "--elev-2", "--elev-3"):
        assert step + ":" in CSS, step
        assert CSS.count("var({})".format(step)) >= 1, "{} is unused".format(step)
    assert len(re.findall(r"--shadow-cast:", CSS)) == 2, \
        "the cast colour must be defined in both themes or one of them is wrong"


# ------------------------------------------------------------------ focus


def test_every_focus_ring_is_the_same_colour():
    assert "--focus:" in CSS
    for stray in ("outline: 2px solid var(--s1)", "outline: 2px solid var(--brand)"):
        assert stray not in CSS, "a focus ring is still on {}".format(stray)
    assert CSS.count("outline: 2px solid var(--focus)") >= 50


# ------------------------------------------------------------------ figures


def test_data_tables_use_lining_figures():
    """And the name column still opts out, which is the pair that makes it a
    decision rather than a default."""
    td = [d for d in _decls("table.data td") if "text-align" in d]
    assert td and "font-variant-numeric: tabular-nums" in td[0]
    assert "table.data td.name" in CSS
    name = _decls("table.data td.name")
    assert name and "font-variant-numeric: normal" in name[0]


# -------------------------------------------------------------- containment


def test_the_catalyst_table_can_be_scrolled_to():
    """`table.data` carries a 480px floor, and an overflow escaping a
    `visible` parent does not always give a scrolling ancestor anything to
    scroll. The same containment `.panel .grid > *` uses."""
    body = _decls(".cat-body")
    assert body, ".cat-body is gone; check the catalyst card still contains its table"
    assert "min-width: 0" in body[0] and "overflow-x: auto" in body[0]
    assert ".panel .grid > * { min-width: 0; overflow-x: auto; }" in CSS, \
        "the pattern this copies"


# ------------------------------------------------- charting: the chart wins


def test_the_charting_tab_gives_up_the_session_legend():
    """Measured at 1280x900 with NVDA charted: 347px of chrome above the
    workspace, a 97px toolbar inside it, and a 309px chart -- a third of the
    screen on the one tab whose whole job is the chart. Dropping the phase
    legend there took the session bar 204px -> 86px and the chart 309 -> 362.
    At 768 the chart is 501px and at 375 it is 529px.

    The legend decodes a 24-hour strip that the chart's own time axis already
    covers, and `.ses-main` names the phase in words directly above it. Every
    other view keeps it, because there the strip is the only session context
    on the page.

    Keyed on `body[data-view]` because `#sessionbar` is a sibling of the views
    rather than a child of one."""
    assert 'body[data-view="chart"] .ses-legend' in CSS


def test_it_never_gives_up_the_staleness_warning():
    """`.ses-fold` and not `.ses-desc`. The fold only exists in the phases
    where the description is background; overnight, holiday and the weekend
    render it as a plain div with no fold class, so the sentence saying the
    price on screen is not live survives on the chart tab exactly as it does
    everywhere else.

    Verified by driving renderSessionBar into the overnight phase with the
    chart tab open: the description rendered, visible, and not as a fold."""
    rule = [ln for ln in CSS.split("\n")
            if 'body[data-view="chart"]' in ln and "ses-" in ln]
    assert rule, "the charting session rule is gone"
    joined = " ".join(rule)
    assert ".ses-fold" in joined
    assert ".ses-desc" not in joined, \
        "hiding .ses-desc would take the staleness warning with it"
