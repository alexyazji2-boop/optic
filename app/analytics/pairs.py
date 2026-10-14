"""Pairs: two related stocks' spread, and whether trading it has worked out of sample.

From a trading post: "Some stocks trade in pairs: same products, same
customers, same market. When one runs ahead and the other falls behind, buying
the loser and shorting the leader tends to make money. It's called statistical
arbitrage." The idea is old and real (Gatev, Goetzmann and Rouwenhorst, Review
of Financial Studies 2006, found profits in US pairs from 1962 that shrank
after the 1990s); "tends to make money" is the part to test, pair by pair, on
data the pair was not chosen with.

**The spread.** Log prices, A against B: s = log A - (alpha + beta x log B),
with alpha and beta fitted by least squares on a formation year. The z-score is
the spread less its formation mean, over its formation standard deviation.

**Whether it is a pair at all.** Two trending stocks are correlated without
their spread ever coming back. The Engle-Granger test asks whether the spread
is stationary: an augmented Dickey-Fuller regression on it, compared with
MacKinnon's critical values for two variables (5%: -3.34). The half-life,
from an AR(1) fit of the spread, is how long a gap typically takes to halve.

**The rule.** Enter when |z| reaches 2 (short the leader, buy the laggard, the
laggard's leg sized by beta), exit when z crosses back through 0, stop at
|z| of 4, and give up after three half-lives (5 to 63 sessions). Signals on a
close fill at the NEXT close. Each leg pays `cost_bps` a side and the short leg
pays borrow; returns are on gross exposure (both legs).

**Out of sample.** Walk forward: fit on 252 sessions, trade the next 126 with
those numbers frozen, roll on 126, over the shared history (up to 15 years).
Only the trading windows count. Two books: every window traded (the post's
version), and only windows whose formation year passed the cointegration test
(the textbook version). Beside both, the same trades on random days.
"""

from __future__ import annotations

import math
import random
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

FORMATION = 252
TRADE = 126
MAX_YEARS = 15
COST_BPS = 5.0
BORROW_PCT = 0.5          # a year, on the short leg's notional
RANDOM_RUNS = 500
SEED = 20261014
# MacKinnon (2010), Engle-Granger, two variables, constant, no trend.
EG_CRIT = [(0.01, -3.90), (0.05, -3.34), (0.10, -3.04)]


def _p(pid, label, kind, default, lo, hi, step=None):
    out = {"id": pid, "label": label, "kind": kind, "default": default, "min": lo, "max": hi}
    if step is not None:
        out["step"] = step
    return out


PARAMS = [
    _p("entry_z", "Enter at |z|", "float", 2.0, 0.5, 4.0, 0.25),
    _p("exit_z", "Exit at |z|", "float", 0.0, 0.0, 2.0, 0.25),
    _p("stop_z", "Stop at |z|", "float", 4.0, 2.0, 8.0, 0.5),
]


def params_for(raw: Dict[str, Any]) -> Dict[str, float]:
    out = {}
    for p in PARAMS:
        try:
            v = float(raw.get(p["id"], p["default"]))
        except (TypeError, ValueError):
            v = p["default"]
        if not math.isfinite(v):
            v = p["default"]
        out[p["id"]] = round(max(p["min"], min(p["max"], v)), 4)
    if out["exit_z"] >= out["entry_z"]:
        out["exit_z"] = max(0.0, out["entry_z"] - 0.5)
    if out["stop_z"] <= out["entry_z"]:
        out["stop_z"] = out["entry_z"] + 1.0
    return out


# ------------------------------------------------------------ statistics

def ols(y: np.ndarray, x: np.ndarray) -> Tuple[float, float]:
    """y = alpha + beta x, least squares."""
    xm, ym = x.mean(), y.mean()
    vx = ((x - xm) ** 2).sum()
    beta = float(((x - xm) * (y - ym)).sum() / vx) if vx > 0 else 0.0
    return float(ym - beta * xm), beta


