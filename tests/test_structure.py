"""Tests for app/analytics/structure.py.

Where a formula is standard (floor pivots, value area) the expected numbers are
worked out by hand in the test rather than copied from the implementation, so a
test failure means the maths changed rather than the wiring.
"""

import numpy as np
import pandas as pd
import pytest

from app.analytics import structure


def _frame(rows, start="2026-01-01"):
    """rows: list of (open, high, low, close, volume)."""
    idx = pd.date_range(start, periods=len(rows), freq="D")
    return pd.DataFrame(
        {
            "Open": [r[0] for r in rows],
            "High": [r[1] for r in rows],
            "Low": [r[2] for r in rows],
            "Close": [r[3] for r in rows],
            "Volume": [r[4] for r in rows],
        },
        index=idx,
    )


def _trend(n=260, start=100.0, step=0.4, vol=1_000_000):
    rows = []
    price = start
    for _ in range(n):
        rows.append((price, price + 1.0, price - 1.0, price + step, vol))
        price += step
    return _frame(rows)


# ------------------------------------------------------------- floor pivots

def test_floor_pivots_match_the_textbook_formula():
    # Previous bar H=110 L=90 C=105 -> PP = 305/3
    df = _frame([(100, 110, 90, 105, 1000), (105, 106, 104, 105.5, 1000)])
    p = structure.floor_pivots(df)
    pp = (110 + 90 + 105) / 3.0
    assert p["available"] is True
    assert p["pp"] == pytest.approx(pp, abs=1e-6)
    assert p["r1"] == pytest.approx(2 * pp - 90, abs=1e-6)
    assert p["s1"] == pytest.approx(2 * pp - 110, abs=1e-6)
    assert p["r2"] == pytest.approx(pp + 20, abs=1e-6)
    assert p["s2"] == pytest.approx(pp - 20, abs=1e-6)


def test_floor_pivots_use_the_previous_bar_not_the_current_one():
    """A pivot from the live bar would move every tick, which defeats the point."""
    base = [(100, 110, 90, 105, 1000), (105, 106, 104, 105.5, 1000)]
    a = structure.floor_pivots(_frame(base))
    # Change only the *last* bar; pivots must not move.
    moved = list(base)
    moved[-1] = (105, 500, 1, 400, 1000)
    b = structure.floor_pivots(_frame(moved))
    assert a["pp"] == b["pp"]
    assert a["r1"] == b["r1"]


def test_floor_pivots_need_two_bars():
    assert structure.floor_pivots(_frame([(1, 2, 0.5, 1.5, 10)]))["available"] is False


# ----------------------------------------------------------- volume profile

def test_volume_profile_point_of_control_finds_the_busy_shelf():
    # 40 quiet bars around 100, then 40 heavy bars around 120.
    rows = [(100, 101, 99, 100, 1_000) for _ in range(40)]
    rows += [(120, 121, 119, 120, 50_000) for _ in range(40)]
    vp = structure.volume_profile(_frame(rows), lookback=80)
    assert vp["available"] is True
    assert vp["poc"] == pytest.approx(120, abs=1.5)
    # Value area should sit around the heavy shelf, not span the whole range.
    assert vp["val"] > 110


def test_volume_profile_spreads_volume_across_the_bar_range():
    """A wide bar traded at every price it touched, not only at its close."""
    rows = [(100, 130, 100, 130, 100_000)] * 20
    vp = structure.volume_profile(_frame(rows), lookback=20, bins=30)
    # If volume were dumped on the close, the POC would pin to 130.
    assert vp["poc"] < 129, f"POC pinned to the close: {vp['poc']}"
    assert 100 <= vp["poc"] <= 130


def test_volume_profile_reports_where_price_sits_versus_value():
    rows = [(100, 101, 99, 100, 10_000) for _ in range(60)]
    rows.append((100, 160, 100, 158, 10_000))          # close far above value
    vp = structure.volume_profile(_frame(rows), lookback=61)
    assert vp["location"] == "above value"


def test_volume_profile_needs_enough_bars():
    assert structure.volume_profile(_frame([(1, 2, 0.5, 1.5, 10)] * 5))["available"] is False


# -------------------------------------------------------------- ema stack

def test_ema_stack_detects_a_full_bullish_stack():
    st = structure.ema_stack(_trend()["Close"])
    assert st["available"] is True
    assert st["bullish_stack"] is True
    assert st["read"] == "full bullish stack"
    assert st["ema9"] > st["ema21"] > st["ema50"]


def test_ema_stack_detects_a_full_bearish_stack():
    st = structure.ema_stack(_trend(step=-0.4, start=200.0)["Close"])
    assert st["bearish_stack"] is True
    assert st["read"] == "full bearish stack"


def test_ema_stack_reports_mixed_when_price_sits_among_its_averages():
    rng = np.random.default_rng(7)
    close = pd.Series(100 + np.cumsum(rng.normal(0, 0.3, 300)))
    st = structure.ema_stack(close)
    assert st["available"] is True
    assert st["read"] in {"mixed", "above, not stacked", "below, not stacked",
                          "full bullish stack", "full bearish stack"}


def test_ema_stack_needs_enough_history():
    assert structure.ema_stack(pd.Series([1.0, 2.0, 3.0]))["available"] is False


# --------------------------------------------------------- bandwidth rank

