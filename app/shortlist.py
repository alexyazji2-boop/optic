"""The nightly setup shortlist (roadmap stage 5, 2026-10-22).

A short, bounded list of the setups app/analytics/setups.py finds on the last
completed daily candle, across one documented universe (Optic Portfolio's
curated list: paper.CURATED_UNIVERSE). It is not a list of "best trades" and
it has no quota: on a quiet night it is empty, and says so.

What it adds to the setups engine, and nothing else:

* **A versioned selection rule** (SELECTION_VERSION, RULES) deciding which of
  the engine's rows make the list, so a change to what qualifies is a new
  version, never a silent edit of an old list.
* **Catalysts for the names selected**: the next earnings date inside the
  setup's horizon, and a material or pending news catalyst (news.py's event
  detectors, which date earnings from the calendar).
* **A stored snapshot per evaluation date**, and **outcomes recorded later for
  every entry**, the ones that went nowhere or failed included. The record
  that builds up is forward: setups listed before their outcome was known. It
  is never a backtest, and it says how many entries it rests on.

The evaluation time is the close of the last completed session (setups.daily_bars
leaves a candle still forming out). Nothing here calls a model.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

# .1 let in any armed setup still waiting (up to 5 sessions old): 42 of 86 names qualified on the
# 2026-10-22 close, half the universe, which is not a shortlist. .2 keeps only what changed on the last
# session, and breaks ties on measured participation rather than the alphabet.
SELECTION_VERSION = "shortlist-2026-10-22.2"
MAX_ITEMS = 15
OUTCOME_SESSIONS = 10
RULES = [
    "Universe: Optic Portfolio's curated list of large US stocks and index, sector and commodity funds, "
    "about 85 names chosen for liquidity, not for performance.",
    "Setups: the setups engine's presets on completed daily candles, both directions, excluding "
    "presets marked experimental.",
    "A setup qualifies when it triggered on the last completed session with every condition met, or "
    "armed on that session with every condition except its trigger in place.",
    "One setup per name: the one with the most conditions met, a triggered one before an armed one.",
    "At most {} names: triggered before armed, then by the setup bar's volume against its 20-session "
    "average (participation, a tie-break, not a forecast); any others that qualified are named, not hidden.".format(MAX_ITEMS),
    "Outcomes are recorded {} sessions later for every entry: whether an armed setup triggered, "
    "whether the invalidation was closed through, and the move from the evaluation close.".format(OUTCOME_SESSIONS),
]
HORIZON = "Days to a few weeks: a daily swing setup, which expires if its trigger does not come within 5 sessions."

_LOCK = threading.Lock()


def _dir() -> str:
    d = os.environ.get("TRACKER_DATA_DIR") or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(d, exist_ok=True)
    return d


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(os.path.join(_dir(), "shortlist.db"), timeout=10)
    c.execute("CREATE TABLE IF NOT EXISTS lists (as_of TEXT PRIMARY KEY, version TEXT, built_at TEXT, body TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS outcomes (as_of TEXT, key TEXT, recorded_at TEXT, body TEXT, PRIMARY KEY (as_of, key))")
    return c


# ------------------------------------------------------------------ selection

def _groups(row: Dict[str, Any]) -> Dict[str, bool]:
    return {g["group"]: bool(g.get("passed")) for g in ((row.get("conditions") or {}).get("groups") or [])}


def qualifies(row: Dict[str, Any], as_of: str) -> Optional[str]:
    """Why a row makes the list, or None. Pure: tests drive it on fixtures."""
    if row.get("experimental") or row.get("provisional"):
        return None
    g = _groups(row)
    if row.get("status") == "triggered" and row.get("status_at") == as_of and g and all(g.values()):
        return "Every condition met, and it triggered on the last completed session."
    if (row.get("status") == "armed" and (row.get("armed_at") or row.get("status_at")) == as_of
            and g and all(v for k, v in g.items() if k != "Trigger")):
        return "Every condition but the trigger holds; it waits for {}.".format(
            (row.get("trigger") or "its trigger").rstrip(".").lower())
    return None


def select(rows_by_symbol: Dict[str, List[Dict[str, Any]]], as_of_by_symbol: Dict[str, str]) -> Dict[str, Any]:
    picked: List[Dict[str, Any]] = []
    for sym, rows in rows_by_symbol.items():
        best = None
        for r in rows:
            why = qualifies(r, as_of_by_symbol.get(sym, ""))
            if not why:
                continue
            c = r.get("conditions") or {}
            vol = (r.get("volume") or {}).get("ratio")
            rank = (1 if r["status"] == "triggered" else 0, (c.get("met") or 0) / max(c.get("of") or 1, 1),
                    float(vol) if isinstance(vol, (int, float)) and np.isfinite(vol) else 0.0)
            if best is None or rank > best[0]:
                best = (rank, r, why)
        if best:
            picked.append({**best[1], "why_included": best[2], "_rank": best[0]})
    picked.sort(key=lambda r: (-r["_rank"][0], -r["_rank"][1], -r["_rank"][2], r["symbol"]))
    shown, rest = picked[:MAX_ITEMS], picked[MAX_ITEMS:]
    for r in picked:
        r.pop("_rank", None)
    return {"items": shown, "also_qualified": [r["symbol"] for r in rest]}


def evidence(row: Dict[str, Any]) -> Dict[str, List[str]]:
    """The engine's own checks, split: what holds supports the setup, what fails conflicts with it.
    A failed trigger on an armed setup is the wait, not a conflict."""
    sup, con = [], []
    for c in row.get("checks") or []:
        rule = str(c.get("rule") or "").strip()
        if not rule:
            continue
        if c.get("passed") is True:
            sup.append(rule)
        elif c.get("passed") is False and not (c.get("group") == "Trigger" and row.get("status") == "armed"):
            con.append("Not in place: " + (rule if rule[1:2].isupper() else rule[0].lower() + rule[1:]))
    return {"supporting": sup[:6], "conflicting": con[:6]}


# ------------------------------------------------------------------ building

def build(provider, news_for=None, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Evaluate the universe once and return the shortlist (not stored)."""
    from . import paper
    from .analytics import setups as setups_mod
    universe = list(paper.CURATED_UNIVERSE)
    bench = "SPY"
    frames = provider.batch_history(sorted(set(universe) | {bench}), period="2y", interval="1d") or {}
    rows_by, as_of_by, failed, forming = {}, {}, [], None
    for sym in universe:
        df = frames.get(sym)
        if df is None or getattr(df, "empty", True):
            failed.append(sym)
            continue
        try:
            res = setups_mod.analyse(sym, df, frames.get(bench), None, ("bull", "bear"), {}, "daily", None, now=now)
        except Exception:                                          # noqa: BLE001 - one name must not cost the rest
            failed.append(sym)
            continue
        if not res.get("available"):
            failed.append(sym)
            continue
        rows_by[sym], as_of_by[sym] = res["rows"], res["as_of"]
        forming = forming or res.get("forming")
    if not rows_by:
        return {"available": False, "version": SELECTION_VERSION, "universe_size": len(universe), "failed": failed,
                "reason": "No prices came back for the {} names; the data source may be refusing requests. "
                          "It is tried again within half an hour.".format(len(universe))}
    sel = select(rows_by, as_of_by)
    as_of = max(as_of_by.values())
    items = []
    for r in sel["items"]:
        ev = evidence(r)
        cat = catalysts(provider, r["symbol"], news_for, r.get("as_of"))
        items.append({
            "symbol": r["symbol"], "direction": r["direction"], "setup": r["label"], "preset": r["preset"], "family": r.get("family"),
            "horizon": HORIZON, "state": r["status"], "state_at": r.get("status_at"), "armed_at": r.get("armed_at"),
            "trigger": r.get("trigger"), "trigger_level": _f(r.get("trigger_level")), "invalidation": _f(r.get("invalidation")),
            "close": _f(_last_close(frames.get(r["symbol"]), r.get("as_of"))), "volume_ratio": _f((r.get("volume") or {}).get("ratio")),
            "conditions": {"met": (r.get("conditions") or {}).get("met"), "of": (r.get("conditions") or {}).get("of")},
            "supporting": ev["supporting"], "conflicting": ev["conflicting"] + cat["conflicting"],
            "catalysts": cat["items"], "data_as_of": r.get("as_of"), "why_included": r["why_included"],
            "explanation": r.get("explanation"), "key": "{}:{}:{}".format(r["symbol"], r["preset"], r["direction"]),
        })
    return {
        "as_of": as_of, "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "version": SELECTION_VERSION, "rules": RULES, "universe_size": len(universe), "evaluated": len(rows_by),
        "failed": failed, "forming_excluded": bool(forming), "items": items, "also_qualified": sel["also_qualified"],
        "empty_note": None if items else "Nothing in the universe qualified on the {} close. That is a normal answer.".format(as_of),
    }


