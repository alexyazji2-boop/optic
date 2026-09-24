"""The caps on the two endpoints that cost money.

/api/chat and /api/research bill per call, and the terminal is open to anyone
with the URL. Without a cap that combination is an unmetered spend endpoint on a
public address, where the first sign of abuse is the invoice.

Two caps now, doing different jobs.

The **hourly** one is per address and in memory. It is a burst limit and it
applies to everybody. Not access control and it does not pretend to be: many
addresses get many buckets. It converts "drain the balance in a minute" into
"drain it slowly enough to notice".

The **daily** one is an allowance and it lives in the accounts database. It
takes an account: Pulse is the only surface here that spends the operator's
money per use, and metered by address it was also the easiest thing in the app
to get more of, because a new address is a new allowance. Everything else in
the terminal stays open to guests, which `test_auth_authorization.py` holds.

So a guest reaching either endpoint gets 401 and a sentence naming the way in,
and the hourly cap below is now only reachable with an account -- which is why
these tests sign in first. `GUEST_AI_CALLS_PER_DAY` above zero restores the old
per-address metering for an operator who wants it, and the tests that cover
that path still set it.

An account holder must keep working when the accounts database does not: see
the last test in this file.
"""

def signed_in(email):
    """A client with a session. The hourly cap applies to everybody, but only
    an account holder can now reach it."""
    c = TestClient(main.app)
    c.post("/api/auth/register", json={
        "first_name": "A", "email": email,
        "password": "tungsten-carbide-9", "confirm_password": "tungsten-carbide-9"})
    return c

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


def test_caller_is_cut_off_after_its_allowance(accounts):
    main.AI_CALLS_PER_HOUR = 3
    who = signed_in("hourly1@example.com")
    head = {"x-forwarded-for": "203.0.113.7"}
    codes = [who.post("/api/chat", json=BODY, headers=head).status_code
             for _ in range(4)]
    assert codes[3] == 429, codes
    assert codes.count(429) == 1, codes


def test_the_message_says_how_long_to_wait(accounts):
    main.AI_CALLS_PER_HOUR = 1
    who = signed_in("hourly2@example.com")
    head = {"x-forwarded-for": "203.0.113.8"}
    who.post("/api/chat", json=BODY, headers=head)
    body = who.post("/api/chat", json=BODY, headers=head).json()
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


def test_research_shares_the_same_budget(accounts):
    """Both endpoints bill the same account, so they draw on one allowance."""
    main.AI_CALLS_PER_HOUR = 2
    who = signed_in("hourly3@example.com")
    head = {"x-forwarded-for": "203.0.113.10"}
    who.post("/api/chat", json=BODY, headers=head)
    who.post("/api/chat", json=BODY, headers=head)
    blocked = who.post("/api/research", json={"ticker": "SPY"}, headers=head)
    assert blocked.status_code == 429


def test_zero_disables_the_guard():
    """An operator running this privately should be able to turn it off."""
    main.AI_CALLS_PER_HOUR = 0
    head = {"x-forwarded-for": "203.0.113.11"}
    for _ in range(5):
        assert client.post("/api/chat", json=BODY, headers=head).status_code != 429


def test_stale_buckets_are_reaped(accounts):
    """A long-lived instance must not accumulate an entry per visitor forever."""
    main.AI_CALLS_PER_HOUR = 5
    main._ai_calls.update({"10.0.0.%d" % i: [0.0] for i in range(2100)})
    who = signed_in("reaper@example.com")
    who.post("/api/chat", json=BODY, headers={"x-forwarded-for": "203.0.113.12"})
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


def test_the_assistant_still_answers_when_the_accounts_database_is_gone(accounts,
                                                                       monkeypatch):
    """One broken table must not take out the feature people came for.

    The daily allowance degrades and says so in the log; the hourly cap carries
    on alone. Failing closed here would mean an unmigrated database looks
    exactly like Pulse being broken.

    This used to be asserted with a guest, which cannot be the subject any
    more: Pulse takes an account, and a guest gets 401 whatever the database
    is doing. The invariant is about the people who can use the feature, and
    it holds for them -- an account holder presents a session cookie, the
    lookup raises OSError from os.makedirs, `_spend_guard` catches it, logs
    that the daily cap is not being enforced, and the request goes through on
    the hourly cap alone. Measured: 200 with the database gone.

    The other half of it still holds for a guest and is asserted below: a
    broken database produces a clean, explained 401 rather than a 500 with a
    stack trace."""
    from app import db as accounts_db
    # Established while the database works; the cookie outlives it.
    who = signed_in("dbgone@example.com")
    # A path under a directory that cannot be created, which is what an
    # unmounted volume looks like: the failure arrives from os.makedirs as an
    # OSError, not from sqlite. Catching only sqlite3.Error left this as a 500.
    monkeypatch.setattr(accounts_db, "DB_PATH", "/nonexistent-root-dir/accounts.db")
    monkeypatch.setattr(main, "_allowance_warned", False)
    main.AI_CALLS_PER_HOUR = 2
    head = {"x-forwarded-for": "203.0.113.24"}
    assert who.post("/api/chat", json=BODY, headers=head).status_code == 200
    state = who.get("/api/ai-allowance", headers=head).json()["allowance"]
    assert state["enforced"] is False
    # And it does not then demand a sign-in it cannot verify: with nobody
    # identifiable the panel must not be told an account is required.
    assert state.get("requires_account") is not True
    # The hourly cap is still doing its job.
    who.post("/api/chat", json=BODY, headers=head)
    assert who.post("/api/chat", json=BODY, headers=head).status_code == 429


