"""Quote quality, a consistent implied-volatility surface, and the term structure.

Three things the chain needed before any number built on it could be trusted
(Options audit, 2026-10-13; the 2026-10-11 analysis measured each):

**1. The clock.** Time to expiry was whole calendar days from the server's
local date (UTC on the host), floored at six hours. Listed US equity and ETF
options stop trading at 4:00pm ET on the expiry date, so after 8pm ET a UTC
server counted every contract a day short, and every expiry-day contract had
six hours left whatever the time. `expiry_tau` measures to 4:00pm ET on the
expiry date from now, in calendar years. AM-settled index options (standard
SPX, NDX, RUT monthlies) settle on the opening print instead; the chains Optic
reads are equities and ETFs, and an index symbol gets the same clock plus a
note.

**2. The quote.** A mid of (bid + ask) / 2 only means something when both sides
are quoted and the ask is above the bid. The chain fell back to the last trade
otherwise, which can be days old, and priced "spread %" from a zero bid.
`quote_state` names the state of every contract: two-sided, locked (bid ==
ask), crossed (bid > ask), no bid, no ask or no quote; only a two-sided quote
has a mid and a spread.

**3. The volatility.** The feed's implied vols are Yahoo's, solved with
inputs Optic cannot see; priced with Optic's own rate they disagree with
put-call parity, so calls read 2 to 4 vol points richer than puts at the same
strike (the "chase bid" artefact). Here each two-sided mid is re-solved for
its Black-Scholes IV at Optic's rate and dividend yield. Then, per expiry and
strike, the out-of-the-money side's IV is used for both contracts: OTM quotes
carry almost no early-exercise value, so a European model fits them, while an
in-the-money American put's price includes an exercise premium the model would
misread as volatility. This is the convention behind Cboe's VIX strike
selection and most vendor surfaces. Where neither side has a usable quote the
feed's IV stays, flagged, and where the feed has none the existing fill does.

Everything is labelled with its source: `iv_source` is "otm_mid", "own_mid"
(the OTM side had no quote), "feed" or "filled".
"""

from __future__ import annotations

from datetime import datetime, time as dtime, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from scipy.special import ndtr

ET = ZoneInfo("America/New_York")
YEAR_SECONDS = 365.0 * 24 * 3600
MIN_TAU = 1.0 / (365.0 * 24.0)          # an hour: keeps gamma finite at the bell
INDEX_ROOTS = {"^SPX", "SPX", "^NDX", "NDX", "^RUT", "RUT", "^XSP", "XSP", "^VIX", "VIX"}


# ----------------------------------------------------------------- the clock

def expiry_close(expiry: str) -> datetime:
    """4:00pm ET on the expiry date, as an aware datetime."""
    day = pd.Timestamp(expiry).date()
    return datetime.combine(day, dtime(16, 0), tzinfo=ET)


def expiry_tau(expiry: str, now: Optional[datetime] = None) -> float:
    """Calendar years from now to the 4:00pm ET close on the expiry date."""
    now = now or datetime.now(timezone.utc)
    seconds = (expiry_close(expiry) - now.astimezone(ET)).total_seconds()
    return max(seconds / YEAR_SECONDS, MIN_TAU)


def expiry_dte(expiry: str, now: Optional[datetime] = None) -> int:
    """Calendar days to the expiry date, counted on the ET calendar."""
    now = now or datetime.now(timezone.utc)
    return max((pd.Timestamp(expiry).date() - now.astimezone(ET).date()).days, 0)


def apply_clock(chain: pd.DataFrame, now: Optional[datetime] = None) -> pd.DataFrame:
    """Replace the chain's dte/tau with the ET 4pm clock. Pure: returns a copy."""
    if chain is None or chain.empty or "expiry" not in chain:
        return chain
    out = chain.copy()
    now = now or datetime.now(timezone.utc)
    taus = {e: expiry_tau(e, now) for e in out["expiry"].unique()}
    dtes = {e: expiry_dte(e, now) for e in out["expiry"].unique()}
    out["tau"] = out["expiry"].map(taus).astype(float)
    out["dte"] = out["expiry"].map(dtes).astype(int)
    out.attrs["clock"] = "4:00pm ET on the expiry date, calendar time, measured {}".format(
        now.astimezone(ET).strftime("%Y-%m-%d %H:%M ET"))
    return out


# ----------------------------------------------------------------- the quote

QUOTE_STATES = ("two_sided", "locked", "crossed", "no_bid", "no_ask", "no_quote")


