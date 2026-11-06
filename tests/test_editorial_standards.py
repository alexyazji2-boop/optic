"""Optic's editorial standards, held by tests (Phase 12, 2026-11-02).

Three things: the copy gate (no `error` finding from `tests/editorial/rules.py` in v2 or server copy, unless
`tests/editorial/allow.txt` gives a reason), proof that the rules catch what they name and pass good writing (the
directive's own before-and-after pairs), and the contract that every model request carries the house writing rules
(`app/editorial.py`) with the advice policy after them. Classic is reported but not gated: the owner's rule is that
Classic is left as it is unless asked. Legal text is reported for counsel and never gated.

The full inventory is `.venv/bin/python -m tests.editorial.review inventory`; the reviewer for a branch's new copy is
`... review diff`.
"""
from __future__ import annotations

import re
import types

import pytest

from app import ai, ai_policy, editorial
from tests.editorial import extract as X
from tests.editorial import review as REV
from tests.editorial import rules as R


@pytest.fixture(scope="module")
def inventory():
    texts, counts = X.inventory()
    REV.review(texts)
    return texts, counts


# ------------------------------------------------------------------------------------------ the gate
def test_no_error_finding_in_v2_or_server_copy(inventory):
    texts, _ = inventory
    allow = REV.allowed()
    bad = ["{}:{} {} \"{}\": {}".format(t.file, t.line, f["rule"], f["match"], f["suggestion"])
           for t in texts if REV.zone(t) != "classic" and t.kind in ("client", "server")
           for f in t.findings if f["severity"] == "error" and not REV.is_allowed(t, f, allow)]
    assert not bad, "editorial errors (fix the copy, or add a reasoned line to tests/editorial/allow.txt):\n" + "\n".join(bad)


def test_every_allow_line_still_matches_something(inventory):
    """An allowance for copy that has since changed is a hole: it would wave through the next text that happens to
    contain its words."""
    texts, _ = inventory
    stale = [a for a in REV.allowed()
             if not any(t.file == a[0] and a[2] in t.text and any(f["rule"] == a[1] for f in t.findings) for t in texts)]
    assert not stale, stale


def test_the_inventory_reads_the_whole_terminal(inventory):
    texts, counts = inventory
    kinds = X.by_kind(texts)
    assert counts["client_files"] >= 110 and counts["server_files"] >= 150
    assert kinds["client"] > 10000 and kinds["server"] > 3000 and kinds["legal"] > 50 and kinds["prompt"] >= 15
    pages = {t.file for t in texts if t.file.startswith("static/v2/js/pages/")}
    missing = [p.name for p in (X.V2 / "pages").glob("*.js") if "static/v2/js/pages/" + p.name not in pages]
    assert not missing, "a page contributed no text at all: the extractor lost its place in " + ", ".join(missing)
    # what a template cut at a `${...}` leaves at its ends is markup, never a text of its own
    leaks = [t.text for t in texts if t.kind == "client" and re.search(r'\b(?:class|href|id|style)="', t.text)]
    assert len(leaks) < 0.002 * kinds["client"], leaks[:10]
    # every model prompt is traced to its constant
    prompts = {t.symbol for t in texts if t.kind == "prompt"}
    assert {"SYSTEM_PROMPT", "FORMAT_PROMPT", "POLICY_TEXT", "WEEKLY_PROMPT", "DESK_PROMPT"} <= prompts


