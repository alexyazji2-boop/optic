"""The one-day change, taken from the quote rather than from the bars.

The defect this guards against was visible on the home page: the Ask Pulse
starter read "Why is S&P 500 futures up 1.3% today?" on a day ES=F was up
0.13%. Yahoo's daily bars for anything trading around the clock do not break
where the session settles, so the last bar's close over the one before it
counted the overnight gap twice. Cash rows were unaffected, which is what
identifies it as session alignment rather than a stale cache.

Measured on 2026-09-16 with the real feed, and the numbers below are those
measurements: ES=F prior bar 7589.25 against a prior settlement of 7672.50,
gold +0.413% from bars against -0.307% from the quote — a flipped sign on a
haven instrument.
"""
from __future__ import annotations

import pandas as pd
import pytest

from app.analytics import global_markets as gm
from app.analytics import macro
from app.analytics.series_stats import apply_quote, live_quotes
from app.providers.base import MarketDataProvider


def _frame(vals):
    # Dated index: the overnight panel publishes `last_bar` off it.
    idx = pd.date_range("2025-01-01", periods=len(vals), freq="B", tz="America/New_York")
    return pd.DataFrame({"Close": vals, "High": vals, "Low": vals,
                         "Open": vals, "Volume": [1e6] * len(vals)}, index=idx)


# ------------------------------------------------------------- apply_quote


def test_es_futures_reference_error_is_corrected():
    """The measured case. Bars said +1.196%, the contract was up +0.121%."""
    snap = apply_quote({"last": 7680.0, "chg_1d": 1.196},
                       {"last": 7680.0, "prev_close": 7672.5, "as_of": "t"})
    assert snap["chg_1d"] == pytest.approx(0.098, abs=0.001)
    assert snap["prev_close"] == 7672.5
    assert snap["chg_1d_source"] == "quote"
    assert snap["quote_as_of"] == "t"


def test_gold_sign_flip_is_corrected():
    """Bars named the wrong direction, which is worse than being imprecise."""
    snap = apply_quote({"last": 4350.7, "chg_1d": 0.413},
                       {"last": 4350.7, "prev_close": 4367.2})
    assert snap["chg_1d"] < 0


def test_price_and_change_stay_mutually_consistent():
    """Both come off the same two numbers, so dividing one into the other has
    to reproduce the other — the UI prints them side by side."""
    snap = apply_quote({"last": 100.0, "chg_1d": 99.0},
                       {"last": 101.5, "prev_close": 100.0})
    assert snap["last"] == 101.5
    assert snap["chg_1d"] == pytest.approx(
        (snap["last"] / snap["prev_close"] - 1.0) * 100.0, abs=0.001)


def test_ratio_fields_are_left_on_the_bar_basis():
    """Deliberate: each stays consistent with the series it is measured against."""
    snap = apply_quote({"last": 100.0, "chg_1d": 1.0, "vs_sma20": 2.5,
                        "atr_pct": 0.8, "rsi": 55.0},
                       {"last": 101.5, "prev_close": 100.0})
    assert (snap["vs_sma20"], snap["atr_pct"], snap["rsi"]) == (2.5, 0.8, 55.0)


def test_multi_day_changes_are_not_touched():
    snap = apply_quote({"last": 1.0, "chg_1d": 1.0, "chg_5d": 5.0, "chg_20d": 20.0},
                       {"last": 2.0, "prev_close": 1.0})
    assert (snap["chg_5d"], snap["chg_20d"]) == (5.0, 20.0)


@pytest.mark.parametrize("quote", [
    None, {}, {"last": None, "prev_close": 100.0}, {"last": 100.0},
    {"last": 100.0, "prev_close": 0}, {"last": 100.0, "prev_close": None},
])
def test_falls_back_to_the_bars_and_says_so(quote):
    """A missing or unusable quote must leave the bar figure standing rather
    than blanking a row that has a year of history behind it."""
    snap = apply_quote({"last": 50.0, "chg_1d": 1.234}, quote)
    assert snap["chg_1d"] == 1.234
    assert snap["last"] == 50.0
    assert snap["chg_1d_source"] == "bars"
    assert "prev_close" not in snap


def test_source_is_always_recorded():
    """A panel that switches arithmetic between rows has to say which it used."""
    assert apply_quote({}, None)["chg_1d_source"] == "bars"
    assert apply_quote({}, {"last": 2.0, "prev_close": 1.0})["chg_1d_source"] == "quote"


