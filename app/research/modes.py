"""Which analysis a question calls for, from its words and the verified
release timing.

Five modes: long_term, swing, pre_earnings, post_earnings, combined. The
question decides first; for an earnings question the calendar decides between
before and after, because "how are earnings looking for JPM" means the report
that just came out on the day after it and the next one a month later.

A short question is answered short (`depth` = "quick"): asking what the stop
is does not need a full report. When the question names no timeframe and the
answer genuinely depends on it, the mode is "unclear" and Milo's existing
timeframe rule applies (state the assumption, or ask one short question).

Built on top of the research pack's intent (`app/desk/research.py`) and the
horizon words (`app/horizon.py`), so the three cannot drift apart: this only
adds what those lack, the post-earnings and combined cases and the timing.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict, Optional

from .. import horizon as horizon_mod
from ..desk import research as desk_research

MODES = ("long_term", "swing", "pre_earnings", "post_earnings", "combined")

_POST = re.compile(
    r"\b(how did .{0,25}\b(earnings|results|report|quarter|print) (go|land|come in)|"
    r"after (the |its )?(earnings|report|results|print)|post[- ]?earnings|reaction to (the |its )?"
    r"(earnings|results|report|print)|(just|already) reported|reported (last night|yesterday|this morning|today)|"
    r"(beat|missed) (on )?(earnings|estimates|revenue)|why (is|did|was) .{0,40}\b(up|down|drop\w*|fall\w*|fell|"
    r"jump\w*|ris\w*|rose|gap\w*|soar\w*|tank\w*|sink\w*|sank).{0,30}\b(earnings|results|report|quarter|print)|"
    r"(earnings|results|report|print) (yesterday|last night|this morning|today)|the quarter they just)\b", re.I)
_PRE = re.compile(
    r"\b(ahead of (the )?(earnings|report|results|print)|into (the )?(earnings|report|print)|"
    r"before (the |its )?(earnings|report|results|print)|pre[- ]?earnings|what to expect|preview|"
    r"will (they|it) (beat|miss)|(upcoming|next) (earnings|report|quarter|print)|expected move|"
    r"earnings (next week|this week|on|date))\b", re.I)
_COMBINED = re.compile(
    r"\b(full picture|big picture|overall|everything|all angles|complete (analysis|picture|view)|"
    r"(trade|trading) (and|or) (invest|hold)\w*|(invest|hold)\w* (and|or) (trade|swing)\w*|"
    r"short[- ]term and long[- ]term|long[- ]term and short[- ]term|both (the )?(trade|swing|long)|"
    r"every angle|whole thing|full analysis|full report)\b", re.I)
_FULL = re.compile(r"\b(analy[sz]\w*|breakdown|report|deep|full|thorough|walk me through|in depth|detailed|"
                   r"comprehensive|case for|bull case|bear case)\b", re.I)
_LONG_EXPLICIT = re.compile(r"\b(long[- ]term|for years|invest(ing|ment|or)?|retire\w*|own (it|the stock|shares)|"
                            r"moat|business quality|valuation|undervalued|overvalued|intrinsic)\b", re.I)
_AMBIG = re.compile(r"\b(buy|sell|good (stock|investment|entry)|worth (it|buying)|should i)\b", re.I)


def _days(d: Optional[str], today: date) -> Optional[int]:
    try:
        return (date.fromisoformat(str(d)[:10]) - today).days
    except (TypeError, ValueError):
        return None


def resolve(question: str, ticker: Optional[str], *, next_report: Optional[str] = None,
            last_report: Optional[str] = None, saved_horizon: Optional[str] = None,
            explicit: Optional[str] = None, today: Optional[date] = None,
            pre_window: int = 21, post_window: int = 10) -> Dict[str, Any]:
    """{mode, source, depth, why, timing} for one question."""
    today = today or date.today()
    q = question or ""
    words = len(q.split())
    depth = "full" if (_FULL.search(q) or words > 28) else "quick"
    nxt, last = _days(next_report, today), _days(last_report, today)
    timing = {"next_report": next_report, "days_to_next": nxt, "last_report": last_report,
              "days_since_last": -last if last is not None else None}
    if explicit in MODES:
        return {"mode": explicit, "source": "chosen", "depth": "full", "why": "Chosen on the page.",
                "timing": timing}
    if not ticker:
        return {"mode": None, "source": "none", "depth": depth, "why": "No single company in the question.",
                "timing": timing}
    if _COMBINED.search(q):
        return {"mode": "combined", "source": "question", "depth": "full",
                "why": "The question asks for more than one horizon.", "timing": timing}
    stated = horizon_mod.stated_in(q)
    intent = desk_research.intent(q, horizon=None, ticker=ticker)
    if _POST.search(q):
        return {"mode": "post_earnings", "source": "question", "depth": depth,
                "why": "The question is about a release that has happened.", "timing": timing}
    if _PRE.search(q):
        return {"mode": "pre_earnings", "source": "question", "depth": depth,
                "why": "The question is about a coming release.", "timing": timing}
    if intent == "pre_earnings":
        # An earnings question without tense: the calendar decides.
        recent = timing["days_since_last"] is not None and 0 <= timing["days_since_last"] <= post_window
        soon = nxt is not None and 0 <= nxt <= pre_window
        if recent and (not soon or timing["days_since_last"] <= (nxt or 99)):
            return {"mode": "post_earnings", "source": "timing", "depth": depth,
                    "why": "Results came out {} days ago.".format(timing["days_since_last"]), "timing": timing}
        if soon or nxt is not None:
            return {"mode": "pre_earnings", "source": "timing", "depth": depth,
                    "why": "The next release is {} days away.".format(nxt) if nxt is not None else
                           "An earnings question with no recent release.", "timing": timing}
        if recent or last is not None:
            return {"mode": "post_earnings", "source": "timing", "depth": depth,
                    "why": "No upcoming date in the feed; the last release is the one on record.", "timing": timing}
        return {"mode": "pre_earnings", "source": "timing", "depth": depth,
                "why": "An earnings question, but no release date is in the feed.", "timing": timing}
    if stated == "long" or _LONG_EXPLICIT.search(q):
        return {"mode": "long_term", "source": "question", "depth": depth,
                "why": "The question is about owning the business.", "timing": timing}
    if stated in ("swing", "day") or intent in ("swing", "day_trade"):
        return {"mode": "swing", "source": "question", "depth": depth,
                "why": "The question is about a trade over days to weeks." if stated != "day" else
                       "An intraday question: the swing framework's levels apply, at a shorter horizon.",
                "timing": timing}
    # The research pack falls back to "long_term" for any company question, so
    # its intent counts here only when one of its long-term words matched.
    if desk_research._LONG.search(q) and not _AMBIG.search(q):
        return {"mode": "long_term", "source": "question", "depth": depth,
                "why": "The question is about the business.", "timing": timing}
    hz = horizon_mod.normalise(saved_horizon)
    if hz == "long":
        return {"mode": "long_term", "source": "saved", "depth": depth, "why": "The reader's saved timeframe.",
                "timing": timing}
    if hz in ("swing", "day"):
        return {"mode": "swing", "source": "saved", "depth": depth, "why": "The reader's saved timeframe.",
                "timing": timing}
    if _AMBIG.search(q):
        return {"mode": "unclear", "source": "none", "depth": depth,
                "why": "A buy-or-sell question with no timeframe: the answer differs for a trade and an "
                       "investment.", "timing": timing}
    return {"mode": None, "source": "none", "depth": depth,
            "why": "The question does not call for one of the framework's analyses.", "timing": timing}
