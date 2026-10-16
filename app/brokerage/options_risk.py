"""Option positions as risk: Greeks, net exposure per underlying, expiries, and
what can happen at expiry. Pure: every input is injected, nothing is fetched.

The connection sends each leg's contracts, strike, expiry and the broker's last
price at sync time, and nothing else: no Greeks, no implied vol, no pairing of
legs into strategies. So everything here is derived, and says from what:

* **Implied vol** is solved from the broker's last price against Optic's
  current spot, on a Barone-Adesi-Whaley American price for equity and ETF
  options and Black-Scholes for the European index options (the same split
  `vol_surface.solve_iv` uses for the chain). Greeks are Black-Scholes at that
  vol, the convention the Options tab already follows. Where the price is
  missing, zero, at or below intrinsic, or no vol fits it, the leg says why and
  carries no Greeks: a vol is never invented, because a made-up vol produces a
  confident delta that is wrong by however much the guess was.
* **The two prices are from different times.** The option price is the
  broker's last at sync; the spot is a delayed quote from now. A leg whose two
  times are more than an hour of trading apart is flagged, because a spot that
  has moved since the sync is read by the solve as a change in volatility.
* **Adjusted contracts are excluded.** After a split, special dividend or
  merger the OCC re-roots a series with a digit (TSLA1) and the deliverable
  stops being 100 shares. The connection does not say what it became, so such a
  leg is listed and kept out of every sum rather than counted as 100 shares.
  Mini options also carry a 7 in the root (SPY7) and are recognised as minis,
  not adjustments, when the provider marks them so.

Sign convention, stated in the output as well: contracts are signed (negative
is short) and every scaled Greek carries the position's sign, so positive
delta means the position gains when the underlying rises.
"""

from __future__ import annotations

import math
from datetime import date, datetime, time as dtime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from app import session as market_session
from app.analytics import greeks as greeks_mod
from app.analytics import vol_surface

VERSION = "options-risk-2026-10-15.1"

# Expiry buckets, in calendar days on the New York calendar. The edges follow
# how the risk changes rather than round numbers: inside a week gamma and
# assignment dominate, the next month is the standard monthly cycle, then the
# quarter, then everything longer (LEAPS among it).
BUCKETS: Tuple[Tuple[int, Optional[int], str], ...] = (
    (0, 7, "0-7 days"), (8, 30, "8-30 days"), (31, 90, "31-90 days"), (91, None, "91+ days"))
CONCENTRATION_PCT = 50.0        # share of option premium value in one bucket worth a flag
NEAR_EXPIRY_DAYS = 7            # assignment, auto-exercise and expire-worthless window
FRESHNESS_GAP_MIN = 60.0        # trading minutes between the option price and the spot
STANDARD_MULTIPLIERS = (100.0, 10.0)
GREEK_SUMS = ("delta_shares", "dollar_delta", "gamma_shares_per_dollar", "dollar_gamma_1pct",
              "theta_per_day", "vega_per_vol_point")

# Cash-settled, European-style index roots. vol_surface.INDEX_ROOTS covers the
# underlyings; the weekly and PM-settled series trade under their own roots.
INDEX_OPTION_ROOTS = {"SPX", "SPXW", "NDX", "NDXP", "RUT", "RUTW", "XSP", "VIX", "VIXW"}
# AM-settled standard monthlies settle on the opening print of expiry day, not
# at the 4:00pm close the clock below measures to.
AM_SETTLED_ROOTS = {"SPX", "NDX", "RUT"}
# VIX options are priced off the VIX future for their own expiry, not the spot
# index, and Optic has no VIX futures curve to price them against.
VIX_ROOTS = {"VIX", "^VIX", "VIXW"}

ET = vol_surface.ET

UNITS = {
    "contracts": "Signed count of contracts: negative is a short position.",
    "multiplier": "Shares (or index units) per contract, from the provider where it sent one.",
    "price": "The broker's last price per share at sync time, in the option's currency.",
    "iv": "Annualised implied volatility as a decimal (0.30 is 30%).",
    "days": "Calendar days to expiry on the New York calendar.",
    "per_share.delta": "Change in the option price per 1.00 rise in the underlying, per share.",
    "per_share.gamma": "Change in per-share delta per 1.00 rise in the underlying.",
    "per_share.theta": "Change in the option price per calendar day, per share.",
    "per_share.vega": "Change in the option price per 1 point of implied volatility, per share.",
    "delta_shares": "Share-equivalents: delta x contracts x multiplier. Positive gains when the "
                    "underlying rises.",
    "dollar_delta": "Currency: delta_shares x spot, the stock position with the same first-order "
                    "exposure. A 1% rise changes the value by about 1% of it.",
    "gamma_shares_per_dollar": "Change in delta_shares per 1.00 rise in the underlying: gamma x "
                               "contracts x multiplier.",
    "dollar_gamma_1pct": "Currency: 0.5 x gamma x (0.01 x spot)^2 x contracts x multiplier, the "
                         "profit or loss from gamma alone for a 1% move in either direction.",
    "theta_per_day": "Currency per calendar day: theta x contracts x multiplier, with spot and "
                     "volatility unchanged.",
    "vega_per_vol_point": "Currency per 1 point of implied volatility (30% to 31%): vega x "
                          "contracts x multiplier.",
    "notional": "Currency: |contracts| x multiplier x spot, the value of the shares the contracts "
                "control.",
    "premium_value": "Currency: broker's last price x contracts x multiplier; negative for a short.",
    "moneyness": "Spot divided by strike.",
    "moneyness_pct": "100 x (spot - strike) / strike.",
    "intrinsic": "Per share, at the current spot: max(spot - strike, 0) for a call, "
                 "max(strike - spot, 0) for a put.",
    "extrinsic": "Per share: the broker's price minus intrinsic at the current spot.",
}

