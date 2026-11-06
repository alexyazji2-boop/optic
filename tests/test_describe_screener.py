"""Handoff 8 of the owner's handover pack (2026-11-03): the Describe-It screener, a request in English read as filters
the reader can see and change before anything runs.

What existed, verified first: Scan's "Find stocks" read a request with fixed rules (app/analytics/scan_request.py) and
Milo for words they left over, then ran it at once, with no step to look at the reading; vague words became fixed
thresholds; leftover words were listed one by one; results gave a ranking's age but no date for the data, no
fingerprint and no record; nothing could be saved. The screener had no fundamentals at all (a price-and-volume
ranking of NASDAQ stocks), so the handoff's own example, "positive revenue growth and below-average debt ratios",
could not be expressed.

Now: POST /api/screener/read proposes filters in plain English with their periods and names each phrase nothing can
screen for; the reader edits and presses Run; revenue growth and the debt ratio come from SEC's XBRL frames for the
whole universe (app/analytics/sec_frames.py); a "below average" bound is the universe's median, said with its value;
every result says its filters, universe, dates, sources and fingerprint, every run is kept (screen_log.py), an empty
result names the filter that emptied it with a looser bound to approve, and a screen saves to the library and runs
again from there. SEC and the ranking are stood in here; no test reaches the network.
"""
from __future__ import annotations

import datetime as dt
import json

import pytest
from fastapi.testclient import TestClient

import app.main as m
from app import library
from app.analytics import scan_request, screen_log, screener, sec_frames
from app.auth import config
from tests.test_frontend_v2_stage0 import V2, _run
from tests.test_research_library import GOOD

JS = V2 / "js"
SCAN = (JS / "pages/scan.js").read_text()
CSS = (V2 / "css/pages.css").read_text()
EXAMPLE = "Positive revenue growth and below-average debt ratios"
TODAY = dt.date(2026, 11, 4)

# A universe of 40 stocks, as the ranking keeps them, and SEC's figures for 36 of them (four file outside US GAAP)
SYMS = ["S{:02d}".format(i) for i in range(40)]


def ranking():
    rows = [{"symbol": s, "price": 20 + i, "dollar_volume": 5e7 + i * 1e6, "roc20": i - 20, "roc60": (i - 20) * 1.5,
             "range_position": i / 40, "atr_pct": 2.0, "volume_expansion": 1.0, "score": 40 - i, "chg1d": 0.1,
             "sma20": 20 + i, "sma50": 19 + i, "sma200": 18 + i} for i, s in enumerate(SYMS)]
    return {"ranked": rows, "universe_size": 120, "passed": 40, "ranked_at": 1_793_800_000.0, "bars_through": "2026-11-03",
            "gates": {"min_price": 5.0, "min_dollar_volume": 2e7}}


def fake_frames():
    """SEC's frames as sec_frames.build reads them: revenue under two tags across 2025 and 2024, and a balance sheet
    where most companies tag total liabilities and a few only liabilities-and-equity and equity."""
    cik = {s: 1000 + i for i, s in enumerate(SYMS)}
    rev = {"RevenueFromContractWithCustomerExcludingAssessedTax": {}, "Revenues": {}}
    for i, s in enumerate(SYMS[:36]):
        tag = "Revenues" if i % 5 == 0 else "RevenueFromContractWithCustomerExcludingAssessedTax"
        before = 100.0 + i
        growth = (i - 12) / 100.0                       # S00 to S11 shrank, S12 flat, S13 on grew
        rev[tag].setdefault("CY2024", []).append({"cik": cik[s], "end": "2024-12-31", "val": before})
        rev[tag].setdefault("CY2025", []).append({"cik": cik[s], "end": "2025-12-31", "val": before * (1 + growth)})
    bs = {"Assets": [], "Liabilities": [], "LiabilitiesAndStockholdersEquity": [], "StockholdersEquity": []}
    for i, s in enumerate(SYMS[:36]):
        bs["Assets"].append({"cik": cik[s], "end": "2026-06-30", "val": 1000.0})
        ratio = 0.2 + i * 0.015
        if i % 7 == 0:   # no total-liabilities tag: worked out from liabilities-and-equity less equity
            bs["LiabilitiesAndStockholdersEquity"].append({"cik": cik[s], "end": "2026-06-30", "val": 1000.0})
            bs["StockholdersEquity"].append({"cik": cik[s], "end": "2026-06-30", "val": 1000.0 * (1 - ratio)})
        else:
            bs["Liabilities"].append({"cik": cik[s], "end": "2026-06-30", "val": 1000.0 * ratio})

    def frame(concept, unit, period):
        if concept in rev:
            return rev[concept].get(period, [])
        return bs.get(concept, []) if period == "CY2026Q2I" else []
    return frame, (lambda: {v: [k] for k, v in cik.items()})


