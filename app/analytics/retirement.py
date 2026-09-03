"""Roth IRA model allocation from long-run fund data.

This is a calculator, not advice. It takes the user's horizon and risk tolerance
as inputs, measures a fixed universe of broad, low-cost funds over ten years, and
applies a published-style glidepath to produce a model allocation with its
reasoning shown. Nothing here knows the user's income, tax bracket, other
accounts or goals, so every output is framed as a starting point to compare
against, not a recommendation to act on.

Roth-specific reasoning that genuinely changes the answer versus a taxable account:

* Growth compounds tax-free and is never taxed on withdrawal after 59½, so the
  highest-expected-return assets are the ones that benefit most from the space.
* Dividends and fund distributions aren't taxed year to year, which makes
  otherwise tax-inefficient holdings (REITs, high-yield) cheapest to own here.
* Losses aren't deductible and there's no tax-loss harvesting, so there's no
  tax reason to hold volatile positions you'd otherwise harvest.
* The annual contribution limit is small, so fragmenting across many funds buys
  complexity rather than diversification.
"""

from __future__ import annotations

from .. import legal as legal_mod

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

# Role drives the allocation logic, so the model can be reasoned about in terms
# of exposures rather than tickers. Expense ratios and yields are read live from
# the feed rather than hardcoded, since they change.
UNIVERSE: List[Dict[str, str]] = [
    {"symbol": "VTI", "role": "us_total", "name": "US total market", "note": "3,500+ US companies, market-cap weighted"},
    {"symbol": "VOO", "role": "us_large", "name": "US large cap (S&P 500)", "note": "the 500 largest US companies"},
    {"symbol": "QQQ", "role": "us_growth", "name": "US large-cap growth", "note": "Nasdaq-100, tech-heavy"},
    {"symbol": "AVUV", "role": "small_value", "name": "US small-cap value", "note": "historically higher return, higher volatility"},
    {"symbol": "VEA", "role": "intl_dev", "name": "International developed", "note": "Europe, Japan, Canada, Australia"},
    {"symbol": "VWO", "role": "intl_em", "name": "Emerging markets", "note": "China, India, Taiwan, Brazil"},
    {"symbol": "SCHD", "role": "dividend", "name": "US dividend equity", "note": "quality screen, higher income"},
    {"symbol": "VNQ", "role": "reit", "name": "US real estate", "note": "REITs. Tax-inefficient outside a Roth"},
    {"symbol": "BND", "role": "bonds", "name": "US total bond market", "note": "ballast, dampens drawdowns"},
    {"symbol": "GLD", "role": "gold", "name": "Gold", "note": "crisis hedge, no cash flow"},
]

BY_ROLE = {f["role"]: f for f in UNIVERSE}

TRADING_DAYS = 252


def _f(value: Any, digits: int = 4) -> Optional[float]:
    try:
        if value is None:
            return None
        out = float(value)
        if not np.isfinite(out):
            return None
        return round(out, digits)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ fund stats


def _fund_stats(frame: pd.DataFrame) -> Dict[str, Any]:
    """Long-run return and risk for one fund."""
    if frame is None or frame.empty or "Close" not in frame:
        return {}
    closes = frame["Close"].dropna()
    if len(closes) < TRADING_DAYS:
        return {}

    values = closes.to_numpy()
    years = len(values) / TRADING_DAYS

    def cagr(n_years: int) -> Optional[float]:
        """Annualized return over roughly the requested window.

        Tolerant of a few missing sessions: a "10y" fetch returns about 2,515
        trading days, not the 2,520 a strict 252×10 check would demand, which
        would blank out every 10-year figure. Annualises by the span actually
        measured, and gives up only if the fund is genuinely too young.
        """
        want = int(n_years * TRADING_DAYS)
        n = min(want, len(values) - 1)
        span = n / TRADING_DAYS
        if span < n_years * 0.9:
            return None
        return _f(((values[-1] / values[-n - 1]) ** (1.0 / span) - 1.0) * 100.0, 2)

    daily = np.diff(values) / values[:-1]
    vol = float(np.std(daily, ddof=1) * np.sqrt(TRADING_DAYS) * 100.0)

    peak = np.maximum.accumulate(values)
    dd = (values / peak - 1.0) * 100.0

    full_cagr = _f(((values[-1] / values[0]) ** (1.0 / years) - 1.0) * 100.0, 2)
    # Sharpe at a zero risk-free rate, consistent with the rest of the app —
    # a return-per-unit-of-volatility ratio rather than a true excess-return Sharpe.
    sharpe = _f(full_cagr / vol, 2) if full_cagr and vol else None

    return {
        "years_of_history": _f(years, 1),
        "cagr_full_pct": full_cagr,
        "cagr_10y_pct": cagr(10),
        "cagr_5y_pct": cagr(5),
        "cagr_3y_pct": cagr(3),
        "volatility_pct": _f(vol, 2),
        "return_per_vol": sharpe,
        "max_drawdown_pct": _f(float(dd.min()), 1),
        "current_drawdown_pct": _f(float(dd[-1]), 1),
    }


