"""Congressional stock trades, from the filings themselves.

**What this costs: nothing.** The STOCK Act requires members of Congress to
disclose covered transactions within 45 days, and the Clerk of the House
publishes those filings at disclosures-clerk.house.gov with no key, no licence
and no paid tier. Vendors resell this; the source is public.

**Shape of the data.** One annual ZIP holds an XML index of every financial
filing -- 1,695 for 2026, of which 400 are `FilingType P`, the Periodic
Transaction Reports that carry actual trades. The index has no ticker and no
amount: it is a list of documents. Each trade lives in a per-filing PDF at
`/public_disc/ptr-pdfs/{year}/{doc_id}.pdf`, and those PDFs carry a real text
layer, so this is parsing rather than OCR.

**What a filing actually tells you, and what it does not.** The amount is a
band -- "$1,001 - $15,000" -- never a figure, so a dollar total across trades
is a range and is presented as one. The transaction date can be up to 45 days
before the filing date, and both are recorded here because the gap is the part
a reader should see. Options and bond trades appear in the same tables; only
rows with an equity-shaped ticker are kept, which is why a Treasury note with
a CUSIP in the ticker position is skipped rather than parsed into a symbol
that does not exist.

**Not a signal.** A disclosure is a record of something that happened up to
seven weeks ago, filed by someone who is not required to explain it. This
module reports filings.

Senate filings are deliberately not here. efdsearch.senate.gov gates its search
behind an acceptance form and a session cookie rather than publishing an
archive, so it needs a different and more fragile approach than reading a
published file. The House is the half that is offered openly.
"""

from __future__ import annotations

import io
import logging
import os
import re
import statistics
import threading
import time
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests

log = logging.getLogger("uvicorn.error")

HOUSE_INDEX = "https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}FD.zip"
HOUSE_PTR = "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{year}/{doc}.pdf"
SOURCE_PAGE = "https://disclosures-clerk.house.gov/PublicDisclosure"

_DATA_DIR = os.environ.get(
    "TRACKER_DATA_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                 "data"),
)
CACHE_DIR = os.path.join(_DATA_DIR, "congress")

# The index is republished as filings land; a filed PDF never changes.
INDEX_TTL = float(os.environ.get("CONGRESS_INDEX_TTL", "21600"))     # 6 hours
# How many unseen filings to pull per refresh. 400 PDFs is 32MB and several
# minutes against a government file server that owes us nothing, so the
# backlog fills over successive refreshes instead of in one burst.
FETCH_BUDGET = int(os.environ.get("CONGRESS_FETCH_BUDGET", "25"))
REQUEST_GAP = float(os.environ.get("CONGRESS_REQUEST_GAP", "0.4"))
TIMEOUT = 25

_LOCK = threading.RLock()
_MEM: Dict[str, Any] = {"at": 0.0, "trades": [], "index_at": None, "parsed": 0, "known": 0}

# A ticker in the asset column, and nothing that merely looks like one. Bonds
# carry a 9-character CUSIP in the same parentheses and must not become symbols.
_ROW = re.compile(
    r"\((?P<ticker>[A-Z][A-Z.\-]{0,5})\)\s*\[(?P<kind>[A-Z]{2})\]\s*"
    r"(?P<tx>P|S \(partial\)|S|E)\s+"
    r"(?P<date>\d{2}/\d{2}/\d{4})\s+(?P<notified>\d{2}/\d{2}/\d{4})\s+"
    r"\$(?P<low>[\d,]+)\s*-\s*\$(?P<high>[\d,]+)")
_NAME = re.compile(r"Name:\s*(.+?)\s*Status:")
_DIST = re.compile(r"State/District:\s*([A-Z]{2}\d{2})")
# Asset types worth keeping. ST stock, OP option, CS corporate security.
_EQUITY_KINDS = {"ST", "OP", "CS"}
_TX_LABEL = {"P": "purchase", "S": "sale", "S (partial)": "partial sale", "E": "exchange"}


def _session() -> requests.Session:
    s = requests.Session()
    # A government file server is entitled to know who is asking.
    s.headers.update({"User-Agent": "OpticTerminal/1.0 (research tool; +https://theopticterminal.com)"})
    return s


def _cache_path(year: int, doc: str) -> str:
    return os.path.join(CACHE_DIR, str(year), "%s.pdf" % doc)


