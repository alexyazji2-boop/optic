"""The brief's anchor rebuild runs once a day, not once a deploy.

The loop remembered the day it had forced the rebuild on app.state, which a
restart empties, and Railway starts a new process on every deploy. So thirty
seconds after each deploy the loop forced the day's brief again: a build
measured at 24.2s on the live site (2026-09-28), repeated on a day of several
deploys, and running while the first readers after the deploy loaded. The
archive on the volume already records when today's brief was last built.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

import app.main as main
from app import brief

ET = ZoneInfo("America/New_York")


@pytest.fixture
def archive(tmp_path, monkeypatch):
    monkeypatch.setattr(brief, "DB_PATH", str(tmp_path / "brief.db"))
    monkeypatch.setattr(main.app.state, "brief_anchor_day", None, raising=False)

    def built(day, when_et):
        with brief._connect() as conn:
            conn.execute("INSERT INTO briefs (day, payload, built_at, builds) VALUES (?, ?, ?, 1)",
                         (day, json.dumps({"day": day}),
                          when_et.astimezone(timezone.utc).isoformat()))
    return built


def test_a_restart_after_todays_anchor_build_does_not_force_another(archive):
    archive("2026-08-24", datetime(2026, 8, 24, 9, 5, tzinfo=ET))
    now = datetime(2026, 8, 24, 14, 0, tzinfo=ET)      # a deploy that afternoon
    assert main._brief_anchor_day(now) == "2026-08-24"
    assert main.brief_anchor_due(now, main._brief_anchor_day(now)) is None


def test_a_build_before_the_hour_does_not_count(archive):
    # 08:20 is before the last hour of overnight wires the anchor exists for.
    archive("2026-08-24", datetime(2026, 8, 24, 8, 20, tzinfo=ET))
    now = datetime(2026, 8, 24, 9, 30, tzinfo=ET)
    assert main._brief_anchor_day(now) is None
    assert main.brief_anchor_due(now, None) == "2026-08-24"


def test_yesterdays_build_does_not_count_today(archive):
    archive("2026-08-23", datetime(2026, 8, 23, 9, 5, tzinfo=ET))
    assert main._brief_anchor_day(datetime(2026, 8, 24, 10, 0, tzinfo=ET)) is None


def test_nothing_on_record_or_an_unreadable_archive_forces_as_before(archive, tmp_path, monkeypatch):
    now = datetime(2026, 8, 24, 14, 0, tzinfo=ET)
    assert main._brief_anchor_day(now) is None
    blocker = tmp_path / "a-file"
    blocker.write_text("")
    monkeypatch.setattr(brief, "DB_PATH", str(blocker / "brief.db"))   # its directory is a file
    assert brief.built_at("2026-08-24") is None
    assert main._brief_anchor_day(now) is None


class _Stop(BaseException):
    pass


def test_the_first_pass_after_a_restart_serves_the_days_brief_unforced(archive, monkeypatch):
    now_et = datetime.now(timezone.utc).astimezone(ET)
    archive(now_et.strftime("%Y-%m-%d"), now_et - timedelta(minutes=5))
    monkeypatch.setattr(main, "BRIEF_ANCHOR_HOUR", 0)     # the anchor is behind us, whenever this runs
    asked = []

    async def instant(*a, **k):
        return None

    def state(provider, day, force):
        asked.append(force)
        raise _Stop()

    monkeypatch.setattr(main.asyncio, "sleep", instant)
    monkeypatch.setattr(main.app.state, "last_account_sweep", 10 ** 12, raising=False)
    monkeypatch.setattr(main.snapshots, "due", lambda *a, **k: False)
    monkeypatch.setattr(main.brief_mod, "state", state)
    monkeypatch.setattr(main, "BRIEF_AUTO", True)
    with pytest.raises(_Stop):
        asyncio.run(main._tracker_loop())
    assert asked == [False], "the restart forced the day's brief again"
