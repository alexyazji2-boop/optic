"""Strike selection and entry planning.

Turns the terminal's stance into two concrete answers: *which contract* and
*at what price to get in*.

Candidate strikes are ranked by repricing each one with Black-Scholes at a
projected target price and a shortened time to expiry — so the ranking reflects
the payoff you'd actually collect if the thesis works on schedule, not just a
delta that looked convenient. Both the target and the timeline are derived from
ATR and chart structure, and every assumption is returned alongside the numbers.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from .greeks import bs_price

TRADING_DAYS = 252

# ---------------------------------------------------------------- affordability
#
# Without these the ranker recommended an $11,300 contract: a $220 put on a $130
# stock, almost entirely intrinsic value. It scored well because the old formula
# rewarded "return if the thesis stalls", and a contract with barely any extrinsic
# value barely decays — so the deepest, most expensive strike always won that term.
# There was no cost term at all to push back.
#
# That is a real trade, but it isn't an *option* trade: paying 87% of the share
# price for the right to be short is buying the stock with extra steps, worse
# spreads and an expiry date. A recommendation nobody can size is not a
# recommendation.

# Premium ceiling as a share of the underlying price. Above this you are paying
# mostly for intrinsic value you could get by trading the shares directly.
MAX_PREMIUM_PCT_OF_SPOT = 18.0

# Soft budget per contract. Not a hard filter — a $600 stock has no cheap options
# and refusing to quote one would be worse than quoting an expensive one — but
# cost is scored, so a cheaper contract wins all else being equal.
SOFT_BUDGET_PER_CONTRACT = 2500.0

# Delta band. The old ceiling of 0.78 is where the deep-ITM problem lived; 0.65
# still gives a directional contract that moves with the stock without paying for
# a near-share-equivalent.
MIN_DELTA, MAX_DELTA = 0.35, 0.65


def _join(items: Any) -> str:
    """Comma-separated with a final "and". Joining three labels with " and " gave
    "the 9-day EMA and the 20-day SMA and the 21-day EMA", which reads as a
    mistake rather than a list."""
    parts = [str(i) for i in items if i]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return "{} and {}".format(", ".join(parts[:-1]), parts[-1])


def _usd(value: Any, digits: int = 2) -> str:
    """Prices with a currency symbol and a fixed number of decimals.

    round() alone produced "$300.0" and "$1242.5", which read as truncated
    numbers rather than prices — the reader can't tell whether a digit is missing.
    """
    try:
        return "${:,.{}f}".format(float(value), digits)
    except (TypeError, ValueError):
        return "n/a"


def _strike_label(strike: Any) -> str:
    """Strikes are usually whole or half dollars. "330.0" reads like a rounding
    artefact, so trailing zeros are dropped and 330.5 still shows its half."""
    try:
        value = float(strike)
    except (TypeError, ValueError):
        return str(strike)
    return "{:,.0f}".format(value) if abs(value - round(value)) < 1e-9 else "{:,.2f}".format(value)


def _f(value: Any, digits: int = 4) -> Optional[float]:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(out) else round(out, digits)


# ------------------------------------------------------------- IV positioning


def _realised_vol_series(history: pd.DataFrame, window: int = 20) -> pd.Series:
    """Rolling annualized realized vol (in percent) over the trailing window."""
    returns = history["Close"].pct_change()
    return returns.rolling(window, min_periods=window).std(ddof=0) * np.sqrt(TRADING_DAYS) * 100.0


def _iv_rank_proxy(atm_iv_pct: float, history: Optional[pd.DataFrame]) -> Dict[str, Any]:
    """IV rank / percentile, approximated.

    True IV rank needs a trailing year of the stock's *own* implied vol, which
    free data doesn't provide — yfinance has no historical-IV endpoint. The
    honest substitute: benchmark today's IV against the trailing-year range of
    the stock's own realized vol instead. It answers a related question — "is
    today's IV high relative to how this stock actually trades?" — but it is
    not the real thing, so every field here is prefixed accordingly and the
    method note says so explicitly.
    """
    if history is None or len(history) < 60:
        return {}

    series = _realised_vol_series(history, 20).dropna().tail(TRADING_DAYS)
    if len(series) < 40:
        return {}

    lo, hi = float(series.min()), float(series.max())
    current_rv = float(series.iloc[-1])

    rv_rank = _f((current_rv - lo) / (hi - lo) * 100.0, 1) if hi > lo else None
    if rv_rank is not None:
        rv_rank = float(np.clip(rv_rank, 0, 100))
    rv_percentile = _f(float((series < current_rv).mean() * 100.0), 1)

    iv_rank_proxy = None
    if hi > lo:
        iv_rank_proxy = float(np.clip((atm_iv_pct - lo) / (hi - lo) * 100.0, 0, 100))

    return {
        "iv_rank_proxy": _f(iv_rank_proxy, 1),
        "realised_vol_rank_pct": rv_rank,
        "realised_vol_percentile_pct": rv_percentile,
        "realised_vol_52w_low": _f(lo, 2),
        "realised_vol_52w_high": _f(hi, 2),
        "realised_vol_current_20d": _f(current_rv, 2),
    }


def iv_context(
    frame: pd.DataFrame,
    spot: float,
    realised_vol_pct: Optional[float],
    history: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    """Is implied vol rich or cheap versus how much the stock has actually moved?

    Without a historical IV series there is no true IV rank, so this compares
    implied to 20-day realized — a defensible substitute, and labeled as one.
    """
    near = frame[(frame["strike"] >= spot * 0.95) & (frame["strike"] <= spot * 1.05)]
    if near.empty:
        near = frame

    atm_iv = _f(near["iv"].median(), 4)
    if atm_iv is None:
        return {"available": False}

    front, back = None, None
    by_expiry = frame.groupby("expiry").agg(dte=("dte", "first"), iv=("iv", "median")).sort_values("dte")
    if len(by_expiry) >= 2:
        front = _f(by_expiry["iv"].iloc[0], 4)
        back = _f(by_expiry["iv"].iloc[-1], 4)

    premium_ratio = None
    if realised_vol_pct and realised_vol_pct > 0:
        premium_ratio = _f(atm_iv * 100.0 / realised_vol_pct, 3)

    verdict, guidance = "unknown", ""
    if premium_ratio is not None:
        if premium_ratio >= 1.35:
            verdict = "rich"
            guidance = (
                "Implied vol is {:.0f}% of realized. Options are pricing more movement than the stock "
                "has been delivering. Prefer spreads or credit structures over outright long premium.".format(premium_ratio * 100)
            )
        elif premium_ratio >= 1.1:
            verdict = "slightly rich"
            guidance = (
                "Implied vol runs modestly above realized, which is normal. Long premium is workable; "
                "spreads still reduce the vol risk."
            )
        elif premium_ratio >= 0.9:
            verdict = "fair"
            guidance = "Implied and realized vol are aligned. No vol edge either way; trade the direction."
        else:
            verdict = "cheap"
            guidance = (
                "Implied vol sits below realized. The market is underpricing recent movement. "
                "This favors buying premium outright over selling it."
            )

    term = None
    if front is not None and back is not None:
        if front > back * 1.08:
            term = (
                "Front-month IV ({:.1f}%) above back-month ({:.1f}%). Inverted term structure, typically an "
                "event or earnings bid. Front-dated long premium will get crushed once it passes.".format(front * 100, back * 100)
            )
        elif back > front * 1.08:
            term = (
                "Normal upward term structure ({:.1f}% front vs {:.1f}% back). No event premium in the front month.".format(
                    front * 100, back * 100
                )
            )

    atm_iv_pct = _f(atm_iv * 100.0, 2)
    rank_block = _iv_rank_proxy(atm_iv_pct, history)

    rank_guidance = None
    proxy_rank = rank_block.get("iv_rank_proxy")
    if proxy_rank is not None:
        if proxy_rank >= 70:
            rank_guidance = (
                "IV rank (proxy) {:.0f}. Implied vol is high versus this stock's own trailing-year vol range. "
                "Selling premium is more favourably priced than buying it right now.".format(proxy_rank)
            )
        elif proxy_rank <= 30:
            rank_guidance = (
                "IV rank (proxy) {:.0f}. Implied vol is low versus this stock's own trailing-year vol range. "
                "Buying premium is relatively cheap right now.".format(proxy_rank)
            )
        else:
            rank_guidance = "IV rank (proxy) {:.0f}. Implied vol sits mid-range versus this stock's own trailing-year vol history.".format(proxy_rank)

    return {
        "available": True,
        "atm_iv_pct": atm_iv_pct,
        "realised_vol_20d_pct": realised_vol_pct,
        "iv_to_realised_ratio": premium_ratio,
        "verdict": verdict,
        "guidance": guidance,
        "front_iv_pct": _f((front or 0) * 100.0, 2) if front else None,
        "back_iv_pct": _f((back or 0) * 100.0, 2) if back else None,
        "term_structure": term,
        "rank_guidance": rank_guidance,
        **rank_block,
        "method": "IV rank needs a historical IV series, which free data does not provide. "
        "'IV / realized' compares ATM implied vol to actual (realized) 20-day volatility. "
        "'IV rank (proxy)' and 'realized vol rank' benchmark today's IV and realized vol against this "
        "stock's own trailing-year realized-vol range, standing in for a true IV-history rank.",
    }


# ------------------------------------------------------ target and timeframe


def project_target(
    spot: float, direction: str, technicals: Dict[str, Any], gex: Dict[str, Any]
) -> Dict[str, Any]:
    """Where the move is likely headed, and how long it should take.

    Structure supplies the level (Fibonacci, gamma wall); ATR supplies the pace.
    A target with no timeline can't select an expiry.
    """
    fib = (technicals or {}).get("fibonacci") or {}
    vol = (technicals or {}).get("volatility") or {}
    levels = (gex or {}).get("levels") or {}
    atr = vol.get("atr14")

    candidates: List[Dict[str, Any]] = []
    if direction == "up":
        res = (fib.get("nearest_resistance") or {}).get("price")
        if res:
            candidates.append({"price": res, "source": "nearest Fibonacci resistance"})
        wall = (levels.get("call_wall") or {}).get("strike")
        if wall and wall > spot:
            candidates.append({"price": wall, "source": "dealer call wall"})
    else:
        sup = (fib.get("nearest_support") or {}).get("price")
        if sup:
            candidates.append({"price": sup, "source": "nearest Fibonacci support"})
        wall = (levels.get("put_wall") or {}).get("strike")
        if wall and wall < spot:
            candidates.append({"price": wall, "source": "dealer put wall"})

    if atr:
        # 2x ATR is a normal swing objective. 3x reads as a bigger prize but is
        # reached rarely enough that using it as the default target quietly biases
        # strike selection toward far-OTM lottery contracts.
        move = atr * 2.0
        candidates.append(
            {"price": spot + move if direction == "up" else spot - move, "source": "2x ATR projection"}
        )

    if not candidates:
        return {"available": False}

    # A level 1% away doesn't pay for the spread and the theta, so it isn't a
    # usable options target even when it's the nearest structure on the chart.
    MIN_MOVE_PCT = 2.0
    worthwhile = [
        c for c in candidates
        if abs(c["price"] / spot - 1.0) * 100.0 >= MIN_MOVE_PCT
    ]
    pool = worthwhile or candidates

    # Nearest qualifying level in the direction of the trade: the first place the
    # move has to prove itself, not the most optimistic one.
    if direction == "up":
        chosen = min(pool, key=lambda c: c["price"])
    else:
        chosen = max(pool, key=lambda c: c["price"])

    distance = abs(chosen["price"] - spot)
    trading_days_needed = None
    if atr and atr > 0:
        # Price travel scales with the square root of time, not linearly — a move
        # of 2 ATR takes roughly 4 sessions of pure excursion, and the 1.5x factor
        # accounts for the retracement that real trends spend most of their time in.
        # Assuming linear travel is how you end up buying far too little time.
        atr_multiples = distance / atr
        trading_days_needed = int(math.ceil((atr_multiples ** 2) * 1.5))
        trading_days_needed = max(5, min(trading_days_needed, 90))

    calendar_days = int(round((trading_days_needed or 15) * 1.4)) if trading_days_needed else 21

    skipped = [c for c in candidates if c not in pool]

    return {
        "available": True,
        "target_price": _f(chosen["price"], 2),
        "target_source": chosen["source"],
        "nearer_levels_skipped": [
            {"price": _f(c["price"], 2), "source": c["source"],
             "move_pct": _f((c["price"] / spot - 1.0) * 100.0, 2)}
            for c in skipped
        ] or None,
        "move_required_pct": _f((chosen["price"] / spot - 1.0) * 100.0, 2),
        "atr14": _f(atr, 3),
        "estimated_trading_days": trading_days_needed,
        "estimated_calendar_days": calendar_days,
        "alternatives": [
            {"price": _f(c["price"], 2), "source": c["source"], "move_pct": _f((c["price"] / spot - 1.0) * 100.0, 2)}
            for c in candidates
        ],
        "method": "Target is the nearest structural level in the trade's direction; the timeline assumes "
        "roughly 0.6 ATR of net daily progress, then adds 40% for weekends and chop.",
    }


# ------------------------------------------------------------ strike ranking


def rank_strikes(
    frame: pd.DataFrame,
    spot: float,
    direction: str,
    target: Dict[str, Any],
    rate: float = 0.0,
    div: float = 0.0,
    top_n: int = 6,
) -> List[Dict[str, Any]]:
    """Reprice every liquid candidate at the projected target and rank the payoff."""
    if frame is None or frame.empty or not target.get("available"):
        return []

    is_call = direction == "up"
    target_price = float(target["target_price"])
    hold_days = int(target.get("estimated_calendar_days") or 21)

    side = frame[frame["is_call"] == is_call].copy()
    if side.empty:
        return []

    # Buy more time than the thesis needs: an option that expires the week the
    # move is due leaves no room for the move to arrive late, which it usually does.
    min_dte = max(21, hold_days + 10)
    side = side[(side["mid"] > 0.05) & (side["dte"] >= min_dte)]
    if side.empty:
        return []

    # Only contracts that can be entered and exited: a wide spread eats the edge
    # before the thesis has a chance.
    liquid = side[
        ((side["open_interest"] >= 50) | (side["volume"] >= 50))
        & (side["spread_pct"].fillna(99) <= 15)
    ]
    pool = liquid if len(liquid) >= 4 else side
    if pool.empty:
        return []

    # Delta band, not just a strike range. Below ~0.30 delta the contract needs an
    # outsized move merely to break even, and ranking on percentage return will
    # always favor those lottery tickets if they are left in the pool.
    delta_abs = pool["delta"].abs()
    banded = pool[(delta_abs >= MIN_DELTA) & (delta_abs <= MAX_DELTA)]
    pool = banded if not banded.empty else pool
    if pool.empty:
        return []

    # Drop contracts priced like the stock itself. Applied after the delta band so
    # a genuinely expensive underlying still gets a quote — the fallback keeps the
    # cheapest available rather than returning nothing.
    affordable = pool[pool["mid"] <= spot * (MAX_PREMIUM_PCT_OF_SPOT / 100.0)]
    if not affordable.empty:
        pool = affordable
    else:
        pool = pool.nsmallest(max(4, top_n), "mid")

    rows: List[Dict[str, Any]] = []
    for _, row in pool.iterrows():
        entry = float(row["mid"])
        tau_now = float(row["tau"])
        tau_exit = max(tau_now - hold_days / 365.0, 1.0 / 365.0)
        iv = float(row["iv"])

        def value_at(price: float, vol: float) -> float:
            return float(
                bs_price(price, np.array([row["strike"]]), np.array([tau_exit]),
                         np.array([max(vol, 1e-4)]), rate, div, is_call)[0]
            )

        base = value_at(target_price, iv)
        crushed = value_at(target_price, iv * 0.8)   # post-event vol collapse
        flat = value_at(spot, iv)                     # thesis stalls, time passes
        against = value_at(
            spot - (target_price - spot) * 0.5 if is_call else spot + (spot - target_price) * 0.5, iv
        )

        ret = (base / entry - 1.0) * 100.0
        rows.append(
            {
                "contract": row.get("contract"),
                "strike": _f(row["strike"], 2),
                "expiry": row["expiry"],
                "dte": int(row["dte"]),
                "moneyness": "ITM" if (is_call and row["strike"] < spot) or ((not is_call) and row["strike"] > spot) else "OTM",
                "entry_mid": _f(entry, 2),
                "bid": _f(row["bid"], 2),
                "ask": _f(row["ask"], 2),
                "spread_pct": _f(row.get("spread_pct"), 2),
                "delta": _f(row["delta"], 3),
                "gamma": _f(row["gamma"], 5),
                "theta_per_day": _f(row["theta"], 3),
                "vega": _f(row["vega"], 3),
                "iv_pct": _f(iv * 100.0, 2),
                "open_interest": _f(row["open_interest"], 0),
                "volume": _f(row["volume"], 0),
                "breakeven": _f(
                    float(row["strike"]) + entry if is_call else float(row["strike"]) - entry, 2
                ),
                "value_at_target": _f(base, 2),
                "return_at_target_pct": _f(ret, 1),
                "value_if_iv_drops_20pct": _f(crushed, 2),
                "return_if_iv_drops_20pct": _f((crushed / entry - 1.0) * 100.0, 1),
                "value_if_flat": _f(flat, 2),
                "return_if_flat_pct": _f((flat / entry - 1.0) * 100.0, 1),
                "return_if_half_against_pct": _f((against / entry - 1.0) * 100.0, 1),
                "capital_per_contract": _f(entry * 100.0, 2),
            }
        )

    if not rows:
        return []

    # Rank on payoff if right, penalised by the bleed if the move simply doesn't
    # happen — which is the most common outcome — and by the cost of trading it.
    for r in rows:
        upside = r["return_at_target_pct"] or 0.0
        stall = r["return_if_flat_pct"] or 0.0
        spread = r["spread_pct"] or 0.0
        liquidity_ok = (r["open_interest"] or 0) >= 100 or (r["volume"] or 0) >= 100

        # Cost penalty, so capital efficiency competes with payoff. Scaled against
        # the soft budget rather than an absolute figure, and capped so one very
        # expensive underlying can't swamp every other term.
        cost = r["capital_per_contract"] or 0.0
        cost_penalty = min(cost / SOFT_BUDGET_PER_CONTRACT, 3.0) * 12.0

        # Extrinsic share of the premium: what you're actually buying when you buy
        # an option. A contract that is 90% intrinsic is a stock substitute.
        intrinsic = max(0.0, (spot - r["strike"]) if is_call else (r["strike"] - spot))
        extrinsic_pct = 0.0
        if r["entry_mid"]:
            extrinsic_pct = max(0.0, (r["entry_mid"] - intrinsic) / r["entry_mid"]) * 100.0
        r["extrinsic_pct"] = _f(extrinsic_pct, 1)

        # Stall weight cut from 0.35: rewarding low decay is fair, but at that
        # weight it was the single biggest term and it points straight at the
        # deepest strike on the board.
        r["score"] = round(
            upside * 0.5 + stall * 0.20 - spread * 1.5 - cost_penalty
            + (5 if liquidity_ok else -10), 2
        )

    rows.sort(key=lambda r: -r["score"])
    for i, r in enumerate(rows[:top_n], start=1):
        r["rank"] = i
    return rows[:top_n]


# ------------------------------------------------------------- the entry plan


def build_plan(
    frame: pd.DataFrame,
    spot: float,
    verdict: Dict[str, Any],
    technicals: Dict[str, Any],
    gex: Dict[str, Any],
    news: Dict[str, Any],
    rate: float = 0.0,
    div: float = 0.0,
    history: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    stance = (verdict or {}).get("stance") or "neutral"
    conviction = (verdict or {}).get("conviction") or "none"
    vol = (technicals or {}).get("volatility") or {}
    fib = (technicals or {}).get("fibonacci") or {}
    mas = (technicals or {}).get("moving_averages") or {}
    levels = (gex or {}).get("levels") or {}
    regime = ((gex or {}).get("regime") or {}).get("state")

    bullish = stance in ("bullish", "leaning bullish")
    bearish = stance in ("bearish", "leaning bearish")
    direction = "up" if bullish else "down" if bearish else None

    ivc = (
        iv_context(frame, spot, vol.get("realised_vol_20d"), history=history)
        if frame is not None and not frame.empty
        else {"available": False}
    )

    if direction is None:
        # Say what would create a trade instead of manufacturing one.
        trigger_up = (fib.get("nearest_resistance") or {}).get("price") or (levels.get("call_wall") or {}).get("strike")
        trigger_dn = (fib.get("nearest_support") or {}).get("price") or (levels.get("put_wall") or {}).get("strike")
        return {
            "actionable": False,
            "stance": stance,
            "headline": "No directional entry justified. The inputs disagree.",
            "reasoning": [
                "The composite sits at {:+.0f}, inside the neutral band, so a directional option is a "
                "coin flip paying theta for the privilege.".format((verdict or {}).get("composite_score") or 0),
                "Wait for one of the triggers below, or express the range with a credit structure "
                "if the gamma regime is positive.",
            ],
            "waiting_for": [
                {"condition": "A daily close above {}".format(_usd(trigger_up)),
                 "then": "bullish setups activate"} if trigger_up else None,
                {"condition": "A daily close below {}".format(_usd(trigger_dn)),
                 "then": "bearish setups activate"} if trigger_dn else None,
            ],
            "iv_context": ivc,
        }

    target = project_target(spot, direction, technicals, gex)
    candidates = rank_strikes(frame, spot, direction, target, rate, div)
    best = candidates[0] if candidates else None

    # ------------------------------------------------------ entry zone
    zone: List[Dict[str, Any]] = []
    if bullish:
        for key, label in (("ema21", "21-day EMA"), ("sma20", "20-day SMA"), ("ema9", "9-day EMA")):
            value = (mas.get(key) or {}).get("value")
            if value and value < spot:
                zone.append({"price": _f(value, 2), "label": label})
        support = (fib.get("nearest_support") or {}).get("price")
        if support:
            zone.append({"price": _f(support, 2), "label": "nearest Fibonacci support"})
        put_wall = (levels.get("put_wall") or {}).get("strike")
        if put_wall and put_wall < spot:
            zone.append({"price": _f(put_wall, 2), "label": "dealer put wall"})
    else:
        for key, label in (("ema21", "21-day EMA"), ("sma20", "20-day SMA"), ("ema9", "9-day EMA")):
            value = (mas.get(key) or {}).get("value")
            if value and value > spot:
                zone.append({"price": _f(value, 2), "label": label})
        resistance = (fib.get("nearest_resistance") or {}).get("price")
        if resistance:
            zone.append({"price": _f(resistance, 2), "label": "nearest Fibonacci resistance"})
        call_wall = (levels.get("call_wall") or {}).get("strike")
        if call_wall and call_wall > spot:
            zone.append({"price": _f(call_wall, 2), "label": "dealer call wall"})

    zone = [z for z in zone if z["price"]]
    zone.sort(key=lambda z: -z["price"] if bullish else z["price"])
    prices = [z["price"] for z in zone]
    zone_lo = min(prices) if prices else None
    zone_hi = max(prices) if prices else None

    atr = vol.get("atr14") or 0.0
    breakout_level = (
        (fib.get("nearest_resistance") or {}).get("price") if bullish
        else (fib.get("nearest_support") or {}).get("price")
    )

    entries: List[Dict[str, Any]] = []
    if zone_lo and zone_hi:
        entries.append(
            {
                "style": "Pullback entry (preferred)",
                "zone": [zone_lo, zone_hi],
                "detail": "Wait for the stock to come back into {} – {}, where {} sit. Buying "
                "into support means a closer stop and a cheaper option than chasing the "
                "move.".format(
                    _usd(zone_lo), _usd(zone_hi), _join(z["label"] for z in zone[:3]),
                ),
                "confirmation": (
                    "A reversal candle or reclaim of the 9-day EMA inside the zone, with RSI turning back above 50."
                    if bullish else
                    "A rejection candle or loss of the 9-day EMA inside the zone, with RSI turning back below 50."
                ),
            }
        )
    if breakout_level:
        entries.append(
            {
                "style": "Breakout entry",
                "zone": [_f(breakout_level, 2), _f(breakout_level + (atr * 0.5 if bullish else -atr * 0.5), 2)],
                "detail": "A daily close {} {} on heavier-than-usual volume confirms the move is "
                "continuing. This pays more premium and needs a wider stop, but it doesn't depend "
                "on a pullback that may never come.".format(
                    "above" if bullish else "below", _usd(breakout_level)
                ),
                "confirmation": "Daily close beyond the level, not just an intraday poke through it.",
            }
        )
    entries.append(
        {
            "style": "Scale-in",
            "zone": None,
            "detail": "Half size now, half on the pullback or the breakout confirmation above. "
            "Guarantees partial participation without committing to one entry read.",
            "confirmation": "Predefine both fills before entering so the second tranche is mechanical.",
        }
    )

    # ------------------------------------------------------ order guidance
    order: Dict[str, Any] = {}
    if best:
        mid = best["entry_mid"] or 0.0
        bid, ask = best["bid"] or 0.0, best["ask"] or 0.0
        limit = round(mid + (ask - mid) * 0.25, 2) if ask > mid else mid
        order = {
            "limit_price": limit,
            "never_pay_more_than": round(mid + (ask - mid) * 0.5, 2) if ask > mid else mid,
            "note": "Place a limit order at {}, just above the mid price of {}. The midpoint "
            "between the best bid and the best ask. The bid/ask spread is {}% of that mid, "
            "which is {}".format(
                _usd(limit), _usd(mid), _f(best["spread_pct"], 1),
                "wide enough that paying the ask outright can cost more than a whole day's "
                "time decay." if (best["spread_pct"] or 0) > 5
                else "tight enough to fill close to the mid without losing much to the spread.",
            ),
            "capital_per_contract": best["capital_per_contract"],
        }

    # ------------------------------------------------------ timing warnings
    warnings: List[str] = []
    days_to_earnings = (news or {}).get("days_to_earnings")
    if days_to_earnings is not None and 0 <= days_to_earnings <= 10:
        warnings.append(
            "Earnings in {} day{}. Buying premium now means paying event vol and eating the post-print crush. "
            "Either size for a binary event or wait until after the report.".format(
                days_to_earnings, "" if days_to_earnings == 1 else "s"
            )
        )
    if ivc.get("verdict") == "rich":
        warnings.append(
            "IV is rich versus realized: a debit spread or a lower-delta long caps the vol risk that an "
            "outright long option carries here."
        )
    flip = ((gex or {}).get("regime") or {}).get("flip_point")
    if flip:
        near_flip = abs(spot / flip - 1.0) * 100.0
        if near_flip < 1.0:
            warnings.append(
                "Spot is within {:.1f}% of the gamma flip at {}. The hedging regime can invert on a small "
                "move, so expect whipsaw around this level.".format(near_flip, _f(flip, 2))
            )
    if best and best["dte"] and best["dte"] < 21:
        warnings.append(
            "The best-scoring contract has only {} days left; gamma is high but so is theta. "
            "Do not hold it through a stall.".format(best["dte"])
        )
    if regime == "negative" and bullish:
        warnings.append(
            "Negative gamma regime cuts both ways: it will extend the move if you are right and "
            "accelerate the drawdown if you are wrong. Respect the stop."
        )

    stop = (
        _f(spot - atr * 1.5, 2) if bullish else _f(spot + atr * 1.5, 2)
    )

    # Written out in full rather than as a terse order ticket. "at about 12.54"
    # gave no currency and no unit, and an option premium is quoted per share but
    # bought in hundreds — so the number a reader sees is a hundredth of what
    # leaves the account. Both figures are stated.
    headline_parts = []
    if best:
        limit = order.get("limit_price")
        per_contract = limit * 100.0 if limit else None
        headline_parts.append(
            "Buy the ${} {} expiring {} for about ${} per share{}".format(
                _strike_label(best["strike"]),
                "call" if bullish else "put",
                best["expiry"],
                _f(limit, 2),
                " ({} for one contract, since an option covers 100 shares)".format(
                    _usd(per_contract, 0)) if per_contract else "",
            )
        )
    if zone_lo and zone_hi:
        headline_parts.append(
            "but only on a pullback in the stock to {} – {}".format(_usd(zone_lo), _usd(zone_hi)))
    elif breakout_level:
        headline_parts.append("but only on a daily close {} {}".format(
            "above" if bullish else "below", _usd(breakout_level)))

    return {
        "actionable": True,
        "stance": stance,
        "conviction": conviction,
        "direction": "long" if bullish else "short",
        "headline": (", ".join(headline_parts) + ".") if headline_parts else "Directional setup identified.",
        "recommended": best,
        "candidates": candidates,
        "target": target,
        "entry_options": entries,
        "entry_zone": {"low": zone_lo, "high": zone_hi, "levels": zone},
        "order_guidance": order,
        "risk": {
            "underlying_stop": stop,
            "stop_basis": "1.5 x the average daily range over the last 14 days ({}), measured "
                          "from the current price".format(_usd(atr * 1.5)),
            "target_price": target.get("target_price"),
            "target_source": target.get("target_source"),
            "invalidation": "Close beyond the stop, loss of the entry zone on a closing basis, or a flip "
            "in the dealer gamma regime.",
            "position_sizing": "Max loss is the full premium. Size so that a total loss is a fraction of "
            "the account you are willing to repeat. The allocation decision is yours.",
        },
        "warnings": warnings,
        "iv_context": ivc,
        "assumptions": [
            "Candidate returns hold implied vol constant and assume the target is reached in about {} calendar "
            "days; an IV-drop column shows what a 20% vol contraction does to each.".format(
                target.get("estimated_calendar_days")
            ),
            "Greeks come from Black-Scholes at a {:.2%} risk-free rate on delayed quotes.".format(rate),
            "Mid prices assume you can fill near the midpoint, which is optimistic on wide spreads.",
        ],
    }
