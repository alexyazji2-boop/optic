"""Live audit M1 (2026-11-11): Milo brought a reader's linked brokerage holdings into answers that did not ask for them.

On the public build, signed in with linked accounts and asking from the AAPL Overview, a tax question listed every
linked holding, a legal question checked the same accounts, and a portfolio framed "not my real holdings" was compared
against "your real book". All three matched the first-person rule of 2026-10-27 ("my Apple shares", "my real
holdings"), which attaches the holdings block and offers the get_my_portfolio tool.

What is pinned here, with no model call:
- which questions are about the reader's own portfolio (app/portfolio_intent.py), on the audit's words and around them;
- the server's line whenever the holdings reach Milo, from the CONTEXT block or the tool, and none otherwise;
- the prompt's rules for using them (only the part asked about; never for a made-up or someone else's portfolio);
- the line in v2's panel, kept with a saved or reopened conversation, and in Classic's.
The chat route itself is tested with a linked sandbox reader in tests/test_brokerage.py (the audit_m1 tests).
"""
from __future__ import annotations

import asyncio
import json
import types
from pathlib import Path

import pytest

from app import ai, ai_store, library, milo_tools, portfolio_intent as pi
from tests.test_frontend_v2_stage0 import V2, _run

ROOT = Path(__file__).resolve().parents[1]

# ------------------------------------------------------------------------------------------- which questions
# The audit's three, word for word (evidence/milo/answers-all.json: A3, A4, T6)
AUDIT_TAX = "When should I sell my Apple shares so I pay less tax?"
AUDIT_LEGAL = "Is it legal for me to avoid capital gains tax by gifting my Apple shares to my child?"
AUDIT_MADE_UP = ("Hypothetically, take a made-up portfolio of 50% AAPL, 30% MSFT and 20% cash (not my real holdings). "
                 "What are its main risks?")

# The portfolio in question is not the reader's real one, or they said not to use it: nothing, from any page or thread
EXCLUDED = [
    AUDIT_MADE_UP,
    "Take a made-up portfolio of 50% AAPL (not my real one). What are its main risks?",
    "Imagine a hypothetical portfolio of equal parts AAPL and MSFT. How volatile would it be?",
    "What are the risks of a portfolio that's 60% SPY and 40% TLT?",
    "Pretend my portfolio were 100% NVDA. What are the risks?",
    "Imagine my portfolio is all tech. What happens in a selloff?",
    "How would my paper portfolio do in a crash?",
    "My dad's portfolio is 80% bonds. Is that too safe for him?",
    "Is my wife’s Roth account too concentrated?",
    "Don't look at my accounts, just explain wash sales.",
    "DON’T use my portfolio, just explain beta.",
    "Ignore my holdings and tell me how a 60/40 portfolio behaves in a recession.",
    "Leave my portfolio out of this: what is a reasonable bond share for a 30-year-old?",
    "Without looking at my portfolio, how should anyone think about concentration?",
    "Compare this made-up portfolio (not my real holdings) with QQQ.",
]
# A tax or legal question that names the reader's shares only as its premise: answered from general rules
MENTIONED = [
    AUDIT_TAX,
    AUDIT_LEGAL,
    "Can I deduct my losses on Tesla?",
    "Are my dividends taxed as income?",
    "How are my options taxed?",
    "If I hold my Apple shares for a year, is the tax lower?",
    "How is my Roth account taxed?",
    "Is it legal to gift shares from my brokerage account to my son?",
    "How does the new tax law affect me?",
]
# About the reader's own portfolio or holdings: the 2026-10-27 set (tests/test_brokerage.py ABOUT_THEM) and more
ASKED = [
    "Where is my portfolio concentrated?", "my portfolio?", "Which earnings affect my holdings?",
    "Which earnings affect me this week?", "How exposed am I to technology?", "What do I own in energy?",
    "Do I own anything that reports this week?", "I own 40 AAPL, what should I watch?",
    "How did my tech exposure change since the last sync?", "Is my Roth account diversified?",
    "How is my portfolio doing today?", "Why did my portfolio move today?", "How are my investments doing?",
    "How many Apple shares do I own?", "Am I too concentrated in tech?", "How are my Apple shares doing today?",
    "Should I sell my Apple shares before earnings?", "What's in my account?", "How is my brokerage account doing?",
    "Stress test my portfolio against a 2008-style crash.",
    # a scenario on the real book is about it, hypothetical or not
    "Hypothetically, how would a 20% drop in NVDA hit my portfolio?",
    "If I sold my Apple shares, how would my exposure change?",
    "If my portfolio were down 20%, how much would I have lost?",
    # a tax or legal question that asks about the holdings themselves
    "Which of my holdings have losses I could harvest for tax?",
    "Do I have any wash-sale risk in my accounts?",
    "How can I make my portfolio more tax-efficient?",
    "When should I sell my Apple shares so I pay less tax? Check my linked accounts.",
    # a made-up portfolio set against theirs at their request
    "Compare a made-up portfolio of 50% AAPL and 50% cash with my real holdings.",
    # a bare "not my holdings" is a question about them
    "Which QQQ names are not my holdings?",
]
# Not about the reader's holdings: the 2026-10-27 set (tests/test_brokerage.py NOT_ABOUT_THEM), the audit's other
# advice questions, and two the old rule matched ("since the last earnings report", the Optic account's settings)
NONE = [
    "Why does MSFT lead the position setup, and how far should I trust that?",
    "What's NVDA's exposure to China?", "Is AAPL too concentrated in iPhone revenue?",
    "How is the allocation of capex changing at MSFT?", "What are QQQ's top holdings?",
    "Should I hold a position through earnings?",
    "Microsoft develops a portfolio of technology solutions. What is its biggest segment?",
    "Explain to my dad how options work.",
    "Should I buy Apple stock today?", "I have $10,000. How many Apple shares should I buy, and when?",
    "Give me your price target for Apple next month and guarantee it.",
    "If I bought AAPL in 2015, how much would I have now?",
    "Suppose I hold 100 shares of AAPL. What happens at a 10% drop?",
    "How has NVDA moved since the last earnings report?",
    "How do I delete my account?", "How do I change the email on my account?",
    "What is the tax treatment of options?", "What is a covered call?", "",
]


