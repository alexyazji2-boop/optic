"""Strategy backtests on one symbol's daily history, for the Chart tab.

Asked for from a broker's marketing email ("MACD crosses up below zero, exit on
a bearish cross, a 50/200 death cross or after 35 candles: +1416% on PLTR").
The test itself is useful; the email's way of presenting it is not, because a
single headline return on a stock that rose twentyfold says more about the
stock than about the rule. So every result here is shown beside what would
have tested it:

* **Buy and hold over the same window.** A long-only rule on a stock that went
  up will show a gain whether or not the rule adds anything.
* **Random entries with the same exposure.** The same number of trades, each
  held for one of the strategy's own holding periods, entered on random days,
  500 times with a fixed seed. The strategy's return is placed in that
  distribution: at the 50th percentile it did no better than chance timing.
* **The win rate's 95% interval** (Wilson), because 47% from 30 trades and 47%
  from 300 are different claims.

**How trades are simulated.** Signals are read on a completed daily bar and
filled at the NEXT bar's open, so no trade uses a price it could not have had.
Every trade is long and fully invested, returns compound, and each side pays
`cost_bps` (5 basis points by default: commission and slippage together).
Prices are Yahoo's split-adjusted daily bars; dividends are not included.

**What it cannot tell you.** It is one symbol, chosen today, which survived to
be chosen (survivorship); the rules can be tuned until the past looks good
(overfitting), and nothing here protects against that except the baselines;
taxes, gaps through a stop and partial fills are not modelled. A backtest
describes the past. None has been shown to predict.
"""

from __future__ import annotations

import math
import random
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

COST_BPS = 5.0
RANDOM_RUNS = 500
SEED = 20261013
MAX_YEARS = 20


# ---------------------------------------------------------------- indicators

def ema(x: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(x), np.nan)
    if len(x) < n:
        return out
    a = 2.0 / (n + 1)
    out[n - 1] = np.mean(x[:n])
    for i in range(n, len(x)):
        out[i] = a * x[i] + (1 - a) * out[i - 1]
    return out


def sma(x: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(x), np.nan)
    if len(x) < n:
        return out
    c = np.cumsum(np.insert(x, 0, 0.0))
    out[n - 1:] = (c[n:] - c[:-n]) / n
    return out


def rsi(x: np.ndarray, n: int = 14) -> np.ndarray:
    out = np.full(len(x), np.nan)
    if len(x) <= n:
        return out
    d = np.diff(x)
    up, dn = np.maximum(d, 0), np.maximum(-d, 0)
    au, ad = up[:n].mean(), dn[:n].mean()
    out[n] = 100 - 100 / (1 + au / ad) if ad else 100.0
    for i in range(n + 1, len(x)):
        au = (au * (n - 1) + up[i - 1]) / n
        ad = (ad * (n - 1) + dn[i - 1]) / n
        out[i] = 100 - 100 / (1 + au / ad) if ad else 100.0
    return out


def macd(x: np.ndarray, fast: int, slow: int, signal: int) -> Tuple[np.ndarray, np.ndarray]:
    line = ema(x, fast) - ema(x, slow)
    sig = np.full(len(x), np.nan)
    ok = np.where(~np.isnan(line))[0]
    if len(ok) >= signal:
        sig[ok] = ema(line[ok], signal)
    return line, sig


def cross_up(a: np.ndarray, b: np.ndarray, i: int) -> bool:
    return (i > 0 and not (np.isnan(a[i]) or np.isnan(b[i]) or np.isnan(a[i - 1]) or np.isnan(b[i - 1]))
            and a[i - 1] <= b[i - 1] and a[i] > b[i])


def cross_down(a: np.ndarray, b: np.ndarray, i: int) -> bool:
    return (i > 0 and not (np.isnan(a[i]) or np.isnan(b[i]) or np.isnan(a[i - 1]) or np.isnan(b[i - 1]))
            and a[i - 1] >= b[i - 1] and a[i] < b[i])


# ---------------------------------------------------------------- strategies

def _p(pid: str, label: str, kind: str, default: Any, lo: Any = None, hi: Any = None) -> Dict[str, Any]:
    return {"id": pid, "label": label, "kind": kind, "default": default, "min": lo, "max": hi}


