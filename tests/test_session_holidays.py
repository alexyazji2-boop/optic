"""Market holidays and early closes.

The module used to say so in its own docstring: "Holidays aren't modelled...
this module will still call it a regular session, which is the one case where it
knowingly overstates what's happening." On Labor Day 2026 at 12:05pm ET it read
the clock, found a weekday inside 9:30-16:00, and reported a regular session in
progress with "after hours in 3 hours and 54 minutes".

The dates here are checked against the published NYSE calendar, not against the
implementation. They are computed from rules rather than tabulated so that no
year silently inherits the previous one's calendar, which is exactly the failure
a hardcoded list produces the first January nobody updates it.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from app import session

ET = ZoneInfo("America/New_York")

# The published NYSE closures for 2026.
NYSE_2026 = {
    date(2026, 1, 1): "New Year's Day",
    date(2026, 1, 19): "Martin Luther King, Jr. Day",
    date(2026, 2, 16): "Washington's Birthday",
    date(2026, 4, 3): "Good Friday",
    date(2026, 5, 25): "Memorial Day",
    date(2026, 6, 19): "Juneteenth",
    date(2026, 7, 3): "Independence Day",
    date(2026, 9, 7): "Labor Day",
    date(2026, 11, 26): "Thanksgiving Day",
    date(2026, 12, 25): "Christmas Day",
}


def test_the_2026_calendar_matches_the_exchange():
    assert session.market_holidays(2026) == NYSE_2026


def test_every_year_has_ten_closures_and_none_on_a_weekend():
    """A closure computed onto a Saturday is a closure that never happens, and
    it would also push the next-open calculation a day wrong."""
    for year in range(2022, 2036):
        days = session.market_holidays(year)
        assert len(days) in (9, 10), (year, len(days))
        for day in days:
            assert day.weekday() < 5, (year, day, day.strftime("%a"))


def test_labor_day_is_closed_at_midday():
    """The reported bug, at the exact instant it was reported."""
    st = session.state(datetime(2026, 9, 7, 12, 5, tzinfo=ET))
    assert st["phase"] == "holiday"
    assert st["is_open"] is False
    assert st["is_regular"] is False
    assert st["holiday"] == "Labor Day"
    assert "Labor Day" in st["label"]


def test_the_holiday_is_named_not_just_flagged():
    """"Closed" leaves the reader working out why. Every closure says which."""
    for day, name in NYSE_2026.items():
        st = session.state(datetime(day.year, day.month, day.day, 11, 0, tzinfo=ET))
        assert st["holiday"] == name, day
        assert name in st["label"], day


def test_a_holiday_is_closed_at_every_hour_not_just_market_hours():
    """The old logic consulted the clock first, so 3am on a holiday was
    'overnight' and 10am was 'regular'. Neither trades."""
    for hour in (0, 3, 5, 9, 10, 13, 16, 18, 21, 23):
        st = session.state(datetime(2026, 9, 7, hour, 30, tzinfo=ET))
        assert st["phase"] == "holiday", hour
        assert st["is_open"] is False, hour


def test_the_evening_before_a_holiday_opens_no_overnight_session():
    """The overnight session runs from 8pm into the next morning, so it only
    exists if there is a next morning. The Sunday before Labor Day would
    otherwise light Overnight at 8pm for a session that never opens."""
    st = session.state(datetime(2026, 9, 6, 21, 0, tzinfo=ET))
    assert st["phase"] == "closed"
    assert st["next"]["phase"] == "holiday"


def test_new_years_day_on_a_saturday_closes_nothing():
    """The documented exception: unlike the federal calendar, the exchange does
    not reach back into December for it. 1 January 2028 is a Saturday."""
    assert date(2028, 1, 1).weekday() == 5
    days = session.market_holidays(2028)
    assert date(2027, 12, 31) not in days
    assert not any(d.month == 1 and d.day in (1, 2, 3) for d in days)


def test_a_fixed_date_holiday_shifts_the_way_the_exchange_shifts_it():
    """Independence Day 2026 falls on a Saturday, so it is taken on Friday the
    3rd. Christmas 2027 falls on a Saturday, so it is taken on Friday the 24th."""
    assert date(2026, 7, 4).weekday() == 5
    assert session.market_holidays(2026)[date(2026, 7, 3)] == "Independence Day"
    assert date(2027, 12, 25).weekday() == 5
    assert session.market_holidays(2027)[date(2027, 12, 24)] == "Christmas Day"


def test_good_friday_tracks_easter():
    """The only closure that is neither a fixed date nor an nth-weekday rule."""
    for year, expected in ((2026, date(2026, 4, 3)), (2027, date(2027, 3, 26)),
                           (2028, date(2028, 4, 14))):
        assert session.market_holidays(year)[expected] == "Good Friday", year


def test_juneteenth_only_exists_from_2022():
    assert date(2021, 6, 18) not in session.market_holidays(2021)
    assert any(name == "Juneteenth" for name in session.market_holidays(2022).values())


# ----------------------------------------------------------- early closes

def test_the_half_day_regular_session_ends_at_one():
    """The day after Thanksgiving 2026. At 12:30 it is still trading; at 13:30
    it is not."""
    assert session.state(datetime(2026, 11, 27, 12, 30, tzinfo=ET))["phase"] == "regular"
    assert session.state(datetime(2026, 11, 27, 13, 30, tzinfo=ET))["phase"] == "after"


def test_the_half_day_after_hours_ends_at_five():
    assert session.state(datetime(2026, 11, 27, 16, 30, tzinfo=ET))["phase"] == "after"
    assert session.state(datetime(2026, 11, 27, 17, 30, tzinfo=ET))["phase"] == "overnight"


def test_a_full_day_still_ends_at_four():
    """The half-day rule must not leak onto ordinary days."""
    assert session.state(datetime(2026, 9, 9, 15, 0, tzinfo=ET))["phase"] == "regular"
    assert session.state(datetime(2026, 9, 9, 17, 0, tzinfo=ET))["phase"] == "after"


def test_the_early_close_is_announced_before_it_happens():
    """"The market shuts at 1pm today" is worth knowing at 9:30am, not at 12:59."""
    st = session.state(datetime(2026, 11, 27, 10, 0, tzinfo=ET))
    assert st["early_close"] == "the day after Thanksgiving"
    assert "1:00pm" in st["early_close_note"]


def test_july_third_is_not_an_early_close_when_it_is_the_holiday():
    """In 2026 the 4th is a Saturday, so the 3rd is the full closure. Listing it
    as a half day as well would have the module claim a 1pm close on a day
    nothing trades at all."""
    assert date(2026, 7, 3) in session.market_holidays(2026)
    assert date(2026, 7, 3) not in session.early_closes(2026)


def test_no_early_close_is_also_a_full_holiday():
    for year in range(2022, 2036):
        overlap = set(session.early_closes(year)) & set(session.market_holidays(year))
        assert not overlap, (year, overlap)


def test_an_ordinary_day_reports_no_early_close():
    st = session.state(datetime(2026, 9, 9, 10, 0, tzinfo=ET))
    assert st["early_close"] is None
    assert st["early_close_note"] is None


def test_every_phase_has_a_label_and_a_description():
    """A new phase that renders as `undefined` is the failure this catches."""
    for phase in ("regular", "after", "overnight", "pre", "closed", "holiday"):
        assert session.LABELS.get(phase), phase
        assert session.DESCRIPTIONS.get(phase), phase
