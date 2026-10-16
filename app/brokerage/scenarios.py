"""What-if: today's holdings after hypothetical buys, sells and weight targets.

Pure arithmetic on the holdings as the broker last reported them. No trade is
placed and nothing is sent anywhere; prices for names not held come from the
injected `price_of`, and history from the injected closes.

**The funding rule decides the answer, so it is stated, not assumed.**

* `cash`: buys spend cash, including what this scenario's sells raise. When
  the buys need more than that, every buy is scaled down by the same fraction
  and the shortfall is reported. Optic does not invent money: a scenario that
  needed margin would show a negative cash line nobody has.
* `new_money`: buys are paid with money added from outside, so the total
  grows by exactly that much. Sells add their proceeds to cash.
* `pro_rata`: buys are paid by selling every holding the scenario does not
  name, each in proportion to its value, so their weights shrink together and
  the total is unchanged. Sells add their proceeds to cash.

Sells are applied before buys. A sell cannot exceed what is held (there is no
shorting here): it is cut to the holding and the result says so. A target
weight is a share of the total after the scenario, holdings plus cash; with new
money that total depends on the buys themselves, and is solved exactly.

Before and after volatility and beta come from `scorecard.history_risk`, with
cash as a zero-return holding, over the last year of daily closes. They are
history at the stated weights, not a forecast; the S&P 500 stress line is beta
times the fall, which is a model and nothing more.
"""

from __future__ import annotations

import math
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import scorecard as sc

VERSION = "scenarios-2026-10-15.1"
STRESS_MOVE_PCT = -10.0
TOP_N = 10
FUNDING = ("cash", "new_money", "pro_rata")
ACTIONS = ("buy", "sell", "target_weight")
AMOUNT_TYPES = ("dollars", "shares", "weight_pct")
CENT = 0.005

KIND_LABELS = {"bond": "Bonds", "crypto": "Crypto", "other": "Other"}
FUND_LABEL = "ETFs and funds (not looked through)"
UNKNOWN_SECTOR = "Sector not known"

FUNDING_RULES = {
    "cash": "Buys spend cash, including what the sells raise. If that is not enough, every buy is scaled down "
            "by the same fraction and the shortfall is shown; no money is assumed.",
    "new_money": "Buys are paid with new money added to the account, so the total grows by the amount bought. "
                 "Sells add their proceeds to cash.",
    "pro_rata": "Buys are paid by selling every holding the scenario does not name, each in proportion to its "
                "value. Sells add their proceeds to cash.",
}


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


def _call(fn: Optional[Callable], arg: Any) -> Any:
    if fn is None:
        return None
    try:
        return fn(arg)
    except Exception:                                            # noqa: BLE001
        return None


# ---------------------------------------------------------------- the book

def _positions(holdings: List[Dict[str, Any]], warnings: List[str]) -> Dict[str, Dict[str, Any]]:
    pos: Dict[str, Dict[str, Any]] = {}
    for h in holdings or []:
        sym = str(h.get("symbol") or h.get("description") or "").upper()
        if not sym:
            continue
        v = sc.holding_value(h)
        if v is None:
            warnings.append("{} has no US-dollar value (no exchange rate), so it is left out of before and after."
                            .format(sym))
            continue
        qty = _num(h.get("quantity"))
        p = pos.setdefault(sym, {"symbol": sym, "kind": h.get("kind") or "other", "sector": h.get("sector"),
                                 "value": 0.0, "quantity": 0.0, "held": True, "tradable": bool(h.get("symbol"))})
        p["value"] += v
        p["quantity"] += qty or 0.0
        if not p.get("sector") and h.get("sector"):
            p["sector"] = h.get("sector")
    for p in pos.values():
        p["price"] = p["value"] / p["quantity"] if p["quantity"] else None
        p["value0"] = p["value"]
    return pos


def _sector_label(p: Dict[str, Any]) -> str:
    kind = p.get("kind")
    if kind in sc.FUNDLIKE:
        return FUND_LABEL
    if kind in sc.STOCKLIKE or kind == "unknown":
        return p.get("sector") or UNKNOWN_SECTOR
    return KIND_LABELS.get(kind, "Other")


