"""Trading-session phases and the close-versus-current pairing.

Only one phase exists at a time, so five of these six states can never be seen
by loading the page — they get tested instead. The failure mode being guarded
against is a quiet one: a price labelled "current" that is actually a settled
close from hours earlier.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import session  # noqa: E402

ET = ZoneInfo("America/New_York")

# 2026-07-27 is a Monday, so this week runs Mon 27th – Sun 2nd August.
MON, THU, FRI, SAT, SUN = 27, 30, 31, 1, 2


def at(day, hour, minute=0, month=7):
    return datetime(2026, month, day, hour, minute, tzinfo=ET)


# ----------------------------------------------------------------- the phases


def test_regular_session():
    s = session.state(at(THU, 10, 0))
    assert s["phase"] == "regular"
    assert s["is_regular"] is True
    assert s["feed_covers_phase"] is True


def test_after_hours_starts_at_the_bell():
    assert session.state(at(THU, 15, 59))["phase"] == "regular"
    assert session.state(at(THU, 16, 0))["phase"] == "after"
    assert session.state(at(THU, 19, 59))["phase"] == "after"


def test_overnight_spans_midnight():
    assert session.state(at(THU, 20, 0))["phase"] == "overnight"
    assert session.state(at(THU, 23, 30))["phase"] == "overnight"
    assert session.state(at(FRI, 1, 0))["phase"] == "overnight"
    assert session.state(at(FRI, 3, 59))["phase"] == "overnight"


def test_pre_market():
    assert session.state(at(FRI, 4, 0))["phase"] == "pre"
    assert session.state(at(FRI, 9, 29))["phase"] == "pre"
    assert session.state(at(FRI, 9, 30))["phase"] == "regular"


def test_weekend_has_no_overnight_session():
    """Friday night is not an overnight session — the venue is shut until Sunday
    evening. Calling it 'overnight' would imply a price could still move."""
    assert session.state(at(FRI, 21, 0))["phase"] == "closed"
    assert session.state(at(SAT, 13, 0, month=8))["phase"] == "closed"
    assert session.state(at(SUN, 19, 0, month=8))["phase"] == "closed"
    assert session.state(at(SUN, 20, 30, month=8))["phase"] == "overnight"


def test_countdown_to_the_next_phase():
    s = session.state(at(THU, 23, 15))
    assert s["next"]["phase"] == "pre"
    assert s["next"]["minutes_away"] == 4 * 60 + 45      # 11:15pm -> 4:00am


def test_countdown_crosses_the_weekend():
    s = session.state(at(FRI, 21, 0))
    assert s["next"]["phase"] == "overnight"             # Sunday 8pm
    assert s["next"]["minutes_away"] == 47 * 60


def test_marker_always_lands_inside_an_active_segment():
    """The 'now' marker is positioned on a 24-hour strip. Overnight straddles
    midnight, and omitting its 00:00-04:00 half left the marker floating outside
    every highlighted block for four hours a night."""
    for hour in range(24):
        when = at(THU, hour, 30)
        s = session.state(when)
        if s["phase"] == "closed":
            continue
        marker = s["day_pct"]
        active = [g for g in s["segments"] if g["active"]]
        assert active, hour
        assert any(g["start_pct"] <= marker <= g["start_pct"] + g["width_pct"]
                   for g in active), (hour, s["phase"], marker)


# --------------------------------------------------- close versus current


QUOTE = {
    "price": 333.43,
    "change_pct": -1.41,
    "post_market_price": 312.33,
    "post_market_change_pct": -6.33,
    "post_market_time": "2026-07-30T23:59:59+00:00",
    "pre_market_price": None,
    "pre_market_change_pct": None,
}


def test_regular_hours_shows_one_price():
    v = session.price_view(QUOTE, at(THU, 10, 0))
    assert v["current"] == 333.43
    assert v["current_kind"] == "regular session"
    assert v["change_from_close_pct"] is None
    assert "stale_note" not in v


def test_after_hours_pairs_close_with_extended():
    v = session.price_view(QUOTE, at(THU, 17, 0))
    assert v["regular_close"] == 333.43
    assert v["current"] == 312.33
    assert v["current_kind"] == "after hours"
    assert v["change_from_close_pct"] == -6.33
    # In the after-hours session the print is live, so no staleness warning.
    assert "stale_note" not in v


def test_overnight_flags_the_price_as_not_live():
    """The regression this module exists for: at 11pm the feed's newest number is
    the 8pm after-hours print. Presenting that as the current overnight price
    would be the misleading part."""
    v = session.price_view(QUOTE, at(THU, 23, 15))
    assert v["current"] == 312.33
    assert "stale_note" in v
    assert "overnight" in v["stale_note"].lower()
    assert session.state(at(THU, 23, 15))["feed_covers_phase"] is False


def test_pre_market_without_a_pre_print_says_where_the_price_came_from():
    v = session.price_view(QUOTE, at(FRI, 6, 0))
    assert v["current"] == 312.33
    assert "yesterday evening" in v["stale_note"]


def test_pre_market_prefers_a_pre_market_print():
    quote = dict(QUOTE, pre_market_price=320.0, pre_market_change_pct=-4.0)
    v = session.price_view(quote, at(FRI, 6, 0))
    assert v["current"] == 320.0
    assert v["current_kind"] == "pre-market"


def test_weekend_says_the_price_is_frozen():
    """Found by this test: the weekend fell through to the extended-hours branch
    and got no warning at all, so Friday's 8pm print was presented as the current
    price two days later."""
    v = session.price_view(QUOTE, at(SAT, 13, 0, month=8))
    assert "won't change" in v["stale_note"]
    assert "Nothing has traded since" in v["stale_note"]


def test_weekend_with_no_extended_print_still_warns():
    quote = dict(QUOTE, post_market_price=None, post_market_change_pct=None)
    v = session.price_view(quote, at(SAT, 13, 0, month=8))
    assert "won't change" in v["stale_note"]
