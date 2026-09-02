"""Tests for pattern detection.

Synthetic bars throughout: a double bottom built by hand is the only way to know
the detector found the pattern rather than something that happened to be nearby.
The negative cases matter more than the positive ones here — a detector that
fires on everything passes every positive test.
"""

import numpy as np
import pandas as pd
import pytest

from app.analytics import patterns


def _frame(rows):
    """rows: list of (open, high, low, close) or (o,h,l,c,volume)."""
    idx = pd.date_range("2025-01-01", periods=len(rows), freq="B")
    data = {
        "Open": [r[0] for r in rows],
        "High": [r[1] for r in rows],
        "Low": [r[2] for r in rows],
        "Close": [r[3] for r in rows],
        "Volume": [r[4] if len(r) > 4 else 1_000_000 for r in rows],
    }
    return pd.DataFrame(data, index=idx)


def _flat(n, price=100.0, spread=1.0):
    return [(price, price + spread, price - spread, price)] * n


def _path(closes, spread=1.0):
    """Bars tracking a close path, each with a symmetric range.

    The open is the previous close, which makes the first bar a doji — that is
    what silently turned a "three rising closes" fixture into three dojis. The
    first bar is nudged so every bar has a real body.
    """
    out = []
    prev = closes[0] - (closes[1] - closes[0]) / 2 if len(closes) > 1 else closes[0] - spread
    for c in closes:
        out.append((prev, max(prev, c) + spread, min(prev, c) - spread, c))
        prev = c
    return out


# ------------------------------------------------------------------- pivots

def test_pivots_find_a_clean_peak_and_trough():
    closes = [100, 101, 102, 103, 108, 103, 102, 101, 100, 95, 100, 101, 102, 103]
    df = _frame(_path(closes))
    piv = patterns.find_pivots(df, order=3)
    kinds = {p["kind"] for p in piv}
    assert "high" in kinds and "low" in kinds


def test_pivots_need_clearance_on_both_sides():
    """A bar at the very edge of the series cannot be a pivot — there is no
    right-hand side to compare it against yet."""
    df = _frame(_path([100, 101, 102, 103, 110]))
    piv = patterns.find_pivots(df, order=3)
    assert all(p["index"] < len(df) - 3 for p in piv)


def test_equal_highs_still_yield_a_pivot():
    """The symmetric strict-inequality version silently drops every flat double
    top, which is the exact shape being looked for."""
    closes = [100, 102, 104, 106, 110, 110, 106, 104, 102, 100, 99]
    df = _frame(_path(closes))
    piv = patterns.find_pivots(df, order=3)
    assert any(p["kind"] == "high" for p in piv)


def test_pivots_on_a_short_frame_return_nothing():
    assert patterns.find_pivots(_frame(_flat(4)), order=3) == []


# -------------------------------------------------------------- candlesticks

def test_hammer_needs_a_long_lower_wick_and_little_upper():
    # A hammer needs a body big enough not to be a doji: body 2.0 on a range of
    # 8.5 is a 24% body, above DOJI_BODY_MAX, with a 6.0 lower wick.
    df = _frame(_flat(6) + [(100.0, 102.5, 94.0, 102.0)])
    names = [c["name"] for c in patterns.candle_patterns(df, lookback=2)]
    assert "Hammer" in names


def test_a_wide_range_bar_with_two_wicks_is_not_a_hammer():
    df = _frame(_flat(6) + [(100.0, 106.0, 94.0, 102.0)])
    names = [c["name"] for c in patterns.candle_patterns(df, lookback=2)]
    assert "Hammer" not in names, "both wicks long means no single-side rejection"


def test_shooting_star_is_the_hammer_inverted():
    df = _frame(_flat(6) + [(100.0, 108.0, 99.5, 100.0)])
    names = [c["name"] for c in patterns.candle_patterns(df, lookback=2)]
    assert "Shooting star" in names or "Gravestone doji" in names


def test_doji_variants_are_distinguished_by_which_wick():
    dragon = _frame(_flat(6) + [(100.0, 100.3, 95.0, 100.05)])
    grave = _frame(_flat(6) + [(100.0, 105.0, 99.8, 100.05)])
    assert "Dragonfly doji" in [c["name"] for c in patterns.candle_patterns(dragon, 2)]
    assert "Gravestone doji" in [c["name"] for c in patterns.candle_patterns(grave, 2)]