@pytest.mark.parametrize("kind,questions", [(pi.EXCLUDED, EXCLUDED), (pi.MENTIONED, MENTIONED),
                                            (pi.ASKED, ASKED), (pi.NONE, NONE)], ids=["excluded", "mentioned",
                                                                                     "asked", "none"])
def test_each_question_is_read_as_about_their_portfolio_or_not(kind, questions):
    wrong = {q: pi.classify(q) for q in questions if pi.classify(q) != kind}
    assert not wrong, "read otherwise than {}: {}".format(kind, wrong)


def test_the_audit_questions_are_not_about_their_portfolio_and_a_genuine_one_is():
    assert pi.classify(AUDIT_TAX) == pi.classify(AUDIT_LEGAL) == pi.MENTIONED
    assert pi.classify(AUDIT_MADE_UP) == pi.EXCLUDED
    assert not any(pi.asks_about_own(q) for q in (AUDIT_TAX, AUDIT_LEGAL, AUDIT_MADE_UP))
    assert pi.asks_about_own("Where is my portfolio concentrated?")


def test_the_routes_rule_uses_the_same_reading():
    import app.main as m
    for q in ASKED:
        assert m._asks_about_own_portfolio({"role": "user", "content": q}), q
    for q in EXCLUDED + MENTIONED + NONE:
        assert not m._asks_about_own_portfolio({"role": "user", "content": q}), q
    assert not m._asks_about_own_portfolio(None) and not m._asks_about_own_portfolio("my portfolio")


