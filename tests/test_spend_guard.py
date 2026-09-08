"""The caps on the two endpoints that cost money.

/api/chat and /api/research bill per call, and the terminal is open to anyone
with the URL. Without a cap that combination is an unmetered spend endpoint on a
public address, where the first sign of abuse is the invoice.

Two caps now, doing different jobs.

The **hourly** one is per address and in memory. It is a burst limit and it
applies to everybody. Not access control and it does not pretend to be: many
addresses get many buckets. It converts "drain the balance in a minute" into
"drain it slowly enough to notice".

The **daily** one is an allowance and it lives in the accounts database. Guests
get a few messages a day so the product can be tried; signing in raises it to
the account's plan. That is also why the assistant must keep working when the
accounts database does not: see the last test in this file.
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
    assert "in an hour from this connection" in body["detail"]
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


# ------------------------------------------------------- the daily allowance


def test_a_guest_is_told_what_an_account_would_give():
    body = client.get("/api/ai-allowance",
                      headers={"x-forwarded-for": "203.0.113.20"}).json()["allowance"]
    assert body["scope"] == "guest"
    assert body["allowed"] == main.GUEST_AI_CALLS_PER_DAY
    assert body["signed_in_allowance"] > body["allowed"]


def test_the_guest_daily_allowance_refuses_and_names_the_way_out(monkeypatch):
    monkeypatch.setattr(main, "GUEST_AI_CALLS_PER_DAY", 2)
    head = {"x-forwarded-for": "203.0.113.21"}
    codes = [client.post("/api/chat", json=BODY, headers=head).status_code
             for _ in range(3)]
    assert codes == [200, 200, 429], codes
    body = client.post("/api/chat", json=BODY, headers=head).json()
    assert "Create a free account" in body["detail"]
    # And the rest of the terminal is unaffected.
    assert "stays open either way" in body["detail"]
    assert client.get("/api/session").status_code == 200


def test_signing_in_raises_the_allowance(accounts, monkeypatch):
    monkeypatch.setattr(main, "GUEST_AI_CALLS_PER_DAY", 1)
    signed = TestClient(main.app)
    signed.post("/api/auth/register", json={
        "first_name": "A", "email": "spender@example.com",
        "password": "tungsten-carbide-9", "confirm_password": "tungsten-carbide-9"})
    head = {"x-forwarded-for": "203.0.113.22"}
    # Past the guest allowance of one, because the bucket is now the account.
    codes = [signed.post("/api/chat", json=BODY, headers=head).status_code
             for _ in range(4)]
    assert codes == [200, 200, 200, 200], codes
    state = signed.get("/api/ai-allowance").json()["allowance"]
    assert state["scope"] == "account"
    assert state["used"] == 4


def test_the_plan_allowance_is_enforced(accounts, monkeypatch):
    from app.auth import store
    monkeypatch.setitem(store.PLANS["free"], "ai_calls_per_day", 2)
    signed = TestClient(main.app)
    signed.post("/api/auth/register", json={
        "first_name": "A", "email": "capped@example.com",
        "password": "tungsten-carbide-9", "confirm_password": "tungsten-carbide-9"})
    head = {"x-forwarded-for": "203.0.113.23"}
    codes = [signed.post("/api/chat", json=BODY, headers=head).status_code
             for _ in range(3)]
    assert codes == [200, 200, 429], codes
    assert "this plan includes" in signed.post("/api/chat", json=BODY,
                                               headers=head).json()["detail"]


def test_the_assistant_still_answers_when_the_accounts_database_is_gone(monkeypatch):
    """One broken table must not take out the feature people came for.

    The daily allowance degrades and says so in the log; the hourly cap carries
    on alone. Failing closed here would mean an unmigrated database looks
    exactly like Pulse being broken."""
    from app import db as accounts_db
    # A path under a directory that cannot be created, which is what an
    # unmounted volume looks like: the failure arrives from os.makedirs as an
    # OSError, not from sqlite. Catching only sqlite3.Error left this as a 500.
    monkeypatch.setattr(accounts_db, "DB_PATH", "/nonexistent-root-dir/accounts.db")
    monkeypatch.setattr(main, "_allowance_warned", False)
    main.AI_CALLS_PER_HOUR = 2
    head = {"x-forwarded-for": "203.0.113.24"}
    assert client.post("/api/chat", json=BODY, headers=head).status_code == 200
    state = client.get("/api/ai-allowance", headers=head).json()["allowance"]
    assert state["enforced"] is False
    # The hourly cap is still doing its job.
    client.post("/api/chat", json=BODY, headers=head)
    assert client.post("/api/chat", json=BODY, headers=head).status_code == 429
