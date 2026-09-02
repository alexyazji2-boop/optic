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

    def intraday_history(
        self, ticker: str, period: str = "5d", interval: str = "1m"
    ) -> pd.DataFrame:
        """Minute-resolution bars, tz-aware in US/Eastern.

        Same OHLCV column contract as history(). ``period`` covers the last N
        calendar days (subject to the vendor's intraday lookback limit).
        """
        raise NotImplementedError
