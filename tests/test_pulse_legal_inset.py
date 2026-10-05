"""The notice above the Pulse conversation sits centred in the panel.

Reported twice: "center the not financial advice text more on pulse, its goes
exactly from border to border", and then, with a screenshot, "it is still on
the border, center it more". `.legal-area` carries no padding because
everywhere else it sits inside a panel that has some; in Pulse its parent is
the bare scroller. It is a card now. Measured in the running panel: docked at
520px the card is 19px from the left edge and 18px from the right, its text
34px and 36px in; dragged to 1100px it holds a 72ch measure, 254px and 253px
from each edge.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "static/styles.css").read_text()
HTML = (ROOT / "static/index.html").read_text()
NO_COMMENTS = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)


def _rule():
    found = re.search(r"\n#chat \.chat-body > \.legal-area \{([^}]*)\}", NO_COMMENTS)
    assert found, "the notice is edge to edge again"
    return found.group(1)


def test_the_notice_is_a_direct_child_of_the_scroller():
    """What the rule selects. If the notice moves into a padded box this rule
    should go, or the inset doubles."""
    body = HTML[HTML.index('<div class="chat-body" id="chat-body">'):]
    body = body[:body.index('<div class="chat-foot">')]
    assert '<div class="legal-area" id="pulse-legal" role="note"></div>' in body


def test_it_keeps_clear_of_both_edges_at_any_width():
    """A width that leaves the margins, and auto margins to centre it. With
    auto margins alone it is back on the border whenever the panel is
    narrower than the measure."""
    rule = _rule()
    assert "width: calc(100% - 2 * var(--space-4));" in rule
    assert "margin: var(--space-3) auto var(--space-1);" in rule
    assert "box-sizing: border-box;" in rule
    assert "max-width: 72ch;" in rule, "centred, at a measure, in a wide panel"


def test_it_reads_as_a_card_rather_than_loose_text():
    rule = _rule()
    for decl in ("padding: var(--space-3);", "background: var(--surface-2);",
                 "border: 1px solid var(--border);", "border-radius: var(--r-md);"):
        assert decl in rule, decl
