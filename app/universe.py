"""Tradable symbol universes.

The Tracker scans the whole NASDAQ rather than a hand-picked shortlist, which
means the list of symbols has to come from somewhere authoritative instead of
being typed out. NASDAQ publishes its own listing directory as a pipe-delimited
file, updated daily, so that's the source.

Two things this module is careful about:

* **What counts as a stock.** The raw directory is about 4,300 lines and includes
  ETFs, warrants, rights, units, preferred shares and depositary receipts. Paper
  trading a warrant against an equity model would be meaningless, so those are
  filtered out by both the file's own flags and the security-name text.
* **Not re-fetching.** The file changes once a day. It's cached to disk with the
  date it was fetched, so a restart doesn't re-download it and a network failure
  falls back to the last good copy rather than emptying the universe.
"""

from __future__ import annotations

import json
import os
import re
import threading
import urllib.error
import urllib.request
from datetime import date
from typing import Any, Dict, List, Optional

# NASDAQ's own symbol directory. Public, keyless, no terms beyond attribution;
# it's the same file their FTP server has served for years.
NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"

CACHE_DIR = os.environ.get(
    "TRACKER_DATA_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"),
)
CACHE_PATH = os.path.join(CACHE_DIR, "universe_nasdaq.json")

_LOCK = threading.RLock()

# Security types that aren't common stock. The directory doesn't flag these, so
# they have to come out of the name. A warrant or a unit has no meaningful
# equity technicals and often barely trades.
_NON_EQUITY = re.compile(
    r"\b(warrant|warrants|right|rights|unit|units|preferred|depositary|debenture|"
    r"notes?|subordinated|trust preferred|convertible)\b",
    re.IGNORECASE,
)

# Fifth-letter suffixes: W warrant, R right, U unit, P/O/N preferred series.
# Applied only to 5-character tickers, which is where the convention holds.
_SUFFIX_CLASSES = set("WRUPON")

# Last-resort universe if the download fails and no cache exists. Deliberately
# the large, liquid NASDAQ names — enough for the tracker to keep working, and
# obviously not the whole exchange, which the caller reports as a degraded state.
FALLBACK_SYMBOLS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "GOOG", "AVGO", "TSLA", "COST",
    "NFLX", "AMD", "PEP", "ADBE", "CSCO", "LIN", "TMUS", "INTU", "QCOM", "TXN",
    "AMGN", "ISRG", "AMAT", "BKNG", "HON", "VRTX", "PANW", "ADP", "SBUX", "GILD",
    "MU", "ADI", "LRCX", "MDLZ", "REGN", "KLAC", "SNPS", "CDNS", "MELI", "PYPL",
    "MAR", "CRWD", "ORLY", "CSX", "ABNB", "FTNT", "ADSK", "CHTR", "NXPI", "WDAY",
    "PCAR", "ROP", "CPRT", "MNST", "PAYX", "AEP", "ODFL", "FAST", "KDP", "ROST",
    "DDOG", "EA", "VRSK", "CTSH", "EXC", "GEHC", "KHC", "CCEP", "LULU", "IDXX",
    "TTWO", "CSGP", "ON", "MRVL", "DXCM", "ANSS", "ZS", "TEAM", "BIIB", "ILMN",
]


def _is_common_stock(symbol: str, name: str, etf_flag: str, test_flag: str,
                     financial_status: str) -> bool:
    if test_flag.strip().upper() == "Y":
        return False                      # NASDAQ's own test tickers
    if etf_flag.strip().upper() == "Y":
        return False                      # funds, not companies
    # Financial status: N is normal. D/E/Q/G/H/J/K mean deficient, delinquent or
    # bankrupt. Those are real securities but a paper trade in one is noise.
    if financial_status.strip().upper() not in ("", "N"):
        return False
    if _NON_EQUITY.search(name):
        return False
    # '$' and '.' mark warrant/unit/class sub-issues in this file, and Yahoo
    # doesn't quote most of them under these symbols anyway.
    if "$" in symbol or "." in symbol:
        return False
    if not re.fullmatch(r"[A-Z]{1,5}", symbol):
        return False
    if len(symbol) == 5 and symbol[4] in _SUFFIX_CLASSES:
        return False
    return True


def _parse(text: str) -> List[str]:
    out: List[str] = []
    for line in text.splitlines()[1:]:          # first line is the header
        parts = line.split("|")
        if len(parts) < 7:
            continue                            # the trailing "File Creation Time" line
        symbol, name, _category, test_flag, financial_status, _lot, etf_flag = parts[:7]
        symbol = symbol.strip().upper()
        if _is_common_stock(symbol, name, etf_flag, test_flag, financial_status):
            out.append(symbol)
    return sorted(set(out))


