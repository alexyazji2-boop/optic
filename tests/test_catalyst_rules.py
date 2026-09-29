"""The catalyst scan without the model, and a ticker search that reads the company.

Asked for as "is there no way to make the catalyst scan not require my AI
credits? its a web search of catalysts for the specific ticker essentially
across several factors". Every scan was a call on the owner's key. The default
reader is now published rules over the same stories (app/catalyst_rules.py),
and a search for one symbol reads that company's headlines, the wires naming
it, its 8-K filings and its next report by the same rules.

The headlines below are the week's stories as the scan read them on
2026-09-29. A theme word alone filed 45 of those 120; the rules file the 17
events among them and none of the commentary. No test reaches the network.
"""
from __future__ import annotations

import os
import re
import shutil
import sqlite3
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app import ai, catalyst_rules as rules, catalysts, feeds, live_mirror

ROOT = Path(__file__).resolve().parent.parent
NOW = datetime.now(timezone.utc)
TODAY = NOW.date()


def _iso(hours_ago):
    return (NOW - timedelta(hours=hours_ago)).replace(microsecond=0).isoformat()


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(catalysts, "DB_PATH", str(tmp_path / "catalysts.db"))
    monkeypatch.setattr(catalysts, "READER", "rules")
    monkeypatch.setattr(catalysts, "_LAST_ATTEMPT", [0.0])
    monkeypatch.setattr(catalysts, "AUTO", True)
    monkeypatch.setattr(catalysts, "_TICKER_CACHE", {})
    return tmp_path


# The week's events, and the source each was read from.
EVENTS = [
    ("Trump rules out joint US-China venture to develop AI", "BBC News"),
    ("America's Canadian import restrictions come into force. Here are the products barred from entry", "CNBC"),
    ("US 30-year Treasury yield hits highest since 2002", "Financial Times"),
    ("Shell backs $23 billion LNG Canada expansion in boost to Carney's ‘energy superpower’ push", "CNBC"),
    ("STAT+: AstraZeneca invests $2 billion in Summit Therapeutics", "STAT"),
    ("OpenAI scraps rollout of new model over safety concerns", "BBC News"),
    ("Samsung to inject $1 billion into Nvidia- and KKR-backed AI infrastructure firm", "CNBC"),
    ("FDA Approves First Treatment for MCT8 Deficiency", "FDA"),
    ("Trump announces plan for $15 billion steel plant, would be largest in U.S. history", "CNBC"),
    ("FDA intends to evaluate changes to the PMTA regulatory framework", "FDA"),
    ("Trump ‘very seriously’ considering diesel export ban as global supply crunch worsens", "CNBC"),
    ("FTC, States Win Protections to Lower Pesticide Prices for American Farmers in Antitrust Case Against Corteva", "FTC"),
    ("Apple ordered to pay $5.7bn after losing vibration tech patent suit", "BBC News"),
    ("U.S., China to lower tariffs on $60 billion of goods. Here's what qualifies", "CNBC"),
    ("Mortgage rates break past 7% as bond yields surge, deepening U.S. housing gridlock", "NPR"),
    ("Federal Reserve Board requests public comment on two proposals related to establishing a regulatory framework for Board-supervised payment stablecoin issuers", "Federal Reserve"),
    ("Lennar shares pop as Berkshire builds almost a 10% stake in beleaguered homebuilder", "CNBC"),
]

