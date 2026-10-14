"""Long-term analysis: business quality, then valuation, then the chart, then a
conviction that keeps the three apart.

Inputs are the valuation workspace's sourced SEC filings (`app/valuation`), so
every figure here can be traced to the filing it came from, and the long-term
panel's own price history (`app/analytics/longterm.py`). Nothing is fetched in
this module: `service.py` gathers and this module grades, so each rule can be
tested on synthetic statements.

Every component is graded 0 to 4 against a written rubric (RUBRICS below) and
reports one of three states: scored, insufficient (the data was not there),
or not_applicable (the measure does not describe this kind of business, such as
free cash flow for a bank). Insufficient is never scored as bad: a missing
figure is a gap in the evidence, not evidence against the company.
"""

from __future__ import annotations

from statistics import mean, median, pstdev
from typing import Any, Dict, List, Optional, Tuple

from . import policy as policy_mod

LETTERS = [(3.5, "A"), (2.75, "B"), (2.0, "C"), (1.25, "D"), (-1.0, "F")]

# Weights of the quality components, out of 100. Returns on capital and cash
# carry the most because they are the two a reported profit can flatter least.
QUALITY_WEIGHTS = {
    "returns": 22, "cash": 18, "health": 14, "margins": 13, "growth": 13, "durability": 12, "dilution": 8,
}

RUBRICS: Dict[str, str] = {
    "returns": ("Average return on invested capital over the last three fiscal years minus the cost of "
                "capital (WACC): 4 at +10 points or more, 3 at +4, 2 at 0, 1 at -4, else 0. Banks and "
                "insurers use return on equity against the cost of equity."),
    "margins": ("Latest operating margin: 4 at 25% or more, 3 at 15%, 2 at 8%, 1 at 0%, else 0; one "
                "point off when the margin has ranged more than 8 points across the years read."),
    "growth": ("Revenue growth a year, compounded over the years read: 4 at 15% or more, 3 at 8%, 2 at "
               "3%, 1 at 0%, else 0."),
    "cash": ("Over the policy's cash-conversion window: operating cash flow against net income, and free "
             "cash flow (operating cash flow minus capex) against revenue. 4 when conversion is at least "
             "1.0 and the free-cash-flow margin at least 15%; 3 at 0.9 and 8%; 2 at 0.7 with positive free "
             "cash flow; 1 with positive free cash flow; else 0."),
    "health": ("Net debt against EBITDA and operating income against interest. 4 with net cash, or net "
               "debt at most 1x EBITDA with interest covered 8x; 3 at 2x and 5x; 2 within the policy "
               "limits (leverage_max_net_debt_ebitda, coverage_min_ebit_interest); 1 outside them; 0 when "
               "interest is covered less than 1.5x or EBITDA is negative with net debt."),
    "dilution": ("Diluted share count change a year and stock-based pay as a share of revenue: 4 when "
                 "shares fall and stock pay is under 3%; 3 when shares rise no more than 1% a year and "
                 "stock pay is under 5%; 2 at up to 3% a year with stock pay under 10%; 1 at up to 6% a "
                 "year; else 0."),
    "durability": ("Moat evidence, four measurable tests, one point each: returns above the cost of "
                   "capital in at least 80% of the years read; operating margin range within 6 points; "
                   "gross margin of 40% or more (operating margin of 20% where gross profit is not "
                   "reported); revenue up in at least 75% of years without the operating margin falling "
                   "more than 3 points. Needs three tests with data. These are the traces a durable "
                   "advantage leaves in the accounts; they do not say what the advantage is."),
}

VALUATION_RUBRICS: Dict[str, str] = {
    "intrinsic": ("Base-case value per share from the model that fits this business (the DCF, or residual "
                  "income for a bank) against the price: 4 at 30% upside or more, 3 at +10%, 2 within 10%, "
                  "1 down to -30%, else 0. Scored only when the model is the primary fit at normal confidence."),
    "own_history": ("Today's P/E against the company's own five-year range: 4 in the bottom fifth, 3 "
                    "below the 40th percentile, 2 below the 60th, 1 below the 80th, else 0."),
    "cash_yield": ("Free cash flow to equity over market value (an equity measure over an equity value), "
                   "against the 10-year Treasury yield: 4 at 2 points above or more, 3 at or above it, 2 "
                   "down to 1.5 below, 1 down to 3 below, else 0. Free cash flow to the firm over "
                   "enterprise value is reported beside it."),
    "implied_growth": ("Growth the price implies (reverse DCF) against the company's own revenue record: "
                       "4 when it implies 5 points a year less or more than 5 below, 3 at or below the "
                       "record, 2 up to 5 above, 1 up to 10 above, else 0."),
    "peers": ("Trailing P/E (EV/EBITDA when earnings are negative) against the median of the peer group: "
              "4 at 0.75x or less, 3 at 0.95x, 2 at 1.1x, 1 at 1.4x, else 0."),
}

VALUATION_LABELS = [(3.0, "Attractive"), (2.25, "Fair"), (1.5, "Full"), (-1.0, "Stretched")]

CONVICTION_ORDER = ["High Conviction", "Constructive", "Neutral", "Weak Structure", "Not Investable"]


# ---------------------------------------------------------------- helpers

def _v(f: Any) -> Optional[float]:
    if isinstance(f, dict):
        f = f.get("value")
    try:
        x = float(f)
    except (TypeError, ValueError):
        return None
    return x if x == x else None


def _pct(x: Optional[float], d: int = 1) -> str:
    return "n/a" if x is None else "{:.{d}f}%".format(x * 100.0, d=d)


def _pts(x: Optional[float], d: int = 1) -> str:
    return "n/a" if x is None else "{:+.{d}f} points".format(x * 100.0, d=d)


def _fy(y: Dict[str, Any]) -> str:
    return "FY" + str(y.get("fy_end") or "")[:4]


def letter(score: Optional[float]) -> Optional[str]:
    if score is None:
        return None
    for floor, name in LETTERS:
        if score >= floor:
            return name
    return "F"


def _band(x: float, steps: List[Tuple[float, int]], default: int = 0) -> int:
    for floor, score in steps:
        if x >= floor:
            return score
    return default


def _source(y: Dict[str, Any], concept: str, label: Optional[str] = None) -> Optional[Dict[str, Any]]:
    f = (y.get("flows") or {}).get(concept) or (y.get("balance") or {}).get(concept)
    if not isinstance(f, dict) or f.get("value") is None:
        return None
    return {"label": label or concept.replace("_", " "), "period": f.get("end") or y.get("fy_end"),
            "form": f.get("form"), "filed": f.get("filed"), "url": f.get("url"), "tag": f.get("tag")}


def _component(cid: str, label: str, status: str, score: Optional[float] = None, headline: str = "",
               evidence: Optional[List[str]] = None, figures: Optional[Dict[str, Any]] = None,
               sources: Optional[List[Optional[Dict[str, Any]]]] = None, reason: str = "") -> Dict[str, Any]:
    return {"id": cid, "label": label, "status": status,
            "score": None if score is None else round(float(score), 2),
            "grade": letter(score) if status == "scored" else None,
            "headline": headline, "evidence": evidence or [], "figures": figures or {},
            "sources": [s for s in (sources or []) if s], "reason": reason,
            "rubric": RUBRICS.get(cid) or VALUATION_RUBRICS.get(cid, "")}


def _flow(y: Dict[str, Any], c: str) -> Optional[float]:
    return _v((y.get("flows") or {}).get(c))


def _bal(y: Dict[str, Any], c: str) -> Optional[float]:
    return _v((y.get("balance") or {}).get(c))


