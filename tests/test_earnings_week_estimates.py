"""The Earnings this week panel: a report already out shows its own quarter's
estimates, and every row says when it lands.

Seen live on 2026-10-26: Verizon reported Q3 before the open (EPS 1.31 against
1.27), and the panel showed EPS est. 1.16 and revenue est. 37.3B, which were
Yahoo's Q4 consensus. Yahoo moves its consensus to the next quarter once a
company reports while its calendar still shows the report's date. The panel's
note also still said the provider had no before-open or after-close tag, which
Home's What Matters Today has used since 86bb730.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app import earnings_result as er
from app import earnings_week as ew
from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"

MON_NOON = datetime(2026, 10, 26, 16, 30, tzinfo=timezone.utc)      # 12:30 PM ET
MON_8AM = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)        # 8 AM ET
MON_10AM = datetime(2026, 10, 26, 14, 0, tzinfo=timezone.utc)       # 10 AM ET
WED_NOON = datetime(2026, 10, 28, 16, 0, tzinfo=timezone.utc)       # Wed noon ET


def _cal(day, report="T12:30:00+00:00", estimate=False, eps=1.16, revenue=37.26e9):
    return {"dates": [day], "date_is_estimate": estimate, "confirmed": not estimate,
            "report_times": [day + report] if report else [], "call_at": None,
            "eps_avg": eps, "eps_low": eps - 0.05, "eps_high": eps + 0.05, "revenue_avg": revenue}


class _Provider:
    def __init__(self, dates, cals, hist=None):
        self.dates, self.cals, self.hist = dates, cals, hist or {}

    def earnings_date(self, symbol):
        return self.dates.get(symbol)

    def earnings_calendar(self, symbol):
        return self.cals.get(symbol, {})

    def earnings_history(self, symbol, limit=10):
        return self.hist.get(symbol, [])

    def profile(self, symbol):
        return {"name": symbol + " Inc", "website": "https://www.example.com"}


VZ_ROW = {"date": "2026-10-26", "at": "2026-10-26T07:00:00-04:00",
          "eps_reported": 1.31, "eps_estimate": 1.27, "surprise_pct": 2.8}


def _row(out, ticker):
    return next(r for d in out["days"] for r in d["rows"] if r["ticker"] == ticker)


def _vz(now=MON_NOON, hist=True):
    p = _Provider({"VZ": "2026-10-26"}, {"VZ": _cal("2026-10-26")}, {"VZ": [VZ_ROW] if hist else []})
    return _row(ew.build(p, now=now, watchlist=["VZ"]), "VZ")


def test_a_reported_row_shows_that_quarters_eps_estimate_not_the_next():
    r = _vz()
    assert r["reported"] is True
    assert r["eps_consensus"] == 1.27 and r["eps_consensus_source"] == "surprise_table"
    assert r["eps_reported"] == 1.31 and r["surprise_pct"] == 2.8 and r["result_short"] == "Beat"
    assert r["eps_low"] is None and r["eps_high"] is None, "Yahoo's live range is the next quarter's"


def test_a_reported_row_without_a_record_shows_no_revenue_estimate_and_says_why():
    r = _vz()
    assert r["revenue_consensus"] is None, "37.26B was Q4's"
    assert "not recorded before the release" in r["estimate_note"]
    assert "next quarter" in r["estimate_note"]


def test_a_recorded_estimate_that_matches_supplies_the_revenue():
    er.record_consensus("VZ", "2026-10-26", _cal("2026-10-26", eps=1.27, revenue=33.9e9), "before_open",
                        datetime(2026, 10, 25, 18, 0, tzinfo=timezone.utc))
    r = _vz()
    assert r["revenue_consensus"] == 33.9e9 and r["eps_consensus"] == 1.27
    assert r["estimate_note"] is None


def test_a_recorded_estimate_for_another_quarter_is_not_used():
    er.record_consensus("VZ", "2026-10-26", _cal("2026-10-26", eps=1.16, revenue=37.26e9), "before_open",
                        datetime(2026, 10, 25, 18, 0, tzinfo=timezone.utc))
    r = _vz()
    assert r["revenue_consensus"] is None and r["eps_consensus"] == 1.27


def test_a_report_out_before_the_table_has_it_uses_the_record_or_nothing():
    p = _Provider({"GM": "2026-10-26"}, {"GM": _cal("2026-10-26", eps=2.80)})
    r = _row(ew.build(p, now=WED_NOON, watchlist=["GM"]), "GM")
    assert r["reported"] is True and r["eps_consensus"] is None and r["revenue_consensus"] is None
    assert r["estimate_note"].startswith("Reported. Yahoo has moved its estimates to the next quarter")
    er.record_consensus("GM", "2026-10-26", _cal("2026-10-26", eps=2.40, revenue=44e9), "before_open",
                        datetime(2026, 10, 25, 18, 0, tzinfo=timezone.utc))
    r = _row(ew.build(p, now=WED_NOON, watchlist=["GM"]), "GM")
    assert r["eps_consensus"] == 2.40 and r["eps_consensus_source"] == "recorded"
    assert r["revenue_consensus"] == 44e9


def test_a_confirmed_report_past_its_time_counts_as_out_before_the_table_catches_up():
    assert _vz(now=MON_10AM, hist=False)["reported"] is True, "8:30 AM report, 10 AM read"
    early = _vz(now=MON_8AM, hist=False)
    assert early["reported"] is False and early["eps_consensus"] == 1.16, "still to come: the live consensus"


def test_a_report_still_to_come_keeps_the_live_consensus_and_is_recorded():
    p = _Provider({"V": "2026-10-27"}, {"V": _cal("2026-10-27", report="T20:05:00+00:00", eps=2.97, revenue=10.6e9)})
    r = _row(ew.build(p, now=MON_NOON, watchlist=["V"]), "V")
    assert r["reported"] is False and r["eps_consensus"] == 2.97 and r["revenue_consensus"] == 10.6e9
    assert r["session"] == "after_close" and r["time"] == "After close" and r["session_label"] == "After the close"
    assert er.recorded_consensus("V", "2026-10-27")["revenue_avg"] == 10.6e9, "kept for when Yahoo rolls it"


def test_the_time_comes_only_from_a_trusted_stamp():
    assert _vz()["session"] == "before_open", "the surprise table's 7 AM stamp"
    p = _Provider({"AAPL": "2026-10-29"},
                  {"AAPL": _cal("2026-10-29", report="T19:00:00+00:00", estimate=True)})
    r = _row(ew.build(p, now=MON_NOON, watchlist=["AAPL"]), "AAPL")
    assert r["session"] is None and r["time"] is None, "an unconfirmed 3 PM placeholder is no time"


def test_the_session_note_says_where_the_time_comes_from():
    note = ew.SESSION_NOTE
    assert "no before-open or after-close tag" not in note
    assert "confirmed the date" in note and "time not set" in note and "next quarter" in note
    assert "—" not in note
    out = ew.build(_Provider({}, {}), now=MON_NOON, watchlist=[])
    assert out["session_note"] == note


BODY = """{ available: true, week_label: 'Oct 26 – 30', checked: 2, days: [
  { day: 'Monday', short: 'Mon', day_number: 26, is_past: false, rows: [
    { ticker: 'VZ', name: 'Verizon', confirmed: true, reported: true, eps_reported: 1.31, eps_consensus: 1.27,
      revenue_consensus: null, result_short: 'Beat', session: 'before_open', session_label: 'Before the open', time: 'Before open',
      estimate_note: "Revenue estimate not recorded before the release; Yahoo's current one is the next quarter's." }] },
  { day: 'Tuesday', short: 'Tue', day_number: 27, is_past: false, rows: [
    { ticker: 'FCX', name: 'Freeport', confirmed: true, reported: false, eps_consensus: 0.4, revenue_consensus: 6.6e9,
      session: null, session_label: null, time: null }] }] }"""


def test_the_home_panel_shows_the_time_and_the_reported_quarters_estimate(tmp_path):
    got = _run(tmp_path, f"""
      const W = await import('{(JS / "pages/workspace.js").as_posix()}');
      W._test.load();
      const {{ toString }} = await import('{(JS / "core/dom.js").as_posix()}');
      print(JSON.stringify(toString(W.PANELS.earnings.body({BODY}, {{ offset: 0, im: {{}} }}))));
    """)
    vz = got[got.index(">VZ<"):got.index(">FCX<")]
    assert 'Mon 26<span class="ws-rule">Before open</span>' in got
    assert ">1.27<" in vz and "1.16" not in vz
    assert "Not recorded" in vz and "Reported: beat" in vz
    assert 'Tue 27<span class="ws-rule">Time not set</span>' in got


def test_the_earnings_page_says_the_result_and_the_time(tmp_path):
    got = _run(tmp_path, f"""
      const E = await import('{(JS / "pages/earningsweek.js").as_posix()}');
      const {{ toString }} = await import('{(JS / "core/dom.js").as_posix()}');
      const b = {BODY};
      print(JSON.stringify(b.days.map((d) => toString(E._test.row(d.rows[0])))));
    """)
    vz, fcx = got
    assert "EPS <b>1.31</b> against 1.27 expected: beat" in vz
    assert "<span>Before the open</span>" in vz and ">Revenue estimate not recorded</span>" in vz
    assert 'title="Revenue estimate not recorded before the release' in vz, "the reason on hover"
    assert "EPS <b>0.40</b>, revenue <b>$6.6B</b>" in fcx and "<span>Time not set</span>" in fcx