def quote_state(bid: pd.Series, ask: pd.Series) -> np.ndarray:
    b = pd.to_numeric(bid, errors="coerce").fillna(0.0).to_numpy()
    a = pd.to_numeric(ask, errors="coerce").fillna(0.0).to_numpy()
    state = np.full(len(b), "no_quote", dtype=object)
    state[(b > 0) & (a <= 0)] = "no_ask"
    state[(b <= 0) & (a > 0)] = "no_bid"
    both = (b > 0) & (a > 0)
    state[both & (a > b)] = "two_sided"
    state[both & (a == b)] = "locked"
    state[both & (a < b)] = "crossed"
    return state


def apply_quotes(chain: pd.DataFrame, now: Optional[datetime] = None) -> pd.DataFrame:
    """Quote state, a mid only for a two-sided quote, absolute and percentage
    spread, and how old the last trade is. Pure: returns a copy.

    `mid` keeps its old meaning for the panels that read it (the last trade
    where there is no two-sided quote) and `mark_source` says which it is, so
    nothing downstream silently changes; `quote_mid` is the strict one."""
    if chain is None or chain.empty:
        return chain
    out = chain.copy()
    now = now or datetime.now(timezone.utc)
    out["quote_state"] = quote_state(out.get("bid"), out.get("ask"))
    two = out["quote_state"] == "two_sided"
    bid = pd.to_numeric(out.get("bid"), errors="coerce")
    ask = pd.to_numeric(out.get("ask"), errors="coerce")
    out["quote_mid"] = np.where(two, (bid + ask) / 2.0, np.nan)
    out["spread_abs"] = np.where(two, ask - bid, np.nan)
    out["spread_pct"] = np.where(two, (ask - bid) / ((bid + ask) / 2.0) * 100.0, np.nan)
    last = pd.to_numeric(out.get("last"), errors="coerce")
    out["mid"] = np.where(two, out["quote_mid"], last)
    out["mark_source"] = np.where(two, "mid", np.where(last > 0, "last", "none"))
    if "last_trade" in out:
        lt = pd.to_datetime(out["last_trade"], errors="coerce", utc=True)
        age = (pd.Timestamp(now) - lt).dt.total_seconds() / 3600.0
        out["last_trade_age_h"] = age.round(1)
    else:
        out["last_trade_age_h"] = np.nan
    return out


# ----------------------------------------------------------------- the model

def _bs(spot, strike, tau, vol, rate, div, is_call):
    vsqrt = vol * np.sqrt(tau)
    d1 = (np.log(spot / strike) + (rate - div + 0.5 * vol * vol) * tau) / vsqrt
    d2 = d1 - vsqrt
    dq, dr = np.exp(-div * tau), np.exp(-rate * tau)
    call = spot * dq * ndtr(d1) - strike * dr * ndtr(d2)
    put = strike * dr * ndtr(-d2) - spot * dq * ndtr(-d1)
    return np.where(is_call, call, put)


def solve_iv(price, spot, strike, tau, rate, div, is_call, lo=1e-3, hi=5.0, iters=64):
    """Vectorised bisection for Black-Scholes IV. NaN where the price lies
    outside the no-arbitrage bounds (below discounted intrinsic, above the
    spot for a call or the discounted strike for a put)."""
    price = np.asarray(price, dtype=float)
    strike = np.asarray(strike, dtype=float)
    tau = np.maximum(np.asarray(tau, dtype=float), MIN_TAU)
    is_call = np.asarray(is_call, dtype=bool)
    dq, dr = np.exp(-div * tau), np.exp(-rate * tau)
    fwd_intr = np.where(is_call, spot * dq - strike * dr, strike * dr - spot * dq)
    lower = np.maximum(fwd_intr, 0.0)
    upper = np.where(is_call, spot * dq, strike * dr)
    ok = np.isfinite(price) & (price > lower + 1e-9) & (price < upper - 1e-9) & (strike > 0)
    a = np.full(price.shape, lo)
    b = np.full(price.shape, hi)
    for _ in range(iters):
        m = 0.5 * (a + b)
        model = _bs(spot, strike, tau, m, rate, div, is_call)
        high = model > price
        b = np.where(high, m, b)
        a = np.where(high, a, m)
    iv = 0.5 * (a + b)
    iv = np.where(ok & (iv > lo * 1.5) & (iv < hi * 0.99), iv, np.nan)
    return iv


