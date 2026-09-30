"""Optic mode and Optic Persona share their row, and their menus stay in Pulse.

Reported as "fix how the dynamic sizing works for optic persona when the panel
becomes smaller". Each box was as wide as its label (177px and 144px, changing
with the choice), and each menu was a fixed 320px opening from its own box's
left edge. Measured at 1470x785: with Pulse at its 382px default the persona
menu ended 139px past the window, at 460px 61px, and at 320px, with the boxes
stacked, 15px. After: the boxes are 172px each side by side at 382px and full
width stacked at 320px, and both menus end inside the panel at all three.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "static/styles.css").read_text()


def _rule(selector):
    at = CSS.index("\n" + selector)
    body = CSS[at:CSS.index("}", at)]
    return re.sub(r"/\*.*?\*/", "", body, flags=re.S)


def test_the_two_controls_split_the_row_and_wrap_to_a_line_each():
    row = _rule(".pulse-persona > .km,\n.pulse-persona > .pp")
    assert "flex: 1 1 150px;" in row and "min-width: 0;" in row
    box = _rule(".pulse-persona .km-btn,\n.pulse-persona .pp-field")
    assert "width: 100%;" in box


def test_a_long_label_ends_in_an_ellipsis_rather_than_widening_its_box():
    label = _rule(".pulse-persona .km-now,\n.pulse-persona .pp-now")
    for decl in ("max-width: 100%;", "overflow: hidden;", "text-overflow: ellipsis;",
                 "white-space: nowrap;"):
        assert decl in label, decl


def test_neither_menu_is_wider_than_the_panel_and_the_persona_menu_opens_leftward():
    menus = _rule(".pulse-persona .km-menu,\n.pulse-persona .oc-menu")
    assert ("max-width: min(calc(var(--chat-w) - 2 * var(--space-3)), "
            "calc(100vw - 2 * var(--space-3)));") in menus
    assert ".pulse-persona .pp .oc-menu { left: auto; right: 0; }" in CSS


def test_the_rule_that_never_applied_is_gone():
    """`.pp-field` is inside `.pp`, not a child of the row."""
    assert ".pulse-persona .pp-field { flex: 0 1 auto; }" not in CSS
