"""Stock maps.

A treemap is unusually good at making a comparison look authoritative, which is
exactly why the layout and the refusals need testing. Tiles whose areas do not
match the measure are a lie told convincingly, and a row plotted at zero because
its P/E was missing reads as "very cheap" — the opposite of the truth for a
company with no earnings.
"""

import numpy as np
import pandas as pd
import pytest

from app.analytics import stockmaps as sm


# ------------------------------------------------------------ the layout

def _items(sizes):
    return [{"symbol": "S%d" % i, "_size": v} for i, v in enumerate(sizes)]


def test_tiles_fill_the_rectangle_without_overlapping():
    """Two properties a treemap must have and which are easy to break: the tiles
    cover the box, and no two of them overlap."""
    out = sm._squarify(_items([40, 25, 15, 10, 6, 4]), 0, 0, 100, 100)
    assert len(out) == 6
    area = sum(t["w"] * t["h"] for t in out)
    assert area == pytest.approx(10000, rel=0.02)
    for i, a in enumerate(out):
        for b in out[i + 1:]:
            overlap_x = min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"])
            overlap_y = min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"])
            assert not (overlap_x > 0.01 and overlap_y > 0.01), (
                "%s overlaps %s" % (a["symbol"], b["symbol"]))


def test_tile_area_is_proportional_to_the_measure():
    """The whole claim a treemap makes. If area does not track the measure the
    picture is decorative."""
    sizes = [50, 25, 12.5, 12.5]
    out = sm._squarify(_items(sizes), 0, 0, 100, 100)
    by_sym = {t["symbol"]: t["w"] * t["h"] for t in out}
    total = sum(by_sym.values())
    for i, want in enumerate(sizes):
        got = by_sym["S%d" % i] / total * 100
        assert got == pytest.approx(want, rel=0.03), (
            "S%d should occupy %.1f%% of the area, got %.1f%%" % (i, want, got))


def test_tiles_stay_inside_the_box():
    out = sm._squarify(_items([30, 20, 20, 15, 10, 5]), 0, 0, 100, 100)
    for t in out:
        assert t["x"] >= -0.01 and t["y"] >= -0.01
        assert t["x"] + t["w"] <= 100.01
        assert t["y"] + t["h"] <= 100.01


def test_zero_and_negative_sizes_are_not_drawn():
    """A tile with no area is not a small tile, it is a missing one — and a
    negative size has no meaning as an area at all."""
    out = sm._squarify(_items([50, 0, -10, 25]), 0, 0, 100, 100)
    assert len(out) == 2


def test_squarify_avoids_slivers():
    """Slice-and-dice produces long thin tiles whose areas cannot be compared by
    eye, which defeats the point. Squarified layout should keep aspect ratios
    within reach of square for most tiles."""
    out = sm._squarify(_items([25] * 8), 0, 0, 100, 100)
    ratios = [max(t["w"] / t["h"], t["h"] / t["w"]) for t in out]
    assert max(ratios) < 4.0, "produced a sliver with aspect ratio %.1f" % max(ratios)


def test_an_empty_universe_lays_out_nothing():
    assert sm._squarify([], 0, 0, 100, 100) == []


# ---------------------------------------------------- templates and measures

def test_every_template_uses_declared_measures():
    for t in sm.TEMPLATES:
        for key in ("size", "color", "x", "y"):
            if t.get(key):
                assert t[key] in sm.MEASURES, "%s: unknown measure %s" % (t["id"], t[key])


def test_every_template_points_at_a_real_universe():
    for t in sm.TEMPLATES:
        assert t["universe"] in sm.UNIVERSES, t["id"]


def test_every_template_states_its_question():
    """A configuration is not a feature. 'P/E outliers in Energy' is a question;
    'size by market cap, colour by P/E' is a setting."""
    for t in sm.TEMPLATES:
        assert t.get("question")
        assert len(t["question"]) > 25, t["id"]


def test_every_measure_explains_itself_and_declares_a_direction():
    for key, val in sm.MEASURES.items():
        assert val.get("label"), key
        assert val.get("note"), key
        assert "higher_is_better" in val, key


def test_measures_without_a_good_end_say_so():
    """RSI and daily range have no good direction. Colouring them on a
    green-to-red diverging scale would assert that high is bad, which the measure
    does not claim."""
    for key in ("rsi", "atr_pct", "beta", "market_cap", "dollar_volume"):
        assert sm.MEASURES[key]["higher_is_better"] is None, key


def test_valuation_measures_are_lower_is_better():
    for key in ("trailing_pe", "forward_pe", "price_to_book"):
        assert sm.MEASURES[key]["higher_is_better"] is False, key


def test_etf_templates_do_not_ask_for_company_fundamentals():
    """Measured live: sizing an ETF map by market cap dropped all eleven rows,
    because a sector ETF has no market cap in the feed. ETF universes size by
    dollar volume instead."""
    fundamental = {"market_cap", "trailing_pe", "forward_pe", "price_to_book",
                   "revenue_growth", "profit_margin", "beta"}
    for t in sm.TEMPLATES:
        if t["universe"] == "megacap":
            continue
        used = {t[k] for k in ("size", "color", "x", "y") if t.get(k)}
        clash = used & fundamental
        assert not clash, "%s asks an ETF universe for %s" % (t["id"], clash)


def test_the_fundamental_templates_use_real_companies():
    for t in sm.TEMPLATES:
        used = {t[k] for k in ("size", "color", "x", "y") if t.get(k)}
        if used & {"forward_pe", "revenue_growth", "beta", "price_to_book"}:
            assert t["universe"] == "megacap", (
                "%s needs fundamentals but points at %s" % (t["id"], t["universe"]))


def test_template_ids_are_unique():
    ids = [t["id"] for t in sm.TEMPLATES]
    assert len(ids) == len(set(ids))


def test_bubble_templates_declare_both_axes():
    for t in sm.TEMPLATES:
        if t["shape"] == "bubble":
            assert t.get("x") and t.get("y"), t["id"]
        else:
            assert t.get("size") and t.get("color"), t["id"]
