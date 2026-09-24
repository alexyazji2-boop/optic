"""Colour on a catalyst means the headlines leaned, not the type.

Asked for as "red or green on whether they are bullish or bearish, if
suitable". The qualifier is the whole of it, because a catalyst *type* has no
direction and colouring it by type would be the easy, wrong version:

  analyst action     matches "upgrade" and "downgrade" on one pattern
  management change  matches "appoint" and "resign"
  earnings           a beat and a miss
  guidance           raised and cut
  capital return     a buyback and a dividend cut
  macro event        nothing directional at all

What is real is the sentiment already scored on each headline. So a type
inherits the lean of the stories it was actually found in. Measured on QCOM:
`analyst action` came back bearish at -2.0 because the one story carrying it
read bearish -- that was a downgrade, and the colour is right for the reason
that makes it right. `commercial deal` averaged -1.0 across a neutral and a
bearish story. `management change`, `product news` and `macro event` stayed
neutral, which is the honest answer when the headlines disagree.
"""

from __future__ import annotations

import re

APP = open("static/app.js", encoding="utf-8").read()
NEWS = open("app/news.py", encoding="utf-8").read()


from app.news import lean_from_scores


def _lean(scores):
    """The server's own rule, imported rather than restated.

    This was a reimplementation of the threshold, and a mutation that widened
    the real band -- every non-zero mean gets a colour -- passed against it.
    A test that carries its own copy of the rule it is testing cannot fail
    when the rule moves, which is the one thing a test about a threshold has
    to do."""
    return lean_from_scores(scores)["lean"]


def test_a_type_that_only_appeared_in_bearish_stories_leans_bearish():
    assert _lean([-2.0]) == "bearish"


def test_a_type_that_only_appeared_in_bullish_stories_leans_bullish():
    assert _lean([2.0, 3.0]) == "bullish"


def test_disagreeing_headlines_get_no_colour():
    """A type found in one bullish and one bearish story has not leaned. The
    honest colour there is no colour, not the average's rounding."""
    assert _lean([3.0, -3.0]) == "neutral"
    assert _lean([0.0]) == "neutral"


def test_the_band_matches_the_per_article_scale():
    """+/-1 is where the article scale already stops calling something
    neutral, so the chip and the headline beside it cannot disagree about
    whether a story leaned."""
    assert _lean([0.9]) == "neutral"
    assert _lean([1.0]) == "bullish"
    assert _lean([-1.0]) == "bearish"


def test_the_server_derives_the_lean_from_headline_scores():
    assert "catalyst_scores" in NEWS
    assert "sentiment_score" in NEWS.split("catalyst_scores", 1)[1][:600]
    # And it ships on every summary row.
    assert '"type": k, "mentions": v, **_lean(k)' in NEWS


def test_the_lean_is_named_apart_from_the_headlines_own_tone():
    """Two different things: a story has a `tone`, a catalyst type has a
    `lean` averaged across stories. One field name for both would invite
    reading the average as a reading of the type itself."""
    assert '"lean"' in NEWS and '"lean_score"' in NEWS


def test_the_client_colours_from_the_lean_and_not_from_the_type():
    fn = APP[APP.index("function catalystChip("):]
    fn = fn[:fn.index("\nfunction ")]
    assert "lean === 'bullish' ? 'bull'" in fn
    assert "lean === 'bearish' ? 'bear'" in fn
    # No mapping of catalyst names to colours anywhere in it.
    for kind in ("analyst action", "management change", "earnings", "guidance"):
        assert kind not in fn, "a type must not carry its own colour: " + kind


def test_a_row_chip_uses_its_own_headlines_tone():
    """At row level the reading is exact rather than averaged: a catalyst
    listed under a bearish story should not look neutral because the same type
    read bullish elsewhere. Verified in a browser -- "Commercial deal" renders
    grey under the neutral headline and red under the bearish one."""
    row = APP[APP.index("function newsArticleRow(a) {"):]
    row = row[:row.index("\n}")]
    # The tone has to reach the chip, not merely appear somewhere in the row --
    # `toneChip(a.tone)` is also in here, and an earlier version of this
    # assertion passed on that while the chip itself had been cut off from it.
    call = row[row.index("catalystChip("):]
    call = call[:call.index(".join(")]
    assert "a.tone" in call, "the chip call has to read the row's own tone"
    assert "bullish" in call and "bearish" in call


def test_the_summary_chip_uses_the_averaged_lean():
    block = APP[APP.index("Catalyst types detected"):][:600]
    assert "catalystChip(" in block
    assert "c.lean" in block


def test_the_chip_says_what_the_colour_means():
    """A red chip that looks like an error state, on a panel of neutral ones,
    needs to say it is a reading of the headlines rather than of the type."""
    fn = APP[APP.index("function catalystChip("):]
    fn = fn[:fn.index("\nfunction ")]
    assert "title=" in fn
    assert "headlines carrying this" in fn
    assert "no direction" in fn
