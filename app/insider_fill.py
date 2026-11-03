"""The insider trades Yahoo's list leaves out, read from the SEC's own Form 4 filings.

**What went wrong.** The chart marks insider purchases and sales from the Form 4 rows Yahoo Finance lists, and the
provider asks for two years of them (`providers/yf.py insiders`). Yahoo stops at its 150 latest rows. For a company
that files many awards that is well short of two years, and the rows that fall off are the older ones, whatever
they are. Measured on 29 symbols on 2026-11-03: 7 lists stood at exactly 150 rows and began between 10 and 20
months back. UNH's began on 2025-06-24 and held 146 awards and 4 sales, so the chart showed sales only, and the
executives' open-market purchases of May 2025 were not in Optic at all. A sale is the common case and a purchase
the rare one, so a list cut short loses the purchases first, and the chart read as "insiders only sell".

**What this does.** When Yahoo's list is full and starts inside the two years, the stretch before its oldest row is
read from EDGAR: the company's list of filings (one request to data.sec.gov), then each Form 4 filed in that
stretch (one request each, about 4KB). Only open-market purchases (code P) and sales (code S) of the company's own
shares are kept, which are what Yahoo's "Purchase" and "Sale" rows are; awards, exercises, tax withholding and
gifts are not trades (see `app/insiders.py CODES`). A filing never changes once accepted, so each is read once and
kept in `app/form4_store.py`.

**What it costs, and when.** Nothing on the page's request: `complete` only reads what is kept and, when filings
are unread, starts one background reader. That reads the newest unread filings first, at most RUN_BUDGET a run,
one company at a time, a second apart on top of the feed module's polite gap, and stops at the first run of
refusals, so the next visit resumes where it stopped. UNH's missing stretch was 96 filings: about two and a half
minutes once, then nothing.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from . import feeds, form4_store, insiders as insiders_mod

log = logging.getLogger(__name__)

# Yahoo's insider list holds its latest 150 rows (measured, 2026-11-03): a list this long may be cut short.
YAHOO_ROWS = 150
# The span the chart draws insider trades over, as the provider asks Yahoo for it.
DAYS = 730
# A company's list of filings changes when it files; read again after twelve hours.
LIST_TTL = 12 * 3600
# A Form 4 is due two business days after the trade. Filings this many days after Yahoo's oldest row can still
# report a trade from before it, so they are read too.
LAG_DAYS = 7
RUN_BUDGET = int(os.environ.get("INSIDER_FILL_BUDGET", "200"))
FILL_GAP_SECONDS = float(os.environ.get("INSIDER_FILL_GAP", "1.0"))
ENABLED = os.environ.get("INSIDER_SEC_FILL", "1") != "0"

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
OLDER_URL = "https://data.sec.gov/submissions/{name}"
ARCHIVE_INDEX = "https://www.sec.gov/Archives/edgar/data/{cik}/{folder}/{accession}-index.htm"

TRADE_CODES = {"P": "purchase", "S": "sale"}

_RUNNING: set = set()
_RUNNING_LOCK = threading.Lock()
_ONE_AT_A_TIME = threading.Lock()


def _today() -> dt.date:
    return dt.datetime.now(dt.timezone.utc).date()


def _plus(day: str, n: int) -> str:
    return (dt.date.fromisoformat(day) + dt.timedelta(days=n)).isoformat()


def gap(trades: List[Dict[str, Any]], today: Optional[dt.date] = None) -> Optional[Tuple[str, str]]:
    """(since, until) when Yahoo's list is full and starts inside the two years: the stretch before its oldest
    row, which it does not cover. None when the list is whole."""
    if len(trades) < YAHOO_ROWS:
        return None
    since = ((today or _today()) - dt.timedelta(days=DAYS)).isoformat()
    dates = [str(r.get("date") or "")[:10] for r in trades if r.get("date")]
    oldest = min(dates) if dates else ""
    if not oldest or oldest <= since:
        return None
    return since, oldest


def _window(kept: Dict[str, Any], since: str, until: str) -> List[Tuple[str, str]]:
    last = _plus(until, LAG_DAYS)
    return [(acc, filed) for acc, filed in kept.get("filings") or [] if since <= filed <= last]


def _fresh(kept: Optional[Dict[str, Any]], since: str) -> bool:
    if not kept:
        return False
    try:
        age = time.time() - dt.datetime.fromisoformat(kept["fetched_at"]).timestamp()
    except (KeyError, TypeError, ValueError):
        return False
    return age < LIST_TTL and bool(kept.get("reaches")) and kept["reaches"] <= since


def _row(trade: Dict[str, Any], parsed: Dict[str, Any], accession: str) -> Dict[str, Any]:
    """One kept trade in the shape of Yahoo's rows, so every reader of `recent_transactions` takes it as it is."""
    action = TRADE_CODES[trade["code"]]
    price = trade.get("price")
    words = "Purchase" if action == "purchase" else "Sale"
    detail = ("{} at price {:.2f} per share, from the Form 4 filed with the SEC.".format(words, price) if price
              else "{}, from the Form 4 filed with the SEC.".format(words))
    return {"insider": parsed.get("insider") or "", "position": ", ".join(parsed.get("roles") or []),
            "date": trade["date"], "shares": trade.get("shares"), "value": trade.get("value"), "action": action,
            "detail": detail, "source": "sec", "accession": accession}


