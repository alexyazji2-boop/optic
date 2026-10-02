"""Every ticker's News tab has the stories the feed has for it.

Reported with COIN's News tab reading "No headlines returned for this ticker":
"no news on coinbase? hard to believe, fix this issue across all tickers". On
the live site that day COIN had none while NVDA, AAPL and MSTR had a dozen
each, Disney six and Ford three, and a search for "COIN" from here found 21
stories tagged with it.

`Ticker.news` has been empty for every symbol since September, so every page
rested on a search for the bare symbol: for COIN, ALL or F a search for a word.
An error from the first feed returned before the search was tried, and an empty
answer was kept for ten minutes. Then the relevance rule matched a symbol in
any case, so "Coin Flip" was Coinbase news, and read the company only by its
full name, so "Disney" and "Ford" headlines were dropped as off-topic.

Now the company's name is searched too when the symbol finds few, a failing
feed hands on to the next, an empty answer stands two minutes with the last
good list shown meanwhile, a symbol counts in capitals, and a story Yahoo
tagged with the symbol alone counts when it uses a word of the name.

Measured on 2 October with the new code against the live feed: COIN 0 to 12,
DIS 6 to 12, F 3 to 10, ALL 9 to 12, and NVDA, AAPL, META, TSLA, JPM and CAT
as they were.
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from app import news
from app.providers import yf as Y

APP = (Path(__file__).resolve().parent.parent / "static/app.js").read_text()


def _story(uid, title, tags, at=1790900000):
    return {"uuid": uid, "title": title, "publisher": "Wire", "link": "https://y.example/" + uid,
            "providerPublishTime": at, "relatedTickers": tags}


class _Yahoo:
    """Yahoo's two feeds, scripted per query, recording what was asked."""

    def __init__(self, searches, ticker_news=None, ticker_raises=False, search_raises=()):
        self.searches, self.ticker_news = searches, ticker_news or []
        self.ticker_raises, self.search_raises = ticker_raises, set(search_raises)
        self.asked = []
        yahoo = self

        class Ticker:
            def __init__(self, sym):
                self.sym = sym

            @property
            def news(self):
                yahoo.asked.append(("ticker", self.sym))
                if yahoo.ticker_raises:
                    raise RuntimeError("Too Many Requests")
                return yahoo.ticker_news

        class Search:
            def __init__(self, query, max_results=8, news_count=8):
                yahoo.asked.append(("search", query))
                if query in yahoo.search_raises:
                    raise RuntimeError("Too Many Requests")
                self.news = yahoo.searches.get(query, [])

        self.Ticker, self.Search = Ticker, Search


@pytest.fixture
def provider(monkeypatch):
    def make(yahoo, name="Coinbase Global, Inc."):
        monkeypatch.setattr(Y.yf, "Ticker", yahoo.Ticker)
        monkeypatch.setattr(Y.yf, "Search", yahoo.Search)
        monkeypatch.setattr(Y, "_CACHE", {})
        monkeypatch.setattr(Y, "_NEWS_GOOD", {})
        p = Y.YFinanceProvider()
        monkeypatch.setattr(p, "quote", lambda sym: {"name": name})
        return p
    return make


WORD = [_story("w1", "Williams Says the Fed Has Time. Odds Fell Below a Coin Flip", ["BTC-USD"]),
        _story("w2", "Bitcoin Crosses $86,000", ["BTC-USD", "MSTR"])]
NAMED = [_story("n1", "Piper Sandler Adjusts Coinbase Global Price Target to $170", ["COIN"]),
         _story("n2", "Coinbase Shares Rise on Volumes", ["COIN"]),
         _story("n3", "Bitcoin Crosses $86,000", ["BTC-USD", "MSTR"])]


def test_a_symbol_that_is_a_word_is_searched_by_the_companys_name(provider):
    yahoo = _Yahoo({"COIN": WORD, "Coinbase Global": NAMED})
    items = provider(yahoo).news("COIN", limit=36)
    assert [i["title"] for i in items] == [
        "Piper Sandler Adjusts Coinbase Global Price Target to $170", "Coinbase Shares Rise on Volumes"]
    assert yahoo.asked == [("ticker", "COIN"), ("search", "COIN"), ("search", "Coinbase Global")]
    assert items[0]["tickers"] == ["COIN"]


def test_a_feed_that_errors_hands_on_to_the_next(provider):
    yahoo = _Yahoo({"COIN": NAMED[:2]}, ticker_raises=True)
    items = provider(yahoo).news("COIN", limit=3)
    assert len(items) == 2, "it returned before the search was tried"


def test_a_symbol_search_that_finds_enough_asks_nothing_more(provider):
    many = [_story("s%d" % i, "Coinbase story %d" % i, ["COIN"]) for i in range(30)]
    yahoo = _Yahoo({"COIN": many})
    assert len(provider(yahoo).news("COIN", limit=36)) == 30
    assert ("search", "Coinbase Global") not in yahoo.asked