def resolve_surface(chain: pd.DataFrame, spot: float, rate: float, div: float) -> pd.DataFrame:
    """Re-solve IVs from two-sided mids, OTM side per strike. Pure: a copy."""
    if chain is None or chain.empty or not spot:
        return chain
    out = chain.copy()
    if "quote_state" not in out:
        out = apply_quotes(out)
    out["iv_feed"] = out["iv"]
    filled = out["iv_filled"].astype(bool) if "iv_filled" in out else pd.Series(False, index=out.index)
    solved = solve_iv(out["quote_mid"].to_numpy(), float(spot), out["strike"].to_numpy(),
                      out["tau"].to_numpy(), rate, div, out["is_call"].to_numpy())
    out["iv_mid"] = solved
    fwd = spot * np.exp((rate - div) * out["tau"].to_numpy())
    out["otm"] = np.where(out["is_call"].to_numpy(), out["strike"].to_numpy() >= fwd,
                          out["strike"].to_numpy() < fwd)
    # The OTM side's solved IV for each (expiry, strike).
    otm_iv = (out[out["otm"]].groupby(["expiry", "strike"])["iv_mid"].first())
    key = pd.MultiIndex.from_arrays([out["expiry"], out["strike"]])
    out["iv_otm"] = otm_iv.reindex(key).to_numpy()
    iv = np.where(np.isfinite(out["iv_otm"]), out["iv_otm"],
                  np.where(np.isfinite(out["iv_mid"]), out["iv_mid"], out["iv_feed"]))
    source = np.where(np.isfinite(out["iv_otm"]), "otm_mid",
                      np.where(np.isfinite(out["iv_mid"]), "own_mid",
                               np.where(filled.to_numpy(), "filled", "feed")))
    out["iv"] = iv
    out["iv_source"] = source
    out.attrs.update(chain.attrs)
    out.attrs["iv_method"] = ("Black-Scholes IV re-solved from each two-sided mid at Optic's rate and "
                              "dividend yield; the out-of-the-money side's IV is used for both "
                              "contracts at a strike.")
    return out


def _delta(spot, strike, tau, vol, rate, div, is_call):
    d1 = (np.log(spot / strike) + (rate - div + 0.5 * vol * vol) * tau) / (vol * np.sqrt(tau))
    dq = np.exp(-div * tau)
    return np.where(is_call, dq * ndtr(d1), dq * (ndtr(d1) - 1.0))


def _f(x: Any, digits: int = 4) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return round(v, digits) if np.isfinite(v) else None


def expiry_rows(chain: pd.DataFrame, spot: float, rate: float, div: float) -> List[Dict[str, Any]]:
    """Per expiry: ATM IV at the forward, 25-delta risk reversal, the ATM
    straddle and the two expected-move readings, and how much is quoted."""
    rows: List[Dict[str, Any]] = []
    if chain is None or chain.empty:
        return rows
    for exp, g in chain.groupby("expiry"):
        tau = float(g["tau"].iloc[0])
        fwd = spot * np.exp((rate - div) * tau)
        otm = g[g["otm"] & g["iv_source"].isin(["otm_mid"])] if "otm" in g else g.iloc[0:0]
        # ATM IV: interpolate total variance in log-moneyness between the two
        # OTM strikes either side of the forward.
        atm_iv = None
        if len(otm) >= 2:
            pts = otm.groupby("strike")["iv"].first().sort_index()
            k = np.log(pts.index.to_numpy() / fwd)
            w = (pts.to_numpy() ** 2) * tau
            if k.min() <= 0 <= k.max():
                atm_iv = float(np.sqrt(np.interp(0.0, k, w) / tau))
            else:
                atm_iv = float(pts.iloc[int(np.argmin(np.abs(k)))])
        # 25-delta risk reversal: put IV at -0.25 delta minus call IV at +0.25.
        rr = None
        calls = g[g["is_call"] & (g["iv_source"] == "otm_mid")]
        puts = g[~g["is_call"] & (g["iv_source"] == "otm_mid")]
        if len(calls) >= 2 and len(puts) >= 2:
            cd = _delta(spot, calls["strike"].to_numpy(), tau, calls["iv"].to_numpy(), rate, div, True)
            pdl = _delta(spot, puts["strike"].to_numpy(), tau, puts["iv"].to_numpy(), rate, div, False)
            ci = int(np.argmin(np.abs(cd - 0.25)))
            pi = int(np.argmin(np.abs(pdl + 0.25)))
            if abs(cd[ci] - 0.25) <= 0.08 and abs(pdl[pi] + 0.25) <= 0.08:
                rr = float(puts["iv"].to_numpy()[pi] - calls["iv"].to_numpy()[ci])
        # ATM straddle at the strike nearest the forward with both sides quoted.
        straddle = None
        strike_used = None
        both = g[g["quote_state"] == "two_sided"]
        paired = both.groupby("strike").filter(lambda s: s["is_call"].nunique() == 2)
        if not paired.empty:
            ks = np.array(sorted(paired["strike"].unique()))
            kk = float(ks[int(np.argmin(np.abs(ks - fwd)))])
            if abs(kk / spot - 1) <= 0.05:
                legs = paired[paired["strike"] == kk]
                straddle = float(legs["quote_mid"].sum())
                strike_used = kk
        quoted = int((g["quote_state"] == "two_sided").sum())
        rows.append({
            "expiry": exp,
            "dte": int(g["dte"].iloc[0]),
            "tau_years": _f(tau, 6),
            "atm_iv_pct": _f(atm_iv * 100 if atm_iv else None, 2),
            "rr25_pts": _f(rr * 100 if rr is not None else None, 2),
            "straddle": _f(straddle, 2),
            "straddle_strike": strike_used,
            "straddle_move_pct": _f(straddle / spot * 100 if straddle else None, 2),
            "one_sd_move_pct": _f(atm_iv * np.sqrt(tau) * 100 if atm_iv else None, 2),
            "contracts": int(len(g)),
            "two_sided": quoted,
            "open_interest": _f(float(g["open_interest"].fillna(0).sum()), 0),
        })
    rows.sort(key=lambda r: r["tau_years"] or 0)
    return rows