def _fetch_index(year: int, sess: requests.Session) -> List[Dict[str, str]]:
    """The annual index of filings. Small, and the only thing re-read."""
    r = sess.get(HOUSE_INDEX.format(year=year), timeout=TIMEOUT)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        name = next((n for n in z.namelist() if n.lower().endswith(".xml")), None)
        if not name:
            return []
        root = ET.fromstring(z.read(name))
    out = []
    for m in root.findall("Member"):
        if (m.findtext("FilingType") or "").strip() != "P":
            continue          # P is the Periodic Transaction Report
        doc = (m.findtext("DocID") or "").strip()
        if not doc:
            continue
        out.append({
            "doc_id": doc,
            "last": (m.findtext("Last") or "").strip(),
            "first": (m.findtext("First") or "").strip(),
            "prefix": (m.findtext("Prefix") or "").strip(),
            "filed": (m.findtext("FilingDate") or "").strip(),
            "district": (m.findtext("StateDst") or "").strip(),
            "year": str(year),
        })
    return out


def _parse_pdf(path: str) -> Dict[str, Any]:
    """Rows out of one filing. Import is local so a missing pypdf degrades this
    module rather than breaking the import graph of everything that reads it."""
    try:
        from pypdf import PdfReader
    except ImportError:
        return {"member": None, "district": None, "rows": [], "error": "pypdf not installed"}
    try:
        reader = PdfReader(path)
        text = re.sub(r"\s+", " ", "\n".join((p.extract_text() or "") for p in reader.pages))
    except Exception as exc:
        return {"member": None, "district": None, "rows": [], "error": str(exc)[:120]}

    name = _NAME.search(text)
    dist = _DIST.search(text)
    rows = []
    for m in _ROW.finditer(text):
        if m.group("kind") not in _EQUITY_KINDS:
            continue
        tx = m.group("tx")
        rows.append({
            "ticker": m.group("ticker"),
            "asset_kind": m.group("kind"),
            "transaction": _TX_LABEL.get(tx, tx),
            "side": "buy" if tx == "P" else "sell" if tx.startswith("S") else "other",
            "traded": m.group("date"),
            "notified": m.group("notified"),
            "amount_low": int(m.group("low").replace(",", "")),
            "amount_high": int(m.group("high").replace(",", "")),
        })
    return {"member": name.group(1) if name else None,
            "district": dist.group(1) if dist else None,
            "rows": rows, "error": None}


def _member_name(entry: Dict[str, str], from_pdf: Optional[str]) -> str:
    """The filer's name, from the structured index rather than the PDF header.

    Both carry the same stutter where the Clerk's record has one: doc 20035450
    is filed under `First: "Scott Scott", Last: "Franklin"` in the index and
    prints as "Hon. Scott Scott Franklin" on the form. The duplication is in
    the government's own data, so this is not a parsing artifact -- but a
    reader who sees it will reasonably conclude the terminal is broken, so an
    immediately repeated word is collapsed. Only consecutive repeats, which is
    what a stutter is; "William Williams" keeps both.
    """
    name = " ".join(x for x in (entry.get("prefix"), entry.get("first"),
                                entry.get("last"), entry.get("suffix")) if x).strip()
    name = name or (from_pdf or "").strip()
    name = re.sub(r"\b(\w+)(\s+\1\b)+", r"\1", name)
    # And an honorific filed into the wrong column: the index carries
    # `First: "John J Mr", Last: "McGuire"`. Stripped only after the first
    # token, so the leading "Hon." the Clerk puts in Prefix survives.
    head, _, rest = name.partition(" ")
    rest = re.sub(r"\b(?:Mr|Mrs|Ms|Dr|Hon|Rep|Sen)\.?\b", " ", rest)
    return re.sub(r"\s{2,}", " ", (head + " " + rest)).strip()


def _iso(us_date: str) -> Optional[str]:
    try:
        return datetime.strptime(us_date, "%m/%d/%Y").date().isoformat()
    except Exception:
        return None


def _disclosure_lag(traded: str, notified: str) -> Optional[int]:
    a, b = _iso(traded), _iso(notified)
    if not a or not b:
        return None
    return (datetime.fromisoformat(b) - datetime.fromisoformat(a)).days


