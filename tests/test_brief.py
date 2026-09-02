"""Daily brief: feed parsing, filing classification, section assembly, archive.

No test here touches the network. The feed layer is exercised against fixture
documents and the section builders against monkeypatched loaders, so the suite
stays deterministic and runs offline — a test that depends on what the BBC
published this morning is not a test.
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest

from app import brief, events, feeds


# --------------------------------------------------------------- feed parsing

RSS_DOC = b"""<?xml version="1.0"?>
<rss version="2.0"><channel>
  <title>Example wire</title>
  <item>
    <title>Oil tankers threatened in the Gulf</title>
    <link>https://example.com/a</link>
    <description>&lt;p&gt;Shipping rates &amp;amp; insurance jump.&lt;/p&gt;</description>
    <pubDate>Mon, 03 Aug 2026 11:30:00 GMT</pubDate>
  </item>
  <item>
    <title>Second story</title>
    <link>https://example.com/b</link>
    <pubDate>Mon, 03 Aug 2026 09:00:00 GMT</pubDate>
  </item>
</channel></rss>"""

# The BLS serves Atom, not RSS. An earlier version of the parser only looked for
# <item> and silently returned zero rows for every statistical agency — the
# section rendered empty and looked like a dead feed rather than a parser bug.
ATOM_DOC = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <id>bls.gov:feed:cpi</id>
  <title>Consumer Price Index</title>
  <entry>
    <title>CPI for all items falls 0.4% in June</title>
    <link rel="alternate" href="https://www.bls.gov/news.release/cpi.htm"/>
    <updated>2026-07-15T08:30:00Z</updated>
    <summary>Gasoline down.</summary>
  </entry>
</feed>"""


def test_parse_feed_reads_rss():
    rows = feeds.parse_feed(RSS_DOC)
    assert len(rows) == 2
    assert rows[0]["title"] == "Oil tankers threatened in the Gulf"
    assert rows[0]["url"] == "https://example.com/a"
    # Tags stripped, entities decoded, whitespace collapsed.
    assert rows[0]["summary"] == "Shipping rates & insurance jump."
    assert rows[0]["published"].tzinfo is not None


def test_parse_feed_reads_atom():
    """The regression that mattered: Atom must not silently yield nothing."""
    rows = feeds.parse_feed(ATOM_DOC)
    assert len(rows) == 1
    assert rows[0]["title"].startswith("CPI for all items falls")
    assert rows[0]["url"].endswith("cpi.htm")
    assert rows[0]["published"].year == 2026


def test_parse_feed_ignores_unknown_dialect():
    assert feeds.parse_feed(b"<html><body>not a feed</body></html>") == []


def test_parse_date_handles_both_conventions():
    rfc = feeds._parse_date("Mon, 03 Aug 2026 11:30:00 GMT")
    iso = feeds._parse_date("2026-08-03T11:30:00Z")
    assert rfc is not None and iso is not None
    assert rfc.tzinfo is not None and iso.tzinfo is not None
    assert feeds._parse_date("") is None
    assert feeds._parse_date("nonsense") is None


def test_dedupe_keeps_distinct_but_similar_titles():
    """Two Fed releases can share a long prefix and still be different news."""
    rows = [
        {"title": "Federal Reserve Board requests comment on a proposal to modernize its rule "
                  "governing the extension of credit to bank insiders"},
        {"title": "Federal Reserve Board requests comment on a proposal to modernize rules for "
                  "mutual banking organizations"},
        {"title": "Federal Reserve Board requests comment on a proposal to modernize rules for "
                  "mutual banking organizations"},
    ]
    out = feeds.dedupe(rows)
    assert len(out) == 2


def test_within_hours_keeps_undated_entries():
    now = datetime.now(timezone.utc)
    rows = [
        {"title": "fresh", "published": now.isoformat()},
        {"title": "old", "published": (now - timedelta(hours=200)).isoformat()},
        {"title": "undated", "published": None},
    ]
    kept = {r["title"] for r in feeds.within_hours(rows, 48)}
    assert kept == {"fresh", "undated"}


