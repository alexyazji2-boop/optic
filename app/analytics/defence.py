"""What price has to hold through the close to keep the trend intact.

An intraday dip below a moving average means nothing — the average is defined on
closes. So the question a swing trader actually has at 3pm is narrower than "where
is support": it is *which single level, if the closing print lands the wrong side
of it, changes the read I am holding overnight.*

That level is the nearest trend-defining one on the side price is defending. In an
uptrend that is the highest level below spot; in a downtrend the lowest above it.
Everything further away is irrelevant today, because this one breaks first.

The module takes a list of candidate levels and picks the binding one. Which
levels count is the caller's decision, and it differs by horizon: a daily swing is
defined by the 9-day EMA and today's pivot, a multi-year hold by the 40-week
average. Feeding weekly levels to a day trade, or daily noise to a decade-long
position, produces a number that is arithmetically right and useless.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

# Regular session close, in ET minutes from midnight.
CLOSE_MINUTE = 16 * 60

# A cushion thinner than this is "within touching distance" — worth flagging,
# because normal noise covers it in a single bar.
TIGHT_CUSHION_PCT = 0.5


def _num(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if out != out or out in (float("inf"), float("-inf")):
        return None
    return out


def minutes_to_close(now: Optional[datetime] = None) -> Optional[int]:
    """Minutes until 4pm ET, or None outside a weekday regular session."""
    when = (now or datetime.now(timezone.utc)).astimezone(ET)
    if when.weekday() >= 5:
        return None
    minute = when.hour * 60 + when.minute
    if minute < 9 * 60 + 30 or minute >= CLOSE_MINUTE:
        return None
    return CLOSE_MINUTE - minute


def evaluate(spot: Optional[float], direction: Optional[str],
             candidates: List[Dict[str, Any]],
             now: Optional[datetime] = None) -> Dict[str, Any]:
    """The level that must hold, and what breaks if it doesn't.

    `direction` is "up" or "down". `candidates` are dicts of label / price /
    breaks. Levels on the wrong side of price are dropped rather than reported as
    already-broken: in an uptrend the averages *above* price are resistance, which
    is a different question from what is being defended.
    """
    spot = _num(spot)
    # spot must be a positive price. Level prices were already guarded but this
    # was not: zero divided by zero in the distance calculation, and a negative
    # spot produced a confident answer built on nonsense.
    if spot is None or spot <= 0 or direction not in ("up", "down"):
        return {"available": False}

    clean: List[Dict[str, Any]] = []
    # Two sources can name the same price — the long-term adapter's accumulation
    # zones include the 40-week average, so the ladder listed it twice. Keep the
    # first mention, which is the more specific label.
    seen_prices = set()
    for row in candidates or []:
        price = _num((row or {}).get("price"))
        label = (row or {}).get("label")
        if price is None or not label or price <= 0:
            continue
        stamp = round(price, 2)
        if stamp in seen_prices:
            continue
        seen_prices.add(stamp)
        clean.append({
            "label": str(label),
            "price": round(price, 4),
            "breaks": str((row or {}).get("breaks") or ""),
            "distance_pct": round((price / spot - 1.0) * 100.0, 2),
        })
    if not clean:
        return {"available": False}

    defending = "up" if direction == "up" else "down"
    if defending == "up":
        # Uptrend: the highest level still beneath price is the first to give.
        below = [lv for lv in clean if lv["price"] < spot]
        below.sort(key=lambda lv: -lv["price"])
        ladder = below
    else:
        above = [lv for lv in clean if lv["price"] > spot]
        above.sort(key=lambda lv: lv["price"])
        ladder = above

    if not ladder:
        # Every trend level is on the other side of price: the trend the caller
        # asked about is not the one price is in.
        return {
            "available": True,
            "direction": defending,
            "must_hold": None,
            "note": ("Price is already on the wrong side of every level that defines "
                     "this trend, so there is nothing left to defend into the close — "
                     "the trend read itself is what has changed."),
            "minutes_to_close": minutes_to_close(now),
            "levels": clean,
        }

    must_hold = ladder[0]
    cushion = abs(must_hold["distance_pct"])
    remaining = minutes_to_close(now)

    if defending == "up":
        requirement = f"close at or above {must_hold['price']:,.2f}"
        consequence = must_hold["breaks"] or "the uptrend structure"
    else:
        requirement = f"close at or below {must_hold['price']:,.2f}"
        consequence = must_hold["breaks"] or "the downtrend structure"

    return {
        "available": True,
        "direction": defending,
        "must_hold": must_hold,
        "next_level": ladder[1] if len(ladder) > 1 else None,
        "cushion_pct": round(cushion, 2),
        "tight": cushion <= TIGHT_CUSHION_PCT,
        "requirement": requirement,
        "consequence": consequence,
        "minutes_to_close": remaining,
        "levels": ladder,
        "method": (
            "Moving averages, pivots and value areas are all defined on closing "
            "prices, so an intraday poke through them decides nothing. This is the "
            "nearest level on the side price is defending — the one a closing print "
            "reaches first. Levels on the other side of price are resistance, not "
            "defence, and are excluded."
        ),
    }


# ------------------------------------------------------------------- adapters

def for_swing(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Daily-horizon defence, from the /api/ticker payload."""
    if not isinstance(payload, dict):
        return {"available": False}
    tech = payload.get("technicals") or {}
    struct = payload.get("structure") or {}
    spot = _num(tech.get("spot")) or _num((payload.get("quote") or {}).get("price"))

    bias = (tech.get("bias") or "").lower()
    direction = "up" if "bull" in bias else "down" if "bear" in bias else None
    if direction is None:
        # Neutral chart: fall back to which side of the 50-day it sits on, so the
        # panel still answers the question rather than disappearing.
        sma50 = _num(((tech.get("moving_averages") or {}).get("sma50") or {}).get("value"))
        if spot is not None and sma50:
            direction = "up" if spot >= sma50 else "down"

    mas = tech.get("moving_averages") or {}
    candidates: List[Dict[str, Any]] = []

    for key, label, breaks in (
        ("ema9", "9-day EMA", "the fast-average stack that defines the current leg"),
        ("ema21", "21-day EMA", "the three-week trend"),
        ("ema50", "50-day EMA", "the intermediate trend"),
        ("sma20", "20-day average", "the short-term trend"),
        ("sma50", "50-day average", "the intermediate trend most desks watch"),
        ("sma200", "200-day average", "the long-term trend line"),
    ):
        block = mas.get(key) or {}
        candidates.append({"label": label, "price": _num(block.get("value")),
                           "breaks": breaks})

    pivots = struct.get("pivots") or {}
    if pivots.get("available"):
        candidates.append({"label": "Today's pivot", "price": _num(pivots.get("pp")),
                           "breaks": "the session's own bias line"})

    vp = struct.get("volume_profile") or {}
    if vp.get("available"):
        candidates.append({"label": "Value area high", "price": _num(vp.get("vah")),
                           "breaks": "the breakout above the volume shelf"})
        candidates.append({"label": "Value area low", "price": _num(vp.get("val")),
                           "breaks": "the hold inside the volume shelf"})

    fib = tech.get("fibonacci") or {}
    for side in ("nearest_support", "nearest_resistance"):
        level = fib.get(side) or {}
        if level:
            candidates.append({
                "label": f"Fib {level.get('label', '')}".strip(),
                "price": _num(level.get("price")),
                "breaks": "the retracement that has been holding",
            })

    out = evaluate(spot, direction, candidates)
    out["horizon"] = "daily"
    return out


