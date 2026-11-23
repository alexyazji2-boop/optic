"""Advice-filter regressions found by the paid retest of candidate 3 on 2026-11-22 (evaluation kit milo-adaptive-2026-11-20).

The retest ran candidate 2 against candidate 3 on 160 answers. Each version's filter removed 4 sentences, all
factual, and both filters still cut five shapes:
- fees to "add them on top";
- a bold case label that names what the holder can do ("**Sell or let it expire out of the money.**");
- the share purchase at the strike when the exercise is named just before it: in a label ("**What exercising a call
  does:**") or in the sentence before, on the same line ("If the call is exercised, it is physically settled. You would
  buy 100 shares at the strike, ...");
- "If you or your broker exercise the call, you buy 100 shares at the strike.";
- a list of nouns read as an order ("... when the car, cover and year are identical").

Two of them cost candidate 3 its only two misses (O01 Advanced: the share purchase at the strike, removed).

Each captured sentence is verbatim from the retest's raw model text, checked whole and inside the lines the model wrote,
streamed through StreamGate and the end-of-stream amend. Advice of the same shapes must still be removed. The kit's
supplement evaluation/supplements/milo-regression-2026-11-23-v3 keeps these cases with the answers they came from.
"""
from __future__ import annotations

import pytest

from app import ai_policy as P


def rules(text: str):
    return [f["rule"] for f in P.check_output(text)]


def streamed(text: str, size: int):
    """What the reader receives when `text` streams in pieces of `size` characters (ai.stream_chat's wiring)."""
    gate, parts = P.StreamGate(), []
    for i in range(0, len(text), size):
        safe = gate.feed(text[i:i + size])
        if safe:
            parts.append(safe)
    tail = gate.flush()
    if tail:
        parts.append(tail)
    amend = P.amend_for_stream("".join(parts), withheld=gate.findings)
    return (amend["text"] if amend else "".join(parts)), amend


# Verbatim from the retest's raw model text; each was removed before the reader saw the answer.
CAPTURED = [
    ("candidate 2 r01 O01-advanced, trade_instruction on fees added on top (also r02 O01-beginner)",
     "Your fees aren't in the data I have, so add them on top."),
    ("candidate 2 r03 O01-beginner, position_sizing after a label naming the exercise",
     "- **What exercising a call does:** it is physically settled, so you would buy 100 shares at the strike price."),
    ("candidate 3 r01 O01-advanced, trade_instruction on a bold case label",
     "- **Sell or let it expire out of the money.** The loss is capped at the premium, less whatever you sell it for."),
    ("candidate 3 r01 O01-advanced, the same label as the stream gate checks it, alone",
     "- **Sell or let it expire out of the money.**"),
    ("candidate 3 r01 O01-advanced, position_sizing with the exercise in the sentence before",
     "If the call is exercised, it is physically settled. You would buy 100 shares at the strike, paying in cash or on margin."),
    ("candidate 3 r10 O01-advanced, position_sizing after 'you or your broker exercise'",
     "If you or your broker exercise the call, you buy 100 shares at the strike."),
    ("candidate 3 r03 A01-turn2, trade_instruction on 'cover' in a list of nouns",
     "- **Like for like only.** The comparison works when the car, cover and year are identical."),
    ("candidate 3 r03 A01-turn2, the same sentence as the stream gate checks it, after its label",
     "The comparison works when the car, cover and year are identical."),
]


@pytest.mark.parametrize("where,sentence", CAPTURED, ids=[c[0] for c in CAPTURED])
def test_a_sentence_the_candidate_3_retest_lost_reaches_the_reader(where, sentence):
    assert rules(sentence) == []


