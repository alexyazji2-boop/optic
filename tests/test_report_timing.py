"""Report timing and the deeper read of a released result, on Home's What Matters Today.

Asked for on 2026-10-26 with screenshots of the live v2 strip: "FCX reports
Tuesday" did not say before the open or after the close, and a released result
was only "EPS 1.31 against 1.27 expected: beat by 2.8%".

What these hold: a session comes only from a source shown to be right (Yahoo's
quote on a confirmed date, outside the session, with the call agreeing; or the
surprise table's stamp on a released report) and otherwise the row says the
time is not set; the revenue estimate is the one Optic recorded before the
report and is used only when it is that quarter's; every figure the panel lacks
is named with its reason; and the v2 page shows the timing in the strip, the
lists and the detail without saying it twice. The live data behind these rules
(37 of 37 confirmed names, the 3 PM placeholders, Verizon's rolled consensus)
is in app/earnings_result.py's docstring.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from app import earnings_result as er
from app import priority
from app.providers import yf as yf_mod
from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"
HOME = (JS / "pages/home.js").read_text()

MON_NOON = datetime(2026, 10, 26, 16, 30, tzinfo=timezone.utc)      # 12:30 PM ET
MON_EVENING = datetime(2026, 10, 26, 22, 0, tzinfo=timezone.utc)    # 6 PM ET
TUE_NIGHT = datetime(2026, 10, 28, 1, 0, tzinfo=timezone.utc)       # Tue 9 PM ET


def _cal(day="2026-10-27", report="T12:30:00+00:00", call="T14:00:00+00:00", estimate=False, **extra):
    """Yahoo's calendar as the provider returns it, times in UTC as the quote gives them."""
    out = {"dates": [day], "date_is_estimate": estimate,
           "report_times": [day + report] if report else [], "call_at": day + call if call else None,
           "eps_avg": 1.27, "revenue_avg": 34.0e9}
    out.update(extra)
    return out


# ------------------------------------------------------------------ the session


def test_a_time_before_the_open_or_after_the_close_says_which():
    assert er.session_of("2026-10-27T08:30:00-04:00") == "before_open"
    assert er.session_of("2026-10-27T12:30:00+00:00") == "before_open"    # the same, as Yahoo sends it
    assert er.session_of("2026-10-27T16:00:00-04:00") == "after_close"
    assert er.session_of("2026-10-27T06:00:00-04:00") == "before_open"


def test_a_time_inside_the_session_or_at_midnight_says_nothing():
    """Yahoo's unscheduled reports sit at 3 PM (AAPL, NVDA, AMD on 2026-10-26)."""
    assert er.session_of("2026-11-02T15:00:00-05:00") is None
    assert er.session_of("2026-10-27T09:30:00-04:00") is None
    assert er.session_of("2026-10-27T00:00:00-04:00") is None
    assert er.session_of("2026-10-27T08:30:00") is None, "no zone, no time"
    assert er.session_of(None) is None


def test_a_scheduled_session_needs_a_confirmed_date():
    assert er.scheduled_session(_cal(), "2026-10-27") == "before_open"
    assert er.scheduled_session(_cal(estimate=True), "2026-10-27") is None, "an estimated date's time is a placeholder"
    assert er.scheduled_session(_cal(estimate=None), "2026-10-27") is None, "no flag, no trust"
    assert er.scheduled_session(_cal(), "2026-10-28") is None, "the quote's time is for another day"


def test_a_call_on_the_other_side_of_the_close_cancels_the_time():
    after = _cal(report="T20:00:00+00:00", call="T21:00:00+00:00")
    assert er.scheduled_session(after, "2026-10-27") == "after_close"
    assert er.scheduled_session(_cal(report="T20:00:00+00:00", call="T14:00:00+00:00"), "2026-10-27") is None
    assert er.scheduled_session(_cal(report="T12:30:00+00:00", call="T21:00:00+00:00"), "2026-10-27") is None
    # a call stamped on another day (NVDA's was August's) says nothing about this one
    stale = _cal(report="T20:00:00+00:00", call="T21:00:00+00:00")
    stale["call_at"] = "2026-08-26T21:00:00+00:00"
    assert er.scheduled_session(stale, "2026-10-27") == "after_close"


