"""Scalping / intraday panel.

Swing analysis lives on daily bars and multi-week Fibonacci grids; none of that
is the right tool for a trade meant to last minutes. This module works on the
most recent trading session's minute bars and the nearest listed option
expiry — often 0DTE, sometimes not, and it says which — to surface what an
intraday options trader actually watches: VWAP, the opening range, classic
floor-trader pivots, relative volume, fast momentum, near-the-money liquidity,
and a gamma/short-squeeze read built from dealer positioning plus short
interest.

Honesty note up front: scalping requires genuinely real-time data. Every
number here is computed correctly from whatever feed is active, but if that
feed is the free delayed one, the whole tab is a structural view of levels and
positioning — not a live execution tool. The API response says which situation
you're in; the UI repeats it prominently rather than letting it get lost.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from .fundamentals import analyse_short_interest
from .gex import compute_exposure, gamma_profile
from .technicals import ema, rsi

TRADING_DAYS = 252


def _f(value: Any, digits: int = 4) -> Optional[float]:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(out) else round(out, digits)


# --------------------------------------------------------------- sessions


def _session_frames(intraday: pd.DataFrame):
    """Split minute bars into (most recent session, [prior sessions])."""
    if intraday is None or intraday.empty:
        return pd.DataFrame(), []
    dates = sorted(set(intraday.index.date))
    if not dates:
        return pd.DataFrame(), []
    current = intraday[intraday.index.date == dates[-1]]
    prior = [intraday[intraday.index.date == d] for d in dates[:-1]]
    return current, [p for p in prior if not p.empty]


def _vwap(session: pd.DataFrame) -> pd.Series:
    if session.empty:
        return pd.Series(dtype=float)
    typical = (session["High"] + session["Low"] + session["Close"]) / 3.0
    cum_vol = session["Volume"].cumsum()
    cum_pv = (typical * session["Volume"]).cumsum()
    return cum_pv / cum_vol.replace(0, np.nan)


def _opening_range(session: pd.DataFrame, minutes: int = 15) -> Dict[str, Any]:
    if session.empty:
        return {}
    cutoff = session.index[0] + pd.Timedelta(minutes=minutes)
    window = session[session.index < cutoff]
    if window.empty:
        return {}
    return {
        "minutes": minutes,
        "high": _f(window["High"].max(), 2),
        "low": _f(window["Low"].min(), 2),
        "complete": bool(session.index[-1] >= cutoff),
    }


def _pivots(prior_session: Optional[pd.DataFrame]) -> Dict[str, Any]:
    """Classic floor-trader pivots from the prior session's high/low/close."""
    if prior_session is None or prior_session.empty:
        return {}
    hi = float(prior_session["High"].max())
    lo = float(prior_session["Low"].min())
    close = float(prior_session["Close"].iloc[-1])
    pivot = (hi + lo + close) / 3.0
    span = hi - lo
    return {
        "prior_close": _f(close, 2),
        "prior_high": _f(hi, 2),
        "prior_low": _f(lo, 2),
        "pivot": _f(pivot, 2),
        "r1": _f(2 * pivot - lo, 2),
        "r2": _f(pivot + span, 2),
        "s1": _f(2 * pivot - hi, 2),
        "s2": _f(pivot - span, 2),
    }


def _rvol(current: pd.DataFrame, prior: List[pd.DataFrame]) -> Dict[str, Any]:
    """Volume so far this session vs the historical average at this same
    point in the trading day — the standard relative-volume calculation."""
    if current.empty or not prior:
        return {}
    now_cum = float(current["Volume"].sum())
    elapsed = current.index[-1] - current.index[0]

    baselines = []
    for day in prior[-4:]:  # last 4 prior sessions as the baseline
        cutoff = day.index[0] + elapsed
        window = day[day.index <= cutoff]
        if not window.empty:
            baselines.append(float(window["Volume"].sum()))
    if not baselines:
        return {}

    baseline_avg = float(np.mean(baselines))
    rvol = _f(now_cum / baseline_avg, 3) if baseline_avg > 0 else None
    return {
        "volume_so_far": _f(now_cum, 0),
        "baseline_avg_volume": _f(baseline_avg, 0),
        "rvol": rvol,
        "sessions_in_baseline": len(baselines),
    }


