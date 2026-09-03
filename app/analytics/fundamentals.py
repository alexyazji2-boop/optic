"""Company-level context: short interest, financials, insider and institutional
activity, and the earnings track record.

Purpose here is swing-relevant framing, not a full model. Each block answers one
question: is the float crowded, is the business actually growing, are the people
who know most buying or selling, and does this company usually beat?
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

# yfinance's statement row labels. Kept as tuples of aliases because the exact
# label varies by filer and by statement vintage.
ROW_ALIASES = {
    "revenue": ("Total Revenue", "Operating Revenue"),
    "gross_profit": ("Gross Profit",),
    "operating_income": ("Total Operating Income As Reported", "Operating Income"),
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
}


def _f(value: Any, digits: int = 4) -> Optional[float]:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(out) else round(out, digits)


def _pick_row(block: Optional[Dict[str, Any]], key: str) -> Optional[List[Optional[float]]]:
    if not block:
        return None
    rows = block.get("rows") or {}
    for alias in ROW_ALIASES.get(key, ()):
        if alias in rows:
            return rows[alias]
    return None


def _growth(values: Optional[List[Optional[float]]]) -> Optional[float]:
    """Period-over-period growth. yfinance returns newest-first columns."""
    if not values or len(values) < 2:
        return None
    current, prior = values[0], values[1]
    if current is None or prior is None or prior == 0:
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
    squeeze = "low"

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
                "{:.1f} days to cover at average volume. Shorts cannot exit quickly, "
                "which is what makes squeezes violent.".format(days_to_cover)
            )
        else:
            notes.append("{:.1f} days to cover. Shorts can exit without moving price much.".format(days_to_cover))

    if change_pct is not None:
        if change_pct > 10:
            notes.append("Short interest rose {:.0f}% versus the prior settlement. Bears are adding.".format(change_pct))
        elif change_pct < -10:
            notes.append("Short interest fell {:.0f}% versus the prior settlement. Bears are covering.".format(abs(change_pct)))

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
        "caveat": "Short interest is reported twice monthly and lags by roughly two weeks . "
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
    eps_a = _pick_row(annual, "diluted_eps")

    rev_q = _pick_row(quarterly, "revenue")
    ni_q = _pick_row(quarterly, "net_income")
    eps_q = _pick_row(quarterly, "diluted_eps")

    def margin(numer, denom, idx=0):
        if not numer or not denom or len(numer) <= idx or len(denom) <= idx:
            return None
        n, d = numer[idx], denom[idx]
        if n is None or d in (None, 0):
            return None
        return _f(n / d * 100.0, 2)

    total_debt = _pick_row(balance, "total_debt")
    cash_bal = _pick_row(balance, "cash")
    equity = _pick_row(balance, "total_equity")
    fcf = _pick_row(cash, "free_cash_flow")

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
        "annual": {
            "revenue": rev_a, "gross_profit": gp_a, "operating_income": oi_a,
            "net_income": ni_a, "diluted_eps": eps_a, "free_cash_flow": fcf,
        },
        "quarterly": {"revenue": rev_q, "net_income": ni_q, "diluted_eps": eps_q},
        "margins": {"gross_pct": gm, "operating_pct": om, "net_pct": nm},
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

    beats = [r for r in reported if (r.get("surprise_pct") or 0) > 0]
    misses = [r for r in reported if (r.get("surprise_pct") or 0) < 0]
    surprises = [r["surprise_pct"] for r in reported if r.get("surprise_pct") is not None]

    beat_rate = _f(len(beats) / len(reported) * 100.0, 1)
    avg_surprise = _f(float(np.mean(surprises)), 2) if surprises else None

    notes: List[str] = []
    if beat_rate is not None:
        notes.append(
            "Beat consensus in {} of the last {} quarters ({:.0f}%){}.".format(
                len(beats), len(reported), beat_rate,
                ", average surprise {:+.1f}%".format(avg_surprise) if avg_surprise is not None else "",
            )
        )
    if len(misses) >= 2:
        notes.append("{} misses in the window. The beat streak is not dependable.".format(len(misses)))
    if avg_surprise is not None and avg_surprise > 5:
        notes.append(
            "A consistent large beat is usually already in the price; the reaction depends on guidance, not the print."
        )

    return {
        "available": True,
        "quarters": reported,
        "upcoming": upcoming[:2],
        "beat_count": len(beats),
        "miss_count": len(misses),
        "sample_size": len(reported),
        "beat_rate_pct": beat_rate,
        "avg_surprise_pct": avg_surprise,
        "notes": notes,
    }


# ------------------------------------------------ insider & institutional flow


def analyse_ownership(insiders: Dict[str, Any], institutions: Dict[str, Any]) -> Dict[str, Any]:
    summary = (insiders or {}).get("summary_6m") or {}
    trades = (insiders or {}).get("transactions") or []
    breakdown = (institutions or {}).get("breakdown") or {}
    holders = (institutions or {}).get("top_holders") or {}

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

    net_shares = (net or {}).get("shares")
    if net_shares is not None:
        if net_shares > 0:
            insider_signal = "buying"
            notes.append(
                "Insiders were net buyers of {} shares over six months. Insider buying is the more "
                "informative direction. There is only one reason to buy.".format(_human(net_shares))
            )
        elif net_shares < 0:
            insider_signal = "selling"
            notes.append(
                "Insiders were net sellers of {} shares over six months. Much insider selling is "
                "scheduled diversification or option exercise, so treat it as weak evidence.".format(_human(abs(net_shares)))
            )
        else:
            notes.append("Insider buying and selling roughly offset over six months.")

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

    accumulating = [h for h in holders if (h.get("pct_change") or 0) > 0.02]
    trimming = [h for h in holders if (h.get("pct_change") or 0) < -0.02]
    if accumulating or trimming:
        notes.append(
            "Among the largest reported holders, {} added and {} trimmed at the last 13F.".format(
                len(accumulating), len(trimming)
            )
        )

    return {
        "available": bool(summary or holders),
        "insider_signal": insider_signal,
        "insider_6m": {
            "purchase_shares": (purchases or {}).get("shares"),
            "purchase_count": (purchases or {}).get("transactions"),
            "sale_shares": (sales or {}).get("shares"),
            "sale_count": (sales or {}).get("transactions"),
            "net_shares": net_shares,
        },
        "recent_transactions": trades,
        "institutional_pct_held": inst_pct,
        "insider_pct_held": insiders_pct,
        "top_holders": holders,
        "holders_adding": len(accumulating),
        "holders_trimming": len(trimming),
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
