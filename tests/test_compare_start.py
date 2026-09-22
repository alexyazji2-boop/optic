"""Compare stopped asking you to type symbols it already knows you looked at.

Two faults on one screen, both visible in a browser at 800px:

The empty view was 389px and two panels, and the second one said "Enter two
tickers and press Compare" directly beneath a panel holding two ticker fields
and a Compare button. A second panel restating the first is the clearest case
of duplication in the app.

And it left the reader typing symbols from memory on the one page whose job is
putting two of them side by side, while `recentSymbols()` -- local, already
built for the command palette -- knew exactly where this browser had been.

After: one panel, 314px, the loaded symbol already in the first field and the
rest one click each. Measured end to end -- load NVDA, open Compare, click
AAPL -- the fields read NVDA and AAPL with no typing, and both names drop out
of the offered list as they are used.
"""

from __future__ import annotations

import re

APP = open("static/app.js", encoding="utf-8").read()
CSS = open("static/styles.css", encoding="utf-8").read()

# Comments stripped, because the comment explaining a removal quotes the thing
# it removed -- and a bare substring check cannot tell the two apart. This is
# the same trap that let a deleted setAttribute survive its own test once.
CODE = re.sub(r"//[^\n]*", "", re.sub(r"/\*.*?\*/", "", APP, flags=re.S))


def _fn(name, end="\n}"):
    return APP.split(name, 1)[1].split(end, 1)[0]


# ------------------------------------------------------- the duplicate panel


def test_the_panel_that_restated_the_button_is_gone():
    assert "Enter two tickers and press" not in CODE
    fn = _fn("function renderCompare(c) {")
    assert "if (!c) return head;" in fn, \
        "nothing run yet is the controls alone, not the controls plus a caption"


def test_the_instruction_survives_where_there_is_nothing_to_offer():
    """A first visit has no history. Saying "nothing is fetched until you
    press Compare" is the honest empty state of the picks row -- better than
    filler tickers nobody chose, and it is a caption now rather than a panel."""
    fn = _fn("function comparePicksHTML() {")
    assert "Nothing is fetched until you press Compare." in fn
    assert "cmp-hint" in fn
    assert ".cmp-hint {" in CSS


# ------------------------------------------------------------ carried context


def test_arriving_with_a_symbol_loaded_brings_it_with_you():
    """Drilling into a comparison should not lose the thing you are comparing
    from. The palette already did this; arriving by the nav was the one route
    that did not."""
    assert "function seedCompareFromContext() {" in APP
    assert "seedCompareFromContext();" in _fn("async function loadCompare(force) {")


def test_it_never_overwrites_something_already_typed():
    fn = _fn("function seedCompareFromContext() {")
    assert "if (inputs.some((v) => String(v || '').trim())) return;" in fn
    assert "if (!STATE.ticker) return;" in fn


def test_clearing_a_field_and_leaving_sticks():
    """Seeding on the way in rather than on every render. Re-seeding per paint
    would refill a field the reader had just emptied, which is the version of
    this that feels haunted."""
    assert "seedCompareFromContext" not in _fn("function renderCompare(c) {")


# ------------------------------------------------------------- the picks row


def test_the_picks_come_from_where_this_browser_has_been():
    """Local, no request, nothing account-backed -- the same list the command
    palette offers."""
    fn = _fn("function comparePicksHTML() {")
    assert "recentSymbols()" in fn
    assert "function recentSymbols() {" in APP


def test_a_symbol_already_in_a_field_is_not_offered_again():
    fn = _fn("function comparePicksHTML() {")
    assert "const taken = new Set((STATE.compareInputs || [])" in fn
    assert "!taken.has(sym)" in fn


def test_a_pick_fills_the_first_empty_field():
    fn = _fn("  const cmpPick = evt.target.closest('[data-cmp-pick]');", "\n  if (evt.target.closest('[data-cmp-add]'))")
    assert "const slot = inputs.findIndex((v) => !String(v || '').trim());" in fn
    assert "if (slot >= 0) inputs[slot] = cmpPick.dataset.cmpPick;" in fn


def test_a_pick_never_overwrites_a_field_that_has_something_in_it():
    """Saving one keystroke is not worth throwing away a symbol the reader
    typed. With every field full it appends, and with four already it does
    nothing -- four is the API's ceiling."""
    fn = _fn("  const cmpPick = evt.target.closest('[data-cmp-pick]');", "\n  if (evt.target.closest('[data-cmp-add]'))")
    assert "else if (inputs.length < 4) inputs.push(cmpPick.dataset.cmpPick);" in fn
    assert "else return;" in fn


def test_the_ceiling_matches_the_one_the_add_button_enforces():
    """Two places now decide how many tickers Compare takes. They have to
    agree, or the picks row can build a comparison the controls cannot."""
    render = _fn("function renderCompare(c) {")
    assert "(STATE.compareInputs || []).length < 4" in render
    handler = _fn("  const cmpPick = evt.target.closest('[data-cmp-pick]');", "\n  if (evt.target.closest('[data-cmp-add]'))")
    assert "inputs.length < 4" in handler
