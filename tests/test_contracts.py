"""Federal contract awards, and the match that must not be a guess.

USAspending is the government's own record of what it awarded -- free, no key,
the same terms as the House Clerk's filings. The hard part is not fetching it,
it is deciding which recipient a listed company IS.

Measured against the live API while this was built: LMT resolves to LOCKHEED
MARTIN CORP ($60.5B lifetime, and its awards include Sikorsky, which is the
parent roll-up working); LDOS to LEIDOS HOLDINGS; AAPL and SBUX to nothing at
all, which is the correct answer. Asked for "Apple" the recipient search ranks
MAYER BROS. APPLE PRODUCTS INC. first, and for "Appledore" it returns a marine
engineering firm -- so a keyword match would have put a juice company's federal
contracts under AAPL.
"""

from __future__ import annotations

import re
from pathlib import Path

from app import contracts

ROOT = Path(__file__).resolve().parent.parent
SRC = (ROOT / "app/contracts.py").read_text()
MAIN = (ROOT / "app/main.py").read_text()
APP = (ROOT / "static/app.js").read_text()


class FakeAPI:
    """Stands in for USAspending. Records what it was asked."""

    def __init__(self, recipients=None, awards=None, fail=False):
        self.recipients = recipients if recipients is not None else []
        self.awards = awards if awards is not None else []
        self.fail = fail
        self.calls = []

    def __call__(self, url, body):
        self.calls.append((url, body))
        if self.fail:
            return None
        if url.endswith("/recipient/"):
            return {"results": self.recipients}
        return {"results": self.awards}


def _use(monkeypatch, api):
    monkeypatch.setattr(contracts, "_post", api)
    contracts._CACHE.clear()
    return api


# ------------------------------------------------- the match


def test_a_name_is_reduced_to_the_part_that_identifies_it():
    """"Lockheed Martin Corporation" and "LOCKHEED MARTIN CORP" are one company
    written two ways, and neither the filer nor the exchange is consistent.
    Without stripping suffixes an equality test matches nothing and the feature
    silently never works."""
    assert contracts.normalise("Lockheed Martin Corporation") == "LOCKHEED MARTIN"
    assert contracts.normalise("LOCKHEED MARTIN CORP") == "LOCKHEED MARTIN"
    assert contracts.normalise("Leidos Holdings, Inc.") == "LEIDOS"
    assert contracts.normalise("General Dynamics Corp.") == "GENERAL DYNAMICS"


def test_a_similar_name_is_not_a_match(monkeypatch):
    """The whole reason the rule is equality. Asked for "Apple", USAspending's
    recipient search returns companies that press them."""
    _use(monkeypatch, FakeAPI(recipients=[
        {"name": "MAYER BROS. APPLE PRODUCTS INC.", "uei": "X1", "recipient_level": "P",
         "amount": 9_000_000.0},
        {"name": "APPLEDORE MARINE ENGINEERING, LLC", "uei": "X2", "recipient_level": "P",
         "amount": 4_000_000.0},
    ]))
    out = contracts.for_company("Apple Inc.", "AAPL")
    assert out["matched"] is False
    assert out["awards"] == []
    assert "exact" in out["reason"]


def test_an_exact_name_is_a_match(monkeypatch):
    api = _use(monkeypatch, FakeAPI(
        recipients=[{"name": "LOCKHEED MARTIN CORP", "uei": "ZFN2", "recipient_level": "P",
                     "amount": 60_000_000_000.0}],
        awards=[{"Award ID": "N001", "Recipient Name": "LOCKHEED MARTIN CORPORATION",
                 "Awarding Agency": "Department of Defense", "Award Amount": 1234.0,
                 "Start Date": "2026-01-02", "generated_internal_id": "CONT_AWD_X"}]))
    out = contracts.for_company("Lockheed Martin Corporation", "LMT")
    assert out["matched"] is True
    assert out["recipient"] == "LOCKHEED MARTIN CORP"
    assert out["awards"][0]["amount"] == 1234.0
    # The awards call goes by UEI, never by name: measured, a name filter 504s
    # after sixty seconds at every window width tried.
    award_call = [b for (u, b) in api.calls if u.endswith("spending_by_award/")][0]
    assert award_call["filters"]["recipient_search_text"] == ["ZFN2"]


def test_the_parent_record_wins_over_a_subsidiary(monkeypatch):
    """A company's awards are spread across its subsidiaries and the parent is
    the roll-up -- Lockheed's real list includes Sikorsky because of this."""
    _use(monkeypatch, FakeAPI(recipients=[
        {"name": "LOCKHEED MARTIN CORP", "uei": "CHILD", "recipient_level": "C",
         "amount": 25_000_000_000.0},
        {"name": "LOCKHEED MARTIN CORPORATION", "uei": "PARENT", "recipient_level": "P",
         "amount": 60_000_000_000.0},
    ]))
    out = contracts.for_company("Lockheed Martin Corporation", "LMT")
    assert out["uei"] == "PARENT"


