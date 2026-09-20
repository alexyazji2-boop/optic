"""Headline pass: sentiment scoring and catalyst tagging.

This is the fast, always-available layer. Sentiment is lexicon-based, which is
crude but transparent and instant — a headline scored "bearish" here can always
be checked against the words that triggered it. The deeper live-research pass
lives in ai.py.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

BULLISH_TERMS = {
    "beat": 3, "beats": 3, "tops": 3, "surge": 3, "surges": 3, "soar": 3, "soars": 3,
    "jump": 2, "jumps": 2, "rally": 2, "rallies": 2, "climb": 2, "climbs": 2,
    "upgrade": 3, "upgraded": 3, "outperform": 3, "buy rating": 3, "overweight": 2,
    "raises guidance": 4, "raised guidance": 4, "hikes forecast": 4, "record": 2,
    "all-time high": 3, "breakout": 2, "strong demand": 3, "expansion": 2,
    "approval": 3, "approved": 3, "wins": 2, "won": 2, "awarded": 2, "contract": 1,
    "partnership": 2, "acquisition": 2, "buyback": 3, "repurchase": 3,
    "dividend increase": 3, "raises dividend": 3, "profit": 1, "growth": 1,
    "bullish": 3, "optimistic": 2, "momentum": 1, "accelerating": 2, "rebound": 2,
    "price target raised": 3, "boosts": 2, "expands": 1, "milestone": 2,
}

BEARISH_TERMS = {
    "miss": 3, "misses": 3, "missed": 3, "plunge": 4, "plunges": 4, "crash": 4,
    "sink": 3, "sinks": 3, "tumble": 3, "tumbles": 3, "slump": 3, "slumps": 3,
    "fall": 1, "falls": 1, "drop": 2, "drops": 2, "slide": 2, "slides": 2,
    "downgrade": 3, "downgraded": 3, "underperform": 3, "sell rating": 3,
    "underweight": 2, "cuts guidance": 4, "cut guidance": 4, "lowers forecast": 4,
    "warns": 3, "warning": 3, "probe": 3, "investigation": 3, "lawsuit": 3,
    "sues": 2, "sued": 2, "subpoena": 3, "sec filing": 1, "fine": 2, "penalty": 2,
    "recall": 3, "halt": 3, "halted": 3, "layoffs": 3, "layoff": 3, "job cuts": 3,
    "resigns": 2, "resignation": 2, "steps down": 2, "bankruptcy": 5, "default": 4,
    "delisting": 4, "fraud": 4, "restatement": 3, "bearish": 3, "concerns": 1,
    "headwind": 2, "headwinds": 2, "slowdown": 2, "weak demand": 3, "shortfall": 3,
    "price target cut": 3, "dilution": 2, "offering": 1, "short seller": 3,
}

CATALYSTS: List[Tuple[str, str, str]] = [
    (r"\bearnings\b|\bq[1-4]\b|\bquarterly results\b|\breports? (?:q[1-4]|results)\b", "earnings", "high"),
    (r"\bguidance\b|\bforecast\b|\boutlook\b", "guidance", "high"),
    (r"\bupgrade|downgrade|price target|analyst\b", "analyst action", "medium"),
    (r"\bacquisition\b|\bmerger\b|\bacquires?\b|\bbuyout\b|\bm&a\b|\btakeover\b", "M&A", "high"),
    (r"\bfda\b|\bclinical\b|\bphase [123]\b|\btrial results?\b", "regulatory / clinical", "high"),
    (r"\bsec\b|\binvestigation\b|\bprobe\b|\blawsuit\b|\bantitrust\b|\bsubpoena\b", "legal / regulatory", "high"),
    (r"\bbuyback\b|\brepurchase\b|\bdividend\b|\bsplit\b", "capital return", "medium"),
    (r"\bceo\b|\bcfo\b|\bresign|\bappoint|\bexecutive\b", "management change", "medium"),
    (r"\blayoffs?\b|\bjob cuts\b|\brestructur", "restructuring", "medium"),
    (r"\blaunch|\bunveils?\b|\bannounces?\b|\bproduct\b", "product news", "low"),
    (r"\bpartnership\b|\bcontract\b|\bdeal\b|\bagreement\b", "commercial deal", "medium"),
    (r"\bshort (?:seller|report|interest)\b|\bsqueeze\b", "short interest", "high"),
    (r"\bchip|\bsemiconductor|\btariff|\bexport control|\bsanction", "policy / supply chain", "medium"),
    # Legislation, which the taxonomy had no pattern for at all.
    #
    # Measured: "Senate to vote on CLARITY Act for crypto market structure",
    # "House panel advances stablecoin legislation" and "Congress weighs crypto
    # regulatory framework bill" all classified as `[]`, which puts them in the
    # background tier and makes them invisible to anything reading catalysts. A
    # bill that decides whether an asset class is legal to custody is not
    # background for the companies holding it.
    #
    # Anchored on the legislative body or on the word legislation rather than on
    # "act" or "bill" alone: lowercased text makes `\w+ act` match "did not act"
    # and `\bbill\b` match a person called Bill.
    (r"\blegislation\b|\blawmakers?\b|\bsenate\b|\bcongress\b"
     r"|\bhouse (?:panel|committee|bill|vote|passes|advances)\b"
     r"|\bregulatory framework\b|\bmarket structure bill\b"
     r"|\b(?:passes|advances|introduces?|vote on) (?:the )?[a-z]+ act\b",
     "legislation", "high"),
    # Yields and the curve belong here. Without them "Stocks Decline, 10-Year
    # Treasury Yield Touches 5%" matched only "policy / supply chain" on the
    # word "tariff"-adjacent stem and was rated medium, so it ranked below a
    # corporate rebranding in the homepage story slot. A benchmark yield through
    # a round number is a macro event by any reading.
    (r"\bfed\b|\brate (?:cut|hike|decision)\b|\bcpi\b|\binflation\b|\bfomc\b"
     r"|\btreasury (?:yield|note|bond)s?\b|\byield curve\b|\b10-year\b"
     r"|\bten-year\b|\bjobs report\b|\bnonfarm\b|\bpayrolls\b|\bunemployment\b",
     "macro event", "high"),
]


# --------------------------------------------------------------- the hierarchy
#
# A flat feed makes the reader do the triage. Twelve headlines in provider order
# put an analyst note above an earnings miss and a week-old product launch above
# something that landed twenty minutes ago, and the only way to tell was to read
# all twelve.
#
# Three things decide a tier, and all three are already measured: how old the
# item is, what the catalyst taxonomy makes of it, and nothing else. There is no
# model here and no scoring of importance by tone, because a lexicon sum says
# how *excited* a headline is, which is not the same as how much it matters:
# "shares soar" scores higher than "SEC opens investigation".
#
# NOT CALLED "MARKET MOVING", which is what the brief asked for and what this
# cannot support. To say a headline moved the market you need to show the market
# moved *because of it*, and all that is available is whether the two happened
# on the same day. This codebase has made that mistake once already: the factor
# panel was titled "Why it's moving" over a list ranked by absolute score, so on
# a down day its three strongest readings were all bullish, and it was reported
# as a rendering fault. A tier is named for the thing that was measured.
TIER_BREAKING = "breaking"
TIER_MAJOR = "major"
TIER_NOTABLE = "notable"
TIER_BACKGROUND = "background"

TIER_ORDER = [TIER_BREAKING, TIER_MAJOR, TIER_NOTABLE, TIER_BACKGROUND]

# Three hours, not the more obvious twenty-four. The feed is a company news
# feed, so "today" is most of what it returns during a session and a tier that
# holds most of the list has sorted nothing.
BREAKING_HOURS = 3.0

_IMPORTANCE_RANK = {"high": 3, "medium": 2, "low": 1}

TIERS: List[Dict[str, str]] = [
    {
        "id": TIER_BREAKING,
        "label": "Breaking",
        "rule": "Filed in the last {:.0f} hours.".format(BREAKING_HOURS),
    },
    {
        "id": TIER_MAJOR,
        "label": "Major",
        "rule": "Carries a catalyst the taxonomy rates high: earnings, guidance, "
                "M&A, regulatory, legal, macro or short interest.",
    },
    {
        "id": TIER_NOTABLE,
        "label": "Notable",
        "rule": "Carries a catalyst of some kind, rated medium or low.",
    },
    {
        "id": TIER_BACKGROUND,
        "label": "Background",
        "rule": "No catalyst matched. Coverage, opinion and repetition sit here.",
    },
]


# ------------------------------------------------------- is it about this name
#
# The feed is not per-company, whatever the argument to it suggests. Asking for
# NVDA returns "RF Industries Q3 2026 Earnings Call Summary", "Cisco's New
# Splunk AI Package" and "Apple's Foldable Phone Has Arrived": market coverage
# that happens to be served under the symbol.
#
# Flat feed order hid that, and ranking by tier exposed it in the worst way. RF
# Industries' earnings is fresh and tagged "earnings", so it sorted to the top
# of NVDA's page as "Breaking" on the strength of a different company's results.
# Ranking made the page more wrong, which is the thing to catch before it ships
# rather than after.
#
# So relevance is decided before importance, and the test is whether the item
# names the company at all. Conservative in the direction that cannot mislead:
# an item that does not name it is market context, which is what it is even when
# it is genuinely relevant. Calling context "context" understates some headlines;
# calling another company's earnings "breaking news about NVDA" is false.

# Corporate-form words carry no identity, and leaving them in means the phrase
# never matches: no headline says "NVIDIA Corporation".
_NAME_NOISE = re.compile(
    r"\b(?:inc|incorporated|corp|corporation|co|company|companies|ltd|limited"
    r"|plc|llc|lp|holding|holdings|group|class\s+[a-c]|sa|nv|ag|se|ab|oyj"
    r"|trust|the)\b\.?",
    re.I,
)


# Leading words too ordinary to identify a company on their own. Dropped from
# the one-word shortcut below, not from the full name: "Advanced Micro Devices"
# still matches as a phrase, and AMD matches as a symbol.
#
# The asymmetry is what decides this list. A false positive puts another
# company's earnings at the top of this company's page, which is the bug the
# relevance split exists to fix. A false negative moves a real headline into
# "Market context", where it is still on screen and still tiered. So when in
# doubt, do not match: "General" would have claimed every headline containing
# the word for General Motors.
_GENERIC_HEADS = {
    "advanced", "general", "american", "national", "international", "united",
    "first", "global", "standard", "premier", "superior", "universal",
    "atlantic", "pacific", "northern", "southern", "eastern", "western",
    "central", "continental", "federal", "republic", "liberty", "capital",
    "digital", "applied", "integrated", "dynamic", "dynamics", "enterprise",
    "enterprises", "industries", "industrial", "consolidated", "diversified",
    "select", "prime", "core", "summit", "sterling", "signature", "alliance",
    "allied", "associated", "community", "regional", "commerce", "commercial",
    "public", "service", "services", "systems", "solutions", "partners",
    "resources", "energy", "power", "financial", "insurance", "health",
    "healthcare", "medical", "pharmaceutical", "pharmaceuticals", "materials",
    "products", "brands", "foods", "motors", "airlines", "banks", "bancorp",
}


def _match_terms(ticker: str, name: str) -> List[str]:
    """The strings whose presence means a headline is about this company."""
    terms = [ticker.strip().upper()] if ticker else []
    cleaned = _NAME_NOISE.sub(" ", name or "")
    cleaned = re.sub(r"[^\w\s&'-]", " ", cleaned)
    cleaned = " ".join(cleaned.split()).strip()
    if cleaned:
        terms.append(cleaned)
        # "Advanced Micro Devices" never appears in a headline that says AMD,
        # but "Nvidia" does. Only the leading word, and only when it is long
        # enough to be a name rather than an adjective.
        head = cleaned.split()[0]
        if (len(head) >= 5 and head.lower() != cleaned.lower()
                and head.lower() not in _GENERIC_HEADS):
            terms.append(head)
    return [t for t in dict.fromkeys(terms) if len(t) >= 2]


def mentions_company(text: str, ticker: str, name: str) -> bool:
    """Does this headline name the company, by symbol or by name?

    Word boundaries throughout, which is doing real work for the generic names:
    `\btarget\b` does not match "Cisco's package Targets computing", because
    the boundary after "target" needs a non-word character and "s" is not one.
    A company genuinely called Target still collides with the ordinary English
    word, and nothing here can fix that, so the panel says the rule out loud
    instead of implying a precision it does not have.
    """
    blob = text or ""
    for term in _match_terms(ticker, name):
        if re.search(r"\b" + re.escape(term) + r"\b", blob, re.I):
            return True
    return False


# --------------------------------------------------------------- the filter
#
# Yahoo's per-ticker feed is not a per-ticker feed. Measured on AAPL, ten
# headlines came back and five of them named no company at all:
#
#     If You Had Invested $500 a Month in VOO Since Its 2010 Launch...
#     Turning 73 Forces a Withdrawal From This Stock Whether the Owner...
#     Cramer strongly recommends buying beaten-down 90s tech legend
#     Why India's Big Tech Companies Are Betting on Hyderabad
#     Taiwan Semiconductor Manufacturing's Foundry Market Share...
#
# The relevance split already knew none of those were about Apple and filed
# them under Market context, which is honest labelling and not enough: a
# dollar-cost-averaging explainer about an index fund is not context for a
# company, it is filler that arrived on the same wire.
#
# **It was also moving the numbers.** `net_sentiment` is weighted over every
# scored row, so the VOO piece — scored bearish by the lexicon, on the strength
# of "crashes" and "pandemics" — was pulling Apple's news factor down. That is
# the part that made this worth fixing rather than tidying: a headline about a
# different instrument was changing a reading about this one.

# Never news about a company, whoever it names.
#
# Tight on purpose, and every pattern here is a *shape* rather than a topic. A
# topic list would take "retirement" and drop "Apple CFO announces retirement",
# which is real news; the retirement terms below are account mechanics that do
# not appear in corporate copy. The cost of a false positive is a real headline
# silently gone, which is worse than the filler it would remove.
_FILLER = re.compile(
    r"""
      \bif\s+you\s+(?:had\s+)?(?:invested|bought|put|owned)\b
    | \$[\d,.]+\s*(?:k\b)?\s*(?:a|per)\s+(?:month|week|year)\s+(?:in|into)\b
    | \b(?:you|you'?d)\s+would\s+have\b
    | \bhow\s+much\s+(?:you|i|we)(?:'d|\s+would|\s+will)?\s+(?:have|need)\b
    | \bturning\s+\d{2}\b
    | \b(?:rmd|required\s+minimum\s+distributions?)\b
    | \b(?:401\(?k\)?|roth\s+ira|social\s+security|nest\s+egg)\b
    | \bretirement\s+(?:account|savings|portfolio|plan)s?\b
    | \$[\d,.]+\s*(?:k\b)?\s+investment\s+in\b
    | \b(?:is|are|would\s+be)\s+worth\s+this\s+much\b
    | \bwould\s+be\s+worth\s+(?:about\s+)?\$
    | \bdollar[-\s]cost\s+averag
    | \bbecome\s+a\s+millionaire\b
    """,
    re.I | re.X,
)

# What earns a slot for a headline that never names the company.
#
# Market-wide things only: an index, a macro release, a policy lever. Not
# "another company did something", which is the class the relevance split was
# written for and which this now removes rather than relabels.
_MARKET_TERMS = re.compile(
    r"""
      \b(?:s&p\s*500|nasdaq|dow(?:\s+jones)?|russell\s*2000|vix)\b
    | \b(?:the\s+)?fed\b | \bfomc\b | \bfederal\s+reserve\b
    | \b(?:interest\s+)?rate\s+(?:cut|hike|decision)s?\b
    | \binflation\b | \bcpi\b | \bppi\b | \bjobs\s+report\b | \bpayrolls\b
    | \bgdp\b | \brecession\b | \btariffs?\b | \btreasury\s+yields?\b
    | \b(?:bond|elevated|rising|falling|surging)\s+yields?\b
    | \bexport\s+controls?\b | \bsanctions?\b | \btrade\s+war\b
    | \bbull\s+market\b | \bbear\s+market\b | \bselloff\b
    | \bearnings\s+season\b
    """,
    re.I | re.X,
)


def is_filler(text: str) -> bool:
    """Personal-finance syndication that is not news about anything."""
    return bool(_FILLER.search(text or ""))


def _sector_terms(sector: str, industry: str) -> List[str]:
    """Words from the company's own sector and industry.

    Whole words, and the single-word generics are dropped for the same reason
    `_GENERIC_HEADS` exists: "Technology" would claim every headline with the
    word in it, which on a technology company is most of the feed."""
    out: List[str] = []
    for raw in (sector or "", industry or ""):
        cleaned = re.sub(r"[^\w\s&-]", " ", raw)
        cleaned = " ".join(cleaned.split())
        # Multi-word only. "Consumer Electronics" identifies something;
        # "Technology" on a technology company identifies nothing.
        if cleaned and len(cleaned.split()) >= 2:
            out.append(cleaned)
    return out


def is_market_context(text: str, sector: str = "", industry: str = "") -> bool:
    """Is a headline that does not name the company still about its market?"""
    blob = text or ""
    if _MARKET_TERMS.search(blob):
        return True
    for term in _sector_terms(sector, industry):
        if re.search(r"\b" + re.escape(term) + r"\b", blob, re.I):
            return True
    return False


# Catalyst types that matter without naming a company.
#
# The rest of the taxonomy — earnings, guidance, analyst action, M&A, product
# news — describes something *a* company did, and on this page the company is
# fixed. Measured on AAPL: "Cramer strongly recommends buying beaten-down 90s
# tech legend" carried an `earnings` tag off the words "its Q2 cash flow" and
# rode it onto Apple's page as a major story about a company the headline does
# not even name. "TSMC owns two-thirds of the chip foundry market" did the same
# through `policy / supply chain`, which fires on the bare word "chip".
#
# Tariffs, sanctions and export controls are genuinely market-wide and are
# handled by `_MARKET_TERMS` instead, so they do not need a catalyst type here.
MARKET_CATALYSTS = frozenset({"legislation", "macro event"})


def keep_article(about: bool, text: str, catalysts: List[Dict[str, str]],
                 sector: str = "", industry: str = "") -> Tuple[bool, str]:
    """(keep, why not). One place, so the panel can report what it removed.

    Order matters. Filler is dropped even when it names the company, because
    "If You Had Invested $1,000 in Apple Ten Years Ago" is the same article
    with the name filled in. Everything else that names the company is kept
    without further argument: the asymmetry recorded above the relevance split
    still holds, and a false drop is worse than a weak keep.
    """
    if is_filler(text):
        return False, "filler"
    if about:
        return True, ""
    if any((c or {}).get("type") in MARKET_CATALYSTS for c in catalysts or []):
        return True, ""
    if is_market_context(text, sector, industry):
        return True, ""
    return False, "off-topic"


def _importance_rank(catalysts: List[Dict[str, str]]) -> int:
    """The strongest catalyst on an item, 0 when there is none."""
    return max((_IMPORTANCE_RANK.get(c.get("importance", ""), 0)
                for c in catalysts), default=0)


def tier_for(age_hours: Optional[float],
             catalysts: List[Dict[str, str]]) -> Dict[str, Any]:
    """Which tier an item sits in, and the reason in the reader's words.

    `why` is returned rather than composed in the client because the brief's own
    rule is that a claim has to be checkable: the tier is a judgement, so the
    sentence that justifies it travels with it and there is one copy of the
    wording.

    A missing timestamp cannot be breaking. Some publishers in this feed return
    none at all, and treating absent as recent would put every undated item at
    the top of the page permanently.
    """
    rank = _importance_rank(catalysts)
    fresh = age_hours is not None and age_hours <= BREAKING_HOURS
    names = ", ".join(sorted({c.get("type", "") for c in catalysts if c.get("type")}))

    if fresh and rank >= _IMPORTANCE_RANK["medium"]:
        return {
            "tier": TIER_BREAKING,
            "why": "Filed {} and tagged {}.".format(_age_words(age_hours), names),
        }
    if rank >= _IMPORTANCE_RANK["high"]:
        return {
            "tier": TIER_MAJOR,
            "why": "Tagged {}, which the taxonomy rates high.".format(names),
        }
    if fresh:
        # Fresh with nothing behind it. Recency alone is not importance, so it
        # ranks below a major catalyst rather than above it, and says so.
        return {
            "tier": TIER_NOTABLE,
            "why": "Filed {}, but no catalyst of substance matched.".format(
                _age_words(age_hours)),
        }
    if rank:
        return {
            "tier": TIER_NOTABLE,
            "why": "Tagged {}.".format(names),
        }
    return {
        "tier": TIER_BACKGROUND,
        "why": "No catalyst matched the headline or summary.",
    }


def _age_words(age_hours: Optional[float]) -> str:
    """Plain words for an age, because "0.4h ago" is not a sentence."""
    if age_hours is None:
        return "at an unstated time"
    minutes = int(round(age_hours * 60))
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return "{} minute{} ago".format(minutes, "" if minutes == 1 else "s")
    hours = int(round(age_hours))
    if hours < 24:
        return "{} hour{} ago".format(hours, "" if hours == 1 else "s")
    days = int(round(age_hours / 24.0))
    return "{} day{} ago".format(days, "" if days == 1 else "s")


def _score_text(text: str) -> Tuple[float, List[str]]:
    lowered = " " + re.sub(r"\s+", " ", text.lower()) + " "
    score = 0.0
    hits: List[str] = []
    for term, weight in BULLISH_TERMS.items():
        if term in lowered:
            score += weight
            hits.append("+" + term)
    for term, weight in BEARISH_TERMS.items():
        if term in lowered:
            score -= weight
            hits.append("-" + term)
    return score, hits



def _num(value: Any, digits: int = 4) -> Optional[float]:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return round(out, digits)


# How recent a catalyst has to be for the chart to be measuring the world before
# it. Three days: long enough to cover a Friday event read on a Monday, short
# enough that it is still the most recent thing the tape has priced.
CATALYST_WINDOW_HOURS = 72.0

def age_phrase(hours: Optional[float]) -> str:
    """"an hour ago", "3 hours ago", "2 days ago". Plural agreement included,
    because "1 hours ago" was what the first version printed."""
    if hours is None:
        return "recently"
    if hours < 1.5:
        return "an hour ago"
    if hours < 24:
        return "{:.0f} hours ago".format(hours)
    # The bands have to meet without overlapping or leaving a hole. A first
    # version ran hours to 36 and then asked whether days < 1.5, which is the
    # same boundary from both sides: every value at or above 36 hours was at
    # least 1.5 days, so "a day ago" could not be reached at all.
    if hours < 42:
        return "a day ago"
    return "{:.0f} days ago".format(hours / 24.0)


def count_words(n: int, noun: str) -> str:
    return "One {}".format(noun) if n == 1 else "{} {}s".format(n, noun)


def material_catalyst(news: Dict[str, Any]) -> Dict[str, Any]:
    """A material, company-specific catalyst inside the recent window.

    `news.py` already does this classification and the verdict was throwing it
    away. Its own comment explains why that matters: "a lexicon sum says how
    *excited* a headline is, which is not the same as how much it matters:
    'shares soar' scores higher than 'SEC opens investigation'." The tiers exist
    precisely because tone is not importance, and `_news_score` was reading
    tone alone.

    Four conditions, all from fields the feed already carries. The headline has
    to be about this company rather than the market, inside the window, in the
    breaking or major tier, and tagged with a catalyst the taxonomy rates high.
    An analyst note on a quiet week clears none of them.
    """
    articles = (news or {}).get("articles") or []
    hits: List[Dict[str, Any]] = []
    for row in articles:
        if not row.get("about_company"):
            continue
        age = row.get("age_hours")
        if age is None or age > CATALYST_WINDOW_HOURS:
            continue
        if row.get("tier") not in (TIER_BREAKING, TIER_MAJOR):
            continue
        # A headline announcing a future event is not evidence it happened.
        # "Senate to vote on CLARITY Act" and RARE's own "Sanfilippo Drug Ruling
        # Nears" both land in the major tier with a high-importance tag, and
        # both were being counted here as resolved: the first damped the chart
        # for an event that had not occurred, and the second would have done the
        # same two days before the approval it was anticipating. The two
        # detectors have to be mutually exclusive or the pending case silently
        # becomes the resolved one.
        text = " ".join(str(row.get(k) or "") for k in ("title", "summary"))
        if PENDING_MARKERS.search(text):
            continue
        kinds = [c.get("type") for c in (row.get("catalysts") or [])
                 if c.get("importance") == "high" and c.get("type")]
        if not kinds:
            continue
        hits.append({"title": row.get("title"), "tier": row.get("tier"),
                     "age_hours": age, "kinds": kinds,
                     "tone": row.get("tone"),
                     "sentiment": row.get("sentiment_score")})

    if not hits:
        return {"material": False}

    # Direction from the material headlines only. The overall net sentiment
    # averages them with background coverage, which is how a resolved binary
    # event ends up reading like a mildly positive week.
    tones = [h["sentiment"] for h in hits if h.get("sentiment") is not None]
    lean = sum(tones) / len(tones) if tones else 0.0
    kinds: List[str] = []
    for h in hits:
        for k in h["kinds"]:
            if k not in kinds:
                kinds.append(k)
    freshest = min(h["age_hours"] for h in hits)
    return {
        "material": True,
        "count": len(hits),
        "kinds": kinds,
        "lean": _num(lean, 2),
        "freshest_hours": _num(freshest, 1),
        "headline": sorted(hits, key=lambda h: h["age_hours"])[0]["title"],
        "window_hours": CATALYST_WINDOW_HOURS,
    }


# Language that puts a catalyst in the future rather than the past.
#
# Both halves are required: a forward marker AND a catalyst the taxonomy rates
# high. "Shares slip ahead of the open" carries the first and none of the
# second. The markers are the phrasings a wire actually uses for a scheduled
# binary: a PDUFA date, a scheduled vote, a decision expected in a window.
PENDING_MARKERS = re.compile(
    r"\bpdufa\b|\bdecision (?:date|expected|due)\b|\bexpected (?:in|by|on|this|next)\b"
    r"|\bscheduled (?:for|to)\b|\bset (?:for|to (?:vote|decide|rule))\b"
    r"|\bawait(?:s|ing)\b|\bto vote\b|\bvote on\b|\bdeadline\b|\bslated\b"
    r"|\bdue (?:in|on|by)\b|\bahead of\b|\bnears?\b|\bupcoming\b"
    r"|\bwill (?:decide|rule|vote)\b|\blooms?\b",
    re.I)

# A scheduled event can be announced weeks out, so this window is far wider than
# the three days a resolved catalyst gets. What matters for a resolved one is
# that the chart has not absorbed it yet; what matters here is only that the
# event is still ahead.
PENDING_WINDOW_HOURS = 24.0 * 30


def pending_catalyst(news: Dict[str, Any]) -> Dict[str, Any]:
    """A scheduled, unresolved binary ahead of this ticker.

    The opposite case to `material_catalyst`, and it needs the opposite
    treatment. A resolved catalyst makes the chart stale, so weight moves off
    the chart and onto the news. An unresolved one says nothing about direction
    at all: the market cannot know which way a vote or a decision goes, and a
    model that reads "FDA decision expected" as bullish is inventing the
    outcome. It is a reason to size down, which is the same instinct the
    earnings halving in `swing._news_score` already encodes.

    `about_company` is deliberately NOT required here. A CLARITY Act vote is not
    "about" any one crypto holding and is a real pending catalyst for all of
    them; the feed is already scoped to this ticker, so a policy story arriving
    in it is a story about this ticker's world. Company relevance is enforced by
    the feed rather than by the flag.
    """
    articles = (news or {}).get("articles") or []
    hits: List[Dict[str, Any]] = []
    for row in articles:
        age = row.get("age_hours")
        if age is None or age > PENDING_WINDOW_HOURS:
            continue
        text = " ".join(str(row.get(k) or "") for k in ("title", "summary"))
        if not PENDING_MARKERS.search(text):
            continue
        kinds = [c.get("type") for c in (row.get("catalysts") or [])
                 if c.get("importance") == "high" and c.get("type")]
        if not kinds:
            continue
        hits.append({"title": row.get("title"), "kinds": kinds,
                     "age_hours": age, "url": row.get("url")})
    if not hits:
        return {"pending": False}

    kinds: List[str] = []
    for h in hits:
        for k in h["kinds"]:
            if k not in kinds:
                kinds.append(k)
    newest = sorted(hits, key=lambda h: h["age_hours"])[0]
    return {
        "pending": True,
        "count": len(hits),
        "kinds": kinds,
        "headline": newest["title"],
        "url": newest.get("url"),
        # No date. The headline says an event is scheduled; it does not give a
        # parseable date, and inventing one would be the worst kind of precision.
        "dated": False,
        "window_hours": PENDING_WINDOW_HOURS,
    }


def _catalysts(text: str) -> List[Dict[str, str]]:
    lowered = text.lower()
    found: List[Dict[str, str]] = []
    seen = set()
    for pattern, label, importance in CATALYSTS:
        if re.search(pattern, lowered) and label not in seen:
            seen.add(label)
            found.append({"type": label, "importance": importance})
    return found


def classify(text: str) -> Dict[str, Any]:
    """Public seam over the lexicon and catalyst taxonomy.

    The daily brief classifies headlines that never came from a per-ticker news
    call, so it needs the tagging without the rest of `analyse`. Exposed as one
    function rather than letting another module import the private helpers, so
    there stays exactly one definition of what counts as a catalyst — a second
    taxonomy disagreeing with this one on the same headline across two tabs is a
    bug report waiting to happen.

    `tone` is the raw lexicon sum, unbounded and unnormalised: it is a rough
    signal for sorting and colour, not a score to display as a number.
    """
    tone, hits = _score_text(text)
    return {"tone": tone, "terms": hits[:6], "catalysts": _catalysts(text)}


def _age_hours(published: str) -> Optional[float]:
    if not published:
        return None
    try:
        stamp = datetime.fromisoformat(published.replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return round((datetime.now(timezone.utc) - stamp).total_seconds() / 3600.0, 1)


# Over-fetch, because the filter removes about half of a ticker feed and a
# page that asked for twelve should still get twelve where twelve exist.
OVERFETCH = 3


def analyse(provider, ticker: str, limit: int = 12) -> Dict[str, Any]:
    items = provider.news(ticker, limit=limit * OVERFETCH)
    earnings = provider.earnings_date(ticker)

    # For the relevance split. The quote is cached and /api/ticker has already
    # fetched it by the time this runs, so this is a cache hit on the path that
    # matters and one extra call on the standalone /api/news endpoint.
    # Degrades to symbol-only matching rather than failing: a missing name makes
    # the split coarser, not wrong.
    company_name = ""
    sector = industry = ""
    try:
        quote = provider.quote(ticker) or {}
        company_name = str(quote.get("name") or "")
        # For the context test. A headline that never names the company can
        # still be about its industry, and "Consumer Electronics" is a phrase
        # a headline plausibly contains where "Technology" is not.
        sector = str(quote.get("sector") or "")
        industry = str(quote.get("industry") or "")
    except Exception:
        company_name = ""

    scored: List[Dict[str, Any]] = []
    dropped: Dict[str, int] = {"filler": 0, "off-topic": 0}
    for item in items:
        blob = "{} {}".format(item.get("title", ""), item.get("summary", ""))
        score, hits = _score_text(blob)
        age = _age_hours(item.get("published", ""))

        if score >= 3:
            tone = "bullish"
        elif score <= -3:
            tone = "bearish"
        elif score > 0:
            tone = "mildly bullish"
        elif score < 0:
            tone = "mildly bearish"
        else:
            tone = "neutral"

        cats = _catalysts(blob)
        placed = tier_for(age, cats)
        about = mentions_company(blob, ticker, company_name)

        # Before the row is built, and before it reaches the sentiment
        # average. Filing an off-topic item under Market context still let it
        # vote on this company's tone; dropping it is what stops that.
        keep, why = keep_article(about, blob, cats, sector, industry)
        if not keep:
            dropped[why] += 1
            continue

        scored.append(
            {
                "title": item.get("title"),
                "summary": (item.get("summary") or "")[:400],
                "publisher": item.get("publisher"),
                "published": item.get("published"),
                "age_hours": age,
                "url": item.get("url"),
                "sentiment_score": round(score, 2),
                "tone": tone,
                "keywords": hits[:8],
                "catalysts": cats,
                "tier": placed["tier"],
                "tier_why": placed["why"],
                "age_words": _age_words(age),
                "about_company": about,
            }
        )

    # Relevance first, then tier, then the strongest catalyst, then age. The
    # feed's own order is the one thing not used: it is the publisher's, and it
    # put a week-old analyst note above an earnings miss.
    #
    # Relevance outranks tier deliberately. A fresh, high-catalyst headline
    # about a different company is still about a different company, and sorting
    # it first is how "RF Industries Q3 Earnings" reached the top of NVDA.
    scored.sort(key=lambda r: (
        0 if r["about_company"] else 1,
        TIER_ORDER.index(r["tier"]),
        -_importance_rank(r["catalysts"]),
        999999.0 if r["age_hours"] is None else r["age_hours"],
    ))

    # Trim before the sentiment average, not after.
    #
    # The over-fetch means more survives the filter than the page asks for, and
    # scoring over rows the reader cannot see would make `net_sentiment` a
    # claim about evidence that is not on screen. Ranked first, so what is
    # dropped here is the weakest tail rather than an arbitrary slice.
    surplus = max(0, len(scored) - limit)
    scored = scored[:limit]

    # Fresh news moves price; a week-old headline is already discounted.
    weighted = 0.0
    weight_total = 0.0
    for row in scored:
        age = row["age_hours"]
        weight = 1.0 if age is None else max(0.15, 1.0 / (1.0 + age / 36.0))
        weighted += row["sentiment_score"] * weight
        weight_total += weight

    net = round(weighted / weight_total, 2) if weight_total else 0.0
    if net >= 2:
        overall = "bullish"
    elif net >= 0.5:
        overall = "mildly bullish"
    elif net <= -2:
        overall = "bearish"
    elif net <= -0.5:
        overall = "mildly bearish"
    else:
        overall = "neutral"

    catalyst_counts: Dict[str, int] = {}
    for row in scored:
        for cat in row["catalysts"]:
            catalyst_counts[cat["type"]] = catalyst_counts.get(cat["type"], 0) + 1

    earnings_warning = None
    days_to_earnings = None
    if earnings:
        try:
            days_to_earnings = (datetime.fromisoformat(earnings).date() - datetime.now().date()).days
        except ValueError:
            days_to_earnings = None
        if days_to_earnings is not None and 0 <= days_to_earnings <= 21:
            when = (
                "today"
                if days_to_earnings == 0
                else "tomorrow"
                if days_to_earnings == 1
                else "in {} days".format(days_to_earnings)
            )
            earnings_warning = (
                "Earnings on {} — {}. IV will stay bid into the print and collapse after it; "
                "long premium held through earnings usually loses even when the direction is right.".format(
                    earnings, when
                )
            )

    removed = dropped["filler"] + dropped["off-topic"]
    return {
        "method": "Lexicon sentiment and regex catalyst tagging over the "
                  "headline feed, recency-weighted. Ranked by tier, then "
                  "catalyst, then age",
        "overall_tone": overall,
        "net_sentiment": net,
        "article_count": len(scored),
        # Published rather than described in the client's own copy, so the tier
        # a reader sees and the rule it claims come from one place.
        "tiers": TIERS,
        "tier_counts": {t: sum(1 for r in scored if r["tier"] == t)
                        for t in TIER_ORDER},
        "about_count": sum(1 for r in scored if r["about_company"]),
        "context_count": sum(1 for r in scored if not r["about_company"]),
        # What the filter took out, so the panel can say so rather than just
        # looking short. `filler` is personal-finance syndication; `off_topic`
        # is a headline about some other company with nothing market-wide in
        # it. `surplus` is the tail past the requested limit and is not a
        # judgement about the items.
        "dropped": {"filler": dropped["filler"],
                    "off_topic": dropped["off-topic"],
                    "total": removed,
                    "surplus": surplus},
        "matched_on": _match_terms(ticker, company_name),
        "earnings_date": earnings,
        "days_to_earnings": days_to_earnings,
        "earnings_warning": earnings_warning,
        "catalyst_summary": sorted(
            [{"type": k, "mentions": v} for k, v in catalyst_counts.items()],
            key=lambda r: -r["mentions"],
        ),
        "articles": scored,
    }


def rank_wire(entries: List[Dict[str, Any]], limit: int = 3) -> List[Dict[str, Any]]:
    """The market's own top stories, ranked by what they are about.

    The daily brief orders its desks by a per-source `weight`, which is an
    editorial judgement about outlets rather than about stories. Measured on the
    live wire, that put "Novo CEO tells CNBC why drugmaker is rebranding" at the
    top of the Markets desk and left "Core CPI Upside Surprise and FOMC Odds"
    fourth, because CNBC outweighs Econbrowser. For a homepage slot whose whole
    job is what is moving markets, the catalyst matters more than the masthead.

    So this reuses the tiering the headline panel uses. One rule, two surfaces:
    a macro event ranks above a rebranding on both, and if the taxonomy is ever
    wrong it is wrong in one place.

    No relevance split here, deliberately. That test asks whether an item names
    a particular company, and this feed is not about one: everything on it is
    market context, which is exactly what the slot is for.
    """
    ranked: List[Dict[str, Any]] = []
    for entry in entries or []:
        blob = "{} {}".format(entry.get("title", ""), entry.get("summary", ""))
        cats = _catalysts(blob)
        age = _age_hours(entry.get("published", ""))
        placed = tier_for(age, cats)
        row = dict(entry)
        row.update({
            "tier": placed["tier"],
            "tier_why": placed["why"],
            "age_words": _age_words(age),
            "age_hours": age,
            "catalysts": cats,
        })
        ranked.append(row)

    ranked.sort(key=lambda r: (
        TIER_ORDER.index(r["tier"]),
        -_importance_rank(r["catalysts"]),
        999999.0 if r["age_hours"] is None else r["age_hours"],
    ))
    return ranked[:limit] if limit else ranked
