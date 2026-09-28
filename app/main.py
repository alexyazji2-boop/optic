"""FastAPI backend for Optic Terminal."""

from __future__ import annotations

import asyncio
import contextvars
from concurrent.futures import ThreadPoolExecutor
import logging
import os
import re
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from . import (ai, brief as brief_mod, feeds as feeds_mod, legal,
               news as news_mod, paper, session as session_mod)
from . import account as account_mod
from . import db as accounts_db
from .auth import admin as auth_admin
from .auth import deps as auth_deps
from .auth import ratelimit as auth_ratelimit
from . import feedback as feedback_mod
from .auth import routes as auth_routes
from .auth import store as auth_store
from .runtime import is_hosted
from . import snapshots
from . import universe as universe_mod
from . import earnings_week as earnings_week_mod
from . import priority as priority_mod
from . import weekly as weekly_mod
from . import catalysts as catalysts_mod
from . import catalyst_live as catalyst_live_mod
from . import live_mirror
from .analytics import cases as cases_mod
from .analytics import congress as congress_mod
from . import papertrade as papertrade_mod
from . import contracts as contracts_mod
from .analytics import screen as screen_mod
from .analytics import stage as stage_mod
from .analytics import screener as screener_mod
from .analytics import segments as segments_mod
from . import insiders as insiders_mod
from .analytics import regime as regime_mod
from .analytics import relperf as relperf_mod
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
from .analytics import series_stats as series_stats_mod
from .analytics import morning_desk as morning_desk_mod
from .analytics import forex as forex_mod
from . import alerts as alerts_mod
from .analytics import econ as econ_mod
from .analytics import pulse as pulse_mod
from .analytics import watchlist as watchlist_mod
from . import knowledge as knowledge_mod
from . import watch_runner
from .analytics import watches as watches_mod
from . import events as events_mod
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
from .providers import yf as yf_provider_mod
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

# --------------------------------------------------------------- app logging
#
# Without this, nothing this application logs is ever seen.
#
# `logging.basicConfig` exists in exactly one place in the tree, inside
# `app/db.py`'s `if __name__ == "__main__"` block, which uvicorn never reaches.
# Uvicorn configures its own three loggers and leaves the root alone, so every
# `log.info` in this package propagated to a root logger with no handler at the
# default WARNING and was dropped on the floor.
#
# What that cost, and it is not hypothetical. `app/auth/mailer.py` falls back to
# writing a verification link to the log when no relay is configured, and says
# so to the reader: "Email is not configured on this deployment, so the link
# went to the server log." DEPLOY.md and CLAUDE.md repeat the promise. The line
# was never emitted, so on a deployment with no SMTP an address could not be
# confirmed by any route at all -- which also meant `ADMIN_EMAILS` could never
# take effect, because `is_admin` requires a *verified* address. Measured on a
# local server with `--log-level info`: registering an account produced zero
# `[mail:log]` lines.
#
# Two trees, not one, and the first attempt at this fix configured the wrong
# one. Modules here take a logger three ways: `getLogger(__name__)` gives
# `app.*`, `getLogger("uvicorn.error")` borrows uvicorn's (already configured,
# which is why warm-up lines have always been visible and hid the problem), and
# ten call sites use an explicit `optic` or `optic.<area>`. `app/auth/mailer.py`
# is one of those ten -- its logger is `optic.mail` -- so scoping this to the
# package tree alone left the exact line this was written to rescue still
# invisible.
#
# Scoped to our own trees rather than the root, so a dependency's INFO chatter
# does not arrive with it. `propagate = False` because uvicorn's handler is on
# its own loggers rather than root, and leaving propagation on would print each
# line twice the moment anything attaches one there.
for _name in (__package__ or "app", "optic"):
    _pkg_log = logging.getLogger(_name)
    if not _pkg_log.handlers:
        _handler = logging.StreamHandler()
        _handler.setFormatter(
            logging.Formatter("%(levelname)s:     %(name)s - %(message)s"))
        _pkg_log.addHandler(_handler)
        _pkg_log.setLevel(logging.INFO)
        _pkg_log.propagate = False


app = FastAPI(title="Optic Terminal", version="1.0.0")

# ------------------------------------------------------------------ transfer
#
# Compress what goes over the wire. app.js is 1.2 MB of source and styles.css is
# 408 KB, and `StaticFiles` sends both raw: measured, a local request for app.js
# with `Accept-Encoding: gzip` came back 1,258,176 bytes with no
# `Content-Encoding` header at all.
#
# Railway's edge already gzips in production, where the same three files arrive
# as 389 KB, 38 KB and 103 KB. So this is not what makes the live site fast; it
# is here for the two cases the edge does not cover. Local development was
# serving 1.75 MB uncompressed, which is not the shape of the thing being
# tested, and an edge that stops compressing should degrade the transfer rather
# than silently quadruple it.
#
# 800 bytes rather than the 500-byte default: below about that, the gzip header
# and the loss of the proxy's ability to stream cost more than the saving, and
# every JSON payload worth compressing here is far larger.
app.add_middleware(GZipMiddleware, minimum_size=800)

# ------------------------------------------------------ open, with accounts
#
# Every research endpoint still answers anybody. There is no wall in front of the
# terminal: load a ticker, read the analysis, open a chart, run a screen, all
# without an account. That was a deliberate decision and it has not changed.
#
# What accounts add is *keeping* things — a watchlist, saved research,
# preferences — which needs somewhere to put them and someone to own them. See
# `app/auth/` and `app/db.py`. A guest loses nothing they had before.
#
# The one thing that is metered is the assistant: /api/chat and /api/research
# spend real money per call. Guests get a small daily allowance, signing in
# raises it to the account's plan, and a per-IP hourly cap sits over both as the
# burst limit. See _spend_guard.
@app.get("/healthz")
async def healthz() -> Dict[str, bool]:
    """Liveness probe for hosting platforms. Deliberately says nothing else."""
    return {"ok": True}


