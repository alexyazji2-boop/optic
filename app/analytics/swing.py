"""Composite swing verdict and concrete option structures.

Nothing here invents new information — it weighs the four independent reads
(trend/momentum, dealer gamma regime, options flow, news) into one stance, then
picks actual strikes and expiries from the live chain so the output is a trade,
not an adjective.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from .entry import iv_context
from .series_stats import relative_strength

# GICS sector labels (as yfinance reports them) mapped to their SPDR sector
# ETF, so a pair trade can be suggested even though we only ever load one
# ticker's own option chain.
SECTOR_ETF_MAP = {
    "Technology": "XLK",
    "Financial Services": "XLF",
    "Financials": "XLF",
    "Healthcare": "XLV",
    "Health Care": "XLV",
    "Consumer Cyclical": "XLY",
    "Consumer Discretionary": "XLY",
    "Consumer Defensive": "XLP",
    "Consumer Staples": "XLP",
    "Energy": "XLE",
    "Industrials": "XLI",
    "Basic Materials": "XLB",
    "Materials": "XLB",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Communication Services": "XLC",
}

# Relative weights. Technicals lead because they're the most reliable input on a
# swing timeframe; flow is a proxy on free data, so it's weighted lightest.
WEIGHTS = {
    "technicals": 0.34,
    "gamma": 0.24,
    "flow": 0.20,
    "news": 0.12,
    "macro": 0.10,
}


def _f(value: Any, digits: int = 4) -> Optional[float]:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(out) else round(out, digits)


def _gamma_score(gex: Dict[str, Any], spot: float) -> Optional[float]:
    """Directional read from dealer positioning.

    Positive gamma pins price and favors fading extremes; negative gamma lets
    trends run. Position relative to the flip point matters more than the sign
    of total GEX alone.
    """
    if not gex or gex.get("error"):
        return None

    regime = gex.get("regime", {})
    levels = gex.get("levels", {})
    score = 0.0

    flip = regime.get("flip_point")
    if flip:
        if spot > flip:
            score += 20  # above flip: dealers dampen downside
        else:
            score -= 25  # below flip: air pocket, moves accelerate

    call_wall = (levels.get("call_wall") or {}).get("distance_pct")
    put_wall = (levels.get("put_wall") or {}).get("distance_pct")

    # Room to the call wall is upside runway; sitting on it is a ceiling.
    if call_wall is not None:
        if call_wall > 4:
            score += 12
        elif call_wall < 1:
            score -= 12
    if put_wall is not None:
        if put_wall > -1.5:
            score -= 10  # price sitting on the put wall is fragile
        elif put_wall < -5:
            score += 8  # cushion well below

    net_dex = (gex.get("totals") or {}).get("net_dex")
    if net_dex is not None:
        score += float(np.clip(net_dex / 5e9, -15, 15))

    return float(np.clip(score, -100, 100))


def _news_score(news: Dict[str, Any]) -> Optional[float]:
    if not news:
        return None
    net = news.get("net_sentiment")
    if net is None:
        return None
    score = float(np.clip(net * 12.0, -70, 70))
    # An imminent print is a reason to size down, not a directional signal.
    days = news.get("days_to_earnings")
    if days is not None and 0 <= days <= 7:
        score *= 0.5
    return score


def _macro_score(macro: Optional[Dict[str, Any]]) -> Optional[float]:
    if not macro or macro.get("error"):
        return None
    return macro.get("risk_score")


# ------------------------------------------------------------ trade ideas


def _pick(chain: pd.DataFrame, is_call: bool, expiry: str, target_delta: float):
    """Closest liquid contract to a target delta on a given expiry."""
    side = chain[(chain["is_call"] == is_call) & (chain["expiry"] == expiry)].copy()
    if side.empty:
        return None
    side = side[side["delta"].notna()]
    if side.empty:
        return None
    side["delta_gap"] = (side["delta"].abs() - abs(target_delta)).abs()
    # Prefer contracts that can actually be filled.
    liquid = side[(side["open_interest"] >= 20) | (side["volume"] >= 20)]
    pool = liquid if not liquid.empty else side
    return pool.nsmallest(1, "delta_gap").iloc[0]


def _leg(row, action: str) -> Dict[str, Any]:
    return {
        "action": action,
        "type": "CALL" if bool(row["is_call"]) else "PUT",
        "strike": _f(row["strike"]),
        "expiry": row["expiry"],
        "dte": int(row["dte"]),
        "delta": _f(row["delta"], 3),
        "gamma": _f(row["gamma"], 6),
        "theta_per_day": _f(row["theta"], 4),
        "vega": _f(row["vega"], 4),
        "iv": _f(row["iv"], 4),
        "mid": _f(row["mid"], 2),
        "bid": _f(row["bid"], 2),
        "ask": _f(row["ask"], 2),
        "spread_pct": _f(row.get("spread_pct"), 2),
        "open_interest": _f(row["open_interest"], 0),
        "volume": _f(row["volume"], 0),
        "contract": row.get("contract"),
    }


def _choose_expiry(chain: pd.DataFrame, min_dte: int = 21, max_dte: int = 60) -> Optional[str]:
    """Swing structures want 3-8 weeks: enough time for the thesis, not so much
    that you overpay for theta you won't use."""
    if chain.empty:
        return None
    grouped = chain.groupby("expiry")["dte"].first().sort_values()
    window = grouped[(grouped >= min_dte) & (grouped <= max_dte)]
    if not window.empty:
        return str(window.index[0])
    longer = grouped[grouped >= min_dte]
    if not longer.empty:
        return str(longer.index[0])
    return str(grouped.index[-1])


