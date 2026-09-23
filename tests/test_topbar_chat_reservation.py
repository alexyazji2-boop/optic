"""The top bar has to get out of the Pulse panel's way, like everything else.

`main` reserves the panel with `margin-right: var(--chat-w)` and `footer.legal`
with a matching `padding-right`. The header had neither and laid out across the
whole window, so its right-hand end sat underneath the panel.

Measured in a browser at 1100px with Pulse open, panel edge at x=769: before
the rule the settings gear (828-866), the account slot (875-961) and the Pulse
toggle itself (979-1066) were all entirely behind it; after it they sit at
508-546, 555-641 and 659-746, clearing the edge by the 23px gutter. The panel
carries its own close button so this was never a trap, but Settings and Sign in
could not be reached without first closing the thing you wanted to keep open.

It became visible when Watchlist made an eighth nav group -- seven tabs ended at
758 and cleared the edge by 22px -- but the three buttons were already hidden at
every width where the panel splits the page rather than covering it.
"""

from __future__ import annotations

CSS = open("static/styles.css", encoding="utf-8").read()

OPEN = "body.chat-open header.topbar"
FULL = "body.chat-full header.topbar"


def _decl(selector):
    """The declaration block for a selector that appears exactly once."""
    assert CSS.count(selector + " {") == 1, \
        "{} is declared {} times; this test reads one".format(
            selector, CSS.count(selector + " {"))
    body = CSS.split(selector + " {", 1)[1]
    return body[:body.index("}")]


def test_the_bar_reserves_the_panel_at_all():
    assert OPEN in CSS, "the header is the only one of the three that never did"
    assert "padding-right" in _decl(OPEN)


def test_the_reservation_tracks_the_panel_rather_than_guessing_at_it():
    """The panel is drag-resizable and `--chat-w` is what the grip writes, so a
    literal width here would be correct only until the first drag. Measured
    across 320/500/700/860 at 1100px: no control overlaps the panel at any of
    them, which only holds because both sides read the same variable."""
    decl = _decl(OPEN)
    assert "var(--chat-w)" in decl, "a fixed px value would drift on the first drag"
    assert "var(--space-5)" in decl, "and the gutter beside the panel is the page's"


def test_it_is_padding_because_the_bar_is_the_painted_surface():
    """`main` uses margin and gets away with it because nothing is drawn on
    `main`. The bar is sticky, full-bleed, and carries `background: var(--glass)`
    with a `backdrop-filter`; pulling its box in would leave a 320px strip of
    unblurred page beside it. `footer.legal` reserves the panel with padding for
    the same reason, and is the precedent this follows."""
    assert "margin-right" not in _decl(OPEN)
    assert "body.chat-open footer.legal { padding-right: var(--chat-w); }" in CSS


def test_covering_drops_the_reservation():
    """Past the threshold the panel covers the page instead of splitting it, so
    reserving would push the bar's contents off to the left for nothing."""
    assert FULL in CSS
    decl = _decl(FULL)
    assert "var(--chat-w)" not in decl, "nothing to reserve when it covers"
    assert "var(--space-5)" in decl, "but the page gutter stays"


def test_covering_wins_over_splitting_on_source_order():
    """`chat-full` is added alongside `chat-open`, never in place of it --
    `applyChatWidth` toggles one and leaves the other -- so both selectors match
    at once. They are the same specificity (0,2,2), which leaves source order
    as the only thing deciding, and it has to resolve to `chat-full`.

    This is the same failure the `body.chat-full main` rule above it already
    carries a comment about: written 3,900 lines too early it lost silently and
    left main 46px wide."""
    assert CSS.index(FULL) > CSS.index(OPEN), \
        "chat-full must come after chat-open or covering never takes effect"
    app = open("static/app.js", encoding="utf-8").read()
    fn = app.split("function applyChatWidth(", 1)[1].split("\n}", 1)[0]
    assert "classList.toggle('chat-full'" in fn
    assert "chat-open" not in fn, \
        "if this ever removed chat-open the ordering above would stop mattering"


def test_the_controls_it_rescues_are_the_ones_that_exist():
    """Both directions, as everywhere else: a rule protecting a control that is
    gone protects nothing, and says nothing about it."""
    html = open("static/index.html", encoding="utf-8").read()
    # The gear is not in this list any more: it moved to the rail footer, and
    # the rail is not in the bar, so the padding rule does not rescue it and
    # asserting it here would pass on an element the rule cannot reach.
    bar = html.split('<header class="topbar">', 1)[1].split("</header>", 1)[0]
    for el_id in ("account-slot", "chat-toggle"):
        assert 'id="{}"'.format(el_id) in bar, el_id
    assert 'id="settings-btn"' not in bar