@app.on_event("startup")
async def _warn_if_open_and_paid() -> None:
    if ai.available().get("enabled"):
        logging.getLogger("uvicorn.error").warning(
            "Pulse is enabled and this server has no access control. Anyone who "
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


# Set by the scheduled loops, so everything they run takes the jobs' lane at
# the rate limiter and a reader's fetches go first (see yf.background). A
# context variable because each loop is its own task: set inside one, it is
# seen by that task's _run calls and by nobody else's.
_BACKGROUND_JOB = contextvars.ContextVar("optic_background_job", default=False)


def _run(fn, *args, **kwargs):
    """Push blocking provider/analytics work off the event loop."""
    if _BACKGROUND_JOB.get():
        def call():
            with yf_provider_mod.background():
                return fn(*args, **kwargs)
    else:
        def call():
            return fn(*args, **kwargs)
    return asyncio.get_running_loop().run_in_executor(None, call)


# ------------------------------------------------------------------ assembly


# The ticker build's slow, independent fetches, run side by side on request.
#
# Measured on a cold symbol (PINS, 2026-09-28): macro 2.6s, fundamentals 2.4s,
# SEC filings 0.9s, the sector check 0.7s, and about half a second each for the
# quote, the history, the option chains and the news, 9.3s in all, one after
# another, though nothing waits on another's answer except fundamentals on the
# quote. On the live site first loads measured 9.4s, 10.3s and 58.1s: long
# enough that a reader who pressed Load once took it for broken and pressed it
# again, and the second press found the caches the first had filled. Reported
# as "I need to change the ticker with two inputs, not one".
#
# One pool for the process, not one per request, so an early exit (the 404 for
# a symbol with no prices) leaves nothing to shut down: a leg nobody collects
# finishes and fills its cache. Legs never wait on legs, so the pool cannot
# deadlock against itself, and every provider call is still paced by the
# provider's own limiter.
#
# Thirty-two since the company fetches became legs of their own: a first load
# is now eighteen, and two readers loading at once would otherwise queue each
# other's. A leg can wait on another only through a provider key lock, which
# is held by a thread that is already running, so a full pool still cannot
# deadlock.
_LEG_POOL = ThreadPoolExecutor(max_workers=32, thread_name_prefix="ticker-leg")


class _Timings:
    """Where one request's time went, sent as its Server-Timing header.

    That header because the browser's network panel draws it beside the
    request and `curl -D -` prints it, so reading the live site's numbers needs
    no log access. Every row is milliseconds:

      queue    waiting for a worker thread before the build started
      build    the build, start to finish
      compute  the build's own work, which is `build` less the time it sat
               waiting on a leg
      cpu      CPU the whole process used over the build. Near `build`, the
               server was busy computing rather than waiting on Yahoo; other
               requests running at the same moment count as well.
      <leg>    each fetch, with when it started, how long the rate limiter
               held it, how long it waited on a lock (the same data already
               being fetched by another leg, or the download lock), how long
               its requests took, and how many it made. A wait on the download
               lock is inside a request, so it counts in both.
    """

    def __init__(self) -> None:
        self.t0 = time.perf_counter()
        self.started: Optional[float] = None
        self.ended: Optional[float] = None
        self._cpu: List[float] = []
        self.blocked = 0.0
        self.legs: List[tuple] = []
        self._lock = threading.Lock()

    def begin(self) -> None:
        self.started = time.perf_counter()
        self._cpu = [time.process_time()]

    def finish(self) -> None:
        self.ended = time.perf_counter()
        if self._cpu:
            self._cpu.append(time.process_time())

    def wrap(self, name: str, fn):
        def timed(*args, **kwargs):
            yf_provider_mod.meter_reset()
            began = time.perf_counter()
            try:
                return fn(*args, **kwargs)
            finally:
                took = time.perf_counter() - began
                gated, locked, fetching, requests = yf_provider_mod.meter_read()
                with self._lock:
                    self.legs.append((name, began - self.t0, took, gated, locked,
                                      fetching, requests))
        return timed

    def header(self) -> str:
        def ms(sec: float) -> str:
            return "{:.1f}".format(sec * 1000.0)

        end = self.ended if self.ended is not None else time.perf_counter()
        start = self.started if self.started is not None else self.t0
        parts = ["queue;dur=" + ms(start - self.t0),
                 "build;dur=" + ms(end - start),
                 "compute;dur=" + ms(max(end - start - self.blocked, 0.0))]
        if len(self._cpu) == 2:
            parts.append("cpu;dur=" + ms(self._cpu[1] - self._cpu[0]))
        with self._lock:
            legs = sorted(self.legs, key=lambda row: row[1])
        # " / " inside the description rather than commas: a comma in a quoted
        # desc is legal, but it is also what every hand-rolled reader of this
        # header splits the metrics on, the first one written for it included.
        for name, at, took, gated, locked, fetching, requests in legs:
            parts.append(
                '{};dur={};desc="at {} ms / gate {} ms / lock {} ms / fetch {} ms / {} req"'.format(
                    name, ms(took), ms(at).split(".")[0], ms(gated).split(".")[0],
                    ms(locked).split(".")[0], ms(fetching).split(".")[0], requests))
        return ", ".join(parts)


class _Legs:
    """Start fetches together, or run each where it is read.

    Sequential is the default and the scans keep it: a scan builds a snapshot
    for thirty names, and eight requests at once per name is the traffic that
    earns a rate limit. In that mode `get` makes the call at the point the
    build reads it, so a scan's order of calls is what it always was. Either
    way a leg's exception surfaces at `get`, inside whatever try the build
    already had around that call.
    """

    def __init__(self, parallel: bool, timings: Optional[_Timings] = None) -> None:
        self.parallel = parallel
        self.timings = timings
        self._legs: Dict[str, Any] = {}

    def start(self, name: str, fn, *args, **kwargs) -> None:
        if self.timings is not None:
            fn = self.timings.wrap(name, fn)
        self._legs[name] = (_LEG_POOL.submit(fn, *args, **kwargs) if self.parallel
                            else (fn, args, kwargs))

    def get(self, name: str) -> Any:
        leg = self._legs.pop(name)
        began = time.perf_counter()
        try:
            if not self.parallel:
                fn, args, kwargs = leg
                return fn(*args, **kwargs)
            return leg.result()
        finally:
            if self.timings is not None:
                self.timings.blocked += time.perf_counter() - began


def _sector_confirm(ticker: str) -> Dict[str, Any]:
    prof = YF_PROVIDER.profile(ticker) or {}
    return sector_confirm_mod.build(YF_PROVIDER, ticker, prof.get("sector"))


def _swing_snapshot(
    ticker: str,
    expiries: Optional[List[str]],
    max_expiries: int,
    include_macro: bool,
    # Keyword-only, and that bar is load-bearing rather than tidy. Adding
    # `include_company` in front of `budget` silently rebound one caller's
    # budget argument onto the new flag -- `_run(_swing_snapshot, ticker,
    # wanted, max_expiries, macro, True, budget)` -- so /api/ticker passed
    # budget=None as include_company and the Dossier lost its fundamentals.
    # Nothing raised; production just started answering "not requested".
    *,
    include_earnings: bool = True,
    include_company: bool = True,
    budget: Optional[float] = None,
    parallel: bool = False,
    timings: Optional[_Timings] = None,
) -> Dict[str, Any]:
    ticker = ticker.upper().strip()
    if timings is not None:
        timings.begin()

    legs = _Legs(parallel, timings)
    legs.start("quote", PROVIDER.quote, ticker)
    legs.start("hist", PROVIDER.history, ticker, period="2y", interval="1d")
    legs.start("news", news_mod.analyse, YF_PROVIDER, ticker)
    legs.start("expiries", PROVIDER.expirations, ticker)
    legs.start("chain", PROVIDER.options_chain, ticker, expiries=expiries,
               max_expiries=max_expiries)
    if include_macro:
        legs.start("macro", macro_mod.analyse, YF_PROVIDER)
    if include_earnings:
        legs.start("earnings", earnings_mod.momentum, YF_PROVIDER, ticker)
    legs.start("filings", filings_mod.recent, ticker)
    legs.start("sector", _sector_confirm, ticker)
    legs.start("earnings_date", YF_PROVIDER.earnings_date, ticker)
    # Read at the very end, by "what matters next", and started here: on a
    # fresh server it is the FRED calendar fetched cold, and inside the build's
    # own work it made `compute` 1.45s of a 1.9s first load (SNPS, 2026-09-28).
    legs.start("calendar", _macro_calendar_rows)
    # The company and earnings blocks' own fetches, started now rather than one
    # after another inside those blocks. They were the last two legs to finish:
    # fundamentals is five fetches in a row and could not start before the
    # quote, earnings momentum three. Profiled on cold symbols (SNAP, LYFT,
    # 2026-09-28) the company leg ran from 0.39s to 2.05s and the earnings leg
    # to 1.76s, with everything else done by 1.2s. The blocks themselves are
    # unchanged and find these in the provider's cache, or wait on the one
    # already in flight, so each is still one request.
    #
    # Only in parallel: nothing collects these, so a scan, which builds this
    # sequentially and runs a leg only when it reads it, never starts them.
    if legs.parallel:
        if include_company:
            legs.start("short_interest", YF_PROVIDER.short_interest, ticker)
            legs.start("insiders", YF_PROVIDER.insiders, ticker)
            legs.start("institutions", YF_PROVIDER.institutions, ticker)
        if include_company or include_earnings:
            legs.start("financials", YF_PROVIDER.financials, ticker)
            legs.start("earnings_history", YF_PROVIDER.earnings_history, ticker)
        if include_earnings:
            legs.start("estimates", YF_PROVIDER.estimates, ticker)

    quote = legs.get("quote")
    # The one leg that needs another's answer, started the moment it has it.
    if include_company:
        legs.start("company", fundamentals_mod.analyse, YF_PROVIDER, ticker, quote)
    hist = legs.get("hist")
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
    news_read = legs.get("news")

    available_expiries = legs.get("expiries")
    chain = legs.get("chain")

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
        note = "No options chain available for {}. Equity/technical analysis only.".format(ticker)
        gex_read = {"error": note}
        flow_read = {"error": note}
        greeks_read = {"error": note}

    macro_read: Optional[Dict[str, Any]] = None
    if include_macro:
        try:
            macro_read = legs.get("macro")
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
            exposure, spot, call, tech, gex_read, news_read, rate=RISK_FREE, div=div,
            history=hist, budget=budget,
        )

    # Same argument as earnings_momentum below, and it was missed here because
    # this block is one call rather than three. Measured: fundamentals.analyse
    # is five provider fetches and 1.8s per ticker -- short interest, the
    # statements, earnings history, insider and institutional holdings. Over a
    # thirty-name shortlist that is 150 requests and about 54 seconds spent on
    # a block `consider_ticker` never opens: it reads verdict, technicals,
    # quote, entry_plan and ticker, and nothing else.
    company: Dict[str, Any] = {"available": False, "reason": "not requested"}
    if include_company:
        try:
            company = legs.get("company")
        except Exception as exc:  # company data is context, never fatal
            company = {"error": "fundamentals unavailable: {}".format(exc)}

    # Shown on the Swing tab but never scored. Skipped for tracker scans: it costs
    # three more provider calls per ticker, and over a thirty-name shortlist that
    # is exactly the extra traffic that earns a rate limit — for a panel the
    # ledger doesn't read.
    earnings_momentum: Dict[str, Any] = {"available": False, "reason": "not requested"}
    if include_earnings:
        try:
            earnings_momentum = legs.get("earnings")
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
    payload["filings"] = legs.get("filings")
    # Days to expiry, so the dealer-gamma and charm readings can be read against
    # the date they unwind on rather than in isolation.
    payload["expiry_context"] = expiries_mod.context()
    # Whether the group around this name agrees with it. Sector context is the
    # weakest of the claims made about a setup, so it is reported beside the
    # per-name analysis rather than folded into the score.
    try:
        payload["sector_confirm"] = legs.get("sector")
    except Exception as exc:
        logging.getLogger("uvicorn.error").warning(
            "sector confirmation unavailable for %s: %s", ticker, exc)

    # The three answers the asset page leads with, built last from the finished
    # payload for the same reason `cases` is: they cite other panels, so they
    # must not be able to disagree with the numbers those panels show.
    #
    # No AI call in any of them. The writers are capped at thirty calls an hour
    # and these have to render on every page load for every symbol, so all three
    # are derived from fields already in this dict.
    # The evaluation is a multi-symbol backtest and far too slow to run inside a
    # ticker load, so the skill note is filled by the client from /api/evaluate
    # when that panel's data is already in hand. Until then the note says the
    # blend has not been measured on this run, which is true.
    payload["pulse"] = pulse_mod.pulse(payload, None)
    payload["why"] = pulse_mod.why(payload)
    # The next earnings date, which is nowhere else in this payload:
    # company.earnings_history is past prints and earnings_momentum carries no
    # date at all. It is the largest scheduled risk a holder has, so "what
    # matters next" without it would be missing the obvious answer. Cached by
    # the provider and best-effort, like the calendar.
    try:
        payload["next_earnings_date"] = legs.get("earnings_date")
    except Exception as exc:
        logging.getLogger("uvicorn.error").warning(
            "next earnings date unavailable for %s: %s", ticker, exc)
    payload["whats_next"] = pulse_mod.whats_next(payload, legs.get("calendar"))
    # The layer above the eight options panels. Same reasoning as `why`: the
    # workings were all present and the summary was not.
    payload["options_brief"] = pulse_mod.options_brief(payload)
    # Last, because it reads pulse, why, news, quote, gex and technicals and
    # turns them into the sentence the panel leads with. Ordering is load-
    # bearing: built before `why` it would have no attribution to name, and the
    # lede would degrade to the bare price move on every symbol.
    payload["digest"] = pulse_mod.digest(payload)
    return payload


def _macro_calendar_rows() -> List[Dict[str, Any]]:
    """Upcoming scheduled macro releases, for "what matters next".

    events.upcoming() is the same calendar the Read tab draws, already cached
    and already filtered to a horizon, so this borrows it rather than fetching
    the agencies again.

    Best-effort by design: a missing calendar drops the macro rows from the
    section, it does not fail the page. The section states what it found, so
    losing a leg is visible rather than silent.
    """
    try:
        data = events_mod.upcoming()
        return (data or {}).get("events") or []
    except Exception as exc:
        logging.getLogger("uvicorn.error").warning("macro calendar unavailable: %s", exc)
        return []


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
        "accounts": _accounts_health(),
    }


def _accounts_health() -> Dict[str, Any]:
    """Whether the accounts schema is where the code expects it.

    Here because the migration runner fires on boot inside a try/except that
    logs and carries on, which is right (a broken accounts database must not
    take down a terminal whose research endpoints all work without one) and
    leaves no way to observe the outcome from outside. Adding a table and
    deploying it, the only available check was that the new endpoints returned
    401 to a guest, and that is `require_user` answering before any query runs:
    it proves the route is registered and says nothing about the table.

    Same idea as `feeds.CONTACT_OK`, which exists so a missing address shows up
    as configuration rather than as a broken section.

    Version numbers only. The migration list is in a public repository already,
    so this discloses nothing, and it stops short of any row count or column
    name so it cannot become a schema dump.
    """
    try:
        applied = accounts_db.applied()
        return {
            "ready": applied == [m[0] for m in accounts_db.MIGRATIONS],
            "applied": applied,
            "known": [m[0] for m in accounts_db.MIGRATIONS],
        }
    except Exception as exc:
        # Never the reason /api/health fails. Health saying "I could not tell"
        # is useful; health 500ing because a side question raised is not.
        return {"ready": False, "error": type(exc).__name__}


@app.get("/api/ticker/{ticker}")
async def ticker_analysis(
    ticker: str,
    response: Response,
    expiries: Optional[str] = Query(None, description="Comma-separated YYYY-MM-DD expiries"),
    max_expiries: int = Query(4, ge=1, le=10),
    macro: bool = Query(True, description="Include the macro regime panel"),
    budget: Optional[float] = Query(
        None, ge=0, le=1_000_000,
        description="Most one contract may cost, in dollars. Omitted means no filter."),
) -> Dict[str, Any]:
    """Full swing-trading analysis for one ticker.

    `budget` is what the reader can place on one contract, not their account
    size. An option is quoted per share and bought in hundreds, so the number in
    the chain is a hundredth of what leaves the account, and that multiplication
    is exactly the step that gets skipped. Omitted by default: the figure is the
    reader's own business and nothing here should assume one.
    """
    wanted = [e.strip() for e in expiries.split(",") if e.strip()] if expiries else None
    _KEEP_WARM["read_at"] = time.time()
    timings = _Timings()
    payload = await _run(_swing_snapshot, ticker, wanted, max_expiries, macro,
                         include_earnings=True, budget=budget, parallel=True,
                         timings=timings)
    timings.finish()
    response.headers["Server-Timing"] = timings.header()
    return payload


@app.get("/api/quote/{ticker}")
async def quick_quote(ticker: str, response: Response) -> Dict[str, Any]:
    """The price and the name, ahead of the full analysis.

    /api/ticker is several seconds on a symbol's first load, and the Dossier's
    header strip only needs this much of it. PROVIDER.quote is the same cached
    call the build starts with, so asking for it first costs nothing: the
    build's own quote is then served from the cache this filled.
    """
    _KEEP_WARM["read_at"] = time.time()
    timings = _Timings()

    def build() -> Dict[str, Any]:
        timings.begin()
        sym = ticker.upper().strip()
        try:
            quote = timings.wrap("quote", PROVIDER.quote)(sym)
        except Exception as exc:                                # noqa: BLE001
            logging.getLogger("uvicorn.error").info("quick quote for %s: %s", sym, exc)
            return {"ticker": sym, "available": False}
        if not quote or quote.get("price") is None:
            return {"ticker": sym, "available": False}
        return {"ticker": sym, "available": True, "quote": quote}
    body = await _run(build)
    timings.finish()
    response.headers["Server-Timing"] = timings.header()
    return body


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
        # `available is not True`, not `not brief`. These writers now return a
        # dict explaining a failure instead of None, and a dict is truthy — a
        # falsiness check would sail past the guard and return the failure
        # payload with a ticker and a timestamp attached to it.
        if not brief or brief.get("available") is not True:
            status = ai.available()
            return {"available": False,
                    "reason": ("The assistant is not configured, so there is no written "
                               "brief. Every figure it would discuss is on the panel above."
                               if status.get("enabled") is not True else
                               (brief or {}).get("reason")
                               or "The brief could not be written on this attempt. The "
                                  "panel's own numbers are unaffected.")}
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
    # News rides along so the conviction can see a resolved catalyst. Best
    # effort: the long-run read is built from twelve years of prices and must
    # not fail because a headline feed is down. `news_mod.analyse` is cached for
    # ten minutes and the swing tab usually warmed it for the same symbol.
    news_read: Optional[Dict[str, Any]] = None
    try:
        news_read = await _run(news_mod.analyse, YF_PROVIDER, ticker.upper())
    except Exception as exc:                                    # noqa: BLE001
        logging.getLogger("uvicorn.error").warning(
            "longterm: news unavailable for %s: %s", ticker.upper(), exc)

    holding = await _run(longterm.analyse_holding, PROVIDER, ticker.upper(),
                         news_read)
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


@app.get("/api/watches/catalogue")
async def watch_catalogue() -> Dict[str, Any]:
    """The conditions a watch can be built from, and what each one reads."""
    return watches_mod.catalogue()


