"""Optional indicators, computed on request rather than always.

The terminal already carries what it uses to form a view: moving averages, RSI,
MACD, Bollinger, ATR, Fibonacci, support and resistance, dealer gamma. This module
is for the ones a reader may want to add themselves, so it is built as a catalogue
with a uniform shape rather than folded into the main technicals payload — nothing
here is computed unless it is asked for.

Two rules about what went in.

**Only indicators with one agreed definition.** ADX has a Wilder formula that
everyone implements the same way. "Smart money index" has a dozen mutually
incompatible versions, so including one and calling it by that name would be
presenting a choice as a standard.

**Labelled by what it measures, not by what it predicts.** Every entry carries a
`measures` line and, where relevant, a `caveat`. The one thing this module will not
do is tell you an indicator works — the pattern base rates elsewhere in this
terminal are what happens when that gets measured, and mostly it is a coin toss.
VWAP is here because institutions genuinely benchmark executions against it, which
is a fact about how it is used, not a claim that crossing it predicts anything.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pandas as pd

from .technicals import atr, bollinger as bollinger_bands, ema, sma

log = logging.getLogger(__name__)


def _f(value: Any, digits: int = 4) -> Optional[float]:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if out != out or out in (float("inf"), float("-inf")):
        return None
    return round(out, digits)


def _series(values: pd.Series, digits: int = 4) -> List[Optional[float]]:
    return [_f(v, digits) for v in values]


# --------------------------------------------------------------- primitives

def vwap(df: pd.DataFrame, anchor: Optional[str] = None) -> pd.Series:
    """Volume-weighted average price, cumulative from the anchor.

    Typical price rather than close, because VWAP is an execution benchmark and a
    fill can happen anywhere in the bar. Anchored VWAP restarts the accumulation
    at a chosen date, which is the form desks actually use — a VWAP running from
    an earnings gap answers "is the average buyer since the news up or down",
    which a session VWAP on a daily chart cannot.
    """
    typical = (df["High"] + df["Low"] + df["Close"]) / 3.0
    volume = df["Volume"].astype(float) if "Volume" in df else pd.Series(1.0, index=df.index)
    if anchor:
        mask = df.index >= pd.Timestamp(anchor)
        typical, volume = typical[mask], volume[mask]
    cum_vol = volume.cumsum().replace(0.0, np.nan)
    out = (typical * volume).cumsum() / cum_vol
    return out.reindex(df.index)


def adx(df: pd.DataFrame, length: int = 14) -> Dict[str, pd.Series]:
    """Wilder's ADX with the directional indicators.

    Trend STRENGTH, with direction carried separately by +DI and -DI. That
    separation is the reason to have it next to MACD rather than instead of it:
    MACD conflates the two into one signed line, so a weak drift and a strong
    trend can produce the same histogram.
    """
    high, low, close = df["High"], df["Low"], df["Close"]
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
    tr = atr(df, length)
    alpha = 1.0 / length
    plus_di = 100.0 * plus_dm.ewm(alpha=alpha, adjust=False, min_periods=length).mean() / tr
    minus_di = 100.0 * minus_dm.ewm(alpha=alpha, adjust=False, min_periods=length).mean() / tr
    denom = (plus_di + minus_di).replace(0.0, np.nan)
    dx = 100.0 * (plus_di - minus_di).abs() / denom
    return {
        "adx": dx.ewm(alpha=alpha, adjust=False, min_periods=length).mean(),
        "plus_di": plus_di,
        "minus_di": minus_di,
    }


def obv(df: pd.DataFrame) -> pd.Series:
    """On-balance volume: volume signed by the day's direction, accumulated."""
    if "Volume" not in df:
        return pd.Series(dtype=float, index=df.index)
    direction = np.sign(df["Close"].diff().fillna(0.0))
    return (direction * df["Volume"].astype(float)).cumsum()


