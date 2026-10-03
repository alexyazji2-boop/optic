"""What a stock is worth against its own record, what analysts say, and how safe its dividend looks.

Asked for with a list of what another app puts behind a paid tier ("stock picks
chosen by experts", a rating, research reports, model portfolios, "fair value
analysis + dividend scores"): "add these features to the optic terminal
wherever applicable". Model portfolios and stock ideas were here already (Optic
Portfolio, Scan), and the analysts' own ratings and targets were on the Earnings
tab. The two that were not: a fair value, and a dividend score. This builds
those two, and puts the analysts' view beside them on the Investing tab.

**Every figure here is computed from data the terminal already reads, and the
method is on the page.** Nothing is licensed and nothing is hand-set per name.

*Fair value* is the company's own trailing earnings at the multiples the market
has paid for it: the 25th percentile, the median and the 75th percentile of its
own weekly trailing P/E over the last five years, from SEC filings (see
pe_history), times its trailing twelve-month diluted EPS. It answers "what would
this be worth at the price-to-earnings it has usually been given", and it says
nothing about whether that multiple was right, or whether the business has
changed. It is a range to read the price against, never a target.

*The analysts' view* is each firm's published rating and price target as Yahoo
carries them: a count of buys, holds and sells, and the mean, low and high
target. It is what the sell side says, not a pick by Optic.

*The dividend score* is out of 100 from four things that can be checked in the
payment record: whether earnings cover the dividend, how many years in a row the
annual total has risen, the five-year growth of that total, and the yield. Each
is out of 25, and a part with no data is left out and the rest scaled.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from . import earnings as earnings_mod
from . import extras as extras_mod
from . import pe_history as pe_history_mod

log = logging.getLogger(__name__)

# Five years of weekly multiples is 260 points; under three years the quartiles
# are not a range worth putting a price on.
MIN_BAND_WEEKS = 156

# Where the price sits against the range, in the words the panel uses.
BELOW, INSIDE, ABOVE = "below its range", "inside its range", "above its range"
# A range wider than this share of its own middle is not a range to read a price
# against. Measured on 3 October 2026: Apple 0.22 and Coca-Cola 0.11, against
# Tesla 1.62 and Coinbase 1.19, whose multiples have swung from the teens into
# the hundreds and back. "Inside its range" over 78 to 423 says nothing.
WIDE_RANGE = 0.6
WIDE = "too wide to call"

# The dividend's four parts, each out of this.
PART_MAX = 25.0
STREAK_FULL_YEARS = 10
# A cut inside this many years caps the consistency part.
CUT_WINDOW_YEARS = 10
CUT_CAP = 8.0
# Past this a yield is more often the price falling than a generous payer.
HIGH_YIELD = 0.08
YIELD_FULL = 0.04
# Paid within this long ago, or it is not paying now.
PAYING_WITHIN_DAYS = 460


def _f(value: Any, digits: int = 2) -> Optional[float]:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if out != out else round(out, digits)


# --------------------------------------------------------------- fair value


def fair_value(pe: Dict[str, Any], price: Optional[float]) -> Dict[str, Any]:
    """The range, from the multiples history, or why there is none."""
    if not pe or not pe.get("available"):
        return {"available": False,
                "reason": (pe or {}).get("reason") or "No filed earnings history to value against."}
    series = pe.get("pe_series") or []
    bands = pe.get("pe_bands") or {}
    eps = _f((series[-1] or {}).get("ttm_eps"), 4) if series else None
    if not eps or eps <= 0:
        return {"available": False,
                "reason": "Trailing earnings are not positive, so a multiple of them is not a value."}
    if (pe.get("band_weeks") or 0) < MIN_BAND_WEEKS or pe.get("short_history"):
        return {"available": False,
                "reason": "Less than three years of weekly multiples, too little to call a range."}
    lo_pe, mid_pe, hi_pe = (_f(bands.get(k), 1) for k in ("25", "50", "75"))
    if None in (lo_pe, mid_pe, hi_pe) or not price or price <= 0:
        return {"available": False, "reason": "The multiple bands or the price are missing."}

    low, mid, high = (round(eps * m, 2) for m in (lo_pe, mid_pe, hi_pe))
    if price < low:
        position = BELOW
    elif price > high:
        position = ABOVE
    else:
        position = INSIDE
    width = round((high - low) / mid, 2)
    wide = width > WIDE_RANGE
    if wide:
        position = WIDE
    gap = round((price / mid - 1.0) * 100.0, 1)
    years = round((pe.get("band_weeks") or 0) / 52.0)
    return {
        "available": True,
        "price": round(price, 2),
        "low": low, "mid": mid, "high": high,
        "gap_to_mid_pct": gap,
        "position": position,
        "range_width": width,
        "wide": wide,
        "wide_note": ("Its multiple has swung too far for the range to say anything: the "
                      "25th to 75th percentile spans {:.0f}% of the middle value. The "
                      "numbers are shown, with no verdict.".format(width * 100)) if wide else None,
        "ttm_eps": eps,
        "multiples": {"low": lo_pe, "mid": mid_pe, "high": hi_pe,
                      "now": _f(pe.get("pe_current"), 1), "years": years},
        "basis": "Trailing twelve-month EPS of ${:.2f} at its own {}-year P/E of {:.1f}x, {:.1f}x "
                 "and {:.1f}x (25th, 50th and 75th percentile).".format(
                     eps, years, lo_pe, mid_pe, hi_pe),
        "limits": [
            "A fair value from its own past multiple. It assumes the next years look "
            "like the last ones, which is exactly what is in doubt for a company whose "
            "growth or business has changed.",
            "A range to read the price against. It is not a price target, and the "
            "market has often paid outside it for years.",
            "Trailing earnings only. A company about to earn much more or less than it "
            "did will look cheap or dear here when it is not.",
        ],
        "source": pe.get("source"),
    }


# ------------------------------------------------------------ analysts


def analysts_view(view: Dict[str, Any], price: Optional[float]) -> Dict[str, Any]:
    """The firms' rating counts and price targets, or that there are none."""
    out = earnings_mod._analyst(view or {}, price)
    if not out.get("analyst_count") and out.get("target_mean") is None:
        return {"available": False, "reason": "No analyst coverage in the feed for this symbol."}
    out["available"] = True
    out["note"] = ("What the firms that cover it publish, as Yahoo carries it. Not an Optic "
                   "pick, and targets run stale: a mean target far from the price usually "
                   "means the opinions are old, or the market disagrees.")
    out["ratings"] = (out.get("ratings") or [])[:4]
    return out


