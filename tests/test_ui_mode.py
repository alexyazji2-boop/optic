"""Simple and Pro: how much of the terminal to show.

The Analysis tab renders twenty-two panels and nine of them are the options
machinery — delta, gamma, GEX, VEX, call-versus-put flow, net premium by strike,
buy calls/puts, the strike recommendation and the options strategies. Measured on
AAPL in a browser, not estimated from the source, because the headings carry
appended chrome ("Ask Pulse", bar counts, the ticker) and a match on the whole
string would silently hide nothing.

Two rules this feature lives by, and most of these tests are about them.

Pro is the default, because Simple would silently remove nine panels from a page
an existing reader already uses. And nothing is hidden silently: the view says
how many panels are out and offers the switch back, where the panels would have
been. A page quietly missing sections is indistinguishable from one that failed
to load them.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP_JS = (ROOT / "static" / "app.js").read_text()
STYLES = (ROOT / "static" / "styles.css").read_text()

ADVANCED_VIEWS = ["swing", "long", "market"]


def _advanced() -> dict:
    block = APP_JS.split("const PANELS_ADVANCED = {", 1)[1].split("\n};", 1)[0]
    out = {}
    for view, body in re.findall(r"(\w+):\s*\[([^\]]*)\]", block, re.S):
        out[view] = re.findall(r"'([^']+)'", body)
    return out


# --------------------------------------------------------------- the defaults

def test_pro_is_the_default():
    """Simple as the default would remove nine panels from a page someone already
    uses, and "the app lost half my tab" is a worse first impression than a long
    page."""
    body = APP_JS.split("function uiMode() {", 1)[1].split("\n}", 1)[0]
    assert "return 'pro';" in body


def test_an_unknown_stored_mode_falls_back():
    body = APP_JS.split("function uiMode() {", 1)[1].split("\n}", 1)[0]
    assert "UI_MODES.includes(raw)" in body


def test_private_mode_does_not_break_it():
    """localStorage throws in private browsing. Both the read and the write are
    wrapped everywhere else in this file for the same reason."""
    for fn in ("function uiMode()", "function setUiMode("):
        body = APP_JS.split(fn, 1)[1].split("\n}", 1)[0]
        assert "catch" in body, fn


# ------------------------------------------------------- what Simple leaves out

def test_every_view_with_an_advanced_set_declares_one():
    got = _advanced()
    for view in ADVANCED_VIEWS:
        assert got.get(view), f"{view} has no advanced set"


def test_the_options_machinery_is_the_analysis_set():
    """The nine measured on AAPL. Named individually rather than by a prefix,
    because "gamma" alone would also catch the close-defence panel's wording."""
    swing = _advanced()["swing"]
    for key in ("delta analysis", "gamma analysis", "gex.", "vex.",
                "call vs put flow", "net premium by strike", "buy calls / puts",
                "options strategies", "strike & entry recommendation"):
        assert key in swing, key
    assert len(swing) == 9, swing


def test_the_keys_are_lowercase_and_matched_lowercase():
    """The headings are title-case in the markup. A key with a capital in it
    would match nothing and hide nothing, silently."""
    for view, keys in _advanced().items():
        for k in keys:
            assert k == k.lower(), f"{view}: {k}"
    body = APP_JS.split("function isAdvancedPanel(", 1)[1].split("\n}", 1)[0]
    assert ".toLowerCase()" in body


def test_matching_is_a_substring_not_an_equality():
    """A heading is "GEX. Dealer gamma exposureAsk Pulse" in the DOM: it carries
    the Ask-Pulse button's text, bar counts and the ticker."""
    body = APP_JS.split("function isAdvancedPanel(", 1)[1].split("\n}", 1)[0]
    assert "includes(" in body


def test_nothing_that_states_a_limitation_is_ever_hidden():
    """Simple hides complexity, never the caveats. Hiding "what this cannot tell
    you" from a beginner is exactly backwards, and it is the one thing every
    panel in this app is required to carry."""
    for keys in _advanced().values():
        for k in keys:
            assert "cannot" not in k and "caveat" not in k and "method" not in k
    rule = STYLES.split(".panel.is-advanced {", 1)[1].split("}", 1)[0]
    assert "display: none" in rule
    # The rule is scoped to whole panels, never to caveat or callout classes.
    assert not re.search(r"\.mode-simple[^{]*\.(caveat|callout|scan-blind)", STYLES)


# ------------------------------------------------------------------- the note

def test_the_view_says_how_many_it_hid():
    body = APP_JS.split("function applyUiMode(", 1)[1].split("\nfunction ", 1)[0]
    assert "data-mode-note" in body
    assert "${hidden}" in body
    assert "data-set-mode=\"pro\"" in body, "no way back from the note"


def test_the_note_describes_what_it_hid_per_view():
    """It said "options and positioning" everywhere, which was written for
    Analysis and was untrue on Long-Term (a valuation panel) and Macro (ratio
    pairs). A note that misdescribes what it hid is worse than a generic one."""
    assert "const ADVANCED_NOUN = {" in APP_JS
    block = APP_JS.split("const ADVANCED_NOUN = {", 1)[1].split("\n};", 1)[0]
    for view in ADVANCED_VIEWS:
        assert f"{view}:" in block, view
    body = APP_JS.split("function applyUiMode(", 1)[1].split("\nfunction ", 1)[0]
    assert "advancedNoun(view)" in body
    assert "options and positioning panel" not in body