# The same week's commentary, speeches, notices and news about nothing a
# market prices. Each of these matched a theme word.
NOT_EVENTS = [
    ("Education Department extends deadline for student loan interest rate discount", "CNBC"),
    ("The AI boom meets a new kind of crypto scam", "The Economist"),
    ("How the AI boom could worsen the rich world’s fiscal crunch", "The Economist"),
    ("Burnham to fight next election on pledge to change voting system", "BBC News"),
    ("STAT+: Anthropic joins ARPA-H clinical AI moonshot, will hold closed-door health care event", "STAT"),
    ("Three EU Nations Call for New 2040 Renewable Energy Goal", "OilPrice"),
    ("The Hidden Tradeoffs of a U.S. Diesel Export Ban", "OilPrice"),
    ("Trump meets with AI execs, Treasury yields pressure stocks, Alaska's luxury push and more in Morning Squawk", "CNBC"),
    ("Mistral CEO says U.S. AI safety debate masks competitors’ 'negligence'", "CNBC"),
    ("US-Iran war adds €100bn to EU’s fuel bill", "Financial Times"),
    ("Senate advances college sports bill aimed at regulating NIL deals", "CNBC"),
    ("ECB amends monetary policy implementation guidelines as part of regular review", "European Central Bank"),
    ("Yields Up (Again), Yield Curve Steepening", "Econbrowser"),
    ("Jim Cramer says these stocks can win even as oil and bond yields squeeze the market", "CNBC"),
    ("Feds can't withhold counterterrorism funds from states to force election admin changes, judge rules", "CNBC"),
    ("Meta, Google, Amazon, Microsoft draw Sen. Warren questions about AI tax subsidies", "CNBC"),
    ("Cook, An Update on AI and the Economy", "Federal Reserve"),
    ("Bond Yields: Two Pictures", "Econbrowser"),
    ("This may be the ‘missing piece’ for investors looking to boost AI exposure", "CNBC"),
    ("Federal Reserve Board announces approval of application by Peoples Bancorp Inc.", "Federal Reserve"),
    ("Henry Hub natural gas prices this summer were 6% lower than last summer", "EIA"),
    ("Here's what happens to the economy when Treasury yields soar like they are now", "CNBC"),
    ("Surging Treasury yields pose a brand new problem for Kevin Warsh and the Fed", "CNBC"),
    ("Federal Reserve Board issues enforcement action with former employee of Sandy Spring Bank", "Federal Reserve"),
    ("CFTC Staff Releases Updates to FAQs Concerning Registrants and Registered Entity Activities Relating to Crypto Assets", "CFTC"),
    ("FTC Approves Publication of Federal Register Notices Revising the Commission’s Rules of Practice", "FTC"),
    ("ECB Executive Board member Isabel Schnabel to resign to take senior role at IMF", "European Central Bank"),
    ("How the Fed should measure inflation", "The Economist"),
    ("Israel’s war economy is thriving", "The Economist"),
    ("Federal Court Enters Consent Decree Against Gold Star Distribution, Inc. Following Persistent Insanitary Warehouse Conditions", "FDA"),
    ("Meta's Muse reignites AI disruption fears. Traders are targeting this brokerage stock as next casualty", "CNBC"),
    ("Christine Lagarde: Hearing of the Committee on Economic and Monetary Affairs of the European Parliament", "European Central Bank"),
    ("Philip R. Lane: The outlook for the euro area economy", "European Central Bank"),
    ("Sciarra Aeromed, Inc. - 728248 - 09/23/2026", "FDA"),
    ("H.R. 2299, Ensuring Workers Get PAID Act of 2025", "Congressional Budget Office"),
    ("Cramer weighs in on Goldman amid CEO succession talks — plus, Boeing bounces back", "CNBC"),
    ("Five takeaways from Andy Burnham's Labour conference speech", "BBC News"),
    ("SEC Charges Registered Investment Adviser Zoe Financial for Failure to Disclose Conflict of Interest", "SEC"),
]


def _story(n, title, source, hours_ago=5, access="open"):
    return {"id": "s%d" % n, "title": title, "summary": "", "source": source, "desk": "",
            "published": _iso(hours_ago), "url": "https://news.example/%d" % n,
            "access": access}


# ------------------------------------------------------------- the rules


def test_the_rules_file_the_events_and_none_of_the_commentary():
    stories = [_story(n, t, s) for n, (t, s) in enumerate(EVENTS + NOT_EVENTS, 1)]
    found = rules.extract(stories)
    titles = {c["title"] for c in found}
    assert titles == {rules.display_title(t) for t, _s in EVENTS}
    assert "AstraZeneca invests $2 billion in Summit Therapeutics" in titles, "the desk label goes"


