"""Milo's research tools: typed, validated, server-side access to what the terminal computes (2026-10-15).

Why this exists. Milo only ever answered from what the page pushed to it. A reader asked from Home "What does
the updated call/put flow, walls and gamma look like on AMD?"; the server did fetch AMD's whole analysis
(`_augment_chat_context_lookups`), but as one 261,550-character block it exceeded the context budget's
14,000-character section cap and was dropped entirely, and Milo told the reader to open the Options tab.
Page context should enrich an answer, not bound it. So Milo now has tools: when the question needs data
the page did not send, it asks for it, and the answer is built on the same functions the terminal's own
views use (`app/main.py` hands this module its runners, so nothing here imports the web layer).

What a tool is, and is not:

* Each tool is one terminal capability: a quote, the Options tab's analytics, chart levels, the long-term
  model, the fair-value model, the earnings panel, the news panel, the market read, a comparison, the
  research framework, the screener, the signed-in reader's own watchlists and linked portfolio, and (since
  post-demo Phase 08, from the milo-upgrade branch) the symbol directory, price history, SEC filings and
  reported results (`app/milo_data.py`).
* Inputs are validated here before anything runs (a symbol pattern, enums, bounded lists), because the
  request streams with eager input and the API does not validate for us.
* Every result is trimmed to a size the model can use and carries its source and freshness: when the
  source says the data is from (the quote's own time, the chain's), not when Milo happened to fetch it.
* Results are data. Text inside them (headlines, filings) is never an instruction to the model.
* There is no generic endpoint, no database access and no way to name another reader: the watchlist tool
  reads the asking reader's own lists, from their session, or nothing.

Limits per answer: rounds, calls, a per-call timeout and a total time budget. A repeated call with the same
input returns the first result. Calls run one at a time: the price feed returns partial frames under
concurrent batch downloads (see `market_panel` in app/main.py).
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

# A leading caret is allowed: index symbols (^VIX, ^GSPC) start with one, and the description below offers
# ^GSPC as an example while the first pattern rejected it (milo-reasoning evaluation, 2026-10-16; milo-upgrade
# 795a766; post-demo Phase 08).
TICKER = re.compile(r"^[A-Z0-9^][A-Z0-9.\-^=]{0,11}$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RESULT_CHARS = 12_000
MAX_ROUNDS = 4
MAX_CALLS = 10
CALL_TIMEOUT = 30.0
TOTAL_BUDGET = 75.0

_TICKER_PROP = {"type": "string", "description": "The symbol, for example AMD, BRK.B, ^GSPC, BTC-USD or EURUSD=X."}

# --------------------------------------------------------------------------------------- definitions
# Descriptions say when to call each one, which is what decides whether the model reaches for it.
SPECS: List[Dict[str, Any]] = [
    {
        "name": "get_quote",
        "description": ("The latest delayed quote for one symbol: price, change, the day's range, volume, "
                        "market state, any pre- or post-market print, and the quote's own timestamp. Call it "
                        "when the question needs the current price of a symbol CONTEXT does not have, or a "
                        "fresher one."),
        "input_schema": {"type": "object", "properties": {"ticker": _TICKER_PROP},
                         "required": ["ticker"], "additionalProperties": False},
    },
    {
        "name": "get_options",
        "description": ("The Options tab's analytics for one symbol, computed from the delayed option chain: "
                        "the call/put volume and open-interest flow proxy (no trade side: it cannot show buying, "
                        "selling, opening or closing), dealer gamma exposure (net GEX per "
                        "1% move, its regime, net vanna), the call wall, put wall, largest-gamma strike, "
                        "largest open-interest strike, the gamma flip if the modeled range has one, ATM greeks, "
                        "implied volatility, its term structure and any priced event move, IV rank, and which "
                        "expiries were used. Call it for any question about options, flow, walls, gamma, "
                        "positioning, implied volatility or expiries when CONTEXT has no options data for "
                        "that symbol. Without `expiries` it uses the Options tab's default: up to four "
                        "expiries, the ones nearest 7, 21, 35 and 60 days out and at least two days away."),
        "input_schema": {"type": "object", "properties": {
            "ticker": _TICKER_PROP,
            "expiries": {"type": "array", "items": {"type": "string", "description": "YYYY-MM-DD"},
                         "maxItems": 4,
                         "description": "Specific expiries to analyse, only when the reader named them."}},
            "required": ["ticker"], "additionalProperties": False},
    },
    {
        "name": "get_chart_levels",
        "description": ("Support and resistance levels and trend lines for one symbol over a timeframe, the "
                        "same ones Milo's inline chart draws, with the moving averages and RSI. Call it when "
                        "the question is about levels, a trend, a breakout, or where a stock could find "
                        "support, and CONTEXT has no `chart_levels` for that symbol and timeframe."),
        "input_schema": {"type": "object", "properties": {
            "ticker": _TICKER_PROP,
            "timeframe": {"type": "string", "enum": ["day", "swing", "long", "both"],
                          "description": "day (3 months of bars), swing (6 months), long (2 years), both (2 years)."}},
            "required": ["ticker", "timeframe"], "additionalProperties": False},
    },
    {
        "name": "get_fundamentals",
        # It listed returns on capital, cash conversion, the balance sheet and dilution, which it does not return
        # (they are the research framework's: get_assessment, long_term); a description that promises a figure the
        # result lacks invites one from memory (post-demo Phase 08, from the tool audit)
        "description": ("Optic's long-term model for one company: the holding view and its conviction, revenue and "
                        "earnings growth, profit margin, P/E, PEG, price to book and dividend yield, the returns over "
                        "one, three, five and ten years, the valuation history against its own record, drawdowns, "
                        "volatility and beta, and the weekly levels. Call it for questions about the business, its "
                        "growth and margins, or owning it for years, when CONTEXT lacks them. For returns on capital, "
                        "cash conversion, the balance sheet or dilution, call get_assessment with mode long_term."),
        "input_schema": {"type": "object", "properties": {"ticker": _TICKER_PROP},
                         "required": ["ticker"], "additionalProperties": False},
    },
    {
        "name": "get_valuation",
        "description": ("Optic's fair-value workspace for one company: the deterministic DCF value per share "
                        "against the price, its scenarios and sensitivities, the reverse DCF (what the price "
                        "assumes), the terminal value's share, and the complementary models that fit the "
                        "business. Call it for questions about value, cheap or expensive, or what the price "
                        "implies, when CONTEXT has no `valuation` for that symbol. The model's value is what "
                        "its assumptions imply, never a target."),
        "input_schema": {"type": "object", "properties": {"ticker": _TICKER_PROP},
                         "required": ["ticker"], "additionalProperties": False},
    },
    {
        "name": "get_earnings",
        "description": ("The earnings panel for one company: the next report date and timing, the consensus, "
                        "estimate revisions, the surprise record with price reactions, the latest result, and "
                        "what options charge for the event. Call it for questions about a coming or recent "
                        "report when CONTEXT has no `earnings` for that symbol."),
        "input_schema": {"type": "object", "properties": {"ticker": _TICKER_PROP},
                         "required": ["ticker"], "additionalProperties": False},
    },
    {
        "name": "get_news",
        "description": ("Recent headlines for one symbol with publisher, time and Optic's word-list score. "
                        "Call it when the question asks what is moving a stock or about recent news."),
        "input_schema": {"type": "object", "properties": {"ticker": _TICKER_PROP},
                         "required": ["ticker"], "additionalProperties": False},
    },
    {
        "name": "get_market",
        "description": ("Optic's whole-market read: index and sector levels and moves, breadth, the index "
                        "regime score, the written summary and the macro calendar, from the daily brief. Call "
                        "it for questions about the market, sectors, macro releases or the tape when CONTEXT "
                        "has no market data."),
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "compare",
        "description": ("A side-by-side comparison of two to four symbols across swing, position and "
                        "long-term horizons, with the read across them. Call it when the reader compares "
                        "companies."),
        "input_schema": {"type": "object", "properties": {
            "tickers": {"type": "array", "items": _TICKER_PROP, "minItems": 2, "maxItems": 4}},
            "required": ["tickers"], "additionalProperties": False},
    },
    {
        "name": "get_assessment",
        "description": ("Optic's research framework for one company in one mode: long_term (quality and "
                        "valuation grades, conviction, loss paths), swing (the setup grade and plan), "
                        "pre_earnings, post_earnings, or combined (all of them and where they agree). "
                        "Deterministic rules, no model call. Call it when the question asks for a judgement "
                        "the framework makes and CONTEXT has no `framework` for that symbol and mode."),
        "input_schema": {"type": "object", "properties": {
            "ticker": _TICKER_PROP,
            "mode": {"type": "string", "enum": ["long_term", "swing", "pre_earnings", "post_earnings", "combined"]}},
            "required": ["ticker", "mode"], "additionalProperties": False},
    },
    {
        "name": "screen_stocks",
        "description": ("Optic's screener over its ranked universe, reading a request in words (\"large caps "
                        "above the 200-day with rising earnings\") into its filters and returning the matches. "
                        "Call it when the reader asks Optic to find stocks."),
        "input_schema": {"type": "object", "properties": {
            "request": {"type": "string", "description": "The screen, in words, at most 200 characters."}},
            "required": ["request"], "additionalProperties": False},
    },
    {
        "name": "get_my_watchlists",
        "description": ("The signed-in reader's own saved watchlists (names and symbols). Call it when the "
                        "reader asks about their watchlist and CONTEXT does not carry it. It never returns "
                        "anyone else's lists; a guest has none stored."),
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "get_my_portfolio",
        "description": ("The signed-in reader's own linked brokerage portfolio, read-only, for the accounts they "
                        "count (or the account they narrowed the Brokerage page to): `summary` (holdings, weights, "
                        "totals, concentration), `exposure` (sectors, issuer countries, pricing currencies and "
                        "companies held directly and through funds, with look-through coverage), `events` (their "
                        "earnings, ex-dividend dates and option expiries, confirmed or estimated), `performance` "
                        "(time- and money-weighted returns, deposits and withdrawals, income, against a benchmark, "
                        "with the history it rests on), `scorecard` (diversification, financial quality, valuation, "
                        "volatility, event exposure, each with coverage), `options` (Greeks and expiry risk of their "
                        "option positions) or `briefing` (measured moves today and since the last sync, with "
                        "headlines matched by timing only). Call it when the reader asks about their own "
                        "portfolio, holdings, accounts, exposure, performance or upcoming events and CONTEXT has no "
                        "`brokerage_portfolio` or lacks the part needed. It never returns anyone else's data; "
                        "describe it, never advise trades."),
        "input_schema": {"type": "object", "properties": {
            "part": {"type": "string", "enum": ["summary", "exposure", "events", "performance", "scorecard",
                                                 "options", "briefing"]}},
            "required": ["part"], "additionalProperties": False},
    },
    # The milo-upgrade branch's data tools (795a766, 2026-10-25), brought in by hand in post-demo Phase 08: facts
    # Optic already reads for its pages that Milo could not ask for (app/milo_data.py).
    {
        "name": "lookup_company",
        "description": ("Find the ticker for a company, fund, index, rate, currency or crypto from its name, an alias "
                        "or part of a symbol, from the listed-symbol directory the terminal's search uses. Call it "
                        "when the reader names a company without its ticker, or a ticker you are not sure exists, "
                        "before fetching anything for it."),
        "input_schema": {"type": "object", "properties": {
            "query": {"type": "string", "description": "A company name, alias or symbol, at most 60 characters."}},
            "required": ["query"], "additionalProperties": False},
    },
    {
        "name": "get_price_history",
        "description": ("Daily or weekly price bars for one symbol over a named window, from the same Yahoo Finance "
                        "history the charts draw, with the window's change, high and low closes with dates, largest "
                        "drawdown and realised volatility computed by Optic, and the most recent bars. Call it "
                        "whenever the question asks how something has moved or performed over a period (\"the last "
                        "three months\", \"this year\", \"since the spring\") or needs past prices, and answer "
                        "from the window's figures, never from memory."),
        "input_schema": {"type": "object", "properties": {
            "ticker": _TICKER_PROP,
            "period": {"type": "string", "enum": ["1m", "3m", "6m", "ytd", "1y", "2y", "5y"]},
            "interval": {"type": "string", "enum": ["daily", "weekly"],
                         "description": "daily unless the window is 2y or longer."}},
            "required": ["ticker", "period"], "additionalProperties": False},
    },
    {
        "name": "get_filings",
        "description": ("The company's recent notable SEC filings, newest first (annual and quarterly reports, current "
                        "reports with their item numbers, proxies and similar), each with its filing date and a link "
                        "to the document, from SEC EDGAR. Call it for questions about what a company has filed or "
                        "disclosed recently, or when its latest report was filed."),
        "input_schema": {"type": "object", "properties": {
            "ticker": _TICKER_PROP,
            "limit": {"type": "integer", "minimum": 1, "maximum": 20,
                      "description": "How many filings, 10 unless the question needs more."}},
            "required": ["ticker"], "additionalProperties": False},
    },
    {
        "name": "get_financials",
        "description": ("Quarterly revenue and diluted EPS exactly as the company filed them in XBRL with the SEC, "
                        "with trailing twelve months and year-on-year growth, for up to the last 12 quarters. Call "
                        "it when the question needs reported results over time (\"how has revenue grown\", \"what "
                        "did they earn last quarter\") rather than Optic's long-term model (get_fundamentals)."),
        "input_schema": {"type": "object", "properties": {"ticker": _TICKER_PROP},
                         "required": ["ticker"], "additionalProperties": False},
    },
]
TOOL_NAMES = [s["name"] for s in SPECS]
PORTFOLIO_PARTS = ("summary", "exposure", "events", "performance", "scorecard", "options", "briefing")


def definitions() -> List[Dict[str, Any]]:
    """The tool list for a streamed request: eager input streaming on, so inputs are validated here."""
    return [dict(spec, eager_input_streaming=True) for spec in SPECS]


# ---------------------------------------------------------------------------------------- validation
class InvalidInput(ValueError):
    pass


def _ticker(raw: Any) -> str:
    sym = str(raw or "").strip().upper()
    # A share class as people write it (BRK.B) is Yahoo's BRK-B; asked as written, every tool answered that the
    # feed had no data for one of the largest companies listed (investor audit, 2026-10-27). Suffixes such as
    # SHOP.TO are not a class and are left alone.
    sym = re.sub(r"^([A-Z]{1,5})[./]([AB])$", r"\1-\2", sym)
    if not TICKER.match(sym):
        raise InvalidInput("Not a symbol: {!r}.".format(str(raw)[:40]))
    return sym


def validate(name: str, raw: Any) -> Dict[str, Any]:
    """The cleaned input for a tool, or InvalidInput with what is wrong."""
    if name not in TOOL_NAMES:
        raise InvalidInput("There is no tool called {!r}.".format(str(name)[:40]))
    args = raw if isinstance(raw, dict) else {}
    spec = next(s for s in SPECS if s["name"] == name)
    allowed = set(spec["input_schema"]["properties"])
    extra = set(args) - allowed
    if extra:
        raise InvalidInput("Unexpected input: {}.".format(", ".join(sorted(extra))))
    out: Dict[str, Any] = {}
    if "ticker" in allowed:
        out["ticker"] = _ticker(args.get("ticker"))
    if name == "get_options":
        exps = args.get("expiries") or []
        if not isinstance(exps, list) or len(exps) > 4 or not all(isinstance(e, str) and DATE.match(e) for e in exps):
            raise InvalidInput("expiries must be up to four YYYY-MM-DD dates.")
        out["expiries"] = exps or None
    if name == "get_chart_levels":
        tf = args.get("timeframe")
        if tf not in ("day", "swing", "long", "both"):
            raise InvalidInput("timeframe must be day, swing, long or both.")
        out["timeframe"] = tf
    if name == "get_assessment":
        mode = args.get("mode")
        if mode not in ("long_term", "swing", "pre_earnings", "post_earnings", "combined"):
            raise InvalidInput("mode must be long_term, swing, pre_earnings, post_earnings or combined.")
        out["mode"] = mode
    if name == "compare":
        tks = args.get("tickers")
        if not isinstance(tks, list) or not 2 <= len(tks) <= 4:
            raise InvalidInput("tickers must list two to four symbols.")
        out["tickers"] = list(dict.fromkeys(_ticker(t) for t in tks))
        if len(out["tickers"]) < 2:
            raise InvalidInput("tickers must name at least two different symbols.")
    if name == "get_my_portfolio":
        part = args.get("part")
        if part not in PORTFOLIO_PARTS:
            raise InvalidInput("part must be one of {}.".format(", ".join(PORTFOLIO_PARTS)))
        out["part"] = part
    if name == "screen_stocks":
        req = re.sub(r"\s+", " ", str(args.get("request") or "")).strip()
        if not req or len(req) > 200:
            raise InvalidInput("request must be a description in words, 1 to 200 characters.")
        out["request"] = req
    if name == "lookup_company":
        query = re.sub(r"\s+", " ", str(args.get("query") or "")).strip()
        if not query or len(query) > 60:
            raise InvalidInput("query must be a name or symbol, 1 to 60 characters.")
        out["query"] = query
    if name == "get_price_history":
        if args.get("period") not in ("1m", "3m", "6m", "ytd", "1y", "2y", "5y"):
            raise InvalidInput("period must be 1m, 3m, 6m, ytd, 1y, 2y or 5y.")
        interval = args.get("interval") or ("weekly" if args["period"] in ("2y", "5y") else "daily")
        if interval not in ("daily", "weekly"):
            raise InvalidInput("interval must be daily or weekly.")
        out.update(period=args["period"], interval=interval)
    if name == "get_filings":
        limit = args.get("limit", 10)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 20:
            raise InvalidInput("limit must be a whole number from 1 to 20.")
        out["limit"] = limit
    return out


def status_words(name: str, args: Dict[str, Any]) -> str:
    """What the reader sees while a tool runs."""
    t = args.get("ticker", "")
    return {
        "get_quote": "Checking {}'s quote".format(t),
        "get_options": "Checking {}'s options data".format(t),
        "get_chart_levels": "Reading {}'s chart levels".format(t),
        "get_fundamentals": "Reading {}'s financials".format(t),
        "get_valuation": "Running {}'s fair-value model".format(t),
        "get_earnings": "Reading {}'s earnings".format(t),
        "get_news": "Reading the latest {} news".format(t),
        "get_market": "Reading the market",
        "compare": "Comparing {}".format(", ".join(args.get("tickers") or [])),
        "get_assessment": "Running Optic's framework on {}".format(t),
        "screen_stocks": "Screening stocks",
        "get_my_watchlists": "Reading your watchlists",
        "get_my_portfolio": "Reading your linked portfolio ({})".format(args.get("part") or "summary"),
        "lookup_company": "Looking up {}".format(args.get("query") or "the company"),
        "get_price_history": "Reading {}'s price history".format(t),
        "get_filings": "Reading {}'s SEC filings".format(t),
        "get_financials": "Reading {}'s reported results".format(t),
    }.get(name, "Looking that up")


# ------------------------------------------------------------------------------------------ trimming
def _num(x: Any, nd: int = 4) -> Any:
    if isinstance(x, float):
        return round(x, nd)
    return x


def trim(obj: Any, depth: int = 0, list_max: int = 8, str_max: int = 500, cut: Optional[List[str]] = None,
         path: str = "") -> Any:
    """A smaller copy: lists cut, long strings cut, floats rounded, deep nesting summarised. Each list it cuts is
    noted in `cut` ("sectors: 8 of 11"), so the result can say it is partial."""
    if isinstance(obj, dict):
        if depth > 5:
            return "{...}"
        return {k: trim(v, depth + 1, list_max, str_max, cut, "{}.{}".format(path, k) if path else str(k))
                for k, v in obj.items() if not str(k).startswith("_") and v not in (None, "", [], {})}
    if isinstance(obj, list):
        if cut is not None and len(obj) > list_max:
            cut.append("{}: {} of {}".format(path or "list", list_max, len(obj)))
        return [trim(v, depth + 1, list_max, str_max, cut, path) for v in obj[:list_max]]
    if isinstance(obj, str):
        return obj if len(obj) <= str_max else obj[:str_max] + "..."
    return _num(obj)


def fit(obj: Any, limit: int = RESULT_CHARS) -> Any:
    """Trim harder until the JSON fits `limit` characters. What was cut is said in `left_out_to_fit`, which the
    result's `meta` turns into `partial` (post-demo Phase 08: lists were cut to eight or fewer without a word, so a
    market read showed 8 of the 11 sectors as if they were all of them)."""
    for lm, sm in ((8, 500), (5, 300), (3, 200), (2, 120), (1, 80)):
        cut: List[str] = []
        out = trim(obj, list_max=lm, str_max=sm, cut=cut)
        if cut and isinstance(out, dict):
            # with what an earlier step already left out (shrink's dropped parts), not in place of it
            prior = [x for x in (out.get("left_out_to_fit") or []) if isinstance(x, str)]
            out["left_out_to_fit"] = (prior + [c for c in sorted(set(cut)) if c not in prior and not c.startswith("left_out_to_fit")])[:12]
        if len(json.dumps(out, default=str)) <= limit:
            return out
    # the last resort keeps what the result is and when it is from
    keep = {k: obj.get(k) for k in ("status", "source", "as_of", "as_of_utc") if isinstance(obj, dict) and obj.get(k)}
    text = json.dumps(trim(obj, list_max=1, str_max=60), default=str)
    return dict(keep, truncated=True, partial=text[:limit - 400])


def _pick(d: Any, *keys: str) -> Dict[str, Any]:
    d = d if isinstance(d, dict) else {}
    return {k: d.get(k) for k in keys if d.get(k) not in (None, "", [], {})}


DELAY_NOTE = ("Delayed quote: Yahoo Finance prices can run up to 15 minutes behind during the session; outside it the "
              "price is the last close or an extended-hours print.")


def et(stamp: Any) -> Any:
    """An ISO timestamp as Eastern time for the model ("Oct 15, 4:02 PM ET"). The feed's times are UTC, and
    the live answer read a post-market time of 20:01+00:00 as "8:01 PM ET" at 4:20 PM (2026-10-15)."""
    if not isinstance(stamp, str) or "T" not in stamp:
        return stamp
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        t = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        if t.tzinfo is None:
            return stamp
        local = t.astimezone(ZoneInfo("America/New_York"))
        return local.strftime("%b %d, %I:%M %p ET").replace(" 0", " ")
    except (ValueError, ImportError):
        return stamp


def compact_quote(q: Dict[str, Any]) -> Dict[str, Any]:
    body = _pick(q, "ticker", "name", "price", "change", "change_pct", "prev_close", "open", "day_high", "day_low",
                 "volume", "avg_volume", "market_state", "pre_market_price", "pre_market_change_pct",
                 "pre_market_time", "post_market_price", "post_market_change_pct", "post_market_time",
                 "fifty_two_high", "fifty_two_low", "market_cap", "trailing_pe", "forward_pe", "sector", "industry")
    for key in ("pre_market_time", "post_market_time"):
        if key in body:
            body[key] = et(body[key])
    # The trade's own time. `as_of` on a Yahoo quote is when Optic fetched it, which on a delayed feed is fifteen
    # minutes or a whole weekend after the price was set; it was reported as the quote's time (milo-upgrade 795a766,
    # 2026-10-25; post-demo Phase 08).
    source = str(q.get("quote_source") or "")
    realtime = source.startswith("tradier (real-time)")
    # Tradier overlays its price on Yahoo's quote and keeps Yahoo's `trade_time`, which is then the delayed
    # print's time, not this price's; its own `as_of` is the fetch of a real-time quote (app/providers/tradier.py).
    stamp = q.get("as_of") if realtime else (q.get("trade_time") or q.get("as_of") or q.get("market_time"))
    out = {"source": "Tradier quote (labelled real-time by the provider)" if realtime else "Yahoo Finance quote (delayed)",
           "as_of": et(stamp), "as_of_utc": stamp,
           "as_of_is": ("when Optic fetched the real-time quote" if realtime else "the trade's time" if q.get("trade_time")
                        else "when Optic fetched it (the feed gave no trade time)"),
           "freshness_note": None if realtime else DELAY_NOTE, "quote": body,
           "currency": q.get("currency")}
    if q.get("delayed_minutes") is not None and not realtime:
        out["delayed_minutes"] = q.get("delayed_minutes")
    return {k: v for k, v in out.items() if v is not None}


def compact_options(snap: Dict[str, Any], limit: int = RESULT_CHARS) -> Dict[str, Any]:
    """The Options tab's analytics, in the shape an options question needs."""
    q = snap.get("quote") or {}
    gex = snap.get("gex") if isinstance(snap.get("gex"), dict) else {}
    flow = snap.get("flow") if isinstance(snap.get("flow"), dict) else {}
    greeks = snap.get("greeks") if isinstance(snap.get("greeks"), dict) else {}
    vs = snap.get("vol_surface") if isinstance(snap.get("vol_surface"), dict) else {}
    exp = snap.get("expiries") if isinstance(snap.get("expiries"), dict) else {}
    missing = [k for k in ("gex", "flow", "greeks", "vol_surface") if not snap.get(k) or (
        isinstance(snap.get(k), dict) and snap[k].get("error"))]
    profile = gex.get("profile") if isinstance(gex.get("profile"), dict) else {}
    flip = None
    if profile:
        if profile.get("flip_point") is not None:
            flip = {"flip_point": profile.get("flip_point"), "distance_pct": profile.get("flip_distance_pct"),
                    "direction": profile.get("flip_direction")}
        else:
            flip = {"flip_point": None, "note": "Net GEX does not change sign anywhere in the modeled price range, "
                                                "so there is no flip to report."}
    strikes = gex.get("by_strike") if isinstance(gex.get("by_strike"), list) else []
    top = sorted((s for s in strikes if isinstance(s, dict)),
                 key=lambda s: -abs(s.get("net_gex") or s.get("gex") or 0))[:6]
    out = {
        "source": "Optic's Options-tab analytics, computed from the {} option chain".format(
            snap.get("data_source") or "delayed"),
        # The underlying's trade time where the feed gives one: `as_of` is when Optic fetched the snapshot, which
        # read as Sunday night for Friday's chain (milo-upgrade evaluation, 2026-10-25; post-demo Phase 08).
        "freshness": {"quote_time": et(q.get("trade_time") or q.get("as_of")), "quote_as_of_utc": q.get("trade_time") or q.get("as_of"),
                      "quote_time_is": "the trade's time" if q.get("trade_time") else "when Optic fetched it",
                      "analysis_built": et(snap.get("generated_at")),
                      "market_state": q.get("market_state"), "note": DELAY_NOTE + (
                          " The chain is as delayed as the quote; open interest is the exchange's count from "
                          "the previous session.")},
        "underlying": dict(_pick(q, "ticker", "price", "change_pct", "market_state", "post_market_price",
                                 "pre_market_price"), **{k: et(q[k]) for k in ("post_market_time", "pre_market_time")
                                                         if q.get(k)}),
        "expiries": {"analysed": exp.get("used"), "available": (exp.get("available") or [])[:12],
                     "available_count": len(exp.get("available") or []),
                     "default_rule": ("Without named expiries, the Options tab's default: up to four expiries, "
                                      "the ones nearest 7, 21, 35 and 60 days out and at least two days away.")},
        "flow_proxy": dict(_pick(flow, "method", "stance", "flow_score", "volume", "open_interest", "premium",
                                 "new_positions", "moneyness", "iv_skew", "notes"),
                           unusual=(flow.get("unusual") or [])[:5],
                           caveat=("A volume and open-interest proxy from the chain. It does not observe who bought "
                                   "or sold (no trade tape), whether a trade opened or closed a position, or who "
                                   "holds it. `premium` is time value traded on either side. `new_positions` (an "
                                   "old key name) is only volume above the previous session's open interest, "
                                   "which same-day round trips also produce: never call it new or opening "
                                   "positions, buying, sweeps or institutional activity.")),
        "dealer_gamma": dict(_pick(gex, "assumption", "spot", "expiries_used", "excluded_contracts", "inputs"),
                             totals=gex.get("totals"), regime=_pick(gex.get("regime"), "state", "note"),
                             levels=gex.get("levels"), flip=flip, by_expiry=gex.get("by_expiry"),
                             largest_strikes=top,
                             definitions=("Call wall: the strike with the largest positive gamma exposure; put wall: "
                                          "the largest negative; gamma pin: the largest absolute; all estimates under "
                                          "the stated dealer-positioning assumption.")),
        "greeks": _pick(greeks, "atm_greeks", "second_order", "delta"),
        "volatility": dict(_pick(vs, "iv30", "term", "event", "quote_states"),
                           iv_rank=snap.get("iv_rank"), iv_vs_realised=snap.get("iv_hv")),
        "expiry_context": snap.get("expiry_context"),
        "caveats": [c for c in (snap.get("data_caveat"), snap.get("liquidity_method")) if c],
    }
    if gex.get("error"):
        out["dealer_gamma"] = {"unavailable": gex.get("error")}
    if missing:
        out["status"] = "partial"
        out["missing"] = missing
    return shrink(out, OPTIONS_OPTIONAL, limit)


