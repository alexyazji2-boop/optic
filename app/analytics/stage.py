"""Weinstein stage analysis: which of four trend states a chart is in.

From Stan Weinstein's *Secrets for Profiting in Bull and Bear Markets* (1988).
A price cycle is read off weekly closes against a 30-week simple moving
average, and the average's *slope* matters as much as which side of it the
price is on -- price above a falling average is a bounce, not an advance.

    Stage 1  Basing      average flattens after a decline
    Stage 2  Advancing   price above a rising average
    Stage 3  Topping     average flattens after an advance
    Stage 4  Declining   price below a falling average

**Why it fetches its own history.** A chart's visible range decides how many
bars it holds, and a 3-month chart has about thirteen weeks -- far short of a
30-week average. The stage is a property of the instrument, not of the range
the reader happens to be looking at, so it is computed from two years of
weekly closes whatever the chart shows.

**Why the slope is measured over ten weeks.** Calibrated on live data before
this was written. Over four weeks the S&P 500's steady uptrend read +1.5%,
close enough to a flat band that a quiet stretch would flicker it into "Stage
3" -- wrong for a healthy index. Over ten weeks it read +3.5%, and every symbol
checked landed where its chart says it is: ^GSPC, NVDA, AAPL and INTC in Stage
2, TSLA and TLT in Stage 4, META in Stage 1 above a still-falling average, and
PLTR in Stage 2 at $189.67 -- the same price and the same call as the TrendSpider
chart it was checked against.

**Mixed readings are the interesting ones.** When price and slope disagree --
above a falling average, below a rising one -- or the average is flat, the stage
is a transition, and which one depends on where the trend came from: flattening
after a decline is a base, after an advance a top. That is decided by the
average's slope over the thirteen weeks *before* the recent window.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

SMA_WEEKS = 30          # Weinstein's own
SLOPE_WEEKS = 10        # the recent window the average's direction is read over
PRIOR_WEEKS = 13        # the window before it, which says where the trend came from
FLAT_PCT = 1.0          # |slope| under this, over SLOPE_WEEKS, is a flat average

MIN_WEEKS = SMA_WEEKS + SLOPE_WEEKS + PRIOR_WEEKS

NAMES = {1: "Basing", 2: "Advancing", 3: "Topping", 4: "Declining"}

# Said on every reading, not only when asked: the house rule that a panel
# states what it cannot tell you.
LIMITS = ("Weinstein's stages are read off weekly closes against a 30-week "
          "average. They are easy to draw in hindsight and harder to call in "
          "real time: a breakout can fail and a base can roll over into more "
          "decline. It describes the trend a chart is in, not where it goes "
          "next.")


def _sma(values: Sequence[float], n: int) -> List[Optional[float]]:
    out: List[Optional[float]] = []
    total = 0.0
    for i, v in enumerate(values):
        total += v
        if i >= n:
            total -= values[i - n]
        out.append(total / n if i >= n - 1 else None)
    return out


def _pct(now: float, then: float) -> float:
    return (now - then) / then * 100.0 if then else 0.0


def _direction(slope_pct: float) -> str:
    if slope_pct > FLAT_PCT:
        return "rising"
    if slope_pct < -FLAT_PCT:
        return "falling"
    return "flat"


def classify(closes: Sequence[float]) -> Dict[str, Any]:
    """The stage for a series of weekly closes, oldest first."""
    clean = [float(c) for c in closes if c is not None and c == c and c > 0]
    if len(clean) < MIN_WEEKS:
        return {
            "available": False,
            "reason": ("A stage needs {} weeks of closes: {} for the 30-week "
                       "average and {} more to read which way it is heading. "
                       "This has {}.").format(MIN_WEEKS, SMA_WEEKS,
                                               SLOPE_WEEKS + PRIOR_WEEKS, len(clean)),
            "limits": LIMITS,
        }

    sma = _sma(clean, SMA_WEEKS)
    price = clean[-1]
    now = sma[-1]
    recent_from = sma[-1 - SLOPE_WEEKS]
    prior_from = sma[-1 - SLOPE_WEEKS - PRIOR_WEEKS]

    slope = _pct(now, recent_from)
    prior = _pct(recent_from, prior_from)
    trend = _direction(slope)
    above = price > now
    # Only its sign is needed, to tell a base from a top.
    came_from = "up" if prior > 0 else "down"

    transition = None
    # One word for the chip, the sentence for its title. The chip is read at a
    # glance beside a price; the reason it says "new" belongs a hover away.
    short = None
    if trend == "rising" and above:
        stage = 2
        if came_from == "down":
            short = "new"
            transition = ("Newly in Stage 2: the average turned up only "
                          "recently, after a decline. Early advances are the "
                          "ones most likely to fail.")
    elif trend == "falling" and not above:
        stage = 4
        if came_from == "up":
            short = "new"
            transition = ("Newly in Stage 4: the average turned down only "
                          "recently, after an advance.")
    else:
        stage = 1 if came_from == "down" else 3
        if stage == 1 and above:
            short = "breakout"
            transition = ("Price has broken above the average, but the average "
                          "is not rising yet, which is what Weinstein waited for "
                          "before calling it Stage 2.")
        elif stage == 3 and not above:
            short = "breakdown"
            transition = ("Price has slipped below an average that is not "
                          "falling yet: the first sign of a top, or a "
                          "pullback inside the advance.")

    vs = _pct(price, now)
    explain = ("Price is {:.1f}% {} a 30-week average that has {} {:.1f}% over "
               "{} weeks.").format(abs(vs), "above" if above else "below",
                                    {"rising": "risen", "falling": "fallen",
                                     "flat": "moved"}[trend],
                                    abs(slope), SLOPE_WEEKS)
    return {
        "available": True,
        "stage": stage,
        "name": NAMES[stage],
        "label": "Stage {} · {}".format(stage, NAMES[stage]),
        "price": round(price, 4),
        "sma30w": round(now, 4),
        "vs_sma_pct": round(vs, 2),
        "slope_pct": round(slope, 2),
        "prior_slope_pct": round(prior, 2),
        "trend": trend,
        "slope_weeks": SLOPE_WEEKS,
        "transition": transition,
        "transition_short": short,
        "explain": explain,
        "limits": LIMITS,
        "weeks": len(clean),
    }


def for_symbol(provider, symbol: str) -> Dict[str, Any]:
    """Fetch two years of weekly closes and classify them."""
    sym = (symbol or "").strip()
    if not sym:
        return {"available": False, "reason": "No symbol.", "limits": LIMITS}
    frame = provider.history(sym, period="2y", interval="1wk")
    if frame is None or getattr(frame, "empty", True):
        return {"available": False,
                "reason": "No weekly history for {}.".format(sym),
                "limits": LIMITS}
    out = classify(frame["Close"].astype(float).tolist())
    out["symbol"] = sym
    return out
