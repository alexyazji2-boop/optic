"""Chart and candlestick pattern detection.

Pattern reading is the most subjective corner of technical analysis, and the
usual software treatment makes that worse: a label appears, a textbook direction
is asserted, and nothing tells the reader how often that direction was right.
Two rules govern this module.

**Every threshold is explicit and relative.** A "long" wick, a "tight" base, two
lows "at the same price" — each needs a number, and a number in percent breaks
across names. A 1% tolerance merges two genuinely different lows on a quiet
utility and splits one double bottom into two on a high-beta semiconductor. So
tolerances are in ATR units throughout, and each is named as a constant with the
reasoning next to it.

**Unconfirmed is not the same as absent.** A double bottom is not a double bottom
until price closes back above the peak between the two lows. Before that it is
two lows and a hope. Most tools draw the shape as soon as the geometry fits,
which is exactly when it is least reliable, so `confirmed` is carried on every
structural pattern and the panel is expected to show it.

What this module does NOT do is tell you a pattern is bullish. Direction here is
the *conventional* reading, labelled as such, and `app/analytics/pattern_stats.py`
measures what actually followed on real data so the two can be shown together.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .technicals import atr

log = logging.getLogger(__name__)

# ------------------------------------------------------------------ tolerances

# Two swing lows count as "the same level" within this fraction of ATR. 0.6 ATR
# is wide enough to survive a one-day overshoot on the retest — which is the
# normal shape of a real double bottom, not a defect — and tight enough that a
# drifting decline does not read as one.
LEVEL_TOL_ATR = 0.6

# A pivot needs this many bars either side that do not exceed it. 3 keeps
# meaningful minor structure; 2 turns ordinary noise into a pivot and buries the
# real ones in a crowd.
PIVOT_ORDER = 3

# Minimum bars between the two lows of a double bottom. Adjacent pivots are one
# event seen twice, not a retest.
MIN_PATTERN_SPAN = 8
MAX_PATTERN_SPAN = 120

# The pattern's height — neckline to the two extremes — as a multiple of ATR.
#
# Without this the detector was worthless on anything that ranges. SPY produced
# a double bottom, then a double top, then a double bottom, then two more tops
# across eight weeks: every consecutive pivot pair sat within tolerance of each
# other, so ordinary oscillation came back labelled as five reversal patterns.
# 1.5 ATR is the floor at which the shape describes a move rather than chop.
MIN_AMPLITUDE_ATR = 1.5

# A reversal needs something to reverse. Price must have travelled at least this
# far, in ATR, into the pattern's first pivot over the preceding PRIOR_MOVE_BARS.
PRIOR_MOVE_ATR = 2.0
PRIOR_MOVE_BARS = 30

# How many times the neckline may already have been crossed before the pattern
# began, and over what window.
#
# The amplitude and prior-move gates above are not sufficient on their own, and a
# test caught it: a clean oscillation between 94 and 106 satisfies both — each
# trough is a real distance below a real prior peak — and returned five reversal
# patterns across seventy bars. Geometrically they are all there. What separates
# them from a reversal is that the neckline is not a level being tested for the
# first time; in a range price has been through it repeatedly.
#
# The level to count crossings of is the pattern's MIDLINE — halfway between its
# extreme and its neckline — not the neckline itself. That was the first attempt
# and it measured nothing: for a double bottom the neckline is the intervening
# peak's high, which in an oscillation sits above every close in the series, so
# the count came back zero for all five false positives. The midline is the level
# a range genuinely cycles through.
MAX_MIDLINE_CROSSINGS = 3
CROSSING_WINDOW_BARS = 90

# Zones are filtered by reachability over a stated horizon rather than by a bare
# ATR multiple, because the question "is this level relevant" only has an answer
# once you say over what period.
#
# 40 sessions is eight weeks, the top of the swing horizon this terminal works
# on. Expected travel over N bars scales with sqrt(N), so the limit is
# ATR x sqrt(40), about 6.3 ATR. Unfiltered, a stock that has tripled returns its
# old accumulation bases at -46%, -56% and -63%: real history, and not a level
# anyone is trading against this quarter. Zones outside the horizon are counted
# and reported rather than silently dropped — on a name that has run a long way
# the fact that all its demand is far below is itself the finding.
ZONE_HORIZON_BARS = 40

# A candle body smaller than this share of its own high-low range is a doji:
# the session opened and closed in the same place having travelled.
DOJI_BODY_MAX = 0.12

# A wick this many times the body makes a hammer or shooting star. 2.0 is the
# common convention and it is a convention, not a finding.
WICK_BODY_MULT = 2.0

# The opposite wick may not exceed this share of the range, or the bar is just a
# wide-range candle rather than a rejection from one direction.
WICK_OPPOSITE_MAX = 0.25

# A supply or demand zone needs a base whose range is at most this in ATR terms,
# then a departure of at least DEPARTURE_ATR. A zone is defined by the imbalance
# that left it, so both halves are required — a tight range that drifts out
# sideways is congestion, not a zone.
BASE_MAX_ATR = 1.6
BASE_MIN_BARS = 2
BASE_MAX_BARS = 8
DEPARTURE_ATR = 2.2
DEPARTURE_BARS = 4

# How long a pattern has to clear its neckline before the break stops counting as
# confirmation of that pattern.
#
# Without a window, `_neckline_confirmed` searched forward forever: NVDA's double
# bottom of October 2025 came back marked "confirmed 2026-04-27", six months
# later. Price did cross the level, for reasons that had nothing to do with a
# pattern two quarters old. The window scales with the pattern's own span — a
# structure that took sixty bars to build can reasonably take longer to resolve
# than one that took ten — and is clamped so neither end runs away.
CONFIRM_WINDOW_MIN = 10
CONFIRM_WINDOW_MAX = 40

# Zones are forgotten once price has closed decisively through them.
ZONE_BREAK_ATR = 0.5


def _atr_value(df: pd.DataFrame) -> Optional[float]:
    series = atr(df, 14).dropna()
    if series.empty:
        return None
    val = float(series.iloc[-1])
    return val if val > 0 and np.isfinite(val) else None


def _atr_series(df: pd.DataFrame) -> pd.Series:
    """Bar-by-bar ATR, forward-filled at the head.

    A pattern from eighteen months ago has to be judged against the volatility of
    its own time, not today's. Using one trailing ATR for the whole history
    labelled everything before a volatility expansion as tight.
    """
    series = atr(df, 14)
    return series.bfill().ffill()


# ------------------------------------------------------------------ pivots

def find_pivots(df: pd.DataFrame, order: int = PIVOT_ORDER) -> List[Dict[str, Any]]:
    """Fractal highs and lows: a bar not exceeded within `order` bars either side.

    Strict inequality on one side and non-strict on the other, so a flat double
    top over two adjacent bars yields one pivot rather than none — the symmetric
    strict version silently drops every equal-high pair, which is precisely the
    shape being looked for.
    """
    if df is None or len(df) < order * 2 + 1:
        return []
    highs = df["High"].to_numpy(dtype=float)
    lows = df["Low"].to_numpy(dtype=float)
    dates = [str(i.date()) for i in df.index]
    out: List[Dict[str, Any]] = []
    for i in range(order, len(df) - order):
        left_h, right_h = highs[i - order:i], highs[i + 1:i + order + 1]
        left_l, right_l = lows[i - order:i], lows[i + 1:i + order + 1]
        if highs[i] > left_h.max() and highs[i] >= right_h.max():
            out.append({"kind": "high", "index": i, "price": float(highs[i]),
                        "date": dates[i]})
        if lows[i] < left_l.min() and lows[i] <= right_l.min():
            out.append({"kind": "low", "index": i, "price": float(lows[i]),
                        "date": dates[i]})
    out.sort(key=lambda p: p["index"])
    return out


# ------------------------------------------------------------ candle patterns

def _candle_geometry(o: float, h: float, l: float, c: float) -> Dict[str, float]:
    rng = h - l
    body = abs(c - o)
    return {
        "range": rng,
        "body": body,
        "body_share": body / rng if rng > 0 else 0.0,
        "upper": h - max(o, c),
        "lower": min(o, c) - l,
        "up": 1.0 if c > o else 0.0,
    }


def candle_patterns(df: pd.DataFrame, lookback: int = 10) -> List[Dict[str, Any]]:
    """Named candlestick formations in the last `lookback` bars.

    Only patterns with a mechanical definition are here. "Rising three methods"
    and its relatives need a judgement about whether the intervening bars are
    "small enough relative to the trend", and encoding that judgement as a
    constant would present taste as a measurement.

    Each result carries `conventional`, the textbook reading, explicitly named so
    it is not mistaken for a result this terminal measured.
    """
    if df is None or len(df) < 5:
        return []
    tail = df.tail(max(lookback + 3, 8))
    o = tail["Open"].to_numpy(dtype=float)
    h = tail["High"].to_numpy(dtype=float)
    lo = tail["Low"].to_numpy(dtype=float)
    c = tail["Close"].to_numpy(dtype=float)
    dates = [str(i.date()) for i in tail.index]
    atr_s = _atr_series(tail).to_numpy(dtype=float)
    n = len(tail)
    out: List[Dict[str, Any]] = []

    def add(i: int, name: str, direction: str, conventional: str, note: str) -> None:
        out.append({
            "name": name, "date": dates[i], "index": int(i),
            "bar_offset": int(n - 1 - i),          # 0 = the most recent bar
            "direction": direction,
            "conventional": conventional,
            "note": note,
            "price": float(c[i]),
        })

    start = max(2, n - lookback)
    for i in range(start, n):
        g = _candle_geometry(o[i], h[i], lo[i], c[i])
        p = _candle_geometry(o[i - 1], h[i - 1], lo[i - 1], c[i - 1])
        a = float(atr_s[i]) if np.isfinite(atr_s[i]) and atr_s[i] > 0 else None
        if g["range"] <= 0:
            continue

        # --- single bar -----------------------------------------------------
        if g["body_share"] <= DOJI_BODY_MAX:
            if g["lower"] > g["range"] * 0.6:
                add(i, "Dragonfly doji", "bullish", "rejection of lower prices",
                    "Opened and closed near the high after trading well below it.")
            elif g["upper"] > g["range"] * 0.6:
                add(i, "Gravestone doji", "bearish", "rejection of higher prices",
                    "Opened and closed near the low after trading well above it.")
            else:
                add(i, "Doji", "indecisive", "no conviction either way",
                    "Open and close in the same place after a full session's range.")
        elif (g["lower"] >= g["body"] * WICK_BODY_MULT
              and g["upper"] <= g["range"] * WICK_OPPOSITE_MAX):
            add(i, "Hammer" if c[i] >= o[i] else "Hanging man",
                "bullish" if c[i] >= o[i] else "bearish",
                "buyers reclaimed the session" if c[i] >= o[i]
                else "sellers appeared at the highs",
                "Long lower wick, small body, little upper wick.")
        elif (g["upper"] >= g["body"] * WICK_BODY_MULT
              and g["lower"] <= g["range"] * WICK_OPPOSITE_MAX):
            add(i, "Shooting star" if c[i] <= o[i] else "Inverted hammer",
                "bearish" if c[i] <= o[i] else "bullish",
                "sellers defended the highs" if c[i] <= o[i]
                else "buyers probed higher and were pushed back",
                "Long upper wick, small body, little lower wick.")
        elif a and g["body"] > a * 1.4 and g["body_share"] > 0.8:
            add(i, "Marubozu", "bullish" if c[i] > o[i] else "bearish",
                "one side controlled the whole session",
                "A body larger than a typical day's full range, with almost no wick.")

        # --- two bar --------------------------------------------------------
        engulfs = c[i] > o[i - 1] and o[i] < c[i - 1]
        engulfed_down = c[i] < o[i - 1] and o[i] > c[i - 1]
        if p["body"] > 0 and g["body"] > p["body"]:
            if c[i] > o[i] and c[i - 1] < o[i - 1] and engulfs:
                add(i, "Bullish engulfing", "bullish", "reversal of the prior session",
                    "An up bar whose body completely covers the previous down bar.")
            elif c[i] < o[i] and c[i - 1] > o[i - 1] and engulfed_down:
                add(i, "Bearish engulfing", "bearish", "reversal of the prior session",
                    "A down bar whose body completely covers the previous up bar.")
        if h[i] <= h[i - 1] and lo[i] >= lo[i - 1] and p["range"] > 0:
            add(i, "Inside bar", "indecisive", "compression, direction unresolved",
                "The whole session fits inside the previous bar's range.")
        elif h[i] > h[i - 1] and lo[i] < lo[i - 1]:
            add(i, "Outside bar", "bullish" if c[i] > o[i] else "bearish",
                "both sides tested, one closed it out",
                "Took out both the previous bar's high and its low.")
        # Tweezers: two sessions rejected from the same price.
        if a and abs(lo[i] - lo[i - 1]) < a * 0.15 and c[i] > o[i] and c[i - 1] < o[i - 1]:
            add(i, "Tweezer bottom", "bullish", "the same low held twice",
                "Two consecutive sessions turned from the same price.")
        if a and abs(h[i] - h[i - 1]) < a * 0.15 and c[i] < o[i] and c[i - 1] > o[i - 1]:
            add(i, "Tweezer top", "bearish", "the same high capped twice",
                "Two consecutive sessions failed at the same price.")

        # --- three bar ------------------------------------------------------
        if i >= 2:
            q = _candle_geometry(o[i - 2], h[i - 2], lo[i - 2], c[i - 2])
            small_middle = p["body"] < q["body"] * 0.5 and p["body"] < g["body"] * 0.5
            if (small_middle and c[i - 2] < o[i - 2] and c[i] > o[i]
                    and c[i] > (o[i - 2] + c[i - 2]) / 2):
                add(i, "Morning star", "bullish", "a three-session bottom",
                    "Down bar, a pause, then an up bar closing back into the first.")
            if (small_middle and c[i - 2] > o[i - 2] and c[i] < o[i]
                    and c[i] < (o[i - 2] + c[i - 2]) / 2):
                add(i, "Evening star", "bearish", "a three-session top",
                    "Up bar, a pause, then a down bar closing back into the first.")
            three_up = all(c[j] > o[j] for j in (i - 2, i - 1, i)) and c[i] > c[i - 1] > c[i - 2]
            three_dn = all(c[j] < o[j] for j in (i - 2, i - 1, i)) and c[i] < c[i - 1] < c[i - 2]
            if three_up:
                add(i, "Three white soldiers", "bullish", "sustained accumulation",
                    "Three up closes in a row, each higher than the last.")
            if three_dn:
                add(i, "Three black crows", "bearish", "sustained distribution",
                    "Three down closes in a row, each lower than the last.")

    # Most recent first, and one entry per (name, date).
    seen = set()
    unique = []
    for row in sorted(out, key=lambda r: -r["index"]):
        key = (row["name"], row["date"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


# ----------------------------------------------------------- chart patterns

def _had_prior_move(df: pd.DataFrame, index: int, atr_val: float,
                    direction: str) -> bool:
    """Did price actually travel into this pivot?

    `direction` is the pattern's expected resolution: an "up" pattern (double
    bottom, inverse head and shoulders) requires a preceding decline. Measured
    from the highest high before a bottom, and the lowest low before a top, over
    PRIOR_MOVE_BARS — the extreme rather than the close, because the size of the
    move that has to be reversed is what matters.
    """
    start = max(0, index - PRIOR_MOVE_BARS)
    if index - start < 5:
        return False
    before = df.iloc[start:index]
    if before.empty:
        return False
    pivot_price = float(df["Low"].iloc[index] if direction == "up"
                        else df["High"].iloc[index])
    if direction == "up":
        return (float(before["High"].max()) - pivot_price) >= atr_val * PRIOR_MOVE_ATR
    return (pivot_price - float(before["Low"].min())) >= atr_val * PRIOR_MOVE_ATR


def _is_fresh_structure(df: pd.DataFrame, extreme: float, neckline: float,
                       start: int) -> bool:
    """Was this price band already being cycled through before the pattern formed?

    Counts sign changes of (close - midline) over CROSSING_WINDOW_BARS before the
    pattern's first pivot, where midline is halfway between the pattern's extreme
    and its neckline. This is what tells a reversal apart from an oscillation:
    both have the amplitude and both have a prior move, but only one is happening
    in a band price has not been traversing all along.
    """
    level = (extreme + neckline) / 2.0
    lo = max(0, start - CROSSING_WINDOW_BARS)
    if start - lo < 10:
        return True                     # not enough history to judge; do not reject
    closes = df["Close"].to_numpy(dtype=float)[lo:start]
    side = np.sign(closes - level)
    side = side[side != 0]
    if len(side) < 2:
        return True
    crossings = int((side[1:] != side[:-1]).sum())
    return crossings <= MAX_MIDLINE_CROSSINGS


def _drop_overlaps(found: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One pattern per stretch of chart.

    Overlapping detections are the same price action read several ways, not
    several findings. Ranked by amplitude in ATR — the biggest structure over a
    span is the one a reader would have drawn — then anything sharing bars with
    an already-kept pattern is dropped. Confirmed beats unconfirmed at equal
    size, because a completed pattern is a fact and an open one is a maybe.
    """
    ranked = sorted(
        found,
        key=lambda p: (-(p.get("amplitude_atr") or 0), 0 if p.get("confirmed") else 1),
    )
    kept: List[Dict[str, Any]] = []
    for p in ranked:
        lo = min(pt["index"] for pt in p["points"])
        hi = max(pt["index"] for pt in p["points"])
        clash = False
        for k in kept:
            klo = min(pt["index"] for pt in k["points"])
            khi = max(pt["index"] for pt in k["points"])
            if not (hi < klo or lo > khi):
                clash = True
                break
        if not clash:
            kept.append(p)
    kept.sort(key=lambda p: p["end_date"])
    return kept