def _snapshot(pos: Dict[str, Dict[str, Any]], cash: float) -> Dict[str, Any]:
    total = sum(p["value"] for p in pos.values()) + cash
    invested = sum(p["value"] for p in pos.values() if p["value"] > 0)
    longs = sorted((p["value"] / invested for p in pos.values() if p["value"] > CENT), reverse=True) \
        if invested > 0 else []
    hhi = sum(w * w for w in longs)
    sectors: Dict[str, float] = {}
    for p in pos.values():
        if p["value"] > CENT:
            label = _sector_label(p)
            sectors[label] = sectors.get(label, 0.0) + p["value"]
    if abs(cash) > CENT:
        sectors["Cash"] = sectors.get("Cash", 0.0) + cash
    return {
        "total": total, "cash": cash, "invested": invested,
        "weights": {s: (p["value"] / total if total else 0.0) for s, p in pos.items() if p["value"] > CENT},
        "cash_pct": 100.0 * cash / total if total else None,
        "effective_holdings": 1.0 / hhi if hhi > 0 else None,
        "top1_pct": 100.0 * longs[0] if longs else None,
        "top5_pct": 100.0 * sum(longs[:5]) if longs else None,
        "holdings": len(longs),
        "sectors": {k: 100.0 * v / total for k, v in sectors.items()} if total else {},
    }


# ---------------------------------------------------------------- look-through

