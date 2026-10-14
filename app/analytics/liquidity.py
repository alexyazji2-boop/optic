"""How tradable a contract looks on screen, from what a free chain carries.

What the chain has: bid, ask, last trade and its time, the session's volume and
the previous session's open interest. What it does not have, and so what no
grade here can say: quote size (how many contracts are bid or offered),
the quote's own timestamp, other exchanges' quotes, or the complex order book
where a multi-leg order can fill inside the legs' combined spread.

So the grade is about the cost of crossing the quoted spread and about how
active the contract is, never about a fill: a mid is an estimate between two
quotes, not a price anyone has promised, and volume or open interest say a
contract is used, not that the next order fills well.

Thresholds are defaults, passed in and returned with every grade, so a reader
or a caller can change them and see what moved.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

DEFAULTS = {
    "tight_spread_pct": 5.0,     # of the mid
    "fair_spread_pct": 10.0,
    "wide_spread_pct": 25.0,
    "tight_spread_abs": 0.05,    # dollars: a nickel on a cheap contract is tight whatever the %
    "min_oi": 100,
    "good_oi": 500,
}

GRADES = ("good", "fair", "poor", "not_tradable")
LABELS = {"good": "Tight", "fair": "Fair", "poor": "Wide", "not_tradable": "No usable quote"}


def grade_row(row: Dict[str, Any], th: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    th = {**DEFAULTS, **(th or {})}
    reasons: List[str] = []
    state = row.get("quote_state") or "no_quote"
    oi = float(row.get("open_interest") or 0)
    vol = float(row.get("volume") or 0)
    sp = row.get("spread_pct")
    sa = row.get("spread_abs")
    mid = row.get("quote_mid")
    if state != "two_sided":
        reasons.append({
            "no_quote": "No bid and no ask on the feed.",
            "no_bid": "No bid: nobody is quoted to buy it, so there is no price to sell at.",
            "no_ask": "No ask: nobody is quoted to sell it.",
            "locked": "Bid equals ask, which on a delayed feed usually means one side is stale.",
            "crossed": "Bid above ask: a stale or mismatched quote, not a real market.",
        }.get(state, "No usable quote."))
        grade = "not_tradable"
    else:
        sp = float(sp) if sp is not None and np.isfinite(sp) else None
        sa = float(sa) if sa is not None and np.isfinite(sa) else None
        tight_abs = sa is not None and sa <= th["tight_spread_abs"] + 1e-9
        if sp is None:
            grade = "poor"
        elif sp <= th["tight_spread_pct"] or tight_abs:
            grade = "good"
        elif sp <= th["fair_spread_pct"]:
            grade = "fair"
        elif sp <= th["wide_spread_pct"]:
            grade = "poor"
        else:
            grade = "not_tradable"
            reasons.append("The spread is {:.0f}% of the mid: crossing it costs more than most moves "
                           "would pay.".format(sp))
        if sp is not None and grade in ("fair", "poor"):
            reasons.append("Spread {:.1f}% of the mid (${:.2f}).".format(sp, sa or 0))
        if oi < th["min_oi"]:
            reasons.append("Open interest {:,.0f}: few contracts open.".format(oi))
            if grade == "good":
                grade = "fair"
        elif oi < th["good_oi"] and grade == "good":
            grade = "fair"
            reasons.append("Open interest {:,.0f}: active, not deep.".format(oi))
        if vol <= 0:
            reasons.append("No trades in the session the feed reports.")
            if grade == "good":
                grade = "fair"
    age = row.get("last_trade_age_h")
    if age is not None and np.isfinite(age) and age > 30:
        reasons.append("The last trade was {:.0f} hours ago, so 'last' is not a current price.".format(age))
    cost = None
    if state == "two_sided" and sa is not None and mid:
        # Buying at the ask and later selling at the bid crosses the whole spread.
        cost = {"per_contract": round(float(sa) * 100.0, 2), "pct_of_mid": round(float(sa) / float(mid) * 100.0, 1)}
    return {"grade": grade, "label": LABELS[grade], "reasons": reasons, "round_trip_cost": cost}


def grade_frame(df: pd.DataFrame, th: Optional[Dict[str, float]] = None) -> List[Dict[str, Any]]:
    cols = ["quote_state", "open_interest", "volume", "spread_pct", "spread_abs", "quote_mid", "last_trade_age_h"]
    sub = df[[c for c in cols if c in df.columns]]
    return [grade_row(r, th) for r in sub.to_dict("records")]


def method(th: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    th = {**DEFAULTS, **(th or {})}
    return {
        "thresholds": th,
        "text": ("Tight: a two-sided quote with a spread of at most {tight_spread_pct:.0f}% of the mid "
                 "(or ${tight_spread_abs:.2f}), open interest of {good_oi:,.0f} or more and trades this "
                 "session. Fair: up to {fair_spread_pct:.0f}%, or thinner open interest. Wide: up to "
                 "{wide_spread_pct:.0f}%. No usable quote: one side missing, locked, crossed, or wider "
                 "than {wide_spread_pct:.0f}%.").format(**th),
        "cannot_see": ["quote size (how many contracts are bid or offered)",
                       "the quote's own timestamp",
                       "the complex order book, where a spread order can fill inside its legs"],
        "mid_note": "A mid is an estimate between two quotes, not a price anyone has promised.",
    }