# ------------------------------------------------------------- live_quotes


class _NoQuotes:
    def batch_history(self, symbols, period="1y", interval="1d"):
        return {}


class _Broken:
    def batch_quote(self, tickers):
        raise RuntimeError("feed down")


def test_provider_without_a_quote_feed_degrades_quietly():
    assert live_quotes(_NoQuotes(), ["ES=F"]) == {}


def test_quote_feed_failure_degrades_quietly():
    """A year of history in hand is not a reason to fail the panel."""
    assert live_quotes(_Broken(), ["ES=F"]) == {}


def test_non_dict_return_is_rejected():
    class _Odd:
        def batch_quote(self, tickers): return [("ES=F", 1)]
    assert live_quotes(_Odd(), ["ES=F"]) == {}


# --------------------------------------------------- base provider default


def test_base_batch_quote_loops_quote_and_drops_incomplete_rows():
    class _P(MarketDataProvider):
        def quote(self, ticker):
            return {
                "GOOD": {"price": 10.0, "prev_close": 9.0, "as_of": "t"},
                "NOPREV": {"price": 10.0, "prev_close": None},
                "ZERO": {"price": 10.0, "prev_close": 0},
                "NOPRICE": {"price": None, "prev_close": 9.0},
            }[ticker]

    out = _P().batch_quote(["GOOD", "NOPREV", "ZERO", "NOPRICE"])
    assert list(out) == ["GOOD"]
    assert out["GOOD"] == {"last": 10.0, "prev_close": 9.0, "as_of": "t"}


def test_base_batch_quote_skips_a_symbol_that_raises():
    class _P(MarketDataProvider):
        def quote(self, ticker):
            if ticker == "BAD":
                raise RuntimeError("no such symbol")
            return {"price": 2.0, "prev_close": 1.0, "as_of": "t"}

    assert list(_P().batch_quote(["BAD", "OK"])) == ["OK"]


# ----------------------------------------------------------- panel wiring


class _BarsOnly:
    """A provider with no quote feed at all — the pre-existing adapter shape."""

    def __init__(self, quotes=None):
        self.quotes = quotes or {}
        self.asked = []

    def batch_history(self, symbols, period="1y", interval="1d"):
        # 7589.25 then 7680.00: the gap that read as +1.196%.
        vals = [7000.0 + i for i in range(260)] + [7589.25, 7680.0]
        return {s: _frame(vals) for s in symbols}


class _Feed(_BarsOnly):
    """Bars that disagree with the quote exactly as Yahoo's futures bars do."""

    def batch_quote(self, tickers):
        self.asked.append(list(tickers))
        return {t: self.quotes[t] for t in tickers if t in self.quotes}


def test_macro_prefers_the_quote_for_a_futures_row():
    sym = "ES=F"
    feed = _Feed({sym: {"last": 7680.0, "prev_close": 7672.5, "as_of": "t"}})
    rows = {r["symbol"]: r for g in macro.analyse(feed)["groups"].values() for r in g}
    assert rows[sym]["chg_1d"] == pytest.approx(0.098, abs=0.001)
    assert rows[sym]["chg_1d_source"] == "quote"


def test_macro_keeps_bar_arithmetic_for_a_row_the_feed_skips():
    """Per-row fallback, not all-or-nothing: one uncovered symbol must not
    drag the rest of the strip back onto the bars."""
    covered = "ES=F"
    feed = _Feed({covered: {"last": 7680.0, "prev_close": 7672.5}})
    rows = {r["symbol"]: r for g in macro.analyse(feed)["groups"].values() for r in g}
    others = [r for s, r in rows.items() if s != covered]
    assert others, "expected more than one instrument in the strip"
    assert all(r["chg_1d_source"] == "bars" for r in others)
    assert all(r["chg_1d"] == pytest.approx(1.196, abs=0.001) for r in others)


def test_macro_survives_a_provider_with_no_quote_feed():
    rows = {r["symbol"]: r for g in macro.analyse(_BarsOnly())["groups"].values()
            for r in g}
    assert rows
    assert all(r["chg_1d_source"] == "bars" for r in rows.values())


def test_macro_asks_for_every_instrument_once():
    feed = _Feed()
    macro.analyse(feed)
    assert len(feed.asked) == 1
    assert sorted(feed.asked[0]) == sorted(i["symbol"] for i in macro.INSTRUMENTS)


