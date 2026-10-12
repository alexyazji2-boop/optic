"""What a company does, from its latest annual report on EDGAR.

The Overview's "What does X do?" printed Yahoo's longBusinessSummary under the
note "The description may be out of date", and for Nebius it was: Yahoo's text
read "It offers Nebius builds full-stack infrastructure for AI", a sentence
spliced from two versions, while the 20-F filed on 2026-04-30 opens with what
the company now says it is (reported 2026-10-12: "make sure that it is always
up to date").

So the description comes from the newest 10-K or 20-F the company has filed:
the opening paragraphs of Item 1 (Business) or of Item 4 (Information on the
Company). It is the company's own words, dated, and it changes the day a new
report is filed, because the filing list is read again every few hours. Yahoo's
text stays as the fallback for a symbol with no annual report on EDGAR (funds,
indices, Canadian 40-F filers whose report is an exhibit).

The report is a 1-10MB document, so it is never read inside a request: the
first ask starts a background look and returns nothing, the extract is kept per
accession number (a filing never changes), and the filing list is looked at
again in the background every six hours. The session endpoint that carries
the profile is polled every minute, so the filing's text replaces Yahoo's on
the next poll.
"""
from __future__ import annotations

import html
import logging
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from .. import feeds
from . import sec_facts

log = logging.getLogger("optic")

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
# Shared with app/analytics/segments.py, which reads the same list.
SUBMISSIONS_KEY = "seg:subs:"
SUBMISSIONS_TTL = 6 * 3600
DOC_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{folder}/{doc}"

# Originals only: an amendment is often Part III alone, with no business section.
ANNUAL_FORMS = ("10-K", "20-F")
FORM_NAMES = {"10-K": "annual report (Form 10-K)", "20-F": "annual report (Form 20-F)"}

# Enough to say what the company is; the panel clamps it and offers the rest.
TARGET_CHARS = 700
MAX_PARAGRAPHS = 4

_LOCK = threading.Lock()
_EXTRACTS: Dict[str, Optional[Dict[str, Any]]] = {}   # accession -> extract (None: none found)
_CHECKED: Dict[str, Tuple[float, Optional[Dict[str, Any]]]] = {}   # symbol -> (when, result)
_RUNNING: set = set()                                    # symbols being looked up now


_ITEM = re.compile(r"(?i)^items?\s*\d+[a-z]?\b")


def _blocks(raw: str) -> List[str]:
    """The document as one line per paragraph, cell or heading."""
    raw = re.sub(r"(?is)<(script|style|ix:header)\b.*?</\1>", " ", raw)
    raw = re.sub(r"(?i)</(p|div|tr|li|h\d|table)>", "\n", raw)
    raw = re.sub(r"(?i)<br\s*/?>", "\n", raw)
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw)).replace("\xa0", " ")
    lines = [" ".join(line.split()) for line in text.split("\n") if line.strip()]
    # A paragraph broken across a page or a styled span arrives as two lines,
    # the first without its full stop; TSMC's and Alibaba's overviews were
    # read from the second half ("TSMC 3DFabric advanced silicon stacking...").
    # A long line that does not end a sentence is joined to the one after it.
    out: List[str] = []
    for line in lines:
        if out and len(out[-1]) >= 60 and out[-1][-1:] not in ".:;!?)”\"" and not _ITEM.match(line):
            out[-1] = out[-1] + " " + line
        else:
            out.append(line)
    return out


# A 20-F is laid out in more ways than a 10-K: ASML, TSMC and Alibaba each set
# Item 4 differently ("Information on the Company" alone in a cell, "ITEM 4.
# INFORMATION ON THE COMPANY", "B. Business Overview", "Business Overview of
# the Company"), and Item 4 often opens with A, the company's history. So the
# Business Overview heading is looked for first and Item 4 is the fallback.
_HEADS = {
    "10-K": [re.compile(r"(?i)^items?\s*1\s*(and\s*2)?\s*[.:\-–—]?\s*business\b")],
    "20-F": [re.compile(r"(?i)^(item\s*)?(4\.?\s*)?(b\s*[.:\-–—]\s*)?business\s+overview(\s+of\s+the\s+company)?\s*\.?$"),
             re.compile(r"(?i)^(item\s*4\s*[.:\-–—]?\s*)?information\s+on\s+the\s+company\s*\.?$")],
}

# Paragraphs about the document rather than the business ("When used in this
# report, the terms we, us...", PepsiCo), and the fiscal-year housekeeping
# sentence ("The Company's fiscal year is the 52- or 53-week period", Apple).
_ABOUT_THE_REPORT = re.compile(
    r"(?i)\b(this|the)\s+(annual\s+)?report\b|\bform\s+(10-k|20-f)\b|forward-looking|"
    r"^(unless the context|as used (herein|in this)|references to|reference is made)|\bon pages?\s+\d")
_FISCAL_YEAR = re.compile(r"(?i)[^.]*\bfiscal year (is|ends|end)\b[^.]*\.\s*")
MAX_CHARS = 1200


def _prose(line: str) -> bool:
    return len(line) >= 80 and line[-1:] in ".:;)”\"" and not _ITEM.match(line)