def complete(ticker: str, insiders: Dict[str, Any], today: Optional[dt.date] = None) -> Dict[str, Any]:
    """`insiders` (the provider's answer) with the stretch Yahoo's list leaves out filled from kept Form 4s.

    Makes no request. Adds `coverage`, which says how far Yahoo's list reaches and how much of the rest has been
    read, and starts the background reader when filings are unread or the company's list is stale."""
    trades = list((insiders or {}).get("transactions") or [])
    stretch = gap(trades, today)
    if stretch is None:
        return insiders
    since, until = stretch
    kept = form4_store.load_list(ticker)
    window = _window(kept, since, until) if kept else []
    parsed = form4_store.load_many(acc for acc, _ in window)
    unread = sum(1 for acc, _ in window if acc not in parsed)
    rows: List[Dict[str, Any]] = []
    for acc, _ in window:
        p = parsed.get(acc)
        # a company's list also holds the filings it makes as an owner of another issuer's shares
        if not p or not p.get("available") or p.get("issuer_cik") != (kept or {}).get("cik"):
            continue
        rows += [_row(t, p, acc) for t in p.get("trades") or [] if since <= t.get("date", "") < until]
    listed = _fresh(kept, since)
    if ENABLED and (unread or not listed):
        start(ticker, until)
    rows.sort(key=lambda r: r["date"], reverse=True)
    out = dict(insiders)
    out["transactions"] = sorted(trades + rows, key=lambda r: str(r.get("date") or ""), reverse=True)
    out["coverage"] = {
        "since": since, "yahoo_from": until, "yahoo_rows": len(trades), "sec_rows": len(rows),
        "sec_filings": len(window), "sec_unread": unread, "listed": bool(kept),
        "complete": bool(kept) and kept.get("reaches") is not None and kept["reaches"] <= since and not unread,
    }
    return out


# ------------------------------------------------------------------------------------------ the reader

def start(ticker: str, until: str) -> bool:
    """One background reader per symbol; False when one is already running. `until` is the date of Yahoo's
    oldest row: the reader reads the filings before it (and LAG_DAYS after)."""
    sym = (ticker or "").upper().strip()
    with _RUNNING_LOCK:
        if not sym or sym in _RUNNING:
            return False
        _RUNNING.add(sym)
    threading.Thread(target=_run, args=(sym, until), name="insider-fill-" + sym, daemon=True).start()
    return True


def _run(ticker: str, until: str) -> None:
    try:
        with _ONE_AT_A_TIME:
            got = fill(ticker, until)
        log.info("insider fill %s: %s", ticker, got)
    except Exception as exc:                                  # noqa: BLE001
        log.info("insider fill %s failed: %s", ticker, exc)
    finally:
        with _RUNNING_LOCK:
            _RUNNING.discard(ticker)


def _form4s(arrays: Dict[str, Any]) -> List[List[str]]:
    keys = zip(arrays.get("accessionNumber") or [], arrays.get("form") or [], arrays.get("filingDate") or [])
    return [[acc, filed] for acc, form, filed in keys if form in ("4", "4/A")]


