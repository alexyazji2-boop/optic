"""The moving averages' colours stay clear of every colour the chart draws.

Asked for with a screenshot of the averages menu: "change the color scheme here
so it does not overlap with the charting colors". Measured on the old palette
in CIE76, dark theme: SMA 50 was the up candle exactly (0.0), EMA 50 was 17.0
from the green, SMA 200 was 19.7 from the stage-3 amber, and SMA 20 and EMA 9
were 25.7 and 25.4 from the red and the coral. The price line had just become
green over a rise and red over a fall, which made those the worst ones.

Distance alone is not the rule, which is why hue is asserted as well: a search
on CIE76 alone offered a bright green (#2bee2b) 33.7 from the line's green,
on lightness, and it is still green. The palette is held to blues, violets and
orchids, the one part of the wheel no price, candle, stage or level uses.

The numbers are read from styles.css through its own cascade, both themes, so
a future edit to any colour on either side re-runs the measurement.
"""
from __future__ import annotations

import colorsys
import itertools
import math
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CSS = re.sub(r"/\*.*?\*/", " ", (ROOT / "static/styles.css").read_text(), flags=re.S)
APP = (ROOT / "static/app.js").read_text()
CHARTS = (ROOT / "static/charts.js").read_text()


def _block_vars(selector):
    """Custom properties declared in top-level blocks with exactly this selector."""
    out = {}
    for m in re.finditer(r"(?m)^" + re.escape(selector) + r"\s*\{(.*?)\n\}", CSS, re.S):
        for name, value in re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", m.group(1)):
            out[name] = value.strip()
    return out


DARK = _block_vars(":root")
LIGHT = {**DARK, **_block_vars(':root[data-theme="light"]')}


def _resolve(env, name):
    value = env[name]
    for _ in range(8):
        ref = re.fullmatch(r"var\((--[\w-]+)\)", value)
        if not ref:
            return value
        value = env[ref.group(1)]
    raise AssertionError("unresolved " + name)


THEMES = {"dark": DARK, "light": LIGHT}
AVERAGES = ["--ma-1", "--ma-2", "--ma-3", "--ma-4", "--ma-5", "--ma-6"]
SMA, EMA = AVERAGES[:3], AVERAGES[3:]
# Everything a price chart draws in, other than the averages.
CHART = ["--pos", "--neg", "--s3", "--s8", "--warn", "--stage-1", "--brand",
         "--ref-sr", "--ref-session", "--ref-fib", "--ink-2"]
NEUTRAL = {"--ref-fib", "--ink-2"}          # no hue to be near


def _rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]


def _lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _lum(h):
    r, g, b = map(_lin, _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a, b):
    hi, lo = sorted((_lum(a), _lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _lab(h):
    r, g, b = map(_lin, _rgb(h))
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
    f = lambda t: t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    return (116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z)))


def _de(a, b):
    return math.dist(_lab(a), _lab(b))


def _hue_gap(a, b):
    ha = colorsys.rgb_to_hls(*_rgb(a))[0] * 360
    hb = colorsys.rgb_to_hls(*_rgb(b))[0] * 360
    d = abs(ha - hb)
    return min(d, 360 - d)


def _col(theme, name):
    return _resolve(THEMES[theme], name)


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_every_average_is_far_from_every_chart_colour(theme):
    for ma in AVERAGES:
        for mark in CHART:
            d = _de(_col(theme, ma), _col(theme, mark))
            assert d >= 30, "%s %s is %.1f from %s" % (theme, ma, d, mark)


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_and_in_another_hue_family_not_only_another_lightness(theme):
    for ma in AVERAGES:
        for mark in CHART:
            if mark in NEUTRAL:
                continue
            gap = _hue_gap(_col(theme, ma), _col(theme, mark))
            assert gap >= 15, "%s %s is %.0f degrees from %s" % (theme, ma, gap, mark)


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_the_averages_read_against_the_chart_background(theme):
    bg = _col(theme, "--surface")
    for ma in AVERAGES:
        assert _contrast(_col(theme, ma), bg) >= 4.5, (theme, ma)


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_the_averages_are_told_apart_from_each_other(theme):
    """Each trio is what is usually on at once, so it is held further apart."""
    for trio in (SMA, EMA):
        for a, b in itertools.combinations(trio, 2):
            assert _de(_col(theme, a), _col(theme, b)) >= 25, (theme, a, b)
    for a, b in itertools.combinations(AVERAGES, 2):
        assert _de(_col(theme, a), _col(theme, b)) >= 18, (theme, a, b)