# ---------------------------------------------------------- filing classifier

def _hit(names, items, adsh="0000320193-26-000012", cik="0000320193"):
    return {"_source": {"display_names": names, "items": items,
                        "adsh": adsh, "ciks": [cik], "file_date": "2026-08-03"}}


def test_filing_row_extracts_ticker_and_builds_index_url():
    row = feeds._filing_row(_hit(["APPLE INC  (AAPL)  (CIK 0000320193)"], ["2.02", "9.01"]))
    assert row["ticker"] == "AAPL"
    assert row["company"] == "APPLE INC"
    # The measured-good URL shape: unpadded CIK, accession without dashes as the
    # directory, accession with dashes in the filename.
    assert row["url"] == ("https://www.sec.gov/Archives/edgar/data/320193/"
                          "000032019326000012/0000320193-26-000012-index.htm")
    assert "2.02" in row["items"] and "9.01" not in row["items"]
    assert row["groups"] == ["earnings"]


def test_filing_row_drops_exhibit_only_filings():
    """Item 9.01 alone is the exhibit index — paperwork, not news. It appeared on
    82 of 126 filings in one measured day, so admitting it would swamp the tab."""
    assert feeds._filing_row(_hit(["SOME CO  (CIK 0000000001)"], ["9.01"])) is None


def test_filing_row_handles_missing_ticker():
    row = feeds._filing_row(_hit(["Fundrise eREIT, LLC  (CIK 0002093809)"], ["8.01"]))
    assert row is not None
    assert row["ticker"] is None
    assert row["company"] == "Fundrise eREIT, LLC"


def test_filing_row_weight_takes_the_most_serious_item():
    row = feeds._filing_row(_hit(["ECHOSTAR CORP  (ECHO)  (CIK 0001001082)"],
                                 ["1.03", "2.04", "5.02", "9.01"]))
    # Bankruptcy dominates a management change in the same filing.
    assert row["weight"] == feeds.ITEM_LABELS["1.03"][1]
    assert set(row["groups"]) == {"distress", "management"}


def test_every_item_group_maps_to_a_known_label():
    for code in feeds.ITEM_GROUPS:
        assert code in feeds.ITEM_LABELS
    for group in feeds.ITEM_GROUPS.values():
        assert group in brief.GROUP_LABELS


def test_filing_row_survives_a_hit_with_no_names():
    assert feeds._filing_row({"_source": {"items": ["2.02"]}}) is None


# ------------------------------------------------------------------- sections

def test_classify_whitelist_drops_company_only_catalysts():
    """A GDP release came out tagged 'product news' because the company taxonomy
    matches the word 'announces'. A wrong label reads as a claim, so the
    non-company sections keep only categories about events bigger than a filer."""
    entry = {"title": "GDP (Advance Estimate), 2nd Quarter 2026", "summary": ""}
    unrestricted = brief._classify(entry)
    restricted = brief._classify(entry, brief.NON_COMPANY_CATALYSTS)
    assert all(c["type"] in brief.NON_COMPANY_CATALYSTS for c in restricted["catalysts"])
    # And the whitelist is doing something: the raw pass tagged it.
    assert len(restricted["catalysts"]) <= len(unrestricted["catalysts"])


def test_classify_reports_tone_without_publishing_a_score():
    good = brief._classify({"title": "Company beats and raises guidance", "summary": ""})
    bad = brief._classify({"title": "Company misses, warns on demand", "summary": ""})
    assert good["tone_label"] == "positive"
    assert bad["tone_label"] == "negative"
    assert brief._classify({"title": "Committee meeting scheduled"})["tone_label"] == "neutral"


