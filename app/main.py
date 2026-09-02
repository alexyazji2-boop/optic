"""FastAPI backend for Optic Terminal."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import (ai, brief as brief_mod, feeds as feeds_mod, legal,
               news as news_mod, paper, session as session_mod)
from . import snapshots
from . import universe as universe_mod
from . import earnings_week as earnings_week_mod
from . import priority as priority_mod
from . import weekly as weekly_mod
from . import catalysts as catalysts_mod
from . import catalyst_live as catalyst_live_mod
from .analytics import cases as cases_mod
from .analytics import screen as screen_mod
from .analytics import regime as regime_mod
from .analytics import compare as compare_mod
from .analytics import correlation as correlation_mod
from .analytics import global_markets as global_mod
from .analytics import indicators as indicators_mod
from .analytics import patterns as patterns_mod
from .analytics import pe_history as pe_history_mod
from .analytics import pattern_stats as pattern_stats_mod
from .analytics import portfolio_risk as portfolio_risk_mod
from .analytics import evaluate as evaluate_mod
from .analytics import expiries as expiries_mod
from .analytics import scanners as scanners_mod
from .analytics import forex as forex_mod
from . import alerts as alerts_mod
from .analytics import econ as econ_mod
from .analytics import extras as extras_mod
from .analytics import rotation as rotation_mod
from .analytics import stockmaps as stockmaps_mod
from .analytics import trendlines as trendlines_mod
from .analytics import seasonality as seasonality_mod
from .analytics import sector_board as sector_board_mod
from .analytics import sector_confirm as sector_confirm_mod
from .analytics import sentiment as sentiment_mod
from .analytics import defence as defence_mod
from .analytics import filings as filings_mod
from .analytics import earnings as earnings_mod
from .analytics import entry as entry_mod
from .analytics import flow as flow_mod
from .analytics import fundamentals as fundamentals_mod
from .analytics import gex as gex_mod
from .analytics import greeks_panel, longterm, macro as macro_mod
from .analytics import retirement as retirement_mod
from .analytics import sectors as sectors_mod
from .analytics import structure as structure_mod
from .analytics import swing, technicals
from .providers.tradier import TradierProvider
from .providers.yf import PROVIDER as YF_PROVIDER

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def _load_dotenv() -> None:
    """Load KEY=VALUE lines from a .env file next to this project, without
    adding a python-dotenv dependency. Existing env vars always win, so a
    real `export` in the shell still overrides the file."""
    env_path = STATIC_DIR.parent / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()

app = FastAPI(title="Optic Terminal", version="1.0.0")

# ------------------------------------------------------------- open access
#
# No authentication: anyone who can reach this server can use it. That's the
# intended posture for an open demo — there are no accounts and nothing
# user-specific is stored server-side (the Roth tab's holdings live in the
# visitor's own browser and are only ever posted to be computed, never saved).
#
# The one thing that changes this calculus is the assistant: /api/chat and
# /api/research spend real money per call. With no gate, that spend is open to
# anyone with the URL, so a warning is logged at startup rather than silently
# allowing it.
@app.get("/healthz")
async def healthz() -> Dict[str, bool]:
    """Liveness probe for hosting platforms. Deliberately says nothing else."""
    return {"ok": True}


@app.on_event("startup")
async def _warn_if_open_and_paid() -> None:
    if ai.available().get("enabled"):
        logging.getLogger("uvicorn.error").warning(
            "Pulse is enabled and this server has no access control — anyone who "
            "can reach the URL can spend Anthropic credits via /api/chat and "
            "/api/research. Unset ANTHROPIC_API_KEY, or put the server behind "
            "access control, if that isn't intended."
        )


# Zero risk-free rate: for 3-8 week swing options the rate contribution to the
# greeks is smaller than the bid/ask spread, and hard-coding a stale rate would
# be worse than being explicit about the simplification.
RISK_FREE = float(os.environ.get("RISK_FREE_RATE", "0.0"))

# PROVIDER serves the "currently loaded ticker" — quote, chain, expirations,
# history — the calls that actually benefit from being real-time. It becomes
# Tradier automatically when TRADIER_ACCESS_TOKEN is set, falling back to
# yfinance's own instance otherwise (so the app works unchanged with no
# credentials configured). YF_PROVIDER is used explicitly, everywhere, for the
# macro/sector symbol universe (FX pairs, futures, index tickers Tradier can't
# serve) and for company fundamentals/news, which Tradier's API doesn't cover
# at all — freshness doesn't matter for those, and switching PROVIDER should
# never silently break them.
_tradier_token = os.environ.get("TRADIER_ACCESS_TOKEN")
if _tradier_token:
    PROVIDER = TradierProvider(
        token=_tradier_token,
        sandbox=os.environ.get("TRADIER_SANDBOX", "false").strip().lower() == "true",
        fallback=YF_PROVIDER,
    )
else:
    PROVIDER = YF_PROVIDER


def _run(fn, *args, **kwargs):
    """Push blocking provider/analytics work off the event loop."""
    return asyncio.get_running_loop().run_in_executor(None, lambda: fn(*args, **kwargs))


# ------------------------------------------------------------------ assembly


def _swing_snapshot(
    ticker: str,
    expiries: Optional[List[str]],
    max_expiries: int,
    include_macro: bool,
    include_earnings: bool = True,
) -> Dict[str, Any]:
    ticker = ticker.upper().strip()

    quote = PROVIDER.quote(ticker)
    hist = PROVIDER.history(ticker, period="2y", interval="1d")
    if hist is None or hist.empty:
        raise HTTPException(status_code=404, detail="No price data found for '{}'.".format(ticker))

    spot = quote.get("price") or float(hist["Close"].iloc[-1])
    div = quote.get("dividend_yield") or 0.0

    tech = technicals.analyse(hist)
    # Price-location structure: where price sits versus traded volume, the
    # session's pivots, the fast EMA fan, band width against its own history and
    # what the last few candles did. Separate from `tech` because that block
    # answers "what is momentum doing" and this one answers "where are we".
    # Refresh the forming bar from the live quote before deriving levels — the
    # history cache is 5 minutes but the quote is 30 seconds, and every read below
    # except the pivots moves with the last bar.
    session_date = datetime.now(timezone.utc).astimezone(session_mod.ET).date()
    live_hist = structure_mod.with_live_bar(hist, spot, session_date)
    close = live_hist["Close"] if "Close" in live_hist else None
    structure_read = {
        "volume_profile": structure_mod.volume_profile(live_hist),
        "pivots": structure_mod.floor_pivots(hist),
        "ema_stack": structure_mod.ema_stack(close) if close is not None else {"available": False},
        "bandwidth": structure_mod.bandwidth_rank(close) if close is not None else {"available": False},
        "candles": structure_mod.candle_patterns(live_hist),
    }
    news_read = news_mod.analyse(YF_PROVIDER, ticker)

    available_expiries = PROVIDER.expirations(ticker)
    chain = PROVIDER.options_chain(ticker, expiries=expiries, max_expiries=max_expiries)

    gex_read: Dict[str, Any] = {}
    greeks_read: Dict[str, Any] = {}
    flow_read: Dict[str, Any] = {}
    naked_ideas: List[Dict[str, Any]] = []
    strategy_ideas: List[Dict[str, Any]] = []
    exposure: Optional[pd.DataFrame] = None

    if chain is not None and not chain.empty:
        gex_read = gex_mod.analyse(chain, spot, rate=RISK_FREE, div=div)
        exposure = gex_read.pop("_exposure_frame", None)
        if exposure is not None:
            greeks_read = greeks_panel.analyse(exposure, spot)
        flow_read = flow_mod.analyse(chain, spot)
    else:
        note = "No options chain available for {} — equity/technical analysis only.".format(ticker)
        gex_read = {"error": note}
        flow_read = {"error": note}
        greeks_read = {"error": note}

    macro_read: Optional[Dict[str, Any]] = None
    if include_macro:
        try:
            macro_read = macro_mod.analyse(YF_PROVIDER)
        except Exception as exc:  # macro is supporting context, never fatal
            macro_read = {"error": "macro panel unavailable: {}".format(exc)}

    call = swing.verdict(tech, gex_read, flow_read, news_read, macro_read, spot)

    entry_plan: Dict[str, Any] = {"actionable": False, "headline": "No options chain available."}
    if exposure is not None:
        naked_ideas = swing.build_naked_ideas(exposure, spot, call["stance"], tech)
        strategy_ideas = swing.build_strategy_ideas(
            exposure, spot, call["stance"], gex_read, tech,
            news=news_read, quote=quote, history=hist, provider=YF_PROVIDER,
        )
        entry_plan = entry_mod.build_plan(
            exposure, spot, call, tech, gex_read, news_read, rate=RISK_FREE, div=div, history=hist
        )

    try:
        company = fundamentals_mod.analyse(YF_PROVIDER, ticker, quote)
    except Exception as exc:  # company data is context, never fatal
        company = {"error": "fundamentals unavailable: {}".format(exc)}

    # Shown on the Swing tab but never scored. Skipped for tracker scans: it costs
    # three more provider calls per ticker, and over a thirty-name shortlist that
    # is exactly the extra traffic that earns a rate limit — for a panel the
    # ledger doesn't read.
    earnings_momentum: Dict[str, Any] = {"available": False, "reason": "not requested"}
    if include_earnings:
        try:
            earnings_momentum = earnings_mod.momentum(YF_PROVIDER, ticker)
        except Exception as exc:
            earnings_momentum = {"available": False,
                                 "reason": "earnings momentum unavailable: {}".format(exc)}

    if PROVIDER.name == "tradier":
        data_caveat = (
            "Quote and options chain are real-time via Tradier. Greeks are computed locally via "
            "Black-Scholes with a {:.2%} risk-free rate. Company fundamentals and news still come "
            "from yfinance and are not real-time.".format(RISK_FREE)
        )
    else:
        data_caveat = (
            "Quotes are delayed ~15 minutes. Greeks are computed locally via "
            "Black-Scholes with a {:.2%} risk-free rate.".format(RISK_FREE)
        )

    payload = {
        "ticker": ticker,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_source": PROVIDER.name,
        "data_caveat": data_caveat,
        "quote": quote,
        "verdict": call,
        "technicals": tech,
        "structure": structure_read,
        # From `hist`, not `live_hist`. A forming bar has no completed high or
        # low, and letting it stand as a pivot would invent structure that
        # vanishes at the close.
        "patterns": patterns_mod.analyse(hist, spot=spot),
        "gex": gex_read,
        "greeks": greeks_read,
        "flow": flow_read,
        "news": news_read,
        "entry_plan": entry_plan,
        "company": company,
        "earnings_momentum": earnings_momentum,
        "naked_ideas": naked_ideas,
        "strategy_ideas": strategy_ideas,
        "macro": macro_read,
        "disclaimer": legal.SHORT,
        "disclaimer_area": legal.AREAS["swing"],
        "expiries": {
            "available": available_expiries,
            "used": sorted(chain["expiry"].unique().tolist()) if chain is not None and not chain.empty else [],
        },
    }
    # Built last, from the finished payload, so an argument can cite any panel on
    # the page and cannot drift from the numbers it quotes.
    payload["cases"] = cases_mod.build(payload)
    # What has to hold through the close to keep the overnight trend read.
    payload["close_defence"] = defence_mod.for_swing(payload)
    # The company's own recent disclosures. Primary source, and the 8-K item
    # codes are the filer's classification rather than an interpretation.
    payload["filings"] = filings_mod.recent(ticker)
    # Days to expiry, so the dealer-gamma and charm readings can be read against
    # the date they unwind on rather than in isolation.
    payload["expiry_context"] = expiries_mod.context()
    # Whether the group around this name agrees with it. Sector context is the
    # weakest of the claims made about a setup, so it is reported beside the
    # per-name analysis rather than folded into the score.
    try:
        prof = YF_PROVIDER.profile(ticker) or {}
        payload["sector_confirm"] = sector_confirm_mod.build(
            YF_PROVIDER, ticker, prof.get("sector"))
    except Exception as exc:
        logging.getLogger("uvicorn.error").warning(
            "sector confirmation unavailable for %s: %s", ticker, exc)
    return payload


# -------------------------------------------------------------------- routes


# What is actually running, and since when.
#
# Without this there is no way to answer "did my push deploy?" from outside the
# hosting dashboard. Trying to infer it from the asset version does not work:
# that stamp comes from the mtimes of the files in static/, so a commit that
# touches only Python or documentation leaves it unchanged and an unchanged
# stamp is indistinguishable from a deploy that never happened.
#
# Railway injects RAILWAY_GIT_COMMIT_SHA at build time; the other platforms in
# this repo have their own names for it. Absent all of them (a local run) this
# reports "dev", which is the honest answer rather than a guess.
# A function rather than a module constant so it can be tested by setting the
# environment, without reloading app.main — reloading re-registers every startup
# hook and floods the suite with warnings.
def deployed_commit() -> str:
    return (os.environ.get("RAILWAY_GIT_COMMIT_SHA")
            or os.environ.get("SOURCE_VERSION")          # Render
            or os.environ.get("FLY_MACHINE_VERSION")     # Fly
            or "dev")[:12]


_BOOTED_AT = datetime.now(timezone.utc)


@app.get("/api/health")
async def health() -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {
        "status": "ok",
        "provider": PROVIDER.name,
        "realtime_chain": PROVIDER.name == "tradier",
        "assistant": ai.available(),
        "server_time": now.isoformat(),
        "commit": deployed_commit(),
        # Uptime is the other half of the question. A process that restarted
        # minutes ago either just deployed or is crash-looping, and both are
        # things you want to see rather than infer.
        "booted_at": _BOOTED_AT.isoformat(),
        "uptime_seconds": int((now - _BOOTED_AT).total_seconds()),
    }


@app.get("/api/ticker/{ticker}")
async def ticker_analysis(
    ticker: str,
    expiries: Optional[str] = Query(None, description="Comma-separated YYYY-MM-DD expiries"),
    max_expiries: int = Query(4, ge=1, le=10),
    macro: bool = Query(True, description="Include the macro regime panel"),
) -> Dict[str, Any]:
    """Full swing-trading analysis for one ticker."""
    wanted = [e.strip() for e in expiries.split(",") if e.strip()] if expiries else None
    return await _run(_swing_snapshot, ticker, wanted, max_expiries, macro)


@app.get("/api/earnings/{ticker}")
async def earnings_panel(ticker: str) -> Dict[str, Any]:
    """Earnings panel: consensus, surprise history with price reactions, estimate
    revisions, reported and forecast growth, and what the options market charges
    for the event.

    PROVIDER supplies the chain (the implied-move calculation benefits from a
    real-time quote); YF_PROVIDER supplies estimates and statements, which
    Tradier doesn't carry at all.
    """
    def build() -> Dict[str, Any]:
        ticker_u = ticker.upper().strip()
        quote = PROVIDER.quote(ticker_u)
        result = earnings_mod.analyse(PROVIDER, YF_PROVIDER, ticker_u, quote, rate=RISK_FREE)
        result["generated_at"] = datetime.now(timezone.utc).isoformat()
        return result

    return await _run(build)


@app.get("/api/earnings/{ticker}/brief")
async def earnings_brief(ticker: str) -> Dict[str, Any]:
    """A written pre-earnings brief for one name.

    Split from /api/earnings deliberately. The panel's own numbers are computed
    locally in well under a second; a model call is neither that fast nor that
    reliable, and blocking the whole panel on it would mean a slow assistant makes
    the fast data look slow too. The panel renders first and this arrives after.

    Every number the brief discusses is already visible above it, so when this
    returns unavailable the reader loses commentary, not information.
    """
    def build() -> Dict[str, Any]:
        ticker_u = ticker.upper().strip()
        quote = PROVIDER.quote(ticker_u)
        facts = earnings_mod.analyse(PROVIDER, YF_PROVIDER, ticker_u, quote, rate=RISK_FREE)

        # What the company has actually filed. This is the only source here for
        # corporate events, and it is a primary one — an 8-K item code is the
        # filer's own classification. Without it the brief could only discuss
        # estimates, which is not "what the company has been doing".
        try:
            facts["filings"] = filings_mod.recent(ticker_u, limit=8)
        except Exception as exc:
            logging.getLogger("uvicorn.error").warning(
                "earnings brief: filings unavailable for %s: %s", ticker_u, exc)

        # Sector and industry, so the brief can place the company. Explicitly not
        # the business summary: it is marketing copy of unknown vintage, and a
        # model handed it will paraphrase it as though it were current fact.
        try:
            prof = YF_PROVIDER.profile(ticker_u) or {}
            facts["profile"] = {k: prof.get(k) for k in
                                ("name", "sector", "industry", "employees", "country", "kind_label")
                                if prof.get(k) is not None}
        except Exception as exc:
            logging.getLogger("uvicorn.error").warning(
                "earnings brief: profile unavailable for %s: %s", ticker_u, exc)

        brief = ai.write_earnings_brief(ticker_u, facts)
        if not brief:
            status = ai.available()
            return {"available": False,
                    "reason": ("The assistant is not configured, so there is no written "
                               "brief — every figure it would discuss is on the panel above."
                               if status.get("enabled") is not True else
                               "The brief could not be written on this attempt. The panel's "
                               "own numbers are unaffected.")}
        brief["ticker"] = ticker_u
        brief["generated_at"] = datetime.now(timezone.utc).isoformat()
        return brief

    return await _run(build)


@app.get("/api/chain/{ticker}")
async def raw_chain(
    ticker: str,
    expiries: Optional[str] = Query(None),
    max_expiries: int = Query(2, ge=1, le=10),
) -> Dict[str, Any]:
    """Greek-annotated option chain — the raw table behind the panels."""
    wanted = [e.strip() for e in expiries.split(",") if e.strip()] if expiries else None

    def build() -> Dict[str, Any]:
        quote = PROVIDER.quote(ticker.upper())
        spot = quote.get("price")
        if spot is None:
            raise HTTPException(status_code=404, detail="No quote for '{}'.".format(ticker))
        chain = PROVIDER.options_chain(ticker.upper(), expiries=wanted, max_expiries=max_expiries)
        if chain is None or chain.empty:
            raise HTTPException(status_code=404, detail="No options chain for '{}'.".format(ticker))
        frame = gex_mod.compute_exposure(chain, spot, rate=RISK_FREE, div=quote.get("dividend_yield") or 0.0)
        cols = [
            "contract", "expiry", "dte", "strike", "is_call", "bid", "ask", "mid", "last",
            "volume", "open_interest", "iv", "delta", "gamma", "vega", "theta", "gex", "dex",
            "spread_pct",
        ]
        present = [c for c in cols if c in frame.columns]
        table = frame[present].replace({float("nan"): None})
        return {
            "ticker": ticker.upper(),
            "spot": spot,
            "rows": table.to_dict(orient="records"),
        }

    return await _run(build)


@app.get("/api/macro")
async def macro_panel() -> Dict[str, Any]:
    return await _run(macro_mod.analyse, YF_PROVIDER)


@app.get("/api/sectors")
async def sector_panel() -> Dict[str, Any]:
    return await _run(sectors_mod.analyse, YF_PROVIDER)


@app.get("/api/market")
async def market_panel() -> Dict[str, Any]:
    """Macro + sectors together — one call for the market tab.

    Both always run on yfinance (YF_PROVIDER): the symbol universe here is FX
    pairs, futures, and index tickers that a brokerage options API doesn't
    serve. Run sequentially, not gathered — concurrent yfinance batch
    downloads return partially-empty frames rather than failing loudly.
    """
    def build() -> Dict[str, Any]:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "macro": macro_mod.analyse(YF_PROVIDER),
            "sectors": sectors_mod.analyse(YF_PROVIDER),
        }

    return await _run(build)


@app.get("/api/longterm/{ticker}")
async def longterm_panel(ticker: str, indices: bool = Query(False)) -> Dict[str, Any]:
    """Long-run analysis of holding the shares themselves.

    Indices live on their own endpoint and their own tab now — a ten-index,
    ten-year pull is slow and has nothing to do with the loaded ticker, so it
    defaults off rather than riding along with every share request.
    """
    holding = await _run(longterm.analyse_holding, PROVIDER, ticker.upper())
    payload: Dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "holding": holding,
    }
    # Weekly-horizon version of the same question the swing tab asks: which level
    # has to survive the close. Weekly averages, so the honest cadence note rides
    # along with it.
    payload["close_defence"] = defence_mod.for_longterm(holding)
    if indices:
        payload["indices"] = await _run(longterm.analyse_indices, YF_PROVIDER)
    return payload


@app.post("/api/retirement")
async def retirement_panel(payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    """Rules-based Roth IRA model allocation, drift and rebalancing plan.

    POST rather than GET because holdings are an arbitrary-length body, and
    because a portfolio shouldn't end up in a URL, a browser history entry or a
    server access log. Nothing here is persisted — the response is computed and
    discarded, and the browser keeps the only copy.

    Horizon, risk, contribution, holdings and stock candidates are all caller
    inputs; the endpoint holds no opinion about the user's situation. Uses
    YF_PROVIDER because the universe is ETFs on a ten-year clock, where
    real-time pricing is irrelevant.
    """
    def build() -> Dict[str, Any]:
        result = retirement_mod.analyse(
            YF_PROVIDER,
            years=int(payload.get("years") or 30),
            risk=str(payload.get("risk") or "balanced"),
            annual_contribution=float(payload.get("annual") or 0),
            holdings=payload.get("holdings"),
            stock_candidates=payload.get("stock_candidates"),
        )
        result["generated_at"] = datetime.now(timezone.utc).isoformat()
        return result

    return await _run(build)


@app.get("/api/indices")
async def indices_panel() -> Dict[str, Any]:
    return await _run(longterm.analyse_indices, YF_PROVIDER)


@app.get("/api/search")
async def symbol_search(
    q: str = Query("", max_length=40, description="Partial symbol or company name"),
    limit: int = Query(10, ge=1, le=25),
) -> Dict[str, Any]:
    """Typeahead for the ticker box. Matches symbol or company name across every
    US-listed symbol, ranked so the company someone meant comes first."""
    return await _run(lambda: {"query": q, "results": universe_mod.search(q, limit)})


@app.get("/api/legal")
async def legal_notice() -> Dict[str, Any]:
    """The disclosures. Its own endpoint so a client consuming the JSON directly —
    which is where the strike recommendations and the simulated ledger live — can
    surface them without scraping the page."""
    return legal.notice()


@app.get("/api/session")
async def session_state() -> Dict[str, Any]:
    """Which trading session is running right now. No ticker needed."""
    return session_mod.state()


@app.get("/api/session/{ticker}")
async def session_prices(ticker: str) -> Dict[str, Any]:
    """The session, plus the close-versus-current pair for one ticker.

    Its own endpoint because every tab wants it and it has to stay cheap — a
    single quote, not the whole analysis. The strip has to be right on the
    Earnings and Long-Term tabs too, not just Swing.
    """
    def build() -> Dict[str, Any]:
        symbol = ticker.upper().strip()
        quote = PROVIDER.quote(symbol)
        # The profile rides along here rather than getting its own request: this
        # endpoint already fires on every ticker load from every tab, and a
        # business description is cached for a day so it costs nothing after the
        # first call.
        try:
            profile = YF_PROVIDER.profile(symbol)
        except Exception:
            profile = {}
        return {
            "ticker": symbol,
            "session": session_mod.state(),
            "prices": session_mod.price_view(quote),
            "profile": profile,
            "name": quote.get("name"),
        }

    return await _run(build)


@app.get("/api/news/{ticker}")
async def news_panel(ticker: str, limit: int = Query(12, ge=1, le=30)) -> Dict[str, Any]:
    return await _run(news_mod.analyse, YF_PROVIDER, ticker.upper(), limit)


# ----------------------------------------------------------------- daily brief
#
# One shared brief per Eastern-time day, not a per-visitor feed: every reader of
# the tab sees the same page, which is what makes it a record rather than a
# search. Building is cheap (~1s warm) because the feed layer caches per source
# and the overview reuses a single batched history call.

@app.get("/api/brief")
async def daily_brief(
    day: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    force: bool = Query(False),
) -> Dict[str, Any]:
    """Today's brief, or an archived day. `force` rebuilds today from source."""
    return await _run(brief_mod.state, YF_PROVIDER, day, force)


