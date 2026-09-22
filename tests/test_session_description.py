"""The session description folds where it is background and never where it is
a warning.

Measured at 800x835 with NVDA loaded: the session bar was 253px and the ticker
header did not appear until y=468, so the security a reader had just searched
for sat in the bottom 44% of the first screen. 76px of that bar was a prose
paragraph explaining what a trading session is -- shown above the price, on
every page, for the life of the account.

The reason it could not simply be hidden is in the copy itself, in
app/session.py. Three of the six phase descriptions are not background:

    overnight  "this feed carries no overnight tape for them, so a single
                stock still shows its 4pm close"
    holiday    "the last price shown is the previous session's close"
    closed     "Nothing trades until the overnight session reopens on Sunday"

Those say the number on screen is not live. Folding them to save space is the
trade this file must not make. The other three -- regular, pre, after --
explain what a session is, which is worth reading once.

Measured after, by driving renderSessionBar through each phase in a browser:
regular, pre and after fold and the bar drops 253 -> 204px with the ticker
header at y=418; overnight stays 253 and holiday 215, both with the text
still open on the page.

There is history here. A disclosure over this whole region was removed once
because the rule that hid it was written outside its width query and so
applied at every width, hiding company details on a desktop that had room for
them. The note left behind reads: "If it needs paying down again, pay it
inside a width query and verify the rule is actually in one." This pays it
somewhere else instead -- by phase, not by width -- so the rule is
unconditional on purpose and the last test here is what checks that.
"""

from __future__ import annotations

import re

APP = open("static/app.js", encoding="utf-8").read()
CSS = open("static/styles.css", encoding="utf-8").read()
SESSION_PY = open("app/session.py", encoding="utf-8").read()


def _fn(name, end="\n}"):
    return APP.split(name, 1)[1].split(end, 1)[0]


CAVEAT = ("overnight", "holiday", "closed")
BACKGROUND = ("regular", "pre", "after")


def test_the_caveat_phases_are_the_ones_whose_copy_is_a_caveat():
    """Both directions against the server's own text, so the split cannot
    drift when someone rewrites a description."""
    decl = APP.split("const SESSION_CAVEAT_PHASES = new Set(", 1)[1]
    listed = set(re.findall(r"'([a-z]+)'", decl[:decl.index(")")]))
    assert listed == set(CAVEAT), listed

    body = SESSION_PY.split("DESCRIPTIONS = {", 1)[1]
    body = body[:body.index("\n}")]
    text = {}
    for m in re.finditer(r'"(\w+)":\s*((?:\s*"[^"]*")+)', body):
        text[m.group(1)] = " ".join(re.findall(r'"([^"]*)"', m.group(2)))

    for phase in CAVEAT:
        assert phase in text, phase
        said = text[phase].lower()
        assert ("close" in said or "not trade" in said or "nothing trades" in said), \
            "{} is listed as a caveat phase but its copy does not warn about the " \
            "price on screen: {!r}".format(phase, text[phase])


def test_a_caveat_phase_renders_the_text_open_on_the_page():
    fn = _fn("function sessionDescHTML(phase, description) {")
    assert "if (SESSION_CAVEAT_PHASES.has(phase)) {" in fn
    # To the if-block's own closing brace, not a fixed number of characters:
    # a slice long enough to be safe runs into the else branch and finds the
    # <details> it is asserting the absence of.
    branch = fn.split("if (SESSION_CAVEAT_PHASES.has(phase)) {", 1)[1]
    branch = branch[:branch.index("\n  }")]
    assert '<div class="ses-desc">' in branch
    assert "<details" not in branch, "a warning behind a click is not a warning"


def test_a_background_phase_folds():
    fn = _fn("function sessionDescHTML(phase, description) {")
    tail = fn.split("SESSION_CAVEAT_PHASES.has(phase)", 1)[1]
    assert '<details class="ses-desc ses-fold"' in tail
    assert "What is this session?" in tail


def test_the_fold_defaults_closed():
    """The phases where the text matters are the phases that never fold, so
    nothing is lost by starting shut."""
    fn = _fn("function sessionDescOpen() {")
    assert "=== '1'" in fn, "anything but an explicit '1' is closed"
    assert "catch (e) { return false; }" in fn, "private mode starts closed too"


def test_the_fold_is_remembered_across_a_tab_change():
    """`renderSessionBar` runs on every view switch, so a bare <details> would
    re-close itself each time the reader changed tab, which reads as the page
    fighting them."""
    assert "fold.addEventListener('toggle', () => rememberSessionDesc(fold.open));" in APP
    assert "function rememberSessionDesc(open) {" in APP
    assert "renderSessionBar();" in _fn("function switchView(view, force) {")


def test_nothing_renders_when_there_is_no_description():
    fn = _fn("function sessionDescHTML(phase, description) {")
    assert "if (!description) return '';" in fn


def test_the_fold_matches_the_disclosure_the_app_already_has():
    """`details.ind-explain` is the existing inline fold: marker suppressed,
    muted summary, focus ring. A second look for the same gesture is a second
    thing to keep in step."""
    for prop in ("list-style: none", "cursor: pointer"):
        block = CSS.split(".ses-fold > summary {", 1)[1]
        assert prop in block[:block.index("}")], prop
    assert ".ses-fold > summary::-webkit-details-marker { display: none; }" in CSS
    assert ".ses-fold > summary:focus-visible" in CSS


def test_the_fold_is_not_hidden_by_a_width_rule():
    """The failure this replaces. A disclosure over this region was removed
    once because its `display: none` was written outside the 640px block it
    was meant for and applied everywhere.

    This fold is keyed on phase, not width, so no width query may touch it --
    and the check is that no rule mentioning .ses-fold sits inside a @media at
    all."""
    for m in re.finditer(r"@media[^{]*\{", CSS):
        start = m.end()
        depth, i = 1, start
        while i < len(CSS) and depth:
            if CSS[i] == "{":
                depth += 1
            elif CSS[i] == "}":
                depth -= 1
            i += 1
        assert ".ses-fold" not in CSS[start:i], \
            "a width query touches .ses-fold: {}".format(m.group()[:60])
