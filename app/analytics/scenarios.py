"""Portfolio scenarios (roadmap stage 6, 2026-10-22): what today's positions would
be worth if something happened, and the exposures that decide it, kept apart.

Pure: positions, quotes, closes and report dates are injected, nothing is
fetched, nothing is stored. Both the Optic Portfolio books (/api/portfolio-risk)
and a linked brokerage (/api/brokerage/workspace/scenarios) call `build`, so the
two views can never disagree about how a position is revalued.

What it keeps apart, because each answers a different question:

* **Premium at risk** (the most the long options can lose), **gross and net
  notional** (the size of what is controlled), and **delta-adjusted exposure**
  (the stock-equivalent dollars it moves like now). An option's notional is not
  its risk and its delta is not its size.
* **Concentration** (where the delta-adjusted money sits) and **correlated
  exposure** (names that have been moving together, measured over a trailing
  window). Low measured correlation is a description of calm markets, not
  protection in a crisis: in a selloff correlations rise toward one, so the
  "everything together" scenarios are reported beside the beta-weighted one.
* **Nonlinear option risk**: every scenario revalues each option in full at the
  shocked price, volatility and date, with the same pricer the Options tab
  uses (Barone-Adesi-Whaley for American equity options, Black-Scholes for
  European index options), and says how far the first-order delta estimate is
  from it.

Every figure is theoretical: a model value at the solved implied volatility,
not a price anyone would pay. Where bid and ask are known, the cost of closing
at them is shown beside it; where they are not, that is said. Positions that
cannot be revalued (no price, no volatility solves, an adjusted contract) are
listed with the reason and left out of every sum, never priced on a guess.

These are hypothetical outcomes for the positions as they stand. They are not
performance, not a forecast and not a probability.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

from . import greeks as greeks_mod
from . import vol_surface
from .position import _leg_value_model

VERSION = "scenarios-2026-10-22.1"

MOVES = (-20, -10, -5, 5, 10, 20)           # every holding together, percent
MARKET = (-20, -10, -5, 5, 10)              # the S&P 500, through each name's beta
VOL_POINTS = (-10, -5, 5, 10)               # implied volatility, in points (30% to 40% is +10)
DAYS = (1, 7, 30)                           # calendar days passing, nothing else changing
CRASH = (-10, 10)                           # every holding -10% and volatility +10 points
EARNINGS_WINDOW_DAYS = 45                   # a report this close is a scenario of its own
EVENT_IV_CRUSH = 0.30                       # same assumption as the Contract Picker's event case
BETA_SESSIONS = 252
MIN_BETA_SESSIONS = 120
CORR_SESSIONS = 63                          # portfolio_risk.WINDOW: a quarter of sessions
HIGH_PAIR = 0.70                            # portfolio_risk.HIGH_PAIR
STALE_TRADING_MINUTES = 60.0                # an option price and its spot this far apart are flagged
OLD_QUOTE_TRADING_MINUTES = 390.0           # a quote a full session old is flagged on its own
STANDARD_MULTIPLIER = 100.0
INDEX_ROOTS = {"SPX", "SPXW", "NDX", "NDXP", "RUT", "RUTW", "XSP", "^SPX", "^NDX", "^RUT"}

def _pm(v: float) -> str:
    """+5%, \u221220%: a minus sign, not a hyphen, in a label."""
    return ("+" if v > 0 else "\u2212" if v < 0 else "") + "{:g}".format(abs(v))


HYPOTHETICAL = ("Hypothetical: what a model says today's positions would be worth if each thing happened. "
                "Not recorded performance, not a forecast and not a probability.")


def _num(v: Any) -> Optional[float]:
    if v is None or isinstance(v, bool):
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _r(v: Optional[float], n: int = 2) -> Optional[float]:
    return None if v is None else round(float(v), n)


def _when(v: Any) -> Optional[datetime]:
    if not v:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if isinstance(v, (int, float)):
        return datetime.fromtimestamp(float(v), tz=timezone.utc)
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _series(c: Any) -> Optional[pd.Series]:
    """Closes as a date-indexed series, from a Series or the workspace's [[date, close], ...]."""
    if c is None:
        return None
    if isinstance(c, pd.Series):
        s = c.dropna()
    else:
        try:
            s = pd.Series([float(v) for _, v in c], index=pd.to_datetime([d for d, _ in c]))
        except (TypeError, ValueError):
            return None
    if s.empty:
        return None
    s.index = pd.to_datetime(s.index).tz_localize(None) if getattr(s.index, "tz", None) is not None else pd.to_datetime(s.index)
    return s[~s.index.duplicated(keep="last")].sort_index()


