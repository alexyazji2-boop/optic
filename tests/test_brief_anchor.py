"""The pre-open rebuild anchor, and the weekend-aware wire window.

Both exist because the brief's freshness was previously incidental. It rebuilt
when the cached payload happened to age past its TTL on whatever tick the loop
was on, and its wire window was a fixed 36 hours — which is the wrong number in
exactly the case a pre-open read matters most.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from app import brief

ET = ZoneInfo("America/New_York")


def _anchor(now, last=None):
    from app.main import brief_anchor_due
    return brief_anchor_due(now, last)


def test_anchor_fires_once_at_the_pre_open_hour():
    morning = datetime(2026, 8, 24, 9, 5, tzinfo=ET)
    assert _anchor(morning) == "2026-08-24"
    # And not again the same day.
    assert _anchor(datetime(2026, 8, 24, 11, 0, tzinfo=ET), "2026-08-24") is None


def test_anchor_does_not_fire_before_the_hour():
    assert _anchor(datetime(2026, 8, 24, 8, 55, tzinfo=ET)) is None


def test_anchor_fires_on_a_late_start():
    """A server that boots at 14:00 still needs one forced rebuild — a brief
    cached from before it booted is not what a reader wants."""
    assert _anchor(datetime(2026, 8, 24, 14, 0, tzinfo=ET)) == "2026-08-24"


def test_anchor_resets_the_next_day():
    assert _anchor(datetime(2026, 8, 25, 9, 1, tzinfo=ET), "2026-08-24") == "2026-08-25"


# ------------------------------------------------------------ wire window

def test_monday_morning_covers_the_whole_weekend():
    """The defect this replaced: Friday 16:00 to Monday 09:00 is 65 hours, so a
    fixed 36-hour window dropped all of Friday and most of Saturday from the read
    a user opens specifically to catch up on the weekend."""
    monday = datetime(2026, 8, 24, 9, 0, tzinfo=ET)
    assert brief.wire_window_hours(monday) == 65


def test_midweek_falls_back_to_the_floor():
    """The gap from yesterday's close is only ~17 hours, and a 17-hour window
    renders a near-empty page."""
    tuesday = datetime(2026, 8, 25, 9, 0, tzinfo=ET)
    assert brief.wire_window_hours(tuesday) == brief.WORLD_WINDOW_FLOOR_HOURS


def test_the_window_is_capped():
    """A long holiday weekend must not present a week of headlines as new."""
    for day in range(20, 28):
        got = brief.wire_window_hours(datetime(2026, 8, day, 9, 0, tzinfo=ET))
        assert got <= brief.WORLD_WINDOW_CEILING_HOURS


def test_saturday_and_sunday_measure_from_fridays_close():
    sat = brief.wire_window_hours(datetime(2026, 8, 22, 11, 0, tzinfo=ET))
    sun = brief.wire_window_hours(datetime(2026, 8, 23, 20, 0, tzinfo=ET))
    assert sat >= brief.WORLD_WINDOW_FLOOR_HOURS
    assert sun > sat, "the gap grows as the weekend goes on"


# --------------------------------------------------- geopolitical paragraph

def _wires(world=0, politics=0, window=65):
    def rows(n, tag):
        return [{"title": f"{tag} story {i}", "source": "BBC News",
                 "published": f"2026-08-24T0{i}:00:00Z"} for i in range(n)]
    return {"window_hours": window,
            "desks": [{"id": "world", "entries": rows(world, "World")},
                      {"id": "politics", "entries": rows(politics, "Politics")}]}


def test_world_paragraph_counts_and_attributes():
    text = brief._world_paragraph(_wires(world=6, politics=3), 65)
    assert "world (6)" in text and "politics (3)" in text
    assert "9 stor" in text
    assert "BBC News" in text


def test_world_paragraph_absent_when_the_desks_are_empty():
    assert brief._world_paragraph(_wires(), 65) is None


def test_world_paragraph_makes_no_market_claim():
    """It points at coverage; it does not decide that a story matters to the S&P.
    A mechanical threshold dressed up as geopolitical analysis would be the worst
    output on the page."""
    text = brief._world_paragraph(_wires(world=4), 65).lower()
    assert "nothing here reads across to a price" in text
    for banned in ("bullish", "bearish", "risk-off", "will likely", "expect"):
        assert banned not in text


def test_mechanical_narrative_includes_the_world_leg():
    overview = {"groups": {"indices": [], "sectors": [], "mag7": []},
                "sector_breadth_pct": None, "leaders": [], "laggards": []}
    out = brief._narrative(overview, _wires(world=2, politics=1))
    assert any("desk" in p for p in out["paragraphs"])


# ---------------------------------------------- the anchor does not skip weekends
#
# The read is the thing a reader opens on a Monday to find out what happened
# while the market was shut, which only works if it kept rebuilding while the
# market was shut. The rule has no weekday test in it, and these state that as a
# guarantee rather than leaving it as an accident of how it was written — a
# plausible "don't waste calls when the market is closed" optimisation would
# break exactly the case the read exists for.

def test_the_anchor_fires_on_a_saturday():
    saturday = datetime(2026, 8, 29, 9, 5, tzinfo=ET)
    assert saturday.weekday() == 5
    assert _anchor(saturday) == "2026-08-29"


def test_the_anchor_fires_on_a_sunday():
    sunday = datetime(2026, 8, 30, 9, 5, tzinfo=ET)
    assert sunday.weekday() == 6
    assert _anchor(sunday) == "2026-08-30"


def test_every_day_across_a_weekend_gets_its_own_rebuild():
    """Friday through Monday, one forced rebuild each and no repeats."""
    last = None
    stamps = []
    for day in (28, 29, 30, 31):                     # Fri, Sat, Sun, Mon 2026-08
        stamp = _anchor(datetime(2026, 8, day, 9, 30, tzinfo=ET), last)
        assert stamp is not None, "no rebuild on 2026-08-%d" % day
        stamps.append(stamp)
        last = stamp
        # A second tick the same day must not fire again.
        assert _anchor(datetime(2026, 8, day, 15, 0, tzinfo=ET), last) is None
    assert stamps == ["2026-08-28", "2026-08-29", "2026-08-30", "2026-08-31"]


def test_the_brief_refresh_runs_before_the_market_hours_gate():
    """A placement guard, not a behaviour test.

    The refresh sits above the `continue` that skips a closed market. Moved below
    it — an easy and superficially sensible edit — the brief would stop rebuilding
    every evening and all weekend, which is precisely when news arrives and no
    reader is around to trigger a build by opening the tab. Nothing else in the
    suite would fail.
    """
    import inspect
    from app import main

    src = inspect.getsource(main._tracker_loop)
    brief_at = src.index("if BRIEF_AUTO:")
    gate_at = src.index("Nothing to do overnight or at the weekend")
    assert brief_at < gate_at, (
        "the brief refresh moved below the market-hours gate — it will stop "
        "updating overnight and at weekends")
