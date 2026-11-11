"""The owner's three signals, recorded from day one (2026-11-09): does a reader open a stock from Home, ask
Milo a question, and come back within a week.

One table, `usage_event` (migration 21 in app/db.py), one row per event:

* ``home_stock_open``: a company opened from Home. Sent by the page (POST /api/usage) when the route moves
  from Home to a company's page, because only the page knows where a click came from.
* ``milo_question``: a question to Milo. Written here by the chat route itself, after the allowance has let
  the question through, never by the page: a page could send one without asking anything.
* ``visit``: the first visit of a UTC calendar day per reader. The page sends one on every load; the server
  keeps the first of the day and drops the rest. "Came back within a week" is counted from these rows.

Who: a signed-in reader is their account id (``signed_in``). A signed-out reader is a random id their own
browser made and keeps (``visitor``, ``optic.visitor.v1``), so a return can be counted without an account.
It names no one and is not shared with anyone; the privacy page should say it exists (the owner's and his
counsel's text, proposed in the pull request, not written here).

What is never in a row: the question's text, an IP address, an email address. The IP is used only in memory,
for the burst limit below, and is not logged.

Kept 400 days (one year and a week, so a year-on-year return can be counted), the figure the Metrics records
already use (app/db.py METRICS_KEEP_DAYS); deleted by the accounts sweep, and with the account on the
delete-account path (the foreign key cascades).

``OPTIC_USAGE_CAPTURE=off`` stops recording; /api/health reports which.
"""

from __future__ import annotations

import os
import re
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Any, Deque, Dict, List, Optional, Tuple

from . import db

EVENTS = ("home_stock_open", "milo_question", "visit")
# What the page may send. A Milo question is written by the chat route alone.
CLIENT_EVENTS = ("home_stock_open", "visit")
LEVELS = ("beginner", "intermediate", "advanced")
MAX_BODY = 1024                       # bytes; the largest real event is under 200
VISITOR = re.compile(r"^v-[0-9a-f]{32}$")
SYMBOL = re.compile(r"^[A-Z0-9.^=-]{1,12}$")
SCREEN = re.compile(r"^[a-z][a-z0-9_]{0,23}$")
KEEP_DAYS = 400

# Burst limits, per reader and per address, in memory only. A reader who clears their browser gets a new
# visitor id, so the per-reader limit alone can be walked around; the address limit is the backstop.
ACTOR_LIMIT = (20, 60.0)              # events per window seconds
IP_LIMIT = (60, 60.0)


def capture_on() -> bool:
    return (os.environ.get("OPTIC_USAGE_CAPTURE") or "on").strip().lower() not in ("off", "0", "false", "no")


def utc_day(ts: str) -> str:
    return ts[:10]


# ------------------------------------------------------------------ the burst limits

class _Window:
    def __init__(self, limit: Tuple[int, float]) -> None:
        self.limit, self.span = limit
        self.hits: Dict[str, Deque[float]] = defaultdict(deque)
        self.lock = threading.Lock()

    def allow(self, key: str, now: Optional[float] = None) -> bool:
        now = time.monotonic() if now is None else now
        with self.lock:
            q = self.hits[key]
            while q and now - q[0] > self.span:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(now)
            if len(self.hits) > 50000:          # never grows without end: the oldest keys go first
                for k in list(self.hits)[:10000]:
                    self.hits.pop(k, None)
            return True

    def reset(self) -> None:
        with self.lock:
            self.hits.clear()


ACTORS = _Window(ACTOR_LIMIT)
ADDRESSES = _Window(IP_LIMIT)


def reset_limits() -> None:
    ACTORS.reset()
    ADDRESSES.reset()


# ------------------------------------------------------------------ recording

def actor_for(user: Optional[Dict[str, Any]], visitor: Optional[str]) -> Optional[Tuple[str, str, Optional[str]]]:
    """(actor_kind, actor_ref, user_id), or None when the request names no one we can count."""
    if user and user.get("id"):
        return ("signed_in", str(user["id"]), str(user["id"]))
    if visitor and VISITOR.match(visitor):
        return ("visitor", visitor, None)
    return None


