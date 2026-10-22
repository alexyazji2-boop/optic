"""Contract picker: up to three contracts that fit a stated plan, or none.

The reader says what they think (up or down), how long they mean to hold, the
most premium they will put at risk, and optionally a target, an invalidation
and whether they mean to hold through the next report. This narrows the chain
to contracts that fit those constraints and can be traded on the quotes the
feed shows, ranks them by a **fit score**, and explains each one.

The fit score is how well a contract matches the stated plan and how tradable
its quote looks. It is not a chance of profit, and nothing here forecasts the
stock: the scenarios are the model's value of the contract under stated moves,
not predictions of which move happens.

Everything is read from the same inputs as the rest of the Options page:
contracts.table for cost, breakeven, greeks and the liquidity grade, contracts
.events for what happens before an expiry, and position's pricing for values
before expiry, so the picker cannot disagree with the research table or the
position builder about any figure.
"""

from __future__ import annotations

import math
import re
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from . import contracts as contracts_mod
from . import position as position_mod
from .quotes import NOT_A_FILL, OI_CAVEAT

# Delta band for a single bought option on a directional view. Below 0.25 the
# contract mostly needs a large move to pay; above 0.80 it is close to owning the
# stock with more capital tied up. A band, stated, not a "right" delta.
DELTA_LO, DELTA_HI = 0.25, 0.80
# The expiry should outlast the plan: the last week before expiry is where time
# decay and sensitivity to the stock speed up most.
EXPIRY_BUFFER_DAYS = 7
MAX_PICKS = 3
# Grades a pick may have. "Wide" (over 25% of the mid) and no usable quote are out.
TRADABLE = ("good", "fair")
# Scenario sizes, stated with the result
VOL_CRUSH_EVENT = 0.30     # implied volatility falls by 30% of itself after a report held through
VOL_CRUSH = 0.20           # otherwise a 20% fall in implied volatility

FIT_NOTE = ("The fit score is how well the contract matches your plan (expiry against your holding "
            "period, cost against your limit, sensitivity to the stock) and how tradable its quote looks. "
            "It is not a chance of profit.")
MODEL_NOTE = ("Values before expiry are Black-Scholes (or its American approximation for stock options) at "
              "the contract's own implied volatility, the risk-free rate and the dividend yield, valued at the "
              "mid. They are what the model says the contract would be worth, not prices anyone has offered.")


def _f(x: Any, digits: int = 2) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return round(v, digits) if math.isfinite(v) else None


def _root(contract: Optional[str]) -> Optional[str]:
    m = re.match(r"^([A-Z.]+?)(\d*)(\d{6})[CP]\d{8}$", str(contract or ""))
    return (m.group(1) + m.group(2)) if m else None


def is_adjusted(contract: Optional[str], ticker: str) -> bool:
    """An adjusted contract (after a split, merger or special dividend) trades under
    a changed root such as AAPL1, and its deliverable is not 100 shares. The feed
    gives no deliverable, so such a contract cannot be priced or sized here."""
    root = _root(contract)
    return bool(root) and root.replace(".", "") != ticker.upper().replace(".", "").replace("-", "")


def _value(row: Dict[str, Any], S: float, tau: float, rate: float, div: float,
           iv_shift: float = 0.0, american: bool = False) -> float:
    leg = {"type": row["type"], "strike": row["strike"], "iv": (row["iv_pct"] or 0.0) / 100.0,
           "american": american}
    return float(position_mod._leg_value_model(leg, np.array([S]), tau, rate, div, iv_shift)[0])


def _payoff(row: Dict[str, Any], S: float) -> float:
    return float(position_mod._leg_value_at_expiry({"type": row["type"], "strike": row["strike"]},
                                                   np.array([S]))[0])


