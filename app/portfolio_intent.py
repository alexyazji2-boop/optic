"""Whether a question to Milo is about the reader's own linked portfolio.

The reader's linked brokerage reaches Milo two ways: the CONTEXT block
(`main._with_linked_portfolio`) and the get_my_portfolio tool
(`main._milo_toolbox`). Both follow `classify` here, so one rule decides.

History of the rule:
- 2026-10-27: bare "position", "exposure" and "allocation" matched company and
  Compare questions, and a Compare answer quoted the owner's weights. The rule
  became first-person only ("my holdings", "what do I own").
- 2026-11-11 (live audit, finding M1): first person was still too wide.
  "When should I sell my Apple shares so I pay less tax?" and "Is it legal for
  me to avoid capital gains tax by gifting my Apple shares to my child?" each
  sent every linked holding, and the tax answer listed them all. A made-up
  portfolio, "(not my real holdings)", was compared against "your real book".

So a question reads as one of four kinds:
- EXCLUDED: it rules the reader's real book out. The portfolio is made up, an
  example, a paper one or someone else's, or the reader says not to use theirs.
  Nothing is attached and the tool is not offered, from any page or thread.
- ASKED: it asks about the reader's own portfolio or holdings.
- MENTIONED: a tax or legal question names the reader's shares only as its
  premise ("my Apple shares"). Milo answers those from general rules and does
  not decide them, and the linked block holds no tax lots or purchase dates. So
  the holdings could add nothing it may use, only exposure. Naming the
  portfolio itself still counts ("which of my holdings ...").
- NONE: nothing about the reader's own holdings.

A miss costs one answer without the reader's holdings, and asking about "my
holdings" or asking from the Brokerage page brings them in. A false match sends
every holding to the model provider and can put them in the answer. So where
the words are ambiguous, the rule leans to leaving the portfolio out.
"""
from __future__ import annotations

import re
from typing import List

ASKED, MENTIONED, EXCLUDED, NONE = "asked", "mentioned", "excluded", "none"

_I = re.I

# What a reader calls their whole book (or a part of it read as a whole)
_BOOK = (r"portfolios?|holdings|positions|investments|brokerage(?!\s+account\b)|book|accounts|exposures?|allocation|"
         r"weights|weighting")
# The book or one holding in it, for the phrases that rule it out
_OWNED = _BOOK + r"|account|position|shares|stocks|money"
# Broker and account-type words that make a single "my ... account" a brokerage account
_ACCOUNT_KIND = (r"brokerage|broker|linked|investment|investing|trading|retirement|roth|ira|401\(?k\)?|taxable|"
                 r"individual|joint|margin|custodial|hsa|robinhood|schwab|fidelity|vanguard|e\*?trade|webull|ibkr|"
                 r"tastytrade|merrill|ameritrade|sofi|public")
# A single holding, or money in the book: what a premise names ("my Apple shares"); "my dad how options" is not one,
# so one word at most comes between (as the 2026-10-27 rule)
_HOLDING = (r"stocks|shares|options|calls|puts|cash|money|gains?|losses|dividends|returns?|performance|p&l|pnl|"
            r"position|stake|lots?|cost\s+basis|balance")

# ---- kept apart before anything is read: phrases about a portfolio that is not the reader's real one
# A portfolio made up for the question. The adjective sits on the noun, never across "my": "stress test my portfolio"
# and "model my portfolio's risk" are about the real one.
_INVENTED = [
    re.compile(r"\b(?:made[- ]?up|hypothetical|imaginary|imagined|fictional|fictitious|fake|pretend|invented|example|"
               r"sample|model|mock|dummy|toy|practice|paper|demo|theoretical|notional)\s+(?:(?!my\b|our\b)[\w/-]+\s+){0,2}?"
               r"(?:portfolios?|holdings|positions|accounts?|books?|allocations?|mix)\b", _I),
    # weights given for a portfolio that is not "my" one: "a portfolio of 50% AAPL", "take a portfolio that's 60% SPY"
    re.compile(r"\b(?:a|an|the|this|that|some|one)\s+(?:(?!my\b|our\b)[\w/-]+\s+)?portfolios?\s+(?:of|with|that(?:'s|\s+is)|"
               r"which\s+is|holding|split|made\s+of)\s+(?:[\w$]+\s+){0,2}?\d{1,3}(?:\.\d+)?\s*%", _I),
    # the reader's portfolio imagined with a different make-up: "pretend my portfolio were 100% NVDA"; not a scenario
    # on the real one ("if my portfolio were down 20%")
    re.compile(r"\b(?:pretend|imagine|suppose|supposing|say|assume|assuming|what\s+if|if)\s+(?:that\s+)?(?:my|our)\s+"
               r"(?:[\w-]+\s+)?(?:portfolio|holdings|account|book)\s+(?:were|was|is|had\s+been)\s+(?:\d{1,3}(?:\.\d+)?\s*%|"
               r"all|only|entirely|fully|just)|\b(?:pretend|imagine|suppose|supposing|say|assume|assuming|what\s+if|if)\s+"
               r"(?:that\s+)?(?:my|our)\s+(?:[\w-]+\s+)?(?:portfolio|holdings|account|book)\s+consist(?:s|ed)\s+of", _I),
]
# Someone else's: "my dad's portfolio", "my wife's Roth account", "my clients' holdings"
_SOMEONE_ELSES = re.compile(
    r"\b(?:my|our)\s+(?:wife|husband|spouse|partner|girlfriend|boyfriend|fianc[ée]e?|dad|father|mom|mum|mother|parents?|"
    r"son|daughter|kids?|child|children|brother|sister|siblings?|friend|cousin|uncle|aunt|grand(?:ma|pa|mother|father|"
    r"parents?|son|daughter)|clients?|boss|colleague|co-?worker|roommate|neighbou?r|family|in-laws?|niece|nephew)"
    r"(?:'s|s'|s)?\s+(?:[\w-]+\s+)?(?:" + _OWNED + r"|exposure)\b", _I)
