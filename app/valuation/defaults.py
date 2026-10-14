"""A starting assumption set built from the company's own history, each value
with the reason it was chosen and what kind of figure it is.

The defaults lean neither way. Growth starts from analysts' published
consensus when their base year matches the filings, otherwise from the
company's own three-year record, and fades to a long-run rate. Margins revert
toward their recent average instead of extending a trend. Capex that has
surged moves part of the way back toward its recent average, not all the way
to the pre-surge level. None of them is a forecast Optic makes. They are a
documented place to start, meant to be changed.

Kinds:
  reported           - read from a filing
  history            - computed from several filed years
  external_estimate  - published by someone else (analyst consensus)
  market             - observed in a market (a yield, a price)
  assumption         - a choice, explained
"""

from __future__ import annotations

from statistics import mean, median
from typing import Any, Dict, List, Optional, Tuple

from . import engine

ERP = 0.0423
ERP_SOURCE = ("Damodaran, implied equity risk premium for the S&P 500, January 2026 "
              "(4.23%, trailing-12-month cash yield)")
MARGINAL_TAX = 0.25
MARGINAL_TAX_WHY = ("US federal statutory 21% plus roughly 4% state tax, the rate a company "
                    "converges to as tax deferrals and credits run out (Damodaran's convention). "
                    "A multinational with persistent low-tax foreign profits may stay lower.")
TERMINAL_GROWTH = 0.025
UNPROFITABLE_TARGET_MARGIN = 0.08
UNPROFITABLE_TARGET_CAPEX = 0.08
BLUME = (0.67, 0.33)
HORIZON = 10


def _v(f: Optional[Dict[str, Any]]) -> Optional[float]:
    if not f:
        return None
    v = f.get("value")
    return None if v is None else float(v)