def _macd_turn(bars: Dict[str, np.ndarray], prm: Dict[str, Any]):
    c = bars["close"]
    line, sig = macd(c, prm["fast"], prm["slow"], prm["signal"])
    s50, s200 = sma(c, 50), sma(c, 200)

    def entry(i: int) -> Optional[str]:
        if cross_up(line, sig, i) and line[i] < 0:
            return "MACD crossed above its signal line below zero ({:.2f})".format(float(line[i]))
        return None

    def exit_(i: int, held: int) -> Optional[str]:
        if prm["exit_macd"] and cross_down(line, sig, i):
            return "MACD crossed below its signal line"
        if prm["exit_death_cross"] and cross_down(s50, s200, i):
            return "50-day average crossed below the 200-day"
        if prm["max_bars"] and held >= prm["max_bars"]:
            return "held {} candles".format(prm["max_bars"])
        return None
    return entry, exit_, max(prm["slow"] + prm["signal"], 200 if prm["exit_death_cross"] else 0)


def _golden_cross(bars, prm):
    c = bars["close"]
    f, s = sma(c, prm["fast"]), sma(c, prm["slow"])
    entry = lambda i: "{}-day average crossed above the {}-day".format(prm["fast"], prm["slow"]) if cross_up(f, s, i) else None
    exit_ = lambda i, held: "{}-day average crossed below the {}-day".format(prm["fast"], prm["slow"]) if cross_down(f, s, i) else None
    return entry, exit_, prm["slow"]


def _rsi_rebound(bars, prm):
    c = bars["close"]
    r = rsi(c, prm["length"])
    lo = np.full(len(c), float(prm["oversold"]))
    hi = np.full(len(c), float(prm["take"]))

    def exit_(i, held):
        if r[i] >= prm["take"]:
            return "RSI reached {}".format(prm["take"])
        if prm["max_bars"] and held >= prm["max_bars"]:
            return "held {} candles".format(prm["max_bars"])
        return None
    entry = lambda i: "RSI crossed back above {}".format(prm["oversold"]) if cross_up(r, lo, i) else None
    return entry, exit_, prm["length"] + 1


def _donchian(bars, prm):
    h, l, c = bars["high"], bars["low"], bars["close"]
    n_in, n_out = prm["entry_days"], prm["exit_days"]

    def entry(i):
        if i < n_in:
            return None
        return "closed above the prior {}-day high".format(n_in) if c[i] > np.max(h[i - n_in:i]) else None

    def exit_(i, held):
        if i < n_out:
            return None
        return "closed below the prior {}-day low".format(n_out) if c[i] < np.min(l[i - n_out:i]) else None
    return entry, exit_, n_in


STRATEGIES: List[Dict[str, Any]] = [
    {"id": "macd_turn_below_zero", "label": "MACD turn below zero",
     "summary": "Buys when the MACD line crosses up through its signal line while still below zero, an early "
                "turn in momentum after a decline. Sells on the next bearish MACD cross, a 50/200-day death "
                "cross, or after a set number of candles.",
     "params": [_p("fast", "MACD fast", "int", 12, 2, 50), _p("slow", "MACD slow", "int", 26, 5, 100),
                _p("signal", "Signal", "int", 9, 2, 50), _p("max_bars", "Sell after (candles, 0 = never)", "int", 35, 0, 500),
                _p("exit_macd", "Sell on a bearish MACD cross", "bool", True),
                _p("exit_death_cross", "Sell on a 50/200 death cross", "bool", True)],
     "build": _macd_turn},
    {"id": "golden_cross", "label": "Moving-average cross",
     "summary": "Buys when the faster average crosses above the slower one and sells when it crosses back.",
     "params": [_p("fast", "Fast average (days)", "int", 50, 2, 200), _p("slow", "Slow average (days)", "int", 200, 5, 400)],
     "build": _golden_cross},
    {"id": "rsi_rebound", "label": "RSI rebound from oversold",
     "summary": "Buys when RSI climbs back above the oversold line and sells when it reaches the take level or "
                "after a set number of candles.",
     "params": [_p("length", "RSI length", "int", 14, 2, 50), _p("oversold", "Oversold line", "int", 30, 5, 50),
                _p("take", "Sell at RSI", "int", 70, 50, 95), _p("max_bars", "Sell after (candles, 0 = never)", "int", 20, 0, 500)],
     "build": _rsi_rebound},
    {"id": "donchian_breakout", "label": "Channel breakout",
     "summary": "Buys on a close above the prior N-day high and sells on a close below the prior M-day low, the "
                "classic trend-following rule.",
     "params": [_p("entry_days", "Breakout window (days)", "int", 55, 5, 250), _p("exit_days", "Exit window (days)", "int", 20, 2, 250)],
     "build": _donchian},
]
# Rules that live inside one session (app/analytics/session_rules.py): their
# own simulator, on five-minute bars only.
from . import session_rules  # noqa: E402

