"""Invented market and company figures for the visual update's journeys (2026-11-11), served to the page at its own
API boundary by Playwright, so Home and the company Overview draw every figure the update adds: the headline line, the
tiles' 90-session lines, the heat map, the gauges and bars, the watchlist lines, the four small figures, the revenue
mix, estimates against results, the day after each report and who owns it.

Every value here is made up to show the shape the routes answer with (app/main.py, app/analytics/*); none is a real
quote. The shapes were read from the routes' own code and a local run. Without these the journeys see only the outage
states (every provider is refused at the closed port), which the failure journeys test on purpose.

`refuse(page, which)` answers the named routes as a failed feed does, so a journey can check that a missing series
shows the delivered empty or failed state, never a blank or a crash."""
from __future__ import annotations

import datetime as dt
import json
import math
import re

TODAY = "2026-11-09"


def _sessions(n, end=TODAY):
    d, out = dt.date.fromisoformat(end), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d -= dt.timedelta(days=1)
    return out[::-1]


def _path(n, start, end, wiggle, period=7.0):
    """A smooth made-up path from start to end with a wiggle."""
    return [round(start + (end - start) * i / (n - 1) + wiggle * math.sin(i / period), 2) for i in range(n)]


# ------------------------------------------------------------------ Home

STRIP = [
    ("equity", "S&P 500", "^GSPC", 7616.0, 1.27, 7200.0), ("equity", "Nasdaq 100", "^NDX", 28468.0, 2.63, 28900.0),
    ("equity", "Russell 2000", "^RUT", 2845.0, 0.86, 2900.0), ("volatility", "VIX", "^VIX", 17.71, -8.99, 21.0),
    ("rates", "US 10Y", "^TNX", 5.0, 0.3, 4.8), ("commodities", "WTI Crude", "CL=F", 88.25, 2.57, 80.0),
    ("commodities", "Gold", "GC=F", 4008.0, -0.53, 4100.0), ("crypto", "Bitcoin", "BTC-USD", 74178.0, 0.64, 70000.0),
]
FACTORS = [("VIX level", 17.7, 10.0, "in the 14 to 18 band"), ("VIX 5-day change", 6.3, -6.0, "-1.2 per 1% move"),
           ("Copper 20-day", -2.1, -4.7, "scaled"), ("Russell 2000 20-day", 1.4, 4.2, "scaled"),
           ("S&P 500 20-day", -1.1, -2.7, "scaled"), ("High-yield spread 20-day", 0.4, -2.3, "scaled"),
           ("Curve 3m10y", 0.6, 1.0, "positive slope"), ("Dollar 20-day", 0.9, -1.0, "scaled")]
SECTORS = [("XLK", "Technology", 3.86), ("XLE", "Energy", 1.47), ("XLI", "Industrials", 1.18), ("XLC", "Communication Services", 0.67),
           ("XLB", "Materials", 0.12), ("XLF", "Financials", 0.01), ("XLU", "Utilities", -0.10), ("XLRE", "Real Estate", -0.36),
           ("XLY", "Consumer Discretionary", -0.36), ("XLP", "Consumer Staples", -0.46), ("XLV", "Health Care", -0.70)]
SENTIMENT = [("Market momentum", 8.6), ("Market breadth", 57.4), ("Market volatility", 35.5), ("Risk appetite", 18.2),
             ("Safe-haven demand", 6.1), ("Junk-bond demand", 17.2)]
WATCH = [("AAPL", 353.98, 1.57, 330.0), ("NVDA", 175.29, 3.79, 190.0), ("MSFT", 519.33, -2.59, 505.0), ("TSLA", 392.82, 3.43, 360.0), ("AMZN", 266.68, -1.55, 255.0)]


def home_payload():
    groups = {}
    for g, label, sym, last, chg, start in STRIP:
        groups.setdefault(g, []).append({"label": label, "symbol": sym, "group": g, "last": last, "chg_1d": chg, "chg_5d": chg / 2, "chg_20d": chg * 2,
                                         "series": _path(90, start, last, abs(last) * 0.012), "delayed_minutes": 15,
                                         "trade_time": TODAY + "T16:00:00+00:00", "exchange": "TEST"})
    return {
        "generated_at": TODAY + "T16:42:00+00:00", "degraded": [],
        "session": {"phase": "regular", "label": "Regular session", "is_regular": True, "is_open": True, "now_et": TODAY + "T11:42:00-05:00"},
        "macro": {"regime": "neutral / mixed", "risk_score": -2.0, "stance": "Mixed.",
                  "factors": [{"factor": f, "value": v, "contribution": c, "rule": r, "kind": "scaled"} for f, v, c, r in FACTORS],
                  "expected_move": {"vix": 17.71, "spot": 7616.0, "implied_pct": 1.107, "implied_points": 84.3, "atr14": 106.0, "atr_pct": 1.38,
                                    "realized_pct": 0.863, "ratio": 1.29, "reading": "Options are pricing about 1.3 times the movement the index has been delivering, so protection is dear against recent moves."},
                  "groups": groups, "instruments": [x for v in groups.values() for x in v]},
        "alerts": [],
        "morning_desk": {"available": True, "date": TODAY, "title": "Optic Desk", "voice": "mechanical", "voice_reason": "unconfigured",
                         "overall": "Rates and the dollar give no clear signal today. With no big report due, where prices close says more than any move during the day. Oil is up, which feeds into the prices of almost everything.",
                         "lead": ["Traders expect the Federal Reserve's rate to be a little higher on average in January.", "Index futures are up."],
                         "scenarios": [], "calendar": [], "releases": [], "stories": [], "note": "",
                         "limits": ["No consensus estimates.", "Not a forecast."]},
    }