def _der(y: Dict[str, Any], c: str) -> Optional[float]:
    return _v((y.get("derived") or {}).get(c))


# ------------------------------------------------------------- components

def returns_component(hist: List[Dict[str, Any]], kind: str, wacc: Optional[float],
                      cost_equity: Optional[float]) -> Dict[str, Any]:
    label = "Returns on capital"
    if kind == "reit":
        return _component("returns", label, "not_applicable",
                          reason="Property depreciation understates a REIT's returns on its buildings, so "
                                 "return on invested capital does not describe it; funds from operations "
                                 "per share is the industry's measure and is not read here.")
    if kind in ("bank", "insurer"):
        roes = [(y, _der(y, "roe")) for y in hist[:5]]
        roes = [(y, r) for y, r in roes if r is not None]
        if len(roes) < 2 or cost_equity is None:
            return _component("returns", label, "insufficient",
                              reason="Needs two years of return on equity and a cost of equity.")
        avg = mean(r for _, r in roes[:3])
        spread = avg - cost_equity
        score = _band(spread, [(0.10, 4), (0.04, 3), (0.0, 2), (-0.04, 1)])
        above = sum(1 for _, r in roes if r > cost_equity)
        return _component(
            "returns", label, "scored", score,
            "Return on equity averaged {} over the last {} years against a {} cost of equity ({}).".format(
                _pct(avg), min(3, len(roes)), _pct(cost_equity), _pts(spread)),
            ["{} return on equity {}".format(_fy(y), _pct(r)) for y, r in roes],
            {"roe_avg_3y": avg, "cost_equity": cost_equity, "spread": spread,
             "years_above": above, "years": len(roes), "method": "net income to common / average equity"},
            [_source(roes[0][0], "net_income_common", "net income"), _source(roes[0][0], "equity")])

    # Operating companies. Return on invested capital as the valuation inputs
    # compute it: after-tax operating income over the prior year's equity plus
    # debt less cash and investments. When that base is near zero or negative
    # (heavy buybacks, or a cash pile larger than the debt and equity), the
    # ratio is arithmetic without meaning, so every year switches to the same
    # second measure rather than mixing two definitions in one average.
    rows: List[Tuple[Dict[str, Any], Optional[float]]] = []
    method = "after-tax operating income / prior-year invested capital (equity + debt - cash and investments)"
    for i, y in enumerate(hist[:5]):
        r, ic = _der(y, "roic"), _der(y, "invested_capital")
        rows.append((y, r if (r is not None and ic is not None and ic > 0 and -1.0 <= r <= 1.0) else None))
    meaningful = [r for _, r in rows if r is not None]
    switched = False
    if len(meaningful) < max(2, len(rows) - 1):
        switched = True
        method = ("after-tax operating income / prior-year total capital (equity + debt), cash included; "
                  "used because invested capital net of cash is near zero or negative for this company")
        rows = []
        for i, y in enumerate(hist[:5]):
            prior = hist[i + 1] if i + 1 < len(hist) else None
            ebit, t = _flow(y, "operating_income"), _der(y, "effective_tax_rate")
            if prior is None or ebit is None:
                continue
            cap = (_bal(prior, "equity") or 0.0) + (_bal(prior, "debt") or 0.0)
            if cap <= 0:
                continue
            tax = min(max(t if t is not None else 0.21, 0.0), 0.5)
            rows.append((y, ebit * (1 - tax) / cap))
        meaningful = [r for _, r in rows if r is not None]
    if len(meaningful) < 2 or wacc is None:
        return _component("returns", label, "insufficient",
                          reason="Needs two years of return on capital and a cost of capital (WACC). " +
                                 ("No WACC could be built (a beta or risk-free rate is missing)." if wacc is None
                                  else "Fewer than two years computed."))
    avg = mean(meaningful[:3])
    spread = avg - wacc
    score = _band(spread, [(0.10, 4), (0.04, 3), (0.0, 2), (-0.04, 1)])
    years = [(y, r) for y, r in rows if r is not None]
    above = sum(1 for _, r in years if r > wacc)
    return _component(
        "returns", label, "scored", score,
        "Return on capital averaged {} over the last {} years against a {} cost of capital ({}).".format(
            _pct(avg), min(3, len(meaningful)), _pct(wacc), _pts(spread)),
        ["{} return on capital {}".format(_fy(y), _pct(r)) for y, r in years]
        + (["Measured on total capital: invested capital net of cash is near zero or negative here, "
            "so the usual ratio would be meaningless."] if switched else []),
        {"roic_avg_3y": avg, "wacc": wacc, "spread": spread, "years_above": above, "years": len(years),
         "method": method, "total_capital_basis": switched},
        [_source(hist[0], "operating_income", "operating income"), _source(hist[0], "equity"),
         _source(hist[0], "debt")])


def _comparable_years(hist: List[Dict[str, Any]], n: int = 5) -> List[Dict[str, Any]]:
    """Years whose revenue is at least a tenth of the latest. A launch year
    with almost no revenue has a margin that describes nothing: Rivian's
    fiscal 2021 margin of about -7,600% made its "range" 7,606 points."""
    years = hist[:n]
    latest = _flow(years[0], "revenue") if years else None
    if not latest or latest <= 0:
        return years
    return [y for y in years if (_flow(y, "revenue") or 0) >= 0.1 * latest]


def margins_component(hist: List[Dict[str, Any]], kind: str) -> Dict[str, Any]:
    label = "Profitability and margins"
    if kind in ("bank", "insurer", "reit"):
        return _component("margins", label, "not_applicable",
                          reason="An operating margin on reported revenue does not describe a {}: interest "
                                 "spread, underwriting and property income are measured differently.".format(
                                     {"bank": "bank", "insurer": "insurer", "reit": "REIT"}[kind]))
    rows = [(y, _der(y, "ebit_margin")) for y in _comparable_years(hist)]
    rows = [(y, m) for y, m in rows if m is not None]
    if not rows:
        return _component("margins", label, "insufficient", reason="No operating margin in the filings read.")
    latest = rows[0][1]
    score = _band(latest, [(0.25, 4), (0.15, 3), (0.08, 2), (0.0, 1)])
    spread = (max(m for _, m in rows) - min(m for _, m in rows)) if len(rows) > 1 else 0.0
    evidence = ["{} operating margin {}".format(_fy(y), _pct(m)) for y, m in rows]
    if len(rows) > 1 and spread > 0.08:
        score = max(score - 1, 0)
        evidence.append("Operating margin ranged {:.1f} points across these years, so one point is taken "
                        "off: a margin that swings this much is a poor guide to the next one.".format(spread * 100))
    figures: Dict[str, Any] = {"ebit_margin_latest": latest, "ebit_margin_range": spread,
                               "years": len(rows)}
    drivers = margin_drivers(hist)
    if drivers:
        evidence.append(drivers["text"])
        figures["drivers"] = drivers
    return _component("margins", label, "scored", score,
                      "Operating margin was {} in {}, with a {:.1f}-point range over {} years.".format(
                          _pct(latest), _fy(rows[0][0]), spread * 100, len(rows)),
                      evidence, figures, [_source(rows[0][0], "operating_income", "operating income"),
                                          _source(rows[0][0], "revenue")])


def _gross_margin(y: Dict[str, Any]) -> Optional[float]:
    rev = _flow(y, "revenue")
    if not rev:
        return None
    gp = _flow(y, "gross_profit")
    if gp is None:
        cor = _flow(y, "cost_of_revenue")
        gp = (rev - cor) if cor is not None else None
    return None if gp is None else gp / rev