def test_an_empty_answer_shows_the_last_good_list_and_is_soon_asked_again(provider):
    yahoo = _Yahoo({"COIN": NAMED[:2]})
    p = provider(yahoo)
    first = p.news("COIN", limit=36)
    assert len(first) == 2
    yahoo.searches = {}                                   # the feed goes quiet
    Y._CACHE.pop("news:COIN")
    assert p.news("COIN", limit=36) == first, "the last good list, not an empty page"
    assert Y._CACHE["news:COIN"][1] == []
    asked = len(yahoo.asked)
    p.news("COIN", limit=36)
    assert len(yahoo.asked) == asked, "within two minutes the empty answer stands"
    Y._CACHE["news:COIN"] = (time.time() - Y.YFinanceProvider.TTL_NEWS_EMPTY - 1, [])
    p.news("COIN", limit=36)                              # drops the old empty answer
    p.news("COIN", limit=36)
    assert len(yahoo.asked) > asked, "and after them it is asked again"
    Y._NEWS_GOOD["news:COIN"] = (time.time() - Y.YFinanceProvider.NEWS_STALE_FOR - 1, first)
    Y._CACHE.pop("news:COIN", None)
    assert p.news("COIN", limit=36) == [], "six hours on, an empty page is the answer"


def test_every_feed_failing_is_not_cached_as_no_news(provider):
    yahoo = _Yahoo({}, ticker_raises=True, search_raises={"COIN", "Coinbase Global"})
    p = provider(yahoo)
    assert p.news("COIN", limit=36) == []
    assert "news:COIN" not in Y._CACHE, "a failure is tried again on the next read"


def test_the_symbol_counts_in_capitals_and_the_name_in_any_case():
    coin = ("COIN", "Coinbase Global, Inc.")
    assert not news.mentions_company("October Rate Hike Odds Fell Below a Coin Flip", *coin)
    assert news.mentions_company("XYZ, COIN, MSTR Stocks Get Target Hikes", *coin)
    assert news.mentions_company("coinbase shares jump", *coin)
    assert news.mentions_company("Meta unveils new smart glasses", "META", "Meta Platforms, Inc.")
    assert news.mentions_company("Uber expands robotaxi deal", "UBER", "Uber Technologies, Inc.")
    assert not news.mentions_company("Stocks rally on Fed hopes", "ON", "ON Semiconductor Corporation")
    assert not news.mentions_company("All three indexes close higher", "ALL", "The Allstate Corporation")
    assert not news.mentions_company("Now is the time to buy", "NOW", "ServiceNow, Inc.")


def test_a_story_tagged_with_the_symbol_alone_counts_when_it_names_the_company():
    disney = news._name_words("The Walt Disney Company")
    ford = news._name_words("Ford Motor Company")
    assert disney == ["Walt", "Disney"] and ford == ["Ford", "Motor"]
    alone = {"tickers": ["DIS"]}
    assert news.tagged_about(alone, "DIS", "Disney TV restructuring targets hundreds of jobs", disney)
    assert not news.tagged_about(alone, "DIS", "A Superman comic sold for $9.1 million", disney)
    assert not news.tagged_about({"tickers": ["DIS", "NFLX"]}, "DIS", "Disney and Netflix raise prices",
                                 disney), "tagged with another company as well"
    assert news.tagged_about({"tickers": ["F"]}, "F", "Ford US Vehicle Sales Drop 6.6% in Q3", ford)
    assert not news.tagged_about({"tickers": ["F"]}, "F",
                                 "Breakthrough T1D Walks Bring Communities Together", ford)


def test_the_page_keeps_disneys_and_fords_own_headlines():
    class Feed:
        def __init__(self, items, name):
            self.items, self.name = items, name

        def news(self, ticker, limit=12):
            return self.items

        def earnings_date(self, ticker):
            return None

        def quote(self, ticker):
            return {"name": self.name}

    rows = [{"title": t, "summary": "", "publisher": "Wire", "published": "", "url": "u" + t,
             "tickers": tags} for t, tags in (
        ("Disney TV restructuring targets hundreds of jobs", ["DIS"]),
        ("Disney president defends ongoing company layoffs", ["DIS"]),
        ("A Superman comic sold for $9.1 million", ["DIS"]),
        ("Stocks That Explain Today's Market", ["DIS", "NVDA", "TSLA"]))]
    out = news.analyse(Feed(rows, "The Walt Disney Company"), "DIS", 12)
    assert sorted(a["title"] for a in out["articles"] if a["about_company"]) == [
        "Disney TV restructuring targets hundreds of jobs",
        "Disney president defends ongoing company layoffs"]


def test_the_page_says_how_it_matches():
    fn = APP[APP.index("function newsTierLegend(news, matched) {"):]
    fn = fn[:fn.index("\n}\n")]
    assert "the headline and summary for the symbol, in capitals, or the company name," in fn
    assert "a story the feed tagged with this symbol alone when it uses" in fn
