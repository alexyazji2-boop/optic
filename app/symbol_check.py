"""Whether a symbol names something Optic can show a page for (Handoff 3 of the owner's handover pack, 2026-11-03).

**What went wrong.** Any address shaped like a ticker opened a Dossier (static/v2/js/core/router.js parse): `#/markets`
drew a "MARKETS" Dossier, with its tabs, an empty chart and a Watch button, and Milo was told the page was "MARKETS
Dossier, Overview" (authenticated audit, 2026-11-03, defect 1). A reader could research a company that does not exist,
save it to a watchlist and ask Milo about it.

**The check**, against the universe the search box uses (app/universe.py), made before any Dossier content is drawn:

1. A symbol in the exchange directory (every US-listed stock and fund, read daily from Nasdaq Trader) or one of the
   instruments Optic quotes (indices, rates, currencies, futures, crypto) is listed.
2. One the directory does not have may still trade where the directory does not reach (over the counter, a foreign
   listing): the quote source is asked, and a trade in the last ten days counts.
3. A quote whose last trade is older is a symbol that no longer trades. Its last trade date is said; a delisting is
   not, since nothing here can verify one.
4. Anything else is unknown.

Either source failing is "could not check": never a not-found, and never a Dossier. An unknown answer is kept ten
minutes (a symbol can list tomorrow); a listed one six hours; a traded one an hour. Each miss is logged with the
attempted text and where the link was, both sanitised, for finding bad links, and nothing about the reader.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from . import universe

log = logging.getLogger("optic.symbols")

# The shape a symbol can have in an address (static/v2/js/core/router.js parse), and the share-class spellings that are
# one company (store.canon): BRK.B, BRK/B, BRK B and brk-b are all BRK-B, the form every price source uses.
SHAPE = re.compile(r"^[A-Z0-9.^=-]{1,12}$")
_CLASS = re.compile(r"^([A-Z]{1,5})[./ ]([AB])$")
OK = ("listed", "instrument", "traded")
REFUSED = ("unknown", "not_trading", "invalid")
TRADED_DAYS = 10
UNKNOWN_TTL = 600.0
TRADED_TTL = 3600.0
LISTED_TTL = 6 * 3600.0
# The quote source, set by app/main.py to the provider's quote; a test passes its own.
QUOTE: Optional[Callable[[str], Dict[str, Any]]] = None
_KINDS = {"EQUITY": "stock", "ETF": "etf", "MUTUALFUND": "fund", "INDEX": "index", "CRYPTOCURRENCY": "crypto",
          "CURRENCY": "fx", "FUTURE": "future"}


def canonical(raw: Any) -> str:
    s = re.sub(r"\s+", " ", str(raw or "")).strip().upper()
    m = _CLASS.match(s)
    return "{}-{}".format(m.group(1), m.group(2)) if m else s


def shown(raw: Any) -> str:
    """The attempted text as a page or a log line may show it: printable characters only, at most 24. A newline in a
    "symbol" cannot start a forged log line, and markup is escaped where it is drawn."""
    return re.sub(r"[^\x20-\x7e]", "", str(raw or "")).strip()[:24]


def referrer(raw: Any) -> str:
    """Where a link came from, with nothing that identifies a reader: an Optic page's route without its query, another
    site's origin, or "direct"."""
    s = str(raw or "").strip()
    if not s:
        return "direct"
    if s.startswith("#"):
        return re.sub(r"[^\x21-\x7e]", "", s.split("?", 1)[0])[:60] or "direct"
    m = re.match(r"^(https?)://([A-Za-z0-9.-]+)", s)
    return "{}://{}".format(m.group(1), m.group(2).lower())[:80] if m else "other"


# ------------------------------------------------------------------------------------------------ the universe
def _directory(loaded_only: bool) -> Optional[Dict[str, Any]]:
    """The directory as the search box reads it, or None when it cannot be read. `loaded_only` reads what is already in
    memory, so a request that is not a search (a watchlist save, a Milo question) never starts the day's download."""
    if loaded_only:
        memo = universe._MEMO.get("index") or (universe._MEMO.get("failed") or {}).get("idx")    # noqa: SLF001
        return memo if memo and memo.get("rows") else None
    try:
        idx = universe._rows_today()                                                            # noqa: SLF001
    except Exception:                                                                            # noqa: BLE001
        return None
    return idx if idx.get("rows") else None


_BY: Dict[str, Any] = {"rows": None, "by": {}}
_BY_LOCK = threading.Lock()


