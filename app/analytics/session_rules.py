"""Intraday rules that live inside one session, for the Backtest widget.

The first is the opening-range break with a VWAP retest, from a trading post
(nicholascrown, 2026): "The entry only exists after a qualified break. 1. Price
breaks the opening range, the first 30 minutes. 2. The move extends at least
one full range width past the break. 3. No close back through VWAP on the way.
All three, then the first touch of the line is your entry."

The post gives the entry and nothing else, so the rest is stated here and
adjustable in the widget rather than assumed silently:

* **Stop**: a fixed fraction of the opening range beyond the entry (half a
  range by default). The post's own thesis, that buyers who missed the leg are
  waiting at VWAP, is wrong once price moves well through the line.
* **Target**: a multiple of that risk (2R by default), or none.
* **Flat by the close**, always: it is a day trade.
* One trade a session, the first qualified one, long or short.

**How it is simulated, and why each choice is the cautious one.**

* VWAP is the session's cumulative (typical price x volume) / volume. The
  level an entry rests at is VWAP as of the bar BEFORE the touch, the line a
  trader could see; the bar that touches it fills at that level, or at its open
  if it opened through it (a resting limit fills at the better price).
* "No close back through VWAP" is read on every bar from the break to the bar
  that completes the extension, that bar included.
* If a bar reaches both the stop and the target, the stop is taken: five-minute
  bars do not say which came first. On the entry bar itself a stop counts and a
  target does not, for the same reason.
* Each side pays `cost_bps`, as in the daily backtests.

**Two baselines**, because a rule that trades a stock that trended for sixty
sessions will look good whatever it does:

* *Random timing*: the same trades (same days, same sides, same number of bars
  held) entered at random bars after the opening range, 500 times.
* *The plain break*: entering at the open after the first close outside the
  range, with the same stop, target and close-out. It is the same idea without
  rules 2 and 3 and the wait for VWAP, so the difference between the two is what
  those rules add.

**What the data allows.** The free feed keeps the last 60 sessions of
five-minute bars, so one symbol gives a handful of qualified setups at most.
That is a small sample, and every result says so.
"""

from __future__ import annotations

import math
import random
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

COST_BPS = 5.0
RANDOM_RUNS = 500
SEED = 20261014
SESSION_OPEN = 9 * 60 + 30
SESSION_CLOSE = 16 * 60


def _p(pid, label, kind, default, lo=None, hi=None, step=None):
    out = {"id": pid, "label": label, "kind": kind, "default": default, "min": lo, "max": hi}
    if step is not None:
        out["step"] = step
    return out


ORB_PARAMS = [
    _p("range_minutes", "Opening range (minutes)", "int", 30, 5, 120),
    _p("extension", "Extension past the break (range widths)", "float", 1.0, 0.25, 4.0, 0.25),
    _p("stop_ranges", "Stop beyond the entry (range widths)", "float", 0.5, 0.1, 3.0, 0.1),
    _p("target_r", "Target (multiples of the risk, 0 = hold to the close)", "float", 2.0, 0.0, 10.0, 0.5),
    _p("last_entry", "No entries after (minutes after the open)", "int", 330, 30, 385),
    _p("allow_long", "Take long setups", "bool", True),
    _p("allow_short", "Take short setups", "bool", True),
]


