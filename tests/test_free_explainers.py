"""A chip that asks what something is answers it free, without Pulse.

Reported by a user: "if there's an option like "Why three horizons" next to the
Side by side, the user shouldn't have to use 1 out of 3 chats with Pulse to do
that, it should be free information". Checked in a browser at 1470x785 on the
Compare tab: the chip opened its answer beneath itself, Pulse stayed shut, and
the page made no request at all.

That chip itself is gone since: its follow-up sent Pulse a question about a
comparison it had not been given, and the owner asked for it to be removed
("remove the three horizons chatbot button as well"). The definition chips that
remain answer from the glossary.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
RAW = (ROOT / "static/app.js").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _raw_fn(name):
    return re.search(r"^function %s\([^\n]*\) \{.*?^\}" % name, RAW, re.M | re.S).group()


def _block(name):
    return re.search(r"^const %s = \{.*?^\};" % name, RAW, re.M | re.S).group()


def _run(scenario):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = ("function assert(v, m) { if (!v) throw new Error(m); }\n"
           + _raw_fn("esc") + "\n"
           + _block("GLOSSARY") + "\n" + _block("PULSE_ASK_LABELS") + "\n"
           + _block("ASK_EXPLAINERS") + "\n"
           + _raw_fn("explainerHTML") + "\n" + _raw_fn("askPulse") + "\n"
           + scenario + "\nprint('TEST_OK');")
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=30)
    assert "TEST_OK" in out.stdout, out.stdout + out.stderr


def test_a_definition_chip_opens_its_answer_and_a_live_one_still_asks_pulse():
    _run("""
      var free = askPulse('gex');
      assert(free.indexOf('data-explain="gex"') > 0 && free.indexOf('data-ask') < 0, free);
      assert(free.indexOf('aria-haspopup="dialog"') > 0, 'a dialog');
      var live = askPulse('flow');
      assert(live.indexOf('data-ask="flow"') > 0 && live.indexOf('data-explain') < 0, live);
      ['gex', 'iv', 'levels', 'pehistory'].forEach(function (t) {
        assert(askPulse(t).indexOf('data-explain="' + t + '"') > 0, t);
      });
    """)


def test_the_answers_are_the_terminals_own_words():
    _run("""
      assert(explainerHTML('gex') === '<p>' + GLOSSARY['gex'] + '</p><p>' + GLOSSARY['dealer gamma']
             + '</p><p>' + GLOSSARY['gamma flip'] + '</p>', 'the glossary, verbatim');
      assert(explainerHTML('flow') === '', 'no answer for a live question');
    """)


def test_the_comparison_has_no_chip_and_no_question_left_behind():
    """Removed with everything it opened, so no other button can send the
    question it asked."""
    fn = RAW[RAW.index("function renderCompare(c) {"):]
    fn = fn[:fn.index("\n}\n")]
    assert "<h2 class=\"weekly-title\">Compare</h2>" in fn
    assert "askPulse(" not in fn
    for block in ("PULSE_TOPICS", "PULSE_ASK_LABELS", "ASK_EXPLAINERS"):
        body = re.search(r"^const %s = \{.*?^\};" % block, RAW, re.M | re.S).group()
        assert "\n  compare:" not in body, block
    assert "'Why three horizons?'" not in RAW, "the label, as a string the page could print"


def test_it_closes_on_the_x_a_click_elsewhere_or_escape_and_pulse_is_one_press_away():
    click = RAW[RAW.index("const explainChip = evt.target.closest('[data-explain]');"):]
    end = "openPulseWith(ask.dataset.ask); return; }"
    click = click[:click.index(end) + len(end)]
    assert "if (explainerFrom === explainChip) closeExplainer(true);" in click
    assert "if (evt.target.closest('[data-explain-close]')) { closeExplainer(true); return; }" in click
    assert "if (!evt.target.closest('#explain-pop')) closeExplainer(false);" in click
    assert "if (ask) { closeExplainer(false); openPulseWith(ask.dataset.ask); return; }" in click
    assert "if (evt.key === 'Escape' && document.getElementById('explain-pop')) closeExplainer(true);" in RAW
    pop = _raw_fn("openExplainer")
    assert 'class="explain-more" data-ask="${esc(topic)}"' in pop
    assert "Uses a Pulse chat." in pop
