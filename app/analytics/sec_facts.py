"""Quarterly revenue and earnings history from SEC XBRL.

The free fundamentals feed gives four fiscal years and about five quarters, which
is not enough to draw a revenue-growth history or a price/earnings series. SEC's
XBRL `companyfacts` endpoint gives thirteen to seventeen years of quarterly
filings for a US filer, free and without a key. It is the same filing data the
paid feeds resell.

Three things have to be handled or the series is quietly wrong.

**Companies change XBRL tags mid-history.** Revenue has lived under at least six
different us-gaap tags. Reading the first tag that looks populated is how you get
NVIDIA's revenue ending in 2020 and JPMorgan's in 2014 — both switched. Every
known revenue tag is merged into one timeline.

**Filings are restated.** The same quarter appears in several filings with
different values as figures are revised. The most recently *filed* value wins,
not the first one found.

**A fiscal Q4 usually is not filed as a quarter.** The 10-K reports the full year,
so the fourth quarter has to be derived as the annual figure minus the three
reported quarters. Without that step every year has a hole in it.

And one that matters more than all of them for the P/E series: **EPS becomes
public on the filing date, not the period end.** A trailing P/E computed with a
quarter's earnings from the day that quarter closed is using a number nobody had
for another three to six weeks. Every series here is stamped with `available_from`
and the P/E builder uses that, not the period end.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from .. import feeds

log = logging.getLogger(__name__)

FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"

# Filings arrive four times a year, so a day of cache is generous and still fresh.
FACTS_TTL = 86400
TICKER_TTL = 86400

# Revenue, in the order preferred when two tags cover the same quarter. Merged
# rather than chosen: a single company's history routinely spans three of these.
REVENUE_TAGS = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "Revenues",
    "RevenuesNetOfInterestExpense",
    "SalesRevenueNet",
    "SalesRevenueGoodsNet",
    "SalesRevenueServicesNet",
)

EPS_TAGS = (
    "EarningsPerShareDiluted",
    "EarningsPerShareBasicAndDiluted",
    "EarningsPerShareBasic",
)

# A "quarter" by duration. XBRL durations wobble around 91 days because fiscal
# quarters end on weekdays; 80-100 accepts that and excludes half-years.
Q_MIN_DAYS, Q_MAX_DAYS = 80, 100
# An annual duration, used to derive the missing fourth quarter.
Y_MIN_DAYS, Y_MAX_DAYS = 340, 380


def _days(start: str, end: str) -> Optional[int]:
    try:
        return (dt.date.fromisoformat(end) - dt.date.fromisoformat(start)).days
    except (TypeError, ValueError):
        return None


def _json_or_stale(url: str, ttl: float, key: str) -> Any:
    """Fetch, and on failure fall back to any cached copy however old.

    SEC returns 403 to a caller it considers too busy, and a short burst of
    requests is enough to earn one. Without this fallback a rate-limit reply took
    the entire feature offline even though a complete copy of the filings was
    sitting on disk — and quarterly results filed years ago do not expire.
    """
    try:
        return feeds.fetch_json(url, ttl, key=key)
    except Exception as exc:                                   # noqa: BLE001
        stale = feeds.cached_json(key)
        if stale is not None:
            log.info("sec_facts: %s failed (%s), using cached copy", key, exc)
            return stale
        raise


class LookupUnavailable(RuntimeError):
    """EDGAR could not be reached. Distinct from "this is not a filer".

    Worth its own type because collapsing the two produced a flatly false
    message: with SEC rate-limiting the directory fetch, the panel told the
    reader that Microsoft "does not resolve to an SEC filer". One of these is a
    fact about the security and the other is a fact about our connection, and
    they must not read the same.
    """


def cik_for(ticker: str) -> Optional[str]:
    """Zero-padded CIK for a ticker, from EDGAR's own directory.

    Returns None when the ticker genuinely is not in the directory. Raises
    LookupUnavailable when the directory itself could not be read.
    """
    sym = (ticker or "").upper().strip()
    if not sym:
        return None
    try:
        blob = _json_or_stale(TICKER_MAP_URL, TICKER_TTL, "sec:tickers")
    except Exception as exc:                                   # noqa: BLE001
        raise LookupUnavailable(str(exc)[:120]) from exc
    if not isinstance(blob, dict):
        raise LookupUnavailable("EDGAR ticker directory was unreadable.")
    for row in blob.values():
        if isinstance(row, dict) and str(row.get("ticker", "")).upper().strip() == sym:
            return str(row.get("cik_str", "")).zfill(10)
    return None


def _facts(cik: str) -> Dict[str, Any]:
    blob = _json_or_stale(FACTS_URL.format(cik=cik), FACTS_TTL, "sec:facts:" + cik)
    return (blob or {}).get("facts", {}).get("us-gaap", {}) or {}


def _merge_periods(gaap: Dict[str, Any], tags: Tuple[str, ...], unit: str,
                   lo: int, hi: int) -> Dict[str, Dict[str, Any]]:
    """One value per period end, merged across tags, latest filing winning."""
    out: Dict[str, Dict[str, Any]] = {}
    for tag in tags:
        block = gaap.get(tag)
        if not block:
            continue
        for point in block.get("units", {}).get(unit, []) or []:
            start, end, filed = point.get("start"), point.get("end"), point.get("filed")
            if not (start and end and filed):
                continue
            span = _days(start, end)
            if span is None or not (lo <= span <= hi):
                continue
            val = point.get("val")
            if val is None:
                continue
            prev = out.get(end)
            if prev is None:
                out[end] = {"value": float(val), "filed": filed, "first_filed": filed,
                            "tag": tag, "start": start, "span_days": span}
                continue
            # Two different questions, and conflating them broke the P/E series.
            #
            # Which VALUE is right: the most recently filed one, because a
            # restatement supersedes what it restates.
            #
            # When the quarter became PUBLIC: the earliest filing, because that is
            # when a reader could first have seen it. Overwriting this with the
            # restatement date told the code that Microsoft's June 2021 quarter
            # was not public until July 2023 — which broke the four-consecutive-
            # quarters test for two years of the series, so every multiple in that
            # stretch was computed against earnings up to two years stale and the
            # five-year median came out at 42 instead of 30.
            if filed > prev["filed"]:
                prev.update({"value": float(val), "filed": filed, "tag": tag,
                             "start": start, "span_days": span})
            if filed < prev.get("first_filed", filed):
                prev["first_filed"] = filed
    return out


def _fill_fourth_quarters(quarters: Dict[str, Dict[str, Any]],
                          years: Dict[str, Dict[str, Any]]) -> int:
    """Derive the fiscal Q4 the 10-K reports only as part of the full year.

    Annual minus the three quarters that fall inside it. Requires all three or the
    year is skipped — deriving Q4 from two quarters would silently fold a missing
    quarter into it and produce a spike.
    """
    added = 0
    for y_end, y_row in years.items():
        y_start = y_row.get("start")
        if not y_start or y_end in quarters:
            continue
        inside = [q for end, q in quarters.items() if y_start <= q["start"] and end < y_end]
        inside = [q for q in inside if _days(y_start, q["start"]) is not None
                  and 0 <= (_days(y_start, q["start"]) or 0) <= 300]
        if len(inside) != 3:
            continue
        remainder = y_row["value"] - sum(q["value"] for q in inside)
        if remainder <= 0:
            continue
        # first_filed, not filed. The annual figure is restated in later 10-Ks, and
        # inheriting the restatement date made every derived fourth quarter look
        # years newer than it was. For Microsoft that is every June quarter, so any
        # trailing-twelve-month window containing one was gated behind a date two
        # to three years late — which is why the multiple history sat on stale
        # earnings for long stretches even after the availability logic was right.
        first = y_row.get("first_filed") or y_row["filed"]
        quarters[y_end] = {
            "value": remainder, "filed": y_row["filed"], "first_filed": first,
            "tag": y_row["tag"] + " (derived)",
            "start": max(q["start"] for q in inside), "span_days": None, "derived": True,
        }
        added += 1
    return added


def _series(merged: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for end in sorted(merged):
        row = merged[end]
        rows.append({
            "period_end": end,
            # The date the number first became public — the earliest filing that
            # carried it, not the latest restatement of it. Everything downstream
            # that could otherwise look ahead reads this instead of period_end.
            "available_from": row.get("first_filed") or row["filed"],
            "restated_on": row["filed"] if row.get("first_filed") != row["filed"] else None,
            "value": row["value"],
            "derived": bool(row.get("derived")),
        })
    return rows


def _trailing(rows: List[Dict[str, Any]], window: int = 4) -> List[Dict[str, Any]]:
    """Rolling sum of the last `window` quarters, gap-aware.

    Requires the four quarters to be roughly consecutive: summing across a hole
    would produce a trailing figure covering five or six quarters and label it
    twelve months.

    The gap test is on the span between the FIRST and LAST period end, which for
    four consecutive quarters is three intervals — about 270 days, not 365. The
    first version asked for 300-420 and threw away almost every valid window;
    Microsoft came back with none at all.
    """
    out = []
    for i in range(window - 1, len(rows)):
        chunk = rows[i - window + 1:i + 1]
        first = dt.date.fromisoformat(chunk[0]["period_end"])
        last = dt.date.fromisoformat(chunk[-1]["period_end"])
        if not (240 <= (last - first).days <= 300):
            continue
        out.append({
            "period_end": chunk[-1]["period_end"],
            "available_from": max(c["available_from"] for c in chunk),
            "value": sum(c["value"] for c in chunk),
            "derived": any(c["derived"] for c in chunk),
        })
    return out


def _yoy(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Year-on-year growth per quarter, matched four quarters back by date."""
    by_end = {r["period_end"]: r for r in rows}
    ends = sorted(by_end)
    out = []
    for i, end in enumerate(ends):
        if i < 4:
            continue
        prior = by_end[ends[i - 4]]
        gap = _days(ends[i - 4], end)
        if gap is None or not (300 <= gap <= 420):
            continue
        base = prior["value"]
        if base <= 0:
            continue
        row = by_end[end]
        out.append({
            "period_end": end,
            "available_from": row["available_from"],
            "value": row["value"],
            "prior": base,
            "growth_pct": round((row["value"] / base - 1.0) * 100.0, 1),
            "derived": row["derived"] or prior["derived"],
        })
    return out


