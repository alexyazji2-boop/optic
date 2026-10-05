"""The notice above the Pulse conversation sits inset, not edge to edge.

Reported as "center the not financial advice text more on pulse, its goes
exactly from border to border". `.legal-area` carries no padding because
everywhere else it sits inside a panel that has some; in Pulse its parent is
the bare scroller. Measured in the running panel at 711px: the text ran 0px
from either edge, and with this it starts 19px in, the conversation's own inset.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "static/styles.css").read_text()
HTML = (ROOT / "static/index.html").read_text()
NO_COMMENTS = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)


def test_the_notice_is_a_direct_child_of_the_scroller():
    """What the rule below selects. If the notice moves into a padded box this
    rule should go, or the inset doubles."""
    body = HTML[HTML.index('<div class="chat-body" id="chat-body">'):]
    body = body[:body.index('<div class="chat-foot">')]
    assert '<div class="legal-area" id="pulse-legal" role="note"></div>' in body


def test_it_takes_the_conversations_inset_on_both_sides():
    rule = re.search(r"\n#chat \.chat-body > \.legal-area \{([^}]*)\}", NO_COMMENTS)
    assert rule, "the notice is edge to edge again"
    assert "padding: var(--space-3) var(--space-4) 0;" in rule.group(1)
    log = re.search(r"\n#chat \.chat-log \{([^}]*)\}", NO_COMMENTS).group(1)
    assert "padding: var(--space-3) var(--space-4);" in log, "the log's step moved; match it"
