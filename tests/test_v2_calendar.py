"""The Read's calendar (backlog task 9, 2026-10-20): days and "released" from the clock now, each date's
status in words, a previous reading with its period, the week's company reports in their days, no pills.

calendarItems and periodOf run in JavaScriptCore; the tab itself was driven in headless Chrome at 360, 390,
430, 844x390, 768 and 1440 px on the 2026-10-19 live Read and a fixture of company reports
(~/Optic/work/v2-backlog/cal_check.py), since the local Read is not built overnight; then in market hours on
2026-10-20 against the server's own Read and Today's priority (~/Optic/work/v2-backlog/cal_live.py).
"""
import json
from datetime import datetime

from app import events, fred
from app.fred import SERIES_MAP
from tests.test_frontend_v2_stage0 import V2, _run

READ = (V2 / "js/pages/read.js").read_text()


def test_every_quarterly_reading_is_named_by_its_quarter(tmp_path):
    """periodOf names a quarter from the series label. Productivity's label did not say quarterly, so its Q2
    reading (FRED dates a quarter by its first day, 2026-04-01) read "Previous reading, for April 2026" on the
    live Read, 2026-10-20. Every series the Read can show is checked with its own label."""
    specs = [[s["series"], s["transform"], s["label"]] for s in SERIES_MAP.values()]
    got = _run(tmp_path, f"""
      const r = await import('{(V2 / "js/pages/read.js").as_posix()}');
      const specs = {json.dumps(specs)};
      print(JSON.stringify(specs.map(([id, t, label]) => [id, t, r.periodOf('2026-04-01', label)])));
    """)
    for sid, transform, name in got:
        assert name == ("Q2 2026" if "qoq" in transform else "April 2026"), f"{sid} ({transform}) is named {name!r}"


def test_items_take_their_day_and_status_from_now(tmp_path):
    got = _run(tmp_path, f"""
      const r = await import('{(V2 / "js/pages/read.js").as_posix()}');
      const now = new Date('2026-10-20T14:00:00Z');        // 10:00 AM ET, Tuesday
      const c = {{ events: [
        {{ title: 'Out at 8:30', at: '2026-10-20T08:30:00-04:00', released: false, days_away: 1, when_label: 'Tomorrow' }},
        {{ title: 'Due at noon', at: '2026-10-20T12:00:00-04:00', released: false }},
        {{ title: 'Yesterday', at: '2026-10-19T10:00:00-04:00', released: true }},
        {{ title: 'Thursday', at: '2026-10-22T08:30:00-04:00' }} ] }};
      const pr = {{ columns: [{{ id: 'earnings', rows: [{{ ticker: 'NFLX', date: '2026-10-20', impact: 'high' }}, {{ ticker: 'IBM', date: '2026-10-21' }}] }}] }};
      const o = r.calendarItems(c, pr, now);
      print(JSON.stringify({{ today: o.today, tomorrow: o.tomorrow, rows: o.items.map((e) => [e.title, e.day, e.days_away, !!e.released, e.kind]) }}));
    """)
    assert got["today"] == "2026-10-20" and got["tomorrow"] == "2026-10-21"
    rows = {r[0]: r[1:] for r in got["rows"]}
    assert rows["Out at 8:30"] == ["2026-10-20", 0, True, "macro"], "a Read built yesterday called it tomorrow and due"
    assert rows["Due at noon"] == ["2026-10-20", 0, False, "macro"]
    assert rows["Yesterday"][1] == -1
    assert rows["NFLX reports"] == ["2026-10-20", 0, False, "report"] and rows["IBM reports"][1] == 1
    order = [r[0] for r in got["rows"]]
    assert order.index("Due at noon") < order.index("NFLX reports") < order.index("IBM reports") < order.index("Thursday")


def test_a_reading_names_its_period(tmp_path):
    got = _run(tmp_path, f"""
      const r = await import('{(V2 / "js/pages/read.js").as_posix()}');
      print(JSON.stringify([r.periodOf('2026-09-01', 'Nonfarm payrolls, change on the month'), r.periodOf('2026-04-01', 'Employment cost index, quarter over quarter'), r.periodOf('', 'x')]));
    """)
    assert got == ["September 2026", "Q2 2026", ""]