@pytest.mark.parametrize("title,kind,category", [
    ("US 30-year Treasury yield hits highest since 2002", "market", "monetary-policy"),
    ("Trump ‘very seriously’ considering diesel export ban as global supply crunch worsens",
     "policy", "geopolitical"),
    ("FDA intends to evaluate changes to the PMTA regulatory framework", "policy", "regulatory"),
    ("Federal Reserve Board requests public comment on two proposals related to establishing a "
     "regulatory framework for payment stablecoin issuers", "policy", "regulatory"),
    ("Apple ordered to pay $5.7bn after losing vibration tech patent suit", "company", "corporate"),
    ("Shell backs $23 billion LNG Canada expansion", "company", "commodity"),
])
def test_each_event_says_which_rule_filed_it(title, kind, category):
    c = rules.extract([_story(1, title, "CNBC")])[0]
    assert (c["rule"], c["category"]) == (kind, category)


def test_a_company_that_leads_its_headline_makes_it_its_own_event():
    """Shell's decision, not Canada's: no LNG read-through beside the name."""
    c = rules.extract([_story(1, "Shell backs $23 billion LNG Canada expansion", "CNBC")])[0]
    assert [x["ticker"] for x in c["companies"]] == ["SHEL"]
    assert c["companies"][0]["why"] == rules.NAMED_WHY


def test_the_standard_read_through_says_that_is_what_it_is():
    c = rules.extract([_story(1, "FDA intends to evaluate changes to the PMTA regulatory framework",
                              "FDA")])[0]
    assert [x["ticker"] for x in c["companies"]] == ["MO", "PM", "BTI"]
    assert all(x["why"].startswith("Standard read-through for tobacco and nicotine: ")
               for x in c["companies"])


def test_a_policy_aimed_at_a_named_company_carries_that_company_alone():
    """No grain traders under "Antitrust Case Against Corteva"."""
    c = rules.extract([_story(1, EVENTS[11][0], "FTC")])[0]
    assert [x["ticker"] for x in c["companies"]] == ["CTVA"]


def test_a_headline_with_no_subject_takes_the_summarys():
    story = _story(1, "U.S., China to lower tariffs on $60 billion of goods", "CNBC")
    story["summary"] = "The cuts cover soybeans, corn and other farm goods."
    c = rules.extract([story])[0]
    assert "Agriculture" in c["themes"] and "ADM" in [x["ticker"] for x in c["companies"]]


def test_one_event_from_two_outlets_is_one_catalyst_led_by_the_first_open_report():
    stories = [
        _story(1, "Apple faces $5.7 billion patent infringement verdict over iPhone haptics",
               "Financial Times", hours_ago=60, access="paid"),
        _story(2, "Apple faces $5.7 billion patent verdict, jury says", "CNBC", hours_ago=50),
        _story(3, "Apple ordered to pay $5.7bn after losing vibration tech patent suit",
               "BBC News", hours_ago=10),
    ]
    found = rules.extract(stories)
    assert len(found) == 1
    assert found[0]["story_ids"][0] == "s2", "the first a reader can open leads"
    assert found[0]["title"] == stories[1]["title"]
    assert sorted(found[0]["story_ids"]) == ["s1", "s2", "s3"]


@pytest.mark.parametrize("text,named", [
    ("Amazon rainforest fires spread", []),
    ("Amazon to buy a chip start-up", ["AMZN"]),
    ("Ex-Tesla team raises $12.5M", []),
    ("TMC Names Former ExxonMobil Executive to Board", []),
    ("Shell companies used to launder funds", []),
    ("Meta Platforms and Nvidia sign a deal", ["META", "NVDA"]),
    ("Acme Corp (NASDAQ: ACME) announces results", ["ACME"]),
])
def test_names_are_the_companies_and_not_the_words(text, named):
    assert rules.named_companies(text) == named


# ------------------------------------------------------------- the scan


def _scan(monkeypatch, stories):
    def model(*a, **k):
        raise AssertionError("the model was called")

    monkeypatch.setattr(catalysts, "candidate_stories", lambda hours=168: [dict(s) for s in stories])
    monkeypatch.setattr(catalysts, "ticker_directory",
                        lambda: {"SHEL": "Shell plc", "AAPL": "Apple Inc.", "MO": "ALTRIA GROUP, INC.",
                                 "PM": "Philip Morris International Inc."})
    monkeypatch.setattr(ai, "extract_catalysts", model)
    return catalysts.refresh(trigger="manual")


