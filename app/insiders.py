"""Form 4 filings as they arrive, across the whole market.

The terminal already showed insider transactions for one loaded ticker, from
yfinance, with a date and no time. This is the other question: who is buying
anything, right now. It comes from the filings themselves.

**Why the primary source and not a feed of it.** EDGAR publishes every Form 4 the
moment it is accepted, with the acceptance timestamp to the second, and the form
itself carries the issuer's ticker, the insider's name and role, the transaction
date, the code, the share count and the price. A vendor feed of the same thing
is that data with a delay and a subscription in front of it.

**A grant is not a purchase, and this is the whole reason the module is careful.**
Form 4 code `A` is an award: shares handed over as compensation. Code `P` is an
open-market purchase, someone spending their own money. Presenting the first as
an "insider buy" is the single most misleading thing this panel could do — the
first Form 4 read while building this was a 51,606-share award at a price of
$0.00, which as a "buy" would read as enormous conviction and is in fact a
payslip. Every row carries its code, its meaning in words, and whether it was a
purchase, a disposal or neither, and the default view is open-market only.

**The cost, and how it is paid.** The index feed is one request. Each filing is a
second request of about 4KB. Forty filings would be forty requests at a polite
gap, which is half a minute, so enrichment is capped per call and cached
per accession forever: a filing never changes after it is accepted. The first
call returns the handful it managed and says how many are still unread; the next
one picks up where it stopped. Nothing here blocks a page on a cold cache.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from . import feeds

log = logging.getLogger(__name__)

# EDGAR's live filing index. `owner=only` is what restricts it to ownership
# forms: measured, `type=4` alone returns 424B2 prospectuses and 485BXT fund
# filings, 36 of 40 rows on the run that found it.
INDEX_URL = ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4"
             "&owner=only&count={count}&output=atom")

# The index moves constantly; two minutes is fresh enough for a page and far
# inside EDGAR's tolerance.
INDEX_TTL = 120
# A filing is immutable once accepted, so its parse is cached for a week and
# only evicted by the cache's own size limit.
FILING_TTL = 7 * 86400

# How many unread filings one request will fetch. Twelve at the module's polite
# gap is about seven seconds, which is the most a panel should ever cost.
ENRICH_BUDGET = int(os.environ.get("INSIDER_ENRICH_BUDGET", "12"))
INDEX_COUNT = int(os.environ.get("INSIDER_INDEX_COUNT", "100"))
# browse-edgar is a CGI script rather than a static file and is slower than the
# feed module's twelve-second default, which reported it as down on a cold call.
INDEX_TIMEOUT = float(os.environ.get("INSIDER_INDEX_TIMEOUT", "30"))

# Form 4 transaction codes, in the SEC's own vocabulary.
#
# `buy` is deliberately true for P alone. Everything else is either
# compensation, a mechanical consequence of compensation, or a transfer.
CODES: Dict[str, Dict[str, Any]] = {
    "P": {"label": "Open-market purchase", "buy": True,
          "note": "Bought on the open market with their own money."},
    "S": {"label": "Open-market sale", "buy": False,
          "note": "Sold on the open market. Often scheduled in advance under a "
                  "10b5-1 plan, which the filing may or may not say."},
    "A": {"label": "Grant or award", "buy": False,
          "note": "Shares granted as compensation, frequently at a stated price "
                  "of zero. Not a purchase and not a signal of conviction."},
    "M": {"label": "Option exercise", "buy": False,
          "note": "An option converted into shares at its strike. A decision "
                  "about an expiry date more often than about the price."},
    "F": {"label": "Shares withheld for tax", "buy": False,
          "note": "Shares surrendered to cover the tax on a grant. Mechanical."},
    "D": {"label": "Disposition to the issuer", "buy": False, "note": ""},
    "G": {"label": "Gift", "buy": False, "note": ""},
    "C": {"label": "Conversion", "buy": False, "note": ""},
    "X": {"label": "In-the-money option exercise", "buy": False, "note": ""},
    "J": {"label": "Other", "buy": False,
          "note": "The filer chose 'other' and the explanation is in the "
                  "footnotes, which this does not read."},
}

# Module constants rather than inline strings, so a test can assert the value
# instead of searching the source. CLAUDE.md records why that matters: an
# implicitly-concatenated Python string is not in the file as one string, so a
# source search for "two business days" finds nothing while the sentence reads
# perfectly on the page.
METHOD = ("Form 4 filings from EDGAR's live index, read in full. The timestamp "
          "is EDGAR's own acceptance time; the transaction date is the one the "
          "insider reported. Codes are the SEC's.")

BLIND = ("Only what has been filed. An insider has two business days to report, "
         "so today's list is mostly last week's trades, and nothing here says "
         "whether a sale was scheduled in advance under a 10b5-1 plan unless "
         "the filer's footnotes say so, which this does not read.")

_ATOM = "{http://www.w3.org/2005/Atom}"


def _text(node: Optional[ET.Element], path: str) -> Optional[str]:
    if node is None:
        return None
    found = node.find(path)
    if found is None or found.text is None:
        return None
    value = found.text.strip()
    return value or None


def _num(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out else None


def _accession(url: str) -> Optional[str]:
    """The accession number out of an index URL."""
    hit = re.search(r"(\d{10}-\d{2}-\d{6})", url or "")
    return hit.group(1) if hit else None


def index(count: int = INDEX_COUNT, force: bool = False) -> Dict[str, Any]:
    """The newest Form 4 filings: accession, issuer, and when it was accepted."""
    url = INDEX_URL.format(count=max(10, min(int(count), 100)))
    try:
        body = feeds.fetch_text(url, 0 if force else INDEX_TTL,
                                key="insider:index", timeout=INDEX_TIMEOUT)
    except Exception as exc:                                 # noqa: BLE001
        return {"available": False,
                "reason": "EDGAR's filing index did not answer ({}).".format(
                    type(exc).__name__),
                "rows": []}

    rows: List[Dict[str, Any]] = []
    try:
        root = ET.fromstring(body.encode("utf-8", "replace"))
    except ET.ParseError:
        return {"available": False,
                "reason": "EDGAR's filing index returned something that is not a feed.",
                "rows": []}

    # EDGAR lists one filing once per party: the issuer as "(Filer)" and the
    # insider as "(Reporting)", same accession, same timestamp. Without this
    # every transaction rendered twice — measured, eight filings read produced
    # sixteen index rows and every row on the panel appeared in a pair.
    seen: set = set()
    for entry in root.findall(_ATOM + "entry"):
        title = (entry.findtext(_ATOM + "title") or "").strip()
        updated = (entry.findtext(_ATOM + "updated") or "").strip()
        link_el = entry.find(_ATOM + "link")
        href = (link_el.get("href") if link_el is not None else "") or ""
        acc = _accession(href)
        if not acc:
            continue
        # "4 - COMPANY NAME (0001234567) (Reporting)"
        form = title.split(" - ", 1)[0].strip()
        if form not in ("4", "4/A"):
            continue
        if acc in seen:
            continue
        seen.add(acc)
        rows.append({
            "accession": acc,
            "form": form,
            "filed_at": updated or None,
            "index_url": href,
            "title": title,
        })
    return {"available": True, "rows": rows}


def _filing_folder(index_url: str) -> str:
    return index_url.rsplit("/", 1)[0]


def parse_filing(index_url: str, accession: str) -> Dict[str, Any]:
    """One Form 4, as transactions.

    Reads the complete submission text file rather than listing the folder and
    then fetching the XML: the XML's filename is unpredictable
    ("wk-form4_1789056227.xml"), so the folder listing was a second request per
    filing for nothing. The submission wraps the XML in SGML, which is why the
    document is sliced out by tag rather than parsed whole.
    """
    url = "{}/{}.txt".format(_filing_folder(index_url), accession)
    body = feeds.fetch_text(url, FILING_TTL, key="insider:doc:" + accession)

    start = body.find("<ownershipDocument>")
    end = body.find("</ownershipDocument>")
    if start < 0 or end < 0:
        return {"available": False, "reason": "no ownership document in the submission"}
    try:
        root = ET.fromstring(body[start:end + len("</ownershipDocument>")])
    except ET.ParseError as exc:
        return {"available": False, "reason": "unparsable Form 4 ({})".format(exc)}

    issuer = root.find("issuer")
    owner = root.find("reportingOwner")
    rel = root.find("reportingOwner/reportingOwnerRelationship")

    roles = []
    if rel is not None:
        if (_text(rel, "isDirector") or "0") in ("1", "true"):
            roles.append("Director")
        if (_text(rel, "isOfficer") or "0") in ("1", "true"):
            roles.append(_text(rel, "officerTitle") or "Officer")
        if (_text(rel, "isTenPercentOwner") or "0") in ("1", "true"):
            roles.append("10% owner")
        other = _text(rel, "otherText")
        if other:
            roles.append(other)

    out: Dict[str, Any] = {
        "available": True,
        "accession": accession,
        "ticker": (_text(issuer, "issuerTradingSymbol") or "").upper() or None,
        "issuer": _text(issuer, "issuerName"),
        "insider": _text(owner, "reportingOwnerId/rptOwnerName"),
        "roles": roles,
        "transactions": [],
    }

    for kind, path in (("share", "nonDerivativeTable/nonDerivativeTransaction"),
                       ("derivative", "derivativeTable/derivativeTransaction")):
        for tx in root.findall(path):
            code = (_text(tx, "transactionCoding/transactionCode")
                    or _text(tx, "transactionCoded/transactionCode") or "").upper()
            meta = CODES.get(code) or {"label": "Code " + (code or "?"),
                                       "buy": False, "note": ""}
            shares = _num(_text(tx, "transactionAmounts/transactionShares/value"))
            price = _num(_text(tx, "transactionAmounts/transactionPricePerShare/value"))
            ad = (_text(tx, "transactionAmounts/transactionAcquiredDisposedCode/value")
                  or "").upper()
            out["transactions"].append({
                "kind": kind,
                "security": _text(tx, "securityTitle/value"),
                "date": _text(tx, "transactionDate/value"),
                "code": code or None,
                "code_label": meta["label"],
                "code_note": meta["note"],
                "is_purchase": bool(meta["buy"]),
                "acquired": ad == "A",
                "shares": shares,
                "price": price,
                # Zero-price grants would otherwise report a $0 value, which
                # reads as a data fault rather than as compensation.
                "value": (round(shares * price, 2)
                          if shares is not None and price else None),
                "shares_after": _num(
                    _text(tx, "postTransactionAmounts/sharesOwnedFollowingTransaction/value")),
            })
    return out


def latest(limit: int = 40, only_purchases: bool = True, force: bool = False,
           budget: int = ENRICH_BUDGET) -> Dict[str, Any]:
    """Recent Form 4 transactions across the market, newest filing first."""
    idx = index(force=force)
    if not idx.get("available"):
        return {"available": False, "reason": idx.get("reason"), "rows": [],
                "codes": CODES}

    listed = idx["rows"]
    rows: List[Dict[str, Any]] = []
    fetched = 0
    unread = 0
    failed = 0

    for entry in listed:
        acc = entry["accession"]
        cached = feeds.cached_json("insider:parsed:" + acc)
        parsed = cached
        if parsed is None:
            if fetched >= max(0, int(budget)):
                unread += 1
                continue
            fetched += 1
            try:
                parsed = parse_filing(entry["index_url"], acc)
            except Exception as exc:                         # noqa: BLE001
                log.info("insiders: %s failed (%s)", acc, exc)
                failed += 1
                continue
            # Stored even when the parse failed, so a malformed filing is not
            # refetched on every poll for a week.
            feeds.store_json("insider:parsed:" + acc, parsed, )
        if not parsed.get("available"):
            failed += 1
            continue

        for tx in parsed.get("transactions", []):
            rows.append({
                "accession": acc,
                "filed_at": entry.get("filed_at"),
                "form": entry.get("form"),
                "index_url": entry.get("index_url"),
                "ticker": parsed.get("ticker"),
                "issuer": parsed.get("issuer"),
                "insider": parsed.get("insider"),
                "roles": parsed.get("roles") or [],
                **tx,
            })

    if only_purchases:
        rows = [r for r in rows if r.get("is_purchase")]

    # Filing time first, transaction date second. Both are shown because they
    # are different facts: a purchase made on Monday and filed on Wednesday is
    # news on Wednesday.
    rows.sort(key=lambda r: (r.get("filed_at") or "", r.get("date") or ""), reverse=True)

    return {
        "available": True,
        "rows": rows[:max(1, min(int(limit), 200))],
        "matched": len(rows),
        "filings_listed": len(listed),
        "filings_read": len(listed) - unread - failed,
        "filings_unread": unread,
        "filings_failed": failed,
        "fetched_now": fetched,
        "only_purchases": bool(only_purchases),
        "codes": {k: {"label": v["label"], "buy": v["buy"], "note": v["note"]}
                  for k, v in CODES.items()},
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": METHOD,
        "blind_spot": BLIND,
    }
