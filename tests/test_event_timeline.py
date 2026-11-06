"""Handoff 9 (owner's handover pack, 2026-11-03): the Company Event Timeline.

The four acceptance tests, each named for it, then the edge cases. Every source is stood in: the provider (news,
earnings, insiders, analyst actions), the House archive and SEC EDGAR, so no feed is reached. The clock is pinned to
Wednesday 4 Nov 2026, 4 PM New York time."""
import datetime as dt
import json
import re
import time

import pytest
from fastapi.testclient import TestClient

import app.main as m
from app import session as session_mod, timeline
from app.analytics import congress as congress_mod, filings as filings_mod
from app.providers import yf as yf_mod
from tests.test_frontend_v2_stage0 import V2, _run

NOW = dt.datetime(2026, 11, 4, 21, 0, tzinfo=dt.timezone.utc)
TODAY = dt.date(2026, 11, 4)
JS = V2 / "js"

NEWS = [
    {"id": "n1", "title": "Apple cuts employee AI budgets as costs climb", "summary": "Apple told engineers to lower daily AI spending.",
     "publisher": "Investing.com", "published": "2026-11-04T20:32:00+00:00", "url": "https://example.com/apple-ai-budgets"},
    # the same story twice in the feed: one entry
    {"id": "n1b", "title": "Apple cuts employee AI budgets as costs climb", "summary": "", "publisher": "Investing.com",
     "published": "2026-11-04T20:32:00+00:00", "url": "https://example.com/apple-ai-budgets"},
    # 2 AM UTC on Nov 4 is Nov 3 in New York
    {"id": "n2", "title": "Apple supplier earnings beat estimates", "summary": "", "publisher": "Barrons.com",
     "published": "2026-11-04T02:00:00+00:00", "url": "https://example.com/apple-supplier"},
    {"id": "n3", "title": "Apple reports fourth-quarter results", "summary": "Apple posted record revenue.",
     "publisher": "Reuters", "published": "2026-10-30T20:35:00+00:00", "url": "https://example.com/apple-results"},
]
HISTORY = [
    {"date": "2027-01-28", "timing": None, "at": None, "eps_estimate": 2.40, "eps_reported": None, "surprise_pct": None},
    {"date": "2026-10-30", "timing": "after_close", "at": "2026-10-30T20:30:00+00:00", "eps_estimate": 1.77,
     "eps_reported": 1.85, "surprise_pct": 4.52},
    {"date": "2026-07-31", "timing": "after_close", "at": "2026-07-31T20:30:00+00:00", "eps_estimate": 1.43,
     "eps_reported": 1.57, "surprise_pct": 9.79},
    {"date": "2026-05-01", "timing": "after_close", "at": None, "eps_estimate": 1.62, "eps_reported": 1.65,
     "surprise_pct": 1.85},
]
INSIDERS = {"summary_6m": {}, "transactions": [
    {"insider": "COOK TIMOTHY D", "position": "Chief Executive Officer", "date": "2026-10-02", "shares": 129963.0,
     "value": 33300000.0, "action": "sale", "detail": "Sale at price 255.00 - 258.00 per share."},
    {"insider": "KHAN SABIH", "position": "Chief Operating Officer", "date": "2026-10-01", "shares": 99878.0,
     "value": None, "action": "other", "detail": ""},
    {"insider": "LEVINSON ARTHUR D", "position": "Director", "date": "2026-08-20", "shares": 1000.0,
     "value": 230000.0, "action": "purchase", "detail": "Purchase at price 230.00 per share."},
    {"insider": "MAESTRI LUCA", "position": "Officer", "date": "2026-01-05", "shares": 5000.0, "value": 1.0e6,
     "action": "sale", "detail": "Sale at price 200.00 per share."},
]}
ACTIONS = [
    {"at": "2026-11-03T14:12:00+00:00", "firm": "Barclays", "to_grade": "Underweight", "from_grade": "Underweight",
     "action": "main", "pt_action": "Raises", "pt": 261.0, "prior_pt": 245.0},
    {"at": "2026-10-20T13:46:00+00:00", "firm": "Loop Capital", "to_grade": "Hold", "from_grade": "Buy",
     "action": "down", "pt_action": "Lowers", "pt": 330.0, "prior_pt": 370.0},
    # midnight UTC: a dated record with no time, kept on its own day
    {"at": "2026-09-15T00:00:00+00:00", "firm": "Needham", "to_grade": "Hold", "from_grade": "", "action": "init",
     "pt_action": "", "pt": None, "prior_pt": None},
]
HOUSE = [
    {"ticker": "AAPL", "member": "Hon. Pete Sessions", "district": "TX17", "filed": "2026-10-27", "traded": "09/30/2026",
     "traded_iso": "2026-09-30", "side": "sell", "transaction": "sale", "amount_low": 250001, "amount_high": 500000,
     "owner": "SP", "description": None, "doc_id": "20031234", "date_suspect": False, "disclosure_lag_days": 27,
     "source_url": "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2026/20031234.pdf"},
    {"ticker": "AAPL", "member": "Hon. Kevin Hern", "district": "OK01", "filed": "2026-10-01", "traded": "07/20/2026",
     "traded_iso": "2026-07-20", "side": "buy", "transaction": "purchase", "amount_low": 1001, "amount_high": 15000,
     "owner": None, "description": "Purchased 40 shares.", "doc_id": "20031111", "date_suspect": False,
     "disclosure_lag_days": 73, "source_url": "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2026/20031111.pdf"},
    {"ticker": "AAPL", "member": "Hon. Jane Roe", "district": "CA12", "filed": "2026-09-10", "traded": "12/26/2026",
     "traded_iso": "2026-12-26", "side": "sell", "transaction": "partial sale", "amount_low": 15001,
     "amount_high": 50000, "owner": "JT", "description": None, "doc_id": "20030001", "date_suspect": True,
     "disclosure_lag_days": None,
     "source_url": "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2026/20030001.pdf"},
]
EDGAR = "https://www.sec.gov/Archives/edgar/data/320193/"
FILINGS = [
    {"form": "10-K", "filed": "2026-10-31", "items": "", "what": "Annual report", "url": EDGAR + "000032019326000105/aapl-20260926.htm"},
    {"form": "8-K", "filed": "2026-10-30", "items": "2.02,9.01",
     "what": "Material event: results of operations; financial statements and exhibits",
     "url": EDGAR + "000032019326000103/aapl-8k.htm"},
    # the same filing listed twice: one entry
    {"form": "8-K", "filed": "2026-10-30", "items": "2.02,9.01",
     "what": "Material event: results of operations; financial statements and exhibits",
     "url": EDGAR + "000032019326000103/aapl-8k.htm"},
    {"form": "10-Q", "filed": "2026-08-01", "items": "", "what": "Quarterly report", "url": EDGAR + "000032019326000090/aapl-20260627.htm"},
]


