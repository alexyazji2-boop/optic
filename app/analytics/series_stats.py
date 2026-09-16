"""Shared per-instrument statistics used by the macro and sector panels."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from .technicals import atr, bollinger, ema, rsi, sma

log = logging.getLogger(__name__)


def _f(value: Any, digits: int = 4) -> Optional[float]:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(out) else round(out, digits)


def pct_change_over(close: pd.Series, bars: int) -> Optional[float]:
    if close is None or len(close) <= bars:
        return None
    prior = close.iloc[-1 - bars]
    if prior == 0:
        return None
    return _f((close.iloc[-1] / prior - 1.0) * 100.0, 3)


# --------------------------------------------------------- live reconciliation


def live_quotes(provider, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
    """`provider.batch_quote` if the adapter has one, `{}` otherwise.

    Duck-typed deliberately. A provider with no quote feed and a quote feed that
    is down mean the same thing to every caller here — fall back to the bars —
    and neither is a reason to fail a panel that has a full year of history in
    hand.
    """
    fetch = getattr(provider, "batch_quote", None)
    if not callable(fetch):
        return {}
    try:
        out = fetch(list(symbols))
    except Exception as exc:                                    # noqa: BLE001
        log.warning("live_quotes: quote feed unavailable: %s", exc)
        return {}
    return out if isinstance(out, dict) else {}


def apply_quote(snap: Dict[str, Any], quote: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Take the one-day change from the quote instead of from the bars.

    `chg_1d` was the last daily close over the one before it. That is the
    session's change for a cash index and wrong for anything trading around the
    clock, because Yahoo's daily bars do not break where the session does.

    Measured across the macro strip on 2026-09-16. ES=F's prior bar closed at
    7589.25 against a prior settlement of 7672.50, so bar arithmetic read
    +1.196% on a day the contract was up +0.121% — the overnight gap counted
    twice, and an 83-point reference error. NQ=F was out by 1.28 points of
    percentage and RTY=F by 0.93. Gold was worse than imprecise: the bars said
    +0.413% and the quote said -0.307%, so the panel named the wrong direction
    on a haven instrument. The cash rows agreed to within 0.14 either way, which
    is what identifies the cause as session alignment rather than staleness.

    Only the one-day figure is reconciled, and the multi-day ones are left alone
    rather than left correct. They compare the same live last bar against an
    older bar on the same misaligned basis, so they carry the same reference
    error — for ES=F about 83 points, spread over a move several times larger.
    A quote supplies exactly one authoritative prior print, the previous
    settlement, and there is no equivalent for "five sessions ago" to reconcile
    `chg_5d` against, so correcting it would mean inventing a basis. Bar-derived
    at least keeps each multi-day figure consistent with the series it is drawn
    from, and `chg_5d` and `chg_20d` are what the risk-regime score consumes —
    worth knowing before trusting that score on a futures row.

    `last` is taken from the same quote, and for one reason: the UI prints price
    and change as a pair, so they have to be computed from the same two numbers
    or a reader can divide one by the other and catch the panel disagreeing with
    itself. It also drops the headline price from the five-minute history cache
    to the thirty-second quote.

    The ratio fields — `vs_sma20`, `pct_from_52w_high`, `atr_pct` and the rest —
    stay derived from the frame's own last close, so each remains consistent
    with the series it is measured against. At the scale that matters to them a
    quote is not meaningfully newer than the bar: the gap is under five minutes
    of drift against a twenty- to two-hundred-day average.

    `chg_1d_source` records which arithmetic produced the number, because a
    panel that quietly switches method between rows should say so.
    """
    snap["chg_1d_source"] = "bars"
    if not quote:
        return snap
    last, prev = quote.get("last"), quote.get("prev_close")
    if last is None or not prev:
        return snap
    change = _f((float(last) / float(prev) - 1.0) * 100.0, 3)
    if change is None:
        return snap
    snap["last"] = _f(last)
    snap["chg_1d"] = change
    snap["prev_close"] = _f(prev)
    snap["chg_1d_source"] = "quote"
    snap["quote_as_of"] = quote.get("as_of")
    return snap