def constant_maturity(rows: List[Dict[str, Any]], days: int = 30) -> Dict[str, Any]:
    """ATM IV at a fixed tenor, interpolated in total variance between the two
    expiries that bracket it. Outside the listed range it is not extrapolated."""
    pts = [(r["tau_years"], r["atm_iv_pct"] / 100.0) for r in rows if r.get("atm_iv_pct") and r.get("tau_years")]
    t = days / 365.0
    if len(pts) < 2:
        return {"available": False, "reason": "fewer than two expiries with an at-the-money IV"}
    pts.sort()
    lo = [p for p in pts if p[0] <= t]
    hi = [p for p in pts if p[0] >= t]
    if not lo or not hi:
        return {"available": False, "reason": "no listed expiry on each side of {} days".format(days)}
    (t1, v1), (t2, v2) = lo[-1], hi[0]
    if t2 == t1:
        iv = v1
    else:
        w = v1 * v1 * t1 + (v2 * v2 * t2 - v1 * v1 * t1) * (t - t1) / (t2 - t1)
        iv = float(np.sqrt(max(w, 0.0) / t))
    return {"available": True, "days": days, "iv_pct": _f(iv * 100, 2),
            "method": "Total variance interpolated between the expiries either side of {} days.".format(days)}


def term_read(rows: List[Dict[str, Any]], event_date: Optional[str] = None) -> Dict[str, Any]:
    """Front against back ATM IV, said plainly.

    The front is the first expiry at least a week out: weeklies a few days
    from expiry carry weekend and calendar effects that swing their IV (SPY's
    Friday-close chain had 9.8% to 11.6% across four expiries inside a week),
    and an "inverted" call from them named an event that was not there."""
    pts = [r for r in rows if r.get("atm_iv_pct")]
    if len(pts) < 2:
        return {"available": False, "reason": "fewer than two expiries with an at-the-money IV"}
    front = next((r for r in pts if r["dte"] >= 7), pts[0])
    back = pts[-1]
    if front is back:
        return {"available": False, "reason": "one expiry a week or more out"}
    ratio = front["atm_iv_pct"] / back["atm_iv_pct"]
    shape = "inverted" if ratio > 1.05 else "upward" if ratio < 0.95 else "flat"
    words = {
        "inverted": "Near-dated options carry more implied volatility than later ones",
        "upward": "Later-dated options carry more implied volatility than near-dated ones",
        "flat": "Implied volatility is about the same across expiries",
    }[shape]
    text = "{} ({:.1f}% for {} against {:.1f}% for {}).".format(
        words, front["atm_iv_pct"], front["expiry"], back["atm_iv_pct"], back["expiry"])
    with_event = [r["expiry"] for r in pts if r.get("contains_event")]
    if with_event:
        text += " The company's report on {} falls inside the {} expiry{}, which usually lifts its IV.".format(
            event_date, with_event[0], " and later ones" if len(with_event) > 1 else "")
    elif shape == "inverted":
        text += " No scheduled company event falls inside these expiries in Optic's data, so the reason is not known from this page."
    return {"available": True, "shape": shape, "front": front["expiry"], "back": back["expiry"],
            "front_iv_pct": front["atm_iv_pct"], "back_iv_pct": back["atm_iv_pct"],
            "ratio": _f(ratio, 3), "text": text,
            "method": "At-the-money IV at each expiry's forward, from out-of-the-money quotes; the "
                      "front is the first expiry a week or more out; inverted when it is more than "
                      "5% above the back, upward when more than 5% below."}


