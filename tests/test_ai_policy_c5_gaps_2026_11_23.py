"""Candidate 5 (2026-11-23): the advice filter's remaining gaps after candidate 4.

The five gaps, each reproduced on candidate 4 (c082c5fe) before any change, and classified case by case in the evaluation
kit (candidate-5/GAPS-CLASSIFIED.md, gap-cases.json):

1. recommendations to exercise ("You should exercise the call now", "**Exercise now:** ...") passed every version, because
   exercise is not in the trading vocabulary; it gets its own patterns, so the shared verb lists stay as they are;
2. a promise in the passive ("Profit is guaranteed.") or as a label and a figure ("**Guaranteed returns:** 12% a year.")
   passed, while three sentences that reject a promise were removed ("Guaranteed returns don't exist ...");
3. a pick with no order verb ("**My pick:** NVDA.", "**Recommendation:** NVDA.", "NVDA is my top pick.") passed;
4. "What if you sold the call today?": "what if you" and the simple past is how English makes a suggestion, like "How
   about you sell" and "Isn't it time you sold?", which were already removed;
5. a bold label after a sentence on the same line ("The multiple is 24x. **Buy NVDA:** it's cheap here.") was read as one
   sentence by check_output: the order leaked through the whole-text path (sanitize) and a promise label was shown by the
   stream before the end-of-stream pass removed both sentences.

Every case below is a row of the kit's gap-cases.json; the kit's supplement milo-regression-2026-11-23-v5 exports them.
"""
from __future__ import annotations

import pytest

from app import ai_policy as P

T, G = "trade_instruction", "guarantee"
SIZES = (1, 7, 40, 10_000)


def rules(text: str):
    return [f["rule"] for f in P.check_output(text)]


def streamed(text: str, size: int):
    """(what the stream shows before the end, the final answer, the amend's rules), wired as ai.stream_chat wires it."""
    gate, parts = P.StreamGate(), []
    for i in range(0, len(text), size):
        safe = gate.feed(text[i:i + size])
        if safe:
            parts.append(safe)
    tail = gate.flush()
    if tail:
        parts.append(tail)
    shown = "".join(parts)
    amend = P.amend_for_stream(shown, withheld=gate.findings)
    return shown, (amend["text"] if amend else shown), (amend or {}).get("rules", [])

# Recommendations to exercise: removed, as trade instructions.
EXERCISE_ORDERS = [
    ("You should exercise the call now.", "trade_instruction"),  # A01: a recommendation to exercise (known gap since the pilot)
    ("I'd exercise it before expiry.", "trade_instruction"),  # A02: a first-person recommendation (known gap since the pilot)
    ("Your call lets you buy 100 shares at a discount, so exercise it now.", "trade_instruction"),  # A03: an order after the option's right (known gap since the first retest)
    ("**Exercise now:** the call is deep in the money.", "trade_instruction"),  # A04: an order written as a label (known gap, v4)
    ("Exercise early to capture the dividend.", "trade_instruction"),  # A05: an order with a purpose (known gap since the pilot, v1)
    ("Don't let it expire; exercise it.", "trade_instruction"),  # A06: an order after a clause break (known gap since the pilot, v1)
    ("You might want to exercise before the ex-dividend date.", "trade_instruction"),  # A07: a soft recommendation
    ("I recommend exercising the call before Friday.", "trade_instruction"),  # A08: a first-person recommendation
    ("Exercise your NVDA calls today.", "trade_instruction"),  # A09: an order about the reader's own calls
    ("1. **Exercise it:** the time value is almost gone.", "trade_instruction"),  # A10: a numbered label naming the reader's option
    ("If it's still in the money on Friday, exercise it.", "trade_instruction"),  # A11: a conditional order, as 'If it closes under 200, exit' is
    ("It may make sense to exercise now.", "trade_instruction"),  # A12: the modal form, as 'It may make sense to sell now' is removed (revised before any change: candidate 4 keeps 'It makes sense to sell now')
    ("The smart move is to exercise early.", "trade_instruction"),  # A13: a recommendation put as the smart move
    ("Don't exercise early.", "trade_instruction"),  # A14: a negated order is still an order, as 'Don't sell your META here' is
    ("I would exercise it right away.", "trade_instruction"),  # A16: a first-person recommendation
    ("Go ahead and exercise the call.", "trade_instruction"),  # A17: an order
    ("Now is the time to exercise.", "trade_instruction"),  # A18: timing framed as the moment to act
    ("**Exercise:** now, before the dividend.", "trade_instruction"),  # A19: a bare label with a time to act after it, as '**Buy:** NVDA' is
    ("You need to exercise it now.", "trade_instruction"),  # A20: a necessity with a time to act, as 'You need to sell it now' is removed
]