def _neckline_confirmed(df: pd.DataFrame, level: float, after: int,
                        direction: str, span: int = 0) -> Tuple[bool, Optional[str]]:
    """Has a close cleared the neckline within the confirmation window?

    On closes, not intraday extremes. A wick through a neckline that closes back
    inside is the failure of the pattern, not its confirmation, and using highs
    would score those as breakouts.

    Bounded in time, which the first version was not: an unbounded forward search
    reported a pattern as confirmed by a crossing six months later, which is a
    coincidence rather than a resolution.
    """
    if after >= len(df):
        return False, None
    limit = int(min(CONFIRM_WINDOW_MAX, max(CONFIRM_WINDOW_MIN, span)))
    window = df.iloc[after:after + limit]
    closes = window["Close"].to_numpy(dtype=float)
    hit = closes > level if direction == "up" else closes < level
    if not hit.any():
        return False, None
    idx = int(np.argmax(hit))
    return True, str(window.index[idx].date())


def _double(df: pd.DataFrame, pivots: List[Dict[str, Any]], atr_bars: np.ndarray,
            kind: str) -> List[Dict[str, Any]]:
    """Double bottoms (kind='low') or double tops (kind='high')."""
    want = [p for p in pivots if p["kind"] == kind]
    opposite = [p for p in pivots if p["kind"] != kind]
    out = []
    for a, b in zip(want, want[1:]):
        span = b["index"] - a["index"]
        if not (MIN_PATTERN_SPAN <= span <= MAX_PATTERN_SPAN):
            continue
        # Volatility as of the second pivot — the bar at which the shape is first
        # visible. Using the first pivot's would judge the retest by conditions
        # that predate it.
        atr_val = float(atr_bars[b["index"]])
        if not np.isfinite(atr_val) or atr_val <= 0:
            continue
        tol = atr_val * LEVEL_TOL_ATR
        if abs(a["price"] - b["price"]) > tol:
            continue
        between = [p for p in opposite if a["index"] < p["index"] < b["index"]]
        if not between:
            continue
        if kind == "low":
            neck = max(between, key=lambda p: p["price"])
            # The peak between the lows has to be a real move off them, or this
            # is a flat shelf being read as a reversal pattern.
            if neck["price"] - max(a["price"], b["price"]) < tol:
                continue
            direction, name = "up", "Double bottom"
            conventional = "reversal higher once the middle peak gives way"
            amplitude = neck["price"] - min(a["price"], b["price"])
        else:
            neck = min(between, key=lambda p: p["price"])
            if min(a["price"], b["price"]) - neck["price"] < tol:
                continue
            direction, name = "down", "Double top"
            conventional = "reversal lower once the middle trough gives way"
            amplitude = max(a["price"], b["price"]) - neck["price"]
        amp_atr = amplitude / atr_val if atr_val else 0.0
        if amp_atr < MIN_AMPLITUDE_ATR:
            continue
        if not _had_prior_move(df, a["index"], atr_val, direction):
            continue
        if not _is_fresh_structure(df, min(a["price"], b["price"]) if kind == "low"
                                   else max(a["price"], b["price"]),
                                   neck["price"], a["index"]):
            continue
        confirmed, on = _neckline_confirmed(df, neck["price"], b["index"] + 1,
                                            direction, span=span)
        out.append({
            "amplitude_atr": round(amp_atr, 2),
            "name": name, "direction": direction, "conventional": conventional,
            "points": [
                {"role": "first", "date": a["date"], "price": a["price"], "index": a["index"]},
                {"role": "neckline", "date": neck["date"], "price": neck["price"],
                 "index": neck["index"]},
                {"role": "second", "date": b["date"], "price": b["price"], "index": b["index"]},
            ],
            "neckline": neck["price"],
            "confirmed": confirmed,
            "confirmed_on": on,
            "start_date": a["date"], "end_date": b["date"],
            "span_bars": int(span),
        })
    return out