def _correlations(frames: Dict[str, pd.DataFrame], symbols: List[str]) -> Dict[str, Any]:
    """Correlation of daily returns — the number that decides whether adding a
    fund actually diversifies or just adds another way to own the same risk."""
    series = {}
    for sym in symbols:
        frame = frames.get(sym)
        if frame is None or frame.empty or "Close" not in frame:
            continue
        series[sym] = frame["Close"].pct_change()
    if len(series) < 2:
        return {}
    joined = pd.DataFrame(series).dropna()
    if len(joined) < 120:
        return {}
    corr = joined.corr()
    return {
        "symbols": list(corr.columns),
        "matrix": [[_f(corr.iloc[i, j], 2) for j in range(len(corr.columns))]
                   for i in range(len(corr.columns))],
    }


# ------------------------------------------------------------------ allocation

RISK_TIERS = ("conservative", "balanced", "growth")

# Deliberately higher than the "moderate" threshold used elsewhere in the app:
# this is retirement money in a single company, so a merely-not-bad long-run
# record should not earn a place.
STOCK_CONVICTION_BAR = 30.0


def _glidepath_equity_pct(years: int, risk: str) -> float:
    """Share of the portfolio in equities.

    Rises with horizon because a longer runway means more time to recover from a
    drawdown, then adjusted by stated risk tolerance. Capped at 95% rather than
    100% so there's always something to rebalance from after a crash.
    """
    base = 55.0 + min(years, 35) * 1.15  # 30 years out ≈ 89%
    shift = {"conservative": -12.0, "balanced": 0.0, "growth": +8.0}[risk]
    return float(np.clip(base + shift, 30.0, 95.0))


def _model_allocation(years: int, risk: str) -> Dict[str, Any]:
    """Rules-based target weights, expressed by role then mapped to tickers."""
    equity = _glidepath_equity_pct(years, risk)
    bonds = 100.0 - equity

    # Within equities: a total-market core, then satellites. Growth and small-value
    # tilts scale with horizon, because both need a long runway to pay off and
    # both underperform for years at a stretch.
    tilt_room = min(years, 30) / 30.0
    growth_tilt = {"conservative": 0.0, "balanced": 8.0, "growth": 14.0}[risk] * tilt_room
    small_tilt = {"conservative": 0.0, "balanced": 5.0, "growth": 8.0}[risk] * tilt_room
    intl_share = {"conservative": 30.0, "balanced": 25.0, "growth": 20.0}[risk]

    intl = equity * intl_share / 100.0
    us = equity - intl
    us_growth = us * growth_tilt / 100.0
    us_small = us * small_tilt / 100.0
    us_core = us - us_growth - us_small

    # Conservative sleeves add income and a hedge — both are cheapest to hold in
    # a Roth, where their distributions aren't taxed annually.
    reit = 4.0 if risk != "growth" else 0.0
    gold = 3.0 if risk == "conservative" else 0.0
    bonds = max(bonds - reit - gold, 0.0)

    weights = {
        "us_total": us_core,
        "us_growth": us_growth,
        "small_value": us_small,
        "intl_dev": intl * 0.72,
        "intl_em": intl * 0.28,
        "reit": reit,
        "gold": gold,
        "bonds": bonds,
    }
    weights = {k: v for k, v in weights.items() if v >= 0.5}

    total = sum(weights.values())
    if total:
        weights = {k: v / total * 100.0 for k, v in weights.items()}

    return {
        "equity_pct": _f(equity, 1),
        "bond_pct": _f(100.0 - equity, 1),
        "weights": {k: _f(v, 1) for k, v in weights.items()},
    }


