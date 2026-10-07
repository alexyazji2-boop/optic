"""A House disclosure's dates: the gap is trade to filing, and an impossible date
does not set the page.

Two faults, both seen in the 2026 record on the Insiders page.

"Filed after" was trade to NOTIFICATION, the date the member learned of the
trade, under a header promising "days between the trade and the filing". The
two differ on 2,588 of 2,838 rows, and a row read "Traded Sep 28, Disclosed
Oct 2, Filed after 0d": four days apart in the two cells beside it. The 45-day
limit the column cites counts from the trade to the filing.

One filing dates a SONY trade "12/26/2026" and was received on Feb 9. It was
the newest trade in the archive, so the per-day chart's thirty days ran Nov 27
to Dec 26 of a year not yet over and drew one bar, and the row topped the table
with a lag of -339 days.

Nothing here touches the network: the Clerk's index and files are fakes.
"""
from __future__ import annotations

import pytest

from app.analytics import congress


class _Resp:
    status_code, content = 200, b"%PDF-1.4 fake"


class _Clerk:
    def get(self, url, timeout=None):
        return _Resp()


INDEX = [
    {"doc_id": "1", "last": "Rulli", "first": "Michael", "prefix": "Hon.",
     "filed": "10/02/2026", "district": "OH06", "year": "2026"},
    {"doc_id": "2", "last": "Cohen", "first": "Steve", "prefix": "Hon.",
     "filed": "02/09/2026", "district": "TN09", "year": "2026"},
    {"doc_id": "3", "last": "Hern", "first": "Kevin", "prefix": "Hon.",
     "filed": "09/25/2026", "district": "OK01", "year": "2026"},
]

ROWS = {
    # Notified the day of the trade, filed four days later.
    "1": [{"ticker": "MSFT", "traded": "09/28/2026", "notified": "09/28/2026"}],
    # The trade date is after the filing that reports it.
    "2": [{"ticker": "SONY", "traded": "12/26/2026", "notified": "01/21/2026"}],
    # Filed ten days after the trade.
    "3": [{"ticker": "HD", "traded": "09/15/2026", "notified": "09/24/2026"}],
}


@pytest.fixture
def record(monkeypatch, tmp_path):
    def parse(path):
        doc = path.rsplit("/", 1)[-1][:-len(".pdf")]
        rows = [{"asset_kind": "ST", "transaction": "purchase", "side": "buy",
                 "amount_low": 1001, "amount_high": 15000, **r} for r in ROWS[doc]]
        return {"member": None, "district": None, "error": None, "rows": rows}

    monkeypatch.setattr(congress, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(congress, "REQUEST_GAP", 0)
    monkeypatch.setattr(congress, "_session", lambda: _Clerk())
    monkeypatch.setattr(congress, "_fetch_index", lambda year, sess: INDEX)
    monkeypatch.setattr(congress, "_parse_pdf", parse)
    monkeypatch.setattr(congress, "_PARSED", {})
    monkeypatch.setattr(congress, "_FAILED", {})
    monkeypatch.setattr(congress, "_MEM", {"at": 0.0, "trades": [], "index_at": None,
                                           "parsed": 0, "known": 0, "backlog": 0})
    congress.refresh(2026, 10)
    return congress.summary(limit=10, activity_days=30)


def _row(out, sym):
    return next(t for t in out["trades"] if t["ticker"] == sym)


def test_filed_after_counts_from_the_trade_to_the_filing(record):
    assert _row(record, "MSFT")["disclosure_lag_days"] == 4, "it was 0: trade to notification"
    assert _row(record, "HD")["disclosure_lag_days"] == 10, "it was 9"
    # The notification gap is kept beside it, named for what it is.
    assert _row(record, "HD")["notice_lag_days"] == 9
    assert record["lag_median"] == 7 and record["lag_max"] == 10


def test_a_trade_dated_after_its_filing_is_marked_and_kept(record):
    sony = _row(record, "SONY")
    assert sony["date_suspect"] is True
    assert sony["disclosure_lag_days"] is None, "no -339 days"
    assert sony["traded_iso"] == "2026-12-26", "shown as filed, not corrected by guesswork"
    assert record["dates_suspect"] == 1
    assert record["count"] == 3, "the row is not dropped"


def test_it_does_not_set_the_window_the_order_or_the_latest_trade(record):
    days = record["activity"]
    assert days[-1]["date"] == "2026-09-28", "the chart ended on a date in December"
    assert sum(d["buys"] for d in days) == 2, "the window holds the two real trades"
    assert record["latest_traded"] == "2026-09-28"
    assert record["trades"][0]["ticker"] == "MSFT", "it topped the table"
    # Sorted by its filing date instead, so it sits in February where it was filed.
    assert record["trades"][-1]["ticker"] == "SONY"


def test_the_helper_reads_either_date_format():
    assert congress._disclosure_lag("09/28/2026", "2026-10-02") == 4
    assert congress._disclosure_lag("09/28/2026", "10/02/2026") == 4
    assert congress._disclosure_lag("09/28/2026", "") is None
    assert congress._date_suspect("2026-12-26", "2026-02-09") is True
    assert congress._date_suspect("2026-09-28", "2026-10-02") is False
    assert congress._date_suspect(None, "2026-10-02") is False


def test_a_slice_with_nothing_to_chart_says_so_rather_than_drawing_a_key():
    """SONY's only House trade is the impossible one, so its window is empty.
    The panel described a chart, drew the key over nothing, and said half the
    trades were disclosed "some days or more after the fact"."""
    import json
    import os
    import re
    import shutil
    import subprocess
    from pathlib import Path

    jsc = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
    exe = jsc if os.path.exists(jsc) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    app = (Path(__file__).resolve().parent.parent / "static/app.js").read_text()

    def fn(name):
        return re.search(r"^function " + name + r"\([^\n]*\) \{.*?^\}", app, re.M | re.S).group()

    def run(c):
        src = "\n".join([
            "function fmt(v, d) { return Number(v).toFixed(d); }",
            "function esc(v) { return String(v); }",
            "function dayLabel(v) { return v; }",
            fn("congressActivityChart"), fn("congressChartBlock"),
            "print(congressChartBlock(%s, {days: 30}));" % json.dumps(c),
        ])
        return subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=30).stdout

    empty = run({"count": 1, "activity": [], "dates_suspect": 1, "lag_median": None,
                 "lag_max": None, "other": 0, "activity_days": 30})
    assert "Nothing to chart" in empty and "dated after the filing" in empty
    assert "ca-key" not in empty and "ca-chart" not in empty, "a key over nothing"
    assert "some days" not in empty
    day = {"date": "2026-09-28", "buys": 1, "sells": 0, "other": 0}
    drawn = run({"count": 3, "activity": [day], "dates_suspect": 1, "lag_median": 7,
                 "lag_max": 10, "other": 0, "activity_days": 30})
    assert "ca-chart" in drawn and "ca-key" in drawn
    assert "7 days" in drawn and "One filing dates its trade" in drawn
