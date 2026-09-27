"""The futures week, which is not the equity week.

The defect this exists for is two hours wide. `_weekend` calls Sunday shut
until 8:00pm because that is when the equity *overnight* session starts, but
CME equity index futures opened at 6:00pm -- and the home strip is already
drawing their prices by then. Measured on a Sunday at 18:44 ET the terminal
read "Weekend. Closed, Overnight in 1 hour and 15 minutes" above a row of live
ES and NQ quotes.

The week modelled here: open Sunday 6:00pm, shut Friday 5:00pm, one hour down
at 5:00pm on the days between.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app import session

ET = ZoneInfo("America/New_York")

# A week with no US holiday in it, so nothing here is really testing the
# equity holiday calendar by accident.
SUN = (2026, 9, 27)
MON = (2026, 9, 28)
THU = (2026, 10, 1)
FRI = (2026, 10, 2)
SAT = (2026, 10, 3)


def at(day, hour, minute=0):
    return datetime(day[0], day[1], day[2], hour, minute, tzinfo=ET)


# ------------------------------------------------------- the Sunday open


def test_futures_open_at_six_on_sunday():
    assert session.futures_phase(at(SUN, 18, 0)) == "open"


def test_futures_are_shut_one_minute_before_that():
    assert session.futures_phase(at(SUN, 17, 59)) == "weekend"


@pytest.mark.parametrize("hour,minute", [(18, 0), (18, 44), (19, 30), (23, 59)])
def test_futures_are_open_through_sunday_evening(hour, minute):
    """The whole window the terminal used to call closed."""
    assert session.futures_phase(at(SUN, hour, minute)) == "open"


def test_the_two_markets_disagree_on_sunday_evening_and_that_is_the_point():
    """Both answers are correct and they are not the same answer. Flattening
    them into one status would throw away the fact this module exists for."""
    when = at(SUN, 18, 44)
    assert session.state(when)["phase"] == "closed", "US equities are shut"
    assert session.futures_state(when)["is_open"] is True, "ES is trading"


def test_the_sunday_open_is_reported_as_the_next_change_before_it_happens():
    nxt = session.futures_state(at(SUN, 17, 30))["next"]
    assert nxt["phase"] == "open"
    assert nxt["minutes_away"] == 30


# ------------------------------------------------------- the daily break


@pytest.mark.parametrize("day", [MON, THU])
def test_futures_halt_for_the_maintenance_hour(day):
    assert session.futures_phase(at(day, 16, 59)) == "open"
    assert session.futures_phase(at(day, 17, 0)) == "break"
    assert session.futures_phase(at(day, 17, 59)) == "break"
    assert session.futures_phase(at(day, 18, 0)) == "open"


def test_the_break_reports_when_it_reopens():
    nxt = session.futures_state(at(MON, 17, 30))["next"]
    assert nxt["phase"] == "open"
    assert nxt["minutes_away"] == 30


# --------------------------------------------------------- the Friday close


def test_five_pm_friday_is_the_end_of_the_week_not_a_break():
    """The case a break-first reading gets wrong: on any other weekday 5:00pm
    reopens an hour later, and on Friday it does not reopen until Sunday."""
    assert session.futures_phase(at(FRI, 16, 59)) == "open"
    assert session.futures_phase(at(FRI, 17, 0)) == "weekend"
    assert session.futures_phase(at(FRI, 18, 30)) == "weekend", \
        "Friday 6pm is not a reopen"


def test_saturday_is_shut_all_day():
    for hour in (0, 9, 17, 18, 23):
        assert session.futures_phase(at(SAT, hour)) == "weekend"


def test_from_the_friday_close_the_next_open_is_sunday_at_six():
    nxt = session.futures_state(at(FRI, 17, 0))["next"]
    assert nxt["phase"] == "open"
    # Friday 17:00 to Sunday 18:00 is 49 hours.
    assert nxt["minutes_away"] == 49 * 60


# ------------------------------------------------------------- the payload


def test_the_session_payload_carries_the_futures_week():
    """Alongside the equity phase rather than merged into it."""
    out = session.state(at(SUN, 18, 44))
    assert out["phase"] == "closed"
    assert out["futures"]["phase"] == "open"
    assert out["futures"]["label"] == "Futures open"


def test_every_phase_has_a_label_and_a_description():
    """`LABELS[phase]` on a phase nobody wrote copy for is a KeyError at
    render time, and the equity half of this module shipped that shape of bug
    twice as a nav reading its own lowercase view id."""
    for phase in ("open", "break", "weekend"):
        assert phase in session.FUTURES_LABELS
        assert phase in session.FUTURES_DESCRIPTIONS
        assert len(session.FUTURES_DESCRIPTIONS[phase]) > 40


def test_it_says_what_it_does_not_model():
    """Every panel states what it cannot tell you. CME's holiday calendar is
    not NYSE's -- several equity holidays are shortened futures sessions
    rather than closed ones, and this will read those as ordinary."""
    limits = session.futures_state(at(MON, 10))["limits"]
    assert "Holiday" in limits or "holiday" in limits
    assert "CME" in limits


def test_the_description_does_not_call_a_future_the_index():
    """The module already refuses this conflation for the overnight strip: a
    future carries basis and its own expiry, so it is where the market is
    leaning rather than a price for the index."""
    text = session.FUTURES_DESCRIPTIONS["open"]
    assert "not the index" in text


# ----------------------------------------------------------- daylight saving


def test_the_open_tracks_the_clock_through_the_dst_change():
    """Six o'clock means six o'clock in New York on both sides of the change,
    which is what storing ET clock minutes and converting through zoneinfo
    buys. A UTC offset hardcoded anywhere here would be an hour out for half
    the year -- and the half it is wrong in changes."""
    # 1 Nov 2026 is the Sunday the US leaves daylight saving.
    after_change = datetime(2026, 11, 1, 18, 0, tzinfo=ET)
    assert after_change.utcoffset().total_seconds() == -5 * 3600, "sanity: EST"
    assert session.futures_phase(after_change) == "open"
    assert session.futures_phase(datetime(2026, 11, 1, 17, 59, tzinfo=ET)) == "weekend"
    # And in daylight time, where the same clock reading is a different instant.
    summer = datetime(2026, 6, 28, 18, 0, tzinfo=ET)
    assert summer.utcoffset().total_seconds() == -4 * 3600, "sanity: EDT"
    assert session.futures_phase(summer) == "open"
