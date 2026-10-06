"""A request in words, read as the screener's own filters.

Asked for with another terminal's scanner box ("Describe what you're looking
for"): "add this in the discover -> scan tab for users to look for stocks based
on their requests", with two buttons, one to find the symbols at once and one
to hand the request to the assistant. The example given was "Strong Stocks on
the 200 SMA line right now", which that terminal answered with GOOGL.

**The screener does the finding; this only reads.** A request becomes bounds
and states from `app/analytics/screener.py`'s published vocabulary, and the
screener runs them over the ranking it already shares with the named scans.
Nothing here invents a field: a part of the request the vocabulary cannot
express (an RSI level, a sector, a P/E) is reported as unread, never screened
on something else in its place.

**Read here first, and by Pulse only for what this cannot read.** Most requests
are a handful of phrasings ("near the 200-day", "52-week highs", "under $20",
"high volume"), and reading those costs nothing. A request with words left over
goes to the assistant when the reader is allowed it (see /api/screener/ask),
and what it reads is kept, so the same request is never paid for twice.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Tuple

# "On" or "near" an average, as a band either side of it in percent. Three is
# where a daily close stops being a touch and starts being a trend away.
NEAR_PCT = 3.0

# A length and at least one word saying it is an average: "the 200" alone could
# as well be a price, and "under 200" read as the 200-day would be a misreading.
_MA = (r"(20|50|200)[\s-]*(?:(?:days?|d|dma|sma|ema|ma|period|simple|exponential|"
       r"moving[\s-]*average|average|line|mark)\b[\s-]*)+")
_THE = r"(?:the\s+|its\s+|their\s+|a\s+)?"

# Words that carry no condition: what is left of a request once these and the
# phrases below are taken out is what this could not read.
STOPWORDS = set("""
a an and any are as at be been best by can do find for from get give good great has have
i in into is it its just like list look looking me my names now of on or please right
show some still stock stocks that the their them these this those to today top trading
want were what which who whose with currently companies shares equities tickers symbols
ones one ideas candidates setups setup screen scan us also only very really quite line
""".split())

def _near(n: str) -> List[Dict[str, Any]]:
    return [{"field": "pct_from_sma" + n, "min": -NEAR_PCT, "max": NEAR_PCT}]


def _rules() -> List[Tuple[re.Pattern, Any]]:
    """Each entry is a compiled pattern and a function of its match giving
    (filters, states, label, sort), tried in this order. A pattern consumes the
    words it matched, so the longer phrases come first: "strong volume" is
    volume, and only a "strong" left over is a trend."""
    out: List[Tuple[re.Pattern, Any]] = []

    def add(pattern: str, make) -> None:
        out.append((re.compile(pattern, re.I), make))

    # Near, on, testing or holding a moving average.
    add(r"\b(?:on|at|near|around|touching|testing|hugging|holding|retesting|sitting\s+on|"
        r"right\s+on|close\s+to|bouncing\s+off|bouncing\s+on)\s+" + _THE + _MA,
        lambda m: (_near(m.group(1)), [],
                   "Within {:g}% of the {}-day average".format(NEAR_PCT, m.group(1)), None))
    # Above or below one.
    add(r"\b(above|over|below|under|beneath)\s+" + _THE + _MA,
        lambda m: _side(m.group(1).lower(), m.group(2)))
    add(r"\bgolden\s+cross(?:es|ed)?\b",
        lambda m: ([], ["golden"], "50-day average above the 200-day", None))
    add(r"\b(?:high\s+momentum|momentum|outperform(?:ers|ing)?|ripping|running|"
        r"big\s+winners?|top\s+performers?)\b",
        lambda m: ([{"field": "roc60", "min": 10.0, "max": None}], [],
                   "Up 10% or more over three months", ("roc60", "desc")))
    # The 52-week range.
    add(r"\b(?:(?:new|near|at|making|hitting)\s+)?(?:52[\s-]*week|yearly|year|all[\s-]*time)\s+highs?\b"
        r"|\bnew\s+highs?\b|\bnear\s+(?:their|its|the)?\s*highs?\b",
        lambda m: ([{"field": "range_position", "min": 90.0, "max": None}], [],
                   "In the top tenth of the 52-week range", ("range_position", "desc")))
    add(r"\b(?:(?:new|near|at|making|hitting)\s+)?(?:52[\s-]*week|yearly|year)\s+lows?\b"
        r"|\bnew\s+lows?\b|\bnear\s+(?:their|its|the)?\s*lows?\b",
        lambda m: ([{"field": "range_position", "min": None, "max": 10.0}], [],
                   "In the bottom tenth of the 52-week range", ("range_position", "asc")))
    add(r"\bbreak(?:ing)?[\s-]*outs?\b",
        lambda m: ([{"field": "range_position", "min": 95.0, "max": None},
                    {"field": "volume_expansion", "min": 1.2, "max": None}], [],
                   "Breaking out: at the top of the 52-week range on rising volume",
                   ("range_position", "desc")))
    add(r"\b(?:pull(?:ing)?[\s-]*backs?|dips?|dipping|dipped|pulled\s+back)\b",
        lambda m: ([{"field": "pct_from_sma20", "min": None, "max": 0.0}], ["golden"],
                   "Pulling back: under the 20-day inside an uptrend", ("pct_from_sma20", "asc")))
    # Volume and volatility.
    add(r"\b(?:high|heavy|rising|unusual|big|strong|expanding)\s+volume\b|\bvolume\s+(?:surge|spike|"
        r"expansion|increase)s?\b",
        lambda m: ([{"field": "volume_expansion", "min": 1.3, "max": None}], [],
                   "Volume 30% or more above its three-month average",
                   ("volume_expansion", "desc")))
    add(r"\b(?:low|quiet|calm)\s+(?:volatility|vol)\b|\b(?:calm|quiet|stable|steady)\b",
        lambda m: ([{"field": "atr_pct", "min": None, "max": 2.0}], [],
                   "A daily range of 2% or less", ("atr_pct", "asc")))
    add(r"\b(?:high\s+(?:volatility|vol)|volatile|big\s+movers?|wild)\b",
        lambda m: ([{"field": "atr_pct", "min": 4.0, "max": None}], [],
                   "A daily range of 4% or more", ("atr_pct", "desc")))
    add(r"\b(?:most\s+)?(?:liquid|heavily\s+traded|most\s+traded)\b",
        lambda m: ([], [], "Most traded first", ("dollar_volume", "desc")))
    # Strength and weakness, as trend structure: the 50-day above the 200-day,
    # or the price under the 200-day and lower than three months ago.
    add(r"\b(?:strong(?:est)?|leaders?|leading|uptrends?|up[\s-]?trending|trending\s+up|"
        r"bullish|healthy)\b",
        lambda m: ([], ["golden"], "In an uptrend: the 50-day above the 200-day", None))
    add(r"\b(?:weak(?:est)?|laggards?|lagging|downtrends?|down[\s-]?trending|trending\s+down|"
        r"bearish|broken)\b",
        lambda m: ([{"field": "pct_from_sma200", "min": None, "max": 0.0},
                    {"field": "roc60", "min": None, "max": 0.0}], [],
                   "In a downtrend: under the 200-day and lower than three months ago",
                   ("roc60", "asc")))
    # Price, which needs a dollar sign or the word, so "under 200 day" is not a price.
    # And not an amount with a size after it: "market cap over $10B" read as a
    # share price over $10. There is no market-cap field, so that request is
    # left unread and the reply says so.
    add(r"\b(?:under|below|less\s+than|cheaper\s+than)\s+\$\s*(\d+(?:\.\d+)?)" + _NOT_AN_AMOUNT +
        r"|\b(?:under|below|less\s+than)\s+(\d+(?:\.\d+)?)\s*(?:dollars|bucks)\b",
        lambda m: ([{"field": "price", "min": None, "max": float(m.group(1) or m.group(2))}], [],
                   "Priced under ${:g}".format(float(m.group(1) or m.group(2))), None))
    add(r"\b(?:over|above|more\s+than)\s+\$\s*(\d+(?:\.\d+)?)" + _NOT_AN_AMOUNT +
        r"|\b(?:over|above|more\s+than)\s+(\d+(?:\.\d+)?)\s*(?:dollars|bucks)\b",
        lambda m: ([{"field": "price", "min": float(m.group(1) or m.group(2)), "max": None}], [],
                   "Priced over ${:g}".format(float(m.group(1) or m.group(2))), None))
    # Returns over a stated span.
    add(r"\b(up|down|gained|lost|rallied|fallen|fell|dropped)\s+(?:more\s+than\s+|over\s+|at\s+least\s+)?"
        r"(\d+(?:\.\d+)?)\s*%\s*(?:(?:this|in\s+(?:the\s+)?(?:last|past)|over\s+(?:the\s+)?(?:last|past)|"
        r"in\s+a)\s+)?(month|3\s+months|three\s+months|quarter)\b",
        lambda m: _returns(m.group(1).lower(), float(m.group(2)), m.group(3).lower()))
    return out


# After a dollar figure: a size word or letter makes it an amount ($10B, $500
# million), not a share price.
_NOT_AN_AMOUNT = r"(?!\d|\.\d|\s*(?:[kmbt]\b|bn\b|mm\b|thousand|million|billion|trillion))"


def _side(word: str, n: str):
    above = word in ("above", "over")
    if n == "200" and above:
        return [], ["above_sma200"], "Above its 200-day average", None
    if n == "50" and above:
        return [], ["above_sma50"], "Above its 50-day average", None
    field = "pct_from_sma" + n
    if above:
        return [{"field": field, "min": 0.0, "max": None}], [], \
            "Above its {}-day average".format(n), None
    return [{"field": field, "min": None, "max": 0.0}], [], \
        "Below its {}-day average".format(n), None


def _returns(word: str, pct: float, span: str):
    field = "roc20" if span == "month" else "roc60"
    named = "a month" if field == "roc20" else "three months"
    if word in ("up", "gained", "rallied"):
        return [{"field": field, "min": pct, "max": None}], [], \
            "Up {:g}% or more over {}".format(pct, named), (field, "desc")
    return [{"field": field, "min": None, "max": -pct}], [], \
        "Down {:g}% or more over {}".format(pct, named), (field, "asc")


_RULES = _rules()

def labels(filters: List[Dict[str, Any]], states: List[str]) -> List[str]:
    """A reading in words, from the screener's own labels: what the assistant
    read is shown the same way as what was read here."""
    from . import screener
    out: List[str] = []
    for f in filters or []:
        field = screener.FIELD_BY_ID.get(f.get("field"))
        if not field:
            continue
        unit = field.get("unit") or ""

        def show(v: Any) -> str:
            n = "{:,.{}f}".format(float(v), 0 if float(v).is_integer() else 2)
            return "$" + n if unit == "$" else n + ("%" if unit == "%" else "x" if unit == "x" else "")
        lo, hi = f.get("min"), f.get("max")
        if lo is not None and hi is not None:
            out.append("{} from {} to {}".format(field["label"], show(lo), show(hi)))
        elif lo is not None:
            out.append("{} at least {}".format(field["label"], show(lo)))
        elif hi is not None:
            out.append("{} at most {}".format(field["label"], show(hi)))
    for key in states or []:
        state = screener.STATE_BY_ID.get(key)
        if state:
            out.append(state["label"])
    return out


def cache_key(text: str) -> str:
    """The same request in different case or spacing is the same request."""
    norm = re.sub(r"\s+", " ", (text or "").strip().lower())
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()


def read(text: str) -> Dict[str, Any]:
    """The request as filters, states and a sort, with what was not read.

    `leftover` is the words no rule took and that carry meaning, in the order
    they were written; empty means the whole request was read here."""
    remaining = " " + (text or "") + " "
    filters: List[Dict[str, Any]] = []
    states: List[str] = []
    understood: List[str] = []
    sort: Tuple[str, str] = ("score", "desc")
    sorted_by_rule = False
    for pattern, make in _RULES:
        while True:
            m = pattern.search(remaining)
            if not m:
                break
            got_filters, got_states, label, got_sort = make(m)
            for f in got_filters:
                # One bound per field: a later rule narrows, it does not stack.
                filters = [x for x in filters if x["field"] != f["field"]] + [dict(f)]
            for s in got_states:
                if s not in states:
                    states.append(s)
            if label and label not in understood:
                understood.append(label)
            if got_sort and not sorted_by_rule:
                sort, sorted_by_rule = got_sort, True
            remaining = remaining[:m.start()] + " " + remaining[m.end():]
    # "/" kept inside a word, so "P/E" is one word the reply can say it did
    # not read, rather than "p" and "e", each too short to be listed.
    words = re.findall(r"[a-z0-9$%][a-z0-9$%'./-]*", remaining.lower())
    leftover = [w for w in words if w.strip(".-'") not in STOPWORDS and len(w.strip(".-'")) > 1]
    return {"filters": filters, "states": states, "sort": sort[0], "direction": sort[1],
            "understood": understood, "leftover": leftover}
