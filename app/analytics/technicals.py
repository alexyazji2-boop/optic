"""Technical factors for swing timeframes: RSI, MACD, moving averages,
Fibonacci retracements, ATR, and a directional-bias read that decides which
way the Fib levels get drawn.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from scipy.signal import argrelextrema


# ---------------------------------------------------------------- indicators


def sma(series: pd.Series, length: int) -> pd.Series:
    return series.rolling(length, min_periods=length).mean()


def ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False, min_periods=length).mean()


def rsi(close: pd.Series, length: int = 14) -> pd.Series:
    """Wilder's RSI (the one every charting package draws by default)."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / length, adjust=False, min_periods=length).mean()
    avg_loss = loss.ewm(alpha=1.0 / length, adjust=False, min_periods=length).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100.0 - (100.0 / (1.0 + rs))
    # All-gain windows divide by zero -> pin to 100.
    return out.where(avg_loss > 0, 100.0).where(avg_gain > 0, out.fillna(50.0))


def macd(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> Dict[str, pd.Series]:
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = macd_line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return {
        "macd": macd_line,
        "signal": signal_line,
        "hist": macd_line - signal_line,
    }


def atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    prev_close = df["Close"].shift(1)
    tr = pd.concat(
        [
            df["High"] - df["Low"],
            (df["High"] - prev_close).abs(),
            (df["Low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1.0 / length, adjust=False, min_periods=length).mean()


def bollinger(close: pd.Series, length: int = 20, mult: float = 2.0) -> Dict[str, pd.Series]:
    mid = sma(close, length)
    sd = close.rolling(length, min_periods=length).std(ddof=0)
    return {"mid": mid, "upper": mid + mult * sd, "lower": mid - mult * sd}


# ------------------------------------------------------------------ helpers


def _f(value: Any) -> Optional[float]:
    """numpy/pandas scalar -> JSON-safe float (NaN becomes None)."""
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(out) else round(out, 6)


def _last(series: pd.Series) -> Optional[float]:
    if series is None or series.empty:
        return None
    return _f(series.iloc[-1])


def _slope_pct(series: pd.Series, lookback: int = 10) -> Optional[float]:
    """Percent change of an indicator over ``lookback`` bars, used to tell a
    rising 50-day from a rolling-over one."""
    clean = series.dropna()
    if len(clean) <= lookback:
        return None
    prior = clean.iloc[-1 - lookback]
    if prior == 0:
        return None
    return _f((clean.iloc[-1] / prior - 1.0) * 100.0)


def find_swing_points(df: pd.DataFrame, lookback: int = 120) -> Dict[str, Any]:
    """Highest high / lowest low in the recent window, plus which came last.

    Which extreme is more recent is what decides whether the current leg is up
    or down, and therefore which direction the Fib grid is anchored.
    """
    window = df.tail(lookback)
    if window.empty:
        return {}
    hi_idx = window["High"].idxmax()
    lo_idx = window["Low"].idxmin()
    return {
        "swing_high": _f(window["High"].max()),
        "swing_low": _f(window["Low"].min()),
        "swing_high_date": str(hi_idx.date()),
        "swing_low_date": str(lo_idx.date()),
        "high_is_recent": bool(hi_idx > lo_idx),
        "lookback_bars": int(len(window)),
    }


# ------------------------------------------------------------ fib retracement

FIB_RATIOS = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
FIB_EXTENSIONS = [1.272, 1.618]


def fib_levels(swing: Dict[str, Any], bias: str, spot: float) -> Dict[str, Any]:
    """Fibonacci grid anchored by trend direction.

    Bullish leg (low -> high): retracements sit *below* price and act as
    support, so 0% is the swing high and 100% is the swing low. Extensions
    project upward past the high as targets.

    Bearish leg (high -> low): retracements sit *above* price and act as
    resistance, anchored the other way, with extensions projecting downward.
    """
    hi = swing.get("swing_high")
    lo = swing.get("swing_low")
    if hi is None or lo is None or hi <= lo:
        return {}

    span = hi - lo
    bullish = bias in ("bullish", "neutral-bullish")
    levels: List[Dict[str, Any]] = []

    for ratio in FIB_RATIOS:
        price = hi - span * ratio if bullish else lo + span * ratio
        levels.append(
            {
                "ratio": ratio,
                "label": "{:.1f}%".format(ratio * 100),
                "price": _f(price),
                "role": ("support" if price < spot else "resistance"),
                "distance_pct": _f((price / spot - 1.0) * 100.0),
                "is_golden": ratio in (0.5, 0.618),
            }
        )

    for ratio in FIB_EXTENSIONS:
        price = lo + span * ratio if bullish else hi - span * ratio
        levels.append(
            {
                "ratio": ratio,
                "label": "{:.1f}% ext".format(ratio * 100),
                "price": _f(price),
                "role": "target",
                "distance_pct": _f((price / spot - 1.0) * 100.0),
                "is_golden": False,
            }
        )

    levels.sort(key=lambda item: (item["price"] is None, -(item["price"] or 0.0)))

    # The two levels bracketing spot are the ones that matter for entries.
    below = [lv for lv in levels if lv["price"] is not None and lv["price"] < spot]
    above = [lv for lv in levels if lv["price"] is not None and lv["price"] > spot]

    return {
        "direction": "bullish" if bullish else "bearish",
        "anchor_high": hi,
        "anchor_low": lo,
        "anchor_high_date": swing.get("swing_high_date"),
        "anchor_low_date": swing.get("swing_low_date"),
        "levels": levels,
        "nearest_support": max(below, key=lambda lv: lv["price"]) if below else None,
        "nearest_resistance": min(above, key=lambda lv: lv["price"]) if above else None,
        "retracement_pct": _f((hi - spot) / span * 100.0) if bullish else _f((spot - lo) / span * 100.0),
    }


# --------------------------------------------------- support & resistance


def support_resistance_levels(
    df: pd.DataFrame,
    spot: float,
    lookback: int = 252,
    order: int = 4,
    max_levels: int = 8,
) -> List[Dict[str, Any]]:
    """Support/resistance from candle structure, scored rather than counted.

    Deliberately distinct from the Fibonacci grid above: Fibonacci is a ratio
    projected from one swing, this is empirical. Four properties of a candle
    decide how much a pivot is worth, because a level is only as real as the
    reaction it produced:

    * **Touches** — how many separate pivots cluster at the price.
    * **Rejection** — the share of each pivot bar that is wick rather than body.
      A long upper wick means price reached the level and was pushed back inside
      the bar; a bar that closed at its high did not get rejected there, it broke
      through, so it scores far less.
    * **Volume** — total volume on bars whose range spans the level. Price
      turning on heavy participation is a stronger memory than a thin spike.
    * **Recency** — pivots decay with age. A level defended last month matters
      more than the same price a year ago.

    Clustering tolerance scales with ATR instead of a fixed percentage: on a
    quiet name 1.5% merges genuinely separate shelves, and on a volatile one it
    splits a single shelf into several.
    """
    window = df.tail(lookback)
    if len(window) < order * 2 + 10:
        return []

    highs = window["High"].to_numpy(dtype=float)
    lows = window["Low"].to_numpy(dtype=float)
    opens = window["Open"].to_numpy(dtype=float)
    closes = window["Close"].to_numpy(dtype=float)
    volumes = (
        window["Volume"].to_numpy(dtype=float)
        if "Volume" in window else np.ones(len(window))
    )
    bars = len(window)

    # ATR sets the merge tolerance. Falls back to a percentage of spot when ATR
    # is unavailable (too little history) so the function still returns levels.
    atr_series = atr(window, 14).dropna()
    tol = float(atr_series.iloc[-1]) * 0.6 if not atr_series.empty else spot * 0.012
    if not np.isfinite(tol) or tol <= 0:
        tol = spot * 0.012

    high_idx = argrelextrema(highs, np.greater_equal, order=order)[0]
    low_idx = argrelextrema(lows, np.less_equal, order=order)[0]

    pivots: List[Dict[str, Any]] = []
    for i in high_idx:
        rng = highs[i] - lows[i]
        # Upper wick as a fraction of the bar. 0 means it closed at its high
        # (no rejection); ~1 means the entire bar was a rejection tail.
        rejection = (highs[i] - max(opens[i], closes[i])) / rng if rng > 0 else 0.0
        pivots.append({"price": float(highs[i]), "kind": "swing high",
                       "bars_ago": bars - 1 - int(i), "rejection": float(rejection)})
    for i in low_idx:
        rng = highs[i] - lows[i]
        rejection = (min(opens[i], closes[i]) - lows[i]) / rng if rng > 0 else 0.0
        pivots.append({"price": float(lows[i]), "kind": "swing low",
                       "bars_ago": bars - 1 - int(i), "rejection": float(rejection)})

    if not pivots:
        return []

    pivots.sort(key=lambda p: p["price"])

    clusters: List[Dict[str, Any]] = []
    for piv in pivots:
        match = next((c for c in clusters if abs(piv["price"] - c["mean"]) <= tol), None)
        if match:
            match["pivots"].append(piv)
            match["mean"] = float(np.mean([p["price"] for p in match["pivots"]]))
        else:
            clusters.append({"mean": piv["price"], "pivots": [piv]})

    total_volume = float(volumes.sum()) or 1.0
    levels: List[Dict[str, Any]] = []
    for c in clusters:
        group = c["pivots"]
        if len(group) < 2:
            continue  # a single pivot is a spike, not a level
        level = c["mean"]

        # Volume transacted at the level: bars whose high-low range spans it.
        spanning = (highs >= level) & (lows <= level)
        vol_at_level = float(volumes[spanning].sum())
        vol_share = vol_at_level / total_volume

        # Recency: newest pivot in the cluster, decaying over the lookback.
        freshest = min(p["bars_ago"] for p in group)
        recency = float(np.exp(-freshest / (bars / 3.0)))
        avg_rejection = float(np.mean([p["rejection"] for p in group]))

        # Weights: touches carry the most, then how hard price was rejected,
        # then participation, then recency. Capped so one dimension can't
        # dominate — a level with 10 touches and no rejection is not stronger
        # than one with 3 clean rejections on heavy volume.
        strength = (
            min(len(group), 6) / 6.0 * 40.0
            + min(avg_rejection, 1.0) * 25.0
            + min(vol_share * 4.0, 1.0) * 20.0
            + recency * 15.0
        )

        kinds = {p["kind"] for p in group}
        levels.append({
            "price": _f(round(level, 2)),
            "touches": len(group),
            # Role is by position relative to price now, which is how these are
            # traded: a broken resistance becomes support and vice versa.
            "role": "resistance" if level > spot else "support",
            "distance_pct": _f(round((level / spot - 1.0) * 100.0, 2)),
            "strength": _f(round(strength, 1)),
            "rejection_pct": _f(round(avg_rejection * 100.0, 0)),
            "volume_share_pct": _f(round(vol_share * 100.0, 1)),
            "last_touch_bars_ago": freshest,
            "origin": "both" if len(kinds) > 1 else next(iter(kinds)),
            "band_low": _f(round(level - tol / 2, 2)),
            "band_high": _f(round(level + tol / 2, 2)),
        })

    levels.sort(key=lambda lv: -(lv["strength"] or 0))
    return levels[:max_levels]



# --------------------------------------------------------------- entry point


# Realized-volatility windows, and whether vol is opening up or settling down.
#
# There was already a single 20-day figure, which the IV/realized ratio compares
# against. One window can say implied is 1.3x realized; it cannot say whether
# that gap is closing. A 1.3x against vol that has doubled in a fortnight is a
# market catching up to a real move; the same 1.3x against vol drifting lower is
# the option actually being expensive. Those call for opposite trades, so the
# ratio is close to unusable without the trend beside it.
#
# Close-to-close log returns, annualised by sqrt(252). Log returns rather than
# simple percentage changes because they are additive across days, which is the
# assumption the sqrt-time scaling depends on.
HV_WINDOWS = (10, 20, 30, 60)

# How far apart short- and long-window vol must sit before the move is called
# rather than treated as noise. 15% of the slower reading: below that, the two
# windows on the same series routinely differ by more than any story explains.
HV_TREND_BAND = 0.15


def realised_vol(close: pd.Series, window: int) -> Optional[float]:
    """Annualised close-to-close volatility over `window` bars, in percent."""
    if close is None or len(close) < window + 1:
        return None
    rets = np.log(close / close.shift(1)).dropna()
    if len(rets) < window:
        return None
    sd = float(rets.tail(window).std(ddof=0))
    if not np.isfinite(sd):
        return None
    return _f(sd * np.sqrt(252) * 100.0)


def realised_vol_windows(df: pd.DataFrame) -> Dict[str, Any]:
    """Realized vol across several windows, plus a plain read of the direction."""
    if df is None or df.empty or "Close" not in df:
        return {}
    close = df["Close"].dropna()
    out: Dict[str, Any] = {}
    for window in HV_WINDOWS:
        out[f"hv_{window}d"] = realised_vol(close, window)

    fast, slow = out.get("hv_10d"), out.get("hv_60d")
    trend, note = None, ""
    if fast is not None and slow is not None and slow > 0:
        change = (fast - slow) / slow
        if change > HV_TREND_BAND:
            trend = "expanding"
            note = (f"10-day realized vol ({fast:.1f}%) is running "
                    f"{change * 100:.0f}% above the 60-day ({slow:.1f}%) — "
                    "the stock has become more volatile recently.")
        elif change < -HV_TREND_BAND:
            trend = "contracting"
            note = (f"10-day realized vol ({fast:.1f}%) is running "
                    f"{abs(change) * 100:.0f}% below the 60-day ({slow:.1f}%) — "
                    "the stock has been settling down.")
        else:
            trend = "steady"
            note = (f"10-day and 60-day realized vol are within "
                    f"{HV_TREND_BAND * 100:.0f}% of each other, so recent movement "
                    "is in line with the last quarter.")
        # This module's _f takes no precision argument, unlike entry.py's.
        out["hv_fast_vs_slow_pct"] = _f(round(change * 100.0, 1))
    out["hv_trend"] = trend
    out["hv_trend_note"] = note
    return out


def analyse(df: pd.DataFrame, swing_lookback: int = 120) -> Dict[str, Any]:
    """Compute the full technical picture from a daily OHLCV frame."""
    if df is None or len(df) < 30:
        return {"error": "not enough price history for technical analysis"}

    close = df["Close"]
    spot = float(close.iloc[-1])

    rsi14 = rsi(close, 14)
    macd_parts = macd(close)
    bb = bollinger(close)
    atr14 = atr(df)

    mas = {
        "sma20": sma(close, 20),
        "sma50": sma(close, 50),
        "sma100": sma(close, 100),
        "sma200": sma(close, 200),
        "ema9": ema(close, 9),
        "ema21": ema(close, 21),
        "ema50": ema(close, 50),
    }

    ma_snapshot = {}
    for name, series in mas.items():
        value = _last(series)
        ma_snapshot[name] = {
            "value": value,
            "distance_pct": _f((spot / value - 1.0) * 100.0) if value else None,
            "position": None if value is None else ("above" if spot > value else "below"),
            "slope_10d_pct": _slope_pct(series, 10),
        }

    # --- trend structure
    sma20_v, sma50_v, sma200_v = (
        ma_snapshot["sma20"]["value"],
        ma_snapshot["sma50"]["value"],
        ma_snapshot["sma200"]["value"],
    )
    stacked_bull = all(
        v is not None for v in (sma20_v, sma50_v, sma200_v)
    ) and sma20_v > sma50_v > sma200_v
    stacked_bear = all(
        v is not None for v in (sma20_v, sma50_v, sma200_v)
    ) and sma20_v < sma50_v < sma200_v

    golden_cross = None
    if sma50_v is not None and sma200_v is not None:
        prev50 = mas["sma50"].iloc[-6] if len(mas["sma50"].dropna()) > 6 else np.nan
        prev200 = mas["sma200"].iloc[-6] if len(mas["sma200"].dropna()) > 6 else np.nan
        if np.isfinite(prev50) and np.isfinite(prev200):
            if prev50 <= prev200 and sma50_v > sma200_v:
                golden_cross = "golden cross (50 crossed above 200) within 5 bars"
            elif prev50 >= prev200 and sma50_v < sma200_v:
                golden_cross = "death cross (50 crossed below 200) within 5 bars"

    # --- scored bias, -100 (max bearish) to +100 (max bullish)
    score = 0.0
    reasons: List[str] = []

    if stacked_bull:
        score += 25
        reasons.append("MAs stacked bullish (20>50>200)")
    elif stacked_bear:
        score -= 25
        reasons.append("MAs stacked bearish (20<50<200)")

    if sma200_v is not None:
        if spot > sma200_v:
            score += 15
            reasons.append("price above 200-SMA")
        else:
            score -= 15
            reasons.append("price below 200-SMA")

    if sma50_v is not None:
        score += 10 if spot > sma50_v else -10

    ema9_v, ema21_v = ma_snapshot["ema9"]["value"], ma_snapshot["ema21"]["value"]
    if ema9_v is not None and ema21_v is not None:
        if ema9_v > ema21_v:
            score += 10
            reasons.append("9-EMA above 21-EMA (short-term up)")
        else:
            score -= 10
            reasons.append("9-EMA below 21-EMA (short-term down)")

    rsi_v = _last(rsi14)
    if rsi_v is not None:
        if rsi_v >= 70:
            score -= 5
            reasons.append("RSI {:.1f} overbought — chase risk".format(rsi_v))
        elif rsi_v <= 30:
            score += 5
            reasons.append("RSI {:.1f} oversold — bounce candidate".format(rsi_v))
        elif rsi_v > 55:
            score += 10
            reasons.append("RSI {:.1f} in bullish regime".format(rsi_v))
        elif rsi_v < 45:
            score -= 10
            reasons.append("RSI {:.1f} in bearish regime".format(rsi_v))

    macd_v, sig_v, hist_v = (
        _last(macd_parts["macd"]),
        _last(macd_parts["signal"]),
        _last(macd_parts["hist"]),
    )
    hist_series = macd_parts["hist"].dropna()
    macd_cross = None
    if len(hist_series) >= 3:
        if hist_series.iloc[-1] > 0 and hist_series.iloc[-2] <= 0:
            macd_cross = "bullish crossover today"
        elif hist_series.iloc[-1] < 0 and hist_series.iloc[-2] >= 0:
            macd_cross = "bearish crossover today"
        elif hist_series.iloc[-1] > hist_series.iloc[-2] > hist_series.iloc[-3]:
            macd_cross = "histogram expanding up"
        elif hist_series.iloc[-1] < hist_series.iloc[-2] < hist_series.iloc[-3]:
            macd_cross = "histogram expanding down"

    if macd_v is not None and sig_v is not None:
        if macd_v > sig_v:
            score += 15
            reasons.append("MACD above signal")
        else:
            score -= 15
            reasons.append("MACD below signal")
        if macd_v > 0:
            score += 5
        else:
            score -= 5

    score = float(np.clip(score, -100, 100))
    if score >= 40:
        bias = "bullish"
    elif score >= 12:
        bias = "neutral-bullish"
    elif score <= -40:
        bias = "bearish"
    elif score <= -12:
        bias = "neutral-bearish"
    else:
        bias = "neutral"

    swing = find_swing_points(df, swing_lookback)
    fib = fib_levels(swing, bias, spot)
    sr_levels = support_resistance_levels(df, spot)

    atr_v = _last(atr14)
    hv = realised_vol_windows(df)
    # One definition of 20-day realized vol, not two.
    #
    # This was `close.pct_change()` while the window ladder below uses log
    # returns, so the same panel showed 36.7% and 37.2% under labels a reader
    # would take to mean the same thing. Log returns win because they are
    # additive across days, which is the assumption the sqrt(252) annualisation
    # already relies on. The IV/realized ratio shifts by ~1.5% of itself and no
    # verdict band (1.35 / 1.1 / 0.9) changes hands.
    rv20 = hv.get("hv_20d")

    return {
        "spot": _f(spot),
        "bias": bias,
        "trend_score": _f(score),
        "reasons": reasons,
        "rsi": {
            "value": rsi_v,
            "length": 14,
            "state": (
                None
                if rsi_v is None
                else "overbought"
                if rsi_v >= 70
                else "oversold"
                if rsi_v <= 30
                else "bullish"
                if rsi_v > 55
                else "bearish"
                if rsi_v < 45
                else "neutral"
            ),
            "series": [_f(v) for v in rsi14],
        },
        "macd": {
            "macd": macd_v,
            "signal": sig_v,
            "hist": hist_v,
            "state": "bullish" if (macd_v or 0) > (sig_v or 0) else "bearish",
            "event": macd_cross,
            "series": {
                "macd": [_f(v) for v in macd_parts["macd"]],
                "signal": [_f(v) for v in macd_parts["signal"]],
                "hist": [_f(v) for v in macd_parts["hist"]],
            },
        },
        "moving_averages": ma_snapshot,
        "structure": {
            "stacked_bullish": stacked_bull,
            "stacked_bearish": stacked_bear,
            "cross_event": golden_cross,
        },
        "bollinger": {
            "upper": _last(bb["upper"]),
            "mid": _last(bb["mid"]),
            "lower": _last(bb["lower"]),
            "percent_b": (
                _f((spot - _last(bb["lower"])) / (_last(bb["upper"]) - _last(bb["lower"])) * 100.0)
                if _last(bb["upper"]) and _last(bb["lower"]) and _last(bb["upper"]) != _last(bb["lower"])
                else None
            ),
        },
        "volatility": {
            "atr14": atr_v,
            "atr_pct": _f(atr_v / spot * 100.0) if atr_v else None,
            "realised_vol_20d": rv20,
            "expected_2w_move_pct": _f(atr_v / spot * 100.0 * np.sqrt(10)) if atr_v else None,
            **hv,
        },
        "swing_points": swing,
        "fibonacci": fib,
        "support_resistance": sr_levels,
        # The whole window is sent, not a fixed 120 bars, so the client can switch
        # timeframe without a round trip. Moving averages are computed on the full
        # history first, so a 1-month view still shows a correct 200-day average
        # rather than one restarted from the slice.
        "price_series": {
            "bars": int(len(df)),
            "dates": [str(idx.date()) for idx in df.index],
            "close": [_f(v) for v in close],
            "open": [_f(v) for v in df["Open"]],
            "high": [_f(v) for v in df["High"]],
            "low": [_f(v) for v in df["Low"]],
            "volume": [_f(v) for v in df["Volume"]],
            "sma20": [_f(v) for v in mas["sma20"]],
            "sma50": [_f(v) for v in mas["sma50"]],
            "sma200": [_f(v) for v in mas["sma200"]],
            # All three EMAs, not just the 21. The stack reading (9/21/50) was
            # already computed and shown as a tile, but only the 21 was ever sent
            # as a series — so the chart could not draw the thing the tile was
            # describing.
            "ema9": [_f(v) for v in mas["ema9"]],
            "ema21": [_f(v) for v in mas["ema21"]],
            "ema50": [_f(v) for v in mas["ema50"]],
        },
    }
