"""Whether Optic's own reads predict anything: recorded first, tested later.

Options audit O3. The Swing tab's composite score, its gamma regime and its
call and put walls are presented as reads on what comes next, and none of them
has been shown to predict anything. Testing them on history is not possible
honestly: the inputs (news, the chain's open interest, the feed's quotes) are
not kept, so a backtest would score today's code on data it never saw. What is
possible is to start keeping them.

**What is recorded.** Once per symbol per ET trading day, the first time the
tab or a scan reads the symbol during the session, exactly as the engine
reported it then: the price, the composite and its components, the stance,
the gamma regime, net GEX, the flip, the call and put walls, two placebo
levels beside each wall (the strikes two listed steps either side of it), the
30-day IV and whether macro was in the score. Rows are never updated (the table
refuses it), so nothing can be backfilled with hindsight.

**What is tested, and against what.** Each claim has a baseline it must beat,
and none is reported before it has enough observations to mean something:

* *Composite score.* The daily cross-sectional rank correlation (Spearman)
  between the score and the next 10 trading days' return, averaged over days,
  against the same correlation for plain 20-day momentum and against shuffled
  scores (a permutation test within each day). Returns run from the record
  day's close, so the rest of that session is not credited to the score.
* *Gamma regime.* Whether moves are smaller after a positive reading than a
  negative one, over 1 and 5 days, with each move divided by the move the
  recorded IV implied, so a calm market is not credited to the regime.
* *Walls.* How often price touches a wall within 5 days and closes back on the
  near side that day, against the same rate for the placebo strikes beside it.
* *Swing setups.* From the setup history the alert path already keeps
  (app/signal_history.py): each trigger's direction-signed change at 5, 10 and
  20 candles, minus SPY's change over the same candles.

The minimums are deliberately conservative (MINIMUMS). A tested result is a
description of what happened in the recorded window, not a guarantee; a claim
that beats its baseline once can stop doing so.
"""

from __future__ import annotations

import json
import math
import os
import random
import sqlite3
import threading
from datetime import date, datetime, time as dtime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ET = ZoneInfo("America/New_York")
DB_PATH = os.path.join(os.environ.get("TRACKER_DATA_DIR", "data"), "signal_archive.db")
# 2026-10-24: the composite lost its macro input (swing.WEIGHTS). Reads are compared only with reads of the same
# version, so a day that straddles the change is two groups rather than one.
RULE_VERSION = "2026-10-24"
_LOCK = threading.Lock()

# Not in the first quarter hour, when quotes and the chain are still settling.
SESSION_START = dtime(9, 45)
SESSION_END = dtime(16, 0)

COMPOSITE_HORIZON = 10
MOMENTUM_LOOKBACK = 20
REGIME_HORIZONS = (1, 5)
WALL_HORIZON = 5
SETUP_HORIZONS = (5, 10, 20)
PERMUTATIONS = 500
MIN_NAMES_PER_DAY = 5

MINIMUMS = {
    "composite": {"observations": 200, "days": 20},
    "regime": {"per_regime": 100},
    "walls": {"touches": 50},
    "setups": {"observations": 50},
}

