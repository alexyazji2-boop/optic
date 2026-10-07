"""Every button that asks Pulse something puts it in the box, and sends nothing.

Reported with Explain chart's question already sent and Pulse "thinking":
"whenever this button is clicked, it should put the prompted text into the
text box, not automatically send it to pulse incase the user wants to make any
edits. fix this issue across all ask pulse buttons for the entire terminal".

They had sent on the press since "whenever i press explain chart, there is no
explanation that is loaded into pulse". Every way of asking goes through one
function, draftPulse, which opens the panel the way the Pulse button does and
leaves the question in the box with the cursor at its end: Explain chart and
the chart's own asks, the topic buttons, the home page's questions and the
follow-ups beside a symbol, the starter cards, the suggestions over the box, a
saved question asked again, and a question typed into the palette. A press
spends nothing; Send does.
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
var sent = [], toggles = 0, allowances = 0;
var chatState = { busy: false };
function sendChat(text) { sent.push(text); }
function wsOnChatToggle() { toggles++; }
function loadAllowance() { allowances++; }
// Pulse open. The shut case, where a press goes to the reason instead, is
// tests/test_pulse_unavailable.py's.
function pulseBlockedReason() { return null; }
var classes = new Set();
var document = { body: { classList: { add: function (c) { classes.add(c); } } } };
function Event(type) { this.type = type; }
var box = { value: 'half a question', disabled: false, focused: false, events: 0, sel: null,
  focus: function () { this.focused = true; },
  setSelectionRange: function (a, b) { this.sel = [a, b]; },
  dispatchEvent: function () { this.events++; } };
function $(sel) { return sel === '#chat-input' ? box : null; }
"""


def _run(scenario):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = (HARNESS + "\n".join(_fn(n) for n in ("openPulseWithText", "openPulse", "draftPulse"))
           + "\n" + scenario + "\nprint('TEST_OK');")
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=30)
    assert "TEST_OK" in out.stdout, out.stdout + out.stderr


def test_a_press_puts_the_question_in_the_box_and_sends_nothing():
    _run("""
      draftPulse('Read my SPY chart');
      assert(sent.length === 0, 'nothing sent: ' + sent);
      assert(box.value === 'Read my SPY chart', 'in the box: ' + box.value);
      assert(box.focused && box.sel[0] === 17 && box.sel[1] === 17, 'cursor at the end, ready to edit');
      assert(box.events === 1, 'the box is told, so it grows to fit');
      assert(classes.has('chat-open'), 'the panel opened');
      assert(toggles === 1 && allowances === 1, 'opened the way the Pulse button opens it');
    """)


def test_while_an_answer_arrives_it_still_only_fills_the_box():
    _run("""
      chatState.busy = true;
      draftPulse('Explain vanna');
      assert(sent.length === 0 && box.value === 'Explain vanna', 'kept, ready to send');
    """)


def test_an_empty_prompt_asks_nothing():
    _run("""
      draftPulse('');
      assert(sent.length === 0 && !classes.has('chat-open') && box.value === 'half a question',
             'nothing to ask, and the box is left alone');
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


def test_every_button_that_asks_only_fills_the_box():
    handler = APP[APP.index("const explain = evt.target.closest('[data-explain-chart]');"):][:500]
    assert "draftPulse(explainChartPrompt(explain.dataset.explainChart));" in handler
    assert "draftPulse(chartPulsePrompt(askChart.dataset.askChart));" in handler
    topic = _fn("openPulseWith")
    assert topic.rstrip().endswith("draftPulse(text);\n}")
    ask_text = APP[APP.index("const askText = evt.target.closest('[data-ask-text]');"):][:120]
    assert "draftPulse(askText.dataset.askText)" in ask_text
    starter = APP[APP.index("const starter = evt.target.closest('.pulse-card');"):][:120]
    assert "draftPulse(starter.dataset.q);" in starter
    reask = APP[APP.index("const open = evt.target.closest('[data-research-open]');"):][:700]
    assert "draftPulse(row.question || '');" in reask
    assert "run: () => { closePalette(); draftPulse(r.question || ''); }," in APP
    assert "run: () => { closePalette(); draftPulse(q); }," in APP
    # The follow-ups and the research modes share one handler, and it drafts.
    handler = _fn("onPulseSuggestion")
    assert "draftPulse(btn.dataset.q);" in handler
    assert "sendChat" not in handler and "runResearch" not in handler
    assert "$('#chat-suggest').addEventListener('click', onPulseSuggestion);" in APP
    assert "$('#pulse-modes').addEventListener('click', onPulseSuggestion);" in APP


def test_only_send_and_deep_research_send():
    """No button but the panel's own Send sends a question: the old sending
    function is gone, and sendChat is called from nowhere else."""
    assert "askPulseNow" not in CODE
    calls = [m.start() for m in re.finditer(r"\bsendChat\(", CODE)]
    defined = CODE.index("async function sendChat(") + len("async function ")
    send = CODE[CODE.index("$('#chat-send').addEventListener('click'"):][:200]
    assert [c for c in calls if c != defined] == [CODE.index("sendChat(text);",
                                                             CODE.index("$('#chat-send')"))]
    assert "sendChat(text);" in send
