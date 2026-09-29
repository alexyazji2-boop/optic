"""`.info` from its three documents at once, not one after another.

yfinance 1.x builds `.info` from the quote summary, then the v7 quote, then a
fundamentals timeseries read for `trailingPegRatio`, each waiting on the one
before. On the live site ten isolated quotes took 0.32s to 0.66s, eight fired
together 0.84s to 1.07s each, and inside a cold ticker load, with a dozen other
reads in flight, 1.6s to 3.2s (CLSK and HUT, 2026-09-29), the build's critical
path. The quote, the session strip, the profile and the short interest all
read it.

Fetched side by side, the wait is the slowest document rather than the sum.
Checked against yfinance's own `.info` for AAPL, COIN, SPY, SOXL, ES=F, ^GSPC
and BTC-USD: the same keys, and every field this app reads equal, at 0.07s to
0.15s against 0.17s to 0.38s from a desk. The summary keeps fifteen minutes
and the PEG six hours, so a repeat load reads only the quote.
"""
from __future__ import annotations

import threading
import time

import pytest

from app.providers import yf as Y


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.setattr(Y, "_CACHE", {})
    monkeypatch.setattr(Y, "_BUCKET", {"tokens": 100.0, "rate": 100.0, "last": time.time()})
    monkeypatch.setattr(Y, "_THROTTLE", {"until": 0.0, "hits": 0, "last_seen": None})


SUMMARY = {"quoteSummary": {"result": [{
    "assetProfile": {"sector": "Technology", "industry": "Consumer Electronics",
                     "longBusinessSummary": "Makes\xa0phones.", "maxAge": 1,
                     "companyOfficers": [{"name": "A", "totalPay": {"raw": 5, "fmt": "5"}}]},
    "summaryDetail": {"previousClose": 100.0, "currency": "EUR", "beta": 1.2, "dayHigh": 1.0,
                      "dividendYield": 0.5, "maxAge": 1, "askSize": None},
    "financialData": {"targetMeanPrice": 150.0, "recommendationKey": "buy", "profitMargins": 0.25},
    "defaultKeyStatistics": {"pegRatio": 2.0, "shortPercentOfFloat": 0.01},
    "quoteType": {"quoteType": "EQUITY", "longName": "Summary name"},
}], "error": None}}
QUOTE = {"quoteResponse": {"result": [{
    "symbol": "ZZZ", "regularMarketPrice": 101.5, "regularMarketPreviousClose": 100.0,
    "currency": "USD", "longName": "Quote name", "marketState": "REGULAR", "dayHigh": None,
}], "error": None}}


def test_the_merge_is_the_one_yfinance_does():
    """Run yfinance's own builder on the same two documents and compare.

    If a yfinance release changes how `.info` is put together, this fails
    before any page shows a field the merge no longer produces."""
    from yfinance.scrapers.quote import Quote
    q = Quote.__new__(Quote)
    q._symbol = "ZZZ"
    q._already_fetched = False
    q._fetch = lambda modules: {k: v for k, v in SUMMARY.items()}
    q._fetch_additional_info = lambda: {k: v for k, v in QUOTE.items()}
    q._fetch_info()
    theirs = q._info
    ours = Y.merge_info("ZZZ", SUMMARY, QUOTE, peg=1.7)
    assert {k: v for k, v in ours.items() if k != "trailingPegRatio"} == theirs
    assert ours["trailingPegRatio"] == 1.7


def test_the_merge_reads_the_way_the_app_needs_it():
    info = Y.merge_info("ZZZ", SUMMARY, QUOTE, peg=None)
    assert info["regularMarketPrice"] == 101.5 and info["sector"] == "Technology"
    assert info["currency"] == "USD", "the quote's fields are laid over the summary's"
    assert info["longName"] == "Quote name"
    assert info["maxAge"] == 86400 and "askSize" not in info
    assert info["longBusinessSummary"] == "Makes phones."
    assert info["companyOfficers"][0]["totalPay"] == 5
    assert Y.merge_info("ZZZ", None, {"quoteResponse": {"result": []}}) == {}, \
        "a symbol neither document knows is an empty dict, as .info gives"
    assert Y.merge_info("ES=F", None, QUOTE)["regularMarketPrice"] == 101.5, \
        "a future or an index has no summary and still has a quote"


class Reads:
    """A stand-in for yfinance's Quote: each read sleeps, and is counted."""

    def __init__(self, calls, delay=0.3, refuse=None):
        self.calls, self.delay, self.refuse = calls, delay, refuse

    def _fetch(self, modules):
        self.calls.append("summary")
        time.sleep(self.delay)
        if self.refuse == "summary":
            raise RuntimeError("Too Many Requests. Rate limited. Try after a while.")
        return SUMMARY

    def _fetch_additional_info(self):
        self.calls.append("quote")
        time.sleep(self.delay)
        return QUOTE


