"""Does the screen's score actually predict anything?

Every other number in this terminal is a claim. This is the only module that
tests one. It replays the screener's own scoring function over history and
measures what happened next.

**The method.** Pick evaluation dates going back through the sample. At each one,
truncate every symbol's price history to that date — so the score is computed
from information that existed then — and score the universe exactly as the live
screener would. Then measure each name's forward return over several horizons,
and subtract the universe's own mean forward return for that same date. That
subtraction is the point: a momentum score in a rising market will show positive
forward returns whether or not it has any skill, because everything went up.
What matters is whether high scores beat *the other names on the same day*.

**The headline number is the information coefficient** — the Spearman rank
correlation between score and forward excess return, averaged across dates. It
answers the only question worth asking: does a higher score rank a better
outcome? An IC of 0.00 means the score is noise. Real equity signals live around
0.02–0.05; anything above 0.10 on daily-bar momentum should be assumed to be a
bug before it is believed.

**What this cannot fix.** The universe is today's listed names, so anything
delisted, acquired or bankrupt is absent — the sample survived by construction,
and that flatters any long-only result. The overlapping evaluation windows also
mean observations are not independent, so the standard errors here are optimistic.
Both are stated in the output rather than buried, because a backtest that hides
its biases is worse than no backtest.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Sequence

import numpy as np

from . import screen

log = logging.getLogger(__name__)

# Forward horizons in sessions: about a week, a month, a quarter.
HORIZONS = (5, 21, 63)

# Sessions between evaluation dates. Monthly-ish — closer together and the
# windows overlap so heavily that the observations are nearly the same trade
# counted many times.
STEP = 21

# The score needs this much history behind it before it means anything, matching
# the live screener's own gate.
WARMUP = screen.MIN_BARS

# Buckets the score is grouped into for the by-bucket table.
BUCKETS = [(-1e9, -20, "strongly bearish"), (-20, -5, "bearish"),
           (-5, 5, "neutral"), (5, 20, "bullish"), (20, 1e9, "strongly bullish")]


def _num(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if out != out or out in (float("inf"), float("-inf")) else out


def _spearman(xs: Sequence[float], ys: Sequence[float]) -> Optional[float]:
    """Rank correlation, computed here to avoid a scipy dependency."""
    n = len(xs)
    if n < 8:
        return None

    def ranks(vals):
        order = sorted(range(len(vals)), key=lambda i: vals[i])
        out = [0.0] * len(vals)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
                j += 1
            # Average rank across ties, or ties bias the correlation.
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                out[order[k]] = avg
            i = j + 1
        return out

    rx, ry = ranks(list(xs)), ranks(list(ys))
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx)
    dy = sum((b - my) ** 2 for b in ry)
    if dx <= 0 or dy <= 0:
        return None
    return num / (dx * dy) ** 0.5


def _bucket(score: float) -> str:
    for lo, hi, name in BUCKETS:
        if lo <= score < hi:
            return name
    return "neutral"


def _stats(values: List[float]) -> Dict[str, Any]:
    if not values:
        return {"n": 0}
    arr = np.array(values, dtype=float)
    n = len(arr)
    mean = float(arr.mean())
    sd = float(arr.std(ddof=1)) if n > 1 else 0.0
    return {
        "n": n,
        "mean_pct": round(mean, 3),
        "median_pct": round(float(np.median(arr)), 3),
        "hit_rate_pct": round(float((arr > 0).mean() * 100.0), 1),
        "std_pct": round(sd, 3),
        # Standard error, and the 95% band around the mean. Optimistic because
        # the observations overlap; reported anyway so the reader can see how
        # much of the "edge" is inside the noise.
        "stderr_pct": round(sd / (n ** 0.5), 3) if n > 1 else None,
        "ci95_pct": [round(mean - 1.96 * sd / (n ** 0.5), 3),
                     round(mean + 1.96 * sd / (n ** 0.5), 3)] if n > 1 else None,
    }


def run(provider, symbols: Sequence[str], period: str = "2y",
        horizons: Sequence[int] = HORIZONS, step: int = STEP,
        score_fn: Optional[Callable[[Dict[str, Any]], float]] = None) -> Dict[str, Any]:
    """Replay the screen's score over history and measure what happened next."""
    symbols = list(dict.fromkeys(symbols))
    if not symbols:
        return {"available": False, "reason": "No symbols to evaluate."}

    try:
        frames = provider.batch_history(symbols, period=period, interval="1d") or {}
    except Exception as exc:                     # noqa: BLE001
        return {"available": False,
                "reason": "History unavailable: {}: {}".format(type(exc).__name__, exc)}

    usable = {s: f for s, f in frames.items()
              if f is not None and not f.empty and len(f) > WARMUP + max(horizons)}
    if len(usable) < 20:
        return {"available": False,
                "reason": ("Only {} symbols had enough history. A rank correlation "
                           "across fewer than 20 names on a date is noise."
                           .format(len(usable)))}

    max_h = max(horizons)
    # Align on DATES, not integer offsets. Frames come back with different
    # lengths — a recent listing has fewer bars — and taking min() across them
    # collapsed the grid to a single evaluation date whenever one symbol was
    # short. Positions only mean the same thing across symbols if the calendars
    # are the same, and they are not.
    calendar = max((f.index for f in usable.values()), key=len)
    points = [calendar[i] for i in range(WARMUP, len(calendar) - max_h, step)]
    if not points:
        return {"available": False, "reason": "Sample too short for any evaluation date."}

    per_horizon: Dict[int, List[float]] = {h: [] for h in horizons}
    per_bucket: Dict[str, Dict[int, List[float]]] = {
        b[2]: {h: [] for h in horizons} for b in BUCKETS}
    ics: Dict[int, List[float]] = {h: [] for h in horizons}
    scored_rows = 0

    for t in points:
        day_scores: List[float] = []
        day_fwd: Dict[int, List[float]] = {h: [] for h in horizons}
        day_symbols: List[str] = []

        for symbol, frame in usable.items():
            # Where this date sits in THIS symbol's own calendar.
            pos = frame.index.searchsorted(t, side="right")
            if pos < WARMUP or pos + max_h > len(frame):
                continue
            window = frame.iloc[:pos]
            metrics = screen._metrics(symbol, window)
            if not metrics:
                continue
            score = (score_fn(metrics) if score_fn
                     else _num(screen._score(metrics).get("score")))
            if score is None:
                continue
            closes = frame["Close"]
            base = _num(closes.iloc[pos - 1])
            if base is None or base <= 0:
                continue
            fwd = {}
            ok = True
            for h in horizons:
                nxt = _num(closes.iloc[pos - 1 + h])
                if nxt is None:
                    ok = False
                    break
                fwd[h] = (nxt / base - 1.0) * 100.0
            if not ok:
                continue
            day_scores.append(score)
            day_symbols.append(symbol)
            for h in horizons:
                day_fwd[h].append(fwd[h])

        if len(day_scores) < 20:
            continue
        scored_rows += len(day_scores)

        for h in horizons:
            # Excess against the equal-weight universe on this same date. Without
            # this, a momentum score in a bull market looks skilful when it has
            # only been long a rising market.
            mean = float(np.mean(day_fwd[h]))
            excess = [v - mean for v in day_fwd[h]]
            per_horizon[h].extend(excess)
            ic = _spearman(day_scores, excess)
            if ic is not None:
                ics[h].append(ic)
            for score, ex in zip(day_scores, excess):
                per_bucket[_bucket(score)][h].append(ex)

    if not scored_rows:
        return {"available": False, "reason": "No evaluation date produced enough scores."}

    horizon_out = []
    for h in horizons:
        series = ics[h]
        ic_mean = float(np.mean(series)) if series else None
        ic_sd = float(np.std(series, ddof=1)) if len(series) > 1 else None
        horizon_out.append({
            "horizon_sessions": h,
            "information_coefficient": round(ic_mean, 4) if ic_mean is not None else None,
            # IC divided by its own volatility across dates — how consistent the
            # relationship is, not just how big it was on average.
            "ic_stability": (round(ic_mean / ic_sd, 2)
                             if ic_mean is not None and ic_sd else None),
            "ic_dates": len(series),
            "ic_positive_share_pct": (round(sum(1 for x in series if x > 0) / len(series) * 100.0, 1)
                                      if series else None),
            "excess": _stats(per_horizon[h]),
            "buckets": [{"bucket": b[2], **_stats(per_bucket[b[2]][h])} for b in BUCKETS],
        })

    return {
        "available": True,
        "universe_size": len(usable),
        "evaluation_dates": len(points),
        "observations": scored_rows,
        "period": period,
        "step_sessions": step,
        "horizons": horizon_out,
        "interpretation": (
            "The information coefficient is the rank correlation between the score "
            "and what the stock did next, relative to the rest of the universe on "
            "the same day. Zero means the score carries no information. Real "
            "equity signals sit around 0.02-0.05; a reading above 0.10 on daily "
            "price-and-volume momentum should be treated as a bug until proven "
            "otherwise."
        ),
        "biases": [
            ("Survivorship. The universe is today's listed names, so anything "
             "delisted, acquired or bankrupt over the sample is absent. The sample "
             "survived by construction, which flatters any long-only result."),
            ("Overlapping windows. Evaluation dates are {} sessions apart while the "
             "longest forward window is {}, so observations share periods and are "
             "not independent. The standard errors below are therefore optimistic . "
             "The true intervals are wider.".format(step, max(horizons))),
            ("No costs. Returns are close-to-close with no spread, commission or "
             "slippage. A signal with a small edge can be entirely consumed by "
             "them."),
            ("One scoring function. This measures the screen's trend-and-momentum "
             "score, not the terminal's per-ticker composite, which uses options "
             "and news data that free history cannot reconstruct point-in-time."),
        ],
    }


