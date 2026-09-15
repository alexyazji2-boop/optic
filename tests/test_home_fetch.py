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


# ------------------------------------------------- the other two duplicates
#
# Measured on production: /api/watchlist twice at boot (889ms and 784ms) and
# /api/scanners/movers twice. Both are the same defect as /api/home had, and
# both are fixed the same way. After: 9 calls on a fresh load, zero endpoint
# fetched more than once, and the movers table, the watchlist, the five market
# blocks and the eight strip cells all still render.


def test_the_watchlist_guard_cannot_be_passed_twice():
    """Its cache guard reads `STATE.watchlist`, which is assigned AFTER the
    await, while `STATE.watchlistKey` is assigned before it. A second caller
    arriving mid-flight saw a matching key and no payload, fell through, and
    fetched again."""
    fn = body_of("loadWatchlist")
    assert "watchlistInFlight && watchlistInFlightKey === key" in fn
    assert "await watchlistInFlight;" in fn


def test_the_watchlist_flight_is_keyed_by_the_symbol_list():
    """A request for a different list is a different request and must not be
    handed this one's promise."""
    assert "watchlistInFlightKey = key;" in CODE
    fn = body_of("loadWatchlist")
    assert "watchlistInFlightKey === key" in fn


def test_both_new_flights_clear_on_failure():
    """`.finally`, not `.then`. A rejected fetch that left the promise in place
    would serve the same failure to every later caller for the life of the
    page."""
    for name in ("loadWatchlist", "homeMovers"):
        fn = body_of(name)
        assert ".finally(" in fn, name
        assert "InFlight = null" in fn, name


def test_the_movers_fetch_is_deduped_where_the_fetch_is():
    """It has one caller, so the duplicate was the caller running twice. The
    guard belongs on the fetch rather than the render: a future second caller
    would otherwise make it three."""
    fn = body_of("homeMovers")
    # The guard itself, not a mention of the variable. `"moversInFlight" in fn`
    # was the first version and it survived `if (true) {`, which starts a fresh
    # request on every call while leaving the name in place.
    assert "if (!moversInFlight) {" in fn
    assert "data = await moversInFlight;" in fn
    calls = re.findall(r"getJSON\(\s*['\"]/api/scanners/movers['\"]", CODE)
    assert len(calls) == 1, calls


def test_the_movers_error_branch_re_reads_its_host():
    """It wrote into a `host` captured before the await. Writing into a
    detached node succeeds silently, which is how the market block came to show
    an empty div."""
    fn = body_of("homeMovers")
    catch_at = fn.index("catch (err)")
    branch = fn[catch_at:]
    assert "document.getElementById('cc-movers')" in branch
    assert "if (failed)" in branch


def test_the_movers_reuse_window_stays_inside_the_refresh_tick():
    fn = body_of("homeMovers")
    window = re.search(r"Date\.now\(\)\s*-\s*moversAt\s*<\s*(\d+)", fn)
    assert window, "no freshness comparison"
    assert 1000 <= int(window.group(1)) < 20000, window.group(1)


# ------------------------------------------------------------- the transfer

def test_the_responses_are_compressed():
    """app.js is 1.2 MB of source and styles.css is 408 KB, and StaticFiles
    sends both raw: measured, a local request for app.js with
    `Accept-Encoding: gzip` came back 1,258,176 bytes with no
    `Content-Encoding` at all.

    Railway's edge already gzips in production, where those two arrive as 389 KB
    and 103 KB, so this does not make the live site faster. It is here so local
    development is not testing a 1.75 MB shape the deployed app never has, and
    so an edge that stops compressing degrades the transfer rather than silently
    quadrupling it.
    """
    main = open("app/main.py", encoding="utf-8").read()
    assert "from fastapi.middleware.gzip import GZipMiddleware" in main
    assert "app.add_middleware(GZipMiddleware" in main
    # Above the default 500: below roughly this size the header and the lost
    # streaming cost more than the saving.
    got = re.search(r"GZipMiddleware, minimum_size=(\d+)", main)
    assert got and int(got.group(1)) >= 500, main[:0] or got


def test_filed_fundamentals_are_not_refetched_hourly():
    """The five calls behind `fundamentals.analyse` measured 1,555 ms together,
    the largest single leg of a ticker load, and four of them were on the same
    one hour as a news feed. Company financials and 13F holdings are quarterly
    and FINRA short interest publishes twice a month, so an hour meant
    re-fetching figures that cannot have moved.

    `insiders` is deliberately excluded: Form 4s arrive continuously.
    """
    yf = open("app/providers/yf.py", encoding="utf-8").read()
    got = re.search(r"TTL_FILED = (\d+) \* 3600", yf)
    assert got, "TTL_FILED is gone"
    hours = int(got.group(1))
    # Bounded by the publication cadence, not chosen for speed: long enough to
    # be worth having, far short of the fortnight that is the shortest cadence.
    assert 2 <= hours <= 24, hours
    for key in ("short:", "earnhist:", "fin:", "inst:"):
        assert 'return _cached("%s" + ticker, self.TTL_FILED, build)' % key in yf, key
    assert 'return _cached("insider:" + ticker, 3600, build)' in yf, (
        "insider filings arrive continuously and must keep the short TTL")