@pytest.fixture
def stood_in(monkeypatch):
    rk = ranking()
    monkeypatch.setattr(m, "_cached_ranking", lambda: rk)
    monkeypatch.setattr(m, "_ensure_ranking", lambda r: None)
    frame, tickers = fake_frames()
    data = sec_frames.build(TODAY, frame=frame, tickers=tickers)
    monkeypatch.setattr(sec_frames, "ensure", lambda today=None, background=True: data)
    monkeypatch.setattr(m, "_spend_guard", lambda request: None)
    # the rules alone: a request with words they leave over would otherwise go to the model
    monkeypatch.setattr(m.ai, "available", lambda: {"enabled": False})
    return {"ranking": rk, "fund": data}


client = TestClient(m.app)


def read(text):
    r = client.post("/api/screener/read", json={"text": text})
    assert r.status_code == 200, r.text
    return r.json()


def run(spec, text=""):
    r = client.post("/api/screener", json=dict(spec, text=text, limit=200))
    assert r.status_code == 200, r.text
    return r.json()


def spec_of(prop):
    keep = ("field", "min", "max", "min_exclusive", "max_exclusive", "min_peer", "max_peer")
    # `is not`, not `not in (None, False)`: a minimum of 0 equals False in Python and would be dropped
    return {"filters": [{k: f[k] for k in keep if f.get(k) is not None and f.get(k) is not False} for f in prop["filters"]],
            "states": [s["id"] for s in prop["states"]], "sort": prop["sort"], "direction": prop["direction"]}


# ---------------------------------------------------------------- the four acceptance tests


def test_acceptance_1_the_example_reads_as_visible_editable_filters_and_reruns_the_same(stood_in):
    prop = read(EXAMPLE)
    assert prop["read_by"] == "terminal" and prop["unmapped"] == [], "every phrase read, at no cost"
    said = [f["said"] for f in prop["filters"]]
    assert said == ["Revenue growth above 0% (the latest fiscal year in SEC's filings against the year before)",
                    "Debt ratio below the universe's median (total liabilities over total assets, on the latest "
                    "balance sheet in SEC's filings)"]
    assert prop["filters"][0]["min"] == 0 and prop["filters"][0]["min_exclusive"] is True
    assert prop["filters"][1]["max_peer"] == "median" and prop["needs_fundamentals"] is True
    # the page shows each one in plain English with its own controls, and nothing runs until Run
    review = SCAN[SCAN.index("function review() {"):SCAN.index("const fmtDay")]
    assert "<p class=\"ds-said\">${plainOf(f, fd)}</p>" in review and "data-ds-min=" in review and "data-ds-del=" in review
    assert "data-ds-peer=" in review and "Against the universe's median" in review and "data-ds-run" in review
    read_fn = SCAN[SCAN.index("async function readRequest(text) {"):SCAN.index("async function runDescribed(")]
    assert "/api/screener/read" in read_fn and "/api/screener'" not in read_fn, "reading runs nothing"

    first = run(spec_of(prop), EXAMPLE)
    assert first["available"] and first["filters_said"][0].startswith("Revenue growth above 0%")
    # the result says what it ran on: the universe, the dates, the median it came to and over how many, the sources
    assert first["universe"] == 120 and first["considered"] == 40
    assert first["as_of"]["bars_through"] == "2026-11-03"
    assert first["as_of"]["fundamentals"]["periods"] == {"revenue_year": 2025, "revenue_prior": 2024,
                                                         "balance_end": "2026-06-30", "balance_frame": "CY2026Q2I"}
    peer = first["peers"][0]
    assert peer["basis"] == "median" and peer["of"] == 36 and peer["value"] == pytest.approx(46.25, abs=0.01)
    assert "SEC EDGAR XBRL frames" in first["sources"]["fundamental"] and "Yahoo Finance" in first["sources"]["price"]
    # S13 to S35 grew; below the median debt ratio leaves those under 46.25%: S13 to S17
    assert set(first["symbols"]) == {"S13", "S14", "S15", "S16", "S17"}
    assert set(first["symbols"]) <= set(SYMS), "no invented tickers"
    # the same filters on the same data: the same list, the same fingerprint, both runs kept
    again = run(spec_of(prop), EXAMPLE)
    assert again["symbols"] == first["symbols"] and again["fingerprint"] == first["fingerprint"]
    kept = screen_log.runs(first["fingerprint"])
    assert len(kept) >= 2 and all(r["symbols"] == first["symbols"] for r in kept)
    assert kept[-1]["text"] == EXAMPLE and kept[-1]["peers"][0]["value"] == peer["value"]