# ------------------------------------------------------------------------------------------ the rules catch what they name
BAD = [  # the directive's own BAD examples (Part 2.3), and the families it names (Part 1.2)
    ("Optic leverages powerful, cutting-edge AI-driven technology to deliver comprehensive financial market insights, "
     "empowering investors to make more informed and data-driven decisions.", {"F1", "E1"}),
    ("The RSI indicator, which is widely utilized by traders, provides valuable insights into momentum conditions, "
     "helping identify potential overbought or oversold scenarios.", {"E1", "D4"}),
    ("That's a great question! Let's dive into a comprehensive analysis of the various factors.", {"D3"}),
    ("We encountered an unexpected issue while attempting to retrieve the requested information. Please try again at "
     "a later time.", {"X1"}),
    ("It's important to note that margins narrowed.", {"D1"}),
    ("In today's rapidly evolving landscape, rates matter.", {"D2"}),
    ("This highlights the importance of liquidity.", {"D4"}),
    ("In conclusion, the stock rose.", {"J1"}),
    ("A game-changing, unparalleled view of the market.", {"F1"}),
    ("The company, which reported on Tuesday after the close, said that revenue, which analysts had expected to fall, "
     "rose in the quarter, while margins, helped by lower freight costs, widened slightly from a year earlier.", {"A1"}),
    ("The stock rose. The stock fell. The stock closed flat.", {"B1"}),
]
GOOD = [  # the directive's BETTER examples, and ordinary Optic copy that must not trip a rule
    "Research stocks, follow market data, and ask Milo questions in one terminal.",
    "RSI measures recent price momentum. Readings above 70 are commonly described as overbought, while readings "
    "below 30 are considered oversold.",
    "Revenue increased over the reported period, while profit margins narrowed.",
    "Three factors explain the recent move.",
    "Couldn't load market data. Try again.",
    "AAPL, MSFT, NVDA, AMZN, META and GOOGL make up about a third of the index.",
    "A leveraged ETF resets daily, so over a month it can return far less than twice the index.",
    "Capacity utilization rose to 78.2% in September.",
    "Prices as of 10:05 AM EDT. Delayed about 15 minutes.",
]


@pytest.mark.parametrize("text,rules", BAD)
def test_a_rule_catches_the_pattern_it_names(text, rules):
    got = {f["rule"] for f in R.check(text, "client")}
    assert rules <= got, (rules - got, got)


@pytest.mark.parametrize("text", GOOD)
def test_good_writing_passes_without_an_error_or_a_warning(text):
    got = [f for f in R.check(text, "client") if f["severity"] in ("error", "warn")]
    assert not got, got


def test_prompts_are_not_held_to_the_phrase_rules():
    """A prompt has to be able to say what not to write."""
    assert R.check('No "great question", never "cutting-edge".', "prompt") == []


def test_the_diff_reviewer_sees_only_new_copy(monkeypatch):
    before = "const a = html`<p>Prices as of 10:05.</p>`;\n"
    after = before + "const b = html`<p>Our cutting-edge engine delivers valuable insights.</p>`;\n"
    old = {t.text for t in REV._texts_of("static/v2/js/pages/x.js", before)}
    new = [t for t in REV._texts_of("static/v2/js/pages/x.js", after) if t.text not in old]
    assert [t.text for t in new] == ["Our cutting-edge engine delivers valuable insights."]
    assert {f["rule"] for f in R.check(new[0].text, "client")} >= {"F1", "D4"}


# ------------------------------------------------------------------------------------------ every model request carries the rules
def test_writers_carry_the_rules_with_the_policy_after_them(monkeypatch):
    sent = []

    def create(**kw):
        sent.append(kw)
        return types.SimpleNamespace(model="m", stop_reason="end_turn", usage=None,
                                     content=[types.SimpleNamespace(type="text", text="Rates fell.")])
    client = types.SimpleNamespace(messages=types.SimpleNamespace(create=create))
    monkeypatch.setattr(ai.ai_store, "record", lambda *a, **k: 1)
    ai._ask(client, "weekly", model="m", max_tokens=10, system=[{"type": "text", "text": "Write the note."}],
            messages=[{"role": "user", "content": "x"}])
    texts = [b["text"] for b in sent[0]["system"]]
    assert texts[0] == "Write the note."
    assert texts.index(editorial.WRITING_RULES) < texts.index(ai_policy.POLICY_TEXT), "the policy must read last"
    # a string system prompt gets both too, once each
    ai._ask(client, "scan", model="m", max_tokens=10, system="Read the filters.", messages=[{"role": "user", "content": "x"}])
    s = sent[1]["system"]
    assert s.count(editorial.WRITING_RULES) == 1 and s.count(ai_policy.POLICY_TEXT) == 1
    assert s.index(editorial.WRITING_RULES) < s.index(ai_policy.POLICY_TEXT)


