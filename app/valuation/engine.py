"""The valuation formulas. Pure functions: numbers in, numbers out, no I/O.

Every model here takes a `base` (what the company reported, already sourced by
`inputs`) and a set of `drivers` (the assumptions, the reader's or the defaults)
and returns a result that shows its working: the year-by-year forecast, the
discounting, the terminal value and the bridge from enterprise value to a value
per share. Nothing is rounded inside the arithmetic. Rounding is for display.

Conventions, stated once here and in METHODS.md:

* **Money** is in the statements' currency, in units (not thousands or
  millions). Rates are decimals: 0.08 is 8%.
* **Free cash flow to the firm** is EBIT x (1 - tax) + D&A - capex - change in
  operating working capital. Stock-based compensation is left in EBIT as the
  expense GAAP records, and is *not* added back. Dilution from awards already
  granted is in the share count; future grants are paid for through that
  expense. Adding SBC back and also counting future dilution would charge it
  twice; adding it back and ignoring dilution would charge it never.
* **Operating leases** stay operating: their cost is inside EBIT, so their
  liability is not debt here. Counting the liability as debt without adding the
  lease cost back to EBIT would charge the leases twice. **Finance leases** are
  debt: their interest is below EBIT and their principal is a financing flow.
* **Timing.** Cash and debt are taken at the balance-sheet date, so the cash
  flows counted are those after it. The first forecast year is the fiscal year
  that contains the balance-sheet date, scaled to the part of it still to come
  (the stub). Discount times run from the valuation date. With the mid-year
  convention each year's flow arrives at its middle.
* **Terminal value** is a perpetuity from the year after the forecast, valued
  at the end of the last forecast year. The default "value driver" form ties
  growth to reinvestment: FCFF = NOPAT x (1 - g / RONIC), so faster growth costs
  cash, which the plain growing-perpetuity form does not insist on.
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

DAYS_PER_YEAR = 365.25

# Validation thresholds, named so the checks and the docs agree.
MIN_SPREAD_WACC_G = 0.01       # warn when the discount rate is within 1 point of growth
MAX_HORIZON, MIN_HORIZON = 15, 3


class ModelError(ValueError):
    """An assumption set that has no meaningful answer (growth at or above the
    discount rate, a negative share count). Raised so the caller shows the
    reason instead of a number."""


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _d(value: Any) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def add_years(day: date, years: int) -> date:
    """The same calendar day `years` later; 29 February becomes the 28th."""
    try:
        return day.replace(year=day.year + years)
    except ValueError:
        return day.replace(year=day.year + years, day=28)


def linear_path(start: float, target: float, n: int, reach: Optional[int] = None) -> List[float]:
    """`n` yearly values moving in equal steps from `start` (year 1) to
    `target`, reached in year `reach` (default: the last year) and held."""
    reach = n if reach is None else max(1, min(int(reach), n))
    if reach == 1:
        return [float(target)] * n
    out = []
    for t in range(1, n + 1):
        if t >= reach:
            out.append(float(target))
        else:
            out.append(start + (target - start) * (t - 1) / (reach - 1))
    return out


def growth_path(g1: float, g_terminal: float, n: int, g2: Optional[float] = None) -> List[float]:
    """Revenue growth by year: g1 in year 1 (and g2 in year 2 when given),
    then equal steps toward the terminal growth rate, which the year *after*
    the forecast reaches. So the last forecast year still sits a step above
    terminal growth rather than jumping to it."""
    if g2 is None or n < 2:
        return [g1 + (g_terminal - g1) * (t - 1) / n for t in range(1, n + 1)]
    out = [g1, g2]
    steps = n - 1
    for t in range(3, n + 1):
        out.append(g2 + (g_terminal - g2) * (t - 2) / steps)
    return out[:n]


def apply_overrides(path: List[float], overrides: Optional[Dict[Any, Any]]) -> List[float]:
    """Explicit per-year values the reader typed into the forecast table win
    over the driver-generated path. Keys are 1-based year numbers."""
    if not overrides:
        return path
    out = list(path)
    for key, value in overrides.items():
        try:
            year = int(key)
        except (TypeError, ValueError):
            continue
        if 1 <= year <= len(out) and value is not None:
            out[year - 1] = float(value)
    return out


def discount_factor(rate: float, years: float) -> float:
    return (1.0 + rate) ** (-years)


# ---------------------------------------------------------------------------
# Cost of capital
# ---------------------------------------------------------------------------

def cost_of_equity(risk_free: float, beta: float, erp: float, extra: float = 0.0) -> float:
    """CAPM: risk-free + beta x equity risk premium (+ any premium the reader
    adds, such as for size or country risk, shown separately)."""
    return risk_free + beta * erp + extra


def wacc(cost_equity: float, pre_tax_cost_debt: float, tax_rate: float,
         equity_value: float, debt_value: float) -> Dict[str, float]:
    """Weighted average cost of capital from market equity and book debt.

    Weights use gross debt, not net debt: cash is valued separately in the
    bridge, so netting it here as well would count it twice."""
    if equity_value <= 0:
        raise ModelError("The equity weight needs a positive market value.")
    debt_value = max(0.0, debt_value)
    total = equity_value + debt_value
    we, wd = equity_value / total, debt_value / total
    after_tax_debt = pre_tax_cost_debt * (1.0 - tax_rate)
    return {"wacc": we * cost_equity + wd * after_tax_debt, "weight_equity": we,
            "weight_debt": wd, "cost_equity": cost_equity, "pre_tax_cost_debt": pre_tax_cost_debt,
            "after_tax_cost_debt": after_tax_debt, "tax_rate": tax_rate}


# Damodaran's synthetic-rating table for large non-financial firms (data as of
# January 2026): interest coverage (EBIT / interest expense) -> rating, default
# spread over the risk-free rate. Lower bound inclusive.
SYNTHETIC_RATINGS: Tuple[Tuple[float, str, float], ...] = (
    (8.5, "AAA", 0.0040), (6.5, "AA", 0.0055), (5.5, "A+", 0.0070), (4.25, "A", 0.0078),
    (3.0, "A-", 0.0089), (2.5, "BBB", 0.0111), (2.25, "BB+", 0.0138), (2.0, "BB", 0.0184),
    (1.75, "B+", 0.0275), (1.5, "B", 0.0321), (1.25, "B-", 0.0509), (0.8, "CCC", 0.0885),
    (0.65, "CC", 0.1261), (0.2, "C", 0.1600), (float("-inf"), "D", 0.1900),
)
SYNTHETIC_SOURCE = ("Damodaran, ratings, interest coverage ratios and default spreads, "
                    "large non-financial firms, data as of January 2026 "
                    "(pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/ratings.html)")


def synthetic_rating(ebit: Optional[float], interest: Optional[float]) -> Dict[str, Any]:
    """A rating and default spread implied by interest coverage. A company with
    no interest expense is treated as top-rated, and says so."""
    if interest is None or interest <= 0:
        return {"rating": "AAA", "spread": SYNTHETIC_RATINGS[0][2], "coverage": None,
                "note": "No interest expense reported, so coverage is unbounded."}
    if ebit is None:
        return {"rating": None, "spread": None, "coverage": None,
                "note": "No operating income to measure coverage."}
    coverage = ebit / interest
    for floor, rating, spread in SYNTHETIC_RATINGS:
        if coverage >= floor:
            return {"rating": rating, "spread": spread, "coverage": coverage, "note": None}
    return {"rating": "D", "spread": SYNTHETIC_RATINGS[-1][2], "coverage": coverage, "note": None}


# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------

def timing(fy0_end: Any, balance_date: Any, valuation_date: Any, n: int,
           convention: str = "mid_year") -> Dict[str, Any]:
    """Fiscal-year ends, the first year's stub and each flow's discount time.

    The first forecast year is the fiscal year after FY0. If the balance sheet
    is from inside that year (a 10-Q), only the part after it is counted. A
    10-Q from a later year than FY0+1 means FY0 is stale; the caller rebases."""
    fy0, bal, val = _d(fy0_end), _d(balance_date), _d(valuation_date)
    ends = [add_years(fy0, t) for t in range(1, n + 1)]
    fy_len = (ends[0] - fy0).days or 365
    stub = (ends[0] - max(bal, fy0)).days / fy_len
    stub = min(1.0, max(0.0, stub))
    # Time is measured in fiscal years: the first year-end is the fraction of
    # FY1 between the valuation date and its end, and each later one is one
    # full year further. Counting days over 365.25 instead would make a
    # 365-day year 0.9993 years long and every whole-year case inexact.
    first = (ends[0] - val).days / fy_len
    end_times = [first + t for t in range(n)]
    if convention == "end_year":
        flow_times = list(end_times)
    elif convention == "mid_year":
        flow_times = [end_times[0] - stub / 2.0] + [t - 0.5 for t in end_times[1:]]
    else:
        raise ModelError("Unknown discounting convention: {}".format(convention))
    # A flow dated before the valuation date (part of the first stub can be)
    # is not compounded forward; it counts at face value.
    flow_times = [max(0.0, t) for t in flow_times]
    return {"fiscal_year_ends": [e.isoformat() for e in ends], "stub_fraction": stub,
            "end_times": end_times, "flow_times": flow_times, "convention": convention}


# ---------------------------------------------------------------------------
# Operating forecast (shared by FCFF, FCFE and the three-statement model)
# ---------------------------------------------------------------------------

def expand_drivers(drivers: Dict[str, Any]) -> Dict[str, List[float]]:
    """Turn compact drivers (start, target, years to reach) into per-year paths,
    then apply any per-year values typed into the table."""
    n = int(drivers["horizon"])
    g = drivers["growth"]
    t = drivers["terminal"]
    m = drivers["margin"]
    c = drivers["capex_pct"]
    tx = drivers["tax"]
    ov = drivers.get("overrides") or {}
    paths = {
        "revenue_growth": growth_path(g["y1"], t["growth"], n, g.get("y2")),
        "ebit_margin": linear_path(m["start"], m["target"], n, m.get("years")),
        "capex_pct": linear_path(c["start"], c["target"], n, c.get("years")),
        "tax_rate": linear_path(tx["start"], tx["terminal"], n, tx.get("years")),
        "nwc_pct": [float(drivers["nwc_pct"])] * n,
    }
    if drivers.get("da_pct") is not None:
        paths["da_pct"] = [float(drivers["da_pct"])] * n
    for key in list(paths):
        paths[key] = apply_overrides(paths[key], ov.get(key))
    return paths


def operating_forecast(base: Dict[str, Any], drivers: Dict[str, Any]) -> Dict[str, Any]:
    """Revenue, EBIT, operating taxes, NOPAT, D&A, capex, working capital,
    invested capital and FCFF for each forecast year.

    D&A follows the asset base: D&A = depreciation rate x opening net PP&E, and
    PP&E rolls forward by capex less D&A. So a burst of capex shows up in later
    depreciation instead of vanishing. Without a PP&E figure, D&A falls back to
    a share of revenue."""
    n = int(drivers["horizon"])
    if not (MIN_HORIZON <= n <= MAX_HORIZON):
        raise ModelError("The forecast horizon must be {} to {} years.".format(MIN_HORIZON, MAX_HORIZON))
    paths = expand_drivers(drivers)
    rev_prev = float(base["revenue"])
    if rev_prev <= 0:
        raise ModelError("A cash-flow forecast needs positive revenue in the base year.")
    ppe_prev = base.get("ppe")
    dep_rate = drivers.get("dep_rate")
    use_ppe = ppe_prev is not None and dep_rate is not None and drivers.get("da_pct") is None
    nwc_prev = float(base.get("nwc") if base.get("nwc") is not None else paths["nwc_pct"][0] * rev_prev)
    ic_prev = base.get("invested_capital")
    nol = float(base.get("nol") or 0.0)
    da_path: List[float] = []
    if not use_ppe:
        if paths.get("da_pct") is not None:
            da_path = paths["da_pct"]
        elif base.get("da_pct") is not None:
            da_path = [float(base["da_pct"])] * n
        else:
            raise ModelError("Depreciation needs either net PP&E with a depreciation rate or a "
                             "D&A share of revenue; neither is available, and it is not assumed "
                             "to be zero.")

    rows: List[Dict[str, Any]] = []
    for i in range(n):
        g = paths["revenue_growth"][i]
        revenue = rev_prev * (1.0 + g)
        margin = paths["ebit_margin"][i]
        ebit = revenue * margin
        rate = paths["tax_rate"][i]
        if ebit < 0:
            nol += -ebit
            taxable = 0.0
        else:
            used = min(nol, ebit)
            nol -= used
            taxable = ebit - used
        taxes = taxable * rate
        nopat = ebit - taxes
        capex = revenue * paths["capex_pct"][i]
        if use_ppe:
            da = dep_rate * ppe_prev
            ppe = ppe_prev + capex - da
        else:
            da = revenue * da_path[i]
            ppe = None if ppe_prev is None else ppe_prev + capex - da
        nwc = revenue * paths["nwc_pct"][i]
        d_nwc = nwc - nwc_prev
        fcff = nopat + da - capex - d_nwc
        net_reinvest = capex - da + d_nwc
        ic = None if ic_prev is None else ic_prev + net_reinvest
        roic = (nopat / ic_prev) if (ic_prev is not None and ic_prev > 0) else None
        rows.append({
            "year": i + 1, "revenue": revenue, "revenue_growth": g, "ebit": ebit,
            "ebit_margin": margin, "tax_rate": rate, "taxes": taxes, "nopat": nopat,
            "nol_remaining": nol, "da": da, "capex": capex, "capex_pct": paths["capex_pct"][i],
            "nwc": nwc, "change_nwc": d_nwc, "net_reinvestment": net_reinvest,
            "fcff": fcff, "ebitda": ebit + da, "ppe": ppe, "invested_capital": ic,
            "roic": roic,
            "reinvestment_rate": (net_reinvest / nopat) if nopat > 0 else None,
        })
        rev_prev, nwc_prev, ic_prev = revenue, nwc, ic
        if use_ppe:
            ppe_prev = ppe
    return {"rows": rows, "paths": paths, "nol_left": nol, "da_method": "ppe" if use_ppe else "pct_revenue"}


# ---------------------------------------------------------------------------
# Terminal value
# ---------------------------------------------------------------------------

def terminal_value(last: Dict[str, Any], drivers: Dict[str, Any], rate: float) -> Dict[str, Any]:
    """Value at the end of the forecast of every year after it.

    value_driver (default): NOPAT(N+1) = revenue(N) x (1+g) x margin(N) x
      (1 - terminal tax); FCFF(N+1) = NOPAT(N+1) x (1 - g / RONIC);
      TV = FCFF(N+1) / (rate - g).
    fcf_growth: FCFF(N+1) = FCFF(N) x (1+g); TV = FCFF(N+1) / (rate - g). Shown
      with the return on new capital it implicitly assumes."""
    t = drivers["terminal"]
    g = float(t["growth"])
    method = t.get("method") or "value_driver"
    if g >= rate:
        raise ModelError("Terminal growth ({:.2%}) must be below the discount rate ({:.2%}); "
                         "at or above it the perpetuity has no finite value.".format(g, rate))
    tax = float(drivers["tax"]["terminal"])
    nopat_next = last["revenue"] * (1.0 + g) * last["ebit_margin"] * (1.0 - tax)
    out: Dict[str, Any] = {"method": method, "growth": g, "rate": rate, "nopat_next": nopat_next}
    if method == "value_driver":
        ronic = float(t["ronic"])
        if ronic <= 0:
            raise ModelError("The return on new invested capital must be positive.")
        reinvest_rate = g / ronic
        if reinvest_rate > 1.0:
            raise ModelError("Growing {:.1%} a year at a {:.1%} return on new capital needs more "
                             "than all of the profit reinvested.".format(g, ronic))
        fcff_next = nopat_next * (1.0 - reinvest_rate)
        out.update({"ronic": ronic, "reinvestment_rate": reinvest_rate})
    elif method == "fcf_growth":
        fcff_next = last["fcff"] * (1.0 + g)
        reinvest_rate = (1.0 - fcff_next / nopat_next) if nopat_next > 0 else None
        out.update({"reinvestment_rate": reinvest_rate,
                    "implied_ronic": (g / reinvest_rate) if reinvest_rate else None})
    else:
        raise ModelError("Unknown terminal method: {}".format(method))
    out["fcff_next"] = fcff_next
    out["value"] = fcff_next / (rate - g)
    return out


def implied_growth_from_multiple(tv: float, last: Dict[str, Any], drivers: Dict[str, Any],
                                 rate: float) -> Optional[float]:
    """The perpetual growth that would make the growing-perpetuity terminal
    value equal a given terminal value (for example, one from an exit multiple),
    holding RONIC and the terminal margin. Solved by bisection."""
    def f(g: float) -> float:
        d = dict(drivers)
        d["terminal"] = dict(drivers["terminal"], growth=g)
        return terminal_value(last, d, rate)["value"] - tv
    lo, hi = -0.10, rate - 1e-4
    try:
        flo, fhi = f(lo), f(hi)
    except ModelError:
        return None
    if flo * fhi > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2.0
        try:
            fm = f(mid)
        except ModelError:
            hi = mid
            continue
        if flo * fm <= 0:
            hi, fhi = mid, fm
        else:
            lo, flo = mid, fm
        if hi - lo < 1e-9:
            break
    return (lo + hi) / 2.0


# ---------------------------------------------------------------------------
# Enterprise value to equity
# ---------------------------------------------------------------------------

BRIDGE_ADD = ("cash", "short_term_investments", "long_term_investments")
BRIDGE_SUBTRACT = ("debt", "finance_leases", "preferred", "noncontrolling_interests",
                   "pension_deficit")
BRIDGE_LABELS = {
    "cash": "Cash and equivalents",
    "short_term_investments": "Short-term investments",
    "long_term_investments": "Long-term and equity-method investments",
    "debt": "Debt (current and long-term)",
    "finance_leases": "Finance lease liabilities",
    "preferred": "Preferred stock",
    "noncontrolling_interests": "Non-controlling interests",
    "pension_deficit": "Unfunded pension obligations",
}


def bridge(enterprise_value: float, items: Dict[str, Optional[float]],
           include: Optional[Dict[str, bool]] = None) -> Dict[str, Any]:
    """Enterprise value plus non-operating assets less every other claim
    senior to common shareholders. Missing items are listed, never zeroed
    silently: the caller decides whether a missing claim blocks the result."""
    include = include or {}
    lines: List[Dict[str, Any]] = [{"key": "enterprise_value", "label": "Enterprise value",
                                    "value": enterprise_value, "sign": 1}]
    equity = enterprise_value
    missing: List[str] = []
    for key in BRIDGE_ADD + BRIDGE_SUBTRACT:
        sign = 1 if key in BRIDGE_ADD else -1
        on = include.get(key, True)
        value = items.get(key)
        if value is None:
            missing.append(key)
            lines.append({"key": key, "label": BRIDGE_LABELS[key], "value": None,
                          "sign": sign, "included": False})
            continue
        lines.append({"key": key, "label": BRIDGE_LABELS[key], "value": float(value),
                      "sign": sign, "included": bool(on)})
        if on:
            equity += sign * float(value)
    return {"lines": lines, "equity_value": equity, "missing": missing}


# ---------------------------------------------------------------------------
# Enterprise DCF (FCFF at WACC)
# ---------------------------------------------------------------------------

def run_dcf(base: Dict[str, Any], drivers: Dict[str, Any], rate: float) -> Dict[str, Any]:
    """The full enterprise DCF for one assumption set and one discount rate.

    Returns the forecast table, present values, terminal value and its share,
    the bridge, the per-share value and the checks that applied."""
    if not (rate > 0):
        raise ModelError("The discount rate must be positive.")
    shares = base.get("shares")
    if not shares or shares <= 0:
        raise ModelError("A per-share value needs a positive diluted share count.")
    n = int(drivers["horizon"])
    fc = operating_forecast(base, drivers)
    rows = fc["rows"]
    tm = timing(base["fy0_end"], base["balance_date"], base["valuation_date"], n,
                drivers.get("convention") or "mid_year")
    pv_sum = 0.0
    for i, r in enumerate(rows):
        scale = tm["stub_fraction"] if i == 0 else 1.0
        r["fiscal_year_end"] = tm["fiscal_year_ends"][i]
        r["counted_fraction"] = scale
        r["fcff_counted"] = r["fcff"] * scale
        r["discount_time"] = tm["flow_times"][i]
        r["discount_factor"] = discount_factor(rate, tm["flow_times"][i])
        r["pv"] = r["fcff_counted"] * r["discount_factor"]
        pv_sum += r["pv"]

    tv = terminal_value(rows[-1], drivers, rate)
    end_n = tm["end_times"][-1]
    # Under the mid-year convention the perpetuity's flows also arrive
    # mid-year, so its end-of-year-N value is brought back half a year less.
    tv_time = end_n - 0.5 if tm["convention"] == "mid_year" else end_n
    tv["discount_time"] = tv_time
    tv["pv"] = tv["value"] * discount_factor(rate, tv_time)
    ev = pv_sum + tv["pv"]

    last_ebitda = rows[-1]["ebitda"]
    tv["implied_exit_ev_ebitda"] = (tv["value"] / last_ebitda) if last_ebitda > 0 else None

    br = bridge(ev, base.get("bridge") or {}, drivers.get("bridge_include"))
    per_share = br["equity_value"] / shares

    exit_check = None
    multiple = drivers.get("exit_multiple")
    if multiple:
        tv_exit = float(multiple) * last_ebitda
        ev_exit = pv_sum + tv_exit * discount_factor(rate, end_n)
        br_exit = bridge(ev_exit, base.get("bridge") or {}, drivers.get("bridge_include"))
        exit_check = {"multiple": float(multiple), "metric": "EV / EBITDA", "terminal_value": tv_exit,
                      "enterprise_value": ev_exit, "per_share": br_exit["equity_value"] / shares,
                      "implied_growth": implied_growth_from_multiple(tv_exit, rows[-1], drivers, rate),
                      "discount_time": end_n}

    return {
        "rows": rows, "timing": tm, "da_method": fc["da_method"], "nol_left": fc["nol_left"],
        "pv_forecast": pv_sum, "terminal": tv, "enterprise_value": ev,
        "terminal_share": (tv["pv"] / ev) if ev > 0 else None,
        "bridge": br, "equity_value": br["equity_value"], "shares": shares,
        "per_share": per_share, "discount_rate": rate, "exit_check": exit_check,
        "checks": checks(base, drivers, rate, rows, tv, ev),
    }


def checks(base: Dict[str, Any], drivers: Dict[str, Any], rate: float, rows: List[Dict[str, Any]],
           tv: Dict[str, Any], ev: float) -> List[Dict[str, str]]:
    """Plausibility flags. `error` means the number should not be read;
    `warn` means read it with the caveat; `info` explains a treatment."""
    out: List[Dict[str, str]] = []
    g = float(drivers["terminal"]["growth"])
    rf = base.get("risk_free")

    def add(level: str, code: str, text: str) -> None:
        out.append({"level": level, "code": code, "text": text})

    if rate - g < MIN_SPREAD_WACC_G:
        add("warn", "thin_spread", "The discount rate is within one point of terminal growth, so "
            "small changes to either swing the terminal value enormously.")
    if rf is not None and g > rf:
        add("warn", "growth_above_rf", "Terminal growth of {:.1%} is above the risk-free rate of "
            "{:.1%}. Over a perpetuity, a company growing faster than the economy's nominal rate "
            "eventually becomes the economy.".format(g, rf))
    if g > 0.04:
        add("warn", "growth_high", "Terminal growth above 4% a year forever exceeds most estimates "
            "of long-run nominal GDP growth.")
    if g < 0:
        add("info", "growth_negative", "Negative terminal growth: the business shrinks forever. "
            "Coherent for a declining franchise; capital is released as it shrinks.")
    last = rows[-1]
    if last["ebit_margin"] <= 0:
        add("error", "terminal_loss", "The last forecast year still loses money, so the terminal "
            "value is negative or zero. A going-concern value needs a path to profit; the result "
            "here is not meaningful.")
    if tv.get("method") == "value_driver" and tv.get("ronic") is not None and tv["ronic"] < rate:
        add("info", "ronic_below_wacc", "New investment earns less than the cost of capital in the "
            "terminal period, so growth destroys value there.")
    if tv.get("method") == "fcf_growth" and tv.get("implied_ronic") is not None:
        ir = tv["implied_ronic"]
        if ir is not None and (ir < 0 or ir > 0.6):
            add("warn", "implied_ronic", "Growing the last year's cash flow implies a {:.0%} return on "
                "new capital in perpetuity, which is implausible. The value-driver method ties "
                "growth to reinvestment.".format(ir))
        if tv.get("reinvestment_rate") is not None and tv["reinvestment_rate"] < 0 < g:
            add("warn", "growth_without_reinvestment", "Terminal cash flow exceeds NOPAT while "
                "still growing: growth with negative reinvestment.")
    share = (tv.get("pv", 0) / ev) if ev > 0 else None
    if share is not None and share > 0.85:
        add("warn", "terminal_heavy", "{:.0%} of enterprise value comes after the forecast. The "
            "answer depends mostly on the terminal assumptions.".format(share))
    if ev <= 0:
        add("error", "negative_ev", "Enterprise value is zero or negative under these assumptions.")
    for r in rows:
        if r["roic"] is not None and r["roic"] > 1.0:
            add("warn", "roic_extreme", "Forecast return on invested capital exceeds 100% in year "
                "{}; book invested capital may understate the real asset base (brands, R&D).".format(r["year"]))
            break
    if any(r["capex"] < r["da"] * 0.8 for r in rows[-3:]) and g > 0:
        add("warn", "capex_below_da", "Capex runs well below depreciation in the last forecast years "
            "while revenue still grows: the asset base is shrinking under a growing business.")
    return out


# ---------------------------------------------------------------------------
# FCFE at the cost of equity
# ---------------------------------------------------------------------------

def run_fcfe(base: Dict[str, Any], drivers: Dict[str, Any], cost_equity: float,
             pre_tax_cost_debt: float, marginal_tax: float, debt_ratio: float) -> Dict[str, Any]:
    """Free cash flow to equity: FCFF - interest x (1 - t) + net borrowing,
    discounted at the cost of equity.

    Debt policy (Damodaran's target-ratio form): each year's net reinvestment
    (capex - D&A + change in working capital) is financed `debt_ratio` by new
    debt, the same debt weight the discount rate uses, so the two answers rest
    on one capital structure. Losses are not debt-financed, and shrinking
    reinvestment repays debt. Cash and investments are added at the end
    because the interest they earn is not in the forecast. The answer differs
    from FCFF's for legitimate reasons: a single cost of equity rather than a
    blended rate, and book debt rather than market weights."""
    shares = base.get("shares")
    if not shares or shares <= 0:
        raise ModelError("A per-share value needs a positive diluted share count.")
    if not (0.0 <= debt_ratio < 1.0):
        raise ModelError("The debt ratio must be between 0 and 100%.")
    n = int(drivers["horizon"])
    fc = operating_forecast(base, drivers)
    rows = fc["rows"]
    tm = timing(base["fy0_end"], base["balance_date"], base["valuation_date"], n,
                drivers.get("convention") or "mid_year")
    b = base.get("bridge") or {}
    debt_prev = float((b.get("debt") or 0.0) + (b.get("finance_leases") or 0.0))
    debt0 = debt_prev
    out_rows, pv = [], 0.0
    for i, r in enumerate(rows):
        borrowing = debt_ratio * r["net_reinvestment"]
        borrowing = max(borrowing, -debt_prev)            # cannot repay more than is owed
        interest = pre_tax_cost_debt * debt_prev
        fcfe = r["fcff"] - interest * (1.0 - marginal_tax) + borrowing
        scale = tm["stub_fraction"] if i == 0 else 1.0
        df = discount_factor(cost_equity, tm["flow_times"][i])
        pv += fcfe * scale * df
        out_rows.append({"year": r["year"], "fcff": r["fcff"], "interest": interest,
                         "net_borrowing": borrowing, "debt": debt_prev + borrowing, "fcfe": fcfe,
                         "counted_fraction": scale, "discount_factor": df, "pv": fcfe * scale * df})
        debt_prev = debt_prev + borrowing
    t = drivers["terminal"]
    g = float(t["growth"])
    if g >= cost_equity:
        raise ModelError("Terminal growth must be below the cost of equity.")
    tv_f = terminal_value(rows[-1], drivers, cost_equity)
    reinvest_next = tv_f["nopat_next"] - tv_f["fcff_next"]
    fcfe_next = (tv_f["fcff_next"] - pre_tax_cost_debt * debt_prev * (1.0 - marginal_tax)
                 + debt_ratio * reinvest_next)
    tv_value = fcfe_next / (cost_equity - g)
    end_n = tm["end_times"][-1]
    tv_time = end_n - 0.5 if tm["convention"] == "mid_year" else end_n
    tv_pv = tv_value * discount_factor(cost_equity, tv_time)
    adds = sum(float(b.get(k) or 0.0) for k in BRIDGE_ADD)
    subs = sum(float(b.get(k) or 0.0) for k in ("preferred", "noncontrolling_interests", "pension_deficit"))
    equity = pv + tv_pv + adds - subs
    return {"rows": out_rows, "pv_forecast": pv, "terminal_value": tv_value, "terminal_pv": tv_pv,
            "terminal_share": tv_pv / (pv + tv_pv) if (pv + tv_pv) > 0 else None,
            "non_operating_added": adds, "claims_subtracted": subs, "equity_value": equity,
            "per_share": equity / shares, "cost_equity": cost_equity, "debt_ratio": debt_ratio,
            "debt_start": debt0, "debt_end": debt_prev}


# ---------------------------------------------------------------------------
# Dividend discount model (two stage)
# ---------------------------------------------------------------------------

def run_ddm(dps0: float, growth_high: float, years_high: int, growth_terminal: float,
            cost_equity: float) -> Dict[str, Any]:
    """Value = sum of dividends growing at g1 for n years, discounted at the
    cost of equity, plus a growing perpetuity from year n+1 at g2. Dividends
    are taken as received at each year end."""
    if dps0 is None or dps0 <= 0:
        raise ModelError("No dividend to discount.")
    if growth_terminal >= cost_equity:
        raise ModelError("Terminal dividend growth must be below the cost of equity.")
    rows, pv, d = [], 0.0, float(dps0)
    for t in range(1, int(years_high) + 1):
        d *= (1.0 + growth_high)
        df = discount_factor(cost_equity, t)
        rows.append({"year": t, "dividend": d, "discount_factor": df, "pv": d * df})
        pv += d * df
    d_next = d * (1.0 + growth_terminal)
    tv = d_next / (cost_equity - growth_terminal)
    tv_pv = tv * discount_factor(cost_equity, int(years_high))
    return {"rows": rows, "pv_dividends": pv, "terminal_value": tv, "terminal_pv": tv_pv,
            "per_share": pv + tv_pv, "terminal_share": tv_pv / (pv + tv_pv)}


# ---------------------------------------------------------------------------
# Residual income (banks and insurers)
# ---------------------------------------------------------------------------

def run_residual_income(bvps0: float, roe_start: float, roe_terminal: float, cost_equity: float,
                        growth_start: float, growth_terminal: float, years: int = 10) -> Dict[str, Any]:
    """Value = book value + present value of future residual income, where
    residual income = (ROE - cost of equity) x opening book value.

    Book value grows along a path from `growth_start` to the terminal rate,
    and the payout each year is whatever that growth leaves: payout = 1 -
    g / ROE (clean surplus). Tying retention to growth is the same discipline
    as RONIC in the DCF: a high ROE with high retention, compounded for a
    decade, would otherwise assume the business can redeploy all of its
    earnings at that ROE indefinitely. After the forecast, the justified
    price-to-book (ROE - g) / (cost of equity - g) values what is left, which
    equals a growing perpetuity of residual income."""
    if bvps0 is None or bvps0 <= 0:
        raise ModelError("Residual income needs positive book value per share.")
    if growth_terminal >= cost_equity:
        raise ModelError("Terminal growth must be below the cost of equity.")
    roes = linear_path(roe_start, roe_terminal, years)
    growths = linear_path(growth_start, growth_terminal, years)
    bv, pv, rows = float(bvps0), 0.0, []
    for t, (roe, g) in enumerate(zip(roes, growths), start=1):
        eps = roe * bv
        ri = (roe - cost_equity) * bv
        df = discount_factor(cost_equity, t)
        payout = (1.0 - g / roe) if roe > 0 else 0.0
        rows.append({"year": t, "book_value": bv, "roe": roe, "eps": eps, "residual_income": ri,
                     "book_growth": g, "payout": payout, "discount_factor": df, "pv": ri * df})
        pv += ri * df
        bv = bv * (1.0 + g)
    pb_terminal = (roe_terminal - growth_terminal) / (cost_equity - growth_terminal)
    tv = bv * (pb_terminal - 1.0)                       # value above book at year N
    tv_pv = tv * discount_factor(cost_equity, years)
    value = bvps0 + pv + tv_pv
    return {"rows": rows, "book_value_0": bvps0, "pv_residual_income": pv, "terminal_premium": tv,
            "terminal_pv": tv_pv, "terminal_pb": pb_terminal, "per_share": value,
            "justified_pb_now": (roe_start - growth_terminal) / (cost_equity - growth_terminal),
            "implied_pb": value / bvps0}


def justified_pb(roe: float, cost_equity: float, growth: float) -> float:
    """Single-stage justified price-to-book: (ROE - g) / (r - g)."""
    if growth >= cost_equity:
        raise ModelError("Growth must be below the cost of equity.")
    return (roe - growth) / (cost_equity - growth)


# ---------------------------------------------------------------------------
# Comparable companies and sum of the parts
# ---------------------------------------------------------------------------

def percentile(values: Sequence[float], q: float) -> Optional[float]:
    vals = sorted(v for v in values if v is not None and math.isfinite(v))
    if not vals:
        return None
    if len(vals) == 1:
        return vals[0]
    pos = (len(vals) - 1) * q
    lo, hi = int(math.floor(pos)), int(math.ceil(pos))
    return vals[lo] + (vals[hi] - vals[lo]) * (pos - lo)


def comps_value(metric_value: Optional[float], peer_multiples: Sequence[float], is_equity_multiple: bool,
                bridge_items: Dict[str, Optional[float]], shares: float) -> Optional[Dict[str, Any]]:
    """Price per share implied by applying the peers' 25th, median and 75th
    percentile multiple to the company's own metric. An enterprise multiple
    (EV/EBIT, EV/sales) goes through the bridge; an equity multiple (P/E) does
    not. Returns None when the metric is missing or not positive."""
    if metric_value is None or metric_value <= 0 or not shares:
        return None
    clean = [m for m in peer_multiples if m is not None and m > 0 and math.isfinite(m)]
    if len(clean) < 3:
        return None
    out: Dict[str, Any] = {"peers_used": len(clean)}
    for label, q in (("low", 0.25), ("mid", 0.5), ("high", 0.75)):
        mult = percentile(clean, q)
        value = mult * metric_value
        if not is_equity_multiple:
            value = bridge(value, bridge_items)["equity_value"]
        out[label] = {"multiple": mult, "per_share": value / shares}
    return out


def sotp(segments: Sequence[Dict[str, Any]], unallocated: float, unallocated_multiple: float,
         bridge_items: Dict[str, Optional[float]], shares: float) -> Dict[str, Any]:
    """Sum of the parts: each segment's operating income x its own EV/EBIT
    multiple, less the capitalised cost of what the segments do not carry
    (corporate costs, eliminations), then the usual bridge."""
    lines, ev = [], 0.0
    for s in segments:
        oi, mult = s.get("operating_income"), s.get("multiple")
        if oi is None or mult is None:
            lines.append(dict(s, value=None))
            continue
        lines.append(dict(s, value=oi * mult))
        ev += oi * mult
    corp = unallocated * unallocated_multiple
    ev += corp
    br = bridge(ev, bridge_items)
    return {"segments": lines, "unallocated": unallocated, "unallocated_value": corp,
            "enterprise_value": ev, "equity_value": br["equity_value"],
            "per_share": br["equity_value"] / shares if shares else None}


# ---------------------------------------------------------------------------
# Condensed linked three-statement forecast
# ---------------------------------------------------------------------------

def three_statement(base: Dict[str, Any], drivers: Dict[str, Any], policy: Dict[str, Any]) -> Dict[str, Any]:
    """Income statement, balance sheet and cash flow linked year by year.

    A condensed model, not a full one: operating current assets and
    liabilities each keep their share of revenue, PP&E rolls forward, other
    assets, other liabilities and long-term investments are held flat, and
    debt follows the stated policy. Cash is the plug that the cash flow
    statement produces, which is what makes the balance check a real test: if
    any link is wrong, assets stop equalling liabilities plus equity.

    `policy`: interest_rate_debt, interest_rate_cash, payout_ratio (dividends /
    net income), buyback_ratio (buybacks / net income), min_cash (floor, in
    currency), debt_policy ("flat" or "ratio")."""
    bs0 = base.get("balance_sheet")
    if not bs0:
        raise ModelError("The three-statement forecast needs a starting balance sheet.")
    fc = operating_forecast(base, drivers)
    rows = fc["rows"]
    rev0 = float(base["revenue"])
    # Operating current assets keep their share of revenue; liabilities are
    # whatever leaves working capital on the operating forecast's path, so the
    # statements and the DCF use one working-capital figure, not two.
    oca_pct = bs0["operating_current_assets"] / rev0
    cash, debt = float(bs0["cash"]), float(bs0["debt"])
    ppe = float(bs0["ppe"])
    inv, other_a, other_l = float(bs0["investments"]), float(bs0["other_assets"]), float(bs0["other_liabilities"])
    equity = float(bs0["equity"])
    debt_ratio = debt / rev0
    years: List[Dict[str, Any]] = []
    nol = float(base.get("nol") or 0.0)
    for r in rows:
        oca = oca_pct * r["revenue"]
        ocl = oca - r["nwc"]
        int_exp = policy["interest_rate_debt"] * debt
        int_inc = policy["interest_rate_cash"] * max(cash, 0.0)
        pretax = r["ebit"] - int_exp + int_inc
        if pretax < 0:
            nol += -pretax
            taxable = 0.0
        else:
            used = min(nol, pretax)
            nol -= used
            taxable = pretax - used
        taxes = taxable * r["tax_rate"]
        ni = pretax - taxes
        d_nwc = r["change_nwc"]
        cfo = ni + r["da"] - d_nwc
        cfi = -r["capex"]
        target_debt = debt if policy.get("debt_policy", "flat") == "flat" else debt_ratio * r["revenue"]
        dividends = max(0.0, policy["payout_ratio"] * ni)
        buybacks = max(0.0, policy["buyback_ratio"] * ni)
        pre_payout = cash + cfo + cfi + (target_debt - debt)
        # Payouts give way before the cash floor does: buybacks first, then
        # dividends, then the shortfall is borrowed.
        room = pre_payout - policy["min_cash"]
        if room < buybacks + dividends:
            buybacks = max(0.0, min(buybacks, room - dividends))
            if room < dividends:
                dividends = max(0.0, room)
        revolver = max(0.0, policy["min_cash"] - (pre_payout - dividends - buybacks))
        new_debt = target_debt + revolver
        cff = (new_debt - debt) - dividends - buybacks
        cash_new = cash + cfo + cfi + cff
        ppe_new = ppe + r["capex"] - r["da"]
        equity_new = equity + ni - dividends - buybacks
        assets = cash_new + oca + ppe_new + inv + other_a
        liabs = ocl + new_debt + other_l
        years.append({
            "year": r["year"], "revenue": r["revenue"], "ebit": r["ebit"], "interest_expense": int_exp,
            "interest_income": int_inc, "pretax_income": pretax, "taxes": taxes, "net_income": ni,
            "da": r["da"], "change_nwc": d_nwc, "cfo": cfo, "capex": r["capex"], "cfi": cfi,
            "dividends": dividends, "buybacks": buybacks, "net_borrowing": new_debt - debt,
            "revolver_draw": revolver, "cff": cff, "change_cash": cash_new - cash,
            "cash": cash_new, "operating_current_assets": oca, "ppe": ppe_new, "investments": inv,
            "other_assets": other_a, "total_assets": assets, "operating_current_liabilities": ocl,
            "debt": new_debt, "other_liabilities": other_l, "total_liabilities": liabs,
            "equity": equity_new, "balance_check": assets - liabs - equity_new,
            "fcff_from_statements": cfo + (int_exp - int_inc) * (1 - r["tax_rate"]) + cfi,
            "fcff_dcf": r["fcff"],
        })
        cash, debt, ppe, equity = cash_new, new_debt, ppe_new, equity_new
    worst = max(abs(y["balance_check"]) for y in years)
    return {"years": years, "max_imbalance": worst, "balances": worst < max(1.0, 1e-9 * rev0),
            "label": "Condensed linked three-statement forecast"}


# ---------------------------------------------------------------------------
# Root finding (reverse DCF)
# ---------------------------------------------------------------------------

def solve(f: Callable[[float], Optional[float]], target: float, lo: float, hi: float,
          tol: float = 1e-7, max_iter: int = 200) -> Optional[float]:
    """Bisection for x in [lo, hi] with f(x) = target, f monotone. None when
    the target is outside what the bracket can reach, or f fails at a bound."""
    def g(x: float) -> Optional[float]:
        try:
            v = f(x)
        except ModelError:
            return None
        return None if v is None else v - target
    glo, ghi = g(lo), g(hi)
    if glo is None or ghi is None or glo * ghi > 0:
        return None
    for _ in range(max_iter):
        mid = (lo + hi) / 2.0
        gm = g(mid)
        if gm is None:
            return None
        if abs(gm) < tol * max(1.0, abs(target)):
            return mid
        if glo * gm <= 0:
            hi, ghi = mid, gm
        else:
            lo, glo = mid, gm
    return (lo + hi) / 2.0