def _rows():
    with sqlite3.connect(catalysts.DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute("SELECT * FROM catalysts ORDER BY title")]


def test_a_scan_stores_the_events_without_the_model(monkeypatch):
    stories = [_story(1, EVENTS[3][0], "CNBC"), _story(2, EVENTS[12][0], "BBC News"),
               _story(3, NOT_EVENTS[13][0], "CNBC")]
    out = _scan(monkeypatch, stories)
    assert out["available"] is True and out["reader"] == "rules"
    assert (out["scanned"], out["identified"], out["new"]) == (3, 2, 2)
    rows = _rows()
    assert [r["source_url"] for r in rows] == ["https://news.example/2", "https://news.example/1"]
    assert [r["title"] for r in rows] == [EVENTS[12][0], EVENTS[3][0]]
    # The EDGAR check still runs: SHEL resolves, the named-only link is kept.
    assert '"ticker": "SHEL"' in rows[1]["companies"]


def test_a_second_scan_of_the_same_stories_files_nothing_new(monkeypatch):
    stories = [_story(1, EVENTS[3][0], "CNBC")]
    _scan(monkeypatch, stories)
    again = _scan(monkeypatch, stories)
    assert (again["identified"], again["known"], again["written"]) == (0, 1, 0)
    assert len(_rows()) == 1


def test_a_scan_never_rewrites_a_row_the_model_wrote(monkeypatch):
    catalysts.upsert([{"id": "model0000row", "event_date": TODAY.isoformat(),
                       "title": "Shell Approves $23 Billion LNG Canada Phase 2 Expansion",
                       "summary": "Written by the model.", "category": "commodity",
                       "horizon": "long-term", "themes": [], "sectors": [], "companies": [],
                       "source_url": "https://news.example/1", "source_name": "CNBC"}])
    out = _scan(monkeypatch, [_story(1, EVENTS[3][0], "CNBC")])
    assert out["known"] == 1
    assert [r["title"] for r in _rows()] == ["Shell Approves $23 Billion LNG Canada Phase 2 Expansion"]


def test_the_schedule_needs_no_key_under_the_rules(monkeypatch):
    monkeypatch.setattr(ai, "key_usable", lambda: False)
    monkeypatch.setattr(live_mirror, "MODE", "auto")
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
    assert catalysts.mirrored() is False, "a copy without a key fills its own library"
    assert catalysts.scheduled() is True
    monkeypatch.setattr(catalysts, "READER", "model")
    assert catalysts.scheduled() is False, "the model still needs a key"


def test_the_setting_that_says_mirror_is_still_honoured(monkeypatch):
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
    monkeypatch.setattr(live_mirror, "MODE", "on")
    assert catalysts.mirrored() is True and catalysts.scheduled() is False


def test_the_method_note_describes_the_reader_in_use(monkeypatch):
    assert catalysts.search()["method"] == catalysts.METHOD_RULES
    assert "not a model" in catalysts.METHOD_RULES
    monkeypatch.setattr(catalysts, "READER", "model")
    assert catalysts.search()["method"] == catalysts.METHOD_MODEL


def test_a_reader_scans_fifteen_minutes_apart_under_the_rules_and_an_hour_under_the_model(monkeypatch):
    client = TestClient(main.app)
    monkeypatch.setattr(main, "WRITE_TOKEN", "test-write-token")
    monkeypatch.setattr(main.live_mirror, "active", lambda: False)
    monkeypatch.setattr(main.catalysts_mod, "refresh",
                        lambda hours, trigger: {"available": True})
    monkeypatch.setattr(main.catalysts_mod, "seconds_since_last_scan", lambda: 20 * 60.0)
    assert client.post("/api/catalysts/refresh").status_code == 200
    monkeypatch.setattr(main.catalysts_mod, "seconds_since_last_scan", lambda: 5 * 60.0)
    r = client.post("/api/catalysts/refresh")
    assert r.status_code == 429
    assert r.json()["detail"] == ("The last catalyst scan ran 5 minutes ago. "
                                  "The next one can start in 10 minutes.")
    monkeypatch.setattr(main.catalysts_mod, "READER", "model")
    monkeypatch.setattr(main.catalysts_mod, "seconds_since_last_scan", lambda: 20 * 60.0)
    assert client.post("/api/catalysts/refresh").status_code == 429


