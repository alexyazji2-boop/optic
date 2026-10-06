"""Signal history: each swing-setup trigger a reader was alerted to, and what followed.

Asked for as "transparent, persistent signal history". What counts as a signal
is deliberately narrow: a Swing setups rule that fired on a completed candle
and raised one of the reader's own `swing_setup` alerts. Not a bullish score,
not a page view, not a row on the scanner nobody asked to be told about. The
record is made when the alert path sees the trigger, from what the engine
reported at that moment, and never later from history: this module has no way
to create a signal for a candle it did not see fire, which is what keeps the
history from being backfilled with hindsight.

**The record is immutable.** Symbol, strategy, side and timeframe; when the
trigger candle closed and the newest candle the evaluation read; the trigger
price, the level it crossed, the invalidation and a target where the rule has
one (the setups rules do not); the rule checks and indicator readings exactly
as they stood; the data source, the rule version, the parameters and the
assumptions. The database refuses an UPDATE on it (app/db.py, MIGRATION_10).

**What followed is recorded beside it, once each.** A status when the trigger
is invalidated (a completed close beyond its invalidation level) or its
listing window ends, and an observation of the stock's close a fixed number of
completed candles after the trigger. Each is stamped with when it was observed
and which candle it read. A horizon whose candle has not printed, or is
missing from the feed, has no row, and the page shows it as unknown: never as
a zero, a win or a loss.

**What an observation is.** The change in the underlying stock's closing price
from the trigger candle's close to a later candle's close. Not an options
return, not a trade's result: nothing here was bought or sold, and no option
price is known for those dates.
"""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

from . import db
from .analytics import setups as setups_mod

log = logging.getLogger("optic.signals")

# Completed candles after the trigger candle at which the close is observed.
HORIZONS = (1, 5, 10, 20)

TERMINAL = ("invalidated", "expired")

SOURCE = ("Yahoo Finance daily candles (split-adjusted, not dividend-adjusted), "
          "read by Optic's Swing setups engine")

ASSUMPTIONS = [
    "Rules read completed candles only; the trigger candle had closed when it fired.",
    "Swing pivots count only once their confirmation bars had printed.",
    "The higher-timeframe filter read completed weekly candles.",
    "Invalidation is a completed close beyond the level, not an intraday touch.",
    "Prices are delayed exchange data; nothing was traded.",
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _num(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def record_from_row(row: Dict[str, Any], *, data_as_of: str, params: Dict[str, Any],
                    trigger_completed_at: Optional[str] = None) -> Dict[str, Any]:
    """The immutable record's fields from a Swing setups row, as it stood."""
    trig = row.get("trigger") or {}
    return {
        "signal_key": row["key"],
        "symbol": row["symbol"],
        "strategy": row["preset"],
        "strategy_label": row.get("label") or row["preset"],
        "family": row.get("family") or "",
        "kind": row.get("kind") or "",
        "direction": row["direction"],
        "timeframe": row.get("timeframe") or "daily",
        "trigger_at": trig.get("stamp") or row.get("status_at"),
        "trigger_completed_at": trigger_completed_at,
        "data_as_of": data_as_of,
        "trigger_price": _num(trig.get("close")),
        "trigger_level": _num(trig.get("level")),
        "invalidation": _num(row.get("invalidation")),
        "target": None,
        "conditions": {"checks": row.get("checks") or [],
                       "met": (row.get("conditions") or {}).get("met"),
                       "of": (row.get("conditions") or {}).get("of"),
                       "note": (row.get("conditions") or {}).get("note")},
        "indicators": row.get("values") or {},
        "explanation": row.get("explanation") or "",
        "source": SOURCE,
        "rule_version": setups_mod.RULES_VERSION,
        "params": params or {},
        "assumptions": ASSUMPTIONS,
    }


def record(user_id: str, rec: Dict[str, Any], origin: str,
           when: Optional[datetime] = None) -> Optional[str]:
    """Store one signal for one reader. None when that reader already has it.

    The unique index on (user_id, signal_key) is the dedupe, so a second
    runner, the page's own check and a retry all land on the one row."""
    when = when or _now()
    sid = db.new_id()
    try:
        db.execute(
            "INSERT INTO signals (id, user_id, signal_key, symbol, strategy, strategy_label, "
            "family, kind, direction, timeframe, trigger_at, trigger_completed_at, data_as_of, "
            "recorded_at, trigger_price, trigger_level, invalidation, target, conditions, "
            "indicators, explanation, source, rule_version, params, assumptions, origin) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (sid, user_id, rec["signal_key"], rec["symbol"], rec["strategy"],
             rec["strategy_label"], rec.get("family") or "", rec.get("kind") or "",
             rec["direction"], rec["timeframe"], rec["trigger_at"],
             rec.get("trigger_completed_at"), rec["data_as_of"], when.isoformat(),
             rec.get("trigger_price"), rec.get("trigger_level"), rec.get("invalidation"),
             rec.get("target"), json.dumps(rec.get("conditions") or {}),
             json.dumps(rec.get("indicators") or {}), rec.get("explanation") or "",
             rec.get("source") or "", rec.get("rule_version") or "",
             json.dumps(rec.get("params") or {}, sort_keys=True),
             json.dumps(rec.get("assumptions") or []), origin))
    except Exception as exc:                              # the unique index, normally
        if "UNIQUE" not in str(exc).upper():
            log.warning("signal not stored: %s", exc)
        return None
    return sid


def add_event(signal: Dict[str, Any], kind: str, label: str, data_as_of: str,
              price: Optional[float] = None, change_pct: Optional[float] = None,
              detail: str = "", when: Optional[datetime] = None) -> bool:
    """Append one status or observation. False when it was already recorded."""
    when = when or _now()
    try:
        db.execute(
            "INSERT INTO signal_events (id, signal_id, user_id, kind, label, observed_at, "
            "data_as_of, price, change_pct, detail) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (db.new_id(), signal["id"], signal["user_id"], kind, label, when.isoformat(),
             data_as_of, price, change_pct, detail))
    except Exception as exc:
        if "UNIQUE" not in str(exc).upper():
            log.warning("signal event not stored: %s", exc)
        return False
    return True


