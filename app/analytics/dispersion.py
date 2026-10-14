"""Dispersion: how much the average stock is expected to move, against the index.

From a trading post: "VIXEQ - VIX measures the risk hiding beneath the index.
When the spread rises, the S&P 500 can look calm while the average stock
becomes much more volatile. That is often where market stress starts."

The first two sentences are arithmetic. VIXEQ is Cboe's 30-day implied
volatility of the average large US stock; the VIX is the S&P 500's. An index
is calmer than its members by however little they move together, so the gap
is mostly implied correlation, which Cboe publishes as COR1M (a month ahead),
and DSPX is Cboe's direct measure of expected dispersion. A wide gap means
stocks are expected to move a lot, but not together.

The third sentence is a forecast, and it was tested (2026-10-14,
`docs/research/dispersion-2026-10-14.md`; Cboe's daily history from June 2014,
the S&P 500's drawdown over the next 63 sessions, quintiles cut on data up to
each day). Days in the gap's two lowest quintiles were followed by a 10%
drawdown 6% of the time, the upper three 13 to 16%; but the VIX alone sorts
the same outcomes more sharply (0.3% in its lowest quintile, 19% in its
highest), and inside each VIX tercile the gap adds nothing consistent. A
rising gap predicted nothing. So the gauge is shown for what it describes, and
the panel says what it did not predict.

Sources: today's values from Yahoo (^VIX, ^VIXEQ, ^COR1M, ^DSPX). History:
Yahoo keeps DSPX from May 2024 and only five days of VIXEQ and COR1M, so
Optic stores one reading a day of each, and where `OPTIC_CBOE_HISTORY` is set
reads Cboe's own daily files (VIXEQ and DSPX from 2014, COR1M from 2006).
Cboe's site terms are for personal use, so showing that history publicly is
the owner's decision, as with DoltHub's.
"""

from __future__ import annotations

import csv
import os
import sqlite3
import threading
import time
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Tuple
SYMBOLS = {"^VIX": "VIX", "^VIXEQ": "VIXEQ", "^COR1M": "COR1M", "^DSPX": "DSPX"}
CBOE_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/{}_History.csv"
CBOE_TTL = 18 * 3600
MIN_HISTORY = 60
_LOCK = threading.Lock()

# From the study, so the panel can say what the gauge did and did not do.
EVIDENCE = {
    "sample": "Cboe daily history, June 2014 to October 2026; S&P 500 drawdown over the next 63 sessions",
    "p_dd10_by_gap_quintile": [5.9, 5.5, 12.8, 16.0, 13.1],
    "p_dd10_by_vix_quintile": [0.3, 9.0, 9.3, 16.8, 18.6],
    "finding": ("Wide gaps came before 10% drawdowns somewhat more often (13 to 16% of days in the upper three "
                "quintiles, about 6% in the lower two), but the VIX alone sorted the same outcomes more sharply, "
                "and within each VIX level the gap added nothing consistent. A rising gap predicted nothing."),
}


def cboe_enabled() -> bool:
    return os.environ.get("OPTIC_CBOE_HISTORY", "false").strip().lower() in ("1", "true", "yes", "on")


def _data_dir() -> str:
    return os.environ.get("TRACKER_DATA_DIR", "data")


def _connect() -> sqlite3.Connection:
    os.makedirs(_data_dir(), exist_ok=True)
    con = sqlite3.connect(os.path.join(_data_dir(), "index_daily.db"), timeout=10)
    con.execute("CREATE TABLE IF NOT EXISTS index_daily (symbol TEXT NOT NULL, day TEXT NOT NULL, "
                "value REAL NOT NULL, PRIMARY KEY (symbol, day))")
    return con


def record(values: Dict[str, Tuple[str, float]]) -> None:
    """One reading a day per index, keyed by the bar's own date."""
    with _LOCK:
        try:
            con = _connect()
            with con:
                con.executemany("INSERT OR REPLACE INTO index_daily VALUES (?,?,?)",
                                [(k, d, v) for k, (d, v) in values.items()])
            con.close()
        except sqlite3.Error:
            pass


def stored(name: str) -> Dict[str, float]:
    with _LOCK:
        try:
            con = _connect()
            rows = con.execute("SELECT day, value FROM index_daily WHERE symbol=?", (name,)).fetchall()
            con.close()
        except sqlite3.Error:
            return {}
    return {d: v for d, v in rows}


def _cboe_series(name: str, fetch: Optional[Callable[[str], str]] = None) -> Dict[str, float]:
    """Cboe's daily file for one index, cached on disk for 18 hours."""
    folder = os.path.join(_data_dir(), "cboe")
    path = os.path.join(folder, name + ".csv")
    fresh = os.path.exists(path) and time.time() - os.path.getmtime(path) < CBOE_TTL
    if not fresh:
        try:
            if fetch:
                text = fetch(CBOE_URL.format(name))
            else:
                req = urllib.request.Request(CBOE_URL.format(name), headers={"User-Agent": "OpticTerminal/1.0"})
                with urllib.request.urlopen(req, timeout=20) as r:
                    text = r.read().decode("utf-8")
            if text.startswith("DATE"):
                os.makedirs(folder, exist_ok=True)
                with open(path, "w") as f:
                    f.write(text)
        except Exception:                                         # noqa: BLE001
            pass
    if not os.path.exists(path):
        return {}
    out: Dict[str, float] = {}
    with open(path) as f:
        rows = list(csv.reader(f))
    head = rows[0] if rows else []
    col = head.index("CLOSE") if "CLOSE" in head else (head.index(name) if name in head else len(head) - 1)
    for r in rows[1:]:
        try:
            m, d, y = r[0].split("/")
            out["{}-{}-{}".format(y, m.zfill(2), d.zfill(2))] = float(r[col])
        except (ValueError, IndexError):
            continue
    return out