def _head_shoulders(df: pd.DataFrame, pivots: List[Dict[str, Any]],
                    atr_bars: np.ndarray, inverse: bool) -> List[Dict[str, Any]]:
    """Head and shoulders, or the inverse.

    Three same-side pivots where the middle one is the extreme and the outer two
    are within tolerance of each other. The shoulders being level is what
    separates this from an ordinary three-push trend leg, so that test is on the
    shoulders rather than on the head.
    """
    kind = "low" if inverse else "high"
    want = [p for p in pivots if p["kind"] == kind]
    opposite = [p for p in pivots if p["kind"] != kind]
    out = []
    for i in range(len(want) - 2):
        left, head, right = want[i], want[i + 1], want[i + 2]
        if right["index"] - left["index"] > MAX_PATTERN_SPAN * 1.5:
            continue
        atr_val = float(atr_bars[right["index"]])
        if not np.isfinite(atr_val) or atr_val <= 0:
            continue
        tol = atr_val * LEVEL_TOL_ATR
        if head["index"] - left["index"] < 4 or right["index"] - head["index"] < 4:
            continue
        if inverse:
            if not (head["price"] < left["price"] - tol
                    and head["price"] < right["price"] - tol):
                continue
        elif not (head["price"] > left["price"] + tol
                  and head["price"] > right["price"] + tol):
            continue
        if abs(left["price"] - right["price"]) > tol * 1.5:
            continue
        troughs = [p for p in opposite if left["index"] < p["index"] < right["index"]]
        if len(troughs) < 2:
            continue
        neck = (max(t["price"] for t in troughs) if inverse
                else min(t["price"] for t in troughs))
        direction = "up" if inverse else "down"
        amplitude = abs(neck - head["price"])
        amp_atr = amplitude / atr_val if atr_val else 0.0
        if amp_atr < MIN_AMPLITUDE_ATR:
            continue
        if not _had_prior_move(df, left["index"], atr_val, direction):
            continue
        if not _is_fresh_structure(df, head["price"], neck, left["index"]):
            continue
        confirmed, on = _neckline_confirmed(
            df, neck, right["index"] + 1, direction,
            span=right["index"] - left["index"])
        out.append({
            "amplitude_atr": round(amp_atr, 2),
            "name": "Inverse head and shoulders" if inverse else "Head and shoulders",
            "direction": direction,
            "conventional": ("reversal higher on a neckline break" if inverse
                             else "reversal lower on a neckline break"),
            "points": [
                {"role": "left shoulder", "date": left["date"], "price": left["price"],
                 "index": left["index"]},
                {"role": "head", "date": head["date"], "price": head["price"],
                 "index": head["index"]},
                {"role": "right shoulder", "date": right["date"], "price": right["price"],
                 "index": right["index"]},
            ],
            "neckline": float(neck),
            "confirmed": confirmed,
            "confirmed_on": on,
            "start_date": left["date"], "end_date": right["date"],
            "span_bars": int(right["index"] - left["index"]),
        })
    return out


