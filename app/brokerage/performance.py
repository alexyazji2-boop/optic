"""Performance for the Brokerage workspace: how the accounts in view did,
measured two ways, against a benchmark, with where the money came from.

Pure: data in, dict out. No network and no database; `workspace.py` reads the
stored transactions, balance history and snapshots and passes them in.

Two returns, because they answer different questions and can disagree in sign.
The time-weighted return (TWR) is how the investments did, with the timing of
deposits and withdrawals removed; it is the one compared with a benchmark. The
money-weighted return (MWR, an XIRR) is how the reader's money did, timing
included: a large deposit just before a fall drags it down while the TWR does
not move. `tests/test_brokerage_performance.py` has a worked case where the
TWR is 0% and the MWR is about -67% a year.

Values come from three places and are never blended silently (PLAN.md,
"History"): the provider's daily balance estimate, Optic's own daily snapshots
("collected"), and the latest sync as the last point dated today. Each point
records which one it came from, and a switch between them is a limitation,
because the provider's reconstruction and Optic's valuation of the holdings are
measured differently: the sandbox's estimate is deliberately "not meant to match
the holdings", and a TWR chained across the switch would book the difference
as a return.

Currencies are never added together. A scope with accounts in more than one
currency is measured per currency in `by_currency`, and the top level says a
combined return needs FX that Optic does not apply here.

Output keys (stable; `workspace.py` and the front end read them):

  scope         {"accounts": [{"id", "name", "currency"}], "count"}
  currency      the scope's currency, or None when the accounts are in more
                than one currency (then read `by_currency`)
  period        {"requested", "start", "end", "measured_start", "measured_end",
                 "days", "covered_days"}
  sources       {"values": "provider_estimate" | "collected" | "mixed" | "none",
                 "values_label", "points": {source: count}, "provider_window",
                 "collected_days", "switches", "gaps", "transactions"}
  returns       {"available", "reason",
                 "twr": {"pct", "annualized_pct" | None, "annualized", "method",
                         "covered_days", "excluded"},
                 "mwr": {"available", "reason", "irr_annualized_pct", "period_pct",
                         "converged", "method"},
                 "benchmark": {"symbol", "twr_pct", "method", "available",
                               "reason"} | None,
                 "excess_pct", "excess_method"}
  series        [{"date", "value", "net_flow", "cum_net_flow", "cum_twr_pct",
                  "cum_benchmark_pct", "source", "measured"}]
  series_fields {field: what it is}; value and cum_net_flow are labelled as
                not a return
  flows         {"available", "window", "currency", "deposits", "withdrawals",
                 "net_external", "counts", "internal_transfers", "in_kind",
                 "unvalued", "by_month", "items"}
  income        {"available", "window", "currency", "dividends", "reinvested",
                 "interest", "fees", "taxes", "net", "stock_dividends",
                 "trade_commissions", "by_symbol"}
  attribution   {"available", "reason", "window", "currency", "positions",
                 "sum_contributions", "total_change", "flows", "remainder",
                 "average_capital", "skipped_pairs", "method", ...}
  by_currency   {ccy: {"currency", "period", "sources", "returns", "series",
                 "flows", "income", "attribution", "limitations"}}, only when
                the scope mixes currencies
  limitations   sentences: every assumption this computation actually used
  definitions   DEFINITIONS
  version       VERSION

Money is rounded to cents and percentages to 2 dp at the output boundary only;
every chain is computed at full precision.
"""

from __future__ import annotations

import calendar
import math
from bisect import bisect_right
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .providers import EXTERNAL_FLOW_TYPES

VERSION = "performance-2026-10-15.1"
PERIODS = ("1m", "3m", "ytd", "1y", "all")

INCOME_TYPES = ("DIVIDEND", "SUBSTITUTE_DIVIDEND", "INTEREST", "REI", "STOCK_DIVIDEND")
COST_TYPES = ("FEE", "TAX")
TRADE_TYPES = ("BUY", "SELL", "OPTIONEXPIRATION", "OPTIONASSIGNMENT", "OPTIONEXERCISE")
OTHER_TYPES = ("SPLIT", "ADJUSTMENT")

# The direction a flow type implies when the amount cannot say: an in-kind
# transfer can arrive with no amount at all (the sandbox's margin account has
# one, units 1, no price), and then only the type knows which way it went.
DIRECTION_OF_TYPE = {"CONTRIBUTION": 1, "EXTERNAL_ASSET_TRANSFER_IN": 1,
                     "WITHDRAWAL": -1, "EXTERNAL_ASSET_TRANSFER_OUT": -1}

MATCH_DAYS = 3                 # an internal transfer's legs can post up to three calendar days apart
MATCH_CENTS = 0.01
MATCH_RELATIVE = 0.001         # 0.1%: a wire fee or a rounding at the receiving broker
ANNUALISE_MIN_DAYS = 365
SHORT_MWR_DAYS = 30
XIRR_LOW, XIRR_HIGH = -0.99, 10.0
STALE_BENCHMARK_DAYS = 4       # a long weekend is three days; more than that is a feed that stopped

TWR_METHOD = ("Daily returns chained: (value minus that day's net external flow) divided by the previous "
              "value, minus one. Across a gap of more than one day, Modified Dietz. Flows count at the end "
              "of their day.")
MWR_METHOD = ("XIRR on a 365-day year: the starting value as money in, each external flow on its date, the "
              "ending value as money out. Newton's method, falling back to bisection on -99% to +1000%.")
EXCESS_METHOD = ("A simple difference of two time-weighted returns over the same dates, in percentage "
                 "points. Not risk-adjusted.")
ATTRIBUTION_METHOD = ("For each pair of consecutive collected days: shares held on the first day times the "
                      "change in price to the second (an option: its value on the first day times the "
                      "relative change in its price). Remainder = change in value minus net flows minus "
                      "the contributions.")

SOURCE_LABELS = {"provider_estimate": "estimated by the provider", "collected": "collected by Optic",
                 "current": "latest sync", "mixed": "mixed sources (see switches)", "none": "no values"}

