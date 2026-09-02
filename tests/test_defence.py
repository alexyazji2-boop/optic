"""Tests for app/analytics/defence.py.

The core claim is directional: in an uptrend the binding level is the *highest*
one below price, in a downtrend the *lowest* above it. Get that backwards and the
panel confidently quotes a level price has already cleared by 10%, so it is
asserted from both sides.
"""

from datetime import datetime, timezone

import pytest
from zoneinfo import ZoneInfo

from app.analytics import defence

ET = ZoneInfo("America/New_York")


def _lv(label, price, breaks="something"):
    return {"label": label, "price": price, "breaks": breaks}


# ----------------------------------------------------------- which level binds

def test_uptrend_defends_the_highest_level_below_price():
    out = defence.evaluate(100.0, "up", [
        _lv("far below", 80.0), _lv("just below", 98.0), _lv("mid", 90.0),
        _lv("above, irrelevant", 110.0),
    ])
    assert out["available"] is True
    assert out["must_hold"]["label"] == "just below"
    assert out["next_level"]["label"] == "mid"


def test_downtrend_defends_the_lowest_level_above_price():
    out = defence.evaluate(100.0, "down", [
        _lv("far above", 130.0), _lv("just above", 102.0), _lv("mid", 115.0),
        _lv("below, irrelevant", 90.0),
    ])
    assert out["must_hold"]["label"] == "just above"
    assert out["next_level"]["label"] == "mid"


def test_levels_on_the_wrong_side_are_excluded_not_reported_broken():
    """In an uptrend, an average above price is resistance — a different question."""
    out = defence.evaluate(100.0, "up", [_lv("below", 95.0), _lv("above", 105.0)])
    labels = [lv["label"] for lv in out["levels"]]
    assert labels == ["below"]


def test_no_level_on_the_defended_side_says_the_trend_has_changed():
    out = defence.evaluate(100.0, "up", [_lv("above", 105.0), _lv("higher", 110.0)])
    assert out["available"] is True
    assert out["must_hold"] is None
    assert "wrong side" in out["note"]


# ------------------------------------------------------------------- reporting

def test_cushion_and_requirement_describe_the_close():
    out = defence.evaluate(100.0, "up", [_lv("level", 99.0, "the uptrend")])
    assert out["cushion_pct"] == pytest.approx(1.0, abs=0.01)
    assert "at or above" in out["requirement"]
    assert out["consequence"] == "the uptrend"
    assert out["tight"] is False


def test_a_thin_cushion_is_flagged():
    out = defence.evaluate(100.0, "up", [_lv("level", 99.8)])
    assert out["tight"] is True


def test_downtrend_requirement_reads_the_other_way():
    out = defence.evaluate(100.0, "down", [_lv("level", 101.0)])
    assert "at or below" in out["requirement"]


def test_duplicate_prices_appear_once():
    """Two sources naming the same price listed it twice in the ladder."""
    out = defence.evaluate(100.0, "up", [
        _lv("40-week average", 90.0), _lv("Accumulation zone", 90.001),
        _lv("other", 85.0),
    ])
    prices = [round(lv["price"], 2) for lv in out["levels"]]
    assert len(prices) == len(set(prices))
    assert out["levels"][0]["label"] == "40-week average"   # first mention wins


# -------------------------------------------------------------- minutes to close

@pytest.mark.parametrize("hh,mm,expected", [
    (15, 0, 60),      # 3pm -> an hour left
    (9, 30, 390),     # the open
    (15, 59, 1),
])
def test_minutes_to_close_inside_the_session(hh, mm, expected):
    when = datetime(2026, 8, 6, hh, mm, tzinfo=ET).astimezone(timezone.utc)
    assert defence.minutes_to_close(when) == expected


@pytest.mark.parametrize("hh,mm", [(8, 0), (16, 0), (20, 30)])
def test_minutes_to_close_is_none_outside_the_session(hh, mm):
    when = datetime(2026, 8, 6, hh, mm, tzinfo=ET).astimezone(timezone.utc)
    assert defence.minutes_to_close(when) is None


def test_minutes_to_close_is_none_at_the_weekend():
    sat = datetime(2026, 8, 8, 12, 0, tzinfo=ET).astimezone(timezone.utc)
    assert defence.minutes_to_close(sat) is None


# ------------------------------------------------------------------ robustness

@pytest.mark.parametrize("spot", [None, 0, -5, float("nan"), "abc"])
def test_a_nonsense_spot_is_unavailable(spot):
    assert defence.evaluate(spot, "up", [_lv("x", 10.0)])["available"] is False


def test_an_unknown_direction_is_unavailable():
    assert defence.evaluate(100.0, "sideways", [_lv("x", 90.0)])["available"] is False


def test_levels_without_a_usable_price_are_dropped():
    out = defence.evaluate(100.0, "up", [
        {"label": "no price"}, {"label": "bad", "price": "abc"},
        {"price": 95.0}, _lv("good", 96.0),
    ])
    assert [lv["label"] for lv in out["levels"]] == ["good"]


def test_no_candidates_at_all_is_unavailable():
    assert defence.evaluate(100.0, "up", [])["available"] is False


# -------------------------------------------------------------------- adapters

def test_swing_adapter_uses_daily_levels_and_reads_the_bias():
    payload = {
        "technicals": {
            "spot": 100.0,
            "bias": "bullish",
            "moving_averages": {
                "ema9": {"value": 98.0}, "ema21": {"value": 95.0},
                "sma200": {"value": 80.0},
            },
        },
        "structure": {"pivots": {"available": True, "pp": 97.0}},
    }
    out = defence.for_swing(payload)
    assert out["horizon"] == "daily"
    assert out["direction"] == "up"
    assert out["must_hold"]["label"] == "9-day EMA"


def test_swing_adapter_falls_back_when_the_bias_is_neutral():
    payload = {
        "technicals": {
            "spot": 100.0, "bias": "neutral",
            "moving_averages": {"sma50": {"value": 90.0}, "ema9": {"value": 97.0}},
        },
    }
    out = defence.for_swing(payload)
    assert out["direction"] == "up"          # above the 50-day


def test_longterm_adapter_uses_weekly_levels_only():
    holding = {
        "price": 200.0,
        "long_trend": {"phase": "advancing", "sma_40w": 180.0, "sma_200w": 110.0,
                       "above_40w_sma": True},
        "accumulation_zones": [{"label": "zone", "price": 150.0}],
    }
    out = defence.for_longterm(holding)
    assert out["horizon"] == "weekly"
    assert out["must_hold"]["label"] == "40-week average"
    # No daily average should ever appear at this horizon.
    assert not any("day" in lv["label"] for lv in out["levels"])
    assert "Friday" in out["cadence_note"]


def test_adapters_survive_junk_input():
    for fn in (defence.for_swing, defence.for_longterm):
        assert fn({})["available"] is False
        assert fn(None)["available"] is False