def test_a_released_report_uses_its_stamp_unless_the_quote_disagrees():
    row = {"date": "2026-10-26", "at": "2026-10-26T08:00:00-04:00"}
    assert er.released_session(row, {}, "2026-10-26") == "before_open"
    rolled = _cal(day="2026-10-26", estimate=True)        # after a report the flag is the next date's
    assert er.released_session(row, rolled, "2026-10-26") == "before_open", "the flag is not needed once it is out"
    late = _cal(day="2026-10-26", report="T20:00:00+00:00", call="T21:00:00+00:00")
    assert er.released_session(row, late, "2026-10-26") is None, "two sources that disagree give no time"
    assert er.released_session({"date": "2026-10-26", "at": "2026-10-26T15:00:00-04:00"}, {}, "2026-10-26") is None
    assert er.released_session(None, late, "2026-10-26") == "after_close"


def test_the_provider_keeps_a_reports_time_but_not_midnight():
    assert yf_mod._stamp_iso(pd.Timestamp("2026-10-26 06:00", tz="America/New_York")) == "2026-10-26T06:00:00-04:00"
    assert yf_mod._stamp_iso(pd.Timestamp("2026-10-26 00:00", tz="America/New_York")) is None
    assert yf_mod._stamp_iso(pd.Timestamp("2026-10-26 06:00")) is None


# ------------------------------------------------------------------ the board


class _Board:
    """Enough of the provider for priority._earnings."""

    def __init__(self, cals, history=None):
        self.cals, self.history_rows = cals, history or {}

    def earnings_calendar(self, symbol):
        return self.cals.get(symbol, {})

    def earnings_history(self, symbol, limit=6):
        return self.history_rows.get(symbol, [])


def _week(monkeypatch, days):
    monkeypatch.setattr(priority.weekly_mod, "earnings_this_week", lambda provider, now: {"days": days})


def test_every_report_says_before_the_open_after_the_close_or_time_not_set(monkeypatch):
    _week(monkeypatch, [{"day": "Tuesday", "date": "2026-10-27", "symbols": ["FCX", "V", "AAPL"]}])
    p = _Board({"FCX": _cal(),
                "V": _cal(report="T20:00:00+00:00", call="T21:00:00+00:00"),
                "AAPL": _cal(report="T19:00:00+00:00", call="T21:00:00+00:00")})
    rows = {r["ticker"]: r for r in priority._earnings(p, MON_NOON)}
    assert rows["FCX"]["title"] == "FCX reports Tuesday before the open"
    assert (rows["FCX"]["session"], rows["FCX"]["session_label"], rows["FCX"]["time"]) == \
        ("before_open", "Before the open", "Before open")
    assert rows["V"]["title"] == "V reports Tuesday after the close" and rows["V"]["time"] == "After close"
    assert rows["AAPL"]["title"] == "AAPL reports Tuesday, time not set"
    assert rows["AAPL"]["session"] is None and rows["AAPL"]["time"] is None, "no cell label rather than a guess"


def test_a_released_report_keeps_its_time_in_the_past_tense(monkeypatch, tmp_path):
    monkeypatch.setattr(er, "STORE_PATH", str(tmp_path / "c.json"))
    _week(monkeypatch, [{"day": "Monday", "date": "2026-10-26", "symbols": ["VZ"]}])
    p = _Board({"VZ": _cal(day="2026-10-26", estimate=True)},
               {"VZ": [{"date": "2026-10-26", "at": "2026-10-26T06:00:00-04:00", "timing": "before_open",
                        "eps_reported": 1.31, "eps_estimate": 1.27, "surprise_pct": 2.8}]})
    row = priority._earnings(p, MON_EVENING)[0]
    assert row["title"] == "VZ reported Monday before the open"
    assert row["time"] == "Before open" and row["result"]["short"] == "Beat"
    assert row["result"]["text"] == "EPS 1.31 against 1.27 expected: beat by 2.8%.", "the EPS line is unchanged"
    assert row["result"]["source"] == "Yahoo Finance surprise table (adjusted EPS)"


