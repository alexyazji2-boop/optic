"""What changed since yesterday: the reader's names, compared session to session.

Asked for as a compact daily briefing for the watchlist and, where they already
exist, holdings: price moves and technical conditions, setups newly triggered
or invalidated, earnings approaching or just reported, and material changes to
the fundamental data on file. Three rules shape it.

**Two saved readings, never one reading and a guess.** Prices and technicals
come from the completed daily candles of the two sessions compared, which are
the exchange's own dated record: the earlier session's state is computed from
the candles up to its close and nothing after. Earnings dates and filed
fundamentals cannot be rebuilt that way, because today's feed only knows
today's answer, so they are read and saved once a session in this module's own
store (observations.db under TRACKER_DATA_DIR). A change there is one saved
reading against the reading before it. With no earlier reading there is no
comparison, and the briefing says so rather than calling it unchanged.

**The period is named.** The latest completed session against the one before
it, on the exchange calendar (app/session.py): on a Monday that is Friday
against Thursday, a holiday is skipped and named, and a session still trading
is part of neither.

**Unchanged has to be earned.** Each name is reported as changed, unchanged
(every check ran and none crossed its line), stale (the feed's newest candle is
older than the session compared) or missing (no candles), and a check that
could not run is named rather than counted as a pass.

Deterministic throughout: each sentence is a template filled from numbers, so
the briefing works with no AI service configured.
"""

from __future__ import annotations

import json
import logging
import math
import os
import sqlite3
import threading
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

import numpy as np
import pandas as pd

from . import session as session_mod
from .analytics import setups as setups_mod

log = logging.getLogger("optic.briefing")

_DATA_DIR = os.environ.get(
    "TRACKER_DATA_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"),
)
DB_PATH = os.path.join(_DATA_DIR, "observations.db")

ET = session_mod.ET

# A daily move is called out only when it is both large in itself and large
# for this stock: 2% is routine for a semiconductor and a lot for a utility, so
# the floor alone would flag one and never the other.
MOVE_FLOOR_PCT = 2.0
MOVE_SIGMAS = 2.0
TYPICAL_WINDOW = 20
VOLUME_MULTIPLE = 2.0
RSI_HIGH, RSI_LOW = 70.0, 30.0
# Leaving a zone has to mean it: 70 to 69 is the same reading, not news.
RSI_EXIT_BUFFER = 5.0
YEAR_SESSIONS = 252
# "Approaching" earnings: within the next five sessions.
EARNINGS_AHEAD_SESSIONS = 5
SHARES_CHANGE_PCT = 1.0
MAX_SYMBOLS = 60
# How many names one post-close pass reads, and for how long a guest's request
# keeps a name on that list. Each reading is up to four provider calls.
CAPTURE_PER_PASS = 120
REQUESTED_DAYS = 14

SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
  symbol      TEXT NOT NULL,
  session     TEXT NOT NULL,   -- the completed session the reading belongs to
  observed_at TEXT NOT NULL,   -- when it was read, UTC
  data        TEXT NOT NULL,
  PRIMARY KEY (symbol, session)
);
CREATE TABLE IF NOT EXISTS requested (
  symbol         TEXT PRIMARY KEY,
  last_requested TEXT NOT NULL
);
"""

_LOCK = threading.Lock()


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _num(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


# ---------------------------------------------------------------- the period

def previous_trading_day(day: date) -> date:
    probe = day - timedelta(days=1)
    for _ in range(10):
        if session_mod.regular_close(probe) is not None:
            return probe
        probe -= timedelta(days=1)
    return probe


def latest_session(now: datetime) -> date:
    """The newest session whose regular close has passed."""
    now_et = now.astimezone(ET)
    day = now_et.date()
    for _ in range(10):
        close_at = session_mod.regular_close(day)
        if close_at is not None and close_at <= now_et:
            return day
        day -= timedelta(days=1)
    return day


def _day_label(day: date) -> str:
    return "{} {} {}".format(day.strftime("%a"), day.strftime("%b"), day.day)


def period(now: Optional[datetime] = None) -> Dict[str, Any]:
    """The two closes compared, and what the gap between them skipped."""
    now = now or datetime.now(timezone.utc)
    latest = latest_session(now)
    previous = previous_trading_day(latest)
    skipped: List[str] = []
    probe = previous + timedelta(days=1)
    # Copied: market_holidays may hand back a cached dict.
    holidays = dict(session_mod.market_holidays(latest.year))
    holidays.update(session_mod.market_holidays(previous.year))
    while probe < latest:
        if probe in holidays:
            skipped.append("{} ({})".format(_day_label(probe), holidays[probe]))
        elif probe.weekday() >= 5:
            if probe.weekday() == 5:
                skipped.append("the weekend")
        probe += timedelta(days=1)
    now_et = now.astimezone(ET)
    today_close = session_mod.regular_close(now_et.date())
    in_progress = (today_close is not None and now_et.date() > latest
                   and now_et.hour * 60 + now_et.minute >= session_mod.REGULAR_START
                   and now_et < today_close)
    label = "From the close of {} to the close of {}".format(_day_label(previous), _day_label(latest))
    notes = []
    if skipped:
        notes.append("No session in between: {}.".format(", ".join(skipped)))
    if in_progress:
        notes.append("Today's session is still trading and is not part of this comparison.")
    return {"latest": latest.isoformat(), "previous": previous.isoformat(), "label": label,
            "skipped": skipped, "in_progress": in_progress, "notes": notes}


def sessions_between(a: date, b: date) -> int:
    """Trading sessions after `a` up to and including `b`."""
    n, probe = 0, a
    for _ in range(40):
        if probe >= b:
            break
        probe = session_mod.next_trading_day(probe)
        if probe <= b:
            n += 1
    return n


# ---------------------------------------------------------------- the store

def record(symbol: str, session: str, data: Dict[str, Any],
           when: Optional[datetime] = None) -> bool:
    """Save one reading. The first reading of a session stands: a second one
    the same session would let the comparison drift with the time of day."""
    when = when or datetime.now(timezone.utc)
    with _LOCK, closing(_connect()) as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO observations (symbol, session, observed_at, data) VALUES (?,?,?,?)",
            (symbol, session, when.isoformat(), json.dumps(data, sort_keys=True)))
        conn.commit()
        return cur.rowcount > 0


def readings(symbol: str, upto: str) -> List[Dict[str, Any]]:
    """The newest saved reading at or before `upto`, and the one before it."""
    with _LOCK, closing(_connect()) as conn:
        rows = conn.execute(
            "SELECT * FROM observations WHERE symbol = ? AND session <= ? ORDER BY session DESC LIMIT 2",
            (symbol, upto)).fetchall()
    out = []
    for r in rows:
        try:
            data = json.loads(r["data"])
        except (TypeError, ValueError):
            data = {}
        out.append({"session": r["session"], "observed_at": r["observed_at"], "data": data})
    return out


def has_reading(symbol: str, session: str) -> bool:
    with _LOCK, closing(_connect()) as conn:
        return conn.execute("SELECT 1 FROM observations WHERE symbol = ? AND session = ?",
                            (symbol, session)).fetchone() is not None


def note_requested(symbols: Iterable[str], when: Optional[datetime] = None) -> None:
    """Names somebody asked about, so the post-close pass reads them. The
    symbol and a time, nothing about who asked."""
    stamp = (when or datetime.now(timezone.utc)).isoformat()
    with _LOCK, closing(_connect()) as conn:
        conn.executemany(
            "INSERT INTO requested (symbol, last_requested) VALUES (?, ?) "
            "ON CONFLICT(symbol) DO UPDATE SET last_requested = excluded.last_requested",
            [(s, stamp) for s in symbols])
        conn.commit()


def recently_requested(when: Optional[datetime] = None) -> List[str]:
    since = ((when or datetime.now(timezone.utc)) - timedelta(days=REQUESTED_DAYS)).isoformat()
    with _LOCK, closing(_connect()) as conn:
        return [r["symbol"] for r in conn.execute(
            "SELECT symbol FROM requested WHERE last_requested >= ? ORDER BY symbol", (since,))]


def observe(provider, symbol: str) -> Dict[str, Any]:
    """One reading of what cannot be rebuilt from candles: the next earnings
    date, the last reported quarter, the filed trailing figures and the share
    count. A field the feed did not answer is None, with the reason kept."""
    from .analytics import sec_facts
    data: Dict[str, Any] = {"errors": {}}
    try:
        data["next_earnings"] = provider.earnings_date(symbol)
    except Exception as exc:                                   # noqa: BLE001
        data["next_earnings"] = None
        data["errors"]["next_earnings"] = str(exc)[:120]
    try:
        rows = provider.earnings_history(symbol, limit=8) or []
        done = [r for r in rows if r.get("eps_reported") is not None and r.get("date")]
        data["last_reported"] = max(done, key=lambda r: r["date"]) if done else None
    except Exception as exc:                                   # noqa: BLE001
        data["last_reported"] = None
        data["errors"]["last_reported"] = str(exc)[:120]
    try:
        facts = sec_facts.history(symbol)
    except Exception as exc:                                   # noqa: BLE001
        facts = {"available": False, "reason": str(exc)[:120]}
    if facts.get("available"):
        rev = (facts.get("revenue_ttm") or [None])[-1]
        eps = (facts.get("eps_ttm") or [None])[-1]
        data["revenue_ttm"] = ({"value": rev["value"], "period_end": rev["period_end"],
                                "available_from": rev.get("available_from")} if rev else None)
        data["eps_ttm"] = ({"value": eps["value"], "period_end": eps["period_end"],
                            "available_from": eps.get("available_from")} if eps else None)
    else:
        data["revenue_ttm"] = data["eps_ttm"] = None
        data["errors"]["filings"] = facts.get("reason") or "No SEC filings for this symbol."
    try:
        data["shares_outstanding"] = _num((provider.short_interest(symbol) or {}).get("shares_outstanding"))
    except Exception as exc:                                   # noqa: BLE001
        data["shares_outstanding"] = None
        data["errors"]["shares_outstanding"] = str(exc)[:120]
    return data


def capture(provider, symbols: Sequence[str], session: str,
            when: Optional[datetime] = None, limit: int = CAPTURE_PER_PASS) -> Dict[str, Any]:
    """Read and save every name that has no reading for `session` yet."""
    todo = [s for s in symbols if not has_reading(s, session)][:limit]
    saved = 0
    for sym in todo:
        try:
            if record(sym, session, observe(provider, sym), when):
                saved += 1
        except Exception as exc:                               # noqa: BLE001
            log.warning("briefing: reading %s failed: %s", sym, exc)
    return {"session": session, "wanted": len(todo), "saved": saved}


# ---------------------------------------------------------------- the checks

def _sma(c: np.ndarray, n: int) -> np.ndarray:
    return pd.Series(c).rolling(n, min_periods=n).mean().to_numpy()


def _fmt_price(v: float) -> str:
    return "{:,.2f}".format(v)


def _fmt_pct(v: float, digits: int = 1) -> str:
    text = "{:+.{d}f}%".format(v, d=digits)
    return text.replace("+-", "-")


def _big(v: float) -> str:
    for cut, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(v) >= cut:
            return "{:.1f}{}".format(v / cut, suffix)
    return "{:.0f}".format(v)


def price_checks(symbol: str, bars: Optional[setups_mod.Bars], latest: str,
                 previous: str) -> Dict[str, Any]:
    """The move between the two closes and the technical conditions at each,
    each computed from candles up to its own close."""
    if bars is None or not len(bars):
        return {"state": "missing", "note": "No daily candles from the feed for {}.".format(symbol)}
    stamps = bars.stamps
    if stamps[-1] < latest:
        return {"state": "stale", "as_of": stamps[-1],
                "note": "The feed's newest completed candle is {}, older than the {} session "
                        "compared.".format(stamps[-1], latest)}
    try:
        i, j = stamps.index(latest), stamps.index(previous)
    except ValueError:
        return {"state": "missing",
                "note": "No candle for {} or {} in the feed.".format(previous, latest)}
    c, v = bars.c, bars.v
    close_l, close_p = float(c[i]), float(c[j])
    change = (close_l / close_p - 1.0) * 100.0
    out: Dict[str, Any] = {"state": "ok", "close": close_l, "previous_close": close_p,
                           "change_pct": round(change, 2), "items": [], "not_checked": []}

    # Its usual daily move, from the sessions before the earlier close.
    hist = c[: j + 1]
    typical = None
    if len(hist) > TYPICAL_WINDOW:
        rets = np.diff(hist[-(TYPICAL_WINDOW + 1):]) / hist[-(TYPICAL_WINDOW + 1):-1] * 100.0
        typical = float(np.std(rets, ddof=1)) if len(rets) > 1 else None
    out["typical_pct"] = round(typical, 2) if typical else None
    vol_ratio = None
    if i >= TYPICAL_WINDOW and v[i] > 0:
        base = float(np.mean(v[i - TYPICAL_WINDOW:i]))
        vol_ratio = float(v[i]) / base if base > 0 else None
    out["volume_ratio"] = round(vol_ratio, 2) if vol_ratio else None

    unusual = abs(change) >= MOVE_FLOOR_PCT and (typical is None or abs(change) >= MOVE_SIGMAS * typical)
    if unusual:
        bits = []
        if typical:
            bits.append("about {:.1f} times its typical daily move of {:.1f}% over the "
                        "previous {} sessions".format(abs(change) / typical, typical, TYPICAL_WINDOW))
        if vol_ratio and vol_ratio >= VOLUME_MULTIPLE:
            bits.append("on volume {:.1f} times its 20-day average".format(vol_ratio))
        out["items"].append({
            "kind": "move", "rank": 1,
            "headline": "{} {} {:.1f}% to {}".format(symbol, "rose" if change > 0 else "fell",
                                                     abs(change), _fmt_price(close_l)),
            "detail": (bits[0][0].upper() + bits[0][1:] + (", " + bits[1] if len(bits) > 1 else "") + "."
                       ) if bits else "",
            "why": "A move this far outside its usual range usually has a reason, and it "
                   "can change how the chart's levels read.",
            "link": {"view": "chart"},
        })

    def cross(n: int) -> None:
        if i < n:
            out["not_checked"].append("the {}-day average (fewer than {} candles)".format(n, n))
            return
        avg = _sma(c[: i + 1], n)
        a_l, a_p = avg[i], avg[j]
        if not (np.isfinite(a_l) and np.isfinite(a_p)):
            out["not_checked"].append("the {}-day average".format(n))
            return
        above_l, above_p = close_l > a_l, close_p > a_p
        if above_l == above_p:
            return
        out["items"].append({
            "kind": "technical", "rank": 2 if n == 200 else 3,
            "headline": "{} closed {} its {}-day average".format(
                symbol, "above" if above_l else "below", n),
            "detail": "Close {} against the average at {}; the previous close was {} it.".format(
                _fmt_price(close_l), _fmt_price(float(a_l)), "below" if above_l else "above"),
            "why": ("The {}-day average is a common line between {}; a close through it is a "
                    "change of state, not a forecast.").format(
                        n, "a long-term uptrend and downtrend" if n == 200 else "a trend and a pullback"),
            "link": {"view": "chart"},
        })

    cross(50)
    cross(200)

    r = setups_mod.rsi(c[: i + 1], 14)
    if np.isfinite(r[i]) and np.isfinite(r[j]):
        zone = lambda x: "overbought" if x >= RSI_HIGH else "oversold" if x <= RSI_LOW else "neutral"
        z_l, z_p = zone(r[i]), zone(r[j])
        if z_l != z_p and z_l != "neutral":
            out["items"].append({
                "kind": "technical", "rank": 4,
                "headline": "{} RSI entered {} territory at {:.0f}".format(symbol, z_l, r[i]),
                "detail": "The 14-day RSI went from {:.0f} to {:.0f}.".format(r[j], r[i]),
                "why": "Readings past {:.0f} or {:.0f} describe a stretched move; they often "
                       "persist in a strong trend.".format(RSI_HIGH, RSI_LOW),
                "link": {"view": "chart"},
            })
        elif z_p != "neutral" and z_l == "neutral" and (
                r[i] <= RSI_HIGH - RSI_EXIT_BUFFER if z_p == "overbought" else r[i] >= RSI_LOW + RSI_EXIT_BUFFER):
            out["items"].append({
                "kind": "technical", "rank": 5,
                "headline": "{} RSI left {} territory".format(symbol, z_p),
                "detail": "The 14-day RSI went from {:.0f} to {:.0f}.".format(r[j], r[i]),
                "why": "The stretched reading has eased, which is where pullback and "
                       "reversal setups start to read.",
                "link": {"view": "chart"},
            })
    else:
        out["not_checked"].append("RSI (not enough candles)")

    if i >= YEAR_SESSIONS:
        prior = c[i - YEAR_SESSIONS:i]
        if close_l > float(np.max(prior)):
            out["items"].append({
                "kind": "technical", "rank": 2,
                "headline": "{} closed at a 52-week high".format(symbol),
                "detail": "Close {}, above every close of the previous year.".format(_fmt_price(close_l)),
                "why": "A new high leaves no overhead level from the past year to trade against.",
                "link": {"view": "chart"},
            })
        elif close_l < float(np.min(prior)):
            out["items"].append({
                "kind": "technical", "rank": 2,
                "headline": "{} closed at a 52-week low".format(symbol),
                "detail": "Close {}, below every close of the previous year.".format(_fmt_price(close_l)),
                "why": "A new low leaves no support level from the past year beneath it.",
                "link": {"view": "chart"},
            })
    else:
        out["not_checked"].append("52-week highs and lows (less than a year of candles)")
    return out


def setup_checks(symbol: str, result: Optional[Dict[str, Any]], latest: str) -> Dict[str, Any]:
    """Setups that triggered or were invalidated on the latest completed candle,
    one item for each, however many rules agreed: three breakout rules firing
    on one close is one event seen three ways."""
    if not result or not result.get("available"):
        return {"ran": False, "items": [], "note": (result or {}).get("reason") or "No setups reading."}
    fired, ended = [], []
    for r in result.get("rows") or []:
        trig = r.get("trigger") or {}
        if r.get("status") == "triggered" and trig.get("stamp") == latest:
            fired.append(r)
        elif r.get("status") == "invalidated" and r.get("status_at") == latest:
            ended.append(r)

    def names(rows: List[Dict[str, Any]]) -> str:
        return ", ".join("{} ({})".format(r.get("label"), "bullish" if r.get("direction") == "bull"
                                          else "bearish") for r in rows)

    def stops(rows: List[Dict[str, Any]]) -> str:
        """Where each would be invalidated: the level a reader acts on, which the
        rules' full explanations bury in their last sentence."""
        levels = []
        for r in rows:
            lvl = _num(r.get("invalidation"))
            if lvl is None:
                continue
            text = "a close {} {}".format("below" if r.get("direction") == "bull" else "above", _fmt_price(lvl))
            if text not in levels:
                levels.append(text)
        return " Invalidated by {}.".format(" or ".join(levels)) if levels else ""

    items = []
    if fired:
        items.append({
            "kind": "setup", "rank": 1,
            "headline": "{} {} triggered on the close".format(
                symbol, "a setup" if len(fired) == 1 else "{} setups".format(len(fired))),
            "detail": names(fired) + "." + stops(fired),
            "why": "A rule's trigger on a completed candle, with its invalidation level already "
                   "set, read with the default rules. It is for review, not an order.",
            "link": {"view": "swing", "panel": "Swing setups"},
        })
    if ended:
        items.append({
            "kind": "setup", "rank": 2,
            "headline": "{} {} invalidated on the close".format(
                symbol, "a setup was" if len(ended) == 1 else "{} setups were".format(len(ended))),
            "detail": names(ended) + ".",
            "why": "The level the setup depended on gave way on a completed close.",
            "link": {"view": "swing", "panel": "Swing setups"},
        })
    return {"ran": True, "items": items}