def mark_events(rows: List[Dict[str, Any]], event_date: Optional[str],
                after_close: bool = False) -> None:
    """Flag the expiries that are still open when the report comes out. A
    report after the close on an expiry day lands after that expiry ends."""
    if not event_date:
        return
    for r in rows:
        r["contains_event"] = r["expiry"] > event_date or (r["expiry"] == event_date and not after_close)


def event_move(rows: List[Dict[str, Any]], event_date: Optional[str]) -> Dict[str, Any]:
    """The move priced for the report itself, from the term structure.

    Total variance of the first expiry after the report, minus what that same
    span would carry at the IV of the last expiry before it:
    move = sqrt(max(0, IV_after^2 x T_after - IV_before^2 x T_after)). It assumes
    the non-event days are priced at the earlier expiry's IV; when that
    expiry is only days out, weekend and calendar effects move the answer."""
    if not event_date:
        return {"available": False, "reason": "no scheduled report in Optic's data"}
    pts = [r for r in rows if r.get("atm_iv_pct") and r.get("tau_years")]
    after = next((r for r in pts if r.get("contains_event")), None)
    before = [r for r in pts if not r.get("contains_event") and r["dte"] >= 3]
    if not after or not before:
        return {"available": False, "reason": "needs a quoted expiry on each side of the report"}
    b = before[-1]
    ta = after["tau_years"]
    var = (after["atm_iv_pct"] / 100) ** 2 * ta - (b["atm_iv_pct"] / 100) ** 2 * ta
    if var <= 0:
        return {"available": True, "move_pct": 0.0, "after": after["expiry"], "before": b["expiry"],
                "text": "The expiry that spans the report carries no more implied volatility than the "
                        "one before it, so no extra move for the report is priced in on this method."}
    move = float(np.sqrt(var) * 100)
    return {"available": True, "move_pct": _f(move, 2), "after": after["expiry"], "before": b["expiry"],
            "text": "About {:.1f}% priced for the report day itself, from the {} expiry's IV against "
                    "the {} expiry's.".format(move, after["expiry"], b["expiry"]),
            "method": "sqrt(IV_after^2 x T_after - IV_before^2 x T_after): the variance the later "
                      "expiry carries beyond the earlier one's rate. A model reading of what is "
                      "priced, not a forecast of the move."}


def build(chain: pd.DataFrame, spot: float, rate: float, div: float,
          event_date: Optional[str] = None, after_close: bool = False) -> Dict[str, Any]:
    """The surface block for the payload. `chain` must already be resolved."""
    rows = expiry_rows(chain, spot, rate, div)
    mark_events(rows, event_date, after_close)
    states = chain["quote_state"].value_counts().to_dict() if "quote_state" in chain else {}
    sources = chain["iv_source"].value_counts().to_dict() if "iv_source" in chain else {}
    return {
        "available": bool(rows),
        "expiries": rows,
        "iv30": constant_maturity(rows, 30),
        "term": term_read(rows, event_date),
        "event": event_move(rows, event_date),
        "event_date": event_date,
        "quote_states": {k: int(v) for k, v in states.items()},
        "iv_sources": {k: int(v) for k, v in sources.items()},
        "clock": chain.attrs.get("clock"),
        "iv_method": chain.attrs.get("iv_method"),
        "notes": [
            "Expected moves are model readings of what options are priced for, not price limits: "
            "a one-standard-deviation move is exceeded about a third of the time if the model "
            "holds, and the straddle is the cost of the at-the-money call plus put.",
            "Skew here is the 25-delta risk reversal: put IV minus call IV at the strikes whose "
            "deltas are about 0.25, in vol points. Positive means downside protection costs more.",
        ],
    }