def test_the_method_says_where_the_time_comes_from():
    for words in ("confirmed", "outside the session", "time not set", "surprise table", "recorded before the report"):
        assert words in priority.EARNINGS_METHOD


# ------------------------------------------------------------ the recorded estimate


def test_the_consensus_is_recorded_before_the_report_and_not_after(tmp_path):
    path = str(tmp_path / "c.json")
    assert er.record_consensus("FCX", "2026-10-27", _cal(), "before_open", MON_NOON, path=path)
    assert er.recorded_consensus("FCX", "2026-10-27", path)["revenue_avg"] == 34.0e9
    rolled = _cal(eps_avg=0.9, revenue_avg=30.0e9)
    tue_morning = datetime(2026, 10, 27, 11, 0, tzinfo=timezone.utc)
    assert not er.record_consensus("FCX", "2026-10-27", rolled, "before_open", tue_morning, path=path), \
        "after midnight a report before the open may be out, and Yahoo's consensus the next quarter's"
    assert er.recorded_consensus("FCX", "2026-10-27", path)["revenue_avg"] == 34.0e9
    tue_afternoon = datetime(2026, 10, 27, 19, 0, tzinfo=timezone.utc)     # 3 PM ET
    assert er.record_consensus("V", "2026-10-27", _cal(), "after_close", tue_afternoon, path=path)
    assert not er.record_consensus("V", "2026-10-27", _cal(), "after_close", TUE_NIGHT, path=path)
    assert not er.record_consensus("X", "2026-10-27", _cal(day="2026-10-28"), None, MON_NOON, path=path), \
        "a calendar about another date is not this report's"


# ------------------------------------------------------------------ the result


class _Feeds:
    """The provider calls a released result makes."""

    def __init__(self, revenue=None, periods=None, closes=None, quote=None):
        self.revenue, self.periods = revenue, periods or []
        self.closes, self.q = closes, quote or {}

    def financials(self, symbol):
        if self.revenue is None:
            return {}
        return {"income_quarterly": {"periods": self.periods, "rows": {"Total Revenue": self.revenue}},
                "income_annual": {"periods": ["2025-12-31"]}}

    def history(self, symbol, period="1mo"):
        idx = pd.DatetimeIndex([pd.Timestamp(d) for d in self.closes])
        return pd.DataFrame({"Close": list(self.closes.values())}, index=idx)

    def quote(self, symbol):
        return self.q


PERIODS = ["2026-09-30", "2026-06-30", "2026-03-31", "2025-12-31", "2025-09-30"]
TABLE = [
    {"date": "2026-10-21", "eps_reported": 0.48, "eps_estimate": 0.45, "surprise_pct": 6.7, "at": "2026-10-21T16:00:00-04:00"},
    {"date": "2026-07-22", "eps_reported": 0.40, "eps_estimate": 0.42, "surprise_pct": -4.8},
    {"date": "2026-04-22", "eps_reported": 0.27, "eps_estimate": 0.27, "surprise_pct": 0.0},
    {"date": "2026-01-28", "eps_reported": 0.50, "eps_estimate": 0.45, "surprise_pct": 11.1},
    {"date": "2025-10-22", "eps_reported": 0.40, "eps_estimate": 0.50, "surprise_pct": -20.0},
]
CLOSES = {"2026-10-20": 100.0, "2026-10-21": 102.0, "2026-10-22": 96.9, "2026-10-23": 98.0}
THU_NIGHT = datetime(2026, 10, 23, 1, 0, tzinfo=timezone.utc)      # Thu 9 PM ET