def test_there_is_no_note_when_nothing_was_hidden():
    """Earnings has no advanced set. A "0 panels hidden" note is noise."""
    body = APP_JS.split("function applyUiMode(", 1)[1].split("\nfunction ", 1)[0]
    assert "if (!hidden) return;" in body


def test_switching_back_unhides_everything():
    body = APP_JS.split("function applyUiMode(", 1)[1].split("\nfunction ", 1)[0]
    assert "p.hidden = false" in body
    assert "classList.remove('is-advanced')" in body


def test_both_the_attribute_and_the_class_are_set():
    """An author `display` beats the UA stylesheet's [hidden] { display: none }
    whatever the specificity — CLAUDE.md, after .set-pw rendered a password form
    open on every visit to Settings. The class carries the display and the
    attribute carries the semantics."""
    body = APP_JS.split("function applyUiMode(", 1)[1].split("\nfunction ", 1)[0]
    assert "classList.add('is-advanced')" in body
    assert "panel.hidden = true" in body


# --------------------------------------------------- panels that arrive later

def test_panels_mounted_after_the_render_pass_are_caught():
    """Several panels are filled by their own request into a host div — the P/E
    history on Long-Term, corporate actions, pattern base rates — so they do not
    exist when applyUiMode runs. Measured: Long-Term hid one of its two advanced
    panels and the one it missed was the one behind an async fetch."""
    assert "function watchForLatePanels()" in APP_JS
    body = APP_JS.split("function watchForLatePanels()", 1)[1].split("\nwatchForLatePanels", 1)[0]
    assert "MutationObserver" in body
    assert "requestAnimationFrame" in body, "unthrottled: a host filling in would thrash"
    assert "uiMode() !== 'simple'" in body, "the observer runs in Pro for nothing"


def test_the_observer_only_reacts_to_panels():
    """Attribute churn and text updates are most of what happens in a view."""
    body = APP_JS.split("function watchForLatePanels()", 1)[1].split("\nwatchForLatePanels", 1)[0]
    assert "addedNodes" in body
    assert "classList?.contains('panel')" in body


# -------------------------------------------- the controls that count panels

def test_the_section_index_skips_hidden_panels():
    """`[data-collapsible="1"]` alone includes them: the attribute is set by
    makePanelsCollapsible and hiding does not remove it. The index listed nine
    panels that were not on the page, so every one of those chips was a jump
    link to a hidden element."""
    assert "const REACHABLE_PANELS =" in APP_JS
    assert ":not([hidden])" in APP_JS.split("const REACHABLE_PANELS =", 1)[1][:120]
    for fn in ("function buildSectionIndex(", "function addBulkControl(",
               "function setAllPanels("):
        body = APP_JS.split(fn, 1)[1].split("\n}\n", 1)[0]
        assert "REACHABLE_PANELS" in body, fn
        assert "'.panel[data-collapsible=\"1\"]'" not in body, f"{fn} still uses the bare selector"


def test_expand_all_does_not_open_what_you_cannot_see():
    """Over the bare selector it expanded nine hidden panels and recorded that
    state, so switching back to Pro found them all open."""
    body = APP_JS.split("function setAllPanels(", 1)[1].split("\n}\n", 1)[0]
    assert "REACHABLE_PANELS" in body


def test_the_mode_runs_before_the_counters():
    """Run after them and the index lists nine hidden panels and the bulk control
    counts them toward its threshold."""
    block = APP_JS.split("makePanelsCollapsible(view);", 1)[1][:600]
    assert block.index("applyUiMode(view)") < block.index("addBulkControl(view)")
    assert block.index("applyUiMode(view)") < block.index("buildSectionIndex(view)")


# ------------------------------------------------------------------ the switch

def test_the_control_is_in_settings_and_wired():
    assert "data-set-mode=" in APP_JS
    assert "closest('[data-set-mode]')" in APP_JS
    block = APP_JS.split("closest('[data-set-mode]')", 1)[1][:200]
    assert "setUiMode(" in block


def test_the_handler_does_not_shadow_the_chart_mode_const():
    """`modeBtn` was already taken in that same listener by data-chart-mode. A
    duplicate const is a SyntaxError, which takes the whole file down rather
    than just that branch — caught by tests/test_js_parses.py."""
    listener = APP_JS.split("closest('[data-chart-mode]')", 1)[1][:1200]
    assert "const modeBtn = evt.target.closest('[data-set-mode]')" not in listener


def test_changing_mode_repaints_the_view_on_screen():
    """The pass runs at render time, so a mode change that only repainted
    Settings would leave the other tabs as they were until the next visit."""
    body = APP_JS.split("function setUiMode(", 1)[1].split("\n}", 1)[0]
    assert "loadView(STATE.view" in body or "renderSettings()" in body
    assert "loadView(STATE.view" in body


@pytest.mark.parametrize("cls", [".panel.is-advanced", ".mode-note"])
def test_the_mode_is_styled(cls):
    assert re.search(re.escape(cls) + r"[\s,{:]", STYLES), f"{cls} has no rule"