def test_a_broken_database_refuses_a_guest_cleanly_rather_than_crashing(monkeypatch):
    """The half of the invariant above that a guest can still stand for."""
    from app import db as accounts_db
    monkeypatch.setattr(accounts_db, "DB_PATH", "/nonexistent-root-dir/accounts.db")
    monkeypatch.setattr(main, "_allowance_warned", False)
    main.AI_CALLS_PER_HOUR = 30
    reply = client.post("/api/chat", json=BODY,
                        headers={"x-forwarded-for": "203.0.113.25"})
    assert reply.status_code == 401
    assert "free account" in reply.json()["detail"]
    assert "stays open" in reply.json()["detail"]


# --------------------------------------------- Pulse takes an account


def test_a_guest_is_refused_and_told_the_way_in():
    """401, not 429: the allowance is not exhausted, it does not exist. A 429
    would tell a first-time visitor to come back tomorrow for something that
    will never arrive."""
    for path, body in (("/api/chat", BODY), ("/api/research", {"ticker": "SPY"})):
        reply = client.post(path, json=body,
                            headers={"x-forwarded-for": "203.0.113.30"})
        assert reply.status_code == 401, path
        detail = reply.json()["detail"]
        assert "free account" in detail, path
        # And it says what is NOT gated, because everything else is open.
        assert "stays open" in detail, path


def test_the_rest_of_the_terminal_is_untouched_for_a_guest():
    """The one gate must not become a wall. This is the regression
    test_auth_authorization.py exists for, asserted again here beside the
    change that could cause it."""
    assert client.get("/api/session").status_code == 200
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/ai-allowance").status_code == 200


def test_a_guest_is_told_an_account_is_required_before_typing():
    """`requires_account` is its own field rather than inferred from
    `allowed == 0`, which is also what a spent allowance looks like and means
    something a reader would act on differently."""
    state = client.get("/api/ai-allowance",
                       headers={"x-forwarded-for": "203.0.113.31"}).json()["allowance"]
    assert state["scope"] == "guest"
    assert state["requires_account"] is True
    assert state["signed_in_allowance"] == store_plans()["free"]["ai_calls_per_day"]


def store_plans():
    from app.auth import store
    return store.PLANS


def test_a_free_account_gets_five_a_day_and_the_sixth_is_refused(accounts):
    """Five, and the sixth says so. The hourly cap is lifted well clear so the
    daily one is what answers."""
    main.AI_CALLS_PER_HOUR = 100
    who = signed_in("fiveaday@example.com")
    head = {"x-forwarded-for": "203.0.113.32"}
    codes = [who.post("/api/chat", json=BODY, headers=head).status_code
             for _ in range(6)]
    assert codes == [200, 200, 200, 200, 200, 429], codes
    assert "5 assistant messages today" in who.post(
        "/api/chat", json=BODY, headers=head).json()["detail"]


def test_the_free_plan_is_five():
    """The number the refusal quotes and the number the panel promises both
    come from here, so there is nothing to keep in step."""
    assert store_plans()["free"]["ai_calls_per_day"] == 5


def test_an_operator_can_re_open_it_to_guests(monkeypatch):
    """The gate is a default, not a literal. Set the variable above zero and
    the per-address metering that was there before works unchanged."""
    monkeypatch.setattr(main, "GUEST_AI_CALLS_PER_DAY", 2)
    head = {"x-forwarded-for": "203.0.113.33"}
    codes = [client.post("/api/chat", json=BODY, headers=head).status_code
             for _ in range(3)]
    assert codes == [200, 200, 429], codes
    state = client.get("/api/ai-allowance", headers=head).json()["allowance"]
    assert state["requires_account"] is False
