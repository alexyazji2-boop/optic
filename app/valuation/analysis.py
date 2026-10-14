"""Scenarios, sensitivities and the reverse DCF, all by re-running the engine.

Nothing here approximates. Every number in a sensitivity table or a tornado
bar is a full model run with one or two assumptions changed, so it agrees with
what the reader sees after typing the same change into the form.
"""

from __future__ import annotations

import copy
from typing import Any, Callable, Dict, List, Optional

from . import engine
from .defaults import compute_wacc


def per_share(base: Dict[str, Any], drivers: Dict[str, Any], rate: float) -> Optional[float]:
    try:
        return engine.run_dcf(base, drivers, rate)["per_share"]
    except engine.ModelError:
        return None


def versus_price(value: Optional[float], price: Optional[float]) -> Dict[str, Any]:
    """Two different quantities, defined separately:

    upside           = value / price - 1   (how far the price would move to reach the value)
    margin of safety = 1 - price / value   (how much of the value the price leaves as a cushion;
                                            only defined when the value is positive)"""
    out: Dict[str, Any] = {"upside": None, "margin_of_safety": None}
    if value is None or not price:
        return out
    out["upside"] = value / price - 1.0
    if value > 0:
        out["margin_of_safety"] = 1.0 - price / value
    return out


def scenarios(base: Dict[str, Any], cases: Dict[str, Dict[str, Any]], rate: float) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for name, drivers in cases.items():
        d = {k: v for k, v in drivers.items() if not k.startswith("_")}
        try:
            r = engine.run_dcf(base, d, rate)
            out[name] = {"per_share": r["per_share"], "enterprise_value": r["enterprise_value"],
                         "terminal_share": r["terminal_share"], "drivers": d,
                         "deltas": drivers.get("_deltas"),
                         "errors": [c for c in r["checks"] if c["level"] == "error"],
                         **versus_price(r["per_share"], base.get("price"))}
        except engine.ModelError as exc:
            out[name] = {"per_share": None, "error": str(exc), "drivers": d}
    return out


def grid(base: Dict[str, Any], drivers: Dict[str, Any], rate: float,
         rows: List[float], cols: List[float],
         apply: Callable[[Dict[str, Any], float, float, float], tuple]) -> List[List[Optional[float]]]:
    """A table of per-share values; `apply(drivers, rate, row, col)` returns
    the (drivers, rate) to run for that cell. Invalid cells are None."""
    table: List[List[Optional[float]]] = []
    for r in rows:
        line: List[Optional[float]] = []
        for c in cols:
            d, w = apply(copy.deepcopy(drivers), rate, r, c)
            line.append(per_share(base, d, w))
        table.append(line)
    return table


def sensitivity(base: Dict[str, Any], drivers: Dict[str, Any], rate: float) -> Dict[str, Any]:
    g0 = drivers["terminal"]["growth"]
    w_steps = [-0.01, -0.005, 0.0, 0.005, 0.01]
    g_steps = [-0.01, -0.005, 0.0, 0.005, 0.01]

    def wg(d, w, dw, dg):
        d["terminal"]["growth"] = g0 + dg
        return d, w + dw
    m0 = drivers["margin"]["target"]
    m_steps = [-0.04, -0.02, 0.0, 0.02, 0.04]
    gr_steps = [-0.04, -0.02, 0.0, 0.02, 0.04]

    def mg(d, w, dm, dgr):
        d["margin"]["target"] = m0 + dm
        d["growth"]["y1"] = d["growth"]["y1"] + dgr
        if d["growth"].get("y2") is not None:
            d["growth"]["y2"] = d["growth"]["y2"] + dgr
        return d, w
    c0 = drivers["capex_pct"]["target"]
    c_steps = [-0.04, -0.02, 0.0, 0.02, 0.04]

    def cw(d, w, dc, dw):
        d["capex_pct"]["target"] = max(0.0, c0 + dc)
        return d, w + dw
    return {
        "wacc_growth": {"rows": [rate + x for x in w_steps], "cols": [g0 + x for x in g_steps],
                        "row_label": "Discount rate (WACC)", "col_label": "Terminal growth",
                        "values": grid(base, drivers, rate, w_steps, g_steps, wg)},
        "margin_growth": {"rows": [m0 + x for x in m_steps], "cols": gr_steps,
                          "row_label": "Target operating margin", "col_label": "Revenue growth, every year (change)",
                          "values": grid(base, drivers, rate, m_steps, gr_steps, mg)},
        "capex_wacc": {"rows": [max(0.0, c0 + x) for x in c_steps], "cols": [rate + x for x in w_steps],
                       "row_label": "Target capex (share of revenue)", "col_label": "Discount rate (WACC)",
                       "values": grid(base, drivers, rate, c_steps, w_steps, cw)},
    }


TORNADO = (
    # key, label, low change, high change, how to apply
    ("wacc", "Discount rate", -0.01, 0.01),
    ("terminal_growth", "Terminal growth", -0.005, 0.005),
    ("margin", "Target operating margin", -0.02, 0.02),
    ("growth", "Revenue growth (every year)", -0.02, 0.02),
    ("capex", "Target capex share of revenue", -0.02, 0.02),
    ("ronic", "Return on new capital (terminal)", -0.02, 0.02),
    ("tax", "Long-run tax rate", -0.03, 0.03),
    ("nwc", "Working capital share of revenue", -0.03, 0.03),
)


