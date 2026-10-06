"""The reported starting point for a reader's own valuation scenarios.

Asked for as editable bull, base and bear scenarios on the Investing tab. The
arithmetic of a scenario is the reader's and lives in one place, the page
(static/app.js, `valuationScenario`). This module only says what the company
reported, where each figure came from and as of when, and what its own history
looked like. It never fills a gap with a guess: a figure the feeds do not have
comes back as `{"value": None, "reason": ...}` and the page asks the reader for
it.

**Reported, derived and history are kept apart.** Revenue and shares are
reported figures. A trailing net margin is derived from two reported figures
of the same statement and the same periods, never from one source's revenue
and another's earnings. The history block (revenue growth, average margin,
share count change) describes what already happened, is labelled that way on
the page, and is never called a forecast.

**Currencies are not mixed silently.** SEC figures here are the us-gaap USD
facts. Yahoo's statements carry no currency of their own, so the quote's
`financial_currency` is reported beside them, and a statement currency that
differs from the price's is stated as a warning rather than converted.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any, Dict, List, Optional

from . import fundamentals as fund_mod
from . import sec_facts

SEC_SOURCE = "SEC filings (XBRL us-gaap facts), the last four reported quarters"
YF_STATEMENTS = "Yahoo Finance income statements"
YF_QUOTE = "Yahoo Finance quote"

# Quote types a revenue-and-earnings valuation means anything for.
COMPANY_TYPES = ("EQUITY",)

HISTORY_NOTE = ("What already happened, from the company's own filings. Not a forecast "
                "and not an analyst's estimate.")


def _num(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _missing(reason: str) -> Dict[str, Any]:
    return {"value": None, "reason": reason}


def _days(a: str, b: str) -> Optional[int]:
    try:
        return (date.fromisoformat(str(b)[:10]) - date.fromisoformat(str(a)[:10])).days
    except ValueError:
        return None


def _cagr(newest: Optional[float], oldest: Optional[float], years: float) -> Optional[float]:
    if newest is None or oldest is None or oldest <= 0 or newest <= 0 or years <= 0:
        return None
    return round(((newest / oldest) ** (1.0 / years) - 1.0) * 100.0, 2)


def _sec_revenue(facts: Dict[str, Any]) -> Dict[str, Any]:
    """Trailing-twelve-month revenue from filings, and its growth over up to
    three years from the same series."""
    rows = (facts or {}).get("revenue_ttm") or []
    if not (facts or {}).get("available") or not rows:
        return {}
    last = rows[-1]
    out = {"ttm": {"value": _num(last.get("value")), "unit": "currency", "currency": "USD",
                   "period_end": last.get("period_end"), "available_from": last.get("available_from"),
                   "source": SEC_SOURCE, "kind": "reported",
                   "derived_quarter": bool(last.get("derived"))}}
    # The same trailing figure one, two or three years earlier, matched by
    # date rather than by position: a gap in the filings would otherwise
    # compare against the wrong year.
    for years in (3, 2, 1):
        target = None
        for r in rows[:-1]:
            gap = _days(r.get("period_end"), last.get("period_end"))
            if gap is not None and abs(gap - 365.25 * years) <= 45:
                target = r
        if target:
            g = _cagr(_num(last.get("value")), _num(target.get("value")), float(years))
            if g is not None:
                out["growth"] = {"value": g, "unit": "pct_per_year", "years": years,
                                 "from": target.get("period_end"), "to": last.get("period_end"),
                                 "source": SEC_SOURCE, "kind": "history", "note": HISTORY_NOTE}
                break
    return out


def _statement_ttm(fin: Dict[str, Any], key: str) -> Optional[Dict[str, Any]]:
    """The last four quarters of one statement line, if they are four
    consecutive quarters, else None."""
    periods = (fin or {}).get("quarterly_periods") or []
    values = ((fin or {}).get("quarterly") or {}).get(key) or []
    if len(periods) < 4 or len(values) < 4:
        return None
    four = values[:4]
    if any(v is None for v in four):
        return None
    span = _days(periods[3], periods[0])
    if span is None or not (240 <= span <= 300):
        return None
    return {"value": float(sum(four)), "period_end": periods[0], "periods": periods[:4]}


def _statements(fin: Dict[str, Any], raw: Dict[str, Any], currency: Optional[str]) -> Dict[str, Any]:
    """Revenue, net income, margin and share history from Yahoo's statements."""
    out: Dict[str, Any] = {}
    if not (fin or {}).get("available"):
        return out
    annual = fin.get("annual") or {}
    periods = fin.get("annual_periods") or []
    rev_ttm = _statement_ttm(fin, "revenue")
    ni_ttm = _statement_ttm(fin, "net_income")
    cur = {"currency": currency, "currency_note": None if currency else
           "The feed does not state which currency these statements are in."}

    if rev_ttm:
        out["revenue"] = {"value": rev_ttm["value"], "unit": "currency", "period_end": rev_ttm["period_end"],
                          "source": YF_STATEMENTS + ", the last four quarters", "kind": "reported", **cur}
    elif annual.get("revenue") and periods and annual["revenue"][0] is not None:
        out["revenue"] = {"value": float(annual["revenue"][0]), "unit": "currency", "period_end": periods[0],
                          "source": YF_STATEMENTS + ", the latest fiscal year (not trailing twelve months)",
                          "kind": "reported", **cur}

    # A margin only from one statement's own revenue and earnings over the same
    # periods, so it is a ratio of like with like.
    if rev_ttm and ni_ttm and rev_ttm["periods"] == ni_ttm["periods"] and rev_ttm["value"] > 0:
        out["margin"] = {"value": round(ni_ttm["value"] / rev_ttm["value"] * 100.0, 2), "unit": "pct",
                         "period_end": rev_ttm["period_end"], "net_income": ni_ttm["value"],
                         "source": YF_STATEMENTS + ", net income over revenue, the last four quarters",
                         "kind": "derived"}
    else:
        rev, ni = annual.get("revenue") or [], annual.get("net_income") or []
        if rev and ni and periods and rev[0] and ni[0] is not None and rev[0] > 0:
            out["margin"] = {"value": round(ni[0] / rev[0] * 100.0, 2), "unit": "pct", "period_end": periods[0],
                             "net_income": float(ni[0]),
                             "source": YF_STATEMENTS + ", net income over revenue, the latest fiscal year",
                             "kind": "derived"}

    # History: every fiscal year the feed has.
    rev, ni = annual.get("revenue") or [], annual.get("net_income") or []
    years: List[Dict[str, Any]] = []
    for i, period in enumerate(periods):
        r = rev[i] if i < len(rev) else None
        n = ni[i] if i < len(ni) else None
        if r and n is not None and r > 0:
            years.append({"period": period, "margin_pct": round(n / r * 100.0, 2)})
    if years:
        out["margin_history"] = {"value": round(sum(y["margin_pct"] for y in years) / len(years), 2),
                                 "unit": "pct", "years": years, "source": YF_STATEMENTS,
                                 "kind": "history", "note": HISTORY_NOTE}
    clean = [(periods[i], rev[i]) for i in range(min(len(periods), len(rev))) if rev[i]]
    if len(clean) >= 2:
        span = (_days(clean[-1][0], clean[0][0]) or 0) / 365.25
        g = _cagr(clean[0][1], clean[-1][1], round(span))
        if g is not None:
            out["revenue_growth"] = {"value": g, "unit": "pct_per_year", "years": round(span),
                                     "from": clean[-1][0], "to": clean[0][0], "source": YF_STATEMENTS,
                                     "kind": "history", "note": HISTORY_NOTE}

    shares = (((raw or {}).get("income_annual") or {}).get("rows") or {}).get("Diluted Average Shares")
    pairs = [(periods[i], shares[i]) for i in range(min(len(periods), len(shares or [])))
             if shares and shares[i]]
    if len(pairs) >= 2:
        span = (_days(pairs[-1][0], pairs[0][0]) or 0) / 365.25
        if span >= 0.9:
            change = ((pairs[0][1] / pairs[-1][1]) ** (1.0 / round(span)) - 1.0) * 100.0
            out["share_change"] = {"value": round(change, 2), "unit": "pct_per_year", "years": round(span),
                                   "from": pairs[-1][0], "to": pairs[0][0],
                                   "source": YF_STATEMENTS + ", diluted average shares",
                                   "kind": "history", "note": HISTORY_NOTE}
    return out


