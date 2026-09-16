"""Provider interface.

Everything upstream of this file talks in normalized frames, so swapping
yfinance for a paid feed means writing one new adapter — not touching the
analytics.

Normalized options-chain columns:
    contract, expiry, dte, tau, strike, is_call, last, bid, ask, mid,
    volume, open_interest, iv, in_the_money
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd


class MarketDataProvider:
    name = "base"

    def quote(self, ticker: str) -> Dict[str, Any]:
        raise NotImplementedError

    def history(self, ticker: str, period: str = "2y", interval: str = "1d") -> pd.DataFrame:
        raise NotImplementedError

    def expirations(self, ticker: str) -> List[str]:
        raise NotImplementedError

    def options_chain(
        self, ticker: str, expiries: Optional[List[str]] = None, max_expiries: int = 4
    ) -> pd.DataFrame:
        raise NotImplementedError

    def splits(self, ticker: str) -> List[Dict[str, Any]]:
        """Stock splits as [{date, ratio}], oldest first. Empty when unknown."""
        return []

    def news(self, ticker: str, limit: int = 12) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def batch_history(
        self, tickers: List[str], period: str = "1y", interval: str = "1d"
    ) -> Dict[str, pd.DataFrame]:
        raise NotImplementedError

    def batch_quote(self, tickers: List[str]) -> Dict[str, Dict[str, Any]]:
        """`{symbol: {last, prev_close, as_of}}` for the symbols the feed answers.

        Separate from `quote()` because the cross-asset panels want exactly two
        numbers for twenty-odd symbols at once, and because one of those two is
        the figure a daily frame cannot supply correctly. A bar-over-bar change
        is the session's change only when the vendor's bars break where the
        session does, and for futures and FX they do not.

        Symbols the feed cannot answer for are left out rather than given null
        entries, so a caller falls back to bar arithmetic per symbol instead of
        losing the whole row.

        The default loops `quote()`, which is correct but costs a request each;
        adapters with a cheaper path should override it.
        """
        out: Dict[str, Dict[str, Any]] = {}
        for ticker in tickers:
            try:
                quote = self.quote(ticker)
            except Exception:                                   # noqa: BLE001
                continue
            last, prev = quote.get("price"), quote.get("prev_close")
            if last is None or not prev:
                continue
            out[ticker] = {"last": last, "prev_close": prev,
                           "as_of": quote.get("as_of")}
        return out

    def intraday_history(
        self, ticker: str, period: str = "5d", interval: str = "1m"
    ) -> pd.DataFrame:
        """Minute-resolution bars, tz-aware in US/Eastern.

        Same OHLCV column contract as history(). ``period`` covers the last N
        calendar days (subject to the vendor's intraday lookback limit).
        """
        raise NotImplementedError