def refresh(year: Optional[int] = None, budget: Optional[int] = None) -> Dict[str, Any]:
    """Pull the index, then up to `budget` filings not already on disk.

    Returns what is parseable now rather than waiting for the whole backlog:
    a partial answer from a public record is more useful than a spinner, and
    the next refresh continues where this one stopped.
    """
    year = year or datetime.now(timezone.utc).year
    budget = FETCH_BUDGET if budget is None else budget
    sess = _session()
    os.makedirs(os.path.join(CACHE_DIR, str(year)), exist_ok=True)

    try:
        index = _fetch_index(year, sess)
    except Exception as exc:
        log.warning("congress index unavailable: %s", exc)
        return {"available": False, "reason": "The House disclosure index could not be read.",
                "source": SOURCE_PAGE}

    fetched = 0
    for entry in sorted(index, key=lambda e: _iso(e["filed"]) or "", reverse=True):
        path = _cache_path(year, entry["doc_id"])
        if os.path.exists(path):
            continue
        if fetched >= budget:
            break
        try:
            r = sess.get(HOUSE_PTR.format(year=year, doc=entry["doc_id"]), timeout=TIMEOUT)
            if r.status_code != 200 or not r.content.startswith(b"%PDF"):
                continue
            with open(path, "wb") as fh:
                fh.write(r.content)
            fetched += 1
            time.sleep(REQUEST_GAP)
        except Exception as exc:
            log.warning("congress filing %s: %s", entry["doc_id"], exc)

    trades: List[Dict[str, Any]] = []
    parsed = 0
    for entry in index:
        path = _cache_path(year, entry["doc_id"])
        if not os.path.exists(path):
            continue
        out = _parse_pdf(path)
        if out.get("error") and not out["rows"]:
            continue
        parsed += 1
        member = _member_name(entry, out["member"])
        for row in out["rows"]:
            trades.append({
                **row,
                "member": member,
                "district": out["district"] or entry["district"],
                "filed": _iso(entry["filed"]),
                "traded_iso": _iso(row["traded"]),
                "disclosure_lag_days": _disclosure_lag(row["traded"], row["notified"]),
                "doc_id": entry["doc_id"],
                "source_url": HOUSE_PTR.format(year=year, doc=entry["doc_id"]),
            })

    trades.sort(key=lambda t: (t["traded_iso"] or "", t["filed"] or ""), reverse=True)
    with _LOCK:
        _MEM.update(at=time.time(), trades=trades, index_at=datetime.now(timezone.utc).isoformat(),
                    parsed=parsed, known=len(index))
    return summary()


def _matches(trade: Dict[str, Any], *, member: Optional[str], side: Optional[str],
             since: Optional[str], until: Optional[str]) -> bool:
    """One row against one filter set.

    Every test is skipped when its filter is absent, so an empty filter set
    matches everything and the unfiltered call costs one pass instead of a
    special case.
    """
    if member:
        # Substring, case-folded. The filed name carries an honorific and a
        # suffix ("Hon. Richard Dean McCormick"), so an exact match would only
        # ever be produced by clicking a name rather than typing one.
        if member.casefold() not in (trade.get("member") or "").casefold():
            return False
    if side and trade.get("side") != side:
        return False
    # ISO dates compare correctly as strings, which is the whole reason
    # traded_iso exists beside the filer's US-format `traded`.
    traded = trade.get("traded_iso")
    if since and (not traded or traded < since):
        return False
    if until and (not traded or traded > until):
        return False
    return True


def _activity(trades: List[Dict[str, Any]], days: int) -> List[Dict[str, Any]]:
    """Trades per day, split by direction, newest day last.

    Keyed on the TRADE date rather than the disclosure date. Both are real and
    they answer different questions -- when it happened, versus when anyone
    could have known -- and this is the one that lines up with a price chart,
    which is what the rest of the row is for. The gap between the two is
    reported separately as the disclosure lag.

    Every day in the window is emitted, including the empty ones: a bar chart
    that silently drops quiet days compresses a fortnight of nothing into the
    same width as a busy week and makes a cluster look like a trend.
    """
    if days <= 0:
        return []
    dated = [t for t in trades if t.get("traded_iso")]
    if not dated:
        return []
    last = max(t["traded_iso"] for t in dated)
    try:
        end = datetime.strptime(last, "%Y-%m-%d").date()
    except ValueError:
        return []
    start = end - timedelta(days=days - 1)
    buckets: Dict[str, Dict[str, int]] = {}
    for offset in range(days):
        key = (start + timedelta(days=offset)).isoformat()
        buckets[key] = {"date": key, "buys": 0, "sells": 0, "other": 0}
    for t in dated:
        row = buckets.get(t["traded_iso"])
        if row is None:
            continue            # older than the window
        side = t.get("side")
        row["buys" if side == "buy" else "sells" if side == "sell" else "other"] += 1
    return [buckets[k] for k in sorted(buckets)]