class StandIn:
    """The provider's calls the timeline makes, answering for AAPL (and nothing for anything else). A failing call
    fails through the provider's own cache, as the real one does: caught and read as empty."""

    def __init__(self, fail=(), slow=()):
        self.fail, self.slow = set(fail), set(slow)

    def _through_cache(self, key, value):
        if key.split(":")[0] in self.fail:
            if key.startswith("news"):
                try:
                    return yf_mod._cached(key, 1, self._refuse)
                except Exception:                        # noqa: BLE001
                    return []
            return yf_mod._cached(key, 1, lambda: yf_mod._failed(type(value)(), RuntimeError("refused")))
        return value

    @staticmethod
    def _refuse():
        raise RuntimeError("refused")

    def quote(self, t):
        return {"price": 270.0, "name": "Apple Inc.", "sector": "Technology", "industry": "Consumer Electronics"}

    def earnings_date(self, t):
        return "2027-01-28" if t == "AAPL" else None

    def news(self, t, limit=12):
        return self._through_cache("news:standin-" + t, [dict(x) for x in NEWS] if t == "AAPL" else [])[:limit]

    def earnings_history(self, t, limit=10):
        return self._through_cache("earnhist:standin-" + t, [dict(x) for x in HISTORY] if t == "AAPL" else [])

    def earnings_calendar(self, t):
        return {"dates": ["2027-01-28"], "confirmed": False, "eps_avg": 2.40} if t == "AAPL" else {}

    def financials(self, t):
        return {"income_annual": {"periods": ["2025-09-27"]}}

    def insiders(self, t, limit=200, days=730):
        return self._through_cache("insider:standin-" + t, json.loads(json.dumps(INSIDERS)) if t == "AAPL"
                                   else {"summary_6m": {}, "transactions": []})

    def analyst_actions(self, t):
        if "actions" in self.slow:
            time.sleep(1.5)
        if "actions" in self.fail:
            raise RuntimeError("refused")
        return [dict(x) for x in ACTIONS] if t == "AAPL" else []


