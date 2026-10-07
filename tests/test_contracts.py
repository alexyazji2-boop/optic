"""Federal contract awards, and the match that must not be a guess.

USAspending is the government's own record of what it awarded -- free, no key,
the same terms as the House Clerk's filings. The hard part is not fetching it,
it is deciding which recipient a listed company IS.

Measured against the live API while this was built: LMT resolves to LOCKHEED
MARTIN CORP ($60.5B, which is its last twelve months of contracts rather than
the lifetime figure it was taken for; its awards include Sikorsky, which is the
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


# ------------------------------------------------- in the order they were awarded


AWARDS = [
    {"Award ID": "A", "Recipient Name": "TRIWEST", "Award Amount": 1.2e9,
     "Base Obligation Date": "2026-09-23", "Start Date": "2026-08-01"},
    {"Award ID": "B", "Recipient Name": "CLARK", "Award Amount": 3.3e8,
     "Base Obligation Date": "2026-09-26", "Start Date": "2026-09-26"},
    {"Award ID": "C", "Recipient Name": "TUTOR PERINI", "Award Amount": 3.1e8,
     "Base Obligation Date": "2026-09-11", "Start Date": "2026-09-11"},
    {"Award ID": "D", "Recipient Name": "MORTENSON", "Award Amount": 2.4e8,
     "Base Obligation Date": "2026-09-22", "Start Date": "2026-12-01"},
]


def test_the_largest_awards_are_listed_newest_first(monkeypatch):
    """Asked for as "make sure that these are in chronological order". The API
    is still asked for the largest; the rows are listed by the day each was
    signed. They were in amount order and dated by the work's start, so the
    list read 23, 26, 11, 25, 22 September with a December 1 among them."""
    api = _use(monkeypatch, FakeAPI(awards=AWARDS))
    out = contracts.recent()
    assert api.calls[0][1]["sort"] == "Award Amount"
    assert [a["award_id"] for a in out["awards"]] == ["B", "A", "D", "C"]
    assert out["awards"][2]["awarded"] == "2026-09-22" and out["awards"][2]["start"] == "2026-12-01"


def test_a_company_lists_its_largest_awards_newest_first(monkeypatch):
    _use(monkeypatch, FakeAPI(
        recipients=[{"name": "LOCKHEED MARTIN CORP", "uei": "U", "recipient_level": "P", "amount": 4.67e10}],
        awards=AWARDS))
    out = contracts.for_company("Lockheed Martin Corporation", "LMT")
    assert [a["award_id"] for a in out["awards"]] == ["B", "A", "D", "C"]
    assert out["amount_12m"] == 4.67e10 and "lifetime_amount" not in out


def test_the_award_date_is_asked_for_and_was_timed():
    """Timed 2026-10-07 against the live API: 0.57s market-wide and 0.64s by
    UEI with it, 0.74s without."""
    assert "Base Obligation Date" in contracts.FIELDS
    assert "Base Obligation Date" in SRC.split("def _award_row(", 1)[1].split("\ndef ", 1)[0]


def test_the_twelve_month_total_is_called_that():
    """With award_type "contracts" the recipient list ranks on its
    last_12_contracts column. Printed "in all", it put Lockheed's $46.7B total
    beside a single $48.1B award from 1993."""
    fn = APP[APP.index("function renderContracts() {"):]
    fn = fn[:fn.index("\n}\n")]
    assert "in contracts over the last 12 months" in fn and "in all" not in fn
    assert "c.amount_12m" in fn


def _jsc(script):
    import json
    import os
    import shutil
    import subprocess
    import pytest
    jsc = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
    exe = jsc if os.path.exists(jsc) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")

    def fn(head):
        at = APP.index(head)
        return APP[at:APP.index("\n}\n", at) + 3]
    src = ("function esc(s) { return String(s); }\n"
           + fn("function contractDate(iso) {") + fn("function contractWhen(a) {") + script)
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    assert "RESULT:" in out.stdout, (out.stdout + out.stderr)[-2000:]
    return json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])


def test_the_row_is_dated_by_the_award_with_a_later_start_under_it():
    """Checked in a browser at 1440x900: the market list read Sep 30 down to
    Sep 9 with "work from Dec 1" under Mortenson's Sep 22, the table 1,125px in
    a 1,125px box; LMT's twelve ran Jun 28, 2024 back to Apr 30, 1984, which
    had read "Apr 30" with no year."""
    out = _jsc("""
      var y = new Date().getFullYear();
      print('RESULT:' + JSON.stringify([
        contractWhen({ awarded: y + '-09-22', start: y + '-12-01' }),
        contractWhen({ awarded: y + '-09-15', start: y + '-09-21' }),
        contractWhen({ awarded: y + '-09-23', start: y + '-08-01' }),
        contractWhen({ awarded: '1993-10-15', start: '1993-10-15' }),
        contractWhen({ start: y + '-10-01' }),
      ]));
    """)
    later, soon, before, old, undated = out
    assert later == 'Sep 22<span class="ct-later">work from Dec 1</span>'
    assert soon == "Sep 15", "a start six days on is not worth a second date"
    assert before == "Sep 23", "work begun before the signature is not a later start"
    assert old == "Oct 15, 1993"
    assert undated == '<span class="ct-later">work from Oct 1</span>'


def test_the_date_leads_the_row_and_the_header():
    row = APP[APP.index("function contractRow(a) {"):]
    row = row[:row.index("\n}\n")]
    assert row.index('class="ct-awarded"') < row.index('class="name ct-who"')
    assert "<thead><tr><th>Awarded</th>" in APP
    css = (ROOT / "static/styles.css").read_text()
    assert "table.ct-table td.ct-agency { white-space: normal; min-width: 18ch; }" in css
    assert "table.ct-table td.ct-awarded::before { content: 'Awarded '; }" in css