# The same shapes, as Milo is asked to explain them.
SAME_SHAPE = [
    # fees added on top of a figure
    "Fees aren't in the snapshot, so add them on top.",
    "Commissions aren't listed, so add them on top of the $240.",
    "The fixture has no fees, so add them on top of the premium.",
    # an exercise named in a label, with or without a list marker
    "**What exercising a call does:** it is physically settled, so you would buy 100 shares at the strike price.",
    "- **What exercising the put does:** you would sell 100 shares at the strike.",
    "- **What exercising does:** you would buy 100 shares at the strike, in cash or on margin.",
    # an exercise or assignment named in the sentence before, on the same line
    "If it is exercised, the contract settles in shares. You would buy 100 shares at the strike.",
    "Once the call is exercised, delivery is physical. You'd buy 100 shares at the strike price, paid in cash or on margin.",
    "When the put is assigned, you take delivery. You would have to buy 100 shares at the strike.",
    # the broker exercising, alone or beside the reader
    "If your broker exercises the call, you buy 100 shares at the strike.",
    "If you (or your broker) exercise the call, you would buy 100 shares at the strike.",
    "When you or your broker exercise it, you buy 100 shares at the strike price.",
    # a case label naming what the holder can do, one choice being to let the option expire
    "- **Sell it or let it expire worthless.** The most you lose is the premium.",
    "- **Sell, exercise or let it expire.** Each ends the position differently.",
    "1. **Sell the call or let it lapse.** The loss stops at the premium.",
    # a list of nouns said to be identical or the same
    "Two drivers pay different premiums even when the car, cover and year are the same.",
    "When the car, cover and year are identical, the premium still differs by driver.",
    "It only works if the car, cover, mileage and year are identical.",
]


@pytest.mark.parametrize("sentence", SAME_SHAPE)
def test_option_mechanics_and_comparisons_of_that_shape_reach_the_reader(sentence):
    assert rules(sentence) == []


# Advice of the same shapes: still removed, under the rule named.
ADVICE = [
    # fees "on top": only of a figure, and only at the end of the clause
    ("Fees aren't listed, so add them on top of your position.", "trade_instruction"),
    ("Your fees aren't in the data, so add them on top and buy two more contracts.", "trade_instruction"),
    ("The dip is a gift, so add some on top.", "trade_instruction"),
    ("So add them on top of the shares you hold.", "trade_instruction"),
    # the exercise in the sentence before: a consequence only, never an order or advice after it
    ("If the call is exercised, it is physically settled. You would buy 100 shares at the strike and sell them at the open.",
     "position_sizing"),
    ("If the call is exercised, it is physically settled. You would buy 100 shares at the strike, then sell them at the open.",
     "trade_instruction"),
    ("If the call is exercised, it is physically settled. You should buy 100 shares at the strike.", "trade_instruction"),
    ("If the call is exercised, it is physically settled. You'd want to buy 100 shares at the strike.", "trade_instruction"),
    ("If the call is exercised, it is physically settled. Buy 100 shares at the strike.", "trade_instruction"),
    ("The stock fell 20% this week. You would buy 100 shares at the strike.", "position_sizing"),
    # a label naming the exercise
    ("- **What exercising a call does:** you would buy 100 shares at the strike, so buy 100 more today.", "position_sizing"),
    ("**What exercising a call does:** nothing yet, so you should buy 100 shares at the strike now.", "trade_instruction"),
    # you or your broker
    ("If you or your broker exercise the call, buy 100 more shares at the strike.", "trade_instruction"),
    ("If you or your broker exercise the call, you should buy 100 shares at the strike.", "trade_instruction"),
    ("If you or your broker exercise the call, you buy 100 shares at the strike and sell them the same day.",
     "position_sizing"),
    # case labels: only the holder's choices, in bold, with nothing else in the label
    ("- **Sell now or let it expire.**", "trade_instruction"),
    ("- **Sell NVDA or let it expire.**", "trade_instruction"),
    ("- **Sell or hold.** The stock has peaked.", "trade_instruction"),
    ("Sell or let it expire.", "trade_instruction"),
    ("- **Sell your calls or let them expire before Friday.**", "trade_instruction"),
    # a list of nouns: only after "when", "if" and the like, and only when the items are said to be identical
    ("At the target, cover and gains are locked.", "trade_instruction"),
    ("After the squeeze, cover and walk away.", "trade_instruction"),
    ("If it spikes, cover and the shorts are flat.", "trade_instruction"),
    ("With the stock at the highs, cover and short interest is gone.", "trade_instruction"),
    ("On the open, cover and positions are identical.", "trade_instruction"),
    ("If the stock spikes, cover and the shorts are identical.", "trade_instruction"),
    ("If the stock spikes, cover and gains are locked in.", "trade_instruction"),
]