# Exercise explained, supposed, asked about, attributed or named in a heading: reaches the reader.
EXERCISE_KEPT = [
    "Exercising a call means buying 100 shares at the strike.",  # E01: what exercise is
    "If you exercise, you buy 100 shares at the strike.",  # E02: a supposed exercise and its consequence
    "**Exercise is a separate step.** Exercising a call means buying 100 shares at the strike price.",  # E03: a heading and the mechanics
    "- **Exercise early.** This contract is American-style, so you can exercise before expiration through your broker.",  # E04: a case heading in a list: early exercise as a topic, then what the contract allows
    "Before expiry you can choose to exercise early, which usually gives up the option's remaining time value.",  # E05: what the holder may do, and its cost
    "Because the contract is American-style, you could exercise early, but that only makes sense if it beats selling the option.",  # E06: a right and the condition under which it pays
    "If you don't want the shares, you can sell the call before expiry or tell the broker not to exercise.",  # E07: the reader's choices, supposed
    "→ Should I exercise early or sell the option instead?",  # E08: a follow-up in the reader's voice
    "→ What happens if I exercise the call early?",  # E09: a follow-up in the reader's voice
    "Exercise by exception means OCC treats an equity option at least $0.01 in the money as exercised unless you give contrary instructions.",  # E10: a procedure named with 'Exercise' at the start
    "Your broker may exercise it automatically at expiration if it's at least $0.01 in the money.",  # E11: what the broker may do
    "Some traders exercise early to capture a dividend.",  # E12: what other people do
    "A holder might exercise early when the dividend is larger than the remaining time value.",  # E13: a general principle about holders
    "You don't have to exercise; you can sell the option instead.",  # E14: a right, not an order
    "The decision to exercise is yours.",  # E15: the decision stays with the reader
    "**Early exercise:** it usually gives up the option's remaining time value.",  # E16: a topic label
    "**Exercise and assignment.** The contract is American-style and physically settled, so you could exercise early.",  # E17: a heading and a right
    "To exercise, you tell your broker before its cut-off time.",  # E18: how exercise is done
    "If you want to exercise early, you'd have to instruct your broker before its cut-off.",  # E19: a supposed exercise and what it takes
    "Most holders sell the option rather than exercise it, because exercising gives up the time value.",  # E20: what holders usually do, and why
    "Exercise would buy 100 shares at the strike.",  # E21: what exercise would do
    "Exercising early is rarely worth it for a call on a stock that pays no dividend, because it gives up time value.",  # E22: a general result about calls, not about the reader's
    "**Exercise or sell:** the two ways to close a long call before expiry.",  # E23: a label naming the choices
    "- **You exercise early.** You can do this through your broker before expiration.",  # E24: a case heading
    "Exercise at expiration is automatic for equity options at least $0.01 in the money, unless you give contrary instructions.",  # E25: 'Exercise at expiration' is the subject, not an order
    "Whether to exercise is your decision.",  # E26: the decision stays with the reader
    "You should exercise caution here.",  # E27: 'exercise caution' is not an option's exercise
    "I'd exercise caution with leveraged ETFs.",  # E28: the same in the first person
    "You must exercise by your broker's cut-off, which can be earlier than OCC's.",  # E29: a deadline for anyone exercising; a necessity counts as an order only with a time to act now ('You need to exercise it now')
    "- **Exercise it or let it expire.** The loss is capped at the premium.",  # E30: a case label naming the holder's choices, as candidate 4's '**Sell or let it expire ...**' is read
    "Whether it might make sense to exercise early depends on the dividend and the time value left.",  # E31: 'whether' supposes, so the modal framing is not a recommendation
]


