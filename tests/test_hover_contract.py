"""Hover stays inside the control and moves nothing (2026-10-12).

Reported with a screenshot: "Read more" on the Overview took a wide gold oval
that covered the headline above it. The cause was shared: one rule gave every
<summary> and several text links a gold pill painted as a box-shadow spread
6px outside the element's box, with an opaque wash, and a summary is a
full-width block, so the oval spanned the row and spilled onto the lines
around it. The same audit found a gold glow and a 1px lift on primary buttons
and a swatch that grew 12% on hover.

The contract, checked over every :hover rule in the stylesheet:
  - no non-inset box-shadow with a spread, and no glow (blur) drawn outside;
  - no transform, except the named nudges below, which move a small glyph
    inside its own control;
  - no property that changes layout (margin, padding, width, height, border
    width, font size or weight, letter spacing).
Selected, active and focus states are not hover and are not checked here.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "static/styles.css").read_text(encoding="utf-8")
NC = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)

# Glyph motion inside its own control: a gear turning, a caret flipping, an
# arrow nudging 2px. None of them leaves its control's box.
ALLOWED_TRANSFORMS = {
    ".icon-btn:hover .gear",
    ".nav-item:hover .nav-caret",
    ".cc-q:hover::after",
    ".inst-back:hover .inst-back-arrow",
}

LAYOUT = ("margin", "padding", "width", "height", "border-width", "font-size",
          "font-weight", "letter-spacing")


def hover_rules():
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", NC):
        sel, body = " ".join(m.group(1).split()), m.group(2)
        if ":hover" in sel:
            yield sel, body


def test_no_hover_paints_outside_its_box():
    bad = []
    for sel, body in hover_rules():
        for value in re.findall(r"box-shadow\s*:\s*([^;]+)", body):
            for part in re.split(r",(?![^(]*\))", value):
                part = part.strip()
                if part == "none" or "inset" in part:
                    continue
                nums = [float(n) for n in re.findall(r"(-?[\d.]+)px", part)]
                if (len(nums) >= 4 and nums[3] > 0) or (len(nums) >= 3 and nums[2] > 0) or "var(--elev" in part:
                    bad.append((sel, part))
    assert not bad, bad


def test_no_hover_moves_or_resizes_anything():
    moved, resized = [], []
    for sel, body in hover_rules():
        for t in re.findall(r"transform\s*:\s*([^;]+)", body):
            if t.strip() != "none" and not any(a in sel for a in ALLOWED_TRANSFORMS):
                moved.append((sel, t.strip()))
        for prop in LAYOUT:
            if re.search(r"(?<![-\w])" + prop + r"\s*:", body):
                resized.append((sel, prop))
    assert not moved, moved
    assert not resized, resized


def test_the_outside_the_box_pill_is_gone():
    assert "--hover-pad" not in CSS
    assert "--hover-gold-solid" not in CSS


def test_primary_buttons_brighten_and_nothing_else():
    rule = CSS[CSS.index("@media (hover: hover) { .btn.primary:hover {"):]
    rule = rule[:rule.index("} }")]
    assert "filter: brightness(1.08)" in rule
    assert "transform" not in rule and "box-shadow" not in rule


def test_secondary_chips_hover_neutral_not_chosen():
    """A brand edge on hover read as the chosen state; gold outlines are the
    sidebar's. Selected states keep their gold."""
    for sel in (".home-quick button:hover {", ".kob-opt:hover {", ".pulse-mode:hover {"):
        rule = CSS[CSS.index(sel):]
        rule = rule[:rule.index("}")]
        assert "var(--border-strong)" in rule, sel
        assert "--brand" not in rule and "--asset-brand" not in rule and "--ws-brand-edge" not in rule, sel


def test_hover_cues_for_controls_that_had_none():
    assert ".ht-det > summary:hover .ht-what" in CSS
    assert "#legal-more:hover { color: var(--ink); }" in CSS


def test_focus_rings_are_kept():
    """No rule removes the focus ring from the controls whose hover changed."""
    for sel in (".kob-opt:focus-visible", ".cc-q:focus-visible", ".hm-more:focus-visible",
                ".ht-more:focus-visible", ".foot-link:focus-visible"):
        assert sel in CSS, sel
    # A focus rule may trade the outline for a ring, a border or (a menu item) a fill, never for nothing.
    for m in re.finditer(r"([^{}]*:focus-visible[^{}]*)\{([^{}]*)\}", NC):
        body = m.group(2)
        if re.search(r"outline:\s*(none|0)\b", body):
            assert any(k in body for k in ("border-color", "box-shadow", "background")), " ".join(m.group(1).split())
