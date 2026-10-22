"""Portfolio-level risk: are these separate bets, or one bet with several tickets?

Optic Portfolio reports each trade on its own — entry, stop, target, risk in
dollars. That is the right view for managing a position and the wrong view for
managing a book. Six longs in semiconductors have six stops and one outcome, and
nothing in a per-trade ledger will ever say so.

The headline here is the **diversification ratio**: the weighted-average
volatility of the individual holdings divided by the volatility of the portfolio
that actually holds them. Independent positions partly cancel, so the portfolio
is calmer than its parts and the ratio rises above 1. A ratio near 1.0 means
nothing is cancelling — the positions move together, and the book is one bet
however many tickets it holds.

Two things this deliberately does not do.

**It does not add up stop losses and call that the risk.** Summing per-trade
risk assumes the stops are hit independently. They are not: correlated positions
gap together, which is precisely when several stops fill at once. The summed
figure is reported because it is what the ledger says, alongside the correlation
that makes it optimistic.

**It does not forecast.** Correlation is measured over a trailing window and is
famously unstable — it rises in exactly the drawdowns where diversification was
supposed to help. The window is stated, and the number is a description of the
recent past.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import numpy as np

from .greeks import greeks as _greeks, implied_vol as _implied_vol

log = logging.getLogger(__name__)

# Trailing window for the return covariance, in sessions. About a quarter —
# long enough to be estimable across a dozen names, short enough to describe
# the regime the book is actually in.
WINDOW = 63

# A pair this correlated is doing the same job.
HIGH_PAIR = 0.70
# Below this diversification ratio, the book is effectively concentrated.
LOW_DIVERSIFICATION = 1.15

# A single sector above this share is a concentration regardless of what
# trailing correlation says. Small-cap biotech is the case that proved it: nine
# names, 60% healthcare, and a highest pairwise correlation of 0.52 — because
# each moves on its own binary catalyst. Daily correlation genuinely is low, and
# a single FDA or reimbursement decision still hits all of them at once. Measured
# co-movement and shared exposure are different risks, and a book can carry the
# second while looking clean on the first.
HEAVY_SECTOR_PCT = 40.0

# Trading days per year, for annualising.
YEAR = 252


def _num(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if out != out or out in (float("inf"), float("-inf")) else out


# ------------------------------------------------------------ option exposure
#
# An option contract was weighted as one share of its stock (pitch audit,
# 2026-10-22): a standard contract covers 100 shares, and how much of them it
# moves like is its delta. Three figures are kept apart, because each answers a
# different question: premium at risk (the most a long option can lose),
# notional (multiplier x contracts x the stock's price, the size of what it
# controls) and delta exposure (the stock-equivalent dollars it moves like
# today, which is what the covariance below can use). The last is a linear
# snapshot of something that is not linear: it changes as the stock moves and
# as expiry nears, and it says nothing about a gap through the strike.

STANDARD_MULTIPLIER = 100.0


def _today() -> date:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York")).date()
    except Exception:
        return date.today()


def option_exposure(p: Dict[str, Any], spot: Optional[float], today: Optional[date] = None) -> Dict[str, Any]:
    """Premium at risk, notional and delta exposure for one option position.

    `multiplier` (shares per contract) comes from the position when it carries
    one, as an adjusted contract after a split or merger does; otherwise the
    standard 100 is assumed and said. Delta comes from the position when it
    carries one, otherwise from Black-Scholes at the implied volatility its own
    mark solves to. With neither, delta is None and the position is reported as
    not covered rather than guessed.
    """
    today = today or _today()
    qty = _num(p.get("qty")) or 0.0
    mult = _num(p.get("multiplier"))
    mult_basis = "position" if mult else "standard contract assumed"
    mult = mult or STANDARD_MULTIPLIER
    sign = -1.0 if str(p.get("direction") or "long").lower() in ("short", "sell") else 1.0
    is_call = str(p.get("option_type") or "").lower() == "call"
    strike = _num(p.get("strike"))
    premium = _num(p.get("mark_price")) or _num(p.get("entry_price"))
    spot = _num(spot) or _num(p.get("mark_spot")) or _num(p.get("entry_spot"))
    out: Dict[str, Any] = {
        "multiplier": mult, "multiplier_basis": mult_basis,
        "premium_per_share": premium,
        # A short option can lose far more than the premium it took in
        "premium_at_risk": round(premium * qty * mult, 2) if premium and sign > 0 else None,
        "notional": round(spot * qty * mult, 2) if spot else None,
        "delta": None, "delta_basis": None, "delta_exposure": None, "uncovered_reason": None,
    }
    delta = _num(p.get("delta"))
    if delta is not None:
        out["delta_basis"] = "position"
    else:
        try:
            expiry = datetime.fromisoformat(str(p.get("expiry"))[:10]).date()
        except (TypeError, ValueError):
            expiry = None
        tau = ((expiry - today).days / 365.0) if expiry else None
        if not (spot and strike and premium and tau and tau > 0):
            out["uncovered_reason"] = ("at or past expiry" if tau is not None and tau <= 0
                                       else "missing strike, expiry, price or mark")
            return out
        iv = _implied_vol(premium, spot, strike, tau, 0.0, 0.0, is_call)
        if not np.isfinite(iv):
            out["uncovered_reason"] = "no implied volatility solves to its mark"
            return out
        delta = float(_greeks(spot, np.array([strike]), np.array([tau]), np.array([iv]),
                              0.0, 0.0, np.array([is_call]))["delta"][0])
        out["delta_basis"] = "Black-Scholes at the mark's implied volatility ({:.0f}%), zero rate".format(iv * 100)
    out["delta"] = round(delta, 3)
    out["delta_exposure"] = round(sign * delta * spot * qty * mult, 2) if spot else None
    return out


def build(provider, positions: List[Dict[str, Any]], today: Optional[date] = None) -> Dict[str, Any]:
    """Concentration and correlation across the open book."""
    rows = []
    for p in (positions or []):
        sym = str(p.get("ticker") or "").upper().strip()
        qty, price = _num(p.get("qty")), _num(p.get("entry_price"))
        if not sym or qty is None or price is None or qty <= 0 or price <= 0:
            continue
        rows.append({"symbol": sym, "qty": qty, "entry_price": price,
                     "direction": (p.get("direction") or "long").lower(),
                     "instrument": p.get("instrument") or "shares",
                     "risk_dollars": _num(p.get("risk_dollars")) or 0.0, "raw": p})
    if not rows:
        return {"available": False, "reason": "No open positions to analyse."}

    symbols = sorted({r["symbol"] for r in rows})
    try:
        frames = provider.batch_history(symbols, period="6mo", interval="1d") or {}
    except Exception as exc:                     # noqa: BLE001
        return {"available": False, "reason": "Price history unavailable: {}".format(exc)}

    # Current value per position, and the sector it sits in.
    closes: Dict[str, Any] = {}
    for sym in symbols:
        f = frames.get(sym)
        if f is not None and not f.empty:
            closes[sym] = f["Close"].dropna()

    by_symbol: Dict[str, Dict[str, Any]] = {}
    options_out: List[Dict[str, Any]] = []
    for r in rows:
        last = _num(closes[r["symbol"]].iloc[-1]) if r["symbol"] in closes else None
        if r["instrument"] == "option":
            ex = option_exposure(r["raw"], last, today)
            p = r["raw"]
            options_out.append({"symbol": r["symbol"], "option_type": p.get("option_type"), "strike": _num(p.get("strike")),
                                "expiry": p.get("expiry"), "contracts": r["qty"], "direction": r["direction"], **ex})
            if ex["delta_exposure"] is None:
                continue                           # reported as not covered, never guessed
            value = abs(ex["delta_exposure"])
            signed = ex["delta_exposure"]          # a long put is negative, a short call negative
        else:
            value = (last or r["entry_price"]) * r["qty"]
            # A short position carries the opposite exposure, so its weight is
            # signed — netting a long and a short in the same name to zero is the
            # correct answer, and summing their absolute values is not.
            signed = -value if r["direction"] in ("short", "sell") else value
        slot = by_symbol.setdefault(r["symbol"], {
            "symbol": r["symbol"], "value": 0.0, "signed_value": 0.0,
            "risk_dollars": 0.0, "positions": 0})
        slot["value"] += value
        slot["signed_value"] += signed
        slot["risk_dollars"] += r["risk_dollars"]
        slot["positions"] += 1
    uncovered = [o for o in options_out if o["delta_exposure"] is None]
    if not by_symbol:
        return {"available": False, "reason": "No position has a measurable exposure.",
                "options": options_out}

    gross = sum(abs(s["signed_value"]) for s in by_symbol.values())
    if gross <= 0:
        return {"available": False, "reason": "Positions carry no measurable value."}

    for s in by_symbol.values():
        s["weight"] = s["signed_value"] / gross
        s["weight_pct"] = round(s["weight"] * 100.0, 2)

    # Sector exposure, so "six semiconductor longs" is visible as one line.
    for s in by_symbol.values():
        try:
            prof = provider.profile(s["symbol"]) or {}
            s["sector"] = prof.get("sector") or "Unclassified"
            s["industry"] = prof.get("industry")
        except Exception:
            s["sector"] = "Unclassified"

    sectors: Dict[str, float] = {}
    for s in by_symbol.values():
        sectors[s["sector"]] = sectors.get(s["sector"], 0.0) + abs(s["weight"])
    sector_rows = sorted(
        ({"sector": k, "weight_pct": round(v * 100.0, 1)} for k, v in sectors.items()),
        key=lambda x: -x["weight_pct"])

    # --- correlation and portfolio volatility --------------------------------
    usable = [s for s in by_symbol.values()
              if s["symbol"] in closes and len(closes[s["symbol"]]) > WINDOW]
    matrix, pairs, diversification, port_vol, weighted_vol = None, [], None, None, None

    if len(usable) >= 2:
        rets = {}
        for s in usable:
            series = closes[s["symbol"]].tail(WINDOW + 1)
            rets[s["symbol"]] = np.diff(np.log(series.to_numpy(dtype=float)))
        n = min(len(v) for v in rets.values())
        syms = [s["symbol"] for s in usable]
        R = np.vstack([rets[k][-n:] for k in syms])

        with np.errstate(invalid="ignore", divide="ignore"):
            corr = np.corrcoef(R)
        corr = np.nan_to_num(corr, nan=0.0)
        cov = np.cov(R) * YEAR

        w = np.array([s["weight"] for s in usable], dtype=float)
        # Renormalise across the names that had usable history, so a missing
        # symbol does not silently shrink the measured portfolio.
        if abs(w).sum() > 0:
            w = w / abs(w).sum()

        port_var = float(w @ cov @ w)
        port_vol = float(np.sqrt(max(port_var, 0.0))) * 100.0
        vols = np.sqrt(np.clip(np.diag(cov), 0, None))
        weighted_vol = float(np.abs(w) @ vols) * 100.0
        diversification = (weighted_vol / port_vol) if port_vol > 0 else None

        matrix = {"symbols": syms,
                  "values": [[round(float(corr[i][j]), 3) for j in range(len(syms))]
                             for i in range(len(syms))]}
        for i in range(len(syms)):
            for j in range(i + 1, len(syms)):
                pairs.append({"a": syms[i], "b": syms[j],
                              "correlation": round(float(corr[i][j]), 3)})
        pairs.sort(key=lambda p: -abs(p["correlation"]))

        # Marginal contribution to portfolio variance — where the risk actually
        # sits, which is not the same as where the money sits.
        if port_vol > 0:
            mc = (cov @ w) / (port_var ** 0.5)
            for s, contrib, weight in zip(usable, mc, w):
                s["risk_contribution_pct"] = round(float(weight * contrib)
                                                   / (port_var ** 0.5) * 100.0, 1)

    positions_out = sorted(by_symbol.values(), key=lambda s: -abs(s["weight"]))
    weights = np.array([abs(s["weight"]) for s in positions_out])
    hhi = float((weights ** 2).sum())
    effective_bets = (1.0 / hhi) if hhi > 0 else None

    high_pairs = [p for p in pairs if abs(p["correlation"]) >= HIGH_PAIR]
    concentrated = diversification is not None and diversification < LOW_DIVERSIFICATION
    # "Unclassified" is missing data, not a sector: a shock to it is not a thing.
    heavy = [s for s in sector_rows
             if s["weight_pct"] >= HEAVY_SECTOR_PCT and s["sector"] != "Unclassified"]

    if concentrated:
        verdict = (
            "These positions are mostly one bet. The book's volatility is barely "
            "below the average of its parts, which means they are moving together "
            "and the diversification is nominal."
        )
    elif diversification is None:
        verdict = ("Not enough overlapping history to measure how these positions "
                   "move together.")
    else:
        verdict = (
            "The positions are partly offsetting: the book is meaningfully calmer "
            "than the average of the names in it."
        )

    # Reported separately from the correlation verdict on purpose. A book can be
    # genuinely uncorrelated day to day and still be one decision away from a
    # common shock, and only naming both keeps that visible.
    sector_warning = None
    if heavy:
        top = heavy[0]
        sector_warning = (
            "{} is {:.0f}% of this book. Trailing correlation between the names is "
            "{}, so day to day they are not moving together, but a shock to the "
            "sector itself, a regulatory decision or a rate move that repriced the "
            "whole group, would not care about that. Shared exposure and measured "
            "co-movement are different risks."
            .format(top["sector"], top["weight_pct"],
                    "low" if not high_pairs else "already high in places")
        )

    return {
        "available": True,
        "positions": positions_out,
        "names": len(positions_out),
        "option_positions": len(options_out),
        "exposure_basis": ("Shares at market value. Each option at its delta exposure: delta x the "
                           "stock's price x contracts x shares per contract."),
        "options": options_out,
        "options_uncovered": len(uncovered),
        "option_premium_at_risk": round(sum(o["premium_at_risk"] or 0.0 for o in options_out), 2),
        "option_notional": round(sum(o["notional"] or 0.0 for o in options_out), 2),
        "option_note": (
            "{} option position{} weighted by delta exposure, the stock-equivalent dollars {} moves "
            "like today. Delta changes as the stock moves and as expiry nears, so these weights "
            "and the volatility above are a snapshot of a nonlinear position, and say nothing about "
            "a gap through a strike.{}".format(
                len(options_out) - len(uncovered), "" if len(options_out) - len(uncovered) == 1 else "s",
                "it" if len(options_out) - len(uncovered) == 1 else "each",
                " {} left out: no delta could be found ({}).".format(
                    len(uncovered), "; ".join(sorted({o["uncovered_reason"] for o in uncovered})))
                if uncovered else "")
        ) if options_out else None,
        "gross_exposure": round(gross, 2),
        "net_exposure": round(sum(s["signed_value"] for s in by_symbol.values()), 2),
        "sectors": sector_rows,
        "largest_weight_pct": positions_out[0]["weight_pct"] if positions_out else None,
        "top3_weight_pct": round(sum(abs(s["weight"]) for s in positions_out[:3]) * 100.0, 1),
        "hhi": round(hhi, 4),
        # 1/HHI: how many equally-sized positions would give this concentration.
        # Ten names with one holding at 80% is not ten bets, and this says so.
        "effective_positions": round(effective_bets, 1) if effective_bets else None,
        "correlation": matrix,
        "window_sessions": WINDOW,
        "top_pairs": pairs[:8],
        "high_correlation_pairs": high_pairs,
        "portfolio_vol_pct": round(port_vol, 1) if port_vol else None,
        "weighted_avg_vol_pct": round(weighted_vol, 1) if weighted_vol else None,
        "diversification_ratio": round(diversification, 2) if diversification else None,
        "concentrated": concentrated,
        "heavy_sectors": heavy,
        "sector_warning": sector_warning,
        "verdict": verdict,
        "summed_stop_risk": round(sum(s["risk_dollars"] for s in by_symbol.values()), 2),
        "summed_risk_note": (
            "This is what the ledger says, and it assumes the stops are hit "
            "independently. They are not. Correlated positions gap together, "
            "which is exactly the session in which several stops fill at once. "
            "Read it against the correlation above, not on its own."
        ),
        "method": (
            "Correlations and volatilities are computed from {} sessions of daily "
            "log returns and annualised. The diversification ratio is the "
            "weighted-average volatility of the holdings divided by the volatility "
            "of the portfolio holding them: 1.0 means nothing is cancelling. "
            "Correlation is measured over a trailing window and is unstable. It "
            "rises in the drawdowns where diversification was supposed to help, so "
            "this describes the recent past rather than forecasting the next one."
            .format(WINDOW)
        ),
    }
