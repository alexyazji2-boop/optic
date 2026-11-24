"""Milo's route with Anthropic played by a recording stub on a local port (Pass 1, 2026-11-09).

The real SDK and the real chat route, the provider replaced by tests/support/anthropic_stub.py: what the route sends
(the screen's figures, the symbol and the reader's level), what it records for the owner (a milo_question row with
the screen and no question text), and what the reader gets when Anthropic times out or answers an error: the
failure said in words, no answer text streamed, nothing half-written."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app import ai, db, feeds, knowledge, usage
from app.auth import config, store
from tests.support.anthropic_stub import ANSWER, AnthropicStub

client = TestClient(main.app)
FEEDS = []
GOOD = "tungsten-carbide-9"


@pytest.fixture(scope="module")
def stub():
    s = AnthropicStub().start()
    yield s
    s.stop()


@pytest.fixture(autouse=True)
def provider(stub, accounts, monkeypatch):
    """The provider's address is a setting, pinned to the stub; the key is a fake one; no retries, a short timeout."""
    monkeypatch.setenv("ANTHROPIC_BASE_URL", stub.url)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    monkeypatch.setenv("ANTHROPIC_MAX_RETRIES", "0")
    monkeypatch.setenv("ANTHROPIC_TIMEOUT_SECONDS", "2")
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_WORKSPACE_ID", raising=False)
    stub.reset("ok")
    stub.hold = 6.0
    # The market feeds the Home context reads (the Fed's press feed and the rest, through app.feeds) are a recording
    # refusal here: each address is kept, and the feed answers as an outage, which the route already handles.
    FEEDS.clear()

    def feed_down(url, *a, **k):
        FEEDS.append(url)
        raise RuntimeError("feed played as down by the test")
    monkeypatch.setattr(feeds, "_fetch", feed_down)
    usage.reset_limits()
    client.cookies.clear()
    yield
    client.cookies.clear()


def signed_in():
    client.post("/api/auth/register", json={"first_name": "A", "last_name": "B", "email": "asker@example.com",
                                            "password": GOOD, "confirm_password": GOOD})
    store.mark_verified(store.get_user_by_email("asker@example.com")["id"])
    return client.cookies.get(config.CSRF_COOKIE)


def overview_context(sym="AAPL"):
    """What the Overview's prompt sends (ui/miloprompt.js -> openMilo -> buildContext): the page, the company in focus,
    and the figures of the quote as the page shows them."""
    return {"focus": {"scope": "auto", "view": "overview", "ticker": sym, "view_label": "{} Overview".format(sym),
                      "asked_from": "{} Overview".format(sym)},
            "view": "overview", "ticker": sym,
            "panel": {"name": "{} quote".format(sym), "figures": [["Price", "248.21"], ["Change today", "+2.42 (+0.98%)"]], "notes": []}}


def ask(question, context, mode="beginner", csrf=None):
    r = client.post("/api/chat", json={"messages": [{"role": "user", "content": question}], "context": context, "mode": mode},
                    headers={"X-Optic-CSRF": csrf or "", "X-Optic-Visitor": "v-" + "c" * 32})
    events = []
    for chunk in r.text.split("\n\n"):
        ev, data = "message", ""
        for line in chunk.split("\n"):
            if line.startswith("event: "):
                ev = line[7:].strip()
            elif line.startswith("data: "):
                data += line[6:]
        if data:
            try:
                events.append((ev, json.loads(data)))
            except ValueError:
                events.append((ev, data))
    return r, events


def sent_text(req):
    """Everything the route put in front of the model: system blocks and messages, as one string."""
    b = req["body"]
    sys_ = b.get("system")
    parts = [json.dumps(sys_)] if sys_ else []
    parts.append(json.dumps(b.get("messages")))
    return "\n".join(parts)


def test_the_stub_is_the_only_provider_reached(stub):
    assert ai._client() is not None
    assert str(ai._client().base_url).rstrip("/") == stub.url


def test_the_overview_prompt_reaches_milo_with_the_symbol_the_figures_and_the_level(stub):
    csrf = signed_in()
    r, events = ask("Why is Apple moving today?", overview_context(), mode="beginner", csrf=csrf)
    assert r.status_code == 200, r.text
    assert ANSWER in "".join(d.get("text", "") for e, d in events if e == "delta" and isinstance(d, dict))
    msgs = stub.messages()
    assert msgs, "the route never reached the stub"
    text = sent_text(msgs[0])
    assert "AAPL" in text and "248.21" in text and "+2.42 (+0.98%)" in text
    # the level travels with the question: the Beginner style block, which is app/knowledge.py's own
    assert knowledge.MODES["beginner"]["prompt"][:60] in text
    assert knowledge.MODES["advanced"]["prompt"][:60] not in text


@pytest.mark.parametrize("level", ["beginner", "intermediate", "advanced"])
def test_each_of_the_three_levels_is_the_style_milo_is_given(stub, level):
    csrf = signed_in()
    stub.reset("ok")
    ask("Why did the market move today?", {"focus": {"scope": "auto", "view": "home", "ticker": None}}, mode=level, csrf=csrf)
    text = sent_text(stub.messages()[0])
    assert knowledge.MODES[level]["prompt"][:60] in text


def test_a_question_is_recorded_for_the_owner_with_its_screen_and_never_its_text(stub):
    csrf = signed_in()
    ask("Why is Apple moving today? My secret note", overview_context(), mode="intermediate", csrf=csrf)
    (row,) = db.rows("SELECT * FROM usage_event WHERE event = 'milo_question'")
    uid = store.get_user_by_email("asker@example.com")["id"]
    assert (row["actor_kind"], row["actor_ref"], row["source_screen"], row["symbol"], row["level"]) == \
        ("signed_in", uid, "overview", "AAPL", "intermediate")
    assert "secret" not in json.dumps(row) and "Apple moving" not in json.dumps(row)


def test_a_question_refused_by_the_allowance_is_not_recorded(stub):
    # no account: Milo needs one (the guard answers 401 before anything is counted)
    r, _ = ask("Why did the market move today?", {"focus": {"view": "home"}})
    assert r.status_code == 401
    assert db.rows("SELECT * FROM usage_event WHERE event = 'milo_question'") == []
    assert stub.messages() == []


@pytest.mark.parametrize("mode", ["timeout", "error"])
def test_anthropic_down_is_said_to_the_reader_and_nothing_is_half_written(stub, mode):
    csrf = signed_in()
    stub.reset(mode)
    r, events = ask("Why is Apple moving today?", overview_context(), csrf=csrf)
    assert r.status_code == 200          # the stream had begun ("gathering") before the provider failed
    assert stub.messages(), "the route did call the provider"
    errors = [d for e, d in events if e == "error"]
    assert errors and isinstance(errors[0], dict) and errors[0].get("message"), events
    msg = errors[0]["message"]
    assert "Traceback" not in msg and "test-key" not in msg
    # no answer text reached the reader, so the panel has nothing to keep (ui/milo.js takes the exchange out and
    # puts the question back in the box; the browser journey checks that side)
    assert not [d for e, d in events if e == "delta"]
    assert not [d for e, d in events if e == "done"]