DEFINITIONS: Dict[str, str] = {
    "time_weighted_return": (
        "How the investments themselves did, with the effect of when money was added or taken out removed. "
        "Each day's return is the value at the end of the day, less that day's net deposits, divided by the "
        "previous day's value, minus one; the days are then multiplied together. This is the figure to "
        "compare with a benchmark."),
    "modified_dietz": (
        "Used across a gap of more than one day between values. Return = (end value minus start value minus "
        "net flows) divided by (start value plus each flow weighted by the fraction of the gap remaining "
        "after it). A flow on the last day of the gap has weight zero, which is the daily formula above."),
    "money_weighted_return": (
        "How your money did, counting when you added or withdrew it. It is the annual rate (XIRR, 365-day "
        "year) at which the starting value, each deposit and withdrawal on its date, and the ending value net "
        "to zero. A large deposit just before a fall pulls it below the time-weighted return. The period "
        "figure is that rate compounded over the period's own length."),
    "annualised": (
        "A return is annualised only when it covers at least 365 days. A shorter return is shown for its own "
        "period, because annualising it would project it forward."),
    "flow_timing": (
        "Deposits and withdrawals count at the end of the day they are dated, so they earn nothing that day. "
        "A transaction is dated by its trade date, or by its settlement date when it has no trade date."),
    "external_flow": (
        "Money or securities moving into or out of the accounts in view: contributions, withdrawals, transfers, "
        "and transfers of assets in or out. Positive is money in, negative is money out."),
    "internal_transfer": (
        "An outflow from one account in view and an inflow of the same amount (within one cent or 0.1%, same "
        "currency) into another account in view within three calendar days. It is money moving between your "
        "own accounts, so it is not a deposit or a withdrawal. When the two sides post on different days, each "
        "side is applied on its own date, so the days in transit are neither a loss nor a gain."),
    "in_kind_transfer": (
        "Securities moved rather than cash. Valued at the broker's amount when it gives one, otherwise at units "
        "times the broker's price (an estimate), otherwise not valued, in which case returns across that date "
        "are not measured."),
    "investment_income": (
        "Dividends, substitute dividends, interest and reinvested dividends, at the amount the broker reported. "
        "Stock dividends add shares rather than cash, so they are counted but carry no amount. Interest keeps "
        "its sign: negative is interest paid, for example on margin."),
    "costs": (
        "Fees and taxes the broker reported as transactions of their own, shown as the amount paid (positive), "
        "net of any refund."),
    "trades": (
        "Buys, sells, and option expirations, assignments and exercises. They move money between cash and "
        "holdings inside an account, so they are not flows and do not change a return by themselves."),
    "other": "Splits and adjustments: counted, not treated as money in or out.",
    "benchmark_total_return": (
        "The benchmark's closing price with each dividend reinvested at the close on its ex-dividend date. On a "
        "day the market was closed it keeps its last close. Its time-weighted return is measured over exactly "
        "the stretches of dates yours is."),
    "excess_return": (
        "Your time-weighted return minus the benchmark's: a simple difference of two time-weighted returns over "
        "the same dates, in percentage points. It is not adjusted for risk."),
    "value_sources": (
        "Estimated by the provider: the provider's reconstruction of each account's daily balance. Collected: "
        "Optic's own daily snapshot of the holdings. Latest sync: the holdings as last synced, dated today. "
        "Optic uses the provider's estimate on dates every account in view has it, its own snapshots outside "
        "that window, and the latest sync as the last value. It never fills a gap by interpolation."),
    "attribution": (
        "Over days Optic collected itself: each holding's contribution is the shares held at the end of one day "
        "times the change in its price to the next day (an option uses its value times the relative change in "
        "its price). The rest of the change in value is deposits and withdrawals plus a remainder: trades during "
        "a day, holdings opened or closed, dividends and interest."),
    "cumulative_series": (
        "cum_twr_pct and cum_benchmark_pct are cumulative time-weighted returns from the first date, on the "
        "same dates. value and cum_net_flow are a balance and a running total of money in and out: they are "
        "not returns and are never compared with the benchmark."),
}

SERIES_FIELDS = {
    "date": "The valuation date.",
    "value": "The value of the accounts in view on that date. A balance, not a return.",
    "net_flow": "Net deposits minus withdrawals since the previous date (transfers between accounts in view "
                "excluded). Not a return.",
    "cum_net_flow": "Running total of net_flow from the first date. Not a return.",
    "cum_twr_pct": "Cumulative time-weighted return from the first date, in percent.",
    "cum_benchmark_pct": "The benchmark's cumulative total return over the same dates, in percent.",
    "source": "Where the value came from: provider_estimate, collected or current.",
    "measured": "False when the return since the previous date could not be measured and was left out.",
}


# ------------------------------------------------------------------ helpers


def _num(v: Any) -> Optional[float]:
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _day(v: Any) -> Optional[date]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def _iso(d: Optional[date]) -> Optional[str]:
    return d.isoformat() if d else None


def _money(v: Optional[float]) -> Optional[float]:
    return None if v is None else round(v + 0.0, 2)


def _pct(v: Optional[float]) -> Optional[float]:
    return None if v is None else round(100.0 * v + 0.0, 2)


def _plural(n: int, word: str, many: Optional[str] = None) -> str:
    return "{} {}".format(n, word if n == 1 else (many or word + "s"))


def _months_back(today: date, months: int) -> date:
    y, m = today.year, today.month - months
    while m <= 0:
        m += 12
        y -= 1
    return date(y, m, min(today.day, calendar.monthrange(y, m)[1]))


def period_start(period: str, today: date, earliest: Optional[date] = None) -> date:
    """The requested start. YTD starts at the previous year's last day, so the
    first trading day of the year has a value to be measured from."""
    if period == "1m":
        return _months_back(today, 1)
    if period == "3m":
        return _months_back(today, 3)
    if period == "ytd":
        return date(today.year - 1, 12, 31)
    if period == "1y":
        return _months_back(today, 12)
    if period == "all":
        return min(earliest, today) if earliest else today
    raise ValueError("period must be one of " + ", ".join(PERIODS))


def classify(kind: Optional[str]) -> str:
    """external_flow | income | cost | trade | other | unrecognised."""
    k = (kind or "").upper()
    if k in EXTERNAL_FLOW_TYPES:
        return "external_flow"
    if k in INCOME_TYPES:
        return "income"
    if k in COST_TYPES:
        return "cost"
    if k in TRADE_TYPES:
        return "trade"
    if k in OTHER_TYPES:
        return "other"
    return "unrecognised"


def flow_value(activity: Dict[str, Any]) -> Dict[str, Any]:
    """The signed value of one external flow and how it was reached:
    {"value": float | None, "direction": 1 | -1 | None, "in_kind": bool,
     "valued_by": "amount" | "units_x_price" | "unknown"}."""
    kind = (activity.get("type") or "").upper()
    amount, units, price = (_num(activity.get("amount")), _num(activity.get("units")),
                            _num(activity.get("price")))
    in_kind = bool(units) or bool(activity.get("option_occ")) or (bool(activity.get("symbol")) and not amount)
    direction = DIRECTION_OF_TYPE.get(kind)
    if direction is None:
        if amount:
            direction = 1 if amount > 0 else -1
        elif units:
            direction = 1 if units > 0 else -1
    if not in_kind:
        # Cash: the amount's own sign is the account's side (providers.Activity),
        # which also carries a reversed deposit correctly as money out.
        if amount is None:
            return {"value": None, "direction": direction, "in_kind": False, "valued_by": "unknown"}
        return {"value": amount, "direction": 1 if amount > 0 else (-1 if amount < 0 else direction),
                "in_kind": False, "valued_by": "amount"}
    if direction is None:
        return {"value": None, "direction": None, "in_kind": True, "valued_by": "unknown"}
    # A zero amount on an in-kind transfer means the broker did not value it,
    # not that the shares were worth nothing.
    if amount:
        return {"value": direction * abs(amount), "direction": direction, "in_kind": True, "valued_by": "amount"}
    if units and price:
        return {"value": direction * abs(units * price), "direction": direction, "in_kind": True,
                "valued_by": "units_x_price"}
    return {"value": None, "direction": direction, "in_kind": True, "valued_by": "unknown"}


