"""News triage: relevance first, then importance, and neither claims causation.

The headline panel rendered twelve items in provider order, which makes the
reader do the triage. Worse, the order is the publisher's: a week-old analyst
note sat above an earnings miss.

Two things were added, and the second exists because the first made the page
wrong in a new way.

**Tiers.** Breaking / Major / Notable / Background, decided by age and by the
catalyst taxonomy that was already in this module. Not by tone: a lexicon sum
measures how excited a headline is, and "shares soar" scores higher than "SEC
opens investigation".

**Relevance.** The feed is not per-company whatever the argument implies.
Measured on the live feed, asking for NVDA returned "RF Industries, Ltd. Q3 2026
Earnings Call Summary", which is fresh and tagged `earnings`, so tiering alone
sorted another company's results to the top of NVDA's page as Breaking. Ranking
made the page more wrong. Relevance is now decided before importance.

Measured on the live feed after both changes:

    NVDA  matched_on ['NVDA','NVIDIA']  2 about, 8 context
          RF Industries demoted out of the lead; Nvidia items lead
    TSLA  matched_on ['TSLA','Tesla']   6 about, 4 context
"""

from app import news


def test_the_tiers_are_ordered_worst_to_best_known():
    """`TIER_ORDER` is the sort key, so its order *is* the hierarchy."""
    assert news.TIER_ORDER == [news.TIER_BREAKING, news.TIER_MAJOR,
                              news.TIER_NOTABLE, news.TIER_BACKGROUND]


def test_every_tier_publishes_the_rule_it_claims():
    """The rule travels with the tier so the badge and its meaning cannot
    drift, the same reason `knowledge.catalogue()` publishes what a mode
    changes. A badge whose rule lived in the client's copy would be two records
    of one fact."""
    ids = [t["id"] for t in news.TIERS]
    assert ids == news.TIER_ORDER
    for tier in news.TIERS:
        assert tier["label"]
        assert tier["rule"].endswith("."), tier["id"]
        assert len(tier["rule"]) > 25, tier["id"]


def test_nothing_is_called_market_moving():
    """The brief asked for a MARKET MOVING tier. Nothing here can support it:
    showing a headline moved the market means showing the market moved *because
    of it*, and only same-day coincidence is available.

    This repo has made the mistake once. The factor panel was titled "Why it's
    moving" over a list ranked by absolute score, so on a down day its three
    strongest readings all read bullish, and it was reported as a rendering
    fault. A tier is named for what was measured.
    """
    blob = " ".join(t["label"] + " " + t["rule"] for t in news.TIERS).lower()
    assert "market moving" not in blob
    assert "moves the market" not in blob
    for tier in news.TIERS:
        assert "because" not in tier["rule"].lower(), tier["id"]


# ------------------------------------------------------------------ the tiers

def test_fresh_and_substantial_is_breaking():
    got = news.tier_for(0.2, [{"type": "earnings", "importance": "high"}])
    assert got["tier"] == news.TIER_BREAKING
    assert "12 minutes ago" in got["why"]
    assert "earnings" in got["why"]


def test_fresh_and_trivial_is_not_breaking():
    """Recency is not importance. A product launch filed twenty minutes ago
    must not outrank an earnings miss, or the tier just re-sorts by age."""
    got = news.tier_for(0.3, [{"type": "product news", "importance": "low"}])
    assert got["tier"] == news.TIER_NOTABLE
    assert "no catalyst of substance" in got["why"]


def test_a_high_catalyst_is_major_however_old():
    got = news.tier_for(400.0, [{"type": "M&A", "importance": "high"}])
    assert got["tier"] == news.TIER_MAJOR
    assert "M&A" in got["why"]


def test_an_item_with_no_timestamp_is_never_breaking():
    """Some publishers in this feed return no date. Treating absent as recent
    would pin every undated item to the top of the page forever."""
    got = news.tier_for(None, [{"type": "earnings", "importance": "high"}])
    assert got["tier"] == news.TIER_MAJOR
    got = news.tier_for(None, [])
    assert got["tier"] == news.TIER_BACKGROUND


def test_nothing_matched_is_background_and_says_so():
    got = news.tier_for(500.0, [])
    assert got["tier"] == news.TIER_BACKGROUND
    assert "No catalyst matched" in got["why"]


def test_the_breaking_window_is_tight_enough_to_sort_anything():
    """Bounds, not a pinned value. A company feed during a session is mostly
    "today", so a 24-hour window would hold most of the list and sort nothing."""
    assert 1.0 <= news.BREAKING_HOURS <= 6.0


def test_every_tier_is_reachable():
    """A tier nothing can land in is a badge that never renders."""
    seen = {
        news.tier_for(0.1, [{"type": "earnings", "importance": "high"}])["tier"],
        news.tier_for(99.0, [{"type": "earnings", "importance": "high"}])["tier"],
        news.tier_for(99.0, [{"type": "product news", "importance": "low"}])["tier"],
        news.tier_for(99.0, [])["tier"],
    }
    assert seen == set(news.TIER_ORDER)