def test_the_calendar_says_what_each_line_is():
    cal = READ[READ.index("const DATE_WORD"):READ.index("function headlines")]
    assert "Date published by" in cal and "Recurring date, set by rule" in cal and "Estimated date, not yet published" in cal
    assert "`Released${when ? ` ${when}` : ''}`" in cal and "`Due ${when}`" in cal
    assert "Previous reading${pAsOf ? `, for ${periodOf(pAsOf, r.series_label)}` : ''}" in cal
    assert 'class="pill"' not in cal and 'class="pill"' not in READ.split("function catalystMode")[1].split("function library")[0]
    assert "No consensus forecasts" in cal and "Company reports" in cal and "#/${e.ticker}/earnings" in cal


SEPT = [("2026-07-01", 159000.0), ("2026-08-01", 159133.0), ("2026-09-01", 159162.0)]   # FRED on 2026-10-20
OCT = SEPT + [("2026-10-01", 159250.0)]                                                   # once FRED has October


def _jobs_day(monkeypatch, now, rows=SEPT):
    """Jobs day, 2026-11-06 (the October report), with the payrolls series as FRED has it: by default as it was on
    2026-10-20, September the last print."""
    monkeypatch.setattr(fred, "observations", lambda series, timeout=None: rows)
    bls = [{"title": "Employment Situation", "at": "2026-11-06T08:30:00-05:00", "importance": 10, "agency_short": "BLS",
            "confidence": "published"},
           {"title": "Employment Situation", "at": "2026-11-06T14:00:00-05:00", "importance": 10, "agency_short": "BLS",
            "confidence": "published"}]
    monkeypatch.setattr(events, "_bls_events", lambda force=False: {"events": [dict(r) for r in bls], "error": None})
    for leg in ("_fomc_events", "_fomc_minutes_events"):
        monkeypatch.setattr(events, leg, lambda force=False: {"events": [], "error": None})
    monkeypatch.setattr(events, "_cot_events", lambda now: {"events": [], "error": None})
    monkeypatch.setattr(events, "_expiry_events", lambda now: {"events": [], "error": None})
    monkeypatch.setattr(events, "_last_release", lambda title, force=False: None)
    return {r["at"][11:16]: r for r in events.upcoming(now=now, earlier_today=True)["events"]}


def test_a_release_later_today_is_still_to_come(monkeypatch):
    """Upcoming by the clock, not the day: at 7 AM on jobs day the release had not printed, yet its readings said
    September's +29k was this release's figure and August's +133k was September's (the live payrolls series with
    the clock at 2026-11-06 07:00 ET, 2026-10-20)."""
    rows = _jobs_day(monkeypatch, datetime(2026, 11, 6, 7, 0, tzinfo=events.ET))
    r = rows["08:30"]["readings"]
    assert rows["08:30"]["released"] is False and r["is_upcoming"] is True
    assert r["actual"] is None and r["previous"] == 29 and r["previous_as_of"] == "2026-09-01"


def test_a_release_out_today_names_the_period_of_the_figure_before_it(monkeypatch):
    rows = _jobs_day(monkeypatch, datetime(2026, 11, 6, 10, 0, tzinfo=events.ET), OCT)
    out, due = rows["08:30"], rows["14:00"]
    assert out["released"] is True and out["readings"]["is_upcoming"] is False and not out["readings"]["feed_pending"]
    assert out["readings"]["actual"] == 88 and out["readings"]["previous"] == 29
    assert out["readings"]["previous_as_of"] == "2026-09-01", "29k is September's, not the as_of month's"
    assert due["released"] is False and due["readings"]["is_upcoming"] is True


