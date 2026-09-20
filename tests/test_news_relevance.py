"""What gets onto a ticker's News tab, and what does not.

Reported as "why is this here", against a headline on Apple's page reading
*"If You Had Invested $500 a Month in VOO Since Its 2010 Launch, You Would
Have About $330,000 Today"*.

Yahoo's per-ticker feed is not a per-ticker feed. Measured on AAPL the day
this was written, ten headlines came back and five named no company at all.
The relevance split already knew that and filed them under Market context,
which is honest labelling and not enough — and, worse, they were still voting:
`net_sentiment` is weighted over every scored row, so the VOO piece, scored
bearish by the lexicon on the strength of "crashes" and "pandemics", was
pulling Apple's news factor down. A headline about an index fund was moving a
reading about a company.

The asymmetry that decides every rule below is the same one recorded above
`mentions_company`: a false drop removes a real headline silently, a false
keep puts another company's story on this company's page. Filler is the one
exception where dropping is safe, because the shapes it matches are never news
about anything.
"""

from __future__ import annotations

import pytest

from app import news

APP_JS = open("static/app.js", encoding="utf-8").read()

SECTOR, INDUSTRY = "Technology", "Consumer Electronics"


def cat(kind):
    return [{"type": kind, "importance": "high"}]


# ------------------------------------------------------------------- filler


@pytest.mark.parametrize("headline", [
    # The reported one.
    "If You Had Invested $500 a Month in VOO Since Its 2010 Launch, You Would "
    "Have About $330,000 Today",
    # Its neighbours on the same feed.
    "Turning 73 Forces a Withdrawal From This Stock Whether the Owner Wants It",
    "A $10,000 Investment in SPY at Its 1993 Launch Is Worth This Much Today",
    "Can Your Retirement Plan Stand Up to Inflation? These 2 Tweaks May Help",
    "How Much You'd Have If You Bought Apple at the IPO",
    "Here Is How to Become a Millionaire on a $60,000 Salary",
    "Your 401(k) Is Not Enough. Here Is What Else to Do",
    "Dollar-Cost Averaging Beat Lump Sum in 7 of the Last 10 Years",
])
def test_personal_finance_filler_is_dropped(headline):
    assert news.is_filler(headline), headline


@pytest.mark.parametrize("headline", [
    # Every one of these contains a word the filler patterns are near.
    "Apple CFO Luca Maestri announces retirement",
    "Tesla announces $1 billion buyback as cash builds",
    "Fed holds rates steady as inflation cools",
    "Nvidia Q3 earnings beat on data centre revenue",
    "Berkshire's Apple stake is worth $150 billion after the rally",
    "Social media curbs in Australia draw Apple response",
])
def test_real_news_near_those_words_is_not_dropped(headline):
    """The expensive direction. "Retirement" is in a CEO departure, "worth $"
    is in a valuation story, "social security" is one word away from "social
    media". Every pattern is a *shape*, not a topic, for this reason."""
    assert not news.is_filler(headline), headline


def test_filler_goes_even_when_it_names_the_company():
    """"If You Had Invested $1,000 in Apple Ten Years Ago" is the same article
    with the name filled in, and the relevance test would keep it."""
    keep, why = news.keep_article(
        True, "If You Had Invested $1,000 in Apple Ten Years Ago You Would Have",
        [], SECTOR, INDUSTRY)
    assert keep is False and why == "filler"


# -------------------------------------------------------- naming the company


def test_anything_naming_the_company_is_kept():
    """The standing asymmetry. A weak headline that names Apple stays; a
    stronger one that does not, goes."""
    keep, _ = news.keep_article(True, "Apple ships a minor iOS point release",
                                [], SECTOR, INDUSTRY)
    assert keep is True


