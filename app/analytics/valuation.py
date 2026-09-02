"""Where today's multiple sits in the company's own five-year range.

A P/E on its own says almost nothing. Forty times earnings is cheap for one
business and absurd for another, and the only comparison that needs no
cross-company assumptions is the company against itself: is this name expensive
*for this name*?

Built from reported annual diluted EPS and the actual share price during each of
those fiscal years. Deliberately trailing-only. Historical *forward* multiples
would need the consensus estimate as it stood at the time, which nothing here
keeps, and reconstructing it from today's estimates would quietly compare a known
past against a hoped-for future.

Earnings-per-share is used rather than revenue or cash flow because EPS is already
per-share. Any revenue multiple needs a share count for each historical year, and
buybacks and issuance move that enough to turn the answer into an artefact of the
share count rather than a statement about valuation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

# A band needs enough years to have a middle. Three is the floor: two gives a
# midpoint that is really just the average of the endpoints.
MIN_YEARS = 3

# Percentile bands for the plain-English read.
RICH_PCT, CHEAP_PCT = 75.0, 25.0


def _num(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if out != out or out in (float("inf"), float("-inf")):
        return None
    return out


def _avg_price_in_year(frame: pd.DataFrame, end: str) -> Optional[float]:
    """Mean close over the fiscal year ending on `end`.

    The average across the year, not the closing price on the last day. A single
    date makes the multiple a function of whatever the stock happened to do that
    week, and fiscal year-ends cluster near quarter boundaries where moves are
    larger than usual.
    """
    if frame is None or frame.empty or "Close" not in frame:
        return None
    try:
        stop = pd.Timestamp(end)
    except (ValueError, TypeError):
        return None
    start = stop - pd.Timedelta(days=365)
    idx = frame.index
    if getattr(idx, "tz", None) is not None:
        start, stop = start.tz_localize(idx.tz), stop.tz_localize(idx.tz)
    window = frame.loc[(idx > start) & (idx <= stop), "Close"].dropna()
    if window.empty:
        return None
    return float(window.mean())


def history_band(provider, ticker: str, financials: Dict[str, Any],
                 current_pe: Optional[float]) -> Dict[str, Any]:
    """Trailing P/E for each reported fiscal year, and where today sits in it."""
    periods = (financials or {}).get("annual_periods") or []
    annual = (financials or {}).get("annual") or {}
    eps_row = annual.get("diluted_eps") or []
    if not periods or not eps_row:
        return {"available": False, "reason": "no reported annual EPS"}

    try:
        # Six years of dailies to cover five fiscal years plus the earliest year's
        # opening months. Cached by the provider, so this is usually free.
        frame = provider.history(ticker, period="6y", interval="1d")
    except Exception as exc:
        return {"available": False, "reason": f"price history unavailable: {exc}"}

    years: List[Dict[str, Any]] = []
    for i, period in enumerate(periods):
        eps = _num(eps_row[i]) if i < len(eps_row) else None
        avg = _avg_price_in_year(frame, period)
        if eps is None or avg is None:
            continue
        if eps <= 0:
            # A loss year has no meaningful P/E. Recorded so the panel can say the
            # year existed and was excluded, rather than silently shortening the
            # history and making the band look tighter than it is.
            years.append({"period": str(period)[:10], "eps": round(eps, 4),
                          "avg_price": round(avg, 2), "pe": None,
                          "note": "loss-making year, no meaningful multiple"})
            continue
        years.append({"period": str(period)[:10], "eps": round(eps, 4),
                      "avg_price": round(avg, 2), "pe": round(avg / eps, 1)})

    usable = [y["pe"] for y in years if y.get("pe") is not None]
    if len(usable) < MIN_YEARS:
        return {"available": False, "years": years,
                "reason": f"only {len(usable)} profitable year(s) with a usable multiple"}

    ordered = sorted(usable)
    mid = len(ordered) // 2
    median = ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2.0
    low, high = ordered[0], ordered[-1]

    pe = _num(current_pe)
    percentile = read = premium = None
    if pe is not None and pe > 0:
        below = sum(1 for v in ordered if v <= pe)
        percentile = round(below / len(ordered) * 100.0, 0)
        premium = round((pe / median - 1.0) * 100.0, 1)
        if percentile >= RICH_PCT:
            read = "expensive versus its own history"
        elif percentile <= CHEAP_PCT:
            read = "cheap versus its own history"
        else:
            read = "mid-range versus its own history"

    return {
        "available": True,
        "years": years,
        "current_pe": pe,
        "median_pe": round(median, 1),
        "low_pe": round(low, 1),
        "high_pe": round(high, 1),
        "percentile": percentile,
        "premium_to_median_pct": premium,
        "read": read,
        "usable_years": len(ordered),
        "method": (
            "Trailing P/E for each reported fiscal year: the company's own diluted "
            "EPS for that year against the average closing price across it. The "
            "average rather than the year-end close, because a single date makes the "
            "multiple a function of one week's price action. Loss-making years are "
            "listed but excluded — a negative P/E is not a cheap one. Trailing only: "
            "a historical forward multiple would need the consensus estimate as it "
            "stood then, which this tool does not keep."
        ),
    }


def revenue_and_multiple(financials: Dict[str, Any],
                         history: Dict[str, Any]) -> Dict[str, Any]:
    """Revenue per fiscal year alongside the P/E the market paid that year.

    The two series answer different halves of one question: revenue is what the
    business did, the multiple is what the market was willing to pay for it. Read
    together they show whether a rerating was earned by growth or was just
    sentiment — a revenue line rising while the multiple compresses is a very
    different story from both rising at once.

    **The window is short and that is a data limit, not a choice.** Free
    fundamentals give four reported fiscal years and about five quarters. The
    published versions of this chart run ten years or more off a licensed
    fundamentals feed; four points can show a direction but cannot establish a
    range, and the note says so rather than letting four bars imply a cycle.
    """
    periods = (financials or {}).get("annual_periods") or []
    annual = (financials or {}).get("annual") or {}
    revenue = annual.get("revenue") or []
    if not periods or not revenue:
        return {"available": False,
                "reason": "No annual revenue history in the free fundamentals feed."}

    pe_by_period = {}
    for row in (history or {}).get("years") or []:
        if row.get("period") and row.get("pe") is not None:
            pe_by_period[row["period"]] = row["pe"]

    rows = []
    for i, period in enumerate(periods):
        rev = revenue[i] if i < len(revenue) else None
        if rev is None:
            continue
        rows.append({
            "period": period,
            "label": str(period)[:4],
            "revenue": float(rev),
            "pe": pe_by_period.get(period),
        })
    # Oldest first, so the chart reads left to right like every other series here.
    rows.reverse()
    if len(rows) < 2:
        return {"available": False,
                "reason": "Fewer than two fiscal years of revenue — nothing to compare."}

    first, last = rows[0]["revenue"], rows[-1]["revenue"]
    growth = ((last / first) ** (1.0 / max(len(rows) - 1, 1)) - 1.0) * 100.0 if first > 0 else None

    quarterly = (financials or {}).get("quarterly") or {}
    q_periods = (financials or {}).get("quarterly_periods") or []
    q_rev = quarterly.get("revenue") or []
    q_rows = []
    for i, period in enumerate(q_periods):
        if i < len(q_rev) and q_rev[i] is not None:
            q_rows.append({"period": period, "revenue": float(q_rev[i])})
    q_rows.reverse()

    with_pe = [r for r in rows if r["pe"] is not None]
    return {
        "available": True,
        "years": rows,
        "quarters": q_rows,
        "revenue_cagr_pct": round(growth, 1) if growth is not None else None,
        "years_covered": len(rows),
        "years_with_pe": len(with_pe),
        "method": (
            "Revenue is the company's own reported annual figure. The multiple is "
            "the trailing P/E for that fiscal year — its diluted EPS against the "
            "average closing price across the year, not the year-end close, so one "
            "volatile December cannot define the whole year. Only {} fiscal years "
            "are available: free fundamentals stop there, and four points can show "
            "a direction but cannot establish a range the way a ten-year series "
            "would.".format(len(rows))
        ),
    }