def _scenarios(row, spot, plan, rate, div, american, event_in_hold) -> Dict[str, Any]:
    """Model value at the planned exit date, and the payoff at expiry, per contract, against
    the price paid at the ask (what an order is likelier to pay than the mid)."""
    paid = row["ask"] * contracts_mod.MULT
    hold = plan["hold_days"]
    tau_exit = max((row["dte"] - hold) / 365.0, 0.0)
    iv = (row["iv_pct"] or 0.0) / 100.0
    bull = plan["thesis"] == "bull"
    one_sd = spot * iv * math.sqrt(max(hold, 1) / 365.0)
    adverse = plan.get("invalidation") or (spot - one_sd if bull else spot + one_sd)
    target = plan.get("target")
    crush = VOL_CRUSH_EVENT if event_in_hold else VOL_CRUSH

    def at_exit(S, shift=0.0, label="", why=""):
        v = _value(row, S, tau_exit, rate, div, shift, american) * contracts_mod.MULT
        return {"label": label, "why": why, "underlying": _f(S), "value": _f(v, 0),
                "pnl": _f(v - paid, 0), "pnl_pct": _f((v / paid - 1) * 100, 0) if paid else None}

    exit_rows = []
    if target:
        exit_rows.append(at_exit(target, 0.0, "Stock at your target", "The stock reaches {:,.2f} by your exit.".format(target)))
    exit_rows.append(at_exit(spot, 0.0, "Stock unchanged",
                             "Only time passes: {} days of decay.".format(hold)))
    exit_rows.append(at_exit(adverse, 0.0, "Stock moves against you",
                             "To your invalidation, {:,.2f}.".format(adverse) if plan.get("invalidation") else
                             "About one standard deviation against you over {} days at today's implied volatility, to {:,.2f}.".format(hold, adverse)))
    exit_rows.append(at_exit(spot, -iv * crush, "Implied volatility falls",
                             ("The stock is unchanged and implied volatility falls {:.0f}% after the report you "
                              "plan to hold through.".format(crush * 100)) if event_in_hold else
                             "The stock is unchanged and implied volatility falls {:.0f}%.".format(crush * 100)))
    expiry_rows = []
    for S, label in ([(target, "At your target")] if target else []) + [(spot, "Unchanged"), (adverse, "Against you")]:
        v = _payoff(row, S) * contracts_mod.MULT
        expiry_rows.append({"label": label, "underlying": _f(S), "value": _f(v, 0), "pnl": _f(v - paid, 0)})
    return {"exit_date_days": hold, "paid": _f(paid, 0), "before_expiry": exit_rows,
            "at_expiry": expiry_rows, "vol_drop_pct": _f(crush * 100, 0)}


def _fit(row, plan) -> Dict[str, Any]:
    """0 to 100, from four parts, each stated."""
    hold = plan["hold_days"]
    slack = row["dte"] - hold
    # expiry: best a week to about the holding period past the plan; less credit further out
    exp_pts = 30.0 if EXPIRY_BUFFER_DAYS <= slack <= max(hold, 21) else max(0.0, 30.0 - (slack - max(hold, 21)) * 0.4)
    sp = row.get("spread_pct") or 25.0
    spread_pts = max(0.0, 30.0 * (1 - sp / 25.0))
    oi = row.get("open_interest") or 0
    act_pts = min(20.0, 20.0 * math.log10(1 + oi) / 3.0)          # 1,000 open contracts earns full marks
    d = abs(row.get("delta") or 0)
    delta_pts = max(0.0, 20.0 * (1 - abs(d - 0.5) / 0.3))
    if plan.get("target") and row.get("breakeven_ask"):
        be, tgt = row["breakeven_ask"], plan["target"]
        reaches = be <= tgt if plan["thesis"] == "bull" else be >= tgt
        if not reaches:
            delta_pts = 0.0
    total = exp_pts + spread_pts + act_pts + delta_pts
    return {"score": _f(total, 0), "parts": {"expiry": _f(exp_pts, 0), "spread": _f(spread_pts, 0),
                                              "activity": _f(act_pts, 0), "sensitivity": _f(delta_pts, 0)}}


def _why(row, plan, kind: str) -> Dict[str, str]:
    hold = plan["hold_days"]
    d = abs(row.get("delta") or 0)
    after = row["dte"] - hold
    fit = ("Costs ${:,.0f} at the ask, inside your ${:,.0f} limit; expires {} days after your planned exit; "
           "moves about ${:,.0f} for each $1 in the stock today (delta {:.2f}).".format(
               row["ask"] * 100, plan["max_premium"], after, d * 100, d))
    if d >= 0.6:
        trade = "In the money: it costs more and loses less to time each day, and behaves more like the stock."
    elif d < 0.4:
        trade = ("Out of the money: cheaper, but it needs the stock to move to {} by expiry just to break even, "
                 "and most of its price is time value that decays if the stock stalls.".format(_f(row["breakeven_ask"])))
    else:
        trade = "Near the money: a balance of cost and sensitivity, and the most time value to lose if the stock stalls."
    if kind == "longer":
        trade += " The longer expiry costs more but decays more slowly over your holding period."
    return {"fit": fit, "tradeoff": trade}


