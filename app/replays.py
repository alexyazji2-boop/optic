"""Learning replays (roadmap stage 7, 2026-10-22): a past chart revealed one completed session at a time,
a decision asked for at the session the setups engine flagged, and a review of what followed.

What it promises, and how:

* **Nothing after the cursor.** The server sends the bars up to the replay's current session and not one
  more; the chart computes its averages, RSI and pivots from those bars alone, and the setup reading is the
  engine run on the history cut at that session's close (`now` = that close), so its confirmed pivots and
  completed candles are the ones that existed then. No news, fundamentals or option data are shown: the
  scope is daily price and volume, and the page says so.
* **Revised data is named.** The feed's daily closes are adjusted for every later stock split (not for
  dividends), so an old close is not the price quoted that day when the stock has split since. The review
  says by how much; during the replay the page says only that the prices are split-adjusted, because the
  date of a later split is itself something nobody knew yet.
* **The decision is the reader's, and kept.** The page asks for it before the replay goes past the decision
  session, and stores it in the reader's browser; the review sets it beside the rule's reading and what
  happened, and says that one outcome does not grade a decision.

The library is small on purpose: each entry is a date where the engine, reading only the bars up to that
date, flagged a setup with every condition but (at most) its trigger in place. It was picked by
work/roadmap-2026-10-22/replays/pick_library.py for a spread of outcomes, which the titles do not reveal.
"""

from __future__ import annotations

import threading
import time
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd

from . import session as session_mod
from . import shortlist as shortlist_mod
from .analytics import setups as setups_mod

VERSION = "replays-2026-10-22.1"
LEAD = 20          # sessions revealed before the decision
REVIEW = 20        # sessions after it, the same horizon the shortlist records
WARMUP = 260       # sessions before the first revealed one, so a 200-session average exists from the start
SCOPE = ("Daily price and volume only, revealed one completed session at a time. No news, results, analyst "
         "changes or option flow are shown, because Optic does not hold them as they stood on each day, and a "
         "replay that showed today's versions would leak what came later.")
REVISED = ("Prices are adjusted for later stock splits, as the feed supplies them (not for dividends). Moves in "
           "percent, the averages and the RSI are the same either way.")

# Each entry: the session the engine flagged (`decision`), its preset and direction as the engine named them.
LIBRARY: List[Dict[str, Any]] = [
    {"id": "nvda-2024-01", "symbol": "NVDA", "preset": "trend_pullback", "direction": "bull", "decision": "2024-01-05", "title": "NVDA, January 2024",
     "question": "The rule flagged a pullback to the 21-day EMA in an uptrend. Would you take it, and where would you be wrong?", "start_hint": "December 2023"},
    {"id": "spy-2024-03", "symbol": "SPY", "preset": "donchian_55", "direction": "bull", "decision": "2024-03-20", "title": "SPY, March 2024",
     "question": "The rule flagged a close above the 55-session high. Would you take it, and where would you be wrong?", "start_hint": "February 2024"},
    {"id": "meta-2022-01", "symbol": "META", "preset": "donchian_20", "direction": "bear", "decision": "2022-01-21", "title": "META, January 2022",
     "question": "The rule flagged a close below the 20-session low. Would you take it, and where would you be wrong?", "start_hint": "December 2021"},
    {"id": "aapl-2025-02", "symbol": "AAPL", "preset": "ema_cross", "direction": "bull", "decision": "2025-02-14", "title": "AAPL, February 2025",
     "question": "The rule flagged the 9-day EMA crossing above the 21-day with the trend. Would you take it, and where would you be wrong?", "start_hint": "January 2025"},
    {"id": "jpm-2024-03", "symbol": "JPM", "preset": "donchian_55", "direction": "bull", "decision": "2024-03-19", "title": "JPM, March 2024",
     "question": "The rule flagged a close above the 55-session high. Would you take it, and where would you be wrong?", "start_hint": "February 2024"},
    {"id": "xom-2023-03", "symbol": "XOM", "preset": "rsi_oversold", "direction": "bull", "decision": "2023-03-20", "title": "XOM, March 2023",
     "question": "The rule flagged the RSI recovering from oversold. Would you take it, and where would you be wrong?", "start_hint": "February 2023"},
]

_CACHE: Dict[str, Any] = {}
_LOCK = threading.Lock()
_TTL = 6 * 3600.0


def entry(rid: str) -> Optional[Dict[str, Any]]:
    return next((e for e in LIBRARY if e["id"] == rid), None)


def library() -> Dict[str, Any]:
    return {"version": VERSION, "scope": SCOPE, "lead": LEAD, "review": REVIEW,
            "replays": [{k: e[k] for k in ("id", "symbol", "title", "question", "start_hint")} for e in LIBRARY]}


