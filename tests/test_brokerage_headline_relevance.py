"""Brokerage's briefing lists only headlines about the holding.

Recorded on the evening of 26 October 2026 from the same Yahoo feeds the
briefing reads: NVDA's carried BlackBerry, Costco, Nike, Intel and SpaceX
stories, and NOW's carried gas prices and "where to deploy cash now". The
briefing had no relevance test and listed all of them as possibly related to
the holding's move."""

import json
from datetime import datetime, timezone
from pathlib import Path

from app import news
from app.brokerage import briefing

FIX = json.loads((Path(__file__).parent / "fixtures" / "brokerage_news_NVDA_NOW_2026-10-26.json").read_text())
FEEDS = FIX["feeds"]
NOW_UTC = datetime(2026, 10, 27, 2, 30, tzinfo=timezone.utc)


def _drivers(rows):
    return briefing.headlines_for(rows, lambda s: FEEDS[s]["news"], NOW_UTC,
                                  company_of=lambda s: FEEDS[s]["company"])


def test_nvda_gets_no_other_companys_story_and_says_so():
    got = _drivers([{"symbol": "NVDA", "change_pct": 1.2, "contribution": 50.0}])[0]
    titles = " ".join(h["title"] for h in got["headlines"])
    for other in ("BlackBerry", "Costco", "Nike", "Intel", "SpaceX", "Alphabet"):
        assert other not in titles
    assert got["headlines"] == [] and got["status"] == "quiet"
    assert got["note"].startswith("No headline about NVDA in the last 36 hours.")
    assert "other companies or the wider market" in got["note"]
    # The Federal Reserve preview is market-wide: kept, but not under NVDA.
    assert [h["title"][:30] for h in got["market_context"]] == ["Here's Exactly What Investors "]


def test_now_needs_more_than_the_word_now():
    got = _drivers([{"symbol": "NOW", "change_pct": 4.1, "contribution": 80.0}])[0]
    titles = [h["title"] for h in got["headlines"]]
    assert titles and all("ServiceNow" in t for t in titles)
    assert not any("Gas Prices" in t or "deploy cash" in t for t in titles)
    assert got["status"] == "possibly_related" and "timing only" in got["note"]


def test_a_symbol_that_is_a_word_counts_only_written_as_a_ticker():
    sn = ("NOW", "ServiceNow, Inc.")
    assert not news.mentions_company("WATCH NOW: STOCKS EXTEND RALLY", *sn)
    assert not news.mentions_company("Gas Prices Now More Expensive", *sn)
    for text in ("Is $NOW a buy?", "Earnings preview (NYSE: NOW)", "Hold or Fold NOW Stock Ahead of Results?",
                 "ServiceNow (NOW) Rallies", "CRM, NOW, ADBE lead software lower", "servicenow cuts guidance"):
        assert news.mentions_company(text, *sn), text
    agilent = ("A", "Agilent Technologies, Inc.")
    assert not news.mentions_company("A Look at Rates Before the Fed", *agilent)
    assert news.mentions_company("Agilent beats estimates", *agilent)
    assert news.is_word_symbol("F") and news.is_word_symbol("all") and not news.is_word_symbol("NVDA")


def test_a_relevant_story_is_listed_and_market_context_is_kept_apart_once():
    feed = {"NVDA": [{"title": "Nvidia unveils Rubin systems at GTC", "published": "2026-10-27T01:00:00Z",
                      "tickers": ["NVDA"], "url": "u1"},
                     {"title": "Stocks rise as Fed rate cut bets build", "published": "2026-10-27T00:00:00Z",
                      "url": "m1"}],
            "AMD": [{"title": "Stocks rise as Fed rate cut bets build", "published": "2026-10-27T00:00:00Z",
                     "url": "m1"},
                    {"title": "Costco October sales rise", "published": "2026-10-27T00:00:00Z", "url": "c1"}]}
    names = {"NVDA": {"name": "NVIDIA Corporation"}, "AMD": {"name": "Advanced Micro Devices, Inc."}}
    overview = {"holdings": [{"symbol": "NVDA", "kind": "equity", "quantity": 10},
                             {"symbol": "AMD", "kind": "equity", "quantity": 10}]}
    quotes = {"NVDA": {"price": 110.0, "prev_close": 100.0}, "AMD": {"price": 101.0, "prev_close": 100.0}}
    out = briefing.build(overview, {}, quotes, news_of=lambda s: feed[s], now=NOW_UTC,
                         company_of=lambda s: names[s])
    by = {d["symbol"]: d for d in out["drivers"]}
    assert [h["title"] for h in by["NVDA"]["headlines"]] == ["Nvidia unveils Rubin systems at GTC"]
    assert by["AMD"]["headlines"] == [] and by["AMD"]["set_aside"] == 1
    assert "market_context" not in by["NVDA"], "moved to the briefing's own list"
    assert [(m["title"], m["under"]) for m in out["market_context"]] == [
        ("Stocks rise as Fed rate cut bets build", ["NVDA", "AMD"])]


def test_the_page_shows_market_context_apart_and_says_the_rule():
    src = (Path(__file__).parent.parent / "static" / "v2" / "js" / "pages" / "brokerage.js").read_text()
    assert "b.market_context" in src and "Market context, not about one holding" in src
    assert "Only stories that name the company are listed under it." in src
