"""Trailing price/earnings as a time series, plus revenue growth alongside price.

The point of putting these two together is that they answer opposite halves of
one question. Revenue growth is what the business did; the multiple is what the
market was willing to pay for it. A revenue line rising while the multiple
compresses is a completely different situation from both rising together, and
neither series says that on its own.

**The one thing this gets right that most versions of this chart do not: earnings
become public on the filing date, not on the day the quarter ended.** A trailing
P/E series built by attaching a quarter's earnings to the quarter's end date is
using a number that nobody had for another three to six weeks. On a name that
gaps on results, that shifts the entire multiple history left by a month and makes
the P/E look like it fell *before* the news that caused it. Every point here uses
`available_from`· the SEC filing date — so the series only ever knows what was
public at the time.
"""

from __future__ import annotations

import bisect
import datetime as dt
import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from . import sec_facts

log = logging.getLogger(__name__)

# Weekly sampling. A daily P/E series is 3,000 points of which 4 in 5 carry no
# new information — the denominator only changes when a filing lands — and it is
# the price axis of the chart that wants resolution, not this pane.
RESAMPLE = "W-FRI"

# A trailing P/E is meaningless when trailing earnings are negative: the ratio
# goes hugely negative and then swings through infinity as EPS crosses zero.
# Those points are dropped and counted, never plotted as a number.
MIN_TTM_EPS = 0.01

# Bands drawn on the pane.
PERCENTILES = (10, 25, 50, 75, 90)

# Bands are computed over this many weeks, not the whole series.
#
# Two reasons, and the second is the important one. A "cheap against its own
# history" read is a decision input, and an eighteen-year window on a company that
# changed shape answers a question nobody asked — Amazon's full-history 90th
# percentile P/E is 670, which is true and useless. And the deep tail is where the
# XBRL restatement basis is least reliable: periods no later filing ever restated
# keep their original share count, so the further back the series runs the more
# scope there is for a mis-scaled point to distort a percentile.
BAND_WEEKS = 260

# How far today's computed multiple may sit from the provider's own trailing P/E
# before the series is flagged. This is the independent check on the whole
# earnings-assembly and split-restatement chain: if the two agree at the latest
# point, the plumbing is sound there.
ANCHOR_TOLERANCE_PCT = 10.0


def _as_of_lookup(rows: List[Dict[str, Any]]) -> List[tuple]:
    """(filing date, value, period end) triples, ordered so an as-of scan works.

    Two dates matter per figure and confusing them is the trap. `available_from`
    is when it became public and gates what may be used; `period_end` is what it
    measures and decides which figure is freshest.

    The list is sorted by filing date, then walked to keep a running maximum of
    period end — so at any point the entry carries the newest period that was
    public by then. A plain "latest filed" lookup instead returns whichever period
    was most recently RESTATED, and XBRL comparative columns mean that is usually
    a figure one to two years old. That single mistake put Microsoft's mid-2023
    multiple on earnings from March 2021, inflating its five-year median P/E to 42
    against a true figure near 30, and the same error scaled NVIDIA's to 288.
    """
    staged = []
    for row in rows:
        try:
            filed = dt.date.fromisoformat(row["available_from"])
        except (KeyError, TypeError, ValueError):
            continue
        staged.append((filed, row["period_end"], float(row["value"])))
    staged.sort(key=lambda r: (r[0], r[1]))

    pairs = []
    best_period = ""
    best = None
    for filed, period, value in staged:
        if period >= best_period:
            best_period, best = period, (value, period)
        if best is not None:
            pairs.append((filed, best[0], best[1]))
    return pairs


def _value_as_of(pairs: List[tuple], when: dt.date) -> Optional[tuple]:
    """The freshest figure that was public on `when`."""
    if not pairs:
        return None
    i = bisect.bisect_right([p[0] for p in pairs], when) - 1
    if i < 0:
        return None
    filed, value, period = pairs[i]
    return (filed, value, period)