def build(provider, ticker: str) -> Dict[str, Any]:
    sym = (ticker or "").upper().strip()
    try:
        quote = provider.quote(sym) or {}
    except Exception as exc:                                   # noqa: BLE001
        return {"available": False, "ticker": sym,
                "reason": "The quote feed did not answer ({}). Nothing here is a guess, so "
                          "nothing is shown.".format(str(exc)[:100])}
    qtype = (quote.get("quote_type") or "").upper()
    if qtype and qtype not in COMPANY_TYPES:
        return {"available": False, "ticker": sym,
                "reason": "Scenarios here value a company from its revenue and earnings, and "
                          "{} is not a company ({}).".format(sym, qtype.lower())}

    price_ccy = quote.get("currency") or None
    stmt_ccy = quote.get("financial_currency") or None
    try:
        raw = provider.financials(sym) or {}
    except Exception:                                          # noqa: BLE001
        raw = {}
    fin = fund_mod.analyse_financials(raw) if raw else {"available": False}
    try:
        facts = sec_facts.history(sym)
    except Exception:                                          # noqa: BLE001
        facts = {"available": False}
    try:
        short = provider.short_interest(sym) or {}
    except Exception:                                          # noqa: BLE001
        short = {}

    sec = _sec_revenue(facts)
    stm = _statements(fin, raw, stmt_ccy)

    inputs: Dict[str, Any] = {}
    price = _num(quote.get("price"))
    inputs["price"] = ({"value": price, "unit": "currency", "currency": price_ccy, "as_of": quote.get("as_of"),
                        "source": YF_QUOTE, "kind": "reported"} if price else _missing("No price in the quote."))
    # Filings first: longer, dated by when they became public, and in USD.
    inputs["revenue"] = (sec.get("ttm") if sec.get("ttm") and sec["ttm"]["value"]
                         else stm.get("revenue") or _missing(
                             "Neither the SEC filings nor the statements feed have revenue for {}.".format(sym)))
    inputs["margin"] = stm.get("margin") or _missing(
        "No net income and revenue for the same periods, so no trailing margin.")
    shares = _num(short.get("shares_outstanding"))
    inputs["shares"] = ({"value": shares, "unit": "shares", "source": YF_QUOTE + ", shares outstanding",
                         "as_of": None, "kind": "reported",
                         "note": "The feed does not date this count."} if shares else
                        _missing("The feed has no share count, so per-share figures need yours."))
    mcap = _num(quote.get("market_cap"))
    inputs["market_cap"] = ({"value": mcap, "unit": "currency", "currency": price_ccy,
                             "source": YF_QUOTE, "as_of": quote.get("as_of"), "kind": "reported"}
                            if mcap else _missing("No market value in the quote."))
    pe = _num(quote.get("trailing_pe"))
    inputs["trailing_pe"] = ({"value": pe, "unit": "multiple", "source": YF_QUOTE, "kind": "reported",
                              "as_of": quote.get("as_of")} if pe and pe > 0 else
                             _missing("No trailing P/E: the last twelve months were a loss, or the "
                                      "feed has none."))
    dy = _num(quote.get("dividend_yield"))
    inputs["dividend_yield"] = ({"value": dy, "unit": "fraction", "source": YF_QUOTE,
                                 "kind": "reported"} if dy else _missing("No dividend in the quote."))

    history: Dict[str, Any] = {}
    history["revenue_growth"] = sec.get("growth") or stm.get("revenue_growth") or _missing(
        "Not enough revenue history to measure growth.")
    history["margin"] = stm.get("margin_history") or _missing("No annual margins in the statements feed.")
    history["share_change"] = stm.get("share_change") or _missing(
        "No diluted share counts across fiscal years in the statements feed.")

    warnings: List[str] = []
    rev_ccy = (inputs["revenue"] or {}).get("currency")
    if rev_ccy and price_ccy and rev_ccy != price_ccy:
        warnings.append("Revenue is in {} and the price is in {}. A per-share value would mix the "
                        "two, so convert the revenue first or read the result as indicative "
                        "only.".format(rev_ccy, price_ccy))
    if stmt_ccy and price_ccy and stmt_ccy != price_ccy and "margin" in stm:
        warnings.append("The statements are in {} and the price in {}; the margin is a ratio of "
                        "the same currency, so it is unaffected.".format(stmt_ccy, price_ccy))
    if stmt_ccy and price_ccy and stmt_ccy != price_ccy and shares:
        warnings.append("A foreign listing's share count may count ordinary shares rather than "
                        "the receipts quoted here. Check the ratio before trusting a per-share "
                        "figure.")
    if facts.get("stale"):
        warnings.append("The SEC filings could not be refreshed just now; these are the last "
                        "ones read, {} days old.".format(facts.get("cache_age_days")))

    return {
        "available": True,
        "ticker": sym,
        "name": quote.get("name"),
        "inputs": inputs,
        "history": history,
        "warnings": warnings,
        "price_currency": price_ccy,
        "statement_currency": stmt_ccy,
        "note": ("Reported figures as the feeds give them, each with its source and date. "
                 "Every scenario input is yours; the history row shows what already happened "
                 "and is not a forecast."),
    }