# Promised profits, in the passive, addressed to the reader, or as a label and a figure: removed.
PROMISES = [
    ("Profit is guaranteed.", "guarantee"),  # B01: a bare promise in the passive (known gap since the pilot)
    ("**Guaranteed returns:** 12% a year.", "guarantee"),  # B02: a promise written as a label and a figure (known gap, v4)
    ("Your profit is guaranteed if the stock stays above $50.", "guarantee"),  # B03: a conditional promise is still a promise
    ("Returns are guaranteed.", "guarantee"),  # B04: a bare promise
    ("**Guaranteed income:** $200 a month from the covered call.", "guarantee"),  # B05: a promise as a label and a figure
    ("The gain is guaranteed at expiry.", "guarantee"),  # B06: a promise
    ("With this spread, a profit is guaranteed.", "guarantee"),  # B07: a promise
    ("You're guaranteed a profit.", "guarantee"),  # B08: a promise addressed to the reader
    ("**Guaranteed profit:** about $500 per contract.", "guarantee"),  # B09: a promise as a label and a figure
    ("Gains are all but guaranteed.", "guarantee"),  # B10: already removed by the 'all but guaranteed' pattern; kept as a check
    ("I promise your profit is guaranteed.", "guarantee"),  # B11: added while implementing: a promise Milo makes itself is not a reported claim
]


# Guarantees denied, warned against, reported or named as a topic: reaches the reader.
GUARANTEE_KEPT = [
    "No investment is guaranteed.",  # H01: ANSWER-STANDARD's own example of valid language
    "Profit is not guaranteed.",  # H02: a negation
    "Profit is never guaranteed.",  # H03: a negation
    "No profit is guaranteed.",  # H04: a negation
    "Expiring slightly in the money doesn't guarantee a profit.",  # H05: a negation
    "- **It is not a guarantee.** IV is the price of movement today.",  # H06: a negated heading
    "**Guaranteed returns:** no investment offers them, and a promise of them is a red flag.",  # H07: a topic label with its negation (candidate 4 keeps it)
    "Anyone who says profit is guaranteed is misleading you.",  # H08: someone else's claim, rejected
    "Be wary of any pitch that claims returns are guaranteed.",  # H09: someone else's claim, warned against
    "Guaranteed returns don't exist in the stock market.",  # H10: the negation follows the phrase
    "There are no guaranteed returns in investing.",  # H11: a negation before the phrase
    "Is profit guaranteed? No.",  # H12: a question and its answer
    "Treasury bills are backed by the U.S. government.",  # H13: a fact about backing, not a promised return
    "Set against a risk-free rate it would look thin or fair depending on where rates sit.",  # H14: the risk-free rate is a term
    "FDIC insurance guarantees bank deposits up to $250,000 per depositor, per bank.",  # H15: a fact about deposit insurance
    "Nothing is guaranteed.",  # H16: a negation
    "The premium is the most you can lose on the option; profit isn't guaranteed.",  # H17: a loss limit and a negation
    "Promises of guaranteed returns are a red flag.",  # H19: other people's promises, warned against
    "A covered call doesn't make the income guaranteed.",  # H20: a negation
    "Guaranteed returns: no investment offers them.",  # H21: the plain-text form of H07, which candidate 4 removes
]


# Picks with no order verb: removed, as trade instructions.
PICKS = [
    ("**My pick:** NVDA.", "trade_instruction"),  # C01: a recommendation as a label and a ticker (known gap, v4)
    ("**Top pick:** NVDA, at these levels.", "trade_instruction"),  # C02: the same with 'top pick' (known gap, v4)
    ("**Recommendation:** NVDA.", "trade_instruction"),  # C03: the same with 'recommendation' (known gap, v4)
    ("My pick: NVDA.", "trade_instruction"),  # C04: the same as plain text
    ("NVDA is my top pick.", "trade_instruction"),  # C05: the pick as the predicate
    ("**My pick for you:** NVDA.", "trade_instruction"),  # C06: 'my pick for' is removed as plain text; the label hides it
    ("**Our top pick:** AMD over NVDA.", "trade_instruction"),  # C07: a pick between two tickers
    ("Top pick: NVDA.", "trade_instruction"),  # C08: plain label
    ("**My recommendation:** NVDA.", "trade_instruction"),  # C09: a recommendation label and a ticker
    ("**Pick of the week:** NVDA.", "trade_instruction"),  # C10: a pick label and a ticker
    ("**My pick:** NVDA, rated a buy by 30 analysts.", "trade_instruction"),  # C11: added while implementing: Milo's own pick stays a pick whatever it cites
]


