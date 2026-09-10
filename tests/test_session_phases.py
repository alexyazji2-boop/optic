"""Every session phase the server can publish must render as words.

Written after the chip rendered the literal string "undefined" beside a beating
dot, every night from 8pm to 4am Eastern. `SESSION_LABEL` in app.js had three
keys — regular, pre, after — and `marketSessionET` returns five: app/session.py
also publishes `overnight` and `closed`, plus `holiday` which folds into closed.
Nothing threw. The template just interpolated a missing key.

This is the same shape of bug as switchView's ticker allow-list: a map keyed on
a server-side enum, maintained by hand, with no test tying the two together. So
the test is the tie.
"""

from __future__ import annotations

import re
from pathlib import Path

from app import session

APP_JS = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()

# The two the JS handles before it reaches the map: 'holiday' is folded into
# 'closed' by marketSessionET, and 'closed' has its own branch with its own copy.
HANDLED_SEPARATELY = {"closed", "holiday"}


def _labels() -> dict:
    block = APP_JS.split("const SESSION_LABEL = {", 1)[1].split("\n};", 1)[0]
    return dict(re.findall(r"^\s*(\w+):\s*'([^']*)'", block, re.M))


def test_every_phase_the_server_publishes_has_a_label():
    missing = sorted(set(session.LABELS) - HANDLED_SEPARATELY - set(_labels()))
    assert missing == [], (
        f"marketSessionET can return {missing} and SESSION_LABEL has no entry, "
        "so the chip renders 'undefined'")


def test_the_label_map_invents_no_phase_of_its_own():
    extra = sorted(set(_labels()) - set(session.LABELS))
    assert extra == [], f"SESSION_LABEL keys that no phase produces: {extra}"


def test_the_closed_branch_still_handles_holidays_by_name():
    body = APP_JS.split("function liveIndicatorHTML(", 1)[1].split("\nfunction ", 1)[0]
    assert "marketHolidayName()" in body
    assert "market closed" in body


def test_a_missing_key_can_never_render_as_undefined_again():
    """The map is the fix; the fallback is the seatbelt. A phase added server-side
    should degrade to its own name, not to a word that looks like a crash."""
    body = APP_JS.split("function liveIndicatorHTML(", 1)[1].split("\nfunction ", 1)[0]
    assert "SESSION_LABEL[session] ||" in body, "no fallback behind the lookup"


def test_overnight_does_not_claim_to_be_refreshing():
    """The feed has no Blue Ocean tape. session.py says so as feed_covers_phase;
    the chip must not say the opposite two inches away."""
    label = _labels()["overnight"]
    assert "refreshing" not in label.lower()
    assert "does not carry" in label.lower()


def test_the_live_tape_predicate_excludes_overnight():
    """The other half of the same finding.

    `isTapeLiveET` was `marketSessionET() !== 'closed'`, and overnight sits
    between the after-hours close and the pre-market open. Two consumers, both
    wrong the same way from 8pm to 4am Eastern: tickAutoRefresh re-requested the
    swing payload every twenty seconds against a feed that does not carry the
    session, and setChartLive pulsed the chart's leading dot — against the
    argument in setChartLive's own comment, that "a dot that blinks while the
    market is shut is telling the reader something untrue".
    """
    body = APP_JS.split("function isTapeLiveET() {", 1)[1].split("\n}", 1)[0]
    assert "TAPE_LIVE_PHASES.includes" in body
    phases = re.findall(r"'(\w+)'", APP_JS.split("const TAPE_LIVE_PHASES = [", 1)[1]
                        .split("];", 1)[0])
    assert phases == ["regular", "pre", "after"], phases
    assert "overnight" not in phases
    assert "closed" not in phases


def test_the_live_predicate_is_an_allow_list():
    """A phase added server-side should default to "not delivering prices". The
    cost of that mistake is a missed refresh; the cost of the other one is a page
    that says it is live when nothing is arriving."""
    body = APP_JS.split("function isTapeLiveET() {", 1)[1].split("\n}", 1)[0]
    assert "!==" not in body, "back to a deny-list, so a new phase reads as live"


def test_the_two_consumers_share_one_predicate():
    """setChartLive is called from a dozen sites and tickAutoRefresh from one.
    Both are asking the same question, so a second predicate would be a second
    thing to get wrong."""
    assert APP_JS.count("setChartLive(isTapeLiveET())") >= 10
    block = APP_JS.split("function tickAutoRefresh()", 1)[1][:400]
    assert "!isTapeLiveET()" in block


def test_only_a_covered_session_gets_the_beating_dot():
    """The pulse is the page's one animated element and it means prices are
    arriving. Overnight they are not."""
    body = APP_JS.split("function liveIndicatorHTML(", 1)[1].split("\nfunction ", 1)[0]
    assert "session === 'overnight' ? ''" in body, "overnight still pulses"


def test_the_covered_sessions_still_do():
    """The other half of the same rule — a fix that killed the pulse everywhere
    would pass the test above and lose the live indicator."""
    body = APP_JS.split("function liveIndicatorHTML(", 1)[1].split("\nfunction ", 1)[0]
    assert "pulse-beat" in body
    for phase in ("regular", "pre", "after"):
        assert "refreshing" in _labels()[phase]