def earnings_checks(symbol: str, reading: Optional[Dict[str, Any]], latest: str,
                    previous: str) -> Dict[str, Any]:
    if not reading:
        return {"ran": False, "items": []}
    data = reading["data"]
    items = []
    l_day, p_day = date.fromisoformat(latest), date.fromisoformat(previous)
    nxt = data.get("next_earnings")
    if nxt:
        try:
            d = date.fromisoformat(str(nxt)[:10])
        except ValueError:
            d = None
        if d and d > l_day:
            ahead = sessions_between(l_day, d)
            if ahead <= EARNINGS_AHEAD_SESSIONS:
                items.append({
                    "kind": "earnings", "rank": 2,
                    "headline": "{} reports earnings on {} ({} session{} away)".format(
                        symbol, _day_label(d), ahead, "" if ahead == 1 else "s"),
                    "detail": "Date as read on {}.".format(reading["observed_at"][:10]),
                    "why": "A report can move the price and resets implied volatility; options "
                           "expiring after it carry the event.",
                    "link": {"view": "earnings"},
                })
    last = data.get("last_reported")
    if last and last.get("date"):
        try:
            d = date.fromisoformat(str(last["date"])[:10])
        except ValueError:
            d = None
        if d and p_day < d <= l_day:
            est, rep = _num(last.get("eps_estimate")), _num(last.get("eps_reported"))
            detail = "Reported EPS {:.2f}".format(rep) if rep is not None else "Reported"
            if est is not None and rep is not None:
                detail += " against {:.2f} expected".format(est)
                if est:
                    detail += " ({})".format(_fmt_pct((rep / abs(est) - 1.0) * 100.0 if est > 0 else
                                                      (rep - est) / abs(est) * 100.0))
            items.append({
                "kind": "earnings", "rank": 1,
                "headline": "{} reported earnings on {}".format(symbol, _day_label(d)),
                "detail": detail + ".",
                "why": "The sessions right after a report are when the market prices it.",
                "link": {"view": "earnings"},
            })
    return {"ran": True, "items": items}


