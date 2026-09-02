"""Long-term holding analysis and index-level regime.

Separate pane from the swing view on purpose: the questions are different.
Swing asks "is this the week?"; this asks "is this a business and a price I
want to own for years, and is the index backdrop in a bull or bear phase?"
Weekly/monthly bars, drawdown, CAGR, risk-adjusted return, valuation, and
accumulation zones — not RSI(14) on daily bars.
"""

from __future__ import annotations

from .. import legal as legal_mod

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from .series_stats import _f
from .technicals import rsi, sma
from . import fundamentals, valuation

log = logging.getLogger(__name__)

TRADING_DAYS = 252

INDICES: List[Dict[str, str]] = [
    {"symbol": "^GSPC", "name": "S&P 500", "note": "US large cap"},
    {"symbol": "^NDX", "name": "Nasdaq 100", "note": "US large-cap growth"},
    {"symbol": "^DJI", "name": "Dow Jones", "note": "US mega-cap value tilt"},
    {"symbol": "^RUT", "name": "Russell 2000", "note": "US small cap"},
    {"symbol": "^GSPC", "name": "S&P 500", "note": "US large cap"},
]

# Deduplicated index list plus the breadth/leadership proxies.
INDEX_UNIVERSE = ["^GSPC", "^NDX", "^DJI", "^RUT", "EFA", "EEM", "SPY", "QQQ"]

INDEX_META = {
    "^GSPC": {"name": "S&P 500", "note": "US large cap"},
    "^NDX": {"name": "Nasdaq 100", "note": "US large-cap growth"},
    "^DJI": {"name": "Dow Jones", "note": "US mega-cap, value tilt"},
    "^RUT": {"name": "Russell 2000", "note": "US small cap"},
    "EFA": {"name": "Developed ex-US", "note": "international developed"},
    "EEM": {"name": "Emerging Markets", "note": "EM equity"},
}


# ---------------------------------------------------------------- helpers


def _weekly(df: pd.DataFrame) -> pd.DataFrame:
    """Resample dailies to weekly bars — the right lens for multi-year trend."""
    if df is None or df.empty:
        return pd.DataFrame()
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last"}
    if "Volume" in df:
        agg["Volume"] = "sum"
    return df.resample("W-FRI").agg(agg).dropna(subset=["Close"])


def _cagr(close: pd.Series, years: float) -> Optional[float]:
    bars = int(years * TRADING_DAYS)
    if len(close) <= bars:
        return None
    start, end = close.iloc[-1 - bars], close.iloc[-1]
    if start <= 0:
        return None
    return _f(((end / start) ** (1.0 / years) - 1.0) * 100.0, 2)


def _drawdown_profile(close: pd.Series) -> Dict[str, Any]:
    running_max = close.cummax()
    dd = (close / running_max - 1.0) * 100.0
    trough_idx = dd.idxmin()
    return {
        "current_drawdown_pct": _f(dd.iloc[-1], 2),
        "max_drawdown_pct": _f(dd.min(), 2),
        "max_drawdown_date": str(trough_idx.date()) if trough_idx is not None else None,
        "all_time_high": _f(running_max.iloc[-1], 4),
        "ath_date": str(close.idxmax().date()),
        "series": [_f(v, 2) for v in dd.tail(260)],
        "dates": [str(i.date()) for i in dd.tail(260).index],
    }


