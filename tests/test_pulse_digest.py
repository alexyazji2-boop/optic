"""The Pulse digest: one sentence, its provenance, and three questions.

The panel used to lead with four labels — an eyebrow, a 32px stance word, a
conviction word and "60% of inputs agree" — above five factor bars. Every part
was accurate and the whole was a legend rather than an answer: the reader had to
assemble "down today but read bullish, carried by positioning, with macro
against" out of a word and five bars themselves.

Every figure in these docstrings is an observation from a live AAPL payload
captured while building this, not a target.
"""

import copy
import json
import re

from app.analytics import pulse as P

APP_JS = open("static/app.js", encoding="utf-8").read()
CSS = open("static/styles.css", encoding="utf-8").read()
MAIN = open("app/main.py", encoding="utf-8").read()


def _payload():
    """A payload shaped like the real one, with the parts digest() reads."""
    return {
        "ticker": "AAPL",
        "generated_at": "2026-09-15T16:55:36+00:00",
        "quote": {"name": "Apple Inc.", "price": 330.11, "change_pct": -0.89},
        "technicals": {"spot": 330.11},
        "gex": {"flip_point": 331.0},
        "pulse": {
            "stance": "bullish",
            "conviction": "high",
            "conflicts": [],
            "factors": [
                {"key": "technicals", "label": "Momentum", "score": 90.0,
                 "direction": "up", "unavailable": False},
                {"key": "flow", "label": "Positioning", "score": 100.0,
                 "direction": "up", "unavailable": False},
                {"key": "macro", "label": "Macro", "score": -26.2,
                 "direction": "down", "unavailable": False},
            ],
            "factors_priced": 3, "factors_total": 3,
        },
        "why": {"available": True, "reasons": [
            {"factor": "flow", "label": "Positioning", "direction": "up", "score": 100.0},
            {"factor": "technicals", "label": "Momentum", "direction": "up", "score": 90.0},
        ]},
        "news": {"days_to_earnings": None, "articles": [
            {"title": "Apple Stock Slips After India Escalates Repair Probe",
             "publisher": "GuruFocus.com", "age_hours": 1.3, "age_words": "1 hour ago",
             "tier": "breaking", "tier_why": "Filed 1 hour ago.", "about_company": True,
             "url": "https://example.com/a",
             "catalysts": [{"type": "legal / regulatory", "importance": "high"}]},
            {"title": "Sector wrap", "publisher": "Reuters", "age_hours": 4.0,
             "age_words": "4 hours ago", "tier": "major", "about_company": False,
             "url": "https://example.com/b", "catalysts": []},
            {"title": "Another Reuters piece", "publisher": "Reuters", "age_hours": 6.0,
             "tier": "notable", "about_company": True, "catalysts": []},
        ]},
    }


# ------------------------------------------------------------------- the lede

def test_the_lede_states_the_move_and_the_reading_without_joining_them():
    """`why()` carries a long note about why its heading is "What's pulling
    hardest" and not "Why it's moving": the factors are an attribution across
    the model's own inputs, so on a day a stock is down the three strongest can
    all read bullish, and they did — it was reported as a bug. Asserting the
    lede never uses a causal verb is what stops that shipping again in the
    largest type on the page."""
    lede = P.digest(_payload())["lede"]
    assert "Apple Inc. is down 0.9% today." in lede
    assert "Optic reads the setup bullish" in lede
    for causal in (" on strong ", " because ", " driven by ", " due to ", " as "):
        assert causal not in lede, f"causal phrasing {causal!r} in the lede"


def test_the_lede_names_the_dissent():
    """The factor pulling against the stance is the most useful half of the
    sentence — otherwise the reader has to find it by comparing five bars."""
    assert "macro pulling the other way" in P.digest(_payload())["lede"]


def test_a_factor_is_never_both_the_hardest_pull_and_the_dissent():
    """`why.reasons` ranks by ABSOLUTE score regardless of direction, so on an
    up day read bearish the same factor was both: "with positioning and momentum
    pulling hardest and momentum pulling the other way" — a sentence that
    contradicts itself in its own second clause."""
    p = _payload()
    p["quote"]["change_pct"] = 2.4
    p["pulse"]["stance"] = "bearish"
    lede = P.digest(p)["lede"]
    for label in ("momentum", "positioning", "macro"):
        assert lede.count(label) <= 1, f"{label} named twice in: {lede}"


def test_the_lede_stays_grammatical_with_no_reasons_above_the_floor():
    """Appending each clause with its own conjunction produced "bullish and
    macro pulling the other way" whenever the pulls list came back empty — a
    dangling "and" on any symbol whose factors all sat under WHY_FLOOR."""
    p = _payload()
    p["why"]["reasons"] = []
    lede = P.digest(p)["lede"]
    assert "bullish and macro" not in lede
    assert "with macro pulling the other way" in lede


