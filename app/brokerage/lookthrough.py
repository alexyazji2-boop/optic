"""What an ETF or mutual fund holds, from its SEC Form N-PORT.

Registered funds file Form N-PORT, and the public version (NPORT-P) lists
every holding with its value and its share of the fund's net assets. That
includes ETFs organised as unit investment trusts, such as SPY. It is the only
free, official, per-holding source for a fund, and it is late: it describes
the fund as it stood at a past month end, not today.

**How a symbol becomes a filing.** Measured against EDGAR on 2026-10-15:

* `company_tickers_mf.json` (1.2MB, 28,593 rows of `[cik, seriesId, classId,
  symbol]`) maps fund share-class tickers to a series. VTI and VOO are both
  series of CIK 36405 (Vanguard Index Funds), QQQ is series S000101292 of its
  own trust, SCHD is S000034163. Mutual-fund classes resolve too: VTSAX is
  the same series as VTI.
* SPY is not in that file at all. A UIT has no series, and SPY appears only in
  `company_tickers.json` (CIK 884394), like a company. So a ticker that is not
  in the fund file is looked up there, and the CIK's submissions JSON says
  whether it has ever filed N-PORT: SPY has 29 recent NPORT-P filings, AAPL
  and GLD (a commodity trust) have none.
* A series' own filings come from the browse-edgar Atom feed queried with the
  series id as the CIK. A trust's submissions JSON cannot do this: it lists
  every series' filings together and does not say which series each is for.
  The feed answered in 0.2-0.6s for eight series, and once in 30.5s (SPXL), so
  its timeout is longer than the others.
* The document is `primary_doc.xml` at the root of the filing folder. The
  `xslFormNPORT-P_X01/primary_doc.xml` that submissions JSON names is the
  rendered HTML view of it.

Every document's `genInfo` names its series, and that is checked against the
series asked for before anything in it is used.

**Sizes and times**, latest filing, gzip on the wire (SEC compresses when
asked, about 11x), parse with `iterparse` clearing each holding:

    VTI   3.2MB   279KB wire  3,546 rows  0.34s fetch  0.08s parse
    VOO   0.50MB   48KB wire    520 rows  0.18s
    QQQ   0.12MB   12KB wire    105 rows
    SCHD  0.10MB   10KB wire    102 rows
    SPY   0.45MB   37KB wire    504 rows
    BND  20.6MB  1.4MB wire  17,409 rows  0.27s fetch  0.48s parse

So the cap is 64MB of XML, three times the largest bond fund measured.

**Dates.** `repPdDate` is the date the holdings are as of. `repPdEnd` is the
end of the fund's fiscal year (2026-12-31 on a filing about June) and is not a
holdings date at all. Filings arrived once a quarter, about 59 days after the
quarter they describe (VTI: June 30 filed August 28), so holdings shown here
are between two and five months old and every result says so.

**Tickers are almost never in the filing.** Of the five funds above, the
`identifiers/ticker` element appeared on 0 to 3 rows each, and those few were
index futures (ESU6, NQU6). Direxion is the exception: 503 of SPXL's 515 rows
carry one, in the form `BRK/B`. Everything else is matched to SEC's
`company_tickers.json` by the issuer's registered name, which matched 96 to
98% of each fund's equity weight. Each row says how its ticker was found and
how sure that is, and a row with no match has no ticker: a wrong ticker would
pull in another company's sector and price.

**Leveraged and inverse funds are not looked through.** TQQQ's stocks are 30%
of its net assets and its swaps and futures are 270%; SQQQ holds no stocks at
all and is short 303% through swaps. Their holdings say nothing about their
exposure. Index funds measured 0.0 to 0.2% in derivative notional, so the
threshold at 50% is far from both.

Network access is the `fetch` argument, so the tests run on fixtures and
nothing here needs the network to be imported.
"""

from __future__ import annotations

import io
import json
import logging
import os
import re
import tempfile
import threading
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zlib
from datetime import date, datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from .. import feeds

log = logging.getLogger(__name__)

SOURCE = "SEC Form N-PORT"

MF_TICKERS_URL = "https://www.sec.gov/files/company_tickers_mf.json"
CO_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SERIES_FEED_URL = ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={series}"
                   "&type=NPORT-P&dateb=&owner=include&count=10&output=atom")
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
DOC_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{folder}/primary_doc.xml"
INDEX_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{folder}/{acc}-index.htm"

# A fund's holdings change once a quarter in public, so a week of cache costs
# nothing in freshness and keeps the workspace off EDGAR on ordinary visits.
CACHE_TTL_SECONDS = 7 * 86400
# The ticker directories change when something lists. Three days is generous.
MAP_TTL_SECONDS = 3 * 86400
CACHE_VERSION = 1

MAX_DOC_BYTES = int(os.environ.get("LOOKTHROUGH_MAX_BYTES", str(64 * 1024 * 1024)))
MAX_SMALL_BYTES = 8 * 1024 * 1024        # Atom feed 16KB, submissions JSON 10-40KB
MAX_MAP_BYTES = 16 * 1024 * 1024         # the two directories were 1.2MB and 0.8MB
FEED_TIMEOUT = 45.0                      # browse-edgar took 30.5s once (SPXL)
DOC_TIMEOUT = 60.0
SMALL_TIMEOUT = 30.0
# Tried in order when a feed entry turns out to be for another series. Never
# observed, but a trust-level CIK feed would do it, and three downloads is
# the most a single lookup should cost.
MAX_CANDIDATES = 3

DERIVATIVE_HEAVY_PCT = 50.0   # gross swap and futures notional, % of net assets
LEVERAGED_PCT = 150.0         # stocks plus net derivative exposure, % of net assets
INVERSE_PCT = -50.0

ASSET_CLASS = {
    "EC": "equity", "EP": "equity",
    "DBT": "debt", "ABS-MBS": "debt", "ABS-ASBS": "debt", "ABS-CBDO": "debt", "ABS-O": "debt",
    "LON": "debt", "SN": "debt",
    "STIV": "cash_like", "RA": "cash_like",
    "DE": "derivatives", "DCO": "derivatives", "DCR": "derivatives", "DFE": "derivatives",
    "DIR": "derivatives", "DO": "derivatives",
    "COMM": "other", "RE": "other", "OTHER": "other",
}
ASSET_CLASS_LABELS = {
    "equity": "Stocks", "debt": "Bonds and other debt", "cash_like": "Cash and equivalents",
    "derivatives": "Derivatives", "other": "Other assets",
}
_DERIV_KIND = {"fwdDeriv": "forward", "futrDeriv": "future", "swapDeriv": "swap",
               "optionSwaptionWarrantDeriv": "option", "othDeriv": "other"}