@pytest.mark.parametrize("history,view,reach", [
    ([AUDIT_TAX], "overview", "none"),
    ([AUDIT_LEGAL], "overview", "none"),
    ([AUDIT_MADE_UP], "overview", "none"),
    (["Where is my portfolio concentrated?"], "overview", "attach"),
    (["Where is my portfolio concentrated?", AUDIT_MADE_UP], "overview", "none"),
    (["Where is my portfolio concentrated?", AUDIT_TAX], "overview", "none"),
    (["Where is my portfolio concentrated?", "And which of those report this week?"], "overview", "tool"),
    ([AUDIT_MADE_UP, "And what is its biggest risk?"], "overview", "none"),
    (["What deserves more research?"], "brokerage", "attach"),
    ([AUDIT_TAX], "brokerage", "attach"),
    ([AUDIT_MADE_UP], "brokerage", "none"),
    ([], "brokerage", "attach"),
    ([], "overview", "none"),
])
def test_how_far_one_answer_reaches_into_the_linked_accounts(history, view, reach):
    import app.main as m
    turns = []
    for q in history:
        turns += [{"role": "user", "content": q}, {"role": "assistant", "content": "An answer."}]
    turns = turns[:-1]
    assert m._linked_portfolio_reach(turns, {"focus": {"view": view, "scope": "auto"}}) == reach
    # Milo set to the market only, or to no context, never reaches them
    for scope in ("market", "none"):
        assert m._linked_portfolio_reach(turns, {"focus": {"view": view, "scope": scope}}) == "none"
    # and a turn that is not a dict is skipped, not read (BUG-189)
    assert m._linked_portfolio_reach(["my portfolio"] + turns, {"focus": {"view": view, "scope": "auto"}}) == reach


# ------------------------------------------------------------------------------------------- the server's line
class _Stream:
    def __init__(self, events, final):
        self.events, self.final = events, final

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def __aiter__(self):
        async def gen():
            for e in self.events:
                yield e
        return gen()

    async def get_final_message(self):
        return self.final


def _final(stop, blocks):
    return types.SimpleNamespace(model=ai.PULSE_MODEL, stop_reason=stop, content=blocks,
                                 usage=types.SimpleNamespace(input_tokens=1, output_tokens=1, cache_read_input_tokens=0))


def _stream_chat(monkeypatch, context, rounds, toolbox=None):
    """Milo's answer stream with the model stood in: each round is text, or ("tool", part) for get_my_portfolio."""
    sent = []

    def stream(**kw):
        sent.append(kw)
        r = rounds[min(len(sent), len(rounds)) - 1]
        if isinstance(r, tuple):
            use = types.SimpleNamespace(type="tool_use", id="t%d" % len(sent), name="get_my_portfolio", input={"part": r[1]})
            return _Stream([], _final("tool_use", [use]))
        ev = types.SimpleNamespace(type="content_block_delta", delta=types.SimpleNamespace(type="text_delta", text=r))
        return _Stream([ev], _final("end_turn", [types.SimpleNamespace(type="text", text=r)]))
    monkeypatch.setattr(ai, "_client", lambda: types.SimpleNamespace(beta=types.SimpleNamespace(
        messages=types.SimpleNamespace(stream=stream))))
    monkeypatch.setattr(ai_store, "record", lambda *a, **k: None)

    async def go():
        return [e async for e in ai.stream_chat([{"role": "user", "content": "How is my portfolio doing?"}],
                                                context=context, toolbox=toolbox)]
    out = []
    for e in asyncio.run(go()):
        head, _, data = e.partition("\ndata: ")
        out.append((head.replace("event: ", "").strip(), json.loads(data.strip() or "{}")))
    return out


def _lines(events):
    return [p for k, p in events if k == "notice" and p.get("kind") == "linked_accounts"]


LINKED = {"status": "ok", "signed_in": True, "linked": True, "part": "summary", "source": "The reader's linked brokerage",
          "data": {"facts": {"holdings": [{"symbol": "VOO", "quantity": 3}]}}}


def test_the_line_says_what_the_audit_asked_for_in_the_panels_voice():
    assert ai.LINKED_ACCOUNTS_LINE == "Milo checked your linked accounts for this answer, as of their last sync."
    assert ai.LINKED_ACCOUNTS_NOTICE == {"kind": "linked_accounts", "text": ai.LINKED_ACCOUNTS_LINE}
    assert "—" not in ai.LINKED_ACCOUNTS_LINE                    # no em dash in anything a reader sees


def test_holdings_in_the_context_get_the_line_before_any_text(monkeypatch):
    events = _stream_chat(monkeypatch, {"brokerage_portfolio": {"facts": {"holdings": [{"symbol": "VOO"}]}},
                                        "brokerage_linked": True}, ["Your largest position is VOO."])
    kinds = [k for k, _ in events]
    assert _lines(events) == [ai.LINKED_ACCOUNTS_NOTICE]
    assert kinds.index("notice") < kinds.index("delta")


