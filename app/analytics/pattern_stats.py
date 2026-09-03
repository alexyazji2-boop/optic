"""What actually followed each pattern, measured on real data.

Pattern software almost universally states a direction and stops. "Double bottom
— bullish reversal" is a claim about the future presented with the same
confidence as the geometry, which is a fact about the past. This module exists so
the terminal can show both and let them disagree.

Method, and the parts of it that matter:

* **Entry is the confirmation close, not the pattern's completion.** A double
  bottom is measured from the day price closed back above the middle peak. That
  is the first bar at which a reader could have acted, so it is the only entry
  that does not quietly assume foresight.
* **Unconfirmed patterns are measured too, separately.** Whether the geometry
  alone carries information is exactly the interesting question, and dropping
  those cases would answer it by assumption.
* **Against a benchmark, and against the name's own drift.** Excess over SPY is
  not enough on its own, and the first version of this was wrong because of it:
  every pattern came back positive, bearish ones included, head and shoulders at
  +2.43% excess. The cause was the universe, not the shapes — NVDA's average
  21-day excess over SPY across *all* bars is +4.0%, and 63% of its bars are
  positive. Any pattern detected in a name that outperformed inherits that for
  free. So each occurrence is measured against the unconditional baseline for its
  own ticker and horizon, and the reported number is the difference. The raw
  excess and the baseline are both carried so the correction is visible rather
  than buried.
* **Hit rate is against the same baseline.** Asking "was excess positive" scores
  a bullish pattern in a rising stock as correct by default; the test is whether
  the occurrence beat that ticker's own typical bar.
* **Non-overlapping only would be ideal and is not affordable** at this sample
  size, so overlapping windows are used and the t-statistic is deliberately not
  reported — the standard error would be understated. The honest summary is the
  hit rate and the excess, with the sample size next to it.

The result is a table of base rates cached on disk. It is not a forecast; it says
what the last few years did after this shape, which is the most a base rate can
ever say.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from . import patterns as patterns_mod

log = logging.getLogger(__name__)

# Deliberately a mixed universe. A list of megacap technology names would measure
# "what happened after this shape during a technology bull market" and report it
# as a property of the shape.
UNIVERSE = [
    "SPY", "QQQ", "IWM", "DIA",
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "AVGO", "AMD", "INTC", "ORCL",
    "JPM", "BAC", "GS", "V", "MA",
    "XOM", "CVX", "COP",
    "JNJ", "PFE", "UNH", "LLY",
    "PG", "KO", "WMT", "COST", "MCD", "HD",
    "CAT", "BA", "LMT", "UPS",
    "T", "VZ", "NEE", "DUK",
    "GLD", "TLT", "SLV",
]

BENCHMARK = "SPY"
HORIZONS = (5, 10, 21)
HISTORY = "10y"
CACHE_PATH = os.path.join("data", "pattern_stats.json")
CACHE_TTL_DAYS = 30

# Below this many observations a hit rate is noise dressed as a number. Reported
# as "too few" rather than shown.
MIN_SAMPLE = 20


def _forward_excess(closes: pd.Series, bench: pd.Series, at: pd.Timestamp,
                    bars: int) -> Optional[float]:
    """Excess return over the benchmark from `at` to `at` + bars sessions."""
    try:
        i = closes.index.get_loc(at)
    except KeyError:
        return None
    if isinstance(i, slice):
        return None
    if i + bars >= len(closes):
        return None
    stock = float(closes.iloc[i + bars] / closes.iloc[i] - 1.0)
    try:
        j = bench.index.get_loc(at)
    except KeyError:
        return None
    if isinstance(j, slice) or j + bars >= len(bench):
        return None
    market = float(bench.iloc[j + bars] / bench.iloc[j] - 1.0)
    return (stock - market) * 100.0


def _baselines(closes: pd.Series, bench: pd.Series) -> Dict[int, float]:
    """This ticker's mean forward excess over the benchmark across every bar.

    The null this whole exercise is measured against. Without it the answer is
    "did this stock beat the index over the last decade", which has nothing to do
    with the pattern that happened to be on the chart.
    """
    joined = pd.concat({"c": closes, "b": bench}, axis=1).dropna()
    out: Dict[int, float] = {}
    for h in HORIZONS:
        ex = ((joined["c"].shift(-h) / joined["c"] - 1.0)
              - (joined["b"].shift(-h) / joined["b"] - 1.0)) * 100.0
        ex = ex.dropna()
        out[h] = float(ex.mean()) if len(ex) else 0.0
    return out


def _collect(provider, universe: List[str]) -> List[Dict[str, Any]]:
    """One row per pattern occurrence, with its forward excess returns."""
    bench_df = provider.history(BENCHMARK, period=HISTORY, interval="1d")
    if bench_df is None or bench_df.empty:
        raise RuntimeError("benchmark history unavailable")
    bench = bench_df["Close"].astype(float)

    rows: List[Dict[str, Any]] = []
    for sym in universe:
        try:
            df = provider.history(sym, period=HISTORY, interval="1d")
        except Exception as exc:                                   # noqa: BLE001
            log.info("pattern_stats: %s unavailable: %s", sym, exc)
            continue
        if df is None or len(df) < 300:
            continue
        closes = df["Close"].astype(float)
        base = _baselines(closes, bench)

        # Detect over the whole history. Geometry uses only bars up to each
        # pattern's own end, and the measurement starts at confirmation, so
        # nothing here reads a price it could not have known.
        found = patterns_mod.chart_patterns(df, lookback=len(df))
        for pat in found:
            if pat.get("confirmed"):
                at_str, state = pat.get("confirmed_on"), "confirmed"
            elif pat.get("confirmed") is False:
                at_str, state = pat.get("end_date"), "unconfirmed"
            else:
                continue                      # triangles resolve, they don't confirm
            if not at_str:
                continue
            at = pd.Timestamp(at_str)
            if at.tzinfo is None and closes.index.tz is not None:
                at = at.tz_localize(closes.index.tz)
            row = {"ticker": sym, "name": pat["name"], "state": state,
                   "direction": pat["direction"], "date": at_str}
            ok = False
            for h in HORIZONS:
                val = _forward_excess(closes, bench, at, h)
                row["h%d" % h] = val
                row["b%d" % h] = None if val is None else val - base[h]
                ok = ok or val is not None
            if ok:
                rows.append(row)

        # Candlestick patterns, measured from the close of the signal bar.
        for i in range(60, len(df) - max(HORIZONS) - 1):
            sub = df.iloc[: i + 1]
            if len(sub) < 60:
                continue
            hits = patterns_mod.candle_patterns(sub, lookback=1)
            for hit in hits:
                at = df.index[i]
                row = {"ticker": sym, "name": hit["name"], "state": "candle",
                       "direction": hit["direction"], "date": str(at.date())}
                ok = False
                for h in HORIZONS:
                    val = _forward_excess(closes, bench, at, h)
                    row["h%d" % h] = val
                    row["b%d" % h] = None if val is None else val - base[h]
                    ok = ok or val is not None
                if ok:
                    rows.append(row)
    return rows


def _summarise(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not rows:
        return {"available": False, "reason": "no occurrences collected"}
    frame = pd.DataFrame(rows)
    out: Dict[str, Any] = {}
    for (name, state), grp in frame.groupby(["name", "state"]):
        key = "%s|%s" % (name, state)
        entry: Dict[str, Any] = {
            "name": name, "state": state,
            "direction": grp["direction"].iloc[0],
            "sample": int(len(grp)),
            "tickers": int(grp["ticker"].nunique()),
        }
        for h in HORIZONS:
            raw = grp["h%d" % h].dropna()
            adj = grp["b%d" % h].dropna()
            if len(adj) < MIN_SAMPLE:
                entry["h%d" % h] = None
                continue
            # Direction-aware, and against the ticker's own drift. Asking only
            # "was excess positive" scores every bullish pattern in a stock that
            # outperformed as correct, which is how the first version of this
            # concluded that head and shoulders was bullish.
            direction = entry["direction"]
            if direction in ("bullish", "up"):
                hits = (adj > 0).mean()
            elif direction in ("bearish", "down"):
                hits = (adj < 0).mean()
            else:
                hits = None
            entry["h%d" % h] = {
                # Raw excess over SPY, kept so the correction below is auditable.
                "excess_mean_pct": round(float(raw.mean()), 2),
                # The number that speaks to the pattern: excess over SPY, minus
                # what this ticker returned over SPY on an average bar.
                "edge_mean_pct": round(float(adj.mean()), 2),
                "edge_median_pct": round(float(adj.median()), 2),
                "drift_pct": round(float(raw.mean() - adj.mean()), 2),
                "hit_rate": round(float(hits), 3) if hits is not None else None,
                "n": int(len(adj)),
            }
        out[key] = entry
    return {
        "available": True,
        "patterns": out,
        "horizons": list(HORIZONS),
        "benchmark": BENCHMARK,
        "universe_size": len(UNIVERSE),
        "history": HISTORY,
        "min_sample": MIN_SAMPLE,
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "method": (
            "Every occurrence of each pattern across {n} names over {hist} of "
            "daily bars. Structural patterns are entered at the confirmation "
            "close. The first bar a reader could have acted on, and measured "
            "against {bm} over the identical dates AND against the ticker's own "
            "average bar, so a bullish pattern in a stock that outperformed for "
            "a decade has to beat that stock's own drift to count, without that "
            "second correction every pattern here measured as bullish, bearish "
            "ones included. Unconfirmed patterns "
            "are measured separately rather than dropped, because whether the "
            "geometry alone carries information is the question. Windows overlap, "
            "so no significance test is quoted: the standard error would be "
            "understated. A hit rate near 50% with an excess near zero is the "
            "honest description of most of these shapes."
        ).format(n=len(UNIVERSE), hist=HISTORY, bm=BENCHMARK),
    }


def build(provider, universe: Optional[List[str]] = None) -> Dict[str, Any]:
    return _summarise(_collect(provider, universe or UNIVERSE))


def load(provider=None, force: bool = False) -> Dict[str, Any]:
    """Cached base rates. A month old is fine — these move very slowly."""
    if not force and os.path.exists(CACHE_PATH):
        age_days = (time.time() - os.path.getmtime(CACHE_PATH)) / 86400.0
        if age_days < CACHE_TTL_DAYS:
            try:
                with open(CACHE_PATH, encoding="utf-8") as fh:
                    data = json.load(fh)
                data["cache_age_days"] = round(age_days, 1)
                return data
            except (OSError, ValueError) as exc:
                log.warning("pattern_stats: cache unreadable: %s", exc)
    if provider is None:
        return {"available": False,
                "reason": "Base rates have not been computed yet."}
    data = build(provider)
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
    except OSError as exc:
        log.warning("pattern_stats: could not write cache: %s", exc)
    data["cache_age_days"] = 0.0
    return data


def for_pattern(stats: Dict[str, Any], name: str,
                state: str) -> Optional[Dict[str, Any]]:
    if not stats or not stats.get("available"):
        return None
    return (stats.get("patterns") or {}).get("%s|%s" % (name, state))