NA = {"", "N/A", "NA", "NONE", "000000000"}


class FetchFailed(RuntimeError):
    """EDGAR could not be read. A fact about the connection, not the fund."""


class TooLarge(FetchFailed):
    """The document is bigger than this module will hold in memory."""


# ------------------------------------------------------------------ network

_POLITE_LOCK = threading.Lock()


def _polite_wait(url: str) -> None:
    """Wait until POLITE_GAP_SECONDS after the last request to any sec.gov host.

    Shares app/feeds.py's per-host clock so this module and the filings and
    insider readers do not arrive at EDGAR as one burst. Spaced across the
    whole agency rather than per host: www.sec.gov and data.sec.gov are
    separate hosts but SEC's fair-access limit is per caller."""
    host = urlparse(url).netloc
    with _POLITE_LOCK:
        with feeds._LOCK:                                          # noqa: SLF001
            last = max([t for h, t in feeds._LAST_HIT.items()      # noqa: SLF001
                        if h == host or (h.endswith("sec.gov") and host.endswith("sec.gov"))] or [0.0])
        wait = feeds.POLITE_GAP_SECONDS - (time.time() - last)
        if wait > 0:
            time.sleep(wait)
        with feeds._LOCK:                                          # noqa: SLF001
            feeds._LAST_HIT[host] = time.time()                    # noqa: SLF001


def http_get(url: str, *, max_bytes: int = MAX_DOC_BYTES, timeout: float = SMALL_TIMEOUT) -> bytes:
    """One polite GET with SEC's required User-Agent, gzip, a size cap and a deadline.

    Read in chunks so an oversized document is refused at the cap rather than
    after it has been held whole. urllib's timeout is per socket read, so a
    server trickling bytes would never trip it; the deadline is total."""
    _polite_wait(url)
    req = urllib.request.Request(url, headers={
        "User-Agent": feeds.USER_AGENT, "Accept-Encoding": "gzip", "Accept": "*/*"})
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            gz = (resp.headers.get("Content-Encoding") or "").lower() == "gzip"
            dec = zlib.decompressobj(16 + zlib.MAX_WBITS) if gz else None
            out = bytearray()
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                out += dec.decompress(chunk) if dec else chunk
                if len(out) > max_bytes:
                    raise TooLarge("larger than {:.0f}MB".format(max_bytes / 1048576))
                if time.time() - started > 2 * timeout:
                    raise FetchFailed("took longer than {:.0f}s".format(2 * timeout))
            if dec:
                out += dec.flush()
            return bytes(out)
    except urllib.error.HTTPError as exc:
        raise FetchFailed("SEC answered {}".format(exc.code)) from exc
    except (urllib.error.URLError, OSError) as exc:
        raise FetchFailed("could not reach SEC ({})".format(str(exc)[:80])) from exc
    finally:
        with feeds._LOCK:                                          # noqa: SLF001
            feeds._LAST_HIT[urlparse(url).netloc] = time.time()    # noqa: SLF001


def _get(fetch: Callable[..., Any], url: str, max_bytes: int, timeout: float) -> bytes:
    try:
        body = fetch(url, max_bytes=max_bytes, timeout=timeout)
    except FetchFailed:
        raise
    except Exception as exc:                                       # noqa: BLE001
        raise FetchFailed(str(exc)[:120] or exc.__class__.__name__) from exc
    if body is None:
        raise FetchFailed("no response")
    if isinstance(body, str):
        body = body.encode("utf-8")
    if len(body) > max_bytes:
        raise TooLarge("larger than {:.0f}MB".format(max_bytes / 1048576))
    return body


# ------------------------------------------------------------------ storage

def default_cache_dir() -> str:
    """`$TRACKER_DATA_DIR/lookthrough`, read at call time so a test or a
    deployment that sets the variable after import is honoured. Falls back to
    the repository's data/ like app/feeds.py does."""
    base = os.environ.get("TRACKER_DATA_DIR") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
    return os.path.join(base, "lookthrough")


# Set by a test harness to keep the suite out of data/ (see tests/conftest.py).
CACHE_DIR: Optional[str] = None


def _safe_name(sym: str) -> str:
    return re.sub(r"[^A-Z0-9_.-]", "_", sym.upper())[:24] or "_"


def _read_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            blob = json.load(fh)
        return blob if isinstance(blob, dict) else None
    except (OSError, ValueError):
        return None


def _write_json(path: str, blob: Dict[str, Any]) -> None:
    """Atomic: a reader on another thread sees the old file or the new one,
    never half of one. A failure to write costs the cache, never the answer."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(blob, fh, separators=(",", ":"))
        os.replace(tmp, path)
    except OSError as exc:
        log.info("lookthrough: could not write %s (%s)", path, exc)


# ------------------------------------------------------------ SEC directories

_MAP_MEMO: Dict[str, Tuple[float, Any]] = {}
_MAP_LOCK = threading.Lock()


def _sec_directory(kind: str, fetch, cache_dir: str, now_ts: float) -> Any:
    """One of SEC's two ticker directories, parsed and indexed, kept on disk.

    Raises FetchFailed only when it cannot be fetched AND no copy was ever kept:
    a three-week-old directory still knows QQQ's series."""
    url = MF_TICKERS_URL if kind == "mf" else CO_TICKERS_URL
    path = os.path.join(cache_dir, "_sec", "company_tickers{}.json".format("_mf" if kind == "mf" else ""))
    memo_key = path
    with _MAP_LOCK:
        hit = _MAP_MEMO.get(memo_key)
    if hit and now_ts - hit[0] < MAP_TTL_SECONDS:
        return hit[1]
    disk = _read_json(path)
    raw = None
    fetched_at = None
    if disk and now_ts - float(disk.get("fetched_at") or 0) < MAP_TTL_SECONDS:
        raw, fetched_at = disk.get("raw"), float(disk["fetched_at"])
    else:
        try:
            raw = json.loads(_get(fetch, url, MAX_MAP_BYTES, SMALL_TIMEOUT).decode("utf-8", "replace"))
            fetched_at = now_ts
            _write_json(path, {"fetched_at": now_ts, "raw": raw})
        except (FetchFailed, ValueError) as exc:
            if disk and disk.get("raw") is not None:
                log.info("lookthrough: %s failed (%s), using the copy kept on disk", url, exc)
                raw, fetched_at = disk["raw"], float(disk.get("fetched_at") or 0)
            else:
                raise FetchFailed(str(exc)) from exc
    index = _index_mf(raw) if kind == "mf" else _index_companies(raw)
    with _MAP_LOCK:
        _MAP_MEMO[memo_key] = (fetched_at or now_ts, index)
    return index