# ------------------------------------------------------------ one ticker

DIRECTORY = {"NVDA": "NVIDIA CORP", "AI": "C3.ai, Inc.", "OIL": "Some Oil Fund",
             "AAPL": "Apple Inc.", "BRK-B": "BERKSHIRE HATHAWAY INC"}


@pytest.mark.parametrize("query,sym", [
    ("nvda", "NVDA"), ("NVDA", "NVDA"), (" $nvda ", "NVDA"), ("brk.b", "BRK-B"),
    ("oil", None), ("OIL", "OIL"), ("ai", None), ("AI", "AI"), ("$ai", "AI"),
    ("nvda export", None), ("zzzz", None), ("", None),
])
def test_a_search_is_for_a_company_only_when_it_is_one_symbol(monkeypatch, query, sym):
    """Typed in lower case, a theme's word is the theme: "oil" and "ai" are
    tickers too, and a reader typing them means the theme."""
    monkeypatch.setattr(catalysts, "ticker_directory", lambda: DIRECTORY)
    assert catalysts.ticker_query(query) == sym


class FakeProvider:
    def __init__(self):
        self.calls = 0

    def quote(self, ticker):
        return {"name": "NVIDIA Corporation", "sector": "Technology"}

    def news(self, ticker, limit=12):
        self.calls += 1
        return [
            {"title": "Nvidia share buyback plan gets $150 billion boost", "summary": "",
             "publisher": "Barron's", "published": _iso(20), "url": "https://y.example/1"},
            {"title": "Why Nvidia stock is soaring today?", "summary": "",
             "publisher": "Motley Fool", "published": _iso(10), "url": "https://y.example/2"},
            {"title": "AMD's $8.2 Billion AI Deal Takes Aim at Nvidia's Biggest Advantage",
             "summary": "", "publisher": "GuruFocus.com", "published": _iso(8),
             "url": "https://y.example/3"},
            {"title": "Elon Musk Wants To Build 20,000 Optimus Robots, Using Nvidia Chips",
             "summary": "", "publisher": "24/7 Wall St.", "published": _iso(6),
             "url": "https://y.example/4"},
        ]

    def earnings_date(self, ticker):
        return (TODAY + timedelta(days=12)).isoformat()


def _filings(ticker, limit=12):
    old = (TODAY - timedelta(days=400)).isoformat()
    return {"available": True, "filings": [
        {"form": "8-K", "filed": (TODAY - timedelta(days=30)).isoformat(), "items": "2.02,9.01",
         "url": "https://sec.example/a"},
        {"form": "8-K", "filed": (TODAY - timedelta(days=60)).isoformat(), "items": "5.02,5.07",
         "url": "https://sec.example/b"},
        {"form": "8-K", "filed": (TODAY - timedelta(days=61)).isoformat(), "items": "9.01",
         "url": "https://sec.example/c"},
        {"form": "10-Q", "filed": (TODAY - timedelta(days=30)).isoformat(), "items": "",
         "url": "https://sec.example/d"},
        {"form": "8-K", "filed": old, "items": "1.01", "url": "https://sec.example/e"},
    ]}


WIRES = [
    {"title": "Nvidia boosts its share buyback plan by $150 billion", "summary": "",
     "source": "CNBC", "published": _iso(24), "url": "https://w.example/1",
     "access": "metered", "source_id": "cnbc"},
    {"title": "Here's why Nvidia's buyback matters more than its earnings", "summary": "",
     "source": "CNBC", "published": _iso(30), "url": "https://w.example/2", "access": "metered",
     "source_id": "cnbc"},
    {"title": "Nvidia to acquire a networking start-up for $2 billion", "summary": "",
     "source": "BBC News", "published": _iso(3), "url": "https://w.example/3", "access": "open",
     "source_id": "bbc"},
]