# What an options read can lose to fit, least needed first. The expiries analysed, the levels, the totals,
# the flip and the flow counts are never cut: a summary that listed three expiries for a read computed on
# four misreported its own scope (found comparing with the Options tab, 2026-10-15).
OPTIONS_OPTIONAL = [("expiry_context",), ("greeks", "second_order"), ("volatility", "quote_states"),
                    ("flow_proxy", "moneyness"), ("flow_proxy", "unusual"), ("volatility", "term"),
                    ("dealer_gamma", "inputs"), ("dealer_gamma", "by_expiry"), ("flow_proxy", "premium"),
                    ("flow_proxy", "new_positions"), ("expiries", "available"), ("dealer_gamma", "largest_strikes"),
                    ("greeks", "atm_greeks")]


def shrink(out: Dict[str, Any], optional: List[Tuple[str, ...]], limit: int = RESULT_CHARS) -> Dict[str, Any]:
    """Drop optional parts, least needed first, until the JSON fits; the rest is never truncated.
    Bulky lists inside what stays are only shortened when every optional part is already gone."""
    cut: List[str] = []
    out = trim(out, list_max=40, str_max=600, cut=cut)
    dropped = sorted(set(cut))
    for path in optional:
        if len(json.dumps(out, default=str)) <= limit:
            break
        node = out
        for key in path[:-1]:
            node = node.get(key) if isinstance(node, dict) else None
        if isinstance(node, dict) and path[-1] in node:
            node.pop(path[-1])
            dropped.append(".".join(path))
    if dropped:
        out["left_out_to_fit"] = dropped
    if len(json.dumps(out, default=str)) > limit:
        out = fit(out, limit)
    return out