def _index_mf(raw: Any) -> Dict[str, Tuple[int, str, str]]:
    out: Dict[str, Tuple[int, str, str]] = {}
    fields = (raw or {}).get("fields") or ["cik", "seriesId", "classId", "symbol"]
    pos = {f: i for i, f in enumerate(fields)}
    for row in (raw or {}).get("data") or []:
        try:
            sym = normalise_ticker(row[pos["symbol"]])
            if sym and sym not in out:
                out[sym] = (int(row[pos["cik"]]), str(row[pos["seriesId"]] or ""), str(row[pos["classId"]] or ""))
        except (IndexError, KeyError, TypeError, ValueError):
            continue
    return out


def _index_companies(raw: Any) -> Dict[str, Any]:
    """by ticker, tickers per CIK in SEC's own order, and three name keys.

    SEC's file is ordered roughly by size, so the first ticker listed for a
    CIK is its main line: GOOGL before GOOG, BRK-B before BRK-A."""
    by_ticker: Dict[str, int] = {}
    tickers: Dict[int, List[str]] = {}
    titles: Dict[int, str] = {}
    exact: Dict[str, set] = {}
    squashed: Dict[str, set] = {}
    shuffled: Dict[str, set] = {}
    rows = raw.values() if isinstance(raw, dict) else (raw or [])
    for r in rows:
        if not isinstance(r, dict):
            continue
        try:
            cik = int(r.get("cik_str"))
        except (TypeError, ValueError):
            continue
        t = normalise_ticker(r.get("ticker"))
        if t:
            by_ticker.setdefault(t, cik)
            tickers.setdefault(cik, [])
            if t not in tickers[cik]:
                tickers[cik].append(t)
        title = str(r.get("title") or "")
        titles.setdefault(cik, title)
        for store, key in ((exact, normalise_name(title)), (squashed, _squash(title)), (shuffled, _shuffle(title))):
            if key:
                store.setdefault(key, set()).add(cik)
    return {"by_ticker": by_ticker, "tickers": tickers, "titles": titles,
            "exact": exact, "squashed": squashed, "shuffled": shuffled}


# ------------------------------------------------------------ name matching

# Trailing words that say what kind of entity it is rather than which one.
# Measured on QQQ, SPY, SCHD, VOO and VTI against SEC's directory: without
# COS/COMPANIES "Lowe's Cos Inc" missed "LOWES COMPANIES INC"; without the
# slash rule "TJX Cos Inc/The" missed "TJX COMPANIES INC /DE/".
_SUFFIXES = {
    "INC", "INCORPORATED", "CORP", "CORPORATION", "CO", "COS", "COMPANY", "COMPANIES", "LTD",
    "LIMITED", "PLC", "PUBLIC", "NV", "SA", "AG", "SE", "LLC", "LP", "HOLDINGS", "HOLDING",
    "GROUP", "THE", "CLASS", "CL", "A", "B", "C", "TRUST", "REIT", "ADR", "ADS", "SPONSORED",
    "ORD", "SHS", "NEW", "DE", "MD", "MA", "TR", "SPA", "ASA", "AB", "OYJ", "BV", "KGAA", "SAB", "CV",
}


def normalise_name(name: Any) -> str:
    s = str(name or "").upper().strip()
    if s in NA:
        return ""
    s = s.replace("&", " AND ")
    s = re.sub(r"\bA/S\b", " ", s)
    s = s.strip(" /")
    # Everything after a slash is a state, a city or "The": "Inc/The",
    # "INC /DE/", "Bank/Los Angeles CA".
    s = re.sub(r"\s*/.*$", "", s)
    s = re.sub(r"[.'`]", "", s)
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    toks = s.split()
    while len(toks) > 1 and toks[-1] in _SUFFIXES:
        toks.pop()
    while len(toks) > 1 and toks[0] == "THE":
        toks.pop(0)
    return " ".join(toks)


def _squash(name: Any) -> str:
    # "Exxon Mobil Corp" against SEC's "ExxonMobil Holdings Corp".
    return normalise_name(name).replace(" ", "")


def _shuffle(name: Any) -> str:
    # SEC's conformed names invert people's names: "SCHWAB CHARLES CORP" for
    # Charles Schwab, "PRICE T ROWE GROUP INC" for T. Rowe Price.
    toks = normalise_name(name).split()
    return " ".join(sorted(toks)) if len(toks) > 1 else ""


def normalise_ticker(t: Any) -> str:
    """Upper case, share-class separator as a hyphen (SEC and Yahoo use BRK-B,
    Direxion's filings say BRK/B), and a trailing Bloomberg exchange code
    dropped (AAPL US)."""
    s = str(t or "").upper().strip()
    s = re.sub(r"\s+(US|UN|UW|UQ|UR|UA|UP)$", "", s)
    s = re.sub(r"[/.]", "-", s)
    # Any other exchange code ("7203 JP") is a listing outside the US that
    # no US quote or profile lookup would find, so it is not a ticker here.
    return s if re.match(r"^[A-Z0-9]{1,6}(-[A-Z0-9]{1,3})?$", s) else ""


def _class_letter(title: str) -> Optional[str]:
    m = re.search(r"(?:CLASS|CL)[\s.-]*([A-Z])\b|-([A-Z])$", (title or "").upper().strip())
    return (m.group(1) or m.group(2)) if m else None


