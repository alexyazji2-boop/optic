"""Whether a reader can actually open the link.

The read page is a page of links: this module stores headline, source and URL
and nothing else, by design, so the click is the whole product. A headline that
opens a subscription page is a dead control with a publisher's logo on it.

None of this touches the network. The source table is data, and the two ranking
functions are pure — the live measurements that justify each source's `access`
value are recorded in app/feeds.py above the table, not re-run here. A test that
fetches wsj.com would fail on their rate limiter, not on our bug.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app import brief, feeds

ROOT = Path(__file__).resolve().parent.parent
APP_JS = (ROOT / "static" / "app.js").read_text()
STYLES = (ROOT / "static" / "styles.css").read_text()


# ------------------------------------------------------------- the source table

def test_every_source_declares_an_access_level():
    """The whole point of the field. A source added without one would default to
    looking free, which is the exact wall this is here to stop."""
    missing = [s["id"] for s in feeds.SOURCES if "access" not in s]
    assert missing == [], f"sources with no access level: {missing}"


def test_every_access_level_is_one_of_the_three():
    bad = [(s["id"], s["access"]) for s in feeds.SOURCES
           if s["access"] not in feeds.ACCESS_LEVELS]
    assert bad == []


def test_the_paywalled_sources_are_still_in_the_table():
    """Ranked down, never removed. A subscriber wants them, and WSJ and the FT
    are frequently the best reporting on their desk."""
    paid = {s["id"] for s in feeds.SOURCES if s["access"] == feeds.ACCESS_PAID}
    assert "wsj-markets" in paid
    assert {"ft-home", "economist-fin", "statnews"} <= paid


def test_every_official_source_is_open():
    """A government or central-bank release is a public record. If one of these
    is ever marked paid it is a typo, not a policy change."""
    official = [s for s in feeds.SOURCES if s["kind"] == "macro"]
    assert official, "macro sources vanished"
    assert all(s["access"] == feeds.ACCESS_OPEN for s in official)


def test_every_desk_has_at_least_one_source_a_reader_can_open():
    """The contract that produced this whole change.

    Measured before it: the Analysis desk was six of six behind a subscription —
    FT, STAT and the Economist, with no free member at all — so ranking readable
    stories first had nothing to rank and every link on that desk was a wall.
    Ranking cannot fix a desk with no free source on it; only a source can.
    """
    for sector in feeds.SECTOR_ORDER:
        members = [s for s in feeds.SOURCES if s.get("sector") == sector]
        assert members, f"{sector} has no sources at all"
        openable = [s["id"] for s in members if feeds.is_reachable(s)]
        assert openable, f"every source on the {sector} desk is paywalled"


def test_a_rejected_candidate_is_never_silently_re_added():
    """REJECTED_SOURCES is the module's memory. A URL cannot be in both."""
    live = {s["url"] for s in feeds.SOURCES}
    assert not (live & set(feeds.REJECTED_SOURCES)), "a rejected feed is back in SOURCES"


# ---------------------------------------------------------------- is_reachable

@pytest.mark.parametrize("level,expected", [
    (feeds.ACCESS_OPEN, True),
    (feeds.ACCESS_METERED, True),
    (feeds.ACCESS_PAID, False),
])
def test_is_reachable_reads_the_level(level, expected):
    assert feeds.is_reachable({"access": level}) is expected


def test_an_untagged_entry_is_treated_as_paid():
    """Fail closed. Promoting an unknown source to the lead is the failure this
    field exists to prevent; demoting one costs it a slot."""
    assert feeds.is_reachable({}) is False
    assert feeds.is_reachable({"access": "nonsense"}) is False


# ------------------------------------------------------- propagation to the API

def _entry(idx, access, source_id, published):
    return {"title": f"story {idx}", "url": f"https://example.com/{idx}",
            "source": source_id, "source_id": source_id, "access": access,
            "published": published, "weight": 5}