def for_longterm(holding: Dict[str, Any]) -> Dict[str, Any]:
    """Multi-year-horizon defence, from the /api/longterm holding block.

    Weekly averages only. A ten-year position is not decided by the 9-day EMA, and
    quoting one here would invite exactly the wrong reaction to a normal wobble.
    """
    if not isinstance(holding, dict):
        return {"available": False}
    spot = _num(holding.get("price"))
    trend = holding.get("long_trend") or {}

    phase = (trend.get("phase") or "").lower()
    if "up" in phase or "advanc" in phase or "bull" in phase:
        direction = "up"
    elif "down" in phase or "declin" in phase or "bear" in phase:
        direction = "down"
    else:
        direction = "up" if trend.get("above_40w_sma") else "down"

    candidates = [
        {"label": "40-week average", "price": _num(trend.get("sma_40w")),
         "breaks": "the multi-quarter uptrend (the weekly 200-day equivalent)"},
        {"label": "200-week average", "price": _num(trend.get("sma_200w")),
         "breaks": "the multi-year trend — the line that separates bull from bear regimes"},
    ]
    for zone in (holding.get("accumulation_zones") or []):
        candidates.append({
            "label": str((zone or {}).get("label") or "Accumulation zone"),
            "price": _num((zone or {}).get("price")),
            "breaks": "the zone flagged for adding on weakness",
        })

    out = evaluate(spot, direction, candidates)
    out["horizon"] = "weekly"
    # Weekly averages move on Friday's close, not tonight's.
    out["cadence_note"] = (
        "Weekly averages are set by Friday's close, so a single day through one of "
        "these is not yet a break — the level that matters is where the week ends."
    )
    return out
