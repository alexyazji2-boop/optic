"""The segment tables keep what they have read, and finish reading on their own.

The Financials tab's segment, product and geography tables are read out of
each filing's XBRL instance document, three a request, because each is about a
megabyte. The parses were kept in the shared feed cache, which holds sixty
entries for every feed in the app and was also holding the raw megabyte
documents, so they were evicted by ordinary traffic and lost on every deploy.
Measured on production: the panel sat at 3 of Intel's 13 filings visit after
visit, and half an hour after a deploy it was reading them from nothing again.

Now each parse is kept by accession in its own store (app/segment_store.py),
the raw documents are not kept at all, and the panel asks for the next batch
itself while the reader is on the page. The first group of tests drives
`segments.build` against a stubbed EDGAR; the last drives the panel's loader
under JavaScriptCore.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from app import feeds
from app import segment_store
from app.analytics import segments

ROOT = Path(__file__).resolve().parent.parent
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"

FILINGS = 13


@pytest.fixture
def edgar(tmp_path, monkeypatch):
    """Thirteen filings, a store and a shared cache of this test's own, and a
    count of every instance document read."""
    monkeypatch.setattr(segment_store, "DB_PATH", str(tmp_path / "segments.db"))
    monkeypatch.setattr(feeds, "CACHE_PATH", str(tmp_path / "feed_cache.json"))
    monkeypatch.setattr(feeds, "_MEM", {})
    monkeypatch.setattr(feeds, "_DISK", {})
    monkeypatch.setattr(segments, "_SHARED_CLEARED", False)
    rows = [{"accession": "0000050863-26-%06d" % k, "form": "10-Q",
             "period": None, "filed": None,
             "instance_url": "https://example.test/%d_htm.xml" % k}
            for k in range(FILINGS)]
    monkeypatch.setattr(segments, "filings", lambda ticker, force=False: {
        "available": True, "cik": "0000050863", "ticker": "INTC", "rows": rows})
    reads = []

    def parse(url):
        reads.append(url)
        k = int(url.rsplit("/", 1)[1].split("_", 1)[0])
        # One quarter each, so the table grows a column per filing read.
        month = 1 + (k % 12)
        return {"available": True, "facts": [{
            "metric": "revenue", "axis": "segment", "member": "Intel Foundry",
            "kind": "quarter", "end": "20%02d-%02d-28" % (14 + k // 12, month),
            "value": 1000.0 + k, "cross": 1}]}

    monkeypatch.setattr(segments, "parse_instance", parse)
    return reads


def _restart(monkeypatch):
    """A new process: nothing in memory. The shared cache file is still on disk."""
    monkeypatch.setattr(feeds, "_MEM", {})
    monkeypatch.setattr(feeds, "_DISK", {})
    monkeypatch.setattr(segments, "_SHARED_CLEARED", False)


# ------------------------------------------------------------- the defect


def test_a_restart_keeps_every_filing_already_read(edgar, monkeypatch):
    """The reported failure: the history never got longer, because each restart
    started it again. Five requests read all thirteen; after a restart the
    sixth reads none from EDGAR and still has all thirteen."""
    got = [segments.build("INTC") for _ in range(5)]
    assert [g["filings_read"] for g in got] == [3, 6, 9, 12, 13]
    assert got[-1]["filings_unread"] == 0
    assert len(edgar) == FILINGS
    _restart(monkeypatch)
    after = segments.build("INTC")
    assert after["filings_read"] == FILINGS and after["fetched_now"] == 0
    assert len(edgar) == FILINGS, "a restart sent the panel back to EDGAR"
    assert len(after["quarters"]) == FILINGS


def test_other_feeds_traffic_does_not_evict_what_was_read(edgar):
    """Sixty entries is what the shared cache keeps, and every feed in the app
    writes to it. A hundred unrelated stores between two visits is an ordinary
    morning."""
    for _ in range(5):
        segments.build("INTC")
    for k in range(100):
        feeds.store_json("other:%d" % k, {"n": k})
    again = segments.build("INTC")
    assert again["filings_read"] == FILINGS and again["fetched_now"] == 0


def test_the_raw_documents_are_not_kept_in_the_shared_cache(monkeypatch, tmp_path):
    """Each was a megabyte in a sixty-entry cache whose file is rewritten on
    every store. The parse is what is kept; the document is read once."""
    seen = {}

    def fetch_text(url, ttl, key=None, **kwargs):
        seen.update(kwargs, key=key)
        return "<xbrli:xbrl xmlns:xbrli='http://www.xbrl.org/2003/instance'/>"

    monkeypatch.setattr(feeds, "fetch_text", fetch_text)
    out = segments.parse_instance("https://example.test/0_htm.xml")
    assert out.get("available") is True
    assert seen.get("store") is False


def test_fetch_text_keeps_nothing_when_told_not_to(monkeypatch, tmp_path):
    monkeypatch.setattr(feeds, "CACHE_PATH", str(tmp_path / "feed_cache.json"))
    monkeypatch.setattr(feeds, "_MEM", {})
    monkeypatch.setattr(feeds, "_DISK", {})
    monkeypatch.setattr(feeds, "_fetch", lambda *a, **k: b"<doc/>")
    assert feeds.fetch_text("https://example.test/a", 60, key="seg:doc:a", store=False) == "<doc/>"
    assert "seg:doc:a" not in feeds._MEM
    assert not os.path.exists(feeds.CACHE_PATH)
    # And the default is unchanged for every other caller.
    feeds.fetch_text("https://example.test/b", 60, key="text:b")
    assert "text:b" in feeds._MEM


def test_documents_already_in_the_shared_cache_are_cleared_once(edgar):
    """The ones put there before this change, removed rather than left holding
    slots until they age out. Everything else in the cache stays."""
    feeds.store_json("seg:doc:https://example.test/old_htm.xml", {"t": "x" * 100})
    feeds.store_json("news:keep", {"rows": []})
    segments.build("INTC")
    disk = json.loads(Path(feeds.CACHE_PATH).read_text())
    assert not [k for k in disk if k.startswith("seg:doc:")]
    assert "news:keep" in disk
    assert "seg:doc:https://example.test/old_htm.xml" not in feeds._MEM


# ------------------------------------------------------------- the edges


def test_a_parse_already_in_the_shared_cache_is_moved_not_reread(edgar):
    first = "0000050863-26-000000"
    feeds.store_json("seg:parsed:" + first, {"available": True, "facts": []})
    out = segments.build("INTC")
    assert "https://example.test/0_htm.xml" not in edgar, "read again from EDGAR"
    assert first in segment_store.load_many([first])
    assert out["fetched_now"] == 3


def test_a_document_that_will_not_parse_is_kept_and_a_network_failure_is_not(edgar, monkeypatch):
    """A malformed filing stays malformed, so its answer is kept and it is not
    fetched on every visit. A timeout is worth trying again."""
    calls = {"n": 0}

    def flaky(url):
        calls["n"] += 1
        if url.endswith("/0_htm.xml"):
            return {"available": False, "reason": "unparsable instance"}
        if url.endswith("/1_htm.xml"):
            raise TimeoutError("EDGAR was slow")
        return {"available": True, "facts": []}

    monkeypatch.setattr(segments, "parse_instance", flaky)
    one = segments.build("INTC")
    assert one["filings_failed"] == 2
    two = segments.build("INTC")
    kept = segment_store.load_many(["0000050863-26-000000", "0000050863-26-000001"])
    assert "0000050863-26-000000" in kept and kept["0000050863-26-000000"]["available"] is False
    assert "0000050863-26-000001" not in kept
    assert two["filings_failed"] >= 1


def test_a_store_that_cannot_be_opened_costs_the_history_not_the_panel(edgar, monkeypatch, tmp_path):
    """Pointed under a file, so creating its directory raises OSError: the
    unmounted-volume case. The panel still answers, a batch at a time, as it
    did before there was a store."""
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("")
    monkeypatch.setattr(segment_store, "DB_PATH", str(blocker / "segments.db"))
    out = segments.build("INTC")
    assert out["available"] is True and out["filings_read"] == 3
    assert segment_store.save("x", {"available": True}) is False
    assert segment_store.load_many(["x"]) == {}


# ------------------------------------------------------------- the panel


def _panel(script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = """
      load('tests/support/browser_stubs.js');
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      document.documentElement.style.removeProperty = function () {};
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
      var timers = [];
      setTimeout = function (f) { timers.push(f); return timers.length; };
      clearTimeout = function () {};
      var host = { innerHTML: '' };
      document.getElementById = function (id) { return id === 'seg-host' ? host : null; };
      revealPanels = function () {};
      var asked = [], painted = [];
      function batches(list) {
        getJSON = function (url) {
          asked.push(url);
          var next = list[Math.min(asked.length - 1, list.length - 1)];
          return Promise.resolve(next);
        };
      }
      function page(read, unread, fetched) {
        return { available: true, ticker: 'INTC', filings_listed: 13, filings_read: read,
          filings_unread: unread, fetched_now: fetched, quarters: [], tables: [] };
      }
      function run() {
        drainMicrotasks();
        while (timers.length) { painted.push(host.innerHTML); timers.shift()(); drainMicrotasks(); }
      }
      STATE.ticker = 'INTC'; STATE.view = 'financials';
      var R = {};
    """ + script + "\nprint('RESULT:' + JSON.stringify(R));"
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=120,
                         cwd=str(ROOT))
    blob = out.stdout + out.stderr
    assert "RESULT:" in blob, blob[-2000:]
    return json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])


def test_the_panel_reads_the_rest_without_being_asked():
    out = _panel("""
      batches([page(3, 10, 3), page(6, 7, 3), page(9, 4, 3), page(12, 1, 3), page(13, 0, 1)]);
      loadSegments(false); run();
      R.asked = asked.length; R.read = STATE.segments.filings_read;
      R.more = STATE.segmentsMore; R.forced = asked.filter(function (u) { return /force/.test(u); }).length;
      R.midway = painted[0];
    """)
    assert out["asked"] == 5 and out["read"] == 13
    assert out["more"] is False, "it stops once nothing is left"
    assert out["forced"] == 0
    assert "more being read now" in out["midway"]


def test_the_panel_stops_when_a_batch_makes_no_progress():
    """EDGAR refusing, or every remaining filing failing: asking again would be
    a loop against an agency that asks callers to be considerate."""
    out = _panel("""
      batches([page(3, 10, 0)]);
      loadSegments(false); run();
      R.asked = asked.length; R.note = host.innerHTML;
    """)
    assert out["asked"] == 1
    assert "read on your next visit" in out["note"]


def test_the_panel_stops_when_the_reader_leaves():
    out = _panel("""
      batches([page(3, 10, 3), page(6, 7, 3)]);
      loadSegments(false); drainMicrotasks();
      STATE.view = 'home';
      run();
      R.asked = asked.length;
    """)
    assert out["asked"] == 1


def test_the_panel_has_a_ceiling_on_rounds():
    out = _panel("""
      batches([page(3, 10, 3)]);      // progress reported for ever
      loadSegments(false); run();
      R.asked = asked.length; R.rounds = SEGMENT_MORE_ROUNDS;
    """)
    assert out["asked"] == out["rounds"] + 1