@pytest.fixture
def company(monkeypatch):
    from app.analytics import filings
    monkeypatch.setattr(catalysts, "ticker_directory", lambda: DIRECTORY)
    monkeypatch.setattr(filings, "recent", _filings)
    monkeypatch.setattr(feeds, "load_kind",
                        lambda kind, force=False, sector=None: (WIRES if kind == "wire" else [], []))
    return FakeProvider()


def test_a_company_search_reads_it_across_its_factors(company):
    out = catalysts.ticker_catalysts(company, "NVDA")
    titles = [r["title"] for r in out["rows"]]
    assert titles[0] == "NVIDIA Corporation reports earnings on {}".format(
        (TODAY + timedelta(days=12)).isoformat()), "the next report leads"
    assert "Nvidia to acquire a networking start-up for $2 billion" in titles
    assert "NVIDIA Corporation 8-K: Results of operations" in titles
    assert "NVIDIA Corporation 8-K: Director or officer change" in titles
    # Commentary, another company's deal, an exhibit-only filing, a 10-Q and
    # a filing older than the window are not catalysts.
    assert not any(t.startswith(("Why Nvidia", "AMD's", "Elon Musk", "Here's")) for t in titles)
    assert len([t for t in titles if "8-K" in t]) == 2
    factors = {f["factor"]: f["count"] for f in out["factors"]}
    assert factors["Earnings and guidance"] == 2 and factors["Deals"] == 1
    assert factors["Management"] == 1 and factors["Capital return"] == 1


def test_one_buyback_from_two_sources_is_one_catalyst(company):
    out = catalysts.ticker_catalysts(company, "NVDA")
    buybacks = [r for r in out["rows"] if r["factor"] == "Capital return"]
    assert len(buybacks) == 1
    assert buybacks[0]["basis"] == "wire", "the news desk's story stands for it"
    assert (buybacks[0]["source_name"], buybacks[0]["also"]) == ("CNBC", ["Barron's"])


def test_every_company_row_says_where_it_came_from_and_links_it(company):
    out = catalysts.ticker_catalysts(company, "NVDA")
    for r in out["rows"]:
        assert r["basis"] in ("calendar", "headline", "wire", "filing")
        assert r["companies"][0]["ticker"] == "NVDA" and r["companies"][0]["directness"] == "direct"
        if r["basis"] != "calendar":
            assert r["source_url"].startswith("https://")
    assert [s["id"] for s in out["sources"]] == ["headlines", "wires", "filings", "calendar"]
    assert all(s["ok"] for s in out["sources"])


def test_a_company_search_is_cached_and_a_failed_one_is_not(company, monkeypatch):
    catalysts.ticker_catalysts(company, "NVDA")
    catalysts.ticker_catalysts(company, "NVDA")
    assert company.calls == 1

    class Down(FakeProvider):
        def news(self, ticker, limit=12):
            raise OSError("down")

        def earnings_date(self, ticker):
            return None

    from app.analytics import filings
    monkeypatch.setattr(filings, "recent", lambda t, limit=12: {"available": False, "reason": "x"})
    monkeypatch.setattr(feeds, "load_kind", lambda *a, **k: (_ for _ in ()).throw(OSError("down")))
    down = catalysts.ticker_catalysts(Down(), "AAPL")
    assert not any(s["ok"] for s in down["sources"])
    assert "AAPL" not in catalysts._TICKER_CACHE


def test_a_story_the_library_filed_is_not_shown_twice(company):
    out = catalysts.ticker_catalysts(company, "NVDA")
    deal = next(r for r in out["rows"] if r["factor"] == "Deals")
    view = catalysts.ticker_view(out, [{"source_url": deal["source_url"]}])
    assert deal["title"] not in [r["title"] for r in view["rows"]]
    assert "Deals" not in [f["factor"] for f in view["factors"]], "the tally follows the rows"
    assert len(out["rows"]) == len(view["rows"]) + 1, "the cached answer is not edited"
    only = catalysts.ticker_view(out, [], "regulatory")
    assert only["rows"] == [] and only["factors"] == []
    # Another outlet's report of an event the library linked, likewise; one
    # that only reaches the sector does not take the company's own row away.
    twin = {"title": "Nvidia agrees to acquire a networking start-up for $2 billion",
            "source_url": "https://elsewhere.example/1", "reach": "linked"}
    assert deal["title"] not in [r["title"] for r in catalysts.ticker_view(out, [twin])["rows"]]
    assert deal["title"] in [r["title"] for r in catalysts.ticker_view(out, [dict(twin, reach="sector")])["rows"]]


