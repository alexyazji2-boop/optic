"""yfinance adapter.

Free, keyless, ~15-minute delayed. Good enough for swing-timeframe work:
full option chains with IV and open interest, daily/weekly OHLCV, headlines.
Everything is cached briefly so a dashboard refresh doesn't re-hammer Yahoo.
"""

from __future__ import annotations

import math
import threading
import time
import warnings
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

import yfinance as yf  # noqa: E402

from .base import MarketDataProvider
from .common import clean_iv, pick_swing_expiries

_CACHE: Dict[str, Any] = {}

# yfinance is not safe to drive from several threads at once — concurrent
# yf.download calls interfere and silently return frames with most symbols
# missing, which surfaces as half-empty panels rather than an error. Serialising
# network access is cheap because everything below is cached.
_NET_LOCK = threading.RLock()


def _cached(key: str, ttl: float, producer):
    """Tiny TTL memo. Chains move fast, price history doesn't — callers pick."""
    now = time.time()
    hit = _CACHE.get(key)
    if hit is not None and now - hit[0] < ttl:
        return hit[1]

    with _NET_LOCK:
        # Re-check: another thread may have populated the key while we waited,
        # which also collapses duplicate fetches on a cold start.
        hit = _CACHE.get(key)
        if hit is not None and time.time() - hit[0] < ttl:
            return hit[1]
        value = producer()
        _CACHE[key] = (time.time(), value)
        return value


# ------------------------------------------------------------ throttle state
#
# Yahoo rate-limits, and it does so by raising on the *next* call rather than by
# marking any single response. The failure mode that matters: a throttled options
# fetch used to be swallowed into an empty chain, which reads downstream as "this
# stock has no listed options" — a false statement about the security rather than
# a true one about the feed. Scanning ~3,000 symbols makes hitting the limit
# routine, so the distinction has to be recorded rather than inferred.

_THROTTLE: Dict[str, Any] = {"until": 0.0, "hits": 0, "last_seen": None}

# Backoff after a rate-limit error. Yahoo's window is opaque; a minute is long
# enough to clear a burst and short enough not to freeze the whole app.
THROTTLE_BACKOFF_SECONDS = 60.0


def _is_rate_limit(exc: BaseException) -> bool:
    name = type(exc).__name__
    if "RateLimit" in name or "TooManyRequests" in name:
        return True
    text = str(exc).lower()
    return "too many requests" in text or "rate limit" in text or "429" in text


def note_throttle(exc: BaseException) -> None:
    with _NET_LOCK:
        _THROTTLE["until"] = time.time() + THROTTLE_BACKOFF_SECONDS
        _THROTTLE["hits"] = int(_THROTTLE["hits"]) + 1
        _THROTTLE["last_seen"] = datetime.now(timezone.utc).isoformat()


def throttle_state() -> Dict[str, Any]:
    """Whether the upstream feed is currently rate-limiting us."""
    remaining = max(float(_THROTTLE["until"]) - time.time(), 0.0)
    return {
        "throttled": remaining > 0,
        "seconds_remaining": round(remaining, 1),
        "hits": _THROTTLE["hits"],
        "last_seen": _THROTTLE["last_seen"],
    }


