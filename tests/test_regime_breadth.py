"""The regime score's breadth input is the share of sectors above their 200-day (2026-10-21).

regime.py labelled its breadth input "% of sectors above their 200-day", but the
brief handed it `sector_breadth_pct`, the share of sector ETFs up today. That is
the quantity the leadership input already measures, so one day's move was
counted twice, at 25% and 10% of the score, under two names. The brief only
fetched three months of bars, so no 200-day average could be taken from it.

Now the brief fetches a year and computes each sector's close against its own
200-session average; the regime reads that share, and the up-today share stays
with leadership and the written read's "N% of the eleven closed up".
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app import brief
from app.analytics import regime


def _frame(trend_up: bool, up_today: bool, bars: int = 252) -> pd.DataFrame:
    """A year of closes rising or falling steadily, with the last day up or down."""
    step = 0.002 if trend_up else -0.002
    close = 100 * np.exp(np.cumsum(np.full(bars, step)))
    close[-1] = close[-2] * (1.01 if up_today else 0.99)
    idx = pd.bdate_range("2025-10-01", periods=bars)
    return pd.DataFrame({"Open": close, "High": close, "Low": close, "Close": close,
                         "Volume": np.full(bars, 1e6)}, index=idx)


class _Provider:
    """Eight sectors in uptrends but down today, three in downtrends but up today."""

    def __init__(self):
        self.periods = []

    def batch_history(self, symbols, period="1y", interval="1d"):
        self.periods.append(period)
        sectors = [s["symbol"] for s in brief.SECTORS]
        out = {}
        for sym in symbols:
            if sym in sectors:
                rising = sectors.index(sym) < 8
                out[sym] = _frame(trend_up=rising, up_today=not rising)
            else:
                out[sym] = _frame(trend_up=True, up_today=True)
        return out


def test_the_brief_fetches_enough_history_for_a_200_day_average():
    p = _Provider()
    brief._overview(p)
    assert p.periods == ["1y"]


def test_the_two_breadths_are_measured_apart():
    ov = brief._overview(_Provider())
    n = len(brief.SECTORS)
    assert ov["sector_breadth_pct"] == round(100.0 * 3 / n, 1)        # up today
    assert ov["sectors_above_200d_pct"] == round(100.0 * 8 / n, 1)    # above the 200-day
    assert (ov["sectors_above_200d"], ov["sectors_measured_200d"]) == (8, n)
    rows = {r["symbol"]: r for r in ov["groups"]["sectors"]}
    assert rows[brief.SECTORS[0]["symbol"]]["above_200d"] is True
    assert rows[brief.SECTORS[-1]["symbol"]]["above_200d"] is False


def test_the_regime_breadth_reads_the_200_day_share_not_today():
    ov = brief._overview(_Provider())
    got = regime.score(ov)
    above = ov["sectors_above_200d_pct"]
    mid = (regime.BREADTH_HEALTHY + regime.BREADTH_WEAK) / 2
    span = (regime.BREADTH_HEALTHY - regime.BREADTH_WEAK) / 2
    assert got["components"]["breadth"] == round(max(-100, min(100, (above - mid) / span * 100)), 1)
    # Leadership is still today's share: 3 of 11 up.
    assert got["components"]["leadership"] == round((100.0 * 3 / len(brief.SECTORS) - 50) * 2, 1)
    assert "8 of {} sectors above their 200-day".format(len(brief.SECTORS)) in got["notes"]
    assert "3 of {} sectors higher today".format(len(brief.SECTORS)) in got["notes"]


def test_the_up_today_share_alone_is_never_read_as_breadth():
    """An overview with only the up-today share (an archived brief) has no breadth
    input; the weights renormalise over the rest rather than counting today twice."""
    sectors = [{"symbol": s["symbol"], "day": 0.5} for s in brief.SECTORS]
    got = regime.score({"groups": {"indices": [{"symbol": "SPY", "week": 1.0, "month": 2.0}],
                                   "sectors": sectors},
                        "sector_breadth_pct": 100.0})
    assert "breadth" not in got["components"]
    assert set(got["components"]) == {"trend", "leadership"}


def test_too_little_history_leaves_breadth_out():
    class Short(_Provider):
        def batch_history(self, symbols, period="1y", interval="1d"):
            return {s: _frame(True, True, bars=150) for s in symbols}

    ov = brief._overview(Short())
    assert ov["sectors_above_200d_pct"] is None
    assert all(r["above_200d"] is None for r in ov["groups"]["sectors"])
    assert "breadth" not in regime.score(ov)["components"]