# ------------------------------------------------------------- dividend


def _years(annual: List[Dict[str, Any]]) -> List[float]:
    return [float(row["total"]) for row in annual if row.get("total") is not None]


def dividend_score(actions: Dict[str, Any], price: Optional[float],
                   trailing_pe: Optional[float], yield_: Optional[float],
                   today: Optional[datetime] = None,
                   quote_type: Optional[str] = "EQUITY") -> Dict[str, Any]:
    """The score out of 100 and its four parts, or why the name has none."""
    today = today or datetime.now(timezone.utc)
    if quote_type and str(quote_type).upper() != "EQUITY":
        return {"available": False,
                "reason": "A fund passes on what its holdings pay, so there are no earnings of its "
                          "own for the dividend to be covered by."}
    payments = actions.get("dividends") or []
    if not actions.get("pays_dividend") or not payments:
        return {"available": False, "reason": "It does not pay a dividend."}
    try:
        last_paid = datetime.fromisoformat(payments[-1]["date"]).replace(tzinfo=timezone.utc)
    except (KeyError, ValueError):
        last_paid = None
    if last_paid and (today - last_paid).days > PAYING_WITHIN_DAYS:
        return {"available": False,
                "reason": "No dividend paid since {}.".format(payments[-1]["date"])}

    annual = _years(actions.get("annual") or [])
    streak = int(actions.get("growth_streak_years") or 0)
    cut_year = actions.get("last_cut_year")
    # Twelve months of payments, as a per-share figure to set against earnings.
    recent = [p for p in payments
              if _days_ago(p.get("date"), today) is not None and _days_ago(p.get("date"), today) <= 365]
    ttm_dps = round(sum(float(p["amount"]) for p in recent), 4) if recent else None
    eps = price / trailing_pe if price and trailing_pe and trailing_pe > 0 else None

    parts: List[Dict[str, Any]] = []

    # Cover: how much of this year's earnings the dividend takes.
    if ttm_dps is not None and eps is not None:
        payout = ttm_dps / eps
        if payout <= 0.40:
            pts, why = 25.0, "A modest share of earnings, with room to keep paying in a bad year."
        elif payout <= 0.60:
            pts, why = 20.0, "A comfortable share of earnings."
        elif payout <= 0.75:
            pts, why = 12.0, "A large share of earnings, with less room for a weak year."
        elif payout <= 1.0:
            pts, why = 5.0, "Nearly all of earnings go out as dividends."
        else:
            pts, why = 0.0, "More is paid out than earned."
        parts.append({"id": "cover", "label": "Earnings cover", "points": pts,
                      "value": "{:.0f}% of earnings paid out".format(payout * 100), "why": why})
    elif eps is None and trailing_pe is None:
        parts.append({"id": "cover", "label": "Earnings cover", "points": 0.0,
                      "value": "no positive earnings", "why": "A dividend paid from a loss is "
                      "paid from cash on hand, which does not last."})
    else:
        parts.append({"id": "cover", "label": "Earnings cover", "points": None,
                      "value": "not available", "why": "No trailing earnings to set it against."})

    # Consistency: years in a row the annual total rose, held down by a recent cut.
    pts = PART_MAX * min(streak, STREAK_FULL_YEARS) / STREAK_FULL_YEARS
    cut_recent = bool(cut_year) and cut_year >= today.year - CUT_WINDOW_YEARS
    if cut_recent:
        pts = min(pts, CUT_CAP)
    parts.append({
        "id": "streak", "label": "Years of increases", "points": round(pts, 1),
        "value": "{} year{} in a row".format(streak, "" if streak == 1 else "s"),
        "why": ("Cut in {}, which holds this down.".format(cut_year) if cut_recent
                else "Counts consecutive complete years the annual total rose.")})

    # Growth: five-year change in the annual total.
    if len(annual) >= 6 and annual[-6] > 0:
        cagr = (annual[-1] / annual[-6]) ** (1 / 5) - 1
        if cagr <= 0:
            pts, why = 0.0, "The annual total has not grown over five years."
        elif cagr < 0.03:
            pts, why = 8.0, "Growing, but slower than inflation has run."
        elif cagr < 0.06:
            pts, why = 16.0, "Growing steadily."
        elif cagr < 0.10:
            pts, why = 22.0, "Growing quickly."
        else:
            pts, why = 25.0, "Growing very quickly."
        parts.append({"id": "growth", "label": "Five-year growth", "points": pts,
                      "value": "{:+.1f}% a year".format(cagr * 100), "why": why})
    else:
        parts.append({"id": "growth", "label": "Five-year growth", "points": None,
                      "value": "under six years of payments", "why": "Too little history to score."})

    # Yield: paid for the price, within reason.
    if yield_ is not None and yield_ > 0:
        if yield_ >= HIGH_YIELD:
            pts, why = 0.0, ("A yield this high is more often a price that has fallen than a "
                             "generous payer.")
        else:
            pts = PART_MAX * min(yield_, YIELD_FULL) / YIELD_FULL
            why = "Full marks from {:.0f}% up to {:.0f}%.".format(YIELD_FULL * 100, HIGH_YIELD * 100)
        parts.append({"id": "yield", "label": "Yield", "points": round(pts, 1),
                      "value": "{:.2f}%".format(yield_ * 100), "why": why})
    else:
        parts.append({"id": "yield", "label": "Yield", "points": None,
                      "value": "not available", "why": "No yield in the quote."})

    scored = [p for p in parts if p["points"] is not None]
    if len(scored) < 2:
        return {"available": False, "reason": "Too little of the payment record to score."}
    total = round(sum(p["points"] for p in scored) / (PART_MAX * len(scored)) * 100.0)
    band = ("strong" if total >= 75 else "solid" if total >= 55
            else "mixed" if total >= 35 else "weak")
    return {
        "available": True,
        "score": int(total), "band": band,
        "parts": parts, "scored_of": len(scored),
        "ttm_dividend": ttm_dps, "yield": _f((yield_ or 0) * 100, 2),
        "method": ("Out of 100 from four parts of 25: how much of earnings the dividend takes, "
                   "years in a row the annual total has risen, its five-year growth, and the "
                   "yield. A part with no data is left out and the rest scaled. It reads the "
                   "payment record and trailing earnings only: it cannot see debt, cash flow "
                   "or whether the board means to keep paying."),
        "source": actions.get("source"),
    }


