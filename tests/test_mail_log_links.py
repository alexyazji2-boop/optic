"""A reset link in the log is a sign-in for whoever can read the log.

With no relay configured the mailer writes the link to the server log, which
is how an address gets confirmed on a deployment without email (see
tests/test_log_config.py for the outage that came from that line going
missing). On the hosted site that also put every reader's reset link, token
included, in a log the platform keeps for up to 90 days. The readiness audit of
2026-10-23 (P0, F-42) found it.

So on a host the link is logged only for an ADMIN_EMAILS address: the owner
still has a way to confirm their own address, and nobody else's account can be
opened from the log. Locally nothing changes. MAIL_LOG_LINKS overrides both.
"""
from __future__ import annotations

import logging

import pytest

from app.auth import mailer

LINK = "https://example.test/?reset=SECRET-TOKEN"


def _logged(monkeypatch, to):
    monkeypatch.setattr(mailer, "SMTP_HOST", "")
    records = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    handler = Capture()
    mailer.log.addHandler(handler)
    try:
        assert mailer.send(to, "Reset your password", "body", LINK) is False
    finally:
        mailer.log.removeHandler(handler)
    return "\n".join(records)


@pytest.fixture
def hosted(monkeypatch):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    monkeypatch.setenv("ADMIN_EMAILS", "owner@example.test")
    monkeypatch.delenv("MAIL_LOG_LINKS", raising=False)


def test_on_a_host_a_readers_link_and_address_stay_out_of_the_log(monkeypatch, hosted):
    text = _logged(monkeypatch, "reader@example.test")
    assert "[mail:log]" in text, "the attempt is still recorded"
    assert "SECRET-TOKEN" not in text
    assert "reader@example.test" not in text
    assert "r***@example.test" in text


def test_on_a_host_the_owners_link_is_still_logged(monkeypatch, hosted):
    """Without a relay this is the only way the owner can confirm their address,
    and `is_admin` requires it confirmed."""
    text = _logged(monkeypatch, "Owner@Example.test")
    assert LINK in text


def test_locally_every_link_is_logged(monkeypatch):
    for var in ("RAILWAY_ENVIRONMENT", "RAILWAY_GIT_COMMIT_SHA", "RENDER", "FLY_APP_NAME", "MAIL_LOG_LINKS"):
        monkeypatch.delenv(var, raising=False)
    assert LINK in _logged(monkeypatch, "reader@example.test")


@pytest.mark.parametrize("value,expected", [("true", True), ("false", False)])
def test_the_override_wins_either_way(monkeypatch, hosted, value, expected):
    monkeypatch.setenv("MAIL_LOG_LINKS", value)
    assert (LINK in _logged(monkeypatch, "reader@example.test")) is expected


def test_the_reason_tells_a_hosted_reader_nothing_was_sent(monkeypatch, hosted):
    monkeypatch.setattr(mailer, "SMTP_HOST", "")
    reason = mailer.available()["reason"]
    assert "server log" not in reason
    assert "cannot be sent" in reason
