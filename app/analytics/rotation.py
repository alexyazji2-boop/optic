"""Relative rotation: which sectors are gaining on the index, and which are losing it.

Two numbers per sector, both centred on 100:

  * **Relative strength** — how the sector is doing against the benchmark
    compared with its own recent norm. Above 100 means it is outperforming by
    more than usual for it.
  * **Relative momentum** — whether that relative strength is rising or falling.
    Above 100 means the sector is gaining ground; below 100 means losing it.

Plotted against each other they make four quadrants, and sectors move between
them in a broadly clockwise loop:

    Improving  (weak, but gaining)   |  Leading   (strong and still gaining)
    ------------------------------------------------------------------------
    Lagging    (weak and losing)     |  Weakening (strong, but losing)

The tail is the point of the chart. A single dot says where a sector is; the
tail says where it came from and how fast, and those are the parts that decide
whether "Leading" means early or nearly over.

**On the naming.** This is not the JdK RS-Ratio and RS-Momentum, and the chart is
not an RRG®. Those are Julius de Kempenaer's, trademarked, and their exact
normalisation is not published — anyone claiming to reproduce them from a blog
post is guessing. What follows is a documented method of the same shape, using
the same quadrant layout because the layout is the useful part. The numbers will
not tie out against StockCharts and are not meant to.

**The method, stated so it can be argued with.**

    rs        = sector close / benchmark close
    trend     = rs / SMA(rs, LOOKBACK)                  ... relative to its own norm
    strength  = 100 + Z(trend) * SCALE                  ... z-scored over NORM_WINDOW
    momentum  = 100 + Z(strength - SMA(strength, MOM))  * SCALE

The z-score is what puts both axes on a comparable scale, and it is also the
method's main limitation: it is normalised over a trailing window, so a reading
of 102 means "unusual for this sector over the last two years", not "unusual in
absolute terms". A sector that has quietly outperformed for the whole window
looks ordinary, because the window has absorbed it.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from .sectors import BENCHMARK, SECTORS

log = logging.getLogger(__name__)

HISTORY = "2y"

# Weekly bars. Daily rotation is mostly noise — the tail thrashes across quadrant
# boundaries on nothing — and weekly is the timeframe the chart is read on.
INTERVAL = "1wk"

# How far back "its own norm" reaches, in bars. Ten weeks is a quarter.
LOOKBACK = 10
# The window the z-score is taken over. Two years of weekly bars is ~104.
NORM_WINDOW = 52
# Momentum is the change in strength against its own short average.
MOM_WINDOW = 4
SMOOTH = 5

# Smoothing on both output series, in weeks.
#
# Not cosmetic. Unsmoothed, the median week-to-week step measured 1.6 units
# against a plot half-width of 5.9 — every sector jumped a quarter of the chart
# per week and the tails crossed each other into an unreadable tangle, nothing
# like the clean arcs the layout is meant to produce. A z-score of a difference
# is noisy by construction, and the rolling window's own mean and deviation move
# under it each bar.
#
# At span 5 the median step falls to 0.57, about 13% of the half-width, which is
# the readable range. The cost is real and worth stating: an EMA lags, so a
# sector that turns shows it here a week or two after it turned. This chart is
# for reading rotation, not for calling the exact bar it started.
# Z-scores mostly land in ±3. Scaling by 2 puts a typical reading inside 94-106,
# which is the range these charts are conventionally drawn on.
SCALE = 2.0

# How many points of history to draw behind each sector.
TAIL = 8

# Below this many bars the z-score is being taken over too little to mean
# anything, and the sector is dropped rather than plotted at a made-up 100.
MIN_BARS = NORM_WINDOW + LOOKBACK + MOM_WINDOW


def _f(value: Any, digits: int = 2) -> Optional[float]:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(out) else round(out, digits)


def quadrant(strength: float, momentum: float) -> str:
    """The four names, from the two signs. Nothing else decides this."""
    if strength >= 100:
        return "leading" if momentum >= 100 else "weakening"
    return "improving" if momentum >= 100 else "lagging"


def _z(series: pd.Series, window: int) -> pd.Series:
    """Rolling z-score.

    `ddof=0` because this is a description of the window, not an estimate of a
    wider population — and because with ddof=1 a flat window divides by zero.
    """
    mean = series.rolling(window, min_periods=window).mean()
    sd = series.rolling(window, min_periods=window).std(ddof=0)
    # A sector that has moved with the benchmark all window has no deviation to
    # score against. That is "perfectly ordinary", which is 100, not infinity.
    #
    # The test is relative, not `sd == 0`. A sector holding an exact constant
    # ratio to the index still produces float dust in that ratio — 1.7 * x / x is
    # not exactly 1.7 — and dividing by a standard deviation of 1e-16 amplifies
    # that dust into a reading. Caught in a test where a sector tracking the
    # index exactly came out at 99.95 rather than 100.00: small, but it is
    # numerical noise being presented as a position on the chart.
    tiny = series.abs().rolling(window, min_periods=window).mean() * 1e-9
    return ((series - mean) / sd.where(sd > tiny)).fillna(0.0)


def _track(close: pd.Series, bench: pd.Series) -> Optional[pd.DataFrame]:
    """One sector's path through the two axes."""
    joined = pd.concat({"s": close, "b": bench}, axis=1).dropna()
    if len(joined) < MIN_BARS:
        return None

    rs = joined["s"] / joined["b"]
    trend = rs / rs.rolling(LOOKBACK, min_periods=LOOKBACK).mean()
    strength = 100.0 + _z(trend, NORM_WINDOW) * SCALE

    # Momentum is the change in strength, not the change in price. A sector can
    # be outperforming and losing momentum at the same time, and that is the
    # distinction the top-right and bottom-right quadrants exist to make.
    delta = strength - strength.rolling(MOM_WINDOW, min_periods=MOM_WINDOW).mean()
    momentum = 100.0 + _z(delta, NORM_WINDOW) * SCALE

    out = pd.DataFrame({"strength": strength, "momentum": momentum}).dropna()
    if SMOOTH > 1 and len(out):
        out = out.ewm(span=SMOOTH, adjust=False).mean()
    return out if len(out) else None