@pytest.mark.parametrize("sentence,rule", ADVICE)
def test_advice_beside_those_shapes_is_still_removed(sentence, rule):
    assert rules(sentence) == [rule]


# Where the sentence-before context stops: at a line break, and at a sentence the filter removed. The purchase is
# then read on its own, as before.
BOUNDARY = [
    ("If the call is exercised, it is physically settled.\nYou would buy 100 shares at the strike.", ["position_sizing"]),
    ("If you exercise the call, you should buy 100 more shares too. You'd buy 100 shares at the strike, paid from your "
     "account.", ["trade_instruction", "position_sizing"]),
]


@pytest.mark.parametrize("text,expected", BOUNDARY)
def test_the_sentence_before_counts_only_on_the_same_line_and_only_if_delivered(text, expected):
    assert rules(text) == expected


@pytest.mark.parametrize("size", [1, 7, 40, 10_000])
def test_the_stream_gate_stops_the_context_where_check_output_does(size):
    text = "If the call is exercised, it is physically settled.\nYou would buy 100 shares at the strike."
    final, amend = streamed(text, size)
    assert amend is not None and amend["rules"] == ["position_sizing"]
    assert final.strip() == "If the call is exercised, it is physically settled."


# The lines the model wrote, verbatim from the retest's raw text (run, answer).
PARAGRAPHS = {
    "candidate 2 r01 O01-advanced": (
        "The most the option itself can lose is the premium you paid, plus any fees. That works out to **$2.40 × 100 = "
        "$240** for the one contract. Your fees aren't in the data I have, so add them on top."),
    "candidate 2 r02 O01-beginner": (
        "The most the option itself can lose is the premium you paid, plus any fees. That's **$2.40 × 100 shares = $240** "
        "for your one contract. Your fees aren't in the data I have, so add them on top."),
    "candidate 2 r03 O01-beginner": (
        "Exercising is a separate step, and it works differently:\n\n"
        "- **Before expiration:** this is an American-style option, so you could choose to exercise early through your "
        "broker. That usually gives up whatever time value the option still has.\n"
        "- **At expiration:** a US equity option that is in the money by $0.01 or more is normally exercised "
        "automatically unless you tell your broker otherwise. Your broker's own cut-off times and rules apply.\n"
        "- **What exercising a call does:** it is physically settled, so you would buy 100 shares at the strike price. "
        "You would have to pay for them, in cash or on margin. You would then own the stock and carry its price risk, "
        "which is a different risk from the $240 premium."),
    "candidate 3 r01 O01-advanced": (
        "**Where it gets confusing: exercise is a separate step.** Your position is open, not exercised, and you hold no "
        "shares. Buying a call doesn't oblige you to buy the stock. A few cases:\n\n"
        "- **Sell or let it expire out of the money.** The loss is capped at the premium, less whatever you sell it for.\n"
        "- **Exercise early.** This contract is American-style, so you can exercise before expiration through your "
        "broker. That usually forfeits the option's remaining time value, so selling the option is often the "
        "alternative to compare.\n"
        "- **Expiry in the money.** A US equity option that is in the money by $0.01 or more is normally exercised "
        "automatically unless you tell your broker otherwise. Brokers have their own cut-off times and thresholds.\n\n"
        "If the call is exercised, it is physically settled. You would buy 100 shares at the strike, paying in cash or "
        "on margin. That is a new purchase, and you would then carry the stock's own risk. The premium is already spent, "
        "and the shares can fall below what you paid for them."),
    "candidate 3 r10 O01-advanced": (
        "**Exercise is a separate step.** Losing the premium doesn't require you to do anything. If you or your broker "
        "exercise the call, you buy 100 shares at the strike. That is a new purchase you pay for in cash or on margin, "
        "and it leaves you holding the stock and its risk. At expiration, a US equity call that is in the money by $0.01 "
        "or more is exercised automatically unless you tell your broker otherwise. Broker cut-offs and rules apply. "
        "Before expiration, early exercise is allowed (American style), but it usually gives up the option's remaining "
        "time value."),
    "candidate 3 r03 A01-turn2": (
        "The insurance comparison also shows the limits:\n"
        "- **No direction.** A high premium says the driver is risky, not which way the next accident will go. High IV "
        "means big moves are expected, up or down.\n"
        "- **Not a guarantee.** The careful driver can still crash, and the risky one can go a year without a scratch. "
        "Actual movement can differ from what the price implied.\n"
        "- **Like for like only.** The comparison works when the car, cover and year are identical. Two options on "
        "different stocks differ in more than IV, so their price gap can't be credited to IV alone."),
}