@pytest.fixture(autouse=True)
def stood_in(monkeypatch):
    timeline._CACHE.clear()
    monkeypatch.setattr(timeline, "_now", lambda: NOW)
    monkeypatch.setattr(session_mod, "market_today", lambda now=None: TODAY)
    monkeypatch.setattr(congress_mod, "stale", lambda ttl=None: False)
    monkeypatch.setattr(congress_mod, "summary", lambda ticker=None, limit=60, **kw: {
        "available": True, "trades": [dict(x) for x in HOUSE if x["ticker"] == ticker][:limit],
        "filings_parsed": 400, "filings_known": 400, "complete": True})
    monkeypatch.setattr(filings_mod, "recent", lambda t, limit=12: {
        "available": t == "AAPL", "filings": [dict(x) for x in FILINGS] if t == "AAPL" else [],
        "reason": None if t == "AAPL" else "no notable filings in EDGAR's recent window"})
    monkeypatch.setattr(filings_mod, "_cik_for", lambda t: "0000320193" if t == "AAPL" else None)
    monkeypatch.setattr(m, "YF_PROVIDER", StandIn())
    yield
    timeline._CACHE.clear()


def get(path):
    r = TestClient(m.app).get(path)
    assert r.status_code == 200, r.text
    return r.json()


def section(tmp_path, data, kind="all", items=None, extra=""):
    """The section as the page draws it from a response, with the reader's zone set to New York."""
    return _run(tmp_path, f"""
      globalThis.console = globalThis.console || {{ log() {{}}, warn() {{}}, error() {{}} }};
      const P = await import('{(JS / "core/prefs.js").as_posix()}');
      P.setTimezone('America/New_York');
      const T = await import('{(JS / "ui/timeline.js").as_posix()}');
      const D = await import('{(JS / "core/dom.js").as_posix()}');
      const d = {json.dumps(data)};
      Object.assign(T._test.state, {{ sym: 'AAPL', started: true, kind: {json.dumps(kind)}, data: d,
        items: {json.dumps(items) if items is not None else 'd.events'} }});
      {extra}
      print(JSON.stringify({{ html: D.toString(T._test.sectionHTML('AAPL')) }}));
    """)["html"]


# ---------------------------------------------------------------- the four acceptance tests


