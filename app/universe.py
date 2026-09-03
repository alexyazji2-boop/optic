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


def search(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Rank symbols for a partial query.

    Ordered the way a person expects: the exact symbol first, then symbols that
    start with what was typed, then companies whose name starts with it, then
    anything containing it. Shorter symbols win ties, because "AA" should outrank
    "AAOI" when someone has typed two letters.
    """
    q = (query or "").strip().upper()
    if not q:
        return []
    rows = search_index().get("rows") or []
    volume = _prominence()

    scored: List[tuple] = []
    for row in rows:
        symbol, name = row["symbol"], row["name"]
        upper_name = name.upper()
        if symbol == q:
            rank = 0
        elif symbol.startswith(q):
            rank = 1
        elif upper_name.startswith(q):
            rank = 2
        elif any(word.startswith(q) for word in upper_name.replace(",", " ").split()):
            rank = 3
        elif q in symbol:
            rank = 4
        elif q in upper_name:
            rank = 5
        else:
            continue
        # Within a tier: real businesses before shells and leveraged products,
        # then by how much actually trades, then shorter symbols, then alphabetical.
        # Negated volume so a plain ascending sort puts the busiest first.
        # The demotion has to cross tiers, not just reorder within one. "tes" put
        # three leveraged Tesla products above Tesla itself, because a symbol
        # prefix (TESL) outranks a name prefix (Tesla) — correct in general, wrong
        # when the symbol belongs to a derivative of the thing being searched for.
        if _LOW_PRIORITY.search(name):
            rank += 2
        elif row["etf"]:
            # Also a cross-tier demotion. "tes" surfaced two Tesla-linked funds
            # ahead of Tesla purely because TESL and TEST are symbol prefixes; an
            # operating company is nearly always the intent. An exact symbol match
            # still wins, so searching "SPY" or "VOO" is unaffected.
            rank += 1
        scored.append((
            rank,
            -volume.get(symbol, 0.0),
            len(symbol),
            symbol,
            {"symbol": symbol, "name": name, "etf": row["etf"],
             "dollar_volume": volume.get(symbol) or None},
        ))
        if len(scored) > 4000:
            break

    scored.sort(key=lambda t: t[:4])
    return [t[4] for t in scored[:limit]]


UNIVERSES = {
    "nasdaq": "Every NASDAQ-listed common stock, from NASDAQ's own daily symbol directory.",
    "watchlist": "A fixed ten-name shortlist of the most liquid megacaps.",
}
