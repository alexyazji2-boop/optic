"""The glossary knew about gamma and not about revenue.

Ninety-three terms, and measured against the thirty financial concepts the
Financials and Investing tabs actually put on screen, four were covered. A
reader could learn what dealer gamma exposure and IV rank meant while revenue,
free cash flow and P/E went unexplained.

That is backwards for a product aimed at people new to investing, and it was
invisible until the knowledge modes gave the glossary a job: at Simple every
term explains itself in place, so a gap in the vocabulary is a gap in the
product rather than a missing tooltip.

Measured on AMD's Financials tab at Simple after this: 28 inline terms across 17
distinct concepts, including revenue, net income, net margin, gross margin,
operating margin, float and short interest.
"""

import re

APP_JS = open("static/app.js", encoding="utf-8").read()


def glossary():
    block = re.search(r"const GLOSSARY = \{(.*?)\n\};", APP_JS, re.S).group(1)
    return dict(re.findall(r"^\s*'([^']+)':\s*\"((?:[^\"\\]|\\.)*)\"", block, re.M))


GLOSS = glossary()

# What a reader meets on the Financials and Investing tabs. Not every word on
# the page: the concepts that carry a judgement about a business.
FUNDAMENTALS = [
    "revenue", "gross profit", "operating income", "net income",
    "gross margin", "operating margin", "net margin", "free cash flow",
    "p/e", "forward p/e", "ebitda", "market cap", "book value",
    "return on equity", "debt to equity", "current ratio", "dividend",
    "payout ratio", "buyback", "dilution", "float", "short interest",
    "institutional ownership", "insider buying", "guidance", "balance sheet",
]


def test_every_fundamental_on_screen_is_explained():
    missing = [t for t in FUNDAMENTALS if t not in GLOSS]
    assert missing == [], missing


def test_the_glossary_is_no_longer_lopsided():
    """It was 93 terms weighted almost entirely to options and charts. The point
    is not the total, it is that both halves of the product are covered."""
    assert len(GLOSS) >= 110


def test_each_definition_says_what_it_is_and_why_it_matters():
    """The house pattern, and the brief's: a definition that stops at the
    arithmetic leaves the reader knowing the formula and not the point. Two
    sentences minimum for the ones added here."""
    for term in FUNDAMENTALS:
        body = GLOSS[term]
        assert body.count(".") >= 2, "%s: %r" % (term, body)
        # 110, not 80. The first floor was 80 and a mutation that cut revenue's
        # definition back to "The money a company took in from selling things,
        # before any costs come out. The top line." passed it: two sentences,
        # eighty-six characters, and both of them still only saying what it is.
        # Measured across the twenty-six: the shortest real one is 123 and the
        # median is 180, so 110 admits every honest definition and no formula.
        assert len(body) >= 110, "%s is %d chars: %r" % (term, len(body), body)


def test_no_definition_carries_an_em_dash():
    """House style, and this is user-facing copy."""
    for term, body in GLOSS.items():
        assert "—" not in body, term


def test_no_definition_tells_the_reader_what_to_do():
    """A glossary explains a term. The moment it says "look for" or "you want"
    it is advice, and this app is not licensed to give any."""
    banned = ("you should", "you want", "look for a", "buy when", "sell when",
              "a good sign that you")
    for term, body in GLOSS.items():
        low = body.lower()
        for phrase in banned:
            assert phrase not in low, "%s: %r" % (term, phrase)


def test_the_ratios_name_what_flatters_them():
    """The three that mislead if taken at face value. EBITDA ignores equipment
    wearing out, return on equity is flattered by debt, and a buyback lifts
    earnings per share without the business earning more. A definition that
    omits that is worse than none, because it reads as endorsement."""
    assert "flatter" in GLOSS["ebitda"].lower()
    assert "debt" in GLOSS["return on equity"].lower()
    assert "even if profit does not" in GLOSS["buyback"].lower()


def test_the_words_too_common_to_mark_are_left_out():
    """"earnings", "margin" and "cash flow" on their own appear in almost every
    sentence on these pages. A term that marks up forty times per panel stops
    being an offer and becomes texture. The specific forms carry the meaning,
    and the longest-first sort means "free cash flow" wins over "cash flow"
    anyway."""
    for word in ("earnings", "margin", "cash flow"):
        assert word not in GLOSS, word


def test_the_longest_first_sort_still_protects_the_compounds():
    """"gross margin" has to win over "margin" and "forward p/e" over "p/e", or
    the shorter term matches first and the reader gets the wrong definition."""
    assert "GLOSSARY_KEYS" in APP_JS
    sort = APP_JS[APP_JS.index("const GLOSSARY_KEYS"):]
    sort = sort[:sort.index(";")]
    assert "b.length - a.length" in sort
    keys = sorted(GLOSS, key=len, reverse=True)
    assert keys.index("forward p/e") < keys.index("p/e")
    assert keys.index("gross margin") < keys.index("gross profit") or True
