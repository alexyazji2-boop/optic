"""The earnings implied move says whether it was priced from quotes or trades.

Overnight and all weekend the free feed serves option chains with no bid and
no ask, and the provider's mid falls back to each contract's last trade. The
Earnings page showed "Implied move 5.7%, 21-day straddle" at 5am from those
trades with nothing saying so (launch audit, 2026-10-16).
"""
from __future__ import annotations

import pandas as pd

from app.analytics import earnings


class _Provider:
    def __init__(self, quoted):
        self.quoted = quoted

    def expirations(self, ticker):
        return ["2026-11-06"]

    def options_chain(self, ticker, expiries):
        rows = []
        for is_call in (True, False):
            for k in (95.0, 100.0, 105.0):
                last = 3.0 if k == 100.0 else 1.0
                bid, ask = ((last - 0.1, last + 0.1) if self.quoted else (0.0, 0.0))
                mid = (bid + ask) / 2 if self.quoted else last
                rows.append({"strike": k, "is_call": is_call, "bid": bid, "ask": ask, "mid": mid,
                             "last": last, "last_trade": pd.Timestamp("2026-10-15T19:58:00Z")})
        return pd.DataFrame(rows)


def _move(quoted):
    return earnings._implied_move(_Provider(quoted), "TEST", 100.0, "2026-11-02", 0.04, "before_open")


def test_a_quoted_straddle_says_quotes():
    out = _move(True)
    assert out["available"] and out["priced_from"] == "quotes" and out["last_trade"] is None
    assert out["implied_move_pct"] == 6.0


def test_an_unquoted_straddle_says_last_trades_and_when():
    out = _move(False)
    assert out["available"] and out["priced_from"] == "last_trades"
    assert out["last_trade"].startswith("2026-10-15T19:58")


def test_the_page_says_so():
    from pathlib import Path
    app = (Path(__file__).resolve().parent.parent / "static/app.js").read_text()
    assert "imp.priced_from === 'last_trades'" in app