def _read_cache() -> Optional[Dict[str, Any]]:
    try:
        with open(CACHE_PATH) as handle:
            payload = json.load(handle)
        if payload.get("symbols"):
            return payload
    except (OSError, ValueError):
        pass
    return None


def _write_cache(payload: Dict[str, Any]) -> None:
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(CACHE_PATH, "w") as handle:
            json.dump(payload, handle)
    except OSError:
        pass                                    # a read-only disk shouldn't be fatal


def nasdaq_symbols(force: bool = False) -> Dict[str, Any]:
    """Every NASDAQ-listed common stock, with a note on where the list came from.

    Returns the source alongside the symbols because "the whole NASDAQ" and "the
    80 names we fall back to" are very different claims, and the difference has
    to be visible downstream rather than inferred from a count.
    """
    today = date.today().isoformat()
    with _LOCK:
        cached = _read_cache()
        if cached and not force and cached.get("fetched_on") == today:
            return {**cached, "source": "NASDAQ symbol directory (cached today)"}

        try:
            request = urllib.request.Request(
                NASDAQ_LISTED_URL,
                headers={"User-Agent": "optic-terminal/1.0 (symbol directory)"},
            )
            with urllib.request.urlopen(request, timeout=25) as response:
                text = response.read().decode("utf-8", errors="replace")
            symbols = _parse(text)
            if len(symbols) < 500:
                raise ValueError("directory returned only {} symbols".format(len(symbols)))
            payload = {"symbols": symbols, "fetched_on": today, "count": len(symbols)}
            _write_cache(payload)
            return {**payload, "source": "NASDAQ symbol directory (fetched today)"}
        except (urllib.error.URLError, OSError, ValueError, TimeoutError) as exc:
            if cached:
                return {
                    **cached,
                    "source": "NASDAQ symbol directory (stale cache from {}. Refresh "
                              "failed: {})".format(cached.get("fetched_on"), exc),
                    "stale": True,
                }
            return {
                "symbols": list(FALLBACK_SYMBOLS),
                "fetched_on": None,
                "count": len(FALLBACK_SYMBOLS),
                "source": "built-in large-cap fallback. The NASDAQ directory could not be "
                          "reached ({}), so this is NOT the whole exchange".format(exc),
                "degraded": True,
            }


# ------------------------------------------------------------ symbol search
#
# The universe list above is symbols only, because that's all a scan needs. A
# search box needs names too — nobody types "AAL" hoping for American Airlines,
# they type "american". So this builds a separate index from *both* NASDAQ
# directories: nasdaqlisted covers NASDAQ, otherlisted covers NYSE, NYSE American,
# NYSE Arca, BATS and IEX. Together they're effectively every US-listed symbol.
#
# ETFs are kept here, unlike in the scan universe: someone searching "SPY" wants
# to find it even though the tracker won't trade it.

OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
SEARCH_CACHE_PATH = os.path.join(CACHE_DIR, "symbols.json")

# Trailing security-type boilerplate. "Apple Inc. - Common Stock" is not how anyone
# refers to Apple, but a share class *is* meaningful and has to survive — hence the
# capture group rather than a blanket strip.
_TYPE_SUFFIX = re.compile(
    r"\s*[-–—]?\s*(?:(Class\s+[A-Z0-9]+)\s+)?"
    r"(?:Common|Ordinary|Capital|Registered|Voting|Subordinate\s+Voting)?\s*"
    r"(?:Stock|Shares|Share)\s*$",
    re.IGNORECASE,
)
_TRAILING_JUNK = re.compile(r"[\s,;.\-–—]+$")


def clean_name(raw: str) -> str:
    """Turn a directory security name into something a person would recognise."""
    name = (raw or "").strip()
    # The directories use " - " to separate issuer from instrument, inconsistently.
    match = _TYPE_SUFFIX.search(name)
    if match:
        keep = match.group(1)
        name = name[:match.start()] + ((" " + keep) if keep else "")
    name = _TRAILING_JUNK.sub("", name)
    return name.strip() or (raw or "").strip()