def _history(provider, sym: str) -> pd.DataFrame:
    with _LOCK:
        hit = _CACHE.get(sym)
        if hit and time.time() - hit[0] < _TTL:
            return hit[1]
    df = provider.history(sym, period="max", interval="1d")
    if df is None or df.empty:
        raise LookupError("No price history came back for {}.".format(sym))
    df = df.dropna(subset=["Close"])
    with _LOCK:
        _CACHE[sym] = (time.time(), df)
    return df


def _dates(df: pd.DataFrame) -> List[str]:
    return [pd.Timestamp(i).date().isoformat() for i in df.index]


def _bars(df: pd.DataFrame) -> List[Dict[str, Any]]:
    out = []
    for i, r in df.iterrows():
        d = pd.Timestamp(i).date()
        out.append({"t": int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp() * 1000),
                    "o": round(float(r["Open"]), 4), "h": round(float(r["High"]), 4), "l": round(float(r["Low"]), 4),
                    "c": round(float(r["Close"]), 4), "v": float(r.get("Volume") or 0)})
    return out


def _reading(e: Dict[str, Any], df: pd.DataFrame, bench: pd.DataFrame, through: str) -> Optional[Dict[str, Any]]:
    """The engine's reading of this entry's setup with the history cut at `through`'s close."""
    cut = df[[d <= through for d in _dates(df)]]
    bcut = bench[[d <= through for d in _dates(bench)]]
    close = session_mod.regular_close(date.fromisoformat(through))
    res = setups_mod.analyse(e["symbol"], cut, bcut, [e["preset"]], (e["direction"],), {}, "daily", None, now=close)
    row = next((r for r in res.get("rows") or [] if r["preset"] == e["preset"] and r["direction"] == e["direction"]), None)
    if not row:
        return None
    keep = ("label", "status", "status_at", "armed_at", "trigger", "trigger_level", "invalidation", "explanation", "note",
            "checks", "conditions", "direction")
    return {k: row.get(k) for k in keep}


def _splits_since(df: pd.DataFrame, through: str) -> Optional[float]:
    if "Stock Splits" not in df.columns:
        return None
    s = df["Stock Splits"]
    f = 1.0
    for d, v in zip(_dates(df), s.values):
        if d > through and v and float(v) > 0:
            f *= float(v)
    return f if f != 1.0 else None


def step(provider, rid: str, at: int) -> Dict[str, Any]:
    """The replay at `at` sessions from its decision (-LEAD .. REVIEW): the bars up to then and nothing after."""
    e = entry(rid)
    if not e:
        raise KeyError(rid)
    at = max(-LEAD, min(REVIEW, int(at)))
    df = _history(provider, e["symbol"])
    bench = _history(provider, "SPY")
    dates = _dates(df)
    if e["decision"] not in dates:
        raise LookupError("The feed no longer has the {} session for {}.".format(e["decision"], e["symbol"]))
    d0 = dates.index(e["decision"])
    if d0 + REVIEW >= len(dates):
        raise LookupError("Fewer than {} sessions have passed since {}.".format(REVIEW, e["decision"]))
    cut = d0 + at
    through = dates[cut]
    lo = max(0, d0 - LEAD - WARMUP)
    shown = df.iloc[lo:cut + 1]
    phase = "before" if at < 0 else "decision" if at == 0 else "review" if at == REVIEW else "after"
    out: Dict[str, Any] = {
        "id": rid, "symbol": e["symbol"], "title": e["title"], "question": e["question"], "version": VERSION,
        "at": at, "lead": LEAD, "review": REVIEW, "phase": phase, "through": through,
        "decision_date": e["decision"] if at >= 0 else None,
        "bars": _bars(shown), "first_replayed": max(0, d0 - LEAD - lo),
        "reading": _reading(e, df, bench, through), "scope": SCOPE, "revised": REVISED,
    }
    if phase == "review":
        dec = _reading(e, df, bench, e["decision"]) or {}
        item = {"key": rid, "symbol": e["symbol"], "direction": e["direction"], "setup": dec.get("label") or e["preset"],
                "state": dec.get("status") or "armed", "close": float(df["Close"].iloc[d0]),
                "trigger_level": dec.get("trigger_level"), "invalidation": dec.get("invalidation")}
        out["at_decision"] = dec
        out["rule_outcome"] = shortlist_mod.outcome(item, df[["Close"]].iloc[:d0 + REVIEW + 1], e["decision"], REVIEW)
        f = _splits_since(df, e["decision"])
        out["revision"] = ("{} has split since: {:g} new shares for each old one. On the day, the quoted prices were {:g} "
                           "times the ones on this chart.".format(e["symbol"], f, f) if f else
                           "No split since: the closes here are the closes quoted that day.")
    return out
