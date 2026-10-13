"""What a single- or multi-leg options position does, at expiry and before it.

For a research tool, not an order ticket: every figure is a model estimate
from the chain's quotes, and each says what it assumes.

**Two curves, kept apart.** The payoff at expiry is arithmetic: intrinsic
value of each leg at the expiry price, minus what was paid. Exact, given the
entry price. The value before expiry ("today" and "halfway") is a
Black-Scholes estimate at each leg's current implied volatility, held fixed
as price moves (sticky strike): what the position might be worth if nothing
but the price changed. Real IVs move with price, especially on a fall, so the
before-expiry curve is an illustration, not a quote.

**Entry price, three ways.** At the mid (the optimistic estimate between the
quotes), at the natural price (buy at the ask, sell at the bid: what crossing
the spread costs), and at the mid plus a slippage share of each leg's half
spread, plus a per-contract fee. Research on retail fills (Bryzgalova, Pavlova
& Sikorskaya 2023: about a 12.6% quoted spread on retail-favoured weeklies)
is why the natural price is shown at all. A multi-leg order can fill inside
the legs' combined spread on an exchange's complex order book; nothing here
can see that book.

**Max loss is not margin.** The maximum loss is the payoff curve's minimum,
or unbounded when a short call is uncovered. A broker's margin requirement is
set by its own rules (FINRA 4210 sets the floor) and can be far below the
maximum loss of an undefined-risk position; this module does not compute it.

**Exercise style.** With `american` (equity and ETF options) the values before
expiry are Barone-Adesi-Whaley American prices, so a long leg's right to
exercise early is in them (Options audit O2).

**What is not modelled:** whether a short American leg is assigned early, which
is the holder's choice (most likely on a short call just before an ex-dividend
date, or a deep in-the-money short put; the endpoint flags both), pin risk at expiry, legs on different expiries settling on
different days (a calendar's "at expiry" curve is at the first expiry, with
the later leg valued by the model), dividends beyond a continuous yield.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import numpy as np
from scipy.special import ndtr

from app.analytics import american as american_mod

from .vol_surface import MIN_TAU

MULT = 100.0


def _bs_vec(S, K, tau, vol, r, q, is_call):
    S = np.asarray(S, dtype=float)
    tau = max(float(tau), MIN_TAU)
    vsqrt = vol * np.sqrt(tau)
    d1 = (np.log(S / K) + (r - q + 0.5 * vol * vol) * tau) / vsqrt
    d2 = d1 - vsqrt
    if is_call:
        return S * np.exp(-q * tau) * ndtr(d1) - K * np.exp(-r * tau) * ndtr(d2)
    return K * np.exp(-r * tau) * ndtr(-d2) - S * np.exp(-q * tau) * ndtr(-d1)


def _greeks1(S, K, tau, vol, r, q, is_call):
    tau = max(float(tau), MIN_TAU)
    sq = np.sqrt(tau)
    d1 = (np.log(S / K) + (r - q + 0.5 * vol * vol) * tau) / (vol * sq)
    d2 = d1 - vol * sq
    pdf = np.exp(-0.5 * d1 * d1) / np.sqrt(2 * np.pi)
    dq, dr = np.exp(-q * tau), np.exp(-r * tau)
    delta = dq * ndtr(d1) if is_call else dq * (ndtr(d1) - 1.0)
    gamma = dq * pdf / (S * vol * sq)
    vega = S * dq * pdf * sq / 100.0
    common = -S * dq * pdf * vol / (2 * sq)
    if is_call:
        theta = common - r * K * dr * ndtr(d2) + q * S * dq * ndtr(d1)
        p_itm = ndtr(d2)
    else:
        theta = common + r * K * dr * ndtr(-d2) - q * S * dq * ndtr(-d1)
        p_itm = ndtr(-d2)
    return {"delta": float(delta), "gamma": float(gamma), "vega": float(vega),
            "theta": float(theta / 365.0), "p_itm": float(p_itm)}


def _leg_value_at_expiry(leg: Dict[str, Any], S: np.ndarray) -> np.ndarray:
    if leg["type"] == "stock":
        return S.copy()
    if leg["type"] == "call":
        return np.maximum(S - leg["strike"], 0.0)
    return np.maximum(leg["strike"] - S, 0.0)


def _leg_value_model(leg: Dict[str, Any], S: np.ndarray, tau: float, r: float, q: float,
                     iv_shift: float = 0.0) -> np.ndarray:
    if leg["type"] == "stock":
        return S.copy()
    if tau <= MIN_TAU:
        return _leg_value_at_expiry(leg, S)
    vol = max(leg["iv"] + iv_shift, 0.01)
    if leg.get("american"):
        return american_mod.baw(S, leg["strike"], tau, vol, r, q, leg["type"] == "call")
    return _bs_vec(S, leg["strike"], tau, vol, r, q, leg["type"] == "call")


def _sign(leg: Dict[str, Any]) -> float:
    return 1.0 if leg["side"] == "long" else -1.0


def _units(leg: Dict[str, Any]) -> float:
    """Shares a leg moves per $1: contracts x 100, or stock shares."""
    return float(leg["qty"]) * (1.0 if leg["type"] == "stock" else MULT)


def entry_prices(legs: Sequence[Dict[str, Any]], slippage: float = 0.25,
                 fee_per_contract: float = 0.65) -> Dict[str, Any]:
    """Net cash at entry (positive = paid, negative = received), three ways."""
    mid = natural = slipped = 0.0
    fees = 0.0
    spread_cost = 0.0
    for leg in legs:
        s = _sign(leg)
        u = _units(leg)
        m = leg["mid"]
        if leg["type"] == "stock":
            mid += s * m * u
            natural += s * m * u
            slipped += s * m * u
            continue
        bid = leg.get("bid") or m
        ask = leg.get("ask") or m
        half = max((ask - bid) / 2.0, 0.0)
        mid += s * m * u
        natural += ask * u if s > 0 else -bid * u
        slipped += s * (m + s * slippage * half) * u
        fees += fee_per_contract * float(leg["qty"])
        spread_cost += (ask - bid) * u
    return {
        "mid": round(mid, 2),
        "natural": round(natural, 2),
        "with_slippage_and_fees": round(slipped + fees, 2),
        "fees": round(fees, 2),
        "slippage_share_of_half_spread": slippage,
        "fee_per_contract": fee_per_contract,
        "legs_full_spread": round(spread_cost, 2),
        "note": ("Positive is paid, negative received. Natural buys at the ask and sells at the bid. "
                 "The slippage figure assumes a fill {:.0%} of the way from the mid toward the worse "
                 "side of each leg, plus ${:.2f} a contract in fees; set both to your broker's.".format(
                     slippage, fee_per_contract)),
    }


def _price_grid(legs: Sequence[Dict[str, Any]], spot: float, span_pct: float) -> np.ndarray:
    strikes = [l["strike"] for l in legs if l["type"] != "stock"]
    lo = min([spot * (1 - span_pct)] + [k * 0.9 for k in strikes])
    hi = max([spot * (1 + span_pct)] + [k * 1.1 for k in strikes])
    grid = np.linspace(max(lo, 0.01), hi, 241)
    # A price of (almost) zero is always on the grid, so a loss that is bounded
    # because a price cannot fall below zero is measured there, not at the
    # edge of the drawn range.
    return np.unique(np.concatenate([[1e-6], grid, np.array(strikes + [spot])]))


def _roots(x: np.ndarray, y: np.ndarray) -> List[float]:
    out = []
    for i in range(1, len(x)):
        if y[i - 1] == 0:
            out.append(float(x[i - 1]))
        elif y[i - 1] * y[i] < 0:
            out.append(float(x[i - 1] - y[i - 1] * (x[i] - x[i - 1]) / (y[i] - y[i - 1])))
    dedup: List[float] = []
    for v in out:
        if not dedup or abs(v - dedup[-1]) > 1e-6 * max(1.0, v):
            dedup.append(round(v, 2))
    return dedup


def analyse(legs: Sequence[Dict[str, Any]], spot: float, rate: float, div: float,
            days_forward: Optional[float] = None, slippage: float = 0.25,
            fee_per_contract: float = 0.65, span_pct: float = 0.25,
            american: bool = False) -> Dict[str, Any]:
    """Each leg: {type: call|put|stock, side: long|short, qty, strike, expiry,
    tau (years to its expiry), iv (decimal), mid, bid, ask}. `american`
    values the legs before expiry on an American-exercise price."""
    legs = [dict(l, american=american and l.get("type") != "stock") for l in legs]
    if not legs:
        return {"available": False, "reason": "no legs"}
    opt = [l for l in legs if l["type"] != "stock"]
    first_tau = min([l["tau"] for l in opt], default=0.0)
    entry = entry_prices(legs, slippage, fee_per_contract)
    cost = entry["mid"]                       # curves are drawn from the mid entry
    grid = _price_grid(legs, spot, span_pct)

    # At the first expiry: options expiring then at intrinsic, later ones by model.
    def value_at(tau_elapsed: float, iv_shift: float = 0.0) -> np.ndarray:
        total = np.zeros_like(grid)
        for leg in legs:
            remaining = (leg.get("tau") or 0.0) - tau_elapsed if leg["type"] != "stock" else 0.0
            if leg["type"] == "stock":
                v = grid.copy()
            elif remaining <= MIN_TAU * 1.01:
                v = _leg_value_at_expiry(leg, grid)
            else:
                v = _leg_value_model(leg, grid, remaining, rate, div, iv_shift)
            total += _sign(leg) * v * _units(leg)
        return total

    at_expiry = value_at(first_tau) - cost
    today = value_at(0.0) - cost
    half = value_at(first_tau / 2.0) - cost

    # Bounded or not: the slope as price runs away in each direction.
    up_slope = sum(_sign(l) * _units(l) for l in legs if l["type"] in ("call", "stock")
                   and (l["type"] == "stock" or l["tau"] <= first_tau + 1e-9))
    calendar = any(l["type"] != "stock" and l["tau"] > first_tau + 1e-9 for l in legs)
    max_profit = float(np.max(at_expiry))
    max_loss = float(np.min(at_expiry))
    profit_unbounded = up_slope > 1e-9 and not calendar
    loss_unbounded = up_slope < -1e-9 and not calendar

    agg = {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
    leg_rows = []
    for leg in legs:
        s, u = _sign(leg), _units(leg)
        if leg["type"] == "stock":
            agg["delta"] += s * u
            leg_rows.append({**_public(leg), "delta_shares": s * u})
            continue
        g = _greeks1(spot, leg["strike"], leg["tau"], leg["iv"], rate, div, leg["type"] == "call")
        for k in agg:
            agg[k] += s * u * g[k]
        leg_rows.append({**_public(leg), "delta": round(g["delta"], 3), "p_itm_model": round(g["p_itm"], 3),
                         "theta_per_day": round(s * u * g["theta"], 2),
                         "vega_per_pt": round(s * u * g["vega"], 2)})

    # Scenario grid: price x IV, at "today", at the chosen day, and at expiry.
    moves = [-0.10, -0.05, -0.02, 0.0, 0.02, 0.05, 0.10]
    shifts = [-0.10, 0.0, 0.10]
    fwd = days_forward / 365.0 if days_forward is not None else first_tau / 2.0
    fwd = min(max(fwd, 0.0), first_tau)
    scen = []
    for dt_years, label in ((0.0, "now"), (fwd, "in {:.0f} days".format(fwd * 365)), (first_tau, "at expiry")):
        for sh in shifts:
            row = {"when": label, "iv_shift_pts": int(round(sh * 100)), "pnl": []}
            for m in moves:
                S = np.array([spot * (1 + m)])
                total = 0.0
                for leg in legs:
                    rem = (leg.get("tau") or 0.0) - dt_years if leg["type"] != "stock" else 0.0
                    if leg["type"] == "stock":
                        v = S
                    elif rem <= MIN_TAU * 1.01:
                        v = _leg_value_at_expiry(leg, S)
                    else:
                        v = _leg_value_model(leg, S, rem, rate, div, sh)
                    total += _sign(leg) * float(v[0]) * _units(leg)
                row["pnl"].append(round(total - cost, 2))
            scen.append(row)

    breakevens = _roots(grid, at_expiry)
    return {
        "available": True,
        "spot": spot,
        "legs": leg_rows,
        "entry": entry,
        "breakevens_at_expiry": breakevens,
        "max_profit": None if profit_unbounded else round(max_profit, 2),
        "max_profit_unbounded": profit_unbounded,
        "max_loss": None if loss_unbounded else round(max_loss, 2),
        "max_loss_unbounded": loss_unbounded,
        "bounds_note": ("Within the drawn price range: the later leg's value is a model estimate, so the "
                        "true extremes depend on volatility then." if calendar else None),
        "greeks": {"delta_shares": round(agg["delta"], 1), "gamma_per_dollar": round(agg["gamma"], 3),
                   "theta_per_day": round(agg["theta"], 2), "vega_per_vol_pt": round(agg["vega"], 2)},
        "curves": {
            "price": [round(float(x), 2) for x in grid],
            "at_expiry": [round(float(v), 2) for v in at_expiry],
            "today": [round(float(v), 2) for v in today],
            "halfway": [round(float(v), 2) for v in half],
        },
        "first_expiry_days": round(first_tau * 365.0, 2),
        "calendar": calendar,
        "scenarios": {"moves_pct": [int(m * 100) for m in moves], "rows": scen},
        "assumptions": [
            "P/L is per position in dollars, from the mid entry; the entry block shows the natural price and a slippage-and-fees price.",
            ("Payoff at expiry is exact given the entry price; values before expiry are American-exercise "
             "estimates (Barone-Adesi-Whaley) at each leg's current IV, held fixed as price moves; greeks are "
             "Black-Scholes at that IV." if american else
             "Payoff at expiry is exact given the entry price; values before expiry are Black-Scholes estimates at each leg's current IV, held fixed as price moves."),
            ("American exercise: a long leg's value includes the right to exercise early, but whether a short "
             "leg is assigned early is the holder's choice and is not predicted; see the flags." if american else
             "European exercise (cash-settled index options): no early assignment."),
            "Rate {:.2%}, dividend yield {:.2%}, continuous.".format(rate, div),
            "Max loss is not your broker's margin requirement, which follows its own rules.",
        ] + (["Legs expire on different dates: 'at expiry' is the first expiry, with later legs valued by the model."] if calendar else []),
    }


def _public(leg: Dict[str, Any]) -> Dict[str, Any]:
    keep = ("type", "side", "qty", "strike", "expiry", "mid", "bid", "ask", "contract")
    out = {k: leg.get(k) for k in keep if k in leg}
    if leg.get("iv") is not None:
        out["iv_pct"] = round(float(leg["iv"]) * 100, 2)
    return out
