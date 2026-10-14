"""American-exercise prices for listed equity and ETF options (Options audit O2).

Every listed US equity and ETF option, SPY's included, can be exercised early;
only the cash-settled index options (SPX, NDX, RUT, XSP) are European. A
European model underprices an American put whenever the interest on the strike
is worth more than the time value left (deep in the money, rates at 4%), and an
American call on a dividend payer just before the ex-date. Solving IV from such
a price with Black-Scholes inflates it, which is the error this module removes.

`baw` is the Barone-Adesi & Whaley (1987) quadratic approximation with a
continuous dividend yield, vectorised, in the form Haug (The Complete Guide to
Option Pricing Formulas, 2nd ed., ch. 3.1) gives with its seed values. `crr` is
a Cox-Ross-Rubinstein tree kept as the reference the tests hold it to; it is too
slow to sit inside an IV solve over a whole chain.

Limits, said where they are shown: a continuous yield stands in for discrete
dividends, so the call premium around a single ex-date is smoothed across the
contract's life; against a 3,000-step tree the approximation is within 0.5% of
price or $0.10, whichever is larger, from one day to six months out (the worst
case, a deep in-the-money 60%-vol put, $0.10 on $32.63), and drifts to about 2%
on long-dated out-of-the-money puts, where BAW is known to be weakest."""
from __future__ import annotations

from typing import Any

import numpy as np
from scipy.special import ndtr

_SQRT_2PI = np.sqrt(2.0 * np.pi)
NEWTON_ITERS = 12


def _pdf(x):
    return np.exp(-0.5 * x * x) / _SQRT_2PI


def _euro(s, k, t, v, r, q, is_call):
    vs = v * np.sqrt(t)
    d1 = (np.log(s / k) + (r - q + 0.5 * v * v) * t) / vs
    d2 = d1 - vs
    dq, dr = np.exp(-q * t), np.exp(-r * t)
    call = s * dq * ndtr(d1) - k * dr * ndtr(d2)
    put = k * dr * ndtr(-d2) - s * dq * ndtr(-d1)
    return np.where(is_call, call, put), d1


def _d1(s, k, t, v, r, q):
    return (np.log(s / k) + (r - q + 0.5 * v * v) * t) / (v * np.sqrt(t))


def _call_critical(k, t, v, r, q):
    b = r - q
    v2 = v * v
    m, n = 2.0 * r / v2, 2.0 * b / v2
    kk = 1.0 - np.exp(-r * t)
    q2 = (-(n - 1.0) + np.sqrt((n - 1.0) ** 2 + 4.0 * m / kk)) / 2.0
    q2_inf = (-(n - 1.0) + np.sqrt((n - 1.0) ** 2 + 4.0 * m)) / 2.0
    s_inf = k / (1.0 - 1.0 / q2_inf)
    h2 = -(b * t + 2.0 * v * np.sqrt(t)) * k / (s_inf - k)
    si = k + (s_inf - k) * (1.0 - np.exp(h2))
    dq = np.exp(-q * t)
    vs = v * np.sqrt(t)
    for _ in range(NEWTON_ITERS):
        euro, d1 = _euro(si, k, t, v, r, q, True)
        rhs = euro + (1.0 - dq * ndtr(d1)) * si / q2
        bi = dq * ndtr(d1) * (1.0 - 1.0 / q2) + (1.0 - dq * _pdf(d1) / vs) / q2
        den = 1.0 - bi
        with np.errstate(divide="ignore", invalid="ignore"):
            nxt = (k + rhs - bi * si) / den
        si = np.where(np.isfinite(nxt) & (np.abs(den) > 1e-12), np.maximum(nxt, k * (1.0 + 1e-9)), si)
    return si, q2