SIGN_CONVENTION = (
    "Contracts are signed: negative is a short position, and every scaled Greek carries the "
    "position's sign. Positive delta means the position gains when the underlying rises. Negative "
    "theta means it loses value each day with nothing else changing. Positive vega means it gains "
    "when implied volatility rises. A short leg's Greeks are the long leg's with the sign flipped.")


# ----------------------------------------------------------------- helpers

def _num(v: Any) -> Optional[float]:
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _r(v: Optional[float], n: int = 2) -> Optional[float]:
    return None if v is None else round(float(v), n)


def _when(v: Any) -> Optional[datetime]:
    """An aware datetime from an ISO string or datetime; naive is read as UTC."""
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        d = v
    elif isinstance(v, date):
        d = datetime.combine(v, dtime(16, 0), tzinfo=ET)
    else:
        s = str(v).strip().replace("Z", "+00:00")
        try:
            d = datetime.fromisoformat(s)
        except ValueError:
            try:
                d = datetime.combine(date.fromisoformat(s[:10]), dtime(16, 0), tzinfo=ET)
            except ValueError:
                return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _iso(d: Optional[datetime]) -> Optional[str]:
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if d else None


def _call(fn: Optional[Callable], arg: Any) -> Any:
    if fn is None:
        return None
    try:
        return fn(arg)
    except Exception:                                            # noqa: BLE001
        return None


def occ_root(occ: Optional[str]) -> Optional[str]:
    """The OCC root: everything before the fixed 15-character tail
    (YYMMDD + C/P + strike x 1000 in 8 digits). Works with and without the
    space padding to six characters."""
    s = str(occ or "").strip().upper()
    if len(s) <= 15:
        return None
    tail = s[-15:]
    if not (tail[:6].isdigit() and tail[6] in "CP" and tail[7:].isdigit()):
        return None
    return s[:-15].strip() or None


def trading_minutes_between(a: datetime, b: datetime) -> float:
    """Regular-session minutes between two instants, on the NYSE calendar
    (holidays and half days from app/session.py). A sync at 3:30pm and a spot
    at 10:00am the next day are 60 trading minutes apart, which is the gap that
    matters for a price: the market was moving for an hour in between."""
    if a > b:
        a, b = b, a
    a_et, b_et = a.astimezone(ET), b.astimezone(ET)
    total = 0.0
    day = a_et.date()
    # Bounded: past a year the answer is "far more than an hour" either way.
    for _ in range(400):
        if day > b_et.date():
            break
        close = market_session.regular_close(day)
        if close is not None:
            opened = datetime.combine(day, dtime(9, 30), tzinfo=ET)
            lo, hi = max(opened, a_et), min(close, b_et)
            if hi > lo:
                total += (hi - lo).total_seconds() / 60.0
        day += timedelta(days=1)
    return total


def _in_regular_session(now: datetime) -> bool:
    t = now.astimezone(ET)
    close = market_session.regular_close(t.date())
    return close is not None and datetime.combine(t.date(), dtime(9, 30), tzinfo=ET) <= t < close


def _days_to(expiry: str, now: datetime) -> Optional[int]:
    try:
        return (date.fromisoformat(str(expiry)[:10]) - now.astimezone(ET).date()).days
    except ValueError:
        return None


def _style(underlying: str, root: Optional[str]) -> Dict[str, Any]:
    u = underlying.upper().lstrip("^")
    r = (root or "").upper()
    index = (not vol_surface.is_american(underlying)) or r in INDEX_OPTION_ROOTS \
        or u in {x.lstrip("^") for x in vol_surface.INDEX_ROOTS}
    return {"index": index, "american": not index,
            "settlement": "cash" if index else "physical",
            "am_settled": index and (r or u) in AM_SETTLED_ROOTS,
            "vix": u in {x.lstrip("^") for x in VIX_ROOTS} or r in VIX_ROOTS}


def _check_multiplier(o: Dict[str, Any], root: Optional[str]) -> Dict[str, Any]:
    """The multiplier used, whether it was assumed, and whether this is an
    adjusted (non-standard deliverable) contract to keep out of the sums."""
    given = _num(o.get("multiplier"))
    assumed = bool(o.get("multiplier_assumed")) or given is None or given <= 0
    mini = bool(o.get("mini")) or given == 10.0
    mult = given if given and given > 0 else (10.0 if mini else 100.0)
    notes: List[str] = []
    adjusted, why = False, None
    if root and any(ch.isdigit() for ch in root):
        if mini and root.endswith("7") and mult == 10.0:
            notes.append("A mini option (root {}): 10 shares a contract.".format(root))
        else:
            adjusted = True
            why = ("The OCC root {} carries a digit, which marks an adjusted contract (after a split, "
                   "special dividend or merger). Its deliverable is no longer a standard {} shares and "
                   "the connection does not say what it became, so it is left out of every total."
                   .format(root, int(mult)))
    if not adjusted and given is not None and given > 0 and given not in STANDARD_MULTIPLIERS:
        adjusted = True
        why = ("The provider reports a multiplier of {:g}, which is not a standard 100 or 10 share "
               "contract, so the deliverable is non-standard and the leg is left out of every total."
               .format(given))
    if assumed:
        notes.append("The provider sent no multiplier, so {:g} is assumed ({}).".format(
            mult, "a mini option" if mini else "a standard contract"))
    if o.get("mini") and given is not None and given != 10.0:
        notes.append("Marked as a mini but the provider's multiplier is {:g}; the provider's multiplier "
                     "is used.".format(given))
    return {"multiplier": mult, "assumed": assumed, "mini": mini, "adjusted": adjusted,
            "adjusted_reason": why, "notes": notes}


