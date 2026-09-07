"""The watchlist feed.

Every row carries a "what changed" line and a signal. The tests are about
honesty and about ranking: the failure mode of a feature like this is a column
that is never empty because something is always manufactured to fill it.
"""

import numpy as np
import pandas as pd
import pytest

from app.analytics import watchlist


def _frame(closes, volumes=None):
    n = len(closes)
    idx = pd.date_range("2026-01-01", periods=n, freq="B")
    return pd.DataFrame({
        "Close": closes,
        "Volume": volumes if volumes is not None else np.full(n, 1_000_000.0),
    }, index=idx)


class _Provider:
    """Returns exactly the frames it was given, and records the call count."""

    def __init__(self, frames):
        self.frames = frames
        self.calls = 0

    def batch_history(self, tickers, period="1y", interval="1d"):
        self.calls += 1
        self.asked = list(tickers)
        return {t: self.frames[t] for t in tickers if t in self.frames}


@pytest.fixture(autouse=True)
def _clear_cache():
    """The module caches frames for 90s; tests must not see each other's."""
    watchlist._cache.clear()
    yield
    watchlist._cache.clear()


def _flat(n=80, level=100.0):
    return _frame(np.full(n, level))


# ------------------------------------------------------------ the batched pull

def test_the_whole_list_costs_one_request():
    """Per-symbol fetches would make a ten-name list unusable. The docstring
    claims one batched pull; this is the claim."""
    frames = {s: _flat() for s in ("AAA", "BBB", "CCC", "SPY")}
    prov = _Provider(frames)
    watchlist.build(prov, ["AAA", "BBB", "CCC"])
    assert prov.calls == 1


def test_the_benchmark_is_always_fetched_even_if_not_on_the_list():
    """The leadership comparison needs it, and asking for it separately would
    double the request count."""
    prov = _Provider({s: _flat() for s in ("AAA", "SPY")})
    watchlist.build(prov, ["AAA"])
    assert watchlist.BENCH in prov.asked


def test_reordering_the_list_hits_the_cache_but_adding_does_not():
    """Keyed on the symbol SET. Re-sorting a watchlist in the UI must not
    refetch; adding a name must."""
    prov = _Provider({s: _flat() for s in ("AAA", "BBB", "CCC", "SPY")})
    watchlist.build(prov, ["AAA", "BBB"])
    watchlist.build(prov, ["BBB", "AAA"])
    assert prov.calls == 1, "reorder should not refetch"
    watchlist.build(prov, ["AAA", "BBB", "CCC"])
    assert prov.calls == 2, "a new symbol must refetch"


# ------------------------------------------------------------- what changed

def test_a_quiet_name_reports_nothing_rather_than_something():
    """The whole point of the column. A flat series has not done anything, and
    filling the cell so it is never blank would make every row look eventful."""
    prov = _Provider({"AAA": _flat(), "SPY": _flat()})
    row = watchlist.build(prov, ["AAA"])["rows"][0]
    assert row["changed"] is None


def test_a_breakout_is_measured_against_the_window_before_today():
    """Including today's print in the range it is breaking means price can never
    exceed its own high and the branch is dead."""
    closes = list(np.full(40, 100.0)) + [105.0]
    prov = _Provider({"AAA": _frame(np.array(closes)), "SPY": _flat(41)})
    row = watchlist.build(prov, ["AAA"])["rows"][0]
    assert row["changed"]["text"] == "20-day breakout"
    assert "100.00" in row["changed"]["why"]


def test_a_breakdown_is_detected_too():
    closes = list(np.full(40, 100.0)) + [94.0]
    prov = _Provider({"AAA": _frame(np.array(closes)), "SPY": _flat(41)})
    assert watchlist.build(prov, ["AAA"])["rows"][0]["changed"]["text"] == "20-day breakdown"