def _trading_minutes(a: datetime, b: datetime) -> float:
    from app.brokerage.options_risk import trading_minutes_between
    return trading_minutes_between(min(a, b), max(a, b))


# ------------------------------------------------------------------ positions

def _label(p: Dict[str, Any]) -> str:
    if p.get("label"):
        return str(p["label"])
    q = p.get("qty") or 0
    if p.get("kind") == "option":
        return "{} {:g} {} {:g} {}{} {}".format("Short" if q < 0 else "Long", abs(q), p.get("symbol") or "",
                                               _num(p.get("strike")) or 0, p.get("option_type") or "option",
                                               "" if abs(q) == 1 else "s", p.get("expiry") or "")
    return "{} {:g} {} shares".format("Short" if q < 0 else "Long", abs(q), p.get("symbol") or "")


def _prepare(p: Dict[str, Any], spots: Dict[str, Dict[str, Any]], rate: float, now: datetime) -> Dict[str, Any]:
    """One position, priced once at today's inputs, or the reason it cannot be."""
    sym = str(p.get("symbol") or "").upper()
    kind = "option" if p.get("kind") == "option" else "stock"
    qty = _num(p.get("qty")) or 0.0
    sq = spots.get(sym) or {}
    spot = _num(sq.get("price")) or (_num(p.get("spot")) if kind == "option" else None) or (_num(p.get("price")) if kind == "stock" else None)
    spot_at = _when(sq.get("as_of") or p.get("spot_as_of"))
    leg: Dict[str, Any] = {"symbol": sym, "kind": kind, "qty": qty, "label": _label({**p, "symbol": sym, "kind": kind}),
                           "spot": spot, "priced": False, "reason": None, "stale": None, "price_basis": p.get("price_basis"),
                           # the position's own value, priced or not, so coverage is a share of everything held
                           # (with one of five positions priced it said 100%: audit 2026-10-22)
                           "ref_value": _num(p.get("ref_value"))}
    # a caller that passes ref_value None means "no dollar value" (a CAD holding), not "work it out"
    if "ref_value" not in p and _num(p.get("price")) is not None:
        leg["ref_value"] = abs(qty * _num(p.get("price")) * (1.0 if kind == "stock" else (_num(p.get("multiplier")) or STANDARD_MULTIPLIER)))
    if p.get("not_modelled") and kind == "stock":
        leg["reason"] = p["not_modelled"]
        return leg
    if not sym or qty == 0:
        leg["reason"] = "No symbol or no quantity."
        return leg
    if spot is None or spot <= 0:
        leg["reason"] = "No current price for {}.".format(sym)
        return leg
    if spot_at is not None and _trading_minutes(spot_at, now) > OLD_QUOTE_TRADING_MINUTES:
        leg["stale"] = "The {} quote is from {}, more than a session old.".format(sym, spot_at.date().isoformat())
    if kind == "stock":
        if not _num(sq.get("price")):
            # a stock with no current quote was valued at the broker's sync price without a word (audit 2026-10-22)
            leg["stale"] = "No current quote for {}: valued at its last price from the source ({}).".format(
                sym, p.get("price_basis") or "the broker's sync")
        leg.update(priced=True, multiplier=1.0, value=qty * spot, delta_shares=qty, gamma=0.0, vega=0.0, theta=0.0,
                   notional=abs(qty * spot), signed_notional=qty * spot)
        return leg

    mult = _num(p.get("multiplier"))
    leg["multiplier_assumed"] = bool(p.get("multiplier_assumed")) or mult is None
    mult = mult or STANDARD_MULTIPLIER
    otype = str(p.get("option_type") or "").lower()
    strike, expiry = _num(p.get("strike")), str(p.get("expiry") or "")[:10]
    price = _num(p.get("price"))
    bid, ask = _num(p.get("bid")), _num(p.get("ask"))
    is_call = otype == "call"
    leg.update(multiplier=mult, option_type=otype, strike=strike, expiry=expiry, price=price, bid=bid, ask=ask,
               notional=abs(qty) * mult * spot,
               # calls move with the stock and puts against it; a short flips either
               signed_notional=(1.0 if is_call else -1.0) * qty * mult * spot,
               premium_value=price * qty * mult if price is not None else None)
    if p.get("adjusted") or p.get("not_modelled"):
        leg["reason"] = p.get("not_modelled") or p.get("adjusted_reason") or "An adjusted contract: what it delivers is not known."
        return leg
    if otype not in ("call", "put") or not strike or not expiry:
        leg["reason"] = "The option type, strike or expiry is missing."
        return leg
    try:
        expired = now >= vol_surface.expiry_close(expiry)
        tau = vol_surface.expiry_tau(expiry, now)
    except (TypeError, ValueError):
        leg["reason"] = "The expiry date cannot be read."
        return leg
    if expired:
        leg["reason"] = "At or past expiry."
        return leg
    american = p.get("american")
    if american is None:
        american = sym not in INDEX_ROOTS
    q = _num(p.get("dividend_yield")) or 0.0
    iv = _num(p.get("iv"))
    iv_basis = "given"
    if iv is None:
        if price is None or price <= 0:
            leg["reason"] = "No option price, so no implied volatility can be solved."
            return leg
        iv = float(vol_surface.solve_iv(np.array([price]), float(spot), np.array([strike]), np.array([tau]),
                                        rate, q, np.array([is_call]), american=bool(american))[0])
        iv_basis = "solved from the price"
        if not math.isfinite(iv):
            leg["reason"] = "No implied volatility fits its price (at or below intrinsic, or stale)."
            return leg
    opt_at = _when(p.get("price_as_of"))
    if opt_at is not None and spot_at is not None and _trading_minutes(opt_at, spot_at) > STALE_TRADING_MINUTES:
        leg["stale"] = ("The option price ({}) and the {} quote ({}) are more than an hour of trading apart, so the "
                        "solved volatility carries the move between them.".format(opt_at.isoformat(timespec="minutes"),
                                                                                   sym, spot_at.isoformat(timespec="minutes")))
    model = {"type": otype, "strike": strike, "iv": iv, "american": bool(american)}
    base = float(_leg_value_model(model, np.array([spot]), tau, rate, q)[0])
    g = greeks_mod.greeks(float(spot), np.array([strike]), np.array([tau]), np.array([iv]), rate, q, np.array([is_call]))
    scale = qty * mult
    leg.update(priced=True, model=model, tau=tau, q=q, iv=iv, iv_basis=iv_basis, base=base, value=base * scale,
               delta_shares=float(g["delta"][0]) * scale, gamma=float(g["gamma"][0]) * scale,
               vega=float(g["vega"][0]) * scale, theta=float(g["theta"][0]) * scale)
    return leg