# The reader says not to use theirs: "(not my real holdings)", "don't look at my accounts", "leave my portfolio out".
# A bare "not my holdings" is left alone: "which QQQ names are not my holdings" asks about them.
_OPT_OUT = [
    re.compile(r"\bnot\s+(?:(?:about|from|using|based\s+on|to\s+do\s+with)\s+)?(?:my|our)\s+(?:real|actual|own|linked|current|"
               r"personal|true)\s+(?:" + _OWNED + r"|one|ones)\b", _I),
    re.compile(r"\b(?:not|nothing)\s+(?:about|to\s+do\s+with|based\s+on|using)\s+(?:my|our)\s+(?:[\w-]+\s+)?(?:" + _OWNED + r")\b", _I),
    re.compile(r"\b(?:don'?t|do\s+not|never|without|no\s+need\s+to|please\s+don'?t|rather\s+than|instead\s+of)\s+"
               r"(?:you\s+)?(?:use|using|look(?:ing)?\s+(?:at|into)|check(?:ing)?|read(?:ing)?|pull(?:ing)?\s+(?:in|up)|"
               r"includ(?:e|ing)|consider(?:ing)?|touch(?:ing)?|referenc(?:e|ing)|mention(?:ing)?|bring(?:ing)?\s+(?:in|up)|"
               r"access(?:ing)?|open(?:ing)?|factor(?:ing)?\s+in)\s+(?:in\s+)?(?:my|our)\s+(?:[\w-]+\s+)?(?:" + _OWNED + r")\b", _I),
    re.compile(r"\b(?:ignore|ignoring|disregard(?:ing)?|exclude|excluding|forget(?:ting)?\s+(?:about\s+)?|set(?:ting)?\s+aside)\s+"
               r"(?:my|our)\s+(?:[\w-]+\s+)?(?:" + _OWNED + r")\b", _I),
    re.compile(r"\bleave\s+(?:my|our)\s+(?:[\w-]+\s+)?(?:" + _OWNED + r")\s+out\b|\b(?:my|our)\s+(?:[\w-]+\s+)?(?:" + _OWNED +
               r")\s+aside\b", _I),
]
# "if I bought AAPL in 2015", "suppose I own 100 shares": a trade imagined, not one on the books. Kept apart, so
# what else the question says still counts ("if I sold my Apple shares, how would my exposure change").
_IMAGINED_TRADE = re.compile(
    r"\b(?:if|suppose|supposing|imagine|say|pretend|assuming|assume|what\s+if)\s+(?:that\s+)?(?:i|we)\s+"
    r"(?:had\s+|'d\s+|have\s+|were\s+to\s+|did\s+)?(?:own(?:ed)?|held|hold|bought|buy|sold|sell|invested|put)\b"
    r"|\bhad\s+(?:i|we)\s+(?:bought|sold|held|owned|invested)\b", _I)
# Questions about the reader's Optic account itself, where "my account" is the login, not the brokerage
_ACCOUNT_ADMIN = re.compile(
    r"\b(?:delete|deleting|close|closing|cancel|cancell?ing|deactivate|password|log\s?-?in|log\s?out|sign\s?(?:in|up|out)|"
    r"subscription|billing|invoice|refund|upgrade|downgrade|e-?mail|username|2fa|two[- ]factor)\b", _I)
_BARE_ACCOUNT = re.compile(r"\b(?:my|our)\s+(?:(?:optic|user|login|email|google|apple|github|free|pro|paid)\s+)?accounts?\b", _I)

