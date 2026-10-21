"""Optic's research archive: candidate setups watched forward, with every input recorded.

Research rounds R1 and R2 (2026-10-21, docs/portfolio/RESEARCH-2026-10-21.md) replayed four
price setups with a confluence requirement and two earnings setups on 1993-2026 history and found
**no validated strategy**. Their options-flow, dealer-positioning and news inputs could not be
tested at all, because no history of them exists. This module is the prospective test:

* **Frozen rules.** The setups, categories, stops and exits below are the registered ones, under
  `RULES_VERSION`. Changing any of them is a new version, never an edit of the old one.
* **Everything recorded at the time.** Each trading day after the close it evaluates the list,
  and every setup that is watching, armed or triggered is stored with its evidence, conflicts,
  catalyst status, missing inputs and plan. For a trigger it also keeps the swing snapshot's flow,
  gamma, IV and news reads with their times, which is the only way to test them later.
* **Shadow trades only.** A trigger gets a simulated trade on later daily bars: entry at the next
  open, the registered stop, a 2R target, 45 days, costs charged. Nothing is sized against an
  account, sent to a broker, or added to the three books. The shadow record is not a track record
  until it has enough independent trades, and the payload says so.

Off unless `OPTIC_RESEARCH_BOOK` is set, because it adds a daily round of history requests and a
swing snapshot per trigger. Reading it never calls a provider or a model.
"""
from __future__ import annotations

import json
import logging
import math
import os
import sqlite3
import threading
import urllib.request
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from .analytics import technicals as TA

log = logging.getLogger("optic.research_book")
_ET = ZoneInfo("America/New_York")
_LOCK = threading.RLock()

RULES_VERSION = "rb-2026-10-21"

# The registered constants (research PROTOCOL.md, 2026-10-21). Read by the tests, so a change here
# without a new RULES_VERSION fails loudly.
RVOL_MIN = 1.25
STOP_BUFFER_ATR = 0.25
STOP_FLOOR_ATR = 1.5
STOP_CAP_ATR = 4.0
MAX_GAP_ATR = 1.0
TARGET_R = 2.0
HOLD_DAYS = 45
COOLDOWN_SESSIONS = 5
REACTION_MIN = 0.03
REACTION_RVOL = 2.0
COST_BPS = {"fund": 10.0, "stock": 15.0}      # per side, including 5 of slippage
SECTOR_SPDRS = ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLB", "XLU"]

SETUPS: Dict[str, Dict[str, str]] = {
    "A": {"name": "Trend pullback", "holding": "swing, up to 45 days",
          "context": "an uptrend: close above the 200-day average and the 50-day above the 200-day",
          "location": "a pullback of at least 2 ATR that came within 0.5 ATR of the 50-day average",
          "trigger": "a close above the prior session's high, on an up day"},
    "B": {"name": "Breakout and retest", "holding": "swing, up to 45 days",
          "context": "a close at least 0.25 ATR above the 60-session high within the last 10 sessions",
          "location": "a pullback that came within 0.5 ATR of that level and held",
          "trigger": "a close above the retest session's high, with room of 2R below the 52-week high"},
    "C": {"name": "Failed breakdown and reclaim", "holding": "swing, up to 45 days",
          "context": "a close at least 0.25 ATR below the 60-session low within the last 5 sessions",
          "location": "price back near the broken level",
          "trigger": "a close back above the level and above the prior session's high"},
    "D": {"name": "Range mean reversion", "holding": "swing, up to 45 days",
          "context": "a 60-session range no wider than 8 ATR, moving sideways",
          "location": "a low in the bottom 15% of the range, not more than 0.5 ATR below it",
          "trigger": "an up close above the prior session's high"},
    "G1": {"name": "Post-earnings continuation", "holding": "swing, up to 45 days",
           "context": "an earnings release in the last session (SEC 8-K, item 2.02)",
           "location": "a reaction at least 3 points better than SPY's",
           "trigger": "relative volume of 2 or more and a close in the upper half of the day's range"},
    "G2": {"name": "Post-earnings reversal", "holding": "swing, up to 45 days",
           "context": "an earnings release in the last session, in a stock above its 200-day average",
           "location": "a reaction at least 3 points worse than SPY's",
           "trigger": "relative volume of 2 or more and a close in the upper half of the day's range"},
}