def sentiment_payload():
    return {"available": True, "score": 25.8, "label": "Fear", "generated_at": TODAY + "T16:42:00+00:00",
            "components": [{"key": k.lower().replace(" ", "_"), "label": k, "score": s, "label_text": "Fear" if s < 45 else "Neutral"} for k, s in SENTIMENT],
            "caveat": "A sentiment gauge describes positioning, not value."}


def market_payload():
    rows = [{"symbol": s, "name": n, "label": n, "last": 100.0, "chg_1d": c, "chg_5d": c * 1.5, "chg_20d": c * 3,
             "series": _path(90, 95.0, 100.0, 1.0)} for s, n, c in SECTORS]
    return {"generated_at": TODAY + "T16:42:00+00:00", "sectors": {"sectors": rows}}


def take_chart_payload(sym, span):
    n = {"3m": 63, "6m": 126, "1y": 252}.get(span, 126)
    dates = _sessions(n)
    close = _path(n, 7300.0, 7616.0, 90.0)
    return {"available": True, "ticker": sym, "span": span, "span_words": {"3m": "3 months", "6m": "6 months", "1y": "1 year"}.get(span, "6 months"),
            "bars": n, "as_of": TODAY, "chart": {"available": True, "ticker": sym, "dates": dates, "close": close}, "supports": [], "resistances": []}


def watchlist_payload(symbols):
    rows = []
    for sym, price, chg, start in WATCH:
        if sym in symbols:
            rows.append({"symbol": sym, "available": True, "price": price, "change_pct": chg, "change_5d_pct": chg, "change_20d_pct": chg,
                         "spark": _path(30, start, price, price * 0.01, 3.0), "changed": {"text": ""}})
    return {"available": True, "rows": rows, "generated_at": TODAY + "T16:42:00+00:00"}


# ------------------------------------------------------------------ the company Overview (AAPL's shape, invented values)

def company_extras(payload):
    """The statements and holders the Overview's figures read, added to tests/e2e/fixtures.py's ticker payload."""
    payload["company"]["financials"] = {
        "available": True, "annual_periods": ["2026-09-30", "2025-09-30", "2024-09-30", "2023-09-30"],
        "annual_fiscal": ["FY26", "FY25", "FY24", "FY23"], "fiscal_year_end": "2026-09-30",
        "annual": {"revenue": [479e9, 416e9, 391e9, 383e9], "net_income": [132e9, 112e9, 94e9, 97e9]},
        "margins": {"gross_pct": 48.8, "operating_pct": 33.0, "net_pct": 27.6}, "growth": {"revenue_yoy_pct": 15.1, "net_income_yoy_pct": 18.0}}
    payload["company"]["earnings_history"]["upcoming"] = [{"date": "2027-01-28", "timing": "after_close"}]
    payload["company"]["ownership"] = {"available": True, "institutional_pct_held": 0.67, "insider_pct_held": 0.017, "insider_signal": "selling", "top_holders": []}
    return payload


def earnings_payload():
    quarters = [("2024-12-31", "Q1 FY25", 2.35, 2.40, 0.5), ("2025-03-31", "Q2 FY25", 1.62, 1.65, -3.7), ("2025-06-30", "Q3 FY25", 1.43, 1.57, -2.5),
                ("2025-09-30", "Q4 FY25", 1.77, 1.85, -0.4), ("2025-12-31", "Q1 FY26", 2.67, 2.84, 0.5), ("2026-03-31", "Q2 FY26", 1.95, 1.99, 3.2),
                ("2026-06-30", "Q3 FY26", 1.89, 2.02, -7.4), ("2026-09-30", "Q4 FY26", 1.98, 2.10, -1.9)]
    rows = [{"date": d, "fiscal": f, "eps_estimate": e, "eps_reported": r, "surprise_pct": round((r / e - 1) * 100, 1), "beat": r > e, "next_day_move_pct": m}
            for d, f, e, r, m in reversed(quarters)]
    return {"ticker": "AAPL", "surprise": {"available": True, "rows": rows, "quarters": 8, "beat_count": 8, "miss_count": 0},
            "next_report": {"date": "2027-01-28", "days_away": 80}, "implied": {"available": False}}