def _risk_stats(close: pd.Series, bench_close: Optional[pd.Series]) -> Dict[str, Any]:
    returns = close.pct_change().dropna()
    if returns.empty:
        return {}

    vol = float(returns.std(ddof=0) * np.sqrt(TRADING_DAYS) * 100.0)
    downside = returns[returns < 0]
    downside_vol = (
        float(downside.std(ddof=0) * np.sqrt(TRADING_DAYS) * 100.0) if not downside.empty else None
    )
    annual_return = None
    if len(close) > TRADING_DAYS:
        annual_return = float((close.iloc[-1] / close.iloc[-1 - TRADING_DAYS] - 1.0) * 100.0)

    beta = corr = None
    if bench_close is not None:
        joined = pd.concat(
            [close.pct_change().rename("a"), bench_close.pct_change().rename("b")], axis=1
        ).dropna()
        if len(joined) > 60:
            var_b = joined["b"].var(ddof=0)
            if var_b and var_b > 0:
                beta = _f(joined["a"].cov(joined["b"]) / var_b, 3)
            corr = _f(joined["a"].corr(joined["b"]), 3)

    # Risk-free is left at zero deliberately — this is a relative screen, not a
    # performance report, and hard-coding a stale T-bill rate would be worse.
    sharpe = _f(annual_return / vol, 2) if annual_return is not None and vol > 0 else None
    sortino = (
        _f(annual_return / downside_vol, 2)
        if annual_return is not None and downside_vol and downside_vol > 0
        else None
    )

    return {
        "annualised_vol_pct": _f(vol, 2),
        "downside_vol_pct": _f(downside_vol, 2) if downside_vol else None,
        "trailing_1y_return_pct": _f(annual_return, 2),
        "sharpe_proxy": sharpe,
        "sortino_proxy": sortino,
        "beta_vs_spy": beta,
        "correlation_vs_spy": corr,
        "best_day_pct": _f(returns.max() * 100.0, 2),
        "worst_day_pct": _f(returns.min() * 100.0, 2),
        "pct_positive_days": _f((returns > 0).mean() * 100.0, 1),
    }


def _long_trend(weekly: pd.DataFrame) -> Dict[str, Any]:
    """Weekly-bar trend structure. The 200-week average is the line that has
    historically separated secular bull phases from bear phases."""
    if weekly.empty or len(weekly) < 60:
        return {"phase": "insufficient history"}

    close = weekly["Close"]
    last = float(close.iloc[-1])
    w30 = sma(close, 30)
    w40 = sma(close, 40)
    w200 = sma(close, 200) if len(close) >= 200 else pd.Series(dtype=float)
    weekly_rsi = rsi(close, 14)

    def rel(series: pd.Series) -> Optional[float]:
        clean = series.dropna()
        if clean.empty or clean.iloc[-1] == 0:
            return None
        return _f((last / clean.iloc[-1] - 1.0) * 100.0, 2)

    above_40w = None
    if not w40.dropna().empty:
        above_40w = bool(last > w40.dropna().iloc[-1])
    above_200w = None
    if not w200.dropna().empty:
        above_200w = bool(last > w200.dropna().iloc[-1])

    slope_40w = None
    clean40 = w40.dropna()
    if len(clean40) > 13:
        prior = clean40.iloc[-14]
        if prior:
            slope_40w = _f((clean40.iloc[-1] / prior - 1.0) * 100.0, 2)

    if above_200w and above_40w and (slope_40w or 0) > 0:
        phase = "secular uptrend"
        guidance = "Structurally bullish. Pullbacks toward the 40-week average are accumulation, not exits."
    elif above_200w and not above_40w:
        phase = "uptrend, correcting"
        guidance = "Long-term trend intact but under its 40-week line — a normal correction inside a bull phase. Stagger entries."
    elif above_200w is False and above_40w:
        phase = "attempted bottom"
        guidance = "Below the 200-week but reclaiming the 40-week — early recovery signal, not confirmation. Start small."
    elif above_200w is False:
        phase = "secular downtrend"
        guidance = "Below both long-term averages. Capital preservation over accumulation; wait for the 40-week reclaim."
    else:
        phase = "neutral"
        guidance = "No clear long-term trend. Position size for uncertainty."

    return {
        "phase": phase,
        "guidance": guidance,
        "vs_30w_sma": rel(w30),
        "vs_40w_sma": rel(w40),
        "vs_200w_sma": rel(w200) if not w200.dropna().empty else None,
        "above_40w_sma": above_40w,
        "above_200w_sma": above_200w,
        "sma_200w": _f(w200.dropna().iloc[-1], 4) if not w200.dropna().empty else None,
        "sma_40w": _f(w40.dropna().iloc[-1], 4) if not w40.dropna().empty else None,
        "slope_40w_pct_3m": slope_40w,
        "weekly_rsi": _f(weekly_rsi.dropna().iloc[-1], 2) if not weekly_rsi.dropna().empty else None,
        "weekly_closes": [_f(v, 4) for v in close.tail(260)],
        "weekly_dates": [str(idx.date()) for idx in close.tail(260).index],
        # Full weekly OHLCV, not just closes. _weekly() already aggregates open,
        # high, low and volume and the old payload threw them away — which is why
        # this chart could only ever draw a line. Sent whole rather than tailed so
        # the client can offer its own timeframes and roll up to monthly without a
        # second request.
        "series": {
            "dates": [str(idx.date()) for idx in weekly.index],
            "open": [_f(v, 4) for v in weekly["Open"]],
            "high": [_f(v, 4) for v in weekly["High"]],
            "low": [_f(v, 4) for v in weekly["Low"]],
            "close": [_f(v, 4) for v in weekly["Close"]],
            "volume": ([_f(v, 0) for v in weekly["Volume"]]
                       if "Volume" in weekly else []),
            "bars": int(len(weekly)),
        },
    }