def record(event: str, actor: Tuple[str, str, Optional[str]], *, symbol: Optional[str] = None,
           source_screen: Optional[str] = None, level: Optional[str] = None,
           now: Optional[datetime] = None) -> bool:
    """Write one event. A visit is kept once per reader per UTC day. Never raises: a signal is not worth
    failing a page or a question over. True when a row was written."""
    if event not in EVENTS or not capture_on():
        return False
    at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    kind, ref, uid = actor
    sym = symbol.upper() if isinstance(symbol, str) and SYMBOL.match(symbol.upper()) else None
    screen = source_screen if isinstance(source_screen, str) and SCREEN.match(source_screen) else None
    lv = level if level in LEVELS else None
    try:
        if event == "visit":
            seen = db.row("SELECT 1 AS x FROM usage_event WHERE event = 'visit' AND actor_ref = ? "
                          "AND substr(occurred_at, 1, 10) = ?", (ref, utc_day(at)))
            if seen:
                return False
        db.execute("INSERT INTO usage_event (occurred_at, actor_kind, actor_ref, user_id, event, symbol, "
                   "source_screen, level) VALUES (?,?,?,?,?,?,?,?)", (at, kind, ref, uid, event, sym, screen, lv))
        return True
    except Exception:                                             # noqa: BLE001
        return False


# ------------------------------------------------------------------ reading (the owner's raw counts)

def _since(now: datetime, days: int) -> str:
    return (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def returned_within_week(rows: List[Dict[str, Any]], now: Optional[datetime] = None) -> Tuple[int, int]:
    """(of the readers whose first visit is at least seven days old, so they have had the whole week to come
    back, how many came back within seven days of it; how many such readers there are). From visit rows.

    Both numbers are counted over the same group. Counting "came back" over every reader showed the owner
    "2 of 0" on 2026-11-10: two readers had returned on day two, and neither was a week old yet."""
    days: Dict[str, List[str]] = defaultdict(list)
    for r in rows:
        days[r["actor_ref"]].append(utc_day(r["occurred_at"]))
    came_back = eligible = 0
    today = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).date()
    for ds in days.values():
        first = datetime.strptime(min(ds), "%Y-%m-%d").date()
        if (today - first).days < 7:
            continue
        eligible += 1
        later = [datetime.strptime(d, "%Y-%m-%d").date() for d in ds]
        if any(0 < (d - first).days <= 7 for d in later):
            came_back += 1
    return came_back, eligible


def signals(now: Optional[datetime] = None) -> Dict[str, Any]:
    """Raw counts of the three signals: today, the last 7 days, the last 30 days and everything kept."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    windows = {"today": now.strftime("%Y-%m-%dT00:00:00Z"), "week": _since(now, 7), "month": _since(now, 30), "all": ""}
    out: Dict[str, Any] = {"capture": capture_on(), "keep_days": KEEP_DAYS, "windows": {}}
    try:
        first = db.row("SELECT MIN(occurred_at) AS at FROM usage_event")
        out["since"] = (first or {}).get("at")
        for name, since in windows.items():
            w: Dict[str, Any] = {}
            for ev in ("home_stock_open", "milo_question"):
                r = db.row("SELECT COUNT(*) AS n, COUNT(DISTINCT actor_ref) AS who FROM usage_event "
                           "WHERE event = ? AND occurred_at >= ?", (ev, since))
                w[ev] = {"events": int(r["n"] or 0), "readers": int(r["who"] or 0)}
            r = db.row("SELECT COUNT(*) AS n, COUNT(DISTINCT actor_ref) AS who, "
                       "SUM(CASE WHEN actor_kind = 'visitor' THEN 1 ELSE 0 END) AS guests FROM usage_event "
                       "WHERE event = 'visit' AND occurred_at >= ?", (since,))
            w["visit"] = {"days": int(r["n"] or 0), "readers": int(r["who"] or 0), "signed_out_days": int(r["guests"] or 0)}
            out["windows"][name] = w
        rows = db.rows("SELECT actor_ref, occurred_at FROM usage_event WHERE event = 'visit' ORDER BY occurred_at")
        back, eligible = returned_within_week(rows, now)
        out["returned_within_week"] = {"readers": back, "had_a_full_week": eligible}
        out["available"] = True
    except Exception as exc:                                      # noqa: BLE001
        out = {"available": False, "reason": "The usage records could not be read ({}).".format(type(exc).__name__)}
    return out


def sweep(now: Optional[datetime] = None) -> int:
    """Delete events older than KEEP_DAYS. Called by app/db.py sweep(), which the server runs on its timer."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return db.execute("DELETE FROM usage_event WHERE occurred_at < ?", (_since(now, KEEP_DAYS),))
