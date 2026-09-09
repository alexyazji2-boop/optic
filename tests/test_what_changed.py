"""What changed on a symbol since the last time it was opened.

Nothing on the server keeps per-symbol state: `/api/snapshots` is ledger
backups. So the client stores a handful of comparable readings under each
symbol on load and diffs against them on the next visit.

**The composite score is deliberately not compared.** It is the obvious
candidate and it sits right beside the readings that are. Optic's own evaluate
module reports that the composite "does not beat a single raw momentum number
at 3 of 3 horizons... the weights are decoration rather than signal", so a line
saying the score moved from 48 to 55 would be reporting movement in a number
the app has measured to carry no information. That finding is why the stance
panel has no 0-100 headline either, and this respects the same decision.
"""

from __future__ import annotations

import re

APP_JS = open("static/app.js").read()
CSS = open("static/styles.css").read()


def _fn(name: str) -> str:
    start = APP_JS.index("function %s(" % name)
    nxt = APP_JS.find("\nfunction ", start + 1)
    return APP_JS[start:nxt if nxt > 0 else len(APP_JS)]


def test_the_prior_snapshot_is_read_before_the_new_one_is_written():
    """Writing first overwrites the thing being compared against, and the diff
    is then always empty."""
    fn = _fn("loadSwing")
    assert fn.index("STATE.priorSnapshot = priorSnapshot(") < fn.index("writeSnapshot(")


def test_the_composite_score_is_not_in_the_snapshot():
    """The measured finding. It would otherwise be the first field anyone
    reached for."""
    fn = _fn("snapshotOf")
    assert "composite" not in fn
    assert "composite_score" not in fn
    # And the panel says why, so the omission is not mistaken for an oversight.
    assert "does not beat a single momentum number" in _fn("renderWhatChanged")


def test_the_snapshot_only_holds_readings_the_app_already_stands_behind():
    fn = _fn("snapshotOf")
    for field in ("price", "stance", "conviction", "bias", "trend",
                  "revisions", "earnings"):
        assert "%s:" % field in fn, field


def test_a_same_session_visit_has_nothing_to_say():
    """Verified live: a snapshot minutes old yields no block. Four hours rather
    than a day so an overnight gap still counts."""
    assert "SNAP_MIN_AGE_MS = 4 * 3600 * 1000" in APP_JS
    fn = _fn("priorSnapshot")
    assert "age < SNAP_MIN_AGE_MS" in fn


def test_a_corrupt_timestamp_is_treated_as_no_snapshot():
    """Not as an infinitely old one, which would report every reading as
    changed on the first load after a bad write."""
    fn = _fn("priorSnapshot")
    assert "!Number.isFinite(age)" in fn


def test_a_first_visit_renders_nothing():
    """Verified live on a symbol never opened: no block, and a snapshot written
    for next time."""
    fn = _fn("renderWhatChanged")
    assert "if (!prev) return '';" in fn


def test_no_changes_renders_nothing_rather_than_an_empty_card():
    """A block that is always there and usually empty is furniture."""
    assert "if (!changes.length) return '';" in _fn("renderWhatChanged")


def test_a_reading_missing_on_either_visit_is_not_a_change():
    """"undefined became bullish" is not news. This is why the diff is a list of
    small checks rather than a loop over keys."""
    fn = _fn("changesBetween")
    assert "const both = (a, b) =>" in fn
    assert fn.count("both(prev.") >= 6


def test_a_price_wobble_is_not_reported():
    """Below a quarter of a percent, saying so fills the block on a day nothing
    happened."""
    fn = _fn("changesBetween")
    assert "Math.abs(pct) >= 0.25" in fn


def test_the_trend_score_needs_a_real_move():
    """It is a 0-100 reading that drifts a point or two on its own."""
    assert "Math.abs(now.trend - prev.trend) >= 10" in _fn("changesBetween")


def test_the_store_cannot_grow_without_bound():
    fn = _fn("writeSnapshot")
    assert "SNAP_MAX" in fn
    # Sorted on the timestamp, because JSON round-tripping does not preserve
    # insertion order as a record of age.
    assert "Date.parse(store[a].at" in fn


def test_a_hand_edited_store_cannot_break_the_read():
    fn = _fn("snapshotStore")
    assert "typeof raw === 'object'" in fn
    assert "!Array.isArray(raw)" in fn
    assert "catch (e) { return {}; }" in fn


def test_private_mode_costs_the_history_not_the_page():
    assert "catch (e) { /* private mode: no history, so no what-changed block */ }" \
        in _fn("writeSnapshot")


def test_the_since_wording_scales():
    fn = _fn("sinceWords")
    for word in ("yesterday", "days ago", "weeks ago", "months ago"):
        assert word in fn, word


def test_it_sits_between_the_price_and_the_reads():
    """The first question on a return visit is what was missed, and the answer
    has to arrive before the panels that would have to be re-read to work it
    out."""
    view = APP_JS[APP_JS.index("${renderPriceHead(d, extQ)}"):]
    view = view[:view.index("${renderWhyMoving(d)}")]
    assert view.index("renderWhatChanged") < view.index("renderOpticPulse")


def test_the_ask_topic_exists():
    """The both-directions check would catch this, but naming it here says what
    the button is for."""
    assert "askPulse('whatchanged')" in APP_JS
    assert "whatchanged: " in APP_JS


def test_every_class_it_renders_has_a_rule():
    used = {tok for attr in re.findall(r'class="([^"]*)"', _fn("renderWhatChanged"))
            for tok in attr.split() if tok.startswith("wc-")}
    assert {"wc-block", "wc-since", "wc-list", "wc-label", "wc-text"} <= used, used
    for cls in used:
        assert ".%s" % cls in CSS, cls


def test_no_em_dashes_in_the_copy():
    fn = _fn("renderWhatChanged")
    body = re.sub(r"/\*.*?\*/", "", fn, flags=re.S)
    for text in re.findall(r">([^<>{}]{16,})<", body):
        assert "—" not in text, text
