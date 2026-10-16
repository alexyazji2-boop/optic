"""The reader's own calendar: what is scheduled for what they hold.

Pure: the caller injects the lookups (Yahoo's calendar, the ex-dividend date,
the option positions) so the arithmetic is testable offline and the network
cost is decided in one place (`workspace.py`).

What each kind of event can and cannot claim:

- **Earnings.** Yahoo's calendar gives one date when the company has
  confirmed it and a range when it is an estimate (`earnings_calendar`'s
  `confirmed` is `len(dates) == 1`). An estimate is shown as one, with its
  range. Timing (before the open or after the close) comes only from the
  earnings history scrape and is often unknown; unknown is said, not guessed.
- **Ex-dividend.** Yahoo's `exDividendDate` is frequently the *last* ex-date,
  so only a date today or later is shown. The amount is the last one paid
  (labelled so): Yahoo publishes no declared amount for the next payment, and
  Optic has no pay-date source at all.
- **Option expiry.** From the positions themselves, so these are exact.

Weights are the share of the scope's long value, the same denominator the
holdings table uses, so "events affect 31% of your portfolio" adds up against
the rest of the page.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Callable, Dict, Iterable, List, Optional

VERSION = "events-2026-10-15.1"
WINDOW_DAYS = 45
NOT_COMPANIES = ("etf", "fund", "bond", "crypto", "other")


def _day(v: Any) -> Optional[date]:
    if not v:
        return None
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def _ask(fn: Optional[Callable], sym: str) -> Any:
    if fn is None:
        return None
    try:
        return fn(sym)
    except Exception:                                           # noqa: BLE001
        return None


def build(holdings: Iterable[Dict[str, Any]], options: Iterable[Dict[str, Any]], today: date,
          earnings_of: Optional[Callable[[str], Optional[Dict[str, Any]]]] = None,
          dividend_of: Optional[Callable[[str], Optional[Dict[str, Any]]]] = None,
          window_days: int = WINDOW_DAYS, max_lookups: int = 25) -> Dict[str, Any]:
    """Events for the holdings within `window_days`, soonest first.

    `earnings_of(sym) -> {"dates": [iso, ...], "confirmed": bool, "timing": str|None}`
    `dividend_of(sym) -> {"ex_date": iso|None, "last_amount": float|None, "currency": str|None}`
    """
    holdings = [h for h in holdings if h.get("symbol")]
    options = list(options or [])
    by_symbol: Dict[str, Dict[str, Any]] = {}
    for h in holdings:
        sym = str(h["symbol"]).upper()
        entry = by_symbol.setdefault(sym, {"weight_pct": 0.0, "value": 0.0, "kind": h.get("kind"),
                                           "accounts": set(), "description": h.get("description")})
        entry["weight_pct"] += float(h.get("weight_pct") or 0.0)
        entry["value"] += float(h.get("value_usd") or h.get("market_value") or 0.0)
        entry["accounts"].update(h.get("accounts") or [])
    with_options = {str(o.get("underlying") or "").upper() for o in options}

    events: List[Dict[str, Any]] = []
    looked, skipped = 0, []
    limitations: List[str] = []
    # Largest first, so a capped lookup budget is spent where the weight is.
    for sym, entry in sorted(by_symbol.items(), key=lambda kv: -kv[1]["weight_pct"]):
        if looked >= max_lookups:
            skipped.append(sym)
            continue
        looked += 1
        base = {"symbol": sym, "weight_pct": round(entry["weight_pct"], 2), "value": round(entry["value"], 2),
                "accounts": sorted(a for a in entry["accounts"] if a), "has_options": sym in with_options,
                "description": entry["description"]}
        if entry["kind"] not in NOT_COMPANIES:
            cal = _ask(earnings_of, sym) or {}
            dates = [d for d in (_day(x) for x in cal.get("dates") or []) if d]
            if dates:
                first = min(dates)
                if today <= first <= today.fromordinal(today.toordinal() + window_days):
                    confirmed = bool(cal.get("confirmed")) and len(dates) == 1
                    events.append(dict(base, kind="earnings", date=first.isoformat(),
                                       days_away=(first - today).days, confirmed=confirmed,
                                       range_end=max(dates).isoformat() if len(dates) > 1 else None,
                                       timing=cal.get("timing") if confirmed else None,
                                       title="{} reports earnings".format(sym),
                                       note=None if confirmed else
                                       "Estimated date{}: the company has not confirmed it.".format(
                                           " range" if len(dates) > 1 else ""),
                                       links={"earnings": "#/{}/earnings".format(sym),
                                              "overview": "#/{}".format(sym)}))
        div = _ask(dividend_of, sym) or {}
        ex = _day(div.get("ex_date"))
        if ex and today <= ex <= today.fromordinal(today.toordinal() + window_days):
            amount = div.get("last_amount")
            events.append(dict(base, kind="ex_dividend", date=ex.isoformat(), days_away=(ex - today).days,
                               confirmed=True, timing=None,
                               title="{} goes ex-dividend".format(sym),
                               last_amount=amount, currency=div.get("currency"),
                               note=("Last dividend paid was {} a share; the next amount is not published "
                                     "here.".format(amount) if amount else
                                     "The amount of the next dividend is not published here."),
                               links={"overview": "#/{}".format(sym)}))

    for o in options:
        exp = _day(o.get("expiry"))
        if not exp or exp < today or exp > today.fromordinal(today.toordinal() + window_days):
            continue
        under = str(o.get("underlying") or "").upper()
        n = o.get("contracts")
        events.append({
            "symbol": under, "kind": "option_expiry", "date": exp.isoformat(), "days_away": (exp - today).days,
            "confirmed": True, "timing": None,
            "title": "{} {} {} {} expires".format(under, o.get("strike"), o.get("option_type") or "", exp.isoformat()),
            "contracts": n, "account": o.get("account"),
            "weight_pct": None, "value": o.get("market_value_est"),
            "has_options": True, "accounts": [o.get("account")] if o.get("account") else [],
            "note": "Exact: from the option position itself.",
            "links": {"options": "#/{}/options".format(under)},
        })

    events.sort(key=lambda e: (e["date"], {"earnings": 0, "ex_dividend": 1, "option_expiry": 2}[e["kind"]],
                               -(e.get("weight_pct") or 0)))
    if skipped:
        limitations.append("Calendars were read for the {} largest holdings; {} smaller one{} not checked: {}."
                           .format(looked, len(skipped), "" if len(skipped) == 1 else "s were",
                                   ", ".join(skipped[:10])))
    limitations.append("Earnings dates come from Yahoo's calendar. An estimate is marked as one; a confirmed "
                       "date can still move.")
    limitations.append("Ex-dividend dates come from Yahoo and only future dates are shown. Optic has no source "
                       "for pay dates or the declared amount of the next dividend.")
    if any(h.get("kind") in ("etf", "fund") for h in holdings):
        limitations.append("Funds have no earnings date of their own; their holdings' reports are not "
                           "listed here.")

    def share(kinds: Iterable[str], days: int) -> float:
        syms = {e["symbol"] for e in events if e["kind"] in kinds and e["days_away"] <= days}
        return round(sum(by_symbol[s]["weight_pct"] for s in syms if s in by_symbol), 2)

    return {
        "version": VERSION,
        "window_days": window_days,
        "events": events,
        "summary": {
            "earnings_next_14d_pct": share(("earnings",), 14),
            "earnings_confirmed_next_14d_pct": round(sum(
                by_symbol[e["symbol"]]["weight_pct"] for e in events
                if e["kind"] == "earnings" and e["days_away"] <= 14 and e["confirmed"]), 2),
            "ex_dividend_next_14d_pct": share(("ex_dividend",), 14),
            "options_expiring_7d": len([e for e in events if e["kind"] == "option_expiry" and e["days_away"] <= 7]),
            "count": len(events),
        },
        "limitations": limitations,
        "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