def _value(leg: Dict[str, Any], spot: float, days: float, iv_points: float, iv_scale: float,
           rate: float, now: datetime) -> float:
    """The position's value at a shocked spot, date and volatility."""
    if leg["kind"] == "stock":
        return leg["qty"] * spot
    tau = vol_surface.expiry_tau(leg["expiry"], now + timedelta(days=days)) if days else leg["tau"]
    m = dict(leg["model"], iv=max(leg["iv"] * iv_scale + iv_points / 100.0, 0.01))
    return float(_leg_value_model(m, np.array([spot]), max(tau, 0.0), rate, leg["q"])[0]) * leg["qty"] * leg["multiplier"]


# ------------------------------------------------------------------ market inputs

def betas(closes: Dict[str, Any], bench: str = "SPY") -> Dict[str, Dict[str, Any]]:
    """Beta to the benchmark from daily log returns over the last year."""
    b = _series(closes.get(bench))
    out: Dict[str, Dict[str, Any]] = {}
    if b is None:
        return out
    for sym, c in closes.items():
        s = _series(c)
        if s is None or sym == bench:
            continue
        j = pd.concat([np.log(s).diff(), np.log(b).diff()], axis=1, join="inner").dropna().tail(BETA_SESSIONS)
        if len(j) < MIN_BETA_SESSIONS:
            out[sym] = {"beta": None, "sessions": len(j)}
            continue
        var = float(j.iloc[:, 1].var())
        out[sym] = {"beta": round(float(j.iloc[:, 0].cov(j.iloc[:, 1])) / var, 2) if var > 0 else None, "sessions": len(j)}
    if bench in closes:
        out[bench] = {"beta": 1.0, "sessions": None}
    return out


