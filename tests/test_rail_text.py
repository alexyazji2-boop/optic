"""The sidebar's text, a step brighter.

Asked for with a screenshot of the rail: "make the side bar text a bit more
visible on the website version". The labels, the footer's two buttons and the
wordmark were all --ink-2, and the section icons sat at 85% opacity. They take
--rail-ink now, 70% of the way from --ink-2 to --ink, and the icons are drawn
at full strength. The current section keeps the full --ink, its raised
background and its blue edge, so it still stands out from the rest.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "static/styles.css").read_text()
CODE = re.sub(r"/\*.*?\*/", " ", CSS, flags=re.S)


def _rule(selector):
    m = re.search(r"(?m)^" + re.escape(selector) + r"\s*\{([^}]*)\}", CODE)
    assert m, selector
    return m.group(1)


def _hex(name, block=CODE):
    return re.search(r"--%s:\s*(#[0-9a-fA-F]{6})" % name, block).group(1)


def _luminance(hexcol):
    def chan(v):
        v = v / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hexcol[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)


def _contrast(a, b):
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _mix(a, b, share):
    """color-mix(in srgb, a share, b), which mixes the encoded channels."""
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join("%02x" % round(share * x + (1 - share) * y) for x, y in zip(ca, cb))


def test_the_rail_has_its_own_ink_between_the_two():
    assert ":root { --rail-ink: color-mix(in srgb, var(--ink) 70%, var(--ink-2)); }" in CODE


def test_every_piece_of_sidebar_text_takes_it():
    assert "color: var(--rail-ink);" in _rule(".rail nav.tabs-group .nav-top")
    assert "color: var(--rail-ink);" in _rule(".rail-label")
    assert "color: var(--rail-ink);" in _rule(".rail-foot .icon-btn")
    assert "color: var(--rail-ink);" in _rule(".rail .brand-text")
    assert "opacity: 1;" in _rule(".nav-icon")


def test_the_current_section_still_stands_out():
    active = _rule('.rail nav.tabs-group .nav-top[aria-selected="true"],\n'
                   '.rail nav.tabs-group .nav-item.on > .nav-top')
    assert "color: var(--ink);" in active and "background: var(--surface-2);" in active
    # Marked by a raised pill and a gold glyph since 2026-10-08, when the
    # blue edge on a square box beside a gold hover pill was reported as one
    # of "ALOT of inconsistencies". Still marked, just in the rail's own terms.
    assert "border-radius: var(--r-pill);" in active
    assert (".rail nav.tabs-group .nav-item.on > .nav-top .nav-icon { color: var(--hover-gold); }"
            in CSS)
    assert "color: var(--ink);" in _rule(".rail nav.tabs-group .nav-top:hover")


def test_it_is_more_visible_in_the_dark_theme_than_it_was():
    """On the rail's own plane, the restyle's surface."""
    ink, ink2 = _hex("ink"), _hex("ink-2")
    rail = _hex("asset-surface")
    before = _contrast(ink2, rail)
    after = _contrast(_mix(ink, ink2, 0.7), rail)
    assert before < after, (before, after)
    assert round(before, 1) == 10.7 and after > 14
