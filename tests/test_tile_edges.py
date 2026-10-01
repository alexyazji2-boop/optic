"""A tile in a panel grid keeps its edges.

Reported with a picture of the Strike & entry tiles: "these boxes are fading
away, fix this and keep the text within the boxes". Every child of a grid in
a panel carries scroll shadows, four gradients whose two covers hide the
shades by matching what is under them, and the covers were the panel's
colour. A tile has a fill of its own, so they painted a 34px fade over both of
its edges, and the box read narrower than its text. 53 tiles across Options,
Earnings, Investing, Macro and Indices; nothing else in a panel grid has a
fill.

Checked in a browser on NVDA's Options tab: the covers were rgb(19, 21, 23) on
an rgb(35, 35, 38) tile and are rgb(35, 35, 38), and the four tiles' edges are
square.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "static/styles.css").read_text()


def _rule(selector):
    m = re.search(r"(?m)^" + re.escape(selector) + r" \{\n(.*?)\n\}", CSS, re.S)
    return m.group(1) if m else ""


def test_the_covers_are_the_box_own_fill():
    rule = _rule(".scroll-y,\n.panel .grid > *")
    assert rule, "the scroll shadow rule moved"
    covers = re.findall(r"linear-gradient\(to (?:right|left), (.*?) 40%", rule)
    assert covers == ["var(--scroll-cover, var(--surface))"] * 2, covers


def test_a_tile_names_its_fill_as_the_cover():
    tile = _rule(".tile")
    assert "--scroll-cover: var(--surface-2);" in tile
    assert "background: var(--surface-2);" in tile, "the cover is the tile's own fill"