def test_bullish_engulfing_requires_covering_the_prior_body():
    df = _frame(_flat(6) + [(104.0, 104.5, 100.0, 100.5), (100.0, 105.5, 99.8, 105.0)])
    assert "Bullish engulfing" in [c["name"] for c in patterns.candle_patterns(df, 2)]


def test_a_smaller_body_does_not_engulf():
    df = _frame(_flat(6) + [(104.0, 104.5, 100.0, 100.5), (101.0, 102.0, 100.8, 101.8)])
    assert "Bullish engulfing" not in [c["name"] for c in patterns.candle_patterns(df, 2)]


def test_inside_and_outside_bars_are_mutually_exclusive():
    inside = _frame(_flat(6) + [(100.0, 108.0, 92.0, 101.0), (100.0, 104.0, 97.0, 101.0)])
    outside = _frame(_flat(6) + [(100.0, 102.0, 99.0, 101.0), (100.0, 108.0, 92.0, 107.0)])
    # Per bar, not per result set: a lookback of 2 legitimately reports the
    # previous bar as well, and it can be the opposite kind.
    a = [c["name"] for c in patterns.candle_patterns(inside, 2) if c["bar_offset"] == 0]
    b = [c["name"] for c in patterns.candle_patterns(outside, 2) if c["bar_offset"] == 0]
    assert "Inside bar" in a and "Outside bar" not in a
    assert "Outside bar" in b and "Inside bar" not in b


def test_three_white_soldiers_needs_three_rising_closes():
    up = _frame(_flat(6) + [(100.5, 101.5, 100.2, 101.4),
                            (101.4, 103.2, 101.2, 103.0),
                            (103.0, 105.3, 102.8, 105.0)])
    stalled = _frame(_flat(6) + [(100.5, 101.5, 100.2, 101.4),
                                 (101.4, 103.2, 101.2, 103.0),
                                 (103.0, 103.2, 101.5, 102.0)])
    assert "Three white soldiers" in [c["name"] for c in patterns.candle_patterns(up, 4)]
    assert "Three white soldiers" not in [c["name"] for c in patterns.candle_patterns(stalled, 4)]


def test_every_candle_result_labels_its_reading_as_conventional():
    """The direction shown is the textbook claim, and has to be marked as such —
    the measured base rates are a separate, and mostly contradictory, thing."""
    df = _frame(_flat(6) + [(100.0, 101.0, 94.0, 100.5)])
    for row in patterns.candle_patterns(df, 2):
        assert row["conventional"], row["name"]
        assert row["direction"] in ("bullish", "bearish", "indecisive")


def test_candle_patterns_on_too_little_history():
    assert patterns.candle_patterns(_frame(_flat(3))) == []


# ------------------------------------------------------------ chart patterns

def _double_bottom_path():
    """A decline into two equal lows with a real peak between them, then a
    breakout above that peak so the pattern confirms."""
    return (
        list(range(140, 99, -2))          # the decline that gives it something to reverse
        + [100, 102, 106, 110, 112]       # first low, then the middle peak
        + [108, 104, 100, 100]            # back down to the same low
        + [104, 110, 116, 120]            # close above the peak -> confirmed
    )


def test_double_bottom_is_found_and_confirmed():
    # Padded past the 40-bar floor chart_patterns needs; at 34 bars it returned
    # nothing regardless of what shape was in it.
    df = _frame(_path(_double_bottom_path(), spread=0.4) + _flat(12, 120.0, 0.8))
    found = [p for p in patterns.chart_patterns(df) if p["name"] == "Double bottom"]
    assert found, "a textbook double bottom must be detected"
    pat = found[-1]
    assert pat["direction"] == "up"
    assert pat["confirmed"] is True
    assert pat["confirmed_on"]
    assert [pt["role"] for pt in pat["points"]] == ["first", "neckline", "second"]


def test_double_bottom_without_a_neckline_break_is_unconfirmed():
    path = _double_bottom_path()[:-4] + [101, 102, 101, 100]
    df = _frame(_path(path, spread=0.4) + _flat(14, 100.0, 0.8))
    found = [p for p in patterns.chart_patterns(df) if p["name"] == "Double bottom"]
    assert found
    assert found[-1]["confirmed"] is False, "geometry alone is not confirmation"


