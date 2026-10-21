"""Released results on Home's What Matters Today (server side).

Taken from the home-released-results branch (f888236) for Classic parity B8.6, 2026-10-21: only the server rules
(app/priority.py) and their tests. The branch's Classic page tests stay on the branch with its Classic UI; v2's
display is tested in tests/test_v2_parity_b8.py.


Asked for on 2026-10-15 with a screenshot of the band: "PPI Out" over a
paragraph explaining what the producer price index is. "If the results are
out, the results should be shown here." The figures were already fetched for
each release and dropped on the way to the page.

What these hold: a release that is out carries what it printed, but only when
the figure in hand is that release's (FRED loads a new print hours after it
lands, and until then its newest figure is last month's); the agency's own
headline only when it was published that day; a report that is out reads in
the past tense with its EPS against the estimate; and the page puts the figure
where the word "Out" was, and the figures ahead of the description.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app import priority



def _ppi(as_of="2026-09-01", published="2026-10-15T12:30:00+00:00", **readings):
    rd = {"available": True, "series": "PPIFIS", "series_label": "PPI, final demand, month over month",
          "actual": 1.3, "previous": 0.5, "as_of": as_of, "unit": "%"}
    rd.update(readings)
    return {"released": True, "at": "2026-10-15T08:30:00-04:00", "time_label": "8:30 AM ET",
            "title": "Producer Price Index",
            "agency_short": "BLS", "readings": rd,
            "previous": {"headline": "PPI for final demand increases 1.3% in September",
                         "published": published, "url": "https://www.bls.gov/news.release/ppi.nr0.htm"}}


# ------------------------------------------------------------------ releases


def test_a_release_that_is_out_carries_what_it_printed():
    res = priority._event_result(_ppi())
    assert res["short"] == "+1.3%"
    assert res["text"] == ("PPI, final demand, month over month +1.3% for September 2026, "
                           "after +0.5% the month before.")
    assert res["source"] == "FRED (PPIFIS)"
    assert not res.get("pending")


def test_a_release_still_to_come_has_no_result():
    e = _ppi()
    e["released"] = False
    assert priority._event_result(e) is None


def test_last_months_figure_is_not_shown_as_the_new_print():
    """FRED had not loaded the new print: its newest observation is August's,
    which the September release would have replaced. Shown as the result, it
    would be last month's number under today's date."""
    res = priority._event_result(_ppi(as_of="2026-08-01", published="2026-10-14T12:30:00+00:00"))
    assert "short" not in res and "actual" not in res
    assert res["pending"] is True
    assert "not reached Optic's feeds yet" in res["text"]
    assert "August 2026" in res["fred_pending"]


def test_the_agency_headline_is_used_only_when_it_is_todays():
    today = priority._event_result(_ppi(as_of="2026-08-01"))
    assert today["headline"].startswith("PPI for final demand increases 1.3%")
    assert today["headline_url"].startswith("https://www.bls.gov/")
    assert today["headline_source"] == "BLS"
    assert not today.get("pending"), "the headline alone is a result"
    stale = priority._event_result(_ppi(published="2026-09-11T12:30:00+00:00"))
    assert "headline" not in stale, "last month's release headline is not today's"


def test_a_quarterly_series_is_read_as_a_quarter():
    e = _ppi(as_of="2026-07-01", series="GDPC1", series_label="Real GDP, annualized",
             actual=2.8, previous=3.1)
    e["at"] = "2026-10-29T08:30:00-04:00"
    e["previous"] = {}
    res = priority._event_result(e)
    assert res["text"] == "Real GDP, annualized +2.8% for Q3 2026, after +3.1% the quarter before."


def test_a_release_with_no_figure_to_read_says_nothing_more_than_out():
    """FOMC minutes and options expiry print no number: "the figures have not
    reached Optic's feeds yet" would be waiting for something that never comes."""
    e = {"released": True, "at": "2026-10-07T14:00:00-04:00", "time_label": "2:00 PM ET",
         "title": "FOMC minutes", "readings": {"available": False}, "previous": None}
    assert priority._event_result(e) is None
    e["title"] = "Producer Price Index"
    assert priority._event_result(e)["pending"] is True, "PPI does print one"


def test_it_says_what_the_result_is_measured_against():
    """Consensus forecasts are licensed, so the comparison is the previous
    print, and the page says so rather than letting "+1.3%" read as a beat."""
    res = priority._event_result(_ppi())
    assert "previous print" in res["forecast_note"]


# ------------------------------------------------------------------ earnings


class _Provider:
    def __init__(self, rows):
        self.rows = rows
        self.calls = 0

    def earnings_history(self, symbol, limit=6):
        self.calls += 1
        return self.rows


THU = datetime(2026, 10, 15, 18, 0, tzinfo=timezone.utc)      # 2 PM ET


def test_a_report_that_is_out_shows_eps_against_the_estimate():
    p = _Provider([{"date": "2026-10-13", "eps_reported": 4.60, "eps_estimate": 4.52, "surprise_pct": 1.77}])
    res = priority._earnings_result(p, "GS", "2026-10-13", THU)
    assert res["short"] == "Beat" and res["verdict"] == "beat"
    assert res["text"] == "EPS 4.60 against 4.52 expected: beat by 1.8%."


def test_within_a_percent_is_in_line_not_a_beat():
    p = _Provider([{"date": "2026-10-13", "eps_reported": 2.01, "eps_estimate": 2.00, "surprise_pct": None}])
    res = priority._earnings_result(p, "JNJ", "2026-10-13", THU)
    assert res["short"] == "In line"
    assert res["text"] == "EPS 2.01 against 2.00 expected: in line."


def test_a_report_later_this_week_is_not_looked_up():
    p = _Provider([])
    assert priority._earnings_result(p, "PEP", "2026-10-16", THU) is None
    assert p.calls == 0, "a future report costs no request"


def test_today_with_no_figures_may_still_be_to_come():
    """An after-close report is not out at 2 PM; it keeps "reports"."""
    p = _Provider([{"date": "2026-10-15", "eps_reported": None, "eps_estimate": 1.1}])
    assert priority._earnings_result(p, "ISRG", "2026-10-15", THU) is None


def test_an_earlier_day_with_no_figures_says_they_are_late():
    p = _Provider([{"date": "2026-10-13", "eps_reported": None, "eps_estimate": 1.1}])
    res = priority._earnings_result(p, "UNH", "2026-10-13", THU)
    assert res["pending"] is True and "not reached Optic's feed yet" in res["text"]


def test_a_reported_name_reads_in_the_past_tense(monkeypatch):
    block = {"days": [{"day": "Tuesday", "date": "2026-10-13", "symbols": ["GS", "UNH"]},
                      {"day": "Friday", "date": "2026-10-16", "symbols": ["PEP"]}]}
    monkeypatch.setattr(priority.weekly_mod, "earnings_this_week", lambda provider, now: block)
    p = _Provider([{"date": "2026-10-13", "eps_reported": 4.60, "eps_estimate": 4.52, "surprise_pct": 1.77}])
    titles = {r["ticker"]: r["title"] for r in priority._earnings(p, THU)}
    assert titles["GS"] == "GS reported Tuesday"
    assert titles["PEP"] == "PEP reports Friday"
    p.rows = []
    titles = {r["ticker"]: r["title"] for r in priority._earnings(p, THU)}
    assert titles["UNH"] == "UNH reports Tuesday", "no figures yet, so no claim it reported"