def test_another_companys_story_does_not_ride_a_catalyst_onto_this_page():
    """The leak that survived the first version of this filter.

    "Cramer strongly recommends buying beaten-down 90s tech legend" carried an
    `earnings` tag off the words "its Q2 cash flow" in the summary, and the
    first rule kept anything with a catalyst. It reached Apple's page as a
    *major* story about a company the headline does not name."""
    keep, why = news.keep_article(
        False,
        "Cramer strongly recommends buying beaten-down 90s tech legend. "
        "Jim Cramer touts a former mobile phone king as an AI buy, though its "
        "Q2 cash flow raises questions.",
        cat("earnings"), SECTOR, INDUSTRY)
    assert keep is False and why == "off-topic"


def test_a_rivals_supply_chain_story_does_not_ride_the_word_chip():
    """`policy / supply chain` fires on the bare word "chip", which put
    "TSMC owns more than two-thirds of the chip foundry market" on Apple's
    page. TSMC really does make Apple's chips; nothing here knows that, and
    inventing a supply-chain map to justify the keep would be worse."""
    keep, why = news.keep_article(
        False,
        "Taiwan Semiconductor Manufacturing's Foundry Market Share Is a Massive "
        "Moat Nobody Talks About. TSMC owns more than two-thirds of the chip "
        "foundry market.",
        cat("policy / supply chain"), SECTOR, INDUSTRY)
    assert keep is False and why == "off-topic"


# ------------------------------------------------------------ market context


@pytest.mark.parametrize("headline", [
    "Dow Drops To Record Worst Week In Six Months Amid Elevated Yields",
    "Fed signals two more rate cuts before year end",
    "CPI comes in hotter than forecast",
    "New tariffs on imported components take effect Monday",
    "Export controls tighten on advanced hardware",
])
def test_a_market_wide_headline_still_earns_its_place(headline):
    """Dropping these would be the over-correction. A market-wide headline is
    often the reason a stock moved; it is just not news about the company."""
    keep, _ = news.keep_article(False, headline, [], SECTOR, INDUSTRY)
    assert keep is True, headline


def test_legislation_and_macro_are_the_only_catalysts_that_travel():
    """A bill that decides whether an asset class is legal to custody is not
    background for the companies holding it, and it names none of them. Every
    other catalyst type describes something *a* company did, and on this page
    the company is fixed."""
    assert news.MARKET_CATALYSTS == frozenset({"legislation", "macro event"})
    for kind in ("legislation", "macro event"):
        keep, _ = news.keep_article(False, "Senate advances the CLARITY Act",
                                    cat(kind), SECTOR, INDUSTRY)
        assert keep is True, kind
    for kind in ("earnings", "guidance", "analyst action", "M&A",
                 "product news", "commercial deal", "management change"):
        keep, why = news.keep_article(False, "Some other company did a thing",
                                      cat(kind), SECTOR, INDUSTRY)
        assert keep is False and why == "off-topic", kind


def test_the_industry_earns_a_slot_but_the_sector_alone_does_not():
    """"Consumer Electronics" identifies something. "Technology", on a
    technology company, identifies most of the feed — the same reasoning as
    `_GENERIC_HEADS`, which exists because "General" would have claimed every
    headline containing the word for General Motors."""
    assert news.is_market_context(
        "Consumer Electronics demand softens into the holidays", SECTOR, INDUSTRY)
    assert not news.is_market_context(
        "A technology company you have never heard of just tripled", SECTOR, INDUSTRY)


# ------------------------------------------------------------- the pipeline


class _Provider:
    """Enough of a provider for `analyse`, with no network."""

    def __init__(self, items):
        self._items = items

    def news(self, ticker, limit=12):
        return self._items[:limit]

    def quote(self, ticker):
        return {"name": "Apple Inc.", "sector": SECTOR, "industry": INDUSTRY}

    def earnings_date(self, ticker):
        return None


def _item(title, summary="", published="2026-09-20T12:00:00Z"):
    return {"title": title, "summary": summary, "publisher": "Test",
            "published": published, "url": "https://example.com"}


