"""The "Read more" expansion on the Optic Pulse hero.

**Executed, not grepped.** The other client tests in this repo read
`static/app.js` as text, which is the right tool for wiring and the wrong one
here: every claim this block makes is the result of a comparison — which input
is doing the most work, which side it is on, whether anything opposes the
stance — and a regular expression cannot tell a correct comparison from a
reversed one. So this drives the real function under JavaScriptCore with
synthetic payloads, the same harness `tests/test_js_parses.py` uses.

Two of these cases are regressions from the first version, both found by
running it rather than reading it:

* On a bullish read with Options at -55, the opening sentence introduced
  Options as "behind it" and the next line listed the same input under
  "Against it" — the panel contradicting itself inside one paragraph.
* On a *bearish* read where every input agreed, it announced "nothing material
  is pulling the other way, Options is the nearest to it at -20". On a bearish
  read -20 is agreement, so it named the wrong input and reversed its meaning.

Skipped where `jsc` is absent, so a Linux box does not go red for a reason
unrelated to the change.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess

import pytest

JSC = ("/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/"
       "Helpers/jsc")

APP = open("static/app.js", encoding="utf-8").read()
CSS = open("static/styles.css", encoding="utf-8").read()


def _jsc():
    return JSC if os.path.exists(JSC) else shutil.which("jsc")


def _factor(key, label, score, weight, **extra):
    body = {"key": key, "label": label, "score": score, "weight_pct": weight,
            "bar": 50, "measures": "", "unavailable": False,
            "why_unavailable": None,
            "direction": "up" if (score or 0) > 5
                         else "down" if (score or 0) < -5 else "flat"}
    body.update(extra)
    return body


# Every case is a full `d` as `renderOpticPulse` receives it.
CASES = {
    # Momentum and Positioning both +90; Options mildly against but tiny.
    "bullish_all_agree": {"pulse": {
        "stance": "bullish", "conviction": "high", "agreement_pct": 100,
        "factors_priced": 5, "factors_total": 5,
        "factors": [_factor("technicals", "Momentum", 90, 34),
                    _factor("gamma", "Options", 41, 24),
                    _factor("flow", "Positioning", 90, 20),
                    _factor("news", "News", -2, 12),
                    _factor("macro", "Macro", 18, 10)]}},

    "bullish_with_opposition": {"pulse": {
        "stance": "bullish", "conviction": "medium", "agreement_pct": 60,
        "factors_priced": 4, "factors_total": 4,
        "factors": [_factor("technicals", "Momentum", 80, 34),
                    _factor("gamma", "Options", -55, 24),
                    _factor("flow", "Positioning", 30, 20),
                    _factor("news", "News", -70, 12)]}},

    "bearish_all_agree": {"pulse": {
        "stance": "bearish", "conviction": "high", "agreement_pct": 100,
        "factors_priced": 3, "factors_total": 3,
        "factors": [_factor("technicals", "Momentum", -60, 34),
                    _factor("gamma", "Options", -20, 24),
                    _factor("flow", "Positioning", -40, 20)]}},

    # Macro is here to separate two orderings that the first version of this
    # fixture could not tell apart. Options at +3 on 24% contributes 0.72 and
    # opposes; Macro at -1 on 20% contributes 0.20 and agrees. Picking the
    # smallest contribution names Macro, picking the least-aligned input names
    # Options, and only the second is right. Without Macro both rules returned
    # Options and the mutation that reverted one to the other survived.
    "bearish_mild_opponent": {"pulse": {
        "stance": "bearish", "conviction": "medium", "agreement_pct": 50,
        "factors": [_factor("technicals", "Momentum", -60, 34),
                    _factor("gamma", "Options", 3, 24),
                    _factor("macro", "Macro", -1, 20)]}},

    "neutral": {"pulse": {
        "stance": "neutral", "conviction": "low", "agreement_pct": 40,
        "factors_priced": 5, "factors_total": 5,
        "factors": [_factor("technicals", "Momentum", 20, 34),
                    _factor("gamma", "Options", -20, 24),
                    _factor("flow", "Positioning", 5, 20)]}},

    "missing_and_pending": {"pulse": {
        "stance": "bearish", "conviction": "low", "agreement_pct": 75,
        "factors_priced": 3, "factors_total": 5,
        "pending_catalyst": {"pending": True},
        "conflicts": ["The chart predates the announcement."],
        "factors": [_factor("technicals", "Momentum", -60, 34),
                    _factor("gamma", "Options", -20, 24),
                    _factor("flow", "Positioning", -40, 20),
                    _factor("news", "News", None, 12, unavailable=True,
                            why_unavailable="no headlines in window"),
                    _factor("macro", "Macro", None, 10, unavailable=True,
                            why_unavailable="macro feed unavailable")]}},

    # Nothing to say. Must render nothing rather than an empty disclosure.
    "all_missing": {"pulse": {"stance": "neutral", "factors": [
        _factor("technicals", "Momentum", None, 34, unavailable=True)]}},
    "no_factors": {"pulse": {"stance": "bullish", "factors": []}},
    "no_pulse": {},
}


@pytest.fixture(scope="module")
def rendered():
    """`{case: {html, paragraphs}}`, produced by the real function.

    Strips tags in JS rather than in Python so the assertions below read the
    same text a person would."""
    exe = _jsc()
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    script = """
      load('tests/support/browser_stubs.js');
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
      if (typeof pulseReadMore !== 'function') {
        print('RESULT:' + JSON.stringify({error: 'pulseReadMore is not defined'}));
      } else {
        var cases = %s;
        var out = {};
        for (var key in cases) {
          var html = pulseReadMore(cases[key]) || '';
          var text = html
            .replace(/<[^>]*>/g, ' ')
            .replace(/&amp;/g, '&').replace(/&#39;/g, "'").replace(/&quot;/g, '"')
            .replace(/\\s+/g, ' ').trim();
          // Paragraph boundaries survive the strip so each claim stays separate.
          var paras = html.split('<p').slice(1).map(function (chunk) {
            // Drop the remainder of the opening tag the split cut in half,
            // or every paragraph starts '> ' and no assertion on the first
            // word of a claim can work.
            return chunk.replace(/^[^>]*>/, '').replace(/<[^>]*>/g, ' ')
              .replace(/&amp;/g, '&').replace(/&#39;/g, "'")
              .replace(/\\s+/g, ' ').trim();
          });
          out[key] = {html: html, text: text, paragraphs: paras};
        }
        print('RESULT:' + JSON.stringify(out));
      }
    """ % json.dumps(CASES)
    proc = subprocess.run([exe, "-e", script], capture_output=True, text=True,
                          timeout=180)
    blob = proc.stdout + proc.stderr
    assert "RESULT:" in blob, blob[-1500:]
    body = json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])
    assert "error" not in body, body
    return body


# ------------------------------------------------------------------ it renders


def test_it_renders_a_read_more_disclosure(rendered):
    html = rendered["bullish_all_agree"]["html"]
    assert '<details class="pl-more">' in html
    assert "<summary>Read more</summary>" in html


def test_it_renders_nothing_when_there_is_nothing_to_say(rendered):
    """An empty disclosure is the same fault as a "More" that reveals nothing,
    which this panel's own summary and the status strip both fixed."""
    for key in ("all_missing", "no_factors", "no_pulse"):
        assert rendered[key]["html"] == "", key


# ------------------------------------------------- what is doing the work


def test_it_ranks_by_contribution_not_by_score(rendered):
    """Momentum +90 on 34% and Positioning +90 on 20% are the same score and
    not the same amount of work. Ranking by score alone calls them a tie and
    then picks whichever the sort happened to leave first."""
    first = rendered["bullish_all_agree"]["paragraphs"][0]
    assert first.startswith("Momentum is doing most of the work")
    assert "34%" in first
    # Positioning (18.0) out-contributes Options (9.8) despite the lower score.
    assert "Positioning" in first and "Options" not in first


def test_a_second_input_on_the_other_side_is_not_called_a_supporter(rendered):
    """The regression. Options at -55 on 24% out-contributes Positioning, so
    contribution ranking put it second — and the sentence introduced it as
    "with Options behind it", two lines above "Against it: Options at -55"."""
    paras = rendered["bullish_with_opposition"]["paragraphs"]
    assert "behind it" not in paras[0], paras[0]
    assert paras[1].startswith("Against it:")
    assert "Options at -55" in paras[1]


def test_opposition_is_named_with_its_score_and_weight(rendered):
    second = rendered["bullish_with_opposition"]["paragraphs"][1]
    assert "Options at -55 on 24%" in second
    assert "News at -70 on 12%" in second


def test_a_negative_score_on_a_bearish_read_is_agreement(rendered):
    """The other regression, and the worse of the two: it announced "nothing
    material is pulling the other way, Options is the nearest to it at -20" on
    a read where -20 is agreement. Both the input and the meaning were wrong."""
    second = rendered["bearish_all_agree"]["paragraphs"][1]
    assert second.startswith("Every input that had data points the same way")
    assert "pulling the other way" not in second
    # The weakest *supporter* is Options at -20, and it is named as such.
    assert "Options at -20" in second


def test_a_genuine_mild_opponent_still_reads_as_one(rendered):
    """The counterpart: +3 against a bearish read is opposition, just not
    material. It must not be swept into "every input agrees"."""
    second = rendered["bearish_mild_opponent"]["paragraphs"][1]
    assert "Nothing material is pulling the other way" in second
    assert "Options is the nearest to it at +3" in second
    # Macro contributes less and *agrees*. Naming it here would be the
    # smallest-contribution rule, which is the one that was wrong.
    assert "Macro" not in second, second


def test_neutral_says_what_neutral_means(rendered):
    """"Neutral" is read as a forecast of no movement, and it is not one. It
    is the inputs disagreeing."""
    second = rendered["neutral"]["paragraphs"][1]
    assert "do not agree on a direction" in second
    assert "not a forecast of no movement" in second


# ------------------------------------------------------------- the conviction


def test_conviction_adds_to_the_chip_rather_than_repeating_it(rendered):
    """`.pl-meta` below already prints "high conviction" and "100% of inputs
    agree". A paragraph that says only those two things again is the duplicate
    this panel removed when it dropped the 32px stance chip.

    What it adds is the misreading: conviction measures agreement between the
    inputs, not the probability of the move."""
    para = rendered["bullish_all_agree"]["paragraphs"][2]
    assert "5 of 5 had data" in para
    assert "not a probability" in para


def test_two_inputs_off_one_source_are_reported_as_dependent(rendered):
    """Options and Positioning are both computed from the same option chain,
    so those two agreeing is less corroboration than two ticks look like.
    Derived from the factor keys present, not asserted: stating it
    unconditionally would be wrong the moment either input is missing."""
    assert "same option chain" in rendered["bullish_all_agree"]["text"]
    # Only Momentum and Options here, so the claim must not appear.
    assert "same option chain" not in rendered["bearish_mild_opponent"]["text"]


def test_a_pending_event_explains_the_held_conviction(rendered):
    assert "held short of high" in rendered["missing_and_pending"]["text"]


# ----------------------------------------------------------------- the limits


def test_every_reading_says_what_it_cannot_tell_you(rendered):
    """House rule: every panel states its own limits."""
    for key in ("bullish_all_agree", "bullish_with_opposition",
                "bearish_all_agree", "neutral", "missing_and_pending"):
        text = rendered[key]["text"]
        assert "weights this app chose, not a fitted model" in text, key
        assert 'class="pl-more-limits"' in rendered[key]["html"], key


def test_missing_inputs_are_named_with_the_reason_and_the_consequence(rendered):
    text = rendered["missing_and_pending"]["text"]
    assert "News and Macro had no data" in text
    assert "no headlines in window" in text and "macro feed unavailable" in text
    assert "redistributes its weight rather than counting as zero" in text


def test_a_conflict_in_the_payload_is_finally_rendered(rendered):
    """`renderOpticPulse`'s own comment records that this panel is the whole of
    the judgement on the Dossier overview and does not render conflicts. A
    one-sentence summary that hides a conflict is the case where it actively
    misleads."""
    assert ("The chart predates the announcement."
            in rendered["missing_and_pending"]["text"])


def test_no_paragraph_uses_an_em_dash(rendered):
    """A deliberate pass over the whole terminal, recorded in CLAUDE.md."""
    for key, body in rendered.items():
        assert "—" not in body["text"], key


# -------------------------------------------------------------- it is wired in


def test_the_hero_actually_calls_it():
    """A renderer nothing calls is dead code that passes every test above."""
    hero = APP.split("function renderOpticPulse(d) {", 1)[1].split("\nfunction ", 1)[0]
    assert "pulseReadMore(d)" in hero
    # Under the sentence it expands, above the story link.
    assert hero.index("pulseReadMore(d)") < hero.index('class="pl-story"')


def test_it_is_styled_rather_than_inheriting_whatever_is_nearby():
    for rule in (".pl-more > summary {", ".pl-more-body {", ".pl-more-limits {"):
        assert rule in CSS, rule
    # The disclosure triangle is suppressed the same way .pl-bars does it; two
    # differently-styled disclosures in one panel read as two kinds of control.
    assert ".pl-more > summary::-webkit-details-marker { display: none; }" in CSS
