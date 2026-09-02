"""Implied correlation: is the index cheap or expensive versus its own parts?

An index option is a bet on the basket; single-stock options are bets on the
pieces. The gap between them is a statement about **correlation** — how much the
market expects these names to move together. If every component were perfectly
correlated the index would be exactly as volatile as its weighted parts. It never
is, because they partly cancel, and the size of that cancellation is what index
implied vol is really pricing.

The identity, for weights that sum to one:

    implied correlation  ~=  index variance / (weighted average component vol)^2

High readings mean the market is paying for everything to move together — a
macro tape, where the index is expensive relative to its parts. Low readings mean
it expects dispersion, single names going their own way. This is the number
behind the dispersion trade, and it moves ahead of regime changes more often than
the index itself does.

**This is an approximation and is labelled one everywhere it appears.** CBOE
publishes a real implied-correlation index computed across the full S&P 500 with
exact weights from a licensed constituent file. This uses the largest holdings
only, weighted by their current market capitalisation, with at-the-money implied
vol standing in for a full surface. The direction and the changes are meaningful;
the level should not be compared against CBOE's COR index and called the same
number.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np

log = logging.getLogger(__name__)

# The index and the names standing in for it. Deliberately the mega-caps: they
# are roughly a third of the S&P by weight, so their implied vols dominate the
# index's, and any correlation estimate built from a longer tail of small
# weights adds fetches without moving the answer.
INDEX = "SPY"
BASKET = ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "AVGO", "TSLA",
          "BRK-B", "JPM", "LLY", "V"]

# ATM is defined as strikes within this band of spot.
ATM_BAND = 0.05

# Only expiries in this window — near-dated enough to be liquid, far enough out
# that a single event does not dominate.
MIN_DTE, MAX_DTE = 14, 75

# Bands for describing the reading. Implied correlation is bounded 0-1 in theory
# and clusters between about 0.15 and 0.6 in practice on a mega-cap basket.
HIGH, LOW = 0.55, 0.30


def _num(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if out != out or out in (float("inf"), float("-inf")) else out


def atm_iv(provider, symbol: str) -> Optional[float]:
    """Median at-the-money implied vol across near-dated expiries, as a decimal."""
    try:
        quote = provider.quote(symbol) or {}
        spot = _num(quote.get("price"))
        chain = provider.options_chain(symbol, max_expiries=4)
    except Exception as exc:
        log.info("implied correlation: no chain for %s: %s", symbol, exc)
        return None
    if spot is None or spot <= 0 or chain is None or getattr(chain, "empty", True):
        return None

    frame = chain
    for col in ("strike", "iv", "dte"):
        if col not in frame.columns:
            return None
    near = frame[(frame["strike"] >= spot * (1 - ATM_BAND))
                 & (frame["strike"] <= spot * (1 + ATM_BAND))
                 & (frame["dte"] >= MIN_DTE) & (frame["dte"] <= MAX_DTE)]
    if near.empty:
        return None
    iv = _num(near["iv"].median())
    return iv if iv and 0.01 < iv < 3.0 else None


def build(provider, basket: Optional[List[str]] = None) -> Dict[str, Any]:
    """Implied correlation across the mega-cap basket, against index vol."""
    names = list(basket or BASKET)

    index_iv = atm_iv(provider, INDEX)
    if index_iv is None:
        return {"available": False,
                "reason": "No usable {} option chain, so there is no index vol to "
                          "compare against.".format(INDEX)}

    rows: List[Dict[str, Any]] = []
    for symbol in names:
        iv = atm_iv(provider, symbol)
        if iv is None:
            continue
        cap = None
        try:
            prof = provider.profile(symbol) or {}
            cap = _num(prof.get("market_cap"))
            if cap is None:
                q = provider.quote(symbol) or {}
                cap = _num(q.get("market_cap"))
        except Exception:
            cap = None
        rows.append({"symbol": symbol, "iv": iv, "market_cap": cap})

    if len(rows) < 5:
        return {"available": False,
                "reason": ("Only {} of {} basket names returned a usable chain. A "
                           "correlation estimate from fewer than five is not worth "
                           "showing.".format(len(rows), len(names)))}

    # Cap weights where available, equal weights otherwise — and say which was
    # used, because an equal-weighted mega-cap basket is a different instrument
    # from a cap-weighted one and the reader should know which they are reading.
    caps = [r["market_cap"] for r in rows if r["market_cap"]]
    weighted_by = "market cap" if len(caps) == len(rows) else "equal weight"
    if weighted_by == "market cap":
        total = sum(caps)
        for r in rows:
            r["weight"] = r["market_cap"] / total
    else:
        for r in rows:
            r["weight"] = 1.0 / len(rows)

    weighted_vol = sum(r["weight"] * r["iv"] for r in rows)
    if weighted_vol <= 0:
        return {"available": False, "reason": "Component vols summed to zero."}

    implied_corr = (index_iv ** 2) / (weighted_vol ** 2)
    # The identity can exceed 1 when the basket does not represent the index —
    # which it does not, exactly. Report the raw value alongside the clipped one
    # rather than hiding a number that says the approximation is straining.
    clipped = float(np.clip(implied_corr, 0.0, 1.0))

    if clipped >= HIGH:
        band, plain = "high", ("The market is paying for these names to move together. "
                               "That is a macro tape — index hedges are expensive "
                               "relative to single-stock ones, and stock picking is "
                               "fighting a market that does not differentiate.")
    elif clipped <= LOW:
        band, plain = "low", ("The market expects these names to go their own ways. "
                              "Index vol is cheap relative to its parts, which is the "
                              "tape where single-name selection actually pays.")
    else:
        band, plain = "normal", ("Correlation expectations are mid-range — neither a "
                                 "pure macro tape nor a stock-picker's one.")

    rows.sort(key=lambda r: -r["weight"])
    return {
        "available": True,
        "index": INDEX,
        "index_iv_pct": round(index_iv * 100.0, 2),
        "weighted_component_iv_pct": round(weighted_vol * 100.0, 2),
        "implied_correlation": round(clipped, 3),
        "implied_correlation_raw": round(implied_corr, 3),
        "strained": implied_corr > 1.0,
        "band": band,
        "plain": plain,
        "weighted_by": weighted_by,
        "components": [{"symbol": r["symbol"], "iv_pct": round(r["iv"] * 100.0, 2),
                        "weight_pct": round(r["weight"] * 100.0, 2)} for r in rows],
        "components_used": len(rows),
        "components_requested": len(names),
        "dispersion_note": (
            "Index implied vol is {:.1f}% against a weighted component average of "
            "{:.1f}%. The index is {} than its parts, which is what correlation "
            "pricing means in practice.".format(
                index_iv * 100.0, weighted_vol * 100.0,
                "calmer" if index_iv < weighted_vol else "no calmer")
        ),
        "method": (
            "An approximation, not CBOE's index. Implied correlation is estimated "
            "as index variance divided by the squared weighted-average component "
            "implied vol, across the {} largest holdings weighted by {}, using "
            "median at-the-money implied vol for expiries {}-{} days out. CBOE's "
            "COR index uses the full constituent list with licensed weights and a "
            "complete vol surface; the direction and the changes here are "
            "meaningful, the level should not be quoted as the same number."
            .format(len(rows), weighted_by, MIN_DTE, MAX_DTE)
        ),
    }
