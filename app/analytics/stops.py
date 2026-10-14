"""Where a stop should sit relative to round numbers, and what moving it costs.

From a trading post (nicholascrown, 2026): stops cluster at round numbers, so
price runs through the level, takes the stops just past it and turns back;
"buffer your stop by a fraction of ATR past the round number". The research it
points to is Carol Osler's at the New York Fed (Journal of Finance, 2003), which
found stop-loss orders clustered just beyond round numbers in currency order
books. Currencies, not shares: so before adopting the idea it was measured on
stocks, and the measurement is what this module's defaults and wording rest on.

**The measurement** (2026-10-14; `docs/research/stops-round-numbers-2026-10-14.md`).
Twenty liquid US stocks and ETFs, five-minute bars, the 60 sessions to
2026-10-13. For every first cross of a level in a session, how far the price
went past it (in daily ATRs) before a five-minute close back on the near side.
Round levels (multiples of $10 above $100, $5 from $20, $1 below) against a
control grid of arbitrary prices at the same spacing:

* Falls through a round number overshot by more than 0.10 ATR 37% of the time,
  against 28% at arbitrary prices; by more than 0.25 ATR, 19% against 14%.
  Rises through one showed no clear difference (34% against 32%).
* At any level, most crosses came back within the session (86 to 91%): a stop
  right at a level is mostly taken by a move that then reverses.

So the round-number effect in stocks is real but modest, and the larger point
is general: a stop sitting at a level, round or not, is the one a sweep takes.
The helper therefore checks for a round number near the stop, moves the stop a
buffer past it (never closer to the price), and says how often a cross went
that far in the sample and how much more is at risk.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

# P(a cross overshoots by more than b daily ATRs), per cent, from the study.
EVIDENCE = {
    "sample": "20 liquid US stocks and ETFs, 5-minute bars, the 60 sessions to 2026-10-13",
    "buffers_atr": [0.05, 0.10, 0.15, 0.25, 0.50],
    "round_down": [53.8, 36.9, 27.9, 18.9, 7.1],
    "control_down": [44.6, 28.2, 22.9, 14.1, 4.9],
    "round_up": [50.3, 34.0, 25.9, 16.7, 7.1],
    "control_up": [48.9, 32.4, 24.9, 17.7, 7.0],
    "came_back_pct": {"round_down": 86.2, "control_down": 91.0, "round_up": 88.9, "control_up": 88.4},
    "crosses": {"round_down": 567, "control_down": 554, "round_up": 576, "control_up": 571},
}
DEFAULT_BUFFER_ATR = 0.25
NEAR_ATR = 0.25          # a round number within this of the stop counts as "at" it


def grid_step(price: float) -> float:
    """The spacing of round numbers a trader would see at this price."""
    p = abs(price)
    if p >= 1000:
        return 50.0
    if p >= 100:
        return 10.0
    if p >= 20:
        return 5.0
    if p >= 2:
        return 1.0
    return 0.1


def strength(level: float, step: float) -> str:
    """'major' for a multiple of ten steps (200, 1,000), 'half' for five (250),
    'minor' for one (210)."""
    k = round(level / step)
    if k % 10 == 0:
        return "major"
    if k % 5 == 0:
        return "half"
    return "minor"


def round_levels(lo: float, hi: float, step: Optional[float] = None) -> List[Dict[str, Any]]:
    step = step or grid_step((lo + hi) / 2)
    first = math.ceil(lo / step - 1e-9)
    last = math.floor(hi / step + 1e-9)
    return [{"price": round(k * step, 6), "strength": strength(k * step, step)} for k in range(first, last + 1)]


def _share(side: str, kind: str, buf: float) -> Optional[float]:
    """The share of crosses in the study that overshot by more than `buf` ATRs,
    interpolated between the measured buffers."""
    key = "{}_{}".format(kind, "down" if side == "long" else "up")
    xs, ys = EVIDENCE["buffers_atr"], EVIDENCE[key]
    if buf <= xs[0]:
        return ys[0]
    if buf >= xs[-1]:
        return ys[-1]
    for i in range(1, len(xs)):
        if buf <= xs[i]:
            t = (buf - xs[i - 1]) / (xs[i] - xs[i - 1])
            return round(ys[i - 1] + t * (ys[i] - ys[i - 1]), 1)
    return None


def check(entry: float, stop: float, atr: float, buffer_atr: float = DEFAULT_BUFFER_ATR,
          account: Optional[float] = None, risk_pct: float = 1.0) -> Dict[str, Any]:
    """Whether a stop sits at a round number, and where a buffered one would go.

    The side follows from the prices: a stop below the entry protects a long.
    A stop is only ever moved further from the price, never closer: moving it
    in would put it back among the orders the buffer is meant to avoid."""
    if not all(isinstance(x, (int, float)) and math.isfinite(x) for x in (entry, stop, atr)):
        return {"available": False, "reason": "Entry, stop and ATR must be numbers."}
    if entry <= 0 or atr <= 0 or stop <= 0 or stop == entry:
        return {"available": False, "reason": "The stop must differ from the entry, and prices and ATR be positive."}
    side = "long" if stop < entry else "short"
    sign = 1 if side == "long" else -1           # the stop sits at entry - sign * risk
    buffer_atr = max(0.0, min(2.0, float(buffer_atr)))
    step = grid_step(entry)
    near = NEAR_ATR * atr
    # Round numbers from just beyond the stop to the entry: one there is a
    # level the price has to cross on its way to the stop.
    lo, hi = sorted((stop - sign * near, entry))
    window = [r for r in round_levels(lo, hi, step) if abs(r["price"] - stop) <= near]
    order = {"major": 0, "half": 1, "minor": 2}
    at = sorted(window, key=lambda r: (order[r["strength"]], abs(r["price"] - stop)))[0] if window else None

    adjusted, moved = stop, False
    if at:
        target = at["price"] - sign * buffer_atr * atr
        # Further from the entry only.
        if sign * (stop - target) > 1e-9:
            adjusted, moved = target, True
    adjusted = round(adjusted, 2)
    risk0, risk1 = abs(entry - stop), abs(entry - adjusted)
    past = (sign * (at["price"] - adjusted) / atr) if at else None
    past0 = (sign * (at["price"] - stop) / atr) if at else None

    def size(risk):
        if not account or account <= 0 or risk <= 0:
            return None
        return int(math.floor(account * risk_pct / 100.0 / risk))

    if not at:
        text = ("No round number within {:.2f} ATR of the stop (the nearest are every ${:g}). Nothing to move it "
                "past; the general point still holds, that a stop sitting right at any level is the one a sweep "
                "takes.".format(NEAR_ATR, step))
    elif not moved:
        text = ("The stop is already {:.2f} ATR past {}, the round number beside it.".format(
            past, _usd(at["price"])))
    else:
        text = ("The stop at {} sits {} the round number {}, where stops cluster. {} it to {}, {:g} ATR past the "
                "level, widens the risk from {} to {} a share.".format(
                    _usd(stop), "just past" if sign * (at["price"] - stop) > 0 else "just inside",
                    _usd(at["price"]), "Moving", _usd(adjusted), buffer_atr, _usd(risk0), _usd(risk1)))
    kind_share = _share(side, "round", past) if at and past is not None else None
    # A stop on the near side of the level is reached by every cross of it.
    before_share = (100.0 if past0 <= 0 else _share(side, "round", past0)) if at else None
    return {
        "available": True,
        "side": side,
        "entry": round(entry, 4), "stop": round(stop, 4), "atr": round(atr, 4),
        "buffer_atr": buffer_atr, "step": step,
        "round_level": at,
        "nearby": round_levels(min(entry, stop) - 2 * step, max(entry, stop) + 2 * step, step),
        "adjusted_stop": adjusted,
        "moved": moved,
        "risk_per_share": round(risk0, 4), "risk_per_share_adjusted": round(risk1, 4),
        "risk_pct_of_entry": round(risk0 / entry * 100, 2), "risk_pct_of_entry_adjusted": round(risk1 / entry * 100, 2),
        "shares_for_risk": size(risk0), "shares_for_risk_adjusted": size(risk1),
        "account": account, "risk_pct": risk_pct,
        "past_level_atr": None if past is None else round(past, 3),
        # How often a cross of a round number went further than this stop sits past it.
        "swept_share_pct": kind_share,
        "swept_share_pct_before": before_share,
        "text": text,
        "evidence": EVIDENCE,
        "method": ("A round number counts as at the stop within {:.2f} ATR of it. The buffered stop is the round "
                   "number less {:g} ATR for a long (plus, for a short), never moved closer to the price. ATR is "
                   "the 14-day average true range.".format(NEAR_ATR, buffer_atr)),
        "caveats": [
            "Measured on 60 sessions of 20 large, liquid names; thinner stocks and other markets may differ.",
            "A wider stop is hit less often and costs more when it is: size the trade from the wider stop.",
            "Where orders actually rest is not public; round numbers are a proxy for it.",
        ],
    }


def _usd(v: float) -> str:
    return "${:,.2f}".format(v)