# What the research found, shown with every candidate so nothing here reads as a recommendation.
RESEARCH_STATUS = (
    "No validated strategy. On 1993-2026 history none of these setups, with or without supporting "
    "evidence, beat random entries under the same stops and exits after costs. A strong positive "
    "earnings reaction was the one consistent lead, on survivor-biased stocks. These candidates are "
    "recorded to test them forward, with the options and news inputs that have no history.")
LIMITS = [
    "Shadow trades: simulated on daily bars, never sized against an account or sent anywhere.",
    "Flow, gamma and news are recorded only for triggers, from the swing snapshot taken after the close.",
    "Optic's options flow has no trade side, and its gamma levels assume dealers are long calls and "
    "short puts: models, not observed positions.",
    "Earnings dates are Yahoo's estimate as of the snapshot; past releases come from SEC filings, "
    "whose acceptance time can lag the press release.",
    "A few dozen closed shadow trades say nothing. The record needs hundreds of independent trades.",
]


def enabled() -> bool:
    return os.environ.get("OPTIC_RESEARCH_BOOK", "").strip().lower() in ("1", "true", "yes", "on")


# ------------------------------------------------------------------ storage

def db_path() -> str:
    return os.path.join(os.environ.get("TRACKER_DATA_DIR", "data"), "research_book.db")


SCHEMA = """
CREATE TABLE IF NOT EXISTS rb_signals (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    rules_version TEXT NOT NULL,
    symbol        TEXT NOT NULL,
    setup         TEXT NOT NULL,
    signal_date   TEXT NOT NULL,
    state         TEXT NOT NULL,
    close         REAL,
    evidence      TEXT,
    conflicts     TEXT,
    catalyst      TEXT,
    positioning   TEXT,
    missing       TEXT,
    plan          TEXT,
    recorded_at   TEXT NOT NULL,
    UNIQUE (rules_version, symbol, setup, signal_date)
);
CREATE TABLE IF NOT EXISTS rb_trades (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id     INTEGER NOT NULL UNIQUE,
    rules_version TEXT NOT NULL,
    symbol        TEXT NOT NULL,
    setup         TEXT NOT NULL,
    kind          TEXT NOT NULL,
    status        TEXT NOT NULL,
    signal_date   TEXT NOT NULL,
    signal_close  REAL,
    atr           REAL,
    stop_level    REAL,
    entry_date    TEXT,
    entry         REAL,
    stop          REAL,
    target        REAL,
    exit_date     TEXT,
    exit          REAL,
    reason        TEXT,
    r_gross       REAL,
    cost_r        REAL,
    r_net         REAL,
    mfe           REAL,
    mae           REAL,
    last_close    REAL,
    last_date     TEXT,
    updated_at    TEXT
);
CREATE TABLE IF NOT EXISTS rb_meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS rb_sec (symbol TEXT PRIMARY KEY, fetched_at TEXT, releases TEXT);
"""


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path()) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path(), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with _LOCK, _connect() as conn:
        conn.executescript(SCHEMA)
        have = {r[1] for r in conn.execute("PRAGMA table_info(rb_trades)")}
        for col, kind in (("last_close", "REAL"), ("last_date", "TEXT")):
            if col not in have:
                conn.execute("ALTER TABLE rb_trades ADD COLUMN {} {}".format(col, kind))


