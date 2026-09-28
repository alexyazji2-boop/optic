"""Every chart's own colour is Optic's gold, not blue.

Asked for with a screenshot of the Charting tab's blue intraday line beside the
gold Load button. The line was --s1 because that slot was the first
categorical colour; the chart's colour is now --brand, which follows
--btn-primary, so the charts and the buttons are one colour and stay one.

The gold is warm, and the palette already had two warm colours near it. Measured
in CIE76: 22.6 from --s4's amber in the dark theme, and in the light theme
--warn is 2.7 from it, which is the same colour. So every line drawn beside the
gold by default moved off amber, and those distances are asserted here rather
than remembered.

Blue stays where it is one of several categories: the eleven sectors on the
rotation chart, and the conventional "Improving" quadrant. There the colour's
job is telling lines apart, not being the chart.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "static/styles.css").read_text()


def _strip(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"^\s*//.*$", " ", text, flags=re.M)


APP = _strip((ROOT / "static/app.js").read_text())
CHARTS = _strip((ROOT / "static/charts.js").read_text())
CLEAN_CSS = _strip(CSS)


def _fn(src: str, name: str) -> str:
    body = src[src.index("function " + name + "("):]
    return body[:body.index("\n}") + 2]


# ------------------------------------------------------------ the colour


def test_the_charts_read_the_brand_token_so_the_theme_carries_it():
    c_vars = CHARTS[CHARTS.index("const C_VARS = {"):]
    assert "brand: '--brand'" in c_vars[:c_vars.index("};")]
    assert "--brand: var(--btn-primary);" in CLEAN_CSS


def test_the_picker_still_offers_the_gold():
    """A price line is no longer gold by default: it was asked for green over a
    rise and red over a fall (test_price_line_direction.py). Gold stays the
    first preset for anyone who wants the old line back."""
    presets = APP[APP.index("CHART_COLOR_PRESETS = ["):]
    assert "{ slot: 'brand', label: 'Gold' }," in presets[:presets.index("];")]


# The price lines left this list when they started following their direction:
# the instrument page, the Investing chart, both their keys, and the Macro
# table's sparklines. Everything below is a single-series chart of something
# other than a price, and those are still the gold.
PRIMARY_IN_APP = [
    # single-series charts
    "{ name: 'Trailing P/E', color: C.brand },",
    "values: pts.map((x) => x.pe), color: C.brand,",
    "{ name: 'Net GEX', values: prof.net_gex, color: C.brand, fill: true }",
    "values: rel.ratio,\n      color: C.brand, fill: true }",
    "{ name: e.label, values: e.values, color: C.brand, fill: true }",
    "{ name: r.name, values: r.series || [], color: C.brand, fill: true }",
    "values: pr.series.map((p) => p.balance), color: C.brand }",
    "color: i === 0 ? C.brand : C.s7,",
    # the oscillators, on the Options tab and in the Charting tab's panes
    "values: rsiVals, color: C.brand }",
    "{ name: 'RSI', values: ps.rsi, color: C.brand },",
    "{ name: 'MACD', color: C.brand },",
    'style="background:${C.brand}"></span>RSI',
    'style="background:${C.brand}"></span>MACD',
    # the sequential heat ramp
    "color-mix(in srgb, ${C.brand} ${Math.round(t * 85 + 15)}%, ${C.surface})",
]


def test_every_charts_own_line_is_the_gold():
    for code in PRIMARY_IN_APP:
        assert code in APP, code


def test_the_renderers_defaults_are_the_gold_too():
    assert "function sparkline(values, width = 96, height = 26, color = C.brand)" in CHARTS
    assert "[[macd, C.brand, 'MACD'], [signal, C.s7, 'Signal']]" in CHARTS
    assert "fill: p.color || C.brand," in CHARTS
    assert "const IND_COLORS = ['brand', 's3', 's7', 'neg'];" in APP


def test_the_navigator_and_the_compare_leader_are_the_gold():
    assert ".ws-nav-window { fill: var(--brand);" in CLEAN_CSS
    assert ".ws-nav-edge { fill: var(--brand);" in CLEAN_CSS
    assert ".cb-row.is-lead .cb-fill { background: var(--brand); }" in CLEAN_CSS


def test_blue_is_left_only_where_it_is_one_category_of_several():
    """A guard against the next chart being written with C.s1 as its colour."""
    lines = [ln.strip() for ln in (APP + CHARTS).splitlines() if re.search(r"\bC\.s1\b", ln)]
    allowed = ("const SLOTS = [C.s1,", "fill: C.s1, label: 'Improving'", "stroke: colour || C.s1 ||")
    stray = [ln for ln in lines if not any(a in ln for a in allowed)]
    assert not stray, stray


# ------------------------------------------------------------ its neighbours


COMPANIONS_ON_S7 = [
    ("RSI signal, Options", "{ name: 'Signal', values: rsiSignal, color: C.s7,"),
    ("RSI signal key, Options", "`Signal (${RSI_SIGNAL_PERIOD}-period average)`, color: C.s7 }"),
    ("RSI signal, pane", "{ name: 'Signal', values: ps.rsiSignal || [], color: C.s7,"),
    ("RSI signal key, pane", 'style="background:${C.s7}"></span>Signal ${RSI_SIGNAL_PERIOD}'),
    ("MACD signal key, Options", "{ name: 'Signal', color: C.s7 },"),
    ("MACD signal key, pane", 'style="background:${C.s7}"></span>Signal\n'),
    ("contributions line", "values: pr.series.map((p) => p.contributed), color: C.s7,"),
    ("contributions key", "{ name: 'Contributions only', color: C.s7, dash: true },"),
]


def test_lines_drawn_beside_the_gold_by_default_are_off_amber():
    for what, code in COMPANIONS_ON_S7:
        assert code in APP, what
    assert "[`<span style=\"color:${C.s7}\">■</span> Signal`" in CHARTS


def test_the_gamma_flip_line_is_a_neutral_not_the_warning_amber():
    fn = APP[APP.index("mount('chart-gamma-profile'"):]
    fn = fn[:fn.index("}));")]
    assert "color: C.ink2 } : { value: 0" in fn
    assert "C.warn" not in fn


# ------------------------------------------------------------ measured


def _tokens(block: str, name: str):
    found = re.findall(r"--%s:\s*(#[0-9a-fA-F]{6})" % re.escape(name), block)
    return found[-1] if found else None


def _themes():
    split = CSS.index(':root[data-theme="light"]')
    dark, light = CSS[:split], CSS[split:CSS.index("}", split)]
    # The brand in dark is the asset restyle's gold; the light block sets its own.
    return {"dark": (dark, _tokens(CSS, "asset-brand")),
            "light": (light, _tokens(light, "btn-primary"))}


def _lab(hexcode: str):
    h = hexcode.lstrip("#")
    rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    x = (0.4124 * lin[0] + 0.3576 * lin[1] + 0.1805 * lin[2]) / 0.95047
    y = 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    z = (0.0193 * lin[0] + 0.1192 * lin[1] + 0.9505 * lin[2]) / 1.08883
    f = lambda t: t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    return 116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))


def _de(a: str, b: str) -> float:
    return sum((p - q) ** 2 for p, q in zip(_lab(a), _lab(b))) ** 0.5


def test_amber_really_was_too_close_to_the_gold():
    """The reason the companions moved, kept honest: if the gold or the amber
    changes, this says whether the move is still needed."""
    t = _themes()
    dark, gold_d = t["dark"]
    light, gold_l = t["light"]
    assert gold_d == "#d4b144" and gold_l == "#9a6b00"
    assert _de(gold_d, _tokens(dark, "s4")) < 25
    assert _de(gold_l, _tokens(light, "warn")) < 5


def test_the_companions_are_far_from_the_gold_in_both_themes():
    for theme, (block, gold) in _themes().items():
        s7 = _tokens(block, "s7") or _tokens(CSS, "s7")
        ink2 = _tokens(block, "ink-2") or _tokens(CSS, "ink-2")
        assert _de(gold, s7) > 100, theme
        assert _de(gold, ink2) > 50, theme


# ------------------------------------------------------ the averages beside Stages


def test_averages_are_measured_against_the_stage_colours_when_those_are_drawn():
    """The stages are a band under the price now, not the candles' colour, so
    both are on screen at once and the averages keep clear of both: the price
    as drawn plus the band's four colours."""
    fn = _fn(APP, "maColorsOnChart")
    assert "function maColorsOnChart(candleMode, marks)" in fn
    assert ": lineMarks()), ...(marks || [])].map(lc));" in fn
    tints = _fn(APP, "stageTints")
    assert "const marks = [C.stage1, C.stage2, C.stage3, C.stage4];" in tints
    assert "return { colors, key, marks };" in tints
    base = _fn(APP, "chartBaseColors")
    assert "maColorsOnChart(candleMode, marks)" in base
    assert "chartColor('down')] : lineMarks()),\n    ...(marks || [])];" in base


def test_the_charting_tab_asks_one_question_in_three_places():
    """Chart, legend and study palette all take the stages from wsStages, so
    they cannot disagree about which colours are drawn."""
    assert "const stages = wsStages(ps);" in _fn(APP, "wsMountChart")
    assert "const legStages = wsStages(ps);" in _fn(APP, "wsLegend")
    assert "const stages = wsStages(ps);" in _fn(APP, "wsStudyPalette")
