"""A company profile whose summary document failed is not kept for a day.

Seen on 2026-10-11: one local server's PEP profile came back with its name
and type (from the v7 quote) and nothing from the quote summary, because
yfinance answers a refused summary read with None. The None was cached for
fifteen minutes and the half-empty profile for a day, so the Overview said
"The data feed has no business description" for PepsiCo while another server,
a minute apart, had the full text.
"""
from __future__ import annotations

import time

import pytest

from app.providers import yf as Y


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.setattr(Y, "_CACHE", {})
    monkeypatch.setattr(Y, "_BUCKET", {"tokens": 100.0, "rate": 100.0, "last": time.time()})
    monkeypatch.setattr(Y, "_THROTTLE", {"until": 0.0, "hits": 0, "last_seen": None})


def _stub(monkeypatch, answers):
    """A Ticker whose `.info` returns the next answer on each scrape."""
    seen = []

    class Ticker:
        def __init__(self, symbol):
            self.symbol = symbol

        @property
        def info(self):
            seen.append(self.symbol)
            return answers[min(len(seen), len(answers)) - 1]

    monkeypatch.setattr(Y.yf, "Ticker", Ticker)
    return seen


def test_a_profile_missing_every_summary_field_is_asked_again(monkeypatch):
    partial = {"longName": "PepsiCo, Inc.", "quoteType": "EQUITY"}
    full = dict(partial, longBusinessSummary="PepsiCo, Inc. engages in beverages.",
                sector="Consumer Defensive", industry="Beverages - Non-Alcoholic")
    _stub(monkeypatch, [partial, full])
    provider = Y.YFinanceProvider()
    first = provider.profile("PEP")
    assert first["name"] == "PepsiCo, Inc." and first["summary"] is None, "the caller still gets what came back"
    Y._CACHE.pop("info:PEP", None)          # the 30-second scrape, as if it had expired
    second = provider.profile("PEP")
    assert second["summary"] == "PepsiCo, Inc. engages in beverages."
    assert second["sector"] == "Consumer Defensive"


def test_a_complete_profile_is_still_kept_for_the_day(monkeypatch):
    full = {"longName": "PepsiCo, Inc.", "quoteType": "EQUITY", "sector": "Consumer Defensive",
            "longBusinessSummary": "Beverages and snacks."}
    seen = _stub(monkeypatch, [full])
    provider = Y.YFinanceProvider()
    provider.profile("PEP")
    Y._CACHE.pop("info:PEP", None)
    provider.profile("PEP")
    assert seen == ["PEP"], "a full profile is cached; scraped %d times" % len(seen)


def test_an_index_with_no_summary_is_not_treated_as_a_failed_read(monkeypatch):
    # Indices and currencies have no asset profile at all; that is the answer.
    seen = _stub(monkeypatch, [{"shortName": "S&P 500", "quoteType": "INDEX"}])
    provider = Y.YFinanceProvider()
    provider.profile("^GSPC")
    Y._CACHE.pop("info:^GSPC", None)
    provider.profile("^GSPC")
    assert seen == ["^GSPC"]


def test_a_refused_summary_document_is_not_cached():
    calls = []

    class Reads:
        def _fetch(self, modules):
            calls.append(modules)
            return None if len(calls) == 1 else {"assetProfile": {"sector": "Technology"}}

    provider = Y.YFinanceProvider()
    reads = Reads()
    assert provider._summary_document("AAPL", reads) is None
    assert provider._summary_document("AAPL", reads) == {"assetProfile": {"sector": "Technology"}}
    assert len(calls) == 2