def _f(x: Any) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return round(v, 2) if np.isfinite(v) else None


def _last_close(df, as_of: Optional[str]) -> Optional[float]:
    if df is None or getattr(df, "empty", True) or not as_of:
        return None
    s = df["Close"].dropna()
    idx = [pd.Timestamp(i).date().isoformat() for i in s.index]
    for d, v in zip(reversed(idx), reversed(list(s.values))):
        if d <= as_of:
            return float(v)
    return None


def catalysts(provider, sym: str, news_for=None, as_of: Optional[str] = None) -> Dict[str, Any]:
    """The next report inside the horizon, and a dated or headline catalyst from news.py's detectors."""
    from . import news as news_mod
    items, conflicting = [], []
    try:
        ed = provider.earnings_date(sym)
    except Exception:                                              # noqa: BLE001
        ed = None
    if ed:
        # counted from the evaluation date, the one the setup is read on, not from today
        days = (date.fromisoformat(str(ed)[:10]) - (date.fromisoformat(as_of) if as_of else date.today())).days
        if 0 <= days <= 21:
            items.append({"kind": "earnings", "date": str(ed)[:10], "text": "Reports {} ({} days), inside the horizon.".format(str(ed)[:10], days)})
            conflicting.append("A report in {} days can move the stock either way, whatever the chart says.".format(days))
    if news_for is not None:
        try:
            n = news_for(sym) or {}
            m, p = news_mod.material_catalyst(n), news_mod.pending_catalyst(n)
            for ev in (m.get("events") or [])[:2]:
                items.append({"kind": ev["kind"], "date": ev.get("event_date"), "text": "{}: {} ({}).".format(
                    ev["kind"].capitalize(), ev.get("headline"), ev.get("publisher") or "publisher not given")})
            for ev in (p.get("events") or [])[:1]:
                items.append({"kind": ev["kind"], "date": ev.get("event_date"), "text": "Still ahead: {}.".format(ev.get("headline"))})
        except Exception:                                          # noqa: BLE001
            items.append({"kind": "news", "date": None, "text": "Headlines could not be read for this name."})
    seen, uniq = set(), []
    for it in items:   # the calendar and the news detector both name the same report
        k = (it["kind"], it.get("date"))
        if k not in seen:
            seen.add(k); uniq.append(it)
    return {"items": uniq, "conflicting": conflicting}