def _dividend(div: Optional[Dict[str, Any]], spot: Optional[float]) -> Dict[str, Any]:
    div = div or {}
    y = _num(div.get("yield"))
    amount = None
    amount_basis = None
    for k in ("amount", "next_amount", "last_amount"):
        a = _num(div.get(k))
        if a is not None and a > 0:
            amount, amount_basis = a, ("the last dividend paid" if k == "last_amount" else "the stated amount")
            break
    if amount is None and y and spot:
        # A quarter of the annual yield: most US dividend payers pay
        # quarterly. Said wherever it is used, because a monthly or annual
        # payer would make it wrong by a factor of three or four.
        amount, amount_basis = y * spot / 4.0, "estimated as a quarter of the annual yield"
    return {"yield": y if y is not None else 0.0, "yield_known": y is not None,
            "next_ex_date": str(div.get("next_ex_date"))[:10] if div.get("next_ex_date") else None,
            "amount": amount, "amount_basis": amount_basis}


def _why_no_iv(price: float, spot: float, strike: float, tau: float, r: float, q: float,
               is_call: bool, american: bool) -> str:
    intrinsic = max(spot - strike, 0.0) if is_call else max(strike - spot, 0.0)
    if price < intrinsic - 0.005:
        return ("The broker's price ({:.2f}) is below intrinsic value at the current spot ({:.2f}), which "
                "usually means the option price and the spot are from different times. No volatility "
                "fits it.".format(price, intrinsic))
    if american and price <= intrinsic + 1e-9:
        return ("The broker's price is at intrinsic value at the current spot, so there is no time value "
                "to solve a volatility from.")
    dq, dr = math.exp(-q * tau), math.exp(-r * tau)
    lower = max((spot * dq - strike * dr) if is_call else (strike * dr - spot * dq), 0.0)
    upper = spot * dq if is_call else strike * dr
    if price <= lower + 1e-9:
        return ("The broker's price is at or below the lowest value a European option can have at the "
                "current spot, so there is no time value to solve a volatility from.")
    if price >= upper - 1e-9:
        return ("The broker's price is above the most this option can be worth at the current spot. No "
                "volatility produces it.")
    return "No volatility between 0.1% and 500% reproduces the broker's price."


# --------------------------------------------------------------- one leg

