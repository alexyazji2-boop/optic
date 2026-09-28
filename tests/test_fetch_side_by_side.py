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
    assert Y.meter_read()[3] == 1, "three tokens spent on one request: %r" % (Y.meter_read(),)


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
            # As yfinance does: fetched on the first read, kept on the object.
            if not self._listed:
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


# ------------------------------------------------------------ the expiry list


def test_the_expiry_list_is_fetched_once_for_the_expiries_and_the_chain(monkeypatch):
    listings = []
    monkeypatch.setattr(Y.yf, "Ticker", _chain_ticker(listings))
    provider = Y.YFinanceProvider()
    assert provider.expirations("ABC") == EXPIRIES
    chain = provider.options_chain("ABC", expiries=EXPIRIES)
    assert len(chain) == 12
    assert len(listings) == 1, "the list was fetched %d times" % len(listings)


def test_a_refused_expiry_list_is_not_remembered_and_halves_the_rate_once(monkeypatch):
    class Ticker:
        def __init__(self, symbol):
            pass

        @property
        def options(self):
            raise RuntimeError("Too Many Requests")

    monkeypatch.setattr(Y.yf, "Ticker", Ticker)
    provider = Y.YFinanceProvider()
    before = Y._BUCKET["rate"]
    assert provider.expirations("ABC") == []
    assert Y._BUCKET["rate"] == pytest.approx(before / 2.0), "one refusal, one halving"
    assert "exp:ABC" not in Y._CACHE and "optt:ABC" not in Y._CACHE, (
        "a throttled feed remembered as a stock with no options")


# ------------------------------------------------------------ the sector check


def test_the_sector_check_reads_the_builds_own_history_and_shared_series(monkeypatch):
    from app.analytics import sector_confirm

    asked = []
    idx = pd.bdate_range("2026-03-02", periods=140)

    def history(sym, period="2y", interval="1d"):
        asked.append((sym, period))
        step = {"NVDA": 1.0, "XLK": 0.5, "SPY": 0.2}[sym]
        return pd.DataFrame({"Close": [100.0 + step * i for i in range(len(idx))]}, index=idx)

    provider = types.SimpleNamespace(
        history=history,
        batch_history=lambda *a, **k: pytest.fail("one download keyed on the stock again"))
    monkeypatch.setattr(sector_confirm.sector_board, "build", lambda p: {"rows": []})
    out = sector_confirm.build(provider, "NVDA", "Technology")
    # The stock's series under the same key as the ticker build's history leg,
    # so it is that leg's fetch, not another.
    assert sorted(asked) == [("NVDA", "2y"), ("SPY", "6mo"), ("XLK", "1y")]
    assert out["available"] and out["etf"] == "XLK"
    expect = lambda step: round(((100 + step * 139) / (100 + step * 118) - 1) * 100, 2)  # noqa: E731
    assert out["stock_return_pct"] == expect(1.0)
    assert out["etf_return_pct"] == expect(0.5)
    assert out["spy_return_pct"] == expect(0.2)



def test_the_sector_check_and_the_sector_pair_read_one_fund_series(monkeypatch):
    # Both ask for the same fund; one key means one request.
    from app.analytics import sector_confirm, swing

    asked = []
    idx = pd.bdate_range("2025-09-01", periods=260)

    def history(sym, period="2y", interval="1d"):
        asked.append((sym, period, interval))
        return pd.DataFrame({"Close": [100.0 + i for i in range(len(idx))]}, index=idx)

    provider = types.SimpleNamespace(history=history)
    monkeypatch.setattr(sector_confirm.sector_board, "build", lambda p: {"rows": []})
    sector_confirm.build(provider, "NVDA", "Technology")
    swing._sector_pair_idea({"ticker": "NVDA", "sector": "Technology"},
                            history("NVDA"), provider)
    fund = [a for a in asked if a[0] == "XLK"]
    assert len(set(fund)) == 1, "two different requests for the fund: %r" % fund