def test_macro_section_backfills_a_quiet_week(monkeypatch):
    """Measured live: 2 releases inside a 96-hour window out of 143 available. An
    empty macro panel reads as a broken feed, so the section is topped up."""
    now = datetime.now(timezone.utc)
    entries = [{"title": f"Release {i}", "url": f"https://example.gov/{i}",
                "summary": "", "source": "Federal Reserve", "source_detail": "",
                "published": (now - timedelta(hours=i * 30)).isoformat()}
               for i in range(12)]
    monkeypatch.setattr(feeds, "load_kind", lambda kind, force=False: (entries, []))
    section = brief._macro_section()
    assert section["in_window"] < brief.MACRO_FLOOR
    assert len(section["entries"]) >= brief.MACRO_FLOOR
    assert section["backfilled"] == len(section["entries"]) - section["in_window"]


def test_macro_section_does_not_backfill_a_busy_week(monkeypatch):
    now = datetime.now(timezone.utc)
    entries = [{"title": f"Release {i}", "url": f"https://example.gov/{i}", "summary": "",
                "source": "BLS", "source_detail": "",
                "published": (now - timedelta(hours=i)).isoformat()} for i in range(10)]
    monkeypatch.setattr(feeds, "load_kind", lambda kind, force=False: (entries, []))
    section = brief._macro_section()
    assert section["backfilled"] == 0

def test_overview_survives_a_provider_failure():
    class Broken:
        def batch_history(self, *a, **k):
            raise RuntimeError("feed refused")

    out = brief._overview(Broken())
    assert "feed refused" in out["error"]
    # Every row is still present, just unpriced — the table renders with dashes
    # rather than the section vanishing.
    assert len(out["groups"]["mag7"]) == len(brief.MAG7)
    assert all(r["day"] is None for r in out["groups"]["mag7"])
    assert out["leaders"] == []


# -------------------------------------------------------------------- archive

@pytest.fixture()
def temp_db(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "brief.db")
        monkeypatch.setattr(brief, "DB_PATH", path)
        brief._MEM.clear()
        yield path
        brief._MEM.clear()


def test_save_and_load_round_trip(temp_db):
    brief._save("2026-08-03", {"day": "2026-08-03", "overview": {"note": "x"}})
    assert brief._load("2026-08-03")["overview"]["note"] == "x"
    assert brief._load("2026-08-02") is None


def test_repeated_builds_upsert_one_row_per_day(temp_db):
    brief._save("2026-08-03", {"v": 1})
    brief._save("2026-08-03", {"v": 2})
    rows = brief.archive()
    assert len(rows) == 1
    assert rows[0]["builds"] == 2
    assert brief._load("2026-08-03")["v"] == 2


def test_state_for_a_missing_past_day_does_not_rebuild(temp_db):
    """An archived day must report the gap rather than quietly serving today's
    feeds under an old date."""
    class Exploding:
        def batch_history(self, *a, **k):
            raise AssertionError("must not build for a historical request")

    out = brief.state(Exploding(), day="2020-01-01")
    assert out["missing"] is True
    assert "No brief" in out["reason"]


def test_state_serves_a_stored_past_day(temp_db):
    brief._save("2026-08-01", {"day": "2026-08-01", "macro": {"entries": []}})

    class Exploding:
        def batch_history(self, *a, **k):
            raise AssertionError("must not rebuild an archived day")

    out = brief.state(Exploding(), day="2026-08-01")
    assert out["historical"] is True
    assert out["day"] == "2026-08-01"


def test_today_key_uses_eastern_time():
    """A brief built at 00:30 UTC belongs to the previous Eastern day, which is
    the calendar the rest of the app already reports in."""
    late = datetime(2026, 8, 4, 0, 30, tzinfo=timezone.utc)
    assert brief.today_key(late) == "2026-08-03"


def test_user_agent_declares_a_contact_when_configured(monkeypatch):
    """SEC /Archives returns 403 for a User-Agent with no contact address, so the
    brief surfaces whether one is configured instead of failing opaquely."""
    assert feeds.CONTACT_OK == ("@" in feeds.CONTACT)
    if feeds.CONTACT_OK:
        assert feeds.CONTACT in feeds.USER_AGENT