def _triangles(df: pd.DataFrame, pivots: List[Dict[str, Any]],
               tol: float, atr_val: float) -> List[Dict[str, Any]]:
    """Ascending, descending and symmetrical triangles from the last four pivots.

    Named from the two boundaries independently — rising lows against a flat top
    is ascending, and calling everything with converging boundaries "symmetrical"
    loses the only part a reader acts on.
    """
    highs = [p for p in pivots if p["kind"] == "high"][-3:]
    lows = [p for p in pivots if p["kind"] == "low"][-3:]
    if len(highs) < 2 or len(lows) < 2:
        return []
    h1, h2 = highs[-2], highs[-1]
    l1, l2 = lows[-2], lows[-1]
    dh, dl = h2["price"] - h1["price"], l2["price"] - l1["price"]
    flat_h, flat_l = abs(dh) <= tol, abs(dl) <= tol
    name = direction = conventional = None
    if flat_h and dl > tol:
        name, direction = "Ascending triangle", "up"
        conventional = "buyers stepping up into a fixed ceiling"
    elif flat_l and dh < -tol:
        name, direction = "Descending triangle", "down"
        conventional = "sellers stepping down onto a fixed floor"
    elif dh < -tol and dl > tol:
        name, direction = "Symmetrical triangle", "indecisive"
        conventional = "compression; the break decides direction"
    if not name:
        return []
    span = max(h2["index"], l2["index"]) - min(h1["index"], l1["index"])
    if span < MIN_PATTERN_SPAN:
        return []
    amp_atr = (h2["price"] - l2["price"]) / atr_val if atr_val else 0.0
    if amp_atr < MIN_AMPLITUDE_ATR:
        return []
    return [{
        "name": name, "direction": direction, "conventional": conventional,
        "amplitude_atr": round(amp_atr, 2),
        "points": [
            {"role": "high", "date": h1["date"], "price": h1["price"], "index": h1["index"]},
            {"role": "high", "date": h2["date"], "price": h2["price"], "index": h2["index"]},
            {"role": "low", "date": l1["date"], "price": l1["price"], "index": l1["index"]},
            {"role": "low", "date": l2["date"], "price": l2["price"], "index": l2["index"]},
        ],
        "resistance": h2["price"], "support": l2["price"],
        # A triangle is a state, not an event: there is no neckline to break, so
        # there is nothing to confirm until it resolves.
        "confirmed": None,
        "confirmed_on": None,
        "start_date": min(h1["date"], l1["date"]),
        "end_date": max(h2["date"], l2["date"]),
        "span_bars": int(span),
    }]