def _valuation_read(quote: Dict[str, Any]) -> Dict[str, Any]:
    """Plain-language valuation read. Deliberately conservative: absolute
    multiples are only a rough guide without sector context, and this says so
    rather than pretending to a precise fair value."""
    flags: List[str] = []
    fwd = quote.get("forward_pe")
    trailing = quote.get("trailing_pe")
    pb = quote.get("price_to_book")
    peg = quote.get("peg_ratio")
    margin = quote.get("profit_margin")
    rev_growth = quote.get("revenue_growth")

    if fwd is not None:
        if fwd < 0:
            flags.append("Negative forward earnings — unprofitable on consensus estimates.")
        elif fwd < 15:
            flags.append("Forward P/E {:.1f} — cheap on an absolute basis.".format(fwd))
        elif fwd < 25:
            flags.append("Forward P/E {:.1f} — reasonable.".format(fwd))
        elif fwd < 40:
            flags.append("Forward P/E {:.1f} — priced for growth; execution risk is real.".format(fwd))
        else:
            flags.append("Forward P/E {:.1f} — expensive; leaves no room for disappointment.".format(fwd))

    if trailing is not None and fwd is not None and trailing > 0 and fwd > 0:
        if fwd < trailing * 0.85:
            flags.append("Forward multiple well below trailing — earnings expected to grow.")
        elif fwd > trailing * 1.15:
            flags.append("Forward multiple above trailing — earnings expected to shrink.")

    if peg is not None and 0 < peg < 1.2:
        flags.append("PEG {:.2f} — growth is not fully priced in.".format(peg))
    elif peg is not None and peg > 3:
        flags.append("PEG {:.2f} — paying a lot per unit of growth.".format(peg))

    if pb is not None and pb > 0:
        if pb < 1.5:
            flags.append("Price/book {:.2f} — asset-backed valuation support.".format(pb))
        elif pb > 10:
            flags.append("Price/book {:.1f} — valuation rests entirely on future earnings.".format(pb))

    if margin is not None:
        flags.append("Net margin {:.1f}%.".format(margin * 100))
    if rev_growth is not None:
        flags.append("Revenue growth {:.1f}% y/y.".format(rev_growth * 100))

    if not flags:
        flags.append("Valuation metrics unavailable — typical for ETFs and index products.")

    return {
        "forward_pe": fwd,
        "trailing_pe": trailing,
        "price_to_book": pb,
        "peg_ratio": peg,
        "profit_margin": margin,
        "revenue_growth": rev_growth,
        "earnings_growth": quote.get("earnings_growth"),
        "dividend_yield": quote.get("dividend_yield"),
        "market_cap": quote.get("market_cap"),
        "notes": flags,
        "caveat": "Absolute multiples mean little without sector comparables — treat as a screen, not a verdict.",
    }


