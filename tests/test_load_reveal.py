"""The page settling in, rather than appearing.

Reported as looking laggy on load. It was not slow: the home page had no
entrance at all, so the shell painted, then the market strip and the whole
market block each swapped in whole the instant /api/home landed. An instant
state change surrounded by things that ease reads as a stall followed by a
jump, which is worse than either being slower or neither animating.

The cause was a selector. `revealPanels` only ever looked for `.panel`, and the
home page has none above its tour, so the first screen anyone sees was the one
screen the effect did not reach.
"""

import re

APP_JS = open("static/app.js", encoding="utf-8").read()
CSS = open("static/styles.css", encoding="utf-8").read()


def body_of(name):
    """A top-level function's source, comments and all."""
    head = "function %s(" % name
    start = APP_JS.index(head)
    return APP_JS[start:].split("\nfunction ", 1)[0]


def test_the_reveal_is_not_restricted_to_panels():
    """The class was `.panel.reveal`, which is why a page built from anything
    else got nothing."""
    assert re.search(r"^\.reveal \{ animation: panel-in", CSS, re.M), (
        "the reveal is still scoped to .panel")


def test_reduced_motion_still_turns_all_of_it_off():
    """Widening the selector must widen the opt-out with it, or somebody who
    asked the OS for less motion now gets more of it than before."""
    # There are several of these blocks in the file, so find the one that
    # covers the reveal rather than the first one.
    blocks = []
    at = CSS.find("@media (prefers-reduced-motion: reduce)")
    while at != -1:
        body = CSS[at:]
        blocks.append(body[:body.index("}", body.index("{") + 1)])
        at = CSS.find("@media (prefers-reduced-motion: reduce)", at + 1)
    covering = [b for b in blocks if ".reveal" in b]
    assert covering, "no reduced-motion rule mentions .reveal"
    assert any("animation: none" in b for b in covering)


def test_the_stagger_takes_a_selector():
    """A page whose blocks are not panels needs to name its own."""
    assert "function revealPanels(host, sel)" in APP_JS
    assert "host.querySelectorAll(sel || '.panel')" in APP_JS


def test_the_home_shell_reveals_its_own_blocks():
    assert "revealPanels(views.home, '.home > *')" in APP_JS


def test_the_two_async_fills_reveal_when_they_land():
    """These are the ones the reader actually sees pop: both replace a skeleton
    or an empty box when the request returns, which is hundreds of milliseconds
    after the shell painted."""
    fill = body_of("loadHomeMarket")
    assert "revealPanels(strip.parentElement, '#cc-strip')" in fill
    assert "revealPanels(host, ':scope > *')" in fill


def test_the_strip_fades_as_one_band_not_eight_cells():
    """Eight cells arriving one after another would read as eight separate
    updates to the market rather than as one reading of it."""
    fill = body_of("loadHomeMarket")
    assert "'#cc-strip'" in fill
    assert "'.ms-cell'" not in fill


def test_every_view_gets_swept_on_switch():
    """Views whose loader never calls revealPanels were switching in with no
    entrance while their neighbours had one, which reads as the effect being
    broken rather than absent."""
    switch = body_of("switchView")
    assert "armViewReveals()" in switch


def test_the_stagger_is_still_capped():
    """The reason the delay curve exists. A view with thirty blocks must not
    make the last one wait two seconds, or the fix for looking laggy is itself
    the thing that looks laggy."""
    cap = int(re.search(r"REVEAL_CAP_MS = (\d+)", APP_JS).group(1))
    step = int(re.search(r"REVEAL_STEP_MS = (\d+)", APP_JS).group(1))
    assert cap <= 1000, cap
    assert step <= 80, step
