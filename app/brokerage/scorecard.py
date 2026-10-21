"""The portfolio scorecard: five separate descriptions of what is held today.

Diversification, financial quality, valuation, volatility and event exposure,
each with its inputs, method, thresholds, coverage, the holdings that move it
and the holdings it could not assess. Pure: fundamentals, prices and events
are injected; nothing is fetched here.

**There is no overall score, on purpose.** The stance panel's composite was
measured to be decoration (`/api/evaluate`: it did not beat a single raw
momentum number at 3 of 3 horizons), and the historical validation program
found none of 82 tested signals supported. A single portfolio grade would be
the most confident number on the page and the least supported. Five separate
readings, each saying what it measured, are checkable; their average is not.

**Only two carry a 0-100 score**, diversification and financial quality,
because for those "higher" has a direction that is not a return claim: more
spread out, and stronger reported businesses. Valuation, volatility and event
exposure are described in words against a reference (the S&P 500, the
calendar) with the numbers, and score None: a "cheap" score reads as a buy
signal and a "calm" score reads as "safe", and neither is what was measured.

**Missing data is never a low score.** A holding without fundamentals, or a
fund that company financials do not describe, is listed under `not_assessed`
with the reason, and the result reports what share of value it covers
(`coverage_pct`). The vocabulary follows `app/research/quality.py`: graded
0 to 4 against written bands, insufficient is not scored.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import numpy as np

VERSION = "scorecard-2026-10-15.1"

DISCLAIMER = ("These describe the portfolio as it is today. They are not forecasts of return and not "
              "validated probabilities.")

TRADING_DAYS = 252
MIN_OVERLAP_DAYS = 120        # about six months of sessions; less than that and a covariance is mostly noise
EVENT_WINDOW_DAYS = 14
OPTION_WINDOW_DAYS = 7

STOCKLIKE = ("equity",)
FUNDLIKE = ("etf", "fund")
FUND_QUOTE_TYPES = ("ETF", "MUTUALFUND", "MONEYMARKET", "INDEX", "CLOSEDEND")
FINANCIAL_SECTORS = ("financial services", "financials", "financial")
NOT_A_SECTOR = ("ETFs and funds (not looked through)", "Sector not known")

# ------------------------------------------------------------- diversification
# Effective holdings (1/HHI): idiosyncratic variance of N equal, independent
# positions is 1/N of one position's, so 20 effective holdings has removed 95%
# of it and 4 has removed 75%. Bands are floors.
EFFECTIVE_BANDS = [(20.0, 4), (12.0, 3), (7.0, 2), (4.0, 1)]
# Largest single position, % of value; ceilings. 20% is portfolio.py's
# SINGLE_NAME_FLAG, the share at which the holdings table already says so.
TOP1_BANDS = [(5.0, 4), (10.0, 3), (20.0, 2), (35.0, 1)]
# Largest sector, % of value; ceilings. The S&P 500's own largest sector
# (information technology) was roughly 30 to 35% of the index through 2025, so
# 35% or less scores 3, "about as concentrated as the index". 40% is
# portfolio.py's SECTOR_FLAG.
SECTOR_BANDS = [(25.0, 4), (35.0, 3), (45.0, 2), (60.0, 1)]
DIVERSIFICATION_WEIGHTS = {"effective_holdings": 0.4, "largest_position": 0.3, "largest_sector": 0.3}
DIVERSIFICATION_LEVELS = [(75.0, "Well diversified"), (50.0, "Moderately diversified"),
                          (25.0, "Concentrated"), (-1.0, "Highly concentrated")]

# ------------------------------------------------------------- financial quality
# Each measure graded 0-4 against floors; the margin and growth bands are
# app/research/quality.py's, so a company reads the same here as in its
# long-term panel. Debt to equity is a ceiling.
QUALITY_MEASURES: Dict[str, Dict[str, Any]] = {
    "profitability": {"label": "Return on equity", "field": "return_on_equity",
                      "bands": [(0.20, 4), (0.15, 3), (0.08, 2), (0.0, 1)], "ceiling": False,
                      "rubric": "Return on equity: 4 at 20% or more, 3 at 15%, 2 at 8%, 1 at 0%, else 0."},
    "margins": {"label": "Operating margin", "field": "operating_margin",
                "bands": [(0.25, 4), (0.15, 3), (0.08, 2), (0.0, 1)], "ceiling": False,
                "rubric": "Operating margin: 4 at 25% or more, 3 at 15%, 2 at 8%, 1 at 0%, else 0."},
    "cash_generation": {"label": "Free cash flow margin", "field": "fcf_margin",
                        "bands": [(0.15, 4), (0.08, 3), (0.03, 2), (1e-9, 1)], "ceiling": False,
                        "rubric": "Free cash flow over revenue: 4 at 15% or more, 3 at 8%, 2 at 3%, 1 when "
                                  "positive, else 0."},
    "balance_sheet": {"label": "Debt to equity", "field": "debt_to_equity",
                      "bands": [(0.3, 4), (0.6, 3), (1.0, 2), (2.0, 1)], "ceiling": True,
                      "rubric": "Total debt over shareholders' equity (a ratio, 1.0 = debt equals equity): 4 at "
                                "0.3 or less, 3 at 0.6, 2 at 1.0, 1 at 2.0, else 0."},
    "growth": {"label": "Revenue growth", "field": "revenue_growth",
               "bands": [(0.15, 4), (0.08, 3), (0.03, 2), (0.0, 1)], "ceiling": False,
               "rubric": "Revenue growth on a year earlier: 4 at 15% or more, 3 at 8%, 2 at 3%, 1 at 0%, "
                         "else 0."},
}
MIN_QUALITY_MEASURES = 3      # fewer than three of five and one figure decides the grade
QUALITY_LEVELS = [(75.0, "Strong"), (55.0, "Sound"), (35.0, "Mixed"), (-1.0, "Weak")]

# The keys `fundamentals_of(symbol)` returns, with units. fundamentals_from_yahoo
# produces exactly these.
FUNDAMENTALS_KEYS = {
    "return_on_equity": "Decimal (0.15 is 15%), trailing twelve months.",
    "operating_margin": "Decimal, trailing twelve months.",
    "free_cash_flow": "Currency units, trailing twelve months.",
    "total_revenue": "Currency units, trailing twelve months, same currency as free_cash_flow.",
    "debt_to_equity": "Ratio (1.5 is debt at 1.5x equity). Yahoo reports this in percent; divide by 100.",
    "revenue_growth": "Decimal, latest quarter against the same quarter a year earlier on Yahoo.",
    "forward_pe": "Price over the next fiscal year's consensus EPS; negative when that EPS is negative.",
    "trailing_pe": "Price over trailing twelve-month EPS; absent on Yahoo when EPS is negative.",
    "forward_eps": "Consensus EPS for the next fiscal year, per share.",
    "trailing_eps": "Trailing twelve-month EPS, per share.",
    "price": "The price the ratios were computed at, per share.",
    "quote_type": "EQUITY, ETF, MUTUALFUND ...",
    "sector": "Sector name, used to recognise banks and insurers.",
    "source": "Where the figures came from.",
}

# ------------------------------------------------------------- valuation
# Portfolio P/E within 15% of the market's is "in line": at a 20x market that
# is 17x to 23x, about the spread between the S&P 500's own forward and
# trailing multiples, so a narrower band would call a basis difference a
# valuation difference.
VALUATION_BAND = 0.15

# ------------------------------------------------------------- volatility
VOL_RATIO_LEVELS = [(0.8, "Calmer than the benchmark"), (1.2, "Similar to the benchmark"),
                    (1.6, "More volatile than the benchmark")]
VOL_ABSOLUTE_LEVELS = [(0.12, "Low volatility"), (0.20, "Moderate volatility"), (0.30, "High volatility")]

# ------------------------------------------------------------- events
EVENT_LEVELS = [(10.0, "Low event exposure"), (30.0, "Moderate event exposure")]


# ================================================================= helpers

def _num(v: Any) -> Optional[float]:
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _r(v: Optional[float], n: int = 2) -> Optional[float]:
    return None if v is None else round(float(v), n)


def _band(x: float, bands: List[Tuple[float, int]], ceiling: bool = False) -> int:
    for edge, score in bands:
        if (x <= edge) if ceiling else (x >= edge):
            return score
    return 0


def _level(score: Optional[float], levels: List[Tuple[float, str]]) -> str:
    if score is None:
        return "Not assessed"
    for floor, name in levels:
        if score >= floor:
            return name
    return levels[-1][1]


def _call(fn: Optional[Callable], arg: Any) -> Any:
    if fn is None:
        return None
    try:
        return fn(arg)
    except Exception:                                            # noqa: BLE001
        return None


def holding_value(h: Dict[str, Any]) -> Optional[float]:
    """US-dollar value: portfolio.build's value_usd, else the market value of
    a USD line. A non-USD line without a converted value has none."""
    v = _num(h.get("value_usd"))
    if v is None and (h.get("currency") or "USD").upper() == "USD":
        v = _num(h.get("market_value"))
    return v


def _book(holdings: Iterable[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Long holdings merged by symbol with their weights, and what was left out."""
    rows: Dict[str, Dict[str, Any]] = {}
    skipped: List[Dict[str, Any]] = []
    for h in holdings or []:
        name = str(h.get("symbol") or h.get("description") or "").upper()
        if not name:
            continue
        v = holding_value(h)
        if v is None:
            skipped.append({"symbol": name, "weight_pct": None,
                            "reason": "No US-dollar value (no exchange rate), so it is outside every assessment."})
            continue
        if v <= 0:
            skipped.append({"symbol": name, "weight_pct": None,
                            "reason": "A short or zero-value position; these assessments describe long holdings."})
            continue
        r = rows.setdefault(name, {"symbol": name, "kind": h.get("kind") or "other", "sector": h.get("sector"),
                                   "value": 0.0, "description": h.get("description")})
        r["value"] += v
        if not r.get("sector") and h.get("sector"):
            r["sector"] = h.get("sector")
    total = sum(r["value"] for r in rows.values())
    out = sorted(rows.values(), key=lambda r: -r["value"])
    for r in out:
        r["weight"] = r["value"] / total if total else 0.0
    return out, skipped