def _fast_momentum(session: pd.DataFrame) -> Dict[str, Any]:
    """Short-period trend/momentum read on the intraday bars themselves."""
    close = session["Close"].dropna()
    if len(close) < 20:
        return {}

    ema9 = ema(close, 9)
    ema20 = ema(close, 20)
    rsi7 = rsi(close, 7)

    last = float(close.iloc[-1])
    e9 = ema9.dropna().iloc[-1] if not ema9.dropna().empty else None
    e20 = ema20.dropna().iloc[-1] if not ema20.dropna().empty else None
    r7 = rsi7.dropna().iloc[-1] if not rsi7.dropna().empty else None

    trend = None
    if e9 is not None and e20 is not None:
        trend = "up" if e9 > e20 else "down"

    return {
        "last": _f(last, 2),
        "ema9": _f(e9, 2),
        "ema20": _f(e20, 2),
        "fast_rsi_7": _f(r7, 1),
        "trend": trend,
        "series": {
            "times": [t.strftime("%H:%M") for t in session.index[-120:]],
            "close": [_f(v, 2) for v in close.tail(120)],
            "ema9": [_f(v, 2) for v in ema9.tail(120)],
            "ema20": [_f(v, 2) for v in ema20.tail(120)],
            "vwap": [_f(v, 2) for v in _vwap(session).tail(120)],
            "volume": [_f(v, 0) for v in session["Volume"].tail(120)],
        },
    }


# ------------------------------------------------------- near-term options


def _front_expiry(available: List[str]) -> Optional[Dict[str, Any]]:
    if not available:
        return None
    today = pd.Timestamp.today().normalize()
    dated = sorted(((e, (pd.Timestamp(e) - today).days) for e in available), key=lambda pair: pair[1])
    front, dte = dated[0]
    return {"expiry": front, "dte": max(dte, 0), "is_0dte": dte <= 0}


def _near_term_gex(chain: pd.DataFrame, spot: float, rate: float, div: float) -> Dict[str, Any]:
    """Same mechanics as the swing GEX panel, but scoped to one front expiry
    and a tight ±3% price grid — a scalper cares about the next few strikes,
    not the wall 10% away."""
    if chain is None or chain.empty:
        return {"error": "no near-term chain"}

    frame = compute_exposure(chain, spot, rate=rate, div=div)
    sign = np.where(frame["is_call"], 1.0, -1.0)
    total_gex = float(np.nansum(frame["gex"]))

    by_strike = (
        frame.assign(signed_gex=frame["gex"])
        .groupby("strike")
        .agg(net_gex=("signed_gex", "sum"), call_oi=("open_interest", lambda s: float(s[frame.loc[s.index, "is_call"]].sum())),
             put_oi=("open_interest", lambda s: float(s[~frame.loc[s.index, "is_call"]].sum())))
        .reset_index()
    )
    by_strike["abs_gex"] = by_strike["net_gex"].abs()

    profile = gamma_profile(frame, spot, rate=rate, div=div, span_pct=0.03, steps=41)
    flip = profile.get("flip_point")

    pos = by_strike[by_strike["net_gex"] > 0]
    neg = by_strike[by_strike["net_gex"] < 0]
    call_wall = pos.loc[pos["net_gex"].idxmax()] if not pos.empty else None
    put_wall = neg.loc[neg["net_gex"].idxmin()] if not neg.empty else None

    regime = "positive" if total_gex > 0 else "negative"

    return {
        "spot": _f(spot, 2),
        "total_gex": _f(total_gex, 0),
        "regime": regime,
        "flip_point": _f(flip, 2),
        "flip_distance_pct": _f((flip / spot - 1.0) * 100.0, 3) if flip else None,
        "above_flip": bool(spot > flip) if flip else None,
        "call_wall": _f(call_wall["strike"], 2) if call_wall is not None else None,
        "put_wall": _f(put_wall["strike"], 2) if put_wall is not None else None,
        "profile": profile,
        "_exposure_frame": frame,
    }