def _match_ticker(row: Dict[str, Any], co: Dict[str, Any]) -> None:
    """Fill ticker, cik, ticker_source, ticker_confidence and share_class_known.

    Identifier first, name second, and nothing when neither is unique. A row
    whose issuer has several listed lines and whose filing does not say which
    gets the issuer's first-listed ticker with share_class_known False: the
    company is right, the share class may not be, and exposure is combined
    per company so no total depends on it."""
    row.update({"ticker": None, "cik": None, "ticker_source": None, "ticker_confidence": None,
                "share_class_known": None, "issuer_tickers": None})
    if row.get("asset_category") not in ("EC", "EP"):
        return
    filed = normalise_ticker(row.pop("_filing_ticker", None))
    if filed:
        cik = co["by_ticker"].get(filed)
        row.update({"ticker": filed, "cik": cik, "ticker_source": "filing",
                    "ticker_confidence": "high" if cik else "medium", "share_class_known": True})
        if cik and len(co["tickers"].get(cik, [])) > 1:
            row["issuer_tickers"] = co["tickers"][cik][:6]
        return
    cik, how = None, None
    # Spacing alone ("Amazon.com Inc" against "AMAZON COM INC") is as good as
    # an exact match; reordered words are weaker evidence.
    for store, key, label in ((co["exact"], normalise_name(row.get("name")), "sec_name"),
                              (co["squashed"], _squash(row.get("name")), "sec_name"),
                              (co["shuffled"], _shuffle(row.get("name")), "sec_name_reordered")):
        hits = store.get(key) if key else None
        if hits and len(hits) == 1:
            cik, how = next(iter(hits)), label
            break
        if hits and len(hits) > 1:
            row["ticker_source"] = "ambiguous_name"
            return
    if not cik:
        return
    lines = co["tickers"].get(cik) or []
    if not lines:
        return
    ticker, known = lines[0], len(lines) == 1
    if not known:
        letter = _class_letter(row.get("title") or "")
        pick = [t for t in lines if letter and t.endswith("-" + letter)]
        if len(pick) == 1:
            ticker, known = pick[0], True
        row["issuer_tickers"] = lines[:6]
    row.update({"ticker": ticker, "cik": cik, "ticker_source": how,
                "ticker_confidence": "medium" if how == "sec_name" else "low", "share_class_known": known})


# ------------------------------------------------------------------ parsing

def _num(v: Any) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f and f not in (float("inf"), float("-inf")) else None


def _clean(v: Any) -> Optional[str]:
    s = (v or "").strip() if isinstance(v, str) else v
    return None if s is None or (isinstance(s, str) and s.upper() in NA) else s


def parse_nport(body: bytes) -> Dict[str, Any]:
    """Every holding in an N-PORT primary_doc.xml, streamed.

    Each `invstOrSec` is read and cleared as soon as it closes, so the tree
    never holds more than one holding: BND's 17,409 rows parse in 0.48s
    without the 20MB document ever being a tree. Raises ET.ParseError on a
    document that is not XML."""
    ns = ""
    gen: Dict[str, Any] = {}
    fund: Dict[str, Any] = {}
    rows: List[Dict[str, Any]] = []
    notes: List[str] = []
    header_series = None
    for event, el in ET.iterparse(io.BytesIO(body), events=("start", "end")):
        if event == "start":
            if not ns and el.tag.startswith("{"):
                ns = el.tag[:el.tag.index("}") + 1]
            continue
        tag = el.tag[len(ns):] if ns and el.tag.startswith(ns) else el.tag
        if tag == "seriesId" and header_series is None:
            header_series = (el.text or "").strip() or None
        elif tag == "genInfo":
            gen = {c.tag[len(ns):] if c.tag.startswith(ns) else c.tag: (c.text or "").strip() for c in el}
            el.clear()
        elif tag in ("netAssets", "totAssets"):
            fund[tag] = _num(el.text)
        elif tag == "explntrNote":
            if el.get("note"):
                notes.append(el.get("note")[:300])
        elif tag == "invstOrSec":
            rows.append(_row(el, ns))
            el.clear()
    series_id = _clean(gen.get("seriesId")) or header_series
    return {
        "series_id": _clean(series_id),
        "series_name": _clean(gen.get("seriesName")),
        "registrant": _clean(gen.get("regName")),
        "registrant_cik": int(gen["regCik"]) if (gen.get("regCik") or "").isdigit() else None,
        "report_date": _clean(gen.get("repPdDate")),
        "fiscal_year_end": _clean(gen.get("repPdEnd")),
        "net_assets": fund.get("netAssets"),
        "total_assets": fund.get("totAssets"),
        "rows": rows,
        "explanatory_notes": notes[:5],
    }


def _row(el: ET.Element, ns: str) -> Dict[str, Any]:
    def text(tag: str) -> Optional[str]:
        return _clean(el.findtext(ns + tag))

    ids = el.find(ns + "identifiers")
    isin = ticker = None
    if ids is not None:
        node = ids.find(ns + "isin")
        isin = _clean(node.get("value")) if node is not None else None
        node = ids.find(ns + "ticker")
        ticker = _clean(node.get("value")) if node is not None else None
    currency = text("curCd")
    fx = None
    cond = el.find(ns + "currencyConditional")
    if currency is None and cond is not None:
        currency, fx = _clean(cond.get("curCd")), _num(cond.get("exchangeRt"))
    asset = text("assetCat")
    asset_desc = None
    cond = el.find(ns + "assetConditional")
    if asset is None and cond is not None:
        asset, asset_desc = _clean(cond.get("assetCat")), _clean(cond.get("desc"))
    issuer = text("issuerCat")
    cond = el.find(ns + "issuerConditional")
    if issuer is None and cond is not None:
        issuer = _clean(cond.get("issuerCat"))
    deriv = None
    notional_usd = None
    direction = None
    info = el.find(ns + "derivativeInfo")
    if info is not None and len(info):
        kid = info[0]
        local = kid.tag[len(ns):] if kid.tag.startswith(ns) else kid.tag
        deriv = _DERIV_KIND.get(local, "other")
        notional = _num(kid.findtext(ns + "notionalAmt"))
        if notional is not None:
            ccy = _clean(kid.findtext(ns + "curCd"))
            # Notional is in the contract's currency: EWG's DAX future is in
            # euros, and the row's exchange rate is euros per dollar.
            if ccy and ccy != "USD" and fx:
                notional = notional / fx
            payoff = (_clean(kid.findtext(ns + "payOffProf")) or "").lower()
            # ProShares writes a short swap as a negative notional and a short
            # future as payOffProf Short, also with a negative notional.
            direction = "short" if notional < 0 or payoff == "short" else "long"
            notional_usd = abs(notional)
    name = text("name")
    title = text("title")
    if asset is None and deriv:
        asset = "DO"
    cls = ASSET_CLASS.get(asset or "", "other")
    if asset == "OTHER" and (asset_desc or "").lower() == "currency":
        cls = "cash_like"
    return {
        "name": name or title or "Unnamed holding",
        "title": title,
        "lei": text("lei"),
        "cusip": text("cusip"),
        "isin": isin,
        "_filing_ticker": ticker,
        "balance": _num(el.findtext(ns + "balance")),
        "units": text("units"),
        "currency": currency,
        "value_usd": _num(el.findtext(ns + "valUSD")),
        "pct": _num(el.findtext(ns + "pctVal")),
        "payoff": text("payoffProfile"),
        "asset_category": asset,
        "asset_class": cls,
        "issuer_category": issuer,
        "country": text("invCountry") if text("invCountry") not in ("XX",) else None,
        "restricted": (text("isRestrictedSec") or "").upper() == "Y",
        "fair_value_level": text("fairValLevel"),
        "derivative": deriv,
        "_notional_usd": notional_usd,
        "_direction": direction,
    }


