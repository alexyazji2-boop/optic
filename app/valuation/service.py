"""Assemble a complete, explainable valuation for one company.

`build` returns everything the workspace shows: the sourced inputs, the
classification and which models fit, the default and active assumptions with
their reasons, the DCF and its checks, scenarios, sensitivities, the
assumptions that matter most, the reverse DCF, the complementary models where
they apply, and the linked statements. `run` does the same for assumptions
the reader edited, reusing the cached inputs.

Results from different models are reported side by side and never averaged:
they answer different questions under different assumptions.
"""

from __future__ import annotations

import copy
import threading
import time
from datetime import date, datetime, timezone
from statistics import mean, median
from typing import Any, Dict, List, Optional, Tuple

from . import MODEL_VERSION, analysis, classify, defaults, engine, inputs

INPUT_TTL = 1800.0
_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_LOCK = threading.Lock()


def _v(f: Optional[Dict[str, Any]]) -> Optional[float]:
    if not f:
        return None
    v = f.get("value")
    return None if v is None else float(v)


def gathered(provider, ticker: str, force: bool = False) -> Dict[str, Any]:
    """Inputs for a ticker, cached for half an hour: the filings change four
    times a year and the quote's few seconds of drift do not move a DCF."""
    sym = ticker.upper().strip()
    now = time.time()
    with _LOCK:
        hit = _CACHE.get(sym)
    if hit and not force and now - hit[0] < INPUT_TTL:
        return hit[1]
    data = inputs.gather(provider, sym, force=force)
    if data.get("available"):
        with _LOCK:
            _CACHE[sym] = (now, data)
    return data


# ---------------------------------------------------------------------------
# Reader assumptions: merged onto the defaults and range-checked
# ---------------------------------------------------------------------------

LIMITS = {
    "growth.y1": (-0.6, 2.0), "growth.y2": (-0.6, 2.0),
    "margin.start": (-2.0, 0.95), "margin.target": (-1.0, 0.95), "margin.years": (1, 15),
    "capex_pct.start": (0.0, 1.5), "capex_pct.target": (0.0, 1.5), "capex_pct.years": (1, 15),
    "dep_rate": (0.0, 1.0), "da_pct": (0.0, 1.0), "nwc_pct": (-1.0, 1.0),
    "tax.start": (0.0, 0.6), "tax.terminal": (0.0, 0.6), "tax.years": (1, 15),
    "terminal.growth": (-0.05, 0.08), "terminal.ronic": (0.001, 2.0),
    "exit_multiple": (0.0, 100.0), "horizon": (engine.MIN_HORIZON, engine.MAX_HORIZON),
    "wacc.risk_free": (-0.02, 0.2), "wacc.beta_raw": (-1.0, 5.0), "wacc.erp": (0.0, 0.15),
    "wacc.extra_premium": (0.0, 0.2), "wacc.pre_tax_cost_debt": (0.0, 0.3),
    "wacc.marginal_tax": (0.0, 0.6), "wacc.override": (0.01, 0.4), "wacc.debt_weight": (0.0, 0.95),
}
PATH_KEYS = ("revenue_growth", "ebit_margin", "capex_pct", "tax_rate", "nwc_pct")
PATH_LIMITS = {"revenue_growth": (-0.9, 3.0), "ebit_margin": (-2.0, 0.95), "capex_pct": (0.0, 1.5),
               "tax_rate": (0.0, 0.6), "nwc_pct": (-1.0, 1.0)}
BRIDGE_KEYS = engine.BRIDGE_ADD + engine.BRIDGE_SUBTRACT


EQUITY_LIMITS = {
    "ri.roe_start": (-0.5, 1.0), "ri.roe_terminal": (-0.5, 1.0), "ri.book_growth_start": (-0.2, 0.5),
    "ri.growth_terminal": (-0.05, 0.08), "ddm.growth_high": (-0.5, 1.0), "ddm.years_high": (1, 20),
    "ddm.growth_terminal": (-0.05, 0.08), "reit.p_ffo": (0.5, 100.0),
}
LABELS_EQ = {"ri.roe_start": "Starting return on equity", "ri.roe_terminal": "Long-run return on equity",
             "ri.book_growth_start": "Starting book value growth", "ri.growth_terminal": "Long-run growth",
             "ddm.growth_high": "Dividend growth, first years", "ddm.years_high": "Years of that growth",
             "ddm.growth_terminal": "Dividend growth after that", "reit.p_ffo": "Price-to-FFO multiple"}