def test_acceptance_2_a_phrase_nothing_can_screen_for_is_flagged_never_guessed(stood_in):
    prop = read("Companies with a strong moat and low debt")
    assert prop["unmapped"] == ["strong moat"]
    assert [f["field"] for f in prop["filters"]] == ["debt_ratio"] and prop["states"] == [], "'strong' read as no trend"
    nothing = read("great management and a wide moat")
    assert nothing["filters"] == [] and nothing["states"] == [] and len(nothing["unmapped"]) == 2
    # with nothing to screen on, no list: the page says so and offers the builder, never a guessed screen
    assert "Nothing in that could be read as a filter. Build one yourself, or describe it another way." in SCAN
    assert "data-ds-build>Open in Build a screen</button>" in SCAN
    # what a reading can hold is the screener's own vocabulary: an invented field never reaches a run
    assert screener.parse_filters([{"field": "moat_width", "min": 1}]) == []
    res = run({"filters": [{"field": "debt_ratio", "max_peer": "median"}], "states": [], "sort": "score", "direction": "desc"})
    assert set(res["symbols"]) <= set(SYMS)
    for text in ("cheap stocks with high dividends", "strong balance sheets", "good products"):
        assert not read(text)["filters"], text


def test_acceptance_3_an_empty_result_names_the_filter_that_emptied_it_and_offers_a_looser_bound(stood_in):
    res = run({"filters": [{"field": "roc60", "min": -100}, {"field": "revenue_growth", "min": 500.0}], "states": [],
               "sort": "score", "direction": "desc"})
    assert res["matched"] == 0
    b = res["binding"]
    assert b["field"] == "revenue_growth" and b["reached"] == 40
    assert b["said"].startswith("Revenue growth at least 500%")
    # the looser bound lets five of the stocks that reached the filter through it, and is only proposed
    assert b["keeps"] == 5 and b["suggest"]["min"] == pytest.approx(19.0, abs=0.01)
    loosened = run({"filters": [{"field": "roc60", "min": -100}, b["suggest"]], "states": [], "sort": "score", "direction": "desc"})
    assert loosened["matched"] == 5
    page = SCAN[SCAN.index("function resultView() {"):SCAN.index("async function readRequest")]
    assert "The filter that left nothing: ${b.said}" in page and "data-ds-loosen>Use this bound</button>" in page
    assert "It changes the filter above; nothing runs until you press Run." in page
    loosen = SCAN[SCAN.index("if (t('[data-ds-loosen]')) {"):SCAN.index("if (t('[data-ds-build]'))")]
    assert "runDescribed" not in loosen, "approving the looser bound edits the filter; it does not run"


