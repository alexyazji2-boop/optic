"""Price-location structure: volume profile, floor pivots, moving-average stack,
candle patterns and Bollinger bandwidth rank.

These answer a different question from app/analytics/technicals.py. That module
asks *what is momentum doing*; this one asks *where is price, relative to places
that matter*. A breakout only means something against the volume shelf it broke
out of, and "extended" only means something against how wide the bands usually
get on this name.

Everything here is computed from OHLCV bars the app already fetches. Nothing is
proxied and nothing needs a paid feed — which is deliberate, because the point of
these levels is that two people looking at the same bars should get the same
numbers.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from .technicals import bollinger, ema


def _f(value: Any) -> Optional[float]:
    """numpy/pandas scalar -> JSON-safe float (NaN becomes None)."""
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(out) else round(out, 6)


# ------------------------------------------------------- live-bar refresh

def with_live_bar(df: pd.DataFrame, spot: Optional[float],
                  session_date: Optional[str] = None) -> pd.DataFrame:
    """Patch today's forming bar with the live price before computing levels.

    Daily history is cached for five minutes because 250 historical bars do not
    change. The *last* bar does: it is still forming, and every read here except
    the pivots depends on it. Without this the quote ticks every 30 seconds while
    "above value", the EMA stack and the candle read sit frozen for up to five
    minutes — the page contradicting itself.

    So the expensive part stays cached and only the final bar is refreshed from
    the quote, which costs nothing extra.

    The date guard matters. Before the open the last bar is *yesterday*, and
    stamping a pre-market print onto yesterday's close would rewrite a completed
    session — a silent corruption of history rather than a stale number. When the
    dates don't match, the frame is returned untouched.
    """
    if df is None or df.empty or spot is None:
        return df
    try:
        spot = float(spot)
    except (TypeError, ValueError):
        return df
    if not np.isfinite(spot) or spot <= 0:
        return df

    last = df.index[-1]
    if session_date is not None:
        last_date = getattr(last, "date", lambda: None)()
        if last_date is None or str(last_date) != str(session_date):
            return df

    out = df.copy()
    pos = out.index[-1]
    if "Close" in out:
        out.loc[pos, "Close"] = spot
    if "High" in out:
        out.loc[pos, "High"] = max(float(out.loc[pos, "High"]), spot)
    if "Low" in out:
        out.loc[pos, "Low"] = min(float(out.loc[pos, "Low"]), spot)
    return out


# ------------------------------------------------------------- volume profile

# How much of the traded volume defines the "value area". 70% is the convention
# from Market Profile — roughly one standard deviation of a normal distribution,
# which is where the original construction took it from.
VALUE_AREA_PCT = 0.70

# Price buckets across the range. 50 is enough resolution to separate a shelf
# from a gap on a normal equity range without turning single bars into spikes.
PROFILE_BINS = 50


def volume_profile(df: pd.DataFrame, lookback: int = 120,
                   bins: int = PROFILE_BINS) -> Dict[str, Any]:
    """Where volume actually traded, by price.

    Each bar's volume is spread evenly across the prices it touched (low to
    high) rather than dumped on its close. A bar that ranged $10 did not trade
    all of its volume at the closing print, and assigning it there invents
    shelves that aren't in the data.

    Returns the point of control (busiest price), the value area containing 70%
    of volume, and low-volume nodes — prices with little trade behind them,
    where moves tend to travel quickly because nobody is defending the level.
    """
    if df is None or df.empty:
        return {"available": False}
    need = {"High", "Low", "Close", "Volume"}
    if not need.issubset(df.columns):
        return {"available": False}

    window = df.tail(lookback).dropna(subset=["High", "Low", "Volume"])
    if len(window) < 10:
        return {"available": False}

    lo = float(window["Low"].min())
    hi = float(window["High"].max())
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        return {"available": False}

    edges = np.linspace(lo, hi, bins + 1)
    centres = (edges[:-1] + edges[1:]) / 2.0
    buckets = np.zeros(bins)

    for _, bar in window.iterrows():
        b_lo, b_hi = float(bar["Low"]), float(bar["High"])
        vol = float(bar["Volume"] or 0.0)
        if vol <= 0 or not np.isfinite(b_lo) or not np.isfinite(b_hi):
            continue
        if b_hi <= b_lo:
            # A bar with no range still traded; put it in its own bucket.
            idx = min(bins - 1, max(0, int((b_lo - lo) / (hi - lo) * bins)))
            buckets[idx] += vol
            continue
        # Overlap of [b_lo, b_hi] with each bucket, as a share of the bar range.
        overlap = np.clip(np.minimum(edges[1:], b_hi) - np.maximum(edges[:-1], b_lo), 0, None)
        total = overlap.sum()
        if total > 0:
            buckets += vol * (overlap / total)

    if buckets.sum() <= 0:
        return {"available": False}

    poc_idx = int(np.argmax(buckets))

    # Grow the value area outward from the point of control, always taking the
    # heavier neighbour, until 70% of volume is enclosed. This is the standard
    # construction and it matters that it grows from the POC rather than being a
    # percentile of price: value area is about where trade concentrated.
    target = buckets.sum() * VALUE_AREA_PCT
    low_i = high_i = poc_idx
    acc = buckets[poc_idx]
    while acc < target and (low_i > 0 or high_i < bins - 1):
        below = buckets[low_i - 1] if low_i > 0 else -1.0
        above = buckets[high_i + 1] if high_i < bins - 1 else -1.0
        if above >= below:
            high_i += 1
            acc += buckets[high_i]
        else:
            low_i -= 1
            acc += buckets[low_i]

    # Low-volume nodes: local minima that are genuinely thin, not just the tails
    # of the distribution. Threshold at 30% of the POC so a quiet-but-real shelf
    # doesn't get called an air pocket.
    thin = buckets.max() * 0.30
    lvns: List[Dict[str, Any]] = []
    for i in range(1, bins - 1):
        if buckets[i] < thin and buckets[i] <= buckets[i - 1] and buckets[i] <= buckets[i + 1]:
            lvns.append({"price": _f(centres[i]), "volume_share":
                         _f(buckets[i] / buckets.sum() * 100.0)})

    spot = _f(window["Close"].iloc[-1])
    vah, val = _f(centres[high_i]), _f(centres[low_i])
    location = None
    if spot is not None and vah is not None and val is not None:
        if spot > vah:
            location = "above value"
        elif spot < val:
            location = "below value"
        else:
            location = "inside value"

    return {
        "available": True,
        "poc": _f(centres[poc_idx]),
        "vah": vah,
        "val": val,
        "location": location,
        "lvns": sorted(lvns, key=lambda n: abs((n["price"] or 0) - (spot or 0)))[:4],
        "lookback_bars": int(len(window)),
        "range_low": _f(lo),
        "range_high": _f(hi),
        "method": (
            f"Volume spread across each bar's high-low range over {len(window)} bars, "
            f"in {bins} price buckets. Value area is the {int(VALUE_AREA_PCT * 100)}% of "
            "volume around the point of control."
        ),
    }


# --------------------------------------------------------------- floor pivots

def floor_pivots(df: pd.DataFrame) -> Dict[str, Any]:
    """Classic floor-trader pivots from the previous completed bar.

    Deliberately the previous bar, not the current one: a pivot computed from a
    session still in progress moves every tick, which defeats the point of a
    fixed level to trade against.
    """
    if df is None or len(df) < 2:
        return {"available": False}
    if not {"High", "Low", "Close"}.issubset(df.columns):
        return {"available": False}

    prev = df.iloc[-2]
    high, low, close = float(prev["High"]), float(prev["Low"]), float(prev["Close"])
    if not all(np.isfinite(v) for v in (high, low, close)) or high < low:
        return {"available": False}

    pp = (high + low + close) / 3.0
    rng = high - low
    spot = _f(df["Close"].iloc[-1])

    levels = {
        "pp": _f(pp),
        "r1": _f(2 * pp - low),
        "r2": _f(pp + rng),
        "r3": _f(high + 2 * (pp - low)),
        "s1": _f(2 * pp - high),
        "s2": _f(pp - rng),
        "s3": _f(low - 2 * (high - pp)),
    }
    above = None
    if spot is not None and levels["pp"] is not None:
        above = spot > levels["pp"]
    return {
        "available": True,
        **levels,
        "spot_above_pivot": above,
        "based_on": str(df.index[-2].date()) if hasattr(df.index[-2], "date") else None,
    }


# ----------------------------------------------------------- moving-average stack

# The fast/medium/slow trio the desk read is built on. Shorter than the 20/50/200
# set the swing tab uses, because this is about a multi-day swing rather than a
# multi-month trend.
STACK_SPANS = (9, 21, 50)


def ema_stack(close: pd.Series, spans=STACK_SPANS) -> Dict[str, Any]:
    """Is price above a fanned-out set of EMAs, and in order?

    "Full bullish stack" means price > fast > medium > slow — every timeframe
    agreeing. Partial means price is above them but they are not yet ordered,
    which is what a fresh reversal looks like before it earns the name.
    """
    if close is None or len(close) < max(spans) + 1:
        return {"available": False}

    values = {}
    for span in spans:
        series = ema(close, span).dropna()
        if series.empty:
            return {"available": False}
        values[f"ema{span}"] = _f(series.iloc[-1])
    spot = _f(close.iloc[-1])
    if spot is None or any(v is None for v in values.values()):
        return {"available": False}

    ordered = [values[f"ema{s}"] for s in spans]
    bullish = spot > ordered[0] and all(a > b for a, b in zip(ordered, ordered[1:]))
    bearish = spot < ordered[0] and all(a < b for a, b in zip(ordered, ordered[1:]))
    above_all = all(spot > v for v in ordered)
    below_all = all(spot < v for v in ordered)

    if bullish:
        read, note = "full bullish stack", (
            "Price is above every average and they are stacked fast-over-slow — "
            "each timeframe agrees on the direction.")
    elif bearish:
        read, note = "full bearish stack", (
            "Price is below every average and they are stacked slow-over-fast — "
            "every timeframe agrees on the downside.")
    elif above_all:
        read, note = "above, not stacked", (
            "Price is above all three averages but they are not yet in order — "
            "the move is young and the slower averages have not caught up.")
    elif below_all:
        read, note = "below, not stacked", (
            "Price is below all three averages but they are not yet in order.")
    else:
        read, note = "mixed", (
            "Price sits between its averages — no timeframe agreement either way.")

    return {"available": True, "read": read, "note": note, "spot": spot,
            "bullish_stack": bullish, "bearish_stack": bearish, **values}


# -------------------------------------------------------- bollinger bandwidth

def bandwidth_rank(close: pd.Series, length: int = 20, lookback: int = 252) -> Dict[str, Any]:
    """Where today's Bollinger width sits in its own trailing history.

    An absolute band width says nothing across names — 4% is wide for a utility
    and tight for a biotech. The percentile is the comparable number, and it is
    what "82nd percentile, extended" in a desk note actually means.
    """
    if close is None or len(close) < length + 20:
        return {"available": False}
    bands = bollinger(close, length)
    width = ((bands["upper"] - bands["lower"]) / bands["mid"] * 100.0).dropna()
    if len(width) < 20:
        return {"available": False}

    history = width.tail(lookback)
    current = float(history.iloc[-1])
    pct = float((history < current).sum()) / float(len(history)) * 100.0

    if pct >= 80:
        read = "expanded"
        note = ("Bands are wider than most of the past year — the move is already "
                "running, so entries here carry a worse stop.")
    elif pct <= 20:
        read = "squeezed"
        note = ("Bands are tighter than most of the past year — compressed ranges "
                "tend to resolve into a move, though they do not say which way.")
    else:
        read = "normal"
        note = "Band width is mid-range versus this stock's own past year."

    return {"available": True, "bandwidth_pct": _f(current),
            "percentile": _f(round(pct, 1)), "read": read, "note": note,
            "lookback_bars": int(len(history))}


# ------------------------------------------------------------ candle patterns

# Body must be at least this share of the bar's range to count as a marubozu —
# a "shaved" candle where one side barely wicked.
MARUBOZU_BODY = 0.90
DOJI_BODY = 0.10


def candle_patterns(df: pd.DataFrame, bars: int = 3) -> Dict[str, Any]:
    """Name the last few candles, where they have a name worth using.

    Kept to the four that describe who won the bar rather than the dozens that
    are curve-fits of each other: marubozu (one side never gave ground),
    engulfing (today reversed and swallowed yesterday), doji (nobody won), and
    hammer (rejected a low). Each is a description of the bar, not a forecast,
    and the returned note says so.
    """
    if df is None or len(df) < 2:
        return {"available": False}
    if not {"Open", "High", "Low", "Close"}.issubset(df.columns):
        return {"available": False}

    found: List[Dict[str, Any]] = []
    window = df.tail(bars + 1)
    rows = list(window.itertuples())

    for i in range(1, len(rows)):
        cur, prev = rows[i], rows[i - 1]
        o, h, l, c = float(cur.Open), float(cur.High), float(cur.Low), float(cur.Close)
        if not all(np.isfinite(v) for v in (o, h, l, c)):
            continue
        rng = h - l
        if rng <= 0:
            continue
        body = abs(c - o)
        body_share = body / rng
        bullish = c > o
        date = str(cur.Index.date()) if hasattr(cur.Index, "date") else None

        if body_share >= MARUBOZU_BODY:
            found.append({
                "pattern": "marubozu", "direction": "bullish" if bullish else "bearish",
                "date": date,
                "detail": ("Opened at one extreme and closed at the other with almost no wick — "
                           f"{'buyers' if bullish else 'sellers'} held the bar from open to close."),
            })
        elif body_share <= DOJI_BODY:
            found.append({
                "pattern": "doji", "direction": "neutral", "date": date,
                "detail": "Opened and closed at nearly the same price — the bar settled nothing.",
            })
        else:
            lower_wick = min(o, c) - l
            if lower_wick >= body * 2 and bullish:
                found.append({
                    "pattern": "hammer", "direction": "bullish", "date": date,
                    "detail": ("Traded well below the open and closed back up — the low was "
                               "rejected within the bar."),
                })

        # Engulfing needs yesterday's body inside today's.
        po, pc = float(prev.Open), float(prev.Close)
        if np.isfinite(po) and np.isfinite(pc):
            prev_bull = pc > po
            if bullish != prev_bull and min(o, c) <= min(po, pc) and max(o, c) >= max(po, pc):
                found.append({
                    "pattern": "engulfing", "direction": "bullish" if bullish else "bearish",
                    "date": date,
                    "detail": (f"Today's body covers yesterday's entirely in the opposite "
                               f"direction — {'buyers' if bullish else 'sellers'} took back the "
                               "whole of the previous bar."),
                })

    return {
        "available": True,
        "patterns": found[-4:],
        "note": ("Candle names describe what happened in the bar. They are not predictions, "
                 "and on their own they have no edge — they matter only where they line up "
                 "with a level."),
    }
