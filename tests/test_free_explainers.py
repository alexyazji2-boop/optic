"""A chip that asks what something is answers it free, without Pulse.

Reported by a user: "if there's an option like "Why three horizons" next to the
Side by side, the user shouldn't have to use 1 out of 3 chats with Pulse to do
that, it should be free information". Checked in a browser at 1470x785 on the
Compare tab: the chip opened its answer beneath itself, Pulse stayed shut, and
the page made no request at all.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from app.analytics import compare

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
      var free = askPulse('compare');
      assert(free.indexOf('data-explain="compare"') > 0 && free.indexOf('data-ask') < 0, free);
      assert(free.indexOf('aria-haspopup="dialog"') > 0 && free.indexOf('>Why three horizons?<') > 0, 'named');
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
      var c = explainerHTML('compare');
      assert(c.split('<p>').length - 1 === 5, 'five paragraphs');
      assert(c.indexOf('company&#39;s') > 0 || c.indexOf("company's") > 0, 'escaped as text');
      assert(explainerHTML('flow') === '', 'no answer for a live question');
    """)


def test_the_comparison_answer_matches_what_the_comparison_scores():
    explainers = _block("ASK_EXPLAINERS")
    swing, position, longterm = (h["basis"] for h in compare.HORIZONS)
    for phrase in ("14-session RSI", "20-session realised volatility", "21-session"):
        assert phrase in explainers and phrase in swing, phrase
    assert "50- and 200-day averages" in explainers and "50- and 200-day averages" in position
    assert "Five-year annualised return" in longterm and "five-year annualised return" in explainers
    assert "A lead under 8 points is a close call" in explainers
    assert "const decisive = gap >= 8;" in RAW, "the same threshold the bars use"


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
