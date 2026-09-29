"""The home page's search results sit above the blocks after them.

Reported with a screenshot of ORCL's matches drawn under the "Or jump to"
chips and the Today card. The list's z-index 80 only counts inside its own
stacking context, and `.reveal`'s entrance leaves every revealed block one
(fill-mode `both` keeps the transform), so the chips and the card, revealed
after the form, painted over it. Checked in a browser at 600px: 39 points
sampled across the open list all hit the list, where the chips had covered
it before.
"""
from __future__ import annotations

import re
from pathlib import Path

CSS = (Path(__file__).resolve().parent.parent / "static/styles.css").read_text()


def test_the_search_form_is_a_layer_above_what_follows_it():
    rules = re.findall(r"^\.home-search \{([^}]*)\}", CSS, re.M)
    joined = " ".join(rules)
    assert "position: relative" in joined and re.search(r"z-index:\s*[1-9]", joined), rules


def test_the_cause_is_still_there_so_the_layer_is_still_needed():
    # If the reveal stops leaving a transform behind, this layer can go; until
    # then removing it puts the results back under the chips.
    assert re.search(r"\.reveal \{ animation: panel-in [^}]* both; \}", CSS)
    assert "to   { opacity: 1; transform: none; }" in CSS
