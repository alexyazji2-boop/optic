"""Two fundamentals for every stock in the screen's universe at once, from SEC's XBRL frames (owner's Handoff 8).

The screener ranks NASDAQ-listed stocks on daily bars and nothing else (app/analytics/screen.py), so a request like
"positive revenue growth and below-average debt ratios" had no filter to land on. SEC publishes each XBRL concept for
every filer and one period in a single file (https://data.sec.gov/api/xbrl/frames/...): free, the same filings the
Financials tab reads one company at a time (app/analytics/sec_facts.py), and no new provider. A handful of files
covers the whole universe, so a day of cache costs SEC about ten requests.

Two measures, each with its period said wherever it is shown, because a growth figure without its years reads as
current when it is not:

- **Revenue growth**: revenue in the latest fiscal year SEC's calendar-year frame holds (the fiscal year that falls
  mostly in that calendar year: Apple's year to September 2025 sits in 2025, and so does Nvidia's to January 2026)
  against the year before, both from the same XBRL tag for the same company. The latest year is the one whose annual reports are all due: last year from May on,
  the year before until then.
- **Debt ratio**: total liabilities over total assets on the latest balance sheet every filer has had time to file
  (a quarter-end at least 75 days back). The accounting textbook's "debt ratio"; where a company tags no total
  liabilities, liabilities-and-equity less equity.

A company that files in IFRS (a foreign private issuer's 20-F) or not with SEC at all has no US-GAAP figure here and
is said to have none: it is never estimated, and it does not pass a filter on a figure it lacks.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from .. import feeds
from . import sec_facts

log = logging.getLogger(__name__)

FRAMES_URL = "https://data.sec.gov/api/xbrl/frames/us-gaap/{concept}/{unit}/{period}.json"
CACHE_DIR = os.path.join(feeds._DATA_DIR, "sec_frames")
TTL = 86400.0
# The revenue tags most filers use, in the order preferred (sec_facts.REVENUE_TAGS has the long tail). One tag per
# company for both years, so a company that changed tags between years is not compared across two definitions.
REVENUE_TAGS = ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet")
BALANCE_LAG_DAYS = 75   # a 10-Q is due 40 to 45 days after the quarter; 75 leaves the late filers time
ANNUAL_FROM_MONTH = 5   # 10-Ks for a calendar year are due by the end of March; May leaves the late ones time

SOURCE = "SEC EDGAR XBRL frames (company filings, as filed)"

_LOCK = threading.Lock()
_MEMO: Dict[str, Any] = {"key": None, "data": None, "at": 0.0}
_BUSY = {"running": False, "started": 0.0, "error": None}


def periods(today: Optional[dt.date] = None) -> Dict[str, Any]:
    """Which frames hold the latest complete figures today: the revenue years, and the balance-sheet quarter-end."""
    today = today or dt.date.today()
    year = today.year - 1 if today.month >= ANNUAL_FROM_MONTH else today.year - 2
    ends = [dt.date(y, m, d) for y in (today.year, today.year - 1) for m, d in ((12, 31), (9, 30), (6, 30), (3, 31))]
    quarter_end = next(e for e in ends if (today - e).days >= BALANCE_LAG_DAYS)
    q = (quarter_end.month - 1) // 3 + 1
    return {"revenue_year": year, "revenue_prior": year - 1,
            "balance_end": quarter_end.isoformat(), "balance_frame": "CY{}Q{}I".format(quarter_end.year, q)}


def _cache_path(concept: str, unit: str, period: str) -> str:
    return os.path.join(CACHE_DIR, "{}-{}-{}.json".format(concept, unit, period))


def _frame(concept: str, unit: str, period: str) -> List[Dict[str, Any]]:
    """One frame's rows ({cik, end, val, accn}), from disk if less than a day old, else from SEC (and on a failure
    the last copy on disk, however old, as sec_facts does). [] when SEC has no such frame."""
    path = _cache_path(concept, unit, period)
    try:
        if time.time() - os.path.getmtime(path) < TTL:
            with open(path) as fh:
                return json.load(fh)
    except (OSError, ValueError):
        pass
    try:
        body = feeds._fetch(FRAMES_URL.format(concept=concept, unit=unit, period=period), "application/json")
        rows = [{"cik": int(r["cik"]), "end": r.get("end"), "val": r.get("val"), "accn": r.get("accn")}
                for r in (json.loads(body).get("data") or []) if isinstance(r, dict) and r.get("cik") is not None]
    except Exception as exc:                                   # noqa: BLE001 - a missing frame is a 404
        if "404" in str(exc):
            return []
        try:
            with open(path) as fh:
                log.info("sec_frames: %s/%s failed (%s), using the copy on disk", concept, period, exc)
                return json.load(fh)
        except (OSError, ValueError):
            raise exc
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(path + ".tmp", "w") as fh:
            json.dump(rows, fh)
        os.replace(path + ".tmp", path)
    except OSError as exc:
        log.warning("sec_frames: could not keep %s: %s", path, exc)
    return rows


def _tickers() -> Dict[int, List[str]]:
    """SEC's own CIK-to-ticker directory (sec_facts reads the same file)."""
    blob = sec_facts._json_or_stale(sec_facts.TICKER_MAP_URL, sec_facts.TICKER_TTL, "sec:tickers")
    out: Dict[int, List[str]] = {}
    for row in (blob or {}).values() if isinstance(blob, dict) else []:
        if isinstance(row, dict) and row.get("cik_str") is not None and row.get("ticker"):
            out.setdefault(int(row["cik_str"]), []).append(str(row["ticker"]).upper().replace(".", "-"))
    return out


