"""Every button that asks Pulse something sends it, and an answer comes back.

Reported with HOOD's chart: "whenever i press explain chart, there is no
explanation that is loaded into pulse, fix this and go across the whole
terminal and fix this issue wherever applicable". Explain chart opened the
panel with its prompt typed into the box and stopped there, and so did every
other way of asking: the topic buttons (Explain this desk, the gamma and IV
ones), the home page's questions and the follow-ups beside a symbol, the
starter cards in an empty panel, a saved question asked again, and a question
typed into the palette. The palette's own Ask Pulse opened nothing at all: it
passed an empty prompt to a function that returns on one.

askPulseNow sends, and falls back to typing the question in only where it
cannot go: Pulse unavailable or needing an account, or an answer still
arriving. Checked in a browser: Explain chart on the Charting tab put the
question in the conversation and an answer streaming under it.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
# Code without its comments, for the searches that must not pass on their own
# prose: the comments here quote the calls they replaced.
CODE = re.sub(r"^\s*//.*$", " ", re.sub(r"/\*.*?\*/", " ", APP, flags=re.S), flags=re.M)
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _fn(name):
    return re.search(r"^(?:async )?function %s\([^\n]*\) \{.*?^\}" % name, APP, re.M | re.S).group()


HARNESS = """
function assert(v, m) { if (!v) throw new Error(m); }
var sent = [], toggles = 0, allowances = 0, blocked = null;
var chatState = { busy: false };
function sendChat(text) { sent.push(text); }
function wsOnChatToggle() { toggles++; }
function loadAllowance() { allowances++; }
function pulseBlockedReason() { return blocked; }
var classes = new Set();
var document = { body: { classList: { add: function (c) { classes.add(c); } } } };
function Event(type) { this.type = type; }
var box = { value: 'half a question', disabled: false, focused: false, events: 0,
  focus: function () { this.focused = true; },
  setSelectionRange: function () {}, dispatchEvent: function () { this.events++; } };
function $(sel) { return sel === '#chat-input' ? box : null; }
"""


def _run(scenario):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = (HARNESS + "\n".join(_fn(n) for n in ("openPulseWithText", "openPulse", "askPulseNow"))
           + "\n" + scenario + "\nprint('TEST_OK');")
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=30)
    assert "TEST_OK" in out.stdout, out.stdout + out.stderr


def test_a_press_sends_the_question_and_opens_the_panel():
    _run("""
      askPulseNow('Read my HOOD chart');
      assert(sent.length === 1 && sent[0] === 'Read my HOOD chart', 'sent: ' + sent);
      assert(classes.has('chat-open'), 'the panel opened');
      assert(box.value === '', 'nothing left typed in the box');
      assert(toggles === 1 && allowances === 1, 'opened the way the Pulse button opens it');
    """)


def test_while_an_answer_arrives_the_question_waits_in_the_box():
    _run("""
      chatState.busy = true;
      askPulseNow('Explain vanna');
      assert(sent.length === 0, 'sendChat takes one at a time');
      assert(box.value === 'Explain vanna' && box.focused, 'kept, ready to send');
    """)


def test_where_pulse_cannot_answer_it_opens_on_the_reason_with_the_prompt_kept():
    _run("""
      blocked = { text: 'Pulse needs a free account.' };
      askPulseNow('Explain this desk');
      assert(sent.length === 0, 'nothing sent that would be refused');
      assert(classes.has('chat-open') && box.value === 'Explain this desk', 'open, prompt kept');
      blocked = null; box.disabled = true;
      askPulseNow('Explain gamma');
      assert(sent.length === 0, 'a disabled box is not sent from either');
    """)


def test_an_empty_prompt_asks_nothing():
    _run("""
      askPulseNow('');
      assert(sent.length === 0 && !classes.has('chat-open'), 'nothing to ask');
    """)


def test_the_palettes_ask_pulse_opens_pulse():
    """It passed '' to openPulseWithText, which returns on an empty prompt."""
    _run("""
      openPulseWithText('');
      assert(!classes.has('chat-open'), 'the old call opened nothing');
      openPulse();
      assert(classes.has('chat-open') && box.focused, 'open, and ready to type');
      assert(sent.length === 0, 'and nothing sent');
    """)
    actions = APP[APP.index("const QUICK_ACTIONS = ["):]
    actions = actions[:actions.index("\n];")]
    assert "run: () => openPulse() }," in actions
    assert "openPulseWithText('')" not in CODE


# ------------------------------------------------ every way in goes through it


def test_every_button_that_asks_sends():
    handler = APP[APP.index("const explain = evt.target.closest('[data-explain-chart]');"):][:500]
    assert "askPulseNow(explainChartPrompt(explain.dataset.explainChart));" in handler
    assert "askPulseNow(chartPulsePrompt(askChart.dataset.askChart));" in handler
    # The topic buttons, Explain this desk among them, build their prompt and send it.
    topic = _fn("openPulseWith")
    assert topic.rstrip().endswith("askPulseNow(text);\n}")
    assert "box.value = text;" not in topic
    # The home page's questions, and the follow-ups that use the same attribute.
    ask_text = APP[APP.index("const askText = evt.target.closest('[data-ask-text]');"):][:120]
    assert "askPulseNow(askText.dataset.askText)" in ask_text
    starter = APP[APP.index("const starter = evt.target.closest('.pulse-card');"):][:120]
    assert "askPulseNow(starter.dataset.q);" in starter
    reask = APP[APP.index("const open = evt.target.closest('[data-research-open]');"):][:700]
    assert "askPulseNow(row.question || '');" in reask
    assert "run: () => { closePalette(); askPulseNow(r.question || ''); }," in APP
    assert "run: () => { closePalette(); askPulseNow(q); }," in APP


def test_nothing_else_leaves_a_question_typed_and_unsent():
    """The one caller left is askPulseNow itself, for the case it cannot send."""
    callers = [m.start() for m in re.finditer(r"openPulseWithText\(", CODE)]
    defs = CODE.index("function openPulseWithText(")
    uses = [c for c in callers if c != defs + len("function ")]
    assert len(uses) == 1 and uses[0] > CODE.index("function askPulseNow("), uses