def _by_symbol(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """The directory by symbol, dotted (as filed) and dashed (as quoted), built once per directory."""
    with _BY_LOCK:
        if _BY["rows"] is not rows:
            by: Dict[str, Dict[str, Any]] = {}
            for r in rows:
                by.setdefault(r["symbol"], r)
                by.setdefault(universe._dashed(r["symbol"]), r)                                  # noqa: SLF001
            _BY.update(rows=rows, by=by)
        return _BY["by"]


def _instrument(sym: str) -> Optional[Dict[str, Any]]:
    try:
        return next((r for r in universe._instrument_rows() if r["symbol"] == sym), None)        # noqa: SLF001
    except Exception:                                                                            # noqa: BLE001
        return None


def _when(iso: Any) -> Optional[datetime]:
    try:
        t = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _from_quote(sym: str, quote_fn: Callable[[str], Dict[str, Any]], now: datetime) -> Dict[str, Any]:
    """A symbol the directory does not list, asked of the quote source. Raises when the source fails."""
    q = quote_fn(sym) or {}
    if q.get("price") is None:
        return {"status": "unknown"}
    kind = _KINDS.get(str(q.get("quote_type") or "").upper(), "stock")
    traded = _when(q.get("trade_time"))
    base = {"name": q.get("name") or None, "kind": kind}
    # a price with no trade time is the last close of the source's five days of history: a trade this week
    if traded is None or (now - traded).total_seconds() <= TRADED_DAYS * 86400:
        return dict(base, status="traded",
                    note="Not in the directory of US-listed securities; quoted by the price source, so traded "
                         "elsewhere (over the counter, or a foreign listing).")
    return dict(base, status="not_trading", last_trade=traded.date().isoformat())


# ------------------------------------------------------------------------------------------------ the answer
_CACHE: "OrderedDict[str, tuple]" = OrderedDict()
_CACHE_MAX = 4096
_CACHE_LOCK = threading.Lock()
_TTL = {"listed": LISTED_TTL, "instrument": LISTED_TTL, "traded": TRADED_TTL, "unknown": UNKNOWN_TTL,
        "not_trading": UNKNOWN_TTL}


def _cached(sym: str) -> Optional[Dict[str, Any]]:
    with _CACHE_LOCK:
        hit = _CACHE.get(sym)
        if not hit:
            return None
        at, out = hit
        if time.time() - at > _TTL.get(out["status"], 0):
            _CACHE.pop(sym, None)
            return None
        return dict(out)


def _keep(sym: str, out: Dict[str, Any]) -> None:
    if out["status"] not in _TTL:
        return                                       # "could not check" is never kept: the next request asks again
    with _CACHE_LOCK:
        _CACHE[sym] = (time.time(), dict(out))
        _CACHE.move_to_end(sym)
        while len(_CACHE) > _CACHE_MAX:
            _CACHE.popitem(last=False)


def forget() -> None:
    with _CACHE_LOCK:
        _CACHE.clear()
        _SUGG.clear()


def listed_now(raw: Any) -> Optional[Dict[str, Any]]:
    """The answer for a symbol the directory already in memory lists, or an instrument, at once and with no I/O; None
    for anything else, which check() answers. The endpoint answers these on the event loop, so opening a Dossier
    does not wait behind the other pages' data requests for a thread (SPY took 6.9 s behind BRK-B's, 2026-11-04)."""
    sym = canonical(raw)
    if not sym or not SHAPE.match(sym):
        return None
    hit = _cached(sym)
    if hit and hit["status"] in OK:
        return hit
    inst = _instrument(sym) if universe._INSTRUMENTS is not None else None                       # noqa: SLF001
    idx = _directory(True)
    row = _by_symbol(idx["rows"]).get(sym) if idx else None
    if not inst and not row:
        return None
    base = {"query": shown(raw), "symbol": sym}
    out = (dict(base, status="instrument", name=inst.get("name"), kind=inst.get("kind") or "index") if inst
           else dict(base, status="listed", name=row.get("name"), kind="etf" if row.get("etf") else "stock"))
    _keep(sym, out)
    return out


def check(raw: Any, *, quote_fn: Optional[Callable[[str], Dict[str, Any]]] = None, loaded_only: bool = False,
          now: Optional[datetime] = None) -> Dict[str, Any]:
    """{status, symbol, query, name?, kind?, last_trade?, note?, reason?}: status one of OK (show the page), REFUSED
    (show the not-found state) or "unavailable" (say it could not be checked, and show neither)."""
    query = shown(raw)
    sym = canonical(raw)
    base: Dict[str, Any] = {"query": query, "symbol": sym or None}
    if not sym or not SHAPE.match(sym):
        return dict(base, symbol=None, status="invalid",
                    reason="That is not a symbol: a ticker is up to twelve letters, digits and . - ^ =")
    hit = _cached(sym)
    if hit:
        return hit
    now = now or datetime.now(timezone.utc)
    inst = _instrument(sym)
    if inst:
        out = dict(base, status="instrument", name=inst.get("name"), kind=inst.get("kind") or "index")
    else:
        idx = _directory(loaded_only)
        row = _by_symbol(idx["rows"]).get(sym) if idx else None
        if row:
            out = dict(base, status="listed", name=row.get("name"), kind="etf" if row.get("etf") else "stock")
        elif idx is None and loaded_only:
            return dict(base, status="unavailable", reason="The symbol directory is not loaded yet.")
        else:
            fn = quote_fn or QUOTE
            if fn is None:
                return dict(base, status="unavailable", reason="No quote source to ask.")
            try:
                got = _from_quote(sym, fn, now)
            except Exception as exc:                                                             # noqa: BLE001
                log.info("symbol check for %s: the quote source failed (%s)", sym, type(exc).__name__)
                return dict(base, status="unavailable", reason="The quote source did not answer.")
            # with the directory unreadable, only a recent trade is an answer: anything else could be a false not-found
            if idx is None and got["status"] != "traded":
                return dict(base, status="unavailable", reason="The symbol directory could not be read.")
            out = dict(base, **got)
    _keep(sym, out)
    return out


# ------------------------------------------------------------------------------------------------ suggestions
def _near(a: str, b: str) -> int:
    """Edit distance with transpositions, given up past 2 (APPL is AAPL's two letters swapped: one edit)."""
    if abs(len(a) - len(b)) > 2:
        return 3
    prev2: List[int] = []
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
            if i > 1 and j > 1 and ca == b[j - 2] and a[i - 2] == cb:
                cur[j] = min(cur[j], prev2[j - 2] + 1)
        if min(cur) > 2:
            return 3
        prev2, prev = prev, cur
    return prev[-1]


_SUGG: "OrderedDict[str, tuple]" = OrderedDict()


def suggestions(raw: Any, sym: Optional[str] = None, limit: int = 6) -> List[Dict[str, Any]]:
    """The closest listings to what was typed: symbols one edit away (two for a longer one), the likeliest first,
    then what the search box finds for the text, stocks and funds both. Kept as long as an unknown answer is."""
    key = "{}|{}".format(shown(raw).upper(), limit)
    with _CACHE_LOCK:
        hit = _SUGG.get(key)
        if hit and time.time() - hit[0] <= UNKNOWN_TTL:
            return [dict(x) for x in hit[1]]
    out = _suggest(raw, sym, limit)
    with _CACHE_LOCK:
        _SUGG[key] = (time.time(), out)
        while len(_SUGG) > 512:
            _SUGG.popitem(last=False)
    return out


def _suggest(raw: Any, sym: Optional[str], limit: int) -> List[Dict[str, Any]]:
    text = shown(raw)
    sym = sym or canonical(text)
    out: List[Dict[str, Any]] = []
    seen = set()

    def add(symbol: str, name: Any, kind: Any) -> None:
        s = universe._dashed(str(symbol or "").upper())                                         # noqa: SLF001
        if s and s not in seen and s != sym and len(out) < limit:
            seen.add(s)
            out.append({"symbol": s, "name": name or None, "kind": kind or "stock"})

    idx = _directory(False)
    if sym and SHAPE.match(sym) and idx:
        volume = universe._prominence()                                                          # noqa: SLF001
        reach = 1 if len(sym) <= 4 else 2
        close = [r for r in idx["rows"] if _near(sym, universe._dashed(r["symbol"])) <= reach]   # noqa: SLF001
        close.sort(key=lambda r: (_near(sym, universe._dashed(r["symbol"])), -volume.get(r["symbol"], 0.0),   # noqa: SLF001
                                  len(r["symbol"]), r["symbol"]))
        for r in close[:limit]:
            add(r["symbol"], r.get("name"), "etf" if r.get("etf") else "stock")
    # the letters and digits of what was typed: "%" searched bond names with a percent in them, "AAPL!" finds AAPL
    words = re.sub(r"[^A-Za-z0-9 .\-]", " ", text).strip()
    if re.search(r"[A-Za-z0-9]", words):
        try:
            found = universe.search(words, limit=limit)
        except Exception:                                                                        # noqa: BLE001
            found = []
        for r in found:
            add(r.get("symbol"), r.get("name"), r.get("kind") or ("etf" if r.get("etf") else "stock"))
    return out


# ------------------------------------------------------------------------------------------------ the log of misses
_MISSES: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
_MISSES_MAX = 500
_MISSES_LOCK = threading.Lock()
SINCE = datetime.now(timezone.utc).isoformat(timespec="seconds")


def note_miss(result: Dict[str, Any], ref: Any) -> None:
    """One link to a symbol Optic could not show: logged, and counted for the owner (GET /api/admin/symbol-misses).
    The attempted text and the referring page, sanitised; nothing about the reader."""
    text = shown(result.get("query"))
    where = referrer(ref)
    log.info("invalid symbol %r (%s) from %s", text, result.get("status"), where)
    key = text.upper() or "(empty)"
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _MISSES_LOCK:
        m = _MISSES.pop(key, None) or {"text": key, "count": 0, "first_seen": now, "from": {}}
        m["count"] += 1
        m["last_seen"] = now
        m["status"] = result.get("status")
        if where in m["from"] or len(m["from"]) < 10:
            m["from"][where] = m["from"].get(where, 0) + 1
        _MISSES[key] = m
        while len(_MISSES) > _MISSES_MAX:
            _MISSES.popitem(last=False)


def misses(limit: int = 100) -> Dict[str, Any]:
    with _MISSES_LOCK:
        rows = sorted((dict(m, **{"from": dict(m["from"])}) for m in _MISSES.values()),
                      key=lambda m: (-m["count"], m["text"]))
    return {"since": SINCE, "count": len(rows), "misses": rows[:limit],
            "note": "Links to symbols Optic could not show, since this server started; kept in memory only."}
