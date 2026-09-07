"""The watchlist as an intelligence feed rather than a quote table.

A row of prices tells a reader what they could get from any broker. The
question they actually have when they open a watchlist is "which of these
changed, and does it matter" — so every row carries a **what changed** line and
a qualitative signal alongside the price.

**Derived, never written by a model.** A watchlist of ten names would cost ten
AI calls per refresh against a thirty-an-hour budget, and a "what changed" line
that goes blank when the budget trips or the key is unset is worse than none.
Everything here comes out of one batched history pull, and every line cites the
number that triggered it — so it can be checked, which is the whole difference
between an observation and a plausible sentence.

**One network call for the whole list.** `batch_history` is the difference
between a 2-second panel and a 30-second one; per-symbol fetches would make a
ten-name list unusable.

The signal is qualitative for the same reason Optic Pulse is: a 0-100 number
here would imply a model that has been tested, and this one is a moving-average
stack read plus a relative-strength comparison. It says bullish, neutral or
bearish, and the reason sits next to it.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

BENCH = "SPY"

# Enough history for a 50-day average and a 20-day range with room to spare.
PERIOD = "6mo"

# How far a one-day move has to travel before it is the headline for a row.
BIG_MOVE_SIGMA = 1.5

# Volume multiple that counts as a genuine surge rather than a busy morning.
VOLUME_SURGE = 1.8

_TTL = 90.0                      # seconds; a watchlist is glanced at, not streamed
_cache: Dict[str, Any] = {}
_lock = threading.Lock()


def _num(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if np.isfinite(out) else None


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _frames(provider, symbols: List[str]) -> Dict[str, pd.DataFrame]:
    """Batched history for the list plus the benchmark, cached briefly.

    Keyed on the symbol set, so adding a name refetches and reordering does not.
    """
    wanted = sorted({s.upper().strip() for s in symbols if s and s.strip()} | {BENCH})
    key = ",".join(wanted)
    with _lock:
        hit = _cache.get(key)
        if hit and (time.time() - hit["at"]) < _TTL:
            return hit["frames"]
    try:
        frames = provider.batch_history(wanted, period=PERIOD, interval="1d") or {}
    except Exception:
        frames = {}
    with _lock:
        _cache[key] = {"at": time.time(), "frames": frames}
    return frames


def _change(closes: pd.Series, back: int) -> Optional[float]:
    if len(closes) <= back:
        return None
    prev, last = _num(closes.iloc[-1 - back]), _num(closes.iloc[-1])
    if prev in (None, 0) or last is None:
        return None
    return (last / prev - 1.0) * 100.0


def _what_changed(closes: pd.Series, volumes: Optional[pd.Series],
                  bench: Optional[pd.Series]) -> Optional[Dict[str, str]]:
    """The strongest true statement about this name today.

    Ordered by how much it would change a reader's mind, not by how easy it is
    to compute. A 20-day breakout outranks "up 2%" because the first is a
    change of state and the second is a Tuesday.

    Returns None when nothing clears its threshold. That is a real answer — most
    names on most days have not done anything — and it beats manufacturing a
    line so the column is never empty.
    """
    if len(closes) < 25:
        return None
    last = _num(closes.iloc[-1])
    if last is None:
        return None

    # A range break, measured against the window BEFORE today so today's own
    # print cannot be the high it is breaking.
    prior = closes.iloc[-21:-1]
    hi, lo = _num(prior.max()), _num(prior.min())
    if hi and last > hi:
        return {"text": "20-day breakout", "why": "closed above the prior 20-day high of {:,.2f}".format(hi)}
    if lo and last < lo:
        return {"text": "20-day breakdown", "why": "closed below the prior 20-day low of {:,.2f}".format(lo)}

    # A move large against this name's own recent volatility, which is the only
    # scale on which "big" means anything — 2% is enormous for KO and quiet for
    # a leveraged semiconductor fund.
    rets = closes.pct_change().dropna()
    if len(rets) >= 20:
        sigma = _num(rets.iloc[-20:].std())
        today = _num(rets.iloc[-1])
        if sigma and today is not None and abs(today) > BIG_MOVE_SIGMA * sigma:
            return {"text": "Outsized move",
                    "why": "today's {:+.1f}% is {:.1f}x its own 20-day volatility".format(
                        today * 100, abs(today) / sigma)}

    # A moving-average cross, which is a change of state rather than a level.
    fast, slow = _ema(closes, 9), _ema(closes, 21)
    if len(fast) >= 2:
        now = _num(fast.iloc[-1]) - _num(slow.iloc[-1])
        was = _num(fast.iloc[-2]) - _num(slow.iloc[-2])
        if now is not None and was is not None:
            if was <= 0 < now:
                return {"text": "9/21 EMA cross up", "why": "the 9-day EMA crossed above the 21-day today"}
            if was >= 0 > now:
                return {"text": "9/21 EMA cross down", "why": "the 9-day EMA crossed below the 21-day today"}

    # Volume, which says whether anyone was there for the move.
    if volumes is not None and len(volumes) >= 21:
        avg = _num(volumes.iloc[-21:-1].mean())
        today_v = _num(volumes.iloc[-1])
        if avg and today_v and today_v > VOLUME_SURGE * avg:
            return {"text": "Volume surge",
                    "why": "{:.1f}x its 20-day average volume".format(today_v / avg)}

    # Leadership against the benchmark over a week. Weakest of the five, so last.
    if bench is not None and len(bench) > 6:
        mine, theirs = _change(closes, 5), _change(bench, 5)
        if mine is not None and theirs is not None and abs(mine - theirs) >= 3.0:
            return {"text": "Leading the market" if mine > theirs else "Lagging the market",
                    "why": "{:+.1f}% over five sessions against {} at {:+.1f}%".format(
                        mine, BENCH, theirs)}
    return None


def _signal(closes: pd.Series) -> Dict[str, Any]:
    """Bullish, neutral or bearish, from the average stack. Qualitative for the
    reason stated in the module docstring: this is a stack read, not a model."""
    if len(closes) < 55:
        return {"state": "unknown", "why": "not enough history to read a trend"}
    last = _num(closes.iloc[-1])
    e9, e21, e50 = (_num(_ema(closes, n).iloc[-1]) for n in (9, 21, 50))
    if None in (last, e9, e21, e50):
        return {"state": "unknown", "why": "price history has gaps"}
    if e9 > e21 > e50 and last > e9:
        return {"state": "bullish", "why": "price above a rising 9 > 21 > 50 stack"}
    if e9 < e21 < e50 and last < e9:
        return {"state": "bearish", "why": "price below a falling 9 < 21 < 50 stack"}
    return {"state": "neutral", "why": "the averages are not stacked in either direction"}


def build(provider, symbols: List[str]) -> Dict[str, Any]:
    """One row per symbol: price, change, what changed, and a signal."""
    wanted = [s.upper().strip() for s in symbols if s and s.strip()]
    if not wanted:
        return {"available": True, "rows": [], "reason_none":
                "Nothing on the watchlist yet. Add a symbol to start following it.",
                "benchmark": BENCH, "method": _METHOD}

    frames = _frames(provider, wanted)
    bench_frame = frames.get(BENCH)
    bench_closes = bench_frame["Close"].dropna() if bench_frame is not None \
        and not bench_frame.empty and "Close" in bench_frame else None

    rows: List[Dict[str, Any]] = []
    missing: List[str] = []
    for sym in wanted:
        frame = frames.get(sym)
        if frame is None or frame.empty or "Close" not in frame:
            missing.append(sym)
            rows.append({"symbol": sym, "available": False,
                         "reason": "No price history returned for this symbol."})
            continue
        closes = frame["Close"].dropna()
        if closes.empty:
            missing.append(sym)
            rows.append({"symbol": sym, "available": False,
                         "reason": "No price history returned for this symbol."})
            continue
        volumes = frame["Volume"].dropna() if "Volume" in frame else None
        changed = _what_changed(closes, volumes, bench_closes)
        sig = _signal(closes)
        rows.append({
            "symbol": sym,
            "available": True,
            "price": _num(closes.iloc[-1]),
            "change_pct": _change(closes, 1),
            "change_5d_pct": _change(closes, 5),
            "change_20d_pct": _change(closes, 20),
            "changed": changed,
            "signal": sig["state"],
            "signal_why": sig["why"],
            "bars": int(len(closes)),
        })

    return {
        "available": True,
        "rows": rows,
        "benchmark": BENCH,
        "unavailable": missing,
        "method": _METHOD,
    }


_METHOD = (
    "Every row is computed from daily closes in one batched pull, and each "
    "'what changed' line names the number that triggered it. Nothing here is "
    "written by a model. A blank change column means this name has not done "
    "anything that clears a threshold, which is the usual state and is worth "
    "saying rather than filling."
)