def _clean(text: str) -> str:
    text = re.sub(r"\s*[®™℠]", "", text)
    text = re.sub(r"\s+([,.;:])", r"\1", text)
    return text.strip()


def extract(raw: str, form: str) -> Optional[str]:
    """The opening of the business section, or None if it cannot be found."""
    lines = _blocks(raw)
    # The table of contents names the section too, so every heading that is
    # followed by prose is a candidate, and the first one that reads as an
    # overview wins: a contents entry runs into the next item and gives none.
    for head in _HEADS.get(form, []):
        for i, line in enumerate(lines):
            if len(line) < 90 and head.match(line) and any(_prose(x) for x in lines[i + 1:i + 16]):
                text = _overview(lines, i + 1)
                if text:
                    return text
    return None


def _overview(lines: List[str], start: int) -> Optional[str]:
    """The first few paragraphs of prose from `start`, up to the next item."""
    out: List[str] = []
    for line in lines[start:start + 200]:
        if _ITEM.match(line):
            break
        if _prose(line):
            if _ABOUT_THE_REPORT.search(line):
                continue
            para = _clean(_FISCAL_YEAR.sub("", line))
            if len(para) < 60:
                continue
            out.append(para)
            if len(out) >= MAX_PARAGRAPHS or sum(map(len, out)) >= TARGET_CHARS:
                break
        elif out and (len(out) >= 2 or sum(map(len, out)) >= TARGET_CHARS):
            break   # a sub-heading after enough prose: the overview is over
    text = "\n\n".join(out)
    if len(text) > MAX_CHARS:
        # Cut at the last full sentence that fits.
        cut = max(text.rfind(". ", 0, MAX_CHARS), text.rfind(".\n", 0, MAX_CHARS))
        text = text[:cut + 1] if cut > 200 else text[:MAX_CHARS].rstrip() + "…"
    return text if len(text) >= 120 else None


def _latest_annual(cik: str) -> Optional[Dict[str, str]]:
    blob = feeds.fetch_json(SUBMISSIONS_URL.format(cik=cik), SUBMISSIONS_TTL,
                            key=SUBMISSIONS_KEY + cik)
    recent = ((blob or {}).get("filings") or {}).get("recent") or {}
    cols = {k: recent.get(k) or [] for k in ("form", "accessionNumber", "primaryDocument",
                                              "filingDate", "reportDate")}
    for i, form in enumerate(cols["form"]):        # newest first, as EDGAR lists them
        if form in ANNUAL_FORMS:
            try:
                acc, doc = cols["accessionNumber"][i], cols["primaryDocument"][i]
            except IndexError:
                return None
            if not acc or not doc:
                return None
            return {"form": form, "accession": acc,
                    "filed": cols["filingDate"][i] if i < len(cols["filingDate"]) else None,
                    "period": cols["reportDate"][i] if i < len(cols["reportDate"]) else None,
                    "url": DOC_URL.format(cik=int(cik), folder=acc.replace("-", ""), doc=doc)}
    return None


def _read(filing: Dict[str, str]) -> Optional[Dict[str, Any]]:
    acc = filing["accession"]
    with _LOCK:
        if acc in _EXTRACTS:
            return _EXTRACTS[acc]
    raw = feeds.fetch_text(filing["url"], 0, key="biz:doc:" + acc, timeout=40, store=False)
    text = extract(raw, filing["form"])
    found = dict(filing, text=text, form_name=FORM_NAMES[filing["form"]]) if text else None
    with _LOCK:
        _EXTRACTS[acc] = found
    return found


def _refresh(symbol: str) -> None:
    """Find the newest annual report and read it; never raises."""
    result: Optional[Dict[str, Any]] = None
    ok = False
    try:
        cik = sec_facts.cik_for(symbol)
        filing = _latest_annual(cik) if cik else None
        result = _read(filing) if filing else None
        ok = True
    except Exception as exc:                                  # noqa: BLE001
        log.info("business description: %s unread (%s)", symbol, exc)
    with _LOCK:
        _RUNNING.discard(symbol)
        if ok:
            _CHECKED[symbol] = (time.time(), result)


def latest(ticker: str, wait: bool = False) -> Optional[Dict[str, Any]]:
    """The latest annual report's description for `ticker`, or None.

    Never touches the network on the caller's thread unless `wait`: what was
    found last is returned at once, and when that is older than the filing
    list's TTL (or missing) a background thread looks again. None until the
    first look lands, and for a symbol with no 10-K or 20-F on EDGAR."""
    symbol = (ticker or "").upper().strip()
    if not symbol or not feeds.CONTACT_OK:
        return None
    with _LOCK:
        checked = _CHECKED.get(symbol)
        stale = checked is None or time.time() - checked[0] > SUBMISSIONS_TTL
        start = stale and symbol not in _RUNNING
        if start:
            _RUNNING.add(symbol)
    if start:
        if wait:
            _refresh(symbol)
        else:
            threading.Thread(target=_refresh, args=(symbol,), daemon=True,
                             name="biz-" + symbol).start()
    with _LOCK:
        checked = _CHECKED.get(symbol)
    return checked[1] if checked else None
