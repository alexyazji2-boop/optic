"""Milo and "today": the two errors reported on 2026-10-14.

At 3:32pm Milo said $NVDA "rose roughly 1% to $228.52 today" while it traded at
$221: $228.52 and +1% were Tuesday's close and move, from the digest it had been
handed. And it wrote "$CRWV closed at $65.46" with the session open."""

from __future__ import annotations

from datetime import datetime, timezone

from app import ai, digest


def test_a_digest_says_which_session_its_close_belongs_to():
    briefing = {"available": True, "period": {"latest": "2026-10-13", "previous": "2026-10-12"},
                "names": [{"symbol": "NVDA", "state": "changed", "close": 228.52, "change_pct": 1.0}],
                "items": []}
    one = digest.compose("NVDA", briefing, {}, now=datetime(2026, 10, 14, 19, 30, tzinfo=timezone.utc))
    assert one["session_date"] == "2026-10-13" and one["close"] == 228.52
    assert "not today's trading" in one["describes"] and "2026-10-13" in one["describes"]
    many = digest.compose_list(["NVDA"], briefing, {}, now=datetime(2026, 10, 14, 19, 30, tzinfo=timezone.utc))
    assert many["session_date"] == "2026-10-13" and "not today's trading" in many["describes"]


def test_the_open_session_line_says_nothing_has_closed():
    in_session = datetime(2026, 10, 14, 19, 32, tzinfo=timezone.utc)          # 3:32pm ET, Wednesday
    line = ai._session_line(in_session)
    assert "nothing has closed today" in line and "not a closing price" in line
    after = datetime(2026, 10, 14, 21, 30, tzinfo=timezone.utc)
    assert "nothing has closed today" not in ai._session_line(after)


def test_todays_move_comes_from_the_quote_only():
    p = " ".join(ai.SYSTEM_PROMPT.split())
    assert "Today's price and today's move come from `quote`" in p
    assert "never call its move \"today\" unless that date is today" in p
    assert "never say a stock \"closed\" today" in p


def test_a_search_mid_answer_shows_live_under_the_text():
    from pathlib import Path
    app = (Path(__file__).resolve().parent.parent / "static/app.js").read_text()
    src = (Path(__file__).resolve().parent.parent / "app/ai.py").read_text()
    # A step that arrives after text has started goes to the live line, and the
    # next text clears it, as do the end, an error and a cut stream.
    assert "if (acc) pulseLiveStatus(node, words);" in app
    assert app.count("pulseLiveStatus(node, null);") >= 4
    assert "'reading results': 'Reading what it found'" in app
    assert 'yield _sse("status", {"state": "reading results"})' in src