def _split_factors(splits: List[Dict[str, Any]]) -> List[tuple]:
    """(effective date, cumulative factor to apply to earlier EPS).

    SEC reports earnings per share as they stood at the time; the price history
    here is split-adjusted. Any EPS from before a split has to be divided by the
    splits that happened after it, or the two sides of the ratio are counting
    different shares. Unfixed this gave Apple a P/E near 1 in 2008 and NVIDIA a
    ten-year median of 4.3 — NVIDIA is 40-for-one split since 2021 and Apple
    28-for-one since 2014.
    """
    out = []
    for row in splits or []:
        try:
            when = dt.date.fromisoformat(row["date"])
            ratio = float(row["ratio"])
        except (KeyError, TypeError, ValueError):
            continue
        if ratio > 0:
            out.append((when, ratio))
    out.sort(key=lambda r: r[0])
    return out


def _cumulative_after(factors: List[tuple], when: dt.date) -> float:
    """Product of every split ratio effective after `when`."""
    total = 1.0
    for eff, ratio in factors:
        if eff > when:
            total *= ratio
    return total


def build(provider, ticker: str, years: int = 10) -> Dict[str, Any]:
    """Weekly trailing P/E and quarterly revenue growth for one name."""
    sym = (ticker or "").upper().strip()
    facts = sec_facts.history(sym)
    if not facts.get("available"):
        return {"available": False, "reason": facts.get("reason", "No filing history.")}

    if len(facts.get("eps_quarters") or []) < 8:
        return {"available": False,
                "reason": "Only {} quarters of filed earnings, which is not enough "
                          "for a trailing multiple history.".format(
                              len(facts.get("eps_quarters") or [])),
                "notes": facts.get("notes") or []}

    try:
        daily = provider.history(sym, period="{}y".format(max(2, years)), interval="1d")
    except Exception as exc:                                   # noqa: BLE001
        return {"available": False, "reason": "No price history: {}".format(str(exc)[:100])}
    if daily is None or daily.empty:
        return {"available": False, "reason": "No price history for {}.".format(sym)}

    weekly = daily["Close"].astype(float).resample(RESAMPLE).last().dropna()

    try:
        factors = _split_factors(provider.splits(sym))
    except Exception as exc:                                   # noqa: BLE001
        log.warning("pe_history: splits unavailable for %s: %s", sym, exc)
        factors = []
    # Restate every trailing-EPS point onto today's share count before it meets a
    # split-adjusted price.
    # Adjust each QUARTER onto today's share basis, then sum into a trailing year.
    #
    # Order matters and getting it wrong is subtle. Summing first and adjusting the
    # total by one factor means a trailing window that spans a split has added
    # together quarters counted in different shares — NVIDIA's four-quarter window
    # across June 2024 mixed pre- and post-ten-for-one figures, and no single
    # divisor can fix a sum like that. It left a five-year median P/E of 117
    # against a true figure near 60.
    #
    # The factor is keyed on each figure's FILING date, not its period end. XBRL
    # values for a past quarter usually come from the comparative column of a later
    # filing, and a comparative column has already been restated onto the share
    # basis in force at that filing. So a value needs adjusting only for splits
    # after it was filed. Keying on the period end double-adjusts those; keying on
    # nothing at all under-adjusts the old periods no later filing ever restated,
    # which is what gave Apple a P/E of 1 in 2008.
    eps_q = facts.get("eps_quarters") or []
    adjusted_quarters = []
    for row in eps_q:
        try:
            filed = dt.date.fromisoformat(row["available_from"])
        except (KeyError, TypeError, ValueError):
            continue
        factor = _cumulative_after(factors, filed)
        adjusted_quarters.append({**row, "value": float(row["value"]) / factor,
                                  "split_factor": factor})
    eps_ttm = sec_facts._trailing(adjusted_quarters)      # noqa: SLF001
    if len(eps_ttm) < 4:
        return {"available": False,
                "reason": "Only {} trailing-twelve-month earnings points survived "
                          "the split restatement.".format(len(eps_ttm)),
                "notes": facts.get("notes") or []}
    pairs = _as_of_lookup(eps_ttm)

    points: List[Dict[str, Any]] = []
    negative = 0
    for stamp, price in weekly.items():
        when = stamp.date() if hasattr(stamp, "date") else stamp
        hit = _value_as_of(pairs, when)
        if hit is None:
            continue                       # before the first filing we can see
        _filed, ttm_eps, period = hit
        if ttm_eps < MIN_TTM_EPS:
            # Loss-making trailing year. A P/E here is not a small number, it is
            # not a number — so it is counted and omitted rather than drawn.
            negative += 1
            continue
        points.append({
            "date": str(when),
            "pe": round(float(price) / ttm_eps, 2),
            "price": round(float(price), 2),
            "ttm_eps": round(ttm_eps, 4),
            "eps_period": period,
        })

    if len(points) < 26:
        return {"available": False,
                "reason": "Only {} weeks of overlapping price and earnings "
                          "history.".format(len(points)),
                "notes": facts.get("notes") or []}

    series = np.array([p["pe"] for p in points], dtype=float)
    band_slice = series[-BAND_WEEKS:] if len(series) > BAND_WEEKS else series
    bands = {str(q): round(float(np.percentile(band_slice, q)), 1) for q in PERCENTILES}
    current = points[-1]["pe"]
    rank = float((band_slice <= current).mean() * 100.0)

    # Independent check on the earnings assembly and the split restatement. The
    # provider computes its trailing P/E from a different source entirely, so
    # agreement at the latest point is real corroboration rather than a tautology.
    anchor: Dict[str, Any] = {"available": False}
    try:
        quote = provider.quote(sym) or {}
        theirs = quote.get("trailing_pe")
        if theirs and float(theirs) > 0:
            diff = (current / float(theirs) - 1.0) * 100.0
            anchor = {
                "available": True,
                "ours": current,
                "provider": round(float(theirs), 2),
                "diff_pct": round(diff, 1),
                "agrees": abs(diff) <= ANCHOR_TOLERANCE_PCT,
            }
    except Exception as exc:                                    # noqa: BLE001
        log.info("pe_history: anchor check failed for %s: %s", sym, exc)

    growth = facts.get("revenue_yoy") or []
    # Trim to the price window so the labels line up with the chart beneath them.
    first_date = points[0]["date"]
    growth = [g for g in growth if g["period_end"] >= first_date]

    return {
        "available": True,
        "ticker": sym,
        "pe_series": points,
        "pe_current": current,
        "pe_percentile": round(rank, 0),
        "pe_bands": bands,
        "pe_median": bands["50"],
        "band_weeks": min(len(series), BAND_WEEKS),
        "anchor": anchor,
        "weeks": len(points),
        "loss_weeks": negative,
        "revenue_growth": [
            {"period_end": g["period_end"],
             "label": _quarter_label(g["period_end"]),
             "growth_pct": g["growth_pct"],
             "revenue": g["value"],
             "available_from": g["available_from"]}
            for g in growth
        ],
        "revenue_ttm": facts.get("revenue_ttm") or [],
        "eps_quarters": facts.get("eps_quarters") or [],
        "counts": facts.get("counts") or {},
        "span": facts.get("span") or {},
        "short_history": facts.get("short_history", False),
        "splits_applied": [{"date": str(d), "ratio": r} for d, r in factors],
        "notes": facts.get("notes") or [],
        "source": facts.get("source"),
        "cache_age_days": facts.get("cache_age_days"),
        "method": (
            "Price divided by trailing-twelve-month diluted earnings, sampled "
            "weekly. Earnings are attached to the date the filing became public, "
            "not the date the quarter ended. A multiple history built the usual "
            "way is shifted a month early and appears to move before the results "
            "that moved it. Earnings from before a stock split are restated onto "
            "today\u2019s share count first: filings report the share count of "
            "the day, prices here are split-adjusted, and dividing one by the "
            "other unfixed put Apple on a P/E of 1 in 2008. The restatement is "
            "keyed to each figure\u2019s filing date rather than its period, "
            "because a comparative column in a later filing has already been "
            "restated once. Weeks where the trailing year was loss-making are "
            "omitted rather than plotted, because a P/E on negative earnings is "
            "not a small number, it is not a number{loss}. Percentile bands are "
            "over this name's own history in the window, so \\u201ccheap\\u201d "
            "means cheap against itself and says nothing about its sector."
        ).format(loss=(" — {} such weeks here".format(negative) if negative else "")),
    }


def _quarter_label(period_end: str) -> str:
    """Calendar-quarter label. Fiscal quarters differ from calendar ones for many
    filers, so this is labelled by the quarter the period ENDED in and nothing
    pretends to know the company's fiscal numbering."""
    try:
        d = dt.date.fromisoformat(period_end)
    except (TypeError, ValueError):
        return period_end
    return "Q{}'{}".format((d.month - 1) // 3 + 1, str(d.year)[2:])
