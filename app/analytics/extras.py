"""The remaining data types: dividends, splits, short volume, relative performance.

Each of these was on a "display other types of data" list and each is available
free, from a primary or near-primary source. Grouped in one module because none
of them is big enough to deserve its own, and because they share the same
discipline: report what the source published, say where it came from, and do not
compute a derived opinion on top of it.

**What is deliberately absent.** Dark pool volume and retail-activity percentage
were on the same list and are not here. Neither has a free source — both are sold
by vendors who aggregate broker feeds, and the only way to show them would be to
guess. A missing panel is better than a fabricated one.

**On short volume.** FINRA publishes a daily file of off-exchange short volume,
free and without a key. It is genuinely useful and routinely misread, so the
payload carries the caveat rather than leaving it to the reader: this is
*volume*, not short *interest*. A market maker selling short to fill a buy order
appears here, so a high ratio is often liquidity provision rather than bearish
positioning. It also covers only off-exchange trades, which is roughly half the
tape.
"""

from __future__ import annotations

import csv
import io
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests

FINRA_URL = "https://cdn.finra.org/equity/regsho/daily/CNMSshvol{}.txt"
FNG_URL = "https://api.alternative.me/fng/?limit={}"
TIMEOUT = 12
# FINRA files are published once and never change, so they cache hard.
_CACHE: Dict[str, Tuple[float, Any]] = {}


def _cached(key: str, ttl: float, build):
    hit = _CACHE.get(key)
    now = time.time()
    if hit and now - hit[0] < ttl:
        return hit[1]
    try:
        val = build()
    except Exception:
        # Serve a stale value rather than nothing: a day-old dividend history is
        # far more useful than an error, and none of this is time-critical.
        return hit[1] if hit else None
    _CACHE[key] = (now, val)
    return val


def _f(v: Any, digits: int = 4) -> Optional[float]:
    try:
        out = float(v)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(out) else round(out, digits)


# ------------------------------------------------------ dividends and splits

def corporate_actions(provider, ticker: str) -> Dict[str, Any]:
    """Dividend and split history, and what the dividend record actually shows.

    The growth streak is the number of consecutive years the *annual total* rose.
    Deliberately computed on the annual total rather than on each payment: a
    company that pays quarterly and raises once a year has three flat quarters,
    and counting payments would report a broken streak every time.
    """
    def build() -> Dict[str, Any]:
        import yfinance as yf
        t = yf.Ticker(ticker)
        divs = t.dividends
        splits = t.splits

        div_rows: List[Dict[str, Any]] = []
        if divs is not None and len(divs):
            for idx, val in list(divs.items())[-24:]:
                div_rows.append({"date": str(idx.date()), "amount": _f(val, 4)})

        yearly: Dict[int, float] = {}
        if divs is not None and len(divs):
            for idx, val in divs.items():
                yearly[idx.year] = yearly.get(idx.year, 0.0) + float(val)

        # The current (incomplete) year is excluded from the streak: a partial
        # year is nearly always below the last full one and would report every
        # dividend grower as having just broken its streak.
        this_year = datetime.now(timezone.utc).year
        complete = sorted((y, v) for y, v in yearly.items() if y < this_year)
        streak = 0
        for i in range(len(complete) - 1, 0, -1):
            if complete[i][1] > complete[i - 1][1]:
                streak += 1
            else:
                break
        cut = 0
        for i in range(len(complete) - 1, 0, -1):
            if complete[i][1] < complete[i - 1][1]:
                cut = complete[i][0]
                break

        split_rows: List[Dict[str, Any]] = []
        if splits is not None and len(splits):
            for idx, val in list(splits.items())[-12:]:
                split_rows.append({"date": str(idx.date()), "ratio": _f(val, 4)})

        return {
            "ticker": ticker,
            "dividends": div_rows,
            "splits": split_rows,
            "annual": [{"year": y, "total": _f(v, 4)} for y, v in complete[-12:]],
            "growth_streak_years": streak,
            "last_cut_year": cut or None,
            "pays_dividend": bool(div_rows),
            "note": ("Growth streak counts consecutive years the annual total rose, "
                     "using complete calendar years only. A partial current year "
                     "is always below the last full one and would report every "
                     "dividend grower as having just broken its streak."),
            "source": "Yahoo Finance corporate actions",
        }
    return _cached("actions:" + ticker, 6 * 3600, build) or {
        "ticker": ticker, "dividends": [], "splits": [], "annual": [],
        "error": "corporate actions unavailable",
    }


# ------------------------------------------------------------- short volume

def _finra_day(day: date) -> Optional[Dict[str, Dict[str, float]]]:
    url = FINRA_URL.format(day.strftime("%Y%m%d"))
    resp = requests.get(url, timeout=TIMEOUT)
    if resp.status_code != 200 or not resp.text.startswith("Date|"):
        return None
    out: Dict[str, Dict[str, float]] = {}
    reader = csv.DictReader(io.StringIO(resp.text), delimiter="|")
    for row in reader:
        sym = (row.get("Symbol") or "").strip().upper()
        if not sym:
            continue
        short = _f(row.get("ShortVolume"), 0)
        total = _f(row.get("TotalVolume"), 0)
        if short is None or total is None or total <= 0:
            continue
        out[sym] = {"short": short, "total": total}
    return out


