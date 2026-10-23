"""A linked portfolio, worked out from what the broker supplied and nothing else.

Three layers, kept apart all the way to the screen and to Milo:

* **Facts** are the broker's own numbers as the aggregator relayed them:
  quantities, prices, average costs, cash, the account's total, and when the
  broker last reported. They are shown as reported.
* **Calculations** are Optic's arithmetic on those facts: market values,
  weights, concentration, unrealised gain where a cost basis exists, change
  since the previous sync. Each one says what it covers.
* **Interpretation** is Milo's, and never happens here.

**Nothing incomplete is presented as precise.** A total that leaves out a
position says so and says how much it leaves out. Unrealised gain is summed
only over positions with a cost basis and reports its coverage beside it.
Options are valued at contracts x price x multiplier, using the provider's
multiplier (SnapTrade's positions/all sends one) and assuming 100, or 10 for a
mini, only where it is missing. ETFs are
not looked through, so a sector chart says "ETFs and funds" rather than
pretending to know what is inside them. Currencies are not added together
unless an exchange rate was available, and a converted total says it is
approximate and at whose rate.

The functions that reach outside (sector, earnings date, Optic's quote, an
exchange rate) are arguments, so this module is pure and its tests need no
network.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional

PRICE_GAP_PCT = 2.0          # broker price vs Optic's delayed quote, worth a word
BROKER_TOTAL_GAP_PCT = 1.0   # broker's account total vs the sum of the lines we got
SINGLE_NAME_FLAG = 20.0      # % of long value in one company
SECTOR_FLAG = 40.0           # % of long value in one sector
EARNINGS_WINDOW_DAYS = 30
MAX_LOOKUPS = 25             # bounded so a 300-line portfolio cannot fan out 300 fetches

STOCKLIKE = ("equity",)
FUNDLIKE = ("etf", "fund")
VALUED_KINDS = ("equity", "etf", "fund", "bond", "crypto")
KIND_LABELS = {"equity": "Stocks", "etf": "ETFs", "fund": "Mutual funds", "bond": "Bonds",
               "crypto": "Crypto", "option": "Options", "cash": "Cash", "other": "Other"}


def _num(v: Any) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _r(v: Optional[float], n: int = 2) -> Optional[float]:
    return None if v is None else round(v, n)


def multiplier(opt: Dict[str, Any]) -> float:
    given = _num(opt.get("multiplier"))
    if given and given > 0:
        return given
    return 10 if opt.get("mini") else 100


def _days_until(day: Optional[str], today: date) -> Optional[int]:
    try:
        return (datetime.strptime(str(day)[:10], "%Y-%m-%d").date() - today).days
    except (TypeError, ValueError):
        return None


def build(accounts: List[Dict[str, Any]],
          sector_of: Callable[[str], Optional[str]] = lambda s: None,
          earnings_of: Callable[[str], Optional[str]] = lambda s: None,
          optic_price: Callable[[str], Optional[float]] = lambda s: None,
          fx_to_usd: Callable[[str], Optional[float]] = lambda c: None,
          previous: Optional[Dict[str, Any]] = None,
          today: Optional[date] = None) -> Dict[str, Any]:
    """`accounts` is a list of {row fields..., "payload": {...} | None}.
    Only selected accounts with a payload count towards anything."""
    today = today or datetime.now(timezone.utc).date()
    notes: List[str] = []
    acct_out: List[Dict[str, Any]] = []
    lines: Dict[str, Dict[str, Any]] = {}
    options: List[Dict[str, Any]] = []
    unsupported: List[Dict[str, Any]] = []
    cash_equivalents: List[Dict[str, Any]] = []
    cash_by_ccy: Dict[str, float] = {}
    sync_times: List[str] = []
    broker_times: List[str] = []
    counted = 0

    def rate(ccy: Optional[str]) -> Optional[float]:
        ccy = (ccy or "USD").upper()
        return 1.0 if ccy == "USD" else _num(fx_to_usd(ccy))

    for a in accounts:
        p = a.get("payload") or None
        entry = {
            "id": a.get("id"), "name": a.get("name"), "institution": a.get("institution"),
            "number_mask": a.get("number_mask"), "account_type": a.get("account_type"),
            "currency": a.get("currency"), "selected": bool(a.get("selected", 1)),
            "sync_state": a.get("sync_state"), "sync_note": a.get("sync_note"),
            "last_sync_at": a.get("last_sync_at"), "broker_as_of": a.get("broker_as_of"),
            "connection_id": a.get("connection_id"),
            "broker_total": _num((p or {}).get("total_value")),
            "lines_total": None, "total_gap_pct": None, "cash": [],
        }
        acct_out.append(entry)
        if not entry["selected"] or not p:
            continue
        counted += 1
        if a.get("last_sync_at"):
            sync_times.append(a["last_sync_at"])
        if a.get("broker_as_of"):
            broker_times.append(a["broker_as_of"])
        acct_ccy = (a.get("currency") or "USD").upper()
        acct_sum = 0.0
        acct_sum_ok = True
        for pos in p.get("positions") or []:
            kind = pos.get("kind") or "other"
            qty, price, avg = _num(pos.get("quantity")), _num(pos.get("price")), _num(pos.get("avg_cost"))
            ccy = (pos.get("currency") or acct_ccy).upper()
            if pos.get("cash_equivalent") and "balances" not in (p.get("problems") or []):
                # SnapTrade's Balance.cash "includes" a money-market fund that
                # positions/all also returns with cash_equivalent=true, so the
                # line is shown but counted once, as cash. When the balances
                # failed there is no cash figure to hold it, and it counts here.
                cash_equivalents.append({"symbol": pos.get("symbol"), "description": pos.get("description"),
                                         "account": a.get("name"), "currency": ccy,
                                         "value": _r(qty * price) if qty is not None and price is not None
                                         else None})
                continue
            if kind not in VALUED_KINDS or qty is None or price is None:
                unsupported.append({
                    "description": pos.get("description") or pos.get("symbol") or "Unnamed holding",
                    "symbol": pos.get("symbol"), "account": a.get("name"), "kind": kind,
                    "reason": "No price from the broker, so it is left out of every total."
                    if price is None else "Optic does not value this asset type yet.",
                })
                acct_sum_ok = False
                continue
            mv = qty * price
            key = "{}:{}:{}".format(kind, (pos.get("symbol") or pos.get("description") or "").upper(), ccy)
            line = lines.setdefault(key, {
                "key": key, "symbol": pos.get("symbol"), "description": pos.get("description"),
                "kind": kind, "currency": ccy, "quantity": 0.0, "market_value": 0.0,
                "cost_basis": 0.0, "basis_complete": True, "accounts": [], "prices": [],
            })
            line["quantity"] += qty
            line["market_value"] += mv
            line["prices"].append(price)
            if a.get("name") not in line["accounts"]:
                line["accounts"].append(a.get("name"))
            if avg is None:
                line["basis_complete"] = False
            else:
                line["cost_basis"] += qty * avg
            if ccy == acct_ccy:
                acct_sum += mv
            else:
                acct_sum_ok = False
        unpriced_opts: List[str] = []
        for opt in p.get("options") or []:
            n, price, avg = _num(opt.get("contracts")), _num(opt.get("price")), _num(opt.get("avg_cost"))
            mult = multiplier(opt)
            assumed_mult = not _num(opt.get("multiplier"))
            mv = n * price * mult if n is not None and price is not None else None
            cost = n * avg * mult if n is not None and avg is not None else None
            options.append({
                "underlying": opt.get("underlying"), "occ": opt.get("occ"),
                "option_type": opt.get("option_type"), "strike": _num(opt.get("strike")),
                "expiry": opt.get("expiry"), "days_to_expiry": _days_until(opt.get("expiry"), today),
                "contracts": n, "multiplier": mult, "multiplier_assumed": assumed_mult,
                "mini": bool(opt.get("mini")),
                "price": price, "currency": (opt.get("currency") or acct_ccy).upper(),
                "market_value_est": _r(mv), "cost_basis": _r(cost),
                "unrealized_pl_est": _r(mv - cost) if mv is not None and cost is not None else None,
                "account": a.get("name"),
                # the time the broker's price belongs to: without it the 60-minute freshness check in
                # options_risk could never fire (audit 2026-10-22)
                "price_as_of": a.get("broker_as_of") or a.get("last_sync_at"),
            })
            if mv is not None:
                acct_sum += mv
            else:
                acct_sum_ok = False
                unpriced_opts.append("{} {}".format(opt.get("underlying") or "", opt.get("occ") or "option").strip())
        for c in p.get("cash") or []:
            amt = _num(c.get("amount"))
            ccy = (c.get("currency") or acct_ccy).upper()
            entry["cash"].append({"currency": ccy, "amount": amt, "buying_power": _num(c.get("buying_power"))})
            if amt is not None:
                cash_by_ccy[ccy] = cash_by_ccy.get(ccy, 0.0) + amt
                if ccy == acct_ccy:
                    acct_sum += amt
        if "balances" in (p.get("problems") or []):
            acct_sum_ok = False
        entry["lines_total"] = _r(acct_sum)
        if entry["broker_total"] and acct_sum_ok:
            gap = 100.0 * (acct_sum - entry["broker_total"]) / abs(entry["broker_total"])
            if abs(gap) >= BROKER_TOTAL_GAP_PCT:
                entry["total_gap_pct"] = _r(gap, 1)
                notes.append("{}: the broker's own total differs from the sum of the holdings Optic "
                             "received by {:.1f}%. Something the broker holds may not be reported "
                             "through the connection.".format(a.get("name"), gap))
        if unpriced_opts:
            # an option with no broker price was left out of every total without a word (audit 2026-10-22)
            notes.append("{}: {} came without a price from the broker, so {} left out of every total.".format(
                a.get("name"), ", ".join(unpriced_opts), "it is" if len(unpriced_opts) == 1 else "they are"))
        if p.get("problems"):
            notes.append("{}: the last sync did not return {}. Figures for this account are partial."
                         .format(a.get("name"), " or ".join(p["problems"])))

    # ------------------------------------------------------------ holdings
    holdings: List[Dict[str, Any]] = []
    for line in lines.values():
        qty = line["quantity"]
        prices = line.pop("prices")
        price = line["market_value"] / qty if qty else (prices[0] if prices else None)
        basis = line["cost_basis"] if line["basis_complete"] else None
        holdings.append(dict(line, quantity=_r(qty, 6), price=_r(price, 4),
                             market_value=_r(line["market_value"]), cost_basis=_r(basis),
                             unrealized_pl=_r(line["market_value"] - basis) if basis is not None else None,
                             unrealized_pct=_r(100.0 * (line["market_value"] - basis) / abs(basis), 1)
                             if basis else None))

    # ------------------------------------------------------------- totals
    by_ccy: Dict[str, Dict[str, float]] = {}

    def bucket(ccy: str) -> Dict[str, float]:
        return by_ccy.setdefault(ccy, {"securities": 0.0, "options": 0.0, "cash": 0.0})

    for h in holdings:
        bucket(h["currency"])["securities"] += h["market_value"] or 0.0
    for o in options:
        if o["market_value_est"] is not None:
            bucket(o["currency"])["options"] += o["market_value_est"]
    for ccy, amt in cash_by_ccy.items():
        bucket(ccy)["cash"] += amt
    for ccy, b in by_ccy.items():
        b["total"] = b["securities"] + b["options"] + b["cash"]
        for k in list(b):
            b[k] = round(b[k], 2)

    missing_fx = sorted(c for c in by_ccy if rate(c) is None)
    combined = None
    if by_ccy and not missing_fx:
        combined = {"value": round(sum(b["total"] * rate(c) for c, b in by_ccy.items()), 2),
                    "currency": "USD",
                    "approximate": any(c != "USD" for c in by_ccy),
                    "fx": {c: rate(c) for c in by_ccy if c != "USD"}}
        if combined["approximate"]:
            notes.append("The combined total converts {} to US dollars at Optic's delayed exchange rate, "
                         "so it is approximate.".format(", ".join(c for c in by_ccy if c != "USD")))
    elif missing_fx:
        notes.append("No exchange rate was available for {}, so totals are shown per currency and "
                     "not added together.".format(", ".join(missing_fx)))

    # ----------------------------------------------- weights and allocation
    def usd(v: Optional[float], ccy: str) -> Optional[float]:
        r = rate(ccy)
        return None if v is None or r is None else v * r

    long_value = sum(max(0.0, usd(h["market_value"], h["currency"]) or 0.0) for h in holdings)
    long_value += sum(max(0.0, usd(o["market_value_est"], o["currency"]) or 0.0) for o in options)
    for h in holdings:
        v = usd(h["market_value"], h["currency"])
        h["weight_pct"] = _r(100.0 * v / long_value, 1) if v is not None and long_value and v > 0 else None
        # The workspace's exposure and scorecard add across
        # currencies, so they read this rather than converting again.
        h["value_usd"] = _r(v)
    holdings.sort(key=lambda h: -(usd(h["market_value"], h["currency"]) or 0.0))

    by_kind: Dict[str, float] = {}
    for h in holdings:
        v = usd(h["market_value"], h["currency"])
        if v is not None:
            by_kind[h["kind"]] = by_kind.get(h["kind"], 0.0) + v
    for o in options:
        v = usd(o["market_value_est"], o["currency"])
        if v is not None:
            by_kind["option"] = by_kind.get("option", 0.0) + v
    for ccy, amt in cash_by_ccy.items():
        v = usd(amt, ccy)
        if v is not None:
            by_kind["cash"] = by_kind.get("cash", 0.0) + v
    gross = sum(abs(v) for v in by_kind.values()) or 0.0

    def shares(d: Dict[str, float], labels: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
        out = [{"key": k, "label": (labels or {}).get(k, k), "value": round(v, 2),
                "share_pct": _r(100.0 * v / gross, 1) if gross else None} for k, v in d.items()]
        return sorted(out, key=lambda x: -abs(x["value"]))

    # Sectors for stocks only. Lookups are bounded and the leftovers say so.
    sectors: Dict[str, float] = {}
    looked = 0
    for h in holdings:
        v = usd(h["market_value"], h["currency"])
        if v is None or v <= 0:
            continue
        if h["kind"] in STOCKLIKE and h.get("symbol"):
            sec = None
            if looked < MAX_LOOKUPS:
                looked += 1
                try:
                    sec = sector_of(h["symbol"])
                except Exception:                               # noqa: BLE001
                    sec = None
            h["sector"] = sec
            label = sec or "Sector not known"
        elif h["kind"] in FUNDLIKE:
            label = "ETFs and funds (not looked through)"
        else:
            label = KIND_LABELS.get(h["kind"], "Other")
        sectors[label] = sectors.get(label, 0.0) + v

    by_account = {}
    for e in acct_out:
        if e["selected"] and e["lines_total"] is not None:
            v = usd(e["lines_total"], (e.get("currency") or "USD").upper())
            if v is not None:
                by_account[e["name"] or "Account"] = by_account.get(e["name"] or "Account", 0.0) + v

    # ------------------------------------------------------- concentration
    long_weights = sorted((h["weight_pct"] or 0.0 for h in holdings if (h["weight_pct"] or 0) > 0),
                          reverse=True)
    hhi = sum((w / 100.0) ** 2 for w in long_weights)
    flags: List[str] = []
    for h in holdings:
        if h["kind"] in STOCKLIKE and (h["weight_pct"] or 0) >= SINGLE_NAME_FLAG:
            flags.append("{} is {:.1f}% of long holdings.".format(h["symbol"], h["weight_pct"]))
    for label, v in sectors.items():
        if label in ("ETFs and funds (not looked through)", "Sector not known") or not long_value:
            continue
        pct = 100.0 * v / long_value
        if pct >= SECTOR_FLAG and label in {h.get("sector") for h in holdings}:
            flags.append("{} stocks are {:.1f}% of long holdings, before counting what ETFs hold."
                         .format(label, pct))
    exposures = []
    for h in holdings:
        if h["kind"] not in STOCKLIKE or not h.get("symbol"):
            continue
        opts = [o for o in options if (o.get("underlying") or "").upper() == h["symbol"].upper()]
        if opts:
            exposures.append({
                "symbol": h["symbol"], "shares": h["quantity"], "accounts": h["accounts"],
                "options": [{"option_type": o["option_type"], "contracts": o["contracts"],
                             "strike": o["strike"], "expiry": o["expiry"],
                             "notional_shares": _r((o["contracts"] or 0) * o["multiplier"], 2)} for o in opts],
                "note": "Option exposure is shown as the shares the contracts control, not delta-adjusted: "
                        "the connection supplies no greeks.",
            })
    concentration = {
        "top1_pct": _r(long_weights[0], 1) if long_weights else None,
        "top5_pct": _r(sum(long_weights[:5]), 1) if long_weights else None,
        "effective_holdings": _r(1.0 / hhi, 1) if hhi else None,
        "flags": flags,
        "combined_exposure": exposures,
        "basis": "Shares of long market value (stocks, ETFs, funds, bonds, crypto, long options), "
                 "in US dollars. Cash and short positions are not in the denominator.",
    }

    # --------------------------------------------------------- performance
    with_basis = [h for h in holdings if h["cost_basis"] is not None]
    covered_value = sum(abs(usd(h["market_value"], h["currency"]) or 0.0) for h in with_basis)
    all_value = sum(abs(usd(h["market_value"], h["currency"]) or 0.0) for h in holdings)
    upl_by_ccy: Dict[str, float] = {}
    for h in with_basis:
        upl_by_ccy[h["currency"]] = upl_by_ccy.get(h["currency"], 0.0) + (h["unrealized_pl"] or 0.0)
    performance = {
        "unrealized_pl_by_currency": {k: round(v, 2) for k, v in upl_by_ccy.items()},
        "positions_with_basis": len(with_basis),
        "positions_total": len(holdings),
        "basis_coverage_pct": _r(100.0 * covered_value / all_value, 1) if all_value else None,
        "note": "Unrealised gain is market value minus the broker's average cost, summed only over "
                "positions that have one. It is not a return: deposits, withdrawals, dividends and "
                "realised trades are not in it, and Optic has no transaction history from the "
                "connection to compute a time-weighted return.",
    }
    if len(with_basis) < len(holdings):
        missing = [h["symbol"] or h["description"] for h in holdings if h["cost_basis"] is None]
        notes.append("The broker supplied no cost basis for {}, so unrealised gain leaves {} out."
                     .format(", ".join(missing[:5]) + ("..." if len(missing) > 5 else ""),
                             "it" if len(missing) == 1 else "them"))

    # ------------------------------------------------- earnings and prices
    earnings: List[Dict[str, Any]] = []
    price_checks: List[Dict[str, Any]] = []
    looked = 0
    for h in holdings:
        if h["kind"] not in STOCKLIKE or not h.get("symbol") or looked >= MAX_LOOKUPS:
            continue
        looked += 1
        try:
            day = earnings_of(h["symbol"])
        except Exception:                                       # noqa: BLE001
            day = None
        days = _days_until(day, today)
        if days is not None and 0 <= days <= EARNINGS_WINDOW_DAYS:
            earnings.append({"symbol": h["symbol"], "date": str(day)[:10], "days": days,
                             "weight_pct": h["weight_pct"], "accounts": h["accounts"],
                             "has_options": any((o.get("underlying") or "").upper() == h["symbol"].upper()
                                                for o in options)})
        if h["currency"] == "USD" and h.get("price"):
            try:
                mine = _num(optic_price(h["symbol"]))
            except Exception:                                   # noqa: BLE001
                mine = None
            if mine:
                gap = 100.0 * (mine - h["price"]) / h["price"]
                if abs(gap) >= PRICE_GAP_PCT:
                    price_checks.append({"symbol": h["symbol"], "broker_price": h["price"],
                                         "optic_price": _r(mine, 4), "gap_pct": _r(gap, 1)})
    earnings.sort(key=lambda e: e["days"])
    if price_checks:
        notes.append("Broker prices for {} differ from Optic's delayed quote by more than {:.0f}%. "
                     "Broker values are as of the last sync; Optic's quotes are about 15 minutes "
                     "delayed. Neither is a live price.".format(
                         ", ".join(c["symbol"] for c in price_checks[:5]), PRICE_GAP_PCT))

    if options:
        assumed = any(o["multiplier_assumed"] for o in options)
        notes.append("Option values are estimates: contracts x the broker's last price x the contract "
                     "multiplier{}. The connection supplies no greeks, and a multi-leg strategy arrives "
                     "as separate legs.".format(
                         " (assumed 100, or 10 for minis, where the provider did not send one)"
                         if assumed else ""))
    if unsupported:
        notes.append("{} holding{} could not be valued and {} left out of every total and weight."
                     .format(len(unsupported), "" if len(unsupported) == 1 else "s",
                             "is" if len(unsupported) == 1 else "are"))
    if cash_equivalents:
        notes.append("Money-market and other cash-equivalent holdings ({}) are counted once, inside cash, "
                     "because the broker's cash balance already includes them."
                     .format(", ".join(c["symbol"] or c["description"] or "unnamed" for c in cash_equivalents[:5])))
    if any(h["kind"] == "bond" for h in holdings):
        notes.append("Bonds are valued as quantity x the broker's price. Brokers quote bonds in "
                     "different conventions, so check bond values against the broker.")

    summary = snapshot_summary(holdings, options, by_ccy, combined, acct_out)
    changes = diff(previous, summary) if previous else None
    if changes:
        changes["since"] = previous.get("taken_at")

    return {
        "accounts": acct_out,
        "accounts_counted": counted,
        # The broker's own time where the provider gave one; on a once-a-day
        # plan it can be a day older than when Optic fetched it (review M4).
        "as_of": {"oldest_sync": min(sync_times) if sync_times else None,
                  "newest_sync": max(sync_times) if sync_times else None,
                  "oldest_broker": min(broker_times) if broker_times else None,
                  "broker_complete": bool(broker_times) and len(broker_times) == counted},
        "totals": {"by_currency": by_ccy, "combined_usd": combined},
        "holdings": holdings,
        "options": options,
        "cash": [{"currency": c, "amount": round(v, 2)} for c, v in sorted(cash_by_ccy.items())],
        "unsupported": unsupported,
        "cash_equivalents": cash_equivalents,
        "allocation": {"by_kind": shares(by_kind, KIND_LABELS),
                       "by_sector": shares(sectors),
                       "by_account": shares(by_account)},
        "concentration": concentration,
        "performance": performance,
        "earnings_ahead": earnings,
        "price_checks": price_checks,
        "changes": changes,
        "notes": notes,
        "summary": summary,
    }


# ------------------------------------------------------------ change tracking


def _okey(o: Dict[str, Any]) -> str:
    return "option:{}".format(o.get("occ") or "{}:{}:{}:{}".format(
        o.get("underlying"), o.get("option_type"), o.get("strike"), o.get("expiry")))


def snapshot_summary(holdings: Iterable[Dict[str, Any]], options: Iterable[Dict[str, Any]],
                     by_ccy: Dict[str, Dict[str, float]], combined: Optional[Dict[str, Any]],
                     accounts: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    positions = {}
    for h in holdings:
        positions[h["key"]] = {"symbol": h["symbol"], "kind": h["kind"], "currency": h["currency"],
                               "qty": h["quantity"], "price": h["price"], "value": h["market_value"]}
    for o in options:
        positions[_okey(o)] = {"symbol": o.get("underlying"), "kind": "option", "currency": o["currency"],
                               "qty": o["contracts"], "price": o["price"], "value": o["market_value_est"],
                               "label": "{} {} {} {}".format(o.get("underlying"), o.get("strike"),
                                                             o.get("option_type"), o.get("expiry"))}
    return {"taken_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "by_currency": {c: b.get("total") for c, b in by_ccy.items()},
            "combined_usd": (combined or {}).get("value"),
            "accounts": sorted(a["id"] for a in accounts if a.get("selected") and a.get("lines_total") is not None),
            "positions": positions}


def account_detail(acct: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """One account's own values for a snapshot. Kept for every account with
    data, selected or not, so history can later be read for whatever accounts
    the reader picks, and so a disconnected account can be cut out of stored
    snapshots without guessing (see drop_accounts)."""
    p = acct.get("payload")
    if not p:
        return None
    acct_ccy = (acct.get("currency") or "USD").upper()
    balances_ok = "balances" not in (p.get("problems") or [])
    positions: Dict[str, Dict[str, Any]] = {}
    total: Dict[str, float] = {}
    cash: Dict[str, float] = {}
    complete = not p.get("problems")
    for pos in p.get("positions") or []:
        kind = pos.get("kind") or "other"
        qty, price = _num(pos.get("quantity")), _num(pos.get("price"))
        ccy = (pos.get("currency") or acct_ccy).upper()
        if pos.get("cash_equivalent") and balances_ok:
            continue
        if kind not in VALUED_KINDS or qty is None or price is None:
            complete = False
            continue
        key = "{}:{}:{}".format(kind, (pos.get("symbol") or pos.get("description") or "").upper(), ccy)
        e = positions.setdefault(key, {"symbol": pos.get("symbol"), "kind": kind, "currency": ccy,
                                       "qty": 0.0, "value": 0.0})
        e["qty"] += qty
        e["value"] += qty * price
        total[ccy] = total.get(ccy, 0.0) + qty * price
    for opt in p.get("options") or []:
        n, price = _num(opt.get("contracts")), _num(opt.get("price"))
        ccy = (opt.get("currency") or acct_ccy).upper()
        if n is None or price is None:
            complete = False
            continue
        mv = n * price * multiplier(opt)
        o = dict(opt, currency=ccy, strike=_num(opt.get("strike")))
        e = positions.setdefault(_okey(o), {
            "symbol": opt.get("underlying"), "kind": "option", "currency": ccy, "qty": 0.0, "value": 0.0,
            "multiplier": multiplier(opt), "label": "{} {} {} {}".format(opt.get("underlying"), o.get("strike"), opt.get("option_type"),
                                          opt.get("expiry"))})
        e["qty"] += n
        e["value"] += mv
        total[ccy] = total.get(ccy, 0.0) + mv
    for c in p.get("cash") or []:
        amt = _num(c.get("amount"))
        if amt is None:
            continue
        ccy = (c.get("currency") or acct_ccy).upper()
        cash[ccy] = cash.get(ccy, 0.0) + amt
        total[ccy] = total.get(ccy, 0.0) + amt
    for e in positions.values():
        e["price"] = _r(e["value"] / e["qty"] / (e.get("multiplier") or 1), 4) if e["qty"] else None
        e["value"] = _r(e["value"])
    return {"name": acct.get("name"), "currency": acct_ccy, "selected": bool(acct.get("selected")),
            "complete": complete, "total": {c: _r(v) for c, v in total.items()},
            "cash": {c: _r(v) for c, v in cash.items()}, "positions": positions,
            "broker_total": _num(p.get("total_value"))}


def drop_accounts(summary: Dict[str, Any], gone: Iterable[str]) -> Optional[Dict[str, Any]]:
    """A stored snapshot without the given accounts, its portfolio-level
    figures rebuilt from what remains; None when it cannot be separated (a
    snapshot from before per-account detail was kept), which the caller
    deletes rather than keep a disconnected account's data."""
    by = summary.get("by_account")
    if not isinstance(by, dict):
        return None
    gone = set(gone)
    keep = {aid: d for aid, d in by.items() if aid not in gone}
    selected = [aid for aid in summary.get("accounts") or [] if aid in keep]
    merged: Dict[str, Dict[str, Any]] = {}
    by_ccy: Dict[str, float] = {}
    for aid in selected:
        d = keep[aid] or {}
        for k, e in (d.get("positions") or {}).items():
            m = merged.setdefault(k, dict({kk: vv for kk, vv in e.items() if kk not in ("qty", "value", "price")},
                                          qty=0.0, value=0.0))
            m["qty"] += e.get("qty") or 0.0
            m["value"] += e.get("value") or 0.0
        for c, v in (d.get("total") or {}).items():
            by_ccy[c] = by_ccy.get(c, 0.0) + (v or 0.0)
    for m in merged.values():
        m["price"] = _r(m["value"] / m["qty"] / (m.get("multiplier") or 1), 4) if m["qty"] else None
        m["value"] = _r(m["value"])
    return dict(summary, by_account=keep, accounts=selected, positions=merged,
                by_currency={c: _r(v) for c, v in by_ccy.items()},
                combined_usd=_r(by_ccy.get("USD", 0.0)) if set(by_ccy) <= {"USD"} else None)