def _result(tmp_path, record=None, revenue=(28.0e9, 0, 0, 0, 25.0e9), now=THU_NIGHT, side="after_close", table=TABLE,
            **feeds):
    path = str(tmp_path / "c.json")
    if record:
        er.record_consensus("TSLA", "2026-10-21", _cal(day="2026-10-21", **record), "after_close",
                            datetime(2026, 10, 20, 20, 0, tzinfo=timezone.utc), path=path)
    p = _Feeds(revenue=list(revenue) if revenue else None, periods=PERIODS, closes=CLOSES, **feeds)
    return er.build(p, "TSLA", "2026-10-21", table[0], table, {}, side, now, path=path)


def test_a_double_beat_is_said_plainly(tmp_path):
    d = _result(tmp_path, record={"eps_avg": 0.46, "revenue_avg": 27.0e9})
    assert d["revenue"]["verdict"] == "beat" and d["revenue"]["surprise_pct"] == 3.7
    assert d["revenue"]["reported_label"] == "$28.00B" and d["revenue"]["estimate_label"] == "$27.00B"
    assert d["combined"] == {"kind": "double beat", "text": "A double beat: EPS and revenue both above their estimates."}
    assert "revenue estimate: Yahoo consensus as Optic recorded it on Oct 20, before the report" in d["sources"]
    assert not any(m.startswith("Revenue estimate") or m.startswith("Double") for m in d["missing"])


def test_a_double_miss_and_a_mixed_result(tmp_path):
    table = [dict(TABLE[0], eps_reported=0.40, surprise_pct=-11.1)] + TABLE[1:]
    d = _result(tmp_path, record={"eps_avg": 0.45, "revenue_avg": 29.0e9}, table=table)
    assert d["combined"]["kind"] == "double miss"
    d = _result(tmp_path, record={"eps_avg": 0.45, "revenue_avg": 28.1e9})
    assert d["revenue"]["verdict"] == "in line"
    assert d["combined"] == {"kind": "mixed", "text": "Mixed: EPS beat, revenue in line."}


def test_without_a_recorded_estimate_the_panel_says_why(tmp_path):
    d = _result(tmp_path)
    assert d["revenue"]["available"] and "estimate" not in d["revenue"]
    assert d["combined"] is None
    assert ("Revenue estimate: not available. Yahoo moves its consensus to the next quarter once a company reports, "
            "and Optic had not recorded this quarter's before the release.") in d["missing"]
    assert "Double beat or miss: not called without revenue against its estimate." in d["missing"]


def test_an_estimate_recorded_for_another_quarter_is_not_used(tmp_path):
    """Verizon's calendar, hours after its report: still dated that morning, its
    EPS consensus 1.16 against the 1.27 the quarter was measured on."""
    d = _result(tmp_path, record={"eps_avg": 0.39, "revenue_avg": 27.0e9})
    assert "estimate" not in d["revenue"] and d["combined"] is None
    assert any(m.startswith("Revenue estimate: the one Optic recorded does not match") for m in d["missing"])


def test_an_estimate_on_another_basis_draws_no_verdict(tmp_path):
    d = _result(tmp_path, record={"eps_avg": 0.45, "revenue_avg": 20.0e9})
    assert "verdict" not in d["revenue"] and d["combined"] is None
    assert any("different bases" in m for m in d["missing"])


def test_without_reported_revenue_the_panel_says_why(tmp_path):
    d = _result(tmp_path, revenue=None)
    assert d["revenue"] == {"available": False}
    assert d["missing"][0].startswith("Reported revenue, and so its growth: not in Optic's feeds yet.")
    assert "revenue_text" not in d["growth"]


def test_last_quarters_revenue_is_not_this_quarters(tmp_path):
    """Verizon on its report day: Yahoo's newest quarter was June's, 118 days earlier."""
    p = _Feeds(revenue=[34.0e9, 34.4e9], periods=["2026-06-30", "2026-03-31"], closes=CLOSES)
    d = er.build(p, "VZ", "2026-10-26", TABLE[0], TABLE, {}, "before_open", THU_NIGHT, path=str(tmp_path / "c.json"))
    assert d["revenue"] == {"available": False}