# ------------------------------------------------------------------ storage

def save(sl: Dict[str, Any]) -> None:
    if not sl.get("as_of"):
        return
    with _LOCK, _conn() as c:
        c.execute("INSERT OR REPLACE INTO lists VALUES (?,?,?,?)", (sl["as_of"], sl["version"], sl["built_at"], json.dumps(sl)))


def latest() -> Optional[Dict[str, Any]]:
    with _LOCK, _conn() as c:
        row = c.execute("SELECT body FROM lists ORDER BY as_of DESC LIMIT 1").fetchone()
    return json.loads(row[0]) if row else None


def history(limit: int = 60) -> List[Dict[str, Any]]:
    with _LOCK, _conn() as c:
        rows = c.execute("SELECT body FROM lists ORDER BY as_of DESC LIMIT ?", (limit,)).fetchall()
    return [json.loads(r[0]) for r in rows]


# ------------------------------------------------------------------ outcomes

def outcome(item: Dict[str, Any], bars: pd.DataFrame, as_of: str, sessions: int = OUTCOME_SESSIONS) -> Optional[Dict[str, Any]]:
    """What happened in the `sessions` completed sessions after the evaluation close, or None if
    fewer have passed. Pure, so a fixture can check it: closes only, as the engine reads them."""
    s = bars["Close"].dropna()
    dates = [pd.Timestamp(i).date().isoformat() for i in s.index]
    after = [(d, float(v)) for d, v in zip(dates, s.values) if d > as_of]
    if len(after) < sessions:
        return None
    win = after[:sessions]
    base = item.get("close")
    long = item["direction"] == "bull"
    trig, inv = item.get("trigger_level"), item.get("invalidation")
    triggered = item["state"] == "triggered" or (trig is not None and any((c >= trig) if long else (c <= trig) for _, c in win))
    invalid_at = next((d for d, c in win if inv is not None and ((c <= inv) if long else (c >= inv))), None)
    sign = 1 if long else -1
    moves = [sign * (c / base - 1) * 100 for _, c in win] if base else []
    return {"key": item["key"], "symbol": item["symbol"], "direction": item["direction"], "setup": item["setup"],
            "state_then": item["state"], "triggered": bool(triggered), "invalidated_on": invalid_at,
            "move_pct": round(moves[-1], 2) if moves else None, "best_pct": round(max(moves), 2) if moves else None,
            "worst_pct": round(min(moves), 2) if moves else None, "sessions": sessions, "through": win[-1][0]}