def _leg(o: Dict[str, Any], spot_q: Optional[Dict[str, Any]], r: float,
         div: Optional[Dict[str, Any]], now: datetime) -> Dict[str, Any]:
    underlying = str(o.get("underlying") or "").upper()
    root = occ_root(o.get("occ"))
    style = _style(underlying, root)
    mult = _check_multiplier(o, root)
    n = _num(o.get("contracts"))
    strike = _num(o.get("strike"))
    price = _num(o.get("price"))
    otype = str(o.get("option_type") or "").lower()
    is_call = otype == "call"
    expiry = str(o.get("expiry") or "")[:10] or None
    days = _days_to(expiry, now) if expiry else None
    spot = _num((spot_q or {}).get("price"))
    if spot is not None and spot <= 0:
        spot = None
    price_as_of = None
    for k in ("price_as_of", "broker_as_of", "last_sync_at", "synced_at"):
        price_as_of = _when(o.get(k))
        if price_as_of:
            break
    m = mult["multiplier"]
    d = _dividend(div, spot)

    out: Dict[str, Any] = {
        "underlying": underlying, "occ": o.get("occ"), "root": root, "option_type": otype or None,
        "strike": strike, "expiry": expiry, "days": days,
        "contracts": n, "side": None if n is None else ("short" if n < 0 else "long"),
        "multiplier": m, "multiplier_assumed": mult["assumed"], "mini": mult["mini"],
        "adjusted": mult["adjusted"], "adjusted_reason": mult["adjusted_reason"],
        "notes": list(mult["notes"]),
        "exercise": "american" if style["american"] else "european",
        "settlement": style["settlement"], "am_settled": style["am_settled"],
        "currency": (o.get("currency") or "USD").upper(), "account": o.get("account"),
        "price": price, "price_as_of": _iso(price_as_of),
        "spot": spot, "spot_as_of": (spot_q or {}).get("as_of"),
        "intrinsic": None, "extrinsic": None, "moneyness": None, "moneyness_pct": None, "itm": None,
        "premium_value": _r(price * n * m) if price is not None and n is not None else None,
        "notional": None,
        "iv": None, "iv_model": None, "greeks_available": False, "greeks_reason": None,
        "per_share": None,
        "delta_shares": None, "dollar_delta": None, "gamma_shares_per_dollar": None,
        "dollar_gamma_1pct": None, "theta_per_day": None, "vega_per_vol_point": None,
        "dividend_yield": d["yield"], "dividend_yield_known": d["yield_known"],
        "in_aggregates": not mult["adjusted"],
        "_div": d,
        # Unrounded figures for the sums, so a total is not the sum of
        # rounded parts: rounding each leg to cents first moved an SPX
        # put's net dollar delta 15.19 away from its own option figure.
        "_raw": {"premium_value": price * n * m if price is not None and n is not None else None,
                 "notional": None},
    }
    if out["adjusted"]:
        out["greeks_reason"] = mult["adjusted_reason"]
        return out

    def no(reason: str) -> Dict[str, Any]:
        out["greeks_reason"] = reason
        return out

    if otype not in ("call", "put"):
        return no("The option type is missing, so it cannot be priced.")
    if strike is None or strike <= 0 or not expiry or days is None:
        return no("The strike or expiry is missing, so it cannot be priced.")
    if n is None or n == 0:
        return no("No contract count from the broker.")
    if spot is not None:
        intrinsic = max(spot - strike, 0.0) if is_call else max(strike - spot, 0.0)
        out.update(intrinsic=_r(intrinsic, 4), moneyness=_r(spot / strike, 4),
                   moneyness_pct=_r(100.0 * (spot - strike) / strike, 2),
                   itm=(spot > strike) if is_call else (spot < strike),
                   notional=_r(abs(n) * m * spot))
        out["_raw"]["notional"] = abs(n) * m * spot
        if price is not None:
            out["extrinsic"] = _r(price - intrinsic, 4)
    if days < 0 or now.astimezone(ET) >= vol_surface.expiry_close(expiry):
        return no("Expired at the {} close; the broker still lists it, probably pending exercise, "
                  "assignment or removal.".format(expiry))
    if style["vix"]:
        return no("VIX options are priced off the VIX future for their expiry, not the spot index, and "
                  "Optic has no VIX futures curve, so no Greeks are computed.")
    if spot is None:
        return no("No current quote for {}, so nothing that depends on the spot is shown.".format(underlying))
    if price is None:
        return no("The broker sent no price for this option, so no volatility can be solved.")
    if price <= 0:
        return no("The broker's price is zero, so no volatility can be solved.")

    tau = vol_surface.expiry_tau(expiry, now)
    q = d["yield"]
    iv = float(vol_surface.solve_iv(np.array([price]), float(spot), np.array([strike]), np.array([tau]),
                                    r, q, np.array([is_call]), american=style["american"])[0])
    if not math.isfinite(iv):
        return no(_why_no_iv(price, spot, strike, tau, r, q, is_call, style["american"]))
    g = greeks_mod.greeks(float(spot), np.array([strike]), np.array([tau]), np.array([iv]), r, q,
                          np.array([is_call]))
    delta, gamma = float(g["delta"][0]), float(g["gamma"][0])
    theta, vega = float(g["theta"][0]), float(g["vega"][0])
    scale = n * m
    out.update(
        iv=round(iv, 4),
        iv_model=("Barone-Adesi-Whaley American price where early exercise is worth something, "
                  "Black-Scholes otherwise; Greeks are Black-Scholes at that vol")
        if style["american"] else "Black-Scholes (European exercise)",
        greeks_available=True, tau_years=round(tau, 6),
        per_share={"delta": round(delta, 4), "gamma": round(gamma, 6),
                   "theta": round(theta, 4), "vega": round(vega, 4)},
    )
    raw = out["_raw"]
    raw.update(delta_shares=delta * scale, dollar_delta=delta * scale * spot,
               gamma_shares_per_dollar=gamma * scale,
               dollar_gamma_1pct=0.5 * gamma * (0.01 * spot) ** 2 * scale,
               theta_per_day=theta * scale, vega_per_vol_point=vega * scale)
    for k in GREEK_SUMS:
        out[k] = _r(raw[k], 4 if k == "gamma_shares_per_dollar" else 2)
    return out


# --------------------------------------------------------------- the book

def _bucket(days: Optional[int]) -> Optional[str]:
    if days is None or days < 0:
        return None
    for lo, hi, label in BUCKETS:
        if days >= lo and (hi is None or days <= hi):
            return label
    return None


def _add(acc: Dict[str, Any], key: str, v: Optional[float]) -> None:
    if v is not None:
        acc[key] = (acc.get(key) or 0.0) + v


def _contract_label(p: Dict[str, Any]) -> str:
    n = p.get("contracts") or 0
    return "{} {:g} {} {:g} {}{} expiring {}".format(
        "Short" if n < 0 else "Long", abs(n), p.get("underlying") or "", p.get("strike") or 0,
        p.get("option_type") or "option", "" if abs(n) == 1 else "s", p.get("expiry") or "unknown")


