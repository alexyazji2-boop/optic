"""Dedicated delta and gamma panels.

GEX answers "what must dealers hedge?" under its stated assumption about who
holds which side (app/analytics/gex.py). This answers "what is the chain itself
made of?" — where delta and gamma sit by strike and expiry, what the at-the-money
contracts actually cost in theta, and where the gamma is concentrated enough to
matter for a swing entry.

**Nothing here is signed by position.** Every contract has a buyer and a seller,
so the delta and gamma of open interest belong to both sides at once. The
figures below count each open contract as if held long, which describes how
much delta and gamma the chain carries and where, and says nothing about who is
long it. Readings that need a side are the GEX panel's, and say so.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


def _f(value: Any, digits: int = 4) -> Optional[float]:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(out) else round(out, digits)


def _atm_row(frame: pd.DataFrame, spot: float, is_call: bool, expiry: str):
    side = frame[(frame["is_call"] == is_call) & (frame["expiry"] == expiry)]
    if side.empty:
        return None
    return side.iloc[(side["strike"] - spot).abs().argsort().iloc[0]]


def analyse(frame: pd.DataFrame, spot: float, top_n: int = 16) -> Dict[str, Any]:
    """``frame`` is the exposure frame produced by gex.compute_exposure."""
    if frame is None or frame.empty:
        return {"error": "no chain data"}

    calls = frame[frame["is_call"]]
    puts = frame[~frame["is_call"]]
    oi = frame["open_interest"].fillna(0.0)

    # ------------------------------------------------------------- delta
    # Open-interest-weighted delta: the net directional bet standing in the
    # chain, in share-equivalents.
    call_share_delta = float((calls["delta"] * calls["open_interest"]).sum() * 100.0)
    put_share_delta = float((puts["delta"] * puts["open_interest"]).sum() * 100.0)

    total_oi = float(oi.sum())
    weighted_call_delta = (
        float((calls["delta"] * calls["open_interest"]).sum() / max(calls["open_interest"].sum(), 1))
    )
    weighted_put_delta = (
        float((puts["delta"] * puts["open_interest"]).sum() / max(puts["open_interest"].sum(), 1))
    )

    by_strike = (
        frame.groupby("strike")
        .apply(
            lambda g: pd.Series(
                {
                    "call_delta_oi": float(
                        (g.loc[g["is_call"], "delta"] * g.loc[g["is_call"], "open_interest"]).sum()
                        * 100.0
                    ),
                    "put_delta_oi": float(
                        (g.loc[~g["is_call"], "delta"] * g.loc[~g["is_call"], "open_interest"]).sum()
                        * 100.0
                    ),
                    "call_gamma_oi": float(
                        (g.loc[g["is_call"], "gamma"] * g.loc[g["is_call"], "open_interest"]).sum()
                        * 100.0
                    ),
                    "put_gamma_oi": float(
                        (g.loc[~g["is_call"], "gamma"] * g.loc[~g["is_call"], "open_interest"]).sum()
                        * 100.0
                    ),
                    "total_oi": float(g["open_interest"].sum()),
                    "total_volume": float(g["volume"].sum()),
                    "avg_iv": float(g["iv"].mean()),
                },
            ),
            include_groups=False,
        )
        .reset_index()
    )
    by_strike["net_delta_oi"] = by_strike["call_delta_oi"] + by_strike["put_delta_oi"]
    by_strike["total_gamma_oi"] = by_strike["call_gamma_oi"] + by_strike["put_gamma_oi"]

    focus = by_strike.reindex(
        by_strike["total_gamma_oi"].abs().nlargest(top_n).index
    ).sort_values("strike")

    # -------------------------------------------------------- ATM greeks
    atm_rows: List[Dict[str, Any]] = []
    for expiry in sorted(frame["expiry"].unique()):
        call = _atm_row(frame, spot, True, expiry)
        put = _atm_row(frame, spot, False, expiry)
        if call is None and put is None:
            continue
        ref = call if call is not None else put
        entry: Dict[str, Any] = {"expiry": expiry, "dte": int(ref["dte"])}
        for label, row in (("call", call), ("put", put)):
            if row is None:
                continue
            premium = _f(row["mid"], 2) or 0.0
            entry[label] = {
                "strike": _f(row["strike"]),
                "delta": _f(row["delta"], 4),
                "gamma": _f(row["gamma"], 6),
                "vega": _f(row["vega"], 4),
                "theta_per_day": _f(row["theta"], 4),
                "iv": _f(row["iv"], 4),
                "mid": premium,
                "theta_pct_daily": _f(abs(float(row["theta"])) / premium * 100.0, 2)
                if premium
                else None,
                "open_interest": _f(row["open_interest"], 0),
                "volume": _f(row["volume"], 0),
            }
        atm_rows.append(entry)

    # ------------------------------------------------- gamma concentration
    gamma_by_expiry = (
        frame.assign(gamma_oi=frame["gamma"] * oi * 100.0)
        .groupby("expiry")
        .agg(gamma_oi=("gamma_oi", "sum"), dte=("dte", "first"), total_oi=("open_interest", "sum"))
        .reset_index()
        .sort_values("dte")
    )
    total_gamma = float(gamma_by_expiry["gamma_oi"].sum())

    peak = by_strike.loc[by_strike["total_gamma_oi"].idxmax()] if not by_strike.empty else None

    # Fraction of all gamma sitting within one ATR-ish band of spot: high
    # concentration means the pin is real and breakouts need force.
    near = by_strike[(by_strike["strike"] >= spot * 0.98) & (by_strike["strike"] <= spot * 1.02)]
    near_share = (
        _f(near["total_gamma_oi"].sum() / total_gamma * 100.0, 1) if total_gamma else None
    )

    net_share_delta = call_share_delta + put_share_delta
    # Calling the chain's lean a positioning lean was a claim open interest cannot support: every
    # contract open has a long side and a short side. Said as what it is, the
    # delta of the chain counted as if every contract were held long.
    delta_read = (
        "Counting every open contract as held long, calls carry {:,.0f} share-equivalents of "
        "delta and puts {:,.0f}, net {:,.0f}. Open interest does not say who is long or short, "
        "so this is the chain's size and lean, not anybody's position."
    ).format(call_share_delta, put_share_delta, net_share_delta)

    if near_share is not None and near_share > 35:
        # Whether concentrated gamma pins or sharpens moves depends on which
        # side holds it, which open interest does not show. The GEX panel reads
        # it under its stated assumption; this says only where it sits.
        gamma_read = (
            "{:.0f}% of chain gamma sits within 2% of spot, so hedging flows near here are large. "
            "Whether they dampen moves or add to them depends on the sign of dealer gamma, which "
            "the GEX panel reads under its assumption.".format(near_share)
        )
    elif near_share is not None and near_share < 15:
        gamma_read = (
            "Only {:.0f}% of chain gamma is near spot. Little pinning, so price can travel freely "
            "between levels.".format(near_share)
        )
    else:
        gamma_read = "Gamma is moderately distributed around spot. Normal hedging behavior."

    return {
        "spot": _f(spot),
        "delta": {
            "call_delta_shares": _f(call_share_delta, 0),
            "put_delta_shares": _f(put_share_delta, 0),
            "net_delta_shares": _f(net_share_delta, 0),
            "net_delta_notional": _f(net_share_delta * spot, 0),
            "oi_weighted_call_delta": _f(weighted_call_delta, 4),
            "oi_weighted_put_delta": _f(weighted_put_delta, 4),
            "total_open_interest": _f(total_oi, 0),
            "read": delta_read,
        },
        "gamma": {
            "total_gamma_oi": _f(total_gamma, 2),
            "peak_gamma_strike": _f(peak["strike"]) if peak is not None else None,
            "peak_gamma_distance_pct": _f((float(peak["strike"]) / spot - 1.0) * 100.0, 2)
            if peak is not None
            else None,
            "gamma_within_2pct_share": near_share,
            "read": gamma_read,
            "by_expiry": [
                {
                    "expiry": row["expiry"],
                    "dte": int(row["dte"]),
                    "gamma_oi": _f(row["gamma_oi"], 2),
                    "open_interest": _f(row["total_oi"], 0),
                    "share_pct": _f(row["gamma_oi"] / total_gamma * 100.0, 1) if total_gamma else None,
                }
                for _, row in gamma_by_expiry.iterrows()
            ],
        },
        "atm_greeks": atm_rows,
        "by_strike": [
            {
                "strike": _f(row["strike"]),
                "call_delta_oi": _f(row["call_delta_oi"], 0),
                "put_delta_oi": _f(row["put_delta_oi"], 0),
                "net_delta_oi": _f(row["net_delta_oi"], 0),
                "call_gamma_oi": _f(row["call_gamma_oi"], 2),
                "put_gamma_oi": _f(row["put_gamma_oi"], 2),
                "total_gamma_oi": _f(row["total_gamma_oi"], 2),
                "total_oi": _f(row["total_oi"], 0),
                "total_volume": _f(row["total_volume"], 0),
                "avg_iv": _f(row["avg_iv"], 4),
            }
            for _, row in focus.iterrows()
        ],
        "second_order": {
            "net_vanna": _f(float((frame["vanna"] * oi * 100.0).sum()), 2),
            "net_charm": _f(float((frame["charm"] * oi * 100.0).sum()), 2),
            "note": "Counted as if every contract were held long, in shares: vanna is how delta "
            "moves with implied volatility, charm how it decays with time. The dealer-signed "
            "versions, in dollars, are on the GEX and vanna panels.",
        },
    }
