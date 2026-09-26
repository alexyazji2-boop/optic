"""The rail's empty half, and the cold start nobody should pay for.

Two separate complaints, both about a page that is not ready when you arrive.

**The rail.** Measured at 965px tall: the brand took 42px, the sections 313px
and the foot 90px, leaving 460px of nothing -- with Settings and Collapse
floating in the middle of it rather than sitting at the bottom, which is what
made it read as unfinished rather than as roomy. After this: 14px.

**The cold start.** /api/home is six legs, three of which reach the network.
Measured on the live server: 7.35s on the first request after a restart, 0.6s
on every one after it. The platform restarts on every deploy, so the first
person to open the site after a deploy paid all of it.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
CSS = (ROOT / "static/styles.css").read_text()
HTML = (ROOT / "static/index.html").read_text()
MAIN = (ROOT / "app/main.py").read_text()


def function(name):
    return re.search(r"^(?:async )?function " + name + r"\([^\n]*\) \{.*?^\}",
                     APP, re.M | re.S).group()


# ------------------------------------------------- the foot sits at the foot


def test_the_foot_is_pinned_to_the_bottom():
    """At `margin-top: var(--space-5)` it sat wherever the sections happened to
    end, and the rail's remaining height opened up underneath it."""
    block = CSS[CSS.index("the rail's space"):]
    rule = block[block.index(".rail-foot {"):]
    rule = rule[:rule.index("}")]
    assert "margin-top: auto" in rule


def test_the_rail_rules_do_not_reach_the_phone():
    """Below 560px the rail is a row along the bottom of the screen, where
    `margin-top: auto` pushes nothing useful and the phone block already sets
    `margin-top: 0`. That block sits EARLIER in this file, so an unscoped rule
    at the end would win on source order and undo it -- the first draft did
    exactly that."""
    block = CSS[CSS.index("the rail's space"):]
    opener = block[:block.index(".rail-foot {")]
    assert "@media (min-width: 560px)" in opener, \
        "the column-only rules must be scoped to the column layout"
    # And the phone rule it must not clobber is still there.
    assert ".rail-foot { margin-top: 0;" in CSS


def test_the_recents_hide_where_there_is_no_column_to_fill():
    """Collapsed the rail is icons only, and a row of bare symbols has no icon
    to collapse to; on the phone it is a row with no vertical space at all.

    Keyed on `body.rail-tight`, which is the class applyRail actually sets. A
    plausible-looking `.rail.is-collapsed` would have matched nothing and
    failed silently, which is the whole failure mode of a dead selector."""
    assert "body.rail-tight .rail .rail-recent { display: none; }" in CSS
    assert "classList.toggle('rail-tight'" in APP, "the class this depends on"
    tail = CSS[CSS.index("body.rail-tight .rail .rail-recent"):]
    assert "@media (max-width: 559px)" in tail


# ------------------------------------------------- what fills it


def test_it_shows_where_you_have_been_not_a_third_watchlist():
    """The watchlist is already a nav destination and a homepage panel. This
    app has a written rule about offering the same job twice on one screen --
    tests/test_home_and_nav_hierarchy.py is entirely about it -- and a third
    copy would be the clearest possible breach.

    Where you have just been is recorded nowhere on screen: the recents list
    existed only inside the command palette, behind a keystroke."""
    fn = function("railRecentHTML")
    assert "recentSymbols()" in fn
    assert "watchList()" not in fn and "STATE.watchlist" not in fn


def test_it_costs_no_request():
    """The rail is drawn on every page. Anything here that fetched would be a
    request per navigation, on the element that is supposed to be instant."""
    for name in ("railRecentHTML", "paintRailRecent"):
        fn = function(name)
        assert "getJSON" not in fn and "fetch(" not in fn, name
    # recentSymbols reads localStorage and nothing else.
    assert "localStorage.getItem(RECENT_KEY)" in function("recentSymbols")


def test_an_empty_list_says_so_rather_than_rendering_nothing():
    """An empty strip with no explanation reads as a panel that failed to load.
    One sentence makes it a space that is waiting."""
    fn = function("railRecentHTML")
    assert "rail-recent-none" in fn
    assert "Symbols you open show up here." in fn


def test_it_is_drawn_at_boot_and_not_only_on_a_view_change():
    """`switchView` repaints it, but the first page is rendered by `renderHome`
    directly rather than through switchView -- so on a cold arrival the strip
    was an empty div with no sentence in it. Measured: innerText was ''."""
    boot = APP[APP.index("mountPulseMarks();"):]
    boot = boot[:boot.index("updateStatus();")]
    assert "paintRailRecent();" in boot
    assert boot.index("paintRailRecent();") < boot.index("renderHome();")