def _assessment(aid: str, label: str, **kw: Any) -> Dict[str, Any]:
    base = {"id": aid, "label": label, "level": "Not assessed", "score": None, "summary": "", "inputs": {},
            "method": "", "weights": {}, "coverage_pct": None, "drivers": [], "not_assessed": [],
            "version": VERSION}
    base.update(kw)
    return base


def _pct(x: Optional[float], d: int = 1) -> str:
    return "n/a" if x is None else "{:.{d}f}%".format(x, d=d)


# ================================================================= history maths

def _series(rows: Any) -> Dict[str, float]:
    """{YYYY-MM-DD: close} from [[date, close], ...] (or {"closes": [...]})."""
    if isinstance(rows, dict):
        rows = rows.get("closes") or rows.get("points") or []
    out: Dict[str, float] = {}
    for item in rows or []:
        try:
            d, c = item[0], item[1]
        except (TypeError, IndexError, KeyError):
            continue
        c = _num(c)
        if c is None or c <= 0 or not d:
            continue
        out[str(d)[:10]] = c
    return out


def history_risk(values: Dict[str, float], closes: Dict[str, Any], benchmark_closes: Any,
                 cash: float = 0.0, min_days: int = MIN_OVERLAP_DAYS) -> Dict[str, Any]:
    """Volatility, beta and drawdown of a portfolio held at fixed weights over
    the window of `closes`.

    `values` is {symbol: US-dollar value} of long holdings. Cash, when given,
    is a zero-return holding in the denominator, so moving cash into stocks
    shows as more volatility. Holdings without `min_days` closes overlapping
    the benchmark are left out and the others re-weighted among themselves
    and the cash; `coverage_pct` says how much value that left in.

    Daily simple returns, so the portfolio's return each day is exactly the
    weighted sum (rebalanced daily to the same weights). Volatility is the
    sample standard deviation x sqrt(252). Beta is cov(portfolio, benchmark) /
    var(benchmark) over the same days.
    """
    bench = _series(benchmark_closes)
    excluded: List[Dict[str, Any]] = []
    series: Dict[str, Dict[str, float]] = {}
    for sym, v in values.items():
        if v is None or v <= 0:
            continue
        s = _series((closes or {}).get(sym))
        if not s:
            excluded.append({"symbol": sym, "reason": "No price history."})
            continue
        overlap = len(set(s) & set(bench)) if bench else len(s)
        if overlap < min_days:
            excluded.append({"symbol": sym, "reason": "Only {} days of history overlap the benchmark's; {} are "
                                                      "needed.".format(overlap, min_days)})
            continue
        series[sym] = s

    def common_dates(syms: List[str]) -> List[str]:
        sets = [set(series[s]) for s in syms] + ([set(bench)] if bench else [])
        return sorted(set.intersection(*sets)) if sets else []

    included = sorted(series, key=lambda s: -values[s])
    dates = common_dates(included) if included else []
    # Different listing dates and missing days can make the shared window
    # shorter than each holding's own; drop the shortest history until it fits.
    while included and len(dates) < min_days:
        worst = min(included, key=lambda s: len(series[s]))
        included.remove(worst)
        excluded.append({"symbol": worst, "reason": "Its dates overlap the other holdings' too little for a shared "
                                                    "window of {} days.".format(min_days)})
        dates = common_dates(included) if included else []
    all_value = sum(v for v in values.values() if v and v > 0)
    if not included:
        return {"available": False, "reason": "No holding has {} days of price history overlapping the benchmark."
                .format(min_days), "excluded": excluded, "coverage_pct": 0.0 if all_value else None}

    prices = np.array([[series[s][d] for d in dates] for s in included], dtype=float)
    rets = prices[:, 1:] / prices[:, :-1] - 1.0
    inc_value = sum(values[s] for s in included)
    cash = max(float(cash or 0.0), 0.0)
    w = np.array([values[s] for s in included], dtype=float) / (inc_value + cash)
    port = w @ rets
    cov = np.atleast_2d(np.cov(rets, ddof=1))
    var_p = float(w @ cov @ w)
    vol = math.sqrt(max(var_p, 0.0) * TRADING_DAYS)
    out: Dict[str, Any] = {
        "available": True,
        "window": {"start": dates[0], "end": dates[-1], "returns": int(rets.shape[1])},
        "portfolio_vol_pct": _r(100.0 * vol),
        "benchmark_vol_pct": None, "beta": None, "correlation": None,
        "max_drawdown_pct": None, "benchmark_max_drawdown_pct": None,
        "included": included, "excluded": excluded,
        "coverage_pct": _r(100.0 * inc_value / all_value) if all_value else None,
        "weights_used": {s: _r(100.0 * float(x)) for s, x in zip(included, w)},
        "cash_weight_pct": _r(100.0 * cash / (inc_value + cash)) if (inc_value + cash) else None,
    }
    path = np.concatenate([[1.0], np.cumprod(1.0 + port)])
    out["max_drawdown_pct"] = _r(100.0 * float(np.min(path / np.maximum.accumulate(path) - 1.0)))
    if bench:
        b = np.array([bench[d] for d in dates], dtype=float)
        rb = b[1:] / b[:-1] - 1.0
        var_b = float(np.var(rb, ddof=1))
        if var_b > 0:
            cov_pb = float(np.cov(port, rb, ddof=1)[0, 1])
            out["beta"] = _r(cov_pb / var_b, 3)
            sd_p = float(np.std(port, ddof=1))
            out["correlation"] = _r(cov_pb / (sd_p * math.sqrt(var_b)), 3) if sd_p > 0 else None
        out["benchmark_vol_pct"] = _r(100.0 * math.sqrt(var_b * TRADING_DAYS))
        bpath = np.concatenate([[1.0], np.cumprod(1.0 + rb)])
        out["benchmark_max_drawdown_pct"] = _r(100.0 * float(np.min(bpath / np.maximum.accumulate(bpath) - 1.0)))
    contrib = []
    if var_p > 0:
        marginal = cov @ w
        own = np.sqrt(np.clip(np.diag(cov), 0, None) * TRADING_DAYS)
        for i, s in enumerate(included):
            contrib.append({"symbol": s, "weight_used_pct": _r(100.0 * float(w[i])),
                            "own_vol_pct": _r(100.0 * float(own[i])),
                            "risk_share_pct": _r(100.0 * float(w[i] * marginal[i]) / var_p)})
        contrib.sort(key=lambda c: -abs(c["risk_share_pct"] or 0.0))
    out["risk_contributions"] = contrib
    return out