# ------------------------------------------------------------- what followed

def followup_events(sig: Dict[str, Any], bars: Optional[setups_mod.Bars],
                    signal_ttl: int) -> List[Dict[str, Any]]:
    """What the completed candles after a trigger say, from the record alone.

    Status from the record's own invalidation level and listing window, so the
    verdict cannot drift with a later version of the rules: the first completed
    close beyond the invalidation invalidates it, and `signal_ttl` candles
    without one end its listing. Observations are the close at each horizon.
    A horizon whose candle is not in `bars` produces nothing, which the page
    shows as unknown."""
    if bars is None or not len(bars):
        return []
    try:
        t0 = bars.stamps.index(sig["trigger_at"])
    except ValueError:
        return []                      # the trigger candle is not in the feed now
    out: List[Dict[str, Any]] = []
    bull = sig["direction"] == "bull"
    stop = _num(sig.get("invalidation"))
    base = _num(sig.get("trigger_price"))
    status = None
    for k in range(t0 + 1, len(bars)):
        c = float(bars.c[k])
        if stop is not None and ((bull and c < stop) or (not bull and c > stop)):
            status = {"kind": "status", "label": "invalidated", "data_as_of": bars.stamps[k],
                      "price": c, "detail": "Completed close {} the invalidation at {:.2f}.".format(
                          "below" if bull else "above", stop)}
            break
        if k - t0 >= signal_ttl:
            status = {"kind": "status", "label": "expired", "data_as_of": bars.stamps[k],
                      "price": c, "detail": "Listed for {} candles without invalidation.".format(signal_ttl)}
            break
    if status:
        out.append(status)
    for h in HORIZONS:
        k = t0 + h
        if k >= len(bars) or base is None or base == 0:
            continue
        c = float(bars.c[k])
        out.append({"kind": "observation", "label": "after {} candle{}".format(h, "" if h == 1 else "s"),
                    "data_as_of": bars.stamps[k], "price": c,
                    "change_pct": (c / base - 1.0) * 100.0,
                    "detail": "Close-to-close change in the stock from the trigger candle."})
    return out


def _signal_ttl(sig: Dict[str, Any]) -> int:
    try:
        params = json.loads(sig.get("params") or "{}")
    except (TypeError, ValueError):
        params = {}
    try:
        return max(1, int(params.get("signal_ttl") or 10))
    except (TypeError, ValueError):
        return 10


def pending() -> List[Dict[str, Any]]:
    """Every signal, across accounts, still missing a status or a horizon."""
    rows = db.rows(
        "SELECT s.*, (SELECT COUNT(*) FROM signal_events e WHERE e.signal_id = s.id) AS events, "
        "(SELECT COUNT(*) FROM signal_events e WHERE e.signal_id = s.id AND e.kind = 'status') AS statuses "
        "FROM signals s ORDER BY s.symbol")
    want = 1 + len(HORIZONS)
    return [r for r in rows if r["events"] < want]


