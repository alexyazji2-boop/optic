"""Black-Scholes greeks and implied-volatility solving.

Everything here is pure-numeric and vectorised over numpy arrays so a whole
options chain can be priced in one shot. Rates/dividends are continuous.
"""

from __future__ import annotations

import math
from typing import Dict, Optional

import numpy as np

SQRT_2PI = math.sqrt(2.0 * math.pi)


def _norm_pdf(x: np.ndarray) -> np.ndarray:
    return np.exp(-0.5 * np.square(x)) / SQRT_2PI


def _norm_cdf(x: np.ndarray) -> np.ndarray:
    # erf is vectorised via numpy's ufunc on the scipy-free path
    return 0.5 * (1.0 + np.vectorize(math.erf)(x / math.sqrt(2.0)))


def _sanitise(
    spot: float,
    strike: np.ndarray,
    tau: np.ndarray,
    vol: np.ndarray,
):
    """Clamp inputs into a domain where Black-Scholes is well defined."""
    strike = np.asarray(strike, dtype=float)
    tau = np.asarray(tau, dtype=float)
    vol = np.asarray(vol, dtype=float)

    strike = np.where(strike <= 0, np.nan, strike)
    # Expiry day options: floor at ~1 hour so gamma stays finite instead of
    # exploding to infinity at the money.
    tau = np.clip(tau, 1.0 / (365.0 * 24.0), None)
    vol = np.clip(vol, 1e-4, 5.0)
    return float(spot), strike, tau, vol


def d1_d2(spot, strike, tau, vol, rate=0.0, div=0.0):
    spot, strike, tau, vol = _sanitise(spot, strike, tau, vol)
    vsqrt = vol * np.sqrt(tau)
    d1 = (np.log(spot / strike) + (rate - div + 0.5 * vol * vol) * tau) / vsqrt
    return d1, d1 - vsqrt


def greeks(
    spot: float,
    strike: np.ndarray,
    tau: np.ndarray,
    vol: np.ndarray,
    rate: float = 0.0,
    div: float = 0.0,
    is_call: Optional[np.ndarray] = None,
) -> Dict[str, np.ndarray]:
    """Full greek set for an array of contracts.

    ``tau`` is in years, ``vol`` is annualized. ``is_call`` is a boolean array;
    when omitted every contract is treated as a call.

    Conventions:
      delta   per $1 of spot, per share
      gamma   per $1 of spot (dDelta/dSpot)
      vega    per 1 volatility point (i.e. already divided by 100)
      theta   per calendar day
      rho     per 1% rate move
    """
    spot_f, k, t, v = _sanitise(spot, strike, tau, vol)
    if is_call is None:
        is_call = np.ones_like(k, dtype=bool)
    is_call = np.asarray(is_call, dtype=bool)

    d1, d2 = d1_d2(spot_f, k, t, v, rate, div)
    pdf_d1 = _norm_pdf(d1)
    disc_r = np.exp(-rate * t)
    disc_q = np.exp(-div * t)
    sqrt_t = np.sqrt(t)

    call_delta = disc_q * _norm_cdf(d1)
    delta = np.where(is_call, call_delta, call_delta - disc_q)

    gamma = disc_q * pdf_d1 / (spot_f * v * sqrt_t)
    vega = spot_f * disc_q * pdf_d1 * sqrt_t / 100.0

    common_theta = -spot_f * disc_q * pdf_d1 * v / (2.0 * sqrt_t)
    call_theta = (
        common_theta
        - rate * k * disc_r * _norm_cdf(d2)
        + div * spot_f * disc_q * _norm_cdf(d1)
    )
    put_theta = (
        common_theta
        + rate * k * disc_r * _norm_cdf(-d2)
        - div * spot_f * disc_q * _norm_cdf(-d1)
    )
    theta = np.where(is_call, call_theta, put_theta) / 365.0

    rho_call = k * t * disc_r * _norm_cdf(d2) / 100.0
    rho_put = -k * t * disc_r * _norm_cdf(-d2) / 100.0
    rho = np.where(is_call, rho_call, rho_put)

    # Second-order: vanna (dDelta/dVol) and charm (dDelta/dTime, per day).
    vanna = -disc_q * pdf_d1 * d2 / v / 100.0
    charm_call = disc_q * (
        div * _norm_cdf(d1) - pdf_d1 * (2.0 * (rate - div) * t - d2 * v * sqrt_t) / (2.0 * t * v * sqrt_t)
    )
    charm_put = disc_q * (
        -div * _norm_cdf(-d1)
        - pdf_d1 * (2.0 * (rate - div) * t - d2 * v * sqrt_t) / (2.0 * t * v * sqrt_t)
    )
    charm = np.where(is_call, charm_call, charm_put) / 365.0

    return {
        "delta": delta,
        "gamma": gamma,
        "vega": vega,
        "theta": theta,
        "rho": rho,
        "vanna": vanna,
        "charm": charm,
        "d1": d1,
        "d2": d2,
    }


def bs_price(spot, strike, tau, vol, rate=0.0, div=0.0, is_call=True):
    spot_f, k, t, v = _sanitise(spot, strike, tau, vol)
    d1, d2 = d1_d2(spot_f, k, t, v, rate, div)
    disc_r = np.exp(-rate * t)
    disc_q = np.exp(-div * t)
    call = spot_f * disc_q * _norm_cdf(d1) - k * disc_r * _norm_cdf(d2)
    put = k * disc_r * _norm_cdf(-d2) - spot_f * disc_q * _norm_cdf(-d1)
    return np.where(np.asarray(is_call, dtype=bool), call, put)


def implied_vol(
    price: float,
    spot: float,
    strike: float,
    tau: float,
    rate: float = 0.0,
    div: float = 0.0,
    is_call: bool = True,
) -> float:
    """Bisection IV solve. Used only to backfill contracts with a missing or
    obviously broken IV from the feed."""
    if not np.isfinite(price) or price <= 0 or tau <= 0:
        return float("nan")

    intrinsic = max(0.0, (spot - strike) if is_call else (strike - spot))
    if price < intrinsic * math.exp(-rate * tau) - 1e-6:
        return float("nan")

    lo, hi = 1e-4, 5.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        model = float(bs_price(spot, np.array([strike]), np.array([tau]), np.array([mid]), rate, div, is_call)[0])
        if model > price:
            hi = mid
        else:
            lo = mid
        if hi - lo < 1e-6:
            break
    iv = 0.5 * (lo + hi)
    return float("nan") if iv >= 4.99 or iv <= 1.1e-4 else iv