def test_the_list_repaints_when_it_changes():
    """The rail is drawn once per navigation, not per symbol load, so opening a
    ticker would not have moved it until the next page change."""
    assert "paintRailRecent();" in function("rememberSymbol")
    assert "paintRailRecent();" in function("switchView")


def test_a_symbol_opened_from_the_rail_lands_where_a_searched_one_does():
    """Two entry points to the same destination that disagree is how "it opens
    the wrong tab" gets reported. loadTicker is the shared one; see
    SEARCH_LANDING."""
    i = APP.index("closest('[data-recent-symbol]')")
    block = APP[i:i + 500]
    assert "loadTicker(recentBtn.dataset.recentSymbol)" in block
    assert "SEARCH_LANDING" in APP


def test_the_host_exists_for_the_painter_to_find():
    assert 'id="rail-recent"' in HTML
    assert "getElementById('rail-recent')" in function("paintRailRecent")


# ------------------------------------------------- the cold start


def test_the_priority_board_is_cached_like_its_neighbour():
    """One of its four legs is the same ~150-call earnings scan that
    /api/earnings-week caches for an hour -- and that endpoint's own docstring
    says it "takes tens of seconds cold, which is far too slow for a tab a
    reader opens casually". This board is not a tab opened casually: it is on
    the landing page above the fold, and it had no cache at all.

    Timed cold, per leg: earnings 66.6s, events 3.9s, sectors 0.8s, movers
    0.01s. Measured on the live server: 42s."""
    assert "_PRIORITY_CACHE" in MAIN and "PRIORITY_TTL" in MAIN
    fn = MAIN[MAIN.index("async def priority_board()"):]
    fn = fn[:fn.index("\n\n\n")]
    assert 'hit = _PRIORITY_CACHE.get("board")' in fn
    assert "time.time() - hit[\"at\"]) < PRIORITY_TTL" in fn
    # Shorter than the hour its neighbour uses: the sector leg reads current
    # price against the prior session's range and is the one a reader could
    # catch being wrong. It rebuilds in 0.8s.
    ttl = float(re.search(r"PRIORITY_TTL = ([\d.]+)", MAIN).group(1))
    assert 300 <= ttl <= 1800, ttl


def test_the_home_payload_is_built_before_a_reader_asks():
    """7.35s on the first request after a restart, 0.6s after. This platform
    restarts on every deploy, and the landing page is the most requested
    endpoint in the app -- so the person who pays the cold cost is also the
    most likely one to exist."""
    assert "async def _warm_home()" in MAIN
    fn = MAIN[MAIN.index("async def _warm_home()"):]
    fn = fn[:fn.index("\n@app.on_event")]
    assert "await home_summary()" in fn
    # And the board, which is the slower of the two: timed cold, its earnings
    # leg alone is 66.6s against 0.02s for the whole build once warm, and the
    # live server served it in 42s.
    assert "await priority_board()" in fn
    # Started at boot, and held so it is not garbage-collected mid-flight:
    # asyncio keeps only a weak reference to a bare create_task.
    assert "app.state.warm_task = asyncio.create_task(_warm_home())" in MAIN


def test_the_warm_up_cannot_take_the_process_down():
    """It is a head start, not a dependency. Every leg of /api/home already
    reports its own absence when a reader asks for real, so a warm-up that
    raised would trade a slow first page for no pages at all."""
    fn = MAIN[MAIN.index("async def _warm_home()"):]
    fn = fn[:fn.index("\n@app.on_event")]
    assert "except Exception as exc:" in fn
    # But not the cancellation that shutdown sends it.
    assert "except asyncio.CancelledError:" in fn
    assert fn.index("except asyncio.CancelledError:") < fn.index("except Exception as exc:")


def test_the_warm_up_is_cancelled_on_shutdown():
    """A task still sleeping when the server is told to stop keeps the loop
    alive for its remaining wait and logs a "task was destroyed but it is
    pending" on the way out."""
    fn = MAIN[MAIN.index("async def _stop_tracker()"):]
    fn = fn[:fn.index("\n\n")]
    assert "warm_task" in fn and "tracker_task" in fn