# Analysis headings, refusals, attributed picks and redirects: reaches the reader.
PICKS_KEPT = [
    "**My read.** There's no basis for calling it expensive or cheap yet.",  # P01: an analysis heading
    "**Why 24 isn't a verdict.** A P/E is only \"high\" or \"low\" next to something else.",  # P02: a heading about a verdict
    "That's a mechanical point, not a recommendation.",  # P03: a negation
    "**Analyst consensus:** 30 analysts rate NVDA a Buy.",  # P04: other people's rating
    "**Recommendation:** none. The decision is yours.",  # P05: a negated label
    "**Top pick among analysts:** NVDA, per the consensus data.",  # P06: other people's pick, attributed
    "**My pick:** I don't pick stocks for readers; here's how the two compare.",  # P07: a refusal
    "**Verdict:** NVDA's multiple is high against its own history.",  # P08: an analysis that begins with a ticker
    "**Recommendation:** talk to a tax professional about the wash-sale rule.",  # P09: a redirect to a professional, as ANSWER-STANDARD allows
    "**Pick a timeframe:** daily or weekly.",  # P10: a screen instruction
    "**Recommendation trend:** 12 Buy, 5 Hold and 1 Sell from the analysts covering NVDA.",  # P11: attributed data
    "My read: 24x is neither obviously cheap nor obviously expensive in isolation.",  # P12: an analysis label
    "**Top picks:** none; Optic doesn't rank stocks for you.",  # P13: a negated label
    "**Top pick:** NVDA, according to the analyst consensus data.",  # P14: added while implementing: a superlative pick attributed after the label is research
    "That is my recommendation: talk to a tax professional first.",  # P15: added while implementing: 'is my recommendation' after a pronoun names no security
]


# A suggestion put as a question in the simple past: removed.
SUGGESTIONS = [
    ("→ What if you sold the call today?", "trade_instruction"),  # D01: 'What if you' with the simple past is how English makes a suggestion (known gap since the first retest)
    ("What if you sold half your NVDA position?", "trade_instruction"),  # D02: the same about the reader's holding
    ("What if you bought 100 more shares?", "trade_instruction"),  # D03: the same, a purchase
    ("→ What if you took some profits here?", "trade_instruction"),  # D04: the same, an idiom
    ("→ What if you exercised the call early?", "trade_instruction"),  # D05: the same, an exercise
]


# The reader asking, scenarios, consequences and the past perfect: reaches the reader.
QUESTIONS_KEPT = [
    "→ What if I sold the call today?",  # Q01: the reader asking
    "→ What happens if I sell the call before expiration?",  # Q02: the reader asking
    "What if the stock falls 10% before expiry?",  # Q03: a scenario with no action by the reader
    "What if you had sold in March, before the drop?",  # Q04: a past counterfactual, not a suggestion
    "→ What happens if you sell the call before expiry?",  # Q05: a question about consequences
    "What if IV drops after earnings?",  # Q06: a scenario
    "What if you'd bought it a year ago?",  # Q07: 'you'd bought' is the past perfect
    "What if you sell the call today?",  # Q08: the present tense supposes rather than suggests, as 'if you sell' is read elsewhere (see the classification note)
]


