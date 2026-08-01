"""FastAPI backend for Optic Terminal."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import ai, legal, news as news_mod, paper, session as session_mod
from . import universe as universe_mod
from .analytics import earnings as earnings_mod
from .analytics import entry as entry_mod
from .analytics import flow as flow_mod
from .analytics import fundamentals as fundamentals_mod
from .analytics import gex as gex_mod
from .analytics import greeks_panel, longterm, macro as macro_mod
from .analytics import retirement as retirement_mod
from .analytics import scalp as scalp_mod
from .analytics import sectors as sectors_mod
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

    return {
        "ticker": ticker,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_source": PROVIDER.name,
        "data_caveat": data_caveat,
        "quote": quote,
        "verdict": call,
        "technicals": tech,
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


# -------------------------------------------------------------------- routes


@app.get("/api/health")
async def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "provider": PROVIDER.name,
        "realtime_chain": PROVIDER.name == "tradier",
        "assistant": ai.available(),
        "server_time": datetime.now(timezone.utc).isoformat(),
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


@app.get("/api/scalp/{ticker}")
async def scalp_panel(ticker: str) -> Dict[str, Any]:
    """Intraday / scalping panel: VWAP, opening range, pivots, relative
    volume, fast momentum, near-term (0DTE-first) gamma, and squeeze read.

    Uses PROVIDER (Tradier when configured) for intraday bars and the option
    chain — the one panel in the app where that choice actually matters — and
    YF_PROVIDER for short interest, which Tradier doesn't have.
    """
    def build() -> Dict[str, Any]:
        ticker_u = ticker.upper().strip()
        quote = PROVIDER.quote(ticker_u)
        result = scalp_mod.analyse(PROVIDER, YF_PROVIDER, ticker_u, quote, rate=RISK_FREE)
        result["generated_at"] = datetime.now(timezone.utc).isoformat()
        return result

    return await _run(build)


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
) -> Dict[str, Any]:
    """The ledger. `month` selects which month's trades to detail; the monthly
    breakdown is always included so the dropdown can be built without a second
    request."""
    return await _run(paper.state, 60, month)


@app.post("/api/tracker/mark")
async def tracker_mark() -> Dict[str, Any]:
    """Refresh marks on open positions without looking for new entries."""
    async with _SCAN_LOCK:
        return await _run(paper.mark_open_positions, PROVIDER, RISK_FREE)


async def _do_scan(tickers: Optional[List[str]], trigger: str) -> Dict[str, Any]:
    async with _SCAN_LOCK:
        return await _run(
            paper.run_scan, _tracker_snapshot, PROVIDER, tickers, trigger, RISK_FREE
        )


@app.post("/api/tracker/scan")
async def tracker_scan(payload: Optional[Dict[str, Any]] = Body(None)) -> Dict[str, Any]:
    """Start a scan and return immediately.

    A NASDAQ-wide scan screens ~3,000 symbols and then puts a shortlist through
    the full analysis — minutes, not seconds. Holding the HTTP request open for
    that long means a proxy timeout decides whether the scan is recorded, so the
    work runs as a task and the tab polls /api/tracker for progress instead.
    """
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


@app.post("/api/chat")
async def chat(payload: Dict[str, Any] = Body(...)) -> StreamingResponse:
    """Streaming assistant. Send {messages: [{role, content}], context: {...}}."""
    history = payload.get("messages") or []
    context = payload.get("context")
    use_web = bool(payload.get("web"))
    return StreamingResponse(
        ai.stream_chat(history, context=context, use_web=use_web),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/research")
async def research(payload: Dict[str, Any] = Body(...)) -> StreamingResponse:
    """Streaming live web research for a ticker or macro question."""
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

if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
