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


# A year and a bit of daily closes for the stock page's past-year chart, with four earnings reports inside it, so the
# chart draws in the suite with its E marks (which are buttons). Without it the history never arrives (the feeds are
# refused) and the chart's SVG was never drawn by any journey: the accessibility scans passed while the live stock page
# failed axe's nested-interactive on that chart (gauntlet D1, 2026-11-10). Invented values, a smooth made-up path.
def _sessions(end="2026-11-09", n=300):
    import datetime as dt
    d, out = dt.date.fromisoformat(end), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d -= dt.timedelta(days=1)
    return out[::-1]


def ticker_payload(sym):
    import math
    q = QUOTES[sym]
    dates = _sessions()
    base = q["price"]
    close = [round(base * (0.78 + 0.22 * i / (len(dates) - 1)) + 6 * math.sin(i / 9.0), 2) for i in range(len(dates))]
    close[-1] = base
    quarters = [{"date": d, "timing": "amc", "eps_reported": e, "eps_estimate": round(e - 0.04, 2), "surprise_pct": 2.5}
                for d, e in (("2026-01-29", 2.40), ("2026-04-30", 1.65), ("2026-07-30", 1.57), ("2026-10-30", 1.85))]
    return {"ticker": sym, "quote": q, "company": {"name": q.get("name") or sym, "earnings_history": {"quarters": quarters}},
            "technicals": {"price_series": {"dates": dates, "close": close}}}


def route_price_history(page):
    """Serve ticker_payload for the symbols above at /api/ticker; opt-in, for the journeys that need the chart drawn."""
    def ticker(route):
        sym = route.request.url.split("/api/ticker/", 1)[1].split("?", 1)[0].upper()
        if sym not in QUOTES:
            return route.fallback()
        route.fulfill(status=200, content_type="application/json", body=json.dumps(ticker_payload(sym)))

    page.route(re.compile(r".*/api/ticker/[A-Za-z0-9.^=-]+(\?.*)?$"), ticker)


def intraday_payload(sym, n=200):
    """Hourly bars for the Chart tab's default bar size (1h), shaped as /api/intraday answers. Invented values: a smooth
    made-up path ending at the fixture's price, one bar an hour across regular sessions."""
    import datetime as dt
    import math
    base = QUOTES[sym]["price"]
    days = _sessions(n=(n // 7) + 2)
    times = [f"{d}T{h:02d}:30:00-05:00" for d in days for h in range(9, 16)][-n:]
    closes = [round(base * (0.9 + 0.1 * i / (len(times) - 1)) + 2 * math.sin(i / 5.0), 2) for i in range(len(times))]
    closes[-1] = base
    opens = [closes[0]] + closes[:-1]
    return {"available": True, "symbol": sym, "times": times, "opens": opens, "closes": closes,
            "highs": [round(max(o, c) + 0.8, 2) for o, c in zip(opens, closes)], "lows": [round(min(o, c) - 0.8, 2) for o, c in zip(opens, closes)],
            "volumes": [1_000_000 + 1000 * i for i in range(len(times))], "session_note": "Invented hourly bars (test data)."}


def route_intraday(page):
    """Serve intraday_payload at /api/intraday for the symbols above; opt-in, for the journeys that need the Chart tab drawn."""
    def intraday(route):
        sym = route.request.url.split("/api/intraday/", 1)[1].split("?", 1)[0].upper()
        if sym not in QUOTES:
            return route.fallback()
        route.fulfill(status=200, content_type="application/json", body=json.dumps(intraday_payload(sym)))

    page.route(re.compile(r".*/api/intraday/[A-Za-z0-9.^=-]+(\?.*)?$"), intraday)