def test_acceptance_1_aapl_timeline_is_in_date_order_with_sources_and_congress_lag_notes(tmp_path):
    """AAPL timeline shows news, earnings, insider, analyst events in date order with sources; congressional entries
    carry disclosure-lag notes."""
    d = get("/api/timeline/AAPL?days=90")
    assert d["complete"] and d["answered"] == 6 and not d["notes"]
    kinds = {e["type"] for e in d["events"]}
    assert {"news", "earnings", "insiders", "analysts", "congress", "filings"} <= kinds
    # newest first: the scheduled report on top, then each entry no later than the one above it
    stamps = [e["at"] or e["date"] for e in d["events"]]
    assert d["events"][0]["date_kind"] == "scheduled"
    keys = [timeline._noon(dt.date.fromisoformat(e["date"])) if not e["at"] else dt.datetime.fromisoformat(e["at"])
            for e in d["events"]]
    assert keys == sorted(keys, reverse=True), stamps
    # every entry names its source and links it or its page; none merges two sources
    for e in d["events"]:
        assert e["source"] and (e["source_url"] or e["source_link"]), e
        assert e["type_label"] == timeline.LABELS[e["type"]]
    by = {e["title"]: e for e in d["events"]}
    assert by["Apple cuts employee AI budgets as costs climb"]["source"] == "Investing.com, via Yahoo Finance"
    assert by["Apple cuts employee AI budgets as costs climb"]["source_url"] == "https://example.com/apple-ai-budgets"
    results = [e for e in d["events"] if e["date_kind"] == "reported" and e["date"] == "2026-10-30"]
    assert len(results) == 1 and "$1.85" in results[0]["summary"] and "$1.77" in results[0]["summary"]
    assert results[0]["when_note"] == "after the close, New York time"
    assert results[0]["source_url"] == "https://finance.yahoo.com/calendar/earnings?symbol=AAPL"
    sale = by["Sale of 129,963 shares by COOK TIMOTHY D, Chief Executive Officer"]
    assert sale["summary"] == "Sale at price 255.00 to 258.00 per share. Value about $33.3 million, as reported."
    assert sale["source_url"].endswith("CIK=0000320193&type=4&dateb=&owner=include&count=40")
    down = by["Loop Capital downgraded the stock to Hold from Buy"]
    assert down["summary"] == "Price target lowered to $330.00 from $370.00."
    assert down["source_url"] == "https://finance.yahoo.com/quote/AAPL/analysis"
    # congress: disclosed on the filing day, the trade date and the 45 days beside it
    house = [e for e in d["events"] if e["type"] == "congress"]
    assert len(house) == 3
    for e in house:
        assert e["source_url"].startswith("https://disclosures-clerk.house.gov/") and e["delay_note"]
    sessions = next(e for e in house if "Sessions" in e["title"])
    assert sessions["title"] == "Hon. Pete Sessions disclosed a sale of $250,001 to $500,000"
    assert sessions["summary"] == "Held by the spouse."
    assert sessions["delay_note"] == ("Disclosed Oct 27, 2026; the trade occurred on or around Sep 30, 2026. Members "
                                      "may disclose a trade up to 45 days after it.")
    late = next(e for e in house if "Hern" in e["title"])
    assert late["delay_note"].endswith("This one was disclosed 73 days after the trade.")
    typo = next(e for e in house if "Roe" in e["title"])
    assert "falls after the date it was filed, so one of the two is a typo in the filing" in typo["delay_note"]
    # drawn: each entry with its kind in words, its date's meaning, its source link and the lag note
    h = section(tmp_path, d)
    assert h.count('class="tl-e"') == len(d["events"])
    assert '<span>Congress</span>' in h and '<span>Insiders</span>' in h and '<span>News</span>' in h
    assert "Disclosed Oct 27, 2026; the trade occurred on or around Sep 30, 2026." in h
    assert 'href="https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2026/20031234.pdf" target="_blank" rel="noopener">The filing (PDF)' in h
    assert "Scheduled, not yet reported" in h


