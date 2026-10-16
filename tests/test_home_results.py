"""Released results on Home's What Matters Today.

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

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone

import pytest

from app import priority

JSC = ("/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/"
       "Helpers/jsc")
APP = open("static/app.js", encoding="utf-8").read()
CSS = open("static/styles.css", encoding="utf-8").read()


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


# ------------------------------------------------------------------ the page


RES_PPI = {"short": "+1.3%", "text": "PPI, final demand +1.3% for September 2026, after +0.5% the month before.",
           "headline": "PPI for final demand increases 1.3% in September", "headline_source": "BLS",
           "headline_url": "https://www.bls.gov/news.release/ppi.nr0.htm"}
RES_GS = {"short": "Beat", "text": "EPS 4.60 against 4.52 expected: beat by 1.8%."}
PENDING = {"pending": True, "text": "Released at 8:30 AM ET; the figures have not reached Optic's feeds yet."}


def _row(title, kind="event", why="What the producer price index measures.", result=None, short="",
         days_away=0, released=True, when="Thu Oct 15"):
    return {"kind": kind, "impact": "high", "title": title, "short": short, "when": when,
            "time": "Out at 8:30 AM ET" if released else "8:30 AM ET", "released": released,
            "days_away": days_away, "why": why, "agency": "BLS", "result": result}


def _col(cid, rows):
    return {"id": cid, "name": cid, "blurb": "", "rows": rows, "total": len(rows), "preview": rows[:3]}


PAYLOAD = {"available": True, "horizon_days": 5, "columns": [
    _col("events", [_row("Producer Price Index", short="PPI", result=RES_PPI),
                    # Tomorrow's slot, so that today holds two and none overflows.
                    _row("Retail sales", short="Retail", result=PENDING, days_away=1),
                    _row("No reading", short="Undated", result=RES_PPI, days_away=None)]),
    _col("earnings", [dict(_row("PNC reported Thursday", kind="earnings", why="", result=RES_GS, when="Thursday"),
                           ticker="PNC"),
                      _row("GS reported Tuesday", kind="earnings", why="An earnings report resets the estimate.",
                           result=RES_GS, days_away=-2, when="Tuesday")])]}


@pytest.fixture(scope="module")
def page():
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    script = """
      load('tests/support/browser_stubs.js');
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
      STATE.home = { session: { now_et: '2026-10-15T14:00:00-04:00' } };
      var p = %s, out = {};
      out.band = homeTodayHTML(p) || '';
      var placed = catalystPlacement(p, '2026-10-15T14:00:00-04:00');
      var items = [];
      placed.days.forEach(function (d) { d.items.forEach(function (it) { items.push(it); }); });
      out.items = items.map(function (it) { return {title: it.title, time: it.time, result: it.result}; });
      out.note = catalystNoteHTML(items.filter(function (it) { return it.title === 'PPI'; })[0]);
      out.pending = catalystNoteHTML(items.filter(function (it) { return it.title === 'Retail'; })[0]);
      out.row = homeTodayRow(p.columns[0].rows[2]);
      out.past = homeTodayRow(p.columns[1].rows[1]);
      print('RESULT:' + JSON.stringify(out));
    """ % json.dumps(PAYLOAD)
    proc = subprocess.run([exe, "-e", script], capture_output=True, text=True, timeout=180)
    blob = proc.stdout + proc.stderr
    assert "RESULT:" in blob, blob[-1500:]
    return json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])


def test_the_strip_shows_the_figure_where_out_was(page):
    times = {it["title"]: it for it in page["items"]}
    assert times["PPI"]["time"] == "+1.3%" and times["PPI"]["result"] is True
    assert times["PNC"]["time"] == "Beat", "a report goes on the strip by its ticker"
    assert times["Retail"]["time"] == "Out", "no figures yet: it says it is out, nothing more"
    assert times["Retail"]["result"] is False
    assert 'class="cs-time is-result">+1.3%<' in page["band"]


def test_a_result_with_no_description_still_opens(page):
    assert 'data-cs-note="PNC"' in page["band"]


def test_the_note_leads_with_the_figures_then_the_description(page):
    note = page["note"]
    assert note.index("+1.3% for September 2026") < note.index("What the producer price index measures.")
    assert 'class="cs-note-why"' in note, "the description is the muted line under the figures"
    assert "BLS: “PPI for final demand increases 1.3% in September”" in note
    assert 'href="https://www.bls.gov/news.release/ppi.nr0.htm"' in note and 'rel="noopener"' in note


def test_a_pending_result_says_so_and_keeps_the_description(page):
    note = page["pending"]
    assert "is-pending" in note and "have not reached Optic's feeds yet" in note
    assert "cs-note-why" not in note


def test_a_column_row_shows_its_figure_and_opens_onto_it(page):
    row = page["row"]
    assert '<span class="ht-res">+1.3%</span>' in row
    assert row.index("+1.3% for September 2026") < row.index("What the producer price index measures.")


def test_a_report_earlier_in_the_week_is_listed_with_its_verdict(page):
    """The strip starts today, so Tuesday's reports are in the column, and
    "GS reported Tuesday" does not say Tuesday twice."""
    past = page["past"]
    assert '<span class="ht-res">Beat</span>' in past
    assert "EPS 4.60 against 4.52 expected" in past
    assert "ht-when" not in past
    assert "GS reported Tuesday" in page["band"]


def test_the_figures_are_styled_from_tokens():
    for sel in (".cs-time.is-result", ".cs-note-result", ".cs-note-why", ".ht-res"):
        assert sel in CSS, sel
    block = CSS.split(".cs-note-result {", 1)[1].split("}", 1)[0]
    assert "var(--" in block and "#" not in block