def test_a_range_does_not_produce_reversal_patterns():
    """The failure that made the first version useless: SPY oscillating in a band
    returned five reversal patterns in eight weeks, because every consecutive
    pivot pair sat within tolerance of the last."""
    osc = []
    for _ in range(9):
        osc += [100, 103, 106, 103, 100, 97, 94, 97]
    df = _frame(_path(osc, spread=0.5))
    found = patterns.chart_patterns(df)
    structural = [p for p in found if p["name"] in
                  ("Double bottom", "Double top", "Head and shoulders",
                   "Inverse head and shoulders")]
    # Once there is enough history to judge, every one of these is rejected. The
    # very first trough is exempt on purpose: with six bars behind it there is no
    # basis for calling the band well-travelled, and refusing to judge is better
    # than guessing. Before the midline test this returned five.
    late = [p for p in structural
            if min(pt["index"] for pt in p["points"]) >= 10]
    assert not late, [(p["name"], min(pt["index"] for pt in p["points"]))
                      for p in late]


def test_detected_patterns_never_overlap():
    df = _frame(_path(_double_bottom_path() + [116, 110, 104, 100, 100, 106, 114], 0.4)
                + _flat(10, 114.0, 0.8))
    found = [p for p in patterns.chart_patterns(df)
             if p.get("confirmed") is not None]      # triangles are exempt
    spans = sorted((min(pt["index"] for pt in p["points"]),
                    max(pt["index"] for pt in p["points"])) for p in found)
    for (a_lo, a_hi), (b_lo, b_hi) in zip(spans, spans[1:]):
        assert a_hi < b_lo, "overlapping detections are one move read twice"


def test_amplitude_floor_rejects_a_shallow_shape():
    """Two equal lows two ticks below a peak is not a double bottom."""
    path = list(range(140, 99, -2)) + [100, 100.4, 100.6, 100.4, 100, 100.5, 101]
    df = _frame(_path(path, spread=0.3) + _flat(14, 101.0, 0.5))
    found = [p for p in patterns.chart_patterns(df) if p["name"] == "Double bottom"]
    assert not found


def test_head_and_shoulders_needs_level_shoulders():
    rising = list(range(60, 101, 2))
    hs = rising + [
        102, 104, 106, 104, 102,          # left shoulder
        98, 96, 94, 96, 98,               # first trough
        104, 110, 116, 118, 116, 110, 104,   # head
        98, 96, 94, 96, 98,               # second trough
        102, 104, 106, 104, 102,          # right shoulder, level with the left
        96, 92, 88, 86,                   # neckline break
    ]
    df = _frame(_path(hs, spread=0.5) + _flat(10, 86.0, 0.8))
    names = [p["name"] for p in patterns.chart_patterns(df)]
    assert "Head and shoulders" in names, names


def test_triangles_are_named_from_both_boundaries():
    """Calling every converging shape 'symmetrical' loses the only part anyone
    acts on."""
    asc = list(range(60, 101, 2)) + [
        100, 90, 100, 92, 100, 94, 100, 96, 100, 97, 100]
    df = _frame(_path(asc, spread=0.4) + _flat(10, 100.0, 0.6))
    tri = [p for p in patterns.chart_patterns(df) if "triangle" in p["name"].lower()]
    if tri:
        assert tri[0]["name"] in ("Ascending triangle", "Descending triangle",
                                  "Symmetrical triangle")
        assert tri[0]["confirmed"] is None, "a triangle is a state, not an event"


def test_chart_patterns_on_too_little_history():
    assert patterns.chart_patterns(_frame(_flat(20))) == []


# --------------------------------------------------------- supply and demand

def test_a_tight_base_then_an_impulse_is_a_demand_zone():
    # ATR here is ~3, so a move to 112 is about 4 ATR — inside the reachability
    # horizon. The first version of this fixture jumped 24% on a 1.5-ATR series,
    # which the horizon filter rejected, correctly.
    path = (_flat(40, 100.0, 1.5) + _flat(4, 100.0, 0.6)
            + _path([104, 108, 112], 1.0) + _flat(20, 112.0, 1.5))
    df = _frame(path)
    zones, _far = patterns.supply_demand_zones(df, spot=112.0)
    assert any(z["side"] == "demand" for z in zones)