def test_a_flat_day_gets_its_own_words():
    """"up 0.0% today" is a sentence about nothing."""
    p = _payload()
    p["quote"]["change_pct"] = 0.01
    assert "is flat today" in P.digest(p)["lede"]


def test_a_missing_change_is_said_rather_than_guessed():
    p = _payload()
    p["quote"].pop("change_pct")
    assert "has not printed a change today" in P.digest(p)["lede"]


def test_a_long_legal_name_falls_back_to_the_ticker():
    """"Alphabet Inc. Class A Common Stock is down 0.9% today" is not a
    sentence a person would write."""
    p = _payload()
    p["quote"]["name"] = "Alphabet Inc. Class A Common Stock"
    assert P.digest(p)["lede"].startswith("AAPL is down")


def test_a_neutral_stance_claims_no_agreement():
    """Neutral has no direction, so the two strongest inputs are named without
    implying either supports the reading."""
    p = _payload()
    p["pulse"]["stance"] = "neutral"
    lede = P.digest(p)["lede"]
    assert "neutral" in lede and "pulling hardest" in lede


def test_no_pulse_means_no_digest():
    p = _payload()
    p.pop("pulse")
    out = P.digest(p)
    assert out["available"] is False and out["reason_none"]


# ---------------------------------------------------------------- provenance

def test_sources_counts_distinct_publishers_not_articles():
    """Ten stories from Reuters twice and eight others is nine sources. The
    article count would overstate the breadth of the wire that was read."""
    src = P.digest(_payload())["sources"]
    assert src["count"] == 2, src           # GuruFocus + Reuters, Reuters twice
    assert src["article_count"] == 3
    assert src["names"].count("Reuters") == 1


def test_the_named_story_is_about_this_company():
    """news.py sorts company stories ahead of sector context precisely because
    an unfiltered wire put "RF Industries Q3 Earnings" at the top of NVDA's
    page. A lede is the worst possible place for that to happen again."""
    story = P.digest(_payload())["story"]
    assert story["publisher"] == "GuruFocus.com"
    assert "Apple" in story["title"]


def test_the_named_story_carries_what_the_tier_badge_needs():
    """The client's badge reads the label out of news.tiers and the explanation
    off the row, so the row has to carry both. A hardcoded "Breaking" in the
    client would be a second copy that drifts."""
    story = P.digest(_payload())["story"]
    assert story["tier"] == "breaking"
    assert story["tier_why"]


def test_a_company_story_with_no_catalyst_is_not_promoted():
    """"Another Reuters piece" is about_company and has no catalyst. Naming it
    would put an untagged background story in the largest type on the page."""
    p = _payload()
    p["news"]["articles"][0]["catalysts"] = []
    assert P.digest(p)["story"] is None


def test_no_news_costs_the_story_and_nothing_else():
    p = _payload()
    p["news"]["articles"] = []
    out = P.digest(p)
    assert out["available"] and out["lede"]
    assert out["story"] is None and out["sources"]["count"] == 0


# ---------------------------------------------------------------- follow-ups

def test_follow_ups_name_a_number_on_screen():
    """"Tell me about the options" is a question anyone could ask without
    opening the app."""
    ups = P.digest(_payload())["follow_ups"]
    assert len(ups) == P.FOLLOW_UP_LIMIT
    assert any(re.search(r"[+-]?\d", u["question"]) for u in ups)


def test_the_invalidation_question_always_survives():
    """It ranks last on purpose. A digest that only ever confirms itself is one
    nobody should trust."""
    for mutate in (lambda p: None,
                   lambda p: p["pulse"].update(conflicts=["a", "b"]),
                   lambda p: p["news"].update(days_to_earnings=2),
                   lambda p: p["why"].update(reasons=[])):
        p = _payload()
        mutate(p)
        qs = [u["question"] for u in P.digest(p)["follow_ups"]]
        assert any("wrong" in q for q in qs), qs


def test_follow_ups_carry_their_own_prompt_not_a_shared_topic():
    """The first version routed them through PULSE_TOPICS keys and two of three
    collided on `whymoving`: the strongest-input question and the
    freshest-story question are different questions that would have opened the
    identical template, so one was dropped and three earned follow-ups rendered
    as two."""
    ups = P.digest(_payload())["follow_ups"]
    assert len(ups) == 3
    assert len({u["prompt"] for u in ups}) == 3
    for u in ups:
        assert u["question"] in u["prompt"], "the question asked must be the one shown"
        assert "AAPL" in u["prompt"], "a model that cannot see the page needs the symbol"


def test_follow_ups_are_deduplicated_by_question():
    ups = P.digest(_payload())["follow_ups"]
    assert len({u["question"] for u in ups}) == len(ups)