def test_load_kind_puts_access_on_every_entry_and_status_row(monkeypatch):
    monkeypatch.setattr(feeds, "load_source", lambda src, force=False: {
        "entries": [{"title": "t", "url": "u", "published": "2026-09-09T10:00:00+00:00"}],
        "error": None})
    entries, status = feeds.load_kind("wire")
    assert entries and all("access" in e for e in entries)
    assert status and all("access" in s for s in status)


# ------------------------------------------------------------------ _spread

def test_paywalled_stories_cannot_take_more_than_their_reserve():
    """Eight fresh stories, the four newest all behind a wall. Straight recency
    would open the desk with four dead links."""
    rows = ([_entry(i, feeds.ACCESS_PAID, f"paid{i}", f"2026-09-09T1{9 - i}:00:00+00:00")
             for i in range(4)]
            + [_entry(10 + i, feeds.ACCESS_OPEN, f"free{i}", f"2026-09-09T1{5 - i}:00:00+00:00")
               for i in range(4)])
    out = brief._spread(rows)
    assert len(out) == brief.DESK_LIMIT
    paid = [r for r in out if r["access"] == feeds.ACCESS_PAID]
    assert len(paid) == brief.PAID_DESK_SLOTS


def test_the_reserve_is_not_a_quota():
    """Nothing behind a wall: the desk is six free stories, not four and a gap."""
    rows = [_entry(i, feeds.ACCESS_OPEN, f"free{i}", f"2026-09-09T{20 - i}:00:00+00:00")
            for i in range(9)]
    out = brief._spread(rows)
    assert len(out) == brief.DESK_LIMIT
    assert all(r["access"] == feeds.ACCESS_OPEN for r in out)


def test_a_desk_with_only_paywalled_stories_is_still_filled():
    """Better a desk of walls, labelled, than a desk of one story. The label is
    the honest part; an empty desk reads as a broken feed."""
    rows = [_entry(i, feeds.ACCESS_PAID, f"paid{i % 3}", f"2026-09-09T{20 - i}:00:00+00:00")
            for i in range(9)]
    out = brief._spread(rows)
    assert len(out) == brief.DESK_LIMIT


def test_the_desk_reads_free_first_then_newest():
    """One comparator for every desk: readable first, then newest.

    On seven of the eight desks this is indistinguishable from plain recency,
    because they carry no paywalled source. It only bites on Analysis, where the
    four newest stories are all behind a subscription and no free feed exists at
    wire volume to displace them — twelve were probed; see REJECTED_SOURCES.
    """
    rows = ([_entry(i, feeds.ACCESS_PAID, f"paid{i}", f"2026-09-09T1{9 - i}:00:00+00:00")
             for i in range(4)]
            + [_entry(10 + i, feeds.ACCESS_OPEN, f"free{i}", f"2026-09-09T1{5 - i}:00:00+00:00")
               for i in range(4)])
    out = brief._spread(rows)
    levels = [r["access"] for r in out]
    assert levels == sorted(levels, key=lambda a: a != feeds.ACCESS_OPEN), \
        "a paywalled story is sitting above one the reader can open"
    for level in (feeds.ACCESS_OPEN, feeds.ACCESS_PAID):
        stamps = [r["published"] for r in out if r["access"] == level]
        assert stamps == sorted(stamps, reverse=True), f"{level} block is out of order"


def test_a_desk_with_nothing_paywalled_is_plain_recency():
    """The comparator has to be a no-op on the seven desks that carry no walls,
    or it is a sort-order change dressed up as an accessibility fix."""
    rows = [_entry(i, feeds.ACCESS_OPEN, f"free{i}", f"2026-09-09T{20 - i}:00:00+00:00")
            for i in range(9)]
    out = brief._spread(rows)
    stamps = [r["published"] for r in out]
    assert stamps == sorted(stamps, reverse=True)


def test_the_half_a_desk_cap_per_source_still_holds():
    """The rule this function was written for, and the one most at risk from a
    rewrite: WSJ Opinion once took all six slots of the Analysis desk."""
    rows = ([_entry(i, feeds.ACCESS_OPEN, "loud", f"2026-09-09T{20 - i}:00:00+00:00")
             for i in range(8)]
            + [_entry(20 + i, feeds.ACCESS_OPEN, f"quiet{i}", f"2026-09-09T0{7 - i}:00:00+00:00")
               for i in range(4)])
    out = brief._spread(rows)
    assert sum(1 for r in out if r["source_id"] == "loud") <= brief.DESK_LIMIT // 2


