"""Dealer gamma, delta, vanna and charm exposure (GEX, DEX, VEX, CEX) from a chain.

**The model's assumption, stated once and used everywhere.** Dealers (the market
makers on the other side of customer orders) are assumed to be LONG every call
customers have sold to them and SHORT every put customers have bought from them.
That is the common retail convention (customers write calls against stock and
buy puts for protection), and it is an assumption: open interest says how many
contracts are open at a strike, not who holds which side of them, so nothing
here is observed dealer inventory. Under it, each contract's exposure is the
dealer's own:

    call  GEX = +gamma x OI x multiplier x S^2 x 0.01     (long a call: long gamma)
    put   GEX = -gamma x OI x multiplier x S^2 x 0.01     (short a put: short gamma)

**What a sign means.** Positive net GEX is dealers net LONG gamma. To stay
delta-neutral a long-gamma book sells as the price rises and buys as it falls,
which leans against moves: ranges tend to hold. Negative net GEX is dealers
net SHORT gamma, whose hedge buys rises and sells falls, adding to moves:
trends tend to extend. The flip point is the spot price at which the sign of
net GEX changes, re-priced at each level, and it is reported with the direction
it crosses in, because "above the flip, dealers dampen" is only true of a
crossing from negative below to positive above.

**Units.** Every exposure is in dollars of the dealer's delta (shares of delta
valued at today's spot), with gamma per $1 and per share, open interest in
contracts and the multiplier in shares per contract:

* GEX: change in dealer delta, in dollars, for a 1% move in spot: the stock the
  hedge has to trade to stay neutral after that move.
* DEX: the dealer's option delta, in dollars (delta x OI x multiplier x S).
  Under this convention it is never negative (a long call and a short put both
  carry positive delta), and the dealer's stock hedge is the opposite sign.
* VEX: change in dealer delta, in dollars, for a 1 point rise in implied vol.
* CEX: change in dealer delta, in dollars, for one calendar day passing.

**Contract size.** The provider's stated size where it gives one (Tradier's
contract_size), 100 shares for a contract whose symbol's root is the ticker's,
and otherwise unknown: an adjusted contract (TSLA1 rather than TSLA) after a
split or merger can deliver something other than 100 shares, so it is left out
of every exposure and counted rather than multiplied by a number that is
probably wrong. See app/analytics/quotes.py.

**What open interest cannot establish**, and so what no number here claims: who
is long and who is short; positions opened or closed today (open interest is
the last session's); whether dealers hedge, how much, or with what; positions
held away from dealers, and trades between two customers; and the deliverable
of an adjusted contract.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from . import quotes
from .greeks import greeks

# Kept for callers that import it. A contract's own size is used wherever it is
# known; see the module docstring.
CONTRACT_MULTIPLIER = quotes.STANDARD_MULTIPLIER


# The least share of the largest strike's absolute gamma exposure a strike
# must carry to be named a call or put wall (see analyse).
WALL_MIN_SHARE = 0.05

ASSUMPTION = ("Model assumption, not observed positions: dealers are long the calls "
              "customers sold and short the puts customers bought, so calls count as "
              "positive gamma exposure and puts as negative. Open interest shows how "
              "many contracts are open, not who holds which side.")

CONVENTION = {
    "positions": "Dealers long customer-sold calls, short customer-bought puts.",
    "represents": "The dealer's own exposure under that assumption, not the customer's.",
    "positive": ("Dealers net long gamma: hedging sells rises and buys falls, which "
                 "leans against moves."),
    "negative": ("Dealers net short gamma: hedging buys rises and sells falls, which "
                 "adds to moves."),
    "units": {
        "gex": "dollars of dealer delta per 1% move in spot",
        "dex": "dollars of dealer option delta; the stock hedge is the opposite sign",
        "vex": "dollars of dealer delta per 1 point rise in implied volatility",
        "cex": "dollars of dealer delta per calendar day",
    },
    "multiplier": ("Shares per contract: the provider's stated size, 100 for a standard "
                   "contract, and an adjusted contract of unstated size left out."),
    "cannot_establish": [
        "who holds which side of a contract",
        "positions opened or closed today",
        "whether, how much and with what dealers hedge",
        "positions held away from dealers, or trades between customers",
        "an adjusted contract's deliverable",
    ],
}


def _f(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(out) else out


def compute_exposure(chain: pd.DataFrame, spot: float, rate: float = 0.0, div: float = 0.0,
                     ticker: Optional[str] = None) -> pd.DataFrame:
    """Attach greeks and the dealer's signed dollar exposures to a chain frame.

    ``chain`` needs columns: strike, tau, iv, open_interest, volume, is_call.
    Rows whose contract size cannot be known (an adjusted contract with no
    stated size) are dropped, and the frame's ``attrs["unknown_size"]`` says
    how many."""
    df = chain.copy()
    size = quotes.multipliers(df, ticker)
    unknown = int(size.isna().sum())
    df = df[size.notna()].copy()
    df["multiplier"] = size[size.notna()].to_numpy()
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

    # +1 for a call (dealer long it), -1 for a put (dealer short it).
    sign = np.where(df["is_call"].to_numpy(), 1.0, -1.0)
    oi = df["open_interest"].fillna(0.0).to_numpy()
    vol = df["volume"].fillna(0.0).to_numpy()
    mult = df["multiplier"].to_numpy(dtype=float)

    # Dealer delta change, in dollars, for a 1% move in spot.
    df["gex"] = sign * df["gamma"].to_numpy() * oi * mult * spot * spot * 0.01
    df["gex_volume"] = sign * df["gamma"].to_numpy() * vol * mult * spot * spot * 0.01

    # The dealer's own option delta in dollars. Never negative under this
    # convention; the hedge in stock is the opposite sign.
    df["dex"] = sign * df["delta"].to_numpy() * oi * mult * spot

    # Dealer delta change in dollars per vol point (vanna) and per day (charm).
    df["vex"] = sign * df["vanna"].to_numpy() * oi * mult * spot
    df["cex"] = sign * df["charm"].to_numpy() * oi * mult * spot

    df["notional_oi"] = oi * mult * df["strike"].to_numpy()
    df["premium_traded"] = vol * mult * df["mid"].fillna(df["last"]).fillna(0.0).to_numpy()
    df.attrs["unknown_size"] = unknown
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
    mult = (df["multiplier"].to_numpy(dtype=float) if "multiplier" in df.columns
            else np.full(len(df), quotes.STANDARD_MULTIPLIER))
    exposure = sign * g["gamma"] * oi * mult * test_spot * test_spot * 0.01
    return float(np.nansum(exposure))


def gamma_profile(
    df: pd.DataFrame,
    spot: float,
    rate: float = 0.0,
    div: float = 0.0,
    span_pct: float = 0.12,
    steps: int = 61,
) -> Dict[str, Any]:
    """Net GEX as a function of spot, plus the zero-crossing (gamma flip).

    The crossing nearest spot, with its direction: "upward" when net GEX is
    negative below the flip and positive above it, "downward" the reverse.
    Only an upward crossing supports "above the flip dealers dampen moves"."""
    lo, hi = spot * (1 - span_pct), spot * (1 + span_pct)
    grid = np.linspace(lo, hi, steps)
    values = [_gamma_at_spot(df, float(s), rate, div) for s in grid]

    flip: Optional[float] = None
    direction: Optional[str] = None
    for i in range(1, len(values)):
        a, b = values[i - 1], values[i]
        if np.isfinite(a) and np.isfinite(b) and a * b < 0:
            # Linear interpolation between the two bracketing grid points.
            weight = abs(a) / (abs(a) + abs(b))
            candidate = float(grid[i - 1] + weight * (grid[i] - grid[i - 1]))
            # Keep whichever crossing sits closest to spot.
            if flip is None or abs(candidate - spot) < abs(flip - spot):
                flip = candidate
                direction = "upward" if b > a else "downward"

    return {
        "spots": [round(float(s), 4) for s in grid],
        "net_gex": [_f(v) for v in values],
        "flip_point": None if flip is None else round(flip, 4),
        "flip_distance_pct": None if flip is None else round((flip / spot - 1.0) * 100.0, 3),
        "flip_direction": direction,
    }


def _level(row: Optional[pd.Series], spot: float, key: str = "gex") -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    return {"strike": float(row["strike"]), key: float(row["net_gex"] if key == "gex" else row["abs_gex"]),
            "distance_pct": round((float(row["strike"]) / spot - 1.0) * 100.0, 3)}


def analyse(
    chain: pd.DataFrame,
    spot: float,
    rate: float = 0.0,
    div: float = 0.0,
    top_n: int = 14,
    ticker: Optional[str] = None,
) -> Dict[str, Any]:
    """GEX/DEX analysis for the (already expiry-filtered) chain."""
    if chain is None or chain.empty:
        return {"error": "empty options chain"}

    df = compute_exposure(chain, spot, rate, div, ticker)
    unknown = int(df.attrs.get("unknown_size") or 0)
    if df.empty:
        return {"error": "no contract on this chain has a known size"}

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

    # Walls, on the side of spot each is named for. The call wall is the
    # heaviest positive net GEX at or above spot: long dealer gamma there leans
    # against a rally into it. The put wall is the heaviest negative net GEX at
    # or below spot: short dealer gamma there adds to a fall through it, which
    # is why it is not called support here. Both used to be taken from either
    # side of spot, so a "ceiling" could sit under the price.
    # And only a strike that carries a real share of the chain's exposure. On
    # AAPL at 9:36am ET on 2026-10-07 the "put wall" was the $20 strike, 94%
    # below the price, at -$5.8k of gamma against $24M at the pin: the most
    # negative strike below spot existed and was noise, and the panel named it
    # a level where hedging adds to a fall. A wall under WALL_MIN_SHARE of the
    # largest strike's exposure is no wall.
    floor = WALL_MIN_SHARE * float(by_strike["abs_gex"].max() or 0.0)
    above = by_strike[(by_strike["strike"] >= spot) & (by_strike["net_gex"] > floor)]
    below = by_strike[(by_strike["strike"] <= spot) & (by_strike["net_gex"] < -floor)]
    call_wall = above.loc[above["net_gex"].idxmax()] if not above.empty else None
    put_wall = below.loc[below["net_gex"].idxmin()] if not below.empty else None
    max_oi_strike = by_strike.loc[(by_strike["call_oi"] + by_strike["put_oi"]).idxmax()]

    # The pin is where long dealer gamma is heaviest, because only long gamma
    # pins: hedging it sells above and buys below. It used to be the largest
    # exposure of either sign, which on a put-heavy chain named a strike where
    # hedging pushes price away rather than pulling it in.
    positive = by_strike[by_strike["net_gex"] > 0]
    pin = positive.loc[positive["net_gex"].idxmax()] if not positive.empty else None

    regime = "positive" if total_gex > 0 else "negative" if total_gex < 0 else "flat"
    flip = profile["flip_point"]

    if regime == "positive":
        regime_note = (
            "Positive net GEX: under the model's assumption dealers are net long gamma, so "
            "their hedging sells rises and buys falls. Expect mean reversion, suppressed "
            "realized vol and ranges that hold. Favours selling premium and spreads over "
            "naked directional longs."
        )
        swing_note = (
            "For swings, rallies into the call wall tend to stall and breakouts need a "
            "catalyst to overcome hedging drag. The put wall below is where negative gamma "
            "is heaviest: a fall that reaches it is where hedging stops resisting and "
            "starts adding to the move."
        )
    elif regime == "negative":
        regime_note = (
            "Negative net GEX: under the model's assumption dealers are net short gamma, so "
            "their hedging buys rises and sells falls. Expect vol expansion, trend "
            "continuation and larger daily ranges. Favours long premium and directional swings."
        )
        swing_note = (
            "For swings, momentum breakouts tend to extend rather than revert. Long calls "
            "and puts get help from hedging flows instead of fighting them, and a stop gets "
            "hit faster when the move turns."
        )
    else:
        regime_note = "Net GEX is zero: the model's call and put exposure cancel at this price."
        swing_note = "No hedging lean either way at this price under the model."

    top = by_strike.nlargest(top_n, "abs_gex").sort_values("strike")

    return {
        "assumption": ASSUMPTION,
        "convention": CONVENTION,
        "excluded_contracts": unknown,
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
            "flip_direction": profile.get("flip_direction"),
            "above_flip": None if flip is None else bool(spot > flip),
        },
        "levels": {
            "call_wall": _level(call_wall, spot),
            "put_wall": _level(put_wall, spot),
            "gamma_pin": None if pin is None else {
                "strike": float(pin["strike"]),
                "gex": float(pin["net_gex"]),
                # Kept under its old name too: the pin is positive now, so its
                # size and its absolute size are the same number.
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