def snapshot(df: pd.DataFrame, label: str = "") -> Dict[str, Any]:
    """Momentum / trend / stretch stats for a single instrument."""
    if df is None or df.empty or "Close" not in df:
        return {"label": label, "error": "no data"}

    close = df["Close"].dropna()
    if len(close) < 25:
        return {"label": label, "error": "insufficient history"}

    last = float(close.iloc[-1])
    sma20 = sma(close, 20)
    sma50 = sma(close, 50)
    sma200 = sma(close, 200)
    ema21 = ema(close, 21)
    rsi14 = rsi(close, 14)
    bb = bollinger(close, 20, 2.0)

    def rel(series: pd.Series) -> Optional[float]:
        clean = series.dropna()
        if clean.empty or clean.iloc[-1] == 0:
            return None
        return _f((last / clean.iloc[-1] - 1.0) * 100.0, 3)

    high_252 = float(close.tail(252).max())
    low_252 = float(close.tail(252).min())

    # Bandwidth percentile: a squeeze (low percentile) is what precedes a
    # breakout, so it's the screen input rather than raw volatility.
    width = ((bb["upper"] - bb["lower"]) / bb["mid"] * 100.0).dropna()
    squeeze_pct = None
    if len(width) >= 60:
        squeeze_pct = _f((width.tail(120) <= width.iloc[-1]).mean() * 100.0, 1)

    atr14 = atr(df, 14).dropna() if {"High", "Low"}.issubset(df.columns) else pd.Series(dtype=float)
    atr_pct = _f(atr14.iloc[-1] / last * 100.0, 3) if not atr14.empty else None

    vol_ratio = None
    if "Volume" in df and len(df) > 25:
        recent = df["Volume"].tail(5).mean()
        base = df["Volume"].tail(60).mean()
        if base and base > 0:
            vol_ratio = _f(recent / base, 3)

    return {
        "label": label,
        "last": _f(last),
        "chg_1d": pct_change_over(close, 1),
        "chg_5d": pct_change_over(close, 5),
        "chg_20d": pct_change_over(close, 20),
        "chg_60d": pct_change_over(close, 60),
        "chg_120d": pct_change_over(close, 120),
        "vs_sma20": rel(sma20),
        "vs_sma50": rel(sma50),
        "vs_sma200": rel(sma200),
        "vs_ema21": rel(ema21),
        "above_sma50": bool(last > sma50.dropna().iloc[-1]) if not sma50.dropna().empty else None,
        "above_sma200": bool(last > sma200.dropna().iloc[-1]) if not sma200.dropna().empty else None,
        "rsi": _f(rsi14.dropna().iloc[-1], 2) if not rsi14.dropna().empty else None,
        "pct_from_52w_high": _f((last / high_252 - 1.0) * 100.0, 2) if high_252 else None,
        "pct_from_52w_low": _f((last / low_252 - 1.0) * 100.0, 2) if low_252 else None,
        "dist_to_20d_high": _f((last / float(close.tail(20).max()) - 1.0) * 100.0, 2),
        "dist_to_60d_high": _f((last / float(close.tail(60).max()) - 1.0) * 100.0, 2),
        "squeeze_percentile": squeeze_pct,
        "atr_pct": atr_pct,
        "volume_ratio_5d_60d": vol_ratio,
        "series": [_f(v) for v in close.tail(90)],
    }


def relative_strength(df: pd.DataFrame, bench: pd.DataFrame) -> Dict[str, Any]:
    """Ratio-line analysis of an instrument against a benchmark.

    A rising ratio line means capital is rotating in, which is the actual
    tradable signal — absolute return alone can't tell leadership from beta.
    """
    if df is None or bench is None or df.empty or bench.empty:
        return {}

    joined = pd.concat(
        [df["Close"].rename("a"), bench["Close"].rename("b")], axis=1
    ).dropna()
    if len(joined) < 30:
        return {}

    ratio = joined["a"] / joined["b"]
    ratio_sma20 = ratio.rolling(20, min_periods=20).mean()
    ratio_sma50 = ratio.rolling(50, min_periods=50).mean()

    mean60 = ratio.tail(60).mean()
    std60 = ratio.tail(60).std(ddof=0)
    zscore = _f((ratio.iloc[-1] - mean60) / std60, 3) if std60 and std60 > 0 else None

    return {
        "ratio": _f(ratio.iloc[-1], 6),
        "rs_1w": pct_change_over(ratio, 5),
        "rs_1m": pct_change_over(ratio, 21),
        "rs_3m": pct_change_over(ratio, 63),
        "rs_6m": pct_change_over(ratio, 126),
        "ratio_above_sma20": (
            bool(ratio.iloc[-1] > ratio_sma20.dropna().iloc[-1])
            if not ratio_sma20.dropna().empty
            else None
        ),
        "ratio_above_sma50": (
            bool(ratio.iloc[-1] > ratio_sma50.dropna().iloc[-1])
            if not ratio_sma50.dropna().empty
            else None
        ),
        "ratio_zscore_60d": zscore,
        "ratio_series": [_f(v, 6) for v in ratio.tail(90)],
    }
