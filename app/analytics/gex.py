"""Dealer gamma / delta exposure (GEX / DEX) from an options chain.

SIGN CONVENTION (this matters, and every vendor picks their own):
we assume the dealer is *short* customer calls and *long* customer puts, the
standard retail-flow assumption. That gives

    call GEX = +gamma * OI * contract_multiplier * S^2 * 0.01
    put  GEX = -gamma * OI * contract_multiplier * S^2 * 0.01

so positive net GEX = dealers hedge *against* the move (vol suppression,
mean reversion, ranges hold) and negative net GEX = dealers hedge *with* the
move (vol expansion, trends extend, breakouts run). Every number returned is
"dollars of dealer delta that must be hedged per 1% move in spot".

The assumption is stated explicitly in the payload so it can be flipped rather
than silently believed.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from .greeks import greeks

CONTRACT_MULTIPLIER = 100.0


def _f(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(out) else out


def compute_exposure(chain: pd.DataFrame, spot: float, rate: float = 0.0, div: float = 0.0) -> pd.DataFrame:
    """Attach greeks and signed dollar exposures to a normalized chain frame.

    ``chain`` needs columns: strike, tau, iv, open_interest, volume, is_call.
    """
    df = chain.copy()
    g = greeks(
        spot,
        df["strike"].to_numpy(),
        df["tau"].to_numpy(),
        df["iv"].to_numpy(),
        rate=rate,
        div=div,
        is_call=df["is_call"].to_numpy(),
    )
    for name in ("delta", "gamma", "vega", "theta", "vanna", "charm"):
        df[name] = g[name]

    sign = np.where(df["is_call"].to_numpy(), 1.0, -1.0)
    oi = df["open_interest"].fillna(0.0).to_numpy()
    vol = df["volume"].fillna(0.0).to_numpy()

    # Gamma exposure in $ of dealer delta per 1% spot move.
    df["gex"] = sign * df["gamma"].to_numpy() * oi * CONTRACT_MULTIPLIER * spot * spot * 0.01
    df["gex_volume"] = sign * df["gamma"].to_numpy() * vol * CONTRACT_MULTIPLIER * spot * spot * 0.01

    # Delta exposure in $ notional of dealer hedge.
    df["dex"] = sign * df["delta"].to_numpy() * oi * CONTRACT_MULTIPLIER * spot

    # Vanna / charm exposure, the two flows that drive drift into opex.
    df["vex"] = sign * df["vanna"].to_numpy() * oi * CONTRACT_MULTIPLIER * spot
    df["cex"] = sign * df["charm"].to_numpy() * oi * CONTRACT_MULTIPLIER * spot

    df["notional_oi"] = oi * CONTRACT_MULTIPLIER * df["strike"].to_numpy()
    df["premium_traded"] = vol * CONTRACT_MULTIPLIER * df["mid"].fillna(df["last"]).fillna(0.0).to_numpy()
    return df


def _gamma_at_spot(df: pd.DataFrame, test_spot: float, rate: float, div: float) -> float:
    """Total signed dealer gamma exposure if spot were ``test_spot``.

    Re-pricing gamma at each candidate level (rather than scaling the current
    profile) is what makes the flip point meaningful — gamma migrates to
    whichever strikes are near the money.
    """
    g = greeks(
        test_spot,
        df["strike"].to_numpy(),
        df["tau"].to_numpy(),
        df["iv"].to_numpy(),
        rate=rate,
        div=div,
        is_call=df["is_call"].to_numpy(),
    )
    sign = np.where(df["is_call"].to_numpy(), 1.0, -1.0)
    oi = df["open_interest"].fillna(0.0).to_numpy()
    exposure = sign * g["gamma"] * oi * CONTRACT_MULTIPLIER * test_spot * test_spot * 0.01
    return float(np.nansum(exposure))


def gamma_profile(
    df: pd.DataFrame,
    spot: float,
    rate: float = 0.0,
    div: float = 0.0,
    span_pct: float = 0.12,
    steps: int = 61,
) -> Dict[str, Any]:
    """Net GEX as a function of spot, plus the zero-crossing (gamma flip)."""
    lo, hi = spot * (1 - span_pct), spot * (1 + span_pct)
    grid = np.linspace(lo, hi, steps)
    values = [_gamma_at_spot(df, float(s), rate, div) for s in grid]

    flip: Optional[float] = None
    for i in range(1, len(values)):
        a, b = values[i - 1], values[i]
        if np.isfinite(a) and np.isfinite(b) and a * b < 0:
            # Linear interpolation between the two bracketing grid points.
            weight = abs(a) / (abs(a) + abs(b))
            candidate = float(grid[i - 1] + weight * (grid[i] - grid[i - 1]))
            # Keep whichever crossing sits closest to spot.
            if flip is None or abs(candidate - spot) < abs(flip - spot):
                flip = candidate

    return {
        "spots": [round(float(s), 4) for s in grid],
        "net_gex": [_f(v) for v in values],
        "flip_point": None if flip is None else round(flip, 4),
        "flip_distance_pct": None if flip is None else round((flip / spot - 1.0) * 100.0, 3),
    }


def analyse(
    chain: pd.DataFrame,
    spot: float,
    rate: float = 0.0,
    div: float = 0.0,
    top_n: int = 14,
) -> Dict[str, Any]:
    """GEX/DEX analysis for the (already expiry-filtered) chain."""
    if chain is None or chain.empty:
        return {"error": "empty options chain"}

    df = compute_exposure(chain, spot, rate, div)

    by_strike = (
        df.groupby("strike")
        .agg(
            call_gex=("gex", lambda s: float(np.nansum(s[df.loc[s.index, "is_call"]]))),
            put_gex=("gex", lambda s: float(np.nansum(s[~df.loc[s.index, "is_call"]]))),
            net_gex=("gex", lambda s: float(np.nansum(s))),
            net_dex=("dex", lambda s: float(np.nansum(s))),
            call_oi=("open_interest", lambda s: float(np.nansum(s[df.loc[s.index, "is_call"]]))),
            put_oi=("open_interest", lambda s: float(np.nansum(s[~df.loc[s.index, "is_call"]]))),
            call_vol=("volume", lambda s: float(np.nansum(s[df.loc[s.index, "is_call"]]))),
            put_vol=("volume", lambda s: float(np.nansum(s[~df.loc[s.index, "is_call"]]))),
        )
        .reset_index()
    )
    by_strike["abs_gex"] = by_strike["net_gex"].abs()

    total_gex = float(np.nansum(df["gex"]))
    total_dex = float(np.nansum(df["dex"]))
    call_gex_total = float(np.nansum(df.loc[df["is_call"], "gex"]))
    put_gex_total = float(np.nansum(df.loc[~df["is_call"], "gex"]))

    profile = gamma_profile(df, spot, rate, div)

    # Walls: heaviest positive (call) and heaviest negative (put) gamma strikes.
    pos = by_strike[by_strike["net_gex"] > 0]
    neg = by_strike[by_strike["net_gex"] < 0]
    call_wall = pos.loc[pos["net_gex"].idxmax()] if not pos.empty else None
    put_wall = neg.loc[neg["net_gex"].idxmin()] if not neg.empty else None
    max_oi_strike = by_strike.loc[(by_strike["call_oi"] + by_strike["put_oi"]).idxmax()]

    # Absolute-gamma peak = the strike price is most magnetically pinned to.
    pin = by_strike.loc[by_strike["abs_gex"].idxmax()]

    regime = "positive" if total_gex > 0 else "negative"
    flip = profile["flip_point"]

    if regime == "positive":
        regime_note = (
            "Positive net GEX: dealers are long gamma and hedge against direction — "
            "expect mean reversion, suppressed realized vol, and ranges that hold. "
            "Favours selling premium / spreads over naked directional longs."
        )
        swing_note = (
            "For swings, buy dips toward the put wall and fade rips into the call wall. "
            "Breakouts need a catalyst to overcome hedging drag."
        )
    else:
        regime_note = (
            "Negative net GEX: dealers are short gamma and hedge with direction — "
            "expect vol expansion, trend continuation, and larger daily ranges. "
            "Favours long premium and directional swings."
        )
        swing_note = (
            "For swings, momentum breakouts extend rather than revert. "
            "Long calls/puts get help from dealer hedging instead of fighting it."
        )

    top = by_strike.nlargest(top_n, "abs_gex").sort_values("strike")

    return {
        "assumption": "dealers short customer calls, long customer puts (calls +GEX, puts -GEX)",
        "spot": round(float(spot), 4),
        "totals": {
            "net_gex": total_gex,
            "call_gex": call_gex_total,
            "put_gex": put_gex_total,
            "net_dex": total_dex,
            "net_gex_per_1pct_millions": round(total_gex / 1e6, 3),
            "gross_gex": float(np.nansum(df["gex"].abs())),
            "net_vanna": float(np.nansum(df["vex"])),
            "net_charm": float(np.nansum(df["cex"])),
        },
        "regime": {
            "state": regime,
            "note": regime_note,
            "swing_implication": swing_note,
            "flip_point": flip,
            "flip_distance_pct": profile["flip_distance_pct"],
            "above_flip": None if flip is None else bool(spot > flip),
        },
        "levels": {
            "call_wall": None
            if call_wall is None
            else {
                "strike": float(call_wall["strike"]),
                "gex": float(call_wall["net_gex"]),
                "distance_pct": round((float(call_wall["strike"]) / spot - 1.0) * 100.0, 3),
            },
            "put_wall": None
            if put_wall is None
            else {
                "strike": float(put_wall["strike"]),
                "gex": float(put_wall["net_gex"]),
                "distance_pct": round((float(put_wall["strike"]) / spot - 1.0) * 100.0, 3),
            },
            "gamma_pin": {
                "strike": float(pin["strike"]),
                "abs_gex": float(pin["abs_gex"]),
                "distance_pct": round((float(pin["strike"]) / spot - 1.0) * 100.0, 3),
            },
            "max_oi_strike": {
                "strike": float(max_oi_strike["strike"]),
                "total_oi": float(max_oi_strike["call_oi"] + max_oi_strike["put_oi"]),
            },
        },
        "profile": profile,
        "by_strike": [
            {
                "strike": float(r["strike"]),
                "call_gex": _f(r["call_gex"]),
                "put_gex": _f(r["put_gex"]),
                "net_gex": _f(r["net_gex"]),
                "net_dex": _f(r["net_dex"]),
                "call_oi": _f(r["call_oi"]),
                "put_oi": _f(r["put_oi"]),
                "call_vol": _f(r["call_vol"]),
                "put_vol": _f(r["put_vol"]),
            }
            for _, r in top.iterrows()
        ],
        "_exposure_frame": df,
    }