def adf_t(s: np.ndarray, lags: int = 1) -> Optional[float]:
    """t-statistic of gamma in  d s_t = c + gamma s_{t-1} + sum phi_i d s_{t-i} + e."""
    s = np.asarray(s, dtype=float)
    d = np.diff(s)
    n = len(d) - lags
    if n < 20:
        return None
    y = d[lags:]
    cols = [np.ones(n), s[lags:-1]]
    for i in range(1, lags + 1):
        cols.append(d[lags - i:-i])
    X = np.column_stack(cols)
    try:
        coef, *_ = np.linalg.lstsq(X, y, rcond=None)
        resid = y - X @ coef
        dof = n - X.shape[1]
        s2 = float(resid @ resid) / dof
        cov = s2 * np.linalg.inv(X.T @ X)
    except np.linalg.LinAlgError:
        return None
    se = math.sqrt(cov[1, 1]) if cov[1, 1] > 0 else None
    return float(coef[1] / se) if se else None


def eg_level(t: Optional[float]) -> Optional[float]:
    """The smallest of 1%, 5%, 10% the test passes at, or None."""
    if t is None:
        return None
    for level, crit in EG_CRIT:
        if t < crit:
            return level
    return None


def half_life(s: np.ndarray) -> Optional[float]:
    s = np.asarray(s, dtype=float)
    a, b = ols(np.diff(s), s[:-1])
    if b >= 0 or b <= -1:
        return None
    return float(-math.log(2) / math.log(1 + b))


def fit(la: np.ndarray, lb: np.ndarray) -> Dict[str, Any]:
    alpha, beta = ols(la, lb)
    s = la - (alpha + beta * lb)
    sd = float(s.std(ddof=1))
    t = adf_t(s)
    ra, rb = np.diff(la), np.diff(lb)
    corr = float(np.corrcoef(ra, rb)[0, 1]) if ra.std() > 0 and rb.std() > 0 else None
    return {"alpha": alpha, "beta": beta, "mean": float(s.mean()), "sd": sd, "adf_t": t,
            "coint_level": eg_level(t), "half_life": half_life(s), "corr": corr}


# --------------------------------------------------------------- trading

def _hold_cap(hl: Optional[float]) -> int:
    if hl is None or not math.isfinite(hl):
        return 63
    return int(max(5, min(63, round(3 * hl))))


def trade_window(pa: np.ndarray, pb: np.ndarray, dates: List[str], f: Dict[str, Any], start: int, end: int,
                 prm: Dict[str, float], cost_bps: float = COST_BPS) -> List[Dict[str, Any]]:
    """Trades in [start, end) on frozen formation numbers. A position still
    open at the window's end is closed at its last close."""
    la, lb = np.log(pa), np.log(pb)
    # A hedge ratio at or below zero says the two moved apart over the year:
    # "short one, buy the other" would then be long or short both. Not a pair.
    if not (f["sd"] > 0) or f["beta"] <= 0:
        return []
    z = (la - (f["alpha"] + f["beta"] * lb) - f["mean"]) / f["sd"]
    beta = f["beta"]
    gross = 1.0 + abs(beta)
    cost = cost_bps / 10000.0
    borrow_day = BORROW_PCT / 100.0 / 252.0
    cap = _hold_cap(f["half_life"])
    trades: List[Dict[str, Any]] = []
    pos = None          # (side, entry index, entry z): side +1 = long A / short B
    pending = None      # ("open", side) or ("close", why)
    for t in range(start, end):
        if pending is not None:
            kind, arg = pending
            pending = None
            if kind == "open" and pos is None:
                pos = (arg, t, float(z[t - 1]))
            elif kind == "close" and pos is not None:
                trades.append(_close(pos, t, arg, pa, pb, beta, gross, cost, borrow_day, dates, z))
                pos = None
        last = t == end - 1
        if pos is None:
            if last:
                continue
            if z[t] >= prm["entry_z"]:
                pending = ("open", -1)     # A rich: short A, buy B
            elif z[t] <= -prm["entry_z"]:
                pending = ("open", +1)
            continue
        side, ei, ez = pos
        held = t - ei
        why = None
        if side == -1 and z[t] <= prm["exit_z"] or side == +1 and z[t] >= -prm["exit_z"]:
            why = "spread came back"
        elif abs(z[t]) >= prm["stop_z"]:
            why = "stopped at |z| {:g}".format(prm["stop_z"])
        elif held >= cap:
            why = "gave up after {} sessions".format(cap)
        if last:
            trades.append(_close(pos, t, why or "window ended", pa, pb, beta, gross, cost, borrow_day, dates, z))
            pos = None
        elif why:
            pending = ("close", why)
    return trades