def test_overnight_panel_prefers_the_quote_for_its_crosses():
    sym = gm.CROSSES[0]["symbol"]
    feed = _Feed({sym: {"last": 7680.0, "prev_close": 7672.5, "as_of": "t"}})
    out = gm.build(feed)
    row = next(c for c in out["crosses"] if c["symbol"] == sym)
    assert row["chg_1d"] == pytest.approx(0.098, abs=0.001)
    assert row["chg_1d_source"] == "quote"


def test_overnight_panel_survives_a_provider_with_no_quote_feed():
    out = gm.build(_BarsOnly())
    assert out["available"] is True
    assert all(c["chg_1d_source"] == "bars" for c in out["crosses"])


# ------------------------------------------------- yfinance adapter caching


class _FastInfo(dict):
    pass


def _yf_stub(calls, known):
    class _Ticker:
        def __init__(self, symbol):
            self.symbol = symbol

        @property
        def fast_info(self):
            calls.append(self.symbol)
            if self.symbol not in known:
                raise RuntimeError("possibly delisted")
            last, prev = known[self.symbol]
            return _FastInfo(lastPrice=last, previousClose=prev)

    return _Ticker


@pytest.fixture()
def yf_adapter(monkeypatch):
    """A YFinanceProvider whose fast_info is a stub, with a clean cache."""
    from app.providers import yf as adapter

    for key in [k for k in adapter._CACHE if k.startswith("fastq:")]:
        del adapter._CACHE[key]
    calls: list = []
    known = {"ES=F": (7680.0, 7672.5), "GC=F": (4350.7, 4367.2),
             "^GSPC": (7600.0, 7585.5), "CL=F": (102.29, 104.78)}
    monkeypatch.setattr(adapter.yf, "Ticker", _yf_stub(calls, known))
    yield adapter.YFinanceProvider(), calls
    for key in [k for k in adapter._CACHE if k.startswith("fastq:")]:
        del adapter._CACHE[key]


def test_adapter_reads_the_two_numbers_off_fast_info(yf_adapter):
    provider, _ = yf_adapter
    out = provider.batch_quote(["ES=F"])
    assert out["ES=F"]["last"] == 7680.0
    assert out["ES=F"]["prev_close"] == 7672.5
    assert out["ES=F"]["as_of"]


def test_overlapping_callers_fetch_each_symbol_once(yf_adapter):
    """The macro strip and the overnight panel both want gold and the S&P.
    Keyed on the symbol list instead, a cold home page paid for those twice."""
    provider, calls = yf_adapter
    provider.batch_quote(["ES=F", "GC=F", "^GSPC"])
    assert sorted(calls) == ["%s" % s for s in sorted(["ES=F", "GC=F", "^GSPC"])]
    calls.clear()
    provider.batch_quote(["GC=F", "^GSPC", "CL=F"])
    assert calls == ["CL=F"]


def test_a_symbol_the_feed_cannot_answer_is_not_refetched(yf_adapter):
    """Caching the failure: otherwise a delisted symbol costs a request, and a
    404 round-trip, on every single home-page build."""
    provider, calls = yf_adapter
    assert provider.batch_quote(["NOTASYMBOL"]) == {}
    assert calls == ["NOTASYMBOL"]
    calls.clear()
    assert provider.batch_quote(["NOTASYMBOL"]) == {}
    assert calls == []


def test_a_repeat_request_hits_no_network(yf_adapter):
    provider, calls = yf_adapter
    provider.batch_quote(["ES=F", "GC=F"])
    calls.clear()
    assert set(provider.batch_quote(["ES=F", "GC=F"])) == {"ES=F", "GC=F"}
    assert calls == []


def test_duplicate_symbols_in_one_request_are_fetched_once(yf_adapter):
    provider, calls = yf_adapter
    provider.batch_quote(["ES=F", "ES=F", "ES=F"])
    assert calls == ["ES=F"]


def test_only_requested_symbols_come_back(yf_adapter):
    provider, _ = yf_adapter
    provider.batch_quote(["ES=F", "GC=F"])
    assert set(provider.batch_quote(["GC=F"])) == {"GC=F"}