CACHE_DIR = os.path.join("data", "sec_facts")
# Bumped whenever the extraction gains or renames a field. Without it, entries
# written before a new key existed are served to code that expects it — adding
# `short_history` raised a KeyError on every previously-cached ticker.
CACHE_SCHEMA = 4
# Filings land four times a year. A week of cache is still current and turns a
# multi-megabyte fetch into a file read.
CACHE_TTL_SECONDS = 7 * 86400


def _cache_path(ticker: str) -> str:
    safe = "".join(ch for ch in (ticker or "").upper() if ch.isalnum() or ch in "-.")
    return os.path.join(CACHE_DIR, safe + ".json")


def _read_cache(ticker: str) -> Tuple[Optional[Dict[str, Any]], float]:
    """The cached extraction and its age in seconds, or (None, inf)."""
    path = _cache_path(ticker)
    try:
        age = time.time() - os.path.getmtime(path)
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict) or data.get("schema") != CACHE_SCHEMA:
            return None, float("inf")        # written by an older extraction
        return data, age
    except (OSError, ValueError):
        return None, float("inf")


def _write_cache(ticker: str, data: Dict[str, Any]) -> None:
    """Only the extracted series, never the raw facts blob.

    companyfacts for a large filer runs to several megabytes. Putting that in the
    shared feed cache would bloat a file that everything else on the terminal
    reads on startup, so this keeps its own directory and stores only the handful
    of series actually used.
    """
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        tmp = _cache_path(ticker) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        os.replace(tmp, _cache_path(ticker))
    except OSError as exc:
        log.warning("sec_facts: could not cache %s: %s", ticker, exc)