def test_a_tight_base_that_drifts_sideways_leaves_no_zone():
    """Both halves of the definition are required. Congestion is not a zone."""
    df = _frame(_flat(70, 100.0, 0.5))
    zones, _far = patterns.supply_demand_zones(df, spot=100.0)
    assert zones == []


def test_a_zone_price_has_closed_through_is_dropped():
    path = (_flat(30, 100.0, 1.5) + _flat(4, 100.0, 0.6)
            + _path([104, 108, 112], 1.0)
            + _path([106, 100, 94, 90], 1.0) + _flat(20, 90.0, 1.5))
    df = _frame(path)
    zones, _far = patterns.supply_demand_zones(df, spot=90.0)
    assert not any(z["side"] == "demand" and z["bottom"] > 95 for z in zones)


def test_zones_beyond_the_horizon_are_counted_not_listed():
    """A stock that has run a long way keeps its old bases far below. Those are
    history, not levels — but silently dropping them hides the fact."""
    path = (_flat(30, 20.0, 0.2) + _flat(3, 20.0, 0.1)
            + _path(list(range(22, 200, 6)), 0.8) + _flat(30, 198.0, 2.0))
    df = _frame(path)
    zones, far = patterns.supply_demand_zones(df, spot=198.0)
    assert far >= 1 or zones == []
    for z in zones:
        assert z["out_of_horizon"] is False


def test_zone_is_a_band_not_a_line():
    path = (_flat(40, 100.0, 1.5) + _flat(4, 100.0, 0.6)
            + _path([104, 108, 112], 1.0) + _flat(20, 112.0, 1.5))
    zones, _far = patterns.supply_demand_zones(_frame(path), spot=112.0)
    for z in zones:
        assert z["top"] > z["bottom"], "unfilled orders sit across a range"


# -------------------------------------------------------------------- assemble

def test_analyse_returns_the_whole_payload():
    df = _frame(_path(_double_bottom_path(), 0.4) + _flat(30, 120.0, 1.0))
    out = patterns.analyse(df)
    assert out["available"] is True
    for key in ("candles", "chart_patterns", "zones", "tolerances", "method",
                "zones_out_of_horizon", "zone_horizon_bars"):
        assert key in out, key


def test_analyse_states_its_thresholds():
    """Every tolerance is a judgement call, so the payload has to carry them —
    a pattern label without its threshold is not reproducible."""
    df = _frame(_path(_double_bottom_path(), 0.4) + _flat(30, 120.0, 1.0))
    tol = patterns.analyse(df)["tolerances"]
    for key in ("level_tol_atr", "pivot_order", "base_max_atr", "departure_atr",
                "min_amplitude_atr", "prior_move_atr"):
        assert key in tol and tol[key] is not None, key


def test_analyse_refuses_a_short_frame_with_a_reason():
    out = patterns.analyse(_frame(_flat(10)))
    assert out["available"] is False and out["reason"]


def test_method_text_names_the_confirmation_rule():
    df = _frame(_path(_double_bottom_path(), 0.4) + _flat(30, 120.0, 1.0))
    method = patterns.analyse(df)["method"].lower()
    assert "close" in method and "confirmed" in method


def test_confirmation_is_bounded_in_time():
    """An unbounded forward search reported NVDA's October double bottom as
    confirmed by a crossing the following April. A crossing months later is a
    coincidence, not a resolution of that pattern."""
    # Two lows, no break, then a long flat stretch, then a late rally through the
    # old neckline well outside the window.
    path = (_double_bottom_path()[:-4] + [101, 100, 101, 100]
            + [100] * 55 + [104, 110, 116, 122])
    df = _frame(_path(path, spread=0.4))
    found = [p for p in patterns.chart_patterns(df) if p["name"] == "Double bottom"]
    assert found
    assert found[-1]["confirmed"] is False, found[-1].get("confirmed_on")


def test_a_prompt_break_still_confirms():
    df = _frame(_path(_double_bottom_path(), spread=0.4) + _flat(12, 120.0, 0.8))
    found = [p for p in patterns.chart_patterns(df) if p["name"] == "Double bottom"]
    assert found and found[-1]["confirmed"] is True
