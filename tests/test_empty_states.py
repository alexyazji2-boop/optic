"""The third state.

`loadingHTML` and `errorHTML` have been shared helpers from the start. There
was no `emptyHTML`, so every call site wrote its own sentence -- twenty-five of
them -- and the "no symbol" panel got written twice, byte for byte, inline
styles and all. Two copies of a string is a drift waiting for whichever one
gets edited first.

What made it worth extracting is not the duplication, though: it is what the
copy did. "No ticker loaded" names an absence and stops. A reader who did not
already know a symbol was needed has learnt only that something is missing, and
the one control offered sent them to a different page to find it. The rule the
helper encodes is: say what would fill the space, then offer the control that
fills it, on the panel where the gap is.

Driven in a browser: the panel renders, the button opens the palette, and the
panel is no longer folded into its own title.
"""

from __future__ import annotations

import re

APP = open("static/app.js", encoding="utf-8").read()
CSS = open("static/styles.css", encoding="utf-8").read()


def _code(src):
    """A comment explaining why the inline style went away contains the inline
    style. Strip both comment forms before asserting anything about code."""
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", "", src)


def _fn(name, src):
    start = src.index("function %s(" % name)
    nxt = src.find("\nfunction ", start + 1)
    return src[start:nxt if nxt > 0 else len(src)]


def test_the_empty_state_is_a_helper_beside_the_other_two():
    code = _code(APP)
    for name in ("loadingHTML", "errorHTML", "emptyHTML"):
        assert "function %s(" % name in code, "%s is missing" % name


def test_it_offers_a_control_and_not_just_a_sentence():
    """The whole point. A title and a sub with no action is the state this
    replaced, and it would still pass a test that only checked for a panel."""
    fn = _fn("emptyHTML", _code(APP))
    assert "empty-acts" in fn
    assert 'class="btn"' in fn, "the action has to be the app's button"
    assert "action.attr" in fn and "action.label" in fn


def test_the_action_is_a_data_attribute_rather_than_a_callback():
    """This returns a string into innerHTML, so a closure passed in here would
    be dropped silently and the button would render and do nothing."""
    fn = _fn("emptyHTML", _code(APP))
    assert "${action.attr}" in fn
    assert "onclick" not in fn.lower()


def test_the_panel_does_not_fold_itself_shut():
    """`makePanelsCollapsible` turns any `.panel` with its own h2 into a
    disclosure. The empty state is a `.panel` with an h2, so it was folded to a
    chevron with the sentence and the button hidden behind it -- measured in a
    browser, which is the only way this was ever going to be noticed.

    `data-fixed="1"` is the opt-out the function already honours for card grids
    that are not sections."""
    fn = _fn("emptyHTML", _code(APP))
    assert 'data-fixed="1"' in fn, "without this the empty state collapses"
    # And the opt-out still means what it meant.
    collapse = _fn("makePanelsCollapsible", _code(APP))
    assert "dataset.fixed === '1'" in collapse and "return" in collapse


def test_no_call_site_still_hand_rolls_the_no_symbol_panel():
    """Both copies carried the same inline style, which is the tell: a button
    that needs `style="padding:..."` is a button the component system is not
    reaching."""
    code = _code(APP)
    assert "No ticker loaded</h2>" not in code
    assert 'data-goto-home style="padding' not in code
    # The helper is the only thing building this panel now.
    assert code.count("'No symbol loaded',") == 2, \
        "both ticker-guard call sites should route through emptyHTML"


def test_one_word_for_one_thing():
    """The panel said "symbol" and the status line said "ticker" for the same
    absence, in the same moment, eight pixels apart."""
    code = _code(APP)
    assert "No ticker loaded. Enter a symbol to begin." not in code
    assert "No symbol loaded. Search for one to begin." in code


def test_the_empty_state_borrows_the_error_states_spacing():
    """Two panels a reader meets in the same session, both a sentence followed
    by the control that answers it. Different action offsets would be the
    radius families again in a different property."""
    empty = re.search(r"\.empty-acts\s*\{([^}]*)\}", CSS)
    error = re.search(r"\.error-acts\s*\{([^}]*)\}", CSS)
    assert empty and error
    def gap(b):
        return re.search(r"margin-top:\s*([^;]+)", b.group(1)).group(1).strip()
    assert gap(empty) == gap(error), "empty and error actions sit at different offsets"