def test_acceptance_2_type_filters_work_and_empty_types_say_so(tmp_path):
    """Type filters work; empty-type states render."""
    every = get("/api/timeline/AAPL?days=90")
    counts = {t["id"]: t["count"] for t in every["types"]}
    for kind in timeline.TYPES:
        one = get("/api/timeline/AAPL?days=90&type={}".format(kind))
        assert one["total"] == counts[kind] and {e["type"] for e in one["events"]} <= {kind}
        assert [t["count"] for t in one["types"]] == [t["count"] for t in every["types"]], "the counts are the period's"
    assert sum(counts.values()) == every["total"]
    # a company with no congressional trades: the handoff's own words
    msft = get("/api/timeline/MSFT?days=90&type=congress")
    house = next(t for t in msft["types"] if t["id"] == "congress")
    assert msft["total"] == 0 and house["state"] == "ok" and house["count"] == 0
    assert house["empty"] == "No congressional trades reported for this company in this period."
    h = section(tmp_path, msft, kind="congress")
    assert "No congressional trades reported for this company in this period." in h
    assert 'data-tl-kind="congress" aria-pressed="true"' in h and 'data-tl-kind="all" aria-pressed="false"' in h
    assert "House filings only: the Senate publishes no comparable archive." in h
    # one kind chosen: only its entries are drawn, the chips still count every kind
    ins = get("/api/timeline/AAPL?days=90&type=insiders")
    h = section(tmp_path, ins, kind="insiders")
    assert h.count('data-tl-type="insiders"') == ins["total"] == 3 and 'data-tl-type="news"' not in h
    assert re.search(r'data-tl-kind="news" aria-pressed="false">.*?<span>News</span> <span class="t-muted">3</span>', h)
    # a source that does not apply says why rather than "none"
    assert msft["types"][5]["state"] == "none" and msft["types"][5]["absent"] == "No notable filings in EDGAR's recent window."
    with pytest.raises(AssertionError):
        get("/api/timeline/AAPL?type=trades")
    assert TestClient(m.app).get("/api/timeline/AAPL?type=trades").status_code == 422
    assert TestClient(m.app).get("/api/timeline/AAPL?days=45").status_code == 422
    assert TestClient(m.app).get("/api/timeline/A%20B").status_code == 400


def test_acceptance_3_one_source_failing_is_a_note_beside_the_rest(tmp_path, monkeypatch):
    """One-source failure renders partial timeline + note, not a silent gap."""
    monkeypatch.setattr(m, "YF_PROVIDER", StandIn(fail={"actions"}))
    d = get("/api/timeline/AAPL?days=90")
    assert not d["complete"] and d["answered"] == 5
    assert d["notes"] == ["Analyst actions temporarily unavailable. The analyst-action feed did not answer."]
    analysts = next(t for t in d["types"] if t["id"] == "analysts")
    assert analysts["state"] == "failed" and analysts["count"] == 0
    assert {e["type"] for e in d["events"]} == {"news", "earnings", "insiders", "congress", "filings"}
    h = section(tmp_path, d)
    assert "Not every source answered. Analysts: The analyst-action feed did not answer. The entries below are from the other 5 sources." in h
    assert 'data-tl-kind="analysts" aria-pressed="false"><svg' in h and '<span>Analysts</span> <span class="t-muted">unavailable</span>' in h
    assert "data-tl-retry" in h and h.count('class="tl-e"') == len(d["events"])
    # the failed kind chosen: unavailable, never "none reported"
    h = section(tmp_path, dict(d, total=0, events=[]), kind="analysts", items=[])
    assert "Analysts: temporarily unavailable" in h and "No analyst actions reported" not in h
    # a failure the provider swallows (the news feed answering [] after an error) is still caught as one
    timeline._CACHE.clear()
    monkeypatch.setattr(m, "YF_PROVIDER", StandIn(fail={"news", "earnhist"}))
    d = get("/api/timeline/AAPL?days=90")
    states = {t["id"]: t["state"] for t in d["types"]}
    assert states["news"] == "failed" and states["earnings"] == "failed" and states["insiders"] == "ok"
    assert "News temporarily unavailable. The headline feed did not answer." in d["notes"]
    assert "Earnings temporarily unavailable. The earnings feed did not answer." in d["notes"]
    # a source that does not answer in time is said too, and the rest are not held for it
    timeline._CACHE.clear()
    started = time.time()
    built = timeline.build(StandIn(slow={"actions"}), "AAPL", 90, now=NOW, wait=0.3)
    assert time.time() - started < 1.2
    assert built["sources"]["analysts"]["state"] == "failed"
    assert built["sources"]["analysts"]["failed"] == "The analysts source did not answer in time."
    assert built["sources"]["insiders"]["state"] == "ok"
    # a partial build is kept briefly, a whole one for the full time
    assert timeline.TTL_PARTIAL < timeline.TTL