def _put_critical(k, t, v, r, q):
    b = r - q
    v2 = v * v
    m, n = 2.0 * r / v2, 2.0 * b / v2
    kk = 1.0 - np.exp(-r * t)
    q1 = (-(n - 1.0) - np.sqrt((n - 1.0) ** 2 + 4.0 * m / kk)) / 2.0
    q1_inf = (-(n - 1.0) - np.sqrt((n - 1.0) ** 2 + 4.0 * m)) / 2.0
    s_inf = k / (1.0 - 1.0 / q1_inf)
    h1 = (b * t - 2.0 * v * np.sqrt(t)) * k / (k - s_inf)
    si = s_inf + (k - s_inf) * np.exp(h1)
    dq = np.exp(-q * t)
    vs = v * np.sqrt(t)
    for _ in range(NEWTON_ITERS):
        euro, d1 = _euro(si, k, t, v, r, q, False)
        rhs = euro - (1.0 - dq * ndtr(-d1)) * si / q1
        bi = -dq * ndtr(-d1) * (1.0 - 1.0 / q1) - (1.0 + dq * _pdf(-d1) / vs) / q1
        den = 1.0 + bi
        with np.errstate(divide="ignore", invalid="ignore"):
            nxt = (k - rhs + bi * si) / den
        si = np.where(np.isfinite(nxt) & (np.abs(den) > 1e-12), np.clip(nxt, 1e-9 * k, k * (1.0 - 1e-9)), si)
    return si, q1


def baw(spot: Any, strike: Any, tau: Any, vol: Any, rate: float, div: float, is_call: Any) -> np.ndarray:
    """American option value per share, vectorised over every argument but
    the rate and yield. Never below the European value or intrinsic."""
    s, k, t, v, c = np.broadcast_arrays(np.asarray(spot, float), np.asarray(strike, float),
                                        np.maximum(np.asarray(tau, float), 1e-8),
                                        np.maximum(np.asarray(vol, float), 1e-6),
                                        np.asarray(is_call, bool))
    r, q = float(rate), float(div)
    euro, _ = _euro(s, k, t, v, r, q, c)
    out = euro.copy()
    # A call is exercised early only for the dividend (q > 0); a put only for
    # the interest on the strike (r > 0). Otherwise American = European.
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        out = _early(out, euro, s, k, t, v, c, r, q)
    intrinsic = np.where(c, s - k, k - s)
    # A critical price that did not converge falls back to the European value
    # (a lower bound), never to NaN.
    out = np.where(np.isfinite(out), out, euro)
    return np.maximum(np.maximum(out, euro), np.maximum(intrinsic, 0.0))


def _early(out, euro, s, k, t, v, c, r, q):
    if q > 0 and c.any():
        idx = c
        si, q2 = _call_critical(k[idx], t[idx], v[idx], r, q)
        d1 = _d1(si, k[idx], t[idx], v[idx], r, q)
        a2 = (si / q2) * (1.0 - np.exp(-q * t[idx]) * ndtr(d1))
        sv = s[idx]
        out[idx] = np.where(sv < si, euro[idx] + a2 * (sv / si) ** q2, sv - k[idx])
    if r > 0 and (~c).any():
        idx = ~c
        si, q1 = _put_critical(k[idx], t[idx], v[idx], r, q)
        d1 = _d1(si, k[idx], t[idx], v[idx], r, q)
        a1 = -(si / q1) * (1.0 - np.exp(-q * t[idx]) * ndtr(-d1))
        sv = s[idx]
        out[idx] = np.where(sv > si, euro[idx] + a1 * (sv / si) ** q1, k[idx] - sv)
    return out


def early_exercise_premium(spot, strike, tau, vol, rate, div, is_call) -> np.ndarray:
    """American minus European at the same inputs, per share (>= 0)."""
    euro, _ = _euro(*np.broadcast_arrays(np.asarray(spot, float), np.asarray(strike, float),
                                         np.maximum(np.asarray(tau, float), 1e-8),
                                         np.maximum(np.asarray(vol, float), 1e-6)),
                    float(rate), float(div), np.asarray(is_call, bool))
    return np.maximum(baw(spot, strike, tau, vol, rate, div, is_call) - euro, 0.0)


def crr(spot: float, strike: float, tau: float, vol: float, rate: float, div: float,
        is_call: bool, steps: int = 2000) -> float:
    """Cox-Ross-Rubinstein American value: the reference, not the workhorse."""
    dt = tau / steps
    u = np.exp(vol * np.sqrt(dt))
    d = 1.0 / u
    p = (np.exp((rate - div) * dt) - d) / (u - d)
    disc = np.exp(-rate * dt)
    j = np.arange(steps + 1)
    prices = spot * u ** (steps - 2 * j)
    values = np.maximum(prices - strike, 0.0) if is_call else np.maximum(strike - prices, 0.0)
    for i in range(steps - 1, -1, -1):
        prices = prices[:-1] * d
        cont = disc * (p * values[:-1] + (1.0 - p) * values[1:])
        ex = prices - strike if is_call else strike - prices
        values = np.maximum(cont, ex)
    return float(values[0])