def fundamental_checks(symbol: str, reads: List[Dict[str, Any]]) -> Dict[str, Any]:
    """The newest saved reading against the one before it."""
    if not reads:
        return {"ran": False, "items": [], "note": "Not read yet: the first reading is saved after a close."}
    if len(reads) < 2:
        return {"ran": False, "items": [],
                "note": "First reading saved {}; changes show from the next one.".format(
                    reads[0]["observed_at"][:10])}
    new, old = reads[0]["data"], reads[1]["data"]
    items = []
    rn, ro = new.get("revenue_ttm") or {}, old.get("revenue_ttm") or {}
    if rn.get("period_end") and ro.get("period_end") and rn["period_end"] > ro["period_end"]:
        grow = ((rn["value"] / ro["value"] - 1.0) * 100.0) if ro.get("value") else None
        items.append({
            "kind": "fundamental", "rank": 1,
            "headline": "{} filed a new quarter: trailing revenue {}".format(symbol, "$" + _big(rn["value"])),
            "detail": "Twelve months to {}{}.".format(
                rn["period_end"], ", {} on the trailing figure on file before".format(_fmt_pct(grow))
                if grow is not None else ""),
            "why": "Revenue is the base the growth readings and valuation scenarios start from.",
            "link": {"view": "financials"},
        })
    en, eo = new.get("eps_ttm") or {}, old.get("eps_ttm") or {}
    if en.get("period_end") and eo.get("period_end") and en["period_end"] > eo["period_end"]:
        items.append({
            "kind": "fundamental", "rank": 2,
            "headline": "{} trailing EPS is now {:.2f}".format(symbol, en["value"]),
            "detail": "Was {:.2f} for the twelve months to {}.".format(eo["value"], eo["period_end"]),
            "why": "Trailing earnings are what the P/E on every panel divides by.",
            "link": {"view": "long"},
        })
    sn, so = _num(new.get("shares_outstanding")), _num(old.get("shares_outstanding"))
    if sn and so and abs(sn / so - 1.0) * 100.0 >= SHARES_CHANGE_PCT:
        pct = (sn / so - 1.0) * 100.0
        items.append({
            "kind": "fundamental", "rank": 3,
            "headline": "{} shares outstanding {} {:.1f}%".format(
                symbol, "rose" if pct > 0 else "fell", abs(pct)),
            "detail": "{} shares, from {}.".format(_big(sn), _big(so)),
            "why": "Per-share earnings move with the share count: issuance dilutes, buybacks "
                   "concentrate.",
            "link": {"view": "long"},
        })
    dn, do = new.get("next_earnings"), old.get("next_earnings")
    if dn and do and dn != do:
        items.append({
            "kind": "earnings", "rank": 2,
            "headline": "{} earnings date moved to {}".format(symbol, dn),
            "detail": "It read {} on {}.".format(do, reads[1]["observed_at"][:10]),
            "why": "A moved date changes which expiries carry the report.",
            "link": {"view": "earnings"},
        })
    return {"ran": True, "items": items, "compared": [reads[1]["observed_at"], reads[0]["observed_at"]]}


