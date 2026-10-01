"""The House disclosures, read to the end of the year.

Asked with a screenshot of "No House trades in BE": "nancy pelosi bought BE
at $160, does that not count?" It does, and her filing of August 21 lists
spouse purchases of BE stock and call options on July 24 and 28. It had not
been read. The backlog was filled only by readers, one batch of 25 per visit at
most every six hours, newest first, and the year was 113 of 403 filings in.
Her June and January filings had not been fetched at all.

The server reads the backlog itself now, a batch at a time with a pause
between, and a reader's request downloads nothing. Each filing is parsed once
and the rows kept beside the PDF, where every refresh used to parse every
filing on disk again, 23 to 114ms apiece.

Nothing here touches the network: the Clerk's index and files are fakes.
"""
from __future__ import annotations

import asyncio
import json
import os
import threading

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.analytics import congress


class _Resp:
    def __init__(self, status=200, content=b"%PDF-1.4 fake"):
        self.status_code, self.content = status, content


class _Clerk:
    """The Clerk's file server: every filing is a PDF unless told otherwise."""
    def __init__(self, broken=()):
        self.asked, self.broken = [], set(broken)

    def get(self, url, timeout=None):
        doc = url.rsplit("/", 1)[-1][:-len(".pdf")]
        self.asked.append(doc)
        return _Resp(404, b"") if doc in self.broken else _Resp()


def _index(n):
    """n filings, doc 1 filed first and doc n last."""
    return [{"doc_id": str(i), "last": "Member%d" % i, "first": "A", "prefix": "Hon.",
             "filed": "%02d/%02d/2026" % (1 + i // 28, 1 + i % 28), "district": "CA11",
             "year": "2026"} for i in range(1, n + 1)]


@pytest.fixture
def clerk(monkeypatch, tmp_path):
    server = _Clerk()
    parses = []

    def parse(path):
        parses.append(os.path.basename(path))
        return {"member": None, "district": None, "error": None,
                "rows": [{"ticker": "BE", "asset_kind": "ST", "transaction": "purchase",
                          "side": "buy", "traded": "07/24/2026", "notified": "07/24/2026",
                          "amount_low": 1000001, "amount_high": 5000000}]}
    monkeypatch.setattr(congress, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(congress, "REQUEST_GAP", 0)
    monkeypatch.setattr(congress, "_session", lambda: server)
    monkeypatch.setattr(congress, "_fetch_index", lambda year, sess: _index(server.n))
    monkeypatch.setattr(congress, "_parse_pdf", parse)
    monkeypatch.setattr(congress, "_PARSED", {})
    monkeypatch.setattr(congress, "_FAILED", {})
    monkeypatch.setattr(congress, "_MEM", {"at": 0.0, "trades": [], "index_at": None,
                                           "parsed": 0, "known": 0, "backlog": 0})
    server.n, server.parses, server.dir = 60, parses, tmp_path
    return server


def test_a_batch_is_the_newest_filings_and_the_rest_is_the_backlog(clerk):
    out = congress.refresh(2026, 25)
    assert clerk.asked == [str(i) for i in range(60, 35, -1)], "newest filed first"
    assert out["filings_parsed"] == 25 and out["filings_known"] == 60
    assert congress.backlog() == 35
    congress.refresh(2026, 25)
    congress.refresh(2026, 25)
    assert congress.backlog() == 0 and congress.summary()["complete"] is True


def test_a_readers_request_downloads_nothing(clerk, monkeypatch):
    congress.refresh(2026, 10)
    clerk.asked.clear()
    out = congress.refresh(2026, 0)
    assert clerk.asked == [] and out["filings_parsed"] == 10
    # And the endpoint asks for exactly that while the server backfills.
    seen = []
    monkeypatch.setattr(main.congress_mod, "stale", lambda: True)
    monkeypatch.setattr(main.congress_mod, "refresh",
                        lambda year=None, budget=None: seen.append(budget) or {})
    TestClient(main.app).get("/api/congress", params={"ticker": "BE"})
    assert seen == [0]


def test_each_filing_is_parsed_once_and_kept_beside_it(clerk, monkeypatch):
    congress.refresh(2026, 5)
    congress.refresh(2026, 0)
    assert sorted(clerk.parses) == sorted("%d.pdf" % i for i in range(56, 61))
    stored = json.loads((clerk.dir / "2026" / "60.json").read_text())
    assert stored["v"] == congress.PARSE_VERSION and stored["out"]["rows"][0]["ticker"] == "BE"
    # A restart reads the rows back instead of parsing again.
    monkeypatch.setattr(congress, "_PARSED", {})
    clerk.parses.clear()
    out = congress.refresh(2026, 0)
    assert clerk.parses == [] and out["filings_parsed"] == 5 and out["count"] == 5


def test_a_parse_from_another_version_of_the_parser_is_read_again(clerk, monkeypatch):
    congress.refresh(2026, 1)
    side = clerk.dir / "2026" / "60.json"
    side.write_text(json.dumps({"v": congress.PARSE_VERSION - 1, "out": {"rows": []}}))
    monkeypatch.setattr(congress, "_PARSED", {})
    clerk.parses.clear()
    congress.refresh(2026, 0)
    assert clerk.parses == ["60.pdf"]


def test_a_failed_parse_is_not_kept_on_disk(clerk, monkeypatch):
    monkeypatch.setattr(congress, "_parse_pdf",
                        lambda path: {"member": None, "district": None, "rows": [],
                                      "error": "pypdf not installed"})
    congress.refresh(2026, 1)
    assert not (clerk.dir / "2026" / "60.json").exists()


def test_a_filing_that_will_not_download_does_not_hold_the_backlog_open(clerk):
    clerk.n = 3
    clerk.broken = {"3"}
    congress.refresh(2026, 25)
    assert congress.backlog() == 0, "only the broken one is left, and it waits"
    clerk.asked.clear()
    congress.refresh(2026, 25)
    assert clerk.asked == [], "not asked for again before RETRY_AFTER"


def test_one_refresh_at_a_time(clerk):
    congress.refresh(2026, 3)
    clerk.asked.clear()
    assert congress._REFRESHING.acquire(blocking=False)
    try:
        out = congress.refresh(2026, 25)
    finally:
        congress._REFRESHING.release()
    assert clerk.asked == [] and out["filings_parsed"] == 3, "what is read so far"


# ------------------------------------------------------------------ the loop


def test_the_server_reads_batch_after_batch_until_nothing_is_left(monkeypatch):
    sleeps, left = [], [40, 15, 0]

    async def sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) > 4:
            raise asyncio.CancelledError

    def refresh():
        left.append(left.pop(0))      # the backlog after each batch
        return {"available": True}
    monkeypatch.setattr(main.asyncio, "sleep", sleep)
    monkeypatch.setattr(main.congress_mod, "refresh", refresh)
    monkeypatch.setattr(main.congress_mod, "backlog", lambda: left[-1])
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(main._congress_loop())
    assert sleeps[0] == main.CONGRESS_BOOT_DELAY
    assert sleeps[1:4] == [main.CONGRESS_BATCH_PAUSE, main.CONGRESS_BATCH_PAUSE,
                           congress.INDEX_TTL]


def test_the_loop_starts_with_the_server_and_can_be_switched_off():
    src = open("app/main.py", encoding="utf-8").read()
    start = src[src.index("async def _start_tracker() -> None:"):][:900]
    assert "if CONGRESS_BACKFILL:\n        app.state.congress_task = asyncio.create_task(_congress_loop())" in start
    assert 'CONGRESS_BACKFILL = os.environ.get("CONGRESS_BACKFILL", "true")' in src