def test_a_release_out_before_fred_has_it_is_not_given_the_month_before(monkeypatch):
    """Out is not in FRED: at 10 AM on jobs day FRED can still end at September, and its +29k is not the October
    report's figure. It stays the previous reading, for September, and the new one is said to be on its way."""
    rows = _jobs_day(monkeypatch, datetime(2026, 11, 6, 10, 0, tzinfo=events.ET))
    r = rows["08:30"]["readings"]
    assert rows["08:30"]["released"] is True and r["is_upcoming"] is False and r["feed_pending"] is True
    assert r["actual"] is None and r["previous"] == 29 and r["previous_as_of"] == "2026-09-01"


def test_each_release_reports_on_its_own_period():
    """The period a release covers, as FRED dates it: the jobs report the month before, JOLTS the one before that,
    the quarterly releases the quarter before. A series with no rule (the weekly mortgage rate) has none."""
    from datetime import date
    got = {t: fred.reference_period(t, d) for t, d in [
        ("Employment Situation", date(2026, 11, 6)), ("Consumer Price Index", date(2027, 1, 13)),
        ("Job Openings and Labor Turnover Survey", date(2026, 11, 3)), ("Employment Cost Index", date(2026, 10, 30)),
        ("Productivity and Costs", date(2026, 11, 5)), ("Gross Domestic Product", date(2027, 1, 28)),
        ("30-year mortgage rate", date(2026, 10, 22)), ("Usual Weekly Earnings", date(2026, 10, 21))]}
    assert got == {"Employment Situation": "2026-10-01", "Consumer Price Index": "2026-12-01",
                   "Job Openings and Labor Turnover Survey": "2026-09-01", "Employment Cost Index": "2026-07-01",
                   "Productivity and Costs": "2026-07-01", "Gross Domestic Product": "2026-10-01",
                   "30-year mortgage rate": None, "Usual Weekly Earnings": None}
    assert all("reports" in v for k, v in SERIES_MAP.items() if k != "mortgage rate"), "every BLS-calendar series"


def test_the_read_keeps_todays_releases_and_the_note_is_told_only_what_is_to_come(monkeypatch):
    """Asked for only what was still to come, the Read dropped a release from its own Today within one 20-minute
    build of printing (the 10:00 BLS release was on the 8:10 build and gone from the 11:04 one, 2026-10-20). The
    written note still gets only what is ahead, so it cannot write about a print that is out as if it were coming."""
    from app import brief
    src = (V2.parents[1] / "app/brief.py").read_text()
    assert "calendar = events.upcoming(earlier_today=True)" in src
    seen = {}
    monkeypatch.setattr(brief, "_narrative", lambda overview, wires: {"paragraphs": []})
    monkeypatch.setattr(brief, "_edition_read", lambda edition, facts: seen.update(facts) or None)
    cal = {"events": [{"title": "Out at 8:30", "released": True}, {"title": "Due at 2", "released": False}]}
    brief._morning_read({}, {}, cal, {}, index_regime={}, global_context={})
    assert [e["title"] for e in seen["upcoming_calendar"]] == ["Due at 2"]


def test_classic_marks_a_release_out_and_a_figure_fred_has_not_posted():
    app = (V2.parents[0] / "app.js").read_text()
    row = app[app.index("function calReadings(r)"):app.index("/* Vanna and charm exposure")]
    assert "${e.released ? 'Out at ' : ''}${esc(e.time_label || 'all day')}" in row
    assert "r.is_upcoming || r.feed_pending ? 'pending' : null" in row
    assert "const before = readings.is_upcoming || readings.feed_pending;" in row and "before ? 'Previous reading' : 'This print'" in row


def test_fred_says_which_observation_the_previous_figure_is():
    spec = SERIES_MAP["employment situation"]
    got = fred._present(spec, [("2026-07-01", 1.0), ("2026-08-01", 2.0), ("2026-09-01", 4.0)])
    assert got["as_of"] == "2026-09-01" and got["previous_as_of"] == "2026-08-01"


def test_the_page_names_the_previous_figures_own_period_and_no_figure_for_a_release_still_due():
    cal = READ[READ.index("function calItem"):READ.index("function calendar()")]
    assert "const pAsOf = r.previous_as_of || (r.is_upcoming ? r.as_of : '');" in cal
    assert "const actual = r.available && e.released ?" in cal and "!r.is_upcoming" not in cal
