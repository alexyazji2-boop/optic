"""The Pulse empty state, and the control that used to destroy it.

Found while checking Pulse still had everything the TrendSpider backlog lists
under items 19, 20 and 13. It did — twelve starter cards, symbol-aware, six
personas, the format prompt intact — but the expander beneath them was worse
than dead. Clicking "see more examples" removed every card and left an empty
panel with no way back.

The cause was a category error rather than a logic error. `renderPulseEmpty`
decides whether to draw the empty state by asking whether the log holds any
`.msg`, and the boot greeting is added with `addMsg('assistant', ...)` from the
health check. So the moment health resolved, the panel believed a conversation
was under way. Nothing threw; the cards simply went.
"""

from __future__ import annotations

import re
from pathlib import Path

APP_JS = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()


def _starters() -> str:
    return APP_JS.split("const PULSE_STARTERS = [", 1)[1].split("\n];", 1)[0]


# ---------------------------------------------------- what the backlog promised

def test_there_are_twelve_starter_cards():
    assert len(re.findall(r"^\s*\{ need:", _starters(), re.M)) == 12


def test_half_of_them_wait_for_a_symbol():
    """A card that needs data you have not got produces a hedge, not an answer."""
    block = _starters()
    assert len(re.findall(r"need: 'ticker'", block)) == 6
    assert len(re.findall(r"need: null", block)) == 6


def test_the_symbol_cards_actually_name_the_symbol():
    for line in _starters().splitlines():
        if "need: 'ticker'" in line:
            assert "{T}" in line, f"ticker card with no substitution: {line.strip()[:60]}"


def test_four_show_before_the_expander():
    body = APP_JS.split("function pulseStarters(", 1)[1].split("\nfunction ", 1)[0]
    assert "usable.slice(0, 4)" in body


# ------------------------------------------------------------- the actual bug

def test_the_greeting_does_not_count_as_a_conversation():
    """The one-line fix, and the reason the whole file exists."""
    body = APP_JS.split("function renderPulseEmpty(", 1)[1].split("\nfunction ", 1)[0]
    assert ".msg:not(.msg-greeting)" in body, (
        "renderPulseEmpty counts the boot greeting as a message again, which "
        "deletes the starter cards the first time the expander is clicked")


def test_both_greetings_are_marked():
    """There are two — one for a configured assistant and one for an
    unconfigured one — and marking only the happy path would leave the bug live
    for exactly the readers who have not set an API key yet."""
    marks = APP_JS.count("classList.add('msg-greeting')")
    assert marks == 2, f"expected both boot greetings marked, found {marks}"


def test_a_real_message_still_clears_the_empty_state():
    """The check is not pointless — it is what stops the starter cards sitting
    under a live conversation. The fix narrows it; it must not remove it."""
    body = APP_JS.split("function renderPulseEmpty(", 1)[1].split("\nfunction ", 1)[0]
    assert "if (hasMsgs)" in body and "existing.remove()" in body


def test_the_expander_toggles_both_ways():
    assert "data-pulse-more" in APP_JS and "data-pulse-less" in APP_JS
    for attr, expected in (("data-pulse-more", "true"), ("data-pulse-less", "false")):
        handler = APP_JS.split(f"closest('[{attr}]')", 1)[1][:120]
        assert f"pulseStartersExpanded = {expected}" in handler
        assert "renderPulseEmpty()" in handler