SPLIT_RATIOS = (2.0, 3.0, 4.0, 5.0, 10.0, 0.5, 1 / 3.0, 0.25, 0.2, 0.1)


def diff(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """What moved between two syncs, split into quantity changes (something was
    bought, sold or adjusted) and price changes (the market moved)."""
    op, np_ = old.get("positions") or {}, new.get("positions") or {}
    added, removed, changed = [], [], []
    price_effect: Dict[str, float] = {}
    for k, n in np_.items():
        o = op.get(k)
        if not o:
            added.append({"symbol": n.get("symbol"), "label": n.get("label"), "kind": n["kind"],
                          "qty": n["qty"], "value": n["value"]})
            continue
        oq, nq = _num(o.get("qty")) or 0.0, _num(n.get("qty")) or 0.0
        if abs(nq - oq) > 1e-9:
            item = {"symbol": n.get("symbol"), "label": n.get("label"), "kind": n["kind"],
                    "from_qty": oq, "to_qty": nq}
            if oq and nq:
                ratio = nq / oq
                po, pn = _num(o.get("price")), _num(n.get("price"))
                if po and pn and any(abs(ratio - r) < 0.01 * r for r in SPLIT_RATIOS) \
                        and abs((po / pn) - ratio) < 0.15 * ratio:
                    item["looks_like"] = ("a split or similar corporate action: quantity and price moved "
                                          "by the same ratio, so it is probably not a trade")
            changed.append(item)
        po, pn = _num(o.get("price")), _num(n.get("price"))
        if po is not None and pn is not None and oq and nq and n["kind"] != "option":
            ccy = n.get("currency") or "USD"
            held = min(abs(oq), abs(nq)) * (1 if oq > 0 else -1) if (oq > 0) == (nq > 0) else 0.0
            price_effect[ccy] = price_effect.get(ccy, 0.0) + held * (pn - po)
    for k, o in op.items():
        if k not in np_:
            removed.append({"symbol": o.get("symbol"), "label": o.get("label"), "kind": o["kind"],
                            "qty": o["qty"], "value": o["value"]})
    value_change = {}
    for ccy, v in (new.get("by_currency") or {}).items():
        before = (old.get("by_currency") or {}).get(ccy)
        if before is not None and v is not None:
            value_change[ccy] = round(v - before, 2)
    same_accounts = (old.get("accounts") or []) == (new.get("accounts") or [])
    return {
        "added": added, "removed": removed, "quantity_changed": changed,
        "value_change_by_currency": value_change,
        "price_effect_by_currency": {k: round(v, 2) for k, v in price_effect.items()},
        "same_accounts": same_accounts,
        "note": "Value change includes deposits, withdrawals and trades as well as price moves; "
                "the price effect is the part explained by prices on quantities held at both syncs."
                + ("" if same_accounts else " The set of accounts counted changed between these syncs, "
                   "so the totals are not like for like."),
    }