def _close(pos, t, why, pa, pb, beta, gross, cost, borrow_day, dates, z) -> Dict[str, Any]:
    side, ei, ez = pos
    ra = pa[t] / pa[ei] - 1
    rb = pb[t] / pb[ei] - 1
    # Long A / short B: +A - beta*B; the mirror for the other side. On gross.
    pnl = side * (ra - beta * rb) / gross
    short_share = (1.0 if side == -1 else abs(beta)) / gross
    pnl -= 2 * cost + short_share * borrow_day * (t - ei)
    return {"entry_date": dates[ei], "exit_date": dates[t], "side": "long A, short B" if side == 1 else "short A, long B",
            "entry_z": round(ez, 2), "exit_z": round(float(z[t]), 2), "bars": t - ei,
            "return_pct": round(pnl * 100, 2), "exit_reason": why, "entry_index": ei, "exit_index": t}


def _wilson(k: int, n: int):
    if n == 0:
        return None, None
    zz, p = 1.96, k / n
    d = 1 + zz * zz / n
    c = (p + zz * zz / (2 * n)) / d
    h = zz * math.sqrt(p * (1 - p) / n + zz * zz / (4 * n * n)) / d
    return round((c - h) * 100, 1), round((c + h) * 100, 1)


def _book(trades: List[Dict[str, Any]], years: float) -> Dict[str, Any]:
    rets = [t["return_pct"] / 100 for t in trades]
    if not rets:
        return {"trades": 0, "total_return_pct": 0.0, "win_rate_pct": None, "win_rate_ci95": [None, None],
                "avg_trade_pct": None, "cagr_pct": None, "max_drawdown_pct": 0.0}
    eq = np.cumprod([1 + r for r in rets])
    peak = np.maximum.accumulate(np.concatenate([[1.0], eq]))
    dd = float(np.min(np.concatenate([[1.0], eq]) / peak - 1) * 100)
    wins = sum(1 for r in rets if r > 0)
    lo, hi = _wilson(wins, len(rets))
    total = float(eq[-1] - 1)
    return {"trades": len(rets), "total_return_pct": round(total * 100, 1),
            "win_rate_pct": round(wins / len(rets) * 100, 1), "win_rate_ci95": [lo, hi],
            "avg_trade_pct": round(float(np.mean(rets)) * 100, 2),
            "cagr_pct": round(((1 + total) ** (1 / years) - 1) * 100, 1) if years > 0.25 and total > -1 else None,
            "max_drawdown_pct": round(dd, 1)}


def _random_book(pa, pb, windows, trades, beta_of, cost_bps, runs=RANDOM_RUNS) -> List[float]:
    """The same number of trades, in the same windows with the same holding
    periods, on random days and on a coin-flip side.

    Not the rule's own sides: in a window where the spread trends, the rule
    keeps taking the side against the trend, and random days on those sides
    inherit that bet for the whole window. KO/PEP's random books lost a median
    53% that way against about 27% from costs alone, and the rule beat 99% of
    them while losing money. A coin-flip side carries no view, which is what a
    baseline for timing has to be."""
    if not trades:
        return []
    rng = random.Random(SEED)
    cost = cost_bps / 10000.0
    out = []
    for _ in range(runs):
        total = 1.0
        for t in trades:
            w = t["_window"]
            s, e = windows[w]
            h = max(1, t["bars"])
            if e - s - 1 <= h:
                continue
            i = rng.randint(s, e - 1 - h)
            j = i + h
            beta = beta_of[w]
            side = 1 if rng.random() < 0.5 else -1
            r = side * ((pa[j] / pa[i] - 1) - beta * (pb[j] / pb[i] - 1)) / (1 + abs(beta)) - 2 * cost
            total *= 1 + r
        out.append((total - 1) * 100)
    return out