@app.get("/api/brief/search")
async def brief_search(
    q: str = Query("", max_length=120),
    limit: int = Query(40, ge=1, le=100),
) -> Dict[str, Any]:
    """Search the headlines the brief is built from.

    Scoped to what the feed layer already holds — every source in the table,
    roughly the last few days — rather than the open web. That keeps it free, keeps
    it instant, and keeps every result attributable to a source the page already
    lists. The response reports how many stories were searched so the UI can say
    so instead of implying a web search.
    """
    return await _run(feeds_mod.search, q, limit)


# -------------------------------------------------------------- optic tracker
#
# The tracker is a single shared ledger, not a per-visitor portfolio, so every
# request sees exactly the same record. Scans are serialised behind a lock: a
# scan is a long chain of provider calls, and two overlapping scans could both
# see a ticker as un-held and open it twice.

_SCAN_LOCK = asyncio.Lock()


def _tracker_snapshot(ticker: str) -> Dict[str, Any]:
    """A scan needs the verdict, levels and entry plan — nothing else. Macro is
    skipped because it's identical for every ticker and costs a fetch each time,
    and earnings momentum because it isn't scored and would add three provider
    calls per name to a thirty-name shortlist."""
    return _swing_snapshot(ticker, None, 4, False, include_earnings=False)