def record_outcomes(provider) -> int:
    """Record outcomes for every past entry old enough and not yet recorded."""
    lists = history(200)
    with _LOCK, _conn() as c:
        done = {(a, k) for a, k in c.execute("SELECT as_of, key FROM outcomes").fetchall()}
    todo = [(sl["as_of"], it) for sl in lists for it in sl.get("items") or [] if (sl["as_of"], it["key"]) not in done]
    if not todo:
        return 0
    syms = sorted({it["symbol"] for _, it in todo})
    frames = provider.batch_history(syms, period="6mo", interval="1d") or {}
    n = 0
    for as_of, it in todo:
        df = frames.get(it["symbol"])
        if df is None or getattr(df, "empty", True):
            continue
        out = outcome(it, df, as_of)
        if out is None:
            continue
        with _LOCK, _conn() as c:
            c.execute("INSERT OR IGNORE INTO outcomes VALUES (?,?,?,?)", (as_of, it["key"], datetime.now(timezone.utc).isoformat(timespec="seconds"), json.dumps(out)))
        n += 1
    return n


def record_summary() -> Dict[str, Any]:
    with _LOCK, _conn() as c:
        rows = [json.loads(r[0]) for r in c.execute("SELECT body FROM outcomes").fetchall()]
        first = c.execute("SELECT MIN(as_of) FROM lists").fetchone()[0]
        listed = sum(len(json.loads(r[0]).get("items") or []) for r in c.execute("SELECT body FROM lists").fetchall())
    n = len(rows)
    moves = [r["move_pct"] for r in rows if r.get("move_pct") is not None]
    return {
        "since": first, "entries_listed": listed, "outcomes_recorded": n, "pending": max(listed - n, 0),
        "triggered": sum(1 for r in rows if r["triggered"]), "invalidated": sum(1 for r in rows if r["invalidated_on"]),
        "avg_move_pct": round(sum(moves) / len(moves), 2) if moves else None,
        "positive": sum(1 for m in moves if m > 0),
        "note": ("A forward record: setups listed before their outcome was known, {} sessions later, from the "
                 "evaluation close, before costs. {} recorded; under about 100 it says little, and it is not a "
                 "backtest or a forecast.".format(OUTCOME_SESSIONS, n)),
        "recent": sorted(rows, key=lambda r: r.get("through") or "", reverse=True)[:20],
    }
