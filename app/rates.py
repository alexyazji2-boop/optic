"""The risk-free rate the options maths uses, and where it came from.

It was a constant, 0.0 unless RISK_FREE_RATE was set, and the 2026-10-11
analysis measured what that costs: with r = 0 the feed's implied vols put calls
2 to 4 vol points above puts at the same strike on every SPY and AAPL expiry,
which put-call parity produces on its own, and the flow score read it as a
"chase bid" worth +10. SPY's net GEX moved from $430M to $1,138M per 1% between
r = 0 and r = 4%. A reader could not see the choice except in a caveat.

Now: an explicit RISK_FREE_RATE setting wins (an operator's choice, said so);
otherwise the 13-week Treasury bill yield (^IRX, quoted in percent), a
standard short-rate proxy for listed options a few months out; otherwise the last good read; otherwise 0%,
said plainly. A single short rate for every expiry is itself an assumption
(a two-year LEAP sits on a different part of the curve), stated in `note`.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any, Dict, Optional

_LOCK = threading.Lock()
_CACHE: Dict[str, Any] = {}
TTL_SECONDS = 6 * 3600.0


def _from_env() -> Optional[float]:
    raw = os.environ.get("RISK_FREE_RATE")
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _read_irx(provider: Any) -> Optional[Dict[str, Any]]:
    # Yahoo answers ^IRX for some periods and not others: "10d" and "1mo"
    # came back empty on 2026-10-13 while "5d" and "3mo" did not.
    hist = None
    for period in ("5d", "3mo"):
        try:
            hist = provider.history("^IRX", period=period, interval="1d")
        except Exception:                                         # noqa: BLE001
            hist = None
        if hist is not None and not hist.empty and "Close" in hist:
            break
    if hist is None or hist.empty or "Close" not in hist:
        return None
    closes = hist["Close"].dropna()
    if closes.empty:
        return None
    pct = float(closes.iloc[-1])
    # ^IRX is a yield in percent (4.15 means 4.15%). A value outside 0-25 is a
    # bad print, not a rate.
    if not (0.0 <= pct <= 25.0):
        return None
    when = closes.index[-1]
    return {"rate": pct / 100.0, "as_of": str(getattr(when, "date", lambda: when)())}


def risk_free(provider: Any = None, now: Optional[float] = None) -> Dict[str, Any]:
    """{"rate", "source", "as_of", "note"} for the options maths."""
    env = _from_env()
    if env is not None:
        return {"rate": env, "source": "setting", "as_of": None,
                "label": "{:.2%} (the deployment's RISK_FREE_RATE setting)".format(env),
                "note": "One short rate for every expiry."}
    now = now if now is not None else time.time()
    with _LOCK:
        hit = _CACHE.get("irx")
        if hit and now - hit["at"] < TTL_SECONDS:
            return hit["value"]
    read = _read_irx(provider) if provider is not None else None
    with _LOCK:
        if read:
            value = {"rate": read["rate"], "source": "irx", "as_of": read["as_of"],
                     "label": "{:.2%} (13-week Treasury bill, {})".format(read["rate"], read["as_of"]),
                     "note": "One short rate for every expiry; a long-dated contract sits on a "
                             "different part of the curve."}
            _CACHE["irx"] = {"at": now, "value": value}
            _CACHE["last_good"] = value
            return value
        last = _CACHE.get("last_good")
        if last:
            stale = dict(last)
            stale["note"] = "The latest bill-yield read failed; this is the last good one."
            return stale
    return {"rate": 0.0, "source": "unavailable", "as_of": None,
            "label": "0% (the bill yield could not be read, so no rate is assumed)",
            "note": "With no rate, calls price slightly rich to puts at the same strike."}


def reset_cache() -> None:
    with _LOCK:
        _CACHE.clear()
