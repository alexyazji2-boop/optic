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

**Why ten years of weeks, and a stage for every one of them.** The charts
colour each bar by the stage of its week, and the longest daily range on
screen is five years (the instrument page). A week needs 53 weeks behind it
before it has a stage, so five years of coloured bars needs six of history;
ten leaves room and is about 520 rows. Each week is read from the closes up to
and including its own and never a later one, so an old bar is coloured by what
its stage was then rather than by what hindsight makes it.

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

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence

SMA_WEEKS = 30          # Weinstein's own
SLOPE_WEEKS = 10        # the recent window the average's direction is read over
PRIOR_WEEKS = 13        # the window before it, which says where the trend came from
FLAT_PCT = 1.0          # |slope| under this, over SLOPE_WEEKS, is a flat average

MIN_WEEKS = SMA_WEEKS + SLOPE_WEEKS + PRIOR_WEEKS

NAMES = {1: "Basing", 2: "Advancing", 3: "Topping", 4: "Declining"}

# What each stage means, in the terms _read_at decides it in, for the charts'
# stage legend. Written here beside the rule so the two cannot drift: the
# legend was asked for as "what stages 1-4 is", and a definition the rule does
# not use would be a claim the chart cannot back.
MEANINGS = {
    1: ("After a decline, the 30-week average has gone flat or price has crossed "
        "it against its slope. A base forming."),
    2: ("Price is above a 30-week average that has risen more than 1% over ten "
        "weeks. The uptrend."),
    3: ("After an advance, the 30-week average has gone flat or price has crossed "
        "it against its slope. A top forming."),
    4: ("Price is below a 30-week average that has fallen more than 1% over ten "
        "weeks. The downtrend."),
}

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


def _valid(c) -> bool:
    return c is not None and c == c and c > 0


def _read_at(clean: Sequence[float], sma: Sequence[Optional[float]], i: int) -> Dict[str, Any]:
    """The reading at week ``i``, from the closes up to and including it.

    One function for the chip and for every coloured bar, so the newest bar on
    a chart and the label above it cannot disagree about the same week.
    """
    price = clean[i]
    now = sma[i]
    recent_from = sma[i - SLOPE_WEEKS]
    prior_from = sma[i - SLOPE_WEEKS - PRIOR_WEEKS]
    slope = _pct(now, recent_from)
    prior = _pct(recent_from, prior_from)
    trend = _direction(slope)
    above = price > now
    # Only its sign is needed, to tell a base from a top.
    came_from = "up" if prior > 0 else "down"
    if trend == "rising" and above:
        stage = 2
    elif trend == "falling" and not above:
        stage = 4
    else:
        stage = 1 if came_from == "down" else 3
    return {"stage": stage, "price": price, "now": now, "slope": slope,
            "prior": prior, "trend": trend, "above": above, "came_from": came_from}


def classify(closes: Sequence[float]) -> Dict[str, Any]:
    """The stage for a series of weekly closes, oldest first."""
    clean = [float(c) for c in closes if _valid(c)]
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
    r = _read_at(clean, sma, len(clean) - 1)
    stage, price, now = r["stage"], r["price"], r["now"]
    slope, prior, trend = r["slope"], r["prior"], r["trend"]
    above, came_from = r["above"], r["came_from"]

    transition = None
    # One word for the chip, the sentence for its title. The chip is read at a
    # glance beside a price; the reason it says "new" belongs a hover away.
    short = None
    if stage == 2:
        if came_from == "down":
            short = "new"
            transition = ("Newly in Stage 2: the average turned up only "
                          "recently, after a decline. Early advances are the "
                          "ones most likely to fail.")
    elif stage == 4:
        if came_from == "up":
            short = "new"
            transition = ("Newly in Stage 4: the average turned down only "
                          "recently, after an advance.")
    elif stage == 1 and above:
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


def history(weeks: Sequence[date], closes: Sequence[float]) -> List[List[Any]]:
    """``[[monday, stage], ...]`` for every week that has a stage at all.

    That is every week with MIN_WEEKS closes up to and including its own; the
    first 52 of any series have too little behind them and are left out rather
    than guessed.

    Keyed on the Monday of each week, as an ISO date, because that is a rule
    both ends can compute without agreeing on anything else: the feed labels a
    weekly bar by its Monday and the client finds a daily bar's Monday with
    the same arithmetic ``aggregateWeekly`` already uses. Normalised here
    anyway, so a feed that labelled a week by another day would still land on
    the right key.

    Bad closes are dropped with their dates, not after them. Filtering the
    closes alone would slide every later stage onto the wrong week.
    """
    pairs = [(w, float(c)) for w, c in zip(weeks, closes) if _valid(c)]
    if len(pairs) < MIN_WEEKS:
        return []
    clean = [c for _, c in pairs]
    sma = _sma(clean, SMA_WEEKS)
    out: List[List[Any]] = []
    for i in range(MIN_WEEKS - 1, len(clean)):
        w = pairs[i][0]
        monday = w - timedelta(days=w.weekday())
        out.append([monday.isoformat(), _read_at(clean, sma, i)["stage"]])
    return out


def _week_dates(frame) -> Optional[List[date]]:
    """The date of each weekly row, or None when the rows are not dated.

    The feed's weekly index is dated. One that was not would otherwise take the
    chip down with the colours, when only the colours need a date."""
    out: List[date] = []
    for ts in getattr(frame, "index", []):
        if isinstance(ts, datetime):
            out.append(ts.date())
        elif isinstance(ts, date):
            out.append(ts)
        else:
            return None
    return out


def for_symbol(provider, symbol: str) -> Dict[str, Any]:
    """Fetch ten years of weekly closes, classify them, and stage every week."""
    sym = (symbol or "").strip()
    if not sym:
        return {"available": False, "reason": "No symbol.", "limits": LIMITS}
    frame = provider.history(sym, period="10y", interval="1wk")
    if frame is None or getattr(frame, "empty", True):
        return {"available": False,
                "reason": "No weekly history for {}.".format(sym),
                "limits": LIMITS}
    closes = frame["Close"].astype(float).tolist()
    out = classify(closes)
    out["symbol"] = sym
    if out.get("available") is True:
        weeks = _week_dates(frame)
        if weeks is not None:
            out["history"] = history(weeks, closes)
        # The chart's key names every stage on screen, not only this week's,
        # and this is the one place the four names are written down.
        out["names"] = {str(k): v for k, v in NAMES.items()}
        out["meanings"] = {str(k): v for k, v in MEANINGS.items()}
    return out
