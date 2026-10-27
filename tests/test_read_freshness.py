"""The written Read says which session it covers, and its figures are checked.

The close edition of 26 October 2026 (the fixture, as /api/brief served it that
night) called that day's chip rally "yesterday", and said 64% of sectors were
above their 200-day average while Macro showed 55%. The first because the
writer is a morning note nobody told which session it covered; the second
because the figure it was handed was the share of sectors up that day (7 of
11), under a name that did not say so."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import ai, brief
from tests.test_ai_credits import claude  # noqa: F401  (the stubbed client)

FIX = json.loads((Path(__file__).parent / "fixtures" / "read_close_edition_2026-10-26.json").read_text())
ROOT = Path(__file__).parent.parent


@pytest.mark.parametrize("edition, date, words", [
    ("2026-10-26:close", "2026-10-26", "today"),          # written after Monday's close
    ("2026-10-27:overnight", "2026-10-26", "yesterday"),
    ("2026-10-27:morning", "2026-10-26", "yesterday"),
    ("2026-10-26:morning", "2026-10-23", "on Friday"),     # Monday before the open
    ("2026-10-31:closed", "2026-10-30", "yesterday"),      # Saturday
    ("2026-11-26:closed", "2026-11-25", "yesterday"),      # Thanksgiving
    ("2026-11-27:close", "2026-11-27", "today"),           # the early close after it
])
def test_the_covered_session_and_its_words(edition, date, words):
    got = brief.covered_session(edition)
    assert (got["date"], got["words"]) == (date, words)
    assert words in got["rule"]


def test_the_breadth_sentence_is_checked_against_the_200_day_share():
    facts = {"sectors": FIX["sectors"], "indices": FIX["indices"], "themes": FIX["themes"],
             "index_regime": FIX["index_regime"], "sectors_up_today_pct": FIX["sector_breadth_pct"],
             "sectors_above_200d_pct": 54.5}
    out = brief.check_figures(FIX["paragraphs"], facts)
    bad = {u["figure"]: u["why"] for u in out["unmatched"]}
    assert bad.get("64%") == "the data's share of sectors above their 200-day average is 54.5%"
    assert out["checked"] > 20


def test_a_breadth_sentence_with_the_right_share_passes():
    facts = {"sectors_above_200d_pct": 54.5, "x": [2.7]}
    out = brief.check_figures(["Breadth: **55%** of sectors are above their 200-day average. Semis **2.7%**."], facts)
    assert out == {"checked": 2, "unmatched": []}


def test_a_figure_the_data_does_not_have_is_listed():
    out = brief.check_figures(["The S&P rose **3.4%**."], {"spy": {"day": 0.71}})
    assert out["unmatched"] == [{"figure": "3.4%", "why": "not in the data this was written from"}]


def test_the_writer_is_told_the_session_and_both_breadths_and_the_edition_records_them(claude, monkeypatch):  # noqa: F811
    monkeypatch.setattr(brief, "read_edition", lambda now=None: "2026-10-26:close")
    overview = {"groups": {"sectors": FIX["sectors"], "indices": FIX["indices"]},
                "sector_breadth_pct": FIX["sector_breadth_pct"], "sectors_above_200d_pct": 54.5}
    out = brief._morning_read(overview, {}, {}, {}, index_regime={"score": 0})
    sent = json.loads(claude.asked[0]["messages"][0]["content"].split("DATA:\n", 1)[1])
    assert sent["session_covered"]["words"] == "today" and sent["session_covered"]["date"] == "2026-10-26"
    assert sent["sectors_up_today_pct"] == FIX["sector_breadth_pct"] and sent["sectors_above_200d_pct"] == 54.5
    assert "sector_breadth_pct" not in sent, "the ambiguous name is gone from what the writer reads"
    assert "session_covered" in claude.asked[0]["system"][0]["text"]
    assert out["covers_session"] == "2026-10-26" and out["covers_words"] == "Monday, October 26"
    assert out["figures_as_of"] and out["figure_check"]["checked"] >= 0


def test_the_page_says_what_the_text_covers_and_what_did_not_match():
    src = (ROOT / "static/v2/js/pages/read.js").read_text()
    assert "The text covers the session of ${s.covers_words}." in src
    assert "(s.figure_check || {}).unmatched" in src


def test_a_figure_inside_a_releases_text_counts():
    out = brief.check_figures(["CPI rose **0.6%** in September."],
                              {"official_releases": [{"summary": "The CPI rose 0.6 percent in September."}]})
    assert out["unmatched"] == []


def test_a_morning_edition_written_after_the_open_covers_today_so_far():
    """Found in review, 2026-10-27: a retried morning write at 11 AM has today's forming bar."""
    from datetime import datetime, timezone
    early = brief.covered_session("2026-10-27:morning", datetime(2026, 10, 27, 13, 0, tzinfo=timezone.utc))
    late = brief.covered_session("2026-10-27:morning", datetime(2026, 10, 27, 15, 0, tzinfo=timezone.utc))
    assert (early["date"], early["words"]) == ("2026-10-26", "yesterday")
    assert (late["date"], late["words"]) == ("2026-10-27", "today so far")
