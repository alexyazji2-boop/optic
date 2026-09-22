"""Space between blocks, without every block having to ask for it.

`.gap` is opt-in and eighty-one blocks opt in. The defect was the ones that
forget: measured across all nineteen views, sixteen boundaries had no space at
all, so a panel's closing caveat ran into the next heading. The daily Read was
the worst, seven flush boundaries down one page, and the one that was reported
was the books panel running into Optic Portfolio.

Opt-in spacing cannot be held consistent by hand. A new panel is correct only if
whoever wrote it remembered a class that does nothing visible when it is absent,
and the symptom is two blocks touching rather than anything that looks wrong on
its own.

**The rule is a default, not an override, and that is the whole design.** A first
attempt used `> * + * { margin-top }` and leaned on adjacent sibling margins
collapsing so the eighty-one opt-ins would not double. The collapsing worked.
What went wrong is that the rule outranked the deliberate values: measured, six
chrome boundaries that were 14px and 18px by choice became 23px, including the
header above every dossier page. Wrapping the whole selector in `:where()` drops
it to zero specificity, so anything that declares a margin wins and the rule
only fills in where nothing was declared.

Measured in a browser across 103 boundaries in 19 views, scrolled to top and
with the reveal animations settled:

    before   16 boundaries flush
    after     0 flush outside the charting workspace, where the toolbar sits
              against the chart body on purpose
    preserved sec-head 14, sec-index 9, legal-area 18, and the Read view's
              four --space-4 boundaries
    36 of 57 content boundaries on the 23px rhythm

An earlier pass of this file read 34px and 36px at two boundaries and 0 at one
that should have been 18. All three were artifacts: the reveal animation was
mid-flight and the page was scrolled, which moves a rect relative to its
sibling. Measure settled and at the top.
"""

import re

CSS = open("static/styles.css", encoding="utf-8").read()


def rule_for(selector):
    """The declaration block for one selector, or None."""
    at = CSS.find(selector)
    if at < 0:
        return None
    return CSS[at:CSS.index("}", at) + 1]


def test_the_view_carries_the_rhythm():
    rule = rule_for(':where([role="tabpanel"] > *:not(:last-child):not(:empty))')
    assert rule, "the page rhythm rule is gone"
    assert "margin-bottom: var(--space-5)" in rule


def test_the_rhythm_is_a_default_and_can_be_beaten():
    """Zero specificity is the design, not a detail. Everything sits inside
    `:where()`, including the attribute selector: `:where([role=...] > *)`
    rather than `:where([role=...]) > *`, because the latter still scores an
    attribute selector and ties with every class rule it is meant to lose to.
    """
    assert ':where([role="tabpanel"] >' in CSS, (
        "the attribute selector escaped the :where(), so the rule now outranks "
        "the deliberate margins it is supposed to yield to")
    # And it must not have become a margin-top rule again: that version cannot
    # be beaten by a previous sibling's deliberate margin-bottom.
    rule = rule_for(':where([role="tabpanel"] > *:not(:last-child):not(:empty))')
    assert "margin-top" not in rule


def test_it_does_not_space_the_last_block():
    """Otherwise every view ends on 23px of nothing."""
    assert ":not(:last-child)" in CSS


def test_it_does_not_space_a_host_that_has_not_filled_yet():
    """`#roth-host` and the portfolio-risk host are empty divs in index.html
    that a later fetch writes into. Spacing something with no content in it is
    the same 23px of nothing in a different place, and it was measured on the
    tracker after the rhythm rule shipped. `:empty` stops matching the moment
    content lands, so the rhythm arrives with it."""
    assert ":not(:empty)" in CSS
    rule = rule_for(':where([role="tabpanel"] > *:not(:last-child):not(:empty))')
    assert rule, "the empty guard is not on the rhythm rule itself"


def test_the_deliberate_spacings_still_declare_their_own():
    """These are the six the first attempt overrode. Each is on the scale and
    each is a choice: chrome sits closer to what it labels than content blocks
    sit to each other. If one of these loses its own margin it silently falls
    back to the 23px rhythm, which is the regression this guards."""
    for cls, token in (("sec-head", "--space-3"),
                       ("scan-modes", "--space-3"),
                       ("read-strip", "--space-4"),
                       ("read-lead", "--space-4"),
                       ("read-nav", "--space-4"),
                       ("read-desks", "--space-4")):
        block = rule_for(".%s {" % cls)
        assert block, cls
        assert "margin-bottom: var(%s)" % token in block, (cls, token)