@app.get("/api/tracker")
async def tracker_state(
    month: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$",
                                 description="Month to detail, e.g. 2026-08"),
    book: Optional[str] = Query(None, description="conservative | balanced | aggressive"),
) -> Dict[str, Any]:
    """The ledger for one book. `month` selects which month's trades to detail;
    the monthly breakdown and all three books' headline figures are always
    included, so the selector and the comparison need no second request."""
    chosen = book if book in paper.BOOK_IDS else paper.DEFAULT_BOOK
    return await _run(paper.state, 60, month, chosen)


@app.post("/api/tracker/mark")
async def tracker_mark(request: Request) -> Dict[str, Any]:
    """Refresh marks on open positions without looking for new entries."""
    _write_guard(request)
    async with _SCAN_LOCK:
        return await _run(paper.mark_open_positions, PROVIDER, RISK_FREE)


async def _do_scan(tickers: Optional[List[str]], trigger: str) -> Dict[str, Any]:
    async with _SCAN_LOCK:
        result = await _run(
            paper.run_scan, _tracker_snapshot, PROVIDER, tickers, trigger, RISK_FREE
        )
    _raise_scan_alerts(result)
    return result


def _raise_scan_alerts(result: Dict[str, Any]) -> None:
    """Record alerts for whatever the scan did.

    Server-side rather than in the browser, so the inbox fills whether or not
    anyone had the page open — which is the only version of this worth having.

    Wrapped because an alert is a nice-to-have and a scan is not: several minutes
    of provider calls must never be lost because a notification failed to write.
    """
    try:
        made = alerts_mod.from_scan(result or {})
        if made:
            logging.getLogger("uvicorn.error").info("alerts: recorded %s", made)
    except Exception as exc:  # noqa: BLE001 - never break a scan over an alert
        logging.getLogger("uvicorn.error").warning("alerts failed: %s", exc)


@app.post("/api/tracker/scan")
async def tracker_scan(request: Request,
                       payload: Optional[Dict[str, Any]] = Body(None)) -> Dict[str, Any]:
    """Start a scan and return immediately.

    A NASDAQ-wide scan screens ~3,000 symbols and then puts a shortlist through
    the full analysis — minutes, not seconds. Holding the HTTP request open for
    that long means a proxy timeout decides whether the scan is recorded, so the
    work runs as a task and the tab polls /api/tracker for progress instead.
    """
    _write_guard(request)
    tickers = None
    if payload:
        raw = payload.get("watchlist") or payload.get("tickers")
        if raw:
            tickers = [str(t).upper().strip() for t in raw][:40]
    if _SCAN_LOCK.locked() or paper.progress().get("running"):
        raise HTTPException(status_code=409, detail="A scan is already running — watch its progress above.")

    # Publish "running" before returning, not from inside the task: otherwise the
    # response says the scan isn't running and a UI that trusts that reply shows
    # nothing until its first poll lands.
    paper.mark_scan_queued("manual")
    task = asyncio.create_task(_do_scan(tickers, "manual"))
    # Keep a reference: a bare create_task can be garbage-collected mid-flight,
    # which cancels the scan silently.
    app.state.manual_scan = task

    def _log_failure(done: asyncio.Task) -> None:
        if done.cancelled():
            return
        exc = done.exception()
        if exc:
            logging.getLogger("uvicorn.error").warning("manual tracker scan failed: %s", exc)

    task.add_done_callback(_log_failure)
    return {"started": True, "progress": paper.progress()}


# How often the background loop runs. Marking is cheap and wants to be frequent
# so P&L on the tab isn't stale; a full scan screens the whole exchange and then
# runs the analytics stack over a shortlist, so it runs far less often.
TRACKER_MARK_MINUTES = float(os.environ.get("TRACKER_MARK_MINUTES", "20"))
TRACKER_SCAN_MINUTES = float(os.environ.get("TRACKER_SCAN_MINUTES", "240"))
TRACKER_AUTO = os.environ.get("TRACKER_AUTO", "true").strip().lower() != "false"
# The brief piggybacks on the tracker loop rather than running a second timer.
BRIEF_AUTO = os.environ.get("BRIEF_AUTO", "true").strip().lower() != "false"
# The pre-open anchor, in Eastern hours. 09:00 is half an hour before the open:
# late enough to have the overnight wires and any 08:30 release, early enough to
# be read before the bell.
BRIEF_ANCHOR_HOUR = int(os.environ.get("BRIEF_ANCHOR_HOUR", "9"))


def brief_anchor_due(now_et: datetime, last_anchor_day: Optional[str]) -> Optional[str]:
    """Should the brief be force-rebuilt now, and for which day?

    Returns the day stamp to record, or None. Extracted from the loop so the rule
    can be tested without waiting for 09:00 to come round.

    The rule is "once per Eastern day, at or after the anchor hour". A server that
    starts at 14:00 still gets one forced rebuild — a cached brief from before it
    booted is not what a reader wants — so the condition deliberately does not
    require the anchor window itself. What it must not do is call that a pre-open
    build, which is why the caller logs the actual clock time.
    """
    stamp = now_et.strftime("%Y-%m-%d")
    if last_anchor_day == stamp:
        return None
    return stamp if now_et.hour >= BRIEF_ANCHOR_HOUR else None