def test_the_library_route_answers_a_ticker_with_the_company_and_what_reaches_it(company, monkeypatch):
    monkeypatch.setattr(main, "YF_PROVIDER", company)
    monkeypatch.setattr(main.live_mirror, "active", lambda: False)
    catalysts.upsert([
        {"id": "a1", "event_date": TODAY.isoformat(), "title": "Chip export rule",
         "summary": "", "category": "geopolitical", "horizon": "long-term", "themes": [],
         "sectors": ["Technology"], "companies": [{"ticker": "NVDA", "name": "NVIDIA CORP",
                                                   "directness": "direct", "strength": "strong",
                                                   "why": "x"}],
         "source_url": "https://s.example/1", "source_name": "BBC News"},
        {"id": "a2", "event_date": TODAY.isoformat(), "title": "AI data-centre subsidy",
         "summary": "", "category": "government", "horizon": "long-term", "themes": [],
         "sectors": ["Technology"], "companies": [], "source_url": "https://s.example/2",
         "source_name": "CNBC"},
        {"id": "a3", "event_date": TODAY.isoformat(), "title": "Oil supply cut",
         "summary": "", "category": "commodity", "horizon": "medium-term", "themes": [],
         "sectors": ["Energy"], "companies": [], "source_url": "https://s.example/3",
         "source_name": "CNBC"},
    ])
    before = catalysts.count()
    body = TestClient(main.app).get("/api/catalysts", params={"q": "nvda"}).json()
    assert body["ticker"]["symbol"] == "NVDA" and body["ticker"]["rows"]
    assert [(c["title"], c["reach"]) for c in body["catalysts"]] == [
        ("Chip export rule", "linked"), ("AI data-centre subsidy", "sector")]
    assert catalysts.count() == before, "a search stores nothing"
    theme = TestClient(main.app).get("/api/catalysts", params={"q": "oil"}).json()
    assert "ticker" not in theme and [c["title"] for c in theme["catalysts"]] == ["Oil supply cut"]


# ------------------------------------------------------------ the provider


def test_yahoo_headlines_come_from_search_when_the_ticker_feed_is_empty(monkeypatch):
    """Measured with yfinance 1.2.0: Ticker("NVDA").news was empty and Search
    returned a dozen stories."""
    from app.providers import yf as yfp

    class Ticker:
        def __init__(self, sym):
            self.news = []

    class Search:
        def __init__(self, sym, max_results=8, news_count=8):
            self.news = [
                {"uuid": "1", "title": "Nvidia share buyback plan gets $150 billion boost",
                 "publisher": "CNBC", "link": "https://y.example/1",
                 "providerPublishTime": 1790699940, "relatedTickers": ["NVDA"]},
                {"uuid": "2", "title": "Stock Market Today: Dow dips", "publisher": "IBD",
                 "link": "https://y.example/2", "providerPublishTime": 1790699940,
                 "relatedTickers": ["^DJI", "AAPL"]},
            ]

    monkeypatch.setattr(yfp.yf, "Ticker", Ticker)
    monkeypatch.setattr(yfp.yf, "Search", Search)
    monkeypatch.setattr(yfp, "_cached", lambda key, ttl, build: build())
    items = yfp.YFinanceProvider().news("NVDA", limit=10)
    assert [i["title"] for i in items] == ["Nvidia share buyback plan gets $150 billion boost"]
    assert items[0]["url"] == "https://y.example/1" and items[0]["published"].startswith("2026-")


# ------------------------------------------------------------------ the page

APP_RAW = (ROOT / "static/app.js").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _raw_fn(name):
    return re.search(r"^(?:async )?function " + name + r"\([^\n]*\) \{.*?^\}",
                     APP_RAW, re.M | re.S).group()