def keltner(df: pd.DataFrame, length: int = 20,
            mult: float = 2.0) -> Dict[str, pd.Series]:
    """Keltner channel: an EMA with ATR bands.

    Kept alongside Bollinger rather than instead of it because they disagree in a
    useful way. Bollinger's width is standard deviation of the close, so it
    contracts when closes cluster even if the daily ranges are wide; Keltner's is
    ATR, which does not. When one is squeezing and the other is not, that
    difference is the information.
    """
    mid = ema(df["Close"], length)
    band = atr(df, length) * mult
    return {"mid": mid, "upper": mid + band, "lower": mid - band}


def donchian(df: pd.DataFrame, length: int = 20) -> Dict[str, pd.Series]:
    """Rolling highest high and lowest low — the original breakout channel."""
    upper = df["High"].rolling(length, min_periods=length).max()
    lower = df["Low"].rolling(length, min_periods=length).min()
    return {"upper": upper, "lower": lower, "mid": (upper + lower) / 2.0}


def stochastic(df: pd.DataFrame, length: int = 14,
               smooth: int = 3) -> Dict[str, pd.Series]:
    """Where the close sits inside the recent range, and a smoothing of it."""
    low = df["Low"].rolling(length, min_periods=length).min()
    high = df["High"].rolling(length, min_periods=length).max()
    span = (high - low).replace(0.0, np.nan)
    k = 100.0 * (df["Close"] - low) / span
    k_smooth = k.rolling(smooth, min_periods=smooth).mean()
    return {"k": k_smooth, "d": k_smooth.rolling(smooth, min_periods=smooth).mean()}


def money_flow_index(df: pd.DataFrame, length: int = 14) -> pd.Series:
    """RSI computed on money flow rather than price — volume-weighted."""
    if "Volume" not in df:
        return pd.Series(dtype=float, index=df.index)
    typical = (df["High"] + df["Low"] + df["Close"]) / 3.0
    flow = typical * df["Volume"].astype(float)
    direction = typical.diff()
    positive = flow.where(direction > 0, 0.0).rolling(length, min_periods=length).sum()
    negative = flow.where(direction < 0, 0.0).rolling(length, min_periods=length).sum()
    ratio = positive / negative.replace(0.0, np.nan)
    return 100.0 - (100.0 / (1.0 + ratio))


def relative_strength_line(close: pd.Series, bench: pd.Series) -> pd.Series:
    """Price divided by the benchmark, rebased to 100 at the start.

    The line institutions actually watch, and it answers a different question from
    a percentage. A rising RS line through a falling market means the name is
    being accumulated relative to the index — which a price chart alone cannot
    show, because both are falling.
    """
    joined = pd.concat({"a": close, "b": bench}, axis=1).dropna()
    if joined.empty:
        return pd.Series(dtype=float)
    ratio = joined["a"] / joined["b"]
    return (ratio / ratio.iloc[0]) * 100.0


