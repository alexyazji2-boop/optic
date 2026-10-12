"""Panel names survive the Simple level's inline glossary.

At Simple, glossTerm renders a heading's words as `<button class="gloss-term
is-inline">`, so a heading that is wholly a glossary term (hg() on a
HEADER_DEFS entry) is one button. headingName stripped every button to drop
the Ask-Pulse chip and the collapse toggle, and took the heading's words with
them: an empty name, so makePanelsCollapsible skipped the panel and
panelMinLevel answered "always show". Simple then opened every glossed panel,
the opposite of what it is for (ux/UX.md section 0.1, 2026-10-11).
"""
import re
from pathlib import Path

APP = (Path(__file__).resolve().parent.parent / "static/app.js").read_text()


def _fn(name):
    body = APP[APP.index("function %s(" % name):]
    return body[:body.index("\n}\n")]


def test_the_strip_list_keeps_glossary_terms():
    strip = re.search(r"clone\.querySelectorAll\('([^']+)'\)", _fn("headingName")).group(1)
    first = strip.split(",")[0].strip()
    assert first == "button:not(.gloss-term)", strip
    # The other chrome still goes.
    for sel in (".gloss-inline", ".th-plain", ".lvl-count", ".chip", ".bk-active", ".spec-tag"):
        assert sel in strip, sel


def test_the_inline_glossary_is_a_button_with_that_class():
    """The exception only works while the inline term carries the class."""
    gloss = _fn("glossTerm")
    assert 'class="gloss-term is-inline"' in gloss and "<button" in gloss


def test_title_casing_makes_the_same_exception():
    assert "button:not(.gloss-term)" in re.search(r"const TITLE_SKIP = '([^']+)'", APP).group(1)
