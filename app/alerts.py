"""Alerts: a record of things the terminal noticed, and why.

**What this is and is not.** It is a rules engine plus a stored inbox. It is not
a delivery mechanism — nothing here sends an email or a text, and the reason is
worth stating rather than hiding behind a TODO. Delivery needs two things: a
credential (an SMTP password or a provider key, which belongs in .env and which
the operator has to create) and a server that is awake whenever the market is.
An alert that silently misses the move it was created for is worse than no
alert, because you would have stopped watching.

The second requirement used to be the hard one: this ran on a laptop behind a
temporary tunnel. It is on a hosting platform now, so `status()` reads where it
is running rather than asserting it, and the remaining blocker on the deployed
site is the credential and the `ALERT_ALWAYS_ON` acknowledgement.

So: rules are evaluated whenever the ledger scans, hits are written to the
database, and the UI shows them. When there is a host and a key, `deliver()` is
the single function that needs a body.

**On what counts as an alert.** Deliberately not "price crossed a number". That
is the easiest rule to write and the least useful thing this terminal knows.
A level is one input among the fifteen the composite already weighs. The rules
here fire on things that took work to compute: a scored setup, a position
closing, a pattern confirming with a measured base rate behind it.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .runtime import is_hosted

DB_PATH = os.path.join("data", "alerts.db")

# Kinds, and what each one is worth interrupting someone for. The `urgency` is
# not decoration — it is what a delivery layer would filter on, and writing it
# down now means the rules do not all arrive as equally important later.
KINDS: Dict[str, Dict[str, str]] = {
    "idea": {
        "label": "New trade idea",
        "urgency": "normal",
        "why": "A scan opened a position: the composite cleared the book's bar, "
               "it sized, and it has a stop and a target.",
    },
    "closed": {
        "label": "Position closed",
        "urgency": "high",
        "why": "A holding hit its stop, its target or its time stop. More urgent "
               "than a new idea because it already affected the record.",
    },
    "pattern": {
        "label": "Pattern confirmed",
        "urgency": "low",
        "why": "A chart pattern confirmed on a name, with its measured base rate "
               "attached so the alert says how often that pattern has worked.",
    },
    "risk": {
        "label": "Book risk",
        "urgency": "high",
        "why": "The book reached a cap. Position slots, or the portfolio risk "
               "budget. It will stop adding, which is worth knowing before you "
               "wonder why a scan found nothing.",
    },
}


def _conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init() -> None:
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at  TEXT NOT NULL,
                kind        TEXT NOT NULL,
                ticker      TEXT,
                title       TEXT NOT NULL,
                body        TEXT,
                payload     TEXT,
                seen        INTEGER NOT NULL DEFAULT 0,
                delivered   INTEGER NOT NULL DEFAULT 0,
                -- A stable key per logical event, so the same scan running twice
                -- does not produce the same alert twice. Without it a restart
                -- during a scan floods the inbox with duplicates.
                dedupe_key  TEXT UNIQUE
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS alerts_created ON alerts(created_at DESC)")


def raise_alert(kind: str, title: str, *, ticker: Optional[str] = None,
                body: str = "", payload: Optional[Dict[str, Any]] = None,
                dedupe_key: Optional[str] = None) -> bool:
    """Record one alert. Returns False if it was a duplicate."""
    if kind not in KINDS:
        return False
    init()
    key = dedupe_key or "%s:%s:%s" % (kind, ticker or "", title)
    now = datetime.now(timezone.utc).isoformat()
    try:
        with _conn() as conn:
            conn.execute(
                "INSERT INTO alerts (created_at, kind, ticker, title, body, payload, "
                "dedupe_key) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (now, kind, ticker, title, body,
                 json.dumps(payload or {}), key),
            )
        return True
    except sqlite3.IntegrityError:
        # The dedupe key already exists. Not an error — it is the mechanism
        # working.
        return False


def recent(limit: int = 50, unseen_only: bool = False) -> List[Dict[str, Any]]:
    init()
    sql = "SELECT * FROM alerts"
    if unseen_only:
        sql += " WHERE seen = 0"
    sql += " ORDER BY created_at DESC LIMIT ?"
    with _conn() as conn:
        rows = [dict(r) for r in conn.execute(sql, (limit,))]
    for r in rows:
        try:
            r["payload"] = json.loads(r["payload"] or "{}")
        except (TypeError, ValueError):
            r["payload"] = {}
        meta = KINDS.get(r["kind"], {})
        r["kind_label"] = meta.get("label", r["kind"])
        r["urgency"] = meta.get("urgency", "normal")
    return rows


def mark_seen(ids: Optional[List[int]] = None) -> int:
    init()
    with _conn() as conn:
        if ids:
            marks = ",".join("?" for _ in ids)
            cur = conn.execute("UPDATE alerts SET seen = 1 WHERE id IN (%s)" % marks, ids)
        else:
            cur = conn.execute("UPDATE alerts SET seen = 1 WHERE seen = 0")
        return cur.rowcount


def clear(before_id: Optional[int] = None) -> int:
    init()
    with _conn() as conn:
        if before_id:
            cur = conn.execute("DELETE FROM alerts WHERE id <= ?", (before_id,))
        else:
            cur = conn.execute("DELETE FROM alerts")
        return cur.rowcount


def unseen_count() -> int:
    init()
    with _conn() as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM alerts WHERE seen = 0").fetchone()
    return int(row["n"] if row else 0)


# ------------------------------------------------------------------- rules

def from_scan(result: Dict[str, Any]) -> int:
    """Turn one scan's output into alerts. Returns how many were new.

    Called by the tracker loop after every scan, so the inbox fills whether or
    not anyone had the page open — which is the whole point of recording them
    server-side rather than in the browser.
    """
    made = 0
    ran_at = result.get("ran_at") or datetime.now(timezone.utc).isoformat()

    for pos in result.get("opened_positions") or []:
        tkr = pos.get("ticker")
        instrument = pos.get("instrument", "shares")
        side = pos.get("direction", "")
        made += raise_alert(
            "idea",
            "%s. New %s %s" % (tkr, side, instrument),
            ticker=tkr,
            body=("Composite %s. Entry %s, stop %s, target %s. Book: %s."
                  % (pos.get("composite"), pos.get("entry_price"),
                     pos.get("stop"), pos.get("target"), pos.get("book"))),
            payload=pos,
            # One per position id, so re-running a scan cannot duplicate it.
            dedupe_key="idea:%s:%s:%s:%s" % (tkr, instrument, pos.get("book"),
                                             pos.get("entry_at") or ran_at),
        ) and 1 or 0

    for pos in result.get("closed_positions") or []:
        tkr = pos.get("ticker")
        made += raise_alert(
            "closed",
            "%s closed: %s" % (tkr, pos.get("exit_reason") or "exit"),
            ticker=tkr,
            body=_closed_body(pos),
            payload=pos,
            dedupe_key=_closed_key(pos, ran_at),
        ) and 1 or 0

    return made


def _closed_body(pos: Dict[str, Any]) -> str:
    """The sentence, built from the parts that exist.

    This was one %s-formatted string over three fields, and a position closed
    without a recorded P&L rendered "Exited at 0.05 for None. Held —." on the
    live site. Two faults in nine words: `None` interpolated as text, which
    reads as a broken template rather than as missing data, and an em dash in
    user-facing copy, which this codebase took a deliberate pass to remove.
    """
    parts = []
    price = pos.get("exit_price")
    if price is not None:
        parts.append("Exited at %s" % price)
    pnl = pos.get("pnl")
    if pnl is not None:
        parts.append("for %s" % pnl)
    held = pos.get("held")
    sentence = " ".join(parts)
    out = (sentence + ".") if sentence else ""
    if held:
        out = (out + " Held %s." % held).strip()
    # Absence stated rather than punctuated. An alert whose body is empty is
    # indistinguishable from the blank rows the view used to render.
    return out or "The ledger recorded the exit without a price or a duration."


def _closed_key(pos: Dict[str, Any], ran_at: str) -> str:
    """A key for the event, not for the moment it was noticed.

    It was "closed:{id}:{exit_at or ran_at}". A position closed without an id or
    an exit timestamp fell through to `ran_at`, which changes on every scan, so
    the same exit was inserted again each time the ledger ran. Measured on the
    live inbox: two identical BWMN rows out of nineteen alerts.

    The exit itself is what identifies it: this ticker, this instrument, out at
    this price for this reason. Two genuinely different exits of the same name at
    the same price for the same reason would collapse into one, and that is the
    right trade against duplicating every scan.
    """
    if pos.get("id") is not None:
        return "closed:%s" % pos["id"]
    if pos.get("exit_at"):
        return "closed:%s:%s" % (pos.get("ticker") or "", pos["exit_at"])
    return "closed:%s:%s:%s:%s" % (
        pos.get("ticker") or "", pos.get("instrument") or "",
        pos.get("exit_reason") or "", pos.get("exit_price"))


def from_capacity(book: str, capacity: Dict[str, Any], day: str) -> int:
    """Warn once a day when a book has stopped being able to add."""
    slots = capacity.get("position_slots_left")
    budget = capacity.get("risk_budget_left")
    if slots is not None and slots <= 0:
        return 1 if raise_alert(
            "risk", "%s book is full. No position slots left" % book,
            body="It will pass on every setup until something closes.",
            payload=capacity, dedupe_key="risk:slots:%s:%s" % (book, day)) else 0
    if budget is not None and budget <= 0:
        return 1 if raise_alert(
            "risk", "%s book has no risk budget left" % book,
            body="Deployed risk has reached the portfolio cap.",
            payload=capacity, dedupe_key="risk:budget:%s:%s" % (book, day)) else 0
    return 0


# ---------------------------------------------------------------- delivery

def delivery_status() -> Dict[str, Any]:
    """What delivery would need, checked rather than assumed.

    Reported to the UI so the alerts panel can say precisely what is missing
    instead of a vague "not configured" — the two blockers are different in kind
    and only one of them is a credential.
    """
    smtp = bool(os.environ.get("ALERT_SMTP_URL"))
    api = bool(os.environ.get("ALERT_EMAIL_KEY"))
    to = bool(os.environ.get("ALERT_EMAIL_TO"))
    always_on = os.environ.get("ALERT_ALWAYS_ON", "").strip().lower() == "true"
    return {
        "enabled": (smtp or api) and to and always_on,
        "has_credential": smtp or api,
        "has_recipient": to,
        "declared_always_on": always_on,
        "blockers": [b for b in [
            None if (smtp or api) else
            "No sending credential. Set ALERT_SMTP_URL (an SMTP app password) or "
            "ALERT_EMAIL_KEY (Resend/Postmark) in .env.",
            None if to else "No recipient. Set ALERT_EMAIL_TO in .env.",
            None if always_on else (
                # Where this is running is read, not asserted. The original text
                # said "it currently runs on a laptop behind a temporary tunnel",
                # which was true when it was written and is now wrong on the
                # deployed site: it tells the operator to wait for a deployment
                # that already happened.
                "The server is not declared always-on. Alerts fire only while "
                "this process is running. This one is on a hosting platform, so "
                "it stays up between scans: set ALERT_ALWAYS_ON=true to confirm "
                "that and let delivery enable itself."
                if is_hosted() else
                "The server is not declared always-on. Alerts fire only while "
                "this process is running, and this one is a local process that "
                "stops when you close it, so anything that happens while it is "
                "down is missed silently. Set ALERT_ALWAYS_ON=true once it is "
                "deployed somewhere that stays up."
            ),
        ] if b],
    }


def deliver(alert: Dict[str, Any]) -> bool:
    """Send one alert. Deliberately unimplemented.

    The single function a delivery layer needs. It is left as a refusal rather
    than a half-working SMTP call because a half-working one is the dangerous
    version: it would appear to work in testing, then drop messages whenever the
    process was down, and the failure would be invisible exactly when it
    mattered. On a hosting platform that is a restart or a redeploy rather than
    a laptop lid, which is a shorter window and not a smaller problem.
    """
    return False