def standard_error_channel(close: pd.Series, length: int = 100,
                           mult: float = 2.0) -> Dict[str, Any]:
    """Least-squares fit over the window, with bands at a multiple of the residual
    standard deviation.

    Returns the fitted line and its bands as per-bar series, not just their latest
    values. That distinction mattered: with only end-point numbers the channel was
    declared a price-axis indicator but had nothing the chart could draw, so it
    rendered as a block of statistics below a chart it was supposed to be drawn on.
    A regression channel you cannot see is the weaker half of a regression channel.

    The series are padded with nulls before the window opens rather than
    extrapolated backwards — the fit describes those bars and no others, and drawing
    it across history it was not fitted to would misrepresent it.
    """
    clean = close.dropna()
    tail = clean.tail(length)
    if len(tail) < max(20, length // 3):
        return {"available": False, "reason": "not enough bars for the window"}
    x = np.arange(len(tail), dtype=float)
    y = tail.to_numpy(dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    fit = slope * x + intercept
    resid = y - fit
    sigma = float(resid.std(ddof=1)) if len(resid) > 1 else 0.0
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - float((resid ** 2).sum()) / ss_tot if ss_tot > 0 else None

    pad = [None] * (len(close) - len(tail))
    def band(offset: float) -> List[Optional[float]]:
        return pad + [_f(v + offset, 2) for v in fit]

    return {
        "available": True,
        "lines": [
            {"name": "Regression upper", "values": band(mult * sigma)},
            {"name": "Regression fit", "values": band(0.0)},
            {"name": "Regression lower", "values": band(-mult * sigma)},
        ],
        "slope_per_bar": _f(slope),
        "slope_pct_per_bar": _f(slope / y.mean() * 100.0 if y.mean() else None),
        "r_squared": _f(r2, 3),
        "mid": _f(fit[-1], 2),
        "upper": _f(fit[-1] + mult * sigma, 2),
        "lower": _f(fit[-1] - mult * sigma, 2),
        "bars": len(tail),
        "sigma": _f(sigma, 3),
    }


# ----------------------------------------------------------------- catalogue

CATALOGUE: List[Dict[str, Any]] = [
    {"id": "vwap", "name": "Anchored VWAP", "pane": "price", "group": "Execution",
     "represents": ("Every share traded since the anchor date, averaged by how much volume went through at each price. Not a moving average of closes — a moving average of transactions."),
     "why": ("It is the number a desk is graded against. An institution filling a large order over days is measured on whether it beat VWAP, so the level is where a lot of real money defines success or failure. Price above it means the average buyer since the anchor is in profit; below it means they are not, and that is a fact about positioning rather than a prediction about direction."),
     "measures": "The volume-weighted average price paid since the anchor date.",
     "caveat": "An execution benchmark, not a signal. Desks are measured against "
               "it, which is why the level attracts attention — that is a fact "
               "about behaviour, not evidence that crossing it predicts anything."},
    {"id": "bollinger", "name": "Bollinger bands", "pane": "price", "group": "Volatility",
     "represents": ("A 20-day average with bands two standard deviations of the closing price either side. The band distance IS the recent volatility, restated in dollars."),
     "why": ("The width answers a question price alone cannot: is this quiet or loud by its own standards? Volatility clusters — quiet periods tend to be followed by quiet periods until they are not — so a band width at a historic narrow tells you a move, in either direction, will look large relative to what came before. It says nothing about which direction."),
     "measures": "A 20-day average with bands at 2 standard deviations of the close.",
     "caveat": "The width is the whole content — the bands are a volatility "
               "measure wearing the costume of support and resistance. Price "
               "spends about 5% of its time outside them by construction, so a "
               "touch is not a signal; a band that has contracted to a historic "
               "narrow is the observation worth having."},
    {"id": "keltner", "name": "Keltner channel", "pane": "price", "group": "Volatility",
     "represents": ("The same idea as Bollinger with a different ruler: an EMA with bands at two average true ranges, so the width is built from each bar's full high-to-low travel rather than from where it closed."),
     "why": ("Worth having precisely because it disagrees with Bollinger. Closes clustering inside wide daily ranges squeeze Bollinger and not Keltner; the reverse happens when bars are narrow but drift. When one contracts and the other does not, the gap tells you whether the quiet is in the closes or in the whole session."),
     "measures": "An EMA with bands at 2x ATR.",
     "caveat": ("The bands are a multiple of average range, so one violent session widens them for weeks afterwards and the channel keeps describing a volatility that has already passed. Price outside a band is not a signal either — it says the move is large relative to recent range, which is what a large move is.")},
    {"id": "donchian", "name": "Donchian channel", "pane": "price", "group": "Volatility",
     "represents": ("The highest high and the lowest low of the last 20 sessions, drawn as a channel. The oldest systematic trend rule there is."),
     "why": ("It makes the definition of a breakout explicit rather than a judgement. Price at the upper line is, by construction, at a 20-day high — no interpretation required. The channel also shows how much room the recent range has given you, which is what a stop outside it would have to respect."),
     "measures": "The highest high and lowest low of the last 20 sessions.",
     "caveat": ("The channel is defined entirely by where price has already been, so the breakout level exists because of the last 20 sessions and for no other reason. It also widens after a violent move, which is when it gives the least useful stop.")},
    {"id": "sec", "name": "Regression channel", "pane": "price", "group": "Trend",
     "represents": ("A least-squares straight line through the window, with bands at two standard errors of the residuals. The line is the trend the data itself implies, not one drawn by eye."),
     "why": ("The R-squared is the significant part and the reason to prefer this to a hand-drawn trendline. It states what share of the movement the straight line actually explains. A channel through noise looks identical to a channel through a trend until you see that the line accounts for 15% of the variance — at which point the channel is decoration."),
     "measures": "A least-squares fit over the window with bands at 2 standard "
                 "errors, reported with its slope and R².",
     "caveat": "The R² is the point. A channel drawn through noise looks the "
               "same as one drawn through a trend until you see how little of the "
               "variance the line explains."},
    {"id": "adx", "name": "ADX and DI", "pane": "own", "group": "Trend",
     "represents": ("Wilder's measure of how ORDERLY the movement is, on a 0-100 scale, with direction carried separately by +DI and -DI. A market can score high on ADX while falling."),
     "why": ("It answers the question every other trend tool assumes: is there a trend here at all? Below roughly 20 the market is ranging, and tools built on trend-following — moving-average crosses, breakout rules — are being asked to work in the conditions they fail in. MACD cannot tell you this because it folds strength and direction into one signed line."),
     "measures": "Trend strength, with direction carried separately by +DI and -DI.",
     "caveat": ("Lagging by construction — a smoothed average of smoothed values — so it confirms a trend well after the trend began and stays elevated after one ends. On its own it says nothing about direction: a hard sell-off and a strong rally read the same.")},
    {"id": "stochastic", "name": "Stochastic", "pane": "own", "group": "Momentum",
     "represents": ("Where the close sits inside the last 14 sessions' high-low range, as a percentage. At 100 it closed at the top of the range; at 0, the bottom."),
     "why": ("It is a position-in-range reading, not a momentum reading, and that distinction is where most misuse starts. In a strong trend it pins near an extreme for weeks — 'overbought' at 90 during a sustained advance has been a bad reason to sell far more often than a good one. It is most informative in a range, which is exactly when ADX is low."),
     "measures": "Where the close sits inside the last 14 sessions' range.",
     "caveat": ("In a sustained trend it pins near an extreme for weeks, so \u201coverbought\u201d here has been a bad reason to sell far more often than a good one. It reads position in a range, and a range is what a trending market does not have.")},
    {"id": "obv", "name": "On-balance volume", "pane": "own", "group": "Flow",
     "represents": ("A running total of volume, added on up days and subtracted on down days. The level is arbitrary; only its direction carries meaning."),
     "why": ("It is a crude attempt at the question price cannot answer: is the move being paid for? The case people watch for is divergence — price making highs while the line does not, implying the advance is happening on lighter participation. Treat it as a description of where volume went, not as a leading signal."),
     "measures": "Volume signed by the day's direction, accumulated.",
     "caveat": "Signs the whole day's volume by the close-to-close direction, so a "
               "session that round-tripped counts as fully one-sided."},
    {"id": "mfi", "name": "Money flow index", "pane": "own", "group": "Flow",
     "represents": ("RSI computed on price times volume rather than price alone, bounded 0-100."),
     "why": ("It is the volume-weighted version of an overbought reading, so a stretched value backed by heavy trade reads differently from the same number on a thin drift. Same caution as the stochastic: in a real trend it can sit above 80 for a long time, and 'extreme' is not 'about to turn'."),
     "measures": "RSI computed on price times volume rather than price alone.",
     "caveat": ("Bounded 0-100, so like every oscillator it can sit at an extreme for as long as the trend lasts. Volume weighting makes the reading better founded; it does not make an extreme a turning point.")},
    {"id": "rs", "name": "Relative strength line", "pane": "own", "group": "Trend",
     "represents": ("This name's price divided by SPY, rebased to 100 at the start of the window. Rising means it is outperforming the index; falling means it is lagging — regardless of whether either is going up."),
     "why": ("It separates the company from the market, which a price chart cannot. In a selloff everything falls and the price chart tells you nothing about relative demand; a rising RS line through that selloff says money is rotating in. It is the line institutional screens are built on for exactly that reason."),
     "measures": "Price divided by SPY, rebased to 100.",
     "caveat": ("It is a ratio, so it rises whenever this name falls more slowly than the index — outperformance can mean losing less money. It says nothing about absolute return, and a rising line through a bear market has still cost you.")},
]

CATALOGUE_BY_ID = {row["id"]: row for row in CATALOGUE}


def compute(df: pd.DataFrame, ids: List[str], bench: Optional[pd.Series] = None,
            anchor: Optional[str] = None) -> Dict[str, Any]:
    """Compute the requested indicators over `df`, newest bar last.

    Unknown ids are reported rather than ignored: a typo that silently returns
    nothing looks identical to an indicator that had no data.
    """
    if df is None or df.empty:
        return {"available": False, "reason": "no price history"}

    out: Dict[str, Any] = {}
    unknown: List[str] = []
    for key in ids or []:
        if key not in CATALOGUE_BY_ID:
            unknown.append(key)
            continue
        try:
            result = _one(df, key, bench=bench, anchor=anchor)
            if result.get("available"):
                # Never let a failure to describe the value cost the value itself.
                try:
                    result["reading"] = _reading(key, df, result)
                except Exception as exc:                        # noqa: BLE001
                    log.info("indicators: reading for %s failed: %s", key, exc)
                    result["reading"] = None
            out[key] = result
        except Exception as exc:                                # noqa: BLE001
            log.warning("indicators: %s failed: %s", key, exc)
            out[key] = {"available": False, "reason": str(exc)[:120]}

    return {
        "available": True,
        "dates": [str(i.date()) for i in df.index],
        "indicators": out,
        "unknown": unknown,
        "catalogue": CATALOGUE,
    }


def _reading(key: str, df: pd.DataFrame, payload: Dict[str, Any]) -> Optional[str]:
    """What this indicator's CURRENT value says, in a sentence.

    The static prose explains what an indicator is; this says what it is doing right
    now, which is the part a reader actually wants and the part no fixed text can
    provide. Thresholds are the conventional ones and are named as conventions
    rather than findings — after measuring the pattern base rates elsewhere in this
    terminal, the honest register here is descriptive.
    """
    lines = {l["name"]: l["values"] for l in payload.get("lines") or []}

    def last(name: str) -> Optional[float]:
        vals = [v for v in lines.get(name, []) if v is not None]
        return vals[-1] if vals else None

    spot = _f(df["Close"].iloc[-1], 2) if "Close" in df and len(df) else None

    if key == "vwap":
        v = last("VWAP")
        if v is None or spot is None:
            return None
        gap = (spot / v - 1) * 100
        return ("Price is {:+.1f}% {} the anchored VWAP of {:,.2f}, so the average "
                "share bought since the anchor is {}."
                .format(gap, "above" if gap > 0 else "below", v,
                        "in profit" if gap > 0 else "under water"))

    if key == "bollinger":
        pct = payload.get("width_percentile")
        width = payload.get("last")
        if width is None:
            return None
        if pct is None:
            return "Bands are {:.1f}% wide.".format(width)
        band = ("unusually narrow — quiet by this name's own standards"
                if pct <= 20 else
                "unusually wide — this has been a loud stretch" if pct >= 80 else
                "middling by this name's own standards")
        return ("Bands are {:.1f}% wide, the {:.0f}th percentile of the last year: "
                "{}.".format(width, pct, band))

    if key == "keltner":
        up, low, mid = last("Keltner upper"), last("Keltner lower"), last("Keltner mid")
        if None in (up, low, mid) or spot is None:
            return None
        where = ("above the upper band" if spot > up else
                 "below the lower band" if spot < low else
                 "inside the channel")
        return ("Channel runs {:,.2f} to {:,.2f} and price is {}."
                .format(low, up, where))

    if key == "donchian":
        hi, lo = last("Donchian high"), last("Donchian low")
        if None in (hi, lo) or spot is None or hi <= lo:
            return None
        pos = (spot - lo) / (hi - lo) * 100
        return ("Price sits {:.0f}% of the way up a 20-day range of {:,.2f} to "
                "{:,.2f}.".format(pos, lo, hi))

    if key == "sec":
        fit = payload.get("fit") or {}
        r2, slope = fit.get("r_squared"), fit.get("slope_pct_per_bar")
        if r2 is None or slope is None:
            return None
        quality = ("the line explains very little of the movement, so read the "
                   "channel as decoration" if r2 < 0.3 else
                   "a reasonable fit" if r2 < 0.6 else "a strong fit")
        return ("Sloping {:+.2f}% a session with an R-squared of {:.2f} — {}."
                .format(slope, r2, quality))

    if key == "adx":
        adx_v, plus, minus = last("ADX"), last("+DI"), last("-DI")
        if adx_v is None:
            return None
        state = ("no trend worth the name — trend-following tools are being asked "
                 "to work in the conditions they fail in" if adx_v < 20 else
                 "a trend is forming but not established" if adx_v < 25 else
                 "a trend is in place" if adx_v < 40 else "a strong trend")
        direction = ""
        if plus is not None and minus is not None:
            # Within a point of each other is a tie, not a direction. Reporting
            # "down" off +DI 21.24 against -DI 21.27 asserts a winner that the
            # rounding in the same sentence contradicts.
            if abs(plus - minus) < 1.0:
                direction = (" Neither side is in control (+DI {:.1f} against -DI "
                             "{:.1f}).".format(plus, minus))
            else:
                direction = (" Direction is {} (+DI {:.0f} against -DI {:.0f})."
                             .format("up" if plus > minus else "down", plus, minus))
        return "ADX {:.0f}: {}.{}".format(adx_v, state, direction)

    if key == "stochastic":
        k, d = last("%K"), last("%D")
        if k is None:
            return None
        zone = ("in the upper end of its range" if k >= 80 else
                "in the lower end of its range" if k <= 20 else "mid-range")
        note = (" In a real trend this can stay pinned here for weeks, so it is not "
                "a turn signal." if k >= 80 or k <= 20 else "")
        cross = ""
        if d is not None:
            cross = " %K is {} %D.".format("above" if k > d else "below")
        return "Closing {}, at {:.0f}.{}{}".format(zone, k, cross, note)

    if key == "obv":
        vals = [v for v in lines.get("OBV", []) if v is not None]
        if len(vals) < 25 or "Close" not in df:
            return None
        obv_up = vals[-1] > vals[-21]
        closes = df["Close"].dropna()
        if len(closes) < 21:
            return None
        price_up = float(closes.iloc[-1]) > float(closes.iloc[-21])
        if obv_up == price_up:
            return ("Over the last 20 sessions volume flow and price moved the same "
                    "way ({}), so the move is being paid for."
                    .format("both up" if price_up else "both down"))
        return ("Over the last 20 sessions price went {} while volume flow went {} "
                "— a divergence, which is the case this indicator exists to show. "
                "It describes participation, not a coming reversal."
                .format("up" if price_up else "down", "up" if obv_up else "down"))

    if key == "mfi":
        v = last("MFI")
        if v is None:
            return None
        extreme = v >= 80 or v <= 20
        zone = ("stretched high" if v >= 80 else "stretched low" if v <= 20
                else "mid-range")
        # Only claim an extreme when there is one. The previous version appended
        # "this is an extreme backed by real trade" to a mid-range reading.
        tail = (" Volume-weighted, so this is an extreme backed by real trade "
                "rather than a thin drift." if extreme else
                " Nothing stretched either way.")
        return "Money flow index {:.0f} — {}.{}".format(v, zone, tail)

    if key == "rs":
        vals = [v for v in lines.get("RS vs SPY", []) if v is not None]
        if len(vals) < 25:
            return None
        now, prior = vals[-1], vals[-21]
        return ("Relative strength {:.0f} against a base of 100, and {} over the "
                "last 20 sessions — this name has {} the index."
                .format(now, "rising" if now > prior else "falling",
                        "been outperforming" if now > prior else "been lagging"))
    return None


def _one(df: pd.DataFrame, key: str, bench: Optional[pd.Series],
         anchor: Optional[str]) -> Dict[str, Any]:
    meta = CATALOGUE_BY_ID[key]
    base = {"available": True, "id": key, "name": meta["name"], "pane": meta["pane"],
            "measures": meta["measures"], "caveat": meta.get("caveat"),
            "represents": meta.get("represents"), "why": meta.get("why")}

    if key == "vwap":
        line = vwap(df, anchor=anchor)
        return {**base, "anchor": anchor or str(df.index[0].date()),
                "lines": [{"name": "VWAP", "values": _series(line, 2)}],
                "last": _f(line.dropna().iloc[-1], 2) if line.notna().any() else None}
    if key == "bollinger":
        b = bollinger_bands(df["Close"])
        width = ((b["upper"] - b["lower"]) / b["mid"] * 100.0).dropna()
        return {**base, "lines": [
            {"name": "Bollinger upper", "values": _series(b["upper"], 2)},
            {"name": "Bollinger mid", "values": _series(b["mid"], 2)},
            {"name": "Bollinger lower", "values": _series(b["lower"], 2)}],
            # The width, and where it sits in its own history — the number the
            # bands are actually for. A band touch is common by construction; a
            # band width at its own 5th percentile is not.
            "last": _f(width.iloc[-1], 1) if len(width) else None,
            "width_percentile": (
                _f(float((width <= width.iloc[-1]).mean() * 100.0), 0)
                if len(width) > 60 else None),
        }
    if key == "keltner":
        k = keltner(df)
        return {**base, "lines": [
            {"name": "Keltner upper", "values": _series(k["upper"], 2)},
            {"name": "Keltner mid", "values": _series(k["mid"], 2)},
            {"name": "Keltner lower", "values": _series(k["lower"], 2)}]}
    if key == "donchian":
        d = donchian(df)
        return {**base, "lines": [
            {"name": "Donchian high", "values": _series(d["upper"], 2)},
            {"name": "Donchian low", "values": _series(d["lower"], 2)}]}
    if key == "sec":
        fit = standard_error_channel(df["Close"])
        if not fit.get("available"):
            return {**base, "available": False, "reason": fit.get("reason")}
        lines = fit.pop("lines", [])
        # Both: the lines draw on the price axis, and the fit statistics are what
        # tell you whether the channel means anything. The R-squared is the point.
        return {**base, "lines": lines, "fit": fit}
    if key == "adx":
        a = adx(df)
        last = a["adx"].dropna()
        return {**base, "lines": [
            {"name": "ADX", "values": _series(a["adx"], 2)},
            {"name": "+DI", "values": _series(a["plus_di"], 2)},
            {"name": "-DI", "values": _series(a["minus_di"], 2)}],
            "last": _f(last.iloc[-1], 1) if len(last) else None,
            # Wilder's own threshold, named as his convention rather than a finding.
            "reference": [{"value": 25, "label": "25 — Wilder's trending threshold"}]}
    if key == "stochastic":
        st = stochastic(df)
        return {**base, "lines": [
            {"name": "%K", "values": _series(st["k"], 2)},
            {"name": "%D", "values": _series(st["d"], 2)}],
            "reference": [{"value": 80, "label": "80"}, {"value": 20, "label": "20"}]}
    if key == "obv":
        line = obv(df)
        return {**base, "lines": [{"name": "OBV", "values": _series(line, 0)}]}
    if key == "mfi":
        line = money_flow_index(df)
        return {**base, "lines": [{"name": "MFI", "values": _series(line, 2)}],
                "reference": [{"value": 80, "label": "80"}, {"value": 20, "label": "20"}]}
    if key == "rs":
        if bench is None or bench.empty:
            return {**base, "available": False,
                    "reason": "benchmark history unavailable"}
        line = relative_strength_line(df["Close"], bench).reindex(df.index).ffill()
        return {**base, "lines": [{"name": "RS vs SPY", "values": _series(line, 2)}],
                "reference": [{"value": 100, "label": "100 — in line with SPY"}]}
    raise KeyError(key)