# ------------------------------------------------------------------ narrative

def _ov(spy=None, qqq=None, iwm=None, vix=None, vix_last=None, mag7=None,
        sectors=None, themes=None, breadth=None):
    def rows(spec):
        return [{"symbol": s, "name": n, "day": d, "week": None, "month": None, "last": None}
                for s, n, d in (spec or [])]
    idx = []
    if spy is not None:
        idx.append({"symbol": "SPY", "name": "S&P 500", "day": spy, "last": 700})
    if qqq is not None:
        idx.append({"symbol": "QQQ", "name": "Nasdaq 100", "day": qqq, "last": 600})
    if iwm is not None:
        idx.append({"symbol": "IWM", "name": "Russell 2000", "day": iwm, "last": 290})
    if vix is not None:
        idx.append({"symbol": "^VIX", "name": "VIX", "day": vix, "last": vix_last or 16.0})
    return {"groups": {"indices": idx, "mag7": rows(mag7),
                       "sectors": rows(sectors), "themes": rows(themes)},
            "sector_breadth_pct": breadth, "note": ""}


def test_narrative_describes_the_tape_and_breadth():
    out = brief._narrative(_ov(spy=1.53, qqq=1.88, breadth=63.6))
    text = " ".join(out["paragraphs"])
    assert "S&P 500" in text and "+1.5%" in text
    assert "64%" in text
    assert out["paragraphs"]


def test_narrative_never_lowercases_vix():
    """`.capitalize()` produced 'the vix' — it lowercases everything after the
    first character."""
    out = brief._narrative(_ov(spy=1.0, vix=-1.4, vix_last=15.8))
    text = " ".join(out["paragraphs"])
    assert "VIX" in text
    assert "vix" not in text


def test_narrative_does_not_stack_two_with_clauses():
    out = brief._narrative(_ov(spy=1.5, qqq=1.8, breadth=64))
    tape = out["paragraphs"][0]
    assert tape.count(", with") <= 1


def test_narrative_calls_a_flat_tape_flat():
    out = brief._narrative(_ov(spy=0.04, breadth=50))
    assert "little changed" in " ".join(out["paragraphs"])
    assert "flat" in out["headline"].lower()


def test_narrative_notes_megacap_dispersion():
    out = brief._narrative(_ov(spy=1.5, mag7=[
        ("META", "Meta", 6.5), ("AAPL", "Apple", -1.0), ("MSFT", "Microsoft", 5.3),
    ]))
    text = " ".join(out["paragraphs"])
    assert "Meta" in text and "Apple" in text
    assert "spread" in text          # 7.5 points apart is dispersion, not a trend


def test_narrative_says_all_higher_when_they_all_are():
    out = brief._narrative(_ov(spy=1.0, mag7=[
        ("A", "Alpha", 1.1), ("B", "Beta", 1.2), ("C", "Gamma", 0.9),
    ]))
    assert "all seven finished higher" in " ".join(out["paragraphs"]) or \
           "higher" in " ".join(out["paragraphs"])


def test_narrative_reports_leaders_and_laggards():
    out = brief._narrative(_ov(spy=0.5,
        sectors=[("XLE", "Energy", -1.7), ("XLK", "Technology", 1.8), ("XLU", "Utilities", -0.4)],
        themes=[("JETS", "Airlines", 4.2)]))
    text = " ".join(out["paragraphs"])
    assert "Airlines" in text and "Energy" in text

def test_narrative_is_deterministic():
    args = (_ov(spy=1.2, qqq=1.4, vix=-2.0, breadth=70,
                mag7=[("A", "Alpha", 2.0), ("B", "Beta", 0.5)]),)
    assert brief._narrative(*args) == brief._narrative(*args)


def test_narrative_survives_a_total_data_failure():
    out = brief._narrative({"groups": {}, "sector_breadth_pct": None})
    assert out["paragraphs"] == []
    assert "unavailable" in out["headline"].lower()


