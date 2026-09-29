"""The rail's sections never overlap what is under them.

Reported with a screenshot: Reports printed across the RECENT heading. The
column's sections had `min-height: 0` and a shrink of 1, so a rail with less
height than its content took the shortfall out of them, and they draw overflow
instead of clipping it (the fly-outs need that), so the last section slid over
the list below. Measured at 1280x845 with eight recent symbols: the sections'
box 81-437, their content 440 tall, Reports at 436-484, the heading at 468.

Now the recents, the part built to give way, shrink and scroll. Under 700px
tall they go and the rows tighten; under 520px, a phone on its side, the brand
row and the collapse toggle go too and the touch floor drops to 34px, so
Settings stays on screen. Checked at 1280x845, 760, 720, 700, 650, 600, 560,
1100x500 and 1024x500 in Default and Large text, and at 740x360: nothing past
its box, nothing overlapping, Settings on screen.
"""
from __future__ import annotations

import re
from pathlib import Path

CSS = (Path(__file__).resolve().parent.parent / "static/styles.css").read_text()


def media_block(query):
    head = "@media %s {" % query
    start = CSS.index(head) + len(head)
    depth, i = 1, start
    while depth:
        depth += {"{": 1, "}": -1}.get(CSS[i], 0)
        i += 1
    return CSS[start:i - 1], start


def test_the_sections_do_not_shrink_in_the_column():
    block, at = media_block("(min-width: 560px)")
    # The first (min-width: 560px) block is the one right after the rule it overrides.
    blocks = [m.start() for m in re.finditer(r"@media \(min-width: 560px\) \{", CSS)]
    found = [b for b in blocks if ".rail nav.tabs-group { flex-shrink: 0; }" in CSS[b:b + 200]]
    assert found, "no column rule keeps the sections at their content height"
    assert found[0] > CSS.index(".rail nav.tabs-group { order: 0; flex: 0 1 auto; }"), \
        "it has to come after the unmediated `flex: 0 1 auto` it overrides"


def test_the_recents_are_what_gives_way():
    rule = CSS[CSS.index("  .rail-recent {\n"):]
    rule = rule[:rule.index("}")]
    for decl in ("flex: 1 1 auto;", "min-height: 0;", "overflow-y: auto;"):
        assert decl in rule


def test_a_short_window_keeps_settings_on_screen():
    short, _ = media_block("(min-width: 560px) and (max-height: 699px)")
    assert ".rail-recent { display: none; }" in short
    assert "padding-top: var(--space-1); padding-bottom: var(--space-1);" in short
    tiny, _ = media_block("(min-width: 560px) and (max-height: 519px)")
    assert ".rail > .brand, .rail-foot .rail-toggle { display: none; }" in tiny
    assert ".rail nav.tabs-group .nav-top, .rail .rail-foot .icon-btn { min-height: 34px; }" in tiny, \
        "the coarse-pointer 44px floor is what pushed Settings off a 360px screen"
    assert "z-index: 55;" in tiny, "a fly-out from the second section opens level with the top bar"
