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
    r"what (should|do|can|would) (i|we|you) expect|expect(ations)? (from|for|into) .{0,20}(earnings|report|results|quarter)|"
    r"before (the |its )?(earnings|report|results|print)|pre[- ]?earnings|what to expect|preview|"
    r"will (they|it) (beat|miss)|(upcoming|next) (earnings|report|quarter|print)|expected move|"
    r"earnings (next week|this week|on|date))\b", re.I)
_COMBINED = re.compile(
    r"\b(full picture|big picture|overall|everything|all angles|complete (analysis|picture|view)|"
    r"(trade|trading) (and|or) (invest|hold)\w*|(invest|hold)\w* (and|or) (trade|swing)\w*|"
    r"short[- ]term and long[- ]term|long[- ]term and short[- ]term|both (the )?(trade|swing|long)|"
    r"every angle|whole thing|full analysis|full report|"
    # Two horizons named together, or asked to be reconciled: "why do the
    # long-term and swing reads disagree on Alphabet" routed to long term only,
    # so Milo could not see the swing read it was asked to explain (found by
    # the Milo eval session, 2026-10-15).
    r"(long[- ]term|invest\w*|hold\w*) (and|vs\.?|versus|or) (the |a |an )?(swing|trade|trading|short[- ]term)|"
    r"(swing|trade|trading|short[- ]term) (and|vs\.?|versus|or) (the |a |an )?(long[- ]term|invest\w*|hold\w*)|"
    r"(disagree|conflict|contradict)\w*|(reads|views|grades|signals) (don'?t|do not) (agree|match))\b", re.I)
# A take on the stock, the owner's reference shape (2026-10-15): "Thoughts on HOOD in the near/long
# term?" routed to long term only, so the near-term half had no swing read behind it. Both timeframes
# named together in any wording, or a request for your take with none named, get both assessments.
_BOTH_HORIZONS = re.compile(
    r"\b(near|short)(?:[- ]?term)?\b.{0,40}\blong[- ]?term\b|\blong[- ]?term\b.{0,40}\b(near|short)[- ]?term\b|"
    r"\bnext (?:few|couple of) (?:weeks|days)\b.{0,60}\b(?:for years|long[- ]?term|long run)\b", re.I)
_TAKE = re.compile(r"\b(thoughts? (?:on|about)|(?:your )?take on|what do you (?:think|make) of|your view on|"
                   r"opinion on|how do you feel about)\b", re.I)
# A request for a definition is about the term, not the company on screen:
# "What's a dividend yield?" with KO open pulled KO's whole long-term
# assessment. Not a definition when it asks for a judgement or a level.
_DEFINE = re.compile(r"^\s*(what(?:'s| is| are) (?:a|an)\b|what does .{1,40}\bmean\b|define\b|definition of|"
                     r"meaning of|explain what (?:a|an)\b)", re.I)
_NOT_DEFINE = re.compile(r"\b(good|best|reasonable|fair|sensible|right|safe|smart|stop|entry|target|setup|"
                         r"trade|level|this|here|now|today|their|its)\b", re.I)
# "Quick" is for a narrow ask about one figure or level ("where's the stop",
# "what's the consensus"). A judgement ("is it a good investment", "is there a
# setup", "how did earnings go") is a full read even when it is short: the
# first capture (2026-10-14) marked four of seven judgement questions quick,
# which would have answered "is NVDA a good long-term investment" in three
# sentences.
_NARROW = re.compile(r"^\s*(what'?s|what is|what are|where'?s|where is|where are|when'?s|when is|which|how much|"
                     r"how many|how far)\b.{0,60}\b(stop|target|entry|level|levels|support|resistance|date|price|"
                     r"ratio|grade|score|eps|consensus|estimate|move|invalidation|atr|rsi|yield|multiple|p/?e)\b", re.I)
_JUDGE = re.compile(r"\b(should|good|worth|expect|think|go|went|is there|any (?:good )?(?:setup|trade)|buy|sell|"
                    r"invest\w*|why|analy[sz]\w*|picture|case|view|outlook|opinion|thoughts?)\b", re.I)
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
    depth = "quick" if (_NARROW.search(q) and not _JUDGE.search(q) and words <= 20) else "full"
    nxt, last = _days(next_report, today), _days(last_report, today)
    timing = {"next_report": next_report, "days_to_next": nxt, "last_report": last_report,
              "days_since_last": -last if last is not None else None}
    if explicit in MODES:
        return {"mode": explicit, "source": "chosen", "depth": "full", "why": "Chosen on the page.",
                "timing": timing}
    if not ticker:
        return {"mode": None, "source": "none", "depth": depth, "why": "No single company in the question.",
                "timing": timing}
    if _DEFINE.search(q) and not _NOT_DEFINE.search(q):
        return {"mode": None, "source": "definition", "depth": "quick",
                "why": "A question about what a term means, not about this company.", "timing": timing}
    # A take with no timeframe named goes to both assessments only when the reader has not saved one:
    # "thoughts on NVDA?" from a reader whose timeframe is swing is a swing question.
    take_open = (_TAKE.search(q) and not horizon_mod.stated_in(q)
                 and horizon_mod.normalise(saved_horizon) == horizon_mod.DEFAULT)
    if _COMBINED.search(q) or _BOTH_HORIZONS.search(q) or take_open:
        return {"mode": "combined", "source": "question", "depth": "full",
                "why": "The question asks for more than one horizon, or why they differ.", "timing": timing}
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
    # A question about the options themselves: "options are cheap" read as valuation and sent the
    # long-term assessment, "if I buy a call" read as buy-or-sell (Milo eval, 2026-10-15). A stated
    # horizon or a coming report still decides first.
    if intent == "options":
        return {"mode": None, "source": "options", "depth": depth,
                "why": "A question about the options, not the company: the framework assesses the stock.",
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