def test_it_waits_for_the_server_to_finish_binding():
    """`_tracker_loop` waits thirty seconds for the same reason. Two here,
    because this one is racing an actual visitor rather than a schedule."""
    fn = MAIN[MAIN.index("async def _warm_home()"):]
    fn = fn[:fn.index("\n@app.on_event")]
    m = re.search(r"asyncio\.sleep\((\d+)\)", fn)
    assert m, "no delay before it touches the network"
    assert 1 <= int(m.group(1)) <= 5, m.group(1)


# ------------------------------------------------- the countdown past a day


def test_a_gap_longer_than_a_day_is_said_in_days():
    """On a Saturday afternoon the next session is about thirty hours out, and
    the session bar read "Overnight in 29 hours and 3 minutes" -- a number
    nobody can hold. The reader wants to know it is tomorrow evening and has to
    divide by 24 to find that out.

    Checked at the boundaries under JavaScriptCore: 1439 -> "23 hours and 59
    minutes", 1440 -> "1 day", 1743 -> "1 day and 5 hours", 2880 -> "2 days"."""
    fn = re.search(r"function humanCountdown\(minutes\) \{.*?\n\}", APP, re.S).group()
    assert "if (h >= 24) {" in fn
    assert "Math.floor(h / 24)" in fn
    # An exact day says "2 days", not "2 days and 0 hours".
    assert "return rem ?" in fn


def test_a_gap_under_a_day_still_carries_its_minutes():
    """"In 3 hours and 20 minutes" is a number somebody plans around. Rounding
    it to "3 hours" would drop the part they are using -- the days rule is for
    gaps where one minute is precision about nothing."""
    fn = re.search(r"function humanCountdown\(minutes\) \{.*?\n\}", APP, re.S).group()
    tail = fn.split("if (h >= 24) {", 1)[1].split("}", 1)[1]
    assert "minute${m === 1 ? '' : 's'}" in tail


# ------------------------------------------------- the Markets icon climbs


def _polyline(d):
    """The points of an absolute M/L path like `M3 16.5 9 10.5 13 14.5`."""
    nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", d)]
    return list(zip(nums[0::2], nums[1::2]))


def _market_icon_paths():
    """The two `d` strings of the Markets nav icon.

    Scoped to NAV_ICONS. Splitting the whole file on `market: '` found the
    LEGAL DISCLAIMER map instead -- it has a `market:` key too and it comes
    first -- so the extraction returned a sentence about not recommending
    anything and the geometry assertions had nothing to parse.
    """
    icons = APP.split("const NAV_ICONS = {", 1)[1].split("\n};", 1)[0]
    block = icons.split("market: '", 1)[1].split("',", 1)[0]
    return re.findall(r'<path d="([^"]+)"', block)


def test_the_markets_icon_finishes_climbing():
    """It was `M3 17l5-5 4 3 4-6 5 4`, whose last leg went DOWN -- from (16,9)
    to (21,13). A line that finishes falling reads as a squiggle however much
    ground it gained on the way, and it was reported as not looking like a
    trend at all.

    SVG y grows downward, so "higher" is a SMALLER y. Getting that backwards is
    the easy mistake here and would pass a test written the other way round."""
    line = _market_icon_paths()[0]
    pts = _polyline(line)
    assert len(pts) >= 3, "a straight line is a chart of nothing"
    assert pts[-1][1] < pts[0][1], "it must end higher than it starts"
    assert pts[-1][1] < pts[-2][1], "and the last leg must be the climb"
    assert pts[-1][1] == min(y for _, y in pts), "ending at the highest point"
    # And it still has a pullback: markets do not go up in a line, and an icon
    # that says they do is the one claim this app must not make.
    assert any(pts[i][1] > pts[i - 1][1] for i in range(1, len(pts))), \
        "a straight diagonal is not a market"


def test_the_markets_icon_carries_an_arrowhead():
    """What turns a rising line into a trend at 18px."""
    paths = _market_icon_paths()
    assert len(paths) == 2, paths
    line, head = paths
    tip = _polyline(line)[-1]
    # The arrowhead starts on the tip's own row and closes at its column, which
    # is what makes it an arrow rather than a stray tick.
    assert "h" in head and "v" in head, head
    hx, hy = _polyline(head)[0]
    assert hy == tip[1], "the arrowhead sits on the line's own row"
    assert hx < tip[0], "and reaches back toward it"


def test_the_icon_draws_no_axis_of_its_own():
    """At 18px an axis, a zigzag and an arrowhead is three ideas in a space
    that holds one -- and no other icon in this set draws its own baseline:
    `analyse` is three bars with nothing under them."""
    assert "M3 21h18" not in "".join(_market_icon_paths())