def _pct(values: List[float], today: float) -> Optional[float]:
    if len(values) < MIN_HISTORY:
        return None
    return round(sum(1 for v in values if v < today) / len(values) * 100, 1)


def build(provider, fetch: Optional[Callable[[str], str]] = None) -> Dict[str, Any]:
    now: Dict[str, Tuple[str, float]] = {}
    dspx_hist: Dict[str, float] = {}
    for sym, name in SYMBOLS.items():
        try:
            df = provider.history(sym, period="2y" if name == "DSPX" else "5d", interval="1d")
        except Exception:                                          # noqa: BLE001
            df = None
        if df is None or df.empty or "Close" not in df:
            continue
        closes = df["Close"].dropna()
        if closes.empty:
            continue
        stamp = closes.index[-1]
        now[name] = (str(getattr(stamp, "date", lambda: stamp)()), float(closes.iloc[-1]))
        if name == "DSPX":
            dspx_hist = {str(getattr(i, "date", lambda: i)()): float(v) for i, v in closes.items()}
    if "VIX" not in now or "VIXEQ" not in now:
        return {"available": False, "reason": "The VIX or VIXEQ reading is missing from the feed today."}
    record(now)

    def hist(name: str, yahoo: Optional[Dict[str, float]] = None) -> Tuple[Dict[str, float], str]:
        merged = dict(stored(name))
        src = "Optic's own daily readings"
        if yahoo:
            merged.update(yahoo)
            src = "Yahoo's daily history"
        if cboe_enabled():
            cb = _cboe_series(name, fetch)
            if cb:
                merged = {**cb, **merged}
                src = "Cboe's daily history"
        return merged, src

    vix_h, vix_src = hist("VIX")
    eq_h, eq_src = hist("VIXEQ")
    cor_h, cor_src = hist("COR1M")
    dsp_h, dsp_src = hist("DSPX", dspx_hist)
    days = sorted(set(vix_h) & set(eq_h))
    gaps = [eq_h[d] - vix_h[d] for d in days]
    vix_d, vix_v = now["VIX"]
    eq_d, eq_v = now["VIXEQ"]
    gap = eq_v - vix_v
    gap_pct = _pct(gaps, gap)
    cor = now.get("COR1M")
    dsp = now.get("DSPX")
    cor_pct = _pct(list(cor_h.values()), cor[1]) if cor else None
    dsp_pct = _pct(list(dsp_h.values()), dsp[1]) if dsp else None
    since = days[0] if days else None

    parts = ["The average large stock's options price {:.1f}% a year of movement (VIXEQ) against {:.1f}% for the "
             "S&P 500 (VIX): a gap of {:.1f} points".format(eq_v, vix_v, gap)]
    if gap_pct is not None:
        parts[0] += ", wider than {:.0f}% of days since {}".format(gap_pct, since[:4])
    text = parts[0] + "."
    if cor:
        text += " Implied correlation (COR1M) is {:.1f}{}: stocks are expected to move a lot, but not together, which " \
                "is what keeps the index calm.".format(
                    cor[1], ", lower than {:.0f}% of days on record".format(100 - cor_pct) if cor_pct is not None and cor_pct < 50
                    else (", higher than {:.0f}% of days on record".format(cor_pct) if cor_pct is not None else ""))
    return {
        "available": True,
        "as_of": max(vix_d, eq_d),
        "vix": round(vix_v, 2), "vixeq": round(eq_v, 2), "gap": round(gap, 2), "gap_percentile": gap_pct,
        "gap_history_from": since, "gap_history_days": len(gaps), "gap_history_source": eq_src,
        "cor1m": None if not cor else round(cor[1], 2), "cor1m_percentile": cor_pct, "cor1m_source": cor_src,
        "dspx": None if not dsp else round(dsp[1], 2), "dspx_percentile": dsp_pct, "dspx_source": dsp_src,
        "text": text,
        "evidence": EVIDENCE,
        "history": [{"day": d, "gap": round(eq_h[d] - vix_h[d], 2)} for d in days[-252:]],
        "method": ("VIXEQ is Cboe's 30-day implied volatility of the average large US stock; VIX the S&P 500's; "
                   "COR1M the one-month implied correlation among the index's largest members; DSPX Cboe's "
                   "expected dispersion. Percentiles are over every day of history available, which grows a day at "
                   "a time where only Optic's own readings exist."),
        "sources": ["Yahoo Finance quotes for ^VIX, ^VIXEQ, ^COR1M, ^DSPX (Cboe indices)"]
                   + (["Cboe daily index history (cdn.cboe.com)"] if cboe_enabled() else []),
    }
