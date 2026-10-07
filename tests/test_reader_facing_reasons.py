"""A dark feature says why in the words of whoever is reading.

"Set FEED_CONTACT in .env" and "Set ANTHROPIC_API_KEY in your environment" are
the right sentences for the person running the terminal on their own machine
and useless ones for a visitor to the hosted site, who has no environment to
set anything in. Pulse's hint branched on this first; the SEC feeds behind
Insiders, segments and filings, and Pulse's own streaming errors, did not.
runtime.for_reader is that branch, and each of these sites is driven both ways
here rather than read as text.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from app import ai, feeds, insiders
from app.analytics import filings, segments
from app.runtime import for_reader


@pytest.fixture(params=["hosted", "local"])
def audience(request, monkeypatch):
    if request.param == "hosted":
        monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    else:
        for var in ("RAILWAY_ENVIRONMENT", "RAILWAY_GIT_COMMIT_SHA", "RENDER", "FLY_APP_NAME"):
            monkeypatch.delenv(var, raising=False)
    return request.param


def _check(reason, audience):
    if audience == "hosted":
        assert "FEED_CONTACT" not in reason and "ANTHROPIC_API_KEY" not in reason, reason
        assert ".env" not in reason and "environment" not in reason, reason
    else:
        assert "FEED_CONTACT" in reason or "ANTHROPIC_API_KEY" in reason, reason


def test_the_helper_picks_by_audience(audience):
    assert for_reader("reader", "operator") == ("reader" if audience == "hosted" else "operator")


def test_the_sec_feeds_say_why_they_are_dark(audience, monkeypatch):
    monkeypatch.setattr(feeds, "CONTACT_OK", False)
    for out in (insiders.index(force=True), segments.filings("AAPL", force=True),
                filings.recent("AAPL")):
        assert out["available"] is False
        _check(out["reason"], audience)


def _first_event(gen):
    async def first():
        async for chunk in gen:
            return chunk
    return asyncio.run(first())


def test_pulses_streams_say_why_they_are_dark(audience, monkeypatch):
    monkeypatch.setattr(ai, "_client", lambda: None)
    for gen in (ai.stream_chat([{"role": "user", "content": "hi"}]),
                ai.deep_research("AAPL")):
        chunk = _first_event(gen)
        payload = json.loads(chunk.split("data:", 1)[1].strip())
        _check(payload["message"], audience)
