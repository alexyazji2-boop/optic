"""The Pulse header, the context chip, and the page making room for the panel.

Three reports in one sitting, all about Pulse sitting badly on the page:

* "Keep this button next to the close tab at all times." `margin-left: auto`
  sat on `.close`, which pushed only the x to the edge and stranded the history
  button straight after the chip -- so it moved whenever the chip's text did.
* "Explain what the NVDA options means." The chip lists the data Pulse is handed
  with each question, and "options" is the shortest possible name for the
  biggest set: the ticker's whole analysis, the options chain only part of it.
* "All this should collapse when Pulse is dragged to the side." The status line
  and the session strip are siblings of `main`, not children, so main's
  `margin-right` never reached them. Measured at 1600px with the panel dragged
  to 560px: both ran to 1600, under the panel, cut off mid-word. After: both
  end at 1017, 23px short of the edge at 1040, and the same at every drag width
  swept from 320 to 860.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
CSS = (ROOT / "static/styles.css").read_text()


def _strip(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"^\s*//.*$", " ", text, flags=re.M)


CLEAN = _strip(CSS)


def _rule(selector: str) -> str:
    start = CLEAN.index(selector + " {") + len(selector) + 2
    return CLEAN[start:CLEAN.index("}", start)]


# ------------------------------------------------------------- the header


def test_the_close_button_no_longer_takes_the_slack():
    """On `.close` it pushed the x alone, leaving history wherever the chip's
    text happened to end."""
    assert "margin-left: auto" not in _rule("#chat .chat-head .close")


def test_the_chip_takes_the_slack_so_both_buttons_travel_together():
    assert "margin-right: auto" in _rule("#chat .chat-head #chat-ctx")


def test_a_long_context_list_shortens_itself_instead_of_the_buttons():
    """Measured at the panel's narrowest, 319px, with six sets loaded: the
    chip's text ellipsed and both buttons stayed visible, 9px apart."""
    assert "min-width: 0" in _rule("#chat .chat-head #chat-ctx")
    inner = _rule("#chat .chat-head #chat-ctx > span:last-child")
    assert "text-overflow: ellipsis" in inner
    assert "white-space: nowrap" in inner


def test_the_buttons_never_shrink():
    assert "flex-shrink: 0" in _rule("#chat .chat-head .icon-btn, #chat .chat-head .close")


# --------------------------------------------------------------- the chip


def test_the_chip_explains_itself():
    fn = _strip(APP)[_strip(APP).index("function updateChatContext()"):]
    fn = fn[:fn.index("\n}\n")]
    assert "chip.title =" in fn
    assert "It cannot see anything not listed here" in fn, \
        "the other half: what Pulse does not have"


def test_options_is_spelled_out_as_the_whole_analysis():
    """The label undersells it, and that is what was asked about."""
    block = APP[APP.index("const CTX_MEANS = {"):]
    block = block[:block.index("};")]
    assert "dealer gamma" in block and "strike ranker" in block


def test_the_new_copy_carries_no_em_dash():
    """CLAUDE.md: a deliberate pass removed them from reader-facing copy.

    Sliced to exactly the new strings, from the map to the end of the title
    statement. The first version ran on to the next function and failed on an
    em dash in code that predates this change -- a test about new copy has to
    be bounded by the new copy."""
    start = APP.index("const CTX_MEANS = {")
    end = APP.index("'Load a ticker or open Macro to give it the numbers.';", start)
    assert chr(0x2014) not in APP[start:end + 60]


# ------------------------------------------------------- room for the panel


def test_the_status_line_and_session_strip_reserve_the_panel():
    rule = _rule("body.chat-open .statusline,\nbody.chat-open .sessionbar")
    assert "padding-right: calc(var(--chat-w) + var(--space-5))" in rule


def test_they_give_it_back_when_the_panel_covers_the_page():
    rule = _rule("body.chat-full .statusline,\nbody.chat-full .sessionbar")
    assert "padding-right: var(--space-5)" in rule


def test_the_cover_rule_comes_after_the_split_rule():
    """applyChatWidth adds `chat-full` alongside `chat-open`, both selectors
    have the same specificity, and source order is all that decides."""
    assert CLEAN.index("body.chat-open .statusline") < CLEAN.index("body.chat-full .statusline")
