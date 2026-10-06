"""Which option quotes a contract may be chosen from, and why the rest were not.

One screen, shared by everything that picks a contract: the ranked strikes on
the Options tab (entry.py), the single call or put and the strategies
(swing.py), and the contract list under a swing setup (setups.py). It used to be
three different rules, and the ranked one relaxed itself: when fewer than four
contracts passed its liquidity test it ranked the whole side of the chain
instead, so a thin chain was quietly answered with the contracts the test had
just excluded.

**A quote is usable** when it has a bid and an ask, both finite and above zero,
and the ask is not below the bid. A crossed or one-sided market has no price
anybody can expect to trade at. The midpoint and the spread are computed from
that bid and ask here, rather than taken from the provider: the chain builders
fall back to the last trade price for the midpoint when a side is missing,
which is a price from whenever that trade was, not a market.

**Liquid** means some trading interest and a tight enough market: open
interest or today's volume at a floor, and a spread no wider than a share of
the midpoint. Neither says a reader's order will fill. Open interest counts
contracts still open after the last session; volume counts today's trades so
far; the spread is the quote at the moment the chain was read. The midpoint is
an estimate of a fair price between them, not a price anybody has offered.

**Adjusted contracts are left out.** After a split, merger or special dividend
a contract can deliver something other than 100 shares, and its symbol's root
then differs from the ticker's (TSLA1, not TSLA). Every cost and every exposure
in this app multiplies by the contract's size, so one whose size is unknown
cannot be priced honestly; where the provider states a size (Tradier's
contract_size) it is used, and where it does not, an adjusted contract is
excluded and counted.

**Quote age** is checked only where the provider dates its quotes. Tradier's
bid_date and ask_date do; Yahoo's chain dates only each contract's last trade,
which says when somebody traded, not when the bid and ask were set. Where there
is no quote time the screen says so instead of assuming the quote is current.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

from .. import session as session_mod

# The ranked plan's floors, unchanged from entry.py: open interest or volume of
# at least 50, a spread of at most 15% of the midpoint.
PLAN_MIN_ACTIVITY = 50
# The quick-glance ideas' activity floor, unchanged from swing.py's 20.
IDEA_MIN_ACTIVITY = 20
MAX_SPREAD_PCT = 15.0
STANDARD_MULTIPLIER = 100.0

# During the regular session a dated quote older than this is not used. Outside
# it every quote is the last session's, which the screen says rather than hides.
MAX_QUOTE_AGE_MINUTES = 20

NOT_A_FILL = ("The midpoint is an estimate between the bid and the ask, not a "
              "price anybody has offered; a fill can be worse.")
OI_CAVEAT = ("Open interest and volume show trading interest, not that an order "
             "will fill: open interest counts contracts still open after the last "
             "session, volume counts today's trades so far.")


def _num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


_OCC = re.compile(r"^([A-Z0-9.]{1,6})(\d{6})([CP])(\d{8})$")


def option_root(contract: Any) -> Optional[str]:
    """The root of an OCC option symbol: what comes before the date, the side
    and the strike. "AAPL261120C00350000" is AAPL. None for anything that is not
    an OCC symbol, which is treated as a standard contract rather than guessed at."""
    m = _OCC.match(str(contract or "").strip().upper())
    return m.group(1) if m else None


def multipliers(frame: pd.DataFrame, ticker: Optional[str]) -> pd.Series:
    """Shares per contract, or NaN where it is not known.

    The provider's own size where it gives one. Otherwise 100 for a contract
    whose root is the ticker, and unknown for one whose root differs, which is
    how an adjusted contract appears in a chain that does not state sizes."""
    if "multiplier" in frame.columns:
        given = _num(frame["multiplier"])
    else:
        given = pd.Series(np.nan, index=frame.index)
    if "contract" in frame.columns and len(frame):
        roots = frame["contract"].map(option_root)
        # Without a ticker, the chain's own most common root is the standard
        # one: adjusted contracts are a handful beside the regular series.
        want = str(ticker).upper() if ticker else (
            roots.dropna().mode().iloc[0] if roots.notna().any() else None)
        standard = roots.isna() | (roots == want) if want else pd.Series(True, index=frame.index)
    else:
        standard = pd.Series(True, index=frame.index)
    implied = pd.Series(np.where(standard, STANDARD_MULTIPLIER, np.nan), index=frame.index)
    return given.where(given.notna() & (given > 0), implied)


def _quote_age_minutes(frame: pd.DataFrame, now: datetime) -> Optional[pd.Series]:
    """Minutes since the older of the bid and the ask was set, or None when the
    provider does not date its quotes."""
    if "bid_time" not in frame.columns or "ask_time" not in frame.columns:
        return None
    bid_t = pd.to_datetime(frame["bid_time"], errors="coerce", utc=True)
    ask_t = pd.to_datetime(frame["ask_time"], errors="coerce", utc=True)
    if bid_t.isna().all() and ask_t.isna().all():
        return None
    older = pd.concat([bid_t, ask_t], axis=1).min(axis=1)
    stamp = pd.Timestamp(now).tz_convert("UTC") if pd.Timestamp(now).tzinfo else pd.Timestamp(now, tz="UTC")
    return (stamp - older).dt.total_seconds() / 60.0


def _new_report(criteria: str) -> Dict[str, Any]:
    return {"considered": 0, "passed": 0, "dropped": {}, "criteria": criteria,
            "quote_times": None, "reason": None, "notes": [NOT_A_FILL, OI_CAVEAT]}


def _dropper(report: Dict[str, Any]):
    def drop(pool: pd.DataFrame, mask: pd.Series, why: str) -> pd.DataFrame:
        mask = pd.Series(mask, index=pool.index).fillna(False).astype(bool)
        removed = int((~mask).sum())
        if removed:
            report["dropped"][why] = report["dropped"].get(why, 0) + removed
        return pool[mask]
    return drop


def usable(frame: Optional[pd.DataFrame], ticker: Optional[str] = None,
           now: Optional[datetime] = None,
           report: Optional[Dict[str, Any]] = None) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Contracts with a two-sided, uncrossed, dated-enough quote and a known size,
    with `mid`, `spread_pct` and `multiplier` recomputed from that quote."""
    now = now or datetime.now(timezone.utc)
    report = report if report is not None else _new_report(
        "a bid and an ask above zero and not crossed")
    if frame is None or frame.empty:
        report["reason"] = "no_contracts"
        return (frame if frame is not None else pd.DataFrame()), report
    drop = _dropper(report)
    pool = frame.copy()
    report["considered"] = int(len(pool))
    bid, ask = _num(pool["bid"]), _num(pool["ask"])
    pool = drop(pool, np.isfinite(bid) & np.isfinite(ask) & (bid > 0) & (ask > 0),
                "no usable bid or ask")
    pool = drop(pool, _num(pool["ask"]) >= _num(pool["bid"]), "a crossed market (bid above ask)")
    pool = drop(pool, multipliers(pool, ticker).notna(), "an adjusted contract whose size is not stated")
    bid, ask = _num(pool["bid"]), _num(pool["ask"])
    mid = (bid + ask) / 2.0
    pool = pool.assign(mid=mid, spread_pct=(ask - bid) / mid * 100.0,
                       multiplier=multipliers(pool, ticker))
    age = _quote_age_minutes(pool, now)
    if age is None:
        report["quote_times"] = ("not provided by this feed: the chain dates each "
                                 "contract's last trade, not its bid and ask")
    elif session_mod.state(now)["phase"] == "regular":
        pool = drop(pool, age <= MAX_QUOTE_AGE_MINUTES,
                    "a quote older than {} minutes".format(MAX_QUOTE_AGE_MINUTES))
        report["quote_times"] = ("dated by the feed; quotes older than {} minutes are "
                                 "not used during the session").format(MAX_QUOTE_AGE_MINUTES)
    else:
        report["quote_times"] = ("dated by the feed; the market is closed, so these "
                                 "are the last session's quotes")
    report["passed"] = int(len(pool))
    if pool.empty:
        report["reason"] = "unusable"
    return pool, report