def history(ticker: str, force: bool = False) -> Dict[str, Any]:
    """Quarterly revenue and diluted EPS history for one filer."""
    sym = (ticker or "").upper().strip()
    cached, age = _read_cache(sym)
    if cached and not force and age < CACHE_TTL_SECONDS:
        cached["cache_age_days"] = round(age / 86400.0, 1)
        return cached

    try:
        cik = cik_for(sym)
    except LookupUnavailable as exc:
        # Stale beats absent: these are filed quarterly results, not a quote.
        if cached:
            cached["cache_age_days"] = round(age / 86400.0, 1)
            cached["stale"] = True
            return cached
        return {"available": False,
                "reason": "Could not reach EDGAR to look up {} ({}). This is a "
                          "connection problem, not a statement about the "
                          "security.".format(sym, exc)}
    if not cik:
        return {"available": False,
                "reason": "{} is not in EDGAR's ticker directory — XBRL history "
                          "exists only for US registrants, so ETFs and foreign "
                          "issuers have none.".format(sym)}
    try:
        gaap = _facts(cik)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("sec_facts: companyfacts failed for %s: %s", ticker, exc)
        if cached:
            cached["cache_age_days"] = round(age / 86400.0, 1)
            cached["stale"] = True
            return cached
        return {"available": False, "reason": "SEC XBRL unavailable: {}".format(
            str(exc)[:120])}
    if not gaap:
        return {"available": False, "reason": "No us-gaap facts filed for this CIK."}

    rev_q = _merge_periods(gaap, REVENUE_TAGS, "USD", Q_MIN_DAYS, Q_MAX_DAYS)
    rev_y = _merge_periods(gaap, REVENUE_TAGS, "USD", Y_MIN_DAYS, Y_MAX_DAYS)
    derived_q = _fill_fourth_quarters(rev_q, rev_y)

    eps_q = _merge_periods(gaap, EPS_TAGS, "USD/shares", Q_MIN_DAYS, Q_MAX_DAYS)
    eps_y = _merge_periods(gaap, EPS_TAGS, "USD/shares", Y_MIN_DAYS, Y_MAX_DAYS)
    derived_eps = _fill_fourth_quarters(eps_q, eps_y)

    revenue = _series(rev_q)
    eps = _series(eps_q)
    if not revenue and not eps:
        return {"available": False,
                "reason": "No quarterly revenue or EPS tags in this filer's XBRL."}

    # A CIK with almost no filings behind a long-listed ticker means a
    # reorganisation: EDGAR points the ticker at the new registrant and the
    # predecessor's decades sit under a CIK this lookup cannot reach. Exxon is the
    # live example — XOM resolves to CIK 2115436 with two quarters, while the
    # eighteen-year history is filed under 34088. Showing two quarters as though
    # they were the company's history would be the worst of the three options, so
    # the thinness is stated.
    short_history = max(len(revenue), len(eps)) < 12
    notes: List[str] = []
    if short_history:
        notes.append(
            "EDGAR maps this ticker to CIK {}, which has only {} quarters of "
            "filings. That normally means a reorganisation or redomiciliation: the "
            "predecessor's history is filed under a different CIK that a ticker "
            "lookup cannot follow, so this series begins at the new entity rather "
            "than at the start of the business.".format(cik, max(len(revenue), len(eps))))

    out = {
        "available": True,
        "schema": CACHE_SCHEMA,
        "ticker": sym,
        "cik": cik,
        "revenue_quarters": revenue,
        "revenue_yoy": _yoy(revenue),
        "revenue_ttm": _trailing(revenue),
        "eps_quarters": eps,
        "eps_ttm": _trailing(eps),
        "counts": {
            "revenue_quarters": len(revenue),
            "eps_quarters": len(eps),
            "revenue_q4_derived": derived_q,
            "eps_q4_derived": derived_eps,
        },
        "span": {
            "revenue_from": revenue[0]["period_end"] if revenue else None,
            "revenue_to": revenue[-1]["period_end"] if revenue else None,
            "eps_from": eps[0]["period_end"] if eps else None,
            "eps_to": eps[-1]["period_end"] if eps else None,
        },
        "short_history": short_history,
        "notes": notes,
        "source": "SEC XBRL companyfacts (CIK {})".format(cik),
        "method": (
            "Straight from the filings. Revenue is merged across every us-gaap "
            "tag a company has used — six of them are in circulation, and a "
            "single issuer's history routinely spans three, so reading one tag "
            "truncates the series at whichever year they switched. Where the same "
            "quarter appears in several filings the most recently filed value "
            "wins, because that is the restated truth — while the date a quarter "
            "became public is the EARLIEST filing that carried it, not the latest "
            "restatement of it. A fiscal fourth quarter is "
            "usually filed only inside the annual figure, so it is derived as the "
            "year minus its three reported quarters, and skipped rather than "
            "guessed when any of the three is missing. Each point carries the date "
            "it was filed, not just the period it covers."
        ),
    }
    _write_cache(sym, out)
    out["cache_age_days"] = 0.0
    return out