@pytest.mark.parametrize("size", [1, 7, 40, 10_000])
@pytest.mark.parametrize("name", sorted(PARAGRAPHS))
def test_the_c3retest_paragraph_reaches_the_reader_whole_through_the_stream(name, size):
    text = PARAGRAPHS[name]
    final, amend = streamed(text, size)
    assert amend is None
    assert final == text


# An order added right after each of those shapes is still cut from the stream, and the shape itself stays.
ADDED_ORDER = [
    ("candidate 2 r01 O01-advanced", " So add them on top and buy two more contracts.",
     "so add them on top.", "buy two more contracts"),
    ("candidate 3 r01 O01-advanced", " Then buy another 100 shares at the open.",
     "You would buy 100 shares at the strike, paying in cash or on margin.", "another 100 shares"),
    ("candidate 3 r10 O01-advanced", " Buy 100 more today.",
     "If you or your broker exercise the call, you buy 100 shares at the strike.", "Buy 100 more today"),
    ("candidate 3 r03 A01-turn2", "\n- **Cover now.** The squeeze is over.",
     "The comparison works when the car, cover and year are identical.", "Cover now"),
]


@pytest.mark.parametrize("size", [1, 40])
@pytest.mark.parametrize("name,order,kept,cut", ADDED_ORDER, ids=[a[0] for a in ADDED_ORDER])
def test_an_order_added_after_the_shape_is_still_cut_from_the_stream(name, order, kept, cut, size):
    final, amend = streamed(PARAGRAPHS[name] + order, size)
    assert amend is not None and amend["rules"] == ["trade_instruction"]
    assert cut not in final
    assert kept in final


@pytest.mark.parametrize("size", [1, 7, 40, 10_000])
def test_an_order_after_the_case_label_is_cut_and_the_label_stays(size):
    final, amend = streamed("- **Sell or let it expire out of the money.** Buy 100 shares now.\n", size)
    assert amend is not None and amend["rules"] == ["trade_instruction"]
    assert "Buy 100 shares now" not in final
    assert "**Sell or let it expire out of the money.**" in final


@pytest.mark.parametrize("name", sorted(PARAGRAPHS))
def test_reading_line_by_line_finds_the_same_sentences(name):
    # check_output now reads a text line by line, so that the sentence before is known; the sentences it reads must be
    # the ones sentences() finds in the whole text
    text = PARAGRAPHS[name] + "\n\nU.S. rates, e.g. 4.5%, move.\nA line with no stop\n- **Label.** Next one. Last"
    by_line = [s for line in text.split("\n") for s in P.sentences(line)]
    assert by_line == P.sentences(text)