def test_acceptance_4_each_source_dates_its_entries_as_what_they_are(tmp_path):
    """Date-type labels (transaction vs filing vs publication) are correct per source."""
    d = get("/api/timeline/AAPL?days=90")
    kinds = {}
    for e in d["events"]:
        kinds.setdefault(e["type"], set()).add((e["date_kind"], e["date_label"]))
    assert kinds["news"] == {("published", "Published")}
    assert kinds["earnings"] == {("reported", "Reported"), ("scheduled", "Scheduled, not yet reported")}
    assert kinds["insiders"] == {("traded", "Transaction date")}
    assert kinds["congress"] == {("disclosed", "Disclosed")}
    assert kinds["analysts"] == {("recorded", "Recorded")}
    assert kinds["filings"] == {("filed", "Filed")}
    ev = {e["title"]: e for e in d["events"]}
    # news: the publication instant, on its New York day (2 AM UTC Nov 4 is Nov 3 in New York)
    sup = ev["Apple supplier earnings beat estimates"]
    assert sup["at"] == "2026-11-04T02:00:00+00:00" and sup["date"] == "2026-11-03"
    # insiders: the transaction date, with the filing lag said
    assert ev["Sale of 129,963 shares by COOK TIMOTHY D, Chief Executive Officer"]["date"] == "2026-10-02"
    assert "two business days" in ev["Sale of 129,963 shares by COOK TIMOTHY D, Chief Executive Officer"]["delay_note"]
    # congress: placed on the filing day, not the trade day
    assert ev["Hon. Pete Sessions disclosed a sale of $250,001 to $500,000"]["date"] == "2026-10-27"
    # analysts: Yahoo's time when it has one, the bare day when it does not
    assert ev["Loop Capital downgraded the stock to Hold from Buy"]["at"] == "2026-10-20T13:46:00+00:00"
    needham = ev["Needham started coverage at Hold"]
    assert needham["at"] is None and needham["date"] == "2026-09-15"
    # filings: the EDGAR filing date
    assert ev["Annual report (Form 10-K)"]["date"] == "2026-10-31"
    # each kind's date explained once, per source, in the response and in each entry's details
    dates = {t["id"]: t["dates"] for t in d["types"]}
    assert dates["congress"].startswith("The day the House received the disclosure")
    assert dates["insiders"].startswith("The transaction date on the Form 4")
    assert dates["news"].startswith("When the story was published")
    assert dates["filings"] == "The filing date EDGAR gives."
    h = section(tmp_path, d)
    assert "The date: The transaction date on the Form 4." in h
    # in the reader's zone with its name where the source gives a time; as the source dates it where it does not
    got = _run(tmp_path, f"""
      const P = await import('{(JS / "core/prefs.js").as_posix()}');
      const T = await import('{(JS / "ui/timeline.js").as_posix()}');
      P.setTimezone('America/Los_Angeles');
      const a = T.whenOf({{ at: '2026-11-04T02:00:00+00:00', date: '2026-11-03' }});
      const b = T.whenOf({{ at: null, date: '2026-09-15' }});
      P.setTimezone('America/New_York');
      const c = T.whenOf({{ at: '2026-11-04T02:00:00+00:00', date: '2026-11-03' }});
      print(JSON.stringify({{ a, b, c }}));
    """)
    assert got["a"]["day"] == "Nov 3, 2026" and got["a"]["time"] == "6:00 PM PST"
    assert got["b"] == {"iso": "2026-09-15", "day": "Sep 15, 2026", "time": ""}
    assert got["c"]["day"] == "Nov 3, 2026" and got["c"]["time"] == "9:00 PM EST"


# ---------------------------------------------------------------- the edge cases


def test_the_same_item_twice_is_one_entry_and_two_sources_stay_two():
    d = get("/api/timeline/AAPL?days=90")
    news = [e for e in d["events"] if e["type"] == "news"]
    assert len(news) == 3, "four stories in the feed, one of them listed twice"
    assert len([e for e in d["events"] if e["type"] == "filings"]) == 2, "the 8-K listed twice is one entry"
    # the results 8-K, the earnings report and the story about it: three entries, three sources, same week
    week = [e for e in d["events"] if e["date"] in ("2026-10-30", "2026-10-31")]
    assert {e["type"] for e in week} == {"news", "earnings", "filings"}
    assert len({e["id"] for e in d["events"]}) == len(d["events"]), "every entry has its own id"