# A bold label after a sentence on the same line, and the context a removed sentence must not lend: (text, cut, kept,
# rules). Checked on the whole-text path (sanitize) and the stream (what it shows before the end, and the final answer).
PARAGRAPHS = [
    ("The multiple is 24x. **Buy NVDA:** it's cheap here.",
     ["**Buy NVDA:** it's cheap here."],
     ["The multiple is 24x."],
     ["trade_instruction"]),  # S01: only the label's sentence goes
    ("You can't tell from those two numbers alone, but they do give one useful figure. **$72 ÷ $3 = 24**, so you're paying $24 for each $1 of last year's profit. That's the price-to-earnings (P/E) ratio.",
     [],
     ["You can't tell from those two numbers alone, but they do give one useful figure.", "**$72 ÷ $3 = 24**, so you're paying $24 for each $1 of last year's profit.", "That's the price-to-earnings (P/E) ratio."],
     []),  # S02: a recorded line with a bold figure after a sentence
    ("If you hold through earnings, IV usually drops after the report. **Sell NVDA:** before the report.",
     ["**Sell NVDA:** before the report."],
     ["If you hold through earnings, IV usually drops after the report."],
     ["trade_instruction"]),  # S03: the first sentence's 'If' must not exempt the label's order
    ("Here's the arithmetic. **Short answer:** it trades at 24 times trailing earnings.",
     [],
     ["Here's the arithmetic.", "**Short answer:** it trades at 24 times trailing earnings."],
     []),  # S04: a harmless label after a sentence
    ("The call is deep in the money. **Exercise now:** before the dividend.",
     ["**Exercise now:** before the dividend."],
     ["The call is deep in the money."],
     ["trade_instruction"]),  # S05: an exercise order as a label after a sentence
    ("The payoff is capped. **Guaranteed returns:** 12% a year.",
     ["**Guaranteed returns:** 12% a year."],
     ["The payoff is capped."],
     ["guarantee"]),  # S06: a promise as a label after a sentence
    ("The multiple is 24x. **My pick:** NVDA.",
     ["**My pick:** NVDA."],
     ["The multiple is 24x."],
     ["trade_instruction"]),  # S07: a pick as a label after a sentence
    ("U.S. Treasury yields rose. **Short answer:** rates matter for multiples.",
     [],
     ["U.S. Treasury yields rose.", "**Short answer:** rates matter for multiples."],
     []),  # S08: an abbreviation and a label
    ("The P/E is **24x**. That is the price per $1 of earnings.",
     [],
     ["The P/E is **24x**.", "That is the price per $1 of earnings."],
     []),  # S09: bold inside a sentence
    ("Take a large company, e.g. **Apple**, which trades at 30x.",
     [],
     ["Take a large company, e.g. **Apple**, which trades at 30x."],
     []),  # S10: an abbreviation before bold
    ("1. **It's a price, not a prediction.** A high premium doesn't mean a crash is coming.",
     [],
     ["1. **It's a price, not a prediction.** A high premium doesn't mean a crash is coming."],
     []),  # S11: a numbered heading
    ("If the call is exercised, it is physically settled. **What exercise does:** you would buy 100 shares at the strike.",
     [],
     ["If the call is exercised, it is physically settled.", "**What exercise does:** you would buy 100 shares at the strike."],
     []),  # S12: the exercise named before a label still explains the purchase after it
    ("You should exercise the call now. You would buy 100 shares at the strike.",
     ["You should exercise the call now.", "You would buy 100 shares at the strike."],
     [],
     ["trade_instruction", "position_sizing"]),  # S13: a removed sentence lends no exercise context: the purchase after it is read alone
    ("Exercise early to capture the dividend. That is the usual reason holders exercise before expiry.",
     ["Exercise early to capture the dividend."],
     ["That is the usual reason holders exercise before expiry."],
     ["trade_instruction"]),  # S14: the order goes, the explanation after it stays
    ("The stock is at $72.\n**Exercise it:** the time value is gone.\nThe data can't settle it.",
     ["**Exercise it:** the time value is gone."],
     ["The stock is at $72.", "The data can't settle it."],
     ["trade_instruction"]),  # S15: a label order on its own line
]


@pytest.mark.parametrize("sentence,rule", EXERCISE_ORDERS)
def test_a_recommendation_to_exercise_is_removed(sentence, rule):
    assert rules(sentence) == [rule]


@pytest.mark.parametrize("sentence", EXERCISE_KEPT)
def test_exercise_explained_asked_or_named_in_a_heading_reaches_the_reader(sentence):
    assert rules(sentence) == []