def chart_patterns(df: pd.DataFrame, lookback: int = 252) -> List[Dict[str, Any]]:
    """Structural patterns over the recent window, newest last."""
    if df is None or len(df) < 40:
        return []
    window = df.tail(lookback)
    if _atr_value(window) is None:
        return []
    # Bar-by-bar, so each pattern is judged against the volatility of its own
    # time. A single trailing ATR is a look-ahead in any backtest and it read
    # every pre-expansion range as tight.
    atr_bars = _atr_series(window).to_numpy(dtype=float)
    pivots = find_pivots(window)
    if len(pivots) < 3:
        return []
    a = float(atr_bars[-1])
    found: List[Dict[str, Any]] = []
    found += _double(window, pivots, atr_bars, "low")
    found += _double(window, pivots, atr_bars, "high")
    found += _head_shoulders(window, pivots, atr_bars, inverse=False)
    found += _head_shoulders(window, pivots, atr_bars, inverse=True)
    triangles = _triangles(window, pivots, a * LEVEL_TOL_ATR, a)
    # A triangle is the current state, so it is exempt from overlap suppression:
    # it necessarily shares bars with whatever formed inside it.
    return _drop_overlaps(found) + triangles


# ------------------------------------------------------- supply / demand zones

def supply_demand_zones(df: pd.DataFrame, spot: float, lookback: int = 252,
                        max_zones: int = 6) -> Tuple[List[Dict[str, Any]], int]:
    """Zones left behind by an imbalance, not merely places price turned.

    The distinction matters and most tools collapse it. Support is a price that
    held. A demand zone is a price where orders were so one-sided that price
    could not stay — a tight base, then a move away too fast to be two-sided.
    That is why both halves are required here: a quiet range that drifts out
    sideways produced no imbalance and leaves nothing behind.

    The zone is the base's own high-low, kept as a band rather than collapsed to
    a line, because the unfilled orders sit across the range that formed it.
    """
    if df is None or len(df) < 60 or not spot:
        return [], 0
    window = df.tail(lookback).reset_index()
    date_col = window.columns[0]
    highs = window["High"].to_numpy(dtype=float)
    lows = window["Low"].to_numpy(dtype=float)
    closes = window["Close"].to_numpy(dtype=float)
    atr_s = _atr_series(window.set_index(date_col)).to_numpy(dtype=float)
    n = len(window)
    zones: List[Dict[str, Any]] = []

    for start in range(0, n - BASE_MAX_BARS - DEPARTURE_BARS):
        a = float(atr_s[start])
        if not np.isfinite(a) or a <= 0:
            continue
        for length in range(BASE_MIN_BARS, BASE_MAX_BARS + 1):
            end = start + length
            if end + DEPARTURE_BARS >= n:
                break
            top = float(highs[start:end].max())
            bottom = float(lows[start:end].min())
            if top - bottom > a * BASE_MAX_ATR:
                break               # widening further only makes it wider
            after = closes[end:end + DEPARTURE_BARS]
            up_move = (after.max() - top) / a
            down_move = (bottom - after.min()) / a
            if up_move >= DEPARTURE_ATR and up_move >= down_move:
                side, ref = "demand", bottom
            elif down_move >= DEPARTURE_ATR:
                side, ref = "supply", top
            else:
                continue
            # Has price since closed decisively back through it?
            later = closes[end + DEPARTURE_BARS:]
            broken = bool(
                (later < bottom - a * ZONE_BREAK_ATR).any() if side == "demand"
                else (later > top + a * ZONE_BREAK_ATR).any()
            ) if len(later) else False
            zones.append({
                "side": side,
                "top": round(top, 4),
                "bottom": round(bottom, 4),
                "formed": str(pd.Timestamp(window[date_col].iloc[start]).date()),
                "left_on": str(pd.Timestamp(window[date_col].iloc[end]).date()),
                "base_bars": int(length),
                "departure_atr": round(float(max(up_move, down_move)), 2),
                "broken": broken,
                "distance_pct": round((ref / spot - 1) * 100, 2),
                "index_start": int(start),
                "index_end": int(end),
            })
            break               # the tightest base at this start is the zone

    # Overlapping bases describe one zone. Keep the strongest departure of each
    # cluster rather than stacking three bands on the same shelf.
    zones.sort(key=lambda z: -z["departure_atr"])
    kept: List[Dict[str, Any]] = []
    for z in zones:
        if any(not (z["top"] < k["bottom"] or z["bottom"] > k["top"]) for k in kept):
            continue
        kept.append(z)

    now_atr = float(atr_s[-1]) if len(atr_s) and np.isfinite(atr_s[-1]) else None
    live = [z for z in kept if not z["broken"]]
    out_of_range: List[Dict[str, Any]] = []
    if now_atr and now_atr > 0:
        reach = now_atr * float(np.sqrt(ZONE_HORIZON_BARS))
        in_range = []
        for z in live:
            (in_range if abs(spot * z["distance_pct"] / 100.0) <= reach
             else out_of_range).append(z)
        live = in_range
    live.sort(key=lambda z: abs(z["distance_pct"]))
    for z in live:
        z["out_of_horizon"] = False
    # Attached to the nearest surviving zone would be wrong — this is a fact about
    # the set, so it rides on the return value via a sentinel entry the caller
    # unpacks. Keeping it out of the zone list keeps the list purely levels.
    return live[:max_zones], len(out_of_range)


