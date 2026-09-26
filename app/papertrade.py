"""A manual paper-trading book: marked on demand, stored nowhere.

**Not app/paper.py.** That module is the terminal's OWN record -- positions
opened by the scanner under a fixed risk policy, kept in SQLite, and published
as Optic Portfolio. Its whole value is that nobody has touched it: a track
record a reader can edit is not a track record. So a hand-entered trade must
never reach it, and this module shares that one's arithmetic and none of its
storage.

**Why nothing is stored.** The terminal has no sign-in and is not going to get
one, so a server-side book would be one book shared by every visitor -- your
trades in a stranger's list. The browser keeps the only copy and posts it here
to be marked, which is the same shape `/api/retirement` already uses for
holdings and for the same reason.

**What is reused, deliberately.** `paper.mark_option` resolves an option to the
live chain mid and falls back to a model only when there is no quote, labelling
which it did; `paper._pnl` already carries the 100x contract multiplier and the
sign flip that makes a short position's arithmetic work. Rewriting either here
would be two implementations of the same thing, and the one nobody looks at
would be the one that drifts.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from . import paper

log = logging.getLogger("uvicorn.error")

# A book, not a universe. Fifty is past any hand-entered book and well short of
# a request that would sit on a provider for a minute: each distinct symbol is
# a quote, and every option leg is a chain read on top of that.
MAX_POSITIONS = 50

INSTRUMENTS = ("shares", "option")
DIRECTIONS = ("long", "short")
OPTION_TYPES = ("call", "put")


def _num(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    # NaN fails this comparison against itself, which is the cheapest test for
    # it and the one that matters: a NaN strike reaches the chain lookup and
    # matches nothing, so the position silently marks as modelled forever.
    return out if out == out else None


def clean_position(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """One position from the browser, or None if it cannot be marked.

    Rejected rather than repaired. A position with no entry price has no P&L,
    and guessing one would put a number in front of a reader that nothing in
    the request supports.
    """
    if not isinstance(raw, dict):
        return None
    ticker = str(raw.get("ticker") or "").upper().strip()
    if not ticker or len(ticker) > 12 or not ticker.replace(".", "").replace("-", "").replace("^", "").isalnum():
        return None
    instrument = str(raw.get("instrument") or "shares").lower()
    direction = str(raw.get("direction") or "long").lower()
    if instrument not in INSTRUMENTS or direction not in DIRECTIONS:
        return None
    entry_price = _num(raw.get("entry_price"))
    qty = _num(raw.get("qty"))
    if entry_price is None or entry_price <= 0 or qty is None or qty <= 0:
        return None

    out: Dict[str, Any] = {
        "id": str(raw.get("id") or "")[:64],
        "ticker": ticker,
        "instrument": instrument,
        "direction": direction,
        "qty": qty,
        "entry_price": entry_price,
        "entry_spot": _num(raw.get("entry_spot")) or entry_price,
        "entry_at": str(raw.get("entry_at") or "")[:32],
        "stop": _num(raw.get("stop")),
        "target": _num(raw.get("target")),
    }
    if instrument == "option":
        option_type = str(raw.get("option_type") or "").lower()
        strike = _num(raw.get("strike"))
        expiry = str(raw.get("expiry") or "")[:10]
        if option_type not in OPTION_TYPES or strike is None or not expiry:
            return None
        out.update(option_type=option_type, strike=strike, expiry=expiry)
    return out


def _spot_map(provider, tickers: List[str]) -> Dict[str, Optional[float]]:
    """One quote call for the whole book.

    A book of twelve positions across four symbols is four quotes, not twelve:
    `batch_quote` is what the rest of the app uses for exactly this, and the
    per-position loop below reads the answer rather than asking again.
    """
    if not tickers:
        return {}
    try:
        quotes = provider.batch_quote(tickers) or {}
    except Exception as exc:                                    # noqa: BLE001
        log.warning("paper book: quotes unavailable: %s", exc)
        return {}
    out: Dict[str, Optional[float]] = {}
    for sym in tickers:
        row = quotes.get(sym) or {}
        # `last`, which is what batch_quote calls it. It was `price` here, which
        # is the key /api/ticker's quote block uses -- so every position in the
        # book marked as "No quote for NVDA right now" while NVDA was trading
        # perfectly well. Two field names for the same number, and the wrong one
        # fails silently as an absence rather than as an error.
        #
        # `prev_close` is NOT a fallback. It is yesterday's number, and a book
        # that marked a position at it would be showing a P&L that is a day old
        # without saying so.
        out[sym] = _num(row.get("last"))
    return out


def mark_book(provider, positions: List[Dict[str, Any]],
              rate: float = 0.0) -> Dict[str, Any]:
    """Mark every position in a hand-entered book.

    Each position is marked on its own and reports its own failure. One symbol
    the provider has nothing for must cost that row its mark and nothing else:
    a book that refuses to show eleven positions because the twelfth is a
    delisted ticker is a book nobody can use to close the twelfth.
    """
    cleaned = [c for c in (clean_position(p) for p in (positions or [])[:MAX_POSITIONS]) if c]
    spots = _spot_map(provider, sorted({c["ticker"] for c in cleaned}))

    marks: List[Dict[str, Any]] = []
    for pos in cleaned:
        spot = spots.get(pos["ticker"])
        row: Dict[str, Any] = {"id": pos["id"], "ticker": pos["ticker"], "spot": spot}
        if spot is None:
            row["reason"] = "No quote for {} right now.".format(pos["ticker"])
            marks.append(row)
            continue
        if pos["instrument"] == "shares":
            # The share price IS the mark. No model, no fallback, no label
            # needed -- and saying "Live quote" where there is nothing else it
            # could be is noise.
            # Rounded, because the feed hands back a float32 widened to a
            # double and it arrives as 225.07000732421875. Four places, to
            # match what paper.py stores.
            price, source, extra = round(spot, 4), "Last trade", {}
        else:
            try:
                got = paper.mark_option(provider, pos, spot, rate)
            except Exception as exc:                            # noqa: BLE001
                log.warning("paper book: %s option mark failed: %s", pos["ticker"], exc)
                row["reason"] = "The chain for this contract could not be read."
                marks.append(row)
                continue
            price = got.get("price")
            source = got.get("source")
            extra = {"dte": got.get("dte"), "iv": got.get("iv")}
        if price is None:
            row["reason"] = "No mark for this contract."
            marks.append(row)
            continue
        row.update(paper._pnl(pos, price), mark_price=price, mark_source=source, **extra)
        marks.append(row)

    return {
        "available": True,
        "marks": marks,
        "counted": len(cleaned),
        "dropped": max(0, len(positions or []) - len(cleaned)),
        # Said rather than silently truncated: a book at the cap would
        # otherwise show its first fifty marked and the rest blank forever,
        # which looks like the marking is broken rather than capped.
        "capped": len(positions or []) > MAX_POSITIONS,
        "max_positions": MAX_POSITIONS,
    }