# --------------------------------------------------------- leverage and inverse

_FACTOR = re.compile(r"(?<![\w.])(-?)(\d+(?:\.\d+)?)\s?x\b", re.I)
_ULTRA = re.compile(r"\bultra(?:pro)?\b(?![- ]?short)", re.I)
# "UltraShort QQQ" and "UltraPro Short QQQ" are leveraged and inverse;
# "Ultra Short-Term Bond" and "Ultra Short Duration" are neither.
_ULTRA_SHORT = re.compile(r"\bultra(?:pro)?\s?short\b(?![- ](?:term|duration|income|bond|maturity|"
                          r"municipal|treasury|govt|government|credit))", re.I)
_INVERSE_WORDS = re.compile(r"\b(?:inverse|bear)\b", re.I)


def name_flags(name: Optional[str]) -> Tuple[bool, bool]:
    """(leveraged, inverse) from the fund's name.

    "Short" alone is not taken as inverse: SHV is "iShares Short Treasury Bond
    ETF" and is not short anything. "Ultra" followed by "-Short" or " Short" is
    an ultra-short-duration bond fund (JPST, VUSB), not ProShares' Ultra."""
    s = name or ""
    leveraged = inverse = False
    for sign, factor in _FACTOR.findall(s):
        f = float(factor)
        if f > 1:
            leveraged = True
        if sign == "-":
            inverse = True
    if _ULTRA_SHORT.search(s):
        leveraged = inverse = True
    elif _ULTRA.search(s):
        leveraged = True
    if _INVERSE_WORDS.search(s):
        inverse = True
    return leveraged, inverse


def derivative_profile(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """Swap, futures and options exposure as a share of net assets.

    Currency forwards are left out on purpose: a currency-hedged equity fund
    holds forwards of about its whole value and its stocks are still exactly
    what it owns. Options carry no notional in N-PORT, so their marked value
    is counted instead; a buffer fund made of options lands above the
    threshold that way."""
    net = parsed.get("net_assets") or 0.0
    long_n = short_n = 0.0
    option_pct = 0.0
    stock_pct = 0.0
    for r in parsed.get("rows") or []:
        if r["asset_class"] == "equity" and (r.get("payoff") or "Long") != "Short":
            stock_pct += r.get("pct") or 0.0
        if r.get("derivative") == "option":
            option_pct += abs(r.get("pct") or 0.0)
        if r.get("derivative") in ("swap", "future", "other") and r.get("_notional_usd") and \
                r.get("asset_category") != "DFE":
            if r.get("_direction") == "short":
                short_n += r["_notional_usd"]
            else:
                long_n += r["_notional_usd"]
    if net <= 0:
        return {"gross_pct": None, "net_pct": None, "implied_pct": None, "option_pct": round(option_pct, 2)}
    gross = 100.0 * (long_n + short_n) / net
    netd = 100.0 * (long_n - short_n) / net
    return {"gross_pct": round(gross, 1), "net_pct": round(netd, 1),
            "implied_pct": round(stock_pct + netd, 1), "option_pct": round(option_pct, 2)}


# ---------------------------------------------------------------- results

def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).replace(microsecond=0).isoformat()


def _ts(now: Any) -> float:
    if now is None:
        return time.time()
    if isinstance(now, datetime):
        return (now if now.tzinfo else now.replace(tzinfo=timezone.utc)).timestamp()
    return float(now)


def _base(sym: str) -> Dict[str, Any]:
    return {"available": False, "status": None, "symbol": sym, "fund_name": None, "registrant": None,
            "series_id": None, "cik": None, "accession": None, "report_date": None, "filed": None,
            "source": SOURCE, "source_url": None, "document_url": None, "holdings": [],
            "coverage_pct": None, "rows_total": 0, "rows_kept": 0, "net_assets_usd": None,
            "leveraged": False, "inverse": False, "derivative_exposure_pct": None, "mix": None,
            "notes": [], "reason": None, "fetched_at": None, "stale": False}


def _refuse(sym: str, status: str, reason: str, **extra: Any) -> Dict[str, Any]:
    out = _base(sym)
    out.update(extra)
    out.update({"status": status, "reason": reason})
    return out


def _display_name(parsed: Dict[str, Any]) -> Optional[str]:
    name = parsed.get("series_name") or parsed.get("registrant")
    return re.sub(r"\s*\((?:R|TM)\)", "", name) if name else None


def _mix(rows: List[Dict[str, Any]], key: str) -> Dict[str, float]:
    """Share of net assets by `key` over every row, not just the kept ones,
    plus what the rows do not account for (cash and receivables less
    liabilities), so each mix adds to 100."""
    out: Dict[str, float] = {}
    total = 0.0
    for r in rows:
        p = r.get("pct") or 0.0
        k = r.get(key) or "not_reported"
        out[k] = out.get(k, 0.0) + p
        total += p
    out["net_other_assets"] = out.get("net_other_assets", 0.0) + (100.0 - total)
    return {k: round(v, 4) for k, v in out.items() if abs(v) >= 0.00005}