def list_filings(ticker: str, since: str) -> Optional[Dict[str, Any]]:
    """The company's Form 4s from EDGAR's submissions, back to `since`: {cik, filings, reaches}, or None when the
    symbol is not an SEC filer. The recent page holds the latest thousand filings of every form; older pages are
    read only while they could hold filings after `since`."""
    from .analytics import sec_facts
    padded = sec_facts.cik_for(ticker)
    if not padded:
        return None
    blob = json.loads(feeds.fetch_text(SUBMISSIONS_URL.format(cik=padded), 0, store=False, timeout=30))
    filings = blob.get("filings") or {}
    recent = filings.get("recent") or {}
    rows = _form4s(recent)
    dates = recent.get("filingDate") or []
    # the earliest date the list is whole from
    reaches = min(dates) if dates else None
    pages = filings.get("files") or []
    if not pages:
        reaches = "0000-00-00"                        # the recent page is the company's whole history
    for page in pages:
        to, frm = str(page.get("filingTo") or ""), str(page.get("filingFrom") or "")
        if to and to < since:
            # nothing after `since` is on this page or an older one, so the list is whole from its end
            reaches = min(reaches or to, to)
            continue
        rows += _form4s(json.loads(feeds.fetch_text(OLDER_URL.format(name=page["name"]), 0, store=False, timeout=30)))
        if frm:
            reaches = min(reaches or frm, frm)
    rows.sort(key=lambda r: r[1], reverse=True)
    return {"cik": str(int(padded)), "filings": rows, "reaches": reaches}


def compact(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """What is kept of one Form 4: who, and its open-market purchases and sales of shares, one per day and code
    (a trade filled in several lots is filed as several lines at several prices; the price kept is their average)."""
    if not parsed.get("available"):
        return {"available": False, "reason": parsed.get("reason")}
    days: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for tx in parsed.get("transactions") or []:
        code = tx.get("code")
        if tx.get("kind") != "share" or code not in TRADE_CODES or not tx.get("date"):
            continue
        d = days.setdefault((tx["date"][:10], code), {"date": tx["date"][:10], "code": code, "shares": 0.0, "value": 0.0,
                                                       "priced": True})
        d["shares"] += tx.get("shares") or 0.0
        if tx.get("value") is None:
            d["priced"] = False
        else:
            d["value"] += tx["value"]
    trades = []
    for d in days.values():
        priced = d.pop("priced") and d["value"] > 0
        d["value"] = round(d["value"], 2) if priced else None
        d["price"] = round(d["value"] / d["shares"], 4) if priced and d["shares"] else None
        trades.append(d)
    return {"available": True, "issuer_cik": parsed.get("issuer_cik"), "insider": parsed.get("insider"),
            "roles": parsed.get("roles") or [], "trades": trades}


def fill(ticker: str, until: str, budget: int = RUN_BUDGET, today: Optional[dt.date] = None) -> Dict[str, int]:
    """Read the unread filings of the stretch Yahoo's list leaves out (two years back to `until`, Yahoo's oldest
    row), newest first, and keep them."""
    since = ((today or _today()) - dt.timedelta(days=DAYS)).isoformat()
    kept = form4_store.load_list(ticker)
    if not _fresh(kept, since):
        listed = list_filings(ticker, since)
        if listed is None:
            return {"listed": 0, "read": 0}
        form4_store.save_list(ticker, listed["cik"], listed["filings"], listed["reaches"])
        kept = form4_store.load_list(ticker) or dict(listed, fetched_at="")
    window = _window(kept, since, until)
    have = form4_store.load_many(acc for acc, _ in window)
    todo = [(acc, filed) for acc, filed in window if acc not in have]
    read = failed = refused = 0
    for acc, _ in todo[:max(0, int(budget))]:
        try:
            parsed = insiders_mod.parse_filing(
                ARCHIVE_INDEX.format(cik=kept["cik"], folder=acc.replace("-", ""), accession=acc), acc, store=False)
        except Exception as exc:                              # noqa: BLE001
            failed += 1
            refused += 1
            log.info("insider fill %s: %s not read (%s)", ticker, acc, exc)
            if refused >= 3:                                  # EDGAR is refusing or down: the next visit resumes
                break
            continue
        refused = 0
        form4_store.save(acc, kept["cik"], compact(parsed))
        read += 1
        time.sleep(FILL_GAP_SECONDS)
    return {"listed": len(kept.get("filings") or []), "window": len(todo), "read": read, "failed": failed}