def test_acceptance_4_a_saved_screen_reopens_from_the_library_and_runs_again(stood_in, accounts, tmp_path):
    http = TestClient(m.app)
    http.post("/api/auth/register", json={"first_name": "A", "last_name": "B", "email": "screens@example.com",
                                          "password": GOOD, "confirm_password": GOOD})
    headers = {"X-Optic-CSRF": http.cookies.get(config.CSRF_COOKIE)}
    prop = read(EXAMPLE)
    spec = spec_of(prop)
    first = run(spec, EXAMPLE)
    body = {"kind": "screen", "tickers": [], "screen": dict(spec, text=EXAMPLE), "name": "Growers with light debt",
            "summary": {"text": EXAMPLE, "said": first["filters_said"]}}
    saved = http.post("/api/library", headers=headers, json=body)
    assert saved.status_code == 200, saved.text
    item = saved.json()["item"]
    assert item["kind"] == "screen" and item["tickers"] == [] and item["ref"]["screen"]
    # the two sides key a screen the same way, so Save knows it is saved
    key = _run(tmp_path, f"""
      const L = await import('{(JS / "core/library.js").as_posix()}');
      print(JSON.stringify({{ key: L.screenKey({json.dumps(spec)}), route: L.routeOf({{ kind: 'screen', id: '{item["id"]}', tickers: [] }}) }}));
    """)
    assert key["key"] == item["ref"]["screen"] == library.fnv1a(library.screen_canonical(spec))
    assert key["route"] == "#/scan?saved={}".format(item["id"])
    assert http.post("/api/library", headers=headers, json=body).status_code == 409, "the same screen is not saved twice"
    # reopened: the saved filters, exactly, and run again they give the same list
    full = http.get("/api/library/{}".format(item["id"])).json()["item"]
    assert full["screen"]["text"] == EXAMPLE
    assert [{k: v for k, v in f.items() if v is not None} for f in full["screen"]["filters"]] == spec["filters"]
    rerun = run({k: full["screen"][k] for k in ("filters", "states", "sort", "direction")})
    assert rerun["symbols"] == first["symbols"] and rerun["fingerprint"] == first["fingerprint"]
    listed = http.get("/api/library?kind=screen").json()
    assert [x["name"] for x in listed["items"]] == ["Growers with light debt"] and listed["counts"]["screen"] == 1
    assert "if (prm.saved) openSaved(String(prm.saved));" in SCAN and "paint(); runDescribed();" in SCAN
    # another account cannot open it
    other = TestClient(m.app)
    other.post("/api/auth/register", json={"first_name": "C", "last_name": "D", "email": "other@example.com",
                                           "password": GOOD, "confirm_password": GOOD})
    assert other.get("/api/library/{}".format(item["id"])).status_code == 404


# ---------------------------------------------------------------- the edge cases


def test_sec_frames_reads_both_measures_with_their_periods_and_never_estimates():
    frame, tickers = fake_frames()
    data = sec_frames.build(TODAY, frame=frame, tickers=tickers)
    by = data["by_ticker"]
    assert data["coverage"] == {"revenue_growth": 36, "debt_ratio": 36}
    assert "revenue_growth" not in by.get("S38", {}) and "debt_ratio" not in by.get("S38", {}), "no figure is none"
    assert by["S13"]["revenue_growth"] == pytest.approx(1.0) and by["S00"]["revenue_period"]["tag"] == "Revenues"
    assert by["S07"]["debt_ratio"] == pytest.approx(30.5) and by["S07"]["debt_period"]["how"].startswith("LiabilitiesAndStockholdersEquity")
    # which frames are complete: last year's from May, the year before until then; a quarter-end at least 75 days back
    assert sec_frames.periods(dt.date(2026, 11, 4)) == {"revenue_year": 2025, "revenue_prior": 2024,
                                                        "balance_end": "2026-06-30", "balance_frame": "CY2026Q2I"}
    assert sec_frames.periods(dt.date(2026, 3, 1))["revenue_year"] == 2024
    assert sec_frames.periods(dt.date(2026, 1, 20))["balance_frame"] == "CY2025Q3I"


def test_the_first_screen_of_the_day_waits_for_secs_figures_and_shows_nothing_partial(monkeypatch):
    monkeypatch.setattr(m, "_cached_ranking", ranking)
    monkeypatch.setattr(m, "_ensure_ranking", lambda r: None)
    monkeypatch.setattr(sec_frames, "ensure", lambda today=None, background=True: None)
    monkeypatch.setattr(sec_frames, "status", lambda: {"running": True, "started": 1.0, "error": None})
    res = run({"filters": [{"field": "revenue_growth", "min": 0}], "states": [], "sort": "score", "direction": "desc"})
    assert res["available"] is False and res["building"]["what"] == "sec" and "nothing partial is shown" in res["reason"]
    assert "rows" not in res
    monkeypatch.setattr(sec_frames, "status", lambda: {"running": False, "started": 1.0, "error": "403"})
    failed = run({"filters": [{"field": "debt_ratio", "max": 50}], "states": [], "sort": "score", "direction": "desc"})
    assert failed["available"] is False and failed["retry"] is True and "Nothing was screened" in failed["reason"]
    # a screen with no fundamentals never waits for SEC
    plain = run({"filters": [{"field": "roc60", "min": 0}], "states": [], "sort": "score", "direction": "desc"})
    assert plain["available"] and plain["as_of"]["fundamentals"] is None
    # the page asks again every 5 seconds while it builds, and Stop waiting ends that
    assert "whenBuilt(S.run && S.run.building && !S.stopped, () => runDescribed(true));" in SCAN
    assert "data-ds-stop>Stop waiting</button>" in SCAN


