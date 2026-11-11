"""The visual update's text and chart tokens (2026-11-11), checked by computing WCAG 2.x contrast from the values in
tokens.css itself, so a later edit to a token is measured, not trusted.

What it holds: the three greys lifted a step (body text at least 13.8:1 and labels at least 9.9:1 on every dark
surface a sentence sits on), gold unchanged, the red and green chart pair from the owner's 2026-11-09 drawing in both
dark blocks with deeper ones on ivory, the figures' text colours following the pair, and nothing set under 13px."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "static/v2/css"
TOK = (CSS / "tokens.css").read_text()
LIGHT = TOK[:TOK.index(':root[data-theme="charcoal"]')]
DARK = TOK[TOK.index(':root[data-theme="charcoal"]'):TOK.index("@media (prefers-color-scheme: dark)")]
SYSDARK = TOK[TOK.index("@media (prefers-color-scheme: dark)"):TOK.index("\n.scene {")]


def _val(name, block):
    m = re.search(r"--%s:\s*([^;]+);" % re.escape(name), block)
    assert m, name
    v = m.group(1).strip().lower()
    ref = re.fullmatch(r"var\(--([a-z0-9-]+)\)", v)
    return _val(ref.group(1), block) if ref else v


def _lum(h):
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def ratio(a, b):
    hi, lo = sorted((_lum(a), _lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_the_three_greys_are_lifted_a_step_in_both_dark_blocks():
    for block in (DARK, SYSDARK):
        assert (_val("c-ink", block), _val("c-ink-2", block), _val("c-ink-3", block)) == ("#f7f5f0", "#e5e1d9", "#c5c0b6")


def test_body_text_is_at_least_13_8_and_labels_at_least_9_9_to_1_on_the_panel():
    for block in (DARK, SYSDARK):
        panel, page = _val("c-raised", block), _val("c-plane", block)
        assert ratio(_val("c-ink-2", block), panel) >= 13.8, ratio(_val("c-ink-2", block), panel)
        assert ratio(_val("c-ink-3", block), panel) >= 9.9, ratio(_val("c-ink-3", block), panel)
        assert ratio(_val("c-ink", block), panel) >= 16.5
        for bg in (page, panel, _val("c-sunk", block)):
            assert ratio(_val("c-ink-3", block), bg) >= 7, "every grey stays above 7:1 on every surface"


def test_gold_is_unchanged():
    for block in (DARK, SYSDARK):
        assert _val("c-gold", block) == "#d4b144" and _val("c-gold-ink", block) == "#e3c76f"
    assert "--c-gold: #b0861b;" in LIGHT and "--c-gold-ink: #74580c;" in LIGHT


def test_the_chart_pair_and_its_text_colours():
    for block in (DARK, SYSDARK):
        assert (_val("c-up", block), _val("c-down", block)) == ("#22c55e", "#ef4444"), "the owner's drawing, 2026-11-09"
        for name in ("c-up", "c-down"):
            for bg in ("c-plane", "c-raised", "c-sunk"):
                assert ratio(_val(name, block), _val(bg, block)) >= 3, "a graphic needs 3:1"
        for name in ("c-up-ink", "c-down-ink", "c-pos", "c-neg"):
            for bg in ("c-plane", "c-raised", "c-sunk"):
                assert ratio(_val(name, block), _val(bg, block)) >= 4.5, (name, bg)
        assert _val("c-pos", block) == _val("c-up-ink", block) and _val("c-neg", block) == _val("c-down-ink", block), \
            "a move in a sentence is the same green and red as the line beside it"
    # on ivory the owner's green is 2.3:1, so the light theme's pair is deeper
    for name in ("c-up", "c-down"):
        assert ratio(_val(name, LIGHT), _val("c-raised", LIGHT)) >= 3
    assert ratio(_val("c-up-ink", LIGHT), _val("c-raised", LIGHT)) >= 4.5 and ratio(_val("c-down-ink", LIGHT), _val("c-raised", LIGHT)) >= 4.5


def test_nothing_is_set_under_13px():
    assert "--t-xs: 13px;" in TOK and "--t-sm: 13px;" in TOK
    sizes = [int(x) for x in re.findall(r"--t-[a-z0-9]+:\s*(\d+)px", TOK)]
    assert min(sizes) >= 13, sizes
    rules = "\n".join(p.read_text() for p in CSS.glob("*.css") if p.name != "tokens.css")
    floors = [int(x) for x in re.findall(r"font-size:\s*max\((\d+)px", rules)]
    assert all(f >= 13 for f in floors), floors
    literal = [float(x) for x in re.findall(r"font-size:\s*(\d+(?:\.\d+)?)px", rules)]
    assert all(s >= 13 for s in literal), literal