def _fund_mixes(exposure: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    """{fund symbol: {sector: fraction of the fund}} where the exposure result
    carries per-fund sector mixes (under `funds` or `by_fund`); else empty."""
    if not isinstance(exposure, dict):
        return {}
    src = exposure.get("funds") or exposure.get("by_fund") or []
    items = list(src.values()) if isinstance(src, dict) else list(src)
    out: Dict[str, Dict[str, float]] = {}
    for f in items:
        if not isinstance(f, dict) or not f.get("symbol"):
            continue
        sec = f.get("sectors") or f.get("sector_mix") or {}
        mix: Dict[str, float] = {}
        if isinstance(sec, dict):
            for k, v in sec.items():
                x = _num(v)
                if x is not None:
                    mix[str(k)] = x
        else:
            for row in sec:
                if isinstance(row, dict):
                    name = row.get("sector") or row.get("label") or row.get("name")
                    x = sc._lt_pct(row)
                    if name and x is not None:
                        mix[str(name)] = x
        if not mix:
            continue
        # Percent or fraction: a mix whose parts sum past 1.5 is in percent.
        if sum(mix.values()) > 1.5:
            mix = {k: v / 100.0 for k, v in mix.items()}
        out[str(f["symbol"]).upper()] = mix
    return out


def _lookthrough_sectors(pos: Dict[str, Dict[str, Any]], cash: float,
                         mixes: Dict[str, Dict[str, float]]) -> Dict[str, float]:
    total = sum(p["value"] for p in pos.values()) + cash
    out: Dict[str, float] = {}
    for sym, p in pos.items():
        if p["value"] <= CENT:
            continue
        mix = mixes.get(sym) if p.get("kind") in sc.FUNDLIKE else None
        if mix:
            for sec, f in mix.items():
                out[sec] = out.get(sec, 0.0) + p["value"] * f
            rest = 1.0 - sum(mix.values())
            if rest > 0.0005:
                out["Not looked through"] = out.get("Not looked through", 0.0) + p["value"] * rest
        else:
            label = _sector_label(p)
            label = "Not looked through" if label == FUND_LABEL else label
            out[label] = out.get(label, 0.0) + p["value"]
    if abs(cash) > CENT:
        out["Cash"] = out.get("Cash", 0.0) + cash
    return {k: 100.0 * v / total for k, v in out.items()} if total else {}


# ---------------------------------------------------------------- the run

def _refuse(rec: Dict[str, Any], reason: str) -> None:
    rec["status"] = "refused"
    rec["reason"] = reason


def run(holdings: List[Dict[str, Any]], cash: float, changes: List[Dict[str, Any]], funding: str,
        price_of: Callable[[str], Optional[Dict[str, Any]]], sector_of: Callable[[str], Optional[str]],
        closes: Dict[str, Any], benchmark_closes: Any, exposure: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Before and after for a list of hypothetical changes. See the module
    docstring for the funding rules; nothing here places a trade."""
    warnings: List[str] = []
    funding = str(funding or "").strip().lower()
    cash0 = _num(cash) or 0.0
    pos = _positions(holdings, warnings)
    before = _snapshot(pos, cash0)
    total0 = before["total"]
    base = {"version": VERSION, "funding": funding, "funding_rule": FUNDING_RULES.get(funding)}
    if funding not in FUNDING:
        return dict(base, available=False,
                    reason="Unknown funding rule {!r}: choose cash, new_money or pro_rata.".format(funding),
                    warnings=warnings)

    # ------------------------------------------------ validate the changes
    recs: List[Dict[str, Any]] = []
    seen = set()
    for i, c in enumerate(changes or []):
        c = c or {}
        sym = str(c.get("symbol") or "").strip().upper()
        action = str(c.get("action") or "").strip().lower()
        atype = str(c.get("amount_type") or "").strip().lower()
        amount = _num(c.get("amount"))
        rec = {"index": i, "symbol": sym, "action": action, "amount_type": atype, "amount": amount,
               "status": "applied", "reason": None, "requested_usd": None, "applied_usd": 0.0,
               "applied_shares": None, "price": None, "price_as_of": None, "price_source": None}
        recs.append(rec)
        if not sym:
            _refuse(rec, "No symbol.")
            continue
        if action not in ACTIONS:
            _refuse(rec, "Unknown action {!r}: buy, sell or target_weight.".format(action))
            continue
        if atype not in AMOUNT_TYPES:
            _refuse(rec, "Unknown amount type {!r}: dollars, shares or weight_pct.".format(atype))
            continue
        if amount is None or amount < 0 or (amount == 0 and action != "target_weight"):
            _refuse(rec, "The amount must be a positive number.")
            continue
        if action == "target_weight" and atype == "weight_pct" and amount >= 100.0:
            _refuse(rec, "A target weight must be below 100% of the portfolio.")
            continue
        if sym in seen:
            _refuse(rec, "{} already has a change in this scenario; combine them into one.".format(sym))
            continue
        seen.add(sym)
        held = sym in pos and pos[sym]["value"] > CENT
        if held and not pos[sym]["tradable"]:
            _refuse(rec, "{} has no symbol from the broker, so it cannot be traded here.".format(sym))
            continue
        if held:
            rec["price"], rec["price_source"] = pos[sym]["price"], "the broker's last price at sync"
            if rec["price"] is None and atype == "shares":
                _refuse(rec, "No share count for {}, so a number of shares cannot be valued.".format(sym))
                continue
        else:
            if action == "sell":
                _refuse(rec, "{} is not held, and selling what is not held would be a short sale.".format(sym))
                continue
            q = _call(price_of, sym) or {}
            p = _num(q.get("price")) if isinstance(q, dict) else None
            if not p or p <= 0:
                _refuse(rec, "Optic has no price for {}, so it may not be a listed symbol. Nothing was assumed."
                        .format(sym))
                continue
            rec["price"], rec["price_as_of"], rec["price_source"] = p, q.get("as_of"), "Optic's quote"
            kind = str(q.get("kind") or q.get("quote_type") or "").lower()
            kind = {"etf": "etf", "mutualfund": "fund", "fund": "fund", "equity": "equity"}.get(kind, "unknown")
            pos[sym] = {"symbol": sym, "kind": kind, "sector": _call(sector_of, sym), "value": 0.0, "value0": 0.0,
                        "quantity": 0.0, "price": p, "held": False, "tradable": True}

    live = [r for r in recs if r["status"] != "refused"]
    named = {r["symbol"] for r in live}

    def dollars(rec: Dict[str, Any]) -> float:
        if rec["amount_type"] == "dollars":
            return rec["amount"]
        if rec["amount_type"] == "shares":
            return rec["amount"] * rec["price"]
        return rec["amount"] / 100.0 * total0

    # ------------------------------------------------ resolve targets
    sells: List[Tuple[Dict[str, Any], float]] = []
    buys: List[Tuple[Dict[str, Any], float]] = []
    fractions: List[Dict[str, Any]] = []
    fixed_buys = 0.0
    for rec in live:
        v = pos[rec["symbol"]]["value"]
        if rec["action"] == "sell":
            sells.append((rec, dollars(rec)))
        elif rec["action"] == "buy":
            buys.append((rec, dollars(rec)))
            fixed_buys += dollars(rec)
        elif rec["amount_type"] == "weight_pct":
            fractions.append(rec)
        else:
            delta = dollars(rec) - v
            (buys if delta > 0 else sells).append((rec, abs(delta)))
            if delta > 0:
                fixed_buys += delta
    total_final = total0
    if fractions and funding == "new_money":
        # With new money the total includes the buys that hit the targets:
        # T = (T0 + fixed buys - value already held in the buy targets) /
        # (1 - their target fractions). The set of targets that are buys can
        # only grow as T grows, so a few passes settle it.
        buy_set = {r["index"] for r in fractions if r["amount"] / 100.0 * total0 > pos[r["symbol"]]["value"]}
        for _ in range(len(fractions) + 2):
            st = sum(r["amount"] / 100.0 for r in fractions if r["index"] in buy_set)
            sv = sum(pos[r["symbol"]]["value"] for r in fractions if r["index"] in buy_set)
            if st >= 1.0:
                for r in fractions:
                    if r["index"] in buy_set:
                        _refuse(r, "Target weights bought with new money add up to 100% or more, which no amount "
                                   "of new money can reach.")
                fractions = [r for r in fractions if r["status"] != "refused"]
                buy_set = set()
                break
            total_final = (total0 + fixed_buys - sv) / (1.0 - st)
            nxt = {r["index"] for r in fractions if r["amount"] / 100.0 * total_final > pos[r["symbol"]]["value"]}
            if nxt == buy_set:
                break
            buy_set = nxt
    for rec in fractions:
        delta = rec["amount"] / 100.0 * total_final - pos[rec["symbol"]]["value"]
        if delta > CENT:
            buys.append((rec, delta))
        elif delta < -CENT:
            sells.append((rec, -delta))
        else:
            rec["status"], rec["reason"] = "no_change", "Already at the target weight."

    # ------------------------------------------------ sells, then buys
    cash_now = cash0
    for rec, amt in sells:
        p = pos[rec["symbol"]]
        rec["requested_usd"] = _r(amt)
        if amt > p["value"] + CENT:
            warnings.append("Sell of {} cut from {:.2f} to the {:.2f} held: there is no shorting here."
                            .format(rec["symbol"], amt, p["value"]))
            rec["status"], rec["reason"] = "clamped", "Cut to the value held; selling more would be a short sale."
            amt = p["value"]
        frac = amt / p["value"] if p["value"] else 0.0
        rec["applied_shares"] = _r(-p["quantity"] * frac, 6) if p["quantity"] else None
        p["quantity"] -= p["quantity"] * frac
        p["value"] -= amt
        rec["applied_usd"] = _r(-amt)
        cash_now += amt

    wanted = sum(a for _, a in buys)
    new_money = 0.0
    shortfall = 0.0
    scale = 1.0
    if buys:
        if funding == "cash":
            avail = max(cash_now, 0.0)
            if wanted > avail + CENT:
                scale = avail / wanted if wanted else 0.0
                shortfall = wanted - avail
                warnings.append("The buys need {:.2f} and cash, after the sells, is {:.2f}: short by {:.2f}. Each buy "
                                "is scaled to {:.1f}% of what was asked. Nothing is borrowed."
                                .format(wanted, avail, shortfall, 100.0 * scale))
            cash_now -= wanted * scale
        elif funding == "new_money":
            new_money = wanted
        else:
            sources = {s: p["value"] for s, p in pos.items()
                       if s not in named and p["value"] > CENT and p["tradable"]}
            pool = sum(sources.values())
            if wanted > pool + CENT:
                scale = pool / wanted if wanted else 0.0
                shortfall = wanted - pool
                warnings.append("The buys need {:.2f} and the holdings not named in the scenario are worth {:.2f}: "
                                "short by {:.2f}. Each buy is scaled to {:.1f}% of what was asked."
                                .format(wanted, pool, shortfall, 100.0 * scale))
            raised = wanted * scale
            for s, v in sources.items():
                p = pos[s]
                cut = raised * v / pool
                p["quantity"] -= p["quantity"] * (cut / p["value"]) if p["value"] else 0.0
                p["value"] -= cut
    for rec, amt in buys:
        p = pos[rec["symbol"]]
        rec["requested_usd"] = _r(amt)
        got = amt * scale
        if scale < 1.0:
            rec["status"], rec["reason"] = "partial", "Funding covered {:.1f}% of it.".format(100.0 * scale)
        p["value"] += got
        if p.get("price"):
            p["quantity"] += got / p["price"]
            rec["applied_shares"] = _r(got / p["price"], 6)
        rec["applied_usd"] = _r(got)
    for rec in recs:
        if rec["status"] == "refused":
            warnings.append("{} not applied: {}".format(rec["symbol"] or "A change", rec["reason"]))

    after = _snapshot(pos, cash_now)
    for rec in fractions:
        if rec["status"] in ("applied", "partial"):
            got = 100.0 * after["weights"].get(rec["symbol"], 0.0)
            if abs(got - rec["amount"]) > 0.05:
                rec["reason"] = ((rec["reason"] + " ") if rec["reason"] else "") + \
                    "Reached {:.2f}% against a target of {:.2f}%.".format(got, rec["amount"])

    # ------------------------------------------------ comparisons
    def pct(x: Optional[float]) -> Optional[float]:
        return _r(x)

    syms = set(before["weights"]) | set(after["weights"])
    changed = {r["symbol"] for r in recs if r["status"] in ("applied", "partial", "clamped")}
    if funding == "pro_rata" and buys:
        changed |= {s for s, p in pos.items() if abs(p["value"] - p["value0"]) > CENT}
    rows = [{"symbol": s, "before_pct": pct(100.0 * before["weights"].get(s, 0.0)),
             "after_pct": pct(100.0 * after["weights"].get(s, 0.0)),
             "change_pts": pct(100.0 * (after["weights"].get(s, 0.0) - before["weights"].get(s, 0.0))),
             "changed": s in changed,
             "value_before": _r(pos[s]["value0"]), "value_after": _r(pos[s]["value"])} for s in syms]
    rows.sort(key=lambda x: -(x["after_pct"] or 0.0))
    shown = [x for i, x in enumerate(rows) if i < TOP_N or x["changed"]]

    sectors = sorted(set(before["sectors"]) | set(after["sectors"]))
    sector_rows = [{"sector": k, "before_pct": pct(before["sectors"].get(k, 0.0)),
                    "after_pct": pct(after["sectors"].get(k, 0.0)),
                    "change_pts": pct(after["sectors"].get(k, 0.0) - before["sectors"].get(k, 0.0))}
                   for k in sectors]
    sector_rows.sort(key=lambda x: -(x["after_pct"] or 0.0))
    look = None
    if exposure is not None:
        mixes = _fund_mixes(exposure)
        if mixes:
            pos_before = {s: dict(p, value=p["value0"]) for s, p in pos.items()}
            lb, la = _lookthrough_sectors(pos_before, cash0, mixes), _lookthrough_sectors(pos, cash_now, mixes)
            look = {"available": True,
                    "rows": sorted(({"sector": k, "before_pct": pct(lb.get(k, 0.0)), "after_pct": pct(la.get(k, 0.0)),
                                     "change_pts": pct(la.get(k, 0.0) - lb.get(k, 0.0))}
                                    for k in set(lb) | set(la)), key=lambda x: -(x["after_pct"] or 0.0)),
                    "note": "Funds are split into sectors by their latest reported holdings; a fund bought here "
                            "that was not already looked through is shown as not looked through."}
        else:
            lt = sc.lookthrough_view(exposure)
            look = {"available": False,
                    "before": [{"sector": k, "pct": pct(v)} for k, v in sorted((lt or {}).get("sectors", {}).items(),
                                                                           key=lambda kv: -kv[1])] if lt else None,
                    "reason": "The look-through result has no per-fund sector mix, so the after column cannot be "
                              "recomputed; the before column is today's look-through."
                    if lt else "No look-through exposure was available."}

    h_before = sc.history_risk({s: p["value0"] for s, p in pos.items() if p["value0"] > CENT}, closes or {},
                               benchmark_closes, cash=cash0)
    h_after = sc.history_risk({s: p["value"] for s, p in pos.items() if p["value"] > CENT}, closes or {},
                              benchmark_closes, cash=cash_now)

    def hist(h: Dict[str, Any]) -> Dict[str, Any]:
        if not h.get("available"):
            return {"available": False, "reason": h.get("reason"), "excluded": h.get("excluded") or []}
        return {"available": True, "vol_pct": h["portfolio_vol_pct"], "beta": h["beta"],
                "benchmark_vol_pct": h["benchmark_vol_pct"], "max_drawdown_pct": h["max_drawdown_pct"],
                "coverage_pct": h["coverage_pct"], "window": h["window"], "excluded": h["excluded"]}

    hb, ha = hist(h_before), hist(h_after)
    for e in h_after.get("excluded") or []:
        if e["symbol"] in named:
            warnings.append("{} has no usable price history, so the after volatility and beta leave it out."
                            .format(e["symbol"]))

    def stress(h: Dict[str, Any], total: float) -> Optional[Dict[str, Any]]:
        if not h.get("available") or h.get("beta") is None:
            return None
        move = h["beta"] * STRESS_MOVE_PCT
        return {"pct": _r(move), "value": _r(total * move / 100.0)}

    out = dict(
        base, available=True,
        changes=recs,
        weights=shown,
        cash={"before": _r(cash0), "after": _r(cash_now), "before_pct": pct(before["cash_pct"]),
              "after_pct": pct(after["cash_pct"])},
        total={"before": _r(before["total"]), "after": _r(after["total"])},
        new_money_usd=_r(new_money),
        shortfall_usd=_r(shortfall),
        concentration={
            "before": {"effective_holdings": _r(before["effective_holdings"]), "top1_pct": pct(before["top1_pct"]),
                       "top5_pct": pct(before["top5_pct"]), "holdings": before["holdings"]},
            "after": {"effective_holdings": _r(after["effective_holdings"]), "top1_pct": pct(after["top1_pct"]),
                      "top5_pct": pct(after["top5_pct"]), "holdings": after["holdings"]},
            "basis": "Effective holdings (1 / sum of squared weights), the largest position and the top five, over "
                     "invested holdings only, cash left out, as on the holdings page.",
        },
        sectors={"direct": sector_rows, "look_through": look,
                 "basis": "Shares of the total, cash included. Stocks by their sector; funds are one line unless "
                          "looked through."},
        history={"before": hb, "after": ha,
                 "label": "History, not a forecast: what a portfolio held at these weights did over the last "
                          "year of daily closes."},
        stress={"benchmark_move_pct": STRESS_MOVE_PCT, "before": stress(h_before, before["total"]),
                "after": stress(h_after, after["total"]),
                "label": "If the S&P 500 fell {:.0f}%, a beta-implied change. A model: beta from a year of daily "
                         "returns times the fall. Real falls do not follow beta, and in a sell-off correlations "
                         "rise.".format(abs(STRESS_MOVE_PCT))},
        warnings=warnings,
        method=("No trades are placed: this is arithmetic on the holdings as the broker last reported them, at the "
                "broker's last prices, and Optic's quote for anything not held. {} Sells are applied before buys "
                "and cannot exceed what is held. A buy or sell given as weight_pct is that share of today's total; "
                "a target weight is a share of the total after the scenario. Weights are shares of the total, cash "
                "included. Volatility and beta use daily closes over the last year with cash as a zero-return "
                "holding; holdings without {} days of history are left out and the rest re-weighted, and the "
                "coverage says how much value that kept.".format(FUNDING_RULES[funding], sc.MIN_OVERLAP_DAYS)),
        limitations=[
            "Trading costs, taxes, spreads and the price moving while you trade are not modelled.",
            "Prices are the broker's last at sync for holdings and Optic's delayed quote for anything new.",
            "Options and holdings without a US-dollar value are outside these weights.",
            "Volatility, beta and the stress line describe the last year at these weights; they are not a "
            "forecast or a guarantee.",
        ],
    )
    return out
