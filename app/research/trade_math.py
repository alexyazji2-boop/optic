"""Trade arithmetic: reward-to-risk, stop placement, sensitivity and sizing.

Pure functions, no I/O. Every figure a swing grade depends on is computed here
so that it can be checked by hand and tested in isolation.

Conventions:
  long  reward-to-risk = (target - entry) / (entry - stop)
  short reward-to-risk = (entry - target) / (stop - entry)
A plan whose stop is on the wrong side of entry, or whose target is, has no
reward-to-risk at all (None), not a negative one: it is not a plan.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _num(x: Any) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v and v not in (float("inf"), float("-inf")) else None


def reward_to_risk(entry: Any, stop: Any, target: Any, side: str = "long") -> Optional[float]:
    e, s, t = _num(entry), _num(stop), _num(target)
    if e is None or s is None or t is None:
        return None
    if side == "short":
        risk, reward = s - e, e - t
    else:
        risk, reward = e - s, t - e
    if risk <= 0 or reward <= 0:
        return None
    return reward / risk


def place_stop(entry: float, structural_stop: Optional[float], atr: Optional[float],
               atr_multiple: float, side: str = "long") -> Dict[str, Any]:
    """The stop: structural invalidation, widened to `atr_multiple` x ATR when
    structure sits closer than that. Never tightened.

    Returns {stop, basis, structural, atr_floor, widened, note}. The structural
    level is the price at which the setup's premise is wrong; the ATR floor is
    the distance inside which ordinary daily noise would stop the trade out.
    The wider of the two is used, because a stop inside the noise turns a
    correct idea into a loss, and a stop moved closer to flatter the
    reward-to-risk ratio misstates the risk being taken.
    """
    sign = -1.0 if side != "short" else 1.0
    floor = entry + sign * atr_multiple * atr if atr else None
    if structural_stop is None and floor is None:
        return {"stop": None, "basis": None, "structural": None, "atr_floor": None, "widened": False,
                "note": "No structural level and no ATR, so there is no defensible stop."}
    if structural_stop is None:
        return {"stop": floor, "basis": "atr", "structural": None, "atr_floor": floor, "widened": False,
                "note": "No structural level below entry was found, so the stop is the ATR distance alone."}
    wrong_side = (structural_stop >= entry) if side != "short" else (structural_stop <= entry)
    if wrong_side:
        return {"stop": floor, "basis": "atr", "structural": structural_stop, "atr_floor": floor,
                "widened": False,
                "note": "The structural level is on the wrong side of entry, so the ATR distance is used."}
    if floor is None:
        return {"stop": structural_stop, "basis": "structure", "structural": structural_stop,
                "atr_floor": None, "widened": False, "note": "Stop at structural invalidation (no ATR)."}
    struct_dist = abs(entry - structural_stop)
    floor_dist = abs(entry - floor)
    if struct_dist >= floor_dist:
        return {"stop": structural_stop, "basis": "structure", "structural": structural_stop,
                "atr_floor": floor, "widened": False,
                "note": "Stop at structural invalidation, already beyond {:g} daily ATRs.".format(atr_multiple)}
    return {"stop": floor, "basis": "atr", "structural": structural_stop, "atr_floor": floor, "widened": True,
            "note": "Structure sits inside {:g} daily ATRs of entry, inside ordinary noise, so the stop "
                    "was widened to that distance. It was not tightened.".format(atr_multiple)}


def sensitivity(entry: float, stop: float, target: float, side: str = "long", *,
                zone_low: Optional[float] = None, zone_high: Optional[float] = None,
                spread: Optional[float] = None, slippage_bps: float = 10.0) -> Dict[str, Any]:
    """How much the reward-to-risk depends on exactly where the fill lands.

    Three cases a reader can check: the best and worst fill inside the entry
    zone, and the representative entry after paying half the spread and
    `slippage_bps` on both the entry and the exit at the stop or the target.
    """
    out: Dict[str, Any] = {"representative": reward_to_risk(entry, stop, target, side)}
    cases: List[Dict[str, Any]] = []
    if zone_low is not None and zone_high is not None and zone_high > zone_low:
        best_entry, worst_entry = (zone_low, zone_high) if side != "short" else (zone_high, zone_low)
        cases.append({"case": "best fill in the entry zone", "entry": best_entry,
                      "rr": reward_to_risk(best_entry, stop, target, side)})
        cases.append({"case": "worst fill in the entry zone", "entry": worst_entry,
                      "rr": reward_to_risk(worst_entry, stop, target, side)})
    cost = entry * slippage_bps / 10000.0 + (spread or 0.0) / 2.0
    sign = 1.0 if side != "short" else -1.0
    e2 = entry + sign * cost          # pay up on the way in
    s2 = stop - sign * cost           # and give some back on the way out
    t2 = target - sign * cost
    cases.append({"case": "after spread and {:g}bp slippage each way".format(slippage_bps),
                  "entry": e2, "rr": reward_to_risk(e2, s2, t2, side)})
    out["cases"] = cases
    values = [c["rr"] for c in cases if c["rr"] is not None]
    if out["representative"] is not None:
        values.append(out["representative"])
    out["low"] = min(values) if values else None
    out["high"] = max(values) if values else None
    return out


def sizing_example(account: float, risk_pct: float, entry: float, stop: float,
                   gap_price: Optional[float] = None, side: str = "long") -> Dict[str, Any]:
    """Educational sizing arithmetic: shares that risk `risk_pct` of `account`
    if the stop fills at its price, and what a gap through the stop would cost.

    Not a recommendation of an account size or a risk level; the reader's own
    numbers replace both.
    """
    per_share = abs(entry - stop)
    if per_share <= 0 or account <= 0 or risk_pct <= 0:
        return {"available": False, "reason": "Needs a positive account, risk share and stop distance."}
    budget = account * risk_pct / 100.0
    shares = int(budget // per_share)
    out = {"available": True, "account": account, "risk_pct": risk_pct, "risk_budget": budget,
           "risk_per_share": per_share, "shares": shares, "position_value": shares * entry,
           "planned_loss": shares * per_share}
    if gap_price is not None:
        gap_loss = shares * abs(entry - gap_price)
        out["gap_price"] = gap_price
        out["gap_loss"] = gap_loss
        out["gap_note"] = ("A stop is an order, not a guarantee. If the stock opens at {:.2f}, beyond the "
                           "stop, the loss is about {:,.0f} rather than the planned {:,.0f}.".format(
                               gap_price, gap_loss, out["planned_loss"]))
    return out


PACE_ATR_PER_DAY = 0.4


def holding_estimate(entry: float, target: float, atr: Optional[float], max_days: int) -> Dict[str, Any]:
    """A rough holding period: the target's distance in daily ATRs, read as
    trading days, bounded by the policy's maximum. Stated as an estimate of
    pace, not a forecast of when the target is reached."""
    if not atr or atr <= 0:
        return {"days": None, "basis": "No ATR, so no pace estimate."}
    distance_atr = abs(target - entry) / atr
    # 0.4 ATR of net progress a day: a stock's daily range is mostly noise
    # around a much smaller drift, and the first version's two thirds of an
    # ATR put NVDA's 2.3-ATR target three sessions away, a pace few trends hold.
    days = int(min(max(round(distance_atr / PACE_ATR_PER_DAY), 3), max_days))
    return {"days": days, "distance_atr": distance_atr, "pace_atr_per_day": PACE_ATR_PER_DAY,
            "basis": "The target is {:.1f} daily ATRs away; at about {:g} ATR of net progress a day that is "
                     "roughly {} trading days, capped at {}. A pace estimate, not a forecast.".format(
                         distance_atr, PACE_ATR_PER_DAY, days, max_days)}
