"""Reader-reported problems: stored here, emailed if an address is configured.

**Why this is not a GitHub issue link.** It was one, and it asked a reader who
had just found a bug to hold a GitHub account and sign in to it before they
could say so. Almost nobody will, and the ones who would are not the readers
whose problems go unheard.

**Stored before sent, and stored even when it cannot be sent.** The destination
is `FEEDBACK_EMAIL_TO`, an environment variable, and it is deliberately not in
this file: the repository is public. For any window where it is unset the choice
is between losing the reports and keeping them, so every report is written to
SQLite first and the email is a second step that is allowed to fail. `unsent()`
is what replays the backlog once an address exists.

**What the reader is told.** `stored` and `emailed` are returned separately and
the UI says which happened, because "thanks, we got it" over a message that went
nowhere is the same lie `app/auth/mailer.py` refuses to tell about verification
links. Stored-but-not-emailed is a success for the reader: the report is kept.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from . import db
from .auth import mailer

log = logging.getLogger(__name__)

# Never a literal. The repository is public and this is a personal address.
FEEDBACK_TO = (os.environ.get("FEEDBACK_EMAIL_TO") or "").strip()

# Where a report is meant to end up, whatever build the reader is running.
# Safe as a literal where the address above is not: it is the public name of
# the site, printed on the site.
CANONICAL_HOSTS = ("theopticterminal.com", "www.theopticterminal.com")

# The origins allowed to post a report from another origin, which is the same
# list as "where Optic runs when it is not production": a dev server and a
# tunnel preview. Deliberately not `*`. This endpoint takes anonymous text and
# its only defence is a per-address rate limit, and a wildcard would let any
# site on the web spend a visitor's address against that limit from a page the
# visitor thought was unrelated.
_DEV_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_DEV_SUFFIX = ".trycloudflare.com"


def cors_origin(origin: str) -> str:
    """Echo `origin` back when it may post a report cross-origin, else "".

    Parsed, not matched as a substring. `origin.endswith(_DEV_SUFFIX)` over the
    raw header is the standard hole in this check: it is also true of
    `https://evil.example/#.trycloudflare.com`, and userinfo puts an arbitrary
    prefix in front of the host that a reader of the string takes for the host.
    `urlparse(...).hostname` is the part the browser actually enforces.
    """
    text = (origin or "").strip()
    # A header long enough to be worth parsing carefully is not one of ours.
    if not text or len(text) > 200:
        return ""
    try:
        parsed = urlparse(text)
    except ValueError:
        return ""
    if parsed.scheme not in ("http", "https"):
        return ""
    # A real Origin is scheme://host[:port] and nothing more. Anything carrying
    # a path, query, fragment or userinfo is either not an Origin or is dressed
    # to read like one of the hosts below.
    if (parsed.path or parsed.query or parsed.fragment
            or parsed.username or parsed.password):
        return ""
    host = (parsed.hostname or "").lower()
    if not host:
        return ""
    if host in _DEV_HOSTS or host.endswith(_DEV_SUFFIX):
        return text
    return ""

# Long enough for a paragraph and a pasted error, short enough that the column
# is not an attack surface. The client counts down against the same number.
MAX_MESSAGE = 2000

# Context fields. Truncated rather than rejected: a report with an odd
# User-Agent is still a report, and failing the submission over it would lose
# the part that matters.
MAX_PAGE = 200
MAX_REPLY_TO = 254
MAX_USER_AGENT = 300

SUBJECT = "Optic Terminal problem report"


def configured() -> Dict[str, Any]:
    """Whether a report can be emailed, and if not, why not.

    Two independent reasons, reported separately because they have different
    fixes: no destination address, or no working mail backend.
    """
    if not FEEDBACK_TO:
        return {"available": False,
                "reason": "No FEEDBACK_EMAIL_TO is set, so reports are stored on the "
                          "server and not emailed."}
    post = mailer.available()
    if not post.get("available"):
        return {"available": False, "reason": post.get("reason") or "Mail is not configured."}
    return {"available": True}


def _clip(value: Any, limit: int) -> str:
    text = "" if value is None else str(value)
    return text.strip()[:limit]


def _body(row: Dict[str, Any]) -> str:
    lines = [row["message"], "", "---"]
    if row.get("page"):
        lines.append("Page: {}".format(row["page"]))
    if row.get("reply_to"):
        lines.append("Reply to: {}".format(row["reply_to"]))
    if row.get("user_agent"):
        lines.append("Browser: {}".format(row["user_agent"]))
    lines.append("Received: {}".format(row["created_at"]))
    lines.append("Report id: {}".format(row["id"]))
    return "\n".join(lines)


def store(message: str, page: str = "", reply_to: str = "",
          user_agent: str = "") -> Optional[Dict[str, Any]]:
    """Write one report. None when the message is empty after trimming."""
    text = _clip(message, MAX_MESSAGE)
    if not text:
        return None
    row = {
        "id": uuid.uuid4().hex,
        "message": text,
        "page": _clip(page, MAX_PAGE),
        "reply_to": _clip(reply_to, MAX_REPLY_TO),
        "user_agent": _clip(user_agent, MAX_USER_AGENT),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    with db.cursor(write=True) as conn:
        conn.execute(
            "INSERT INTO feedback (id,message,page,reply_to,user_agent,emailed,created_at) "
            "VALUES (?,?,?,?,?,0,?)",
            (row["id"], row["message"], row["page"], row["reply_to"],
             row["user_agent"], row["created_at"]))
    return row


def mark_emailed(report_id: str) -> None:
    with db.cursor(write=True) as conn:
        conn.execute("UPDATE feedback SET emailed = 1 WHERE id = ?", (report_id,))


def submit(message: str, page: str = "", reply_to: str = "",
           user_agent: str = "") -> Dict[str, Any]:
    """Store a report, then try to email it.

    Blocking on the mail send, like the auth routes: the caller runs it off the
    event loop. A send that fails leaves `emailed = 0` and the row intact, so
    nothing is lost and the backlog can go out later.
    """
    row = store(message, page, reply_to, user_agent)
    if row is None:
        return {"stored": False, "emailed": False,
                "reason": "The report was empty, so there was nothing to send."}

    status = configured()
    if not status["available"]:
        return {"stored": True, "emailed": False, "id": row["id"],
                "reason": status["reason"]}

    sent = mailer.send(FEEDBACK_TO, SUBJECT, _body(row))
    if sent:
        mark_emailed(row["id"])
        return {"stored": True, "emailed": True, "id": row["id"]}
    return {"stored": True, "emailed": False, "id": row["id"],
            "reason": "The report is stored. Sending it on failed, so it will be "
                      "sent with the next batch."}


# The lists `log` can draw: the Reports page's two tabs, and both at once.
STATUSES = ("open", "resolved", "all")


def log(limit: int = 50, include_resolved: bool = False,
        status: Optional[str] = None) -> Dict[str, Any]:
    """The newest reports and how many there are. What the operator reads.

    Distinct from `unsent()`, which is the email backlog and drops a report the
    moment it goes out. That is the wrong list for someone trying to find out
    what readers have been saying, and it was the only list there was: every
    report filed since this shipped is in SQLite with no route to it that is
    not a Python shell on the server.

    `status` picks the list: "open", the default, "resolved" or "all".
    `include_resolved` is the older way to ask for all of them and still works.
    Open reports come newest first. Resolved ones come most recently resolved
    first, so a report closed a moment ago heads that list rather than sitting
    wherever it was filed; the thirteen closed by one Resolve all share a
    stamp and fall back to newest first. `total` counts the list drawn from and
    `open` and `resolved` split the whole, so a page showing fifty can say how
    many there are, and both of its tabs can carry a count.

    Carries `configured()` so the answer to "why has none of this been emailed"
    arrives with the reports rather than having to be gone looking for.
    """
    if status not in STATUSES:
        status = "all" if include_resolved else "open"
    where = {"open": "WHERE resolved_at IS NULL ",
             "resolved": "WHERE resolved_at IS NOT NULL ",
             "all": ""}[status]
    order = ("ORDER BY resolved_at DESC, created_at DESC " if status == "resolved"
             else "ORDER BY created_at DESC ")
    with db.cursor() as conn:
        rows = conn.execute(
            "SELECT id,message,page,reply_to,user_agent,emailed,created_at,resolved_at "
            "FROM feedback " + where + order + "LIMIT ?",
            (limit,)).fetchall()
        counts = conn.execute(
            "SELECT COUNT(*) AS n, "
            "SUM(CASE WHEN resolved_at IS NULL THEN 1 ELSE 0 END) AS open "
            "FROM feedback").fetchone()
    everything = int(counts["n"] or 0)
    still_open = int(counts["open"] or 0)
    done = everything - still_open
    return {"reports": [dict(r) for r in rows],
            "total": {"open": still_open, "resolved": done, "all": everything}[status],
            "open": still_open, "resolved": done,
            "status": status, "include_resolved": status == "all",
            "delivery": configured()}


def resolve(report_id: str, resolved: bool = True) -> Optional[Dict[str, Any]]:
    """Mark one report resolved, or open again. None when there is no such report.

    An update, never a delete: the report is what a reader said, and resolving
    it is the operator's note that it has been dealt with, which can be wrong.
    """
    stamp = datetime.now(timezone.utc).isoformat() if resolved else None
    with db.cursor(write=True) as conn:
        cur = conn.execute("UPDATE feedback SET resolved_at = ? WHERE id = ?",
                           (stamp, report_id))
        if not cur.rowcount:
            return None
    return {"id": report_id, "resolved_at": stamp}


def resolve_open() -> Dict[str, Any]:
    """Mark every open report resolved: the page's Resolve all. The count, and the
    one timestamp they all share, so the page can say what it did."""
    stamp = datetime.now(timezone.utc).isoformat()
    with db.cursor(write=True) as conn:
        cur = conn.execute("UPDATE feedback SET resolved_at = ? WHERE resolved_at IS NULL",
                           (stamp,))
        count = cur.rowcount or 0
    return {"resolved": count, "resolved_at": stamp if count else None}


def unsent(limit: int = 200) -> List[Dict[str, Any]]:
    """Reports still waiting for an address, oldest first."""
    with db.cursor() as conn:
        rows = conn.execute(
            "SELECT id,message,page,reply_to,user_agent,created_at FROM feedback "
            "WHERE emailed = 0 ORDER BY created_at LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def flush(limit: int = 200) -> Dict[str, Any]:
    """Send the backlog. What to run once FEEDBACK_EMAIL_TO exists."""
    status = configured()
    if not status["available"]:
        return {"sent": 0, "pending": len(unsent(limit)), "reason": status["reason"]}
    sent = 0
    for row in unsent(limit):
        if mailer.send(FEEDBACK_TO, SUBJECT, _body(row)):
            mark_emailed(row["id"])
            sent += 1
        else:
            # Stop on the first failure rather than hammering a broken relay
            # through the whole backlog.
            break
    return {"sent": sent, "pending": len(unsent(limit))}
