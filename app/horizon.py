"""The reader's horizon: what timeframe Milo answers for.

A second axis beside the knowledge level (app/knowledge.py). The level says how
much the reader already knows and changes the wording; the horizon says what
the reader is deciding about and changes which evidence matters. "Is AAPL a
buy?" has a different honest answer for somebody trading the open tomorrow and
for somebody holding for ten years, and the 2026-10-12 audit found Milo had no
way to know which it was being asked: the system prompt assumed "a
self-directed trader" for everybody.

**Stated beats saved beats nothing.** Words in the question ("for the next two
weeks", "hold for years", "at the open") decide the horizon for that answer
only. Otherwise the reader's saved choice applies. With neither, no horizon
block is sent and the base prompt tells Milo to state its assumption, or ask
one short question when the answer genuinely turns on it. One question never
reclassifies the reader: nothing here is written back to their preference.

**The data never changes, only the emphasis.** Same rule as the levels and the
personas: a horizon decides which figures lead, never what they are, and every
caveat survives every horizon.
"""

from __future__ import annotations

import re
from typing import Dict, Optional, Tuple

DEFAULT = "auto"

HORIZONS: Dict[str, Dict[str, str]] = {
    "auto": {
        "label": "Auto",
        "blurb": "Milo reads the timeframe from your question and says what it assumed.",
        "prompt": "",
    },
    "day": {
        "label": "Day trading",
        "blurb": "Today's session: levels, volume, volatility, liquidity and catalysts.",
        "prompt": (
            "## Horizon: intraday\n"
            "The reader is thinking about today's session or the next open. Lead with the "
            "session (the session line in CONTEXT says which one is open now) and whether "
            "the prices you have are live, delayed, or from the last close. Then the "
            "intraday structure CONTEXT actually has: the prior close and day range, "
            "pivots and the nearest computed support and resistance, relative volume, the "
            "daily range (ATR) or implied move, and any catalyst due today. Liquidity "
            "matters at this horizon: say when volume, open interest or a wide spread "
            "would change the economics. Quotes here are delayed and you cannot watch "
            "the tape, so frame everything as conditions the reader can check (\"if it "
            "opens above X and holds, ...; a move back under Y ...\"), never as a plan to "
            "execute. If the data is from a closed session, say so in the first line."
        ),
    },
    "swing": {
        "label": "Swing",
        "blurb": "Days to weeks: trend, levels, momentum, events and invalidation.",
        "prompt": (
            "## Horizon: days to a few weeks\n"
            "The reader is weighing a hold of days to weeks. Lead with the multi-day "
            "trend (the averages and the stage), the support and resistance CONTEXT "
            "computed, and momentum. Name every scheduled event inside the window "
            "(earnings, macro releases, ex-dividend, expiry) with its date, because a "
            "hold through a report carries overnight gap risk that no level protects "
            "against. Close with the condition that would invalidate the read, stated "
            "as a level or an event, not as an instruction."
        ),
    },
    "long": {
        "label": "Long term",
        "blurb": "Years: business quality, valuation, competitive position.",
        "prompt": (
            "## Horizon: years\n"
            "The reader is thinking about owning the business for years. Lead with what "
            "the business does and how well (growth, margins, cash and debt), then what "
            "the price already assumes: the valuation against the company's own history "
            "and the market, from CONTEXT. Keep those two apart and say which one the "
            "answer turns on: a strong business can be an expensive stock. Competitive "
            "position and capital allocation (buybacks, dividends, acquisitions, debt) "
            "only from CONTEXT or cited sources; say when the data does not cover them. "
            "Short-term technicals and options positioning are background at this "
            "horizon: mention them in a clause if at all. Never project a return."
        ),
    },
}

ORDER = ["auto", "day", "swing", "long"]

# Words that state a horizon. Kept narrow on purpose: a match decides one
# answer's emphasis, so a false positive costs more than a miss (a miss leaves
# Milo to read the question itself, which it does well).
_STATED = [
    ("day", re.compile(
        r"\b(?:day[- ]?trad\w*|intra-?day|scalp\w*|0 ?dte|at the (?:open|bell)|"
        r"(?:this|tomorrow) morning|by the close|into the close|pre-?market|"
        r"after[- ]hours|today'?s (?:open|close|session))\b", re.I)),
    ("long", re.compile(
        r"\b(?:long[- ]term|for (?:many |the next |\d+ )?(?:years|decades?)|\d+\+? ?years?|"
        r"a decade|retire\w*|buy[- ]and[- ]hold|hold(?:ing)? (?:it |this |them )?for years|"
        r"compound\w*|roth|ira|401\(?k\)?)\b", re.I)),
    ("swing", re.compile(
        r"\b(?:swing\w*|multi-?day|(?:next|coming) (?:few|couple of|\d+(?:-\d+)?|two|three) "
        r"(?:days|weeks)|this week|next week|few weeks|\d+(?:-\d+)? weeks?|"
        r"over the next (?:month|week)s?)\b", re.I)),
]


def normalise(value: Optional[str]) -> str:
    key = str(value or "").strip().lower()
    return key if key in HORIZONS else DEFAULT


def stated_in(question: str) -> Optional[str]:
    """The horizon the question itself names, or None."""
    text = question or ""
    for key, pattern in _STATED:
        if pattern.search(text):
            return key
    return None


def resolve(saved: Optional[str], question: str) -> Tuple[str, str]:
    """(horizon, why) for one answer. `why` is 'question', 'saved' or 'none'."""
    stated = stated_in(question)
    if stated:
        return stated, "question"
    pref = normalise(saved)
    if pref != DEFAULT:
        return pref, "saved"
    return DEFAULT, "none"


def prompt_for(horizon: str, why: str) -> str:
    """The system block for this answer's horizon, or "" for none."""
    block = HORIZONS[normalise(horizon)]["prompt"]
    if not block:
        return ""
    if why == "question":
        block += ("\nThe question named this timeframe. It decides this answer only: the "
                  "reader has not told you it is how they always invest.")
    else:
        block += ("\nThis is the reader's saved preference. If the question plainly asks "
                  "about a different timeframe, answer that one instead.")
    return block


def catalogue() -> Dict[str, object]:
    return {
        "default": DEFAULT,
        "horizons": [{"id": k, "label": HORIZONS[k]["label"], "blurb": HORIZONS[k]["blurb"]}
                     for k in ORDER],
        "changes": ["Which evidence Milo leads with: today's session, the next few weeks, "
                    "or the business over years."],
        "never_changes": ["The figures and the risks. Every horizon reads the same data "
                          "and states the same limits."],
    }