async def _tracker_loop() -> None:
    """Keep the ledger current on its own so the record accumulates whether or
    not anyone is looking at the page."""
    log = logging.getLogger("uvicorn.error")
    await asyncio.sleep(30)  # let startup finish before touching the network

    # Seed from the ledger, not from zero. A full scan is a few minutes of
    # provider calls, and starting the clock at zero meant every restart fired
    # one — which on a platform that restarts on each deploy is a scan nobody
    # asked for, on stale conditions, at the worst possible moment.
    loop_now = asyncio.get_running_loop().time()
    age = paper.seconds_since_last_scan()
    last_scan = loop_now - age if age is not None else 0.0

    # Whether the previous pass saw a live tape, so the close can be detected and
    # marked once instead of the loop re-reading the same stale quotes all night.
    was_open = paper.market_open_et()

    while True:
        try:
            now = asyncio.get_running_loop().time()
            is_open = paper.market_open_et()
            just_closed = was_open and not is_open
            was_open = is_open

            # Snapshot the ledger, above the market-hours gate for the same
            # reason as the brief: the `continue` for a closed market would
            # otherwise skip it every evening and all weekend, and a backup that
            # only runs while the market is open is not a backup.
            if snapshots.due(getattr(app.state, "last_snapshot", None), now):
                try:
                    await _run(snapshots.take)
                    app.state.last_snapshot = now
                except Exception as exc:
                    log.warning("ledger snapshot failed: %s", exc)

            # Keep the daily brief's archive complete — before the market-hours
            # gate below, deliberately.
            #
            # The tab rebuilds on load, which is enough to *serve* a brief but not
            # to *record* one: a day nobody opened the tab would have no row at
            # all, leaving gaps in what is meant to be a daily record. Placed
            # after the gate it was worse than useless — the `continue` for a
            # closed market skipped it every evening and all weekend, which is
            # precisely when news still arrives and no reader is around to
            # trigger a build. Nearly free: state() returns the cached payload
            # untouched until it ages past BRIEF_REBUILD_MINUTES.
            if BRIEF_AUTO:
                # A forced rebuild once per day at the pre-open anchor, and the
                # ordinary cache-aged refresh otherwise.
                #
                # The opportunistic refresh alone was not a guarantee. It rebuilds
                # when the cached payload ages past BRIEF_REBUILD_MINUTES, which
                # depends on when the loop happens to tick — so the read a user
                # opens at 09:05 could have been assembled at 08:20, before the
                # last hour of overnight wires and any pre-market release. The
                # anchor makes one build a fixed part of the day: 09:00 Eastern,
                # half an hour before the open, forced so it re-reads the feeds
                # rather than serving a cached brief.
                try:
                    now_et = datetime.now(timezone.utc).astimezone(session_mod.ET)
                    stamp = brief_anchor_due(
                        now_et, getattr(app.state, "brief_anchor_day", None))
                    await _run(brief_mod.state, YF_PROVIDER, None, bool(stamp))
                    if stamp:
                        app.state.brief_anchor_day = stamp
                        # The actual clock time, not the word "pre-open": on a
                        # server that booted at 14:00 this is the day's forced
                        # rebuild and nothing about it was before the open.
                        log.info("brief: forced daily rebuild for %s at %s ET",
                                 stamp, now_et.strftime("%H:%M"))
                except Exception as exc:  # noqa: BLE001 - never break the loop
                    log.warning("brief refresh failed: %s", exc)

            # Nothing to do overnight or at the weekend. Prices don't move, so
            # marking would re-read the same close and a scan would take entries
            # at a price nobody could have traded. The one exception is the first
            # pass after the close, which captures the settled marks.
            if not is_open and not just_closed:
                await asyncio.sleep(TRACKER_MARK_MINUTES * 60)
                continue

            due_for_scan = is_open and (now - last_scan) >= TRACKER_SCAN_MINUTES * 60
            async with _SCAN_LOCK:
                if due_for_scan:
                    result = await _run(
                        paper.run_scan, _tracker_snapshot, PROVIDER, None, "scheduled", RISK_FREE
                    )
                    last_scan = now
                    _raise_scan_alerts(result)
                    log.info(
                        "tracker scan: considered %s, opened %s, closed %s",
                        result["considered"], result["opened"], result["closed"],
                    )
                else:
                    await _run(paper.mark_open_positions, PROVIDER, RISK_FREE)
                    if just_closed:
                        log.info("tracker: marked final closing prices")
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # a failed pass must not kill the loop
            log.warning("tracker loop pass failed: %s", exc)
        await asyncio.sleep(TRACKER_MARK_MINUTES * 60)


@app.on_event("startup")
async def _start_tracker() -> None:
    paper.init_db()
    if TRACKER_AUTO:
        # Held on the app so the reference isn't garbage-collected mid-flight.
        app.state.tracker_task = asyncio.create_task(_tracker_loop())


@app.on_event("shutdown")
async def _stop_tracker() -> None:
    task = getattr(app.state, "tracker_task", None)
    if task:
        task.cancel()


# --------------------------------------------------- naming a ticker in chat

# App jargon that is also a plausible ticker symbol. Without this, "what is the
# GEX saying" fetches whatever ticker happens to be called GEX and answers a
# question nobody asked.
_CHAT_NOT_TICKERS = {
    "GEX", "IV", "HV", "RSI", "MACD", "ATR", "EMA", "SMA", "VWAP", "DTE", "OI",
    "CPI", "PPI", "FOMC", "COT", "JOLTS", "GDP", "PCE", "ETF", "API", "USD",
    "PM", "AM", "ET", "EOD", "ITM", "OTM", "ATM", "PNL", "YTD", "EPS", "PE",
    "AI", "US", "UK", "EU", "CEO", "CFO", "SEC", "FED", "AND", "OR", "VS",
    "THE", "A", "I", "IT", "ON", "ALL", "FOR", "PUT", "CALL", "BUY", "SELL",
}

# One lookup per message. Each analysis is a full chain fetch — several seconds
# and real quota — so "compare these six names" deliberately does not trigger six.
_CHAT_MAX_LOOKUPS = 1


def _symbols_in(text: str) -> List[str]:
    """Uppercase tokens in a message that are really tradeable symbols."""
    out: List[str] = []
    for token in re.findall(r"\b[A-Z][A-Z.\-]{0,5}\b", text or ""):
        token = token.strip(".-")
        if len(token) < 2 or token in _CHAT_NOT_TICKERS or token in out:
            continue
        # Validated against the real symbol directory rather than a regex guess:
        # a match must be the exact symbol, not merely a search hit.
        try:
            hits = universe_mod.search(token, limit=3)
        except Exception:
            continue
        if any((h.get("symbol") or "").upper() == token for h in hits):
            out.append(token)
    return out


# Phrases that mean "give me candidates" rather than "tell me about X".
_IDEA_HINTS = (
    "recommend", "suggest", "ideas", "candidates", "what should i", "what would you",
    "any setups", "possible swings", "swings to take", "watchlist", "screen for",
    "opportunities", "best plays", "what looks good", "anything worth",
)


def _wants_candidates(text: str) -> bool:
    low = (text or "").lower()
    return any(h in low for h in _IDEA_HINTS)


# Intraday shapes for the 1D and 5D pills. Two specs rather than one, because a
# single interval cannot serve both: 1-minute bars over five days is ~1,950
# points for a chart a few hundred pixels wide, and 15-minute bars over one day
# is 26 points, which is not a chart. Each range gets the interval that makes it
# readable.
INTRADAY_SPECS = {
    "1d": {"period": "1d", "interval": "5m"},
    "5d": {"period": "5d", "interval": "15m"},
}