def walk_forward(pa: np.ndarray, pb: np.ndarray, dates: List[str], prm: Dict[str, float],
                 cost_bps: float = COST_BPS) -> Dict[str, Any]:
    n = len(pa)
    la, lb = np.log(pa), np.log(pb)
    windows, fits, all_trades = [], [], []
    k = FORMATION
    while k < n - 5:
        f = fit(la[k - FORMATION:k], lb[k - FORMATION:k])
        e = min(k + TRADE, n)
        # Was it still a pair in the window it was traded in? (Re-fitted there,
        # for the record only; nothing below trades on it.)
        later = fit(la[k:e], lb[k:e]) if e - k >= 60 else None
        w = len(windows)
        windows.append((k, e))
        fits.append({"from": dates[k], "to": dates[e - 1], "beta": round(f["beta"], 3),
                     "coint_level": f["coint_level"], "adf_t": None if f["adf_t"] is None else round(f["adf_t"], 2),
                     "half_life": None if f["half_life"] is None else round(f["half_life"], 1),
                     "still_coint": None if later is None else later["coint_level"] is not None})
        for t in trade_window(pa, pb, dates, f, k, e, prm, cost_bps):
            t["_window"] = w
            t["coint"] = f["coint_level"] is not None
            all_trades.append(t)
        k += TRADE
    if not windows:
        return {"windows": [], "all": _book([], 0), "coint_only": _book([], 0)}
    traded_days = sum(e - s for s, e in windows)
    years = traded_days / 252.0
    coint_windows = [i for i, f in enumerate(fits) if f["coint_level"] is not None]
    coint_years = sum(windows[i][1] - windows[i][0] for i in coint_windows) / 252.0
    ct = [t for t in all_trades if t["coint"]]
    beta_of = {i: f["beta"] for i, f in enumerate(fits)}
    rand_all = _random_book(pa, pb, windows, all_trades, beta_of, cost_bps)
    rand_ct = _random_book(pa, pb, windows, ct, beta_of, cost_bps)
    b_all, b_ct = _book(all_trades, years), _book(ct, coint_years)

    def rank(book, rnd):
        return round(sum(1 for r in rnd if r < book["total_return_pct"]) / len(rnd) * 100, 1) if rnd else None
    kept = [f["still_coint"] for f in fits if f["coint_level"] is not None and f["still_coint"] is not None]
    return {
        "windows": fits,
        "years_traded": round(years, 1),
        "all": dict(b_all, beats_random_pct=rank(b_all, rand_all),
                    random_median_pct=round(float(np.median(rand_all)), 1) if rand_all else None),
        "coint_only": dict(b_ct, windows=len(coint_windows), years=round(coint_years, 1),
                           beats_random_pct=rank(b_ct, rand_ct),
                           random_median_pct=round(float(np.median(rand_ct)), 1) if rand_ct else None),
        "coint_share_pct": round(len(coint_windows) / len(windows) * 100, 1),
        "stayed_coint_pct": round(sum(kept) / len(kept) * 100, 1) if kept else None,
        "trades": [{k2: v for k2, v in t.items() if not k2.startswith("_") and k2 not in ("entry_index", "exit_index")}
                   for t in all_trades],
    }


