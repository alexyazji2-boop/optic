"""Two years of insider filings in the ticker payload, not the 12 latest (2026-10-19).

The owner asked for insider trades on the v2 chart; with 12 rows they stopped about a month back for a large
company (AAPL: Sep 15 to Oct 6). Yahoo lists roughly 70 to 150 rows for one, about two years. The provider now
keeps the last two years, the span of daily bars the charts draw them on, newest first and at most 200.

What reads the list, and what it does with more:
- the v2 chart's insider arrows and the classic chart's insider marks: every purchase and sale, now two years;
- the v2 and classic Insiders widgets: the latest 6, unchanged;
- the classic Financials table: every row, in its 200px scroll box;
- the v2 Financials table: the latest 20, with a line saying how many there are;
- the watches: the latest 12, as before, so a watch on purchases still means a recent one.
"""
from __future__ import annotations

import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from app.analytics import watches
from app.providers import yf as Y

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.setattr(Y, "_CACHE", {})
    monkeypatch.setattr(Y, "_BUCKET", {"tokens": 100.0, "rate": 100.0, "last": time.time()})
    monkeypatch.setattr(Y, "_THROTTLE", {"until": 0.0, "hits": 0, "last_seen": None})


def _frame(days_ago):
    today = date.today()
    return pd.DataFrame([{"Insider": f"PERSON {n}", "Position": "Director", "Start Date": pd.Timestamp(today - timedelta(days=d)),
                          "Shares": 100.0 + n, "Value": 1000.0 + n, "Text": "Sale at price 10.00 per share."}
                         for n, d in enumerate(days_ago)])


def _stub(monkeypatch, frame):
    class Ticker:
        def __init__(self, symbol):
            self.symbol = symbol
        insider_purchases = pd.DataFrame()
        insider_transactions = frame
    monkeypatch.setattr(Y.yf, "Ticker", Ticker)


def test_two_years_newest_first(monkeypatch):
    # out of order, with rows older than two years
    _stub(monkeypatch, _frame([400, 3, 900, 30, 729, 731, 1]))
    got = Y.YFinanceProvider().insiders("ZZZA")["transactions"]
    ages = [(date.today() - date.fromisoformat(r["date"])).days for r in got]
    assert ages == [1, 3, 30, 400, 729], "the last two years, newest first"
    assert all(r["action"] == "sale" for r in got)


def test_at_most_two_hundred(monkeypatch):
    _stub(monkeypatch, _frame([d % 700 for d in range(260)]))
    got = Y.YFinanceProvider().insiders("ZZZB")["transactions"]
    assert len(got) == 200
    assert got[0]["date"] >= got[-1]["date"]


def test_a_watch_still_reads_only_the_latest_twelve():
    sale = {"action": "sale", "date": "2026-10-01"}
    old_buy = {"action": "purchase", "date": "2025-03-01"}
    twelve_sales_then_a_buy = {"company": {"ownership": {"recent_transactions": [sale] * 12 + [old_buy]}}}
    assert watches.RECENT_FILINGS == 12
    assert watches._insider_activity(twelve_sales_then_a_buy, {"side": "purchase"}) is None, \
        "a purchase from last year is not news"
    recent_buy = {"company": {"ownership": {"recent_transactions": [sale] * 4 + [old_buy] + [sale] * 20}}}
    assert watches._insider_activity(recent_buy, {"side": "purchase"}) is not None
    ev = watches._insider_activity({"company": {"ownership": {"recent_transactions": [sale] * 80}}}, {"side": "any"})
    assert ev["evidence"].startswith("12 recent form 4 filings"), "the count it reports is the latest twelve"


def test_the_v2_financials_table_shows_the_latest_twenty():
    src = (ROOT / "static/v2/js/pages/financials.js").read_text()
    assert "(ow.recent_transactions || []).slice(0, 20).map(" in src
    assert "The latest 20 of ${(ow.recent_transactions || []).length} filings from the last two years." in src
