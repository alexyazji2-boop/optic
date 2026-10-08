"""Every button's hover is the same outlined pill, in the Optic mark's gold.

Asked for on 2026-10-08 as "from now on, every time you hover over a button,
use [the 'Why the gap?' chip] as a reference, but change the color scheme to
the gold in the optic logo".
"""
from pathlib import Path

CSS = (Path(__file__).resolve().parent.parent / "static/styles.css").read_text()


def _block(head):
    at = CSS.index(head)
    return CSS[at:CSS.index("}", at)]


def test_the_hover_reaches_every_kind_of_button_and_skips_disabled_ones():
    rule = _block('  button:not(:disabled):not([aria-disabled="true"]):not(.primary):hover,')
    assert 'summary:not(:disabled):not([aria-disabled="true"]):hover,' in rule
    assert '[role="button"]:not(:disabled):not([aria-disabled="true"]):not(.clamp-prose):hover {' in rule
    assert "border-radius: var(--hover-r, var(--r-pill));" in rule
    assert "var(--hover-gold)" in rule and "color: var(--ink);" in rule
    assert "@media (hover: hover) {\n  button:not(:disabled)" in CSS, "no sticky hover after a tap"


def test_the_gold_is_the_marks_gold_and_holds_up_on_white():
    assert "--hover-gold: var(--asset-brand);" in CSS
    assert "--hover-gold: color-mix(in srgb, var(--asset-brand) 72%, var(--ink));" in CSS
    assert "--asset-brand: #d4b144;" in CSS


def test_nothing_moves_when_the_pointer_arrives():
    rule = _block('  button:not(:disabled):not([aria-disabled="true"]):not(.primary):hover,')
    assert "padding" not in rule and "border-width" not in rule and "margin" not in rule
    assert "box-shadow:" in rule


def test_cards_keep_their_corners_and_bare_links_get_room():
    assert ":where(.ov-card, .pulse-card) { --hover-r: var(--r-md); }" in CSS
    assert ":where(summary, .hm-more, .ht-more, .ht-rest, .foot-link, .cs-note-btn) {" in CSS


def test_the_primary_button_keeps_its_gold_fill():
    rule = _block('  .btn.primary:not(:disabled):not([aria-disabled="true"]):hover {')
    assert "background" not in rule and "var(--hover-gold)" in rule