def _by_cik(rows: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    return {r["cik"]: r for r in rows if isinstance(r.get("val"), (int, float))}


def build(today: Optional[dt.date] = None, frame: Callable[[str, str, str], List[Dict[str, Any]]] = None,
          tickers: Callable[[], Dict[int, List[str]]] = None) -> Dict[str, Any]:
    """Both measures for every filer, by ticker, with the periods and the source. `frame` and `tickers` are the
    two fetches, injectable for tests."""
    frame = frame or _frame
    tickers = tickers or _tickers
    p = periods(today)
    by_ticker: Dict[str, Dict[str, Any]] = {}
    cik_tickers = tickers()

    def put(cik: int, key: str, value: Any) -> None:
        for t in cik_tickers.get(cik, []):
            by_ticker.setdefault(t, {})[key] = value

    # revenue growth: the first tag a company reports in both years, the same tag for both
    done = set()
    for tag in REVENUE_TAGS:
        now = _by_cik(frame(tag, "USD", "CY{}".format(p["revenue_year"])))
        before = _by_cik(frame(tag, "USD", "CY{}".format(p["revenue_prior"])))
        for cik, row in now.items():
            if cik in done or cik not in before:
                continue
            prior = before[cik]["val"]
            if not prior or prior <= 0:
                continue
            done.add(cik)
            put(cik, "revenue_growth", round((row["val"] / prior - 1.0) * 100.0, 2))
            put(cik, "revenue_period", {"end": row.get("end"), "prior_end": before[cik].get("end"), "tag": tag,
                                        "revenue": row["val"], "revenue_prior": prior})
    # debt ratio: liabilities over assets, at the same balance-sheet date
    assets = _by_cik(frame("Assets", "USD", p["balance_frame"]))
    liab = _by_cik(frame("Liabilities", "USD", p["balance_frame"]))
    both = _by_cik(frame("LiabilitiesAndStockholdersEquity", "USD", p["balance_frame"]))
    equity = _by_cik(frame("StockholdersEquity", "USD", p["balance_frame"]))
    for cik, a in assets.items():
        if not a["val"] or a["val"] <= 0:
            continue
        if cik in liab:
            total, how = liab[cik]["val"], "Liabilities"
        elif cik in both and cik in equity:
            total, how = both[cik]["val"] - equity[cik]["val"], "LiabilitiesAndStockholdersEquity less StockholdersEquity"
        else:
            continue
        put(cik, "debt_ratio", round(total / a["val"] * 100.0, 2))
        put(cik, "debt_period", {"end": a.get("end"), "how": how, "liabilities": total, "assets": a["val"]})
    return {"by_ticker": by_ticker, "periods": p, "source": SOURCE, "built_at": time.time(),
            "coverage": {"revenue_growth": sum(1 for v in by_ticker.values() if "revenue_growth" in v),
                         "debt_ratio": sum(1 for v in by_ticker.values() if "debt_ratio" in v)}}


def cached(today: Optional[dt.date] = None) -> Optional[Dict[str, Any]]:
    """The measures if they are built for today's periods, without fetching anything."""
    key = json.dumps(periods(today), sort_keys=True)
    with _LOCK:
        if _MEMO["key"] == key and _MEMO["data"] and time.time() - _MEMO["at"] < TTL:
            return _MEMO["data"]
    return None


def status() -> Dict[str, Any]:
    with _LOCK:
        return dict(_BUSY)


def ensure(today: Optional[dt.date] = None, background: bool = True) -> Optional[Dict[str, Any]]:
    """The measures, or None while they are being read in the background (the screen says so and asks again)."""
    have = cached(today)
    if have is not None:
        return have
    with _LOCK:
        if _BUSY["running"]:
            return None
        _BUSY.update(running=True, started=time.time(), error=None)

    def work() -> Optional[Dict[str, Any]]:
        try:
            data = build(today)
            with _LOCK:
                _MEMO.update(key=json.dumps(periods(today), sort_keys=True), data=data, at=time.time())
            return data
        except Exception as exc:                               # noqa: BLE001 - said to the reader by the screen
            log.warning("sec_frames: build failed: %s", exc)
            with _LOCK:
                _BUSY["error"] = str(exc)[:200]
            return None
        finally:
            with _LOCK:
                _BUSY["running"] = False
    if background:
        threading.Thread(target=work, daemon=True, name="sec-frames").start()
        return None
    return work()


def install(data: Dict[str, Any], today: Optional[dt.date] = None) -> None:
    """Put built measures in place (tests, and a warm start)."""
    with _LOCK:
        _MEMO.update(key=json.dumps(periods(today), sort_keys=True), data=data, at=time.time())