def _iso_from_epoch(value: Any) -> Optional[str]:
    """Yahoo's extended-hours timestamps are unix seconds. Kept so the UI can say
    *when* an after-hours price was last struck — a quote from 4:05pm and one from
    7:55pm are very different levels of evidence."""
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def _f(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if not math.isfinite(out) else out


class YFinanceProvider(MarketDataProvider):
    name = "yfinance"

    # cache TTLs in seconds
    TTL_QUOTE = 30
    TTL_CHAIN = 60
    TTL_HISTORY = 300
    TTL_NEWS = 600

    # ------------------------------------------------------------ quotes

    def quote(self, ticker: str) -> Dict[str, Any]:
        def build() -> Dict[str, Any]:
            t = yf.Ticker(ticker)
            info: Dict[str, Any] = {}
            try:
                info = dict(t.info or {})
            except Exception as exc:
                if _is_rate_limit(exc):
                    note_throttle(exc)
                info = {}

            price = _f(info.get("regularMarketPrice"))
            if price is None:
                hist = self.history(ticker, period="5d")
                if not hist.empty:
                    price = _f(hist["Close"].iloc[-1])

            # yfinance 1.x reports dividendYield in percent (1.01 means 1.01%),
            # so it always needs scaling. Getting this wrong silently corrupts
            # every greek in the chain via the carry term, so it's clamped to a
            # plausible range rather than trusted outright.
            raw_yield = _f(info.get("dividendYield"))
            div_yield = None
            if raw_yield is not None and raw_yield >= 0:
                div_yield = raw_yield / 100.0
                if div_yield > 0.20:
                    div_yield = None  # implausible; drop rather than mis-price

            return {
                "ticker": ticker.upper(),
                "name": info.get("longName") or info.get("shortName") or ticker.upper(),
                "price": price,
                "prev_close": _f(info.get("regularMarketPreviousClose")),
                "change": _f(info.get("regularMarketChange")),
                "change_pct": _f(info.get("regularMarketChangePercent")),
                "day_high": _f(info.get("regularMarketDayHigh")),
                "day_low": _f(info.get("regularMarketDayLow")),
                # Extended-hours trade. This is where an earnings reaction first
                # shows up — a company can report after the close and be down 6%
                # before the next session opens — so it can't be left out just
                # because the regular session is over.
                "has_extended_hours": bool(info.get("hasPrePostMarketData")),
                "post_market_price": _f(info.get("postMarketPrice")),
                "post_market_change_pct": _f(info.get("postMarketChangePercent")),
                "post_market_time": _iso_from_epoch(info.get("postMarketTime")),
                "pre_market_price": _f(info.get("preMarketPrice")),
                "pre_market_change_pct": _f(info.get("preMarketChangePercent")),
                "pre_market_time": _iso_from_epoch(info.get("preMarketTime")),
                "volume": _f(info.get("regularMarketVolume")),
                "avg_volume": _f(info.get("averageDailyVolume3Month")),
                "market_cap": _f(info.get("marketCap")),
                "dividend_yield": div_yield,
                "beta": _f(info.get("beta")),
                "trailing_pe": _f(info.get("trailingPE")),
                "forward_pe": _f(info.get("forwardPE")),
                "price_to_book": _f(info.get("priceToBook")),
                "peg_ratio": _f(info.get("pegRatio") or info.get("trailingPegRatio")),
                "profit_margin": _f(info.get("profitMargins")),
                "revenue_growth": _f(info.get("revenueGrowth")),
                "earnings_growth": _f(info.get("earningsGrowth")),
                "fifty_two_high": _f(info.get("fiftyTwoWeekHigh")),
                "fifty_two_low": _f(info.get("fiftyTwoWeekLow")),
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "quote_type": info.get("quoteType"),
                "currency": info.get("currency", "USD"),
                "market_state": info.get("marketState"),
                "exchange": info.get("fullExchangeName") or info.get("exchange"),
                "analyst_target": _f(info.get("targetMeanPrice")),
                "recommendation": info.get("recommendationKey"),
                "short_percent_float": _f(info.get("shortPercentOfFloat")),
                "as_of": datetime.now(timezone.utc).isoformat(),
            }

        return _cached("quote:" + ticker, self.TTL_QUOTE, build)

    def earnings_date(self, ticker: str) -> Optional[str]:
        def build() -> Optional[str]:
            try:
                cal = yf.Ticker(ticker).calendar
            except Exception:
                return None
            if not cal:
                return None
            dates = cal.get("Earnings Date") if isinstance(cal, dict) else None
            if not dates:
                return None
            first = dates[0] if isinstance(dates, (list, tuple)) else dates
            try:
                return str(pd.Timestamp(first).date())
            except Exception:
                return None

        return _cached("earn:" + ticker, 3600, build)

    # ----------------------------------------------------------- history

    def history(self, ticker: str, period: str = "2y", interval: str = "1d") -> pd.DataFrame:
        key = "hist:{}:{}:{}".format(ticker, period, interval)

        def build() -> pd.DataFrame:
            try:
                df = yf.Ticker(ticker).history(
                    period=period, interval=interval, auto_adjust=False
                )
            except Exception:
                return pd.DataFrame()
            if df is None or df.empty:
                return pd.DataFrame()
            df = df.dropna(subset=["Close"])
            return df

        return _cached(key, self.TTL_HISTORY, build)

    def batch_history(
        self, tickers: List[str], period: str = "1y", interval: str = "1d"
    ) -> Dict[str, pd.DataFrame]:
        """One download for many symbols — the difference between a 2s and a 30s
        macro panel."""
        key = "batch:{}:{}:{}".format(",".join(sorted(tickers)), period, interval)

        def build() -> Dict[str, pd.DataFrame]:
            try:
                raw = yf.download(
                    tickers,
                    period=period,
                    interval=interval,
                    group_by="ticker",
                    auto_adjust=False,
                    progress=False,
                    threads=True,
                )
            except Exception as exc:
                if _is_rate_limit(exc):
                    note_throttle(exc)
                raw = None

            out: Dict[str, pd.DataFrame] = {}
            if raw is None or len(raw) == 0:
                return out

            if isinstance(raw.columns, pd.MultiIndex):
                for sym in tickers:
                    if sym in raw.columns.get_level_values(0):
                        frame = raw[sym].dropna(subset=["Close"])
                        if not frame.empty:
                            out[sym] = frame
            elif len(tickers) == 1:
                frame = raw.dropna(subset=["Close"])
                if not frame.empty:
                    out[tickers[0]] = frame
            return out

        return _cached(key, self.TTL_HISTORY, build)

    def intraday_history(self, ticker: str, period: str = "5d", interval: str = "1m") -> pd.DataFrame:
        # Short TTL: this is the one feed on the whole page where a 5-minute-old
        # bar is actually stale, not just "fine for now".
        key = "intraday:{}:{}:{}".format(ticker, period, interval)

        def build() -> pd.DataFrame:
            try:
                df = yf.Ticker(ticker).history(
                    period=period, interval=interval, auto_adjust=False, prepost=False
                )
            except Exception:
                return pd.DataFrame()
            if df is None or df.empty:
                return pd.DataFrame()
            return df.dropna(subset=["Close"])

        return _cached(key, 30, build)

    # ----------------------------------------------------------- options

    def expirations(self, ticker: str) -> List[str]:
        """Expiry dates for a ticker, or [] if it has none listed.

        A rate-limited fetch deliberately does *not* get cached as an empty list.
        Memoizing that would turn a temporary feed problem into a sixty-second
        claim that a stock has no options, which is how a throttled scan ends up
        quietly recording shares-only trades for names that do have chains.
        """
        def build() -> List[str]:
            try:
                return list(yf.Ticker(ticker).options or [])
            except Exception as exc:
                if _is_rate_limit(exc):
                    note_throttle(exc)
                    raise
                return []

        try:
            return _cached("exp:" + ticker, self.TTL_CHAIN, build)
        except Exception:
            return []

    def options_chain(
        self, ticker: str, expiries: Optional[List[str]] = None, max_expiries: int = 4
    ) -> pd.DataFrame:
        """Normalized chain across one or more expiries.

        Swing traders live in the 2-8 week window, so when no expiries are given
        we pick the nearest ones with at least a few days left rather than the
        0-DTE lottery tickets.
        """
        available = self.expirations(ticker)
        if not available:
            return pd.DataFrame()

        if expiries:
            wanted = [e for e in expiries if e in available]
        else:
            wanted = pick_swing_expiries(available, max_expiries)

        if not wanted:
            return pd.DataFrame()

        key = "chain:{}:{}".format(ticker, ",".join(wanted))

        def build() -> pd.DataFrame:
            frames: List[pd.DataFrame] = []
            today = pd.Timestamp.today().normalize()
            t = yf.Ticker(ticker)

            for exp in wanted:
                try:
                    oc = t.option_chain(exp)
                except Exception as exc:
                    if _is_rate_limit(exc):
                        note_throttle(exc)
                    continue
                for side_df, is_call in ((oc.calls, True), (oc.puts, False)):
                    if side_df is None or side_df.empty:
                        continue
                    part = pd.DataFrame(
                        {
                            "contract": side_df.get("contractSymbol"),
                            "strike": side_df["strike"].astype(float),
                            "last": pd.to_numeric(side_df.get("lastPrice"), errors="coerce"),
                            "bid": pd.to_numeric(side_df.get("bid"), errors="coerce"),
                            "ask": pd.to_numeric(side_df.get("ask"), errors="coerce"),
                            "volume": pd.to_numeric(side_df.get("volume"), errors="coerce"),
                            "open_interest": pd.to_numeric(
                                side_df.get("openInterest"), errors="coerce"
                            ),
                            "iv": pd.to_numeric(
                                side_df.get("impliedVolatility"), errors="coerce"
                            ),
                            "in_the_money": side_df.get("inTheMoney"),
                        }
                    )
                    part["is_call"] = is_call
                    part["expiry"] = exp
                    dte = max((pd.Timestamp(exp) - today).days, 0)
                    part["dte"] = dte
                    part["tau"] = max(dte, 0.25) / 365.0
                    frames.append(part)

            if not frames:
                return pd.DataFrame()

            chain = pd.concat(frames, ignore_index=True)
            chain["mid"] = np.where(
                (chain["bid"] > 0) & (chain["ask"] > 0),
                (chain["bid"] + chain["ask"]) / 2.0,
                chain["last"],
            )
            chain["spread_pct"] = np.where(
                chain["mid"] > 0, (chain["ask"] - chain["bid"]) / chain["mid"] * 100.0, np.nan
            )

            chain = clean_iv(chain)
            chain["volume"] = chain["volume"].fillna(0.0)
            chain["open_interest"] = chain["open_interest"].fillna(0.0)
            return chain

        return _cached(key, self.TTL_CHAIN, build)

    # ------------------------------------------------------- fundamentals

    def short_interest(self, ticker: str) -> Dict[str, Any]:
        def build() -> Dict[str, Any]:
            try:
                info = dict(yf.Ticker(ticker).info or {})
            except Exception:
                return {}
            settle = info.get("dateShortInterest")
            settle_date = None
            if settle:
                try:
                    settle_date = str(datetime.fromtimestamp(int(settle), tz=timezone.utc).date())
                except (ValueError, OSError, TypeError):
                    settle_date = None
            pct_float = _f(info.get("shortPercentOfFloat"))
            return {
                "shares_short": _f(info.get("sharesShort")),
                "shares_short_prior": _f(info.get("sharesShortPriorMonth")),
                "short_ratio_days": _f(info.get("shortRatio")),
                "short_percent_float": pct_float,
                "float_shares": _f(info.get("floatShares")),
                "shares_outstanding": _f(info.get("sharesOutstanding")),
                "settlement_date": settle_date,
            }

        return _cached("short:" + ticker, 3600, build)

    def earnings_history(self, ticker: str, limit: int = 10) -> List[Dict[str, Any]]:
        def build() -> List[Dict[str, Any]]:
            try:
                frame = yf.Ticker(ticker).earnings_dates
            except Exception:
                return []
            if frame is None or frame.empty:
                return []
            out: List[Dict[str, Any]] = []
            for stamp, row in frame.iterrows():
                out.append(
                    {
                        "date": str(pd.Timestamp(stamp).date()),
                        "eps_estimate": _f(row.get("EPS Estimate")),
                        "eps_reported": _f(row.get("Reported EPS")),
                        "surprise_pct": _f(row.get("Surprise(%)")),
                    }
                )
            return out[: limit * 2]

        return _cached("earnhist:" + ticker, 3600, build)

    def profile(self, ticker: str) -> Dict[str, Any]:
        """What the company actually does, in its own words.

        Separate from quote() and on a day-long TTL: a business description
        changes essentially never, and it has no business riding the 30-second
        quote cache. ETFs get the same treatment — the summary there describes the
        fund's mandate, which is the equivalent answer to "what is this".
        """

        def build() -> Dict[str, Any]:
            try:
                info = dict(yf.Ticker(ticker).info or {})
            except Exception as exc:
                if _is_rate_limit(exc):
                    note_throttle(exc)
                return {}

            kind = (info.get("quoteType") or "").upper()
            summary = (info.get("longBusinessSummary") or "").strip()
            # An index is not a fund — nobody manages it and there's nothing to
            # buy. Lumping the two together labelled ^VIX as a fund, which is
            # wrong in a way a reader would reasonably act on.
            labels = {"ETF": "ETF", "MUTUALFUND": "fund", "INDEX": "index",
                      "CURRENCY": "currency", "FUTURE": "futures",
                      "CRYPTOCURRENCY": "crypto"}
            return {
                "ticker": ticker.upper(),
                "name": info.get("longName") or info.get("shortName") or ticker.upper(),
                "kind": kind or None,
                "kind_label": labels.get(kind),
                "is_fund": kind in ("ETF", "MUTUALFUND"),
                "is_company": kind == "EQUITY",
                "summary": summary or None,
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                # Fund equivalents of sector/industry.
                "category": info.get("category"),
                "fund_family": info.get("fundFamily"),
                "employees": _f(info.get("fullTimeEmployees")),
                "country": info.get("country"),
                "city": info.get("city"),
                "website": info.get("website"),
            }

        return _cached("profile:" + ticker, 86400, build)

    def fund_meta(self, ticker: str) -> Dict[str, Any]:
        """ETF/fund cost and income figures.

        Kept separate from quote() because these are fund-only fields on a much
        slower clock — an expense ratio changes at most once a year, so this
        caches for a day rather than riding the quote's short TTL.
        """

        def build() -> Dict[str, Any]:
            try:
                info = yf.Ticker(ticker).info or {}
            except Exception:
                return {}
            # yfinance reports both of these as fractions (0.03 = 0.03%, 0.0105 = 1.05%)
            # but the expense field is already in percent units while yield is not.
            expense = info.get("netExpenseRatio")
            if expense is None:
                annual = _f(info.get("annualReportExpenseRatio"))
                expense = annual * 100.0 if annual is not None else None
            raw_yield = _f(info.get("yield"))
            return {
                "name": info.get("shortName") or info.get("longName") or ticker.upper(),
                "category": info.get("category"),
                "expense_ratio_pct": _f(expense),
                "yield_pct": _f(raw_yield * 100.0) if raw_yield is not None else None,
            }

        return _cached("fundmeta:" + ticker, 86400, build)

    def earnings_calendar(self, ticker: str) -> Dict[str, Any]:
        """Next scheduled report plus the consensus EPS/revenue band for it."""

        def build() -> Dict[str, Any]:
            try:
                cal = yf.Ticker(ticker).calendar or {}
            except Exception:
                return {}
            dates = cal.get("Earnings Date") or []
            if not isinstance(dates, list):
                dates = [dates]
            return {
                # yfinance returns a list: one entry is a confirmed date, two is
                # an estimated window the company hasn't pinned down yet.
                "dates": [str(d) for d in dates],
                "confirmed": len(dates) == 1,
                "eps_avg": _f(cal.get("Earnings Average")),
                "eps_low": _f(cal.get("Earnings Low")),
                "eps_high": _f(cal.get("Earnings High")),
                "revenue_avg": _f(cal.get("Revenue Average")),
                "revenue_low": _f(cal.get("Revenue Low")),
                "revenue_high": _f(cal.get("Revenue High")),
            }

        return _cached("earncal:" + ticker, 3600, build)

    def estimates(self, ticker: str) -> Dict[str, Any]:
        """Analyst estimates and how they've been revised.

        yfinance keys periods as 0q / +1q / 0y / +1y (current quarter, next
        quarter, current fiscal year, next). The revision trend across 7/30/60/90
        days is the closest public proxy for guidance direction, since company
        guidance text itself isn't in any free feed.
        """

        def build() -> Dict[str, Any]:
            t = yf.Ticker(ticker)
            out: Dict[str, Any] = {}
            for name, attr in (
                ("eps_trend", "eps_trend"),
                ("eps_revisions", "eps_revisions"),
                ("growth", "growth_estimates"),
                ("eps_estimate", "earnings_estimate"),
                ("revenue_estimate", "revenue_estimate"),
            ):
                try:
                    frame = getattr(t, attr)
                except Exception:
                    frame = None
                if frame is None or getattr(frame, "empty", True):
                    out[name] = None
                    continue
                out[name] = {
                    str(idx): {str(c): _f(frame.loc[idx, c]) for c in frame.columns}
                    for idx in frame.index
                }
            return out

        return _cached("est:" + ticker, 3600, build)

    def analyst_view(self, ticker: str) -> Dict[str, Any]:
        """Price-target band and the rating distribution over recent months."""

        def build() -> Dict[str, Any]:
            t = yf.Ticker(ticker)
            out: Dict[str, Any] = {"targets": None, "ratings": []}
            try:
                targets = t.analyst_price_targets or {}
                out["targets"] = {k: _f(v) for k, v in targets.items()}
            except Exception:
                pass
            try:
                frame = t.recommendations
                if frame is not None and not frame.empty:
                    out["ratings"] = [
                        {
                            "period": str(row.get("period")),
                            "strong_buy": _f(row.get("strongBuy")),
                            "buy": _f(row.get("buy")),
                            "hold": _f(row.get("hold")),
                            "sell": _f(row.get("sell")),
                            "strong_sell": _f(row.get("strongSell")),
                        }
                        for _, row in frame.iterrows()
                    ]
            except Exception:
                pass
            return out

        return _cached("analyst:" + ticker, 3600, build)

    def financials(self, ticker: str) -> Dict[str, Any]:
        """Annual and quarterly statement lines, keyed by the labels yfinance uses."""

        def build() -> Dict[str, Any]:
            t = yf.Ticker(ticker)
            out: Dict[str, Any] = {}
            for name, attr in (
                ("income_annual", "income_stmt"),
                ("income_quarterly", "quarterly_income_stmt"),
                ("balance_annual", "balance_sheet"),
                ("cashflow_annual", "cashflow"),
            ):
                try:
                    frame = getattr(t, attr)
                except Exception:
                    frame = None
                if frame is None or getattr(frame, "empty", True):
                    out[name] = None
                    continue
                out[name] = {
                    "periods": [str(pd.Timestamp(c).date()) for c in frame.columns],
                    "rows": {
                        str(idx): [_f(v) for v in frame.loc[idx].tolist()]
                        for idx in frame.index
                    },
                }
            return out

        return _cached("fin:" + ticker, 3600, build)

    def insiders(self, ticker: str, limit: int = 12) -> Dict[str, Any]:
        def build() -> Dict[str, Any]:
            t = yf.Ticker(ticker)
            summary: Dict[str, Any] = {}
            try:
                frame = t.insider_purchases
                if frame is not None and not frame.empty:
                    label_col = frame.columns[0]
                    for _, row in frame.iterrows():
                        key = str(row[label_col])
                        summary[key] = {
                            "shares": _f(row.get("Shares")),
                            "transactions": _f(row.get("Trans")),
                        }
            except Exception:
                summary = {}

            trades: List[Dict[str, Any]] = []
            try:
                frame = t.insider_transactions
                if frame is not None and not frame.empty:
                    for _, row in frame.head(limit).iterrows():
                        text = str(row.get("Text") or "")
                        lowered = text.lower()
                        action = (
                            "sale" if "sale" in lowered
                            else "purchase" if "purchase" in lowered or "buy" in lowered
                            else "other"
                        )
                        trades.append(
                            {
                                "insider": str(row.get("Insider") or ""),
                                "position": str(row.get("Position") or ""),
                                "date": str(row.get("Start Date") or "")[:10],
                                "shares": _f(row.get("Shares")),
                                "value": _f(row.get("Value")),
                                "action": action,
                                "detail": text[:120],
                            }
                        )
            except Exception:
                trades = []

            return {"summary_6m": summary, "transactions": trades}

        return _cached("insider:" + ticker, 3600, build)

    def institutions(self, ticker: str, limit: int = 10) -> Dict[str, Any]:
        def build() -> Dict[str, Any]:
            t = yf.Ticker(ticker)
            breakdown: Dict[str, Any] = {}
            try:
                frame = t.major_holders
                if frame is not None and not frame.empty:
                    col = frame.columns[0]
                    for idx, row in frame.iterrows():
                        breakdown[str(idx)] = _f(row[col])
            except Exception:
                breakdown = {}

            holders: List[Dict[str, Any]] = []
            try:
                frame = t.institutional_holders
                if frame is not None and not frame.empty:
                    for _, row in frame.head(limit).iterrows():
                        holders.append(
                            {
                                "holder": str(row.get("Holder") or ""),
                                "date_reported": str(row.get("Date Reported") or "")[:10],
                                "shares": _f(row.get("Shares")),
                                "value": _f(row.get("Value")),
                                "pct_held": _f(row.get("pctHeld")),
                                "pct_change": _f(row.get("pctChange")),
                            }
                        )
            except Exception:
                holders = []

            return {"breakdown": breakdown, "top_holders": holders}

        return _cached("inst:" + ticker, 3600, build)

    # -------------------------------------------------------------- news

    def news(self, ticker: str, limit: int = 12) -> List[Dict[str, Any]]:
        def build() -> List[Dict[str, Any]]:
            try:
                raw = yf.Ticker(ticker).news or []
            except Exception:
                return []

            items: List[Dict[str, Any]] = []
            for entry in raw[:limit]:
                content = entry.get("content", entry) or {}
                provider = content.get("provider") or {}
                url = ""
                for candidate in ("canonicalUrl", "clickThroughUrl"):
                    node = content.get(candidate) or {}
                    if isinstance(node, dict) and node.get("url"):
                        url = node["url"]
                        break
                items.append(
                    {
                        "id": content.get("id") or entry.get("id"),
                        "title": content.get("title") or "",
                        "summary": content.get("summary") or content.get("description") or "",
                        "publisher": provider.get("displayName") or "",
                        "published": content.get("pubDate") or content.get("displayTime") or "",
                        "url": url,
                        "content_type": content.get("contentType"),
                    }
                )
            return items

        return _cached("news:" + ticker, self.TTL_NEWS, build)


PROVIDER = YFinanceProvider()