def build(options: List[Dict[str, Any]], stock_shares: Dict[str, float],
          spot_of: Callable[[str], Optional[Dict[str, Any]]], rate: Optional[Dict[str, Any]],
          div_of: Callable[[str], Optional[Dict[str, Any]]], now: datetime) -> Dict[str, Any]:
    """Greeks, exposure and expiry risk for `portfolio.build()["options"]`.

    Each option may carry `price_as_of` (the account's broker_as_of, else its
    last_sync_at), which the caller adds: it is the time the broker's last
    price belongs to, and without it the freshness check says it is unknown.
    `stock_shares` is shares held directly per underlying, for net delta.
    """
    now = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    options = [o for o in (options or []) if o]
    stock_shares = {str(k).upper(): float(v) for k, v in (stock_shares or {}).items() if _num(v) is not None}
    rate = rate or {}
    r = _num(rate.get("rate"))
    rate_known = r is not None
    r = r if r is not None else 0.0
    base = {"version": VERSION, "as_of": _iso(now), "units": UNITS, "sign_convention": SIGN_CONVENTION,
            "rate": {"rate": r, "source": rate.get("source") or ("unknown" if not rate_known else None),
                     "as_of": rate.get("as_of")}}
    if not options:
        return dict(base, available=False, reason="No option positions in the accounts counted.",
                    positions=[], by_underlying=[], totals_by_currency={}, expiry_buckets=[],
                    considerations=[], freshness={"underlyings": [], "statement": None},
                    excluded=[], limitations=[], method="")

    underlyings = sorted({str(o.get("underlying") or "").upper() for o in options if o.get("underlying")})
    spots = {u: _call(spot_of, u) for u in underlyings}
    divs = {u: _call(div_of, u) for u in underlyings}
    legs = [_leg(o, spots.get(str(o.get("underlying") or "").upper()), r,
                 divs.get(str(o.get("underlying") or "").upper()), now) for o in options]

    # ---------------------------------------------------- per underlying
    groups: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for p in legs:
        if not p["in_aggregates"] or not p["underlying"]:
            continue
        raw = p["_raw"]
        g = groups.setdefault((p["underlying"], p["currency"]), {
            "spot": p["spot"], "spot_as_of": p["spot_as_of"], "legs": 0, "contracts_long": 0.0,
            "contracts_short": 0.0, "legs_without_greeks": [], "with_greeks": 0, "sums": {}, "expiries": {}})
        g["legs"] += 1
        if (p["contracts"] or 0) > 0:
            g["contracts_long"] += p["contracts"]
        elif (p["contracts"] or 0) < 0:
            g["contracts_short"] += -p["contracts"]
        _add(g["sums"], "premium_value", raw["premium_value"])
        _add(g["sums"], "notional", raw["notional"])
        e = g["expiries"].setdefault(p["expiry"], {"expiry": p["expiry"], "days": p["days"], "legs": 0,
                                                   "legs_without_greeks": 0, "sums": {}})
        e["legs"] += 1
        _add(e["sums"], "premium_value", raw["premium_value"])
        if not p["greeks_available"]:
            g["legs_without_greeks"].append({"occ": p["occ"], "label": _contract_label(p),
                                             "reason": p["greeks_reason"]})
            e["legs_without_greeks"] += 1
            continue
        g["with_greeks"] += 1
        for k in GREEK_SUMS:
            _add(g["sums"], k, raw[k])
            _add(e["sums"], k, raw[k])

    def greek_figures(sums: Dict[str, float], any_greeks: bool) -> Dict[str, Optional[float]]:
        # None rather than 0 when no leg had Greeks: a zero would read as "no
        # exposure", which is the one thing nobody can say about a leg Optic
        # could not price.
        return {k: (_r(sums.get(k, 0.0), 4 if k == "gamma_shares_per_dollar" else 2) if any_greeks else None)
                for k in GREEK_SUMS}

    by_underlying: List[Dict[str, Any]] = []
    totals: Dict[str, Dict[str, Any]] = {}
    for (u, ccy), g in sorted(groups.items()):
        shares = stock_shares.get(u, 0.0)
        spot = g["spot"]
        complete = not g["legs_without_greeks"]
        figs = greek_figures(g["sums"], g["with_greeks"] > 0)
        opt_shares = g["sums"].get("delta_shares", 0.0)
        net = shares + opt_shares
        missing = len(g["legs_without_greeks"])
        row = {
            "underlying": u, "currency": ccy, "spot": spot, "spot_as_of": g["spot_as_of"],
            "stock_shares": _r(shares, 4),
            "stock_dollar_delta": _r(shares * spot) if spot is not None else None,
            "option_delta_shares": figs["delta_shares"],
            "option_dollar_delta": figs["dollar_delta"],
            # The headline is withheld when a leg is missing: a deep in-the-money
            # leg the solve could not price carries close to its full share
            # count, so a net figure without it can have the wrong sign.
            "net_delta_shares": _r(net) if complete else None,
            "net_dollar_delta": _r(net * spot) if complete and spot is not None else None,
            "partial": None if complete else {
                "net_delta_shares": _r(net) if g["with_greeks"] else None,
                "net_dollar_delta": _r(net * spot) if spot is not None and g["with_greeks"] else None,
                "legs_left_out": missing,
                "note": "Only the legs with Greeks. The {} left out can change this a great deal, so it is not "
                        "the net exposure.".format("leg" if missing == 1 else "{} legs".format(missing))},
            "gamma_shares_per_dollar": figs["gamma_shares_per_dollar"],
            "dollar_gamma_1pct": figs["dollar_gamma_1pct"],
            "theta_per_day": figs["theta_per_day"],
            "vega_per_vol_point": figs["vega_per_vol_point"],
            "premium_value": _r(g["sums"].get("premium_value")),
            "notional": _r(g["sums"].get("notional")),
            "legs": g["legs"], "contracts_long": _r(g["contracts_long"], 4),
            "contracts_short": _r(g["contracts_short"], 4),
            "complete": complete, "legs_without_greeks": g["legs_without_greeks"],
            "expiries": [dict({k: v for k, v in e.items() if k != "sums"},
                              premium_value=_r(e["sums"].get("premium_value")),
                              complete=e["legs_without_greeks"] == 0,
                              **{k: v for k, v in greek_figures(e["sums"], e["legs"] > e["legs_without_greeks"])
                                 .items() if k != "gamma_shares_per_dollar"})
                         for _, e in sorted(g["expiries"].items(), key=lambda kv: kv[0] or "")],
            "note": ("Net delta is the shares held directly plus the option legs' share-equivalents. Legs are "
                     "summed one by one; Optic does not pair them into strategies.")
            + ("" if complete else " {} leg{} without Greeks {} left out of the option figures, so they are "
               "incomplete and the net is withheld.".format(missing, "" if missing == 1 else "s",
                                                             "is" if missing == 1 else "are")),
        }
        by_underlying.append(row)
        t = totals.setdefault(ccy, {"sums": {}, "underlyings": 0, "complete": True, "net": 0.0})
        t["underlyings"] += 1
        t["complete"] = t["complete"] and complete and spot is not None
        if spot is not None:
            t["net"] += net * spot
        for k in ("dollar_delta", "dollar_gamma_1pct", "theta_per_day", "vega_per_vol_point"):
            if g["with_greeks"]:
                _add(t["sums"], k, g["sums"].get(k, 0.0))
        for k in ("premium_value", "notional"):
            _add(t["sums"], k, g["sums"].get(k))
    by_underlying.sort(key=lambda x: -abs(x["net_dollar_delta"] if x["net_dollar_delta"] is not None
                                          else (x["option_dollar_delta"] or 0.0)))
    totals_out = {}
    for c, t in totals.items():
        totals_out[c] = {
            "net_dollar_delta": _r(t["net"]) if t["complete"] else None,
            "option_dollar_delta": _r(t["sums"].get("dollar_delta")),
            "dollar_gamma_1pct": _r(t["sums"].get("dollar_gamma_1pct")),
            "theta_per_day": _r(t["sums"].get("theta_per_day")),
            "vega_per_vol_point": _r(t["sums"].get("vega_per_vol_point")),
            "premium_value": _r(t["sums"].get("premium_value")),
            "notional": _r(t["sums"].get("notional")),
            "underlyings": t["underlyings"], "complete": t["complete"],
            "note": "Summed across underlyings in {} only, over the legs with Greeks. A summed dollar delta is "
                    "the change for a 1% move in every underlying at once, which they do not do.{}".format(
                        c, "" if t["complete"] else " Some legs or quotes are missing, so the net is withheld."),
        }

    # ---------------------------------------------------- expiry buckets
    expiry_buckets: List[Dict[str, Any]] = []
    for ccy in sorted({p["currency"] for p in legs if p["in_aggregates"]}):
        rows = {label: {"label": label, "min_days": lo, "max_days": hi, "legs": 0, "legs_without_greeks": 0,
                        "abs_dollar_delta": 0.0, "premium_value": 0.0} for lo, hi, label in BUCKETS}
        for p in legs:
            if not p["in_aggregates"] or p["currency"] != ccy:
                continue
            b = _bucket(p["days"])
            if b is None:
                continue
            rows[b]["legs"] += 1
            if p["greeks_available"]:
                rows[b]["abs_dollar_delta"] += abs(p["_raw"]["dollar_delta"])
            else:
                rows[b]["legs_without_greeks"] += 1
            if p["_raw"]["premium_value"] is not None:
                rows[b]["premium_value"] += abs(p["_raw"]["premium_value"])
        tot_dd = sum(x["abs_dollar_delta"] for x in rows.values())
        tot_pv = sum(x["premium_value"] for x in rows.values())
        out_rows = [dict(x, abs_dollar_delta=_r(x["abs_dollar_delta"]), premium_value=_r(x["premium_value"]),
                         abs_dollar_delta_pct=_r(100.0 * x["abs_dollar_delta"] / tot_dd) if tot_dd else None,
                         premium_pct=_r(100.0 * x["premium_value"] / tot_pv) if tot_pv else None)
                    for x in rows.values()]
        top = max(out_rows, key=lambda x: x["premium_pct"] or 0.0)
        concentrated = bool(top["premium_pct"] is not None and top["premium_pct"] > CONCENTRATION_PCT)
        expiry_buckets.append({
            "currency": ccy, "buckets": out_rows,
            "concentrated_in": top["label"] if concentrated else None,
            "flag": ("{:.1f}% of option premium value expires in the {} bucket.".format(top["premium_pct"],
                                                                                       top["label"])
                     if concentrated else None),
            "basis": "Premium value is |broker's last price x contracts x multiplier|, longs and shorts "
                     "alike. Dollar delta is |delta x contracts x multiplier x spot|, for legs with Greeks "
                     "only. Concentration is flagged above {:.0f}% of premium value in one bucket."
                     .format(CONCENTRATION_PCT),
        })

    # ---------------------------------------------------- considerations
    considerations: List[Dict[str, Any]] = []
    today = now.astimezone(ET).date()
    seen_settlement = set()
    for p in legs:
        u, n, days = p["underlying"], p["contracts"] or 0, p["days"]
        label = _contract_label(p)
        if p["adjusted"]:
            considerations.append({"kind": "adjusted_contract", "underlying": u, "occ": p["occ"], "days": days,
                                   "severity": "info", "text": "{}: {}".format(label, p["adjusted_reason"])})
            continue
        if u and (u, p["settlement"]) not in seen_settlement:
            seen_settlement.add((u, p["settlement"]))
            if p["settlement"] == "cash":
                text = ("{} options are cash-settled and European-style: they cannot be exercised or assigned "
                        "before expiry, and an in-the-money contract settles in cash for the in-the-money "
                        "amount.".format(u))
                if p["am_settled"]:
                    text += (" Standard monthly {} options settle on the opening print of expiry day, not the "
                             "close.".format(u))
            else:
                text = ("{} options are physically settled: exercise or assignment delivers {:g} shares a "
                        "contract, and American-style contracts can be assigned on any day before expiry."
                        .format(u, p["multiplier"]))
            considerations.append({"kind": "settlement", "underlying": u, "occ": None, "days": None,
                                   "severity": "info", "settlement": p["settlement"], "text": text})
        if days is None:
            continue
        if days < 0 or p["greeks_reason"] and p["greeks_reason"].startswith("Expired"):
            considerations.append({"kind": "expired", "underlying": u, "occ": p["occ"], "days": days,
                                   "severity": "medium",
                                   "text": "{}: expired, but the broker still lists it. Check the account for "
                                           "the exercise, assignment or removal.".format(label)})
            continue
        if days == 0:
            considerations.append({"kind": "expires_today", "underlying": u, "occ": p["occ"], "days": 0,
                                   "severity": "high",
                                   "text": "{}: expires today (0DTE), at the {}. Value and delta can swing "
                                           "hard in the last hours.".format(
                                               label, "opening settlement print" if p["am_settled"]
                                               else "4:00pm ET close")})
        near = days <= NEAR_EXPIRY_DAYS
        if near and n < 0 and p["itm"]:
            if p["settlement"] == "cash":
                text = ("{}: short and in the money by {:.2f} a share at the last spot, {} day{} to expiry. "
                        "It settles in cash at expiry for the in-the-money amount; European-style, so it "
                        "is not assigned early.".format(label, p["intrinsic"] or 0.0, days, "" if days == 1 else "s"))
            else:
                text = ("{}: short and in the money by {:.2f} a share at the last spot, {} day{} to expiry. "
                        "In-the-money short options near expiry are often assigned, which would {} {:g} "
                        "shares.".format(label, p["intrinsic"] or 0.0, days, "" if days == 1 else "s",
                                         "deliver" if p["option_type"] == "call" else "buy",
                                         abs(n) * p["multiplier"]))
            considerations.append({"kind": "assignment_risk", "underlying": u, "occ": p["occ"], "days": days,
                                   "severity": "high", "text": text})
        if near and n > 0 and p["itm"] is False:
            considerations.append({
                "kind": "may_expire_worthless", "underlying": u, "occ": p["occ"], "days": days,
                "severity": "medium",
                "text": "{}: out of the money at the last spot. If {} stays {} {:g} through expiry it expires "
                        "worthless{}.".format(label, u, "below" if p["option_type"] == "call" else "above",
                                              p["strike"] or 0,
                                              ", and the {} {:.2f} of premium at the broker's last price goes "
                                              "with it".format(p["currency"], abs(p["premium_value"]))
                                              if p["premium_value"] else "")})
        if near and n > 0 and p["itm"] and p["settlement"] == "physical":
            considerations.append({
                "kind": "auto_exercise", "underlying": u, "occ": p["occ"], "days": days, "severity": "medium",
                "text": "{}: in the money at the last spot. The OCC exercises an option $0.01 or more in the "
                        "money at expiry unless the broker is told otherwise, which would {} {:g} shares at "
                        "the strike, about {:.2f} in {}.".format(
                            label, "buy" if p["option_type"] == "call" else "sell", abs(n) * p["multiplier"],
                            abs(n) * p["multiplier"] * (p["strike"] or 0.0), p["currency"])})
        d = p["_div"]
        if (n < 0 and p["option_type"] == "call" and p["exercise"] == "american" and d["next_ex_date"]
                and p["itm"] and p["extrinsic"] is not None and d["amount"] is not None):
            try:
                ex = date.fromisoformat(d["next_ex_date"])
            except ValueError:
                ex = None
            if ex and p["expiry"] and today <= ex <= date.fromisoformat(p["expiry"]) \
                    and p["extrinsic"] < d["amount"]:
                considerations.append({
                    "kind": "early_assignment_dividend", "underlying": u, "occ": p["occ"], "days": days,
                    "severity": "high",
                    "text": "{}: {} goes ex-dividend on {}, before expiry, and the call's time value ({:.2f} a "
                            "share) is below the dividend ({:.2f}, {}). Holders of in-the-money calls often "
                            "exercise the day before the ex-date to collect it, so early assignment is "
                            "likely.".format(label, u, d["next_ex_date"], p["extrinsic"], d["amount"],
                                             d["amount_basis"])})
    order = {"high": 0, "medium": 1, "info": 2}
    considerations.sort(key=lambda c: (order.get(c["severity"], 3), c["days"] if c["days"] is not None else 9999))

    # ---------------------------------------------------- freshness
    in_session = _in_regular_session(now)
    fresh_rows = []
    any_gap = False
    for u in underlyings:
        q = spots.get(u) or {}
        spot_at = _when(q.get("as_of"))
        ulegs = [p for p in legs if p["underlying"] == u]
        price_times = sorted({p["price_as_of"] for p in ulegs if p["price_as_of"]})
        oldest = _when(price_times[0]) if price_times else None
        gap = trading_minutes_between(oldest, spot_at) if oldest and spot_at else None
        flagged = gap is not None and gap > FRESHNESS_GAP_MIN
        any_gap = any_gap or flagged
        earlier_session = bool(oldest and spot_at and in_session
                               and oldest.astimezone(ET).date() < spot_at.astimezone(ET).date())
        if not q or _num(q.get("price")) is None:
            note = "No current quote for {}: spot-dependent figures are not shown.".format(u)
        elif flagged:
            note = ("The broker's option price is {:.0f} trading minutes older than the spot. The solve reads "
                    "any move in between as a change in volatility, so these Greeks are approximate."
                    .format(gap))
        elif oldest is None:
            note = "The time of the broker's option price is not known, so its gap to the spot cannot be checked."
        else:
            note = "The option price and the spot are within an hour of trading of each other."
        if earlier_session and not flagged and q:
            note += " The option price is from an earlier session than the spot."
        fresh_rows.append({
            "underlying": u, "spot": _num(q.get("price")), "spot_as_of": q.get("as_of"),
            "spot_source": q.get("source"), "spot_delayed_minutes": q.get("delayed_minutes"),
            "option_price_as_of": price_times[0] if price_times else None,
            "trading_minutes_apart": _r(gap, 0), "flagged": flagged, "earlier_session": earlier_session,
            "note": note})
    freshness = {
        "underlyings": fresh_rows,
        "market_open": in_session,
        "any_flagged": any_gap,
        "statement": ("Greeks combine the broker's last option price, from the time of the account's sync, with "
                      "a newer delayed spot. Where the two are more than {:.0f} trading minutes apart the leg is "
                      "flagged.".format(FRESHNESS_GAP_MIN)),
        "rate": {"rate": r, "source": rate.get("source"), "as_of": rate.get("as_of")},
    }

    # ---------------------------------------------------- the rest
    excluded = [{"underlying": p["underlying"], "occ": p["occ"], "label": _contract_label(p),
                 "reason": p["adjusted_reason"]} for p in legs if p["adjusted"]]
    with_greeks = sum(1 for p in legs if p["greeks_available"])
    limitations = [
        "Greeks are model values: Black-Scholes at a volatility solved from the broker's last price, not "
        "quotes. The last price is not a bid-ask mid, and on a thinly traded contract it can be hours or "
        "days old, which moves the solved volatility and every Greek with it.",
        "One short interest rate is used for every expiry, and dividends enter as a continuous yield, so a "
        "single ex-date is smoothed across the contract's life.",
        "Multi-leg strategies arrive as separate legs. They are summed per underlying and per expiry and are "
        "not paired, so a spread's legs are shown as two positions.",
        "The spot is assumed to be quoted in the option's currency.",
        "Assignment and exercise considerations describe conditions at the last spot. They are not "
        "predictions: whether a holder exercises is their decision.",
    ]
    if not rate_known or rate.get("source") == "unavailable":
        limitations.append("No interest rate was available, so 0% is used. Calls then price slightly rich to "
                           "puts and the solved volatilities shift a little.")
    no_yield = sorted({p["underlying"] for p in legs if not p["dividend_yield_known"] and p["exercise"] == "american"})
    if no_yield:
        limitations.append("No dividend yield was available for {}, so 0% is assumed there.".format(
            ", ".join(no_yield[:8])))
    if any(p["am_settled"] for p in legs):
        limitations.append("AM-settled index options settle on the opening print, but time to expiry is "
                           "measured to the 4:00pm close, so the last day's time value is overstated.")
    if excluded:
        limitations.append("{} adjusted contract{} {} left out of every total.".format(
            len(excluded), "" if len(excluded) == 1 else "s", "is" if len(excluded) == 1 else "are"))
    if any(p["multiplier_assumed"] for p in legs):
        limitations.append("Some multipliers were assumed (100, or 10 for a mini) because the provider sent "
                           "none.")
    positions = [{k: v for k, v in p.items() if not k.startswith("_")} for p in legs]
    positions.sort(key=lambda p: (p["underlying"], p["expiry"] or "", p["strike"] or 0.0))
    return dict(
        base, available=True,
        positions=positions,
        by_underlying=by_underlying,
        totals_by_currency=totals_out,
        expiry_buckets=expiry_buckets,
        considerations=considerations,
        freshness=freshness,
        excluded=excluded,
        coverage={"legs": len(legs), "with_greeks": with_greeks, "adjusted": len(excluded),
                  "without_greeks": len(legs) - with_greeks - len(excluded)},
        method=("Implied volatility is solved from the broker's last price per share against the current "
                "spot, on an American (Barone-Adesi-Whaley) price for equity and ETF options where early "
                "exercise is worth something and Black-Scholes for European index options. Time to expiry runs "
                "to 4:00pm ET on the expiry date. Greeks are Black-Scholes at that volatility, then scaled by "
                "contracts x multiplier: delta_shares = delta x contracts x multiplier; dollar_delta = "
                "delta_shares x spot; dollar_gamma_1pct = 0.5 x gamma x (0.01 x spot)^2 x contracts x "
                "multiplier; theta per calendar day; vega per volatility point. Sums are per underlying and "
                "currency, never across currencies."),
        limitations=limitations,
    )
