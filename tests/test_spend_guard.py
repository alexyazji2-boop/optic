"""The per-IP cap on the two endpoints that cost money.

Optic is deliberately open — no accounts, no sign-in — and /api/chat and
/api/research bill per call. Without a cap that combination is an unmetered
spend endpoint on a public URL, where the first sign of abuse is the invoice.

The guard is not access control and does not pretend to be: many addresses get
many buckets. It converts "drain the balance in a minute" into "drain it slowly
enough to notice", which is the exposure worth closing before publishing.
"""

import pytest

import app.main as main
from fastapi.testclient import TestClient

client = TestClient(main.app)

BODY = {"messages": [{"role": "user", "content": "hi"}]}


@pytest.fixture(autouse=True)
def no_model_calls(monkeypatch):
    """Stub the model out.

    The first version of this file let calls that passed the guard fall through
    to the real ai.stream_chat, so running the suite made live Anthropic
    requests. It only looked harmless because the account balance was zero —
    the moment it was topped up, `pytest` would have started billing. What is
    under test is the gate, not the model behind it.
    """
    def fake_stream(*args, **kwargs):
        yield "data: stub\n\n"

    monkeypatch.setattr(main.ai, "stream_chat", fake_stream)
    monkeypatch.setattr(main.ai, "deep_research", fake_stream)
    main._ai_calls.clear()
    allowance = main.AI_CALLS_PER_HOUR
    yield
    main.AI_CALLS_PER_HOUR = allowance
    main._ai_calls.clear()


def test_caller_is_cut_off_after_its_allowance():
    main.AI_CALLS_PER_HOUR = 3
    head = {"x-forwarded-for": "203.0.113.7"}
    codes = [client.post("/api/chat", json=BODY, headers=head).status_code
             for _ in range(4)]
    assert codes[3] == 429, codes
    assert codes.count(429) == 1, codes


def test_the_message_says_how_long_to_wait():
    main.AI_CALLS_PER_HOUR = 1
    head = {"x-forwarded-for": "203.0.113.8"}
    client.post("/api/chat", json=BODY, headers=head)
    body = client.post("/api/chat", json=BODY, headers=head).json()
    assert "an hour per visitor" in body["detail"]
    assert "minutes" in body["detail"]


def test_one_heavy_caller_does_not_lock_out_everyone_else():
    """The bucket is per address, so abuse from one IP must not close the demo."""
    main.AI_CALLS_PER_HOUR = 2
    heavy = {"x-forwarded-for": "203.0.113.9"}
    for _ in range(3):
        client.post("/api/chat", json=BODY, headers=heavy)
    other = client.post("/api/chat", json=BODY,
                        headers={"x-forwarded-for": "198.51.100.4"})
    assert other.status_code != 429


def test_research_shares_the_same_budget():
    """Both endpoints bill the same account, so they draw on one allowance."""
    main.AI_CALLS_PER_HOUR = 2
    head = {"x-forwarded-for": "203.0.113.10"}
    client.post("/api/chat", json=BODY, headers=head)
    client.post("/api/chat", json=BODY, headers=head)
    blocked = client.post("/api/research", json={"ticker": "SPY"}, headers=head)
    assert blocked.status_code == 429


def test_zero_disables_the_guard():
    """An operator running this privately should be able to turn it off."""
    main.AI_CALLS_PER_HOUR = 0
    head = {"x-forwarded-for": "203.0.113.11"}
    for _ in range(5):
        assert client.post("/api/chat", json=BODY, headers=head).status_code != 429


def test_stale_buckets_are_reaped():
    """A long-lived instance must not accumulate an entry per visitor forever."""
    main.AI_CALLS_PER_HOUR = 5
    main._ai_calls.update({"10.0.0.%d" % i: [0.0] for i in range(2100)})
    client.post("/api/chat", json=BODY, headers={"x-forwarded-for": "203.0.113.12"})
    assert len(main._ai_calls) < 2100