def _compact(rows: List[Dict[str, Any]], max_rows: int, net_assets: Optional[float]
             ) -> Tuple[List[Dict[str, Any]], float, int]:
    """Top `max_rows` by share of net assets, then two residual rows so the
    list adds to 100: the rows not kept, and cash and other assets less
    liabilities, which is what the filing's percentages leave over. VTI's add
    to 100.47 (securities-lending collateral is a holding and its matching
    liability is not), so that second row is often slightly negative."""
    ranked = sorted(rows, key=lambda r: -(r.get("pct") or 0.0))
    kept = [r for r in ranked[:max(0, max_rows)] if (r.get("pct") or 0.0) > 0]
    kept_ids = {id(r) for r in kept}
    rest = [r for r in rows if id(r) not in kept_ids]
    total = sum(r.get("pct") or 0.0 for r in rows)
    out = list(kept)
    if rest:
        out.append({"name": "Other holdings", "residual": "other_holdings", "rows": len(rest),
                    "pct": sum(r.get("pct") or 0.0 for r in rest),
                    "value_usd": sum(r.get("value_usd") or 0.0 for r in rest)})
    other = 100.0 - total
    if abs(other) >= 0.0001:
        out.append({"name": "Cash and other assets less liabilities", "residual": "net_other_assets",
                    "rows": 0, "pct": other,
                    "value_usd": net_assets * other / 100.0 if net_assets else None})
    covered = sum(r.get("pct") or 0.0 for r in kept)
    return out, covered, len(kept)


_PUBLIC_FIELDS = ("name", "title", "ticker", "cik", "cusip", "isin", "lei", "pct", "value_usd", "balance",
                  "units", "country", "currency", "asset_category", "asset_class", "issuer_category",
                  "payoff", "restricted", "fair_value_level", "derivative", "ticker_source",
                  "ticker_confidence", "share_class_known", "issuer_tickers")


def _public_row(r: Dict[str, Any]) -> Dict[str, Any]:
    if r.get("residual"):
        return {"name": r["name"], "residual": r["residual"], "rows": r.get("rows"),
                "pct": round(r["pct"], 4), "value_usd": None if r.get("value_usd") is None else round(r["value_usd"], 2),
                "ticker": None, "cusip": None, "isin": None, "country": None, "currency": None,
                "asset_category": None, "asset_class": None, "issuer_category": None, "ticker_source": None}
    out = {k: r.get(k) for k in _PUBLIC_FIELDS}
    # Four places: VTI's smallest holding is 0.0018% of the fund, which two
    # places would round to nothing and drop from every look-through sum.
    out["pct"] = None if r.get("pct") is None else round(r["pct"], 4)
    out["value_usd"] = None if r.get("value_usd") is None else round(r["value_usd"], 2)
    out["balance"] = None if r.get("balance") is None else round(r["balance"], 4)
    return out


def _build(sym: str, parsed: Dict[str, Any], filing: Dict[str, Any], co: Dict[str, Any],
           max_rows: int, now_ts: float) -> Dict[str, Any]:
    rows = parsed["rows"]
    name = _display_name(parsed)
    lev_name, inv_name = name_flags(name)
    prof = derivative_profile(parsed)
    lev_filing = bool(prof["gross_pct"] is not None and prof["gross_pct"] >= DERIVATIVE_HEAVY_PCT
                      and abs(prof["implied_pct"] or 0) >= LEVERAGED_PCT)
    inv_filing = bool(prof["gross_pct"] is not None and prof["gross_pct"] >= DERIVATIVE_HEAVY_PCT
                      and (prof["implied_pct"] or 0) <= INVERSE_PCT)
    heavy = bool((prof["gross_pct"] or 0) >= DERIVATIVE_HEAVY_PCT or prof["option_pct"] >= DERIVATIVE_HEAVY_PCT)
    out = _base(sym)
    out.update({
        "fund_name": name, "registrant": parsed.get("registrant"), "series_id": parsed.get("series_id"),
        "cik": filing["cik"], "accession": filing["accession"], "report_date": parsed.get("report_date"),
        "filed": filing.get("filed"), "source_url": filing["index_url"], "document_url": filing["doc_url"],
        "rows_total": len(rows), "net_assets_usd": None if parsed.get("net_assets") is None
        else round(parsed["net_assets"], 2),
        "leveraged": lev_name or lev_filing, "inverse": inv_name or inv_filing,
        "derivative_exposure_pct": prof["gross_pct"], "fetched_at": _iso(now_ts),
    })
    age = _age_days(parsed.get("report_date"), now_ts)
    out["report_age_days"] = age
    dated = ("Holdings as of {} ({} days ago), filed with SEC on {}. Funds report to SEC every month "
             "but EDGAR showed one public report a quarter, about 60 days after the date it describes, "
             "so these are between two and five months old, not today's holdings."
             .format(parsed.get("report_date"), age, filing.get("filed"))
             if age is not None else "The filing does not state the date its holdings are as of.")
    out["notes"].append(dated)
    if out["leveraged"] or out["inverse"] or heavy:
        what = []
        if out["leveraged"]:
            what.append("leveraged")
        if out["inverse"]:
            what.append("inverse")
        kind = " and ".join(what) or "built from derivatives"
        evidence = []
        if lev_name or inv_name:
            evidence.append("its name says so")
        if prof["gross_pct"] is not None and prof["gross_pct"] >= DERIVATIVE_HEAVY_PCT:
            evidence.append("swaps and futures in the filing come to {:.0f}% of net assets, against "
                            "0 to 0.2% in the index funds measured".format(prof["gross_pct"]))
        if prof["option_pct"] >= DERIVATIVE_HEAVY_PCT:
            evidence.append("options are {:.0f}% of net assets".format(prof["option_pct"]))
        out.update({
            "status": "leveraged_or_inverse" if (out["leveraged"] or out["inverse"]) else "derivative_heavy",
            "reason": "{} is {} ({}). Its economic exposure is not the sum of what it holds, so Optic "
                      "does not look through it and counts it as one fund.".format(
                          sym, kind, "; ".join(evidence) or "from the filing"),
        })
        return out

    kept_and_residual, covered, kept_n = _compact(rows, max_rows, parsed.get("net_assets"))
    for r in kept_and_residual:
        if not r.get("residual"):
            _match_ticker(r, co)
    holdings = [_public_row(r) for r in kept_and_residual]
    equity = [r for r in kept_and_residual if not r.get("residual") and r.get("asset_class") == "equity"]
    by_src: Dict[str, int] = {}
    for r in equity:
        k = r.get("ticker_source") or "none"
        by_src[k] = by_src.get(k, 0) + 1
    out.update({
        "available": True, "status": "ok", "holdings": holdings, "rows_kept": kept_n,
        "coverage_pct": round(min(covered, 100.0), 2),
        "mix": {"asset_class": _mix(rows, "asset_class"), "country": _mix(rows, "country"),
                "currency": _mix(rows, "currency")},
    })
    if kept_n < len(rows):
        out["notes"].append("The {} largest of {} holdings are listed ({:.2f}% of the fund); the rest are "
                            "one 'Other holdings' row.".format(kept_n, len(rows), min(covered, 100.0)))
    if equity:
        out["notes"].append(
            "Tickers for the {} listed stock holdings: {} from the filing itself, {} matched to SEC's "
            "company list by registered name, {} not found. A name match is not an identifier; where a "
            "company has several share classes and the filing does not say which, the ticker is the "
            "company's main line.".format(
                len(equity), by_src.get("filing", 0),
                by_src.get("sec_name", 0) + by_src.get("sec_name_reordered", 0),
                by_src.get("none", 0) + by_src.get("ambiguous_name", 0)))
    if any(r.get("issuer_category") == "RF" and r.get("asset_class") == "equity" for r in equity):
        out["notes"].append("Some holdings are themselves funds. They are listed as one line each and "
                            "not looked through again.")
    for note in parsed.get("explanatory_notes") or []:
        out["notes"].append("From the filing: " + note)
    return out