def _liquidity_read(frame: pd.DataFrame, spot: float) -> Dict[str, Any]:
    """Are the near-the-money strikes actually tradeable for something fast?"""
    if frame is None or frame.empty:
        return {}
    near = frame[(frame["strike"] >= spot * 0.97) & (frame["strike"] <= spot * 1.03)]
    if near.empty:
        near = frame
    avg_spread = _f(near["spread_pct"].replace([np.inf, -np.inf], np.nan).dropna().median(), 2)
    avg_oi = _f(near["open_interest"].mean(), 0)
    avg_vol = _f(near["volume"].mean(), 0)

    if avg_spread is None:
        quality = "unknown"
    elif avg_spread <= 3:
        quality = "tight"
    elif avg_spread <= 8:
        quality = "workable"
    else:
        quality = "wide"

    return {
        "median_spread_pct": avg_spread,
        "avg_open_interest": avg_oi,
        "avg_volume": avg_vol,
        "quality": quality,
        "note": {
            "tight": "Spreads are tight enough to scalp — slippage won't eat the trade.",
            "workable": "Spreads are workable but not ideal — size down or use limit orders only.",
            "wide": "Spreads are wide for a fast trade — a quick in-and-out here bleeds to slippage before it bleeds to theta.",
            "unknown": "Not enough quotes near the money to judge spread quality.",
        }[quality],
    }


# ------------------------------------------------------------ squeeze read


def _squeeze_read(
    near_gex: Dict[str, Any],
    momentum: Dict[str, Any],
    rvol: Dict[str, Any],
    opening_range: Dict[str, Any],
    short_interest: Dict[str, Any],
    vwap_now: Optional[float],
) -> Dict[str, Any]:
    """Two related but distinct mechanisms, scored separately:

    Gamma squeeze — dealers are short gamma near spot, so their hedging BUYS
    into strength and SELLS into weakness, amplifying whichever way price
    breaks. Needs: negative near-term gamma, price breaking a level, volume
    confirming.

    Short squeeze — a crowded short position that a rally forces to cover,
    which is itself buying pressure. Needs: high short interest, low days-to-
    cover making the exit crowded, and price breaking up on volume.

    Both float on the same three ingredients (breakout, volume, positioning)
    but the positioning half is different, so a name can show one without
    the other.
    """
    spot = near_gex.get("spot")
    last = momentum.get("last")
    trend = momentum.get("trend")
    rvol_val = (rvol or {}).get("rvol")
    or_high = (opening_range or {}).get("high")
    or_low = (opening_range or {}).get("low")

    breaking_up = bool(
        last is not None and (
            (or_high is not None and last > or_high) or (vwap_now is not None and last > vwap_now)
        )
    )
    breaking_down = bool(
        last is not None and (
            (or_low is not None and last < or_low) or (vwap_now is not None and last < vwap_now)
        )
    )

    # ---- gamma squeeze
    gamma_score = 0.0
    gamma_notes: List[str] = []
    if near_gex.get("regime") == "negative":
        gamma_score += 45
        gamma_notes.append("Near-term dealer gamma is negative — hedging amplifies the next move instead of damping it.")
    flip_dist = near_gex.get("flip_distance_pct")
    if flip_dist is not None and abs(flip_dist) < 1.5:
        gamma_score += 20
        gamma_notes.append("Spot is within 1.5% of the gamma flip — small moves can flip the hedging regime entirely.")
    if breaking_up and trend == "up":
        gamma_score += 20
        gamma_notes.append("Price is breaking above the opening range / VWAP with upward momentum already in place.")
    if rvol_val is not None and rvol_val >= 1.5:
        gamma_score += 15
        gamma_notes.append("Volume is running {:.1f}x the usual pace at this time of day — real participation, not drift.".format(rvol_val))
    gamma_score = float(np.clip(gamma_score, 0, 100))

    # ---- short squeeze
    short_score = 0.0
    short_notes: List[str] = []
    pct_float = (short_interest or {}).get("percent_of_float")
    days_to_cover = (short_interest or {}).get("days_to_cover")
    if pct_float is not None:
        if pct_float >= 0.20:
            short_score += 40
            short_notes.append("{:.0f}% of float is short — a crowded position with real fuel if it reverses.".format(pct_float * 100))
        elif pct_float >= 0.10:
            short_score += 20
            short_notes.append("{:.0f}% of float is short — meaningful but not extreme.".format(pct_float * 100))
    if days_to_cover is not None and days_to_cover >= 4:
        short_score += 20
        short_notes.append("{:.1f} days to cover — shorts can't exit quickly, which is what makes a squeeze violent once it starts.".format(days_to_cover))
    if breaking_up and trend == "up":
        short_score += 25
        short_notes.append("Price is already breaking higher, which is the trigger a squeeze needs.")
    if rvol_val is not None and rvol_val >= 1.5:
        short_score += 15
        short_notes.append("Elevated volume is consistent with covering activity, not just drift.")
    short_score = float(np.clip(short_score, 0, 100))

    return {
        "gamma_squeeze_score": round(gamma_score, 0),
        "gamma_squeeze_notes": gamma_notes,
        "short_squeeze_score": round(short_score, 0),
        "short_squeeze_notes": short_notes,
        "breaking_up": breaking_up,
        "breaking_down": breaking_down,
        "headline": _squeeze_headline(gamma_score, short_score),
    }


