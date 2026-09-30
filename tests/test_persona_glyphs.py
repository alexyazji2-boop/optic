"""Every Optic Persona glyph draws as an emoji, the size of the Optic mode one.

Asked for with a screenshot of the Optic Persona box, its scales small beside
the text: "make the emojis the same size as the financially literate ones".
The scales (U+2696), the shield (U+1F6E1) and the pawn (U+265F) are text
symbols by default, so the browser drew them as small monochrome characters
beside the mode box's full-size emoji. With U+FE0F, the emoji presentation
selector, each measured 15x19px in the Pulse panel, the same as the mode
box's chart emoji.
"""
from __future__ import annotations

import re
from pathlib import Path

from app import ai, knowledge

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()

# Symbols that draw as text unless asked otherwise. Everything below U+1F000
# is, and these are the ones above it the personas could plausibly use.
TEXT_DEFAULT_ABOVE = {0x1F6E1, 0x1F321, 0x1F336, 0x1F37D, 0x1F396, 0x1F397, 0x1F399,
                      0x1F39E, 0x1F39F, 0x1F3CB, 0x1F3CC, 0x1F3CD, 0x1F3CE, 0x1F441,
                      0x1F4FD, 0x1F549, 0x1F54A, 0x1F56F, 0x1F570, 0x1F573, 0x1F574,
                      0x1F575, 0x1F576, 0x1F577, 0x1F578, 0x1F579, 0x1F587, 0x1F58A,
                      0x1F58B, 0x1F58C, 0x1F58D, 0x1F590, 0x1F5A5, 0x1F5A8, 0x1F5B1,
                      0x1F5B2, 0x1F5BC, 0x1F5C2, 0x1F5C3, 0x1F5C4, 0x1F5D1, 0x1F5D2,
                      0x1F5D3, 0x1F5DC, 0x1F5DD, 0x1F5DE, 0x1F5E1, 0x1F5E3, 0x1F5E8,
                      0x1F5EF, 0x1F5F3, 0x1F5FA, 0x1F6CB, 0x1F6CD, 0x1F6CE, 0x1F6CF,
                      0x1F6E0, 0x1F6E2, 0x1F6E3, 0x1F6E4, 0x1F6E5, 0x1F6E9, 0x1F6F0,
                      0x1F6F3}


def _needs_selector(glyph):
    first = ord(glyph[0])
    return first < 0x1F000 or first in TEXT_DEFAULT_ABOVE


def test_every_persona_glyph_draws_as_an_emoji():
    for key, persona in ai.PERSONAS.items():
        glyph = persona["glyph"]
        if _needs_selector(glyph):
            assert glyph.endswith("️"), key


def test_the_three_that_were_text_now_carry_the_selector():
    assert ai.PERSONAS["neutral"]["glyph"] == "⚖️"
    assert ai.PERSONAS["stoic"]["glyph"] == "\U0001F6E1️"
    assert ai.PERSONAS["skeptic"]["glyph"] == "♟️"


def test_the_mode_glyphs_need_none_and_the_page_fallback_matches_the_server():
    for mode in knowledge.MODES.values():
        assert not _needs_selector(mode["glyph"]), mode["glyph"]
    assert "{ id: 'neutral', glyph: '\\u2696\\uFE0F', label: 'Neutral analyst'," in APP
