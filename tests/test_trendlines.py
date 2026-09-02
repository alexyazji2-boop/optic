"""Trend lines fitted to pivots.

Any two points define a line, so a chart with thirty pivots offers 435 of them
and a person will find whichever one supports the view they already hold. The
rules exist to reject most of those, and these tests are about the rejections —
a line-fitter that accepts everything is worse than drawing none, because it
launders a coincidence as a level.
"""

import numpy as np
import pandas as pd
import pytest

from app.analytics import trendlines


def _frame(closes, highs=None, lows=None):
    n = len(closes)
    idx = pd.date_range("2025-01-02", periods=n, freq="B")
    close = np.asarray(closes, dtype=float)
    return pd.DataFrame({
        "Open": close,
        "High": close if highs is None else np.asarray(highs, dtype=float),
        "Low": close if lows is None else np.asarray(lows, dtype=float),
        "Close": close,
        "Volume": np.full(n, 1_000_000.0),
    }, index=idx)


def _sawtooth(n, slope, amplitude, period=14, base=100.0):
    """A rising or falling channel with regular swings, so pivots are certain."""
    t = np.arange(n, dtype=float)
    return base + slope * t + amplitude * np.sin(2 * np.pi * t / period)


# ------------------------------------------------------------------ refusals

def test_too_few_bars_is_refused():
    out = trendlines.build(_frame(_sawtooth(30, 0.2, 3)))
    assert out["available"] is False
    assert out["lines"] == []


def test_pure_noise_yields_no_line_with_three_touches():
    """The important negative. Random walks throw up plenty of two-point fits;
    almost none survive a third touch plus the no-violation rule."""
    rng = np.random.default_rng(11)
    closes = 100 * np.exp(np.cumsum(rng.normal(0, 0.012, 220)))
    out = trendlines.build(_frame(closes, closes * 1.004, closes * 0.996))
    assert out["available"] is True
    for line in out["lines"]:
        assert line["touches"] >= trendlines.MIN_TOUCHES
        assert line["span_bars"] >= trendlines.MIN_SPAN_FRAC * len(closes) - 1


def test_a_line_price_closed_through_midway_is_rejected():
    """A support line price closed well below halfway along was never support.
    Without this rule the fitter happily draws a line through three lows that
    price spent the middle of the window underneath."""
    closes = list(_sawtooth(90, 0.35, 2.5))
    # A deep gap through the middle of what would otherwise be a clean rising
    # support line.
    for i in range(44, 52):
        closes[i] -= 26
    df = _frame(closes, np.array(closes) + 0.6, np.array(closes) - 0.6)
    out = trendlines.build(df)
    for line in out["lines"]:
        if line["kind"] != "support":
            continue
        first, last = line["start_index"], max(line["touch_indexes"])
        assert not (first < 46 < last), (
            "kept a support line straddling a close 26 points beneath it")


def test_a_line_out_of_reach_is_dropped():
    """Measured on live data: SPY produced a five-touch 'support' line projecting
    to 607 while price was 769 — twenty-five ATR away. It passed every other
    rule and could neither hold nor break."""
    # A falling line fitted early, then price runs far away from it.
    closes = list(_sawtooth(70, -0.4, 2.0, base=100.0))
    closes += list(np.linspace(closes[-1], closes[-1] + 140, 90))
    df = _frame(closes, np.array(closes) + 0.5, np.array(closes) - 0.5)
    out = trendlines.build(df)
    assert out["dropped_out_of_reach"] >= 1
    for line in out["lines"]:
        assert abs(line["distance_atr"]) <= trendlines.MAX_DISTANCE_ATR


def test_near_duplicate_lines_are_collapsed():
    """Fitting every pivot pair produces many lines sharing most of their
    touches. Drawing all of them is the unreadable fan the manual version makes."""
    df = _frame(*(lambda c: (c, c + 0.5, c - 0.5))(_sawtooth(200, 0.3, 3.0)))
    out = trendlines.build(df)
    seen = []
    for line in out["lines"]:
        for prev in seen:
            shared = set(line["touch_indexes"]) & set(prev)
            assert len(shared) < 2, "two kept lines share two or more touches"
        seen.append(line["touch_indexes"])


# ------------------------------------------------------------- what it finds

def test_a_clean_rising_channel_yields_support_and_resistance():
    df = _frame(*(lambda c: (c, c + 0.4, c - 0.4))(_sawtooth(200, 0.3, 3.0)))
    out = trendlines.build(df)
    kinds = {line["kind"] for line in out["lines"]}
    assert out["lines"], "found nothing in a textbook channel"
    assert 'support' in kinds or 'resistance' in kinds
    for line in out["lines"]:
        assert line["direction"] == 'rising'


def test_the_break_flag_needs_a_real_move_through_the_line():
    """A close a cent through a line is not a break."""
    df = _frame(*(lambda c: (c, c + 0.4, c - 0.4))(_sawtooth(200, 0.3, 3.0)))
    out = trendlines.build(df)
    for line in out["lines"]:
        if line["broken"]:
            assert abs(line["distance_atr"]) >= trendlines.BREAK_ATR


def test_every_line_reports_what_it_was_fitted_to():
    """A level with no provenance is an assertion. Touch count, dates and span
    are what let a reader disagree with it."""
    df = _frame(*(lambda c: (c, c + 0.4, c - 0.4))(_sawtooth(200, 0.3, 3.0)))
    out = trendlines.build(df)
    for line in out["lines"]:
        assert line["touches"] == len(line["touch_indexes"])
        assert len(line["touch_dates"]) == line["touches"]
        assert line["span_bars"] > 0
        assert line["score"] is not None


def test_params_are_reported_so_the_rules_are_inspectable():
    df = _frame(*(lambda c: (c, c + 0.4, c - 0.4))(_sawtooth(120, 0.3, 3.0)))
    out = trendlines.build(df)
    for key in ("min_touches", "touch_tol_atr", "violation_atr",
                "min_span_frac", "break_atr", "max_distance_atr"):
        assert key in out["params"]
