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


def analyse(provider, ticker: str, limit: int = 12) -> Dict[str, Any]:
    items = provider.news(ticker, limit=limit)
    earnings = provider.earnings_date(ticker)

    # For the relevance split. The quote is cached and /api/ticker has already
    # fetched it by the time this runs, so this is a cache hit on the path that
    # matters and one extra call on the standalone /api/news endpoint.
    # Degrades to symbol-only matching rather than failing: a missing name makes
    # the split coarser, not wrong.
    company_name = ""
    try:
        company_name = str((provider.quote(ticker) or {}).get("name") or "")
    except Exception:
        company_name = ""

    scored: List[Dict[str, Any]] = []
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
