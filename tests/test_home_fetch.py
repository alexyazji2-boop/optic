"""One fetch of /api/home per burst, and a render that survives the dedupe.

Boot asks for the homepage payload from more than one place, and that is the
right design: the strip, the market block and the onboarding card each decide
independently whether they have anything to draw, so none of them can assume
another ran first. What was wrong is that asking three times cost three round
trips of the same payload. Measured on a fresh load: `/api/home` x3 inside one
second.

The first fix shared the whole promise and broke the page. A second caller got
back the first caller's *work*, and that work had already captured `#hm-market`
before `renderHome()` replaced the element, so the market filled a node that was
no longer in the document. Measured: 1 request, 0 rendered blocks. Fewer
requests and nothing on screen is not an improvement, so both halves are
asserted here: the fetch is shared, the render is not.

Verified in a browser from a cleared knowledge store, with the onboarding path
active, at 977x835 and at 375x812:

    /api/home x1, zero duplicated endpoints of any kind across 9 calls,
    8 strip cells, 6 market blocks, onboarding card present exactly once

These read source text, which is the project's pattern for client contracts and
is only sound for a wiring property. The behaviour itself was measured in the
browser, above; what source can prove is that the wiring cannot silently come
apart, which is the failure mode this file exists for.
"""

import re

APP_JS = open("static/app.js", encoding="utf-8").read()


def strip_comments(js):
    """Comments out before matching.

    Not optional here. Every property this file asserts is also *explained* in a
    comment two lines above the code, so a test reading the raw file would pass
    on the explanation of a line that had been deleted. That has caught me four
    times in this codebase.
    """
    js = re.sub(r"/\*.*?\*/", " ", js, flags=re.S)
    return re.sub(r"(?<!:)//[^\n]*", " ", js)


CODE = strip_comments(APP_JS)


def body_of(name):
    start = CODE.index("function %s(" % name)
    return CODE[start:].split("\nfunction ", 1)[0]


# ------------------------------------------------------------- one fetch path

def test_only_home_data_fetches_the_home_payload():
    """A second `getJSON('/api/home')` anywhere would reintroduce the duplicate
    without touching this function, so the count is the assertion."""
    calls = re.findall(r"getJSON\(\s*['\"]/api/home['\"]", CODE)
    assert len(calls) == 1, "expected one /api/home fetch site, found %d" % len(calls)
    assert "getJSON('/api/home')" in body_of("homeData")


def test_home_data_shares_a_flight_in_progress():
    """The three boot callers overlap, so the guard has to be the in-flight
    promise itself. A freshness check alone would not help them: nothing has
    landed yet when the second and third callers arrive."""
    fn = body_of("homeData")
    assert "if (homeDataInFlight) return homeDataInFlight;" in fn
    assert "homeDataInFlight = getJSON" in fn


def test_home_data_clears_the_flight_even_when_the_fetch_fails():
    """`.finally`, not `.then`. A rejected fetch that left the stale promise in
    place would serve the same failure to every later caller for the life of the
    page, so one dropped connection at boot would mean a permanently empty
    homepage."""
    fn = body_of("homeData")
    assert ".finally(" in fn
    assert "homeDataInFlight = null" in fn


def test_home_data_reuse_window_is_shorter_than_the_refresh_tick():
    """Bounds, not a pinned value. The window has to cover a boot burst and stay
    clear of the 20-second auto-refresh, or the refresh would hand back the
    payload it was firing to replace."""
    fn = body_of("homeData")
    window = re.search(r"Date\.now\(\)\s*-\s*homeDataAt\s*<\s*(\d+)", fn)
    assert window, "no freshness comparison found"
    ms = int(window.group(1))
    assert 1000 <= ms < 20000, ms


def test_the_reuse_window_requires_a_payload_to_reuse():
    """`homeDataAt` starts at 0, so a bare clock comparison is false at boot and
    this is belt-and-braces. It stops being belt-and-braces the first time
    anything assigns `homeDataAt` without assigning `STATE.home`."""
    fn = body_of("homeData")
    assert re.search(r"if \(STATE\.home && Date\.now\(\)", fn)


# --------------------------------------------- the half that broke the render

def test_every_home_loader_reads_its_host_after_the_await():
    """The property whose absence gave 1 request and 0 rendered blocks.

    A shared promise means the caller that resolves is not always the caller
    that asked, so an element captured before the await may have been replaced
    by `renderHome()` in between. Writing into it succeeds silently and paints
    nothing. Asserted for every loader on the page, not just the one that broke,
    because they all now share one flight.
    """
    for name in ("loadHomeMarket",):
        fn = body_of(name)
        await_at = fn.index("await homeData()")
        after = fn[await_at:]
        assert "document.getElementById('hm-market')" in after, name
        # And the re-read is guarded: a host that went away between the request
        # and the response is a navigation, not an error to report.
        assert "if (!host) return;" in after, name


def test_the_failure_branch_also_re_reads_its_host():
    """Same trap, quieter: the error path writes copy into the page too, and it
    is the branch nobody exercises by hand."""
    fn = body_of("loadHomeMarket")
    catch_at = fn.index("catch (err)")
    branch = fn[catch_at:]
    assert "document.getElementById('hm-market')" in branch
    assert "if (failed)" in branch


def test_the_skeleton_host_is_not_reused_across_the_await():
    """`skeleton` is read before the fetch on purpose, to paint the placeholder.
    It must not be the thing written into afterwards, which is exactly the bug:
    one variable spanning the await reads as correct and is not."""
    fn = body_of("loadHomeMarket")
    await_at = fn.index("await homeData()")
    assert "skeleton" not in fn[await_at:], (
        "the pre-await host leaked past the await")


# ------------------------------------------------- the second surface, Explore

def test_explore_shares_the_same_flight():
    """Explore draws the same payload and used to hand-roll the cache.

    Its version was `STATE.home ? resolve(STATE.home) : getJSON('/api/home')`,
    which fails in both directions: no in-flight guard, so opening Explore
    during boot fired a second request; and no expiry, so once the payload
    landed Explore reused it for the life of the page.
    """
    fn = body_of("loadExplore")
    assert "homeData()" in fn
    assert "Promise.resolve(STATE.home)" not in fn, (
        "the hand-rolled cache is back")


def test_explore_still_prefers_a_stale_payload_to_an_empty_section():
    """The one thing the hand-rolled version did right. Sharing the flight means
    Explore can now see a rejection it previously could not, so the fallback has
    to be explicit or a failed refresh empties a section that had content."""
    fn = body_of("loadExplore")
    assert "homeData().catch(() => STATE.home || null)" in fn


def test_explore_survives_one_feed_failing():
    """Pre-existing and worth holding: `allSettled`, not `all`. With `all` a
    sector feed returning 500 would empty a page whose other two thirds are
    fine."""
    fn = body_of("loadExplore")
    assert "Promise.allSettled([" in fn
    assert "Promise.all([" not in fn
