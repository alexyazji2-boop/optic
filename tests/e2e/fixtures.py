"""Recorded answers for the stock page's symbol check and quote, served to the page by Playwright.

Invented values, shaped as app/main.py and app/symbol_check.py answer, labelled as test data. AAPL's price and change
are the watchlist row on the owner's home screen of 2026-11-09; everything else is made up to show the shape. QQQX is
a listed symbol whose feed gives no company name, for the prompt's fallback to the ticker."""
from __future__ import annotations

import json
import re

QUOTES = {
    "AAPL": {"symbol": "AAPL", "name": "Apple Inc.", "price": 248.21, "change": 2.42, "change_pct": 0.98, "previous_close": 245.79,
             "volume": 51234000, "avg_volume": 48000000, "market_cap": 3.71e12, "currency": "USD", "delayed_minutes": 15,
             "trade_time": "2026-11-09T21:00:00+00:00", "fifty_two_low": 164.08, "fifty_two_high": 260.10, "trailing_pe": 33.1},
    "MSFT": {"symbol": "MSFT", "name": "Microsoft Corporation", "price": 517.30, "change": 3.29, "change_pct": 0.64, "previous_close": 514.01,
             "volume": 21000000, "market_cap": 3.85e12, "currency": "USD", "delayed_minutes": 15, "trade_time": "2026-11-09T21:00:00+00:00"},
    "QQQX": {"symbol": "QQQX", "price": 27.15, "change": -0.11, "change_pct": -0.40, "previous_close": 27.26, "volume": 120000,
             "currency": "USD", "delayed_minutes": 15, "trade_time": "2026-11-09T21:00:00+00:00"},
}


def route_fixtures(page):
    """Serve the fixtures above; everything else goes to the real server."""
    def symbol_check(route):
        q = re.search(r"[?&]q=([^&]+)", route.request.url)
        sym = (q.group(1) if q else "").upper()
        if sym in QUOTES:
            body = {"query": sym, "symbol": sym, "status": "listed", "name": QUOTES[sym].get("name") or ""}
        else:
            body = {"query": sym, "symbol": sym, "status": "unknown"}
        route.fulfill(status=200, content_type="application/json", body=json.dumps(body))

    def quote(route):
        sym = route.request.url.rsplit("/", 1)[-1].split("?", 1)[0].upper()
        q = QUOTES.get(sym)
        body = {"ticker": sym, "available": True, "quote": q} if q else {"ticker": sym, "available": False}
        route.fulfill(status=200, content_type="application/json", body=json.dumps(body))

    page.route(re.compile(r".*/api/symbol-check\?.*"), symbol_check)
    page.route(re.compile(r".*/api/quote/[A-Za-z0-9.^=-]+(\?.*)?$"), quote)