def test_the_sec_filing_stands_in_when_the_statement_has_no_quarter(tmp_path, monkeypatch):
    monkeypatch.setattr(er, "sec_history", lambda s: {
        "available": True,
        "revenue_quarters": [{"period_end": "2026-09-30", "value": 28.0e9, "derived": False}],
        "revenue_yoy": [{"period_end": "2026-09-30", "value": 28.0e9, "prior": 25.0e9, "growth_pct": 12.0}]})
    d = _result(tmp_path, revenue=None)
    assert d["revenue"]["source"] == "SEC filing (XBRL)" and d["revenue"]["reported"] == 28.0e9
    assert d["growth"]["revenue_text"] == "Revenue up 12.0% on the same quarter a year earlier."


def test_growth_on_the_same_quarter_a_year_earlier(tmp_path):
    d = _result(tmp_path)
    assert d["growth"]["revenue_yoy_pct"] == 12.0
    assert d["growth"]["eps_text"] == "EPS up 20.0% from 0.40 a year earlier."
    loss = [dict(r) for r in TABLE]
    loss[4]["eps_reported"] = -0.10
    d = _result(tmp_path, table=loss)
    assert "eps_yoy_pct" not in d["growth"]
    assert "EPS growth: not meaningful against a loss of -0.10 a year earlier." in d["missing"]
    d = _result(tmp_path, table=TABLE[:3])
    assert "EPS growth: the surprise table has no report from a year earlier." in d["missing"]


def test_the_surprise_record_counts_the_last_reports(tmp_path):
    d = _result(tmp_path)
    assert d["record"]["text"] == "EPS beat 2 of the last 5, in line 1, missed 2."
    assert d["record"]["rows"][0] == {"date": "2026-10-21", "verdict": "beat", "surprise_pct": 6.7}
    d = _result(tmp_path, table=TABLE[:1])
    assert "Surprise record: the surprise table has fewer than two reports with an estimate." in d["missing"]


def test_the_reaction_is_the_session_that_traded_the_report(tmp_path):
    d = _result(tmp_path)
    assert d["reaction"]["kind"] == "session" and d["reaction"]["move_pct"] == -5.0
    assert d["reaction"]["text"] == "Down 5.0% in the session that reacted (Thu Oct 22)."
    d = _result(tmp_path, side="before_open")
    assert d["reaction"]["text"] == "Up 2.0% in the session that reacted (Wed Oct 21)."


def test_a_reaction_still_trading_or_in_extended_hours_says_so(tmp_path):
    thu_noon = datetime(2026, 10, 22, 16, 0, tzinfo=timezone.utc)
    d = _result(tmp_path, now=thu_noon, quote={"change_pct": -4.2})
    assert d["reaction"]["text"] == "Down 4.2% so far today; the session that reacts is still trading."
    wed_evening = datetime(2026, 10, 21, 22, 0, tzinfo=timezone.utc)
    d = _result(tmp_path, now=wed_evening, quote={"post_market_change_pct": 3.4})
    assert d["reaction"]["text"] == ("Up 3.4% after hours, on thin volume; the session that reacts (Thu Oct 22) "
                                     "has not opened.")
    d = _result(tmp_path, now=wed_evening, quote={})
    assert any(m.startswith("Price reaction: the session that reacts (Thu Oct 22) has not opened") for m in d["missing"])


def test_no_reaction_without_the_reports_time(tmp_path):
    d = _result(tmp_path, side=None)
    assert d["reaction"]["available"] is False
    assert ("Price reaction: the feed gives no time for this report, so it is not known whether that day's "
            "session or the next one reacted to it.") in d["missing"]