def screen(frame: Optional[pd.DataFrame], ticker: Optional[str] = None,
           min_activity: float = PLAN_MIN_ACTIVITY, max_spread_pct: float = MAX_SPREAD_PCT,
           now: Optional[datetime] = None) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Usable quotes, then liquid ones, with a report of what each test removed.

    Never relaxes. Fewer passing contracts mean fewer candidates, and none
    means none, said in `report["reason"]`."""
    report = _new_report(("a bid and an ask above zero and not crossed, open interest or "
                          "volume of at least {:g}, and a spread of at most {:g}% of the "
                          "midpoint").format(min_activity, max_spread_pct))
    pool, report = usable(frame, ticker, now, report)
    if pool.empty:
        report["reason"] = report["reason"] or "illiquid"
        if report["considered"]:
            report["reason"] = "illiquid"
        return pool, report
    drop = _dropper(report)
    oi = _num(pool["open_interest"]).fillna(0.0)
    vol = _num(pool["volume"]).fillna(0.0)
    pool = drop(pool, (oi >= min_activity) | (vol >= min_activity),
                "open interest and volume both under {:g}".format(min_activity))
    pool = drop(pool, _num(pool["spread_pct"]) <= max_spread_pct,
                "a spread wider than {:g}% of the midpoint".format(max_spread_pct))
    report["passed"] = int(len(pool))
    report["reason"] = "illiquid" if pool.empty else None
    return pool, report


def describe_empty(report: Dict[str, Any], side: str = "contract") -> str:
    """The sentence for a screen that left nothing, with the numbers."""
    considered = report.get("considered") or 0
    if not considered:
        return "No {}s are quoted on this chain.".format(side)
    worst = sorted((report.get("dropped") or {}).items(), key=lambda kv: -kv[1])
    because = "; ".join("{} for {}".format(why, n) for why, n in worst[:3])
    return ("No contracts meet the liquidity criteria: none of the {} {}s considered "
            "has {}.{}").format(
                considered, side, report.get("criteria"),
                " Removed: {}.".format(because) if because else "")