def _squeeze_headline(gamma_score: float, short_score: float) -> str:
    if gamma_score >= 60 and short_score >= 60:
        return "Both gamma and short-covering dynamics are lined up — the highest-energy setup this panel flags."
    if gamma_score >= 60:
        return "Gamma squeeze conditions are in place — dealer hedging is set up to amplify a move, not fade it."
    if short_score >= 60:
        return "Short squeeze conditions are in place — a crowded, slow-to-cover short position sits under a breaking price."
    if gamma_score >= 35 or short_score >= 35:
        return "Partial squeeze conditions — worth watching, not yet a full setup."
    return "No squeeze conditions detected right now."


# ------------------------------------------------------------------ assembly


def analyse(
    provider: Any,
    yf_provider: Any,
    ticker: str,
    quote: Dict[str, Any],
    rate: float = 0.0,
) -> Dict[str, Any]:
    """Full scalping panel for one ticker.

    ``provider`` is whatever is currently active for real-time-sensitive data
    (Tradier if configured, yfinance otherwise) — used for intraday bars and
    the options chain. ``yf_provider`` is always yfinance, used for short
    interest the same way the rest of the app does.
    """
    realtime = getattr(provider, "name", "") == "tradier"

    intraday = provider.intraday_history(ticker, period="5d", interval="1m")
    current, prior = _session_frames(intraday)
    if current.empty:
        return {"error": "No intraday data available for {} (markets may be closed, or this symbol has no minute-bar history).".format(ticker)}

    spot = quote.get("price") or _f(current["Close"].iloc[-1])
    div = quote.get("dividend_yield") or 0.0

    vwap_series = _vwap(current)
    vwap_now = _f(vwap_series.dropna().iloc[-1], 2) if not vwap_series.dropna().empty else None
    opening_range = _opening_range(current, 15)
    pivots = _pivots(prior[-1] if prior else None)
    rvol = _rvol(current, prior)
    momentum = _fast_momentum(current)

    available_expiries = provider.expirations(ticker)
    front = _front_expiry(available_expiries)

    near_gex: Dict[str, Any] = {"error": "no options chain"}
    liquidity: Dict[str, Any] = {}
    if front is not None:
        chain = provider.options_chain(ticker, expiries=[front["expiry"]], max_expiries=1)
        if chain is not None and not chain.empty:
            near_gex = _near_term_gex(chain, spot, rate, div)
            exposure = near_gex.pop("_exposure_frame", None)
            if exposure is not None:
                liquidity = _liquidity_read(exposure, spot)

    short_interest = {}
    try:
        raw_short = yf_provider.short_interest(ticker)
        short_interest = analyse_short_interest(raw_short, quote.get("avg_volume"))
    except Exception:
        short_interest = {}

    squeeze = _squeeze_read(
        near_gex if not near_gex.get("error") else {"regime": None, "spot": spot, "flip_distance_pct": None},
        momentum, rvol, opening_range, short_interest, vwap_now,
    )

    price_vs_vwap_pct = _f((spot / vwap_now - 1.0) * 100.0, 3) if vwap_now else None

    return {
        "ticker": ticker.upper(),
        "realtime": realtime,
        "data_caveat": (
            "Intraday bars and the options chain are real-time via Tradier — this tab is suitable for live use."
            if realtime else
            "Intraday bars and quotes are delayed like the rest of this feed (yfinance), not true real-time. "
            "Treat this tab as a structural read of intraday levels and dealer positioning, not a live execution "
            "tool. Configure a Tradier access token to make it real-time."
        ),
        "spot": _f(spot, 2),
        "session_date": str(current.index[0].date()),
        "bars_so_far": int(len(current)),
        "vwap": vwap_now,
        "price_vs_vwap_pct": price_vs_vwap_pct,
        "opening_range": opening_range,
        "pivots": pivots,
        "rvol": rvol,
        "momentum": momentum,
        "front_expiry": front,
        "near_term_gex": near_gex,
        "liquidity": liquidity,
        "squeeze": squeeze,
        "short_interest": short_interest,
    }
