"""Cheap first-pass screen over a large universe.

The Tracker's real verdict is the full swing composite, which needs a quote, two
years of history, an options chain across four expiries, news and fundamentals.
Roughly four seconds a symbol. Running that over ~3,000 NASDAQ listings would
take hours per scan and would get the free data feed to throttle us.

So the scan is a funnel. This module is the wide end: one batched download per
few hundred symbols, daily bars only, and a score computed from price and volume
alone. It ranks the universe and hands a shortlist to the expensive stage.

Two things worth being clear about, because a screen that looks like a verdict is
the easy way to mislead someone:

* **This score is not the composite.** It sees no options positioning, no news,
  no fundamentals. It exists to decide *what deserves a closer look*, and a name
  can top this screen and then be rejected outright by the real analysis.
* **The liquidity gate does most of the work.** Of ~3,000 NASDAQ listings, the
  large majority are too thin to trade a real position in, let alone to have a
  usable options chain. Filtering those out isn't an optimisation, it's what
  makes the remaining numbers mean anything.
"""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

# Symbols per batched download. 150 comes out around 4 seconds; much larger and
# Yahoo starts truncating the response, which shows up as symbols silently
# missing from the result rather than as an error.
CHUNK_SIZE = 150

# Pause between batches. Twenty back-to-back downloads is what gets the free feed
# to rate-limit, and a throttled feed then breaks the *expensive* stage — where
# the options chains are — long after the screen itself has finished. A second per
# batch adds about twenty seconds to a scan and is much cheaper than that.
CHUNK_PAUSE_SECONDS = float(os.environ.get("SCREEN_CHUNK_PAUSE", "1.0"))

# Longer wait before retrying batches that came back empty, which is usually the
# feed's rate limit rather than a bad symbol list.
RETRY_PAUSE_SECONDS = float(os.environ.get("SCREEN_RETRY_PAUSE", "45"))

# A position needs to be exitable and the name needs a real options chain. Below
# roughly $20M traded a day, neither is true — the spread eats the edge and the
# chain is often a handful of strikes with no bid.
MIN_PRICE = 5.0
MIN_DOLLAR_VOLUME = 20_000_000.0

# Enough history for a 200-day average to exist at all.
MIN_BARS = 210

# Daily range above this isn't a swing trade, it's a coin flip. A name moving 15%
# a day makes any stop either meaningless or so wide the position rounds to zero.
MAX_ATR_PCT = 12.0

# A stock up 130% in a month is a post-catalyst biotech, and the catalyst is
# already public. Pure trend scoring loves those — every average is below price,
# every momentum term maxes out — which is exactly why they have to be excluded
# explicitly. The screen is looking for trends to join, not moves that are over.
MAX_ABS_ROC20 = 60.0