# -------------------------------------------------------------- age in words

def test_ages_read_as_sentences():
    cases = {0.0: "just now", 0.2: "12 minutes ago", 1.0: "1 hour ago",
             5.0: "5 hours ago", 48.0: "2 days ago"}
    for hours, words in cases.items():
        assert news._age_words(hours) == words, hours
    assert news._age_words(None) == "at an unstated time"


def test_the_singular_is_not_one_hours_ago():
    assert news._age_words(1.0) == "1 hour ago"
    assert news._age_words(24.0) == "1 day ago"
    assert news._age_words(1 / 60.0) == "1 minute ago"


# ------------------------------------------------------------- the relevance

def test_the_symbol_alone_is_enough():
    assert news.mentions_company("NVDA hits a record high", "NVDA", "")


def test_the_company_name_is_matched_case_insensitively():
    assert news.mentions_company("Nvidia, Palantir pull back", "NVDA",
                                 "NVIDIA Corporation")


def test_corporate_form_words_are_stripped_from_the_name():
    """No headline says "NVIDIA Corporation", so an unstripped phrase never
    matches and the company's own news lands in Market context.

    Asserted as a substring over each term, not with `noise not in terms`.
    That was the first version and it is a list-membership test: "Corporation"
    is never its own element, so it passed with the stripping deleted. Caught by
    mutating `_NAME_NOISE.sub` away, which is the only reason it is written this
    way.
    """
    assert "NVIDIA" in news._match_terms("NVDA", "NVIDIA Corporation")
    for noise in ("corporation", "inc", "holdings", "the"):
        terms = news._match_terms("X", "Thing " + noise.title())
        for term in terms:
            assert noise not in term.lower(), (noise, terms)
    # And the phrase that is left is the one a headline would actually print.
    assert news._match_terms("NVDA", "NVIDIA Corporation") == ["NVDA", "NVIDIA"]


def test_another_companys_news_is_not_about_this_one():
    """The measured failure. Fresh and tagged `earnings`, and it led NVDA."""
    title = "RF Industries, Ltd. Q3 2026 Earnings Call Summary"
    assert not news.mentions_company(title, "NVDA", "NVIDIA Corporation")


def test_a_plural_of_a_generic_name_does_not_match_it():
    """`\\btarget\\b` must not match "Targets". Word boundaries are doing real
    work here, not decoration: a company called Target collides with the
    ordinary English word and this is the half of it that is fixable."""
    text = "Cisco's New Splunk AI Package Targets Computing"
    assert not news.mentions_company(text, "TGT", "Target Corporation")
    assert news.mentions_company("Target raises guidance", "TGT",
                                 "Target Corporation")


def test_a_generic_leading_word_is_not_a_company_match():
    """"Advanced Micro Devices" keeps the phrase and the symbol; "Advanced"
    alone would claim every headline about advanced anything. Same for General,
    American, First, United."""
    assert not news.mentions_company("Advanced AI chips announced", "AMD",
                                     "Advanced Micro Devices, Inc.")
    assert not news.mentions_company("General optimism lifts stocks", "GM",
                                     "General Motors Company")
    assert news.mentions_company("AMD beats on datacenter revenue", "AMD",
                                 "Advanced Micro Devices, Inc.")


def test_a_distinctive_leading_word_still_matches():
    """The stoplist must not swallow the cases the shortcut exists for:
    headlines say "Berkshire", not "Berkshire Hathaway Inc"."""
    assert news.mentions_company("Berkshire trims Apple stake", "BRK-B",
                                 "Berkshire Hathaway Inc.")


def test_a_missing_company_name_degrades_to_the_symbol():
    """`provider.quote` can fail. That has to make the split coarser, not
    wrong, and must never raise inside a news read."""
    assert news._match_terms("NVDA", "") == ["NVDA"]
    assert news.mentions_company("NVDA up 3%", "NVDA", "")
    assert not news.mentions_company("Cisco ships a router", "NVDA", "")


# ------------------------------------------------ relevance outranks the tier

def test_relevance_is_sorted_before_the_tier():
    """The whole point. A fresh high-catalyst headline about another company is
    still about another company."""
    src = open("app/news.py", encoding="utf-8").read()
    body = src[src.index("scored.sort("):]
    body = body[:body.index(")\n")]
    about_at = body.index("about_company")
    tier_at = body.index("TIER_ORDER.index")
    assert about_at < tier_at, "tier is outranking relevance"


def test_the_publishers_own_order_is_not_used():
    """It is the one ordering that is somebody else's editorial judgement."""
    src = open("app/news.py", encoding="utf-8").read()
    assert "scored.sort(" in src


# ------------------------------------------------------------------ the client
#
# Source-text contracts, which is this project's pattern for client wiring and
# is only sound because the behaviour itself was driven in a browser. Verified
# live on NVDA: two groups ("About this company 1", "Market context 9"), four
# tier rules with live counts, "Matched on NVDA, NVIDIA", and a badge whose
# tooltip read "Filed 24 minutes ago and tagged policy / supply chain."