def test_a_short_desk_is_returned_untouched():
    rows = [_entry(i, feeds.ACCESS_PAID, f"p{i}", f"2026-09-09T0{i}:00:00+00:00")
            for i in range(3)]
    assert brief._spread(rows) == rows


# --------------------------------------------------------------------- the lead

def test_the_lead_skips_a_newer_paywalled_story():
    """The lead gets a headline three times the size of anything else on the
    page. A subscription wall there is the first thing a reader meets."""
    fresh = [_entry(0, feeds.ACCESS_PAID, "wsj-markets", "2026-09-09T20:00:00+00:00"),
             _entry(1, feeds.ACCESS_OPEN, "bbc-world", "2026-09-09T19:00:00+00:00")]
    pool = [r for r in fresh if feeds.is_reachable(r)] or fresh
    lead = max(pool, key=lambda r: ((r.get("published") or ""), r.get("weight", 0)))
    assert lead["source_id"] == "bbc-world"


def test_the_lead_falls_back_to_a_paywalled_story_rather_than_none():
    fresh = [_entry(0, feeds.ACCESS_PAID, "wsj-markets", "2026-09-09T20:00:00+00:00")]
    pool = [r for r in fresh if feeds.is_reachable(r)] or fresh
    assert pool == fresh


def test_desks_prefers_a_reachable_lead(monkeypatch):
    """The real function, not a re-implementation of its key."""
    rows = [_entry(0, feeds.ACCESS_PAID, "wsj-markets", "2026-09-09T20:00:00+00:00"),
            _entry(1, feeds.ACCESS_OPEN, "bbc-world", "2026-09-09T19:00:00+00:00")]
    for r in rows:
        r["sector"] = "markets"
    monkeypatch.setattr(feeds, "load_kind", lambda kind, force=False, sector=None: (rows, []))
    monkeypatch.setattr(feeds, "within_hours", lambda entries, hours: entries)
    out = brief._desks()
    assert out["lead"]["source_id"] == "bbc-world"


# ------------------------------------------------------------------- the label

def test_the_card_says_so_before_the_click():
    assert "function briefAccess(" in APP_JS
    body = APP_JS.split("function briefAccess(", 1)[1].split("\nfunction ", 1)[0]
    assert "'paid'" in body, "the chip must key off the access level"
    assert "Subscription" in body


def test_only_paywalled_sources_get_a_chip():
    """Metered is deliberately unlabelled: six of the wire feeds are CNBC, and a
    chip on all of them is the noise that teaches people to ignore chips."""
    body = APP_JS.split("function briefAccess(", 1)[1].split("\nfunction ", 1)[0]
    assert "metered" not in body


def test_both_renderers_show_it():
    """The lead and the desk cards are separate functions with a duplicated meta
    line — adding it to one and not the other is the easy mistake here."""
    for fn in ("function briefHeadline(", "function briefLead("):
        body = APP_JS.split(fn, 1)[1].split("\nfunction ", 1)[0]
        assert "briefAccess(e)" in body, f"{fn} does not show the access chip"


def test_the_source_line_names_who_needs_a_subscription():
    body = APP_JS.split("function briefSourceLine(", 1)[1].split("\nfunction ", 1)[0]
    assert "'paid'" in body and "subscription" in body


def test_the_chip_is_styled():
    """A class with no rule renders at body size in the middle of a metadata
    line. This repo has shipped that twice."""
    assert re.search(r"^\.brief-paid\s*\{", STYLES, re.M)


def test_the_chip_text_clears_the_contrast_floor():
    """--t-micro is small text, so 4.5:1 applies. --ink-2 is 9.31:1 on the dark
    surface and 8.93:1 on the light one; --btn-primary, checked first, is 4.02:1
    and would have failed."""
    rule = STYLES.split(".brief-paid {", 1)[1].split("}", 1)[0]
    assert "var(--ink-2)" in rule
