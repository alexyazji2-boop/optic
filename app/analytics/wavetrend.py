"""WaveTrend: LazyBear's momentum oscillator, its crosses and divergences, and what followed them.

LazyBear's WaveTrend is the oscillator underneath Market Cipher B and VuManChu's
Cipher B; everywhere a reader sees it, it is called WaveTrend. It has one agreed
definition, which is this terminal's rule for an indicator (indicators.py):

    ap  = (high + low + close) / 3
    esa = EMA(ap, channel_len)
    d   = EMA(|ap - esa|, channel_len)
    ci  = (ap - esa) / (0.015 * d)
    wt1 = EMA(ci, avg_len)
    wt2 = SMA(wt1, ma_len)

`ci` is the commodity channel index built on the typical price with EMAs where
CCI has simple means, and 0.015 is Lambert's constant, which puts most readings
inside plus or minus 100. WT1 smooths it, WT2 is a short average of WT1, and the
two cross the way a MACD line and its signal do.

Every average is the codebase's own (technicals.ema and sma): adjust=False, an
EMA seeded with its first value, and null until it has `length` values. Chained,
that leaves WT1 null for its first 2 * channel_len + avg_len - 3 bars (27 at the
defaults) and WT2 for ma_len - 1 more (29). A flat stretch has no deviation to
scale by (d == 0), so it has no reading: null, never a division by zero.

Nothing is reported before the close that makes it known:

* A cross is WT1 closing above WT2 after a close at or below it (bullish), or
  the reverse (bearish), known at that close. It is strong when WT2 is at or
  beyond the first level on that bar: at or below the first oversold level for a
  bullish cross, at or above the first overbought level for a bearish one. That
  is where Cipher B draws its large dots.
* A pivot high on WT2 is a bar higher than each of the `lookback` bars either
  side of it, so it is known `lookback` bars after it printed; a pivot low
  mirrors it. A divergence pairs a
  pivot with the previous one on the same side of zero, as VuManChu's script
  does: a higher high in price (the bars' highs) with a lower high in WT2, both
  above zero, is bearish; a lower low in price (the lows) with a higher low in
  WT2, both below zero, is bullish. It is known when its second pivot is.

What followed them (`evidence`) is measured the way the pattern base rates are
(pattern_stats.py), on the bars the oscillator was computed on: entry at the
close of the bar where the signal became known, and the change in the close 5,
10 and 20 bars later, against every bar of the same window, which is what an
entry at random averages to. Where the signal's mean falls among 500 random
draws of as many bars from that window, with the Backtest widget's seed
(backtest.py), says whether the gap is larger than luck gives at that sample
size. Under 20 signals they are counted and not measured. The windows overlap,
so no t-statistic is given. Nothing here says the signals work; the numbers are
reported whatever they say.
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from .backtest import RANDOM_RUNS, SEED
from .indicators import _f, _series
from .technicals import ema, sma

CHANNEL_LEN, AVG_LEN, MA_LEN = 9, 12, 3
OVERBOUGHT = (53.0, 60.0)
OVERSOLD = (-53.0, -60.0)
PIVOT_LOOKBACK = 5
HORIZONS = (5, 10, 20)
# pattern_stats' floor: under it a hit rate is noise dressed as a number
MIN_SAMPLE = 20
# d under a billionth of the price is the float noise an average of a constant leaves behind, not a deviation
FLAT = 1e-9
# the daily and weekly periods the feed serves; anything else would be a new cache entry for nothing
PERIODS = frozenset({"1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"})
SIGNALS = (
    ("strong_bullish_cross", "Strong bullish crosses", "up"),
    ("strong_bearish_cross", "Strong bearish crosses", "down"),
    ("bullish_divergence", "Bullish divergences", "up"),
    ("bearish_divergence", "Bearish divergences", "down"),
)


def warmup(channel_len: int = CHANNEL_LEN, avg_len: int = AVG_LEN,
           ma_len: int = MA_LEN) -> Dict[str, int]:
    """How many bars each line is null for: each average in the chain waits for `length` values."""
    wt1 = 2 * (channel_len - 1) + (avg_len - 1)
    return {"wt1": wt1, "wt2": wt1 + ma_len - 1}


def series(df: pd.DataFrame, channel_len: int = CHANNEL_LEN, avg_len: int = AVG_LEN,
           ma_len: int = MA_LEN) -> Dict[str, pd.Series]:
    """WT1, WT2 and WT1 - WT2 over `df`, newest bar last, NaN where there is no reading."""
    ap = (df["High"].astype(float) + df["Low"].astype(float) + df["Close"].astype(float)) / 3.0
    esa = ema(ap, channel_len)
    d = ema((ap - esa).abs(), channel_len)
    d = d.where(d > FLAT * ap.abs())
    ci = ((ap - esa) / (0.015 * d)).replace([np.inf, -np.inf], np.nan)
    wt1 = ema(ci, avg_len)
    wt2 = sma(wt1, ma_len)
    return {"wt1": wt1, "wt2": wt2, "hist": wt1 - wt2}


def crosses(wt1: pd.Series, wt2: pd.Series, overbought: float = OVERBOUGHT[0],
            oversold: float = OVERSOLD[0]) -> List[Dict[str, Any]]:
    """Each bar whose close took WT1 through WT2, strong when WT2 is at or beyond the first level there.

    The side WT1 is on is carried through bars where the two are equal, so meeting WT2 and turning back is not a
    cross, and meeting it and going on through is one, on the bar it came out the other side. A bar with no
    reading forgets the side: a change across a gap happened at no bar anyone saw.
    """
    a, b = wt1.to_numpy(dtype=float), wt2.to_numpy(dtype=float)
    out: List[Dict[str, Any]] = []
    side = 0
    for i, gap in enumerate((a - b).tolist()):
        if gap != gap:
            side = 0
            continue
        now = (gap > 0) - (gap < 0)
        if now == 0:
            continue
        if side and now != side:
            bull = now > 0
            out.append({"i": i, "type": "bullish" if bull else "bearish",
                        "strong": bool(b[i] <= oversold) if bull else bool(b[i] >= overbought)})
        side = now
    return out


def pivots(values: Sequence[float], lookback: int, high: bool = True) -> List[int]:
    """The pivot highs of `values` (lows with `high=False`): higher than each of the `lookback` bars either side.
    Strictly, so the corner where a slope meets a flat stretch is not one (nor is a flat top, which a reading
    carried to fifteen figures does not have). Only a bar with `lookback` bars after it can be one, which is what
    makes a pivot known that many bars late and never sooner."""
    v = np.asarray(values, dtype=float)
    if not high:
        v = -v
    if len(v) < 2 * lookback + 1:
        return []
    # each row is a bar with its `lookback` neighbours either side, the bar in the middle
    w = sliding_window_view(v, 2 * lookback + 1)
    mid = w[:, lookback]
    ok = (np.isfinite(w).all(axis=1) & (mid > w[:, :lookback].max(axis=1))
          & (mid > w[:, lookback + 1:].max(axis=1)))
    return (np.flatnonzero(ok) + lookback).tolist()


def divergences(df: pd.DataFrame, wt2: pd.Series,
                lookback: int = PIVOT_LOOKBACK) -> List[Dict[str, Any]]:
    """Price and WT2 disagreeing at consecutive WT2 pivots on the same side of zero, in the order they became known.

    `from` and `to` are the two pivots' bars, `known` the bar where the second was confirmed.
    """
    v = wt2.to_numpy(dtype=float)
    highs, lows = df["High"].to_numpy(dtype=float), df["Low"].to_numpy(dtype=float)
    out: List[Dict[str, Any]] = []
    tops = [p for p in pivots(v, lookback, high=True) if v[p] > 0]
    for a, b in zip(tops, tops[1:]):
        if highs[b] > highs[a] and v[b] < v[a]:
            out.append({"type": "bearish", "from": a, "to": b, "known": b + lookback})
    bottoms = [p for p in pivots(v, lookback, high=False) if v[p] < 0]
    for a, b in zip(bottoms, bottoms[1:]):
        if lows[b] < lows[a] and v[b] > v[a]:
            out.append({"type": "bullish", "from": a, "to": b, "known": b + lookback})
    out.sort(key=lambda x: (x["known"], x["type"]))
    return out


def _pct(x: float, digits: int) -> float:
    return round(float(x) * 100.0, digits)


def _measure(r: np.ndarray, pool: np.ndarray, way: str) -> Dict[str, Any]:
    """One signal at one horizon: its hit rate and mean against the window's, and the share of random draws of as
    many bars from the window it did better than (a higher mean for a signal that points up, lower for down)."""
    out: Dict[str, Any] = {"n": int(len(r)), "too_few": len(r) < MIN_SAMPLE, "hit_rate_pct": None,
                           "mean_pct": None, "baseline_hit_rate_pct": None, "baseline_mean_pct": None,
                           "edge_pct": None, "beats_random_pct": None}
    if out["too_few"] or len(pool) < len(r):
        return out
    hit = (r > 0).mean() if way == "up" else (r < 0).mean()
    base_hit = (pool > 0).mean() if way == "up" else (pool < 0).mean()
    mean, base = float(r.mean()), float(pool.mean())
    # as many distinct bars as there are signals, the same seed every time
    rng = np.random.default_rng(SEED)
    draws = np.array([pool[rng.choice(len(pool), size=len(r), replace=False)].mean()
                      for _ in range(RANDOM_RUNS)])
    beats = (draws < mean).mean() if way == "up" else (draws > mean).mean()
    out.update(hit_rate_pct=_pct(hit, 1), mean_pct=_pct(mean, 2), baseline_hit_rate_pct=_pct(base_hit, 1),
               baseline_mean_pct=_pct(base, 2), edge_pct=_pct(mean - base, 2), beats_random_pct=_pct(beats, 1))
    return out


def evidence(close: pd.Series, entries: Dict[str, Sequence[int]], start: int,
             horizons: Sequence[int] = HORIZONS) -> Dict[str, Any]:
    """What followed each kind of signal: `entries` are the bars where each became known, `start` the first bar of
    the window (the first with a WT2 reading, where a signal could first be known). A signal too near the last bar
    for a horizon is counted and left out of that horizon."""
    c = close.to_numpy(dtype=float)
    n = len(c)
    fwd: Dict[int, np.ndarray] = {}
    pool: Dict[int, np.ndarray] = {}
    for h in horizons:
        f = np.full(n, np.nan)
        if n > h:
            with np.errstate(divide="ignore", invalid="ignore"):
                f[:n - h] = c[h:] / c[:n - h] - 1.0
        f[~np.isfinite(f)] = np.nan
        fwd[h] = f
        tail = f[start:] if start < n else np.array([])
        pool[h] = tail[np.isfinite(tail)]
    rows = []
    for sid, label, way in SIGNALS:
        idx = sorted(i for i in set(entries.get(sid, ())) if start <= i < n)
        by = {}
        for h in horizons:
            r = fwd[h][idx] if idx else np.array([])
            by[str(h)] = _measure(r[np.isfinite(r)], pool[h], way)
        rows.append({"id": sid, "label": label, "direction": way, "count": len(idx), "by_horizon": by})
    baseline = {str(h): {"n": int(len(pool[h])),
                         "mean_pct": _pct(pool[h].mean(), 2) if len(pool[h]) else None,
                         "up_pct": _pct((pool[h] > 0).mean(), 1) if len(pool[h]) else None,
                         "down_pct": _pct((pool[h] < 0).mean(), 1) if len(pool[h]) else None}
                for h in horizons}
    return {"horizons": list(horizons), "min_sample": MIN_SAMPLE, "random_runs": RANDOM_RUNS,
            "signals": rows, "baseline": baseline, "finding": _finding(rows, horizons[len(horizons) // 2]),
            "method": ("Each signal is entered at the close of the bar where it became known: the cross's own bar, "
                       "or for a divergence the bar its second pivot was confirmed on. The change in the close 5, 10 "
                       "and 20 bars later is compared with the same change after every bar of the window, which is "
                       "what an entry at random averages to. A hit is a close that moved the signal's way. Each mean "
                       "is also set among {} random draws of as many bars from the window, always with the same "
                       "seed: doing better than a draw is a higher mean for a bullish signal and a lower one for a "
                       "bearish signal. Fewer than {} signals are counted and not measured, and a signal too near "
                       "the last bar for a horizon is left out of it. The windows overlap, so no t-statistic is "
                       "given, and with four signals at three horizons about one comparison in twenty clears 95% "
                       "by chance.").format(RANDOM_RUNS, MIN_SAMPLE)}


def _joined(words: List[str]) -> str:
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def _finding(rows: List[Dict[str, Any]], horizon: int) -> str:
    """The section's one line: how each measured signal did against random draws at the middle horizon."""
    at = str(horizon)
    fine = [r for r in rows if r["by_horizon"][at]["beats_random_pct"] is not None]
    if not fine:
        return ("Too few signals on these bars to measure any of them: each kind needs {} with {} bars after "
                "them.".format(MIN_SAMPLE, horizon))
    pct = ["{:.0f}%".format(r["by_horizon"][at]["beats_random_pct"]) for r in fine]
    said = ["{} did better than {} of random draws".format(fine[0]["label"].lower(), pct[0])]
    said += ["{} {}".format(r["label"].lower(), p) for r, p in zip(fine[1:], pct[1:])]
    head = "{} bars on, {}.".format(horizon, _joined(said))
    cleared = [r["label"].lower() for r in fine if r["by_horizon"][at]["beats_random_pct"] >= 95]
    if not cleared:
        return head + " None cleared 95%, the bar for more than luck."
    return head + " {} cleared 95%, though across this many comparisons one in twenty would by chance.".format(
        _joined(cleared).capitalize())


