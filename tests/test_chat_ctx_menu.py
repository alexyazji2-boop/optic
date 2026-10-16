"""Milo's "what Milo reads" menu is a surface, not a tint.

2026-10-15, a screenshot of the menu open over the Milo panel with the
panel's own text showing straight through it: "this shows when i click the
market only button, fix this". Its background was `--raised`, a 3% white
wash meant for lifting a card off the panel. A menu that floats over content
needs an opaque surface.
"""

from __future__ import annotations

import re

CSS = open("static/styles.css", encoding="utf-8").read()


def _block(selector):
    return CSS.split("\n" + selector + " {", 1)[1].split("\n}", 1)[0]


def _token(name, scope=":root {"):
    block = CSS.split(scope, 1)[1].split("\n}", 1)[0]
    return re.search(r"--{}:\s*([^;]+);".format(name), block).group(1).strip()


def test_the_menu_paints_an_opaque_surface():
    block = _block(".chat-ctx-menu")
    bg = re.search(r"background:\s*var\(--([\w-]+)\)", block).group(1)
    assert bg != "raised", "--raised is a translucent tint, and the panel shows through it"
    assert bg == "surface-2"


def test_that_surface_is_opaque_in_both_themes():
    dark = _token("asset-raised")
    light = _token("surface-2", ':root[data-theme="light"] {')
    for value in (dark, light):
        assert re.fullmatch(r"#[0-9a-fA-F]{6}", value), value


def test_it_sits_above_the_panel_with_the_shared_elevation():
    block = _block(".chat-ctx-menu")
    assert "position: absolute" in block and "z-index" in block
    assert "box-shadow: var(--elev-2)" in block