STRATEGIES.append({
    "id": "orb_vwap_retest", "label": "Opening-range break, VWAP retest",
    "summary": "A day trade. Waits for a break of the opening range that runs at least a range width without "
               "closing back through VWAP, then enters on the first touch of VWAP. Exits at a stop, a target or "
               "the close; long and short.",
    "params": session_rules.ORB_PARAMS, "engine": "session", "timeframes": ["5m"],
})
for _s in STRATEGIES:
    _s.setdefault("timeframes", ["1d", "4h", "1h"])
BY_ID = {s["id"]: s for s in STRATEGIES}


def catalogue() -> List[Dict[str, Any]]:
    return [{k: v for k, v in s.items() if k != "build"} for s in STRATEGIES]


def params_for(sid: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    if BY_ID[sid].get("engine") == "session":
        return session_rules.params_for(raw)
    out = {}
    for p in BY_ID[sid]["params"]:
        v = raw.get(p["id"], p["default"])
        if p["kind"] == "bool":
            out[p["id"]] = v if isinstance(v, bool) else str(v).lower() in ("1", "true", "yes", "on")
        else:
            try:
                v = int(float(v))
            except (TypeError, ValueError):
                v = p["default"]
            out[p["id"]] = max(p["min"], min(p["max"], v))
    if sid == "macd_turn_below_zero" and out["fast"] >= out["slow"]:
        out["fast"] = max(2, out["slow"] - 1)
    if sid == "golden_cross" and out["fast"] >= out["slow"]:
        out["fast"] = max(2, out["slow"] - 1)
    return out


# --------------------------------------------------------------- simulation

def _wilson(k: int, n: int) -> Tuple[Optional[float], Optional[float]]:
    if n == 0:
        return None, None
    z, p = 1.96, k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round((c - h) * 100, 1), round((c + h) * 100, 1)


def _max_drawdown(equity: np.ndarray) -> float:
    peak = np.maximum.accumulate(equity)
    return float(np.min(equity / peak - 1.0) * 100) if len(equity) else 0.0


def simulate(bars: Dict[str, np.ndarray], dates: List[str], sid: str, prm: Dict[str, Any],
             cost_bps: float = COST_BPS, trade_from: int = 0) -> Dict[str, Any]:
    """Trades begin at `trade_from` (the reporting window); the indicators are
    computed on everything before it, so the first signal is not a warm-up
    artefact and no trade straddles the window's start."""
    entry, exit_, warmup = BY_ID[sid]["build"](bars, prm)
    o, c = bars["open"], bars["close"]
    n = len(c)
    cost = cost_bps / 10000.0
    trades: List[Dict[str, Any]] = []
    pos = None              # (entry_index, entry_price, reason)
    pending: Optional[Tuple[str, str]] = None   # ("buy"|"sell", reason), filled at the next open
    equity = np.ones(n)
    cash = 1.0
    start = min(max(warmup, trade_from), n - 1)
    for i in range(start, n):
        if pending and i > start:
            kind, why = pending
            px = o[i]
            if kind == "buy" and pos is None and np.isfinite(px) and px > 0:
                pos = (i, px * (1 + cost), why)
            elif kind == "sell" and pos is not None and np.isfinite(px) and px > 0:
                ei, ep, ewhy = pos
                xp = px * (1 - cost)
                ret = xp / ep - 1.0
                cash *= 1 + ret
                trades.append({"entry_date": dates[ei], "entry_price": round(float(o[ei]), 4), "entry_reason": ewhy,
                               "exit_date": dates[i], "exit_price": round(float(px), 4), "exit_reason": why,
                               "bars": i - ei, "return_pct": round(float(ret) * 100, 2), "entry_index": ei, "exit_index": i})
                pos = None
            pending = None
        # Mark to market at the close.
        equity[i] = cash * (c[i] / pos[1] * (1 - cost) if pos is not None else 1.0)
        if i == n - 1:
            break
        if pos is None:
            why = entry(i)
            if why:
                pending = ("buy", why)
        else:
            why = exit_(i, i - pos[0] + 1)
            if why:
                pending = ("sell", why)
    equity[:start] = 1.0
    open_trade = None
    if pos is not None:
        ei, ep, ewhy = pos
        open_trade = {"entry_date": dates[ei], "entry_price": round(float(o[ei]), 4), "entry_reason": ewhy,
                      "bars": n - 1 - ei, "unrealised_pct": round(float(c[-1] * (1 - cost) / ep - 1) * 100, 2),
                      "entry_index": ei}
    return {"trades": trades, "open": open_trade, "equity": equity, "start": start}


def _random_baseline(c: np.ndarray, o: np.ndarray, start: int, holds: List[int], cost: float,
                     runs: int = RANDOM_RUNS) -> List[float]:
    """Total returns of `runs` random-entry books with the strategy's own
    holding periods, non-overlapping, inside the same window."""
    n = len(c)
    rng = random.Random(SEED)
    out = []
    span = n - start - 1
    need = sum(holds) + len(holds)
    if not holds or span <= need:
        return out
    for _ in range(runs):
        hs = holds[:]
        rng.shuffle(hs)
        slack = span - need
        # Random gaps between trades that sum to the slack.
        cuts = sorted(rng.randint(0, slack) for _ in range(len(hs)))
        gaps = [cuts[0]] + [cuts[k] - cuts[k - 1] for k in range(1, len(cuts))]
        i = start + 1
        total = 1.0
        for g, h in zip(gaps, hs):
            i += g
            j = min(i + h, n - 1)
            if i >= n - 1:
                break
            total *= (o[j] * (1 - cost)) / (o[i] * (1 + cost))
            i = j + 1
        out.append((total - 1) * 100)
    return out


TIMEFRAMES = {
    "1d": {"label": "Daily", "note": "Daily bars, the symbol's whole listed history."},
    "4h": {"label": "4 hours", "note": "Two bars a session (9:30 to 13:30 and 13:30 to 16:00 ET) built from hourly "
                                       "bars; about the last three years, which is all the free feed keeps."},
    "1h": {"label": "1 hour", "note": "Regular-session hourly bars; about the last three years."},
    "5m": {"label": "5 minutes", "note": "Regular-session five-minute bars; the free feed keeps the last 60 sessions."},
}


def intraday_frame(df, splits: Optional[List[Dict[str, Any]]] = None, four_hour: bool = False):
    """Hourly bars made comparable across time, optionally as 4-hour bars.

    The feed's intraday bars are not split-adjusted: Nvidia's 10-for-1 in June
    2024 would read as a 90% fall in one hour. Prices before each split are
    divided by its ratio, volumes multiplied, using the feed's split record."""
    import pandas as pd
    if df is None or df.empty:
        return df
    out = df[["Open", "High", "Low", "Close"] + (["Volume"] if "Volume" in df else [])].copy()
    idx = pd.DatetimeIndex(out.index)
    for sp in splits or []:
        try:
            when = pd.Timestamp(sp["date"])
            ratio = float(sp["ratio"])
        except (KeyError, TypeError, ValueError):
            continue
        if not ratio or ratio == 1:
            continue
        if when.tzinfo is None and idx.tz is not None:
            when = when.tz_localize(idx.tz)
        before = idx < when
        for col in ("Open", "High", "Low", "Close"):
            out.loc[before, col] = out.loc[before, col] / ratio
        if "Volume" in out:
            out.loc[before, "Volume"] = out.loc[before, "Volume"] * ratio
    if not four_hour:
        return out
    et = idx.tz_convert("America/New_York") if idx.tz is not None else idx
    bucket = [(d.date(), 0 if (d.hour, d.minute) < (13, 30) else 1) for d in et]
    out["_b"] = bucket
    agg = out.groupby("_b", sort=True).agg({"Open": "first", "High": "max", "Low": "min", "Close": "last",
                                            **({"Volume": "sum"} if "Volume" in out else {})})
    stamps = out.reset_index().groupby("_b", sort=True).first().iloc[:, 0]
    agg.index = pd.DatetimeIndex(list(stamps))
    return agg


def run(frame, sid: str, raw_params: Optional[Dict[str, Any]] = None, years: Optional[float] = None,
        cost_bps: float = COST_BPS, timeframe: str = "1d") -> Dict[str, Any]:
    if sid not in BY_ID:
        return {"available": False, "reason": "Unknown strategy."}
    if frame is None or getattr(frame, "empty", True):
        return {"available": False, "reason": "No price history."}
    if timeframe not in BY_ID[sid]["timeframes"]:
        return {"available": False, "reason": "{} runs on {} bars.".format(
            BY_ID[sid]["label"], " or ".join(TIMEFRAMES[t]["label"].lower() for t in BY_ID[sid]["timeframes"]))}
    if BY_ID[sid].get("engine") == "session":
        out = session_rules.run(frame, raw_params, cost_bps)
        if out.get("available"):
            out["strategy"] = {k: v for k, v in BY_ID[sid].items() if k != "build"}
        return out
    df = frame.dropna(subset=["Open", "High", "Low", "Close"])
    prm = params_for(sid, raw_params or {})
    import pandas as pd
    stamps = pd.DatetimeIndex(df.index)
    intraday = timeframe != "1d"
    if stamps.tz is not None:
        stamps = stamps.tz_convert("America/New_York")
    dates = [d.strftime("%Y-%m-%d %H:%M") if intraday else d.strftime("%Y-%m-%d") for d in stamps]
    bars = {k.lower(): df[k].to_numpy(dtype=float) for k in ("Open", "High", "Low", "Close")}
    # The reporting window: the last `years`, with the indicators warmed up
    # on the history before it.
    cut = 0
    if years:
        since = stamps[-1] - pd.Timedelta(days=min(years, MAX_YEARS) * 365.25)
        cut = int(np.searchsorted(stamps.asi8, since.value))
    res = simulate(bars, dates, sid, prm, cost_bps, trade_from=max(0, cut))
    start = res["start"]
    trades = res["trades"]
    eq = res["equity"][start:]
    eq = eq / eq[0] if len(eq) and eq[0] else eq
    c, o = bars["close"], bars["open"]
    bh = c[start:] / c[start] if len(c) > start and c[start] else np.array([1.0])
    rets = [t["return_pct"] for t in trades]
    wins = [r for r in rets if r > 0]
    losses = [r for r in rets if r <= 0]
    total = (float(eq[-1]) - 1) * 100 if len(eq) else 0.0
    yrs = max((stamps[-1] - stamps[start]).days / 365.25, 1e-9) if len(stamps) > start else 1e-9
    cagr = ((eq[-1]) ** (1 / yrs) - 1) * 100 if len(eq) and eq[-1] > 0 else None
    bh_total = (float(bh[-1]) - 1) * 100
    bh_cagr = ((bh[-1]) ** (1 / yrs) - 1) * 100 if bh[-1] > 0 else None
    holds = [max(1, t["bars"]) for t in trades]
    randoms = _random_baseline(c, o, start, holds, cost_bps / 10000.0)
    pct_rank = (round(sum(1 for r in randoms if r < total) / len(randoms) * 100, 1) if randoms else None)
    lo, hi = _wilson(len(wins), len(rets))
    avg_win = float(np.mean(wins)) if wins else None
    avg_loss = float(np.mean(losses)) if losses else None
    in_market = sum(t["bars"] for t in trades) + ((res["open"] or {}).get("bars") or 0)
    step = max(1, len(eq) // 300)
    curve_idx = list(range(0, len(eq), step))
    if curve_idx and curve_idx[-1] != len(eq) - 1:
        curve_idx.append(len(eq) - 1)
    return {
        "available": True,
        "strategy": {k: v for k, v in BY_ID[sid].items() if k != "build"},
        "params": prm,
        "window": {"from": dates[start], "to": dates[-1], "years": round(yrs, 2), "bars": len(eq),
                   "timeframe": timeframe, "timeframe_label": TIMEFRAMES.get(timeframe, {}).get("label", timeframe),
                   "timeframe_note": TIMEFRAMES.get(timeframe, {}).get("note", "")},
        "cost_bps": cost_bps,
        "fill": "Signals on a completed bar, filled at the next bar's open.",
        "stats": {
            "total_return_pct": round(total, 1),
            "cagr_pct": None if cagr is None else round(cagr, 1),
            "trades": len(rets),
            "win_rate_pct": round(len(wins) / len(rets) * 100, 1) if rets else None,
            "win_rate_ci95": [lo, hi],
            "avg_win_pct": None if avg_win is None else round(avg_win, 2),
            "avg_loss_pct": None if avg_loss is None else round(avg_loss, 2),
            "reward_risk": round(avg_win / abs(avg_loss), 2) if (avg_win and avg_loss) else None,
            "profit_factor": round(sum(wins) / abs(sum(losses)), 2) if (wins and losses and sum(losses)) else None,
            "max_drawdown_pct": round(_max_drawdown(eq), 1),
            "time_in_market_pct": round(in_market / max(len(eq), 1) * 100, 1),
            "trades_per_year": round(len(rets) / yrs, 1) if yrs > 0.05 else None,
            "avg_bars_held": round(float(np.mean(holds)), 1) if holds else None,
            "exit_reasons": _count(t["exit_reason"] for t in trades),
        },
        "benchmark": {
            "buy_hold_return_pct": round(bh_total, 1),
            "buy_hold_cagr_pct": None if bh_cagr is None else round(bh_cagr, 1),
            "buy_hold_max_drawdown_pct": round(_max_drawdown(bh), 1),
            "random_runs": len(randoms),
            "random_median_pct": round(float(np.median(randoms)), 1) if randoms else None,
            "beats_random_pct": pct_rank,
            "random_method": ("The same number of trades, each held for one of the strategy's own holding periods, "
                              "on random non-overlapping days in the same window; {} runs, fixed seed.".format(len(randoms))),
        },
        "equity": [{"date": dates[start + k], "strategy": round(float(eq[k]), 4), "buy_hold": round(float(bh[k]), 4)}
                   for k in curve_idx],
        "trades": [{k: v for k, v in t.items() if k not in ("entry_index", "exit_index")} for t in trades],
        "open_trade": ({k: v for k, v in res["open"].items() if k != "entry_index"} if res["open"] else None),
        "verdict": _verdict(total, bh_total, pct_rank, len(rets)),
        "caveats": [
            "One symbol, chosen today: it survived to be chosen, which flatters any long-only rule.",
            "Rules can be tuned until the past looks good; the random-entry and buy-and-hold comparisons are the check.",
            "Split-adjusted prices without dividends; no taxes; gaps through an exit and partial fills are not modelled.",
            "A backtest describes the past. It is not a forecast.",
        ],
    }


def _count(items) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for x in items:
        out[x] = out.get(x, 0) + 1
    return out


def _verdict(total: float, bh: float, pct: Optional[float], n: int) -> str:
    if n < 10:
        return "Too few trades ({}) to say anything about the rule.".format(n)
    beat_bh = total > bh
    if pct is None:
        return "Beat buy and hold." if beat_bh else "Did worse than buying and holding."
    luck = pct < 80
    if beat_bh and not luck:
        return ("Beat buy and hold, and did better than {:.0f}% of random-entry books with the same exposure."
                .format(pct))
    if beat_bh:
        return ("Beat buy and hold, but random entries with the same exposure did as well {:.0f}% of the time, "
                "so the timing may be luck.".format(100 - pct))
    if not luck:
        return ("Did worse than buying and holding, though better than {:.0f}% of random-entry books: the timing "
                "helped, being out of the market cost more.".format(pct))
    return "Did worse than buying and holding, and no better than random entries with the same exposure."