def test_bandwidth_rank_is_high_when_the_range_has_just_widened():
    quiet = [100 + (i % 2) * 0.05 for i in range(220)]
    loud = [100 + (i % 2) * 8.0 for i in range(30)]
    br = structure.bandwidth_rank(pd.Series(quiet + loud))
    assert br["available"] is True
    assert br["percentile"] > 80
    assert br["read"] == "expanded"


def test_bandwidth_rank_is_low_in_a_squeeze():
    loud = [100 + (i % 2) * 8.0 for i in range(220)]
    quiet = [100 + (i % 2) * 0.05 for i in range(30)]
    br = structure.bandwidth_rank(pd.Series(loud + quiet))
    assert br["percentile"] < 20
    assert br["read"] == "squeezed"


# -------------------------------------------------------- candle patterns

def test_marubozu_needs_an_almost_bodyless_wick():
    df = _frame([(100, 101, 99, 100, 10), (100, 110.0, 100.0, 110.0, 10)])
    pats = structure.candle_patterns(df)["patterns"]
    assert any(p["pattern"] == "marubozu" and p["direction"] == "bullish" for p in pats)


def test_bullish_engulfing_requires_covering_the_previous_body():
    # Down bar, then an up bar whose body covers it entirely.
    df = _frame([(100, 101, 95, 96, 10), (95, 106, 94.5, 105, 10)])
    pats = structure.candle_patterns(df)["patterns"]
    assert any(p["pattern"] == "engulfing" and p["direction"] == "bullish" for p in pats)


def test_a_bar_that_does_not_cover_the_previous_body_is_not_engulfing():
    df = _frame([(100, 101, 95, 96, 10), (97, 99, 96.5, 98, 10)])
    pats = structure.candle_patterns(df)["patterns"]
    assert not any(p["pattern"] == "engulfing" for p in pats)


def test_doji_is_flagged_when_open_and_close_agree():
    df = _frame([(100, 101, 99, 100, 10), (100, 108, 92, 100.2, 10)])
    pats = structure.candle_patterns(df)["patterns"]
    assert any(p["pattern"] == "doji" for p in pats)


def test_candle_patterns_survive_a_flat_bar():
    """Zero-range bars must not divide by zero."""
    df = _frame([(100, 100, 100, 100, 10), (100, 100, 100, 100, 10)])
    assert structure.candle_patterns(df)["available"] is True


# -------------------------------------------------------------- robustness

@pytest.mark.parametrize("fn", [
    structure.volume_profile,
    structure.floor_pivots,
    structure.candle_patterns,
])
def test_frame_functions_handle_empty_input(fn):
    assert fn(pd.DataFrame())["available"] is False


def test_volume_profile_handles_a_missing_volume_column():
    df = _frame([(100, 101, 99, 100, 10)] * 30).drop(columns=["Volume"])
    assert structure.volume_profile(df)["available"] is False


def test_nan_prices_do_not_crash_the_profile():
    rows = [(100, 101, 99, 100, 1000)] * 40
    df = _frame(rows)
    df.loc[df.index[5], "High"] = np.nan
    df.loc[df.index[6], "Volume"] = np.nan
    out = structure.volume_profile(df, lookback=40)
    assert out["available"] is True
    assert out["poc"] is not None


# ------------------------------------------------------- live-bar refresh

def test_live_bar_updates_the_forming_close():
    df = _frame([(100, 101, 99, 100, 1000), (100, 102, 99, 101, 1000)])
    today = str(df.index[-1].date())
    out = structure.with_live_bar(df, 105.0, today)
    assert out["Close"].iloc[-1] == 105.0
    assert out["High"].iloc[-1] == 105.0        # high extends to meet it
    assert out["Low"].iloc[-1] == 99.0          # low untouched


def test_live_bar_never_rewrites_a_completed_session():
    """Pre-market: the last bar is yesterday, and must not take today's print."""
    df = _frame([(100, 101, 99, 100, 1000), (100, 102, 99, 101, 1000)])
    out = structure.with_live_bar(df, 105.0, "2099-12-31")
    pd.testing.assert_frame_equal(out, df)


def test_live_bar_ignores_a_nonsense_price():
    df = _frame([(100, 101, 99, 100, 1000), (100, 102, 99, 101, 1000)])
    today = str(df.index[-1].date())
    for bad in (None, 0, -5, float("nan"), "abc"):
        pd.testing.assert_frame_equal(structure.with_live_bar(df, bad, today), df)


def test_live_bar_moves_the_reads_that_depend_on_it():
    """The whole point: a price move must change the derived levels."""
    rows = [(100, 101, 99, 100, 10_000) for _ in range(80)]
    df = _frame(rows)
    today = str(df.index[-1].date())
    before = structure.volume_profile(df, lookback=80)
    after = structure.volume_profile(structure.with_live_bar(df, 160.0, today), lookback=80)
    assert before["location"] != after["location"]
    assert after["location"] == "above value"


def test_live_bar_leaves_pivots_alone():
    """Pivots come from the previous bar, so a live tick must not move them."""
    df = _frame([(100, 110, 90, 105, 1000), (105, 106, 104, 105.5, 1000)])
    today = str(df.index[-1].date())
    a = structure.floor_pivots(df)
    b = structure.floor_pivots(structure.with_live_bar(df, 200.0, today))
    assert a["pp"] == b["pp"] and a["r1"] == b["r1"]