def test_earnings_outrank_everything_when_they_are_days_away():
    p = _payload()
    p["news"]["days_to_earnings"] = 2
    qs = [u["question"] for u in P.digest(p)["follow_ups"]]
    assert any("Earnings are" in q for q in qs), qs


def test_a_distant_gamma_flip_earns_no_question():
    """Within 3% it shapes the day's range. Twenty percent away it is trivia.

    Asserted against the candidate pool rather than the final three. A widened
    threshold is indistinguishable from a question that simply lost on rank
    once only two ranked slots exist — mutating `away <= 3.0` to `away <= 300.0`
    left the picked list identical, so a test on the shortlist proved nothing.
    """
    near = _payload()                      # flip at 331 against spot 330.11
    got = [c["question"] for c in P._candidate_follow_ups(near)]
    assert any("gamma flip" in q for q in got), got

    far = _payload()
    far["gex"]["flip_point"] = 420.0
    got = [c["question"] for c in P._candidate_follow_ups(far)]
    assert not any("gamma flip" in q for q in got), got


# ------------------------------------------------------------------ wiring

def test_the_digest_is_built_after_the_panels_it_reads():
    """Built before `why` it would have no attribution to name, and the lede
    would degrade to the bare price move on every symbol."""
    order = [MAIN.index('payload["%s"] = pulse_mod.%s(' % (k, fn))
             for k, fn in (("pulse", "pulse"), ("why", "why"), ("digest", "digest"))]
    assert order == sorted(order), "digest must be assembled after pulse and why"
    # Exactly one place builds it. Two call sites is how the endpoint and the
    # scheduler come to disagree about what a payload contains.
    assert MAIN.count("pulse_mod.digest(") == 1


def test_the_client_leads_with_the_lede_and_not_a_stance_chip():
    """A 32px duplicate of a word already in the sentence is the same fault
    removed from the price header and the status strip in this pass."""
    fn = APP_JS.split("function renderOpticPulse(d) {", 1)[1].split("\nfunction ", 1)[0]
    assert 'class="pl-lede' in fn
    assert "pl-stance" not in fn, "the sentence already contains the stance word"
    assert "pl-stance" not in CSS, "and the rule for it is now dead"


def test_the_factor_bars_are_always_shown():
    """They were behind a "How the N inputs scored" summary and are not any
    more.

    They are the measured part, and the skill note beside them is this
    project's own finding that the blend does not beat raw momentum. A toggle
    over the one section that qualifies everything above it makes the default
    view of this panel the confident half with the evidence hidden — which is
    the opposite of the reason the disclosure was added."""
    fn = APP_JS.split("function renderOpticPulse(d) {", 1)[1].split("\nfunction ", 1)[0]
    assert '<section class="pl-bars"' in fn
    assert "pl-factors" in fn and "pl-skill" in fn
    assert "<details" not in fn.split("pl-bars")[1], \
        "the bars must not be behind a disclosure again"
    assert "inputs scored</summary>" not in fn

    # The summary carried the group's name for a screen reader; without it the
    # five rows are an unlabelled grid, so the name moves to the container.
    assert 'aria-label="How the ${p.factors_total || 5} inputs scored"' in fn

    # And the rules for the summary are gone rather than left dark.
    assert ".pl-bars > summary" not in CSS
    assert ".pl-bars[open]" not in CSS
    assert ".pl-bars { margin-top:" in CSS, \
        "the spacing the summary used to contribute has to come from somewhere"


def test_the_lede_carries_direction_as_a_rule_not_a_repeated_word():
    assert ".pl-lede.is-bullish { border-left-color: var(--pos); }" in CSS
    assert ".pl-lede.is-bearish { border-left-color: var(--neg); }" in CSS


def test_the_tier_badge_shrink_wraps_inside_the_story_grid():
    """It is inline-block everywhere else, but as a grid item it took the
    column: measured at 660px in a 681px row, so "BREAKING" rendered as a
    full-width outlined bar above the headline."""
    assert ".pl-story > .nw-tier { justify-self: start; }" in CSS


def test_the_follow_ups_reuse_the_home_pages_question_pattern():
    """`cc-qs` / `cc-q` already had exactly this — text buttons, one per line,
    seeded from live data. A second visual language for "a question you can
    ask" would be the duplicate this pass exists to remove."""
    fn = APP_JS.split("function renderFollowUps(d) {", 1)[1].split("\nfunction ", 1)[0]
    assert 'class="cc-qs"' in fn and 'class="cc-q"' in fn
    assert "data-ask-text" in fn, "the existing handler, not a new one"


def test_the_follow_up_block_renders_in_the_swing_view():
    assert "${renderFollowUps(d)}" in APP_JS
