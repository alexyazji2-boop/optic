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
    """The chip must never imply a single stock's price is moving when it is a
    4pm close. That property is unchanged; the fact under it moved.

    This read "single stocks are not [live]" because the feed had no overnight
    tape for them. It does now, for the names an overnight venue has printed --
    app/providers/overnight.py, measured live across twenty names on
    2026-10-04, all twenty printed within minutes. So "single stocks are not"
    became false for most of them, and whether one is live is a fact about
    that name rather than about the session.

    So the static label, which is what a view about no single name falls back
    to, now claims only what is true of the session: the futures. The per-name
    claim -- live with the venue named for a name that printed, "no venue has
    printed this name tonight" for one that did not -- is asserted by running
    liveIndicatorHTML in tests/test_client_loading.py."""
    label = _labels()["overnight"].lower()
    assert "refreshing" not in label
    assert "futures are live" in label
    assert "stocks are live" not in label, "the session label claims every stock"


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
    arriving. Overnight they arrive for a name a venue has printed tonight, and
    for nothing else -- so the overnight guard is tied to that print rather
    than to the phase alone. Exercised for real in tests/test_client_loading.py;
    this checks the guard is still keyed on the print."""
    body = APP_JS.split("function liveIndicatorHTML(", 1)[1].split("\nfunction ", 1)[0]
    assert "session === 'overnight' && !night ? ''" in body, \
        "overnight pulses without a print, or never pulses with one"


def test_the_covered_sessions_still_do():
    """The other half of the same rule — a fix that killed the pulse everywhere
    would pass the test above and lose the live indicator."""
    body = APP_JS.split("function liveIndicatorHTML(", 1)[1].split("\nfunction ", 1)[0]
    assert "pulse-beat" in body
    for phase in ("regular", "pre", "after"):
        assert "refreshing" in _labels()[phase]


# ------------------------------------------- the pulse, per instrument
#
# `isTapeLiveET` answers for a US stock, and it was the only answer available,
# so the instrument view asked it about gold, bitcoin and the E-mini too. The
# report was a Sunday evening: ES=F trading, the equity phase reading "closed",
# and the chart's leading dot sitting still on a price that was moving.


def _fn(name: str) -> str:
    """One function's body, comments stripped.

    Stripped because this file is about to assert that a symbol suffix appears
    in a branch, and every one of those suffixes is also named in the prose
    explaining the branch. Three tests elsewhere in this repo have passed on
    their own comments.
    """
    body = APP_JS[APP_JS.index("function " + name + "("):]
    body = body[:body.index("\n}") + 2]
    body = re.sub(r"/\*.*?\*/", " ", body, flags=re.S)
    return re.sub(r"^\s*//.*$", " ", body, flags=re.M)


def test_the_futures_week_comes_from_the_server():
    """CLAUDE.md's rule: calendar logic does not go on the client. That
    duplication is what made the app report a regular session on Labor Day."""
    fn = _fn("isFuturesTapeLive")
    assert "STATE.session" in fn and "futures" in fn
    assert "getDay" not in fn and "getHours" not in fn, "a clock crept in"


def test_an_unloaded_payload_does_not_pulse():
    """False until the answer arrives, and the asymmetry is the argument: a
    missed pulse costs nothing, a pulse on a shut market is the page telling
    the reader something untrue."""
    fn = _fn("isFuturesTapeLive")
    assert "!!(fut && fut.is_open)" in fn


def test_a_future_follows_the_futures_week_and_a_stock_does_not():
    fn = _fn("chartLiveForSymbol")
    assert "'=F'" in fn and "isFuturesTapeLive()" in fn
    assert "isTapeLiveET()" in fn, "everything else still follows the cash session"


def test_crypto_never_closes():
    fn = _fn("chartLiveForSymbol")
    assert "'-USD'" in fn
    assert "return true" in fn


def test_fx_is_left_on_the_cash_session_on_purpose():
    """It trades Sunday 5:00pm to Friday 5:00pm, an hour wider than the CME
    week. Claiming a window an hour early is the expensive mistake, so FX gets
    no overnight pulse until its week is modelled as exactly as the CME one."""
    fn = _fn("chartLiveForSymbol")
    assert "'=X'" not in fn, "FX must not borrow the futures week"


def test_the_instrument_chart_sets_the_flag_itself():
    """`liveNextChart` is a module global in charts.js that every chart's
    loader sets before drawing. This one never did, so it inherited whichever
    value the last view rendered left behind -- the dot pulsed or sat still
    depending on where the reader had just been, which is worse than either
    answer because it is not repeatable."""
    fn = _fn("drawInstrumentChart")
    assert "setChartLive(chartLiveForSymbol(" in fn


def test_the_server_publishes_what_the_client_reads():
    """The tie, in the shape this file was written for: a client reading
    `futures.is_open` against a server that publishes it."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    payload = session.state(datetime(2026, 9, 27, 18, 44, tzinfo=ZoneInfo("America/New_York")))
    assert "futures" in payload
    assert payload["futures"]["is_open"] is True
    assert payload["phase"] == "closed", "and the two disagree, which is the point"