# ------------------------------------------------------------------- assemble

def analyse(df: pd.DataFrame, spot: Optional[float] = None,
            lookback: int = 252) -> Dict[str, Any]:
    """Everything this module finds, in one payload."""
    if df is None or len(df) < 40:
        return {"available": False,
                "reason": "Needs at least 40 daily bars to read structure."}
    price = float(spot if spot else df["Close"].iloc[-1])
    try:
        candles = candle_patterns(df)
        charts = chart_patterns(df, lookback=lookback)
        zones, far_zones = supply_demand_zones(df, price, lookback=lookback)
    except Exception as exc:                                  # noqa: BLE001
        log.warning("patterns: analyse failed: %s", exc)
        return {"available": False, "reason": str(exc)[:160]}

    return {
        "available": True,
        "spot": round(price, 4),
        "candles": candles,
        "chart_patterns": charts,
        "zones": zones,
        "zones_out_of_horizon": far_zones,
        "zone_horizon_bars": ZONE_HORIZON_BARS,
        "tolerances": {
            "level_tol_atr": LEVEL_TOL_ATR,
            "pivot_order": PIVOT_ORDER,
            "base_max_atr": BASE_MAX_ATR,
            "departure_atr": DEPARTURE_ATR,
            "min_amplitude_atr": MIN_AMPLITUDE_ATR,
            "prior_move_atr": PRIOR_MOVE_ATR,
            "max_midline_crossings": MAX_MIDLINE_CROSSINGS,
            "confirm_window_bars": [CONFIRM_WINDOW_MIN, CONFIRM_WINDOW_MAX],
        },
        "method": (
            "Pivots are fractal highs and lows with {order} bars clear either "
            "side. Levels count as equal within {tol} ATR, so the tolerance "
            "widens on a volatile name instead of splitting one pattern into "
            "two. A reversal pattern is marked confirmed only once a CLOSE has "
            "cleared its neckline, and cleared it within a window that scales "
            "with how long the pattern took to form — a crossing months later is "
            "a coincidence, not a resolution. Before that the geometry fits and "
            "nothing has happened yet. A pattern also has to be {amp} ATR tall and follow "
            "a move of at least {prior} ATR in the opposite direction: without "
            "those two tests an index that simply oscillates returns a reversal "
            "pattern every fortnight — and they alone were not enough, so the "
            "band the pattern occupies must not already have been cycled "
            "through: no more than {cross} crossings of its midline in the "
            "preceding {cwin} sessions. A range crosses its own middle a dozen "
            "times; a reversal comes into the band once. Overlapping "
            "detections are one piece of "
            "price action read several ways, so only the largest over any stretch "
            "is kept. Supply and demand zones require both halves of "
            "the definition: a base no wider than {base} ATR, then a departure "
            "of at least {dep} ATR within {dbars} bars. Zones are then filtered "
            "to what price could plausibly reach in {zbars} sessions — ATR times "
            "the square root of that — so old bases far below a stock that has "
            "run are counted separately rather than listed as levels. Directions "
            "shown are the "
            "conventional reading of each pattern, not a measurement — the base "
            "rates panel is where this terminal says what actually followed."
        ).format(order=PIVOT_ORDER, tol=LEVEL_TOL_ATR, base=BASE_MAX_ATR,
                 dep=DEPARTURE_ATR, dbars=DEPARTURE_BARS,
                 amp=MIN_AMPLITUDE_ATR, prior=PRIOR_MOVE_ATR,
                 zbars=ZONE_HORIZON_BARS, cross=MAX_MIDLINE_CROSSINGS,
                 cwin=CROSSING_WINDOW_BARS),
    }
