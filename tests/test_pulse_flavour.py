"""Pulse's personality: the funny friend on the desk.

2026-10-12, with a screenshot of another assistant roasting a BAC call: "add a
personality to pulse where it speaks to the user like this, in a joking and
friendly way". Every reply now, for the neutral analyst; the limits below are
the ones it always had, plus no slur stand-ins and no jokes about a reader's
partner or job.

Before that (kept for the history):

Asked for with a screenshot of another assistant answering "would you swing NVDA
calls into the weekend?" as a trading-forum regular: "have pulse humorous in
this tone from time to time". An instruction to be funny occasionally gets
every reply or none, so the server picks: about one reply in four, the same for
the same question, never for the other lenses, never when the question is about
a loss or asks for the long form. The tone is borrowed and the limits are not.
The screenshot told the reader to buy, called ordinary traders poor and stated
"inverse retail" as if it were a finding; the block says no to each.
"""
from __future__ import annotations

import pytest

from app import ai


def flat(text):
    return " ".join(text.lower().split())


FLAVOUR = flat(ai.FLAVOUR_PROMPT)

QUESTIONS = [
    "would you swing NVDA calls into the weekend?", "what is the gamma flip on SPY",
    "is TSLA overbought", "how is the macro regime", "tell me about AMD earnings",
    "why is COIN down today", "explain vanna", "compare MSFT and GOOG", "is the vix cheap",
    "what moved today", "what does the put wall at 6,100 mean", "is the dollar rolling over",
    "how are small caps doing", "what's the read on HYG", "does the curve matter here",
    "is oil breaking out", "what do insiders think of COIN", "is the 10 year at a high",
    "what's pulling SPY lower", "which sectors are leading", "how's the VIX term structure",
    "what happened to PLTR", "is IWM a buy here", "summarise the tape", "what's priced into earnings",
    "where is support on QQQ", "explain gamma squeeze", "how is credit behaving",
    "is bitcoin leading stocks", "what should I watch tomorrow",
]


def test_it_is_occasional_and_the_same_for_the_same_question():
    """About one reply in two since the strategy brief asked for "occasional
    light humor" (2026-10-12); FLAVOUR_ONE_IN = 1 would restore every reply."""
    got = [ai.flavour_for(i % 4 + 1, q) for i, q in enumerate(QUESTIONS)]
    assert all(g in ("", ai.FLAVOUR_PROMPT) for g in got)
    assert 0.25 <= sum(1 for g in got if g) / len(got) <= 0.75
    assert ai.flavour_for(3, QUESTIONS[0].upper() + "  ") == ai.flavour_for(3, QUESTIONS[0])


def test_the_gate_reads_the_question_not_the_page_data():
    """It ran on the turn with CONTEXT prepended, so "stop loss" in the entry
    plan matched the loss filter and it was off on 20 of 21 eval questions."""
    ctx = {"entry_plan": {"note": "stop loss below the 50-day, detailed plan"}, "quote": {"price": 1}}
    asked = [q for q in QUESTIONS if ai.flavour_for(1, q)]
    assert asked
    _, meta = ai.build_chat_request([{"role": "user", "content": asked[0]}], context=ctx)
    assert meta["humour"] is True


def test_only_the_neutral_analyst_gets_it():
    q = next(q for q in QUESTIONS if ai.flavour_for(1, q))
    assert ai.flavour_for(1, q, "neutral") == ai.FLAVOUR_PROMPT
    for lens in ("longterm", "stoic", "quant", "skeptic", "no-such-lens"):
        assert ai.flavour_for(1, q, lens) == "", lens


@pytest.mark.parametrize("text", [
    "I'm down 40% on my calls, what now", "I lost a lot on NVDA this week",
    "worried about my puts into earnings", "got a margin call, what do I do",
    "deep analysis on GOOGL puts", "full bear case on AMD", "give me a detailed breakdown"])
def test_never_when_the_question_is_about_a_loss_or_asks_for_the_long_form(text):
    assert all(ai.flavour_for(n, text) == "" for n in range(1, 40))


def test_the_block_borrows_the_tone_and_keeps_the_limits():
    for phrase in ("tease the trade, the market or yourself", "never a joke instead of a number",
                   "never at the reader's expense as a person",
                   "no slurs or their stand-ins (\"regard\")",
                   "no jokes about anybody's partner, job, intelligence or money",
                   "no calling anybody poor, dumb or a loser",
                   "never a rocket, a fire or an emoji", "no forced slang",
                   "a joke is not a finding", "no \"i like the play\"", "no \"i'd buy these\"",
                   "no \"ride it\"", "no \"swing those calls\"", "no \"take the profit\"",
                   "the caveat stays one clause", "if the reader is down on a position",
                   "delta is a rough guide to the odds"):
        assert phrase in FLAVOUR, phrase
    assert "—" not in ai.FLAVOUR_PROMPT
    assert "smart money" in FLAVOUR and "volume and open interest" in FLAVOUR


def test_it_rides_after_the_cached_prefix_and_leaves_the_base_prompt_alone():
    src = open(ai.__file__, encoding="utf-8").read()
    body = src[src.index("    flavour_prompt = flavour_for("):]
    body = body[:body.index('        "messages": messages,')]
    assert '"text": SYSTEM_PROMPT + FORMAT_PROMPT,\n             "cache_control": {"type": "ephemeral"}}' in body
    assert body.index("SYSTEM_PROMPT + FORMAT_PROMPT") < body.index("level_prompt") < body.index("persona_prompt")
    assert body.index("persona_prompt}] if persona_prompt") < body.index("flavour_prompt}] if flavour_prompt")
    assert "FLAVOUR_PROMPT" not in ai.SYSTEM_PROMPT and "looser voice" not in flat(ai.SYSTEM_PROMPT)
