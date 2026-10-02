"""Pulse ends every answer with follow-ups drawn from the question, as buttons.

Asked for as "make sure that pulse asks follow ups as well based on the
prompt". The format rules asked for follow-ups only on a long answer, a short
factual one was told to "ignore all of the above", and the lines it did write
("→ ...") rendered as plain text for the reader to retype.

Now the prompt asks for two or three on every reply but a greeting or a thank-you,
built from the question and the answer and written as the reader's own
question; and the client lifts the trailing "→ " lines out of the bubble into
the Home page's question rows, which put their words in the message box.

Checked in a browser: a reply ending in three "→" lines showed the prose, then
three rows; pressing the first put "What would make the 6,180 flip point fail?"
in the box; a streamed reply flushed twice kept one set of rows; an arrow
mid-sentence stayed where it was.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from app import ai

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
CSS = (ROOT / "static/styles.css").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
FORMAT = " ".join(ai.FORMAT_PROMPT.lower().split())


def _fn(name):
    at = APP.index("function %s(" % name)
    return APP[at:APP.index("\n}\n", at) + 3]


def _split(text):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    out = subprocess.run([exe, "-e", _fn("splitFollowUps") + "print('RESULT:' + JSON.stringify(splitFollowUps(%s)));"
                          % json.dumps(text)], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    assert "RESULT:" in out.stdout, (out.stdout + out.stderr)[-1500:]
    return json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])


# ------------------------------------------------------------- the prompt

def test_every_reply_ends_with_follow_ups_a_short_one_included():
    assert "## follow-ups on every answer" in FORMAT
    assert "end every reply with two or three follow-ups, one per line, each starting with `→ `" in FORMAT
    assert "the follow-ups below still come after it" in FORMAT, "a one-line answer gets them too"
    assert "ignore all of the above" not in FORMAT
    assert "leave them out only when the message is a greeting or a thank-you" in FORMAT


def test_they_come_from_the_question_and_are_the_readers_to_send():
    for phrase in ("build them from the question just asked and the answer you gave",
                   "could be pasted under any answer is not one",
                   "write each as the reader's own question",
                   "would you like me to check the chain?",
                   "words they never said",
                   "only suggest what this terminal can do",
                   "cannot set a price alert", "cannot send email", "cannot route an order"):
        assert phrase in FORMAT, phrase
    assert "—" not in ai.FORMAT_PROMPT


# ------------------------------------------------------------- the client

def test_trailing_arrow_lines_are_the_follow_ups_and_the_rest_is_the_answer():
    out = _split("Answer here -> with an arrow.\n\nMore.\n\n→ First?\n→ Second?\n-> Third?\n")
    assert out["ups"] == ["First?", "Second?", "Third?"]
    assert out["body"] == "Answer here -> with an arrow.\n\nMore."


def test_no_trailing_arrows_leaves_the_text_alone_and_only_the_end_counts():
    text = "One.\n→ Not a follow-up\nTwo, and it ends here."
    assert _split(text) == {"body": text, "ups": []}
    assert _split("") == {"body": "", "ups": []}
    mid = "Margins went 41% \u2192 44% over the year."
    assert _split(mid) == {"body": mid, "ups": []}, "an arrow inside a line is not a follow-up"
    assert _split("→ Only this?") == {"body": "", "ups": ["Only this?"]}
    assert len(_split("x\n" + "\n".join("→ q%d?" % i for i in range(9)))["ups"]) == 4, (
        "four rows at most")


def test_the_rows_are_the_home_pages_and_press_into_the_box():
    rows = _fn("followUpsHTML")
    assert 'class="cc-q" data-ask-text="${' in rows and "host.className = 'pulse-ups'" in rows
    assert "const askText = evt.target.closest('[data-ask-text]');\n  if (askText) { draftPulse(askText.dataset.askText); }" in APP
    assert ".msg .pulse-ups { display: flex; flex-direction: column;" in CSS


def test_a_reply_is_painted_with_its_rows_from_both_paths_and_never_twice():
    paint = _fn("paintReply")
    assert "wrap.querySelectorAll(':scope > .pulse-ups').forEach((n) => n.remove());" in paint
    assert "bubble.insertAdjacentElement('afterend', rows)" in paint
    add = _fn("addMsg")
    assert "if (role === 'assistant') paintReply(bubbleEl, text || '');" in add
    flush = APP[APP.index("    flush() {"):]
    flush = flush[:flush.index("    text() { return target; },")]
    assert "splitFollowUps(target)" in flush
    assert "wrap.querySelectorAll(':scope > .pulse-ups').forEach((n) => n.remove());" in flush