def describe(channel_len: int = CHANNEL_LEN, avg_len: int = AVG_LEN, ma_len: int = MA_LEN) -> Dict[str, str]:
    """The three registers every indicator here explains itself in, and its caveat."""
    return {
        "name": "WaveTrend",
        "measures": ("Where the typical price sits against its own {}-bar EMA, in units of its average distance "
                     "from it, smoothed over {} bars (WT1), with a {}-bar average of that line (WT2)."
                     .format(channel_len, avg_len, ma_len)),
        "represents": ("LazyBear's WaveTrend: the commodity channel index's construction on the typical price, "
                       "smoothed. WT1 is the oscillator, WT2 a short average of it, and their crosses are its "
                       "signals."),
        "why": ("A momentum reading fast enough to turn near short-term extremes, with two lines that cross the way "
                "MACD's do. The levels at 53 and 60 either side of zero are conventions, not measured thresholds."),
        "caveat": ("Unbounded, so a strong trend can hold it beyond the levels for weeks, and a cross out there is "
                   "not a turn. A cross on the bar still forming can undo itself before the close, and a divergence "
                   "is only known some bars after its second pivot. What followed each signal on these bars is "
                   "measured under the chart, against entries at random."),
    }


def build(df: pd.DataFrame, channel_len: int = CHANNEL_LEN, avg_len: int = AVG_LEN, ma_len: int = MA_LEN,
          overbought: Sequence[float] = OVERBOUGHT, oversold: Sequence[float] = OVERSOLD,
          lookback: int = PIVOT_LOOKBACK, intraday: bool = False) -> Dict[str, Any]:
    """The /api/indicators/wavetrend answer for `df`, newest bar last: the lines bar for bar (null in the warmup
    and wherever there is no reading), the crosses and divergences with their bars, and what followed them.
    Bars are named by date, or on intraday bars by moment, as /api/indicators names them."""
    if df is None or df.empty or not {"High", "Low", "Close"} <= set(df.columns):
        return {"available": False, "reason": "no price history"}
    w = warmup(channel_len, avg_len, ma_len)
    if len(df) <= w["wt2"] + 1:
        return {"available": False,
                "reason": "WaveTrend needs more than {} bars at these lengths and there are {}.".format(
                    w["wt2"] + 1, len(df))}
    s = series(df, channel_len, avg_len, ma_len)
    xs = crosses(s["wt1"], s["wt2"], overbought[0], oversold[0])
    dv = divergences(df, s["wt2"], lookback)
    stamps = [t.isoformat() if intraday else str(t.date()) for t in df.index]
    v1, v2 = s["wt1"].to_numpy(dtype=float), s["wt2"].to_numpy(dtype=float)
    read = np.flatnonzero(np.isfinite(v2))
    start = int(read[0]) if len(read) else len(df)
    entries = {
        "strong_bullish_cross": [x["i"] for x in xs if x["strong"] and x["type"] == "bullish"],
        "strong_bearish_cross": [x["i"] for x in xs if x["strong"] and x["type"] == "bearish"],
        "bullish_divergence": [x["known"] for x in dv if x["type"] == "bullish"],
        "bearish_divergence": [x["known"] for x in dv if x["type"] == "bearish"],
    }
    ev = evidence(df["Close"].astype(float), entries, start)
    ev["window"] = {"from": stamps[start] if start < len(df) else None, "to": stamps[-1],
                    "bars": max(0, len(df) - start)}
    highs, lows = df["High"].to_numpy(dtype=float), df["Low"].to_numpy(dtype=float)

    def point(i: int, price: float) -> Dict[str, Any]:
        return {"i": i, "t": stamps[i], "wt2": _f(v2[i], 2), "price": _f(price, 4)}

    return {
        "available": True,
        **describe(channel_len, avg_len, ma_len),
        "params": {"channel_len": channel_len, "avg_len": avg_len, "ma_len": ma_len, "pivot_lookback": lookback},
        "levels": {"overbought": [float(x) for x in overbought], "oversold": [float(x) for x in oversold]},
        "warmup": w,
        "timestamps": stamps,
        "wt1": _series(s["wt1"], 2),
        "wt2": _series(s["wt2"], 2),
        "hist": _series(s["hist"], 2),
        "crosses": [{"i": x["i"], "t": stamps[x["i"]], "type": x["type"], "strong": x["strong"],
                     "wt1": _f(v1[x["i"]], 2), "wt2": _f(v2[x["i"]], 2)} for x in xs],
        "divergences": [{"type": x["type"],
                         "from": point(x["from"], highs[x["from"]] if x["type"] == "bearish" else lows[x["from"]]),
                         "to": point(x["to"], highs[x["to"]] if x["type"] == "bearish" else lows[x["to"]]),
                         "confirmed": {"i": x["known"], "t": stamps[x["known"]]}} for x in dv],
        "evidence": ev,
    }