def test_a_big_move_is_scaled_to_the_name_s_own_volatility():
    """2% is enormous for a staple and quiet for a leveraged semiconductor fund.
    An absolute threshold would flag the wrong names every day."""
    # A smooth arc, so the prior 20-day high sits above the final close and the
    # breakout branch — which outranks this one by design — cannot fire. Two
    # earlier fixtures failed for instructive reasons: a drifting series made
    # the +4% day a genuine breakout, and a step change to create a prior high
    # put a huge single-bar return inside the sigma window and suppressed the
    # very branch under test. A sine has a high without a violent bar.
    t = np.linspace(0, np.pi, 60)
    base = 100.0 + 18.0 * np.sin(t)
    calm = base * (1 + np.random.default_rng(7).normal(0, 0.002, 60))
    wild = base * (1 + np.random.default_rng(7).normal(0, 0.05, 60))
    # The same +4% final day on both.
    calm = np.append(calm, calm[-1] * 1.04)
    wild = np.append(wild, wild[-1] * 1.04)
    prov = _Provider({"CALM": _frame(calm), "WILD": _frame(wild), "SPY": _flat(61)})
    rows = {r["symbol"]: r for r in watchlist.build(prov, ["CALM", "WILD"])["rows"]}
    calm_change = rows["CALM"]["changed"]
    assert calm_change and calm_change["text"] == "Outsized move"
    wild_change = rows["WILD"]["changed"]
    assert not (wild_change and wild_change["text"] == "Outsized move"), \
        "4% is inside this name's own noise"


def test_a_range_break_outranks_a_big_move():
    """Ordered by how much it would change a reader's mind. A breakout is a
    change of state; a large day is a Tuesday."""
    closes = list(np.full(40, 100.0)) + [130.0]
    prov = _Provider({"AAA": _frame(np.array(closes)), "SPY": _flat(41)})
    row = watchlist.build(prov, ["AAA"])["rows"][0]
    assert row["changed"]["text"] == "20-day breakout"


def test_every_change_line_cites_the_number_behind_it():
    """An observation you cannot check is a plausible sentence."""
    closes = list(np.full(40, 100.0)) + [105.0]
    prov = _Provider({"AAA": _frame(np.array(closes)), "SPY": _flat(41)})
    changed = watchlist.build(prov, ["AAA"])["rows"][0]["changed"]
    assert changed["why"] and any(ch.isdigit() for ch in changed["why"])


def test_a_short_history_produces_no_change_line_rather_than_a_wrong_one():
    prov = _Provider({"AAA": _flat(8), "SPY": _flat(8)})
    assert watchlist.build(prov, ["AAA"])["rows"][0]["changed"] is None


# ------------------------------------------------------------------ signal

def test_the_signal_is_qualitative():
    """A 0-100 here would imply a tested model. This is a stack read."""
    n = 80
    rising = _frame(np.linspace(50, 150, n))
    falling = _frame(np.linspace(150, 50, n))
    prov = _Provider({"UP": rising, "DOWN": falling, "SPY": _flat(n)})
    rows = {r["symbol"]: r for r in watchlist.build(prov, ["UP", "DOWN"])["rows"]}
    assert rows["UP"]["signal"] == "bullish"
    assert rows["DOWN"]["signal"] == "bearish"
    for row in rows.values():
        assert isinstance(row["signal"], str)
        assert row["signal_why"]


def test_a_short_history_signal_says_unknown_not_neutral():
    """"Neutral" is a reading. "Not enough history" is the absence of one."""
    prov = _Provider({"AAA": _flat(20), "SPY": _flat(20)})
    row = watchlist.build(prov, ["AAA"])["rows"][0]
    assert row["signal"] == "unknown"
    assert "history" in row["signal_why"]


# ------------------------------------------------------------- missing data

def test_a_symbol_with_no_history_is_reported_not_dropped():
    """Silently omitting it means the reader's list is shorter than the list
    they saved, with nothing saying why."""
    prov = _Provider({"AAA": _flat(), "SPY": _flat()})
    out = watchlist.build(prov, ["AAA", "NOPE"])
    assert out["unavailable"] == ["NOPE"]
    bad = next(r for r in out["rows"] if r["symbol"] == "NOPE")
    assert bad["available"] is False and bad["reason"]
    assert len(out["rows"]) == 2


def test_an_empty_list_is_an_answer():
    prov = _Provider({})
    out = watchlist.build(prov, [])
    assert out["available"] is True and out["rows"] == []
    assert "Add a symbol" in out["reason_none"]
    assert prov.calls == 0, "an empty list should not hit the provider"


def test_a_provider_failure_degrades_every_row_not_the_call():
    class Broken:
        def batch_history(self, *a, **k):
            raise RuntimeError("upstream down")
    out = watchlist.build(Broken(), ["AAA", "BBB"])
    assert out["available"] is True
    assert all(r["available"] is False for r in out["rows"])


def test_the_method_says_no_model_wrote_this():
    prov = _Provider({"AAA": _flat(), "SPY": _flat()})
    method = watchlist.build(prov, ["AAA"])["method"]
    assert "Nothing here is written by a model" in method