def _avg(values: List[Optional[float]], n: int) -> Optional[float]:
    clean = [v for v in values[:n] if v is not None]
    return mean(clean) if clean else None


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def build_base(data: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """The reported starting point the engine forecasts from. Returns the base
    and the list of figures that were missing (which block the DCF)."""
    hist = data["history"]
    fy0 = hist[0]
    f0, b0, d0 = fy0["flows"], fy0["balance"], fy0["derived"]
    bal = data["balance"]
    missing: List[str] = []
    for key, label in (("revenue", "revenue"), ("operating_income", "operating income (EBIT)"),
                       ("capex", "capital expenditure"), ("da", "depreciation and amortization")):
        if _v(f0.get(key)) is None:
            missing.append(label)
    if _v(bal.get("cash")) is None:
        missing.append("cash")
    if data["shares"].get("value") is None:
        missing.append("share count")

    das = [(y["derived"] or {}).get("da_pct") for y in hist]
    base = {
        "fy0_end": fy0["fy_end"], "balance_date": data["balance_date"],
        "valuation_date": data["valuation_date"],
        "revenue": _v(f0.get("revenue")), "ebit": _v(f0.get("operating_income")),
        "ppe": _v(b0.get("ppe")), "nwc": _v(b0.get("nwc")),
        "invested_capital": d0.get("invested_capital"),
        "da_pct": _avg(das, 3),
        "nol": 0.0,
        "shares": data["shares"].get("value"),
        "price": data["quote"].get("price"),
        "risk_free": (data.get("risk_free") or {}).get("value"),
        "bridge": {k: _v(bal.get(k)) for k in engine.BRIDGE_ADD + engine.BRIDGE_SUBTRACT},
        "currency": data.get("statement_currency") or "USD",
    }
    # The condensed balance sheet the three-statement forecast starts from, at
    # FY0 so it lines up with the base year. Other assets and other
    # liabilities are the plugs that make the reported totals add up.
    assets, liabs = _v(b0.get("assets")), _v(b0.get("liabilities"))
    oca, ocl = b0.get("operating_current_assets"), b0.get("operating_current_liabilities")
    if None not in (assets, oca, ocl, base["ppe"], _v(b0.get("cash"))):
        cash = _v(b0["cash"]) + (_v(b0.get("short_term_investments")) or 0.0)
        debt = (_v(b0.get("debt")) or 0.0) + (_v(b0.get("finance_leases")) or 0.0)
        inv = _v(b0.get("long_term_investments")) or 0.0
        equity_total = None
        if liabs is not None:
            equity_total = assets - liabs
        else:
            eq = _v(b0.get("equity_incl_nci")) or ((_v(b0.get("equity")) or 0.0)
                                                     + (_v(b0.get("noncontrolling_interests")) or 0.0))
            equity_total = eq
            liabs = assets - eq
        other_a = assets - cash - oca - base["ppe"] - inv
        other_l = liabs - ocl - debt
        reported_eq = (_v(b0.get("equity")) or 0.0) + (_v(b0.get("noncontrolling_interests")) or 0.0)
        base["balance_sheet"] = {
            "date": fy0["fy_end"], "cash": cash, "operating_current_assets": oca, "ppe": base["ppe"],
            "investments": inv, "other_assets": other_a, "operating_current_liabilities": ocl,
            "debt": debt, "other_liabilities": other_l, "equity": equity_total,
            "reported_equity_incl_nci": reported_eq,
            "unexplained_equity": equity_total - reported_eq,
        }
    return base, missing


def wacc_parts(data: Dict[str, Any], base: Dict[str, Any]) -> Dict[str, Any]:
    """Each input to the discount rate, with what kind of figure it is."""
    rf = data.get("risk_free") or {}
    raw_beta = data["quote"].get("beta")
    hist = data["history"]
    f0 = hist[0]["flows"]
    rating = engine.synthetic_rating(_v(f0.get("operating_income")), _v(f0.get("interest_expense")))
    rf_val = rf.get("value")
    kd = (rf_val + rating["spread"]) if (rf_val is not None and rating["spread"] is not None) else None
    implied_kd = None
    interest = _v(f0.get("interest_expense"))
    b = base["bridge"]
    debt_total = (b.get("debt") or 0.0) + (b.get("finance_leases") or 0.0)
    if interest and debt_total > 0:
        implied_kd = interest / debt_total
    kd_source = "synthetic_rating"
    ebit = _v(f0.get("operating_income"))
    if ebit is not None and ebit <= 0 and implied_kd is not None and rf_val is not None:
        # Coverage is undefined with operating losses; a D rating would price
        # the debt as if in default. The rate the company actually pays is the
        # better evidence then.
        kd, kd_source = max(implied_kd, rf_val), "filing_implied"
    return {
        "risk_free": rf_val, "risk_free_meta": rf,
        "beta_raw": raw_beta, "beta_adjust": "blume",
        "erp": ERP, "extra_premium": 0.0,
        "pre_tax_cost_debt": kd, "rating": rating, "implied_cost_debt": implied_kd, "kd_source": kd_source,
        "marginal_tax": MARGINAL_TAX, "override": None,
    }


def equity_cost(parts: Dict[str, Any]) -> Dict[str, Any]:
    """CAPM cost of equity on its own: what the equity-side models (residual
    income, dividends) need, and all a bank or insurer has a use for."""
    rf, erp, raw = parts.get("risk_free"), parts.get("erp"), parts.get("beta_raw")
    if rf is None:
        raise engine.ModelError("A risk-free rate is needed for the cost of equity.")
    if raw is None:
        raise engine.ModelError("No beta in the quote feed; enter one to compute the cost of equity.")
    beta = BLUME[0] * raw + BLUME[1] if parts.get("beta_adjust", "blume") == "blume" else raw
    return {"cost_equity": engine.cost_of_equity(rf, beta, erp, parts.get("extra_premium") or 0.0),
            "beta": beta, "beta_raw": raw, "risk_free": rf, "erp": erp}


def compute_wacc(parts: Dict[str, Any], base: Dict[str, Any]) -> Dict[str, Any]:
    """The discount rate from its parts, or the reader's override. Returns
    every intermediate so the page can show the derivation."""
    if parts.get("override") is not None:
        w = float(parts["override"])
        return {"wacc": w, "override": True, "cost_equity": parts.get("cost_equity_override") or w,
                "note": "Entered directly by the reader."}
    rf, erp = parts.get("risk_free"), parts.get("erp")
    raw = parts.get("beta_raw")
    if rf is None:
        raise engine.ModelError("A risk-free rate is needed for the discount rate.")
    if raw is None:
        raise engine.ModelError("No beta in the quote feed; enter one, or enter the discount rate directly.")
    beta = BLUME[0] * raw + BLUME[1] if parts.get("beta_adjust", "blume") == "blume" else raw
    ke = engine.cost_of_equity(rf, beta, erp, parts.get("extra_premium") or 0.0)
    kd = parts.get("pre_tax_cost_debt")
    if kd is None:
        raise engine.ModelError("A pre-tax cost of debt is needed for the discount rate.")
    equity_mv = (base.get("price") or 0.0) * (base.get("shares") or 0.0)
    b = base["bridge"]
    debt = (b.get("debt") or 0.0) + (b.get("finance_leases") or 0.0)
    if parts.get("debt_weight") is not None:
        wd = float(parts["debt_weight"])
        equity_mv, debt = 1.0 - wd, wd
    out = engine.wacc(ke, kd, parts.get("marginal_tax") or MARGINAL_TAX, equity_mv, debt)
    out.update({"beta": beta, "beta_raw": raw, "risk_free": rf, "erp": erp,
                "extra_premium": parts.get("extra_premium") or 0.0, "override": False,
                "equity_market_value": equity_mv if parts.get("debt_weight") is None else None,
                "debt_book_value": debt if parts.get("debt_weight") is None else None})
    return out


def default_drivers(data: Dict[str, Any], base: Dict[str, Any], kind: str,
                    wacc_value: Optional[float]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """The base-case drivers, and a line of rationale for each."""
    hist = data["history"]
    d = [y["derived"] for y in hist]
    why: List[Dict[str, Any]] = []

    def note(key: str, value: Any, kind_: str, text: str) -> None:
        why.append({"key": key, "value": value, "kind": kind_, "why": text})

    cons = data.get("consensus") or {}
    revs = [_v(y["flows"].get("revenue")) for y in hist]
    cagr = None
    if len(revs) >= 4 and revs[0] and revs[3] and revs[3] > 0:
        cagr = (revs[0] / revs[3]) ** (1 / 3.0) - 1.0
    elif len(revs) >= 2 and revs[0] and revs[-1] and revs[-1] > 0:
        cagr = (revs[0] / revs[-1]) ** (1 / (len(revs) - 1.0)) - 1.0
    g_term = TERMINAL_GROWTH
    rf = base.get("risk_free")
    if rf is not None and rf - 0.005 < g_term:
        g_term = max(0.0, rf - 0.005)
    if cons.get("available"):
        g1, g2 = cons["growth_y1"], cons.get("growth_y2")
        note("growth.y1", g1, "external_estimate", "Analysts' average revenue estimate for the current fiscal "
             "year ({} analysts), against the last reported year.".format(int(cons.get("analysts_y1") or 0)))
        if g2 is not None:
            note("growth.y2", g2, "external_estimate", "Analysts' average for the following year.")
    elif cagr is not None:
        g1, g2 = cagr, None
        note("growth.y1", g1, "history", "No usable consensus, so the company's own revenue growth over the "
             "last {} reported years.".format(min(3, len(revs) - 1)))
    else:
        g1, g2 = g_term, None
        note("growth.y1", g1, "assumption", "Too little history to measure growth, so the long-run rate.")
    note("growth.fade", None, "assumption", "Growth then falls in equal steps to the terminal rate, "
         "because high growth rarely lasts and a forecast that ends at a high rate inflates the "
         "terminal value.")

    margins = [x.get("ebit_margin") for x in d]
    m0 = margins[0] if margins and margins[0] is not None else None
    if kind == "unprofitable" or m0 is None or m0 <= 0:
        m_start = m0 if m0 is not None else 0.0
        m_target, m_years = UNPROFITABLE_TARGET_MARGIN, 7
        note("margin.target", m_target, "assumption", "Placeholder, not an estimate: the company has no "
             "profitable record to anchor on. The value depends mostly on this number; the reverse DCF "
             "shows what margin the price already assumes.")
    elif kind == "cyclical":
        m_start = m0
        avg5 = _avg([m for m in margins if m is not None and m > 0], 5) or m0
        m_target, m_years = (m0 + avg5) / 2.0, 3
        note("margin.target", m_target, "assumption", "Halfway between the last year's margin and the "
             "average of the last {} reported years ({:.1%}). A cyclical business's single year is a poor "
             "guide, but five years may not span a full cycle either, so neither is taken whole.".format(
                 min(5, len([m for m in margins if m])), avg5))
    else:
        m_start = m0
        m_target = _avg([m for m in margins if m is not None and m > 0], 3) or m0
        m_years = 5
        norm = _avg([x.get("ebit_margin_normalized") for x in d[:3]], 3)
        extra = ""
        if norm is not None and abs(norm - m_target) > 0.005:
            extra = (" Excluding the restructuring and impairment charges the filings tag (one-off items the "
                     "company itself may call non-recurring), the same average is {:.1%}; that is offered "
                     "as a what-if, not used, because untagged charges cannot be removed the same way."
                     .format(norm))
        note("margin.target", m_target, "history", "Average operating margin over the last {} reported "
             "years. Reverting to the recent average, rather than extending the latest trend, avoids "
             "building margin expansion into the base case.".format(min(3, len([m for m in margins if m]))) + extra)
    note("margin.start", m_start, "reported", "The last fiscal year's operating margin.")

    capex = [x.get("capex_pct") for x in d]
    c0 = capex[0] if capex and capex[0] is not None else (base.get("da_pct") or 0.05)
    c_avg = _avg(capex, 3) or c0
    # Partial reversion, the same rule in both directions: halfway from the
    # latest share of revenue to the three-year average over five years.
    c_target, c_years = (c0 + c_avg) / 2.0, 5
    note("capex.start", c0, "reported", "The last fiscal year's capital expenditure as a share of revenue.")
    if kind == "unprofitable" and c0 > UNPROFITABLE_TARGET_CAPEX:
        c_target, c_years = UNPROFITABLE_TARGET_CAPEX, 7
        note("capex.target", c_target, "assumption", "Placeholder, not an estimate: a business building "
             "capacity spends far more of its (small) revenue than it will at scale, so its own history is "
             "no guide. Set your own; it moves the value almost as much as the margin.")
    else:
        note("capex.target", c_target, "assumption", "Halfway between the latest year and the three-year "
             "average ({:.1%}), reached over five years: neither staying where it is nor snapping back. "
             "Capex and margins are separate assumptions: if extra spending does not earn a return, lower "
             "the margin too.".format(c_avg))

    dep = _avg([x.get("dep_rate") for x in d], 3)
    if dep is not None and base.get("ppe"):
        note("dep_rate", dep, "history", "Depreciation and amortization as a share of the previous year's "
             "net PP&E, averaged over three years. D&A follows the asset base, so a capex surge raises "
             "later depreciation.")
    else:
        dep = None
        note("da_pct", base.get("da_pct"), "history", "No PP&E figure, so D&A is held at its three-year "
             "share of revenue.")

    nwc_pct = (base["nwc"] / base["revenue"]) if (base.get("nwc") is not None and base["revenue"]) else 0.0
    note("nwc_pct", nwc_pct, "reported" if base.get("nwc") is not None else "assumption",
         "Operating working capital held at the last year's share of revenue, so each dollar of new "
         "revenue ties up (or, if negative, releases) the same share." if base.get("nwc") is not None
         else "The balance sheet has no current/non-current split, so working capital investment is "
              "assumed to be nil. This is a stated assumption, not a measured figure.")

    taxes = [x.get("effective_tax_rate") for x in d]
    t_eff = _avg([t for t in taxes if t is not None and 0 <= t <= 0.5], 3)
    t_start = _clamp(t_eff, 0.05, 0.35) if t_eff is not None else MARGINAL_TAX
    note("tax.start", t_start, "history" if t_eff is not None else "assumption",
         "Average effective tax rate over the last three years." if t_eff is not None else
         "No meaningful effective rate (losses), so the marginal rate.")
    t_term = (t_start + MARGINAL_TAX) / 2.0
    note("tax.terminal", t_term, "assumption", "Halfway between the company's recent effective rate and "
         "the 25% marginal rate. " + MARGINAL_TAX_WHY + " Halfway because both outcomes are plausible: "
         "deferrals unwind, but a global minimum of 15% and foreign profits keep many multinationals below "
         "the US marginal rate.")

    roic0 = d[0].get("roic") if d else None
    if wacc_value is None:
        # The discount rate is not known yet (an input is missing). RONIC is
        # left for the service to set equal to it once it is, and said so.
        ronic = None
        note("terminal.ronic", None, "assumption", "Set equal to the cost of capital once the discount rate "
             "can be computed; enter your own to override.")
    elif roic0 is not None and roic0 > wacc_value:
        ronic = _clamp(wacc_value + 0.5 * (roic0 - wacc_value), wacc_value, 0.40)
        note("terminal.ronic", ronic, "assumption", "Halfway between the cost of capital and today's return on "
             "invested capital ({:.0%}): some of today's advantage persists on new investment, but "
             "competition erodes part of it.".format(roic0))
    else:
        ronic = wacc_value
        note("terminal.ronic", ronic, "assumption", "Equal to the cost of capital: growth after the forecast "
             "adds no value, the conservative case when today's returns do not exceed it.")
    note("terminal.growth", g_term, "assumption", "Long-run nominal growth: around expected inflation plus "
         "modest real growth, and below the risk-free rate so the company does not outgrow the economy.")

    ebitda0 = (base.get("ebit") or 0.0) + (base.get("da_pct") or 0.0) * base["revenue"]
    f0 = hist[0]["flows"]
    if _v(f0.get("da")) is not None and base.get("ebit") is not None:
        ebitda0 = base["ebit"] + _v(f0["da"])
    b = base["bridge"]
    mcap = (base.get("price") or 0.0) * (base.get("shares") or 0.0)
    ev_mkt = mcap + sum((b.get(k) or 0.0) for k in engine.BRIDGE_SUBTRACT) - sum((b.get(k) or 0.0) for k in engine.BRIDGE_ADD)
    exit_mult = (ev_mkt / ebitda0) if ebitda0 and ebitda0 > 0 and ev_mkt > 0 else None
    if exit_mult is not None:
        note("exit_multiple", exit_mult, "market", "Today's trading EV/EBITDA. A cross-check only: using the "
             "market's own multiple to value the company is circular.")

    drivers = {
        "horizon": HORIZON, "convention": "mid_year",
        "growth": {"y1": g1, "y2": g2},
        "margin": {"start": m_start, "target": m_target, "years": m_years},
        "capex_pct": {"start": c0, "target": c_target, "years": c_years},
        "dep_rate": dep, "da_pct": None if dep is not None else base.get("da_pct"),
        "nwc_pct": nwc_pct,
        "tax": {"start": t_start, "terminal": t_term, "years": None},
        "terminal": {"method": "value_driver", "growth": g_term, "ronic": ronic},
        "exit_multiple": exit_mult,
        "overrides": {},
    }
    return drivers, why


def scenario_drivers(base_drivers: Dict[str, Any], wacc_value: float) -> Dict[str, Dict[str, Any]]:
    """Bear and bull cases that move growth, margins, capex and the long run
    together and by the same amount in each direction, so the base case is not
    quietly the optimistic end of the range."""
    import copy

    def shift(sign: int) -> Dict[str, Any]:
        d = copy.deepcopy(base_drivers)
        g = d["growth"]
        dg = max(0.03, 0.25 * abs(g["y1"]))
        g["y1"] = g["y1"] + sign * dg
        if g.get("y2") is not None:
            g["y2"] = g["y2"] + sign * dg
        m = d["margin"]
        dm = max(0.02, 0.10 * abs(m["target"]))
        m["target"] = m["target"] + sign * dm
        c = d["capex_pct"]
        c["target"] = max(0.005, c["target"] - sign * 0.02)
        t = d["terminal"]
        t["growth"] = t["growth"] + sign * 0.005
        h = max(t["ronic"] - wacc_value, 0.0)
        t["ronic"] = wacc_value if sign < 0 else t["ronic"] + h
        d["_deltas"] = {"growth": sign * dg, "margin_target": sign * dm, "capex_target": -sign * 0.02,
                        "terminal_growth": sign * 0.005, "ronic": t["ronic"] - base_drivers["terminal"]["ronic"]}
        return d

    return {"bear": shift(-1), "base": copy.deepcopy(base_drivers), "bull": shift(1)}


SCENARIO_TEXT = {
    "bear": ("Growth runs below the base path, margins settle lower, capex stays heavier, and new "
             "investment after the forecast earns only its cost of capital."),
    "base": "The defaults above: consensus or recent growth fading to the long run, margins at their "
            "recent average.",
    "bull": ("Growth runs above the base path, margins settle higher, capex eases, and new investment "
             "keeps more of today's excess return."),
}