def test_expiry_refetches(yf_adapter, monkeypatch):
    provider, calls = yf_adapter
    provider.batch_quote(["ES=F"])
    calls.clear()
    from app.providers import yf as adapter
    # The real clock has to be captured first: `adapter.time` is the time module
    # itself, so a lambda reaching for time.time() would call its own patch.
    real_time = adapter.time.time
    monkeypatch.setattr(adapter.time, "time",
                        lambda: real_time() + provider.TTL_QUOTE + 1)
    provider.batch_quote(["ES=F"])
    assert calls == ["ES=F"]


# ----------------------------------------------------------- forex panel


def test_forex_prefers_the_quote_for_every_pair():
    """Every row on this panel is a cross, which is the case the bars get wrong."""
    from app.analytics import forex as fx

    sym = fx.PAIRS[0]["symbol"]
    feed = _Feed({sym: {"last": 7680.0, "prev_close": 7672.5, "as_of": "t"}})
    row = next(r for r in fx.build(feed)["pairs"] if r["symbol"] == sym)
    assert row["snapshot"]["chg_1d"] == pytest.approx(0.098, abs=0.001)
    assert row["snapshot"]["chg_1d_source"] == "quote"


def test_forex_survives_a_provider_with_no_quote_feed():
    from app.analytics import forex as fx

    rows = fx.build(_BarsOnly())["pairs"]
    assert rows
    assert all(r["snapshot"]["chg_1d_source"] == "bars" for r in rows)


def test_forex_monthly_reading_is_untouched():
    """`_reading` is built on chg_20d, which stays on the bar basis."""
    from app.analytics import forex as fx

    sym = fx.PAIRS[0]["symbol"]
    quoted = fx.build(_Feed({sym: {"last": 7680.0, "prev_close": 7672.5}}))
    plain = fx.build(_BarsOnly())
    by_sym = {r["symbol"]: r for r in plain["pairs"]}
    for row in quoted["pairs"]:
        assert row["reading"] == by_sym[row["symbol"]]["reading"]


def test_forex_empty_frame_gets_no_change_figure():
    """An empty snapshot must stay empty rather than picking up a bare source
    tag that would read as a row with data behind it."""
    from app.analytics import forex as fx

    class _Empty(_BarsOnly):
        def batch_history(self, symbols, period="1y", interval="1d"):
            return {}

    rows = fx.build(_Empty())["pairs"]
    assert rows
    assert all(r["snapshot"] == {} for r in rows)


# ------------------------------------------------- instrument drill-down


def test_drill_down_reconciles_like_the_strip(monkeypatch):
    """The strip and the chart a reader clicks through to must not disagree
    about the same instrument's change. Drives the endpoint, because the defect
    this replaced was in the wiring rather than in the arithmetic."""
    from fastapi.testclient import TestClient

    import app.main as main

    quote = {"last": 7680.0, "prev_close": 7672.5, "as_of": "t"}
    vals = [7000.0 + i for i in range(260)] + [7589.25, 7680.0]
    frame = _frame(vals)

    class _One:
        def history(self, ticker, period="2y", interval="1d"):
            return frame

        def batch_quote(self, tickers):
            return {t: quote for t in tickers if t == "ES=F"}

    monkeypatch.setattr(main, "YF_PROVIDER", _One())
    body = TestClient(main.app).get(
        "/api/instrument", params={"symbol": "ES=F", "range": "1y"}).json()

    assert body["snapshot"]["chg_1d"] == pytest.approx(0.098, abs=0.001)
    assert body["snapshot"]["chg_1d_source"] == "quote"

    # Bar arithmetic on the same frame is the number this used to publish.
    assert macro.snapshot(frame, "x")["chg_1d"] == pytest.approx(1.196, abs=0.001)


def test_drill_down_falls_back_when_the_symbol_has_no_quote():
    """Arbitrary symbols reach this endpoint, not just the strip's own."""
    from fastapi.testclient import TestClient

    import app.main as main

    vals = [7000.0 + i for i in range(260)] + [7589.25, 7680.0]

    class _One:
        def history(self, ticker, period="2y", interval="1d"):
            return _frame(vals)

        def batch_quote(self, tickers):
            return {}

    client = TestClient(main.app)
    original = main.YF_PROVIDER
    main.YF_PROVIDER = _One()
    try:
        body = client.get("/api/instrument",
                          params={"symbol": "WHATEVER", "range": "1y"}).json()
    finally:
        main.YF_PROVIDER = original

    assert body["snapshot"]["chg_1d"] == pytest.approx(1.196, abs=0.001)
    assert body["snapshot"]["chg_1d_source"] == "bars"