def test_narrative_never_claims_causation():
    """It has no causal information, so it must not offer a reason."""
    out = brief._narrative(_ov(spy=1.5, qqq=1.9, vix=-3.0, breadth=80,
                               mag7=[("A", "Alpha", 3.0), ("B", "Beta", 1.0)],
                               sectors=[("XLK", "Technology", 2.0)]))
    blob = (" ".join(out["paragraphs"]) + " " + out["headline"]).lower()
    for word in (" because ", " due to ", " driven by ", " on hopes", " on fears", " after "):
        assert word not in blob


# --------------------------------------------------------------- desks / sectors

def test_no_cnn_sources_in_the_table():
    """CNN's public RSS is abandoned — measured 2026-08-04, the freshest item in
    edition_world was 2.9 years old and two other feeds ~9.5 years. They cost
    four requests a cycle and every item fell outside the freshness window."""
    assert not [s for s in feeds.SOURCES if "cnn" in s["id"]]


def test_every_wire_source_has_a_known_sector():
    """A source with a typo'd sector would vanish from the page silently."""
    for src in feeds.SOURCES:
        if src["kind"] == "wire":
            assert src.get("sector") in feeds.SECTOR_ORDER, src["id"]


def test_every_sector_has_at_least_one_source():
    covered = {s.get("sector") for s in feeds.SOURCES if s["kind"] == "wire"}
    assert covered == set(feeds.SECTOR_ORDER)


def test_load_kind_can_narrow_to_one_sector(monkeypatch):
    def fake(source, force=False):
        return {"entries": [{"title": f"from {source['id']}", "url": "u",
                             "summary": "", "published": None,
                             "source": source["name"], "source_detail": "",
                             "source_id": source["id"]}], "error": None}
    monkeypatch.setattr(feeds, "load_source", fake)
    entries, status = feeds.load_kind("wire", sector="tech")
    assert entries and all(e["sector"] == "tech" for e in entries)
    assert {s["id"] for s in status} == {
        s["id"] for s in feeds.SOURCES if s.get("sector") == "tech"}


# ------------------------------------------------------------------- ics parsing

def test_parse_ics_unfolds_continuation_lines():
    """RFC 5545 folds long lines with a leading space. Reading fields before
    unfolding truncates the summary at the fold."""
    ics = ("BEGIN:VEVENT\r\nDTSTART:20260812T083000\r\n"
           "SUMMARY:Consumer Price\r\n  Index\r\nEND:VEVENT\r\n")
    events = feeds.parse_ics(ics)
    assert len(events) == 1
    assert events[0]["summary"] == "Consumer Price Index"
    assert events[0]["start"].hour == 8 and events[0]["start"].minute == 30


def test_parse_ics_marks_all_day_events():
    ics = "BEGIN:VEVENT\nDTSTART;VALUE=DATE:20260812\nSUMMARY:Something\nEND:VEVENT"
    assert feeds.parse_ics(ics)[0]["all_day"] is True


def test_parse_ics_skips_events_missing_a_date():
    assert feeds.parse_ics("BEGIN:VEVENT\nSUMMARY:No date\nEND:VEVENT") == []


# -------------------------------------------------------------- fomc scraping

def _fomc_html(year, month, days):
    return (f'<h4><a href="#">{year} FOMC Meetings</a></h4>'
            f'<div class="row fomc-meeting">'
            f'<div class="fomc-meeting__month col-md-2"><strong>{month}</strong></div>'
            f'<div class="fomc-meeting__date col-lg-1">{days}</div></div>')


def test_fomc_parser_takes_the_final_day_of_a_meeting(monkeypatch):
    """The statement lands on day two, which is the date that matters."""
    monkeypatch.setattr(feeds, "load_html",
                        lambda *a, **k: {"text": _fomc_html(2026, "January", "27-28")})
    rows = events._fomc_events()["events"]
    assert len(rows) == 1
    assert rows[0]["at"].startswith("2026-01-28T14:00")


