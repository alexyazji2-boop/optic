"""Trend lines fitted to pivots, and whether price has broken one.

A trend line is two or more swing points that lie close enough to a straight
line, extended forward. Drawn from *lows* it is support and rising means an
uptrend; drawn from *highs* it is resistance and falling means a downtrend. A
close through one is a breakout.

**Why this is worth automating rather than eyeballing.** Any two points define a
line, so a chart with thirty pivots offers 435 of them and a person will find
whichever one supports the view they already hold. Requiring a third touch, and
requiring the line not to have been cut through in between, is what separates a
line the market has respected from a line drawn through two coincidences.

**The rules, stated so they can be argued with:**

* Fit through pivot *lows* for support, pivot *highs* for resistance.
* At least ``MIN_TOUCHES`` pivots within ``TOUCH_TOL_ATR`` ATR of the line.
* No close beyond the line by more than ``VIOLATION_ATR`` ATR between the first
  and last touch — a "support" line that price closed well below halfway along
  was not support.
* The span must cover at least ``MIN_SPAN_FRAC`` of the window, so a line fitted
  to three pivots inside a fortnight is not presented as the trend.
* Lines are scored and the strongest few kept, because ten overlapping lines is
  the same unreadable chart the manual version produces.

**What this deliberately does not do.** It does not predict. A break is reported
as a break, with how far price is through the line in ATR, and nothing here says
what happens next — the pattern base-rate module is where that question belongs.
"""

from __future__ import annotations

import itertools
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from .patterns import _atr_series, find_pivots

# A line needs a third touch. Two points are a coincidence.
MIN_TOUCHES = 3
# How close a pivot must sit to count as touching, in ATR.
TOUCH_TOL_ATR = 0.45
# How far a close may sit beyond the line, mid-span, before the line is void.
VIOLATION_ATR = 0.8
# Fraction of the window the line must span.
MIN_SPAN_FRAC = 0.25
# How many of each kind to return.
MAX_LINES = 3
# A break has to clear the line by this much to be called one, so a close a cent
# through is not a signal.
BREAK_ATR = 0.3
# How far the line may sit from the current price and still be worth drawing.
#
# Found by running this on SPY: a falling "support" line fitted to five pivots
# scored 266 and projected to 607 while price was at 769 — twenty-five ATR away.
# It satisfied every rule above (real touches, long span, never violated between
# them) and was still useless: price cannot reach it, so it can neither hold nor
# break. Same class of thing produced a "resistance" line five ATR BELOW price
# and flagged it as freshly broken, when the break happened months ago.
#
# So a line has to still be in play. Four ATR is roughly a fortnight of ordinary
# movement — near enough that the next few weeks could test it.
MAX_DISTANCE_ATR = 4.0


def _f(v: Any, digits: int = 2) -> Optional[float]:
    try:
        out = float(v)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(out) else round(out, digits)


def _fit(p1: Dict[str, Any], p2: Dict[str, Any]) -> Optional[Dict[str, float]]:
    """Slope and intercept through two pivots, in (bar index, price) space."""
    dx = p2["index"] - p1["index"]
    if dx <= 0:
        return None
    slope = (p2["price"] - p1["price"]) / dx
    return {"slope": slope, "intercept": p1["price"] - slope * p1["index"]}


def _at(line: Dict[str, float], index: float) -> float:
    return line["intercept"] + line["slope"] * index