def test_the_old_palette_would_have_failed_this():
    """So the assertions above are measuring the complaint and not a formality."""
    old = {"SMA 50": "#199e70", "EMA 50": "#5fa617", "SMA 200": "#c98500"}
    dark = {m: _col("dark", m) for m in CHART}
    assert min(_de(old["SMA 50"], v) for v in dark.values()) < 30
    assert min(_de(old["EMA 50"], v) for v in dark.values()) < 30
    assert min(_de(old["SMA 200"], v) for v in dark.values()) < 30


# ------------------------------------------------------------------ wiring


def test_the_averages_and_the_clouds_are_drawn_in_their_own_tokens():
    defs = APP[APP.index("const OVERLAY_DEFS = ["):]
    defs = defs[:defs.index("\n];")]
    for oid, slot in (("sma20", "ma1"), ("sma50", "ma2"), ("sma200", "ma3"),
                      ("ema9", "ma4"), ("ema21", "ma5"), ("ema50", "ma6")):
        assert re.search(r"id: '%s'.*?color: '%s'" % (oid, slot), defs, re.S), oid
    assert defs.count("color: 'cloudUp', fill: true") == 2
    clouds = APP[APP.index("function emaClouds(ps)"):]
    clouds = clouds[:clouds.index("\n}")]
    assert "upColor: C.cloudUp," in clouds and "downColor: C.cloudDown," in clouds
    assert "C.pos" not in clouds and "C.neg" not in clouds


def test_the_renderer_reads_them_from_the_theme_and_falls_back_to_the_dark_values():
    c_vars = CHARTS[CHARTS.index("const C_VARS = {"):]
    c_vars = c_vars[:c_vars.index("};")]
    for i in range(1, 7):
        assert "ma%d: '--ma-%d'" % (i, i) in c_vars
        assert re.search(r"ma%d: '%s'" % (i, _col("dark", "--ma-%d" % i)), CHARTS), i
    assert "cloudUp: '--cloud-up'" in c_vars and "cloudDown: '--cloud-down'" in c_vars


def test_a_displaced_average_lands_on_another_average_colour():
    line = re.search(r"const MA_CANDLE_FALLBACKS = \[(.*?)\];", APP).group(1)
    assert [s.strip(" '") for s in line.split(",")] == [
        "ma1", "ma2", "ma3", "ma4", "ma5", "ma6", "ink2"]


# ------------------------------------------------------------------ studies


STUDY_TOKENS = {"brand": "--brand", "ink2": "--ink-2", "s5": "--s5",
                "refSR": "--ref-sr", "s4": "--s4"}


def test_studies_no_longer_take_the_colours_of_the_line_or_the_averages():
    pool = re.search(r"const IND_COLOR_POOL = \[(.*?)\];", APP).group(1)
    slots = [s.strip(" '") for s in pool.split(",")]
    assert slots[0] == "brand", "gold first, now the line is not gold"
    for gone in ("s8", "s6", "s7"):
        assert gone not in slots, gone
    assert set(slots) == set(STUDY_TOKENS)


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_every_study_colour_is_clear_of_the_line_and_the_averages(theme):
    for slot, var in STUDY_TOKENS.items():
        c = _col(theme, var)
        assert min(_de(c, _col(theme, m)) for m in AVERAGES) >= 30, (theme, slot)
        assert min(_de(c, _col(theme, m)) for m in ("--pos", "--neg")) >= 25, (theme, slot)