@pytest.mark.parametrize("context", [None, {}, {"brokerage_linked": True}, {"brokerage_portfolio": None},
                                     {"brokerage_portfolio": {}}])
def test_no_line_when_no_holdings_were_attached(monkeypatch, context):
    assert _lines(_stream_chat(monkeypatch, context, ["Apple reports on Jan 28."])) == []


def test_the_tool_reading_them_gets_the_line_once_and_the_block_and_tool_together_once(monkeypatch):
    calls = []
    box = milo_tools.Toolbox(runners={"get_my_portfolio": lambda part: calls.append(part) or dict(LINKED, part=part)})
    events = _stream_chat(monkeypatch, {"brokerage_linked": True},
                          [("tool", "summary"), ("tool", "events"), ("tool", "summary"), "Two report this week."], box)
    assert calls == ["summary", "events"] and _lines(events) == [ai.LINKED_ACCOUNTS_NOTICE]
    kinds = [k for k, _ in events]
    reading = events.index(("status", {"state": "Reading your linked portfolio (summary)"}))
    assert reading < kinds.index("notice") < kinds.index("delta"), "when the tool returned them, before any text"
    box = milo_tools.Toolbox(runners={"get_my_portfolio": lambda part: dict(LINKED, part=part)})
    events = _stream_chat(monkeypatch, {"brokerage_portfolio": {"facts": {}}, "brokerage_linked": True},
                          [("tool", "performance"), "Up 3% since the last sync."], box)
    assert _lines(events) == [ai.LINKED_ACCOUNTS_NOTICE]


@pytest.mark.parametrize("result", [
    {"status": "ok", "signed_in": False, "linked": False, "note": "The reader is not signed in."},
    {"status": "ok", "signed_in": True, "linked": False, "note": "No brokerage is linked to this account."},
    {"status": "unavailable", "error": "The accounts database could not be read just now."},
])
def test_no_line_when_the_tool_read_no_holdings(monkeypatch, result):
    box = milo_tools.Toolbox(runners={"get_my_portfolio": lambda part: dict(result)})
    events = _stream_chat(monkeypatch, {}, [("tool", "summary"), "Nothing is linked."], box)
    assert ("status", {"state": "Reading your linked portfolio (summary)"}) in events, "the tool ran"
    assert _lines(events) == []


def test_only_the_portfolio_tool_with_their_data_counts():
    body = json.dumps(dict(LINKED, meta={}))
    assert ai.read_linked_accounts("get_my_portfolio", body)
    assert not ai.read_linked_accounts("get_my_watchlists", body)
    assert not ai.read_linked_accounts("get_my_portfolio", json.dumps({"status": "ok", "linked": True}))
    assert not ai.read_linked_accounts("get_my_portfolio", "not json")
    assert not ai.read_linked_accounts("get_my_portfolio", json.dumps(["a list"]))
    assert ai.uses_linked_accounts({"brokerage_portfolio": {"facts": {}}})
    assert not ai.uses_linked_accounts({"brokerage_linked": True}) and not ai.uses_linked_accounts(None)


# ------------------------------------------------------------------------------------------- the prompt
def test_milo_is_told_to_use_only_the_part_asked_about_and_never_for_a_portfolio_not_theirs():
    fmt = " ".join(ai.FORMAT_PROMPT.split())
    assert "the panel shows the reader a line above your answer saying you checked their linked accounts" in fmt
    assert ("a question about one company gets that position, or the fact that none is held, never a list of "
            "the others") in fmt
    assert "List or describe their other holdings only when the question asks about the portfolio as a whole" in fmt
    assert ("A question about a made-up, example, paper or someone else's portfolio, or one that says not to use the "
            "reader's own, is about that portfolio alone: never compare it with their linked accounts or mention "
            "them") in fmt
    system = " ".join(ai.SYSTEM_PROMPT.split())
    assert ("Never call it for a made-up, example or someone else's portfolio, or for a tax or legal question that "
            "does not ask about their holdings") in system


# ------------------------------------------------------------------------------------------- the panels
MILO = (V2 / "js/ui/milo.js").read_text()
MILO_JS = (V2 / "js/ui/milo.js").as_posix()
DOM_JS = (V2 / "js/core/dom.js").as_posix()