class Data:
    def __init__(self, calls, delay=0.3):
        self.calls, self.delay = calls, delay

    def get_raw_json(self, url):
        self.calls.append("peg")
        time.sleep(self.delay)
        assert "type=trailingPegRatio" in url and "symbol=ZZZ" in url
        return {"timeseries": {"result": [{"trailingPegRatio": [
            {"reportedValue": {"raw": 1.1}}, {"reportedValue": {"raw": 1.4}}]}], "error": None}}


def _ticker_class(calls, **kw):
    class Ticker:
        def __init__(self, symbol):
            self._quote = Reads(calls, **kw)
            self._data = Data(calls, kw.get("delay", 0.3))

        @property
        def info(self):
            calls.append("info")
            return {"regularMarketPrice": 1.0}
    return Ticker


def test_the_three_documents_are_read_at_once(monkeypatch):
    calls = []
    monkeypatch.setattr(Y.yf, "Ticker", _ticker_class(calls))
    provider = Y.YFinanceProvider()
    t0 = time.time()
    info = provider._info("ZZZ")
    took = time.time() - t0
    assert sorted(calls) == ["peg", "quote", "summary"], calls
    assert took < 0.55, "three 0.3s reads took %.2fs, so they ran in a row" % took
    assert info["regularMarketPrice"] == 101.5 and info["trailingPegRatio"] == 1.4
    assert provider.quote("ZZZ")["price"] == 101.5 and len(calls) == 3, "the quote reuses it"


def test_a_repeat_load_reads_only_the_quote(monkeypatch):
    calls = []
    monkeypatch.setattr(Y.yf, "Ticker", _ticker_class(calls, delay=0.0))
    provider = Y.YFinanceProvider()
    provider._info("ZZZ")
    # A minute later: past the quote's thirty seconds, inside the summary's
    # fifteen minutes and the PEG's six hours.
    for key in list(Y._CACHE):
        stamp, value = Y._CACHE[key]
        Y._CACHE[key] = (stamp - 60, value)
    calls.clear()
    provider._info("ZZZ")
    assert calls == ["quote"], calls


def test_a_stand_in_ticker_answers_with_its_own_info(monkeypatch):
    calls = []

    class Ticker:
        def __init__(self, symbol):
            pass

        @property
        def info(self):
            calls.append("info")
            return {"regularMarketPrice": 7.0}
    monkeypatch.setattr(Y.yf, "Ticker", Ticker)
    assert Y.YFinanceProvider()._info("ZZZ") == {"regularMarketPrice": 7.0} and calls == ["info"]


def test_a_refusal_reaches_the_limiter(monkeypatch):
    calls = []
    monkeypatch.setattr(Y.yf, "Ticker", _ticker_class(calls, delay=0.0, refuse="summary"))
    with pytest.raises(Exception):
        Y.YFinanceProvider()._info("ZZZ")
    assert "info" not in calls, "a refusal is not a reason to read .info three more times"
    assert Y._BUCKET["rate"] < 100.0, "the gated fill halved the rate"


def test_the_prior_close_is_the_quote_documents(monkeypatch):
    calls = []
    Ticker = _ticker_class(calls, delay=0.0)
    provider = Y.YFinanceProvider()
    assert provider._prior_close("ZZZ", Ticker("ZZZ"), {}) == 100.0
    assert calls == ["quote"], "one read, not the three behind .info"


def test_only_a_spent_token_counts_as_a_success(monkeypatch):
    monkeypatch.setattr(Y, "_BUCKET", {"tokens": 100.0, "rate": 1.0, "last": time.time()})
    monkeypatch.setattr(Y, "YF_RATE", 2.0)
    Y._cached("ungated", 60, lambda: 1, gate=False)
    assert Y._BUCKET["rate"] == 1.0
    Y._cached("gated", 60, lambda: 1)
    assert Y._BUCKET["rate"] == pytest.approx(1.02)


def test_the_expiry_list_outlives_the_chain():
    P = Y.YFinanceProvider
    assert P.TTL_EXPIRIES == 30 * 60 and P.TTL_CHAIN == 60
    import inspect
    assert '_cached("exp:" + ticker, self.TTL_EXPIRIES' in inspect.getsource(P.expirations)
    assert '_cached("optt:" + ticker, self.TTL_EXPIRIES' in inspect.getsource(P._options_ticker)


# ------------------------------------------------------ the earnings dates