def test_the_off_topic_bearish_headline_no_longer_moves_the_tone():
    """The measurement that made this worth fixing rather than tidying.

    The VOO piece scores bearish on "crashes" and "pandemics". Filed under
    Market context it still reached the recency-weighted average, so a story
    about an index fund was making Apple's news factor negative."""
    noise = _item(
        "If You Had Invested $500 a Month in VOO Since Its 2010 Launch, You "
        "Would Have About $330,000 Today",
        "Fifteen years of automatic S&P 500 investing through crashes, "
        "pandemics, and AI euphoria reveals something surprising.")
    signal = _item("Apple ships a minor iOS point release")

    # The lexicon really does read that headline as bearish; if it stops, this
    # test is measuring nothing and should be rewritten rather than deleted.
    score, _hits = news._score_text(noise["title"] + " " + noise["summary"])
    assert score < 0, "the premise of this test is that the filler scores bearish"

    out = news.analyse(_Provider([signal, noise]), "AAPL", limit=12)
    assert [a["title"] for a in out["articles"]] == [signal["title"]]
    assert out["dropped"]["filler"] == 1
    assert out["net_sentiment"] >= 0


def test_the_panel_reports_what_it_removed():
    """Without this a filtered page just looks short, and three headlines on a
    mega-cap reads as a broken feed rather than a working filter."""
    items = [
        _item("Apple beats on iPhone revenue"),
        _item("If You Had Invested $500 a Month in VOO"),
        _item("Some rival launches a product", "Its Q2 results were fine."),
    ]
    out = news.analyse(_Provider(items), "AAPL", limit=12)
    assert out["dropped"] == {"filler": 1, "off_topic": 1, "total": 2,
                              "surplus": 0}
    assert out["article_count"] == 1


def test_it_over_fetches_so_a_filtered_page_still_fills():
    """The filter removes about half of a ticker feed. A page that asked for
    twelve should still get twelve where twelve exist."""
    asked = {}

    class Counting(_Provider):
        def news(self, ticker, limit=12):
            asked["limit"] = limit
            return self._items[:limit]

    items = [_item("Apple story number {}".format(i)) for i in range(40)]
    out = news.analyse(Counting(items), "AAPL", limit=12)
    assert asked["limit"] > 12, "asking for exactly the limit under-fills"
    assert out["article_count"] == 12
    assert out["dropped"]["surplus"] > 0, "the surplus is reported, not hidden"


def test_the_sentiment_is_measured_over_what_is_shown():
    """Trimmed before the average, not after. Scoring over rows the reader
    cannot see makes `net_sentiment` a claim about evidence off screen."""
    body = news.__file__ and open("app/news.py", encoding="utf-8").read()
    head, _, tail = body.partition("scored = scored[:limit]")
    assert tail, "the trim is gone"
    assert "weighted +=" not in head.split("scored.sort(")[-1], \
        "the average must come after the trim"
    assert "weighted +=" in tail


def test_a_quote_that_fails_does_not_take_the_feed_down():
    """`analyse` degrades to symbol-only matching rather than failing. Without
    a sector the context test gets coarser, not wrong."""
    class Broken(_Provider):
        def quote(self, ticker):
            raise RuntimeError("no network")

    out = news.analyse(Broken([_item("AAPL rises on strong iPhone demand")]),
                       "AAPL", limit=12)
    assert out["article_count"] == 1


# -------------------------------------------------------------------- the UI


def test_the_client_says_how_many_were_left_out():
    assert "function newsFilterNote(news)" in APP_JS
    fn = APP_JS.split("function newsFilterNote(news) {", 1)[1].split("\n}", 1)[0]
    assert "personal-finance filler" in fn
    assert "about other companies" in fn
    assert "if (!total) return '';" in fn, "a clean feed says nothing"
    sections = APP_JS.split("function newsHeadlineSections(news, arts) {", 1)[1]
    assert "newsFilterNote(news)" in sections.split("\n}", 1)[0]


def test_the_legend_admits_what_the_filter_costs():
    """House rule: every panel states what it cannot tell you. Here that is a
    supplier or a rival whose story is genuinely relevant and gets dropped
    with the noise."""
    legend = APP_JS.split("function newsTierLegend(news, matched) {", 1)[1]
    legend = legend.split("\n}", 1)[0]
    assert "supplier" in legend and "supply-chain map" in legend