import re

APP_JS = open("static/app.js", encoding="utf-8").read()
CSS = open("static/styles.css", encoding="utf-8").read()


def strip_comments(js):
    """Comments out first. Every claim below is also explained in a comment
    beside the code, so a raw read would pass on the explanation of a deleted
    line. That trap has caught me repeatedly in this codebase."""
    js = re.sub(r"/\*.*?\*/", " ", js, flags=re.S)
    return re.sub(r"(?<!:)//[^\n]*", " ", js)


CODE = strip_comments(APP_JS)


def body_of(name):
    start = CODE.index("function %s(" % name)
    return CODE[start:].split("\nfunction ", 1)[0]


def test_the_headlines_are_split_into_two_groups():
    fn = body_of("newsHeadlineSections")
    assert "a.about_company" in fn
    assert "!a.about_company" in fn
    assert "About this company" in fn
    assert "Market context" in fn


def test_market_context_is_kept_not_dropped():
    """A market-wide headline is often the reason a stock moved. Hiding it
    would be throwing away the feed's most useful half to fix its ordering."""
    fn = body_of("newsHeadlineSections")
    assert "context.map(newsArticleRow)" in fn


def test_an_empty_company_group_says_which_is_which():
    """Nothing naming the company is a normal state for this feed, and a blank
    heading above a full second group reads as a broken panel."""
    fn = body_of("newsHeadlineSections")
    assert "Nothing in the feed names this company" in fn


def test_the_badge_label_comes_from_the_server():
    """No hardcoded "Breaking" in the client. Same rule as the knowledge-mode
    chip: one copy of the wording, on the side that owns it."""
    fn = body_of("newsTierBadge")
    assert "tiers" in fn
    assert "label.label" in fn
    # Bare words, not quoted forms. The first version looked for `'Breaking'`
    # and `"Breaking"`, and a mutation that added
    # `return '<span class="nw-tier">Breaking</span>'` as a fallback sailed past
    # it: the word was inside a longer literal, so neither quoted form matched.
    for label in (t["label"] for t in news.TIERS):
        assert label not in fn, label


def test_the_badge_carries_its_own_reason():
    """The legend explains the tiers in general; `tier_why` explains this item.
    A reader asking why *this* headline is Major gets it on the headline."""
    assert "a.tier_why" in body_of("newsTierBadge")


def test_the_legend_renders_the_servers_rules():
    fn = body_of("newsTierLegend")
    assert "news.tiers" in fn
    assert "t.rule" in fn
    assert "tier_counts" in fn


def test_the_legend_states_what_the_grouping_cannot_do():
    """House rule: every panel says what it cannot tell you. Two limits here,
    and the second is the one that matters: a tier is not a claim about price."""
    fn = body_of("newsTierLegend")
    assert "What this cannot do" in fn
    assert "without naming it" in fn
    assert "caused a move" in fn


def test_the_client_does_not_call_any_tier_market_moving():
    for name in ("newsTierBadge", "newsTierLegend", "newsHeadlineSections"):
        assert "market moving" not in body_of(name).lower(), name


def test_the_age_is_shown_in_words_not_in_hours():
    """It read "0h ago" for anything under thirty minutes, which is the window
    where the age matters most."""
    fn = body_of("newsArticleRow")
    assert "a.age_words" in fn
    assert "h ago" not in fn


# The tier styles, sliced out of the stylesheet.
#
# Anchored on "\n.nw-tier {" rather than ".nw-tier {". A bare substring matches
# inside any descendant selector that ends in this class, and one arrived:
# `.pl-story > .nw-tier { justify-self: start; }` in the Pulse block, which sits
# ~3,000 lines earlier in the file. The slice then started there and ran to the
# news block, swallowing `.pl-bar.tone-up { background: var(--pos) }` on the way
# — so both tests below failed reporting a directional colour in the tier styles
# that was never in them. The newline pins it to a rule at top level.
TIER_BLOCK_START = "\n.nw-tier {"


def test_every_tier_has_a_style_and_none_of_them_is_directional():
    """--pos/--neg mean up and down in every percentage, candle and volume bar
    in this app. A tier is not a direction, and painting Breaking green would
    say a fresh headline is good news before anyone has read it. The VIX tile
    shipped that mistake in the other direction once."""
    block = CSS[CSS.index(TIER_BLOCK_START):CSS.index(".nw-count {")]
    for tier in news.TIER_ORDER:
        assert ".nw-tier.t-%s" % tier in CSS or tier == "notable", tier
    assert "--pos" not in block
    assert "--neg" not in block


def test_the_tier_styles_use_tokens_only():
    """No hex literals. `--ink-3` was invented for the Major border here and
    does not exist, so the declaration was silently dropped;
    tests/test_css_variables.py caught it."""
    block = CSS[CSS.index(TIER_BLOCK_START):CSS.index(".nw-legend ul")]
    assert "#" not in block, "hex literal in the tier styles"
    for var in re.findall(r"var\((--[a-z0-9-]+)\)", block):
        assert "  %s:" % var in CSS, var