def _single_idea(
    chain: pd.DataFrame, spot: float, expiry: str, is_call: bool, target_delta: float, name: str, rationale: str
) -> Optional[Dict[str, Any]]:
    leg = _pick(chain, is_call, expiry, target_delta)
    if leg is None or not leg["mid"] or leg["mid"] <= 0:
        return None
    cost = float(leg["mid"])
    breakeven = float(leg["strike"]) + cost if is_call else float(leg["strike"]) - cost
    return {
        "name": name,
        "structure": "long single option",
        "rationale": rationale,
        "expiry": expiry,
        "dte": int(leg["dte"]),
        "legs": [_leg(leg, "BUY")],
        "net_debit": _f(cost, 2),
        "max_profit": "unlimited" if is_call else _f(float(leg["strike"]) - cost, 2),
        "max_loss": _f(cost, 2),
        "breakeven": _f(breakeven, 2),
        "breakeven_move_pct": _f((breakeven / spot - 1.0) * 100.0, 2),
        "net_delta": _f(leg["delta"], 3),
        "net_theta_per_day": _f(leg["theta"], 4),
        "theta_pct_of_premium_daily": _f(abs(float(leg["theta"])) / cost * 100.0, 2),
    }


def _spread_idea(
    chain: pd.DataFrame, expiry: str, is_call: bool, long_delta: float, short_delta: float, name: str, rationale: str
) -> Optional[Dict[str, Any]]:
    long_leg = _pick(chain, is_call, expiry, long_delta)
    short_leg = _pick(chain, is_call, expiry, short_delta)
    if long_leg is None or short_leg is None:
        return None
    if float(long_leg["strike"]) == float(short_leg["strike"]):
        return None
    debit = (long_leg["mid"] or 0) - (short_leg["mid"] or 0)
    width = abs(float(short_leg["strike"]) - float(long_leg["strike"]))
    if debit <= 0 or width <= 0:
        return None
    return {
        "name": name,
        "structure": "vertical debit spread",
        "rationale": rationale,
        "expiry": expiry,
        "dte": int(long_leg["dte"]),
        "legs": [_leg(long_leg, "BUY"), _leg(short_leg, "SELL")],
        "net_debit": _f(debit, 2),
        "max_profit": _f(width - debit, 2),
        "max_loss": _f(debit, 2),
        "risk_reward": _f((width - debit) / debit, 2) if debit else None,
        "breakeven": _f(
            float(long_leg["strike"]) + debit if is_call else float(long_leg["strike"]) - debit, 2
        ),
        "net_delta": _f(float(long_leg["delta"]) - float(short_leg["delta"]), 3),
        "net_theta_per_day": _f(float(long_leg["theta"]) - float(short_leg["theta"]), 4),
    }