def _days_ago(date_text: Optional[str], today: datetime) -> Optional[int]:
    try:
        when = datetime.fromisoformat(str(date_text)).replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return (today - when).days


# ---------------------------------------------------------------- entry


def build(provider, ticker: str) -> Dict[str, Any]:
    """The three blocks for one symbol; each fails on its own."""
    sym = (ticker or "").strip().upper()
    quote: Dict[str, Any] = {}
    try:
        quote = provider.quote(sym) or {}
    except Exception as exc:                                   # noqa: BLE001
        log.warning("fair value: no quote for %s: %s", sym, exc)
    price = quote.get("price")

    def attempt(label: str, make):
        try:
            return make()
        except Exception as exc:                               # noqa: BLE001
            log.warning("fair value: %s unavailable for %s: %s", label, sym, exc)
            return {"available": False, "reason": "Could not be worked out right now."}

    pe = attempt("multiples", lambda: pe_history_mod.build(provider, sym, years=10))
    return {
        "ticker": sym,
        "price": price,
        "fair_value": attempt("fair value", lambda: fair_value(pe, price)),
        "analysts": attempt("analysts", lambda: analysts_view(provider.analyst_view(sym), price)),
        "dividend": attempt("dividend", lambda: dividend_score(
            extras_mod.corporate_actions(provider, sym), price,
            quote.get("trailing_pe"), quote.get("dividend_yield"),
            quote_type=quote.get("quote_type"))),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