def params_for(raw: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for p in ORB_PARAMS:
        v = raw.get(p["id"], p["default"])
        if p["kind"] == "bool":
            out[p["id"]] = v if isinstance(v, bool) else str(v).lower() in ("1", "true", "yes", "on")
            continue
        try:
            v = float(v)
        except (TypeError, ValueError):
            v = p["default"]
        if not math.isfinite(v):
            v = p["default"]
        v = max(p["min"], min(p["max"], v))
        out[p["id"]] = int(round(v)) if p["kind"] == "int" else round(v, 4)
    # The range is read in whole bars.
    out["range_minutes"] = max(5, int(round(out["range_minutes"] / 5.0)) * 5)
    if not (out["allow_long"] or out["allow_short"]):
        out["allow_long"] = True
    return out


# ------------------------------------------------------------- the sessions

def sessions(frame) -> List[Dict[str, Any]]:
    """Regular-session five-minute bars, one dict of arrays per ET day.

    A day missing its opening bar (a late feed, a halt at the open) is dropped:
    its opening range would be the wrong thirty minutes."""
    import pandas as pd
    if frame is None or getattr(frame, "empty", True):
        return []
    df = frame.dropna(subset=["Open", "High", "Low", "Close"])
    idx = pd.DatetimeIndex(df.index)
    if idx.tz is not None:
        idx = idx.tz_convert("America/New_York")
    mins = idx.hour * 60 + idx.minute
    keep = (mins >= SESSION_OPEN) & (mins < SESSION_CLOSE)
    df, idx, mins = df[keep], idx[keep], mins[keep]
    vol = df["Volume"].to_numpy(dtype=float) if "Volume" in df else np.ones(len(df))
    days: Dict[Any, List[int]] = {}
    for k, d in enumerate(idx.date):
        days.setdefault(d, []).append(k)
    out = []
    o, h, l, c = (df[k].to_numpy(dtype=float) for k in ("Open", "High", "Low", "Close"))
    for d in sorted(days):
        ks = days[d]
        if mins[ks[0]] != SESSION_OPEN:
            continue
        out.append({"date": d.isoformat(), "min": np.asarray(mins[ks]) - SESSION_OPEN,
                    "stamp": [idx[k].strftime("%Y-%m-%d %H:%M") for k in ks],
                    "open": o[ks], "high": h[ks], "low": l[ks], "close": c[ks],
                    "volume": np.nan_to_num(vol[ks], nan=0.0)})
    return out


def vwap(s: Dict[str, Any]) -> np.ndarray:
    """VWAP through each bar's close. A bar with no volume leaves it where it was;
    the opening bar with none falls back to its typical price."""
    tp = (s["high"] + s["low"] + s["close"]) / 3.0
    v = s["volume"]
    cv, cpv = np.cumsum(v), np.cumsum(tp * v)
    out = np.where(cv > 0, cpv / np.where(cv > 0, cv, 1), np.nan)
    for i in range(len(out)):
        if not np.isfinite(out[i]):
            out[i] = out[i - 1] if i else tp[0]
    return out


# ------------------------------------------------------------- one session

def _setup(s: Dict[str, Any], prm: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The first qualified VWAP-retest entry of one session, or None, with
    why not (for the counts the result reports)."""
    n_or = prm["range_minutes"] // 5
    m, h, l, c, o = s["min"], s["high"], s["low"], s["close"], s["open"]
    n = len(c)
    if n <= n_or + 2:
        return {"skip": "short session"}
    orh, orl = float(np.max(h[:n_or])), float(np.min(l[:n_or]))
    w = orh - orl
    if not (w > 0):
        return {"skip": "no range"}
    vw = vwap(s)
    sides = [x for x, ok in (("long", prm["allow_long"]), ("short", prm["allow_short"])) if ok]
    state = {x: {"broke": None, "ext": None, "dead": False} for x in sides}
    for i in range(n_or, n):
        for side in sides:
            st = state[side]
            if st["dead"]:
                continue
            sign = 1 if side == "long" else -1
            level = orh if side == "long" else orl
            if st["broke"] is None:
                if sign * (c[i] - level) > 0:
                    st["broke"] = i
                    # The breaking bar can complete the extension too.
                else:
                    continue
            if st["ext"] is None:
                if sign * (c[i] - vw[i]) < 0:
                    st["dead"] = True           # closed back through VWAP on the way
                    continue
                far = h[i] if side == "long" else l[i]
                if sign * (far - (level + sign * prm["extension"] * w)) >= 0:
                    st["ext"] = i
                continue
            # Qualified: the first touch of VWAP as it stood at the last close.
            line = vw[i - 1]
            touched = (l[i] <= line) if side == "long" else (h[i] >= line)
            if not touched:
                continue
            if m[i] > prm["last_entry"]:
                st["dead"] = True
                continue
            fill = min(o[i], line) if side == "long" else max(o[i], line)
            return {"side": side, "i": i, "fill": float(fill), "line": float(line), "orh": orh, "orl": orl,
                    "w": w, "break_i": st["broke"], "ext_i": st["ext"]}
    # The furthest either side got, so each day counts once.
    stages = ["no break", "closed back through VWAP", "never extended", "no retest in time"]
    best = 0
    for side in sides:
        st = state[side]
        stage = (0 if st["broke"] is None else 1 if st["dead"] and st["ext"] is None
                 else 2 if st["ext"] is None else 3)
        best = max(best, stage)
    return {"skip": stages[best]}


def _manage(s: Dict[str, Any], side: str, i: int, entry: float, risk: float, target_r: float,
            cost: float) -> Dict[str, Any]:
    """Stop, target or the close, from entry bar i. Stop first on any tie."""
    h, l, c, o = s["high"], s["low"], s["close"], s["open"]
    n = len(c)
    sign = 1 if side == "long" else -1
    stop = entry - sign * risk
    target = entry + sign * target_r * risk if target_r > 0 else None
    exit_px, why, j = None, None, n - 1
    for k in range(i, n):
        hit_stop = (l[k] <= stop) if side == "long" else (h[k] >= stop)
        if hit_stop:
            # A bar that opened through the stop fills at its open, not the stop.
            gap = (o[k] < stop) if side == "long" else (o[k] > stop)
            exit_px, why, j = (o[k] if gap and k > i else stop), "stopped", k
            break
        if target is not None and k > i:
            hit_t = (h[k] >= target) if side == "long" else (l[k] <= target)
            if hit_t:
                gap = (o[k] > target) if side == "long" else (o[k] < target)
                exit_px, why, j = (o[k] if gap else target), "target", k
                break
    if exit_px is None:
        exit_px, why, j = c[n - 1], "flat at the close", n - 1
    if side == "long":
        ret = (exit_px * (1 - cost)) / (entry * (1 + cost)) - 1
    else:
        ret = (entry * (1 - cost) - exit_px * (1 + cost)) / (entry * (1 - cost))
    return {"exit": float(exit_px), "why": why, "j": j, "ret": float(ret), "stop": float(stop),
            "target": None if target is None else float(target)}


def _plain_break(s: Dict[str, Any], prm: Dict[str, Any], cost: float) -> Optional[Dict[str, Any]]:
    """The same day traded on the first close outside the range, at the next open."""
    n_or = prm["range_minutes"] // 5
    h, l, c, o, m = s["high"], s["low"], s["close"], s["open"], s["min"]
    n = len(c)
    if n <= n_or + 2:
        return None
    orh, orl = float(np.max(h[:n_or])), float(np.min(l[:n_or]))
    w = orh - orl
    if not (w > 0):
        return None
    for i in range(n_or, n - 1):
        side = ("long" if c[i] > orh and prm["allow_long"] else
                "short" if c[i] < orl and prm["allow_short"] else None)
        if side is None:
            continue
        if m[i + 1] > prm["last_entry"]:
            return None
        res = _manage(s, side, i + 1, float(o[i + 1]), prm["stop_ranges"] * w, prm["target_r"], cost)
        res.update(side=side, i=i + 1)
        return res
    return None


# ------------------------------------------------------------- the test

def _wilson(k: int, n: int) -> Tuple[Optional[float], Optional[float]]:
    if n == 0:
        return None, None
    z, p = 1.96, k / n
    d = 1 + z * z / n
    cc = (p + z * z / (2 * n)) / d
    hh = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round((cc - hh) * 100, 1), round((cc + hh) * 100, 1)


def _book(rets: List[float]) -> Dict[str, Any]:
    wins = [r for r in rets if r > 0]
    losses = [r for r in rets if r <= 0]
    total = float(np.prod([1 + r for r in rets]) - 1) * 100 if rets else 0.0
    return {"trades": len(rets), "total_return_pct": round(total, 2),
            "win_rate_pct": round(len(wins) / len(rets) * 100, 1) if rets else None,
            "avg_trade_pct": round(float(np.mean(rets)) * 100, 3) if rets else None}


def _random_timing(sess: List[Dict[str, Any]], trades: List[Dict[str, Any]], prm: Dict[str, Any],
                   cost: float, runs: int = RANDOM_RUNS) -> List[float]:
    """Each trade re-entered at a random bar after the opening range on its own
    day, same side, held the same number of bars (to the close at most)."""
    if not trades:
        return []
    by_day = {s["date"]: s for s in sess}
    n_or = prm["range_minutes"] // 5
    rng = random.Random(SEED)
    out = []
    for _ in range(runs):
        total = 1.0
        for t in trades:
            s = by_day[t["day"]]
            o, c, m = s["open"], s["close"], s["min"]
            ok = np.where(m <= prm["last_entry"])[0]
            last = int(ok[-1]) if len(ok) else len(c) - 1
            if last < n_or:
                continue
            k = rng.randint(n_or, last)
            j = min(k + max(0, t["bars"] - 1), len(c) - 1)
            ep, xp = o[k], c[j]
            if t["side"] == "long":
                r = (xp * (1 - cost)) / (ep * (1 + cost)) - 1
            else:
                r = (ep * (1 - cost) - xp * (1 + cost)) / (ep * (1 - cost))
            total *= 1 + r
        out.append((total - 1) * 100)
    return out


def run(frame, raw_params: Optional[Dict[str, Any]] = None, cost_bps: float = COST_BPS) -> Dict[str, Any]:
    prm = params_for(raw_params or {})
    sess = sessions(frame)
    if len(sess) < 5:
        return {"available": False, "reason": "Not enough five-minute history for this symbol."}
    cost = cost_bps / 10000.0
    trades: List[Dict[str, Any]] = []
    skips: Dict[str, int] = {}
    plain: List[float] = []
    for s in sess:
        su = _setup(s, prm)
        pb = _plain_break(s, prm, cost)
        if pb is not None:
            plain.append(pb["ret"])
        if not su or "skip" in su:
            why = (su or {}).get("skip", "no setup")
            skips[why] = skips.get(why, 0) + 1
            continue
        res = _manage(s, su["side"], su["i"], su["fill"], prm["stop_ranges"] * su["w"], prm["target_r"], cost)
        verb = "Bought" if su["side"] == "long" else "Sold short"
        trades.append({
            "day": s["date"], "side": su["side"],
            "entry_date": s["stamp"][su["i"]], "entry_price": round(su["fill"], 4),
            "entry_reason": "{} at VWAP {:.2f} after a break of the {}-minute range ({:.2f} to {:.2f}) that ran "
                            "{:g} range width{} without closing back through VWAP".format(
                                verb, su["line"], prm["range_minutes"], su["orl"], su["orh"], prm["extension"],
                                "" if prm["extension"] == 1 else "s"),
            "exit_date": s["stamp"][res["j"]], "exit_price": round(res["exit"], 4), "exit_reason": res["why"],
            "bars": res["j"] - su["i"] + 1, "return_pct": round(res["ret"] * 100, 2),
            "stop": round(res["stop"], 4), "target": None if res["target"] is None else round(res["target"], 4),
        })
    rets = [t["return_pct"] / 100 for t in trades]
    book = _book(rets)
    wins = [r for r in rets if r > 0]
    losses = [r for r in rets if r <= 0]
    lo, hi = _wilson(len(wins), len(rets))
    randoms = _random_timing(sess, trades, prm, cost)
    total = book["total_return_pct"]
    pct = round(sum(1 for r in randoms if r < total) / len(randoms) * 100, 1) if randoms else None
    plain_book = _book(plain)
    first_c, last_c = float(sess[0]["open"][0]), float(sess[-1]["close"][-1])
    bh = (last_c / first_c - 1) * 100

    # Growth of $1 at each session's close, beside holding the shares.
    eq, val, by_day = [], 1.0, {}
    for t in trades:
        by_day.setdefault(t["day"], []).append(t["return_pct"] / 100)
    for s in sess:
        for r in by_day.get(s["date"], []):
            val *= 1 + r
        eq.append({"date": s["date"], "strategy": round(val, 4), "buy_hold": round(float(s["close"][-1]) / first_c, 4)})
    dd = 0.0
    peak = 1.0
    for p in eq:
        peak = max(peak, p["strategy"])
        dd = min(dd, p["strategy"] / peak - 1)
    bh_dd, peak = 0.0, eq[0]["buy_hold"] if eq else 1.0
    for p in eq:
        peak = max(peak, p["buy_hold"])
        bh_dd = min(bh_dd, p["buy_hold"] / peak - 1)
    avg_win = float(np.mean(wins)) * 100 if wins else None
    avg_loss = float(np.mean(losses)) * 100 if losses else None
    n = len(trades)
    return {
        "available": True,
        "engine": "session",
        "params": prm,
        "window": {"from": sess[0]["date"], "to": sess[-1]["date"], "sessions": len(sess),
                   "years": round(len(sess) / 252.0, 2), "bars": int(sum(len(s["close"]) for s in sess)),
                   "timeframe": "5m", "timeframe_label": "5 minutes",
                   "timeframe_note": "Regular-session five-minute bars; the free feed keeps the last 60 sessions."},
        "cost_bps": cost_bps,
        "sides": "long and short" if prm["allow_long"] and prm["allow_short"] else ("long only" if prm["allow_long"] else "short only"),
        "fill": ("Entries rest at VWAP as it stood at the last close and fill on the first bar that touches it (at its "
                 "open if it opened through the line). Stops and targets fill at their level, or at the open of a bar "
                 "that gapped through; a bar that reaches both is counted as stopped. Every trade is flat by the close."),
        "stats": {
            "total_return_pct": round(total, 1),
            "trades": n,
            "win_rate_pct": book["win_rate_pct"],
            "win_rate_ci95": [lo, hi],
            "avg_win_pct": None if avg_win is None else round(avg_win, 2),
            "avg_loss_pct": None if avg_loss is None else round(avg_loss, 2),
            "avg_trade_pct": book["avg_trade_pct"],
            "reward_risk": round(avg_win / abs(avg_loss), 2) if (avg_win and avg_loss) else None,
            "profit_factor": round(sum(wins) / abs(sum(losses)), 2) if (wins and losses and sum(losses)) else None,
            "max_drawdown_pct": round(dd * 100, 1),
            "setups_per_session": round(n / len(sess), 2),
            "avg_bars_held": round(float(np.mean([t["bars"] for t in trades])), 1) if trades else None,
            "exit_reasons": _count(t["exit_reason"] for t in trades),
            "sides": _count(t["side"] for t in trades),
            "no_trade_days": skips,
        },
        "benchmark": {
            "buy_hold_return_pct": round(bh, 1),
            "buy_hold_max_drawdown_pct": round(bh_dd * 100, 1),
            "random_runs": len(randoms),
            "random_median_pct": round(float(np.median(randoms)), 1) if randoms else None,
            "beats_random_pct": pct,
            "random_method": ("Each trade re-entered at a random five-minute bar after the opening range on its own "
                              "day, same side, held as many bars; {} runs, fixed seed.".format(len(randoms))),
            "plain_break": plain_book,
            "plain_break_method": ("The same sessions traded on the first close outside the opening range, entered at "
                                   "the next open with the same stop, target and close-out: the rule without the "
                                   "extension, the VWAP condition and the wait for the retest."),
        },
        "equity": eq,
        "trades": trades,
        "open_trade": None,
        "verdict": _verdict(n, total, pct, plain_book, len(sess)),
        "caveats": [
            "Sixty sessions is a short window: a handful of setups on one symbol cannot separate a rule from luck.",
            "Five-minute bars hide the order of moves inside a bar; ties go against the trade, which may understate it.",
            "No slippage beyond the cost per side, no borrow cost on shorts, no partial fills at the VWAP limit.",
            "The post gives the entry only. The stop, target and close-out are this test's choices, shown in the rules.",
            "A backtest describes the past. It is not a forecast.",
        ],
    }


def _count(items) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for x in items:
        out[x] = out.get(x, 0) + 1
    return out


def _verdict(n: int, total: float, pct: Optional[float], plain: Dict[str, Any], sessions_n: int) -> str:
    if n == 0:
        return "No qualified setup in the last {} sessions: the rule did not trade.".format(sessions_n)
    if n < 10:
        return ("{} trade{} in {} sessions: far too few to judge the rule. Pool more symbols or wait for more "
                "history.".format(n, "" if n == 1 else "s", sessions_n))
    better_plain = plain.get("trades") and total > (plain.get("total_return_pct") or 0)
    lead = "Made money" if total > 0 else "Lost money"
    luck = pct is None or pct < 80
    parts = [lead + " over {} trades".format(n)]
    if pct is not None:
        parts.append("{} random timing on the same days (better than {:.0f}% of {} books)".format(
            "beat" if not luck else "no better than", pct, RANDOM_RUNS))
    parts.append("{} the plain break ({:+.1f}%)".format("ahead of" if better_plain else "behind",
                                                       plain.get("total_return_pct") or 0))
    return ", ".join(parts) + "."
