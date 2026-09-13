"""Evaluate stored watches server-side, so a hit is waiting at the next sign-in.

**The gap this closes.** `app/analytics/watches.py` is a stateless evaluator and
`/api/watches/check` is driven by the browser: it checks the symbols the page is
looking at, while the page is open. That makes the one thing anybody actually
wants from an alert — being told about a move you were *not* watching — the one
thing it could not do. This runs the same evaluator against the same panels on a
schedule and writes what fired to `watch_hits`, keyed to the account.

**Still not a push, and the copy says so.** Nothing here can reach a device or a
mailbox: no token store, no verified sender. What it promises is "this will be
here when you come back", which is a promise it can keep. An alert that silently
misses its move is worse than no alert, and that is the same argument
`app/alerts.py` makes about delivery.

**One symbol, one snapshot.** A snapshot is the expensive part (it builds the
chain, the greeks and the technicals), so watches are grouped by symbol and each
symbol is built once however many accounts are watching it. With ten accounts
watching NVDA that is one snapshot rather than ten.

**One hit per watch per UTC day.** Almost every condition reports a STATE rather
than a transition: "RSI above 50" stays true for as long as it is true, so a
runner on a fifteen-minute loop would write the same sentence ninety-six times.
The unique index on (user_id, dedupe_key) enforces it rather than this module
remembering to, because a restart mid-run is exactly when a caller's memory is
wrong.

**A symbol that fails costs its own symbol.** One bad ticker in a hundred must
not stop the other ninety-nine, so each is tried on its own and the failures are
counted and reported rather than raised.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional

from . import db
from .analytics import watches as watches_mod

log = logging.getLogger("optic.watch_runner")

# A ceiling on one pass, so a runaway account cannot turn a scheduled job into
# an unbounded one. Watches are capped per account already; this caps the fleet.
MAX_SYMBOLS_PER_RUN = 60


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _dedupe_key(watch_id: str, when: datetime) -> str:
    """One hit per watch per day.

    The date is part of the key rather than a lookup, so the uniqueness is a
    property of the row and survives two runners overlapping.
    """
    return "%s:%s" % (watch_id, when.date().isoformat())


def due_watches() -> List[Dict[str, Any]]:
    """Every active watch across every account, with its owner."""
    return db.rows(
        "SELECT w.id, w.user_id, w.symbol, w.kind, w.params, w.note "
        "FROM watches w WHERE w.active = 1 ORDER BY w.symbol, w.created_at")


def group_by_symbol(rows: Iterable[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row["symbol"]).upper(), []).append(row)
    return grouped


def _params(row: Dict[str, Any]) -> Dict[str, Any]:
    try:
        value = json.loads(row.get("params") or "{}")
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _title(symbol: str, result: Dict[str, Any]) -> str:
    return "%s: %s" % (symbol, result.get("label") or result.get("kind") or "watch")


def _body(result: Dict[str, Any], note: Optional[str]) -> str:
    """The evidence first, the reader's own note after it.

    Built from the parts that exist rather than a format string over maybe-None
    values: "Exited at 0.05 for None" shipped once from exactly that mistake.
    """
    parts = []
    if result.get("evidence"):
        parts.append(str(result["evidence"]))
    if note:
        parts.append('Your note: "%s"' % str(note).strip())
    return ". ".join(parts)


def record_hit(row: Dict[str, Any], result: Dict[str, Any],
               when: Optional[datetime] = None) -> bool:
    """Write one hit. False means the dedupe index refused it, which is normal."""
    when = when or _now()
    symbol = str(row["symbol"]).upper()
    try:
        db.execute(
            "INSERT INTO watch_hits (id, user_id, watch_id, symbol, kind, title, "
            "body, created_at, dedupe_key) VALUES (?,?,?,?,?,?,?,?,?)",
            (uuid.uuid4().hex, row["user_id"], row["id"], symbol, row["kind"],
             _title(symbol, result), _body(result, row.get("note")),
             when.isoformat(), _dedupe_key(row["id"], when)))
    except Exception as exc:                      # the unique index, normally
        if "UNIQUE" not in str(exc).upper():
            log.warning("watch hit not stored: %s", exc)
            return False
        return False
    # The watch remembers too, which is what the browser-side check reads so it
    # does not re-announce something already sitting in the inbox.
    db.execute("UPDATE watches SET last_met_at = ?, last_evidence = ? WHERE id = ?",
               (when.isoformat(), str(result.get("evidence") or ""), row["id"]))
    return True


def run_once(snapshot: Callable[[str], Dict[str, Any]],
             limit: int = MAX_SYMBOLS_PER_RUN) -> Dict[str, Any]:
    """Evaluate every stored watch and record what fired.

    `snapshot` takes a symbol and returns the payload `watches.check` reads. It
    is injected rather than imported so this module does not depend on the app,
    and so a test can drive it without the network.
    """
    when = _now()
    grouped = group_by_symbol(due_watches())
    symbols = sorted(grouped)[:limit]
    checked = fired = 0
    failed: List[str] = []

    for symbol in symbols:
        rows = grouped[symbol]
        try:
            payload = snapshot(symbol)
        except Exception as exc:
            # One bad ticker must not end the pass. Named in the result, because
            # a run that quietly skipped a symbol is a run whose empty inbox
            # means nothing.
            log.warning("watch snapshot failed for %s: %s", symbol, exc)
            failed.append(symbol)
            continue
        specs = [{"id": r["id"], "kind": r["kind"], "params": _params(r)} for r in rows]
        results = watches_mod.check(payload, specs)
        by_id = {r.get("id"): r for r in results}
        for row in rows:
            checked += 1
            result = by_id.get(row["id"])
            if result and result.get("met") and record_hit(row, result, when):
                fired += 1

    return {
        "ran_at": when.isoformat(),
        "symbols": len(symbols),
        "skipped_symbols": max(0, len(grouped) - len(symbols)),
        "watches_checked": checked,
        "hits": fired,
        "failed_symbols": failed,
    }


def hits_for(user_id: str, limit: int = 50,
             unseen_only: bool = False) -> List[Dict[str, Any]]:
    sql = ("SELECT id, watch_id, symbol, kind, title, body, created_at, seen "
           "FROM watch_hits WHERE user_id = ?")
    if unseen_only:
        sql += " AND seen = 0"
    sql += " ORDER BY created_at DESC LIMIT ?"
    return [dict(r) for r in db.rows(sql, (user_id, max(1, min(200, limit))))]


def unseen_count(user_id: str) -> int:
    row = db.row("SELECT COUNT(*) AS n FROM watch_hits WHERE user_id = ? AND seen = 0",
                 (user_id,))
    return int((row or {}).get("n") or 0)


def mark_seen(user_id: str, ids: Optional[List[str]] = None) -> int:
    """Scoped to the owner in the WHERE clause, not checked beforehand.

    An id belonging to somebody else simply matches no row. Reading the row
    first and comparing user_id would be the same answer with a race in it.
    """
    if ids:
        marks = ",".join("?" for _ in ids)
        return db.execute(
            "UPDATE watch_hits SET seen = 1 WHERE user_id = ? AND id IN (%s)" % marks,
            tuple([user_id] + list(ids)))
    return db.execute("UPDATE watch_hits SET seen = 1 WHERE user_id = ?", (user_id,))