def _atr_pct(frame: pd.DataFrame, period: int = 14) -> Optional[float]:
    high, low, close = frame["High"], frame["Low"], frame["Close"]
    prev = close.shift(1)
    span = pd.concat([high - low, (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)
    atr = span.rolling(period).mean().iloc[-1]
    last = close.iloc[-1]
    if not np.isfinite(atr) or not last:
        return None
    return float(atr / last * 100.0)


def _score(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Signed trend/momentum score, negative for bearish.

    Weights are judgement, not a fit. They're written out as a breakdown so the
    number can be argued with instead of taken on faith.
    """
    factors: List[Dict[str, Any]] = []
    total = 0.0

    def award(points: float, label: str) -> None:
        nonlocal total
        total += points
        if points:
            factors.append({"label": label, "points": round(points, 1)})

    price = metrics["price"]
    for period, weight in (("sma20", 8.0), ("sma50", 10.0), ("sma200", 12.0)):
        level = metrics.get(period)
        if level:
            above = price > level
            award(weight if above else -weight,
                  "price {} its {}-day average".format("above" if above else "below",
                                                       period[3:]))

    # Structure: the 50/200 relationship is the crudest possible read on whether
    # the multi-month trend is up, and it's most of why it's here.
    if metrics.get("sma50") and metrics.get("sma200"):
        up = metrics["sma50"] > metrics["sma200"]
        award(10.0 if up else -10.0,
              "50-day average {} the 200-day".format("above" if up else "below"))

    # Momentum, capped so one violent month can't dominate the ranking.
    # tanh rather than a hard clip: a clip made every strong mover score exactly
    # the ceiling, so dozens of names tied at the top and the shortlist was
    # decided by dictionary order instead of by the data.
    for key, weight, label in (("roc20", 14.0, "1-month return"),
                               ("roc60", 12.0, "3-month return")):
        roc = metrics.get(key)
        if roc is not None:
            award(float(np.tanh(roc / 15.0)) * weight, label)

    # Where it sits in its own year. Near the high is where momentum continuation
    # happens; near the low is where it doesn't.
    pos = metrics.get("range_position")
    if pos is not None:
        award((pos - 0.5) * 2.0 * 10.0, "position in the 52-week range")

    # Volume expanding alongside a move is the difference between participation
    # and drift. Only counted in the direction the move is already going.
    expansion = metrics.get("volume_expansion")
    if expansion is not None and expansion > 1.15:
        award(np.sign(total) * min((expansion - 1.0) * 10.0, 6.0), "volume expanding")

    return {"score": round(total, 1), "factors": factors}


def _metrics(symbol: str, frame: pd.DataFrame) -> Optional[Dict[str, Any]]:
    if frame is None or len(frame) < MIN_BARS:
        return None
    close = frame["Close"].astype(float)
    volume = frame["Volume"].astype(float)
    price = float(close.iloc[-1])
    if not np.isfinite(price) or price <= 0:
        return None

    dollar_volume = float((close.tail(20) * volume.tail(20)).mean())
    window = close.tail(252)
    high52, low52 = float(window.max()), float(window.min())
    span = high52 - low52

    recent_vol = float(volume.tail(20).mean())
    base_vol = float(volume.tail(60).mean())

    out: Dict[str, Any] = {
        "symbol": symbol,
        "price": round(price, 2),
        "dollar_volume": round(dollar_volume, 0),
        "sma20": float(close.rolling(20).mean().iloc[-1]),
        "sma50": float(close.rolling(50).mean().iloc[-1]),
        "sma200": float(close.rolling(200).mean().iloc[-1]),
        "roc20": round(float(close.iloc[-1] / close.iloc[-21] - 1.0) * 100.0, 2)
        if len(close) > 21 else None,
        "roc60": round(float(close.iloc[-1] / close.iloc[-61] - 1.0) * 100.0, 2)
        if len(close) > 61 else None,
        "range_position": round((price - low52) / span, 3) if span > 0 else None,
        "volume_expansion": round(recent_vol / base_vol, 2) if base_vol else None,
        "atr_pct": _atr_pct(frame),
        "bars": int(len(frame)),
    }
    for key in ("sma20", "sma50", "sma200"):
        if not np.isfinite(out[key]):
            out[key] = None
        else:
            out[key] = round(out[key], 2)
    return out


def _rank(provider, symbols: Sequence[str], min_price: float, min_dollar_volume: float,
          progress: Optional[Callable[[int, int], None]]) -> Dict[str, Any]:
    """The expensive part: download and score the whole universe."""
    scored: List[Dict[str, Any]] = []
    with_data = 0
    illiquid = 0
    short_history = 0
    too_wild = 0
    already_moved = 0
    failed_batches = 0

    def absorb(frames: Dict[str, Any]) -> None:
        nonlocal with_data, short_history, illiquid, too_wild, already_moved
        for symbol, frame in frames.items():
            with_data += 1
            metrics = _metrics(symbol, frame)
            if metrics is None:
                short_history += 1
                continue
            if metrics["price"] < min_price or metrics["dollar_volume"] < min_dollar_volume:
                illiquid += 1
                continue
            if metrics["atr_pct"] is not None and metrics["atr_pct"] > MAX_ATR_PCT:
                too_wild += 1
                continue
            if metrics["roc20"] is not None and abs(metrics["roc20"]) > MAX_ABS_ROC20:
                already_moved += 1
                continue
            metrics.update(_score(metrics))
            scored.append(metrics)

    chunks = [symbols[i:i + CHUNK_SIZE] for i in range(0, len(symbols), CHUNK_SIZE)]
    missed: List[Sequence[str]] = []

    for index, chunk in enumerate(chunks):
        if index and CHUNK_PAUSE_SECONDS > 0:
            time.sleep(CHUNK_PAUSE_SECONDS)
        try:
            frames = provider.batch_history(chunk, period="1y", interval="1d")
        except Exception:
            frames = {}
        if frames:
            absorb(frames)
        else:
            missed.append(chunk)
        if progress:
            progress(min((index + 1) * CHUNK_SIZE, len(symbols)), len(symbols))

    # One retry pass for whole batches that came back empty. A batch usually fails
    # because the feed throttled us mid-scan, and leaving those symbols out would
    # silently narrow the universe — the ranking gets cached for over an hour, so a
    # gap here is a gap in every scan until it expires.
    if missed:
        time.sleep(RETRY_PAUSE_SECONDS)
        for chunk in missed:
            try:
                frames = provider.batch_history(chunk, period="1y", interval="1d")
            except Exception:
                frames = {}
            if frames:
                absorb(frames)
            else:
                failed_batches += 1
            time.sleep(CHUNK_PAUSE_SECONDS)

    # Rank on absolute score: the tracker takes both sides, so a deeply bearish
    # name is as interesting as a deeply bullish one. Liquidity breaks ties, so
    # among equally-rated setups the shortlist leans toward the ones with a real
    # options chain behind them.
    ranked = sorted(scored, key=lambda m: (abs(m["score"]), m["dollar_volume"]), reverse=True)

    return {
        "ranked": ranked,
        "universe_size": len(symbols),
        "with_data": with_data,
        "dropped_short_history": short_history,
        "dropped_illiquid": illiquid,
        "dropped_too_volatile": too_wild,
        "dropped_already_moved": already_moved,
        "failed_batches": failed_batches,
        "passed": len(scored),
        "ranked_at": time.time(),
        "gates": {
            "min_price": min_price,
            "min_dollar_volume": min_dollar_volume,
            "min_bars": MIN_BARS,
            "max_atr_pct": MAX_ATR_PCT,
            "max_abs_1m_move_pct": MAX_ABS_ROC20,
        },
    }


# The ranking is built from daily bars, so it doesn't change intraday in any way
# that matters — but re-running it costs ~3,000 symbol-downloads, which is exactly
# what gets the free feed to rate-limit. Cached so a manual scan right after a
# scheduled one reuses the ranking instead of re-earning a throttle.
CACHE_TTL_SECONDS = float(os.environ.get("SCREEN_CACHE_MINUTES", "90")) * 60.0

_CACHE: Dict[str, Any] = {}
_CACHE_LOCK = threading.RLock()

# Persisted to disk as well as memory. A restart would otherwise re-download the
# whole exchange, and on a host that redeploys or wakes from sleep that is exactly
# when the feed is least willing to answer three thousand requests.
CACHE_DIR = os.environ.get(
    "TRACKER_DATA_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                 "data"),
)
CACHE_PATH = os.path.join(CACHE_DIR, "screen_ranking.json")


def _load_disk_cache(key: str) -> Optional[Dict[str, Any]]:
    try:
        with open(CACHE_PATH) as handle:
            payload = json.load(handle)
    except (OSError, ValueError):
        return None
    if payload.get("key") != key:
        return None                             # different universe or gates
    ranking = payload.get("ranking")
    if not ranking or "ranked_at" not in ranking:
        return None
    return ranking


def _save_disk_cache(key: str, ranking: Dict[str, Any]) -> None:
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(CACHE_PATH, "w") as handle:
            json.dump({"key": key, "ranking": ranking}, handle)
    except OSError:
        pass                                    # a read-only disk isn't fatal


def run(provider, symbols: Sequence[str], top_n: int = 30,
        min_price: float = MIN_PRICE, min_dollar_volume: float = MIN_DOLLAR_VOLUME,
        exclude: Optional[Sequence[str]] = None,
        progress: Optional[Callable[[int, int], None]] = None,
        force: bool = False) -> Dict[str, Any]:
    """Rank a universe and return the shortlist plus the funnel that produced it.

    Exclusions and the shortlist size are applied *after* the cache, so holding a
    position in a name doesn't invalidate the ranking for everything else.
    """
    symbols = [s for s in symbols if s]
    skip = {s.upper() for s in (exclude or [])}
    key = "{}:{}:{}".format(len(symbols), min_price, min_dollar_volume)

    with _CACHE_LOCK:
        hit = _CACHE.get(key)
        if hit is None:
            hit = _load_disk_cache(key)
            if hit is not None:
                _CACHE[key] = hit
        fresh = bool(hit) and (time.time() - hit["ranked_at"]) < CACHE_TTL_SECONDS

    if fresh and not force:
        ranking = hit
        age_minutes = round((time.time() - hit["ranked_at"]) / 60.0, 1)
    else:
        ranking = _rank(provider, symbols, min_price, min_dollar_volume, progress)
        with _CACHE_LOCK:
            _CACHE[key] = ranking
            _save_disk_cache(key, ranking)
        age_minutes = 0.0

    ranked = ranking["ranked"]
    shortlist = [m for m in ranked if m["symbol"] not in skip][:top_n]

    out = {k: v for k, v in ranking.items() if k != "ranked"}
    out.update({
        "shortlist": shortlist,
        "already_held": sum(1 for m in ranked if m["symbol"] in skip),
        "ranking_age_minutes": age_minutes,
        "ranking_reused": bool(fresh and not force),
        "top_n": top_n,
        "caveat": "This is a price-and-volume prefilter, not the terminal's verdict. It "
                  "sees no options positioning, no news and no fundamentals. Its only job "
                  "is to choose which names get the full analysis, and a name can rank "
                  "first here and still be rejected outright by it.",
    })
    return out