CLAIMS = {
    "composite": "The composite score ranks which stocks do better over the next two weeks.",
    "regime": "Moves are smaller after a positive gamma reading than after a negative one.",
    "walls": "Price tends to stall at the call and put walls.",
    "setups": "Swing setups are followed by moves in their direction, beyond the market's.",
}

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS reads (
        symbol TEXT NOT NULL, day TEXT NOT NULL, recorded_at TEXT NOT NULL,
        spot REAL, composite REAL, stance TEXT, components TEXT NOT NULL DEFAULT '{}',
        macro_included INTEGER NOT NULL DEFAULT 0,
        regime TEXT, net_gex REAL, flip REAL, call_wall REAL, put_wall REAL,
        placebo TEXT NOT NULL DEFAULT '{}', iv30 REAL, index_like INTEGER NOT NULL DEFAULT 0,
        rule_version TEXT NOT NULL, PRIMARY KEY (symbol, day))""",
    """CREATE TRIGGER IF NOT EXISTS reads_immutable BEFORE UPDATE ON reads
       BEGIN SELECT RAISE(ABORT, 'archived reads are immutable'); END""",
]


def _connect() -> sqlite3.Connection:
    d = os.path.dirname(DB_PATH)
    if d:
        os.makedirs(d, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    for stmt in SCHEMA:
        conn.execute(stmt)
    return conn


def _num(x: Any) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def in_session(now: Optional[datetime] = None) -> bool:
    et = (now or datetime.now(timezone.utc)).astimezone(ET)
    return et.weekday() < 5 and SESSION_START <= et.time() < SESSION_END


def placebo_strikes(strikes: Iterable[float], wall: Optional[float], spot: float,
                    above: bool, steps: int = 2) -> List[float]:
    """The listed strikes `steps` places either side of a wall, on the wall's
    side of the price: levels at much the same distance that the model did not
    single out."""
    if wall is None:
        return []
    ks = sorted({float(k) for k in strikes if _num(k) is not None})
    if wall not in ks:
        return []
    i = ks.index(wall)
    out = []
    for j in (i - steps, i + steps):
        if 0 <= j < len(ks):
            k = ks[j]
            if (k > spot) if above else (k < spot):
                out.append(k)
    return out


def record(symbol: str, spot: Optional[float], verdict: Dict[str, Any], gex: Dict[str, Any],
           *, strikes: Iterable[float] = (), iv30: Optional[float] = None,
           macro_included: bool = False, index_like: bool = False,
           now: Optional[datetime] = None) -> bool:
    """Keep the first in-session read of the day. False when none was kept."""
    now = now or datetime.now(timezone.utc)
    if not in_session(now) or not symbol or _num(spot) is None:
        return False
    verdict = verdict or {}
    gex = gex if isinstance(gex, dict) and "error" not in gex else {}
    levels = gex.get("levels") or {}
    regime = gex.get("regime") or {}
    cw = _num((levels.get("call_wall") or {}).get("strike"))
    pw = _num((levels.get("put_wall") or {}).get("strike"))
    strikes = list(strikes)
    placebo = {"call": placebo_strikes(strikes, cw, float(spot), True),
               "put": placebo_strikes(strikes, pw, float(spot), False)}
    row = (symbol.upper(), now.astimezone(ET).date().isoformat(), now.isoformat(), float(spot),
           _num(verdict.get("composite_score")), verdict.get("stance"),
           json.dumps(verdict.get("components") or {}), int(bool(macro_included)),
           regime.get("state"), _num((gex.get("totals") or {}).get("net_gex")),
           _num(regime.get("flip_point")), cw, pw, json.dumps(placebo), _num(iv30),
           int(bool(index_like)), RULE_VERSION)
    try:
        with _LOCK, _connect() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO reads (symbol, day, recorded_at, spot, composite, stance, components,"
                " macro_included, regime, net_gex, flip, call_wall, put_wall, placebo, iv30, index_like,"
                " rule_version) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", row)
            return cur.rowcount == 1
    except sqlite3.Error:
        return False


def reads() -> List[Dict[str, Any]]:
    try:
        with _LOCK, _connect() as conn:
            out = [dict(r) for r in conn.execute("SELECT * FROM reads ORDER BY day, symbol")]
    except sqlite3.Error:
        return []
    for r in out:
        r["placebo"] = json.loads(r.get("placebo") or "{}")
        r["components"] = json.loads(r.get("components") or "{}")
    return out


LEVEL_FIELDS = ("symbol", "day", "recorded_at", "spot", "regime", "net_gex", "flip", "call_wall",
                "put_wall", "iv30", "index_like", "rule_version")


def levels(symbol: Optional[str] = None, since: Optional[str] = None,
           until: Optional[str] = None) -> List[Dict[str, Any]]:
    """The recorded walls and flip, one row per symbol and day, as they were read.

    For comparing Optic's levels with another vendor's on the same days (asked
    2026-10-23 for SpotGamma's SPY/SPX levels). The scores and components stay
    out: this is the levels and the price they were read at, nothing else.
    """
    sql, args = "SELECT {} FROM reads WHERE 1=1".format(", ".join(LEVEL_FIELDS)), []
    if symbol:
        sql += " AND symbol = ?"
        args.append(symbol.upper())
    if since:
        sql += " AND day >= ?"
        args.append(since)
    if until:
        sql += " AND day <= ?"
        args.append(until)
    try:
        with _LOCK, _connect() as conn:
            return [dict(r) for r in conn.execute(sql + " ORDER BY day, symbol", args)]
    except sqlite3.Error:
        return []


# ------------------------------------------------------------------ testing

def _closes_after(bars: pd.DataFrame, day: str) -> Optional[int]:
    """Position of the record day's candle in a daily frame, or None."""
    if bars is None or bars.empty:
        return None
    idx = pd.DatetimeIndex(bars.index)
    if idx.tz is not None:
        idx = idx.tz_convert(ET).tz_localize(None)
    days = idx.normalize()
    hit = np.where(days == pd.Timestamp(day))[0]
    return int(hit[0]) if len(hit) else None


def _spearman(a: Sequence[float], b: Sequence[float]) -> Optional[float]:
    if len(a) < 3:
        return None
    ra = pd.Series(a).rank().to_numpy()
    rb = pd.Series(b).rank().to_numpy()
    if np.std(ra) == 0 or np.std(rb) == 0:
        return None
    return float(np.corrcoef(ra, rb)[0, 1])


def _status(name: str, n: Dict[str, int], since: Optional[str]) -> Dict[str, Any]:
    need = MINIMUMS[name]
    short = {k: (n.get(k, 0), v) for k, v in need.items() if n.get(k, 0) < v}
    return {"claim": CLAIMS[name], "since": since, "counts": n, "needed": need,
            "status": "collecting" if short else "tested", "result": None}


def test_composite(rows: List[Dict[str, Any]], bars: Dict[str, pd.DataFrame],
                   rng: Optional[random.Random] = None) -> Dict[str, Any]:
    h, lb = COMPOSITE_HORIZON, MOMENTUM_LOOKBACK
    obs = []
    for r in rows:
        if r.get("composite") is None:
            continue
        b = bars.get(r["symbol"])
        i = _closes_after(b, r["day"])
        if i is None or i + h >= len(b):
            continue
        c = b["Close"].to_numpy(dtype=float)
        mom = c[i] / c[i - lb] - 1 if i - lb >= 0 else None
        obs.append({"day": r["day"], "group": (r["day"], r["macro_included"], r.get("rule_version")),
                    "score": r["composite"],
                    "stance": r.get("stance"), "fwd": c[i + h] / c[i] - 1, "mom": mom})
    groups: Dict[Any, List[Dict[str, Any]]] = {}
    for o in obs:
        groups.setdefault(o["group"], []).append(o)
    groups = {g: v for g, v in groups.items() if len(v) >= MIN_NAMES_PER_DAY}
    used = [o for v in groups.values() for o in v]
    days = sorted({g[0] for g in groups})
    out = _status("composite", {"observations": len(used), "days": len(days)},
                  min((r["day"] for r in rows), default=None))
    if out["status"] != "tested":
        return out
    ics, moms = [], []
    for g, v in sorted(groups.items()):
        ics.append(_spearman([o["score"] for o in v], [o["fwd"] for o in v]))
        mv = [o for o in v if o["mom"] is not None]
        moms.append(_spearman([o["mom"] for o in mv], [o["fwd"] for o in mv]) if len(mv) >= 3 else None)
    ic = [x for x in ics if x is not None]
    mean_ic = float(np.mean(ic)) if ic else None
    mom_ic = [x for x in moms if x is not None]
    # Shuffled scores within each day: how often chance does as well.
    rng = rng or random.Random(13)
    beat = 0
    for _ in range(PERMUTATIONS):
        vals = []
        for v in groups.values():
            s = [o["score"] for o in v]
            rng.shuffle(s)
            x = _spearman(s, [o["fwd"] for o in v])
            if x is not None:
                vals.append(x)
        if vals and mean_ic is not None and np.mean(vals) >= mean_ic:
            beat += 1
    # Excess return by stance against that day's average.
    by_stance: Dict[str, List[float]] = {}
    for v in groups.values():
        avg = float(np.mean([o["fwd"] for o in v]))
        for o in v:
            by_stance.setdefault(o["stance"] or "none", []).append(o["fwd"] - avg)
    out["result"] = {
        "mean_rank_correlation": None if mean_ic is None else round(mean_ic, 4),
        "momentum_rank_correlation": round(float(np.mean(mom_ic)), 4) if mom_ic else None,
        "shuffled_as_good_pct": round(beat / PERMUTATIONS * 100, 1),
        "excess_return_pct_by_stance": {k: {"n": len(v), "mean": round(float(np.mean(v)) * 100, 3)}
                                        for k, v in sorted(by_stance.items())},
        "horizon_days": h,
        "note": ("Days overlap (each return spans {} trading days), so consecutive days are not "
                 "independent; the shuffle test keeps each day's names together.").format(h),
    }
    return out


def test_regime(rows: List[Dict[str, Any]], bars: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
    acc: Dict[int, Dict[str, List[float]]] = {h: {"positive": [], "negative": []} for h in REGIME_HORIZONS}
    for r in rows:
        if r.get("regime") not in ("positive", "negative") or not r.get("iv30"):
            continue
        b = bars.get(r["symbol"])
        i = _closes_after(b, r["day"])
        if i is None:
            continue
        c = b["Close"].to_numpy(dtype=float)
        for h in REGIME_HORIZONS:
            if i + h < len(c):
                implied = r["iv30"] / 100.0 * math.sqrt(h / 252.0)
                acc[h][r["regime"]].append(abs(c[i + h] / c[i] - 1) / implied)
    first = acc[REGIME_HORIZONS[-1]]
    out = _status("regime", {"per_regime": min(len(first["positive"]), len(first["negative"])),
                             "positive": len(first["positive"]), "negative": len(first["negative"])},
                  min((r["day"] for r in rows if r.get("regime")), default=None))
    if out["status"] != "tested":
        return out
    res = {}
    for h, d in acc.items():
        p, n = np.array(d["positive"]), np.array(d["negative"])
        se = math.sqrt(p.var(ddof=1) / len(p) + n.var(ddof=1) / len(n)) if len(p) > 1 and len(n) > 1 else None
        res["{}d".format(h)] = {
            "positive_mean_move_vs_implied": round(float(p.mean()), 3),
            "negative_mean_move_vs_implied": round(float(n.mean()), 3),
            "difference_t": round(float((n.mean() - p.mean()) / se), 2) if se else None,
            "n_positive": len(p), "n_negative": len(n)}
    out["result"] = {"by_horizon": res,
                     "note": "1.0 is a move the size the recorded IV implied; below 1.0 is calmer than priced."}
    return out


def _touch(b: pd.DataFrame, i: int, level: float, above: bool, h: int) -> Optional[bool]:
    """None if not touched in h days; else whether the first touch day closed
    back on the near side."""
    for k in range(i + 1, min(i + h + 1, len(b))):
        hi, lo, cl = float(b["High"].iloc[k]), float(b["Low"].iloc[k]), float(b["Close"].iloc[k])
        if above and hi >= level:
            return cl < level
        if not above and lo <= level:
            return cl > level
    return None


def test_walls(rows: List[Dict[str, Any]], bars: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
    wall, plac = [], []
    for r in rows:
        b = bars.get(r["symbol"])
        i = _closes_after(b, r["day"])
        if i is None or i + 1 >= len(b) or not {"High", "Low", "Close"} <= set(b.columns):
            continue
        for side, level, above in (("call", r.get("call_wall"), True), ("put", r.get("put_wall"), False)):
            if level is None or (above and level <= r["spot"]) or (not above and level >= r["spot"]):
                continue
            t = _touch(b, i, level, above, WALL_HORIZON)
            if t is not None:
                wall.append(t)
            for p in (r.get("placebo") or {}).get(side, []):
                tp = _touch(b, i, p, above, WALL_HORIZON)
                if tp is not None:
                    plac.append(tp)
    out = _status("walls", {"touches": len(wall), "placebo_touches": len(plac)},
                  min((r["day"] for r in rows if r.get("call_wall") or r.get("put_wall")), default=None))
    if out["status"] != "tested" or not plac:
        if out["status"] == "tested":
            out["status"] = "collecting"
        return out
    out["result"] = {"wall_hold_pct": round(sum(wall) / len(wall) * 100, 1),
                     "placebo_hold_pct": round(sum(plac) / len(plac) * 100, 1),
                     "horizon_days": WALL_HORIZON,
                     "note": "Held: the first day price reached the level, it closed back on the near side."}
    return out


def test_setups(observations: List[Dict[str, Any]], spy: Optional[pd.DataFrame]) -> Dict[str, Any]:
    """`observations`: {direction, horizon, trigger_day, observed_day, change_pct}
    from the setup history, daily timeframe only."""
    spy_close = None
    if spy is not None and not spy.empty:
        idx = pd.DatetimeIndex(spy.index)
        if idx.tz is not None:
            idx = idx.tz_convert(ET).tz_localize(None)
        spy_close = pd.Series(spy["Close"].to_numpy(dtype=float), index=idx.normalize())
    by_h: Dict[int, List[float]] = {h: [] for h in SETUP_HORIZONS}
    for o in observations:
        h = o.get("horizon")
        if h not in by_h or spy_close is None:
            continue
        try:
            a = spy_close.asof(pd.Timestamp(o["trigger_day"]))
            z = spy_close.asof(pd.Timestamp(o["observed_day"]))
        except Exception:                                         # noqa: BLE001
            continue
        if not (a and z) or not math.isfinite(a) or not math.isfinite(z):
            continue
        sign = 1.0 if o["direction"] == "bull" else -1.0
        by_h[h].append(sign * (o["change_pct"] - (z / a - 1) * 100))
    smallest = min(len(v) for v in by_h.values())
    out = _status("setups", {"observations": smallest, **{"after_{}".format(h): len(v) for h, v in by_h.items()}},
                  min((o["trigger_day"] for o in observations), default=None))
    if out["status"] != "tested":
        return out
    out["result"] = {"by_horizon": {
        "{} candles".format(h): {"n": len(v), "mean_excess_pct": round(float(np.mean(v)), 3),
                                 "beat_spy_pct": round(float(np.mean(np.array(v) > 0)) * 100, 1)}
        for h, v in by_h.items()},
        "note": "Direction-signed change in the stock minus SPY's change over the same candles."}
    return out


def evaluate(rows: List[Dict[str, Any]], load_bars: Callable[[List[str]], Dict[str, pd.DataFrame]],
             setup_obs: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Every claim's status, fetching prices only for a claim with enough rows
    to be tested at all."""
    setup_obs = setup_obs or []
    days = sorted({r["day"] for r in rows})
    with_score = [r for r in rows if r.get("composite") is not None]
    regime_counts = {k: sum(1 for r in rows if r.get("regime") == k) for k in ("positive", "negative")}
    wall_rows = [r for r in rows if r.get("call_wall") or r.get("put_wall")]
    could = {
        "composite": len(with_score) >= MINIMUMS["composite"]["observations"]
        and len(days) >= MINIMUMS["composite"]["days"],
        "regime": min(regime_counts.values()) >= MINIMUMS["regime"]["per_regime"],
        # A wall is touched on a fraction of days; the read count is a floor.
        "walls": len(wall_rows) >= MINIMUMS["walls"]["touches"],
    }
    syms = sorted({r["symbol"] for r in rows}) if any(could.values()) else []
    want_spy = len(setup_obs) >= MINIMUMS["setups"]["observations"]
    bars = load_bars(syms + (["SPY"] if want_spy and "SPY" not in syms else [])) if (syms or want_spy) else {}
    out = {
        "composite": test_composite(rows, bars) if could["composite"] else _status(
            "composite", {"observations": len(with_score), "days": len(days)}, days[0] if days else None),
        "regime": test_regime(rows, bars) if could["regime"] else _status(
            "regime", {"per_regime": min(regime_counts.values()), **regime_counts},
            min((r["day"] for r in rows if r.get("regime")), default=None)),
        "walls": test_walls(rows, bars) if could["walls"] else _status(
            "walls", {"touches": 0, "reads_with_walls": len(wall_rows)},
            min((r["day"] for r in wall_rows), default=None)),
        "setups": test_setups(setup_obs, bars.get("SPY")) if want_spy else _status(
            "setups", {"observations": len(setup_obs)},
            min((o["trigger_day"] for o in setup_obs), default=None)),
    }
    return {"claims": out, "rule_version": RULE_VERSION, "reads": len(rows), "days": len(days),
            "first_day": days[0] if days else None, "method": __doc__.split("**What is tested")[0].strip()}
