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

from . import db
from .auth import mailer

log = logging.getLogger(__name__)

# Never a literal. The repository is public and this is a personal address.
FEEDBACK_TO = (os.environ.get("FEEDBACK_EMAIL_TO") or "").strip()

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