def test_v2_draws_the_line_above_the_answer_and_escapes_it(tmp_path):
    got = _run(tmp_path, f"""
      const M = await import('{MILO_JS}'), {{ toString }} = await import('{DOM_JS}');
      print(JSON.stringify({{
        line: toString(M.linkedNote({{ linkedLine: 'Milo checked your linked accounts for this answer, as of their last sync.' }})),
        hostile: toString(M.linkedNote({{ linkedLine: '<img src=x onerror=alert(1)>' }})),
        none: toString(M.linkedNote({{}})), empty: toString(M.linkedNote(null)) }}));
    """)
    assert got["line"] == ('<p class="milo-linked" role="note">Milo checked your linked accounts for this answer, '
                           'as of their last sync.</p>')
    assert "<img" not in got["hostile"] and "&lt;img" in got["hostile"]
    assert got["none"] == got["empty"] == ""
    msg = MILO.split("function msgHTML")[1].split("function sourceLists")[0]
    answer = msg.index('<div class="milo-bubble">${raw(body)}</div>')
    assert msg.index("${info.policyLine ?") < msg.index("${linkedNote(info)}") < answer, "above Milo's answer text"


def test_v2_shows_the_line_as_it_arrives_and_keeps_it_with_the_answer():
    handler = MILO[MILO.index("else if (ev === 'notice')"):MILO.index("else if (ev === 'amend')")]
    assert "p.kind === 'linked_accounts' && p.text" in handler and "meta.get(ai).linkedLine = String(p.text)" in handler
    assert "paintLinked(ai)" in handler, "drawn in place while the answer streams"
    persist = MILO[MILO.index("function persist()"):MILO.index("export function conversationSpec")]
    assert "if (inf.linkedLine) o.linked = String(inf.linkedLine).slice(0, 200);" in persist
    reopen = MILO[MILO.index("if ((b = t('[data-v2-milo-open]')))"):MILO.index("if ((b = t('[data-v2-milo-del]')))")]
    assert "linkedLine: saved.linked || ''" in reopen


def test_v2_a_saved_conversation_keeps_the_line_through_the_library(tmp_path):
    got = _run(tmp_path, f"""
      const M = await import('{MILO_JS}');
      const facts = new Map([[1, {{ symbol: 'AAPL', policyLine: '', level: 'intermediate',
        linkedLine: 'Milo checked your linked accounts for this answer, as of their last sync.',
        context: {{ focus: {{ view_label: 'AAPL Overview', ticker: 'AAPL', captured_at: '2026-11-11T23:08:00Z' }} }} }}]]);
      const spec = M.conversationSpec({{ id: 'c1', messages: [{{ role: 'user', content: 'How is my portfolio doing?' }},
        {{ role: 'assistant', content: 'Up 1.2% today.' }}], lastTicker: 'AAPL' }}, facts, 'AAPL Overview');
      print(JSON.stringify({{ spec }}));
    """)
    saved = got["spec"]["conversation"]["messages"]
    assert saved[1]["linked"] == ai.LINKED_ACCOUNTS_LINE and "linked" not in saved[0]
    kept = library._conversation({"messages": saved, "saved_from": "AAPL Overview"})["messages"]
    assert kept[1]["linked"] == ai.LINKED_ACCOUNTS_LINE, "the server keeps it with the saved answer"
    back = _run(tmp_path, f"""
      const M = await import('{MILO_JS}');
      const r = M.restoreSaved({json.dumps({"kind": "conversation", "tickers": ["AAPL"], "ref": {"conversation": "c1"},
                                             "created_at": "2026-11-11T23:10:00Z", "updated_at": "2026-11-11T23:10:00Z",
                                             "conversation": {"messages": kept}})});
      print(JSON.stringify({{ line: r.facts.get(1).linkedLine }}));
    """)
    assert back["line"] == ai.LINKED_ACCOUNTS_LINE


def test_classic_shows_the_line_above_the_answer_too():
    classic = (ROOT / "static" / "app.js").read_text()
    notice = classic[classic.index("} else if (event === 'notice') {"):classic.index("} else if (event === 'amend') {")]
    assert "payload.kind === 'linked_accounts' && payload.text && !node.querySelector('.msg-linked')" in notice
    assert "<p class=\"msg-assumed msg-linked\" role=\"note\">${esc(payload.text)}</p>" in notice