def _apply(key: str, d: Dict[str, Any], w: float, x: float):
    if key == "wacc":
        return d, w + x
    if key == "terminal_growth":
        d["terminal"]["growth"] += x
    elif key == "margin":
        d["margin"]["target"] += x
    elif key == "growth":
        d["growth"]["y1"] += x
        if d["growth"].get("y2") is not None:
            d["growth"]["y2"] += x
    elif key == "capex":
        d["capex_pct"]["target"] = max(0.0, d["capex_pct"]["target"] + x)
    elif key == "ronic":
        d["terminal"]["ronic"] = max(0.01, d["terminal"]["ronic"] + x)
    elif key == "tax":
        d["tax"]["terminal"] += x
    elif key == "nwc":
        d["nwc_pct"] += x
    return d, w


def tornado(base: Dict[str, Any], drivers: Dict[str, Any], rate: float, center: float) -> List[Dict[str, Any]]:
    """Per-share value with each assumption moved down and up by a stated
    step, the others held. Ranked by the size of the swing."""
    bars: List[Dict[str, Any]] = []
    for key, label, lo, hi in TORNADO:
        if key == "ronic" and drivers["terminal"].get("method") != "value_driver":
            continue
        d_lo, w_lo = _apply(key, copy.deepcopy(drivers), rate, lo)
        d_hi, w_hi = _apply(key, copy.deepcopy(drivers), rate, hi)
        v_lo, v_hi = per_share(base, d_lo, w_lo), per_share(base, d_hi, w_hi)
        if v_lo is None or v_hi is None:
            continue
        bars.append({"key": key, "label": label, "step_low": lo, "step_high": hi,
                     "value_low": v_lo, "value_high": v_hi,
                     "swing": abs(v_hi - v_lo), "center": center})
    bars.sort(key=lambda b: -b["swing"])
    return bars


def reverse_dcf(base: Dict[str, Any], drivers: Dict[str, Any], rate: float) -> Dict[str, Any]:
    """What today's price implies, one assumption at a time.

    Many combinations explain the same price, so each solve moves exactly one
    thing and says what was held fixed."""
    price = base.get("price")
    out: Dict[str, Any] = {"price": price, "solves": []}
    if not price:
        out["reason"] = "No market price."
        return out
    held_all = "the discount rate, terminal growth, margins, capex, working capital and taxes"

    def growth_shift(x: float) -> Optional[float]:
        d = copy.deepcopy(drivers)
        d["growth"]["y1"] += x
        if d["growth"].get("y2") is not None:
            d["growth"]["y2"] += x
        return per_share(base, d, rate)
    x = engine.solve(growth_shift, price, -0.40, 0.80)
    if x is not None:
        d = copy.deepcopy(drivers)
        d["growth"]["y1"] += x
        if d["growth"].get("y2") is not None:
            d["growth"]["y2"] += x
        rows = engine.run_dcf(base, d, rate)["rows"]
        n = len(rows)
        cagr = (rows[-1]["revenue"] / base["revenue"]) ** (1.0 / n) - 1.0
        out["solves"].append({
            "key": "growth", "label": "Revenue growth",
            "value": d["growth"]["y1"], "shift": x, "implied_cagr": cagr,
            "base_cagr": (engine.run_dcf(base, drivers, rate)["rows"][-1]["revenue"] / base["revenue"]) ** (1.0 / n) - 1.0,
            "text": ("The price implies first-year growth of {:.1%} (fading to the long-run rate as in the "
                     "base case), or {:.1%} a year compounded over {} years.".format(d["growth"]["y1"], cagr, n)),
            "held": held_all})
    else:
        out["solves"].append({"key": "growth", "label": "Revenue growth", "value": None,
                              "text": "No growth rate between -40% and +80% a year reaches the price with "
                                      "the other assumptions held."})

    def margin(x: float) -> Optional[float]:
        d = copy.deepcopy(drivers)
        d["margin"]["target"] = x
        return per_share(base, d, rate)
    m = engine.solve(margin, price, -0.20, 0.90)
    out["solves"].append({
        "key": "margin", "label": "Target operating margin", "value": m,
        "text": ("The price implies operating margins settling at {:.1%} (base case {:.1%}).".format(
            m, drivers["margin"]["target"]) if m is not None else
            "No operating margin up to 90% reaches the price with the other assumptions held."),
        "held": "revenue growth, the discount rate, terminal growth, capex, working capital and taxes"})

    def discount(x: float) -> Optional[float]:
        return per_share(base, drivers, x)
    lo = drivers["terminal"]["growth"] + 0.0025
    r = engine.solve(discount, price, lo, 0.40)
    out["solves"].append({
        "key": "wacc", "label": "Implied return", "value": r,
        "text": ("At today's price, the base-case cash flows return {:.1%} a year (the discount rate "
                 "that equates them to the price), against a cost of capital of {:.1%}.".format(r, rate)
                 if r is not None else "No discount rate in range equates the base-case cash flows to "
                                       "the price."),
        "held": "every cash-flow assumption"})
    return out


def run_case(base: Dict[str, Any], drivers: Dict[str, Any], parts: Dict[str, Any]) -> Dict[str, Any]:
    """WACC from its parts, then the DCF. The one entry point the service uses
    for a single assumption set."""
    w = compute_wacc(parts, base)
    result = engine.run_dcf(base, drivers, w["wacc"])
    result["wacc"] = w
    result.update(versus_price(result["per_share"], base.get("price")))
    return result
