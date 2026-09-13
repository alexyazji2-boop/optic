"""Watches evaluated server-side, so a hit is waiting at the next sign-in.

The feature this completes. `/api/watches/check` is driven by the browser: it
evaluates the symbols the page is looking at, while the page is open. That made
the one thing anybody wants from an alert — being told about a move you were
*not* watching — the one thing it could not do.

These drive the runner directly with a fake snapshot, so they assert behaviour
rather than reading the source, and they never touch the network.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app import db, watch_runner
from app.analytics import watches as watches_mod


@pytest.fixture()
def account(accounts):
    """One empty accounts database and one user in it.

    `accounts` is the shared fixture in conftest: a per-test database, because
    these count rows and a shared one makes every total depend on what ran
    before it."""
    uid = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    db.execute("INSERT INTO users (id, email, created_at, updated_at) "
               "VALUES (?,?,?,?)", (uid, "a@example.com", now, now))
    return uid


def add_watch(user_id, symbol, kind, params, note=None):
    wid = uuid.uuid4().hex
    db.execute(
        "INSERT INTO watches (id, user_id, symbol, kind, params, note, active, "
        "created_at) VALUES (?,?,?,?,?,?,1,?)",
        (wid, user_id, symbol, kind, json.dumps(params, sort_keys=True), note,
         datetime.now(timezone.utc).isoformat()))
    return wid


def snapshot_with(rsi=None, macd_state=None, price=None):
    tech = {}
    if rsi is not None:
        tech["rsi"] = {"value": rsi, "length": 14}
    if macd_state is not None:
        tech["macd"] = {"state": macd_state, "macd": 2.5, "signal": 3.1}
    payload = {"technicals": tech}
    if price is not None:
        payload["quote"] = {"price": price}
    return lambda symbol: payload


# ------------------------------------------------------------ the conditions

def test_rsi_above_fires_on_the_level_it_was_given():
    """The request that prompted this, literally: RSI over 50 on NVDA."""
    d = {"technicals": {"rsi": {"value": 62.4}}}
    hit = watches_mod.EVALUATORS["rsi_above"](d, {"level": 50})
    assert hit and "62.4" in hit["evidence"] and "50" in hit["evidence"]
    assert watches_mod.EVALUATORS["rsi_above"](d, {"level": 70}) is None


def test_rsi_below_is_not_just_the_negation():
    d = {"technicals": {"rsi": {"value": 24.0}}}
    assert watches_mod.EVALUATORS["rsi_below"](d, {"level": 30})
    assert watches_mod.EVALUATORS["rsi_below"](d, {"level": 20}) is None


def test_exactly_on_the_level_is_not_above_it():
    """"Rises above 50" at exactly 50.00 has not risen above anything. The
    boundary is where a watch is most likely to be read as broken, because it is
    the one value the reader is staring at when they made it, and `<=` against
    `<` is a one-character difference that nothing else would catch."""
    at = {"technicals": {"rsi": {"value": 50.0}}}
    assert watches_mod.EVALUATORS["rsi_above"](at, {"level": 50}) is None
    assert watches_mod.EVALUATORS["rsi_below"](at, {"level": 50}) is None
    just_over = {"technicals": {"rsi": {"value": 50.01}}}
    assert watches_mod.EVALUATORS["rsi_above"](just_over, {"level": 50})


def test_an_absent_rsi_never_fires():
    """Unmeasurable is not the same as false, and a watch that fires on missing
    data is worse than one that misses: it reports news that did not happen."""
    for payload in ({}, {"technicals": {}}, {"technicals": {"rsi": {}}}):
        assert watches_mod.EVALUATORS["rsi_above"](payload, {"level": 50}) is None
        assert watches_mod.EVALUATORS["rsi_below"](payload, {"level": 50}) is None


def test_macd_direction_is_respected():
    d = {"technicals": {"macd": {"state": "bearish", "macd": 2.5, "signal": 3.1}}}
    assert watches_mod.EVALUATORS["macd_cross"](d, {"to": "any"})
    assert watches_mod.EVALUATORS["macd_cross"](d, {"to": "bearish"})
    assert watches_mod.EVALUATORS["macd_cross"](d, {"to": "bullish"}) is None


def test_every_choice_the_catalogue_offers_is_one_the_evaluator_accepts():
    """The fault this codebase has shipped three times: a stored parameter
    compared as a string against a vocabulary produced somewhere else. The watch
    stores fine, evaluates fine and never fires, and "did not fire" is also the
    correct answer most of the time, so nothing looks broken."""
    spec = watches_mod.CONDITIONS["macd_cross"]["param"]
    d = {"technicals": {"macd": {"state": "bullish", "macd": 3.1, "signal": 2.5}}}
    fired = [c["value"] for c in spec["choices"]
             if watches_mod.EVALUATORS["macd_cross"](d, {"to": c["value"]})]
    assert "any" in fired and "bullish" in fired
    assert "bearish" not in fired


# ----------------------------------------------------------------- the runner

def test_a_hit_is_recorded_for_the_owner(account):
    add_watch(account, "NVDA", "rsi_above", {"level": 50})
    out = watch_runner.run_once(snapshot_with(rsi=62.4))
    assert out["hits"] == 1 and out["watches_checked"] == 1
    hits = watch_runner.hits_for(account)
    assert len(hits) == 1
    assert hits[0]["symbol"] == "NVDA"
    assert "62.4" in hits[0]["body"]


def test_a_watch_that_stays_true_reports_once_a_day(account):
    """Almost every condition describes a STATE. RSI above 50 is true for as
    long as it is true, so a runner on a fifteen-minute loop would write the
    same sentence ninety-six times and the inbox would be one nobody opens
    twice."""
    add_watch(account, "NVDA", "rsi_above", {"level": 50})
    first = watch_runner.run_once(snapshot_with(rsi=62.4))
    second = watch_runner.run_once(snapshot_with(rsi=63.1))
    assert first["hits"] == 1
    assert second["hits"] == 0
    assert len(watch_runner.hits_for(account)) == 1


def test_tomorrow_it_reports_again(account):
    """The other half. Dedupe that never expires is silence."""
    wid = add_watch(account, "NVDA", "rsi_above", {"level": 50})
    now = datetime.now(timezone.utc)
    row = {"id": wid, "user_id": account, "symbol": "NVDA",
           "kind": "rsi_above", "note": None}
    result = {"label": "RSI rises above", "evidence": "RSI 62.4, above 50"}
    assert watch_runner.record_hit(row, result, now)
    assert not watch_runner.record_hit(row, result, now)
    assert watch_runner.record_hit(row, result, now + timedelta(days=1))
    assert len(watch_runner.hits_for(account)) == 2


def test_a_watch_that_does_not_fire_leaves_nothing(account):
    add_watch(account, "NVDA", "rsi_above", {"level": 70})
    out = watch_runner.run_once(snapshot_with(rsi=62.4))
    assert out["watches_checked"] == 1 and out["hits"] == 0
    assert watch_runner.hits_for(account) == []


def test_one_snapshot_per_symbol_however_many_accounts_watch_it(account):
    """A snapshot builds the chain, the greeks and the technicals, so it is the
    expensive part. Ten accounts watching NVDA must cost one, not ten."""
    other = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    db.execute("INSERT INTO users (id, email, created_at, updated_at) "
               "VALUES (?,?,?,?)", (other, "b@example.com", now, now))
    add_watch(account, "NVDA", "rsi_above", {"level": 50})
    add_watch(other, "NVDA", "rsi_above", {"level": 40})
    add_watch(account, "AMD", "rsi_above", {"level": 50})

    calls = []

    def snapshot(symbol):
        calls.append(symbol)
        return {"technicals": {"rsi": {"value": 62.4}}}

    out = watch_runner.run_once(snapshot)
    assert sorted(calls) == ["AMD", "NVDA"], calls
    assert out["watches_checked"] == 3 and out["hits"] == 3


def test_a_failing_symbol_costs_only_itself(account):
    """One bad ticker in a hundred must not end the pass, and a run that quietly
    skipped a symbol is a run whose empty inbox means nothing."""
    add_watch(account, "NVDA", "rsi_above", {"level": 50})
    add_watch(account, "BADTICK", "rsi_above", {"level": 50})

    def snapshot(symbol):
        if symbol == "BADTICK":
            raise RuntimeError("no such symbol")
        return {"technicals": {"rsi": {"value": 62.4}}}

    out = watch_runner.run_once(snapshot)
    assert out["hits"] == 1
    assert out["failed_symbols"] == ["BADTICK"]


def test_the_run_is_capped(account):
    """A scheduled job that grows without bound with the user base is one that
    eventually does not finish."""
    for i in range(5):
        add_watch(account, "SYM%d" % i, "rsi_above", {"level": 50})
    calls = []

    def snapshot(symbol):
        calls.append(symbol)
        return {"technicals": {"rsi": {"value": 62.4}}}

    out = watch_runner.run_once(snapshot, limit=2)
    assert len(calls) == 2
    assert out["symbols"] == 2 and out["skipped_symbols"] == 3


def test_the_reader_note_travels_with_the_hit(account):
    """The reason they made the watch is the context they will have lost by the
    time it fires."""
    add_watch(account, "NVDA", "rsi_above", {"level": 50}, note="momentum thesis")
    watch_runner.run_once(snapshot_with(rsi=62.4))
    body = watch_runner.hits_for(account)[0]["body"]
    assert "momentum thesis" in body
    assert "RSI 62.4" in body


def test_a_hit_body_never_prints_a_missing_value(account):
    """"Exited at 0.05 for None" shipped once, from a format string over a value
    that was not there."""
    add_watch(account, "NVDA", "rsi_above", {"level": 50})
    watch_runner.run_once(snapshot_with(rsi=62.4))
    body = watch_runner.hits_for(account)[0]["body"]
    assert "None" not in body
    assert "—" not in body


# ------------------------------------------------------------------ the inbox

def test_unseen_is_counted_and_clearable(account):
    add_watch(account, "NVDA", "rsi_above", {"level": 50})
    watch_runner.run_once(snapshot_with(rsi=62.4))
    assert watch_runner.unseen_count(account) == 1
    watch_runner.mark_seen(account)
    assert watch_runner.unseen_count(account) == 0
    assert len(watch_runner.hits_for(account)) == 1, "read is not deleted"


def test_one_account_cannot_mark_anothers_hits(account):
    """Scoped in the WHERE clause rather than checked first, so an id belonging
    to somebody else matches no row instead of racing a lookup."""
    other = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    db.execute("INSERT INTO users (id, email, created_at, updated_at) "
               "VALUES (?,?,?,?)", (other, "b@example.com", now, now))
    add_watch(account, "NVDA", "rsi_above", {"level": 50})
    watch_runner.run_once(snapshot_with(rsi=62.4))
    mine = watch_runner.hits_for(account)[0]["id"]
    assert watch_runner.mark_seen(other, [mine]) == 0
    assert watch_runner.unseen_count(account) == 1


def test_hits_are_only_ever_the_callers_own(account):
    other = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    db.execute("INSERT INTO users (id, email, created_at, updated_at) "
               "VALUES (?,?,?,?)", (other, "b@example.com", now, now))
    add_watch(account, "NVDA", "rsi_above", {"level": 50})
    add_watch(other, "AMD", "rsi_above", {"level": 50})
    watch_runner.run_once(snapshot_with(rsi=62.4))
    assert [h["symbol"] for h in watch_runner.hits_for(account)] == ["NVDA"]
    assert [h["symbol"] for h in watch_runner.hits_for(other)] == ["AMD"]