def segments_payload():
    return {"available": True, "ticker": "AAPL", "tables": [], "annual_only_tables": [{
        "axis": "product", "axis_label": "By product", "metric": "revenue", "metric_label": "Revenue",
        "annual": {"ends": ["2025-09-27", "2026-09-26"], "rows": [
            {"member": "iPhone", "values": [209e9, 254e9]}, {"member": "Services", "values": [109e9, 125e9]}, {"member": "Mac", "values": [33e9, 38e9]},
            {"member": "Wearables", "values": [36e9, 34e9]}, {"member": "iPad", "values": [28e9, 28e9]}]},
        "reported": {"year": [{"value": 415e9, "form": "10-K"}, {"value": 479e9, "form": "10-K"}]}}]}


def fair_value_payload():
    return {"available": True, "stars": {"available": True, "stars": 1, "word": "Above its usual valuation range"}}


def longterm_payload():
    return {"holding": {"valuation_history": {"available": True, "usable_years": 4, "current_pe": 39.4, "median_pe": 30.9, "low_pe": 26.0, "high_pe": 38.0},
                        "risk": {"annualised_vol_pct": 28.0}, "drawdown": {"current_drawdown_pct": -1.0}}}


# ------------------------------------------------------------------ routing

def _json(route, body, status=200):
    route.fulfill(status=status, content_type="application/json", body=json.dumps(body))


def route_home(page, watch_symbols=()):
    """Serve Home's market figures; everything else goes on to the real server."""
    page.route(re.compile(r".*/api/home(\?.*)?$"), lambda r: _json(r, home_payload()))
    page.route(re.compile(r".*/api/sentiment(\?.*)?$"), lambda r: _json(r, sentiment_payload()))
    page.route(re.compile(r".*/api/market(\?.*)?$"), lambda r: _json(r, market_payload()))

    def chart(route):
        m = re.search(r"/api/take-chart/([^?]+)\?span=(\w+)", route.request.url)
        _json(route, take_chart_payload(m.group(1) if m else "^GSPC", m.group(2) if m else "6m"))
    page.route(re.compile(r".*/api/take-chart/.*"), chart)

    def watch(route):
        q = re.search(r"symbols=([^&]+)", route.request.url)
        syms = set(re.split(r"%2C|,", q.group(1))) if q else set()
        _json(route, watchlist_payload(syms))
    page.route(re.compile(r".*/api/watchlist\?.*"), watch)


def route_company(page):
    """Serve the Overview's figures for AAPL (the ticker payload from fixtures.py with statements and holders added)."""
    from tests.e2e.fixtures import ticker_payload

    def ticker(route):
        if "/api/ticker/AAPL" not in route.request.url:
            return route.fallback()
        _json(route, company_extras(ticker_payload("AAPL")))
    page.route(re.compile(r".*/api/ticker/[A-Za-z0-9.^=-]+(\?.*)?$"), ticker)
    page.route(re.compile(r".*/api/earnings/AAPL(\?.*)?$"), lambda r: _json(r, earnings_payload()))
    page.route(re.compile(r".*/api/segments/AAPL(\?.*)?$"), lambda r: _json(r, segments_payload()))
    page.route(re.compile(r".*/api/fair-value/AAPL(\?.*)?$"), lambda r: _json(r, fair_value_payload()))
    page.route(re.compile(r".*/api/longterm/AAPL(\?.*)?$"), lambda r: _json(r, longterm_payload()))


REFUSE = {"home": r".*/api/home(\?.*)?$", "sentiment": r".*/api/sentiment(\?.*)?$", "market": r".*/api/market(\?.*)?$",
          "take-chart": r".*/api/take-chart/.*", "watchlist": r".*/api/watchlist\?.*", "ticker": r".*/api/ticker/.*",
          "earnings": r".*/api/earnings/.*", "segments": r".*/api/segments/.*", "longterm": r".*/api/longterm/.*", "fair-value": r".*/api/fair-value/.*"}


def refuse(page, *which):
    """Answer the named routes as the feed did on 2026-11-10 and 11 ("Invalid Crumb", a 401 passed on as a 502)."""
    for w in which:
        page.route(re.compile(REFUSE[w]), lambda r: _json(r, {"detail": "The data source refused the request (Invalid Crumb)."}, 502))
