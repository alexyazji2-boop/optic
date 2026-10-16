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
  research framework, the screener, and the signed-in reader's own watchlists.
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
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

TICKER = re.compile(r"^[A-Z0-9][A-Z0-9.\-^=]{0,11}$")
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
                        "the call/put volume and open-interest flow proxy, dealer gamma exposure (net GEX per "
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
        "description": ("Optic's long-term model for one company: the holding view and its conviction, "
                        "business quality measures (growth, margins, returns on capital, cash conversion, "
                        "balance sheet, dilution), the valuation history against its own record, drawdowns, "
                        "and the weekly levels. Call it for questions about the business, its financials, "
                        "quality, or owning it for years, when CONTEXT lacks them."),
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
    }.get(name, "Looking that up")


# ------------------------------------------------------------------------------------------ trimming
def _num(x: Any, nd: int = 4) -> Any:
    if isinstance(x, float):
        return round(x, nd)
    return x


def trim(obj: Any, depth: int = 0, list_max: int = 8, str_max: int = 500) -> Any:
    """A smaller copy: lists cut, long strings cut, floats rounded, deep nesting summarised."""
    if isinstance(obj, dict):
        if depth > 5:
            return "{...}"
        return {k: trim(v, depth + 1, list_max, str_max) for k, v in obj.items()
                if not str(k).startswith("_") and v not in (None, "", [], {})}
    if isinstance(obj, list):
        return [trim(v, depth + 1, list_max, str_max) for v in obj[:list_max]]
    if isinstance(obj, str):
        return obj if len(obj) <= str_max else obj[:str_max] + "..."
    return _num(obj)


def fit(obj: Any, limit: int = RESULT_CHARS) -> Any:
    """Trim harder until the JSON fits `limit` characters."""
    for lm, sm in ((8, 500), (5, 300), (3, 200), (2, 120), (1, 80)):
        out = trim(obj, list_max=lm, str_max=sm)
        if len(json.dumps(out, default=str)) <= limit:
            return out
    text = json.dumps(trim(obj, list_max=1, str_max=60), default=str)
    return {"truncated": True, "partial": text[:limit - 100]}


def _pick(d: Any, *keys: str) -> Dict[str, Any]:
    d = d if isinstance(d, dict) else {}
    return {k: d.get(k) for k in keys if d.get(k) not in (None, "", [], {})}


DELAY_NOTE = ("Delayed quote: Yahoo Finance prices run about 15 minutes behind during the session; outside it the "
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
    stamp = q.get("as_of") or q.get("market_time")
    return {"source": "Yahoo Finance quote (delayed)", "as_of": et(stamp), "as_of_utc": stamp,
            "freshness_note": DELAY_NOTE, "quote": body}


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
        "freshness": {"quote_time": et(q.get("as_of")), "quote_as_of_utc": q.get("as_of"),
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
                                   "holds it.")),
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
    out = trim(out, list_max=40, str_max=600)
    dropped = []
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
    items = []
    for h in (payload.get("articles") or payload.get("headlines") or payload.get("items") or [])[:10]:
        if isinstance(h, dict):
            items.append(_pick(h, "title", "publisher", "published", "age_hours", "score", "sentiment", "tier",
                               "catalyst", "url"))
    return fit({"source": "Yahoo Finance headlines, scored by Optic's word list (not read for meaning)",
                "as_of": payload.get("generated_at") or (items[0].get("published") if items else None),
                "summary": _pick(payload, "score", "tone", "summary", "counts", "catalyst_summary"),
                "headlines": items})


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

    def label(self) -> str:
        t = self.args.get("ticker") or ", ".join(self.args.get("tickers") or []) or ""
        name = {"get_quote": "quote", "get_options": "options analytics", "get_chart_levels": "chart levels",
                "get_fundamentals": "long-term model", "get_valuation": "fair-value model",
                "get_earnings": "earnings panel", "get_news": "news", "get_market": "market read",
                "compare": "comparison", "get_assessment": "research framework",
                "screen_stocks": "screener", "get_my_watchlists": "your watchlists",
                "get_my_portfolio": "your portfolio ({})".format(self.args.get("part") or "summary")
                }.get(self.tool, self.tool)
        return "{} {}".format(t, name).strip()

    def public(self) -> Dict[str, Any]:
        """What the reader is shown under the answer: no inputs beyond the symbol, no internals."""
        return {"label": self.label(), "source": self.source, "as_of": self.as_of, "ok": self.ok,
                "status": self.status}


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
            content, is_error = json.dumps(body, default=str), status in ("unavailable", "not_found", "unsupported")
            rec = Record(name, args, not is_error, status, time.monotonic() - t0,
                         source=(result or {}).get("source") if isinstance(result, dict) else None,
                         as_of=_as_of(result))
        except asyncio.TimeoutError:
            content, is_error = json.dumps({"status": "unavailable", "error": (
                "The data source did not answer within {:.0f} seconds. Say it could not be retrieved this time; "
                "do not guess the figures.".format(self.call_timeout))}), True
            rec = Record(name, args, False, "timeout", time.monotonic() - t0, error="timeout")
        except Exception as exc:                                    # noqa: BLE001 - a provider failure, reported
            content, is_error = json.dumps({"status": "unavailable", "error": (
                "The data source failed ({}). Say it could not be retrieved this time; do not guess the "
                "figures.".format(type(exc).__name__))}), True
            rec = Record(name, args, False, "error", time.monotonic() - t0, error=type(exc).__name__)
        self._spent += rec.seconds
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