def test_fomc_parser_ignores_the_projections_asterisk(monkeypatch):
    monkeypatch.setattr(feeds, "load_html",
                        lambda *a, **k: {"text": _fomc_html(2026, "March", "17-18*")})
    assert events._fomc_events()["events"][0]["at"].startswith("2026-03-18")


def test_fomc_parser_rolls_a_range_over_a_month_end(monkeypatch):
    monkeypatch.setattr(feeds, "load_html",
                        lambda *a, **k: {"text": _fomc_html(2026, "April", "30-1")})
    assert events._fomc_events()["events"][0]["at"].startswith("2026-05-01")


def test_fomc_parser_does_not_scrape_prose_dates(monkeypatch):
    """The first version matched "Month DD, YYYY" anywhere and picked up archive
    links and "(Released February 18, 2026)" minutes notes — 46 dates spanning
    2021-2028 with one in the future."""
    html = (_fomc_html(2026, "January", "27-28")
            + "<div>(Released February 18, 2026)</div>"
            + '<a href="/x">December 15, 2021</a>')
    monkeypatch.setattr(feeds, "load_html", lambda *a, **k: {"text": html})
    rows = events._fomc_events()["events"]
    assert [r["at"][:10] for r in rows] == ["2026-01-28"]


def test_fomc_parser_reports_failure_rather_than_guessing(monkeypatch):
    monkeypatch.setattr(feeds, "load_html", lambda *a, **k: {"text": "<p>nothing</p>"})
    out = events._fomc_events()
    assert out["events"] == [] and out["error"]


# ------------------------------------------------------------------ cot rule

def test_cot_events_land_on_friday_afternoons():
    from datetime import datetime
    out = events._cot_events(datetime(2026, 8, 4, 9, 0, tzinfo=events.ET))
    assert len(out["events"]) == 3
    for row in out["events"]:
        when = datetime.fromisoformat(row["at"])
        assert when.weekday() == 4          # Friday
        assert (when.hour, when.minute) == (15, 30)


def test_cot_events_are_labelled_as_derived_not_published():
    """The CFTC publishes no machine-readable schedule, so these are a rule."""
    from datetime import datetime
    out = events._cot_events(datetime(2026, 8, 4, 9, 0, tzinfo=events.ET))
    assert all(r["confidence"] == "recurring" for r in out["events"])


# --------------------------------------------------------------------- search

def _wire(title, summary=""):
    return {"title": title, "url": "u", "summary": summary, "published": None,
            "source": "X", "source_detail": "", "source_id": "x", "sector": "markets"}


def test_search_requires_every_term_to_match(monkeypatch):
    rows = [_wire("Oil prices fall in the Strait of Hormuz"),
            _wire("Oil prices rise on demand")]
    monkeypatch.setattr(feeds, "load_kind", lambda kind, force=False: (rows, []))
    assert feeds.search("oil hormuz")["matched"] == 1
    assert feeds.search("oil")["matched"] == 2


def test_search_ranks_title_hits_above_summary_hits(monkeypatch):
    rows = [_wire("Unrelated headline", "a note about inflation"),
            _wire("Inflation cools in June")]
    monkeypatch.setattr(feeds, "load_kind", lambda kind, force=False: (rows, []))
    results = feeds.search("inflation")["results"]
    assert results[0]["title"].startswith("Inflation")


def test_search_on_empty_query_returns_nothing(monkeypatch):
    monkeypatch.setattr(feeds, "load_kind", lambda kind, force=False: ([_wire("x")], []))
    out = feeds.search("   ")
    assert out["results"] == [] and out["searched"] == 0


def test_search_reports_the_corpus_it_searched(monkeypatch):
    """The UI promises a search of loaded headlines, not the web — so the size of
    the corpus has to be reportable."""
    rows = [_wire("alpha"), _wire("beta")]
    monkeypatch.setattr(feeds, "load_kind", lambda kind, force=False: (rows, []))
    out = feeds.search("alpha")
    assert out["searched"] == 2 and out["matched"] == 1