def test_rows_with_nothing_to_tell_them_apart_are_both_kept(monkeypatch):
    twice = json.loads(json.dumps(INSIDERS))
    twice["transactions"].append(dict(twice["transactions"][0]))

    class Twice(StandIn):
        def insiders(self, t, limit=200, days=730):
            return json.loads(json.dumps(twice))

    built = timeline.build(Twice(), "AAPL", 90, now=NOW)
    cooks = [e for e in built["events"] if e["type"] == "insiders" and "COOK" in e["title"]]
    assert len(cooks) == 2 and cooks[0]["id"] != cooks[1]["id"], "no identity to match on, so both are kept"


def test_scheduled_report_and_a_passed_date_with_no_results():
    hist = [dict(x) for x in HISTORY] + [{"date": "2026-11-02", "timing": "before_open", "at": None,
                                         "eps_estimate": 0.9, "eps_reported": None, "surprise_pct": None}]

    class Due(StandIn):
        def earnings_history(self, t, limit=10):
            return [dict(x) for x in hist]

    built = timeline.build(Due(), "AAPL", 90, now=NOW)
    earn = [e for e in built["events"] if e["type"] == "earnings"]
    nxt = next(e for e in earn if e["date_kind"] == "scheduled")
    assert nxt["date"] == "2027-01-28" and nxt["title"] == "Next earnings report"
    assert nxt["summary"].startswith("Scheduled, not yet reported. The date is an estimate, not confirmed by the company.")
    due = next(e for e in earn if e["date_kind"] == "due")
    assert due["date"] == "2026-11-02" and due["date_label"] == "Report date passed, results not in the feed yet"
    assert due["when_note"] == "before the open, New York time"