def test_a_peer_bound_can_be_the_mean_and_is_strict(stood_in):
    res = run({"filters": [{"field": "debt_ratio", "max_peer": "mean"}], "states": [], "sort": "score", "direction": "desc"})
    p = res["peers"][0]
    assert p["basis"] == "mean" and p["of"] == 36
    assert all(stood_in["fund"]["by_ticker"][s]["debt_ratio"] < p["value"] for s in res["symbols"])
    assert screener.plain({"field": "debt_ratio", "max_peer": "mean"}).startswith("Debt ratio below the universe's mean")


def test_the_reading_and_the_page_say_a_filter_the_same_way(tmp_path):
    cat = screener.describe()
    cases = [{"field": "revenue_growth", "min": 0, "min_exclusive": True}, {"field": "debt_ratio", "max_peer": "median"},
             {"field": "price", "min": None, "max": 20}, {"field": "pct_from_sma200", "min": -3, "max": 3},
             {"field": "volume_expansion", "min": 1.3}, {"field": "range_position", "min": 90}]
    got = _run(tmp_path, f"""
      const P = await import('{(JS / "pages/scan.js").as_posix()}');
      const cat = {json.dumps(cat)};
      print(JSON.stringify({json.dumps(cases)}.map((f) => P.plainOf(f, cat.fields.find((x) => x.id === f.field), cat.period_words))));
    """)
    assert got == [screener.plain(f) for f in cases]


def test_the_result_carries_its_universe_dates_sources_disclaimer_and_pages(stood_in):
    pin = SCAN[SCAN.index("function pinned(r) {"):SCAN.index("function resultView() {")]
    for part in ("<dt>Filters</dt>", "<dt>Universe</dt>", "<dt>As of</dt>", "<dt>Compared with</dt>", "<dt>Sources</dt>",
                 "<dt>Screen</dt>", "the same filters on the same data give the same list",
                 "in SEC's US-GAAP filings (most file in IFRS or are funds), so this filter cannot pass them",
                 "A small universe: only ${r.considered} stocks were screened."):
        assert part in pin, part
    view = SCAN[SCAN.index("function resultView() {"):SCAN.index("async function readRequest")]
    assert "Screening is not investment advice: being on a list is not a recommendation. Check the figures before acting on them." in view
    assert "data-ds-more>Show ${Math.min(PAGE, r.rows.length - shown.length)} more</button>" in view and "const PAGE = 25;" in SCAN
    assert "saveButton('screen', `screen:${lib.screenKey(specOf(S.prop))}`, { label: 'Save screen' })" in view
    # on a phone each filter stacks above its controls, and the pinned facts stack too
    assert "@media (max-width: 640px) { .ds-pin > div { grid-template-columns: 1fr; gap: 2px; } .ds-edit .field { flex: 1 1 5em; } }" in CSS
    # a result is in a deterministic order: the symbol breaks ties, every run
    a = run({"filters": [], "states": ["above_sma50"], "sort": "atr_pct", "direction": "desc"})
    b = run({"filters": [], "states": ["above_sma50"], "sort": "atr_pct", "direction": "desc"})
    assert a["symbols"] == b["symbols"] == sorted(a["symbols"])


def test_the_screen_log_keeps_runs_without_the_reader_and_trims_itself(tmp_path, monkeypatch):
    monkeypatch.setattr(screen_log, "LOG_PATH", str(tmp_path / "runs.jsonl"))
    monkeypatch.setattr(screen_log, "_COUNT", {"path": None, "lines": 0})
    monkeypatch.setattr(screen_log, "MAX_LINES", 10)
    monkeypatch.setattr(screen_log, "KEEP", 4)
    for i in range(12):
        screen_log.record({"available": True, "fingerprint": "f{}".format(i), "symbols": ["S01"], "filters": []}, "words")
    rows = screen_log.runs()
    assert 4 <= len(rows) <= 10 and rows[-1]["fingerprint"] == "f11"
    assert not any(k in rows[-1] for k in ("user", "user_id", "email", "ip"))
    screen_log.record({"available": False}, "x")
    assert screen_log.runs()[-1]["fingerprint"] == "f11", "a screen that did not run is not a run"