_OPTIONS_Q = re.compile(r"\b(options?|calls?|puts?|call/put|put/call|flow|walls?|gamma|gex|vanna|vex|greeks?|delta|"
                        r"theta|vega|implied|iv|skew|straddle|strangle|expir\w*|strikes?|open interest|0 ?dte|"
                        r"positioning|dealers?)\b", re.I)


def compact_snapshot(snap: Dict[str, Any], question: str = "", limit: int = RESULT_CHARS) -> Dict[str, Any]:
    """A named ticker's snapshot (main._swing_snapshot), summarised for CONTEXT: the quote, the technicals'
    headline, the score and what is coming always; the Options tab's analytics in full when the question is
    about options, and a one-line gamma read otherwise. Fitted to `limit` characters, so it is never the
    section the budget drops whole."""
    q = snap.get("quote") or {}
    out: Dict[str, Any] = {
        "quote": compact_quote(q),
        "technicals": trim(snap.get("technicals"), list_max=4, str_max=200),
        "verdict": trim(snap.get("verdict"), list_max=4, str_max=200),
        "whats_next": trim(snap.get("whats_next"), list_max=5, str_max=200),
        "next_earnings_date": snap.get("next_earnings_date"),
        "built_at": snap.get("generated_at"),
    }
    if _OPTIONS_Q.search(question or ""):
        out["options"] = compact_options(snap, limit=int(limit * 0.7))
    else:
        gex = snap.get("gex") if isinstance(snap.get("gex"), dict) else {}
        out["options_headline"] = {"regime": (gex.get("regime") or {}).get("state"), "levels": gex.get("levels"),
                                   "note": "The full options read is one get_options call away."}
    # Over the limit, the general parts go before the options read is touched.
    return shrink(out, [("whats_next",), ("verdict",), ("technicals",)], limit)