# ---------------------------------------------------------------- the briefing

def build(symbols: Sequence[str], holdings: Iterable[str],
          bars_for: Callable[[str], Optional[setups_mod.Bars]],
          setups_for: Callable[[str], Optional[Dict[str, Any]]],
          per: Dict[str, Any]) -> Dict[str, Any]:
    """Every name's checks, in one deterministic report. Network is the
    caller's: candles and setups arrive through `bars_for` and `setups_for`."""
    held = set(holdings or [])
    latest, previous = per["latest"], per["previous"]
    names: List[Dict[str, Any]] = []
    items: List[Dict[str, Any]] = []
    unread: List[str] = []
    for sym in symbols:
        price = price_checks(sym, bars_for(sym), latest, previous)
        setups = setup_checks(sym, setups_for(sym), latest) if price["state"] == "ok" else {"ran": False, "items": []}
        reads = readings(sym, latest)
        if not reads:
            unread.append(sym)
        earnings = earnings_checks(sym, reads[0] if reads else None, latest, previous)
        funds = fundamental_checks(sym, reads)
        found = price.get("items", []) + setups["items"] + earnings["items"] + funds["items"]
        for it in found:
            it["symbol"] = sym
            it["holding"] = sym in held
            items.append(it)
        not_checked = list(price.get("not_checked") or [])
        if not setups["ran"]:
            not_checked.append("setups")
        if not reads:
            not_checked.append("earnings dates and filings (not read yet)")
        elif not funds["ran"]:
            not_checked.append("filings and share count (only one reading so far)")
        if price["state"] != "ok":
            state, summary = price["state"], price["note"]
        elif found:
            state = "changed"
            summary = "{} change{}.".format(len(found), "" if len(found) == 1 else "s")
        else:
            state = "unchanged"
            ran = ["moved {} ({})".format(_fmt_pct(price["change_pct"]),
                                         "within its usual range" if price.get("typical_pct") else
                                         "under the {:.0f}% line".format(MOVE_FLOOR_PCT))]
            if setups["ran"]:
                ran.append("no setup triggered or invalidated")
            if earnings["ran"]:
                ran.append("no earnings reported or due within {} sessions".format(EARNINGS_AHEAD_SESSIONS))
            if funds["ran"]:
                ran.append("no new filing or share count change")
            summary = "No meaningful change: " + "; ".join(ran) + "."
        names.append({"symbol": sym, "holding": sym in held, "state": state, "summary": summary,
                      "change_pct": price.get("change_pct"), "close": price.get("close"),
                      "not_checked": not_checked,
                      "fundamentals_note": funds.get("note"),
                      "compared_readings": funds.get("compared")})
    items.sort(key=lambda it: (not it["holding"], it.get("rank", 9), it["symbol"]))
    counts = {k: sum(1 for n in names if n["state"] == k) for k in ("changed", "unchanged", "stale", "missing")}
    parts = []
    if counts["changed"]:
        parts.append("{} of {} name{} changed".format(counts["changed"], len(names), "" if len(names) == 1 else "s"))
    if counts["unchanged"]:
        parts.append("{} had no meaningful change".format(counts["unchanged"]))
    if counts["stale"]:
        parts.append("{} {} stale data".format(counts["stale"], "has" if counts["stale"] == 1 else "have"))
    if counts["missing"]:
        parts.append("{} had no data for the period".format(counts["missing"]))
    return {
        "available": True,
        "period": per,
        "items": items,
        "names": names,
        "counts": counts,
        "summary": ("; ".join(parts) + ".") if parts else "Nothing to compare.",
        "unread": unread,
        "method": ("Prices and technical conditions come from the completed daily candles of the "
                   "two sessions, each read only up to its own close. Earnings dates, filings and "
                   "share counts are compared between readings saved once a session; a name with "
                   "one reading so far has nothing to compare them with. Written from fixed rules, "
                   "not by an AI model."),
        "source": "Yahoo Finance daily candles and earnings calendar; SEC filings (XBRL).",
    }