def _age_days(day: Optional[str], now_ts: float) -> Optional[int]:
    try:
        d = date.fromisoformat(str(day)[:10])
    except (TypeError, ValueError):
        return None
    return (datetime.fromtimestamp(now_ts, timezone.utc).date() - d).days


def _truncate(result: Dict[str, Any], max_rows: int) -> Dict[str, Any]:
    """A cached result asked for with a smaller max_rows: fold the extra rows
    into 'Other holdings' rather than fetch again."""
    hold = result.get("holdings") or []
    listed = [h for h in hold if not h.get("residual")]
    if len(listed) <= max_rows:
        return result
    keep, drop = listed[:max_rows], listed[max_rows:]
    other = next((h for h in hold if h.get("residual") == "other_holdings"), None)
    net = next((h for h in hold if h.get("residual") == "net_other_assets"), None)
    folded = {"name": "Other holdings", "residual": "other_holdings",
              "rows": len(drop) + ((other or {}).get("rows") or 0),
              "pct": round(sum(h.get("pct") or 0 for h in drop) + ((other or {}).get("pct") or 0), 4),
              "value_usd": round(sum(h.get("value_usd") or 0 for h in drop) + ((other or {}).get("value_usd") or 0), 2),
              "ticker": None, "cusip": None, "isin": None, "country": None, "currency": None,
              "asset_category": None, "asset_class": None, "issuer_category": None, "ticker_source": None}
    out = dict(result)
    out["holdings"] = keep + [folded] + ([net] if net else [])
    out["rows_kept"] = len(keep)
    out["coverage_pct"] = round(min(100.0, sum(h.get("pct") or 0 for h in keep)), 2)
    return out


# ------------------------------------------------------------- resolution

_ATOM = "{http://www.w3.org/2005/Atom}"


def _feed_filings(body: bytes) -> List[Dict[str, Any]]:
    root = ET.fromstring(body)
    out = []
    for entry in root.findall(_ATOM + "entry"):
        c = entry.find(_ATOM + "content")
        if c is None:
            continue
        d = {(x.tag[len(_ATOM):] if x.tag.startswith(_ATOM) else x.tag): (x.text or "").strip() for x in c}
        href = d.get("filing-href") or ""
        m = re.search(r"/Archives/edgar/data/(\d+)/(\d{18})/", href)
        acc = d.get("accession-number")
        if not (m and acc):
            continue
        out.append({"form": d.get("filing-type") or "", "filed": d.get("filing-date"), "accession": acc,
                    "cik": int(m.group(1)), "folder": m.group(2)})
    return out


def _submission_filings(blob: Dict[str, Any], cik: int) -> List[Dict[str, Any]]:
    recent = ((blob or {}).get("filings") or {}).get("recent") or {}
    forms = recent.get("form") or []
    out = []
    for i, form in enumerate(forms):
        if not str(form).startswith("NPORT-P"):
            continue
        acc = (recent.get("accessionNumber") or [None] * len(forms))[i]
        if not acc:
            continue
        out.append({"form": form, "filed": (recent.get("filingDate") or [None] * len(forms))[i],
                    "accession": acc, "cik": cik, "folder": acc.replace("-", "")})
    return out


