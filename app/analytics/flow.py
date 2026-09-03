"""Call vs put flow, reconstructed from volume / open interest.

HONESTY NOTE: free data has no trade tape, so there is no true bid/ask side per
print and therefore no real "bought vs sold" classification. Everything here is
a documented *proxy*:

  * call/put volume + premium ratios (directional appetite today)
  * volume vs open interest (volume > OI means the position is new, not a close)
  * premium-weighted skew (a $5m call sweep matters more than 10k pennies)
  * OTM-vs-ITM split (OTM call buying = speculation, ITM put = hedging/assignment)
  * per-strike net premium heatmap (where the money actually went)

Each field is labeled so a proxy never gets read as a tape.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


def _safe_ratio(numer: float, denom: float) -> Optional[float]:
    if denom is None or denom == 0 or not np.isfinite(denom):
        return None
    return round(float(numer) / float(denom), 4)


def _f(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(out) else out


def analyse(chain: pd.DataFrame, spot: float, top_n: int = 12) -> Dict[str, Any]:
    """Flow proxy for a (already expiry-filtered) normalized chain."""
    if chain is None or chain.empty:
        return {"error": "empty options chain"}

    df = chain.copy()
    df["volume"] = df["volume"].fillna(0.0)
    df["open_interest"] = df["open_interest"].fillna(0.0)
    df["price_used"] = df["mid"].fillna(df["last"]).fillna(0.0)
    df["premium"] = df["volume"] * 100.0 * df["price_used"]
    df["notional"] = df["volume"] * 100.0 * df["strike"]

    calls = df[df["is_call"]]
    puts = df[~df["is_call"]]

    call_vol = float(calls["volume"].sum())
    put_vol = float(puts["volume"].sum())
    call_oi = float(calls["open_interest"].sum())
    put_oi = float(puts["open_interest"].sum())
    call_prem = float(calls["premium"].sum())
    put_prem = float(puts["premium"].sum())

    total_vol = call_vol + put_vol
    total_prem = call_prem + put_prem

    # --- new-position detection: contracts whose day volume exceeds standing OI
    new_pos = df[(df["volume"] > df["open_interest"]) & (df["volume"] > 0)]
    new_call_prem = float(new_pos.loc[new_pos["is_call"], "premium"].sum())
    new_put_prem = float(new_pos.loc[~new_pos["is_call"], "premium"].sum())

    # --- moneyness split
    otm_calls = calls[calls["strike"] > spot]
    otm_puts = puts[puts["strike"] < spot]
    otm_call_prem = float(otm_calls["premium"].sum())
    otm_put_prem = float(otm_puts["premium"].sum())

    # --- unusual activity: high volume relative to its own OI and big premium
    unusual = df[(df["volume"] >= 50) & (df["premium"] >= 25_000)].copy()
    unusual["vol_oi_ratio"] = unusual["volume"] / unusual["open_interest"].replace(0.0, np.nan)
    unusual = unusual.sort_values("premium", ascending=False).head(top_n)

    # --- per-strike net premium (calls positive, puts negative)
    df["signed_premium"] = np.where(df["is_call"], df["premium"], -df["premium"])
    strike_flow = (
        df.groupby("strike")
        .agg(
            call_premium=("premium", lambda s: float(s[df.loc[s.index, "is_call"]].sum())),
            put_premium=("premium", lambda s: float(s[~df.loc[s.index, "is_call"]].sum())),
            net_premium=("signed_premium", "sum"),
            call_volume=("volume", lambda s: float(s[df.loc[s.index, "is_call"]].sum())),
            put_volume=("volume", lambda s: float(s[~df.loc[s.index, "is_call"]].sum())),
        )
        .reset_index()
    )
    strike_flow["gross"] = strike_flow["call_premium"] + strike_flow["put_premium"]
    top_strikes = strike_flow.nlargest(top_n, "gross").sort_values("strike")

    # --- IV skew: 25-delta-ish proxy using nearest OTM contracts either side
    call_iv = _f(otm_calls.nsmallest(5, "strike")["iv"].median()) if not otm_calls.empty else None
    put_iv = _f(otm_puts.nlargest(5, "strike")["iv"].median()) if not otm_puts.empty else None
    skew = None
    if call_iv is not None and put_iv is not None:
        skew = round((put_iv - call_iv) * 100.0, 3)

    # --- composite flow score, -100 (put-dominant) .. +100 (call-dominant)
    score = 0.0
    notes: List[str] = []

    pcr_vol = _safe_ratio(put_vol, call_vol)
    if pcr_vol is not None:
        if pcr_vol < 0.6:
            score += 30
            notes.append("Put/call volume {:.2f}. Heavy call skew".format(pcr_vol))
        elif pcr_vol < 0.9:
            score += 15
            notes.append("Put/call volume {:.2f}. Mild call lean".format(pcr_vol))
        elif pcr_vol > 1.4:
            score -= 30
            notes.append("Put/call volume {:.2f}. Heavy put skew".format(pcr_vol))
        elif pcr_vol > 1.1:
            score -= 15
            notes.append("Put/call volume {:.2f}. Mild put lean".format(pcr_vol))
        else:
            notes.append("Put/call volume {:.2f}. Balanced".format(pcr_vol))

    prem_share = _safe_ratio(call_prem, total_prem)
    if prem_share is not None:
        if prem_share > 0.65:
            score += 25
            notes.append("{:.0f}% of premium spent on calls".format(prem_share * 100))
        elif prem_share < 0.35:
            score -= 25
            notes.append("{:.0f}% of premium spent on puts".format((1 - prem_share) * 100))

    new_total = new_call_prem + new_put_prem
    if new_total > 0:
        new_share = new_call_prem / new_total
        if new_share > 0.6:
            score += 20
            notes.append("New positions skew call-side ({:.0f}%)".format(new_share * 100))
        elif new_share < 0.4:
            score -= 20
            notes.append("New positions skew put-side ({:.0f}%)".format((1 - new_share) * 100))

    otm_total = otm_call_prem + otm_put_prem
    if otm_total > 0:
        otm_share = otm_call_prem / otm_total
        if otm_share > 0.6:
            score += 15
            notes.append("OTM premium favors upside speculation")
        elif otm_share < 0.4:
            score -= 15
            notes.append("OTM premium favors downside protection")

    if skew is not None:
        if skew > 8:
            score -= 10
            notes.append("Put IV richer than call IV by {:.1f} vol pts (fear bid)".format(skew))
        elif skew < -2:
            score += 10
            notes.append("Call IV richer than put IV by {:.1f} vol pts (chase bid)".format(-skew))

    score = float(np.clip(score, -100, 100))
    if score >= 35:
        stance = "bullish"
    elif score >= 12:
        stance = "leaning bullish"
    elif score <= -35:
        stance = "bearish"
    elif score <= -12:
        stance = "leaning bearish"
    else:
        stance = "neutral"

    return {
        "method": "Volume/OI proxy. No trade tape on free data, side is inferred not observed",
        "stance": stance,
        "flow_score": score,
        "notes": notes,
        "volume": {
            "calls": call_vol,
            "puts": put_vol,
            "total": total_vol,
            "put_call_ratio": pcr_vol,
            "call_share_pct": None if not total_vol else round(call_vol / total_vol * 100.0, 2),
        },
        "open_interest": {
            "calls": call_oi,
            "puts": put_oi,
            "put_call_ratio": _safe_ratio(put_oi, call_oi),
        },
        "premium": {
            "calls": call_prem,
            "puts": put_prem,
            "total": total_prem,
            "call_share_pct": None if not total_prem else round(call_prem / total_prem * 100.0, 2),
            "net": call_prem - put_prem,
        },
        "new_positions": {
            "definition": "contracts where today's volume exceeded standing open interest",
            "call_premium": new_call_prem,
            "put_premium": new_put_prem,
            "contract_count": int(len(new_pos)),
            "call_share_pct": None if not new_total else round(new_call_prem / new_total * 100.0, 2),
        },
        "moneyness": {
            "otm_call_premium": otm_call_prem,
            "otm_put_premium": otm_put_prem,
            "itm_call_premium": float(calls[calls["strike"] <= spot]["premium"].sum()),
            "itm_put_premium": float(puts[puts["strike"] >= spot]["premium"].sum()),
        },
        "iv_skew": {
            "otm_call_iv": call_iv,
            "otm_put_iv": put_iv,
            "put_minus_call_vol_pts": skew,
        },
        "by_strike": [
            {
                "strike": float(r["strike"]),
                "call_premium": _f(r["call_premium"]),
                "put_premium": _f(r["put_premium"]),
                "net_premium": _f(r["net_premium"]),
                "call_volume": _f(r["call_volume"]),
                "put_volume": _f(r["put_volume"]),
            }
            for _, r in top_strikes.iterrows()
        ],
        "unusual": [
            {
                "contract": r.get("contract"),
                "type": "CALL" if r["is_call"] else "PUT",
                "strike": float(r["strike"]),
                "expiry": r.get("expiry"),
                "dte": _f(r.get("dte")),
                "volume": _f(r["volume"]),
                "open_interest": _f(r["open_interest"]),
                "vol_oi_ratio": _f(r.get("vol_oi_ratio")),
                "premium": _f(r["premium"]),
                "iv": _f(r["iv"]),
                "is_new_position": bool(r["volume"] > r["open_interest"]),
                "moneyness": "OTM"
                if (r["is_call"] and r["strike"] > spot) or ((not r["is_call"]) and r["strike"] < spot)
                else "ITM",
            }
            for _, r in unusual.iterrows()
        ],
    }