def build(provider, tail: int = TAIL) -> Dict[str, Any]:
    """The rotation payload: one track per sector, most recent point last."""
    symbols = [s["symbol"] for s in SECTORS]
    frames = provider.batch_history(symbols + [BENCHMARK],
                                    period=HISTORY, interval=INTERVAL)
    bench_df = frames.get(BENCHMARK)
    if bench_df is None or bench_df.empty:
        return {"error": "benchmark history unavailable", "benchmark": BENCHMARK}
    bench = bench_df["Close"].astype(float).dropna()
    bench.index = pd.to_datetime(bench.index).tz_localize(None)

    rows: List[Dict[str, Any]] = []
    skipped: List[str] = []
    for meta in SECTORS:
        df = frames.get(meta["symbol"])
        if df is None or df.empty:
            skipped.append(meta["symbol"])
            continue
        close = df["Close"].astype(float).dropna()
        close.index = pd.to_datetime(close.index).tz_localize(None)
        track = _track(close, bench)
        if track is None:
            skipped.append(meta["symbol"])
            continue

        points = track.tail(max(tail, 2))
        path = [{"date": str(d.date()),
                 "strength": _f(r.strength), "momentum": _f(r.momentum)}
                for d, r in points.iterrows()]
        now = path[-1]
        prev = path[-2]
        rows.append({
            "symbol": meta["symbol"],
            "name": meta["name"],
            "strength": now["strength"],
            "momentum": now["momentum"],
            "quadrant": quadrant(now["strength"], now["momentum"]),
            "previous_quadrant": quadrant(prev["strength"], prev["momentum"]),
            # The tail's own direction, which is what "rotating" means here.
            "d_strength": _f(now["strength"] - prev["strength"]),
            "d_momentum": _f(now["momentum"] - prev["momentum"]),
            "path": path,
        })

    if not rows:
        return {"error": "no sector had enough history to plot", "benchmark": BENCHMARK}

    rows.sort(key=lambda r: (r["strength"] or 0) + (r["momentum"] or 0), reverse=True)
    counts: Dict[str, int] = {}
    for r in rows:
        counts[r["quadrant"]] = counts.get(r["quadrant"], 0) + 1

    moved = [r for r in rows if r["quadrant"] != r["previous_quadrant"]]

    return {
        "benchmark": BENCHMARK,
        "interval": "weekly",
        "tail": tail,
        "as_of": rows[0]["path"][-1]["date"],
        "sectors": rows,
        "counts": counts,
        "crossed": [{"symbol": r["symbol"], "name": r["name"],
                     "from": r["previous_quadrant"], "to": r["quadrant"]}
                    for r in moved],
        "skipped": skipped,
        "params": {"lookback": LOOKBACK, "norm_window": NORM_WINDOW,
                   "momentum_window": MOM_WINDOW, "scale": SCALE,
                   "smooth": SMOOTH},
    }