def _clusters(closes: Dict[str, Any], syms: List[str]) -> Tuple[List[List[str]], Dict[Tuple[str, str], float]]:
    """Names joined by a trailing correlation of HIGH_PAIR or more, as groups."""
    rets = {}
    for s in syms:
        c = _series(closes.get(s))
        if c is not None and len(c) > CORR_SESSIONS:
            rets[s] = np.log(c).diff().dropna().tail(CORR_SESSIONS)
    names = sorted(rets)
    pairs: Dict[Tuple[str, str], float] = {}
    parent = {s: s for s in names}

    def root(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            j = pd.concat([rets[a], rets[b]], axis=1, join="inner").dropna()
            if len(j) < 30:
                continue
            c = float(j.iloc[:, 0].corr(j.iloc[:, 1]))
            if math.isfinite(c):
                pairs[(a, b)] = c
                if c >= HIGH_PAIR:
                    parent[root(a)] = root(b)
    groups: Dict[str, List[str]] = {}
    for s in names:
        groups.setdefault(root(s), []).append(s)
    return [g for g in groups.values() if len(g) > 1], pairs


def report_move(closes: Any, report_dates: Iterable[str], before_open: Iterable[str] = ()) -> Optional[Dict[str, Any]]:
    """The median absolute one-session move on this stock's past reports, from its own closes."""
    from .earnings import _reaction_map
    s = _series(closes)
    if s is None:
        return None
    moves = [abs(v) for v in _reaction_map(pd.DataFrame({"Close": s}), list(report_dates), set(before_open)).values() if v is not None]
    if len(moves) < 3:
        return None
    return {"move_pct": round(float(np.median(moves)), 2), "reports": len(moves),
            "basis": "the median of its last {} report-day moves".format(len(moves))}


# ------------------------------------------------------------------ the book

def build(positions: List[Dict[str, Any]], spots: Dict[str, Dict[str, Any]], closes: Dict[str, Any],
          rate: Optional[float] = None, now: Optional[datetime] = None,
          earnings: Optional[Dict[str, Dict[str, Any]]] = None, sectors: Optional[Dict[str, str]] = None,
          stock_shares: Optional[Dict[str, float]] = None, source: str = "") -> Dict[str, Any]:
    """Exposures and scenarios for `positions`.

    Each position: symbol, kind ('stock' or 'option'), qty (signed shares or
    signed contracts), price (per share: the mark), price_as_of, price_basis;
    for an option also option_type, strike, expiry, multiplier (None when the
    source did not say), iv (optional; solved from price otherwise), bid and
    ask (optional), american (optional), adjusted (optional). `spots` is
    {symbol: {price, as_of}}; `closes` is daily closes per symbol with SPY for
    the betas; `earnings` is {symbol: {date, move_pct, basis}}.
    """
    now = now or datetime.now(timezone.utc)
    now = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    r = _num(rate) or 0.0
    legs = [_prepare(p, spots or {}, r, now) for p in positions or []]
    if not legs:
        return {"available": False, "version": VERSION, "reason": "No open positions."}
    priced = [l for l in legs if l["priced"]]
    unpriced = [{"label": l["label"], "reason": l["reason"]} for l in legs if not l["priced"]]
    if not priced:
        return {"available": False, "version": VERSION, "reason": "No position could be revalued.", "coverage": {"unpriced": unpriced}}
    syms = sorted({l["symbol"] for l in priced})
    spot_of = {l["symbol"]: l["spot"] for l in priced}
    options = [l for l in legs if l["kind"] == "option"]
    p_opts = [l for l in priced if l["kind"] == "option"]

    # ---- exposures
    by: Dict[str, Dict[str, Any]] = {}
    for l in legs:
        row = by.setdefault(l["symbol"], {"symbol": l["symbol"], "stock_value": 0.0, "option_delta_dollars": 0.0,
                                          "notional": 0.0, "positions": 0, "unpriced": 0, "sector": (sectors or {}).get(l["symbol"])})
        row["positions"] += 1
        row["notional"] += l.get("notional") or 0.0
        if not l["priced"]:
            row["unpriced"] += 1
            continue
        if l["kind"] == "stock":
            row["stock_value"] += l["value"]
        else:
            row["option_delta_dollars"] += l["delta_shares"] * l["spot"]
    for row in by.values():
        row["delta_adjusted"] = row["stock_value"] + row["option_delta_dollars"]
        row["priced"] = row["positions"] - row["unpriced"]
    gross_da = sum(abs(r_["delta_adjusted"]) for r_ in by.values())
    rows = sorted(by.values(), key=lambda x: -abs(x["delta_adjusted"]))
    for row in rows:
        row["share_pct"] = _r(100.0 * abs(row["delta_adjusted"]) / gross_da, 1) if gross_da else None
        for k in ("stock_value", "option_delta_dollars", "notional", "delta_adjusted"):
            row[k] = _r(row[k])
        if not row["priced"]:
            # nothing in this name could be valued: unknown, not 0.0 (audit 2026-10-22)
            row.update(stock_value=None, option_delta_dollars=None, delta_adjusted=None, share_pct=None,
                       note="Not valued: no position in {} could be priced.".format(row["symbol"]))
    w = np.array([abs(x["delta_adjusted"]) / gross_da for x in rows if x["delta_adjusted"] is not None]) if gross_da else np.array([])
    hhi = float((w ** 2).sum()) if len(w) else None
    sector_share: Dict[str, float] = {}
    for row in rows:
        if row["sector"] and gross_da and row["delta_adjusted"] is not None:
            sector_share[row["sector"]] = sector_share.get(row["sector"], 0.0) + abs(row["delta_adjusted"]) / gross_da * 100.0
    clusters, pairs = _clusters(closes or {}, syms)
    correlated = []
    for g in clusters:
        da = sum(abs(by[s]["delta_adjusted"]) for s in g)
        cs = [c for (a, b), c in pairs.items() if a in g and b in g]
        correlated.append({"names": g, "delta_adjusted": _r(da), "share_pct": _r(100.0 * da / gross_da, 1) if gross_da else None,
                           "avg_correlation": _r(sum(cs) / len(cs), 2) if cs else None})
    correlated.sort(key=lambda c: -(c["delta_adjusted"] or 0))

    shares_held = {str(k).upper(): float(v) for k, v in (stock_shares or {}).items()}
    for l in legs:
        if l["kind"] == "stock" and l["priced"] and not stock_shares:
            shares_held[l["symbol"]] = shares_held.get(l["symbol"], 0.0) + l["qty"]
    uncovered_calls = []
    for s in sorted({l["symbol"] for l in options}):
        short_calls = sum(-l["qty"] * l["multiplier"] for l in options if l["symbol"] == s and l.get("option_type") == "call" and l["qty"] < 0)
        long_calls = sum(l["qty"] * l["multiplier"] for l in options if l["symbol"] == s and l.get("option_type") == "call" and l["qty"] > 0)
        bare = short_calls - long_calls - max(shares_held.get(s, 0.0), 0.0)
        if short_calls > 0 and bare > 0:
            uncovered_calls.append({"symbol": s, "shares_uncovered": _r(bare, 0)})

    exposure = {
        "premium_at_risk": _r(sum(l["premium_value"] for l in options if l["qty"] > 0 and l.get("premium_value") is not None)),
        "short_premium": _r(-sum(l["premium_value"] for l in options if l["qty"] < 0 and l.get("premium_value") is not None)),
        "uncovered_short_calls": uncovered_calls,
        "gross_notional": _r(sum(l.get("notional") or 0.0 for l in legs)),
        "net_notional": _r(sum(l.get("signed_notional") or 0.0 for l in legs)),
        "delta_adjusted_gross": _r(gross_da), "delta_adjusted_net": _r(sum(x["delta_adjusted"] or 0.0 for x in rows)),
        "by_underlying": rows,
        "concentration": {"largest": rows[0]["symbol"] if rows and rows[0]["share_pct"] is not None else None,
                          "largest_pct": rows[0]["share_pct"] if rows else None,
                          "top3_pct": _r(sum(x["share_pct"] or 0 for x in rows[:3]), 1),
                          "effective_names": _r(1.0 / hhi, 1) if hhi else None,
                          "sectors": sorted(({"sector": k, "share_pct": _r(v, 1)} for k, v in sector_share.items()), key=lambda x: -x["share_pct"])},
        "correlated": correlated,
        "correlated_note": ("Groups of names whose daily moves correlated at {:.2f} or more over the last {} sessions. "
                            "Correlation measured in calm markets is not protection: in a selloff it rises toward one, "
                            "which is why the scenarios below move every holding together as well as by beta."
                            .format(HIGH_PAIR, CORR_SESSIONS)),
        "nonlinear": {"gamma_1pct": _r(sum(0.5 * l["gamma"] * (0.01 * l["spot"]) ** 2 for l in p_opts)) if p_opts else None,
                      "vega_per_point": _r(sum(l["vega"] for l in p_opts)) if p_opts else None,
                      "theta_per_day": _r(sum(l["theta"] for l in p_opts)) if p_opts else None},
        "basis": ("Delta-adjusted: shares at their price, each option at delta x the stock's price x contracts x shares "
                  "per contract. Notional: shares at their price, each option at contracts x shares per contract x the "
                  "stock's price; in the net figure a call counts with the stock and a put against it."),
    }

    # ---- scenarios
    def run(shock: Callable[[str], Optional[float]], days: float = 0.0, iv_points: float = 0.0,
            iv_scale: Callable[[Dict[str, Any]], float] = lambda l: 1.0) -> Dict[str, Any]:
        tot = stock = opt = est = 0.0
        per: Dict[str, float] = {}
        left_out = set()
        for l in priced:
            m = shock(l["symbol"])
            if m is None:
                left_out.add(l["symbol"])
                continue
            s1 = l["spot"] * (1.0 + m / 100.0)
            pnl = _value(l, s1, days, iv_points, iv_scale(l), r, now) - l["value"]
            tot += pnl
            per[l["symbol"]] = per.get(l["symbol"], 0.0) + pnl
            if l["kind"] == "stock":
                stock += pnl
            else:
                opt += pnl
            est += l["delta_shares"] * l["spot"] * m / 100.0
        worst = sorted(per.items(), key=lambda kv: kv[1])[:3]
        return {"pnl": _r(tot), "stock_pnl": _r(stock), "option_pnl": _r(opt) if p_opts else None,
                "delta_estimate": _r(est) if (p_opts and not days and not iv_points) else None,
                "worst": [{"symbol": k, "pnl": _r(v)} for k, v in worst if v < 0],
                "left_out": sorted(left_out)}

    value_now = sum(l["value"] for l in priced)
    gross_value = sum(abs(l["value"]) for l in priced)
    beta = betas(closes or {})
    groups = []
    together = []
    for m in MOVES:
        out = run(lambda s, m=m: m)
        together.append({"id": "all{:+d}".format(m), "label": "Every holding {}%".format(_pm(m)), "move_pct": m, **out})
    groups.append({"id": "together", "title": "Every holding moves together",
                   "note": "No offsetting: the case a crisis tends toward. Implied volatility and the date are left as they are.",
                   "rows": together})
    market = []
    no_beta = sorted(s for s in syms if (beta.get(s) or {}).get("beta") is None)
    for m in MARKET:
        out = run(lambda s, m=m: None if (beta.get(s) or {}).get("beta") is None else beta[s]["beta"] * m)
        market.append({"id": "spx{:+d}".format(m), "label": "S&P 500 {}%".format(_pm(m)), "move_pct": m, **out})
    groups.append({"id": "market", "title": "A market move, through each holding's beta",
                   "note": ("Each holding moves by its beta to SPY over the last year times the market's move. Betas are "
                            "measured in ordinary markets and rise in selloffs, so this is the milder case; compare it with "
                            "every holding moving together." + (" No beta for {} (too little history), left out.".format(", ".join(no_beta)) if no_beta else "")),
                   "betas": [{"symbol": s, "beta": (beta.get(s) or {}).get("beta")} for s in syms], "rows": market})
    if p_opts:
        vol = [{"id": "iv{:+d}".format(v), "label": "Implied volatility {} points".format(_pm(v)), "iv_points": v,
                **run(lambda s: 0.0, iv_points=v)} for v in VOL_POINTS]
        groups.append({"id": "volatility", "title": "Volatility expands or contracts",
                       "note": "Every option's implied volatility moved by the same number of points, prices unchanged. Shares are unaffected.",
                       "rows": vol})
        time_rows = [{"id": "t{}".format(d), "label": "{} day{} pass{}".format(d, "" if d == 1 else "s", "es" if d == 1 else ""), "days": d,
                      **run(lambda s: 0.0, days=d)} for d in DAYS]
        groups.append({"id": "time", "title": "Time passes",
                       "note": "Prices and implied volatility unchanged; an option that expires inside the window is valued at what it is worth at expiry.",
                       "rows": time_rows})
        crash = run(lambda s: CRASH[0], iv_points=CRASH[1])
        groups.append({"id": "shock", "title": "A market shock",
                       "note": "Every holding {}% together and implied volatility {} points: a selloff as options usually see one.".format(_pm(CRASH[0]), _pm(CRASH[1])),
                       "rows": [{"id": "crash", "label": "Holdings {}%, volatility {} points".format(_pm(CRASH[0]), _pm(CRASH[1])), **crash}]})
    ev_rows = []
    for s in syms:
        e = (earnings or {}).get(s) or {}
        when, mv = e.get("date"), _num(e.get("move_pct"))
        if not when:
            continue
        try:
            days_to = (datetime.fromisoformat(str(when)[:10]).date() - now.astimezone(vol_surface.ET).date()).days
        except ValueError:
            continue
        if not (0 <= days_to <= EARNINGS_WINDOW_DAYS):
            continue
        if mv is None:
            ev_rows.append({"id": "er-" + s, "symbol": s, "date": str(when)[:10], "label": "{} reports {}".format(s, str(when)[:10]),
                            "unavailable": "Too few past reports to size its move, so no scenario is shown."})
            continue
        after = days_to + 1

        def crush(l: Dict[str, Any], s: str = s, when: str = str(when)[:10]) -> float:
            return 1.0 - EVENT_IV_CRUSH if l["symbol"] == s and l["kind"] == "option" and l["expiry"] > when else 1.0
        up = run(lambda x, s=s, mv=mv: mv if x == s else 0.0, days=after, iv_scale=crush)
        down = run(lambda x, s=s, mv=mv: -mv if x == s else 0.0, days=after, iv_scale=crush)
        ev_rows.append({"id": "er-" + s, "symbol": s, "date": str(when)[:10], "move_pct": mv, "basis": e.get("basis"),
                        "label": "{} reports {} ({} days)".format(s, str(when)[:10], days_to), "up": up, "down": down})
    if ev_rows:
        groups.append({"id": "earnings", "title": "Reports ahead",
                       "note": ("Each name moves by its own typical report-day move, up and down, valued the day after the "
                                "report, with its options' implied volatility {:.0%} lower where they expire after it. "
                                "Other holdings unchanged.".format(EVENT_IV_CRUSH)),
                       "rows": ev_rows})

    # ---- coverage and the price you could actually get
    quoted = [l for l in p_opts if l.get("bid") is not None and l.get("ask") is not None and l["ask"] >= l["bid"] > 0]
    spread = sum(((l["base"] - l["bid"]) if l["qty"] > 0 else (l["ask"] - l["base"])) * abs(l["qty"]) * l["multiplier"] for l in quoted)
    marks = {"theoretical_value": _r(value_now),
             "options_with_quotes": len(quoted), "options_priced": len(p_opts),
             "closing_cost": _r(spread) if quoted else None,
             "note": (("Closing the {} option position{} with bid and ask at them would realise {} less than their model "
                       "value.".format(len(quoted), "" if len(quoted) == 1 else "s", "${:,.0f}".format(abs(spread))) if quoted else
                       "No bid or ask came with these options, so the cost of closing at the market is not known; it is "
                       "at least the spread, and wider in a fast market.") if p_opts else
                      "Shares are valued at their last price; a large order would move it.")}
    coverage = {
        "positions": len(legs), "priced": len(priced), "unpriced": unpriced,
        "stale": [{"label": l["label"], "reason": l["stale"]} for l in legs if l.get("stale")],
        "multiplier_assumed": [l["label"] for l in options if l.get("multiplier_assumed")],
        "iv_solved": sum(1 for l in p_opts if l.get("iv_basis") == "solved from the price"),
        "value_covered_pct": None,
    }
    # over every position with a value of its own, priced or not; a position with no value at all is counted
    # in `positions` and listed, and the share says what it rests on
    known = [l for l in legs if l.get("ref_value") is not None or l["priced"]]
    num_v = sum(abs(l["value"]) if l["priced"] else 0.0 for l in known)
    den_v = sum(abs(l["value"]) if l["priced"] else (l.get("ref_value") or 0.0) for l in known)
    coverage["value_covered_pct"] = _r(100.0 * num_v / den_v, 1) if den_v else None
    coverage["valued_positions"] = len(known)
    return {
        "available": True, "version": VERSION, "as_of": now.isoformat(timespec="seconds"), "source": source,
        "hypothetical": HYPOTHETICAL, "value_now": _r(value_now), "gross_value": _r(gross_value),
        "exposure": exposure, "groups": groups, "marks": marks, "coverage": coverage,
        "rate": r,
        "method": ("Every scenario revalues each position in full: shares at the shocked price; each option with "
                   "Barone-Adesi-Whaley (American equity options) or Black-Scholes (European index options) at the shocked "
                   "price, date and implied volatility, starting from the volatility its own price solves to, at a {:.2%} "
                   "risk-free rate. P/L is against the same model's value today, so a mark that differs from the model "
                   "does not show up as a scenario loss. The delta estimate is the first-order approximation; the gap "
                   "between the two is the options' convexity.".format(r)),
    }
