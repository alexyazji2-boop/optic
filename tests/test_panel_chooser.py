"""The reader's own layout: hide any panel, on any tab.

Simple and Pro are two presets. This is the third case — the reader who wants
eight of the nine options panels, or who never looks at Seasonality.

Deliberately the same shape as the collapse memory, which has always worked this
way: a preset decides the initial value and an explicit choice overrides it. One
question per panel, visible or not, rather than two overlapping states to reason
about, and "reset" means forgetting the choices rather than computing an inverse.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP_JS = (ROOT / "static" / "app.js").read_text()
STYLES = (ROOT / "static" / "styles.css").read_text()


def _code(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"^\s*//.*$", " ", text, flags=re.M)


def _fn(name: str) -> str:
    return _code(APP_JS.split(f"function {name}(", 1)[1].split("\nfunction ", 1)[0])


# ------------------------------------------------------------- the resolution

def test_a_choice_beats_the_preset():
    body = _fn("panelIsHidden")
    assert "hasOwnProperty.call(chosen, id)" in body, \
        "an explicit choice must win over the mode"
    assert "uiMode() === 'simple'" in body and "isAdvancedPanel" in body


def test_no_opinion_and_explicitly_shown_stay_distinguishable():
    """Storing `false` for "show this" is not the same as storing nothing: the
    first must survive a switch to Simple, the second must follow it. So a
    shown panel is a deleted key, not a false one."""
    body = _fn("setPanelHidden")
    assert "delete all[id]" in body
    assert "all[id] = true" in body


def test_the_key_is_the_one_the_collapse_memory_uses():
    """Two id schemes for the same panel would eventually disagree about which
    panel they describe."""
    assert "panelId(view, title)" in _fn("panelIsHidden")
    assert "panelId(view, raw)" in _fn("panelChooserHTML")


def test_reset_is_scoped_to_one_view():
    """Resetting Analysis must not un-hide the five panels someone chose to drop
    from Macro."""
    body = _fn("clearHiddenPanels")
    assert "startsWith(view + '|')" in body


def test_private_mode_does_not_break_it():
    for name in ("hiddenPanels", "setPanelHidden", "clearHiddenPanels"):
        assert "catch" in _fn(name), name


# ------------------------------------------------------------------ the pass

def test_the_pass_runs_in_both_modes():
    """A panel can be hidden in Pro now, so there is no mode in which
    applyUiMode can return early."""
    body = _fn("applyUiMode")
    assert "panelIsHidden(view, title)" in body
    assert "classList.toggle('is-advanced', hide)" in body
    assert "panel.hidden = hide" in body


def test_the_note_says_which_of_the_two_hid_them():
    """The remedies are different: one is a mode switch, the other is a choice
    this reader made. A single count would offer the wrong fix for half of it."""
    body = _fn("applyUiMode")
    assert "byMode" in body and "mine" in body
    assert "by Simple mode and" in body
    assert "you chose to hide" in body


def test_the_note_only_offers_the_mode_switch_when_the_mode_did_it():
    body = _fn("applyUiMode")
    assert 'byMode ? ` \\u00b7 <button' in body or "byMode ?" in body
    assert "data-panels-open" in body, "no way into the chooser from the note"


# ---------------------------------------------------------------- the dialog

def test_it_is_one_dialog_not_a_control_per_heading():
    """A heading already carries a collapse toggle and an Ask-Pulse button. A
    third would make the thing you click to read a panel the smallest target
    on it."""
    assert "function panelChooserHTML(" in APP_JS
    assert 'class="pch"' in APP_JS
    assert "role=\"dialog\"" in APP_JS.split("function panelChooserHTML(", 1)[1][:1600]


def test_a_panel_with_no_heading_is_not_offered():
    """There would be nothing to name it in the list, which is the same reason
    makePanelsCollapsible skips them."""
    body = _fn("panelChooserHTML")
    assert "if (!title) return null" in body
    assert "mode-note" in body, "the note itself would appear in its own list"


def test_the_heading_is_stripped_of_its_chrome():
    """textContent alone produced "GEX. Dealer gamma exposureAsk Pulse" in the
    section index, for the same reason."""
    body = _fn("panelChooserHTML")
    assert "cloneNode(true)" in body
    assert "querySelectorAll('button" in body


def test_the_specialist_panels_are_marked():
    """So the reader can see which ones Simple mode would have taken, rather
    than having to switch modes to find out."""
    body = _fn("panelChooserHTML")
    assert "r.advanced" in body and "pch-tag" in body


def test_the_list_is_capped_and_scrolls():
    """Macro has fourteen panels and Analysis twenty-two. A dialog taller than
    the window puts its reset button off screen."""
    rule = STYLES.split(".pch-list {", 1)[1].split("}", 1)[0]
    assert "max-height" in rule and "overflow-y: auto" in rule


# ------------------------------------------------------------------- wiring

@pytest.mark.parametrize("attr,handler", [
    ("data-panels-open", "openPanelChooser"),
    ("data-panels-close", "closePanelChooser"),
    ("data-panels-reset", "clearHiddenPanels"),
])
def test_every_control_has_a_handler(attr, handler):
    assert f"closest('[{attr}]')" in APP_JS, f"{attr} has no handler"
    block = APP_JS.split(f"closest('[{attr}]')", 1)[1][:400]
    assert handler in block, f"{attr} does not reach {handler}"


def test_the_dialog_does_not_stop_clicks_from_reaching_the_document():
    """The first version put onclick="event.stopPropagation()" on the dialog so
    clicks inside it would not reach the backdrop's close handler. That also
    stopped them reaching `document`, which is where every delegated handler in
    this file lives — so Reset and the × took the click and did nothing, while
    the checkboxes carried on working because they fire `change` rather than
    bubbling a click."""
    # Comments stripped: the function carries a note naming stopPropagation on
    # purpose, so nobody reintroduces it. Third time this file has needed that.
    assert "stopPropagation" not in _fn("panelChooserHTML")


def test_the_backdrop_closes_only_on_itself():
    assert "matches('[data-panels-backdrop]')" in APP_JS


def test_escape_closes_it():
    assert "evt.key === 'Escape' && document.querySelector('.pch-back')" in APP_JS


def test_ticking_does_not_rebuild_the_dialog():
    """Rebuilding replaced the checkbox that had just been clicked: focus went to
    the body, so a keyboard reader lost their place after every tick, and two
    quick clicks landed the second on a detached node. Same lesson as the
    watchlist search repainting only the feed."""
    block = _code(APP_JS.split("if (t.dataset.panelShow !== undefined) {", 1)[1][:900])
    assert "openPanelChooser(" not in block, "the dialog is being rebuilt on every tick"
    assert "applyUiMode(STATE.view)" in block, "the page is not updated"
    assert ".pch-foot .subnote" in block, "the count would go stale"


def test_the_chooser_is_reachable_from_both_bulk_bars():
    """The section index carries them on views with six or more panels and the
    standalone bar on the ones below that. A control on one is missing on half
    the tabs."""
    for cls in ("sec-bulk-btn", "bulk-btn"):
        block = APP_JS.split(f'class="{cls}" data-bulk="open"', 1)[1][:400]
        assert "data-panels-open" in block, cls


@pytest.mark.parametrize("cls", [".pch-back", ".pch", ".pch-head", ".pch-x",
                                 ".pch-list", ".pch-tag", ".pch-foot"])
def test_the_dialog_is_styled(cls):
    assert re.search(re.escape(cls) + r"[\s,{:]", STYLES), f"{cls} has no rule"