def with_controls(provider, symbols: Sequence[str], period: str = "2y",
                  seed: int = 99) -> Dict[str, Any]:
    """The screen's score measured against two controls, always together.

    An information coefficient on its own is uninterpretable. Two controls make
    it mean something:

    **Random.** A score drawn from noise. If the harness were manufacturing
    correlation — through overlapping windows, a look-ahead slip, an alignment
    bug — this would come back positive. It must land near zero.

    **Single factor.** The stock's own three-month return, with no weighting
    scheme at all. This is the honest benchmark for a hand-weighted composite: if
    eight factors and a set of judged weights cannot beat one raw number, the
    weights are not adding information, and saying so is more useful than
    publishing the composite's IC alone.
    """
    import random as _random

    live = run(provider, symbols, period=period)
    if not live.get("available"):
        return live

    rnd = _random.Random(seed)
    null = run(provider, symbols, period=period, score_fn=lambda m: rnd.random())
    single = run(provider, symbols, period=period,
                 score_fn=lambda m: _num(m.get("roc60")) or 0.0)

    def ic_map(result):
        if not result.get("available"):
            return {}
        return {h["horizon_sessions"]: h["information_coefficient"]
                for h in result["horizons"]}

    live_ic, null_ic, single_ic = ic_map(live), ic_map(null), ic_map(single)
    comparison = []
    for h in sorted(live_ic):
        l, n, sg = live_ic.get(h), null_ic.get(h), single_ic.get(h)
        beats_single = (l is not None and sg is not None and l > sg)
        comparison.append({
            "horizon_sessions": h,
            "composite_ic": l,
            "random_ic": n,
            "single_factor_ic": sg,
            "beats_random": (l is not None and n is not None and l > abs(n)),
            "beats_single_factor": beats_single,
        })

    beaten = [c for c in comparison if c["single_factor_ic"] is not None
              and not c["beats_single_factor"]]
    verdict = (
        "The composite does not beat a single raw momentum number at {} of {} "
        "horizons. Eight weighted factors are not adding information over the "
        "three-month return on its own, which means the weights are decoration "
        "rather than signal.".format(len(beaten), len(comparison))
        if beaten else
        "The composite beats both controls at every horizon tested."
    )

    return {
        **live,
        "controls": {"random": null_ic, "single_factor": single_ic},
        "comparison": comparison,
        "verdict": verdict,
        "control_note": (
            "Random is a score drawn from noise. It must land near zero, or the "
            "harness itself is manufacturing correlation. Single factor is the "
            "stock's own three-month return with no weighting scheme, which is the "
            "benchmark a hand-weighted composite has to clear to justify its "
            "complexity."
        ),
    }
