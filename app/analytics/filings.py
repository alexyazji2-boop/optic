"""Recent SEC filings for one company, from EDGAR.

The market-wide 8-K feed was removed from the Read tab deliberately — a firehose
of every filer's disclosures is not a daily read. Per-ticker is a different
question: when you are looking at one name, "what has this company actually filed
lately" is exactly the kind of primary source that beats an article about it.

Two things make this worth having over a news feed. The filing is the company's
own account, so there is no publisher between the reader and the document. And an
8-K item code is the filer's own classification — item 2.02 *is* results of
operations, not somebody's guess at what the filing was about.

Requires a contact address in the User-Agent. Measured against sec.gov, a
User-Agent containing an email returns 200 from /Archives while one without
returns 403, so FEED_CONTACT is not optional here.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .. import feeds

# EDGAR's ticker directory. Small, stable, and cached for a day — the mapping only
# changes when a company lists, delists or changes symbol.
TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
TICKER_MAP_TTL = 86400

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SUBMISSIONS_TTL = 3600

# Forms worth showing a reader looking at a chart, and what they are in English.
# Anything not listed is dropped: the full feed is dominated by Form 4s and 13F
# housekeeping, which bury the two filings a month that actually say something.
FORM_LABELS = {
    "8-K": "Material event",
    "10-Q": "Quarterly report",
    "10-K": "Annual report",
    "S-1": "Registration",
    "S-3": "Shelf registration",
    "SC 13D": "Activist stake",
    "SC 13G": "Passive stake",
    "DEF 14A": "Proxy statement",
    "425": "Merger communication",
}

# 8-K item codes, so a material event says which kind. Same table the removed
# market-wide feed used; the codes are the filer's own classification.
ITEM_LABELS = {
    "1.01": "material agreement signed",
    "1.02": "material agreement terminated",
    "2.01": "completion of an acquisition or disposal",
    "2.02": "results of operations",
    "2.03": "new debt obligation",
    "3.01": "listing or compliance notice",
    "4.01": "change of auditor",
    "4.02": "prior financials no longer reliable",
    "5.02": "director or officer change",
    "5.07": "shareholder vote results",
    "7.01": "Regulation FD disclosure",
    "8.01": "other material event",
}

MAX_ROWS = 12

# A filing older than this is history, not news. SPY's most recent listed filing is
# a 1999 SC 13G — correct, because an ETF trust files differently, but rendering
# 27-year-old documents under a "recent filings" heading is the same lie as showing
# a 2017 headline as today's news. Past this age the panel says so instead.
STALE_DAYS = 550


def _cik_for(ticker: str) -> Optional[str]:
    """Zero-padded CIK for a ticker, or None if EDGAR does not list it."""
    blob = feeds.fetch_json(TICKER_MAP_URL, TICKER_MAP_TTL, key="sec:tickers")
    if not isinstance(blob, dict):
        return None
    want = (ticker or "").upper().strip()
    for row in blob.values():
        if isinstance(row, dict) and str(row.get("ticker", "")).upper() == want:
            return str(row.get("cik_str", "")).zfill(10)
    return None


def _describe(form: str, items: str) -> str:
    """One phrase for what a filing is."""
    label = FORM_LABELS.get(form, form)
    codes = [c.strip() for c in (items or "").split(",") if c.strip()]
    named = [ITEM_LABELS[c] for c in codes if c in ITEM_LABELS]
    if named:
        return "{} — {}".format(label, "; ".join(named[:2]))
    return label


def recent(ticker: str, limit: int = MAX_ROWS) -> Dict[str, Any]:
    """The company's recent notable filings, newest first."""
    if not feeds.CONTACT_OK:
        return {"available": False,
                "reason": "SEC requires a contact address — set FEED_CONTACT in .env"}

    try:
        cik = _cik_for(ticker)
    except Exception as exc:
        return {"available": False, "reason": "EDGAR ticker directory unavailable: {}".format(exc)}
    if not cik:
        return {"available": False,
                "reason": "{} is not in EDGAR's directory — foreign issuers and most "
                          "ETFs file differently or not at all".format(ticker.upper())}

    try:
        sub = feeds.fetch_json(SUBMISSIONS_URL.format(cik=cik), SUBMISSIONS_TTL,
                               key="sec:sub:{}".format(cik))
    except Exception as exc:
        return {"available": False, "reason": "EDGAR filings unavailable: {}".format(exc)}
    if not isinstance(sub, dict):
        return {"available": False, "reason": "EDGAR returned no filing history"}

    rec = (sub.get("filings") or {}).get("recent") or {}
    forms = rec.get("form") or []
    dates = rec.get("filingDate") or []
    items = rec.get("items") or []
    accns = rec.get("accessionNumber") or []
    docs = rec.get("primaryDocument") or []

    rows: List[Dict[str, Any]] = []
    for i, form in enumerate(forms):
        if form not in FORM_LABELS:
            continue
        accn = (accns[i] if i < len(accns) else "").replace("-", "")
        doc = docs[i] if i < len(docs) else ""
        rows.append({
            "form": form,
            "filed": dates[i] if i < len(dates) else None,
            "items": items[i] if i < len(items) else "",
            "what": _describe(form, items[i] if i < len(items) else ""),
            # Link to the document itself, not a search page.
            "url": ("https://www.sec.gov/Archives/edgar/data/{}/{}/{}".format(
                int(cik), accn, doc) if accn and doc else
                "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={}"
                "&type=&dateb=&owner=include&count=40".format(cik)),
        })
        if len(rows) >= limit:
            break

    # How old is the newest thing here? A filer that stopped filing is a different
    # answer from a filer with nothing new this month, and the reader needs to know
    # which one they are looking at.
    newest_age = None
    if rows and rows[0].get("filed"):
        try:
            newest = datetime.strptime(rows[0]["filed"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            newest_age = (datetime.now(timezone.utc) - newest).days
        except (ValueError, TypeError):
            newest_age = None
    stale = newest_age is not None and newest_age > STALE_DAYS

    if stale:
        return {
            "available": False,
            "cik": cik,
            "company": sub.get("name"),
            "filings": rows,
            "newest_age_days": newest_age,
            "reason": (
                "the newest notable filing is {} years old — this is normal for an "
                "ETF or trust, which files under a different regime, so there is no "
                "recent corporate disclosure to show".format(round(newest_age / 365.0, 1))
            ),
        }

    return {
        "available": bool(rows),
        "cik": cik,
        "company": sub.get("name"),
        "filings": rows,
        "newest_age_days": newest_age,
        "reason": None if rows else "no notable filings in EDGAR's recent window",
        "method": (
            "Straight from EDGAR, newest first. Form 4 insider reports and 13F "
            "holdings are excluded here — they dominate the raw feed and the insider "
            "panel already summarises them. An 8-K's item code is the filer's own "
            "classification of what the filing is about, not an interpretation."
        ),
    }
