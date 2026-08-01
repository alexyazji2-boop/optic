"""Universe construction and prefilter gates.

The tracker scans the whole NASDAQ, so two things decide what it can ever trade:
which symbols are considered securities at all, and which of those survive the
liquidity and volatility gates. Both are silent filters — a bug in either makes
the tracker quietly narrower, with nothing in the UI to say so.
"""

from __future__ import annotations

import os
import sys
import tempfile

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import universe                       # noqa: E402
from app.analytics import screen               # noqa: E402

# The real pacing exists to avoid the upstream rate limit; against a fake provider
# it would just make the suite take a minute per test.
screen.CHUNK_PAUSE_SECONDS = 0.0
screen.RETRY_PAUSE_SECONDS = 0.0

# And point the persisted ranking somewhere disposable, so the suite neither reads
# the real one (which would make the cache tests pass for the wrong reason) nor
# overwrites it with two synthetic symbols.
screen.CACHE_DIR = tempfile.mkdtemp(prefix="optic-screen-test-")
screen.CACHE_PATH = os.path.join(screen.CACHE_DIR, "screen_ranking.json")


def _clear_cache():
    screen._CACHE.clear()
    try:
        os.remove(screen.CACHE_PATH)
    except OSError:
        pass


# --------------------------------------------------------------- the universe


def test_common_stock_is_kept():
    assert universe._is_common_stock("AAPL", "Apple Inc. - Common Stock", "N", "N", "N")


def test_etfs_warrants_and_units_are_dropped():
    assert not universe._is_common_stock("QQQ", "Invesco QQQ Trust", "Y", "N", "N")
    assert not universe._is_common_stock("ABCDW", "Acme Corp - Warrant", "N", "N", "N")
    assert not universe._is_common_stock("ABCDU", "Acme Corp - Unit", "N", "N", "N")
    assert not universe._is_common_stock("ABCDR", "Acme Corp - Right", "N", "N", "N")
    assert not universe._is_common_stock("ABCP", "Acme Corp - 6% Preferred", "N", "N", "N")


def test_test_issues_and_distressed_listings_are_dropped():
    assert not universe._is_common_stock("ZVZZT", "NASDAQ TEST STOCK", "N", "Y", "N")
    # 'D' is deficient, 'E' delinquent — real securities, but not ones to model.
    assert not universe._is_common_stock("ABCD", "Acme Corp - Common Stock", "N", "N", "D")


def test_parse_skips_the_header_and_footer_lines():
    text = (
        "Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares\n"
        "AAPL|Apple Inc. - Common Stock|Q|N|N|100|N|N\n"
        "QQQ|Invesco QQQ Trust|G|N|N|100|Y|N\n"
        "File Creation Time: 0730202614:01|||||||\n"
    )
    assert universe._parse(text) == ["AAPL"]


# ----------------------------------------------------------------- the screen


def _frame(price: float, volume: float, bars: int = 260, drift: float = 0.0,
           daily_range: float = 0.01) -> pd.DataFrame:
    """A synthetic price series with a controllable trend and daily range."""
    closes = np.array([price * (1.0 + drift) ** (i / bars) for i in range(bars)])
    closes = closes * price / closes[-1]        # end exactly at `price`
    idx = pd.date_range("2025-01-01", periods=bars, freq="B")
    return pd.DataFrame({
        "Open": closes,
        "High": closes * (1 + daily_range),
        "Low": closes * (1 - daily_range),
        "Close": closes,
        "Volume": np.full(bars, volume),
    }, index=idx)


class _Provider:
    """Serves prepared frames, and records what was asked for."""

    def __init__(self, frames):
        self.frames = frames
        self.calls = 0

    def batch_history(self, tickers, period="1y", interval="1d"):
        self.calls += 1
        return {t: self.frames[t] for t in tickers if t in self.frames}


def _run(frames, **kw):
    _clear_cache()                              # each test screens fresh
    return screen.run(_Provider(frames), list(frames), progress=None, **kw)


def test_penny_stocks_and_thin_names_are_excluded():
    frames = {
        "LIQUID": _frame(100.0, 1_000_000),     # $100M a day
        "PENNY": _frame(2.0, 50_000_000),       # liquid but under the price floor
        "THIN": _frame(100.0, 1_000),           # $100k a day
    }
    out = _run(frames)
    assert [m["symbol"] for m in out["shortlist"]] == ["LIQUID"]
    assert out["dropped_illiquid"] == 2


def test_short_history_is_excluded():
    out = _run({"NEW": _frame(100.0, 1_000_000, bars=60)})
    assert out["shortlist"] == []
    assert out["dropped_short_history"] == 1


def test_wild_names_are_excluded():
    frames = {"CALM": _frame(100.0, 1_000_000, daily_range=0.01),
              "WILD": _frame(100.0, 1_000_000, daily_range=0.15)}
    out = _run(frames)
    assert [m["symbol"] for m in out["shortlist"]] == ["CALM"]
    assert out["dropped_too_volatile"] == 1


def test_a_name_that_already_doubled_is_excluded():
    """The regression that mattered: pure trend scoring loves a post-catalyst
    biotech, because every average is below price and every momentum term maxes
    out — which is exactly the setup where the move is already over."""
    frame = _frame(100.0, 5_000_000)
    frame.iloc[-1, frame.columns.get_loc("Close")] = 100.0
    # Make the price 21 bars ago a third of today's, i.e. up ~200% in a month.
    frame.iloc[-21, frame.columns.get_loc("Close")] = 33.0
    out = _run({"MOONED": frame})
    assert out["dropped_already_moved"] == 1
    assert out["shortlist"] == []


def test_uptrend_scores_positive_and_downtrend_negative():
    frames = {"UP": _frame(100.0, 2_000_000, drift=0.6),
              "DOWN": _frame(100.0, 2_000_000, drift=-0.4)}
    out = _run(frames)
    by_symbol = {m["symbol"]: m["score"] for m in out["shortlist"]}
    assert by_symbol["UP"] > 0 > by_symbol["DOWN"]


def test_held_names_are_excluded_but_still_counted():
    frames = {"HELD": _frame(100.0, 5_000_000, drift=0.6),
              "FREE": _frame(50.0, 5_000_000, drift=0.5)}
    out = _run(frames, exclude=["HELD"])
    assert [m["symbol"] for m in out["shortlist"]] == ["FREE"]
    assert out["already_held"] == 1


def test_ranking_is_cached_so_a_second_scan_costs_nothing():
    """The screen is ~3,000 downloads; re-running it back-to-back is what earns a
    rate limit, and the rate limit then breaks the options stage."""
    frames = {"AAA": _frame(100.0, 5_000_000, drift=0.5)}
    _clear_cache()
    provider = _Provider(frames)
    first = screen.run(provider, list(frames))
    second = screen.run(provider, list(frames))
    assert provider.calls == 1
    assert first["ranking_reused"] is False
    assert second["ranking_reused"] is True


def test_force_bypasses_the_cache():
    frames = {"AAA": _frame(100.0, 5_000_000, drift=0.5)}
    _clear_cache()
    provider = _Provider(frames)
    screen.run(provider, list(frames))
    screen.run(provider, list(frames), force=True)
    assert provider.calls == 2


def test_shortlist_respects_top_n():
    frames = {"S{}".format(i): _frame(100.0 + i, 5_000_000, drift=0.1 * i)
              for i in range(1, 9)}
    out = _run(frames, top_n=3)
    assert len(out["shortlist"]) == 3