PAGE = ("<html><head>" + "<script>var x = 1;</script>" * 4000 + "</head><body><div>"
        "<table><thead><tr><th>Symbol</th><th>Company</th><th>Earnings Date</th>"
        "<th>EPS Estimate</th><th>Reported EPS</th><th>Surprise (%)</th></tr></thead><tbody>"
        "<tr><td>ZZZ</td><td>Zed</td><td>October 30, 2026 at 4 PM EDT</td><td>1.10</td><td>-</td><td>-</td></tr>"
        "<tr><td>ZZZ</td><td>Zed</td><td>July 30, 2026 at 4 PM EDT</td><td>1.00</td><td>1.20</td><td>+20.00</td></tr>"
        "<tr><td>ZZZ</td><td>Zed</td><td>January 29, 2026 at 4 PM EST</td><td>0.90</td><td>0.80</td><td>-11.11</td></tr>"
        "</tbody></table></div></body></html>")


class _Page:
    text = PAGE


def test_the_earnings_frame_is_yfinances_own(monkeypatch):
    """yfinance's scraper and this one, on the same page."""
    import yfinance as yf
    theirs_ticker = yf.Ticker("ZZZ")
    monkeypatch.setattr(theirs_ticker._data, "cache_get", lambda url, *a, **k: _Page())
    theirs = theirs_ticker._get_earnings_dates_using_scrape(limit=12)

    class Data:
        def get(self, url, *a, **k):
            assert "symbol=ZZZ" in url and "size=25" in url
            return _Page()

    class Ticker:
        def __init__(self, symbol):
            self._data = Data()
    monkeypatch.setattr(Y.yf, "Ticker", Ticker)
    import bs4
    monkeypatch.setattr(bs4, "BeautifulSoup", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("the whole page went through BeautifulSoup")))
    ours = Y.YFinanceProvider()._earnings_dates("ZZZ")
    assert ours.equals(theirs)
    rows = Y.YFinanceProvider().earnings_history("ZZZ")
    assert rows[1] == {"date": "2026-07-30", "eps_estimate": 1.0, "eps_reported": 1.2,
                       "surprise_pct": 20.0}


def test_a_page_without_a_table_has_no_dates(monkeypatch):
    class Data:
        def get(self, url, *a, **k):
            class R:
                text = "<html><body>No results</body></html>"
            return R()

    class Ticker:
        def __init__(self, symbol):
            self._data = Data()
    monkeypatch.setattr(Y.yf, "Ticker", Ticker)
    assert Y.YFinanceProvider()._earnings_dates("ZZZ") is None
    assert Y.YFinanceProvider().earnings_history("ZZZ") == []


def test_a_stand_in_answers_with_its_own_earnings_dates(monkeypatch):
    class Ticker:
        def __init__(self, symbol):
            pass
        earnings_dates = "their frame"
    monkeypatch.setattr(Y.yf, "Ticker", Ticker)
    assert Y.YFinanceProvider()._earnings_dates("ZZZ") == "their frame"


# ------------------------------------------------ the exchange's timezone

def test_the_timezone_cache_moves_only_onto_a_configured_volume(monkeypatch, tmp_path):
    moved = []
    monkeypatch.setattr(Y.yf, "set_tz_cache_location", lambda path: moved.append(path))
    assert Y._persist_timezones(None) is None and moved == [], "tests and local runs keep the default"
    assert Y._persist_timezones(str(tmp_path)) == str(tmp_path / "yfinance")
    assert moved == [str(tmp_path / "yfinance")] and (tmp_path / "yfinance").is_dir()


def test_a_quote_teaches_the_cache_its_timezone(monkeypatch):
    stored = {}

    class Store:
        def lookup(self, symbol):
            return stored.get(symbol)

        def store(self, symbol, tz):
            stored[symbol] = tz
    from yfinance import cache as yf_cache
    monkeypatch.setattr(yf_cache, "get_tz_cache", lambda: Store())
    doc = {"quoteResponse": {"result": [{"exchangeTimezoneName": "America/New_York"}]}}
    Y._remember_timezone("ZZZ", doc)
    assert stored == {"ZZZ": "America/New_York"}
    Y._remember_timezone("BAD", {"quoteResponse": {"result": [{"exchangeTimezoneName": "Mars/Base"}]}})
    Y._remember_timezone("NONE", None)
    assert set(stored) == {"ZZZ"}, "an invalid or absent zone is not stored"
    calls = []
    monkeypatch.setattr(Y.yf, "Ticker", _ticker_class(calls, delay=0.0))
    monkeypatch.setattr(Y, "_remember_timezone", lambda sym, d: calls.append(("tz", sym)))
    Y.YFinanceProvider()._info("ZZZ")
    assert ("tz", "ZZZ") in calls, "the quote read passes its document on"