def compact_levels(block: Dict[str, Any], tech: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    out = {"source": "Optic's support/resistance and trend-line rules over Yahoo Finance daily bars",
           "levels": {k: v for k, v in (block or {}).items() if k != "chart_tag"}}
    if tech:
        out["technicals"] = tech
    if block and block.get("chart_tag"):
        out["chart_tag"] = block["chart_tag"]
    return fit(out)


def compact_generic(source: str, payload: Any, as_of: Optional[str] = None) -> Dict[str, Any]:
    stamp = as_of or (payload.get("generated_at") if isinstance(payload, dict) else None)
    return fit({"source": source, "as_of": et(stamp), "as_of_utc": stamp, "data": payload})


def compact_news(payload: Dict[str, Any]) -> Dict[str, Any]:
    """The news panel's headlines. It read `score`, `sentiment` and `catalyst`, while app/news.py writes
    `sentiment_score`, `tone` and `catalysts` (and `overall_tone`, `net_sentiment` for the list), so Optic's score
    never reached Milo; and its time was the first headline's, which is the most important, not the newest
    (post-demo Phase 08, from the tool audit). The older keys are still read for other callers' shapes."""
    items = []
    for h in (payload.get("articles") or payload.get("headlines") or payload.get("items") or [])[:10]:
        if isinstance(h, dict):
            items.append(_pick(h, "title", "publisher", "published", "age_hours", "sentiment_score", "tone", "tier",
                               "catalysts", "about_company", "score", "sentiment", "catalyst", "url"))
    newest = max((str(i["published"]) for i in items if i.get("published")), default=None)
    out = {"source": "Yahoo Finance headlines, scored by Optic's word list (not read for meaning)",
           "as_of": payload.get("generated_at") or newest, "fetched_at": payload.get("fetched_at"),
           "summary": _pick(payload, "overall_tone", "net_sentiment", "article_count", "tier_counts", "score", "tone",
                            "summary", "counts", "catalyst_summary", "times_note"),
           "headlines": items}
    held = payload.get("held")
    if isinstance(held, dict):
        out["stale"] = True
        out["stale_note"] = held.get("note") or "The feed came back empty just now; these are its earlier stories."
    return fit({k: v for k, v in out.items() if v is not None})


def compact_valuation(v: Dict[str, Any]) -> Dict[str, Any]:
    """The fair-value workspace, led by what a question about value turns on; its 57,000-character inputs
    block and the three-statement model stay out (they are the workspace's working, not the answer)."""
    out = {"source": "Optic's fair-value workspace (SEC filings, Yahoo Finance)",
           "as_of": v.get("generated_at"), "valuation_date": v.get("valuation_date"),
           "note": "The model's value is what its assumptions imply, never a price target.",
           "dcf": _pick(v.get("dcf"), "per_share", "upside", "margin_of_safety", "enterprise_value", "equity_value",
                        "terminal_share", "discount_rate", "incremental_return", "terminal", "wacc", "checks"),
           **{k: v.get(k) for k in ("ticker", "name", "available", "market", "base", "classification",
                                     "assumptions", "scenarios", "scenario_text", "reverse", "sensitivity",
                                     "tornado", "what_ifs", "dividends", "cost_of_equity") if v.get(k) is not None}}
    return shrink(out, [("what_ifs",), ("tornado",), ("sensitivity",), ("classification",), ("dividends",),
                        ("scenario_text",), ("assumptions",)])


# ------------------------------------------------------------------------------------------- freshness
# Every tool result carries `meta`: where it came from, what time it describes, its units, and four flags a
# reader would ask about (delayed, stale, partial, unavailable), so Milo can say how far to trust a figure
# without inferring it from the payload (milo-upgrade 795a766, 2026-10-25; post-demo Phase 08). True and False
# are findings; None means the flag does not apply to that kind of data (a filing is not "delayed").

UNITS: Dict[str, Dict[str, str]] = {
    "get_quote": {"prices": "the quote currency (`currency`)", "change_pct": "percent", "volume": "shares",
                  "market_cap": "the quote currency"},
    "get_options": {"prices and strikes": "USD", "gex": "USD of dealer hedging per 1% move", "iv": "annualised, "
                    "as a decimal unless labelled percent", "volume and open_interest": "contracts"},
    "get_chart_levels": {"levels": "the quote currency", "rsi": "0 to 100", "atr_pct": "percent"},
    "get_price_history": {"prices": "the quote currency (`currency`)", "change_pct, max_drawdown_pct, "
                          "realised_vol_annualised_pct": "percent", "volume": "shares"},
    "get_fundamentals": {"money": "the company's reporting currency as Yahoo gives it", "margins and growth": "as labelled"},
    "get_valuation": {"value_per_share and price": "the quote currency", "rates": "decimals unless labelled percent"},
    "get_earnings": {"eps": "the quote currency per share", "moves": "percent"},
    "get_financials": {"revenue": "USD as filed", "eps": "USD per diluted share as filed", "yoy": "percent"},
    "get_market": {"levels": "each instrument's own units", "changes": "percent"},
    "compare": {"returns": "percent", "scores": "0 to 100"},
    "get_filings": {}, "get_news": {}, "lookup_company": {},
    "get_assessment": {"grades": "framework labels, not probabilities"},
    "screen_stocks": {"returns": "percent", "price": "USD"},
    "get_my_watchlists": {}, "get_my_portfolio": {"money": "each account's currency, combined in USD where stated",
                                                  "weights": "percent"},
}
# Tools whose figures come from the delayed price feed.
_FEED = ("get_quote", "get_options", "get_chart_levels", "get_price_history", "get_market", "compare", "screen_stocks")
_UNAVAILABLE = ("unavailable", "not_found", "unsupported", "timeout", "error", "invalid_input", "limit")
_COPY_SOURCES = ("get_filings", "get_financials", "lookup_company")


def _parse(stamp: Any) -> Optional[datetime]:
    if not isinstance(stamp, str) or not stamp:
        return None
    try:
        t = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def describe(name: str, result: Any, is_error: bool, now: Optional[datetime] = None,
             session_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The `meta` block for one tool result."""
    r = result if isinstance(result, dict) else {}
    now = now or datetime.now(timezone.utc)
    status = str(r.get("status") or ("unavailable" if is_error else "ok"))
    st = session_state
    if st is None:
        try:
            from . import session as market_session
            st = market_session.state(now)
        except Exception:                                           # noqa: BLE001 - freshness is best effort
            st = {}
    notes: List[str] = []
    realtime = "real-time" in str(r.get("source") or "")
    delayed: Optional[bool] = None
    if name in _FEED:
        delayed = not realtime
        if name == "get_quote" and r.get("delayed_minutes") is not None:
            delayed = float(r["delayed_minutes"]) > 0
    stale: Optional[bool] = bool(r["stale"]) if isinstance(r.get("stale"), bool) else None
    # Sources that answer from a kept copy when they cannot be reached say so with `stale`; when they do not, the
    # copy is today's, which is a finding (False), not "does not apply".
    if stale is None and name in _COPY_SOURCES and status == "ok":
        stale = False
    as_of = r.get("as_of_utc") or _as_of(r)
    close = _parse(((st or {}).get("last_close") or {}).get("at"))
    if name == "get_quote" and status == "ok":
        t = _parse(r.get("as_of_utc"))
        if t is not None:
            if st.get("is_regular"):
                stale = (now - t).total_seconds() > 45 * 60
                if stale:
                    notes.append("The quote's time is more than 45 minutes old with the regular session open.")
            elif close is not None:
                stale = t < close - timedelta(minutes=10)
                if stale:
                    notes.append("The quote's time is before the last regular close.")
    if name == "get_price_history" and status == "ok" and isinstance(r.get("as_of"), str) and close is not None:
        last_bar = r["as_of"][:10]
        if r.get("interval") == "weekly":
            stale = (close.date() - datetime.strptime(last_bar, "%Y-%m-%d").date()).days > 7
        else:
            # The newest bar should be the last completed session's, or today's while a session runs.
            stale = last_bar < close.date().isoformat()
            if st.get("is_regular"):
                notes.append("The regular session is open: today's bar, if present, is still forming.")
    partial = bool(r.get("left_out_to_fit") or r.get("truncated") or status == "partial"
                   or (isinstance(r.get("missing"), list) and r.get("missing")))
    if r.get("left_out_to_fit"):
        notes.append("Left out to fit: {}.".format(", ".join(map(str, r["left_out_to_fit"]))))
    unavailable = bool(is_error or status in _UNAVAILABLE)
    if unavailable:
        delayed = None                  # nothing came back, so there is no figure to be delayed
    out = {"source": r.get("source"), "as_of": as_of,
           "retrieved_at": now.isoformat(timespec="seconds"), "units": UNITS.get(name, {}),
           "delayed": delayed, "stale": stale, "partial": partial, "unavailable": unavailable}
    if delayed and name in _FEED:
        mins = r.get("delayed_minutes")
        out["delay"] = ("about {} minutes per the feed".format(int(float(mins))) if mins is not None
                        else "about 15 minutes during the session (Yahoo Finance)")
    if notes:
        out["notes"] = notes
    return out


# ------------------------------------------------------------------------------------------- toolbox
@dataclass
class Record:
    tool: str
    args: Dict[str, Any]
    ok: bool
    status: str
    seconds: float
    source: Optional[str] = None
    as_of: Optional[str] = None
    error: Optional[str] = None
    retrieved_at: Optional[str] = None

    def symbols(self) -> List[str]:
        one = self.args.get("ticker")
        return [str(s).upper() for s in ([one] if one else (self.args.get("tickers") or []))]

    def data_type(self) -> str:
        return {"get_quote": "quote", "get_options": "options analytics", "get_chart_levels": "chart levels",
                "get_fundamentals": "long-term model", "get_valuation": "fair-value model",
                "get_earnings": "earnings panel", "get_news": "news", "get_market": "market read",
                "compare": "comparison", "get_assessment": "research framework",
                "screen_stocks": "screener", "get_my_watchlists": "your watchlists",
                "get_my_portfolio": "your portfolio ({})".format(self.args.get("part") or "summary"),
                "lookup_company": "symbol lookup",
                "get_price_history": "price history ({}, {})".format(self.args.get("period"), self.args.get("interval")),
                "get_filings": "SEC filings", "get_financials": "reported revenue and EPS",
                }.get(self.tool, self.tool)

    def label(self) -> str:
        return "{} {}".format(", ".join(self.symbols()), self.data_type()).strip()

    def public(self) -> Dict[str, Any]:
        """What the reader is shown under the answer: no inputs beyond the symbol, no internals.

        Each record names its instrument, its kind of data, when the data was observed (`as_of`, the
        quote's own time where the result carries one) and when Milo fetched it (`retrieved_at`): an
        NVDA answer asked from AAPL's page was labelled only "About AAPL" (pitch audit, 2026-10-22)."""
        return {"label": self.label(), "symbols": self.symbols(), "data_type": self.data_type(),
                "source": self.source, "as_of": self.as_of, "retrieved_at": self.retrieved_at,
                "ok": self.ok, "status": self.status}


@dataclass
class Toolbox:
    """The tools for one answer: the runners, the limits, what was called."""
    runners: Dict[str, Callable[..., Any]]
    max_rounds: int = MAX_ROUNDS
    max_calls: int = MAX_CALLS
    call_timeout: float = CALL_TIMEOUT
    total_budget: float = TOTAL_BUDGET
    records: List[Record] = field(default_factory=list)
    _memo: Dict[str, Tuple[str, bool]] = field(default_factory=dict)
    _spent: float = 0.0

    def definitions(self) -> List[Dict[str, Any]]:
        return [d for d in definitions() if d["name"] in self.runners]

    @property
    def calls(self) -> int:
        return len(self.records)

    def exhausted(self) -> Optional[str]:
        if self.calls >= self.max_calls:
            return "the call limit for one answer ({}) is reached".format(self.max_calls)
        if self._spent >= self.total_budget:
            return "the time budget for one answer ({:.0f}s) is spent".format(self.total_budget)
        return None

    async def run(self, name: str, raw_input: Any) -> Tuple[str, bool, Dict[str, Any]]:
        """(content for the tool_result, is_error, cleaned args)."""
        try:
            args = validate(name, raw_input)
        except InvalidInput as exc:
            self.records.append(Record(name, {}, False, "invalid", 0.0, error=str(exc)))
            return json.dumps({"status": "invalid_input", "error": str(exc)}), True, {}
        if name not in self.runners:
            return json.dumps({"status": "unsupported", "error": "That tool is not available here."}), True, args
        key = name + json.dumps(args, sort_keys=True)
        if key in self._memo:
            content, is_error = self._memo[key]
            return content, is_error, args
        stop = self.exhausted()
        if stop:
            return json.dumps({"status": "limit", "error": "Not run: {}. Answer from what you have and say what "
                                                           "is missing.".format(stop)}), True, args
        t0 = time.monotonic()
        try:
            budget = min(self.call_timeout, max(1.0, self.total_budget - self._spent))
            result = await asyncio.wait_for(asyncio.to_thread(self.runners[name], **args), timeout=budget)
            status = (result or {}).get("status", "ok") if isinstance(result, dict) else "ok"
            body = {"status": status, **(result if isinstance(result, dict) else {"data": result})}
            is_error = status in ("unavailable", "not_found", "unsupported")
            body["meta"] = describe(name, body, is_error)
            content = json.dumps(body, default=str)
            rec = Record(name, args, not is_error, status, time.monotonic() - t0,
                         source=(result or {}).get("source") if isinstance(result, dict) else None,
                         as_of=_as_of(result))
        except asyncio.TimeoutError:
            content, is_error = json.dumps({"status": "unavailable", "error": (
                "The data source did not answer within {:.0f} seconds. Say it could not be retrieved this time; "
                "do not guess the figures.".format(self.call_timeout)),
                "meta": describe(name, {"status": "timeout"}, True)}), True
            rec = Record(name, args, False, "timeout", time.monotonic() - t0, error="timeout")
        except Exception as exc:                                    # noqa: BLE001 - a provider failure, reported
            content, is_error = json.dumps({"status": "unavailable", "error": (
                "The data source failed ({}). Say it could not be retrieved this time; do not guess the "
                "figures.".format(type(exc).__name__)), "meta": describe(name, {"status": "error"}, True)}), True
            rec = Record(name, args, False, "error", time.monotonic() - t0, error=type(exc).__name__)
        self._spent += rec.seconds
        rec.retrieved_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.records.append(rec)
        self._memo[key] = (content, is_error)
        return content, is_error, args

    def retrieved(self) -> List[Dict[str, Any]]:
        return [r.public() for r in self.records if r.status != "invalid"]


def _as_of(result: Any) -> Optional[str]:
    if not isinstance(result, dict):
        return None
    fr = result.get("freshness") if isinstance(result.get("freshness"), dict) else {}
    return fr.get("quote_as_of_utc") or result.get("as_of_utc") or result.get("as_of")
