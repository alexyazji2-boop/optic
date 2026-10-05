"""Pulse, redrawn.

Asked for with a picture of another broker's assistant: "make pulse look like
this". Its ideas, in Optic's colours and words and never its branding: the
reader's question a filled bubble and the answer plain text; a short list of
what Pulse is doing, each step one the server sent and each ticked as the next
begins, folded to "Worked through N steps" once the answer starts; a chart
inside an answer, drawn from the terminal's own bars where Pulse writes
`[[chart SPY 3m]]`; Copy and Ask again under an answer (Ask again drafts the
question, as every ask does: no button but Send sends); New and Save at the top.

Checked in a browser at 375x812 with a simulated answer: the bubble, the folded
card, the answer, a gold SPY chart, the follow-ups and Copy / Ask again; the
next question's card read Working, a tick on "Reading what is on your screen"
and a spinner on "Thinking it through"; the bottom bar was off while Pulse was
open.
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
HTML = (ROOT / "static/index.html").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _fn(head):
    at = APP.index(head)
    return APP[at:APP.index("\n}\n", at) + 3]


def _run(script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    consts = APP[APP.index("const PULSE_CHART_RE ="):APP.index("const pulseChartBars")]
    # The chart pass hands on to the source chips (test_pulse_sources).
    sources = APP[APP.index("const PULSE_SOURCES = {"):APP.index("function pulseSourcesIn(")]
    prelude = ("function esc(s) { return String(s); }\n" + consts + sources
               + _fn("function pulseChartsIn(html) {") + _fn("function pulseSourcesIn(html) {"))
    out = subprocess.run([exe, "-e", prelude + script], capture_output=True, text=True,
                         timeout=60, cwd=str(ROOT))
    assert "RESULT:" in out.stdout, (out.stdout + out.stderr)[-1500:]
    return json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])


def test_a_chart_marker_becomes_a_chart_and_nothing_else_does():
    out = _run("""
      print('RESULT:' + JSON.stringify([
        pulseChartsIn('<p>see</p>\\n[[chart SPY 3m]]\\nmore'),
        pulseChartsIn('[[chart BRK.B 5y]] and [[chart ^GSPC 1y]]'),
        pulseChartsIn('[[chart spy 3m]] [[chart SPY 2w]] [[chart <b>x</b> 1m]]')]));
    """)
    spy, two, none = out
    assert '<div class="pulse-chart" data-sym="SPY" data-span="3m">' in spy
    assert "SPY, daily close over the last 3 months" in spy and "[[chart" not in spy
    assert 'data-sym="BRK.B" data-span="5y"' in two and 'data-sym="^GSPC" data-span="1y"' in two
    assert "pulse-chart" not in none, "a lower-case symbol, an unknown span or markup is left as text"


def test_the_chart_is_drawn_from_the_terminals_bars_in_its_gold():
    mount = _fn("function mountPulseCharts(root) {")
    assert "getJSON('/api/daily-bars/' + encodeURIComponent(sym))" in mount
    assert "color: C.brand" in mount and "bars.close.slice(-n)" in mount
    assert "No price history for" in mount
    for at in ("bubble.innerHTML = pulseChartsIn(mdLite(body));\n  mountPulseCharts(bubble);",
               "settledEl.innerHTML = pulseChartsIn(mdLite(body));\n      mountPulseCharts(settledEl);"):
        assert at in APP, at


def test_pulse_is_told_how_and_when_to_place_one():
    fmt = " ".join(ai.FORMAT_PROMPT.split())
    assert "`[[chart SYMBOL SPAN]]`" in fmt and "one of 1m, 3m, 6m, 1y or 5y" in fmt
    assert "One chart per answer at most" in fmt
    assert "Never write the chart's numbers as if you had read them off it" in fmt
    assert "—" not in ai.FORMAT_PROMPT


def test_the_steps_are_the_servers_ticked_in_turn_and_folded_once_it_answers():
    stream = _fn("async function streamTo(url, body, node) {")
    assert "if (node.pulseSteps) pulseStepAdd(node, PULSE_STEP_WORDS[state] || cap(state));" in stream
    assert stream.count("if (node.pulseSteps) pulseStepsDone(node); else statusEl.textContent = '';") == 2, (
        "folded when the answer starts, and at the end if it never did")
    assert "if (node.pulseSteps) pulseStepsDone(node, true);" in stream
    add = _fn("function pulseStepAdd(node, label) {")
    assert "list.querySelectorAll('li.on').forEach((li) => { li.className = 'done'; });" in add
    assert "if (steps[steps.length - 1] === label) return;" in add, "a repeated event is one step"
    done = _fn("function pulseStepsDone(node, failed) {")
    assert "`Worked through ${n} step${n === 1 ? '' : 's'}`" in done and "box.open = false;" in done
    assert "pulseStepsStart(node, 'Reading what is on your screen');" in _fn("async function sendChat(text) {")
    assert "pulseStepsStart(node, 'Searching live sources');" in _fn("async function runResearch() {")


def test_under_an_answer_copy_and_ask_again_and_neither_sends():
    acts = _fn("function addReplyActions(node, text, question) {")
    assert "data-pulse-copy" in acts and "data-pulse-again" in acts
    assert "if (node && node.dataset.question) draftPulse(node.dataset.question);" in APP
    assert "addReplyActions(node, reply, text);" in _fn("async function sendChat(text) {")
    assert "navigator.clipboard.writeText(text)" in APP


def test_no_new_or_save_buttons_at_the_top_of_the_panel():
    """A pencil (New conversation) and an arrow (Save as a file) shipped in the
    panel's header on 2026-10-04 and were removed the next day on the reader's
    call: bare glyphs whose meaning was only in a tooltip, asked about as
    "what are these two buttons on pulse?". Save was reachable from nowhere
    else, so it went whole; a new conversation is still the New button in
    Saved conversations, which predates both."""
    head = HTML[HTML.index('<div class="chat-head">'):HTML.index('<div class="chat-body"')]
    assert "data-pulse-new" not in head and "data-pulse-export" not in head
    assert "pulseExport" not in APP and "data-pulse-export" not in APP, \
        "no handler left behind without its control"
    drawer = _fn("function renderPulseHistory(open) {")
    assert 'data-pulse-new>New</button>' in drawer
    assert "if (evt.target.closest('[data-pulse-new]')) { pulseNewConversation(); return; }" in APP


def test_the_look():
    assert "#chat .msg.user .bubble {\n  align-self: flex-end;" in CSS
    assert "#chat .msg.assistant .bubble { background: none; border: 0; padding: 0; }" in CSS
    assert ".ps-list li.done::before {" in CSS and ".ps-list li.on::before" in CSS
    assert "body.chat-open .mtabs { display: none; }" in CSS
    status = APP.index('<div class="status"></div>\n    <div class="bubble"></div>')
    assert status > 0, "the steps above the answer"