def short_volume(ticker: str, days: int = 20) -> Dict[str, Any]:
    """FINRA off-exchange short volume, most recent first."""
    sym = ticker.strip().upper()

    def build() -> Dict[str, Any]:
        rows: List[Dict[str, Any]] = []
        cursor = datetime.now(timezone.utc).date()
        # Walk back over calendar days, skipping weekends and any day with no
        # file (holidays, or a publication lag of a day or two).
        looked = 0
        while len(rows) < days and looked < days * 3:
            looked += 1
            cursor -= timedelta(days=1)
            if cursor.weekday() >= 5:
                continue
            table = _cached("finra:" + cursor.isoformat(), 30 * 24 * 3600,
                            lambda d=cursor: _finra_day(d))
            if not table:
                continue
            hit = table.get(sym)
            if not hit:
                continue
            rows.append({
                "date": cursor.isoformat(),
                "short_volume": _f(hit["short"], 0),
                "total_volume": _f(hit["total"], 0),
                "short_pct": _f(hit["short"] / hit["total"] * 100, 2),
            })
        if not rows:
            return {"ticker": sym, "rows": [], "error": "no FINRA data for this symbol"}
        pcts = [r["short_pct"] for r in rows if r["short_pct"] is not None]
        return {
            "ticker": sym,
            "rows": rows,
            "latest_pct": rows[0]["short_pct"],
            "average_pct": _f(float(np.mean(pcts)), 2) if pcts else None,
            "days": len(rows),
            "caveat": ("This is short VOLUME, not short interest, and it covers "
                       "off-exchange trades only, roughly half the tape. A market "
                       "maker selling short to fill someone's buy order appears "
                       "here, so a high ratio is often liquidity provision rather "
                       "than bearish positioning. Read a change against this "
                       "symbol's own average, not against 50%."),
            "source": "FINRA Reg SHO daily short volume",
        }
    return _cached("shortvol:%s:%d" % (sym, days), 4 * 3600, build) or {
        "ticker": sym, "rows": [], "error": "short volume unavailable"}


# ------------------------------------------------------- crypto fear & greed

def crypto_sentiment(limit: int = 30) -> Dict[str, Any]:
    """The crypto fear and greed index.

    Included because it is a genuine risk-appetite reading on the most
    speculative liquid asset class, and it often moves before equity sentiment
    does. It is not a crypto price forecast and is not presented as one.
    """
    def build() -> Dict[str, Any]:
        resp = requests.get(FNG_URL.format(limit), timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json().get("data") or []
        rows = []
        for row in data:
            ts = row.get("timestamp")
            try:
                when = datetime.fromtimestamp(int(ts), tz=timezone.utc).date().isoformat()
            except (TypeError, ValueError):
                when = None
            rows.append({
                "date": when,
                "value": _f(row.get("value"), 0),
                "label": row.get("value_classification"),
            })
        if not rows:
            return {"rows": [], "error": "no readings returned"}
        vals = [r["value"] for r in rows if r["value"] is not None]
        return {
            "rows": rows,
            "latest": rows[0],
            "average_30d": _f(float(np.mean(vals)), 0) if vals else None,
            "note": ("0 is extreme fear, 100 extreme greed. A risk-appetite "
                     "reading on the most speculative liquid asset class, which "
                     "is why it is here. It tends to move before equity "
                     "sentiment. It says nothing about crypto prices."),
            "source": "alternative.me",
        }
    return _cached("fng:%d" % limit, 3600, build) or {
        "rows": [], "error": "sentiment unavailable"}


# --------------------------------------------------- relative performance

def relative_performance(provider, ticker: str, benchmark: str = "SPY",
                         period: str = "1y") -> Dict[str, Any]:
    """This symbol against a benchmark, as a ratio line and as excess returns.

    The ratio is the honest form: a stock up 20% in a year when the index rose
    25% underperformed, and a price chart alone will not say so.
    """
    sym = ticker.strip().upper()
    frames = provider.batch_history([sym, benchmark], period=period, interval="1d")
    a = frames.get(sym)
    b = frames.get(benchmark)
    if a is None or b is None or a.empty or b.empty:
        return {"ticker": sym, "benchmark": benchmark,
                "error": "history unavailable for one side"}

    left = a["Close"].astype(float).dropna()
    right = b["Close"].astype(float).dropna()
    left.index = pd.to_datetime(left.index).tz_localize(None)
    right.index = pd.to_datetime(right.index).tz_localize(None)
    joined = pd.concat({"a": left, "b": right}, axis=1).dropna()
    if len(joined) < 30:
        return {"ticker": sym, "benchmark": benchmark,
                "error": "not enough overlapping history"}

    ratio = joined["a"] / joined["b"]
    # Indexed to 100 at the start, so the line reads as "relative to where this
    # pair began" rather than as an arbitrary price ratio.
    indexed = ratio / ratio.iloc[0] * 100

    def excess(bars: int) -> Optional[float]:
        if len(joined) <= bars:
            return None
        s_ret = joined["a"].iloc[-1] / joined["a"].iloc[-1 - bars] - 1
        b_ret = joined["b"].iloc[-1] / joined["b"].iloc[-1 - bars] - 1
        return _f((s_ret - b_ret) * 100, 2)

    return {
        "ticker": sym,
        "benchmark": benchmark,
        "dates": [str(i.date()) for i in joined.index],
        "ratio": [_f(v, 3) for v in indexed.tolist()],
        "excess": {"5d": excess(5), "20d": excess(20), "60d": excess(60),
                   "120d": excess(120), "252d": excess(252)},
        "note": ("The line is this symbol divided by {}, indexed to 100 at the "
                 "start. Rising means outperformance regardless of whether either "
                 "went up. A stock up 20% in a year the index rose 25% "
                 "underperformed, and a price chart will not say so."
                 .format(benchmark)),
    }