def equity_edits(edits: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    """The reader's changes to the equity-side models, range-checked."""
    raw = (edits or {}).get("equity") if isinstance((edits or {}).get("equity"), dict) else {}
    out: Dict[str, Dict[str, float]] = {}
    errors: List[str] = []
    for key, (lo, hi) in EQUITY_LIMITS.items():
        model, field = key.split(".")
        blk = raw.get(model) if isinstance(raw.get(model), dict) else {}
        if field not in blk or blk[field] in (None, ""):
            continue
        try:
            x = float(blk[field])
        except (TypeError, ValueError):
            errors.append("{} is not a number.".format(LABELS_EQ[key]))
            continue
        if x != x or not (lo <= x <= hi):
            plain = key in ("ddm.years_high", "reit.p_ffo")
            errors.append("{} must be between {}.".format(
                LABELS_EQ[key], "{:g} and {:g}".format(lo, hi) if plain else "{:g}% and {:g}%".format(lo * 100, hi * 100)))
            continue
        out.setdefault(model, {})[field] = x
    if errors:
        raise InputError(errors)
    return out


class NeedsInput(engine.ModelError):
    """The model lacks a figure only the reader can now supply."""


class InputError(ValueError):
    def __init__(self, errors: List[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def _same(a: Any, b: Any) -> bool:
    if a is None or b is None:
        return a is b
    try:
        return abs(float(a) - float(b)) <= 1e-12
    except (TypeError, ValueError):
        return a == b


LABELS = {
    "growth.y1": "Revenue growth, first year", "growth.y2": "Revenue growth, second year",
    "margin.start": "Operating margin, first year", "margin.target": "Target operating margin",
    "margin.years": "Years to reach the target margin", "capex_pct.start": "Capex, first year",
    "capex_pct.target": "Target capex", "capex_pct.years": "Years to reach the target capex",
    "dep_rate": "Depreciation rate", "da_pct": "D&A share of revenue", "nwc_pct": "Working capital share",
    "tax.start": "Tax rate, first year", "tax.terminal": "Long-run tax rate", "tax.years": "Years to the long-run tax rate",
    "terminal.growth": "Growth after the forecast", "terminal.ronic": "Return on new capital",
    "exit_multiple": "Exit multiple", "horizon": "Forecast years", "wacc.risk_free": "Risk-free rate",
    "wacc.beta_raw": "Beta", "wacc.erp": "Equity risk premium", "wacc.extra_premium": "Extra premium",
    "wacc.pre_tax_cost_debt": "Pre-tax cost of debt", "wacc.marginal_tax": "Tax rate for the interest shield",
    "wacc.override": "Discount rate", "wacc.debt_weight": "Debt weight",
}
PLAIN_NUMBERS = {"margin.years", "capex_pct.years", "tax.years", "horizon", "exit_multiple", "wacc.beta_raw"}


def _bounds(key: str, lo: float, hi: float) -> str:
    if key in PLAIN_NUMBERS:
        return "{:g} and {:g}".format(lo, hi)
    return "{:g}% and {:g}%".format(round(lo * 100, 4), round(hi * 100, 4))


def _check(key: str, value: Any, errors: List[str]) -> Optional[float]:
    if value is None:
        return None
    label = LABELS.get(key, key)
    try:
        x = float(value)
    except (TypeError, ValueError):
        errors.append("{} is not a number.".format(label))
        return None
    lo, hi = LIMITS.get(key, (-1e18, 1e18))
    if x != x or not (lo <= x <= hi):
        errors.append("{} must be between {}.".format(label, _bounds(key, lo, hi)))
        return None
    return x


def merge(default_drivers: Dict[str, Any], default_wacc: Dict[str, Any],
          edits: Optional[Dict[str, Any]]) -> Tuple[Dict[str, Any], Dict[str, Any], List[str]]:
    """Apply a reader's edits to the defaults. Only known fields are taken;
    anything else is ignored. Returns (drivers, wacc_parts, changed_keys)."""
    drivers, parts = copy.deepcopy(default_drivers), copy.deepcopy(default_wacc)
    if not edits:
        return drivers, parts, []
    errors: List[str] = []
    changed: List[str] = []
    d_in = edits.get("drivers") if isinstance(edits.get("drivers"), dict) else {}
    for key in LIMITS:
        if key.startswith("wacc."):
            continue
        head, _, tail = key.partition(".")
        src = d_in.get(head)
        if tail:
            if not isinstance(src, dict) or tail not in src:
                continue
            raw = src[tail]
        else:
            if head not in d_in:
                continue
            raw = d_in[head]
        if raw is None and key in ("growth.y2", "exit_multiple", "da_pct", "dep_rate", "tax.years"):
            val = None
        else:
            val = _check(key, raw, errors)
            if val is None:
                continue
        if key in ("horizon", "margin.years", "capex_pct.years", "tax.years") and val is not None:
            val = int(round(val))
        before = drivers[head].get(tail) if tail else drivers.get(head)
        if tail:
            drivers[head][tail] = val
        else:
            drivers[head] = val
        if not _same(before, val):
            changed.append(key)
    if d_in.get("convention") in ("mid_year", "end_year"):
        if d_in["convention"] != drivers.get("convention"):
            changed.append("convention")
        drivers["convention"] = d_in["convention"]
    term = d_in.get("terminal") if isinstance(d_in.get("terminal"), dict) else {}
    if term.get("method") in ("value_driver", "fcf_growth"):
        if term["method"] != drivers["terminal"]["method"]:
            changed.append("terminal.method")
        drivers["terminal"]["method"] = term["method"]
    ov = d_in.get("overrides") if isinstance(d_in.get("overrides"), dict) else {}
    clean_ov: Dict[str, Dict[str, float]] = {}
    for path in PATH_KEYS:
        per = ov.get(path)
        if not isinstance(per, dict):
            continue
        lo, hi = PATH_LIMITS[path]
        for year, raw in per.items():
            try:
                y, x = int(year), float(raw)
            except (TypeError, ValueError):
                errors.append("overrides.{}.{} is not a number.".format(path, year))
                continue
            if not (1 <= y <= engine.MAX_HORIZON) or x != x or not (lo <= x <= hi):
                errors.append("overrides.{}.{} is out of range.".format(path, year))
                continue
            clean_ov.setdefault(path, {})[str(y)] = x
            changed.append("overrides.{}.{}".format(path, y))
    drivers["overrides"] = clean_ov
    inc = d_in.get("bridge_include") if isinstance(d_in.get("bridge_include"), dict) else {}
    if inc:
        drivers["bridge_include"] = {k: bool(inc[k]) for k in BRIDGE_KEYS if k in inc}
        changed.extend("bridge_include." + k for k in drivers["bridge_include"] if not drivers["bridge_include"][k])

    w_in = edits.get("wacc") if isinstance(edits.get("wacc"), dict) else {}
    for key in LIMITS:
        if not key.startswith("wacc."):
            continue
        field = key[5:]
        if field not in w_in:
            continue
        if w_in[field] is None and field in ("override", "debt_weight"):
            if parts.get(field) is not None:
                changed.append(key)
            parts[field] = None
            continue
        val = _check(key, w_in[field], errors)
        if val is not None:
            if not _same(parts.get(field), val):
                changed.append(key)
            parts[field] = val
    if w_in.get("beta_adjust") in ("blume", "raw"):
        if w_in["beta_adjust"] != parts.get("beta_adjust"):
            changed.append("wacc.beta_adjust")
        parts["beta_adjust"] = w_in["beta_adjust"]
    if errors:
        raise InputError(errors)
    return drivers, parts, sorted(set(changed))


# ---------------------------------------------------------------------------
# Complementary models
# ---------------------------------------------------------------------------

def _hist_avg(hist: List[Dict[str, Any]], key: str, n: int = 3, lo: float = -1e9, hi: float = 1e9) -> Optional[float]:
    vals = [y["derived"].get(key) for y in hist[:n]]
    vals = [v for v in vals if v is not None and lo <= v <= hi]
    return mean(vals) if vals else None


def dividend_facts(data: Dict[str, Any]) -> Dict[str, Any]:
    hist = data["history"]
    paid = [_v(y["flows"].get("dividends_paid")) for y in hist]
    years = sum(1 for p in paid if p and p > 0)
    dps0 = _v(hist[0]["flows"].get("dps"))
    dps_kind = "reported"
    if not dps0:
        div0 = paid[0] if paid else None
        sh = _v(hist[0]["flows"].get("diluted_shares_avg"))
        if div0 and sh:
            dps0, dps_kind = div0 / sh, "derived"
    payout = _hist_avg(hist, "payout_ratio", 3, 0.0, 3.0)
    bb = _hist_avg(hist, "buyback_ratio", 3, 0.0, 5.0)
    return {"dps0": dps0, "dps_kind": dps_kind, "dividend_years": years, "payout_ratio": payout,
            "buyback_ratio": bb, "has_dividend": bool(dps0 and dps0 > 0),
            "buyback_heavy": bool(bb is not None and payout is not None and bb > payout)}


def ddm_model(data: Dict[str, Any], drivers: Dict[str, Any], ke: float, fit: Dict[str, Any],
              over: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    df = dividend_facts(data)
    if not df["has_dividend"]:
        return {"available": False, "fit": fit, "reason": "No dividend to discount."}
    g_path = engine.growth_path(drivers["growth"]["y1"], drivers["terminal"]["growth"],
                                int(drivers["horizon"]), drivers["growth"].get("y2"))
    g1 = mean(g_path[:5])
    roe = _hist_avg(data["history"], "roe", 3, -1.0, 2.0)
    sustainable = roe * (1 - df["payout_ratio"]) if (roe is not None and df["payout_ratio"] is not None
                                                     and df["payout_ratio"] < 1) else None
    note = "Five years of dividend growth equal to the base case's average revenue growth over those years"
    if sustainable is not None and sustainable < g1:
        g1 = max(sustainable, 0.0)
        note = ("Five years of dividend growth at the sustainable rate, return on equity x retention "
                "({:.1%}), which is below revenue growth".format(sustainable))
    over = over or {}
    defaults_ddm = {"growth_high": g1, "years_high": 5, "growth_terminal": drivers["terminal"]["growth"]}
    gh = over.get("growth_high", g1)
    yh = int(round(over.get("years_high", 5)))
    gt = over.get("growth_terminal", drivers["terminal"]["growth"])
    if over:
        note = "Your dividend growth path"
    try:
        r = engine.run_ddm(df["dps0"], gh, yh, gt, ke)
    except engine.ModelError as exc:
        return {"available": False, "fit": fit, "reason": str(exc), "defaults": defaults_ddm}
    r.update({"available": True, "fit": fit, "dps0": df["dps0"], "dps_kind": df["dps_kind"],
              "defaults": defaults_ddm, "edited": sorted(over),
              "growth_high": gh, "years_high": yh, "growth_terminal": gt,
              "cost_equity": ke, "payout_ratio": df["payout_ratio"], "growth_note": note + ", then the "
              "terminal rate.", **analysis.versus_price(r["per_share"], data["quote"].get("price"))})
    return r


def residual_income_model(data: Dict[str, Any], ke: float, g: float, fit: Dict[str, Any],
                          over: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    hist = data["history"]
    bal = data["balance"]
    eq, pref = _v(bal.get("equity")), _v(bal.get("preferred")) or 0.0
    shares = data["shares"].get("value")
    if eq is None or not shares:
        return {"available": False, "fit": fit, "reason": "No book value or share count."}
    common = eq - pref
    roes: List[float] = []
    for i in range(min(3, len(hist) - 1)):
        ni = _v(hist[i]["flows"].get("net_income_common"))
        e1, e0 = _v(hist[i]["balance"].get("equity")), _v(hist[i + 1]["balance"].get("equity"))
        p1, p0 = _v(hist[i]["balance"].get("preferred")) or 0.0, _v(hist[i + 1]["balance"].get("preferred")) or 0.0
        if ni is not None and e1 and e0:
            avg = ((e1 - p1) + (e0 - p0)) / 2.0
            if avg > 0:
                roes.append(ni / avg)
    if not roes:
        return {"available": False, "fit": fit, "reason": "Not enough years of earnings and equity for a "
                                                        "return on equity."}
    roe_hist = mean(roes)
    df = dividend_facts(data)
    payout = min(1.0, max(0.0, (df["payout_ratio"] or 0.0) + (df["buyback_ratio"] or 0.0)))
    over = over or {}
    d_roe, d_roe_t = roe_hist, ke + 0.5 * (roe_hist - ke)
    # Book growth starts at what the company has been retaining (ROE x
    # (1 - payout)), capped at 15% a year, and fades to the long-run rate.
    d_g0 = max(g, min(0.15, roe_hist * (1.0 - payout)))
    defaults_ri = {"roe_start": d_roe, "roe_terminal": d_roe_t, "book_growth_start": d_g0, "growth_terminal": g}
    roe = over.get("roe_start", d_roe)
    roe_t = over.get("roe_terminal", d_roe_t if "roe_start" not in over else ke + 0.5 * (roe - ke))
    g_t = over.get("growth_terminal", g)
    g0 = over.get("book_growth_start", max(g_t, min(0.15, roe * (1.0 - payout))))
    bv0 = common / shares
    try:
        r = engine.run_residual_income(bv0, roe, roe_t, ke, g0, g_t, 10)
    except engine.ModelError as exc:
        return {"available": False, "fit": fit, "reason": str(exc), "defaults": defaults_ri}
    # Sensitivity: cost of equity across, starting ROE down, every cell a run.
    ke_steps, roe_steps = [-0.01, -0.005, 0.0, 0.005, 0.01], [-0.04, -0.02, 0.0, 0.02, 0.04]
    table = []
    for dr in roe_steps:
        line = []
        for dk in ke_steps:
            try:
                k2, r2 = ke + dk, roe + dr
                line.append(engine.run_residual_income(bv0, r2, k2 + 0.5 * (r2 - k2), k2,
                                                       max(g_t, min(0.15, r2 * (1.0 - payout))), g_t, 10)["per_share"])
            except engine.ModelError:
                line.append(None)
        table.append(line)
    # Bear and bull move the starting ROE by the same amount each way; the
    # bear's long run earns only the cost of equity, the bull's keeps the
    # same excess again over it.
    step = max(0.02, 0.15 * abs(roe))
    scen = {}
    for name, sign in (("bear", -1), ("base", 0), ("bull", 1)):
        r_s = roe + sign * step
        rt_s = roe_t if sign == 0 else (ke if sign < 0 else roe_t + max(roe_t - ke, 0.0))
        g_s = g_t + sign * 0.005
        try:
            v = engine.run_residual_income(bv0, r_s, rt_s, ke, max(g_s, min(0.15, r_s * (1.0 - payout))) if sign else g0,
                                           g_s, 10)["per_share"]
        except engine.ModelError:
            v = None
        scen[name] = {"per_share": v, "roe_start": r_s, "roe_terminal": rt_s, "growth_terminal": g_s,
                      **analysis.versus_price(v, data["quote"].get("price"))}
    price = data["quote"].get("price")
    flags = []
    if roe > 2.0 * ke:
        flags.append("Return on equity of {:.0%} is more than twice the cost of equity. In insurance and "
                     "lending that is often a cyclical peak (underwriting or credit cycles), so the three-year "
                     "average may overstate what lasts; try a lower starting ROE.".format(roe))
    r.update({"available": True, "fit": fit, "roe_history": roes, "flags": flags, "defaults": defaults_ri,
              "edited": sorted(over), "scenarios": scen,
              "sensitivity": {"rows": [roe + x for x in roe_steps], "cols": [ke + x for x in ke_steps],
                              "row_label": "Starting return on equity", "col_label": "Cost of equity",
                              "values": table}, "roe_start": roe, "roe_terminal": roe_t,
              "payout": payout, "cost_equity": ke, "growth_terminal": g_t, "book_growth_start": g0,
              "common_equity": common, "price_to_book": (price / bv0) if price else None,
              "implied_roe": (g_t + (price / bv0) * (ke - g_t)) if price else None,
              "notes": ["Return on common equity, three-year average ({:.1%}); it fades halfway to the cost of "
                        "equity over ten years as competition and regulation narrow excess returns.".format(roe_hist),
                        "Book value grows at what the company has been retaining (ROE x (1 - payout), "
                        "dividends and buybacks counted, at most 15% a year), fading to the long-run "
                        "rate; the payout each year is whatever that growth leaves (clean surplus).",
                        "The implied ROE is what today's price-to-book requires in perpetuity: "
                        "g + P/B x (cost of equity - g)."],
              **analysis.versus_price(r["per_share"], price)})
    return r


def reit_model(provider, data: Dict[str, Any], ke: float, drivers: Dict[str, Any], fit: Dict[str, Any],
               over: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """Funds from operations, approximately the NAREIT definition: net income
    to common + real-estate depreciation and amortization + impairments -
    gains on property sales. Reported D&A includes a small non-property part,
    so FFO here runs slightly high. AFFO needs maintenance capex and
    straight-line rent, which the filings do not tag consistently, so it is
    not computed."""
    rows = []
    for y in data["history"]:
        f = y["flows"]
        ni, da = _v(f.get("net_income_common")), _v(f.get("da"))
        if ni is None or da is None:
            continue
        imp, gain = _v(f.get("impairment_real_estate")), _v(f.get("gain_real_estate"))
        ffo = ni + da + (imp or 0.0) - (gain or 0.0)
        sh = _v(f.get("diluted_shares_avg"))
        rows.append({"fy_end": y["fy_end"], "net_income": ni, "da": da, "impairments": imp, "gains": gain,
                     "ffo": ffo, "shares": sh, "ffo_per_share": (ffo / sh) if sh else None,
                     "dividends": _v(f.get("dividends_paid")),
                     "missing": [k for k, v in (("impairments", imp), ("gains on sale", gain)) if v is None]})
    if not rows or rows[0]["ffo_per_share"] is None:
        return {"available": False, "fit": fit, "reason": "Net income and depreciation are not both reported."}
    price = data["quote"].get("price")
    ffo_ps = rows[0]["ffo_per_share"]
    out: Dict[str, Any] = {"available": True, "fit": fit, "years": rows, "ffo_per_share": ffo_ps,
                           "price_to_ffo": (price / ffo_ps) if (price and ffo_ps > 0) else None,
                           "ffo_payout": (rows[0]["dividends"] / rows[0]["ffo"]) if rows[0]["dividends"] and rows[0]["ffo"] > 0 else None,
                           "affo": None, "affo_reason": "AFFO needs maintenance capex and straight-line rent "
                                                        "adjustments that the filings do not tag consistently."}
    # Price-to-FFO in each past fiscal year, from the average price that year.
    try:
        from ..analytics.valuation import _avg_price_in_year
        frame = provider.history(data["ticker"], period="6y", interval="1d")
        hist_m = []
        for r in rows:
            avg = _avg_price_in_year(frame, r["fy_end"])
            if avg and r["ffo_per_share"] and r["ffo_per_share"] > 0:
                r["avg_price"], r["p_ffo"] = avg, avg / r["ffo_per_share"]
                hist_m.append(r["p_ffo"])
        if len(hist_m) >= 3:
            out["own_history"] = {"median": median(hist_m), "low": min(hist_m), "high": max(hist_m),
                                  "per_share_mid": median(hist_m) * ffo_ps,
                                  "per_share_low": min(hist_m) * ffo_ps, "per_share_high": max(hist_m) * ffo_ps,
                                  "note": "Today's FFO at the multiples the market paid in each of the "
                                          "last {} fiscal years. Relative to its own history, not "
                                          "intrinsic.".format(len(hist_m))}
    except Exception:                                                                      # noqa: BLE001
        pass
    # The reader's own price-to-FFO, or the REIT's own median by default.
    mult = (over or {}).get("p_ffo") or (out.get("own_history") or {}).get("median")
    if mult:
        out["at_multiple"] = {"multiple": mult, "per_share": mult * ffo_ps,
                              "source": "reader" if (over or {}).get("p_ffo") else "own_history_median",
                              **analysis.versus_price(mult * ffo_ps, price)}
    out["edited"] = sorted(over or {})
    return out


def fcfe_model(base: Dict[str, Any], drivers: Dict[str, Any], w: Dict[str, Any], fit: Dict[str, Any],
               price: Optional[float]) -> Dict[str, Any]:
    try:
        r = engine.run_fcfe(base, drivers, w["cost_equity"], w["pre_tax_cost_debt"], w["tax_rate"],
                            w.get("weight_debt") or 0.0)
    except (engine.ModelError, KeyError) as exc:
        return {"available": False, "fit": fit, "reason": str(exc)}
    r.update({"available": True, "fit": fit, **analysis.versus_price(r["per_share"], price),
              "notes": ["New reinvestment is financed {:.0%} by debt, the discount rate's own debt weight; "
                        "losses are not borrowed against. Interest is the pre-tax cost of debt on last "
                        "year's balance.".format(w.get("weight_debt") or 0.0),
                        "Discounted at the cost of equity. The FCFF answer uses one blended rate; the "
                        "two agree only when leverage stays at its market weight."]})
    return r


# ---------------------------------------------------------------------------
# The full build
# ---------------------------------------------------------------------------

def _compact_fact(f: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if f is None:
        return None
    keep = ("value", "tag", "unit", "start", "end", "form", "filed", "url", "restated", "kind",
            "rule", "note", "reason", "retrieved", "parts", "concept", "includes_finance_leases")
    return {k: f[k] for k in keep if k in f and f[k] is not None}


def _history_table(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for y in data["history"]:
        f, b, d = y["flows"], y["balance"], y["derived"]
        rows.append({
            "fy_end": y["fy_end"],
            "facts": {k: _compact_fact(f.get(k)) for k in ("revenue", "operating_income", "pretax_income",
                                                          "income_tax", "net_income", "da", "capex", "cfo",
                                                          "sbc", "interest_expense", "dividends_paid",
                                                          "buybacks", "dps", "diluted_shares_avg")},
            "balance": {k: _compact_fact(b.get(k)) for k in ("cash", "debt", "nwc", "ppe", "equity")},
            "derived": d,
        })
    return rows


def _defaults_for(data: Dict[str, Any]) -> Dict[str, Any]:
    """Base, classification, default drivers and WACC parts. Raises
    ModelError when a DCF cannot be built from these inputs."""
    base, missing = defaults.build_base(data)
    seg_hint = False
    df = dividend_facts(data)
    kind = classify.business_type((data.get("profile") or {}).get("sic"), data["quote"].get("industry"),
                                  data["history"])
    fit = classify.suitability(kind, {**df, "has_segments": seg_hint,
                                      "short_history": len(data["history"]) < 3})
    parts = defaults.wacc_parts(data, base)
    return {"base": base, "missing": missing, "kind": kind, "fit": fit, "parts": parts, "dividends": df}


# Base-year lines a reader may supply when the SEC facts lack them (a filer
# that tags them with its own extension, as NextEra does capex). Each is
# labelled as the reader's and links to the filing to read it from.
SUPPLIABLE = {"operating_income": "Operating income (EBIT)", "capex": "Capital expenditure",
              "da": "Depreciation and amortization"}


def supply_missing(data: Dict[str, Any], given: Optional[Dict[str, Any]]) -> Tuple[Dict[str, Any], List[str]]:
    """Put reader-supplied base-year figures into a copy of the inputs, only
    for lines the filings do not report, and recompute the ratios."""
    if not isinstance(given, dict) or not given or not data.get("history"):
        return data, []
    errors: List[str] = []
    out = copy.deepcopy(data)
    fy0 = out["history"][0]
    used = []
    for key, raw in given.items():
        if key not in SUPPLIABLE or raw in (None, ""):
            continue
        if _v(fy0["flows"].get(key)) is not None:
            errors.append("{} is already in the filings, so it is not replaced.".format(SUPPLIABLE[key]))
            continue
        try:
            x = float(raw)
        except (TypeError, ValueError):
            errors.append("{} is not a number.".format(SUPPLIABLE[key]))
            continue
        if x != x or (key != "operating_income" and x < 0) or abs(x) > 1e14:
            errors.append("{} is out of range.".format(SUPPLIABLE[key]))
            continue
        fy0["flows"][key] = {"concept": key, "value": x, "kind": "reader", "end": fy0["fy_end"],
                             "note": "Entered by the reader from the filing; the SEC facts do not carry it."}
        used.append(key)
    if errors:
        raise InputError(errors)
    inputs.derive(out["history"])
    return out, used


def suggestions(data: Dict[str, Any], concept: str) -> Dict[str, Any]:
    fy0 = data["history"][0]
    start = next((f.get("start") for f in fy0["flows"].values() if f and f.get("start") and f.get("tag")), None)
    if not start:
        return {"available": False, "reason": "The fiscal year's start date is not known."}
    try:
        return inputs.extension_candidates(data["ticker"], concept, start, fy0["fy_end"])
    except Exception as exc:                                                               # noqa: BLE001
        return {"available": False, "reason": "Could not read the filing ({}).".format(type(exc).__name__)}


def build(provider, ticker: str, edits: Optional[Dict[str, Any]] = None,
          force: bool = False, light: bool = False) -> Dict[str, Any]:
    data = gathered(provider, ticker, force=force)
    if not data.get("available"):
        return {"available": False, "ticker": ticker.upper(), "reason": data.get("reason"),
                "model_version": MODEL_VERSION}
    try:
        data, supplied = supply_missing(data, (edits or {}).get("base"))
    except InputError as exc:
        return {"available": False, "input_errors": exc.errors, "ticker": data["ticker"],
                "model_version": MODEL_VERSION}
    prep = _defaults_for(data)
    base, kind, fit, parts0 = prep["base"], prep["kind"], prep["fit"], prep["parts"]
    out: Dict[str, Any] = {
        "available": True, "model_version": MODEL_VERSION, "ticker": data["ticker"], "name": data["name"],
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "valuation_date": data["valuation_date"],
        "market": {"price": data["quote"]["price"], "as_of": data["quote"]["as_of"],
                   "market_time": data["quote"].get("market_time"),
                   "currency": data["quote"]["currency"], "source": data["quote"]["source"],
                   "market_cap": data["quote"]["market_cap"]},
        "classification": fit,
        "inputs": {
            "fy_ends": data["fy_ends"], "balance_date": data["balance_date"], "history": _history_table(data),
            "bridge": {k: _compact_fact(data["balance"].get(k)) for k in BRIDGE_KEYS},
            "operating_lease": _compact_fact(data["balance"].get("operating_lease")),
            "shares": {k: (_compact_fact(v) if isinstance(v, dict) else v) for k, v in data["shares"].items()},
            "risk_free": data["risk_free"], "consensus": data["consensus"], "quote": data["quote"],
            "trailing": {k: (v if k != "values" else {c: _compact_fact(f) for c, f in v.items()})
                         for k, v in (data.get("trailing") or {}).items()},
            "profile": data["profile"], "retrieved": data["retrieved"], "source_note": data["source_note"],
            "statement_currency": data["statement_currency"], "cik": data["cik"],
        },
        "warnings": list(data["warnings"]),
        "dividends": prep["dividends"],
        # The reported numbers the engine ran on, and their dates: what a saved
        # snapshot stores so it can be replayed exactly.
        "base": base,
        "inputs_digest": {"fy0_end": base["fy0_end"], "balance_date": base["balance_date"],
                          "filings_retrieved": data["retrieved"], "price": data["quote"]["price"],
                          "price_as_of": data["quote"]["as_of"],
                          "risk_free_as_of": (data.get("risk_free") or {}).get("as_of"),
                          "valuation_date": data["valuation_date"]},
    }
    out["supplied"] = supplied
    if prep["missing"] and kind not in ("bank", "insurer"):
        fy0 = data["history"][0]
        can_supply = [k for k in SUPPLIABLE if _v(fy0["flows"].get(k)) is None]
        out["dcf"] = {"available": False, "reason": "The filings are missing: {}. Nothing is filled in "
                      "with a guess, so the DCF is not run.{}".format(
                          ", ".join(prep["missing"]),
                          " " + fit["models"]["dcf"]["why"] if kind == "reit" else ""),
                      "missing": can_supply, "missing_labels": {k: SUPPLIABLE[k] for k in can_supply},
                      "suggestions": {k: suggestions(data, k) for k in can_supply} if not light else {},
                      "filing_url": (fy0["flows"].get("revenue") or {}).get("url"), "fy0_end": fy0["fy_end"]}
    # Discount-rate defaults first: RONIC and scenarios depend on it.
    try:
        w0 = defaults.compute_wacc(parts0, base)
    except engine.ModelError as exc:
        out["wacc_error"] = str(exc)
        w0 = None
    out["wacc_parts_default"] = parts0

    financial = kind in ("bank", "insurer")
    can_dcf = not prep["missing"] and not financial
    if can_dcf:
        w_def = w0
        if w_def is None and isinstance((edits or {}).get("wacc"), dict):
            # The feeds lacked a part of the rate (a beta, say) and the reader
            # supplied it: the defaults that depend on the rate are then the
            # ones the feeds would have given.
            try:
                _, p_try, _ = merge({}, parts0, {"wacc": edits["wacc"]})
                w_def = defaults.compute_wacc(p_try, base)
            except (InputError, engine.ModelError):
                w_def = None
        try:
            d0, why = defaults.default_drivers(data, base, kind, w_def["wacc"] if w_def else None)
        except Exception as exc:                                                           # noqa: BLE001
            d0, why = None, []
            out["dcf"] = {"available": False, "reason": "Defaults could not be built ({}).".format(exc)}
        if d0 is not None:
            out["defaults"] = {"drivers": d0, "wacc": parts0, "rationale": why}
            try:
                drivers, parts, changed = merge(d0, parts0, edits)
            except InputError as exc:
                return {"available": False, "input_errors": exc.errors, "ticker": data["ticker"],
                        "model_version": MODEL_VERSION}
            out["assumptions"] = {"drivers": drivers, "wacc": parts, "changed": changed}
            try:
                # The reader's discount-rate parts can supply what the feeds
                # lacked (a beta, a risk-free rate), so the rate is built from
                # the merged parts, not the defaults.
                try:
                    w = defaults.compute_wacc(parts, base)
                except engine.ModelError as exc:
                    # A missing input, not an impossible combination: the
                    # page asks for it.
                    raise NeedsInput(str(exc))
                if drivers["terminal"].get("ronic") is None:
                    drivers["terminal"]["ronic"] = w["wacc"]
                    if out["defaults"]["drivers"]["terminal"].get("ronic") is None:
                        out["defaults"]["drivers"]["terminal"]["ronic"] = w["wacc"]
                res = analysis.run_case(base, drivers, parts)
                out["dcf"] = dict(res, available=True)
                rate = res["wacc"]["wacc"]
                if not light:
                    cases = defaults.scenario_drivers(drivers, rate)
                    out["scenarios"] = analysis.scenarios(base, cases, rate)
                    out["scenario_text"] = defaults.SCENARIO_TEXT
                    out["sensitivity"] = analysis.sensitivity(base, drivers, rate)
                    out["tornado"] = analysis.tornado(base, drivers, rate, res["per_share"])
                    out["reverse"] = analysis.reverse_dcf(base, drivers, rate)
                    out["what_ifs"] = what_ifs(base, drivers, rate, res["per_share"], data)
                    out["fcfe"] = fcfe_model(base, drivers, res["wacc"], fit["models"]["fcfe"],
                                             base.get("price"))
                    out["three_statement"] = three_statement_model(base, drivers, res["wacc"], data)
            except NeedsInput as exc:
                out["dcf"] = {"available": False, "reason": str(exc), "needs_input": True}
            except engine.ModelError as exc:
                out["dcf"] = {"available": False, "reason": str(exc), "invalid": True}
    elif "dcf" not in out:
        out["dcf"] = {"available": False, "reason": fit["models"]["dcf"]["why"] if financial else
                      (out.get("wacc_error") or "The DCF could not be run.")}

    # Equity-side models that do not depend on the FCFF forecast. They need
    # only the cost of equity, which a bank has even when a blended rate
    # (and a synthetic credit rating from operating income) does not apply.
    try:
        eq_over = equity_edits(edits)
    except InputError as exc:
        return {"available": False, "input_errors": exc.errors, "ticker": data["ticker"],
                "model_version": MODEL_VERSION}
    eq_parts = (out.get("assumptions") or {}).get("wacc")
    if eq_parts is None:
        try:
            _, eq_parts, _ = merge({}, parts0, {"wacc": (edits or {}).get("wacc") or {}})
        except InputError as exc:
            return {"available": False, "input_errors": exc.errors, "ticker": data["ticker"],
                    "model_version": MODEL_VERSION}
    out["equity_wacc_parts"] = eq_parts
    try:
        ke_parts = defaults.equity_cost(eq_parts)
    except engine.ModelError as exc:
        ke_parts = None
        out["cost_of_equity_error"] = str(exc)
    if ke_parts is not None and not light:
        ke = ke_parts["cost_equity"]
        out["cost_of_equity_parts"] = ke_parts
        g = (out.get("assumptions") or {}).get("drivers", {}).get("terminal", {}).get("growth", defaults.TERMINAL_GROWTH)
        if fit["models"]["residual_income"]["fit"] != "not_applicable":
            out["residual_income"] = residual_income_model(data, ke, g, fit["models"]["residual_income"],
                                                           eq_over.get("ri"))
        if kind == "reit":
            drivers_for = (out.get("assumptions") or {}).get("drivers") or {
                "growth": {"y1": 0.03, "y2": None}, "terminal": {"growth": g}, "horizon": 10}
            out["reit"] = reit_model(provider, data, ke, drivers_for, fit["models"]["reit_ffo"], eq_over.get("reit"))
        if fit["models"]["ddm"]["fit"] != "not_applicable":
            drivers_for = (out.get("assumptions") or {}).get("drivers") or {
                "growth": {"y1": defaults.TERMINAL_GROWTH + 0.01, "y2": None},
                "terminal": {"growth": g}, "horizon": 10}
            out["ddm"] = ddm_model(data, drivers_for, ke, fit["models"]["ddm"], eq_over.get("ddm"))
        out["cost_of_equity"] = ke
    return out


def three_statement_model(base: Dict[str, Any], drivers: Dict[str, Any], w: Dict[str, Any],
                          data: Dict[str, Any]) -> Dict[str, Any]:
    if not base.get("balance_sheet"):
        return {"available": False, "reason": "The balance sheet is not split into current and "
                                              "non-current items, so a linked forecast cannot start."}
    df = dividend_facts(data)
    rf = base.get("risk_free") or 0.0
    policy = {"interest_rate_debt": w.get("pre_tax_cost_debt") or rf, "interest_rate_cash": max(0.0, rf - 0.01),
              "payout_ratio": min(1.0, max(0.0, df["payout_ratio"] or 0.0)),
              "buyback_ratio": min(1.5, max(0.0, df["buyback_ratio"] or 0.0)),
              "min_cash": 0.02 * base["revenue"], "debt_policy": "flat"}
    try:
        r = engine.three_statement(base, drivers, policy)
    except engine.ModelError as exc:
        return {"available": False, "reason": str(exc)}
    sheltered = any((y.get("pretax_income") or 0) < 0 for y in r["years"]) or (base.get("nol") or 0) > 0
    r["reconciles_with_dcf"] = all(abs(y["fcff_from_statements"] - y["fcff_dcf"]) <= 1e-6 * base["revenue"]
                                   for y in r["years"])
    if not r["reconciles_with_dcf"] and sheltered:
        r["reconcile_note"] = ("Free cash flow from the statements differs from the DCF's in loss years: "
                               "the statements shelter pre-tax income (after interest), the DCF shelters "
                               "operating income, so carried-forward losses are used at different times.")
    r.update({"available": True, "policy": policy, "start": base["balance_sheet"],
              "notes": ["Condensed: operating current assets keep their share of revenue, PP&E rolls "
                        "forward, other assets and liabilities and long-term investments are held flat.",
                        "Debt is held flat; if payouts would push cash below 2% of revenue, buybacks "
                        "are cut first, then dividends, then a revolver is drawn.",
                        "Interest on debt at the pre-tax cost of debt, on cash at the risk-free rate "
                        "less one point. Full fiscal years: no stub.",
                        "The DCF does not use this forecast for value; it shows the financing the "
                        "operating plan implies and checks that the statements balance."]})
    return r


# ---------------------------------------------------------------------------
# Comparable companies (separate request: it reads several other companies)
# ---------------------------------------------------------------------------

COMPS_MULTIPLES = (
    # key, label, Yahoo info field for the peer multiple, target metric field, equity multiple?
    ("ev_ebitda", "EV / EBITDA", "enterpriseToEbitda", "ebitda", False),
    ("ev_revenue", "EV / revenue", "enterpriseToRevenue", "totalRevenue", False),
    ("pe", "Price / earnings", "trailingPE", "trailingEps", True),
    ("pb", "Price / book", "priceToBook", "bookValue", True),
)
MAX_PEERS = 8


def default_peers(provider, sym: str, n: int = 25, level: str = "industry") -> List[str]:
    """The largest companies in the same Yahoo industry (or sector), by
    market weight."""
    try:
        info = provider._info(sym) or {}                                                  # noqa: SLF001
        key = info.get("industryKey" if level == "industry" else "sectorKey")
        if not key:
            return []
        import yfinance as yf
        top = (yf.Industry(key) if level == "industry" else yf.Sector(key)).top_companies
        if top is None or top.empty:
            return []
        return [str(s).upper() for s in top.index if str(s).upper() != sym][:n]
    except Exception:                                                                      # noqa: BLE001
        return []


SIZE_BAND = 25.0          # default peers within 25x of the company's market value, either way
DISPERSION_FLAG = 2.0     # 75th / 25th percentile multiple above this: peers disagree widely


def _fences(values: List[float]) -> Tuple[float, float]:
    """Tukey fences on the log of the multiples: a multiple far outside the
    middle half (a company priced on hope, or on a collapsed year) is set
    aside rather than allowed to set the median's neighbours."""
    import math as _m
    logs = sorted(_m.log(v) for v in values)
    q1, q3 = engine.percentile(logs, 0.25), engine.percentile(logs, 0.75)
    iqr = q3 - q1
    return _m.exp(q1 - 1.5 * iqr), _m.exp(q3 + 1.5 * iqr)


def comps(provider, ticker: str, peers: Optional[List[str]] = None) -> Dict[str, Any]:
    """Peer multiples and the per-share values they imply for this company.

    Peers and target are read from one source (Yahoo Finance trailing twelve
    months), so a multiple and the metric it is applied to are defined the
    same way. An enterprise multiple becomes equity value using that source's
    own net debt (its enterprise value less market value), not the SEC
    bridge, for the same reason.

    Default peers are the industry's largest companies within a size band of
    this one, the eight closest in size. For each multiple only peers with a
    positive figure count, and outliers beyond Tukey fences are set aside and
    named. When the peers' 25th and 75th percentiles are more than 2x apart,
    the comparison is flagged: it then says more about which peers were chosen
    than about this company. Market-relative throughout."""
    from concurrent.futures import ThreadPoolExecutor
    import math as _m
    sym = ticker.upper().strip()
    chosen = [p.upper().strip() for p in (peers or []) if p and p.strip()][:MAX_PEERS]
    source = "reader" if chosen else "industry"
    candidates = chosen or default_peers(provider, sym)
    sector: List[str] = []
    if not chosen:
        # A company that dominates its own industry (Microsoft is most of
        # Yahoo's "software infrastructure") has few peers of its size there;
        # the sector's largest fill in, labelled as sector peers.
        sector = [p for p in default_peers(provider, sym, level="sector") if p not in candidates]
        candidates = candidates + sector
    if not candidates:
        return {"available": False, "reason": "No peer list: the quote feed gives no industry for {}, "
                                              "and none was entered.".format(sym)}

    def info(s: str) -> Dict[str, Any]:
        try:
            return provider._info(s) or {}                                                # noqa: SLF001
        except Exception:                                                                  # noqa: BLE001
            return {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        infos = dict(zip([sym] + candidates, pool.map(info, [sym] + candidates)))
    me = infos.get(sym) or {}
    price = _num(me.get("currentPrice") or me.get("regularMarketPrice"))
    mcap, ev = _num(me.get("marketCap")), _num(me.get("enterpriseValue"))
    if not (price and mcap):
        return {"available": False, "reason": "The quote feed returned no price or market value for {} "
                                              "just now, so its multiples cannot be compared.".format(sym)}
    shares = mcap / price
    net_debt = (ev - mcap) if ev is not None else None
    rows, excluded = [], []
    for p in candidates:
        i = infos.get(p) or {}
        pm = _num(i.get("marketCap"))
        row = {"symbol": p, "name": i.get("shortName") or i.get("longName"), "market_cap": pm,
               "origin": "reader" if chosen else ("sector" if p in sector else "industry"),
               **{k: _num(i.get(field)) for k, _, field, _, _ in COMPS_MULTIPLES}}
        if not pm:
            excluded.append(dict(row, why="no market value in the feed"))
        elif source == "industry" and not (mcap / SIZE_BAND <= pm <= mcap * SIZE_BAND):
            if row["origin"] == "industry":
                excluded.append(dict(row, why="outside {:g}x of {}'s size".format(SIZE_BAND, sym)))
        else:
            rows.append(row)
    if source == "industry":
        # Industry peers first, nearest in size; sector peers only to bring
        # the set up to five, and never past eight.
        ind = sorted([r for r in rows if r["origin"] == "industry"], key=lambda r: abs(_m.log(r["market_cap"] / mcap)))
        sec = sorted([r for r in rows if r["origin"] == "sector"], key=lambda r: abs(_m.log(r["market_cap"] / mcap)))
        keep = ind[:MAX_PEERS]
        if len(keep) < 5:
            keep = keep + sec[:5 - len(keep)]
        kept_ids = {r["symbol"] for r in keep}
        for r in rows:
            if r["symbol"] not in kept_ids and r["origin"] == "industry":
                excluded.append(dict(r, why="further in size than the eight closest"))
        rows = keep
        source = "industry" if not any(r["origin"] == "sector" for r in rows) else "industry_and_sector"
    implied, flags = [], []
    for key, label, field, metric_field, equity in COMPS_MULTIPLES:
        metric = _num(me.get(metric_field))
        positive = [(r["symbol"], r[key]) for r in rows if r[key] is not None and r[key] > 0]
        outliers: List[str] = []
        if len(positive) >= 4:
            lo, hi = _fences([v for _, v in positive])
            outliers = [s for s, v in positive if not (lo <= v <= hi)]
            positive = [(s, v) for s, v in positive if lo <= v <= hi]
        mults = [v for _, v in positive]
        val = engine.comps_value(metric, mults, True, {}, 1.0)
        if val and not equity:
            if net_debt is None:
                val = None
            else:
                for lvl in ("low", "mid", "high"):
                    val[lvl]["per_share"] = (val[lvl]["per_share"] - net_debt) / shares
        spread = (val["high"]["multiple"] / val["low"]["multiple"]) if val and val["low"]["multiple"] > 0 else None
        wide = bool(spread and spread > DISPERSION_FLAG)
        own = _num(me.get(field))
        note = None
        if val and own and own > 0:
            ratio = own / val["mid"]["multiple"]
            if ratio < 0.5 or ratio > 2.0:
                note = ("{} trades at {:.1f}x against a peer median of {:.1f}x. A gap that large usually means the "
                        "peers are priced for different growth or margins, so the implied value mostly reflects "
                        "the peer choice.".format(sym, own, val["mid"]["multiple"]))
        implied.append({"key": key, "label": label, "metric": metric, "own_multiple": own,
                        "peers_with_value": len(mults), "outliers": outliers, "implied": val,
                        "spread": spread, "wide": wide, "note": note,
                        "reason": None if val else ("Fewer than three peers have a positive {}, or {}'s own "
                                                    "figure is missing or negative.".format(label, sym))})
        if wide:
            flags.append("{}: peers' 25th and 75th percentiles are {:.1f}x apart.".format(label, spread))
    return {"available": True, "ticker": sym, "peers": rows, "excluded": excluded, "peer_source": source,
            "implied": implied, "flags": flags, "price": price, "net_debt": net_debt, "shares": shares,
            "market_cap": mcap,
            "source": "Yahoo Finance, trailing twelve months, for the company and each peer",
            "note": ("Market-relative: what the company would be worth at its peers' multiples. If the "
                     "whole group is mispriced, so is this.")}


def _num(value: Any) -> Optional[float]:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if x == x and x not in (float("inf"), float("-inf")) else None


def clean(obj: Any) -> Any:
    """JSON-safe: non-finite floats become None (a JSON response refuses NaN)."""
    if isinstance(obj, float):
        return obj if (obj == obj and obj not in (float("inf"), float("-inf"))) else None
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean(v) for v in obj]
    return obj


def what_ifs(base: Dict[str, Any], drivers: Dict[str, Any], rate: float, center: float,
             data: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """A few single-assumption alternatives the reader (and Milo) commonly
    ask about, each a full model run with only that change."""
    out: List[Dict[str, Any]] = []

    def add(key: str, label: str, d: Dict[str, Any], w: float = rate) -> None:
        v = analysis.per_share(base, d, w)
        out.append({"key": key, "label": label, "per_share": v,
                    "change": (v / center - 1.0) if (v is not None and center) else None})
    c = drivers["capex_pct"]
    if abs(c["start"] - c["target"]) > 1e-6:
        d = copy.deepcopy(drivers)
        d["capex_pct"]["target"] = c["start"]
        add("capex_stays", "Capex stays at last year's {:.1%} of revenue instead of easing to {:.1%}".format(
            c["start"], c["target"]), d)
    m = drivers["margin"]
    if abs(m["start"] - m["target"]) > 1e-6:
        d = copy.deepcopy(drivers)
        d["margin"]["target"] = m["start"]
        add("margin_holds", "Operating margin holds at last year's {:.1%} instead of {:.1%}".format(
            m["start"], m["target"]), d)
    if data:
        norms = [y["derived"].get("ebit_margin_normalized") for y in data["history"][:3]]
        norms = [x for x in norms if x is not None]
        if norms and abs(mean(norms) - m["target"]) > 0.005:
            d = copy.deepcopy(drivers)
            d["margin"]["target"] = mean(norms)
            add("margin_normalized", "Margins settle at the three-year average excluding tagged restructuring and "
                "impairment charges ({:.1%})".format(mean(norms)), d)
    d = copy.deepcopy(drivers)
    d["terminal"]["ronic"] = rate
    add("no_excess_returns", "New investment after the forecast earns only the cost of capital", d)
    add("wacc_plus_1", "Discount rate one point higher ({:.1%})".format(rate + 0.01), copy.deepcopy(drivers), rate + 0.01)
    return out


# ---------------------------------------------------------------------------
# Sum of the parts (separate request: it reads filing instance documents)
# ---------------------------------------------------------------------------

UNALLOCATED_WORDS = ("corporate", "non segment", "nonsegment", "elimination", "reconcil",
                     "unallocated", "other operating", "intersegment")


def _consecutive(quarters: List[str]) -> bool:
    from datetime import date as _date
    try:
        ds = [_date.fromisoformat(q[:10]) for q in quarters]
    except ValueError:
        return False
    gaps = [(b - a).days for a, b in zip(ds, ds[1:])]
    return len(ds) == 4 and all(80 <= g <= 100 for g in gaps)


def sotp_model(provider, ticker: str, multiples: Optional[Dict[str, Any]] = None,
               unallocated_multiple: Optional[float] = None,
               edits: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Each reported segment's trailing-twelve-month operating income at a
    multiple the reader chooses, less capitalised unallocated costs, through
    the same bridge as the DCF.

    Only four consecutive reported quarters make a trailing year: a missing
    quarter is not filled in, and a single quarter is not annualised (segments
    are seasonal). Until the reader enters multiples, every segment starts at
    the DCF's own implied EV / EBIT, which reproduces the whole-company value
    and is there to be changed."""
    from ..analytics import segments as segments_mod
    sym = ticker.upper().strip()
    seg = segments_mod.build(sym)
    if not seg.get("available"):
        return {"available": False, "reason": seg.get("reason") or "No segment data in the filings."}
    table = next((t for t in seg.get("tables") or []
                  if t.get("metric") == "operating_income" and "segment" in str(t.get("axis", "")).lower()), None)
    if not table:
        return {"available": False, "reason": "The filings report revenue by segment but not operating income, "
                                              "so segments cannot be valued on earnings."}
    data = gathered(provider, sym)
    if not data.get("available"):
        return {"available": False, "reason": data.get("reason")}
    fy0 = data["fy_ends"][0] if data.get("fy_ends") else None
    # The fiscal year the DCF starts from, as the 10-K reports it by segment:
    # same period as the company's EBIT, so the parts reconcile to the whole.
    # Four consecutive quarters are the fallback when that 10-K is not read.
    annual = table.get("annual") or {}
    ends = list(annual.get("ends") or [])
    col = None
    if fy0:
        for i, e in enumerate(ends):
            if abs((date.fromisoformat(e[:10]) - date.fromisoformat(fy0[:10])).days) <= 10:
                col = i
    period_note = None
    if col is not None:
        picked = [(r.get("member"), (r.get("values") or [None] * len(ends))[col]) for r in annual.get("rows") or []]
        period = {"kind": "fiscal_year", "end": ends[col]}
    else:
        quarters = list(seg.get("quarters") or [])
        if len(quarters) < 4 or not _consecutive(quarters[-4:]):
            return {"available": False, "reason": "Neither the fiscal year the model starts from ({}) nor four "
                    "consecutive quarters of segment operating income have been read from the filings yet "
                    "(quarters read: {}). One quarter is not annualised, because segments are seasonal."
                    .format(fy0, ", ".join(quarters[-4:]) or "none"),
                    "quarters": quarters, "filings_unread": seg.get("filings_unread")}
        picked = []
        for r in table.get("rows") or []:
            vals = (r.get("values") or [])[-4:]
            picked.append((r.get("member"), None if len(vals) < 4 or any(v is None for v in vals) else float(sum(vals))))
        period = {"kind": "trailing_four_quarters", "end": quarters[-1], "quarters": quarters[-4:]}
        period_note = "The base fiscal year's 10-K has not been read by segment yet, so the last four quarters are used."
    # A subtotal or total tagged as a member (Coca-Cola's "Material
    # Reconciling Items" equals the sum of its segments) is dropped: added in,
    # it doubles the parts.
    seg_vals = [float(v) for n, v in picked if v is not None
                and not any(w in str(n or "").lower() for w in UNALLOCATED_WORDS)]
    ebit_fy0 = (data["history"][0]["flows"].get("operating_income") or {}).get("value")
    dropped = []
    kept_rows = []
    for name, value in picked:
        if value is not None and seg_vals:
            others = sum(seg_vals) - (float(value) if value in seg_vals else 0.0)
            is_total = (abs(float(value) - others) <= 0.005 * max(abs(others), 1.0) and others != 0) or (
                ebit_fy0 and period["kind"] == "fiscal_year" and abs(float(value) - ebit_fy0) <= 0.005 * abs(ebit_fy0)
                and len(picked) > 2)
            if is_total:
                dropped.append(str(name))
                continue
        kept_rows.append((name, value))
    picked = kept_rows
    rows, unallocated = [], 0.0
    for name, value in picked:
        name = str(name or "")
        if value is None:
            rows.append({"name": name, "operating_income": None, "note": "not reported for this period"})
            continue
        if any(w in name.lower() for w in UNALLOCATED_WORDS):
            unallocated += float(value)
            continue
        rows.append({"name": name, "operating_income": float(value)})
    if not any(r.get("operating_income") is not None for r in rows):
        return {"available": False, "reason": "No segment reports operating income for {}.".format(period["end"])}
    base, _ = defaults.build_base(data)
    # The reader's current assumptions, so the starting multiple is the one
    # implied by the model on their screen, not the defaults.
    full = build(provider, sym, edits=edits, light=True)
    dcf = full.get("dcf") or {}
    implied = (dcf["enterprise_value"] / base["ebit"]) if dcf.get("available") and base.get("ebit") else None
    m_in = multiples if isinstance(multiples, dict) else {}
    for r in rows:
        raw = m_in.get(r["name"])
        try:
            r["multiple"] = float(raw) if raw is not None and raw != "" else implied
        except (TypeError, ValueError):
            r["multiple"] = implied
        r["multiple_source"] = "reader" if r["name"] in m_in and m_in.get(r["name"]) not in (None, "") else "dcf_implied"
    um = unallocated_multiple if unallocated_multiple is not None else implied
    if um is None or not base.get("shares"):
        return {"available": False, "reason": "No multiple to start from: the DCF did not run, so enter a "
                                              "multiple for each segment."}
    res = engine.sotp(rows, unallocated, float(um), base["bridge"], base["shares"])
    seg_sum = sum(r["operating_income"] for r in rows if r.get("operating_income") is not None) + unallocated
    if dropped:
        period_note = ((period_note + " ") if period_note else "") + (
            "Dropped as a total rather than a part: {}.".format(", ".join(dropped)))
    res.update({"available": True, "period": period, "period_note": period_note,
                "quarters": period.get("quarters"), "axis_label": table.get("axis_label"),
                "dcf_implied_ev_ebit": implied, "segments_ttm_total": seg_sum,
                "company_ebit_fy0": base.get("ebit"), "q4_derived": seg.get("q4_derived"),
                "price": data["quote"].get("price"),
                **analysis.versus_price(res.get("per_share"), data["quote"].get("price")),
                "source": "Segment operating income from the filings' XBRL instances (SEC EDGAR)",
                "reconciles": (abs(seg_sum / base["ebit"] - 1.0) <= 0.02) if (base.get("ebit") and period["kind"] == "fiscal_year") else None,
                "note": ("Operating income by segment as the company reports it for {}. Corporate costs and "
                         "eliminations are valued at the unallocated multiple, as a negative. The segments plus "
                         "those items should add up to the company's operating income for the same year."
                         .format("the fiscal year ended " + period["end"] if period["kind"] == "fiscal_year"
                                 else "the four quarters to " + period["end"]))})
    return res
