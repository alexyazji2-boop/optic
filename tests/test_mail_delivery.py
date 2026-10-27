"""What the mailer hands a relay once SMTP is configured, against a fake relay.

Production has no SMTP_HOST (checked 26 October 2026: /api/auth/providers says
backend "log"), so nothing here has met a real relay. These pin what the owner
can check after setting one up: the message's headers and link, TLS on each
port, and a refused relay reported as unsent with no token in the log. The
token's expiry and single use are in tests/test_auth_tokens.py."""

from __future__ import annotations

import logging
import smtplib

import pytest

from app.auth import mailer

LINK = "https://theopticterminal.com/?reset=SECRET-TOKEN"


class _Relay:
    seen = []

    def __init__(self, host, port, timeout=None, context=None):
        self.calls = [("connect", host, port, "ssl" if context is not None else "plain")]
        _Relay.seen.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def ehlo(self):
        self.calls.append(("ehlo",))

    def has_extn(self, name):
        return name == "starttls"

    def starttls(self, context=None):
        self.calls.append(("starttls",))

    def login(self, user, password):
        self.calls.append(("login", user))

    def send_message(self, message):
        self.calls.append(("send",))
        self.message = message


@pytest.fixture
def relay(monkeypatch):
    _Relay.seen = []
    monkeypatch.setattr(mailer, "SMTP_HOST", "smtp.example.test")
    monkeypatch.setattr(mailer, "EMAIL_FROM", "noreply@theopticterminal.com")
    monkeypatch.setattr(mailer, "SMTP_USERNAME", "apikey")
    monkeypatch.setattr(mailer.smtplib, "SMTP", _Relay)
    monkeypatch.setattr(mailer.smtplib, "SMTP_SSL", _Relay)
    return _Relay


def test_a_reset_email_reaches_the_relay_with_its_link_over_starttls(relay, monkeypatch):
    monkeypatch.setattr(mailer, "SMTP_PORT", 587)
    mail = mailer.reset_email("Ada", LINK)
    assert mailer.available()["backend"] == "smtp"
    assert mailer.send("ada@example.test", mail["subject"], mail["body"], LINK) is True
    r = relay.seen[0]
    assert [c[0] for c in r.calls] == ["connect", "ehlo", "starttls", "ehlo", "login", "send"]
    m = r.message
    assert m["To"] == "ada@example.test" and m["From"] == "Optic Terminal <noreply@theopticterminal.com>"
    assert m["Subject"] == "Reset your Optic Terminal password"
    assert LINK in m.get_content() and "works once" in m.get_content() and "15 minutes" in m.get_content()


def test_port_465_is_tls_from_the_first_byte(relay, monkeypatch):
    monkeypatch.setattr(mailer, "SMTP_PORT", 465)
    assert mailer.send("ada@example.test", "s", "b") is True
    calls = relay.seen[0].calls
    assert calls[0][3] == "ssl" and ("starttls",) not in calls


def test_a_refused_relay_is_unsent_and_the_token_is_not_logged(relay, monkeypatch):
    def refuse(self, message):
        raise smtplib.SMTPRecipientsRefused({"ada@example.test": (550, b"no")})
    monkeypatch.setattr(_Relay, "send_message", refuse)
    records = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())
    handler = Capture()
    mailer.log.addHandler(handler)
    try:
        assert mailer.send("ada@example.test", "Reset", "body " + LINK, LINK) is False
    finally:
        mailer.log.removeHandler(handler)
    text = "\n".join(records)
    assert "SECRET-TOKEN" not in text and "mail send failed" in text


def test_a_relay_without_a_from_address_is_not_used(monkeypatch):
    monkeypatch.setattr(mailer, "SMTP_HOST", "smtp.example.test")
    monkeypatch.setattr(mailer, "EMAIL_FROM", "")
    assert mailer.available() == {"available": False, "backend": "log",
                                  "reason": mailer.available()["reason"]}
    assert "EMAIL_FROM" in mailer.available()["reason"]
