"""Does the calendar itself carry information for this ticker?

Seasonality slices returns by *position in the year* rather than by anything the
price did: what happens in each month, on each weekday, around the turn of the
month. The claim under test is that the date is informative.

Most tools that show this draw a bar chart of average returns and stop, which is
where the whole thing goes wrong. Fifteen years of history gives fifteen
observations per calendar month against a monthly standard deviation around 7%,
and at that ratio a three-point spread between the best and worst month is what
noise looks like. A chart of those means, drawn without a sample size, reads as a
finding.

So every figure here ships with the things that decide whether to believe it:

  * **n**, on every row. No sample size, no claim.
  * **Excess over the benchmark** across the same window, so "December is strong"
    cannot just be "the market went up in December".
  * **Hit rate and dispersion**, because a mean of +3% from fourteen flat years
    and one enormous one is a different animal from +3% fourteen times.
  * **The drop-the-best-period check** — the mean recomputed with the single
    best occurrence removed. It is the cheapest test there is for "this is one
    outlier wearing a trend coat".
  * **A significance verdict corrected for multiple comparisons.** Testing twelve
    months means twelve chances to clear p < 0.05, and roughly one will by luck
    alone. The threshold reported is Bonferroni-corrected, and the honest result
    for most tickers is that nothing clears it.

The verdict wording is deliberately flat. "Noise" is the expected outcome and is
printed as such, because a seasonality panel that always finds something is a
seasonality panel that is not measuring anything.

**What this cannot tell you.** A calendar effect is not a mechanism. Where a
month coincides with the company's usual reporting month the effect is most
likely the earnings reaction, not the season, and that is flagged rather than
left for the reader to spot. Fifteen years is also a single market regime for
many names — a stock that listed in 2010 has never seen a sustained bear market
in this sample.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from scipy import stats

log = logging.getLogger(__name__)

BENCHMARK = "SPY"
HISTORY = "15y"

# Below this, a bucket is reported but never given a verdict — the arithmetic
# still runs on four observations and means nothing.
MIN_SAMPLE = 8

# The turn-of-month window: the last trading day of a month plus the first three
# of the next. Fixed in advance rather than fitted, for the same reason the paper
# ledger's 2:1 target is fixed — a window chosen because it produced the best
# number is not a finding.
TOM_BEFORE = 1
TOM_AFTER = 3

ALPHA = 0.05


def _f(value: Any, digits: int = 2) -> Optional[float]:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(out):
        return None
    return round(out, digits)


def _verdict(p: Optional[float], threshold: float, n: int) -> str:
    """Three words the reader can act on, and no more confidence than earned."""
    if n < MIN_SAMPLE or p is None:
        return "too few"
    if p < threshold:
        return "significant"
    if p < ALPHA:
        return "unproven"          # would pass alone; does not survive the family
    return "noise"


def _bucket_stats(values: pd.Series, baseline: float,
                  threshold: float, digits: int = 2) -> Dict[str, Any]:
    """One calendar bucket: what happened, how often, and whether to believe it.

    `baseline` is the ticker's own mean over every period in the sample, not
    zero. The question is whether *this* month differs from how the stock
    normally behaves, and testing against zero would instead rediscover that the
    stock went up — which is true of most stocks and is not seasonality.
    """
    vals = values.dropna()
    n = len(vals)
    if not n:
        return {"n": 0, "verdict": "too few"}

    # Drop the single best occurrence. If the effect is one year in a costume,
    # this is where it comes off.
    ex_best = vals.drop(vals.idxmax()) if n > 1 else vals

    p: Optional[float] = None
    if n >= 2 and float(vals.std()) > 0:
        try:
            p = float(stats.ttest_1samp(vals, baseline).pvalue)
        except Exception:                                          # noqa: BLE001
            p = None

    return {
        "n": n,
        # `digits` exists because daily and monthly returns live two orders of
        # magnitude apart. Rounding a weekday mean of 0.034%/day to two places
        # gives 0.03 and throws away most of the signal being reported.
        "mean": _f(vals.mean(), digits),
        "median": _f(vals.median(), digits),
        "hit_rate": _f((vals > 0).mean() * 100, 1),
        "sd": _f(vals.std(), digits),
        "best": _f(vals.max(), digits),
        "worst": _f(vals.min(), digits),
        "mean_ex_best": _f(ex_best.mean(), digits),
        "vs_baseline": _f(vals.mean() - baseline, digits),
        "p": None if p is None else round(p, 4),
        "verdict": _verdict(p, threshold, n),
    }


def _monthly(px: pd.Series, bench: pd.Series) -> Dict[str, Any]:
    """Calendar-month returns, and the same net of the benchmark."""
    m = px.resample("ME").last().pct_change().dropna() * 100.0
    b = bench.resample("ME").last().pct_change().dropna() * 100.0
    joined = pd.concat({"t": m, "b": b}, axis=1).dropna()
    if joined.empty:
        return {"rows": [], "baseline": None, "threshold": None}

    excess = joined["t"] - joined["b"]
    base_raw, base_ex = float(joined["t"].mean()), float(excess.mean())
    threshold = ALPHA / 12.0

    rows = []
    for month in range(1, 13):
        mask = joined.index.month == month
        raw = _bucket_stats(joined["t"][mask], base_raw, threshold)
        ex = _bucket_stats(excess[mask], base_ex, threshold)
        rows.append({
            "key": month,
            "label": pd.Timestamp(2000, month, 1).strftime("%B"),
            "short": pd.Timestamp(2000, month, 1).strftime("%b"),
            "raw": raw,
            "excess": ex,
            # The years behind the row, so a reader can see the spread rather
            # than trust the mean.
            "years": [{"year": int(d.year), "pct": _f(v)}
                      for d, v in joined["t"][mask].items()],
        })
    return {
        "rows": rows,
        "baseline": _f(base_raw),
        "baseline_excess": _f(base_ex),
        "threshold": round(threshold, 4),
        "tests": 12,
        "periods": int(len(joined)),
    }


def _weekday(px: pd.Series, bench: pd.Series) -> Dict[str, Any]:
    """Day-of-week returns.

    Worth more than the monthly grid on sample size alone: fifteen years gives
    about 780 observations per weekday against fifteen per calendar month, so a
    real effect has somewhere to show up.
    """
    d = px.pct_change().dropna() * 100.0
    b = bench.pct_change().dropna() * 100.0
    joined = pd.concat({"t": d, "b": b}, axis=1).dropna()
    if joined.empty:
        return {"rows": [], "baseline": None, "threshold": None}

    excess = joined["t"] - joined["b"]
    base_raw, base_ex = float(joined["t"].mean()), float(excess.mean())
    threshold = ALPHA / 5.0
    names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

    rows = []
    for i, name in enumerate(names):
        mask = joined.index.dayofweek == i
        rows.append({
            "key": i, "label": name, "short": name[:3],
            "raw": _bucket_stats(joined["t"][mask], base_raw, threshold, 3),
            "excess": _bucket_stats(excess[mask], base_ex, threshold, 3),
        })
    return {
        "rows": rows,
        "baseline": _f(base_raw, 3),
        "baseline_excess": _f(base_ex, 3),
        "threshold": round(threshold, 4),
        "tests": 5,
        "periods": int(len(joined)),
    }


def _turn_of_month(px: pd.Series, bench: pd.Series) -> Dict[str, Any]:
    """The turn-of-month window against the rest of the month.

    One comparison, so there is no multiple-comparison penalty to pay and the
    threshold is the plain 0.05.
    """
    d = px.pct_change().dropna() * 100.0
    b = bench.pct_change().dropna() * 100.0
    joined = pd.concat({"t": d, "b": b}, axis=1).dropna()
    if joined.empty:
        return {"rows": [], "threshold": None}

    # Trading-day index within each month, counted from both ends so the window
    # follows the actual calendar rather than assuming a 21-day month.
    idx = pd.Series(np.arange(len(joined)), index=joined.index)
    from_start = idx.groupby([joined.index.year, joined.index.month]).rank(method="first")
    from_end = idx.groupby([joined.index.year, joined.index.month]).rank(
        method="first", ascending=False)
    in_window = (from_start <= TOM_AFTER) | (from_end <= TOM_BEFORE)

    excess = joined["t"] - joined["b"]
    base_ex = float(excess.mean())
    rows = []
    for label, mask in (("Turn of month", in_window), ("Rest of the month", ~in_window)):
        rows.append({
            "label": label,
            "raw": _bucket_stats(joined["t"][mask], float(joined["t"].mean()), ALPHA, 3),
            "excess": _bucket_stats(excess[mask], base_ex, ALPHA, 3),
        })

    # The comparison that matters is window against remainder, not either
    # against the overall mean — the two halves make up that mean between them.
    a, c = excess[in_window], excess[~in_window]
    p = None
    if len(a) > 1 and len(c) > 1:
        try:
            p = float(stats.ttest_ind(a, c, equal_var=False).pvalue)
        except Exception:                                          # noqa: BLE001
            p = None
    return {
        "rows": rows,
        "window": {"before": TOM_BEFORE, "after": TOM_AFTER},
        "gap": _f(float(a.mean() - c.mean()), 3) if len(a) and len(c) else None,
        "p": None if p is None else round(p, 4),
        "threshold": ALPHA,
        "tests": 1,
        "verdict": _verdict(p, ALPHA, min(len(a), len(c))),
    }


def _reporting_months(ticker: str) -> List[int]:
    """Calendar months this company usually files results in.

    Read from the SEC filing dates already cached for the P/E and revenue
    panels, so it costs nothing extra. The point is to stop a reader crediting
    the calendar for what is really the earnings reaction: for AAPL the July
    strength is the fiscal-Q3 print, and saying so is more useful than the bar.
    """
    try:
        from . import sec_facts
        facts = sec_facts.history(ticker)
    except Exception:                                              # noqa: BLE001
        return []
    if not facts or not facts.get("available"):
        return []
    months: Dict[int, int] = {}
    for row in (facts.get("revenue_quarters") or []):
        # `available_from` is publication, which is the date the market could
        # react to — the period the figures describe ended months earlier and is
        # not when the stock moved.
        filed = row.get("available_from")
        if not filed or len(str(filed)) < 7:
            continue
        try:
            month = int(str(filed)[5:7])
        except ValueError:
            continue
        if 1 <= month <= 12:
            months[month] = months.get(month, 0) + 1
    if not months:
        return []
    # Measured against the busiest month, not against the total.
    #
    # A share of the total was the first attempt and it was wrong: a quarterly
    # filer spreads 72 filings over eight months, because a results date near a
    # month boundary lands in January one year and February the next. A fifth of
    # the total set the bar at 14, which admitted Apple's January and July and
    # threw out its April (10) and October (13) — two of its four actual
    # reporting seasons. A quarter of the busiest month keeps the whole season
    # and still rejects the stray amendment.
    floor = max(1, int(max(months.values()) * 0.25))
    return sorted(m for m, n in months.items() if n >= floor)


def build(provider, ticker: str) -> Dict[str, Any]:
    """The seasonality payload for one ticker."""
    df = provider.history(ticker, period=HISTORY, interval="1d")
    if df is None or df.empty or len(df) < 400:
        return {"error": "not enough price history for a seasonality read",
                "ticker": ticker}
    bench_df = provider.history(BENCHMARK, period=HISTORY, interval="1d")
    if bench_df is None or bench_df.empty:
        return {"error": "benchmark history unavailable", "ticker": ticker}

    px = df["Close"].astype(float).dropna()
    bench = bench_df["Close"].astype(float).dropna()
    # Both series stripped of timezone so a DST boundary cannot misalign the
    # join and quietly drop a day at each end.
    px.index = pd.to_datetime(px.index).tz_localize(None)
    bench.index = pd.to_datetime(bench.index).tz_localize(None)

    monthly = _monthly(px, bench)
    weekday = _weekday(px, bench)
    tom = _turn_of_month(px, bench)
    reporting = _reporting_months(ticker)

    for row in monthly.get("rows", []):
        row["is_reporting_month"] = row["key"] in reporting

    # How many verdicts across the whole panel actually cleared their corrected
    # threshold. Usually zero, and the panel says so at the top rather than
    # leaving the reader to add it up from the colour of the rows.
    found = sum(
        1 for section in (monthly, weekday)
        for row in section.get("rows", [])
        if (row.get("excess") or {}).get("verdict") == "significant"
    ) + (1 if tom.get("verdict") == "significant" else 0)

    return {
        "ticker": ticker,
        "benchmark": BENCHMARK,
        "history": HISTORY,
        "start": str(px.index[0].date()),
        "end": str(px.index[-1].date()),
        "years": _f(len(px) / 252.0, 1),
        "monthly": monthly,
        "weekday": weekday,
        "turn_of_month": tom,
        "reporting_months": reporting,
        "significant_count": found,
    }
