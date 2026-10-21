"""Support and resistance from confirmed pivots only (2026-10-21).

`support_resistance_levels` found pivots with scipy's `argrelextrema(order=4)`,
whose default mode='clip' compares an edge bar with copies of itself. So any of
the last four bars could count as a swing high or low with nothing yet to its
right, and the level it made could be gone a few sessions later: the factor
audit (docs/portfolio/research-2026-10-21/FACTORS.md) found a level gone five
sessions on in 223 of 240 sampled windows. The paper ledger's stop
(`paper._pick_stop`) sits under the nearest of these levels, so a new low on
today's unfinished bar could hand it a "support" right under the entry.

A pivot now needs four bars on each side inside the window. The first four bars
of the window are left out for the same reason on the left.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app import paper
from app.analytics import technicals

ORDER = 4


def _bars(highs, lows):
    highs = np.asarray(highs, dtype=float)
    lows = np.asarray(lows, dtype=float)
    mid = (highs + lows) / 2
    idx = pd.bdate_range("2026-01-02", periods=len(highs))
    return pd.DataFrame({"Open": mid, "High": highs, "Low": lows, "Close": mid,
                         "Volume": np.full(len(highs), 1e6)}, index=idx)


def _quiet(n, start=0):
    """A gentle wave around 100: highs near 101, lows near 99, no exact ties."""
    i = np.arange(start, start + n)
    wave = 0.3 * np.sin(i / 3.0)
    return list(101 + wave), list(99 + wave)


def _near(levels, price, within=1.0):
    return [lv for lv in levels if abs(lv["price"] - price) <= within]


def _frame_with_new_high_today():
    """A confirmed swing high at 110 long ago, and today's bar at 110.2."""
    highs, lows = _quiet(60)
    highs[20], lows[20] = 110.0, 103.0
    highs[59], lows[59] = 110.2, 103.2
    return highs, lows


def test_the_last_bars_cannot_make_a_level():
    """Today's high at 110.2 used to pair with the old 110 swing high into a
    two-touch resistance, though nothing after today exists to confirm it."""
    highs, lows = _frame_with_new_high_today()
    df = _bars(highs, lows)
    levels = technicals.support_resistance_levels(df, spot=105.0)
    assert _near(levels, 110.1) == []
    assert all(lv["last_touch_bars_ago"] >= ORDER for lv in levels)


def test_the_same_level_appears_once_four_bars_confirm_it_and_then_stays():
    highs, lows = _frame_with_new_high_today()
    more_h, more_l = _quiet(ORDER, start=60)
    df = _bars(highs + more_h, lows + more_l)
    levels = technicals.support_resistance_levels(df, spot=100.0)
    level = _near(levels, 110.1)
    assert len(level) == 1 and level[0]["touches"] == 2
    assert level[0]["last_touch_bars_ago"] == ORDER

    # Further quiet sessions do not take it away.
    later_h, later_l = _quiet(10, start=60 + ORDER)
    df = _bars(highs + more_h + later_h, lows + more_l + later_l)
    assert len(_near(technicals.support_resistance_levels(df, spot=100.0), 110.1)) == 1


def test_no_level_rests_on_an_unconfirmed_pivot_on_random_walks():
    rng = np.random.default_rng(7)
    for _ in range(20):
        close = 100 * np.exp(np.cumsum(rng.normal(0, 0.015, 320)))
        spread = close * rng.uniform(0.004, 0.02, 320)
        df = _bars(close + spread, close - spread)
        bars = len(df.tail(252))
        for end in range(260, 321, 15):
            window = df.iloc[:end]
            for lv in technicals.support_resistance_levels(window, float(window["Close"].iloc[-1])):
                assert ORDER <= lv["last_touch_bars_ago"] <= bars - 1 - ORDER


def test_a_new_low_today_no_longer_sets_the_paper_stop():
    """The stop sat 1% under the nearest support. A fresh low on today's bar
    that matched an old swing low made that support, so a long entered today got
    a stop just under its own bar. Now the old low alone is no level and the
    stop falls back to 2x ATR."""
    highs, lows = _quiet(220)
    highs[100], lows[100] = 97.0, 90.0
    highs[219], lows[219] = 96.8, 90.1
    df = _bars(highs, lows)
    spot = 93.0
    tech = technicals.analyse(df)
    assert _near(tech["support_resistance"], 90.05) == []
    stop = paper._pick_stop({"technicals": tech}, spot, long=True)
    atr14 = tech["volatility"]["atr14"]
    supports = [lv["price"] for lv in tech["support_resistance"] if lv["price"] < spot * 0.995]
    if supports:
        assert stop == round(max(supports) * 0.99, 2)
    else:
        assert stop == round(spot - 2 * atr14, 2)
    assert stop != round(90.05 * 0.99, 2)
