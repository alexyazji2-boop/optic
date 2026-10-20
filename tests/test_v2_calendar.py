"""The Read's calendar (backlog task 9, 2026-10-20): days and "released" from the clock now, each date's
status in words, a previous reading with its period, the week's company reports in their days, no pills.

calendarItems and periodOf run in JavaScriptCore; the tab itself was driven in headless Chrome at 360, 390,
430, 844x390, 768 and 1440 px on the 2026-10-19 live Read and a fixture of company reports
(~/Optic/work/v2-backlog/cal_check.py), since the local Read is not built overnight.
"""
from tests.test_frontend_v2_stage0 import V2, _run

READ = (V2 / "js/pages/read.js").read_text()


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
    assert "Previous reading${r.as_of ? `, for ${periodOf(r.as_of, r.series_label)}` : ''}" in cal
    assert 'class="pill"' not in cal and 'class="pill"' not in READ.split("function catalystMode")[1].split("function library")[0]
    assert "No consensus forecasts" in cal and "Company reports" in cal and "#/${e.ticker}/earnings" in cal