def _ordered(filings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Newest original report first. An amendment (NPORT-P/A) can restate an
    older month, and taking it because it was filed last would show older
    holdings as the latest; it is used only when no original is listed."""
    originals = [f for f in filings if f["form"] == "NPORT-P"]
    amended = [f for f in filings if f["form"] != "NPORT-P"]
    key = lambda f: f.get("filed") or ""                           # noqa: E731
    return sorted(originals, key=key, reverse=True) + sorted(amended, key=key, reverse=True)


def _with_urls(f: Dict[str, Any]) -> Dict[str, Any]:
    f = dict(f)
    f["doc_url"] = DOC_URL.format(cik=f["cik"], folder=f["folder"])
    f["index_url"] = INDEX_URL.format(cik=f["cik"], folder=f["folder"], acc=f["accession"])
    return f


def _read_filing(sym: str, filings: List[Dict[str, Any]], fetch, accept: Callable[[Dict[str, Any]], bool],
                 ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], List[str]]:
    tried: List[str] = []
    for f in _ordered(filings)[:MAX_CANDIDATES]:
        f = _with_urls(f)
        body = _get(fetch, f["doc_url"], MAX_DOC_BYTES, DOC_TIMEOUT)
        parsed = parse_nport(body)
        if accept(parsed):
            return f, parsed, tried
        tried.append("{} ({})".format(f["accession"], parsed.get("series_id") or parsed.get("registrant")))
    return None, None, tried


def _resolve(sym: str, fetch, cache_dir: str, now_ts: float, max_rows: int) -> Dict[str, Any]:
    mf = _sec_directory("mf", fetch, cache_dir, now_ts)
    co = _sec_directory("co", fetch, cache_dir, now_ts)
    hit = mf.get(sym)
    if hit:
        cik, series_id, _class_id = hit
        body = _get(fetch, SERIES_FEED_URL.format(series=series_id), MAX_SMALL_BYTES, FEED_TIMEOUT)
        filings = _feed_filings(body)
        if not filings:
            return _refuse(sym, "no_nport",
                           "{} is fund series {} in SEC's directory, but EDGAR lists no Form N-PORT for it. "
                           "A new fund's first public report appears a few months after it launches."
                           .format(sym, series_id), series_id=series_id, cik=cik)
        f, parsed, tried = _read_filing(sym, filings, fetch, lambda p: p.get("series_id") == series_id)
        if not parsed:
            return _refuse(sym, "unverified",
                           "The N-PORT filings EDGAR listed for {} are for a different series ({}), so "
                           "none of them can be shown as its holdings.".format(sym, ", ".join(tried)),
                           series_id=series_id, cik=cik)
        return _build(sym, parsed, f, co, max_rows, now_ts)

    cik = co["by_ticker"].get(sym)
    if cik is None:
        return _refuse(sym, "unknown_symbol",
                       "{} is in neither of SEC's ticker directories (funds, or companies and trusts), so "
                       "Optic cannot find a filing for it. Funds not registered with SEC, such as most "
                       "funds listed outside the US, publish no N-PORT.".format(sym))
    blob = json.loads(_get(fetch, SUBMISSIONS_URL.format(cik=cik), MAX_SMALL_BYTES, SMALL_TIMEOUT)
                      .decode("utf-8", "replace"))
    filings = _submission_filings(blob, cik)
    name = blob.get("name") or co["titles"].get(cik) or sym
    if not filings:
        sic = str(blob.get("sicDescription") or "")
        if "commodit" in sic.lower():
            why = ("{} ({}) is a commodity trust. It is not a registered fund, files no Form N-PORT, and its "
                   "exposure is the commodity it holds.".format(sym, name))
        elif blob.get("entityType") == "operating":
            why = ("{} ({}) is a company's stock, not a fund: SEC has no Form N-PORT from it and there are no "
                   "holdings to look through.".format(sym, name))
        else:
            why = ("{} ({}) has filed no Form N-PORT with SEC. Only registered funds file one, so there is no "
                   "public holdings list to look through.".format(sym, name))
        return _refuse(sym, "not_a_fund", why, cik=cik, fund_name=name)

    def same_registrant(p: Dict[str, Any]) -> bool:
        # A unit investment trust such as SPY has no series and files under
        # its own CIK. A filing that names a series came from a trust with
        # several funds, and nothing here says which of them this ticker is.
        return p.get("registrant_cik") == cik and not p.get("series_id")

    f, parsed, tried = _read_filing(sym, filings, fetch, same_registrant)
    if not parsed:
        return _refuse(sym, "unverified",
                       "{} ({}) files N-PORT for more than one fund and SEC's directory does not say which "
                       "series this ticker is, so no filing can be shown as its holdings."
                       .format(sym, name), cik=cik, fund_name=name)
    return _build(sym, parsed, f, co, max_rows, now_ts)


# ------------------------------------------------------------------ entry

def constituents(symbol: str, *, fetch: Optional[Callable[..., Any]] = None, cache_dir: Optional[str] = None,
                 now: Any = None, max_rows: int = 600) -> Dict[str, Any]:
    """A fund's holdings from its latest public N-PORT, or a reason it has none.

    Callers test `available is not True`: a refusal is a truthy dict.
    `fetch(url, *, max_bytes, timeout) -> bytes` reaches EDGAR (default
    `http_get`). Results, refusals included, are kept a week per symbol under
    `cache_dir`; when SEC cannot be reached the last copy is served however
    old, marked `stale`. A connection failure is never kept, so the next call
    tries again."""
    sym = normalise_ticker(symbol)
    now_ts = _ts(now)
    max_rows = max(1, int(max_rows or 600))
    if not sym:
        return _refuse(str(symbol or ""), "invalid", "There is no symbol to look up.")
    cache_dir = cache_dir or CACHE_DIR or default_cache_dir()
    path = os.path.join(cache_dir, _safe_name(sym) + ".json")
    kept = _read_json(path)
    if kept and kept.get("version") != CACHE_VERSION:
        kept = None
    if kept and isinstance(kept.get("result"), dict):
        fresh = now_ts - float(kept.get("fetched_at") or 0) < CACHE_TTL_SECONDS
        res = kept["result"]
        enough = (int(kept.get("max_rows") or 0) >= max_rows
                  or (res.get("rows_kept") or 0) >= (res.get("rows_total") or 0))
        if fresh and enough:
            return _truncate(res, max_rows)
    try:
        result = _resolve(sym, fetch or http_get, cache_dir, now_ts, max_rows)
    except TooLarge as exc:
        result = _refuse(sym, "too_large",
                         "{}'s N-PORT filing is {}, more than Optic reads, so it is not looked through."
                         .format(sym, exc))
    except (FetchFailed, ET.ParseError, ValueError) as exc:
        reason = ("SEC's filing for {} could not be read ({})".format(sym, str(exc)[:80])
                  if isinstance(exc, ET.ParseError) else
                  "SEC could not be reached ({})".format(str(exc)[:80]))
        if kept and isinstance(kept.get("result"), dict):
            res = dict(_truncate(kept["result"], max_rows))
            res["stale"] = True
            res["notes"] = list(res.get("notes") or []) + [
                "{}, so this is the copy Optic kept from {}.".format(reason, _iso(float(kept.get("fetched_at") or 0)))]
            return res
        return _refuse(sym, "unavailable", reason + ", and Optic has no earlier copy. Try again later.")
    _write_json(path, {"version": CACHE_VERSION, "fetched_at": now_ts, "max_rows": max_rows, "result": result})
    return result