@app.get("/api/intraday/{ticker}")
async def intraday(ticker: str, range: str = Query("1d")) -> Dict[str, Any]:
    """Intraday bars for the short-range chart pills.

    Separate from /api/ticker deliberately. That payload is daily bars and the
    whole analysis built on them; intraday is only wanted when the reader picks
    1D or 5D, and fetching it on every ticker load would be a request per view
    that most readers never look at.

    Regular session only. Pre- and post-market prints come from thin books, and
    splicing them into the same line as regular-hours trade draws gaps and
    spikes that look like price action and are not.
    """
    spec = INTRADAY_SPECS.get((range or "").lower())
    if not spec:
        return {"available": False,
                "reason": "Unknown range {!r} — expected 1d or 5d.".format(range)}

    def build() -> Dict[str, Any]:
        symbol = ticker.upper().strip()
        frame = YF_PROVIDER.intraday_history(
            symbol, period=spec["period"], interval=spec["interval"])
        if frame is None or frame.empty:
            return {"available": False, "ticker": symbol, "range": range,
                    "reason": ("No intraday bars came back. Free intraday history is "
                               "thin outside regular hours and absent for many symbols.")}

        closes, times, volumes = [], [], []
        for stamp, row in frame.iterrows():
            close = row.get("Close")
            if close is None or close != close:
                continue
            closes.append(round(float(close), 4))
            times.append(stamp.isoformat())
            vol = row.get("Volume")
            volumes.append(None if vol is None or vol != vol else float(vol))

        if not closes:
            return {"available": False, "ticker": symbol, "range": range,
                    "reason": "Intraday bars came back with no usable closes."}

        # The reference for a percentage change is the first bar of the window,
        # not the previous daily close — the chart shows this window, so the
        # number under it has to describe the same thing.
        first, last = closes[0], closes[-1]
        return {
            "available": True,
            "ticker": symbol,
            "range": range,
            "interval": spec["interval"],
            "times": times,
            "closes": closes,
            "volumes": volumes,
            "bars": len(closes),
            "first": first,
            "last": last,
            "change_pct": round((last / first - 1.0) * 100.0, 3) if first else None,
            "session_note": (
                "Regular session bars only, at {} resolution. Pre- and post-market "
                "prints are excluded: they trade on thin books, and splicing them "
                "into the same line draws gaps that look like price action and are "
                "not.".format(spec["interval"])
            ),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    return await _run(build)


@app.get("/api/sectors/board")
async def sector_board_panel() -> Dict[str, Any]:
    """Each SPDR sector against its prior-session high and low, plus rotation."""
    def build() -> Dict[str, Any]:
        out = sector_board_mod.build(YF_PROVIDER)
        out["generated_at"] = datetime.now(timezone.utc).isoformat()
        return out
    return await _run(build)


@app.get("/api/indices/board")
async def index_board_panel() -> Dict[str, Any]:
    """The major index ETFs against their prior-session high and low."""
    def build() -> Dict[str, Any]:
        out = sector_board_mod.build(YF_PROVIDER, sector_board_mod.INDEX_ETFS)
        out["generated_at"] = datetime.now(timezone.utc).isoformat()
        return out
    return await _run(build)


@app.get("/api/sectors/{symbol}/read")
async def sector_read(symbol: str) -> Dict[str, Any]:
    """A written read on one sector or index ETF.

    Separate endpoint and separate request from the board itself. The board is
    eleven rows of arithmetic and renders instantly; this is a paid model call
    for one row the reader actually clicked. Fetching fifteen of these to fill a
    table nobody has opened would be a bill for nothing.
    """
    def build() -> Dict[str, Any]:
        sym = symbol.upper().strip()
        facts = sector_board_mod.detail(YF_PROVIDER, sym)
        if not facts.get("available"):
            return {"available": False, "reason": facts.get("reason", "No data for this symbol.")}
        read = ai.write_sector_read(sym, facts)
        if not read:
            return {"available": False, "symbol": sym,
                    "summary": (facts.get("row") or {}).get("summary"),
                    "reason": ("The assistant is not configured, so there is no written read — "
                               "the levels and rotation on the board are unaffected."
                               if ai.available().get("enabled") is not True else
                               "The read could not be written on this attempt.")}
        read["row"] = facts.get("row")
        read["generated_at"] = datetime.now(timezone.utc).isoformat()
        return read
    return await _run(build)


@app.get("/api/sentiment")
async def sentiment_panel() -> Dict[str, Any]:
    """The fear-and-greed reading, with its own recomputed history."""
    def build() -> Dict[str, Any]:
        out = sentiment_mod.build(YF_PROVIDER)
        out["generated_at"] = datetime.now(timezone.utc).isoformat()
        return out
    return await _run(build)


@app.get("/api/weekly")
async def weekly_update(force: bool = False) -> Dict[str, Any]:
    """The weekly market update, generated once per ISO week.

    Same economics as the morning note: one model call a week shared by every
    reader, not one per page view. That is the only reason a piece this long is
    affordable to publish at all.
    """
    def build() -> Dict[str, Any]:
        key = weekly_mod.week_key()
        if force:
            ai._WEEKLY_CACHE.pop(key, None)
        facts = weekly_mod.gather(YF_PROVIDER)
        update = ai.write_weekly_update(key, facts)
        if not update:
            return {"available": False, "week_key": key,
                    "reason": ("The assistant is not configured, so there is no weekly "
                               "update."
                               if ai.available().get("enabled") is not True else
                               "The weekly update could not be written on this attempt.")}
        update["facts"] = {
            "earnings": facts.get("earnings"),
            "spy": facts.get("spy"),
            "sectors": facts.get("sectors"),
        }
        update["generated_at"] = datetime.now(timezone.utc).isoformat()
        return update
    return await _run(build)


@app.get("/api/catalysts")
async def catalyst_library(
    q: str = Query("", description="Free-text search"),
    status: str = Query("relevant"),
    category: str = Query(""),
    sector: str = Query(""),
    theme: str = Query(""),
    limit: int = Query(60, ge=1, le=200),
) -> Dict[str, Any]:
    """Search the stored catalyst library. Reads only — never generates."""
    def build() -> Dict[str, Any]:
        return catalysts_mod.search(query=q, status=status, category=category,
                                    sector=sector, theme=theme, limit=limit)
    return await _run(build)


@app.post("/api/catalysts/refresh")
async def catalyst_refresh(request: Request,
                           hours: int = Query(168, ge=24, le=720)) -> Dict[str, Any]:
    """Scan recent stories for new catalysts.

    A POST and a separate endpoint from the search above, deliberately: this one
    spends money and writes to the store, and neither of those should happen
    because somebody opened a tab.
    """
    _write_guard(request)

    def build() -> Dict[str, Any]:
        out = catalysts_mod.refresh(hours=hours)
        out["generated_at"] = datetime.now(timezone.utc).isoformat()
        return out
    return await _run(build)


@app.get("/api/catalyst-mode")
async def catalyst_mode() -> Dict[str, Any]:
    """The release currently moving the tape, its cross-asset reaction, and a read."""
    def build() -> Dict[str, Any]:
        facts = catalyst_live_mod.build(YF_PROVIDER)
        if not facts.get("available"):
            return facts
        key = (facts.get("release") or {}).get("url") or (facts.get("release") or {}).get("title") or "-"
        read = ai.write_catalyst_read(key, facts)
        facts["read"] = read or {"available": False}
        facts["generated_at"] = datetime.now(timezone.utc).isoformat()
        return facts
    return await _run(build)


_EVAL_CACHE: Dict[str, Any] = {}
EVAL_SAMPLE = int(os.environ.get("EVAL_SAMPLE", "220"))


@app.get("/api/evaluate")
async def evaluate_signal(force: bool = False) -> Dict[str, Any]:
    """Measure whether the screen's score predicts anything, against controls.

    Cached in memory: the run replays the scoring function across the sample at
    every evaluation date, and the answer only changes when the price history
    does. It is also the one endpoint here whose output may be unflattering, so
    it must not be quietly skipped when it is.
    """
    def build() -> Dict[str, Any]:
        import random as _random
        if _EVAL_CACHE and not force:
            return _EVAL_CACHE["result"]
        ranking = _cached_ranking()
        rows = (ranking or {}).get("ranked") or []
        if not rows:
            return {"available": False,
                    "reason": "The universe ranking has not been built yet."}
        symbols = [r.get("symbol") for r in rows if r.get("symbol")]
        # A fixed seed so the sample — and therefore the measurement — is
        # reproducible. A result that changes every refresh cannot be argued with.
        _random.Random(11).shuffle(symbols)
        out = evaluate_mod.with_controls(YF_PROVIDER, symbols[:EVAL_SAMPLE])
        out["sample_size"] = min(EVAL_SAMPLE, len(symbols))
        out["universe_total"] = len(symbols)
        out["generated_at"] = datetime.now(timezone.utc).isoformat()
        _EVAL_CACHE["result"] = out
        return out
    return await _run(build)


@app.get("/api/implied-correlation")
async def implied_correlation() -> Dict[str, Any]:
    """Index implied vol against its own components — the dispersion read."""
    def build() -> Dict[str, Any]:
        out = correlation_mod.build(PROVIDER)
        out["expiries"] = expiries_mod.context()
        out["generated_at"] = datetime.now(timezone.utc).isoformat()
        return out
    return await _run(build)


@app.get("/api/portfolio-risk")
async def portfolio_risk_panel(
    book: Optional[str] = Query(None, description="Which book to assess"),
) -> Dict[str, Any]:
    """Concentration and correlation across the open paper book."""
    def build() -> Dict[str, Any]:
        try:
            state = paper.state(60, None, book if book in paper.BOOK_IDS else paper.DEFAULT_BOOK)
        except Exception as exc:
            return {"available": False, "reason": "Tracker unavailable: {}".format(exc)}
        positions = (state or {}).get("open") or []
        out = portfolio_risk_mod.build(YF_PROVIDER, positions)
        out["generated_at"] = datetime.now(timezone.utc).isoformat()
        return out
    return await _run(build)


def _cached_ranking() -> Optional[Dict[str, Any]]:
    """The screener's ranking as it sits on disk, or None.

    Reads through screen_mod.CACHE_PATH rather than rebuilding the path, so a
    change to TRACKER_DATA_DIR cannot silently point the scanners at a file the
    screener is not writing.
    """
    import json as _json                       # local: main.py has no json import
    try:
        with open(screen_mod.CACHE_PATH) as fh:
            blob = _json.load(fh)
    except (OSError, ValueError):
        return None
    return (blob or {}).get("ranking") or None


@app.get("/api/priority")
async def priority_board() -> Dict[str, Any]:
    """Today's four-column triage board."""
    def build() -> Dict[str, Any]:
        return priority_mod.build(YF_PROVIDER, scanners_mod, _cached_ranking())
    return await _run(build)


_EW_CACHE: Dict[int, Dict[str, Any]] = {}
EW_TTL = 3600.0


@app.get("/api/earnings-week")
async def earnings_week_calendar(
    offset: int = Query(0, ge=-8, le=8, description="Weeks from this one"),
) -> Dict[str, Any]:
    """Who reports this week, grouped by day. Needs no ticker loaded.

    Cached for an hour per week. The scan is ~150 provider calls and takes tens of
    seconds cold, which is far too slow for a tab a reader opens casually — and
    earnings dates move on the scale of days, not minutes.
    """
    def build() -> Dict[str, Any]:
        hit = _EW_CACHE.get(offset)
        if hit and (time.time() - hit["at"]) < EW_TTL:
            return hit["data"]
        out = earnings_week_mod.build(YF_PROVIDER, offset=offset)
        out["generated_at"] = datetime.now(timezone.utc).isoformat()
        _EW_CACHE[offset] = {"at": time.time(), "data": out}
        return out
    return await _run(build)


@app.get("/api/compare")
async def compare_tickers(
    tickers: str = Query(..., description="Comma-separated, 2 to 4 symbols"),
) -> Dict[str, Any]:
    """Side-by-side comparison across swing, position and long-term horizons."""
    def build() -> Dict[str, Any]:
        wanted = [t for t in (tickers or "").replace(" ", "").split(",") if t]

        def snapshot(sym: str) -> Dict[str, Any]:
            # The same snapshot the Swing tab uses, minus the option chain: the
            # comparison needs technicals and structure, and pulling four chains
            # would triple the wait for numbers it never reads.
            return _swing_snapshot(sym, None, 1, False, include_earnings=False)

        def longterm_for(sym: str) -> Dict[str, Any]:
            # analyse_holding(provider, ticker) — and the module is imported as
            # `longterm`, not `longterm_mod`. Both wrong first time, and a bare
            # except would have hidden it as "no long-term data" forever.
            try:
                return {"holding": longterm.analyse_holding(PROVIDER, sym)}
            except Exception as exc:
                logging.getLogger("uvicorn.error").warning(
                    "compare: long-term unavailable for %s: %s", sym, exc)
                return {}

        out = compare_mod.build(snapshot, longterm_for, wanted)
        out["generated_at"] = datetime.now(timezone.utc).isoformat()
        return out
    return await _run(build)


@app.get("/api/pe-history/{ticker}")
async def pe_history_panel(ticker: str, years: int = Query(10, ge=2, le=20)) -> Dict[str, Any]:
    """Weekly trailing P/E and quarterly revenue growth, from SEC filings."""
    def build() -> Dict[str, Any]:
        out = pe_history_mod.build(YF_PROVIDER, ticker, years=years)
        out["generated_at"] = datetime.now(timezone.utc).isoformat()
        return out
    return await _run(build)


@app.get("/api/trendlines/{ticker}")
async def trendlines_panel(ticker: str,
                           period: str = Query("1y")) -> Dict[str, Any]:
    """Trend lines fitted to pivots, and whether price has broken one."""
    sym = ticker.strip().upper()

    def build() -> Dict[str, Any]:
        df = YF_PROVIDER.history(sym, period=period, interval="1d")
        out = trendlines_mod.build(df)
        out["ticker"] = sym
        out["period"] = period
        out["dates"] = ([str(i.date()) for i in df.index]
                        if df is not None and len(df) else [])
        return out
    return await _run(build)


@app.get("/api/forex")
async def forex_panel(q: str = Query("", max_length=40)) -> Dict[str, Any]:
    """Currency pairs with their macro driver and what each one reads across to."""
    def build() -> Dict[str, Any]:
        out = forex_mod.build(YF_PROVIDER, q)
        out["generated_at"] = datetime.now(timezone.utc).isoformat()
        return out
    return await _run(build)


@app.get("/api/stockmap")
async def stockmap(template: str = Query("sector-month",
                                         max_length=40)) -> Dict[str, Any]:
    """A screen laid out as a treemap or a bubble chart."""
    def build() -> Dict[str, Any]:
        out = stockmaps_mod.build(YF_PROVIDER, template)
        out["generated_at"] = datetime.now(timezone.utc).isoformat()
        return out
    return await _run(build)


@app.get("/api/extras/{ticker}")
async def extras(ticker: str,
                 benchmark: str = Query("SPY", max_length=8)) -> Dict[str, Any]:
    """Dividends, splits, off-exchange short volume and relative performance.

    One endpoint for four small datasets rather than four: they are all
    per-symbol, all cheap, and a client that wants one usually wants the rest.
    """
    sym = ticker.strip().upper()

    def build() -> Dict[str, Any]:
        return {
            "ticker": sym,
            "actions": extras_mod.corporate_actions(YF_PROVIDER, sym),
            "short_volume": extras_mod.short_volume(sym),
            "relative": extras_mod.relative_performance(YF_PROVIDER, sym, benchmark),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    return await _run(build)


@app.get("/api/crypto-sentiment")
async def crypto_sentiment() -> Dict[str, Any]:
    """The crypto fear and greed index — a risk-appetite reading, not a forecast."""
    return await _run(extras_mod.crypto_sentiment)


@app.get("/api/snapshots")
async def list_snapshots() -> Dict[str, Any]:
    """What ledger backups exist. Listing only — no download, because the file
    is the whole record and this endpoint is open like every other read."""
    rows = snapshots.existing()
    return {
        "snapshots": rows,
        "keep": snapshots.KEEP,
        "every_hours": snapshots.EVERY_HOURS,
        "note": "Copies live beside the ledger on the same volume, so they cover "
                "corruption and accidental wipes but not loss of the volume.",
    }


@app.get("/api/alerts")
async def list_alerts(limit: int = Query(50, ge=1, le=200),
                      unseen: bool = False) -> Dict[str, Any]:
    """The alert inbox, plus what delivery would still need."""
    return {
        "alerts": alerts_mod.recent(limit=limit, unseen_only=unseen),
        "unseen": alerts_mod.unseen_count(),
        "kinds": alerts_mod.KINDS,
        "delivery": alerts_mod.delivery_status(),
    }


@app.post("/api/alerts/seen")
async def alerts_seen(payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    ids = payload.get("ids")
    return {"marked": alerts_mod.mark_seen(ids if isinstance(ids, list) else None)}


@app.post("/api/alerts/clear")
async def alerts_clear(request: Request) -> Dict[str, Any]:
    _write_guard(request)
    return {"removed": alerts_mod.clear()}


@app.get("/api/econ")
async def econ_catalogue() -> Dict[str, Any]:
    """The economic series available to plot, grouped. No fetch."""
    return econ_mod.catalogue()


@app.get("/api/econ/{code}")
async def econ_series(code: str, years: int = Query(12, ge=1, le=60)) -> Dict[str, Any]:
    """One FRED series, transformed into the form it is actually read in."""
    return await _run(econ_mod.series, code.strip().upper(), years)


@app.get("/api/rotation")
async def rotation_panel(tail: int = Query(8, ge=2, le=20)) -> Dict[str, Any]:
    """Sector relative rotation: strength against momentum, both centred on 100."""
    def build() -> Dict[str, Any]:
        out = rotation_mod.build(YF_PROVIDER, tail=tail)
        out["generated_at"] = datetime.now(timezone.utc).isoformat()
        return out
    return await _run(build)


@app.get("/api/seasonality/{ticker}")
async def seasonality_panel(ticker: str) -> Dict[str, Any]:
    """Calendar effects: month of year, day of week, turn of month.

    Deliberately not part of the swing payload. It reads fifteen years of daily
    bars for the ticker and the benchmark, and the answer changes about as often
    as the calendar does — there is no reason to pay for it on every ticker load.
    """
    def build() -> Dict[str, Any]:
        out = seasonality_mod.build(YF_PROVIDER, ticker.upper().strip())
        out["generated_at"] = datetime.now(timezone.utc).isoformat()
        return out
    return await _run(build)


def _num(value: Any) -> Optional[float]:
    """NaN and inf are not JSON. A silent null is better than a 500 on one bar."""
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if out != out or out in (float("inf"), float("-inf")) else round(out, 6)


@app.get("/api/global")
async def global_panel() -> Dict[str, Any]:
    """The overnight session worldwide, ordered by the clock.

    Cached for the same reason the sector board is: eighteen symbols of six-month
    history is a slow pull, and every one of these markets is shut by the time a US
    reader loads the page, so the numbers do not change intraday.
    """
    def build() -> Dict[str, Any]:
        now = time.time()
        hit = getattr(app.state, "global_cache", None)
        if hit and now - hit["at"] < 900:
            out = dict(hit["data"])
            out["cache_age_seconds"] = int(now - hit["at"])
            return out
        out = global_mod.build(YF_PROVIDER)
        out["generated_at"] = datetime.now(timezone.utc).isoformat()
        app.state.global_cache = {"at": now, "data": out}
        out["cache_age_seconds"] = 0
        return out
    return await _run(build)


@app.get("/api/instrument")
async def instrument_chart(
    symbol: str = Query(..., description="Provider symbol, e.g. ^VIX or DX-Y.NYB"),
    range_: str = Query("1y", alias="range"),
    ids: str = Query("", description="Optional indicator ids"),
) -> Dict[str, Any]:
    """Full history for one cross-asset instrument.

    A query parameter rather than a path segment on purpose: these symbols contain
    characters that do not survive a path cleanly — `^VIX`, `DX-Y.NYB`, `USDJPY=X`
    and `HG=F` all break or get mangled by a router that splits on slashes and
    normalises dots.

    Always YF_PROVIDER. The brokerage feed covers tradeable equities and options;
    an index level, a yield proxy and a currency cross are not that, so routing
    this through PROVIDER would return nothing for exactly the rows this serves.
    """
    def build() -> Dict[str, Any]:
        sym = (symbol or "").strip()
        known = {i["symbol"]: i for i in macro_mod.INSTRUMENTS}
        frame = YF_PROVIDER.history(sym, period=range_, interval="1d")
        if frame is None or frame.empty:
            raise HTTPException(status_code=404,
                                detail="No history for '{}'.".format(sym))
        meta = known.get(sym, {})
        snap = macro_mod.snapshot(frame, meta.get("label") or sym)
        close = frame["Close"].astype(float)
        wanted = [i for i in (ids or "").replace(" ", "").split(",") if i]
        extras = {}
        if wanted:
            extras = indicators_mod.compute(frame, wanted)
        return {
            "available": True,
            "symbol": sym,
            "label": meta.get("label") or sym,
            "note": meta.get("note"),
            "group": meta.get("group"),
            "range": range_,
            "dates": [str(i.date()) for i in frame.index],
            "open": [_num(v) for v in frame["Open"]] if "Open" in frame else None,
            "high": [_num(v) for v in frame["High"]] if "High" in frame else None,
            "low": [_num(v) for v in frame["Low"]] if "Low" in frame else None,
            "close": [_num(v) for v in close],
            "volume": ([_num(v) for v in frame["Volume"]]
                       if "Volume" in frame and frame["Volume"].notna().any() else None),
            "snapshot": snap,
            "indicators": extras,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    return await _run(build)


@app.get("/api/indicators/{ticker}")
async def indicator_panel(
    ticker: str,
    ids: str = Query("", description="Comma-separated indicator ids"),
    range_: str = Query("2y", alias="range"),
    anchor: str = Query("", description="Anchor date for VWAP, YYYY-MM-DD"),
) -> Dict[str, Any]:
    """Optional indicators, computed only for the ids asked for.

    A catalogue endpoint rather than more fields on the ticker payload: nine
    indicators on every request would be work nobody asked for on most page loads,
    and the reader picks these deliberately.
    """
    def build() -> Dict[str, Any]:
        sym = ticker.upper().strip()
        wanted = [i for i in (ids or "").replace(" ", "").split(",") if i]
        hist = PROVIDER.history(sym, period=range_, interval="1d")
        if hist is None or hist.empty:
            raise HTTPException(status_code=404,
                                detail="No price data found for '{}'.".format(sym))
        bench = None
        if "rs" in wanted:
            frame = YF_PROVIDER.history("SPY", period=range_, interval="1d")
            if frame is not None and not frame.empty:
                bench = frame["Close"].astype(float)
        out = indicators_mod.compute(hist, wanted, bench=bench,
                                     anchor=anchor or None)
        out["ticker"] = sym
        out["generated_at"] = datetime.now(timezone.utc).isoformat()
        return out
    return await _run(build)


@app.get("/api/patterns/base-rates")
async def pattern_base_rates(force: bool = Query(False)) -> Dict[str, Any]:
    """Measured base rates for each pattern.

    Cached on disk for a month. The full build walks 43 names over ten years of
    daily bars detecting candles bar by bar, which takes about ninety seconds —
    far too slow to sit in a page load, and the numbers move so slowly that a
    stale month is not a meaningful staleness.
    """
    def build() -> Dict[str, Any]:
        return pattern_stats_mod.load(YF_PROVIDER, force=force)
    return await _run(build)


@app.get("/api/patterns/{ticker}")
async def pattern_read(ticker: str) -> Dict[str, Any]:
    """Chart patterns, candles and supply/demand zones for one name."""
    def build() -> Dict[str, Any]:
        sym = ticker.upper().strip()
        hist = PROVIDER.history(sym, period="2y", interval="1d")
        if hist is None or hist.empty:
            raise HTTPException(status_code=404,
                                detail="No price data found for '{}'.".format(sym))
        quote = PROVIDER.quote(sym)
        spot = quote.get("price") or float(hist["Close"].iloc[-1])
        out = patterns_mod.analyse(hist, spot=spot)
        out["ticker"] = sym
        # Base rates ride along so the panel can show the measured outcome next
        # to each label without a second request. Never computed on this path —
        # if the cache is cold the panel says so rather than blocking the page.
        out["base_rates"] = pattern_stats_mod.load(provider=None)
        out["generated_at"] = datetime.now(timezone.utc).isoformat()
        return out
    return await _run(build)


@app.get("/api/scanners/groups")
async def scanner_groups() -> Dict[str, Any]:
    """The scan groups, so the tab can present a menu rather than a flat list."""
    def build() -> Dict[str, Any]:
        return {"groups": scanners_mod.groups(),
                "note": ("Grouped by the question each scan asks. Premarket movers, "
                         "short-squeeze watch and quality screens are deliberately "
                         "absent: they need premarket quotes, short interest and "
                         "fundamentals across the whole universe, none of which this "
                         "terminal has at 700-name scale.")}
    return await _run(build)


@app.get("/api/scanners")
async def scanner_catalogue() -> Dict[str, Any]:
    """The scans on offer, and whether there is a ranking to run them over."""
    def build() -> Dict[str, Any]:
        ranking = _cached_ranking()
        rows = (ranking or {}).get("ranked") or []
        return {
            "scans": scanners_mod.catalogue(),
            "ready": bool(rows),
            "considered": len(rows),
            "universe_size": (ranking or {}).get("universe_size"),
        }
    return await _run(build)


@app.get("/api/scanners/{scan_id}")
async def scanner_run(scan_id: str, limit: int = Query(scanners_mod.DEFAULT_LIMIT,
                                                       ge=1, le=100)) -> Dict[str, Any]:
    """Run one named scan over the cached ranking.

    Cheap by construction: the expensive part — downloading and scoring roughly
    three thousand symbols — already happened in the background, so this is a
    filter and a sort over rows that exist. That is the whole reason the scans
    are defined against the ranking's metrics rather than against anything
    needing a fresh per-symbol fetch.
    """
    def build() -> Dict[str, Any]:
        out = scanners_mod.run(_cached_ranking(), scan_id, limit=limit)
        out["generated_at"] = datetime.now(timezone.utc).isoformat()
        return out
    return await _run(build)


def _screen_candidates(limit: int = 8) -> Optional[Dict[str, Any]]:
    """The screener's current ranking, for questions that name no ticker.

    "Recommend me some swings" has nothing to work from: no symbol in the question
    and, on the home tab, nothing in the browser either. The terminal already
    knows the answer — the screener ranks the NASDAQ every scan and the result is
    cached on disk — so it is handed over rather than the reader being told to go
    look somewhere else.

    What travels is deliberately partial: price and the trend metrics the screen
    itself computed. There is no option chain, no gamma and no flow here, because
    those cost a full per-symbol fetch. The note says so, because the alternative
    is a model filling the gap with plausible invented flow.
    """
    import json as _json                       # local: main.py has no json import

    try:
        # screen.CACHE_PATH is the single definition of where this lives; building
        # the path again here would drift the moment TRACKER_DATA_DIR changes.
        with open(screen_mod.CACHE_PATH) as fh:
            blob = _json.load(fh)
    except (OSError, ValueError):
        return None
    rows = ((blob or {}).get("ranking") or {}).get("ranked") or []
    if not rows:
        return None

    keep = ("symbol", "price", "score", "sma20", "sma50", "sma200", "roc20", "roc60",
            "range_position", "volume_expansion", "atr_pct")
    out = []
    for row in rows[:limit]:
        item = {k: row.get(k) for k in keep if row.get(k) is not None}
        item["factors"] = [f.get("label") for f in (row.get("factors") or [])[:5]]
        out.append(item)

    # Enrich with the things a criteria question actually filters on.
    #
    # "Small tech company with a decent valuation reporting soon" cannot be
    # answered from a momentum ranking: the screen knows price and trend and
    # nothing about sector, size, multiple or earnings date. Without these the
    # model either ignores the criteria or invents the missing fields.
    #
    # Each source is separately cached — profile for a day, earnings for an hour —
    # so this is free on a warm cache and slow exactly once per symbol per day.
    # Failures are per-field and silent: a name missing a P/E should still appear
    # with its sector rather than vanish from the list.
    for item in out:
        symbol = item.get("symbol")
        if not symbol:
            continue
        try:
            prof = YF_PROVIDER.profile(symbol) or {}
            item["sector"] = prof.get("sector")
            item["industry"] = prof.get("industry")
        except Exception:
            pass
        try:
            q = YF_PROVIDER.quote(symbol) or {}
            cap = q.get("market_cap")
            if cap:
                item["market_cap"] = cap
                # Bucket it, because "small company" is the phrasing people use
                # and a raw number invites the model to invent its own cutoffs.
                billions = float(cap) / 1e9
                item["size"] = ("mega" if billions >= 200 else "large" if billions >= 10
                                else "mid" if billions >= 2 else "small")
            for field in ("forward_pe", "trailing_pe", "price_to_book"):
                if q.get(field) is not None:
                    item[field] = q.get(field)
        except Exception:
            pass
        try:
            # earnings_date(), not earnings() — the latter does not exist, and the
            # bare except below would have hidden the AttributeError forever while
            # next_earnings silently stayed absent on every name.
            nxt = YF_PROVIDER.earnings_date(symbol)
            if nxt:
                item["next_earnings"] = str(nxt)
        except Exception:
            pass
    return {
        "ranked": out,
        "universe": (blob or {}).get("key"),
        "note": (
            "The terminal's own screen, ranked by trend and momentum score, enriched "
            "with sector, market-cap bucket, valuation multiples and the next earnings "
            "date so criteria like \"small tech company reporting soon\" can actually be "
            "filtered rather than guessed. Any of those fields may be absent for a "
            "given name; absent means unknown, not zero. These are "
            "the technical metrics the screen computed — price versus its 20/50/200-day "
            "averages, rate of change, where price sits in its range, volume expansion "
            "and ATR. There is NO option chain, gamma, flow or news here: those need a "
            "per-symbol fetch. Do not state contract prices, greeks, IV, gamma levels or "
            "flow figures for these names — say the name needs loading for that."
        ),
    }

# Questions about the tape as a whole rather than about one name.
_MARKET_HINTS = (
    "market condition", "the market", "market today", "conditions today", "the tape",
    "why is there", "why so much", "chop", "choppy", "risk on", "risk off",
    "broad market", "indices", "index", "spy", "macro", "cpi", "inflation",
    "fed ", "fomc", "rates", "vix", "volatility today", "breadth", "rotation",
    "what happened today", "how is the market", "market summary",
)


def _wants_market(text: str) -> bool:
    low = (text or "").lower()
    return any(h in low for h in _MARKET_HINTS)


async def _market_context() -> Optional[Dict[str, Any]]:
    """Index levels, breadth, the regime score and today's macro calendar.

    A question like "why is there so much chop today" needs the tape, not a
    ticker — and there was no path to it: no symbol in the question meant no
    auto-load, so CONTEXT stayed at {"active_view": "home"} and the answer became
    a list of things to go and open.

    Served from the daily brief, which is already built and cached, so this costs
    nothing beyond a dict lookup on the common path.
    """
    try:
        brief = await _run(brief_mod.state, YF_PROVIDER, None, False)
    except Exception as exc:
        logging.getLogger("uvicorn.error").warning("market context failed: %s", exc)
        return None
    if not isinstance(brief, dict):
        return None

    overview = brief.get("overview") or {}
    out: Dict[str, Any] = {
        "as_of": brief.get("day"),
        "indices": (overview.get("groups") or {}).get("indices"),
        "sectors": (overview.get("groups") or {}).get("sectors"),
        "mag7": (overview.get("groups") or {}).get("mag7"),
        "sector_breadth_pct": overview.get("sector_breadth_pct"),
        "leaders": overview.get("leaders"),
        "laggards": overview.get("laggards"),
        "written_summary": brief.get("summary"),
        "macro_releases": (brief.get("macro") or {}).get("entries"),
        "calendar": (brief.get("calendar") or {}).get("events"),
    }
    # The index regime score, so a market question gets the same composite the
    # Read tab is built around rather than the model eyeballing percentages.
    try:
        out["index_regime"] = regime_mod.score(overview)
    except Exception:
        pass
    out["note"] = (
        "Index and sector levels, breadth, the index regime score and the macro "
        "calendar, from the terminal's daily brief. This is the whole-market view; "
        "there is no single-name option chain, gamma or flow here unless a ticker "
        "block also appears in CONTEXT."
    )
    return out

async def _augment_chat_context(history: List[Dict[str, Any]],
                                context: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Load a ticker the reader named but had not opened.

    Pulse only ever saw whatever the browser happened to have on screen, so asking
    "what is NVDA's gamma saying" from the home tab shipped `{"active_view":
    "home"}` and the honest answer was "I cannot see that". Correct, and useless —
    the terminal *can* compute it, nobody had pressed the button.

    So the server now fetches it. The reader asks about a ticker, the analysis is
    built server-side and handed to the model as context. Note this deliberately
    does not switch the reader's view: they asked a question, not to navigate.
    """
    if not history:
        return context
    last = next((t for t in reversed(history) if t.get("role") != "assistant"), None)
    if not last:
        return context

    already = {(context or {}).get("ticker", "") or ""}
    for key in ("swing", "earnings", "long"):
        block = (context or {}).get(key)
        if isinstance(block, dict):
            already.add((block.get("ticker") or "").upper())

    text = last.get("content") or ""
    wanted = [s for s in _symbols_in(text) if s not in already]

    if not wanted:
        # No symbol named. Give the question whatever it is actually about.
        out = dict(context or {})
        added = False
        if _wants_candidates(text):
            candidates = _screen_candidates()
            if candidates:
                out["screen_candidates"] = candidates
                added = True
        if _wants_market(text) and not out.get("macro") and not out.get("read"):
            market = await _market_context()
            if market:
                out["market"] = market
                added = True
        return out if added else context

    out = dict(context or {})
    fetched: Dict[str, Any] = {}
    for symbol in wanted[:_CHAT_MAX_LOOKUPS]:
        try:
            fetched[symbol] = await _run(_swing_snapshot, symbol, None, 2, True)
        except Exception as exc:                       # a bad symbol must not 500 the chat
            logging.getLogger("uvicorn.error").warning(
                "chat auto-load failed for %s: %s", symbol, exc)
    if fetched:
        out["auto_loaded"] = fetched
        out["auto_loaded_note"] = (
            "Fetched by the server because the question named these symbols and they "
            "were not open in the reader's browser. Same data the tabs would show."
        )
    return out


@app.get("/api/personas")
async def personas() -> Dict[str, Any]:
    """The response lenses Pulse can adopt.

    Served rather than hardcoded in the client so the two cannot drift — a
    persona the UI offers but the server does not know would silently fall back
    to neutral and look like the setting had no effect.
    """
    return {
        "default": ai.DEFAULT_PERSONA,
        "personas": [
            {"id": key, "label": val["label"], "blurb": val["blurb"]}
            for key, val in ai.PERSONAS.items()
        ],
    }


# ----------------------------------------------------------------- write guard
#
# The app has no sign-in and that is deliberate: every research endpoint should
# answer anybody who finds the URL. But "anyone may read this" and "anyone may
# rewrite my track record" are separable claims, and they were bundled.
#
# Three endpoints change state — a manual scan opens paper positions, a re-mark
# moves their marks, and clearing the alert inbox deletes rows. On a public URL
# that made the ledger a shared scratchpad: a stranger appending junk trades is
# indistinguishable from the owner doing it, which quietly destroys the one
# thing the record is for.
#
# So: reads stay open to everyone, writes want a token.
#
# Fail-closed in production, open locally. If the token is unset the guard has
# to decide what unset means, and both answers are wrong somewhere — refusing
# breaks a local checkout that never had a token, allowing leaves a forgotten
# deployment wide open. Deciding by whether a hosting platform is present gets
# both right without anyone configuring anything: Railway, Render and Fly all
# announce themselves in the environment, and a laptop does not.
WRITE_TOKEN = os.environ.get("OPTIC_WRITE_TOKEN", "").strip()

_PLATFORM_VARS = ("RAILWAY_ENVIRONMENT", "RAILWAY_GIT_COMMIT_SHA",
                  "RENDER", "FLY_APP_NAME")


def is_hosted() -> bool:
    """True when running on a hosting platform rather than a local machine."""
    return any(os.environ.get(v) for v in _PLATFORM_VARS)


def _write_guard(request: Request) -> None:
    """Allow a state-changing request, or explain what it needs."""
    if WRITE_TOKEN:
        supplied = request.headers.get("x-optic-token", "")
        # Constant-time: a plain == leaks the shared prefix through timing, and
        # this token is the only thing standing in front of the ledger.
        if secrets.compare_digest(supplied, WRITE_TOKEN):
            return
        raise HTTPException(
            status_code=401,
            detail="This action changes the record, so it needs the write token. "
                   "Reading every panel stays open to everyone.",
        )
    if is_hosted():
        raise HTTPException(
            status_code=503,
            detail="Writes are disabled: this deployment has no OPTIC_WRITE_TOKEN "
                   "set, so it refuses to let anonymous callers change the ledger. "
                   "Scheduled scans still run.",
        )
    # Local, no token configured: the historical behaviour.


# ----------------------------------------------------------------- spend guard
#
# /api/chat and /api/research are the only endpoints that cost money, and the
# app is deliberately open — no accounts, no sign-in. Those two facts together
# mean an unmetered spend endpoint on a public URL: one script in a loop could
# drain the Anthropic balance, and the first sign of it would be the bill.
#
# A per-IP token bucket keeps the door open to every real visitor while capping
# what any single caller can spend. It is not security — an attacker with many
# addresses gets many buckets — but it turns "drain the account in a minute"
# into "drain it slowly enough to notice", which is the actual exposure here.
#
# In-process and per-instance on purpose: one worker (see the Dockerfile) means
# one bucket, and a shared store would be a database dependency for a counter.
# The state is lost on restart, which is the safe direction to fail.
AI_CALLS_PER_HOUR = int(os.environ.get("AI_CALLS_PER_HOUR", "30"))

_ai_calls: Dict[str, List[float]] = {}


def _spend_guard(request: Request) -> None:
    """Raise 429 once a caller has spent its hourly allowance."""
    if AI_CALLS_PER_HOUR <= 0:            # 0 disables the guard
        return
    # Behind Railway/Cloudflare the socket peer is the proxy, so prefer the
    # forwarded chain's first hop. Spoofable, but so is any header, and the
    # alternative is bucketing every visitor together as one proxy IP.
    fwd = request.headers.get("x-forwarded-for", "")
    who = fwd.split(",")[0].strip() or (request.client.host if request.client else "?")

    now = time.time()
    recent = [t for t in _ai_calls.get(who, []) if now - t < 3600]
    if len(recent) >= AI_CALLS_PER_HOUR:
        oldest = min(recent)
        wait = int(3600 - (now - oldest))
        _ai_calls[who] = recent
        raise HTTPException(
            status_code=429,
            detail="This demo allows {} assistant messages an hour per visitor, "
                   "to keep one caller from spending the whole budget. Try again "
                   "in about {} minutes.".format(AI_CALLS_PER_HOUR, max(1, wait // 60)),
        )
    recent.append(now)
    _ai_calls[who] = recent

    # Keep the dict from growing without bound on a long-lived instance.
    if len(_ai_calls) > 2048:
        for addr in [a for a, hits in _ai_calls.items()
                     if not any(now - t < 3600 for t in hits)]:
            _ai_calls.pop(addr, None)


@app.post("/api/chat")
async def chat(request: Request,
               payload: Dict[str, Any] = Body(...)) -> StreamingResponse:
    """Streaming assistant.

    Send {messages: [{role, content}], context: {...}, attachments: [...]}.
    Attachments are {name, media_type, data} with base64 data; they are passed
    straight through to the model and never written to disk.
    """
    _spend_guard(request)
    history = payload.get("messages") or []
    context = payload.get("context")
    use_web = bool(payload.get("web"))
    attachments = payload.get("attachments")
    persona = str(payload.get("persona") or ai.DEFAULT_PERSONA)
    context = await _augment_chat_context(history, context)
    return StreamingResponse(
        ai.stream_chat(history, context=context, use_web=use_web,
                       attachments=attachments, persona=persona),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/research")
async def research(request: Request,
                   payload: Dict[str, Any] = Body(...)) -> StreamingResponse:
    """Streaming live web research for a ticker or macro question."""
    _spend_guard(request)
    ticker = (payload.get("ticker") or "").upper()
    question = payload.get("question")
    context = payload.get("context")
    if not ticker and not question:
        raise HTTPException(status_code=400, detail="Provide a ticker or a question.")
    return StreamingResponse(
        ai.deep_research(ticker, question=question, context=context),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# --------------------------------------------------------------------- static
#
# Mounted at "/" (not "/static") so index.html's own asset references
# (styles.css, app.js, charts.js) are plain siblings — the same relative
# paths that resolve correctly if someone opens the file directly from disk
# instead of through the server. This mount must stay the last route
# registered: Starlette matches in registration order, and a mount at "/"
# would otherwise shadow every /api/* route above it.

# Two problems this block fixes, both of which present as "my change didn't ship":
#
# 1. Plain StaticFiles sends ETag and Last-Modified but no Cache-Control. With no
#    explicit policy a browser is free to apply heuristic freshness, and Chrome
#    caches index.html for a fraction of its age without revalidating. The
#    ?v= query on the asset tags cannot help: it lives *inside* the HTML that is
#    itself stale, so an old page keeps requesting the old assets and every
#    change looks like it silently did nothing.
#
# 2. The ?v= number in index.html was maintained by hand, so shipping an edit
#    meant remembering to bump it. _ASSET_V derives it from the mtimes of the
#    three assets instead, and the "/" route below substitutes it on the way
#    out. The literal in the file stays as the fallback for opening index.html
#    straight from disk, where there is no server to rewrite anything.


def _asset_version() -> str:
    """A cache key that changes whenever any front-end asset changes."""
    stamp = 0
    for name in ("app.js", "charts.js", "styles.css"):
        try:
            stamp = max(stamp, int((STATIC_DIR / name).stat().st_mtime))
        except OSError:
            continue
    return str(stamp)


class _NoCacheHTML(StaticFiles):
    """Revalidate HTML every time; let ETag turn that into a cheap 304.

    Assets get the same treatment rather than a long max-age. A far-future
    max-age would be safe only if the ?v= key were guaranteed correct, and
    trusting that is what broke above."""

    def file_response(self, *args: Any, **kwargs: Any) -> Any:
        resp = super().file_response(*args, **kwargs)
        resp.headers.setdefault("Cache-Control", "no-cache")
        return resp


if STATIC_DIR.exists():
    _INDEX = STATIC_DIR / "index.html"

    @app.get("/", include_in_schema=False)
    async def index() -> Any:
        """index.html with the asset version stamped in from the file mtimes."""
        html = _INDEX.read_text(encoding="utf-8")
        html = re.sub(r"\?v=\d+", "?v=" + _asset_version(), html)
        return Response(content=html, media_type="text/html",
                        headers={"Cache-Control": "no-cache"})

    app.mount("/", _NoCacheHTML(directory=str(STATIC_DIR), html=True), name="static")
