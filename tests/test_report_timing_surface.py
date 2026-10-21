"""The report's time of day reaches the volatility surface (2026-10-21).

An expiry that ends on the report date spans a report before the open and not
one after the close, which lands after that expiry stops trading.
`vol_surface.mark_events` took an `after_close` flag for this, but main.py never
passed it and it defaulted to False, so every report on an expiry's own date was
counted inside that expiry: the report-day move was read from an expiry that, for
an after-close report, prices none of it, and the term read said the report fell
inside it.

Now the timing is passed where Optic knows it and is "unknown" otherwise. The
time the feed lists for a report still to come is a placeholder
(analytics/earnings._next_report), so it is known once the report is out. At an
unknown time the same-day expiry is on neither side: the move is read from the
expiries either side of the report date, and the page says why that one is left
out. The company's habit is said beside it, never used for it.

Found with it: main.py read the `earnings_date` leg twice, and a leg is gone once
read, so whenever a chain loaded the payload lost `next_earnings_date`.
"""
from __future__ import annotations

import inspect

import numpy as np
import pytest

import app.main as main
from app.analytics import vol_surface as vs

REPORT = "2026-10-30"


def _rows():
    return [{"expiry": "2026-10-23", "dte": 11, "tau_years": 11 / 365, "atm_iv_pct": 30.0},
            {"expiry": REPORT, "dte": 18, "tau_years": 18 / 365, "atm_iv_pct": 31.0},
            {"expiry": "2026-11-06", "dte": 25, "tau_years": 25 / 365, "atm_iv_pct": 45.0},
            {"expiry": "2026-11-20", "dte": 39, "tau_years": 39 / 365, "atm_iv_pct": 38.0}]


def _move(after_iv, after_days, before_iv):
    return np.sqrt((after_iv / 100) ** 2 * after_days / 365
                   - (before_iv / 100) ** 2 * (after_days - 1) / 365) * 100


@pytest.mark.parametrize("timing, want", [
    ("before_open", [False, True, True, True]),
    ("after_close", [False, False, True, True]),
    (None, [False, None, True, True]),
])
def test_the_same_day_expiry_follows_the_timing(timing, want):
    rows = _rows()
    vs.mark_events(rows, REPORT, timing)
    assert [r["contains_event"] for r in rows] == want


def test_an_after_close_report_is_read_from_the_next_expiry():
    rows = _rows()
    vs.mark_events(rows, REPORT, "after_close")
    ev = vs.event_move(rows, REPORT, "after_close")
    assert (ev["after"], ev["before"], ev["timing"]) == ("2026-11-06", REPORT, "after_close")
    assert ev["move_pct"] == pytest.approx(_move(45.0, 25, 31.0), abs=0.01)


def test_a_before_open_report_is_inside_its_own_days_expiry():
    rows = _rows()
    vs.mark_events(rows, REPORT, "before_open")
    ev = vs.event_move(rows, REPORT, "before_open")
    assert (ev["after"], ev["before"]) == (REPORT, "2026-10-23")


def test_at_an_unknown_time_the_same_day_expiry_is_on_neither_side_and_says_so():
    """It was counted inside: the move came out of the 10-30 expiry's 31% against
    the 10-23's 30%, about 2.3%, where the report is priced in the 11-06 expiry's
    45%, about 8.9%."""
    rows = _rows()
    vs.mark_events(rows, REPORT, None, {"timing": "after_close", "count": 4})
    ev = vs.event_move(rows, REPORT)
    assert (ev["after"], ev["before"], ev["timing"]) == ("2026-11-06", "2026-10-23", "unknown")
    assert ev["move_pct"] == pytest.approx(_move(45.0, 25, 30.0), abs=0.01)
    assert "not known" in ev["text"] and "counted on neither side" in ev["text"]
    assert "last 4 reports came after the close: its habit, not this report's announced time" in ev["text"]

    term = vs.term_read(rows, REPORT)["text"]
    assert "falls inside the 2026-11-06 expiry" in term
    assert "falls inside the {}".format(REPORT) not in term
    assert "The {} expiry ends on the report date".format(REPORT) in term


def test_no_timing_given_is_unknown_not_inside():
    """The default that caused this: with no timing the same-day expiry was True."""
    rows = _rows()
    vs.mark_events(rows, REPORT)
    assert rows[1]["contains_event"] is None


def test_no_note_and_no_change_when_no_expiry_falls_on_the_report_date():
    rows = [r for r in _rows() if r["expiry"] != REPORT]
    vs.mark_events(rows, REPORT, None)
    assert [r["contains_event"] for r in rows] == [False, True, True]
    assert not any("event_note" in r for r in rows)
    assert "not known" not in vs.event_move(rows, REPORT)["text"]


# ------------------------------------------------------------ main.py's side


class _Chain:
    """Just enough of a chain for the lookup: its expiries."""

    def __init__(self, expiries):
        import pandas as pd
        self.frame = pd.DataFrame({"expiry": expiries})


def _history(rows, calls):
    def fn(ticker, limit=10):
        calls.append(ticker)
        return rows
    return fn


PAST = [{"date": d, "timing": "after_close", "eps_reported": 1.1}
        for d in ("2026-07-30", "2026-04-30", "2026-01-29", "2025-10-30")]


def test_no_lookup_unless_an_expiry_falls_on_the_report_date(monkeypatch):
    calls = []
    monkeypatch.setattr(main.YF_PROVIDER, "earnings_history", _history(PAST, calls))
    chain = _Chain(["2026-10-23", "2026-11-06"]).frame
    assert main._report_timing_for_surface("ABC", REPORT, chain) == (None, None)
    assert main._report_timing_for_surface("ABC", None, chain) == (None, None)
    assert calls == []


def test_an_upcoming_reports_listed_time_is_not_taken_as_known(monkeypatch):
    """The feed lists a time for a report still to come (a placeholder) with no
    reported EPS: unknown, with the habit from the four before."""
    calls = []
    upcoming = [{"date": REPORT, "timing": "before_open", "eps_reported": None}] + PAST
    monkeypatch.setattr(main.YF_PROVIDER, "earnings_history", _history(upcoming, calls))
    chain = _Chain(["2026-10-23", REPORT, "2026-11-06"]).frame
    timing, usual = main._report_timing_for_surface("ABC", REPORT, chain)
    assert timing is None and usual == {"timing": "after_close", "count": 4}
    assert calls == ["ABC"]


def test_a_report_already_out_gives_its_own_time(monkeypatch):
    out = [{"date": REPORT, "timing": "before_open", "eps_reported": 1.2}] + PAST
    monkeypatch.setattr(main.YF_PROVIDER, "earnings_history", _history(out, []))
    chain = _Chain([REPORT, "2026-11-06"]).frame
    timing, usual = main._report_timing_for_surface("ABC", REPORT, chain)
    assert timing == "before_open"
    assert usual == {"timing": "after_close", "count": 4}, "the habit is from the reports before this one"


def test_the_builder_passes_the_timing():
    # The port onto live (2026-11-06) keeps live's own read of the report date (calendar fallback, 2026-10-31
    # hotfix), whose legs can be read again, so only the timing half of 7c34135 is tested here.
    src = inspect.getsource(main._swing_snapshot)
    assert "timing, usual_timing = _report_timing_for_surface(ticker, event_date, chain)" in src
    assert "timing=timing, usual_timing=usual_timing" in src
