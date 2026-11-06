"""How delayed each source's data is, said once (Handoff 4 of the owner's handover pack, 2026-11-03).

**What went wrong.** The authenticated audit of 2026-11-03 found quote delays that disagree: 15 minutes on the Dossier
and in Milo's answers, 20 minutes on Brokerage. Each surface wrote its own sentence: "Delayed up to 15 minutes" on
Home's panels, the status line, Settings, alerts, the paper desk and the research sheet, "about 15 minutes" on Options
and in Milo's prompt, while Brokerage took the longest delay among the holdings' quotes and printed that.

**What the feed states, measured 2026-11-04 at 1:46 PM ET.** Yahoo Finance gives each quote its exchange's delay
(`exchangeDataDelayedBy`) and the trade's own time. NYSE 20 minutes (JPM, KO, IBM, XOM, BRK-B), Nasdaq 15 (AAPL, MSFT,
QQQ), NYSE Arca none (SPY, GLD), the S&P 500 index none, Cboe's indices 15 (^VIX, its last trade 15 minutes old), CME
futures 10 (ES=F, 10 minutes old), over the counter 15 (TCEHY), Toronto 15, currencies and crypto none. Brokerage's 20
was its NYSE holdings, not a different feed.

**So:** a quote's label is computed in the browser from its own stated delay and trade time (static/v2/js/core/
delays.js), in the reader's timezone. A delay other than the usual 15 minutes names its exchange, which is where the 20
comes from. A sentence about quotes in general gives the longest any exchange in the feed states, 20 minutes, "by
exchange", and a quote stating no delay is said to be delayed by up to that longest one, the conservative reading.

This module is the one place those numbers live. GET /api/delays serves them to the pages, and the server's own texts
(the legal notice's label, Milo's prompt and tools, payload notes, the research sheet's freshness) read them here.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.research import policy

VERSION = "2026-11-04.1"
PROVIDER = "Yahoo Finance"
# The longest delay any exchange in the quote feed states (NYSE): what a general statement says, and what a quote that
# states no delay is given.
LONGEST_MINUTES = 20
# The delay most US listings in the feed state (Nasdaq, Cboe, over the counter, Toronto). A quote stating another one
# names its exchange beside the number.
USUAL_MINUTES = 15
# Option chains, a separate feed: OPRA's delayed tape, about 15 minutes behind on the free feed.
CHAIN_MINUTES = 15
# Each exchange's stated delay, as the feed gave it on 2026-11-04: what a reader is shown as examples, never a lookup
# (each quote states its own).
BY_EXCHANGE = {"NYSE": 20, "Nasdaq": 15, "NYSE Arca": 0, "S&P indices": 0, "Cboe indices": 15, "CME futures": 10,
               "Over the counter": 15, "Toronto": 15, "Currencies": 0, "Crypto": 0}
# The feed's exchange codes, as a reader knows them, for naming the exchange beside a delay that is not the usual one.
EXCHANGE_NAMES = {"NYSE": "NYSE", "NYQ": "NYSE", "NYSEArca": "NYSE Arca", "PCX": "NYSE Arca", "NYSE American": "NYSE American",
                  "ASE": "NYSE American", "NasdaqGS": "Nasdaq", "NasdaqGM": "Nasdaq", "NasdaqCM": "Nasdaq", "NMS": "Nasdaq",
                  "NGM": "Nasdaq", "NCM": "Nasdaq", "BATS": "Cboe BZX", "Cboe Indices": "Cboe", "CME": "CME",
                  "CBOT": "CBOT", "NYMEX": "NYMEX", "NY Mercantile": "NYMEX", "COMEX": "COMEX", "ICE Futures": "ICE",
                  "Chicago Board of Trade": "CBOT", "OTC Markets OTCPK": "OTC",
                  "OTC Markets OTCQX": "OTC", "OTC Markets OTCQB": "OTC", "Toronto": "Toronto", "SNP": "S&P",
                  "CCC": "crypto", "CCY": "currency"}


def stale_tolerance() -> int:
    """Minutes past its own delay a regular-session quote's last trade may be before it is stale, not current: the
    research framework's rule (app/research/policy.py quote_stale_minutes, 30 by default), so the sheet and every
    price label draw the line at the same place."""
    try:
        return int(policy.current()["values"]["quote_stale_minutes"])
    except Exception:                                      # noqa: BLE001 - the rule's default when the policy will not read
        return int(policy.RULES["quote_stale_minutes"]["value"])


def stale_limit(delayed_minutes: Any, tolerance: Optional[int] = None) -> float:
    """The age in minutes past which a regular-session price is stale: its stated delay, or the longest when it states
    none, plus the tolerance."""
    try:
        delay = float(delayed_minutes)
    except (TypeError, ValueError):
        delay = float(LONGEST_MINUTES)
    return delay + (stale_tolerance() if tolerance is None else tolerance)


def quotes_up_to() -> str:
    """'up to 20 minutes', for a sentence about quotes in general."""
    return "up to {} minutes".format(LONGEST_MINUTES)


def quote_sentence() -> str:
    """The general statement, the same on every surface that makes one."""
    return ("Quotes are delayed {} during the session, by exchange; each price states its own delay and the time of "
            "its trade.".format(quotes_up_to()))


def quote_label() -> str:
    """The same as a label (the legal notice's `delayed`)."""
    return "Quotes delayed {} during the session, by exchange".format(quotes_up_to())


def chain_sentence(realtime: bool = False, provider: str = "Tradier") -> str:
    """Option chains, their own feed."""
    if realtime:
        return "Option chains are real-time from {}.".format(provider)
    return "Option chains are delayed about {} minutes during the session.".format(CHAIN_MINUTES)


def sources(realtime_chain: bool = False, chain_provider: str = "Tradier") -> Dict[str, Dict[str, Any]]:
    """Each data source, its delay and what its time means."""
    return {
        "quotes": {"provider": PROVIDER, "minutes": None, "longest_minutes": LONGEST_MINUTES,
                   "usual_minutes": USUAL_MINUTES, "by_exchange": BY_EXCHANGE, "text": quote_sentence()},
        "options": {"provider": chain_provider if realtime_chain else PROVIDER,
                    "minutes": 0 if realtime_chain else CHAIN_MINUTES, "text": chain_sentence(realtime_chain, chain_provider)},
        # The broker states quantities and costs as of its last sync; the prices beside them are the quote feed's
        "brokerage": {"provider": "your broker, through SnapTrade", "minutes": None, "prices": "quotes",
                      "text": "Holdings are as of your broker's last sync; Optic prices them with its quotes, delayed {} "
                              "by exchange.".format(quotes_up_to())},
        "fundamentals": {"provider": "SEC EDGAR and Yahoo Finance", "minutes": None,
                         "text": "Statements are as filed; they change when the company files."},
        "news": {"provider": "Publisher and wire feeds", "minutes": None,
                 "text": "Headlines are as published, re-read every few minutes."},
    }


def public(realtime_chain: bool = False, chain_provider: str = "Tradier") -> Dict[str, Any]:
    """GET /api/delays: what every page labels delays from."""
    return {"version": VERSION, "longest_minutes": LONGEST_MINUTES, "usual_minutes": USUAL_MINUTES,
            "chain_minutes": 0 if realtime_chain else CHAIN_MINUTES, "stale_after_minutes": stale_tolerance(),
            "exchanges": EXCHANGE_NAMES,
            "sources": sources(realtime_chain, chain_provider), "footer": quote_sentence()}