def _top_tickers(trades: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    """Most-disclosed symbols, with the direction split each one carries.

    Ranked by disclosure COUNT rather than by amount. Amounts are bands, so a
    ranking by money would be a ranking by the width of a band somebody else
    chose -- and a single $1M-$5M sale would outrank ten separate purchases
    that tell you far more about what a committee is doing.
    """
    tally: Dict[str, Dict[str, Any]] = {}
    for t in trades:
        sym = t.get("ticker")
        if not sym:
            continue
        row = tally.setdefault(sym, {"ticker": sym, "count": 0, "buys": 0, "sells": 0,
                                     "other": 0, "members": set()})
        row["count"] += 1
        side = t.get("side")
        row["buys" if side == "buy" else "sells" if side == "sell" else "other"] += 1
        if t.get("member"):
            row["members"].add(t["member"])
    out = sorted(tally.values(), key=lambda r: (-r["count"], r["ticker"]))[:limit]
    # The set was only ever a counter; it must not reach JSON.
    return [{**r, "members": len(r["members"])} for r in out]


def summary(ticker: Optional[str] = None, limit: int = 60, *,
            member: Optional[str] = None, side: Optional[str] = None,
            since: Optional[str] = None, until: Optional[str] = None,
            activity_days: int = 30, top: int = 6) -> Dict[str, Any]:
    """What is parsed right now. Never fetches -- callers decide when to spend.

    The filters are keyword-only. This function already had two positional
    parameters and gained five; earlier this session a third positional flag
    added to a different function bound itself to the argument after it and
    shipped a panel reading "not requested". Keyword-only makes that
    impossible rather than unlikely.

    Every count below is over the FILTERED set, not the whole archive. A
    reader who has narrowed to one member and one month is asking what that
    slice contains, and a total that ignored the filter would be answering a
    question nobody asked -- while looking authoritative.
    """
    with _LOCK:
        trades = list(_MEM["trades"])
        parsed, known, at = _MEM["parsed"], _MEM["known"], _MEM["index_at"]
    if ticker:
        want = ticker.upper().strip()
        trades = [t for t in trades if t["ticker"] == want]
    if member or side or since or until:
        trades = [t for t in trades
                  if _matches(t, member=member, side=side, since=since, until=until)]
    shown = trades[:limit]
    buys = sum(1 for t in trades if t["side"] == "buy")
    sells = sum(1 for t in trades if t["side"] == "sell")
    lags = sorted(t["disclosure_lag_days"] for t in trades
                  if t.get("disclosure_lag_days") is not None)
    filed = [t["filed"] for t in trades if t.get("filed")]
    return {
        "available": bool(trades) or parsed > 0,
        "trades": shown,
        "count": len(trades),
        "buys": buys,
        "sells": sells,
        # Neither a buy nor a sell: exchanges and the like. Reported rather
        # than folded into either side, for the same reason an insider
        # exercise is not a purchase.
        "other": len(trades) - buys - sells,
        "activity": _activity(trades, activity_days),
        "activity_days": activity_days,
        "top_tickers": _top_tickers(trades, top),
        "members": len({t["member"] for t in trades if t.get("member")}),
        "symbols": len({t["ticker"] for t in trades if t.get("ticker")}),
        # The middle of the lag distribution, not the mean: there is a filing
        # in the live archive disclosed 476 days after the trade, and one of
        # those drags a mean away from anything a reader would recognise.
        #
        # statistics.median rather than `lags[len // 2]`, which is the
        # upper-middle on an even count and not the median. Rounded, because a
        # half day is not a unit this data has.
        "lag_median": round(statistics.median(lags)) if lags else None,
        "lag_max": lags[-1] if lags else None,
        "latest_filed": max(filed) if filed else None,
        "latest_traded": max((t["traded_iso"] for t in trades if t.get("traded_iso")),
                             default=None),
        # A band per trade means the total is a band. Reported as two numbers
        # rather than a midpoint, because a midpoint is a figure nobody filed.
        "amount_low": sum(t["amount_low"] for t in trades),
        "amount_high": sum(t["amount_high"] for t in trades),
        "filings_parsed": parsed,
        "filings_known": known,
        "complete": parsed >= known and known > 0,
        "index_at": at,
        "source": SOURCE_PAGE,
        "chamber": "house",
        "caveat": ("Amounts are the bands the filer reported, never exact figures. "
                   "A trade may be disclosed up to 45 days after it happened, so the "
                   "gap between the trade date and the notification date is shown per "
                   "row. House filings only: the Senate publishes no comparable archive."),
    }


def stale(ttl: float = INDEX_TTL) -> bool:
    with _LOCK:
        return (time.time() - float(_MEM["at"])) > ttl