def run(a: str, b: str, frame_a, frame_b, raw: Optional[Dict[str, Any]] = None,
        cost_bps: float = COST_BPS) -> Dict[str, Any]:
    import pandas as pd
    prm = params_for(raw or {})
    if a == b:
        return {"available": False, "reason": "Pick a second, different symbol."}
    if frame_a is None or frame_b is None or frame_a.empty or frame_b.empty:
        return {"available": False, "reason": "No price history for one of the two."}
    # Dividends included where the feed has them: a high-yield leg's price
    # alone drifts down against the other's on every ex-date.
    col = lambda f: f["Adj Close"] if "Adj Close" in f and f["Adj Close"].notna().any() else f["Close"]
    sa = col(frame_a).astype(float)
    sb = col(frame_b).astype(float)
    sa.index = pd.to_datetime(sa.index).tz_localize(None).normalize()
    sb.index = pd.to_datetime(sb.index).tz_localize(None).normalize()
    df = pd.concat([sa.rename("a"), sb.rename("b")], axis=1, join="inner").dropna()
    df = df[(df["a"] > 0) & (df["b"] > 0)]
    if len(df) > MAX_YEARS * 252 + FORMATION:
        df = df.iloc[-(MAX_YEARS * 252 + FORMATION):]
    if len(df) < FORMATION + 60:
        return {"available": False, "reason": "Under {} shared sessions of history; a pair needs a formation year "
                                              "and some trading after it.".format(FORMATION + 60)}
    pa, pb = df["a"].to_numpy(), df["b"].to_numpy()
    dates = [d.strftime("%Y-%m-%d") for d in df.index]
    la, lb = np.log(pa), np.log(pb)

    now = fit(la[-FORMATION:], lb[-FORMATION:])
    z_now = (la[-1] - (now["alpha"] + now["beta"] * lb[-1]) - now["mean"]) / now["sd"] if now["sd"] > 0 else None
    zs = (la[-FORMATION:] - (now["alpha"] + now["beta"] * lb[-FORMATION:]) - now["mean"]) / now["sd"]
    step = max(1, FORMATION // 120)
    hist = [{"date": dates[-FORMATION + i], "z": round(float(zs[i]), 3)} for i in range(0, FORMATION, step)]
    if hist[-1]["date"] != dates[-1]:
        hist.append({"date": dates[-1], "z": round(float(zs[-1]), 3)})
    stance = None
    if now["beta"] <= 0:
        stance = ("Over the last year {} and {} moved in opposite directions (a hedge ratio of {:.2f}), so there is no "
                  "spread to trade: buying one and shorting the other would not offset.".format(a, b, now["beta"]))
    elif z_now is not None:
        if z_now >= prm["entry_z"]:
            stance = "{} has run ahead of {} by {:.1f} standard deviations: the rule would short {} and buy {}.".format(
                a, b, z_now, a, b)
        elif z_now <= -prm["entry_z"]:
            stance = "{} has fallen behind {} by {:.1f} standard deviations: the rule would buy {} and short {}.".format(
                a, b, -z_now, a, b)
        else:
            stance = "The spread is {:+.1f} standard deviations from its average: inside the {:g} the rule waits for.".format(
                z_now, prm["entry_z"])
    wf = walk_forward(pa, pb, dates, prm, cost_bps)
    return {
        "available": True,
        "a": a, "b": b, "params": prm, "cost_bps": cost_bps, "borrow_pct": BORROW_PCT,
        "history": {"from": dates[0], "to": dates[-1], "sessions": len(df)},
        "now": {"beta": round(now["beta"], 3), "corr": None if now["corr"] is None else round(now["corr"], 2),
                "adf_t": None if now["adf_t"] is None else round(now["adf_t"], 2), "coint_level": now["coint_level"],
                "half_life": None if now["half_life"] is None else round(now["half_life"], 1),
                "z": None if z_now is None else round(float(z_now), 2), "stance": stance,
                "window": "{} to {}".format(dates[-FORMATION], dates[-1])},
        "z_history": hist,
        "walk_forward": wf,
        "verdict": _verdict(a, b, now, wf),
        "method": ("Dividend-adjusted closes. Log-price spread with alpha and beta from least squares on {} sessions; cointegration by "
                   "Engle-Granger (ADF on the spread, MacKinnon's two-variable critical values); half-life from an "
                   "AR(1) fit. Walk-forward: fit on {} sessions, trade the next {} with those numbers frozen, roll "
                   "on {}. Signals on a close fill at the next close; {} bp a leg a side and {}% a year borrow on "
                   "the short leg; returns on gross exposure.".format(FORMATION, FORMATION, TRADE, TRADE, cost_bps,
                                                                    BORROW_PCT)),
        "caveats": [
            "A pair chosen because it looks related today is chosen with hindsight; the walk-forward cannot remove that.",
            "Closing prices only: a spread can blow out and come back within a day without the test seeing it.",
            "Borrow can cost far more than {}% for a hard-to-borrow name, and a short can be recalled.".format(BORROW_PCT),
            "A cointegration test passed at 5% on one year fails often in the next; see how often it held.",
            "A backtest describes the past. It is not a forecast.",
        ],
    }


def _verdict(a: str, b: str, now: Dict[str, Any], wf: Dict[str, Any]) -> str:
    ct, al = wf["coint_only"], wf["all"]
    held = wf.get("stayed_coint_pct")
    pair = ("{} and {} test as a pair over the last year (cointegrated at {:.0%})".format(a, b, now["coint_level"])
            if now["coint_level"] is not None else
            "{} and {} do not test as a pair over the last year (no cointegration at 10%)".format(a, b))
    if al["trades"] < 10:
        return pair + ". Too few out-of-sample trades ({}) to judge the rule.".format(al["trades"])
    out = pair + ". Out of sample, trading every window: {} trades, {:+.1f}%{}".format(
        al["trades"], al["total_return_pct"],
        ", no better than random days" if (al.get("beats_random_pct") or 0) < 80 else "")
    if ct["trades"]:
        out += "; only when the formation year passed the test: {} trades, {:+.1f}%".format(
            ct["trades"], ct["total_return_pct"])
    if held is not None:
        out += ". The test held in the next window {:.0f}% of the time".format(held)
    return out + "."
