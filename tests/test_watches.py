"""User-defined watches: the evaluator, the vocabularies, and the storage.

The evaluator was written before accounts existed and the parameter vocabularies
were never written down anywhere. Three of them were wrong, and all three failed
the same way: the watch stored fine, evaluated fine, and never fired. "Did not
fire" is also the correct answer most of the time, so nothing looked broken.

That is what most of this file is about.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.analytics import watches
from app.auth import config

client = TestClient(main.app)

GOOD = "tungsten-carbide-9"


@pytest.fixture(autouse=True)
def fresh(accounts):
    client.cookies.clear()
    return accounts


@pytest.fixture
def signed_in():
    client.post("/api/auth/register", json={
        "first_name": "Alex", "email": "watcher@example.com",
        "password": GOOD, "confirm_password": GOOD})
    return client.cookies.get(config.CSRF_COOKIE)


# ------------------------------------------------------ vocabularies


def test_every_choice_the_catalogue_offers_is_one_the_evaluator_accepts():
    """The contract that stops the next mismatch. A UI built from `choices`
    cannot offer a value the evaluator ignores, but only if the two agree."""
    cases = {
        "signal_flip": lambda value: watches._signal_flip(
            {"verdict": {"stance": "bullish", "conviction": "high"}}, {"to": value}),
        "analyst_revisions": lambda value: watches._analyst_revisions(
            {"earnings_momentum": {"revision_direction": "rising", "signals": []}},
            {"direction": value}),
        "insider_activity": lambda value: watches._insider_activity(
            {"company": {"ownership": {"recent_transactions": [
                {"action": "purchase"}, {"action": "sale"}]}}}, {"side": value}),
    }
    for kind, run in cases.items():
        choices = watches.CONDITIONS[kind]["param"]["choices"]
        assert choices, kind
        for choice in choices:
            # Every offered value must be *understood*. Not every one has to
            # fire against this fixture, but a value the evaluator cannot
            # recognise would be a watch that is dead on arrival.
            run(choice["value"])            # must not raise


@pytest.mark.parametrize("want,stance,fires", [
    ("bullish", "bullish", True),
    # The one that mattered: an exact match stays silent through the first
    # thing that actually happens.
    ("bullish", "leaning bullish", True),
    ("bullish", "bearish", False),
    ("bearish", "leaning bearish", True),
    # The narrow option still means only itself.
    ("leaning bullish", "bullish", False),
    ("leaning bullish", "leaning bullish", True),
    ("neutral", "neutral", True),
    ("any", "leaning bearish", True),
])
def test_a_stance_watch_covers_the_family_it_names(want, stance, fires):
    payload = {"verdict": {"stance": stance, "conviction": "moderate"}}
    assert (watches._signal_flip(payload, {"to": want}) is not None) is fires


def test_the_five_stances_the_composite_produces_are_all_selectable():
    """If swing.verdict gains a sixth stance, this is where it shows up."""
    import re
    source = open("app/analytics/swing.py").read()
    produced = set(re.findall(
        r'stance, conviction = "([^"]+)"', source))
    offered = {c["value"] for c in watches.CONDITIONS["signal_flip"]["param"]["choices"]}
    assert produced <= offered, produced - offered


@pytest.mark.parametrize("side,fires", [
    ("any", True), ("purchase", True), ("sale", True), ("director", False),
])
def test_an_insider_watch_reads_the_field_the_data_actually_has(side, fires):
    """The rows carry `action`; the evaluator read `kind` and `type`, neither of
    which exists, so every side-specific insider watch was dead."""
    payload = {"company": {"ownership": {"recent_transactions": [
        {"action": "purchase", "insider": "A"},
        {"action": "sale", "insider": "B"},
    ]}}}
    assert (watches._insider_activity(payload, {"side": side}) is not None) is fires


def test_the_provider_still_labels_insider_rows_the_way_the_evaluator_expects():
    """Reads the provider rather than trusting the fixture above."""
    source = open("app/providers/yf.py").read()
    assert '"action": action' in source
    assert '"sale" if "sale" in lowered' in source


@pytest.mark.parametrize("direction,want,fires", [
    ("rising", "rising", True),
    ("falling", "falling", True),
    # `up` and `down` are what a UI would guess, and neither is ever produced.
    ("rising", "up", False),
    ("flat", "any", False),
    # "unknown" means earnings.py found no revision history at all. Firing on
    # it reports an event where there is not even an observation.
    ("unknown", "any", False),
])
def test_a_revisions_watch_uses_the_words_earnings_py_produces(direction, want, fires):
    payload = {"earnings_momentum": {"revision_direction": direction, "signals": []}}
    assert (watches._analyst_revisions(payload, {"direction": want}) is not None) is fires


def test_the_words_earnings_py_produces_are_the_ones_offered():
    """Scoped to the function that produces `revision_direction`.

    `direction` is assigned by two unrelated pieces of logic in earnings.py —
    the other one is the direction of a post-earnings price move, and it uses
    up/down. Scraping the whole file picked those up and reported a mismatch
    that did not exist.
    """
    import re
    source = open("app/analytics/earnings.py").read()
    # Anchored on a string unique to the function that *produces* the value.
    # `"revision_direction": direction` is in `momentum()`, which only reads it
    # — anchoring there found a function with no literal assignments at all,
    # and the scrape silently returned an empty set.
    marker = "No estimate-revision history available for this ticker."
    start = source.index(marker)
    body = source[source.rindex("\ndef ", 0, start):source.index("\ndef ", start)]
    produced = set(re.findall(r'direction(?:, note)? = "([a-z]+)"', body))
    assert produced, "the scrape found nothing, so it is checking nothing"
    offered = {c["value"] for c in
               watches.CONDITIONS["analyst_revisions"]["param"]["choices"]}
    # `flat` and `unknown` are deliberately not offered, and the evaluator
    # treats both as "nothing happened", so a watch for either could not fire.
    assert produced - offered == {"flat", "unknown"}, produced - offered


# ---------------------------------------------------------- storage


def test_create_read_and_delete_a_watch(signed_in):
    made = client.post("/api/watches", headers={"X-Optic-CSRF": signed_in},
                       json={"symbol": "nvda", "kind": "price_above",
                             "params": {"level": 200}})
    assert made.status_code == 200, made.text
    watch = made.json()["watch"]
    assert watch["symbol"] == "NVDA"
    assert watch["params"] == {"level": 200.0}
    assert watch["active"] is True

    listed = client.get("/api/watches").json()["watches"]
    assert len(listed) == 1
    assert client.get("/api/watches", params={"symbol": "AAPL"}).json()["watches"] == []

    gone = client.delete("/api/watches/{}".format(watch["id"]),
                         headers={"X-Optic-CSRF": signed_in})
    assert gone.status_code == 200
    assert client.get("/api/watches").json()["watches"] == []


def test_a_watch_needs_its_parameter(signed_in):
    reply = client.post("/api/watches", headers={"X-Optic-CSRF": signed_in},
                        json={"symbol": "NVDA", "kind": "price_above"})
    assert reply.status_code == 400
    assert "needs a value for Level" in reply.json()["detail"]


def test_a_condition_with_no_parameter_needs_none(signed_in):
    reply = client.post("/api/watches", headers={"X-Optic-CSRF": signed_in},
                        json={"symbol": "NVDA", "kind": "breakout"})
    assert reply.status_code == 200
    assert reply.json()["watch"]["params"] == {}


def test_an_unknown_condition_is_refused(signed_in):
    reply = client.post("/api/watches", headers={"X-Optic-CSRF": signed_in},
                        json={"symbol": "NVDA", "kind": "goes_to_the_moon"})
    assert reply.status_code == 400
    assert "not a condition Optic can watch for" in reply.json()["detail"]


def test_a_value_outside_the_vocabulary_is_refused_rather_than_stored_dead(signed_in):
    """The API-level half of the same bug: `up` looks plausible, is accepted by
    a naive validator, and produces a watch that can never fire."""
    reply = client.post("/api/watches", headers={"X-Optic-CSRF": signed_in},
                        json={"symbol": "NVDA", "kind": "analyst_revisions",
                              "params": {"direction": "up"}})
    assert reply.status_code == 400
    assert "rising" in reply.json()["detail"]
    ok = client.post("/api/watches", headers={"X-Optic-CSRF": signed_in},
                     json={"symbol": "NVDA", "kind": "analyst_revisions",
                           "params": {"direction": "rising"}})
    assert ok.status_code == 200


@pytest.mark.parametrize("level", ["not-a-number", "", None])
def test_a_non_numeric_level_is_refused(level, signed_in):
    reply = client.post("/api/watches", headers={"X-Optic-CSRF": signed_in},
                        json={"symbol": "NVDA", "kind": "price_above",
                              "params": {"level": level}})
    assert reply.status_code == 400


def test_the_same_watch_twice_is_a_conflict_not_a_second_row(signed_in):
    body = {"symbol": "NVDA", "kind": "price_above", "params": {"level": 200}}
    assert client.post("/api/watches", headers={"X-Optic-CSRF": signed_in},
                       json=body).status_code == 200
    again = client.post("/api/watches", headers={"X-Optic-CSRF": signed_in}, json=body)
    assert again.status_code == 409
    assert "already watching" in again.json()["detail"]
    # A different level is a different watch.
    assert client.post("/api/watches", headers={"X-Optic-CSRF": signed_in},
                       json={"symbol": "NVDA", "kind": "price_above",
                             "params": {"level": 210}}).status_code == 200
    assert len(client.get("/api/watches").json()["watches"]) == 2


def test_params_are_serialised_with_sorted_keys_so_the_index_can_see_a_duplicate(signed_in):
    """Two equal dicts only serialise identically if the key order is forced."""
    from app.account import _params_key
    assert _params_key({"b": 1, "a": 2}) == _params_key({"a": 2, "b": 1})


def test_a_watch_can_be_paused_without_deleting_it(signed_in):
    made = client.post("/api/watches", headers={"X-Optic-CSRF": signed_in},
                       json={"symbol": "NVDA", "kind": "breakout"}).json()["watch"]
    off = client.patch("/api/watches/{}".format(made["id"]),
                       headers={"X-Optic-CSRF": signed_in}, json={"active": False})
    assert off.json()["watch"]["active"] is False
    on = client.patch("/api/watches/{}".format(made["id"]),
                      headers={"X-Optic-CSRF": signed_in}, json={"active": True})
    assert on.json()["watch"]["active"] is True


def test_watches_are_scoped_to_their_owner(signed_in):
    made = client.post("/api/watches", headers={"X-Optic-CSRF": signed_in},
                       json={"symbol": "NVDA", "kind": "breakout"}).json()["watch"]
    other = TestClient(main.app)
    other.post("/api/auth/register", json={
        "first_name": "B", "email": "other@example.com",
        "password": GOOD, "confirm_password": GOOD})
    csrf = other.cookies.get(config.CSRF_COOKIE)
    assert other.get("/api/watches").json()["watches"] == []
    assert other.delete("/api/watches/{}".format(made["id"]),
                        headers={"X-Optic-CSRF": csrf}).status_code == 404
    assert other.patch("/api/watches/{}".format(made["id"]),
                       headers={"X-Optic-CSRF": csrf},
                       json={"active": False}).status_code == 404
    assert len(client.get("/api/watches").json()["watches"]) == 1


def test_a_guest_cannot_store_watches_but_the_catalogue_stays_open():
    assert client.get("/api/watches").status_code == 401
    assert client.post("/api/watches", json={"symbol": "NVDA",
                                             "kind": "breakout"}).status_code == 401
    # The evaluator and the catalogue answer anybody, because a guest keeps
    # watches in localStorage and still needs them checked.
    assert client.get("/api/watches/catalogue").status_code == 200


def test_the_limit_is_enforced(signed_in, monkeypatch):
    import app.account as account_mod
    monkeypatch.setattr(account_mod, "MAX_WATCHES", 2)
    for level in (100, 200):
        assert client.post("/api/watches", headers={"X-Optic-CSRF": signed_in},
                           json={"symbol": "NVDA", "kind": "price_above",
                                 "params": {"level": level}}).status_code == 200
    refused = client.post("/api/watches", headers={"X-Optic-CSRF": signed_in},
                          json={"symbol": "NVDA", "kind": "price_above",
                                "params": {"level": 300}})
    assert refused.status_code == 403
    assert "which is the limit" in refused.json()["detail"]


# ------------------------------------------------------------ recording


def test_recording_a_trip_keeps_the_state_a_flip_is_measured_against(signed_in):
    """`_signal_flip` reports a state, not a transition, by design. The client
    detects the change by comparing against the last recorded state, so the
    state has to survive the round trip."""
    made = client.post("/api/watches", headers={"X-Optic-CSRF": signed_in},
                       json={"symbol": "NVDA", "kind": "signal_flip",
                             "params": {"to": "any"}}).json()["watch"]
    assert made["last_met_at"] is None

    recorded = client.post("/api/watches/seen", headers={"X-Optic-CSRF": signed_in},
                           json={"results": [{"id": made["id"], "met": True,
                                              "state": "bullish",
                                              "evidence": "stance reads bullish"}]})
    assert recorded.json()["recorded"] == 1
    after = client.get("/api/watches").json()["watches"][0]
    assert after["last_met_at"]
    assert after["last_evidence"]["state"] == "bullish"
    assert after["last_evidence"]["evidence"] == "stance reads bullish"


def test_a_watch_that_did_not_trip_is_not_recorded(signed_in):
    made = client.post("/api/watches", headers={"X-Optic-CSRF": signed_in},
                       json={"symbol": "NVDA", "kind": "breakout"}).json()["watch"]
    reply = client.post("/api/watches/seen", headers={"X-Optic-CSRF": signed_in},
                        json={"results": [{"id": made["id"], "met": False}]})
    assert reply.json()["recorded"] == 0
    assert client.get("/api/watches").json()["watches"][0]["last_met_at"] is None


def test_recording_cannot_touch_another_users_watch(signed_in):
    made = client.post("/api/watches", headers={"X-Optic-CSRF": signed_in},
                       json={"symbol": "NVDA", "kind": "breakout"}).json()["watch"]
    other = TestClient(main.app)
    other.post("/api/auth/register", json={
        "first_name": "B", "email": "other@example.com",
        "password": GOOD, "confirm_password": GOOD})
    csrf = other.cookies.get(config.CSRF_COOKIE)
    reply = other.post("/api/watches/seen", headers={"X-Optic-CSRF": csrf},
                       json={"results": [{"id": made["id"], "met": True,
                                          "evidence": "forged"}]})
    # Accepted, and matched nothing: the id is a filter alongside user_id.
    assert reply.status_code == 200
    assert client.get("/api/watches").json()["watches"][0]["last_met_at"] is None


def test_every_condition_in_the_catalogue_has_an_evaluator():
    """A catalogue entry with no evaluator is a condition the UI offers and the
    server reports as unknown."""
    assert set(watches.CONDITIONS) == set(watches.EVALUATORS)
    assert len(watches.CONDITIONS) == 10


def test_check_reports_one_row_per_watch_met_or_not():
    """"This was checked and did not fire" is what makes an empty result
    trustworthy rather than ambiguous."""
    payload = {"quote": {"price": 100.0, "change_pct": 1.0}}
    rows = watches.check(payload, [
        {"id": "a", "kind": "price_above", "params": {"level": 50}},
        {"id": "b", "kind": "price_above", "params": {"level": 500}},
        {"id": "c", "kind": "invented", "params": {}},
    ])
    assert [r["met"] for r in rows] == [True, False, False]
    assert "may have been removed" in rows[2]["reason"]


def test_no_em_dashes_in_the_copy_a_reader_sees():
    """House rule, from a deliberate pass over the whole terminal. It applies to
    the strings that reach a screen, not to the comments explaining them."""
    for kind, spec in watches.CONDITIONS.items():
        assert "—" not in (spec.get("why") or ""), kind
        assert "—" not in (spec.get("label") or ""), kind
        param = spec.get("param") or {}
        assert "—" not in (param.get("label") or ""), kind
        for choice in param.get("choices") or []:
            assert "—" not in choice["label"], (kind, choice)
    assert "—" not in watches.catalogue()["method"]

    # And the evidence strings the evaluators build.
    from datetime import date, timedelta
    evidence = watches._earnings_near(
        {"next_earnings_date": (date.today() + timedelta(days=70)).isoformat()},
        {"days": 90})
    assert evidence and "—" not in evidence["evidence"], evidence
