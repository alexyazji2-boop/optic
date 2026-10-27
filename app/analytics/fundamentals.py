"""Company-level context: short interest, financials, insider and institutional
activity, and the earnings track record.

Purpose here is swing-relevant framing, not a full model. Each block answers one
question: is the float crowded, is the business actually growing, are the people
who know most buying or selling, and does this company usually beat?
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List, Optional

import numpy as np
from .. import session as session_mod

# yfinance's statement row labels. Kept as tuples of aliases because the exact
# label varies by filer and by statement vintage.
ROW_ALIASES = {
    "revenue": ("Total Revenue", "Operating Revenue"),
    "gross_profit": ("Gross Profit",),
    "operating_income": ("Total Operating Income As Reported", "Operating Income"),
    # The statement's own EBITDA line, as Yahoo carries it. Not "Normalized
    # EBITDA", which also strips unusual items and is a different figure. Banks
    # and insurers report none, and the field is left empty rather than built.
    "ebitda": ("EBITDA",),
    "net_income": (
        "Net Income Common Stockholders",
        "Net Income",
        "Net Income From Continuing Operation Net Minority Interest",
    ),
    "diluted_eps": ("Diluted EPS",),
    "cash": ("Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"),
    "total_debt": ("Total Debt",),
    "total_assets": ("Total Assets",),
    "total_equity": ("Stockholders Equity", "Total Equity Gross Minority Interest"),
    "free_cash_flow": ("Free Cash Flow",),
    "operating_cash_flow": ("Operating Cash Flow",),
    # spending on property and equipment, negative on the statement (cash out); free cash flow is operating cash
    # flow plus it
    "capital_expenditure": ("Capital Expenditure",),
    # the weighted diluted share count the statement's diluted EPS divides by
    "diluted_shares": ("Diluted Average Shares",),
}



# A holder "added" or "trimmed" when its stake changed by more than this fraction of itself at the last 13F.
HOLDER_CHANGE = 0.02

def _f(value: Any, digits: int = 4) -> Optional[float]:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(out) else round(out, digits)


def _pick_row(block: Optional[Dict[str, Any]], key: str,
              periods: Optional[List[str]] = None) -> Optional[List[Optional[float]]]:
    """A statement line by its aliases. With `periods`, its values in those periods' order, matched by date:
    the cash-flow statement carries a fifth column the income statement does not, and read by position its
    free cash flow sat under the wrong fiscal year (audit 2026-10-20)."""
    if not block:
        return None
    rows = block.get("rows") or {}
    for alias in ROW_ALIASES.get(key, ()):
        if alias in rows:
            vals = rows[alias]
            if periods is None:
                return vals
            return _aligned(block.get("periods") or [], vals, periods)
    return None


def _aligned(own: List[str], vals: List[Optional[float]], want: List[str]) -> List[Optional[float]]:
    """`vals` (on `own` period ends) placed under `want`'s period ends: the same date, or one within 15 days
    (a 52-or-53-week filer's statements can end a few days apart); None where the statement has no column."""
    out: List[Optional[float]] = []
    dates = []
    for p in own:
        try:
            dates.append(dt.date.fromisoformat(str(p)[:10]))
        except ValueError:
            dates.append(None)
    for w in want:
        try:
            wd = dt.date.fromisoformat(str(w)[:10])
        except ValueError:
            out.append(None)
            continue
        best = None
        for i, d in enumerate(dates):
            if d is not None and abs((d - wd).days) <= 15 and i < len(vals):
                if best is None or abs((d - wd).days) < abs((dates[best] - wd).days):
                    best = i
        out.append(vals[best] if best is not None else None)
    return out


# ------------------------------------------------------------ fiscal periods

def _is_calendar(fy_end: dt.date) -> bool:
    """A fiscal year that is the calendar year (ending in the last week of December or the first of January)."""
    return (fy_end.month == 12 and fy_end.day >= 24) or (fy_end.month == 1 and fy_end.day <= 7)


def fiscal_label(period_end: Any, fy_end: Any, annual: bool = False) -> Optional[str]:
    """A period end as the company's own fiscal period: "Q1 FY26" for Microsoft's quarter to 30 September
    2025, "Q3 2026" for a calendar-year filer, "FY26" or "2026" for a year. The same quarter used to read as
    "Jun 30 2026" on Earnings, "Jun 27 26" on Segments and "Jul 30 2026" as a report date (audit 2026-10-20).
    `fy_end` is any fiscal year end the company has reported (the latest annual statement's)."""
    try:
        d = dt.date.fromisoformat(str(period_end)[:10])
        fe = dt.date.fromisoformat(str(fy_end)[:10])
    except (TypeError, ValueError):
        return None
    cal = _is_calendar(fe)
    # the fiscal year that holds d ends on the first anniversary of fe on or after d (10 days' tolerance for a
    # 52-or-53-week year, whose end drifts)
    try:
        end = fe.replace(year=d.year)
    except ValueError:                       # 29 February
        end = fe.replace(year=d.year, day=28)
    if end < d - dt.timedelta(days=10):
        try:
            end = end.replace(year=end.year + 1)
        except ValueError:
            end = end.replace(year=end.year + 1, day=28)
    year = end.year
    if cal and end.month == 1:
        year = end.year - 1                  # a 52-week year ending 2 January 2027 is the year 2026
    if annual:
        return str(year) if cal else "FY{:02d}".format(year % 100)
    q = 4 - int(round((end - d).days / 91.31))
    if not 1 <= q <= 4:
        return None
    return "Q{} {}".format(q, year) if cal else "Q{} FY{:02d}".format(q, year % 100)


def reported_quarter(report_date: Any, fy_end: Any) -> Optional[str]:
    """The fiscal quarter an earnings report covers: the latest quarter end at least five days before it,
    on the company's own quarter grid (its fiscal year end, stepped back in quarters of 91.31 days)."""
    try:
        r = dt.date.fromisoformat(str(report_date)[:10])
        fe = dt.date.fromisoformat(str(fy_end)[:10])
    except (TypeError, ValueError):
        return None
    cut = r - dt.timedelta(days=5)
    k = int(np.floor((cut - fe).days / 91.31))
    q_end = fe + dt.timedelta(days=round(k * 91.31))
    if q_end > cut:
        q_end = fe + dt.timedelta(days=round((k - 1) * 91.31))
    if (r - q_end).days > 120:
        return None
    return fiscal_label(q_end, fe)


# One rule for a beat: above the estimate. Exactly on it (a surprise that rounds to 0.0%) is in line, neither
# a beat nor a miss. The Earnings page counted in line as a miss and Financials as neither, over different
# denominators, so the two pages gave one company two beat rates (audit 2026-10-20).
def surprise_counts(surprises: List[Optional[float]]) -> Dict[str, Any]:
    vals = [round(float(s), 1) for s in surprises if s is not None and np.isfinite(s)]
    beats = sum(v > 0 for v in vals)
    misses = sum(v < 0 for v in vals)
    return {"beat_count": beats, "miss_count": misses, "in_line_count": len(vals) - beats - misses,
            "rate_quarters": len(vals),
            "beat_rate_pct": _f(beats / len(vals) * 100.0, 1) if vals else None}


def _growth(values: Optional[List[Optional[float]]]) -> Optional[float]:
    """Period-over-period growth. yfinance returns newest-first columns.

    None from a base at or below zero. Growth from a loss has no meaningful
    percentage, and the arithmetic gives the wrong sign: a loss of 100 turning
    into a profit of 50 came out as -150%, "net income fell 150%", and a loss
    narrowing from 100 to 50 as a 50% fall.
    """
    if not values or len(values) < 2:
        return None
    current, prior = values[0], values[1]
    if current is None or prior is None or prior <= 0:
        return None
    return _f((current / prior - 1.0) * 100.0, 2)


# ------------------------------------------------------------ short interest


def analyse_short_interest(raw: Dict[str, Any], avg_volume: Optional[float]) -> Dict[str, Any]:
    if not raw:
        return {"available": False}

    pct_float = raw.get("short_percent_float")
    shares = raw.get("shares_short")
    prior = raw.get("shares_short_prior")
    days_to_cover = raw.get("short_ratio_days")

    change_pct = None
    if shares and prior:
        change_pct = _f((shares / prior - 1.0) * 100.0, 2)

    notes: List[str] = []
    # Without the share of float there is no reading of crowding: "low" from nothing was a conclusion drawn
    # from missing data (design review, 2026-10-19). Both apps print this word.
    squeeze = "low" if pct_float is not None else "not known"

    if pct_float is not None:
        pct = pct_float * 100.0
        if pct >= 20:
            squeeze = "high"
            notes.append(
                "{:.1f}% of float is short. Crowded enough that good news forces covering. "
                "Cuts both ways: crowded shorts also mean informed scepticism.".format(pct)
            )
        elif pct >= 10:
            squeeze = "elevated"
            notes.append("{:.1f}% of float short. Meaningful bearish positioning.".format(pct))
        elif pct >= 5:
            squeeze = "moderate"
            notes.append("{:.1f}% of float short. Normal for a liquid name.".format(pct))
        else:
            notes.append("{:.1f}% of float short. No crowding.".format(pct))

    if days_to_cover is not None:
        if days_to_cover >= 5:
            notes.append(
                "{:.1f} days to cover at average volume: a rough crowding measure, high here. "
                "Crowded shorts are the condition squeezes come from, not a sign one is "
                "coming.".format(days_to_cover)
            )
        else:
            notes.append("{:.1f} days to cover at average volume: a rough crowding measure, "
                         "low here. It is not a guarantee of how buying back would move the price.".format(days_to_cover))

    if change_pct is not None:
        if change_pct > 10:
            notes.append("Short interest rose {:.0f}% versus the prior settlement. More shares are sold short.".format(change_pct))
        elif change_pct < -10:
            notes.append("Short interest fell {:.0f}% versus the prior settlement. Fewer shares are sold short.".format(abs(change_pct)))

    return {
        "available": True,
        "shares_short": shares,
        "shares_short_prior": prior,
        "change_vs_prior_pct": change_pct,
        "percent_of_float": pct_float,
        "days_to_cover": days_to_cover,
        "float_shares": raw.get("float_shares"),
        "settlement_date": raw.get("settlement_date"),
        "squeeze_potential": squeeze,
        "notes": notes,
        "caveat": "Short interest is reported twice monthly and lags by roughly two weeks. "
        "Treat it as positioning background, not a live signal.",
    }


# ---------------------------------------------------------------- financials


def analyse_financials(raw: Dict[str, Any]) -> Dict[str, Any]:
    if not raw:
        return {"available": False}

    annual = raw.get("income_annual")
    quarterly = raw.get("income_quarterly")
    balance = raw.get("balance_annual")
    cash = raw.get("cashflow_annual")

    if not annual and not quarterly:
        return {"available": False, "note": "No statement data. Common for ETFs and index products."}

    rev_a = _pick_row(annual, "revenue")
    ni_a = _pick_row(annual, "net_income")
    gp_a = _pick_row(annual, "gross_profit")
    oi_a = _pick_row(annual, "operating_income")
    ebitda_a = _pick_row(annual, "ebitda")
    eps_a = _pick_row(annual, "diluted_eps")

    rev_q = _pick_row(quarterly, "revenue")
    ni_q = _pick_row(quarterly, "net_income")
    eps_q = _pick_row(quarterly, "diluted_eps")
    gp_q = _pick_row(quarterly, "gross_profit")
    oi_q = _pick_row(quarterly, "operating_income")
    ebitda_q = _pick_row(quarterly, "ebitda")
    a_periods = (annual or {}).get("periods") or []
    q_periods = (quarterly or {}).get("periods") or []
    fy_end = a_periods[0] if a_periods else None

    def margin(numer, denom, idx=0):
        if not numer or not denom or len(numer) <= idx or len(denom) <= idx:
            return None
        n, d = numer[idx], denom[idx]
        if n is None or d in (None, 0):
            return None
        # four places, so every display rounds once from near the raw ratio: rounded to two here and to one
        # again on the page, RIVN's -66.549% read -66.6% on the card and -66.5% on the chart (audit 2026-10-22)
        return _f(n / d * 100.0, 4)

    total_debt = _pick_row(balance, "total_debt")
    cash_bal = _pick_row(balance, "cash")
    equity = _pick_row(balance, "total_equity")
    # on the income statement's fiscal years, by date: the cash-flow statement's columns are not the same list
    fcf = _pick_row(cash, "free_cash_flow", a_periods) if a_periods else _pick_row(cash, "free_cash_flow")
    # the lines behind free cash flow, and cash and debt at each fiscal year end, on the same years (the charts on
    # Financials, 2026-10-20); the diluted share count behind EPS, yearly and quarterly
    ocf = _pick_row(cash, "operating_cash_flow", a_periods) if a_periods else None
    capex = _pick_row(cash, "capital_expenditure", a_periods) if a_periods else None
    cash_hist = _pick_row(balance, "cash", a_periods) if a_periods else None
    debt_hist = _pick_row(balance, "total_debt", a_periods) if a_periods else None
    shares_a = _pick_row(annual, "diluted_shares")
    shares_q = _pick_row(quarterly, "diluted_shares")

    net_cash = None
    if cash_bal and total_debt and cash_bal[0] is not None and total_debt[0] is not None:
        net_cash = _f(cash_bal[0] - total_debt[0], 0)

    debt_to_equity = None
    if total_debt and equity and total_debt[0] is not None and equity[0] not in (None, 0):
        debt_to_equity = _f(total_debt[0] / equity[0], 2)

    notes: List[str] = []
    rev_growth = _growth(rev_a)
    ni_growth = _growth(ni_a)
    rev_growth_q = _growth(rev_q)

    if rev_growth is not None:
        notes.append("Annual revenue {} {:.1f}%.".format("grew" if rev_growth >= 0 else "fell", abs(rev_growth)))
    if ni_growth is not None:
        notes.append("Annual net income {} {:.1f}%.".format("grew" if ni_growth >= 0 else "fell", abs(ni_growth)))
    if rev_growth_q is not None:
        notes.append("Most recent quarter revenue {} {:.1f}% versus the prior quarter.".format(
            "grew" if rev_growth_q >= 0 else "fell", abs(rev_growth_q)))

    gm = margin(gp_a, rev_a)
    om = margin(oi_a, rev_a)
    em = margin(ebitda_a, rev_a)
    nm = margin(ni_a, rev_a)
    if gm is not None:
        notes.append("Gross margin {:.1f}%, operating margin {}, net margin {}.".format(
            gm,
            "{:.1f}%".format(om) if om is not None else "n/a",
            "{:.1f}%".format(nm) if nm is not None else "n/a",
        ))
    if net_cash is not None:
        notes.append("{} net {} position.".format(
            "$" + _human(abs(net_cash)), "cash" if net_cash >= 0 else "debt"))
    if debt_to_equity is not None and debt_to_equity > 2:
        notes.append("Debt/equity {:.1f}. Leveraged balance sheet raises the stakes on a miss.".format(debt_to_equity))

    return {
        "available": True,
        "annual_periods": (annual or {}).get("periods"),
        "quarterly_periods": (quarterly or {}).get("periods"),
        # each period as the company names it: "FY26", "Q1 FY26", "2026", "Q3 2026"
        "fiscal_year_end": fy_end,
        "annual_fiscal": [fiscal_label(p, fy_end, annual=True) for p in a_periods] if fy_end else [],
        "quarterly_fiscal": [fiscal_label(p, fy_end) for p in q_periods] if fy_end else [],
        "annual": {
            "revenue": rev_a, "gross_profit": gp_a, "operating_income": oi_a, "ebitda": ebitda_a,
            "net_income": ni_a, "diluted_eps": eps_a, "free_cash_flow": fcf,
            "operating_cash_flow": ocf, "capital_expenditure": capex, "diluted_shares": shares_a,
        },
        "quarterly": {"revenue": rev_q, "gross_profit": gp_q, "operating_income": oi_q, "ebitda": ebitda_q,
                      "net_income": ni_q, "diluted_eps": eps_q, "diluted_shares": shares_q},
        # cash and equivalents and total debt at each fiscal year end, under annual_periods
        "balance_history": {"cash": cash_hist, "total_debt": debt_hist},
        # Yahoo carries the filings' statements; the diluted EPS here is the statement's (GAAP), which is not
        # the basis analysts' estimates and surprises use (usually adjusted)
        "source": "The company's annual and quarterly statements as Yahoo Finance carries them.",
        "eps_basis": "Diluted EPS from the income statement (GAAP).",
        "margins": {"gross_pct": gm, "operating_pct": om, "ebitda_pct": em, "net_pct": nm},
        "growth": {
            "revenue_yoy_pct": rev_growth,
            "net_income_yoy_pct": ni_growth,
            "revenue_qoq_pct": rev_growth_q,
        },
        "balance_sheet": {
            "cash": cash_bal[0] if cash_bal else None,
            "total_debt": total_debt[0] if total_debt else None,
            "net_cash": net_cash,
            "total_equity": equity[0] if equity else None,
            "debt_to_equity": debt_to_equity,
        },
        "notes": notes,
    }


def _human(value: float) -> str:
    for cut, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(value) >= cut:
            return "{:.2f}{}".format(value / cut, suffix)
    return "{:.0f}".format(value)


# ----------------------------------------------------------- earnings record


def analyse_earnings_history(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not rows:
        return {"available": False}

    reported = [r for r in rows if r.get("eps_reported") is not None][:8]
    upcoming = [r for r in rows if r.get("eps_reported") is None]

    if not reported:
        return {"available": False, "upcoming": upcoming[:2]}

    surprises = [r["surprise_pct"] for r in reported if r.get("surprise_pct") is not None]
    counts = surprise_counts(surprises)
    beat_rate = counts["beat_rate_pct"]
    # A percentage surprise on an estimate at or below zero is a ratio to nearly nothing: CRCL's -0.16
    # estimate made one quarter +813.9% and the average +249% (audit 2026-10-22). Those quarters still
    # count as beats or misses; they are left out of the average, which says how many it rests on.
    sized = [r["surprise_pct"] for r in reported if r.get("surprise_pct") is not None
             and r.get("eps_estimate") is not None and r["eps_estimate"] > 0]
    avg_surprise = _f(float(np.mean(sized)), 2) if sized else None
    left_out = len(surprises) - len(sized)

    notes: List[str] = []
    if beat_rate is not None:
        notes.append(
            "Beat consensus in {} of the last {} quarters ({:.0f}%){}{}.".format(
                counts["beat_count"], counts["rate_quarters"], beat_rate,
                ", {} in line".format(counts["in_line_count"]) if counts["in_line_count"] else "",
                ", average surprise {:+.1f}%{}".format(
                    avg_surprise, " over the {} with a positive estimate".format(len(sized)) if left_out else "")
                if avg_surprise is not None else "",
            )
        )
    if counts["miss_count"] >= 2:
        notes.append("{} misses in the window. The beat streak is not dependable.".format(counts["miss_count"]))
    # only for a record that is consistent: beside "3 misses, not dependable" it contradicted itself (RIVN)
    if avg_surprise is not None and avg_surprise > 5 and counts["miss_count"] < 2 and (beat_rate or 0) >= 75:
        notes.append(
            "A consistent large beat is usually already in the price; the reaction depends on guidance, not the print."
        )

    return {
        "available": True,
        # the track record is on analysts' basis; the per-share chart on the same page is GAAP, and CRCL's
        # reported 1.12 sat beside a GAAP -4.48 for the same quarter with nothing saying why (audit 2026-10-22)
        "eps_basis": ("Estimates and reported EPS on the basis analysts use, usually adjusted, which can differ "
                      "from the GAAP diluted EPS charted above."),
        "quarters": reported,
        "upcoming": upcoming[:2],
        "beat_count": counts["beat_count"],
        "miss_count": counts["miss_count"],
        "in_line_count": counts["in_line_count"],
        "sample_size": counts["rate_quarters"],
        "beat_rate_pct": beat_rate,
        "avg_surprise_pct": avg_surprise,
        "notes": notes,
    }


# ------------------------------------------------ insider & institutional flow


def _six_month_trades(trades: List[Dict[str, Any]], now: Optional[dt.date] = None) -> Dict[str, Any]:
    """Open-market purchases and sales over the last six months, from the classified Form 4 rows.

    Yahoo's own six-month tally ("Purchases", "Sales") counts every acquisition, stock awards and option
    exercises included: Microsoft's said 16 purchases against 10 sales and "net buying" when its rows held
    2 purchases, 28 sales and 60 awards and grants (audit 2026-10-20). An award is not a decision to buy.
    The signal is read from purchases and sales only; the rest are counted and named."""
    today = now or session_mod.market_today()
    cutoff = (today - dt.timedelta(days=182)).isoformat()
    rows = [r for r in trades if str(r.get("date") or "") >= cutoff]
    buys = [r for r in rows if r.get("action") == "purchase"]
    sells = [r for r in rows if r.get("action") == "sale"]
    total = lambda xs, k: sum(float(r.get(k) or 0) for r in xs)          # noqa: E731
    # the provider keeps two years and up to 200 rows: when the oldest row kept is inside the window, rows
    # before it may be missing, and the counts are a floor
    oldest = min((str(r.get("date") or "") for r in trades), default="")
    return {
        "basis": "open_market",
        "since": cutoff,
        "purchase_count": len(buys), "purchase_shares": total(buys, "shares"), "purchase_value": total(buys, "value"),
        "sale_count": len(sells), "sale_shares": total(sells, "shares"), "sale_value": total(sells, "value"),
        "other_count": len(rows) - len(buys) - len(sells),
        "net_shares": total(buys, "shares") - total(sells, "shares"),
        "complete": not (len(trades) >= 200 and oldest > cutoff),
    }


def analyse_ownership(insiders: Dict[str, Any], institutions: Dict[str, Any],
                      now: Optional[dt.date] = None) -> Dict[str, Any]:
    summary = (insiders or {}).get("summary_6m") or {}
    trades = (insiders or {}).get("transactions") or []
    breakdown = (institutions or {}).get("breakdown") or {}
    # A list, empty or not. `or {}` turned an empty list into a dict, the page
    # called .slice on it, and the whole Financials tab rendered blank for any
    # stock whose holders call came back empty (KO, locally, 2026-10-06).
    holders = (institutions or {}).get("top_holders") or []

    def find(*needles) -> Optional[Dict[str, Any]]:
        for key, value in summary.items():
            low = key.lower()
            if all(n in low for n in needles):
                return value
        return None

    purchases = find("purchase")
    sales = find("sale")
    net = find("net", "purchased")

    notes: List[str] = []
    insider_signal = "neutral"
    six = _six_month_trades(trades, now)
    net_shares = six["net_shares"] if trades else (net or {}).get("shares")
    other = " {} awards, grants, gifts and option exercises are not counted: they are not decisions to buy or sell.".format(
        six["other_count"]) if six["other_count"] else ""
    if trades and not six["purchase_count"] and not six["sale_count"]:
        # "neutral", the word the classic page already prints ("Insiders are net neutral"); the counts say none
        insider_signal = "neutral"
        notes.append("No open-market purchases or sales by insiders in six months." + other)
    elif net_shares is not None and trades:
        if net_shares > 0:
            insider_signal = "buying"
            notes.append(
                "Insiders bought {} more shares on the open market than they sold over six months ({} purchases, "
                "{} sales). Insider buying is the more informative direction. There is only one reason to buy.{}".format(
                    _human(net_shares), six["purchase_count"], six["sale_count"], other))
        elif net_shares < 0:
            insider_signal = "selling"
            notes.append(
                "Insiders sold {} more shares on the open market than they bought over six months ({} sales, "
                "{} purchases). Much insider selling is scheduled diversification, so treat it as weak "
                "evidence.{}".format(_human(abs(net_shares)), six["sale_count"], six["purchase_count"], other))
        else:
            notes.append("Insider purchases and sales offset over six months." + other)

    inst_pct = None
    for key, value in breakdown.items():
        if "institutionsPercentHeld" in key:
            inst_pct = value
    insiders_pct = None
    for key, value in breakdown.items():
        if "insidersPercentHeld" in key:
            insiders_pct = value

    if inst_pct is not None:
        pct = inst_pct * 100.0
        if pct > 80:
            notes.append("{:.0f}% institutionally held. Moves are driven by fund flows and rebalancing.".format(pct))
        elif pct < 30:
            notes.append("Only {:.0f}% institutionally held. A more retail-driven, and typically more volatile, shareholder base.".format(pct))
        else:
            notes.append("{:.0f}% institutionally held.".format(pct))

    # Counted against a 2% change in the holder's own stake, so small rebalancing is not "adding". The scope and
    # the threshold travel with the counts: a page said "two added" above a list with six positive changes and
    # said neither (owner, 2026-10-19).
    accumulating = [h for h in holders if (h.get("pct_change") or 0) > HOLDER_CHANGE]
    trimming = [h for h in holders if (h.get("pct_change") or 0) < -HOLDER_CHANGE]
    if accumulating or trimming:
        notes.append(
            "Of the {} largest reported holders, {} raised and {} cut their stake by more than {:.0f}% at the "
            "last 13F; the rest changed by less.".format(len(holders), len(accumulating), len(trimming), HOLDER_CHANGE * 100)
        )

    return {
        "available": bool(summary or holders),
        "insider_signal": insider_signal,
        # Open-market purchases and sales over six months, from the Form 4 rows below (since 2026-10-20).
        "insider_6m": six if trades else {
            "basis": "yahoo_tally",
            "purchase_shares": (purchases or {}).get("shares"),
            "purchase_count": (purchases or {}).get("transactions"),
            "sale_shares": (sales or {}).get("shares"),
            "sale_count": (sales or {}).get("transactions"),
            "net_shares": net_shares,
        },
        # Yahoo's own six-month tally, kept and named for what it counts: every acquisition and disposal
        "yahoo_tally_6m": {
            "acquired_shares": (purchases or {}).get("shares"), "acquired_count": (purchases or {}).get("transactions"),
            "disposed_shares": (sales or {}).get("shares"), "disposed_count": (sales or {}).get("transactions"),
            "net_shares": (net or {}).get("shares"),
            "note": "Yahoo Finance's count of every acquisition and disposal, awards and option exercises included.",
        },
        "insider_method": ("Open-market purchases and sales (Form 4 codes P and S) by officers, directors and 10% owners "
                           "in the last six months, from the filings Yahoo Finance lists for the last two years. "
                           "A transaction date is when the trade happened; it became public when the Form 4 was filed, "
                           "usually within two business days. Reported history, not current trading."),
        "recent_transactions": trades,
        "institutional_pct_held": inst_pct,
        "insider_pct_held": insiders_pct,
        "top_holders": holders,
        "holders_adding": len(accumulating),
        "holders_trimming": len(trimming),
        "holders_counted": len(holders),
        "holder_change_threshold_pct": HOLDER_CHANGE * 100,
        "notes": notes,
        "caveat": "13F institutional holdings are filed quarterly with a 45-day lag; insider filings are "
        "prompt but often reflect pre-scheduled plans.",
    }


# ------------------------------------------------------------------ assembly


def analyse(provider, ticker: str, quote: Dict[str, Any]) -> Dict[str, Any]:
    short_raw = provider.short_interest(ticker)
    fin_raw = provider.financials(ticker)
    earn_raw = provider.earnings_history(ticker)
    ins_raw = provider.insiders(ticker)
    inst_raw = provider.institutions(ticker)

    return {
        "short_interest": analyse_short_interest(short_raw, quote.get("avg_volume")),
        "financials": analyse_financials(fin_raw),
        "earnings_history": analyse_earnings_history(earn_raw),
        "ownership": analyse_ownership(ins_raw, inst_raw),
    }
