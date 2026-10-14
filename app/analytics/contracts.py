"""Contract research: the chain as a table a reader can filter, not a pick.

"Which contracts fit my thesis and timeframe?" is answered with a list the
reader narrows by expiry, side, a delta range, the widest spread they will
accept and the least open interest. Nothing is ranked "best": there is no
universal right delta, and the research behind the common ranges (45 days,
16 to 30 delta) is practitioner testing without published costs or methods
(Options audit research, 2026-10-13). Each row carries what the choice turns
on: the cost at the ask and at the mid, the breakeven and the move it needs,
time decay and volatility exposure per contract, the model's chance of
finishing in the money, and the liquidity grade with its reasons.

**Delta is not a probability.** The model's chance of finishing in the money
is N(d2) for a call (N(-d2) for a put) under risk-neutral pricing, not delta
(N(d1)), and neither is a forecast: the stock's real drift and the skew are
not in it. Finishing in the money is also not making money: a bought option
has to clear its premium (the breakeven).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from scipy.special import ndtr

from app.analytics import american as american_mod

from . import liquidity as liq

MULT = 100.0


def _f(x: Any, digits: int = 4) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return round(v, digits) if np.isfinite(v) else None


def is_monthly(expiry: str) -> bool:
    """Standard monthly equity options expire on the third Friday (the
    Thursday before when that Friday is a market holiday)."""
    d = pd.Timestamp(expiry).date()
    if d.weekday() == 4:
        return 15 <= d.day <= 21
    if d.weekday() == 3:
        return 14 <= d.day <= 20 and (d + pd.Timedelta(days=1)).day in range(15, 22)
    return False


def table(frame: pd.DataFrame, spot: float, rate: float, div: float, *,
          side: str = "call", expiry: Optional[str] = None,
          delta_lo: float = 0.0, delta_hi: float = 1.0,
          max_spread_pct: Optional[float] = None, min_oi: float = 0.0,
          include_unquoted: bool = False,
          thresholds: Optional[Dict[str, float]] = None,
          american: bool = False) -> Dict[str, Any]:
    df = frame.copy()
    if expiry:
        df = df[df["expiry"] == expiry]
    df = df[df["is_call"] == (side == "call")]
    total = int(len(df))
    if df.empty:
        return {"rows": [], "total": 0, "shown": 0, "filtered_out": {}}
    tau = df["tau"].to_numpy(dtype=float)
    k = df["strike"].to_numpy(dtype=float)
    vol = np.maximum(df["iv"].to_numpy(dtype=float), 1e-4)
    d1 = (np.log(spot / k) + (rate - div + 0.5 * vol * vol) * tau) / (vol * np.sqrt(tau))
    d2 = d1 - vol * np.sqrt(tau)
    df["p_itm_model"] = ndtr(d2) if side == "call" else ndtr(-d2)
    # What the right to exercise early is worth at this IV, per contract: the
    # part of the price a European model misses (O2).
    df["_eep"] = (american_mod.early_exercise_premium(spot, k, tau, vol, rate, div, side == "call") * MULT
                  if american else np.zeros(len(df)))
    grades = liq.grade_frame(df, thresholds)
    df["_grade"] = [g["grade"] for g in grades]
    dropped = {"delta": 0, "spread": 0, "open_interest": 0, "unquoted": 0}
    keep = np.ones(len(df), dtype=bool)
    adelta = np.abs(df["delta"].to_numpy(dtype=float))
    m = (adelta >= delta_lo) & (adelta <= delta_hi)
    dropped["delta"] = int((keep & ~m).sum())
    keep &= m
    if not include_unquoted:
        m = (df["quote_state"] == "two_sided").to_numpy()
        dropped["unquoted"] = int((keep & ~m).sum())
        keep &= m
    if max_spread_pct is not None:
        sp = df["spread_pct"].to_numpy(dtype=float)
        m = np.where(np.isfinite(sp), sp <= max_spread_pct, include_unquoted)
        dropped["spread"] = int((keep & ~m).sum())
        keep &= m
    if min_oi:
        m = df["open_interest"].fillna(0).to_numpy(dtype=float) >= min_oi
        dropped["open_interest"] = int((keep & ~m).sum())
        keep &= m
    sel = df[keep]
    sel_grades = [g for g, k_ in zip(grades, keep) if k_]
    rows: List[Dict[str, Any]] = []
    for (_, r), g in zip(sel.iterrows(), sel_grades):
        ask = _f(r.get("ask"), 2) if r["quote_state"] == "two_sided" else None
        mid = _f(r.get("quote_mid"), 3)
        intrinsic = max(spot - r["strike"], 0.0) if side == "call" else max(r["strike"] - spot, 0.0)
        be_ask = (r["strike"] + ask if side == "call" else r["strike"] - ask) if ask else None
        be_mid = (r["strike"] + mid if side == "call" else r["strike"] - mid) if mid else None
        rows.append({
            "contract": r.get("contract"),
            "type": side,
            "expiry": r["expiry"],
            "dte": int(r["dte"]),
            "strike": float(r["strike"]),
            "moneyness_pct": _f((r["strike"] / spot - 1) * 100, 2),
            "bid": _f(r.get("bid"), 2), "ask": _f(r.get("ask"), 2), "mid": mid,
            "last": _f(r.get("last"), 2), "last_trade_age_h": _f(r.get("last_trade_age_h"), 1),
            "quote_state": r["quote_state"],
            "volume": _f(r.get("volume"), 0), "open_interest": _f(r.get("open_interest"), 0),
            "spread_abs": _f(r.get("spread_abs"), 2), "spread_pct": _f(r.get("spread_pct"), 1),
            "liquidity": g,
            "iv_pct": _f(r["iv"] * 100, 2), "iv_source": r.get("iv_source"),
            "delta": _f(r["delta"], 3), "gamma": _f(r["gamma"], 4),
            "theta_per_contract": _f(r["theta"] * MULT, 2),
            "vega_per_contract": _f(r["vega"] * MULT, 2),
            "p_itm_model": _f(r["p_itm_model"], 3),
            "intrinsic": _f(intrinsic, 2),
            "extrinsic_mid": _f(mid - intrinsic, 2) if mid is not None else None,
            "cost_ask_contract": _f(ask * MULT, 0) if ask else None,
            "cost_mid_contract": _f(mid * MULT, 0) if mid else None,
            "breakeven_ask": _f(be_ask, 2), "breakeven_mid": _f(be_mid, 2),
            "breakeven_move_pct": _f((be_ask / spot - 1) * 100, 2) if be_ask else None,
            "exercise": "american" if american else "european",
            "early_exercise_premium_contract": _f(r["_eep"], 2) if american else None,
        })
    rows.sort(key=lambda x: x["strike"])
    return {"rows": rows, "total": total, "shown": len(rows), "filtered_out": dropped}


def events(expiry: str, today: date, earnings: Optional[str], earnings_timing: Optional[str],
           ex_dividend: Optional[str], index_like: bool = False) -> List[Dict[str, Any]]:
    """What happens before this expiry that changes how its contracts behave."""
    out: List[Dict[str, Any]] = []
    exp = pd.Timestamp(expiry).date()
    if earnings:
        ed = pd.Timestamp(earnings).date()
        inside = today <= ed < exp or (ed == exp and earnings_timing == "before_open")
        if inside:
            out.append({"kind": "earnings", "date": earnings,
                        "text": "The company reports on {}{}, before this expiry. Its implied volatility "
                                "includes a price for that move and usually falls once the report is out, "
                                "whichever way the stock goes.".format(
                                    earnings, {"before_open": " before the open",
                                               "after_close": " after the close"}.get(earnings_timing or "", ""))})
    if ex_dividend:
        xd = pd.Timestamp(ex_dividend).date()
        if today <= xd <= exp:
            out.append({"kind": "ex_dividend", "date": ex_dividend,
                        "text": "The stock goes ex-dividend on {}. The price usually drops by about the "
                                "dividend that morning, and a short in-the-money call whose remaining "
                                "time value is below the dividend is at real risk of early assignment the "
                                "day before.".format(ex_dividend)})
    kind = "monthly" if is_monthly(expiry) else "weekly or other"
    settle = ("Index options here may be cash-settled and, for standard monthlies, settled on the "
              "opening print (AM); check the contract's specification." if index_like else
              "Equity and ETF options settle in shares and can be exercised early (American style). "
              "Contracts $0.01 or more in the money at the close are exercised automatically unless "
              "the holder says otherwise.")
    out.append({"kind": "expiry", "date": expiry,
                "text": "A {} expiry. Trading stops at 4:00pm ET that day. {}".format(kind, settle)})
    dte = (exp - today).days
    if dte <= 1:
        out.append({"kind": "short_dated", "date": expiry,
                    "text": "Expires within a day: value changes very fast with the stock (gamma) and "
                            "the clock (theta), and the open interest behind any positioning reading is "
                            "the previous session's, which misses same-day positions."})
    return out