def followup_all(load_bars: Callable[[List[str]], Dict[str, setups_mod.Bars]],
                 when: Optional[datetime] = None) -> Dict[str, Any]:
    """Append what is newly knowable for every unfinished signal.

    `load_bars` takes symbols and returns their completed daily candles; it is
    injected so a test can drive this with no network, and so the scheduler can
    hand it one batched download for every symbol at once."""
    todo = pending()
    symbols = sorted({r["symbol"] for r in todo})
    bars = load_bars(symbols) if symbols else {}
    added = 0
    for sig in todo:
        for ev in followup_events(sig, bars.get(sig["symbol"]), _signal_ttl(sig)):
            if add_event(sig, ev["kind"], ev["label"], ev["data_as_of"], ev.get("price"),
                         ev.get("change_pct"), ev.get("detail") or "", when):
                added += 1
    return {"signals": len(todo), "symbols": len(symbols), "events_added": added}


def horizon_states(sig: Dict[str, Any], events: Sequence[Dict[str, Any]],
                   today: Optional[str] = None) -> List[Dict[str, Any]]:
    """Each horizon as observed, still to come, or missing.

    Counted in exchange sessions from the trigger candle, on the server's
    calendar (app/session.py), so a page never has to do calendar arithmetic.
    "Missing" is a horizon whose session has passed with no observation: the
    feed had no candle for it or the follow-up has not run since. Either way it
    is shown as unknown, never as a number."""
    from datetime import date as _date
    from . import session as session_mod
    seen = {e["label"]: e for e in events if e.get("kind") == "observation"}
    try:
        day = _date.fromisoformat(str(sig.get("trigger_at"))[:10])
    except ValueError:
        return [{"horizon": h, "state": "unknown"} for h in HORIZONS]
    last = _date.fromisoformat(today) if today else datetime.now(session_mod.ET).date()
    passed = 0
    probe = day
    while passed < max(HORIZONS) + 1:
        probe = session_mod.next_trading_day(probe)
        close_at = session_mod.regular_close(probe)
        if probe > last or (close_at and close_at > datetime.now(session_mod.ET) and probe == last):
            break
        passed += 1
    out = []
    for h in HORIZONS:
        label = "after {} candle{}".format(h, "" if h == 1 else "s")
        if label in seen:
            e = seen[label]
            out.append({"horizon": h, "state": "observed", "data_as_of": e["data_as_of"],
                        "price": e.get("price"), "change_pct": e.get("change_pct"),
                        "observed_at": e.get("observed_at")})
        elif passed >= h:
            out.append({"horizon": h, "state": "missing"})
        else:
            out.append({"horizon": h, "state": "pending"})
    return out


# ------------------------------------------------------------------ reading

def _decode(row: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(row)
    for key in ("conditions", "indicators", "params", "assumptions"):
        try:
            out[key] = json.loads(out.get(key) or ("[]" if key == "assumptions" else "{}"))
        except (TypeError, ValueError):
            out[key] = [] if key == "assumptions" else {}
    return out


def history(user_id: str, symbol: Optional[str] = None, status: Optional[str] = None,
            strategy: Optional[str] = None, direction: Optional[str] = None,
            limit: int = 200) -> List[Dict[str, Any]]:
    """One reader's signals, newest trigger first, each with its events.

    Scoped to the reader in the WHERE clause: an id or a symbol belonging to
    somebody else matches nothing."""
    sql = "SELECT * FROM signals WHERE user_id = ?"
    args: List[Any] = [user_id]
    if symbol:
        sql += " AND symbol = ?"
        args.append(symbol.upper())
    if strategy:
        sql += " AND strategy = ?"
        args.append(strategy)
    if direction in ("bull", "bear"):
        sql += " AND direction = ?"
        args.append(direction)
    sql += " ORDER BY trigger_at DESC, recorded_at DESC LIMIT ?"
    args.append(max(1, min(500, int(limit))))
    sigs = [_decode(r) for r in db.rows(sql, tuple(args))]
    if not sigs:
        return []
    marks = ",".join("?" for _ in sigs)
    events = db.rows(
        "SELECT * FROM signal_events WHERE user_id = ? AND signal_id IN (%s) "
        "ORDER BY data_as_of, observed_at" % marks, tuple([user_id] + [s["id"] for s in sigs]))
    by_sig: Dict[str, List[Dict[str, Any]]] = {}
    for e in events:
        by_sig.setdefault(e["signal_id"], []).append(dict(e))
    out = []
    for s in sigs:
        evs = by_sig.get(s["id"], [])
        terminal = next((e for e in evs if e["kind"] == "status" and e["label"] in TERMINAL), None)
        s["events"] = evs
        s["status"] = terminal["label"] if terminal else "unresolved"
        s["horizons"] = horizon_states(s, evs)
        if status and s["status"] != status:
            continue
        out.append(s)
    return out
