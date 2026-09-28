"""A first load's slow fetches, measured on the live site and made fewer or wider.

The Server-Timing header's first steady-state reading of a cold FTNT
(2026-09-28, 5.7s) had nothing held at the rate limiter. The time was in the
requests: the option chain 4.5s for four expiries fetched one after another,
the statements 3.5s for four in a row, and the quote and the short interest
2.7s and 2.9s for the same `.info` document scraped twice at once, with the
profile scraping it a third time. Yahoo answered ten requests at once in
1.0s to 1.3s each, so width is cheap there and repetition is not.
"""
from __future__ import annotations

import threading
import time
import types

import pandas as pd
import pytest

from app.providers import yf as Y


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.setattr(Y, "_CACHE", {})
    monkeypatch.setattr(Y, "_BUCKET", {"tokens": 100.0, "rate": 100.0, "last": time.time()})
    monkeypatch.setattr(Y, "_THROTTLE", {"until": 0.0, "hits": 0, "last_seen": None})


# ------------------------------------------------------------ one .info scrape


def test_the_quote_the_short_interest_and_the_profile_share_one_scrape(monkeypatch):
    scrapes = []

    class Ticker:
        def __init__(self, symbol):
            self.symbol = symbol

        @property
        def info(self):
            scrapes.append(self.symbol)
            time.sleep(0.1)
            return {"regularMarketPrice": 41.2, "longName": "Robinhood Markets",
                    "sharesShort": 1000.0, "quoteType": "EQUITY", "sector": "Financial Services"}

    monkeypatch.setattr(Y.yf, "Ticker", Ticker)
    provider = Y.YFinanceProvider()
    Y.meter_reset()
    out = {}
    calls = {"quote": provider.quote, "short": provider.short_interest, "profile": provider.profile}
    threads = [threading.Thread(target=lambda n=n, f=f: out.update({n: f("HOOD")}))
               for n, f in calls.items()]
    for t in threads:
        t.start()
    for t in threads:
        t.join(5)
    assert scrapes == ["HOOD"], "scraped %d times" % len(scrapes)
    assert out["quote"]["price"] == 41.2
    assert out["short"]["shares_short"] == 1000.0
    assert out["profile"]["sector"] == "Financial Services"


def test_the_limiter_counts_the_one_request_it_lets_out(monkeypatch):
    class Ticker:
        def __init__(self, symbol):
            pass

        @property
        def info(self):
            return {"regularMarketPrice": 1.0}

    monkeypatch.setattr(Y.yf, "Ticker", Ticker)
    provider = Y.YFinanceProvider()
    Y.meter_reset()
    provider.quote("ABC"), provider.short_interest("ABC"), provider.profile("ABC")
    assert Y.meter_read()[2] == 1, "three tokens spent on one request: %r" % (Y.meter_read(),)


def test_a_failed_scrape_still_reads_as_each_one_did(monkeypatch):
    class Ticker:
        def __init__(self, symbol):
            pass

        @property
        def info(self):
            raise RuntimeError("Too Many Requests")

    monkeypatch.setattr(Y.yf, "Ticker", Ticker)
    # The refusal opens a backoff that each later call waits out, up to the
    # gate's twenty seconds, exactly as each did when it scraped for itself.
    monkeypatch.setattr(Y, "MAX_GATE_WAIT", 0.05)
    provider = Y.YFinanceProvider()
    monkeypatch.setattr(provider, "history", lambda *a, **k: pd.DataFrame())
    assert provider.short_interest("ABC") == {}
    assert provider.profile("ABC") == {}
    assert provider.quote("ABC")["price"] is None
    assert Y._THROTTLE["hits"] >= 1, "the refusal was recorded"


# ------------------------------------------------------------ the chain


def _side(strikes):
    return pd.DataFrame({"contractSymbol": ["C%s" % k for k in strikes], "strike": strikes,
                         "lastPrice": [1.0] * len(strikes), "bid": [0.9] * len(strikes),
                         "ask": [1.1] * len(strikes), "volume": [10] * len(strikes),
                         "openInterest": [100] * len(strikes),
                         "impliedVolatility": [0.3] * len(strikes),
                         "inTheMoney": [False] * len(strikes)})


def _chain_ticker(listings, fail=()):
    class Ticker:
        def __init__(self, symbol):
            self._listed = False

        @property
        def options(self):
            listings.append(threading.get_ident())
            self._listed = True
            return ("2026-10-16", "2026-10-30", "2026-11-20", "2026-12-18")

        def option_chain(self, exp):
            assert self._listed, "read before the expiry list"
            time.sleep(0.2)
            if exp in fail:
                raise RuntimeError("no data for " + exp)
            return types.SimpleNamespace(calls=_side([90.0, 100.0]), puts=_side([95.0]))
    return Ticker


EXPIRIES = ["2026-10-16", "2026-10-30", "2026-11-20", "2026-12-18"]


def test_the_expiries_are_fetched_side_by_side_in_order(monkeypatch):
    listings = []
    monkeypatch.setattr(Y.yf, "Ticker", _chain_ticker(listings))
    provider = Y.YFinanceProvider()
    monkeypatch.setattr(provider, "expirations", lambda t: EXPIRIES)
    t0 = time.time()
    chain = provider.options_chain("ABC", expiries=EXPIRIES)
    took = time.time() - t0
    assert took < 0.5, "four 0.2s expiries took %.2fs" % took
    assert len(listings) == 1, "the expiry list was read %d times" % len(listings)
    assert chain["expiry"].drop_duplicates().tolist() == EXPIRIES
    assert len(chain) == 12


def test_a_failed_expiry_is_skipped_as_before(monkeypatch):
    monkeypatch.setattr(Y.yf, "Ticker", _chain_ticker([], fail=("2026-10-30",)))
    provider = Y.YFinanceProvider()
    monkeypatch.setattr(provider, "expirations", lambda t: EXPIRIES)
    chain = provider.options_chain("ABC", expiries=EXPIRIES)
    assert chain["expiry"].drop_duplicates().tolist() == ["2026-10-16", "2026-11-20", "2026-12-18"]


# ------------------------------------------------------------ the statements


def test_the_four_statements_are_fetched_side_by_side(monkeypatch):
    frame = pd.DataFrame({pd.Timestamp("2025-12-31"): [1.0, 2.0]}, index=["Total Revenue", "Net Income"])

    class Ticker:
        def __init__(self, symbol):
            pass

        def _slow(self):
            time.sleep(0.2)
            return frame

        income_stmt = property(_slow)
        quarterly_income_stmt = property(_slow)
        balance_sheet = property(_slow)

        @property
        def cashflow(self):
            time.sleep(0.2)
            return pd.DataFrame()                 # a statement the feed lacks

    monkeypatch.setattr(Y.yf, "Ticker", Ticker)
    t0 = time.time()
    out = Y.YFinanceProvider().financials("ABC")
    took = time.time() - t0
    assert took < 0.5, "four 0.2s statements took %.2fs" % took
    assert out["cashflow_annual"] is None
    for name in ("income_annual", "income_quarterly", "balance_annual"):
        assert out[name] == {"periods": ["2025-12-31"],
                             "rows": {"Total Revenue": [1.0], "Net Income": [2.0]}}, name
