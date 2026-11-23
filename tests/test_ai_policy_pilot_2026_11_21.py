"""Advice-filter regressions found by Milo's paid pilot of 2026-11-21 (evaluation kit milo-adaptive-2026-11-20).

The pilot captured four sentences that the advice filter removed although none of them gives advice: a bullet label
read as an order to own something ("Own history."), the cash a call's exercise would need read as a share count, and
two loss limits read as promises ("can't lose more than you paid"). Each is checked here the way the filter meets it:
as a whole sentence, as the piece the streaming gate checks, and inside the paragraph the model actually wrote,
streamed through StreamGate and the end-of-stream amend. Beside them are option mechanics of the same shape that the
answer standard asks Milo to explain, education that already passes, and advice in the same neighbourhood that must
still be removed under the same rule. The sentences are verbatim from the pilot's raw responses; the kit's regression
supplement (evaluation/supplements/) keeps them with the answers they came from.
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


# Verbatim from the pilot's raw model text; the reader received each answer without it.
CAPTURED = [
    ("baseline V01-advanced (trade_instruction)", "- **Own history.** A stock that has usually traded at 18x is stretched at 24x."),
    ("baseline V01-advanced, the piece the gate checked", "- **Own history.** "),
    ("candidate O01-intermediate (position_sizing)",
     "If you exercised, you would need cash to buy 100 shares at the strike, and your loss would then follow the stock."),
    ("candidate O01-beginner (guarantee)", "Unlike selling a call, a bought call can't lose more than you paid."),
    ("baseline O01-beginner (guarantee)", "You also hold no shares, so you can't lose money on stock you don't own."),
]


@pytest.mark.parametrize("where,sentence", CAPTURED, ids=[c[0] for c in CAPTURED])
def test_a_sentence_the_pilot_lost_reaches_the_reader(where, sentence):
    assert rules(sentence) == []


# The same shapes, written as the option mechanics and labels Milo is asked to use.
SAME_SHAPE = [
    "If the call is exercised, you buy 100 shares at the strike and then carry the stock's risk.",
    "Exercise would buy 100 shares at the strike, a separate purchase you must pay for.",
    "If it is exercised at expiration, you would have to buy 100 shares at the strike.",
    "A long call can't lose more than the premium you paid, plus fees.",
    "- **Own history:** no past P/E range is loaded.",
    "**Own history.** No past P/E range is loaded here.",
    "- **Own track record.** The stock has no P/E history loaded.",
]


@pytest.mark.parametrize("sentence", SAME_SHAPE)
def test_option_mechanics_and_labels_of_that_shape_reach_the_reader(sentence):
    assert rules(sentence) == []


# Already passing before this change; kept so the change cannot start removing them.
EDUCATION = [
    "No profit is guaranteed.",
    "Nothing here guarantees a profit.",
    "Past performance does not guarantee future results.",
    "There is no guaranteed return on an option.",
    "At expiration, an in-the-money call is generally exercised automatically unless you tell your broker otherwise.",
    "You can give your broker contrary instructions if you don't want the call exercised.",
    "Before expiration, you can choose to exercise early, though that usually gives up the option's remaining time value.",
    "Exercising the call would mean buying 100 shares at the strike price, which you would need to pay for.",
    "Upon exercise, you would pay the strike price for 100 shares.",
    "Your broker may set its own cutoff time for exercise instructions.",
    "Its own history matters as much as the peers do.",
    # what the instructions' new bullet on a bought option asks Milo to say (tests/test_milo_options_exercise.py)
    "At expiration, a US stock option that is in the money by $0.01 or more is exercised automatically unless you give "
    "your broker contrary instructions.",
    "If you don't want the shares, you can tell your broker before its cut-off that you do not want the call exercised.",
    "Exercising this call buys 100 shares at the strike, a separate purchase you must pay for in cash or on margin.",
    "I can't give a dollar figure for that purchase, because the strike isn't in the data.",
    "This applies to a physically settled stock call; a put's exercise sells shares, and an index option settles in "
    "cash with no shares.",
]


@pytest.mark.parametrize("sentence", EDUCATION)
def test_education_about_guarantees_and_exercise_still_reaches_the_reader(sentence):
    assert rules(sentence) == []


# Advice next to those shapes: each must still be removed, under the rule named.
ADVICE = [
    ("Own NVDA here.", "trade_instruction"),
    ("- **Own it.** The setup is strong.", "trade_instruction"),
    ("Own the stock through earnings.", "trade_instruction"),
    ("Own shares of XYZ before the report.", "trade_instruction"),
    ("Buy 100 shares now.", "trade_instruction"),
    ("You should buy 100 shares of XYZ.", "trade_instruction"),
    ("If you exercise, buy 100 shares of XYZ as well.", "trade_instruction"),
    ("If you exercised, buy 100 shares at the strike too.", "trade_instruction"),
    ("If you exercise, you should buy 100 more shares of XYZ.", "trade_instruction"),
    ("If it breaks $50, you would have to buy 100 shares to cover the short.", "trade_instruction"),
    # an order put as what exercise requires: not a purchase or sale at the strike, so not mechanics
    ("If you exercise, you must sell the shares right away to lock in the gain.", "trade_instruction"),
    ("Once exercised, you need to sell the stock immediately.", "trade_instruction"),
    # (removed as position sizing until candidate 5, 2026-11-23, whose exercise order reads "Exercise the call" first)
    ("Exercise the call and buy 100 shares of the stock.", "trade_instruction"),
    ("You need cash to buy 100 shares, so buy 100 shares now.", "position_sizing"),
    ("Put 10% of your portfolio into this call.", "position_sizing"),
    ("Risk 2% of your account per trade.", "position_sizing"),
    ("Allocate 20% of your savings to options.", "position_sizing"),
    ("You can't lose with this trade.", "guarantee"),
    ("This call can't lose.", "guarantee"),
    ("You won't lose money on this one.", "guarantee"),
    ("You cannot lose here.", "guarantee"),
    ("You can't lose, and the upside is huge.", "guarantee"),
    ("This trade is guaranteed to make money.", "guarantee"),
    ("It's a risk-free trade.", "guarantee"),
]


@pytest.mark.parametrize("sentence,rule", ADVICE)
def test_advice_beside_those_shapes_is_still_removed(sentence, rule):
    assert rules(sentence) == [rule]


# The paragraphs the model wrote, verbatim; the reader must receive each one whole, however the stream is cut.
PARAGRAPHS = {
    "baseline V01-advanced": (
        "**What would decide it:**\n- **Growth.** If EPS is compounding at 15% or more, 24x can be modest. At 3% it is a "
        "full price. The PEG ratio (P/E divided by growth) needs the missing growth estimate.\n- **Peers.** A 24x multiple "
        "is cheap against a group at 35x and rich against one at 15x.\n- **Own history.** A stock that has usually traded "
        "at 18x is stretched at 24x. One that has averaged 30x is not.\n- **Earnings quality.** Trailing EPS can be "
        "inflated by one-offs or depressed by a bad year. That would make 24x misleading in either direction."),
    "candidate O01-intermediate": (
        "**Exercise risk.** This is an American-style, physically settled contract. If you exercised, you would need cash "
        "to buy 100 shares at the strike, and your loss would then follow the stock. Your position is open with no shares "
        "held. If an in-the-money call is left unexercised at expiry, your broker may auto-exercise it, which can create a "
        "stock purchase you didn't plan for. Check how your broker handles that."),
    "candidate O01-beginner": (
        "**Why it's capped.** You bought the call, so you hold the right to buy 100 shares at the strike price, but you "
        "aren't obliged to. If the stock ends up below the strike at expiration, you let the option expire worthless and "
        "lose the $240. You hold no shares and haven't exercised, so nothing else is at risk. Unlike selling a call, a "
        "bought call can't lose more than you paid."),
    "baseline O01-beginner": (
        "**Why the loss is capped.** You bought the call, so you hold the right to buy 100 shares at the strike price. You "
        "don't have to use it. If the stock ends up below the strike at expiration, the call expires worthless and you "
        "lose the $240. Because you own the option and haven't sold or written one, you have no further obligation. You "
        "also hold no shares, so you can't lose money on stock you don't own."),
}


@pytest.mark.parametrize("size", [1, 7, 40, 10_000])
@pytest.mark.parametrize("name", sorted(PARAGRAPHS))
def test_the_pilot_paragraph_reaches_the_reader_whole_through_the_stream(name, size):
    text = PARAGRAPHS[name]
    final, amend = streamed(text, size)
    assert amend is None
    assert final == text


@pytest.mark.parametrize("size", [1, 40])
def test_an_order_added_to_a_pilot_paragraph_is_still_cut_from_the_stream(size):
    text = PARAGRAPHS["baseline V01-advanced"] + "\n- **Own it.** Buy 100 shares now."
    final, amend = streamed(text, size)
    assert amend is not None and amend["rules"] == ["trade_instruction"]
    assert "Own it" not in final and "Buy 100 shares now" not in final
    assert "A stock that has usually traded at 18x is stretched at 24x." in final