def test_the_board_says_double_beat_in_the_cell(monkeypatch, tmp_path):
    monkeypatch.setattr(er, "STORE_PATH", str(tmp_path / "c.json"))
    er.record_consensus("TSLA", "2026-10-21", _cal(day="2026-10-21", eps_avg=0.46, revenue_avg=27.0e9), "after_close",
                        datetime(2026, 10, 20, 20, 0, tzinfo=timezone.utc))

    class P(_Feeds, _Board):
        def __init__(self):
            _Feeds.__init__(self, revenue=[28.0e9, 0, 0, 0, 25.0e9], periods=PERIODS, closes=CLOSES)
            _Board.__init__(self, {}, {"TSLA": TABLE})

    res = priority._earnings_result(P(), "TSLA", "2026-10-21", THU_NIGHT, {})
    assert res["short"] == "Double beat" and res["session"] == "after_close"
    assert res["detail"]["combined"]["kind"] == "double beat"


# ------------------------------------------------------------------ the page


BOARD = """{ horizon_days: 5, generated_at: '2026-10-26T16:30:00Z', earnings_method: 'Before the open comes from Yahoo.', columns: [
  { id: 'earnings', rows: [
    { kind: 'earnings', impact: 'medium', ticker: 'VZ', title: 'VZ reported Monday before the open', when: 'Monday', date: '2026-10-26', days_away: 0,
      session: 'before_open', time: 'Before open', why: 'A report resets the estimate.',
      result: { short: 'Beat', text: 'EPS 1.31 against 1.27 expected: beat by 2.8%.', source: 'Yahoo Finance surprise table (adjusted EPS)',
        detail: { fiscal: 'Q3 2026', revenue: { available: false }, combined: null,
          growth: { eps_text: 'EPS up 8.3% from 1.21 a year earlier.' },
          record: { available: true, text: 'EPS beat 7 of the last 8, in line 1.' },
          reaction: { available: true, text: 'Down 2.9% so far today; the session that reacts is still trading.' },
          missing: ['Reported revenue, and so its growth: not in Optic\\'s feeds yet.', 'Revenue estimate: not available.'],
          sources: 'EPS: Yahoo Finance surprise table (adjusted EPS); prices: Yahoo Finance.' } } },
    { kind: 'earnings', impact: 'high', ticker: 'V', title: 'V reports Tuesday after the close', when: 'Tuesday', date: '2026-10-27', session: 'after_close', time: 'After close' },
    { kind: 'earnings', impact: 'medium', ticker: 'BA', title: 'BA reports Tuesday before the open', when: 'Tuesday', date: '2026-10-27', session: 'before_open', time: 'Before open' },
    { kind: 'earnings', impact: 'medium', ticker: 'FCX', title: 'FCX reports Tuesday, time not set', when: 'Tuesday', date: '2026-10-27', session: null, time: null },
    { kind: 'earnings', impact: 'medium', ticker: 'GM', title: 'GM reported Monday, time not known', when: 'Monday', date: '2026-10-26', result: { short: 'Missed', text: 'EPS 1.00 against 1.10 expected: missed by 9.1%.' } }] }] }"""


def test_the_strip_says_the_time_and_keeps_it_under_a_result(tmp_path):
    got = _run(tmp_path, f"""
      const H = await import('{(JS / "pages/home.js").as_posix()}');
      const r = H.catalystDays({BOARD}, '2026-10-26');
      print(JSON.stringify(r.days.slice(0, 2).map((d) => d.items.map((i) => [i.title, i.time, i.sess]))));
    """)
    assert got[0] == [["VZ", "Beat", "Before open"], ["GM", "Missed", ""]], "a released report keeps its time; none, nothing"
    assert got[1] == [["V", "After close", ""], ["BA", "Before open", ""], ["FCX", "", ""]], "no label for a time not set"


def test_the_rest_of_a_day_and_the_list_say_the_time_once(tmp_path):
    got = _run(tmp_path, f"""
      const H = await import('{(JS / "pages/home.js").as_posix()}');
      const {{ toString }} = await import('{(JS / "core/dom.js").as_posix()}');
      const b = {BOARD};
      H.evPress({{ closest: (sel) => (sel === '[data-v2-cs]' ? {{ dataset: {{ v2Cs: 'more:2026-10-27' }} }} : null) }});
      const strip = toString(H.catalystStrip(b, '2026-10-26'));
      const list = toString(H.eventsBlock(b, [], 'all'));
      print(JSON.stringify({{ strip, list }}));
    """)
    rest = got["strip"][got["strip"].index("the rest"):]
    assert "FCX reports Tuesday, time not set</b>" in rest and "Before open" not in rest.split("</ul>")[0], \
        "the title says the time; no second label beside it"
    assert "before the open<small>" in got["list"] and "before the open<small>Before open" not in got["list"]
    assert "How this is sorted and timed" in got["list"] and "Before the open comes from Yahoo." in got["list"]


