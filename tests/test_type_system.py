"""One type system, applied everywhere (2026-10-12).

A font audit of the live build (5,832 text elements on 23 page states,
measured in headless Chrome) found four webfonts downloaded and three drawn:
Inter 92%, Host Grotesk 6%, Space Grotesk 2%, Plus Jakarta Sans fetched and
never used. Small uppercase labels, one job, came in 23 styles (3 faces, 4
weights, 9 trackings); tickers used the label face in 37 places and Inter Bold
in 255; one price was Host Grotesk 600 on one tab and Inter 650 on the next;
39 letter-spacing values and five weights in all.

The decision: Inter for everything read, Space Grotesk for labels and
tickers, three weights, three trackings, one label style. These tests hold it.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "static/styles.css").read_text()
HTML = (ROOT / "static/index.html").read_text()
CHARTS = (ROOT / "static/charts.js").read_text()

CODE = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
HTML_CODE = re.sub(r"<!--.*?-->", "", HTML, flags=re.S)

# The wordmark is a logo lockup, not text, and keeps its own tracking.
BRAND = ".rail .brand-text"
TICKERS = (".tkr", ".ct-sym", ".map-tile-sym", ".idx-sym", ".px-sym", ".sec-sym", ".home-quick button")


def _rules():
    """(selector, body) for every innermost rule, comments removed."""
    out, stack, sel_start = [], [], 0
    for i, ch in enumerate(CODE):
        if ch == "{":
            stack.append((i, sel_start))
            sel_start = i + 1
        elif ch == "}":
            at, _ = stack.pop()
            body = CODE[at + 1:i]
            if "{" not in body:
                head = CODE[:at]
                cut = max(head.rfind("{"), head.rfind("}"), head.rfind(";"))
                out.append((" ".join(head[cut + 1:].split()), body))
            sel_start = i + 1
    return out


RULES = _rules()


def _prop(body: str, name: str):
    m = re.search(r"(?:^|[;\s])" + re.escape(name) + r"\s*:\s*([^;]+)", body)
    return m.group(1).strip() if m else None


def test_two_families_are_loaded_and_nothing_else():
    links = re.findall(r'<link[^>]+href="([^"]*fontsource[^"]*)"', HTML_CODE)
    assert links == [
        "https://cdn.jsdelivr.net/npm/@fontsource-variable/inter/opsz.css",
        "https://cdn.jsdelivr.net/npm/@fontsource-variable/space-grotesk/index.css",
    ], links
    for gone in ("Host Grotesk", "host-grotesk", "Plus Jakarta", "plus-jakarta", "Switzer"):
        assert gone not in CODE and gone not in HTML_CODE, gone


def test_each_face_is_defined_once():
    assert len(re.findall(r"--sans\s*:", CODE)) == 1
    assert re.search(r'--sans:\s*"Inter Variable"', CODE)
    assert re.findall(r"--display\s*:\s*([^;]+);", CODE) == ["var(--sans)"]
    assert len(re.findall(r'--label-face:\s*"Space Grotesk Variable"', CODE)) == 1
    # No family is named outside the three tokens.
    named = re.findall(r'font(?:-family)?\s*:[^;]*"(?:Inter|Space Grotesk)', CODE)
    assert named == [], named


def test_three_weights():
    weights = set(re.findall(r"font-weight\s*:\s*(\w+)", CODE))
    weights |= set(re.findall(r"\bfont\s*:\s*(\d{3})\b", CODE))
    assert weights <= {"400", "500", "600", "inherit", "normal"}, weights


def test_three_trackings():
    seen = {}
    for sel, body in RULES:
        v = _prop(body, "letter-spacing")
        if v and sel != BRAND:
            seen.setdefault(v, sel)
    assert set(seen) <= {"-0.01em", "0", "0.08em"}, seen


def test_every_uppercase_label_is_the_one_label_style():
    labels = 0
    for sel, body in RULES:
        if not re.search(r"text-transform\s*:\s*uppercase", body) or "input" in sel or sel == BRAND:
            continue
        labels += 1
        short = _prop(body, "font")
        if short and short != "inherit":
            assert re.fullmatch(r"600 var\(--t-micro\)(/[\d.]+)? var\(--label-face\)", short), (sel, short)
        else:
            assert _prop(body, "font-family") == "var(--label-face)", sel
            assert _prop(body, "font-size") == "var(--t-micro)", sel
            assert _prop(body, "font-weight") == "600", sel
        assert _prop(body, "letter-spacing") == "0.08em", sel
    assert labels > 60


def test_tickers_are_set_in_the_label_face():
    for want in TICKERS:
        bodies = [b for s, b in RULES if s == want]
        assert bodies, want
        for body in bodies:
            face = _prop(body, "font-family") or (_prop(body, "font") or "")
            assert "var(--label-face)" in face, (want, body)
            assert _prop(body, "letter-spacing") == "0", want


def test_the_headline_price_is_inter_on_every_tab():
    for want in (".sec-px", ".px-last"):
        for sel, body in RULES:
            if sel == want:
                face = _prop(body, "font-family") or _prop(body, "font") or ""
                assert "label-face" not in face, (want, face)


def test_chart_text_is_on_the_scale():
    cf = CHARTS[CHARTS.index("const CF = {"):]
    cf = cf[:cf.index("};")]
    sizes = re.findall(r":\s*([\d.]+) \* CHART_UI_SCALE", cf)
    assert len(sizes) == 5 and set(sizes) <= {"9.5", "10.5"}, cf
    assert "getPropertyValue('--ui-scale')" in CHARTS


def test_an_eyebrow_restyled_on_its_own_stays_the_label_style():
    """.ph-eyebrow set weight 500 and .pl-eyebrow the caption size in rules
    without the uppercase in them, so the audit still found them off-style."""
    for sel, body in RULES:
        if sel in (".eyebrow", ".pl-eyebrow", ".ph-eyebrow", ".hero-label"):
            assert _prop(body, "font-size") in (None, "var(--t-micro)"), sel
            assert _prop(body, "font-weight") in (None, "600"), sel


def test_chart_text_takes_the_same_three_weights():
    weights = set(re.findall(r"'font-weight':\s*(\d+)", CHARTS))
    weights |= set(re.findall(r"^\s+\w+: (\d{3}),$", CHARTS[CHARTS.index("const CW = {"):][:200], re.M))
    assert weights <= {"400", "500", "600"}, weights
