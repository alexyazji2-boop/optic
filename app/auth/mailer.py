"""Sending the two emails this app has to send, and being honest when it cannot.

**Two backends.** SMTP when `SMTP_HOST` is set, and the log otherwise. SMTP
rather than one provider's HTTP API because every provider worth using speaks it
(Resend, SES, Postmark, Mailgun, Fastmail, a Gmail app password), so the operator
picks one without this file changing.

**Why the log backend is not a stub.** With no mail configured, signup and
password reset still have to *work* — someone has to be able to run this locally
and click the link. So the link is written to the server log at INFO and
`sent` comes back False. The API passes that False through and the UI says the
message could not be sent and shows what to do about it, rather than claiming
"check your inbox" for a message that was never sent. `app/alerts.py` makes the
same argument for the same reason: an alert that silently misses is worse than
no alert.

Nothing here retries. A queue with retries is a real piece of infrastructure and
pretending otherwise with a `while` loop in a request handler would hold the
response open while it failed.
"""

from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr
from typing import Any, Dict, Optional

log = logging.getLogger("optic.mail")

SMTP_HOST = (os.environ.get("SMTP_HOST") or "").strip()
SMTP_PORT = int(os.environ.get("SMTP_PORT") or "587")
SMTP_USERNAME = (os.environ.get("SMTP_USERNAME") or "").strip()
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD") or ""
EMAIL_FROM = (os.environ.get("EMAIL_FROM") or "").strip()
EMAIL_FROM_NAME = (os.environ.get("EMAIL_FROM_NAME") or "Optic Terminal").strip()

# 10 seconds. A signup request waits on this, so an unreachable mail host has to
# fail fast rather than hold the browser for the platform's whole request budget.
SMTP_TIMEOUT = float(os.environ.get("SMTP_TIMEOUT") or "10")


def available() -> Dict[str, Any]:
    if not SMTP_HOST:
        return {"available": False, "backend": "log",
                "reason": "No SMTP_HOST is set, so verification and reset links are "
                          "written to the server log instead of being emailed."}
    if not EMAIL_FROM:
        return {"available": False, "backend": "log",
                "reason": "SMTP_HOST is set but EMAIL_FROM is not, and a message with "
                          "no From address is rejected by every relay."}
    return {"available": True, "backend": "smtp", "host": SMTP_HOST}


def _send_smtp(message: EmailMessage) -> None:
    """Implicit TLS on 465, STARTTLS everywhere else.

    Port 465 is SMTPS: the connection is encrypted from the first byte and
    issuing STARTTLS on it is a protocol error. 587 is submission, which opens in
    the clear and upgrades. Getting these the wrong way round fails at connect
    time with an error that mentions neither port nor TLS."""
    context = ssl.create_default_context()
    if SMTP_PORT == 465:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT,
                              context=context) as client:
            if SMTP_USERNAME:
                client.login(SMTP_USERNAME, SMTP_PASSWORD)
            client.send_message(message)
        return
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT) as client:
        client.ehlo()
        if client.has_extn("starttls"):
            client.starttls(context=context)
            client.ehlo()
        if SMTP_USERNAME:
            client.login(SMTP_USERNAME, SMTP_PASSWORD)
        client.send_message(message)


def send(to: str, subject: str, body: str, link: Optional[str] = None) -> bool:
    """True only if a relay accepted the message.

    Blocking. Callers run it off the event loop; see the routes."""
    status = available()
    if not status["available"]:
        # The link, not the whole body: it is the only part anyone needs from the
        # log, and a wall of copy makes it harder to find.
        log.info("[mail:log] to=%s subject=%s%s", to, subject,
                 ("\n           link=" + link) if link else "")
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((EMAIL_FROM_NAME, EMAIL_FROM))
    message["To"] = to
    message.set_content(body)
    try:
        _send_smtp(message)
        return True
    except (smtplib.SMTPException, OSError, ssl.SSLError) as exc:
        # The address is logged, the error is logged, the token never is.
        log.warning("mail send failed to=%s subject=%s error=%s", to, subject, exc)
        return False


# ------------------------------------------------------------------ templates
#
# Plain text on purpose. An HTML email needs a second copy of the same words
# kept in sync, renders differently in every client, and buys nothing here: both
# of these messages are one sentence and one link.


def verification_email(name: str, link: str) -> Dict[str, str]:
    greeting = "Hi {},".format(name) if name else "Hi,"
    return {
        "subject": "Verify your email for Optic Terminal",
        "body": "{}\n\nConfirm this address to finish setting up your Optic Terminal "
                "account:\n\n{}\n\nThe link works for 24 hours. If you did not create "
                "an account, you can ignore this message and nothing will "
                "happen.\n\nOptic Terminal\n".format(greeting, link),
    }


def reset_email(name: str, link: str) -> Dict[str, str]:
    greeting = "Hi {},".format(name) if name else "Hi,"
    return {
        "subject": "Reset your Optic Terminal password",
        "body": "{}\n\nUse this link to choose a new password:\n\n{}\n\nIt works once "
                "and expires in 15 minutes. Signing in again on every device will be "
                "needed afterwards.\n\nIf you did not ask for this, someone entered "
                "your address on the sign-in page. No change has been made and you can "
                "ignore this message.\n\nOptic Terminal\n".format(greeting, link),
    }


def password_changed_email(name: str, when: str) -> Dict[str, str]:
    """Sent after a password changes. Not a courtesy: it is the one notification
    that tells someone their account was taken over while they still have the
    mailbox to do something about it."""
    greeting = "Hi {},".format(name) if name else "Hi,"
    return {
        "subject": "Your Optic Terminal password was changed",
        "body": "{}\n\nThe password on your Optic Terminal account was changed at {} "
                "UTC, and every other signed-in device was signed out.\n\nIf that was "
                "not you, reset your password now and check which sign-in methods are "
                "connected under Settings, Security.\n\nOptic "
                "Terminal\n".format(greeting, when),
    }
