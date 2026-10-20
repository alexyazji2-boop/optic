"""Actual and previous values for economic releases, from FRED.

The calendar could say a release was *scheduled* but never what it *said*. That
is half a calendar: the useful question the morning after a print is "what was
the number, and how does it compare to last time".

FRED publishes every series this needs as CSV at a stable URL with **no API key**,
which is why this exists at all — the alternative was a licensed economic-calendar
feed. The data is the statistical agency's own, redistributed by the St. Louis
Fed, so it is a primary source at one remove rather than a vendor's
interpretation.

**There is still no forecast column and there will not be one from here.**
Consensus estimates are surveyed and licensed. FRED carries what was published,
not what anyone expected, and a "forecast" copied from a free mirror of somebody
else's survey is worse than an honest gap — a stale consensus next to a real
actual manufactures a surprise that never happened.

**Series are mapped explicitly, never guessed.** A fuzzy title match would
eventually pair "Producer Price Index" with the wrong PPI series — of which FRED
has dozens — and print a confidently wrong number. Anything not in the map gets
no value, which is the correct answer.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from . import feeds

log = logging.getLogger(__name__)

CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"

# Series change once a month at most, and several are monthly or weekly. Six
# hours keeps a same-day re-read free without ever showing yesterday's print as
# today's.
TTL_SECONDS = 6 * 3600

# Release title (lowercase substring) -> FRED series and how to present it.
#
# `transform` decides what the reader sees:
#   "level"    the value as published — a rate, an index, a count
#   "pct_mom"  month-over-month percentage change, computed here
#   "pct_yoy"  year-over-year percentage change, computed here
#
# CPI and PPI are *indexes* in FRED; nobody quotes them that way, so those are
# converted to the month-over-month change the release headline actually leads
# with. Getting this wrong would print "332.813%" for inflation.
#
# `reports` is the period a release covers, counted back from the month it comes
# out in: most monthly releases report the month before, JOLTS the one before
# that, the quarterly ones the quarter before. It is how a release that is out
# is checked against FRED, which posts the new print some time after the agency
# does: until FRED has that period, its last value is the period before's, and
# calling it the new print would be wrong. A series without it (the weekly
# mortgage rate) is taken as FRED has it.
SERIES_MAP: Dict[str, Dict[str, Any]] = {
    "consumer price index": {
        "series": "CPIAUCSL", "transform": "pct_mom", "unit": "%", "reports": ("month", 1),
        "label": "CPI, all items, month over month"},
    "producer price index": {
        "series": "PPIFIS", "transform": "pct_mom", "unit": "%", "reports": ("month", 1),
        "label": "PPI, final demand, month over month"},
    "employment situation": {
        "series": "PAYEMS", "transform": "diff_thousands", "unit": "k", "reports": ("month", 1),
        "label": "Nonfarm payrolls, change on the month"},
    "unemployment": {
        "series": "UNRATE", "transform": "level", "unit": "%", "reports": ("month", 1),
        "label": "Unemployment rate"},
    "personal income": {
        "series": "PI", "transform": "pct_mom", "unit": "%", "reports": ("month", 1),
        "label": "Personal income, month over month"},
    "retail sales": {
        "series": "RSAFS", "transform": "pct_mom", "unit": "%", "reports": ("month", 1),
        "label": "Retail sales, month over month"},
    "industrial production": {
        "series": "INDPRO", "transform": "pct_mom", "unit": "%", "reports": ("month", 1),
        "label": "Industrial production, month over month"},
    "gross domestic product": {
        "series": "GDPC1", "transform": "pct_qoq_annual", "unit": "%", "reports": ("quarter", 1),
        "label": "Real GDP, annualised quarterly rate"},
    "job openings": {
        "series": "JTSJOL", "transform": "level_millions", "unit": "m", "reports": ("month", 2),
        "label": "Job openings"},
    "employment cost index": {
        "series": "ECIALLCIV", "transform": "pct_qoq", "unit": "%", "reports": ("quarter", 1),
        "label": "Employment cost index, quarter over quarter"},
    "import and export price": {
        "series": "IR", "transform": "pct_mom", "unit": "%", "reports": ("month", 1),
        "label": "Import price index, month over month"},
    "productivity": {
        "series": "OPHNFB", "transform": "pct_qoq_annual", "unit": "%", "reports": ("quarter", 1),
        "label": "Nonfarm productivity, annualised quarterly rate"},
    "mortgage rate": {
        "series": "MORTGAGE30US", "transform": "level", "unit": "%",
        "label": "30-year fixed mortgage rate"},
}


def _num(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if out != out else out


def observations(series: str, timeout: Optional[float] = None) -> List[Tuple[str, float]]:
    """(date, value) pairs for a FRED series, oldest first.

    FRED writes "." for a missing observation rather than an empty field, so a
    naive float() over the column raises on perfectly normal data.

    `timeout` is for a caller that cannot wait the feed's full timeout on a
    miss: the macro panel reads the high-yield spread on every load.
    """
    try:
        # Empty string = send no User-Agent. FRED hangs on ours; see feeds._fetch.
        raw = feeds.fetch_text(CSV_URL.format(series=series), TTL_SECONDS,
                               key="fred:" + series, user_agent="", timeout=timeout)
    except Exception as exc:
        log.warning("FRED series %s unavailable: %s", series, exc)
        return []

    out: List[Tuple[str, float]] = []
    for line in (raw or "").splitlines()[1:]:
        parts = line.split(",")
        if len(parts) < 2:
            continue
        value = _num(parts[1].strip())
        if value is None:
            continue
        out.append((parts[0].strip(), value))
    return out


def _present(spec: Dict[str, Any], rows: List[Tuple[str, float]]) -> Dict[str, Any]:
    """Turn the last observations into the actual and previous a reader wants."""
    transform = spec["transform"]
    need = 3 if transform.startswith("pct") or transform.startswith("diff") else 2
    if len(rows) < need:
        return {"available": False}

    def at(i: int) -> float:
        return rows[-i][1]

    def change(newer: float, older: float) -> Optional[float]:
        if older == 0:
            return None
        return (newer / older - 1.0) * 100.0

    if transform == "level":
        actual, previous = at(1), at(2)
    elif transform == "level_millions":
        actual, previous = at(1) / 1000.0, at(2) / 1000.0
    elif transform == "diff_thousands":
        actual, previous = at(1) - at(2), at(2) - at(3)
    elif transform in ("pct_mom", "pct_qoq"):
        actual, previous = change(at(1), at(2)), change(at(2), at(3))
    elif transform in ("pct_qoq_annual",):
        # Annualise a quarterly change: compounding four quarters of it.
        q1, q2 = change(at(1), at(2)), change(at(2), at(3))
        actual = ((1 + q1 / 100.0) ** 4 - 1) * 100.0 if q1 is not None else None
        previous = ((1 + q2 / 100.0) ** 4 - 1) * 100.0 if q2 is not None else None
    else:
        return {"available": False}

    if actual is None:
        return {"available": False}

    digits = 0 if spec["unit"] == "k" else 1 if abs(actual) >= 10 else 2
    return {
        "available": True,
        "series": spec["series"],
        "label": spec["label"],
        "unit": spec["unit"],
        "as_of": rows[-1][0],
        "previous_as_of": rows[-2][0],           # the observation `previous` is for
        "actual": round(actual, digits),
        "previous": round(previous, digits) if previous is not None else None,
        # No forecast, and the reason travels with the row rather than living in
        # a footnote nobody reads.
        "forecast": None,
        "forecast_note": ("Consensus estimates are surveyed and licensed. FRED "
                          "publishes what was released, not what was expected."),
    }


def _spec(title: str) -> Optional[Dict[str, Any]]:
    low = (title or "").lower()
    return next((v for k, v in SERIES_MAP.items() if k in low), None)


def reference_period(title: str, released_on: date) -> Optional[str]:
    """The first day of the period a release out on `released_on` reports on, as
    FRED dates it ("2026-10-01" for October, "2026-07-01" for Q3), or None when
    the series has no rule."""
    spec = _spec(title)
    rule = (spec or {}).get("reports")
    if not rule:
        return None
    unit, back = rule
    if unit == "quarter":
        q = (released_on.year * 4 + (released_on.month - 1) // 3) - back
        return "{:04d}-{:02d}-01".format(q // 4, (q % 4) * 3 + 1)
    m = (released_on.year * 12 + released_on.month - 1) - back
    return "{:04d}-{:02d}-01".format(m // 12, m % 12 + 1)


def for_release(title: str) -> Dict[str, Any]:
    """Actual and previous for a release title, or unavailable."""
    spec = _spec(title)
    if not spec:
        return {"available": False,
                "reason": "No FRED series is mapped to this release."}
    return _present(spec, observations(spec["series"]))