def _accumulation_zones(daily: pd.Series, weekly_trend: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Price levels worth scaling into, drawn from long-term structure."""
    zones: List[Dict[str, Any]] = []
    last = float(daily.iloc[-1])

    for key, label in (("sma_40w", "40-week average"), ("sma_200w", "200-week average")):
        level = weekly_trend.get(key)
        if level:
            zones.append(
                {
                    "label": label,
                    "price": level,
                    "distance_pct": _f((level / last - 1.0) * 100.0, 2),
                    "kind": "support" if level < last else "reclaim level",
                }
            )

    lookback = daily.tail(756) if len(daily) > 756 else daily
    hi, lo = float(lookback.max()), float(lookback.min())
    if hi > lo:
        for ratio, name in ((0.382, "38.2%"), (0.5, "50%"), (0.618, "61.8%")):
            level = hi - (hi - lo) * ratio
            zones.append(
                {
                    "label": "{} retracement of the 3-year range".format(name),
                    "price": _f(level, 4),
                    "distance_pct": _f((level / last - 1.0) * 100.0, 2),
                    "kind": "support" if level < last else "resistance",
                }
            )

    zones.sort(key=lambda z: -(z["price"] or 0))
    return zones


# ------------------------------------------------------------- entry points


def _data_quality(close: pd.Series) -> Dict[str, Any]:
    """Flag histories too short or too distorted for long-term metrics.

    Recent IPOs, spinoffs, and post-reverse-split tickers produce headline
    numbers that are arithmetically correct and analytically meaningless — a
    2,000% "one-year return" off a when-issued stub price will otherwise sail
    into a conviction score as if it were a track record.
    """
    years = round(len(close) / TRADING_DAYS, 2)
    warnings: List[str] = []
    reliable = True

    if years < 1.2:
        warnings.append(
            "Only {:.1f} years of price history — there is no long-term record to assess yet.".format(years)
        )
        reliable = False
    elif years < 3.2:
        warnings.append(
            "Only {:.1f} years of price history — likely a recent IPO, spinoff, or ticker change. "
            "Multi-year metrics are unavailable or unreliable.".format(years)
        )
        reliable = False

    if len(close) > TRADING_DAYS:
        one_year = close.iloc[-1] / close.iloc[-1 - TRADING_DAYS] - 1.0
        if one_year > 3.0:
            warnings.append(
                "Trailing one-year return of {:.0f}% almost always indicates a corporate action, "
                "a listing change, or a stub starting price rather than a repeatable return. "
                "Verify the price history before trusting any figure derived from it.".format(one_year * 100)
            )
            reliable = False

    return {"history_years": years, "reliable": reliable, "warnings": warnings}


def _revenue_multiple(provider, ticker: str, quote: Dict[str, Any]) -> Dict[str, Any]:
    """Revenue against the multiple the market paid, per fiscal year."""
    try:
        fin = fundamentals.analyse_financials(provider.financials(ticker))
        hist = _valuation_history(provider, ticker, quote)
        return valuation.revenue_and_multiple(fin, hist)
    except Exception as exc:                     # noqa: BLE001
        log.warning("revenue/multiple unavailable for %s: %s", ticker, exc)
        return {"available": False, "reason": str(exc)[:120]}


def _valuation_history(provider, ticker: str, quote: Dict[str, Any]) -> Dict[str, Any]:
    """The five-year multiple band, or a reason it is unavailable.

    Wrapped because it needs both the annual financials and six years of dailies,
    and neither is guaranteed: an ETF has no EPS at all, and a recent listing has
    no history. A missing band must not cost the reader the rest of the tab.
    """
    try:
        fin = (fundamentals.analyse(provider, ticker, quote) or {}).get("financials") or {}
        return valuation.history_band(provider, ticker, fin, quote.get("trailing_pe"))
    except Exception as exc:
        return {"available": False, "reason": "could not be computed: {}".format(exc)}

def analyse_holding(provider, ticker: str) -> Dict[str, Any]:
    """Long-horizon read on a single ticker."""
    daily = provider.history(ticker, period="12y", interval="1d")
    if daily is None or daily.empty:
        return {"error": "no price history for {}".format(ticker)}

    bench = provider.history("SPY", period="12y", interval="1d")
    quote = provider.quote(ticker)
    close = daily["Close"].dropna()
    weekly = _weekly(daily)
    trend = _long_trend(weekly)

    horizons = {
        "return_1y_pct": _f((close.iloc[-1] / close.iloc[-1 - TRADING_DAYS] - 1.0) * 100.0, 2)
        if len(close) > TRADING_DAYS
        else None,
        "cagr_3y_pct": _cagr(close, 3),
        "cagr_5y_pct": _cagr(close, 5),
        "cagr_10y_pct": _cagr(close, 10),
    }

    bench_cagr_5y = _cagr(bench["Close"].dropna(), 5) if bench is not None and not bench.empty else None
    excess_5y = None
    if horizons["cagr_5y_pct"] is not None and bench_cagr_5y is not None:
        excess_5y = _f(horizons["cagr_5y_pct"] - bench_cagr_5y, 2)

    drawdown = _drawdown_profile(close)
    risk = _risk_stats(close, bench["Close"].dropna() if bench is not None and not bench.empty else None)
    valuation = _valuation_read(quote)
    zones = _accumulation_zones(close, trend)
    quality = _data_quality(close)

    # ------------------------------------------------- conviction scoring
    #
    # Every adjustment is recorded, not just summed, so the panel can show the
    # arithmetic. A score with no visible derivation invites more trust than a
    # weighted heuristic deserves.
    score = 0.0
    reasons: List[str] = []
    factors: List[Dict[str, Any]] = []

    def award(points: float, label: str, detail: str, kind: str) -> None:
        nonlocal score
        score += points
        factors.append({
            "label": label, "points": round(points, 1), "detail": detail, "kind": kind,
        })
        reasons.append(detail)

    if trend.get("above_200w_sma"):
        award(25, "200-week trend", "Above the 200-week average — secular trend is up.", "trend")
    elif trend.get("above_200w_sma") is False:
        award(-25, "200-week trend", "Below the 200-week average — secular trend is down.", "trend")

    if trend.get("above_40w_sma"):
        award(12, "40-week trend", "Above the 40-week average — intermediate trend supportive.", "trend")
    else:
        award(-8, "40-week trend", "Below the 40-week average — intermediate weakness.", "trend")

    if excess_5y is not None and quality["reliable"]:
        if excess_5y > 3:
            award(15, "5-year vs SPY", "Outperformed SPY by {:.1f}%/yr over 5 years.".format(excess_5y), "relative strength")
        elif excess_5y < -3:
            award(-15, "5-year vs SPY", "Underperformed SPY by {:.1f}%/yr over 5 years.".format(abs(excess_5y)), "relative strength")

    sharpe = risk.get("sharpe_proxy")
    if sharpe is not None and quality["reliable"]:
        if sharpe > 1.0:
            award(10, "Return per unit of risk", "Return/vol ratio {:.2f} over the past year — well compensated.".format(sharpe), "risk")
        elif sharpe < 0:
            award(-10, "Return per unit of risk", "Negative trailing return with full volatility — poorly compensated.", "risk")

    fwd = valuation.get("forward_pe")
    if fwd is not None and 0 < fwd < 20:
        award(8, "Valuation", "Forward P/E of {:.1f} leaves room for multiple expansion.".format(fwd), "valuation")
    elif fwd is not None and fwd > 45:
        award(-8, "Valuation", "Forward P/E of {:.1f} raises the bar for future returns.".format(fwd), "valuation")
    elif fwd is not None:
        # Recorded at zero on purpose: "the model looked and shrugged" is more
        # honest than the factor silently not appearing.
        factors.append({
            "label": "Valuation", "points": 0.0, "kind": "valuation",
            "detail": "Forward P/E of {:.1f} is between the 20 and 45 thresholds — no adjustment either way.".format(fwd),
        })

    current_dd = drawdown.get("current_drawdown_pct")
    if current_dd is not None and current_dd < -25 and trend.get("above_200w_sma"):
        award(10, "Drawdown opportunity",
              "{:.0f}% below the all-time high while the secular trend holds — historically a favorable accumulation window.".format(abs(current_dd)),
              "timing")

    div = quote.get("dividend_yield")
    if div is not None and div > 0.025:
        award(5, "Dividend", "{:.2f}% dividend yield contributes to total return.".format(div * 100), "income")

    score = float(np.clip(score, -100, 100))

    # A thin or distorted history can't support a confident verdict, whatever the
    # arithmetic says — cap the score rather than letting it read as a track record.
    if not quality["reliable"]:
        score = float(np.clip(score, -25, 25))
        reasons.append(
            "Conviction capped: {:.1f} years of usable history is not enough for a long-term verdict.".format(
                quality["history_years"]
            )
        )

    if score >= 40:
        conviction, plan = "high", "Suitable as a core long-term holding. Scale in on weakness toward the listed zones."
    elif score >= 12:
        conviction, plan = "moderate", "Reasonable holding. Build the position gradually rather than all at once."
    elif score <= -40:
        conviction, plan = "low", "Long-term picture is unfavourable. Avoid new capital until the trend repairs."
    elif score <= -12:
        conviction, plan = "cautious", "Mixed to negative. Any exposure should be small and dated to a specific catalyst."
    else:
        conviction, plan = "neutral", "No long-term edge either way. Dollar-cost averaging is the honest approach here."

    return {
        "ticker": ticker.upper(),
        "name": quote.get("name"),
        "price": quote.get("price") or _f(close.iloc[-1]),
        "conviction": conviction,
        "conviction_score": round(score, 1),
        "conviction_factors": factors,
        "conviction_scale": {
            # Sum of the best case for every factor. The score is not out of 100:
            # printing it against ±100 overstates how close to "perfect" a result is.
            "max_possible": 85,
            "min_possible": -74,
            "thresholds": {"high": 40, "moderate": 15, "cautious": -15, "low": -40},
        },
        "plan": plan,
        "reasons": reasons,
        "data_quality": quality,
        "horizons": horizons,
        "benchmark_cagr_5y_pct": bench_cagr_5y,
        "excess_cagr_5y_pct": excess_5y,
        "long_trend": trend,
        "drawdown": drawdown,
        "risk": risk,
        "valuation": valuation,
        # Where today's multiple sits in this company's own five-year range. Kept
        # separate from `valuation` above, which is a cross-sectional read on
        # absolute levels — the two answer different questions and a name can
        # easily be absolutely expensive but cheap against its own history.
        "valuation_history": _valuation_history(provider, ticker, quote),
        "revenue_multiple": _revenue_multiple(provider, ticker, quote),
        "accumulation_zones": zones,
        "fundamentals": {
            "sector": quote.get("sector"),
            "industry": quote.get("industry"),
            "quote_type": quote.get("quote_type"),
            "analyst_target": quote.get("analyst_target"),
            "recommendation": quote.get("recommendation"),
            "fifty_two_high": quote.get("fifty_two_high"),
            "fifty_two_low": quote.get("fifty_two_low"),
        },
        "disclaimer": legal_mod.AREAS["longterm"],
        "disclaimer_short": legal_mod.SHORT,
    }


def analyse_indices(provider) -> Dict[str, Any]:
    """Index-level long-term regime plus breadth and leadership proxies."""
    frames = provider.batch_history(INDEX_UNIVERSE, period="12y", interval="1d")

    rows: List[Dict[str, Any]] = []
    for symbol, meta in INDEX_META.items():
        frame = frames.get(symbol)
        if frame is None or frame.empty:
            continue
        close = frame["Close"].dropna()
        weekly = _weekly(frame)
        trend = _long_trend(weekly)
        drawdown = _drawdown_profile(close)
        rows.append(
            {
                "symbol": symbol,
                "name": meta["name"],
                "note": meta["note"],
                "last": _f(close.iloc[-1]),
                "return_1y_pct": _f((close.iloc[-1] / close.iloc[-1 - TRADING_DAYS] - 1.0) * 100.0, 2)
                if len(close) > TRADING_DAYS
                else None,
                "cagr_3y_pct": _cagr(close, 3),
                "cagr_5y_pct": _cagr(close, 5),
                "cagr_10y_pct": _cagr(close, 10),
                "phase": trend.get("phase"),
                "guidance": trend.get("guidance"),
                "vs_40w_sma": trend.get("vs_40w_sma"),
                "vs_200w_sma": trend.get("vs_200w_sma"),
                "above_200w_sma": trend.get("above_200w_sma"),
                "weekly_rsi": trend.get("weekly_rsi"),
                "current_drawdown_pct": drawdown.get("current_drawdown_pct"),
                "max_drawdown_pct": drawdown.get("max_drawdown_pct"),
                "weekly_closes": trend.get("weekly_closes"),
                "weekly_dates": trend.get("weekly_dates"),
            }
        )

    spy = frames.get("SPY")

    growth_value: Dict[str, Any] = {}
    qqq = frames.get("QQQ")
    if qqq is not None and spy is not None and not qqq.empty and not spy.empty:
        joined = pd.concat(
            [qqq["Close"].rename("q"), spy["Close"].rename("s")], axis=1
        ).dropna()
        if len(joined) > 70:
            line = joined["q"] / joined["s"]
            chg_3m = _f((line.iloc[-1] / line.iloc[-64] - 1.0) * 100.0, 2)
            if chg_3m is not None and chg_3m > 2:
                gv_note = (
                    "Growth is leading the broad market by {:.1f}% over 3 months — long-duration, "
                    "higher-multiple names are in favor, which typically needs falling or stable "
                    "rates to persist.".format(chg_3m)
                )
            elif chg_3m is not None and chg_3m < -2:
                gv_note = (
                    "Growth is lagging the broad market by {:.1f}% over 3 months — leadership is "
                    "rotating toward value and cyclicals, often a sign rates or margins are the "
                    "market's main worry.".format(abs(chg_3m))
                )
            else:
                gv_note = "Growth and the broad market are moving together — no clear style leadership."
            growth_value = {
                "qqq_spy_ratio": _f(line.iloc[-1], 5),
                "chg_3m_pct": chg_3m,
                "note": gv_note,
                "series": [_f(v, 5) for v in line.tail(260)],
                "dates": [str(i.date()) for i in line.tail(260).index],
            }

    bulls = [r for r in rows if r.get("above_200w_sma")]
    if rows:
        share = len(bulls) / len(rows) * 100.0
        if share >= 80:
            regime = "Global equity regime is broadly bullish — most major indices are in secular uptrends."
        elif share >= 50:
            regime = "Mixed global regime — US and international indices are diverging. Favor the strongest."
        else:
            regime = "Defensive global regime — a majority of major indices sit below their 200-week averages."
    else:
        regime = "Index data unavailable."

    return {
        "indices": rows,
        "regime_summary": regime,
        "growth_vs_market": growth_value,
    }
