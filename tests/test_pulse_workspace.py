"""A personal API key, and what Pulse says when one is refused.

Production refused every chat and every brief with the same 400, while
`/api/health` reported `enabled: true` and `credential_source:
ANTHROPIC_API_KEY` -- which proves a key exists, and nothing about whether
Anthropic will take it:

    This API key is not scoped to a workspace, so this request must include the
    anthropic-workspace-id header with the ID of the workspace to use. Add the
    header, or use an API key that is scoped to a workspace.

The reader was then told "The assistant failed with an unexpected error
(BadRequestError). Try again." -- advice that can never work, because the same
request gets the same 400 every time.
"""
from __future__ import annotations

import pytest

from app import ai

# Verbatim from the production log, so the matcher is tested against what the
# API actually says rather than what someone expects it to say.
PRODUCTION_400 = (
    "Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', "
    "'message': 'This API key is not scoped to a workspace, so this request must "
    "include the anthropic-workspace-id header with the ID of the workspace to use. "
    "Add the header, or use an API key that is scoped to a workspace.'}, "
    "'request_id': None}")


class BadRequestError(Exception):
    """Shaped like the SDK's: the name and `status_code` are what is read."""
    status_code = 400


class InternalServerError(Exception):
    status_code = 500


# ----------------------------------------------------------------- the header


def _headers(monkeypatch, workspace):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    if workspace is None:
        monkeypatch.delenv("ANTHROPIC_WORKSPACE_ID", raising=False)
    else:
        monkeypatch.setenv("ANTHROPIC_WORKSPACE_ID", workspace)
    client = ai._client()
    assert client is not None
    return client


def test_a_configured_workspace_is_sent_on_every_request(monkeypatch):
    client = _headers(monkeypatch, "wrkspc_01abc")
    assert client.default_headers.get("anthropic-workspace-id") == "wrkspc_01abc"


def test_no_workspace_means_no_header(monkeypatch):
    """A workspace-scoped key needs nothing, and an empty header value is not
    nothing -- it is a request naming a workspace that does not exist."""
    client = _headers(monkeypatch, None)
    assert "anthropic-workspace-id" not in client.default_headers


def test_a_blank_setting_is_treated_as_unset(monkeypatch):
    """A variable saved with only a space in it, which a dashboard paste will
    produce, must not send that space."""
    client = _headers(monkeypatch, "   ")
    assert "anthropic-workspace-id" not in client.default_headers


def test_the_retry_budget_survives_the_change(monkeypatch):
    """Five attempts is what absorbs a capacity wobble; the header must not
    have cost it."""
    assert _headers(monkeypatch, "wrkspc_01abc").max_retries == 5


# ------------------------------------------------------------------ the copy


def test_the_production_error_is_recognised():
    text = ai._human_error(BadRequestError(PRODUCTION_400))
    assert "workspace" in text
    assert "unexpected error" not in text


def test_it_does_not_tell_the_reader_to_retry():
    """The whole complaint. The same request gets the same 400 every time."""
    text = ai._human_error(BadRequestError(PRODUCTION_400)).lower()
    assert "try again" not in text
    assert "will not help" in text


def test_the_workspace_case_wins_over_the_generic_400():
    """It *is* a 400, so if the generic branch came first the specific and
    more useful sentence would never be reached."""
    text = ai._human_error(BadRequestError(PRODUCTION_400))
    assert "rejected as invalid" not in text


def test_any_other_400_does_not_promise_a_retry_either():
    text = ai._human_error(BadRequestError("prompt is too long")).lower()
    assert "try again" not in text
    assert "same answer" in text


def test_an_unrecognised_non_400_still_suggests_a_retry():
    """The generic fallback is unchanged for errors that might be transient: a
    500 is the one kind where asking again can genuinely work."""
    text = ai._human_error(InternalServerError("boom"))
    assert "Try again" in text


def test_no_new_copy_uses_an_em_dash():
    """CLAUDE.md: a deliberate pass removed them from reader-facing copy."""
    for exc in (BadRequestError(PRODUCTION_400), BadRequestError("x")):
        assert "—" not in ai._human_error(exc)