def _const(name):
    one = re.search(r"^const " + name + r" = \{[^\n]*\};$", APP_RAW, re.M)
    return (one or re.search(r"^const " + name + r" = \{.*?^\};", APP_RAW, re.M | re.S)).group()


def _js(scenario):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = ("function assert(v, m) { if (!v) throw new Error(m); }\n"
           "function fmt(v, d) { return Number(v).toFixed(d); }\n"
           + "\n".join(_const(n) for n in ("CAT_HORIZON_CLASS", "CAT_DIRECT_CLASS",
                                           "CAT_STRENGTH_CLASS", "CAT_BASIS"))
           + "\n" + "\n".join(_raw_fn(n) for n in ("esc", "httpUrl", "catalystCard",
                                                    "catalystTickerHTML", "catalystCountLine",
                                                    "catalystScanLine", "catalystEmptyText"))
           + "\n" + scenario + "\nprint('TEST_OK');")
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=30)
    assert "TEST_OK" in out.stdout, out.stdout + out.stderr


def test_the_page_shows_the_company_its_factors_and_where_each_card_came_from():
    _js("""
      var row = {title: 'NVIDIA 8-K: Results of operations', horizon: 'short-term',
                 category: 'corporate', factor: 'Earnings and guidance', basis: 'filing',
                 event_date: '2026-08-26', relevant: true, companies: [],
                 source_url: 'https://sec.example/a', source_name: 'SEC EDGAR'};
      var next = {title: 'NVIDIA reports earnings on 2026-11-17', horizon: 'short-term',
                  factor: 'Earnings and guidance', basis: 'calendar', upcoming: true,
                  relevant: true, companies: []};
      var html = catalystTickerHTML({symbol: 'NVDA', name: 'NVIDIA Corporation', rows: [next, row],
        factors: [{factor: 'Earnings and guidance', count: 2}],
        sources: [{label: 'Its headlines', ok: true}, {label: 'Its SEC filings', ok: false}],
        method: 'Read now, not stored.'});
      assert(html.indexOf('data-analyse="NVDA"') > 0, 'the symbol opens the company');
      assert(html.indexOf('2 catalysts across 1 factor.') > 0, html);
      assert(html.indexOf('Earnings and guidance <strong>2</strong>') > 0, 'the factor count');
      assert(html.indexOf('Could not be read this time: Its SEC filings.') > 0, 'a missing source is named');
      assert(html.indexOf('>SEC filing<') > 0 && html.indexOf('>calendar<') > 0, 'each says where it came from');
      assert(html.indexOf('>upcoming<') > 0, 'the next report is marked');
      var none = catalystTickerHTML({symbol: 'MSFT', name: 'Microsoft', rows: [], factors: [], sources: []});
      assert(none.indexOf('reads as a catalyst right now') > 0, none);
      assert(catalystTickerHTML(undefined) === '', 'no ticker, no section');
    """)


def test_the_library_says_how_each_catalyst_reaches_the_company():
    _js("""
      var d = {ticker: {symbol: 'NVDA', sector: 'Technology'},
               catalysts: [{reach: 'linked'}, {reach: 'sector'}, {reach: 'sector'}]};
      assert(catalystCountLine(d) === 'In the library: 1 linked to NVDA, 2 through its sector (Technology)',
             catalystCountLine(d));
      assert(catalystCountLine({matched: 3, stored_total: 9}) === '3 catalysts of 9 stored', 'a text search');
      var card = catalystCard({title: 'T', reach: 'sector', relevant: true, companies: []});
      assert(card.indexOf('through its sector') > 0, 'a sector read-through is marked');
      assert(catalystEmptyText({ticker: {symbol: 'NVDA', sector: 'Technology'}, stored_total: 4, scan: {}})
             === 'Nothing in the library names NVDA or is filed under its sector (Technology) yet.', 'empty');
      assert(catalystScanLine({last_ok_at: null, every_hours: 1})
             === ' · No scan has finished yet. The library rescans the wires every hour.', 'hourly');
    """)


def test_the_scan_line_counts_what_was_already_stored():
    fn = _raw_fn("refreshCatalysts")
    assert "r.known ? ` · ${r.known} already in the library` : ''" in fn
