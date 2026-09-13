"""The inbox where a fired watch is read.

The payoff half of the feature. The runner writes hits server-side; this is the
only surface that answers "did anything happen on the names I care about", and
without it the runner was a job nobody could see the output of.

Client contracts, so they read `static/*.js` as text. Comments are stripped
first: the region carries a long rationale and several of these phrases appear
in it, which is how a test comes to pass by matching its own explanation.
"""

import re

APP_JS = open("static/app.js", encoding="utf-8").read()
CSS = open("static/styles.css", encoding="utf-8").read()


def strip_comments(js):
    js = re.sub(r"/\*.*?\*/", " ", js, flags=re.S)
    return re.sub(r"(?<!:)//[^\n]*", " ", js)


CODE = strip_comments(APP_JS)


def mark_read_handler():
    """The click handler, found by its selector call rather than by the first
    appearance of the attribute: the attribute is in the button's markup too,
    two hundred lines above, and slicing from there reads the template."""
    start = CODE.index("closest('[data-hits-seen]')")
    # To a `});` at the start of a line. A bare "});" first matches inside
    # `body: {} });` on the fetch call, which cuts the slice three lines in and
    # hides everything this is checking for.
    return CODE[start:CODE.index("\n});", start)]


def body_of(name):
    start = CODE.index("function %s(" % name)
    return CODE[start:].split("\nfunction ", 1)[0]


def test_the_inbox_renders_above_the_builder():
    """A reader opening this tab is asking what happened, not what to set up
    next. Every branch of renderAlerts, because the scan feed failing must not
    take their own alerts down with it."""
    render = body_of("renderAlerts")
    assert render.count("renderWatchHits()") == 3, "one branch is missing it"
    for chunk in render.split("renderWatchHits()")[1:]:
        head = chunk[:80]
        assert "renderWatchesBlock()" in head, (
            "the builder must follow the inbox, not precede it")


def test_a_guest_is_told_why_nothing_accumulates():
    """A hit is written by a scheduled job against a stored watch, so there has
    to be a row to store it against. Silence here would read as an empty inbox,
    which is a different and wrong claim."""
    fn = body_of("renderWatchHits")
    assert "if (!signedIn())" in fn
    assert "live in this browser" in fn


def test_an_empty_inbox_says_it_is_the_ordinary_state():
    """A watch that has not fired is the common case, and a bare "nothing here"
    invites the reader to assume nothing was checked."""
    fn = body_of("renderWatchHits")
    assert "not that nothing was checked" in fn


def test_unread_is_marked_twice():
    """Colour alone is the only signal for a reader who cannot see it, and this
    list is the one place in the app where missing a row is the whole failure."""
    assert ".wh-row.is-new { border-left-color:" in CSS
    fn = body_of("watchHitRow")
    assert "wh-new" in fn and "Unread" in fn


def test_marking_read_does_not_delete():
    """Read and gone are different states. A reader who marks all read and then
    wants to see what fired yesterday has to still have it."""
    seen = mark_read_handler()
    assert "h.seen = 1" in seen
    assert "splice" not in seen and "= []" not in seen


def test_marking_read_repaints_from_local_state():
    """The server is the authority and has already agreed. A refetch would
    repaint a beat later, which reads as the button having lagged."""
    seen = mark_read_handler()
    assert "loadWatchHits" not in seen
    assert "paintWatchHitBadge()" in seen


def test_the_phone_tab_carries_the_unseen_count():
    """The bottom bar is the only route to this inbox on a phone, and a tab that
    looks identical whether or not something fired is one nobody taps."""
    fn = body_of("paintWatchHitBadge")
    assert "[data-mtab=\"alerts\"]" in fn
    assert "STATE.watchHits" in fn


def test_the_badge_counts_only_the_readers_own():
    """The scheduled-scan feed below the inbox belongs to the deployment rather
    than to them. Counting it on their tab would be the badge lying about whose
    news it is."""
    fn = body_of("paintWatchHitBadge")
    assert "STATE.alerts" not in fn


def test_the_badge_is_positioned_out_of_the_flow():
    """The tab is a grid of two fixed rows. A third item would resize every tab
    in the bar the moment one alert fired."""
    rule = CSS[CSS.index(".mtab-badge {"):]
    rule = rule[:rule.index("}")]
    assert "position: absolute" in rule


def test_the_inbox_is_fetched_beside_the_scan_feed_not_inside_it():
    """Two endpoints with no dependency on each other. A reader whose scan feed
    is unreachable still needs to see what their own watches did."""
    fn = body_of("loadAlertsFeed")
    assert fn.index("loadWatchHits(force)") < fn.index("getJSON('/api/alerts')")


def test_a_failed_fetch_does_not_blank_the_section():
    fn = body_of("loadWatchHits")
    assert "STATE.watchHits = { error: err.message }" in fn
    render = body_of("renderWatchHits")
    assert "state.error" in render and "errorHTML" in render