def _parse_search_rows(text: str, symbol_col: int, name_col: int,
                       etf_col: Optional[int], test_col: Optional[int]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for line in text.splitlines()[1:]:
        parts = line.split("|")
        if len(parts) <= max(symbol_col, name_col):
            continue                                   # trailing "File Creation Time" line
        symbol = parts[symbol_col].strip().upper()
        name = parts[name_col].strip()
        if not symbol or not name:
            continue
        if test_col is not None and len(parts) > test_col and parts[test_col].strip().upper() == "Y":
            continue
        if "$" in symbol or not re.fullmatch(r"[A-Z.]{1,6}", symbol):
            continue
        is_etf = (etf_col is not None and len(parts) > etf_col
                  and parts[etf_col].strip().upper() == "Y")
        out.append({"symbol": symbol, "name": clean_name(name), "etf": is_etf})
    return out


def _fetch(url: str) -> str:
    request = urllib.request.Request(
        url, headers={"User-Agent": "optic-terminal/1.0 (symbol directory)"})
    with urllib.request.urlopen(request, timeout=25) as response:
        return response.read().decode("utf-8", errors="replace")


def search_index(force: bool = False) -> Dict[str, Any]:
    """Every US-listed symbol with a readable company name, cached for the day."""
    today = date.today().isoformat()
    with _LOCK:
        cached: Optional[Dict[str, Any]] = None
        try:
            with open(SEARCH_CACHE_PATH) as handle:
                cached = json.load(handle)
        except (OSError, ValueError):
            cached = None
        if cached and not force and cached.get("fetched_on") == today and cached.get("rows"):
            return cached

        rows: List[Dict[str, Any]] = []
        try:
            # nasdaqlisted: Symbol|Security Name|Market Category|Test Issue|...|ETF
            rows += _parse_search_rows(_fetch(NASDAQ_LISTED_URL), 0, 1, 6, 3)
            # otherlisted: ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|...|Test Issue
            rows += _parse_search_rows(_fetch(OTHER_LISTED_URL), 0, 1, 4, 6)
        except Exception as exc:
            if cached and cached.get("rows"):
                return {**cached, "stale": True, "error": str(exc)}
            return {"rows": [], "fetched_on": None, "error": str(exc)}

        # De-duplicate: a handful of symbols appear in both files.
        seen: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            seen.setdefault(row["symbol"], row)
        payload = {
            "rows": sorted(seen.values(), key=lambda r: r["symbol"]),
            "fetched_on": today,
            "count": len(seen),
        }
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            with open(SEARCH_CACHE_PATH, "w") as handle:
                json.dump(payload, handle)
        except OSError:
            pass
        return payload


# Names that clutter a search box: blank-cheque shells with no operating business,
# and leveraged/inverse products that exist only as a bet on some other ticker.
# Both are real listings and stay searchable — they just shouldn't outrank the
# company someone was actually looking for.
_LOW_PRIORITY = re.compile(
    r"\b(acquisition\s+corp|acquisition\s+company|blank\s+check)\b"
    r"|\b\d+(?:\.\d+)?X\b"
    r"|\b(bear|bull)\s+\d|\bdaily\s+target\b|\binverse\b|\bleveraged\b",
    re.IGNORECASE,
)


def _prominence() -> Dict[str, float]:
    """Dollar volume per symbol, where the screener already measured it.

    Reused rather than recomputed: the tracker's prefilter downloads a year of
    bars for the whole NASDAQ and caches the result, so average dollar volume is
    already on disk for the liquid names. It's the only real popularity signal
    available offline — the symbol directory has no size or volume field — and it
    is what puts Apple above a same-length shell company for "aa".
    """
    try:
        with open(os.path.join(CACHE_DIR, "screen_ranking.json")) as handle:
            payload = json.load(handle)
        ranked = (payload.get("ranking") or {}).get("ranked") or []
        return {r["symbol"]: float(r.get("dollar_volume") or 0.0) for r in ranked}
    except (OSError, ValueError, KeyError, TypeError):
        return {}


# Indices, rates, currencies, commodities, futures and crypto are not in the exchange
# directory, so a box that only searched it could not find "VIX", "spx" or "10 year"
# (2026-10-20 search audit: VIX opened VIXM, spx opened SPX Technologies). The rows come
# from the instruments Optic already quotes (analytics/macro.py, longterm.py); `kind`
# sends the client to the instrument page rather than a company dossier.
INSTRUMENT_ALIASES: Dict[str, List[str]] = {
    "^GSPC": ["spx", "s&p", "s&p 500", "s&p500", "sp500", "sp 500", "s and p 500", "s and p"],
    "^NDX": ["ndx", "nasdaq", "nasdaq 100", "nasdaq-100", "nasdaq100"],
    "^DJI": ["dow", "dow jones", "djia", "the dow", "dow jones industrial average"],
    "^RUT": ["rut", "russell", "russell 2000", "small caps"],
    "^VIX": ["vix", "volatility index", "fear index", "fear gauge"],
    "^VVIX": ["vvix"],
    "DX-Y.NYB": ["dxy", "dollar index", "us dollar", "dollar"],
    "USDJPY=X": ["usdjpy", "usd/jpy", "yen"],
    "EURUSD=X": ["eurusd", "eur/usd", "euro"],
    "^TNX": ["tnx", "10 year", "10y", "10-year", "ten year", "us10y", "10 year yield", "10 year treasury"],
    "^FVX": ["fvx", "5 year", "5y", "5-year", "five year", "5 year yield"],
    "^IRX": ["irx", "3 month", "3m", "13 week", "t-bill", "t bill", "3 month bill"],
    "CL=F": ["oil", "crude", "wti", "crude oil"],
    "NG=F": ["natural gas", "nat gas", "natgas"],
    "GC=F": ["gold"],
    "HG=F": ["copper"],
    "BTC-USD": ["bitcoin", "btc"],
    "ES=F": ["es", "es1", "s&p futures", "s&p 500 futures", "spx futures"],
    "NQ=F": ["nq", "nasdaq futures", "nasdaq 100 futures"],
    "RTY=F": ["rty", "russell futures"],
}
_GROUP_KIND = {"volatility": "index", "equity": "index", "fx": "fx", "rates": "rate",
               "commodities": "commodity", "crypto": "crypto", "futures": "future"}


def _instrument_rows() -> List[Dict[str, Any]]:
    """The non-listed instruments, once: symbol, name, kind and the words people type for them."""
    global _INSTRUMENTS
    if _INSTRUMENTS is not None:
        return _INSTRUMENTS
    rows: Dict[str, Dict[str, Any]] = {}
    try:
        from .analytics import macro as macro_mod, longterm as longterm_mod
        for inst in macro_mod.INSTRUMENTS:
            sym = inst["symbol"]
            if not re.search(r"[\^=]|-USD$|\.NYB$", sym):
                continue   # HYG, LQD, TLT are funds in the directory already
            name = inst.get("name") or ("{}, {}".format(inst["label"], inst["note"]) if inst.get("note") else inst["label"])
            rows[sym] = {"symbol": sym, "name": name, "kind": _GROUP_KIND.get(inst.get("group"), "index"),
                         "label": inst.get("label") or sym}
        for sym, meta in (getattr(longterm_mod, "INDEX_META", {}) or {}).items():
            if sym.startswith("^") and sym not in rows:
                rows[sym] = {"symbol": sym, "name": meta.get("name") or sym, "kind": "index", "label": meta.get("name") or sym}
    except Exception:   # a broken import must not take the search box down with it
        rows = {}
    for sym, words in INSTRUMENT_ALIASES.items():
        if sym in rows:
            rows[sym]["aliases"] = [w.upper() for w in words]
    _INSTRUMENTS = list(rows.values())
    return _INSTRUMENTS


_INSTRUMENTS: Optional[List[Dict[str, Any]]] = None
_NAME_ALIASES: Optional[Dict[str, str]] = None
_MEMO: Dict[str, Any] = {}
# US share classes are dotted in the exchange directory (BRK.B) and dashed everywhere a
# price comes from (BRK-B): quotes, watchlists, the paper desk. Search answers in the
# dashed form, and takes either, or a space.
_CLASS = re.compile(r"^([A-Z]{1,5})[.\-/ ]([A-Z])$")


def _company_aliases() -> Dict[str, str]:
    """Company names as people type them ("google" is GOOGL), from the catalyst rules' table."""
    global _NAME_ALIASES
    if _NAME_ALIASES is None:
        try:
            from . import catalyst_rules
            _NAME_ALIASES = {k.upper(): v for k, v in getattr(catalyst_rules, "NAMES", {}).items()}
        except Exception:
            _NAME_ALIASES = {}
    return _NAME_ALIASES


def _rows_today() -> Dict[str, Any]:
    """The directory, read from disk once a day rather than on every keystroke."""
    today = date.today().isoformat()
    memo = _MEMO.get("index")
    if memo and memo.get("fetched_on") == today and memo.get("rows"):
        return memo
    idx = search_index()
    if idx.get("rows") and not idx.get("error"):
        _MEMO["index"] = idx
    return idx


def _dashed(symbol: str) -> str:
    m = _CLASS.match(symbol)
    return "{}-{}".format(m.group(1), m.group(2)) if m else symbol


def search_with_status(query: str, limit: int = 10) -> Dict[str, Any]:
    """`search`, plus whether the directory answered: `available` False when it could not
    be read at all, `stale` when an older copy stood in after a failed refresh."""
    idx = _rows_today()
    out = {"results": search(query, limit, _idx=idx), "available": bool(idx.get("rows")),
           "stale": bool(idx.get("stale"))}
    if idx.get("error"):
        out["reason"] = "The symbol directory could not be refreshed."
    return out


def search(query: str, limit: int = 10, _idx: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Rank symbols for a partial query.

    Ordered the way a person expects: the exact symbol first, then a name people
    use for it ("google", "spx", "10 year"), then symbols that start with what
    was typed, then companies whose name starts with it, then anything containing
    it. Shorter symbols win ties, because "AA" should outrank "AAOI" when someone
    has typed two letters.

    Each result says how it matched (`match`) and what it is (`kind`: stock, etf,
    index, rate, fx, commodity, future, crypto).
    """
    q = (query or "").strip().upper()
    if not q:
        return []
    m = _CLASS.match(q)
    dotted = "{}.{}".format(m.group(1), m.group(2)) if m else None
    idx = _idx if _idx is not None else _rows_today()
    rows = idx.get("rows") or []
    volume = _prominence()
    alias_sym = _company_aliases().get(q)

    scored: List[tuple] = []
    for inst in _instrument_rows():
        sym, words = inst["symbol"], inst.get("aliases") or []
        bare = sym.lstrip("^")
        if q in (sym, bare) or q in words:
            rank, how = (0, "symbol") if q in (sym, bare) else (0.5, "alias")
        elif any(w.startswith(q) for w in words) and len(q) >= 3:
            rank, how = 2, "name"
        elif inst["name"].upper().startswith(q) and len(q) >= 2:
            rank, how = 2, "name"
        else:
            continue
        scored.append((rank, 0.0, len(sym), sym, {"symbol": sym, "name": inst["name"], "etf": False,
                                                     "kind": inst["kind"], "match": how, "dollar_volume": None}))
    for row in rows:
        symbol, name = row["symbol"], row["name"]
        upper_name = name.upper()
        if symbol == q or symbol == dotted:
            rank, how = 0, "symbol"
        elif alias_sym and _dashed(symbol) == alias_sym:
            rank, how = 0.5, "alias"
        elif symbol.startswith(q):
            rank, how = 1, "prefix"
        elif upper_name.startswith(q):
            rank, how = 2, "name"
        elif any(word.startswith(q) for word in upper_name.replace(",", " ").split()):
            rank, how = 3, "word"
        elif q in symbol:
            rank, how = 4, "contains"
        elif q in upper_name:
            rank, how = 5, "contains"
        else:
            continue
        # Within a tier: real businesses before shells and leveraged products,
        # then by how much actually trades, then shorter symbols, then alphabetical.
        # Negated volume so a plain ascending sort puts the busiest first.
        # The demotion has to cross tiers, not just reorder within one. "tes" put
        # three leveraged Tesla products above Tesla itself, because a symbol
        # prefix (TESL) outranks a name prefix (Tesla) — correct in general, wrong
        # when the symbol belongs to a derivative of the thing being searched for.
        # An exact symbol or a known name is never demoted: "SPY" and "SQQQ" mean those.
        if rank >= 1:
            if _LOW_PRIORITY.search(name):
                rank += 2
            elif row["etf"]:
                # Also a cross-tier demotion. "tes" surfaced two Tesla-linked funds
                # ahead of Tesla purely because TESL and TEST are symbol prefixes; an
                # operating company is nearly always the intent.
                rank += 1
        shown = _dashed(symbol)
        scored.append((
            rank,
            -volume.get(symbol, 0.0),
            len(symbol),
            symbol,
            {"symbol": shown, "name": name, "etf": row["etf"], "kind": "etf" if row["etf"] else "stock",
             "match": how, "dollar_volume": volume.get(symbol) or None},
        ))
    # No early stop: the directory is alphabetical, so a cap on matches dropped exact
    # one-letter symbols late in the alphabet (T opened Cooper Companies, 2026-10-20).

    scored.sort(key=lambda t: t[:4])
    return [t[4] for t in scored[:limit]]


UNIVERSES = {
    "curated": "A fixed list of large, widely held stocks and the index, sector and "
               "leveraged funds that trade like them, 86 names in all.",
    "nasdaq": "Every NASDAQ-listed common stock, from NASDAQ's own daily symbol directory.",
    "watchlist": "A fixed ten-name shortlist of the most liquid megacaps.",
}