def _attach_risk_plan(
    ideas: List[Dict[str, Any]], spot: float, bearish: bool, atr_pct: Optional[float],
    support: Optional[float], resistance: Optional[float],
) -> None:
    """Common stop/target block derived from ATR and structure — mutates in place."""
    stop_distance = (atr_pct or 2.0) * 1.5
    for idea in ideas:
        idea["risk_plan"] = {
            "underlying_stop": _f(
                spot * (1 - stop_distance / 100.0) if not bearish else spot * (1 + stop_distance / 100.0), 2
            ),
            "stop_basis": "1.5 x the average daily range, which is {:.1f}% of the current "
                          "price".format(stop_distance),
            "first_target": _f(resistance if not bearish else support, 2),
            "invalidation": "A daily close beyond the stop, or dealer gamma flipping sign through "
                            "the flip point — either one breaks the reason for the trade.",
            "sizing_note": "Size each idea so the worst case costs a fixed fraction of the "
                           "account. The maximum loss shown above is the whole position.",
        }


def build_naked_ideas(
    chain: pd.DataFrame,
    spot: float,
    stance: str,
    technicals: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Naked long call or put — direct directional exposure, no second leg.

    For the fully ranked version of this same idea (multiple strikes scored
    against a projected target), see the Strike & Entry Recommendation panel —
    this is the quick-glance version in the same card format as the strategies
    below, so a naked option and a spread can be compared side by side.
    """
    if chain is None or chain.empty or "delta" not in chain.columns:
        return []

    expiry = _choose_expiry(chain)
    if expiry is None:
        return []

    atr_pct = ((technicals or {}).get("volatility", {}) or {}).get("atr_pct")
    fib = (technicals or {}).get("fibonacci", {}) or {}
    support = (fib.get("nearest_support") or {}).get("price")
    resistance = (fib.get("nearest_resistance") or {}).get("price")

    bullish = stance in ("bullish", "leaning bullish")
    bearish = stance in ("bearish", "leaning bearish")

    ideas: List[Dict[str, Any]] = []
    if bullish:
        idea = _single_idea(
            chain, spot, expiry, True, 0.50,
            "Long call (at-the-money)",
            "Cleanest expression of an upside swing: a ~50-delta call gives roughly half-share "
            "participation per contract-share with risk capped at the premium. Theta is the cost — "
            "see the daily burn rate on the leg below.",
        )
        if idea:
            ideas.append(idea)
    elif bearish:
        idea = _single_idea(
            chain, spot, expiry, False, 0.50,
            "Long put (at-the-money)",
            "Direct downside exposure with defined risk. Negative-gamma tape amplifies moves in your favor.",
        )
        if idea:
            ideas.append(idea)

    _attach_risk_plan(ideas, spot, bearish, atr_pct, support, resistance)
    return ideas


def build_strategy_ideas(
    chain: pd.DataFrame,
    spot: float,
    stance: str,
    gex: Dict[str, Any],
    technicals: Dict[str, Any],
    news: Optional[Dict[str, Any]] = None,
    quote: Optional[Dict[str, Any]] = None,
    history: Optional[pd.DataFrame] = None,
    provider: Any = None,
) -> List[Dict[str, Any]]:
    """Multi-leg and cross-underlying structures: spreads, condors, iron
    butterflies, straddles/strangles, and sector pair trades.

    Distinct from build_naked_ideas() — everything here either trades two legs
    against each other or trades a view on volatility/relative-strength rather
    than pure direction.
    """
    if chain is None or chain.empty or "delta" not in chain.columns:
        return []

    expiry = _choose_expiry(chain)
    if expiry is None:
        return []

    levels = (gex or {}).get("levels", {}) or {}
    regime = ((gex or {}).get("regime", {}) or {}).get("state")
    call_wall = (levels.get("call_wall") or {}).get("strike")
    put_wall = (levels.get("put_wall") or {}).get("strike")
    atr_pct = ((technicals or {}).get("volatility", {}) or {}).get("atr_pct")
    fib = (technicals or {}).get("fibonacci", {}) or {}
    support = (fib.get("nearest_support") or {}).get("price")
    resistance = (fib.get("nearest_resistance") or {}).get("price")

    bullish = stance in ("bullish", "leaning bullish")
    bearish = stance in ("bearish", "leaning bearish")
    ideas: List[Dict[str, Any]] = []

    if bullish:
        idea = _spread_idea(
            chain, expiry, True, 0.55, 0.25, "Bull call spread",
            "Caps upside but cuts cost and theta bleed roughly in half — the right structure when "
            "the target is a specific level{}.".format(
                " like the call wall at {:.0f}".format(call_wall) if call_wall else ""
            ),
        )
        if idea:
            ideas.append(idea)

        if regime == "positive" and put_wall:
            put_leg = _pick(chain, False, expiry, 0.20)
            if put_leg is not None and put_leg["mid"]:
                ideas.append(
                    {
                        "name": "Cash-secured put",
                        "structure": "short put (income)",
                        "rationale": "Positive gamma regime plus a dealer put wall near {:.0f} means dips get bought. "
                        "Selling a ~20-delta put collects premium and only obliges you at a price you already like.".format(put_wall),
                        "expiry": expiry,
                        "dte": int(put_leg["dte"]),
                        "legs": [_leg(put_leg, "SELL")],
                        "net_credit": _f(put_leg["mid"], 2),
                        "max_profit": _f(put_leg["mid"], 2),
                        "max_loss": _f(float(put_leg["strike"]) - float(put_leg["mid"]), 2),
                        "breakeven": _f(float(put_leg["strike"]) - float(put_leg["mid"]), 2),
                        "net_delta": _f(-float(put_leg["delta"]), 3),
                        "assignment_note": "Requires cash or margin for 100 shares per contract.",
                    }
                )

    if bearish:
        idea = _spread_idea(
            chain, expiry, False, 0.55, 0.25, "Bear put spread",
            "Lower cost than an outright put, with the short leg placed near the dealer put wall"
            "{}.".format(" at {:.0f}".format(put_wall) if put_wall else ""),
        )
        if idea:
            ideas.append(idea)

    if not bullish and not bearish:
        days_to_earnings = (news or {}).get("days_to_earnings")
        catalyst_soon = days_to_earnings is not None and 0 <= days_to_earnings <= 12
        iv_read = iv_context(
            chain, spot, ((technicals or {}).get("volatility") or {}).get("realised_vol_20d"), history=history
        )
        iv_verdict = iv_read.get("verdict") if iv_read.get("available") else None

        # Premium-selling structures: the textbook fit is neutral + positive
        # gamma (hedging suppresses realized vol) and IV that isn't already cheap.
        if regime == "positive" or iv_verdict in ("rich", "slightly rich", "fair"):
            short_call = _pick(chain, True, expiry, 0.20)
            long_call = _pick(chain, True, expiry, 0.10)
            short_put = _pick(chain, False, expiry, 0.20)
            long_put = _pick(chain, False, expiry, 0.10)
            condor_note = (
                "No directional edge and dealers are long gamma — hedging suppresses realized vol, "
                "which is the condition premium selling wants."
                if regime == "positive"
                else "No directional edge; implied vol isn't cheap, so selling the range collects a "
                "premium that realized vol is unlikely to eat into."
            )
            if all(leg is not None for leg in (short_call, long_call, short_put, long_put)):
                credit = (
                    float(short_call["mid"] or 0) + float(short_put["mid"] or 0)
                    - float(long_call["mid"] or 0) - float(long_put["mid"] or 0)
                )
                call_width = abs(float(long_call["strike"]) - float(short_call["strike"]))
                put_width = abs(float(short_put["strike"]) - float(long_put["strike"]))
                if credit > 0:
                    ideas.append(
                        {
                            "name": "Iron condor",
                            "structure": "short strangle with wings",
                            "rationale": condor_note,
                            "expiry": expiry,
                            "dte": int(short_call["dte"]),
                            "legs": [
                                _leg(long_put, "BUY"), _leg(short_put, "SELL"),
                                _leg(short_call, "SELL"), _leg(long_call, "BUY"),
                            ],
                            "net_credit": _f(credit, 2),
                            "max_profit": _f(credit, 2),
                            "max_loss": _f(max(call_width, put_width) - credit, 2),
                            "profit_zone": [_f(short_put["strike"]), _f(short_call["strike"])],
                            "net_delta": _f(
                                -float(short_call["delta"]) + float(long_call["delta"])
                                - float(short_put["delta"]) + float(long_put["delta"]), 3,
                            ),
                        }
                    )

            # Tighter body, more credit, same defined-risk shape as the condor —
            # the higher-conviction-pin alternative when gamma is strongly positive.
            atm_call = _pick(chain, True, expiry, 0.50)
            atm_put = _pick(chain, False, expiry, 0.50)
            wing_call = _pick(chain, True, expiry, 0.15)
            wing_put = _pick(chain, False, expiry, 0.15)
            if all(leg is not None for leg in (atm_call, atm_put, wing_call, wing_put)):
                credit = (
                    float(atm_call["mid"] or 0) + float(atm_put["mid"] or 0)
                    - float(wing_call["mid"] or 0) - float(wing_put["mid"] or 0)
                )
                call_width = abs(float(wing_call["strike"]) - float(atm_call["strike"]))
                put_width = abs(float(atm_put["strike"]) - float(wing_put["strike"]))
                if credit > 0 and float(atm_call["strike"]) != float(wing_call["strike"]):
                    ideas.append(
                        {
                            "name": "Iron butterfly",
                            "structure": "short straddle with wings",
                            "rationale": "Same premium-selling case as the condor, but selling the ATM straddle "
                            "collects more credit for a tighter profit zone — pays off if price truly pins "
                            "near {:.0f} through expiry.".format(spot),
                            "expiry": expiry,
                            "dte": int(atm_call["dte"]),
                            "legs": [
                                _leg(wing_put, "BUY"), _leg(atm_put, "SELL"),
                                _leg(atm_call, "SELL"), _leg(wing_call, "BUY"),
                            ],
                            "net_credit": _f(credit, 2),
                            "max_profit": _f(credit, 2),
                            "max_loss": _f(max(call_width, put_width) - credit, 2),
                            "profit_zone": [
                                _f(float(atm_put["strike"]) - credit),
                                _f(float(atm_call["strike"]) + credit),
                            ],
                            "net_delta": _f(
                                -float(atm_call["delta"]) + float(wing_call["delta"])
                                - float(atm_put["delta"]) + float(wing_put["delta"]), 3,
                            ),
                        }
                    )

        # Volatility-expansion structures: negative gamma, cheap IV, or an
        # imminent catalyst all argue for owning premium instead of selling it.
        if regime == "negative" or iv_verdict == "cheap" or catalyst_soon:
            why = []
            if regime == "negative":
                why.append("dealers are short gamma, so a real move tends to extend rather than mean-revert")
            if iv_verdict == "cheap":
                why.append("implied vol is cheap relative to realized, so premium isn't overpriced")
            if catalyst_soon:
                why.append("earnings in {} days is a scheduled catalyst for a move".format(days_to_earnings))
            why_text = "; ".join(why) or "a breakout in either direction is plausible"

            straddle_call = _pick(chain, True, expiry, 0.50)
            straddle_put = _pick(chain, False, expiry, 0.50)
            if straddle_call is not None and straddle_put is not None:
                cost = float(straddle_call["mid"] or 0) + float(straddle_put["mid"] or 0)
                if cost > 0:
                    ideas.append(
                        {
                            "name": "Long straddle",
                            "structure": "long call + long put, same strike",
                            "rationale": "No directional edge, but {} — a straddle profits from a big move "
                            "either way and loses only if price sits still through expiry.".format(why_text),
                            "expiry": expiry,
                            "dte": int(straddle_call["dte"]),
                            "legs": [_leg(straddle_call, "BUY"), _leg(straddle_put, "BUY")],
                            "net_debit": _f(cost, 2),
                            "max_profit": "unlimited",
                            "max_loss": _f(cost, 2),
                            "breakeven": [
                                _f(float(straddle_call["strike"]) + cost),
                                _f(float(straddle_put["strike"]) - cost),
                            ],
                            "net_delta": _f(float(straddle_call["delta"]) + float(straddle_put["delta"]), 3),
                            "net_theta_per_day": _f(float(straddle_call["theta"]) + float(straddle_put["theta"]), 4),
                        }
                    )

            strangle_call = _pick(chain, True, expiry, 0.30)
            strangle_put = _pick(chain, False, expiry, 0.30)
            if (
                strangle_call is not None and strangle_put is not None
                and float(strangle_call["strike"]) != float(straddle_call["strike"] if straddle_call is not None else -1)
            ):
                cost = float(strangle_call["mid"] or 0) + float(strangle_put["mid"] or 0)
                if cost > 0:
                    ideas.append(
                        {
                            "name": "Long strangle",
                            "structure": "long OTM call + long OTM put",
                            "rationale": "Cheaper than the straddle above because both legs are further "
                            "out-of-the-money — needs a bigger move to profit, but risks less premium getting there. "
                            "Same thesis: {}.".format(why_text),
                            "expiry": expiry,
                            "dte": int(strangle_call["dte"]),
                            "legs": [_leg(strangle_call, "BUY"), _leg(strangle_put, "BUY")],
                            "net_debit": _f(cost, 2),
                            "max_profit": "unlimited",
                            "max_loss": _f(cost, 2),
                            "breakeven": [
                                _f(float(strangle_call["strike"]) + cost),
                                _f(float(strangle_put["strike"]) - cost),
                            ],
                            "net_delta": _f(float(strangle_call["delta"]) + float(strangle_put["delta"]), 3),
                            "net_theta_per_day": _f(float(strangle_call["theta"]) + float(strangle_put["theta"]), 4),
                        }
                    )

    pair_idea = _sector_pair_idea(quote, history, provider)
    if pair_idea:
        ideas.append(pair_idea)

    _attach_risk_plan([i for i in ideas if not i.get("conceptual")], spot, bearish, atr_pct, support, resistance)
    return ideas


def _sector_pair_idea(
    quote: Optional[Dict[str, Any]], history: Optional[pd.DataFrame], provider: Any
) -> Optional[Dict[str, Any]]:
    """A pair trade expressed with options: long calls on whichever side is
    showing relative strength, long puts on the other, isolating the
    stock-vs-sector divergence from the sector's own broader move.

    Deliberately conceptual rather than fully priced — we only have this
    ticker's own option chain loaded, not the sector ETF's, so no ETF strikes
    are picked here. Open the ETF in this terminal for its own priced structures.
    """
    if quote is None or history is None or provider is None or history.empty:
        return None

    ticker = quote.get("ticker")
    sector = quote.get("sector")
    etf = SECTOR_ETF_MAP.get(sector or "")
    if not ticker or not etf or etf == ticker:
        return None

    try:
        etf_hist = provider.history(etf, period="1y", interval="1d")
    except Exception:
        return None
    if etf_hist is None or etf_hist.empty:
        return None

    rs = relative_strength(history, etf_hist)
    if not rs:
        return None

    rs_1m = rs.get("rs_1m")
    rs_3m = rs.get("rs_3m")
    signal = rs_1m if rs_1m is not None else rs_3m
    if signal is None or abs(signal) < 6.0:
        return None  # not enough divergence from its own sector to be a trade

    if signal > 0:
        long_name, short_name = ticker, etf
        thesis = (
            "{} has outpaced its own sector ETF ({}) by {:.1f}% over the past month — stock-specific "
            "strength, not just the sector moving. A pair trade isolates that: long calls on {}, long "
            "puts on {}, so a sector-wide reversal doesn't erase the edge.".format(
                ticker, etf, abs(rs_1m if rs_1m is not None else rs_3m), ticker, etf
            )
        )
    else:
        long_name, short_name = etf, ticker
        thesis = (
            "{} has lagged its own sector ETF ({}) by {:.1f}% over the past month — stock-specific "
            "weakness. A pair trade isolates that: long calls on {}, long puts on {}, so a sector-wide "
            "rally doesn't mask the underperformance.".format(
                ticker, etf, abs(rs_1m if rs_1m is not None else rs_3m), etf, ticker
            )
        )

    return {
        "name": "Sector pair trade — {} vs {}".format(ticker, etf),
        "structure": "cross-underlying pair trade",
        "conceptual": True,
        "rationale": thesis,
        "pair": {
            "long": long_name,
            "short": short_name,
            "rs_1m_pct": rs_1m,
            "rs_3m_pct": rs_3m,
            "ratio_zscore_60d": rs.get("ratio_zscore_60d"),
        },
        "note": "Strikes aren't priced here — this terminal only loads one option chain at a time. "
        "Load {} directly for its own priced call/put ideas.".format(short_name if long_name == ticker else long_name),
    }


# ------------------------------------------------------------- the verdict


# What each composite input actually measures, in the terms a reader needs.
COMPONENT_MEANING = {
    "technicals": "Chart structure on daily bars: moving-average stacking, price versus the "
                  "200-day, RSI regime, and whether MACD is above or below its signal line.",
    "gamma": "Dealer gamma exposure from the options chain — whether market-maker hedging is "
             "likely to dampen moves or amplify them, and which side of the gamma flip price sits on.",
    "flow": "Call versus put activity across the chain, weighted by volume and open interest. "
            "A positioning proxy, not real order flow — free data has no trade tape.",
    "news": "Tone of recent headlines, scored against a keyword lexicon and weighted toward "
            "the most recent stories, plus any detected catalyst types.",
    "macro": "The cross-asset risk regime — VIX, credit, the dollar, rates and oil — scored "
             "risk-on to risk-off. Applies to the whole market, not this ticker specifically.",
}


def verdict(
    technicals: Dict[str, Any],
    gex: Dict[str, Any],
    flow: Dict[str, Any],
    news: Dict[str, Any],
    macro: Optional[Dict[str, Any]],
    spot: float,
) -> Dict[str, Any]:
    components: Dict[str, Optional[float]] = {
        "technicals": (technicals or {}).get("trend_score"),
        "gamma": _gamma_score(gex, spot),
        "flow": (flow or {}).get("flow_score"),
        "news": _news_score(news),
        "macro": _macro_score(macro),
    }

    used = {k: v for k, v in components.items() if v is not None}
    weight_sum = sum(WEIGHTS[k] for k in used) or 1.0
    if used:
        composite = sum(v * WEIGHTS[k] for k, v in used.items()) / weight_sum
    else:
        composite = 0.0

    composite = float(np.clip(composite, -100, 100))

    if composite >= 30:
        stance, conviction = "bullish", "high" if composite >= 50 else "moderate"
    elif composite >= 10:
        stance, conviction = "leaning bullish", "low"
    elif composite <= -30:
        stance, conviction = "bearish", "high" if composite <= -50 else "moderate"
    elif composite <= -10:
        stance, conviction = "leaning bearish", "low"
    else:
        stance, conviction = "neutral", "none"

    # Disagreement between independent reads is itself information.
    signs = [np.sign(v) for v in used.values() if abs(v) > 8]
    agreement = None
    if signs:
        positive = sum(1 for s in signs if s > 0)
        agreement = round(max(positive, len(signs) - positive) / len(signs) * 100.0, 1)

    conflicts: List[str] = []
    tech = components.get("technicals")
    flow_score = components.get("flow")
    gamma = components.get("gamma")
    if tech is not None and flow_score is not None and tech * flow_score < -200:
        conflicts.append(
            "Technicals and options flow disagree — positioning is fighting the chart. Wait for one to break."
        )
    if tech is not None and gamma is not None and tech * gamma < -200:
        conflicts.append(
            "Trend and dealer positioning disagree — expect chop and false starts rather than a clean trend."
        )
    if news and news.get("earnings_warning"):
        conflicts.append(news["earnings_warning"])

    # What each component actually measures, and its arithmetic contribution to
    # the composite. Without this the five weighted numbers are unexplained: a
    # reader can see "gamma -13, weight 24%" and still not know what was measured.
    breakdown = []
    for name, value in components.items():
        weight = WEIGHTS[name]
        if value is None:
            breakdown.append({
                "component": name, "score": None, "weight_pct": round(weight * 100, 0),
                "contribution": None, "measures": COMPONENT_MEANING[name],
                "unavailable": True,
            })
            continue
        # Weights are renormalised over available components, so the contribution
        # shown is the share of the composite this component actually drove.
        effective = weight / weight_sum
        breakdown.append({
            "component": name,
            "score": _f(value, 1),
            "weight_pct": round(effective * 100, 0),
            "contribution": _f(value * effective, 1),
            "measures": COMPONENT_MEANING[name],
            "unavailable": False,
        })

    return {
        "stance": stance,
        "composite_score": round(composite, 1),
        "conviction": conviction,
        "components": {k: _f(v, 1) for k, v in components.items()},
        "weights": WEIGHTS,
        "breakdown": breakdown,
        "scale_note": (
            "Each input is scored -100 to +100, then averaged using the weights below. "
            "Weights are renormalised over whatever data is available, so a missing input "
            "redistributes rather than counting as zero."
        ),
        "signal_agreement_pct": agreement,
        "conflicts": conflicts,
        "summary": _summary(stance, composite, technicals, gex, flow, news),
    }


def _summary(
    stance: str,
    composite: float,
    technicals: Dict[str, Any],
    gex: Dict[str, Any],
    flow: Dict[str, Any],
    news: Dict[str, Any],
) -> str:
    bits: List[str] = []
    bias = (technicals or {}).get("bias")
    if bias:
        rsi_v = ((technicals or {}).get("rsi") or {}).get("value")
        macd_state = ((technicals or {}).get("macd") or {}).get("state")
        bits.append(
            "Chart is {} (RSI {}, MACD {})".format(
                bias,
                "{:.0f}".format(rsi_v) if rsi_v is not None else "n/a",
                macd_state or "n/a",
            )
        )

    regime = ((gex or {}).get("regime") or {}).get("state")
    if regime:
        flip = ((gex or {}).get("regime") or {}).get("flip_point")
        bits.append(
            "dealer gamma is {}{}".format(
                regime, " with the flip point at ${:,.2f}".format(flip) if flip else ""
            )
        )

    if flow and flow.get("stance"):
        pcr = ((flow or {}).get("volume") or {}).get("put_call_ratio")
        bits.append(
            "flow proxy reads {}{}".format(
                flow["stance"], " (put/call {:.2f})".format(pcr) if pcr else ""
            )
        )

    if news and news.get("overall_tone"):
        bits.append("news tone is {}".format(news["overall_tone"]))

    body = "; ".join(bits) if bits else "limited data"
    # "{:+.0f}" turns a composite of -0.04 into "-0", which reads as a broken sign
    # rather than a number. Round first, then add the sign, so anything that comes
    # out as zero is written as zero.
    rounded = round(composite)
    score = "{:+.0f}".format(rounded) if rounded else "0"
    return "Net stance {} ({}/100). {}.".format(
        stance, score, body[0].upper() + body[1:] if body else body)