def pick(frames: Dict[str, pd.DataFrame], spot: float, rate: float, div: float, plan: Dict[str, Any],
         today: date, earnings: Optional[str], earnings_timing: Optional[str], ticker: str,
         american: bool = False, ex_dividend: Optional[str] = None) -> Dict[str, Any]:
    """frames: expiry -> the chain frame at that expiry (main._options_frame's)."""
    side = "call" if plan["thesis"] == "bull" else "put"
    hold = int(plan["hold_days"])
    exit_day = today + timedelta(days=hold)
    ed = pd.Timestamp(earnings).date() if earnings else None
    event_in_hold = bool(ed and today <= ed <= exit_day)
    considered, out = 0, []
    reasons = {"expiry_too_soon": 0, "adjusted": 0, "no_quote": 0, "wide_spread": 0,
               "over_budget": 0, "delta": 0, "event": 0}
    for exp, frame in frames.items():
        tbl = contracts_mod.table(frame, spot, rate, div, side=side, expiry=exp, include_unquoted=True,
                                  american=american)
        for r in tbl["rows"]:
            considered += 1
            if r["dte"] < hold + EXPIRY_BUFFER_DAYS:
                reasons["expiry_too_soon"] += 1; continue
            if is_adjusted(r.get("contract"), ticker):
                reasons["adjusted"] += 1; continue
            if r["quote_state"] != "two_sided" or not r.get("ask"):
                reasons["no_quote"] += 1; continue
            if (r.get("liquidity") or {}).get("grade") not in TRADABLE:
                reasons["wide_spread"] += 1; continue
            if r["ask"] * contracts_mod.MULT > plan["max_premium"]:
                reasons["over_budget"] += 1; continue
            if not DELTA_LO <= abs(r.get("delta") or 0) <= DELTA_HI:
                reasons["delta"] += 1; continue
            evs = contracts_mod.events(exp, today, earnings, earnings_timing, ex_dividend)
            report_before_expiry = any(e["kind"] == "earnings" for e in evs)
            if event_in_hold and not plan.get("through_event"):
                # the plan says exit before the report, but the report falls inside the holding period
                reasons["event"] += 1; continue
            out.append({**r, "fit": _fit(r, plan), "events": evs,
                        "report_before_expiry": report_before_expiry})
    out.sort(key=lambda r: -(r["fit"]["score"] or 0))
    # The best fit, then the best that differs in sensitivity (a cheaper or a costlier strike, so the
    # cost-against-move tradeoff is visible), then the best at another expiry. Never padded: a third
    # pick that only repeats the first two is left out. Three 350 calls at three expiries was the first
    # version's answer for AAPL, which hid the choice a reader most needs to see.
    def far(r, picks, dd, other_expiry):
        return all(abs(abs(p["delta"]) - abs(r["delta"])) >= dd and (not other_expiry or p["expiry"] != r["expiry"])
                   for p in picks)
    chosen: List[Dict[str, Any]] = out[:1]
    for dd, other in ((0.15, False), (0.05, True)):
        nxt = next((r for r in out if r not in chosen and far(r, chosen, dd, other)), None)
        if nxt is not None and len(chosen) < MAX_PICKS:
            chosen.append(nxt)
    picks: List[Dict[str, Any]] = []
    for r in chosen:
        kind = "longer" if picks and r["dte"] > max(p["dte"] for p in picks) else ""
        picks.append({**r, "why": _why(r, plan, kind),
                      "scenarios": _scenarios(r, spot, plan, rate, div, american, event_in_hold and plan.get("through_event")),
                      "multiplier": contracts_mod.MULT, "multiplier_basis": "standard contract, 100 shares"})
    why_none = None
    if not picks:
        parts = {"expiry_too_soon": "expire too soon for your holding period plus a week",
                 "adjusted": "are adjusted contracts whose deliverable the feed does not give",
                 "no_quote": "have no two-sided quote", "wide_spread": "have a spread wider than 25% of the mid",
                 "over_budget": "cost more than your limit at the ask",
                 "delta": "sit outside a 0.25 to 0.80 delta",
                 "event": "would be held through the report on {} that your plan exits before".format(earnings)}
        why_none = "None of the {} {}s considered fits: {}.".format(
            considered, side, "; ".join("{} {}".format(n, parts[k]) for k, n in reasons.items() if n) or "none were listed")
    # The one reason a reader can act on straight away, said first: the plan and the calendar disagree
    conflict = None
    if event_in_hold and not plan.get("through_event"):
        before = (ed - today).days - 1
        conflict = ("The {} earnings report falls inside your {}-day hold. Either say you mean to hold through "
                    "it, or plan a hold of {} or fewer.".format(
                        ed.isoformat(), hold, "{} days".format(before) if before >= 1 else "less than a day"))
    return {
        "available": True, "side": side, "plan": plan, "spot": _f(spot),
        "event_in_hold": event_in_hold, "earnings": earnings, "exit_date": exit_day.isoformat(),
        # No date from the feed is not "no report": say it was not checked (seen 2026-10-22, when Yahoo
        # answered the chain but not the calendar and AAPL's Nov 2 report went unflagged)
        "earnings_note": None if earnings else ("The feed gave no next earnings date just now, so whether a report "
                                                "falls inside your hold or before an expiry was not checked."),
        "considered": considered, "eligible": len(out), "excluded": reasons,
        "picks": picks, "why_none": why_none, "conflict": conflict,
        "rules": ("Calls for a rising view, puts for a falling one; an expiry at least {} days after your planned "
                  "exit; a two-sided quote with a spread within 25% of the mid; a cost at the ask within your "
                  "limit; a delta between {:.2f} and {:.2f}; standard 100-share contracts only; and, if your plan "
                  "exits before the next report, no holding period that contains it.".format(
                      EXPIRY_BUFFER_DAYS, DELTA_LO, DELTA_HI)),
        "fit_note": FIT_NOTE, "model_note": MODEL_NOTE, "fill_note": NOT_A_FILL, "oi_note": OI_CAVEAT,
    }
