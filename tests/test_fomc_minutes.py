"""FOMC minutes on the calendar, and on Home's Today after they are out.

Asked for as "there FOMC minutes today? focus on accuracy here", on
2026-10-07. The September minutes came out at 2pm that day, the Fed's own
calendar page said "(Released October 07, 2026)" under the September 15-16
meeting, and Optic's calendar listed meetings only.

Checked against the Fed's page as fetched that afternoon: every minutes date it
gives for 2021-2026 is 21 days after the decision except two holiday weeks,
which came early (Nov 26, 2024 and Dec 30, 2025). Checked on the local server
at 3:05pm: Home's Today read "FOMC minutes · Out", and the list under it "Out
at 2:00 PM ET".
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from app import events, feeds, priority

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
MAIN = (ROOT / "app/main.py").read_text()


def _meeting(month, days, minutes=""):
    return (f'<div class="row fomc-meeting">'
            f'<div class="fomc-meeting__month col-md-2"><strong>{month}</strong></div>'
            f'<div class="fomc-meeting__date col-lg-1">{days}</div>'
            f'{minutes}</div>')


PAGE = ('<h4><a href="#">2026 FOMC Meetings</a></h4>'
        + _meeting("July", "28-29", 'Minutes: <a>PDF</a> | <a>HTML</a> (Released August 19, 2026)')
        + _meeting("September", "15-16*", 'Minutes: <a>PDF</a> | <a>HTML</a> (Released October 07, 2026)')
        + _meeting("October", "27-28")
        + _meeting("November", "6")
        + '<h4><a href="#">2025 FOMC Meetings</a></h4>'
        + _meeting("December", "9-10", 'Minutes: (Released December 30, 2025)'))


def _page(monkeypatch, text=PAGE):
    monkeypatch.setattr(feeds, "load_html", lambda *a, **k: {"text": text})


def test_out_minutes_take_the_date_the_fed_gives(monkeypatch):
    _page(monkeypatch)
    rows = {r["at"][:10]: r for r in events._fomc_minutes_events()["events"]}
    sep = rows["2026-10-07"]
    assert sep["title"] == "FOMC minutes from the September meeting"
    assert sep["short"] == "FOMC minutes" and sep["at"].startswith("2026-10-07T14:00")
    assert sep["confidence"] == "published"
    # The holiday week: the page's date, not the rule's January 1.
    assert rows["2025-12-30"]["confidence"] == "published"


def test_minutes_still_to_come_are_dated_by_the_rule_and_say_so(monkeypatch):
    _page(monkeypatch)
    rows = {r["at"][:10]: r for r in events._fomc_minutes_events()["events"]}
    october = rows["2026-11-18"]
    assert october["confidence"] == "estimated"
    assert "three weeks after the decision" in october["note"]
    assert not any(r["title"].endswith("November meeting") for r in rows.values()), \
        "a one-day meeting's minutes are not guessed"


def test_the_minutes_are_high_impact_with_their_own_reason():
    assert events._impact(8) == "high"
    assert "MINUTES_AFTER = timedelta(days=21)" in (ROOT / "app/events.py").read_text()
    why = events._why("FOMC minutes from the September meeting", "Fed")
    assert why == events.WHY_IT_MATTERS["fomc minutes"]
    assert why != events.WHY_IT_MATTERS["fomc"], "the decision's reason is not the minutes'"


def test_the_decisions_are_unchanged(monkeypatch):
    _page(monkeypatch)
    rows = events._fomc_events()["events"]
    assert [r["at"][:10] for r in rows] == ["2026-07-29", "2026-09-16", "2026-10-28",
                                            "2026-11-06", "2025-12-10"]
    assert all(r["short"] == "FOMC" for r in rows)


def test_a_note_belongs_to_the_meeting_it_sits_under(monkeypatch):
    """A note with no meeting before it in its month is dropped, not given to
    the meeting before that."""
    page = ('<h4>2026 FOMC Meetings</h4>' + _meeting("July", "28-29")
            + '<div class="fomc-meeting__month"><strong>August</strong></div>(Released August 19, 2026)')
    _page(monkeypatch, page)
    rows = events._fomc_minutes_events()["events"]
    assert [r["at"][:10] for r in rows] == ["2026-08-19"]
    assert rows[0]["confidence"] == "estimated", "the rule, not the stray note"


def _calendar(monkeypatch, now):
    _page(monkeypatch)
    monkeypatch.setattr(events, "_bls_events", lambda force=False: {"events": [], "error": None})
    monkeypatch.setattr(events, "_cot_events", lambda now: {"events": [], "error": None})
    monkeypatch.setattr(events, "_expiry_events", lambda now: {"events": [], "error": None})
    monkeypatch.setattr(events, "_readings", lambda title, days: {"available": False})
    monkeypatch.setattr(events, "_last_release", lambda title, force=False: None)


def test_home_keeps_minutes_that_came_out_earlier_today(monkeypatch):
    now = datetime(2026, 10, 7, 15, 5, tzinfo=events.ET)
    _calendar(monkeypatch, now)
    later = events.upcoming(now=now)["events"]
    assert not any(r["at"].startswith("2026-10-07") for r in later), \
        "every other reader of the calendar wants what is still to come"
    today = events.upcoming(now=now, earlier_today=True)["events"]
    row = next(r for r in today if r["short"] == "FOMC minutes")
    assert row["released"] is True and row["when_label"] == "Today"
    monkeypatch.setattr(priority.events_mod, "upcoming",
                        lambda now=None, earlier_today=False: {"events": today})
    board = priority._events(now)
    assert board[0]["time"] == "Out at 2:00 PM ET" and board[0]["released"] is True


def test_the_strip_says_out_and_the_desk_does_not_take_minutes_for_a_meeting():
    assert "time: row.released ? 'Out' : row.time" in APP
    block = MAIN[MAIN.index("for row in ((events_out or {}).get(\"events\") or []):"):]
    block = block[:block.index("break")]
    assert '"minutes" not in title' in block, "the rate path is priced to the decision"
    assert "'FOMC minutes': 'The Fed minutes'" in APP
    q = APP[APP.index("function catalystQuestion(data) {"):]
    q = q[:q.index("\n}\n")]
    assert "What could they change about the next decision?" in q
    assert not re.search(r"Fed minutes.{0,40}hot or a cool", q)


def test_the_calendar_says_what_estimated_means():
    assert "estimated: 'Dated by the Fed’s rule of three weeks after the decision." in APP
    assert "e.confidence === 'estimated' ? ' · estimated'" in APP
    assert "Rows marked <em>estimated</em> are FOMC minutes not yet out" in APP