def test_milos_chat_and_deep_research_carry_the_rules_in_the_cached_prefix():
    kw, _ = ai.build_chat_request([{"role": "user", "content": "How is NVDA doing?"}])
    first = kw["system"][0]["text"]
    assert editorial.WRITING_RULES in first and first.index(editorial.WRITING_RULES) < first.index(ai_policy.POLICY_TEXT)
    src = open(ai.__file__, encoding="utf-8").read()
    dr = src[src.index("async def deep_research("):]
    assert 'RESEARCH_PROMPT + "\\n\\n" + editorial.WRITING_RULES + "\\n\\n" + ai_policy.POLICY_TEXT' in dr


def test_the_rules_keep_what_shorter_writing_must_not_lose():
    """Part 3.4: the guidance must not suppress uncertainty, sources or legal safeguards."""
    r = " ".join(editorial.WRITING_RULES.split())
    assert "never outrank the advice policy" in r
    assert "date and source" in r and "every limit that changes the answer" in r
    assert "an inference is labelled as one" in r


def test_no_prompt_invites_the_patterns_the_rules_remove():
    names = [n for n in dir(ai) if n.endswith("_PROMPT") and isinstance(getattr(ai, n), str)]
    assert len(names) >= 13
    for n in names:
        text = getattr(ai, n)
        assert "llipses are fine" not in text and "llipses for pacing" not in text, n
        assert "Woohoo" not in text and "used ONCE" not in text, n
        assert "**Bottom line**" not in text or "needs no **Bottom line** label" in text, n


# ------------------------------------------------------------------------------------------ the level's inline definitions
def test_an_inline_definition_never_splits_a_noun_phrase(tmp_path):
    """New to Markets showed "No consensus (the average of what analysts forecast) estimates" on the Desk: the
    definition went in after the first word of a two-word term. It now goes in only where the phrase ends."""
    from tests.test_v2_p3 import _run
    from tests.test_frontend_v2_stage0 import V2
    got = _run(tmp_path, f"""
      const G = await import('{(V2 / "js/ui/glossmark.js").as_posix()}');
      print(JSON.stringify([' estimates', ' exposure', '-based', "'s margin", ' is high', ' of 30', ', and', '', '.'].map(G.endsPhrase)));
    """)
    assert got == [False, False, False, False, True, True, True, True, True]


def test_an_inline_definition_has_one_level_of_parentheses_and_keeps_an_acronyms_capitals(tmp_path):
    """New to Markets read "gamma (how fast an option's directional exposure (its delta (how much ...)) changes" and
    "Reported EPS (earnings Per Share)" (the copy editor's findings 42 and 43, Phase 12)."""
    from tests.test_v2_p3 import _run
    from tests.test_frontend_v2_stage0 import V2
    got = _run(tmp_path, f"""
      const G = await import('{(V2 / "js/ui/glossmark.js").as_posix()}');
      print(JSON.stringify({{ gamma: G.gloss('gamma'), eps: G.gloss('eps'), consensus: G.gloss('consensus') }}));
    """)
    assert got["gamma"] == "how fast an option's directional exposure, its delta, changes as the stock price moves"
    assert got["eps"] == "Earnings Per Share" and got["consensus"] == "the average of what analysts forecast"
    src = (V2 / "js/ui/glossmark.js").read_text()
    assert "'.term-inline'].join(', ')" in src, "a definition shown inline is never marked again"
    assert "const NO_INLINE = 'table, dl, .kv, .rd .k';" in src