# ================================================================= 1. diversification

def _lt_rows(obj: Any) -> List[Dict[str, Any]]:
    """A list of rows from an exposure field that may be a list or a dict that
    holds the look-through list under one of a few names."""
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        for k in ("look_through", "lookthrough", "combined", "items", "rows"):
            if isinstance(obj.get(k), list):
                return [x for x in obj[k] if isinstance(x, dict)]
    return []


def _lt_pct(row: Dict[str, Any]) -> Optional[float]:
    for k in ("look_through_pct", "total_pct", "combined_pct", "weight_pct", "share_pct", "pct"):
        v = _num(row.get(k))
        if v is not None:
            return v
    v = _num(row.get("weight"))
    return None if v is None else 100.0 * v


def _lt_name(row: Dict[str, Any], keys: Tuple[str, ...]) -> Optional[str]:
    for k in keys:
        if row.get(k):
            return str(row[k])
    return None


def lookthrough_view(exposure: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Companies and sectors from `exposure.build`, as {name: % of value}, or
    None when there is no usable look-through."""
    if not isinstance(exposure, dict) or exposure.get("available") is False:
        return None
    companies: Dict[str, float] = {}
    for row in _lt_rows(exposure.get("companies")):
        name, pct = _lt_name(row, ("symbol", "ticker", "name", "key", "label")), _lt_pct(row)
        if name and pct is not None and pct > 0:
            companies[name.upper()] = companies.get(name.upper(), 0.0) + pct
    sectors: Dict[str, float] = {}
    for row in _lt_rows(exposure.get("sectors")):
        name, pct = _lt_name(row, ("sector", "label", "name", "key")), _lt_pct(row)
        if name and pct is not None and pct > 0:
            sectors[name] = sectors.get(name, 0.0) + pct
    if not companies:
        return None
    cov = None
    for src in (exposure, exposure.get("sectors") if isinstance(exposure.get("sectors"), dict) else {},
                exposure.get("companies") if isinstance(exposure.get("companies"), dict) else {}):
        for k in ("look_through_coverage_pct", "coverage_pct", "lookthrough_coverage_pct"):
            if cov is None and isinstance(src, dict):
                cov = _num(src.get(k))
    return {"companies": companies, "sectors": sectors, "coverage_pct": cov}


def _diversification(rows: List[Dict[str, Any]], skipped: List[Dict[str, Any]],
                     exposure: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    label = "Diversification"
    if not rows:
        return _assessment("diversification", label, summary="No long holdings with a value to assess.",
                           not_assessed=skipped)
    lt = lookthrough_view(exposure)
    notes: List[str] = []
    if lt:
        basis = "look-through"
        weights = {k: v / 100.0 for k, v in lt["companies"].items()}
        covered = sum(weights.values())
        uncovered = max(0.0, 1.0 - covered)
        hhi = sum(w * w for w in weights.values()) + (uncovered * uncovered if uncovered > 0.005 else 0.0)
        ranked = sorted(weights.items(), key=lambda kv: -kv[1])
        drivers = [{"symbol": k, "weight_pct": _r(100.0 * w), "basis": "direct plus held through funds"}
                   for k, w in ranked[:5]]
        if uncovered > 0.005:
            notes.append("{:.1f}% of value could not be looked through to companies and is counted as one "
                         "block, which understates diversification rather than overstating it."
                         .format(100.0 * uncovered))
        sectors = {k: v for k, v in lt["sectors"].items() if k not in NOT_A_SECTOR}
        sector_cov = lt["coverage_pct"] if lt["coverage_pct"] is not None else (
            sum(lt["sectors"].values()) if lt["sectors"] else None)
    else:
        basis = "direct"
        uncovered = 0.0
        weights = {r["symbol"]: r["weight"] for r in rows}
        hhi = sum(w * w for w in weights.values())
        ranked = sorted(weights.items(), key=lambda kv: -kv[1])
        drivers = [{"symbol": r["symbol"], "weight_pct": _r(100.0 * r["weight"]), "kind": r["kind"]}
                   for r in rows[:5]]
        if any(r["kind"] in FUNDLIKE for r in rows):
            notes.append("Direct holdings only: each ETF or fund counts as one holding, which overstates "
                         "concentration for a broad fund. Look-through was not available.")
        sectors = {}
        known = 0.0
        for r in rows:
            if r["kind"] in STOCKLIKE and r.get("sector"):
                sectors[r["sector"]] = sectors.get(r["sector"], 0.0) + 100.0 * r["weight"]
                known += r["weight"]
        sector_cov = 100.0 * known
    eff = 1.0 / hhi if hhi > 0 else None
    top1_name, top1 = (ranked[0][0], 100.0 * ranked[0][1]) if ranked else (None, None)
    top5 = 100.0 * sum(w for _, w in ranked[:5])
    big_sector = max(sectors.items(), key=lambda kv: kv[1]) if sectors else None

    comps: Dict[str, Optional[int]] = {
        "effective_holdings": _band(eff, EFFECTIVE_BANDS) if eff is not None else None,
        "largest_position": _band(top1, TOP1_BANDS, ceiling=True) if top1 is not None else None,
        "largest_sector": _band(big_sector[1], SECTOR_BANDS, ceiling=True) if big_sector else None,
    }
    used = {k: DIVERSIFICATION_WEIGHTS[k] for k, v in comps.items() if v is not None}
    score = (100.0 * sum(used[k] * comps[k] for k in used) / (4.0 * sum(used.values()))) if used else None
    if comps["largest_sector"] is None:
        notes.append("No sector was known for any holding, so the sector measure is left out and the other two "
                     "carry the score.")
    level = _level(score, DIVERSIFICATION_LEVELS)
    summary = ("{}: about {:.1f} effective holdings; the largest, {}, is {:.1f}% and the top five {:.1f}%{}."
               .format(level, eff or 0.0, top1_name, top1 or 0.0, top5,
                       "; the largest sector, {}, is {:.1f}%".format(big_sector[0], big_sector[1])
                       if big_sector else ""))
    summary += " Based on {} holdings.".format("look-through" if basis == "look-through" else "direct")
    return _assessment(
        "diversification", label, level=level, score=_r(score, 0),
        summary=summary,
        inputs={"basis": basis, "effective_holdings": _r(eff, 2), "hhi": _r(hhi, 4),
                "top1": top1_name, "top1_pct": _r(top1), "top5_pct": _r(top5),
                "largest_sector": big_sector[0] if big_sector else None,
                "largest_sector_pct": _r(big_sector[1]) if big_sector else None,
                "sector_coverage_pct": _r(sector_cov), "holdings_count": len(rows),
                "components": comps, "notes": notes},
        method=("Effective holdings is 1 / HHI, where HHI is the sum of squared weights (by US-dollar value, long "
                "holdings only; cash and options are outside it). Each of three measures is graded 0 to 4: "
                "effective holdings 4 at 20 or more, 3 at 12, 2 at 7, 1 at 4; the largest position 4 at 5% or "
                "less, 3 at 10%, 2 at 20%, 1 at 35%; the largest sector 4 at 25% or less, 3 at 35%, 2 at 45%, "
                "1 at 60%; else 0. The score is the weighted mean of the grades, out of 4, times 25. Levels: "
                "75 and over well diversified, 50 moderately, 25 concentrated, below that highly concentrated. "
                "With look-through, a company held directly and inside funds is one exposure."),
        weights=DIVERSIFICATION_WEIGHTS,
        coverage_pct=_r(100.0 * (1.0 - uncovered)),
        drivers=drivers, not_assessed=skipped)


# ================================================================= 2. financial quality

def _is_fund(row: Dict[str, Any], f: Optional[Dict[str, Any]]) -> bool:
    if row["kind"] in FUNDLIKE:
        return True
    qt = str((f or {}).get("quote_type") or "").upper()
    return qt in FUND_QUOTE_TYPES


def _quality_one(f: Dict[str, Any]) -> Dict[str, Any]:
    vals = {k: _num(f.get(k)) for k in ("return_on_equity", "operating_margin", "free_cash_flow",
                                        "total_revenue", "debt_to_equity", "revenue_growth")}
    fcf_margin = None
    if vals["free_cash_flow"] is not None and vals["total_revenue"] and vals["total_revenue"] > 0:
        fcf_margin = vals["free_cash_flow"] / vals["total_revenue"]
    vals["fcf_margin"] = fcf_margin
    financial = str(f.get("sector") or "").strip().lower() in FINANCIAL_SECTORS
    negative_equity = vals["debt_to_equity"] is not None and vals["debt_to_equity"] < 0
    comps: Dict[str, Dict[str, Any]] = {}
    for cid, m in QUALITY_MEASURES.items():
        x = vals[m["field"]]
        if financial and cid in ("balance_sheet", "cash_generation"):
            comps[cid] = {"status": "not_applicable", "score": None, "value": x,
                          "reason": "A bank or insurer: borrowing is its raw material and free cash flow does not "
                                    "describe it."}
        elif negative_equity and cid in ("balance_sheet", "profitability"):
            comps[cid] = {"status": "not_applicable", "score": None, "value": x,
                          "reason": "Shareholders' equity is negative (often from buybacks), so ratios on equity "
                                    "have no meaning."}
        elif x is None:
            comps[cid] = {"status": "insufficient", "score": None, "value": None, "reason": "Not reported."}
        else:
            comps[cid] = {"status": "scored", "score": _band(x, m["bands"], m["ceiling"]), "value": _r(x, 4)}
    scored = [c["score"] for c in comps.values() if c["status"] == "scored"]
    return {"components": comps, "measures": len(scored),
            "score": 25.0 * sum(scored) / len(scored) if len(scored) >= MIN_QUALITY_MEASURES else None}


def _quality(rows: List[Dict[str, Any]], skipped: List[Dict[str, Any]],
             funds: Dict[str, Optional[Dict[str, Any]]]) -> Dict[str, Any]:
    assessed: List[Dict[str, Any]] = []
    not_assessed = list(skipped)
    for r in rows:
        f = funds.get(r["symbol"])
        wp = _r(100.0 * r["weight"])
        if _is_fund(r, f):
            not_assessed.append({"symbol": r["symbol"], "weight_pct": wp,
                                 "reason": "A fund: company financials do not describe it. Its holdings are in the "
                                           "look-through exposure."})
            continue
        if r["kind"] not in STOCKLIKE:
            not_assessed.append({"symbol": r["symbol"], "weight_pct": wp,
                                 "reason": "Not a company ({}).".format(r["kind"])})
            continue
        if not f:
            not_assessed.append({"symbol": r["symbol"], "weight_pct": wp,
                                 "reason": "No fundamentals were available. Left out, not scored low."})
            continue
        q = _quality_one(f)
        if q["score"] is None:
            not_assessed.append({"symbol": r["symbol"], "weight_pct": wp,
                                 "reason": "Only {} of 5 measures were reported; {} are needed. Left out, not "
                                           "scored low.".format(q["measures"], MIN_QUALITY_MEASURES)})
            continue
        assessed.append(dict(r, quality=q))
    total = sum(r["weight"] for r in rows) + 0.0
    covered = sum(r["weight"] for r in assessed)
    coverage = 100.0 * covered / total if total else None
    method = ("Each stock is graded 0 to 4 on up to five measures from its reported fundamentals: {} A bank or "
              "insurer is not graded on debt to equity or free cash flow, and a company with negative equity "
              "is not graded on the two equity ratios. A stock's score is the mean of the measures it has, out "
              "of 4, times 25, and needs at least {} measures. The portfolio score is the value-weighted mean over "
              "the stocks assessed. Levels: 75 and over strong, 55 sound, 35 mixed, below that weak. Funds, "
              "non-companies and stocks with missing data are listed as not assessed and never scored low."
              .format(" ".join(m["rubric"] for m in QUALITY_MEASURES.values()), MIN_QUALITY_MEASURES))
    weights = {k: 0.2 for k in QUALITY_MEASURES}
    if not assessed:
        return _assessment("financial_quality", "Financial quality", summary=(
            "No stock could be assessed: {}.".format("every holding is a fund or lacks fundamentals")
            if rows else "No holdings."), method=method, weights=weights,
            coverage_pct=0.0 if rows else None, not_assessed=not_assessed,
            inputs={"stocks_assessed": 0})
    score = sum(r["weight"] * r["quality"]["score"] for r in assessed) / covered
    level = _level(score, QUALITY_LEVELS)
    drivers = sorted(assessed, key=lambda r: -abs(r["weight"] * (r["quality"]["score"] - score)))[:5]
    details = [{"symbol": r["symbol"], "weight_pct": _r(100.0 * r["weight"]),
                "score": _r(r["quality"]["score"], 0), "level": _level(r["quality"]["score"], QUALITY_LEVELS),
                "components": r["quality"]["components"]} for r in assessed]
    summary = "{}: value-weighted {:.0f} out of 100 across {} stock{} covering {:.1f}% of value.".format(
        level, score, len(assessed), "" if len(assessed) == 1 else "s", coverage)
    if coverage < 50.0:
        summary += " Most of the portfolio is not assessed, so this describes the minority that is."
    return _assessment(
        "financial_quality", "Financial quality", level=level, score=_r(score, 0), summary=summary,
        inputs={"stocks_assessed": len(assessed), "holdings": details, "fields": FUNDAMENTALS_KEYS},
        method=method, weights=weights, coverage_pct=_r(coverage),
        drivers=[{"symbol": r["symbol"], "weight_pct": _r(100.0 * r["weight"]),
                  "score": _r(r["quality"]["score"], 0),
                  "pulls": "up" if r["quality"]["score"] >= score else "down"} for r in drivers],
        not_assessed=not_assessed)


# ================================================================= 3. valuation

def earnings_yield(f: Dict[str, Any]) -> Tuple[Optional[float], Optional[str]]:
    """(E/P, "forward"|"trailing"); forward first. Negative when earnings are."""
    price = _num(f.get("price"))
    for basis in ("forward", "trailing"):
        pe = _num(f.get(basis + "_pe"))
        if pe is not None and pe != 0:
            return 1.0 / pe, basis
        eps = _num(f.get(basis + "_eps"))
        if eps is not None and price and price > 0:
            return eps / price, basis
    return None, None


def _valuation(rows: List[Dict[str, Any]], skipped: List[Dict[str, Any]],
               funds: Dict[str, Optional[Dict[str, Any]]], market: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    market = market or {}
    mpe, ten = _num(market.get("pe")), _num(market.get("ten_year"))
    if ten is not None and ten > 1.0:
        # Expected as a decimal (0.041); a value above 1 can only be percent
        # (4.1), since no 10-year Treasury has yielded 100%.
        ten = ten / 100.0
    assessed, not_assessed = [], list(skipped)
    for r in rows:
        f = funds.get(r["symbol"])
        wp = _r(100.0 * r["weight"])
        if _is_fund(r, f) or r["kind"] not in STOCKLIKE:
            not_assessed.append({"symbol": r["symbol"], "weight_pct": wp,
                                 "reason": "A fund or non-company: no earnings of its own from this source."})
            continue
        ey, basis = earnings_yield(f or {})
        if ey is None:
            not_assessed.append({"symbol": r["symbol"], "weight_pct": wp,
                                 "reason": "No P/E or earnings per share was available."})
            continue
        assessed.append(dict(r, ey=ey, basis=basis))
    total = sum(r["weight"] for r in rows)
    covered = sum(r["weight"] for r in assessed)
    method = ("Each stock's earnings yield is forward earnings over price (1 / forward P/E), or trailing where no "
              "forward figure exists. The portfolio's is the value-weighted mean over the stocks assessed, the "
              "same as their combined earnings over their combined value, and its P/E is the reciprocal. "
              "Loss-making companies enter with negative yields, so they make the portfolio look richer, never "
              "cheaper. Compared with the S&P 500's forward P/E: more than {:.0f}% above it is richer, more than "
              "{:.0f}% below is cheaper, otherwise in line. Without a market P/E the earnings yield is set "
              "beside the 10-year Treasury yield, a rough comparison that ignores growth. No 0-100 score: a "
              "cheaper reading describes the price, it does not forecast a return."
              .format(100 * VALUATION_BAND, 100 * VALUATION_BAND))
    if not assessed:
        return _assessment("valuation", "Valuation", summary="No stock had earnings data to value.", method=method,
                           coverage_pct=0.0 if rows else None, not_assessed=not_assessed,
                           inputs={"market_pe": mpe, "ten_year": ten})
    ey = sum(r["weight"] * r["ey"] for r in assessed) / covered
    pe = 1.0 / ey if ey > 0 else None
    losers = [r for r in assessed if r["ey"] < 0]
    loser_pct = 100.0 * sum(r["weight"] for r in losers) / covered
    fwd_pct = 100.0 * sum(r["weight"] for r in assessed if r["basis"] == "forward") / covered
    ratio = (pe / mpe) if pe and mpe and mpe > 0 else None
    if ey <= 0:
        level = "Loss-making in aggregate"
        summary = ("The stocks assessed lose money in aggregate (earnings yield {:.2f}%), so there is no P/E to "
                   "compare. That is not cheapness.".format(100 * ey))
    elif ratio is not None:
        if ratio > 1 + VALUATION_BAND:
            level = "Richer than the S&P 500"
        elif ratio < 1 - VALUATION_BAND:
            level = "Cheaper than the S&P 500"
        else:
            level = "In line with the S&P 500"
        summary = "{}: about {:.1f}x earnings against the S&P 500's {:.1f}x forward.".format(level, pe, mpe)
    elif ten is not None:
        level = ("Earnings yield above the 10-year Treasury yield" if ey > ten
                 else "Earnings yield below the 10-year Treasury yield")
        summary = "{}: {:.2f}% against {:.2f}% (about {:.1f}x earnings). No S&P 500 P/E was available.".format(
            level, 100 * ey, 100 * ten, pe)
    else:
        level = "No market comparison"
        summary = "About {:.1f}x earnings. No S&P 500 P/E or Treasury yield was available to compare.".format(pe)
    if losers:
        summary += " {:.1f}% of the value assessed is in loss-making companies ({}), counted as negative earnings." \
            .format(loser_pct, ", ".join(r["symbol"] for r in losers[:5]))
    if fwd_pct < 100.0:
        summary += " {:.0f}% of it uses forward earnings and the rest trailing.".format(fwd_pct)
    drivers = sorted(assessed, key=lambda r: -abs(r["weight"] * (r["ey"] - ey)))[:5]
    return _assessment(
        "valuation", "Valuation", level=level, score=None, summary=summary,
        inputs={"earnings_yield_pct": _r(100 * ey), "pe": _r(pe, 1), "market_pe": mpe,
                "market_earnings_yield_pct": _r(100.0 / mpe) if mpe else None,
                "pe_vs_market": _r(ratio, 3), "ten_year_pct": _r(100 * ten) if ten is not None else None,
                "forward_basis_pct": _r(fwd_pct), "loss_making_pct": _r(loser_pct),
                "loss_making": [{"symbol": r["symbol"], "weight_pct": _r(100.0 * r["weight"]),
                                 "earnings_yield_pct": _r(100 * r["ey"]), "basis": r["basis"]} for r in losers],
                "holdings": [{"symbol": r["symbol"], "weight_pct": _r(100.0 * r["weight"]),
                              "earnings_yield_pct": _r(100 * r["ey"]),
                              "pe": _r(1.0 / r["ey"], 1) if r["ey"] > 0 else None, "basis": r["basis"]}
                             for r in assessed]},
        method=method, weights={"value_weighted": True},
        coverage_pct=_r(100.0 * covered / total) if total else None,
        drivers=[{"symbol": r["symbol"], "weight_pct": _r(100.0 * r["weight"]),
                  "pe": _r(1.0 / r["ey"], 1) if r["ey"] > 0 else None,
                  "earnings_yield_pct": _r(100 * r["ey"]),
                  "pulls": "cheaper" if r["ey"] > ey else "richer"} for r in drivers],
        not_assessed=not_assessed)


# ================================================================= 4. volatility

def _volatility(rows: List[Dict[str, Any]], skipped: List[Dict[str, Any]], closes: Dict[str, Any],
                benchmark_closes: Any) -> Dict[str, Any]:
    bench_label = "the benchmark"
    if isinstance(benchmark_closes, dict) and benchmark_closes.get("symbol"):
        bench_label = str(benchmark_closes["symbol"])
    h = history_risk({r["symbol"]: r["value"] for r in rows}, closes or {}, benchmark_closes)
    weights = {r["symbol"]: _r(100.0 * r["weight"]) for r in rows}
    not_assessed = list(skipped) + [dict(e, weight_pct=weights.get(e["symbol"])) for e in h.get("excluded") or []]
    method = ("Daily simple returns over the window shown, for the holdings with at least {} days of history "
              "overlapping the benchmark's. Volatility is the standard deviation of the daily return of a portfolio "
              "held at today's weights (re-weighted among the holdings with history), times the square root of "
              "252. Beta is the covariance of that return with the benchmark's over its variance. The maximum "
              "drawdown is a backtest of today's weights over the window, not your actual history: you did not "
              "necessarily hold these weights then. Levels compare volatility with the benchmark's: below 0.8x "
              "calmer, up to 1.2x similar, up to 1.6x more volatile, above that much more volatile. No 0-100 "
              "score: lower volatility is not better or safer in itself.".format(MIN_OVERLAP_DAYS))
    if not h.get("available"):
        return _assessment("volatility", "Volatility", summary=h.get("reason") or "No price history.",
                           method=method, coverage_pct=h.get("coverage_pct"), not_assessed=not_assessed)
    vol, bvol = h["portfolio_vol_pct"], h["benchmark_vol_pct"]
    if bvol:
        ratio = vol / bvol
        level = next((name for edge, name in VOL_RATIO_LEVELS if ratio < edge), "Much more volatile than the benchmark")
        level = level.replace("the benchmark", bench_label)
        summary = ("{}: {:.1f}% a year against {:.1f}% for {}{}. A portfolio held at today's weights would have "
                   "fallen as much as {:.1f}% over the window ({} to {}); {} fell {:.1f}%."
                   .format(level, vol, bvol, bench_label,
                           ", beta {:.2f}".format(h["beta"]) if h["beta"] is not None else "",
                           -h["max_drawdown_pct"], h["window"]["start"], h["window"]["end"], bench_label,
                           -(h["benchmark_max_drawdown_pct"] or 0.0)))
    else:
        level = next((name for edge, name in VOL_ABSOLUTE_LEVELS if vol / 100.0 < edge), "Very high volatility")
        summary = ("{}: {:.1f}% a year. No benchmark history, so no beta. Held at today's weights it would have "
                   "fallen as much as {:.1f}% over the window.".format(level, vol, -h["max_drawdown_pct"]))
    summary += " History, not a forecast."
    return _assessment(
        "volatility", "Volatility", level=level, score=None, summary=summary,
        inputs={"window": h["window"], "portfolio_vol_pct": vol, "benchmark": bench_label,
                "benchmark_vol_pct": bvol, "beta": h["beta"], "correlation": h["correlation"],
                "max_drawdown_pct": h["max_drawdown_pct"],
                "max_drawdown_label": "A backtest of today's weights over the window, not your actual history.",
                "benchmark_max_drawdown_pct": h["benchmark_max_drawdown_pct"],
                "weights_used_pct": h["weights_used"]},
        method=method, weights={"todays_weights": True}, coverage_pct=h["coverage_pct"],
        drivers=h["risk_contributions"][:5], not_assessed=not_assessed)


# ================================================================= 5. event exposure

def _day(v: Any) -> Optional[date]:
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


def _events(rows: List[Dict[str, Any]], skipped: List[Dict[str, Any]], events: Iterable[Dict[str, Any]],
            today: date) -> Dict[str, Any]:
    weights = {r["symbol"]: 100.0 * r["weight"] for r in rows}
    by_symbol: Dict[str, Dict[str, Any]] = {}
    options: List[Dict[str, Any]] = []
    for e in events or []:
        d = _day(e.get("date"))
        sym = str(e.get("symbol") or "").upper()
        if not d or not sym:
            continue
        days = (d - today).days
        kind = e.get("kind")
        if kind == "option_expiry":
            if 0 <= days <= OPTION_WINDOW_DAYS:
                options.append({"symbol": sym, "date": d.isoformat(), "days": days,
                                "contracts": _num(e.get("contracts")), "value": _num(e.get("value"))})
            continue
        if kind not in ("earnings", "ex_dividend") or not (0 <= days <= EVENT_WINDOW_DAYS):
            continue
        w = _num(e.get("weight_pct"))
        s = by_symbol.setdefault(sym, {"symbol": sym, "weight_pct": None, "kinds": [], "events": [],
                                       "confirmed": False})
        if s["weight_pct"] is None:
            s["weight_pct"] = w if w is not None else weights.get(sym)
        if kind not in s["kinds"]:
            s["kinds"].append(kind)
        s["events"].append({"kind": kind, "date": d.isoformat(), "days": days, "confirmed": bool(e.get("confirmed"))})
        s["confirmed"] = s["confirmed"] or bool(e.get("confirmed"))
    hit = list(by_symbol.values())

    def share(items: Iterable[Dict[str, Any]]) -> float:
        return sum(i["weight_pct"] or 0.0 for i in items)

    total = share(hit)
    conf = share(i for i in hit if i["confirmed"])
    kinds = {}
    for k in ("earnings", "ex_dividend"):
        items = [i for i in hit if k in i["kinds"]]
        kinds[k] = {"pct": _r(share(items)),
                    "confirmed_pct": _r(share(i for i in items if any(ev["kind"] == k and ev["confirmed"]
                                                                       for ev in i["events"]))),
                    "symbols": [i["symbol"] for i in items]}
        kinds[k]["estimated_pct"] = _r((kinds[k]["pct"] or 0.0) - (kinds[k]["confirmed_pct"] or 0.0))
    not_assessed = list(skipped) + [
        {"symbol": r["symbol"], "weight_pct": _r(100.0 * r["weight"]),
         "reason": "No event calendar for this asset type ({}).".format(r["kind"])}
        for r in rows if r["kind"] not in STOCKLIKE + FUNDLIKE]
    covered = sum(r["weight"] for r in rows if r["kind"] in STOCKLIKE + FUNDLIKE)
    level = next((name for edge, name in EVENT_LEVELS if total < edge), "High event exposure")
    summary = ("{}: {:.1f}% of value has an earnings report or ex-dividend date in the next {} days ({:.1f}% "
               "confirmed, {:.1f}% on estimated dates).".format(level, total, EVENT_WINDOW_DAYS, conf, total - conf))
    if options:
        summary += " {} option position{} expire{} within {} days.".format(
            len(options), "" if len(options) == 1 else "s", "s" if len(options) == 1 else "", OPTION_WINDOW_DAYS)
    return _assessment(
        "event_exposure", "Event exposure", level=level, score=None, summary=summary,
        inputs={"window_days": EVENT_WINDOW_DAYS, "with_event_pct": _r(total), "confirmed_pct": _r(conf),
                "estimated_pct": _r(total - conf), "by_kind": kinds,
                "options_expiring": {"window_days": OPTION_WINDOW_DAYS, "count": len(options),
                                     "contracts": _r(sum(abs(o["contracts"] or 0.0) for o in options), 4),
                                     "value": _r(sum(o["value"] or 0.0 for o in options)),
                                     "positions": sorted(options, key=lambda o: o["days"])}},
        method=("The share of portfolio value in holdings with an earnings report or an ex-dividend date from "
                "today to {} days ahead, each holding counted once whatever it has scheduled. A holding with any "
                "confirmed date counts as confirmed; an estimated earnings date is the company's expected window, "
                "not an announcement. Weights are the event calendar's share of long value. Option expiries "
                "within {} days are listed separately, because options are outside the holdings' weights. "
                "Levels: under 10% low, under 30% moderate, otherwise high; in the busiest weeks of an earnings "
                "season a high reading is ordinary. No 0-100 score: a scheduled event is neither good nor bad."
                .format(EVENT_WINDOW_DAYS, OPTION_WINDOW_DAYS)),
        weights={"value_weighted": True},
        coverage_pct=_r(100.0 * covered) if rows else None,
        drivers=[{"symbol": i["symbol"], "weight_pct": _r(i["weight_pct"]), "kinds": i["kinds"],
                  "events": i["events"], "confirmed": i["confirmed"]}
                 for i in sorted(hit, key=lambda i: -(i["weight_pct"] or 0.0))[:8]],
        not_assessed=not_assessed)


# ================================================================= the card

def build(holdings: List[Dict[str, Any]], exposure: Optional[Dict[str, Any]],
          fundamentals_of: Callable[[str], Optional[Dict[str, Any]]], closes: Dict[str, Any],
          benchmark_closes: Any, events: List[Dict[str, Any]], market: Optional[Dict[str, Any]],
          today: date) -> Dict[str, Any]:
    """Five separate assessments of the long holdings in `holdings`
    (portfolio.build's, with value_usd). No overall score."""
    rows, skipped = _book(holdings)
    funds: Dict[str, Optional[Dict[str, Any]]] = {}
    for r in rows:
        if r["kind"] in STOCKLIKE:
            got = _call(fundamentals_of, r["symbol"])
            funds[r["symbol"]] = got if isinstance(got, dict) and got else None
    assessments = [
        _diversification(rows, skipped, exposure),
        _quality(rows, skipped, funds),
        _valuation(rows, skipped, funds, market),
        _volatility(rows, skipped, closes, benchmark_closes),
        _events(rows, skipped, events, today),
    ]
    return {
        "version": VERSION,
        "as_of": today.isoformat(),
        "assessments": assessments,
        "overall": None,
        "overall_note": "There is no overall score. Each assessment measures something different, and an average "
                        "of them would be more confident than any of its parts.",
        "disclaimer": DISCLAIMER,
        "basis": "Long holdings (stocks, ETFs, funds, bonds, crypto) by US-dollar value. Cash and options are "
                 "outside these weights.",
        "holdings_counted": len(rows),
        "limitations": [
            "Fundamentals are the data provider's latest figures, not read from filings here; a restatement or a "
            "stale field passes through.",
            "Volatility, beta and drawdown describe the last year of prices at today's weights. They are history, "
            "not a forecast.",
            "Event dates can move; an estimated earnings date is not an announcement.",
            "Valuation mixes forward and trailing earnings where forward estimates are missing.",
        ],
    }


# ================================================================= Yahoo mapping

def fundamentals_from_yahoo(info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Yahoo `.info` keys into the FUNDAMENTALS_KEYS dict, units normalised.

    Yahoo's debtToEquity is in percent (154.5 means debt is 1.545x equity),
    unlike every other ratio it returns, which are decimals; it is divided by
    100 here. "Infinity" and NaN strings, which Yahoo sends for some P/Es,
    become None."""
    info = info or {}

    def g(*keys: str) -> Optional[float]:
        for k in keys:
            v = _num(info.get(k))
            if v is not None:
                return v
        return None

    de = g("debtToEquity")
    qt = info.get("quoteType")
    return {
        "return_on_equity": g("returnOnEquity"),
        "operating_margin": g("operatingMargins"),
        "free_cash_flow": g("freeCashflow"),
        "total_revenue": g("totalRevenue"),
        "debt_to_equity": de / 100.0 if de is not None else None,
        "revenue_growth": g("revenueGrowth"),
        "forward_pe": g("forwardPE"),
        "trailing_pe": g("trailingPE"),
        "forward_eps": g("forwardEps"),
        "trailing_eps": g("trailingEps", "epsTrailingTwelveMonths"),
        "price": g("currentPrice", "regularMarketPrice"),
        "quote_type": str(qt).upper() if qt else None,
        "sector": info.get("sector") or None,
        "source": "Yahoo Finance",
    }
