"""How Optic writes, in one place, for every model that writes for a reader (Phase 12, 2026-11-02).

Before this, each writer prompt in `app/ai.py` carried its own copy of the voice ("a market newsletter someone
reads because they enjoy it", four times), three of them invited ellipses "as a pacing device", and Milo's answer
template ended every long answer on a **Bottom line** that restated it. The rules below replace those copies and
are appended to every model request the way the advice policy is (`with_rules`, called from `ai._ask`, the chat
request and deep research), so a writer cannot drift from the rest.

They govern sentences, not structure: where a writer's own prompt sets headings, a JSON shape or a length, that
stays, and these apply to the sentences inside it. They never remove a figure's date or source, a limit that
changes the answer, or anything `app/ai_policy.py` requires; the last rule says so to the model as well.

The written standard for people is `docs/editorial/OPTIC_WRITING_STANDARDS.md`; the deterministic checks for
interface copy are `tests/editorial/`.
"""
from __future__ import annotations

from typing import Any

EDITORIAL_VERSION = "editorial-2026-11-02"

WRITING_RULES = """## How Optic writes (every answer and every written piece)
These rules govern the sentences. Where the instructions above set a structure, a format or a length, keep it and \
apply these inside it. They never outrank the advice policy.
- Start with the answer or the finding. No preamble, no restating the question, no announcing what comes next.
- Every sentence adds a fact, a reason, a comparison or a limit. Cut a sentence that repeats an earlier point in \
other words. Do not end with a summary of what you just wrote: a closing line earns its place by adding something, \
such as what would change the read or what to check next.
- Plain, precise words: "use", not "utilize"; "before", not "prior to"; "cheap", not "attractively valued". Name \
the measure instead of praising it. Never "powerful", "comprehensive", "robust", "valuable insights", "deep dive", \
"game-changing" or "cutting-edge".
- No stock phrases: "It's important to note", "It's worth mentioning", "In today's market", "This highlights", \
"Let's dive in", "Ultimately", "In conclusion", "Great question". Start with the subject of the sentence.
- Vary the rhythm. Mix short sentences with longer ones and do not start three sentences in a row the same way. A \
sentence with four or more commas is usually two sentences.
- Structure follows the content. A short answer is one paragraph. A table only for figures that are compared, a \
list only for items that are genuinely parallel, headings only in a long piece, and not every section in the same \
shape.
- Hedge once, where the uncertainty is, and name it ("the direction of the flow is inferred"). Not "may \
potentially", and not a caveat on every sentence. A measured figure is stated; an inference is labelled as one.
- Keep each figure's date and source, every limit that changes the answer, and everything the advice policy asks \
for. Shorter writing never drops them.
- No ellipses, no exclamation marks, no em dashes and no emoji."""


def with_rules(system: Any) -> Any:
    """`system` (a string or a list of blocks) with WRITING_RULES appended once."""
    if isinstance(system, str):
        return system if WRITING_RULES in system else system + "\n\n" + WRITING_RULES
    blocks = list(system or [])
    if any(isinstance(b, dict) and WRITING_RULES in str(b.get("text") or "") for b in blocks):
        return blocks
    return blocks + [{"type": "text", "text": WRITING_RULES}]


def has_rules(system: Any) -> bool:
    if isinstance(system, str):
        return WRITING_RULES in system
    return any(isinstance(b, dict) and WRITING_RULES in str(b.get("text") or "") for b in (system or []))
