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
    (r"\bfed\b|\brate (?:cut|hike|decision)\b|\bcpi\b|\binflation\b|\bfomc\b", "macro event", "high"),
]


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
                "catalysts": _catalysts(blob),
            }
        )

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
        "method": "Lexicon sentiment + regex catalyst tagging over the headline feed, recency-weighted",
        "overall_tone": overall,
        "net_sentiment": net,
        "article_count": len(scored),
        "earnings_date": earnings,
        "days_to_earnings": days_to_earnings,
        "earnings_warning": earnings_warning,
        "catalyst_summary": sorted(
            [{"type": k, "mentions": v} for k, v in catalyst_counts.items()],
            key=lambda r: -r["mentions"],
        ),
        "articles": scored,
    }