def test_a_released_report_reads_past_its_eps_line(tmp_path):
    got = _run(tmp_path, f"""
      const H = await import('{(JS / "pages/home.js").as_posix()}');
      const {{ toString }} = await import('{(JS / "core/dom.js").as_posix()}');
      const b = {BOARD};
      H.evPress({{ closest: (sel) => (sel === '[data-v2-cs]' ? {{ dataset: {{ v2Cs: 'item:earnings|VZ|2026-10-26|' }} }} : null) }});
      const note = toString(H.catalystStrip(b, '2026-10-26'));
      print(JSON.stringify({{ note: note.slice(note.indexOf('id="cs-note"')) }}));
    """)
    note = got["note"]
    assert "VZ reported Monday before the open" in note
    assert "Q3 2026: EPS 1.31 against 1.27 expected: beat by 2.8%." in note
    for label, text in (("Year on year", "EPS up 8.3% from 1.21 a year earlier."),
                        ("Record", "EPS beat 7 of the last 8, in line 1."),
                        ("Reaction", "Down 2.9% so far today; the session that reacts is still trading.")):
        assert f"<dt>{label}</dt><dd>{text}</dd>" in note
    assert "<dt>Revenue</dt>" not in note and "<dt>Together</dt>" not in note, "nothing drawn for a figure not in hand"
    assert "Not in Optic&#39;s data yet: reported revenue, and so its growth; revenue estimate</summary>" in note \
        or "Not in Optic's data yet: reported revenue, and so its growth; revenue estimate</summary>" in note
    assert "EPS: Yahoo Finance surprise table (adjusted EPS); prices: Yahoo Finance." in note


def test_the_revenue_line_says_both_figures_and_the_verdict(tmp_path):
    got = _run(tmp_path, f"""
      const H = await import('{(JS / "pages/home.js").as_posix()}');
      const {{ toString }} = await import('{(JS / "core/dom.js").as_posix()}');
      const b = {BOARD};
      const d = b.columns[0].rows[0].result.detail;
      d.revenue = {{ available: true, reported_label: '$28.00B', estimate: 27e9, estimate_label: '$27.00B', verdict: 'beat', surprise_pct: 3.7 }};
      d.combined = {{ kind: 'double beat', text: 'A double beat: EPS and revenue both above their estimates.' }};
      d.missing = [];
      H.evPress({{ closest: (sel) => (sel === '[data-v2-cs]' ? {{ dataset: {{ v2Cs: 'item:earnings|VZ|2026-10-26|' }} }} : null) }});
      const one = toString(H.catalystStrip(b, '2026-10-26'));
      d.revenue = {{ available: true, reported_label: '$28.00B' }};
      const two = toString(H.catalystStrip(b, '2026-10-26'));
      print(JSON.stringify({{ one, two }}));
    """)
    assert "<dt>Together</dt><dd>A double beat: EPS and revenue both above their estimates.</dd>" in got["one"]
    assert "<dt>Revenue</dt><dd>$28.00B against $27.00B expected: beat by 3.7%.</dd>" in got["one"]
    assert "Not in Optic" not in got["one"], "nothing missing, no fold"
    assert "<dt>Revenue</dt><dd>$28.00B reported, with no estimate to set it against.</dd>" in got["two"]


def test_no_em_dash_in_the_new_copy():
    for text in (open("app/earnings_result.py", encoding="utf-8").read(),
                 HOME[HOME.index("function reportBody("):HOME.index("const shortResult")]):
        assert "—" not in text
