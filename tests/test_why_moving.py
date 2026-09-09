"""The panel that promised a cause and delivered an attribution.

It was headed "Why it's moving" with the day's change beside it, and the body
ranks the model's factors by *absolute* score. So on a day a stock closed down
0.66% the three strongest could all read bullish, and they did: three green
arrows under a red number, which was reported as a rendering bug.

Nothing about the ranking was wrong. The heading was making a claim the panel
cannot support. It now says what the list is.

Also here: the Ask Pulse button, which two panels offered only while they were
empty.
"""

from __future__ import annotations

import re

APP_JS = open("static/app.js").read()
PULSE_PY = open("app/analytics/pulse.py").read()


def _fn(name: str) -> str:
    start = APP_JS.index("function %s(" % name)
    nxt = APP_JS.find("\nfunction ", start + 1)
    return APP_JS[start:nxt if nxt > 0 else len(APP_JS)]


def _code_only(src: str) -> str:
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", "", src)


def test_the_heading_no_longer_claims_a_cause():
    """"Why it's moving" is a causal claim. The panel ranks by score."""
    code = _code_only(APP_JS)
    assert "Why it's moving" not in code
    assert code.count("What's pulling hardest") == 2      # both branches


def test_the_aria_label_moved_with_it():
    """A screen reader would otherwise still be told the old claim."""
    code = _code_only(APP_JS)
    assert 'aria-label="Why it is moving"' not in code
    assert code.count('aria-label="What is pulling hardest"') == 2


def test_the_day_s_change_is_labelled_rather_than_bare():
    """A bare percentage next to the heading is what made it read as the thing
    being explained."""
    fn = _fn("renderWhyMoving")
    assert "fmtPct(w.change_pct, 2)} today" in fn


def test_the_change_comes_before_the_action():
    """The button sat between the title and its number, interrupting them."""
    fn = _fn("renderWhyMoving")
    head = fn[fn.index("What's pulling hardest${\n"):]
    head = head[:head.index("</h2>")]
    assert head.index("pl-h-chg") < head.index("askPulse")


def test_the_method_line_explains_the_thing_that_was_reported():
    """Restating the heading would waste the one line the panel has to explain
    why bullish factors can sit under a red number."""
    assert "regardless of direction" in PULSE_PY
    assert "read bullish on a day the price is down" in PULSE_PY
    assert "not a causal" in PULSE_PY
    # And it still does not claim causation.
    assert "These are the scored inputs pulling hardest" not in PULSE_PY


def test_no_em_dash_in_the_method_line():
    """The house rule, and tests/test_relperf.py already asserts it elsewhere.
    This line carried one for a while."""
    block = PULSE_PY[PULSE_PY.index('"method": ('):]
    block = block[:block.index('"reason_none"')]
    assert "—" not in block


def test_the_pulse_prompt_does_not_quote_the_old_title():
    """It asked Pulse about "the why it is moving read", which no longer
    exists on screen."""
    prompt = APP_JS[APP_JS.index("whymoving: '"):]
    prompt = prompt[:prompt.index("\n\n")]
    assert "why it is moving" not in prompt
    assert "what is pulling hardest" in prompt


# ------------------------------------------------------------ the ask button


def test_the_ask_button_is_offered_when_there_is_something_to_ask_about():
    """It was on the empty branch and not the populated one, so it appeared
    only when the panel had nothing in it."""
    assert _fn("renderWhyMoving").count("askPulse('whymoving')") == 2
    assert _fn("renderWhatsNext").count("askPulse('whatsnext')") == 2


def test_no_panel_offers_the_button_in_only_one_of_its_states():
    """The audit that found the second instance. A per-topic count cannot see
    this: the topic is referenced, just from the wrong branch."""
    inconsistent = []
    for m in re.finditer(r"function (render\w+)\(", APP_JS):
        name, start = m.group(1), m.start()
        nxt = APP_JS.find("\nfunction ", start + 1)
        body = APP_JS[start:nxt if nxt > 0 else len(APP_JS)]
        heads = re.findall(r'<h2 class="pl-h">([^<]*?)</h2>', body)
        if len(heads) >= 2 and len({("askPulse" in h) for h in heads}) > 1:
            inconsistent.append(name)
    assert not inconsistent, inconsistent


def test_the_topic_key_survived_the_rename():
    """Only the copy changed, not the id.

    The both-directions check on PULSE_TOPICS lives in
    tests/test_auth_client.py (test_every_ask_pulse_topic_used_is_a_topic_defined)
    and does this properly, scoped to the topics block and tolerant of either
    quote style. A second copy here parsed the whole file with a narrower
    pattern and reported `earningsweek` as undefined because that one entry is
    written with double quotes."""
    assert "whymoving:" in APP_JS
    assert "askPulse('whymoving')" in APP_JS