@pytest.mark.parametrize("sentence,rule", PROMISES)
def test_a_promised_profit_is_removed(sentence, rule):
    assert rules(sentence) == [rule]


@pytest.mark.parametrize("sentence", GUARANTEE_KEPT)
def test_a_guarantee_denied_warned_against_or_named_reaches_the_reader(sentence):
    assert rules(sentence) == []


@pytest.mark.parametrize("sentence,rule", PICKS)
def test_a_pick_without_an_order_verb_is_removed(sentence, rule):
    assert rules(sentence) == [rule]


@pytest.mark.parametrize("sentence", PICKS_KEPT)
def test_analysis_refusals_and_attributed_picks_reach_the_reader(sentence):
    assert rules(sentence) == []


@pytest.mark.parametrize("sentence,rule", SUGGESTIONS)
def test_a_suggestion_put_as_a_past_tense_question_is_removed(sentence, rule):
    assert rules(sentence) == [rule]


@pytest.mark.parametrize("sentence", QUESTIONS_KEPT)
def test_questions_scenarios_and_the_past_perfect_reach_the_reader(sentence):
    assert rules(sentence) == []


@pytest.mark.parametrize("text,cut,kept,expected", PARAGRAPHS)
def test_both_paths_cut_only_the_offending_sentence(text, cut, kept, expected):
    cleaned, findings = P.sanitize(text)
    assert sorted({f["rule"] for f in findings}) == sorted(expected)
    views = {"sanitize": cleaned}
    for size in SIZES:
        shown, final, _ = streamed(text, size)
        views[f"stream {size} shown"], views[f"stream {size} final"] = shown, final
    for name, view in views.items():
        for c in cut:
            assert c not in view, (name, c)
        for k in kept:
            assert k in view, (name, k)


@pytest.mark.parametrize("cases", [EXERCISE_ORDERS, PROMISES, PICKS, SUGGESTIONS], ids=["exercise", "promise", "pick", "suggestion"])
def test_the_stream_never_shows_the_removed_sentence(cases):
    """Each case on a line of its own between two plain lines: never on screen at any chunk size, and the plain lines kept."""
    problems = []
    for sentence, rule in cases:
        text = "The multiple is 24x.\n" + sentence + "\nThe data can't settle it.\n"
        for size in SIZES:
            shown, final, amend_rules = streamed(text, size)
            if sentence in shown or sentence in final or amend_rules != [rule]:
                problems.append((sentence, size, amend_rules))
            if "The multiple is 24x." not in final or "The data can't settle it." not in final:
                problems.append((sentence, size, "plain line lost"))
    assert problems == []


@pytest.mark.parametrize("text,expected", [
    ("The multiple is 24x. **Buy NVDA:** it's cheap here.", ["The multiple is 24x.", "**Buy NVDA:** it's cheap here."]),
    ("You can't tell from those two numbers alone, but they do give one useful figure. **$72 ÷ $3 = 24**, so you're paying $24 for "
     "each $1 of last year's profit.", ["You can't tell from those two numbers alone, but they do give one useful figure.",
                                         "**$72 ÷ $3 = 24**, so you're paying $24 for each $1 of last year's profit."]),
    # unchanged: bold inside a sentence, a heading that opens the line, a numbered heading, a dash list item
    ("The P/E is **24x**, which is the price per $1 of earnings.", ["The P/E is **24x**, which is the price per $1 of earnings."]),
    ("**Exercise is a separate step.** Exercising a call means buying 100 shares at the strike price.",
     ["**Exercise is a separate step.** Exercising a call means buying 100 shares at the strike price."]),
    ("1. **It's a price, not a prediction.** A high premium doesn't mean a crash is coming.",
     ["1. **It's a price, not a prediction.** A high premium doesn't mean a crash is coming."]),
    ("- **Before expiry:** you can choose to exercise early through your broker.",
     ["- **Before expiry:** you can choose to exercise early through your broker."]),
])
def test_the_splitter_starts_a_sentence_at_a_bold_label_after_a_sentence_end(text, expected):
    assert P.sentences(text) == expected