# ---- what counts, in what is left
# The book named as such, or asked about: these count in every question, tax and legal ones included
_ASKS_ABOUT_BOOK = [
    re.compile(r"\b(?:my|our)\s+(?:[\w-]+\s+)?(?:" + _BOOK + r")\b", _I),
    re.compile(r"\bwhich\s+of\s+(?:my|our)\b", _I),
    re.compile(r"\b(?:what|which)\s+(?:[\w-]+\s+){0,3}?(?:do|did)\s+(?:i|we)\s+(?:own|hold|have)\b", _I),
    re.compile(r"\bhow\s+(?:much|many)\s+(?:[\w-]+\s+){0,3}?(?:do|did)\s+(?:i|we)\s+(?:own|hold|have)\b", _I),
    re.compile(r"\b(?:do|did)\s+(?:i|we)\s+(?:own|hold)\b", _I),
    re.compile(r"\b(?:am\s+i|are\s+we)\s+(?:too\s+|over\s?|under\s?|well\s+|very\s+|more\s+|less\s+)?(?:exposed|concentrated|"
               r"diversified|overweight|underweight|overexposed|underexposed)\b", _I),
    re.compile(r"\b(?:exposed|concentrated|diversified|overweight|underweight)\s+(?:am\s+i|are\s+we)\b", _I),
    re.compile(r"\blast\s+sync\b|\bsince\s+the\s+last\s+(?:sync|update|refresh|import|connection)\b", _I),
]
# The reader's own holding or money as a premise: these count except in a tax or legal question
_NAMES_A_HOLDING = [
    re.compile(r"\b(?:my|our)\s+(?:[\w-]+\s+)?(?:" + _HOLDING + r")\b", _I),
    # one account, as a premise ("gift shares from my brokerage account") or a question ("is my Roth account
    # diversified?"): the book, but named through one account
    re.compile(r"\b(?:my|our)\s+(?:(?:" + _ACCOUNT_KIND + r")\s+){0,2}account\b", _I),
    re.compile(r"(?<!should )(?<!would )(?<!could )(?<!if )\b(?:i|we)\s+(?:own|hold|bought|sold)\b", _I),
    re.compile(r"\b(?:affects?|affecting|hits?|hitting|hurts?|hurting|touch(?:es)?|impacts?|impacting)\s+(?:me|us)\b", _I),
    re.compile(r"\bsince\s+my\s+last\b", _I),
]
# A tax or legal question. Not "real estate" (a sector), not "cost basis" (a holding's fact the block carries), not
# a company's lawsuit or regulator (company news, asked about a holding).
_TAX_OR_LEGAL = re.compile(
    r"\b(?:tax(?:es|ed|able|ation|[- ]free|[- ]efficient)?|capital\s+gains?|cap\s+gains|wash[- ]sales?|tax[- ]loss|"
    r"harvest(?:ing)?\s+(?:the\s+)?(?:losses|gains)|irs|hmrc|deduct(?:ion|ible|ions)?|write[- ]?offs?|1099s?|w-?2|"
    r"form\s+\d{3,4}|gift(?:s|ed|ing)?|inherit(?:ance|ed|ing|s)?|(?<!real\s)estates?|step[- ]up|probate|"
    r"beneficiar(?:y|ies)|legal(?:ly)?|illegal(?:ly)?|lawful(?:ly)?|unlawful(?:ly)?|laws?|lawyers?|attorneys?|cpa|"
    r"accountants?|insider\s+trading|utma|ugma|divorce)\b", _I)


def _plain(question: str) -> str:
    return " ".join(str(question or "").replace("’", "'").replace("‘", "'").split())


def _without(text: str, patterns: List["re.Pattern"]) -> str:
    for rx in patterns:
        text = rx.sub(" • ", text)
    return text


def classify(question: str) -> str:
    """ASKED, MENTIONED, EXCLUDED or NONE for one question (see the module's notes)."""
    q = _plain(question)
    if not q:
        return NONE
    if any(rx.search(q) for rx in _OPT_OUT):
        return EXCLUDED
    left = _without(q, _INVENTED + [_SOMEONE_ELSES])
    set_apart = left != q
    left = _IMAGINED_TRADE.sub(" • ", left)
    if _ACCOUNT_ADMIN.search(left):
        left = _BARE_ACCOUNT.sub(" • ", left)
    if any(rx.search(left) for rx in _ASKS_ABOUT_BOOK):
        return ASKED            # named in its own right, even beside a made-up one: "compare it with my holdings"
    if set_apart:
        return EXCLUDED         # the portfolio in question is made up or someone else's
    if any(rx.search(left) for rx in _NAMES_A_HOLDING):
        return MENTIONED if _TAX_OR_LEGAL.search(left) else ASKED
    return NONE


def asks_about_own(question: str) -> bool:
    """The question asks about the reader's own portfolio or holdings."""
    return classify(question) == ASKED