def _rows(acct: Dict[str, Any], acts: Optional[Iterable[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    out = []
    for i, a in enumerate(acts or []):
        kind = (a.get("type") or "").upper()
        row = {"key": (acct["id"], i), "id": a.get("id"), "account": acct["id"], "account_name": acct["name"],
               "type": kind, "class": classify(kind),
               "date": _day(a.get("trade_date")) or _day(a.get("settlement_date")),
               "currency": (a.get("currency") or acct["currency"]).upper(), "symbol": a.get("symbol"),
               "units": _num(a.get("units")), "price": _num(a.get("price")), "amount": _num(a.get("amount")),
               "fee": _num(a.get("fee")), "description": a.get("description") or "", "pair": None}
        if row["class"] == "external_flow":
            row.update(flow_value(a))
            if row["currency"] != acct["currency"]:
                # No FX here: a flow in another currency cannot be added to this
                # account's values, so it is treated as one that could not be valued.
                row.update(value=None, valued_by="other_currency")
        out.append(row)
    return out


# ------------------------------------------------------------- primitives


def xirr(cashflows: Sequence[Tuple[Any, float]], low: float = XIRR_LOW, high: float = XIRR_HIGH) -> Dict[str, Any]:
    """The annual rate at which dated cash flows net to zero on a 365-day year,
    as Excel's XIRR defines it. {"rate", "converged", "method"}.

    Newton first, from 10%, because it is fast and exact near the answer;
    bisection on [low, high] when Newton leaves the bracket or stalls, because
    Newton on an NPV curve with a large early outflow can overshoot below -100%,
    where (1 + r) ** t is not real."""
    cf = [(_day(d), float(a)) for d, a in cashflows if a and _day(d) is not None]
    if not any(a > 0 for _, a in cf) or not any(a < 0 for _, a in cf):
        return {"rate": None, "converged": False, "method": "needs money both in and out"}
    t0 = min(d for d, _ in cf)
    ts = [((d - t0).days / 365.0, a) for d, a in cf]
    scale = sum(abs(a) for _, a in ts)
    tol = 1e-10 * scale

    def npv(r: float) -> float:
        try:
            return sum(a / (1.0 + r) ** t for t, a in ts)
        except (OverflowError, ZeroDivisionError):
            return float("inf")

    def slope(r: float) -> float:
        try:
            return sum(-t * a / (1.0 + r) ** (t + 1.0) for t, a in ts)
        except (OverflowError, ZeroDivisionError):
            return float("nan")

    r = 0.1
    for _ in range(100):
        f = npv(r)
        if not math.isfinite(f):
            break
        if abs(f) <= tol:
            return {"rate": r, "converged": True, "method": "newton"}
        d = slope(r)
        if not math.isfinite(d) or d == 0:
            break
        nxt = r - f / d
        if not (low < nxt < high) or not math.isfinite(nxt):
            break
        r = nxt
    lo, hi = low, high
    f_lo, f_hi = npv(lo), npv(hi)
    if not (math.isfinite(f_lo) and math.isfinite(f_hi)) or f_lo * f_hi > 0:
        return {"rate": None, "converged": False, "method": "no rate between -99% and +1000% a year"}
    mid = lo
    for _ in range(400):
        mid = (lo + hi) / 2.0
        f_mid = npv(mid)
        if abs(f_mid) <= tol or (hi - lo) < 1e-14:
            return {"rate": mid, "converged": True, "method": "bisection"}
        if (f_mid < 0) == (f_lo < 0):
            lo, f_lo = mid, f_mid
        else:
            hi = mid
    return {"rate": mid, "converged": abs(npv(mid)) <= 1e-6 * scale, "method": "bisection"}


def modified_dietz(v0: float, v1: float, flows: Iterable[Tuple[Any, float]], d0: Any, d1: Any) -> Optional[float]:
    """Return over (d0, d1] with flows at the end of their day, weighted by the
    fraction of the gap remaining after them. None when the capital at work
    (the denominator) is zero or negative: there is no return to speak of."""
    d0, d1 = _day(d0), _day(d1)
    span = (d1 - d0).days
    if span <= 0:
        return None
    net = weighted = 0.0
    for d, f in flows:
        net += f
        weighted += f * (d1 - _day(d)).days / span
    denom = v0 + weighted
    if denom <= 0:
        return None
    return (v1 - v0 - net) / denom


def benchmark_index(closes: Iterable[Sequence[Any]],
                    dividends: Iterable[Sequence[Any]] = ()) -> List[Tuple[date, float]]:
    """A total-return index, 1.0 at the first close: each day's level is the
    previous level times (close + dividends going ex since the previous close)
    divided by the previous close, which is a dividend reinvested at its
    ex-date close. A dividend going ex on a day with no close is applied at
    the next close."""
    cl = sorted((d, c) for d, c in ((_day(p[0]), _num(p[1])) for p in closes or []) if d and c and c > 0)
    dedup: Dict[date, float] = {}
    for d, c in cl:
        dedup[d] = c
    cl = sorted(dedup.items())
    if not cl:
        return []
    divs = sorted((d, v) for d, v in ((_day(p[0]), _num(p[1])) for p in dividends or []) if d and v)
    out = [(cl[0][0], 1.0)]
    level, j = 1.0, 0
    while j < len(divs) and divs[j][0] <= cl[0][0]:
        j += 1
    for k in range(1, len(cl)):
        d, c = cl[k]
        div = 0.0
        while j < len(divs) and divs[j][0] <= d:
            div += divs[j][1]
            j += 1
        level *= (c + div) / cl[k - 1][1]
        out.append((d, level))
    return out


def _level_on(index: List[Tuple[date, float]], dates: List[date], d: date) -> Optional[float]:
    i = bisect_right(dates, d) - 1
    return index[i][1] if i >= 0 else None


def _close_enough(a: float, b: float) -> bool:
    diff = abs(abs(a) - abs(b))
    return diff <= MATCH_CENTS + 1e-9 or diff <= MATCH_RELATIVE * max(abs(a), abs(b))


def match_internal_transfers(flows: List[Dict[str, Any]]) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """Pairs (outflow, inflow) between two different accounts, same currency,
    within MATCH_DAYS, equal within a cent or 0.1%. Any external-flow type
    pairs with any other: a broker can report the two sides as WITHDRAWAL and
    CONTRIBUTION rather than TRANSFER. Legs without a value pair on the same
    symbol and number of units. Closest dates first, then closest amounts,
    so one leg is never claimed by two pairs."""
    outs = [f for f in flows if f.get("direction") == -1 and f.get("date")]
    ins = [f for f in flows if f.get("direction") == 1 and f.get("date")]
    cands = []
    for o in outs:
        for i in ins:
            if i["account"] == o["account"] or i["currency"] != o["currency"]:
                continue
            gap = abs((i["date"] - o["date"]).days)
            if gap > MATCH_DAYS:
                continue
            if o.get("value") is not None and i.get("value") is not None:
                if _close_enough(o["value"], i["value"]):
                    cands.append((gap, abs(abs(o["value"]) - abs(i["value"])), o["date"], o["key"], i["key"], o, i))
            elif (o.get("symbol") and o.get("symbol") == i.get("symbol") and o.get("units") and i.get("units")
                  and abs(abs(o["units"]) - abs(i["units"])) <= 1e-9):
                cands.append((gap, 0.0, o["date"], o["key"], i["key"], o, i))
    cands.sort(key=lambda c: c[:5])
    used, pairs = set(), []
    for *_, o, i in cands:
        if o["key"] in used or i["key"] in used:
            continue
        used.add(o["key"])
        used.add(i["key"])
        pairs.append((o, i))
    return pairs


# ------------------------------------------------------------- value series


def _snapshot_days(snapshots: Iterable[Dict[str, Any]], start: Optional[date],
                   today: date) -> List[Tuple[date, Dict[str, Any]]]:
    by_day: Dict[date, Dict[str, Any]] = {}
    for s in snapshots or []:
        d = _day(str(s.get("taken_at") or "")[:10])
        if d is None or d > today or (start and d < start):
            continue
        prev = by_day.get(d)
        if prev is None or str(s.get("taken_at")) >= str(prev.get("taken_at")):
            by_day[d] = s
    return sorted(by_day.items())


def _account_total(entry: Any, ccy: str) -> Tuple[Optional[float], Optional[str]]:
    """One account's collected value in its own currency, or why not."""
    if not isinstance(entry, dict):
        return None, "missing"
    if entry.get("complete") is False:
        return None, "incomplete"
    total = entry.get("total") or {}
    for k, v in total.items():
        if str(k).upper() != ccy and _num(v):
            return None, "other_currency"
    v = _num(total.get(ccy))
    return (0.0 if v is None else v), None


def _value_points(ccy: str, accts: List[Dict[str, Any]], histories: Dict[str, Any], snapshots: Any,
                  current: Dict[str, Any], today: date) -> Tuple[List[Tuple[date, float, str]], Dict[str, Any]]:
    aids = [a["id"] for a in accts]
    info: Dict[str, Any] = {"provider": {}, "provider_currency_mismatch": [], "collected": {}, "dropped": {},
                            "current_missing": [], "current_as_of": [], "provider_window": None}
    prov: Dict[str, Dict[date, float]] = {}
    for a in accts:
        h = (histories or {}).get(a["id"]) or {}
        pts: Dict[date, float] = {}
        hccy = (h.get("currency") or a["currency"]).upper()
        if hccy != ccy and h.get("points"):
            info["provider_currency_mismatch"].append(a["name"])
        else:
            for p in h.get("points") or []:
                if not isinstance(p, (list, tuple)) or len(p) < 2:
                    continue
                d, v = _day(p[0]), _num(p[1])
                if d and v is not None and d <= today:
                    pts[d] = v
        prov[a["id"]] = pts
        info["provider"][a["id"]] = (min(pts), max(pts), len(pts)) if pts else None
    shared = set.intersection(*(set(prov[i]) for i in aids)) if aids and all(prov[i] for i in aids) else set()
    points: Dict[date, Tuple[float, str]] = {d: (sum(prov[i][d] for i in aids), "provider_estimate") for d in shared}
    if shared:
        info["provider_window"] = (min(shared), max(shared))
    for d, s in _snapshot_days(snapshots, None, today):
        by = s.get("by_account") if isinstance(s.get("by_account"), dict) else {}
        total, why = 0.0, None
        for aid in aids:
            v, why = _account_total(by.get(aid), ccy)
            if why:
                break
            total += v
        if why:
            info["dropped"][d] = why
            continue
        info["collected"][d] = total
        # Inside the provider's window the provider's points are used and its
        # missing days stay gaps: interleaving the two sources day by day would
        # book the difference between them as a return every other day.
        if shared and info["provider_window"][0] <= d <= info["provider_window"][1]:
            continue
        points[d] = (total, "collected")
    cur_total, ok = 0.0, bool(aids)
    for a in accts:
        c = (current or {}).get(a["id"]) or {}
        v = _num(c.get("value"))
        if v is None or (c.get("currency") or a["currency"]).upper() != ccy:
            ok = False
            info["current_missing"].append(a["name"])
            continue
        cur_total += v
        if c.get("as_of"):
            info["current_as_of"].append(str(c["as_of"]))
    if ok:
        points[today] = (cur_total, "current")
    return sorted((d, v, src) for d, (v, src) in points.items()), info


# ------------------------------------------------------------- one currency


def _empty_returns(reason: str) -> Dict[str, Any]:
    return {"available": False, "reason": reason,
            "twr": {"pct": None, "annualized_pct": None, "annualized": False, "method": TWR_METHOD,
                    "covered_days": 0, "excluded": []},
            "mwr": {"available": False, "reason": reason, "irr_annualized_pct": None, "period_pct": None,
                    "converged": False, "method": MWR_METHOD},
            "benchmark": None, "excess_pct": None, "excess_method": EXCESS_METHOD}


def _txn_known(a: Dict[str, Any], acts: Optional[List[Any]]) -> bool:
    # workspace.py passes [] where nothing is stored, so an empty list only
    # means "no transactions" when the last fetch succeeded.
    return bool(acts) or a.get("activities_state") == "ok"


def _why_no_transactions(a: Dict[str, Any]) -> str:
    st = a.get("activities_state")
    if st == "unavailable":
        return "the provider does not supply transactions for {}".format(a["name"])
    if st == "error":
        return "the transactions fetch for {} failed and nothing was stored".format(a["name"])
    return "transactions for {} have not been fetched yet".format(a["name"])


DROP_REASONS = {"missing": "an account in view was missing from the snapshot",
                "incomplete": "the sync was incomplete or a holding had no price",
                "other_currency": "an account held positions priced in another currency"}


def _dropped_text(dropped: Dict[date, str], lo: date, hi: date) -> Optional[Tuple[str, str]]:
    """("2 collected days", "2 where the sync was incomplete ...") or None."""
    counts: Dict[str, int] = {}
    for d, why in dropped.items():
        if lo <= d <= hi:
            counts[why] = counts.get(why, 0) + 1
    if not counts:
        return None
    n = sum(counts.values())
    return ("{} collected {}".format(n, "day" if n == 1 else "days"),
            "; ".join("{} where {}".format(c, DROP_REASONS[w]) for w, c in sorted(counts.items())))


def _why_no_history(accts: List[Dict[str, Any]], info: Dict[str, Any], window_start: date, today: date,
                    n_points: int) -> str:
    parts = []
    for a in accts:
        if info["provider"].get(a["id"]):
            lo, hi, _n = info["provider"][a["id"]]
            if hi < window_start:
                parts.append("the provider's balance history for {} ends on {}".format(a["name"], hi.isoformat()))
            continue
        st = a.get("history_state")
        if a["name"] in info["provider_currency_mismatch"]:
            parts.append("the provider's balance history for {} is in another currency".format(a["name"]))
        elif st == "unavailable":
            parts.append("SnapTrade's balance-history add-on is off for {}".format(a["name"]))
        elif st == "error":
            parts.append("the last balance-history fetch for {} failed".format(a["name"]))
        elif st == "ok":
            parts.append("the provider returned no balance history for {}".format(a["name"]))
        else:
            parts.append("balance history for {} has not been fetched yet".format(a["name"]))
    if not parts and all(info["provider"].get(a["id"]) for a in accts) and not info["provider_window"]:
        parts.append("the provider's balance histories for these accounts share no dates")
    days = sorted(d for d in info["collected"] if window_start <= d <= today)
    who = "these accounts" if len(accts) > 1 else accts[0]["name"] if accts else "these accounts"
    if days:
        parts.append("Optic has collected complete snapshots of {} on {} since {}".format(
            who, _plural(len(days), "day"), days[0].isoformat()))
    else:
        parts.append("Optic has not collected a complete snapshot of {} in this period yet".format(who))
    dropped = _dropped_text(info["dropped"], window_start, today)
    if dropped:
        parts.append("{} could not be used ({})".format(*dropped))
    if info["current_missing"]:
        parts.append("there is no current value for {}".format(", ".join(info["current_missing"])))
    return ("Not enough history for a return: {}. A time-weighted return needs values on at least two dates, "
            "and this period has {}.").format("; ".join(parts), _plural(n_points, "date"))


def _group(ccy: str, accts: List[Dict[str, Any]], rows: Dict[str, List[Dict[str, Any]]],
           raw_acts: Dict[str, Any], histories: Dict[str, Any], snapshots: Any, current: Dict[str, Any],
           benchmark: Optional[Dict[str, Any]], today: date, period: str, start: date) -> Dict[str, Any]:
    lim: List[str] = []
    names = {a["id"]: a["name"] for a in accts}
    all_rows = [r for a in accts for r in rows.get(a["id"], [])]

    # ---- flows: classify, match internal transfers, date them
    ext = [r for r in all_rows if r["class"] == "external_flow"]
    pairs = match_internal_transfers(ext) if len(accts) > 1 else []
    for n, (o, i) in enumerate(pairs):
        o["pair"] = i["pair"] = n
        # A leg the broker valued lends its value to an unvalued partner of the
        # same shares: the scope's total did not change, whatever it was worth.
        if o["value"] is None and i["value"] is not None:
            o.update(value=-abs(i["value"]), valued_by="matching_leg")
        elif i["value"] is None and o["value"] is not None:
            i.update(value=abs(o["value"]), valued_by="matching_leg")
    undated = [r for r in ext if r["date"] is None]
    tflows = sorted((r for r in ext if r["date"] is not None), key=lambda r: (r["date"], r["key"]))

    # ---- values
    first_txn = max((a["transactions_first_date"] for a in accts if a["transactions_first_date"]), default=None)
    window_start = start
    if first_txn and first_txn > start:
        window_start = first_txn
    pts_all, vinfo = _value_points(ccy, accts, histories, snapshots, current, today)
    # Where the measurable history begins: a period reaching further back measures the same days as All, and
    # the page says so rather than offering five buttons that show one number (owner, 2026-10-20)
    known = [p for p in pts_all if p[1] > 0 and (not first_txn or p[0] >= first_txn)]
    history_start = known[0][0] if known else None
    pts = [p for p in pts_all if window_start <= p[0] <= today]
    # A provider history can open with zero balances before the first deposit
    # arrives; a return on no capital is undefined, so the measured span starts
    # at the first day with money in it rather than excluding every empty day.
    while pts and pts[0][1] <= 0:
        pts.pop(0)

    missing_txn = [a for a in accts if not _txn_known(a, raw_acts.get(a["id"]))]
    reasons = []
    if len(pts) < 2:
        reasons.append(_why_no_history(accts, vinfo, window_start, today, len(pts)))
    if missing_txn:
        reasons.append("Deposits and withdrawals cannot be separated from gains and losses because {}.".format(
            "; ".join(_why_no_transactions(a) for a in missing_txn)))
    if first_txn and first_txn > start:
        lim.append("Transactions begin on {} (the earliest the broker supplied for {}), so returns are measured "
                   "from then: before it, deposits and withdrawals are not known.".format(
                       first_txn.isoformat(), ", ".join(a["name"] for a in accts
                                                        if a["transactions_first_date"] == first_txn)))

    # ---- chain
    returns: Dict[str, Any]
    series: List[Dict[str, Any]] = []
    subs: List[Dict[str, Any]] = []
    measured_start = pts[0][0] if pts else None
    measured_end = pts[-1][0] if pts else None
    if not reasons:
        fi = 0
        cum = 1.0
        cum_flow = 0.0
        series.append({"date": pts[0][0].isoformat(), "value": _money(pts[0][1]), "net_flow": 0.0,
                       "cum_net_flow": 0.0, "cum_twr_pct": 0.0, "cum_benchmark_pct": None,
                       "source": pts[0][2], "measured": True})
        while fi < len(tflows) and tflows[fi]["date"] <= pts[0][0]:
            fi += 1
        for k in range(1, len(pts)):
            d0, v0, _s0 = pts[k - 1]
            d1, v1, s1 = pts[k]
            inside = []
            while fi < len(tflows) and tflows[fi]["date"] <= d1:
                inside.append(tflows[fi])
                fi += 1
            pair_ids = [r["pair"] for r in inside if r["pair"] is not None]
            unvalued = [r for r in inside if r["value"] is None
                        and not (r["pair"] is not None and pair_ids.count(r["pair"]) == 2)]
            known = [(r["date"], r["value"]) for r in inside if r["value"] is not None]
            net_ext = sum(r["value"] for r in inside if r["pair"] is None and r["value"] is not None)
            cum_flow += net_ext
            rate = None
            why = None
            if unvalued:
                why = "a transfer on {} could not be valued".format(
                    ", ".join(sorted({u["date"].isoformat() for u in unvalued})))
            else:
                rate = modified_dietz(v0, v1, known, d0, d1)
                if rate is None:
                    why = "the value at the start was zero or negative"
            if rate is not None:
                cum *= 1.0 + rate
            subs.append({"from": d0, "to": d1, "rate": rate, "reason": why})
            series.append({"date": d1.isoformat(), "value": _money(v1), "net_flow": _money(net_ext),
                           "cum_net_flow": _money(cum_flow), "cum_twr_pct": _pct(cum - 1.0),
                           "cum_benchmark_pct": None, "source": s1, "measured": rate is not None})
        included = [s for s in subs if s["rate"] is not None]
        excluded = _merge_stretches([s for s in subs if s["rate"] is None])
        span = (measured_end - measured_start).days
        covered = sum((s["to"] - s["from"]).days for s in included)
        if not included:
            reasons.append("No stretch between {} and {} could be measured: {}.".format(
                measured_start.isoformat(), measured_end.isoformat(),
                "; ".join("{} to {}: {}".format(s["from"].isoformat(), s["to"].isoformat(), s["reason"])
                          for s in excluded)))
    if reasons:
        returns = _empty_returns(" ".join(reasons))
        if not series:
            series = [{"date": d.isoformat(), "value": _money(v), "net_flow": None, "cum_net_flow": None,
                       "cum_twr_pct": None, "cum_benchmark_pct": None, "source": s, "measured": False}
                      for d, v, s in pts]
        else:
            for row in series:
                row.update(cum_twr_pct=None, measured=False)
        twr_total = None
    else:
        twr_total = cum - 1.0
        annualise = covered >= ANNUALISE_MIN_DAYS
        twr = {"pct": _pct(twr_total),
               "annualized_pct": _pct((1.0 + twr_total) ** (365.0 / covered) - 1.0) if annualise else None,
               "annualized": annualise, "method": TWR_METHOD, "covered_days": covered,
               "excluded": [{"from": s["from"].isoformat(), "to": s["to"].isoformat(), "reason": s["reason"]}
                            for s in excluded]}
        lim.append(DEFINITIONS["flow_timing"])
        # A weekend or a holiday at either end is not worth a sentence; a
        # history that starts months into the period is.
        if (measured_start - start).days > STALE_BENCHMARK_DAYS:
            lim.append("Values begin on {}, after the period's start on {}, so the return covers {} to {}.".format(
                measured_start.isoformat(), start.isoformat(), measured_start.isoformat(),
                measured_end.isoformat()))
        if measured_end < today:
            lim.append("The latest value is dated {}; there is none for {}.".format(
                measured_end.isoformat(), today.isoformat()))
        lim.append("Deposits and withdrawals come from the broker's transaction list; one the broker did not "
                   "report would be counted as a gain or a loss.")
        if not annualise:
            lim.append("The return covers {} and is not annualised: annualising less than a year would project "
                       "it forward.".format(_plural(covered, "day")))
        for s in excluded:
            lim.append("The return from {} to {} could not be measured ({}), so that stretch is left out of the "
                       "time-weighted return and the benchmark's, not counted as zero.".format(
                           s["from"].isoformat(), s["to"].isoformat(), s["reason"]))

        # ---- money-weighted
        mwr: Dict[str, Any] = {"available": True, "reason": None, "irr_annualized_pct": None,
                               "period_pct": None, "converged": False, "method": MWR_METHOD}
        in_span = [r for r in tflows if measured_start < r["date"] <= measured_end]
        span_ids = [r["pair"] for r in in_span if r["pair"] is not None]
        unvalued_span = [r for r in in_span if r["value"] is None
                         and not (r["pair"] is not None and span_ids.count(r["pair"]) == 2)]
        if unvalued_span:
            mwr.update(available=False, reason=(
                "A transfer on {} could not be valued, and a money-weighted return needs every flow's "
                "amount.").format(", ".join(sorted({r["date"].isoformat() for r in unvalued_span}))))
        else:
            cfs = [(measured_start, -pts[0][1])]
            cfs += [(r["date"], -r["value"]) for r in in_span if r["value"] is not None]
            cfs.append((measured_end, pts[-1][1]))
            got = xirr(cfs)
            mwr["converged"] = got["converged"]
            if got["rate"] is not None and got["converged"]:
                mwr["irr_annualized_pct"] = _pct(got["rate"])
                mwr["period_pct"] = _pct((1.0 + got["rate"]) ** (span / 365.0) - 1.0)
            else:
                mwr.update(available=False, reason="The money-weighted return did not solve ({}).".format(
                    got["method"]))
                lim.append("The money-weighted return could not be solved for these flows ({}).".format(
                    got["method"]))
            if span < SHORT_MWR_DAYS:
                lim.append("The money-weighted return covers {}; over a short span it swings widely with the "
                           "timing of each deposit, so it is noisy.".format(_plural(span, "day")))
        returns = {"available": True, "reason": None, "twr": twr, "mwr": mwr, "benchmark": None,
                   "excess_pct": None, "excess_method": EXCESS_METHOD}

        # ---- benchmark over the same stretches
        if benchmark:
            sym = benchmark.get("symbol") or "Benchmark"
            idx = benchmark_index(benchmark.get("closes") or [], benchmark.get("dividends") or [])
            idx_dates = [d for d, _ in idx]
            b = {"symbol": sym, "twr_pct": None, "available": False, "reason": None,
                 "method": DEFINITIONS["benchmark_total_return"]}
            if not idx:
                b["reason"] = "No closes for {}.".format(sym)
            elif idx_dates[0] > measured_start:
                b["reason"] = "{}'s closes start on {}, after the first measured date {}.".format(
                    sym, idx_dates[0].isoformat(), measured_start.isoformat())
            else:
                bcum = 1.0
                by_date = {measured_start.isoformat(): 0.0}
                for s in subs:
                    if s["rate"] is not None:
                        bcum *= _level_on(idx, idx_dates, s["to"]) / _level_on(idx, idx_dates, s["from"])
                    by_date[s["to"].isoformat()] = bcum - 1.0
                for row in series:
                    row["cum_benchmark_pct"] = _pct(by_date.get(row["date"]))
                b.update(twr_pct=_pct(bcum - 1.0), available=True)
                returns["excess_pct"] = round(100.0 * (twr_total - (bcum - 1.0)), 2)
                lim.append("{}'s total return reinvests each dividend at the close on its ex-dividend date, and "
                           "keeps its last close on days the market was closed.".format(sym))
                if (measured_end - idx_dates[-1]).days > STALE_BENCHMARK_DAYS:
                    lim.append("{}'s closes end on {}; later dates carry that close forward.".format(
                        sym, idx_dates[-1].isoformat()))
                bccy = (benchmark.get("currency") or "USD").upper()
                if bccy != ccy:
                    lim.append("{} is priced in {} and these accounts in {}; Optic does not convert, so the "
                               "difference includes currency moves.".format(sym, bccy, ccy))
            returns["benchmark"] = b

    # ---- sources
    used_src = {}
    for _d, _v, s in pts:
        used_src[s] = used_src.get(s, 0) + 1
    kinds = {"collected" if s == "current" else s for s in used_src}
    values = "none" if not pts else ("mixed" if len(kinds) > 1 else next(iter(kinds)))
    switches = [{"date": pts[k][0].isoformat(), "from": pts[k - 1][2], "to": pts[k][2]}
                for k in range(1, len(pts))
                if {pts[k - 1][2], pts[k][2]} - {"collected", "current"} and pts[k - 1][2] != pts[k][2]]
    gaps = [{"from": pts[k - 1][0].isoformat(), "to": pts[k][0].isoformat(), "days": (pts[k][0] - pts[k - 1][0]).days}
            for k in range(1, len(pts)) if (pts[k][0] - pts[k - 1][0]).days > 1]
    prov_used = [d for d, _v, s in pts if s == "provider_estimate"]
    coll_used = [d for d, _v, s in pts if s == "collected"]
    if prov_used:
        lim.append("Values from {} to {} are the provider's estimate of each account's daily balance "
                   "(estimated by the provider), not broker statements.".format(
                       prov_used[0].isoformat(), prov_used[-1].isoformat()))
    if coll_used:
        lim.append("Values on {} are Optic's own daily snapshots of the holdings, priced as the broker reported "
                   "them when Optic synced.".format(_plural(len(coll_used), "day")))
    if used_src.get("current"):
        as_of = " (broker as of {})".format(max(vinfo["current_as_of"])) if vinfo["current_as_of"] else ""
        lim.append("The last value, dated {}, is the latest sync of the holdings{}.".format(today.isoformat(), as_of))
    for sw in switches:
        lim.append("On {} the values switch from {} to {}; the two are measured differently, so part of that "
                   "change can be the difference between the sources rather than a return.".format(
                       sw["date"], SOURCE_LABELS[sw["from"]], SOURCE_LABELS[sw["to"]]))
    if gaps:
        longest = max(gaps, key=lambda g: g["days"])
        lim.append("{} of more than a day between values (longest {} days, {} to {}); returns across a gap use "
                   "the Modified Dietz method and nothing is interpolated.".format(
                       _plural(len(gaps), "gap"), longest["days"], longest["from"], longest["to"]))
    dropped = _dropped_text(vinfo["dropped"], window_start, today)
    if dropped:
        lim.append("{} in this period {} left out ({}): a partial value would read as a loss and a "
                   "recovery.".format(dropped[0], "was" if dropped[0].startswith("1 ") else "were", dropped[1]))
    if vinfo["provider_currency_mismatch"]:
        lim.append("The provider's balance history for {} is in another currency and is not used.".format(
            ", ".join(vinfo["provider_currency_mismatch"])))

    # ---- flows summary over the requested window
    win = [r for r in tflows if start <= r["date"] <= today]
    ext_win = [r for r in win if r["pair"] is None]
    deposits = sum(r["value"] for r in ext_win if r["value"] is not None and r["value"] > 0)
    withdrawals = -sum(r["value"] for r in ext_win if r["value"] is not None and r["value"] < 0)
    months: Dict[str, Dict[str, float]] = {}
    for r in ext_win:
        if r["value"] is None:
            continue
        m = months.setdefault(r["date"].strftime("%Y-%m"), {"deposits": 0.0, "withdrawals": 0.0})
        m["deposits" if r["value"] > 0 else "withdrawals"] += abs(r["value"])
    pairs_win = [(o, i) for o, i in pairs if (o["date"] and start <= o["date"] <= today)
                 or (i["date"] and start <= i["date"] <= today)]
    in_kind = [r for r in win if r.get("in_kind")]
    unvalued = [r for r in win if r["value"] is None]
    flows = {
        "available": True, "window": {"start": start.isoformat(), "end": today.isoformat()}, "currency": ccy,
        "deposits": _money(deposits), "withdrawals": _money(withdrawals),
        "net_external": _money(deposits - withdrawals),
        "counts": {"deposits": sum(1 for r in ext_win if (r["value"] or 0) > 0),
                   "withdrawals": sum(1 for r in ext_win if (r["value"] or 0) < 0),
                   "unvalued": len(unvalued)},
        "internal_transfers": {
            "matched": len(pairs_win),
            "total": _money(sum(abs(o["value"] or i["value"] or 0.0) for o, i in pairs_win)),
            "pairs": [{"out_date": _iso(o["date"]), "in_date": _iso(i["date"]), "from": names.get(o["account"]),
                       "to": names.get(i["account"]), "amount": _money(abs(o["value"])) if o["value"] is not None
                       else None, "currency": o["currency"], "types": [o["type"], i["type"]]}
                      for o, i in pairs_win]},
        "in_kind": [{"date": _iso(r["date"]), "account": names.get(r["account"]), "type": r["type"],
                     "symbol": r["symbol"], "units": r["units"], "value": _money(r["value"]),
                     "valued_by": r["valued_by"], "internal": r["pair"] is not None} for r in in_kind],
        "unvalued": [{"date": _iso(r["date"]), "account": names.get(r["account"]), "type": r["type"],
                      "description": r["description"], "why": "in another currency" if r["valued_by"] ==
                      "other_currency" else "no amount, and no units and price"} for r in unvalued],
        "by_month": [{"month": k, "deposits": _money(v["deposits"]), "withdrawals": _money(v["withdrawals"]),
                      "net": _money(v["deposits"] - v["withdrawals"])} for k, v in sorted(months.items())],
        "items": [{"date": _iso(r["date"]), "account": names.get(r["account"]), "type": r["type"],
                   "value": _money(r["value"]), "valued_by": r["valued_by"],
                   "internal": r["pair"] is not None} for r in win],
    }
    if pairs_win:
        lim.append("{} between accounts in view {} matched and {} not counted as money in or out.".format(
            _plural(len(pairs_win), "transfer"), "was" if len(pairs_win) == 1 else "were",
            "is" if len(pairs_win) == 1 else "are"))
    if len(accts) == 1 and any(r["type"] == "TRANSFER" for r in win):
        lim.append("With one account in view, transfers to or from your other accounts count as money in or out.")
    est = [r for r in in_kind if r["valued_by"] == "units_x_price"]
    if est:
        lim.append("{} valued as units times the broker's price (estimated from units and price), which may "
                   "not be the value on the day.".format(_plural(len(est), "in-kind transfer")))
    if unvalued:
        lim.append("{} could not be valued ({}); returns across {} are not measured.".format(
            _plural(len(unvalued), "transfer"), ", ".join(sorted({r["date"].isoformat() for r in unvalued})),
            "that date" if len({r["date"] for r in unvalued}) == 1 else "those dates"))
    if undated:
        lim.append("{} had no date and {} not counted.".format(
            _plural(len(undated), "deposit or withdrawal", "deposits or withdrawals"),
            "is" if len(undated) == 1 else "are"))
    for a in accts:
        if a.get("activities_state") == "error" and raw_acts.get(a["id"]):
            lim.append("The last transactions fetch for {} failed; anything after the previous good fetch may be "
                       "missing.".format(a["name"]))

    # ---- income summary over the requested window
    inc_rows = [r for r in all_rows if r["class"] in ("income", "cost") and r["date"] and start <= r["date"] <= today]
    foreign = [r for r in inc_rows if r["currency"] != ccy]
    inc_rows = [r for r in inc_rows if r["currency"] == ccy]
    tot = {"dividends": 0.0, "reinvested": 0.0, "interest": 0.0, "fees": 0.0, "taxes": 0.0}
    by_sym: Dict[str, Dict[str, float]] = {}
    stock_divs = 0
    for r in inc_rows:
        amt = r["amount"]
        if r["type"] == "STOCK_DIVIDEND":
            stock_divs += 1
            continue
        if amt is None:
            continue
        bucket = {"DIVIDEND": "dividends", "SUBSTITUTE_DIVIDEND": "dividends", "REI": "reinvested",
                  "INTEREST": "interest", "FEE": "fees", "TAX": "taxes"}[r["type"]]
        val = -amt if bucket in ("fees", "taxes") else amt
        tot[bucket] += val
        s = by_sym.setdefault(r["symbol"] or "", dict.fromkeys(tot, 0.0))
        s[bucket] += val
    commissions = sum(r["fee"] for r in all_rows if r["class"] == "trade" and r["fee"] and r["date"]
                      and start <= r["date"] <= today and r["currency"] == ccy)
    income = {
        "available": True, "window": {"start": start.isoformat(), "end": today.isoformat()}, "currency": ccy,
        **{k: _money(v) for k, v in tot.items()},
        "net": _money(tot["dividends"] + tot["reinvested"] + tot["interest"] - tot["fees"] - tot["taxes"]),
        "stock_dividends": stock_divs, "trade_commissions": _money(commissions),
        "by_symbol": [dict({"symbol": k or None, "label": k or "Account level"},
                           **{b: _money(v) for b, v in vals.items()})
                      for k, vals in sorted(by_sym.items(), key=lambda kv: (-abs(sum(kv[1].values())), kv[0]))],
    }
    if tot["reinvested"]:
        lim.append("Reinvested dividends (REI) are on their own line: a broker that also reports the same "
                   "dividend as a DIVIDEND would otherwise have it counted twice.")
    if commissions:
        lim.append("Trade commissions are shown from each trade's fee field for information; they are inside "
                   "the trades and are not added to fees.")
    if foreign:
        lim.append("{} in a currency other than {} {} not counted in income; Optic does not convert "
                   "currencies.".format(_plural(len(foreign), "transaction"), ccy,
                                        "is" if len(foreign) == 1 else "are"))
    unknown_types = sorted({r["type"] or "(none)" for r in all_rows if r["class"] == "unrecognised"})
    if unknown_types:
        n = sum(1 for r in all_rows if r["class"] == "unrecognised")
        lim.append("{} of a type Optic does not recognise ({}) {} not counted.".format(
            _plural(n, "transaction"), ", ".join(unknown_types), "is" if n == 1 else "are"))

    attribution = _attribution(ccy, accts, snapshots, tflows, start, today, not missing_txn)
    lim.extend(attribution.pop("_limitations", []))

    counts: Dict[str, int] = {}
    for r in all_rows:
        counts[r["class"]] = counts.get(r["class"], 0) + 1
    return {
        "currency": ccy,
        "period": {"requested": period, "start": start.isoformat(), "end": today.isoformat(),
                   "measured_start": None if reasons else _iso(measured_start),
                   "measured_end": None if reasons else _iso(measured_end),
                   "days": None if reasons else (measured_end - measured_start).days,
                   "covered_days": returns["twr"]["covered_days"],
                   "history_start": _iso(history_start),
                   "starts": {p: period_start(p, today).isoformat() for p in PERIODS if p != "all"}},
        "sources": {"values": values, "values_label": SOURCE_LABELS[values], "points": used_src,
                    "provider_window": ({"start": vinfo["provider_window"][0].isoformat(),
                                         "end": vinfo["provider_window"][1].isoformat()}
                                        if vinfo["provider_window"] else None),
                    "collected_days": sum(1 for d in vinfo["collected"] if window_start <= d <= today),
                    "switches": switches, "gaps": gaps,
                    "transactions": {"counts": counts,
                                     "first_dates": {a["id"]: _iso(a["transactions_first_date"]) for a in accts},
                                     "states": {a["id"]: a.get("activities_state") for a in accts}}},
        "returns": returns,
        "series": series,
        "series_fields": SERIES_FIELDS,
        "flows": flows,
        "income": income,
        "attribution": attribution,
        "limitations": _dedupe(lim),
    }


def _attribution(ccy: str, accts: List[Dict[str, Any]], snapshots: Any, tflows: List[Dict[str, Any]],
                 start: date, today: date, txn_known: bool) -> Dict[str, Any]:
    aids = [a["id"] for a in accts]
    days = _snapshot_days(snapshots, start, today)
    base = {"available": False, "reason": None, "currency": ccy, "method": ATTRIBUTION_METHOD, "positions": [],
            "window": None, "sum_contributions": None, "total_change": None, "flows": None, "remainder": None,
            "average_capital": None, "skipped_pairs": []}
    if len(days) < 2:
        base["reason"] = ("Optic has collected {} of these accounts in this period{}; attribution needs at "
                          "least two consecutive days.").format(
                              _plural(len(days), "daily snapshot"),
                              " (on {})".format(days[0][0].isoformat()) if days else "")
        return base
    contrib: Dict[str, float] = {}
    meta: Dict[str, Dict[str, Any]] = {}
    change = net = capital_sum = 0.0
    used = 0
    unpriced = other_ccy = 0
    skipped = []
    for (d0, s0), (d1, s1) in zip(days, days[1:]):
        b0 = s0.get("by_account") if isinstance(s0.get("by_account"), dict) else {}
        b1 = s1.get("by_account") if isinstance(s1.get("by_account"), dict) else {}
        v0 = v1 = 0.0
        why = None
        for aid in aids:
            x0, w0 = _account_total(b0.get(aid), ccy)
            x1, w1 = _account_total(b1.get(aid), ccy)
            if w0 or w1:
                why = {"missing": "an account is missing from a snapshot",
                       "incomplete": "a sync was incomplete",
                       "other_currency": "holdings priced in another currency"}[w0 or w1]
                break
            v0 += x0
            v1 += x1
        inside = [r for r in tflows if d0 < r["date"] <= d1]
        ids = [r["pair"] for r in inside if r["pair"] is not None]
        if not why and any(r["value"] is None and not (r["pair"] is not None and ids.count(r["pair"]) == 2)
                           for r in inside):
            why = "a transfer could not be valued"
        if why:
            skipped.append({"from": d0.isoformat(), "to": d1.isoformat(), "reason": why})
            continue
        for aid in aids:
            p0 = (b0[aid].get("positions") or {})
            p1 = (b1[aid].get("positions") or {})
            for key, e0 in p0.items():
                e1 = p1.get(key)
                if not isinstance(e1, dict) or not isinstance(e0, dict):
                    continue
                if (e0.get("currency") or ccy).upper() != ccy:
                    other_ccy += 1
                    continue
                pr0, pr1 = _num(e0.get("price")), _num(e1.get("price"))
                if pr0 is None or pr1 is None:
                    unpriced += 1
                    continue
                if e0.get("kind") == "option":
                    # The snapshot's option price is per share and qty is
                    # contracts, so qty x price change is off by the multiplier;
                    # the value already carries it.
                    v = _num(e0.get("value"))
                    if v is None or pr0 == 0:
                        unpriced += 1
                        continue
                    c = v * (pr1 / pr0 - 1.0)
                else:
                    q = _num(e0.get("qty"))
                    if q is None:
                        unpriced += 1
                        continue
                    c = q * (pr1 - pr0)
                contrib[key] = contrib.get(key, 0.0) + c
                meta.setdefault(key, {"symbol": e0.get("symbol"), "kind": e0.get("kind"),
                                      "label": e0.get("label") or e0.get("symbol") or key})
        change += v1 - v0
        net += sum(r["value"] for r in inside if r["value"] is not None) if txn_known else 0.0
        capital_sum += v0
        used += 1
    base["skipped_pairs"] = skipped
    if not used:
        base["reason"] = "No two consecutive collected days in this period could be compared: {}.".format(
            "; ".join("{} to {}: {}".format(s["from"], s["to"], s["reason"]) for s in skipped))
        return base
    avg = capital_sum / used
    total_c = sum(contrib.values())
    lims = []
    if skipped:
        lims.append("Attribution skips {} of collected days ({}).".format(
            _plural(len(skipped), "pair"), "; ".join(sorted({s["reason"] for s in skipped}))))
    if not txn_known:
        lims.append("Transactions are not available, so attribution's remainder includes any deposits or "
                    "withdrawals.")
    if other_ccy:
        lims.append("Holdings priced in a currency other than {} are left out of attribution.".format(ccy))
    base.update({
        "available": True, "reason": None,
        "window": {"start": days[0][0].isoformat(), "end": days[-1][0].isoformat(), "pairs": used,
                   "snapshots": len(days)},
        "positions": [dict(meta[k], key=k, contribution=_money(v),
                           contribution_pct=round(100.0 * v / avg, 2) if avg > 0 else None)
                      for k, v in sorted(contrib.items(), key=lambda kv: (-abs(kv[1]), kv[0]))],
        "sum_contributions": _money(total_c),
        "sum_contributions_pct": round(100.0 * total_c / avg, 2) if avg > 0 else None,
        "total_change": _money(change),
        "flows": _money(net) if txn_known else None,
        "remainder": _money(change - net - total_c),
        "remainder_note": ("Trades during a day, holdings opened or closed, dividends, interest and fees: what "
                           "the price moves of holdings held on both days do not explain."),
        "average_capital": _money(avg),
        "unpriced_lines": unpriced,
        "_limitations": lims,
    })
    return base


def _merge_stretches(stretches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Back-to-back unmeasured stretches with the same reason as one: a
    margin account under water for forty days is one sentence, not forty."""
    out: List[Dict[str, Any]] = []
    for s in stretches:
        if out and out[-1]["to"] == s["from"] and out[-1]["reason"] == s["reason"]:
            out[-1] = dict(out[-1], to=s["to"])
        else:
            out.append(dict(s))
    return out


def _dedupe(items: Iterable[str]) -> List[str]:
    seen, out = set(), []
    for s in items:
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


# ------------------------------------------------------------------ build


def build(accounts: List[Dict[str, Any]], activities: Dict[str, List[Dict[str, Any]]],
          histories: Dict[str, Dict[str, Any]], snapshots: List[Dict[str, Any]],
          current: Dict[str, Dict[str, Any]], benchmark: Optional[Dict[str, Any]], today: Any,
          period: str = "1y") -> Dict[str, Any]:
    """Performance of the accounts in scope over `period` ending `today`.
    Raises ValueError for a period not in PERIODS. See the module docstring
    for the output keys."""
    if period not in PERIODS:
        raise ValueError("period must be one of " + ", ".join(PERIODS))
    today = _day(today)
    if today is None:
        raise ValueError("today must be a date")
    activities = activities or {}
    accts = [{"id": a["id"], "name": a.get("name") or "Account", "currency": (a.get("currency") or "USD").upper(),
              "transactions_first_date": _day(a.get("transactions_first_date")),
              "activities_state": a.get("activities_state"), "history_state": a.get("history_state")}
             for a in accounts or []]
    rows = {a["id"]: _rows(a, activities.get(a["id"])) for a in accts}

    earliest = None
    if period == "all":
        cands = [r["date"] for rs in rows.values() for r in rs if r["date"]]
        cands += [d for a in accts for p in ((histories or {}).get(a["id"]) or {}).get("points") or []
                  for d in [_day(p[0]) if isinstance(p, (list, tuple)) and p else None] if d]
        cands += [d for d, _s in _snapshot_days(snapshots, None, today)]
        earliest = min(cands) if cands else None
    start = period_start(period, today, earliest)

    groups: Dict[str, List[Dict[str, Any]]] = {}
    for a in accts:
        groups.setdefault(a["currency"], []).append(a)
    scope = {"accounts": [{"id": a["id"], "name": a["name"], "currency": a["currency"]} for a in accts],
             "count": len(accts)}
    base = {"scope": scope, "definitions": DEFINITIONS, "version": VERSION, "series_fields": SERIES_FIELDS}

    if not groups:
        reason = "No accounts are in view, so there is nothing to measure."
        return dict(base, currency=None,
                    period={"requested": period, "start": start.isoformat(), "end": today.isoformat(),
                            "measured_start": None, "measured_end": None, "days": None, "covered_days": 0},
                    sources={"values": "none", "values_label": SOURCE_LABELS["none"], "points": {},
                             "provider_window": None, "collected_days": 0, "switches": [], "gaps": [],
                             "transactions": {"counts": {}, "first_dates": {}, "states": {}}},
                    returns=_empty_returns(reason), series=[],
                    flows={"available": False, "reason": reason}, income={"available": False, "reason": reason},
                    attribution={"available": False, "reason": reason}, limitations=[reason])

    results = {c: _group(c, g, rows, activities, histories or {}, snapshots or [], current or {}, benchmark,
                         today, period, start) for c, g in groups.items()}
    if len(results) == 1:
        (ccy, r), = results.items()
        out = dict(base, **{k: v for k, v in r.items() if k != "series_fields"})
        return out

    ccys = sorted(results)
    reason = ("These accounts are in {}. A combined return needs currency conversion, which Optic does not "
              "apply here, so each currency is measured on its own in by_currency.").format(
                  ", ".join(ccys[:-1]) + " and " + ccys[-1])
    return dict(base, currency=None,
                period={"requested": period, "start": start.isoformat(), "end": today.isoformat(),
                        "measured_start": None, "measured_end": None, "days": None, "covered_days": 0},
                sources={"values": "none", "values_label": SOURCE_LABELS["none"],
                         "by_currency": {c: results[c]["sources"]["values"] for c in ccys}},
                returns=_empty_returns(reason), series=[],
                flows={"available": False, "reason": reason}, income={"available": False, "reason": reason},
                attribution={"available": False, "reason": reason},
                by_currency={c: {k: v for k, v in results[c].items() if k != "series_fields"} for c in ccys},
                limitations=[reason])
