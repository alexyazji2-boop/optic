"""Tradier adapter — real-time quotes and options chains.

Tradier's brokerage market-data API gives real-time bid/ask/last/volume/open
interest and IV for a funded (even unfunded) account, unlike the ~15-minute
delayed yfinance feed. It does not, however, have equivalent coverage for
company financials, insider/institutional filings, earnings history, news, or
non-equity instruments (FX pairs, index tickers like ^VIX, commodity futures).

So this provider handles only what genuinely benefits from being real-time —
quote, history, expirations, options_chain — and delegates everything else
(batch_history for the macro/sector universe, news, fundamentals) to a wrapped
yfinance instance. See app/main.py for how the two are composed: Tradier
supplies the "current ticker" price and chain when configured; yfinance always
supplies the macro/sector universe and company fundamentals, since Tradier has
no data for either.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import requests

from .base import MarketDataProvider
from .common import clean_iv, period_to_days, pick_swing_expiries

PRODUCTION_BASE = "https://api.tradier.com/v1"
SANDBOX_BASE = "https://sandbox.tradier.com/v1"


def _f(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(out) else out


class TradierProvider(MarketDataProvider):
    name = "tradier"

    # Short TTLs — the whole point of this adapter is freshness, but a UI
    # refresh loop or a burst of panel loads shouldn't re-hit the API per pixel.
    TTL_QUOTE = 5
    TTL_CHAIN = 8
    TTL_EXPIRY = 300
    TTL_HISTORY = 300

    def __init__(self, token: str, sandbox: bool = False, fallback: Optional[MarketDataProvider] = None):
        self.token = token
        self.base = SANDBOX_BASE if sandbox else PRODUCTION_BASE
        # Fundamentals, news, and the macro/sector symbol universe (FX pairs,
        # futures, index tickers) aren't things Tradier's equity/options API
        # can serve — delegate those to yfinance rather than reimplementing.
        self.fallback = fallback
        self._session = requests.Session()
        self._session.headers.update(
            {"Authorization": "Bearer {}".format(token), "Accept": "application/json"}
        )
        self._cache: Dict[str, Any] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------- transport

    def _get(self, path: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            resp = self._session.get(self.base + path, params=params, timeout=10)
            if resp.status_code != 200:
                return None
            return resp.json()
        except (requests.RequestException, ValueError):
            return None

    def _cached(self, key: str, ttl: float, producer):
        now = time.time()
        with self._lock:
            hit = self._cache.get(key)
            if hit is not None and now - hit[0] < ttl:
                return hit[1]
            value = producer()
            self._cache[key] = (time.time(), value)
            return value

    @staticmethod
    def _as_list(node: Any) -> List[Any]:
        """Tradier collapses a single-item result to a bare object instead of
        a one-element list — normalise both shapes."""
        if node is None:
            return []
        return node if isinstance(node, list) else [node]

    # ------------------------------------------------------------------ quote

    def quote(self, ticker: str) -> Dict[str, Any]:
        def build() -> Dict[str, Any]:
            # Descriptive/fundamental fields (name, sector, market cap, PE,
            # dividend yield...) don't need to be real-time — a company's
            # sector doesn't change intraday — so those come from yfinance.
            # Only the numeric, time-sensitive fields get overlaid from Tradier.
            base = self.fallback.quote(ticker) if self.fallback else {"ticker": ticker.upper()}

            data = self._get("/markets/quotes", {"symbols": ticker, "greeks": "false"})
            quotes = self._as_list((data or {}).get("quotes", {}).get("quote")) if data else []
            if not quotes:
                base["quote_source"] = "yfinance (Tradier quote unavailable)"
                return base

            q = quotes[0]
            base.update(
                {
                    "price": _f(q.get("last")) or base.get("price"),
                    "prev_close": _f(q.get("prevclose")) or base.get("prev_close"),
                    "change": _f(q.get("change")),
                    "change_pct": _f(q.get("change_percentage")),
                    "day_high": _f(q.get("high")),
                    "day_low": _f(q.get("low")),
                    "volume": _f(q.get("volume")),
                    "avg_volume": _f(q.get("average_volume")) or base.get("avg_volume"),
                    "fifty_two_high": _f(q.get("week_52_high")) or base.get("fifty_two_high"),
                    "fifty_two_low": _f(q.get("week_52_low")) or base.get("fifty_two_low"),
                    "bid": _f(q.get("bid")),
                    "ask": _f(q.get("ask")),
                    "exchange": q.get("exch") or base.get("exchange"),
                    "quote_source": "tradier (real-time)",
                    "as_of": datetime.now(timezone.utc).isoformat(),
                }
            )
            return base

        return self._cached("quote:" + ticker, self.TTL_QUOTE, build)

    # ---------------------------------------------------------------- history

    def history(self, ticker: str, period: str = "2y", interval: str = "1d") -> pd.DataFrame:
        key = "hist:{}:{}:{}".format(ticker, period, interval)

        def build() -> pd.DataFrame:
            days = period_to_days(period)
            end = datetime.now().date()
            start = end - timedelta(days=days)
            tradier_interval = {"1d": "daily", "1wk": "weekly", "1mo": "monthly"}.get(interval, "daily")

            data = self._get(
                "/markets/history",
                {
                    "symbol": ticker,
                    "interval": tradier_interval,
                    "start": str(start),
                    "end": str(end),
                },
            )
            rows = self._as_list((data or {}).get("history", {}).get("day")) if data else []
            if not rows:
                return pd.DataFrame()

            frame = pd.DataFrame(rows)
            frame["date"] = pd.to_datetime(frame["date"])
            frame = frame.set_index("date").sort_index()
            frame = frame.rename(
                columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}
            )
            for col in ("Open", "High", "Low", "Close", "Volume"):
                if col in frame:
                    frame[col] = pd.to_numeric(frame[col], errors="coerce")
            return frame.dropna(subset=["Close"])

        return self._cached(key, self.TTL_HISTORY, build)

    def intraday_history(self, ticker: str, period: str = "5d", interval: str = "1m") -> pd.DataFrame:
        """Minute bars via /markets/timesales — genuinely real-time, unlike the
        yfinance fallback, which is why intraday work is worth using Tradier
        for specifically."""
        key = "intraday:{}:{}:{}".format(ticker, period, interval)

        def build() -> pd.DataFrame:
            days = period_to_days(period)
            end = datetime.now()
            start = end - timedelta(days=days)
            tradier_interval = {"1m": "1min", "5m": "5min", "15m": "15min"}.get(interval, "1min")

            data = self._get(
                "/markets/timesales",
                {
                    "symbol": ticker,
                    "interval": tradier_interval,
                    "start": start.strftime("%Y-%m-%d %H:%M"),
                    "end": end.strftime("%Y-%m-%d %H:%M"),
                    "session_filter": "open",
                },
            )
            rows = self._as_list((data or {}).get("series", {}).get("data")) if data else []
            if not rows:
                # Fall back to the delayed feed rather than an empty intraday read.
                return self.fallback.intraday_history(ticker, period=period, interval=interval) if self.fallback else pd.DataFrame()

            frame = pd.DataFrame(rows)
            frame["time"] = pd.to_datetime(frame["time"])
            frame = frame.set_index("time").sort_index()
            if frame.index.tz is None:
                frame = frame.tz_localize("America/New_York")
            else:
                frame = frame.tz_convert("America/New_York")
            frame = frame.rename(
                columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}
            )
            for col in ("Open", "High", "Low", "Close", "Volume"):
                if col in frame:
                    frame[col] = pd.to_numeric(frame[col], errors="coerce")
            return frame.dropna(subset=["Close"])

        return self._cached(key, 15, build)

    def batch_history(
        self, tickers: List[str], period: str = "1y", interval: str = "1d"
    ) -> Dict[str, pd.DataFrame]:
        # Macro/sector universes include FX pairs, futures, and index tickers
        # Tradier's equity/options API doesn't serve, plus this needs one bulk
        # request rather than N serial ones — yfinance remains the right tool.
        if self.fallback:
            return self.fallback.batch_history(tickers, period=period, interval=interval)
        return {}

    # ----------------------------------------------------------------options

    def expirations(self, ticker: str) -> List[str]:
        def build() -> List[str]:
            data = self._get(
                "/markets/options/expirations",
                {"symbol": ticker, "includeAllRoots": "true", "strikes": "false"},
            )
            dates = self._as_list((data or {}).get("expirations", {}).get("date")) if data else []
            return [str(d) for d in dates]

        return self._cached("exp:" + ticker, self.TTL_EXPIRY, build)

    def options_chain(
        self, ticker: str, expiries: Optional[List[str]] = None, max_expiries: int = 4
    ) -> pd.DataFrame:
        available = self.expirations(ticker)
        if not available:
            return pd.DataFrame()

        wanted = [e for e in expiries if e in available] if expiries else pick_swing_expiries(available, max_expiries)
        if not wanted:
            return pd.DataFrame()

        key = "chain:{}:{}".format(ticker, ",".join(wanted))

        def build() -> pd.DataFrame:
            frames: List[pd.DataFrame] = []
            today = pd.Timestamp.today().normalize()

            for exp in wanted:
                data = self._get(
                    "/markets/options/chains", {"symbol": ticker, "expiration": exp, "greeks": "true"}
                )
                contracts = self._as_list((data or {}).get("options", {}).get("option")) if data else []
                if not contracts:
                    continue

                rows = []
                for c in contracts:
                    greeks = c.get("greeks") or {}
                    iv = _f(greeks.get("mid_iv")) or _f(greeks.get("smv_vol")) or _f(greeks.get("ask_iv")) or _f(greeks.get("bid_iv"))
                    rows.append(
                        {
                            "contract": c.get("symbol"),
                            "strike": _f(c.get("strike")),
                            "last": _f(c.get("last")),
                            "bid": _f(c.get("bid")),
                            "ask": _f(c.get("ask")),
                            "volume": _f(c.get("volume")),
                            "open_interest": _f(c.get("open_interest")),
                            "iv": iv,
                            "is_call": (c.get("option_type") or "").lower() == "call",
                        }
                    )

                part = pd.DataFrame(rows)
                if part.empty:
                    continue
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

        return self._cached(key, self.TTL_CHAIN, build)

    # ------------------------------------------------ delegated (no Tradier data)

    def news(self, ticker: str, limit: int = 12) -> List[Dict[str, Any]]:
        return self.fallback.news(ticker, limit=limit) if self.fallback else []