def test_the_charting_view_opts_out():
    """It is a grid, margins do not collapse in one, and its layout is the dock
    beside the chart, spaced by the grid. An id so it beats the default
    outright rather than by source order."""
    rule = rule_for("#view-chart > * {")
    assert rule
    assert "margin-bottom: 0" in rule


def test_the_books_panel_no_longer_runs_into_the_next_section():
    """The reported case. Its own `gap` as well as the rhythm, because the
    panel is rendered as a string in app.js and reads better carrying the
    class the other eighty do."""
    app = open("static/app.js", encoding="utf-8").read()
    at = app.index("function renderBookSelector(")
    body = app[at:app.index("\nfunction ", at + 1)]
    assert 'class="panel span-all gap"' in body


def test_the_rhythm_uses_a_token():
    rule = rule_for(':where([role="tabpanel"] > *:not(:last-child):not(:empty))')
    assert "#" not in rule
    assert "px" not in rule.split("var(")[0]


def test_every_view_is_a_tabpanel():
    """The selector hangs off `role="tabpanel"`, so a view that is not one gets
    no rhythm at all and the whole page goes flush. There is no shared class to
    use instead; this is the hook."""
    html = open("static/index.html", encoding="utf-8").read()
    ids = re.findall(r'id="(view-[a-z]+)"', html)
    assert len(ids) >= 18, ids
    for view_id in ids:
        tag = re.search(r'<[^>]*id="%s"[^>]*>' % view_id, html)
        assert tag, view_id
        assert 'role="tabpanel"' in tag.group(0), view_id


# ------------------------------------------- wrappers of nothing but hidden
#
# `applyUiMode` hides panels and never their wrappers, because it iterates
# `.panel`. A hidden panel costs nothing: `display: none` generates no box, so
# its margin does not apply. The wrapper is the problem. It stays
# `display: grid` with every child hidden, which makes it a 0px-tall box still
# carrying `.gap`'s 23px.
#
# Measured on the Options tab, driving the knowledge ladder in a browser:
#
#   Simple          6 wrappers hidden, 1 visible, 11 panels, 0 phantom spacers
#   Literate        4 hidden, 3 visible, 14 panels, 0 phantom (was 4, 92px)
#   Professional    0 hidden, 7 visible, 23 panels, 0 phantom
#
# Professional is the one that matters: nothing may be hidden when everything
# is shown.

WRAPPER_RULE = ".grid:has(> .panel.is-advanced):not(:has(> *:not(.is-advanced)))"


def test_a_wrapper_of_only_hidden_panels_is_hidden():
    rule = rule_for(WRAPPER_RULE)
    assert rule, "the wrapper rule is gone"
    assert "display: none" in rule


def test_the_wrapper_rule_needs_a_hidden_panel_to_fire():
    """Rather than matching any childless grid. A grid with no children at all
    is usually an async host waiting on a fetch, and hiding one of those would
    fight the reveal animation that fills it."""
    assert ":has(> .panel.is-advanced)" in CSS


def test_the_wrapper_rule_yields_the_moment_anything_is_visible():
    """The Professional case. `:not(:has(> *:not(.is-advanced)))` is the half
    that does this: one visible child and the wrapper stays. Written over `*`
    rather than `.panel`, so a heading or a note beside a hidden panel also
    keeps the wrapper."""
    assert ":not(:has(> *:not(.is-advanced)))" in CSS


def test_the_hiding_is_driven_by_the_class_the_js_already_sets():
    """`:has()` rather than a second pass in `applyUiMode`, so there is no
    ordering to get wrong: a panel toggled from the chooser updates its wrapper
    in the same frame with nothing to re-run."""
    app = open("static/app.js", encoding="utf-8").read()
    assert "panel.classList.toggle('is-advanced', hide);" in app
    # And applyUiMode still must not try to hide wrappers itself.
    at = app.index("function applyUiMode(")
    body = app[at:app.index("\nfunction ", at + 1)]
    assert ".grid" not in body


def test_the_hidden_panel_note_is_not_inside_a_wrapper():
    """It says how many panels are hidden and offers the chooser. Appended to
    the view, so hiding a wrapper cannot take the explanation with it."""
    app = open("static/app.js", encoding="utf-8").read()
    at = app.index("function applyUiMode(")
    body = app[at:app.index("\nfunction ", at + 1)]
    assert "host.appendChild(note)" in body