def test_pages_of_fifty_and_the_period():
    many = [dict(ACTIONS[0], at="2026-10-{:02d}T{:02d}:00:00+00:00".format(1 + i // 6, 10 + i % 6), firm="Firm {}".format(i))
            for i in range(120)]

    class Many(StandIn):
        def analyst_actions(self, t):
            return [dict(x) for x in many]

    built = timeline.build(Many(), "AAPL", 90, now=NOW)
    one = timeline.page(built, "analysts", 1)
    three = timeline.page(built, "analysts", 3)
    assert one["per"] == 50 and one["pages"] == 3 and len(one["events"]) == 50 and len(three["events"]) == 20
    assert not set(e["id"] for e in one["events"]) & set(e["id"] for e in three["events"])
    assert timeline.page(built, "analysts", 9)["page"] == 3, "past the end is the last page"
    # the period: 30 days leaves out what 90 days keeps, and a year adds the older rows
    month = timeline.build(StandIn(), "AAPL", 30, now=NOW)
    year = timeline.build(StandIn(), "AAPL", 365, now=NOW)
    assert not any(e["date"] < "2026-10-05" for e in month["events"])
    assert any(e["title"].startswith("Sale of 5,000 shares by MAESTRI LUCA") for e in year["events"])
    assert month["since"] == "2026-10-05" and year["since"] == "2025-11-04"


def test_reach_shorter_than_the_period_is_said():
    year = timeline.page(timeline.build(StandIn(), "AAPL", 365, now=NOW))
    t = {x["id"]: x for x in year["types"]}
    assert t["congress"]["reach"] == ("House filings only: the Senate publishes no comparable archive. Optic reads the "
                                      "House's filings for 2026 only, so trades disclosed before Jan 1, 2026 are not here.")
    assert t["news"]["reach"] == ("The headline feed holds its latest 3 stories about the company, which reach back to "
                                  "Oct 30, 2026. Older news is not in it.")


def test_neutral_wording_on_trades_and_no_advice():
    d = get("/api/timeline/AAPL?days=365")
    text = " ".join(" ".join(str(e.get(k) or "") for k in ("title", "summary", "delay_note"))
                    for e in d["events"]).lower()
    for word in ("signal", "bullish", "bearish", "suspicious", "illegal", "wrongdoing", "dump", "smart money",
                 "should", "buy now", "sell now", "warning", "red flag"):
        assert word not in text, word
    assert "not a signal" in d["method"] and "Not investment advice" in d["method"]


def test_failures_are_noted_through_the_provider_cache():
    # the failure marker and a raised fetch are both listed; a success and a cache hit are not
    with yf_mod.noting_failures() as noted:
        assert yf_mod._cached("timeline-test:marker", 1, lambda: yf_mod._failed([], RuntimeError("x"))) == []
        with pytest.raises(RuntimeError):
            yf_mod._cached("timeline-test:raised", 1, StandIn._refuse)
        assert yf_mod._cached("timeline-test:fine", 60, lambda: [1]) == [1]
        assert yf_mod._cached("timeline-test:fine", 60, lambda: [2]) == [1]
    assert noted == ["timeline-test:marker", "timeline-test:raised"]
    # outside the block nothing is kept, and a block on another thread does not see this one's
    assert yf_mod._cached("timeline-test:marker2", 1, lambda: yf_mod._failed([], None)) == []


def test_the_page_draws_entries_accessibly_and_on_a_phone(tmp_path):
    d = get("/api/timeline/AAPL?days=90")
    h = section(tmp_path, d)
    # a word for the kind beside a decorative icon; details open and shut by a named button
    assert '<p class="tl-kind"><svg viewBox="0 0 24 24" aria-hidden="true" class="ic ic-insider">' in h
    first = d["events"][0]["id"]
    assert 'data-tl-open="{}" aria-expanded="false" aria-controls="tl-d-'.format(first) in h
    assert '<span class="sr">: Next earnings report</span>' in h
    assert '<span class="sr"> (opens in a new tab)</span>' in h
    assert 'class="tl-detail" id="tl-d-' in h and " hidden>" in h
    assert 'aria-label="Period"' in h and 'data-tl-days="90" aria-pressed="true"' in h
    assert "Showing {} of {}.".format(len(d["events"]), d["total"]) in h
    assert "Events as of" in h and "for Aug 6, 2026 to Nov 4, 2026" in h
    # every entry links its section in Optic
    got = _run(tmp_path, f"""
      const T = await import('{(JS / "ui/timeline.js").as_posix()}');
      print(JSON.stringify(Object.fromEntries(T.TYPES.map(([id]) => [id, T.sectionLink(id, 'AAPL').href]))));
    """)
    assert got == {"news": "#/AAPL/news", "earnings": "#/AAPL/earnings",
                   "insiders": "#/AAPL/financials?section=fin-ownership",
                   "congress": "#/insiders?symbol=AAPL&view=house", "analysts": "#/analysts?symbol=AAPL",
                   "filings": "#/AAPL/financials?section=fin-filings"}
    # more than a page: the next 50 on request
    h = section(tmp_path, dict(d, total=120), items=d["events"])
    assert "Show 50 older" in h and "data-tl-more" in h
    css = (V2 / "css" / "pages.css").read_text()
    phone = css[css.index("/* Company events (Handoff 9"):]
    assert ".tl-e { grid-template-columns: minmax(0, 1fr); }" in phone and ".chips { display: flex; flex-wrap: wrap;" in (V2 / "css" / "components.css").read_text()


def test_the_overview_reads_events_after_its_own_figures():
    src = (JS / "pages" / "dossier.js").read_text()
    assert "<div data-tl-slot></div>" in src and "mountTimeline(main, sym);" in src and "disposeTimeline();" in src
    after = src[src.index("fresh(`/api/ticker/${enc}"):]
    assert after.index("startTimeline(sym);") < after.index("fresh(`/api/framework/"), "started from the ticker's answer"
    tl = (JS / "ui" / "timeline.js").read_text()
    assert "load();" not in tl[tl.index("export function mountTimeline"):], "mounting reads nothing"
    fin = (JS / "pages" / "financials.js").read_text()
    assert "wantSection = /^fin-[a-z]+$/.test(want) ? want : null;" in fin
    an = (JS / "pages" / "analysts.js").read_text()
    assert "if (/^[A-Z0-9.^=-]{1,12}$/.test(want)) { Q.ticker = want; Q.days = 365; }" in an