def margin_drivers(hist: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Why the operating margin moved: gross margin (price and mix) against
    the operating cost ratio (spending), first year read to the latest.

    Stock-based pay is reported beside it because it sits inside operating
    costs and can move the margin without any change in the business."""
    years = [y for y in hist[:5] if _der(y, "ebit_margin") is not None]
    if len(years) < 2:
        return None
    new, old = years[0], years[-1]
    m_new, m_old = _der(new, "ebit_margin"), _der(old, "ebit_margin")
    g_new, g_old = _gross_margin(new), _gross_margin(old)
    out: Dict[str, Any] = {"from": _fy(old), "to": _fy(new), "ebit_margin_change": m_new - m_old}
    parts = ["Operating margin {} from {} to {}".format(
        "rose" if m_new > m_old else "fell" if m_new < m_old else "held", _fy(old), _fy(new))]
    if g_new is not None and g_old is not None:
        gm_chg = g_new - g_old
        cost_chg = (g_new - m_new) - (g_old - m_old)
        out.update({"gross_margin_change": gm_chg, "cost_ratio_change": cost_chg})
        parts.append("gross margin {} {:.1f} points and operating costs {} {:.1f} points of revenue".format(
            "added" if gm_chg >= 0 else "took off", abs(gm_chg) * 100,
            "fell by" if cost_chg <= 0 else "rose by", abs(cost_chg) * 100))
    else:
        parts.append("gross profit is not reported in the filings read, so the change cannot be split "
                     "between pricing and spending")
    s_new, s_old = _der(new, "sbc_pct"), _der(old, "sbc_pct")
    if s_new is not None and s_old is not None and abs(s_new - s_old) >= 0.005:
        out["sbc_pct_change"] = s_new - s_old
        parts.append("stock-based pay went from {} to {} of revenue".format(_pct(s_old), _pct(s_new)))
    out["text"] = "; ".join(parts) + "."
    return out


def growth_component(hist: List[Dict[str, Any]], kind: str) -> Dict[str, Any]:
    label = "Revenue growth"
    revs = [(y, _flow(y, "revenue")) for y in hist[:5]]
    revs = [(y, r) for y, r in revs if r]
    if len(revs) < 3:
        return _component("growth", label, "insufficient", reason="Needs three fiscal years of revenue.")
    n = len(revs) - 1
    first, last = revs[-1][1], revs[0][1]
    if first <= 0:
        return _component("growth", label, "insufficient", reason="The earliest revenue read is not positive.")
    cagr = (last / first) ** (1.0 / n) - 1.0
    ups = sum(1 for i in range(len(revs) - 1) if revs[i][1] > revs[i + 1][1])
    score = _band(cagr, [(0.15, 4), (0.08, 3), (0.03, 2), (0.0, 1)])
    return _component(
        "growth", label, "scored", score,
        "Revenue compounded {} a year from {} to {}, up in {} of {} years.".format(
            _pct(cagr), _fy(revs[-1][0]), _fy(revs[0][0]), ups, n),
        ["{} revenue {:,.0f}".format(_fy(y), r) for y, r in revs],
        {"revenue_cagr": cagr, "years": n, "years_up": ups,
         "latest_growth": _der(revs[0][0], "revenue_growth")},
        [_source(revs[0][0], "revenue"), _source(revs[-1][0], "revenue")])


def cash_component(hist: List[Dict[str, Any]], kind: str, window: int) -> Dict[str, Any]:
    label = "Cash generation and earnings quality"
    if kind in ("bank", "insurer"):
        return _component("cash", label, "not_applicable",
                          reason="A lender's or insurer's operating cash flow moves with loans, deposits and "
                                 "reserves, so it says little about earnings quality.")
    years = [y for y in hist[:window] if _flow(y, "cfo") is not None and _flow(y, "net_income") is not None]
    if len(years) < 2:
        return _component("cash", label, "insufficient",
                          reason="Needs at least two years with both operating cash flow and net income.")
    cfo = sum(_flow(y, "cfo") for y in years)
    ni = sum(_flow(y, "net_income") for y in years)
    capex = sum(_flow(y, "capex") or 0.0 for y in years)
    rev = sum(_flow(y, "revenue") or 0.0 for y in years)
    sbc = sum(_flow(y, "sbc") or 0.0 for y in years)
    fcf = cfo - capex
    fcf_m = fcf / rev if rev else None
    conv = cfo / ni if ni > 0 else None
    evidence: List[str] = []
    # Year-by-year, before any conclusion: a gap between profit and cash can
    # be working capital building in a growing business, a timing effect, or
    # genuinely weak earnings, and one year cannot tell them apart.
    gaps = []
    for y in years:
        c, n = _flow(y, "cfo"), _flow(y, "net_income")
        if n and n > 0 and c / n < 0.8:
            d_nwc = _der(y, "change_nwc")
            why = (" Working capital absorbed {:,.0f} that year, which accounts for {}.".format(
                d_nwc, "most of it" if d_nwc and d_nwc >= 0.5 * (n - c) else "part of it")
                   if d_nwc and d_nwc > 0 else " Working capital does not explain it.")
            gaps.append(y)
            evidence.append("{}: operating cash flow was {:.0%} of net income.{}".format(_fy(y), c / n, why))
    if gaps and len(gaps) == 1:
        evidence.append("One year of cash below profit is a question to follow up, not a finding of low "
                        "earnings quality.")
    elif len(gaps) >= 2:
        evidence.append("Cash fell short of profit in {} of {} years, a pattern worth understanding before "
                        "trusting reported earnings.".format(len(gaps), len(years)))
    if ni <= 0:
        score = 1 if fcf > 0 else 0
        head = ("Cumulative net income over {} years was not positive; free cash flow was {:,.0f}.".format(
            len(years), fcf))
    else:
        if conv >= 1.0 and fcf_m is not None and fcf_m >= 0.15:
            score = 4
        elif conv >= 0.9 and fcf_m is not None and fcf_m >= 0.08:
            score = 3
        elif conv >= 0.7 and fcf > 0:
            score = 2
        elif fcf > 0:
            score = 1
        else:
            score = 0
        head = ("Over {} years operating cash flow was {:.2f}x net income and free cash flow {} of "
                "revenue.".format(len(years), conv, _pct(fcf_m)))
    if rev and sbc:
        evidence.append("After stock-based pay ({} of revenue), free cash flow was {} of revenue: stock pay "
                        "is a real cost that cash flow adds back.".format(_pct(sbc / rev), _pct((fcf - sbc) / rev)))
    return _component("cash", label, "scored", score, head, evidence,
                      {"cfo_to_net_income": conv, "fcf_margin": fcf_m, "fcf": fcf,
                       "fcf_after_sbc_margin": ((fcf - sbc) / rev) if rev else None,
                       "years": len(years), "years_cash_below_profit": len(gaps)},
                      [_source(years[0], "cfo", "operating cash flow"), _source(years[0], "capex"),
                       _source(years[0], "net_income", "net income")])


def health_component(hist: List[Dict[str, Any]], balance: Dict[str, Any], kind: str,
                     values: Dict[str, Any]) -> Dict[str, Any]:
    label = "Balance sheet and liquidity"
    if kind in ("bank", "insurer", "reit"):
        return _component("health", label, "not_applicable",
                          reason="Debt is part of how a {} operates, so operating-company leverage limits do "
                                 "not apply; capital ratios {}are not read here.".format(
                                     {"bank": "bank", "insurer": "insurer", "reit": "REIT"}[kind],
                                     "and occupancy " if kind == "reit" else ""))
    y = hist[0]
    ebit, da, interest = _flow(y, "operating_income"), _flow(y, "da"), _flow(y, "interest_expense")
    debt = (_v(balance.get("debt")) or 0.0) + (_v(balance.get("finance_leases")) or 0.0)
    cash = (_v(balance.get("cash")) or 0.0) + (_v(balance.get("short_term_investments")) or 0.0)
    if ebit is None or _v(balance.get("cash")) is None:
        return _component("health", label, "insufficient",
                          reason="Needs operating income and a cash balance from the filings.")
    ebitda = ebit + (da or 0.0)
    net_debt = debt - cash
    lev = (net_debt / ebitda) if ebitda > 0 else None
    cov = (ebit / interest) if interest and interest > 0 else None
    ca, cl = _v(balance.get("assets_current")), _v(balance.get("liabilities_current"))
    current_ratio = (ca / cl) if (ca and cl) else None
    due = _v(balance.get("debt_current"))
    max_lev, min_cov = values["leverage_max_net_debt_ebitda"], values["coverage_min_ebit_interest"]
    if ebit <= 0:
        # Leverage and coverage ratios are undefined with operating losses, so
        # the question becomes runway: how long the cash lasts at last year's
        # burn. The first version scored Rivian 0 under a headline reading
        # "Net cash of 767,000,000", which contradicted itself.
        cfo, capex = _flow(y, "cfo"), _flow(y, "capex")
        burn = -((cfo or 0.0) - (capex or 0.0)) if cfo is not None else None
        runway = (cash / burn) if (burn and burn > 0) else None
        score = 2 if (runway is None or runway >= 3) and net_debt <= 0 else 1 if (runway or 0) >= 1.5 else 0
        ev = ["Operating at a loss ({:,.0f} operating income), so leverage and interest-coverage ratios are "
              "undefined.".format(ebit),
              "Cash and short-term investments {:,.0f}; debt {:,.0f}.".format(cash, debt)]
        if runway is not None:
            ev.append("Free cash flow was {:,.0f} last year: at that burn the cash lasts about {:.1f} years, "
                      "before any new financing.".format(-burn, runway))
        else:
            ev.append("Free cash flow was not negative last year, so there is no burn to measure runway against.")
        return _component("health", label, "scored", score,
                          "Loss-making: cash covers about {} of last year's cash burn.".format(
                              "{:.1f} years".format(runway) if runway is not None else "an unmeasured span"),
                          ev, {"net_debt": net_debt, "cash": cash, "debt": debt, "runway_years": runway,
                               "annual_burn": burn},
                          [_source({"balance": balance}, "cash"), _source(y, "cfo", "operating cash flow")])
    if net_debt > 0 and ebitda <= 0:
        score = 0
    elif cov is not None and cov < 1.5:
        score = 0
    elif net_debt <= 0:
        score = 4
    elif lev is not None and lev <= 1.0 and (cov is None or cov >= 8):
        score = 4
    elif lev is not None and lev <= 2.0 and (cov is None or cov >= 5):
        score = 3
    elif lev is not None and lev <= max_lev and (cov is None or cov >= min_cov):
        score = 2
    else:
        score = 1
    ev = ["Net debt {:,.0f} ({}) against EBITDA {:,.0f}{}.".format(
        net_debt, "net cash" if net_debt <= 0 else "{:.1f}x".format(lev) if lev is not None else "EBITDA not positive",
        ebitda, "" if da is not None else " (no depreciation tagged, so EBITDA is operating income)")]
    if cov is not None:
        ev.append("Operating income covers interest {:.1f}x.".format(cov))
    else:
        ev.append("No interest expense tagged, so coverage is not computed.")
    if current_ratio is not None:
        ev.append("Current ratio {:.2f} (current assets over current liabilities).".format(current_ratio))
    if due:
        ev.append("Debt due within a year: {:,.0f}, against cash and short-term investments of {:,.0f}.".format(
            due, cash))
    ev.append("Maturities beyond the next year are not read from the filings; the debt footnote has the ladder.")
    return _component(
        "health", label, "scored", score,
        ("Net cash of {:,.0f}.".format(-net_debt) if net_debt <= 0 else
         "Net debt is {} EBITDA{}.".format("{:.1f}x".format(lev) if lev is not None else "not covered by",
                                           ", interest covered {:.1f}x".format(cov) if cov else "")),
        ev, {"net_debt": net_debt, "ebitda": ebitda, "net_debt_to_ebitda": lev, "interest_coverage": cov,
             "current_ratio": current_ratio, "debt_due_1y": due, "limits": {"max_net_debt_ebitda": max_lev,
                                                                           "min_coverage": min_cov}},
        [_source({"balance": balance}, "debt"), _source({"balance": balance}, "cash"),
         _source(y, "interest_expense", "interest expense")])


def split_factor(filed: Optional[str], splits: Optional[List[Dict[str, Any]]]) -> float:
    """How many of today's shares one share in a filing is worth: the product
    of every split dated after the filing. A filed share count is as reported,
    and the latest filing of a period is not always after a split: NVIDIA's
    fiscal 2022 count comes from a 10-K filed in February 2024, before that
    June's 10-for-1, so it read 2.5bn against 24.9bn a year later, and the
    first version reported "shares rose 76% a year"."""
    f = 1.0
    for sp in splits or []:
        try:
            if filed and str(sp.get("date"))[:10] > str(filed)[:10] and float(sp.get("ratio") or 0) > 0:
                f *= float(sp["ratio"])
        except (TypeError, ValueError):
            continue
    return f


def dilution_component(hist: List[Dict[str, Any]], kind: str,
                       splits: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    label = "Dilution and stock-based pay"
    shares = []
    adjusted = False
    # Comparable years only: an IPO year's weighted share count averages in
    # the months before the listing, so Rivian's fiscal 2021 made four years
    # of ordinary issuance read as 55% a year.
    for y in _comparable_years(hist):
        f = (y.get("flows") or {}).get("diluted_shares_avg")
        v = _v(f)
        if not v:
            continue
        k = split_factor(f.get("filed") if isinstance(f, dict) else None, splits)
        adjusted = adjusted or k != 1.0
        shares.append((y, v * k))
    if len(shares) < 2:
        return _component("dilution", label, "insufficient", reason="Needs two years of diluted share counts.")
    n = len(shares) - 1
    chg = (shares[0][1] / shares[-1][1]) ** (1.0 / n) - 1.0
    sbc = _der(hist[0], "sbc_pct")
    s = sbc if sbc is not None else 0.0
    if chg < -0.001 and s < 0.03:
        score = 4
    elif chg <= 0.01 and s < 0.05:
        score = 3
    elif chg <= 0.03 and s < 0.10:
        score = 2
    elif chg <= 0.06:
        score = 1
    else:
        score = 0
    if kind == "reit" and chg > 0:
        note = ["REITs fund growth by issuing shares, so dilution is part of the model; what matters is "
                "whether funds from operations per share grow, which is not read here."]
    else:
        note = []
    return _component(
        "dilution", label, "scored", score,
        "Diluted shares {} {} a year over {} years; stock-based pay was {} of revenue in {}.".format(
            "fell" if chg < 0 else "rose", _pct(abs(chg)), n, _pct(sbc) if sbc is not None else "not tagged",
            _fy(hist[0])),
        ["{} diluted shares {:,.0f}".format(_fy(y), v) for y, v in shares] + note
        + (["Share counts are restated for stock splits dated after each filing, so years compare like for "
            "like."] if adjusted else []),
        {"share_change_a_year": chg, "sbc_pct": sbc, "years": n, "split_adjusted": adjusted},
        [_source(shares[0][0], "diluted_shares_avg", "diluted shares"), _source(hist[0], "sbc", "stock-based pay")])


def durability_component(hist: List[Dict[str, Any]], kind: str, returns: Dict[str, Any],
                         hurdle: Optional[float]) -> Dict[str, Any]:
    label = "Durability (moat evidence)"
    tests: List[Dict[str, Any]] = []
    # 1. Returns above the cost of capital, persistently.
    rf = returns.get("figures") or {}
    if returns.get("status") == "scored" and rf.get("years"):
        share = rf["years_above"] / rf["years"]
        tests.append({"test": "Returns above the cost of capital in at least 80% of years",
                      "passed": share >= 0.8, "detail": "{} of {} years".format(rf["years_above"], rf["years"])})
    else:
        tests.append({"test": "Returns above the cost of capital in at least 80% of years", "passed": None,
                      "detail": "Not measured"})
    margins = [_der(y, "ebit_margin") for y in _comparable_years(hist)]
    margins = [m for m in margins if m is not None]
    if kind not in ("bank", "insurer", "reit") and len(margins) >= 3:
        rng = max(margins) - min(margins)
        tests.append({"test": "Operating margin range within 6 points", "passed": rng <= 0.06,
                      "detail": "{:.1f}-point range over {} years".format(rng * 100, len(margins))})
    elif kind in ("bank", "insurer") and returns.get("status") == "scored":
        roes = [_der(y, "roe") for y in hist[:5] if _der(y, "roe") is not None]
        if len(roes) >= 3:
            rng = max(roes) - min(roes)
            tests.append({"test": "Return on equity range within 6 points", "passed": rng <= 0.06,
                          "detail": "{:.1f}-point range over {} years".format(rng * 100, len(roes))})
        else:
            tests.append({"test": "Return on equity range within 6 points", "passed": None, "detail": "Not measured"})
    else:
        tests.append({"test": "Operating margin range within 6 points", "passed": None, "detail": "Not measured"})
    gm = _gross_margin(hist[0]) if hist else None
    if kind in ("bank", "insurer", "reit"):
        tests.append({"test": "Pricing power (gross margin of 40% or more)", "passed": None,
                      "detail": "Not meaningful for this kind of business"})
    elif gm is not None:
        tests.append({"test": "Pricing power (gross margin of 40% or more)", "passed": gm >= 0.40,
                      "detail": "gross margin {}".format(_pct(gm))})
    elif margins:
        tests.append({"test": "Pricing power (operating margin of 20% or more; no gross profit tagged)",
                      "passed": margins[0] >= 0.20, "detail": "operating margin {}".format(_pct(margins[0]))})
    else:
        tests.append({"test": "Pricing power", "passed": None, "detail": "Not measured"})
    revs = [_flow(y, "revenue") for y in hist[:5]]
    revs = [r for r in revs if r]
    if len(revs) >= 3:
        ups = sum(1 for i in range(len(revs) - 1) if revs[i] > revs[i + 1])
        share = ups / (len(revs) - 1)
        m_ok = True
        if len(margins) >= 2 and kind not in ("bank", "insurer", "reit"):
            m_ok = (margins[0] - margins[-1]) >= -0.03
        tests.append({"test": "Revenue up in at least 75% of years without the margin falling more than 3 points",
                      "passed": share >= 0.75 and m_ok,
                      "detail": "up in {} of {} years{}".format(ups, len(revs) - 1, "" if m_ok else
                                                               ", but the margin fell more than 3 points")})
    else:
        tests.append({"test": "Revenue up in at least 75% of years", "passed": None, "detail": "Not measured"})
    measured = [t for t in tests if t["passed"] is not None]
    if len(measured) < 3:
        return _component("durability", label, "insufficient",
                          reason="Fewer than three of the four moat-evidence tests have data.",
                          figures={"tests": tests})
    score = float(sum(1 for t in measured if t["passed"])) * 4.0 / len(measured)
    return _component(
        "durability", label, "scored", score,
        "{} of {} measurable moat tests passed.".format(sum(1 for t in measured if t["passed"]), len(measured)),
        ["{}: {} ({})".format(t["test"], "passed" if t["passed"] else "not passed" if t["passed"] is False
                              else "not measured", t["detail"]) for t in tests]
        + ["These tests find the traces a durable advantage leaves in the accounts. They do not say what the "
           "advantage is (brand, network, switching costs, scale, licences); that needs the annual report "
           "and reporting, cited."],
        {"tests": tests})


def rule_of_40(hist: List[Dict[str, Any]], values: Dict[str, Any]) -> Dict[str, Any]:
    if not hist:
        return {"applies": False}
    g = _der(hist[0], "revenue_growth")
    if g is None or g < values["rule_of_40_min_growth"]:
        return {"applies": False,
                "reason": "Applied only to companies growing revenue at least {} a year, where trading "
                          "margin for growth is the strategy; this one grew {}.".format(
                              _pct(values["rule_of_40_min_growth"], 0), _pct(g))}
    rev, cfo, capex = _flow(hist[0], "revenue"), _flow(hist[0], "cfo"), _flow(hist[0], "capex")
    if not rev or cfo is None:
        return {"applies": True, "available": False, "reason": "No free cash flow for the latest year."}
    fcf_m = (cfo - (capex or 0.0)) / rev
    total = (g + fcf_m) * 100.0
    return {"applies": True, "available": True, "growth": g, "fcf_margin": fcf_m, "total": total,
            "passes": total >= 40.0,
            "text": "Revenue growth {} plus free-cash-flow margin {} = {:.0f}, {} 40.".format(
                _pct(g), _pct(fcf_m), total, "at or above" if total >= 40 else "below")}


def business_quality(data: Dict[str, Any], kind: str, wacc: Optional[float], cost_equity: Optional[float],
                     values: Dict[str, Any], splits: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    hist = data.get("history") or []
    if not hist:
        return {"status": "insufficient", "grade": None, "components": [],
                "reason": "No annual filings were read for this company."}
    ret = returns_component(hist, kind, wacc, cost_equity)
    hurdle = cost_equity if kind in ("bank", "insurer") else wacc
    comps = [ret, margins_component(hist, kind), growth_component(hist, kind),
             cash_component(hist, kind, int(values["cash_conversion_years"])),
             health_component(hist, data.get("balance") or hist[0].get("balance") or {}, kind, values),
             dilution_component(hist, kind, splits), durability_component(hist, kind, ret, hurdle)]
    scored = [c for c in comps if c["status"] == "scored"]
    need = int(values["quality_min_components"])
    r40 = rule_of_40(hist, values)
    if len(scored) < need:
        return {"status": "insufficient", "grade": None, "score": None, "components": comps, "rule_of_40": r40,
                "reason": "Only {} of the quality measures could be scored for this {} (the framework needs "
                          "{}). That is a gap in the evidence, not a low grade.".format(
                              len(scored), kind.replace("_", " "), need),
                "weights": QUALITY_WEIGHTS}
    wsum = sum(QUALITY_WEIGHTS[c["id"]] for c in scored)
    score = sum(c["score"] * QUALITY_WEIGHTS[c["id"]] for c in scored) / wsum
    strongest = max(scored, key=lambda c: c["score"])
    weakest = min(scored, key=lambda c: c["score"])
    return {"status": "scored", "grade": letter(score), "score": round(score, 2), "components": comps,
            "rule_of_40": r40, "weights": QUALITY_WEIGHTS,
            "strongest": strongest["id"], "weakest": weakest["id"],
            "unscored": [c["id"] for c in comps if c["status"] != "scored"],
            "summary": "Business quality {} ({:.2f} of 4 across {} measures). Strongest: {}; weakest: {}.".format(
                letter(score), score, len(scored), strongest["label"].lower(), weakest["label"].lower())}


# --------------------------------------------------------------- valuation

def valuation_grade(val: Dict[str, Any], data: Dict[str, Any], lt: Dict[str, Any],
                    comps: Optional[Dict[str, Any]], kind: str,
                    revenue_cagr: Optional[float]) -> Dict[str, Any]:
    out: List[Dict[str, Any]] = []
    price = _v((val.get("market") or {}).get("price")) or _v((data.get("quote") or {}).get("price"))
    fit = (val.get("classification") or {})
    models = fit.get("models") or {}
    # 1. Intrinsic value from the model that fits.
    model_id = "residual_income" if kind in ("bank", "insurer") else "dcf"
    block = val.get(model_id) or {}
    per_share = _v(block.get("per_share"))
    fit_level = (models.get(model_id) or {}).get("fit")
    if per_share is not None and price:
        upside = per_share / price - 1.0
        primary = fit_level == "primary" and fit.get("confidence") == "normal"
        sc = (val.get("scenarios") or {}) if model_id == "dcf" else {}
        rng = {k: _v((sc.get(k) or {}).get("per_share")) for k in ("bear", "base", "bull")}
        ev = ["{} base case {:.2f} a share against {:.2f} ({:+.0%}).".format(
            (models.get(model_id) or {}).get("name") or model_id, per_share, price, upside)]
        if rng.get("bear") is not None and rng.get("bull") is not None:
            ev.append("Bear to bull scenarios: {:.2f} to {:.2f}.".format(rng["bear"], rng["bull"]))
        # A model value more than double the price, or under 40% of it, says
        # more about the assumptions than about the price: NVIDIA's base case
        # came out 226% above the price on 2026-10-14, which would have graded
        # the stock cheap on the strength of a growth path, not a measurement.
        implausible = upside > 1.0 or upside < -0.6
        if primary and implausible:
            out.append(_component("intrinsic", "Intrinsic value", "not_applicable",
                                  reason="The base case is {:+.0%} from the price, a gap wider than the model's own "
                                         "reliability: it reflects the assumptions (growth and margins held for "
                                         "years) more than a mispricing, so it is shown and not graded. The "
                                         "fair-value workspace shows which assumption drives it.".format(upside),
                                  evidence=ev, figures={"per_share": per_share, "upside": upside, "scenarios": rng}))
        elif primary:
            out.append(_component("intrinsic", "Intrinsic value", "scored",
                                  _band(upside, [(0.30, 4), (0.10, 3), (-0.10, 2), (-0.30, 1)]),
                                  "The base-case model value is {:+.0%} from the price.".format(upside), ev,
                                  {"per_share": per_share, "upside": upside, "scenarios": rng,
                                   "model": model_id, "model_version": val.get("model_version")}))
        else:
            out.append(_component("intrinsic", "Intrinsic value", "not_applicable",
                                  reason="The {} is a {} fit at {} confidence here, so it is shown but not "
                                         "graded.".format(model_id.replace("_", " "), fit_level or "limited",
                                                          fit.get("confidence") or "limited"),
                                  evidence=ev, figures={"per_share": per_share, "upside": upside}))
    else:
        reason = (block.get("reason") or "The model was not run.") if isinstance(block, dict) else "Not run."
        out.append(_component("intrinsic", "Intrinsic value", "insufficient", reason=reason))
    # 2. Against its own history.
    vh = (lt or {}).get("valuation_history") or {}
    pct = _v(vh.get("percentile"))
    if vh.get("available", True) and pct is not None:
        p = pct / 100.0 if pct > 1.0 else pct
        score = 4 if p <= 0.2 else 3 if p <= 0.4 else 2 if p <= 0.6 else 1 if p <= 0.8 else 0
        out.append(_component("own_history", "Against its own history", "scored", score,
                              "The P/E sits at the {:.0f}th percentile of its five-year range.".format(p * 100),
                              [vh.get("read") or "", "Median P/E {}; premium to median {}.".format(
                                  vh.get("median_pe"), "{:+.0f}%".format(vh["premium_to_median_pct"])
                                  if vh.get("premium_to_median_pct") is not None else "n/a")],
                              {"percentile": p, "median_pe": vh.get("median_pe"),
                               "premium_to_median_pct": vh.get("premium_to_median_pct")}))
    else:
        out.append(_component("own_history", "Against its own history", "insufficient",
                              reason=vh.get("reason") or "No five-year P/E range (negative or missing earnings)."))
    # 3. Cash yield, matched measures.
    if kind in ("bank", "insurer"):
        out.append(_component("cash_yield", "Cash yield", "not_applicable",
                              reason="Free cash flow does not describe a lender's or insurer's earnings."))
    else:
        hist = data.get("history") or []
        mcap = _v((data.get("quote") or {}).get("market_cap"))
        rf = _v((data.get("risk_free") or {}).get("value"))
        y0 = hist[0] if hist else {}
        cfo, capex = _flow(y0, "cfo"), _flow(y0, "capex")
        fcff = _der(y0, "fcff")
        bal = data.get("balance") or {}
        if cfo is not None and mcap and rf is not None:
            fcfe_yield = (cfo - (capex or 0.0)) / mcap
            debt = (_v(bal.get("debt")) or 0.0) + (_v(bal.get("finance_leases")) or 0.0)
            cash = (_v(bal.get("cash")) or 0.0) + (_v(bal.get("short_term_investments")) or 0.0)
            ev_ = mcap + debt - cash
            fcff_yield = (fcff / ev_) if (fcff is not None and ev_ > 0) else None
            spread = fcfe_yield - rf
            out.append(_component(
                "cash_yield", "Cash yield", "scored",
                _band(spread, [(0.02, 4), (0.0, 3), (-0.015, 2), (-0.03, 1)]),
                "Free cash flow yields {} on the market value, against a {} 10-year Treasury.".format(
                    _pct(fcfe_yield), _pct(rf)),
                ["Free cash flow (operating cash flow minus capex, {}) over market capitalisation: {}.".format(
                    _fy(y0), _pct(fcfe_yield)),
                 "Free cash flow to the firm over enterprise value: {}.".format(_pct(fcff_yield)),
                 "A yield below the Treasury's is a bet on growth; it is not wrong, but it needs the growth."],
                {"fcfe_yield": fcfe_yield, "fcff_yield": fcff_yield, "risk_free": rf, "spread": spread,
                 "enterprise_value": ev_},
                [_source(y0, "cfo", "operating cash flow"), _source(y0, "capex")]))
        else:
            out.append(_component("cash_yield", "Cash yield", "insufficient",
                                  reason="Needs operating cash flow, a market value and a risk-free rate."))
    # 4. What the price implies.
    rev_solves = ((val.get("reverse") or {}).get("solves") or [])
    implied = _v(rev_solves[0].get("implied_cagr")) if rev_solves else None
    # The yardstick is analysts' growth for the next two years when the feed
    # has it, and the company's own record only when that record is a fair
    # guide: a five-year CAGR of 68% (NVIDIA through the AI build-out) made an
    # implied 24.5% look cheap against a pace nobody forecasts to continue.
    cons = (data.get("consensus") or {})
    fwd = [g for g in (_v(cons.get("growth_y1")), _v(cons.get("growth_y2"))) if g is not None] if cons.get("available") else []
    if fwd:
        yard, yard_label = mean(fwd), "analysts' revenue growth for the next {} year{}".format(len(fwd), "s" if len(fwd) > 1 else "")
    elif revenue_cagr is not None and revenue_cagr <= 0.30:
        yard, yard_label = revenue_cagr, "the company's own revenue record"
    else:
        yard, yard_label = None, None
    if implied is not None and yard is not None and fit_level == "primary":
        gap = implied - yard
        out.append(_component(
            "implied_growth", "What the price assumes", "scored",
            4 if gap <= -0.05 else 3 if gap <= 0 else 2 if gap <= 0.05 else 1 if gap <= 0.10 else 0,
            "The price implies about {} revenue growth a year, against {} from {}.".format(
                _pct(implied), _pct(yard), yard_label),
            ["Reverse DCF holding the other base-case assumptions fixed.",
             "Revenue record for comparison: {}.".format(_pct(revenue_cagr))],
            {"implied_cagr": implied, "yardstick": yard, "yardstick_basis": yard_label,
             "historical_cagr": revenue_cagr, "gap": gap}))
    else:
        out.append(_component("implied_growth", "What the price assumes", "insufficient",
                              reason=("The revenue record ({}) is too fast to be a yardstick and no analyst growth "
                                      "estimate matched the filings.".format(_pct(revenue_cagr))
                                      if implied is not None and fit_level == "primary" else
                                      "Needs a reverse DCF on a primary-fit model and a growth yardstick.")))
    # 5. Peers.
    if comps and comps.get("available"):
        key = "pe"
        rows = comps.get("peers") or []
        own = next((i.get("own_multiple") for i in comps.get("implied") or [] if i.get("key") == key), None)
        if own is None or own <= 0:
            key = "ev_ebitda"
            own = next((i.get("own_multiple") for i in comps.get("implied") or [] if i.get("key") == key), None)
        peers = [r.get(key) for r in rows if r.get(key) and r.get(key) > 0]
        if own and own > 0 and len(peers) >= 3:
            med = median(peers)
            rel = own / med
            out.append(_component(
                "peers", "Against peers", "scored",
                4 if rel <= 0.75 else 3 if rel <= 0.95 else 2 if rel <= 1.1 else 1 if rel <= 1.4 else 0,
                "{} {:.1f} against a peer median of {:.1f} ({:.2f}x).".format(
                    "P/E" if key == "pe" else "EV/EBITDA", own, med, rel),
                ["Peers: {}.".format(", ".join(r["symbol"] for r in rows if r.get(key))),
                 comps.get("note") or ""],
                {"multiple": key, "own": own, "peer_median": med, "relative": rel,
                 "peer_source": comps.get("peer_source")}))
        else:
            out.append(_component("peers", "Against peers", "insufficient",
                                  reason="Fewer than three peers with a positive multiple."))
    else:
        out.append(_component("peers", "Against peers", "insufficient",
                              reason=(comps or {}).get("reason") or "Peer multiples were not read."))
    scored = [c for c in out if c["status"] == "scored"]
    if len(scored) < 2:
        return {"status": "insufficient", "label": "Insufficient Data", "score": None, "components": out,
                "reason": "Fewer than two valuation measures could be scored."}
    score = mean(c["score"] for c in scored)
    name = next(n for floor, n in VALUATION_LABELS if score >= floor)
    return {"status": "scored", "label": name, "score": round(score, 2), "components": out,
            "summary": "Valuation {} ({:.2f} of 4, where 4 is cheapest, across {} measures).".format(
                name.lower(), score, len(scored))}


# -------------------------------------------------------------- chart context

def chart_context(lt: Dict[str, Any], weekly_volume: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    trend = (lt or {}).get("long_trend") or {}
    above200, above40 = trend.get("above_200w_sma"), trend.get("above_40w_sma")
    slope = trend.get("slope_40w_pct_3m")
    if above200 is None and above40 is None:
        state = "unknown"
        text = "Not enough weekly history to read the long-term structure."
    elif above200 and above40:
        state, text = "intact", "Above the 40- and 200-week averages: the long-term uptrend is intact."
    elif above200 and not above40:
        state, text = "damaged", ("Below the 40-week but above the 200-week average: an intermediate "
                                  "pullback inside a long-term uptrend.")
    elif not above200 and above40:
        state, text = "repairing", "Above the 40-week but below the 200-week average: trying to repair."
    else:
        state, text = "broken", "Below the 40- and 200-week averages: the long-term trend is down."
    out: Dict[str, Any] = {
        "state": state, "text": text, "phase": trend.get("phase"),
        "vs_40w_pct": trend.get("vs_40w_sma"), "vs_200w_pct": trend.get("vs_200w_sma"),
        "slope_40w_pct_3m": slope, "weekly_rsi": trend.get("weekly_rsi"),
        "drawdown_pct": ((lt or {}).get("drawdown") or {}).get("current_drawdown_pct"),
    }
    if weekly_volume:
        out["volume"] = weekly_volume
    return out


def weekly_volume_read(weekly) -> Optional[Dict[str, Any]]:
    """Volume on up weeks against down weeks over the last 26 weeks, as an
    interpretation and labelled one. More volume on up weeks is consistent with
    accumulation; it does not show who bought, and it is not proof of it."""
    try:
        w = weekly.tail(27)
        if len(w) < 20 or "Volume" not in w:
            return None
        chg = w["Close"].diff().iloc[1:]
        vol = w["Volume"].iloc[1:]
        up, down = float(vol[chg > 0].sum()), float(vol[chg < 0].sum())
    except Exception:                                                     # noqa: BLE001
        return None
    if not up or not down:
        return None
    ratio = up / down
    lean = "accumulation" if ratio >= 1.25 else "distribution" if ratio <= 0.8 else "balanced"
    return {"up_down_volume_ratio": round(ratio, 2), "weeks": int(len(chg)), "interpretation": lean,
            "text": ("Over the last {} weeks, volume on up weeks was {:.2f}x volume on down weeks, {}. This is "
                     "an interpretation of volume, not evidence of who traded.".format(
                         len(chg), ratio, {"accumulation": "a pattern consistent with accumulation",
                                           "distribution": "a pattern consistent with distribution",
                                           "balanced": "no clear lean"}[lean]))}


# --------------------------------------------------------------- conviction

def conviction(quality: Dict[str, Any], val: Dict[str, Any], chart: Dict[str, Any],
               values: Dict[str, Any]) -> Dict[str, Any]:
    """The overall long-term label, and every rule that shaped it, by name."""
    applied: List[Dict[str, Any]] = []
    cap = values["quality_cap_grade"]
    if quality.get("status") != "scored":
        return {"label": "Insufficient Data", "rules": applied,
                "why": quality.get("reason") or "Business quality could not be graded."}
    g = quality["grade"]
    vlabel = val.get("label") if val.get("status") == "scored" else None
    if g in ("D", "F"):
        return {"label": "Not Investable", "rules": applied,
                "why": "Business quality grades {}: the measured economics (returns, cash, balance sheet) do not "
                       "meet this framework's bar, whatever the price.".format(g)}
    if policy_mod.grade_below(g, cap):
        label = "Weak Structure" if chart.get("state") == "broken" else "Neutral"
        applied.append(policy_mod.describe("quality_cap_grade", values))
        return {"label": label, "rules": applied,
                "why": "Business quality grades {}, below {}, which caps conviction at Neutral under this "
                       "framework's policy{}.".format(
                           g, cap, "; the long-term trend is also broken" if label == "Weak Structure" else "")}
    # Quality at or above the cap grade.
    if chart.get("state") == "broken":
        return {"label": "Weak Structure", "rules": applied,
                "why": "The business grades {} but the long-term trend is down. That is technical weakness, "
                       "not by itself a failed business thesis; the next results decide which it is.".format(g)}
    if vlabel is None:
        label = "Constructive"
        why = ("Business quality grades {}; valuation could not be graded, so conviction stops at "
               "Constructive.".format(g))
    elif vlabel in ("Attractive", "Fair"):
        label = "High Conviction" if g == "A" else "Constructive"
        why = "Business quality {} and {} {} valuation{}.".format(
            g, "an" if vlabel.lower()[0] in "aeiou" else "a", vlabel.lower(),
            "" if g == "A" else "; High Conviction needs an A")
    elif vlabel == "Full":
        label = "Constructive" if g == "A" else "Neutral"
        why = "Business quality {} at a full valuation: the price already assumes much of the quality.".format(g)
    else:
        label = "Neutral"
        why = "Business quality {} but a stretched valuation: a good business at a price that leaves little room.".format(g)
    if chart.get("state") == "damaged" and label == "High Conviction":
        label = "Constructive"
        why += " The intermediate trend is in a pullback, so this stops at Constructive until it repairs."
    return {"label": label, "rules": applied, "why": why}


def accumulation_zones(lt: Dict[str, Any], quality: Dict[str, Any], val: Dict[str, Any],
                       conv: Dict[str, Any]) -> Dict[str, Any]:
    """Conditional zones, only when the framework would consider accumulation
    at all. Each zone says what it is and what would have to stay true."""
    if conv.get("label") not in ("High Conviction", "Constructive"):
        return {"offered": False,
                "reason": "No accumulation zones: conviction is {}, and zones are offered only at Constructive "
                          "or above.".format(conv.get("label"))}
    price = _v((lt or {}).get("price"))
    zones: List[Dict[str, Any]] = []
    trend = (lt or {}).get("long_trend") or {}
    for key, name in (("sma_40w", "40-week average"), ("sma_200w", "200-week average")):
        lvl = _v(trend.get(key))
        if lvl and price and lvl < price:
            zones.append({"price": round(lvl, 2), "basis": name, "distance_pct": round((lvl / price - 1) * 100, 1)})
    for lvl in (((lt or {}).get("levels") or {}).get("support_resistance") or [])[:6]:
        p = _v(lvl.get("price"))
        if p and price and p < price and lvl.get("role") == "support":
            zones.append({"price": round(p, 2), "basis": "weekly support ({} touches)".format(lvl.get("touches")),
                          "distance_pct": round((p / price - 1) * 100, 1)})
    bear = None
    for c in (val.get("components") or []):
        if c["id"] == "intrinsic":
            bear = ((c.get("figures") or {}).get("scenarios") or {}).get("bear")
    if bear and price and bear < price:
        zones.append({"price": round(bear, 2), "basis": "DCF bear-case value",
                      "distance_pct": round((bear / price - 1) * 100, 1)})
    zones = sorted({z["price"]: z for z in zones if z["distance_pct"] >= -40}.values(), key=lambda z: -z["price"])[:4]
    if not zones:
        return {"offered": False, "reason": "No support level or value estimate below the price within 40%."}
    weakest = quality.get("weakest")
    return {"offered": True, "zones": zones,
            "condition": ("Zones are conditional: they are levels to reassess at, if the business evidence "
                          "still holds when price gets there (the next results confirming the {} measure "
                          "has not deteriorated). They are not targets, and no allocation is implied "
                          "without your portfolio's context.".format(
                              next((c["label"].lower() for c in quality.get("components") or []
                                    if c["id"] == weakest), "weakest")))}


def loss_paths(data: Dict[str, Any], quality: Dict[str, Any], val: Dict[str, Any],
               lt: Dict[str, Any], kind: str = "operating") -> List[Dict[str, Any]]:
    """Plausible ways this investment loses money over three years, computed
    where the data allows and ranked by size. Two are returned."""
    hist = data.get("history") or []
    cands: List[Dict[str, Any]] = []
    vh = (lt or {}).get("valuation_history") or {}
    prem = _v(vh.get("premium_to_median_pct"))
    if prem is not None and prem > 5:
        drop = 1.0 - 1.0 / (1.0 + prem / 100.0)
        cands.append({"risk": "Multiple compression",
                      "size": drop,
                      "text": "The P/E is {:.0f}% above its five-year median. If earnings hold flat for three "
                              "years and the multiple returns to the median, the price falls about {:.0%} with "
                              "nothing wrong with the business.".format(prem, drop)})
    margins = [_der(y, "ebit_margin") for y in _comparable_years(hist)]
    margins = [m for m in margins if m is not None]
    operating = kind not in ("bank", "insurer", "reit")
    if operating and len(margins) >= 3 and margins[0] - mean(margins) > 0.02 and margins[0] > 0:
        cut = 1.0 - mean(margins) / margins[0]
        cands.append({"risk": "Margin reversion",
                      "size": cut,
                      "text": "Operating margin is {} against a {} average over the years read. Reverting to "
                              "the average would cut operating income about {:.0%} at the same revenue.".format(
                                  _pct(margins[0]), _pct(mean(margins)), cut)})
    for c in (val.get("components") or []):
        if c["id"] == "implied_growth" and c["status"] == "scored" and (c["figures"].get("gap") or 0) > 0.02:
            cands.append({"risk": "Growth the price needs",
                          "size": c["figures"]["gap"] * 3,
                          "text": "The price assumes about {} revenue growth a year against {} from {}. "
                                  "Growing at that slower rate instead would leave the price needing to fall to "
                                  "match.".format(_pct(c["figures"]["implied_cagr"]), _pct(c["figures"]["yardstick"]),
                                                  c["figures"]["yardstick_basis"])})
    for c in quality.get("components") or []:
        f = c.get("figures") or {}
        if c["id"] == "health" and c["status"] == "scored" and (f.get("net_debt_to_ebitda") or 0) > 2.5:
            cands.append({"risk": "Leverage", "size": 0.25,
                          "text": "Net debt is {:.1f}x EBITDA: a profit downturn or higher refinancing rates "
                                  "would hit equity holders first.".format(f["net_debt_to_ebitda"])})
        if c["id"] == "dilution" and c["status"] == "scored" and (f.get("share_change_a_year") or 0) > 0.02:
            d = (1 + f["share_change_a_year"]) ** 3 - 1
            cands.append({"risk": "Dilution", "size": d,
                          "text": "Shares grow {} a year; over three years that is about {:.0%} more shares "
                                  "sharing the same profit.".format(_pct(f["share_change_a_year"]), d)})
        if (c["id"] == "margins" and c["status"] == "scored" and (f.get("ebit_margin_range") or 0) > 0.08
                and (kind == "cyclical" or (margins and min(margins) >= 0))):
            cands.append({"risk": "Cyclical earnings", "size": f["ebit_margin_range"],
                          "text": "Operating margin has ranged {:.0f} points: buying on peak earnings is the "
                                  "classic way a cyclical loses money.".format(f["ebit_margin_range"] * 100)})
    dd = ((lt or {}).get("drawdown") or {})
    if dd.get("max_drawdown_pct") is not None:
        cands.append({"risk": "Market drawdown", "size": abs(dd["max_drawdown_pct"]) / 100.0 * 0.5,
                      "text": "The stock's worst fall in the history read was {:.0f}% (to {}). A broad bear "
                              "market takes good businesses down with it, and three years is short enough "
                              "to end inside one.".format(dd["max_drawdown_pct"], dd.get("max_drawdown_date"))})
    cands.sort(key=lambda c: -(c.get("size") or 0))
    seen, out = set(), []
    for c in cands:
        if c["risk"] in seen:
            continue
        seen.add(c["risk"])
        out.append({"risk": c["risk"], "text": c["text"]})
        if len(out) == 2:
            break
    return out