def _evaluate(line: Dict[str, float], pivots: List[Dict[str, Any]],
              closes: np.ndarray, atr: np.ndarray, kind: str,
              n: int) -> Optional[Dict[str, Any]]:
    """Score one candidate line, or reject it."""
    tol = TOUCH_TOL_ATR
    touches = []
    for p in pivots:
        a = atr[p["index"]]
        if not np.isfinite(a) or a <= 0:
            continue
        if abs(p["price"] - _at(line, p["index"])) <= tol * a:
            touches.append(p)
    if len(touches) < MIN_TOUCHES:
        return None

    first, last = touches[0]["index"], touches[-1]["index"]
    if (last - first) < MIN_SPAN_FRAC * n:
        return None

    # Was the line respected between its first and last touch? A support line
    # price closed well below halfway along was never support — it is a line
    # through three points that happens to fit.
    for i in range(first, last + 1):
        a = atr[i]
        if not np.isfinite(a) or a <= 0:
            continue
        gap = closes[i] - _at(line, i)
        if kind == "support" and gap < -VIOLATION_ATR * a:
            return None
        if kind == "resistance" and gap > VIOLATION_ATR * a:
            return None

    # Where the line sits now, and whether the last close is through it.
    end_atr = atr[n - 1]
    now = _at(line, n - 1)
    gap_now = closes[n - 1] - now
    broken = False
    if np.isfinite(end_atr) and end_atr > 0:
        if kind == "support":
            broken = gap_now < -BREAK_ATR * end_atr
        else:
            broken = gap_now > BREAK_ATR * end_atr

    # More touches and a longer span are both evidence. Multiplied rather than
    # added so a 3-touch line over the whole window does not outrank a 6-touch
    # one over half of it by span alone.
    span_frac = (last - first) / max(n - 1, 1)
    return {
        "kind": kind,
        "direction": "rising" if line["slope"] > 0 else "falling",
        "slope_per_bar": _f(line["slope"], 4),
        "touches": len(touches),
        "touch_indexes": [int(t["index"]) for t in touches],
        "touch_dates": [t["date"] for t in touches],
        "start_index": int(first),
        "end_index": int(n - 1),
        "start_price": _f(_at(line, first)),
        "price_now": _f(now),
        "span_bars": int(last - first),
        "broken": bool(broken),
        "distance_atr": _f(gap_now / end_atr, 2) if (
            np.isfinite(end_atr) and end_atr > 0) else None,
        "score": _f(len(touches) * span_frac * 100, 1),
    }


def _dedupe(lines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Drop near-duplicates.

    Fitting every pivot pair produces many lines that differ by a hair and share
    most of their touches. Keeping them all is how an auto-trendline tool ends up
    drawing a fan of eight lines nobody can read.
    """
    out: List[Dict[str, Any]] = []
    for cand in sorted(lines, key=lambda x: -(x["score"] or 0)):
        clash = False
        for kept in out:
            shared = set(cand["touch_indexes"]) & set(kept["touch_indexes"])
            if len(shared) >= 2:
                clash = True
                break
        if not clash:
            out.append(cand)
    return out


def build(df: pd.DataFrame, pivot_order: int = 3) -> Dict[str, Any]:
    """Support and resistance trend lines for one price frame."""
    if df is None or len(df) < 40:
        return {"available": False, "reason": "not enough bars", "lines": []}

    n = len(df)
    closes = df["Close"].to_numpy(dtype=float)
    atr = _atr_series(df).to_numpy(dtype=float)
    pivots = find_pivots(df, order=pivot_order)
    lows = [p for p in pivots if p["kind"] == "low"]
    highs = [p for p in pivots if p["kind"] == "high"]

    found: List[Dict[str, Any]] = []
    for kind, pool in (("support", lows), ("resistance", highs)):
        if len(pool) < MIN_TOUCHES:
            continue
        for p1, p2 in itertools.combinations(pool, 2):
            line = _fit(p1, p2)
            if not line:
                continue
            got = _evaluate(line, pool, closes, atr, kind, n)
            if got:
                found.append(got)

    kept = _dedupe(found)
    # Only lines price could still reach. See MAX_DISTANCE_ATR.
    reachable = [x for x in kept
                 if x["distance_atr"] is not None
                 and abs(x["distance_atr"]) <= MAX_DISTANCE_ATR]
    dropped_far = len(kept) - len(reachable)
    support = [x for x in reachable if x["kind"] == "support"][:MAX_LINES]
    resistance = [x for x in reachable if x["kind"] == "resistance"][:MAX_LINES]
    lines = support + resistance

    breaks = [x for x in lines if x["broken"]]
    return {
        "available": True,
        "lines": lines,
        "support_count": len(support),
        "resistance_count": len(resistance),
        "breaks": breaks,
        "candidates_considered": len(found),
        "dropped_out_of_reach": dropped_far,
        "params": {"min_touches": MIN_TOUCHES, "touch_tol_atr": TOUCH_TOL_ATR,
                   "violation_atr": VIOLATION_ATR, "min_span_frac": MIN_SPAN_FRAC,
                   "break_atr": BREAK_ATR, "max_distance_atr": MAX_DISTANCE_ATR,
                   "pivot_order": pivot_order},
    }