def test_a_name_too_short_to_be_distinctive_is_not_looked_up(monkeypatch):
    """Two letters would match half the register."""
    api = _use(monkeypatch, FakeAPI(recipients=[{"name": "CO", "uei": "X", "amount": 1.0}]))
    out = contracts.for_company("Co.", "XX")
    assert out["matched"] is False
    assert api.calls == [], "it must not even ask"


# ------------------------------------------------- what it reports


def test_matched_with_no_awards_is_not_the_same_as_unmatched(monkeypatch):
    """Collapsing them would tell a reader a company has no federal business
    when what happened is that this declined to guess which recipient it is."""
    _use(monkeypatch, FakeAPI(
        recipients=[{"name": "LEIDOS", "uei": "U", "recipient_level": "P", "amount": 1.0}],
        awards=[]))
    out = contracts.for_company("Leidos Holdings, Inc.", "LDOS")
    assert out["matched"] is True and out["awards"] == []
    assert "reason" not in out, "a match with no awards states no reason for failing"


def test_the_api_refusing_is_reported_not_raised(monkeypatch):
    """This API 504s under load and 502s on an expensive field. An exception
    would be the common case rather than the exceptional one, and the panel has
    to draw either way."""
    _use(monkeypatch, FakeAPI(fail=True))
    out = contracts.recent()
    assert out["available"] is False
    assert "reason" in out


def test_only_contract_awards_are_counted(monkeypatch):
    """Grants, loans and direct payments are a different question, and folding
    them in would put university research money beside a defence award under
    one heading."""
    api = _use(monkeypatch, FakeAPI())
    contracts.recent()
    body = api.calls[0][1]
    assert body["filters"]["award_type_codes"] == ["A", "B", "C", "D"]


def test_the_market_view_asks_for_new_awards_only(monkeypatch):
    """Otherwise a long-running contract's routine modification reappears every
    time it is touched, and the list is a log of paperwork rather than awards."""
    api = _use(monkeypatch, FakeAPI())
    contracts.recent()
    period = api.calls[0][1]["filters"]["time_period"][0]
    assert period["date_type"] == "new_awards_only"


def test_the_expensive_fields_are_not_requested():
    """Timed against the live API: NAICS 54.7s, Last Modified Date 58s, and
    Total Outlays 502'd outright, against 0.6s for the set below."""
    for costly in ("NAICS", "Total Outlays", "Last Modified Date"):
        assert costly not in contracts.FIELDS, costly


def test_it_says_what_an_award_is_not():
    """An obligation is not a payment, the figure is the whole contract rather
    than a year of it, and a prime's award says nothing about its suppliers."""
    low = contracts.CAVEAT.lower()
    assert "not what has been paid" in low
    assert "subcontract" in low


# ------------------------------------------------- cost


def test_a_repeat_read_is_served_from_the_cache(monkeypatch):
    api = _use(monkeypatch, FakeAPI())
    contracts.recent()
    n = len(api.calls)
    contracts.recent()
    assert len(api.calls) == n, "the second read must not hit the API"


def test_a_failure_is_not_cached_for_the_full_hour(monkeypatch):
    """A federal API that is down should not get one call per page view, and
    should not be written off for an hour either."""
    fn = SRC.split("def _cached(", 1)[1].split("\ndef ", 1)[0]
    assert "time.time() - TTL + 120" in fn


# ------------------------------------------------- the endpoint and the page


def test_the_symbol_is_resolved_locally():
    """A dictionary lookup against a list this app already keeps, where a quote
    would be a network call to learn a name that does not change."""
    fn = MAIN[MAIN.index('@app.get("/api/contracts")'):]
    fn = fn[:fn.index("\n@app.")]
    assert "universe_mod.search(sym, 5)" in fn
    assert "contracts_mod.for_company" in fn
    assert "contracts_mod.recent" in fn


def test_the_panel_sits_with_the_other_two_regimes():
    """A member of Congress buying a defence contractor and that contractor
    winning a defence award are the same question asked at both ends."""
    facet = re.search(r"function renderCongressFacet\(\) \{.*?\n\}", APP, re.S).group()
    assert "renderContracts()" in facet
    loader = re.search(r"function loadInsiders\(force\) \{.*?\n\}", APP, re.S).group()
    assert "loadContracts(force)" in loader


def test_the_panel_distinguishes_no_match_from_no_awards():
    fn = re.search(r"function renderContracts\(\) \{.*?\n\}", APP, re.S).group()
    assert "c.matched" in fn
    assert "c.reason" in fn
