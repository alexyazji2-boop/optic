"""Overnight equity prints, from the one keyless source found that carries them.

**Why this exists.** Reported on a Sunday night: COIN traded at $187.74 in the
overnight session while the terminal showed Friday's $183.00 close. Yahoo has
no overnight tape for single stocks -- fetched live at 21:19 ET that night,
`marketState` CLOSED, `preMarketPrice` None, the newest print Friday 19:59.

**What was tried, live, during the overnight session (Sun 2026-10-04 21:28 ET).**
Every keyless source agreed with Yahoo, and that agreement is the finding:

    Nasdaq      183.00, status Closed
    CNBC        183.00, POST_MKT 183.26 dated Friday
    Robinhood   183.00 / 183.26 -- on its default bounds
    Webull      183.00 / 183.24, and an explicit `"overnight": 0`
    Cboe        183.26, Friday
    Stocktwits  183.24, Friday

Robinhood's marketdata endpoint takes a `bounds` parameter that selects which
session the quote describes, and with `bounds=24_5` it returned a live
overnight print: 186.99, then 186.79, 186.69, 186.42 across four polls twenty
seconds apart, with the bid and ask moving and the timestamps advancing. Its
`last_non_reg_trade_price_source` names the venue that printed it -- Blue Ocean
ATS or Bruce ATS, the two overnight venues seen; see VENUES. Twenty names
surveyed, all twenty with a print from the previous few minutes, so it is not a
COIN quirk, and one request covers many symbols.

**Which fields, and why not the obvious ones.** `last_non_reg_trade_price` and
`venue_last_non_reg_trade_time`, not `last_extended_hours_trade_price` and
`updated_at`. `updated_at` is when the quote record was touched, which advances
on every bid change; the venue time is when the trade printed. A quiet name
would otherwise read as trading now on a price set hours ago.

**What this is not.** It is an undocumented endpoint, in the same terms-of-use
position as the Yahoo endpoints yfinance reads, and it could change or close
without notice. So it is a supplement, never a dependency: every failure
returns nothing, and the page falls back to the regular close with no overnight
line -- which is exactly what it showed before this module existed. For a paid
product this is licensed data from Blue Ocean, and BUSINESS-MODEL.md covers what
redistributing it would actually require.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
import threading
import time
from typing import Any, Dict, Iterable, List, Optional

from .. import feeds

log = logging.getLogger("optic.overnight")

URL = "https://api.robinhood.com/marketdata/quotes/?symbols={}&bounds=24_5"

# Short, like TTL_QUOTE. The overnight tape moves -- four polls measured four
# different prices -- and a cache much longer than the client's own refresh
# would freeze the line it exists to keep current.
TTL_SECONDS = 20.0

# One request per batch. The endpoint takes a comma-separated list, and a long
# one is a long URL rather than many requests.
#
# Measured, because it decides whether batching is safe: an unknown symbol
# inside a batch comes back as a `null` slot in a 200 (`COIN,ZZZZ,NVDA` ->
# [COIN, None, NVDA]), and `parse` skips it. Only a request whose *only* symbol
# is unknown returns 404, and that fails soft like any other error. So one bad
# name cannot take a watchlist's overnight prices down with it.
MAX_BATCH = 40

TIMEOUT_SECONDS = 8.0

# What the venue code means, in words a reader can check. Anything unlisted is
# shown as its code rather than guessed at.
#
# Two, and split evenly. Surveyed across twenty names during the session on
# 2026-10-04: ten printed last on `boats` (AAPL, MSFT, NVDA, AMZN, META, GOOGL,
# AMD, SPY, RARE, INTC) and ten on `bruce` (TSLA, COIN, PLTR, QQQ, IWM, MSTR,
# SOFI, NFLX, SMCI, HOOD). The first version of this module knew only Blue
# Ocean and its copy called it "the overnight venue"; COIN's very next print
# came from Bruce. Venues are why the copy elsewhere names none of them and each
# print carries its own.
VENUES = {"boats": "Blue Ocean ATS", "bruce": "Bruce ATS"}

_SYMBOL = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")

_cache: Dict[str, Dict[str, Any]] = {}
_lock = threading.Lock()


def parse_time(value: Any) -> Optional[dt.datetime]:
    """An aware UTC datetime from the venue's timestamp, or None.

    The venue reports nanoseconds -- `2026-10-05T01:33:21.043708867Z` -- and a
    trailing Z. Python 3.9's `fromisoformat` accepts neither, so the fraction is
    cut to microseconds and the Z made explicit before parsing. Failing that,
    None: an unparseable time is a print whose session cannot be checked, and
    the caller treats it as absent rather than as current."""
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    match = re.match(r"^(.*?\.\d{1,6})\d*(.*)$", text)
    if match:
        text = match.group(1) + match.group(2)
    try:
        stamp = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=dt.timezone.utc)
    return stamp.astimezone(dt.timezone.utc)


def _number(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def parse(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """One quote record into an overnight print, or None if it is not one."""
    if not isinstance(row, dict):
        return None
    price = _number(row.get("last_non_reg_trade_price"))
    stamp = parse_time(row.get("venue_last_non_reg_trade_time"))
    if price is None or stamp is None:
        return None
    if row.get("trading_halted"):
        # A halted name's last print is not a price anyone can trade at.
        return None
    code = str(row.get("last_non_reg_trade_price_source") or "").strip().lower()
    return {
        "symbol": str(row.get("symbol") or "").upper(),
        "price": round(price, 4),
        "time": stamp.isoformat(),
        "bid": _number(row.get("bid_price")),
        "ask": _number(row.get("ask_price")),
        "venue": VENUES.get(code, code or "unknown"),
        "venue_code": code,
        "previous_close": _number(row.get("previous_close")),
    }


def _fetch(symbols: List[str]) -> Dict[str, Dict[str, Any]]:
    body = feeds._fetch(URL.format(",".join(symbols)), "application/json",
                        timeout=TIMEOUT_SECONDS)
    data = json.loads(body.decode("utf-8", "replace"))
    out: Dict[str, Dict[str, Any]] = {}
    for row in (data or {}).get("results") or []:
        parsed = parse(row)
        if parsed and parsed["symbol"]:
            out[parsed["symbol"]] = parsed
    return out


def quotes(symbols: Iterable[str]) -> Dict[str, Dict[str, Any]]:
    """Overnight prints for these symbols. Never raises; missing means none.

    Cached per symbol rather than per batch, so a watchlist and a single ticker
    page asking for overlapping names share the work."""
    wanted = []
    for raw in symbols or []:
        sym = str(raw or "").strip().upper()
        if _SYMBOL.match(sym) and sym not in wanted:
            wanted.append(sym)
    if not wanted:
        return {}

    now = time.time()
    result: Dict[str, Dict[str, Any]] = {}
    stale: List[str] = []
    with _lock:
        for sym in wanted:
            hit = _cache.get(sym)
            if hit and now - hit["at"] < TTL_SECONDS:
                if hit["print"]:
                    result[sym] = hit["print"]
            else:
                stale.append(sym)

    for i in range(0, len(stale), MAX_BATCH):
        batch = stale[i:i + MAX_BATCH]
        try:
            fetched = _fetch(batch)
        except Exception as exc:                          # noqa: BLE001
            # Any failure is "no overnight print", which is what the page
            # showed before this module existed. Logged at info: an endpoint
            # that is down overnight is expected weather, not an incident.
            log.info("overnight quotes unavailable (%s): %s",
                     type(exc).__name__, exc)
            continue
        with _lock:
            for sym in batch:
                _cache[sym] = {"at": now, "print": fetched.get(sym)}
        result.update({s: p for s, p in fetched.items() if s in batch})
    return result


def attach(quote: Dict[str, Any], started_at: Optional[dt.datetime],
           found: Optional[Dict[str, Any]]) -> bool:
    """Put an overnight print on a quote, if it belongs to tonight's session.

    Returns whether anything was attached. Pure apart from mutating `quote`,
    so the rule can be tested without a network or a clock.

    **Tonight's, not the latest.** The venue keeps its last print through the
    day, so on a Monday afternoon this endpoint still reports Sunday night's
    trade. Attaching it would recreate the bug this module exists to fix from
    the other side: an old print presented as current. `started_at` comes from
    `session.overnight_started_at`, which is None outside the session, so the
    whole function is a no-op in daytime.

    **Against the regular close.** The change is measured from `quote["price"]`,
    which outside regular hours is the 4pm close -- the same reference the
    after-hours line uses ("+0.13% vs the close"), so the two read alike."""
    if not started_at or not found or not isinstance(quote, dict):
        return False
    stamp = parse_time(found.get("time"))
    if stamp is None or stamp < started_at.astimezone(dt.timezone.utc):
        return False
    price = _number(found.get("price"))
    if price is None:
        return False
    reference = _number(quote.get("price")) or _number(found.get("previous_close"))
    quote["overnight_price"] = price
    quote["overnight_change_pct"] = (
        round((price / reference - 1.0) * 100.0, 4) if reference else None)
    quote["overnight_time"] = stamp.isoformat()
    quote["overnight_bid"] = found.get("bid")
    quote["overnight_ask"] = found.get("ask")
    quote["overnight_venue"] = found.get("venue")
    return True