def _allocation_rows(alloc: Dict[str, Any], stats: Dict[str, Dict[str, Any]],
                     meta: Dict[str, Dict[str, Any]], annual: float) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for role, weight in sorted(alloc["weights"].items(), key=lambda kv: -kv[1]):
        fund = BY_ROLE.get(role)
        if not fund:
            continue
        sym = fund["symbol"]
        st = stats.get(sym, {})
        mt = meta.get(sym, {})
        rows.append({
            "symbol": sym,
            "role": role,
            "name": fund["name"],
            "note": fund["note"],
            "weight_pct": weight,
            "annual_dollars": _f(annual * weight / 100.0, 0),
            "expense_ratio_pct": mt.get("expense_ratio_pct"),
            "yield_pct": mt.get("yield_pct"),
            "cagr_10y_pct": st.get("cagr_10y_pct"),
            "cagr_full_pct": st.get("cagr_full_pct"),
            "years_of_history": st.get("years_of_history"),
            "volatility_pct": st.get("volatility_pct"),
            "max_drawdown_pct": st.get("max_drawdown_pct"),
        })
    return rows


def _blended(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Weighted portfolio characteristics.

    Blended volatility here is the weighted average of each holding's volatility,
    which overstates the real figure because it ignores the diversification
    benefit of imperfect correlation. Stated plainly rather than quietly, since a
    proper covariance calculation is the honest version of this number.
    """
    def wavg(key: str) -> Optional[float]:
        pairs = [(r["weight_pct"], r[key]) for r in rows if r.get(key) is not None]
        if not pairs:
            return None
        w = sum(p[0] for p in pairs)
        return _f(sum(p[0] * p[1] for p in pairs) / w, 2) if w else None

    return {
        "expense_ratio_pct": wavg("expense_ratio_pct"),
        "yield_pct": wavg("yield_pct"),
        "cagr_10y_pct": wavg("cagr_10y_pct"),
        # Full-history CAGR drives the projection: it's defined for every fund,
        # including younger ones like AVUV that have no 10-year figure and would
        # otherwise drop silently out of the weighted average.
        "cagr_long_pct": wavg("cagr_full_pct"),
        "min_years_history": min((r.get("years_of_history") or 99) for r in rows) if rows else None,
        "volatility_pct_upper_bound": wavg("volatility_pct"),
        "max_drawdown_pct": wavg("max_drawdown_pct"),
        "caveat": (
            "Blended volatility and drawdown are weighted averages of the individual funds, so "
            "they overstate portfolio risk. Holdings that don't move together partly cancel out. "
            "Treat them as an upper bound."
        ),
    }


# ------------------------------------------------------------------ projection


def _projection(annual: float, years: int, cagr_pct: Optional[float],
                vol_pct: Optional[float]) -> Dict[str, Any]:
    """Compound annual contributions at the blended historical rate.

    This is arithmetic on past returns, not a forecast. The bands come from
    applying ±1 standard deviation to the annualized rate, which is a crude way
    to show dispersion — real return sequences matter, and a bad decade early
    hurts far more than the same decade late.
    """
    if cagr_pct is None or years < 1:
        return {"available": False,
                "note": "Need a blended return estimate and a horizon of at least a year."}

    def grow(rate_pct: float) -> List[Dict[str, Any]]:
        r = rate_pct / 100.0
        balance = 0.0
        out = []
        for year in range(1, years + 1):
            # Contribute at the start of the year, then grow — closer to a real
            # January lump contribution than end-of-year.
            balance = (balance + annual) * (1.0 + r)
            out.append({"year": year, "contributed": _f(annual * year, 0), "balance": _f(balance, 0)})
        return out

    # Band width is the standard error of the *annualized* return, σ/√years, not a
    # flat slice of σ. Annual volatility describes one year; the uncertainty in the
    # long-run average shrinks with horizon, so applying full σ to a 30-year rate
    # produced a $245k-to-$4M range that was technically derived and practically
    # meaningless.
    spread = (vol_pct or 0.0) / max(np.sqrt(years), 1.0)
    base = grow(cagr_pct)
    low = grow(max(cagr_pct - spread, 0.0))
    high = grow(cagr_pct + spread)

    return {
        "available": True,
        "years": years,
        "annual_contribution": _f(annual, 0),
        "total_contributed": _f(annual * years, 0),
        "rate_pct": _f(cagr_pct, 2),
        "rate_low_pct": _f(max(cagr_pct - spread, 0.0), 2),
        "rate_high_pct": _f(cagr_pct + spread, 2),
        "series": base,
        "balance_base": base[-1]["balance"],
        "balance_low": low[-1]["balance"],
        "balance_high": high[-1]["balance"],
        "series_low": [p["balance"] for p in low],
        "series_high": [p["balance"] for p in high],
        "caveat": (
            "Arithmetic on past returns, not a prediction. It assumes you contribute every year "
            "without fail, never sell, and that the coming decades resemble the last one. The band "
            "is one standard error of the annualized return (σ/√years), so it shows uncertainty in "
            "the long-run average, not the risk of a bad decade landing early. Sequence of returns "
            "matters more than the average, and this doesn't model it."
        ),
    }


# --------------------------------------------------------- holdings & drift

SYMBOL_TO_ROLE = {f["symbol"]: f["role"] for f in UNIVERSE}

# Common funds a real account is likely to hold that aren't in the model universe.
# Mapping them to a role is what lets drift be computed against an actual portfolio
# rather than only against a portfolio that happens to use these exact tickers.
ALIASES = {
    "VOO": "us_large", "SPY": "us_large", "IVV": "us_large", "SPLG": "us_large",
    "FXAIX": "us_large", "SWPPX": "us_large", "VFIAX": "us_large",
    "VTI": "us_total", "ITOT": "us_total", "SCHB": "us_total", "VTSAX": "us_total",
    "FSKAX": "us_total", "FZROX": "us_total",
    "QQQ": "us_growth", "QQQM": "us_growth", "VUG": "us_growth", "VGT": "us_growth",
    "SCHG": "us_growth", "MGK": "us_growth",
    "VXUS": "intl_dev", "VEA": "intl_dev", "IXUS": "intl_dev", "VTIAX": "intl_dev",
    "SCHF": "intl_dev", "EFA": "intl_dev", "VT": "intl_dev",
    "VWO": "intl_em", "IEMG": "intl_em", "EEM": "intl_em", "SCHE": "intl_em",
    "AVUV": "small_value", "VBR": "small_value", "IJS": "small_value",
    "VB": "small_value", "IWM": "small_value", "DFSV": "small_value",
    "SCHD": "dividend", "VYM": "dividend", "DGRO": "dividend", "VIG": "dividend",
    "VNQ": "reit", "SCHH": "reit", "XLRE": "reit", "IYR": "reit",
    "BND": "bonds", "AGG": "bonds", "BNDX": "bonds", "VBTLX": "bonds",
    "FXNAX": "bonds", "SCHZ": "bonds", "VGIT": "bonds", "TLT": "bonds",
    "GLD": "gold", "IAU": "gold", "GLDM": "gold", "SGOL": "gold",
}

# Roles that are near-perfect substitutes get merged before drift is measured.
# Without this, holding VOO against a model that specifies VTI reports 47% "over
# target" in US large cap and 27% "under" in US total market — and would tell you
# to swap two funds that are 1.00 correlated. Real drift means your *exposure* is
# off, not that you picked a different ticker for the same exposure.
ROLE_EQUIVALENTS = {"us_large": "us_total"}


def _canon_role(role: Optional[str]) -> Optional[str]:
    return ROLE_EQUIVALENTS.get(role, role)


def _canon_targets(targets: Dict[str, float]) -> Dict[str, float]:
    """Fold equivalent roles in the target weights into one bucket."""
    folded: Dict[str, float] = {}
    for role, weight in targets.items():
        key = _canon_role(role) or role
        folded[key] = folded.get(key, 0.0) + (weight or 0.0)
    return folded


ROLE_LABELS = {
    "us_total": "US total market", "us_large": "US large cap", "us_growth": "US growth",
    "small_value": "US small-cap value", "intl_dev": "International developed",
    "intl_em": "Emerging markets", "dividend": "US dividend", "reit": "Real estate",
    "bonds": "Bonds", "gold": "Gold", "stocks": "Individual stocks",
    "unclassified": "Unclassified",
}


def parse_holdings(raw: Any) -> Dict[str, float]:
    """Accept either a {symbol: dollar_value} map or newline/comma text.

    Values are dollar amounts rather than share counts on purpose: it avoids
    needing a live price for every symbol the user might hold, and sidesteps any
    ambiguity about splits or fractional shares.
    """
    out: Dict[str, float] = {}
    if isinstance(raw, dict):
        for sym, val in raw.items():
            amount = _f(val, 2)
            if sym and amount and amount > 0:
                out[str(sym).upper().strip()] = amount
        return out
    if not isinstance(raw, str):
        return out
    for line in raw.replace(",", "\n").splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        sym = parts[0].upper().strip()
        amount = _f(parts[-1].lstrip("$").replace("_", ""), 2)
        if sym and amount and amount > 0:
            out[sym] = amount
    return out


def _drift(holdings: Dict[str, float], targets: Dict[str, float],
           stock_symbols: List[str]) -> Dict[str, Any]:
    """Current versus target exposure, by role."""
    total = sum(holdings.values())
    if total <= 0:
        return {"available": False}

    current_by_role: Dict[str, float] = {}
    unmapped: List[str] = []
    for sym, value in holdings.items():
        if sym in stock_symbols:
            role = "stocks"
        else:
            role = _canon_role(ALIASES.get(sym) or SYMBOL_TO_ROLE.get(sym))
        if role is None:
            role = "unclassified"
            unmapped.append(sym)
        current_by_role[role] = current_by_role.get(role, 0.0) + value

    targets = _canon_targets(targets)
    roles = sorted(set(current_by_role) | set(targets))
    rows = []
    for role in roles:
        cur_val = current_by_role.get(role, 0.0)
        cur_pct = cur_val / total * 100.0
        tgt_pct = targets.get(role, 0.0)
        rows.append({
            "role": role,
            "label": ROLE_LABELS.get(role, role),
            "current_value": _f(cur_val, 0),
            "current_pct": _f(cur_pct, 1),
            "target_pct": _f(tgt_pct, 1),
            "drift_pct": _f(cur_pct - tgt_pct, 1),
        })
    rows.sort(key=lambda r: -abs(r["drift_pct"] or 0))

    worst = rows[0] if rows else None
    if worst and abs(worst["drift_pct"] or 0) >= 10:
        summary = (
            f"{worst['label']} is {abs(worst['drift_pct']):.0f} points "
            f"{'over' if worst['drift_pct'] > 0 else 'under'} target. The largest gap. "
            "Worth correcting with this year's contribution."
        )
    elif worst and abs(worst["drift_pct"] or 0) >= 5:
        summary = "Moderate drift. Directing new contributions at the underweights should close it."
    else:
        summary = "Close to target. No meaningful drift. Contribute at target weights."

    return {
        "available": True,
        "total_value": _f(total, 0),
        "rows": rows,
        "summary": summary,
        "unmapped": unmapped,
        "unmapped_note": (
            "Not recognised as a fund in the model's universe, so counted as unclassified: "
            + ", ".join(unmapped) + ". Add them as individual stocks below if that's what they are."
        ) if unmapped else None,
    }


def _rebalance_with_new_money(holdings: Dict[str, float], targets: Dict[str, float],
                              annual: float, stock_symbols: List[str]) -> Dict[str, Any]:
    """Where to point this year's contribution, buying only.

    Selling to rebalance is tax-free inside a Roth, but it still isn't free.
    It's a decision and it costs spreads. Directing new money at the underweights
    fixes drift without touching anything, so that's the default answer here.
    """
    total = sum(holdings.values())
    if total <= 0 or annual <= 0:
        return {"available": False,
                "note": "Needs both current holdings and a contribution amount."}

    current_by_role: Dict[str, float] = {}
    for sym, value in holdings.items():
        role = "stocks" if sym in stock_symbols else (
            _canon_role(ALIASES.get(sym) or SYMBOL_TO_ROLE.get(sym)) or "unclassified")
        current_by_role[role] = current_by_role.get(role, 0.0) + value

    targets = _canon_targets(targets)
    end_total = total + annual
    # Shortfall against where each role *should* sit once the contribution lands.
    needs = {}
    for role, tgt_pct in targets.items():
        desired = end_total * tgt_pct / 100.0
        gap = desired - current_by_role.get(role, 0.0)
        if gap > 0:
            needs[role] = gap

    rows = []
    need_total = sum(needs.values())
    if need_total <= 0:
        return {
            "available": True,
            "rows": [],
            "note": "Every target role is already at or above weight. Contribute at target weights, "
                    "or rebalance by selling if the overweights bother you.",
            "fully_corrected": False,
        }

    # If the shortfall exceeds the contribution, split it proportionally — that
    # closes the largest gaps fastest without overshooting any single role.
    scale = min(1.0, annual / need_total)
    for role, gap in sorted(needs.items(), key=lambda kv: -kv[1]):
        dollars = gap * scale if need_total > annual else gap
        if dollars < 1:
            continue
        fund = BY_ROLE.get(role)
        rows.append({
            "role": role,
            "label": ROLE_LABELS.get(role, role),
            "symbol": fund["symbol"] if fund else None,
            "dollars": _f(dollars, 0),
            "pct_of_contribution": _f(dollars / annual * 100.0, 1),
        })

    # Leftover when contributions more than cover every gap.
    allocated = sum(r["dollars"] or 0 for r in rows)
    leftover = annual - allocated
    if leftover > 1 and rows:
        for r in rows:
            r["dollars"] = _f((r["dollars"] or 0) + leftover * (targets.get(r["role"], 0) / 100.0), 0)
            r["pct_of_contribution"] = _f((r["dollars"] or 0) / annual * 100.0, 1)

    overweight = [role for role, tgt in targets.items()
                  if current_by_role.get(role, 0.0) / total * 100.0 > tgt + 5]

    return {
        "available": True,
        "contribution": _f(annual, 0),
        "rows": rows,
        "fully_corrected": need_total <= annual,
        "note": (
            "This contribution closes every gap." if need_total <= annual else
            f"The total shortfall is ${need_total:,.0f}, more than one year's contribution, so this "
            "splits it proportionally. The biggest gaps get the most. Full correction takes a "
            f"few years of contributions, or one sell-and-buy rebalance."
        ),
        "overweight_roles": [ROLE_LABELS.get(r, r) for r in overweight],
        "overweight_note": (
            "Buying alone can't fix an overweight. These sit more than 5 points above target and "
            "would need a sale to correct: " + ", ".join(ROLE_LABELS.get(r, r) for r in overweight)
            + ". Selling inside a Roth triggers no tax, so the only cost is the spread."
        ) if overweight else None,
    }


def _overlap(holdings: Dict[str, float], provider) -> Dict[str, Any]:
    """Flag holdings that are effectively the same bet.

    Two funds tracking near-identical indices show up as a correlation near 1.00.
    Holding both adds rebalancing work and a false sense of diversification.
    """
    symbols = [s for s in holdings if len(s) <= 6]
    if len(symbols) < 2:
        return {"available": False}
    try:
        frames = provider.batch_history(symbols, period="3y", interval="1d")
    except Exception:
        return {"available": False}

    series = {}
    for sym in symbols:
        frame = frames.get(sym)
        if frame is not None and not frame.empty and "Close" in frame:
            series[sym] = frame["Close"].pct_change()
    if len(series) < 2:
        return {"available": False}
    joined = pd.DataFrame(series).dropna()
    if len(joined) < 120:
        return {"available": False}

    corr = joined.corr()
    pairs = []
    cols = list(corr.columns)
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            value = _f(corr.iloc[i, j], 2)
            if value is None or value < 0.9:
                continue
            role_i = ALIASES.get(cols[i]) or SYMBOL_TO_ROLE.get(cols[i])
            role_j = ALIASES.get(cols[j]) or SYMBOL_TO_ROLE.get(cols[j])
            pairs.append({
                "a": cols[i], "b": cols[j], "correlation": value,
                "same_role": bool(role_i and role_i == role_j),
                "note": (
                    f"{cols[i]} and {cols[j]} move together {value:.2f} of the time"
                    + (" and fill the same role in the model" if role_i and role_i == role_j else "")
                    + ". Holding both is close to holding one at double the weight."
                ),
            })
    pairs.sort(key=lambda p: -p["correlation"])
    return {
        "available": True,
        "pairs": pairs,
        "note": (
            "No two holdings are more than 90% correlated. The portfolio isn't doubling up."
            if not pairs else
            f"{len(pairs)} pair{'s' if len(pairs) != 1 else ''} of holdings are 90%+ correlated."
        ),
    }


# ------------------------------------------------------- individual stocks


def _stock_sleeve(provider, symbols: List[str], risk: str,
                  years: int) -> Dict[str, Any]:
    """Score individual stocks for a retirement sleeve, and cap how much they get.

    Deliberately conservative. Retirement money in single names carries risk that
    diversification is specifically designed to remove, and a small annual
    contribution limit makes concentration worse, not better. So the sleeve is
    capped tightly, scaled by both stated risk tolerance and horizon, and every
    candidate has to clear a conviction bar computed from its own long-run record.
    """
    from . import longterm  # local import: avoids a circular import at module load

    # Cap: the most this sleeve may take of the whole portfolio.
    cap = {"conservative": 0.0, "balanced": 8.0, "growth": 15.0}[risk]
    # A short horizon can't absorb a single-name blow-up, so shrink the cap further.
    cap *= min(years, 20) / 20.0

    if cap <= 0:
        return {
            "available": False,
            "cap_pct": 0.0,
            "note": "A conservative setting allocates nothing to individual stocks. "
                    "Single-name risk is the first thing to cut when capital preservation leads.",
        }
    if not symbols:
        return {
            "available": False,
            "cap_pct": _f(cap, 1),
            "note": f"No candidates entered. At this risk setting and horizon the sleeve could take "
                    f"up to {cap:.0f}% of the portfolio. Leaving it empty is a perfectly good choice.",
        }

    rows = []
    for sym in symbols[:8]:
        try:
            read = longterm.analyse_holding(provider, sym)
        except Exception as exc:
            rows.append({"symbol": sym, "error": str(exc)})
            continue
        if read.get("error"):
            rows.append({"symbol": sym, "error": read["error"]})
            continue
        quality = read.get("data_quality") or {}
        rows.append({
            "symbol": sym,
            "name": read.get("name") or sym,
            "conviction": read.get("conviction"),
            "conviction_score": read.get("conviction_score"),
            "cagr_10y_pct": ((read.get("horizons") or {}).get("cagr_10y_pct")),
            "cagr_5y_pct": ((read.get("horizons") or {}).get("cagr_5y_pct")),
            "max_drawdown_pct": ((read.get("drawdown") or {}).get("max_drawdown_pct")),
            "current_drawdown_pct": ((read.get("drawdown") or {}).get("current_drawdown_pct")),
            "years_of_history": quality.get("history_years"),
            "reliable": quality.get("reliable"),
            "warnings": quality.get("warnings") or [],
        })

    # Only names scoring above a real bar get space, and the sleeve is split by
    # score so a marginal candidate can't take the same weight as a strong one.
    # Reliability gate comes first: a name with two years of history has no
    # long-run record to judge, and a high score off a short sample is exactly the
    # trap the conviction check is supposed to catch.
    eligible = [
        r for r in rows
        if not r.get("error")
        and r.get("reliable") is not False
        and (r.get("conviction_score") or -99) >= STOCK_CONVICTION_BAR
    ]
    score_total = sum(r["conviction_score"] for r in eligible) or 1.0
    for r in rows:
        if r in eligible:
            r["suggested_pct"] = _f(cap * r["conviction_score"] / score_total, 1)
            r["eligible"] = True
            continue
        r["suggested_pct"] = 0.0
        r["eligible"] = False
        if r.get("error"):
            continue
        if r.get("reliable") is False:
            r["reject_reason"] = (
                "Too little price history to judge a decades-long holding. Likely a recent IPO, "
                "spinoff or ticker change."
            )
        else:
            r["reject_reason"] = (
                "Conviction score {} is below the bar of {} this sleeve requires."
                .format(r.get("conviction_score"), STOCK_CONVICTION_BAR)
            )

    return {
        "available": True,
        "cap_pct": _f(cap, 1),
        "rows": rows,
        "eligible_count": len(eligible),
        "note": (
            f"The sleeve is capped at {cap:.0f}% of the portfolio at this risk setting and horizon, "
            f"and {len(eligible)} of {len(rows)} candidates clear the conviction bar of {STOCK_CONVICTION_BAR:.0f}. Weights within "
            "the sleeve are split by conviction score."
        ),
        "caveat": (
            "Individual stocks in retirement money are a concentration bet, and the conviction score "
            "is a backward-looking read on trend, drawdown and valuation, not a forecast. Any single "
            "company can go to zero in a way a total-market fund cannot. Treat this sleeve as the part "
            "of the portfolio you could afford to lose entirely."
        ),
    }


# ------------------------------------------------------------------- Roth notes


def _roth_notes(alloc: Dict[str, Any], risk: str, years: int) -> List[Dict[str, str]]:
    """Why the Roth wrapper changes the answer, not just generic allocation talk."""
    notes = [
        {
            "title": "Put your highest-growth assets here",
            "body": "Growth inside a Roth is never taxed, so the space is worth most to whatever you "
                    "expect to compound fastest. If you hold both a Roth and a taxable account, the "
                    "aggressive equity sleeve belongs in the Roth and the boring ballast in taxable.",
        },
        {
            "title": "Distributions are free of annual tax",
            "body": "REITs and high-dividend funds throw off income that is taxed every year in a "
                    "taxable account. Inside a Roth that drag disappears, which makes this the "
                    "cheapest place to own them if you want them at all.",
        },
        {
            "title": "No tax-loss harvesting",
            "body": "Losses in a Roth aren't deductible, so there's no tax silver lining to a "
                    "position that falls. That removes one argument for holding highly volatile "
                    "single names here.",
        },
        {
            "title": "Keep it to a handful of funds",
            "body": "The annual contribution limit is small. Splitting it across eight funds adds "
                    "rebalancing work without adding much real diversification. Two or three broad "
                    "funds already hold thousands of companies.",
        },
    ]
    if alloc.get("bond_pct") and alloc["bond_pct"] >= 15:
        notes.append({
            "title": "Bonds in a Roth cut both ways",
            "body": f"This model holds {alloc['bond_pct']:.0f}% bonds. Bond interest is taxed as "
                    "ordinary income, so a Roth shelters it well. But bonds also have the lowest "
                    "expected return, so they use up tax-free space that equities would benefit "
                    "from more. Both arguments are legitimate; which wins depends on whether this "
                    "is your only account.",
        })
    if years >= 25 and risk == "conservative":
        notes.append({
            "title": "Your horizon and your risk setting disagree",
            "body": f"With {years} years to go, the main risk to a conservative mix isn't a crash . "
                    "It's not growing enough to keep up with inflation. Worth checking whether the "
                    "conservative setting reflects genuine risk tolerance or just discomfort with "
                    "short-term swings you won't need to act on.",
        })
    return notes


# ------------------------------------------------------------------ entry point


def analyse(provider, years: int = 30, risk: str = "balanced",
            annual_contribution: float = 7000.0, holdings: Any = None,
            stock_candidates: Any = None) -> Dict[str, Any]:
    risk = risk if risk in RISK_TIERS else "balanced"
    years = int(np.clip(years, 1, 45))
    annual = float(max(annual_contribution, 0.0))

    holdings = parse_holdings(holdings)
    if isinstance(stock_candidates, str):
        stock_candidates = [t.strip().upper() for t in stock_candidates.replace(",", " ").split() if t.strip()]
    stock_candidates = [s for s in (stock_candidates or []) if s]

    symbols = [f["symbol"] for f in UNIVERSE]
    frames = provider.batch_history(symbols, period="10y", interval="1d")

    stats: Dict[str, Dict[str, Any]] = {}
    meta: Dict[str, Dict[str, Any]] = {}
    for fund in UNIVERSE:
        sym = fund["symbol"]
        stats[sym] = _fund_stats(frames.get(sym))
        try:
            info = provider.fund_meta(sym) or {}
        except Exception:
            info = {}
        meta[sym] = {
            "fund_name": info.get("name"),
            "category": info.get("category"),
            "expense_ratio_pct": _f(info.get("expense_ratio_pct"), 2),
            "yield_pct": _f(info.get("yield_pct"), 2),
        }

    sleeve = _stock_sleeve(provider, stock_candidates, risk, years)

    # An individual-stock sleeve has to come out of the fund allocation rather than
    # on top of it, or the weights quietly sum past 100%.
    alloc = _model_allocation(years, risk)
    sleeve_pct = sum(r.get("suggested_pct") or 0 for r in (sleeve.get("rows") or []))
    if sleeve_pct > 0:
        keep = (100.0 - sleeve_pct) / 100.0
        alloc["weights"] = {k: _f(v * keep, 1) for k, v in alloc["weights"].items()}
        alloc["stock_sleeve_pct"] = _f(sleeve_pct, 1)
        alloc["equity_pct"] = _f((alloc["equity_pct"] or 0) * keep + sleeve_pct, 1)
        alloc["bond_pct"] = _f((alloc["bond_pct"] or 0) * keep, 1)

    rows = _allocation_rows(alloc, stats, meta, annual)
    blended = _blended(rows)
    projection = _projection(annual, years, blended.get("cagr_long_pct"),
                             blended.get("volatility_pct_upper_bound"))

    fund_rows = []
    for fund in UNIVERSE:
        sym = fund["symbol"]
        fund_rows.append({**fund, **stats.get(sym, {}), **meta.get(sym, {}),
                          "in_model_pct": alloc["weights"].get(fund["role"])})

    # Targets for drift include the stock sleeve, so an actual portfolio holding
    # single names is measured against a model that expects them.
    targets = dict(alloc["weights"])
    if sleeve_pct > 0:
        targets["stocks"] = _f(sleeve_pct, 1)

    drift = _drift(holdings, targets, stock_candidates) if holdings else {"available": False}
    rebalance = (_rebalance_with_new_money(holdings, targets, annual, stock_candidates)
                 if holdings else {"available": False,
                                   "note": "Enter your current holdings to get a rebalancing plan."})
    overlap = _overlap(holdings, provider) if holdings else {"available": False}

    return {
        "inputs": {
            "years": years, "risk": risk, "annual_contribution": _f(annual, 0),
            "holdings": holdings, "stock_candidates": stock_candidates,
        },
        "allocation": alloc,
        "rows": rows,
        "blended": blended,
        "projection": projection,
        "funds": fund_rows,
        "correlations": _correlations(frames, symbols),
        "drift": drift,
        "rebalance": rebalance,
        "overlap": overlap,
        "stock_sleeve": sleeve,
        "roth_notes": _roth_notes(alloc, risk, years),
        "limit_note": (
            "The contribution figure is yours to set. IRS Roth limits change annually and depend "
            "on age and income, so this tool doesn't assume one. Check the current limit and the "
            "income phase-out on irs.gov before relying on the projection."
        ),
        "disclaimer": legal_mod.AREAS["retirement"],
        "disclaimer_short": legal_mod.SHORT,
    }