@app.post("/api/watches/check")
async def watch_check(body: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate a set of watches and report which have tripped.

    A POST because the client sends its watch definitions in the body — there
    is no sign-in, so there is no server-side row to look them up from, and a
    query string long enough to hold ten conditions is not a URL.

    Deliberately NOT behind the write guard: it stores nothing. It reads the
    same panels the analysis page reads and returns a verdict per watch, so it
    is a read that happens to need a body.

    One symbol per request. The alternative is a loop over `_swing_snapshot`,
    which is ~20 seconds each — the client checks the symbols it cares about
    and stops when it has what it needs.
    """
    ticker = str(body.get("ticker") or "").upper().strip()
    rows = body.get("watches") or []
    if not ticker:
        raise HTTPException(status_code=400, detail="A ticker is required.")
    if not isinstance(rows, list) or len(rows) > 25:
        raise HTTPException(status_code=400,
                            detail="Send a list of at most 25 watches.")

    def build() -> Dict[str, Any]:
        payload = _swing_snapshot(ticker, None, 1, False, include_earnings=True)
        try:
            payload["next_earnings_date"] = YF_PROVIDER.earnings_date(ticker)
        except Exception:
            payload["next_earnings_date"] = None
        results = watches_mod.check(payload, rows)
        return {
            "ticker": ticker,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "results": results,
            "met": [r for r in results if r.get("met")],
            "price": (payload.get("quote") or {}).get("price"),
        }

    return await _run(build)


def _watch_snapshot(symbol: str) -> Dict[str, Any]:
    """The payload `watches.check` reads, for one symbol.

    Module-level rather than a closure inside the endpoint, because the
    scheduled loop needs the same thing and two copies of "how to build a
    snapshot for a watch" is how the endpoint and the schedule come to evaluate
    different conditions from the same stored row.
    """
    payload = _swing_snapshot(symbol, None, 1, False, include_earnings=True)
    try:
        payload["next_earnings_date"] = YF_PROVIDER.earnings_date(symbol)
    except Exception:
        # An earnings date that will not load costs the earnings_near condition
        # and nothing else. Every other watch on this symbol still evaluates.
        payload["next_earnings_date"] = None
    return payload


@app.post("/api/watches/run")
async def watches_run(request: Request) -> Dict[str, Any]:
    """Evaluate every stored watch and record what fired.

    Behind the write guard because it writes, and because it is the expensive
    end of the app: one snapshot per distinct symbol under watch. Meant for the
    scheduler, and usable by hand from the same place the scans are triggered.

    The snapshot function is handed in rather than imported by the runner, so
    the runner has no dependency on this module and a test can drive it with no
    network at all.
    """
    _write_guard(request)

    def build() -> Dict[str, Any]:
        return watch_runner.run_once(_watch_snapshot)

    return await _run(build)


@app.get("/api/contracts")
async def federal_contracts(
    ticker: Optional[str] = Query(None, max_length=10,
                                  description="Resolve this symbol to a contractor"),
    limit: int = Query(12, ge=1, le=50),
) -> Dict[str, Any]:
    """Federal contract awards from USAspending.

    With no ticker: the largest new awards market-wide, which is the access
    pattern that API serves well and the useful default -- most federal
    contractors are private, so a view that only worked for a matched symbol
    would be blank most of the time.

    With one: that company's awards, but only when the recipient can be
    matched exactly. app/contracts.py explains why the rule is equality and
    not a keyword search; the short version is that asking USAspending for
    "Apple" returns a company that presses apples.

    The symbol is resolved to a legal name through the local universe file
    rather than the provider: it is a dictionary lookup against a list this
    app already keeps, where a quote would be a network call to learn a name
    that does not change.
    """
    def build() -> Dict[str, Any]:
        sym = (ticker or "").upper().strip()
        if not sym:
            return contracts_mod.recent(limit=limit)
        hits = universe_mod.search(sym, 5)
        exact = next((h for h in hits if (h.get("symbol") or "").upper() == sym), None)
        if not exact:
            return {"available": True, "matched": False, "scope": "company",
                    "ticker": sym, "awards": [],
                    "reason": "No US-listed company with that symbol.",
                    "source": "https://www.usaspending.gov/"}
        return contracts_mod.for_company(exact.get("name") or sym, sym, limit=limit)

    return await _run(build)


@app.post("/api/paper/mark")
async def paper_book_mark(payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    """Mark a hand-entered paper book. Nothing is stored.

    POST rather than GET for the reason `/api/retirement` is: a book is an
    arbitrary-length body, and somebody's positions should not end up in a URL,
    a browser history entry or a server access log. The response is computed
    and discarded; the browser keeps the only copy.

    Stored nowhere on purpose, not by omission. This terminal has no sign-in,
    so a server-side book would be one book shared by every visitor. See
    app/papertrade.py, which also explains why this cannot write to the ledger
    behind Optic Portfolio: a track record a reader can edit is not one.
    """
    def build() -> Dict[str, Any]:
        out = papertrade_mod.mark_book(
            YF_PROVIDER, payload.get("positions") or [], rate=RISK_FREE)
        out["generated_at"] = datetime.now(timezone.utc).isoformat()
        return out

    return await _run(build)


@app.get("/api/watchlist")
async def watchlist_feed(
    symbols: str = Query("", description="Comma-separated symbols"),
) -> Dict[str, Any]:
    """The watchlist as a feed: price, change, what changed, and a signal.

    The list itself lives in the browser. There is no sign-in — anyone can use
    this terminal — so there is no user to hang a server-side watchlist on, and
    localStorage is the honest place for it. The client sends what it has and
    this endpoint enriches it.

    Capped at 40 symbols. One batched history pull is fast, but the cap stops a
    hand-crafted query from turning this into a market-wide download.
    """
    wanted = [s.strip().upper() for s in symbols.split(",") if s.strip()][:40]
    return await _run(watchlist_mod.build, YF_PROVIDER, wanted)


@app.get("/api/home")
async def home_summary() -> Dict[str, Any]:
    """Everything the landing page needs, in one request.

    The home page was making zero calls and showing a marketing page. It now
    opens with the market's actual state, and four requests to paint one screen
    would make the first thing a reader sees the slowest — so the index board,
    the macro instruments, the day's read and the alert list are assembled here.

    Every leg is best-effort and reports its own absence. A landing page that
    500s because one feed is down is worse than one that says which panel is
    missing.
    """
    def build() -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "degraded": [],
        }

        def leg(name: str, fn):
            try:
                out[name] = fn()
            except Exception as exc:
                logging.getLogger("uvicorn.error").warning(
                    "home leg %s unavailable: %s", name, exc)
                out[name] = None
                out["degraded"].append(name)

        # The same board the Indices tab draws, and the same macro read the
        # Market tab draws. Reused rather than reimplemented so the landing page
        # cannot disagree with the page it links to.
        leg("indices", lambda: sector_board_mod.build(
            YF_PROVIDER, sector_board_mod.INDEX_ETFS))
        leg("macro", lambda: macro_mod.analyse(YF_PROVIDER))
        leg("session", session_mod.state)
        leg("alerts", lambda: alerts_mod.recent(limit=4))
        # The day's read is already written and cached daily, so this costs a
        # dictionary lookup rather than a model call.
        leg("read", _home_read)
        # The desk is assembled from legs already fetched above, so it adds one
        # small quote and one FRED series rather than another pass over the
        # market. Placed last because it reads `out["macro"]`.
        leg("morning_desk", lambda: _morning_desk(out.get("macro")))
        return out

    return await _run(build)


# Today's desk prose, written once and shared. Keyed on the Eastern date, which
# is what makes an AI-written note affordable at all: the home page is the most
# requested endpoint in the app, and a call per view would be a call per reader.
_DESK_PROSE: Dict[str, Any] = {}


def _desk_prose(desk: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The written voice for today, or None to keep the deterministic one.

    Cached on the date and nothing else, including the failure: if the model is
    unavailable at 9am the page does not retry it on every request for the rest
    of the day. `None` is a legitimate answer here rather than an error, because
    `morning_desk.build` has already written a correct note.
    """
    day = desk.get("date")
    if not day:
        return None
    if day in _DESK_PROSE:
        return _DESK_PROSE[day]
    try:
        prose = ai.write_morning_desk(desk)
    except Exception as exc:                                    # noqa: BLE001
        logging.getLogger("uvicorn.error").warning(
            "morning desk prose unavailable: %s", exc)
        prose = None
    if prose:
        # What it was written against, so a later request can tell whether it
        # still describes the tape (see _desk_moved).
        prose["tape_marks"] = _desk_tape(desk)
        prose["written_at"] = datetime.now(timezone.utc).isoformat()
    # One day at a time. Yesterday's note is of no use to anyone and holding it
    # would grow this dict for the life of the process.
    _DESK_PROSE.clear()
    _DESK_PROSE[day] = prose
    return prose


# How far the tape may move before the written desk stops describing it.
#
# The written voice is written once a day and was served until midnight, so
# the figures in its lead froze at whatever the first reader of the day saw:
# a note that said futures were down slightly at 9am still said so after a
# rally. Past these limits the deterministic desk is shown instead. It is
# built on every request anyway, so being accurate costs nothing. A tenth of
# a point is where a printed two-decimal change stops being a rounding matter,
# and a change of the lead's own word ("up slightly" to "flat") is stale
# whatever the size.
DESK_STALE_PCT = 0.1
DESK_STALE_VIX = 0.5


def _desk_tape(desk: Dict[str, Any]) -> Dict[str, Optional[float]]:
    """The figures the lead quotes: each index future's day change, and the VIX."""
    tape = desk.get("tape") or {}
    marks: Dict[str, Optional[float]] = {
        r["symbol"]: r.get("chg_1d") for r in (tape.get("futures") or []) if r.get("symbol")}
    marks["^VIX"] = (tape.get("vix") or {}).get("last")
    return marks


def _desk_moved(then: Dict[str, Optional[float]], now: Dict[str, Optional[float]]) -> bool:
    for sym, was in then.items():
        cur = now.get(sym)
        if was is None or cur is None:
            if was is not cur:
                return True             # a figure appeared or vanished
            continue
        if sym == "^VIX":
            if abs(cur - was) > DESK_STALE_VIX:
                return True
        elif (abs(cur - was) > DESK_STALE_PCT
              or morning_desk_mod._move_word(cur) != morning_desk_mod._move_word(was)):
            return True
    return False


def _morning_desk(macro: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Today's desk, from panels already built plus the rate path.

    The macro strip is passed in rather than refetched: the desk quotes the same
    figures the strip above it shows, and two fetches would let them disagree.

    Every input is optional. A desk with no calendar still has a tape, and one
    with no rate quote still has a calendar, so each leg fails to None rather
    than failing the panel.
    """
    events_out = None
    try:
        events_out = events_mod.upcoming()
    except Exception as exc:                                    # noqa: BLE001
        logging.getLogger("uvicorn.error").warning(
            "morning desk: calendar unavailable: %s", exc)

    rate = {"available": False, "reason": "The rate path could not be built."}
    try:
        quotes = YF_PROVIDER.batch_quote([morning_desk_mod.RATE_SYMBOL])
        month = YF_PROVIDER.contract_month(morning_desk_mod.RATE_SYMBOL)
        dff = econ_mod.series("DFF", years=1)
        effective = ((dff or {}).get("latest") or {}).get("value")
        meeting = None
        for row in ((events_out or {}).get("events") or []):
            title = (row.get("title") or "").lower()
            if "fomc" in title or "federal open market" in title:
                meeting = row.get("at")
                break
        rate = morning_desk_mod.rate_path(
            quotes.get(morning_desk_mod.RATE_SYMBOL), effective, month, meeting)
    except Exception as exc:                                    # noqa: BLE001
        logging.getLogger("uvicorn.error").warning(
            "morning desk: rate path unavailable: %s", exc)

    stories = None
    try:
        read = _home_read()
        stories = (read or {}).get("stories")
    except Exception:                                           # noqa: BLE001
        stories = None

    desk = morning_desk_mod.build(macro=macro, events=events_out, rate=rate,
                                  stories=stories)

    # The prose is an overlay, never a replacement. Every figure in `desk` stays
    # exactly as assembled, so the note and the strip above it cannot disagree,
    # and a section the model declines to write keeps the deterministic one.
    desk["voice"] = "mechanical"
    prose = _desk_prose(desk)
    # Why the written voice is not the one showing, for the line under the desk.
    # It said "not configured on this deployment" for every case, which was
    # untrue on the live site the day its note failed to write.
    if prose and _desk_moved(prose.get("tape_marks") or {}, _desk_tape(desk)):
        desk["voice_reason"] = "moved"
        desk["written_at"] = prose.get("written_at")
        prose = None
    elif not prose:
        desk["voice_reason"] = ("unconfigured" if ai.available().get("enabled") is not True
                                else "unwritten")
    if prose:
        desk["voice"] = "written"
        desk["written_by"] = prose.get("written_by")
        desk["lead"] = prose["lead"]
        for key in ("scenarios", "note", "overall"):
            if prose.get(key):
                desk[key] = prose[key]
    return desk


def _home_read() -> Optional[Dict[str, Any]]:
    """The one-paragraph market narrative, from the daily brief.

    Reads the brief from its store WITHOUT building it. brief_mod.state() would
    generate today's brief on a miss — a minute of feed fetches and several AI
    calls — and the landing page must never be the thing that triggers that. If
    today has not been written yet the panel is simply absent, and the Read tab
    is one click away to build it.
    """
    data = brief_mod._load(brief_mod.today_key())
    if not data:
        return None
    return {
        "day": data.get("day"),
        "summary": data.get("summary"),
        "overview": (data.get("overview") or {}).get("read")
        or (data.get("overview") or {}).get("summary"),
        "stories": _home_stories(data),
    }


# Desks whose stories are about the market rather than about one company or one
# agency. `regulatory` is excluded because it is an FDA and agency notice feed:
# measured, its top four entries were "FDA Rare Disease Innovation Hub" and
# three guidance agendas, which are not what is moving markets today.
_STORY_DESKS = ("markets", "economy", "analysis", "energy")


def _home_stories(brief: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The market's top stories for the landing page.

    Costs nothing: the brief is already loaded above, so this is a re-ranking of
    a list in memory rather than any kind of fetch.

    Ranked by `news.rank_wire` rather than taken off the top of the brief's own
    desks, because those are ordered by a per-source weight. Measured on the
    live wire that led with "Novo CEO tells CNBC why drugmaker is rebranding"
    and left "Ten-year Treasury yield hits 5%" further down, because CNBC
    outweighs Econbrowser. The slot is about what is moving markets, so the
    catalyst has to beat the masthead.
    """
    wires = brief.get("wires") or {}
    pool: List[Dict[str, Any]] = []
    for desk in wires.get("desks") or []:
        if desk.get("id") in _STORY_DESKS:
            pool.extend(desk.get("entries") or [])
    if not pool:
        return []
    return [
        {
            "title": row.get("title"),
            "url": row.get("url"),
            "source": row.get("source"),
            "published": row.get("published"),
            "tier": row.get("tier"),
            "tier_why": row.get("tier_why"),
            "age_words": row.get("age_words"),
            "catalysts": [c.get("type") for c in (row.get("catalysts") or [])],
        }
        for row in news_mod.rank_wire(pool, limit=3)
    ]


@app.get("/api/legal")
async def legal_notice() -> Dict[str, Any]:
    """The disclosures. Its own endpoint so a client consuming the JSON directly.
    Which is where the strike recommendations and the simulated ledger live — can
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
    Earnings and Investing tabs too, not just Options.
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
    calls per name to a thirty-name shortlist.

    Company fundamentals go for the same reason and were the larger miss: five
    fetches a ticker against earnings momentum's three, so 150 of the scan's
    480 requests were being spent on a block the ledger does not read."""
    return _swing_snapshot(ticker, None, 4, False, include_earnings=False,
                           include_company=False)


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
    # A manual scan too: it is its own task, and three hundred requests.
    _BACKGROUND_JOB.set(True)
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
        raise HTTPException(status_code=409, detail="A scan is already running. Watch its progress above.")

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
# So do the readers' watches. A pass is one snapshot per distinct symbol under
# watch, so the interval has to exceed the worst-case pass or the next one
# starts while the last is still running: sixty symbols at roughly twenty
# seconds each is about twenty minutes, and thirty leaves headroom. More
# frequent passes would mostly write nothing anyway, since a watch reports at
# most once a day.
WATCH_RUN_MINUTES = float(os.environ.get("WATCH_RUN_MINUTES", "30"))
WATCH_AUTO = os.environ.get("WATCH_AUTO", "true").strip().lower() != "false"
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
    _BACKGROUND_JOB.set(True)
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

            # Delete expired sessions, one-time tokens and rate-limit rows.
            # Above the market-hours gate on purpose: people sign in at the
            # weekend, and an expired session row that is never deleted is a row
            # standing one correct expiry check away from being a valid login.
            # Hourly — the rows are tiny and the work is a handful of indexed
            # DELETEs.
            last_sweep = getattr(app.state, "last_account_sweep", None)
            if last_sweep is None or now - last_sweep > 3600:
                try:
                    await _run(accounts_db.sweep)
                    app.state.last_account_sweep = now
                except Exception as exc:
                    log.warning("accounts sweep failed: %s", exc)

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

            # The readers' own watches, on the same clock.
            #
            # Without this the runner is a job nobody calls: /api/watches/run
            # exists and is tested, and the only thing that ever invoked it was
            # curl, so a watch could only fire if somebody happened to trigger
            # a pass by hand. The whole point of evaluating server-side is
            # being told about a move you were not watching.
            #
            # Inside the market-hours gate, deliberately. Every condition but
            # earnings_near reads a price or a technical, and both are the same
            # number all weekend, so a pass then spends provider calls to
            # re-read Friday's close. The cost of that choice is a
            # calendar-only condition landing up to a day late at a weekend,
            # which for a seven-day earnings window is not a miss.
            #
            # Its own interval rather than the mark cadence. A pass is one
            # snapshot per distinct symbol under watch at roughly twenty
            # seconds each, capped at sixty symbols, so the worst case is about
            # twenty minutes of provider calls: an interval shorter than that
            # would start the next pass while the last one was still running.
            # Thirty leaves headroom, and the once-per-day dedupe means more
            # frequent passes would mostly write nothing anyway.
            if is_open and WATCH_AUTO:
                last_watch = getattr(app.state, "last_watch_run", None)
                if last_watch is None or now - last_watch >= WATCH_RUN_MINUTES * 60:
                    app.state.last_watch_run = now
                    try:
                        out = await _run(watch_runner.run_once, _watch_snapshot)
                        if out["hits"] or out["failed_symbols"]:
                            log.info(
                                "watches: %s symbols, %s checked, %s fired, failed %s",
                                out["symbols"], out["watches_checked"],
                                out["hits"], out["failed_symbols"] or "none",
                            )
                    except Exception as exc:  # noqa: BLE001 - never break the loop
                        log.warning("watch run failed: %s", exc)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # a failed pass must not kill the loop
            log.warning("tracker loop pass failed: %s", exc)
        await asyncio.sleep(TRACKER_MARK_MINUTES * 60)


# The catalyst loop looks at the clock this often. It is not how often it scans
# (that is CATALYST_SCAN_HOURS, read against the store), so a look that finds
# nothing due costs two indexed reads.
CATALYST_CHECK_MINUTES = 15
# After the warm-up and the tracker's first pass, which are racing a visitor;
# this is racing nobody.
CATALYST_BOOT_DELAY = 90


async def _catalyst_loop() -> None:
    """Keep the catalyst library current whether or not anyone presses Scan.

    The button was the only way in, and on a host it needs the write token, so
    the live library held nothing at all and the local one was six weeks old.
    Its own task rather than a leg of `_tracker_loop`: a scan is one model call
    that can take a minute or more, and the tracker's marks should not wait on
    it, nor should TRACKER_AUTO=false switch the library off with it.
    """
    log = logging.getLogger("uvicorn.error")
    _BACKGROUND_JOB.set(True)
    await asyncio.sleep(CATALYST_BOOT_DELAY)
    while True:
        try:
            out = await _run(catalysts_mod.run_if_due)
            if out is not None and out.get("available"):
                log.info("catalyst scan: %s stories, %s catalysts (%s new), %s written",
                         out["scanned"], out["identified"], out["new"], out["written"])
            elif out is not None:
                log.warning("catalyst scan did not complete: %s", out.get("reason"))
        except asyncio.CancelledError:                          # noqa: PERF203
            raise
        except Exception as exc:                                # noqa: BLE001
            log.warning("catalyst scan pass failed: %s", exc)
        await asyncio.sleep(CATALYST_CHECK_MINUTES * 60)


# The data every first load shares, kept fresh while anyone is reading.
#
# The macro basket and the sector funds' board are one download each, cached
# for five minutes, and whichever reader's load found them expired paid for the
# refetch: the macro leg was 3.0s to 3.2s of loads that were otherwise 1.5s on
# the live site (ROST, TTWO, 2026-09-28), and the FRED calendar 3.2s of
# another. Once warm they cost 0.07s, 0.001s and 0.006s. So a loop refetches
# them in the jobs' lane before they expire (yf.refreshing_early): once at
# boot, so the first reader after a deploy finds them ready, and after that
# only while someone has loaded a symbol in the last KEEP_WARM_IDLE seconds,
# because refetching baskets nobody is reading would be traffic for nothing.
KEEP_WARM_SECONDS = 60
KEEP_WARM_IDLE = 15 * 60
KEEP_WARM_BOOT_DELAY = 5
_KEEP_WARM: Dict[str, float] = {"read_at": 0.0}


def _warm_shared() -> None:
    """The ticker build's shared legs, each refetched if near its expiry."""
    log = logging.getLogger("uvicorn.error")
    with yf_provider_mod.refreshing_early():
        for name, fn in (("macro", lambda: macro_mod.analyse(YF_PROVIDER)),
                         ("sector board", lambda: sector_board_mod.build(YF_PROVIDER)),
                         ("SPY", lambda: YF_PROVIDER.history("SPY", period="6mo", interval="1d")),
                         ("calendar", _macro_calendar_rows)):
            try:
                fn()
            except Exception as exc:                            # noqa: BLE001
                log.info("keep-warm %s skipped: %s", name, exc)


async def _keep_warm_loop() -> None:
    _BACKGROUND_JOB.set(True)
    await asyncio.sleep(KEEP_WARM_BOOT_DELAY)
    first = True
    while True:
        try:
            if first or time.time() - _KEEP_WARM["read_at"] < KEEP_WARM_IDLE:
                await _run(_warm_shared)
            first = False
        except asyncio.CancelledError:                          # noqa: PERF203
            raise
        except Exception as exc:                                # noqa: BLE001
            logging.getLogger("uvicorn.error").info("keep-warm pass failed: %s", exc)
        await asyncio.sleep(KEEP_WARM_SECONDS)


async def _warm_home() -> None:
    """Build the landing page's two slow payloads at boot, so no reader does.

    /api/home is six legs and three of them reach the network. Measured on the
    live server: 7.35s on the first request after a restart, 0.6s on every one
    after it. This platform restarts on every deploy, so without this the first
    person to open the site after a deploy pays the entire cold cost -- and the
    landing page is the most requested endpoint in the app, so that person is
    also the most likely one to exist.

    Two seconds of delay first, for the reason `_tracker_loop` waits thirty:
    let the server finish binding before it starts pulling on the network. Two
    rather than thirty because this one is racing an actual visitor.

    Failures are swallowed and logged at info. This is a head start, not a
    dependency: every leg already reports its own absence when a reader asks
    for real, and a warm-up that raised would take the process down with it.
    """
    log = logging.getLogger("uvicorn.error")
    # In the jobs' lane, all of it. Only the board's earnings scan was, and the
    # homepage build ahead of it spent a reader's allowance at boot: a cold
    # load a second after another, twelve seconds after a restart, was held
    # at the limiter for up to 3.9s (STX, 2026-09-28). A reader who opens the
    # homepage meanwhile fetches what is missing at a reader's priority.
    _BACKGROUND_JOB.set(True)
    try:
        await asyncio.sleep(2)
        await home_summary()
        log.info("home payload warmed")
        # The board as well: it is on the same first screen and its earnings
        # leg is 66s cold. Built after the home payload rather than beside
        # it, because both pull on the same provider and racing them at boot
        # would just make the first reader wait for a busier thread pool.
        await priority_board()
        log.info("priority board warmed")
    except asyncio.CancelledError:                              # noqa: PERF203
        raise
    except Exception as exc:                                    # noqa: BLE001
        log.info("warm-up skipped: %s", exc)


async def _flush_feedback() -> None:
    """Send the problem reports that were filed before there was an address.

    A report is stored first and emailed second, and the email is allowed to
    fail, so any window where FEEDBACK_EMAIL_TO or the SMTP settings were
    missing leaves a backlog that nothing retries: `submit` only ever sends the
    report in its own hand. Boot is the natural moment to clear it, because
    setting those variables on this platform *is* a restart -- the backlog goes
    out as a consequence of configuring the thing that was missing, rather than
    waiting for someone to remember a maintenance call.

    Thirty seconds first, for the reason `_tracker_loop` waits: let the server
    bind and let `_warm_home` have the thread pool, since that one is racing an
    actual visitor and this one is racing nobody. These reports have waited
    considerably longer than thirty seconds already.

    Off the event loop because `flush` opens SMTP connections, and it stops on
    its own first failure, so a relay that is down costs one connection attempt
    rather than two hundred. Swallowed and logged like the warm-up: mail that
    cannot go out must not take the terminal down with it.
    """
    log = logging.getLogger("uvicorn.error")
    try:
        await asyncio.sleep(30)
        # Checked before the sleep would have been wrong and before the call is
        # only a saving: unconfigured is the normal state here and `flush` would
        # otherwise count the backlog on every boot to report a number nobody
        # reads. Configured is the rare case, so pay the query there.
        if not feedback_mod.configured().get("available"):
            return
        out = await _run(feedback_mod.flush)
        if out.get("sent"):
            log.info("feedback backlog: %d sent, %d still pending",
                     out["sent"], out.get("pending", 0))
        elif out.get("pending"):
            log.warning("feedback backlog: %d report(s) could not be sent",
                        out["pending"])
    except asyncio.CancelledError:                              # noqa: PERF203
        raise
    except Exception as exc:                                    # noqa: BLE001
        log.info("feedback flush skipped: %s", exc)


@app.on_event("startup")
async def _start_tracker() -> None:
    paper.init_db()
    # Held on the app so the reference isn't garbage-collected mid-flight --
    # asyncio keeps only a weak reference to a bare create_task.
    app.state.warm_task = asyncio.create_task(_warm_home())
    app.state.feedback_task = asyncio.create_task(_flush_feedback())
    app.state.catalyst_task = asyncio.create_task(_catalyst_loop())
    app.state.keepwarm_task = asyncio.create_task(_keep_warm_loop())
    if TRACKER_AUTO:
        # Held on the app so the reference isn't garbage-collected mid-flight.
        app.state.tracker_task = asyncio.create_task(_tracker_loop())


@app.on_event("shutdown")
async def _stop_tracker() -> None:
    # All five. A warm-up still sleeping when the server is told to stop would
    # otherwise keep the loop alive for its remaining two seconds and log a
    # "task was destroyed but it is pending" on the way out, and the feedback
    # flush sleeps fifteen times longer than that.
    for name in ("tracker_task", "warm_task", "feedback_task", "catalyst_task",
                 "keepwarm_task"):
        task = getattr(app.state, name, None)
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
# The intraday ladder, keyed by the bar size in minutes.
#
# Every pair here was probed against the live feed on AAPL before being
# offered, because an interval the provider silently refuses renders as "no
# intraday bars" and reads as a broken symbol rather than an unsupported
# timeframe. Bars returned, and the gap between consecutive stamps matched the
# interval in each case -- including 4h, which is not in yfinance's documented
# list and does come back as genuine four-hour buckets: 43 bars over a month
# at exactly 04:00:00 spacing, two per session at 09:30 and 13:30.
#
# The period attached to each is a default window rather than the provider's
# maximum. It is chosen to land between roughly 250 and 550 bars, which is a
# readable chart: 1m over its full 7-day allowance is 2,464 bars, and at that
# density a candle is a hairline. The maxima the feed enforces are wider --
# 7d for 1m, 60d for 5m through 30m, 730d for 60m -- and are what would cap a
# zoom, not what is fetched up front.
# Keyed in minutes, not `1m`/`4h`. `1m` is already a chart RANGE key meaning
# one month on the client, and both lists are looked up by the same string:
# the 1M range pill would have loaded a one-minute chart. See CHART_INTERVALS.
INTRADAY_SPECS = {
    # `windows` are the lookbacks each size offers, as 1D offers 1M to All.
    # Measured on PLTR: the feed serves up to 7 days of 1m bars, 60 days at 5m
    # to 30m and two years at 1h and 4h. Capped nearer 2,000 bars than the
    # feed's limit (5m over 60 days is 4,680), because every one is drawn and
    # redrawn on each zoom step.
    "1": {"period": "1d", "interval": "1m", "windows": ["1d", "5d"]},
    "5": {"period": "5d", "interval": "5m", "windows": ["1d", "5d", "1mo"]},
    "15": {"period": "1mo", "interval": "15m", "windows": ["5d", "1mo", "60d"]},
    "30": {"period": "1mo", "interval": "30m", "windows": ["5d", "1mo", "60d"]},
    "60": {"period": "3mo", "interval": "60m", "windows": ["1mo", "3mo", "6mo", "1y"]},
    "240": {"period": "1y", "interval": "4h", "windows": ["3mo", "6mo", "1y", "2y"]},
    # The two keys the range pills used before the ladder existed. Kept as
    # aliases: a client holding a stored preference or a page mid-session still
    # asks for these, and answering them costs two entries.
    "1d": {"period": "1d", "interval": "5m"},
    "5d": {"period": "5d", "interval": "15m"},
}


def intraday_spec(key: str, window: str = "") -> Optional[Dict[str, Any]]:
    """The spec for an intraday size, with its window if it is one of the
    size's own; None for an unknown size or a window it does not offer. One
    function for the bars, the studies and the trend lines, so the three are
    always computed on the same frame."""
    spec = INTRADAY_SPECS.get((key or "").lower())
    if not spec:
        return None
    win = (window or "").lower()
    if not win or win == spec["period"]:
        return spec
    if win not in spec.get("windows", ()):
        return None
    return {**spec, "period": win}


@app.get("/api/intraday/{ticker}")
async def intraday(ticker: str, range: str = Query("1d"),
                   window: str = Query("", description="One of the size's windows")) -> Dict[str, Any]:
    """Intraday bars for the short-range chart pills.

    Separate from /api/ticker deliberately. That payload is daily bars and the
    whole analysis built on them; intraday is only wanted when the reader picks
    1D or 5D, and fetching it on every ticker load would be a request per view
    that most readers never look at.

    Regular session only. Pre- and post-market prints come from thin books, and
    splicing them into the same line as regular-hours trade draws gaps and
    spikes that look like price action and are not.
    """
    spec = intraday_spec(range, window)
    if not spec:
        known = INTRADAY_SPECS.get((range or "").lower())
        if known:
            return {"available": False,
                    "reason": "{} bars are offered over {}, not {!r}.".format(
                        known["interval"], ", ".join(known.get("windows") or [known["period"]]),
                        window)}
        return {"available": False,
                "reason": "Unknown range {!r}. Expected one of: {}.".format(
                    range, ", ".join(sorted(INTRADAY_SPECS)))}

    def build() -> Dict[str, Any]:
        symbol = ticker.upper().strip()
        frame = YF_PROVIDER.intraday_history(
            symbol, period=spec["period"], interval=spec["interval"])
        if frame is None or frame.empty:
            return {"available": False, "ticker": symbol, "range": range,
                    "reason": ("No intraday bars came back. Free intraday history is "
                               "thin outside regular hours and absent for many symbols.")}

        # Open, high and low beside the close. This sent closes only, so every
        # rung under a day could draw nothing but a line and the Candles button
        # was disabled on all eight of them. The feed has always carried all
        # four: measured on PLTR, every rung from 1m to 4h came back with no
        # missing open, high or low and no bar whose high sat under its body.
        # A missing value is sent as null rather than guessed, and the chart
        # leaves that one candle out.
        opens, highs, lows, closes, times, volumes = [], [], [], [], [], []

        def _price(value):
            return None if value is None or value != value else round(float(value), 4)

        for stamp, row in frame.iterrows():
            close = row.get("Close")
            if close is None or close != close:
                continue
            closes.append(round(float(close), 4))
            opens.append(_price(row.get("Open")))
            highs.append(_price(row.get("High")))
            lows.append(_price(row.get("Low")))
            times.append(stamp.isoformat())
            vol = row.get("Volume")
            volumes.append(None if vol is None or vol != vol else float(vol))

        if not closes:
            return {"available": False, "ticker": symbol, "range": range,
                    "reason": "Intraday bars came back with no usable closes."}

        # Fibonacci from these bars, not the daily ones. The daily grid is
        # anchored to a swing across months, which sits off the edge of a chart
        # of one session, so the Fibs button drew nothing on any rung under a
        # day. Same two functions as the daily grid, over the whole window the
        # chart shows, so the levels hang off the high and low on screen. The
        # leg runs from the earlier extreme to the later one: a high after the
        # low is an up leg, whose retracements sit under price as support.
        # That is the rule find_swing_points' own docstring states; the daily
        # grid takes its direction from the composite bias instead, which is
        # not computed on intraday bars.
        swing_rows = frame.dropna(subset=["High", "Low", "Close"])
        fib: Dict[str, Any] = {}
        if len(swing_rows) >= 2:
            swing = technicals.find_swing_points(swing_rows, lookback=len(swing_rows))
            if swing:
                fib = technicals.fib_levels(
                    swing, "bullish" if swing.get("high_is_recent") else "bearish",
                    closes[-1])

        # Support and resistance, the band width, and supply and demand, from
        # these bars as the daily payload has them from daily ones: the same
        # three functions. Every one was switched off under a day because the
        # only copies were daily, and a daily shelf months away is off the edge
        # of a session's chart. Measured on PLTR at every rung: 1-3ms for the
        # levels, about 10ms for the zones, so they come with the bars rather
        # than needing a request of their own. Trend lines take 30-280ms and are
        # fetched on demand, as they are on daily bars.
        levels: List[Dict[str, Any]] = []
        atr14 = None
        zones: Dict[str, Any] = {}
        if len(swing_rows) >= 30:
            try:
                levels = technicals.support_resistance_levels(swing_rows, closes[-1]) or []
                atr_v = technicals.atr(swing_rows).iloc[-1]
                atr14 = round(float(atr_v), 4) if atr_v == atr_v else None
                zones = patterns_mod.analyse(swing_rows, spot=closes[-1]) or {}
            except Exception as exc:                          # noqa: BLE001
                # Optional overlays on bars that are already here: a failure
                # costs the levels, never the chart.
                logging.getLogger("uvicorn.error").info(
                    "intraday levels for %s failed: %s", symbol, exc)

        # The reference for a percentage change is the first bar of the window,
        # not the previous daily close — the chart shows this window, so the
        # number under it has to describe the same thing.
        first, last = closes[0], closes[-1]
        return {
            "available": True,
            "ticker": symbol,
            "range": range,
            "interval": spec["interval"],
            "window": spec["period"],
            "times": times,
            "opens": opens,
            "highs": highs,
            "lows": lows,
            "closes": closes,
            "volumes": volumes,
            "fibonacci": fib,
            "support_resistance": levels,
            "atr14": atr14,
            "patterns": zones,
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
        # write_sector_read now explains its own failures, so this no longer has
        # to guess between "not configured" and a shrug. The old branch here
        # could only tell those two apart and reported everything else as "could
        # not be written on this attempt", which hid the usual cause: the
        # account being out of credit, which is both actionable and already
        # spelled out by ai._human_error.
        if not read or read.get("available") is not True:
            return {"available": False, "symbol": sym,
                    "summary": (facts.get("row") or {}).get("summary"),
                    "reason": ((read or {}).get("reason")
                               or "The read could not be written on this attempt.")}
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
        # On a copy that cannot write it, the live site's, which is the same
        # update every reader gets. `force` only skips this copy's cache: it is
        # never passed on, so nobody here can make the live site write again.
        key = weekly_mod.week_key()
        if live_mirror.active():
            got = live_mirror.fetch("/api/weekly", fresh=force)
            if got is not None:
                return got
            # Unreachable, and this copy cannot write one either: say both,
            # rather than attempt a write that is certain to be refused.
            if not ai.key_usable():
                return {"available": False, "week_key": key,
                        "mirror_failed": {"from": live_mirror.LIVE_URL},
                        "reason": ("The live site's weekly update could not be fetched, "
                                   "and this copy's Anthropic key cannot write one. "
                                   "It is fetched again on the next load.")}
        if force:
            ai._WEEKLY_CACHE.pop(key, None)
        facts = weekly_mod.gather(YF_PROVIDER)
        update = ai.write_weekly_update(key, facts)
        # See the earnings brief above: a failure is now a truthy dict.
        if not update or update.get("available") is not True:
            return {"available": False, "week_key": key,
                    "reason": ("The assistant is not configured, so there is no weekly "
                               "update."
                               if ai.available().get("enabled") is not True else
                               (update or {}).get("reason")
                               or "The weekly update could not be written on this attempt.")}
        update["facts"] = {
            "earnings": facts.get("earnings"),
            "spy": facts.get("spy"),
            "sectors": facts.get("sectors"),
        }
        update["generated_at"] = datetime.now(timezone.utc).isoformat()
        return update
    return await _run(build)


_ISO_DAY = r"^\d{4}-\d{2}-\d{2}$"


@app.get("/api/congress")
async def congress_trades(
    ticker: Optional[str] = Query(None, description="Filter to one symbol"),
    limit: int = Query(60, ge=1, le=300),
    member: Optional[str] = Query(
        None, max_length=80,
        description="Case-insensitive substring of the filer's name"),
    side: Optional[str] = Query(
        None, pattern="^(buy|sell|other)$",
        description="buy, sell, or other (exchanges and similar)"),
    since: Optional[str] = Query(None, pattern=_ISO_DAY,
                                 description="Earliest trade date, YYYY-MM-DD"),
    until: Optional[str] = Query(None, pattern=_ISO_DAY,
                                 description="Latest trade date, YYYY-MM-DD"),
    activity_days: int = Query(30, ge=1, le=180,
                               description="Width of the per-day activity series"),
) -> Dict[str, Any]:
    """Stock trades disclosed by members of the House under the STOCK Act.

    Free and public: the Clerk of the House publishes both the index and the
    filings, so there is no key here and no vendor in the path.

    The refresh is bounded and lazy. 400 filings a year is a backlog to fill
    over successive calls rather than a burst to fire at a government file
    server, so a stale read pulls the index plus a budget of new filings and
    answers with whatever is parsed -- `filings_parsed` against
    `filings_known` says how much of the record that is.
    """
    if congress_mod.stale():
        await _run(congress_mod.refresh)
    # Filtering happens here, not in the browser. The archive is thousands of
    # rows and the page shows sixty, so a client filter would mean shipping
    # everything in order to narrow it -- and the counts, the per-day series
    # and the ranking all have to describe the filtered set, which means
    # whatever computes them has to see all of it.
    return congress_mod.summary(
        ticker=ticker, limit=limit, member=member, side=side,
        since=since, until=until, activity_days=activity_days)


@app.get("/api/catalysts")
async def catalyst_library(
    q: str = Query("", description="Free-text search"),
    status: str = Query("relevant"),
    category: str = Query(""),
    sector: str = Query(""),
    theme: str = Query(""),
    limit: int = Query(60, ge=1, le=200),
    fresh: bool = Query(False, description="Skip this copy's cache of the live library"),
) -> Dict[str, Any]:
    """Search the stored catalyst library. Reads only — never generates.

    A local copy that cannot write its own (see live_mirror) answers with the
    live site's library, and says so. If the live site cannot be reached it
    falls back to its own store, and says that too.
    """
    def build() -> Dict[str, Any]:
        mirroring = live_mirror.active()
        if mirroring:
            got = live_mirror.fetch("/api/catalysts", {
                "q": q, "status": status, "category": category, "sector": sector,
                "theme": theme, "limit": limit}, fresh=fresh)
            if got is not None:
                return got
        out = catalysts_mod.search(query=q, status=status, category=category,
                                   sector=sector, theme=theme, limit=limit)
        if mirroring:
            out["mirror_failed"] = {"from": live_mirror.LIVE_URL}
        return out
    return await _run(build)


@app.post("/api/catalysts/refresh")
async def catalyst_refresh(request: Request,
                           hours: int = Query(168, ge=24, le=720)) -> Dict[str, Any]:
    """Scan recent stories for new catalysts.

    A POST and a separate endpoint from the search above, deliberately: this one
    spends money and writes to the store, and neither of those should happen
    because somebody opened a tab. The library does not wait on it: the
    catalyst loop below scans on a schedule whether or not anyone presses this.
    """
    _write_guard(request)
    # A copy showing the live library has nothing to scan with, and its own
    # store is not what the page shows. The button is not drawn in that case;
    # this is for a page that was open before the key stopped working.
    if live_mirror.active():
        return {"available": False, "mirror": {"from": live_mirror.LIVE_URL},
                "reason": live_mirror.why() + " The live library rescans itself "
                          "on its own schedule."}

    def build() -> Dict[str, Any]:
        out = catalysts_mod.refresh(hours=hours, trigger="manual")
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


# The board, and when it was built. Same shape as _EW_CACHE below, for the same
# reason and on the same evidence.
_PRIORITY_CACHE: Dict[str, Any] = {}
PRIORITY_TTL = 600.0


@app.get("/api/priority")
async def priority_board() -> Dict[str, Any]:
    """Today's four-column triage board.

    Cached for ten minutes, because one of its four legs is an earnings scan.
    Timed cold, per leg: earnings 66.6s, events 3.9s, sectors 0.8s, movers
    0.01s -- and 0.02s for the whole build once the provider caches are warm.
    `_earnings` calls the same weekly scan `/api/earnings-week` does, and that
    endpoint's docstring already says it is "~150 provider calls and takes tens
    of seconds cold, which is far too slow for a tab a reader opens casually".
    This board is not a tab a reader opens casually -- it is on the landing
    page, above the fold. Measured on the live server before this: 42s.

    Ten minutes rather than the hour `/api/earnings-week` uses. The earnings
    and events legs move on the scale of days and would tolerate far more, but
    the sector column reads current price against the prior session's high and
    low, and that is the leg a reader could catch being wrong. It costs 0.8s to
    rebuild, so ten minutes is the price of not making anyone wait for the
    other 70.
    """
    def build() -> Dict[str, Any]:
        hit = _PRIORITY_CACHE.get("board")
        if hit and (time.time() - hit["at"]) < PRIORITY_TTL:
            return hit["data"]
        # In the jobs' lane whoever asked, a reader or the warm-up after a
        # deploy: its earnings leg is about a hundred and fifty requests, and a
        # reader loading a symbol meanwhile should not queue behind them.
        with yf_provider_mod.background():
            out = priority_mod.build(YF_PROVIDER, scanners_mod, _cached_ranking())
        _PRIORITY_CACHE["board"] = {"at": time.time(), "data": out}
        return out
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
        with yf_provider_mod.background():                # the same scan
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
        # The read across the comparison. The tab's own subtitle said the
        # disagreement between horizons "is the useful part" and then left the
        # reader to find it by eye across twenty-six rows.
        out["take"] = compare_mod.take(out)
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


@app.get("/api/weekly-bars/{ticker}")
async def weekly_bars(ticker: str) -> Dict[str, Any]:
    """Ten years of weekly bars for the charts' 1W size.

    `/api/weekly-bars`, not `/api/weekly/{ticker}`: `/api/weekly` is the Weekly
    update panel, and a client function named after it collided with that
    panel's own loadWeekly -- the later declaration silently won.

    The weekly chart was rolled up from the two years of daily bars the ticker
    payload carries: 105 weeks, so a 200-week average -- on the 1D chart as a
    200-day one -- could never draw on 1W, and its key said it needed 200 bars.
    Ten years is about 520 weeks. Labelled by each week's Monday, as the feed
    labels them, which is also what makes a mid-week trade snap to its own week
    rather than the one before.
    """
    sym = ticker.strip().upper()

    def build() -> Dict[str, Any]:
        df = YF_PROVIDER.history(sym, period="10y", interval="1wk")
        if df is None or df.empty:
            return {"available": False, "ticker": sym,
                    "reason": "No weekly history for {}.".format(sym)}
        df = df.dropna(subset=["Close"])

        def col(name, digits=4):
            if name not in df:
                return None
            return [None if v != v else round(float(v), digits) for v in df[name]]
        return {
            "available": True,
            "ticker": sym,
            "dates": [str(i.date()) for i in df.index],
            "open": col("Open"), "high": col("High"), "low": col("Low"),
            "close": col("Close"), "volume": col("Volume", 0),
            "bars": int(len(df)),
        }
    return await _run(build)


@app.get("/api/trendlines/{ticker}")
async def trendlines_panel(ticker: str,
                           period: str = Query("1y"),
                           intraday: str = Query("", description="An /api/intraday range key"),
                           window: str = Query("", description="That size's window")) -> Dict[str, Any]:
    """Trend lines fitted to pivots, and whether price has broken one.

    `intraday` fits them to that rung's bars instead of a year of daily ones,
    with times rather than dates, so the chart can anchor each line on the bar
    it was fitted to. Off under a day until now, which left Auto trend lines a
    switch that drew nothing on every size below 1D."""
    sym = ticker.strip().upper()
    spec = intraday_spec(intraday, window) if intraday else None
    if intraday and not spec:
        return {"available": False,
                "reason": "Unknown intraday range {!r}.".format(intraday)}

    def build() -> Dict[str, Any]:
        if spec:
            df = YF_PROVIDER.intraday_history(sym, period=spec["period"],
                                              interval=spec["interval"])
        else:
            df = YF_PROVIDER.history(sym, period=period, interval="1d")
        out = trendlines_mod.build(df)
        out["ticker"] = sym
        out["period"] = spec["period"] if spec else period
        if spec:
            out["intraday"] = intraday
            out["dates"] = [i.isoformat() for i in df.index] if df is not None and len(df) else []
        else:
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
async def stockmap(template: str = Query("sector-month", max_length=40),
                   sector: Optional[str] = Query(None, max_length=8)) -> Dict[str, Any]:
    """A screen laid out as a treemap or a bubble chart.

    `sector` drills into one fund's largest holdings, which is what clicking a
    sector tile asks for. The template is unchanged by the drill, so whatever
    was being measured stays measured one level down.
    """
    def build() -> Dict[str, Any]:
        out = stockmaps_mod.build(YF_PROVIDER, template, sector=sector)
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


# Keyed on the status `_write_guard` chose, so the rule stays that function's
# and only the wording is this route's.
_READ_GUARD_COPY = {
    401: "These are other people's problem reports, so reading them needs the "
         "write token. Every research panel stays open to everyone.",
    403: "That request did not look like it came from this page. The write "
         "token in a header works from anywhere; a browser session needs the "
         "page to send its CSRF header.",
    503: "Problem reports are readable by the operator, and this deployment "
         "has no OPTIC_WRITE_TOKEN set to tell who that is. Set one in the "
         "platform's variables. The reports themselves are safe: they are "
         "stored either way.",
}


def _feedback_cors(request: Request) -> Dict[str, str]:
    """CORS headers for /api/feedback, which is posted to from other origins.

    The client sends a problem report to theopticterminal.com from whatever
    build it happens to be served by, so anywhere but production this is a
    cross-origin POST, and the JSON content type makes it a preflighted one.
    No credentials: the report carries no cookie and no session, so there is
    nothing here for a forged request to ride on and nothing to widen by
    allowing it. `feedback_mod.cors_origin` is the allow-list.

    `Vary: Origin` whatever the outcome. The body is identical for every origin
    but this header is not, and a cache that missed that would hand one origin
    a decision that was made about another.
    """
    headers = {"Vary": "Origin"}
    allowed = feedback_mod.cors_origin(request.headers.get("origin") or "")
    if allowed:
        headers["Access-Control-Allow-Origin"] = allowed
    return headers


@app.options("/api/feedback")
async def feedback_preflight(request: Request) -> Response:
    """The preflight the POST below needs. Without it OPTIONS 405s and no
    cross-origin report is ever sent, because the browser never gets as far as
    the POST. An origin outside the allow-list gets the same 204 without an
    allow header, which the browser reads as a refusal."""
    cors = _feedback_cors(request)
    if "Access-Control-Allow-Origin" in cors:
        cors["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        cors["Access-Control-Allow-Headers"] = "Content-Type"
        # A day. The preflight is pure policy and the policy is a constant.
        cors["Access-Control-Max-Age"] = "86400"
    return Response(status_code=204, headers=cors)


@app.post("/api/feedback")
async def submit_feedback(request: Request,
                          payload: Dict[str, Any] = Body(default={})) -> Response:
    """One reader-reported problem.

    No `_write_guard`. That guard protects the terminal's own state, and this
    writes nothing a reader can read back: it appends to a table only the
    operator sees. Requiring the write token would put the report button behind
    a credential and leave it doing nothing for every actual reader, which is
    the failure this endpoint exists to fix.

    Rate limited by address instead, and the send runs off the event loop
    because it opens an SMTP connection.

    Rendered through JSONResponse rather than returned as a dict so the CORS
    headers survive the error paths. An HTTPException is rendered by Starlette's
    own handler, which never sees this route's response object, so a raised 400
    or 429 would reach a cross-origin caller stripped of its allow header. The
    browser would then report an opaque CORS failure and the reader would be
    told the report did not send instead of being told why.
    """
    cors = _feedback_cors(request)
    try:
        auth_ratelimit.guard(request, "feedback", auth_ratelimit.client_ip(request))
        message = payload.get("message")
        if not isinstance(message, str) or not message.strip():
            raise HTTPException(status_code=400, detail="A report needs a message.")

        page = payload.get("page") if isinstance(payload.get("page"), str) else ""
        reply = payload.get("reply_to") if isinstance(payload.get("reply_to"), str) else ""
        # Taken from the request, not from the body: a client-supplied
        # User-Agent is just another string the reporter typed.
        agent = request.headers.get("user-agent") or ""

        out = await _run(feedback_mod.submit, message, page, reply, agent)
        auth_ratelimit.record("feedback", auth_ratelimit.client_ip(request))
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code,
                            content={"detail": exc.detail}, headers=cors)
    return JSONResponse(content=out, headers=cors)


@app.get("/api/feedback")
async def read_feedback(request: Request,
                        limit: int = Query(50, ge=1, le=200)) -> Dict[str, Any]:
    """The reports, for whoever owns the deployment.

    `_write_guard` on a read. The guard's real subject is "is this the
    operator", and a second gate meaning the same thing is a second gate to
    keep in step. What it protects is other people's words: a reader filing a
    problem is writing to the operator, not to the web.

    The write token is the route that always works here. The guard's admin
    branch pairs with `csrf_guard`, and a URL typed into an address bar carries
    no CSRF header, so a signed-in owner visiting this directly gets a 403 that
    is about the cookie rather than about them.
    """
    try:
        _write_guard(request)
    except HTTPException as exc:
        # Every refusal that guard writes is phrased about changing the ledger,
        # because until this route existed every caller it turned away was
        # trying to. A reader who asked for the reports and is told "writes are
        # disabled... it refuses to let anonymous callers change the ledger"
        # goes looking for a write they never made. Same rule, same status,
        # true sentence.
        raise HTTPException(status_code=exc.status_code,
                            detail=_READ_GUARD_COPY.get(exc.status_code, exc.detail))
    return await _run(feedback_mod.log, limit)


@app.get("/api/econ")
async def econ_catalogue() -> Dict[str, Any]:
    """The economic series available to plot, grouped. No fetch."""
    return econ_mod.catalogue()


@app.get("/api/econ/{code}")
async def econ_series(code: str, years: int = Query(12, ge=1, le=60)) -> Dict[str, Any]:
    """One FRED series, transformed into the form it is actually read in."""
    return await _run(econ_mod.series, code.strip().upper(), years)


@app.get("/api/relperf/{ticker}")
async def relative_performance(ticker: str,
                               fast: str = Query("1m", max_length=4),
                               slow: str = Query("3m", max_length=4)) -> Dict[str, Any]:
    """Where this symbol's return ranks against its peers, over two windows.

    Distinct from /api/extras' relative performance, which is a ratio line
    against one benchmark. This is a percentile against a peer set: it answers
    "how many of them is it beating" rather than "is it beating SPY".
    """
    return await _run(relperf_mod.analyse, YF_PROVIDER, ticker, fast, slow)


@app.get("/api/relperf-scan/{kind}")
async def relative_performance_scan(kind: str,
                                    limit: int = Query(20, ge=1, le=100)) -> Dict[str, Any]:
    """leaders (rank >= 95), laggards (<= 5), cross_up (through 80),
    cross_down (through 20)."""
    allowed = {"leaders", "laggards", "cross_up", "cross_down"}
    if kind not in allowed:
        raise HTTPException(status_code=400,
                            detail="kind must be one of: " + ", ".join(sorted(allowed)))
    return await _run(relperf_mod.scan, YF_PROVIDER, kind, limit)


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


@app.get("/api/stage")
async def stage_reading(
    symbol: str = Query(..., description="Provider symbol, e.g. PLTR or ^GSPC"),
) -> Dict[str, Any]:
    """Weinstein stage for one symbol, from two years of weekly closes.

    Its own endpoint rather than a field on each chart payload, because the
    stage belongs to the instrument and not to the range on screen: a 3-month
    chart holds about thirteen weeks, far short of a 30-week average, so it
    fetches its own history whatever the chart shows. A query parameter for the
    reason `/api/instrument` gives: `^GSPC` and `ES=F` do not survive a path.

    Always YF_PROVIDER, for the same reason as the instrument chart: it is the
    one feed that carries indices, futures and crypto as well as stocks.
    """
    return await _run(stage_mod.for_symbol, YF_PROVIDER, symbol)


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
        # Same quote reconciliation the strip applies, and for the same reason
        # twice over: the figure is wrong on a futures row without it, and a
        # drill-down that recomputed it from the bars would disagree with the
        # row the reader clicked to get here.
        snap = series_stats_mod.apply_quote(
            macro_mod.snapshot(frame, meta.get("label") or sym),
            series_stats_mod.live_quotes(YF_PROVIDER, [sym]).get(sym))
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
    intraday: str = Query("", description="An /api/intraday range key, e.g. 5 or 60"),
    window: str = Query("", description="That size's window, as /api/intraday takes it"),
    weekly: bool = Query(False, description="Compute on weekly bars"),
) -> Dict[str, Any]:
    """Optional indicators, computed only for the ids asked for.

    A catalogue endpoint rather than more fields on the ticker payload: nine
    indicators on every request would be work nobody asked for on most page loads,
    and the reader picks these deliberately.

    **`intraday` computes them on the chart's own intraday bars.** Every study
    was switched off under a day, because these were daily bars and the chart
    lines them up with its own bars by counting back from the newest: a daily
    Bollinger band drawn over five-minute candles would put last March on this
    morning. Same frame /api/intraday draws, so the lines are bar for bar with
    the candles. Its own parameter rather than a value of `range`, because
    "1d" and "5d" are both a daily period and an intraday key.

    VWAP is anchored at the first bar of the window there: a date anchor
    compared against a timezone-aware minute index raises, and the window's
    first bar is what the chart shows. The one-line readings are dropped, as
    they are written in sessions and a bar is not one.
    """
    def build() -> Dict[str, Any]:
        sym = ticker.upper().strip()
        wanted = [i for i in (ids or "").replace(" ", "").split(",") if i]
        spec = intraday_spec(intraday, window) if intraday else None
        if intraday and not spec:
            return {"available": False,
                    "reason": "Unknown intraday range {!r}. Expected one of: {}.".format(
                        intraday, ", ".join(sorted(INTRADAY_SPECS)))}

        def frame_for(symbol: str):
            if spec:
                return YF_PROVIDER.intraday_history(
                    symbol, period=spec["period"], interval=spec["interval"])
            source = PROVIDER if symbol == sym else YF_PROVIDER
            # Weekly bars for a weekly chart. Daily studies were drawn over it,
            # lined up from the newest bar, so a 1W chart of two years carried
            # the last five months of a daily Bollinger band stretched across it.
            return source.history(symbol, period=range_,
                                  interval="1wk" if weekly else "1d")

        hist = frame_for(sym)
        if hist is None or hist.empty:
            if spec:
                return {"available": False, "ticker": sym,
                        "reason": "No intraday bars came back for {}.".format(sym)}
            raise HTTPException(status_code=404,
                                detail="No price data found for '{}'.".format(sym))
        bench = None
        if "rs" in wanted:
            frame = frame_for("SPY")
            if frame is not None and not frame.empty:
                bench = frame["Close"].astype(float)
        out = indicators_mod.compute(hist, wanted, bench=bench,
                                     anchor=None if spec else (anchor or None))
        if spec and out.get("available") is not False:
            # Times, not dates: the chart's x-axis is minutes here.
            out["dates"] = [ts.isoformat() for ts in hist.index]
            for result in (out.get("indicators") or {}).values():
                result.pop("reading", None)
            out["intraday"] = intraday
            out["interval"] = spec["interval"]
        elif weekly:
            out["interval"] = "1wk"
        out["ticker"] = sym
        out["generated_at"] = datetime.now(timezone.utc).isoformat()
        return out
    return await _run(build)


@app.get("/api/patterns/base-rates")
async def pattern_base_rates(force: bool = Query(False)) -> Dict[str, Any]:
    """Measured base rates for each pattern.

    Cached on disk for a month. The full build walks 43 names over ten years of
    daily bars detecting candles bar by bar, which takes about ninety seconds.
    Far too slow to sit in a page load, and the numbers move so slowly that a
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
        return {"groups": scanners_mod.groups() + [dict(
        relperf_mod.SCAN_GROUP,
        count=len(relperf_mod.SCAN_DEFS),
        scans=[{"id": d["id"], "name": d["name"], "looks_for": d["looks_for"]}
               for d in relperf_mod.SCAN_DEFS],
    )],
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


@app.get("/api/segments/{ticker}")
async def segments_panel(ticker: str,
                         force: bool = Query(False)) -> Dict[str, Any]:
    """Revenue and operating income by segment, product and geography.

    Read from each filing's XBRL instance document, because SEC's companyfacts
    API is consolidated only and carries no dimensions at all. Parsing is capped
    per call and cached per accession, so a cold panel reports what it has not
    read rather than holding the page. See app/analytics/segments.py.
    """
    return await _run(segments_mod.build, ticker, force)


@app.get("/api/insiders/latest")
async def insiders_latest(limit: int = Query(40, ge=1, le=200),
                          purchases: bool = Query(True),
                          ticker: str = Query("", max_length=10),
                          force: bool = Query(False)) -> Dict[str, Any]:
    """Form 4 transactions across the market, newest filing first.

    Enrichment is capped per call and cached per accession, so a cold cache
    returns what it managed and reports how many filings it has not read yet
    rather than holding the page for half a minute. See app/insiders.py.
    """
    return await _run(insiders_mod.latest, limit, purchases, force,
                      insiders_mod.ENRICH_BUDGET, ticker)


@app.get("/api/screener/fields")
async def screener_fields() -> Dict[str, Any]:
    """The filter vocabulary, so the builder is generated rather than duplicated.

    Same reason /api/watches/catalogue exists: three watch conditions once
    compared a stored parameter against a vocabulary spelled somewhere else, and
    all three stored fine, evaluated fine and never fired.
    """
    return screener_mod.describe()


@app.post("/api/screener")
async def screener_run(payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    """Free-form screening over the cached ranking.

    POST rather than GET because the body is a list of bounds, and encoding that
    into a query string would be a second format to parse. It reads no state and
    writes none: this is a filter over rows already on disk, so it is deliberately
    outside _write_guard.
    """
    def build() -> Dict[str, Any]:
        out = screener_mod.run(
            _cached_ranking(),
            filters=payload.get("filters"),
            states=payload.get("states"),
            sort=str(payload.get("sort") or "score"),
            direction=str(payload.get("direction") or "desc"),
            limit=int(payload.get("limit") or screener_mod.DEFAULT_LIMIT),
        )
        out["generated_at"] = datetime.now(timezone.utc).isoformat()
        return out
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
        # Relative-performance scans rank a 143-name peer set, not the screener's
        # cached ranking, so they cannot be expressed as a filter over it. They
        # are shaped identically on the way out, which is what lets the Scan tab
        # render both without knowing the difference.
        if relperf_mod.scan_by_id(scan_id):
            out = relperf_mod.run_scan(YF_PROVIDER, scan_id, limit=limit)
        else:
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
            "the technical metrics the screen computed. Price versus its 20/50/200-day "
            "averages, rate of change, where price sits in its range, volume expansion "
            "and ATR. There is NO option chain, gamma, flow or news here: those need a "
            "per-symbol fetch. Do not state contract prices, greeks, IV, gamma levels or "
            "flow figures for these names. Say the name needs loading for that."
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
    "home"}` and the honest answer was "I cannot see that". Correct, and useless.
    The terminal *can* compute it, nobody had pressed the button.

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
            {"id": key, "glyph": val.get("glyph", ""),
             "label": val["label"], "blurb": val["blurb"]}
            for key, val in ai.PERSONAS.items()
        ],
        # What the choice does and the one thing it cannot, so the menu's
        # promise and the behaviour have one source. Same shape as the
        # knowledge catalogue's, because the menu is now the same menu.
        "changes": ai.PERSONA_CHANGES,
        "never_changes": ai.PERSONA_NEVER_CHANGES,
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

# `is_hosted` moved to app/runtime.py: the auth layer needs the same answer for
# the Secure cookie flag and the OAuth redirect URI, and it cannot import this
# module because this module imports its router. Re-exported above, so
# `main.is_hosted()` still resolves.


def _write_guard(request: Request) -> None:
    """Allow a state-changing request, or explain what it needs.

    The owner comes first, so a signed-in admin is never asked for the token.
    That is the point of the admin flag rather than a convenience: the token is
    a shared secret that has to be pasted into a browser prompt and then lives
    in localStorage, and the person it exists to authenticate already has a
    session that proves who they are much better than a copied string does.

    Paired with `csrf_guard` because in that branch a *cookie* authorises a
    state change, which the token branch never did. SameSite=Lax already
    refuses to send the session cookie on a cross-site POST; this is the second
    lock, and without it another origin could aim the owner's own browser at
    /api/tracker/mark. The token branch does not need it — a header an attacker
    cannot read is itself the proof."""
    # `configured()` first, so an unset ADMIN_EMAILS costs no database read at
    # all. The branch then catches the same two exception families the allowance
    # guard does: resolving a session touches the accounts database, and these
    # four endpoints ran on a token alone long before that database existed. An
    # unmounted volume must not turn a correctly-authenticated write into a 500,
    # so a failure here falls through to the token instead of propagating.
    # OSError as well as sqlite3.Error for the reason given in ai_allowance:
    # opening the database creates its directory first, and os.makedirs on a
    # volume that failed to mount does not raise from sqlite.
    if auth_admin.configured():
        try:
            if auth_deps.is_admin(request):
                auth_deps.csrf_guard(request)
                return
        except (sqlite3.Error, OSError) as exc:
            # Not _allowance_unavailable(): that one says the assistant's daily
            # cap is not being enforced, which is a different fact and would
            # send whoever reads the log looking in the wrong place.
            logging.getLogger("optic").error(
                "could not tell whether this caller is an admin: the accounts "
                "database is unavailable (%s). Falling back to the write token.",
                exc)
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
# Two limits, doing two different jobs.
#
# The hourly one is a *burst* cap, per address, and it is unchanged: it stops a
# script in a loop, and it applies to guests and account holders alike. It stays
# in memory because losing it on restart costs at most one hour of one caller's
# burst, and a counter is not worth a database round trip.
#
# The daily one is an *allowance*, and it is the reason accounts exist here at
# all. A guest gets a few messages a day so the product can be tried; signing in
# raises it to whatever the account's plan allows. That one is in SQLite, because
# an allowance an attacker can reset by waiting for the next OOM restart (see
# DEPLOY.md) is not an allowance.
#
# **Why signing in raises it rather than verification.** With no SMTP configured
# nobody can verify an address at all, so gating the useful allowance on a click
# in an inbox would leave every account holder on the guest tier and look like a
# bug. The account itself is the friction: it costs an address per allowance, and
# the hourly burst cap still sits over the top.
AI_CALLS_PER_HOUR = int(os.environ.get("AI_CALLS_PER_HOUR", "30"))
# 0 means "an account is required", and that is the default.
#
# Pulse is the one surface in the terminal that spends the operator's money per
# use, and it was the one thing a visitor could spend without leaving a trace
# to meter. Metered by address it was also the easiest thing in the app to get
# more of: a new address is a new allowance.
#
# Everything else stays open to guests. `tests/test_auth_authorization.py`
# holds that line and is the test that catches somebody wrapping the wrong
# router in a login check.
#
# Still an environment variable rather than a literal, so an operator running
# their own copy can re-open it -- set it above zero and the per-address
# metering below works exactly as it did.
GUEST_AI_CALLS_PER_DAY = int(os.environ.get("GUEST_AI_CALLS_PER_DAY", "0"))

_ai_calls: Dict[str, List[float]] = {}

_DAY = 86400


# The daily allowance lives in the accounts database, and the assistant must not
# depend on that database being reachable. If it is missing or unmigrated, the
# daily half degrades and the hourly cap carries the load on its own; Pulse keeps
# answering. Failing closed here would mean one broken table takes out the
# feature people came for.
#
# Deliberately not silent: logged once per process, because "the allowance
# stopped being enforced" is exactly the kind of thing that should not be
# discovered on an invoice.
_allowance_warned = False


def _allowance_unavailable(exc: Exception) -> None:
    global _allowance_warned
    if not _allowance_warned:
        _allowance_warned = True
        logging.getLogger("optic").error(
            "assistant daily allowance is not being enforced: the accounts "
            "database is unavailable (%s). The hourly per-address cap still "
            "applies.", exc)


def ai_allowance(request: Request) -> Dict[str, Any]:
    """What this caller may spend today, and how much is left.

    Read by /api/ai-allowance so the assistant panel can say "2 of 5 left, sign
    in for 25" before someone types, rather than after."""
    try:
        user = auth_deps.current_user(request)
        if user and auth_admin.is_admin(user):
            # Reported, not just skipped in the guard. The panel renders this
            # number before anyone types, and showing "3 of 25 left" while
            # nothing is enforcing 25 is the panel lying about the product.
            return {"scope": "admin", "used": 0, "allowed": 0, "left": 0,
                    "enforced": False, "plan": "admin"}
        if user:
            plan = auth_store.subscription(user["id"])
            allowed = int(plan["limits"].get("ai_calls_per_day") or 0)
            bucket = auth_ratelimit.key_bucket(user["id"])
            state = auth_ratelimit.allowance("ai_day", bucket, allowed, _DAY)
            state["scope"] = "account"
            state["plan"] = plan["plan"]
            return state
        state = auth_ratelimit.allowance("ai_day", auth_ratelimit.client_ip(request),
                                         GUEST_AI_CALLS_PER_DAY, _DAY)
        state["scope"] = "guest"
        state["signed_in_allowance"] = auth_store.PLANS["free"]["ai_calls_per_day"]
        # So the panel can say "sign in" before the click rather than showing a
        # composer that answers a 401. Reported as its own fact rather than
        # inferred from `allowed == 0`, which is also what an exhausted
        # allowance looks like and means something different.
        state["requires_account"] = GUEST_AI_CALLS_PER_DAY <= 0
        return state
    except (sqlite3.Error, OSError) as exc:
        # OSError as well as sqlite3.Error: opening the database creates its
        # directory first, and a volume that failed to mount raises from
        # os.makedirs rather than from sqlite. Catching only the sqlite family
        # left the realistic failure — no disk — as a 500 on /api/chat.
        _allowance_unavailable(exc)
        # No `requires_account` here, and that is the point: with the database
        # gone nobody can be identified, the daily cap is not being enforced at
        # all, and telling the panel to demand a sign-in would lock out the
        # account holders it cannot currently see.
        return {"scope": "guest", "used": 0, "allowed": 0, "left": 0,
                "enforced": False,
                "signed_in_allowance": auth_store.PLANS["free"]["ai_calls_per_day"]}


def _spend_guard(request: Request) -> None:
    """Raise 429 once a caller has spent an allowance, daily or hourly."""
    try:
        user = auth_deps.current_user(request)
        if user and auth_admin.is_admin(user):
            # Unlimited: both caps, not only the daily one. The operator asked
            # for it, and it is their key.
            #
            # This skipped the daily cap alone for a while, keeping the hourly
            # one as a runaway-loop guard on the grounds that a loop does not
            # care whose key it is spending. That reasoning is still true; what
            # changed is where the guard belongs. A per-address cap inside the
            # app protects nothing once the operator is the one being capped,
            # and it cannot see spend from anywhere else on the same key. A
            # spend limit set in the Anthropic console can, and it caps the
            # balance whatever the app does -- a loop, a bug, or a leaked key.
            #
            # Only a *verified* owner reaches here. `is_admin` requires the
            # address to be confirmed as well as listed, so registering under
            # the owner's address does not buy anyone unlimited use.
            return
        elif user:
            limits = auth_store.subscription(user["id"])["limits"]
            auth_ratelimit.spend(
                "ai_day", auth_ratelimit.key_bucket(user["id"]),
                int(limits.get("ai_calls_per_day") or 0), _DAY,
                "That is {} assistant messages today, which is what this plan "
                "includes. The allowance resets 24 hours after each message.".format(
                    limits.get("ai_calls_per_day")))
        elif GUEST_AI_CALLS_PER_DAY <= 0:
            # Raised inside the try on purpose. If `current_user` threw
            # instead, we are in the except below and cannot tell a guest from
            # an account holder -- and CLAUDE.md is explicit that the assistant
            # survives the accounts database being gone. A 401 there would
            # turn a disk problem into "Pulse is closed to everyone".
            raise HTTPException(
                status_code=401,
                detail="Pulse needs a free account. {} messages a day once "
                       "you are in, and everything else in the terminal stays "
                       "open either way.".format(
                           auth_store.PLANS["free"]["ai_calls_per_day"]))
        else:
            auth_ratelimit.spend(
                "ai_day", auth_ratelimit.client_ip(request),
                GUEST_AI_CALLS_PER_DAY, _DAY,
                "Guests get {} assistant messages a day. Create a free account "
                "for {} a day. Everything else in the terminal stays open "
                "either way.".format(
                    GUEST_AI_CALLS_PER_DAY,
                    auth_store.PLANS["free"]["ai_calls_per_day"]))
    except (sqlite3.Error, OSError) as exc:
        _allowance_unavailable(exc)

    if AI_CALLS_PER_HOUR <= 0:            # 0 disables the burst cap
        return
    # Behind Railway/Cloudflare the socket peer is the proxy, so prefer the
    # forwarded chain's first hop. Spoofable, but so is any header, and the
    # alternative is bucketing every visitor together as one proxy IP.
    who = auth_ratelimit.client_ip(request)

    now = time.time()
    recent = [t for t in _ai_calls.get(who, []) if now - t < 3600]
    if len(recent) >= AI_CALLS_PER_HOUR:
        oldest = min(recent)
        wait = int(3600 - (now - oldest))
        _ai_calls[who] = recent
        raise HTTPException(
            status_code=429,
            detail="That is {} assistant messages in an hour from this connection. "
                   "Try again in about {} minutes.".format(
                       AI_CALLS_PER_HOUR, max(1, wait // 60)),
        )
    recent.append(now)
    _ai_calls[who] = recent

    # Keep the dict from growing without bound on a long-lived instance.
    if len(_ai_calls) > 2048:
        for addr in [a for a, hits in _ai_calls.items()
                     if not any(now - t < 3600 for t in hits)]:
            _ai_calls.pop(addr, None)


@app.get("/api/ai-allowance")
async def ai_allowance_state(request: Request) -> Dict[str, Any]:
    """How many assistant messages are left, and what an account would give.

    Exists so the panel can be honest before the click rather than after: a 429
    arriving mid-answer reads as a failure, and the same fact stated in advance
    reads as a limit."""
    return {"allowance": ai_allowance(request),
            "ai": ai.available()}


@app.get("/api/knowledge/modes")
async def knowledge_modes() -> Dict[str, Any]:
    """The knowledge levels, and what each one changes.

    Published rather than hardcoded in the client so the selector's promise and
    the behaviour come from one place. A menu claiming to change density while
    the density table disagreed would be a split nothing reports.
    """
    return knowledge_mod.catalogue()


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
    # The level and the lens are separate axes and arrive separately. Both are
    # normalised rather than trusted: they come from localStorage, which the
    # reader can edit, and an unknown value has to answer with something.
    mode = knowledge_mod.normalise(payload.get("mode"))
    context = await _augment_chat_context(history, context)
    return StreamingResponse(
        ai.stream_chat(history, context=context, use_web=use_web,
                       attachments=attachments, persona=persona, mode=mode),
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


# ------------------------------------------------------------------ accounts
#
# Registered here, above the static mount and below everything else. Starlette
# matches routes in registration order and the mount at "/" swallows every path
# after it, so a router added below that line answers nothing at all.
app.include_router(auth_routes.router)
app.include_router(account_mod.router)


@app.on_event("startup")
async def _migrate_accounts() -> None:
    """Bring the accounts schema up to date on boot.

    On boot rather than as a deploy step because the deploy *is* a git push:
    there is no place to run a command between the build finishing and the
    container serving traffic. The runner is idempotent, so this is a no-op on
    every boot after the first."""
    try:
        applied = await _run(accounts_db.migrate)
        if applied:
            logging.getLogger("optic").info(
                "accounts database: applied migrations %s", applied)
    except Exception as exc:                     # a broken accounts db must not
        # take the whole terminal down: every research endpoint works without it.
        logging.getLogger("optic").error(
            "accounts database unavailable, sign-in will fail: %s", exc)


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
    """A cache key that changes whenever any front-end asset changes.

    The icons are in this list and were not, which is why a recolour did not
    reach anybody: the stamp is the newest mtime across the set, so a change to
    a file outside it moves nothing and every cached copy stays valid. The icon
    went from blue to amber in the repository and Chrome kept drawing blue,
    correctly, because nothing it could see had changed.

    Favicons need this more than the other assets rather than less. Chrome keeps
    them in a separate store with its own lifetime, does not reliably refetch
    them on a normal reload, and the one place the app is seen while nobody is
    looking at it is the bookmarks bar.
    """
    stamp = 0
    for name in ("app.js", "auth.js", "charts.js", "styles.css",
                 "icon.svg", "icon-192.png", "icon-512.png",
                 "apple-touch-icon.png", "site.webmanifest"):
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