def _rows(sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    with _LOCK, _connect() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _num(x: Any, digits: int = 4) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return round(v, digits) if math.isfinite(v) else None


# ------------------------------------------------------------------ inputs

def arrays(df: pd.DataFrame, spy: pd.DataFrame) -> Dict[str, Any]:
    """Daily arrays for one symbol, completed sessions only, aligned to SPY for relative figures."""
    o, h, l, c = (df[k].astype(float).to_numpy() for k in ("Open", "High", "Low", "Close"))
    v = df["Volume"].astype(float).fillna(0.0).to_numpy()
    close = df["Close"].astype(float)
    prev_vol = pd.Series(v).shift(1).rolling(20).mean().to_numpy()
    s = spy["Close"].astype(float).reindex(df.index).ffill().to_numpy()
    return {"o": o, "h": h, "l": l, "c": c, "v": v, "dates": [d.date() for d in pd.to_datetime(df.index)],
            "atr": TA.atr(df, 14).to_numpy(), "sma50": close.rolling(50).mean().to_numpy(),
            "sma200": close.rolling(200).mean().to_numpy(),
            "rvol": np.where(prev_vol > 0, v / np.where(prev_vol > 0, prev_vol, 1.0), np.nan),
            "spy_ret": pd.Series(s).pct_change().to_numpy(), "n": len(c)}


def market_context(frames: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
    """C4 at the latest close: SPY above its 200-day average and breadth of at least 50%."""
    spy = frames.get("SPY")
    out: Dict[str, Any] = {"spy_above_200d": None, "breadth_pct": None, "supportive": None, "missing": []}
    if spy is None or len(spy) < 200:
        out["missing"].append("SPY history")
        return out
    sc = spy["Close"].astype(float)
    out["spy_above_200d"] = bool(sc.iloc[-1] > sc.rolling(200).mean().iloc[-1])
    flags = []
    for s in SECTOR_SPDRS:
        f = frames.get(s)
        if f is None or len(f) < 200:
            out["missing"].append(s)
            continue
        fc = f["Close"].astype(float)
        flags.append(bool(fc.iloc[-1] > fc.rolling(200).mean().iloc[-1]))
    if len(flags) == len(SECTOR_SPDRS):
        out["breadth_pct"] = round(100.0 * sum(flags) / len(flags), 1)
        out["supportive"] = bool(out["spy_above_200d"] and out["breadth_pct"] >= 50.0)
    return out


# ------------------------------------------------------------------ setups

def _stage_A(a: Dict[str, Any], t: int) -> Tuple[str, Optional[float]]:
    o, h, l, c, atr = a["o"], a["h"], a["l"], a["c"], a["atr"][t]
    if not (c[t] > a["sma200"][t] and a["sma50"][t] > a["sma200"][t]):
        return "none", None
    low5 = l[t - 4:t + 1].min()
    if not (low5 <= a["sma50"][t] + 0.5 * atr and h[t - 20:t].max() - low5 >= 2.0 * atr):
        return "watching", None
    if not (c[t] > h[t - 1] and c[t] > o[t]):
        return "armed", low5
    return "triggered", low5


def _stage_B(a: Dict[str, Any], t: int) -> Tuple[str, Optional[float]]:
    h, l, c, atr = a["h"], a["l"], a["c"], a["atr"][t]
    R = h[t - 65:t - 5].max()
    js = [j for j in range(t - 10, t) if c[j] > R + 0.25 * atr]
    if not js:
        return "none", None
    ks = [k for k in range(js[0] + 1, t) if l[k] <= R + 0.5 * atr and c[k] >= R - 0.25 * atr]
    if not ks:
        return "watching", None
    k = ks[-1]
    level = l[k:t + 1].min()
    if not c[t] > h[k]:
        return "armed", level
    h252 = h[max(0, t - 252):t].max()
    stop = level - STOP_BUFFER_ATR * atr
    if h252 > c[t] and h252 - c[t] < TARGET_R * (c[t] - stop):
        return "armed", level
    return "triggered", level


def _stage_C(a: Dict[str, Any], t: int) -> Tuple[str, Optional[float]]:
    h, l, c, atr = a["h"], a["l"], a["c"], a["atr"][t]
    S = l[t - 65:t - 5].min()
    js = [j for j in range(t - 5, t) if c[j] < S - 0.25 * atr]
    if not js:
        return "none", None
    level = l[js[0]:t + 1].min()
    if not (c[t] > S + 0.1 * atr and c[t] > h[t - 1]):
        return "armed", level
    return "triggered", level


def _stage_D(a: Dict[str, Any], t: int) -> Tuple[str, Optional[float]]:
    o, h, l, c, atr = a["o"], a["h"], a["l"], a["c"], a["atr"][t]
    hh, ll = h[t - 60:t].max(), l[t - 60:t].min()
    W = hh - ll
    if not (W <= 8.0 * atr and abs(c[t - 1] - c[t - 60]) <= 0.25 * W):
        return "none", None
    if not (l[t] <= ll + 0.15 * W and l[t] >= ll - 0.5 * atr):
        return "watching", None
    if not (c[t] > o[t] and c[t] > h[t - 1]):
        return "armed", ll - STOP_BUFFER_ATR * atr
    return "triggered", ll - STOP_BUFFER_ATR * atr


STAGES = {"A": _stage_A, "B": _stage_B, "C": _stage_C, "D": _stage_D}


def stage(a: Dict[str, Any], setup: str, t: int) -> Tuple[str, Optional[float]]:
    """(state, stop level) at bar t. A trigger counts only on the first bar of a run, so a
    condition that holds for three sessions is one signal, not three."""
    if t < 270 or not np.isfinite(a["atr"][t]) or a["atr"][t] <= 0:
        return "none", None
    st, level = STAGES[setup](a, t)
    if st == "triggered" and STAGES[setup](a, t - 1)[0] == "triggered":
        return "armed", level
    return st, level


def earnings_stage(a: Dict[str, Any], t: int, reaction_t: Optional[int], setup: str) -> Tuple[str, Optional[float], Dict]:
    """G1 and G2 on the reaction session itself (t == reaction_t)."""
    if reaction_t is None or reaction_t != t or t < 1:
        return "none", None, {}
    reaction = (a["c"][t] / a["c"][t - 1] - 1.0) - a["spy_ret"][t]
    rng = a["h"][t] - a["l"][t]
    loc = (a["c"][t] - a["l"][t]) / rng if rng > 0 else 0.5
    info = {"reaction_vs_spy_pts": _num(reaction * 100, 2), "rvol": _num(a["rvol"][t], 2),
            "close_in_range": _num(loc, 2)}
    if setup == "G1":
        if reaction < REACTION_MIN:
            return "none", None, info
        ok = a["rvol"][t] >= REACTION_RVOL and loc >= 0.5
    else:
        if reaction > -REACTION_MIN or not a["c"][t - 1] > a["sma200"][t - 1]:
            return "none", None, info
        ok = a["rvol"][t] >= REACTION_RVOL and loc >= 0.5
    return ("triggered" if ok else "watching"), a["l"][t], info


def plan(a: Dict[str, Any], t: int, level: float) -> Dict[str, Any]:
    atr = float(a["atr"][t])
    stop = level - STOP_BUFFER_ATR * atr
    return {"entry": "next session's open; skipped if it opens more than {:.0f} ATR above this close "
                     "({:.2f}) or at or below the stop".format(MAX_GAP_ATR, a["c"][t] + MAX_GAP_ATR * atr),
            "stop_level": _num(level, 4), "stop_before_floor": _num(stop, 4), "atr": _num(atr, 4),
            "stop_rule": "{} ATR under the level, at least {} ATR under the fill, skipped past {} ATR".format(
                STOP_BUFFER_ATR, STOP_FLOOR_ATR, STOP_CAP_ATR),
            "target": "{:.0f}R from the fill".format(TARGET_R), "time": "{} calendar days".format(HOLD_DAYS),
            "invalidation": "a trade below the stop, or no fill on the next open"}


# ------------------------------------------------------------- shadow trades

def advance(trade: Dict[str, Any], a: Dict[str, Any]) -> Dict[str, Any]:
    """Move a shadow trade forward on the bars after its signal: fill, then exits.

    Stop first when a bar holds both levels; a gap through a level fills at the open. The same
    rules the research harness used, so the forward record is comparable with the replay.
    """
    t = dict(trade)
    dates = a["dates"]
    try:
        s_i = dates.index(date.fromisoformat(t["signal_date"]))
    except ValueError:
        return t
    if t["status"] == "intended":
        if s_i + 1 >= a["n"]:
            return t
        i0 = s_i + 1
        e = float(a["o"][i0])
        atr = float(t["atr"])
        stop = float(t["stop_level"]) - STOP_BUFFER_ATR * atr
        if e > float(t["signal_close"]) + MAX_GAP_ATR * atr:
            t.update(status="skipped", reason="opened more than {:.0f} ATR above the signal close".format(MAX_GAP_ATR))
            return t
        if e <= stop:
            t.update(status="skipped", reason="opened at or below the stop")
            return t
        if e - stop < STOP_FLOOR_ATR * atr:
            stop = e - STOP_FLOOR_ATR * atr
        if e - stop > STOP_CAP_ATR * atr:
            t.update(status="skipped", reason="stop more than {:.0f} ATR away".format(STOP_CAP_ATR))
            return t
        t.update(status="open", entry_date=dates[i0].isoformat(), entry=e, stop=stop,
                 target=e + TARGET_R * (e - stop), mfe=0.0, mae=0.0)
    if t["status"] != "open":
        return t
    i0 = dates.index(date.fromisoformat(t["entry_date"]))
    e, stop, target = float(t["entry"]), float(t["stop"]), float(t["target"])
    risk = e - stop
    mfe, mae = 0.0, 0.0
    for i in range(i0, a["n"]):
        lo, hi, op, cl = a["l"][i], a["h"][i], a["o"][i], a["c"][i]
        mfe, mae = max(mfe, (hi - e) / risk), min(mae, (lo - e) / risk)
        px, why = None, None
        if lo <= stop:
            px, why = (min(op, stop) if i > i0 else stop), "stop"
        elif hi >= target:
            px, why = (max(op, target) if i > i0 else target), "target"
        elif (dates[i] - date.fromisoformat(t["entry_date"])).days >= HOLD_DAYS:
            px, why = cl, "time"
        if px is not None:
            side = COST_BPS[t["kind"]] / 1e4
            gross = (px - e) / risk
            cost = side * (e + px) / risk
            t.update(status="closed", exit_date=dates[i].isoformat(), exit=float(px), reason=why,
                     r_gross=_num(gross), cost_r=_num(cost), r_net=_num(gross - cost))
            break
    t.update(mfe=_num(mfe), mae=_num(mae), last_close=_num(a["c"][-1]), last_date=dates[-1].isoformat(),
             updated_at=_now())
    return t


# ------------------------------------------------------------------ catalysts

def _et_from_acceptance(stored: str) -> Optional[datetime]:
    """EDGAR acceptance time. data.sec.gov labels it UTC but it reads as the true UTC time plus
    the Eastern offset (measured 2026-10-21: JPM, WMT, MSFT, AAPL all match their known release
    times only under that reading)."""
    try:
        naive = datetime.strptime(stored[:19], "%Y-%m-%dT%H:%M:%S")
    except (TypeError, ValueError):
        return None
    for hours in (4, 5):
        et = (naive - timedelta(hours=hours)).replace(tzinfo=timezone.utc).astimezone(_ET)
        if -et.utcoffset().total_seconds() / 3600 == hours:
            return et
    return None


def releases_from_submissions(blob: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Earnings releases (8-K item 2.02) from an EDGAR submissions document, oldest first, with
    the first session that can react to each."""
    recent = ((blob or {}).get("filings") or {}).get("recent") or {}
    out, last = [], None
    for i, form in enumerate(recent.get("form") or []):
        items = ((recent.get("items") or [""] * (i + 1))[i] or "").split(",")
        if form != "8-K" or "2.02" not in items:
            continue
        et = _et_from_acceptance((recent.get("acceptanceDateTime") or [""] * (i + 1))[i])
        if et is None:
            continue
        minutes = et.hour * 60 + et.minute
        timing = "before_open" if minutes < 570 else ("during_session" if minutes < 960 else "after_close")
        out.append({"release_et": et.isoformat(), "date": et.date().isoformat(), "timing": timing})
    out.sort(key=lambda r: r["release_et"])
    kept = []
    for r in out:
        d = date.fromisoformat(r["date"])
        if last is None or (d - last).days > 5:
            kept.append(r)
            last = d
    return kept


def reaction_index(dates: List[date], release: Dict[str, Any]) -> Optional[int]:
    d = date.fromisoformat(release["date"])
    pos = next((i for i, x in enumerate(dates) if x >= d), None)
    if pos is None:
        return None
    if release["timing"] == "after_close" and dates[pos] == d:
        pos += 1
    return pos if pos < len(dates) else None


def sec_releases(symbol: str, cik_lookup: Callable[[str], Optional[int]], fetch: Callable[[str], Dict]) -> List[Dict]:
    """Releases for a symbol, refreshed at most once a day and kept in the archive."""
    rows = _rows("SELECT fetched_at, releases FROM rb_sec WHERE symbol=?", (symbol,))
    if rows:
        try:
            if datetime.fromisoformat(rows[0]["fetched_at"]) > datetime.now(timezone.utc) - timedelta(hours=20):
                return json.loads(rows[0]["releases"])
        except (TypeError, ValueError):
            pass
    cik = cik_lookup(symbol)
    if not cik:
        return []
    rels = releases_from_submissions(fetch("https://data.sec.gov/submissions/CIK%s.json" % str(cik).zfill(10)))
    with _LOCK, _connect() as conn:
        conn.execute("INSERT OR REPLACE INTO rb_sec (symbol, fetched_at, releases) VALUES (?,?,?)",
                     (symbol, _now(), json.dumps(rels)))
    return rels


# ------------------------------------------------------------------ the daily run

def _positioning(snap: Dict[str, Any]) -> Dict[str, Any]:
    """The forward-only reads, as the swing snapshot had them, with when it was taken."""
    if not isinstance(snap, dict):
        return {"available": False}
    verdict = snap.get("verdict") or {}
    comps = verdict.get("components") or {}
    gex = snap.get("gex") or {}
    regime = gex.get("regime") or {}
    totals = gex.get("totals") or {}
    levels = gex.get("levels") or {}
    flow = snap.get("flow") or {}
    plan_ = snap.get("entry_plan") or {}
    pick = plan_.get("recommended") or {}
    wall = lambda k: _num((levels.get(k) or {}).get("strike"), 2)  # noqa: E731
    return {"available": True, "taken_at": snap.get("generated_at") or _now(),
            "composite": _num(verdict.get("composite_score"), 1), "stance": verdict.get("stance"),
            "components": {k: _num(v, 1) for k, v in comps.items()},
            "gamma_regime": regime.get("state"), "net_gex": _num(totals.get("net_gex"), 0),
            "net_vanna_vex": _num(totals.get("net_vanna"), 0),
            "flip": _num(regime.get("flip_point"), 2), "flip_distance_pct": _num(regime.get("flip_distance_pct"), 2),
            "call_wall": wall("call_wall"), "put_wall": wall("put_wall"),
            "flow_score": _num(flow.get("flow_score"), 1), "flow_notes": (flow.get("notes") or [])[:4],
            "iv_verdict": (plan_.get("iv_context") or {}).get("verdict"),
            "recommended_contract": ({k: pick.get(k) for k in ("strike", "expiry", "entry_mid", "delta")}
                                     if pick.get("strike") else None),
            "next_earnings_date": snap.get("next_earnings_date"),
            "caveat": "flow has no trade side; gamma and VEX assume dealers long calls and short puts"}


def evaluate_symbol(symbol: str, kind: str, a: Dict[str, Any], ctx: Dict[str, Any],
                    releases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Every setup's state at the latest completed bar, with its evidence and plan."""
    t = a["n"] - 1
    out = []
    rvol = _num(a["rvol"][t], 2)
    react = [(reaction_index(a["dates"], r), r) for r in releases]
    react = [(i, r) for i, r in react if i is not None]
    last_t, last_rel = (react[-1] if react else (None, None))
    recent = [(i, r) for i, r in react if t - 15 <= i <= t - 1]
    c5 = None
    if kind == "stock" and releases:
        c5 = any((a["c"][i] / a["c"][i - 1] - 1) - a["spy_ret"][i] >= 0.02 and a["c"][t] > a["c"][i - 1] for i, _ in recent)
    est = None
    if last_rel:
        start = date.fromisoformat(last_rel["date"]) + timedelta(days=81)
        est = {"window_start": start.isoformat(), "window_end": (start + timedelta(days=20)).isoformat(),
               "basis": "previous SEC release + 81 to 101 days; the window held the next release 84% of the time"}
    for setup in list(STAGES) + (["G1", "G2"] if kind == "stock" else []):
        if setup in STAGES:
            st, level = stage(a, setup, t)
            extra = {}
        else:
            st, level, extra = earnings_stage(a, t, last_t, setup)
        if st == "none":
            continue
        evidence = {"c2_participation": {"rvol": rvol, "met": None if rvol is None else rvol >= RVOL_MIN,
                                         "rule": "relative volume at least {}".format(RVOL_MIN)},
                    "c4_market": {"spy_above_200d": ctx.get("spy_above_200d"), "breadth_pct": ctx.get("breadth_pct"),
                                  "met": ctx.get("supportive"), "rule": "SPY above its 200-day and breadth at least 50%"},
                    "c5_catalyst": {"met": c5, "rule": "an earnings reaction 2 points better than SPY's in the last 15 sessions, still held"} if kind == "stock" else None}
        evidence.update(extra)
        met = [k for k in ("c2_participation", "c4_market", "c5_catalyst") if evidence.get(k) and evidence[k].get("met")]
        conflicts = []
        if ctx.get("supportive") is False:
            conflicts.append("SPY or breadth below the supportive line")
        if est and date.fromisoformat(est["window_start"]) - a["dates"][t] <= timedelta(days=14):
            conflicts.append("an earnings release may fall inside the first two weeks (estimated window from {})".format(est["window_start"]))
        missing = list(ctx.get("missing") or [])
        if kind == "stock" and not releases:
            missing.append("SEC earnings history")
        out.append({"symbol": symbol, "setup": setup, "state": st, "signal_date": a["dates"][t].isoformat(),
                    "close": _num(a["c"][t], 4), "level": level, "atr": _num(a["atr"][t], 4),
                    "evidence": dict(evidence, supports_met=met, qualifies=len(met) >= 2),
                    "conflicts": conflicts, "missing": missing,
                    "catalyst": {"kind": kind, "last_release": last_rel, "next_window_estimate": est},
                    "plan": plan(a, t, level) if level is not None else None})
    return out


def run_daily(history: Callable[[str], pd.DataFrame], universe: List[str], funds: List[str],
              snapshot_fn: Optional[Callable[[str], Dict]] = None,
              releases_fn: Optional[Callable[[str], List[Dict]]] = None,
              today: Optional[date] = None) -> Dict[str, Any]:
    """One pass: advance open shadow trades, then record today's states. Safe to call twice in
    a day: signals are unique by (rules, symbol, setup, date) and a trade by its signal."""
    init_db()
    today = today or datetime.now(timezone.utc).astimezone(_ET).date()
    frames: Dict[str, pd.DataFrame] = {}
    for sym in sorted(set(universe) | set(SECTOR_SPDRS) | {"SPY"}):
        try:
            df = history(sym)
            if df is not None and len(df):
                df = df[[d.date() <= today for d in pd.to_datetime(df.index)]]
                frames[sym] = df
        except Exception as exc:                                     # noqa: BLE001
            log.info("research book: no history for %s: %s", sym, exc)
    ctx = market_context(frames)
    spy = frames.get("SPY")
    recorded = triggered = advanced = 0
    for sym in universe:
        df = frames.get(sym)
        if df is None or spy is None or len(df) < 280:
            continue
        a = arrays(df, spy)
        kind = "fund" if sym in funds else "stock"
        for tr in _rows("SELECT * FROM rb_trades WHERE symbol=? AND status IN ('intended','open')", (sym,)):
            new = advance(tr, a)
            if new != tr:
                with _LOCK, _connect() as conn:
                    conn.execute("UPDATE rb_trades SET status=?, entry_date=?, entry=?, stop=?, target=?, exit_date=?,"
                                 " exit=?, reason=?, r_gross=?, cost_r=?, r_net=?, mfe=?, mae=?, last_close=?,"
                                 " last_date=?, updated_at=? WHERE id=?",
                                 (new["status"], new.get("entry_date"), new.get("entry"), new.get("stop"),
                                  new.get("target"), new.get("exit_date"), new.get("exit"), new.get("reason"),
                                  new.get("r_gross"), new.get("cost_r"), new.get("r_net"), new.get("mfe"),
                                  new.get("mae"), new.get("last_close"), new.get("last_date"), _now(), tr["id"]))
                advanced += 1
        if a["dates"][-1] != today:
            continue                       # no completed bar for today: nothing new to record
        rels = []
        if kind == "stock" and releases_fn is not None:
            try:
                rels = releases_fn(sym) or []
            except Exception as exc:                                 # noqa: BLE001
                log.info("research book: no SEC releases for %s: %s", sym, exc)
        for row in evaluate_symbol(sym, kind, a, ctx, rels):
            positioning = {"available": False, "reason": "recorded for triggers only"}
            if row["state"] == "triggered" and snapshot_fn is not None:
                try:
                    positioning = _positioning(snapshot_fn(sym))
                except Exception as exc:                             # noqa: BLE001
                    positioning = {"available": False, "reason": "snapshot failed: %s" % str(exc)[:80]}
            if row["state"] == "triggered" and _cooling(sym, row["setup"], a, today):
                row["state"] = "armed"
                row["conflicts"].append("within {} sessions of this setup's last shadow trade".format(COOLDOWN_SESSIONS))
            with _LOCK, _connect() as conn:
                cur = conn.execute(
                    "INSERT OR IGNORE INTO rb_signals (rules_version, symbol, setup, signal_date, state, close, "
                    "evidence, conflicts, catalyst, positioning, missing, plan, recorded_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (RULES_VERSION, sym, row["setup"], row["signal_date"], row["state"], row["close"],
                     json.dumps(row["evidence"], default=str), json.dumps(row["conflicts"]),
                     json.dumps(row["catalyst"], default=str), json.dumps(positioning, default=str),
                     json.dumps(row["missing"]), json.dumps(row["plan"], default=str), _now()))
                if cur.rowcount:
                    recorded += 1
                    if row["state"] == "triggered" and row["level"] is not None:
                        conn.execute(
                            "INSERT OR IGNORE INTO rb_trades (signal_id, rules_version, symbol, setup, kind, status, "
                            "signal_date, signal_close, atr, stop_level, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                            (cur.lastrowid, RULES_VERSION, sym, row["setup"], kind, "intended", row["signal_date"],
                             row["close"], row["atr"], row["level"], _now()))
                        triggered += 1
    with _LOCK, _connect() as conn:
        conn.execute("INSERT OR REPLACE INTO rb_meta (key, value) VALUES ('last_run', ?)",
                     (json.dumps({"at": _now(), "date": today.isoformat(), "recorded": recorded,
                                  "triggered": triggered, "advanced": advanced, "symbols": len(frames)}),))
    return {"recorded": recorded, "triggered": triggered, "advanced": advanced, "symbols": len(frames)}


def _cooling(symbol: str, setup: str, a: Dict[str, Any], today: date) -> bool:
    """One shadow trade at a time per symbol and setup, and none within the cooldown after one."""
    rows = _rows("SELECT status, exit_date FROM rb_trades WHERE symbol=? AND setup=? AND rules_version=?",
                 (symbol, setup, RULES_VERSION))
    for r in rows:
        if r["status"] in ("intended", "open"):
            return True
        if r["status"] == "closed" and r["exit_date"]:
            d = date.fromisoformat(r["exit_date"])
            sessions = sum(1 for x in a["dates"] if d < x <= today)
            if sessions <= COOLDOWN_SESSIONS:
                return True
    return False


def due(now: Optional[datetime] = None) -> bool:
    """After 16:20 ET on a weekday, and not yet run for that date."""
    now = (now or datetime.now(timezone.utc)).astimezone(_ET)
    if now.weekday() >= 5 or now.hour * 60 + now.minute < 16 * 60 + 20:
        return False
    init_db()
    rows = _rows("SELECT value FROM rb_meta WHERE key='last_run'")
    if rows:
        try:
            return json.loads(rows[0]["value"]).get("date") != now.date().isoformat()
        except (TypeError, ValueError):
            return True
    return True


# ------------------------------------------------------------------ the payload

def _load(row: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(row)
    for k in ("evidence", "conflicts", "catalyst", "positioning", "missing", "plan"):
        if out.get(k):
            try:
                out[k] = json.loads(out[k])
            except (TypeError, ValueError):
                pass
    return out


def state() -> Dict[str, Any]:
    """What the page shows. Reads the archive only: no provider call, no model call."""
    init_db()
    meta = _rows("SELECT value FROM rb_meta WHERE key='last_run'")
    last = json.loads(meta[0]["value"]) if meta else None
    latest_date = _rows("SELECT MAX(signal_date) AS d FROM rb_signals WHERE rules_version=?", (RULES_VERSION,))
    d = latest_date[0]["d"] if latest_date else None
    current = [_load(r) for r in _rows(
        "SELECT * FROM rb_signals WHERE rules_version=? AND signal_date=? AND state IN ('armed','triggered') "
        "ORDER BY CASE state WHEN 'triggered' THEN 0 ELSE 1 END, symbol", (RULES_VERSION, d))] if d else []
    watching = _rows("SELECT COUNT(*) AS n FROM rb_signals WHERE rules_version=? AND signal_date=? AND state='watching'",
                     (RULES_VERSION, d))[0]["n"] if d else 0
    trades = _rows("SELECT * FROM rb_trades WHERE rules_version=? ORDER BY signal_date DESC, id DESC LIMIT 120",
                   (RULES_VERSION,))
    closed = [t for t in trades if t["status"] == "closed"]
    r = [t["r_net"] for t in _rows("SELECT r_net FROM rb_trades WHERE rules_version=? AND status='closed'", (RULES_VERSION,))
         if t["r_net"] is not None]
    record = {"closed": len(r), "mean_r": _num(float(np.mean(r)), 3) if r else None,
              "win_rate_pct": _num(100.0 * sum(1 for x in r if x > 0) / len(r), 1) if r else None,
              "judgeable": len(r) >= 300,
              "note": "Shadow trades after costs. Under 300 closed trades the average says nothing."}
    return {"enabled": enabled(), "rules_version": RULES_VERSION, "research_status": RESEARCH_STATUS,
            "limits": LIMITS, "setups": SETUPS, "last_run": last, "as_of_date": d,
            "watching_count": watching, "candidates": current,
            "open": [t for t in trades if t["status"] in ("intended", "open")],
            "recent_closed": closed[:20], "record": record}
