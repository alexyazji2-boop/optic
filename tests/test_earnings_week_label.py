"""The earnings week names the month it ends in when that is a different one.

Reported by a user: "Right now in Earning this week, it shows the date as
"Sept 28 - 2", it should specify Oct". The end of the range took only its day.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from app import earnings_week


@pytest.mark.parametrize("start,end,label", [
    ("2026-09-28", "2026-10-02", "Sep 28 – Oct 2"),
    ("2026-09-21", "2026-09-25", "Sep 21 – 25"),
    ("2026-12-28", "2027-01-01", "Dec 28 – Jan 1"),
    ("2026-06-01", "2026-06-05", "Jun 1 – 5"),
])
def test_a_week_across_two_months_names_both(start, end, label):
    got = earnings_week.week_label(datetime.fromisoformat(start), datetime.fromisoformat(end))
    assert got == label


def test_the_payload_uses_it():
    src = open(earnings_week.__file__).read()
    assert '"week_label": week_label(start, start + timedelta(days=4)),' in src
